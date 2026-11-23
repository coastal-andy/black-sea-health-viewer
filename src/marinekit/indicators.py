"""Health cards for the Black Sea Health Viewer (workstream I, interface "I -> U" in docs/plan/WORKFLOW.md).

    from marinekit import indicators as ind
    ind.CARDS                                              # ordered card ids (SHORTLIST section 1)
    c = ind.card("oxygen", 44.17, 28.72, "2026-11-23", profile="public")
    cs = ind.zone_cards((44.17, 28.72), "2026-11-23", "stakeholder:aquaculture")
    cs = ind.zone_cards(shapely_polygon_or_geojson, "2024-07-15", "researcher")

Every card is a dict with the keys of CARD_KEYS:
  id, title, status (normal|watch|alert|no_data), value, unit, reference (dict), z, evidence (measured|satellite|model),
  confidence (high|medium|low), why, driver_note, investigate (list of {trigger, action, who}),
  sources (list of {dataset, origin, date, distance_km, label}), text {public, student, stakeholder, researcher},
  plus "supporting" (list of {name, value, unit, note}) for the secondary indicators of SHORTLIST section 1.

Thresholds carry a label in reference["threshold_type"] and in each supporting item:
  OFFICIAL-RO (Romanian MSFD 2024, NIMRD), OFFICIAL-EU (EU directive), LIT (literature), OURS (our proposal or a
  climatology band). The science and the numbers come from docs/indicators/SHORTLIST.md and physical.md /
  chemical.md / biological.md; the computations are the ones verified in scripts/indicators/*_check.py.

The natural-vs-pressure rule chain of SHORTLIST section 3 is implemented once, in classify_cause(); every card uses it
to fill driver_note.
"""
from __future__ import annotations

import functools
import json
import math
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from . import datahub as dh
from .sources import ROOT, cache_key, cached_path

CARDS = ["temperature", "oxygen", "blooms", "clarity", "nutrients", "bathing", "biodiversity", "drivers",
         "acidification"]
TITLES = {
    "temperature": "Water temperature",
    "oxygen": "Oxygen",
    "blooms": "Eutrophication and blooms",
    "clarity": "Water clarity",
    "nutrients": "Nutrients (historical)",
    "bathing": "Bathing water",
    "biodiversity": "Biodiversity evidence",
    "drivers": "Drivers (natural variability)",
    "acidification": "Acidification (watch only)",
}
CARD_KEYS = ("id", "title", "status", "value", "unit", "reference", "z", "evidence", "confidence", "why",
             "driver_note", "investigate", "sources", "text")
STATUSES = ("normal", "watch", "alert", "no_data")
PROFILES = ("public", "student", "stakeholder", "researcher")
SECTORS = ("ports", "shipyards", "tourism", "fishing", "aquaculture")
_RANK = {"no_data": 0, "normal": 1, "watch": 2, "alert": 3}

# ------------------------------------------------------------------------------------------- thresholds
# (value, label, type)
T = {
    "mhw": ("above the day-of-year 90th percentile for >= 5 days; categories moderate/strong/severe/extreme by "
            "multiples of (p90 - mean)", "Hobday et al. 2016, 2018", "LIT"),
    "o2_classes": ("A >= 5 mg/L (D5C5 level), B 4-5, C 2-4, D < 2 (hypoxia)", "A: RO MSFD 2024 D5C5; B, C: ours; "
                   "D: Diaz & Rosenberg 2008", "OFFICIAL-RO"),
    "d5c5": ("May-Sep P10 of bottom O2 >= 5 mg/L and >= 60 % saturation", "RO MSFD 2024 (NIMRD), D5C5", "OFFICIAL-RO"),
    "o2sat_flags": ("surface saturation > 120 % (bloom), < 80 % (respiration or upwelling)", "chemical.md C2", "OURS"),
    "d5c2_coastal": (5.97, "May-Sep P75 chl, coastal waters (RO MSFD 2024 D5C2)", "OFFICIAL-RO"),
    "d5c2_marine": (2.79, "May-Sep mean chl, marine waters south (RO MSFD 2024)", "OFFICIAL-RO"),
    "secchi_ges": (5.6, "May-Sep P10 Secchi depth, coastal waters (RO MSFD 2024)", "OFFICIAL-RO"),
    "din_marine": (10.5, "DIN P75, marine waters (RO MSFD 2024)", "OFFICIAL-RO"),
    "po4_marine": (0.23, "PO4 P75, marine waters (RO MSFD 2024)", "OFFICIAL-RO"),
    "din_coastal": (13.5, "DIN P75, coastal waters RO-CT (RO MSFD 2024)", "OFFICIAL-RO"),
    "po4_coastal": (0.30, "PO4 P75, coastal waters RO-CT (RO MSFD 2024)", "OFFICIAL-RO"),
    "bwd": ("Excellent / Good / Sufficient / Poor", "Bathing Water Directive 2006/7/EC", "OFFICIAL-EU"),
}
SECCHI_C = 1.1          # Secchi ~= 1.1 / Kd_PAR, tuned to INCDM coastal Secchi 2018-2023 (physical.md P6)
OFFSHORE_DLON = 0.58    # offshore reference for the upwelling index: same latitude, ~47 km east (physical.md P2)
HEAT_CLASSES = [(0.5, "high"), (1.0, "good"), (1.5, "moderate"), (2.0, "poor"), (np.inf, "bad")]  # HELCOM HEAT 3.0

# SHORTLIST section 5
INVESTIGATE = {
    "o2_D": dict(trigger="Bottom oxygen class D (hypoxia) or mussel-bed hypoxia flag",
                 action="ROV or drop-camera transect plus a grab sample within 2 weeks", who="NIMRD, aquaculture operators"),
    "bloom": dict(trigger="Chlorophyll high in June-September",
                  action="Water samples for harmful species; shellfish toxin test for farms",
                  who="NIMRD, sanitary authority, mussel farms"),
    "nis_port": dict(trigger="New non-indigenous species near a port", action="Plankton tow, ballast-water check",
                     who="port authority"),
    "hotspot": dict(trigger="Persistent anomaly with no natural driver inside a sector pressure zone",
                    action="Targeted sampling campaign at this location", who="environment agency (APM Constanta), NIMRD"),
    "bathing": dict(trigger="Bathing water Sufficient or Poor", action="Check nearby wastewater outfalls",
                    who="municipality, water operator"),
}

# Bathing season (WORKFLOW decision 2)
SEASON = ((6, 1), (9, 15))

NIS = {  # biological.md B6: taxon -> (group, non-indigenous)
    "Mnemiopsis leidyi": ("comb jelly", True), "Beroe ovata": ("comb jelly", True), "Rapana venosa": ("rapa whelk", True),
    "Mya arenaria": ("soft-shell clam", True), "Anadara kagoshimensis": ("ark clam", True),
    "Rhithropanopeus harrisii": ("Harris mud crab", True), "Acartia tonsa": ("copepod", True),
    "Aurelia aurita": ("moon jellyfish", False), "Rhizostoma pulmo": ("barrel jellyfish", False),
    "Noctiluca scintillans": ("sea sparkle, bloom dinoflagellate", False),
}


# ------------------------------------------------------------------------------------------- helpers
def _ts(x) -> pd.Timestamp:
    return dh._ts(x).normalize()


def _r(x, n=2):
    if x is None:
        return None
    try:
        if not np.isfinite(float(x)):
            return None
    except (TypeError, ValueError):
        return x
    return round(float(x), n)


def _doy(d: pd.Timestamp) -> int:
    return int(dh._doy365(pd.DatetimeIndex([d]))[0])


def _clim_row(cl: pd.DataFrame, d: pd.Timestamp) -> pd.Series:
    return cl.loc[_doy(d)]


def _join_clim(s: pd.Series, cl: pd.DataFrame) -> pd.DataFrame:
    c = cl.reindex(dh._doy365(s.index))
    c.index = s.index
    return pd.DataFrame({"value": s, "mean": c["mean"], "std": c["std"], "p10": c["p10"], "p90": c["p90"]})


def _src(attrs: dict, date=None, label=None) -> list[dict]:
    """sources entries from a datahub series' attrs (one per dataset used)."""
    out = []
    for d in attrs.get("datasets") or [{}]:
        out.append({"dataset": d.get("dataset") or attrs.get("label"), "origin": d.get("origin") or attrs.get("origin"),
                    "date": None if date is None else str(pd.Timestamp(date).date()),
                    "distance_km": _r(d.get("distance_km", attrs.get("distance_km")), 1),
                    "label": label or attrs.get("label"), "trust": attrs.get("trust")})
    return out


def in_season(d: pd.Timestamp) -> bool:
    return (d.month, d.day) >= SEASON[0] and (d.month, d.day) <= SEASON[1]


def _parse_profile(profile: str) -> tuple[str, str | None]:
    p = (profile or "public").lower()
    if ":" in p:
        p, sector = p.split(":", 1)
        return p, sector if sector in SECTORS else None
    return p, None


def hobday_events(t: pd.Series, thresh: pd.Series, clim: pd.Series, above: bool = True,
                  min_len: int = 5, max_gap: int = 2) -> list[dict]:
    """Marine heatwaves (above) or cold spells (below) after Hobday et al. (2016, 2018): >= 5 days beyond the
    threshold, gaps <= 2 days merged; category from the peak (T - clim) / (thresh - clim)."""
    exc = ((t > thresh) if above else (t < thresh)).fillna(False).to_numpy()
    runs, i = [], 0
    while i < len(exc):
        if exc[i]:
            j = i
            while j + 1 < len(exc) and exc[j + 1]:
                j += 1
            if j - i + 1 >= min_len:
                runs.append([i, j])
            i = j + 1
        else:
            i += 1
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= max_gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    ev = []
    for i, j in merged:
        anom = (t.iloc[i:j + 1] - clim.iloc[i:j + 1]).to_numpy()
        diff = (thresh.iloc[i:j + 1] - clim.iloc[i:j + 1]).to_numpy()
        k = int(np.nanargmax(anom) if above else np.nanargmin(anom))
        ratio = abs(anom[k] / diff[k]) if diff[k] else np.nan
        cat = ["moderate", "strong", "severe", "extreme"][int(min(max(np.floor(ratio), 1), 4)) - 1] if np.isfinite(ratio) else "moderate"
        ev.append(dict(start=t.index[i], end=t.index[j], days=j - i + 1, peak=float(anom[k]), category=cat))
    return ev


