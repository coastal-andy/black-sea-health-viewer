"""Tests for marinekit.validation (source uncertainty API for the viewer). Reads committed CSVs only, no network."""
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from marinekit import validation as val  # noqa: E402

METRICS = pd.read_csv(ROOT / "docs" / "indicators" / "validation" / "metrics.csv")
KEYS = {"variable", "unit", "trusted_source", "rmse", "bias", "n", "stations", "confidence", "reading", "pairs",
        "untrusted", "basis"}
PAIR_KEYS = {"pair", "n", "bias", "rmse", "r2", "r2_anom", "station"}


def test_every_metrics_variable_is_covered():
    assert set(val.variables()) == set(METRICS["variable"])
    assert {"sst", "chl", "sal", "o2", "no3", "po4"} <= set(val.variables())


@pytest.mark.parametrize("var", sorted(METRICS["variable"].unique()))
def test_summary_keys_and_pairs_match_metrics(var):
    s = val.source_summary(var)
    assert KEYS <= set(s)
    assert s["confidence"] in {"high", "medium", "low"}
    assert s["reading"] and s["unit"] and s["trusted_source"] in {"satellite", "model", "in situ"}
    rows = METRICS[METRICS["variable"] == var]
    assert len(s["pairs"]) == len(rows)
    for p in s["pairs"]:
        assert PAIR_KEYS <= set(p)
        r = rows[(rows.station == p["station"]) & (rows.pair == p["pair"])].iloc[0]
        assert p["n"] == r["n"]
        assert p["rmse"] == pytest.approx(r["rmse"]) and p["bias"] == pytest.approx(r["bias"])
        assert p["r2"] == pytest.approx(r["r2"])
    head = [p for p in s["pairs"] if p["headline"]]
    assert head and s["n"] == sum(p["n"] for p in head)
    assert s["stations"] == [p["station"] for p in head]
    if s["rmse"] is not None:
        w = sum(p["n"] for p in head)
        assert s["rmse"] == pytest.approx(math.sqrt(sum(p["n"] * p["rmse"] ** 2 for p in head) / w))
        assert s["bias"] == pytest.approx(sum(p["n"] * p["bias"] for p in head) / w)
    assert s["basis"]["start"] <= s["basis"]["end"]


def test_headlines_consistent_with_interpretation():
    sst = val.source_summary("sst")
    assert sst["trusted_source"] == "satellite" and sst["confidence"] == "high"
    assert abs(sst["rmse"] - 0.45) < 0.05 and all(abs(b) < 0.15 for b in sst["bias_range"])
    assert set(sst["stations"]) == {"EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo03"}
    sal = val.source_summary("sal")
    assert sal["trusted_source"] == "model" and abs(sal["rmse"] - 1.0) < 0.2
    chl = val.source_summary("chl")
    assert chl["trusted_source"] == "satellite" and 1.5 < 10 ** chl["rmse"] < 1.8   # factor about 1.6
    o2 = val.source_summary("o2")
    assert abs(o2["rmse"] - 1.0) < 0.15 and max(abs(b) for b in o2["bias_range"]) < 0.75
    for v in ("no3", "po4"):
        s = val.source_summary(v)
        assert s["rmse"] is None and s["bias"] is None and s["confidence"] == "low"
        assert any("model" in u["source"].lower() for u in s["untrusted"])


def test_untrusted_sources_listed_with_reason():
    for v in val.variables():
        for u in val.source_summary(v)["untrusted"]:
            assert u["source"] and u["reason"]
    names = " ".join(u["source"] for u in val.source_summary("chl")["untrusted"])
    assert "EUXRoOB01-03" in names and "EUXRo03" in names
    assert any("EUXRoOB01-03" in u["source"] for u in val.source_summary("sal")["untrusted"])


def test_unknown_variable_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown variable 'waves'.*sst"):
        val.source_summary("waves")
    with pytest.raises(ValueError):
        val.pair_points("nope")


def test_summary_table_one_row_per_variable():
    t = val.summary_table()
    assert list(t["variable"]) == val.variables()
    assert {"trusted_source", "rmse", "bias", "error_unit", "confidence", "reading", "untrusted"} <= set(t.columns)


def test_pair_points():
    all_sst = val.pair_points("sst")
    assert list(all_sst.columns) == ["station", "variable", "date", "season", "insitu", "satellite", "model"]
    assert pd.api.types.is_datetime64_any_dtype(all_sst["date"])
    one = val.pair_points("sst", station="EUXRoOB01")
    assert len(one) == 823 and set(one["station"]) == {"EUXRoOB01"}
    assert set(one["season"]) == {"DJF", "MAM", "JJA", "SON"}
    assert val.pair_points("sal")["satellite"].isna().all()
    with pytest.raises(ValueError, match="station"):
        val.pair_points("no3", station="EUXRoOB01")
