# =============================================================
# KoSanté BI — app.py
# =============================================================
# RÔLE : Point d'entrée principal du dashboard Streamlit
#        Navigation entre les 4 pages
#
# USAGE :
#   streamlit run dashboard/app.py
# =============================================================

import streamlit as st
from pathlib import Path
import sys

# Ajout du dossier racine au path
sys.path.append(str(Path(__file__).parent.parent))

# =============================================================
# CONFIGURATION GLOBALE
# =============================================================
st.set_page_config(
    page_title="KoSanté BI — Ko'Khoua",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================
# STYLES GLOBAUX
# =============================================================
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
    /* ── Palette KoSanté — Carnet de suivi ── */
    :root {
        --ks-paper:      #F6F3EC;
        --ks-paper-2:    #EFEAE0;
        --ks-ink:        #232323;
        --ks-muted:      #8A8275;
        --ks-line:       #E3DDD0;
        --ks-forest:     #1F4D3A;
        --ks-forest-2:   #2B6650;
        --ks-gold:       #C99A3B;
        --ks-gold-light: #F7ECD3;
        --ks-stamp:      #B33A3A;
        --ks-stamp-light:#F6E2DF;
        --ks-teal:       #3D8C7D;
        --ks-teal-light: #E2EFEB;
        --ks-blue:       #2D6E8E;

        /* Compat anciens noms utilisés dans views/*.py */
        --ks-navy:       #1F4D3A;
        --ks-amber:      #C99A3B;
        --ks-amber-light:#F7ECD3;
        --ks-coral:      #B33A3A;
        --ks-coral-light:#F6E2DF;
        --ks-blue-light: #E3EDF1;
        --ks-bg:         #F6F3EC;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Sidebar — carnet vert, navigation type onglets de dossier ── */
    [data-testid="stSidebar"] {
        background-color: var(--ks-forest) !important;
        border-right: 1px solid rgba(0,0,0,0.15);
    }
    [data-testid="stSidebar"] * {
        color: rgba(255,255,255,0.82) !important;
        font-family: 'Inter', sans-serif;
    }

    /* ── Navigation — boutons pleine largeur, sans puce ── */
    [data-testid="stSidebar"] .stButton {
        width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: rgba(255,255,255,0.78) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 6px !important;
        border-top-left-radius: 0 !important;
        border-bottom-left-radius: 0 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        padding: 8px 12px !important;
        width: 100% !important;
        box-shadow: none !important;
        transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
        display: flex !important;
        flex-direction: row !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebar"] .stButton > button > div {
        width: 100% !important;
        justify-content: flex-start !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .stButton > button p {
        font-family: 'Inter', sans-serif !important;
        text-align: left !important;
        width: 100% !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.07) !important;
        border-left-color: rgba(201,154,59,0.5) !important;
        color: #fff !important;
    }
    [data-testid="stSidebar"] .stButton > button:focus:not(:active) {
        background: rgba(255,255,255,0.07) !important;
        color: #fff !important;
    }
    /* Item actif */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: rgba(255,255,255,0.10) !important;
        border-left-color: var(--ks-gold) !important;
        color: #fff !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: rgba(255,255,255,0.13) !important;
    }

    /* ── Background principal — papier ── */
    .stApp {
        background-color: var(--ks-paper);
    }
    .main .block-container {
        background-color: var(--ks-paper);
        padding-top: 0rem !important;
        padding-bottom: 1rem;
        max-width: 1400px;
    }
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.4rem;
    }
    div.element-container {
        margin-bottom: 0 !important;
    }
    div[data-testid="stAppViewBlockContainer"],
    div[data-testid="stMainBlockContainer"] {
        padding-top: 1rem !important;
    }

    /* ── Masquer éléments Streamlit par défaut ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {
        background: transparent;
        height: 1rem;
    }
    [data-testid="stToolbar"] {visibility: hidden;}

    /* ── Désactiver le repli de la sidebar ── */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"],
    button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* ── Compacter la sidebar (logo, nav, bouton remontent) ── */
    [data-testid="stSidebar"] {
        padding-top: 0 !important;
    }
    [data-testid="stSidebar"] > div {
        padding-top: 0 !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
        padding-top: 0.2rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.15rem !important;
    }
    [data-testid="stSidebar"] div.element-container {
        margin-bottom: 0 !important;
    }
    [data-testid="stSidebar"] hr {
        margin: 0.5rem 0 !important;
        border-color: rgba(255,255,255,0.12) !important;
    }
    /* Bouton "Rafraîchir" — distinct de la nav (plein, doré au hover) */
    [data-testid="stSidebar"] div[data-testid="stButton"]:has(button:not([kind="primary"])) + div,
    .ks-refresh-btn .stButton button {
        background-color: var(--ks-forest-2) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-left: 1px solid rgba(255,255,255,0.15) !important;
        justify-content: center !important;
        text-align: center !important;
        font-weight: 600 !important;
    }
    .ks-refresh-btn .stButton button p {
        text-align: center !important;
    }
    .ks-refresh-btn .stButton button:hover {
        background-color: var(--ks-gold) !important;
        color: var(--ks-ink) !important;
        border-color: var(--ks-gold) !important;
    }

    /* ── Titres ── */
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--ks-forest) !important;
    }

    /* ── Cartes KPI — fiche de dossier tamponnée ── */
    .ks-kpi-card {
        background: #FFFFFF;
        border-radius: 6px;
        padding: 1rem 1.2rem;
        border: 1px solid var(--ks-line);
        border-left: 4px solid var(--ks-ink);
        position: relative;
        overflow: hidden;
        min-height: 110px;
    }
    .ks-kpi-card::after {
        content: '';
        position: absolute;
        top: 12px; right: 12px;
        width: 11px; height: 11px;
        border-radius: 50%;
        border: 2px solid var(--ks-ink);
        background: transparent;
        opacity: 0.55;
    }
    .ks-kpi-teal   { border-left-color: var(--ks-teal); }
    .ks-kpi-teal::after  { border-color: var(--ks-teal); }
    .ks-kpi-blue   { border-left-color: var(--ks-blue); }
    .ks-kpi-blue::after  { border-color: var(--ks-blue); }
    .ks-kpi-amber  { border-left-color: var(--ks-gold); }
    .ks-kpi-amber::after { border-color: var(--ks-gold); }
    .ks-kpi-coral  { border-left-color: var(--ks-stamp); }
    .ks-kpi-coral::after { border-color: var(--ks-stamp); }
    .ks-kpi-navy   { border-left-color: var(--ks-forest); }
    .ks-kpi-navy::after  { border-color: var(--ks-forest); }

    .ks-kpi-label {
        font-size: 10.5px;
        font-weight: 600;
        color: var(--ks-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
        padding-right: 20px;
    }
    .ks-kpi-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 27px;
        font-weight: 600;
        color: var(--ks-ink);
        letter-spacing: -0.5px;
        line-height: 1.2;
        white-space: nowrap;
    }
    .ks-kpi-sub {
        font-size: 11px;
        margin-top: 6px;
        line-height: 1.4;
        font-family: 'Inter', sans-serif;
    }
    .ks-up   { color: var(--ks-teal); }
    .ks-down { color: var(--ks-stamp); }
    .ks-neutral { color: var(--ks-muted); }

    /* ── Section titre — étiquette de dossier ── */
    .ks-section-label {
        display: inline-block;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 11px;
        font-weight: 600;
        color: var(--ks-forest);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 12px;
        margin-top: 8px;
        padding: 3px 10px;
        background: var(--ks-paper-2);
        border-radius: 4px;
        border-left: 3px solid var(--ks-gold);
    }

    /* ── Cascade bar ── */
    .ks-cascade-track {
        height: 10px;
        background: var(--ks-paper-2);
        border-radius: 5px;
        overflow: hidden;
        margin: 6px 0;
        border: 1px solid var(--ks-line);
    }
    .ks-cascade-fill {
        height: 100%;
        border-radius: 5px;
        transition: width 0.8s ease;
    }

    /* ── Alert / warning box ── */
    .ks-alert {
        background: var(--ks-stamp-light);
        border-left: 4px solid var(--ks-stamp);
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 13px;
        color: #5A1F1F;
        margin-bottom: 8px;
    }
    .ks-warning {
        background: var(--ks-gold-light);
        border-left: 4px solid var(--ks-gold);
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 13px;
        color: #5C4419;
        margin-bottom: 8px;
    }

    /* ── Divider ── */
    .ks-divider {
        border: none;
        border-top: 1px solid var(--ks-line);
        margin: 1.5rem 0;
    }

    /* ── Bouton refresh ── */
    .stButton button {
        background-color: var(--ks-forest-2) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-family: 'Space Grotesk', sans-serif !important;
        width: 100%;
        transition: background 0.15s ease;
    }
    .stButton button:hover {
        background-color: var(--ks-gold) !important;
        color: var(--ks-ink) !important;
        border-color: var(--ks-gold) !important;
    }

    /* ── Listes déroulantes (selectbox) ── */
    div[data-testid="stSelectbox"] > label {
        font-size: 11px;
        font-weight: 600;
        color: var(--ks-muted);
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    div[data-testid="stSelectbox"] > div > div {
        background-color: #FFFFFF !important;
        border: 1px solid var(--ks-line) !important;
        border-radius: 6px !important;
        font-family: 'Inter', sans-serif;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
        cursor: pointer;
    }
    div[data-testid="stSelectbox"] > div > div:hover {
        border-color: var(--ks-teal) !important;
        box-shadow: 0 0 0 1px rgba(61,140,125,0.15);
    }
    div[data-testid="stSelectbox"] > div > div:focus-within,
    div[data-testid="stSelectbox"] > div > div[aria-expanded="true"] {
        border-color: var(--ks-forest) !important;
        box-shadow: 0 0 0 2px rgba(31,77,58,0.12);
    }
    ul[data-testid="stSelectboxVirtualDropdown"] li,
    li[role="option"] {
        font-family: 'Inter', sans-serif;
        font-size: 13px;
    }
    li[role="option"]:hover,
    li[aria-selected="true"] {
        background-color: var(--ks-teal-light) !important;
        color: var(--ks-forest) !important;
    }

    /* ── Onglets (tabs) ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid var(--ks-line);
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 13px;
        font-weight: 500;
        color: var(--ks-muted);
        border-radius: 6px 6px 0 0;
        padding: 8px 14px;
        transition: background 0.15s ease, color 0.15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--ks-paper-2);
        color: var(--ks-forest);
        cursor: pointer;
    }
    .stTabs [aria-selected="true"] {
        color: var(--ks-forest) !important;
        font-weight: 600 !important;
        border-bottom: 2px solid var(--ks-gold) !important;
    }

    /* ── Tableaux ── */
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--ks-line);
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================
# CONNEXION DUCKDB — CACHE
# =============================================================
@st.cache_resource
def get_connection():
    """Connexion DuckDB partagée — chargée une seule fois"""
    import duckdb
    db_path = Path(__file__).parent.parent / "data" / "kosante.duckdb"
    if not db_path.exists():
        st.error(f"❌ Base DuckDB introuvable : {db_path}")
        st.stop()
    return duckdb.connect(str(db_path), read_only=True)


