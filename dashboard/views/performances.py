# =============================================================
# KoSanté BI — views/performances.py
# =============================================================
# Page 4 — Performances cliniques
# Filtre année sur évolution CV + Listings Non Stable / NE
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
    st.markdown("""
    <div style="margin-bottom:0.5rem;">
        <h2 style="font-size:20px; font-weight:600; color:#0D2B45; margin:0 0 4px;">
            Performances cliniques — Fichier actif
        </h2>
        <p style="font-size:13px; color:#6B7A93; margin:0;">
            Charge virale · Stabilité thérapeutique · Calculé sur patients actifs uniquement
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────
    kpis = q("SELECT * FROM kpis_file_active").iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-teal">
            <div class="ks-kpi-label">✅ CV supprimée</div>
            <div class="ks-kpi-value">{float(kpis['pct_cv_supprimee']):.1f}%</div>
            <div class="ks-kpi-sub ks-up">{int(kpis['nb_cv_supprimee']):,} / {int(kpis['nb_cv_evalue']):,} évalués</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-teal">
            <div class="ks-kpi-label">📈 Patients stables</div>
            <div class="ks-kpi-value">{float(kpis['pct_stable']):.1f}%</div>
            <div class="ks-kpi-sub ks-up">{int(kpis['nb_stable']):,} patients</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-coral">
            <div class="ks-kpi-label">⚠️ Non stables</div>
            <div class="ks-kpi-value">{int(kpis['nb_non_stable']):,}</div>
            <div class="ks-kpi-sub ks-down">Suivi renforcé requis</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-amber">
            <div class="ks-kpi-label">🧪 Non évalués (NE)</div>
            <div class="ks-kpi-value">{int(kpis['nb_ne']):,}</div>
            <div class="ks-kpi-sub ks-neutral">Moins de 2 CV disponibles</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Statut CV + Évolution CV 6 mois ──────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="ks-section-label">Statut CV — Fichier actif</div>',
            unsafe_allow_html=True
        )
        df_cv = q("""
            SELECT sc.StatutCV, COUNT(*) AS nb
            FROM StatutCV_Patient sc
            INNER JOIN file_active fa ON sc.NumInc = fa.NumInc
            WHERE fa.StatutFile = 'Actif'
            GROUP BY sc.StatutCV
            ORDER BY nb DESC
        """)
        if not df_cv.empty:
            color_map = {'Stable': '#3D8C7D', 'Non Stable': '#B33A3A', 'NE': '#C99A3B'}
            total = df_cv['nb'].sum()
            df_cv['pct'] = (df_cv['nb'] / total * 100).round(1)
            df_cv['label'] = df_cv.apply(
                lambda r: f"{r['StatutCV']} — {r['nb']:,} ({r['pct']}%)", axis=1
            )
            fig = go.Figure(go.Bar(
                y=df_cv['label'],
                x=df_cv['nb'],
                orientation='h',
                marker_color=[color_map.get(s, '#E3DDD0') for s in df_cv['StatutCV']],
                text=df_cv.apply(lambda r: f"{r['nb']:,}  ({r['pct']}%)", axis=1),
                textposition='outside',
                textfont=dict(size=12, color='#232323'),
                cliponaxis=False
            ))
            fig.update_layout(
                height=220,
                margin=dict(l=0, r=120, t=10, b=10),
                paper_bgcolor='white', plot_bgcolor='white',
                xaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                           visible=False,
                           range=[0, df_cv['nb'].max() * 1.6]),
                yaxis=dict(showgrid=False,
                           tickfont=dict(size=12, color='#232323'))
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col2:
        st.markdown(
            '<div class="ks-section-label">Évolution CV — 6 derniers mois (fichier actif)</div>',
            unsafe_allow_html=True
        )
        df_cv6 = q("""
            SELECT
                strftime(CAST(cv.DatePrelev AS DATE), '%b %Y') AS mois,
                CAST(strftime(CAST(cv.DatePrelev AS DATE), '%Y%m') AS INTEGER) AS ordre,
                COUNT(*) AS total_prelevements,
                COUNT(*) FILTER (WHERE cv.CV_Statut = 'Non supprimée') AS non_supprimees
            FROM TblChargesVirales cv
            WHERE cv.DatePrelev IS NOT NULL
              AND CAST(cv.DatePrelev AS DATE) >= (CURRENT_DATE - INTERVAL '6 months')
            GROUP BY mois, ordre
            ORDER BY ordre ASC
        """)
        if not df_cv6.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_cv6['mois'], y=df_cv6['total_prelevements'],
                name='Total prélèvements',
                marker_color='#E3EDF1',
                text=df_cv6['total_prelevements'],
                textposition='outside',
                textfont=dict(size=9, color='#8A8275')
            ))
            fig2.add_trace(go.Bar(
                x=df_cv6['mois'], y=df_cv6['non_supprimees'],
                name='CV non supprimées',
                marker_color='#B33A3A',
                text=df_cv6['non_supprimees'].apply(lambda v: v if v > 0 else ''),
                textposition='outside',
                textfont=dict(size=9, color='#B33A3A')
            ))
            fig2.update_layout(
                barmode='group', height=300,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor='white', plot_bgcolor='white',
                bargap=0.25, bargroupgap=0.1,
                legend=dict(orientation='h', y=-0.2, font=dict(size=11)),
                xaxis=dict(showgrid=False,
                           tickfont=dict(size=10, color='#6B7A93')),
                yaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                           tickfont=dict(size=10, color='#6B7A93'))
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Aucun prélèvement CV sur les 6 derniers mois")

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Évolution CV avec filtre année ────────────────────────
    col_titre, col_filtre = st.columns([3, 1])
    with col_titre:
        st.markdown(
            '<div class="ks-section-label">Évolution CV supprimée par mois — Fichier actif</div>',
            unsafe_allow_html=True
        )
    with col_filtre:
        annees_df = q("""
            SELECT DISTINCT EXTRACT(YEAR FROM CAST(cv.DatePrelev AS DATE))::INTEGER AS annee
            FROM TblChargesVirales cv
            INNER JOIN file_active fa ON cv.Patient = fa.NumInc
            WHERE fa.StatutFile = 'Actif' AND cv.DatePrelev IS NOT NULL
            ORDER BY annee DESC
        """)
        options = ["Depuis le début"] + [str(int(a)) for a in annees_df['annee'].tolist()]
        annee_choisie = st.selectbox("Période", options, label_visibility="collapsed", key="perf_annee")

    if annee_choisie == "Depuis le début":
        filtre_annee = "AND CAST(cv.DatePrelev AS DATE) >= DATE '2020-01-01'"
    else:
        filtre_annee = f"AND EXTRACT(YEAR FROM CAST(cv.DatePrelev AS DATE)) = {annee_choisie}"

    df_cv_evo = q(f"""
        SELECT
            strftime(CAST(cv.DatePrelev AS DATE), '%Y-%m') AS mois,
            COUNT(*) FILTER (WHERE cv.CV_Statut='Supprimée') AS supprimees,
            COUNT(*) FILTER (WHERE cv.CV_Statut != 'Non renseigné') AS evaluees
        FROM TblChargesVirales cv
        INNER JOIN file_active fa ON cv.Patient = fa.NumInc
        WHERE fa.StatutFile = 'Actif'
          AND cv.DatePrelev IS NOT NULL {filtre_annee}
        GROUP BY mois
        ORDER BY mois
    """)

    if not df_cv_evo.empty:
        df_cv_evo['pct'] = (
            df_cv_evo['supprimees'] / df_cv_evo['evaluees'].replace(0, 1) * 100
        ).round(1)

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_cv_evo['mois'], y=df_cv_evo['pct'],
            mode='lines+markers',
            line=dict(color='#0E8C6A', width=2),
            marker=dict(size=5, color='#0E8C6A'),
            fill='tozeroy', fillcolor='rgba(14,140,106,0.08)'
        ))
        fig3.add_hline(y=95, line_dash="dash", line_color="#E8930A",
                       annotation_text="Objectif 95%", annotation_position="right")
        fig3.update_layout(
            height=250, margin=dict(l=0, r=60, t=10, b=0),
            paper_bgcolor='white', plot_bgcolor='white',
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color='#6B7A93')),
            yaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                       tickfont=dict(size=10, color='#6B7A93'), range=[0, 105]),
            showlegend=False
        )
        st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("Aucune donnée pour cette période")

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Listings Non Stables / NE ─────────────────────────────
    tab1, tab2 = st.tabs([
        f"⚠️ Non Stables ({int(kpis['nb_non_stable'])})",
        f"🧪 Non Évalués — NE ({int(kpis['nb_ne'])})"
    ])

    with tab1:
        df_ns = q("""
            SELECT
                NumInc, NumNational, Sexe_label, Age, Tel, NomCommunautaire,
                DernierRegime, derniere_cv, date_derniere_cv,
                avant_derniere_cv, date_avant_derniere_cv
            FROM patients_non_stables
        """)
        if df_ns.empty:
            st.markdown('<div class="ks-warning">✅ Aucun patient non stable</div>',
                        unsafe_allow_html=True)
        else:
            df_display = df_ns.rename(columns={
                **COLONNES_SOCLE,
                'derniere_cv': 'Dernière CV',
                'date_derniere_cv': 'Date dernière CV',
                'avant_derniere_cv': 'CV précédente',
                'date_avant_derniere_cv': 'Date CV précédente'
            })
            st.dataframe(df_display, use_container_width=True, hide_index=True, height=320)
            st.caption(f"📋 {len(df_ns)} patients — voir le menu **Listing** pour l'impression")

    with tab2:
        df_ne = q("""
            SELECT
                NumInc, NumNational, Sexe_label, Age, Tel, NomCommunautaire,
                DernierRegime, nb_cv_disponibles, derniere_date_cv
            FROM patients_non_evalues
        """)
        if df_ne.empty:
            st.markdown('<div class="ks-warning">✅ Aucun patient non évalué</div>',
                        unsafe_allow_html=True)
        else:
            df_display2 = df_ne.rename(columns={
                **COLONNES_SOCLE,
                'nb_cv_disponibles': 'Nb CV disponibles',
                'derniere_date_cv': 'Date dernière CV'
            })
            st.dataframe(df_display2, use_container_width=True, hide_index=True, height=320)
            st.caption(f"📋 {len(df_ne)} patients — voir le menu **Listing** pour l'impression")