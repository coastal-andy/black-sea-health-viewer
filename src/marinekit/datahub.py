"""One entry point for time series and reference climatologies, with the source chosen from the data-quality register.

    from marinekit import datahub as dh
    df = dh.get_series("sst", 44.17, 28.72, "2026-08-01", "2026-11-23")        # source="auto"
    cl = dh.get_climatology("sst", 44.17, 28.72)                                 # day-of-year reference
    cmp = dh.compare_sources("sst", 44.17, 28.72, "2026-10-01", "2026-11-23")   # one column per source
    st = dh.obs_vs_model("o2", 44.17, 28.72, "2026-06-01", "2026-09-01")         # bias, rmse, r, n

Source choice for source="auto" follows docs/indicators/SHORTLIST.md section 4 (data-quality register):
  * SST and chlorophyll: satellite (SST REP + NRT with the NRT offset removed; chl L4 multi-year + NRT).
  * Measured surface O2 / salinity: an offshore buoy (EUXRoOB01-03, EUXRo03) when one is within BUOY_AUTO_KM,
    otherwise the Copernicus BGC / physics model.
  * Physics (bottom temperature, salinity, MLD) and bottom O2, pH: model (reanalysis for old dates, analysis/forecast
    after the reanalysis ends).
  * Nitrate / phosphate: never the model as absolute values. "auto" gives bottle samples (EMODnet Chemistry) and the
    DIVAnd climatology; the model is only available on explicit request and is labelled "not usable as absolute".
  * The coastal buoys EUXRoCB01-03 and NIMH station 15480 are flagged untrusted and are never picked by "auto".
  * Per-variable sensor flags (VARIABLE_TRUST): buoy chlorophyll (fluorescence) at EUXRoOB01-03 and EUXRo03 is
    "indicative", buoy salinity at EUXRoOB01-03 is "untrusted". "auto" skips them (chl -> satellite, then model;
    sal -> model); source="buoy" and compare_sources still return them, with that trust and the reason in notes.

Every returned DataFrame has one column named after the variable, a daily DatetimeIndex and attrs with:
variable, unit, source_id, label, origin (satellite|model|reanalysis|in-situ|derived), evidence
(measured|satellite|model), trust (good|usable|indicative|untrusted|not_usable_absolute), datasets,
distance_km, notes.

Caching: every network call goes through the source modules' disk cache (data/cache/...). On top of that this module
keeps derived climatologies on disk (data/cache/datahub/) and the last results in memory (6-hour buckets).
Offline: set MARINEKIT_OFFLINE=1 to read any cached file regardless of age; without it, a failed refresh of recent
data falls back to the stale cached file automatically.
"""
from __future__ import annotations

import functools
import json
import math
import os
import time
import warnings
from typing import Callable

import numpy as np
import pandas as pd

from .sources import STATIONS, cache_key, cached_path  # noqa: F401  (STATIONS re-exported for callers)

warnings.filterwarnings("ignore", category=RuntimeWarning)

O2_MG = 0.032                       # mmol/m3 -> mg/L
OFFLINE = os.environ.get("MARINEKIT_OFFLINE", "") == "1"
RECENT_MAX_AGE_H = float(os.environ.get("MARINEKIT_MAX_AGE_H", "24"))   # how long recent model/satellite files count as fresh
BUOY_AUTO_KM = 30.0                 # a trusted buoy closer than this is the "auto" source for measured O2 / salinity
NEAR_KM = 30.0                      # untrusted platforms are only listed in compare_sources when closer than this

# Known offsets (docs/indicators/physical.md, chemical.md; SHORTLIST section 4)
SST_NRT_MINUS_REP = 0.53            # deg C, sst_l4_nrt - sst_l4_rep over their overlap at Constanta
BOTTOMT_ANFC_MINUS_REA = 0.41       # deg C, phy_temp bottomT (anfc) - rea_phy_temp
O2B_ANFC_MINUS_REA = -2.0           # mg/L, bgc_o2 o2_bottom (anfc) - rea_bgc_o2, 2024 overlap (not applied, flagged)

# Model system coverage (docs/data_sources/copernicus.md note 9)
PHY_REA_END = pd.Timestamp("2025-07-31")
BGC_REA_END = pd.Timestamp("2024-12-31")
PHY_ANFC_START = pd.Timestamp("2024-12-01")
PHYX_ANFC_START = pd.Timestamp("2024-11-19")   # ssh, mld
BGC_ANFC_START = pd.Timestamp("2024-10-03")

# In-situ platforms (positions from copernicus.INSITU_RO and the chemical check)
PLATFORMS = {
    "EUXRoOB01": dict(lat=44.71, lon=30.76, trust="good", kind="offshore buoy"),
    "EUXRoOB02": dict(lat=44.325, lon=30.41, trust="good", kind="offshore buoy"),
    "EUXRoOB03": dict(lat=43.977, lon=29.924, trust="good", kind="offshore buoy"),
    "EUXRo03": dict(lat=43.98, lon=29.936, trust="good", kind="offshore buoy (2013-2023)"),
    "EUXRoCB01": dict(lat=45.11, lon=29.78, trust="untrusted", kind="coastal buoy",
                      note="new coastal buoy: O2 units unclear, O2 saturation and salinity implausible (under QC)"),
    "EUXRoCB02": dict(lat=44.226, lon=28.678, trust="untrusted", kind="coastal buoy",
                      note="new coastal buoy: O2 saturation ~3.6 %, salinity ~7.5 (sensor fault, under QC)"),
    "EUXRoCB03": dict(lat=43.81, lon=28.61, trust="untrusted", kind="coastal buoy",
                      note="new coastal buoy, not quality-controlled"),
    "15480": dict(lat=44.2, lon=28.6, trust="untrusted", kind="shore station",
                  note="NIMH shore station: ~3.5 C colder than open water; air and harbour context only"),
}

# Per-variable trust of a platform, overriding the platform-level trust for that one variable (SHORTLIST section 4,
# evidence in docs/indicators/validation/interpretation.md and metrics.csv). A flagged platform is still returned on
# explicit request (source="buoy", compare_sources) with this trust and reason in attrs, but "auto" never picks it.
_CHL_FLUO = ("indicative", "buoy chlorophyll is fluorescence, not calibrated against bottles: reads 2-3x satellite and "
             "model at EUXRoOB01-03 (2024-2026), R2 0.00 against satellite at EUXRo03 (2013-2023); comparison only")
_SAL_FOUL = ("untrusted", "buoy salinity shows fouling-like drops to 13-15 PSU lasting weeks to months "
             "(R2 0.00-0.17 against the model); not used, the model is the salinity source")
VARIABLE_TRUST: dict[tuple[str, str], tuple[str, str]] = {
    ("EUXRoOB01", "chl"): _CHL_FLUO, ("EUXRoOB02", "chl"): _CHL_FLUO, ("EUXRoOB03", "chl"): _CHL_FLUO,
    ("EUXRo03", "chl"): _CHL_FLUO,
    ("EUXRoOB01", "sal"): _SAL_FOUL, ("EUXRoOB02", "sal"): _SAL_FOUL, ("EUXRoOB03", "sal"): _SAL_FOUL,
}
AUTO_EXCLUDED_TRUST = ("indicative", "untrusted", "not_usable_absolute")   # per-variable flags that "auto" skips


