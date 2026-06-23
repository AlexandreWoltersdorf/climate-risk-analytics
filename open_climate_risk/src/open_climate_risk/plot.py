"""Visualization: all matplotlib figures for flood risk screening."""
import math
import os
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import contextily as ctx
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy.ndimage import map_coordinates
import rasterio
from rasterio.mask import mask as rio_mask
from shapely.geometry import box, mapping

from .config import OUTPUTS_DIR, RETURN_PERIODS, GCM_LABELS, GCM_COLORS
from .data import aqueduct_source

# ── Web Mercator helpers (pure numpy — no PROJ) ────────────────────────────────
_R = 6_378_137.0

def _lon2x(lon): return _R * np.radians(lon)
def _lat2y(lat): return _R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
def _x2lon(x):   return np.degrees(x / _R)
def _y2lat(y):   return np.degrees(2 * np.arctan(np.exp(y / _R)) - np.pi / 2)


def _outputs(outputs_dir) -> Path:
    d = Path(outputs_dir) if outputs_dir else OUTPUTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Asset location map ─────────────────────────────────────────────────────────

def asset_location(
    asset: dict,
    buf_m: float = 1500,
    outputs_dir: Path = None,
) -> str:
    """Plot asset location on a contextily basemap. Saves asset_location.png."""
    lon, lat = asset['lon'], asset['lat']
    cx, cy = _lon2x(lon), _lat2y(lat)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_xlim(cx - buf_m, cx + buf_m)
    ax.set_ylim(cy - buf_m * 0.83, cy + buf_m * 0.83)
    ax.plot(cx, cy, marker='*', color='#e63946', markersize=26,
            markeredgecolor='white', markeredgewidth=1.5, zorder=5)
    try:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=15)
    except Exception:
        ctx.add_basemap(ax, zoom=15)
    ax.set_title(f'{asset["name"]} \u2014 Localisation\n'
                 f'{lon:.4f}\u00b0E, {lat:.4f}\u00b0N',
                 fontsize=12, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'asset_location.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Localisation : {lon:.4f}\u00b0E, {lat:.4f}\u00b0N')
    return out


# ── Hazard maps ────────────────────────────────────────────────────────────────

