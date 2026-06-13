# KoSanté BI — Journal des Décisions Techniques

> Ce document explique **pourquoi** certains choix ont été faits.
> Il est destiné aux développeurs qui reprendront ce projet
> et aux recruteurs qui veulent comprendre le raisonnement.

---

## DEC-001 — Choix de pyodbc plutôt que access-parser

**Contexte :** Les bases Access `.mdb` doivent être lues depuis Python.

**Options évaluées :**
- `access-parser` → bibliothèque Python pure, pas de driver requis
- `pyodbc` → nécessite le driver Microsoft Access ODBC

**Décision :** `pyodbc`

**Raison :** `access-parser` échoue sur les fichiers `.mdb` complexes avec
des enregistrements "overflow" (erreur `NoneType object is not subscriptable`).
`pyodbc` fonctionne parfaitement car un code existant Ko'Khoua l'utilisait déjà
avec succès sur ces mêmes bases.

**Compromis accepté :** Le driver Microsoft Access doit être installé sur
chaque machine. Documenté dans DEPLOIEMENT.md.

---

## DEC-002 — Choix de DuckDB plutôt que PostgreSQL ou SQLite

**Contexte :** Besoin d'une base analytique pour stocker les données transformées.

**Options évaluées :**
- `SQLite` → fichier local, mais pas optimisé pour les agrégats analytiques
- `PostgreSQL` → puissant mais nécessite un serveur installé
- `DuckDB` → fichier local, optimisé analytique, zéro installation serveur

**Décision :** `DuckDB`

**Raison :**
- Zéro installation serveur → fonctionne sur le PC du directeur sans configuration
- Performances analytiques excellentes sur des agrégats (COUNT, AVG, GROUP BY)
- Compatible Python natif et Power BI via ODBC
- Fichier `.duckdb` portable → copie simple entre machines

---

## DEC-003 — Clé de jointure NumInc et non Code

**Contexte :** `TblDossPatient` a deux identifiants : `Code` et `NumInc`.

**Analyse des données :**
- `Code` → identifiant interne Access, non cohérent entre tables
- `NumInc` → identifiant opérationnel utilisé dans toutes les tables de suivi
  (`TblChargesVirales.Patient`, `TblDossExamensBio.Patient`, etc.)

**Décision :** `NumInc` comme clé de jointure interne clinique

**Validation :** Test de jointure → 99.9% de match entre `NumInc` et `Patient`
dans toutes les tables cliniques.

---

## DEC-004 — TblRegistreCDV traitée comme table indépendante

**Contexte :** Le registre CDV contient les actes de dépistage.
Un lien avec `TblDossPatient` existait via `NumeroPrimoci`.

**Analyse :**
- `NumeroPrimoci` n'est plus renseigné depuis 2017
- Le CDV est un registre anonyme/semi-anonyme
- Un client dépisté négatif n'est pas un patient
- Un client dépisté positif devient patient mais le lien n'est pas tracé numériquement

**Décision :** `TblRegistreCDV` = table indépendante

**Impact :** Les KPIs de dépistage sont calculés séparément.
La cascade 95-95-95 commence à partir de la file active,
pas depuis le CDV. Conforme aux pratiques PNLS Côte d'Ivoire.

---

## DEC-005 — Normalisation NumNational 5→4 chiffres

**Contexte :** Depuis 2026, la clinique saisit les numéros nationaux
sur 5 chiffres (`00132/01/26/00013`) alors que SIGDEP pharmacie
est limité à 4 chiffres (`0132/01/26/00013`).

**Impact :** Les nouveaux patients et les transferts In avec numéro 5 chiffres
ne matchent pas entre les deux bases → exclus de la file active.

**Décision :** Normalisation au format 4 chiffres sur les deux côtés
avant la jointure :
```python
00132/01/26/00013 → 0132/01/26/00013
```

**Compromis :** Les patients non matchés après normalisation
sont ajoutés manuellement par le gestionnaire de données.
Cette limitation est documentée et connue de l'équipe Ko'Khoua.

---

## DEC-006 — Logique File Active Ko'Khoua

**Contexte :** La "file active" doit refléter les patients réellement
suivis à Ko'Khoua à la date du jour.

**Décision :** Un patient est ACTIF si et seulement si :
```
✅ Il a une dispensation ARV dans TblRegime (REGIME IS NOT NULL)
✅ DatePDV = DateRegime + JOURS + 28 jours >= aujourd'hui
✅ DecesDate IS NULL (pas décédé)
✅ TransfDate IS NULL (pas transféré)
✅ NumInc > 0
```

**Raison :** Cette logique est celle utilisée opérationnellement
par Ko'Khoua depuis des années dans leurs outils existants.
Elle garantit que seuls les patients réellement actifs
sont pris en compte dans les KPIs.

**Conséquence importante :** Tous les KPIs (CV, CD4, Stable/Non Stable)
sont calculés UNIQUEMENT sur les patients actifs.
Un patient décédé ou transféré ne contribue à aucun indicateur.

---

## DEC-007 — Statut CV en 3 catégories

**Contexte :** Évaluer l'efficacité thérapeutique par patient.

**Règles Ko'Khoua :**
- `Stable` → 2 dernières CV consécutives ≤ 1 000 copies/mL
- `Non Stable` → 2 dernières CV consécutives > 1 000 copies/mL
- `NE` (Non Évalué) → moins de 2 CV disponibles

**Raison du choix de 2 CV consécutives :**
Une seule CV peut être un résultat ponctuel non représentatif.
2 CV consécutives dans le même sens confirment une tendance réelle.

**Seuil CV supprimée :** 1 000 copies/mL (standard Ko'Khoua CI)
— différent du seuil OMS de 200 copies/mL.

---

## DEC-008 — Distinction Nouveau Ko'Khoua / Transfert In

**Contexte :** Identifier l'origine des nouveaux patients.

**Règle :** Le numéro national Ko'Khoua commence par `0132/01/`
(code site `0132`, district `01`).

**Catégories :**
- `Nouveau Ko'Khoua` → `NumNational` commence par `0132/01/`
  → Patient dépisté et enregistré à Ko'Khoua
- `Transfert In` → préfixe différent
  → Vient d'un autre centre avec son numéro national existant

**Utilité :** Permet de mesurer la capacité de Ko'Khoua à dépister
de nouveaux patients vs attirer des patients déjà suivis ailleurs.

---

## DEC-009 — Perdus de vue hors file active

**Contexte :** Définir la relation entre "perdu de vue" et "file active".

**Décision :** Les perdus de vue sont **hors** de la file active.

**Raisonnement :**
```
File active  → DatePDV >= aujourd'hui  (patient présent)
Perdu de vue → DatePDV < aujourd'hui   (patient absent depuis ≥ 28 jours)
```
Ces deux états sont mutuellement exclusifs par définition.
Un patient ne peut pas être actif ET perdu de vue simultanément.

**KPI "RDV manqué"** (distinct de "perdu de vue") :
```
DateProchainRdv < aujourd'hui  (a raté son RDV)
ET DatePDV >= aujourd'hui      (pas encore à 28 jours)
→ Toujours actif, mais en retard → nécessite une relance
```

---

*Document maintenu par Konaté Soumahila — Data & AI Engineer*
*Dernière mise à jour : Phase 2*