def variable_trust(platform: str, variable: str) -> tuple[str, str | None]:
    """(trust, reason) of one platform for one variable: the VARIABLE_TRUST flag if any, else the platform trust."""
    if (platform, variable) in VARIABLE_TRUST:
        return VARIABLE_TRUST[(platform, variable)]
    p = PLATFORMS.get(platform, {})
    return p.get("trust", "good"), p.get("note")


EVIDENCE = {"satellite": "satellite", "model": "model", "reanalysis": "model", "in-situ": "measured",
            "derived": "model"}


class DataUnavailable(RuntimeError):
    """No source could deliver the requested series."""


# ------------------------------------------------------------------------------------------- small helpers
def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return (t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t)


def today() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None).normalize()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _bucket() -> int:
    """In-memory cache generation: changes every 6 hours so a long-running app picks up refreshed files."""
    return int(time.time() // (6 * 3600))


def _max_age(end: pd.Timestamp) -> float | None:
    """max_age_h for copernicus.fetch_timeseries: None (source default) for old windows, else our freshness limit."""
    if OFFLINE:
        return 1e9
    if end < today() - pd.Timedelta(days=10):
        return None
    return RECENT_MAX_AGE_H


def _cm():
    from .sources import copernicus
    return copernicus


def _with_offline_fallback(fn: Callable, *a, **kw):
    """Call a copernicus fetcher; if the refresh fails (offline, timeout), read the stale cache instead."""
    try:
        return fn(*a, **kw)
    except Exception:
        if kw.get("max_age_h") == 1e9:
            raise
        kw["max_age_h"] = 1e9
        return fn(*a, **kw)


def recent_window(days: int = 60) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(today - days, today): the window scripts/preload_cache.py warms for charts and compare_sources."""
    t = today()
    return t - pd.Timedelta(days=days), t


def card_window(date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Canonical fetch window used by the indicator cards and by scripts/preload_cache.py (same window = same cache).

    Recent dates (current year or the last 120 days): the last 366 days up to today + 10 days of forecast.
    Older dates: the calendar year of the date.
    """
    d, t = _ts(date).normalize(), today()
    if d.year == t.year or d >= t - pd.Timedelta(days=120):
        return t - pd.Timedelta(days=366), t + pd.Timedelta(days=10)
    return pd.Timestamp(f"{d.year}-01-01"), pd.Timestamp(f"{d.year}-12-31")


# ------------------------------------------------------------------------------------------- source register
# kind: how to fetch. "pair" = reanalysis key up to its end + analysis/forecast key after its start.
S = dict
SOURCES: dict[str, list[dict]] = {
    "sst": [
        S(id="satellite", kind="sst_sat", label="Satellite SST L4 (CMEMS REP + NRT, NRT offset removed)",
          origin="satellite", trust="good", unit="°C"),
        S(id="model", kind="pair", rea="rea_phy_temp", anfc="phy_temp", native="thetao", col="temp",
          rea_end=PHY_REA_END, anfc_start=PHY_ANFC_START, label="Copernicus Black Sea physics model, top level",
          origin="model", trust="good", unit="°C"),
        S(id="buoy", kind="buoy", col="temp", label="Nearest offshore buoy", origin="in-situ", trust="good", unit="°C"),
        S(id="station 15480", kind="platform", platform="15480", col="temp", label="NIMH shore station 15480 (Constanta)",
          origin="in-situ", trust="untrusted", unit="°C"),
        S(id="coastal buoy", kind="buoy_untrusted", col="temp", label="Nearest coastal buoy EUXRoCB0x",
          origin="in-situ", trust="untrusted", unit="°C"),
    ],
    "bottom_temp": [
        S(id="model", kind="pair", rea="rea_phy_temp", anfc="phy_temp", native="bottomT", col="bottom_temp",
          rea_end=PHY_REA_END, anfc_start=PHY_ANFC_START, label="Copernicus Black Sea physics model, bottom level",
          origin="model", trust="usable", unit="°C"),
    ],
    "sal": [
        S(id="model", kind="pair", rea="rea_phy_sal", anfc="phy_sal", native="so", col="sal",
          rea_end=PHY_REA_END, anfc_start=PHY_ANFC_START, label="Copernicus Black Sea physics model, top level",
          origin="model", trust="good", unit="PSU"),
        S(id="buoy", kind="buoy", col="sal", label="Nearest offshore buoy", origin="in-situ", trust="good", unit="PSU"),
        S(id="coastal buoy", kind="buoy_untrusted", col="sal", label="Nearest coastal buoy EUXRoCB0x",
          origin="in-situ", trust="untrusted", unit="PSU"),
    ],
    "mld": [
        S(id="model", kind="pair", rea="rea_phy_mld", anfc="phy_mld", native="mlotst", col="mld",
          rea_end=PHY_REA_END, anfc_start=PHYX_ANFC_START, label="Copernicus Black Sea physics model, mixed-layer depth",
          origin="model", trust="good", unit="m"),
    ],
    "chl": [
        S(id="satellite", kind="chl_sat", label="Satellite chl-a L4 gap-free 1 km (CMEMS multi-year + NRT)",
          origin="satellite", trust="good", unit="mg/m³"),
        S(id="model", kind="pair", rea="rea_bgc_chl", anfc="bgc_chl", native="chl", col="chl",
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus Black Sea BGC model, surface chl",
          origin="model", trust="indicative", unit="mg/m³"),
        S(id="buoy", kind="buoy", col="chl", label="Nearest offshore buoy (fluorescence)", origin="in-situ",
          trust="usable", unit="mg/m³"),
    ],
    "kd490": [
        S(id="satellite", kind="kd_sat", label="Satellite Kd490 (CMEMS ocean colour, multi-year + NRT)",
          origin="satellite", trust="good", unit="1/m"),
    ],
    "o2": [
        S(id="buoy", kind="buoy", col="o2", scale=O2_MG, auto_only_near=True, label="Nearest offshore buoy (measured O2)",
          origin="in-situ", trust="good", unit="mg/L"),
        S(id="model", kind="pair", rea="rea_bgc_o2", anfc="bgc_o2", native="o2", col="o2", scale=O2_MG,
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus Black Sea BGC model, surface O2",
          origin="model", trust="usable", unit="mg/L"),
        S(id="coastal buoy", kind="buoy_untrusted", col="o2", scale=O2_MG, label="Nearest coastal buoy EUXRoCB0x",
          origin="in-situ", trust="untrusted", unit="mg/L"),
    ],
    "o2_sat": [
        S(id="buoy", kind="buoy", col="o2_sat", auto_only_near=True, label="Nearest offshore buoy (OSAT)",
          origin="in-situ", trust="good", unit="%"),
        S(id="model", kind="o2sat_model", label="Model O2 / O2 solubility (Garcia & Gordon 1992) at model T, S",
          origin="model", trust="usable", unit="%"),
    ],
    "o2_bottom": [
        S(id="model", kind="pair", rea="rea_bgc_o2", anfc="bgc_o2", native="o2b", col="o2_bottom", scale=O2_MG,
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus Black Sea BGC model, bottom O2",
          origin="model", trust="indicative", unit="mg/L",
          note="no bottom sensor exists; forecast and reanalysis systems differ by about 2 mg/L"),
    ],
    "ph": [
        S(id="model", kind="pair", rea="rea_bgc_car", anfc="bgc_car", native="ph", col="ph",
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus Black Sea BGC model, surface pH",
          origin="model", trust="indicative", unit=""),
    ],
    "no3": [
        S(id="bottles", kind="bottles", col="no3", label="EMODnet Chemistry bottle samples 0-5 m within 30 km",
          origin="in-situ", trust="good", unit="mmol/m³"),
        S(id="model", kind="pair", rea="rea_bgc_nut", anfc="bgc_nut", native="no3", col="no3", auto=False,
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus BGC model nitrate (NOT usable as absolute values)",
          origin="model", trust="not_usable_absolute", unit="mmol/m³"),
    ],
    "po4": [
        S(id="bottles", kind="bottles", col="po4", label="EMODnet Chemistry bottle samples 0-5 m within 30 km",
          origin="in-situ", trust="good", unit="mmol/m³"),
        S(id="model", kind="pair", rea="rea_bgc_nut", anfc="bgc_nut", native="po4", col="po4", auto=False,
          rea_end=BGC_REA_END, anfc_start=BGC_ANFC_START, label="Copernicus BGC model phosphate (NOT usable as absolute values)",
          origin="model", trust="not_usable_absolute", unit="mmol/m³"),
    ],
    "si": [S(id="bottles", kind="bottles", col="si", label="EMODnet Chemistry bottle samples 0-5 m within 30 km",
             origin="in-situ", trust="good", unit="mmol/m³")],
    "nh4": [S(id="bottles", kind="bottles", col="nh4", label="EMODnet Chemistry bottle samples 0-5 m within 30 km",
              origin="in-situ", trust="good", unit="mmol/m³")],
    "wave_height": [
        S(id="model", kind="cmems_daily", key="wav", native="VHM0", col="wave_height", how="max",
          label="Copernicus Black Sea wave model, daily max Hs", origin="model", trust="good", unit="m"),
        S(id="open-meteo", kind="openmeteo", col="wave_height", how="max", label="Open-Meteo marine (MFWAM/ECMWF-WAM), daily max Hs",
          origin="model", trust="usable", unit="m"),
    ],
    "wind_speed": [
        S(id="era5", kind="openmeteo", col="wind_speed", how="mean", label="ERA5 via Open-Meteo (forecast after today)",
          origin="reanalysis", trust="good", unit="m/s"),
    ],
    "discharge": [
        S(id="glofas", kind="glofas", label="Danube discharge at the delta apex, GloFAS v4 (Open-Meteo Flood API)",
          origin="model", trust="good", unit="m³/s"),
    ],
}
ALIASES = {"temp": "sst", "do": "o2", "salinity": "sal", "chlorophyll": "chl", "bottom_o2": "o2_bottom",
           "hs": "wave_height", "danube": "discharge"}
VARIABLES = sorted(SOURCES)


def _var(variable: str) -> str:
    v = ALIASES.get(variable, variable)
    if v not in SOURCES:
        raise KeyError(f"unknown variable {variable!r}; known: {VARIABLES}")
    return v


def sources_for(variable: str) -> list[dict]:
    """The source register for one variable (copies; safe to show in the UI)."""
    return [dict(s) for s in SOURCES[_var(variable)]]


# ------------------------------------------------------------------------------------------- fetchers
def _cm_series(key: str, lat: float, lon: float, start, end, native: str, col: str, depth=None) -> pd.DataFrame:
    cm = _cm()
    start, end = _ts(start), _ts(end)
    df = _with_offline_fallback(cm.fetch_timeseries, key, lat, lon, start, end, variables=[native], depth=depth,
                                max_age_h=_max_age(end))
    out = df[[col]].copy()
    out.attrs = dict(df.attrs)
    return out


def _attrs_from(df: pd.DataFrame) -> dict:
    a = df.attrs
    return {"dataset": a.get("dataset"), "key": a.get("key"), "origin": a.get("origin"),
            "grid_lat": a.get("grid_lat"), "grid_lon": a.get("grid_lon"), "distance_km": a.get("distance_km"),
            "depth_m": a.get("depth_m"), "citation": a.get("citation")}


def _fetch_pair(spec: dict, lat, lon, start, end) -> tuple[pd.Series, list[dict]]:
    """Reanalysis up to its end, then analysis/forecast (the reanalysis wins where both exist: it is the system the
    climatology comes from, and for bottom O2 it is closer to the bottle observations)."""
    start, end = _ts(start), _ts(end)
    parts, used, errs = [], [], []
    if start <= spec["rea_end"]:
        try:
            r = _cm_series(spec["rea"], lat, lon, start, min(end, spec["rea_end"] + pd.Timedelta(hours=23, minutes=59)),
                           spec["native"], spec["col"])
            parts.append(r[spec["col"]])
            used.append({**_attrs_from(r), "role": "reanalysis"})
        except Exception as e:  # noqa: BLE001
            errs.append(f"{spec['rea']}: {e}")
    if end >= spec["anfc_start"]:
        try:
            f = _cm_series(spec["anfc"], lat, lon, max(start, spec["anfc_start"]), end, spec["native"], spec["col"])
            fs = f[spec["col"]]
            if parts and len(parts[0].dropna()):
                fs = fs[fs.index > parts[0].dropna().index.max()]
            parts.append(fs)
            used.append({**_attrs_from(f), "role": "analysis/forecast"})
        except Exception as e:  # noqa: BLE001
            errs.append(f"{spec['anfc']}: {e}")
    if not parts:
        raise DataUnavailable("; ".join(errs) or "window outside both model systems")
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s * spec.get("scale", 1.0), used


def _fetch_sst_sat(lat, lon, start, end) -> tuple[pd.Series, list[dict], list[str]]:
    """REP (climate record) where it exists, NRT after it minus the NRT-REP offset."""
    start, end = _ts(start), _ts(end)
    parts, used, notes = [], [], []
    try:
        r = _cm_series("sst_l4_rep", lat, lon, start, min(end, today()), "analysed_sst", "sst")
        rs = r["sst"].dropna()
        if len(rs):
            parts.append(rs)
            used.append({**_attrs_from(r), "role": "REP"})
    except Exception:  # noqa: BLE001
        rs = pd.Series(dtype=float)
    rep_end = rs.index.max() if len(rs) else None
    if rep_end is None or rep_end < min(end, today()):
        n0 = max(start, rep_end + pd.Timedelta(days=1)) if rep_end is not None else start
        # NRT windows: whole recent window (keeps a single cache file per day)
        n = _cm_series("sst_l4_nrt", lat, lon, start, min(end, today()), "analysed_sst", "sst")
        ns = n["sst"].dropna()
        ns = ns[ns.index >= n0] - SST_NRT_MINUS_REP
        if len(ns):
            parts.append(ns)
            used.append({**_attrs_from(n), "role": "NRT"})
            notes.append(f"NRT values lowered by {SST_NRT_MINUS_REP} °C (NRT minus REP offset over their overlap)")
    if not parts:
        raise DataUnavailable("no satellite SST in window")
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="first")], used, notes