@st.cache_data(ttl=300)  # Cache 5 minutes
def query(_conn, sql: str):
    """Exécute une requête et retourne un DataFrame"""
    import pandas as pd
    return _conn.execute(sql).df()


# =============================================================
# SIDEBAR — Navigation
# =============================================================
def render_sidebar():
    # État de la page active (persiste entre les reruns)
    if "page_active" not in st.session_state:
        st.session_state.page_active = "Vue d'ensemble"

    MENU = [
        ("01", "Vue d'ensemble",  "Vue d'ensemble",   "⊞"),
        ("02", "Dépistage CDV",   "Dépistage CDV",    "🔬"),
        ("03", "Fichier actif",   "Fichier actif",    "👥"),
        ("04", "Performances",    "Performances cliniques", "📊"),
        ("05", "Attrition",       "Attrition",         "⚠"),
        ("06", "Listing",         "Listing",            "🖨"),
    ]

    with st.sidebar:
        # Logo — collé en haut, zéro espace mort
        st.markdown("""
        <div style="padding: 2px 0 10px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="background:#C99A3B; width:34px; height:34px;
                     border-radius:7px; display:flex; align-items:center;
                     justify-content:center; font-size:16px;
                     border:1px solid rgba(255,255,255,0.2); flex-shrink:0;">🏥</div>
                <div>
                    <div style="font-family:'Space Grotesk',sans-serif;
                         font-size:14.5px; font-weight:600; line-height:1.2;
                         color:white; letter-spacing:0.3px;">KoSanté BI</div>
                    <div style="font-size:9.5px; color:rgba(255,255,255,0.45);
                         letter-spacing:1px;">ONG</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown(
            '<div style="font-size:9px; font-weight:600; '
            'color:rgba(255,255,255,0.3); letter-spacing:1.2px; '
            'text-transform:uppercase; margin-bottom:6px;">'
            'TABLEAU DE BORD</div>',
            unsafe_allow_html=True
        )

        for numero, label_affiche, label_route, icone in MENU:
            est_actif = st.session_state.page_active == label_route
            if st.button(
                f"{icone}   {numero} · {label_affiche}",
                key=f"nav_{numero}",
                use_container_width=True,
                type="primary" if est_actif else "secondary"
            ):
                st.session_state.page_active = label_route
                st.rerun()

        st.markdown("---")

        # Bouton rafraîchir — style distinct
        st.markdown('<div class="ks-refresh-btn">', unsafe_allow_html=True)
        if st.button("🔄  Rafraîchir les données", use_container_width=True):
            import subprocess
            import sys
            root = Path(__file__).parent.parent

            # Marqueurs de succès attendus dans le log de chaque script
            # (certains scripts pyodbc crashent en interne APRES avoir
            #  terminé leur travail — à la fermeture de connexion ODBC.
            #  Le returncode seul n'est donc pas fiable ; on vérifie aussi
            #  que le message de succès est bien présent dans la sortie.)
            etapes = [
                ("Extraction",     root / "etl" / "extract.py",   "Extraction complète"),
                ("Transformation", root / "etl" / "transform.py", "Transformation complète"),
                ("Chargement",     root / "etl" / "load.py",      "DuckDB chargé"),
            ]

            erreur_survenue = False
            with st.spinner("Mise à jour en cours..."):
                for nom_etape, script, marqueur_succes in etapes:
                    # Avant de lancer load.py, on doit fermer la connexion
                    # DuckDB que Streamlit garde ouverte en cache — sinon
                    # Windows refuse que load.py supprime/recrée le fichier
                    # (PermissionError: fichier utilisé par un autre processus)
                    if nom_etape == "Chargement":
                        try:
                            get_connection().close()
                        except Exception:
                            pass
                        st.cache_resource.clear()

                    try:
                        resultat = subprocess.run(
                            [sys.executable, str(script)],
                            cwd=str(root),
                            capture_output=True,
                            text=True,
                            timeout=600
                        )
                        sortie_complete = (resultat.stdout or "") + (resultat.stderr or "")
                        succes_detecte = marqueur_succes in sortie_complete

                        if resultat.returncode != 0 and not succes_detecte:
                            erreur_survenue = True
                            st.error(
                                f"❌ Erreur durant l'étape « {nom_etape} »"
                            )
                            with st.expander("Détails de l'erreur"):
                                st.code(resultat.stderr or resultat.stdout)
                            break
                        elif resultat.returncode != 0 and succes_detecte:
                            # Le script a réussi son travail mais a crashé
                            # juste après (ex: fermeture connexion ODBC).
                            # On continue sans bloquer l'utilisateur.
                            pass
                    except subprocess.TimeoutExpired:
                        erreur_survenue = True
                        st.error(f"❌ Timeout durant l'étape « {nom_etape} »")
                        break
                    except Exception as e:
                        erreur_survenue = True
                        st.error(f"❌ Erreur inattendue : {e}")
                        break

            if not erreur_survenue:
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("✅ Données mises à jour !")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Dernière mise à jour
        try:
            conn = get_connection()
            last = query(conn, """
                SELECT MAX(DateRegime) AS last_date
                FROM TblRegime
            """)
            if not last.empty and last['last_date'].iloc[0]:
                st.markdown(
                    f'<div style="font-size:10px; color:rgba(255,255,255,0.3); '
                    f'text-align:center; margin-top:8px;">'
                    f'Données au {last["last_date"].iloc[0]}</div>',
                    unsafe_allow_html=True
                )
        except Exception:
            pass

    return st.session_state.page_active


# =============================================================
# IMPORTS DES PAGES
# =============================================================
def main():
    page = render_sidebar()

    if page == "Vue d'ensemble":
        from views.vue_ensemble import render
        render()
    elif page == "Dépistage CDV":
        from views.depistage import render
        render()
    elif page == "Fichier actif":
        from views.file_active import render
        render()
    elif page == "Performances cliniques":
        from views.performances import render
        render()
    elif page == "Attrition":
        from views.attrition import render
        render()
    elif page == "Listing":
        from views.listing import render
        render()

if __name__ == "__main__":
    main()