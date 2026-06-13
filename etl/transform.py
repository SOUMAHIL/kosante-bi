# =============================================================
# KoSanté BI — transform.py
# =============================================================
# RÔLE : Nettoyer, standardiser et enrichir les 7 tables CSV
#        extraites depuis les bases Access
#
# ENTRÉE  : data/raw/*.csv    (données brutes)
# SORTIE  : data/processed/*.csv (données propres et enrichies)
#
# TRANSFORMATIONS :
#   1. Standardisation des types (dates, entiers, texte)
#   2. Nettoyage des valeurs aberrantes
#   3. Calcul des colonnes dérivées métier Ko'Khoua
#   4. Gestion du doublon TblMiseEnRoute
#
# USAGE :
#   python etl/transform.py
# =============================================================

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging
from datetime import datetime, date

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    RAW_DIR, PROCESSED_DIR,
    CV_SUPPRIMEE_SEUIL,
    PERDU_DE_VUE_JOURS,
    CD4_BAS_SEUIL,
    JOIN_KEY_CLINIQUE
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

DATE_AUJOURDHUI = pd.Timestamp(date.today())


# =============================================================
# UTILITAIRES
# =============================================================

def lire_csv(nom_table: str) -> pd.DataFrame:
    """Lit un CSV depuis data/raw/"""
    chemin = RAW_DIR / f"{nom_table}.csv"
    df = pd.read_csv(chemin, low_memory=False)
    log.info(f"  📂 {nom_table} chargé — {len(df):,} lignes")
    return df


def sauvegarder_csv(df: pd.DataFrame, nom_table: str) -> None:
    """Sauvegarde un DataFrame dans data/processed/"""
    chemin = PROCESSED_DIR / f"{nom_table}.csv"
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    log.info(f"  💾 {nom_table} sauvegardé — {len(df):,} lignes · {len(df.columns)} colonnes")


def parser_dates(df: pd.DataFrame, colonnes: list) -> pd.DataFrame:
    """
    Convertit les colonnes en datetime.
    Les valeurs non parsables deviennent NaT.
    """
    for col in colonnes:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def nettoyer_dates_naissance(df: pd.DataFrame, col: str = "DateNaiss") -> pd.DataFrame:
    """
    Filtre les dates de naissance aberrantes :
    - Avant 1920 → NaT (erreur de saisie)
    - Dans le futur → NaT (erreur de saisie)
    """
    if col not in df.columns:
        return df

    avant = df[col].notna().sum()
    df.loc[df[col] < pd.Timestamp("1920-01-01"), col] = pd.NaT
    df.loc[df[col] > DATE_AUJOURDHUI, col] = pd.NaT
    apres = df[col].notna().sum()

    nb_filtrees = avant - apres
    if nb_filtrees > 0:
        log.warning(f"  ⚠️  {nb_filtrees} dates de naissance aberrantes → NaT")
    return df


def calculer_age(df: pd.DataFrame, col_naissance: str = "DateNaiss") -> pd.DataFrame:
    """Calcule l'âge en années depuis DateNaiss"""
    if col_naissance not in df.columns:
        return df
    df["Age"] = (
        (DATE_AUJOURDHUI - df[col_naissance])
        .dt.days
        .div(365.25)
        .round(0)
        .astype("Int64")  # Int64 supporte les NaN
    )
    return df




# =============================================================
# UTILITAIRE : Normalisation NumNational
# =============================================================
def normaliser_num_national(num) -> str:
    """
    Normalise le NumNational au format 4 chiffres.
    Gère le changement de nomenclature 2026 :
      00132/01/26/00013 -> 0132/01/26/00013
      0132/01/26/00013  -> 0132/01/26/00013 (inchangé)
    """
    if pd.isna(num):
        return None
    num = str(num).strip()
    parties = num.split("/")
    if len(parties) >= 1 and len(parties[0]) == 5 and parties[0].startswith("0"):
        parties[0] = parties[0][1:]
    return "/".join(parties)


