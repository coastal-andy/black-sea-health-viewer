"""Seasonal cycles (harmonic fit with the PSD periods) and interannual linear trend, for every trusted series.

    .venv\\Scripts\\python.exe scripts/seasonal/run_seasonal.py      # cache only (MARINEKIT_OFFLINE=1 is always set)

Third analysis step, after the source validation (scripts/validation) and the power spectra (scripts/spectra):
  * data: the same QC'd series as both earlier steps (compare_sources.fetch_insitu / fetch_other, imported read-only);
    chlorophyll in log10 (so its aggregates are means of log10 = geometric means);
  * periods: the 3 strongest significant peaks per station / variable / source from docs/indicators/spectra/peaks.csv
    that the sampling step can resolve (harmonic.select_periods);
  * two windows: monthly means over the last 20 years where the record allows, weekly means over the last 10 years;
  * fit: OLS harmonic regression with Newey-West standard errors, a WLS variant (1 / se^2), nested models 0..K cycles;
  * trend: OLS on complete annual means (trend.linear_trend), slope per decade, only with >= 8 complete years.
  * SYNTHETIC check: the PSD step's 40-year series, planted values known.

Outputs in docs/indicators/seasonal/: README.md, cycles.csv, models.csv, nested.csv, trends.csv, annual_means.csv,
figures/*.png.
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "indicators" / "seasonal"
FIG = OUT / "figures"
PEAKS = ROOT / "docs" / "indicators" / "spectra" / "peaks.csv"
sys.path.insert(0, str(HERE))
from harmonic import YEAR_D, acf, aggregate, compare_nested, fit_harmonics, select_periods  # noqa: E402
from trend import linear_trend  # noqa: E402

STATIONS = ["EUXRo03", "EUXRoOB01", "EUXRoOB02", "EUXRoOB03"]
VARS = ["sst", "chl", "sal", "o2"]
UNIT = {"sst": "°C", "chl": "log10(mg/m³)", "sal": "PSU", "o2": "mg/L"}
TITLE = {"sst": "Sea surface temperature", "chl": "Chlorophyll-a (surface, log10)", "sal": "Surface salinity",
         "o2": "Surface dissolved oxygen"}
SRC_LABEL = {"insitu": "buoy (in situ)", "satellite": "satellite", "model": "model", "synthetic": "SYNTHETIC"}
WINDOWS = {"monthly": dict(freq="MS", years=20, step=YEAR_D / 12),
           "weekly": dict(freq="W", years=10, step=7.0)}
# Okabe-Ito
OI = dict(black="#000000", orange="#E69F00", sky="#56B4E9", green="#009E73", yellow="#F0E442", blue="#0072B2",
          vermilion="#D55E00", purple="#CC79A7", grey="#999999")
CYC_COL = [OI["blue"], OI["vermilion"], OI["green"]]
SRC_COL = {"insitu": OI["black"], "satellite": OI["blue"], "model": OI["vermilion"], "synthetic": OI["green"]}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# --------------------------------------------------------------------------------------------------------- data
def collect() -> dict:
    """{(station, var): {source: daily Series}} from the cache, via the validation step's loaders and QC."""
    os.environ["MARINEKIT_OFFLINE"] = "1"
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    import compare_sources as cs  # noqa: E402  (read-only reuse)
    from marinekit import datahub as dh  # noqa: E402

    warnings.filterwarnings("ignore")
    data = {}
    for st in STATIONS:
        for var in VARS:
            try:
                ins, _ = cs.fetch_insitu(dh, st, var)
            except Exception as ex:  # noqa: BLE001
                log(f"{st} {var}: no in situ ({str(ex)[:100]})")
                continue
            d = {"insitu": cs.transform(var, ins).dropna()}
            for src in cs.VARIABLES[var]["others"]:
                try:
                    full, _ = cs.fetch_other(dh, st, var, src, ins)
                    d[src] = cs.transform(var, full).dropna()
                except Exception as ex:  # noqa: BLE001
                    log(f"{st} {var} {src}: unavailable ({str(ex)[:100]})")
            data[(st, var)] = d
            log(f"{st} {var}: sources {list(d)}")
    return data


def window(s: pd.Series, years: int) -> pd.Series:
    s = s.dropna().sort_index()
    return s[s.index > s.index[-1] - pd.DateOffset(years=years)]


# ------------------------------------------------------------------------------------------------------- figures
def _style(ax):
    ax.grid(alpha=0.3, lw=0.5)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)


