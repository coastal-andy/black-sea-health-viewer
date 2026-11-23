"""Physical indicators for the Romanian shelf: live computability check at Constanta (44.17 N, 28.72 E).

Run from the repo root:
    .venv/bin/python scripts/indicators/physical_check.py | tee scripts/indicators/physical_check_output.txt

Every fetch goes through the verified modules in src/marinekit/sources/ and is cached by them
(data/cache/...), so a second run works offline. Each section is independent: a failure prints
"NOT COMPUTED" with the reason and the script continues.

Indicators (see docs/indicators/physical.md for the science and thresholds):
  P1  SST anomaly, marine heatwaves and cold spells (Hobday et al. 2016)   sst_l4_rep + sst_l4_nrt
  P2  Bottom temperature anomaly (benthic thermal stress)                   phy_temp/bottomT vs rea_phy_temp
  P3  Stratification: delta sigma-theta bottom - surface, and MLD          phy_temp, phy_sal, phy_mld (+ rea_*)
  P4  Upwelling index: coastal minus offshore SST + Ekman wind index        sst_l4_rep/nrt + Open-Meteo ERA5 wind
  P5  Danube freshwater influence: discharge anomaly + surface salinity     danube_discharge, phy_sal, rea_phy_sal
  P6  Transparency and light at the seabed: Kd490 -> Kd(PAR), Secchi, %E    sat_kd490_my
  P7  Storm and resuspension: Hs, bottom orbital velocity, sea-level surge  wav, Open-Meteo marine, IOC-csta2
  (context) surface currents                                                phy_cur
"""
from __future__ import annotations

import sys
import time
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from marinekit.sources import copernicus as cm  # noqa: E402
from marinekit.sources import emodnet_insitu as ei  # noqa: E402
from marinekit.sources import open_data as od  # noqa: E402

LAT, LON = 44.17, 28.72            # Constanta test point
OFF_LAT, OFF_LON = 44.17, 29.30    # offshore reference for the upwelling index (~47 km east, ~50 m depth)
COAST_BEARING = 10.0               # deg true, direction the coastline runs (SSW -> NNE) near Constanta
TODAY = pd.Timestamp("2026-11-23")
RECENT0 = TODAY - pd.Timedelta(days=90)
G = 9.81
SECCHI_C = 1.1                     # Secchi ~= SECCHI_C / Kd_PAR, tuned to INCDM coastal Secchi 2018-2023 (see P6); 1.7 = open-water rule
pd.set_option("display.width", 160)


# ------------------------------------------------------------------------------------------- helpers
def section(title: str):
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


