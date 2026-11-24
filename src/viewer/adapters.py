"""Data adapters for the viewer.

The viewer talks only to this module. Each function prefers the real workstream module when it exists
(`marinekit.datahub`, `marinekit.indicators`, `viewer.vectorviz`, the v2 files in data/zones/) and otherwise
falls back to a thin placeholder that calls the verified source modules directly, or returns "no data".
Everything is cached with st.cache_data so a warm start is fast and works offline from data/cache.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import re
from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from marinekit.sources import BBOX_RO, ROOT, STATIONS

log = logging.getLogger("viewer")
ZONES = ROOT / "data" / "zones"
DOCS = ROOT / "docs"
O2_MMOL_TO_MGL = 0.032  # 1 mmol/m3 O2 = 32 ug/L


# ------------------------------------------------------------------------------------------ module lookup
def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _mod(name: str):
    if not has_module(name):
        return None
    try:
        return importlib.import_module(name)
    except Exception as ex:  # a module being written right now may not import yet
        log.warning("cannot import %s: %s", name, ex)
        return None


def status_of_modules() -> dict:
    return {
        "marinekit.datahub": has_module("marinekit.datahub"),
        "marinekit.indicators": has_module("marinekit.indicators"),
        "viewer.vectorviz": has_module("viewer.vectorviz"),
        "zones v2 (overlap_summer/winter)": (ZONES / "overlap_summer.geojson").exists(),
    }


from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout  # noqa: E402

_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="viewer-fetch")


class SlowSource(RuntimeError):
    """A download took longer than the viewer waits; it keeps running in the background and fills the cache."""


def timed(fn, *args, timeout: float = 25, **kw):
    fut = _POOL.submit(fn, *args, **kw)
    try:
        return fut.result(timeout=timeout)
    except _FutTimeout:
        raise SlowSource(f"{getattr(fn, '__name__', fn)} still downloading after {timeout:.0f} s")


def today() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()


# ------------------------------------------------------------------------------------------ variables
# One entry per variable the panel can chart. Each source: (catalog key, native variable, origin, factor)
VARIABLES = {
    "sst": dict(label="Sea surface temperature", unit="°C", canon="sst",
                sources=[("sst_l4_nrt", "analysed_sst", "satellite", 1.0), ("phy_temp", "thetao", "model", 1.0)],
                insitu=("temp", 1.0), clim=("sst_l4_nrt", "sst"),
                long=("sst_l4_rep", None, "1982-01-01", "2026-12-31", "satellite")),
    "chl": dict(label="Chlorophyll-a", unit="mg/m³", canon="chl", log=True,
                sources=[("sat_chl_l4_nrt", "CHL", "satellite", 1.0), ("bgc_chl", "chl", "model", 1.0)],
                insitu=("chl", 1.0), clim=("sat_chl_l4_nrt", "chl"),
                long=("sat_chl_l4_my", "CHL", "1998-01-01", "2022-12-31T23:59:59", "satellite")),
    "o2": dict(label="Dissolved oxygen (surface)", unit="mg/L", canon="o2",
               sources=[("bgc_o2", "o2", "model", O2_MMOL_TO_MGL)],
               insitu=("do", 1.0), clim=("bgc_o2", "o2"), clim_factor=O2_MMOL_TO_MGL,
               long=("rea_bgc_o2", "o2", "1993-01-01", "2022-12-31T23:59:59", "reanalysis"), long_factor=O2_MMOL_TO_MGL),
    "o2_bottom": dict(label="Dissolved oxygen (near the seabed)", unit="mg/L", canon="o2_bottom",
                      sources=[("bgc_o2", "o2b", "model", O2_MMOL_TO_MGL)],
                      insitu=None, clim=("bgc_o2", "o2_bottom"), clim_factor=O2_MMOL_TO_MGL,
                      long=("rea_bgc_o2", "o2b", "1993-01-01", "2022-12-31T23:59:59", "reanalysis"),
                      long_factor=O2_MMOL_TO_MGL),
    "sal": dict(label="Salinity", unit="PSU", canon="sal",
                sources=[("phy_sal", "so", "model", 1.0)], insitu=("sal", 1.0), clim=("phy_sal", "sal"),
                long=("rea_phy_sal", "so", "1993-01-01", "2022-12-31T23:59:59", "reanalysis")),
    "kd490": dict(label="Light attenuation Kd490 (higher = murkier)", unit="1/m", canon="kd490", log=True,
                  sources=[("sat_kd490_nrt", "KD490", "satellite", 1.0)], insitu=None, clim=("sat_kd490_nrt", "kd490"),
                  long=("sat_kd490_my", "KD490", "1998-01-01", "2022-12-31T23:59:59", "satellite")),
}

# in-situ trust register (SHORTLIST section 4)
UNTRUSTED = {
    "EUXRoCB01": "Coastal buoy, new (Sep 2026): under QC. O2 units unclear, salinity 7.5.",
    "EUXRoCB02": "Coastal buoy, new (Sep 2026): under QC. O2 units unclear, O2 saturation 3.6 %.",
    "EUXRoCB03": "Coastal buoy, new (Sep 2026): under QC.",
    "EUXRoCB01AWAC": "Coastal buoy wave sensor, new (Sep 2026): under QC.",
    "EUXRoCB02AWAC": "Coastal buoy wave sensor, new (Sep 2026): under QC.",
    "EUXRoCB03AWAC": "Coastal buoy wave sensor, new (Sep 2026): under QC.",
}
SHORE = {
    "15480": "Shore station (Constanța): about 3.5 °C colder than open water. Air and harbour context only.",
    "15360": "Shore station (Sulina): air and harbour context only.",
    "15499": "Shore station (Mangalia): air and harbour context only.",
    "15428": "Shore station (Gura Portiței): air and harbour context only.",
}
TRUSTED = {"EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo02", "EUXRo03"}


def platform_trust(pid: str) -> tuple[str, str]:
    pid = str(pid)
    if pid in UNTRUSTED:
        return "under_qc", UNTRUSTED[pid]
    if pid in SHORE:
        return "context", SHORE[pid]
    if pid in TRUSTED:
        return "good", "Offshore buoy, checked against the formula for O2 saturation (r 0.98)."
    return "not_assessed", "Not yet assessed by the team."


# ------------------------------------------------------------------------------------------ in-situ platforms
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def platforms() -> pd.DataFrame:
    from marinekit.sources import emodnet_insitu as ei
    try:
        p = ei.list_platforms()
    except Exception as ex:
        log.warning("list_platforms: %s", ex)
        return pd.DataFrame(columns=["id", "name", "type", "lat", "lon", "time_end", "canonical", "trust", "trust_note"])
    p = p.drop_duplicates("id").copy()
    tr = p["id"].map(platform_trust)
    p["trust"] = [t[0] for t in tr]
    p["trust_note"] = [t[1] for t in tr]
    p["canonical"] = p["canonical"].map(lambda c: list(c) if c is not None else [])
    p["recent"] = p["time_end"] > today() - pd.Timedelta(days=30)
    return p.reset_index(drop=True)


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def nearest_platforms(lat, lon, canon: str, max_km: float = 60, n: int = 2) -> pd.DataFrame:
    p = platforms()
    if p.empty:
        return p
    p = p[p["canonical"].map(lambda c: canon in c or (canon == "do" and "o2" in c))]
    p = p[(p.trust != "context") & p.time_end.notna()]
    p = p[p.time_end > today() - pd.Timedelta(days=400)]
    if p.empty:
        return p
    p = p.assign(dist_km=_haversine_km(lat, lon, p.lat.to_numpy(), p.lon.to_numpy()))
    return p[p.dist_km <= max_km].sort_values(["dist_km"]).head(n)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def insitu_series(pid: str, canon: str, start: str, end: str) -> pd.Series | None:
    from marinekit.sources import emodnet_insitu as ei
    try:
        df = timed(ei.fetch_platform, pid, pd.Timestamp(start), pd.Timestamp(end), [canon], resample="1D", timeout=20)
    except SlowSource:
        raise
    except Exception as ex:
        log.info("insitu %s %s: %s", pid, canon, ex)
        return None
    if canon not in df:
        return None
    s = df[canon].astype(float)
    s = s.where(s.abs() > 1e-20)  # denormal fills leak through some ERDDAP feeds
    s = s.dropna()
    s.attrs = {k: v for k, v in df.attrs.items() if isinstance(v, (str, int, float, list))}
    return s if len(s) else None


# ------------------------------------------------------------------------------------------ point series
def _attrs_small(a: dict) -> dict:
    keep = ("source", "dataset", "origin", "product", "key", "grid_lat", "grid_lon", "distance_km", "depth_m", "citation",
            "platform", "platform_id", "lat", "lon", "notes", "qc_kept", "years")
    return {k: a.get(k) for k in keep if a.get(k) is not None}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cop_series(key, native, lat, lon, start, end, factor=1.0):
    from marinekit.sources import copernicus as cp
    try:
        df = timed(cp.fetch_timeseries, key, lat, lon, start, end, variables=[native] if native else None, timeout=45)
    except SlowSource:
        raise
    except Exception as ex:
        log.info("copernicus %s %s: %s", key, native, ex)
        return None
    if df.empty:
        return None
    col = df.columns[0] if native is None else next((c for c in df.columns if c != "time"), df.columns[0])
    if native is not None:
        from marinekit.sources.copernicus import CATALOG
        col = CATALOG[key]["vars"].get(native, col)
    s = df[col].astype(float) * factor
    if len(s) > 1 and pd.Series(s.index).diff().min() < pd.Timedelta(hours=23):
        s = s.resample("1D").mean()
    s = s.dropna()
    s.attrs = _attrs_small(df.attrs)
    return s


def _window(days_back=365, days_fwd=5):
    t = today()
    return str((t - pd.Timedelta(days=days_back)).date()), str((t + pd.Timedelta(days=days_fwd)).date())


def series_for(var: str, lat: float, lon: float, days_back: int = 365) -> list[dict]:
    """All sources for one variable at a point: [{label, origin, dataset, series, unit, meta, note}]."""
    v = VARIABLES[var]
    out = []
    hub = _mod("marinekit.datahub")
    start, end = _window(days_back)
    if hub is not None and hasattr(hub, "compare_sources"):
        try:
            got = _hub_compare(var, round(lat, 4), round(lon, 4), str(today().date()))
            if got:
                return got
        except SlowSource as ex:
            return [dict(label="All sources", origin="", dataset="", series=None, unit=v["unit"], meta={},
                         note=f"still downloading ({ex}); reopen this view in a minute")]
        except Exception as ex:
            log.info("datahub.compare_sources failed, using placeholder: %s", ex)
    for key, native, origin, factor in v["sources"]:
        e_end = end if origin == "model" else str(today().date())
        try:
            s = _cop_series(key, native, round(lat, 3), round(lon, 3), start, e_end, factor)
        except SlowSource as ex:
            out.append(dict(label=f"{origin.capitalize()}: {key}", origin=origin, dataset=key, series=None, unit=v["unit"],
                            meta={}, note=f"still downloading ({ex}); reopen this view in a minute"))
            continue
        if s is not None:
            note = ""
            if key == "bgc_chl":
                note = "Model chlorophyll disagrees with its own reanalysis; shown for comparison only."
            if var == "o2_bottom":
                note = "Model systems disagree by about 2 mg/L near the seabed; indicative only."
            out.append(dict(label=f"{origin.capitalize()}: {key}", origin=origin, dataset=s.attrs.get("dataset", key),
                            series=s, unit=v["unit"], meta=s.attrs, note=note))
    if v.get("insitu"):
        canon, factor = v["insitu"]
        istart = str((today() - pd.Timedelta(days=min(days_back, 120))).date())
        for _, p in nearest_platforms(lat, lon, canon).iterrows():
            try:
                s = insitu_series(p.id, canon, istart, str(today().date()))
            except SlowSource as ex:
                out.append(dict(label=f"Measured: buoy {p.id}", origin="in-situ", dataset=p.id, series=None,
                                unit=v["unit"], meta={}, note="still downloading; reopen this view in a minute"))
                continue
            if s is None:
                continue
            s = s * factor
            trust, why = p.trust, p.trust_note
            meta = {**s.attrs, "platform": p.id, "distance_km": round(float(p.dist_km), 1), "trust": trust}
            out.append(dict(label=f"Measured: buoy {p.id}", origin="in-situ", dataset=f"EMODnet Physics {p.id}",
                            series=s, unit=v["unit"], meta=meta,
                            note=(why if trust == "under_qc" else ""), untrusted=trust == "under_qc"))
    return out


def ds_names(ds) -> str:
    """datahub 'datasets' attr: list of dicts {dataset, role, ...}, list of str, or str."""
    if isinstance(ds, (list, tuple)):
        out = []
        for d in ds:
            if isinstance(d, dict):
                out.append(d.get("dataset", "") + (f" ({d['role']})" if d.get("role") else ""))
            else:
                out.append(str(d))
        return ", ".join(dict.fromkeys(x for x in out if x))
    return str(ds or "")


def hub_window(day=None) -> tuple[str, str]:
    """The datahub's canonical window (same as the cards and the preload script, so the cache is shared)."""
    hub = _mod("marinekit.datahub")
    if hub is not None and hasattr(hub, "card_window"):
        a, b = hub.card_window(day or today())
        return str(pd.Timestamp(a).date()), str(pd.Timestamp(b).date())
    return _window(366, 10)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _hub_compare(var, lat, lon, day):
    hub = importlib.import_module("marinekit.datahub")
    v = VARIABLES[var]
    start, end = hub_window(day)
    df = timed(hub.compare_sources, v["canon"], lat, lon, start, end, timeout=90)
    out = []
    srcs = df.attrs.get("sources", {})
    for col in df.columns:
        m = dict(srcs.get(col, {}))
        s = df[col].dropna().astype(float)
        if s.empty:
            continue
        o = str(m.get("origin") or "")
        trust = str(m.get("trust") or "")
        ds = ds_names(m.get("datasets")) or col
        notes = m.get("notes")
        notes = "; ".join(map(str, notes)) if isinstance(notes, (list, tuple)) else str(notes or "")
        if trust == "untrusted":
            notes = ("Not trusted yet (under QC). " + notes).strip()
        elif trust == "indicative":
            notes = ("Indicative only. " + notes).strip()
        meta = {"dataset": ds, "distance_km": m.get("distance_km"), "platform": m.get("platform"), "trust": trust}
        out.append(dict(label=str(m.get("label") or col), origin=o, dataset=ds, series=s,
                        unit=m.get("unit") or v["unit"], meta=meta, note=notes, untrusted=trust == "untrusted",
                        source_id=col))
    failed = df.attrs.get("failed") or {}
    for k, why in failed.items():
        if "DataUnavailable" in why or "no " in why.lower():
            continue
        out.append(dict(label=k, origin="", dataset=k, series=None, unit=v["unit"], meta={}, note=f"failed: {why[:120]}"))
    return out


