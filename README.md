# KoSanté BI — Plateforme d'Analyse & Suivi des PVVIH

> **Projet Data Engineering & Business Intelligence**  
> Développé par **Konaté Soumahila** — Data & AI Engineer  
> Formation : Master 2 MBDS — Université Côte d'Azur / ESATIC Abidjan

---

## 📋 Contexte

Une ONG ivoirienne spécialisée dans la prise en charge des **Personnes Vivant avec le VIH/SIDA (PVVIH)** à Abidjan, Côte d'Ivoire, active depuis plus de 30 ans, gère plus de **6 000 dossiers patients** et assure le suivi médical, le traitement ARV et le conseil-dépistage.

### Problème résolu

Les données de suivi étaient dispersées dans **deux bases Access** non connectées, sans tableau de bord centralisé. La direction ne disposait d'aucun indicateur consolidé pour piloter l'activité et produire les rapports bailleurs (PEPFAR, Fonds Mondial).

**KoSanté BI** transforme ces données brutes en une plateforme analytique complète alignée sur le standard **95-95-95 de l'ONUSIDA**.

---

## 🏗️ Architecture

```
CMSDSdata.mdb (Clinique)     SIGDEP.mdb (Pharmacie)
        │                           │
        └──────────┬────────────────┘
                   │
            [ETL Python]
            extract.py → transform.py → load.py
                   │
            [DuckDB — kosante.duckdb]
                   │
            [Streamlit]
            Dashboard quotidien
```

### Stack technologique

| Couche | Technologie |
|--------|-------------|
| Extraction | Python · pyodbc |
| Transformation | Python · Pandas · NumPy |
| Stockage | DuckDB (fichier local) |
| Dashboard | Streamlit · Plotly |

---

## 📊 KPIs — Cascade 95-95-95 ONUSIDA

| # | Indicateur | Source | Règle métier |
|---|-----------|--------|--------------|
| ① | Dépistés positifs connus | TblRegistreCDV | Actes CDV positifs |
| ② | Taux de rétention ARV | TblMiseEnRoute + file_active | Patients encore actifs / mis sous ARV par cohorte |
| ③ | Charge virale supprimée | TblChargesVirales | CVcopies ≤ 1 000 copies/mL parmi actifs évalués |

---

## 🗄️ Sources de données

### Base clinique — CMSDSdata.mdb

| Table | Rôle | Lignes | Type |
|-------|------|--------|------|
| TblDossPatient | Dossier patient (identité, admission) | 6 017 | 1 ligne/patient |
| TblMiseEnRoute | Initiation traitement ARV | 4 994 | 1 ligne/patient |
| TblChargesVirales | Résultats charge virale | 31 989 | Multi-lignes |
| TblDossExamensBio | Bilans biologiques (CD4, NFS) | 86 265 | Multi-lignes |
| TblDossSuiviPatient | Visites de suivi clinique | 103 521 | Multi-lignes |
| TblRegistreCDV | Registre dépistage volontaire | 20 060 | Multi-lignes |

### Base pharmacie — SIGDEP.mdb

| Table | Rôle | Lignes | Type |
|-------|------|--------|------|
| TblRegime | Dispensations ARV mensuelles | 100 360 | Multi-lignes |

**Total extrait : 353 206 lignes**

---

## 🔗 Clés de jointure

```
TblDossPatient.NumInc      ←→  TblMiseEnRoute.Patient      (99.9% match)
TblDossPatient.NumInc      ←→  TblChargesVirales.Patient   (99.9% match)
TblDossPatient.NumInc      ←→  TblDossExamensBio.Patient   (99.9% match)
TblDossPatient.NumInc      ←→  TblDossSuiviPatient.Patient (jointure clinique)
TblDossPatient.NumNational ←→  TblRegime.NumPatient        (92.6% match)
```

> **Note** : `TblRegistreCDV` est une table indépendante (registre anonyme de dépistage).
> Les KPIs de dépistage sont calculés indépendamment — conformément aux pratiques PNLS CI.

---

## 📁 Structure du projet

