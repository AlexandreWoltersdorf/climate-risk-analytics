# Open Climate Risk

Open-source climate physical risk screening toolkit.

## Architecture

```
src/open_climate_risk/   # Package Python installable
  config.py              # Constantes, chemins, scénarios, GCMs
  data.py                # I/O rasters Aqueduct (S3 COG), courbes JRC, portfolios
  analysis.py            # Fonctions de dommage, EAD, extraction ensemble
  plot.py                # Visualisations matplotlib
  report.py              # Génération rapports Word/Excel

notebooks/               # Exploration et analyses (numérotés)
tests/                   # Pytest, fixtures dans conftest.py
data/                    # Données locales (portfolios, rasters téléchargés)
references/              # Courbes de vulnérabilité JRC Huizinga 2017
outputs/                 # Rapports et figures générés (gitignored)
```

## Stack technique

- **Python 3.11+** — conda env `climate`
- **Géospatial** : rasterio, geopandas, shapely, contextily
- **Data** : numpy, pandas, scipy, xarray, xesmf
- **Climat** : climada, cdsapi (ERA5/CMIP6 via CDS)
- **Viz** : matplotlib
- **Rapports** : python-docx, openpyxl

## Données sources

| Composant | Dataset | Résolution |
|-----------|---------|------------|
| Aléa inondation | WRI Aqueduct Floods v2 (S3 COG) | ~1 km |
| Vulnérabilité | JRC Huizinga et al. 2017 | Régional |
| Climat historique | ERA5 (CDS API) | 0.25° |
| Projections | CMIP6 (CDS API) | Variable (~1-2°) |
| GCMs Aqueduct | ISIMIP2b — 5 modèles, RCP 4.5/8.5 | ~1 km |

## Conventions

- Langue du code : **anglais** (variables, fonctions, docstrings)
- Langue des notebooks : **français** (markdown, commentaires d'analyse)
- Notebooks numérotés : `01_`, `02_`, etc.
- Un notebook = un sujet d'exploration
- Code mature extrait dans `src/open_climate_risk/`
- Tests avec pytest, fixtures partagées dans `conftest.py`

## Commandes utiles

```bash
conda activate climate
pytest tests/ -v
jupyter lab
```

## Contexte projet

- Screening de risque physique climatique (inondation fluviale + côtière)
- Basé sur données publiques open-source
- Workflow : aléa (Aqueduct) → vulnérabilité (JRC) → EAD (intégration trapézoïdale)
- Scénarios : historique (WATCH) vs RCP 4.5/8.5 à 2050, ensemble de 5 GCMs
- En cours : ajout indicateurs climatiques projetés CMIP6 × ERA5, exploration CLIMADA