def _normalise_hub(res, v) -> list[dict]:
    """Accept the likely shapes of datahub.compare_sources: list of DataFrames/Series, dict name -> frame, or a wide frame."""
    items = []
    if isinstance(res, pd.DataFrame) and not res.empty:
        orig = res.attrs.get("origins", {})
        for c in res.columns:
            items.append((c, res[c], {**res.attrs, "origin": orig.get(c, res.attrs.get("origin", ""))}))
    elif isinstance(res, dict):
        for k, x in res.items():
            if isinstance(x, pd.DataFrame):
                items.append((k, x.iloc[:, 0], x.attrs))
            elif isinstance(x, pd.Series):
                items.append((k, x, x.attrs))
    elif isinstance(res, (list, tuple)):
        for x in res:
            if isinstance(x, dict) and "series" in x:
                items.append((x.get("label", "?"), x["series"], {**x.get("meta", {}), "origin": x.get("origin", "")}))
            elif isinstance(x, (pd.DataFrame, pd.Series)):
                s = x.iloc[:, 0] if isinstance(x, pd.DataFrame) else x
                items.append((x.attrs.get("dataset", s.name), s, x.attrs))
    out = []
    for name, s, a in items:
        o = str(a.get("origin") or a.get("evidence") or "").lower()
        out.append(dict(label=str(name), origin=o, dataset=a.get("dataset", name), series=s.dropna().astype(float),
                        unit=a.get("units", v["unit"]) if isinstance(a.get("units"), str) else v["unit"], meta=a, note=""))
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def climatology(var: str, lat: float, lon: float) -> pd.DataFrame | None:
    v = VARIABLES[var]
    hub = _mod("marinekit.datahub")
    if hub is not None and hasattr(hub, "get_climatology"):
        try:
            c = timed(hub.get_climatology, v["canon"], lat, lon, timeout=60)
            if c is not None and len(c) and "mean" in c:
                c = c.copy()
                if str(c.attrs.get("space")) == "log10":
                    # datahub: mean = geometric mean (linear units), percentiles linear, std = sd of log10
                    c["log_mean"], c["log_std"] = np.log10(c["mean"]), c["std"]
                    c["std"] = np.nan
                yrs = c.attrs.get("years")
                if isinstance(yrs, str):
                    yrs = [int(x) for x in re.findall(r"\d{4}", yrs)][:2] or None
                c.attrs = {**c.attrs, "years": yrs}
                return c
        except SlowSource:
            raise
        except Exception as ex:
            log.info("datahub.get_climatology failed: %s", ex)
    from marinekit.sources import copernicus as cp
    key, canon = v["clim"]
    try:
        c = timed(cp.climatology, key, round(lat, 3), round(lon, 3), canon, timeout=60)
    except SlowSource:
        raise
    except Exception as ex:
        log.info("climatology %s: %s", key, ex)
        return None
    f = v.get("clim_factor", 1.0)
    c = c.copy()
    for col in ("mean", "std", "p10", "p50", "p90"):
        c[col] = c[col] * f
    c.attrs = {k: c.attrs.get(k) for k in ("dataset", "years", "window_days", "smooth_days", "n_years", "origin")}
    return c


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def long_series(var: str, lat: float, lon: float) -> pd.Series | None:
    v = VARIABLES[var]
    hub = _mod("marinekit.datahub")
    if hub is not None and hasattr(hub, "get_series"):
        src, start = LONG_HUB.get(var, ("auto", "1993-01-01"))
        try:
            df = timed(hub.get_series, v["canon"], lat, lon, start, str(today().date()), source=src, timeout=90)
            s = df.iloc[:, 0].dropna().astype(float)
            s.attrs = {"origin": df.attrs.get("origin", ""), "dataset": ds_names(df.attrs.get("datasets")),
                       "label": df.attrs.get("label", ""), "distance_km": df.attrs.get("distance_km")}
            if len(s):
                return s
        except SlowSource:
            raise
        except Exception as ex:
            log.info("datahub long series %s: %s", var, ex)
    key, native, start, end, origin = v["long"]
    s = _cop_series(key, native, round(lat, 3), round(lon, 3), start, end, v.get("long_factor", 1.0))
    if s is None:
        return None
    s.attrs["origin"] = origin
    return s