def _month_axis(ax, period):
    if abs(period - YEAR_D) < 1:
        ticks = [pd.Timestamp(2001, m, 1).dayofyear - 1 for m in range(1, 13)]
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(2001, m, 1).strftime("%b")[0] for m in range(1, 13)])
        ax.set_xlabel("month (cycle folded on the year)")
    else:
        ax.set_xlabel(f"day within the {period:.1f}-day cycle")


def fit_figure(fit: dict, agg: pd.DataFrame, title: str, unit: str, path: Path, color: str, label: str) -> Path:
    K = len(fit["cycles"])
    fig = plt.figure(figsize=(11, 8.2 if K else 6))
    gs = fig.add_gridspec(3 if K else 2, max(K, 1) * 2 if K else 2, height_ratios=[1.3, 1, 0.9] if K else [1.3, 0.9],
                          hspace=0.55, wspace=0.6)
    ax0 = fig.add_subplot(gs[0, :])
    d = fit["data"]
    ax0.errorbar(d.index, d.values, yerr=agg["se"].reindex(d.index).values, fmt="o", ms=2.5, color=color, lw=0.6,
                 alpha=0.75, label=f"{label} ({agg.attrs['how']}s, ± SE)")
    grid = pd.date_range(d.index[0], d.index[-1], freq="D")
    ax0.plot(grid, fit["predict"](grid).values, color=OI["orange"], lw=1.6,
             label=f"fit: trend + {K} cycle(s), adj. R² {fit['model']['r2_adj']:.2f}")
    ax0.set_ylabel(unit)
    ax0.set_title(title, fontsize=10.5, loc="left")
    ax0.legend(fontsize=8, loc="best", frameon=True, framealpha=0.85, ncol=2)
    _style(ax0)
    resid = fit["resid"]
    for k, c in enumerate(fit["cycles"]):
        ax = fig.add_subplot(gs[1, 2 * k:2 * k + 2])
        P = c["period_d"]
        t = ((d.index - fit["t0"]) / pd.Timedelta(days=1)).to_numpy(float)
        comp = fit["component"](d.index, k).values
        ax.plot(t % P, resid.values + comp, "o", ms=2.2, color=OI["grey"], alpha=0.6, label="partial residual")
        tt = np.linspace(0, P, 300)
        cc = c["a"] * np.cos(2 * np.pi * tt / P) + c["b"] * np.sin(2 * np.pi * tt / P)
        ax.plot(tt, cc, color=CYC_COL[k], lw=2, label="fitted cycle")
        ax.axvline(c["t_max_d"], color=CYC_COL[k], ls=":", lw=1)
        lo, hi = c["amplitude_ci"]
        ax.set_title(f"cycle {k + 1}: P = {P:.1f} d\namp {c['amplitude']:.2f} [{lo:.2f}, {hi:.2f}] {unit}, "
                     f"{_pp(c['p_value'])}", fontsize=8.5, loc="left")
        ax.set_ylabel(unit)
        _month_axis(ax, P)
        _style(ax)
    row = 2 if K else 1
    axr = fig.add_subplot(gs[row, :(2 * K - 2) if K > 1 else 1])
    axr.axhline(0, color=OI["black"], lw=0.8)
    axr.plot(resid.index, resid.values, "o-", ms=2, lw=0.5, color=OI["purple"])
    for ax_ in (ax0, axr):
        loc = mdates.AutoDateLocator(maxticks=8)
        ax_.xaxis.set_major_locator(loc)
        ax_.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    axr.set_ylabel(f"residual ({unit})")
    axr.set_title(f"residuals: sd {fit['model']['resid_sd']:.2f} {unit}", fontsize=9, loc="left")
    _style(axr)
    axa = fig.add_subplot(gs[row, (2 * K - 2) if K > 1 else 1:])
    r = acf(resid.values, min(12, len(resid) // 3))
    axa.bar(np.arange(len(r)), r, color=OI["purple"], width=0.6)
    lim = 1.96 / np.sqrt(len(resid))
    axa.axhspan(-lim, lim, color=OI["grey"], alpha=0.25)
    axa.set_xlabel(f"lag ({'months' if agg.attrs['freq'] == 'MS' else 'weeks'})")
    axa.set_ylabel("autocorrelation")
    axa.set_title(f"residual ACF, lag-1 = {fit['residuals']['lag1_autocorr']:.2f}", fontsize=9, loc="left")
    _style(axa)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


def trend_figure(tr: dict, title: str, unit: str, path: Path, color: str) -> Path:
    am = tr["annual"]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ok, bad = am[am.complete], am[~am.complete]
    ax.errorbar(ok.index, ok.value, yerr=1.96 * ok.se, fmt="o", color=color, capsize=3,
                label="complete years (mean ± 95 % CI)")
    if len(bad):
        ax.plot(bad.index, bad.value, "x", color=OI["grey"], label="incomplete years (not used)")
    if tr["meaningful"]:
        x = np.array([ok.index.min(), ok.index.max()], float)
        ax.plot(x, tr["intercept"] + tr["slope_per_year"] * x, color=OI["orange"], lw=2,
                label=f"OLS: {tr['slope_per_decade']:+.2f} {unit}/decade [{tr['ci'][0]:+.2f}, {tr['ci'][1]:+.2f}], "
                      f"{_pp(tr['p_value'])}")
    else:
        ax.text(0.02, 0.05, tr["note"], transform=ax.transAxes, fontsize=9, color=OI["vermilion"])
    ax.set_ylabel(f"annual mean ({unit})")
    ax.set_xlabel("year")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_title(title, fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    _style(ax)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


# ------------------------------------------------------------------------------------------------------- text
def _pp(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _amp_text(var: str, c: dict) -> str:
    A = c["amplitude"]
    if var == "chl":
        return f"x{10 ** A:.2f} above / below the mean (log10 amplitude {A:.2f})"
    return f"± {A:.2f} {UNIT[var]}"


def sentence(st, var, src, win, fit, sel) -> str:
    if not fit["cycles"]:
        return (f"What: no significant cycle that {win} means can resolve was found in the {SRC_LABEL[src]} "
                f"spectrum. So what: only the mean and the linear term are fitted; seasonality cannot be described "
                f"from this record.")
    c0 = fit["cycles"][0]
    what = (f"What: {SRC_LABEL[src]} {TITLE[var].lower()} at {st} ({win} means, {fit['start']:%Y-%m} to "
            f"{fit['end']:%Y-%m}) follows a {c0['period_d']:.0f}-day cycle of {_amp_text(var, c0)}, highest around "
            f"{c0['max_date']}")
    if len(fit["cycles"]) > 1:
        what += "; " + ", ".join(f"{c['period_d']:.0f} d ({_amp_text(var, c)}, {_pp(c['p_value'])})"
                                 for c in fit["cycles"][1:])
    what += f". Trend + cycles explain {fit['model']['r2_adj']:.0%} of the variance of the {win} means."
    so = (f" So what: anomalies and trends must be read against this cycle; what remains after it is about "
          f"± {fit['model']['resid_sd']:.2f} {UNIT[var]} ({win} residual sd)")
    if fit["residuals"]["lag1_autocorr"] > 0.3:
        so += f", and it is persistent (lag-1 r = {fit['residuals']['lag1_autocorr']:.2f}), so HAC errors are used"
    return what + so + "."


def trend_sentence(st, var, src, tr) -> str:
    if not tr["meaningful"]:
        return (f"What: {SRC_LABEL[src]} {TITLE[var].lower()} at {st} has {tr['n_years']} complete year(s). "
                f"So what: too short for an interannual trend (need at least 8 complete years); no slope is given.")
    sig = "statistically significant" if tr["p_value"] < 0.05 else "not statistically significant"
    extra = ""
    if var == "chl":
        extra = f" ({(10 ** tr['slope_per_decade'] - 1) * 100:+.0f} % per decade)"
    return (f"What: annual means of {SRC_LABEL[src]} {TITLE[var].lower()} at {st} ({tr['years'][0]}-{tr['years'][1]}, "
            f"{tr['n_years']} complete years) change by {tr['slope_per_decade']:+.2f} {UNIT[var]} per decade{extra} "
            f"(95 % CI {tr['ci'][0]:+.2f} to {tr['ci'][1]:+.2f}, {_pp(tr['p_value'])}). So what: the change is {sig}; "
            f"with about {tr['n_years']} points, year-to-year variability dominates any reading of it.")


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------- synthetic check
def synthetic_check() -> tuple[pd.DataFrame, list]:
    sys.path.insert(0, str(ROOT / "scripts" / "spectra"))
    from synthetic import synthetic_long_daily
    df = synthetic_long_daily()
    p = df.attrs["planted"]
    s = df["sst"]
    periods = [p["annual_period_d"], p["semiannual_period_d"], p["multiyear_period_d"]]
    planted = {p["annual_period_d"]: (p["annual_amp"], p["annual_peak_doy"] - 1),
               p["semiannual_period_d"]: (p["semiannual_amp"], 39.0), p["multiyear_period_d"]: (p["multiyear_amp"], None)}
    rows, figs = [], []
    for win, cfg in WINDOWS.items():
        agg = aggregate(window(s, cfg["years"]), cfg["freq"])
        per = [P for P in periods if 2 * cfg["step"] <= P <= (agg.index[-1] - agg.index[0]).days]
        fit = fit_harmonics(agg.value, per, bin_days=cfg["step"])
        for c in fit["cycles"]:
            A0, tm0 = planted[c["period_d"]]
            lo, hi = c["amplitude_ci"]
            rows.append(dict(window=f"{win}, {fit['start']:%Y}-{fit['end']:%Y}", cycle=f"{c['period_d']:.1f} d",
                             planted_amp=f"{A0:.2f}", fitted_amp=f"{c['amplitude']:.2f} [{lo:.2f}, {hi:.2f}]",
                             planted_max="" if tm0 is None else _planted_dates(tm0, c["period_d"]),
                             fitted_max=c["max_date"] if c["period_d"] < 400 else f"day {c['t_max_d']:.0f}",
                             p=_p(c["p_value"]), ok="yes" if lo <= A0 <= hi else "no"))
        title = (f"SYNTHETIC 40-year daily SST-like series ({win} means, last {cfg['years']} years): planted annual 8 °C, "
                 f"semi-annual 1 °C, 6-year 0.4 °C, trend 0.4 °C/decade")
        figs.append((fit_figure(fit, agg, title, "°C", FIG / f"SYNTHETIC_{win}_fit.png", SRC_COL["synthetic"],
                                "SYNTHETIC"), f"SYNTHETIC check, {win} means"))
    tr = linear_trend(s, exclude_year=2100)
    rows.append(dict(window=f"annual means, {tr['years'][0]}-{tr['years'][1]}", cycle="linear trend",
                     planted_amp=f"{10 * p['trend_per_year']:+.2f} °C/decade",
                     fitted_amp=f"{tr['slope_per_decade']:+.2f} [{tr['ci'][0]:+.2f}, {tr['ci'][1]:+.2f}]",
                     planted_max="", fitted_max="", p=_p(tr["p_value"]),
                     ok="yes" if tr["ci"][0] <= 10 * p["trend_per_year"] <= tr["ci"][1] else "no"))
    figs.append((trend_figure(tr, "SYNTHETIC 40-year series: annual means and OLS trend (planted +0.40 °C/decade)",
                              "°C", FIG / "SYNTHETIC_trend.png", SRC_COL["synthetic"]), "SYNTHETIC trend check"))
    return pd.DataFrame(rows), figs


def _planted_dates(t0: float, P: float) -> str:
    from harmonic import phase_label
    return phase_label(t0, P)


# ------------------------------------------------------------------------------------------------------------ main
def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    peaks = pd.read_csv(PEAKS)
    log(f"peaks.csv: {len(peaks)} rows, columns {list(peaks.columns)}")
    data = collect()
    cyc_rows, mod_rows, nest_rows, tr_rows, am_rows, summary = [], [], [], [], [], []
    for (st, var), d in data.items():
        for src, s in d.items():
            s = s.dropna()
            if len(s) < 60:
                continue
            for win, cfg in WINDOWS.items():
                sw = window(s, cfg["years"])
                agg = aggregate(sw, cfg["freq"], how="mean")
                rec = float((agg.index[-1] - agg.index[0]).days)
                fb = ([(st, var, o) for o in ("satellite", "model", "insitu") if o != src and o in d]
                      + [(o, var, src) for o in STATIONS if o != st])
                sel = select_periods(peaks, st, var, src, step_d=cfg["step"], record_d=rec, k=3, fallback=fb)
                periods = [c["period_d"] for c in sel]
                try:
                    b = cfg["step"]
                    fit = fit_harmonics(agg.value, periods, bin_days=b)
                    fit_w = fit_harmonics(agg.value, periods, se=agg.se, weighted=True, bin_days=b)
                    nest = compare_nested(agg.value, periods, bin_days=b)
                except ValueError as ex:
                    log(f"{st} {var} {src} {win}: {ex}")
                    continue
                key = dict(station=st, variable=var, source=src, window=win,
                           start=f"{fit['start']:%Y-%m-%d}", end=f"{fit['end']:%Y-%m-%d}", n=fit["n"])
                for c, cs_, cw in zip(sel, fit["cycles"], fit_w["cycles"]):
                    cyc_rows.append({**key, "period_psd_d": round(c["period_psd"], 2), "period_d": round(c["period_d"], 2),
                                     "snapped": c["snapped"], "period_from": c["from_series"], "cycle": c["cycle"], "psd_spectrum": c["spectrum"],
                                     "psd_rank_or_strength": c["strength"], "amplitude": cs_["amplitude"],
                                     "amplitude_raw": cs_["amplitude_raw"], "attenuation": cs_["attenuation"],
                                     "amplitude_se_hac": cs_["amplitude_se"], "amplitude_se_ols": cs_["amplitude_se_ols"],
                                     "amp_ci_lo": cs_["amplitude_ci"][0], "amp_ci_hi": cs_["amplitude_ci"][1],
                                     "t_max_d": cs_["t_max_d"], "phase_se_d": cs_["phase_se_d"],
                                     "phase_ci_lo_d": cs_["phase_ci_d"][0], "phase_ci_hi_d": cs_["phase_ci_d"][1],
                                     "max_date": cs_["max_date"], "p_hac": cs_["p_value"], "p_ols": cs_["p_value_ols"],
                                     "amplitude_wls": cw["amplitude"], "max_date_wls": cw["max_date"]})
                m, r = fit["model"], fit["residuals"]
                mod_rows.append({**key, "periods_d": ";".join(f"{p:.2f}" for p in periods), **m, **r,
                                 "r2_adj_wls": fit_w["model"]["r2_adj"]})
                for _, nr in nest.iterrows():
                    nest_rows.append({**key, **nr.to_dict()})
                title = (f"{TITLE[var]}, {SRC_LABEL[src]} at {st}: {win} means {fit['start']:%Y-%m} to "
                         f"{fit['end']:%Y-%m}, periods from the PSD")
                fp = fit_figure(fit, agg, title, UNIT[var], FIG / f"fit_{st}_{var}_{src}_{win}.png", SRC_COL[src],
                                SRC_LABEL[src])
                summary.append(dict(key=key, fit=fit, sel=sel, nest=nest, fig=fp,
                                    text=sentence(st, var, src, win, fit, sel)))
                log(f"{st} {var} {src} {win}: n={fit['n']} periods={[round(p, 1) for p in periods]} "
                    f"R2adj={m['r2_adj']:.2f}")
            tr = linear_trend(s)
            am = tr["annual"].reset_index()
            for _, a in am.iterrows():
                am_rows.append(dict(station=st, variable=var, source=src, **a.to_dict()))
            tr_rows.append(dict(station=st, variable=var, source=src, n_years=tr["n_years"],
                                years="" if not tr["years"] else f"{tr['years'][0]}-{tr['years'][1]}",
                                meaningful=tr["meaningful"], slope_per_decade=tr["slope_per_decade"],
                                ci_lo=tr["ci"][0], ci_hi=tr["ci"][1], p_value=tr["p_value"], r2=tr["r2"],
                                note=tr.get("note", "")))
            tp = trend_figure(tr, f"{TITLE[var]}, {SRC_LABEL[src]} at {st}: annual means and linear trend", UNIT[var],
                              FIG / f"trend_{st}_{var}_{src}.png", SRC_COL[src])
            summary.append(dict(key=dict(station=st, variable=var, source=src, window="trend"), trend=tr, fig=tp,
                                text=trend_sentence(st, var, src, tr)))
    cyc, mod, nest, trd = (pd.DataFrame(x) for x in (cyc_rows, mod_rows, nest_rows, tr_rows))
    cyc.to_csv(OUT / "cycles.csv", index=False, float_format="%.4g")
    mod.to_csv(OUT / "models.csv", index=False, float_format="%.4g")
    nest.to_csv(OUT / "nested.csv", index=False, float_format="%.4g")
    trd.to_csv(OUT / "trends.csv", index=False, float_format="%.4g")
    pd.DataFrame(am_rows).to_csv(OUT / "annual_means.csv", index=False, float_format="%.4g")
    syn, synfigs = synthetic_check()
    syn.to_csv(OUT / "synthetic_check.csv", index=False)
    import report  # noqa: E402
    report.write(OUT, peaks, cyc, mod, nest, trd, syn, synfigs, summary)
    log("done")


if __name__ == "__main__":
    main()