def kdpar_from_kd490(kd490):
    """Morel et al. (2007): Kd(PAR) of the first optical depth from Kd(490)."""
    k = np.asarray(kd490, float)
    return 0.0864 + 0.884 * k - 0.00137 / k


@functools.lru_cache(maxsize=256)
def depth_at(lat: float, lon: float) -> float | None:
    """Water depth (m, positive down) from EMODnet Bathymetry (cached on disk by emodnet_layers)."""
    try:
        from .sources import emodnet_layers as el
        d = el.depth_at(lat, lon)
        return float(d) if np.isfinite(d) else None
    except Exception:  # noqa: BLE001
        return None


def _series(var, lat, lon, date, source="auto"):
    s, e = dh.card_window(date)
    return dh.get_series(var, lat, lon, s, e, source=source)


# ------------------------------------------------------------------------------------------- pressure zones
@functools.lru_cache(maxsize=1)
def _zone_index():
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    p = ROOT / "data" / "zones" / "sector_zones.geojson"
    if not p.exists():
        return None
    gj = json.loads(p.read_text())
    geoms, props = [], []
    for f in gj.get("features", []):
        try:
            geoms.append(shape(f["geometry"]))
            props.append(f.get("properties") or {})
        except Exception:  # noqa: BLE001
            continue
    return STRtree(geoms), geoms, props, str(p.relative_to(ROOT))


def pressure_at(lat: float, lon: float, date) -> dict:
    """Sectors whose pressure zone (data/zones/sector_zones.geojson) contains the point on this date.
    Summer-only zones count only in the bathing season (1 June - 15 September)."""
    try:
        idx = _zone_index()
    except Exception as e:  # noqa: BLE001
        return {"sectors": [], "n": None, "source": None, "note": f"zones unreadable: {e}"}
    if idx is None:
        return {"sectors": [], "n": None, "source": None, "note": "no zone file yet"}
    from shapely.geometry import Point
    tree, geoms, props, src = idx
    pt = Point(lon, lat)
    d = _ts(date)
    secs = set()
    for i in tree.query(pt):
        if not geoms[i].contains(pt):
            continue
        p = props[i]
        if str(p.get("season", "all")).lower() == "summer" and not in_season(d):
            continue
        if p.get("sector") in SECTORS:
            secs.add(p["sector"])
    return {"sectors": sorted(secs), "n": len(secs), "source": src, "note": ""}


# ------------------------------------------------------------------------------------------- drivers (P2, P3, P4, P7)
@functools.lru_cache(maxsize=128)
def _danube_spring_p75() -> tuple[float, pd.Series]:
    s, _ = dh.danube_discharge("1997-01-01", "2025-12-31")
    sp = s[s.index.month.isin([3, 4, 5, 6])]
    sp = sp.groupby(sp.index.year).mean()
    return float(sp.quantile(0.75)), sp


@functools.lru_cache(maxsize=128)
def _drivers_cached(lat: float, lon: float, date: str, bucket: int) -> dict:
    d = pd.Timestamp(date)
    out = {"date": date, "month": d.month, "errors": [], "sources": []}
    # P3 Danube: 30-day discharge ratio vs 1997-2025 day-of-year mean, spring discharge vs p75
    try:
        q = _series("discharge", lat, lon, d)
        cl = dh.get_climatology("discharge", lat, lon)
        j = _join_clim(q["discharge"], cl)
        last30 = j.loc[d - pd.Timedelta(days=29):d]
        out["danube_ratio30"] = _r(last30["value"].mean() / last30["mean"].mean(), 2)
        out["danube_q"] = _r(j["value"].get(d), 0)
        p75, _ = _danube_spring_p75()
        sp = q["discharge"][(q.index.year == d.year) & q.index.month.isin([3, 4, 5, 6])]
        out["spring_q"] = _r(sp.mean(), 0) if len(sp) > 60 else None
        out["spring_above_p75"] = bool(out["spring_q"] is not None and out["spring_q"] > p75)
        out["spring_p75"] = _r(p75, 0)
        out["sources"] += _src(q.attrs, d)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"danube: {e}")
    # surface salinity (model) and its anomaly
    try:
        sa = _series("sal", lat, lon, d)
        v, vd = dh.value_on(sa["sal"], d, 2)
        out["sal"] = _r(v, 2)
        if v is not None:
            c = _clim_row(dh.get_climatology("sal", lat, lon), d)
            out["sal_anom"] = _r(v - c["mean"], 2)
        out["sources"] += _src(sa.attrs, vd)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"salinity: {e}")
    # P4 stratification proxy: surface minus bottom temperature (model); bottom T change over 7 days
    try:
        ts = _series("sst", lat, lon, d, source="model")["sst"]
        tb = _series("bottom_temp", lat, lon, d)
        tbs = tb["bottom_temp"]
        v1, _ = dh.value_on(ts, d, 2)
        v2, vd = dh.value_on(tbs, d, 2)
        out["strat_dT"] = _r(v1 - v2, 2) if v1 is not None and v2 is not None else None
        out["stratified"] = bool(out["strat_dT"] is not None and out["strat_dT"] > 2 and 5 <= d.month <= 10)
        w = tbs.loc[d - pd.Timedelta(days=7):d].dropna()
        out["bottomT_drop7"] = _r(w.iloc[-1] - w.max(), 2) if len(w) > 1 else None
        out["bottom_temp"] = _r(v2, 2)
        out["sources"] += _src(tb.attrs, vd)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"stratification: {e}")
    # bottom salinity (for the cold saline intrusion rule)
    try:
        z = depth_at(lat, lon)
        if z and z > 5:
            cm = dh._cm()
            s0, e0 = dh.card_window(d)
            key = "phy_sal" if s0 >= dh.PHY_ANFC_START else "rea_phy_sal"
            zb = float(min(max(z - 2.0, 3.0), 80.0))
            bs = dh._with_offline_fallback(cm.fetch_timeseries, key, lat, lon, s0, min(e0, dh.PHY_REA_END) if key == "rea_phy_sal" else e0,
                                           variables=["so"], depth=zb, max_age_h=dh._max_age(e0))
            v, _ = dh.value_on(bs["sal"], d, 2)
            w = bs["sal"].loc[d - pd.Timedelta(days=7):d]
            out["bottom_sal"] = _r(w.max() if len(w.dropna()) else v, 2)
            out["bottom_sal_depth_m"] = bs.attrs.get("depth_m")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"bottom salinity: {e}")
    # P2 upwelling (June-September only): coastal minus offshore satellite SST <= -2 C on any of the last 3 days
    out["upwelling"] = None
    if 6 <= d.month <= 9:
        try:
            co = _series("sst", lat, lon, d)["sst"]
            of = _series("sst", lat, min(lon + OFFSHORE_DLON, 31.5), d)["sst"]
            diff = (co - of).loc[d - pd.Timedelta(days=2):d].dropna()
            out["upwelling_dT"] = _r(diff.min(), 2) if len(diff) else None
            out["upwelling"] = bool(len(diff) and diff.min() <= -2.0)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"upwelling: {e}")
    # P7 storm: daily max Hs over the previous 3 days vs hourly p95 (Open-Meteo 2021-2025)
    try:
        hs = _series("wave_height", lat, lon, d)
        w = hs["wave_height"].loc[d - pd.Timedelta(days=3):d].dropna()
        p95 = dh.wave_p95(lat, lon)
        out["hs_max3"] = _r(w.max(), 2) if len(w) else None
        out["hs_p95"] = _r(p95, 2)
        out["storm"] = bool(len(w) and w.max() > p95)
        out["sources"] += _src(hs.attrs, d)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"storm: {e}")
    out["pressure"] = pressure_at(lat, lon, d)
    return out


def drivers_at(lat: float, lon: float, date) -> dict:
    """Natural drivers at a point and date (shared by all cards): Danube ratio, salinity, stratification, bottom T
    drop, bottom salinity, upwelling, storm, and the sector pressure zones containing the point."""
    return _drivers_cached(round(float(lat), 4), round(float(lon), 4), str(_ts(date).date()), dh._bucket())


# ------------------------------------------------------------------------------------------- rule chain (SHORTLIST 3)
RULES = {
    1: "model artefact",
    2: "natural (upwelling)",
    3: "natural (cold saline intrusion)",
    4: "natural (Danube plume or flood)",
    5: "natural (storm)",
    6: "pressure-related (eutrophication: bloom decay under stratification)",
    7: "pressure (wastewater)",
    8: "possible pressure signal",
}


