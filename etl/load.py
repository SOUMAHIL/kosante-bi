# =============================================================
# KoSanté BI — load.py
# =============================================================
# RÔLE : Charger les CSV transformés dans DuckDB
#        et construire le schéma analytique
#
# ENTRÉE  : data/processed/*.csv
# SORTIE  : data/kosante.duckdb
#
# LOGIQUE FILE ACTIVE (Ko'Khoua) :
#   Un patient est ACTIF si :
#     ✅ Il a une dispensation ARV (TblRegime)
#     ✅ DatePDV >= aujourd'hui
#     ✅ Pas décédé (DecesDate IS NULL)
#     ✅ Pas transféré (TransfDate IS NULL)
#
# TOUS LES KPIs sont calculés sur la FILE ACTIVE uniquement
# SAUF le dépistage CDV (table indépendante)
#
# USAGE :
#   python etl/load.py
# =============================================================

import duckdb
import pandas as pd
from pathlib import Path
import sys
import logging
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    PROCESSED_DIR,
    DUCKDB_PATH,
    CV_SUPPRIMEE_SEUIL,
    PERDU_DE_VUE_JOURS,
    CD4_BAS_SEUIL
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


# =============================================================
# CONNEXION DUCKDB
# =============================================================
def connecter_duckdb() -> duckdb.DuckDBPyConnection:
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()
        log.info("  🗑️  Ancienne base supprimée → recréation propre")
    conn = duckdb.connect(str(DUCKDB_PATH))
    log.info(f"  ✅ DuckDB créé → {DUCKDB_PATH.name}")
    return conn


def charger_csv(nom_table: str) -> pd.DataFrame:
    chemin = PROCESSED_DIR / f"{nom_table}.csv"
    df = pd.read_csv(chemin, low_memory=False)
    log.info(f"  📂 {nom_table} — {len(df):,} lignes")
    return df


# =============================================================
# TABLES BRUTES — chargement direct
# =============================================================
def charger_tables_brutes(conn, dfs: dict) -> None:
    """
    Charge toutes les tables brutes transformées dans DuckDB
    telles quelles — source de vérité pour tous les calculs
    """
    log.info("\n── Chargement tables brutes ────────────────────")

    for nom, df in dfs.items():
        conn.execute(f"DROP TABLE IF EXISTS {nom}")
        conn.execute(f"CREATE TABLE {nom} AS SELECT * FROM df")
        nb = conn.execute(f"SELECT COUNT(*) FROM {nom}").fetchone()[0]
        log.info(f"  ✅ {nom:<30} → {nb:>8,} lignes")


# =============================================================
# VUE : file_active
# =============================================================
def creer_vue_file_active(conn) -> None:
    """
    Reproduction exacte de la logique Ko'Khoua :
    File active = patients avec dispensation ARV récente
                  dont DatePDV >= aujourd'hui
                  et non décédés / non transférés

    Source : TblRegime (dernière dispensation) + TblDossPatient
    """
    conn.execute("DROP VIEW IF EXISTS file_active")
    conn.execute("""
        CREATE VIEW file_active AS
        WITH derniere_dispensation AS (
            -- Dernière dispensation ARV par patient
            SELECT
                r.NumPatient,
                r.DateRegime,
                r.REGIME,
                r.JOURS,
                r.DateProchainRdv,
                r.DatePDV,
                r.Actif_Pharmacie
            FROM TblRegime r
            WHERE r.Derniere_Dispensation = TRUE
              AND r.REGIME IS NOT NULL
        )
        SELECT
            p.NumInc,
            p.NumNational,
            p.Nom,
            p.Prenoms,
            p.Sexe_label,
            p.DateNaiss,
            p.Age,
            p.DateAdmi,
            p.CommuneVillage,
            p.NomCommunautaire,
            p.TypePatient,
            p.StadeOMS,
            p.VIHType,
            d.REGIME           AS DernierRegime,
            d.DateRegime       AS DerniereDispensation,
            d.JOURS,
            d.DateProchainRdv,
            d.DatePDV,
            -- Statut détaillé
            CASE
                WHEN CAST(d.DatePDV AS DATE) >= CURRENT_DATE THEN 'Actif'
                ELSE 'Perdu de vue'
            END AS StatutFile
        FROM TblDossPatient p
        INNER JOIN derniere_dispensation d
            ON p.NumNational = d.NumPatient
        WHERE
            -- Pas décédé
            (p.DecesDate IS NULL OR p.DecesDate = '')
            -- Pas transféré
            AND (p.TransfDate IS NULL OR p.TransfDate = '')
            -- NumInc valide
            AND p.NumInc > 0
            -- A une dispensation ARV
            AND d.REGIME IS NOT NULL
    """)

    nb_total = conn.execute("SELECT COUNT(*) FROM file_active").fetchone()[0]
    nb_actifs = conn.execute(
        "SELECT COUNT(*) FROM file_active WHERE StatutFile = 'Actif'"
    ).fetchone()[0]
    nb_pdv = conn.execute(
        "SELECT COUNT(*) FROM file_active WHERE StatutFile = 'Perdu de vue'"
    ).fetchone()[0]

    log.info(f"  ✅ file_active créée :")
    log.info(f"     Actifs       : {nb_actifs:,}")
    log.info(f"     Perdus de vue: {nb_pdv:,}")
    log.info(f"     Total        : {nb_total:,}")