LONG_HUB = {"sst": ("satellite", "1982-01-01"), "chl": ("satellite", "1998-01-01"), "kd490": ("satellite", "1998-01-01"),
            "o2": ("model", "1993-01-01"), "o2_bottom": ("model", "1993-01-01"), "sal": ("model", "1993-01-01")}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def hub_obs_model(var: str, lat: float, lon: float, day: str) -> dict | None:
    """datahub.obs_vs_model plus both daily series for the scatter plot."""
    hub = _mod("marinekit.datahub")
    if hub is None or not hasattr(hub, "obs_vs_model"):
        return None
    v = VARIABLES[var]
    start, end = hub_window(day)
    end = str(min(pd.Timestamp(end), today()).date())
    try:
        r = timed(hub.obs_vs_model, v["canon"], lat, lon, start, end, timeout=90)
    except SlowSource:
        raise
    except Exception as ex:
        log.info("obs_vs_model %s: %s", var, ex)
        return None
    try:
        o = hub.get_series(v["canon"], r["lat"], r["lon"], start, end, source=r["obs_source"]).iloc[:, 0]
        m = hub.get_series(v["canon"], r["lat"], r["lon"], start, end, source=r["model_source"]).iloc[:, 0]
        j = pd.concat([o.rename("obs"), m.rename("mod")], axis=1).dropna()
        r["joined"] = j[j.index <= today()]
    except Exception as ex:
        log.info("obs_vs_model series: %s", ex)
        r["joined"] = None
    return r


def doy365(idx: pd.DatetimeIndex) -> np.ndarray:
    doy = idx.day_of_year.to_numpy().copy()
    doy[idx.is_leap_year & (doy > 59)] -= 1
    return doy


def annual_trend(s: pd.Series, min_days: int = 300) -> dict | None:
    """Annual means and an OLS trend with a 95 % confidence interval (per decade)."""
    from scipy import stats
    s = s[s.index.year < today().year]  # the current year is incomplete (no winter yet): leave it out
    g = s.groupby(s.index.year)
    ann = g.mean()[g.count() >= min_days]
    if len(ann) < 8:
        return None
    x, y = ann.index.to_numpy(float), ann.to_numpy(float)
    r = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, len(x) - 2)
    return dict(annual=ann, slope_decade=r.slope * 10, ci_decade=tcrit * r.stderr * 10, p=r.pvalue, n=len(x),
                intercept=r.intercept, slope=r.slope, years=(int(x.min()), int(x.max())))


def obs_vs_model(obs: pd.Series, mod: pd.Series) -> dict | None:
    j = pd.concat([obs.rename("obs"), mod.rename("mod")], axis=1).dropna()
    if len(j) < 5:
        return None
    d = j["mod"] - j["obs"]
    return dict(n=len(j), bias=float(d.mean()), rmse=float(np.sqrt((d ** 2).mean())),
                r=float(np.corrcoef(j["obs"], j["mod"])[0, 1]), start=j.index.min(), end=j.index.max(), joined=j)


# ------------------------------------------------------------------------------------------ gridded layers
LAYERS = {
    "sst": dict(title="Sea surface temperature", key="sst_l4_nrt_hr", var="analysed_sst", unit="°C", origin="satellite",
                cmap="cmo.thermal", fallback_key="sst_l4_nrt", tile_offset=273.15),
    "sst_anom": dict(title="Sea temperature anomaly", key="sst_anom_nrt", var="sst_anomaly", unit="°C",
                     origin="satellite", cmap="cmo.balance", diverging=True),
    "chl": dict(title="Chlorophyll-a (algae)", key="sat_chl_l4_nrt", var="CHL", unit="mg/m³", origin="satellite",
                cmap="cmo.algae", log=True),
    "kd490": dict(title="Water clarity (Kd490)", key="sat_kd490_nrt", var="KD490", unit="1/m", origin="satellite",
                  cmap="cmo.deep", log=True, note="Gaps are clouds: this satellite layer is not gap-filled."),
    "model_temp": dict(title="Model water temperature (surface)", key="phy_temp", var="thetao", unit="°C",
                       origin="model", cmap="cmo.thermal"),
    "o2": dict(title="Model oxygen (surface)", key="bgc_o2", var="o2", unit="mg/L", origin="model", cmap="cmo.oxy",
               factor=O2_MMOL_TO_MGL),
    "o2_bottom": dict(title="Model oxygen near the seabed", key="bgc_o2", var="o2b", unit="mg/L", origin="model",
                      cmap="cmo.oxy", factor=O2_MMOL_TO_MGL, vrange=(0, 12),
                      note="Below about 150 m the Black Sea has no oxygen at all (natural, permanent). Red offshore is "
                           "that deep water, not pollution. Model bottom oxygen near the coast is indicative only."),
}


