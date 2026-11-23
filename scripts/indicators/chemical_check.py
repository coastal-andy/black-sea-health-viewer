"""Chemical indicators for the Romanian shelf: live computability check at Constanta (44.17 N, 28.72 E).

Run from the repo root:
    .venv/bin/python scripts/indicators/chemical_check.py | tee scripts/indicators/chemical_check_output.txt

Every fetch goes through the verified modules in src/marinekit/sources/ and is cached by them
(data/cache/...), so a second run works offline. Each section is independent: a failure prints
"NOT COMPUTED" with the reason and the script continues.

Indicators (see docs/indicators/chemical.md for the science, thresholds and sources):
  C1  Bottom-oxygen status class + hypoxia days                bgc_o2 (o2_bottom) vs rea_bgc_o2; EMODnet bottles
  C2  Surface O2 saturation and its anomaly                     EUXRoOB0x OSAT (measured); bgc_o2 + phy_temp/phy_sal
  C3  Nutrient status: DIN, PO4, Si against reference values    EMODnet Chemistry samples + DIVAnd climatologies
  C4  Nutrient stoichiometry N:P and Si:N                       same as C3
  C5  Eutrophication index (simplified BEAST/HEAT)              sat_chl_l4_my + bgc_o2 + DIVAnd nutrients
  C6  pH / carbonate-system watch                               bgc_car vs rea_bgc_car (model only)
  C7  Bathing-water class (microbiology, EU BWD)                emodnet_layers 'bathing_waters'
  R   Model-vs-observation reliability for O2 and nutrients     rea/anfc vs bottles and buoys
  D   Natural-variability driver: Danube discharge              open_data.danube_discharge
"""
from __future__ import annotations

import collections
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from marinekit.sources import copernicus as cm  # noqa: E402
from marinekit.sources import emodnet_insitu as ei  # noqa: E402
from marinekit.sources import emodnet_layers as el  # noqa: E402
from marinekit.sources import open_data as od  # noqa: E402

LAT, LON = 44.17, 28.72                 # Constanta test point (model cell 44.175 / 28.725, ~26 m deep)
TODAY = pd.Timestamp("2026-11-23")
ANFC0, ANFC1 = "2024-10-03", "2026-11-30"   # whole BGC analysis/forecast record (same window -> same cache)
REA0, REA1 = "1993-01-01", "2024-12-31"     # whole BGC reanalysis record
O2_MG = 0.032                           # mmol m-3 -> mg/L
pd.set_option("display.width", 170)
pd.set_option("display.max_columns", 30)

# --------------------------------------------------------------------------------------- thresholds
# OFFICIAL = in a legal act / official assessment; LIT = literature convention; OURS = proposed by us.
BOX_CLASSES = [  # daily bottom dissolved oxygen, mg/L, lower bound inclusive
    (5.0, "A meets D5C5 level (>= 5 mg/L)"),             # OFFICIAL boundary value (RO MSFD D5C5, applied there to the P10)
    (4.0, "B below GES level (4-5 mg/L)"),               # OURS (sublethal effects, Vaquer-Sunyer & Duarte 2008)
    (2.0, "C hypoxia risk (2-4 mg/L)"),                  # OURS
    (0.0, "D hypoxic (< 2 mg/L)"),                       # LIT: 2 mg/L = 62.5 mmol m-3 (Diaz & Rosenberg 2008; Capet 2013)
]
HYPOXIA_MG = 2.0                        # LIT
# Romanian MSFD D5C5 (OFFICIAL; NIMRD 2024 Art.17 study, Table III.7.1): P10 of bottom O2 in the warm season
# (May-Sep), stations <= 50 m, must be >= 5 mg/L and >= 60 % saturation.
D5C5_MG, D5C5_SAT = 5.0, 60.0
# Eutrophication index targets (ER = observed / target; for O2 ER = target / observed).
# OFFICIAL Romanian MSFD values for "marine waters" (the Constanta point is ~5 km offshore, outside the
# 1-nm WFD coastal strip), NIMRD 2024 Art.17 study, Table III.7.1. Nutrients are P75 values, chl warm season.
TARGETS = {
    "din": 10.5,            # umol/L, marine waters, P75 (OFFICIAL; coastal waters RO-CT: 13.5)
    "po4": 0.23,            # umol/L, marine waters, P75 (OFFICIAL; coastal waters RO-CT: 0.30)
    "chl_warm": 2.79,       # mg m-3, marine waters south, warm season (OFFICIAL)
    "o2_bottom_p10": D5C5_MG,
}
HEAT_CLASSES = [(0.5, "high"), (1.0, "good"), (1.5, "moderate"), (2.0, "poor"), (np.inf, "bad")]  # HELCOM HEAT 3.0


# ------------------------------------------------------------------------------------------- helpers
def section(title: str):
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


