"""Source uncertainty per variable: in situ vs satellite vs model, read from the committed validation results.

For the viewer's Water page "Sources" section and the Methods page (GitHub issue #2, request 1). Read-only: this
module never downloads anything and never recomputes metrics. It reads the CSV files written by
`scripts/validation/compare_sources.py` in `docs/indicators/validation/` (paths resolved from this file's location,
not from the working directory), and adds the hand-written reading from `interpretation.md` (trusted source,
indicative uncertainty, caveats). Re-run the script to refresh the numbers; the readings are tied to the run of
2026-11-23 and should be re-checked if the numbers move.

Public functions (stable contract; additive changes only)
---------------------------------------------------------
- `variables() -> list[str]`: variable ids present in metrics.csv (sst, chl, sal, o2, no3, po4).
- `source_summary(variable) -> dict`: one variable, keys:
    variable, title, unit (unit of the values), error_unit (unit of rmse and bias: same as unit, except
    "log10 mg/m³" for chl and "z (unitless)" for no3 / po4), space (linear | log10 | z),
    trusted_source (satellite | model | in situ), trusted_label (plain text), uncertainty (plain text, indicative),
    uncertainty_value (float, in error_unit, or None when not quantified), rmse, bias (headline numbers in error_unit:
    n-weighted pooled RMSE = sqrt(sum n*rmse^2 / sum n) and n-weighted mean bias over the headline rows, or None for
    nutrients, whose metrics are on standardised values), bias_range ([min, max] over the headline rows, or None),
    headline_pair (e.g. "in situ vs satellite"), n (matched days in the headline rows), stations (headline
    stations), confidence (high | medium | low), reading (one plain-language line), caveats (list of str),
    pairs (list of dicts, every row of metrics.csv for the variable, see below), untrusted (list of dicts:
    source, reason; these sources stay visible in the viewer but labelled "not used"), basis (dict: files, start,
    end, run_date, stations).
  Each `pairs` item: station, pair, start, end, n, bias, rmse, ubrmse, r2, r2_anom, spearman, slope, median_ratio
  (chl only), space, headline (bool: used for the headline rmse / bias). Missing numbers are None.
  Sign convention: bias = second source minus first source of the pair (e.g. satellite minus in situ).
- `summary_table() -> pandas.DataFrame`: one row per variable for the Methods page; columns variable, title,
  trusted_source, trusted_label, uncertainty, uncertainty_value, rmse, bias, error_unit, n, stations, confidence,
  reading, untrusted (names joined with "; ").
- `pair_points(variable, station=None) -> pandas.DataFrame`: matched daily values for scatter plots, from
  matched_daily.csv; columns station, variable, date (datetime64), season (DJF | MAM | JJA | SON), insitu,
  satellite, model. Values are in the variable's native unit (chl in mg/m³, not log10; nutrients raw mmol/m³,
  not standardised). A source with no value that day is NaN (satellite is NaN for sal, o2, no3, po4).

Viewer usage
------------
    from marinekit import validation as val
    s = val.source_summary("sst")
    st.caption(f"{s['trusted_label']}: {s['uncertainty']} ({s['confidence']} confidence)")
    st.write(s["reading"])
    pts = val.pair_points("sst", station="EUXRoOB01")      # x = insitu, y = satellite / model
    st.dataframe(val.summary_table())                        # Methods page

All uncertainties are INDICATIVE (daily value at a point, from a few stations). They say nothing about bottom
water (hypoxia), where no sensor exists in this check.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

VALIDATION_DIR = Path(__file__).resolve().parents[2] / "docs" / "indicators" / "validation"
RUN_DATE = "2026-11-23"
OFFSHORE = ["EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo03"]
COAST = ["Constanta bottles"]
_SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}

_COASTAL_BUOYS = dict(source="Coastal buoys EUXRoCB01-03",
                      reason="Untrusted by repo rule (CLAUDE.md, SHORTLIST.md); not used in the check.")
_STATION_15480 = dict(source="Shore station 15480 (NIMH)",
                      reason="Untrusted by repo rule; not used in the check.")

# Hand-written reading per variable, from interpretation.md (run of 2026-11-23). Numbers here must stay consistent
# with metrics.csv; tests/test_validation_api.py checks the headline ones.
_SPEC: dict[str, dict] = {
    "sst": dict(
        title="Sea surface temperature", unit="°C", error_unit="°C",
        trusted_source="satellite", trusted_label="Satellite SST (Copernicus L4 analysis)",
        headline_pair="in situ vs satellite", headline_stations=OFFSHORE,
        uncertainty="about 0.45 °C for a daily value at a point, bias under 0.15 °C (indicative)",
        uncertainty_value=0.45, confidence="high",
        reading="Satellite SST is within about 0.45 °C of the offshore buoys on a typical day, "
                "and reads less than 0.15 °C cooler on average.",
        caveats=[
            "Satellite and model agree with each other as closely as each agrees with the buoys; the model very "
            "probably assimilates satellite SST (inferred), so only the buoys are an independent check.",
            "At the Constanta coast the scatter is larger (RMSE about 0.9 °C, 43 bottle days 1993-2021).",
            "R² near 1 comes mostly from the shared seasonal cycle; with monthly means removed it is about 0.9.",
            "By season both read cooler than the buoys in winter (satellite -0.2 °C, model -0.3 °C).",
        ],
        untrusted=[_COASTAL_BUOYS, _STATION_15480],
    ),
    "chl": dict(
        title="Chlorophyll-a (surface)", unit="mg/m³", error_unit="log10 mg/m³",
        trusted_source="satellite", trusted_label="Satellite chlorophyll (Copernicus L4 gap-free, 1 km)",
        headline_pair="satellite vs model", headline_stations=OFFSHORE,
        uncertainty="not quantified against trusted measurements; at least a factor of about 1.6 (indicative)",
        uncertainty_value=0.2, confidence="low",
        reading="Satellite chlorophyll is the working reference, but its error is not known: it agrees with the "
                "model within a factor of about 1.6, and no trusted measurement exists offshore to check either.",
        caveats=[
            "Headline numbers are satellite vs model (consistency, not accuracy), in log10 space: "
            "0.2 log10 is a factor of about 1.6.",
            "Bottle samples at the coast give only 3 chlorophyll days, too few to compare.",
        ],
        untrusted=[
            dict(source="Buoy chlorophyll (fluorescence) EUXRoOB01-03",
                 reason="Reads 2 to 3 times more than both satellite and model (median ratio 0.36-0.51), "
                        "autumn values up to about 100 mg/m³; likely factory calibration, quenching, biofouling "
                        "(inferred)."),
            dict(source="Buoy chlorophyll (fluorescence) EUXRo03",
                 reason="Flat bands that jump between levels; R² with the satellite 0.00."),
            dict(source="Model chlorophyll (Copernicus BGC)",
                 reason="Indicative only: shares part of the satellite variability but has no in situ check."),
            _COASTAL_BUOYS,
        ],
    ),
    "sal": dict(
        title="Surface salinity", unit="PSU", error_unit="PSU",
        trusted_source="model", trusted_label="Model salinity (Copernicus Black Sea physics, 2.5 km)",
        headline_pair="in situ vs model", headline_stations=COAST,
        uncertainty="about 1 PSU for a daily coastal value (indicative)",
        uncertainty_value=1.0, confidence="medium",
        reading="Model salinity is within about 1 PSU of coastal bottle samples on a typical day; it follows the "
                "Danube plume episodes but smooths them.",
        caveats=[
            "Based on 41 bottle days at Constanta (1993-2021): small sample.",
            "Offshore, buoy salinity is not reliable, so the model cannot be checked there "
            "(R² 0.00-0.17 against the buoys, EUXRo03 included).",
        ],
        untrusted=[
            dict(source="Buoy salinity EUXRoOB01-03",
                 reason="Drops to 13-15 PSU lasting weeks to months that end in steps (e.g. OB02 Oct 2025 - "
                        "Mar 2026); matches conductivity-cell fouling (inferred)."),
            _COASTAL_BUOYS,
        ],
    ),
    "o2": dict(
        title="Surface dissolved oxygen", unit="mg/L", error_unit="mg/L",
        trusted_source="model",
        trusted_label="Model O2 (Copernicus BGC) for the seasonal cycle and areas without buoys; "
                      "offshore buoys after QC where available",
        headline_pair="in situ vs model", headline_stations=OFFSHORE,
        uncertainty="about 1 mg/L offshore and 2 mg/L at the coast; bias not known to better than "
                    "+/- 0.7 mg/L (indicative)",
        uncertainty_value=1.0, confidence="medium",
        reading="Model surface O2 is within about 1 mg/L of the offshore buoys (2 mg/L at the coast) and its "
                "bias is uncertain by about +/- 0.7 mg/L; it gets the seasons right, not day-to-day changes.",
        caveats=[
            "The sign of the bias depends on the buoy generation: model higher than OB01-03 (+0.5 to +0.7 mg/L), "
            "lower than EUXRo03 (-0.5 mg/L); the pooled mean bias hides this.",
            "With monthly means removed, R² is 0.00-0.10: no day-to-day skill.",
            "At the coast the model is 1.5 mg/L lower than the bottles (RMSE 2.3 mg/L, 41 days).",
            "Says nothing about bottom O2 (hypoxia): no bottom sensor in this check.",
        ],
        untrusted=[_COASTAL_BUOYS],
    ),
    "no3": dict(
        title="Nitrate (shape only)", unit="mmol/m³", error_unit="z (unitless)",
        trusted_source="in situ", trusted_label="Bottle samples and the DIVAnd climatology",
        headline_pair="in situ vs model", headline_stations=COAST,
        uncertainty="model not usable as absolute values; seasonal shape only (Spearman 0.41)",
        uncertainty_value=None, confidence="low",
        reading="Model nitrate only gets the broad seasonal pattern (peak in February, while the bottles peak in "
                "April); use bottle samples and the climatology for levels.",
        caveats=["35 bottle days at Constanta (1993-1999); compared as standardised values (z-scores)."],
        untrusted=[dict(source="Model nitrate (Copernicus BGC) as absolute values",
                        reason="Repo rule: not usable as absolute values; at most for the timing of the winter "
                               "maximum.")],
    ),
    "po4": dict(
        title="Phosphate (shape only)", unit="mmol/m³", error_unit="z (unitless)",
        trusted_source="in situ", trusted_label="Bottle samples and the DIVAnd climatology",
        headline_pair="in situ vs model", headline_stations=COAST,
        uncertainty="model not usable, even for the seasonal shape (Spearman 0.01)",
        uncertainty_value=None, confidence="low",
        reading="Model phosphate does not match the bottle samples even in shape; do not use it at the coast.",
        caveats=["38 bottle days at Constanta (1993-1999); compared as standardised values (z-scores)."],
        untrusted=[dict(source="Model phosphate (Copernicus BGC)",
                        reason="Repo rule: not usable as absolute values; no agreement in shape either "
                               "(Spearman 0.01).")],
    ),
}


def _num(x):
    """float or None (NaN and empty become None)."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


