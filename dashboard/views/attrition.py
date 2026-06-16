# =============================================================
# KoSanté BI — views/attrition.py
# =============================================================
# Page 5 — Attrition (nouveau)
# Perdus de vue + Transferts + Arrêts volontaires + Décès
# =============================================================

import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))


def get_conn():
    from app import get_connection
    return get_connection()


def q(sql):
    from app import query
    return query(get_conn(), sql)


COLONNES_SOCLE = {
    'NumInc': 'N° Local',
    'NumNational': 'N° National',
    'Sexe_label': 'Sexe',
    'Age': 'Âge',
    'Tel': 'Téléphone',
    'NomCommunautaire': 'Communautaire',
    'DernierRegime': 'Régime ARV',
}


def render():
    # ── En-tête + filtre période ─────────────────────────────
    col_titre, col_filtre = st.columns([3, 1])
    with col_titre:
        st.markdown("""
        <div style="margin-bottom:0.5rem;">
            <h2 style="font-size:20px; font-weight:600; color:#1F4D3A; margin:0 0 4px;">
                Attrition — Sorties de la file active
            </h2>
            <p style="font-size:13px; color:#8A8275; margin:0;">
                Perdus de vue · Transferts · Arrêts volontaires · Décès
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col_filtre:
        periode = st.selectbox(
            "Période",
            ["12 derniers mois", "6 derniers mois", "3 derniers mois", "Tout l'historique"],
            label_visibility="collapsed",
            key="attr_periode"
        )

    # ── Filtre SQL selon période ──────────────────────────────
    def mk_filtre(mois):
        return f"""AND (
            TRY_CAST(TransfDate AS DATE) >= (CURRENT_DATE - INTERVAL '{mois} months')
            OR TRY_CAST(DecesDate AS DATE) >= (CURRENT_DATE - INTERVAL '{mois} months')
            OR TRY_CAST(DatePDV AS DATE) >= (CURRENT_DATE - INTERVAL '{mois} months')
        )"""

    if periode == "3 derniers mois":
        filtre_date = mk_filtre(3)
        label_periode = "3 derniers mois"
    elif periode == "6 derniers mois":
        filtre_date = mk_filtre(6)
        label_periode = "6 derniers mois"
    elif periode == "12 derniers mois":
        filtre_date = mk_filtre(12)
        label_periode = "12 derniers mois"
    else:
        filtre_date = ""
        label_periode = "Tout l'historique"

    # ── KPIs dynamiques selon filtre ─────────────────────────
    df_attr = q(f"""
        SELECT
            COUNT(*) AS nb_attrition,
            COUNT(*) FILTER (WHERE categorie_attrition = 'Perdu de vue') AS nb_pdv,
            COUNT(*) FILTER (WHERE categorie_attrition = 'Transfert') AS nb_transfert,
            COUNT(*) FILTER (WHERE categorie_attrition = 'Arrêt volontaire') AS nb_arret_vol,
            COUNT(*) FILTER (WHERE categorie_attrition = 'Décès') AS nb_deces
        FROM attrition
        WHERE categorie_attrition IS NOT NULL {filtre_date}
    """).iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-navy">
            <div class="ks-kpi-label">📊 Attrition — {label_periode}</div>
            <div class="ks-kpi-value">{int(df_attr['nb_attrition']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Toutes catégories</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-coral">
            <div class="ks-kpi-label">⚠️ Perdus de vue</div>
            <div class="ks-kpi-value">{int(df_attr['nb_pdv']):,}</div>
            <div class="ks-kpi-sub ks-down">≥ 28 jours sans venir</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-blue">
            <div class="ks-kpi-label">🔄 Transferts</div>
            <div class="ks-kpi-value">{int(df_attr['nb_transfert']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Vers autre centre</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-amber">
            <div class="ks-kpi-label">🚫 Arrêts volontaires</div>
            <div class="ks-kpi-value">{int(df_attr['nb_arret_vol']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Refus / Arrêt</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-navy">
            <div class="ks-kpi-label">⚰️ Décès</div>
            <div class="ks-kpi-value">{int(df_attr['nb_deces']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Toute la cohorte</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Répartition + Rétention ARV ───────────────────────────
    col1, col2 = st.columns([1, 1.4])

    with col1:
        st.markdown(
            f'<div class="ks-section-label">Répartition de l\'attrition — {label_periode}</div>',
            unsafe_allow_html=True
        )
        categories = ['Perdus de vue', 'Transferts', 'Arrêts volontaires', 'Décès']
        valeurs = [int(df_attr['nb_pdv']), int(df_attr['nb_transfert']),
                   int(df_attr['nb_arret_vol']), int(df_attr['nb_deces'])]
        colors = ['#B33A3A', '#2D6E8E', '#C99A3B', '#1F4D3A']
        total = sum(valeurs)

        fig = go.Figure(go.Bar(
            y=categories,
            x=valeurs,
            orientation='h',
            marker_color=colors,
            text=[f"{v:,}  ({v/total*100:.1f}%)" if total > 0 else "0" for v in valeurs],
            textposition='outside',
            textfont=dict(size=11, color='#232323'),
            cliponaxis=False
        ))
        fig.update_layout(
            height=250,
            margin=dict(l=0, r=130, t=10, b=10),
            paper_bgcolor='white', plot_bgcolor='white',
            xaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                       visible=False,
                       range=[0, max(valeurs) * 1.6] if valeurs else [0, 1]),
            yaxis=dict(showgrid=False,
                       tickfont=dict(size=12, color='#232323'))
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col2:
        st.markdown(
            '<div class="ks-section-label">Taux de rétention ARV — 6 dernières cohortes</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p style="font-size:11px; color:#8A8275; margin-top:-4px;">'
            'Parmi les patients mis sous ARV une année donnée, '
            'combien sont encore actifs aujourd\'hui ?</p>',
            unsafe_allow_html=True
        )

        df_ret = q("""
            SELECT annee, nb_mis_sous_arv, nb_encore_actifs, taux_retention
            FROM vue_retention_arv
            WHERE annee IS NOT NULL
              AND annee >= (EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 5)
            ORDER BY annee ASC
        """)

        if not df_ret.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_ret['annee'], y=df_ret['nb_mis_sous_arv'],
                name='Mis sous ARV', marker_color='#E3EDF1',
                text=df_ret['nb_mis_sous_arv'], textposition='outside',
                textfont=dict(size=10, color='#8A8275')
            ))
            fig2.add_trace(go.Scatter(
                x=df_ret['annee'], y=df_ret['taux_retention'],
                name='Taux de rétention (%)',
                mode='lines+markers+text',
                line=dict(color='#3D8C7D', width=2),
                marker=dict(size=6),
                text=df_ret['taux_retention'].apply(lambda v: f'{v}%'),
                textposition='top center',
                textfont=dict(size=10, color='#3D8C7D'),
                yaxis='y2'
            ))
            fig2.update_layout(
                height=300,
                margin=dict(l=0, r=40, t=30, b=0),
                paper_bgcolor='white', plot_bgcolor='white',
                xaxis=dict(showgrid=False, tickfont=dict(size=11, color='#232323'), type='category'),
                yaxis=dict(title='Nb patients', showgrid=True, gridcolor='#EEF2F7',
                           tickfont=dict(size=10, color='#8A8275')),
                yaxis2=dict(title='Taux %', overlaying='y', side='right',
                            range=[0, 115], tickfont=dict(size=10, color='#3D8C7D')),
                legend=dict(orientation='h', y=-0.25),
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Listing Perdus de vue 3/6 mois ────────────────────────
    col_titre, col_filtre = st.columns([3, 1])
    with col_titre:
        st.markdown(
            '<div class="ks-section-label">Listing — Patients perdus de vue récents</div>',
            unsafe_allow_html=True
        )
    with col_filtre:
        periode = st.selectbox(
            "Période", ["3 derniers mois", "6 derniers mois", "Tous"],
            label_visibility="collapsed", key="pdv_periode"
        )

    if periode == "3 derniers mois":
        max_jours = 90
    elif periode == "6 derniers mois":
        max_jours = 180
    else:
        max_jours = 999999

    df_pdv = q(f"""
        SELECT
            NumInc, NumNational, Sexe_label, Age, Tel, NomCommunautaire,
            DernierRegime, DatePDV, jours_depuis_pdv
        FROM pdv_listing
        WHERE jours_depuis_pdv <= {max_jours}
        ORDER BY jours_depuis_pdv ASC
    """)

    if df_pdv.empty:
        st.markdown('<div class="ks-warning">✅ Aucun perdu de vue sur cette période</div>',
                    unsafe_allow_html=True)
    else:
        df_display = df_pdv.rename(columns={
            **COLONNES_SOCLE,
            'DatePDV': 'Devenu PDV le',
            'jours_depuis_pdv': 'Jours depuis PDV'
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True, height=350)
        st.caption(f"📋 {len(df_pdv)} patients — voir le menu **Listing** pour l'impression")