def _fetch_chl_sat(lat, lon, start, end) -> tuple[pd.Series, list[dict], list[str]]:
    start, end = _ts(start), _ts(end)
    parts, used, notes = [], [], []
    try:
        m = _cm_series("sat_chl_l4_my", lat, lon, start, min(end, today()), "CHL", "chl")
        ms = m["chl"].dropna()
        if len(ms):
            parts.append(ms)
            used.append({**_attrs_from(m), "role": "multi-year (incl. interim)"})
    except Exception:  # noqa: BLE001
        ms = pd.Series(dtype=float)
    my_end = ms.index.max() if len(ms) else None
    if end >= today() - pd.Timedelta(days=20) and (my_end is None or my_end < min(end, today())):
        try:
            n = _cm_series("sat_chl_l4_nrt", lat, lon, today() - pd.Timedelta(days=20), today(), "CHL", "chl")
            ns = n["chl"].dropna()
            if my_end is not None:
                ns = ns[ns.index > my_end]
            if len(ns):
                parts.append(ns)
                used.append({**_attrs_from(n), "role": "NRT"})
        except Exception as e:  # noqa: BLE001
            notes.append(f"NRT chl unavailable: {e}")
    if not parts:
        raise DataUnavailable("no satellite chl in window")
    s = pd.concat(parts).sort_index()
    s = s[(s.index >= start) & (s.index <= end)]
    return s[~s.index.duplicated(keep="first")], used, notes