@lru_cache(maxsize=None)
def _metrics() -> pd.DataFrame:
    return pd.read_csv(VALIDATION_DIR / "metrics.csv")


@lru_cache(maxsize=None)
def _matched() -> pd.DataFrame:
    df = pd.read_csv(VALIDATION_DIR / "matched_daily.csv", parse_dates=["date"])
    df.insert(3, "season", df["date"].dt.month.map(_SEASON))
    return df


def variables() -> list[str]:
    """Variable ids present in metrics.csv, in file order."""
    return list(dict.fromkeys(_metrics()["variable"]))


def _check(variable: str) -> str:
    v = str(variable).strip().lower()
    known = variables()
    if v not in known:
        raise ValueError(f"Unknown variable {variable!r} for source validation; known: {', '.join(known)}")
    return v


def source_summary(variable: str) -> dict:
    """Trusted source, typical error, bias, plain reading and per-pair metrics for one variable (see module doc)."""
    v = _check(variable)
    rows = _metrics()[_metrics()["variable"] == v]
    spec = _SPEC.get(v) or dict(
        title=v, unit="", error_unit="", trusted_source="unknown", trusted_label="Not assessed",
        headline_pair="in situ vs model", headline_stations=list(rows["station"].unique()),
        uncertainty="not assessed", uncertainty_value=None, confidence="low",
        reading="No hand-written reading for this variable yet; see the pair metrics.", caveats=[], untrusted=[])
    space = str(rows["space"].iloc[0])
    is_head = (rows["pair"] == spec["headline_pair"]) & rows["station"].isin(spec["headline_stations"])
    head = rows[is_head]

    rmse = bias = bias_range = None
    if space != "z" and len(head):
        w = head["n"].astype(float)
        rmse = float(math.sqrt((w * head["rmse"] ** 2).sum() / w.sum()))
        bias = float((w * head["bias"]).sum() / w.sum())
        bias_range = [float(head["bias"].min()), float(head["bias"].max())]

    pairs = []
    for i, r in rows.iterrows():
        pairs.append(dict(
            station=r["station"], pair=r["pair"], start=r["start"], end=r["end"], n=int(r["n"]),
            bias=_num(r["bias"]), rmse=_num(r["rmse"]), ubrmse=_num(r["ubrmse"]), r2=_num(r["r2"]),
            r2_anom=_num(r.get("r2_anom")), spearman=_num(r.get("spearman")), slope=_num(r["slope"]),
            median_ratio=_num(r.get("median_ratio")), space=r["space"], headline=bool(is_head.loc[i])))

    return dict(
        variable=v, title=spec["title"], unit=spec["unit"], error_unit=spec["error_unit"], space=space,
        trusted_source=spec["trusted_source"], trusted_label=spec["trusted_label"],
        uncertainty=spec["uncertainty"], uncertainty_value=spec["uncertainty_value"],
        rmse=rmse, bias=bias, bias_range=bias_range, headline_pair=spec["headline_pair"],
        n=int(head["n"].sum()), stations=list(head["station"]),
        confidence=spec["confidence"], reading=spec["reading"], caveats=list(spec["caveats"]),
        pairs=pairs, untrusted=[dict(u) for u in spec["untrusted"]],
        basis=dict(
            files=[f"docs/indicators/validation/{f}" for f in ("metrics.csv", "matched_daily.csv",
                                                               "interpretation.md")],
            start=str(rows["start"].min()), end=str(rows["end"].max()), run_date=RUN_DATE,
            stations=list(dict.fromkeys(rows["station"]))),
    )


