"""Tests for the viewer API of marinekit.seasonal (seasonal cycle, usual range, long-term trend, quality gate).

SYNTHETIC series through a fake datahub (no network, no cache), plus the precomputed lookup of
docs/indicators/seasonal/*.csv with get_series failing (offline, empty cache) so trust comes from datahub's register.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from marinekit import datahub as real_dh  # noqa: E402
from marinekit import seasonal as se  # noqa: E402

FAR = (45.30, 29.10)          # > 5 km from every fitted station: forces the on-the-fly fit


def synthetic(years: float, amp: float, noise: float, seed: int = 0) -> pd.Series:
    """SYNTHETIC daily SST-like series ending yesterday: mean 15, annual cycle (max ~ 10 Aug), AR(1) noise."""
    end = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    idx = pd.date_range(end - pd.Timedelta(days=int(years * 365.25)), end, freq="D")
    rng = np.random.default_rng(seed)
    e = np.zeros(len(idx))
    for i in range(1, len(idx)):
        e[i] = 0.7 * e[i - 1] + rng.normal(0, noise)
    doy = idx.day_of_year.to_numpy()
    return pd.Series(15 + amp * np.cos(2 * np.pi * (doy - 222) / 365.25) + e, index=idx)


def fake_dh(series: pd.Series | None, trust: str = "good"):
    def get_series(variable, lat, lon, start, end, source="auto"):
        if series is None:
            raise real_dh.DataUnavailable("SYNTHETIC: no cache")
        s = series[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
        df = s.rename(variable).to_frame()
        df.attrs = dict(trust=trust, label="SYNTHETIC source", origin="satellite", source_id=source)
        return df
    return SimpleNamespace(SOURCES=real_dh.SOURCES, get_series=get_series,
                           variable_trust=getattr(real_dh, "variable_trust", lambda p, v: ("good", None)))


@pytest.fixture
def use(monkeypatch):
    def _use(dh):
        se._series.cache_clear()
        se._trust.cache_clear()
        monkeypatch.setattr(se, "_dh", lambda: dh)
    yield _use
    se._series.cache_clear()
    se._trust.cache_clear()


# ------------------------------------------------------------------------------------------------ pure gate rules
def test_cycle_gate_rules():
    assert se._cycle_gate("good", 1e-6, 0.9)[0]
    assert se._cycle_gate("usable", 0.01, 0.5)[0]
    assert not se._cycle_gate("indicative", 1e-6, 0.9)[0]
    assert not se._cycle_gate("untrusted", 1e-6, 0.9)[0]
    ok, why = se._cycle_gate("good", 0.2, 0.9)
    assert not ok and "no significant" in why
    ok, why = se._cycle_gate("good", 0.001, 0.3)
    assert not ok and "adjusted R2" in why


def test_trend_gate_rules():
    show, why, level = se._trend_gate("good", 5, 0.01)
    assert not show and "not enough years yet" in why and level == "none"
    show, why, level = se._trend_gate("good", 10, 0.2)
    assert show and level == "indicative" and "not significant" in why
    show, why, level = se._trend_gate("good", 25, 0.001)
    assert show and level == "climate" and "not significant" not in why
    assert not se._trend_gate("untrusted", 40, 0.001)[0]


# ------------------------------------------------------------------------------------------ SYNTHETIC end to end
def test_strong_cycle_passes(use):
    use(fake_dh(synthetic(6, amp=9.0, noise=0.3)))
    c = se.seasonal_cycle("sst", *FAR, source="satellite")
    assert c["show"], c["gate_reason"]
    assert c["method"].startswith("fitted on the fly")
    assert abs(c["annual"]["amplitude"] - 9.0) < 0.6
    assert c["max_date"].endswith("Aug")
    assert c["r2_adj"] > 0.9 and c["trust"] == "good"
    u = se.usual_range("sst", *FAR, pd.date_range("2026-01-01", "2026-12-31", freq="MS"), source="satellite")
    assert list(u.columns) == ["fit", "lo", "hi"] and (u.lo < u.fit).all() and (u.fit < u.hi).all()
    assert u.fit.idxmax().month in (7, 8, 9) and u.attrs["show"]


def test_weak_cycle_fails(use):
    use(fake_dh(synthetic(6, amp=0.2, noise=1.5, seed=3)))
    c = se.seasonal_cycle("sst", *FAR, source="satellite")
    assert not c["show"]
    assert "R2" in c["gate_reason"] or "no significant" in c["gate_reason"]
    assert c["text"].startswith("Seasonal cycle not shown")


def test_untrusted_source_fails(use):
    use(fake_dh(synthetic(6, amp=9.0, noise=0.3), trust="indicative"))
    c = se.seasonal_cycle("sst", *FAR, source="satellite")
    assert not c["show"] and "trust" in c["gate_reason"]


def test_short_record_not_enough_years(use):
    use(fake_dh(synthetic(4, amp=9.0, noise=0.3)))
    t = se.long_term_trend("sst", *FAR, source="satellite")
    assert not t["show"] and not t["enough_years"]
    assert "not enough years yet" in t["gate_reason"]
    assert np.isnan(t["slope_per_decade"])


def test_no_cache_gives_reason(use):
    use(fake_dh(None))
    c = se.seasonal_cycle("sst", *FAR, source="satellite")
    assert not c["show"] and "no cached" in c["gate_reason"]


# ------------------------------------------------------------------------------- precomputed lookup, offline
def test_precomputed_lookup_offline(use):
    use(fake_dh(None))                   # get_series fails: trust from datahub's register
    lat, lon = se.STATIONS["EUXRo03"]
    c = se.seasonal_cycle("sst", lat, lon)
    assert c["station"] == "EUXRo03" and c["method"].startswith("precomputed")
    assert c["show"] and "register" in c["trust_from"]
    assert 8.0 < c["annual"]["amplitude"] < 10.0 and c["semi_annual"] is not None
    assert len(c["periods_d"]) == 3
    t = se.long_term_trend("sst", lat, lon)
    assert t["show"] and t["enough_years"] and t["level"] in ("indicative", "climate")
    if t["table"] == "trends_long":
        assert t["level"] == "climate" and t["n_years"] >= 20
    g = se.gate_summary()
    assert {"station", "variable", "source", "cycle_show", "cycle_reason", "trend_show", "trend_reason"} <= set(g)
    assert g[(g.variable == "sst")].cycle_show.all()
    assert g.cycle_reason.str.len().gt(0).all()


def test_scripts_reexport_same_functions():
    sys.path.insert(0, str(ROOT / "scripts" / "seasonal"))
    import harmonic
    import trend
    assert harmonic.fit_harmonics is se.fit_harmonics and harmonic.select_periods is se.select_periods
    assert trend.linear_trend is se.linear_trend