def hazard_map(
    asset: dict,
    rp_map: int = 500,
    buffer_deg: float = 0.1,
    upsample: int = 2,
    data_dir: Path = None,
    outputs_dir: Path = None,
) -> tuple[str, str]:
    """Plot smooth + raw hazard maps. Returns (smooth_path, raw_path)."""
    source = aqueduct_source(rp_map, data_dir=data_dir)
    print(f'Source raster : {source}')

    bbox_geom = box(
        asset['lon'] - buffer_deg, asset['lat'] - buffer_deg,
        asset['lon'] + buffer_deg, asset['lat'] + buffer_deg,
    )
    with rasterio.open(source) as src:
        nodata_val = src.nodata
        out_image, out_transform = rio_mask(src, [mapping(bbox_geom)], crop=True)

    data = out_image[0].astype(float)
    if nodata_val is not None:
        data[data == nodata_val] = np.nan
    data[data < 0] = np.nan

    h, w = data.shape
    lon_min = out_transform.c
    lat_max = out_transform.f
    lon_max = lon_min + out_transform.a * w
    lat_min = lat_max + out_transform.e * h

    x_min, x_max = _lon2x(lon_min), _lon2x(lon_max)
    y_min, y_max = _lat2y(lat_min), _lat2y(lat_max)
    cx, cy = _lon2x(asset['lon']), _lat2y(asset['lat'])
    half = max(x_max - x_min, y_max - y_min) / 2
    x0, x1 = cx - half, cx + half
    y0, y1 = cy - half, cy + half

    def _resample(n_cols, n_rows, order):
        xs = np.linspace(x0, x1, n_cols)
        ys = np.linspace(y1, y0, n_rows)
        xx, yy = np.meshgrid(xs, ys)
        col_f = (_x2lon(xx) - lon_min) / out_transform.a
        row_f = (_y2lat(yy) - lat_max) / out_transform.e
        out = map_coordinates(data, [row_f.ravel(), col_f.ravel()],
                              order=order, mode='constant', cval=np.nan,
                              prefilter=False).reshape(n_rows, n_cols)
        out[out < 0] = np.nan
        return out

    data_smooth = _resample(w * upsample, h * upsample, order=1)
    data_raw    = _resample(w, h, order=0)

    colors_flood = [
        (0.529, 0.808, 0.922, 0.0),
        (0.529, 0.808, 0.922, 0.65),
        (0.118, 0.565, 1.000, 0.75),
        (1.000, 0.600, 0.000, 0.80),
        (0.800, 0.000, 0.000, 0.85),
    ]
    cmap_flood = mcolors.LinearSegmentedColormap.from_list('flood', colors_flood, N=256)
    cmap_flood.set_bad(alpha=0)
    all_pos = data_raw[data_raw > 0]
    vmax = float(np.nanpercentile(all_pos, 98)) if all_pos.size > 0 else 2.0

    def _masked(arr):
        return np.ma.masked_where(np.isnan(arr) | (arr <= 0), arr)

    out_dir = _outputs(outputs_dir)

    def _draw(arr, title, fname):
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom='auto', zorder=1)
        im = ax.imshow(_masked(arr), extent=[x0, x1, y0, y1],
                       cmap=cmap_flood, vmin=0, vmax=vmax, zorder=2, interpolation='nearest')
        ax.scatter(cx, cy, color='#D32F2F', s=220, zorder=5,
                   marker='*', edgecolors='white', linewidths=1.5)
        ax.annotate(f'  {asset["name"]}', xy=(cx, cy), xytext=(8, 8),
                    textcoords='offset points', fontsize=9, color='#D32F2F',
                    fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                              alpha=0.85, edgecolor='#D32F2F'), zorder=6)
        div = make_axes_locatable(ax)
        plt.colorbar(im, cax=div.append_axes('right', size='4%', pad=0.08))\
            .set_label('Profondeur [m]', fontsize=9)
        ax.set_title(f'Aléa inondation fluviale — T\u202f=\u202f{rp_map} ans  |  {asset["name"]}\n{title}',
                     fontsize=11, pad=8)
        ax.set_axis_off()
        plt.tight_layout()
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        plt.show()
        print(f'Carte sauvegardée \u2192 {fname}')

    smooth_path = str(out_dir / f'hazard_map_T{rp_map}_smooth.png')
    raw_path    = str(out_dir / f'hazard_map_T{rp_map}_raw.png')
    _draw(data_smooth, f'Interpolation bilinéaire (\u00d7{upsample} suréchantillonnage)', smooth_path)
    _draw(data_raw, f'Données brutes Aqueduct (~1\u202fkm/pixel, {h}\u00d7{w} pixels)',  raw_path)
    return smooth_path, raw_path


# ── JRC curves ─────────────────────────────────────────────────────────────────

def jrc_curves(
    jrc_curves_dict: dict,
    asset_type: str,
    outputs_dir: Path = None,
) -> str:
    """Plot all JRC damage curves, highlighting the selected asset type."""
    from .analysis import build_damage_function
    d_range = np.linspace(0, 6.5, 300)

    fig, ax = plt.subplots(figsize=(9, 5))
    for atype, curve in jrc_curves_dict.items():
        f = build_damage_function(jrc_curves_dict, atype)
        ax.plot(d_range, f(d_range), color=curve['color'], linewidth=2.2, label=curve['label'])
        ax.scatter(curve['depth_m'], curve['damage_fraction'],
                   color=curve['color'], s=30, zorder=5)
    f_sel = build_damage_function(jrc_curves_dict, asset_type)
    ax.fill_between(d_range, 0, f_sel(d_range),
                    alpha=0.08, color=jrc_curves_dict[asset_type]['color'])
    ax.set_xlabel('Flood depth [m]', fontsize=12)
    ax.set_ylabel('Damage fraction [ ]', fontsize=12)
    ax.set_title('JRC Global Flood Depth-Damage Functions\n'
                 '(Huizinga et al. 2017 \u2014 Western Europe)', fontsize=13)
    ax.set_xlim(0, 6.5)
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.legend(loc='lower right', fontsize=10)
    ax.grid(True, alpha=0.35)
    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'jrc_curves.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Selected asset type : {asset_type} (highlighted)')
    return out


