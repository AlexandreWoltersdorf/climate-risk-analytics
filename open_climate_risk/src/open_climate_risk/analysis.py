"""Risk analysis: damage functions, EAD, ensemble extraction."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from .config import RETURN_PERIODS, GCM_LABELS
from .data import (
    extract_hazard_depths, aqueduct_source, batch_sample_raster,
    coastal_source,
)


# ── Damage function ────────────────────────────────────────────────────────────

def build_damage_function(jrc_curves: dict, asset_type: str) -> interp1d:
    """Return a callable f(depth_m) → damage_fraction for the given asset type.

    Prepends (0, 0) if JRC curve doesn't start at depth=0.
    """
    curve  = jrc_curves[asset_type]
    depths = curve['depth_m'].copy()
    fracs  = curve['damage_fraction'].copy()
    if depths[0] > 0.0:
        depths = np.concatenate([[0.0], depths])
        fracs  = np.concatenate([[0.0], fracs])
    return interp1d(depths, fracs, kind='linear', bounds_error=False,
                    fill_value=(0.0, 1.0))


def apply_damage(
    df_hazard: pd.DataFrame,
    jrc_curves: dict,
    asset: dict,
) -> pd.DataFrame:
    """Apply JRC damage function to hazard depths → df_risk DataFrame."""
    damage_fn = build_damage_function(jrc_curves, asset['asset_type'])
    depths = df_hazard['flood_depth_m'].values
    fracs  = damage_fn(depths)
    df = df_hazard.copy()
    df['damage_fraction'] = fracs
    df['damage_eur']      = fracs * asset['value_eur']
    return df


# ── EAD ───────────────────────────────────────────────────────────────────────

def compute_ead(
    exceedance_probs: np.ndarray,
    damages: np.ndarray,
    include_tail: bool = True,
) -> float:
    """Expected Annual Damage via trapezoidal integration over the exceedance curve."""
    idx = np.argsort(exceedance_probs)[::-1]
    p, d = exceedance_probs[idx], damages[idx]
    if p[0] < 1.0:
        p = np.concatenate([[1.0], p])
        d = np.concatenate([[0.0], d])
    _trapz = getattr(np, 'trapezoid', np.trapz)  # numpy >=2.0 compat
    ead = float(_trapz(d, p)) * -1
    if include_tail:
        ead += float(d[-1] * p[-1])
    return ead


def compute_ead_from_df(df_risk: pd.DataFrame, asset: dict) -> tuple[float, float]:
    """Convenience: (ead [€/an], ead_pct [%/an]) from a df_risk DataFrame."""
    ead = compute_ead(
        df_risk['exceedance_prob_yr'].values,
        df_risk['damage_eur'].values,
    )
    ead_pct = ead / asset['value_eur'] * 100
    return ead, ead_pct


# ── Ensemble extraction ────────────────────────────────────────────────────────

def _extract_single_scenario(
    sc: dict,
    asset: dict,
    jrc_curves: dict,
    return_periods: np.ndarray,
    data_dir: Path,
) -> dict:
    """Extract depths + damages + EAD for all GCMs in one scenario."""
    exceedance_probs = 1.0 / return_periods
    damage_fn = build_damage_function(jrc_curves, asset['asset_type'])

    all_depths, all_damages, all_eads = [], [], []
    depths_per_model, damages_per_model = {}, {}

    for model in sc['models']:
        depths_m  = extract_hazard_depths(
            asset['lon'], asset['lat'], return_periods, data_dir,
            scenario=sc['scenario'], model=model, year=sc['year'],
        )
        damages_m = damage_fn(depths_m) * asset['value_eur']
        ead_m     = compute_ead(exceedance_probs, damages_m)

        all_depths.append(depths_m)
        all_damages.append(damages_m)
        all_eads.append(ead_m if not np.isnan(ead_m) else 0.0)
        depths_per_model[model]  = depths_m
        damages_per_model[model] = damages_m

    depths_arr  = np.array(all_depths)
    damages_arr = np.array(all_damages)

    return {
        **sc,
        'depths_median':  np.nanmedian(depths_arr,  axis=0),
        'depths_min':     np.nanmin(depths_arr,     axis=0),
        'depths_max':     np.nanmax(depths_arr,     axis=0),
        'damages_median': np.nanmedian(damages_arr, axis=0),
        'damages_min':    np.nanmin(damages_arr,    axis=0),
        'damages_max':    np.nanmax(damages_arr,    axis=0),
        'ead_median': float(np.nanmedian(all_eads)),
        'ead_min':    float(np.nanmin(all_eads)),
        'ead_max':    float(np.nanmax(all_eads)),
        'ead_per_model':    dict(zip(sc['models'], all_eads)),
        'depths_per_model':  depths_per_model,
        'damages_per_model': damages_per_model,
    }


def extract_ensemble(
    scenarios: list,
    asset: dict,
    jrc_curves: dict,
    return_periods: np.ndarray = None,
    data_dir: Path = None,
) -> list:
    """Run extraction for every scenario. Returns list of result dicts."""
    from .config import DATA_DIR
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    data_dir = data_dir or DATA_DIR
    print('Extraction des données...')
    results = [_extract_single_scenario(sc, asset, jrc_curves, return_periods, data_dir)
               for sc in scenarios]
    print_ensemble_summary(results)
    return results


# ── Coastal scenarios ──────────────────────────────────────────────────────────

def extract_coastal_scenarios(
    scenarios: list,
    asset: dict,
    jrc_curves: dict,
    return_periods: np.ndarray = None,
    data_dir=None,
) -> list:
    """Extract coastal flood depths + damages for each scenario.

    Unlike river ensemble (5 GCMs), each coastal scenario is a single
    deterministic run (subsidence × projection). Results share the same
    dict format as extract_ensemble() for plot compatibility.
    """
    from .config import DATA_DIR as _DD
    from .data import extract_coastal_depths
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    data_dir = data_dir or _DD
    exceedance_probs = 1.0 / return_periods
    damage_fn = build_damage_function(jrc_curves, asset['asset_type'])

    results = []
    print('Extraction coastal...')
    for sc in scenarios:
        depths = extract_coastal_depths(
            asset['lon'], asset['lat'], return_periods, data_dir,
            scenario=sc['scenario'], subsidence=sc['subsidence'],
            year=sc['year'], projection=sc['projection'],
        )
        damages = damage_fn(depths) * asset['value_eur']
        ead_val = compute_ead(exceedance_probs, damages)

        results.append({
            **sc,
            'models': [f'{sc["subsidence"]}/{sc["projection"]}'],
            'depths_median':  depths,
            'depths_min':     depths,
            'depths_max':     depths,
            'damages_median': damages,
            'damages_min':    damages,
            'damages_max':    damages,
            'ead_median': ead_val,
            'ead_min':    ead_val,
            'ead_max':    ead_val,
            'ead_per_model': {f'{sc["subsidence"]}/{sc["projection"]}': ead_val},
            'depths_per_model':  {f'{sc["subsidence"]}/{sc["projection"]}': depths},
            'damages_per_model': {f'{sc["subsidence"]}/{sc["projection"]}': damages},
        })

    # Print summary
    bl = results[0]['ead_median']
    hdr_sc, hdr_ead, hdr_d = 'Sc\u00e9nario', 'EAD', '\u0394 vs baseline'
    print(f'\n{hdr_sc:<35} {hdr_ead:>12}  {hdr_d:>14}')
    print('-' * 65)
    for r in results:
        delta = '  (baseline)' if r is results[0] \
            else f'  ({(r["ead_median"]-bl)/bl*100:+.1f}%)' if bl > 0 else '  (N/A)'
        print(f'{r["label"]:<35} {r["ead_median"]:>12,.0f}  {delta}')
    print()
    return results


# ── Portfolio ──────────────────────────────────────────────────────────────────

def run_portfolio(
    assets: list,
    jrc_curves: dict,
    return_periods: np.ndarray = None,
    data_dir=None,
    scenarios: list = None,
) -> pd.DataFrame:
    """Batch portfolio flood risk analysis.

    Opens each raster file only once and samples all assets — much faster
    than looping extract_hazard_depths() per asset.

    Returns a DataFrame with one row per asset and EAD columns.
    """
    from .config import DATA_DIR as _DATA_DIR
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    data_dir = data_dir or _DATA_DIR
    exceedance_probs = 1.0 / return_periods
    n = len(assets)

    lons = [a['lon'] for a in assets]
    lats = [a['lat'] for a in assets]

    # Cache one damage function per asset type
    dmg_fns = {}
    for a in assets:
        t = a['asset_type']
        if t not in dmg_fns:
            dmg_fns[t] = build_damage_function(jrc_curves, t)

    # ── Historical baseline ───────────────────────────────────────────────
    print(f'Analyse historique — {n} actifs x {len(return_periods)} RP...')
    depth_matrix = np.zeros((n, len(return_periods)))
    for j, rp in enumerate(return_periods):
        src = aqueduct_source(int(rp), data_dir=data_dir)
        depth_matrix[:, j] = batch_sample_raster(src, lons, lats)
    print('  Hazard extraction OK')

    rows = []
    for i, a in enumerate(assets):
        depths = depth_matrix[i]
        damages = dmg_fns[a['asset_type']](depths) * a['value_eur']
        ead_val = compute_ead(exceedance_probs, damages)
        row = {k: a[k] for k in a}
        row['ead_historical'] = ead_val
        row['ead_pct_historical'] = ead_val / a['value_eur'] * 100
        row['max_depth_m'] = float(np.nanmax(depths))
        rows.append(row)

    # ── Climate scenarios ─────────────────────────────────────────────────
    if scenarios:
        future = [s for s in scenarios if len(s['models']) > 1]
        for sc in future:
            key = sc['scenario']
            n_models = len(sc['models'])
            print(f'\n{sc["label"]} — {n_models} GCMs...')
            ead_all = np.zeros((n, n_models))

            for m_idx, model in enumerate(sc['models']):
                dm = np.zeros((n, len(return_periods)))
                for j, rp in enumerate(return_periods):
                    src = aqueduct_source(int(rp), sc['scenario'], model, sc['year'], data_dir)
                    dm[:, j] = batch_sample_raster(src, lons, lats)
                for i, a in enumerate(assets):
                    damages = dmg_fns[a['asset_type']](dm[i]) * a['value_eur']
                    ead_all[i, m_idx] = compute_ead(exceedance_probs, damages)
                print(f'  {model} done')

            for i in range(n):
                rows[i][f'ead_{key}_median'] = float(np.nanmedian(ead_all[i]))
                rows[i][f'ead_{key}_min']    = float(np.nanmin(ead_all[i]))
                rows[i][f'ead_{key}_max']    = float(np.nanmax(ead_all[i]))

    df = pd.DataFrame(rows)
    print(f'\nPortfolio analysé : {n} actifs, '
          f'EAD total historique = {df["ead_historical"].sum():,.0f} EUR/an')
    return df


def run_coastal_portfolio(
    assets: list,
    jrc_curves: dict,
    return_periods: np.ndarray = None,
    data_dir=None,
    scenarios: list = None,
) -> pd.DataFrame:
    """Batch coastal flood risk analysis across a portfolio.

    Same design as run_portfolio() but uses coastal_source() for each
    scenario config (subsidence × projection). No GCM ensemble — each
    scenario is deterministic.
    """
    from .config import DATA_DIR as _DATA_DIR
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    data_dir = data_dir or _DATA_DIR
    exceedance_probs = 1.0 / return_periods
    n = len(assets)

    lons = [a['lon'] for a in assets]
    lats = [a['lat'] for a in assets]

    # Cache one damage function per asset type
    dmg_fns = {}
    for a in assets:
        t = a['asset_type']
        if t not in dmg_fns:
            dmg_fns[t] = build_damage_function(jrc_curves, t)

    if not scenarios:
        raise ValueError('scenarios is required for run_coastal_portfolio')

    rows = [{k: a[k] for k in a} for a in assets]
    baseline_ead = None

    for sc_idx, sc in enumerate(scenarios):
        lbl = sc['label']
        key = f'{sc["scenario"]}_{sc["subsidence"]}'
        print(f'\n{lbl}...')

        depth_matrix = np.zeros((n, len(return_periods)))
        for j, rp in enumerate(return_periods):
            src = coastal_source(
                int(rp), sc['scenario'], sc['subsidence'],
                sc['year'], sc['projection'], data_dir,
            )
            depth_matrix[:, j] = batch_sample_raster(src, lons, lats)

        for i, a in enumerate(assets):
            depths = depth_matrix[i]
            damages = dmg_fns[a['asset_type']](depths) * a['value_eur']
            ead_val = compute_ead(exceedance_probs, damages)
            rows[i][f'ead_{key}'] = ead_val
            rows[i][f'ead_pct_{key}'] = ead_val / a['value_eur'] * 100
            rows[i][f'max_depth_{key}'] = float(np.nanmax(depths))

        if sc_idx == 0:
            baseline_ead = sum(rows[i][f'ead_{key}'] for i in range(n))

        print(f'  OK — EAD total = {sum(rows[i][f"ead_{key}"] for i in range(n)):,.0f} EUR/an')

    # Add convenience aliases for first scenario as 'historical'
    first_key = f'{scenarios[0]["scenario"]}_{scenarios[0]["subsidence"]}'
    for i in range(n):
        rows[i]['ead_historical'] = rows[i][f'ead_{first_key}']
        rows[i]['ead_pct_historical'] = rows[i][f'ead_pct_{first_key}']
        rows[i]['max_depth_m'] = rows[i][f'max_depth_{first_key}']

    df = pd.DataFrame(rows)
    print(f'\nPortfolio côtier analysé : {n} actifs, '
          f'EAD total baseline = {df["ead_historical"].sum():,.0f} EUR/an')
    return df


# ── Print helpers ──────────────────────────────────────────────────────────────

def print_summary(
    asset: dict,
    df_risk: pd.DataFrame,
    ead: float,
    ead_pct: float,
) -> None:
    """Print a formatted risk summary table."""
    print('=' * 60)
    print('  FLOOD RISK SCREENING — SUMMARY')
    print('=' * 60)
    print(f'  Asset      : {asset["name"]}')
    print(f'  Location   : {asset["lon"]:.4f}°E, {asset["lat"]:.4f}°N')
    print(f'  Type       : {asset["asset_type"]}')
    print(f'  Value      : {asset["value_eur"]:,} €')
    print(f'  Floor area : {asset["floor_area_m2"]} m²')
    print()
    print(f'  {"T [yr]":>8}  {"Depth [m]":>10}  {"Damage frac":>12}  {"Damage [€]":>12}')
    print('  ' + '-' * 48)
    for _, row in df_risk.iterrows():
        print(f'  {row.return_period_yr:>8.0f}  '
              f'{row.flood_depth_m:>10.2f}  '
              f'{row.damage_fraction:>11.1%}  '
              f'{row.damage_eur:>12,.0f}')
    print()
    print(f'  EAD (historical baseline) : {ead:>10,.0f} €/year')
    print(f'  EAD / Asset value         : {ead_pct:>10.3f} %/year')
    print('=' * 60)


def print_ensemble_summary(results: list) -> None:
    """Print EAD comparison table across scenarios."""
    bl_ead = results[0]['ead_median']
    print(f'\n{"Scénario":<25} {"EAD médiane":>12}  {"min":>10}  {"max":>10}  {"Δ vs baseline":>14}')
    print('-' * 77)
    for r in results:
        delta = '  (baseline)' if r['label'] == results[0]['label'] \
            else f'  ({(r["ead_median"]-bl_ead)/bl_ead*100:+.1f}%)'
        print(f'{r["label"]:<25} {r["ead_median"]:>12,.0f}  '
              f'{r["ead_min"]:>10,.0f}  {r["ead_max"]:>10,.0f}  {delta}')

    print()
    for r in results[1:]:
        print(f'  [{r["label"]}] — EAD par GCM :')
        max_ead = max(r['ead_per_model'].values()) or 1.0
        for model, val in sorted(r['ead_per_model'].items(), key=lambda x: -x[1]):
            bar = '█' * int(val / max_ead * 20)
            print(f'    {GCM_LABELS.get(model, model):<10} {val:>10,.0f} €/yr  {bar}')
        print()