def colormap(name: str):
    """A matplotlib colormap. 'cmo.<name>' = the cmocean ramp (exact stops, taken from plotly's copy of cmocean)."""
    import matplotlib
    if name.startswith("cmo."):
        from matplotlib.colors import LinearSegmentedColormap
        from plotly.colors import cmocean
        stops = getattr(cmocean, name[4:])
        rgb = [tuple(int(v) / 255 for v in c[c.index("(") + 1:-1].split(",")) for c in stops]
        return LinearSegmentedColormap.from_list(name, rgb, N=256)
    return matplotlib.colormaps[name]


def nice_ticks(vmin: float, vmax: float, log: bool = False, diverging: bool = False) -> tuple[float, float, list]:
    """Round the range out to round numbers and return (vmin, vmax, ticks) with 3-6 round ticks."""
    if log:
        steps = [b * 10.0 ** e for e in range(-3, 4) for b in (1, 2, 5)]
        lo = max([x for x in steps if x <= vmin] or [steps[0]])
        hi = min([x for x in steps if x >= vmax] or [steps[-1]])
        ticks = [x for x in steps if lo <= x <= hi]
        while len(ticks) > 6:
            ticks = ticks[::2] if ticks[-1] in ticks[::2] else [ticks[0]] + ticks[2::2]
        return lo, hi, ticks
    def nice(x):  # smallest of 1, 2, 2.5, 5 x 10^k that is >= x
        mag = 10 ** np.floor(np.log10(x))
        return min((b * mag for b in (1, 2, 2.5, 5, 10) if b * mag >= x * (1 - 1e-9)), default=10 * mag)

    if diverging:
        m = max(abs(vmin), abs(vmax)) or 1.0
        vmin, vmax = -m, m
    span = (vmax - vmin) or 1.0
    fine, tstep = nice(span / 10), nice(span / 4)  # range ends on a fine step, ticks on a coarser one
    lo, hi = np.floor(vmin / fine + 1e-9) * fine, np.ceil(vmax / fine - 1e-9) * fine
    if diverging:
        hi = max(abs(lo), abs(hi))
        lo = -hi
    ticks = [round(float(x), 6) for x in np.arange(np.ceil(lo / tstep - 1e-9) * tstep, hi + tstep * 1e-6, tstep)]
    return round(float(lo), 6), round(float(hi), 6), ticks


@st.cache_data(ttl=6 * 3600, show_spinner=False, max_entries=64)
def field(layer: str, day: str) -> dict | None:
    """Gridded field for the map as an RGBA image + metadata. None if nothing could be loaded."""
    import matplotlib
    from marinekit.sources import copernicus as cp
    L = LAYERS[layer]
    da = None
    used_key = L["key"]
    for key in [L["key"], L.get("fallback_key")]:
        if not key:
            continue
        try:
            da = timed(cp.fetch_field, key, BBOX_RO, time=day, variable=L["var"], timeout=40)
            used_key = key
            break
        except SlowSource:
            raise
        except Exception as ex:
            log.info("fetch_field %s %s: %s", key, day, ex)
    if da is None:
        return None
    a = da.squeeze().transpose("lat", "lon")
    vals = a.values.astype(float) * L.get("factor", 1.0)
    lats, lons = a.lat.values, a.lon.values
    if lats[0] < lats[-1]:
        vals, lats = vals[::-1], lats[::-1]
    finite = vals[np.isfinite(vals)]
    if finite.size == 0:
        return None
    if L.get("vrange"):
        vmin, vmax = L["vrange"]
    elif L.get("diverging"):
        m = float(np.nanpercentile(np.abs(finite), 98))
        vmin, vmax = -m, m
    else:
        vmin, vmax = (float(x) for x in np.nanpercentile(finite, [2, 98]))
    if L.get("vrange"):
        ticks = [float(x) for x in np.linspace(vmin, vmax, 5)]
    else:  # round range and ticks, so the legend reads cleanly and matches what is drawn
        vmin, vmax, ticks = nice_ticks(vmin, vmax, log=bool(L.get("log")), diverging=bool(L.get("diverging")))
    cm = colormap(L["cmap"])
    if L.get("log"):
        lo, hi = np.log10(max(vmin, 1e-3)), np.log10(max(vmax, 1e-3) * 1.0001)
        norm = (np.log10(np.clip(vals, 1e-3, None)) - lo) / (hi - lo)
    else:
        norm = (vals - vmin) / (vmax - vmin if vmax > vmin else 1)
    rgba = cm(np.clip(norm, 0, 1))
    rgba[..., 3] = np.where(np.isfinite(vals), 0.82, 0.0)
    dlat = abs(float(lats[0] - lats[1])) / 2 if len(lats) > 1 else 0
    dlon = abs(float(lons[1] - lons[0])) / 2 if len(lons) > 1 else 0
    t = pd.Timestamp(da.time.values[0]) if "time" in da.coords and da.time.size else pd.Timestamp(day)
    colors = [matplotlib.colors.to_hex(cm(x)) for x in np.linspace(0, 1, 11)]
    return dict(rgba=(rgba * 255).astype(np.uint8), bounds=[[float(lats.min()) - dlat, float(lons.min()) - dlon],
                                                            [float(lats.max()) + dlat, float(lons.max()) + dlon]],
                vmin=vmin, vmax=vmax, ticks=ticks, unit=L["unit"], colors=colors, log=bool(L.get("log")),
                title=L["title"], cmap=L["cmap"],
                time=str(t.date()), dataset=da.attrs.get("dataset", ""), key=used_key, origin=L["origin"],
                values=vals, lats=lats, lons=lons)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def tile_url(layer: str, day: str) -> str | None:
    from marinekit.sources import copernicus as cp
    L = LAYERS[layer]
    for key in [L["key"], L.get("fallback_key")]:
        if not key:
            continue
        try:
            return cp.wmts_tile_url(key, L["var"], time=day)
        except Exception as ex:
            log.info("wmts %s: %s", key, ex)
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def tile_day(layer: str, day: str) -> str | None:
    """The day the Copernicus WMTS can draw for `day`: the day itself if published, else the nearest published day
    (the latest one for today and forecast days). The tile server answers HTTP 400 with no image for a TIME it does
    not have, so the map stays empty if the request asks for an unpublished day. None if the service is unreachable."""
    from marinekit.sources import copernicus as cp
    L = LAYERS[layer]
    want = pd.Timestamp(day)
    for key in [L["key"], L.get("fallback_key")]:
        if not key:
            continue
        try:
            lay = next((l for l in cp.wmts_layers(key) if l["variable"] == L["var"]), None)
        except Exception as ex:
            log.info("wmts layers %s: %s", key, ex)
            continue
        if lay is None:
            continue
        spans = []
        for v in lay.get("time_values") or []:
            parts = str(v).split("/")
            if len(parts) >= 2:
                spans.append((pd.Timestamp(parts[0]).tz_localize(None).normalize(),
                              pd.Timestamp(parts[1]).tz_localize(None).normalize()))
            else:
                for x in str(v).split(","):
                    t = pd.Timestamp(x).tz_localize(None).normalize()
                    spans.append((t, t))
        if not spans:
            d = lay.get("time_default")
            return str(pd.Timestamp(d).tz_localize(None).date()) if d else day
        best = min((min(max(want, a), b) for a, b in spans), key=lambda t: abs((t - want).days))
        return str(best.date())
    return None