# =============================================================
# VUE : patients_rdv_manque
# =============================================================
def creer_vue_rdv_manque(conn) -> None:
    """
    Patients en retard de RDV mais pas encore perdus de vue :
    DateProchainRdv < aujourd'hui
    ET DatePDV >= aujourd'hui
    → Retard entre 1 et 27 jours
    → Toujours dans la file active
    → Nécessitent une relance
    """
    conn.execute("DROP VIEW IF EXISTS patients_rdv_manque")
    conn.execute("""
        CREATE VIEW patients_rdv_manque AS
        SELECT
            NumInc,
            NumNational,
            Nom,
            Prenoms,
            NomCommunautaire,
            DernierRegime,
            DerniereDispensation,
            DateProchainRdv,
            DatePDV,
            DATEDIFF('day',
                CAST(DateProchainRdv AS DATE),
                CURRENT_DATE
            ) AS jours_retard_rdv
        FROM file_active
        WHERE StatutFile = 'Actif'
          AND CAST(DateProchainRdv AS DATE) < CURRENT_DATE
          AND CAST(DatePDV AS DATE) >= CURRENT_DATE
        ORDER BY jours_retard_rdv DESC
    """)

    nb = conn.execute(
        "SELECT COUNT(*) FROM patients_rdv_manque"
    ).fetchone()[0]
    log.info(f"  ✅ patients_rdv_manque : {nb:,} patients en retard RDV (1-27 jours)")


# =============================================================
# VUE : perdus_de_vue
# =============================================================
def creer_vue_perdus_de_vue(conn) -> None:
    """
    Patients perdus de vue :
    DatePDV < aujourd'hui (≥ 28 jours sans venir)
    Hors file active — ni décédés ni transférés
    """
    conn.execute("DROP VIEW IF EXISTS perdus_de_vue")
    conn.execute("""
        CREATE VIEW perdus_de_vue AS
        SELECT
            NumInc,
            NumNational,
            Nom,
            Prenoms,
            NomCommunautaire,
            DernierRegime,
            DerniereDispensation,
            DateProchainRdv,
            DatePDV,
            DATEDIFF('day',
                CAST(DatePDV AS DATE),
                CURRENT_DATE
            ) AS jours_depuis_pdv
        FROM file_active
        WHERE StatutFile = 'Perdu de vue'
        ORDER BY jours_depuis_pdv DESC
    """)

    nb = conn.execute("SELECT COUNT(*) FROM perdus_de_vue").fetchone()[0]
    log.info(f"  ✅ perdus_de_vue : {nb:,} patients perdus de vue (≥28 jours)")


