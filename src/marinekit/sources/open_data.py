"""No-login satellite and open-API data for the Romanian Black Sea shelf.

Everything here works WITHOUT an account (verified live on 2026-11-23, see
docs/data_sources/open_data.md):

* Gridded satellite products from public ERDDAP griddap servers
  (NOAA PIFSC OceanWatch, NOAA CoastWatch central + PolarWatch mirror) and the ESA OC-CCI THREDDS (NCSS):
  SST (CoralTemp 1985-, Geo-Polar blended), chlorophyll-a (OLCI, VIIRS, DINEOF gap-filled, OC-CCI 1997-),
  Kd490 and SPM.
* Open-Meteo Marine (waves, SST, currents, sea level; model) + Open-Meteo archive/forecast weather
  (ERA5 reanalysis / IFS): wind, air temperature.
* Open-Meteo Flood API (GloFAS v4): Danube discharge at Ceatal Izmail / Tulcea, 1997- plus forecast.

Public API
----------
CATALOG                                       dataset registry (key -> dict)
latest_time(key)                              latest time step on the server
fetch_timeseries(key, lat, lon, start, end)   -> DataFrame, nearest-valid-pixel search
fetch_field(key, bbox, date)                  -> xarray.DataArray (time, lat, lon)
climatology(key, lat, lon, years=None)        -> DataFrame per day-of-year (mean, std, p10, p50, p90, n)
anomalies(key, lat, lon, start, end)          -> DataFrame value / clim / anomaly / z
marine_weather(lat, lon, start, end)          -> DataFrame (Open-Meteo marine + weather)
danube_discharge(start, end)                  -> DataFrame (GloFAS river discharge, m3/s)

All results follow the conventions in marinekit.sources (canonical names, UTC-naive DatetimeIndex,
attrs = meta(...)) and are cached under data/cache/open_data so a demo runs offline once fetched.
"""

from __future__ import annotations

import io
import json
import re
import time
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import requests
import xarray as xr

from . import BBOX_RO, CANONICAL, STATIONS, cache_key, cached_path, meta

SOURCE = "open_data"
UA = {"User-Agent": "marinekit-hackathon/0.1 (python-requests)"}

CW = "https://coastwatch.noaa.gov/erddap"  # NOAA CoastWatch central (OSPO products). Proxy times out ~20 s!
PW = "https://polarwatch.noaa.gov/erddap"  # mirrors the CoastWatch dataset IDs -> fallback
PIFSC = "https://oceanwatch.pifsc.noaa.gov/erddap"  # NOAA PIFSC OceanWatch: fast for long point series
OCCI = "https://www.oceancolour.org/thredds/ncss"  # ESA OC-CCI THREDDS NetCDF Subset Service

# Danube main channel just upstream of the delta bifurcation (Ceatal Izmail, ~8 km W of Tulcea).
# This GloFAS cell carries the full Danube flow (~6500 m3/s long-term mean); cells near the mouths
# (Sulina 45.2N 29.6E etc.) return ~0 because the 0.05 deg river network does not resolve the delta.
DANUBE_POINT = (45.225, 28.675)


def _ep(base, ds_id, lon360=False, alt=False, chunk_days=None, kind="erddap"):
    """One server endpoint for a dataset. chunk_days = max days per request (server time-out budget)."""
    if chunk_days is None:
        chunk_days = {CW: 40, PW: 40, PIFSC: 3650}.get(base, 365)
    return dict(kind=kind, base=base, id=ds_id, lon360=lon360, alt=alt, chunk_days=chunk_days)