def classify_cause(kind: str | None, drivers: dict, model_only: bool = False, persist_days: int = 0,
                   bloom_recent: bool = False, nutrient_obs: dict | None = None) -> dict:
    """SHORTLIST section 3: natural variability or pressure? Apply the rules in order; the first match labels
    the event. 'Pressure' is used only when no natural driver explains it.

    kind: the anomaly being explained, one of
        warm, cold, low_o2_bottom, low_o2_surface, high_o2_surface, high_chl, low_clarity, high_nutrients,
        low_ph, low_salinity, or None (no anomaly).
    drivers: drivers_at(...) dict. model_only: the anomaly rests only on a model variable the model gets wrong
    (bottom O2 from the forecast system, model nitrate / phosphate). persist_days: how long the anomaly has lasted.
    bloom_recent: chl above p90 or surface O2 saturation > 120 % 1-4 weeks earlier.
    nutrient_obs: optional {'nh4','no2','po4' high flags, 'near_outfall', 'summer'} for rule 7.

    Returns {label, rule, text, also}: label in natural|mixed|model artefact|pressure-related|pressure|
    possible pressure|unexplained|climate|none; 'also' lists later rules that match too.
    Addition to the SHORTLIST chain: a warm or cold surface event that no rule explains is labelled "climate"
    (regional, weather-driven) and never "possible pressure", because local activities cannot cause it.
    """
    if not kind:
        return {"label": "none", "rule": None, "text": "No anomaly to explain.", "also": []}
    d = drivers or {}
    m = d.get("month", 0)
    hits = []
    if model_only:
        hits.append((1, "model artefact", "This rests on a model value the model is known to get wrong "
                     "(bottom O2: the forecast system runs about 2 mg/L below the reanalysis; nitrate and phosphate "
                     "are unusable as absolute values). Treat it as a model artefact until an observation confirms it."))
    if d.get("upwelling") and 6 <= m <= 9 and kind in ("cold", "low_o2_surface", "low_ph", "high_nutrients",
                                                       "low_o2_bottom", "high_chl"):
        hits.append((2, "natural", f"Upwelling: the coast is {abs(d.get('upwelling_dT') or 0):.1f} °C colder than "
                     "the water 47 km offshore. South-west winds bring cold, nutrient-rich, low-oxygen deep water to "
                     "the surface. This is natural."))
    if kind == "low_o2_bottom" and ((d.get("bottomT_drop7") is not None and d["bottomT_drop7"] < -1.5)
                                    or (d.get("bottom_sal") is not None and d["bottom_sal"] > 18.5)):
        hits.append((3, "natural", f"Cold saline intrusion: bottom salinity {d.get('bottom_sal')} PSU, bottom "
                     f"temperature change over 7 days {d.get('bottomT_drop7')} °C. Shelf-break water naturally low in "
                     "oxygen has moved onto the shelf."))
    danube = (d.get("danube_ratio30") is not None and d["danube_ratio30"] > 1.2) or \
             (d.get("sal") is not None and d["sal"] < 14)
    if danube and kind in ("high_chl", "low_clarity", "high_nutrients", "low_salinity", "low_o2_bottom"):
        mixed = bool(d.get("spring_above_p75"))
        hits.append((4, "mixed" if mixed else "natural",
                     f"Danube influence: river flow {d.get('danube_ratio30')} times normal over 30 days, surface "
                     f"salinity {d.get('sal')} PSU. " + ("The spring discharge was above its 75th percentile, and the "
                                                        "river load is partly a human pressure, so this is mixed."
                                                        if mixed else "This is natural variability.")))
    if d.get("storm") and kind in ("low_clarity", "high_chl"):
        hits.append((5, "natural", f"Storm: waves reached {d.get('hs_max3')} m in the last 3 days (95th percentile "
                     f"{d.get('hs_p95')} m). Waves stir up the seabed; murky water for a few days is natural."))
    if kind == "low_o2_bottom" and d.get("stratified") and bloom_recent:
        hits.append((6, "pressure-related", f"Bloom decay under stratification: the water column is layered "
                     f"(surface {d.get('strat_dT')} °C warmer than the bottom) and an algal bloom 1-4 weeks earlier "
                     "is sinking and decaying. This is the eutrophication pathway."))
    no = nutrient_obs or {}
    if kind == "high_nutrients" and no.get("high_nh4_no2_po4") and no.get("near_outfall") and no.get("summer") \
            and (d.get("sal") is None or d["sal"] >= 14):
        hits.append((7, "pressure", "High ammonium, nitrite or phosphate at normal salinity near an outfall in "
                     "summer: wastewater."))
    if kind in ("warm", "cold") and not hits:
        # Our addition to rule 8: a surface heatwave or cold spell (without upwelling) is a regional
        # atmosphere-driven event; local activities cannot cause it, so it is never flagged as a local pressure.
        hits.append((None, "climate", "Regional sea-temperature event driven by the weather and long-term warming. "
                     "Local activities do not cause it, so it is not counted as a local pressure; its effects "
                     "(heat stress, blooms, low oxygen) show on the other cards."))
    if not hits or (hits[0][0] == 1 and len(hits) == 1):
        zone = d.get("pressure") or {}
        if persist_days >= 5 and zone.get("n"):
            hits.append((8, "possible pressure", f"The anomaly has lasted {persist_days} days with no natural driver, "
                         f"inside a pressure zone ({', '.join(zone['sectors'])}). Possible pressure signal: investigate."))
        elif persist_days >= 5:
            hits.append((8, "unexplained", f"The anomaly has lasted {persist_days} days with no natural driver found. "
                         + ("No sector pressure zone here." if zone.get("n") == 0 else
                            "Pressure-zone overlap unknown.") + " Keep watching."))
        elif not hits:
            hits.append((None, "unexplained", "Short anomaly with no natural driver found yet; it may pass. "
                         "Keep watching."))
    first = hits[0]
    also = [{"rule": h[0], "label": h[1], "text": h[2]} for h in hits[1:]]
    text = first[2]
    if also:
        text += " If the value is real: " + also[0]["text"]
    return {"label": first[1], "rule": first[0], "text": text, "also": also}


def _driver_note(cause: dict) -> str:
    if cause["label"] == "none":
        return "No anomaly, so no cause to assign."
    tag = {"natural": "Natural", "mixed": "Mixed natural and human", "model artefact": "Possible model artefact",
           "pressure-related": "Pressure-related", "pressure": "Pressure", "possible pressure": "Possible pressure",
           "unexplained": "Unexplained", "climate": "Regional climate"}[cause["label"]]
    rule = f" (rule {cause['rule']})" if cause.get("rule") else ""
    return f"{tag}{rule}: {cause['text']}"


# ------------------------------------------------------------------------------------------- card skeleton
def _new(card_id: str) -> dict:
    return {"id": card_id, "title": TITLES[card_id], "status": "no_data", "value": None, "unit": "",
            "reference": {}, "z": None, "evidence": "model", "confidence": "low", "why": "", "driver_note": "",
            "investigate": [], "sources": [], "text": {p: "" for p in PROFILES}, "supporting": []}


def _sup(name, value, unit="", note="", threshold_type=None) -> dict:
    out = {"name": name, "value": value, "unit": unit, "note": note}
    if threshold_type:
        out["threshold_type"] = threshold_type
    return out


def _fmt(x, n=1, unit=""):
    if x is None:
        return "n/a"
    return f"{x:.{n}f}{(' ' + unit) if unit else ''}"


def _sign(x, n=1):
    return "n/a" if x is None else f"{x:+.{n}f}"


# ------------------------------------------------------------------------------------------- 1 temperature (P1, P6)
def _card_temperature(c, lat, lon, d, sector):
    s = _series("sst", lat, lon, d)
    cl = dh.get_climatology("sst", lat, lon)
    sst = s["sst"].asfreq("D").interpolate(limit=2)
    v, vd = dh.value_on(sst, d, 3)
    c["evidence"], c["unit"] = "satellite", "°C"
    c["sources"] += _src(s.attrs, vd)
    c["sources"].append({"dataset": cl.attrs.get("dataset"), "origin": "satellite", "date": None,
                         "distance_km": _r(cl.attrs.get("distance_km"), 1), "label": "climatology 1991-2020 (REP)"})
    if v is None:
        c["why"] = "No satellite SST in the 3 days up to this date."
        return None
    row = _clim_row(cl, vd)
    anom = v - row["mean"]
    z = anom / row["std"]
    j = _join_clim(sst.loc[:vd], cl)
    mhw = hobday_events(j["value"], j["p90"], j["mean"], above=True)
    mcs = hobday_events(j["value"], j["p10"], j["mean"], above=False)
    ongoing = [e for e in mhw + mcs if e["end"] >= vd - pd.Timedelta(days=1)]
    ev = ongoing[0] if ongoing else None
    kind = None
    if ev:
        kind = "warm" if ev in mhw else "cold"
    elif v > row["p90"]:
        kind = "warm"
    elif v < row["p10"]:
        kind = "cold"
    if ev and ev["category"] in ("strong", "severe", "extreme"):
        status = "alert"
    elif ev or kind:
        status = "watch"
    else:
        status = "normal"
    c.update(status=status, value=_r(v, 2), z=_r(z, 2))
    c["reference"] = {"value": _r(row["mean"], 2), "low": _r(row["p10"], 2), "high": _r(row["p90"], 2),
                      "period": "1991-2020", "basis": "day-of-year climatology of satellite SST (REP), 11-day window",
                      "threshold": T["mhw"][0], "threshold_source": T["mhw"][1], "threshold_type": "LIT + OURS"}
    # confidence: does the model agree on the sign of the anomaly?
    conf = "high"
    try:
        ms = _series("sst", lat, lon, d, source="model")
        mv, _ = dh.value_on(ms["sst"], vd, 2)
        mcl = dh.get_climatology("sst", lat, lon, source="model")
        manom = mv - _clim_row(mcl, vd)["mean"]
        if abs(anom) > 0.5 and np.sign(manom) != np.sign(anom):
            conf = "medium"
        c["supporting"].append(_sup("Model surface temperature anomaly", _r(manom, 2), "°C",
                                    "Copernicus physics model vs its 1993-2022 reanalysis climatology", "OURS"))
        c["sources"] += _src(ms.attrs, vd)
    except Exception:  # noqa: BLE001
        conf = "medium"
    c["confidence"] = conf
    # P6 bottom temperature anomaly (anfc bias-corrected)
    try:
        bt = _series("bottom_temp", lat, lon, d)
        bv, bd = dh.value_on(bt["bottom_temp"], d, 2)
        roles = [x.get("role") for x in bt.attrs.get("datasets", [])]
        corr = dh.BOTTOMT_ANFC_MINUS_REA if bd is not None and bd > dh.PHY_REA_END else 0.0
        bcl = dh.get_climatology("bottom_temp", lat, lon)
        br = _clim_row(bcl, bd)
        banom = (bv - corr) - br["mean"]
        c["supporting"].append(_sup("Bottom temperature anomaly (P6)", _r(banom, 2), "°C",
                                    f"model bottom level, {'forecast system corrected by -0.41 °C, ' if corr else ''}"
                                    f"vs reanalysis 1993-2022; value {_r(bv, 2)} °C", "OURS"))
    except Exception:  # noqa: BLE001
        pass
    yr = [e for e in mhw if e["start"].year == vd.year]
    c["supporting"].append(_sup("Marine heatwave days this year", int(sum(e["days"] for e in yr)), "days",
                                f"{len(yr)} events in {vd.year} up to {vd.date()} (window from {j.index[0].date()})", "LIT"))
    dr = drivers_at(lat, lon, d)
    cause = classify_cause(kind, dr, persist_days=(ev["days"] if ev else 0))
    c["driver_note"] = _driver_note(cause)
    if cause["label"] == "possible pressure":
        c["investigate"].append(INVESTIGATE["hotspot"])
    evtxt = ""
    if ev:
        evtxt = (f" A {ev['category']} marine {'heatwave' if kind == 'warm' else 'cold spell'} has been going on for "
                 f"{ev['days']} days (since {ev['start'].date()}).")
    c["why"] = (f"Sea surface {v:.1f} °C on {vd.date()}, {anom:+.1f} °C from the 1991-2020 normal "
                f"({row['mean']:.1f} °C; usual range {row['p10']:.1f}-{row['p90']:.1f} °C).{evtxt}")
    warm = "warmer" if anom > 0 else "colder"
    c["text"]["public"] = (f"The sea here is {v:.1f} °C, {abs(anom):.1f} °C {warm} than usual for this time of year."
                           + (f" That counts as a marine {'heatwave' if kind == 'warm' else 'cold spell'}." if ev else
                              " That is within the normal range." if status == "normal" else
                              " That is unusual, but not yet a heatwave or cold spell."))
    c["text"]["student"] = (f"Anomaly = today's satellite SST minus the 1991-2020 mean for the same date: {anom:+.2f} °C "
                            f"(z = {z:+.1f}). A marine heatwave is 5 or more days above the warmest 10 % for that date "
                            "(Hobday et al. 2016).")
    stake = {"aquaculture": "Mussels are stressed above about 25 °C; long heatwaves in summer raise mortality risk.",
             "tourism": "Warm water favours jellyfish and blooms; sudden cold water in summer usually means upwelling.",
             "fishing": "Sprat and anchovy shift depth and timing with temperature; expect changed catches during long anomalies.",
             "ports": "No direct effect on operations; warm summers increase fouling on hulls and structures.",
             "shipyards": "Warm water speeds hull fouling and the settlement of introduced species."}
    c["text"]["stakeholder"] = ((stake.get(sector) + " ") if sector else "") + \
        f"Status {status}: heatwave days this year {c['supporting'][-1]['value']}. Use it to plan, not to blame."
    c["text"]["researcher"] = (f"SST {v:.2f} °C ({', '.join(x['role'] for x in s.attrs['datasets'])}; NRT lowered by "
                               f"{dh.SST_NRT_MINUS_REP} °C), clim mean {row['mean']:.2f}, sd {row['std']:.2f}, p10 "
                               f"{row['p10']:.2f}, p90 {row['p90']:.2f} (DOY, 11-d window, 31-d smoothing). Events: "
                               f"Hobday 2016 recipe, fixed 1991-2020 baseline (includes the warming trend).")
    return cause


