# =============================================================
# KoSanté BI — export_powerbi.py
# =============================================================
# RÔLE : Exporte les vues DuckDB en CSV pour Power BI
#        Les CSV contiennent déjà les vrais chiffres Ko'Khoua
#        calculés par load.py (file active, attrition, etc.)
#
# USAGE :
#   python etl/export_powerbi.py
# =============================================================

import duckdb
import pandas as pd
from pathlib import Path
import sys
import logging

sys.path.append(str(Path(__file__).parent.parent))
from config import DUCKDB_PATH, PROCESSED_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def exporter_pour_powerbi():
    log.info("=" * 50)
    log.info("  KoSanté BI — Export CSV pour Power BI")
    log.info("=" * 50)

    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    exports = {
        # KPIs agrégés — 1 seule ligne avec tous les chiffres
        "pbi_kpis": "SELECT * FROM kpis_file_active",

        # File active — patients actifs avec leurs infos
        "pbi_file_active": """
            SELECT
                NumInc, NumNational, Sexe_label, Age,
                NomCommunautaire, TypePatient, DernierRegime,
                DateProchainRdv, DatePDV, StatutFile
            FROM file_active
        """,

        # Attrition — catégorisée
        "pbi_attrition": """
            SELECT
                NumInc, NumNational, Sexe_label, Age,
                NomCommunautaire, DernierRegime,
                categorie_attrition, TransfDate, DecesDate, DatePDV
            FROM attrition
            WHERE categorie_attrition IS NOT NULL
        """,

        # Rétention ARV par cohorte annuelle
        "pbi_retention_arv": "SELECT * FROM vue_retention_arv",

        # Cascade 95-95-95
        "pbi_cascade": "SELECT * FROM cascade_95_95_95",

        # Statut CV avec file active
        "pbi_statut_cv": """
            SELECT sc.NumInc, sc.StatutCV, fa.NomCommunautaire
            FROM StatutCV_Patient sc
            INNER JOIN file_active fa ON sc.NumInc = fa.NumInc
            WHERE fa.StatutFile = 'Actif'
        """,

        # Dépistage CDV par mois
        "pbi_depistage": """
            SELECT
                strftime(CAST(DateVisite AS DATE), '%Y-%m') AS mois,
                COUNT(*) AS nb_tests,
                COUNT(*) FILTER (WHERE Resultat_simple = 'Positif') AS nb_positifs,
                COUNT(*) FILTER (WHERE Resultat_simple = 'Négatif') AS nb_negatifs
            FROM TblRegistreCDV
            WHERE DateVisite IS NOT NULL
            GROUP BY mois
            ORDER BY mois
        """,
    }

    for nom, sql in exports.items():
        try:
            df = conn.execute(sql).df()
            chemin = PROCESSED_DIR / f"{nom}.csv"
            df.to_csv(chemin, index=False, encoding='utf-8-sig')
            log.info(f"  ✅ {nom}.csv — {len(df):,} lignes")
        except Exception as e:
            log.error(f"  ❌ {nom} : {e}")

    conn.close()
    log.info("=" * 50)
    log.info("✅ Export terminé → data/processed/pbi_*.csv")
    log.info("   Importe ces fichiers dans Power BI !")
    log.info("=" * 50)


if __name__ == "__main__":
    exporter_pour_powerbi()