def tile_url_styled(layer: str, day: str, vmin: float, vmax: float) -> str | None:
    """Copernicus WMTS tiles drawn with the viewer's ramp and range (STYLE=cmap:<name>,range:a/b in the
    product's own units, e.g. kelvin for satellite SST). None if the layer has no WMTS tiles."""
    from marinekit.sources import copernicus as cp
    L = LAYERS[layer]
    name = L["cmap"][4:] if L["cmap"].startswith("cmo.") else "thermal"
    off, fac = L.get("tile_offset", 0.0), L.get("factor", 1.0)
    a, b = vmin / fac + off, vmax / fac + off
    style = f"cmap:{name},range:{a:.6g}/{b:.6g}" + (",logScale" if L.get("log") else "")
    for key in [L["key"], L.get("fallback_key")]:
        if not key:
            continue
        try:
            return cp.wmts_tile_url(key, L["var"], time=day, style=style)
        except Exception as ex:
            log.info("wmts %s: %s", key, ex)
    return None


def sample_field(fd: dict, lat: float, lon: float) -> float | None:
    if not fd:
        return None
    i = int(np.argmin(np.abs(fd["lats"] - lat)))
    j = int(np.argmin(np.abs(fd["lons"] - lon)))
    v = fd["values"][i, j]
    return float(v) if np.isfinite(v) else None


# ------------------------------------------------------------------------------------------ zones
def _read_json(p: Path):
    return json.loads(p.read_text())


@st.cache_data(show_spinner=False)
def _mtime(p: str) -> float:
    return Path(p).stat().st_mtime if Path(p).exists() else 0.0


def _zones_stamp() -> tuple:
    names = ["overlap_summer.geojson", "overlap_winter.geojson", "overlap_grid.geojson", "sector_zones.geojson",
             "sector_features.geojson", "hotspot_grid.geojson", "hotspots.geojson"]
    return tuple((n, (ZONES / n).stat().st_mtime if (ZONES / n).exists() else 0) for n in names)


def zones_version() -> str:
    return "v2" if (ZONES / "overlap_summer.geojson").exists() else "v1 (old files, overlap derived in the viewer)"


@st.cache_data(show_spinner="Preparing the pressure overlap map...", persist="disk")
def _overlap_geojson(season: str, stamp: tuple) -> dict:
    """Dissolved overlap polygons for 'summer' or 'winter'; feature property 'n' = number of sectors (1-5)."""
    import geopandas as gpd
    f = ZONES / f"overlap_{season}.geojson"
    if f.exists():
        g = gpd.read_file(f)
        col = next((c for c in ("n", "level", "count", f"n_{season}", "n_sectors", "overlap") if c in g.columns), None)
        g["n"] = g[col].astype(int) if col else 1
        sc = next((c for c in (f"sectors_{season}", "sectors") if c in g.columns), None)
        g["sectors"] = g[sc].astype(str) if sc else ""
    else:
        grid_v2 = ZONES / "overlap_grid.geojson"
        if grid_v2.exists():
            g = gpd.read_file(grid_v2)
            g["n"] = g[f"n_{season}"].astype(int)
            g["sectors"] = g.get(f"sectors_{season}", "").astype(str)
        else:  # v1 grid: n_sectors counts all five; tourism is off in winter (decision 2)
            g = gpd.read_file(ZONES / "hotspot_grid.geojson", columns=["n_sectors", "sectors", "S_tourism", "geometry"])
            if season == "winter":
                tour = g["S_tourism"].fillna(0) > 0
                g["n"] = g["n_sectors"].astype(int) - tour.astype(int)
                g["sectors"] = g["sectors"].astype(str).str.replace(r",?tourism", "", regex=True).str.strip(",")
            else:
                g["n"] = g["n_sectors"].astype(int)
                g["sectors"] = g["sectors"].astype(str)
        g = g[g["n"] > 0]
        g = g.dissolve(by="n", as_index=False)[["n", "geometry"]]
        g["sectors"] = ""
    g = g[g["n"] > 0].copy()
    g["geometry"] = g.geometry.simplify(0.0008, preserve_topology=True)
    g = g.to_crs(4326) if g.crs and g.crs.to_epsg() != 4326 else g
    return json.loads(g[["n", "sectors", "geometry"]].to_json())


@st.cache_data(show_spinner=False, persist="disk")
def _overlap_cells(season: str, stamp: tuple) -> pd.DataFrame:
    """Cell centres with their overlap count, for point lookups and sector statistics."""
    gv2 = ZONES / "overlap_grid.geojson"
    if gv2.exists():
        import geopandas as gpd
        g = gpd.read_file(gv2, ignore_geometry=True)
        return pd.DataFrame({"lon": g.lon, "lat": g.lat, "n": g[f"n_{season}"].astype(int),
                             "sectors": g.get(f"sectors_{season}", pd.Series([""] * len(g))).astype(str)})
    csv = ZONES / "hotspot_grid_all.csv"
    g = pd.read_csv(csv, usecols=lambda c: c in ("lon", "lat", "n_sectors", "sectors", "S_tourism"))
    n = g["n_sectors"].astype(int)
    sec = g["sectors"].fillna("").astype(str)
    if season == "winter":
        tour = g["S_tourism"].fillna(0) > 0
        n = n - tour.astype(int)
        sec = sec.str.replace(r",?tourism", "", regex=True).str.strip(",")
    return pd.DataFrame({"lon": g.lon, "lat": g.lat, "n": n, "sectors": sec})


def overlap_at(lat, lon, season) -> tuple[int, str]:
    """(n, sectors) at a point for a season. Uses pressure_zones.overlap_at (cell polygons) when available."""
    pz = _mod("marinekit.pressure_zones")
    if pz is not None and hasattr(pz, "overlap_at") and (ZONES / "overlap_grid.geojson").exists():
        try:
            d = f"{today().year}-07-15" if season == "summer" else f"{today().year}-01-15"
            r = pz.overlap_at(lat, lon, d)
            return int(r.get("n") or 0), str(r.get("sectors") or "")
        except Exception as ex:
            log.info("pressure_zones.overlap_at: %s", ex)
    c = overlap_cells(season, _zones_stamp())
    if c.empty:
        return 0, ""
    d = (c.lat - lat) ** 2 + ((c.lon - lon) * np.cos(np.radians(lat))) ** 2
    i = int(d.idxmin())
    if np.sqrt(d[i]) * 111 > 0.6:  # outside any pressured cell
        return 0, ""
    return int(c.n[i]), str(c.sectors[i])


@st.cache_data(show_spinner=False, persist="disk")
def _sector_zones(stamp: tuple) -> dict:
    """Sector zones normalised to the v2 fields: sector, activity, buffer_m, buffer_basis, basis_ref, season, confidence."""
    import geopandas as gpd
    g = gpd.read_file(ZONES / "sector_zones.geojson")
    v2 = "buffer_m" in g.columns
    if not v2:  # v1: rings per sector; keep the outermost non-potential ring as "the zone"
        g = g[g["ring"].isin(["middle"])].copy() if "ring" in g.columns else g
        g["activity"] = g.get("distances", "")
        g["buffer_m"] = g.get("distance_m")
        g["buffer_basis"] = "rule"
        g["basis_ref"] = g.get("confidence", "")
        g["season"] = np.where(g["sector"] == "tourism", "summer", "all")
        conf = g.get("confidence", pd.Series([""] * len(g))).astype(str)
        g["confidence"] = np.where(conf.str.contains("assumption"),
                                   np.where(conf.str.contains("legal|literature"), "mapped", "assumed"), "official")
    for c in ("activity", "buffer_basis", "basis_ref", "season", "confidence"):
        if c not in g.columns:
            g[c] = ""
    g = g[~g.geometry.is_empty & g.geometry.notna()].copy()
    g["geometry"] = g.geometry.buffer(0).simplify(0.0005, preserve_topology=True)
    keep = ["sector", "activity", "buffer_m", "buffer_basis", "basis_ref", "season", "confidence", "geometry"]
    g["buffer_m"] = pd.to_numeric(g["buffer_m"], errors="coerce")
    return json.loads(g[keep].to_json())


