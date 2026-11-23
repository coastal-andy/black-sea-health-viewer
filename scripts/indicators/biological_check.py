"""Proof that the shortlisted BIOLOGICAL indicators are computable at Constanta (44.17 N, 28.72 E).

Run:  .venv/bin/python scripts/indicators/biological_check.py | tee scripts/indicators/biological_check_output.txt

Uses only the project modules (src/marinekit/sources/*) and their disk caches under data/cache/.
Satellite phytoplankton size classes (sat_pft_l3_my/_nrt) and satellite primary production (sat_pp_my/_nrt)
are CATALOG keys in copernicus.py. OBIS answers are cached under data/cache/obis/ with the same cache helpers.
First run: ~3-6 min (30-year satellite series, OBIS phytoplankton counts). Afterwards: seconds.

Indicators (see docs/indicators/biological.md for the reasoning):
  B1 chl-a anomaly, log space, vs 1998-2020 day-of-year climatology       sat_chl_l4_my / sat_chl_l4_nrt
  B2 bloom days per season and long-term trend of annual chl              sat_chl_l4_my (1998-2025)
  B3 phytoplankton size structure (micro share) + in-situ diatom/dino      sat_pft_l3_my + OBIS NIMRD counts
  B4 primary production, satellite vs model                               sat_pp_my + rea_bgc_o2 nppv
  B5 mussel-bed hypoxia exposure (O2 classes A-D, D5C5 test)  rea_bgc_o2 o2_bottom + rea_phy T/S + OBIS Mytilus
  B6 non-indigenous and gelatinous species: occurrence evidence           OBIS API (Romanian box)
  B7 biological evidence coverage: EurOBIS record grid, strandings        emodnet_layers.biology_records_grid + OBIS
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests

from marinekit.sources import BBOX_RO, cache_key, cached_path
from marinekit.sources import copernicus as cop
from marinekit.sources import open_data as od
from marinekit.sources import emodnet_layers as el

LAT, LON = 44.17, 28.72
T0 = time.time()
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)


def hdr(s):
    print(f"\n{'=' * 100}\n{s}   [t={time.time() - T0:.0f}s]\n{'=' * 100}")


def sen_slope(y: pd.Series) -> float:
    """Theil-Sen slope per index unit (robust trend)."""
    y = y.dropna()
    x = y.index.values.astype(float)
    v = y.values
    s = [(v[j] - v[i]) / (x[j] - x[i]) for i in range(len(v)) for j in range(i + 1, len(v)) if x[j] != x[i]]
    return float(np.median(s)) if s else np.nan


def doy_clim_log(s: pd.Series, years=(1998, 2020), half=15) -> pd.DataFrame:
    """Day-of-year climatology in log10 space: geometric mean, std(log10), p10, p90 (back-transformed)."""
    s = s[(s.index.year >= years[0]) & (s.index.year <= years[1])].dropna()
    v = np.log10(s.clip(lower=1e-3).values)
    doy = s.index.day_of_year.values
    rows = []
    for d in range(1, 367):
        dd = np.abs(doy - d)
        x = v[np.minimum(dd, 366 - dd) <= half]
        p10, p50, p90 = np.percentile(x, [10, 50, 90])
        rows.append((d, 10 ** x.mean(), x.std(ddof=1), 10 ** p10, 10 ** p50, 10 ** p90, len(x)))
    return pd.DataFrame(rows, columns=["doy", "gmean", "std_log10", "p10", "p50", "p90", "n"]).set_index("doy")


def log_anom(s: pd.Series, clim: pd.DataFrame) -> pd.DataFrame:
    c = clim.reindex(s.index.day_of_year)
    out = pd.DataFrame({"chl": s.values}, index=s.index)
    out["clim_gmean"] = c["gmean"].values
    out["clim_p90"] = c["p90"].values
    out["ratio"] = out["chl"] / out["clim_gmean"]                          # 2.0 = twice the normal
    out["z_log"] = (np.log10(out["chl"]) - np.log10(out["clim_gmean"])) / c["std_log10"].values
    out["flag"] = np.select([out["chl"] > out["clim_p90"], out["chl"] < c["p10"].values], ["above_p90", "below_p10"], "normal")
    return out


# --------------------------------------------------------------------------------------------- OBIS
OBIS = "https://api.obis.org/v3"
UA = {"User-Agent": "marinekit-hackathon/0.1 (python-requests)"}
BOX_RO_WKT = "POLYGON((28.4 43.6,30.6 43.6,30.6 45.4,28.4 45.4,28.4 43.6))"
BOX_CTA_WKT = "POLYGON((28.6 44.05,28.95 44.05,28.95 44.3,28.6 44.3,28.6 44.05))"  # ~30 x 28 km off Constanta


def obis_json(path: str, params: dict, tag: str) -> dict | list:
    fp = cached_path("obis", cache_key(tag, path, params), "json")
    if fp.exists():
        return json.loads(fp.read_text())
    for attempt in range(3):
        try:
            r = requests.get(OBIS + path, params=params, headers=UA, timeout=300)
            r.raise_for_status()
            js = r.json()
            fp.write_text(json.dumps(js))
            return js
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)


def obis_phyto_counts(taxon: str, geom: str, enddepth: float = 5) -> pd.DataFrame:
    """Surface (<= enddepth m) phytoplankton abundance records (cells/L) from OBIS measurement-or-facts.
    Pages with `after`; keeps only a compact table, cached as parquet."""
    fp = cached_path("obis", cache_key("phyto_counts", taxon, geom, enddepth), "parquet")
    if fp.exists():
        return pd.read_parquet(fp)
    rows, after = [], None
    fields = "id,eventDate,minimumDepthInMeters,class,scientificName,decimalLatitude,decimalLongitude,datasetName,mof"
    while True:
        p = {"geometry": geom, "scientificname": taxon, "size": 5000, "mof": "true", "enddepth": enddepth, "fields": fields}
        if after:
            p["after"] = after
        r = requests.get(OBIS + "/occurrence", params=p, headers=UA, timeout=300)
        r.raise_for_status()
        res = r.json()["results"]
        if not res:
            break
        for x in res:
            ab = np.nan
            for m in x.get("mof") or []:
                mt = (m.get("measurementType") or "").lower()
                mu = (m.get("measurementUnit") or "").lower()
                if mt.startswith("abundance") and ("litre" in mu or "/l" in mu):
                    try:
                        ab = float(m["measurementValue"])
                    except (TypeError, ValueError):
                        pass
            rows.append((x.get("eventDate"), x.get("minimumDepthInMeters"), x.get("class"), x.get("scientificName"),
                         x.get("decimalLatitude"), x.get("decimalLongitude"), x.get("datasetName"), ab))
        after = res[-1]["id"]
        if len(res) < 5000:
            break
    df = pd.DataFrame(rows, columns=["date", "depth", "class", "taxon", "lat", "lon", "dataset", "cells_per_l"])
    df.to_parquet(fp)
    return df


# =========================================================================================== B1 + B2
hdr("B1/B2  Satellite chl-a at Constanta: 30-year series, log-space climatology, anomalies, bloom days")
assert cop.is_logged_in(), cop.login_help()
long = cop.fetch_timeseries("sat_chl_l4_my", LAT, LON, "1998-01-01", "2025-12-31", variables=["chl"])
chl = long["chl"].dropna()
print(f"sat_chl_l4_my  dataset={long.attrs['dataset']}  cell=({long.attrs['grid_lat']}, {long.attrs['grid_lon']}) "
      f"dist={long.attrs['distance_km']} km  n_days={chl.size}  {chl.index.min().date()}..{chl.index.max().date()}")
clim = doy_clim_log(chl, (1998, 2020))
mon = chl.groupby(chl.index.month).apply(lambda x: 10 ** np.log10(x).mean())
print("Monthly geometric-mean chl 1998-2025 (mg m-3):", " ".join(f"{m}:{v:.1f}" for m, v in mon.items()))
print("Climatology (1998-2020, +-15 d, log10) at selected days:")
print(clim.loc[[15, 74, 135, 196, 258, 319], ["gmean", "p10", "p90", "std_log10", "n"]].round(2).to_string())

# B2: bloom days. Two definitions, reported side by side.
#   relative: chl > day-of-year p90 of 1998-2020 (anomalous high, independent of the coastal case-2 bias)
#   absolute: chl > 10 mg m-3 (a common 'bloom' level for the NW shelf in satellite studies; PROPOSED, not official)
ann = pd.DataFrame({
    "gmean": chl.groupby(chl.index.year).apply(lambda x: 10 ** np.log10(x).mean()),
    "bloom_rel_days": log_anom(chl, clim).groupby(chl.index.year)["flag"].apply(lambda f: int((f == "above_p90").sum())),
    "bloom_abs10_days": chl.groupby(chl.index.year).apply(lambda x: int((x > 10).sum())),
    "spring_MAM_gmean": chl[chl.index.month.isin([3, 4, 5])].groupby(lambda t: t.year).apply(lambda x: 10 ** np.log10(x).mean()),
    "summer_JJA_gmean": chl[chl.index.month.isin([6, 7, 8])].groupby(lambda t: t.year).apply(lambda x: 10 ** np.log10(x).mean()),
})
print("\nAnnual summary (gmean in mg m-3; bloom days per year):")
print(ann.round(2).to_string())
slope = sen_slope(np.log10(ann["gmean"]))
print(f"\nTheil-Sen trend of log10(annual gmean) 1998-2025: {slope:+.4f} /yr  = {100 * (10 ** slope - 1):+.1f} % per year")
print(f"Theil-Sen trend of relative bloom days: {sen_slope(ann['bloom_rel_days'].astype(float)):+.2f} days/yr; "
      f"absolute (>10): {sen_slope(ann['bloom_abs10_days'].astype(float)):+.2f} days/yr")
# Official Romanian MSFD D5C2 metric (RO-MSFD-2024, Table III.7.1): 75th percentile of May-September chl must not
# exceed 5.97 ug/L in coastal waters (CT, Periboina-Vama Veche, includes Constanta). The official metric uses in-situ
# samples of the euphotic layer; here it is applied to satellite surface chl, so it is a PROXY of the official test.
ws = chl[chl.index.month.isin([5, 6, 7, 8, 9])]
p75 = ws.groupby(ws.index.year).quantile(0.75)
print("\nD5C2 proxy: satellite May-Sep P75 chl per year vs official coastal threshold 5.97 ug/L (pass = P75 <= 5.97):")
print("   " + "  ".join(f"{y}:{v:.1f}{'' if v <= 5.97 else '*'}" for y, v in p75.items()) + "   (* = above threshold)")
six = ws.loc["2018":"2023"]
print(f"   2018-2023 pooled P75 = {six.quantile(0.75):.2f} ug/L (NIMRD in-situ coastal P75 for 2018-2023 = 4.9 ug/L)")
d1, d2 = ann.loc[1998:2007, "gmean"], ann.loc[2016:2025, "gmean"]
print(f"Decadal geometric means: 1998-2007 {10 ** np.log10(d1).mean():.2f}  vs 2016-2025 {10 ** np.log10(d2).mean():.2f} mg m-3")

# B1 now: NRT anomaly against the same climatology
nrt = cop.fetch_timeseries("sat_chl_l4_nrt", LAT, LON, pd.Timestamp.today().normalize() - pd.Timedelta(days=21),
                           pd.Timestamp.today().normalize(), variables=["chl"])
an = log_anom(nrt["chl"].dropna(), clim)
print(f"\nB1 latest anomalies (sat_chl_l4_nrt, cell {nrt.attrs['grid_lat']},{nrt.attrs['grid_lon']}):")
print(an.tail(8).round(2).to_string())
recent = log_anom(chl.loc["2021":], clim)
print(f"Share of days 2021-2025 above p90: {100 * (recent['flag'] == 'above_p90').mean():.1f} % "
      f"(expected 10 % if nothing changed); below p10: {100 * (recent['flag'] == 'below_p10').mean():.1f} %")

# Cross-check with an independent product: ESA OC-CCI 8-day (open_data), its own log climatology 1998-2020
hdr("B1 cross-check  ESA OC-CCI v6 8-day (open_data.chl_occi_8day)")
try:
    a = od.anomalies("chl_occi_8day", LAT, LON, "2025-05-01", "2025-09-30", years=(1998, 2020))
    print(f"pixel ({a.attrs['pixel_lat']}, {a.attrs['pixel_lon']}), dist {a.attrs['pixel_dist_km']} km")
    print(a[["value", "clim_mean", "clim_p90", "anomaly_ratio", "z", "above_p90"]].round(2).to_string())
except Exception as ex:
    print("OC-CCI check failed:", type(ex).__name__, ex)

# Natural driver check: is the chl signal Danube-driven? GloFAS discharge at the delta apex (open_data)
hdr("B1/B2 driver check  Danube discharge (GloFAS v4, open_data.danube_discharge) vs chl at Constanta")
try:
    q = od.danube_discharge("1998-01-01", "2025-12-31")["discharge"].dropna()
    drv = pd.DataFrame({
        "Q_annual_m3s": q.groupby(q.index.year).mean(),
        "Q_FebMay_m3s": q[q.index.month.isin([2, 3, 4, 5])].groupby(lambda t: t.year).mean(),
    }).join(ann[["gmean", "spring_MAM_gmean", "bloom_abs10_days"]])
    print(drv.round(2).to_string())
    for a_, b_ in [("Q_annual_m3s", "gmean"), ("Q_FebMay_m3s", "spring_MAM_gmean"), ("Q_annual_m3s", "bloom_abs10_days")]:
        print(f"Spearman rho({a_}, {b_}) = {drv[a_].corr(drv[b_], method='spearman'):+.2f}  (n={drv[[a_, b_]].dropna().shape[0]} years)")
except Exception as ex:
    print("Danube check failed:", type(ex).__name__, ex)

# =========================================================================================== B3
hdr("B3  Phytoplankton size classes (satellite, OCEANCOLOUR_BLK_BGC_L3_MY_009_153: MICRO / NANO / PICO)")
# sat_pft_l3_my / sat_pft_l3_nrt are CATALOG keys in copernicus.py (size classes, not taxonomy)
for yr in (2005, 2024):
    pft = cop.fetch_timeseries("sat_pft_l3_my", LAT, LON, f"{yr}-01-01", f"{yr}-12-31").dropna(subset=["chl"])
    tot = pft[["micro", "nano", "pico"]].sum(axis=1)
    pft["micro_share"] = pft["micro"] / tot
    m = pft.groupby(pft.index.month).agg(days=("chl", "size"), chl=("chl", "median"),
                                         micro=("micro_share", "median"))
    print(f"{yr}: valid days {len(pft)}; monthly median chl and MICRO share (micro / (micro+nano+pico)):")
    print("   " + "  ".join(f"{k}:{r.chl:.1f}/{r.micro:.2f}(n{int(r.days)})" for k, r in m.iterrows()))

hdr("B3  In-situ reference: NIMRD phytoplankton counts off Constanta from OBIS (surface <= 5 m)")
ph = pd.concat([obis_phyto_counts(c, BOX_CTA_WKT) for c in ("Bacillariophyceae", "Dinophyceae", "Coccolithophyceae")])
ph = ph.dropna(subset=["cells_per_l"])
ph["date"] = pd.to_datetime(ph["date"].str[:10], errors="coerce")
ph = ph.dropna(subset=["date"])
smp = ph.pivot_table(index=["date", "lat", "lon", "depth"], columns="class", values="cells_per_l", aggfunc="sum", fill_value=0)
smp["total"] = smp.sum(axis=1)
smp["diatom_share"] = smp.get("Bacillariophyceae", 0) / smp["total"]
smp["year"] = smp.index.get_level_values("date").year
smp["decade"] = smp["year"] // 10 * 10
print(f"records with abundance: {len(ph)}; samples: {len(smp)}; years {smp['year'].min()}-{smp['year'].max()}; "
      f"datasets: {ph['dataset'].nunique()}")
dec = smp.groupby("decade").agg(samples=("total", "size"), median_total_cells_l=("total", "median"),
                                bloom_samples_gt1e6=("total", lambda x: int((x > 1e6).sum())),
                                median_diatom_share=("diatom_share", "median"))
print(dec.round(2).to_string())
top = ph[ph["cells_per_l"] > 1e6].groupby("taxon").size().sort_values(ascending=False).head(10)
print("Taxa with single-taxon counts > 1e6 cells/L (bloom-forming), number of records:")
print("   " + "; ".join(f"{k} {v}" for k, v in top.items()))

# =========================================================================================== B4
hdr("B4  Primary production: satellite PP (OCEANCOLOUR_BLK_BGC_L4_MY_009_154) vs model nppv (BLKSEA_MULTIYEAR_BGC_007_005)")
# sat_pp_my / sat_pp_nrt are CATALOG keys in copernicus.py
pp = cop.fetch_timeseries("sat_pp_my", LAT, LON, "2024-01-01", "2024-12-31")
mod = cop.fetch_timeseries("rea_bgc_o2", LAT, LON, "2024-01-01", "2024-12-31", variables=["nppv"])
print(f"satellite PP cell ({pp.attrs['grid_lat']}, {pp.attrs['grid_lon']}) dist {pp.attrs['distance_km']} km; "
      f"model cell ({mod.attrs['grid_lat']}, {mod.attrs['grid_lon']}) surface nppv in mg C m-3 d-1")
m = pd.DataFrame({"sat_pp_gC_m2_d": pp["pp"].resample("MS").mean(), "model_npp_surf_mgC_m3_d": mod["npp"].resample("MS").mean()})
print(m.round(2).T.to_string())
print(f"2024 annual satellite PP: {pp['pp'].mean() * 365:.0f} g C m-2 yr-1 (mean x 365)")

# =========================================================================================== B5
hdr("B5  Mussel-bed hypoxia exposure: bottom O2 at Mytilus bed sites (model reanalysis)")
myt = obis_json("/occurrence", {"geometry": BOX_RO_WKT, "scientificname": "Mytilus galloprovincialis", "size": 1000,
                                "fields": "decimalLatitude,decimalLongitude,date_year,datasetName,institutionCode,maximumDepthInMeters"},
                "myt")["results"]
myt = pd.DataFrame(myt)
print(f"OBIS Mytilus galloprovincialis records in the Romanian box: {len(myt)}; years "
      f"{int(myt['date_year'].min())}-{int(myt['date_year'].max())}; with depth: {myt['maximumDepthInMeters'].notna().sum()}")
print("depth quantiles of records (m):", myt["maximumDepthInMeters"].quantile([.1, .5, .9]).round(1).to_dict())
# Test sites: two Mytilus-reef stations of the NIMRD "Est Constanta" profile (positions derived from OBIS, see the
# stations section; RO-MSFD-2024 Table IV.2.2.13 lists Est Constanta 2-4 as Mytilus reef stations) and the inshore point.
sites = {"Est_Constanta_36m_44.167N_28.900E": (44.167, 28.900), "Est_Constanta_47m_44.167N_29.133E": (44.167, 29.133),
         "Constanta_inshore_44.17N_28.72E": (LAT, LON)}
MG = 0.032  # mg/L per mmol m-3


def o2_solubility_umol_kg(t, s):
    """O2 saturation concentration (umol/kg), Garcia & Gordon 1992 (Benson & Krause fit); same formula as chemical_check.py."""
    a = [5.80871, 3.20291, 4.17887, 5.10006, -9.86643e-2, 3.80369]
    b = [-7.01577e-3, -7.70028e-3, -1.13864e-2, -9.51519e-3]
    ts = np.log((298.15 - t) / (273.15 + t))
    return np.exp(a[0] + a[1] * ts + a[2] * ts ** 2 + a[3] * ts ** 3 + a[4] * ts ** 4 + a[5] * ts ** 5
                  + s * (b[0] + b[1] * ts + b[2] * ts ** 2 + b[3] * ts ** 3) - 2.75915e-7 * s ** 2)


def o2_class(mgl: float) -> str:
    """Bottom-O2 class shared with the chemical session: A >= 5, B 4-5, C 2-4, D < 2 mg/L."""
    return "A" if mgl >= 5 else "B" if mgl >= 4 else "C" if mgl >= 2 else "D"


for name, (la, lo) in sites.items():
    zsite = el.depth_at(la, lo)
    o = cop.fetch_timeseries("rea_bgc_o2", la, lo, "2010-01-01", "2024-12-31", variables=["o2b"])
    bt = cop.fetch_timeseries("rea_phy_temp", la, lo, "2010-01-01", "2024-12-31", variables=["bottomT"])
    bs = cop.fetch_timeseries("rea_phy_sal", la, lo, "2010-01-01", "2024-12-31", depth=zsite)
    d = pd.concat([o["o2_bottom"] * MG, bt["bottom_temp"], bs["sal"]], axis=1, keys=["o2_mgl", "t", "s"]).dropna()
    d["sat_pct"] = 100 * (d["o2_mgl"] / MG) / (o2_solubility_umol_kg(d["t"], d["s"]) * (1000 + 0.78 * d["s"]) / 1000)
    d["cls"] = d["o2_mgl"].map(o2_class)
    g = d.groupby(d.index.year)
    ws = d[d.index.month.isin([5, 6, 7, 8, 9])].groupby(lambda t: t.year)
    yr = pd.DataFrame({
        "min_mgL": g["o2_mgl"].min().round(2),
        **{f"days_{c}": g["cls"].apply(lambda x, c=c: int((x == c).sum())) for c in "ABCD"},
        "days_lt3_OURS": g["o2_mgl"].apply(lambda x: int((x < 3).sum())),
        "D5C5_P10_mgL": ws["o2_mgl"].quantile(0.10).round(2),
        "D5C5_P10_sat": ws["sat_pct"].quantile(0.10).round(1),
    })
    yr["D5C5_pass"] = (yr["D5C5_P10_mgL"] >= 5) & (yr["D5C5_P10_sat"] >= 60)
    print(f"\n{name}: model cell ({o.attrs['grid_lat']}, {o.attrs['grid_lon']}), depth at site (EMODnet) {zsite:.0f} m, "
          f"salinity level {bs.attrs.get('depth_m')} m. Classes A >= 5, B 4-5, C 2-4, D < 2 mg/L (shared with chemical "
          f"session); D5C5 = official RO seasonal test May-Sep P10 >= 5 mg/L and >= 60 % sat; days_lt3 = our stress marker.")
    print(yr.T.to_string())
    print(f"  years failing D5C5: {int((~yr['D5C5_pass']).sum())} of {len(yr)}; years with any class D day: {int((yr['days_D'] > 0).sum())}; "
          f"with any class C day: {int((yr['days_C'] > 0).sum())}")

# =========================================================================================== B6
hdr("B6  Non-indigenous and gelatinous species: OBIS occurrence evidence in the Romanian box (28.4-30.6E, 43.6-45.4N)")
NIS = {  # taxon: (group, NIS?)
    "Mnemiopsis leidyi": ("ctenophore", True), "Beroe ovata": ("ctenophore", True), "Rapana venosa": ("gastropod", True),
    "Mya arenaria": ("bivalve", True), "Anadara kagoshimensis": ("bivalve", True), "Rhithropanopeus harrisii": ("crab", True),
    "Acartia tonsa": ("copepod", True), "Aurelia aurita": ("jellyfish", False), "Rhizostoma pulmo": ("jellyfish", False),
    "Noctiluca scintillans": ("dinoflagellate", False), "Mytilus galloprovincialis": ("bivalve", False),
    "Modiolula phaseolina": ("bivalve", False), "Zostera noltei": ("seagrass", False),
    "Cystoseira barbata": ("brown alga (=Gongolaria barbata)", False), "Phyllophora crispa": ("red alga", False),
    "Phocoena phocoena": ("porpoise", False), "Tursiops truncatus": ("dolphin", False), "Delphinus delphis": ("dolphin", False),
    "Sprattus sprattus": ("fish", False), "Engraulis encrasicolus": ("fish", False), "Scophthalmus maeoticus": ("fish (turbot)", False),
}
rows = []
for t, (grp, nis) in NIS.items():
    s = obis_json("/statistics", {"geometry": BOX_RO_WKT, "scientificname": t}, "stat")
    y = obis_json("/statistics/years", {"geometry": BOX_RO_WKT, "scientificname": t}, "years")
    y = [r for r in (y if isinstance(y, list) else []) if r.get("records")]
    yrs = [r["year"] for r in y]
    rows.append(dict(taxon=t, group=grp, NIS=nis, records=s.get("records", 0), datasets=s.get("datasets", 0),
                     first=min(yrs) if yrs else None, last=max(yrs) if yrs else None,
                     since_2015=sum(r["records"] for r in y if r["year"] >= 2015)))
tab = pd.DataFrame(rows)
print(tab.to_string(index=False))
nis_recent = tab[(tab.NIS) & (tab.since_2015 > 0)]
print(f"\nNIS with at least one OBIS record since 2015: {len(nis_recent)} of {int(tab.NIS.sum())} listed "
      f"({', '.join(nis_recent.taxon)})")
mb = obis_json("/statistics/years", {"geometry": BOX_RO_WKT, "scientificname": "Mnemiopsis leidyi"}, "years")
bo = obis_json("/statistics/years", {"geometry": BOX_RO_WKT, "scientificname": "Beroe ovata"}, "years")
bo = {r["year"]: r["records"] for r in bo}
print("Mnemiopsis / Beroe records per year (effort-biased, presence only):",
      " ".join(f"{r['year']}:{r['records']}/{bo.get(r['year'], 0)}" for r in sorted(mb, key=lambda r: r["year"]) if r["year"] >= 1995))

# =========================================================================================== B7
hdr("B7  Biological evidence coverage: EurOBIS record grid (EMODnet Biology WFS) and cetacean strandings")
gj = el.fetch_wfs("biology_records_grid")
cells = pd.DataFrame([f["properties"] for f in gj["features"]])
rc = [c for c in cells.columns if c.lower() == "recordcount"]
if rc:
    rc = rc[0]
    print(f"EurOBIS 15' grid cells in BBOX_RO: {len(cells)}; total records {int(cells[rc].sum())}; "
          f"median per cell {cells[rc].median():.0f}; max {int(cells[rc].max())}")
else:
    print("grid cells:", len(cells), "columns:", list(cells.columns))
st = obis_json("/occurrence", {"geometry": BOX_RO_WKT, "datasetid": None, "scientificname": "Cetacea", "size": 5000,
                               "fields": "date_year,scientificName,datasetName,institutionCode"}, "cet")["results"]
st = pd.DataFrame(st)
st = st[st["datasetName"].fillna("").str.contains("Strandings along Romanian", case=False)]
if len(st):
    print("Strandings along the Romanian coast (Mare Nostrum dataset in OBIS), records per year and species:")
    print(st.pivot_table(index="date_year", columns="scientificName", aggfunc="size", fill_value=0).to_string())

# =========================================================================================== stations
hdr("NIMRD monitoring profiles: positions derived from OBIS (plankton 2011-2015), for the map and for field validation")
fp = cached_path("obis", cache_key("nimrd_stations_v1"), "parquet")
if fp.exists():
    stn = pd.read_parquet(fp)
else:
    dsl = obis_json("/dataset", {"geometry": BOX_RO_WKT, "size": 200}, "datasets")["results"]
    ids = [d["id"] for d in dsl if d["title"].startswith(("Romanian Black Sea Phytoplankton data from 2006",
                                                           "Romanian Black Sea Zooplankton data from 2011"))]
    rows = []
    for did in ids:
        after = None
        while True:
            p = {"datasetid": did, "size": 5000, "startdate": "2011-01-01",
                 "fields": "id,locality,decimalLatitude,decimalLongitude,date_year,maximumDepthInMeters"}
            if after:
                p["after"] = after
            res = requests.get(OBIS + "/occurrence", params=p, headers=UA, timeout=300).json()["results"]
            rows += res
            if len(res) < 5000:
                break
            after = res[-1]["id"]
    raw = pd.DataFrame(rows)
    raw["lat"], raw["lon"] = raw["decimalLatitude"].round(3), raw["decimalLongitude"].round(3)
    stn = (raw.groupby(["locality", "lat", "lon"])
           .agg(records=("id", "size"), first=("date_year", "min"), last=("date_year", "max"),
                max_sample_depth_m=("maximumDepthInMeters", "max"))
           .reset_index().query("records >= 50").sort_values(["lat", "lon"], ascending=[False, True]))
    stn.to_parquet(fp)
prof = stn.groupby("locality").agg(lat=("lat", "median"), lon_min=("lon", "min"), lon_max=("lon", "max"),
                                   n_positions=("lon", "size"), max_depth_m=("max_sample_depth_m", "max"))
print(prof.sort_values("lat", ascending=False).round(3).to_string())
print("\nEst Constanta profile positions:")
print(stn[stn["locality"] == "Est Constanta"].to_string(index=False))

print(f"\nDone in {time.time() - T0:.0f} s. Sources: Copernicus Marine (DOIs in attrs), ESA OC-CCI v6 via NOAA PIFSC ERDDAP, "
      f"OBIS (api.obis.org, accessed {pd.Timestamp.today().date()}), EMODnet Biology (VLIZ).")
