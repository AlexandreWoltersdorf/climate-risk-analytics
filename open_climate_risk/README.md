# Open Climate Risk

Open-source climate physical risk screening toolkit. Assess flood risk exposure for any asset worldwide using public datasets.

![Flood Risk Screening](outputs/flood_risk_screening.png)

## What it does

Given an **asset** (location, type, value), the toolkit:

1. **Extracts flood hazard** from [WRI Aqueduct Floods v2](https://www.wri.org/aqueduct) (9 return periods, ~1 km resolution)
2. **Applies vulnerability curves** from [JRC Huizinga et al. 2017](https://publications.jrc.ec.europa.eu/repository/handle/JRC105688) (depth-damage functions by asset type)
3. **Computes Expected Annual Damage (EAD)** via trapezoidal integration over the exceedance probability curve
4. **Compares climate scenarios** — RCP 4.5 / 8.5 at 2050, ensemble of 5 ISIMIP2b GCMs (median + min/max spread)
5. **Generates reports** — Word (.docx) and Excel (.xlsx) with all figures and data

## Quick start

```bash
# Clone
git clone https://github.com/<your-org>/open-climate-risk.git
cd open-climate-risk

# Install
pip install -e .
# or: pip install -r requirements.txt

# Launch
jupyter notebook notebooks/01_riverine_flood_risk.ipynb
```

No data download required — the notebook streams Aqueduct GeoTIFFs directly from WRI's S3 (Cloud-Optimized GeoTIFF). For faster repeated runs, download the rasters locally (~7 GB):

```bash
# Optional: bulk download historical + future scenarios
python -c "
from open_climate_risk.data import aqueduct_source, aqueduct_filename
from open_climate_risk.config import RETURN_PERIODS, SCENARIOS, DATA_DIR
print(f'Download dir: {DATA_DIR}')
# Use curl/wget on the S3 URLs printed by check_availability()
"
```

## Project structure

```
open_climate_risk/
  pyproject.toml          Project metadata & dependencies
  requirements.txt        Pinned dependencies for pip
  src/open_climate_risk/  Python package
    config.py               Constants, paths, GCMs, scenarios
    data.py                 Aqueduct raster I/O, JRC curve loading
    analysis.py             EAD computation, damage, ensemble extraction
    plot.py                 All matplotlib figures
    report.py               Word & Excel report generation
  notebooks/
    01_riverine_flood_risk.ipynb   Main screening notebook
  data/aqueduct/            Aqueduct GeoTIFFs (not in repo, streamed or downloaded)
  references/               JRC Excel vulnerability curves
  outputs/                  Generated figures, CSV, reports
  tests/                    Unit tests
```

## Usage in the notebook

The notebook requires only **one user input** — the asset definition:

```python
ASSET = {
    'name':          'Example asset — Paris',
    'lon':           2.3488,
    'lat':           48.8534,
    'asset_type':    'residential',   # residential | commercial | industrial | agriculture | transport
    'value_eur':     500_000,
    'floor_area_m2': 120,
}
```

Then run all cells. Every computation calls the `open_climate_risk` package:

```python
import open_climate_risk.data     as ocr_data
import open_climate_risk.analysis as ocr_analysis
import open_climate_risk.plot     as ocr_plot
import open_climate_risk.report   as ocr_report

df_hazard = ocr_data.extract_hazard_df(ASSET, RETURN_PERIODS)
df_risk   = ocr_analysis.apply_damage(df_hazard, JRC_CURVES, ASSET)
ead, pct  = ocr_analysis.compute_ead_from_df(df_risk, ASSET)

ocr_plot.risk_screening(df_risk, ead, pct, ASSET)
ocr_report.generate_word(ASSET, df_risk, ead, pct, results)
```

## Data sources

| Component     | Dataset                              | Resolution | License        |
|---------------|--------------------------------------|------------|----------------|
| Hazard        | WRI Aqueduct Floods v2 (riverine)    | ~1 km      | CC BY 4.0      |
| Vulnerability | JRC Huizinga et al. 2017             | Regional   | Public domain  |
| Climate       | ISIMIP2b — 5 GCMs, RCP 4.5 & 8.5    | ~1 km      | CC BY 4.0      |

**GCMs used:** MIROC-ESM-CHEM, NorESM1-M, GFDL-ESM2M, HadGEM2-ES, IPSL-CM5A-LR

## Limitations

- Aqueduct resolution (~1 km) may miss local flood features — use local hydraulic models for detailed assessment
- JRC curves are regional averages — site-specific surveys improve accuracy
- Single-asset analysis — no portfolio diversification effects
- 2050 horizon only — scenario divergence increases at 2080+

## Roadmap

- [ ] FastAPI + PostGIS geospatial API for programmatic access
- [ ] Portfolio-level aggregation
- [ ] Additional hazards (coastal flood, heat stress, drought)
- [ ] CLIMADA integration for advanced probabilistic modelling

## License

MIT License. See [LICENSE](LICENSE).

## References

- Ward, P.J. et al. (2020). *Aqueduct Floods Methodology*. Technical Note. WRI.
- Huizinga, J., de Moel, H. & Szewczyk, W. (2017). *Global flood depth-damage functions*. EUR 28552 EN. JRC.