# ------------------------------------------------------------------------------------------- 2 oxygen (C1, C2, B5)
def _o2_class(mg: float) -> str:
    return "A" if mg >= 5 else "B" if mg >= 4 else "C" if mg >= 2 else "D"


CLASS_TXT = {"A": "A (meets the 5 mg/L level)", "B": "B (4-5 mg/L, below the good-status level)",
             "C": "C (2-4 mg/L, hypoxia risk)", "D": "D (below 2 mg/L, hypoxic)"}


def _card_oxygen(c, lat, lon, d, sector):
    ob = _series("o2_bottom", lat, lon, d)
    bo = ob["o2_bottom"]
    v, vd = dh.value_on(bo, d, 2)
    c["evidence"], c["unit"] = "model", "mg/L"
    c["sources"] += _src(ob.attrs, vd)
    if v is None:
        c["why"] = "No model bottom oxygen for this date."
        return None
    from_anfc = vd > dh.BGC_REA_END
    cls = _o2_class(v)
    status = {"A": "normal", "B": "watch", "C": "watch", "D": "alert"}[cls]
    c["value"] = _r(v, 2)
    c["reference"] = {"value": 5.0, "low": 2.0, "high": None, "classes": T["o2_classes"][0],
                      "basis": T["o2_classes"][1], "threshold_type": "OFFICIAL-RO (5 mg/L) + OURS (B, C) + LIT (2 mg/L)",
                      "season_test": T["d5c5"][0], "season_test_type": "OFFICIAL-RO"}
    # z only against the same model system (reanalysis); the forecast system has a ~2 mg/L offset
    try:
        cl = dh.get_climatology("o2_bottom", lat, lon)
        row = _clim_row(cl, vd)
        c["reference"]["normal_for_date"] = _r(row["mean"], 2)
        if not from_anfc:
            c["z"] = _r((v - row["mean"]) / row["std"], 2)
    except Exception:  # noqa: BLE001
        pass
    last30 = bo.loc[vd - pd.Timedelta(days=29):vd].dropna()
    c["supporting"].append(_sup("Hypoxia days (< 2 mg/L), last 30 days", int((last30 < 2).sum()), "days", "", "LIT"))
    c["supporting"].append(_sup("Days below 4 mg/L, last 30 days", int((last30 < 4).sum()), "days", "", "OURS"))
    ws = bo[(bo.index.year == vd.year) & bo.index.month.isin([5, 6, 7, 8, 9]) & (bo.index <= vd)].dropna()
    if len(ws) >= 60:
        p10 = float(ws.quantile(0.1))
        c["supporting"].append(_sup(f"D5C5 season test {vd.year}: May-Sep P10 bottom O2", _r(p10, 2), "mg/L",
                                    ("pass" if p10 >= 5 else "fail") + " on the concentration part (>= 5 mg/L); the "
                                    "60 % saturation part needs bottom T and S and is not computed here", "OFFICIAL-RO"))
    # C2 surface O2 saturation
    sat_flag = None
    try:
        so = _series("o2_sat", lat, lon, d)
        sv, sd = dh.value_on(so["o2_sat"], d, 2)
        if sv is not None:
            sat_flag = "high" if sv > 120 else "low" if sv < 80 else None
            c["supporting"].append(_sup("Surface O2 saturation (C2)", _r(sv, 1), "%",
                                        f"{so.attrs['label']}; flags > 120 % bloom, < 80 % respiration or upwelling",
                                        "OURS"))
            c["sources"] += _src(so.attrs, sd)
            if sat_flag and status == "normal":
                status = "watch"
    except Exception:  # noqa: BLE001
        pass
    c["status"] = status
    c["confidence"] = "low" if cls != "A" or from_anfc else "medium"
    dr = drivers_at(lat, lon, d)
    # bloom 1-4 weeks earlier (for rule 6)
    bloom_recent = False
    try:
        ch = _series("chl", lat, lon, d)["chl"]
        ccl = dh.get_climatology("chl", lat, lon)
        jj = _join_clim(ch.loc[vd - pd.Timedelta(days=28):vd - pd.Timedelta(days=7)], ccl)
        bloom_recent = bool((jj["value"] > jj["p90"]).any())
    except Exception:  # noqa: BLE001
        pass
    if cls in ("B", "C", "D"):
        kind = "low_o2_bottom"
        persist = 0
        for x in bo.loc[:vd].dropna()[::-1]:
            if x < 5:
                persist += 1
            else:
                break
        cause = classify_cause(kind, dr, model_only=from_anfc, persist_days=persist, bloom_recent=bloom_recent)
    elif sat_flag:
        cause = classify_cause("low_o2_surface" if sat_flag == "low" else "high_o2_surface", dr)
    else:
        cause = classify_cause(None, dr)
    c["driver_note"] = _driver_note(cause)
    if cls == "D":
        c["investigate"].append(INVESTIGATE["o2_D"])
    if cause["label"] == "possible pressure":
        c["investigate"].append(INVESTIGATE["hotspot"])
    off = (" The forecast model runs about 2 mg/L below the reanalysis, so read the class, not small changes."
           if from_anfc else "")
    c["why"] = (f"Bottom oxygen {v:.1f} mg/L on {vd.date()} (model, deepest level): class {CLASS_TXT[cls]}."
                + (f" Surface saturation {c['supporting'][-1]['value']} %." if sat_flag is not None or
                   (c['supporting'] and c['supporting'][-1]['unit'] == '%') else "") + off)
    c["text"]["public"] = ({"A": "There is enough oxygen near the seabed for fish and mussels.",
                            "B": "Oxygen near the seabed is a bit lower than it should be.",
                            "C": "Oxygen near the seabed is low; sensitive animals may be stressed.",
                            "D": "The seabed water is almost out of oxygen; animals there can die."}[cls]
                           + " This comes from a computer model, not a measurement.")
    c["text"]["student"] = (f"Bottom O2 {v:.1f} mg/L, class {cls}. Classes: A >= 5 mg/L (official good-status level), "
                            "B 4-5, C 2-4, D < 2 (hypoxia). Oxygen drops when the water is layered and dead algae "
                            "decay at the bottom.")
    stake = {"aquaculture": "Mussel lines near the bottom are exposed first; class C or D means check the stock.",
             "fishing": "Low bottom oxygen drives turbot and other bottom fish away and can kill benthic shellfish.",
             "tourism": "Low oxygen at the bottom rarely shows at the beach, except in rare summer fish kills.",
             "ports": "Dredging in late summer can release oxygen-consuming mud; avoid it during class C or D.",
             "shipyards": "No direct effect; discharges of organic waste make low oxygen worse."}
    c["text"]["stakeholder"] = ((stake.get(sector) + " ") if sector else "") + \
        f"Class {cls}: {'no action needed' if cls == 'A' else 'watch the next days' if cls in 'BC' else 'send divers or an ROV within 2 weeks'}."
    c["text"]["researcher"] = (f"o2b {v:.2f} mg/L ({'BLKSEA analysis/forecast' if from_anfc else 'BLKSEA BGC reanalysis'}, "
                               f"0.032 mg/L per mmol/m3). Rule 1 applies to forecast bottom O2 (anfc - rea about "
                               f"{dh.O2B_ANFC_MINUS_REA} mg/L in the 2024 overlap); no bottom sensor exists. Official "
                               "NIMRD 2018-2023 P10 at 20-50 m: 5.44 mg/L, 54.3 % saturation.")
    return cause


