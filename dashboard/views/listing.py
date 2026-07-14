# =============================================================
# KoSanté BI — views/listing.py
# =============================================================
# Page 6 — Listing centralisé (impression)
# =============================================================

import streamlit as st
import sys
import io
import pandas as pd
from pathlib import Path
from datetime import date
from dateutil.relativedelta import relativedelta

sys.path.append(str(Path(__file__).parent.parent.parent))


def get_conn():
    from app import get_connection
    return get_connection()


def q(sql):
    """Requête sans cache — important pour les filtres dynamiques"""
    conn = get_conn()
    return conn.execute(sql).df()


COLONNES_SOCLE = {
    'NumInc': 'N° Local',
    'NumNational': 'N° National',
    'Sexe_label': 'Sexe',
    'Age': 'Âge',
    'Tel': 'Téléphone',
    'NomCommunautaire': 'Communautaire',
    'DernierRegime': 'Régime ARV',
}

LISTINGS_STATIQUES = {
    "File active complète": {
        "table": """
            SELECT
                fa.NumInc, fa.NumNational, fa.Sexe_label, fa.Age,
                p.Tel, fa.NomCommunautaire, fa.DernierRegime,
                fa.DateProchainRdv, fa.DatePDV,
                p.DateAdmi, p.DateNaiss,
                r.DateRegime, r.JOURS,
                m.DateMiseTARV
            FROM file_active fa
            INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
            LEFT JOIN (
                SELECT NumPatient, DateRegime, JOURS
                FROM TblRegime WHERE Derniere_Dispensation = TRUE
            ) r ON p.NumNational = r.NumPatient
            LEFT JOIN TblMiseEnRoute m ON fa.NumInc = m.Patient
            WHERE fa.StatutFile = 'Actif'
            ORDER BY fa.NumInc
        """,
        "mode": "sql_direct",
        "renommage": {
            'NumInc': 'N° Local', 'NumNational': 'N° National',
            'Sexe_label': 'Sexe', 'Age': 'Âge', 'Tel': 'Téléphone',
            'NomCommunautaire': 'Communautaire', 'DernierRegime': 'Régime ARV',
            'DateProchainRdv': 'Prochain RDV', 'DatePDV': 'Date PDV limite',
            'DateAdmi': 'Date admission', 'DateNaiss': 'Date naissance',
            'DateRegime': 'Dernière dispensation', 'JOURS': 'Jours',
            'DateMiseTARV': 'Date mise sous ARV'
        },
        "description": "Liste complète des patients actifs dans la file Ko'Khoua."
    },
    "Attrition — 12 derniers mois": {
        "table": """
            SELECT
                a.NumInc, a.NumNational, a.Sexe_label, a.Age,
                a.Tel, a.NomCommunautaire, a.DernierRegime,
                a.categorie_attrition,
                COALESCE(
                    TRY_CAST(a.TransfDate AS DATE),
                    TRY_CAST(a.DecesDate AS DATE),
                    TRY_CAST(a.DatePDV AS DATE)
                ) AS date_sortie,
                a.TransfCentre, a.DecesDate,
                p.DateAdmi
            FROM attrition a
            INNER JOIN TblDossPatient p ON a.NumInc = p.NumInc
            WHERE a.categorie_attrition IS NOT NULL
              AND (
                TRY_CAST(a.TransfDate AS DATE) >= (CURRENT_DATE - INTERVAL '12 months')
                OR TRY_CAST(a.DecesDate AS DATE) >= (CURRENT_DATE - INTERVAL '12 months')
                OR TRY_CAST(a.DatePDV AS DATE) >= (CURRENT_DATE - INTERVAL '12 months')
              )
            ORDER BY date_sortie DESC
        """,
        "mode": "sql_direct",
        "renommage": {
            'NumInc': 'N° Local', 'NumNational': 'N° National',
            'Sexe_label': 'Sexe', 'Age': 'Âge', 'Tel': 'Téléphone',
            'NomCommunautaire': 'Communautaire', 'DernierRegime': 'Régime ARV',
            'categorie_attrition': 'Catégorie', 'date_sortie': 'Date sortie',
            'TransfCentre': 'Centre transfert', 'DecesDate': 'Date décès',
            'DateAdmi': 'Date admission'
        },
        "description": "Patients sortis de la file active (PDV + Transferts + Arrêts + Décès) au cours des 12 derniers mois."
    },
    "À risque fin de mois (RDV ARV)": {
        "table": "a_risque_fin_mois",
        "colonnes_extra": {
            'DateProchainRdv': 'RDV prévu',
            'jours_retard_rdv': 'Jours retard',
            'DatePDV': 'Sera PDV le'
        },
        "description": "Patients actifs dont la dispensation ARV expire avant "
                       "la fin du mois en cours — à relancer en priorité."
    },
    "Patients Non Stables (CV)": {
        "table": "patients_non_stables",
        "colonnes_extra": {
            'derniere_cv': 'Dernière CV',
            'date_derniere_cv': 'Date dernière CV',
            'avant_derniere_cv': 'CV précédente',
            'date_avant_derniere_cv': 'Date CV précédente'
        },
        "description": "Patients avec 2 dernières CV consécutives > 1000 copies/mL."
    },
    "Patients Non Évalués (NE)": {
        "table": "patients_non_evalues",
        "colonnes_extra": {
            'nb_cv_disponibles': 'Nb CV disponibles',
            'derniere_date_cv': 'Date dernière CV'
        },
        "description": "Patients actifs avec moins de 2 CV disponibles."
    },
    "Perdus de vue (3 derniers mois)": {
        "table": "pdv_listing",
        "filtre": "WHERE jours_depuis_pdv <= 90",
        "colonnes_extra": {
            'DatePDV': 'Devenu PDV le',
            'jours_depuis_pdv': 'Jours depuis PDV'
        },
        "description": "Patients perdus de vue au cours des 3 derniers mois."
    },
    "Perdus de vue (6 derniers mois)": {
        "table": "pdv_listing",
        "filtre": "WHERE jours_depuis_pdv <= 180",
        "colonnes_extra": {
            'DatePDV': 'Devenu PDV le',
            'jours_depuis_pdv': 'Jours depuis PDV'
        },
        "description": "Patients perdus de vue au cours des 6 derniers mois."
    },
}

