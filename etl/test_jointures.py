# =============================================================
# KoSanté BI — test_jointures.py
# Test de cohérence des clés de jointure
# =============================================================
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import RAW_DIR

dp  = pd.read_csv(RAW_DIR / "TblDossPatient.csv",    low_memory=False)
mer = pd.read_csv(RAW_DIR / "TblMiseEnRoute.csv",    low_memory=False)
bio = pd.read_csv(RAW_DIR / "TblDossExamensBio.csv", low_memory=False)
cv  = pd.read_csv(RAW_DIR / "TblChargesVirales.csv", low_memory=False)

print("=" * 50)
print("  TYPES DES COLONNES CLÉS")
print("=" * 50)
print(f"TblDossPatient.NumInc      : {dp['NumInc'].dtype} | ex: {dp['NumInc'].dropna().iloc[0]}")
print(f"TblMiseEnRoute.Patient     : {mer['Patient'].dtype} | ex: {mer['Patient'].dropna().iloc[0]}")
print(f"TblDossExamensBio.Patient  : {bio['Patient'].dtype} | ex: {bio['Patient'].dropna().iloc[0]}")
print(f"TblChargesVirales.Patient  : {cv['Patient'].dtype}  | ex: {cv['Patient'].dropna().iloc[0]}")

print()
print("=" * 50)
print("  TEST JOINTURES (forçage int)")
print("=" * 50)
ids_patient = set(dp["NumInc"].dropna().astype(int))
ids_mer     = set(mer["Patient"].dropna().astype(int))
ids_bio     = set(bio["Patient"].dropna().astype(int))
ids_cv      = set(cv["Patient"].dropna().astype(int))

match_mer = len(ids_mer & ids_patient)
match_bio = len(ids_bio & ids_patient)
match_cv  = len(ids_cv  & ids_patient)

print(f"MiseEnRoute  match : {match_mer:,} / {len(ids_mer):,}  ({match_mer/len(ids_mer)*100:.1f}%)")
print(f"ExamensBio   match : {match_bio:,} / {len(ids_bio):,}  ({match_bio/len(ids_bio)*100:.1f}%)")
print(f"ChargesViral match : {match_cv:,}  / {len(ids_cv):,}   ({match_cv/len(ids_cv)*100:.1f}%)")
print("=" * 50)