def _fetch_kd_sat(lat, lon, start, end) -> tuple[pd.Series, list[dict], list[str]]:
    start, end = _ts(start), _ts(end)
    parts, used, notes = [], [], []
    try:
        m = _cm_series("sat_kd490_my", lat, lon, start, min(end, today()), "KD490", "kd490")
        ms = m["kd490"].dropna()
        if len(ms):
            parts.append(ms)
            used.append({**_attrs_from(m), "role": "multi-year"})
    except Exception:  # noqa: BLE001
        ms = pd.Series(dtype=float)
    my_end = ms.index.max() if len(ms) else None
    if end >= today() - pd.Timedelta(days=20) and (my_end is None or my_end < today() - pd.Timedelta(days=2)):
        try:
            n = _cm_series("sat_kd490_nrt", lat, lon, today() - pd.Timedelta(days=30), today(), "KD490", "kd490")
            ns = n["kd490"].dropna()
            if my_end is not None:
                ns = ns[ns.index > my_end]
            if len(ns):
                parts.append(ns)
                used.append({**_attrs_from(n), "role": "NRT"})
        except Exception as e:  # noqa: BLE001
            notes.append(f"NRT Kd490 unavailable: {e}")
    if not parts:
        raise DataUnavailable("no satellite Kd490 in window")
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated(keep="first")], used, notes


_INSITU_COLS = {"do_sat": "o2_sat"}


GEOECOMAR = "https://erddap.geoecomar.ro/erddap/tabledap"


def salinity_pss78(c_mscm, t, p_dbar=0.0):
    """Practical salinity (PSS-78, UNESCO 1983) from conductivity (mS/cm), temperature (deg C) and pressure (dbar)."""
    c, t, p = np.asarray(c_mscm, float), np.asarray(t, float), np.asarray(p_dbar, float)
    a = [0.0080, -0.1692, 25.3851, 14.0941, -7.0261, 2.7081]
    b = [0.0005, -0.0056, -0.0066, -0.0375, 0.0636, -0.0144]
    cc = [0.6766097, 2.00564e-2, 1.104259e-4, -6.9698e-7, 1.0031e-9]
    e_ = [2.070e-5, -6.370e-10, 3.989e-15]
    d_ = [3.426e-2, 4.464e-4, 4.215e-1, -3.107e-3]
    r = c / 42.914
    rt_ = cc[0] + cc[1] * t + cc[2] * t ** 2 + cc[3] * t ** 3 + cc[4] * t ** 4
    rp = 1 + p * (e_[0] + e_[1] * p + e_[2] * p ** 2) / (1 + d_[0] * t + d_[1] * t ** 2 + (d_[2] + d_[3] * t) * r)
    rt = np.clip(r / (rp * rt_), 0, None)
    x = np.sqrt(rt)
    ds = (t - 15) / (1 + 0.0162 * (t - 15)) * (b[0] + b[1] * x + b[2] * x ** 2 + b[3] * x ** 3 + b[4] * x ** 4 + b[5] * x ** 5)
    return a[0] + a[1] * x + a[2] * x ** 2 + a[3] * x ** 3 + a[4] * x ** 4 + a[5] * x ** 5 + ds


def _geoecomar_frame(pid: str, s: pd.Timestamp, e: pd.Timestamp) -> pd.DataFrame:
    """Daily means from the GeoEcoMar ERDDAP ({pid}_{year} datasets, 2024 onwards): live, fresher than EMODnet and the
    Copernicus In Situ TAC. DOXY in umol/L (500 = sensor range cap, dropped; no DOXY QC); salinity from conductivity
    (PSS-78); saturation from Garcia & Gordon (1992). Cached under data/cache/datahub/ (6 h for recent windows)."""
    import io

    import requests
    k = cache_key("geoecomar", pid, str(s.date()), str(e.date()))
    p = cached_path("datahub", k, "parquet")
    recent = e >= today() - pd.Timedelta(days=3)
    if p.exists() and (OFFLINE or not recent or time.time() - p.stat().st_mtime < 6 * 3600):
        return pd.read_parquet(p)
    parts = []
    try:
        for y in range(max(s.year, 2024), e.year + 1):
            url = (f"{GEOECOMAR}/{pid}_{y}.csv?time,TEMP,DOXY,CPWC,CNDC,PRES"
                   f"&time%3E={max(s, pd.Timestamp(f'{y}-01-01')).date()}T00:00:00Z"
                   f"&time%3C={min(e + pd.Timedelta(days=1), pd.Timestamp(f'{y + 1}-01-01')).date()}T00:00:00Z")
            r = requests.get(url, timeout=90, headers={"User-Agent": "marinekit-hackathon/0.1 (python-requests)"})
            if r.status_code == 404:
                continue
            r.raise_for_status()
            parts.append(pd.read_csv(io.StringIO(r.text), skiprows=[1], parse_dates=["time"]))
    except Exception:
        if p.exists():
            return pd.read_parquet(p)
        raise
    if not parts:
        df = pd.DataFrame(columns=["temp", "sal", "o2", "o2_sat", "chl"])
    else:
        raw = pd.concat(parts).set_index("time")
        raw.index = raw.index.tz_localize(None) if raw.index.tz is not None else raw.index
        raw.loc[raw["DOXY"] >= 499, "DOXY"] = np.nan
        raw["sal"] = salinity_pss78(raw["CNDC"], raw["TEMP"], raw["PRES"].fillna(0))
        raw.loc[(raw["sal"] < 5) | (raw["sal"] > 25), "sal"] = np.nan
        df = raw.rename(columns={"TEMP": "temp", "DOXY": "o2", "CPWC": "chl"})[["temp", "sal", "o2", "chl"]]
        df = df.resample("1D").mean()
        df["o2_sat"] = o2_saturation_pct(df["o2"], df["temp"], df["sal"])
    df.index.name = "time"
    df.to_parquet(p)
    return df


