"""Tests for marinekit.indicators and marinekit.datahub (workstream I).

Run with pytest if installed:   .venv/bin/python -m pytest -q tests/test_indicators.py
or as a plain script:            .venv/bin/python tests/test_indicators.py

They read only the disk cache (MARINEKIT_OFFLINE=1 is set below), so run scripts/preload_cache.py once first.
Constanta "today" and a summer-2024 date must give the full key set for every card.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
import warnings
from pathlib import Path

os.environ.setdefault("MARINEKIT_OFFLINE", "1")          # cache only: no network beyond what is already cached
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from marinekit import datahub as dh  # noqa: E402
from marinekit import indicators as ind  # noqa: E402
from marinekit.sources import STATIONS  # noqa: E402

LAT, LON = STATIONS["Constanta"]
TODAY = str(dh.today().date())
SUMMER_2024 = "2024-07-20"
SOURCE_KEYS = {"dataset", "origin", "date", "distance_km"}
EMOJI_RANGES = [(0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x1F000, 0x1F2FF)]

_cards: dict[str, list[dict]] = {}


def _get(date: str) -> list[dict]:
    if date not in _cards:
        _cards[date] = [ind.card(cid, LAT, LON, date, profile="stakeholder:aquaculture") for cid in ind.CARDS]
    return _cards[date]


def _check_cards(cards: list[dict], date: str):
    assert [c["id"] for c in cards] == ind.CARDS
    for c in cards:
        missing = set(ind.CARD_KEYS) - set(c)
        assert not missing, f"{c['id']} {date}: missing keys {missing}"
        assert c["status"] in ind.STATUSES, f"{c['id']}: bad status {c['status']}"
        assert c["evidence"] in ("measured", "satellite", "model"), f"{c['id']}: bad evidence {c['evidence']}"
        assert c["confidence"] in ("high", "medium", "low"), f"{c['id']}: bad confidence {c['confidence']}"
        assert isinstance(c["reference"], dict)
        assert isinstance(c["investigate"], list)
        assert isinstance(c["sources"], list)
        for s in c["sources"]:
            assert SOURCE_KEYS <= set(s), f"{c['id']}: source entry missing keys {SOURCE_KEYS - set(s)}"
        for p in ind.PROFILES:
            t = c["text"].get(p)
            assert isinstance(t, str) and len(t.strip()) > 10, f"{c['id']} {date}: no text for profile {p}"
            assert not any(lo <= ord(ch) <= hi for ch in t for lo, hi in EMOJI_RANGES), f"{c['id']}: emoji in {p}"
        assert c["why"].strip(), f"{c['id']}: empty why"
        assert c["driver_note"].strip(), f"{c['id']}: empty driver_note"
        if c["status"] != "no_data":
            assert c["value"] is not None, f"{c['id']}: status {c['status']} but no value"


def test_cards_today_full_keys():
    _check_cards(_get(TODAY), TODAY)


def test_cards_summer_2024_full_keys():
    _check_cards(_get(SUMMER_2024), SUMMER_2024)


def test_core_cards_have_data_today():
    # with a warm cache the satellite / model cards must not fall back to no_data at Constanta
    st = {c["id"]: c["status"] for c in _get(TODAY)}
    for cid in ("temperature", "oxygen", "blooms", "clarity", "drivers", "acidification"):
        assert st[cid] != "no_data", f"{cid} is no_data today"


def test_thresholds_are_labelled():
    for c in _get(TODAY) + _get(SUMMER_2024):
        if c["status"] == "no_data" or c["id"] in ("drivers",):
            continue
        tt = c["reference"].get("threshold_type", "")
        assert any(k in tt for k in ("OFFICIAL-RO", "OFFICIAL-EU", "OURS", "LIT")), f"{c['id']}: unlabelled threshold"


def test_rule_chain():
    base = {"month": 7, "upwelling": False, "storm": False, "stratified": False, "danube_ratio30": 1.0, "sal": 17.0,
            "pressure": {"sectors": ["ports"], "n": 1}}
    assert ind.classify_cause(None, base)["label"] == "none"
    assert ind.classify_cause("cold", {**base, "upwelling": True, "upwelling_dT": -4})["label"] == "natural"
    assert ind.classify_cause("low_o2_bottom", {**base, "bottom_sal": 19.2}, model_only=True)["label"] == "model artefact"
    assert ind.classify_cause("low_o2_bottom", {**base, "bottom_sal": 19.2})["rule"] == 3
    r = ind.classify_cause("low_o2_bottom", {**base, "stratified": True, "strat_dT": 6}, bloom_recent=True)
    assert r["label"] == "pressure-related" and r["rule"] == 6
    assert ind.classify_cause("low_clarity", {**base, "storm": True})["rule"] == 5
    assert ind.classify_cause("high_chl", {**base, "danube_ratio30": 1.5, "spring_above_p75": True})["label"] == "mixed"
    assert ind.classify_cause("high_chl", {**base}, persist_days=7)["label"] == "possible pressure"
    assert ind.classify_cause("warm", {**base}, persist_days=20)["label"] == "climate"


def test_zone_cards_polygon():
    poly = {"type": "Polygon", "coordinates": [[[28.70, 44.15], [28.76, 44.15], [28.76, 44.19], [28.70, 44.19],
                                                [28.70, 44.15]]]}
    cs = ind.zone_cards(poly, TODAY, "public")
    assert [c["id"] for c in cs] == ind.CARDS
    assert all(any(s["dataset"] == "zone sampling" for s in c["sources"]) for c in cs)


def test_datahub_auto_choices():
    s, e = dh.card_window(TODAY)
    assert dh.get_series("sst", LAT, LON, s, e).attrs["origin"] == "satellite"
    assert dh.get_series("chl", LAT, LON, s, e).attrs["origin"] == "satellite"
    assert dh.get_series("bottom_temp", LAT, LON, s, e).attrs["evidence"] == "model"
    no3 = dh.get_series("no3", LAT, LON, s, e)          # never the model as absolute values
    assert no3.attrs["source_id"] == "bottles"
    for v in dh.VARIABLES:
        for sp in dh.SOURCES[v]:
            if sp["trust"] == "untrusted":
                assert sp["id"] not in ("satellite", "model")
    cl = dh.get_climatology("sst", LAT, LON)
    assert len(cl) == 365 and {"mean", "std", "p10", "p90"} <= set(cl.columns)


def test_timing_warm_cache():
    dh.clear_memory_cache()
    ind._drivers_cached.cache_clear()
    t0 = time.time()
    worst = 0.0
    for cid in ind.CARDS:
        t = time.time()
        ind.card(cid, LAT, LON, TODAY)
        worst = max(worst, time.time() - t)
    total = time.time() - t0
    print(f"    timing (memory caches cleared, disk warm): slowest card {worst:.2f} s, all cards {total:.2f} s")
    assert worst < 3 and total < 10, (worst, total)         # targets from WORKFLOW: ~3 s per card, ~10 s per point


TESTS = [test_cards_today_full_keys, test_cards_summer_2024_full_keys, test_core_cards_have_data_today,
         test_thresholds_are_labelled, test_rule_chain, test_zone_cards_polygon, test_datahub_auto_choices,
         test_timing_warm_cache]

if __name__ == "__main__":
    ok = 0
    for t in TESTS:
        t0 = time.time()
        try:
            t()
            ok += 1
            print(f"PASS {t.__name__} ({time.time() - t0:.1f} s)")
        except Exception:  # noqa: BLE001
            print(f"FAIL {t.__name__} ({time.time() - t0:.1f} s)")
            traceback.print_exc(limit=4)
    print(ind.card_summary(_get(TODAY)).to_string(index=False))
    print(f"\n{ok}/{len(TESTS)} passed")
    sys.exit(0 if ok == len(TESTS) else 1)
