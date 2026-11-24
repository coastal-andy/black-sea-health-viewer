"""Small data-side fixes asked by the viewer (issue #2, request 4).

    .venv/bin/python -m pytest -q tests/test_small_fixes.py

Cache only (MARINEKIT_OFFLINE=1). Checks:
  a) indicators.sst_display gives the same value, date and unit as the temperature card;
  b) the clarity card's public text uses the same rounded Secchi depth as its value;
  c) every sector_zones feature has buffer_label, and the other fields are those of the frozen interface.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("MARINEKIT_OFFLINE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from marinekit import datahub as dh  # noqa: E402
from marinekit import indicators as ind  # noqa: E402
from marinekit import pressure_zones as pz  # noqa: E402
from marinekit.sources import STATIONS  # noqa: E402

LAT, LON = STATIONS["Constanta"]
DATES = [str(dh.today().date()), "2024-07-20"]
ZONES = ROOT / "data" / "zones" / "sector_zones.geojson"
ZONE_FIELDS = {"sector", "activity", "buffer_m", "buffer_basis", "basis_ref", "season", "confidence",
               "n_features", "area_km2", "style_key"}


def test_sst_display_matches_card():
    for d in DATES:
        c = ind.card("temperature", LAT, LON, d)
        s = ind.sst_display(LAT, LON, d)
        assert set(s) >= {"value", "unit", "label", "dataset", "date", "origin"}
        assert s["unit"] == c["unit"] == "°C" and s["origin"] == "satellite"
        assert s["value"] == c["value"], (d, s, c["value"])
        if c["value"] is not None:
            assert s["date"] and s["date"] in c["why"]
            assert s["dataset"]


def test_clarity_text_uses_value():
    seen = 0
    for d in DATES:
        c = ind.card("clarity", LAT, LON, d)
        if c["value"] is None:
            continue
        seen += 1
        assert f"about {c['value']:.1f} m" in c["text"]["public"], (c["value"], c["text"]["public"])
    assert seen, "no clarity value in the cache for the test dates"


def test_buffer_label_on_every_zone():
    gj = json.loads(ZONES.read_text(encoding="utf-8"))
    assert gj["features"]
    for f in gj["features"]:
        p = f["properties"]
        assert set(p) == ZONE_FIELDS | {"buffer_label"}, sorted(p)
        assert p["buffer_label"] == pz.buffer_label(p)
        if p["activity"] == "shipping_lane":
            assert p["buffer_m"] == 0 and p["buffer_label"] == "AIS density cells, no buffer"
        elif p["buffer_m"] > 0:
            assert p["buffer_label"] == f"{p['buffer_m']:.0f} m ({p['buffer_basis']})"


def test_add_buffer_labels_is_idempotent(tmp_path):
    t = tmp_path / "z.geojson"
    t.write_bytes(ZONES.read_bytes())
    pz.add_buffer_labels(t)
    assert t.read_bytes() == ZONES.read_bytes()
