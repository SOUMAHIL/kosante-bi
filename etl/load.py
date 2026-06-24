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
            fa.NumInc,
            fa.NumNational,
            fa.Sexe_label,
            fa.Age,
            p.Tel,
            fa.NomCommunautaire,
            fa.DernierRegime,
            fa.DerniereDispensation,
            fa.DateProchainRdv,
            fa.DatePDV,
            DATEDIFF('day',
                CAST(fa.DateProchainRdv AS DATE),
                CURRENT_DATE
            ) AS jours_retard_rdv
        FROM file_active fa
        INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
        WHERE fa.StatutFile = 'Actif'
          AND CAST(fa.DateProchainRdv AS DATE) < CURRENT_DATE
          AND CAST(fa.DatePDV AS DATE) >= CURRENT_DATE
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
            fa.NumInc,
            fa.NumNational,
            fa.Sexe_label,
            fa.Age,
            p.Tel,
            fa.NomCommunautaire,
            fa.DernierRegime,
            fa.DerniereDispensation,
            fa.DateProchainRdv,
            fa.DatePDV,
            DATEDIFF('day',
                CAST(fa.DatePDV AS DATE),
                CURRENT_DATE
            ) AS jours_depuis_pdv
        FROM file_active fa
        INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
        WHERE fa.StatutFile = 'Perdu de vue'
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
        -- Attrition (Perdus de vue + Transferts + Arrets vol. + Deces)
        attr AS (
            SELECT
                COUNT(*) AS nb_attrition,
                COUNT(*) FILTER (
                    WHERE categorie_attrition = 'Perdu de vue'
                ) AS nb_pdv,
                COUNT(*) FILTER (
                    WHERE categorie_attrition = 'Transfert'
                ) AS nb_transfert,
                COUNT(*) FILTER (
                    WHERE categorie_attrition = 'Arrêt volontaire'
                ) AS nb_arret_vol,
                COUNT(*) FILTER (
                    WHERE categorie_attrition = 'Décès'
                ) AS nb_deces
            FROM attrition
            WHERE categorie_attrition IS NOT NULL
        ),
        -- A risque fin de mois
        risque AS (
            SELECT COUNT(*) AS nb_a_risque
            FROM a_risque_fin_mois
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

            -- Attrition
            attr.nb_attrition,
            attr.nb_pdv,
            attr.nb_transfert,
            attr.nb_arret_vol,
            attr.nb_deces,

            -- A risque fin de mois
            risque.nb_a_risque

        FROM nb_actifs na, cv_actifs ca, cd4_actifs cd,
             statut_cv_actifs sc, nouveaux_mois nm,
             rdv_manques rm, attr, risque
    """)

    log.info(f"  ✅ kpis_file_active créée")


# =============================================================
# VUE : attrition
# =============================================================
def creer_vue_attrition(conn) -> None:
    """
    Attrition = Perdus de vue + Transferts + Arrêts volontaires + Décès

    Catégorisation TransfCentre (Transf = -1) :
      - "ARRET VOLONTAIRE" / "REFUS" / contient "refuse" -> Arrêt volontaire
      - "INJOIGNABLE"                                     -> PDV
      - autre valeur (vrai nom de centre)                 -> Transfert réel

    DECES = -1 -> Décédé
    (Note : 1 seul DECES=1 isolé daté 2015, traité comme cas marginal,
     non inclus dans la catégorie Décès car valeur non standard)
    """
    conn.execute("DROP VIEW IF EXISTS attrition")
    conn.execute("""
        CREATE VIEW attrition AS
        WITH
        base AS (
            SELECT
                p.NumInc,
                p.NumNational,
                p.Sexe_label,
                p.Age,
                p.Tel,
                p.NomCommunautaire,
                p.DECES,
                p.DecesDate,
                p.Transf,
                p.TransfDate,
                p.TransfCentre,
                fa.DatePDV,
                fa.DernierRegime,
                fa.StatutFile
            FROM TblDossPatient p
            LEFT JOIN file_active fa ON p.NumInc = fa.NumInc
        )
        SELECT
            NumInc, NumNational, Sexe_label, Age, Tel, NomCommunautaire,
            DernierRegime,
            CASE
                WHEN DECES = -1 THEN 'Décès'
                WHEN Transf = -1 AND (
                        UPPER(TRIM(COALESCE(TransfCentre,''))) = 'ARRET VOLONTAIRE'
                     OR UPPER(TRIM(COALESCE(TransfCentre,''))) = 'REFUS'
                     OR UPPER(COALESCE(TransfCentre,'')) LIKE '%REFUSE%'
                ) THEN 'Arrêt volontaire'
                WHEN Transf = -1 AND
                     UPPER(TRIM(COALESCE(TransfCentre,''))) = 'INJOIGNABLE'
                    THEN 'Perdu de vue'
                WHEN Transf = -1 THEN 'Transfert'
                WHEN StatutFile = 'Perdu de vue' THEN 'Perdu de vue'
                ELSE NULL
            END AS categorie_attrition,
            DecesDate,
            TransfDate,
            TransfCentre,
            DatePDV
        FROM base
        WHERE
            DECES = -1
            OR (Transf = -1)
            OR StatutFile = 'Perdu de vue'
    """)

    dist = conn.execute("""
        SELECT categorie_attrition, COUNT(*) AS nb
        FROM attrition
        WHERE categorie_attrition IS NOT NULL
        GROUP BY categorie_attrition
        ORDER BY nb DESC
    """).fetchall()

    log.info(f"  ✅ attrition créée :")
    for cat, nb in dist:
        log.info(f"     {cat:<20} : {nb:,}")


# =============================================================
# VUE : a_risque_fin_mois
# =============================================================
def creer_vue_a_risque_fin_mois(conn) -> None:
    """
    Patients actifs dont DatePDV tombe avant la fin du mois en cours.
    Si rien n'est fait, ils deviendront "perdus de vue" avant le
    prochain rapport mensuel.
    """
    conn.execute("DROP VIEW IF EXISTS a_risque_fin_mois")
    conn.execute("""
        CREATE VIEW a_risque_fin_mois AS
        SELECT
            fa.NumInc,
            fa.NumNational,
            fa.Sexe_label,
            fa.Age,
            p.Tel,
            fa.NomCommunautaire,
            fa.DernierRegime,
            fa.DateProchainRdv,
            fa.DatePDV,
            DATEDIFF('day', CAST(fa.DateProchainRdv AS DATE), CURRENT_DATE)
                AS jours_retard_rdv
        FROM file_active fa
        INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
        WHERE fa.StatutFile = 'Actif'
          AND CAST(fa.DatePDV AS DATE) <=
              LAST_DAY(CURRENT_DATE)
        ORDER BY fa.DatePDV ASC
    """)

    nb = conn.execute("SELECT COUNT(*) FROM a_risque_fin_mois").fetchone()[0]
    log.info(f"  ✅ a_risque_fin_mois : {nb:,} patients à risque ce mois")


# =============================================================
# VUE : patients_non_stables / patients_non_evalues
# =============================================================
def creer_vues_statut_cv_listings(conn) -> None:
    """
    Listings détaillés des patients Non Stables et Non Évalués (NE)
    parmi la file active — avec les 2 dernières valeurs de CV.
    """
    # --- Non Stables ---
    conn.execute("DROP VIEW IF EXISTS patients_non_stables")
    conn.execute("""
        CREATE VIEW patients_non_stables AS
        WITH cv_rank AS (
            SELECT
                Patient AS NumInc,
                CVcopies,
                DatePrelev,
                ROW_NUMBER() OVER (
                    PARTITION BY Patient ORDER BY DatePrelev DESC
                ) AS rang
            FROM TblChargesVirales
            WHERE CVcopies IS NOT NULL
        )
        SELECT
            fa.NumInc, fa.NumNational, fa.Sexe_label, fa.Age,
            p.Tel, fa.NomCommunautaire, fa.DernierRegime,
            c1.CVcopies  AS derniere_cv,
            c1.DatePrelev AS date_derniere_cv,
            c2.CVcopies  AS avant_derniere_cv,
            c2.DatePrelev AS date_avant_derniere_cv
        FROM file_active fa
        INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
        INNER JOIN StatutCV_Patient sc ON fa.NumInc = sc.NumInc
        LEFT JOIN cv_rank c1 ON fa.NumInc = c1.NumInc AND c1.rang = 1
        LEFT JOIN cv_rank c2 ON fa.NumInc = c2.NumInc AND c2.rang = 2
        WHERE fa.StatutFile = 'Actif'
          AND sc.StatutCV = 'Non Stable'
        ORDER BY c1.DatePrelev DESC
    """)

    nb = conn.execute("SELECT COUNT(*) FROM patients_non_stables").fetchone()[0]
    log.info(f"  ✅ patients_non_stables : {nb:,} patients")

    # --- Non Évalués (NE) ---
    conn.execute("DROP VIEW IF EXISTS patients_non_evalues")
    conn.execute("""
        CREATE VIEW patients_non_evalues AS
        WITH cv_count AS (
            SELECT
                Patient AS NumInc,
                COUNT(*) AS nb_cv,
                MAX(DatePrelev) AS derniere_date_cv
            FROM TblChargesVirales
            WHERE CVcopies IS NOT NULL
            GROUP BY Patient
        )
        SELECT
            fa.NumInc, fa.NumNational, fa.Sexe_label, fa.Age,
            p.Tel, fa.NomCommunautaire, fa.DernierRegime,
            COALESCE(cc.nb_cv, 0) AS nb_cv_disponibles,
            cc.derniere_date_cv
        FROM file_active fa
        INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
        INNER JOIN StatutCV_Patient sc ON fa.NumInc = sc.NumInc
        LEFT JOIN cv_count cc ON fa.NumInc = cc.NumInc
        WHERE fa.StatutFile = 'Actif'
          AND sc.StatutCV = 'NE'
        ORDER BY cc.derniere_date_cv DESC NULLS LAST
    """)

    nb2 = conn.execute("SELECT COUNT(*) FROM patients_non_evalues").fetchone()[0]
    log.info(f"  ✅ patients_non_evalues : {nb2:,} patients")


# =============================================================
# VUE : perdus_de_vue_periode (3 et 6 mois)
# =============================================================
def creer_vue_pdv_periode(conn) -> None:
    """
    Perdus de vue récents — avec colonne jours_depuis_pdv
    pour filtrage 3/6 mois côté dashboard.
    Inclut les PDV "INJOIGNABLE" depuis attrition.
    """
    conn.execute("DROP VIEW IF EXISTS pdv_listing")
    conn.execute("""
        CREATE VIEW pdv_listing AS
        SELECT
            NumInc, NumNational, Sexe_label, Age, Tel, NomCommunautaire,
            DernierRegime, DatePDV,
            DATEDIFF('day', CAST(DatePDV AS DATE), CURRENT_DATE)
                AS jours_depuis_pdv
        FROM attrition
        WHERE categorie_attrition = 'Perdu de vue'
          AND DatePDV IS NOT NULL
        ORDER BY jours_depuis_pdv ASC
    """)

    nb = conn.execute("SELECT COUNT(*) FROM pdv_listing").fetchone()[0]
    log.info(f"  ✅ pdv_listing : {nb:,} patients perdus de vue")


# =============================================================
# VUE : vue_prochaine_cv
# =============================================================
def creer_vue_prochaine_cv(conn) -> None:
    """
    Calcule la prochaine date de prélèvement CV par patient actif
    selon la procédure Ko'Khoua :

    STABLE              → dernière CV + 12 mois
    NON STABLE + CV supprimée   → dernière CV + 6 mois
    NON STABLE + CV non supp.   → dernière CV + 4 mois
    NE (0 CV)           → DateMiseTARV + 6 mois
    NE (1 CV supprimée) → date CV + 6 mois
    NE (1 CV non supp.) → date CV + 4 mois
    """
    conn.execute("DROP VIEW IF EXISTS vue_prochaine_cv")
    conn.execute("""
        CREATE VIEW vue_prochaine_cv AS
        WITH
        -- Patients actifs
        actifs AS (
            SELECT
                fa.NumInc, fa.NumNational, fa.Sexe_label, fa.Age,
                p.Tel, fa.NomCommunautaire, fa.DernierRegime,
                fa.DateProchainRdv, fa.DatePDV
            FROM file_active fa
            INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
            WHERE fa.StatutFile = 'Actif'
        ),
        -- Statut CV par patient
        statut AS (
            SELECT NumInc, StatutCV
            FROM StatutCV_Patient
        ),
        -- Dernière et avant-dernière CV par patient
        cv_ranked AS (
            SELECT
                Patient AS NumInc,
                CVcopies,
                DatePrelev,
                CV_Statut,
                ROW_NUMBER() OVER (
                    PARTITION BY Patient ORDER BY DatePrelev DESC
                ) AS rang
            FROM TblChargesVirales
            WHERE CVcopies IS NOT NULL
        ),
        derniere_cv AS (
            SELECT NumInc, CVcopies AS cv1_copies,
                   DatePrelev AS cv1_date, CV_Statut AS cv1_statut
            FROM cv_ranked WHERE rang = 1
        ),
        -- DateMiseTARV pour les NE sans aucune CV
        arv AS (
            SELECT Patient AS NumInc, DateMiseTARV
            FROM TblMiseEnRoute
        )
        SELECT
            a.NumInc, a.NumNational, a.Sexe_label, a.Age,
            a.Tel, a.NomCommunautaire, a.DernierRegime,
            a.DateProchainRdv, a.DatePDV,
            s.StatutCV,
            dc.cv1_copies, dc.cv1_date, dc.cv1_statut,
            arv.DateMiseTARV,

            -- Calcul de la prochaine date CV
            CASE
                -- Stable → +12 mois depuis dernière CV
                WHEN s.StatutCV = 'Stable'
                    THEN CAST(dc.cv1_date AS DATE)
                         + INTERVAL '12 months'

                -- Non Stable, dernière CV supprimée → +6 mois
                WHEN s.StatutCV = 'Non Stable'
                     AND dc.cv1_statut = 'Supprimée'
                    THEN CAST(dc.cv1_date AS DATE)
                         + INTERVAL '6 months'

                -- Non Stable, dernière CV non supprimée → +4 mois
                WHEN s.StatutCV = 'Non Stable'
                     AND dc.cv1_statut = 'Non supprimée'
                    THEN CAST(dc.cv1_date AS DATE)
                         + INTERVAL '4 months'

                -- NE avec 1 CV supprimée → +6 mois
                WHEN s.StatutCV = 'NE'
                     AND dc.cv1_date IS NOT NULL
                     AND dc.cv1_statut = 'Supprimée'
                    THEN CAST(dc.cv1_date AS DATE)
                         + INTERVAL '6 months'

                -- NE avec 1 CV non supprimée → +4 mois
                WHEN s.StatutCV = 'NE'
                     AND dc.cv1_date IS NOT NULL
                     AND dc.cv1_statut = 'Non supprimée'
                    THEN CAST(dc.cv1_date AS DATE)
                         + INTERVAL '4 months'

                -- NE sans aucune CV → DateMiseTARV + 6 mois
                WHEN s.StatutCV = 'NE'
                     AND dc.cv1_date IS NULL
                     AND arv.DateMiseTARV IS NOT NULL
                    THEN CAST(arv.DateMiseTARV AS DATE)
                         + INTERVAL '6 months'

                ELSE NULL
            END AS prochaine_cv_date

        FROM actifs a
        LEFT JOIN statut s ON a.NumInc = s.NumInc
        LEFT JOIN derniere_cv dc ON a.NumInc = dc.NumInc
        LEFT JOIN arv ON a.NumInc = arv.NumInc
    """)

    nb = conn.execute("SELECT COUNT(*) FROM vue_prochaine_cv").fetchone()[0]


# =============================================================
# VUE : cascade_95_95_95
# =============================================================
def creer_vue_cascade(conn) -> None:
    """
    Cascade 95-95-95 ONUSIDA — standard Côte d'Ivoire

    ① 1er 95 : Dépistés positifs connus (TblRegistreCDV)
    ② 2ème 95 : Taux de rétention ARV par année de mise sous ARV
               = patients encore actifs / total mis sous ARV cette année
    ③ 3ème 95 : CV supprimée parmi les actifs évalués
    """
    conn.execute("DROP VIEW IF EXISTS cascade_95_95_95")
    conn.execute("""
        CREATE VIEW cascade_95_95_95 AS
        WITH
        -- ① 1er 95 : Dépistés positifs CDV
        depistage AS (
            SELECT
                COUNT(*) AS nb_tests,
                COUNT(*) FILTER (
                    WHERE Resultat_simple = 'Positif'
                ) AS nb_positifs,
                ROUND(
                    COUNT(*) FILTER (WHERE Resultat_simple = 'Positif')
                    * 100.0 /
                    NULLIF(COUNT(*) FILTER (
                        WHERE Resultat_simple IN ('Positif','Négatif')
                    ), 0), 1
                ) AS taux_positivite
            FROM TblRegistreCDV
        ),
        -- ② 2ème 95 : Rétention ARV (patients mis sous ARV encore actifs)
        retention AS (
            SELECT
                EXTRACT(YEAR FROM CAST(m.DateMiseTARV AS DATE))::INTEGER AS annee,
                COUNT(DISTINCT m.Patient) AS nb_mis_sous_arv,
                COUNT(DISTINCT fa.NumInc) AS nb_encore_actifs,
                ROUND(
                    COUNT(DISTINCT fa.NumInc) * 100.0 /
                    NULLIF(COUNT(DISTINCT m.Patient), 0), 1
                ) AS taux_retention
            FROM TblMiseEnRoute m
            LEFT JOIN file_active fa
                ON m.Patient = fa.NumInc
                AND fa.StatutFile = 'Actif'
            WHERE m.DateMiseTARV IS NOT NULL
            GROUP BY annee
            ORDER BY annee DESC
        ),
        -- ③ 3ème 95 : CV supprimée parmi actifs évalués
        cv AS (
            SELECT
                COUNT(*) FILTER (
                    WHERE cv.CV_Statut = 'Supprimée'
                ) AS nb_supprimee,
                COUNT(*) FILTER (
                    WHERE cv.CV_Statut != 'Non renseigné'
                ) AS nb_evalue,
                ROUND(
                    COUNT(*) FILTER (WHERE cv.CV_Statut = 'Supprimée')
                    * 100.0 /
                    NULLIF(COUNT(*) FILTER (
                        WHERE cv.CV_Statut != 'Non renseigné'
                    ), 0), 1
                ) AS pct_cv_supprimee
            FROM TblChargesVirales cv
            INNER JOIN file_active fa ON cv.Patient = fa.NumInc
            WHERE fa.StatutFile = 'Actif'
              AND cv.CV_Derniere = TRUE
        )
        SELECT
            d.nb_tests,
            d.nb_positifs,
            d.taux_positivite,
            cv.nb_supprimee,
            cv.nb_evalue,
            cv.pct_cv_supprimee,
            95.0 AS objectif_pct
        FROM depistage d, cv
    """)

    # Vue séparée pour la rétention par année
    conn.execute("DROP VIEW IF EXISTS vue_retention_arv")
    conn.execute("""
        CREATE VIEW vue_retention_arv AS
        SELECT
            EXTRACT(YEAR FROM CAST(m.DateMiseTARV AS DATE))::INTEGER AS annee,
            COUNT(DISTINCT m.Patient)  AS nb_mis_sous_arv,
            COUNT(DISTINCT fa.NumInc)  AS nb_encore_actifs,
            ROUND(
                COUNT(DISTINCT fa.NumInc) * 100.0 /
                NULLIF(COUNT(DISTINCT m.Patient), 0), 1
            ) AS taux_retention
        FROM TblMiseEnRoute m
        LEFT JOIN file_active fa
            ON m.Patient = fa.NumInc
            AND fa.StatutFile = 'Actif'
        WHERE m.DateMiseTARV IS NOT NULL
        GROUP BY annee
        ORDER BY annee DESC
    """)
    log.info(f"  ✅ cascade_95_95_95 créée (nouvelle logique)")
    log.info(f"  ✅ vue_retention_arv créée")


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
            log.info(f"\n  ── ATTRITION ──────────────────")
            log.info(f"  Attrition totale       : {kpi[13]:,}")
            log.info(f"    Perdus de vue        : {kpi[14]:,}")
            log.info(f"    Transferts           : {kpi[15]:,}")
            log.info(f"    Arrets volontaires   : {kpi[16]:,}")
            log.info(f"    Deces                : {kpi[17]:,}")
            log.info(f"\n  À risque fin de mois   : {kpi[18]:,}")
    except Exception as e:
        log.warning(f"  ⚠️  KPIs : {e}")

    # Cascade 95-95-95
    log.info("\n  ── CASCADE 95-95-95 ───────────────────────")
    try:
        c = conn.execute("SELECT * FROM cascade_95_95_95").fetchone()
        if c:
            log.info(f"  ① Tests CDV            : {c[0]:,} | Positifs : {c[1]:,} ({c[2]}%)")
            log.info(f"  ③ CV supprimée         : {c[3]:,} / {c[4]:,} ({c[5]}%) | objectif 95%")

        # Rétention ARV — 3 dernières années
        log.info("\n  ── RÉTENTION ARV ──────────────────────────")
        retention = conn.execute("""
            SELECT annee, nb_mis_sous_arv, nb_encore_actifs, taux_retention
            FROM vue_retention_arv
            LIMIT 5
        """).fetchall()
        for r in retention:
            log.info(f"  {r[0]} : {r[1]:,} mis sous ARV → {r[2]:,} encore actifs ({r[3]}%)")
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
    creer_vue_attrition(conn)
    creer_vue_a_risque_fin_mois(conn)
    creer_vues_statut_cv_listings(conn)
    creer_vue_pdv_periode(conn)
    creer_vue_kpis(conn)
    creer_vue_cascade(conn)
    creer_vue_prochaine_cv(conn)

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