# =============================================================
# UTILITAIRE : Statut CV (Stable / Non Stable / NE)
# =============================================================
def calculer_statut_cv(df_cv: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule le statut CV par patient :
      STABLE     -> 2 dernières CV consécutives supprimées (≤ 1000)
      NON STABLE -> 2 dernières CV consécutives non supprimées (> 1000)
      NE         -> 0 ou 1 seule CV disponible (Non Evalué)
    """
    df = df_cv[["Patient", "DatePrelev", "CVcopies"]].copy()
    df = df.dropna(subset=["CVcopies"])
    df = df.sort_values(["Patient", "DatePrelev"], ascending=[True, False])

    resultats = []
    for patient, groupe in df.groupby("Patient"):
        nb_cv = len(groupe)
        if nb_cv < 2:
            statut = "NE"
        else:
            deux_dernieres = groupe.head(2)["CVcopies"].values
            cv1, cv2 = deux_dernieres[0], deux_dernieres[1]
            if cv1 <= 1000 and cv2 <= 1000:
                statut = "Stable"
            elif cv1 > 1000 and cv2 > 1000:
                statut = "Non Stable"
            else:
                statut = "NE"
        resultats.append({"NumInc": int(patient), "StatutCV": statut})

    return pd.DataFrame(resultats)


# =============================================================
# UTILITAIRE : Type patient (Nouveau / Transfert In)
# =============================================================
def calculer_type_patient(num_national) -> str:
    """
    Détermine le type de patient selon NumNational :
      Nouveau Ko'Khoua -> commence par 0132/01/
      Transfert In     -> autre préfixe
    """
    if pd.isna(num_national):
        return "Inconnu"
    if str(num_national).startswith("0132/01/"):
        return "Nouveau Ko'Khoua"
    return "Transfert In"



# =============================================================
# TRANSFORMATION 1 — TblDossPatient
# =============================================================
def transformer_doss_patient() -> pd.DataFrame:
    """
    Transformations sur TblDossPatient :
    - Standardisation types
    - Nettoyage dates aberrantes
    - Calcul Age
    - Colonne Nom Communautaire (logique Ko'Khoua par période DateAdmi)
    - Colonne StatutPatient (Actif / Décédé / Transféré / Perdu)
    """
    log.info("\n── TblDossPatient ──────────────────────────────")
    df = lire_csv("TblDossPatient")

    # --- Types entiers ---
    df["NumInc"] = pd.to_numeric(df["NumInc"], errors="coerce").astype("Int64")

    # --- Dates ---
    cols_dates = ["DateAdmi", "DateNaiss", "DatePremiereConsultation",
                  "DateInclusion", "DecesDate", "TransfDate"]
    df = parser_dates(df, cols_dates)
    df = nettoyer_dates_naissance(df)

    # --- Sexe lisible ---
    # 1 = Masculin, 2 = Féminin (convention Access Ko'Khoua)
    if "Sexe" in df.columns:
        df["Sexe_label"] = df["Sexe"].map({1: "M", 2: "F"}).fillna("Inconnu")

    # --- Age ---
    df = calculer_age(df)

    # --- Nom Communautaire (logique métier Ko'Khoua) ---
    # Chaque période correspond à un agent communautaire en poste
    def assigner_communautaire(date_admi):
        if pd.isnull(date_admi):
            return "Inconnu"
        if pd.Timestamp("1992-01-01") <= date_admi <= pd.Timestamp("2006-08-31"):
            return "Madame AKRE"
        elif pd.Timestamp("2006-09-01") <= date_admi <= pd.Timestamp("2009-07-31"):
            return "Madame YAPI"
        elif pd.Timestamp("2009-08-01") <= date_admi <= pd.Timestamp("2011-12-31"):
            return "Madame LINDA"
        elif pd.Timestamp("2012-01-01") <= date_admi <= pd.Timestamp("2014-12-31"):
            return "Madame LEONCE"
        elif pd.Timestamp("2015-01-01") <= date_admi <= pd.Timestamp("2018-12-31"):
            return "Monsieur ISMO"
        elif date_admi >= pd.Timestamp("2019-01-01"):
            return "Monsieur Clavaire"
        return "Inconnu"

    df["NomCommunautaire"] = df["DateAdmi"].apply(assigner_communautaire)
    log.info(f"  ✅ NomCommunautaire calculé")

    # --- Statut Patient ---
    # Priorité : Décédé > Transféré > Actif
    def statut_patient(row):
        if pd.notna(row.get("DecesDate")) or row.get("DECES") == 1:
            return "Décédé"
        if pd.notna(row.get("TransfDate")) or row.get("Transf") == 1:
            return "Transféré"
        return "Actif"

    df["StatutPatient"] = df.apply(statut_patient, axis=1)
    log.info(f"  ✅ StatutPatient : {df['StatutPatient'].value_counts().to_dict()}")

    # --- Normalisation NumNational (5 chiffres -> 4 chiffres) ---
    if "NumNational" in df.columns:
        df["NumNational"] = df["NumNational"].apply(normaliser_num_national)
        log.info(f"  ✅ NumNational normalisé (5->4 chiffres)")

    # --- Type patient (Nouveau Ko'Khoua / Transfert In) ---
    df["TypePatient"] = df["NumNational"].apply(calculer_type_patient)
    dist_type = df["TypePatient"].value_counts().to_dict()
    log.info(f"  ✅ TypePatient : {dist_type}")

    sauvegarder_csv(df, "TblDossPatient")
    return df


# =============================================================
# TRANSFORMATION 2 — TblMiseEnRoute
# =============================================================
def transformer_mise_en_route() -> pd.DataFrame:
    """
    Transformations sur TblMiseEnRoute :
    - Standardisation types
    - Gestion du doublon (1 patient avec 2 mises sous ARV)
      → On garde la plus récente (arrêt puis reprise de traitement)
    """
    log.info("\n── TblMiseEnRoute ──────────────────────────────")
    df = lire_csv("TblMiseEnRoute")

    # --- Types ---
    df["Patient"] = pd.to_numeric(df["Patient"], errors="coerce").astype("Int64")
    df = parser_dates(df, ["DateMiseTARV", "RDVDate"])

    # --- Gestion doublon ---
    # 1 seul cas : patient avec 2 mises sous ARV (arrêt/reprise)
    # On garde la ligne avec la DateMiseTARV la plus récente
    nb_avant = len(df)
    df = df.sort_values("DateMiseTARV", ascending=False)
    df = df.drop_duplicates(subset=["Patient"], keep="first")
    nb_apres = len(df)

    if nb_avant > nb_apres:
        log.warning(f"  ⚠️  {nb_avant - nb_apres} doublon(s) supprimé(s) → DateMiseTARV la plus récente conservée")

    log.info(f"  ✅ {len(df):,} patients avec mise sous ARV")
    sauvegarder_csv(df, "TblMiseEnRoute")
    return df


# =============================================================
# TRANSFORMATION 3 — TblChargesVirales
# =============================================================
def transformer_charges_virales() -> pd.DataFrame:
    """
    Transformations sur TblChargesVirales :
    - Standardisation types
    - Colonne CV_Statut : Supprimée (≤1000) / Non supprimée (>1000)
    - Colonne CV_Derniere : flag pour identifier le dernier résultat par patient
    """
    log.info("\n── TblChargesVirales ───────────────────────────")
    df = lire_csv("TblChargesVirales")

    # --- Types ---
    df["Patient"] = pd.to_numeric(df["Patient"], errors="coerce").astype("Int64")
    df["CVcopies"] = pd.to_numeric(df["CVcopies"], errors="coerce")
    df["CVlog"]    = pd.to_numeric(df["CVlog"],    errors="coerce")
    df = parser_dates(df, ["DatePrelev"])

    # --- Statut CV (règle Ko'Khoua) ---
    # CV SUPPRIMÉE    : CVcopies <= 1 000 copies/mL
    # CV NON SUPPRIMÉE: CVcopies >  1 000 copies/mL
    def statut_cv(valeur):
        if pd.isnull(valeur):
            return "Non renseigné"
        return "Supprimée" if valeur <= CV_SUPPRIMEE_SEUIL else "Non supprimée"

    df["CV_Statut"] = df["CVcopies"].apply(statut_cv)

    # --- Flag dernière CV par patient ---
    df_sorted = df.sort_values("DatePrelev", ascending=False)
    df["CV_Derniere"] = ~df_sorted.duplicated(subset=["Patient"], keep="first")

    # --- Stats ---
    derniere_cv = df[df["CV_Derniere"] == True]
    dist = derniere_cv["CV_Statut"].value_counts().to_dict()
    log.info(f"  ✅ CV_Statut (dernière CV/patient) : {dist}")

    # --- Statut CV (Stable / Non Stable / NE) ---
    df_statut_cv = calculer_statut_cv(df)
    dist_statut = df_statut_cv["StatutCV"].value_counts().to_dict()
    log.info(f"  ✅ StatutCV par patient : {dist_statut}")
    sauvegarder_csv(df_statut_cv, "StatutCV_Patient")

    sauvegarder_csv(df, "TblChargesVirales")
    return df


# =============================================================
# TRANSFORMATION 4 — TblDossExamensBio
# =============================================================
def transformer_examens_bio() -> pd.DataFrame:
    """
    Transformations sur TblDossExamensBio :
    - Standardisation types
    - Sélection colonnes utiles (CD4Nb, CD4Pcent)
    - Flag dernier CD4 par patient
    - Alerte CD4 bas (< 200 cellules/mm³)
    """
    log.info("\n── TblDossExamensBio ───────────────────────────")
    df = lire_csv("TblDossExamensBio")

    # --- Types ---
    df["Patient"] = pd.to_numeric(df["Patient"], errors="coerce").astype("Int64")
    df["CD4Nb"]   = pd.to_numeric(df["CD4Nb"],   errors="coerce")
    df["CD4Pcent"]= pd.to_numeric(df["CD4Pcent"],errors="coerce")
    df = parser_dates(df, ["DateExam"])

    # --- Nettoyer dates aberrantes ---
    df.loc[df["DateExam"] < pd.Timestamp("1980-01-01"), "DateExam"] = pd.NaT

    # --- Flag dernier CD4 par patient ---
    df_sorted = df.sort_values("DateExam", ascending=False)
    df["CD4_Dernier"] = ~df_sorted.duplicated(subset=["Patient"], keep="first")

    # --- Alerte CD4 bas ---
    df["CD4_Alerte"] = df["CD4Nb"].apply(
        lambda x: True if pd.notna(x) and x < CD4_BAS_SEUIL else False
    )

    # --- Stats ---
    dernier_cd4 = df[df["CD4_Dernier"] == True]["CD4Nb"].dropna()
    log.info(f"  ✅ CD4 moyen (dernier/patient) : {dernier_cd4.mean():.0f} cellules/mm³")
    log.info(f"  ✅ CD4 < {CD4_BAS_SEUIL} (alerte) : {df['CD4_Alerte'].sum():,} bilans")

    sauvegarder_csv(df, "TblDossExamensBio")
    return df


# =============================================================
# TRANSFORMATION 5 — TblRegime
# =============================================================
def transformer_regime() -> pd.DataFrame:
    """
    Transformations sur TblRegime :
    - Standardisation types
    - Calcul DateProchainRdv = DateRegime + JOURS
    - Calcul DatePDV = DateProchainRdv + 28 jours (règle Ko'Khoua)
    - Statut Actif pharmacie
    """
    log.info("\n── TblRegime ───────────────────────────────────")
    df = lire_csv("TblRegime")

    # --- Types ---
    df["NumPatient"] = df["NumPatient"].astype(str).str.strip()
    df["JOURS"]      = pd.to_numeric(df["JOURS"], errors="coerce")
    df = parser_dates(df, ["DateRegime"])

    # --- Supprimer lignes sans DateRegime ---
    nb_avant = len(df)
    df = df.dropna(subset=["DateRegime"])
    if len(df) < nb_avant:
        log.warning(f"  ⚠️  {nb_avant - len(df)} lignes sans DateRegime supprimées")

    # --- DateProchainRdv et DatePDV ---
    df["DateProchainRdv"] = df["DateRegime"] + pd.to_timedelta(df["JOURS"], unit="D")
    df["DatePDV"]         = df["DateProchainRdv"] + pd.Timedelta(days=PERDU_DE_VUE_JOURS)

    # --- Statut Actif pharmacie ---
    # Actif = DatePDV >= aujourd'hui (pas encore perdu de vue)
    df["Actif_Pharmacie"] = df["DatePDV"].apply(
        lambda x: True if pd.notna(x) and x >= DATE_AUJOURDHUI else False
    )

    # --- Dernière dispensation par patient ---
    df_sorted = df.sort_values("DateRegime", ascending=False)
    df["Derniere_Dispensation"] = ~df_sorted.duplicated(subset=["NumPatient"], keep="first")

    nb_actifs = df[df["Derniere_Dispensation"] == True]["Actif_Pharmacie"].sum()
    log.info(f"  ✅ Patients actifs pharmacie : {nb_actifs:,} / {df['NumPatient'].nunique():,}")

    sauvegarder_csv(df, "TblRegime")
    return df


# =============================================================
# TRANSFORMATION 6 — TblDossSuiviPatient
# =============================================================
def transformer_suivi_patient() -> pd.DataFrame:
    """
    Transformations sur TblDossSuiviPatient :
    - Standardisation types
    - Dernière visite par patient
    """
    log.info("\n── TblDossSuiviPatient ─────────────────────────")
    df = lire_csv("TblDossSuiviPatient")

    # --- Types ---
    df["Patient"] = pd.to_numeric(df["Patient"], errors="coerce").astype("Int64")

    # Détecter la colonne date de visite
    col_date = None
    for candidat in ["VisiteDate", "DateVisite", "DateConsult", "Date"]:
        if candidat in df.columns:
            col_date = candidat
            break

    if col_date:
        df = parser_dates(df, [col_date])
        df["Derniere_Visite"] = ~df.sort_values(
            col_date, ascending=False
        ).duplicated(subset=["Patient"], keep="first")
        log.info(f"  ✅ Colonne date détectée : {col_date}")
    else:
        log.warning("  ⚠️  Aucune colonne date de visite trouvée")

    log.info(f"  ✅ {df['Patient'].nunique():,} patients uniques en suivi")
    sauvegarder_csv(df, "TblDossSuiviPatient")
    return df


# =============================================================
# TRANSFORMATION 7 — TblRegistreCDV
# =============================================================
def transformer_registre_cdv() -> pd.DataFrame:
    """
    Transformations sur TblRegistreCDV :
    - Standardisation types
    - Nettoyage dates aberrantes
    - Résultat lisible (Positif / Négatif / Indéterminé)
    """
    log.info("\n── TblRegistreCDV ──────────────────────────────")
    df = lire_csv("TblRegistreCDV")

    # --- Types ---
    df = parser_dates(df, ["DateVisite", "DateNaiss"])
    df = nettoyer_dates_naissance(df)

    # --- Sexe lisible ---
    if "Sexe" in df.columns:
        df["Sexe_label"] = df["Sexe"].map({1: "M", 2: "F"}).fillna("Inconnu")

    # --- Résultat lisible ---
    # Convention Ko'Khoua à confirmer — valeurs typiques : 1=Positif, 2=Négatif
    if "Resultat" in df.columns:
        df["Resultat_label"] = df["Resultat"].map({
            0: "Négatif",
            1: "Positif — Stade 1",
            2: "Positif — Stade 2",
            3: "Positif — Stade 3",
            4: "Positif — Stade 4",
            5: "Positif — Stade 5"
        }).fillna("Non renseigné")

        # Colonne simplifiée pour les KPIs cascade 95-95-95
        # Positif = stades 1 à 5 / Négatif = 0
        df["Resultat_simple"] = df["Resultat"].apply(
            lambda x: "Positif" if pd.notna(x) and x in [1, 2, 3, 4, 5]
            else ("Négatif" if pd.notna(x) and x == 0 else "Non renseigné")
        )

        dist = df["Resultat_label"].value_counts().to_dict()
        log.info(f"  ✅ Résultats CDV : {dist}")

    sauvegarder_csv(df, "TblRegistreCDV")
    return df


# =============================================================
# FONCTION PRINCIPALE
# =============================================================
def transformer_toutes_les_tables() -> dict:
    """
    Orchestre toutes les transformations dans l'ordre logique :
    1. TblDossPatient    (table centrale)
    2. TblMiseEnRoute    (dépend de Patient)
    3. TblChargesVirales (dépend de Patient)
    4. TblDossExamensBio (dépend de Patient)
    5. TblRegime         (base pharmacie)
    6. TblDossSuiviPatient
    7. TblRegistreCDV    (indépendante)
    """
    debut = datetime.now()

    log.info("=" * 55)
    log.info("  KoSanté BI — TRANSFORMATION DES DONNÉES")
    log.info("=" * 55)

    resultats = {}

    try:
        resultats["TblDossPatient"]      = transformer_doss_patient()
        resultats["TblMiseEnRoute"]      = transformer_mise_en_route()
        resultats["TblChargesVirales"]   = transformer_charges_virales()
        resultats["TblDossExamensBio"]   = transformer_examens_bio()
        resultats["TblRegime"]           = transformer_regime()
        resultats["TblDossSuiviPatient"] = transformer_suivi_patient()
        resultats["TblRegistreCDV"]      = transformer_registre_cdv()

    except Exception as e:
        log.error(f"❌ Erreur durant la transformation : {e}")
        raise

    duree = (datetime.now() - debut).seconds
    total_lignes = sum(len(df) for df in resultats.values())

    log.info("\n" + "=" * 55)
    log.info("  RÉSUMÉ TRANSFORMATION")
    log.info("=" * 55)
    log.info(f"  Tables transformées : {len(resultats)} / 7")
    log.info(f"  Total lignes        : {total_lignes:,}")
    log.info(f"  Durée               : {duree}s")
    log.info(f"  CSV sauvegardés     : {PROCESSED_DIR}")
    log.info("=" * 55)
    log.info("✅ Transformation complète sans erreur !")

    return resultats


# =============================================================
# POINT D'ENTRÉE
# =============================================================
if __name__ == "__main__":
    transformer_toutes_les_tables()