# KoSanté BI — Dictionnaire des Données

> Référence complète des tables, champs et KPIs du projet.
> Destiné aux utilisateurs du dashboard et aux développeurs.

---

## 1. Sources de données

### 1.1 CMSDSdata.mdb — Base clinique

#### TblDossPatient
*Table centrale — 1 ligne par patient — 6 017 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| NumInc | Entier | **Clé primaire** — Numéro incrémental patient |
| NumNational | Texte | Numéro national VIH (format `XXXX/XX/XX/XXXXX`) |
| Nom | Texte | Nom du patient |
| Prenoms | Texte | Prénoms du patient |
| Sexe | Entier | 1 = Masculin · 2 = Féminin |
| DateNaiss | Date | Date de naissance |
| DateAdmi | Date | Date d'admission à Ko'Khoua |
| CommuneVillage | Texte | Commune ou village de résidence |
| StadeOMS | Entier | Stade clinique OMS (1 à 4) |
| VIHType | Texte | Type de VIH (VIH-1, VIH-2) |
| DECES | Entier | 1 = Décédé |
| DecesDate | Date | Date du décès |
| Transf | Entier | 1 = Transféré vers un autre centre |
| TransfDate | Date | Date du transfert |
| TransfCentre | Texte | Centre d'accueil du transfert |

*Colonnes calculées ajoutées par transform.py :*

| Champ calculé | Description |
|---------------|-------------|
| Sexe_label | "M" ou "F" |
| Age | Âge en années à la date du jour |
| NomCommunautaire | Agent communautaire selon période d'admission |
| StatutPatient | "Actif" / "Décédé" / "Transféré" |
| NumNational | Normalisé au format 4 chiffres |
| TypePatient | "Nouveau Ko'Khoua" / "Transfert In" / "Inconnu" |

---

#### TblMiseEnRoute
*Initiation traitement ARV — 1 ligne par patient — 4 994 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| Patient | Entier | FK → TblDossPatient.NumInc |
| DateMiseTARV | Date | Date de mise sous traitement ARV |
| Regime | Texte | Régime ARV initial |
| Poids | Décimal | Poids au démarrage (kg) |
| Taille | Décimal | Taille au démarrage (cm) |

---

#### TblChargesVirales
*Résultats charge virale — multi-lignes par patient — 31 989 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| Patient | Entier | FK → TblDossPatient.NumInc |
| DatePrelev | Date | Date du prélèvement |
| CVcopies | Décimal | Charge virale en copies/mL |
| CVlog | Décimal | Charge virale en log10 |
| CVseuil | Texte | Seuil laboratoire |

*Colonnes calculées :*

| Champ calculé | Description |
|---------------|-------------|
| CV_Statut | "Supprimée" (≤1000) / "Non supprimée" (>1000) / "Non renseigné" |
| CV_Derniere | True = dernière CV de ce patient |

---

#### TblDossExamensBio
*Bilans biologiques — multi-lignes par patient — 86 265 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| Patient | Entier | FK → TblDossPatient.NumInc |
| DateExam | Date | Date du bilan |
| CD4Nb | Entier | Taux de CD4 en cellules/mm³ |
| CD4Pcent | Décimal | Pourcentage de CD4 |
| HEMOGL | Décimal | Hémoglobine (g/dL) |

*Colonnes calculées :*

| Champ calculé | Description |
|---------------|-------------|
| CD4_Dernier | True = dernier bilan CD4 de ce patient |
| CD4_Alerte | True = CD4 < 200 cellules/mm³ |

---

#### TblDossSuiviPatient
*Visites cliniques — multi-lignes par patient — 103 521 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| Patient | Entier | FK → TblDossPatient.NumInc |
| VisiteDate | Date | Date de la visite |
| Poids | Décimal | Poids à la visite (kg) |
| StadeOMS | Entier | Stade OMS à la visite |
| ARV | Entier | Sous ARV à cette visite |
| TB_Conclu | Texte | Conclusion tuberculose |

---

#### TblRegistreCDV
*Registre dépistage — table indépendante — 20 060 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| Code | Entier | Identifiant acte CDV |
| DateVisite | Date | Date de la consultation CDV |
| Sexe | Entier | 1 = Masculin · 2 = Féminin |
| DateNaiss | Date | Date de naissance du client |
| Resultat | Entier | 0=Négatif · 1-5=Positif (stades) |
| Motivation | Texte | Raison de la consultation |
| Provenance | Texte | Origine de l'orientation |

*Colonnes calculées :*

| Champ calculé | Description |
|---------------|-------------|
| Resultat_label | "Négatif" / "Positif — Stade X" |
| Resultat_simple | "Négatif" / "Positif" / "Non renseigné" |

---

### 1.2 SIGDEP.mdb — Base pharmacie

#### TblRegime
*Dispensations ARV — multi-lignes par patient — 100 360 enregistrements*

