"""Shared fixtures for the test suite."""
import numpy as np
import pytest


@pytest.fixture
def sample_asset():
    """A minimal asset dict for testing."""
    return {
        'name':          'Test Asset — Paris',
        'lon':           2.3488,
        'lat':           48.8534,
        'asset_type':    'residential',
        'value_eur':     500_000,
        'floor_area_m2': 120,
    }


@pytest.fixture
def jrc_curves_stub():
    """Minimal JRC-like curves for testing (no Excel dependency)."""
    depths = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0])
    return {
        'residential': {
            'depth_m': depths,
            'damage_fraction': np.array([0.00, 0.25, 0.40, 0.50, 0.60, 0.75, 0.85, 0.95, 1.00]),
            'color': '#e63946',
            'label': 'Residential',
        },
        'commercial': {
            'depth_m': depths,
            'damage_fraction': np.array([0.00, 0.15, 0.30, 0.45, 0.55, 0.75, 0.90, 1.00, 1.00]),
            'color': '#2196F3',
            'label': 'Commercial',
        },
    }
