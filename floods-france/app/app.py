"""
app.py — Page d'accueil de l'application Floods France

Lancer l'app :
    cd floods-france/app
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Floods France",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Floods France")
    st.caption("Analyse du risque inondation · Pilote Hérault (34)")
    st.markdown("---")
    st.markdown(
        "**Navigation**\n"
        "- 🌊 [Cartes d'Aléa](./Cartes_Alea)\n"
        "- 📊 [Fréquences](./Frequences)\n"
        "- 🏔️ Terrain *(bientôt)*\n"
        "- 🏘️ Exposition *(bientôt)*\n"
        "- 📉 Vulnérabilité *(bientôt)*\n"
        "- 💰 Risque *(bientôt)*\n"
    )

# ── Contenu principal ─────────────────────────────────────────────────────────
st.title("🌊 Analyse du Risque Inondation — France")
st.subheader("Application pilote · Hérault (34) · Données publiques françaises")

st.markdown("""
Cette application analyse le **risque inondation** en France en combinant :

| Composante | Description | Sources |
|-----------|-------------|---------|
| 🌊 **Aléa** | Zones PPRI, TRI, CatNat, fréquences | Géorisques, Hub'Eau |
| 🏔️ **Terrain** | DEM, bassins versants, HAND | Copernicus, IGN |
| 🏘️ **Exposition** | Bâtiments, population, infrastructure | BD TOPO, OSM, INSEE |
| 📉 **Vulnérabilité** | Courbes dommages JRC Huizinga 2017 | JRC, CLIMAAX |
| 💰 **Risque** | Dommages économiques (€) · EAD | Calcul interne |

---
""")

# ── Chaîne de traitement ───────────────────────────────────────────────────────
st.markdown("### Chaîne de traitement")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("""
    **🌊 01 — Aléa**
    - PPRI communes
    - CatNat historique
    - Stations hydro
    - Analyse fréquentielle
    """)
    st.page_link("pages/1_Cartes_Alea.py", label="→ Cartes d'Aléa", icon="🌊")
    st.page_link("pages/2_Frequences.py", label="→ Fréquences", icon="📊")

with col2:
    st.markdown("""
    **🏔️ 02 — Terrain**
    - DEM Copernicus 30m
    - Bassins versants
    - HAND index
    - Flow direction D8
    """)
    st.info("Bientôt disponible")

with col3:
    st.markdown("""
    **⚙️ 03 — Simulation 2D**
    - HydroMT setup
    - SFINCS model
    - Hauteurs d'eau
    - Scénarios T10/T100/T1000
    """)
    st.info("Bientôt disponible")

with col4:
    st.markdown("""
    **🏘️ 04 — Exposition**
    - BD TOPO bâtiments
    - OSM buildings
    - Surface, étages
    - Valeur maximale (€)
    """)
    st.info("Bientôt disponible")

with col5:
    st.markdown("""
    **💰 05/06 — Risque**
    - Courbes JRC Huizinga
    - Dommage par bâtiment
    - Agrégation commune
    - EAD (€/an)
    """)
    st.info("Bientôt disponible")

st.markdown("---")

# ── Infos techniques ──────────────────────────────────────────────────────────
with st.expander("ℹ️ Informations techniques"):
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("""
        **APIs utilisées**
        - `https://mapsref.brgm.fr/wxs/georisques/risques` — WFS v1.1.0
        - `https://www.georisques.gouv.fr/api/v1/gaspar/catnat` — CatNat
        - `https://hubeau.eaufrance.fr/api/v2/hydrometrie` — Hub'Eau v2
        - `https://geo.api.gouv.fr` — Communes, départements
        - `https://data.geopf.fr/wfs/ows` — IGN Géoplateforme (BD TOPO)
        """)

    with col_t2:
        st.markdown("""
        **Stack technique**
        - `streamlit` — Interface web
        - `geopandas` — Données géospatiales
        - `folium` + `streamlit-folium` — Cartes interactives
        - `plotly` — Graphiques interactifs
        - `scipy` — Statistiques (GEV, Gumbel)
        - `requests` — Appels API
        """)

st.caption(
    "Données publiques françaises · Géorisques, Hub'Eau, data.gouv.fr, IGN · "
    "Courbes de vulnérabilité : JRC Huizinga 2017"
)
