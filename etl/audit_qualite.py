# =============================================================
# KoSanté BI — audit_qualite.py
# =============================================================
# RÔLE : Vérifier la qualité des 7 CSV extraits dans data/raw/
#
# CONTRÔLES EFFECTUÉS :
#   1. Dimensions (lignes, colonnes)
#   2. Valeurs nulles par colonne
#   3. Doublons (règles métier VIH — cf. commentaires)
#   4. Formats des dates
#   5. Cohérence des clés de jointure
#
# USAGE :
#   python etl/audit_qualite.py
# =============================================================

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    RAW_DIR,
    JOIN_KEY_CLINIQUE,
    JOIN_KEY_NATIONAL,
    JOIN_KEY_PHARMACIE
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# =============================================================
# RÈGLES MÉTIER VIH — Doublons attendus ou non
# =============================================================
# True  = une seule ligne par patient OBLIGATOIRE
# False = plusieurs lignes par patient NORMAL (suivi à vie)
REGLES_DOUBLONS = {
    "TblDossPatient":      {"unique": True,  "cle": "NumInc",      "raison": "1 dossier par patient"},
    "TblMiseEnRoute":      {"unique": True,  "cle": "Patient",     "raison": "1 seule mise sous ARV"},
    "TblChargesVirales":   {"unique": False, "cle": "Patient",     "raison": "1 CV par prélèvement — normal"},
    "TblDossExamensBio":   {"unique": False, "cle": "Patient",     "raison": "1 bilan par examen — normal"},
    "TblDossSuiviPatient": {"unique": False, "cle": "Patient",     "raison": "1 ligne par visite — normal"},
    "TblRegistreCDV":      {"unique": False, "cle": "NumeroClient","raison": "1 ligne par dépistage — normal"},
    "TblRegime":           {"unique": False, "cle": "NumPatient",  "raison": "1 dispensation par mois — normal"},
}

# Colonnes dates à vérifier par table
COLONNES_DATES = {
    "TblDossPatient":      ["DateAdmi", "DateNaiss", "DateInclusion", "DecesDate"],
    "TblMiseEnRoute":      ["DateMiseTARV"],
    "TblChargesVirales":   ["DatePrelev"],
    "TblDossExamensBio":   ["DateExam"],
    "TblDossSuiviPatient": ["DateVisite"] if "DateVisite" else [],
    "TblRegistreCDV":      ["DateVisite", "DateNaiss"],
    "TblRegime":           ["DateRegime"],
}


# =============================================================
# FONCTIONS D'AUDIT
# =============================================================

def audit_dimensions(df: pd.DataFrame, nom: str):
    log.info(f"  📐 Dimensions    : {len(df):,} lignes · {len(df.columns)} colonnes")


def audit_nulls(df: pd.DataFrame, nom: str, seuil_alerte: float = 0.3):
    """Signale les colonnes avec plus de 30% de valeurs nulles"""
    nulls = df.isnull().sum()
    nulls_pct = (nulls / len(df)).round(3)
    cols_critiques = nulls_pct[nulls_pct > seuil_alerte]

    if cols_critiques.empty:
        log.info(f"  ✅ Nulls         : Aucune colonne critique (seuil >{seuil_alerte*100:.0f}%)")
    else:
        log.warning(f"  ⚠️  Nulls critiques (>{seuil_alerte*100:.0f}%) :")
        for col, pct in cols_critiques.items():
            log.warning(f"      {col:<35} → {pct*100:.1f}% nuls ({nulls[col]:,} valeurs)")


def audit_doublons(df: pd.DataFrame, nom: str):
    """Vérifie les doublons selon les règles métier VIH"""
    regle = REGLES_DOUBLONS.get(nom)
    if not regle:
        return

    cle = regle["cle"]
    unique_attendu = regle["unique"]
    raison = regle["raison"]

    if cle not in df.columns:
        log.warning(f"  ⚠️  Clé '{cle}' introuvable dans {nom}")
        return

    nb_total     = len(df)
    nb_uniques   = df[cle].nunique()
    nb_doublons  = nb_total - nb_uniques

    if unique_attendu:
        # Table où chaque patient ne doit apparaître qu'une fois
        if nb_doublons == 0:
            log.info(f"  ✅ Doublons      : 0 doublon sur '{cle}' — {raison}")
        else:
            log.error(
                f"  ❌ Doublons      : {nb_doublons:,} doublons sur '{cle}' "
                f"— ANOMALIE ({raison})"
            )
            # Afficher les 5 premiers patients en doublon
            doublons = df[df.duplicated(subset=[cle], keep=False)]
            top5 = doublons[cle].value_counts().head(5)
            log.error(f"      Top 5 doublons : {top5.to_dict()}")
    else:
        # Table multi-lignes — on affiche juste la distribution
        moy_lignes = nb_total / nb_uniques if nb_uniques > 0 else 0
        log.info(
            f"  📊 Multi-lignes  : {nb_uniques:,} patients uniques · "
            f"moy {moy_lignes:.1f} lignes/patient — {raison}"
        )


