"""Methods page content: where new measurements are needed, and the uncertainty explained per user level.

Read-only and offline: this module never downloads anything. It reads the committed results of the source validation
(`docs/indicators/validation/`, through `marinekit.validation`), the seasonal quality gate
(`docs/indicators/seasonal/gate_summary.csv` and `trends_long.csv`), the per-variable sensor trust flags
(`marinekit.datahub.VARIABLE_TRUST` / `PLATFORMS`) and the threshold labels (`marinekit.indicators.T`).

Public functions (stable contract; additive changes only)
---------------------------------------------------------
- `measurement_needs(profile=None) -> pandas.DataFrame`: one row per measurement need, ranked. Full columns
  (profile None or "researcher"):
    rank (int, 1 = most needed), need_id, variable, where, lat, lon (approximate point for a map marker),
    what (what to measure), how (how to measure it), why (one plain sentence), cost (low | medium | high | none),
    who (who could act), sectors (affected sectors, joined with ", "; information only, not a criterion),
    disagree, no_trusted_insitu, untrusted_sensor, time_gap, decision_at_stake (bool, the five criteria),
    n_reasons (int 0-5, plain count of the five criteria), reasons (plain names of the criteria met, joined "; "),
    evidence (one line per criterion with the numbers, joined " | "), hand_set (criteria set by hand, not computed),
    label (provenance of the criteria and thresholds).
  With a profile ("public", "student", "stakeholder", "stakeholder:<sector>", or the viewer's profile dict with
  "role" and "sector"), a reduced set of columns is returned (see PROFILE_COLUMNS); for a stakeholder with a sector,
  a bool column `concerns_you` is added (the sector is in `sectors`). The ranking never changes with the profile.
- `uncertainty_text(variable, profile="public") -> str`: markdown text about the uncertainty of one variable, written
  for the profile. variable: sst, chl, sal, o2, o2_bottom, no3, po4 (aliases: temperature, chlorophyll, blooms,
  salinity, oxygen, bottom_oxygen, nutrients, nitrate, phosphate). Unknown variable -> ValueError.
- `uncertainty_primer(profile="public") -> str`: short markdown introduction (measured, satellite, model, and what
  "uncertainty" means) for the top of the Methods page.
- `uncertainty_variables() -> list[str]`: the variable ids accepted by `uncertainty_text`.

Ranking rule (OURS; no weights, no composite index)
---------------------------------------------------
Five yes/no criteria per need, counted:
  D  disagree            the sources disagree by more than the variable's own typical error: |bias| > the
                         indicative uncertainty of `validation.source_summary`, or R2 of the anomalies (monthly
                         means removed) < 0.3; for nutrients (z-scores) Spearman < 0.5. Thresholds OURS.
  N  no_trusted_insitu   no in-situ sensor with trust good or usable is reporting there (data within the last 60
                         days of the run date, OURS).
  S  untrusted_sensor    a sensor exists there but is flagged indicative, untrusted or not usable (cheap to fix).
  T  time_gap            no trusted source passes the trend gate there (8 complete years, OURS), or the in-situ record
                         has ended, or there is none.
  P  decision_at_stake   an OFFICIAL-RO or OFFICIAL-EU threshold depends on this variable.
Order: more reasons first; then needs behind an OFFICIAL threshold; then the cheaper action; then the order below.

Viewer usage
------------
    from marinekit import methods as M
    st.markdown(M.uncertainty_primer(profile))
    st.dataframe(M.measurement_needs(profile))
    st.markdown(M.uncertainty_text("o2", "stakeholder:aquaculture"))
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import datahub as dh
from . import indicators as ind
from . import validation as val

ROOT = Path(__file__).resolve().parents[2]
SEASONAL_DIR = ROOT / "docs" / "indicators" / "seasonal"
RUN_DATE = val.RUN_DATE
REPORTING_DAYS = 60                   # OURS: a sensor counts as reporting if its record ends within this many days
DISAGREE_R2_ANOM = 0.3                # OURS
DISAGREE_SPEARMAN = 0.5               # OURS
TREND_MIN_YEARS = 8                   # OURS, same as marinekit.seasonal
COST_ORDER = {"low": 0, "medium": 1, "high": 2, "none": 3}
CRITERIA = {"disagree": "sources disagree", "no_trusted_insitu": "no trusted in-situ sensor",
            "untrusted_sensor": "sensor exists but is not trusted", "time_gap": "gap in time",
            "decision_at_stake": "an official threshold depends on it"}
LABEL = (f"Criteria, ranking and thresholds OURS; evidence from the validation and seasonal results of {RUN_DATE}; "
         "all numbers indicative")
PROFILES = ("public", "student", "stakeholder", "researcher")
SECTORS = ("ports", "shipyards", "tourism", "fishing", "aquaculture")
PROFILE_COLUMNS = {
    "public": ["rank", "what", "where", "why"],
    "student": ["rank", "what", "where", "why", "reasons", "n_reasons"],
    "stakeholder": ["rank", "what", "where", "why", "how", "who", "cost", "sectors", "n_reasons"],
}

_OB = ["EUXRoOB01", "EUXRoOB02", "EUXRoOB03"]
_CB = ["EUXRoCB01", "EUXRoCB02", "EUXRoCB03"]
_BOTTLES = ["Constanta bottles"]

# Hand-written part of each need (what, where, how, who). The five criteria are computed from the result files,
# except where `hand` gives a value with its evidence (no matched data to compute it).
_NEEDS: list[dict] = [
    dict(need_id="chl_buoys", variables=["chl"], stations=_OB, pair="in situ vs satellite", platforms=_OB,
         thresholds=["d5c2_marine"], sectors=["fishing", "aquaculture"],
         where="Offshore buoys EUXRoOB01-03", lat=44.325, lon=30.41,
         what="Chlorophyll-a in bottle samples, to calibrate the buoy fluorometers",
         how="Take a surface bottle sample for chlorophyll extraction at every buoy service visit (monthly if "
             "possible); compare it with the night-time fluorescence (avoids daytime quenching); clean the optical "
             "window.",
         why="The buoys read 2 to 3 times more chlorophyll than the satellite and the model, so offshore algae "
             "levels cannot be checked against any trusted measurement.",
         cost="low", who="GeoEcoMar (buoy operator), NIMRD laboratory"),
    dict(need_id="o2_coast", variables=["o2"], stations=_BOTTLES, pair="in situ vs model", platforms=_CB,
         thresholds=["o2_classes"], sectors=["tourism", "aquaculture", "fishing"],
         where="Coastal waters, Constanta - Mamaia", lat=44.20, lon=28.68,
         what="Surface dissolved oxygen from a checked coastal sensor",
         how="Confirm the oxygen units and the quality control of the coastal buoys EUXRoCB01-03 (question 4 for "
             "NIMRD), then check them against Winkler bottle samples at each service visit.",
         why="At the coast the model reads about 1.5 mg/L less oxygen than the water samples, and the new coastal "
             "buoys are not yet trusted, so coastal oxygen has no reliable check.",
         cost="low", who="NIMRD, GeoEcoMar"),
    dict(need_id="o2_bottom", variables=["o2_bottom"], stations=[], pair=None, platforms=[],
         thresholds=["d5c5"], sectors=["aquaculture", "fishing"],
         where="North-western shelf bottom water, 20-40 m, including the mussel farms Mangalia - 2 Mai "
               "(May to September)", lat=43.80, lon=28.75,
         what="Bottom dissolved oxygen, about 1 m above the seabed, May to September",
         how="A bottom oxygen sensor (optode) on a mooring at the mussel farms, or monthly CTD casts with an oxygen "
             "sensor at 20, 30 and 40 m depth from May to September.",
         why="Oxygen near the seabed is where fish and mussels can suffocate, and no sensor measures it near the "
             "coast: the dashboard relies on models that disagree with each other.",
         cost="high", who="NIMRD, aquaculture operators",
         hand=dict(disagree=(True, "Copernicus BGC bottom O2: model systems disagree by about 2 mg/L "
                                   "(docs/indicators/SHORTLIST.md section 4); no measurement to compare"))),
    dict(need_id="chl_plume", variables=["chl"], stations=_BOTTLES, pair="in situ vs satellite", platforms=[],
         thresholds=["d5c2_coastal"], sectors=["tourism", "aquaculture"],
         where="Nearshore strip within 20 km of the coast, Danube plume from Sulina to Constanta",
         lat=44.70, lon=29.10,
         what="Nearshore chlorophyll-a in bottle samples, with suspended matter to check the satellite",
         how="A monthly bottle transect along the coast from Sulina to Constanta (stations 1, 5 and 20 km from "
             "shore), with chlorophyll extraction and suspended matter.",
         why="Near the coast river sediment can make the satellite overstate chlorophyll, and only 3 water samples "
             "exist to check it.",
         cost="medium", who="NIMRD"),
    dict(need_id="nutrients", variables=["no3", "po4"], stations=_BOTTLES, pair="in situ vs model", platforms=[],
         thresholds=["din_coastal", "po4_coastal"], sectors=["aquaculture", "tourism", "fishing"],
         where="Coastal stations Constanta, Mamaia, Eforie", lat=44.17, lon=28.70,
         what="Nitrate, nitrite, ammonium and phosphate (DIN, PO4) in bottle samples",
         how="Ask NIMRD for their monitoring data after 2021 (question 1); then monthly bottles at Constanta, "
             "Mamaia and Eforie.",
         why="The model cannot be used for nutrient levels and the water samples we have end years ago, so the "
             "nutrient status today is unknown.",
         cost="medium", who="NIMRD"),
    dict(need_id="sal_buoys", variables=["sal"], stations=_OB, pair="in situ vs model", platforms=_OB,
         thresholds=[], sectors=["shipyards", "aquaculture"],
         where="Offshore buoys EUXRoOB01-03", lat=44.71, lon=30.76,
         what="Surface salinity from a clean conductivity cell",
         how="Clean or replace the conductivity cell at EUXRoOB01-03; take a bottle salinity sample at each service "
             "visit to check the sensor.",
         why="The buoy salinity drops for weeks to months in a way that looks like a dirty sensor, so offshore "
             "salinity comes from the model only.",
         cost="low", who="GeoEcoMar (buoy operator)"),
    dict(need_id="buoy_continuity", variables=["o2"], stations=_OB, pair="in situ vs model", platforms=_OB,
         thresholds=[], sectors=["fishing", "aquaculture"],
         where="Offshore buoys EUXRoOB01-03", lat=43.977, lon=29.924,
         what="Keep the offshore buoys measuring oxygen and temperature",
         how="No new sensor: maintain EUXRoOB01-03 so the record reaches the 8 complete years a trend needs; "
             "EUXRoOB02 data stop at the end of July 2026, check its status.",
         why="The buoys are the only offshore oxygen measurement, the model misses day-to-day changes, and the "
             "record is still too short to show a trend.",
         cost="low", who="GeoEcoMar (buoy operator)"),
    dict(need_id="sst", variables=["sst"], stations=_OB + ["EUXRo03"], pair="in situ vs satellite", platforms=_OB,
         thresholds=[], sectors=["fishing", "aquaculture", "tourism", "shipyards"],
         where="Whole coast (satellite) and offshore buoys", lat=44.325, lon=30.41,
         what="Nothing new for sea surface temperature",
         how="No new measurement needed: keep the existing buoys as the independent check of the satellite.",
         why="Satellite temperature is within about half a degree of the buoys and covers 44 years.",
         cost="none", who="-"),
]


# ------------------------------------------------------------------------------------------------- helpers
def _parse_profile(profile) -> tuple[str, str | None]:
    """'stakeholder:aquaculture' or {'role': 'stakeholder', 'sector': 'aquaculture'} -> ('stakeholder', 'aquaculture').
    Unknown roles fall back to 'public'; unknown sectors to None."""
    if isinstance(profile, dict):
        role, sector = str(profile.get("role") or "public").lower(), profile.get("sector")
    else:
        p = str(profile or "public").lower()
        role, sector = (p.split(":", 1) + [None])[:2] if ":" in p else (p, None)
    role = role if role in PROFILES else "public"
    sector = str(sector).lower() if sector else None
    return role, sector if sector in SECTORS else None


@lru_cache(maxsize=None)
def _gate() -> pd.DataFrame:
    return pd.read_csv(SEASONAL_DIR / "gate_summary.csv")


@lru_cache(maxsize=None)
def _trends_long() -> pd.DataFrame:
    return pd.read_csv(SEASONAL_DIR / "trends_long.csv")


@lru_cache(maxsize=None)
def _inventory() -> pd.DataFrame:
    return pd.read_csv(val.VALIDATION_DIR / "inventory.csv")


def _f(x, nd=2) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.{nd}f}"


def _rng(a, b, nd=2) -> str:
    """'a to b', or a single number when both round to the same value."""
    return _f(a, nd) if _f(a, nd) == _f(b, nd) else f"{_f(a, nd)} to {_f(b, nd)}"


# ------------------------------------------------------------------------------------------------- criteria
def _crit_disagree(need) -> tuple[bool, str]:
    m = val._metrics()
    rows = m[m.variable.isin(need["variables"]) & m.station.isin(need["stations"])]
    if need["pair"]:
        rows = rows[rows.pair == need["pair"]]
    if not len(rows):
        return False, "not testable: no matched in-situ data"
    hits, notes = [], []
    for v, g in rows.groupby("variable", sort=False):
        s = val.source_summary(v)
        if (g.space == "z").all():
            bad = g[g.spearman < DISAGREE_SPEARMAN]
            notes.append(f"{v} Spearman {', '.join(_f(x) for x in g.spearman)} (disagree below {DISAGREE_SPEARMAN})")
        else:
            u = s["uncertainty_value"]
            bad = g[(g.bias.abs() > u) | (g.r2_anom < DISAGREE_R2_ANOM)]
            notes.append(f"{v} {need['pair']}: bias {_rng(g.bias.min(), g.bias.max())} {s['error_unit']} "
                         f"(typical error {u}), R2 of anomalies {_rng(g.r2_anom.min(), g.r2_anom.max())} "
                         f"(disagree below {DISAGREE_R2_ANOM})")
        hits.append(len(bad) > 0)
    return any(hits), "; ".join(notes)


def _reporting(station: str, variable: str) -> bool:
    inv = _inventory()
    r = inv[(inv.station == station) & (inv.variable == variable) & inv.source.str.startswith("in situ")]
    if not len(r) or pd.isna(r.end.iloc[0]):
        return False
    return (pd.Timestamp(RUN_DATE) - pd.Timestamp(r.end.iloc[0])).days <= REPORTING_DAYS


def _crit_sensors(need) -> tuple[tuple[bool, str], tuple[bool, str]]:
    """(N no trusted in-situ, S untrusted sensor) from the datahub trust flags."""
    if not need["platforms"]:
        return (True, "no in-situ sensor for this variable here"), (False, "no sensor here")
    trusted, flagged = [], []
    for p in need["platforms"]:
        for v in need["variables"]:
            t, _ = dh.variable_trust(p, v)
            if t in dh.AUTO_EXCLUDED_TRUST:
                flagged.append(f"{p} {v}: {t}")
            elif _reporting(p, v):
                trusted.append(f"{p} {v}: {t}")
    n = (not trusted, "trusted and reporting: " + ", ".join(trusted) if trusted
         else "no sensor with trust good or usable reporting here")
    s = (bool(flagged), "flagged in datahub: " + ", ".join(flagged) if flagged else "no flagged sensor")
    return n, s


def _crit_time(need) -> tuple[bool, str]:
    g = _gate()
    rows = g[g.station.isin(need["stations"]) & g.variable.isin(need["variables"])]
    if len(rows):
        ok = rows[rows.trend_show & rows.trust.isin(["good", "usable"])]
        if len(ok):
            r = ok.sort_values("n_years").iloc[-1]
            return False, f"{r.source} passes the trend gate ({int(r.n_years)} complete years, {r.trend_level})"
        buoy = rows[rows.source == "buoy"]
        ny = int(buoy.n_years.max()) if len(buoy) else 0
        return True, (f"no trusted source passes the trend gate here; longest buoy record {ny} complete year(s), "
                      f"a trend needs {TREND_MIN_YEARS} (OURS)")
    inv = _inventory()
    r = inv[inv.station.isin(need["stations"]) & inv.variable.isin(need["variables"])
            & inv.source.str.startswith("in situ")].dropna(subset=["end"])
    if len(r):
        return True, f"in-situ record ended {r.end.max()} ({int(r.n_days.max())} sample days)"
    return True, "no in-situ time series"


def _crit_decision(need) -> tuple[bool, str]:
    off = [k for k in need["thresholds"] if str(ind.T[k][2]).startswith("OFFICIAL")]
    if not off:
        return False, "no official threshold"
    return True, "; ".join(f"{ind.T[k][1]} ({ind.T[k][2]})" for k in off)


@lru_cache(maxsize=None)
def _needs_full() -> pd.DataFrame:
    rows = []
    for i, need in enumerate(_NEEDS):
        n, s = _crit_sensors(need)
        crit = dict(disagree=_crit_disagree(need), no_trusted_insitu=n, untrusted_sensor=s,
                    time_gap=_crit_time(need), decision_at_stake=_crit_decision(need))
        hand = need.get("hand", {})
        crit.update(hand)
        met = [k for k in CRITERIA if crit[k][0]]
        rows.append(dict(
            order=i, need_id=need["need_id"], variable=", ".join(need["variables"]), where=need["where"],
            lat=need["lat"], lon=need["lon"], what=need["what"], how=need["how"], why=need["why"],
            cost=need["cost"], who=need["who"], sectors=", ".join(need["sectors"]),
            **{k: bool(crit[k][0]) for k in CRITERIA},
            n_reasons=len(met), reasons="; ".join(CRITERIA[k] for k in met) or "none",
            evidence=" | ".join(f"{k}: {'yes' if crit[k][0] else 'no'} ({crit[k][1]})" for k in CRITERIA),
            hand_set=", ".join(hand) or "", label=LABEL))
    df = pd.DataFrame(rows)
    df["_cost"] = df.cost.map(COST_ORDER)
    df = df.sort_values(["n_reasons", "decision_at_stake", "_cost", "order"], ascending=[False, False, True, True])
    df.insert(0, "rank", range(1, len(df) + 1))
    return df.drop(columns=["_cost", "order"]).reset_index(drop=True)


def measurement_needs(profile=None) -> pd.DataFrame:
    """Ranked measurement needs (see module doc). profile None or researcher: all columns."""
    df = _needs_full().copy()
    if profile is None:
        return df
    role, sector = _parse_profile(profile)
    if role == "researcher":
        return df
    cols = list(PROFILE_COLUMNS[role])
    if role == "stakeholder" and sector:
        df["concerns_you"] = df.sectors.str.split(", ").apply(lambda s: sector in s)
        cols.append("concerns_you")
    return df[cols]


# ------------------------------------------------------------------------------------------------- uncertainty text
_ALIASES = {"temperature": "sst", "sea_temperature": "sst", "chlorophyll": "chl", "blooms": "chl",
            "salinity": "sal", "oxygen": "o2", "bottom_oxygen": "o2_bottom", "o2bottom": "o2_bottom",
            "nutrients": "no3", "nitrate": "no3", "phosphate": "po4"}
_CONF_WORD = {"high": "Reliable", "medium": "Fairly reliable", "low": "Rough guide only"}


def uncertainty_variables() -> list[str]:
    return [v for v in val.variables()] + ["o2_bottom"]


def _var(variable: str) -> str:
    v = str(variable).strip().lower()
    v = _ALIASES.get(v, v)
    if v not in uncertainty_variables():
        raise ValueError(f"Unknown variable {variable!r}; known: {', '.join(uncertainty_variables())} "
                         f"(aliases: {', '.join(_ALIASES)})")
    return v


def _head(s: dict) -> dict:
    """Headline-pair numbers: R2 and R2 of anomalies ranges, from source_summary pairs."""
    h = [p for p in s["pairs"] if p["headline"]]
    r2 = [p["r2"] for p in h if p["r2"] is not None]
    ra = [p["r2_anom"] for p in h if p["r2_anom"] is not None]
    return dict(r2=(min(r2), max(r2)) if r2 else None, r2a=(min(ra), max(ra)) if ra else None)


def _sst_trend() -> str:
    t = _trends_long()
    r = t[(t.variable == "sst") & (t.source == "satellite")]
    if not len(r):
        return ""
    r = r.iloc[0]
    return (f"{r.slope_per_decade:+.2f} °C per decade (95 % CI {r.ci_lo:.2f} to {r.ci_hi:.2f}, {r.years}, "
            f"satellite, {int(r.n_years)} complete years)")


# public: confidence word + one sentence
def _public(v: str, s: dict | None) -> str:
    if v == "o2_bottom":
        return ("**Uncertain.** No sensor measures oxygen near the seabed along the coast. The value shown is a "
                "computer-model estimate, and different models differ by about 2 mg/L.")
    word = _CONF_WORD[s["confidence"]]
    txt = {
        "sst": "The satellite temperature is usually within about half a degree (0.45 °C) of what the buoys "
               "measure.",
        "chl": "The map shows where there is more or less algae, but the exact amount can be off by half or "
               "double. Buoy readings are not used because they read 2 to 3 times too high.",
        "sal": "Salinity comes from a computer model that is usually within about 1 unit (PSU) of water samples "
               "at the coast. The offshore buoy sensors give wrong readings and are not used.",
        "o2": "Surface oxygen from the model is usually within about 1 mg/L of the buoys offshore (2 mg/L at the "
              "coast). Oxygen near the seabed, where fish and mussels can suffocate, is not measured near the coast.",
        "no3": "Nutrient values come from past water samples, not from today: the model is not used for them.",
        "po4": "Nutrient values come from past water samples, not from today: the model is not used for them.",
    }[v]
    return f"**{word}.** {txt}"


# student: what the numbers mean, with this variable as the example
def _student(v: str, s: dict | None) -> str:
    if v == "o2_bottom":
        return ("**What we can and cannot say.** To know how wrong a value can be, we compare it with a "
                "measurement at the same place and day. For bottom oxygen there is no measurement near the coast, "
                "so the error cannot be computed at all. What we have is the spread between two model systems, "
                "about 2 mg/L: that is a lower limit on the uncertainty, not the error itself. Compare it with the "
                "classes: below 2 mg/L is hypoxia, 2-4 mg/L is stress, so a 2 mg/L spread can move a site across a "
                "whole class.")
    h = _head(s)
    intro = ("**Two numbers describe the error.** *RMSE* (root mean square error) is the typical size of the "
             "difference between two sources on one day. *Bias* is the average difference: a constant offset that "
             "could be corrected. ")
    if v == "sst":
        r2, ra = h["r2"], h["r2a"]
        return intro + (
            f"For temperature the satellite differs from the buoys by about {_f(s['rmse'])} °C on a typical day "
            f"(RMSE, {s['n']} matched days at {len(s['stations'])} offshore buoys) and reads {_f(abs(s['bias']))} °C "
            f"cooler on average (bias).\n\n"
            f"**Why a high R² can mislead.** R² (how much of the variation one source explains in the other) is "
            f"{_f(r2[0], 3)}-{_f(r2[1], 3)}, almost perfect, but most of it is the seasons that both sources share: "
            f"winter cold and summer warm. With the monthly means removed, R² drops to {_f(ra[0])}-{_f(ra[1])}. "
            "Agreement is about RMSE and bias, not only R².")
    if v == "chl":
        return intro + (
            "Chlorophyll spans more than 100 times from clear to bloom water, so errors are computed on a "
            "logarithmic scale: a difference of 0.2 in log10 means a factor of 10^0.2, about 1.6. Satellite and "
            "model agree within about that factor. The buoys read 2 to 3 times more (median ratio satellite / "
            "buoy 0.36-0.51).\n\n"
            "**Agreement is not accuracy.** Two sources that agree can both be wrong; here no trusted measurement "
            "exists offshore to check either, so the true error is not known.")
    if v == "sal":
        return intro + (
            f"The model is within about {_f(s['rmse'], 1)} PSU of coastal water samples ({s['n']} sample days). "
            "Offshore, the buoy salinity shows long drops that look like a dirty sensor; against it the model "
            "has R² 0.00-0.17.\n\n"
            "**A bad reference makes a good source look bad.** Before blaming the model, check the measurement.")
    if v == "o2":
        br = s["bias_range"]
        return intro + (
            f"Model surface oxygen differs from the offshore buoys by about {_f(s['rmse'], 1)} mg/L on a typical "
            f"day. Its bias is {_f(br[0])} to {_f(br[1])} mg/L depending on the buoy: higher than the newer buoys, "
            "lower than the older one.\n\n"
            "**An average can hide opposite errors.** The pooled bias looks small because positive and negative "
            "offsets cancel. With the monthly means removed, R² is near 0: the model gets the seasons right, not "
            "the day-to-day changes.")
    return intro + (
        "For nutrients the model values are on a different scale from the samples, so both are standardised "
        "(z-scores) and only the shape is compared, with a rank correlation (Spearman): "
        + ("0.41 for nitrate, enough for the broad seasonal pattern only." if v == "no3" else
           "0.01 for phosphate: no agreement at all.")
        + " That is why the model is not used for nutrient levels.")


_STAKE = {
    "sst": dict(
        _="Good enough for planning: an error of about 0.45 °C rarely changes a decision; near the coast allow "
          "about 0.9 °C.",
        fishing="Temperature maps for where fish gather are reliable offshore (about 0.45 °C); at the coast allow "
                "about 0.9 °C.",
        aquaculture="Heat-stress alerts based on temperature are reliable; at the farm, near the coast, allow "
                    "about 0.9 °C.",
        tourism="Bathing temperature is reliable to about half a degree offshore and about 1 °C at the beach.",
        shipyards="Reliable for work planning and corrosion checks to about half a degree.",
        ports="Reliable to about half a degree; temperature is rarely the limiting factor for port operations."),
    "chl": dict(
        _="Use it as a reason to look, not as a measurement: the amount can be off by a factor of 1.6 or more.",
        tourism="A bloom shown near the beaches or the Danube plume can be overstated by river sediment. Check "
                "with a water sample before warning bathers.",
        aquaculture="A bloom alert near the farms is a reason to take a water sample and a toxin test, not a "
                    "confirmed harmful bloom.",
        fishing="Use it as a broad sign of productive waters, not as an exact value.",
        ports="Not decision-grade for ports; context only.",
        shipyards="Not decision-grade for shipyards; context only."),
    "sal": dict(
        _="Offshore salinity comes from the model only; an error of about 1 PSU is fine for most uses.",
        aquaculture="The model smooths the low-salinity Danube pulses: a short freshwater event at a farm can be "
                    "missed or shown weaker than it is.",
        shipyards="Good enough for corrosion planning (about 1 PSU).",
        ports="Good enough for operations; salinity is rarely limiting."),
    "o2": dict(
        _="An oxygen 'watch' or 'alert' is a reason to measure, not a confirmed event: surface oxygen is about "
          "1 mg/L uncertain offshore, 2 mg/L at the coast, and bottom oxygen is not measured.",
        aquaculture="Mussel deaths depend on bottom oxygen, which nobody measures near the farms. The model value "
                    "is uncertain by about 2 mg/L, as wide as the gap between 'stress' (4 mg/L) and 'hypoxia' "
                    "(2 mg/L). Before acting on an alert, lower an oxygen probe at the farm.",
        fishing="Low bottom oxygen drives fish off the shelf; the map shows where it may happen, not where it did.",
        tourism="Surface oxygen is a background indicator for beaches; fish kills are rare and would be reported "
                "by the authorities first."),
    "no3": dict(_="Historical only: useful to explain long-term blooms, not to act this week."),
    "po4": dict(_="Historical only: useful to explain long-term blooms, not to act this week."),
}


def _stakeholder(v: str, s: dict | None, sector: str | None) -> str:
    key = "o2" if v == "o2_bottom" else v
    d = _STAKE[key]
    conf = "low" if v == "o2_bottom" else s["confidence"]
    lead = f"**{_CONF_WORD[conf]} for decisions.** "
    txt = (d.get(sector) if sector else None) or d["_"]
    return lead + txt


def _researcher(v: str, s: dict | None) -> str:
    out = []
    if v == "o2_bottom":
        out.append("**Bottom O2: no validation possible.** No bottom sensor exists within the study area in the "
                   "matched data; the Copernicus BGC model systems (reanalysis vs analysis/forecast) disagree by "
                   "about 2 mg/L at the bottom (docs/indicators/SHORTLIST.md section 4). The oxygen card therefore "
                   "has low confidence; D5C5 (OFFICIAL-RO) cannot be assessed from data here.")
        s = val.source_summary("o2")
        out.append("Surface O2, for reference:")
    out.append(f"**{s['title']}**: trusted source {s['trusted_label']}; uncertainty {s['uncertainty']}; "
               f"confidence {s['confidence']}.")
    pairs = pd.DataFrame(s["pairs"])[["station", "pair", "start", "end", "n", "bias", "rmse", "r2", "r2_anom",
                                      "slope", "spearman", "headline"]]
    out.append(f"Metrics ({s['error_unit']}; bias = second source minus first):\n\n"
               + pairs.to_markdown(index=False, floatfmt=".2f"))
    out.append("**Method.** Daily means matched on the same day; satellite and model taken at the nearest pixel or "
               "grid cell to the station; chlorophyll compared in log10; nutrients as z-scores. Headline RMSE is "
               "pooled, n-weighted: sqrt(sum n*RMSE^2 / sum n). R² of anomalies uses monthly means removed, so it "
               "measures day-to-day agreement beyond the shared seasonal cycle; R² alone overstates agreement. "
               "Satellite and model are not independent for SST (the model very probably assimilates satellite "
               "SST, inferred); only in-situ data are an independent check.")
    out.append("**Autocorrelation.** Daily values are autocorrelated, so the effective sample size is much smaller "
               "than n; RMSE and bias are fine as descriptions, but any confidence interval computed from n would "
               "be too narrow. Seasonal fits use Newey-West (HAC) errors; trends use annual means without an "
               "autocorrelation correction, so their uncertainty is a lower bound.")
    g = _gate()
    gv = g[g.variable == ("o2" if v == "o2_bottom" else v)]
    if len(gv):
        t = gv[["station", "source", "trust", "r2_adj", "cycle_show", "n_years", "trend_level", "trend_show"]]
        out.append("**Quality gate** (OURS): source trust good or usable; cycle p < 0.05 (HAC) and adjusted R² "
                   ">= 0.5 on weekly means; trend from 8 complete years (indicative below 20, climate from 20).\n\n"
                   + t.to_markdown(index=False, floatfmt=".2f"))
    if v == "sst":
        out.append(f"Long satellite record at the buoys: {_sst_trend()}.")
    if s["caveats"]:
        out.append("**Caveats.**\n" + "\n".join(f"- {c}" for c in s["caveats"]))
    if s["untrusted"]:
        out.append("**Not used.**\n" + "\n".join(f"- {u['source']}: {u['reason']}" for u in s["untrusted"]))
    out.append(f"Basis: {', '.join(s['basis']['files'])}; run {s['basis']['run_date']}. All numbers indicative.")
    return "\n\n".join(out)


def uncertainty_text(variable: str, profile="public") -> str:
    """Markdown text on the uncertainty of one variable for one profile (see module doc)."""
    v = _var(variable)
    role, sector = _parse_profile(profile)
    s = None if v == "o2_bottom" else val.source_summary(v)
    if role == "public":
        return _public(v, s)
    if role == "student":
        return _public(v, s) + "\n\n" + _student(v, s)
    if role == "stakeholder":
        return _stakeholder(v, s, sector)
    return _researcher(v, s)


_PRIMER = {
    "public": "Every value on this site comes from one of three places: a **measurement** (a buoy or a water "
              "sample), a **satellite** (sees only the surface), or a **computer model** (fills the gaps). None is "
              "perfect. Next to each value we say how far you can trust it: *reliable*, *fairly reliable* or "
              "*rough guide only*.",
    "student": "Every value comes from a **measurement** (buoy, water sample), a **satellite** (surface only) or a "
               "**model** (computed everywhere). To know how wrong a value can be, we compare the sources on the "
               "same day at the same place. The typical difference (RMSE) and the average offset (bias) are the "
               "uncertainty; where no measurement exists, the uncertainty is unknown, not zero.",
    "stakeholder": "Every value comes from a measurement, a satellite or a model, and each has an error. For each "
                   "indicator we say what that error means for your decision: whether a 'watch' or 'alert' can be "
                   "acted on directly, or first needs a measurement on site.",
    "researcher": "Uncertainty is estimated by matching in-situ, satellite and model daily values at the offshore "
                  "buoys (EUXRoOB01-03 2024-2026, EUXRo03 2013-2023) and coastal bottle samples (Constanta, "
                  "1993-2021), reporting bias, RMSE, unbiased RMSE, R², R² of anomalies, slope and Spearman. Sensors "
                  "that fail the check are flagged in `marinekit.datahub` and never used as the automatic source. "
                  "Seasonal cycles and trends are shown only behind a quality gate. Thresholds labelled OURS are our "
                  "proposals; all uncertainties are indicative (point values, few stations).",
}


def uncertainty_primer(profile="public") -> str:
    role, _ = _parse_profile(profile)
    return _PRIMER[role]