def run(title: str, fn):
    section(title)
    t = time.time()
    try:
        fn()
        print(f"STATUS: COMPUTED ({time.time() - t:.0f} s)")
    except Exception as e:  # noqa: BLE001
        print(f"STATUS: NOT COMPUTED: {type(e).__name__}: {e}")


def box_class(mg: float) -> str:
    if pd.isna(mg):
        return "no data"
    for lo, name in BOX_CLASSES:
        if mg >= lo:
            return name
    return BOX_CLASSES[-1][1]


def longest_run(mask: pd.Series) -> int:
    """Longest run of consecutive True days (mussels survive days-weeks of anoxia: duration matters)."""
    best = cur = 0
    for v in mask.values:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def heat_class(er: float) -> str:
    return next(name for hi, name in HEAT_CLASSES if er <= hi)


def o2_solubility_umol_kg(t, s):
    """O2 saturation concentration (umol/kg), Garcia & Gordon 1992, Benson & Krause fit."""
    a = [5.80871, 3.20291, 4.17887, 5.10006, -9.86643e-2, 3.80369]
    b = [-7.01577e-3, -7.70028e-3, -1.13864e-2, -9.51519e-3]
    c0 = -2.75915e-7
    ts = np.log((298.15 - t) / (273.15 + t))
    ln_c = (a[0] + a[1] * ts + a[2] * ts**2 + a[3] * ts**3 + a[4] * ts**4 + a[5] * ts**5
            + s * (b[0] + b[1] * ts + b[2] * ts**2 + b[3] * ts**3) + c0 * s**2)
    return np.exp(ln_c)


def rho_approx(t, s):
    """Rough seawater density (kg/L) for umol/kg -> umol/L at shelf T/S (error << 0.1 %)."""
    return (1000 + 0.78 * s - 0.0065 * (t - 4) ** 2) / 1000


def o2_saturation_pct(o2_mmol_m3, t, s):
    return 100 * o2_mmol_m3 / (o2_solubility_umol_kg(t, s) * rho_approx(t, s))


def cmp(obs: pd.Series, mod: pd.Series, label: str, unit: str, scale: float = 1.0) -> dict:
    j = pd.concat([obs.rename("obs"), mod.rename("mod")], axis=1).dropna() * scale
    if len(j) < 3:
        print(f"  {label}: n={len(j)} (too few pairs)")
        return {}
    d = j["mod"] - j["obs"]
    r = j["obs"].corr(j["mod"])
    out = dict(n=len(j), obs=j.obs.mean(), mod=j["mod"].mean(), bias=d.mean(), rmse=float(np.sqrt((d**2).mean())), r=r)
    print(f"  {label:58s} n={out['n']:5d} obs={out['obs']:7.2f} mod={out['mod']:7.2f} "
          f"bias={out['bias']:+6.2f} rmse={out['rmse']:5.2f} r={r:5.2f} [{unit}]")
    return out


_cache: dict = {}


def anfc(key):
    if key not in _cache:
        _cache[key] = cm.fetch_timeseries(key, LAT, LON, ANFC0, ANFC1)
    return _cache[key]


def rea(key):
    if key not in _cache:
        _cache[key] = cm.fetch_timeseries(key, LAT, LON, REA0, REA1)
    return _cache[key]


def bottles():
    """EMODnet Chemistry bottle samples within 30 km of Constanta, whole water column."""
    if "bottles" not in _cache:
        _cache["bottles"] = ei.fetch_chemistry_samples(
            LAT, LON, 30, variables=["temp", "sal", "o2", "do_sat", "no3", "no2", "nh4", "po4", "si", "ph", "chl"],
            max_depth=None)
    return _cache["bottles"]


def bottom_bottles(min_depth=15.0):
    c = bottles().dropna(subset=["o2"]).reset_index()
    c["cast"] = c.station + "|" + c.time.dt.strftime("%Y-%m-%d")
    b = c.loc[c.groupby("cast").depth.idxmax()]
    return b[b.depth >= min_depth].set_index("time")


def divand(var, product="danube", depth=0.0, **kw):
    k = ("div", var, product, depth, tuple(kw.items()))
    if k not in _cache:
        _cache[k] = ei.chemistry_climatology_at(LAT, LON, var, product, depth=depth, **kw)
    return _cache[k]