def run(title: str, fn):
    section(title)
    t = time.time()
    try:
        fn()
        print(f"STATUS: COMPUTED LIVE ({time.time() - t:.0f} s)")
    except Exception as e:  # noqa: BLE001
        print(f"STATUS: NOT COMPUTED: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2, file=sys.stdout)


def where(df: pd.DataFrame) -> str:
    a = df.attrs
    bits = [a.get("dataset", "")]
    if a.get("grid_lat") is not None:
        bits.append(f"cell {a['grid_lat']:.3f}N {a['grid_lon']:.3f}E ({a.get('distance_km')} km)")
    if a.get("depth_m") is not None:
        bits.append(f"depth {a['depth_m']:.2f} m")
    if a.get("pixel_lat") is not None:
        bits.append(f"pixel {a['pixel_lat']:.3f}N {a['pixel_lon']:.3f}E ({a.get('pixel_dist_km')} km)")
    return " | ".join(b for b in bits if b)


def doy365(idx: pd.DatetimeIndex) -> np.ndarray:
    return cm._doy365(pd.DatetimeIndex(idx))


def doy_clim(s: pd.Series, years: tuple[int, int], window: int = 11, smooth: int = 31, log: bool = False) -> pd.DataFrame:
    """Day-of-year climatology of a derived daily series, same recipe as marinekit climatology()
    (pool +-window/2 days over the reference years, then circular running mean of `smooth` days).
    log=True: statistics of log10(s) (for Kd490 and other log-normal variables)."""
    s = s.dropna()
    s = s[(s.index.year >= years[0]) & (s.index.year <= years[1])]
    v = np.log10(s.values) if log else s.values
    dd, half, rows = doy365(s.index), window // 2, []
    for d in range(1, 366):
        dist = np.abs(dd - d)
        x = v[np.minimum(dist, 365 - dist) <= half]
        stats = [np.nanmean(x), np.nanstd(x, ddof=1), *np.nanpercentile(x, [10, 50, 90])] if len(x) > 1 else [np.nan] * 5
        rows.append((d, *stats, len(x)))
    out = pd.DataFrame(rows, columns=["doy", "mean", "std", "p10", "p50", "p90", "n"]).set_index("doy")
    k = smooth // 2
    for c in ["mean", "std", "p10", "p50", "p90"]:
        x = out[c].to_numpy()
        out[c] = pd.Series(np.concatenate([x[-k:], x, x[:k]])).rolling(smooth, center=True, min_periods=1).mean().to_numpy()[k:-k]
    return out


def join_clim(s: pd.Series, clim: pd.DataFrame) -> pd.DataFrame:
    c = clim.reindex(doy365(s.index))
    c.index = s.index
    return pd.DataFrame({"value": s, "clim": c["mean"], "std": c["std"], "p10": c["p10"], "p90": c["p90"]})


def ols_trend(y: pd.Series) -> tuple[float, float, float]:
    """Slope per decade, its 95 % CI half-width (lag-1 autocorrelation-corrected effective n), and lag-1 r."""
    y = y.dropna()
    x = y.index.values.astype(float)
    b, a = np.polyfit(x, y.values, 1)
    res = y.values - (a + b * x)
    r1 = np.corrcoef(res[:-1], res[1:])[0, 1] if len(res) > 3 else 0.0
    n_eff = len(y) * (1 - r1) / (1 + r1) if r1 > 0 else len(y)
    se = np.sqrt(np.sum(res ** 2) / max(n_eff - 2, 1) / np.sum((x - x.mean()) ** 2))
    return 10 * b, 10 * 1.96 * se, r1


def hobday_events(t: pd.Series, thresh: pd.Series, clim: pd.Series, above: bool = True,
                  min_len: int = 5, max_gap: int = 2) -> pd.DataFrame:
    """Marine heatwaves (above=True) or cold spells (above=False) after Hobday et al. (2016):
    >= 5 consecutive days beyond the day-of-year p90 (p10) threshold, events separated by <= 2 days merged.
    Category after Hobday et al. (2018): peak (T - clim) / (thresh - clim): 1-2 moderate, 2-3 strong,
    3-4 severe, >= 4 extreme."""
    t = t.asfreq("D")
    exc = (t > thresh) if above else (t < thresh)
    exc = exc.fillna(False).to_numpy()
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
    rows = []
    for i, j in merged:
        seg = slice(i, j + 1)
        anom = (t.iloc[seg] - clim.iloc[seg]).to_numpy()
        diff = (thresh.iloc[seg] - clim.iloc[seg]).to_numpy()
        k = np.nanargmax(anom) if above else np.nanargmin(anom)
        ratio = abs(anom[k] / diff[k]) if diff[k] else np.nan
        cat = ["moderate", "strong", "severe", "extreme"][int(min(max(np.floor(ratio), 1), 4)) - 1]
        rows.append(dict(start=t.index[i].date(), end=t.index[j].date(), days=j - i + 1,
                         peak_anom=round(float(anom[k]), 2), mean_anom=round(float(np.nanmean(anom)), 2),
                         category=cat))
    return pd.DataFrame(rows)


def sigma0(T, S):
    """Potential density anomaly sigma-theta (kg/m3) with UNESCO EOS-80 at p = 0 (adequate on a 0-50 m shelf)."""
    T, S = np.asarray(T, float), np.asarray(S, float)
    rw = (999.842594 + 6.793952e-2 * T - 9.095290e-3 * T ** 2 + 1.001685e-4 * T ** 3
          - 1.120083e-6 * T ** 4 + 6.536332e-9 * T ** 5)
    A = 8.24493e-1 - 4.0899e-3 * T + 7.6438e-5 * T ** 2 - 8.2467e-7 * T ** 3 + 5.3875e-9 * T ** 4
    B = -5.72466e-3 + 1.0227e-4 * T - 1.6546e-6 * T ** 2
    return rw + A * S + B * S ** 1.5 + 4.8314e-4 * S ** 2 - 1000.0


def wavenumber(T, h):
    """Linear-wave dispersion, Fenton & McKee (1990) explicit approximation; T (s), h (m)."""
    w = 2 * np.pi / np.asarray(T, float)
    k0 = w ** 2 / G
    return k0 / np.tanh((k0 * h) ** 0.75) ** (2 / 3)


def orbital_velocity(Hs, T, h):
    """Near-bed orbital velocity amplitude (m/s), linear theory: u_b = pi H / (T sinh(k h))."""
    k = wavenumber(T, h)
    return np.pi * np.asarray(Hs, float) / (np.asarray(T, float) * np.sinh(k * h))


def kdpar_from_kd490(kd490):
    """Morel et al. (2007) eq. 9: Kd(PAR) of the first optical depth from Kd(490)."""
    kd490 = np.asarray(kd490, float)
    return 0.0864 + 0.884 * kd490 - 0.00137 / kd490


# ------------------------------------------------------------------------------------------- P1
def p1_sst_mhw():
    rep = cm.fetch_timeseries("sst_l4_rep", LAT, LON, "1982-01-01", "2026-12-31")["sst"].dropna()
    nrt = cm.fetch_timeseries("sst_l4_nrt", LAT, LON, "2026-09-01", TODAY)
    print("REP :", where(cm.fetch_timeseries("sst_l4_rep", LAT, LON, "1982-01-01", "2026-12-31")), f"{rep.index[0].date()}..{rep.index[-1].date()}")
    print("NRT :", where(nrt), f"..{nrt.index[-1].date()}")
    nrt = nrt["sst"].dropna()
    ov = (nrt - rep).dropna()
    print(f"NRT - REP over the overlap ({len(ov)} days): bias {ov.mean():+.2f} C, sd {ov.std():.2f} C -> NRT appended after REP ends, bias removed")
    sst = pd.concat([rep, nrt[nrt.index > rep.index[-1]] - ov.mean()]).asfreq("D").interpolate(limit=2)

    clim = cm.climatology("sst_l4_rep", LAT, LON, "sst")  # 1991-2020, 11-day window, 31-day smoothing
    print(f"Climatology {clim.attrs.get('years')} ({clim.attrs.get('n_years')} years) at {clim.attrs.get('grid_lat')}N {clim.attrs.get('grid_lon')}E")
    for m, d in [(2, 15), (5, 15), (8, 15), (11, 23)]:
        r = clim.loc[pd.Timestamp(2001, m, d).dayofyear]
        print(f"  clim {m:02d}-{d:02d}: mean {r['mean']:.2f}  p10 {r['p10']:.2f}  p90 {r['p90']:.2f}  sd {r['std']:.2f}")
    c = clim.reindex(doy365(sst.index))
    c.index = sst.index
    anom = sst - c["mean"]
    z = anom / c["std"]
    print("\nLast 7 days (SST, anomaly, z, threshold p90):")
    tail = pd.DataFrame({"sst": sst, "anom": anom, "z": z, "p90": c["p90"]}).tail(7).round(2)
    print(tail.to_string())

    mhw = hobday_events(sst, c["p90"], c["mean"], above=True)
    mcs = hobday_events(sst, c["p10"], c["mean"], above=False)
    recent = mhw[pd.to_datetime(mhw.start) >= RECENT0 - pd.Timedelta(days=60)]
    print(f"\nMarine heatwaves 1982-{sst.index[-1].year}: {len(mhw)} events; cold spells: {len(mcs)} events")
    print("Heatwaves since late June:\n" + (recent.tail(5).to_string(index=False) if len(recent) else "  none in the last 150 days"))
    print("Last 4 heatwaves on record:\n" + mhw.tail(4).to_string(index=False))
    ongoing = bool(len(mhw)) and pd.Timestamp(mhw.iloc[-1]["end"]) >= sst.index[-1] - pd.Timedelta(days=1)
    print(f"Heatwave ongoing on {sst.index[-1].date()}: {ongoing}")
    print("Most recent cold spells:\n" + mcs.tail(3).to_string(index=False))

    days = pd.Series(0, index=range(1982, 2026), dtype=float)
    for _, e in mhw.iterrows():
        for d in pd.date_range(e.start, e.end):
            if d.year in days.index:
                days[d.year] += 1
    annual = sst[sst.index.year <= 2025].groupby(sst.index.year[sst.index.year <= 2025]).mean()
    tr, ci, r1 = ols_trend(annual)
    trd, cid, _ = ols_trend(days)
    print(f"\nAnnual-mean SST trend 1982-2025: {tr:+.2f} +- {ci:.2f} C per decade (95 % CI, lag-1 r {r1:.2f})")
    print(f"MHW days per year: 1982-1991 mean {days.loc[1982:1991].mean():.0f}, 2016-2025 mean {days.loc[2016:2025].mean():.0f}; "
          f"trend {trd:+.1f} +- {cid:.1f} days per decade")
    print("Note: a fixed 1991-2020 baseline mixes long-term warming into the heatwave count (Hobday 2016 'fixed baseline').")


# ------------------------------------------------------------------------------------------- P2
def p2_bottom_temp():
    now = cm.fetch_timeseries("phy_temp", LAT, LON, RECENT0, TODAY + pd.Timedelta(days=5), variables=["bottomT"])
    print("Model:", where(now))
    clim = cm.climatology("phy_temp", LAT, LON, "bottom_temp")
    print(f"Climatology: rea_phy_temp bottomT {clim.attrs.get('years')}")
    j = join_clim(now["bottom_temp"], clim)
    j["anom"] = j.value - j.clim
    j["z"] = j.anom / j["std"]
    print(j.iloc[::10].round(2).to_string())
    # model-system consistency check over the overlap of the two systems
    a = cm.fetch_timeseries("phy_temp", LAT, LON, "2024-12-01", "2025-07-31", variables=["bottomT"])["bottom_temp"]
    r = cm.fetch_timeseries("rea_phy_temp", LAT, LON, "2024-12-01", "2025-07-31", variables=["bottomT"])["bottom_temp"]
    d = (a - r).dropna()
    print(f"\nanfc - reanalysis bottomT, Dec 2024-Jul 2025 ({len(d)} days): bias {d.mean():+.2f} C, RMSD {np.sqrt((d ** 2).mean()):.2f} C, r {a.corr(r):.2f}")
    print("Bottom-water heatwave (Hobday recipe on bottomT) in the window:")
    ev = hobday_events(now["bottom_temp"].loc[:TODAY], j["p90"].loc[:TODAY], j["clim"].loc[:TODAY])
    print(ev.to_string(index=False) if len(ev) else "  none")


# ------------------------------------------------------------------------------------------- P3
def _strat_series(tkey, skey, start, end, zb):
    tt = cm.fetch_timeseries(tkey, LAT, LON, start, end, variables=["thetao"])
    tb = cm.fetch_timeseries(tkey, LAT, LON, start, end, variables=["bottomT"])
    ss = cm.fetch_timeseries(skey, LAT, LON, start, end, variables=["so"])
    sb = cm.fetch_timeseries(skey, LAT, LON, start, end, variables=["so"], depth=zb)
    df = pd.DataFrame({"t_s": tt["temp"], "t_b": tb["bottom_temp"], "s_s": ss["sal"], "s_b": sb["sal"]})
    df["dsig"] = sigma0(df.t_b, df.s_b) - sigma0(df.t_s, df.s_s)
    # split into thermal and haline parts (linearised around the mean state)
    df["dsig_T"] = sigma0(df.t_b, df.s_s) - sigma0(df.t_s, df.s_s)
    df["dsig_S"] = df.dsig - df.dsig_T
    return df, sb.attrs


def p3_stratification():
    zb = 26.0  # deepest model level at the Constanta cell is 26.49 m (checked); bottomT is that level
    now, a = _strat_series("phy_temp", "phy_sal", RECENT0, TODAY + pd.Timedelta(days=5), zb)
    print(f"Bottom salinity level: {a.get('depth_m')} m at {a.get('grid_lat')}N {a.get('grid_lon')}E")
    ref, _ = _strat_series("rea_phy_temp", "rea_phy_sal", "1993-01-01", "2022-12-31T23:59:59", zb)
    clim = doy_clim(ref["dsig"], (1993, 2022))
    j = join_clim(now["dsig"], clim)
    out = pd.concat([now[["t_s", "t_b", "s_s", "s_b", "dsig_T", "dsig_S"]], j[["value", "clim", "p10", "p90"]]], axis=1)
    out = out.rename(columns={"value": "dsig"})
    print("Delta sigma-theta (bottom - surface, kg/m3) every 10 days:")
    print(out.iloc[::10].round(2).to_string())
    m = ref["dsig"].groupby(ref.index.month)
    print("\nReanalysis 1993-2022 monthly delta sigma (median / p90):",
          "  ".join(f"{k}:{v:.1f}/{m.quantile(0.9)[k]:.1f}" for k, v in m.median().items()))
    print("Share of the haline part in summer stratification (Jun-Aug, reanalysis):",
          f"{(ref.dsig_S[ref.index.month.isin([6, 7, 8])] / ref.dsig[ref.index.month.isin([6, 7, 8])]).median():.0%}")
    mld = cm.fetch_timeseries("phy_mld", LAT, LON, RECENT0, TODAY + pd.Timedelta(days=5))
    cmld = cm.climatology("phy_mld", LAT, LON, "mld")
    jm = join_clim(mld["mld"], cmld)
    print("\nMixed-layer depth (model, m) vs 1993-2022 climatology, every 15 days:")
    print(jm.iloc[::15].round(1).to_string())
    print("Note: water depth at the cell is ~26.5 m, so MLD near 26 m means the column is fully mixed.")


# ------------------------------------------------------------------------------------------- P4
def p4_upwelling():
    co = cm.fetch_timeseries("sst_l4_rep", LAT, LON, "1982-01-01", "2026-12-31")
    of = cm.fetch_timeseries("sst_l4_rep", OFF_LAT, OFF_LON, "1982-01-01", "2026-12-31")
    print("coast  :", where(co))
    print("offshore:", where(of))
    d = (co["sst"] - of["sst"]).dropna()
    clim = cm.climatology("sst_l4_rep", LAT, LON, "sst")
    c = clim.reindex(doy365(co.index))
    c.index = co.index
    summer = d.index.month.isin([6, 7, 8, 9])
    up = (d <= -2.0) & summer
    up_p10 = up & (co["sst"].reindex(d.index) < c["p10"].reindex(d.index))
    yr = up.groupby(up.index.year).sum()
    print(f"\nUpwelling days (Jun-Sep, coast - offshore SST <= -2 C): mean {yr.loc[1991:2020].mean():.1f} per summer 1991-2020; "
          f"max {int(yr.max())} in {yr.idxmax()}; with coastal SST also below p10: {up_p10.groupby(up_p10.index.year).sum().loc[1991:2020].mean():.1f}")
    print("Per summer 2016-2026:", ", ".join(f"{y}:{int(v)}" for y, v in yr.loc[2016:].items()))
    print(f"Typical summer coast - offshore difference (median Jun-Sep 1991-2020): {d[summer & (d.index.year <= 2020)].median():+.2f} C; "
          f"min {d[summer].min():+.1f} C on {d[summer].idxmin().date()}")
    tr, ci, _ = ols_trend(yr.loc[1982:2025].astype(float))
    print(f"Trend in upwelling days 1982-2025: {tr:+.1f} +- {ci:.1f} days per decade")

    # wind-based Ekman index from ERA5 (Open-Meteo archive), summers 2015-2025
    rho_a, cd, rho_w = 1.22, 1.3e-3, 1012.0
    f = 2 * 7.2921e-5 * np.sin(np.deg2rad(LAT))
    th = np.deg2rad(COAST_BEARING)
    rows = []
    for y in range(2015, 2026):
        w = od.marine_weather(LAT, LON, f"{y}-06-01", f"{y}-09-30", freq="hourly")[["wind_u", "wind_v"]].dropna()
        spd = np.hypot(w.wind_u, w.wind_v)
        along = w.wind_u * np.sin(th) + w.wind_v * np.cos(th)      # + = blowing towards NNE (southerly wind)
        tau = rho_a * cd * spd * along                               # N/m2, alongshore stress
        ui = (tau / (rho_w * f) * 100.0).resample("D").mean()        # m3/s per 100 m of coast, + = offshore Ekman transport
        rows.append(ui)
    ui = pd.concat(rows)
    ui3 = ui.rolling(3, min_periods=2).mean().shift(1)             # mean of the 3 days before
    both = pd.DataFrame({"dT": d, "ui": ui, "ui3": ui3}).dropna()
    ev = both[both.dT <= -2.0]
    print(f"\nEkman upwelling index (alongshore wind, coastline {COAST_BEARING:.0f} deg; + = offshore transport), summers 2015-2025:")
    print(f"  median {ui.median():+.2f} m3/s per 100 m; p90 {ui.quantile(0.9):+.2f}")
    print(f"  SST-detected upwelling days 2015-2025: {len(ev)}; of these preceded by favourable wind (3-day mean UI > 0): {(ev.ui3 > 0).mean():.0%}")
    print(f"  correlation daily dT vs 3-day lagged UI: r = {both.dT.corr(both.ui3):+.2f} (negative r = wind-driven cooling)")
    # current state from NRT
    cn = cm.fetch_timeseries("sst_l4_nrt", LAT, LON, RECENT0, TODAY)["sst"]
    on = cm.fetch_timeseries("sst_l4_nrt", OFF_LAT, OFF_LON, RECENT0, TODAY)["sst"]
    dn = (cn - on).dropna()
    print(f"\nLast 5 days coast - offshore SST (NRT): " + ", ".join(f"{i.date()}: {v:+.2f}" for i, v in dn.tail(5).items()))
    print("Outside Jun-Sep the coastal strip is naturally colder than offshore (shallow cooling), so the flag is summer-only.")


# ------------------------------------------------------------------------------------------- P5
def p5_danube_salinity():
    q = od.danube_discharge("1997-01-01", TODAY + pd.Timedelta(days=20))
    qs = q["discharge"]
    print("GloFAS:", q.attrs.get("grid_cell"), f"{qs.index[0].date()}..{qs.index[-1].date()} (forecast after {TODAY.date()})")
    qc = doy_clim(qs, (1997, 2025))
    jq = join_clim(qs, qc)
    jq["ratio"] = jq.value / jq.clim
    print(f"Long-term mean 1997-2025: {qs.loc['1997':'2025'].mean():.0f} m3/s")
    print("Recent and forecast (every 7 days):")
    print(jq.loc[TODAY - pd.Timedelta(days=42):].iloc[::7].round(2).to_string())
    ann = qs.loc["1997":"2025"].groupby(qs.loc["1997":"2025"].index.year).mean()
    print(f"Annual means: min {ann.min():.0f} ({ann.idxmin()}), max {ann.max():.0f} ({ann.idxmax()}); 2026 to date {qs.loc['2026':str(TODAY.date())].mean():.0f}")

    s = cm.fetch_timeseries("phy_sal", LAT, LON, RECENT0, TODAY + pd.Timedelta(days=5))
    sc = cm.climatology("phy_sal", LAT, LON, "sal")
    js = join_clim(s["sal"], sc)
    js["anom"] = js.value - js.clim
    print("\nSurface salinity (model) vs 1993-2022 reanalysis climatology, every 15 days:")
    print(js.iloc[::15].round(2).to_string())
    print("Known offset: anfc - reanalysis surface salinity about -0.44 (Dec 2024-Jul 2025, docs/data_sources/copernicus.md)")

    rs = cm.fetch_timeseries("rea_phy_sal", LAT, LON, "1993-01-01", "2022-12-31T23:59:59", variables=["so"])["sal"]
    mq = qs.loc["1997":"2022"].resample("MS").mean()
    ms = rs.loc["1997":"2022"].resample("MS").mean()
    aq = mq - mq.groupby(mq.index.month).transform("mean")
    as_ = ms - ms.groupby(ms.index.month).transform("mean")
    print("\nMonthly anomaly correlation, Danube discharge (leading) vs surface salinity at Constanta (reanalysis), 1997-2022:")
    print("  " + "  ".join(f"lag {k} mo: r={aq.shift(k).corr(as_):+.2f}" for k in range(0, 4)))


# ------------------------------------------------------------------------------------------- P6
def p6_transparency():
    ref = cm.fetch_timeseries("sat_kd490_my", LAT, LON, "1998-01-01", "2022-12-31T23:59:59", variables=["KD490"])
    print("Reference:", where(ref), f"n valid days {int(ref['kd490'].notna().sum())}")
    kc = doy_clim(ref["kd490"], (1998, 2022), window=31, log=True)
    for m in [1, 4, 7, 10]:
        r = kc.loc[pd.Timestamp(2001, m, 15).dayofyear]
        print(f"  clim mid-{m:02d}: geometric mean Kd490 {10 ** r['mean']:.3f} 1/m  (p10 {10 ** r['p10']:.3f}, p90 {10 ** r['p90']:.3f})")
    now = cm.fetch_timeseries("sat_kd490_my", LAT, LON, RECENT0, TODAY)
    print("Recent:", where(now))
    k = now["kd490"].dropna()
    j = join_clim(np.log10(k), kc)
    out = pd.DataFrame({"kd490": k, "ratio_to_clim": 10 ** (j.value - j.clim), "z_log": (j.value - j.clim) / j["std"]})
    kp = kdpar_from_kd490(k)
    out["kd_par"] = kp
    out["z_eu_1pct_m"] = 4.605 / kp
    out["secchi_m_c1.1"] = SECCHI_C / kp
    out["secchi_m_c1.7"] = 1.7 / kp
    out["light_at_10m_pct"] = 100 * np.exp(-kp * 10)
    out["light_at_20m_pct"] = 100 * np.exp(-kp * 20)
    print(f"{len(out)} valid days in the last 90; last 8:")
    print(out.tail(8).round(3).to_string())
    # rough calibration of the Secchi factor against the INCDM 2024 MSFD study (coastal stations 2018-2023:
    # Secchi median 4.0 m, mean 4.6 m, n = 49; Studiu_raport_MSFD-2024.pdf p. 149)
    ws = ref["kd490"].loc["2018":"2022"].dropna()
    ws = ws[ws.index.month.isin([5, 6, 7, 8, 9])]
    kpw = kdpar_from_kd490(ws)
    print(f"Warm-season (May-Sep) 2018-2022 satellite at Constanta: median Kd_PAR {np.median(kpw):.3f} 1/m -> Secchi(1.7/Kd_PAR) "
          f"median {np.median(1.7 / kpw):.1f} m, p10 {np.percentile(1.7 / kpw, 10):.1f} m (n {len(ws)})")
    print(f"  factor that reproduces the INCDM coastal median Secchi of 4.0 m: c = {4.0 * np.median(kpw):.2f} (vs 1.7 assumed)")
    # habitat light depths: depth where the climatological light falls to the requirement of each plant group
    # 11 % seagrass (Duarte 1991), 0.5 % leathery brown algae e.g. Gongolaria/Cystoseira, 0.1 % foliose red algae
    # e.g. Phyllophora (Markager & Sand-Jensen 1992). Targets: RO-BG MSFD 2024 Annex 3 (to be validated):
    # Gongolaria barbata max depth >= 10 m, Phyllophora / shade algae >= 17 m.
    print("\nHabitat light depths from the 1998-2022 Kd490 climatology (Kd_PAR via Morel 2007), annual median [May-Sep median]:")
    for name, (la, lo) in {"Constanta": (LAT, LON), "Vama Veche": (43.75, 28.60)}.items():
        r = cm.fetch_timeseries("sat_kd490_my", la, lo, "1998-01-01", "2022-12-31T23:59:59", variables=["KD490"])
        cl = doy_clim(r["kd490"], (1998, 2022), window=31, log=True)
        kp = pd.Series(kdpar_from_kd490(10 ** cl["mean"]), index=cl.index)
        warm = kp.loc[pd.Timestamp(2001, 5, 1).dayofyear:pd.Timestamp(2001, 9, 30).dayofyear]
        parts = [f"{lab} {np.log(100 / pct) / kp.median():.1f} [{np.log(100 / pct) / warm.median():.1f}] m"
                 for lab, pct in (("seagrass 11 %:", 11), ("leathery algae 0.5 %:", 0.5), ("red algae 0.1 %:", 0.1))]
        print(f"  {name:10s} ({where(r)}): " + "; ".join(parts))
    for z in (5, 10, 15, 20):
        kpc = kdpar_from_kd490(10 ** kc["mean"])
        frac = 100 * np.exp(-kpc * z)
        print(f"  climatological light at {z:2d} m: {frac.min():.1f}-{frac.max():.1f} % of surface PAR over the year "
              f"(days above 11 %: {(frac > 11).sum()})")


# ------------------------------------------------------------------------------------------- P7
def p7_storms():
    w = cm.fetch_timeseries("wav", LAT, LON, RECENT0, TODAY + pd.Timedelta(days=5))
    print("CMEMS waves:", where(w))
    h = w[["wave_height", "wave_period"]].dropna()
    om = od.marine_weather(LAT, LON, "2021-10-01", TODAY, freq="hourly")[["wave_height", "wave_period", "wind_speed"]]
    print("Open-Meteo marine cell:", om.attrs.get("marine_cell"), f"waves from {om.wave_height.first_valid_index()}")
    hs = om["wave_height"].dropna()
    p95, p99 = hs.quantile(0.95), hs.quantile(0.99)
    print(f"Hs 2021-10..now (Open-Meteo, hourly): median {hs.median():.2f} m, p95 {p95:.2f} m, p99 {p99:.2f} m, max {hs.max():.2f} m on {hs.idxmax().date()}")
    # storm events: Hs above p95 for >= 6 consecutive hours (proposed), merged if < 12 h apart
    exc = (hs > p95).astype(int)
    grp = (exc.diff() != 0).cumsum()
    ev = hs[exc == 1].groupby(grp[exc == 1]).agg(["size", "max"])
    ev = ev[ev["size"] >= 6]
    print(f"Storm events (Hs > p95 for >= 6 h): {len(ev)} in {len(hs) / 8766:.1f} years; mean peak Hs {ev['max'].mean():.2f} m")
    hh = h.loc[:TODAY + pd.Timedelta(days=5)]
    for depth in (10, 20, 26.5):
        ub = pd.Series(orbital_velocity(hh.wave_height, hh.wave_period, depth), index=hh.index)
        print(f"  near-bed orbital velocity at {depth:4.1f} m (last 90 d + forecast): median {ub.median():.3f}, max {ub.max():.3f} m/s on {ub.idxmax().date()}; "
              f"hours > 0.10 m/s: {(ub > 0.10).sum()}, > 0.20 m/s: {(ub > 0.20).sum()}")
    print("Daily max Hs (CMEMS model), last 7 days + forecast:")
    print(hh.wave_height.resample("D").max().loc[TODAY - pd.Timedelta(days=6):].round(2).to_string())

    sl = ei.fetch_platform("IOC-csta2", TODAY - pd.Timedelta(days=30), TODAY, ["ssh"], resample="1h")
    x = sl["ssh"].dropna()
    resid = x - x.rolling("30D", min_periods=24).median()
    print(f"\nTide gauge IOC-csta2 (Constanta), last 30 days, {len(x)} hourly values, local datum (absolute level not meaningful):")
    print(f"  range {x.max() - x.min():.2f} m; residual vs running 30-day median: max {resid.max():+.2f} m on {resid.idxmax()}, min {resid.min():+.2f} m")
    ssh = cm.fetch_timeseries("phy_ssh", LAT, LON, TODAY - pd.Timedelta(days=30), TODAY + pd.Timedelta(days=5))
    print(f"  model SSH (phy_ssh) same period: range {ssh['ssh'].max() - ssh['ssh'].min():.2f} m; daily obs vs model r = "
          f"{x.resample('D').mean().corr(ssh['ssh']):.2f}")


# ------------------------------------------------------------------------------------------- context
def p8_currents():
    c = cm.fetch_timeseries("phy_cur", LAT, LON, TODAY - pd.Timedelta(days=30), TODAY + pd.Timedelta(days=5))
    print("Model:", where(c))
    th = np.deg2rad(COAST_BEARING)
    along = c.current_u * np.sin(th) + c.current_v * np.cos(th)
    spd = np.hypot(c.current_u, c.current_v)
    print(f"Surface current, last 30 days: mean speed {spd.mean():.2f} m/s, max {spd.max():.2f}; mean alongshore {along.mean():+.2f} m/s "
          f"(negative = towards SSW); share of days flowing south: {(along < 0).mean():.0%}")


def p9_turbidity():
    spm = od.fetch_timeseries("spm_dineof", LAT, LON, TODAY - pd.Timedelta(days=60), TODAY)
    print("SPM (NOAA DINEOF gap-filled):", where(spm))
    s = spm.iloc[:, 0].dropna()
    print(f"  last 60 d: median {s.median():.2f} g/m3, max {s.max():.2f} on {s.idxmax().date()}, last {s.index[-1].date()} {s.iloc[-1]:.2f}")
    hr = cm.fetch_timeseries("sat_hr_l3", LAT, LON, TODAY - pd.Timedelta(days=60), TODAY, variables=["TUR", "SPM"])
    v = hr.dropna(how="all")
    print(f"High-res L3 (~100 m) turbidity/SPM: {len(v)} usable days in 60; " +
          ", ".join(f"{i.date()}: TUR {r.get('turb', np.nan):.1f} FNU / SPM {r.get('spm', np.nan):.1f}" for i, r in v.tail(4).iterrows()))


def p10_obs_vs_model_temp():
    obs = cm.fetch_insitu("15480", TODAY - pd.Timedelta(days=30), TODAY, ["temp"])
    o = obs["temp"].resample("D").mean().dropna()
    mod = cm.fetch_timeseries("phy_temp", LAT, LON, TODAY - pd.Timedelta(days=30), TODAY, variables=["thetao"])["temp"]
    sat = cm.fetch_timeseries("sst_l4_nrt", LAT, LON, TODAY - pd.Timedelta(days=30), TODAY)["sst"]
    df = pd.DataFrame({"station_15480": o, "model": mod, "satellite": sat}).dropna()
    print(f"Coastal station 15480 (NIMH Constanta, in situ) vs model (phy_temp 0.5 m) vs satellite (sst_l4_nrt), {len(df)} common days:")
    for c in ("model", "satellite"):
        d = df[c] - df.station_15480
        print(f"  {c:9s} - station: bias {d.mean():+.2f} C, RMSD {np.sqrt((d ** 2).mean()):.2f} C, r {df[c].corr(df.station_15480):.2f}")
    print(df.tail(5).round(2).to_string())


def p11_reanalysis_vs_casts():
    """Validate the physics reanalysis against NIMRD CTD/bottle casts (EMODnet Chemistry, Constanta transect CT1/CT2)."""
    c = ei.fetch_chemistry_samples(LAT, LON, radius_km=25, start="1993-01-01", end="2021-12-31",
                                   variables=["temp", "sal"], max_depth=60).reset_index()
    rows = []
    for st in ("CT1", "CT2"):
        s = c[c.station == st]
        la, lo = s.lat.mean(), s.lon.mean()
        kw = dict(start="1993-01-01", end="1999-12-31")
        tt = cm.fetch_timeseries("rea_phy_temp", la, lo, variables=["thetao"], **kw)
        tb = cm.fetch_timeseries("rea_phy_temp", la, lo, variables=["bottomT"], **kw)
        ss = cm.fetch_timeseries("rea_phy_sal", la, lo, variables=["so"], **kw)
        print(f"{st} ({la:.3f}N {lo:.3f}E, casts to {s.depth.max():.0f} m) -> model {where(tb)}")
        for t, cast in s.groupby("time"):
            d = t.normalize()
            if d not in tb.index:
                continue
            top, bot = cast.nsmallest(1, "depth").iloc[0], cast.nlargest(1, "depth").iloc[0]
            if top.depth <= 2:
                rows.append(dict(st=st, kind="surface T", obs=top.temp, mod=tt.loc[d, "temp"]))
                rows.append(dict(st=st, kind="surface S", obs=top.sal, mod=ss.loc[d, "sal"]))
            if bot.depth >= s.depth.max() - 5:
                rows.append(dict(st=st, kind="bottom T", obs=bot.temp, mod=tb.loc[d, "bottom_temp"]))
    r = pd.DataFrame(rows).dropna()
    r["diff"] = r["mod"] - r["obs"]
    out = r.groupby("kind").apply(lambda g: pd.Series({"n": len(g), "bias": g["diff"].mean(),
                                                         "rmsd": np.sqrt((g["diff"] ** 2).mean()),
                                                         "r": g["mod"].corr(g["obs"])}))
    print("Reanalysis minus NIMRD casts, 1993-1999 (CT1 + CT2):")
    print(out.round(2).to_string())


if __name__ == "__main__":
    print(f"Physical indicator check at Constanta ({LAT} N, {LON} E), run {pd.Timestamp.now():%Y-%m-%d %H:%M}, reference date {TODAY.date()}")
    print(f"Copernicus login present: {cm.is_logged_in()}")
    run("P1  SST anomaly, marine heatwaves and cold spells [sst_l4_rep + sst_l4_nrt]", p1_sst_mhw)
    run("P2  Bottom temperature anomaly [phy_temp bottomT vs rea_phy_temp]", p2_bottom_temp)
    run("P3  Stratification (delta sigma-theta) and mixed-layer depth [phy_temp, phy_sal, phy_mld + rea_*]", p3_stratification)
    run("P4  Upwelling index [sst_l4_rep/nrt coast vs offshore + ERA5 wind via Open-Meteo]", p4_upwelling)
    run("P5  Danube freshwater influence [danube_discharge (GloFAS) + phy_sal / rea_phy_sal]", p5_danube_salinity)
    run("P6  Transparency and light at the seabed [sat_kd490_my]", p6_transparency)
    run("P7  Storms, resuspension and sea level [wav, Open-Meteo marine, IOC-csta2, phy_ssh]", p7_storms)
    run("Context: surface currents [phy_cur]", p8_currents)
    run("Context: turbidity and suspended matter [spm_dineof (open_data), sat_hr_l3]", p9_turbidity)
    run("Context: observed vs model vs satellite temperature [insitu 15480, phy_temp, sst_l4_nrt]", p10_obs_vs_model_temp)
    run("Validation: physics reanalysis vs NIMRD casts [EMODnet Chemistry CT1/CT2, rea_phy_temp, rea_phy_sal]", p11_reanalysis_vs_casts)
