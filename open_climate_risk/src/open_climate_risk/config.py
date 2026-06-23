"""Global constants and configuration."""
from pathlib import Path
import numpy as np

# ── Project paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR     = PROJECT_ROOT / 'data' / 'aqueduct'
OUTPUTS_DIR  = PROJECT_ROOT / 'outputs'
JRC_EXCEL    = (
    PROJECT_ROOT
    / 'references'
    / 'vulnerability_curves'
    / 'copy_of_global_flood_depth-damage_functions__30102017.xlsx'
)

# ── Aqueduct S3 ────────────────────────────────────────────────────────────────
AQUEDUCT_S3 = 'https://wri-projects.s3.amazonaws.com/AqueductFloodTool/download/v2'

# ── Return periods ─────────────────────────────────────────────────────────────
RETURN_PERIODS   = np.array([2, 5, 10, 25, 50, 100, 250, 500, 1000], dtype=float)
EXCEEDANCE_PROBS = 1.0 / RETURN_PERIODS

# ── GCM metadata ──────────────────────────────────────────────────────────────
GCM_MODELS = [
    'MIROC-ESM-CHEM',
    '00000NorESM1-M',
    '0000GFDL-ESM2M',
    '0000HadGEM2-ES',
    '00IPSL-CM5A-LR',
]

GCM_LABELS = {
    'MIROC-ESM-CHEM': 'MIROC',
    '00000NorESM1-M': 'NorESM',
    '0000GFDL-ESM2M': 'GFDL',
    '0000HadGEM2-ES': 'HadGEM',
    '00IPSL-CM5A-LR': 'IPSL',
    '000000000WATCH': 'WATCH (hist.)',
}

GCM_COLORS = {
    'MIROC-ESM-CHEM': '#e63946',
    '00000NorESM1-M': '#2196F3',
    '0000GFDL-ESM2M': '#FF9800',
    '0000HadGEM2-ES': '#9C27B0',
    '00IPSL-CM5A-LR': '#4CAF50',
    '000000000WATCH': '#1565C0',
}

# ── Climate scenarios ──────────────────────────────────────────────────────────
SCENARIOS = [
    {
        'label':     'Historical (baseline)',
        'scenario':  'historical',
        'models':    ['000000000WATCH'],
        'year':      1980,
        'color':     '#1565C0',
        'linestyle': 'solid',
    },
    {
        'label':     'RCP 4.5 — 2050',
        'scenario':  'rcp4p5',
        'models':    GCM_MODELS,
        'year':      2050,
        'color':     '#FF9800',
        'linestyle': 'dashed',
    },
    {
        'label':     'RCP 8.5 — 2050',
        'scenario':  'rcp8p5',
        'models':    GCM_MODELS,
        'year':      2050,
        'color':     '#e63946',
        'linestyle': 'dotted',
    },
]

# ── Coastal flood ─────────────────────────────────────────────────────────────
COASTAL_SCENARIOS = [
    {
        'label':      'Historical (no subsidence)',
        'scenario':   'historical',
        'subsidence': 'nosub',
        'year':       'hist',
        'projection': '0',
        'color':      '#1565C0',
        'linestyle':  'solid',
    },
    {
        'label':      'Historical (with subsidence)',
        'scenario':   'historical',
        'subsidence': 'wtsub',
        'year':       'hist',
        'projection': '0',
        'color':      '#2196F3',
        'linestyle':  'solid',
    },
    {
        'label':      'RCP 4.5 — 2050 (with sub.)',
        'scenario':   'rcp4p5',
        'subsidence': 'wtsub',
        'year':       2050,
        'projection': '0',
        'color':      '#FF9800',
        'linestyle':  'dashed',
    },
    {
        'label':      'RCP 8.5 — 2050 (with sub.)',
        'scenario':   'rcp8p5',
        'subsidence': 'wtsub',
        'year':       2050,
        'projection': '0',
        'color':      '#e63946',
        'linestyle':  'dotted',
    },
]