@functools.lru_cache(maxsize=64)
def _platform_frame(pid: str, start: str, end: str, bucket: int) -> pd.DataFrame:
    """Daily means of one platform. Offshore buoys EUXRoOB01-03 from 2024: GeoEcoMar ERDDAP first (live). Otherwise
    the Copernicus In Situ TAC, then EMODnet Physics."""
    errs = []
    s, e = _ts(start), _ts(end)
    if pid.startswith("EUXRoOB") and e >= pd.Timestamp("2024-01-01"):
        try:
            d = _geoecomar_frame(pid, s, e)
            if len(d.dropna(how="all")):
                d.attrs = {"via": "GeoEcoMar ERDDAP (live, salinity from conductivity)"}
                return d
        except Exception as ex:  # noqa: BLE001
            errs.append(f"geoecomar: {ex}")
    try:
        cm = _cm()
        df = _with_offline_fallback(cm.fetch_insitu, pid, s, e, ["temp", "sal", "o2", "o2_sat", "chl"],
                                    max_age_h=_max_age(e))
        d = df.resample("1D").mean(numeric_only=True)
        d.attrs = {**df.attrs, "via": "Copernicus In Situ TAC"}
        if len(d.dropna(how="all")):
            return d
    except Exception as ex:  # noqa: BLE001
        errs.append(f"copernicus insitu: {ex}")
    try:
        from .sources import emodnet_insitu as ei
        df = ei.fetch_platform(pid, s, e, ["temp", "sal", "o2", "do_sat", "chl"], resample="1D")
        df = df.rename(columns=_INSITU_COLS)
        df.attrs = {**df.attrs, "via": "EMODnet Physics ERDDAP"}
        return df
    except Exception as ex:  # noqa: BLE001
        errs.append(f"emodnet: {ex}")
    raise DataUnavailable(f"platform {pid}: " + "; ".join(errs))


def _platform_series(pid: str, col: str, start, end, scale=1.0) -> tuple[pd.Series, dict]:
    start, end = _ts(start).normalize(), _ts(end).normalize()
    d = _platform_frame(pid, str(start.date()), str(min(end, today()).date()), _bucket())
    if col not in d or d[col].dropna().empty:
        raise DataUnavailable(f"platform {pid} has no {col} in window")
    return d[col] * scale, {"dataset": f"{pid} ({d.attrs.get('via')})", "platform": pid, "origin": "in-situ"}


def nearest_platforms(lat, lon, trust: str = "good", max_km: float | None = None) -> list[tuple[str, float]]:
    out = sorted(((p, haversine_km(lat, lon, v["lat"], v["lon"])) for p, v in PLATFORMS.items()
                  if (v["trust"] == "good") == (trust == "good")), key=lambda x: x[1])
    return [(p, round(d, 1)) for p, d in out if max_km is None or d <= max_km]


def _fetch_bottles(col: str, lat, lon, start, end) -> tuple[pd.Series, dict]:
    from .sources import emodnet_insitu as ei
    c = ei.fetch_chemistry_samples(lat, lon, 30, variables=["temp", "sal", "o2", "do_sat", "no3", "no2", "nh4", "po4", "si", "ph", "chl"],
                                   max_depth=None)
    c = c[c["depth"] <= 5]
    if col == "din":
        c = c.assign(din=c[["no3", "no2", "nh4"]].sum(axis=1, min_count=2))
    s = c[col].dropna() if col in c else pd.Series(dtype=float)
    s = s.groupby(s.index.normalize()).mean()
    s = s[(s.index >= _ts(start)) & (s.index <= _ts(end))]
    last = c[col].dropna().index.max() if col in c and c[col].notna().any() else None
    return s, {"dataset": "EMODnet Chemistry EUT_BLACKSEA_PROFILES (bottles 0-5 m, <= 30 km)", "origin": "in-situ",
               "last_sample": None if last is None else str(last.date())}


@functools.lru_cache(maxsize=32)
def _openmeteo_frame(lat, lon, start: str, end: str, bucket: int) -> pd.DataFrame:
    from .sources import open_data as od
    return od.marine_weather(lat, lon, start, end, freq="hourly")


def _auto_buoys(lat, lon, variable: str | None, max_km: float | None = None) -> list[tuple[str, float]]:
    """Trusted offshore buoys near the point, minus those flagged for this variable in VARIABLE_TRUST."""
    return [(p, d) for p, d in nearest_platforms(lat, lon, "good", max_km)
            if variable is None or variable_trust(p, variable)[0] not in AUTO_EXCLUDED_TRUST]


def _fetch_one(spec: dict, lat, lon, start, end, variable: str | None = None, auto: bool = False) -> tuple[pd.Series, dict]:
    """Returns (daily series, attrs) for one source spec. auto=True skips buoys flagged in VARIABLE_TRUST."""
    kind, start, end = spec["kind"], _ts(start), _ts(end)
    notes = [spec["note"]] if spec.get("note") else []
    datasets, dist, extra = [], None, {}
    if kind == "pair":
        s, used = _fetch_pair(spec, lat, lon, start, end)
        datasets = used
    elif kind == "sst_sat":
        s, datasets, n = _fetch_sst_sat(lat, lon, start, end)
        notes += n
    elif kind == "chl_sat":
        s, datasets, n = _fetch_chl_sat(lat, lon, start, end)
        notes += n
    elif kind == "kd_sat":
        s, datasets, n = _fetch_kd_sat(lat, lon, start, end)
        notes += n
    elif kind == "o2sat_model":
        o2, u1 = _fetch_pair(SOURCES["o2"][1], lat, lon, start, end)
        t, u2 = _fetch_pair(SOURCES["sst"][1], lat, lon, start, end)
        sa, u3 = _fetch_pair(SOURCES["sal"][0], lat, lon, start, end)
        s = o2_saturation_pct(o2 / O2_MG, t, sa).dropna()
        datasets = u1 + u2 + u3
        notes.append("saturation = O2 / O2sat(T, S), Garcia & Gordon (1992); checked against buoy OSAT, r 0.98")
    elif kind in ("buoy", "buoy_untrusted"):
        trust = "good" if kind == "buoy" else "untrusted"
        if kind == "buoy" and auto:
            cands = _auto_buoys(lat, lon, variable)
        else:
            cands = nearest_platforms(lat, lon, trust, None if kind == "buoy" else NEAR_KM)
        if kind == "buoy_untrusted":
            cands = [x for x in cands if PLATFORMS[x[0]]["kind"] == "coastal buoy"]
        if not cands:
            raise DataUnavailable(f"no {trust} platform near the point"
                                  + (f" for {variable} (others flagged in VARIABLE_TRUST)" if auto else ""))
        errs = []
        for pid, d in cands[:3]:
            try:
                s, a = _platform_series(pid, spec["col"], start, end, spec.get("scale", 1.0))
                datasets, dist = [a], d
                extra["platform"] = pid
                if PLATFORMS[pid].get("note"):
                    notes.append(PLATFORMS[pid]["note"])
                if variable is not None and (pid, variable) in VARIABLE_TRUST:
                    extra["trust"], why = VARIABLE_TRUST[(pid, variable)]
                    notes.append(f"{pid} {variable}: {extra['trust']}: {why}")
                break
            except Exception as ex:  # noqa: BLE001
                errs.append(f"{pid}: {ex}")
        else:
            raise DataUnavailable("; ".join(errs))
    elif kind == "platform":
        pid = spec["platform"]
        dist = round(haversine_km(lat, lon, PLATFORMS[pid]["lat"], PLATFORMS[pid]["lon"]), 1)
        s, a = _platform_series(pid, spec["col"], start, end, spec.get("scale", 1.0))
        datasets = [a]
        extra["platform"] = pid
        notes.append(PLATFORMS[pid]["note"])
    elif kind == "bottles":
        s, a = _fetch_bottles(spec["col"], lat, lon, start, end)
        datasets = [a]
        notes.append(f"last bottle sample with {spec['col']} near this point: {a['last_sample']}")
    elif kind == "cmems_daily":
        r = _cm_series(spec["key"], lat, lon, start, end, spec["native"], spec["col"])
        s = getattr(r[spec["col"]].resample("1D"), spec.get("how", "mean"))()
        datasets = [_attrs_from(r)]
    elif kind == "openmeteo":
        w = _openmeteo_frame(lat, lon, str(start.date()), str(end.date()), _bucket())
        s = getattr(w[spec["col"]].resample("1D"), spec.get("how", "mean"))()
        datasets = [{"dataset": w.attrs.get("dataset"), "origin": spec["origin"], "cell": w.attrs.get("marine_cell")}]
    elif kind == "glofas":
        s, a = danube_discharge(start, end)
        datasets = [a]
    else:
        raise ValueError(kind)
    if dist is None:
        ds = [d.get("distance_km") for d in datasets if isinstance(d, dict) and d.get("distance_km") is not None]
        dist = max(ds) if ds else None
    s = s.astype(float)
    s.index = pd.DatetimeIndex(s.index).normalize()
    s = s.groupby(level=0).mean()
    attrs = {"source_id": spec["id"], "label": spec["label"], "origin": spec["origin"],
             "evidence": EVIDENCE[spec["origin"]], "trust": spec["trust"], "unit": spec["unit"],
             "datasets": datasets, "distance_km": dist, "notes": notes, **extra}
    return s, attrs