# ── Risk screening ─────────────────────────────────────────────────────────────

def risk_screening(
    df_risk,
    ead: float,
    ead_pct: float,
    asset: dict,
    return_periods: np.ndarray = None,
    outputs_dir: Path = None,
) -> str:
    """Three-panel risk screening plot (hazard / damage / exceedance curve)."""
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    flood_depths  = df_risk['flood_depth_m'].values
    damage_eur    = df_risk['damage_eur'].values

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f'Riverine Flood Risk Screening \u2014 {asset["name"]}\n'
                 f'({asset["asset_type"].title()}, {asset["value_eur"]:,}\u202f\u20ac)',
                 fontsize=13, y=1.02)

    # Panel 1: depth vs T
    ax = axes[0]
    ax.semilogx(return_periods, flood_depths, 'o-', color='#1565C0',
                linewidth=2.2, markersize=7)
    ax.fill_between(return_periods, 0, flood_depths, alpha=0.12, color='#1565C0')
    ax.set_xlabel('Return period [years]', fontsize=11)
    ax.set_ylabel('Flood depth [m]', fontsize=11)
    ax.set_title('Hazard\n(WRI Aqueduct)', fontsize=12)
    ax.set_xticks(return_periods)
    ax.set_xticklabels([str(int(r)) for r in return_periods], rotation=45, fontsize=8)
    ax.grid(True, alpha=0.35, which='both')
    ax.set_ylim(bottom=0)

    # Panel 2: damage vs T
    ax = axes[1]
    ax.semilogx(return_periods, damage_eur / 1e3, 's-', color='#e63946',
                linewidth=2.2, markersize=7)
    ax.fill_between(return_periods, 0, damage_eur / 1e3, alpha=0.12, color='#e63946')
    ax.axhline(y=asset['value_eur'] / 1e3, color='gray', linestyle='--',
               linewidth=1.5, label=f'Asset value ({asset["value_eur"]/1e3:.0f}\u202fk\u20ac)')
    ax.set_xlabel('Return period [years]', fontsize=11)
    ax.set_ylabel('Damage [k\u20ac]', fontsize=11)
    ax.set_title('Damage per Return Period\n(JRC Huizinga 2017)', fontsize=12)
    ax.set_xticks(return_periods)
    ax.set_xticklabels([str(int(r)) for r in return_periods], rotation=45, fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35, which='both')
    ax.set_ylim(bottom=0)

    # Panel 3: exceedance curve + EAD
    ax = axes[2]
    p_plot = np.concatenate([[1.0], 1.0 / return_periods])
    d_plot = np.concatenate([[0.0], damage_eur / 1e3])
    ax.plot(p_plot, d_plot, 'o-', color='#FF6F00', linewidth=2.2, markersize=6)
    ax.fill_between(p_plot, 0, d_plot, alpha=0.20, color='#FF6F00',
                    label=f'EAD area = {ead/1e3:.1f}\u202fk\u20ac/yr')
    ax.axhline(y=ead / 1e3, color='#FF6F00', linestyle=':', linewidth=1.5, alpha=0.7)
    ax.text(0.5, ead / 1e3 + 0.5, f'EAD = {ead/1e3:.1f}\u202fk\u20ac/yr',
            fontsize=9, color='#FF6F00', ha='center')
    ax.set_xlabel('Annual exceedance probability', fontsize=11)
    ax.set_ylabel('Damage [k\u20ac]', fontsize=11)
    ax.set_title('Damage-Exceedance Curve\n(EAD = shaded area)', fontsize=12)
    ax.set_xlim(0, max(p_plot) * 1.05)
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.35)

    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'flood_risk_screening.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out


