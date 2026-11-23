"""External data sources (Copernicus Marine, EMODnet, satellite ERDDAPs, open APIs).

Shared conventions every source module follows, so the dashboard can mix and compare them:

* Time series  -> pandas DataFrame, DatetimeIndex (UTC, tz-naive), one column per variable using the
                  CANONICAL names below. df.attrs = meta(...) (source, dataset, origin, units, lat, lon, ...).
* Gridded maps -> xarray.Dataset / DataArray with dims (time, lat, lon) [+ depth], canonical variable names,
                  .attrs = meta(...).
* Vector layers-> GeoJSON dict (FeatureCollection, EPSG:4326) with properties kept as given by the service.
* Every network call goes through the on-disk cache (cached_path / cache_key) so a demo works offline
  once the data has been fetched once.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "cache"

# Romanian shelf, Danube mouths to the Bulgarian border (lon_min, lat_min, lon_max, lat_max)
BBOX_RO = (28.4, 43.6, 30.6, 45.4)
# Wider western Black Sea, for context maps
BBOX_WBS = (27.4, 41.0, 32.0, 46.6)

# Reference points along the Romanian coast (lat, lon): offshore enough to be sea pixels in ~1-5 km grids
STATIONS = {
    "Constanta": (44.17, 28.72),
    "Mamaia": (44.25, 28.70),
    "Midia port": (44.33, 28.72),
    "Mangalia / 2 Mai": (43.79, 28.64),
    "Sfantu Gheorghe (Danube)": (44.90, 29.70),
    "Sulina (Danube mouth)": (45.15, 29.78),
    "Offshore shelf": (44.40, 29.50),
}

# Canonical variable names (same as marinekit.io) -> human label, default unit
CANONICAL = {
    "temp": ("Water temperature", "°C"),
    "sst": ("Sea surface temperature", "°C"),
    "sal": ("Salinity", "PSU"),
    "do": ("Dissolved oxygen", "mg/L"),
    "o2": ("Dissolved oxygen", "mmol/m³"),
    "chl": ("Chlorophyll-a", "mg/m³"),
    "turb": ("Turbidity", "NTU"),
    "spm": ("Suspended particulate matter", "g/m³"),
    "kd490": ("Light attenuation Kd490", "1/m"),
    "no3": ("Nitrate", "mmol/m³"),
    "po4": ("Phosphate", "mmol/m³"),
    "ph": ("pH", ""),
    "wave_height": ("Significant wave height", "m"),
    "wind_speed": ("Wind speed", "m/s"),
    "current_u": ("Eastward current", "m/s"),
    "current_v": ("Northward current", "m/s"),
    "ssh": ("Sea surface height", "m"),
    "mld": ("Mixed layer depth", "m"),
    "depth": ("Depth", "m"),
}

ORIGINS = ("in-situ", "satellite", "model", "reanalysis", "derived")


def meta(source: str, dataset: str, origin: str, units: dict | None = None, **extra) -> dict:
    """Standard metadata dict for df.attrs / ds.attrs. origin is one of ORIGINS."""
    assert origin in ORIGINS, origin
    return {"source": source, "dataset": dataset, "origin": origin, "units": units or {}, **extra}


def cache_key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def cached_path(source: str, key: str, ext: str) -> Path:
    d = CACHE / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.{ext}"