def audit_dates(df: pd.DataFrame, nom: str):
    """Vérifie le format et la plage des colonnes dates"""
    cols = COLONNES_DATES.get(nom, [])
    cols_presentes = [c for c in cols if c in df.columns]

    if not cols_presentes:
        return

    for col in cols_presentes:
        try:
            dates = pd.to_datetime(df[col], errors="coerce")
            nb_invalides = dates.isnull().sum() - df[col].isnull().sum()
            date_min = dates.min()
            date_max = dates.max()

            if nb_invalides > 0:
                log.warning(
                    f"  ⚠️  Date '{col}' : {nb_invalides} valeurs non parsables"
                )
            else:
                log.info(
                    f"  📅 Date '{col}' : [{date_min.date()} → {date_max.date()}]"
                )

            # Alerte dates aberrantes
            if date_min and date_min.year < 1980:
                log.warning(f"      ⚠️  Dates avant 1980 détectées dans '{col}'")
            if date_max and date_max.year > 2026:
                log.warning(f"      ⚠️  Dates futures détectées dans '{col}'")

        except Exception as e:
            log.warning(f"  ⚠️  Impossible d'analyser '{col}' : {e}")


def audit_jointures():
    """
    Vérifie la cohérence des clés de jointure entre tables :
    - TblDossPatient.NumInc ↔ Patient (tables cliniques)
    - TblDossPatient.NumNational ↔ TblRegime.NumPatient (inter-bases)
    """
    log.info("\n" + "=" * 55)
    log.info("  AUDIT JOINTURES — Cohérence des clés")
    log.info("=" * 55)

    # Chargement tables clés
    try:
        df_patient  = pd.read_csv(RAW_DIR / "TblDossPatient.csv", low_memory=False)
        df_cv       = pd.read_csv(RAW_DIR / "TblChargesVirales.csv", low_memory=False)
        df_bio      = pd.read_csv(RAW_DIR / "TblDossExamensBio.csv", low_memory=False)
        df_mer      = pd.read_csv(RAW_DIR / "TblMiseEnRoute.csv", low_memory=False)
        df_regime   = pd.read_csv(RAW_DIR / "TblRegime.csv", low_memory=False)
    except FileNotFoundError as e:
        log.error(f"❌ Fichier CSV manquant : {e}")
        return

    patients_numinc     = set(df_patient["NumInc"].dropna().astype(str))
    patients_numnational= set(df_patient["NumNational"].dropna().astype(str))

    # Jointure 1 : TblDossPatient.NumInc ↔ TblChargesVirales.Patient
    cv_patients = set(df_cv["Patient"].dropna().astype(str))
    orphelins_cv = cv_patients - patients_numinc
    log.info(f"\n  TblDossPatient.NumInc ↔ TblChargesVirales.Patient")
    log.info(f"  Patients avec CV        : {len(cv_patients):,}")
    log.info(f"  CV sans dossier patient : {len(orphelins_cv):,}" +
             (" ⚠️" if orphelins_cv else " ✅"))

    # Jointure 2 : TblDossPatient.NumInc ↔ TblDossExamensBio.Patient
    bio_patients = set(df_bio["Patient"].dropna().astype(str))
    orphelins_bio = bio_patients - patients_numinc
    log.info(f"\n  TblDossPatient.NumInc ↔ TblDossExamensBio.Patient")
    log.info(f"  Patients avec bilan     : {len(bio_patients):,}")
    log.info(f"  Bilans sans dossier     : {len(orphelins_bio):,}" +
             (" ⚠️" if orphelins_bio else " ✅"))

    # Jointure 3 : TblDossPatient.NumInc ↔ TblMiseEnRoute.Patient
    mer_patients = set(df_mer["Patient"].dropna().astype(str))
    orphelins_mer = mer_patients - patients_numinc
    log.info(f"\n  TblDossPatient.NumInc ↔ TblMiseEnRoute.Patient")
    log.info(f"  Patients mis sous ARV   : {len(mer_patients):,}")
    log.info(f"  ARV sans dossier        : {len(orphelins_mer):,}" +
             (" ⚠️" if orphelins_mer else " ✅"))

    # Jointure 4 : TblDossPatient.NumNational ↔ TblRegime.NumPatient
    regime_patients = set(df_regime["NumPatient"].dropna().astype(str))
    orphelins_regime = regime_patients - patients_numnational
    communs = regime_patients & patients_numnational
    log.info(f"\n  TblDossPatient.NumNational ↔ TblRegime.NumPatient")
    log.info(f"  Patients en pharmacie   : {len(regime_patients):,}")
    log.info(f"  Patients communs (match): {len(communs):,}" +
             (" ✅" if communs else " ❌"))
    log.info(f"  Pharmacie sans dossier  : {len(orphelins_regime):,}" +
             (" ⚠️" if orphelins_regime else " ✅"))


# =============================================================
# AUDIT PRINCIPAL
# =============================================================
def lancer_audit():
    debut = datetime.now()

    log.info("=" * 55)
    log.info("  KoSanté BI — AUDIT QUALITÉ DES DONNÉES")
    log.info("=" * 55)

    for nom_table in REGLES_DOUBLONS.keys():
        chemin_csv = RAW_DIR / f"{nom_table}.csv"

        if not chemin_csv.exists():
            log.warning(f"\n⚠️  {nom_table}.csv introuvable — ignoré")
            continue

        log.info(f"\n{'─'*55}")
        log.info(f"  📋 {nom_table}")
        log.info(f"{'─'*55}")

        df = pd.read_csv(chemin_csv, low_memory=False)

        audit_dimensions(df, nom_table)
        audit_nulls(df, nom_table)
        audit_doublons(df, nom_table)
        audit_dates(df, nom_table)

    # Audit des jointures inter-tables
    audit_jointures()

    duree = (datetime.now() - debut).seconds
    log.info(f"\n{'='*55}")
    log.info(f"  ✅ Audit terminé en {duree}s")
    log.info(f"{'='*55}")


# =============================================================
# POINT D'ENTRÉE
# =============================================================
if __name__ == "__main__":
    lancer_audit()