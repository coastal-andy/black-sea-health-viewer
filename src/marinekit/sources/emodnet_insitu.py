"""EMODnet in-situ observations for the Romanian Black Sea shelf (EMODnet Physics + EMODnet Chemistry).

All endpoints are public ERDDAP servers, no login, no API key (verified 2026-11-23):

* PHYS      https://erddap.emodnet-physics.eu/erddap        platform catalogue (EP_PLATFORMS_METADATA_V2),
                                                             SeaDataNet Black Sea T/S climatology (SDC_BLS_CLIM_TS_V2_m)
* PLATFORM  https://platform-erddap.emodnet-physics.eu/erddap one tabledap dataset per platform, e.g.
                                                             TS_70_EUXRo02_MO_UND (moorings/buoys, tide gauges, gliders, Argo)
* CHEM      https://erddap.emodnet-chemistry.eu/erddap       EMODnet Chemistry eutrophication bottle/CTD samples
                                                             (EUT_BLACKSEA_PROFILES, EUT_BLACKSEA_TIMESERIES)
* CENTRAL   https://erddap.emodnet.eu/erddap                 EMODnet Chemistry DIVAnd gridded climatologies (griddap)

Public functions
----------------
list_platforms(bbox=BBOX_RO, parameters=None, ...)          -> DataFrame of platforms with dataset_id
fetch_platform(platform_or_dataset, start, end, variables)  -> time series DataFrame (canonical columns)
fetch_chemistry_samples(lat, lon, radius_km, start, end)    -> discrete water samples (nutrients, O2, chl, T, S)
chemistry_climatology_at(lat, lon, variable, product)       -> DIVAnd seasonal climatology at a point (reference)
ts_climatology_at(lat, lon, depth, period)                  -> SeaDataNet monthly T/S climatology at a point

QC conventions
--------------
* Platform data (Copernicus INSTAC / OceanSITES flags, <VAR>_QC): kept 1 = good, 2 = probably good.
  Dropped 0 no QC, 3 probably bad, 4 bad, 5 changed, 6/7 not used, 8 interpolated, 9 missing, -127/-32767 fill.
  On top of that, values outside broad physical bounds (``_BOUNDS``) and the netCDF fill 9.97e36 are dropped,
  because some NRT feeds carry garbage with QC=1 (seen live on EUXRoCB01/CB02 in 2026).
* Chemistry samples (SeaDataNet L20 flags in QV_SEADATANET_<var>): kept "1" good and "2" probably good.
  Others: 0 no QC, 3 probably bad, 4 bad, 5 changed, 6 below detection, 7 in excess, 8 interpolated, 9 missing,
  A value phenomenon uncertain, B nominal, Q below limit of quantification.

Every network call is cached under data/cache/emodnet_insitu (raw ERDDAP CSV). Catalogue/live responses get a
time-to-live; on network failure the stale cache is used so the dashboard keeps working offline.
"""

from __future__ import annotations

import io
import math
import time as _time
import urllib.parse
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from . import BBOX_RO, BBOX_WBS, STATIONS, cache_key, cached_path, meta

SOURCE = "emodnet_insitu"
PHYS = "https://erddap.emodnet-physics.eu/erddap"
PLATFORM = "https://platform-erddap.emodnet-physics.eu/erddap"
CHEM = "https://erddap.emodnet-chemistry.eu/erddap"
CENTRAL = "https://erddap.emodnet.eu/erddap"

_UA = {"User-Agent": "marinekit/0.1 (hackathon research client)"}
_FILL = 1e30  # anything with |value| above this is a netCDF fill (9.969e36) leaking through ERDDAP

# OceanSITES / Copernicus INSTAC parameter code -> (canonical name, unit after conversion)
PARAM_MAP: dict[str, tuple[str, str]] = {
    "TEMP": ("temp", "°C"),
    "PSAL": ("sal", "PSU"),
    "CNDC": ("cond", "S/m"),
    "DOXY": ("o2", "mmol/m³"),          # also emitted as 'do' in mg/L
    "DOX2": ("o2", "mmol/m³"),
    "OSAT": ("do_sat", "%"),
    "FLU2": ("chl", "mg/m³"),           # chlorophyll-a from fluorescence (uncalibrated proxy)
    "CPHL": ("chl", "mg/m³"),
    "CHLT": ("chl", "mg/m³"),
    "TUR4": ("turb", "NTU"),
    "TURB": ("turb", "NTU"),
    "CDOM": ("cdom", "ppb"),
    "PHPH": ("ph", ""),
    "SLEV": ("ssh", "m"),
    "VHM0": ("wave_height", "m"),
    "VAVH": ("wave_height_avg", "m"),
    "VTPK": ("wave_period_peak", "s"),
    "VTM02": ("wave_period_mean", "s"),
    "VMDR": ("wave_dir", "°"),
    "WSPD": ("wind_speed", "m/s"),
    "WDIR": ("wind_dir", "°"),
    "GSPD": ("wind_gust", "m/s"),
    "DRYT": ("air_temp", "°C"),
    "ATMS": ("pressure_atm", "hPa"),
    "RELH": ("rel_humidity", "%"),
    "HCSP": ("current_speed", "m/s"),
    "HCDT": ("current_dir", "°"),
    "EWCT": ("current_u", "m/s"),
    "NSCT": ("current_v", "m/s"),
}
WATER_PARAMS = ("TEMP", "PSAL", "DOXY", "DOX2", "OSAT", "FLU2", "CPHL", "CHLT", "TUR4", "TURB", "CDOM", "PHPH")