# ------------------------------------------------------------------------------------------- C1
def c1():
    f = anfc("bgc_o2")
    r = rea("rea_bgc_o2")
    print(f"model cell {f.attrs.get('grid_lat')}/{f.attrs.get('grid_lon')} ({f.attrs.get('distance_km')} km); "
          f"o2_bottom is the deepest wet level of that cell")
    fb = f["o2_bottom"] * O2_MG
    rb = r["o2_bottom"] * O2_MG
    last = fb[fb.index <= TODAY].dropna()
    print(f"\nLatest analysis day {last.index[-1].date()}: bottom O2 {last.iloc[-1]:.2f} mg/L -> {box_class(last.iloc[-1])}")
    fc = fb[fb.index > TODAY]
    if len(fc):
        print(f"Forecast to {fc.index[-1].date()}: min {fc.min():.2f} mg/L -> {box_class(fc.min())}")
    clim = cm.climatology("bgc_o2", LAT, LON, variable="o2_bottom")
    a = cm.anomalies(f[["o2_bottom"]].loc[TODAY - pd.Timedelta(days=60):TODAY], clim, "o2_bottom")
    print("\nLast 60 days vs reanalysis day-of-year climatology 1993-2022 (mmol m-3), weekly means:")
    print(a[["o2_bottom", "clim_mean", "clim_p10", "anomaly", "zscore"]].resample("7D").mean().round(1).to_string())
    print("  NOTE: forecast-system bottom O2 sits ~2 mg/L below the reanalysis in the 2024 overlap (section R), so a")
    print("        negative anomaly here is partly a model-system offset. Use the absolute class, not the anomaly.")

    print("\nWarm-season (May-Sep) summary per year, bottom O2; D5C5 test = P10 >= 5 mg/L AND P10 sat >= 60 %:")
    tb = pd.concat([cm.fetch_timeseries("rea_phy_temp", LAT, LON, REA0, "2025-07-31", variables=["bottom_temp"]).bottom_temp,
                    cm.fetch_timeseries("phy_temp", LAT, LON, "2024-12-01", ANFC1, variables=["bottom_temp"]).bottom_temp])
    tb = tb[~tb.index.duplicated(keep="last")]
    sbot = 18.0  # PSU, typical bottom salinity at 20-30 m off Constanta (model 17.5-19.5); saturation weakly S-dependent
    rows = []
    for name, s in (("reanalysis", rb), ("analysis/forecast", fb)):
        s = s[s.index.month.isin([5, 6, 7, 8, 9])]
        sat = o2_saturation_pct(s / O2_MG, tb.reindex(s.index), sbot)
        for y, g in s.groupby(s.index.year):
            p10, p10s = g.quantile(.1), sat[g.index].quantile(.1)
            rows.append(dict(system=name, year=y, min=g.min(), p10=p10, p10_sat=p10s, days_lt2=(g < 2).sum(),
                             days_lt4=(g < 4).sum(), run_lt4=longest_run(g < 4),
                             D5C5="pass" if (p10 >= D5C5_MG and p10s >= D5C5_SAT) else "FAIL",
                             cls_min=box_class(g.min())))
    t = pd.DataFrame(rows)
    print(t[t.year >= 2014].round(2).to_string(index=False))
    rea_hist = t[t.system == "reanalysis"]
    print(f"Reanalysis 1993-2024 (May-Sep): years with any day < 2 mg/L: {(rea_hist.days_lt2 > 0).sum()}; "
          f"years with min < 4 mg/L: {(rea_hist['min'] < 4).sum()}; D5C5 fails: {(rea_hist.D5C5 == 'FAIL').sum()} "
          f"of {len(rea_hist)} years")
    print("  (official NIMRD 2018-2023 bottom-water P10 at 20-50 m: 5.44 mg/L, 54.3 % saturation)")

    # Attribution of each low-O2 episode (natural intrusion of deep water vs bloom-decay / eutrophication type)
    t = cm.fetch_timeseries("phy_temp", LAT, LON, "2024-12-01", ANFC1, variables=["bottom_temp", "temp"])
    sb = cm.fetch_timeseries("phy_sal", LAT, LON, "2024-12-01", ANFC1, variables=["sal"], depth=24)
    j = pd.concat([fb.rename("o2b"), t.bottom_temp.rename("tb"), t.temp.rename("ts"), sb.sal.rename("sb")], axis=1).dropna()
    j["dtb7"] = j.tb - j.tb.shift(7)
    j["strat"] = j.ts - j.tb
    low = j[j.o2b < 4]
    if len(low):
        ep = (low.index.to_series().diff() > pd.Timedelta(days=2)).cumsum()
        print("\nLow-O2 episodes (< 4 mg/L) in the analysis/forecast since 2024-12, with attribution test:")
        for _, g in low.groupby(ep.values):
            k = j.loc[g.index]
            cause = ("deep-water intrusion / upwelling (cold, saline): NATURAL"
                     if (k.dtb7.min() < -1.5 or k.sb.max() > 18.5) else
                     "warm stratified bottom water: bloom-decay / EUTROPHICATION type" if k.strat.mean() > 2
                     else "unclear: check model and observations")
            print(f"  {g.index[0].date()}..{g.index[-1].date()} ({len(g)} d): min {k.o2b.min():.2f} mg/L, "
                  f"bottom T change over 7 d {k.dtb7.min():+.1f} C, S(24 m) max {k.sb.max():.2f}, "
                  f"surface-bottom dT {k.strat.mean():+.1f} C -> {cause}")
    print("  Rule: O2 < 4 mg/L with bottom T falling > 1.5 C/week or S(24 m) > 18.5 = shelf-break water (natural);")
    print("        with a warm stratified column (Ts - Tb > 2 C) in May-Oct = organic-matter decay (pressure-related).")

    b = bottom_bottles()
    b = b[b.index.month.isin([7, 8, 9, 10])]
    dec = (b.index.year // 10) * 10
    g = b.groupby(dec)["do"]
    print("\nObserved bottom O2 (deepest bottle >= 15 m, Jul-Oct, <= 30 km from Constanta), EMODnet Chemistry:")
    print(pd.DataFrame({"casts": g.count(), "median": g.median(), "p10": g.quantile(.1),
                        "share<2": g.apply(lambda s: (s < 2).mean()), "share<4": g.apply(lambda s: (s < 4).mean())})
          .round(2).to_string())


# ------------------------------------------------------------------------------------------- C2
def c2():
    o = ei.fetch_platform("EUXRoOB03", "2025-01-01", "2026-09-01", ["o2", "do_sat", "temp", "sal"], resample="1D")
    calc = o2_saturation_pct(o.o2, o.temp, o.sal)
    print("Validation of our saturation formula against the buoy's own OSAT (EUXRoOB03, 3 m, daily):")
    cmp(o.do_sat, calc, "computed %sat (Garcia&Gordon 1992) vs buoy OSAT", "%")
    m = o.resample("ME").mean()
    print("\nEUXRoOB03 monthly means (measured):")
    print(pd.DataFrame({"do_mg_L": m.o2 * O2_MG, "sat_pct": m.do_sat, "temp": m.temp, "sal": m.sal}).round(2).T.to_string())

    f = anfc("bgc_o2")
    t = cm.fetch_timeseries("phy_temp", LAT, LON, "2024-12-01", ANFC1, variables=["temp"])
    s = cm.fetch_timeseries("phy_sal", LAT, LON, "2024-12-01", ANFC1, variables=["sal"])
    j = pd.concat([f.o2, t.temp, s.sal], axis=1).dropna()
    j["sat"] = o2_saturation_pct(j.o2, j.temp, j.sal)
    j["flag"] = np.select([j.sat > 120, j.sat < 80], ["supersat >120% (bloom)", "undersat <80% (respiration/upwelling)"], "normal")
    rec = j.loc[TODAY - pd.Timedelta(days=30):TODAY]
    print(f"\nModel surface O2 saturation at Constanta, last 30 days: mean {rec.sat.mean():.1f} %, "
          f"range {rec.sat.min():.1f}-{rec.sat.max():.1f} %")
    print("Model days per flag since 2024-12:", dict(collections.Counter(j.flag)))


# ------------------------------------------------------------------------------------------- C3 / C4
def c3_c4():
    c = bottles()
    s = c[c.depth <= 5].copy()
    s["din"] = s[["no3", "no2", "nh4"]].sum(axis=1, min_count=2)
    s["winter"] = s.index.month.isin([12, 1, 2, 3])
    dec = (s.index.year // 10) * 10
    print("Observed surface (0-5 m) medians by decade, <= 30 km from Constanta (EMODnet Chemistry, mmol m-3):")
    g = s.groupby(dec)
    print(pd.DataFrame({"n_po4": g.po4.count(), "no3": g.no3.median(), "nh4": g.nh4.median(), "din": g.din.median(),
                        "po4": g.po4.median(), "si": g.si.median(),
                        "N:P": g.apply(lambda x: (x.din / x.po4).median()),
                        "Si:N": g.apply(lambda x: (x.si / x.din).median())}).round(2).to_string())
    print(f"Last sample with nutrients in this circle: {s.dropna(subset=['po4']).index.max().date()}")

    print("\nDIVAnd 'Danube Delta' seasonal climatology at Constanta (NIMRD/EMODnet; DIN 1980-2022, PO4/Si 1970-2022):")
    tab = {}
    for v in ("din", "po4", "si"):
        for dep in (0.0, 20.0):
            d = divand(v, "danube", dep)
            tab[f"{v}_{int(dep)}m"] = d.set_index("season")[f"{v}_L1"]
    tab = pd.DataFrame(tab)
    tab["N:P_0m"] = tab.din_0m / tab.po4_0m
    tab["Si:N_0m"] = tab.si_0m / tab.din_0m
    print(tab.round(2).to_string())

    print("\nDIVAnd 'Black Sea' moving 6-year windows (surface), trusted (_L1, relerr < 0.3) values:")
    w = {}
    for v in ("din", "po4", "si"):
        d = divand(v, "blacksea", 0.0)
        p = d.pivot_table(index=d.index.year, columns="season", values=f"{v}_L1")
        w[v] = p
        print(f"  {v}: " + ", ".join(f"{y}: W {p.loc[y, 'winter']:.2f} / S {p.loc[y, 'summer']:.2f}"
                                     for y in (1985, 1995, 2005, 2015, 2020) if y in p.index))
    din_c, po4_c = tab.loc["winter", "din_0m"], tab.loc["winter", "po4_0m"]
    print("\nC3 nutrient status, latest trusted window per variable (DIVAnd Black Sea) vs Danube climatology:")
    lw = {}
    for v, name, clim in (("din", "DIN", din_c), ("po4", "PO4", po4_c), ("si", "Si", tab.loc["winter", "si_0m"])):
        s = w[v]["winter"].dropna()
        y, val = s.index[-1], s.iloc[-1]
        lw[v] = (y, val)
        print(f"  winter {name}: {val:.2f} mmol m-3 (window centred {y}); Danube climatology {clim:.2f} "
              f"(ratio {val / clim:.2f})")
    ss = {v: w[v]["summer"].dropna() for v in ("din", "po4", "si")}
    ys = min(s.index[-1] for s in ss.values())
    print(f"  summer {ys}: DIN {ss['din'][ys]:.2f}, PO4 {ss['po4'][ys]:.2f}, Si {ss['si'][ys]:.2f} mmol m-3")
    for name, v, tgt, tc in (("DIN", "din", TARGETS["din"], 13.5), ("PO4", "po4", TARGETS["po4"], 0.30)):
        val = ss[v][ys]
        print(f"  summer {name} vs OFFICIAL marine threshold {tgt} (P75): ER {val / tgt:.2f} ({heat_class(val / tgt)}); "
              f"vs coastal-water threshold {tc}: ER {val / tc:.2f}")
    print("  (official NIMRD 2018-2023 P75 on the shelf MT01: DIN 13.78, PO4 0.27 umol/L; offshore MT02: 2.53, 0.08)")
    print(f"C4 stoichiometry, summer window {ys}: N:P = {ss['din'][ys] / ss['po4'][ys]:.1f} (Redfield 16), "
          f"Si:N = {ss['si'][ys] / ss['din'][ys]:.2f} (Redfield ~1)")
    y0 = max(lw[v][0] for v in lw)
    print(f"C4 stoichiometry, latest common winter window: N:P = {lw['din'][1] / lw['po4'][1]:.1f}, "
          f"Si:N = {lw['si'][1] / lw['din'][1]:.2f} (windows {', '.join(f'{k} {v[0]}' for k, v in lw.items())})")
    print("  NOTE: winter windows after ~2012-2016 are masked (relerr > 0.3: almost no winter cruises). Summer is the")
    print(f"        only season with trusted values up to {ys}. Latest bottle sample with nutrients here: 1999.")


# ------------------------------------------------------------------------------------------- C5
def c5():
    # Warm season (May-Sep) for every criterion, as in the Romanian BEAST assessment.
    # direct effect: satellite chl, May-Sep 2025 mean (arithmetic, as the threshold is a concentration level)
    chl = cm.fetch_timeseries("sat_chl_l4_my", LAT, LON, "2025-05-01", "2025-09-30", variables=["chl"])
    chl_s = float(chl.chl.mean())
    # indirect effect: P10 of daily bottom O2, May-Sep 2025, analysis/forecast model
    fb = anfc("bgc_o2").o2_bottom * O2_MG
    o2p10 = float(fb["2025-05-01":"2025-09-30"].quantile(0.1))
    # nutrients: DIVAnd Black Sea latest trusted summer window
    dd = divand("din", "blacksea", 0.0).query("season == 'summer'")["din_L1"].dropna()
    pp = divand("po4", "blacksea", 0.0).query("season == 'summer'")["po4_L1"].dropna()
    din, po4 = dd.iloc[-1], pp.iloc[-1]
    er = {
        "nutrients: DIN summer": din / TARGETS["din"],
        "nutrients: PO4 summer": po4 / TARGETS["po4"],
        "direct: chl May-Sep (sat)": chl_s / TARGETS["chl_warm"],
        "indirect: bottom O2 P10 (model)": TARGETS["o2_bottom_p10"] / o2p10,
    }
    vals = {"nutrients: DIN summer": f"{din:.2f} umol/L (DIVAnd window {dd.index[-1].year}) / {TARGETS['din']}",
            "nutrients: PO4 summer": f"{po4:.2f} umol/L (DIVAnd window {pp.index[-1].year}) / {TARGETS['po4']}",
            "direct: chl May-Sep (sat)": f"{chl_s:.2f} mg m-3 (May-Sep 2025 mean, {chl.chl.notna().sum()} d) / {TARGETS['chl_warm']}",
            "indirect: bottom O2 P10 (model)": f"{TARGETS['o2_bottom_p10']} / {o2p10:.2f} mg/L (May-Sep 2025 P10, bgc_o2)"}
    for k, v in er.items():
        print(f"  {k:34s} {vals[k]:66s} ER {v:.2f} -> {heat_class(v)}")
    cats = collections.defaultdict(list)
    for k, v in er.items():
        cats[k.split(":")[0]].append(v)
    cat_er = {k: float(np.mean(v)) for k, v in cats.items()}
    worst = max(cat_er, key=cat_er.get)
    print("  category ER (mean within category): " + ", ".join(f"{k} {v:.2f}" for k, v in cat_er.items()))
    print(f"  EUTROPHICATION INDEX (one-out-all-out across categories) = {cat_er[worst]:.2f} -> "
          f"{heat_class(cat_er[worst]).upper()} (driven by '{worst}')")
    print("  Confidence: LOW-MEDIUM. Nutrients are a 6-year gridded climatology (window centred 2020), O2 is model-only")
    print("  at the bottom, chl is satellite (case-2 water; Danube CDOM/TSM can bias it). Thresholds are the official")
    print("  Romanian MSFD marine-water values, but the statistics differ (DIVAnd mean vs official P75).")
    print("  Official BEAST 2020-2022 (NIMRD): ~50 % of stations / ~59 % of the RO EEZ area in good status; shelf to 50-60 m")
    print("  and the southern coast (WWTPs, ports) not good.")

    # Replay: same algorithm fed with the OFFICIAL 2018-2023 statistics of the shelf unit MT01 (NIMRD 2024 study,
    # Tables III.7.8, III.7.10, III.7.13). Shows whether our index reproduces the official verdict.
    off = {
        "nutrients: DIN P75 13.78": 13.78 / TARGETS["din"],
        "nutrients: PO4 P75 0.27": 0.27 / TARGETS["po4"],
        "direct: chl P75 south 0.69": 0.69 / TARGETS["chl_warm"],
        "indirect: O2 P10 5.51 mg/L": TARGETS["o2_bottom_p10"] / 5.51,
        "indirect: O2 sat P10 57.3 %": D5C5_SAT / 57.3,
    }
    cats = collections.defaultdict(list)
    for k, v in off.items():
        cats[k.split(":")[0]].append(v)
    cat_er = {k: float(np.mean(v)) for k, v in cats.items()}
    worst = max(cat_er, key=cat_er.get)
    print("\n  Replay with OFFICIAL 2018-2023 shelf (MT01) statistics:")
    for k, v in off.items():
        print(f"    {k:34s} ER {v:.2f} -> {heat_class(v)}")
    print(f"    index = {cat_er[worst]:.2f} -> {heat_class(cat_er[worst]).upper()} (driven by '{worst}'); "
          f"official BEAST for the shelf: not good -> {'AGREES' if cat_er[worst] > 1 else 'DISAGREES'}")


# ------------------------------------------------------------------------------------------- C6
def c6():
    f = anfc("bgc_car")
    r = rea("rea_bgc_car")
    last = f.loc[:TODAY].dropna(subset=["ph"]).iloc[-1]
    clim = cm.climatology("bgc_car", LAT, LON, variable="ph")
    a = cm.anomalies(f[["ph"]].loc[TODAY - pd.Timedelta(days=30):TODAY], clim, "ph")
    print(f"Model surface pH (total scale) on {f.loc[:TODAY].dropna(subset=['ph']).index[-1].date()}: {last.ph:.3f}; "
          f"DIC {last.dic * 1000:.0f} umol/L, TA {last.alk * 1000:.0f} umol/L")
    print(f"Last 30 days: mean anomaly vs reanalysis 1993-2022 {a.anomaly.mean():+.3f} (z {a.zscore.mean():+.2f})")
    ra = r.loc[:"2023-12-31"].resample("YE").mean()
    yrs = ra.index.year.values
    for v in ("ph", "dic", "alk"):
        sl = np.polyfit(yrs, ra[v].values, 1)[0]
        print(f"  reanalysis 1993-2023 trend {v}: {sl * 10:+.4f} per decade (annual means)")
    m = r.loc[:"2023-12-31"].groupby(r.loc[:"2023-12-31"].index.month).ph.mean()
    print("  reanalysis monthly mean pH: " + " ".join(f"{k}:{v:.2f}" for k, v in m.items()))
    obs = bottles().ph.dropna()
    print(f"Observed pH samples within 30 km (EMODnet): n={len(obs)}, years {sorted(set(obs.index.year))}")


# ------------------------------------------------------------------------------------------- C7
def c7():
    bw = el.bathing_water_history("RO")
    print(f"  {bw.site_id.nunique()} RO sites, seasons {bw.year.min()}-{bw.year.max()} ({len(bw)} site-years); "
          f"per-year class from the layer's 'status' field")
    new = bw[bw.year >= 2015]
    tab = new.groupby(["year", "class"]).size().unstack(fill_value=0)
    tab["share_excellent"] = (tab.get("1 - Excellent", 0) / tab.sum(axis=1)).round(2)
    print("  Directive 2006/7/EC seasons:")
    print("  " + tab.to_string().replace("\n", "\n  "))
    print("  EEA country factsheet 2025 (official): 2022 45 Exc/4 Good, 2023 34/15, 2024 41/8 -> "
          + ("MATCH" if (tab.loc[2023, "1 - Excellent"], tab.loc[2023, "2 - Good"]) == (34, 15) else "MISMATCH"))
    piv = new.pivot_table(index="site_id", columns="year", values="class_code")
    y1 = piv.columns.max()
    worse = piv[piv[y1] > piv[y1 - 1]].index
    print(f"  sites downgraded {y1 - 1} -> {y1}: {len(worse)}; never Excellent since 2015: "
          f"{int((piv.min(axis=1) > 1).sum())}")
    nev = bw[bw.site_id.isin(piv[piv.min(axis=1) > 1].index)].drop_duplicates("site_id")
    for _, r in nev.iterrows():
        print(f"    never Excellent: {r['name']} ({r.lat:.3f}, {r.lon:.3f})")
    print("Contaminants (MSFD D8/D9) and bathing microbiology are lab-based: no live feed. Dashboard shows the")
    print("official BWD class per site and a 'needs sampling' marker for D8/D9 (see chemical.md section 6).")


# ------------------------------------------------------------------------------------------- R
def reliability():
    R = pd.concat([rea("rea_bgc_o2"), rea("rea_bgc_nut")], axis=1)
    F = pd.concat([anfc("bgc_o2"), anfc("bgc_nut")], axis=1)
    print("1) Analysis/forecast minus reanalysis, Constanta cell, overlap 2024-10-03..2024-12-31 (daily):")
    for v, sc, u in (("o2", O2_MG, "mg/L"), ("o2_bottom", O2_MG, "mg/L"), ("no3", 1, "mmol m-3"), ("po4", 1, "mmol m-3")):
        cmp(R[v].loc["2024-10-03":], F[v].loc[:"2024-12-31"], f"anfc vs rea {v}", u, sc)

    print("\n2) Reanalysis vs bottle samples (<= 30 km, same day; 1993-2021):")
    c = bottles()
    sd = c[(c.index >= "1993-01-01") & (c.depth <= 5)]
    g = sd.groupby(sd.index.normalize())[["o2", "no3", "po4"]].mean()
    cmp(g.o2, R.o2.reindex(g.index), "rea surface O2 vs bottles 0-5 m", "mg/L", O2_MG)
    cmp(g.no3, R.no3.reindex(g.index), "rea surface NO3 vs bottles 0-5 m", "mmol m-3")
    cmp(g.po4, R.po4.reindex(g.index), "rea surface PO4 vs bottles 0-5 m", "mmol m-3")
    b = bottom_bottles()
    b = b[b.index >= "1993-01-01"]
    gb = b.groupby(b.index.normalize()).o2.mean()
    cmp(gb, R.o2_bottom.reindex(gb.index), "rea o2_bottom vs deepest bottle (>= 15 m)", "mg/L", O2_MG)

    print("\n3) Model surface O2 vs buoys (daily means, model at the buoy position):")
    for pid, plat, plon, key, s, e in (("EUXRo03", 43.980, 29.936, "rea_bgc_o2", "2013-06-01", "2023-11-01"),
                                       ("EUXRoOB03", 43.977, 29.924, "bgc_o2", "2025-01-01", "2026-09-01"),
                                       ("EUXRoOB02", 44.325, 30.410, "bgc_o2", "2025-01-01", "2026-09-01"),
                                       ("EUXRoCB02", 44.226, 28.678, "bgc_o2", "2026-09-01", "2026-11-22")):
        o = ei.fetch_platform(pid, s, e, ["o2", "do_sat", "temp", "sal"], resample="1D")
        m = cm.fetch_timeseries(key, plat, plon, s, e, variables=["o2"])
        cmp(o.o2, m.o2.reindex(o.index), f"{key} vs {pid} ({s[:7]}..{e[:7]})", "mg/L", O2_MG)
        if pid == "EUXRoCB02":
            print(f"    {pid} notes: {o.attrs.get('notes')}; median OSAT {o.do_sat.median():.1f} (should be ~80-110 %),"
                  f" median sal {o.sal.median():.2f}")

    print("\n3a) Live: forecast surface O2 vs GeoEcoMar ERDDAP buoy EUXRoOB03 (DOXY in umol/L), this month:")
    try:
        import io

        import requests
        url = ("https://erddap.geoecomar.ro/erddap/tabledap/EUXRoOB03_2026.csv?time,DOXY,TEMP"
               f"&time%3E={(TODAY - pd.Timedelta(days=22)).date()}T00:00:00Z")
        o = pd.read_csv(io.StringIO(requests.get(url, timeout=60).text), skiprows=[1], parse_dates=["time"])
        o = o.set_index("time").tz_localize(None).resample("1D").mean()
        o = o[o.DOXY < 499]  # 500.0 = sensor range cap
        m = cm.fetch_timeseries("bgc_o2", 43.977, 29.924, (TODAY - pd.Timedelta(days=22)).date(), TODAY.date(),
                                variables=["o2"])
        cmp(o.DOXY, m.o2.reindex(o.index), "bgc_o2 vs OB03 (GeoEcoMar ERDDAP, live)", "mg/L", O2_MG)
    except Exception as e:  # noqa: BLE001
        print(f"  live GeoEcoMar check skipped: {type(e).__name__}: {e}")

    print("\n3b) Reanalysis at Constanta 2018-2023 vs OFFICIAL NIMRD 2018-2023 station statistics (NIMRD 2024 study):")
    x = R.loc["2018-01-01":"2023-12-31"]
    ws = x[x.index.month.isin([5, 6, 7, 8, 9])]
    print(f"  surface NO3  rea median {x.no3.median():6.2f}, P75 {x.no3.quantile(.75):6.2f} | official shelf MT01 median 1.72, "
          f"P75 3.62; coastal CT median 3.67, P90 22.27  [umol/L]")
    print(f"  surface PO4  rea median {x.po4.median():6.2f}, P75 {x.po4.quantile(.75):6.2f} | official shelf median 0.08, "
          f"P75 0.27; coastal median 0.17, P90 0.91  [umol/L]")
    b = ws.o2_bottom * O2_MG
    print(f"  bottom O2 May-Sep  rea mean {b.mean():.2f}, P10 {b.quantile(.1):.2f}, min {b.min():.2f} | official 20-50 m: "
          f"mean 8.02, P10 5.44, min 3.33; coastal P10 5.44; shelf P10 5.51  [mg/L]")
    print(f"  -> reanalysis NO3 is ~{x.no3.median() / 1.72:.0f}x the observed shelf median; PO4 and bottom O2 are of the right order")

    print("\n4) Seasonal cycle of surface NO3 at Constanta, three sources (mmol m-3):")
    obs = sd[sd.index.year.isin(range(1980, 2000))]
    t = pd.DataFrame({
        "bottles 1980-99 (median)": obs.groupby(obs.index.month).no3.median(),
        "reanalysis 1993-2023": R.no3.loc[:"2023"].groupby(R.loc[:"2023"].index.month).mean(),
        "anfc 2024-26": F.no3.groupby(F.index.month).mean(),
    })
    print(t.round(2).T.to_string())
    ya = R.no3.resample("YE").mean()
    print("  reanalysis annual-mean NO3 2019-2024: " + ", ".join(f"{i.year}: {v:.2f}" for i, v in ya.loc["2019":].items()))


# ------------------------------------------------------------------------------------------- D
def danube():
    q = od.danube_discharge("1997-01-01", "2026-12-20")
    obs = q[~q.is_forecast.astype(bool)] if "is_forecast" in q else q
    clim = obs.discharge.loc[:"2024"].groupby(obs.loc[:"2024"].index.month).mean()
    last30 = obs.discharge.loc[TODAY - pd.Timedelta(days=30):TODAY]
    m = TODAY.month
    print(f"Danube discharge, last 30 days mean {last30.mean():.0f} m3/s vs {m}-month 1997-2024 mean {clim[m]:.0f} "
          f"(ratio {last30.mean() / clim[m]:.2f})")
    R = rea("rea_bgc_o2")
    qs = obs.discharge[obs.index.month.isin([3, 4, 5, 6])]
    qs = qs.groupby(qs.index.year).mean()
    rb = (R.o2_bottom * O2_MG)[R.index.month.isin([7, 8, 9, 10])]
    rb = rb.groupby(rb.index.year).min()
    j = pd.concat([qs.rename("q"), rb.rename("o2")], axis=1).dropna().loc[:2023]
    print(f"r(spring Mar-Jun Danube discharge, Jul-Oct min bottom O2 in reanalysis) = {j.q.corr(j.o2):.2f} (n={len(j)} years)")
    print("  -> high-discharge springs precede lower late-summer bottom O2: discharge is a covariate the anomaly")
    print("     detector must account for before calling a low-O2 event 'degradation'.")


if __name__ == "__main__":
    print(f"Chemical indicator check, Constanta {LAT} N {LON} E, reference date {TODAY.date()}")
    print(f"Copernicus login: {cm.is_logged_in()}")
    run("C1  Bottom-oxygen status class (bgc_o2 o2_bottom; rea_bgc_o2; EMODnet bottles)", c1)
    run("C2  Surface O2 saturation (EUXRoOB03 OSAT; bgc_o2 + phy_temp + phy_sal)", c2)
    run("C3/C4  Nutrients DIN, PO4, Si and ratios N:P, Si:N (EMODnet Chemistry samples + DIVAnd)", c3_c4)
    run("C5  Eutrophication index, simplified BEAST/HEAT (sat_chl_l4_my + bgc_o2 + DIVAnd)", c5)
    run("C6  pH / carbonate watch (bgc_car vs rea_bgc_car)", c6)
    run("C7  Bathing-water class (emodnet_layers bathing_waters)", c7)
    run("R   Model vs observation reliability, O2 and nutrients", reliability)
    run("D   Danube discharge as natural-variability covariate", danube)