@st.cache_data(show_spinner=False, persist="disk")
def _sector_features(stamp: tuple) -> dict:
    """Sector features normalised to the v2 fields (feature_id, sector, activity, name, source, confidence, season)."""
    import geopandas as gpd
    g = gpd.read_file(ZONES / "sector_features.geojson")
    if "activity" not in g.columns:
        g["activity"] = g.get("ftype", "")
    if "confidence" not in g.columns:
        lq = g.get("location_quality", pd.Series([""] * len(g))).astype(str).str.lower()
        src = g.get("source", pd.Series([""] * len(g))).astype(str).str.lower()
        g["confidence"] = np.select(
            [lq.str.contains("proxy|assum|place name|approx"), src.str.contains("osm"),
             src.str.contains("emodnet|eea|anpa|law|order|port")], ["assumed", "mapped", "official"], "mapped")
    if "season" not in g.columns:
        g["season"] = np.where(g["sector"] == "tourism", "summer", "all")
    if "source_url" not in g.columns:
        g["source_url"] = ""
    g = g[g["sector"].isin(["ports", "shipyards", "tourism", "fishing", "aquaculture"])].copy()
    g["geometry"] = g.geometry.simplify(0.0003, preserve_topology=True)
    keep = ["feature_id", "sector", "activity", "name", "source", "source_url", "confidence", "season", "geometry"]
    for c in keep:
        if c not in g.columns:
            g[c] = ""
    g["name"] = g["name"].fillna("").astype(str)
    return json.loads(g[keep].to_json())


def n_label(n) -> str:
    return f"{int(n)} sectors"


@st.cache_data(show_spinner=False)
def _hotspots(stamp: tuple) -> pd.DataFrame:
    """Places with the highest overlap. v1: hotspots.geojson polygons. v2: the highest-count cells of the summer grid,
    picked at least 6 km apart and named after the nearest area in top_overlap_areas.csv / reference station."""
    import geopandas as gpd
    f = ZONES / "hotspots.geojson"
    if f.exists():
        g = gpd.read_file(f)
        rp = g.geometry.representative_point()
        g["lat"], g["lon"] = rp.y, rp.x
        g["wkt"] = g.geometry.to_wkt()
        cols = [c for c in ("rank", "name", "max_n_sectors", "sectors", "area_km2", "near", "lat", "lon", "wkt") if c in g.columns]
        return pd.DataFrame(g[cols])
    c = overlap_cells("summer", stamp)
    if c.empty:
        return pd.DataFrame()
    c = c[c.n >= 3].sort_values("n", ascending=False)
    picked = []
    for _, r in c.iterrows():
        if all(_haversine_km(r.lat, r.lon, p["lat"], p["lon"]) > 6 for p in picked):
            near = min(STATIONS.items(), key=lambda kv: _haversine_km(r.lat, r.lon, *kv[1]))
            d = _haversine_km(r.lat, r.lon, *near[1])
            picked.append(dict(rank=len(picked) + 1, name=f"{n_label(r.n)} near {near[0]} ({d:.0f} km)", max_n_sectors=int(r.n),
                               sectors=r.sectors, lat=float(r.lat), lon=float(r.lon), wkt=None))
        if len(picked) >= 10:
            break
    return pd.DataFrame(picked)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def natura() -> dict | None:
    from marinekit.sources import emodnet_layers as el
    try:
        g = el.fetch_gdf("natura2000")
    except Exception as ex:
        log.info("natura2000: %s", ex)
        return None
    g = g[["sitecode", "sitename", "sitetype", "area_ha", "geometry"]].copy()
    g["geometry"] = g.geometry.simplify(0.0008, preserve_topology=True)
    return json.loads(g.to_json())


def zones_containing(lat, lon, stamp) -> list[dict]:
    """Sector zones and Natura 2000 sites that contain a point."""
    from shapely.geometry import Point, shape
    pt = Point(lon, lat)
    out = []
    for f in sector_zones(stamp)["features"]:
        try:
            if shape(f["geometry"]).contains(pt):
                out.append({"kind": "sector zone", **{k: f["properties"].get(k) for k in ("sector", "season", "confidence")}})
        except Exception:
            pass
    nat = natura()
    for f in (nat or {}).get("features", []):
        try:
            if shape(f["geometry"]).contains(pt):
                out.append({"kind": "Natura 2000", "sector": f["properties"].get("sitename"),
                            "season": "", "confidence": f["properties"].get("sitecode")})
        except Exception:
            pass
    return out


def sector_zone_geom(sector: str, stamp):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    gs = [shape(f["geometry"]) for f in sector_zones(stamp)["features"] if f["properties"]["sector"] == sector]
    return unary_union(gs) if gs else None


def season_for_date(d) -> str:
    pz = _mod("marinekit.pressure_zones")
    if pz is not None and hasattr(pz, "season_for_date"):
        try:
            return pz.season_for_date(d)
        except Exception:
            pass
    d = pd.Timestamp(d)
    return "summer" if (6, 1) <= (d.month, d.day) <= (9, 15) else "winter"


# ------------------------------------------------------------------------------------------ health cards
CARD_ORDER = ["temperature", "oxygen", "blooms", "clarity", "nutrients", "bathing", "biodiversity", "drivers",
              "acidification"]
CARD_TITLES = {"temperature": "Water temperature", "oxygen": "Oxygen", "blooms": "Eutrophication and blooms",
               "clarity": "Water clarity", "nutrients": "Nutrients (historical)", "bathing": "Bathing water",
               "biodiversity": "Biodiversity evidence", "drivers": "Drivers (natural variability)",
               "acidification": "Acidification (watch only)"}
CARD_SECTORS = {"temperature": ["aquaculture", "tourism", "fishing"], "oxygen": ["aquaculture", "fishing"],
                "blooms": ["aquaculture", "tourism", "ports"], "clarity": ["tourism", "ports", "shipyards"],
                "nutrients": ["ports", "shipyards", "tourism", "fishing", "aquaculture"], "bathing": ["tourism"],
                "biodiversity": ["ports", "shipyards", "tourism"], "drivers": [], "acidification": ["aquaculture"]}


def cards_source() -> str:
    return "indicators module" if _mod("marinekit.indicators") is not None else "viewer placeholder"


_JOBS: dict = {}
_DONE: dict = {}


def _cards_job(lat, lon, day, prof, wkt, wait):
    """Cards from marinekit.indicators in a background job: a new place does not block the page. The first call
    waits `wait` seconds; later reruns pick up the finished result."""
    k = (lat, lon, day, prof, wkt)
    if k in _DONE:
        return _DONE[k]
    fut = _JOBS.get(k)
    if fut is None:
        ind = importlib.import_module("marinekit.indicators")
        from shapely import wkt as _wkt
        geom = _wkt.loads(wkt) if wkt else (float(lat), float(lon))
        fut = _JOBS[k] = _POOL.submit(ind.zone_cards, geom, day, prof)
    try:
        res = fut.result(timeout=wait)
    except _FutTimeout:
        raise SlowSource("cards still computing")
    except Exception:
        _JOBS.pop(k, None)
        raise
    res = [dict(c) for c in res]
    _DONE[k] = res
    _JOBS.pop(k, None)
    if len(_DONE) > 300:
        _DONE.pop(next(iter(_DONE)))
    return res


def cards_ready(lat, lon, day, prof, wkt=None) -> bool:
    k = (round(lat, 4), round(lon, 4), day, prof, wkt)
    if k in _DONE:
        return True
    f = _JOBS.get(k)
    return f is None or f.done()


def cards_pending(cards: list[dict]) -> bool:
    return any(c.get("pending") for c in cards)


