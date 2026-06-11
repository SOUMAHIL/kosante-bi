# =============================================================
# KoSanté BI — Configuration centrale
# =============================================================
# Ce fichier est l'unique endroit où changer les chemins
# lors d'une installation sur un autre PC.
# =============================================================

from pathlib import Path

# Racine du projet — fonctionne sur n'importe quel PC

BASE_DIR = Path(__file__).parent

# CHEMINS DES DONNÉES
# ============================================================
DATA_DIR        = BASE_DIR / "data"
RAW_DIR         = DATA_DIR / "raw"        # CSV bruts extraits
PROCESSED_DIR   = DATA_DIR / "processed"  # CSV nettoyés
 
DB_CLINIQUE     = DATA_DIR / "CMSDSdata.mdb"
DB_PHARMACIE    = DATA_DIR / "SIGDEP_Data_155_rc3_10102013.mdb"
DUCKDB_PATH     = DATA_DIR / "kosante.duckdb"
# Dans config.py
SIGDEP_PASSWORD = "mt123698745rt"

# TABLES À EXTRAIRE
# ============================================================
TABLES_CLINIQUE = [
    "TblChargesVirales",
    "TblDossExamensBio",
    "TblDossPatient",
    "TblDossSuiviPatient",
    "TblMiseEnRoute",
    "TblRegistreCDV",
]
 
TABLES_PHARMACIE = [
    "TblRegime",
]

# ============================================================
# CLÉS DE JOINTURE (validées avec les données réelles)
# ============================================================
# Jointures internes clinique : TblDossPatient.NumInc ↔ Patient
# Jointure inter-bases        : TblDossPatient.NumNational ↔ TblRegime.NumPatient
 
JOIN_KEY_CLINIQUE  = "NumInc"
JOIN_KEY_NATIONAL  = "NumNational"
JOIN_KEY_PHARMACIE = "NumPatient"
 
# ============================================================
# PARAMÈTRES MÉTIER
# ============================================================

# --- CHARGE VIRALE (CVcopies en copies/mL) ---
# CV SUPPRIMÉE    : CVcopies <= 1000  → patient sous contrôle virologique
# CV NON SUPPRIMÉE: CVcopies >  1000  → échec virologique, action requise
CV_SUPPRIMEE_SEUIL = 1000
 
# --- PERDUS DE VUE ---
# Un patient est considéré "perdu de vue" s'il a raté
# son rendez-vous de 28 jours ou plus après la date prévue.
PERDU_DE_VUE_JOURS = 28
 
# --- CD4 (cellules/mm³) ---
# Seuil d'alerte immunologique — à confirmer avec l'équipe médicale Ko'Khoua
# Valeur par défaut OMS : CD4 < 200 = immunodépression sévère
CD4_BAS_SEUIL = 200      # ← À valider avec le médecin référent
 
# ============================================================
# CRÉATION DES DOSSIERS SI INEXISTANTS
# ============================================================
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)