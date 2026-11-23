"""Demo / smoke test for src/viewer/vectorviz.py: writes standalone HTML previews to docs/viz/.

Run:  .venv/bin/python scripts/viz/demo_vectorviz.py
Outputs:
  docs/viz/wave_map.html        latest wave analysis hour: Hs colour, arrows = direction of travel, length = Tp
  docs/viz/current_map.html     today's daily-mean surface currents: speed colour + arrows
  docs/viz/combined_map.html    waves + currents + wind (reference points) as toggleable layers on one map
  docs/viz/wave_chart.html      7 days at Constanta (44.17, 28.72)
  docs/viz/current_chart.html   7 days of daily-mean currents at Constanta
  docs/viz/wind_chart.html      7 days of wind at Constanta
  docs/viz/combined_chart.html  the three stacked with one time axis
  docs/viz/timings.json         load and draw timings
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import folium  # noqa: E402

from marinekit.sources import BBOX_RO  # noqa: E402
from viewer import vectorviz as vv  # noqa: E402

OUT = ROOT / "docs" / "viz"
OUT.mkdir(parents=True, exist_ok=True)
LAT, LON = 44.17, 28.72


def timed(label, fn, timings):
    t0 = time.perf_counter()
    out = fn()
    timings[label] = round(time.perf_counter() - t0, 3)
    print(f"{label:28s} {timings[label]:7.3f} s")
    return out


def main():
    timings = {}
    now = pd.Timestamp.now("UTC").tz_localize(None).floor("h")

    waves = timed("load_field waves", lambda: vv.load_field("waves", BBOX_RO), timings)
    cur = timed("load_field currents", lambda: vv.load_field("currents", BBOX_RO), timings)
    wind = timed("load_field wind (points)", lambda: vv.load_field("wind", BBOX_RO, waves.attrs["time"]), timings)

    m = vv.base_map()
    timed("field_layer waves", lambda: vv.field_layer(m, waves), timings)
    m.save(OUT / "wave_map.html")

    m = vv.base_map()
    timed("field_layer currents", lambda: vv.field_layer(m, cur), timings)
    m.save(OUT / "current_map.html")

    m = vv.base_map()
    timed("combined map (3 layers)", lambda: (vv.field_layer(m, waves), vv.field_layer(m, cur, show=False),
                                              vv.field_layer(m, wind, legend_pos="topright")), timings)
    folium.LayerControl(collapsed=False, position="topleft").add_to(m)
    m.save(OUT / "combined_map.html")

    start = now - pd.Timedelta(days=7)
    dw = timed("load_point waves 7 d", lambda: vv.load_point("waves", LAT, LON, start, now), timings)
    dc = timed("load_point currents 7 d", lambda: vv.load_point("currents", LAT, LON, start, now), timings)
    dd = timed("load_point wind 7 d", lambda: vv.load_point("wind", LAT, LON, start, now), timings)

    timed("point_chart waves", lambda: vv.point_chart(dw, "waves"), timings).write_html(
        OUT / "wave_chart.html", include_plotlyjs="cdn")
    timed("point_chart currents", lambda: vv.point_chart(dc, "currents"), timings).write_html(
        OUT / "current_chart.html", include_plotlyjs="cdn")
    timed("point_chart wind", lambda: vv.point_chart(dd, "wind"), timings).write_html(
        OUT / "wind_chart.html", include_plotlyjs="cdn")
    vv.combined_chart({"waves": dw, "currents": dc, "wind": dd}).write_html(
        OUT / "combined_chart.html", include_plotlyjs="cdn")
    vv.point_chart(dw, "waves", theme="dark").write_html(OUT / "wave_chart_dark.html", include_plotlyjs="cdn")

    timings["wave_time"] = waves.attrs["time"]
    timings["current_time"] = cur.attrs["time"]
    (OUT / "timings.json").write_text(json.dumps(timings, indent=1))
    print("wrote", sorted(p.name for p in OUT.glob("*.html")))


if __name__ == "__main__":
    main()