# =============================================================
# VUE : kpis_file_active
# =============================================================
def creer_vue_kpis(conn) -> None:
    """
    KPIs principaux calculés sur la FILE ACTIVE uniquement
    Cascade 95-95-95 Ko'Khoua
    """
    conn.execute("DROP VIEW IF EXISTS kpis_file_active")
    conn.execute(f"""
        CREATE VIEW kpis_file_active AS
        WITH
        -- Base : patients actifs uniquement
        actifs AS (
            SELECT NumInc, NumNational
            FROM file_active
            WHERE StatutFile = 'Actif'
        ),
        -- Nb patients actifs
        nb_actifs AS (
            SELECT COUNT(*) AS total_actifs FROM actifs
        ),
        -- CV sur patients actifs — dernière CV uniquement
        cv_actifs AS (
            SELECT
                COUNT(*) FILTER (
                    WHERE cv.CV_Statut = 'Supprimée'
                ) AS nb_cv_supprimee,
                COUNT(*) FILTER (
                    WHERE cv.CV_Statut != 'Non renseigné'
                ) AS nb_cv_evalue,
                COUNT(*) AS nb_cv_total
            FROM TblChargesVirales cv
            INNER JOIN actifs a ON cv.Patient = a.NumInc
            WHERE cv.CV_Derniere = TRUE
        ),
        -- CD4 moyen sur patients actifs — dernier CD4
        cd4_actifs AS (
            SELECT
                ROUND(AVG(cd4.CD4Nb), 0) AS cd4_moyen,
                COUNT(*) FILTER (
                    WHERE cd4.CD4Nb < {CD4_BAS_SEUIL}
                ) AS nb_cd4_bas
            FROM TblDossExamensBio cd4
            INNER JOIN actifs a ON cd4.Patient = a.NumInc
            WHERE cd4.CD4_Dernier = TRUE
              AND cd4.CD4Nb IS NOT NULL
        ),
        -- Statut CV (Stable/Non Stable/NE) sur patients actifs
        statut_cv_actifs AS (
            SELECT
                COUNT(*) FILTER (
                    WHERE sc.StatutCV = 'Stable'
                ) AS nb_stable,
                COUNT(*) FILTER (
                    WHERE sc.StatutCV = 'Non Stable'
                ) AS nb_non_stable,
                COUNT(*) FILTER (
                    WHERE sc.StatutCV = 'NE'
                ) AS nb_ne
            FROM StatutCV_Patient sc
            INNER JOIN actifs a ON sc.NumInc = a.NumInc
        ),
        -- Nouveaux patients du mois courant
        nouveaux_mois AS (
            SELECT
                COUNT(*) FILTER (
                    WHERE p.TypePatient = 'Nouveau Ko''Khoua'
                ) AS nouveaux_kokhoua,
                COUNT(*) FILTER (
                    WHERE p.TypePatient = 'Transfert In'
                ) AS transfert_in
            FROM TblDossPatient p
            WHERE EXTRACT(YEAR  FROM CAST(p.DateAdmi AS DATE))
                  = EXTRACT(YEAR  FROM CURRENT_DATE)
              AND EXTRACT(MONTH FROM CAST(p.DateAdmi AS DATE))
                  = EXTRACT(MONTH FROM CURRENT_DATE)
        ),
        -- RDV manqués
        rdv_manques AS (
            SELECT COUNT(*) AS nb_rdv_manque
            FROM patients_rdv_manque
        ),
        -- Perdus de vue
        pdv AS (
            SELECT COUNT(*) AS nb_perdus_de_vue
            FROM perdus_de_vue
        )
        SELECT
            -- File active
            na.total_actifs,

            -- CV
            ca.nb_cv_supprimee,
            ca.nb_cv_evalue,
            ROUND(ca.nb_cv_supprimee * 100.0 /
                NULLIF(ca.nb_cv_evalue, 0), 1) AS pct_cv_supprimee,

            -- CD4
            cd.cd4_moyen,
            cd.nb_cd4_bas,

            -- Statut CV
            sc.nb_stable,
            sc.nb_non_stable,
            sc.nb_ne,
            ROUND(sc.nb_stable * 100.0 /
                NULLIF(sc.nb_stable + sc.nb_non_stable, 0), 1) AS pct_stable,

            -- Nouveaux patients
            nm.nouveaux_kokhoua,
            nm.transfert_in,

            -- Alertes
            rm.nb_rdv_manque,
            pdv.nb_perdus_de_vue

        FROM nb_actifs na, cv_actifs ca, cd4_actifs cd,
             statut_cv_actifs sc, nouveaux_mois nm,
             rdv_manques rm, pdv
    """)

    log.info(f"  ✅ kpis_file_active créée")


# =============================================================
# VUE : cascade_95_95_95
# =============================================================
def creer_vue_cascade(conn) -> None:
    """
    Cascade 95-95-95 ONUSIDA — standard Côte d'Ivoire
    Calculée sur la file active Ko'Khoua
    """
    conn.execute("DROP VIEW IF EXISTS cascade_95_95_95")
    conn.execute("""
        CREATE VIEW cascade_95_95_95 AS
        WITH
        actifs AS (
            SELECT NumInc FROM file_active WHERE StatutFile = 'Actif'
        ),
        etape1 AS (
            -- 1er 95 : Patients actifs connus et suivis
            SELECT COUNT(*) AS nb FROM actifs
        ),
        etape2 AS (
            -- 2ème 95 : Actifs avec mise sous ARV
            SELECT COUNT(DISTINCT a.NumInc) AS nb
            FROM actifs a
            INNER JOIN TblMiseEnRoute m ON a.NumInc = m.Patient
            WHERE m.DateMiseTARV IS NOT NULL
        ),
        etape3 AS (
            -- 3ème 95 : CV supprimée parmi les actifs évalués
            SELECT
                COUNT(*) FILTER (WHERE cv.CV_Statut = 'Supprimée') AS nb_supprimee,
                COUNT(*) FILTER (WHERE cv.CV_Statut != 'Non renseigné') AS nb_evalue
            FROM TblChargesVirales cv
            INNER JOIN actifs a ON cv.Patient = a.NumInc
            WHERE cv.CV_Derniere = TRUE
        )
        SELECT
            e1.nb                                              AS actifs_connus,
            e2.nb                                             AS sous_arv,
            ROUND(e2.nb * 100.0 / NULLIF(e1.nb, 0), 1)      AS pct_sous_arv,
            e3.nb_supprimee                                   AS cv_supprimee,
            e3.nb_evalue                                      AS cv_evalue,
            ROUND(e3.nb_supprimee * 100.0 /
                NULLIF(e3.nb_evalue, 0), 1)                  AS pct_cv_supprimee,
            95.0                                              AS objectif_pct
        FROM etape1 e1, etape2 e2, etape3 e3
    """)
    log.info(f"  ✅ cascade_95_95_95 créée")


