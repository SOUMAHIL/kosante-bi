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
    for i in range(1, 5):
        m = today + relativedelta(months=i)
        label = m.strftime('%B %Y').capitalize()
        debut = m.replace(day=1).strftime('%Y-%m-%d')
        # Dernier jour du mois
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
            Listings — Export & Impression
        </h2>
        <p style="font-size:13px; color:#8A8275; margin:0;">
            Listes anonymisées prêtes à imprimer pour le suivi terrain
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sélecteur listing ─────────────────────────────────────
    mois_options = get_mois_options()
    mois_labels = [m["label"] for m in mois_options]

    tous_listings = list(LISTINGS_STATIQUES.keys()) + \
                    [f"RDV ARV attendus — {m}" for m in mois_labels]

    choix = st.selectbox("Sélectionner un listing", tous_listings)

    # Vider le cache quand le choix change pour forcer le recalcul
    if "dernier_choix_listing" not in st.session_state:
        st.session_state["dernier_choix_listing"] = choix
    if st.session_state["dernier_choix_listing"] != choix:
        st.cache_data.clear()
        st.session_state["dernier_choix_listing"] = choix

    # ── Listing RDV ARV par mois (dynamique) ─────────────────
    if choix.startswith("RDV ARV attendus"):
        mois_choisi = next(
            (m for m in mois_options if m["label"] in choix), None
        )
        if mois_choisi:
            df = q(f"""
                SELECT
                    fa.NumInc, fa.NumNational, fa.Sexe_label, fa.Age,
                    p.Tel, fa.NomCommunautaire, fa.DernierRegime,
                    fa.DateProchainRdv,
                    fa.DatePDV
                FROM file_active fa
                INNER JOIN TblDossPatient p ON fa.NumInc = p.NumInc
                WHERE fa.StatutFile = 'Actif'
                  AND CAST(fa.DateProchainRdv AS DATE)
                      BETWEEN DATE '{mois_choisi["debut"]}'
                      AND DATE '{mois_choisi["fin"]}'
                ORDER BY fa.DateProchainRdv ASC
            """)

            df_display = df.rename(columns={
                **COLONNES_SOCLE,
                'DateProchainRdv': 'RDV prévu',
                'DatePDV': 'Date PDV limite'
            })

            afficher_listing(
                df_display,
                f"RDV ARV — {mois_choisi['label']}",
                f"Patients actifs dont le prochain RDV ARV est prévu en "
                f"{mois_choisi['label']}. À contacter pour confirmation."
            )

    # ── Listings statiques ────────────────────────────────────
    else:
        config = LISTINGS_STATIQUES[choix]
        colonnes_extra = list(config["colonnes_extra"].keys())
        toutes_colonnes = list(COLONNES_SOCLE.keys()) + colonnes_extra
        filtre = config.get("filtre", "")

        sql = f"""
            SELECT {", ".join(toutes_colonnes)}
            FROM {config['table']}
            {filtre}
        """
        df = q(sql)
        df_display = df.rename(columns={**COLONNES_SOCLE, **config["colonnes_extra"]})

        afficher_listing(df_display, choix, config["description"])