# ------------------------------------------------------------------------------------------- 3 blooms (B1, B2, D5C2, C3)
def _card_blooms(c, lat, lon, d, sector):
    s = _series("chl", lat, lon, d)
    cl = dh.get_climatology("chl", lat, lon)
    ch = s["chl"]
    v, vd = dh.value_on(ch, d, 3)
    c["evidence"], c["unit"] = "satellite", "mg/m³"
    c["sources"] += _src(s.attrs, vd)
    c["sources"].append({"dataset": cl.attrs.get("dataset"), "origin": "satellite", "date": None,
                         "distance_km": _r(cl.attrs.get("distance_km"), 1), "label": "climatology 1998-2020 (log space)"})
    if v is None:
        c["why"] = "No satellite chlorophyll in the 3 days up to this date."
        return None
    row = _clim_row(cl, vd)
    ratio = v / row["mean"]
    z = (math.log10(v) - math.log10(row["mean"])) / row["std"]
    j = _join_clim(ch.loc[:vd].dropna(), cl)
    above = (j["value"] > j["p90"])
    run = 0
    for x in above[::-1]:
        if x:
            run += 1
        else:
            break
    yr = j[j.index.year == vd.year]
    bloom_days_year = int((yr["value"] > yr["p90"]).sum())
    js = yr[yr.index.month.isin([6, 7, 8, 9])]
    bloom_days_summer = int((js["value"] > js["p90"]).sum())
    ws = ch[(ch.index.year == vd.year) & ch.index.month.isin([5, 6, 7, 8, 9]) & (ch.index <= vd)].dropna()
    d5c2_fail = None
    if len(ws) >= 30:
        p75 = float(ws.quantile(0.75))
        d5c2_fail = p75 > T["d5c2_coastal"][0]
        c["supporting"].append(_sup(f"D5C2 proxy {vd.year}: May-Sep P75 chl", _r(p75, 2), "mg/m³",
                                    f"{'fail' if d5c2_fail else 'pass'} vs {T['d5c2_coastal'][0]} (coastal); "
                                    "satellite surface proxy of the official in-situ test", "OFFICIAL-RO"))
        c["supporting"].append(_sup(f"May-Sep mean chl {vd.year}", _r(float(ws.mean()), 2), "mg/m³",
                                    f"vs {T['d5c2_marine'][0]} (marine waters south)", "OFFICIAL-RO"))
    c["supporting"].append(_sup(f"Bloom days {vd.year} (above p90)", bloom_days_year, "days",
                                f"June-September: {bloom_days_summer}", "OURS"))
    is_high = bool(v > row["p90"])
    summer = 6 <= vd.month <= 9
    if is_high and ((summer and run >= 5) or d5c2_fail):
        status = "alert"
    elif is_high or d5c2_fail:
        status = "watch"
    else:
        status = "normal"
    c.update(status=status, value=_r(v, 2), z=_r(z, 2))
    c["reference"] = {"value": _r(row["mean"], 2), "low": _r(row["p10"], 2), "high": _r(row["p90"], 2),
                      "period": "1998-2020", "basis": "day-of-year geometric mean of satellite chl, +-15 days, log space",
                      "threshold": f"above p90 = anomalous high (OURS); D5C2 May-Sep P75 <= {T['d5c2_coastal'][0]} mg/m³",
                      "threshold_type": "OURS + OFFICIAL-RO"}
    c["confidence"] = "medium" if (depth_at(lat, lon) or 99) < 20 else "high"
    # C3 simplified eutrophication index (one-out-all-out), as supporting
    try:
        er = {}
        if len(ws) >= 30:
            er["chl"] = float(ws.mean()) / T["d5c2_marine"][0]
        ob = _series("o2_bottom", lat, lon, d)["o2_bottom"]
        wo = ob[(ob.index.year == vd.year) & ob.index.month.isin([5, 6, 7, 8, 9])].dropna()
        if len(wo) >= 60:
            er["o2"] = 5.0 / float(wo.quantile(0.1))
        for var, key in (("din", "din_marine"), ("po4", "po4_marine")):
            w = dh.nutrient_windows(var, lat, lon)
            sm = w[w["season"] == "summer"]["value"].dropna()
            if len(sm):
                er[var] = float(sm.iloc[-1]) / T[key][0]
        if er:
            cats = {"nutrients": [er[k] for k in ("din", "po4") if k in er], "direct": [er["chl"]] if "chl" in er else [],
                    "indirect": [er["o2"]] if "o2" in er else []}
            cat = {k: float(np.mean(x)) for k, x in cats.items() if x}
            worst = max(cat, key=cat.get)
            cls = next(n for hi, n in HEAT_CLASSES if cat[worst] <= hi)
            c["supporting"].append(_sup("Eutrophication index (C3, simplified BEAST)", _r(cat[worst], 2), "ratio",
                                        f"{cls}, driven by {worst}; ratios " + ", ".join(f"{k} {v_:.2f}" for k, v_ in er.items())
                                        + ". Nutrients from DIVAnd windows, O2 from the model: low-medium confidence",
                                        "OFFICIAL-RO targets"))
    except Exception:  # noqa: BLE001
        pass
    dr = drivers_at(lat, lon, d)
    cause = classify_cause("high_chl" if is_high else None, dr, persist_days=run)
    if not is_high and d5c2_fail:
        cause = {"label": "mixed", "rule": None, "also": [],
                 "text": "Today's value is normal, but the season test failed: the summer chlorophyll level is above "
                         "the official coastal threshold. Danube nutrient load and coastal wastewater both feed it; "
                         "a single date cannot separate them."}
    c["driver_note"] = _driver_note(cause)
    if is_high and summer:
        c["investigate"].append(INVESTIGATE["bloom"])
    if cause["label"] == "possible pressure":
        c["investigate"].append(INVESTIGATE["hotspot"])
    c["why"] = (f"Chlorophyll {v:.2f} mg/m³ on {vd.date()}, {ratio:.1f} times the 1998-2020 normal for this date "
                f"({row['mean']:.2f}; p90 {row['p90']:.2f})." + (f" Above p90 for {run} days in a row." if run else "")
                + ("" if d5c2_fail is None else f" Official D5C2 proxy for {vd.year}: {'fail' if d5c2_fail else 'pass'}."))
    c["text"]["public"] = (f"The sea has {'much more' if ratio >= 2 else 'more' if ratio > 1.2 else 'about the usual amount of' if ratio >= 0.8 else 'less'} "
                           "microscopic algae than usual for this week." +
                           (" Water may look green or brown." if is_high else ""))
    c["text"]["student"] = (f"Satellite chlorophyll compared in log space with a 23-year day-of-year climatology: ratio "
                            f"{ratio:.2f}, z = {z:+.1f}. Values above the 90th percentile count as bloom days.")
    stake = {"aquaculture": "Blooms can carry toxic species; test shellfish before harvest when this is high in summer.",
             "tourism": "A high value means check bathing-water quality; discoloured water is the usual complaint.",
             "ports": "Dredging plumes can look like blooms on satellite images; check the clarity card too.",
             "fishing": "More algae means more food at first, but decaying blooms lower bottom oxygen later.",
             "shipyards": "No direct effect; nutrient-rich discharges feed blooms."}
    c["text"]["stakeholder"] = ((stake.get(sector) + " ") if sector else "") + \
        ("Early warning of an algal bloom, not proof of damage." if is_high else "No bloom signal now.")
    c["text"]["researcher"] = (f"CMEMS OC L4 gap-free 1 km ({', '.join(x['role'] for x in s.attrs['datasets'])}); "
                               f"clim gmean {row['mean']:.2f}, sd(log10) {row['std']:.3f}. Case-2 coastal water: CDOM "
                               "and sediment from the Danube can bias satellite chl upwards.")
    return cause


# ------------------------------------------------------------------------------------------- 4 clarity (P5, P7)
def _card_clarity(c, lat, lon, d, sector):
    s = _series("kd490", lat, lon, d)
    cl = dh.get_climatology("kd490", lat, lon)
    k = s["kd490"]
    v, vd = dh.value_on(k, d, 16)
    c["evidence"], c["unit"] = "satellite", "m"
    c["sources"] += _src(s.attrs, vd)
    c["sources"].append({"dataset": cl.attrs.get("dataset"), "origin": "satellite", "date": None,
                         "distance_km": _r(cl.attrs.get("distance_km"), 1), "label": "climatology 1998-2022 (log space)"})
    if v is None:
        c["why"] = "No cloud-free satellite Kd490 in the 16 days up to this date."
        return None
    row = _clim_row(cl, vd)
    kp = float(kdpar_from_kd490(v))
    secchi = SECCHI_C / kp
    ratio = v / row["mean"]
    zk = (math.log10(v) - math.log10(row["mean"])) / row["std"]
    murky = bool(v > row["p90"])
    if murky and ratio >= 2:
        status = "alert"
    elif murky:
        status = "watch"
    else:
        status = "normal"
    nsecchi = SECCHI_C / float(kdpar_from_kd490(row["mean"]))
    c.update(status=status, value=_r(secchi, 1), z=_r(-zk, 2))
    c["reference"] = {"value": _r(nsecchi, 1), "low": _r(SECCHI_C / float(kdpar_from_kd490(row["p90"])), 1),
                      "high": _r(SECCHI_C / float(kdpar_from_kd490(row["p10"])), 1), "period": "1998-2022",
                      "basis": "Secchi = 1.1 / Kd(PAR), Kd(PAR) from Kd490 (Morel 2007); normal = day-of-year "
                               "geometric mean of Kd490", "threshold": f"{T['secchi_ges'][1]} >= {T['secchi_ges'][0]} m",
                      "threshold_type": "OFFICIAL-RO + OURS (band)"}
    c["supporting"].append(_sup("Kd490", _r(v, 3), "1/m", f"{ratio:.1f} times normal; p90 {row['p90']:.3f}", "OURS"))
    z = depth_at(lat, lon)
    if z and z > 0:
        c["supporting"].append(_sup("Light reaching the seabed", _r(100 * math.exp(-kp * z), 2), "% of surface",
                                    f"depth {z:.0f} m (EMODnet); seagrass needs about 11 %, brown algae 0.5 %", "LIT"))
    ws = k[(k.index.year == vd.year) & k.index.month.isin([5, 6, 7, 8, 9]) & (k.index <= vd)].dropna()
    if len(ws) >= 20:
        sp10 = float(np.percentile(SECCHI_C / kdpar_from_kd490(ws.values), 10))
        c["supporting"].append(_sup(f"May-Sep P10 Secchi {vd.year}", _r(sp10, 1), "m",
                                    f"{'meets' if sp10 >= T['secchi_ges'][0] else 'below'} the {T['secchi_ges'][0]} m "
                                    "coastal GES value (satellite estimate)", "OFFICIAL-RO"))
    c["confidence"] = "medium"
    dr = drivers_at(lat, lon, d)
    if dr.get("hs_max3") is not None:
        c["supporting"].append(_sup("Max wave height, last 3 days (P7)", dr["hs_max3"], "m",
                                    f"storm threshold p95 {dr.get('hs_p95')} m", "OURS"))
    persist = 0
    if murky:
        jj = _join_clim(k.loc[:vd].dropna(), cl)
        for x in (jj["value"] > jj["p90"])[::-1]:
            if x:
                persist += 1
            else:
                break
    cause = classify_cause("low_clarity" if murky else None, dr, persist_days=persist)
    c["driver_note"] = _driver_note(cause)
    if cause["label"] == "possible pressure":
        c["investigate"].append(INVESTIGATE["hotspot"])
    c["why"] = (f"Estimated Secchi depth {secchi:.1f} m on {vd.date()} (normal for the date {nsecchi:.1f} m); Kd490 "
                f"{v:.3f} 1/m, {ratio:.1f} times normal.")
    c["text"]["public"] = (f"You could see about {secchi:.0f} m down here, "
                           + ("much murkier than usual." if status == "alert" else "murkier than usual." if murky else
                              "clearer than usual." if secchi > nsecchi * 1.2 else "about normal for the season."))
    c["text"]["student"] = ("Kd490 says how fast blue light fades with depth. Secchi depth is estimated as 1.1 / Kd(PAR), "
                            "tuned to NIMRD Secchi readings on this coast.")
    stake = {"ports": "Dredging and coastal works make plumes; plan them outside storm and bloom periods.",
             "tourism": "Murky water after storms is natural and clears in a few days.",
             "aquaculture": "Very turbid water clogs filter-feeding mussels; long episodes slow growth.",
             "fishing": "Turbid water changes where fish feed; it rarely matters for a single day.",
             "shipyards": "Hull cleaning and slipway works release fine sediment; contain it."}
    c["text"]["stakeholder"] = ((stake.get(sector) + " ") if sector else "") + \
        "Seagrass and mussel beds need clear water; long murky periods are what matters."
    c["text"]["researcher"] = (f"Kd490 {v:.3f} 1/m (CMEMS OC, L3 1 km or L4 when available; last cloud-free day "
                               f"{vd.date()}); Kd(PAR) {kp:.3f}; z(log Kd) {zk:+.2f}. Secchi factor 1.1 instead of the "
                               "open-water 1.7 (fit to INCDM 2018-2023 coastal Secchi).")
    return cause


