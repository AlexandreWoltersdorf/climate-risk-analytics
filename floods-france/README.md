# Floods France — Analyse du risque inondation

Analyse du risque inondation en France (département pilote : **Hérault — 34**).

## Structure

```
notebooks/
├── 00_data_inventory.ipynb         ← Inventaire & accès aux données
├── 01_hazard/                      ← Cartes d'aléa, fréquence, détection satellite
├── 02_terrain/                     ← DEM, bassins versants
├── 03_simulation_2D/               ← HydroMT-SFINCS, SWMM
├── 04_exposure/                    ← Bâtiments, population, valeurs
├── 05_vulnerability/               ← Courbes JRC / CLIMAAX
├── 06_risk/                        ← Cartographie risque, pertes €
└── 07_future/                      ← Projections climatiques, pluies extrêmes
```

## Types d'inondations couverts
- **Fluviale** : débordement cours d'eau
- **Côtière** : submersion marine
- **Pluviale** : ruissellement direct / urbain

## Installation

```bash
pip install requests geopandas pandas matplotlib folium shapely pyproj
pip install osmnx rioxarray pysheds whitebox
pip install hydromt hydromt_sfincs pyswmm
pip install lmoments3 spotpy AI4Water
```

## Sources de données principales
| Catégorie | Source | Accès |
|-----------|--------|-------|
| Hazard | Géorisques, TRI, GASPAR | Libre |
| Terrain | Copernicus DEM 30m, IGN RGE ALTI | Libre |
| Exposure | BD TOPO, OSM, FILOSOFI, DVF | Libre |
| Vulnerability | JRC Huizinga 2017, CLIMAAX | Libre |
| Rainfall | ERA5, GPM IMERG | Libre (compte CDS) |