# broad physical sanity bounds (inclusive low, inclusive high) applied after QC
_BOUNDS = {
    "temp": (-2.0, 35.0), "sal": (0.0, 40.0), "cond": (0.0, 7.0), "o2": (1.0, 700.0), "do": (0.03, 22.0),
    "do_sat": (1.0, 250.0), "chl": (0.0, 200.0), "turb": (0.0, 1000.0), "cdom": (0.0, 1000.0),
    "ph": (6.0, 9.5), "ssh": (-20.0, 20.0), "wave_height": (0.0, 20.0), "wave_period_peak": (0.0, 30.0),
    "wave_period_mean": (0.0, 30.0), "wind_speed": (0.0, 70.0), "wind_gust": (0.0, 90.0),
    "air_temp": (-40.0, 50.0), "pressure_atm": (850.0, 1100.0), "rel_humidity": (0.0, 100.0),
    "current_speed": (0.0, 5.0), "wave_dir": (0.0, 360.0), "wind_dir": (0.0, 360.0), "current_dir": (0.0, 360.0),
}
_GOOD_QC = (1, 2)
_SDN_GOOD = ("1", "2")
O2_MOLAR_MASS = 31.998  # g/mol: mg/L = mmol/m³ * 31.998 / 1000

# --------------------------------------------------------------------------------------------- HTTP + cache


def _ttl_for_end(end: pd.Timestamp | None) -> float | None:
    """Data ending within the last 3 days may still grow: refresh after 3 h. Older data: cache forever."""
    if end is None or end > pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=3):
        return 3 * 3600
    return None


def _get_text(url: str, ttl: float | None = None, timeout: float = 180, retries: int = 2) -> str | None:
    """GET url through the disk cache. Returns text, or None for an ERDDAP 'no matching results' (cached too).

    ttl=None: cache forever. On network error a stale cache entry is returned if there is one.
    """
    path = cached_path(SOURCE, cache_key("GET", url), "csv")
    empty = path.with_suffix(".empty")
    for p in (path, empty):
        if p.exists() and (ttl is None or _time.time() - p.stat().st_mtime < ttl):
            return p.read_text() if p is path else None
    err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout, headers=_UA)
            if r.status_code == 404 and "no matching results" in r.text.lower():
                empty.write_text(r.text[:500])
                path.unlink(missing_ok=True)
                return None
            r.raise_for_status()
            path.write_text(r.text)
            empty.unlink(missing_ok=True)
            return r.text
        except requests.RequestException as e:  # network trouble or 5xx: retry, then fall back to stale cache
            err = e
            if getattr(e, "response", None) is not None and e.response.status_code in (400, 403, 404):
                break
            _time.sleep(2 * (attempt + 1))
    if path.exists():
        return path.read_text()
    if empty.exists():
        return None
    raise RuntimeError(f"EMODnet request failed and nothing cached: {url}\n{err}")


def _tabledap_url(base: str, dataset: str, variables: list[str], constraints: list[str], fmt: str = "csv") -> str:
    q = ",".join(variables) + "".join("&" + urllib.parse.quote(c, safe="=!~") for c in constraints)
    return f"{base}/tabledap/{dataset}.{fmt}?{q}"


def _read_erddap_csv(text: str | None) -> pd.DataFrame:
    if not text:
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(text), skiprows=[1], low_memory=False)


def _tabledap(base, dataset, variables, constraints, ttl=None, timeout=180) -> pd.DataFrame:
    return _read_erddap_csv(_get_text(_tabledap_url(base, dataset, variables, constraints), ttl=ttl, timeout=timeout))


def _dataset_info(base: str, dataset: str, ttl: float | None = 24 * 3600) -> dict:
    """ERDDAP info/<id>/index.csv -> {'globals': {...}, 'vars': {name: {attr: value}}}."""
    text = _get_text(f"{base}/info/{dataset}/index.csv", ttl=ttl)
    if text is None:
        raise KeyError(f"{dataset} not found on {base}")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    out: dict = {"globals": {}, "vars": {}}
    for row in df.itertuples(index=False):
        kind, var, attr, _dtype, value = row[:5]
        if kind == "variable":
            out["vars"].setdefault(var, {})
        elif kind == "attribute" and var == "NC_GLOBAL":
            out["globals"][attr] = value
        elif kind == "attribute":
            out["vars"].setdefault(var, {})[attr] = value
    return out


def _ts(x) -> pd.Timestamp | None:
    if x is None:
        return None
    t = pd.Timestamp(x)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


def _to_naive_utc(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, errors="coerce").dt.tz_localize(None)


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------------------------- platforms


def _platform_datasets(bbox) -> pd.DataFrame:
    """Per-platform tabledap datasets on platform-erddap whose bbox intersects `bbox`."""
    lon0, lat0, lon1, lat1 = bbox
    df = _tabledap(
        PLATFORM, "allDatasets",
        ["datasetID", "title", "minLongitude", "maxLongitude", "minLatitude", "maxLatitude", "minTime", "maxTime"],
        [f"minLongitude<={lon1}", f"maxLongitude>={lon0}", f"minLatitude<={lat1}", f"maxLatitude>={lat0}"],
        ttl=24 * 3600, timeout=300,
    )
    if df.empty:
        return df
    df = df[df.datasetID.str.match(r"^(TS|PR)_\d+_.+_[A-Z0-9]+_UND$")].copy()
    parts = df.datasetID.str.split("_")
    df["PLATFORMCODE"] = parts.map(lambda p: "_".join(p[2:-2]))
    df["integrator_num"] = parts.map(lambda p: p[1])
    return df


