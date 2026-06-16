# =============================================================
# KoSanté BI — views/depistage.py
# =============================================================
# Page 2 — Dépistage CDV
# Avec filtre Année · Indépendant de la file active
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


def render():
    # ── En-tête + filtre année ─────────────────────────────────
    col_titre, col_filtre = st.columns([3, 1])

    with col_titre:
        st.markdown("""
        <div style="margin-bottom:0.5rem;">
            <h2 style="font-size:20px; font-weight:600; color:#0D2B45; margin:0 0 4px;">
                Dépistage — Conseil et Dépistage Volontaire (CDV)
            </h2>
            <p style="font-size:13px; color:#6B7A93; margin:0;">
                Registre CDV Ko'Khoua · Indépendant de la file active
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col_filtre:
        annees_df = q("""
            SELECT DISTINCT EXTRACT(YEAR FROM CAST(DateVisite AS DATE))::INTEGER AS annee
            FROM TblRegistreCDV
            WHERE DateVisite IS NOT NULL
            ORDER BY annee DESC
        """)
        options = ["Depuis le début"] + [str(int(a)) for a in annees_df['annee'].tolist()]
        annee_choisie = st.selectbox("Période", options, label_visibility="collapsed")

    # ── Filtre SQL ────────────────────────────────────────────
    if annee_choisie == "Depuis le début":
        filtre_annee = ""
        label_periode = "Depuis le début"
    else:
        filtre_annee = f"AND EXTRACT(YEAR FROM CAST(DateVisite AS DATE)) = {annee_choisie}"
        label_periode = annee_choisie

    st.markdown(
        f'<p style="font-size:11px; color:#6B7A93; margin:-4px 0 8px;">'
        f'📅 Période sélectionnée : <strong>{label_periode}</strong></p>',
        unsafe_allow_html=True
    )

    # ── KPIs ─────────────────────────────────────────────────
    stats = q(f"""
        SELECT
            COUNT(*) AS nb_total,
            COUNT(*) FILTER (WHERE Resultat_simple='Positif') AS nb_positifs,
            COUNT(*) FILTER (WHERE Resultat_simple='Négatif') AS nb_negatifs,
            ROUND(COUNT(*) FILTER (WHERE Resultat_simple='Positif') * 100.0
                / NULLIF(COUNT(*) FILTER (
                    WHERE Resultat_simple IN ('Positif','Négatif')), 0), 1
            ) AS taux_positivite
        FROM TblRegistreCDV
        WHERE DateVisite IS NOT NULL {filtre_annee}
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-blue">
            <div class="ks-kpi-label">🔬 Tests réalisés</div>
            <div class="ks-kpi-value">{int(stats['nb_total']):,}</div>
            <div class="ks-kpi-sub ks-neutral">{label_periode}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-coral">
            <div class="ks-kpi-label">🔴 Résultats positifs</div>
            <div class="ks-kpi-value">{int(stats['nb_positifs']):,}</div>
            <div class="ks-kpi-sub ks-down">Séropositifs détectés</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-teal">
            <div class="ks-kpi-label">🟢 Résultats négatifs</div>
            <div class="ks-kpi-value">{int(stats['nb_negatifs']):,}</div>
            <div class="ks-kpi-sub ks-up">Séronégatifs</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        taux = stats['taux_positivite']
        st.markdown(f"""
        <div class="ks-kpi-card ks-kpi-amber">
            <div class="ks-kpi-label">📊 Taux de positivité</div>
            <div class="ks-kpi-value">{taux if taux is not None else 0}%</div>
            <div class="ks-kpi-sub ks-neutral">Parmi les tests évalués</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Évolution mensuelle + Stades ──────────────────────────
    col1, col2 = st.columns([1.6, 1])

    with col1:
        st.markdown(
            '<div class="ks-section-label">Évolution mensuelle des dépistages</div>',
            unsafe_allow_html=True
        )
        df_evo = q(f"""
            SELECT
                strftime(CAST(DateVisite AS DATE), '%Y-%m') AS mois,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE Resultat_simple='Positif') AS positifs
            FROM TblRegistreCDV
            WHERE DateVisite IS NOT NULL {filtre_annee}
            GROUP BY mois
            ORDER BY mois
        """)

        if not df_evo.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_evo['mois'], y=df_evo['total'],
                name='Total tests', marker_color='#E3EDF1',
                text=df_evo['total'], textposition='outside',
                textfont=dict(size=9, color='#8A8275')
            ))
            fig.add_trace(go.Bar(
                x=df_evo['mois'], y=df_evo['positifs'],
                name='Positifs', marker_color='#B33A3A',
                text=df_evo['positifs'].apply(lambda v: v if v > 0 else ''),
                textposition='outside',
                textfont=dict(size=9, color='#B33A3A')
            ))
            fig.update_layout(
                barmode='group', height=300,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor='white', plot_bgcolor='white',
                bargap=0.25, bargroupgap=0.1,
                legend=dict(orientation='h', y=-0.2),
                xaxis=dict(showgrid=False,
                           tickfont=dict(size=10, color='#6B7A93')),
                yaxis=dict(showgrid=True, gridcolor='#EEF2F7',
                           tickfont=dict(size=10, color='#6B7A93'))
            )
            st.plotly_chart(fig, use_container_width=True,
                            config={'displayModeBar': False})
        else:
            st.info("Aucune donnée pour cette période")

    with col2:
        st.markdown(
            '<div class="ks-section-label">Positifs par stade</div>',
            unsafe_allow_html=True
        )
        df_stades = q(f"""
            SELECT
                Resultat_label AS stade,
                COUNT(*) AS nb
            FROM TblRegistreCDV
            WHERE Resultat_simple = 'Positif' {filtre_annee}
            GROUP BY 1
            ORDER BY nb DESC
        """)

        if not df_stades.empty:
            colors = ['#D94F3D', '#E8930A', '#1A6FB5', '#0E8C6A', '#0D2B45']
            fig2 = go.Figure(go.Bar(
                x=df_stades['nb'], y=df_stades['stade'],
                orientation='h',
                marker_color=colors[:len(df_stades)],
                text=df_stades['nb'], textposition='outside'
            ))
            fig2.update_layout(
                height=280,
                margin=dict(l=0, r=40, t=30, b=0),
                paper_bgcolor='white', plot_bgcolor='white',
                xaxis=dict(showgrid=True, gridcolor='#EEF2F7', visible=False),
                yaxis=dict(showgrid=False,
                           tickfont=dict(size=11, color='#1a2332'))
            )
            st.plotly_chart(fig2, use_container_width=True,
                            config={'displayModeBar': False})
        else:
            st.info("Aucun cas positif pour cette période")

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Répartition genre + âge ────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            '<div class="ks-section-label">Répartition par genre</div>',
            unsafe_allow_html=True
        )
        df_sexe = q(f"""
            SELECT
                CASE Sexe WHEN 1 THEN 'Masculin'
                          WHEN 2 THEN 'Féminin'
                          ELSE 'Inconnu' END AS sexe,
                COUNT(*) AS nb
            FROM TblRegistreCDV
            WHERE DateVisite IS NOT NULL {filtre_annee}
            GROUP BY 1
        """)
        if not df_sexe.empty:
            colors_sexe = {'Masculin': '#1A6FB5', 'Féminin': '#0E8C6A', 'Inconnu': '#DDE4EE'}
            fig3 = go.Figure(go.Pie(
                labels=df_sexe['sexe'], values=df_sexe['nb'], hole=0.55,
                marker_colors=[colors_sexe.get(s, '#DDE4EE') for s in df_sexe['sexe']],
                textinfo='percent'
            ))
            fig3.update_layout(height=240,
                               margin=dict(l=0, r=0, t=10, b=0),
                               paper_bgcolor='white',
                               legend=dict(font=dict(size=11)))
            st.plotly_chart(fig3, use_container_width=True,
                            config={'displayModeBar': False})

    with col4:
        st.markdown(
            '<div class="ks-section-label">Répartition par tranche d\'âge</div>',
            unsafe_allow_html=True
        )
        df_age = q(f"""
            SELECT
                CASE
                    WHEN Age IS NULL THEN 'Non renseigné'
                    WHEN Age < 15  THEN '< 15 ans'
                    WHEN Age < 25  THEN '15-24 ans'
                    WHEN Age < 35  THEN '25-34 ans'
                    WHEN Age < 45  THEN '35-44 ans'
                    WHEN Age < 60  THEN '45-59 ans'
                    ELSE '60 ans et +'
                END AS tranche,
                COUNT(*) AS nb
            FROM TblRegistreCDV
            WHERE DateVisite IS NOT NULL {filtre_annee}
            GROUP BY 1
        """)
        if not df_age.empty:
            ordre = ['< 15 ans', '15-24 ans', '25-34 ans', '35-44 ans',
                     '45-59 ans', '60 ans et +', 'Non renseigné']
            df_age['ordre'] = df_age['tranche'].apply(
                lambda x: ordre.index(x) if x in ordre else 99
            )
            df_age = df_age.sort_values('ordre')

            fig4 = go.Figure(go.Bar(
                x=df_age['tranche'], y=df_age['nb'],
                marker_color='#1A6FB5', marker_opacity=0.8,
                text=df_age['nb'], textposition='outside'
            ))
            fig4.update_layout(
                height=240,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor='white', plot_bgcolor='white',
                xaxis=dict(showgrid=False,
                           tickfont=dict(size=10, color='#1a2332')),
                yaxis=dict(showgrid=True, gridcolor='#EEF2F7', visible=False)
            )
            st.plotly_chart(fig4, use_container_width=True,
                            config={'displayModeBar': False})