_FAILED: dict[tuple, str] = {}


@functools.lru_cache(maxsize=512)
def _series_cached(variable, lat, lon, start, end, source, bucket) -> pd.DataFrame:
    specs = SOURCES[variable]
    if source == "auto":
        cands = []
        for sp in specs:
            if sp["trust"] in ("untrusted", "not_usable_absolute") or sp.get("auto") is False:
                continue
            if sp.get("auto_only_near"):
                if not _auto_buoys(lat, lon, variable, BUOY_AUTO_KM):
                    continue
            if sp["kind"] == "buoy" and not _auto_buoys(lat, lon, variable):
                continue                     # every buoy is flagged for this variable (VARIABLE_TRUST)
            cands.append(sp)
    else:
        cands = [sp for sp in specs if sp["id"] == source]
        if not cands:
            raise KeyError(f"{variable}: unknown source {source!r}; have {[s['id'] for s in specs]}")
    errs = []
    for sp in cands:
        try:
            s, attrs = _fetch_one(sp, lat, lon, start, end, variable=variable, auto=(source == "auto"))
            s = s[(s.index >= _ts(start).normalize()) & (s.index <= _ts(end))]
            df = s.rename(variable).to_frame()
            df.index.name = "time"
            df.attrs = {"variable": variable, "lat": lat, "lon": lon, "requested_source": source, **attrs}
            if errs:
                df.attrs["notes"] = df.attrs["notes"] + [f"fell back after: {'; '.join(errs)}"]
            return df
        except Exception as e:  # noqa: BLE001
            errs.append(f"{sp['id']}: {type(e).__name__}: {e}")
    raise DataUnavailable(f"{variable} at ({lat}, {lon}) {start}..{end}: " + " | ".join(errs))


def get_series(variable: str, lat: float, lon: float, start, end, source: str = "auto") -> pd.DataFrame:
    """Daily series of one variable at a point. source="auto" picks the best trusted source (see module doc);
    otherwise a source id from sources_for(variable), e.g. "satellite", "model", "buoy", "station 15480".
    Raises DataUnavailable if nothing can be fetched (or read from cache when offline)."""
    v = _var(variable)
    s, e = _ts(start), _ts(end)
    key = (v, round(float(lat), 4), round(float(lon), 4), str(s), str(e), source, _bucket())
    if key in _FAILED:                       # do not retry a failed source over the network within the same bucket
        raise DataUnavailable(_FAILED[key])
    try:
        df = _series_cached(*key)
    except Exception as ex:
        _FAILED[key] = f"{type(ex).__name__}: {ex}"
        raise
    out = df.copy()
    out.attrs = json.loads(json.dumps(df.attrs, default=str))
    return out


# ------------------------------------------------------------------------------------------- climatology
def _doy365(idx) -> np.ndarray:
    idx = pd.DatetimeIndex(idx)
    doy = idx.day_of_year.to_numpy().copy()
    doy[idx.is_leap_year & (doy > 59)] -= 1
    return doy


def doy_climatology(s: pd.Series, years: tuple[int, int], window: int = 11, smooth: int = 31,
                    log: bool = False) -> pd.DataFrame:
    """Day-of-year climatology (same recipe as copernicus.climatology): pool +-window/2 days over the reference years,
    then a circular running mean of `smooth` days. log=True works on log10 values and returns the geometric mean as
    'mean', p10/p50/p90 back-transformed, and 'std' = standard deviation of log10 (attrs space='log10')."""
    s = s.dropna()
    s = s[(s.index.year >= years[0]) & (s.index.year <= years[1])]
    if log:
        s = s[s > 0]
    v = np.log10(s.values) if log else s.values
    dd, half, rows = _doy365(s.index), window // 2, []
    for d in range(1, 366):
        dist = np.abs(dd - d)
        x = v[np.minimum(dist, 365 - dist) <= half]
        st = [np.nanmean(x), np.nanstd(x, ddof=1), *np.nanpercentile(x, [10, 50, 90])] if len(x) > 1 else [np.nan] * 5
        rows.append((d, *st, len(x)))
    out = pd.DataFrame(rows, columns=["doy", "mean", "std", "p10", "p50", "p90", "n"]).set_index("doy")
    if smooth and smooth > 1:
        k = smooth // 2
        for c in ["mean", "std", "p10", "p50", "p90"]:
            x = out[c].to_numpy()
            out[c] = pd.Series(np.concatenate([x[-k:], x, x[:k]])).rolling(smooth, center=True, min_periods=1).mean().to_numpy()[k:-k]
    if log:
        for c in ["mean", "p10", "p50", "p90"]:
            out[c] = 10 ** out[c]
    return out