def _canon_params(codes: str) -> list[str]:
    out = []
    for c in str(codes).split(","):
        c = c.strip()
        if c in PARAM_MAP and PARAM_MAP[c][0] not in out:
            out.append(PARAM_MAP[c][0])
    return out


def list_platforms(
    bbox: tuple = BBOX_RO,
    parameters: list[str] | None = None,
    types: list[str] | None = None,
    include_bottle: bool = False,
    min_days: float = 1.0,
    with_dataset: bool = True,
) -> pd.DataFrame:
    """EMODnet Physics platforms inside bbox (lon_min, lat_min, lon_max, lat_max).

    parameters : keep platforms measuring any of these (canonical names like 'chl', 'o2', 'temp', or raw
                 OceanSITES codes like 'FLU2', 'DOXY'). None = all.
    types      : keep only these platform types (e.g. ['Mooring', 'Tide Gauge', 'Gliders']). None = all.
    include_bottle : include the ~470 'Bottle Data' cruise-station entries (single casts; no time series).
    min_days   : drop platforms whose observation span is shorter (removes one-off ADCP / CTD casts).
    with_dataset : join the platform-erddap dataset_id usable by fetch_platform (one extra cached request).

    Columns: id, name, type, lat, lon, parameters (raw codes), canonical, time_start, time_end, n_months,
    owner, integrator, dataset_id, dataset_time_end, url (platform page), sorted by time_end descending.
    time_start/time_end come from the daily-updated EMODnet catalogue (EP_PLATFORMS_METADATA_V2).
    """
    lon0, lat0, lon1, lat1 = bbox
    cols = ["PLATFORMCODE", "call_name", "latitude", "longitude", "firstdateobservation", "lastdateobservation",
            "availabledates", "parameters", "dataownername", "integrator_id", "platformtypedescription",
            "platformtypecode", "platformpagelink"]
    df = _tabledap(PHYS, "EP_PLATFORMS_METADATA_V2", cols,
                   [f"latitude>={lat0}", f"latitude<={lat1}", f"longitude>={lon0}", f"longitude<={lon1}"],
                   ttl=24 * 3600, timeout=300)
    if df.empty:
        return df
    out = pd.DataFrame({
        "id": df.PLATFORMCODE.astype(str),
        "name": df.call_name,
        "type": df.platformtypedescription,
        "type_code": df.platformtypecode,
        "lat": df.latitude,
        "lon": df.longitude,
        "parameters": df.parameters.fillna(""),
        "canonical": df.parameters.fillna("").map(_canon_params),
        "time_start": _to_naive_utc(df.firstdateobservation),
        "time_end": _to_naive_utc(df.lastdateobservation),
        "n_months": df.availabledates.fillna("").map(lambda s: s.count("-")),
        "owner": df.dataownername,
        "integrator": df.integrator_id,
        "url": df.platformpagelink,
    })
    if not include_bottle:
        out = out[out.type != "Bottle Data"]
    if types:
        out = out[out.type.isin(types)]
    if min_days:
        span = (out.time_end - out.time_start).dt.total_seconds() / 86400
        out = out[span.isna() | (span >= min_days)]
    if parameters:
        want = set(parameters)
        out = out[out.apply(lambda r: bool(want & (set(r.canonical) | {c.strip() for c in r.parameters.split(",")})),
                            axis=1)]
    if with_dataset and not out.empty:
        ds = _platform_datasets(bbox)
        if not ds.empty:
            # one dataset per platform code; prefer Copernicus INSTAC ('70'), then IOC ('01'), then anything
            ds["_pref"] = ds.integrator_num.map({"70": 0, "01": 1}).fillna(2)
            ds = ds.sort_values("_pref").drop_duplicates("PLATFORMCODE")
            ds = ds.rename(columns={"PLATFORMCODE": "id", "datasetID": "dataset_id", "maxTime": "dataset_time_end"})
            out = out.merge(ds[["id", "dataset_id", "dataset_time_end"]], on="id", how="left")
            out["dataset_time_end"] = _to_naive_utc(out.dataset_time_end)
    return out.sort_values("time_end", ascending=False, na_position="last").reset_index(drop=True)


def _resolve_dataset(platform_or_dataset: str) -> str:
    s = str(platform_or_dataset)
    if (s.startswith("TS_") or s.startswith("PR_")) and s.endswith("_UND"):
        return s
    cat = list_platforms(BBOX_WBS, min_days=0, include_bottle=False)
    hit = cat[(cat.id == s) & cat.dataset_id.notna()] if "dataset_id" in cat else cat.iloc[0:0]
    if len(hit):
        return hit.dataset_id.iloc[0]
    for guess in (f"TS_70_{s}_MO_UND", f"TS_70_{s}_TG_UND", f"TS_01_{s}_TG_UND", f"PR_70_{s}_GL_UND"):
        try:
            _dataset_info(PLATFORM, guess)
            return guess
        except (KeyError, RuntimeError):
            continue
    raise KeyError(f"No EMODnet Physics dataset found for platform {s!r}; see list_platforms(BBOX_WBS)")