# ── Scenarios comparison ───────────────────────────────────────────────────────

def scenarios_comparison(
    results: list,
    asset: dict,
    outputs_dir: Path = None,
) -> str:
    """Two-panel plot: hazard curves by scenario + EAD bar chart with min/max."""
    return_periods = RETURN_PERIODS

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f'Comparaison scénarios climatiques \u2014 {asset["name"]}', fontsize=13)

    ax = axes[0]
    for r in results:
        ax.semilogx(return_periods, r['depths_median'],
                    color=r['color'], linestyle=r['linestyle'],
                    linewidth=2.2, marker='o', markersize=5, label=r['label'])
        if len(r['models']) > 1:
            ax.fill_between(return_periods, r['depths_min'], r['depths_max'],
                            color=r['color'], alpha=0.15)
    ax.set_xlabel('Période de retour [années]', fontsize=11)
    ax.set_ylabel('Profondeur de crue [m]', fontsize=11)
    ax.set_title('Courbes de hazard\n(médiane GCM + enveloppe min/max)', fontsize=11)
    ax.set_xticks(return_periods)
    ax.set_xticklabels([str(int(r)) for r in return_periods], rotation=45, fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35, which='both')
    ax.set_ylim(bottom=0)

    ax = axes[1]
    x_pos = np.arange(len(results))
    for i, r in enumerate(results):
        med, lo, hi = r['ead_median'] / 1e3, r['ead_min'] / 1e3, r['ead_max'] / 1e3
        ax.bar(x_pos[i], med, width=0.5, color=r['color'], alpha=0.8,
               edgecolor='white', zorder=3)
        ax.errorbar(x_pos[i], med, yerr=[[med - lo], [hi - med]],
                    fmt='none', color='#222', capsize=7, capthick=1.8,
                    linewidth=1.8, zorder=4)
        offset = (hi - lo) * 0.04 + 0.3
        ax.text(x_pos[i], hi + offset, f'max {hi:.1f}k\u20ac',
                ha='center', va='bottom', fontsize=8, color='#444')
        ax.text(x_pos[i], med, f'  {med:.1f}k\u20ac',
                ha='left', va='center', fontsize=9, fontweight='bold',
                color='white' if med > 5 else '#333')
        ax.text(x_pos[i], lo - offset, f'min {lo:.1f}k\u20ac',
                ha='center', va='top', fontsize=8, color='#444')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([r['label'] for r in results], rotation=12, fontsize=9)
    ax.set_ylabel('EAD [k\u20ac/an]', fontsize=11)
    ax.set_title('EAD par scénario\n(médiane  |  barre = min/max GCM)', fontsize=11)
    ax.grid(axis='y', alpha=0.35)
    ymax = max(r['ead_max'] for r in results) / 1e3
    ymin = min(r['ead_min'] for r in results) / 1e3
    ax.set_ylim(bottom=max(0, ymin * 0.7), top=ymax * 1.3)

    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'scenarios_comparison.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out


# ── Per-GCM raw hazard curves ──────────────────────────────────────────────────