# ------------------------------------------------------------------------------------------- 5 nutrients (C4, C5)
def _card_nutrients(c, lat, lon, d, sector):
    c["evidence"], c["unit"] = "measured", "µmol/L"
    er, vals, years = {}, {}, {}
    for var in ("din", "po4", "si"):
        try:
            w = dh.nutrient_windows(var, lat, lon)
            sm = w[(w["season"] == "summer") & (w.index.year <= d.year)]["value"].dropna()
            if len(sm):
                vals[var], years[var] = float(sm.iloc[-1]), int(sm.index[-1].year)
                if var == "din":
                    c["sources"].append({"dataset": w.attrs.get("dataset"), "origin": "derived",
                                         "date": str(sm.index[-1].date()), "distance_km": None,
                                         "label": "EMODnet Chemistry DIVAnd Black Sea, 6-year windows (from NIMRD and "
                                                  "other bottle data)"})
        except Exception:  # noqa: BLE001
            continue
    period = None
    if "din" not in vals and "po4" not in vals:
        # near the coast the 0.05 deg Black Sea windows are masked: use the 0.01 deg Danube-shelf seasonal climatology
        for var in ("din", "po4", "si"):
            try:
                ncl = dh.nutrient_climatology(var, lat, lon)
                x = ncl.loc["summer", "mean"] if "summer" in ncl.index else np.nan
                if np.isfinite(x):
                    vals[var], years[var] = float(x), None
                    if var == "din":
                        c["sources"].append({"dataset": ncl.attrs.get("dataset"), "origin": "derived", "date": "2000-2022",
                                             "distance_km": None, "label": "EMODnet Chemistry DIVAnd Danube Delta, "
                                             "seasonal climatology 2000-2022 (0.01 deg)"})
            except Exception:  # noqa: BLE001
                continue
        period = "seasonal climatology 2000-2022"
    if "din" not in vals and "po4" not in vals:
        c["why"] = "No trusted DIVAnd nutrient value at this point (6-year windows and 2000-2022 climatology both masked)."
        return None
    if "din" in vals:
        er["DIN"] = vals["din"] / T["din_marine"][0]
    if "po4" in vals:
        er["PO4"] = vals["po4"] / T["po4_marine"][0]
    worst = max(er, key=er.get)
    status = "normal" if er[worst] <= 1 else "watch" if er[worst] <= 1.5 else "alert"
    c.update(status=status, value=_r(vals.get("din"), 2))
    c["reference"] = {"value": T["din_marine"][0], "basis": T["din_marine"][1], "threshold_type": "OFFICIAL-RO",
                      "po4_threshold": T["po4_marine"][0], "coastal_thresholds": {"din": 13.5, "po4": 0.30},
                      "period": period or f"6-year window centred {years.get('din', years.get('po4'))}"}
    for var, unit in (("po4", "µmol/L"), ("si", "µmol/L")):
        if var in vals:
            c["supporting"].append(_sup(f"{var.upper()} summer", _r(vals[var], 3), unit, period or f"window centred {years[var]}",
                                        "OFFICIAL-RO" if var == "po4" else None))
    if "din" in vals and "po4" in vals:
        c["supporting"].append(_sup("N:P (C5)", _r(vals["din"] / vals["po4"], 1), "", "Redfield 16; above means P-limited", "LIT"))
    if "din" in vals and "si" in vals:
        c["supporting"].append(_sup("Si:N (C5)", _r(vals["si"] / vals["din"], 2), "", "about 1 for diatoms; below favours "
                                    "flagellates", "LIT"))
    for k_, v_ in er.items():
        c["supporting"].append(_sup(f"{k_} ratio to official marine threshold", _r(v_, 2), "",
                                    next(n for hi, n in HEAT_CLASSES if v_ <= hi), "OFFICIAL-RO"))
    try:
        _, a = dh._fetch_bottles("po4", lat, lon, "1900-01-01", "2100-01-01")
        c["supporting"].append(_sup("Last bottle sample with phosphate within 30 km", a.get("last_sample"), "",
                                    "EMODnet Chemistry; newer NIMRD data are not public", None))
    except Exception:  # noqa: BLE001
        pass
    c["confidence"] = "medium"
    yr = years.get("din", years.get("po4"))
    old = d.year - (yr or d.year)
    c["driver_note"] = ("Historical value, so the live rule chain does not apply. Nutrients on this coast come mostly "
                        "from the Danube (river load, partly human) and from wastewater outfalls; this value cannot "
                        "separate them. The model nitrate and phosphate are not used (rule 1).")
    c["why"] = (f"Summer DIN {vals.get('din', float('nan')):.1f} µmol/L and PO4 {vals.get('po4', float('nan')):.2f} "
                + (f"µmol/L in the DIVAnd {period} (the 6-year windows are masked this close to the coast). " if period
                   else f"µmol/L in the 6-year window centred {yr} ({old} years before this date). ")
                + f"Worst ratio to the official "
                f"marine threshold: {worst} {er[worst]:.2f}.")
    c["text"]["public"] = ("Nutrients are fertiliser for algae. These numbers are from past ship samples, "
                           + ("and they were above the official limit." if er[worst] > 1 else "and they were within the official limit."))
    c["text"]["student"] = ("DIN = nitrate + nitrite + ammonium. The ratio to the official threshold above 1 means "
                            "too many nutrients. N:P above 16 means phosphorus limits algal growth.")
    c["text"]["stakeholder"] = ("No live nutrient data exist for this coast after about 2020. "
                                + ("Wastewater operators and farms upstream are the levers. " if er[worst] > 1 else "")
                                + "Ask NIMRD for recent monitoring results.")
    c["text"]["researcher"] = ("EMODnet Chemistry DIVAnd Black Sea moving 6-year windows, surface, _L1 (relerr < 0.3) "
                               "values; official statistic is the P75 of samples, not a gridded mean. Model nitrate is "
                               "about 2x the observed shelf median, so it is not shown.")
    return {"label": "historical", "rule": None, "text": "", "also": []}


# ------------------------------------------------------------------------------------------- 6 bathing (C6)
@functools.lru_cache(maxsize=1)
def _bathing_table() -> pd.DataFrame:
    from .sources import emodnet_layers as el
    return el.bathing_water_history("RO")