def _resolve_vars(available: list[str], variables) -> list[str]:
    if variables is None:
        return [c for c in available if c in WATER_PARAMS or c == "SLEV" or c == "VHM0"]
    want = [variables] if isinstance(variables, str) else list(variables)
    out = []
    for w in want:
        if w == "do":
            w = "o2"
        for code in available:
            if code == w or PARAM_MAP.get(code, (None,))[0] == w:
                if code not in out:
                    out.append(code)
    return out


def _year_chunks(t0: pd.Timestamp, t1: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    chunks, a = [], t0
    while a < t1:
        b = min(pd.Timestamp(year=a.year + 1, month=1, day=1), t1)
        chunks.append((a, b))
        a = b
    return chunks


def fetch_platform(
    platform_or_dataset: str,
    start=None,
    end=None,
    variables: list[str] | str | None = None,
    depth: str | float = "surface",
    qc: tuple[int, ...] = _GOOD_QC,
    resample: str | None = None,
) -> pd.DataFrame:
    """Time series from one EMODnet Physics platform.

    platform_or_dataset : platform code ('EUXRo02', 'EUXRoCB02', 'IOC-csta2', '15480', ...) or a platform-erddap
                          dataset id ('TS_70_EUXRo02_MO_UND').
    start, end          : anything pandas.Timestamp accepts (UTC). Default: last 30 days of the dataset.
    variables           : canonical names ('temp', 'sal', 'o2', 'do', 'do_sat', 'chl', 'turb', 'ssh',
                          'wave_height', 'wind_speed', ...) or raw codes. None = water-column parameters
                          (+ sea level / wave height when that is all the platform has).
    depth               : 'surface' -> per variable and timestamp, the shallowest level holding a good value
                          (buoy sensors sit at ~0-3 m); 'all' -> long table with 'level' and 'depth' columns.
    qc                  : OceanSITES QC flags to keep (default 1 good, 2 probably good).
    resample            : optional pandas offset ('1h', '1D') -> mean per bin.

    Returns DataFrame, DatetimeIndex 'time' (UTC, tz-naive), canonical columns. DOXY gives both 'o2' (mmol/m³)
    and 'do' (mg/L). df.attrs = meta(..., origin='in-situ', lat, lon, platform, qc_kept, depth_m, notes).
    """
    ds = _resolve_dataset(platform_or_dataset)
    info = _dataset_info(PLATFORM, ds)
    g, vinfo = info["globals"], info["vars"]
    codes = _resolve_vars([v for v in vinfo if v in PARAM_MAP], variables)
    if not codes:
        raise ValueError(f"{ds}: none of {variables} available; has {[v for v in vinfo if v in PARAM_MAP]}")
    cov0 = _ts(g.get("time_coverage_start")) or pd.Timestamp("1990-01-01")
    cov1 = _ts(g.get("time_coverage_end")) or pd.Timestamp.now("UTC").tz_localize(None)
    t1 = _ts(end) or pd.Timestamp.now("UTC").tz_localize(None).ceil("h")
    t0 = _ts(start) or (min(t1, cov1) - pd.Timedelta(days=30))
    if t0 >= t1:
        raise ValueError("start must be before end")
    # ERDDAP rejects a start beyond the *advertised* time_coverage_end, which lags real data by days/weeks
    # (EUXRoCB02 advertised 2026-11-07 while serving data to 2026-11-22). Clamp, filter client-side later.
    q0 = min(t0, cov1 - pd.Timedelta(hours=1))
    if t1 < cov0:
        frames = []
    else:
        frames = []
        cols = ["time", "depth", "latitude", "longitude"] + [x for c in codes for x in (c, f"{c}_QC")]
        for a, b in _year_chunks(max(q0, cov0 - pd.Timedelta(days=1)), t1):
            cons = [f"time>={a.isoformat()}Z", f"time<{b.isoformat()}Z"]
            frames.append(_tabledap(PLATFORM, ds, cols, cons, ttl=_ttl_for_end(b), timeout=300))
    raw = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(
        not f.empty for f in frames) else pd.DataFrame()

    lat = float(g.get("geospatial_lat_min", "nan") or "nan")
    lon = float(g.get("geospatial_lon_min", "nan") or "nan")
    platform = g.get("platformCode", str(platform_or_dataset))
    units = {}
    notes = []
    if raw.empty:
        df = pd.DataFrame(index=pd.DatetimeIndex([], name="time"))
        df.attrs = meta("EMODnet Physics", ds, "in-situ", units, lat=lat, lon=lon, platform=platform,
                        qc_kept=list(qc), notes=["no data in requested window"])
        return df

    raw["time"] = _to_naive_utc(raw["time"])
    raw = raw[(raw.time >= t0) & (raw.time <= t1)].copy()
    # rows arrive grouped per timestamp in DEPTH-index order; 'depth' is often only filled on the first row
    # of each monthly file, so recover the level index and map it to the depths that are reported.
    raw["level"] = raw.groupby("time", sort=False).cumcount()
    raw.loc[raw.depth.abs() > _FILL, "depth"] = np.nan
    level_depth = raw.dropna(subset=["depth"]).groupby("level").depth.median().to_dict()
    raw["depth"] = raw.level.map(level_depth)
    if raw.latitude.notna().any():
        pos = raw[(raw.latitude.abs() < 90) & (raw.longitude.abs() < 180)]
        if len(pos):
            lat, lon = float(pos.latitude.median()), float(pos.longitude.median())

    long_cols = {}
    for c in codes:
        name, unit = PARAM_MAP[c]
        v = pd.to_numeric(raw[c], errors="coerce")
        f = pd.to_numeric(raw[f"{c}_QC"], errors="coerce")
        v = v.where(f.isin(qc) & (v.abs() < _FILL))
        src_unit = vinfo.get(c, {}).get("units", "")
        if name == "o2":
            good = v.dropna()
            if len(good) and good.median() < 25:  # provider reported mg/L in a mmol/m³ field (EUXRoCB02)
                notes.append(f"{c}: median {good.median():.2f} << 100 so treated as mg/L despite units '{src_unit}'")
                long_cols["do"] = v
                v = v * 1000 / O2_MOLAR_MASS
            else:
                long_cols["do"] = v * O2_MOLAR_MASS / 1000
            units["do"] = "mg/L"
        if name == "ssh" and "mm" in src_unit:
            v = v / 1000.0
        long_cols[name] = v
        units[name] = unit
        if c == "FLU2":
            notes.append("chl is in-situ fluorescence (FLU2), not HPLC/extracted chlorophyll")
    long = pd.DataFrame(long_cols)
    for name in list(long):
        lo, hi = _BOUNDS.get(name, (-np.inf, np.inf))
        long[name] = long[name].where(long[name].between(lo, hi))
    long.insert(0, "time", raw.time.values)
    long.insert(1, "level", raw.level.values)
    long.insert(2, "depth", raw.depth.values)
    long = long.dropna(subset=[c for c in long.columns if c not in ("time", "level", "depth")], how="all")

    depth_used = {}
    if depth == "all":
        df = long.set_index("time").sort_index()
    else:
        # per variable: value at the shallowest level that has a good value at that timestamp
        long = long.sort_values(["time", "level"])
        parts = []
        for name in [c for c in long.columns if c not in ("time", "level", "depth")]:
            s = long[["time", "level", name]].dropna(subset=[name])
            if isinstance(depth, (int, float)) and level_depth:
                tgt = min(level_depth, key=lambda k: abs(level_depth[k] - depth))
                s = s[s.level == tgt]
            s = s.drop_duplicates("time", keep="first")
            lv = s.level.mode()
            depth_used[name] = (level_depth.get(int(lv.iloc[0]), "unknown (shallowest reported level)")
                                if len(lv) else None)
            parts.append(s.set_index("time")[name])
        df = pd.concat(parts, axis=1, sort=True) if parts else pd.DataFrame()
        df = df.sort_index()
    df.index = pd.DatetimeIndex(df.index, name="time")
    if resample:
        df = df.drop(columns=[c for c in ("level", "depth") if c in df], errors="ignore").resample(resample).mean()
        df = df.dropna(how="all")
    df.attrs = meta(
        "EMODnet Physics", ds, "in-situ", units, lat=lat, lon=lon, platform=platform,
        institution=g.get("institution"), integrator=g.get("integrator"), license=g.get("license"),
        citation=("Data are the property of the producer/owner, distributed through EMODnet Physics "
                  "(https://emodnet.ec.europa.eu/en/physics); " + str(g.get("institution", ""))),
        qc_kept=list(qc), qc_convention="OceanSITES/Copernicus INSTAC: 1 good, 2 probably good",
        depth_mode=depth, depth_m=depth_used, depth_levels=level_depth, raw_codes=codes,
        url=f"{PLATFORM}/tabledap/{ds}.html", notes=notes,
    )
    return df


# --------------------------------------------------------------------------------------------- chemistry samples

CHEM_VARS: dict[str, tuple[str, str]] = {
    # canonical -> (EMODnet Chemistry variable, unit as served)
    "temp": ("ITS_90_water_temperature", "°C"),
    "sal": ("Water_body_salinity", "PSU"),
    "o2": ("Water_body_dissolved_oxygen_concentration", "mmol/m³"),  # served as umol/l == mmol/m³
    "do_sat": ("Water_body_dissolved_oxygen_saturation", "%"),
    "chl": ("Water_body_chlorophyll_a", "mg/m³"),
    "no3": ("Water_body_nitrate", "mmol/m³"),
    "no2": ("Water_body_nitrite", "mmol/m³"),
    "nh4": ("Water_body_ammonium", "mmol/m³"),
    "din": ("Water_body_dissolved_inorganic_nitrogen_DIN", "mmol/m³"),
    "po4": ("Water_body_phosphate", "mmol/m³"),
    "si": ("Water_body_silicate", "mmol/m³"),
    "tn": ("Water_body_total_nitrogen", "mmol/m³"),
    "tp": ("Water_body_total_phosphorus", "mmol/m³"),
    "ph": ("Water_body_pH", ""),
}
CHEM_DEFAULT = ("temp", "sal", "o2", "chl", "no3", "po4", "si", "nh4")


def fetch_chemistry_samples(
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 30.0,
    bbox: tuple | None = None,
    start=None,
    end=None,
    variables: list[str] | None = None,
    max_depth: float | None = 10.0,
    dataset: str = "EUT_BLACKSEA_PROFILES",
    qc: tuple[str, ...] = _SDN_GOOD,
) -> pd.DataFrame:
    """Discrete water samples (bottle/CTD) from EMODnet Chemistry 'Eutrophication v2025 Black Sea'.

    Select either a circle (lat, lon, radius_km) or a bbox (lon_min, lat_min, lon_max, lat_max); default bbox
    is BBOX_RO. max_depth keeps the surface layer (None = whole profile). Values with SeaDataNet QC not in
    `qc` are set to NaN; rows with no remaining value are dropped.

    Returns a long table: DatetimeIndex 'time' (UTC naive) + columns station, cruise, lat, lon, depth,
    originator, dist_km (circle mode) and canonical variables (o2/no3/po4/si/nh4 in mmol/m³ == µmol/L,
    chl mg/m³; 'do' mg/L derived from o2). Coverage for the Romanian shelf: 1963-2021, densest 1970-2010,
    mostly NIMRD 'Grigore Antipa' (EDMO 697); chlorophyll is sparse (~130 surface samples).
    """
    want = list(variables or CHEM_DEFAULT)
    if "do" in want:
        want = [w for w in want if w != "do"] + (["o2"] if "o2" not in want else [])
    info = _dataset_info(CHEM, dataset, ttl=7 * 24 * 3600)
    have = set(info["vars"])
    pairs = [(c, CHEM_VARS[c][0]) for c in want if c in CHEM_VARS and CHEM_VARS[c][0] in have]
    if lat is not None and lon is not None:
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
        box = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    else:
        box = bbox or BBOX_RO
    cons = [f"longitude>={box[0]:.4f}", f"longitude<={box[2]:.4f}", f"latitude>={box[1]:.4f}",
            f"latitude<={box[3]:.4f}"]
    t0, t1 = _ts(start), _ts(end)
    if t0 is not None:
        cons.append(f"time>={t0.isoformat()}Z")
    if t1 is not None:
        cons.append(f"time<={t1.isoformat()}Z")
    if max_depth is not None:
        cons.append(f"depth<={max_depth}")
    cols = ["Cruise", "Station", "time", "longitude", "latitude", "depth", "Originator"]
    cols += [x for _, v in pairs for x in (v, f"QV_SEADATANET_{v}")]
    raw = _tabledap(CHEM, dataset, cols, cons, ttl=None, timeout=600)
    units = {c: CHEM_VARS[c][1] for c, _ in pairs}
    if raw.empty:
        df = pd.DataFrame(index=pd.DatetimeIndex([], name="time"))
        df.attrs = meta("EMODnet Chemistry", dataset, "in-situ", units, lat=lat, lon=lon, qc_kept=list(qc))
        return df
    out = pd.DataFrame({
        "time": _to_naive_utc(raw.time), "station": raw.Station.astype(str), "cruise": raw.Cruise.astype(str),
        "lat": raw.latitude, "lon": raw.longitude, "depth": raw.depth, "originator": raw.Originator,
    })
    for c, v in pairs:
        flag = raw[f"QV_SEADATANET_{v}"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        val = pd.to_numeric(raw[v], errors="coerce").where(flag.isin(qc))
        lo, hi = _BOUNDS.get(c, (-np.inf, np.inf)) if c in ("temp", "sal", "o2", "chl", "ph", "do_sat") else (0, 1e4)
        out[c] = val.where(val.between(lo, hi))
    if "o2" in out:
        out["do"] = out["o2"] * O2_MOLAR_MASS / 1000
        units["do"] = "mg/L"
    if lat is not None and lon is not None:
        out["dist_km"] = _haversine_km(lat, lon, out.lat.values, out.lon.values)
        out = out[out.dist_km <= radius_km]
    valcols = [c for c, _ in pairs] + (["do"] if "do" in out else [])
    out = out.dropna(subset=valcols, how="all").set_index("time").sort_index()
    out.attrs = meta(
        "EMODnet Chemistry", dataset, "in-situ", units, lat=lat, lon=lon, radius_km=radius_km, bbox=box,
        max_depth=max_depth, qc_kept=list(qc),
        qc_convention="SeaDataNet L20: 1 good, 2 probably good",
        citation=("EMODnet Chemistry, Eutrophication v2025 Black Sea aggregated dataset. This resource was "
                  "generated in the framework of EMODnet Chemistry, under the support of DG MARE Call for "
                  "Tender EASME/EMFF/2020/3.1.11 - Lot 5 - Chemistry"),
        url=f"{CHEM}/tabledap/{dataset}.html",
    )
    return out


# --------------------------------------------------------------------------------------------- gridded references

# EMODnet Chemistry DIVAnd v2025 products served as griddap on the central EMODnet ERDDAP.
#   'danube'  : Black Sea - Danube Delta coastal product (NIMRD), 0.01°, lon 28.5-30.5 lat 43.7-45.6,
#               4 seasons (winter DJF, spring MAM, summer JJA, autumn SON) of 2000-2022 (chl) / 1970|1980-2022,
#               depths 0-40 m. Time axis is nominal (2011/2001/1996 + season).
#   'blacksea': whole Black Sea, 0.05°, moving 6-year centred seasonal analyses, one value per season per
#               year 1992-2020 (chl, DIN, PO4, Si) / 1982-2021 (O2); depths 0-50 m.
DIVAND = {
    "danube": {
        "chl": "oceanbrowser_opendap_ebeb_bdb0_a194",
        "din": "oceanbrowser_opendap_13be_1148_6757",
        "o2": "oceanbrowser_opendap_147b_ee8c_9d8c",
        "po4": "oceanbrowser_opendap_78b6_98d7_8c7e",
        "si": "oceanbrowser_opendap_3433_052b_9d7b",
    },
    "blacksea": {
        "chl": "oceanbrowser_opendap_470c_8f10_72a6",
        "din": "oceanbrowser_opendap_af26_ec61_167f",
        "o2": "oceanbrowser_opendap_bcfe_6547_14a6",
        "po4": "oceanbrowser_opendap_8ba2_e24f_6849",
        "si": "oceanbrowser_opendap_63d5_3a17_0164",
    },
}
_DIVAND_TITLE = {  # used to re-discover ids if EMODnet regenerates them
    "danube": "Black Sea, Danube Delta, DIVAnd 4D seasonal analysis of Water body {v}",
    "blacksea": "Black Sea, DIVAnd 4D 6-year seasonal analysis of Water body {v}",
}
_DIVAND_TITLE_VAR = {"chl": "chlorophyll-a", "din": "dissolved inorganic nitrogen", "o2": "dissolved oxygen",
                     "po4": "phosphate", "si": "silicate"}
_SEASON = {1: "winter", 4: "spring", 7: "summer", 10: "autumn"}


def _find_divand_id(product: str, var: str) -> str:
    ds = DIVAND[product][var]
    try:
        _dataset_info(CENTRAL, ds, ttl=7 * 24 * 3600)
        return ds
    except (KeyError, RuntimeError):
        pass
    cat = _tabledap(CENTRAL, "allDatasets", ["datasetID", "title"], [], ttl=7 * 24 * 3600)
    pat = _DIVAND_TITLE[product].format(v=_DIVAND_TITLE_VAR[var])
    hits = cat[cat.title.str.startswith(pat) & cat.title.str.contains(r"v2025 \[time\]\[depth\]")]
    if hits.empty:
        raise KeyError(f"DIVAnd {product}/{var} not found on {CENTRAL}")
    return hits.datasetID.iloc[0]


def _griddap_point(base, ds, varnames: list[str], time_sel: str, depth: float, lat: float, lon: float):
    sel = f"{time_sel}[({depth})][({lat})][({lon})]"
    q = ",".join(v + sel for v in varnames)
    url = f"{base}/griddap/{ds}.csv?" + urllib.parse.quote(q, safe=",():")
    return _read_erddap_csv(_get_text(url, ttl=None))


def chemistry_climatology_at(
    lat: float,
    lon: float,
    variable: str = "chl",
    product: str = "danube",
    depth: float = 0.0,
    start=None,
    end=None,
) -> pd.DataFrame:
    """EMODnet Chemistry DIVAnd seasonal climatology at the nearest grid point: reference conditions.

    variable : 'chl' (mg/m³), 'din', 'po4', 'si', 'o2' (all mmol/m³ == µmol/L).
    product  : 'danube' (coastal Romanian shelf, 0.01°, one seasonal cycle 2000-2022) or
               'blacksea' (0.05°, moving 6-year seasonal analyses 1992-2020; start/end filter years).
    Returns DataFrame indexed by season-centre time with columns: season, <variable> (full analysis),
    <variable>_L1 (masked where relative error > 0.3: trust this one), relerr, and attrs with grid lat/lon.
    """
    if variable == "do":
        variable = "o2"
    ds = _find_divand_id(product, variable)
    info = _dataset_info(CENTRAL, ds, ttl=7 * 24 * 3600)
    base = next(v for v in info["vars"] if v.startswith("Water_body") and not v.endswith(("_L1", "_L2", "_relerr")))
    if product == "blacksea":
        t0 = _ts(start) or pd.Timestamp("1900-01-01")
        t1 = _ts(end) or pd.Timestamp("2100-01-01")
        tc0 = _ts(info["globals"].get("time_coverage_start")) or t0
        tc1 = _ts(info["globals"].get("time_coverage_end")) or t1
        a, b = max(t0, tc0), min(t1, tc1)
        time_sel = f"[({a.strftime('%Y-%m-%dT%H:%M:%SZ')}):1:({b.strftime('%Y-%m-%dT%H:%M:%SZ')})]"
    else:
        time_sel = "[]"
    raw = _griddap_point(CENTRAL, ds, [base, f"{base}_L1", f"{base}_relerr"], time_sel, depth, lat, lon)
    if raw.empty:
        return pd.DataFrame()
    t = _to_naive_utc(raw.time)
    df = pd.DataFrame({
        "season": t.dt.month.map(_SEASON).values,
        variable: pd.to_numeric(raw[base], errors="coerce").values,
        f"{variable}_L1": pd.to_numeric(raw[f"{base}_L1"], errors="coerce").values,
        "relerr": pd.to_numeric(raw[f"{base}_relerr"], errors="coerce").values,
    }, index=pd.DatetimeIndex(t, name="time"))
    g = info["globals"]
    unit = "mg/m³" if variable == "chl" else "mmol/m³"
    df.attrs = meta(
        "EMODnet Chemistry DIVAnd", ds, "derived", {variable: unit, f"{variable}_L1": unit},
        lat=float(raw.latitude.iloc[0]), lon=float(raw.longitude.iloc[0]), depth=float(raw.depth.iloc[0]),
        requested_lat=lat, requested_lon=lon, product=product, title=g.get("title"), doi=g.get("doi"),
        institution=g.get("institution"),
        season_definition="winter DJF, spring MAM, summer JJA, autumn SON (time = mid-season, nominal year)",
        citation=(f"{g.get('title')}. doi:{g.get('doi')}. "
                  + str(g.get("acknowledgement") or g.get("acknowledgment") or "")),
        url=f"{CENTRAL}/griddap/{ds}.html",
    )
    return df


TS_CLIM_PERIODS = {"1955-1994": 1974, "1955-2019": 1987, "1995-2019": 2007}


def ts_climatology_at(lat: float, lon: float, depth: float = 0.0, period: str = "1995-2019",
                      masked: bool = True) -> pd.DataFrame:
    """SeaDataNet Black Sea temperature/salinity monthly climatology (SDC_BLS_CLIM_TS_V2, 0.125°) at a point.

    period: '1995-2019' (default, most recent), '1955-2019' (full) or '1955-1994'. ERDDAP stores the three
    periods as nominal years 2007, 1987, 1974 (period mid-points). masked=True uses the *_L1 fields (relative
    error < 0.3). Returns 12 rows indexed by month (1..12) with columns temp (°C), sal (PSU).
    """
    yr = TS_CLIM_PERIODS[period]
    tsel = f"[({yr}-01-16T00:00:00Z):1:({yr}-12-16T00:00:00Z)]"
    sfx = "_L1" if masked else ""
    raw = _griddap_point(PHYS, "SDC_BLS_CLIM_TS_V2_m", [f"Temperature{sfx}", f"Salinity{sfx}"], tsel, depth, lat, lon)
    if raw.empty:
        return pd.DataFrame()
    df = pd.DataFrame({"temp": pd.to_numeric(raw[f"Temperature{sfx}"], errors="coerce").values,
                       "sal": pd.to_numeric(raw[f"Salinity{sfx}"], errors="coerce").values},
                      index=pd.Index(_to_naive_utc(raw.time).dt.month.values, name="month"))
    df.attrs = meta(
        "SeaDataNet (via EMODnet Physics ERDDAP)", "SDC_BLS_CLIM_TS_V2_m", "derived", {"temp": "°C", "sal": "PSU"},
        lat=float(raw.latitude.iloc[0]), lon=float(raw.longitude.iloc[0]), depth=float(raw.depth.iloc[0]),
        period=period, doi="10.12770/847f1627-f39f-40af-b3b0-a2f6d29ff4dc",
        citation="SeaDataNet SDC_BLS_CLIM_TS_V2 Black Sea T/S climatology, doi:10.12770/847f1627-f39f-40af-b3b0-a2f6d29ff4dc",
        url=f"{PHYS}/griddap/SDC_BLS_CLIM_TS_V2_m.html",
    )
    return df


# --------------------------------------------------------------------------------------------- smoke test

if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    lat, lon = STATIONS["Constanta"]

    print("== platforms on the Romanian shelf (water-quality parameters)")
    pl = list_platforms(BBOX_RO, parameters=["temp", "o2", "chl", "sal", "turb"])
    print(pl[["id", "name", "type", "lat", "lon", "time_start", "time_end", "n_months", "dataset_id"]]
          .head(25).to_string())

    print("\n== EUXRo02 offshore buoy (GeoEcoMar/NIMRD), July 2021, surface")
    d = fetch_platform("EUXRo02", "2021-07-01", "2021-07-08", ["temp", "sal", "chl", "o2", "turb"])
    print(d.head(), "\n", d.describe().T[["count", "mean", "min", "max"]], "\n", d.attrs["depth_m"])

    print("\n== EUXRoOB03 offshore buoy, 2025, daily means")
    d = fetch_platform("EUXRoOB03", "2025-06-01", "2025-09-01", ["temp", "sal", "chl", "o2", "turb"], resample="1D")
    print(d.head(), "\n", d.attrs["notes"])

    print("\n== Constanta tide gauge (IOC csta2), last 3 days")
    now = pd.Timestamp.now("UTC").tz_localize(None)
    d = fetch_platform("IOC-csta2", now - pd.Timedelta(days=3), now, ["ssh"])
    print(d.tail(), len(d))

    print("\n== EMODnet Chemistry samples within 30 km of Constanta, 2000-2010, 0-10 m")
    c = fetch_chemistry_samples(lat, lon, 30, start="2000-01-01", end="2010-12-31")
    print(len(c), "rows;", c.station.nunique(), "stations")
    print(c[["station", "depth", "temp", "sal", "o2", "do", "chl", "no3", "po4", "si"]].head(8))

    print("\n== DIVAnd chlorophyll climatology at Constanta (Danube Delta product, 2000-2022)")
    print(chemistry_climatology_at(lat, lon, "chl", "danube"))
    print("\n== DIVAnd 6-year moving O2 at Constanta (Black Sea product), 2015-2021")
    print(chemistry_climatology_at(lat, lon, "o2", "blacksea", start="2015-01-01").tail(8))
    print("\n== SeaDataNet monthly T/S climatology 1995-2019 at Constanta, surface")
    print(ts_climatology_at(lat, lon).T.round(2))