# Générer les 4 prochains mois dynamiquement
def get_mois_options():
    today = date.today()
    mois = []

    # Mois en cours d'abord
    m = today
    label = m.strftime('%B %Y').capitalize()
    debut = m.replace(day=1).strftime('%Y-%m-%d')
    fin = (m.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')
    mois.append({"label": label, "debut": debut, "fin": fin})

    # 4 mois suivants
    for i in range(1, 5):
        m = today + relativedelta(months=i)
        label = m.strftime('%B %Y').capitalize()
        debut = m.replace(day=1).strftime('%Y-%m-%d')
        fin = (m.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)).strftime('%Y-%m-%d')
        mois.append({"label": label, "debut": debut, "fin": fin})

    return mois


def afficher_listing(df_display, titre, description):
    """Affiche un listing avec en-tête + export"""
    st.markdown(
        f'<div class="ks-warning">ℹ️ {description}</div>',
        unsafe_allow_html=True
    )
    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:white; border:1px solid #E3DDD0; border-radius:6px;
         padding:14px 18px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-family:'Space Grotesk',sans-serif; font-size:14px;
                     font-weight:600; color:#1F4D3A;">{titre}</div>
                <div style="font-size:11px; color:#8A8275;">
                    KoSanté BI · Ko'Khoua ONG · Généré le {date.today().strftime('%d/%m/%Y')}
                </div>
            </div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:24px;
                 font-weight:600; color:#3D8C7D;">
                {len(df_display):,}
                <span style="font-size:12px; color:#8A8275; font-family:'Inter',sans-serif;">
                    patients
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df_display.empty:
        st.markdown(
            '<div class="ks-warning">✅ Aucun patient dans ce listing</div>',
            unsafe_allow_html=True
        )
        return

    st.dataframe(df_display, use_container_width=True, hide_index=True, height=420)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        csv = df_display.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            "⬇️ CSV",
            data=csv,
            file_name=f"{titre.replace(' ', '_')}_{date.today()}.csv",
            mime="text/csv",
            key=f"csv_{titre}"
        )
    with col2:
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_display.to_excel(writer, index=False, sheet_name='Listing')
            st.download_button(
                "⬇️ Excel",
                data=buffer.getvalue(),
                file_name=f"{titre.replace(' ', '_')}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"excel_{titre}"
            )
        except Exception:
            pass
    with col3:
        st.markdown(
            '<p style="font-size:11px; color:#8A8275; margin-top:8px;">'
            '🖨️ Télécharger CSV/Excel puis imprimer depuis votre tableur, '
            'ou <strong>Ctrl+P</strong> (paysage recommandé).</p>',
            unsafe_allow_html=True
        )