```
kosante-bi/
├── data/
│   ├── raw/                    ← CSV bruts extraits (gitignore)
│   ├── processed/              ← CSV nettoyés (gitignore)
│   ├── CMSDSdata.mdb           ← Base clinique (gitignore)
│   ├── SIGDEP_Data_...mdb      ← Base pharmacie (gitignore)
│   └── kosante.duckdb          ← Base analytique (gitignore)
├── etl/
│   ├── extract.py              ← Extraction Access → CSV
│   ├── audit_qualite.py        ← Contrôle qualité des données
│   ├── transform.py            ← Nettoyage & transformation
│   └── load.py                 ← Chargement DuckDB + vues analytiques
├── dashboard/
│   ├── app.py                  ← Point d'entrée Streamlit
│   └── views/
│       ├── vue_ensemble.py     ← 01 · Vue d'ensemble
│       ├── depistage.py        ← 02 · Dépistage CDV
│       ├── file_active.py      ← 03 · Fichier actif
│       ├── performances.py     ← 04 · Performances cliniques
│       ├── attrition.py        ← 05 · Attrition
│       └── listing.py          ← 06 · Listing & Export
├── DECISIONS.md                ← Journal des décisions techniques
├── DICTIONNAIRE_DONNEES.md     ← Référentiel tables et KPIs
├── lancer_dashboard.bat        ← Lancement en 1 clic
├── requirements.txt
├── config.py                   ← Configuration centrale
└── README.md
```

---

## 🚀 Installation & Lancement

### Prérequis
- Python 3.10+
- Microsoft Access Database Engine (driver ODBC 32 ou 64 bits)
- Les fichiers `.mdb` dans le dossier `data/`

### Installation

```bash
# 1. Cloner le projet
git clone https://github.com/SOUMAHIL/kosante-bi.git
cd kosante-bi

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer les chemins dans config.py
# (adapter DB_CLINIQUE et DB_PHARMACIE à votre machine)

# 4. Lancer le pipeline ETL complet
python etl/extract.py
python etl/transform.py
python etl/load.py

# 5. Lancer le dashboard
streamlit run dashboard/app.py
```

### Ou en un clic
```
Double-clic sur lancer_dashboard.bat
```

---

## 📈 Phases du projet

| Phase | Description | Statut |
|-------|-------------|--------|
| **Phase 1** | Setup · Extraction Access → CSV · Audit qualité | ✅ Terminée |
| **Phase 2** | Transformation · Nettoyage · Schéma DuckDB | ✅ Terminée |
| **Phase 3** | Dashboard Streamlit · 6 menus · Listings | ✅ Terminée |
| **Phase 4** | Finalisation · Déploiement | 🔄 En cours |

---

## 🔍 Phase 1 — Détail technique

### Extraction (extract.py)

- Connexion via **pyodbc** (driver ODBC Microsoft Access)
- Extraction table par table avec gestion d'erreurs
- Export CSV encodage **UTF-8 BOM** (compatibilité Excel + accents)
- Gestion séparée des mots de passe (SIGDEP protégé)

### Audit qualité (audit_qualite.py)

| Contrôle | Résultat |
|----------|----------|
| Doublons TblDossPatient | ✅ 0 doublon sur NumInc |
| Doublons TblMiseEnRoute | ⚠️ 1 doublon → garder dernière DateMiseTARV |
| Jointures clinique (NumInc) | ✅ 99.9% de match |
| Jointure inter-bases (NumNational) | ✅ 92.6% de match |
| Dates aberrantes | ⚠️ Filtrées en Phase 2 |

---

## 🔄 Phase 2 — Détail technique

### Transformation (transform.py)

| Table | Transformations clés |
|-------|---------------------|
| TblDossPatient | Normalisation NumNational (5→4 chiffres) · TypePatient · NomCommunautaire · Age |
| TblMiseEnRoute | Gestion doublon → DateMiseTARV la plus récente |
| TblChargesVirales | CV_Statut · StatutCV (Stable/Non Stable/NE) |
| TblDossExamensBio | CD4_Dernier · CD4_Alerte (< 200) |
| TblRegime | Normalisation NumPatient · DateProchainRdv · DatePDV · Actif_Pharmacie |
| TblDossSuiviPatient | Détection VisiteDate · Derniere_Visite |
| TblRegistreCDV | Resultat_label (stades 0-5) · Resultat_simple |

### Logique File Active

