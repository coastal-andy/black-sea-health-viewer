"""Tests for the power-spectrum step (scripts/spectra/psd.py) on SYNTHETIC series. No network, no cache.

The main checks: Welch and Lomb-Scargle recover the planted periods (annual, semi-annual, 6-year, diurnal, inertial at
44 N, M2 tide), the PSD integrates to the variance, Lomb-Scargle equals Welch on gap-free data, and pure red noise
gives about 5 % false alarms.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "spectra"))
import psd  # noqa: E402
from synthetic import INERTIAL_H, M2_H, synthetic_hourly, synthetic_long_daily  # noqa: E402


@pytest.fixture(scope="module")
def long_daily():
    return synthetic_long_daily()


@pytest.fixture(scope="module")
def hourly_gaps():
    return synthetic_hourly(gaps=True)


@pytest.fixture(scope="module")
def hourly_full():
    return synthetic_hourly(gaps=False)


def _nearest_peak(sp, period_d):
    pk = sp["peaks"]
    assert len(pk), "no significant peak at all"
    j = (np.log(pk.period_d) - np.log(period_d)).abs().idxmin()
    return pk.loc[j, "period_d"]


# ------------------------------------------------------------------ synthetic series have the get_series() shape
@pytest.mark.parametrize("make", [synthetic_long_daily, lambda: synthetic_hourly(gaps=True)])
def test_synthetic_shape_like_get_series(make):
    df = make()
    assert isinstance(df.index, pd.DatetimeIndex) and df.index.name == "time"
    assert list(df.columns) == ["sst"]
    a = df.attrs
    for k in ("variable", "lat", "lon", "source_id", "label", "origin", "trust", "unit", "planted"):
        assert k in a
    assert a["label"].startswith("SYNTHETIC") and a["origin"] == "synthetic"


def test_hourly_gaps_present(hourly_gaps):
    g = hourly_gaps.attrs["planted"]["gap_share"]
    assert 0.10 < g < 0.25
    assert not psd.is_regular(psd.series_time(hourly_gaps["sst"]), 1 / 24)


# ------------------------------------------------------------------ planted periods recovered
@pytest.mark.parametrize("name,period_d,tol", [("annual", 365.25, 0.03), ("semi-annual", 182.625, 0.03),
                                               ("6-year", 6 * 365.25, 0.20)])
def test_welch_recovers_long_periods(long_daily, name, period_d, tol):
    sp = psd.spectrum(long_daily["sst"], 1.0, 20 * psd.ANNUAL_D, band=psd.FULL_BAND)
    assert sp["method"] == "Welch"
    got = _nearest_peak(sp, period_d)
    assert abs(got - period_d) / period_d < tol, (name, got)


@pytest.mark.parametrize("method", ["welch", "lomb"])
@pytest.mark.parametrize("period_h", [24.0, INERTIAL_H, M2_H])
def test_subdaily_periods_recovered(hourly_full, hourly_gaps, method, period_h):
    s = hourly_full["sst"] if method == "welch" else hourly_gaps["sst"]
    sp = psd.spectrum(s, 1 / 24, 30.0, anomalies=True, method=method)
    got_h = _nearest_peak(sp, period_h / 24) * 24
    assert abs(got_h - period_h) / period_h < 0.01, (method, period_h, got_h)


def test_inertial_and_tide_are_separated(hourly_full):
    sp = psd.spectrum(hourly_full["sst"], 1 / 24, 30.0, anomalies=True, method="welch")
    per_h = sp["peaks"].period_d * 24
    assert ((per_h > 17) & (per_h < 17.6)).any() and ((per_h > 12.3) & (per_h < 12.6)).any()


def test_trend_recovered_by_ols(long_daily):
    s = long_daily["sst"]
    slope = np.polyfit(psd.series_time(s) / psd.ANNUAL_D, s.to_numpy(), 1)[0]
    assert slope == pytest.approx(long_daily.attrs["planted"]["trend_per_year"], rel=0.25)


# ------------------------------------------------------------------ normalisation and method agreement
def test_welch_integrates_to_variance():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 2.0, 4000)
    out = psd.welch_psd(y, 1.0, 256)
    var = np.sum(out["psd"]) * (out["freq"][1] - out["freq"][0])
    assert var == pytest.approx(4.0, rel=0.1)


def test_lomb_equals_welch_on_gap_free(hourly_full):
    a = psd.spectrum(hourly_full["sst"], 1 / 24, 30.0, anomalies=True, method="welch")
    b = psd.spectrum(hourly_full["sst"], 1 / 24, 30.0, anomalies=True, method="lomb")
    assert np.allclose(a["freq"], b["freq"])
    assert np.median(b["psd"] / a["psd"]) == pytest.approx(1.0, abs=0.1)


def test_lomb_with_gaps_keeps_band_variance(hourly_full, hourly_gaps):
    """Prewhitened Lomb-Scargle on the gappy series gives about the gap-free variance in each band."""
    a = psd.spectrum(hourly_full["sst"], 1 / 24, 30.0, anomalies=True, method="welch")
    b = psd.spectrum(hourly_gaps["sst"], 1 / 24, 30.0, anomalies=True, method="lomb")
    per = 1 / a["freq"]
    for lo, hi in [(1 / 12, 0.5), (0.5, 2), (2, 10)]:
        m = (per >= lo) & (per < hi)
        assert b["psd"][m].sum() / a["psd"][m].sum() == pytest.approx(1.0, abs=0.3), (lo, hi)


def test_ar1_spectrum_integrates_to_variance():
    f = np.linspace(1e-4, 0.5, 20000)
    s = psd.ar1_spectrum(f, 0.8, 3.0, 1.0)
    integral = float(np.sum((s[1:] + s[:-1]) / 2 * np.diff(f)))      # trapezoid rule (numpy 1.x and 2.x)
    assert integral == pytest.approx(3.0, rel=0.01)


def test_wosa_dof():
    assert psd.wosa_dof(1) == 2.0
    assert 2 * 10 / 1.06 < psd.wosa_dof(10) < 20


# ------------------------------------------------------------------ false alarms on pure red noise
@pytest.mark.parametrize("anomalies", [False, True])
def test_red_noise_false_alarm_rate(anomalies):
    rng = np.random.default_rng(7)
    n, rho = 3650, 0.8
    x = np.empty(n)
    x[0] = 0
    e = rng.normal(0, 1, n)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + e[i]
    s = pd.Series(x, index=pd.date_range("2010-01-01", periods=n, freq="D"))
    sp = psd.spectrum(s, 1.0, 365.0, anomalies=anomalies, band=(2.0, 120.0))
    share = psd.n_above(sp) / sp["n_tested"]
    assert share < 0.12, share


def test_band_names():
    assert psd.band_of(365) == "annual"
    assert psd.band_of(182) == "semi-annual"
    assert psd.band_of(5) == "synoptic"
    assert psd.band_of(17.27 / 24) == "inertial"
    assert psd.band_of(12.42 / 24) == "semi-diurnal tide M2"
