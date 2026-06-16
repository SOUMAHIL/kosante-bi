# =============================================================
# KoSanté BI — views/vue_ensemble.py
# =============================================================
# Page 1 — Vue d'ensemble
# KPIs globaux + Cascade 95-95-95 + Attrition + Évolution
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


# =============================================================
# COMPOSANTS UI
# =============================================================
def kpi_card(label, value, sub="", color="teal", icon=""):
    st.markdown(f"""
    <div class="ks-kpi-card ks-kpi-{color}">
        <div class="ks-kpi-label">{icon} {label}</div>
        <div class="ks-kpi-value">{value}</div>
        <div class="ks-kpi-sub ks-neutral">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def cascade_bar(label, valeur, total, pct, couleur, objectif=95, afficher_pct=True):
    pct_val = float(pct) if pct is not None else 0
    if afficher_pct:
        atteint = "✅" if pct_val >= objectif else "⚠️"
        droite = (
            f"{atteint} {pct_val}% "
            f"<span style='font-size:11px; color:#6B7A93; font-weight:400;'>"
            f"({valeur:,} / {total:,})</span>"
        )
        largeur = min(pct_val, 100)
    else:
        droite = f"<span style='font-size:13px; font-weight:600; color:{couleur};'>{valeur:,}</span>"
        largeur = 100

    st.markdown(f"""
    <div style="margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between;
             align-items:center; margin-bottom:5px;">
            <span style="font-size:13px; font-weight:500; color:#1a2332;">{label}</span>
            <span style="font-size:13px; font-weight:600; color:{couleur};">{droite}</span>
        </div>
        <div class="ks-cascade-track">
            <div class="ks-cascade-fill" style="width:{largeur}%; background:{couleur};"></div>
        </div>
        {"<div style='display:flex; justify-content:space-between; margin-top:3px;'>"
         "<span style='font-size:10px; color:#6B7A93;'>0%</span>"
         f"<span style='font-size:10px; color:#6B7A93;'>Objectif : {objectif}%</span>"
         "<span style='font-size:10px; color:#6B7A93;'>100%</span></div>"
         if afficher_pct else ""}
    </div>
    """, unsafe_allow_html=True)


# =============================================================
# GRAPHIQUES
# =============================================================
def graphique_evolution_file_active():
    df = q("""
        SELECT
            strftime(CAST(DateAdmi AS DATE), '%Y-%m') AS mois,
            COUNT(*) AS nouveaux
        FROM TblDossPatient
        WHERE DateAdmi IS NOT NULL
          AND CAST(DateAdmi AS DATE) >= (CURRENT_DATE - INTERVAL '3 years')
        GROUP BY mois
        ORDER BY mois
    """)
    if df.empty:
        return None

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['mois'],
        y=df['nouveaux'],
        marker_color='#3D8C7D',
        marker_opacity=0.85,
        text=df['nouveaux'],
        textposition='outside',
        textfont=dict(size=9, color='#8A8275'),
        hovertemplate='%{x}<br>%{y} nouveaux<extra></extra>'
    ))
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=25, b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=10, color='#6B7A93'),
            tickangle=-30
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#EEF2F7',
            tickfont=dict(size=10, color='#6B7A93'),
            range=[0, df['nouveaux'].max() * 1.25]
        ),
        showlegend=False,
        bargap=0.35
    )
    return fig


def graphique_repartition_sexe():
    df = q("""
        SELECT COALESCE(Sexe_label, 'Inconnu') AS sexe, COUNT(*) AS nb
        FROM file_active
        WHERE StatutFile = 'Actif'
        GROUP BY sexe
    """)
    if df.empty:
        return None

    colors = {'M': '#1A6FB5', 'F': '#0E8C6A', 'Inconnu': '#DDE4EE'}
    fig = go.Figure(go.Pie(
        labels=df['sexe'], values=df['nb'], hole=0.6,
        marker_colors=[colors.get(s, '#DDE4EE') for s in df['sexe']],
        textinfo='percent', textfont_size=12
    ))
    fig.update_layout(
        height=230,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='white',
        showlegend=True,
        legend=dict(orientation='v', font=dict(size=11), x=1, y=0.5)
    )
    return fig


def graphique_statut_cv():
    df = q("""
        SELECT sc.StatutCV, COUNT(*) AS nb
        FROM StatutCV_Patient sc
        INNER JOIN file_active fa ON sc.NumInc = fa.NumInc
        WHERE fa.StatutFile = 'Actif'
        GROUP BY sc.StatutCV
    """)
    if df.empty:
        return None

    color_map = {'Stable': '#0E8C6A', 'Non Stable': '#D94F3D', 'NE': '#DDE4EE'}
    fig = go.Figure(go.Bar(
        x=df['StatutCV'], y=df['nb'],
        marker_color=[color_map.get(s, '#DDE4EE') for s in df['StatutCV']],
        text=df['nb'], textposition='outside',
        textfont=dict(size=12, color='#1a2332')
    ))
    fig.update_layout(
        height=230,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#EEF2F7', visible=False, range=[0, df['nb'].max()*1.25]),
        showlegend=False
    )
    return fig


def graphique_attrition(kpis):
    """Répartition de l'attrition par catégorie"""
    categories = ['Perdus de vue', 'Transferts', 'Arrêts volontaires', 'Décès']
    valeurs = [
        int(kpis['nb_pdv']),
        int(kpis['nb_transfert']),
        int(kpis['nb_arret_vol']),
        int(kpis['nb_deces'])
    ]
    colors = ['#D94F3D', '#1A6FB5', '#E8930A', '#6B7A93']

    fig = go.Figure(go.Bar(
        x=valeurs, y=categories, orientation='h',
        marker_color=colors,
        text=valeurs, textposition='outside',
        textfont=dict(size=12, color='#1a2332')
    ))
    fig.update_layout(
        height=230,
        margin=dict(l=0, r=40, t=10, b=0),
        paper_bgcolor='white', plot_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#EEF2F7', visible=False,
                   range=[0, max(valeurs)*1.2]),
        yaxis=dict(showgrid=False, tickfont=dict(size=12, color='#1a2332'))
    )
    return fig


