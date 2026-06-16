# =============================================================
# KoSanté BI — views/file_active.py
# =============================================================
# Page 3 — Fichier actif
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


def bar_horizontal(df, col_y, col_x, colors, height=280, r=60):
    """Graphique barre horizontal réutilisable"""
    fig = go.Figure(go.Bar(
        y=df[col_y], x=df[col_x],
        orientation='h',
        marker_color=colors[:len(df)],
        text=df[col_x],
        textposition='outside',
        textfont=dict(size=11, color='#232323'),
        cliponaxis=False
    ))
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=r, t=10, b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                   visible=False, range=[0, df[col_x].max() * 1.25]),
        yaxis=dict(showgrid=False,
                   tickfont=dict(size=11, color='#232323'))
    )
    return fig


COLORS_COMM = ['#3D8C7D', '#1F4D3A', '#B33A3A', '#C99A3B', '#2D6E8E', '#8A8275']
COLORS_REGIME = ['#2D6E8E', '#2D6E8E', '#2D6E8E', '#2D6E8E',
                 '#2D6E8E', '#2D6E8E', '#2D6E8E', '#2D6E8E']


def render():
    st.markdown("""
    <div style="margin-bottom:0.5rem;">
        <h2 style="font-size:20px; font-weight:600; color:#1F4D3A; margin:0 0 4px;">
            Fichier actif — Patients suivis à Ko'Khoua
        </h2>
        <p style="font-size:13px; color:#8A8275; margin:0;">
            Patients avec DatePDV ≥ aujourd'hui · Hors décès, transferts et arrêts
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────
    kpis = q("SELECT * FROM kpis_file_active").iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-teal">
            <div class="ks-kpi-label">👥 Fichier actif</div>
            <div class="ks-kpi-value">{int(kpis['total_actifs']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Patients actifs</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-blue">
            <div class="ks-kpi-label">🆕 Nouveaux ce mois</div>
            <div class="ks-kpi-value">{int(kpis['nouveaux_kokhoua']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Ko'Khoua + {int(kpis['transfert_in']):,} Transfert In</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-amber">
            <div class="ks-kpi-label">⏰ RDV manqués</div>
            <div class="ks-kpi-value">{int(kpis['nb_rdv_manque']):,}</div>
            <div class="ks-kpi-sub ks-warning">1 à 27 jours retard</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-coral">
            <div class="ks-kpi-label">🟠 À risque fin de mois</div>
            <div class="ks-kpi-value">{int(kpis['nb_a_risque']):,}</div>
            <div class="ks-kpi-sub ks-down">Deviendront PDV si rien n'est fait</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Ligne 1 : Par communautaire + Régime ARV ──────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="ks-section-label">Fichier actif par communautaire</div>',
            unsafe_allow_html=True
        )
        df_comm = q("""
            SELECT NomCommunautaire, COUNT(*) AS nb
            FROM file_active
            WHERE StatutFile = 'Actif'
            GROUP BY NomCommunautaire
            ORDER BY nb DESC
        """)
        if not df_comm.empty:
            st.plotly_chart(
                bar_horizontal(df_comm, 'NomCommunautaire', 'nb', COLORS_COMM),
                use_container_width=True, config={'displayModeBar': False}
            )

    with col2:
        st.markdown(
            '<div class="ks-section-label">Répartition par régime ARV</div>',
            unsafe_allow_html=True
        )
        df_regime = q("""
            SELECT DernierRegime AS regime, COUNT(*) AS nb
            FROM file_active
            WHERE StatutFile = 'Actif' AND DernierRegime IS NOT NULL
            GROUP BY 1
            ORDER BY nb DESC
            LIMIT 8
        """)
        if not df_regime.empty:
            st.plotly_chart(
                bar_horizontal(df_regime, 'regime', 'nb', COLORS_REGIME),
                use_container_width=True, config={'displayModeBar': False}
            )

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Ligne 2 : PDV fin de mois + RDV manqués par communautaire ──
    col3, col4 = st.columns(2)

    with col3:
        df_risque_comm = q("""
            SELECT NomCommunautaire, COUNT(*) AS nb
            FROM a_risque_fin_mois
            GROUP BY NomCommunautaire
            ORDER BY nb DESC
        """)
        total_risque = int(df_risque_comm['nb'].sum()) if not df_risque_comm.empty else 0

        st.markdown(
            f'<div class="ks-section-label">À risque PDV fin de mois par communautaire'
            f' — Total : {total_risque}</div>',
            unsafe_allow_html=True
        )
        if not df_risque_comm.empty:
            st.plotly_chart(
                bar_horizontal(df_risque_comm, 'NomCommunautaire', 'nb',
                               ['#B33A3A'] * len(df_risque_comm), r=60),
                use_container_width=True, config={'displayModeBar': False}
            )
        else:
            st.markdown(
                '<div class="ks-warning">✅ Aucun patient à risque ce mois</div>',
                unsafe_allow_html=True
            )

    with col4:
        df_rdv_comm = q("""
            SELECT NomCommunautaire, COUNT(*) AS nb
            FROM patients_rdv_manque
            GROUP BY NomCommunautaire
            ORDER BY nb DESC
        """)
        total_rdv = int(df_rdv_comm['nb'].sum()) if not df_rdv_comm.empty else 0

        st.markdown(
            f'<div class="ks-section-label">RDV manqués par communautaire'
            f' — Total : {total_rdv}</div>',
            unsafe_allow_html=True
        )
        if not df_rdv_comm.empty:
            st.plotly_chart(
                bar_horizontal(df_rdv_comm, 'NomCommunautaire', 'nb',
                               ['#C99A3B'] * len(df_rdv_comm), r=60),
                use_container_width=True, config={'displayModeBar': False}
            )
        else:
            st.markdown(
                '<div class="ks-warning">✅ Aucun patient en retard de RDV</div>',
                unsafe_allow_html=True
            )