def _disk_cached(tag: str, parts: tuple, fn: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """Derived tables cached forever under data/cache/datahub/ (attrs in a JSON sidecar)."""
    k = cache_key(tag, *parts)
    p = cached_path("datahub", k, "parquet")
    pj = p.with_suffix(".json")
    if p.exists():
        df = pd.read_parquet(p)
        if pj.exists():
            df.attrs = json.loads(pj.read_text())
        return df
    df = fn()
    df.to_parquet(p)
    pj.write_text(json.dumps(df.attrs, default=str))
    return df


# variable -> (copernicus key, canonical column, scale, years label) for model / satellite climatologies
_CM_CLIM = {
    "sst": ("sst_l4_rep", "sst", 1.0, "satellite"),
    "bottom_temp": ("phy_temp", "bottom_temp", 1.0, "reanalysis"),
    "sal": ("phy_sal", "sal", 1.0, "reanalysis"),
    "mld": ("phy_mld", "mld", 1.0, "reanalysis"),
    "o2": ("bgc_o2", "o2", O2_MG, "reanalysis"),
    "o2_bottom": ("bgc_o2", "o2_bottom", O2_MG, "reanalysis"),
    "ph": ("bgc_car", "ph", 1.0, "reanalysis"),
    "chl_model": ("bgc_chl", "chl", 1.0, "reanalysis"),
}


def _cm_clim(variable, lat, lon, key, col, scale) -> pd.DataFrame:
    cm = _cm()
    c = cm.climatology(key, lat, lon, variable=col)
    out = c.copy()
    for k in ("mean", "std", "p10", "p50", "p90"):
        out[k] = out[k] * scale
    a = c.attrs
    out.attrs = {"variable": variable, "dataset": a.get("dataset"), "key": a.get("key"), "years": a.get("years"),
                 "origin": a.get("origin"), "grid_lat": a.get("grid_lat"), "grid_lon": a.get("grid_lon"),
                 "distance_km": a.get("distance_km"), "space": "linear", "window_days": a.get("window_days"),
                 "smooth_days": a.get("smooth_days"), "n_years": a.get("n_years"),
                 "unit": SOURCES.get(variable, [{}])[0].get("unit", "")}
    return out


@functools.lru_cache(maxsize=256)
def _clim_cached(variable, lat, lon, source) -> pd.DataFrame:
    if variable in ("chl",) and source in ("auto", "satellite"):
        def build():
            r = _with_offline_fallback(_cm().fetch_timeseries, "sat_chl_l4_my", lat, lon, "1998-01-01", "2025-12-31",
                                       variables=["chl"], max_age_h=None)
            out = doy_climatology(r["chl"], (1998, 2020), window=31, smooth=1, log=True)
            out.attrs = {"variable": "chl", "dataset": r.attrs.get("dataset"), "key": "sat_chl_l4_my",
                         "years": [1998, 2020], "origin": "satellite", "grid_lat": r.attrs.get("grid_lat"),
                         "grid_lon": r.attrs.get("grid_lon"), "distance_km": r.attrs.get("distance_km"),
                         "space": "log10", "window_days": 31, "smooth_days": None, "unit": "mg/m³",
                         "note": "mean = geometric mean; std = standard deviation of log10(chl)"}
            return out
        return _disk_cached("clim_chl_v1", (lat, lon), build)
    if variable == "kd490":
        def build():
            r = _with_offline_fallback(_cm().fetch_timeseries, "sat_kd490_my", lat, lon, "1998-01-01",
                                       "2022-12-31T23:59:59", variables=["KD490"], max_age_h=None)
            out = doy_climatology(r["kd490"], (1998, 2022), window=31, smooth=31, log=True)
            out.attrs = {"variable": "kd490", "dataset": r.attrs.get("dataset"), "key": "sat_kd490_my",
                         "years": [1998, 2022], "origin": "satellite", "grid_lat": r.attrs.get("grid_lat"),
                         "grid_lon": r.attrs.get("grid_lon"), "distance_km": r.attrs.get("distance_km"),
                         "space": "log10", "window_days": 31, "smooth_days": 31, "unit": "1/m",
                         "note": "mean = geometric mean; std = standard deviation of log10(Kd490)"}
            return out
        return _disk_cached("clim_kd490_v1", (lat, lon), build)
    if variable == "discharge":
        def build():
            s, a = danube_discharge("1997-01-01", "2025-12-31")
            out = doy_climatology(s, (1997, 2025))
            out.attrs = {"variable": "discharge", "dataset": a["dataset"], "years": [1997, 2025], "origin": "model",
                         "space": "linear", "window_days": 11, "smooth_days": 31, "unit": "m³/s"}
            return out
        return _disk_cached("clim_discharge_v1", (), build)
    if variable == "sst" and source == "model":
        variable_key = ("phy_temp", "temp", 1.0, "reanalysis")
    elif variable == "chl" and source == "model":
        variable_key = _CM_CLIM["chl_model"]
    elif variable in _CM_CLIM:
        variable_key = _CM_CLIM[variable]
    elif variable in ("no3", "po4", "si", "din"):
        return nutrient_climatology(variable, lat, lon)
    else:
        raise DataUnavailable(f"no climatology defined for {variable}")
    key, col, scale, _ = variable_key
    try:
        return _cm_clim(variable, lat, lon, key, col, scale)
    except Exception:
        if OFFLINE:
            raise
        raise


def get_climatology(variable: str, lat: float, lon: float, source: str = "auto") -> pd.DataFrame:
    """Reference conditions at a point, indexed by day of year 1..365 (Feb 29 folded into Feb 28), columns
    mean, std, p10, p50, p90, n. attrs: years, dataset, origin, space ("linear" or "log10"), unit.

    sst: satellite REP 1991-2020 (source="model": physics reanalysis 1993-2022). chl: satellite 1998-2020 in log10
    space. kd490: satellite 1998-2022 in log10 space. bottom_temp, sal, mld, o2, o2_bottom, ph: Copernicus reanalysis
    1993-2022 (O2 in mg/L). discharge: GloFAS 1997-2025. no3/po4/si/din: DIVAnd seasonal climatology (index = season).
    """
    v = _var(variable) if variable != "din" else "din"
    df = _clim_cached(v, round(float(lat), 4), round(float(lon), 4), source)
    out = df.copy()
    out.attrs = json.loads(json.dumps(df.attrs, default=str))
    return out


def nutrient_climatology(variable: str, lat: float, lon: float) -> pd.DataFrame:
    """DIVAnd 'Danube Delta' seasonal climatology at the surface (one cycle 2000-2022), trusted (_L1) values,
    index season (winter, spring, summer, autumn)."""
    from .sources import emodnet_insitu as ei

    def build():
        d = ei.chemistry_climatology_at(lat, lon, variable, "danube", depth=0.0)
        out = d.set_index("season")[[f"{variable}_L1", variable, "relerr"]].rename(
            columns={f"{variable}_L1": "mean", variable: "mean_unmasked"})
        out.attrs = {"variable": variable, "dataset": d.attrs.get("dataset"), "origin": "derived", "space": "linear",
                     "freq": "season", "years": "2000-2022", "unit": "mmol/m³", "grid_lat": d.attrs.get("lat"),
                     "grid_lon": d.attrs.get("lon"), "doi": d.attrs.get("doi")}
        return out
    return _disk_cached("nutclim_v1", (variable, round(lat, 4), round(lon, 4)), build)


def nutrient_windows(variable: str, lat: float, lon: float) -> pd.DataFrame:
    """DIVAnd 'Black Sea' moving 6-year windows at the surface (trusted _L1 values), long table time/season/value."""
    from .sources import emodnet_insitu as ei

    def build():
        d = ei.chemistry_climatology_at(lat, lon, variable, "blacksea", depth=0.0)
        out = d[["season", f"{variable}_L1", "relerr"]].rename(columns={f"{variable}_L1": "value"})
        out.attrs = {"variable": variable, "dataset": d.attrs.get("dataset"), "origin": "derived",
                     "grid_lat": d.attrs.get("lat"), "grid_lon": d.attrs.get("lon"), "doi": d.attrs.get("doi"),
                     "unit": "mmol/m³", "note": "moving 6-year windows; time = window centre"}
        return out
    return _disk_cached("nutwin_v1", (variable, round(lat, 4), round(lon, 4)), build)


# ------------------------------------------------------------------------------------------- Danube, waves
def danube_discharge(start, end) -> tuple[pd.Series, dict]:
    """GloFAS daily discharge. Recent requests are cached here for 12 h (the source re-asks Open-Meteo every call)."""
    from .sources import open_data as od
    start, end = _ts(start).normalize(), _ts(end).normalize()
    a = {"dataset": "GloFAS v4 via Open-Meteo Flood API, Danube at Ceatal Izmail", "origin": "model",
         "distance_km": None}
    if end < today() - pd.Timedelta(days=7):
        df = od.danube_discharge(start, end)
        return df["discharge"], a
    k = cache_key("danube", str(start.date()), str(end.date()))
    p = cached_path("datahub", k, "parquet")
    if p.exists() and (OFFLINE or time.time() - p.stat().st_mtime < 12 * 3600):
        return pd.read_parquet(p)["discharge"], a
    try:
        df = od.danube_discharge(start, end)[["discharge"]]
        df.to_parquet(p)
    except Exception:
        if p.exists():
            return pd.read_parquet(p)["discharge"], a
        raise
    return df["discharge"], a


def wave_p95(lat: float, lon: float) -> float:
    """Hourly Hs 95th percentile, Open-Meteo marine 2021-10-01..2025-12-31 (storm threshold, OURS)."""
    def build():
        from .sources import open_data as od
        w = od.marine_weather(lat, lon, "2021-10-01", "2025-12-31", freq="hourly")["wave_height"].dropna()
        out = pd.DataFrame({"p95": [w.quantile(0.95)], "p99": [w.quantile(0.99)], "median": [w.median()], "n": [len(w)]})
        out.attrs = {"dataset": "Open-Meteo marine, hourly Hs", "years": "2021-10..2025-12"}
        return out
    return float(_disk_cached("wavep95_v1", (round(lat, 3), round(lon, 3)), build)["p95"].iloc[0])


# ------------------------------------------------------------------------------------------- comparisons
def o2_solubility_umol_kg(t, s):
    """O2 saturation concentration (umol/kg), Garcia & Gordon (1992), Benson & Krause fit."""
    a = [5.80871, 3.20291, 4.17887, 5.10006, -9.86643e-2, 3.80369]
    b = [-7.01577e-3, -7.70028e-3, -1.13864e-2, -9.51519e-3]
    ts = np.log((298.15 - np.asarray(t, float)) / (273.15 + np.asarray(t, float)))
    s = np.asarray(s, float)
    return np.exp(a[0] + a[1] * ts + a[2] * ts ** 2 + a[3] * ts ** 3 + a[4] * ts ** 4 + a[5] * ts ** 5
                  + s * (b[0] + b[1] * ts + b[2] * ts ** 2 + b[3] * ts ** 3) - 2.75915e-7 * s ** 2)


def o2_saturation_pct(o2_mmol_m3, t, s):
    rho = (1000 + 0.78 * s - 0.0065 * (t - 4) ** 2) / 1000
    return 100 * o2_mmol_m3 / (o2_solubility_umol_kg(t, s) * rho)


def compare_sources(variable: str, lat: float, lon: float, start, end, include_untrusted: bool = True) -> pd.DataFrame:
    """All sources of one variable side by side, daily. Columns = source ids ("satellite", "model", "buoy",
    "station 15480", ...). attrs["sources"][col] = {label, origin, evidence, trust, unit, distance_km, datasets, notes};
    attrs["failed"] = {source_id: reason}. Untrusted sources are only included when closer than NEAR_KM."""
    v = _var(variable)
    cols, meta_, failed = {}, {}, {}
    for sp in SOURCES[v]:
        if sp["trust"] == "untrusted":
            if not include_untrusted:
                continue
            if sp["kind"] == "platform" and haversine_km(lat, lon, PLATFORMS[sp["platform"]]["lat"],
                                                         PLATFORMS[sp["platform"]]["lon"]) > NEAR_KM:
                continue
            if sp["kind"] == "buoy_untrusted" and not [x for x in nearest_platforms(lat, lon, "untrusted", NEAR_KM)
                                                       if PLATFORMS[x[0]]["kind"] == "coastal buoy"]:
                continue
        try:
            df = get_series(v, lat, lon, start, end, source=sp["id"])
            col = sp["id"] if "platform" not in df.attrs else f"{sp['id']} {df.attrs['platform']}".replace(
                "station 15480 15480", "station 15480")
            cols[col] = df[v]
            meta_[col] = {k: df.attrs.get(k) for k in ("label", "origin", "evidence", "trust", "unit", "distance_km",
                                                         "datasets", "notes", "platform")}
        except Exception as e:  # noqa: BLE001
            failed[sp["id"]] = f"{type(e).__name__}: {str(e)[:200]}"
    out = pd.DataFrame(cols)
    if len(out):
        out = out.asfreq("D")
    out.index.name = "time"
    out.attrs = {"variable": v, "lat": lat, "lon": lon, "sources": meta_, "failed": failed,
                 "origin": {c: m["origin"] for c, m in meta_.items()}}
    return out


def obs_vs_model(variable: str, lat: float, lon: float, start, end, obs: str = "auto", model: str = "model") -> dict:
    """Observation vs model statistics on common days: bias (model - obs), rmse, r, n, means.

    obs="auto": satellite for sst / chl / kd490; for o2, o2_sat and sal the nearest trusted offshore buoy, and the
    model is then sampled at the buoy position (not at the clicked point), which the result says in 'note'."""
    v = _var(variable)
    olat, olon, note = lat, lon, ""
    if obs == "auto":
        ids = [s["id"] for s in SOURCES[v]]
        if v in ("o2", "o2_sat", "sal"):
            pid, d = nearest_platforms(lat, lon, "good")[0]
            olat, olon = PLATFORMS[pid]["lat"], PLATFORMS[pid]["lon"]
            obs = "buoy"
            note = f"buoy {pid} is {d} km from the point; model sampled at the buoy position"
        elif "satellite" in ids:
            obs = "satellite"
        elif "buoy" in ids:
            obs = "buoy"
        else:
            raise DataUnavailable(f"{v}: no observation source to compare with")
    o = get_series(v, olat, olon, start, end, source=obs)
    m = get_series(v, olat, olon, start, end, source=model)
    j = pd.concat([o[v].rename("obs"), m[v].rename("mod")], axis=1).dropna()
    j = j[j.index <= today()]
    out = {"variable": v, "unit": o.attrs.get("unit"), "obs_source": obs, "model_source": model,
           "obs_label": o.attrs.get("label"), "model_label": m.attrs.get("label"),
           "obs_platform": o.attrs.get("platform"), "lat": olat, "lon": olon, "n": int(len(j)),
           "bias": None, "rmse": None, "r": None, "obs_mean": None, "model_mean": None,
           "start": str(_ts(start).date()), "end": str(_ts(end).date()), "note": note,
           "obs_trust": o.attrs.get("trust")}
    if out["obs_trust"] in AUTO_EXCLUDED_TRUST:
        out["note"] = (note + "; " if note else "") + (f"observation trust is {out['obs_trust']} for {v} "
                                                        "(VARIABLE_TRUST): read the statistics as a sensor check")
    if len(j) >= 3:
        d = j["mod"] - j["obs"]
        out.update(bias=round(float(d.mean()), 3), rmse=round(float(np.sqrt((d ** 2).mean())), 3),
                   r=round(float(j["obs"].corr(j["mod"])), 3), obs_mean=round(float(j["obs"].mean()), 3),
                   model_mean=round(float(j["mod"].mean()), 3))
    else:
        out["note"] = (note + "; " if note else "") + "fewer than 3 common days"
    return out


def value_on(s: pd.Series, date, max_lag_days: int = 3) -> tuple[float | None, pd.Timestamp | None]:
    """Last valid value on or before `date`, no older than max_lag_days. (None, None) if none."""
    d = _ts(date).normalize()
    x = s.dropna()
    x = x[(x.index <= d) & (x.index >= d - pd.Timedelta(days=max_lag_days))]
    if x.empty:
        return None, None
    return float(x.iloc[-1]), x.index[-1]


def clear_memory_cache() -> None:
    """Drop the in-process caches (disk caches stay)."""
    for f in (_series_cached, _clim_cached, _platform_frame, _openmeteo_frame):
        f.cache_clear()
    _FAILED.clear()
