"""Tests for the seasonal harmonic fit and the interannual trend (scripts/seasonal). SYNTHETIC data only, no network."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "seasonal"))
sys.path.insert(0, str(ROOT / "scripts" / "spectra"))
from harmonic import aggregate, compare_nested, fit_harmonics, select_periods  # noqa: E402
from trend import annual_means, linear_trend  # noqa: E402

TEMP_PERIODS = [365.25, 182.625, 9.0]   # temporary list (annual, semi-annual, one synoptic), passed as a parameter


def planted(start="2010-01-01", end="2019-12-31", seed=0, noise=0.3, rho=0.7, trend_per_year=0.0, gaps=0.0):
    """SYNTHETIC daily series: annual (amp 8, max on day 220 after 1 Jan), semi-annual (amp 1.5, max day 40),
    9-day cycle (amp 0.5, max day 3), AR(1) noise."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="D")
    t = (idx - pd.Timestamp(idx[0].year, 1, 1)).days.to_numpy(float)
    e = np.zeros(len(t))
    for i in range(1, len(t)):
        e[i] = rho * e[i - 1] + rng.normal(0, noise)
    y = (15 + trend_per_year * t / 365.25 + 8 * np.cos(2 * np.pi * (t - 220) / 365.25)
         + 1.5 * np.cos(2 * np.pi * (t - 40) / 182.625) + 0.5 * np.cos(2 * np.pi * (t - 3) / 9.0) + e)
    s = pd.Series(y, index=idx)
    if gaps:
        s = s[rng.random(len(s)) > gaps]
    return s


def test_daily_fit_recovers_amplitudes_and_phases():
    f = fit_harmonics(planted(gaps=0.2), TEMP_PERIODS)
    amp = [c["amplitude"] for c in f["cycles"]]
    tmax = [c["t_max_d"] for c in f["cycles"]]
    assert amp == pytest.approx([8, 1.5, 0.5], abs=0.15)
    assert tmax[0] == pytest.approx(220, abs=3) and tmax[1] == pytest.approx(40, abs=5)
    assert tmax[2] == pytest.approx(3, abs=0.5)
    for c, a in zip(f["cycles"], [8, 1.5, 0.5]):
        lo, hi = c["amplitude_ci"]
        assert lo - 0.05 <= a <= hi + 0.05
        assert c["p_value"] < 1e-3
    assert f["model"]["r2"] > 0.95
    # daily AR(1) residuals are autocorrelated: HAC se larger than classic
    assert f["residuals"]["lag1_autocorr"] > 0.5
    assert f["cycles"][0]["amplitude_se"] > f["cycles"][0]["amplitude_se_ols"]
    assert "9 Aug" in f["cycles"][0]["max_date"]                 # 1 Jan + 220 days


def test_monthly_and_weekly_aggregates_and_wls():
    s = planted(gaps=0.3)
    m = aggregate(s, "MS")
    w = aggregate(s, "W")
    assert {"value", "n", "se"} <= set(m.columns) and m.n.min() >= 10 and w.n.min() >= 4
    fm = fit_harmonics(m.value, [365.25, 182.625], se=m.se, weighted=True)
    assert fm["weighted"] and fm["cycles"][0]["amplitude"] == pytest.approx(8, abs=0.4)
    fw = fit_harmonics(w.value, [365.25, 182.625])
    assert fw["cycles"][1]["amplitude"] == pytest.approx(1.5, abs=0.3)
    med = aggregate(s, "MS", how="median")
    assert len(med) == len(m)


def test_nested_comparison_each_cycle_adds():
    tab = compare_nested(planted(), TEMP_PERIODS)
    assert list(tab.k) == [0, 1, 2, 3]
    assert (tab.dAIC.iloc[1:] < 0).all()
    assert tab.r2.is_monotonic_increasing and (tab.p_hac.iloc[1:] < 0.01).all()


def test_spurious_cycle_not_significant():
    s = planted(seed=3)
    f = fit_harmonics(s, [365.25, 182.625, 9.0, 47.0])         # 47 d is not planted
    assert f["cycles"][3]["p_value"] > 0.01


def test_psd_session_synthetic_series():
    """Same SYNTHETIC 40-year series as the PSD method check: planted annual amp 8, max doy 220."""
    from synthetic import synthetic_long_daily
    df = synthetic_long_daily()
    p = df.attrs["planted"]
    s = df["sst"]
    m = aggregate(s[s.index >= s.index[-1] - pd.DateOffset(years=20)], "MS")
    f = fit_harmonics(m.value, [p["annual_period_d"], p["semiannual_period_d"]])
    assert f["cycles"][0]["amplitude"] == pytest.approx(p["annual_amp"], rel=0.05)
    assert f["cycles"][0]["t_max_d"] == pytest.approx(p["annual_peak_doy"] - 1, abs=4)
    assert f["cycles"][1]["amplitude"] == pytest.approx(p["semiannual_amp"], abs=0.25)
    tr = linear_trend(s, exclude_year=2100)
    assert tr["meaningful"] and tr["ci"][0] <= 10 * p["trend_per_year"] <= tr["ci"][1] + 0.1