def hazard_curves_per_gcm(
    results: list,
    asset: dict,
    return_periods: np.ndarray = None,
    outputs_dir: Path = None,
) -> str:
    """Two-panel figure: raw hazard depth curves per GCM × scenario."""
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS
    future = [r for r in results if len(r['models']) > 1]
    hist   = results[0]
    n_sc   = len(future)

    fig, axes = plt.subplots(1, n_sc, figsize=(7 * n_sc, 5), sharey=True)
    if n_sc == 1:
        axes = [axes]
    fig.suptitle(f'Courbes d\'aléa brutes par GCM \u2014 {asset["name"]}\n'
                 f'(baseline historique en référence)', fontsize=13)

    for ax, r in zip(axes, future):
        ax.semilogx(return_periods, hist['depths_per_model']['000000000WATCH'],
                    color='#AAAAAA', linewidth=1.8, linestyle='--',
                    label='Historical (WATCH)', zorder=2)
        for model, depths_m in r['depths_per_model'].items():
            ead_m = r['ead_per_model'][model]
            lbl   = f'{GCM_LABELS.get(model, model)}  (EAD={ead_m/1e3:.1f}k\u20ac)'
            ax.semilogx(return_periods, depths_m,
                        color=GCM_COLORS.get(model, '#333'),
                        linewidth=1.8, marker='o', markersize=4,
                        label=lbl, zorder=3)
        ax.semilogx(return_periods, r['depths_median'],
                    color='black', linewidth=3,
                    label=f'Médiane  (EAD={r["ead_median"]/1e3:.1f}k\u20ac)',
                    zorder=4)
        ax.fill_between(return_periods, r['depths_min'], r['depths_max'],
                        color='black', alpha=0.07, zorder=1,
                        label='Enveloppe min/max')
        ax.set_xlabel('Période de retour [années]', fontsize=11)
        ax.set_ylabel('Profondeur de crue [m]', fontsize=11)
        ax.set_title(r['label'], fontsize=12)
        ax.set_xticks(return_periods)
        ax.set_xticklabels([str(int(t)) for t in return_periods], rotation=45, fontsize=8)
        ax.legend(fontsize=8.5, loc='upper left')
        ax.grid(True, alpha=0.3, which='both')
        ax.set_ylim(bottom=0)

    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'hazard_curves_per_gcm.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Sauvegard\u00e9 \u2192 {out}')
    return out