```
Un patient est ACTIF si :
  ✅ Il a une dispensation ARV dans TblRegime (REGIME IS NOT NULL)
  ✅ DatePDV = DateRegime + JOURS + 28 jours >= aujourd'hui
  ✅ DECES = -1 → exclu (décédé)
  ✅ Transf = -1 → exclu (transféré ou arrêt volontaire)
  ✅ NumInc > 0
```

### Vues analytiques DuckDB

| Vue | Description |
|-----|-------------|
| `file_active` | Patients actifs selon logique métier |
| `patients_rdv_manque` | Retard RDV 1-27 jours (anonymisés) |
| `perdus_de_vue` | ≥ 28 jours sans venir |
| `attrition` | PDV + Transferts + Arrêts volontaires + Décès |
| `a_risque_fin_mois` | Actifs dont DatePDV ≤ fin du mois en cours |
| `patients_non_stables` | 2 CV consécutives > 1 000 copies/mL |
| `patients_non_evalues` | Moins de 2 CV disponibles (NE) |
| `pdv_listing` | PDV récents avec jours_depuis_pdv |
| `kpis_file_active` | Tous les KPIs agrégés |
| `cascade_95_95_95` | Indicateurs ONUSIDA |
| `vue_retention_arv` | Taux de rétention par cohorte annuelle |
| `vue_prochaine_cv` | Prochaine date CV par patient selon protocole |

### Résultats obtenus — Données réelles anonymisées

| Indicateur | Valeur | Objectif |
|-----------|--------|----------|
| File active | 2 448 patients | — |
| CV supprimée | 95.7% (2 330 / 2 435) | 95% ✅ |
| Patients stables | 98.6% | — |
| Patients non stables | 32 | — |
| Non évalués (NE) | 137 | — |
| RDV manqués | 270 patients | — |
| À risque fin de mois | 30 patients | — |
| Attrition totale | 2 385 | — |
| → Perdus de vue | 577 | — |
| → Transferts | 949 | — |
| → Arrêts volontaires | 45 | — |
| → Décès | 814 | — |

---

## 📊 Phase 3 — Dashboard Streamlit

### 6 menus disponibles

| Menu | Contenu |
|------|---------|
| **01 · Vue d'ensemble** | KPIs clés · Cascade 95-95-95 · Attrition · Évolution 3 ans |
| **02 · Dépistage CDV** | Tests · Positifs · Taux positivité · Filtre année · Tranches d'âge |
| **03 · Fichier actif** | Par communautaire · Régimes ARV · PDV fin de mois · RDV manqués |
| **04 · Performances cliniques** | Statut CV · Évolution CV 6 mois · Non Stables · NE |
| **05 · Attrition** | Filtre période · Répartition · Rétention ARV 6 cohortes · PDV listing |
| **06 · Listing** | Export CSV/Excel · 13 listings anonymisés · RDV ARV et CV par mois (4 mois à venir) |

### Règles de confidentialité appliquées

Aucune liste n'affiche les noms ou prénoms des patients. Socle commun de toutes les listes :

```
N° Local | N° National | Sexe | Âge | Téléphone | Communautaire | Régime ARV
```

### Logique Attrition

```
Attrition = Perdus de vue
          + Transferts réels
          + Arrêts volontaires  (TransfCentre = "ARRET VOLONTAIRE" / "REFUS" / "refuse")
          + INJOIGNABLE         → comptés dans PDV
          + Décès
```

### Protocole Prochaine CV (vue_prochaine_cv)

```
Patient STABLE              → dernière CV + 12 mois
Patient NON STABLE + CV ≤1000 → dernière CV + 6 mois
Patient NON STABLE + CV >1000 → dernière CV + 4 mois
Patient NE (0 CV)           → DateMiseTARV + 6 mois
Patient NE (1 CV supprimée) → date CV + 6 mois
Patient NE (1 CV non supp.) → date CV + 4 mois
```

---

## 👤 Auteur

**Konaté Soumahila** — Data & AI Engineer
📧 Konatesoumahila124@gmail.com
🔗 [LinkedIn](https://www.linkedin.com/in/konate-soumahila-9a0461211/)
🐙 [GitHub](https://github.com/SOUMAHIL)
📍 Abidjan, Côte d'Ivoire

---

*Projet réalisé dans le cadre du portfolio professionnel — Master 2 MBDS 2026*