def summary_table() -> pd.DataFrame:
    """One row per variable (Methods page). Numbers in each row's error_unit; all uncertainties indicative."""
    out = []
    for v in variables():
        s = source_summary(v)
        out.append(dict(
            variable=v, title=s["title"], trusted_source=s["trusted_source"], trusted_label=s["trusted_label"],
            uncertainty=s["uncertainty"], uncertainty_value=s["uncertainty_value"], rmse=s["rmse"], bias=s["bias"],
            error_unit=s["error_unit"], n=s["n"], stations=", ".join(s["stations"]), confidence=s["confidence"],
            reading=s["reading"], untrusted="; ".join(u["source"] for u in s["untrusted"])))
    return pd.DataFrame(out)


def pair_points(variable: str, station: str | None = None) -> pd.DataFrame:
    """Matched daily values for scatter plots (columns: station, variable, date, season, insitu, satellite, model).

    Native units (chl not log10, nutrients not standardised). Raises ValueError for an unknown variable or a
    station with no matched data for that variable.
    """
    v = _check(variable)
    df = _matched()
    df = df[df["variable"] == v]
    if station is not None:
        if station not in set(df["station"]):
            raise ValueError(f"No matched data for {v!r} at station {station!r}; "
                             f"stations: {', '.join(dict.fromkeys(df['station']))}")
        df = df[df["station"] == station]
    return df.reset_index(drop=True).copy()