def hazard_curves_per_scenario(
    results: list,
    asset: dict,
    return_periods: np.ndarray = None,
    outputs_dir: Path = None,
) -> str:
    """Overlay depth-RP curves for all coastal scenarios on one panel."""
    return_periods = return_periods if return_periods is not None else RETURN_PERIODS

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle(f'Courbes d\'aléa côtier par scénario — {asset["name"]}', fontsize=13)

    for r in results:
        ax.semilogx(
            return_periods, r['depths_median'],
            color=r['color'], linewidth=2.2, marker='o', markersize=4,
            linestyle=r.get('linestyle', 'solid'),
            label=f'{r["label"]}  (EAD={r["ead_median"]/1e3:.1f}k€)',
            zorder=3,
        )
    ax.set_xlabel('Période de retour [années]', fontsize=11)
    ax.set_ylabel('Profondeur de crue [m]', fontsize=11)
    ax.set_xticks(return_periods)
    ax.set_xticklabels([str(int(t)) for t in return_periods], rotation=45, fontsize=8)
    ax.legend(fontsize=9, loc='upper left')
    ax.grid(True, alpha=0.3, which='both')
    ax.set_ylim(bottom=0)
    plt.tight_layout()
    out = str(_outputs(outputs_dir) / 'coastal_hazard_curves.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    print(f'Sauvegardé → {out}')
    return out


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO PLOTS
# ══════════════════════════════════════════════════════════════════════════════

_TYPE_COLORS = {
    'residential': '#e63946', 'commercial': '#2196F3',
    'industrial': '#FF9800', 'agriculture': '#4CAF50', 'transport': '#9C27B0',
}


def portfolio_map(
    df_portfolio,
    outputs_dir=None,
    value_col: str = 'ead_historical',
    title: str = None,
) -> str:
    """European map of assets, markers sized and colored by EAD."""
    out_dir = _outputs(outputs_dir)
    lons = df_portfolio['lon'].values
    lats = df_portfolio['lat'].values
    vals = df_portfolio[value_col].values

    xs = np.array([_lon2x(lo) for lo in lons])
    ys = np.array([_lat2y(la) for la in lats])

    fig, ax = plt.subplots(figsize=(12, 10))
    pad = 200_000  # 200 km padding
    ax.set_xlim(xs.min() - pad, xs.max() + pad)
    ax.set_ylim(ys.min() - pad, ys.max() + pad)

    try:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=5)
    except Exception:
        ctx.add_basemap(ax, zoom=5)

    # Size: 20-300 proportional to value; color: by EAD
    vmax = max(vals.max(), 1)
    sizes = 20 + 280 * (vals / vmax)
    sc = ax.scatter(xs, ys, c=vals / 1e3, s=sizes, cmap='YlOrRd',
                    edgecolors='white', linewidths=0.6, zorder=5, alpha=0.85,
                    vmin=0, vmax=vmax / 1e3)
    cb = plt.colorbar(sc, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label(f'EAD [k\u20ac/an]', fontsize=10)

    # Mark zero-EAD assets in grey
    zero_mask = vals == 0
    if zero_mask.any():
        ax.scatter(xs[zero_mask], ys[zero_mask], c='#CCCCCC', s=25,
                   edgecolors='white', linewidths=0.4, zorder=4, alpha=0.7,
                   label=f'{zero_mask.sum()} actifs sans exposition')
        ax.legend(fontsize=9, loc='lower left')

    title = title or f'Portfolio Flood Risk Map \u2014 {len(df_portfolio)} actifs'
    total = vals.sum()
    ax.set_title(f'{title}\nEAD total = {total:,.0f}\u202f\u20ac/an', fontsize=13)
    ax.axis('off')
    plt.tight_layout()
    out = str(out_dir / 'portfolio_map.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out


def portfolio_summary(
    df_portfolio,
    outputs_dir=None,
) -> str:
    """Four-panel portfolio summary: top 10, by type, by country, distribution."""
    out_dir = _outputs(outputs_dir)
    df = df_portfolio.copy()
    total_ead = df['ead_historical'].sum()

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle(f'Portfolio Flood Risk Summary \u2014 {len(df)} actifs\n'
                 f'EAD total = {total_ead:,.0f}\u202f\u20ac/an', fontsize=14)

    # ── Panel 1: Top 10 contributors ──
    ax = axes[0, 0]
    top10 = df.nlargest(10, 'ead_historical')
    colors = [_TYPE_COLORS.get(t, '#888') for t in top10['asset_type']]
    y_pos = np.arange(len(top10))
    bars = ax.barh(y_pos, top10['ead_historical'] / 1e3, color=colors,
                   edgecolor='white', height=0.7)
    ax.set_yticks(y_pos)
    labels = [f'{r["name"][:30]}' for _, r in top10.iterrows()]
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('EAD [k\u20ac/an]', fontsize=10)
    ax.set_title('Top 10 contributeurs', fontsize=11)
    for bar, val in zip(bars, top10['ead_historical']):
        if val > 0:
            ax.text(bar.get_width() + total_ead * 0.001 / 1e3, bar.get_y() + bar.get_height() / 2,
                    f'{val/1e3:.1f}k\u20ac', va='center', fontsize=8)
    ax.grid(axis='x', alpha=0.3)

    # ── Panel 2: EAD by asset type ──
    ax = axes[0, 1]
    by_type = df.groupby('asset_type').agg(
        ead_sum=('ead_historical', 'sum'),
        count=('ead_historical', 'size'),
        value_sum=('value_eur', 'sum'),
    ).sort_values('ead_sum', ascending=False)
    colors_t = [_TYPE_COLORS.get(t, '#888') for t in by_type.index]
    bars = ax.bar(range(len(by_type)), by_type['ead_sum'] / 1e3, color=colors_t,
                  edgecolor='white')
    ax.set_xticks(range(len(by_type)))
    ax.set_xticklabels([f'{t}\n(n={c})' for t, c in zip(by_type.index, by_type['count'])],
                       fontsize=9)
    ax.set_ylabel('EAD [k\u20ac/an]', fontsize=10)
    ax.set_title('EAD par type d\'actif', fontsize=11)
    ax.grid(axis='y', alpha=0.3)

    # ── Panel 3: EAD by country (top 10) ──
    ax = axes[1, 0]
    if 'country' in df.columns:
        by_country = df.groupby('country')['ead_historical'].sum()\
                       .sort_values(ascending=False).head(10)
        ax.barh(range(len(by_country)), by_country.values / 1e3,
                color='#1565C0', edgecolor='white', height=0.7)
        ax.set_yticks(range(len(by_country)))
        ax.set_yticklabels(by_country.index, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel('EAD [k\u20ac/an]', fontsize=10)
        ax.set_title('EAD par pays (top 10)', fontsize=11)
    else:
        ax.text(0.5, 0.5, 'Colonne "country" absente', transform=ax.transAxes,
                ha='center', fontsize=11, color='grey')
    ax.grid(axis='x', alpha=0.3)

    # ── Panel 4: Distribution of EAD/value ratio ──
    ax = axes[1, 1]
    ratios = df['ead_pct_historical'].values
    exposed = ratios[ratios > 0]
    ax.hist(exposed, bins=30, color='#FF6F00', edgecolor='white', alpha=0.8)
    ax.axvline(np.median(exposed) if len(exposed) > 0 else 0,
               color='#D32F2F', linestyle='--', linewidth=2,
               label=f'M\u00e9diane = {np.median(exposed):.3f}%' if len(exposed) > 0 else '')
    n_zero = (ratios == 0).sum()
    ax.set_xlabel('EAD / Valeur actif [%/an]', fontsize=10)
    ax.set_ylabel('Nombre d\'actifs', fontsize=10)
    ax.set_title(f'Distribution EAD/Valeur\n({n_zero} actifs sans exposition exclus)', fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    out = str(out_dir / 'portfolio_summary.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out


def portfolio_scenarios(
    df_portfolio,
    outputs_dir=None,
) -> str:
    """Portfolio-level scenario comparison if scenario columns exist."""
    out_dir = _outputs(outputs_dir)
    df = df_portfolio

    has_45 = 'ead_rcp4p5_median' in df.columns
    has_85 = 'ead_rcp8p5_median' in df.columns
    if not has_45 and not has_85:
        print('Pas de colonnes sc\u00e9narios dans le DataFrame.')
        return ''

    scenarios = [('Historical', df['ead_historical'].sum(), 0, 0, '#1565C0')]
    if has_45:
        scenarios.append(('RCP 4.5 \u2014 2050',
                          df['ead_rcp4p5_median'].sum(),
                          df['ead_rcp4p5_min'].sum(),
                          df['ead_rcp4p5_max'].sum(), '#FF9800'))
    if has_85:
        scenarios.append(('RCP 8.5 \u2014 2050',
                          df['ead_rcp8p5_median'].sum(),
                          df['ead_rcp8p5_min'].sum(),
                          df['ead_rcp8p5_max'].sum(), '#e63946'))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f'Portfolio Climate Scenario Comparison \u2014 {len(df)} actifs', fontsize=13)

    # Panel 1: Total portfolio EAD by scenario
    ax = axes[0]
    labels = [s[0] for s in scenarios]
    meds   = [s[1] / 1e6 for s in scenarios]
    colors = [s[4] for s in scenarios]
    x = np.arange(len(scenarios))
    ax.bar(x, meds, color=colors, edgecolor='white', width=0.5)
    for i, s in enumerate(scenarios):
        lo, hi = s[2] / 1e6, s[3] / 1e6
        if lo > 0 or hi > 0:
            ax.errorbar(x[i], meds[i], yerr=[[meds[i] - lo], [hi - meds[i]]],
                        fmt='none', color='#222', capsize=7, capthick=1.5)
        ax.text(x[i], meds[i] + max(meds) * 0.02, f'{meds[i]:.2f}M\u20ac',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('EAD total portfolio [M\u20ac/an]', fontsize=10)
    ax.set_title('EAD total par sc\u00e9nario', fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=0)

    # Panel 2: Change in EAD per asset (scatter: hist vs future)
    ax = axes[1]
    ref = df['ead_historical'].values / 1e3
    if has_85:
        fut = df['ead_rcp8p5_median'].values / 1e3
        lbl = 'RCP 8.5'
        clr = '#e63946'
    else:
        fut = df['ead_rcp4p5_median'].values / 1e3
        lbl = 'RCP 4.5'
        clr = '#FF9800'
    maxv = max(ref.max(), fut.max()) * 1.1 or 1
    ax.scatter(ref, fut, c=clr, alpha=0.6, s=40, edgecolors='white', linewidths=0.5)
    ax.plot([0, maxv], [0, maxv], 'k--', linewidth=1, alpha=0.4, label='1:1')
    ax.set_xlabel('EAD historique [k\u20ac/an]', fontsize=10)
    ax.set_ylabel(f'EAD {lbl} 2050 [k\u20ac/an]', fontsize=10)
    ax.set_title(f'Changement par actif\n(au-dessus de la diagonale = augmentation)', fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, maxv)
    ax.set_ylim(0, maxv)
    ax.set_aspect('equal')

    plt.tight_layout()
    out = str(out_dir / 'portfolio_scenarios.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out


def portfolio_coastal_scenarios(
    df_portfolio,
    coastal_scenarios: list,
    outputs_dir=None,
) -> str:
    """Portfolio-level coastal scenario comparison.

    Reads EAD columns named 'ead_{scenario}_{subsidence}' produced by
    run_coastal_portfolio().
    """
    out_dir = _outputs(outputs_dir)
    df = df_portfolio

    bars = []
    for sc in coastal_scenarios:
        key = f'{sc["scenario"]}_{sc["subsidence"]}'
        col = f'ead_{key}'
        if col in df.columns:
            bars.append((sc['label'], df[col].sum(), sc['color']))

    if not bars:
        print('Pas de colonnes scénarios côtiers dans le DataFrame.')
        return ''

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f'Portfolio Coastal Scenario Comparison — {len(df)} actifs', fontsize=13)

    # Panel 1: Total EAD by scenario
    ax = axes[0]
    labels = [b[0] for b in bars]
    totals = [b[1] / 1e6 for b in bars]
    colors = [b[2] for b in bars]
    x = np.arange(len(bars))
    ax.bar(x, totals, color=colors, edgecolor='white', width=0.5)
    for i, t in enumerate(totals):
        ax.text(x[i], t + max(totals) * 0.02, f'{t:.2f}M€',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, rotation=15)
    ax.set_ylabel('EAD total portfolio [M€/an]', fontsize=10)
    ax.set_title('EAD total par scénario côtier', fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=0)

    # Panel 2: Scatter baseline vs worst scenario
    ax = axes[1]
    base_key = f'{coastal_scenarios[0]["scenario"]}_{coastal_scenarios[0]["subsidence"]}'
    worst_sc = coastal_scenarios[-1]
    worst_key = f'{worst_sc["scenario"]}_{worst_sc["subsidence"]}'
    ref = df[f'ead_{base_key}'].values / 1e3
    fut = df[f'ead_{worst_key}'].values / 1e3
    maxv = max(ref.max(), fut.max()) * 1.1 or 1
    ax.scatter(ref, fut, c=worst_sc['color'], alpha=0.6, s=40,
               edgecolors='white', linewidths=0.5)
    ax.plot([0, maxv], [0, maxv], 'k--', linewidth=1, alpha=0.4, label='1:1')
    ax.set_xlabel('EAD baseline [k€/an]', fontsize=10)
    ax.set_ylabel(f'EAD {worst_sc["label"]} [k€/an]', fontsize=10)
    ax.set_title('Changement par actif\n(au-dessus = augmentation)', fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, maxv)
    ax.set_ylim(0, maxv)
    ax.set_aspect('equal')

    plt.tight_layout()
    out = str(out_dir / 'portfolio_coastal_scenarios.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.show()
    return out