# =============================================================
# PAGE PRINCIPALE
# =============================================================
def render():

    # ── En-tête ──────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <h2 style="font-size:20px; font-weight:600; color:#0D2B45; margin:0 0 4px;">
            Tableau de bord — Suivi PVVIH
        </h2>
        <p style="font-size:13px; color:#6B7A93; margin:0;">
            Ko'Khoua ONG · Abidjan, Côte d'Ivoire · Données au jour
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Chargement données ───────────────────────────────────
    try:
        kpis = q("SELECT * FROM kpis_file_active").iloc[0]
        cascade = q("SELECT * FROM cascade_95_95_95").iloc[0]
    except Exception as e:
        st.error(f"Erreur chargement données : {e}")
        return

    # ── KPIs — ligne 1 ────────────────────────────────────────
    st.markdown('<div class="ks-section-label">Indicateurs clés — File active</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("File active", f"{int(kpis['total_actifs']):,}",
                 "patients suivis aujourd'hui", "teal", "👥")
    with c2:
        kpi_card("CV supprimée", f"{float(kpis['pct_cv_supprimee']):.1f}%",
                 f"{int(kpis['nb_cv_supprimee']):,} sur {int(kpis['nb_cv_evalue']):,} évalués",
                 "teal", "✅")
    with c3:
        kpi_card("Patients stables", f"{float(kpis['pct_stable']):.1f}%",
                 f"{int(kpis['nb_stable']):,} sur {int(kpis['nb_stable'])+int(kpis['nb_non_stable']):,} évalués",
                 "teal", "📈")

    # ── KPIs — ligne 2 ────────────────────────────────────────
    c4, c5, c6 = st.columns(3)
    with c4:
        kpi_card("RDV manqués", f"{int(kpis['nb_rdv_manque']):,}",
                 "1 à 27 jours de retard", "amber", "⏰")
    with c5:
        kpi_card("À risque fin de mois", f"{int(kpis['nb_a_risque']):,}",
                 "deviendront PDV avant fin du mois", "amber", "🟠")
    with c6:
        kpi_card("Attrition totale", f"{int(kpis['nb_attrition']):,}",
                 "PDV + Transferts + Arrêts + Décès", "coral", "⚠️")

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Cascade 95-95-95 ─────────────────────────────────────
    col_casc, col_charts = st.columns([1, 1])

    with col_casc:
        st.markdown(
            '<div class="ks-section-label">Cascade 95-95-95 — Standard ONUSIDA</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<p style="font-size:12px; color:#6B7A93; margin-bottom:16px;">'
            "Continuum de soins VIH · Ko'Khoua · Depuis le début</p>",
            unsafe_allow_html=True
        )

        cascade_bar(
            "① Dépistés positifs (CDV)",
            int(cascade['nb_positifs']),
            int(cascade['nb_tests']),
            None, "#1A6FB5",
            afficher_pct=False
        )
        cascade_bar(
            "③ Charge virale supprimée — file active",
            int(cascade['nb_supprimee']),
            int(cascade['nb_evalue']),
            float(cascade['pct_cv_supprimee']),
            "#0E8C6A", objectif=95
        )

        st.markdown(
            '<p style="font-size:11px; color:#6B7A93; margin-top:8px;">'
            'ℹ️ Le 2ᵉ indicateur (mise sous ARV) est suivi via le '
            '<strong>taux de rétention ARV par cohorte annuelle</strong> '
            '— voir page Attrition.</p>',
            unsafe_allow_html=True
        )

    with col_charts:
        st.markdown('<div class="ks-section-label">Répartition file active</div>',
                     unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["Genre", "Statut CV", "Attrition"])
        with tab1:
            fig_sexe = graphique_repartition_sexe()
            if fig_sexe:
                st.plotly_chart(fig_sexe, use_container_width=True,
                                 config={'displayModeBar': False})
        with tab2:
            fig_cv = graphique_statut_cv()
            if fig_cv:
                st.plotly_chart(fig_cv, use_container_width=True,
                                 config={'displayModeBar': False})
        with tab3:
            fig_attr = graphique_attrition(kpis)
            if fig_attr:
                st.plotly_chart(fig_attr, use_container_width=True,
                                 config={'displayModeBar': False})

    st.markdown('<hr class="ks-divider">', unsafe_allow_html=True)

    # ── Évolution nouveaux patients ───────────────────────────
    st.markdown(
        '<div class="ks-section-label">Nouveaux patients par mois — 3 dernières années</div>',
        unsafe_allow_html=True
    )
    fig_evo = graphique_evolution_file_active()
    if fig_evo:
        st.plotly_chart(fig_evo, use_container_width=True,
                         config={'displayModeBar': False})