# ----------------------------------------------------------------------------------------------
# Catalog. 'endpoints' are tried in order (first = preferred). 'log': ~log-normal variable
# (climatology stats in log10). 'clim_years': default reference period for climatology().
# ----------------------------------------------------------------------------------------------
CATALOG: dict[str, dict] = {
    # --- SST -----------------------------------------------------------------------------
    "sst_coraltemp": dict(
        endpoints=[_ep(PIFSC, "CRW_sst_v3_1", lon360=True), _ep(CW, "noaacrwsstDaily"), _ep(PW, "noaacrwsstDaily")],
        variable="analysed_sst", canonical="sst", origin="satellite",
        resolution="0.05 deg (~5 km), daily, gap-free L4", record_start="1985-01-01", latency="~2 days",
        log=False, clim_years=(1991, 2020),
        description="NOAA Coral Reef Watch CoralTemp v3.1 SST (OSTIA reanalysis 1985-2002, OSTIA NRT + "
                    "NOAA Geo-Polar Blended after). Long consistent record -> climatology.",
        citation="NOAA Coral Reef Watch (2019, updated daily). CoralTemp v3.1. NOAA CRW, College Park, MD.",
    ),
    "sst_anom_crw": dict(
        endpoints=[_ep(PIFSC, "CRW_sst_anom_v1_0", lon360=True), _ep(CW, "noaacrwsstanomalyDaily")],
        variable="sea_surface_temperature_anomaly", canonical="sst_anom", unit="°C", origin="derived",
        resolution="0.05 deg, daily", record_start="1985-01-01", latency="~2 days", log=False, clim_years=None,
        description="Coral Reef Watch SST anomaly (CoralTemp minus CRW daily climatology, 1985-2012 base). "
                    "Ready-made anomaly, no climatology download needed.",
        citation="NOAA Coral Reef Watch (2019). CoralTemp SST anomaly v3.1.",
    ),
    "sst_blended": dict(
        endpoints=[_ep(CW, "noaacwBLENDEDsstDNDaily"), _ep(PW, "noaacwBLENDEDsstDNDaily")],
        variable="analysed_sst", canonical="sst", origin="satellite",
        resolution="0.05 deg (~5 km), daily, gap-free L4", record_start="2019-07-22", latency="~1 day",
        log=False, clim_years=None,
        description="NOAA Geo-Polar Blended SST analysis, day+night (GHRSST L4). Freshest gap-free SST.",
        citation="NOAA CoastWatch/OSPO Geo-Polar Blended SST (GHRSST L4), Maturi et al. 2017.",
    ),
    # --- Chlorophyll-a ---------------------------------------------------------------------
    "chl_olci_s3a": dict(
        endpoints=[_ep(CW, "noaacwS3AOLCIchlaDaily", alt=True), _ep(PW, "noaacwS3AOLCIchlaDaily", alt=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="0.0375 deg (~4 km), daily L3 (cloud gaps)", record_start="2019-06-06", latency="~2 days",
        log=True, clim_years=None,
        description="Copernicus Sentinel-3A OLCI chlorophyll-a, NOAA NRT processing.",
        citation="Data courtesy of the Copernicus Programme, processed by NOAA CoastWatch.",
    ),
    "chl_olci_s3b": dict(
        endpoints=[_ep(CW, "noaacwS3BOLCIchlaDaily", alt=True), _ep(PW, "noaacwS3BOLCIchlaDaily", alt=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="0.0375 deg (~4 km), daily L3 (cloud gaps)", record_start="2019-06-07", latency="~2 days",
        log=True, clim_years=None,
        description="Copernicus Sentinel-3B OLCI chlorophyll-a, NOAA NRT processing.",
        citation="Data courtesy of the Copernicus Programme, processed by NOAA CoastWatch.",
    ),
    "chl_viirs_n20": dict(
        endpoints=[_ep(CW, "noaacwN20VIIRSchlaDaily", alt=True), _ep(PW, "noaacwN20VIIRSchlaDaily", alt=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="0.0375 deg (~4 km), daily L3 (cloud gaps)", record_start="2021-08-26", latency="~8 days",
        log=True, clim_years=None,
        description="NOAA-20 VIIRS chlorophyll-a, NOAA NRT (MSL12).",
        citation="NOAA CoastWatch/OSPO VIIRS ocean colour, NOAA STAR.",
    ),
    "chl_viirs_snpp_sq": dict(
        endpoints=[_ep(PIFSC, "noaa_snpp_chla_daily", lon360=True, alt=True),
                   _ep(CW, "noaacwNPPVIIRSSQchlaDaily", alt=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="0.0375 deg (~4 km), daily L3 (cloud gaps)", record_start="2012-01-02",
        latency="~2-3 weeks (S-NPP series appears to end 2026-11)", log=True, clim_years=(2012, 2025),
        description="S-NPP VIIRS science-quality chlorophyll-a, 2012-.",
        citation="NOAA CoastWatch/OSPO VIIRS ocean colour, NOAA STAR.",
    ),
    "chl_dineof": dict(
        endpoints=[_ep(CW, "noaacwNPPN20S3ASCIDINEOF2kmDaily", alt=True),
                   _ep(PW, "noaacwNPPN20S3ASCIDINEOF2kmDaily", alt=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="~0.0208 deg (~2 km), daily, gap-filled (DINEOF)", record_start="2018-01-01",
        latency="~18 days", log=True, clim_years=None,
        description="Gap-filled chlorophyll-a (DINEOF) merging S-NPP + NOAA-20 VIIRS and S-3A OLCI, science quality.",
        citation="NOAA CoastWatch DINEOF gap-filled ocean colour (Liu & Wang 2022).",
    ),
    "chl_occi_8day": dict(
        endpoints=[_ep(PIFSC, "esa-cci-chla-8d-v6-0", lon360=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="1/24 deg (~4 km), 8-day composite", record_start="1997-09-04", latency="~2 months",
        log=True, clim_years=(1998, 2020),
        description="ESA Ocean Colour CCI v6.0 merged multi-sensor chlorophyll-a, 8-day. Best long record.",
        citation="Sathyendranath et al. (2019) Sensors 19:4285; ESA OC-CCI v6.0, Plymouth Marine Laboratory.",
    ),
    "chl_occi_monthly": dict(
        endpoints=[_ep(PIFSC, "esa-cci-chla-monthly-v6-0", lon360=True)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="1/24 deg (~4 km), monthly composite", record_start="1997-09-04", latency="~2-3 months",
        log=True, clim_years=(1998, 2020),
        description="ESA OC-CCI v6.0 monthly chlorophyll-a.",
        citation="Sathyendranath et al. (2019) Sensors 19:4285; ESA OC-CCI v6.0.",
    ),
    "chl_occi_daily": dict(
        endpoints=[_ep(OCCI, "CCI_ALL-v6.0-DAILY", kind="ncss", chunk_days=366)],
        variable="chlor_a", canonical="chl", origin="satellite",
        resolution="1/24 deg (~4 km), daily L3 (cloud gaps)", record_start="1997-09-04", latency="~2 months",
        log=True, clim_years=(1998, 2020),
        description="ESA OC-CCI v6.0 daily merged chlorophyll-a via THREDDS NCSS (no login).",
        citation="Sathyendranath et al. (2019) Sensors 19:4285; ESA OC-CCI v6.0, Plymouth Marine Laboratory.",
    ),
    # --- Turbidity proxies -----------------------------------------------------------------
    "kd490_dineof": dict(
        endpoints=[_ep(CW, "noaacwNPPN20S3AkdSCIDINEOF2kmDaily", alt=True),
                   _ep(PW, "noaacwNPPN20S3AkdSCIDINEOF2kmDaily", alt=True)],
        variable="kd_490", canonical="kd490", origin="satellite",
        resolution="~2 km, daily, gap-filled (DINEOF)", record_start="2018-01-01", latency="~18 days",
        log=True, clim_years=None,
        description="Gap-filled Kd490 (DINEOF), VIIRS + OLCI merged.",
        citation="NOAA CoastWatch DINEOF gap-filled ocean colour.",
    ),
    "kd490_viirs_snpp_sq": dict(
        endpoints=[_ep(PIFSC, "noaa_snpp_kd490_daily", lon360=True, alt=True),
                   _ep(CW, "noaacwNPPVIIRSSQkd490Daily", alt=True)],
        variable="kd_490", canonical="kd490", origin="satellite",
        resolution="0.0375 deg (~4 km), daily L3", record_start="2012-01-02", latency="~2-3 weeks",
        log=True, clim_years=(2012, 2025),
        description="S-NPP VIIRS science-quality Kd490.",
        citation="NOAA CoastWatch/OSPO VIIRS ocean colour, NOAA STAR.",
    ),
    "kd490_occi_8day": dict(
        endpoints=[_ep(PIFSC, "esa-cci-kd-8d-v6-0", lon360=True)],
        variable="kd_490", canonical="kd490", origin="satellite",
        resolution="1/24 deg (~4 km), 8-day", record_start="1997-09-04", latency="~2 months",
        log=True, clim_years=(1998, 2020),
        description="ESA OC-CCI v6.0 Kd490, 8-day composites.",
        citation="Sathyendranath et al. (2019); ESA OC-CCI v6.0.",
    ),
    "kd490_occi_daily": dict(
        endpoints=[_ep(OCCI, "CCI_ALL-v6.0-DAILY", kind="ncss", chunk_days=366)],
        variable="kd_490", canonical="kd490", origin="satellite",
        resolution="1/24 deg (~4 km), daily L3", record_start="1997-09-04", latency="~2 months",
        log=True, clim_years=(1998, 2020),
        description="ESA OC-CCI v6.0 daily Kd490 via THREDDS NCSS.",
        citation="Sathyendranath et al. (2019); ESA OC-CCI v6.0.",
    ),
    "spm_dineof": dict(
        endpoints=[_ep(CW, "noaacwNPPN20S3AspmSCIDINEOF2kmDaily", alt=True),
                   _ep(PW, "noaacwNPPN20S3AspmSCIDINEOF2kmDaily", alt=True)],
        variable="spm", canonical="spm", origin="satellite",
        resolution="~2 km, daily, gap-filled (DINEOF)", record_start="2018-01-01", latency="~18 days",
        log=True, clim_years=None,
        description="Gap-filled suspended particulate matter (mg/L == g/m3), VIIRS + OLCI merged.",
        citation="NOAA CoastWatch DINEOF gap-filled ocean colour.",
    ),
}
for _k, _c in CATALOG.items():
    _c["dataset_id"] = _c["endpoints"][0]["id"]
    _c["server"] = _c["endpoints"][0]["base"]

# Recommended default per canonical variable (freshest reliable + long record for climatology)
DEFAULTS = {
    "sst": {"recent": "sst_blended", "climatology": "sst_coraltemp", "anomaly": "sst_anom_crw"},
    "chl": {"recent": "chl_olci_s3a", "gapfree": "chl_dineof", "climatology": "chl_occi_8day"},
    "kd490": {"recent": "kd490_dineof", "climatology": "kd490_occi_8day"},
    "spm": {"recent": "spm_dineof"},
}


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
class OpenDataError(RuntimeError):
    pass


class NoData(OpenDataError):
    pass


def _get(url: str, params: dict | None = None, timeout: float = 300, retries: int = 3) -> requests.Response:
    """GET with retries + backoff. 4xx -> OpenDataError immediately (NoData for ERDDAP 'no matching results')."""
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=(20, timeout), headers=UA)
            if r.status_code == 200:
                return r
            msg = re.sub(r"\s+", " ", r.text[:500])
            if r.status_code == 404 and "no matching results" in msg.lower():
                raise NoData(msg)
            if 400 <= r.status_code < 500:
                raise OpenDataError(f"HTTP {r.status_code} from {r.url[:250]}: {msg}")
            last = f"HTTP {r.status_code}: {msg[:200]}"
        except (requests.ConnectionError, requests.Timeout) as e:
            last = repr(e)[:200]
        time.sleep(2 * (i + 1))
    raise OpenDataError(f"Request failed after {retries} tries: {url[:200]} ({last})")


def _now() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None)


def _d(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_convert(None) if t.tzinfo else t


def _iso(x) -> str:
    return _d(x).strftime("%Y-%m-%dT%H:%M:%SZ")


def _haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def _cfg(key: str) -> dict:
    if key not in CATALOG:
        raise KeyError(f"Unknown dataset key {key!r}. Choose from: {', '.join(CATALOG)}")
    return CATALOG[key]


def _unit(c: dict) -> str:
    return c.get("unit") or CANONICAL.get(c["canonical"], ("", ""))[1]


# ----------------------------------------------------------------------------------------------
# Raw subset download (box x time) -> long DataFrame [time, lat, lon, value]
# ----------------------------------------------------------------------------------------------
def _erddap_box(ep: dict, var: str, t0, t1, lat0, lat1, lon0, lon1) -> pd.DataFrame:
    off = 360.0 if ep["lon360"] and lon0 < 0 else 0.0
    tsel = f"[({_iso(t0)}):1:({_iso(t1)})]" if _d(t0) != _d(t1) else f"[({_iso(t0)})]"
    q = (f"{var}{tsel}" + ("[(0.0)]" if ep["alt"] else "")
         + f"[({lat0:.4f}):1:({lat1:.4f})][({lon0 + off:.4f}):1:({lon1 + off:.4f})]")
    r = _get(f"{ep['base']}/griddap/{ep['id']}.csv?{q}")
    df = pd.read_csv(io.StringIO(r.text), skiprows=[1])
    df = df.rename(columns={var: "value", "latitude": "lat", "longitude": "lon"})
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["lon"] = np.where(df["lon"] > 180, df["lon"] - 360, df["lon"])
    return df[["time", "lat", "lon", "value"]]


def _ncss_box(ep: dict, var: str, t0, t1, lat0, lat1, lon0, lon1) -> pd.DataFrame:
    url = f"{ep['base']}/{ep['id']}"
    if lat1 - lat0 < 0.02 and lon1 - lon0 < 0.02:  # single pixel -> NCSS point mode (CSV, nearest cell)
        params = dict(var=var, latitude=round((lat0 + lat1) / 2, 5), longitude=round((lon0 + lon1) / 2, 5),
                      time_start=_iso(t0), time_end=_iso(t1), accept="csv")
        df = pd.read_csv(io.StringIO(_get(url, params=params).text))
        df.columns = [col.split("[")[0].strip() for col in df.columns]
        df = df.rename(columns={var: "value", "latitude": "lat", "longitude": "lon"})
    else:
        params = dict(var=var, north=lat1, south=lat0, west=lon0, east=lon1,
                      time_start=_iso(t0), time_end=_iso(t1), accept="netcdf")
        r = _get(url, params=params)
        tmp = cached_path(SOURCE, "tmp_" + cache_key(params), "nc")
        tmp.write_bytes(r.content)
        try:
            with xr.open_dataset(tmp) as ds:
                df = ds[var].load().to_dataframe(name="value").reset_index()
        finally:
            tmp.unlink(missing_ok=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["value"] = df["value"].where(df["value"] < 1e30)  # _FillValue 9.97e36 appears in CSV output
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    return df[["time", "lat", "lon", "value"]]


def _fetch_any(c: dict, t0, t1, lat0, lat1, lon0, lon1, chunked: bool = True) -> pd.DataFrame:
    """Try endpoints in order; each endpoint splits [t0, t1] into aligned chunks of chunk_days
    (aligned to 1970-01-01 so chunk cache files are reused across calls)."""
    errors = []
    for ep in c["endpoints"]:
        fn = _erddap_box if ep["kind"] == "erddap" else _ncss_box
        n = ep["chunk_days"] if chunked else 10 ** 6
        t0, t1 = _d(t0), _d(t1)
        epoch = pd.Timestamp("1970-01-01")
        k0, k1 = (t0 - epoch).days // n, (t1 - epoch).days // n
        parts = []
        try:
            for k in range(k0, k1 + 1):
                a = max(t0, epoch + pd.Timedelta(days=k * n))
                b = min(t1, epoch + pd.Timedelta(days=(k + 1) * n) - pd.Timedelta(seconds=1))
                parts.append(_cached_chunk(ep, c["variable"], fn, a, b, lat0, lat1, lon0, lon1))
            parts = [p for p in parts if len(p)]
            if not parts:
                return pd.DataFrame(columns=["time", "lat", "lon", "value"])
            # ERDDAP snaps chunk edges to the nearest time step -> adjacent chunks may share one step
            return pd.concat(parts, ignore_index=True).drop_duplicates(["time", "lat", "lon"])
        except OpenDataError as e:
            errors.append(f"{ep['base']} {ep['id']}: {str(e)[:300]}")
    raise OpenDataError("All endpoints failed:\n  " + "\n  ".join(errors))


def _cached_chunk(ep, var, fn, a, b, lat0, lat1, lon0, lon1) -> pd.DataFrame:
    """One request, cached. Chunks ending in the last 21 days (latency window) are re-fetched, but if the
    network fails the previous copy is used so the demo still runs offline."""
    fp = cached_path(SOURCE, cache_key("chunk", ep["base"], ep["id"], var, _iso(a), _iso(b), round(lat0, 4),
                                       round(lat1, 4), round(lon0, 4), round(lon1, 4)), "pkl")
    fresh = _d(b) > _now() - pd.Timedelta(days=21)
    if fp.exists() and not fresh:
        return pd.read_pickle(fp)
    try:
        df = fn(ep, var, a, b, lat0, lat1, lon0, lon1)
    except NoData:
        df = pd.DataFrame(columns=["time", "lat", "lon", "value"])
    except OpenDataError:
        if fp.exists():
            return pd.read_pickle(fp)
        raise
    df.to_pickle(fp)
    return df


@lru_cache(maxsize=64)
def _latest_cached(key: str, hour: str) -> pd.Timestamp:
    c = _cfg(key)
    errors = []
    for ep in c["endpoints"]:
        try:
            if ep["kind"] == "erddap":
                info = pd.read_csv(io.StringIO(_get(f"{ep['base']}/info/{ep['id']}/index.csv", timeout=60).text))
                row = info[(info["Variable Name"] == "NC_GLOBAL") & (info["Attribute Name"] == "time_coverage_end")]
                return _d(row["Value"].iloc[0])
            m = re.search(r"<end>([^<]+)</end>", _get(f"{ep['base']}/{ep['id']}/dataset.xml", timeout=60).text)
            return _d(m.group(1))
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:200])
    raise OpenDataError(f"Cannot get latest time for {key}: {errors}")


def latest_time(key: str) -> pd.Timestamp:
    """Latest time step on the (first reachable) server. Cached in memory for an hour; falls back to
    'today' if no server answers (so cached data can still be used offline)."""
    try:
        return _latest_cached(key, _now().strftime("%Y%m%d%H"))
    except OpenDataError:
        return _now().normalize()


def _clamp(c: dict, key: str, start, end):
    start = max(_d(start), pd.Timestamp(c["record_start"]))
    end = min(_d(end), latest_time(key) + pd.Timedelta(hours=12))
    if end < start:
        raise NoData(f"{key}: requested period is outside the record ({c['record_start']} .. {latest_time(key).date()})")
    return start, end


# ----------------------------------------------------------------------------------------------
# Time series with nearest-valid-pixel search
# ----------------------------------------------------------------------------------------------
def _choose_pixel(df: pd.DataFrame, lat: float, lon: float, min_frac: float = 0.5):
    """Nearest pixel whose valid fraction is >= min_frac * best fraction in the window.
    Returns (pix_lat, pix_lon, distance_km, valid_fraction)."""
    g = df.groupby(["lat", "lon"])["value"].agg(lambda s: s.notna().mean()).rename("frac").reset_index()
    if g.empty or g["frac"].max() == 0:
        raise NoData("No valid pixels in the search window for this period (land mask / clouds). "
                     "Increase window_deg or the period.")
    g["dist"] = _haversine_km(lat, lon, g["lat"].values, g["lon"].values)
    r = g[g["frac"] >= min_frac * g["frac"].max()].sort_values("dist").iloc[0]
    return float(r["lat"]), float(r["lon"]), float(r["dist"]), float(r["frac"])


def _attrs(c, key, **extra):
    ep = c["endpoints"][0]
    src = ("ERDDAP " if ep["kind"] == "erddap" else "THREDDS NCSS ") + ep["base"]
    return meta(src, c["dataset_id"], c["origin"], {c["canonical"]: _unit(c)}, key=key, variable=c["variable"],
                resolution=c["resolution"], citation=c.get("citation", ""), **extra)


def fetch_timeseries(key: str, lat: float, lon: float, start, end, window_deg: float = 0.1,
                     agg: str = "pixel") -> pd.DataFrame:
    """Point time series at (lat, lon) from a CATALOG dataset.

    Downloads a small (+-window_deg) box, then
      agg='pixel'  -> the nearest pixel that is valid most of the time (handles coastal land masks), or
      agg='median' -> median over all valid pixels in the window per time step.
    Period is clamped to [record_start, latest available]. Returns DataFrame with one canonical column,
    UTC-naive DatetimeIndex 'time'; attrs = meta(...) incl. pixel_lat, pixel_lon, pixel_dist_km, valid_fraction.
    """
    c = _cfg(key)
    start, end = _clamp(c, key, start, end)
    df = _fetch_any(c, start, end, lat - window_deg, lat + window_deg, lon - window_deg, lon + window_deg)
    df = df[(df["time"] >= start.normalize()) & (df["time"] <= end)]
    if df.empty:
        raise NoData(f"{key}: no time steps between {start.date()} and {end.date()}")
    name = c["canonical"]
    if agg == "median":
        s = df.groupby("time")["value"].median()
        plat, plon, dist, frac = lat, lon, 0.0, float(s.notna().mean())
    else:
        plat, plon, dist, frac = _choose_pixel(df, lat, lon)
        s = df[(df["lat"] == plat) & (df["lon"] == plon)].set_index("time")["value"]
    out = s.sort_index().astype(float).to_frame(name)
    out.index = pd.DatetimeIndex(out.index, name="time")
    out.attrs = _attrs(c, key, lat=lat, lon=lon, pixel_lat=plat, pixel_lon=plon, pixel_dist_km=round(dist, 2),
                       valid_fraction=round(frac, 3), agg=agg, window_deg=window_deg)
    return out


def fetch_field(key: str, bbox: tuple = BBOX_RO, date=None) -> xr.DataArray:
    """2-D map for one date over bbox=(lon_min, lat_min, lon_max, lat_max). date=None -> latest available.
    ERDDAP snaps to the nearest available time step. Returns DataArray (time, lat, lon), lat ascending."""
    c = _cfg(key)
    t = latest_time(key) if date is None else _d(date)
    t = min(t, latest_time(key))
    ep0 = c["endpoints"][0]
    t0, t1 = (t.normalize(), t.normalize() + pd.Timedelta(hours=23)) if ep0["kind"] == "ncss" else (t, t)
    lon0, lat0, lon1, lat1 = bbox
    df = _fetch_any(c, t0, t1, lat0, lat1, lon0, lon1, chunked=False)
    if df.empty:
        raise NoData(f"{key}: no field for {t.date()}")
    df = df[df["time"] == df["time"].iloc[0]]
    da = df.set_index(["time", "lat", "lon"])["value"].to_xarray().sortby("lat").astype(float)
    da.name = c["canonical"]
    da.attrs = _attrs(c, key, bbox=tuple(bbox), requested_date=str(t), actual_date=str(df["time"].iloc[0]),
                      long_name=CANONICAL.get(c["canonical"], (c["canonical"],))[0], units_str=_unit(c))
    return da


# ----------------------------------------------------------------------------------------------
# Climatology (per day of year, smoothed window) + anomalies
# ----------------------------------------------------------------------------------------------
def climatology(key: str, lat: float, lon: float, years: tuple[int, int] | None = None,
                window_days: int = 31, log: bool | None = None, window_deg: float = 0.1) -> pd.DataFrame:
    """Day-of-year climatology at a point: for every DOY 1..366 pool all values within +-window_days//2
    days (circular) over `years` -> mean, std, p10, p50, p90, n.

    Downloads stay small: the pixel is chosen once from a 92-day summer probe (nearest-valid search in a
    +-window_deg box), then only that single pixel is fetched for the reference period. Cached on disk.
    First call is slow for daily 30-yr records (CoralTemp 1991-2020 from PIFSC: ~5 min; OC-CCI 8-day
    1998-2020: ~30 s); afterwards instant.
    log=True (default for chl/kd490/spm): statistics in log10 space; 'mean' is the geometric mean,
    'std' is the std of log10(x), percentiles back-transformed.
    """
    c = _cfg(key)
    years = tuple(years or c.get("clim_years") or (int(c["record_start"][:4]) + 1, date.today().year - 1))
    log = c["log"] if log is None else log
    fp = cached_path(SOURCE, cache_key("clim", key, round(lat, 4), round(lon, 4), years, window_days, log,
                                       window_deg), "pkl")
    if fp.exists():
        return pd.read_pickle(fp)

    probe = fetch_timeseries(key, lat, lon, f"{years[1]}-06-01", f"{years[1]}-08-31", window_deg=window_deg)
    plat, plon = probe.attrs["pixel_lat"], probe.attrs["pixel_lon"]
    eps = 1e-3
    t0 = max(pd.Timestamp(f"{years[0]}-01-01"), pd.Timestamp(c["record_start"]))
    raw = _fetch_any(c, t0, pd.Timestamp(f"{years[1]}-12-31T23:59:59"), plat - eps, plat + eps, plon - eps, plon + eps)
    raw = raw.groupby("time")["value"].mean().dropna()
    if raw.empty:
        raise NoData(f"No valid data at pixel ({plat}, {plon}) for {years}")
    v = np.log10(raw.clip(lower=1e-6)).values if log else raw.values
    doy = raw.index.day_of_year.values
    half = window_days // 2
    rows = []
    for d in range(1, 367):
        dd = np.abs(doy - d)
        x = v[np.minimum(dd, 366 - dd) <= half]
        if len(x) < 5:
            rows.append((d, np.nan, np.nan, np.nan, np.nan, np.nan, len(x)))
            continue
        p10, p50, p90 = np.percentile(x, [10, 50, 90])
        rows.append((d, x.mean(), x.std(ddof=1), p10, p50, p90, len(x)))
    clim = pd.DataFrame(rows, columns=["doy", "mean", "std", "p10", "p50", "p90", "n"]).set_index("doy")
    if log:
        for k in ("mean", "p10", "p50", "p90"):
            clim[k] = 10 ** clim[k]
    clim.attrs = meta("ERDDAP/THREDDS", c["dataset_id"], "derived", {c["canonical"]: _unit(c)}, key=key,
                      variable=c["canonical"], lat=lat, lon=lon, pixel_lat=plat, pixel_lon=plon, years=years,
                      window_days=window_days, log10_stats=log, n_obs=int(raw.size),
                      record=(str(raw.index.min().date()), str(raw.index.max().date())),
                      note="std is in log10 units when log10_stats=True; mean is then the geometric mean")
    clim.to_pickle(fp)
    return clim


def anomalies(key: str, lat: float, lon: float, start, end, years=None, **kw) -> pd.DataFrame:
    """Observed series joined with its DOY climatology at the same pixel. Columns: value, clim_mean,
    clim_std, clim_p10, clim_p90, anomaly (linear vars) or anomaly_ratio (log vars), z, above_p90, below_p10."""
    clim = climatology(key, lat, lon, years=years, **kw)
    ts = fetch_timeseries(key, lat, lon, start, end, window_deg=kw.get("window_deg", 0.1))
    out = ts.rename(columns={ts.columns[0]: "value"})
    d = out.index.day_of_year
    for k in ("mean", "std", "p10", "p90"):
        out["clim_" + k] = clim[k].reindex(d).values
    if clim.attrs["log10_stats"]:
        out["anomaly_ratio"] = out["value"] / out["clim_mean"]
        out["z"] = (np.log10(out["value"].clip(lower=1e-6)) - np.log10(out["clim_mean"])) / out["clim_std"]
    else:
        out["anomaly"] = out["value"] - out["clim_mean"]
        out["z"] = out["anomaly"] / out["clim_std"]
    out["above_p90"] = out["value"] > out["clim_p90"]
    out["below_p10"] = out["value"] < out["clim_p10"]
    out.attrs = {**ts.attrs, "origin": "derived", "climatology": clim.attrs}
    return out


# ----------------------------------------------------------------------------------------------
# Open-Meteo: marine + weather, Danube discharge
# ----------------------------------------------------------------------------------------------
OM_MARINE = "https://marine-api.open-meteo.com/v1/marine"
OM_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OM_FORECAST = "https://api.open-meteo.com/v1/forecast"
OM_FLOOD = "https://flood-api.open-meteo.com/v1/flood"

_MARINE_VARS = {  # open-meteo name -> our column
    "wave_height": "wave_height", "wave_period": "wave_period", "wave_direction": "wave_dir",
    "sea_surface_temperature": "sst", "ocean_current_velocity": "current_speed",
    "ocean_current_direction": "current_dir", "sea_level_height_msl": "ssh",
}
_WEATHER_VARS = {"temperature_2m": "air_temp", "wind_speed_10m": "wind_speed", "wind_direction_10m": "wind_dir",
                 "precipitation": "precip", "shortwave_radiation": "sw_rad"}


def _om(url: str, params: dict, refresh: bool) -> dict:
    """Open-Meteo GET with on-disk cache; refresh=True re-fetches but falls back to cache offline."""
    fp = cached_path(SOURCE, cache_key("om", url, params), "json")
    if fp.exists() and not refresh:
        return json.loads(fp.read_text())
    try:
        r = _get(url, params=params, timeout=120)
    except OpenDataError:
        if fp.exists():
            return json.loads(fp.read_text())
        raise
    js = r.json()
    if js.get("error"):
        raise OpenDataError(f"Open-Meteo: {js.get('reason')}")
    fp.write_text(r.text)
    return js


def _om_frame(js: dict, block: str, mapping: dict) -> pd.DataFrame:
    h = js.get(block) or {}
    if not h:
        return pd.DataFrame()
    df = pd.DataFrame({mapping.get(k, k): v for k, v in h.items() if k != "time"},
                      index=pd.DatetimeIndex(pd.to_datetime(h["time"]), name="time"))
    return df.apply(pd.to_numeric, errors="coerce")


def marine_weather(lat: float, lon: float, start, end, freq: str = "hourly") -> pd.DataFrame:
    """Open-Meteo marine (waves, SST, currents, sea level: MODEL, MeteoFrance MFWAM/SMOC, DWD EWAM, ECMWF WAM)
    + weather (wind 10 m, air temperature, precipitation, shortwave: ERA5 REANALYSIS up to today via the
    archive API, Open-Meteo forecast after today, max +15 d).

    History at the Romanian coast: waves from 2021-10, currents 2022-01, SST/SSH 2022-11; weather from 1940.
    freq='hourly' or 'daily' (daily means; wave_height also gets wave_height_max; directions dropped).
    Columns: wave_height, wave_period, wave_dir, sst, current_speed, current_dir, current_u, current_v, ssh,
             air_temp, wind_speed, wind_dir, wind_u, wind_v, precip, sw_rad  (SI units, speeds in m/s).
    attrs['column_origin'] says 'model' vs 'reanalysis' per column; attrs['marine_cell'] is the snapped grid cell.
    """
    start, end = _d(start).normalize(), _d(end).normalize()
    today = _now().normalize()
    refresh = end >= today - pd.Timedelta(days=7)
    base = dict(latitude=lat, longitude=lon, timezone="GMT", wind_speed_unit="ms")
    m = _om(OM_MARINE, {**base, "hourly": ",".join(_MARINE_VARS), "cell_selection": "sea",
                        "start_date": start.date().isoformat(), "end_date": end.date().isoformat()}, refresh)
    marine = _om_frame(m, "hourly", _MARINE_VARS)

    wparts, wsrc = [], []
    if start <= today:
        w = _om(OM_ARCHIVE, {**base, "hourly": ",".join(_WEATHER_VARS), "start_date": start.date().isoformat(),
                             "end_date": min(end, today).date().isoformat()}, refresh)
        wparts.append(_om_frame(w, "hourly", _WEATHER_VARS))
        wsrc.append("ERA5 via Open-Meteo archive (recent days ERA5T/IFS-filled)")
    if end > today:
        f = _om(OM_FORECAST, {**base, "hourly": ",".join(_WEATHER_VARS),
                              "start_date": max(start, today + pd.Timedelta(days=1)).date().isoformat(),
                              "end_date": min(end, today + pd.Timedelta(days=15)).date().isoformat()}, True)
        wparts.append(_om_frame(f, "hourly", _WEATHER_VARS))
        wsrc.append("Open-Meteo forecast (best match)")
    weather = pd.concat(wparts) if wparts else pd.DataFrame()
    weather = weather[~weather.index.duplicated()]
    df = marine.join(weather, how="outer")

    if "current_speed" in df:
        rad = np.deg2rad(df["current_dir"])  # oceanographic convention: direction the current flows TO
        df["current_u"], df["current_v"] = df["current_speed"] * np.sin(rad), df["current_speed"] * np.cos(rad)
    if "wind_speed" in df:
        rad = np.deg2rad(df["wind_dir"])  # meteorological convention: direction the wind blows FROM
        df["wind_u"], df["wind_v"] = -df["wind_speed"] * np.sin(rad), -df["wind_speed"] * np.cos(rad)
    if freq == "daily":
        mx = df["wave_height"].resample("D").max().rename("wave_height_max") if "wave_height" in df else None
        df = df.drop(columns=[k for k in df if k.endswith("_dir")]).resample("D").mean()
        if mx is not None:
            df["wave_height_max"] = mx
    units = {"wave_height": "m", "wave_height_max": "m", "wave_period": "s", "wave_dir": "deg", "sst": "°C",
             "current_speed": "m/s", "current_dir": "deg (towards)", "current_u": "m/s", "current_v": "m/s",
             "ssh": "m", "air_temp": "°C", "wind_speed": "m/s", "wind_dir": "deg (from)", "wind_u": "m/s",
             "wind_v": "m/s", "precip": "mm/h", "sw_rad": "W/m²"}
    marine_cols = set(_MARINE_VARS.values()) | {"current_u", "current_v", "wave_height_max"}
    df.attrs = meta("Open-Meteo", "marine-api (MFWAM/SMOC/EWAM/ECMWF-WAM) + archive-api (ERA5)", "model",
                    {k: units.get(k, "") for k in df.columns}, lat=lat, lon=lon,
                    marine_cell=(m.get("latitude"), m.get("longitude")),
                    column_origin={k: ("model" if k in marine_cols else "reanalysis") for k in df.columns},
                    weather_source=" + ".join(wsrc), freq=freq,
                    citation="Open-Meteo.com (CC BY 4.0); ERA5 (Hersbach et al. 2020); "
                             "Météo-France MFWAM/SMOC via Copernicus Marine.")
    return df


def danube_discharge(start, end, lat: float = DANUBE_POINT[0], lon: float = DANUBE_POINT[1],
                     ensemble_stats: bool = False) -> pd.DataFrame:
    """Daily Danube discharge (m3/s), GloFAS v4 via the Open-Meteo Flood API (no key).
    Record 1997-01-01 -> today (cell is null before 1997), plus ~30-day forecast for end > today.
    Default cell = Danube main channel at Ceatal Izmail/Tulcea = total flow entering the delta.
    ensemble_stats=True adds forecast ensemble discharge_median / _p25 / _p75."""
    start, end = max(_d(start).normalize(), pd.Timestamp("1997-01-01")), _d(end).normalize()
    today = _now().normalize()
    daily = "river_discharge" + (",river_discharge_median,river_discharge_p25,river_discharge_p75"
                                 if ensemble_stats else "")
    js = _om(OM_FLOOD, dict(latitude=lat, longitude=lon, daily=daily, start_date=start.date().isoformat(),
                            end_date=end.date().isoformat()), end >= today - pd.Timedelta(days=7))
    df = _om_frame(js, "daily", {"river_discharge": "discharge", "river_discharge_median": "discharge_median",
                                 "river_discharge_p25": "discharge_p25", "river_discharge_p75": "discharge_p75"})
    df["is_forecast"] = df.index > today
    df.attrs = meta("Open-Meteo Flood API", "GloFAS v4 (seamless: reanalysis + forecast)", "model",
                    {k: "m³/s" for k in df.columns if k.startswith("discharge")}, lat=lat, lon=lon,
                    grid_cell=(js.get("latitude"), js.get("longitude")),
                    citation="Open-Meteo.com (CC BY 4.0); GloFAS, Copernicus Emergency Management Service.")
    return df


# ----------------------------------------------------------------------------------------------
if __name__ == "__main__":  # smoke test:  cd src && python -m marinekit.sources.open_data [--clim]
    import sys

    pd.set_option("display.width", 160)
    lat, lon = STATIONS["Constanta"]
    today = _now().normalize()
    for key, days in [("sst_blended", 60), ("sst_coraltemp", 60), ("sst_anom_crw", 30), ("chl_olci_s3a", 60),
                      ("chl_dineof", 60), ("kd490_dineof", 60), ("spm_dineof", 60), ("chl_occi_8day", 150),
                      ("chl_occi_daily", 120)]:
        try:
            t = time.time()
            ts = fetch_timeseries(key, lat, lon, today - pd.Timedelta(days=days), today)
            a = ts.attrs
            last = ts.dropna().iloc[-1]
            print(f"[{key:16s}] latest={latest_time(key).date()} n={len(ts)} valid={int(ts.iloc[:, 0].notna().sum())} "
                  f"pixel=({a['pixel_lat']:.3f},{a['pixel_lon']:.3f}) {a['pixel_dist_km']} km  "
                  f"last valid {last.name.date()}={last.iloc[0]:.3f}  ({time.time() - t:.0f}s)")
        except Exception as e:  # noqa: BLE001
            print(f"[{key}] FAILED: {e}")
    for key, dt in [("sst_blended", today - pd.Timedelta(days=2)), ("chl_dineof", None), ("chl_occi_daily", "2026-09-27")]:
        try:
            f = fetch_field(key, BBOX_RO, dt)
            print(f"[field {key}] {f.attrs['actual_date']} {dict(f.sizes)} valid={int(f.count())} "
                  f"median={float(f.median()):.2f}")
        except Exception as e:  # noqa: BLE001
            print(f"[field {key}] FAILED: {e}")
    if "--clim" in sys.argv:
        for key in ("chl_occi_8day", "sst_coraltemp"):
            t = time.time()
            cl = climatology(key, lat, lon)
            print(f"[climatology {key} {cl.attrs['years']}] n_obs={cl.attrs['n_obs']} ({time.time() - t:.0f}s) "
                  f"DOY 327: {cl.loc[327].round(3).to_dict()}")
            lt = latest_time(key)
            an = anomalies(key, lat, lon, lt - pd.Timedelta(days=40), lt)
            print(an.dropna().tail(3).round(3).to_string())
    mw = marine_weather(lat, lon, today - pd.Timedelta(days=3), today + pd.Timedelta(days=2), freq="daily")
    print("\n[marine_weather daily] cell", mw.attrs["marine_cell"])
    print(mw[["wave_height", "wave_height_max", "sst", "current_speed", "ssh", "air_temp", "wind_speed"]].round(2))
    dq = danube_discharge(today - pd.Timedelta(days=10), today + pd.Timedelta(days=10))
    print("\n[danube_discharge]\n", dq.iloc[::4])