| Champ | Type | Description |
|-------|------|-------------|
| NumPatient | Texte | FK → TblDossPatient.NumNational |
| DateRegime | Date | Date de la dispensation |
| REGIME | Texte | Nom du régime ARV dispensé |
| JOURS | Entier | Nombre de jours de traitement dispensé |

*Colonnes calculées :*

| Champ calculé | Description |
|---------------|-------------|
| DateProchainRdv | DateRegime + JOURS |
| DatePDV | DateProchainRdv + 28 jours |
| Actif_Pharmacie | True = DatePDV >= aujourd'hui |
| Derniere_Dispensation | True = dernière dispensation de ce patient |

---

### 1.3 StatutCV_Patient
*Table dérivée — 1 ligne par patient évalué — 3 718 enregistrements*

| Champ | Description |
|-------|-------------|
| NumInc | Identifiant patient |
| StatutCV | "Stable" / "Non Stable" / "NE" |

---

## 2. Vues analytiques DuckDB

### file_active
*Patients actifs selon logique Ko'Khoua*

**Règle :**
```sql
Patient ACTIF = TblDossPatient JOIN TblRegime (dernière dispensation)
WHERE DatePDV >= CURRENT_DATE
  AND DecesDate IS NULL
  AND TransfDate IS NULL
  AND NumInc > 0
```

**Champs clés :**

| Champ | Description |
|-------|-------------|
| NumInc | Identifiant patient |
| StatutFile | "Actif" / "Perdu de vue" |
| DernierRegime | Dernier régime ARV dispensé |
| DatePDV | Date limite avant statut perdu de vue |

---

### patients_rdv_manque
*Patients en retard de RDV mais toujours actifs (1-27 jours)*

**Règle :**
```
DateProchainRdv < aujourd'hui
ET DatePDV >= aujourd'hui
```

---

### perdus_de_vue
*Patients hors file active — ≥ 28 jours sans venir*

**Règle :**
```
DatePDV < aujourd'hui
ET pas décédé ET pas transféré
```

---

### kpis_file_active
*Tous les KPIs calculés sur les patients actifs uniquement*

| KPI | Formule |
|-----|---------|
| total_actifs | COUNT patients actifs |
| nb_cv_supprimee | COUNT dernière CV ≤ 1000 parmi actifs |
| pct_cv_supprimee | nb_cv_supprimee / nb_cv_evalue × 100 |
| cd4_moyen | AVG dernier CD4 parmi actifs |
| nb_stable | COUNT StatutCV = "Stable" parmi actifs |
| nb_non_stable | COUNT StatutCV = "Non Stable" parmi actifs |
| nb_ne | COUNT StatutCV = "NE" parmi actifs |
| pct_stable | nb_stable / (nb_stable + nb_non_stable) × 100 |
| nouveaux_kokhoua | COUNT nouveaux patients Ko'Khoua ce mois |
| transfert_in | COUNT transferts In ce mois |
| nb_rdv_manque | COUNT patients en retard RDV 1-27 jours |
| nb_perdus_de_vue | COUNT patients perdus de vue ≥ 28 jours |

---

### cascade_95_95_95
*Indicateurs ONUSIDA — standard Côte d'Ivoire*

| Étape | Indicateur | Objectif |
|-------|-----------|----------|
| ① | Patients actifs connus et suivis | Référence |
| ② | % sous ARV parmi les actifs | 95% |
| ③ | % CV supprimée parmi les actifs évalués | 95% |

---

## 3. Règles métier Ko'Khoua

| Règle | Valeur | Explication |
|-------|--------|-------------|
| CV supprimée | ≤ 1 000 copies/mL | Standard Ko'Khoua CI |
| CV non supprimée | > 1 000 copies/mL | Échec virologique |
| Perdu de vue | ≥ 28 jours après DatePDV | RDV manqué + délai de grâce |
| CD4 bas | < 200 cellules/mm³ | Immunodépression sévère (OMS) |
| Patient stable | 2 CV consécutives supprimées | Contrôle virologique confirmé |
| Patient non stable | 2 CV consécutives non supprimées | Échec thérapeutique confirmé |
| Non évalué (NE) | < 2 CV disponibles | Suivi biologique insuffisant |

---

## 4. Agents communautaires Ko'Khoua

| Période | Agent |
|---------|-------|
| Jan 1992 — Août 2006 | Madame AKRE |
| Sep 2006 — Juil 2009 | Madame YAPI |
| Août 2009 — Déc 2011 | Madame LINDA |
| Jan 2012 — Déc 2014 | Madame LEONCE |
| Jan 2015 — Déc 2018 | Monsieur ISMO |
| Jan 2019 — aujourd'hui | Monsieur Clavaire |

---

*Document maintenu par Konaté Soumahila — Data & AI Engineer*
*Dernière mise à jour : Phase 2*