def zone_cards(lat: float, lon: float, day: str, profile_level: str, zone_wkt: str | None = None,
               wait: float = 12) -> list[dict]:
    ind = _mod("marinekit.indicators")
    if ind is not None and hasattr(ind, "zone_cards"):
        try:
            return _cards_job(round(lat, 4), round(lon, 4), day, profile_level, zone_wkt, wait)
        except SlowSource:
            return [_card(cid, why="Still being computed for this place.", pending=True) for cid in CARD_ORDER]
        except Exception as ex:
            log.warning("indicators.zone_cards failed, using placeholder: %s", ex)
    try:
        return _placeholder_cards(round(lat, 3), round(lon, 3), day)
    except SlowSource:
        return [_card(cid, why="Data for this place is still downloading; open this again in a minute.") for cid in CARD_ORDER]


def soft(fn, *args, **kw):
    """Call a cached adapter; a slow download returns None instead of blocking the page."""
    try:
        return fn(*args, **kw)
    except SlowSource:
        st.caption("Some data is still downloading in the background; open this view again in a minute.")
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _real_cards(lat, lon, day, profile_level, zone_wkt):
    from shapely import wkt as _wkt
    from shapely.geometry import Point
    ind = importlib.import_module("marinekit.indicators")
    geom = _wkt.loads(zone_wkt) if zone_wkt else (float(lat), float(lon))
    res = timed(ind.zone_cards, geom, day, profile_level, timeout=120)
    return [dict(c) for c in res]


def _card(cid, status="no_data", **kw):
    base = dict(id=cid, title=CARD_TITLES.get(cid, cid), status=status, value=None, unit="", reference="", z=None,
                evidence="", confidence="", why="", driver_note="", investigate="", sources=[], text={})
    base.update(kw)
    return base


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _placeholder_cards(lat, lon, day) -> list[dict]:
    """Minimal cards computed in the viewer until marinekit.indicators lands (same dict format)."""
    d = pd.Timestamp(day)
    out = []

    def recent(var, key_idx=0):
        v = VARIABLES[var]
        key, native, origin, factor = v["sources"][key_idx]
        start = str((d - pd.Timedelta(days=60)).date())
        end = str((d + pd.Timedelta(days=1)).date())
        return _cop_series(key, native, lat, lon, start, end, factor), key, origin

    def vs_clim(var, s):
        c = climatology(var, lat, lon)
        if c is None or s is None or s.empty:
            return None
        cc = c.reindex(doy365(s.index))
        cc.index = s.index
        return cc

    # temperature
    s, key, origin = recent("sst")
    cc = vs_clim("sst", s)
    if s is not None and cc is not None and len(s):
        last, t = float(s.iloc[-1]), s.index[-1]
        z = (last - cc["mean"].iloc[-1]) / cc["std"].iloc[-1]
        above = (s > cc["p90"]).astype(int)
        run = int(above[::-1].cumprod().sum())
        below = int((s < cc["p10"]).astype(int)[::-1].cumprod().sum())
        status = "alert" if run >= 5 else ("watch" if (z > 2 or run >= 1 or below >= 5) else "normal")
        why = (f"Above the 90th percentile for {run} days in a row (marine heatwave definition: 5 or more)." if run else
               f"Below the 10th percentile for {below} days (cold spell)." if below >= 5 else
               f"Within the usual range for {t:%d %b} (z = {z:+.1f}).")
        out.append(_card("temperature", status, value=round(last, 2), unit="°C",
                         reference=f"{cc['mean'].iloc[-1]:.1f} °C usual for {t:%d %b} (1991-2020, p10-p90 {cc['p10'].iloc[-1]:.1f}-{cc['p90'].iloc[-1]:.1f})",
                         z=round(float(z), 2), evidence="satellite", confidence="high", why=why,
                         driver_note="Check upwelling (cold coastal water with offshore wind) before calling a cold anomaly a pressure.",
                         investigate="If a heatwave lasts 5+ days: tell mussel farms and check bottom oxygen." if status != "normal" else "",
                         sources=[dict(dataset=s.attrs.get("dataset", key), origin=origin, date=str(t.date()),
                                       distance_km=s.attrs.get("distance_km"))]))
    else:
        out.append(_card("temperature", why="Satellite SST not available for this point."))

    # oxygen (model bottom; low confidence)
    s, key, origin = recent("o2_bottom")
    if s is not None and len(s):
        sub = s[s.index <= d + pd.Timedelta(days=1)]
        sub = sub if len(sub) else s
        last, t = float(sub.iloc[-1]), sub.index[-1]
        status = "alert" if last < 2 else ("watch" if last < 4 else "normal")
        out.append(_card("oxygen", status, value=round(last, 2), unit="mg/L",
                         reference="Watch below 4 mg/L, alert below 2 mg/L (hypoxia). Draft thresholds, to confirm with NIMRD.",
                         evidence="model", confidence="low",
                         why=f"Model bottom oxygen is {last:.1f} mg/L. No bottom sensor in the area, so this is the model only.",
                         driver_note="Cold, salty bottom water (bottom salinity above 18.5) explains most low-oxygen events: natural.",
                         investigate="If below 2 mg/L at a mussel bed: ROV or drop-camera transect and a grab sample within 2 weeks." if status != "normal" else "",
                         sources=[dict(dataset=s.attrs.get("dataset", key), origin="model", date=str(t.date()),
                                       distance_km=s.attrs.get("distance_km"))]))
    else:
        out.append(_card("oxygen", why="Model oxygen not available for this point."))

    # eutrophication (satellite chl)
    s, key, origin = recent("chl")
    cc = vs_clim("chl", s)
    if s is not None and cc is not None and len(s):
        last, t = float(s.iloc[-1]), s.index[-1]
        p90 = float(cc["p90"].iloc[-1])
        days = int((s > cc["p90"]).astype(int)[::-1].cumprod().sum())
        status = "alert" if last > 10 else ("watch" if last > p90 else "normal")
        out.append(_card("blooms", status, value=round(last, 2), unit="mg/m³",
                         reference=f"{cc['p50'].iloc[-1]:.1f} mg/m³ usual for {t:%d %b} (1998-2022), p90 {p90:.1f}; alert above 10 mg/m³",
                         evidence="satellite", confidence="medium" if lon < 28.9 else "high",
                         why=(f"Above the usual 90th percentile for {days} days." if days else "Within the usual range for the season."),
                         driver_note="High Danube discharge raises chlorophyll naturally; check the Drivers card.",
                         investigate="Jun-Sep bloom: water samples for harmful species; toxin test for shellfish farms." if status != "normal" else "",
                         sources=[dict(dataset=s.attrs.get("dataset", key), origin=origin, date=str(t.date()),
                                       distance_km=s.attrs.get("distance_km"))]))
    else:
        out.append(_card("blooms", why="Satellite chlorophyll not available for this point."))

    # clarity (kd490)
    s, key, origin = recent("kd490")
    cc = vs_clim("kd490", s)
    if s is not None and cc is not None and len(s):
        last, t = float(s.iloc[-1]), s.index[-1]
        p90 = float(cc["p90"].iloc[-1])
        days = int((s > cc["p90"]).astype(int)[::-1].cumprod().sum())
        status = "alert" if days >= 7 else ("watch" if last > p90 else "normal")
        secchi = 1.7 / last if last > 0 else None
        out.append(_card("clarity", status, value=round(last, 3), unit="1/m",
                         reference=f"{cc['p50'].iloc[-1]:.2f} 1/m usual (1998-2022), p90 {p90:.2f}; about {secchi:.1f} m visibility (Secchi = 1.7 / Kd490)" if secchi else "",
                         evidence="satellite", confidence="medium",
                         why=(f"Murkier than usual for {days} days." if days else "Within the usual range."),
                         driver_note="Storms and Danube floods make the water murky naturally.",
                         investigate="If persistent 7+ days near works: check dredging and coastal works." if status != "normal" else "",
                         sources=[dict(dataset=s.attrs.get("dataset", key), origin=origin, date=str(t.date()),
                                       distance_km=s.attrs.get("distance_km"))]))
    else:
        out.append(_card("clarity", why="Satellite Kd490 not available for this point (clouds or coast)."))

    for cid in ("nutrients", "bathing", "biodiversity", "drivers", "acidification"):
        out.append(_card(cid, why="Computed by the indicators module (not connected yet)."))
    return out


