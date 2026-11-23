"""Navigation-log handling and geotagging for AUV/ROV imagery.

Typical flow:
    nav = load_nav("dive_nav.csv")                     # time, lat, lon, depth
    times = frame_times(video_start, n_frames, fps)    # or parse from image filenames / EXIF
    tagged = geotag(times, nav)                        # lat/lon/depth for every frame
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .io import load_table

EARTH_R = 6_371_000.0  # metres

# Default map centre: off Constanța
CONSTANTA = (44.17, 28.66)


def load_nav(path: str | Path) -> pd.DataFrame:
    """Load a vehicle navigation log. Returns columns time, lat, lon (+ depth/alt/heading if present)."""
    df = load_table(path, set_index=False)
    missing = {"time", "lat", "lon"} - set(df.columns)
    if missing:
        raise ValueError(f"Nav log is missing {missing}. Columns found: {list(df.columns)}")
    df = convert_ddm(df)
    return df.reset_index(drop=True)


def convert_ddm(df: pd.DataFrame) -> pd.DataFrame:
    """Convert NMEA-style ddmm.mmmm coordinates (e.g. 4410.2 for 44°10.2') to decimal degrees."""
    for c, lim in (("lat", 90), ("lon", 180)):
        if c in df and df[c].abs().max() > lim:
            v = df[c].astype(float)
            deg = np.trunc(v / 100)
            df[c] = deg + (v - deg * 100) / 60
    return df


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (vectorised)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def track_stats(nav: pd.DataFrame) -> dict:
    d = haversine(nav.lat.values[:-1], nav.lon.values[:-1], nav.lat.values[1:], nav.lon.values[1:])
    dur = (nav.time.iloc[-1] - nav.time.iloc[0]).total_seconds() if "time" in nav else np.nan
    out = {
        "points": len(nav),
        "length_m": float(np.nansum(d)),
        "duration_min": dur / 60,
        "mean_speed_mps": float(np.nansum(d) / dur) if dur else np.nan,
    }
    if "depth" in nav:
        out.update(depth_min=float(nav.depth.min()), depth_max=float(nav.depth.max()))
    return out


def frame_times(start: datetime | str, n_frames: int, fps: float, every_n: int = 1) -> pd.Series:
    """Timestamps for video frames given the recording start time."""
    start = pd.Timestamp(start)
    idx = np.arange(0, n_frames, every_n)
    return pd.Series(start + pd.to_timedelta(idx / fps, unit="s"), index=idx, name="time")


_TS_PATTERNS = [
    (re.compile(r"(\d{8})[_T-]?(\d{6})(\d{0,6})"), "%Y%m%d%H%M%S"),          # 20261123_101530123
    (re.compile(r"(\d{4}-\d{2}-\d{2})[_T ](\d{2}[-:]\d{2}[-:]\d{2})"), None),  # 2026-11-23_10-15-30
]


def time_from_filename(name: str) -> pd.Timestamp | None:
    """Best-effort timestamp extraction from an image filename."""
    stem = Path(name).stem
    m = _TS_PATTERNS[0][0].search(stem)
    if m:
        t = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        frac = m.group(3)
        if frac:
            t += timedelta(seconds=float("0." + frac))
        return pd.Timestamp(t)
    m = _TS_PATTERNS[1][0].search(stem)
    if m:
        return pd.Timestamp(m.group(1) + " " + m.group(2).replace("-", ":"))
    return None


def time_from_exif(path: str | Path) -> pd.Timestamp | None:
    try:
        from PIL import Image

        exif = Image.open(path).getexif()
        raw = exif.get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
        return pd.Timestamp(datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")) if raw else None
    except Exception:
        return None


def geotag(times, nav: pd.DataFrame, max_gap_s: float = 30.0) -> pd.DataFrame:
    """Interpolate nav position at each timestamp. Rows further than max_gap_s from any fix get NaN."""
    times = pd.to_datetime(pd.Series(times)).reset_index(drop=True)
    t_nav = nav.time.astype("int64").values / 1e9
    t_q = times.astype("int64").values / 1e9
    out = pd.DataFrame({"time": times})
    for c in ("lat", "lon", "depth", "alt", "heading"):
        if c in nav:
            out[c] = np.interp(t_q, t_nav, nav[c].astype(float).values, left=np.nan, right=np.nan)
    # mask timestamps that sit inside a big nav gap
    pos = np.searchsorted(t_nav, t_q).clip(1, len(t_nav) - 1)
    gap = np.minimum(np.abs(t_q - t_nav[pos - 1]), np.abs(t_nav[pos] - t_q))
    out.loc[gap > max_gap_s, ["lat", "lon"]] = np.nan
    return out


def to_geojson(df: pd.DataFrame, props: list[str] | None = None) -> dict:
    """Points DataFrame (lat/lon) -> GeoJSON FeatureCollection (for QGIS / web maps)."""
    props = props or [c for c in df.columns if c not in ("lat", "lon")]
    feats = []
    for _, r in df.dropna(subset=["lat", "lon"]).iterrows():
        p = {k: (r[k].isoformat() if isinstance(r[k], pd.Timestamp) else (None if pd.isna(r[k]) else r[k])) for k in props}
        p = {k: (v.item() if hasattr(v, "item") else v) for k, v in p.items()}
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r.lon), float(r.lat)]}, "properties": p})
    return {"type": "FeatureCollection", "features": feats}


def grid_density(df: pd.DataFrame, cell_m: float = 50.0, weight: str | None = None) -> pd.DataFrame:
    """Bin points into a metric grid (local equirectangular). Returns cell centres + counts/sums.

    Useful for 'litter items per 50 m cell' or 'habitat share per cell'.
    """
    d = df.dropna(subset=["lat", "lon"]).copy()
    if d.empty:
        return d
    lat0 = d.lat.mean()
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat0))
    d["gx"] = np.floor(d.lon * m_per_deg_lon / cell_m).astype(int)
    d["gy"] = np.floor(d.lat * m_per_deg_lat / cell_m).astype(int)
    agg = d.groupby(["gx", "gy"]).agg(n=("lat", "size"), **({"w": (weight, "sum")} if weight else {})).reset_index()
    agg["lon"] = (agg.gx + 0.5) * cell_m / m_per_deg_lon
    agg["lat"] = (agg.gy + 0.5) * cell_m / m_per_deg_lat
    agg["per_100m2"] = agg.n / (cell_m * cell_m) * 100
    return agg.drop(columns=["gx", "gy"])
