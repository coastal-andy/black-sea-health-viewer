"""Direction-convention check for vectorviz (writes docs/viz/direction_check.txt).

1. Copernicus wave VMDR vs Open-Meteo wave_direction: both documented as 'coming FROM'. If they agree
   (small circular difference), the same +180 deg rule is right for both.
2. Waves vs wind offshore: when wind is strong (>= 8 m/s), wind sea comes from roughly the wind direction.
   Compare wave 'to' (VMDR + 180) with wind 'to' (wind_dir + 180): should be close.
3. Copernicus currents (u, v -> atan2(u, v)) vs Open-Meteo current_direction ('towards'): should be close
   when the current is not weak.
4. Unit test of the arrow maths: a wave FROM 0 deg (north) must draw an arrow pointing south (screen +y);
   u = +1, v = 0 must point east.
Run: .venv/bin/python scripts/viz/check_directions.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from marinekit.sources import open_data as od  # noqa: E402
from viewer import vectorviz as vv  # noqa: E402

out = []


def say(s=""):
    print(s)
    out.append(s)


def cdiff(a, b):
    """signed circular difference a - b in (-180, 180]"""
    return (np.asarray(a) - np.asarray(b) + 180) % 360 - 180


def stats(d):
    d = d[np.isfinite(d)]
    return f"n={d.size}, median |diff|={np.median(np.abs(d)):.0f} deg, circular mean diff={np.degrees(np.angle(np.mean(np.exp(1j*np.radians(d))))):.0f} deg, share within 45 deg={np.mean(np.abs(d) <= 45):.0%}"


end = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
start = end - pd.Timedelta(days=14)
say(f"Direction check, {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC")
for name, (lat, lon) in [("Constanta", (44.17, 28.72)), ("Offshore shelf", (44.40, 29.50))]:
    say(f"\n== {name} ({lat}, {lon})")
    w = vv.load_point("waves", lat, lon, start, end)
    om = od.marine_weather(lat, lon, start, end)
    j = w.join(om[["wave_dir", "wind_speed", "wind_dir"]].rename(columns={"wave_dir": "om_wave_dir"}), how="inner")
    say("1. CMEMS VMDR (from) vs Open-Meteo wave_direction (from): " + stats(cdiff(j.wave_dir, j.om_wave_dir)))
    strong = j[j.wind_speed >= 8]
    say("2. wave to-direction vs wind to-direction, wind >= 8 m/s: " +
        (stats(cdiff(strong.dir_to, (strong.wind_dir + 180) % 360)) if len(strong) else "no strong-wind hours"))
    say("   same, all hours: " + stats(cdiff(j.dir_to, (j.wind_dir + 180) % 360)))
    say("   (control) if the +180 were wrongly skipped for waves only, the strong-wind diff would be ~180 deg")
    c = vv.load_point("currents", lat, lon, start, end)
    omc = om[["current_speed", "current_dir"]].dropna()
    rad = np.radians(omc.current_dir)
    du = (omc.current_speed * np.sin(rad)).resample("D").mean()
    dv = (omc.current_speed * np.cos(rad)).resample("D").mean()
    om_to = (np.degrees(np.arctan2(du, dv)) + 360) % 360
    jc = c.join(om_to.rename("om_to"), how="inner")
    jc = jc[jc.current_speed >= 0.05]
    say("3. CMEMS daily current to-direction vs Open-Meteo SMOC daily vector-mean 'towards' (speed >= 0.05 m/s): "
        + (stats(cdiff(jc.dir_to, jc.om_to)) if len(jc) else "no data"))

say("\n4. Arrow maths (canvas: x right, y down; dx = sin(to) * L, dy = -cos(to) * L)")
for label, to in [("wave from N (VMDR=0)", (0 + 180) % 360), ("current u=+1, v=0", (np.degrees(np.arctan2(1, 0)) + 360) % 360),
                  ("wind from W (270)", (270 + 180) % 360)]:
    dx, dy = np.sin(np.radians(to)), -np.cos(np.radians(to))
    say(f"   {label}: to={to:.0f} deg -> dx={dx:+.2f}, dy={dy:+.2f} ({vv.compass(to)})")
(ROOT / "docs" / "viz" / "direction_check.txt").write_text("\n".join(out) + "\n")
