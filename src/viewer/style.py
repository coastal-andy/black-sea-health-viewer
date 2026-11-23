"""Colours, CSS and small HTML helpers for the viewer. Okabe-Ito palette, no emoji."""

from __future__ import annotations

import html

# Okabe-Ito
OI = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "grey": "#8C8C8C",
}

STATUS = {
    "normal": ("#009E73", "Normal"),
    "watch": ("#E69F00", "Watch"),
    "alert": ("#D55E00", "Alert"),
    "no_data": ("#8C8C8C", "No data"),
}

# evidence / origin -> colour used in every chart, so "measured / satellite / model" always look the same
ORIGIN = {
    "measured": OI["black"], "in-situ": OI["black"],
    "satellite": OI["blue"],
    "model": OI["orange"], "reanalysis": OI["vermillion"],
    "climatology": OI["grey"], "derived": OI["purple"],
}
ORIGIN_LABEL = {"in-situ": "measured", "measured": "measured", "satellite": "satellite", "model": "model",
                "reanalysis": "model (reanalysis)", "derived": "derived", "climatology": "reference"}

# the sector colours already used in data/zones (pressure_zones.py), kept identical
SECTOR = {
    "ports": ("Ports and logistics", "#0072B2"),
    "shipyards": ("Shipyards and marine engineering", "#D55E00"),
    "tourism": ("Coastal and marine tourism", "#E69F00"),
    "fishing": ("Fishing", "#009E73"),
    "aquaculture": ("Aquaculture", "#CC79A7"),
}

# overlap count 1..5: read from data/zones/overlap_style.json (shared with the QGIS project), with this fallback
_OVERLAP_FALLBACK = [(1, "#FDE0B2", 0.45), (2, "#F4A259", 0.70), (3, "#D55E00", 0.85), (4, "#8C2D04", 0.90),
                     (5, "#4A1402", 0.95)]


def overlap_levels() -> dict:
    """{count: (colour, opacity, label)} from data/zones/overlap_style.json, else the agreed fallback ramp."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / "data" / "zones" / "overlap_style.json"
    try:
        lv = json.loads(f.read_text())["levels"]
        out = {int(x["count"]): (x["color"], float(x.get("opacity", 0.8)), x.get("label") or f"{x['count']} sectors")
               for x in lv}
        if out:
            return out
    except Exception:
        pass
    return {k: (c, a, f"{k} sector{'s' if k > 1 else ''}") for k, c, a in _OVERLAP_FALLBACK}


OVERLAP = {k: v[0] for k, v in overlap_levels().items()}

CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1500px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.bsv-title {font-size: 1.35rem; font-weight: 650; margin: 0; line-height: 1.2;}
.bsv-sub {color: #5A6573; font-size: 0.86rem; margin: 0;}
.bsv-chip {display: inline-block; padding: 2px 10px; border-radius: 999px; background: #E8F1F8; color: #0B4F7C;
           font-size: 0.8rem; font-weight: 600; margin-right: 6px; white-space: nowrap;}
.bsv-pill {display: inline-block; padding: 1px 10px; border-radius: 999px; color: #fff; font-size: 0.78rem;
           font-weight: 650; letter-spacing: 0.02em;}
.bsv-card {border: 1px solid #DDE3E9; border-left-width: 6px; border-radius: 6px; padding: 10px 14px 8px 14px;
           margin-bottom: 12px; background: #fff;}
.bsv-card h4 {margin: 0 0 4px 0; font-size: 1.0rem; font-weight: 650;}
.bsv-card .val {font-size: 1.25rem; font-weight: 650;}
.bsv-card .ref {color: #5A6573; font-size: 0.85rem;}
.bsv-card .row {font-size: 0.88rem; margin: 3px 0;}
.bsv-card .lbl {color: #5A6573; font-weight: 600; margin-right: 4px;}
.bsv-card .src {color: #6B7684; font-size: 0.76rem; margin-top: 6px; border-top: 1px solid #EEF1F4; padding-top: 4px;}
.bsv-origin {display:inline-block; padding: 0 6px; border-radius: 3px; font-size: 0.72rem; font-weight: 650;
             border: 1px solid currentColor; margin-right: 4px;}
.bsv-note {color: #5A6573; font-size: 0.82rem;}
.bsv-box {border: 1px solid #DDE3E9; border-radius: 6px; padding: 10px 14px; background: #F8FAFB; margin-bottom: 10px;}
div[data-testid="stSidebarContent"] {padding-top: 0.6rem;}
</style>
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def pill(status: str) -> str:
    col, lab = STATUS.get(status or "no_data", STATUS["no_data"])
    return f"<span class='bsv-pill' style='background:{col}'>{lab}</span>"


def origin_tag(origin: str) -> str:
    o = (origin or "").lower()
    col = ORIGIN.get(o, OI["grey"])
    return f"<span class='bsv-origin' style='color:{col}'>{esc(ORIGIN_LABEL.get(o, o or 'unknown'))}</span>"


def swatch(color: str, label: str, dashed: bool = False) -> str:
    border = f"2px dashed {color}" if dashed else f"1px solid {color}"
    return (f"<span style='display:inline-block;width:12px;height:12px;background:{color if not dashed else 'transparent'};"
            f"border:{border};margin-right:6px;vertical-align:middle'></span>{esc(label)}")