# =============================================================
# VALIDATION FINALE
# =============================================================
def valider_base(conn) -> None:
    log.info("\n" + "=" * 55)
    log.info("  VALIDATION — kosante.duckdb")
    log.info("=" * 55)

    # Tables
    tables = conn.execute("""
        SELECT table_name FROM duckdb_tables()
        ORDER BY table_name
    """).fetchall()
    for (nom,) in tables:
        nb = conn.execute(f"SELECT COUNT(*) FROM {nom}").fetchone()[0]
        log.info(f"  📋 {nom:<35} → {nb:>8,} lignes")

    # KPIs file active
    log.info("\n  ── KPIs FILE ACTIVE ────────────────────────")
    try:
        kpi = conn.execute("SELECT * FROM kpis_file_active").fetchone()
        if kpi:
            log.info(f"  File active (actifs)   : {kpi[0]:,}")
            log.info(f"  CV supprimée           : {kpi[1]:,} / {kpi[2]:,} ({kpi[3]}%)")
            log.info(f"  CD4 moyen              : {kpi[4]} cellules/mm³")
            log.info(f"  Patients stables       : {kpi[6]:,} ({kpi[9]}%)")
            log.info(f"  Patients non stables   : {kpi[7]:,}")
            log.info(f"  Non évalués (NE)       : {kpi[8]:,}")
            log.info(f"  Nouveaux Ko'Khoua/mois : {kpi[10]:,}")
            log.info(f"  Transferts In/mois     : {kpi[11]:,}")
            log.info(f"  RDV manqués            : {kpi[12]:,}")
            log.info(f"  Perdus de vue          : {kpi[13]:,}")
    except Exception as e:
        log.warning(f"  ⚠️  KPIs : {e}")

    # Cascade 95-95-95
    log.info("\n  ── CASCADE 95-95-95 ───────────────────────")
    try:
        c = conn.execute("SELECT * FROM cascade_95_95_95").fetchone()
        if c:
            log.info(f"  ① Actifs connus        : {c[0]:,}")
            log.info(f"  ② Sous ARV             : {c[1]:,} ({c[2]}%) | objectif 95%")
            log.info(f"  ③ CV supprimée         : {c[3]:,} / {c[4]:,} ({c[5]}%) | objectif 95%")
    except Exception as e:
        log.warning(f"  ⚠️  Cascade : {e}")

    log.info("=" * 55)


# =============================================================
# FONCTION PRINCIPALE
# =============================================================
def charger_dans_duckdb() -> None:
    debut = datetime.now()

    log.info("=" * 55)
    log.info("  KoSanté BI — CHARGEMENT DUCKDB")
    log.info("=" * 55)

    conn = connecter_duckdb()

    # --- Chargement CSV ---
    log.info("\n── Chargement CSV transformés ──────────────────")
    dfs = {
        "TblDossPatient":      charger_csv("TblDossPatient"),
        "TblMiseEnRoute":      charger_csv("TblMiseEnRoute"),
        "TblChargesVirales":   charger_csv("TblChargesVirales"),
        "TblDossExamensBio":   charger_csv("TblDossExamensBio"),
        "TblDossSuiviPatient": charger_csv("TblDossSuiviPatient"),
        "TblRegime":           charger_csv("TblRegime"),
        "TblRegistreCDV":      charger_csv("TblRegistreCDV"),
        "StatutCV_Patient":    charger_csv("StatutCV_Patient"),
    }

    # --- Tables brutes ---
    charger_tables_brutes(conn, dfs)

    # --- Vues analytiques ---
    log.info("\n── Création des vues analytiques ───────────────")
    creer_vue_file_active(conn)
    creer_vue_rdv_manque(conn)
    creer_vue_perdus_de_vue(conn)
    creer_vue_kpis(conn)
    creer_vue_cascade(conn)

    # --- Validation ---
    valider_base(conn)

    conn.close()

    duree = (datetime.now() - debut).seconds
    log.info(f"\n✅ DuckDB chargé en {duree}s → {DUCKDB_PATH.name}")


# =============================================================
# POINT D'ENTRÉE
# =============================================================
if __name__ == "__main__":
    charger_dans_duckdb()