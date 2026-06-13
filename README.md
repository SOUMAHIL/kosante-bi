# KoSanté BI — Plateforme d'Analyse & Suivi des PVVIH

> **Projet Data Engineering & Business Intelligence**  
> Développé par **Konaté Soumahila** — Data & AI Engineer  
> Formation : Master 2 MBDS — Université Côte d'Azur / ESATIC Abidjan

---

## 📋 Contexte

[Ko'Khoua](https://www.kokhoua.org) est une ONG ivoirienne spécialisée dans la prise en charge des **Personnes Vivant avec le VIH/SIDA (PVVIH)** à Abidjan, Côte d'Ivoire. Active depuis 1992, elle gère plus de **6 000 dossiers patients** et assure le suivi médical, le traitement ARV et le conseil-dépistage.

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
        ┌──────────┴──────────┐
        │                     │
  [Streamlit]            [Power BI]
  Dashboard quotidien    Rapport direction
```

### Stack technologique

| Couche | Technologie |
|--------|-------------|
| Extraction | Python · pyodbc · access-parser |
| Transformation | Python · Pandas · NumPy |
| Stockage | DuckDB (fichier local) |
| Dashboard | Streamlit · Plotly |
| Rapport | Power BI Desktop |

---

## 📊 KPIs — Cascade 95-95-95 ONUSIDA

| # | Indicateur | Source | Règle métier |
|---|-----------|--------|--------------|
| 1 | Nombre de dépistages & taux positivité | TblRegistreCDV | Actes CDV réalisés |
| 2 | File active PVVIH | TblDossPatient | Patients sans décès ni transfert |
| 3 | Taux de mise sous ARV | TblMiseEnRoute | Patients avec DateMiseTARV |
| 4 | Charge virale supprimée | TblChargesVirales | CVcopies ≤ 1 000 copies/mL |
| 5 | CD4 moyen | TblDossExamensBio | Dernière valeur CD4Nb par patient |
| 6 | Perdus de vue | TblDossSuiviPatient + TblRegime | RDV raté ≥ 28 jours |

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
> Le lien avec `TblDossPatient` via `NumeroPrimoci` n'est plus renseigné depuis 2017.  
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
│   └── load.py                 ← Chargement DuckDB
├── dashboard/
│   └── app.py                  ← Dashboard Streamlit
├── powerbi/
│   └── kosante.pbix            ← Rapport Power BI
├── lancer_dashboard.bat        ← Lancement en 1 clic
├── requirements.txt
├── config.py                   ← Configuration centrale
└── README.md
```

---

## 🚀 Installation & Lancement

### Prérequis
- Python 3.10+
- Microsoft Access Database Engine (driver ODBC)
- Les fichiers `.mdb` dans le dossier `data/`

### Installation

```bash
# 1. Cloner le projet
git clone https://github.com/SOUMAHIL/kosante-bi.git
cd kosante-bi

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'extraction
python etl/extract.py

# 4. Lancer le dashboard
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
| **Phase 3** | Dashboard Streamlit | 🔄 En cours |
| **Phase 4** | Rapport Power BI | ⏳ À venir |
| **Phase 5** | Finalisation · Déploiement | ⏳ À venir |

---

## 🔍 Phase 1 — Détail technique

### Extraction (extract.py)

- Connexion via **pyodbc** (driver ODBC Microsoft Access)
- Extraction table par table avec gestion d'erreurs
- Export CSV encodage **UTF-8 BOM** (compatibilité Excel + accents)
- Gestion séparée des mots de passe (SIGDEP protégé)

### Audit qualité (audit_qualite.py)

Contrôles effectués :

| Contrôle | Résultat |
|----------|----------|
| Doublons TblDossPatient | ✅ 0 doublon sur NumInc |
| Doublons TblMiseEnRoute | ⚠️ 1 doublon → garder dernière DateMiseTARV |
| Jointures clinique (NumInc) | ✅ 99.9% de match |
| Jointure inter-bases (NumNational) | ✅ 92.6% de match (316 patients pharmacie sans dossier clinique) |
| Dates aberrantes | ⚠️ Quelques DateNaiss avant 1980 et futures → filtrées en Phase 2 |
| Colonnes 100% nulles | ℹ️ Nombreuses colonnes non renseignées → ignorées |

### Décisions techniques documentées

**Pourquoi DuckDB ?**  
DuckDB est un moteur analytique embarqué (fichier `.duckdb`) — zéro installation serveur, performances excellentes sur des agrégats analytiques, compatible Python et Power BI via ODBC.

**Pourquoi `NumInc` et non `Code` comme clé clinique ?**  
Après inspection des données réelles, `NumInc` est l'identifiant opérationnel utilisé dans toutes les tables de suivi. `Code` est un identifiant Access interne non cohérent entre tables.

**Pourquoi TblRegistreCDV est indépendante ?**  
Le registre CDV est anonyme — le lien `NumeroPrimoci` vers `TblDossPatient` n'est plus renseigné depuis 2017. Traitement en flux agrégé indépendant, conforme aux pratiques PNLS Côte d'Ivoire.

---


---

## 🔄 Phase 2 — Détail technique

### Transformation (transform.py)

Transformations appliquées sur les 7 tables :

| Table | Transformations clés |
|-------|---------------------|
| TblDossPatient | Normalisation NumNational (5→4 chiffres) · TypePatient · NomCommunautaire · StatutPatient · Age |
| TblMiseEnRoute | Gestion doublon → DateMiseTARV la plus récente |
| TblChargesVirales | CV_Statut (Supprimée/Non supprimée) · StatutCV (Stable/Non Stable/NE) |
| TblDossExamensBio | CD4_Dernier · CD4_Alerte (< 200) |
| TblRegime | Normalisation NumPatient · DateProchainRdv · DatePDV · Actif_Pharmacie |
| TblDossSuiviPatient | Détection VisiteDate · Derniere_Visite |
| TblRegistreCDV | Resultat_label (stades 0-5) · Resultat_simple |

### Décisions techniques Phase 2

**Normalisation NumNational :**
Depuis 2026, la clinique saisit les numéros nationaux sur 5 chiffres (`00132/...`)
alors que SIGDEP pharmacie reste sur 4 chiffres (`0132/...`).
On normalise les deux côtés au format 4 chiffres avant toute jointure.

**Statut CV — 3 catégories :**
- `Stable` → 2 dernières CV consécutives ≤ 1 000 copies/mL
- `Non Stable` → 2 dernières CV consécutives > 1 000 copies/mL  
- `NE` (Non Évalué) → moins de 2 CV disponibles

**TypePatient — 2 catégories :**
- `Nouveau Ko'Khoua` → NumNational commence par `0132/01/`
- `Transfert In` → préfixe différent (vient d'un autre centre)

### Chargement DuckDB (load.py)

**Logique File Active Ko'Khoua :**
```
Un patient est ACTIF si :
  ✅ Il a une dispensation ARV dans TblRegime
  ✅ DatePDV (= DateRegime + JOURS + 28j) >= aujourd'hui
  ✅ DecesDate IS NULL (pas décédé)
  ✅ TransfDate IS NULL (pas transféré)
  ✅ NumInc > 0
```

**Vues analytiques créées :**

| Vue | Description |
|-----|-------------|
| `file_active` | Patients actifs selon logique Ko'Khoua |
| `patients_rdv_manque` | Retard RDV 1-27 jours (toujours actifs) |
| `perdus_de_vue` | ≥ 28 jours sans venir (hors file active) |
| `kpis_file_active` | Tous les KPIs sur patients actifs uniquement |
| `cascade_95_95_95` | 3 indicateurs ONUSIDA sur file active |

### Résultats Phase 2 — Chiffres réels Ko'Khoua

| Indicateur | Valeur | Objectif |
|-----------|--------|----------|
| File active | 2 443 patients | — |
| Sous ARV | 2 442 (100.0%) | 95% ✅ |
| CV supprimée | 2 331 / 2 429 (96.0%) | 95% ✅ |
| CD4 moyen | 641 cellules/mm³ | — |
| Patients stables | 2 276 (98.7%) | — |
| Patients non stables | 29 (1.3%) | — |
| Non évalués (NE) | 127 (5.2%) | — |
| RDV manqués | 291 patients | — |
| Perdus de vue | 588 patients | — |

---

## 👤 Auteur

**Konaté Soumahila** — Data & AI Engineer  
📧 Konatesoumahila124@gmail.com  
🔗 [LinkedIn](https://www.linkedin.com/in/konate-soumahila-9a0461211/)  
🐙 [GitHub](https://github.com/SOUMAHIL)  
📍 Abidjan, Côte d'Ivoire

---

*Projet réalisé dans le cadre du portfolio professionnel — Master 2 MBDS 2026*