"""Tests for the source-validation metrics (scripts/validation/metrics.py). No network."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "validation"))
from metrics import gap_share, metrics_by_season, pair_metrics, season_of, spearman, zscore  # noqa: E402


def test_identical_series():
    x = np.linspace(5, 25, 50)
    m = pair_metrics(x, x)
    assert m["n"] == 50 and m["bias"] == 0 and m["rmse"] == 0
    assert m["r2"] == pytest.approx(1) and m["slope"] == pytest.approx(1) and m["intercept"] == pytest.approx(0, abs=1e-9)


def test_constant_offset_r2_one_but_biased():
    x = np.linspace(5, 25, 50)
    m = pair_metrics(x, x + 1.0)
    assert m["r2"] == pytest.approx(1)          # R2 blind to the offset
    assert m["bias"] == pytest.approx(1) and m["rmse"] == pytest.approx(1)
    assert m["ubrmse"] == pytest.approx(0, abs=1e-6)


def test_scaled_series_slope():
    x = np.linspace(1, 10, 30)
    m = pair_metrics(x, 2 * x)
    assert m["r2"] == pytest.approx(1) and m["slope"] == pytest.approx(2) and m["std_ratio"] == pytest.approx(2)


def test_nan_dropped_and_small_n():
    m = pair_metrics([1, np.nan, 3], [1, 2, np.nan])
    assert m["n"] == 1 and np.isnan(m["r"])


def test_ubrmse_identity():
    rng = np.random.default_rng(0)
    x = rng.normal(15, 5, 500)
    y = x + 0.5 + rng.normal(0, 1, 500)
    m = pair_metrics(x, y)
    assert m["rmse"] ** 2 == pytest.approx(m["bias"] ** 2 + m["ubrmse"] ** 2)


def test_seasons():
    idx = pd.to_datetime(["2024-01-15", "2024-04-15", "2024-07-15", "2024-10-15", "2024-12-01"])
    assert list(season_of(idx)) == ["DJF", "MAM", "JJA", "SON", "DJF"]
    s = pd.Series(np.arange(366.0), index=pd.date_range("2024-01-01", periods=366))
    t = metrics_by_season(s, s + 2)
    assert list(t.season) == ["all", "DJF", "MAM", "JJA", "SON"]
    assert (t.bias == 2).all() and t.loc[t.season == "all", "n"].item() == 366


def test_gap_share_and_helpers():
    s = pd.Series(1.0, index=pd.date_range("2024-01-01", periods=5))
    assert gap_share(s, "2024-01-01", "2024-01-10") == pytest.approx(0.5)
    assert zscore(pd.Series([1.0, 2.0, 3.0])).mean() == pytest.approx(0)
    assert spearman([1, 2, 3, 4], [10, 20, 30, 100]) == pytest.approx(1)


def test_despike_drops_only_gross_errors():
    from metrics import despike
    idx = pd.date_range("2024-01-01", periods=40)
    s = pd.Series(np.linspace(10, 14, 40), index=idx)
    s.iloc[20] = 3.0                      # one-day drop of ~9 C
    keep = despike(s, 3.0)
    assert not keep.iloc[20] and keep.drop(idx[20]).all()
