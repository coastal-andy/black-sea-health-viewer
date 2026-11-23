"""Synthetic but realistic-looking demo data so the dashboard runs before we get the real datasets.

Run:  python -m marinekit.demo_data      -> writes data/demo/*.csv
Everything here is FAKE: never show it in the pitch as real results.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "demo"

BUOY_POS = (44.17, 28.70)   # off Constanța
AUV_ORIGIN = (43.785, 28.597)  # shallow shelf off 2 Mai (southern coast, where seagrass is plausible)


def make_buoy(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-07-01", "2026-09-15 23:00", freq="1h")
    n = len(t)
    doy = t.dayofyear.values
    hour = t.hour.values
    seasonal = 23.5 + 2.5 * np.sin((doy - 180) / 75 * np.pi / 2)
    diurnal = 0.5 * np.sin((hour - 9) / 24 * 2 * np.pi)
    temp = seasonal + diurnal + rng.normal(0, 0.15, n)
    temp += 2.6 * np.exp(-0.5 * ((t - pd.Timestamp("2026-08-08")).total_seconds() / 86400 / 2.5) ** 2)  # warm episode

    sal = 17.6 + rng.normal(0, 0.08, n) - 0.6 * np.exp(-0.5 * ((t - pd.Timestamp("2026-07-20")).total_seconds() / 86400 / 3) ** 2)

    chl = 2.5 + 0.6 * np.sin(doy / 9) + rng.gamma(2, 0.3, n)
    bloom = np.exp(-0.5 * ((t - pd.Timestamp("2026-08-16")).total_seconds() / 86400 / 1.6) ** 2)
    chl += 22 * bloom

    do = 7.6 + 0.6 * np.sin((hour - 14) / 24 * 2 * np.pi) - 0.08 * (temp - 23) + rng.normal(0, 0.15, n)
    do -= 6.3 * np.exp(-0.5 * ((t - pd.Timestamp("2026-08-21 06:00")).total_seconds() / 86400 / 0.9) ** 2)  # hypoxia after bloom decay
    ph = 8.28 + 0.03 * np.sin((hour - 14) / 24 * 2 * np.pi) + 0.04 * (do - 7.5) / 2 + rng.normal(0, 0.01, n)

    turb = 4 + rng.gamma(2, 1.0, n)
    storm = np.exp(-0.5 * ((t - pd.Timestamp("2026-09-03 12:00")).total_seconds() / 3600 / 10) ** 2)
    turb += 75 * storm
    wave = 0.5 + rng.gamma(2, 0.15, n) + 2.8 * storm
    wind = 4 + rng.gamma(2, 1.2, n) + 14 * storm

    df = pd.DataFrame({"Timestamp (UTC)": t, "Water Temp [°C]": temp, "Salinity [PSU]": sal, "Dissolved Oxygen [mg/L]": do,
                       "Chlorophyll-a [ug/L]": chl, "Turbidity [NTU]": turb, "pH": ph, "Wave Height [m]": wave, "Wind Speed [m/s]": wind})
    # realistic dirt: spikes, a sensor gap, a stuck/out-of-range value
    for col in ["Water Temp [°C]", "Dissolved Oxygen [mg/L]", "Chlorophyll-a [ug/L]"]:
        idx = rng.choice(n, 6, replace=False)
        df.loc[idx, col] = df.loc[idx, col] * rng.choice([3, -1, 0.1], 6)
    gap = (df["Timestamp (UTC)"] >= "2026-07-27") & (df["Timestamp (UTC)"] < "2026-07-29")
    df.loc[gap, df.columns[1:]] = np.nan
    df.loc[500, "Salinity [PSU]"] = 999.0
    df.insert(1, "lat", BUOY_POS[0])
    df.insert(2, "lon", BUOY_POS[1])
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(4)
    return df


def make_auv_nav(seed: int = 3) -> pd.DataFrame:
    """Lawnmower survey ~400 m x 200 m, 1 Hz, ~40 min."""
    rng = np.random.default_rng(seed)
    lat0, lon0 = AUV_ORIGIN
    m_lat, m_lon = 111_320.0, 111_320.0 * np.cos(np.radians(lat0))
    xs, ys = [], []
    speed, leg, spacing = 1.2, 400, 25
    for k in range(9):
        x = np.arange(0, leg, speed)
        xs.append(x if k % 2 == 0 else x[::-1])
        ys.append(np.full_like(x, k * spacing, dtype=float))
        if k < 8:
            yy = np.arange(0, spacing, speed) + k * spacing
            xs.append(np.full_like(yy, leg if k % 2 == 0 else 0, dtype=float))
            ys.append(yy)
    x = np.concatenate(xs) + rng.normal(0, 0.4, sum(map(len, xs)))
    y = np.concatenate(ys) + rng.normal(0, 0.4, len(x))
    t = pd.date_range("2026-09-10 09:00:00", periods=len(x), freq="1s")
    depth = 6 + 0.0175 * x + rng.normal(0, 0.1, len(x))   # 6 m inshore -> 13 m offshore
    return pd.DataFrame({"time": t, "lat": lat0 + y / m_lat, "lon": lon0 + x / m_lon, "depth": depth.round(2),
                         "altitude": (2 + rng.normal(0, 0.15, len(x))).round(2), "heading": np.where(np.gradient(x) >= 0, 90, 270)})


def make_detections(nav: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """Fake litter detections clustered in two hotspots along the AUV track."""
    rng = np.random.default_rng(seed)
    w = np.exp(-((nav.lon - nav.lon.quantile(0.7)) ** 2 + (nav.lat - nav.lat.quantile(0.3)) ** 2) / 2e-7) \
        + 0.6 * np.exp(-((nav.lon - nav.lon.quantile(0.2)) ** 2 + (nav.lat - nav.lat.quantile(0.8)) ** 2) / 1e-7) + 0.02
    idx = rng.choice(len(nav), 140, replace=False, p=(w / w.sum()).values)
    labels = rng.choice(["plastic bottle", "plastic bag", "fishing net", "rope", "metal can", "tire"], 140, p=[.3, .25, .15, .15, .1, .05])
    d = nav.iloc[idx][["time", "lat", "lon", "depth"]].copy()
    d["label"] = labels
    d["conf"] = rng.uniform(0.3, 0.95, len(d)).round(2)
    return d.sort_values("time").reset_index(drop=True)


def make_habitat_track(nav: pd.DataFrame, seed: int = 5) -> pd.DataFrame:
    """Fake habitat labels along the track: rocky reef + brown algae inshore, a seagrass meadow, a Phyllophora
    patch, a mussel bed, sand and mud offshore. ~8 % labels flipped to mimic classifier error."""
    rng = np.random.default_rng(seed)
    d = nav.iloc[::5][["time", "lat", "lon", "depth"]].copy()
    x = ((d.lon - d.lon.min()) / (d.lon.max() - d.lon.min())).values   # 0 = inshore (west)
    y = ((d.lat - d.lat.min()) / (d.lat.max() - d.lat.min())).values
    r2 = lambda cx, cy: (x - cx) ** 2 + (y - cy) ** 2
    hab = np.where(x < 0.6, "sand", "mud").astype(object)
    hab[x < 0.15] = "rock"
    hab[(x < 0.15) & (y > 0.45)] = "brown_algae"
    hab[r2(0.36, 0.45) < 0.035] = "seagrass"
    hab[r2(0.62, 0.18) < 0.012] = "phyllophora"
    ring = r2(0.8, 0.65)
    hab[(ring > 0.025) & (ring < 0.045)] = "shell_debris"
    hab[ring <= 0.025] = "mussel_bed"
    labels = np.array(["sand", "mud", "rock", "seagrass", "algae", "shell_debris", "mussel_bed", "water_column"])
    flip = rng.random(len(hab)) < 0.08
    hab[flip] = rng.choice(labels, flip.sum())
    d["pred"] = hab
    d["conf"] = np.where(flip, rng.uniform(0.25, 0.5, len(hab)), rng.uniform(0.55, 0.95, len(hab))).round(2)
    return d.reset_index(drop=True)


def write_all(out: Path = OUT) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    nav = make_auv_nav()
    files = {
        "buoy": out / "buoy_constanta_demo.csv",
        "nav": out / "auv_nav_demo.csv",
        "detections": out / "litter_detections_demo.csv",
        "habitat": out / "habitat_track_demo.csv",
    }
    make_buoy().to_csv(files["buoy"], index=False)
    nav.to_csv(files["nav"], index=False)
    make_detections(nav).to_csv(files["detections"], index=False)
    make_habitat_track(nav).to_csv(files["habitat"], index=False)
    return files


if __name__ == "__main__":
    for k, p in write_all().items():
        print(f"{k:11s} -> {p}")
