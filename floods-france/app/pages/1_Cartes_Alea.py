"""
Page 1 — Cartes d'Aléa Inondation (PPRI & CatNat)
Équivalent Streamlit du notebook 01a_flood_maps_TRI.ipynb
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import geopandas as gpd
import folium
import streamlit as st
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.api import (
    load_communes,
    load_ppri_approuves,
    load_ppri_prescrits,
    load_catnat,
    load_stations,
    load_observations,
    build_communes_ppri,
    get_center,
    WMS_GEORISQUES,
)

# ── Config page ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aléa Inondation — Floods France",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌊 Aléa Inondation")
    st.markdown("---")
    st.subheader("📍 Périmètre d'étude")

    DEPT_OPTIONS = {
        "34 — Hérault": "34",
        "30 — Gard":    "30",
        "13 — Bouches-du-Rhône": "13",
    }
    dept_label  = st.selectbox("Département", list(DEPT_OPTIONS.keys()), index=0)
    DEPT_CODE   = DEPT_OPTIONS[dept_label]
    DEPT_SUFFIX = dept_label.split("—")[1].strip()

    if st.button("↺ Vider le cache", help="Forcer le rechargement des données API"):
        st.cache_data.clear()
        st.success("Cache vidé !")

    st.markdown("---")
    st.caption(
        "**Sources**\n"
        "- [Géorisques WFS](https://www.georisques.gouv.fr/donnees/bases-de-donnees) v1.1\n"
        "- [Géorisques API CatNat](https://georisques.gouv.fr/api)\n"
        "- [Hub'Eau v2](https://hubeau.eaufrance.fr/)\n"
        "- [geo.api.gouv.fr](https://geo.api.gouv.fr/)\n"
    )

CENTER = get_center(DEPT_CODE)

# ── Chargement des données ────────────────────────────────────────────────────
with st.spinner("⏳ Chargement des données…"):
    try:
        gdf_communes    = load_communes(DEPT_CODE)
        gdf_ppri_app    = load_ppri_approuves(DEPT_CODE)
        gdf_ppri_pre    = load_ppri_prescrits(DEPT_CODE)
        gdf_communes_pp = build_communes_ppri(DEPT_CODE)
        gdf_stations    = load_stations(DEPT_CODE)
        data_ok = True
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
        st.stop()

# ── En-tête ───────────────────────────────────────────────────────────────────
st.title(f"🌊 Aléa Inondation — {DEPT_SUFFIX} ({DEPT_CODE})")
st.caption("PPRI · CatNat · Stations hydrométrie  |  Géorisques · Hub'Eau v2")

# ── Métriques ─────────────────────────────────────────────────────────────────
n_communes  = len(gdf_communes)
n_ppri_com  = gdf_ppri_app["cod_commune"].nunique() if not gdf_ppri_app.empty else 0
n_ppri_tot  = len(gdf_ppri_app)
n_ppri_pre  = gdf_ppri_pre["cod_commune"].nunique() if not gdf_ppri_pre.empty else 0
n_stations  = len(gdf_stations)
pct_ppri    = f"{100*n_ppri_com/max(n_communes,1):.0f}%"

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Communes",         n_communes)
col2.metric("PPRI approuvés",   n_ppri_tot,  delta=f"{n_ppri_com} communes ({pct_ppri})")
col3.metric("PPRI prescrits",   n_ppri_pre,  delta="communes")
col4.metric("Stations hydro",   n_stations,  delta="en service")
col5.metric("Source",           "Géorisques", delta="WFS v1.1 ✅")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_ppri, tab_catnat, tab_hydro, tab_wms = st.tabs([
    "📋 PPRI", "⚡ CatNat", "💧 Hydrométrie", "🗺 Zones officielles (WMS)"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PPRI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ppri:
    col_map, col_chart = st.columns([3, 2])

    # ── Carte choroplèthe PPRI ────────────────────────────────────────────────
    with col_map:
        st.subheader("Communes avec PPRI inondation")

        m_ppri = folium.Map(
            location=CENTER, zoom_start=9,
            tiles="CartoDB positron", prefer_canvas=True
        )

        # Choroplèthe nb PPRI
        folium.Choropleth(
            geo_data=gdf_communes_pp.__geo_interface__,
            data=gdf_communes_pp,
            columns=["code", "nb_ppri"],
            key_on="feature.properties.code",
            fill_color="OrRd",
            fill_opacity=0.65,
            line_opacity=0.25,
            legend_name="Nb PPRI inondation",
            name="Communes — PPRI",
            nan_fill_color="white",
            nan_fill_opacity=0.2,
        ).add_to(m_ppri)

        # Tooltip invisible par-dessus
        folium.GeoJson(
            gdf_communes_pp.__geo_interface__,
            style_function=lambda _: {"fillOpacity": 0, "color": "transparent", "weight": 0},
            tooltip=folium.GeoJsonTooltip(
                fields=["nom", "code", "nb_ppri", "statut"],
                aliases=["Commune", "INSEE", "Nb PPRI", "Statut"],
            ),
        ).add_to(m_ppri)

        # Stations hydrométrie
        for _, row in gdf_stations.iterrows():
            folium.CircleMarker(
                location=[row["latitude_station"], row["longitude_station"]],
                radius=5,
                color="#1a6bab",
                fill=True,
                fill_opacity=0.9,
                tooltip=(f"{row['code_station']} — "
                         f"{row.get('libelle_station', '')} "
                         f"({row.get('libelle_cours_eau', '')})"),
            ).add_to(m_ppri)

        folium.LayerControl().add_to(m_ppri)
        st_folium(m_ppri, use_container_width=True, height=480, returned_objects=[])

    # ── Graphiques PPRI ───────────────────────────────────────────────────────
    with col_chart:
        if gdf_ppri_app.empty:
            st.warning("Aucune donnée PPRI pour ce département.")
        else:
            # Top communes
            top = (
                gdf_ppri_app.groupby(["cod_commune", "lib_commune"])
                .size()
                .reset_index(name="nb_ppri")
                .sort_values("nb_ppri", ascending=False)
                .head(20)
            )

            fig_bar = px.bar(
                top.sort_values("nb_ppri"),
                x="nb_ppri", y="lib_commune",
                orientation="h",
                color="nb_ppri",
                color_continuous_scale="OrRd",
                title=f"Top 20 communes — procédures PPRI",
                labels={"nb_ppri": "Nb PPRI", "lib_commune": "Commune"},
                template="plotly_white",
            )
            fig_bar.update_layout(height=480, coloraxis_showscale=False,
                                  margin=dict(l=0, r=10, t=40, b=10))
            st.plotly_chart(fig_bar, use_container_width=True)

    # ── Timeline approbations PPRI ────────────────────────────────────────────
    st.markdown("#### 📅 Chronologie des approbations PPRI")

    gdf_dated = gdf_ppri_app[gdf_ppri_app["dat_approbation"].notna()].copy()
    gdf_dated["annee_appro"] = pd.to_datetime(
        gdf_dated["dat_approbation"], format="%d-%m-%Y", errors="coerce"
    ).dt.year
    gdf_dated = gdf_dated.dropna(subset=["annee_appro"])

    if gdf_dated.empty:
        st.info("Aucune date d'approbation disponible.")
    else:
        annual_appro = gdf_dated.groupby("annee_appro").size().reset_index(name="nb")
        annual_appro["cumul"] = annual_appro["nb"].cumsum()
        n_parsed = len(gdf_dated)
        n_total  = len(gdf_ppri_app[gdf_ppri_app["dat_approbation"].notna()])

        st.caption(f"{n_parsed} / {n_total} PPRI avec date d'approbation parsée")

        fig_tl = make_subplots(specs=[[{"secondary_y": True}]])
        fig_tl.add_trace(
            go.Bar(
                x=annual_appro["annee_appro"], y=annual_appro["nb"],
                name="Nouveaux PPRI", marker_color="#d7301f",
                hovertemplate="%{x} : %{y} PPRI<extra></extra>",
            ),
            secondary_y=False,
        )
        fig_tl.add_trace(
            go.Scatter(
                x=annual_appro["annee_appro"], y=annual_appro["cumul"],
                name="Cumul PPRI", mode="lines+markers",
                line=dict(color="#2c7bb6", width=2.5),
                hovertemplate="%{x} : %{y} cumulés<extra></extra>",
            ),
            secondary_y=True,
        )
        fig_tl.update_layout(
            title=f"Évolution des approbations PPRI inondation — {DEPT_SUFFIX}",
            height=320, template="plotly_white",
            legend=dict(x=0.02, y=0.98),
        )
        fig_tl.update_yaxes(title_text="Nb PPRI / an", secondary_y=False)
        fig_tl.update_yaxes(title_text="Cumul", secondary_y=True)
        st.plotly_chart(fig_tl, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CATNAT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_catnat:
    if gdf_ppri_app.empty:
        st.warning("Pas de données PPRI disponibles pour calculer les communes à analyser.")
        st.stop()

    # Sélection des communes à analyser
    top_communes = (
        gdf_ppri_app.groupby(["cod_commune", "lib_commune"])
        .size()
        .reset_index(name="nb")
        .sort_values("nb", ascending=False)
        .head(30)
    )
    commune_options = dict(zip(
        top_communes["lib_commune"] + " (" + top_communes["cod_commune"] + ")",
        top_communes["cod_commune"],
    ))

    st.subheader("Configuration")
    selected_labels = st.multiselect(
        "Communes à analyser (CatNat)",
        options=list(commune_options.keys()),
        default=list(commune_options.keys())[:20],
        help="Sélectionner les communes dont on charge les arrêtés CatNat inondation.",
    )
    codes_selected = tuple(commune_options[lbl] for lbl in selected_labels)

    if not codes_selected:
        st.info("Sélectionner au moins une commune.")
        st.stop()

    with st.spinner(f"⏳ Chargement CatNat pour {len(codes_selected)} communes…"):
        df_catnat = load_catnat(codes_selected)

    if df_catnat.empty:
        st.warning("Aucun arrêté CatNat inondation trouvé pour les communes sélectionnées.")
    else:
        st.success(f"**{len(df_catnat)} arrêtés** CatNat inondation chargés")

        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.metric("Arrêtés totaux",    len(df_catnat))
        col_c2.metric("Communes touchées",  df_catnat["code_insee"].nunique())
        col_c3.metric(
            "Année max",
            int(df_catnat["annee"].max()) if not df_catnat["annee"].isna().all() else "—",
        )

        # ── Graphiques CatNat ─────────────────────────────────────────────────
        col_g1, col_g2 = st.columns([3, 2])

        with col_g1:
            annual = df_catnat.groupby("annee").size().reset_index(name="nb")

            fig_an = go.Figure()
            fig_an.add_trace(go.Bar(
                x=annual["annee"], y=annual["nb"],
                marker_color="steelblue", name="Arrêtés",
                hovertemplate="%{x} : %{y} arrêtés<extra></extra>",
            ))
            for yr, lbl in [(2002, "Gard 2002"), (2014, "Oct. 2014"), (2018, "Oct. 2018")]:
                if annual["annee"].min() <= yr <= annual["annee"].max():
                    fig_an.add_vline(
                        x=yr, line_dash="dash", line_color="red", line_width=1,
                        annotation_text=lbl, annotation_font_size=9,
                        annotation_font_color="red",
                    )
            fig_an.update_layout(
                title="Arrêtés CatNat inondation par année",
                xaxis_title="Année", yaxis_title="Nombre d'arrêtés",
                height=320, template="plotly_white",
            )
            st.plotly_chart(fig_an, use_container_width=True)

        with col_g2:
            top_cat = (
                df_catnat.groupby("libelle_commune")
                .size()
                .reset_index(name="nb")
                .sort_values("nb", ascending=False)
                .head(12)
            )
            fig_top = px.bar(
                top_cat.sort_values("nb"),
                x="nb", y="libelle_commune",
                orientation="h",
                color="nb",
                color_continuous_scale="Blues",
                title="Top 12 communes",
                labels={"nb": "Nb CatNat", "libelle_commune": ""},
                template="plotly_white",
            )
            fig_top.update_layout(height=320, coloraxis_showscale=False,
                                  margin=dict(l=0, r=10, t=40, b=0))
            st.plotly_chart(fig_top, use_container_width=True)

        # ── Carte choroplèthe CatNat ──────────────────────────────────────────
        st.subheader("Carte — Fréquence des arrêtés CatNat")

        catnat_count = (
            df_catnat.groupby("code_insee").size().reset_index(name="nb_catnat")
        )
        gdf_cn = gdf_communes.merge(
            catnat_count, left_on="code", right_on="code_insee", how="left"
        )
        gdf_cn["nb_catnat"] = gdf_cn["nb_catnat"].fillna(0).astype(int)

        m_cn = folium.Map(
            location=CENTER, zoom_start=9,
            tiles="CartoDB dark_matter", prefer_canvas=True,
        )
        folium.Choropleth(
            geo_data=gdf_cn.__geo_interface__,
            data=gdf_cn,
            columns=["code", "nb_catnat"],
            key_on="feature.properties.code",
            fill_color="YlOrRd",
            fill_opacity=0.75,
            line_opacity=0.2,
            legend_name="Nb CatNat inondation",
            name="Fréquence CatNat",
            nan_fill_color="transparent",
        ).add_to(m_cn)
        folium.GeoJson(
            gdf_cn.__geo_interface__,
            style_function=lambda _: {"fillOpacity": 0, "color": "transparent", "weight": 0},
            tooltip=folium.GeoJsonTooltip(
                fields=["nom", "code", "nb_catnat"],
                aliases=["Commune", "INSEE", "Nb CatNat"],
            ),
        ).add_to(m_cn)
        folium.LayerControl().add_to(m_cn)
        st_folium(m_cn, use_container_width=True, height=460, returned_objects=[])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HYDROMÉTRIE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_hydro:
    if gdf_stations.empty:
        st.warning("Aucune station hydrométrique trouvée pour ce département.")
        st.stop()

    col_hmap, col_hchart = st.columns([2, 3])

    # ── Carte stations ────────────────────────────────────────────────────────
    with col_hmap:
        st.subheader(f"{len(gdf_stations)} stations en service")

        m_st = folium.Map(
            location=CENTER, zoom_start=9,
            tiles="CartoDB positron", prefer_canvas=True,
        )
        for _, row in gdf_stations.iterrows():
            popup_html = (
                f"<b>{row['code_station']}</b><br>"
                f"{row.get('libelle_station', '')}<br>"
                f"<i>{row.get('libelle_cours_eau', '')}</i>"
            )
            folium.CircleMarker(
                location=[row["latitude_station"], row["longitude_station"]],
                radius=7,
                color="#1a6bab",
                fill=True,
                fill_opacity=0.85,
                tooltip=f"{row['code_station']} — {row.get('libelle_station', '')}",
                popup=folium.Popup(popup_html, max_width=220),
            ).add_to(m_st)

        map_data = st_folium(m_st, use_container_width=True, height=380,
                             returned_objects=["last_object_clicked"])

    # ── Sélection station + courbe hauteur ───────────────────────────────────
    with col_hchart:
        station_options = {
            f"{row['code_station']} — {row.get('libelle_station', '')} ({row.get('libelle_cours_eau', '')})": row["code_station"]
            for _, row in gdf_stations.iterrows()
        }
        selected_station_label = st.selectbox(
            "Station hydrométrique",
            options=list(station_options.keys()),
            index=0,
        )
        selected_station_code = station_options[selected_station_label]

        grandeur = st.radio(
            "Grandeur",
            ["H — Hauteur (mm)", "Q — Débit (m³/s)"],
            horizontal=True,
            index=0,
        )
        grandeur_code = grandeur[0]

        with st.spinner("Chargement observations…"):
            df_obs = load_observations(selected_station_code, grandeur=grandeur_code)

        if df_obs.empty:
            st.info("Aucune observation disponible pour cette station.")
        else:
            unit  = "mm" if grandeur_code == "H" else "m³/s"
            label = f"Hauteur ({unit})" if grandeur_code == "H" else f"Débit ({unit})"
            q_max = df_obs["resultat_obs"].max()
            q_moy = df_obs["resultat_obs"].mean()

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Max observé", f"{q_max:.0f} {unit}")
            mc2.metric("Moyenne",     f"{q_moy:.0f} {unit}")
            mc3.metric("Nb obs.",     len(df_obs))

            fig_obs = go.Figure()
            fig_obs.add_trace(go.Scatter(
                x=df_obs["date_obs"],
                y=df_obs["resultat_obs"],
                mode="lines",
                line=dict(color="steelblue", width=1.8),
                fill="tozeroy",
                fillcolor="rgba(70,130,180,0.12)",
                name=label,
                hovertemplate=f"%{{x|%d/%m %H:%M}} — %{{y:.0f}} {unit}<extra></extra>",
            ))
            fig_obs.update_layout(
                title=f"{selected_station_label[:60]}",
                xaxis_title="Date / heure",
                yaxis_title=label,
                height=340,
                template="plotly_white",
            )
            st.plotly_chart(fig_obs, use_container_width=True)

    # ── Tableau récap stations ────────────────────────────────────────────────
    with st.expander("📋 Toutes les stations", expanded=False):
        cols_show = [c for c in ["code_station", "libelle_station", "libelle_cours_eau",
                                  "superficie_bv", "altitude_site_hydrologique",
                                  "latitude_station", "longitude_station"]
                     if c in gdf_stations.columns]
        st.dataframe(
            gdf_stations[cols_show].reset_index(drop=True),
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ZONES OFFICIELLES (WMS)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_wms:
    st.subheader("Zones PPRI officielles — WMS Géorisques")
    st.info(
        "**Couches WMS** : couchez et dézoomez sur une zone avec PPRI pour voir "
        "les zones d'aléa officielles (périmètres et zones inondées)."
    )

    m_wms = folium.Map(
        location=CENTER, zoom_start=10,
        tiles="CartoDB positron", prefer_canvas=True,
    )

    # Limites communes (fond léger)
    folium.GeoJson(
        gdf_communes.__geo_interface__,
        name="Limites communes",
        style_function=lambda _: {
            "color": "#888", "weight": 0.5, "fillOpacity": 0
        },
        tooltip=folium.GeoJsonTooltip(fields=["nom", "code"],
                                       aliases=["Commune", "INSEE"]),
    ).add_to(m_wms)

    # WMS — Périmètres PPRI
    folium.WmsTileLayer(
        url=WMS_GEORISQUES,
        layers="PPRN_INOND",
        name="PPRI — Périmètres",
        fmt="image/png",
        transparent=True,
        attr="Géorisques / DGPR",
    ).add_to(m_wms)

    # WMS — Zones d'aléa PPRI
    folium.WmsTileLayer(
        url=WMS_GEORISQUES,
        layers="PPRN_ZONE_INOND",
        name="PPRI — Zones aléa",
        fmt="image/png",
        transparent=True,
        attr="Géorisques / DGPR",
    ).add_to(m_wms)

    # WMS — Périmètres avec remplissage
    folium.WmsTileLayer(
        url=WMS_GEORISQUES,
        layers="PPRN_PERIMETRE_INOND",
        name="PPRI — Périmètres remplis",
        fmt="image/png",
        transparent=True,
        attr="Géorisques / DGPR",
    ).add_to(m_wms)

    # Stations
    for _, row in gdf_stations.iterrows():
        folium.CircleMarker(
            location=[row["latitude_station"], row["longitude_station"]],
            radius=5, color="#0066cc", fill=True, fill_opacity=0.9,
            tooltip=f"{row['code_station']} — {row.get('libelle_station', '')}",
        ).add_to(m_wms)

    folium.LayerControl(collapsed=False).add_to(m_wms)
    st_folium(m_wms, use_container_width=True, height=560, returned_objects=[])

    st.caption(
        "Zoomer sur Montpellier ou Béziers pour voir les zones PPRI via WMS. "
        "Activer/désactiver les couches via le contrôle en haut à droite."
    )