def test_trend_recovery_and_short_record():
    s = planted(start="2000-01-01", end="2019-12-31", trend_per_year=0.03, noise=0.3)
    tr = linear_trend(s, exclude_year=2100)
    assert tr["n_years"] == 20 and tr["meaningful"]
    assert tr["ci"][0] <= 0.3 <= tr["ci"][1] and tr["p_value"] < 0.05
    short = linear_trend(planted(start="2024-04-06", end="2026-11-22"), exclude_year=2026)
    assert not short["meaningful"] and np.isnan(short["slope_per_decade"])
    assert "not meaningful" in short["note"]


def test_completeness_rule():
    s = planted(start="2010-01-01", end="2012-12-31")
    s = s[~((s.index.year == 2011) & s.index.month.isin([6, 7, 8]))]      # summer 2011 missing
    am = annual_means(s, exclude_year=2012)
    assert bool(am.loc[2010, "complete"]) and not bool(am.loc[2011, "complete"])
    assert am.loc[2012, "reason"] == "current year"


def test_select_periods_from_peaks_format():
    peaks = pd.DataFrame([
        dict(station="X", variable="sst", source="insitu", spectrum="full", period_d=380.0, cycle="annual",
             psd_over_95_level=10.0, seg_days=1096),
        dict(station="X", variable="sst", source="insitu", spectrum="full", period_d=183.0, cycle="semi-annual",
             psd_over_95_level=2.0, seg_days=1096),
        dict(station="X", variable="sst", source="insitu", spectrum="anomalies", period_d=90.0,
             cycle="intraseasonal", psd_over_95_level=1.5, seg_days=365),
        dict(station="X", variable="sst", source="insitu", spectrum="anomalies", period_d=2.4, cycle="2-3 day",
             psd_over_95_level=3.0, seg_days=365),
        dict(station="X", variable="sst", source="insitu", spectrum="anomalies", period_d=50.0,
             cycle="intraseasonal", psd_over_95_level=0.8, seg_days=365),
    ])
    sel = select_periods(peaks, "X", "sst", "insitu", step_d=30.4, record_d=3000)
    assert [round(c["period_d"], 2) for c in sel] == [365.25, 182.62, 90.0]     # 2.4 d not fittable, 50 d not sig.
    assert sel[0]["snapped"] and sel[0]["period_psd"] == 380.0
    daily = select_periods(peaks, "X", "sst", "insitu", step_d=1, record_d=3000)
    assert [c["period_d"] for c in daily][:2] == [365.25, 2.4]


def test_select_periods_fallback_only_seasonal():
    peaks = pd.DataFrame([
        dict(station="X", variable="sst", source="insitu", spectrum="anomalies", period_d=19.0,
             cycle="intraseasonal", psd_over_95_level=1.1, seg_days=365),
        dict(station="X", variable="sst", source="satellite", spectrum="full", period_d=370.0, cycle="annual",
             psd_over_95_level=20.0, seg_days=1096),
        dict(station="X", variable="sst", source="satellite", spectrum="anomalies", period_d=16.0,
             cycle="intraseasonal", psd_over_95_level=1.6, seg_days=365),
    ])
    sel = select_periods(peaks, "X", "sst", "insitu", step_d=7, record_d=950, fallback=[("X", "sst", "satellite")])
    assert [c["period_d"] for c in sel] == [19.0, 365.25]                     # 16 d not borrowed (< 60 d)
    assert sel[1]["from_series"] == "X/sst/satellite" and sel[0]["from_series"] == "X/sst/insitu"


def test_select_periods_current_peaks_format():
    """Format written by the PSD step from 19:41: period_days, significant_95, rank, source 'in situ'."""
    rows = [("in situ", 396.96, True, 1, "full", "annual"), ("in situ", 101.26, True, 2, "anomalies", "x"),
            ("in situ", 12.66, True, 3, "anomalies", "x"), ("in situ", 182.67, False, None, "full", "semi-annual"),
            ("satellite", 364.58, True, 1, "full", "annual"), ("satellite", 180.8, True, 2, "full", "semi-annual")]
    peaks = pd.DataFrame([dict(variable="sst", source=s, station="X", synthetic=False, method="m", period_days=p,
                               power=1.0, significant_95=sig, rank=r, spectrum=sp, cycle=c)
                          for s, p, sig, r, sp, c in rows])
    sel = select_periods(peaks, "X", "sst", "insitu", step_d=30.4, record_d=3700,
                         fallback=[("X", "sst", "satellite")])
    assert [round(c["period_d"], 1) for c in sel] == [365.2, 101.3, 182.6]
    assert sel[0]["snapped"] and sel[2]["from_series"] == "X/sst/satellite"   # own semi-annual not significant
