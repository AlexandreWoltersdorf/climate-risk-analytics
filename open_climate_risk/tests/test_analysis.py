"""Tests for open_climate_risk.analysis module."""
import numpy as np
import pandas as pd
import pytest

from open_climate_risk.analysis import (
    build_damage_function,
    apply_damage,
    compute_ead,
    compute_ead_from_df,
)


class TestBuildDamageFunction:
    def test_returns_callable(self, jrc_curves_stub):
        fn = build_damage_function(jrc_curves_stub, 'residential')
        assert callable(fn)

    def test_zero_depth_gives_zero_damage(self, jrc_curves_stub):
        fn = build_damage_function(jrc_curves_stub, 'residential')
        assert fn(0.0) == pytest.approx(0.0, abs=0.01)

    def test_high_depth_gives_near_one(self, jrc_curves_stub):
        fn = build_damage_function(jrc_curves_stub, 'residential')
        assert fn(10.0) == pytest.approx(1.0, abs=0.01)

    def test_monotonically_increasing(self, jrc_curves_stub):
        fn = build_damage_function(jrc_curves_stub, 'residential')
        depths = np.linspace(0, 6, 50)
        fracs = fn(depths)
        assert np.all(np.diff(fracs) >= -1e-10)  # allow tiny float errors

    def test_prepends_zero_if_missing(self):
        """If JRC curve starts at d=0.5, function should prepend (0, 0)."""
        curves = {
            'test': {
                'depth_m': np.array([0.5, 1.0, 2.0]),
                'damage_fraction': np.array([0.2, 0.4, 0.8]),
                'color': '#000', 'label': 'Test',
            }
        }
        fn = build_damage_function(curves, 'test')
        assert fn(0.0) == pytest.approx(0.0, abs=0.01)
        assert fn(0.25) < fn(0.5)  # interpolated, not flat


class TestApplyDamage:
    def test_output_columns(self, jrc_curves_stub, sample_asset):
        df = pd.DataFrame({
            'return_period_yr': [10, 100],
            'exceedance_prob_yr': [0.1, 0.01],
            'flood_depth_m': [0.5, 1.5],
        })
        result = apply_damage(df, jrc_curves_stub, sample_asset)
        assert 'damage_fraction' in result.columns
        assert 'damage_eur' in result.columns

    def test_damage_bounded(self, jrc_curves_stub, sample_asset):
        df = pd.DataFrame({
            'return_period_yr': [10],
            'exceedance_prob_yr': [0.1],
            'flood_depth_m': [1.0],
        })
        result = apply_damage(df, jrc_curves_stub, sample_asset)
        assert 0 <= result['damage_fraction'].iloc[0] <= 1
        assert 0 <= result['damage_eur'].iloc[0] <= sample_asset['value_eur']


class TestComputeEad:
    def test_zero_damages_gives_zero_ead(self):
        probs = np.array([0.5, 0.1, 0.01])
        damages = np.array([0.0, 0.0, 0.0])
        assert compute_ead(probs, damages) == pytest.approx(0.0)

    def test_uniform_damage_gives_expected_ead(self):
        """EAD with constant damage: prepends (p=1, d=0) so integral < damage."""
        probs = np.array([0.5, 0.1, 0.01])
        damages = np.array([1000, 1000, 1000])
        ead = compute_ead(probs, damages, include_tail=True)
        # Prepends (p=1, d=0), so ramp from 0→1000 between p=1 and p=0.5
        # then flat 1000 from p=0.5 to p=0. EAD = 0.5*500 + 0.5*1000 = 750
        assert ead == pytest.approx(750, rel=0.01)

    def test_ead_positive_for_positive_damages(self):
        probs = np.array([0.5, 0.1, 0.01, 0.001])
        damages = np.array([0, 1000, 5000, 10000])
        ead = compute_ead(probs, damages)
        assert ead > 0

    def test_ead_increases_with_damages(self):
        probs = np.array([0.1, 0.01])
        ead_low  = compute_ead(probs, np.array([100, 500]))
        ead_high = compute_ead(probs, np.array([1000, 5000]))
        assert ead_high > ead_low


class TestComputeEadFromDf:
    def test_returns_tuple(self, jrc_curves_stub, sample_asset):
        df = pd.DataFrame({
            'return_period_yr': [10, 100],
            'exceedance_prob_yr': [0.1, 0.01],
            'flood_depth_m': [0.5, 1.5],
            'damage_fraction': [0.25, 0.50],
            'damage_eur': [125_000, 250_000],
        })
        ead, pct = compute_ead_from_df(df, sample_asset)
        assert isinstance(ead, float)
        assert isinstance(pct, float)
        assert ead > 0
        assert 0 < pct < 100
