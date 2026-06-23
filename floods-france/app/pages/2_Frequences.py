"""
pages/2_Frequences.py — Analyse fréquentielle des crues

Ajuste GEV (L-moments), Gumbel et Log-Normale sur des maxima annuels pour
estimer les quantiles T10 / T100 / T1000.

Sources de données :
  • Hub'Eau v2 obs_elab — QIXnJ (débit max journalier, série longue)  ← priorité
  • Données synthétiques GEV — calibrées indicativement sur la littérature
    hydro-climatique méditerranéenne (fallback si obs_elab indisponible)
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium

from utils.api import (
    load_stations, load_observations, load_obs_elab, load_dept_boundary,
    DEPT_BBOXES, get_center,
)
from utils.stats import (
    synth_annual_max,
    compute_annual_max,
    compute_annual_max_elab,
    fit_distributions,
    bootstrap_ci,
    return_level,
    build_return_table,
    create_excel_report,
)


# ── Configuration ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analyse Fréquentielle — Floods France",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

RETURN_PERIODS = np.array([2, 5, 10, 20, 50, 100, 200, 500, 1000], dtype=float)
T_PLOT = np.logspace(np.log10(1.5), np.log10(1200), 400)

# Paramètres GEV indicatifs (Hérault — littérature hydro-climatique)
STATION_SYNTH_PARAMS = {
    "Y210001001": {"xi": 0.18, "loc": 380, "scale": 210, "label": "L'Hérault à Gignac"},
    "Y214001002": {"xi": 0.22, "loc": 45,  "scale": 28,  "label": "Le Lez à Lavalette"},
    "Y221001001": {"xi": 0.15, "loc": 120, "scale": 72,  "label": "L'Orb à Bédarieux"},
    "Y210002001": {"xi": 0.20, "loc": 280, "scale": 160, "label": "L'Hérault à Canet"},
    "Y214002001": {"xi": 0.25, "loc": 35,  "scale": 22,  "label": "Le Lez à Montpellier"},
}

DEPT_LABELS = {
    "34": "34 — Hérault",
    "30": "30 — Gard",
    "13": "13 — Bouches-du-Rhône",
    "69": "69 — Rhône",
}

DIST_COLORS = {"GEV": "#e63946", "Gumbel": "#2196F3", "LN2": "#4CAF50"}

# Fonds de carte disponibles (name = folium built-in ; url+attr = custom tiles)
TILE_OPTIONS = {
    "🗺️ Carto (clair)":   {"name": "CartoDB positron"},
    "🌑 Carto (sombre)":  {"name": "CartoDB dark_matter"},
    "🌍 OpenStreetMap":   {"name": "OpenStreetMap"},
    "🛰️ Satellite ESRI": {
        "url":  "https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Tiles &copy; Esri &mdash; Esri, i-cubed, USDA, USGS, AEX, GeoEye, "
                "Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
    },
}

DEPT_BOUNDARY_STYLE = lambda x: {   # noqa: E731
    "fillColor":  "transparent",
    "color":      "#FF9800",
    "weight":     2.5,
    "dashArray":  "8, 5",
    "fillOpacity": 0.0,
}


def _make_map(center, zoom, tile_key, prefer_canvas=True):
    """Crée un objet folium.Map avec le fond de carte sélectionné."""
    cfg = TILE_OPTIONS.get(tile_key, TILE_OPTIONS["🗺️ Carto (clair)"])
    if "url" in cfg:
        return folium.Map(location=center, zoom_start=zoom,
                         tiles=cfg["url"], attr=cfg["attr"],
                         prefer_canvas=prefer_canvas)
    return folium.Map(location=center, zoom_start=zoom,
                     tiles=cfg["name"], prefer_canvas=prefer_canvas)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Analyse Fréquentielle")
    st.caption("Crues — Lois extrêmes · France")
    st.markdown("---")

    dept_code = st.selectbox(
        "Département",
        options=list(DEPT_BBOXES.keys()),
        format_func=lambda x: DEPT_LABELS.get(x, x),
        key="freq_dept",
    )

    with st.spinner("Chargement des stations…"):
        try:
            gdf_stations = load_stations(dept_code)
        except Exception as e:
            st.error(f"Erreur stations : {e}")
            gdf_stations = None

    station_options = {}
    if gdf_stations is not None and not gdf_stations.empty:
        for _, row in gdf_stations.iterrows():
            code  = str(row.get("code_station", "")).strip()
            label = str(row.get("libelle_station", code)).strip()
            if code:
                station_options[code] = f"{label} ({code})"

    if not station_options:
        st.warning("Aucune station disponible pour ce département.")
        if dept_code == "34":
            station_options = {k: f"{v['label']} ({k})" for k, v in STATION_SYNTH_PARAMS.items()}

    selected_station = st.selectbox(
        "Station hydrométrique",
        options=list(station_options.keys()),
        format_func=lambda x: station_options.get(x, x),
        key="freq_station",
    )

    st.markdown("---")

    # Source de données
    data_source = st.radio(
        "Source des données",
        ["📊 Synthétique (démonstration)", "🌊 Réelles Hub'Eau (obs_elab)"],
        key="freq_data_source",
        help=(
            "**Synthétique** : maxima annuels simulés GEV avec paramètres indicatifs.\n\n"
            "**Réelles** : série longue QIXnJ (débit max journalier) via Hub'Eau v2 obs_elab."
        ),
    )
    use_real = data_source.startswith("🌊")

    # Fond de carte
    fond_carte_key = st.selectbox(
        "Fond de carte",
        options=list(TILE_OPTIONS.keys()),
        key="freq_tiles",
    )

    st.markdown("---")
    st.markdown("**Paramètres statistiques**")

    dist_choices = st.multiselect(
        "Distributions",
        options=["GEV", "Gumbel", "LN2"],
        default=["GEV", "Gumbel", "LN2"],
        key="freq_dists",
    )
    if not dist_choices:
        dist_choices = ["GEV"]

    best_dist_only = st.checkbox(
        "Afficher seulement la meilleure (AIC)", value=False, key="freq_best_only"
    )

    n_bootstrap = st.select_slider(
        "Itérations Bootstrap (IC 95%)",
        options=[200, 500, 1000, 2000],
        value=1000,
        key="freq_bootstrap",
    )

    if not use_real:
        n_synth = st.slider(
            "Années synthétiques",
            min_value=30, max_value=100, value=60, step=5,
            key="freq_n_years",
        )
    else:
        n_synth = 60

    st.markdown("---")
    if st.button("🔄 Vider le cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(
        "**Références**\n"
        "- Méthode : Hosking & Wallis 1997\n"
        "- IC : Bootstrap Efron 1979\n"
        "- Données : Hub'Eau v2 (obs_elab / TR)\n"
        "- Synth. : GEV · Neppel et al. 2010\n"
    )


# ── En-tête ───────────────────────────────────────────────────────────────────
st.title("📊 Analyse Fréquentielle des Crues")

station_label = station_options.get(selected_station, selected_station)

# Coordonnées de la station sélectionnée
sel_lat, sel_lon = None, None
if gdf_stations is not None and not gdf_stations.empty:
    sel_rows = gdf_stations[gdf_stations["code_station"] == selected_station]
    if not sel_rows.empty:
        sel_lat = float(sel_rows.iloc[0]["latitude_station"])
        sel_lon = float(sel_rows.iloc[0]["longitude_station"])

# Contour département
with st.spinner("Chargement du contour départemental…"):
    dept_boundary = load_dept_boundary(dept_code)


# ════════════════════════════════════════════════════════════════════════════════
# Carte des stations du département
# ════════════════════════════════════════════════════════════════════════════════
st.markdown(f"### Réseau de stations — {DEPT_LABELS.get(dept_code, dept_code)}")

col_map, col_tbl = st.columns([4, 6])

with col_map:
    dept_center = get_center(dept_code)
    map_center  = [sel_lat, sel_lon] if sel_lat else dept_center

    m = _make_map(map_center, zoom=9, tile_key=fond_carte_key)

    # Contour du département
    if dept_boundary is not None and not dept_boundary.empty:
        folium.GeoJson(
            dept_boundary.__geo_interface__,
            style_function=DEPT_BOUNDARY_STYLE,
            tooltip=folium.Tooltip(f"Département {dept_code}", permanent=False),
        ).add_to(m)

    # Stations
    if gdf_stations is not None and not gdf_stations.empty:
        for _, row in gdf_stations.iterrows():
            code  = str(row.get("code_station", "")).strip()
            name  = str(row.get("libelle_station", code)).strip()
            river = str(row.get("libelle_cours_eau", "")).strip()
            lat_s = row.get("latitude_station")
            lon_s = row.get("longitude_station")
            if pd.isna(lat_s) or pd.isna(lon_s):
                continue
            is_sel = (code == selected_station)
            tip    = f"<b>{name}</b><br>{river}<br><small>{code}</small>"

            if is_sel:
                folium.Marker(
                    location=[float(lat_s), float(lon_s)],
                    icon=folium.Icon(color="red", icon="tint", prefix="fa"),
                    tooltip=folium.Tooltip(tip),
                ).add_to(m)
            else:
                folium.CircleMarker(
                    location=[float(lat_s), float(lon_s)],
                    radius=6,
                    color="#1565C0",
                    fill=True,
                    fill_color="#2196F3",
                    fill_opacity=0.65,
                    weight=1,
                    tooltip=folium.Tooltip(tip),
                ).add_to(m)

    st_folium(m, height=380, use_container_width=True, returned_objects=[])

with col_tbl:
    if gdf_stations is not None and not gdf_stations.empty:
        cols_keep = [c for c in ["code_station", "libelle_station", "libelle_cours_eau",
                                  "latitude_station", "longitude_station"]
                     if c in gdf_stations.columns]
        df_tbl = gdf_stations[cols_keep].copy().rename(columns={
            "code_station":      "Code",
            "libelle_station":   "Station",
            "libelle_cours_eau": "Cours d'eau",
            "latitude_station":  "Lat",
            "longitude_station": "Lon",
        })
        def _hl(row):
            if row.get("Code") == selected_station:
                return ["background-color: rgba(230,57,70,0.15)"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_tbl.style.apply(_hl, axis=1).format({"Lat": "{:.4f}", "Lon": "{:.4f}"}, na_rep="—"),
            height=380, use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aucune station chargée.")

st.markdown("---")
st.subheader(f"Département {dept_code} · {station_label}")


# ════════════════════════════════════════════════════════════════════════════════
# Chargement et sélection des données pour l'ajustement
# ════════════════════════════════════════════════════════════════════════════════
synth_p = STATION_SYNTH_PARAMS.get(
    selected_station,
    {"xi": 0.20, "loc": 150, "scale": 80, "label": station_label},
)

if use_real:
    with st.spinner("Chargement obs_elab Hub'Eau…"):
        try:
            df_elab_q = load_obs_elab(selected_station, "QIXnJ")
        except Exception:
            df_elab_q = pd.DataFrame()
        try:
            df_elab_h = load_obs_elab(selected_station, "HIXnJ")
        except Exception:
            df_elab_h = pd.DataFrame()

    s_annual     = compute_annual_max_elab(df_elab_q)
    n_years_elab = len(s_annual)

    if n_years_elab >= 5:
        data_fit        = s_annual.values
        data_source_lbl = f"Hub'Eau obs_elab — QIXnJ ({n_years_elab} années)"
        st.success(
            f"✅ **{n_years_elab} maxima annuels** chargés depuis Hub'Eau obs_elab "
            f"(QIXnJ — débit max journalier, m³/s). "
            f"Période : {int(s_annual.index.min())}–{int(s_annual.index.max())}.",
            icon="✅",
        )
    else:
        st.warning(
            f"⚠️ Données obs_elab insuffisantes ({n_years_elab} années < 5 requises). "
            "Utilisation des données synthétiques.",
            icon="⚠️",
        )
        data_fit        = synth_annual_max(n=n_synth, xi=synth_p["xi"],
                                           loc=synth_p["loc"], scale=synth_p["scale"])
        data_source_lbl = f"Synthétique (fallback — {n_synth} années)"
        s_annual        = pd.Series(dtype=float)
        n_years_elab    = 0
else:
    df_elab_q    = pd.DataFrame()
    df_elab_h    = pd.DataFrame()
    s_annual     = pd.Series(dtype=float)
    n_years_elab = 0

    data_fit        = synth_annual_max(n=n_synth, xi=synth_p["xi"],
                                       loc=synth_p["loc"], scale=synth_p["scale"])
    data_source_lbl = f"Synthétique ({n_synth} années)"
    st.warning(
        "⚠️ **Mode démonstration** — maxima annuels **synthétiques** (simulation GEV). "
        "Basculez sur *Réelles Hub'Eau* dans la barre latérale.",
        icon="⚠️",
    )


# ── Ajustement des distributions ──────────────────────────────────────────────
with st.spinner("Ajustement des distributions…"):
    fit_results = fit_distributions(data_fit)

if not fit_results:
    st.error("L'ajustement des distributions a échoué.")
    st.stop()

best_dist = min(fit_results, key=lambda k: fit_results[k]["aic"])


# ── Bootstrap CI ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _get_ci(data_tuple, dist_name, n_boot, rp_tuple):
    lo, hi = bootstrap_ci(np.array(data_tuple), dist_name,
                          np.array(rp_tuple), n_bootstrap=n_boot)
    return lo.tolist(), hi.tolist()


with st.spinner(f"Bootstrap IC 95% ({n_bootstrap} itérations)…"):
    try:
        ci_lo_list, ci_hi_list = _get_ci(
            tuple(data_fit.tolist()), best_dist,
            n_bootstrap, tuple(RETURN_PERIODS.tolist()),
        )
        ci_lower = np.array(ci_lo_list)
        ci_upper = np.array(ci_hi_list)
    except Exception:
        ci_lower = ci_upper = None


# ── Métriques ─────────────────────────────────────────────────────────────────
best_rv = fit_results[best_dist]["rv"]
q10     = return_level(best_rv, 10)
q100    = return_level(best_rv, 100)
q1000   = return_level(best_rv, 1000)

n_data = len(data_fit)
years_label = f"{n_years_elab} ans (réels)" if (use_real and n_years_elab >= 5) else f"{n_data} ans (synth.)"

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("📅 Données",          years_label)
with col2: st.metric("🔵 Q10  (décennal)",   f"{q10:.0f} m³/s")
with col3: st.metric("🟠 Q100 (centennal)",  f"{q100:.0f} m³/s")
with col4: st.metric("🔴 Q1000 (millénaire)",f"{q1000:.0f} m³/s")
with col5: st.metric("🏆 Meilleure loi", best_dist,
                     delta=f"AIC={fit_results[best_dist]['aic']:.1f}", delta_color="off")

st.markdown("---")


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📈 Courbe de fréquence",
    "🌊 Données disponibles",
    "📋 Ajustement & paramètres",
])


# ════════════════════════════════════════════════════════════════════════════════
# Tab 1 — Courbe de fréquence
# ════════════════════════════════════════════════════════════════════════════════
with tab1:

    fig = go.Figure()

    # Points empiriques (Weibull)
    sorted_data = np.sort(data_fit)
    n = len(sorted_data)
    emp_T = (n + 1) / np.arange(n, 0, -1)
    fig.add_trace(go.Scatter(
        x=emp_T, y=sorted_data, mode="markers",
        name="Maxima annuels — pos. Weibull",
        marker=dict(color="#555", size=7, symbol="circle-open", line=dict(width=1.5)),
        hovertemplate="T=%{x:.1f} ans<br>Q=%{y:.0f} m³/s<extra></extra>",
    ))

    # Courbes théoriques
    active_dists = [best_dist] if best_dist_only else [d for d in dist_choices if d in fit_results]
    for dist_name in active_dists:
        res     = fit_results[dist_name]
        q_vals  = res["rv"].ppf(1 - 1 / T_PLOT)
        is_best = (dist_name == best_dist)
        fig.add_trace(go.Scatter(
            x=T_PLOT, y=q_vals, mode="lines",
            name=res["label"],
            line=dict(color=DIST_COLORS.get(dist_name, "#999"),
                      width=3.0 if is_best else 1.8,
                      dash="solid" if is_best else "dash"),
            hovertemplate=f"{res['label']}<br>T=%{{x:.0f}} ans → Q=%{{y:.0f}} m³/s<extra></extra>",
        ))

    # IC Bootstrap
    if ci_lower is not None and best_dist in active_dists and not np.all(np.isnan(ci_lower)):
        hx = DIST_COLORS.get(best_dist, "#999")
        r_c, g_c, b_c = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
        fig.add_trace(go.Scatter(
            x=np.concatenate([RETURN_PERIODS, RETURN_PERIODS[::-1]]),
            y=np.concatenate([ci_upper, ci_lower[::-1]]),
            fill="toself",
            fillcolor=f"rgba({r_c},{g_c},{b_c},0.12)",
            line=dict(color=f"rgba({r_c},{g_c},{b_c},0)"),
            name=f"IC 95% {best_dist} (bootstrap n={n_bootstrap})",
            hoverinfo="skip",
        ))

    # Lignes de référence
    for T_ref, color, label in [(10, "#2196F3", "T10"), (100, "#FF9800", "T100"), (1000, "#F44336", "T1000")]:
        fig.add_vline(x=T_ref, line_dash="dot", line_color=color, opacity=0.5,
                      annotation_text=label, annotation_position="top right",
                      annotation_font_color=color, annotation_font_size=11)

    fig.update_layout(
        title=dict(text=f"Courbe de fréquence — {station_label}<br>"
                       f"<sup style='color:#777'>Données : {data_source_lbl}</sup>",
                   font_size=14),
        xaxis=dict(title="Période de retour T (années)", type="log",
                   range=[np.log10(1.5), np.log10(1300)],
                   tickvals=[2, 5, 10, 20, 50, 100, 200, 500, 1000],
                   ticktext=["2","5","10","20","50","100","200","500","1000"],
                   showgrid=True, gridcolor="#eee"),
        yaxis=dict(title="Débit de pointe Q (m³/s)", showgrid=True, gridcolor="#eee"),
        legend=dict(orientation="h", y=-0.22, x=0),
        height=560, template="plotly_white", hovermode="x unified",
        margin=dict(t=70, b=100),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tableau des quantiles
    st.markdown("#### Tableau des quantiles de crue")
    df_quant = build_return_table(fit_results)
    st.dataframe(
        df_quant.style.format({c: "{:.0f}" for c in df_quant.columns if c != "T (ans)"}),
        use_container_width=True, hide_index=True,
    )
    if use_real and n_years_elab >= 5:
        st.caption(
            f"Valeurs calculées sur {n_years_elab} maxima annuels réels "
            f"(Hub'Eau obs_elab · QIXnJ — {int(s_annual.index.min())}–"
            f"{int(s_annual.index.max())}). Méthode GEV L-moments, IC Bootstrap 95%."
        )
    else:
        st.caption(
            f"⚠️ Valeurs calculées sur {n_data} maxima annuels **synthétiques** "
            f"(GEV · ξ={synth_p['xi']}, μ={synth_p['loc']} m³/s, σ={synth_p['scale']} m³/s). "
            "Non opérationnelles — démonstration méthodologique."
        )

    # ── Téléchargements ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📥 Téléchargements")
    col_csv, col_xlsx = st.columns(2)

    # CSV — maxima annuels
    with col_csv:
        if hasattr(s_annual, "index") and len(s_annual) > 0:
            am_csv = pd.DataFrame({
                "annee_hydro":       s_annual.index.astype(int),
                "Q_max_annuel_m3s":  s_annual.values.round(2),
            })
        else:
            am_csv = pd.DataFrame({
                "index":             range(1, n_data + 1),
                "Q_max_annuel_m3s":  np.round(data_fit, 2),
            })
        st.download_button(
            "📊 Maxima annuels (CSV)",
            data=am_csv.to_csv(index=False).encode("utf-8"),
            file_name=f"maxima_{selected_station}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Excel — rapport complet
    with col_xlsx:
        try:
            excel_bytes = create_excel_report(
                station_code=selected_station,
                station_label=station_label,
                data_source_lbl=data_source_lbl,
                annual_max_series=s_annual if len(s_annual) > 0 else data_fit,
                fit_results=fit_results,
            )
            st.download_button(
                "📑 Rapport complet (Excel)",
                data=excel_bytes,
                file_name=f"rapport_freq_{selected_station}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Export Excel indisponible : {e}")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 2 — Données disponibles
# ════════════════════════════════════════════════════════════════════════════════
with tab2:

    # ── Section 1 : Localisation de la station ───────────────────────────────
    st.markdown("### Localisation de la station")

    col_loc_m, col_loc_i = st.columns([5, 5])

    with col_loc_m:
        if sel_lat and sel_lon:
            m2 = _make_map([sel_lat, sel_lon], zoom=12, tile_key=fond_carte_key)
            if dept_boundary is not None and not dept_boundary.empty:
                folium.GeoJson(
                    dept_boundary.__geo_interface__,
                    style_function=DEPT_BOUNDARY_STYLE,
                ).add_to(m2)
            folium.Marker(
                location=[sel_lat, sel_lon],
                icon=folium.Icon(color="red", icon="tint", prefix="fa"),
                tooltip=folium.Tooltip(
                    f"<b>{station_label}</b><br>{selected_station}", permanent=True),
                popup=folium.Popup(
                    f"<b>{station_label}</b><br>{selected_station}<br>"
                    f"{sel_lat:.4f}°N · {sel_lon:.4f}°E", max_width=220),
            ).add_to(m2)
            st_folium(m2, height=300, use_container_width=True, returned_objects=[])
        else:
            st.info("Coordonnées non disponibles pour cette station.")

    with col_loc_i:
        st.markdown("**Informations de la station**")
        if gdf_stations is not None and not gdf_stations.empty:
            sel_row = gdf_stations[gdf_stations["code_station"] == selected_station]
            if not sel_row.empty:
                si = sel_row.iloc[0]
                info_items = [
                    ("Code",           si.get("code_station", "—")),
                    ("Station",        si.get("libelle_station", "—")),
                    ("Cours d'eau",    si.get("libelle_cours_eau", "—")),
                ]
                if sel_lat:
                    info_items += [
                        ("Latitude",   f"{sel_lat:.4f} °N"),
                        ("Longitude",  f"{sel_lon:.4f} °E"),
                    ]
                # Champs optionnels
                for field, label, fmt in [
                    ("en_service",             "En service",   lambda v: "✅ Oui" if v else "🔴 Non"),
                    ("date_ouverture_station",  "Ouverture",    lambda v: str(v)[:10]),
                    ("altitude_ref_altitude",   "Altitude NGF", lambda v: f"{v} m"),
                    ("type_station",            "Type",         lambda v: str(v)),
                    ("uri_station",             "URL Hub'Eau",  lambda v: str(v)),
                ]:
                    val = si.get(field, None)
                    if val is not None and str(val) not in ("", "None", "nan", "NaN"):
                        info_items.append((label, fmt(val)))

                df_info = pd.DataFrame(info_items, columns=["Propriété", "Valeur"])
                st.dataframe(df_info, use_container_width=True, hide_index=True, height=280)
        else:
            st.info("Informations de station non disponibles.")

    st.markdown("---")

    # ── Section 2 : Données historiques long terme ───────────────────────────
    st.markdown("### Données historiques long terme")

    if use_real and n_years_elab >= 5 and not df_elab_q.empty:
        st.success(
            f"**{n_years_elab} années** disponibles — Hub'Eau obs_elab · QIXnJ.",
            icon="✅",
        )

        col_ts, col_stat = st.columns([6, 4])

        with col_ts:
            st.markdown("#### Maxima annuels — QIXnJ (m³/s)")
            years_arr = s_annual.index.astype(int).values
            vals_arr  = s_annual.values
            seuil_90  = float(np.percentile(vals_arr, 90))

            fig_elab = go.Figure()
            fig_elab.add_trace(go.Bar(
                x=years_arr, y=vals_arr,
                name="QIX annuel (m³/s)",
                marker_color=["#e63946" if v >= seuil_90 else "#2196F3" for v in vals_arr],
                hovertemplate="Année %{x}<br>QIX = %{y:.1f} m³/s<extra></extra>",
            ))
            fig_elab.add_hline(y=float(np.median(vals_arr)), line_dash="dash",
                               line_color="gray",
                               annotation_text=f"Médiane = {np.median(vals_arr):.0f} m³/s",
                               annotation_position="bottom right")
            fig_elab.update_layout(
                xaxis_title="Année hydrologique", yaxis_title="Q max annuel (m³/s)",
                height=300, template="plotly_white", margin=dict(t=10, b=30), showlegend=False,
            )
            st.plotly_chart(fig_elab, use_container_width=True)
            st.caption("Barres rouges = années > 90ᵉ percentile. QIXnJ converti de L/s en m³/s.")

        with col_stat:
            st.markdown("#### Statistiques descriptives")
            stats_elab = pd.DataFrame({
                "Statistique": ["N années", "Période", "Minimum", "Q25%", "Médiane",
                                "Moyenne", "Q75%", "Maximum", "Écart-type", "Cv (σ/μ)"],
                "Valeur": [
                    f"{n_years_elab}",
                    f"{int(s_annual.index.min())}–{int(s_annual.index.max())}",
                    f"{vals_arr.min():.1f} m³/s",
                    f"{np.percentile(vals_arr, 25):.1f} m³/s",
                    f"{np.median(vals_arr):.1f} m³/s",
                    f"{vals_arr.mean():.1f} m³/s",
                    f"{np.percentile(vals_arr, 75):.1f} m³/s",
                    f"{vals_arr.max():.1f} m³/s",
                    f"{vals_arr.std():.1f} m³/s",
                    f"{vals_arr.std() / vals_arr.mean():.3f}",
                ],
            })
            st.dataframe(stats_elab, use_container_width=True, hide_index=True)

        # ── Expander : série brute journalière ───────────────────────────────
        with st.expander("📊 Série brute complète — QIXnJ journalier (tous les jours)"):
            st.info(
                "**Pourquoi les maxima annuels ?** La méthode des blocs (Block Maxima / GEV) "
                "extrait le **maximum par année hydrologique** pour garantir "
                "l'**indépendance statistique** des données. "
                "Ici la série complète des QIXnJ journaliers : chaque point = "
                "le débit maximum observé ce jour-là (créneau journalier).",
                icon="ℹ️",
            )

            # Marquer les maxima annuels dans la série brute
            df_plot_raw = df_elab_q.copy()
            df_plot_raw["hydro_year"] = df_plot_raw["date_obs_elab"].apply(
                lambda d: d.year if d.month >= 9 else d.year - 1
            )
            am_dates, am_vals = [], []
            for yr in s_annual.index:
                sub = df_plot_raw[df_plot_raw["hydro_year"] == yr]
                if not sub.empty:
                    idx_mx = sub["resultat_obs_elab"].idxmax()
                    am_dates.append(sub.loc[idx_mx, "date_obs_elab"])
                    am_vals.append(sub.loc[idx_mx, "resultat_obs_elab"])

            fig_raw = go.Figure()
            fig_raw.add_trace(go.Scatter(
                x=df_elab_q["date_obs_elab"],
                y=df_elab_q["resultat_obs_elab"],
                mode="lines",
                name="QIXnJ (m³/s)",
                line=dict(color="#1565C0", width=0.8),
                fill="tozeroy",
                fillcolor="rgba(21,101,192,0.06)",
                hovertemplate="%{x|%Y-%m-%d}<br>Q = %{y:.1f} m³/s<extra></extra>",
            ))
            if am_dates:
                fig_raw.add_trace(go.Scatter(
                    x=am_dates, y=am_vals,
                    mode="markers",
                    name="Max annuel",
                    marker=dict(color="#e63946", size=9, symbol="star"),
                    hovertemplate="%{x|%Y}<br>Q max = %{y:.1f} m³/s<extra></extra>",
                ))
            fig_raw.update_layout(
                xaxis_title="Date", yaxis_title="QIXnJ (m³/s)",
                height=320, template="plotly_white",
                legend=dict(orientation="h", y=-0.2),
                margin=dict(t=10, b=60),
            )
            st.plotly_chart(fig_raw, use_container_width=True)

            # Tableau brut scrollable
            st.dataframe(
                df_elab_q[["date_obs_elab", "resultat_obs_elab"]]
                .rename(columns={"date_obs_elab": "Date",
                                  "resultat_obs_elab": "QIXnJ (m³/s)"})
                .style.format({"QIXnJ (m³/s)": "{:.2f}"}),
                height=220, use_container_width=True, hide_index=True,
            )

        # Hauteurs max annuelles (HIXnJ)
        if not df_elab_h.empty:
            s_annual_h = compute_annual_max_elab(df_elab_h)
            if len(s_annual_h) >= 3:
                with st.expander("📏 Hauteurs maximales annuelles — HIXnJ (m)"):
                    fig_h_elab = go.Figure()
                    fig_h_elab.add_trace(go.Scatter(
                        x=s_annual_h.index.astype(int).values, y=s_annual_h.values,
                        mode="lines+markers", name="H max annuel (m)",
                        line=dict(color="#1565C0", width=1.8),
                        marker=dict(size=6),
                        hovertemplate="Année %{x}<br>H max = %{y:.2f} m<extra></extra>",
                    ))
                    fig_h_elab.update_layout(
                        xaxis_title="Année hydrologique", yaxis_title="H max annuel (m)",
                        height=250, template="plotly_white",
                        margin=dict(t=10, b=30), showlegend=False,
                    )
                    st.plotly_chart(fig_h_elab, use_container_width=True)

    elif use_real:
        st.info(
            "Aucune donnée obs_elab disponible pour cette station "
            "(QIXnJ non publiée dans Banque Hydro). Données synthétiques utilisées.",
            icon="ℹ️",
        )
    else:
        # Série synthétique
        st.markdown("#### Série synthétique utilisée pour l'analyse fréquentielle")
        st.markdown(
            f"Paramètres GEV : **ξ={synth_p['xi']}**, "
            f"**μ={synth_p['loc']} m³/s**, **σ={synth_p['scale']} m³/s** — "
            f"{n_synth} années simulées."
        )
        annual_max_synth = synth_annual_max(n=n_synth, xi=synth_p["xi"],
                                            loc=synth_p["loc"], scale=synth_p["scale"])
        fig_synth = make_subplots(rows=1, cols=2,
                                  subplot_titles=["Distribution des maxima", "Chronologie (fictive)"])
        fig_synth.add_trace(go.Histogram(x=annual_max_synth, nbinsx=20, name="Maxima",
                                         marker_color="#e63946", opacity=0.7), row=1, col=1)
        years_fake = list(range(2025 - n_synth + 1, 2026))
        rng_plot   = np.random.default_rng(99)
        shuffled   = annual_max_synth.copy()
        rng_plot.shuffle(shuffled)
        fig_synth.add_trace(go.Bar(x=years_fake, y=shuffled, name="Série",
                                   marker_color="#e63946", opacity=0.6), row=1, col=2)
        fig_synth.add_hline(y=float(np.median(shuffled)), line_dash="dash", line_color="gray",
                            annotation_text=f"Médiane={np.median(shuffled):.0f} m³/s",
                            annotation_position="bottom right", row=1, col=2)
        fig_synth.update_layout(height=300, template="plotly_white",
                                showlegend=False, margin=dict(t=30, b=20))
        fig_synth.update_xaxes(title_text="Q (m³/s)", row=1, col=1)
        fig_synth.update_xaxes(title_text="Année", row=1, col=2)
        fig_synth.update_yaxes(title_text="Effectif", row=1, col=1)
        fig_synth.update_yaxes(title_text="Q (m³/s)", row=1, col=2)
        st.plotly_chart(fig_synth, use_container_width=True)

    st.markdown("---")

    # ── Section 3 : Observations temps réel ─────────────────────────────────
    st.markdown("### Observations temps réel — Hub'Eau v2")

    nb_jours_rt = st.radio(
        "Plage temporelle",
        options=[1, 7, 14, 30],
        format_func=lambda x: f"{x} jour{'s' if x > 1 else ''}",
        horizontal=True,
        index=1,   # défaut : 7 jours
        key="freq_nb_jours_rt",
    )

    with st.spinner(f"Chargement obs. temps réel ({nb_jours_rt} j)…"):
        try:
            df_h = load_observations(selected_station, grandeur="H", nb_jours=nb_jours_rt)
        except Exception:
            df_h = pd.DataFrame()
        try:
            df_q = load_observations(selected_station, grandeur="Q", nb_jours=nb_jours_rt)
        except Exception:
            df_q = pd.DataFrame()

    st.info(
        "Hub'Eau v2 fournit les **observations en temps réel** (observations_tr). "
        "Pour les séries longues, utilisez la source *Réelles Hub'Eau (obs_elab)* "
        "dans la barre latérale.",
        icon="ℹ️",
    )

    col_h_rt, col_q_rt = st.columns(2)

    with col_h_rt:
        st.markdown("#### Hauteur d'eau — H (m)")
        if df_h.empty:
            st.warning("Aucune donnée H disponible.")
        else:
            fig_h_rt = go.Figure()
            fig_h_rt.add_trace(go.Scatter(
                x=df_h["date_obs"], y=df_h["resultat_obs"],
                mode="lines", name="H (m)",
                line=dict(color="#2196F3", width=1.5),
                fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
                hovertemplate="%{x|%d/%m %H:%M}<br>H = %{y:.3f} m<extra></extra>",
            ))
            fig_h_rt.update_layout(xaxis_title="Date", yaxis_title="Hauteur (m)",
                                   height=260, template="plotly_white", margin=dict(t=10, b=30))
            st.plotly_chart(fig_h_rt, use_container_width=True)
            t0, t1 = df_h["date_obs"].min(), df_h["date_obs"].max()
            st.caption(f"{len(df_h)} obs · {t0.strftime('%d/%m/%Y')} → {t1.strftime('%d/%m/%Y')}")

    with col_q_rt:
        st.markdown("#### Débit — Q (m³/s)")
        if df_q.empty:
            st.warning("Aucune donnée Q disponible.")
        else:
            fig_q_rt = go.Figure()
            fig_q_rt.add_trace(go.Scatter(
                x=df_q["date_obs"], y=df_q["resultat_obs"],
                mode="lines", name="Q (m³/s)",
                line=dict(color="#4CAF50", width=1.5),
                fill="tozeroy", fillcolor="rgba(76,175,80,0.08)",
                hovertemplate="%{x|%d/%m %H:%M}<br>Q = %{y:.2f} m³/s<extra></extra>",
            ))
            fig_q_rt.update_layout(xaxis_title="Date", yaxis_title="Débit (m³/s)",
                                   height=260, template="plotly_white", margin=dict(t=10, b=30))
            st.plotly_chart(fig_q_rt, use_container_width=True)
            t0, t1 = df_q["date_obs"].min(), df_q["date_obs"].max()
            st.caption(f"{len(df_q)} obs · {t0.strftime('%d/%m/%Y')} → {t1.strftime('%d/%m/%Y')}")


# ════════════════════════════════════════════════════════════════════════════════
# Tab 3 — Ajustement & paramètres
# ════════════════════════════════════════════════════════════════════════════════
with tab3:

    st.markdown("### Comparaison des distributions ajustées")

    comp_rows = []
    for dist_name, res in fit_results.items():
        row = {
            "Distribution": res["label"],
            "Meilleure":    "✅" if dist_name == best_dist else "",
            "AIC":          round(res["aic"], 2),
            "KS stat":      round(res["ks_stat"], 4),
            "KS p-value":   round(res["ks_pvalue"], 4),
        }
        for k, v in res["params"].items():
            row[k] = round(v, 4)
        comp_rows.append(row)

    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
    st.caption(
        "AIC : critère d'information d'Akaike (plus bas = meilleur). "
        "KS p > 0.05 → distribution acceptable."
    )

    st.markdown("---")
    st.markdown("### QQ-plots — Quantiles empiriques vs théoriques")

    sorted_data = np.sort(data_fit)
    n           = len(sorted_data)
    emp_probs   = (np.arange(1, n + 1) - 0.5) / n
    n_dists     = len(fit_results)

    fig_qq = make_subplots(rows=1, cols=n_dists,
                           subplot_titles=[res["label"] for res in fit_results.values()])

    for col_idx, (dist_name, res) in enumerate(fit_results.items(), start=1):
        try:
            theor = res["rv"].ppf(emp_probs)
        except Exception:
            continue
        mask      = np.isfinite(theor)
        theor_ok  = theor[mask]
        emp_ok    = sorted_data[mask]
        color     = DIST_COLORS.get(dist_name, "#999")
        fig_qq.add_trace(go.Scatter(x=theor_ok, y=emp_ok, mode="markers", name=dist_name,
                                    marker=dict(color=color, size=6, opacity=0.8),
                                    showlegend=False,
                                    hovertemplate="Théo=%{x:.0f}<br>Emp=%{y:.0f}<extra></extra>"),
                         row=1, col=col_idx)
        lim = max(theor_ok.max(), emp_ok.max()) * 1.08 if len(theor_ok) else 100
        fig_qq.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines",
                                    line=dict(color="gray", dash="dash", width=1),
                                    showlegend=False),
                         row=1, col=col_idx)
        fig_qq.update_xaxes(title_text="Théorique (m³/s)", row=1, col=col_idx)
        if col_idx == 1:
            fig_qq.update_yaxes(title_text="Empirique (m³/s)", row=1, col=col_idx)

    fig_qq.update_layout(height=380, template="plotly_white", margin=dict(t=50, b=30))
    st.plotly_chart(fig_qq, use_container_width=True)
    st.caption(
        "Points proches de la diagonale = bon ajustement. "
        f"Meilleure distribution (AIC) : **{fit_results[best_dist]['label']}**."
    )

    st.markdown("---")
    st.markdown("### Densités de probabilité (PDF)")

    q_range = np.linspace(max(data_fit.min() * 0.2, 1), data_fit.max() * 1.5, 500)
    fig_pdf = go.Figure()
    fig_pdf.add_trace(go.Histogram(x=data_fit, nbinsx=15, histnorm="probability density",
                                   name="Maxima (empirique)", marker_color="lightgray", opacity=0.5))
    for dist_name, res in fit_results.items():
        if dist_name not in dist_choices:
            continue
        try:
            fig_pdf.add_trace(go.Scatter(
                x=q_range, y=res["rv"].pdf(q_range), mode="lines",
                name=res["label"],
                line=dict(color=DIST_COLORS.get(dist_name, "#999"),
                          width=2.5 if dist_name == best_dist else 1.5,
                          dash="solid" if dist_name == best_dist else "dash"),
            ))
        except Exception:
            pass

    fig_pdf.update_layout(
        xaxis_title="Débit de pointe Q (m³/s)",
        yaxis_title="Densité de probabilité",
        height=350, template="plotly_white",
        legend=dict(orientation="h", y=-0.25),
        margin=dict(t=20, b=80),
    )
    st.plotly_chart(fig_pdf, use_container_width=True)