# ------------------------------------------------------------------------------------------ vectors
def vectorviz():
    return _mod("viewer.vectorviz")


# ------------------------------------------------------------------------------------------ docs parsing
def md_tables(path: Path) -> dict[str, list[pd.DataFrame]]:
    """Markdown pipe tables grouped by the '## ' section they appear in."""
    if not path.exists():
        return {}
    out, sec, buf = {}, "", []

    def flush():
        nonlocal buf
        if len(buf) >= 2:
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in buf]
            hdr, body = rows[0], [r for r in rows[2:] if len(r) == len(rows[0])]
            out.setdefault(sec, []).append(pd.DataFrame(body, columns=hdr))
        buf = []

    for line in path.read_text().splitlines():
        if line.startswith("## "):
            flush()
            sec = line[3:].strip()
        elif line.strip().startswith("|"):
            buf.append(line)
        else:
            flush()
    flush()
    return out


def strip_md(s: str) -> str:
    return re.sub(r"\*\*|`", "", str(s))


def catalog_table() -> pd.DataFrame:
    from marinekit.sources.copernicus import CATALOG
    rows = []
    for k, e in CATALOG.items():
        rows.append(dict(key=k, origin=e.get("origin"), product=e.get("product"), dataset_id=e.get("dataset_id", ""),
                         variables=", ".join(f"{a} -> {b}" for a, b in e.get("vars", {}).items()),
                         resolution_deg=e.get("res_deg"), frequency=e.get("freq"),
                         reference_years="-".join(map(str, e["clim_years"])) if e.get("clim_years") else (e.get("clim") or "")))
    return pd.DataFrame(rows)


def stations() -> dict:
    return dict(STATIONS)


# ------------------------------------------------------------------------------------------ safe zone readers
_LAST_GOOD: dict = {}


def _safe(name, fn, *args):
    """Zone files can be rewritten by the pressure-zones workstream while the app runs: a failed read falls back
    to the last good result (or an empty result) instead of breaking the page."""
    try:
        out = fn(*args)
        _LAST_GOOD[(name,) + args[:-1]] = out
        return out
    except Exception as ex:
        log.warning("zone file read failed (%s): %s", name, ex)
        prev = _LAST_GOOD.get((name,) + args[:-1])
        if prev is not None:
            return prev
        if name == "overlap_cells":
            return pd.DataFrame(columns=["lon", "lat", "n", "sectors"])
        if name == "hotspots":
            return pd.DataFrame()
        return {"type": "FeatureCollection", "features": []}


def overlap_geojson(season: str, stamp: tuple) -> dict:
    return _safe("overlap_geojson", _overlap_geojson, season, stamp)


def overlap_cells(season: str, stamp: tuple) -> pd.DataFrame:
    return _safe("overlap_cells", _overlap_cells, season, stamp)


def sector_zones(stamp: tuple) -> dict:
    return _safe("sector_zones", _sector_zones, stamp)


def sector_features(stamp: tuple) -> dict:
    return _safe("sector_features", _sector_features, stamp)


def hotspots(stamp: tuple) -> pd.DataFrame:
    return _safe("hotspots", _hotspots, stamp)


# ------------------------------------------------------------------------------------------ sector sites
SITE_ACTIVITIES = {
    "ports": ["port_area", "anchorage"],
    "shipyards": ["shipyard", "offshore_platform", "dredging_activity"],
    "tourism": ["bathing_water", "beach", "marina"],
    "fishing": ["landing_point", "pound_net_zone", "fishing_ground"],
    "aquaculture": ["aquaculture_lease", "aquaculture_planned"],
}
_CONF_RANK = {"official": 0, "mapped": 1, "assumed": 2}


def _clean_name(s: str) -> str:
    s = re.sub(r"\s*\((EMODnet port location|AIS-derived[^)]*)\)", "", str(s or "")).strip()
    return s[:48]


@st.cache_data(show_spinner=False)
def _sector_sites(sector: str, stamp: tuple, max_sites: int = 4, min_km: float = 15.0) -> list[dict]:
    """2-4 representative sites for a sector: its main features (port areas, shipyards, bathing waters, landing
    points, aquaculture leases), ranked by activity priority, confidence and overlap count, at least `min_km` apart.
    Falls back to the sector's highest-overlap cells."""
    from shapely.geometry import shape
    acts = SITE_ACTIVITIES.get(sector, [])
    cand = []
    for f in sector_features(stamp)["features"]:
        p = f["properties"]
        if p.get("sector") != sector or p.get("activity") not in acts or not f.get("geometry"):
            continue
        try:
            rp = shape(f["geometry"]).representative_point()
        except Exception:
            continue
        n, _ = overlap_at(rp.y, rp.x, "summer")
        cand.append(dict(name=_clean_name(p.get("name")) or p.get("activity").replace("_", " "), lat=round(rp.y, 4),
                         lon=round(rp.x, 4), activity=p.get("activity"), confidence=p.get("confidence"), n=n,
                         rank=(acts.index(p["activity"]), _CONF_RANK.get(p.get("confidence"), 3), -n)))
    cand.sort(key=lambda c: c["rank"])
    picked: list[dict] = []
    for c in cand:
        if all(_haversine_km(c["lat"], c["lon"], q["lat"], q["lon"]) >= min_km for q in picked):
            near = min(STATIONS.items(), key=lambda kv: _haversine_km(c["lat"], c["lon"], *kv[1]))[0]
            c["why"] = (f"{c['activity'].replace('_', ' ')} ({c['confidence']})"
                        + (f", {c['n']} sectors overlap" if c["n"] else ""))
            c["near"] = near
            picked.append(c)
        if len(picked) >= max_sites:
            break
    if len(picked) < 2:  # fallback: highest-overlap cells of this sector
        cells = overlap_cells("summer", stamp)
        cells = cells[cells.sectors.str.contains(sector, na=False)].sort_values("n", ascending=False)
        for _, r in cells.iterrows():
            if all(_haversine_km(r.lat, r.lon, q["lat"], q["lon"]) >= min_km for q in picked):
                near = min(STATIONS.items(), key=lambda kv: _haversine_km(r.lat, r.lon, *kv[1]))[0]
                picked.append(dict(name=f"Overlap cell near {near}", lat=round(float(r.lat), 4), lon=round(float(r.lon), 4),
                                   why=f"{int(r.n)} sectors overlap", near=near, n=int(r.n)))
            if len(picked) >= max_sites:
                break
    for c in picked:
        c.pop("rank", None)
    return picked


def sector_sites(sector: str, stamp: tuple) -> list[dict]:
    try:
        return _sector_sites(sector, stamp)
    except Exception as ex:
        log.warning("sector_sites %s: %s", sector, ex)
        return []


def cards_for_sites(sites: list[dict], day: str, prof: str, wait: float = 8.0) -> list[list[dict]]:
    """Cards for several sites in parallel background jobs; sites not ready within `wait` s come back pending."""
    import time as _t
    for s in sites:  # start every job first
        try:
            _cards_job(s["lat"], s["lon"], day, prof, None, 0.01)
        except Exception:
            pass
    t_end = _t.time() + wait
    out = []
    for s in sites:
        try:
            out.append(_cards_job(s["lat"], s["lon"], day, prof, None, max(0.05, t_end - _t.time())))
        except SlowSource:
            out.append([_card(cid, why="Still being computed for this site.", pending=True) for cid in CARD_ORDER])
        except Exception as ex:
            out.append([_card(cid, why=f"Could not compute: {str(ex)[:100]}") for cid in CARD_ORDER])
    return out
