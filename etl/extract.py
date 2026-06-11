# =============================================================
# KoSanté BI — extract.py
# =============================================================
# RÔLE : Lire les 7 tables depuis les 2 bases Access (.mdb)
#        via pyodbc et les exporter en CSV bruts dans data/raw/
#
# SOURCES :
#   - CMSDSdata.mdb       → 6 tables cliniques (sans mot de passe)
#   - SIGDEP_Data_...mdb  → 1 table pharmacie  (avec mot de passe)
#
# USAGE :
#   python etl/extract.py
# =============================================================

import pandas as pd
import pyodbc
from pathlib import Path
import sys
import logging
from datetime import datetime

# Désactive le pooling ODBC — évite le crash Windows à la fermeture
pyodbc.pooling = False
import pyodbc
from pathlib import Path
import sys
import logging
from datetime import datetime

# --- Ajout du dossier racine au path — DOIT être avant les imports config ---
sys.path.append(str(Path(__file__).parent.parent))

from config import (
    DB_CLINIQUE, DB_PHARMACIE,
    TABLES_CLINIQUE, TABLES_PHARMACIE,
    RAW_DIR, SIGDEP_PASSWORD
)

# =============================================================
# CONFIGURATION DU LOGGING
# =============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


# =============================================================
# FONCTION : Connexion à une base Access via pyodbc
# =============================================================
def connecter_access(chemin_mdb: Path, mot_de_passe: str = None) -> pyodbc.Connection:
    """
    Établit une connexion ODBC à un fichier Access .mdb

    Args:
        chemin_mdb   : Chemin complet vers le fichier .mdb
        mot_de_passe : Mot de passe si la base est protégée (None sinon)

    Returns:
        Connexion pyodbc active
    """
    # Base sans mot de passe
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={chemin_mdb};"
    )

    # Ajout du mot de passe uniquement si fourni
    if mot_de_passe:
        conn_str += f"PWD={mot_de_passe};"

    return pyodbc.connect(conn_str)


# =============================================================
# FONCTION : Extraire une table Access → DataFrame
# =============================================================
def extraire_table(conn: pyodbc.Connection, nom_table: str) -> pd.DataFrame:
    """
    Lit une table complète depuis une connexion Access
    et retourne un DataFrame pandas.

    Args:
        conn      : Connexion pyodbc active
        nom_table : Nom exact de la table dans Access

    Returns:
        DataFrame avec toutes les colonnes et lignes
        DataFrame vide si erreur
    """
    try:
        df = pd.read_sql(f"SELECT * FROM [{nom_table}]", conn)
        log.info(
            f"  ✅ {nom_table:<30} "
            f"→ {len(df):>6} lignes · {len(df.columns)} colonnes"
        )
        return df

    except Exception as e:
        log.error(f"  ❌ {nom_table:<30} → ERREUR : {e}")
        return pd.DataFrame()


# =============================================================
# FONCTION : Exporter un DataFrame → CSV dans data/raw/
# =============================================================
def exporter_csv(df: pd.DataFrame, nom_table: str) -> Path:
    """
    Exporte un DataFrame en CSV dans data/raw/
    Encodage utf-8-sig pour compatibilité Excel (accents OK)
    """
    chemin = RAW_DIR / f"{nom_table}.csv"

    if df.empty:
        log.warning(f"  ⚠️  {nom_table} est vide — CSV non créé")
        return chemin

    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    log.info(f"  💾 CSV → {chemin.name}")
    return chemin


# =============================================================
# FONCTION PRINCIPALE : Extraction complète
# =============================================================
def extraire_toutes_les_tables() -> dict:
    """
    Orchestre l'extraction complète des 2 bases Access.
    - CMSDSdata.mdb  : sans mot de passe
    - SIGDEP.mdb     : avec mot de passe (SIGDEP_PASSWORD)

    Returns:
        Dictionnaire {nom_table: DataFrame}
    """
    resultats = {}
    debut = datetime.now()

    log.info("=" * 55)
    log.info("  KoSanté BI — EXTRACTION ACCESS → CSV")
    log.info("=" * 55)

    # ----------------------------------------------------------
    # PARTIE 1 : Base clinique — CMSDSdata.mdb (sans mot de passe)
    # ----------------------------------------------------------
    log.info(f"\n📂 Base CLINIQUE : {DB_CLINIQUE.name}")

    if not DB_CLINIQUE.exists():
        log.error(f"❌ Fichier introuvable : {DB_CLINIQUE}")
        sys.exit(1)

    try:
        # Pas de mot de passe pour la base clinique
        conn_clinique = connecter_access(DB_CLINIQUE)
        log.info("   Connexion ODBC établie ✅")

        for nom_table in TABLES_CLINIQUE:
            df = extraire_table(conn_clinique, nom_table)
            exporter_csv(df, nom_table)
            resultats[nom_table] = df

        conn_clinique.close()

    except pyodbc.Error as e:
        log.error(f"❌ Erreur connexion CMSDSdata.mdb : {e}")
        sys.exit(1)

    # ----------------------------------------------------------
    # PARTIE 2 : Base pharmacie — SIGDEP.mdb (avec mot de passe)
    # ----------------------------------------------------------
    log.info(f"\n📂 Base PHARMACIE : {DB_PHARMACIE.name}")

    if not DB_PHARMACIE.exists():
        log.error(f"❌ Fichier introuvable : {DB_PHARMACIE}")
        sys.exit(1)

    try:
        # Mot de passe requis pour SIGDEP
        conn_pharmacie = connecter_access(DB_PHARMACIE, mot_de_passe=SIGDEP_PASSWORD)
        log.info("   Connexion ODBC établie ✅")

        for nom_table in TABLES_PHARMACIE:
            df = extraire_table(conn_pharmacie, nom_table)
            exporter_csv(df, nom_table)
            resultats[nom_table] = df

        conn_pharmacie.close()

    except pyodbc.Error as e:
        log.error(f"❌ Erreur connexion SIGDEP.mdb : {e}")
        log.error("   Vérifiez le mot de passe SIGDEP_PASSWORD dans config.py")
        sys.exit(1)

    # ----------------------------------------------------------
    # RÉSUMÉ FINAL
    # ----------------------------------------------------------
    duree = (datetime.now() - debut).seconds
    tables_ok    = sum(1 for df in resultats.values() if not df.empty)
    tables_ko    = sum(1 for df in resultats.values() if df.empty)
    total_lignes = sum(len(df) for df in resultats.values())

    log.info("\n" + "=" * 55)
    log.info("  RÉSUMÉ EXTRACTION")
    log.info("=" * 55)
    log.info(f"  Tables extraites  : {tables_ok} / {len(resultats)}")
    log.info(f"  Tables en erreur  : {tables_ko}")
    log.info(f"  Total lignes      : {total_lignes:,}")
    log.info(f"  Durée             : {duree}s")
    log.info(f"  CSV sauvegardés   : {RAW_DIR}")
    log.info("=" * 55)

    if tables_ko > 0:
        log.warning(f"⚠️  {tables_ko} table(s) en erreur")
    else:
        log.info("✅ Extraction complète sans erreur !")

    return resultats


# =============================================================
# POINT D'ENTRÉE
# =============================================================
if __name__ == "__main__":
    try:
        extraire_toutes_les_tables()
    finally:
        # Libération propre du driver ODBC Access
        # Évite le crash Windows "Python a cessé de fonctionner"
        # causé par le driver 32bits qui plante en libérant la mémoire
        pyodbc.pooling = False