def _card_bathing(c, lat, lon, d, sector):
    c["evidence"], c["unit"] = "measured", "class"
    bw = _bathing_table()
    sites = bw.drop_duplicates("site_id")[["site_id", "name", "lat", "lon"]].copy()
    sites["km"] = [dh.haversine_km(lat, lon, a, b) for a, b in zip(sites.lat, sites.lon)]
    near = sites[sites.km <= 10].sort_values("km")
    if near.empty:
        n1 = sites.sort_values("km").iloc[0]
        c["why"] = f"No designated bathing water within 10 km (nearest: {n1['name']}, {n1['km']:.0f} km)."
        c["text"] = {p: "No official bathing site near this point." for p in PROFILES}
        return {"label": "none", "rule": None, "text": "", "also": []}
    hist = bw[bw.site_id.isin(near.site_id) & (bw.year <= d.year)].dropna(subset=["class_code"])
    if hist.empty:
        c["why"] = "No classified season up to this date for the nearby sites."
        return None
    y = int(hist.year.max())
    last = hist[hist.year == y].merge(near[["site_id", "km"]], on="site_id").sort_values("km")
    first = last.iloc[0]
    label = str(first["class"]).split(" - ", 1)[-1]
    worst = int(last["class_code"].max())
    comparable = y >= 2015
    code = int(first["class_code"])
    status = "normal" if code <= 2 else "watch" if code == 3 else "alert"
    if worst >= 3 and status == "normal":
        status = "watch"
    if not comparable:
        status = "watch" if code >= 3 else "normal"
    c.update(status=status, value=label)
    c["reference"] = {"value": "Excellent or Good", "basis": T["bwd"][1], "threshold": T["bwd"][0],
                      "threshold_type": "OFFICIAL-EU", "season": f"{y}", "scheme": first["scheme"]}
    counts = last["class"].value_counts().to_dict()
    c["supporting"].append(_sup(f"Sites within 10 km, season {y}", len(last), "sites",
                                "; ".join(f"{k}: {v}" for k, v in counts.items()), "OFFICIAL-EU"))
    hs = hist[hist.site_id == first["site_id"]].sort_values("year")
    c["supporting"].append(_sup(f"History of {first['name']}", ", ".join(f"{int(r.year)} {str(r['class']).split(' - ')[-1]}"
                                                                          for _, r in hs[hs.year >= 2015].iterrows()),
                                "", "2015 onwards (Directive 2006/7/EC)", "OFFICIAL-EU"))
    c["sources"].append({"dataset": "EMODnet Human Activities, emodnet:bathingwaters (EEA BWD reporting)",
                         "origin": "in-situ", "date": str(y), "distance_km": _r(first["km"], 1),
                         "label": f"{first['name']} ({first['site_id']})", "trust": "good"})
    c["confidence"] = "high" if comparable else "low"
    c["driver_note"] = ("Bathing class comes from lab tests for faecal bacteria over four seasons; it reflects sewage "
                        "and runoff (pressure), not natural variability.")
    if code >= 3 or worst >= 3:
        c["investigate"].append(INVESTIGATE["bathing"])
    notes = []
    if not comparable:
        notes.append("Seasons before 2015 used an older scheme and are not comparable.")
    if y < d.year:
        notes.append(f"Latest classified season is {y}.")
    if not in_season(d):
        notes.append("The bathing season runs 1 June to 15 September.")
    c["why"] = (f"Nearest official bathing site {first['name']} ({first['km']:.1f} km): {label} in {y}. "
                + " ".join(notes))
    c["text"]["public"] = f"The nearest official beach, {first['name']}, was rated {label} for swimming in {y}."
    c["text"]["student"] = ("The EU class uses four years of E. coli and intestinal enterococci tests. Excellent means "
                            "very low faecal bacteria.")
    c["text"]["stakeholder"] = ("Tourism: " if sector == "tourism" else "") + \
        ("Sufficient or Poor means check nearby wastewater outfalls before the next season."
         if status != "normal" else "The class supports bathing; keep sewage overflows under control in storms.")
    c["text"]["researcher"] = ("EMODnet HA bathing waters layer, per-season 'status' field (matches the EEA 2025 "
                               "factsheet: 2022 45/4, 2023 34/15, 2024 41/8 Excellent/Good).")
    return {"label": "none", "rule": None, "text": "", "also": []}


# ------------------------------------------------------------------------------------------- 7 biodiversity (B6, B7)
OBIS = "https://api.obis.org/v3"
BOX_RO_WKT = "POLYGON((28.4 43.6,30.6 43.6,30.6 45.4,28.4 45.4,28.4 43.6))"


def _obis_checklist(wkt: str, startdate: str | None, enddate: str | None) -> list[dict]:
    p = cached_path("obis", cache_key("checklist_v1", wkt, startdate, enddate), "json")
    if p.exists():
        return json.loads(p.read_text())
    import requests
    params = {"geometry": wkt, "size": 5000}
    if startdate:
        params["startdate"] = startdate
    if enddate:
        params["enddate"] = enddate
    r = requests.get(OBIS + "/checklist", params=params, timeout=120,
                     headers={"User-Agent": "marinekit-hackathon/0.1 (python-requests)"})
    r.raise_for_status()
    res = [{"name": x.get("scientificName"), "records": x.get("records", 0), "class": x.get("class")}
           for x in r.json().get("results", [])]
    p.write_text(json.dumps(res))
    return res


def _card_biodiversity(c, lat, lon, d, sector):
    c["evidence"], c["unit"] = "measured", "species"
    dlat, dlon = 0.15, 0.2
    wkt = (f"POLYGON(({lon - dlon:.2f} {lat - dlat:.2f},{lon + dlon:.2f} {lat - dlat:.2f},{lon + dlon:.2f} "
           f"{lat + dlat:.2f},{lon - dlon:.2f} {lat + dlat:.2f},{lon - dlon:.2f} {lat - dlat:.2f}))")
    recent = _obis_checklist(wkt, "2015-01-01", None)
    # "new" = no record anywhere on the Romanian coast before 2015 (a local box misses long-established species)
    before = _obis_checklist(BOX_RO_WKT, None, "2014-12-31")
    rec_n = int(sum(x["records"] for x in recent))
    names_recent = {x["name"]: x["records"] for x in recent}
    names_before = {x["name"] for x in before}
    c["sources"].append({"dataset": "OBIS checklist API (api.obis.org)", "origin": "in-situ",
                         "date": "2015-present", "distance_km": None,
                         "label": f"box +-{dlat} deg lat, +-{dlon} deg lon around the point", "trust": "good"})
    nis_recent = [n for n, (g, isn) in NIS.items() if isn and n in names_recent]
    gel_recent = [n for n, (g, isn) in NIS.items() if not isn and n in names_recent]
    new_nis = [n for n in nis_recent if n not in names_before]
    if rec_n < 50:
        c["why"] = f"Only {rec_n} biological records since 2015 in this box: too little sampling to say anything."
        c["status"] = "no_data"
        c["value"] = len(nis_recent)
        c["text"] = {p: "Almost nobody has sampled sea life here since 2015." for p in PROFILES}
        return {"label": "none", "rule": None, "text": "", "also": []}
    pz = pressure_at(lat, lon, d)
    entry = [s_ for s_ in ("ports", "shipyards") if s_ in pz["sectors"]]
    status = "watch" if new_nis or (nis_recent and entry) else "normal"
    c.update(status=status, value=len(nis_recent))
    c["reference"] = {"value": None, "basis": "presence over sampling effort, never a trend (biological.md B6)",
                      "threshold": "watch when a tracked non-indigenous species has no record on the Romanian coast "
                                   "before 2015, or when non-indigenous species are present inside a port or shipyard "
                                   "zone (entry points)", "threshold_type": "OURS"}
    c["supporting"].append(_sup("Records since 2015 in the box (sampling effort, B7)", rec_n, "records",
                                f"{len(recent)} taxa", None))
    c["supporting"].append(_sup("Non-indigenous species recorded since 2015", ", ".join(nis_recent) or "none", "",
                                "established invaders unless listed as new", None))
    c["supporting"].append(_sup("Gelatinous and bloom species recorded since 2015", ", ".join(gel_recent) or "none", "",
                                "", None))
    c["confidence"] = "medium" if nis_recent else "low"
    if (new_nis or nis_recent) and entry:
        c["investigate"].append(INVESTIGATE["nis_port"])
    c["driver_note"] = ("Introduced species arrive mainly with ballast water and hull fouling (ports, shipyards). "
                        "Records reflect where people sampled, so absence is weak evidence.")
    c["why"] = (f"{len(nis_recent)} of the {sum(1 for v in NIS.values() if v[1])} tracked non-indigenous species have "
                f"OBIS records since 2015 near this point ({rec_n} records in all)."
                + (f" New on the Romanian coast since 2015: {', '.join(new_nis)}." if new_nis else
                   " All are long-established invaders.")
                + (f" The point is inside a {' and '.join(entry)} zone, an entry route." if entry and nis_recent else ""))
    c["text"]["public"] = ("Introduced species such as the rapa whelk or the comb jelly have been seen here."
                           if nis_recent else "No introduced species from our list have been reported here since 2015.")
    c["text"]["student"] = ("OBIS occurrence records. Many records means many observers, not necessarily many "
                            "animals, so we show presence and sampling effort, never a trend.")
    c["text"]["stakeholder"] = ((("Ports and shipyards are the entry points; new sightings near a terminal mean checking "
                                  "ballast-water and hull-cleaning practice.") if sector in ("ports", "shipyards") else
                                 "Jellyfish and comb jellies affect beaches and fishing nets in late summer.")
                                + (" A new species has appeared since 2015." if new_nis else ""))
    c["text"]["researcher"] = (f"OBIS /checklist for the box, split at 2015-01-01; {len(recent)} taxa since 2015 vs "
                               f"{len(before)} before. Presence-only, effort-biased.")
    return {"label": "none", "rule": None, "text": "", "also": []}


