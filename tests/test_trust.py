"""Per-variable sensor trust flags in marinekit.datahub (VARIABLE_TRUST). No network: the fetchers are replaced by
synthetic series, so these tests check the source-selection logic only."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from marinekit import datahub as dh  # noqa: E402

OB02 = (dh.PLATFORMS["EUXRoOB02"]["lat"], dh.PLATFORMS["EUXRoOB02"]["lon"])   # a point on top of a flagged buoy
START, END = "2025-06-01", "2025-06-10"


def _const(v):
    idx = pd.date_range(START, END, freq="D")
    return pd.Series(float(v), index=idx)


@pytest.fixture
def fake(monkeypatch):
    """Buoys return 99, the model 18 (sal) or 0.5 (chl), the satellite chl 0.4; records which buoys were read."""
    seen = []
    dh.clear_memory_cache()

    def platform_series(pid, col, start, end, scale=1.0):
        seen.append((pid, col))
        return _const(99) * scale, {"dataset": f"{pid} (fake)", "platform": pid, "origin": "in-situ"}

    def fetch_pair(spec, lat, lon, start, end):
        return _const(18.0 if spec.get("col") == "sal" else 0.5), [{"dataset": "model (fake)"}]

    monkeypatch.setattr(dh, "_platform_series", platform_series)
    monkeypatch.setattr(dh, "_fetch_pair", fetch_pair)
    monkeypatch.setattr(dh, "_fetch_chl_sat", lambda *a: (_const(0.4), [{"dataset": "sat (fake)"}], []))
    yield seen
    dh.clear_memory_cache()


def test_table_content():
    for p in ("EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo03"):
        assert dh.variable_trust(p, "chl")[0] == "indicative"
    for p in ("EUXRoOB01", "EUXRoOB02", "EUXRoOB03"):
        assert dh.variable_trust(p, "sal")[0] == "untrusted"
    assert dh.variable_trust("EUXRo03", "sal")[0] == "good"          # kept: no fouling evidence at EUXRo03
    assert dh.variable_trust("EUXRoOB02", "o2")[0] == "good"         # other variables unchanged
    assert dh.variable_trust("EUXRoCB02", "o2")[0] == "untrusted"    # platform-level flags unchanged
    assert dh.variable_trust("15480", "sst")[0] == "untrusted"
    for trust, why in dh.VARIABLE_TRUST.values():
        assert trust in ("indicative", "untrusted") and why


def test_auto_sal_is_model(fake):
    df = dh.get_series("sal", *OB02, START, END)
    assert df.attrs["source_id"] == "model" and df["sal"].iloc[0] == 18.0


def test_auto_chl_is_satellite(fake):
    df = dh.get_series("chl", *OB02, START, END)
    assert df.attrs["source_id"] == "satellite"


def test_auto_chl_never_falls_back_to_buoy(fake, monkeypatch):
    def boom(*a, **k):
        raise dh.DataUnavailable("down")
    monkeypatch.setattr(dh, "_fetch_chl_sat", boom)
    monkeypatch.setattr(dh, "_fetch_pair", boom)
    with pytest.raises(dh.DataUnavailable):
        dh.get_series("chl", *OB02, START, END)
    assert not [s for s in fake if s[1] == "chl"]


def test_auto_sal_fallback_skips_flagged_buoys(fake, monkeypatch):
    def boom(*a, **k):
        raise dh.DataUnavailable("down")
    monkeypatch.setattr(dh, "_fetch_pair", boom)
    df = dh.get_series("sal", *OB02, START, END)          # model down: only EUXRo03 is an allowed buoy for sal
    assert df.attrs["platform"] == "EUXRo03"
    assert all(p == "EUXRo03" for p, c in fake if c == "sal")


def test_explicit_buoy_still_returned_with_flag(fake):
    df = dh.get_series("sal", *OB02, START, END, source="buoy")
    assert df.attrs["platform"] == "EUXRoOB02" and df.attrs["trust"] == "untrusted"
    assert any("fouling" in n for n in df.attrs["notes"])
    c = dh.get_series("chl", *OB02, START, END, source="buoy")
    assert c.attrs["trust"] == "indicative"


def test_auto_o2_still_uses_buoy(fake):
    df = dh.get_series("o2", *OB02, START, END)
    assert df.attrs["source_id"] == "buoy" and df.attrs["platform"] == "EUXRoOB02" and df.attrs["trust"] == "good"


def test_compare_sources_lists_flagged_buoy(fake):
    for var, trust in (("sal", "untrusted"), ("chl", "indicative")):
        cmp = dh.compare_sources(var, *OB02, START, END)
        buoy = [c for c in cmp.columns if c.startswith("buoy")]
        assert buoy, cmp.attrs["failed"]
        assert cmp.attrs["sources"][buoy[0]]["trust"] == trust


def test_obs_vs_model_reports_obs_trust(fake):
    r = dh.obs_vs_model("sal", *OB02, START, END)
    assert r["obs_trust"] == "untrusted" and "VARIABLE_TRUST" in r["note"]
