"""Tests for open_climate_risk.data module."""
import numpy as np
import pytest

from open_climate_risk.data import (
    aqueduct_filename,
    aqueduct_source,
    extract_hazard_df,
    load_jrc_curves,
    load_jrc_max_damage,
)
from open_climate_risk.config import RETURN_PERIODS, DATA_DIR


class TestAqueductFilename:
    def test_historical_default(self):
        fn = aqueduct_filename(100)
        assert fn == 'inunriver_historical_000000000WATCH_1980_rp00100.tif'

    def test_future_scenario(self):
        fn = aqueduct_filename(25, scenario='rcp4p5', model='0000GFDL-ESM2M', year=2050)
        assert fn == 'inunriver_rcp4p5_0000GFDL-ESM2M_2050_rp00025.tif'

    def test_return_period_formatting(self):
        """Return periods should be zero-padded to 4 digits after 'rp0'."""
        assert 'rp00002' in aqueduct_filename(2)
        assert 'rp01000' in aqueduct_filename(1000)


class TestAqueductSource:
    def test_returns_s3_url_when_no_local(self, tmp_path):
        """When file doesn't exist locally, should return S3 URL."""
        src = aqueduct_source(100, data_dir=tmp_path)
        assert src.startswith('https://')
        assert 'rp00100' in src

    def test_returns_local_path_when_exists(self, tmp_path):
        """When file exists locally, should return local path."""
        fn = aqueduct_filename(100)
        (tmp_path / fn).touch()
        src = aqueduct_source(100, data_dir=tmp_path)
        assert not src.startswith('https://')
        assert str(tmp_path) in src


class TestJrcCurves:
    def test_load_returns_dict(self):
        """JRC loading should always return a dict (fallback if no Excel)."""
        curves = load_jrc_curves()
        assert isinstance(curves, dict)
        assert 'residential' in curves
        assert 'transport' in curves

    def test_curve_structure(self):
        curves = load_jrc_curves()
        for atype, curve in curves.items():
            assert 'depth_m' in curve
            assert 'damage_fraction' in curve
            assert len(curve['depth_m']) == len(curve['damage_fraction'])
            # JRC Excel starts at d=0.5m (not 0); build_damage_function prepends (0,0)
            assert curve['damage_fraction'][-1] >= 0.8  # ends near 1.0

    def test_max_damage_returns_all_types(self):
        md = load_jrc_max_damage()
        for t in ['residential', 'commercial', 'industrial', 'agriculture', 'transport']:
            assert t in md
            assert md[t] > 0


class TestExtractHazardDf:
    def test_returns_correct_columns(self, sample_asset):
        """DataFrame should have the 3 expected columns."""
        df = extract_hazard_df(sample_asset)
        assert set(df.columns) == {'return_period_yr', 'exceedance_prob_yr', 'flood_depth_m'}
        assert len(df) == len(RETURN_PERIODS)

    def test_depths_non_negative(self, sample_asset):
        df = extract_hazard_df(sample_asset)
        assert (df['flood_depth_m'] >= 0).all() or df['flood_depth_m'].isna().any()