def render():
    st.markdown("""
    <div style="margin-bottom:0.5rem;">
        <h2 style="font-size:20px; font-weight:600; color:#1F4D3A; margin:0 0 4px;">
            Listings & Rapports
        </h2>
        <p style="font-size:13px; color:#8A8275; margin:0;">
            Listes anonymisées + Rapport mensuel SIG DIIS
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Onglets : Listings / Rapport SIG ──────────────────────
    tab1, tab2 = st.tabs(["📋 Listings", "📄 Rapport SIG"])

    with tab2:
        st.markdown("""
        <div style="background:#F6F3EC; border:1px solid #E3DDD0;
             border-left:4px solid #1F4D3A; border-radius:6px;
             padding:14px 18px; margin-bottom:16px;">
            <div style="font-size:14px; font-weight:600; color:#1F4D3A;">
                Rapports Mensuels Automatiques
            </div>
            <div style="font-size:12px; color:#8A8275; margin-top:4px;">
                Génère automatiquement les rapports officiels depuis les données Ko'Khoua BI
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sélection du mois
        today = date.today()
        mois_precedent = today.replace(day=1) - relativedelta(months=1)

        col1, col2 = st.columns([1, 2])
        with col1:
            annee = st.selectbox(
                "Année", list(range(today.year, today.year - 3, -1)),
                key="sig_annee"
            )
        with col2:
            MOIS_LABELS = [
                "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
            ]
            mois = st.selectbox(
                "Mois", list(range(1, 13)),
                index=mois_precedent.month - 1,
                format_func=lambda m: MOIS_LABELS[m-1],
                key="sig_mois"
            )

        mois_str   = f"{annee}-{mois:02d}"
        mois_label = MOIS_LABELS[mois-1]
        fin_mois   = (date(annee, mois, 1) + relativedelta(months=1) - relativedelta(days=1))

        st.markdown(
            f'<div style="font-size:12px; color:#3D8C7D; margin:8px 0;">'
            f'📅 Rapport du mois de <strong>{mois_label} {annee}</strong> '
            f'(activités du 01/{mois:02d}/{annee} au {fin_mois.day}/{mois:02d}/{annee})</div>',
            unsafe_allow_html=True
        )

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)

        # ── Rapport SIG ──────────────────────────────────────
        st.markdown(
            '<div style="font-size:13px; font-weight:600; color:#1F4D3A; '
            'margin-bottom:8px;">📋 Rapport SIG — DIIS</div>',
            unsafe_allow_html=True
        )

        fichier_prelev = st.file_uploader(
            "Fichier Excel prélèvements (optionnel — Tableau 21a)",
            type=["xlsx", "xls"], key="sig_prelevements",
        )
        df_prev = None
        if fichier_prelev:
            try:
                df_prev = pd.read_excel(fichier_prelev, sheet_name="CNTS", header=3)
                st.success(f"✅ {len(df_prev)} prélèvements chargés")
            except Exception as e:
                st.warning(f"⚠️ Impossible de lire le fichier : {e}")

        if st.button("📄 Générer Rapport SIG", use_container_width=True,
                     type="primary", key="btn_rapport_sig"):
            with st.spinner(f"Génération Rapport SIG {mois_label} {annee}..."):
                try:
                    import sys
                    sys.path.append(str(Path(__file__).parent.parent.parent))
                    from rapport_sig import generer_rapport
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        chemin = generer_rapport(mois_str, df_prev, tmpdir)
                        contenu = open(chemin, "rb").read()
                    st.download_button(
                        "⬇️ Télécharger Rapport SIG (.docx)",
                        data=contenu,
                        file_name=f"Rapport_SIG_KoKhoua_{mois_label}_{annee}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_rapport_sig"
                    )
                    st.success(f"✅ Rapport SIG {mois_label} {annee} généré !")
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")
                    import traceback
                    with st.expander("Détails"):
                        st.code(traceback.format_exc())

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)

        # ── Rapport RMA ──────────────────────────────────────
        st.markdown(
            '<div style="font-size:13px; font-weight:600; color:#1F4D3A; '
            'margin-bottom:8px;">📊 Rapport RMA — JHPIEGO RISE</div>',
            unsafe_allow_html=True
        )

        if st.button("📊 Générer Rapport RMA", use_container_width=True,
                     type="primary", key="btn_rapport_rma"):
            with st.spinner(f"Génération Rapport RMA {mois_label} {annee}..."):
                try:
                    import sys
                    sys.path.append(str(Path(__file__).parent.parent.parent))
                    from rapport_rma import generer_rapport_rma
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        chemin = generer_rapport_rma(mois_str, tmpdir)
                        contenu = open(chemin, "rb").read()
                    st.download_button(
                        "⬇️ Télécharger Rapport RMA (.docx)",
                        data=contenu,
                        file_name=f"Rapport_RMA_KoKhoua_{mois_label}_{annee}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_rapport_rma"
                    )
                    st.success(f"✅ Rapport RMA {mois_label} {annee} généré !")
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")
                    import traceback
                    with st.expander("Détails"):
                        st.code(traceback.format_exc())

    with tab1:
        # ── Sélecteur de date de référence ───────────────────
        today = date.today()
        fin_mois_precedent = today.replace(day=1) - relativedelta(days=1)

        st.markdown("""
        <div style="background:#F0F7F4; border:1px solid #B8D9CC;
             border-left:4px solid #3D8C7D; border-radius:6px;
             padding:10px 16px; margin-bottom:14px;">
            <div style="font-size:13px; font-weight:600; color:#1F4D3A;">
                📅 Date de référence des listings
            </div>
            <div style="font-size:11px; color:#8A8275; margin-top:2px;">
                Tous les listings seront calculés à cette date.
                Choisissez la fin du mois souhaité pour obtenir
                les listes historiques (ex: 30/06/2026 pour juin).
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_date, col_info = st.columns([1, 2])
        with col_date:
            date_ref = st.date_input(
                "Date de référence",
                value=fin_mois_precedent,
                max_value=today,
                format="DD/MM/YYYY",
                key="listing_date_ref"
            )
        with col_info:
            st.markdown(
                f'<div style="margin-top:28px; font-size:12px; color:#3D8C7D;">'
                f'✅ Listings calculés au <strong>'
                f'{date_ref.strftime("%d/%m/%Y")}</strong><br>'
                f'<span style="color:#8A8275;">'
                f'File active = patients dont DatePDV ≥ {date_ref.strftime("%d/%m/%Y")}'
                f'</span></div>',
                unsafe_allow_html=True
            )

        date_ref_str = date_ref.strftime("%Y-%m-%d")

        st.markdown('<hr style="margin:12px 0;">', unsafe_allow_html=True)

        # ── SQL file active figée à date_ref ─────────────────
        FA_FIGE = f"""
            SELECT
                p.NumInc, p.NumNational, p.Sexe_label, p.Age,
                p.Tel, p.NomCommunautaire, p.TypePatient,
                r.REGIME AS DernierRegime,
                r.DateRegime AS DerniereDispensation,
                r.JOURS,
                r.DateProchainRdv,
                r.DatePDV,
                p.DateAdmi, p.DateNaiss,
                m.DateMiseTARV,
                'Actif' AS StatutFile
            FROM TblRegime r
            INNER JOIN TblDossPatient p
                ON REGEXP_REPLACE(TRIM(CAST(r.NumPatient AS VARCHAR)), '^0+', '')
                 = REGEXP_REPLACE(TRIM(CAST(p.NumNational AS VARCHAR)), '^0+', '')
            LEFT JOIN TblMiseEnRoute m ON p.NumInc = m.Patient
            WHERE r.Derniere_Dispensation = TRUE
              AND r.REGIME IS NOT NULL
              AND TRY_CAST(r.DatePDV AS DATE) >= DATE '{date_ref_str}'
              AND (p.DecesDate IS NULL OR p.DecesDate = '')
              AND (p.TransfDate IS NULL OR p.TransfDate = '')
              AND p.NumInc > 0
        """

        # ── Sélecteur listing ─────────────────────────────────
        mois_options = get_mois_options()
        mois_labels = [m["label"] for m in mois_options]

        tous_listings = list(LISTINGS_STATIQUES.keys()) + \
                        [f"RDV ARV attendus — {m}" for m in mois_labels] + \
                        [f"CV attendus — {m}" for m in mois_labels]

        choix = st.selectbox("Sélectionner un listing", tous_listings)

        # Vider le cache si choix ou date changent
        cache_key = f"{choix}_{date_ref_str}"
        if st.session_state.get("dernier_cache_key") != cache_key:
            st.cache_data.clear()
            st.session_state["dernier_cache_key"] = cache_key

        def fmt_dates(df):
            """Formate toutes les colonnes de dates en DD/MM/YYYY"""
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        parsed = pd.to_datetime(df[col], errors='coerce')
                        if parsed.notna().sum() > len(df) * 0.3:
                            df[col] = parsed.dt.strftime('%d/%m/%Y').where(
                                parsed.notna(), other=''
                            )
                    except Exception:
                        pass
            return df

        # ── Listing RDV ARV par mois ──────────────────────────
        if choix.startswith("RDV ARV attendus"):
            mois_choisi = next(
                (m for m in mois_options if m["label"] in choix), None
            )
            if mois_choisi:
                df = q(f"""
                    SELECT
                        NumInc, NumNational, Sexe_label, Age,
                        Tel, NomCommunautaire, DernierRegime,
                        DateProchainRdv, DatePDV
                    FROM ({FA_FIGE}) fa
                    WHERE TRY_CAST(DateProchainRdv AS DATE)
                          BETWEEN DATE '{mois_choisi["debut"]}'
                          AND DATE '{mois_choisi["fin"]}'
                    ORDER BY DateProchainRdv ASC
                """)
                df_display = fmt_dates(df.rename(columns={
                    **COLONNES_SOCLE,
                    'DateProchainRdv': 'RDV prévu',
                    'DatePDV': 'Date PDV limite'
                }))
                afficher_listing(
                    df_display,
                    f"RDV ARV — {mois_choisi['label']}",
                    f"Patients actifs au {date_ref.strftime('%d/%m/%Y')} "
                    f"dont le RDV ARV est prévu en {mois_choisi['label']}."
                )

        # ── Listing CV attendus par mois ──────────────────────
        elif choix.startswith("CV attendus"):
            mois_choisi = next(
                (m for m in mois_options if m["label"] in choix), None
            )
            if mois_choisi:
                df = q(f"""
                    SELECT
                        NumInc, NumNational, Sexe_label, Age,
                        Tel, NomCommunautaire, DernierRegime,
                        StatutCV, cv1_date AS date_derniere_cv,
                        cv1_copies AS derniere_cv_copies,
                        DateMiseTARV, prochaine_cv_date
                    FROM vue_prochaine_cv
                    WHERE prochaine_cv_date IS NOT NULL
                      AND prochaine_cv_date
                          BETWEEN DATE '{mois_choisi["debut"]}'
                          AND DATE '{mois_choisi["fin"]}'
                    ORDER BY prochaine_cv_date ASC
                """)
                df_display = fmt_dates(df.rename(columns={
                    'NumInc': 'N° Local', 'NumNational': 'N° National',
                    'Sexe_label': 'Sexe', 'Age': 'Âge', 'Tel': 'Téléphone',
                    'NomCommunautaire': 'Communautaire',
                    'DernierRegime': 'Régime ARV',
                    'StatutCV': 'Statut CV',
                    'date_derniere_cv': 'Date dernière CV',
                    'derniere_cv_copies': 'Dernière CV (copies)',
                    'DateMiseTARV': 'Date mise sous ARV',
                    'prochaine_cv_date': 'Prochaine CV prévue'
                }))
                afficher_listing(
                    df_display,
                    f"CV attendus — {mois_choisi['label']}",
                    f"Patients actifs dont la prochaine CV est prévue "
                    f"en {mois_choisi['label']} selon la procédure Ko'Khoua."
                )

        # ── Listings statiques ────────────────────────────────
        else:
            config = LISTINGS_STATIQUES[choix]
            mode = config.get("mode", "table")

            if choix == "File active complète":
                # File active figée à date_ref
                df = q(f"""
                    SELECT
                        NumInc, NumNational, Sexe_label, Age,
                        Tel, NomCommunautaire, DernierRegime,
                        DateProchainRdv, DatePDV,
                        DateAdmi, DateNaiss,
                        DerniereDispensation AS DateRegime,
                        JOURS, DateMiseTARV
                    FROM ({FA_FIGE}) fa
                    ORDER BY NumInc
                """)
                df_display = fmt_dates(df.rename(columns={
                    'NumInc': 'N° Local', 'NumNational': 'N° National',
                    'Sexe_label': 'Sexe', 'Age': 'Âge', 'Tel': 'Téléphone',
                    'NomCommunautaire': 'Communautaire',
                    'DernierRegime': 'Régime ARV',
                    'DateProchainRdv': 'Prochain RDV',
                    'DatePDV': 'Date PDV limite',
                    'DateAdmi': 'Date admission',
                    'DateNaiss': 'Date naissance',
                    'DateRegime': 'Dernière dispensation',
                    'JOURS': 'Jours',
                    'DateMiseTARV': 'Date mise sous ARV'
                }))
                afficher_listing(
                    df_display,
                    f"File active au {date_ref.strftime('%d/%m/%Y')}",
                    f"Patients actifs au {date_ref.strftime('%d/%m/%Y')} "
                    f"— {len(df_display):,} patients."
                )

            elif mode == "sql_direct":
                df = q(config["table"])
                df_display = fmt_dates(
                    df.rename(columns=config.get("renommage", {}))
                )
                afficher_listing(df_display, choix, config["description"])

            else:
                colonnes_extra = list(config["colonnes_extra"].keys())
                toutes_colonnes = list(COLONNES_SOCLE.keys()) + colonnes_extra
                filtre = config.get("filtre", "")
                sql = f"""
                    SELECT {", ".join(toutes_colonnes)}
                    FROM {config['table']}
                    {filtre}
                """
                df = q(sql)
                df_display = fmt_dates(df.rename(
                    columns={**COLONNES_SOCLE, **config["colonnes_extra"]}
                ))
                afficher_listing(df_display, choix, config["description"])