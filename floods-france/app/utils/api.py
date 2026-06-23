"""
utils/api.py — Fonctions d'accès aux APIs avec mise en cache Streamlit.

Toutes les fonctions sont décorées avec @st.cache_data pour éviter
de ré-appeler les APIs à chaque interaction utilisateur.
"""

import time
import requests
import pandas as pd
import geopandas as gpd
import numpy as np
import streamlit as st


# ── Encodage ───────────────────────────────────────────────────────────────────
def fix_encoding(s):
    """
    Corrige le double-encodage UTF-8 des APIs Géorisques.
    Ex : 'LodÃ©ve' (latin-1 mal interprété) → 'Lodève'
    """
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def fix_gdf_encoding(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Applique fix_encoding sur toutes les colonnes string d'un GeoDataFrame."""
    for col in gdf.select_dtypes(include="object").columns:
        gdf[col] = gdf[col].apply(fix_encoding)
    return gdf


# ── Endpoints ──────────────────────────────────────────────────────────────────
WFS_GEORISQUES = "https://mapsref.brgm.fr/wxs/georisques/risques"
WMS_GEORISQUES = "https://mapsref.brgm.fr/wxs/georisques/risques"
API_CATNAT     = "https://www.georisques.gouv.fr/api/v1/gaspar/catnat"
API_HUBEAU     = "https://hubeau.eaufrance.fr/api/v2/hydrometrie"
API_GEO        = "https://geo.api.gouv.fr"

# Mots-clés inondation pour filtrer les CatNat
INOND_KEYWORDS = ["inond", "ruissel", "crue", "submers", "débord", "torrent"]

# BBoxes par département [xmin, ymin, xmax, ymax] en WGS84
DEPT_BBOXES = {
    "34": [2.85, 43.21, 3.98, 43.95],
    "30": [3.26, 43.46, 4.85, 44.46],
    "13": [4.23, 43.12, 5.80, 43.94],
    "69": [4.47, 45.46, 5.24, 46.08],
}

DEPT_CENTERS = {
    "34": [43.60, 3.40],
    "30": [43.95, 4.10],
    "13": [43.52, 5.02],
    "69": [45.75, 4.86],
}


def get_bbox_str(dept_code: str) -> str:
    b = DEPT_BBOXES.get(dept_code, DEPT_BBOXES["34"])
    return f"{b[0]},{b[1]},{b[2]},{b[3]}"


def get_center(dept_code: str) -> list:
    return DEPT_CENTERS.get(dept_code, DEPT_CENTERS["34"])


def is_flood(libelle: str) -> bool:
    return any(k in libelle.lower() for k in INOND_KEYWORDS)


# ── API calls ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_communes(dept_code: str) -> gpd.GeoDataFrame:
    """Contours des communes du département via geo.api.gouv.fr."""
    r = requests.get(
        f"{API_GEO}/departements/{dept_code}/communes",
        params={"fields": "nom,code,surface", "format": "geojson", "geometry": "contour"},
        timeout=20,
    )
    r.raise_for_status()
    return gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")


@st.cache_data(ttl=3600, show_spinner=False)
def load_ppri_approuves(dept_code: str) -> gpd.GeoDataFrame:
    """PPRI approuvés depuis WFS Géorisques v1.1.0."""
    r = requests.get(
        WFS_GEORISQUES,
        params={
            "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
            "TYPENAME": "ms:PPRN_COMMUNE_RISQINOND_APPROUV",
            "OUTPUTFORMAT": "geojson", "maxFeatures": 1000,
            "BBOX": get_bbox_str(dept_code),
        },
        timeout=30,
    )
    r.raise_for_status()
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")
    if "cod_commune" in gdf.columns:
        gdf = gdf[gdf["cod_commune"].str.startswith(dept_code)].copy()
    return fix_gdf_encoding(gdf)


@st.cache_data(ttl=3600, show_spinner=False)
def load_ppri_prescrits(dept_code: str) -> gpd.GeoDataFrame:
    """PPRI prescrits depuis WFS Géorisques v1.1.0."""
    r = requests.get(
        WFS_GEORISQUES,
        params={
            "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
            "TYPENAME": "ms:PPRN_COMMUNE_RISQINOND_PRESCRIT",
            "OUTPUTFORMAT": "geojson", "maxFeatures": 1000,
            "BBOX": get_bbox_str(dept_code),
        },
        timeout=30,
    )
    r.raise_for_status()
    gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")
    if "cod_commune" in gdf.columns:
        gdf = gdf[gdf["cod_commune"].str.startswith(dept_code)].copy()
    return fix_gdf_encoding(gdf)


@st.cache_data(ttl=600, show_spinner=False)
def load_catnat(codes_insee: tuple) -> pd.DataFrame:
    """
    Arrêtés CatNat inondation pour un ensemble de communes.
    `codes_insee` doit être un tuple (hashable) pour le cache Streamlit.
    """
    rows = []
    for code in codes_insee:
        try:
            r = requests.get(
                API_CATNAT,
                params={"code_insee": code, "page": 1, "page_size": 200},
                timeout=10,
            )
            if r.status_code == 200:
                for evt in r.json().get("data", []):
                    if is_flood(evt.get("libelle_risque_jo", "")):
                        evt["code_insee"] = code
                        rows.append(evt)
        except Exception:
            pass
        time.sleep(0.05)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["annee"] = pd.to_datetime(
            df["date_debut_evt"], dayfirst=True, errors="coerce"
        ).dt.year
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_stations(dept_code: str) -> gpd.GeoDataFrame:
    """Stations hydrométrie en service depuis Hub'Eau v2."""
    r = requests.get(
        f"{API_HUBEAU}/referentiel/stations",
        params={"code_departement": dept_code, "size": 200, "en_service": "true"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json().get("data", []))
    if df.empty:
        return gpd.GeoDataFrame(columns=["code_station", "libelle_station",
                                          "libelle_cours_eau", "geometry"])
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude_station"], df["latitude_station"]),
        crs="EPSG:4326",
    ).dropna(subset=["longitude_station", "latitude_station"])


@st.cache_data(ttl=86400, show_spinner=False)
def load_dept_boundary(dept_code: str):
    """
    Contour du département (GeoDataFrame, 1 ligne) par dissolve des communes.

    Utilise geo.api.gouv.fr. Mis en cache 24 h (les limites départementales
    ne changent pas). Retourne None en cas d'erreur.
    """
    try:
        r = requests.get(
            f"{API_GEO}/departements/{dept_code}/communes",
            params={"fields": "code", "format": "geojson", "geometry": "contour"},
            timeout=20,
        )
        r.raise_for_status()
        gdf = gpd.GeoDataFrame.from_features(r.json()["features"], crs="EPSG:4326")
        return gdf.dissolve().reset_index(drop=True)
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def load_observations(
    station_code: str,
    grandeur: str = "H",
    nb_jours: int = 7,
) -> pd.DataFrame:
    """
    Observations temps réel depuis Hub'Eau v2 (observations_tr).

    Parameters
    ----------
    nb_jours : int
        Fenêtre temporelle en jours (défaut 7 jours).
        Hub'Eau retourne au maximum size=5000 observations.

    Unités Hub'Eau v2 :
    - H (hauteur) : mm  → ÷ 1000 → m
    - Q (débit)   : L/s → ÷ 1000 → m³/s
    """
    from datetime import datetime, timedelta, timezone

    now        = datetime.now(timezone.utc)
    date_debut = (now - timedelta(days=nb_jours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    size       = min(nb_jours * 200, 5_000)   # ~96 obs/jour à 15 min; marge x2

    r = requests.get(
        f"{API_HUBEAU}/observations_tr",
        params={
            "code_entite":     station_code,
            "grandeur_hydro":  grandeur,
            "date_debut_obs":  date_debut,
            "size":            size,
        },
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if r.status_code not in [200, 206]:
        return pd.DataFrame()
    df = pd.DataFrame(r.json().get("data", []))
    if df.empty or "date_obs" not in df.columns:
        return pd.DataFrame()
    df["date_obs"]     = pd.to_datetime(df["date_obs"])
    df["resultat_obs"] = pd.to_numeric(df["resultat_obs"], errors="coerce")
    # Hub'Eau retourne H en mm et Q en L/s → conversion vers m et m³/s
    df["resultat_obs"] = df["resultat_obs"] / 1000.0
    return df.dropna(subset=["resultat_obs"]).sort_values("date_obs")


@st.cache_data(ttl=3600, show_spinner=False)
def load_obs_elab(
    station_code: str,
    grandeur: str = "QIXnJ",
    size: int = 10_000,
) -> pd.DataFrame:
    """
    Observations élaborées long terme depuis Hub'Eau v2 (obs_elab).

    Grandeurs courantes
    -------------------
    QIXnJ  — débit maximum journalier (L/s → converti en m³/s)
    QmJ    — débit moyen journalier  (L/s → converti en m³/s)
    QmM    — débit moyen mensuel     (L/s → converti en m³/s)
    QIXM   — débit max mensuel       (L/s → converti en m³/s)
    HIXnJ  — hauteur maximale journalière (mm → converti en m)
    HIXM   — hauteur maximale mensuelle   (mm → converti en m)

    Returns
    -------
    pd.DataFrame avec colonnes date_obs_elab (datetime) et resultat_obs_elab (float).
    Vide si la station ne dispose pas de cette grandeur.
    """
    r = requests.get(
        f"{API_HUBEAU}/obs_elab",
        params={
            "code_entite":       station_code,
            "grandeur_hydro_elab": grandeur,
            "size":              size,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if r.status_code not in [200, 206]:
        return pd.DataFrame()

    df = pd.DataFrame(r.json().get("data", []))
    if df.empty or "date_obs_elab" not in df.columns:
        return pd.DataFrame()

    df["date_obs_elab"] = pd.to_datetime(df["date_obs_elab"])
    df["resultat_obs_elab"] = pd.to_numeric(df["resultat_obs_elab"], errors="coerce")

    # Hub'Eau fournit Q en L/s et H en mm → conversion vers m³/s et m (÷ 1000)
    df["resultat_obs_elab"] = df["resultat_obs_elab"] / 1000.0

    return df.dropna(subset=["resultat_obs_elab"]).sort_values("date_obs_elab")


# ── Données enrichies ─────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def build_communes_ppri(dept_code: str) -> gpd.GeoDataFrame:
    """
    Communes enrichies avec le nombre de procédures PPRI.
    Combine load_communes + load_ppri_approuves.
    """
    gdf_communes = load_communes(dept_code)
    gdf_ppri     = load_ppri_approuves(dept_code)

    ppri_agg = (
        gdf_ppri.groupby("cod_commune")
        .agg(
            nb_ppri=("lib_pprn", "count"),
            ppri_noms=("lib_pprn", lambda x: ", ".join(x.unique()[:3])),
        )
        .reset_index()
    )
    gdf = gdf_communes.merge(
        ppri_agg, left_on="code", right_on="cod_commune", how="left"
    )
    gdf["nb_ppri"] = gdf["nb_ppri"].fillna(0).astype(int)
    gdf["statut"]  = gdf["nb_ppri"].apply(lambda x: "Avec PPRI" if x > 0 else "Sans PPRI")
    return gdf