# ------------------------------------------------------------------------------------------- 8 drivers (P2, P3, P4, P7)
def _card_drivers(c, lat, lon, d, sector):
    dr = drivers_at(lat, lon, d)
    c["evidence"], c["unit"] = "model", "x normal"
    c["sources"] += dr.get("sources", [])
    active = []
    r = dr.get("danube_ratio30")
    if r is not None and (r > 1.2 or r < 0.6):
        active.append(f"Danube flow {r:.2f} times normal")
    if dr.get("upwelling"):
        active.append("upwelling")
    if dr.get("storm"):
        active.append("storm in the last 3 days")
    if dr.get("stratified"):
        active.append("stratified water column")
    c["status"] = "watch" if active else ("normal" if r is not None else "no_data")
    c["value"] = r
    c["reference"] = {"value": 1.0, "basis": "Danube discharge 30-day mean / 1997-2025 day-of-year mean (GloFAS)",
                      "threshold": "river influence when > 1.2 or salinity < 14; upwelling when coast - offshore SST "
                                   "<= -2 °C (Jun-Sep); storm when Hs > p95; stratified when surface - bottom T > 2 °C "
                                   "(May-Oct)", "threshold_type": "OURS"}
    sal = dr.get("sal")
    c["supporting"] += [
        _sup("Danube discharge today (P3)", dr.get("danube_q"), "m³/s", f"spring {dr.get('spring_q')} vs p75 "
             f"{dr.get('spring_p75')}", "OURS"),
        _sup("Surface salinity", sal, "PSU", f"anomaly {_sign(dr.get('sal_anom'), 2)} vs 1993-2022", "OURS"),
        _sup("Upwelling (P2)", ("yes" if dr.get("upwelling") else "no") if dr.get("upwelling") is not None else
             "not in season (June-September only)", "", f"coast - offshore SST {dr.get('upwelling_dT')} °C", "OURS"),
        _sup("Stratification (P4)", dr.get("strat_dT"), "°C", "surface minus bottom temperature, model", "OURS"),
        _sup("Storm (P7)", dr.get("hs_max3"), "m", f"max Hs last 3 days; p95 {dr.get('hs_p95')} m", "OURS"),
        _sup("Bottom salinity", dr.get("bottom_sal"), "PSU", "above 18.5 means shelf-break water (rule 3)", "OURS"),
        _sup("Sector pressure zones here", ", ".join(dr["pressure"]["sectors"]) or
             ("none" if dr["pressure"].get("n") == 0 else "unknown"), "", dr["pressure"].get("source") or "", None),
    ]
    c["confidence"] = "medium"
    c["driver_note"] = "Drivers explain natural variability. They are shown beside every card and never count as damage."
    c["why"] = ("Active now: " + ", ".join(active) + "." if active else "No strong natural driver is active.") + \
        (f" Danube at {r:.2f} times its normal flow; surface salinity {sal} PSU." if r is not None else "")
    lowflow = r is not None and r < 0.8
    c["text"]["public"] = ((f"The Danube is carrying {'more' if r and r > 1 else 'less'} water than usual "
                            f"({r:.0%} of normal), " if r is not None else "") +
                           ("so the sea here is saltier and clearer than usual." if lowflow else
                            "so expect fresher, murkier water." if r and r > 1.2 else "close to normal."))
    c["text"]["student"] = ("The Danube supplies most of the river water and nutrients here; its plume reaches Constanța "
                            "about a month later. Winds cause upwelling; storms stir the seabed; summer heating "
                            "layers the water.")
    c["text"]["stakeholder"] = ("Use drivers to anticipate, not to blame: high Danube flow means blooms are likely 2-6 "
                                "weeks later; south-west winds in summer mean sudden cold water.")
    c["text"]["researcher"] = ("GloFAS v4 (Open-Meteo), 30-day mean vs DOY mean 1997-2025; upwelling index after "
                               "physical.md P2 (88 % of events follow 3 days of S/SW wind); stratification as Ts - Tb "
                               "from the physics model; storm p95 from Open-Meteo hourly Hs 2021-2025."
                               + (f" Errors: {'; '.join(dr['errors'])}" if dr.get("errors") else ""))
    return {"label": "none", "rule": None, "text": "", "also": []}


# ------------------------------------------------------------------------------------------- 9 acidification (C7)
def _card_acidification(c, lat, lon, d, sector):
    s = _series("ph", lat, lon, d)
    v, vd = dh.value_on(s["ph"], d, 2)
    c["evidence"], c["unit"] = "model", "pH"
    c["sources"] += _src(s.attrs, vd)
    if v is None:
        c["why"] = "No model pH for this date."
        return None
    cl = dh.get_climatology("ph", lat, lon)
    row = _clim_row(cl, vd)
    anom = v - row["mean"]
    z = anom / row["std"]
    low = bool(v < row["p10"])
    c.update(status="watch" if low else "normal", value=_r(v, 3), z=_r(z, 2), confidence="low")
    c["reference"] = {"value": _r(row["mean"], 3), "low": _r(row["p10"], 3), "high": _r(row["p90"], 3),
                      "period": "1993-2022", "basis": "day-of-year climatology of the BGC reanalysis",
                      "threshold": "watch below p10; never alert (model only)", "threshold_type": "OURS"}
    dr = drivers_at(lat, lon, d)
    cause = classify_cause("low_ph" if low else None, dr, persist_days=0)
    c["driver_note"] = _driver_note(cause)
    c["why"] = f"Model surface pH {v:.3f} on {vd.date()}, {anom:+.3f} from the 1993-2022 normal for the date."
    c["text"]["public"] = ("Sea water acidity is " + ("a little higher than usual." if low else "normal.")
                           + " This is a model estimate only.")
    c["text"]["student"] = ("Lower pH means more acidic water, which makes it harder for mussels to build shells. "
                            "No measurements exist here; this is model output.")
    c["text"]["stakeholder"] = ("Aquaculture: " if sector == "aquaculture" else "") + \
        "Watch only. Acidification is a slow, global trend; local dips come with upwelling or decaying blooms."
    c["text"]["researcher"] = (f"BLKSEA BGC pH (total scale) {v:.3f}, clim mean {row['mean']:.3f}, sd {row['std']:.3f}; "
                               "no in-situ pH after the 1990s near Constanța.")
    return cause


_FUN = {"temperature": _card_temperature, "oxygen": _card_oxygen, "blooms": _card_blooms, "clarity": _card_clarity,
        "nutrients": _card_nutrients, "bathing": _card_bathing, "biodiversity": _card_biodiversity,
        "drivers": _card_drivers, "acidification": _card_acidification}


# ------------------------------------------------------------------------------------------- public API
def card(card_id: str, lat: float, lon: float, date=None, profile: str = "public") -> dict:
    """One health card at a point and date. Never raises for missing data: returns status "no_data" with the reason
    in 'why'. profile is "public", "student", "stakeholder" (optionally "stakeholder:<sector>"), or "researcher";
    the text dict always holds all four, and the sector adds a sector-specific sentence to text["stakeholder"]."""
    if card_id not in _FUN:
        raise KeyError(f"unknown card {card_id!r}; known: {CARDS}")
    d = _ts(date if date is not None else dh.today())
    lat, lon = round(float(lat), 4), round(float(lon), 4)
    _, sector = _parse_profile(profile)
    c = _new(card_id)
    t0 = time.time()
    try:
        _FUN[card_id](c, lat, lon, d, sector)
    except Exception as e:  # noqa: BLE001
        c["status"] = "no_data"
        c["why"] = f"Could not compute: {type(e).__name__}: {str(e)[:300]}"
        c["error"] = traceback.format_exc(limit=3)
    if c["status"] == "no_data":
        for p in PROFILES:
            if not c["text"].get(p):
                c["text"][p] = ("No data for this card here and now. " + (c["why"] or "")).strip()
    for p in PROFILES:
        if not c["text"].get(p):
            c["text"][p] = c["why"]
    if not c["driver_note"]:
        c["driver_note"] = "No cause assigned (no data)." if c["status"] == "no_data" else "No anomaly, so no cause to assign."
    c["seconds"] = round(time.time() - t0, 2)
    return c


def all_cards(lat: float, lon: float, date=None, profile: str = "public") -> list[dict]:
    return [card(cid, lat, lon, date, profile) for cid in CARDS]


def _as_geom(z):
    from shapely.geometry import Point, shape
    if isinstance(z, (tuple, list)) and len(z) == 2 and all(isinstance(x, (int, float)) for x in z):
        return Point(z[1], z[0])          # (lat, lon)
    if isinstance(z, dict):
        if "lat" in z and "lon" in z:
            return Point(z["lon"], z["lat"])
        if z.get("type") == "Feature":
            return shape(z["geometry"])
        if z.get("type") == "FeatureCollection":
            from shapely.ops import unary_union
            return unary_union([shape(f["geometry"]) for f in z["features"]])
        return shape(z)
    return z                                # shapely geometry


def zone_sample_points(geom, samples: int = 1) -> list[tuple[float, float, str]]:
    """Points (lat, lon, how) used for a zone: its centroid when it lies inside the zone, else a point guaranteed
    to be inside (shapely representative_point); with samples > 1, extra random points inside (fixed seed)."""
    if geom.geom_type == "Point":
        return [(geom.y, geom.x, "point")]
    c = geom.centroid
    pts = [(c.y, c.x, "centroid of the zone")] if geom.contains(c) else \
        [(geom.representative_point().y, geom.representative_point().x, "interior point of the zone (centroid falls outside)")]
    if samples > 1:
        from shapely.geometry import Point
        rng = np.random.default_rng(42)
        x0, y0, x1, y1 = geom.bounds
        tries = 0
        while len(pts) < samples and tries < 500:
            tries += 1
            p = Point(rng.uniform(x0, x1), rng.uniform(y0, y1))
            if geom.contains(p):
                pts.append((p.y, p.x, f"random interior sample {len(pts)}"))
    return [(round(a, 4), round(b, 4), h) for a, b, h in pts]


def zone_cards(zone_geom_or_point, date=None, profile: str = "public", samples: int = 1) -> list[dict]:
    """All cards for a point, (lat, lon) tuple, {"lat","lon"} dict, GeoJSON geometry / Feature, or shapely geometry.

    For a polygon the cards are computed at its centroid (or an interior point when the centroid falls outside);
    samples > 1 adds random interior points and keeps, per card, the worst status. The point(s) used are listed in
    each card's sources as {"dataset": "zone sampling", "origin": "derived", ...}. Model and satellite grids snap to
    the nearest sea cell, so a centroid on the beach is served by the nearest sea pixel (its distance is in sources)."""
    g = _as_geom(zone_geom_or_point)
    pts = zone_sample_points(g, samples)
    per_pt = [all_cards(la, lo, date, profile) for la, lo, _ in pts]
    out = []
    for i, cid in enumerate(CARDS):
        cands = [cs[i] for cs in per_pt]
        best = max(range(len(cands)), key=lambda k: _RANK[cands[k]["status"]])
        cc = dict(cands[best])
        cc["sources"] = list(cc["sources"]) + [
            {"dataset": "zone sampling", "origin": "derived", "date": None, "distance_km": None,
             "label": f"{h} at {la:.4f} N {lo:.4f} E" + (" (card taken from this point: worst status)" if j == best and len(pts) > 1 else ""),
             "trust": None}
            for j, (la, lo, h) in enumerate(pts)]
        out.append(cc)
    return out


def card_summary(cards: list[dict]) -> pd.DataFrame:
    """Compact table for logs and tests: id, status, value, unit, z, evidence, confidence, seconds."""
    return pd.DataFrame([{k: c.get(k) for k in ("id", "status", "value", "unit", "z", "evidence", "confidence", "seconds")}
                         for c in cards])
