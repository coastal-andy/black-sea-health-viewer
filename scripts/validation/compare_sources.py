"""Source validation for the Romanian Black Sea coast: in situ vs satellite vs model.

    .venv\\Scripts\\python.exe scripts/validation/compare_sources.py            # fetch (cached), match, metrics, figures, report
    .venv\\Scripts\\python.exe scripts/validation/compare_sources.py --offline  # cache only (MARINEKIT_OFFLINE=1)

Rules (agreed with the user):
  * In situ drives everything. Only trusted in situ is used: the offshore buoys EUXRoOB01-03 (GeoEcoMar, 2024 onwards),
    the older offshore buoy EUXRo03 (Copernicus In Situ TAC, 2013-2023) and EMODnet Chemistry bottle samples (0-5 m,
    within 30 km) at the Constanta coast point. Coastal buoys EUXRoCB0x and station 15480 are untrusted and skipped.
  * Satellite and model are fetched at the in situ position, over the in situ period only, and kept only on days with
    an in situ value. Where no in situ exists (e.g. waves: no in situ source in marinekit), nothing is compared.
  * Everything goes through marinekit.datahub (read-only): get_series(...) and, for bottle temperature / salinity / O2
    at the coast (no register entry), the module's own bottle reader dh._fetch_bottles.

Outputs in docs/indicators/validation/: README.md (report), seasonal_metrics.md, inventory.csv, metrics.csv,
metrics_seasonal.csv, matched_daily.csv, figures/*.png, figures/sst_3d.html.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")

OUT = ROOT / "docs" / "indicators" / "validation"
FIG = OUT / "figures"

# ---------------------------------------------------------------------------------------------- configuration
# Stations: only places with trusted in situ data. Positions from marinekit.datahub.PLATFORMS.
STATIONS = {
    "EUXRoOB01": dict(valid_from="2024-04-06", lat=44.71, lon=30.76, insitu="buoy", window=("2024-01-01", "2026-11-22"),
                      label="Offshore buoy EUXRoOB01 (44.71 N, 30.76 E)"),
    "EUXRoOB02": dict(valid_from="2024-04-06", lat=44.325, lon=30.41, insitu="buoy", window=("2024-01-01", "2026-11-22"),
                      label="Offshore buoy EUXRoOB02 (44.33 N, 30.41 E)"),
    "EUXRoOB03": dict(valid_from="2024-04-06", lat=43.977, lon=29.924, insitu="buoy", window=("2024-01-01", "2026-11-22"),
                      label="Offshore buoy EUXRoOB03 (43.98 N, 29.92 E)"),
    "EUXRo03": dict(lat=43.98, lon=29.936, insitu="buoy", window=("2013-01-01", "2023-12-31"),
                    label="Offshore buoy EUXRo03, older record (43.98 N, 29.94 E)"),
    "Constanta bottles": dict(lat=44.17, lon=28.72, insitu="bottles", window=("1993-01-01", "2021-12-31"),
                              label="Constanta coast, EMODnet bottle samples 0-5 m within 30 km of 44.17 N, 28.72 E"),
}

# Variables: datahub variable id, in situ column, the other sources (datahub source ids), unit, transform.
VARIABLES = {
    "sst": dict(title="Sea surface temperature", unit="°C", others=["satellite", "model"], bottle_col="temp",
                scale=1.0, transform=None),
    "chl": dict(title="Chlorophyll-a (surface)", unit="mg/m³", others=["satellite", "model"], bottle_col=None,
                scale=1.0, transform="log10"),
    "sal": dict(title="Surface salinity", unit="PSU", others=["model"], bottle_col="sal", scale=1.0, transform=None),
    "o2": dict(title="Surface dissolved oxygen", unit="mg/L", others=["model"], bottle_col="o2", scale=0.032,
               transform=None),
    "no3": dict(title="Nitrate (shape only)", unit="mmol/m³", others=["model"], bottle_col="no3", scale=1.0,
                transform="z", bottles_only=True, window=("1993-01-01", "1999-12-31")),
    "po4": dict(title="Phosphate (shape only)", unit="mmol/m³", others=["model"], bottle_col="po4", scale=1.0,
                transform="z", bottles_only=True, window=("1993-01-01", "1999-12-31")),
}

# In situ QC (scripts/validation/metrics.despike): drop daily values farther than this from the buoy's own centred
# 15-day running median. Chlorophyll in log10 (0.7 = factor 5). Values: OURS, chosen to catch only gross errors.
SPIKE = {"sst": 3.0, "sal": 2.0, "o2": 2.5, "chl": 0.7}
# Buoy surface O2 kept only when its saturation is within this range (%, OURS): offshore surface water is close to
# saturation; long runs at 20-60 % next to a near-saturated model are sensor fouling or drift (inferred).
O2_SAT_RANGE = (60.0, 150.0)
# valid_from (OB01-03): first day after deployment. Before 2024-04-06 the buoys read ~21 C water and ~35 mg/m3 chl while
# satellite and model give 8-10 C and 0.3 mg/m3: instruments not yet in the sea (inferred from the data, not documented).

# Earliest dates of the multi-year products (copernicus catalogue; requests before these are clipped).
SOURCE_START = {("sst", "satellite"): "1982-01-01", ("chl", "satellite"): "1997-09-04"}
MODEL_START = "1993-01-01"

NATIVE = {
    "buoy": "sub-daily records, daily means from datahub",
    "bottles": "irregular cruises, 0-5 m samples averaged per day",
    ("sst", "satellite"): "daily L4 analysis (REP 0.05 deg to 2024, then NRT 0.01 deg minus 0.53 C offset)",
    ("chl", "satellite"): "daily L4 gap-free, 1 km (multi-year + interim, NRT last 20 days)",
    "model": "daily mean, 2.5 km grid (reanalysis, then analysis/forecast)",
}

# Okabe-Ito
SEASON_COLOR = {"DJF": "#0072B2", "MAM": "#009E73", "JJA": "#E69F00", "SON": "#D55E00"}
SEASON_MARKER = {"DJF": "o", "MAM": "^", "JJA": "s", "SON": "D"}
SOURCE_COLOR = {"satellite": "#0072B2", "model": "#D55E00"}
STATION_MARKER = {"EUXRoOB01": "o", "EUXRoOB02": "s", "EUXRoOB03": "^", "EUXRo03": "D", "Constanta bottles": "v"}
INK, MUTED, GRID = "#1f2328", "#59636e", "#d8dee4"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------------------------------------- fetching
def _dist(attrs: dict) -> float | None:
    ds = [d.get("distance_km") for d in (attrs.get("datasets") or []) if isinstance(d, dict)]
    ds = [float(d) for d in ds if d not in (None, "None")]
    if ds:
        return round(max(ds), 2)
    d = attrs.get("distance_km")
    return None if d in (None, "None") else round(float(d), 2)


def _datasets(attrs: dict) -> str:
    out = []
    for d in attrs.get("datasets") or []:
        if isinstance(d, dict):
            out.append(str(d.get("dataset") or d.get("key")))
    return "; ".join(dict.fromkeys(out))


def fetch_insitu(dh, st: str, var: str) -> tuple[pd.Series, dict]:
    cfg, v = STATIONS[st], VARIABLES[var]
    s0, s1 = v.get("window", cfg["window"]) if cfg["insitu"] == "bottles" else cfg["window"]
    if cfg["insitu"] == "buoy":
        df = dh.get_series(var, cfg["lat"], cfg["lon"], s0, s1, source="buoy")
        pid = df.attrs.get("platform")
        if pid != st:
            raise RuntimeError(f"nearest trusted buoy with {var} was {pid}, not {st}")
        s = df[var].dropna()
        s.index = pd.DatetimeIndex(s.index).normalize()
        n0 = len(s)
        if cfg.get("valid_from"):
            s = s[s.index >= pd.Timestamp(cfg["valid_from"])]
        n_commission = n0 - len(s)
        from metrics import despike
        keep = despike(s, SPIKE[var], log=(var == "chl"))
        n_spike = int((~keep).sum())
        s = s[keep]
        qc = f"{n_commission} before deployment, {n_spike} spikes"
        if var == "o2":
            # Plausibility (OURS): surface water offshore stays near saturation. Saturation from the buoy's own
            # temperature and a fixed S = 18 (the buoy salinity is unreliable; S changes saturation by < 1 % per PSU).
            t_b = dh.get_series("sst", cfg["lat"], cfg["lon"], s0, s1, source="buoy")["sst"]
            t_b.index = pd.DatetimeIndex(t_b.index).normalize()
            sat = pd.Series(dh.o2_saturation_pct(s / dh.O2_MG, t_b.reindex(s.index), 18.0), index=s.index)
            ok = sat.between(*O2_SAT_RANGE) | sat.isna()
            qc += f", {int((~ok).sum())} implausible saturation"
            s = s[ok]
        return s, dict(dataset=_datasets(df.attrs) or pid, distance_km=0.0, native=NATIVE["buoy"], qc_removed=qc)
    col = v["bottle_col"]
    if col is None:
        raise RuntimeError("too few bottle samples")
    if var in ("no3", "po4"):
        df = dh.get_series(var, cfg["lat"], cfg["lon"], s0, s1, source="bottles")
        s = df[var].dropna()
    else:
        s, _ = dh._fetch_bottles(col, cfg["lat"], cfg["lon"], s0, s1)   # read-only use of the datahub bottle reader
        s = s.dropna() * v["scale"]
    s.index = pd.DatetimeIndex(s.index).normalize()
    return s, dict(dataset="EMODnet Chemistry EUT_BLACKSEA_PROFILES (bottles 0-5 m, <= 30 km)",
                   distance_km="<= 30 (radius)", native=NATIVE["bottles"])


def fetch_other(dh, st: str, var: str, source: str, ins: pd.Series) -> tuple[pd.Series, dict]:
    """Satellite or model at the station position over the in situ period, then kept on in situ days only."""
    cfg = STATIONS[st]
    start = max(ins.index.min(), pd.Timestamp(SOURCE_START.get((var, source), MODEL_START)))
    end = ins.index.max()
    if start > end:
        raise RuntimeError(f"{source} starts after the last in situ value")
    df = dh.get_series(var, cfg["lat"], cfg["lon"], str(start.date()), str(end.date()), source=source)
    full = df[var].dropna()
    full.index = pd.DatetimeIndex(full.index).normalize()
    full = full.groupby(level=0).mean()
    native = NATIVE.get((var, source), NATIVE.get(source, ""))
    return full, dict(dataset=_datasets(df.attrs), distance_km=_dist(df.attrs), native=native,
                      trust=df.attrs.get("trust"), window=(start, end))


def collect(offline: bool) -> tuple[dict, pd.DataFrame]:
    if offline:
        os.environ["MARINEKIT_OFFLINE"] = "1"
    from marinekit import datahub as dh
    from metrics import gap_share

    data, inv = {}, []
    for st, cfg in STATIONS.items():
        for var, v in VARIABLES.items():
            if v.get("bottles_only") and cfg["insitu"] != "bottles":
                continue
            t0 = time.time()
            try:
                ins, a = fetch_insitu(dh, st, var)
            except Exception as ex:  # noqa: BLE001
                log(f"{st} {var}: no in situ ({str(ex)[:120]}) -> skipped")
                inv.append(dict(station=st, variable=var, source="in situ", status=f"no in situ: {str(ex)[:100]}"))
                continue
            if len(ins) < 3:
                log(f"{st} {var}: only {len(ins)} in situ days -> skipped")
                inv.append(dict(station=st, variable=var, source="in situ", n_days=len(ins), status="too few in situ days"))
                continue
            w0, w1 = ins.index.min(), ins.index.max()
            inv.append(dict(station=st, variable=var, source="in situ (" + cfg["insitu"] + ")", native=a["native"],
                            start=w0.date(), end=w1.date(), n_days=len(ins), gap_share=round(gap_share(ins, w0, w1), 3),
                            overlap_start=w0.date(), overlap_end=w1.date(), n_matched=len(ins),
                            distance_km=a["distance_km"], dataset=a["dataset"], qc_removed=a.get("qc_removed", "none"),
                            status="ok"))
            cols = {"insitu": ins}
            for src in v["others"]:
                try:
                    full, b = fetch_other(dh, st, var, src, ins)
                except Exception as ex:  # noqa: BLE001
                    log(f"{st} {var} {src}: unavailable ({str(ex)[:160]})")
                    inv.append(dict(station=st, variable=var, source=src, status=f"unavailable: {str(ex)[:100]}"))
                    continue
                m = full.reindex(ins.index).dropna()
                inv.append(dict(station=st, variable=var, source=src, native=b["native"],
                                start=full.index.min().date() if len(full) else None,
                                end=full.index.max().date() if len(full) else None, n_days=len(full),
                                gap_share=round(gap_share(full, *b["window"]), 3),
                                overlap_start=m.index.min().date() if len(m) else None,
                                overlap_end=m.index.max().date() if len(m) else None, n_matched=len(m),
                                distance_km=b["distance_km"], dataset=b["dataset"], trust=b["trust"], status="ok"))
                cols[src] = full.reindex(ins.index)
            data[(st, var)] = pd.DataFrame(cols)
            log(f"{st} {var}: {len(ins)} in situ days, sources {list(cols)} ({time.time() - t0:.0f} s)")
    return data, pd.DataFrame(inv)


# ---------------------------------------------------------------------------------------------- metrics
PAIRS = [("insitu", "satellite"), ("insitu", "model"), ("satellite", "model")]
PAIR_LABEL = {("insitu", "satellite"): "in situ vs satellite", ("insitu", "model"): "in situ vs model",
              ("satellite", "model"): "satellite vs model"}
SRC_LABEL = {"insitu": "in situ", "satellite": "satellite", "model": "model"}


def transform(var: str, s: pd.Series) -> pd.Series:
    t = VARIABLES[var]["transform"]
    if t == "log10":
        return np.log10(s.where(s > 0))
    if t == "z":
        from metrics import zscore
        return zscore(s)
    return s


def metric_tables(data: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    from metrics import metrics_by_season, spearman
    rows, srows = [], []
    for (st, var), df in data.items():
        for a, b in PAIRS:
            if a not in df or b not in df:
                continue
            j = df[[a, b]].dropna()
            if len(j) < 3:
                continue
            x, y = transform(var, j[a]), transform(var, j[b])
            tab = metrics_by_season(x, y)
            anom_r2 = np.nan
            if VARIABLES[var]["transform"] != "z":
                # day-to-day skill: remove each source's own mean per calendar month, then correlate
                ax_ = x - x.groupby(x.index.month).transform("mean")
                ay_ = y - y.groupby(y.index.month).transform("mean")
                ok = ax_.notna() & ay_.notna()
                if ok.sum() >= 10:
                    anom_r2 = float(np.corrcoef(ax_[ok], ay_[ok])[0, 1] ** 2)
            meta = dict(station=st, variable=var, pair=PAIR_LABEL[(a, b)], space=VARIABLES[var]["transform"] or "linear",
                        start=j.index.min().date(), end=j.index.max().date())
            for _, r in tab.iterrows():
                row = {**meta, **r.to_dict()}
                if r["season"] == "all":
                    row["spearman"] = spearman(j[a], j[b])
                    row["r2_anom"] = anom_r2
                    if VARIABLES[var]["transform"] == "log10":
                        # linear-space bias for readers: median ratio other / in situ
                        row["median_ratio"] = float(np.nanmedian(j[b] / j[a]))
                    rows.append(row)
                else:
                    srows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(srows)


# ---------------------------------------------------------------------------------------------- figures
def _style(ax):
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def scatter_figures(data: dict, metrics: pd.DataFrame) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from metrics import season_of

    FIG.mkdir(parents=True, exist_ok=True)
    out = []
    for var, v in VARIABLES.items():
        sts = [st for st in STATIONS if (st, var) in data]
        if not sts:
            continue
        pairs = [p for p in PAIRS if any(p[0] in data[(st, var)] and p[1] in data[(st, var)] for st in sts)]
        if not pairs:
            continue
        nr, nc = len(sts), len(pairs)
        fig, axes = plt.subplots(nr, nc, figsize=(4.1 * nc, 3.9 * nr), squeeze=False)
        t = v["transform"]
        unit = {"log10": f"log10 {v['unit']}", "z": "standardised anomaly z (unitless)"}.get(t, v["unit"])
        for i, st in enumerate(sts):
            df = data[(st, var)]
            for k, (a, b) in enumerate(pairs):
                ax = axes[i][k]
                _style(ax)
                if a not in df or b not in df or df[[a, b]].dropna().shape[0] < 3:
                    ax.text(0.5, 0.5, "no overlapping data", ha="center", va="center", color=MUTED,
                            transform=ax.transAxes, fontsize=9)
                    ax.set_xticks([]), ax.set_yticks([])
                    ax.set_title(f"{st}: {PAIR_LABEL[(a, b)]}", fontsize=9, color=INK, loc="left")
                    continue
                j = df[[a, b]].dropna()
                x, y = transform(var, j[a]), transform(var, j[b])
                ok = x.notna() & y.notna()
                x, y = x[ok], y[ok]
                seas = season_of(x.index)
                for sname in SEASON_COLOR:
                    msk = seas == sname
                    if msk.any():
                        ax.scatter(x[msk], y[msk], s=10 if len(x) > 200 else 22, c=SEASON_COLOR[sname],
                                   marker=SEASON_MARKER[sname], alpha=0.55 if len(x) > 200 else 0.85,
                                   linewidths=0, zorder=3)
                lo = float(min(x.min(), y.min()))
                hi = float(max(x.max(), y.max()))
                pad = 0.04 * (hi - lo or 1)
                lim = (lo - pad, hi + pad)
                ax.plot(lim, lim, ls="--", lw=1, color=MUTED, zorder=2)
                m = metrics[(metrics.station == st) & (metrics.variable == var) & (metrics.pair == PAIR_LABEL[(a, b)])]
                if len(m):
                    r = m.iloc[0]
                    if np.isfinite(r["slope"]):
                        xx = np.array(lim)
                        ax.plot(xx, r["slope"] * xx + r["intercept"], lw=1.6, color=INK, zorder=4)
                    if t == "z":
                        txt = f"R² = {r['r2']:.2f}\nSpearman = {r['spearman']:.2f}\nn = {int(r['n'])}"
                    else:
                        u = "log10" if t == "log10" else v["unit"]
                        r2s = f"{r['r2']:.3f}" if r["r2"] > 0.99 else f"{r['r2']:.2f}"
                        txt = (f"R² = {r2s}\nbias = {r['bias']:+.2f} {u}\nRMSE = {r['rmse']:.2f} {u}\n"
                               f"n = {int(r['n'])}")
                    ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left", fontsize=8, color=INK,
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=GRID, alpha=0.9), zorder=5)
                ax.set_xlim(lim), ax.set_ylim(lim)
                ax.set_aspect("equal", adjustable="box")
                ax.set_xlabel(f"{SRC_LABEL[a]} [{unit}]", fontsize=8, color=INK)
                ax.set_ylabel(f"{SRC_LABEL[b]} [{unit}]", fontsize=8, color=INK)
                ax.set_title(f"{st}: {PAIR_LABEL[(a, b)]}", fontsize=9, color=INK, loc="left")
        handles = [Line2D([], [], ls="", marker=SEASON_MARKER[s], color=SEASON_COLOR[s], ms=6, label=SEASON_NAME_(s))
                   for s in SEASON_COLOR]
        handles += [Line2D([], [], ls="--", color=MUTED, label="1:1 line"),
                    Line2D([], [], ls="-", color=INK, lw=1.6, label="least-squares fit")]
        H = 3.9 * nr
        fig.legend(handles=handles, loc="upper center", ncol=6 if nc > 1 else 3, frameon=False, fontsize=8,
                   bbox_to_anchor=(0.5, 1 - 0.32 / H))
        note = {"log10": "Chlorophyll compared in log10 space (it is log-normally distributed).",
                "z": "Model nutrients are not usable as absolute values: both sides standardised (z), shape only."}.get(t, "")
        fig.suptitle(f"{v['title']}: daily means on in situ days. {note}", fontsize=10, color=INK, y=1 - 0.05 / H)
        fig.tight_layout(rect=(0, 0, 1, 1 - (0.75 if nc > 1 else 1.0) / H))
        p = FIG / f"scatter_{var}.png"
        fig.savefig(p, dpi=130, bbox_inches="tight")
        plt.close(fig)
        out.append(p)
    return out


def SEASON_NAME_(s):  # noqa: N802
    from metrics import SEASON_NAME
    return SEASON_NAME[s]


def taylor_figures(metrics: pd.DataFrame) -> list[Path]:
    """Normalised Taylor diagram per variable: in situ = reference (std 1, r 1); one marker per station and source."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    out = []
    m = metrics[metrics.pair.str.startswith("in situ")]
    for var, v in VARIABLES.items():
        mv = m[(m.variable == var) & m.r.notna()]
        if mv.empty:
            continue
        fig = plt.figure(figsize=(6.2, 5.2))
        ax = fig.add_subplot(111, projection="polar")
        smax = max(1.6, float(np.nanmax(mv.std_ratio)) * 1.15)
        ax.set_thetamin(0), ax.set_thetamax(90 if (mv.r >= 0).all() else 180)
        ax.set_rlim(0, smax)
        # correlation ticks on the arc
        rt = np.array([0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0])
        if (mv.r < 0).any():
            rt = np.concatenate([-rt[::-1][:-1], rt])
        ax.set_thetagrids(np.degrees(np.arccos(rt)), [f"{x:g}" for x in rt], fontsize=7, color=MUTED)
        ax.tick_params(axis="y", labelsize=7, colors=MUTED)
        ax.grid(color=GRID, lw=0.6)
        # centred RMS contours around the reference point (1, 0)
        th = np.linspace(0, np.pi, 300)
        rr = np.linspace(0, smax, 300)
        TH, RR = np.meshgrid(th, rr)
        crms = np.sqrt(1 + RR ** 2 - 2 * RR * np.cos(TH))
        cs = ax.contour(TH, RR, crms, levels=[0.25, 0.5, 0.75, 1.0, 1.25], colors=MUTED, linewidths=0.6,
                        linestyles=":")
        ax.clabel(cs, fontsize=6, fmt="%.2f")
        ax.plot([0], [1], marker="*", ms=13, color=INK, ls="")
        ax.annotate("in situ (reference)", (0, 1), xytext=(6, 6), textcoords="offset points", fontsize=7, color=INK)
        for _, r in mv.iterrows():
            src = "satellite" if "satellite" in r["pair"] else "model"
            ax.plot(np.arccos(np.clip(r["r"], -1, 1)), r["std_ratio"], marker=STATION_MARKER[r["station"]],
                    ms=8, color=SOURCE_COLOR[src], mec="white", mew=1, ls="")
        handles = [Line2D([], [], ls="", marker="s", color=SOURCE_COLOR[s], ms=7, label=s)
                   for s in SOURCE_COLOR if mv.pair.str.contains(s).any()]
        handles += [Line2D([], [], ls="", marker=STATION_MARKER[s], color=MUTED, ms=7, label=s)
                    for s in STATION_MARKER if (mv.station == s).any()]
        handles += [Line2D([], [], ls=":", color=MUTED, label="centred RMS difference (normalised)")]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=7, frameon=False)
        space = {"log10": " (log10 space)", "z": " (standardised)"}.get(v["transform"], "")
        ax.set_title(f"Taylor diagram: {v['title']}{space}\nradius = std / std(in situ), angle = correlation",
                     fontsize=9, color=INK, pad=14)
        fig.tight_layout()
        p = FIG / f"taylor_{var}.png"
        fig.savefig(p, dpi=130, bbox_inches="tight")
        plt.close(fig)
        out.append(p)
    return out


def nutrient_cycle_figure(data: dict) -> Path | None:
    """Monthly median seasonal cycle, each source standardised: bottles vs model (shape only)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    keys = [(st, var) for (st, var) in data if var in ("no3", "po4") and "model" in data[(st, var)]]
    if not keys:
        return None
    fig, axes = plt.subplots(1, len(keys), figsize=(4.6 * len(keys), 3.4), squeeze=False)
    for ax, (st, var) in zip(axes[0], keys):
        _style(ax)
        j = data[(st, var)][["insitu", "model"]].dropna()
        for col, color, lab in (("insitu", INK, "bottles"), ("model", SOURCE_COLOR["model"], "model")):
            z = transform(var, j[col])
            mon = z.groupby(z.index.month).median().reindex(range(1, 13))
            cnt = z.groupby(z.index.month).size().reindex(range(1, 13)).fillna(0)
            ax.plot(mon.index, mon.values, marker="o", ms=4, lw=2, color=color, label=lab)
        ax.set_ylim(-2.6, 2.6)
        ax.set_xticks(range(1, 13), [f"{m}\n{int(c)}" for m, c in zip("JFMAMJJASOND", cnt.values)])
        ax.set_ylabel("monthly median z (unitless)", fontsize=8)
        ax.set_title(f"{VARIABLES[var]['title']}, {st}\nnumbers under months = matched samples", fontsize=9,
                     color=INK, loc="left")
        ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    p = FIG / "nutrients_seasonal_shape.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def sst_3d(data: dict) -> Path | None:
    import plotly.graph_objects as go
    from metrics import SEASON_NAME, season_of
    frames = []
    for (st, var), df in data.items():
        if var == "sst" and {"insitu", "satellite", "model"} <= set(df):
            j = df[["insitu", "satellite", "model"]].dropna().assign(station=st)
            frames.append(j)
    if not frames:
        return None
    j = pd.concat(frames)
    j["season"] = season_of(j.index)
    fig = go.Figure()
    for s, col in SEASON_COLOR.items():
        d = j[j.season == s]
        fig.add_trace(go.Scatter3d(
            x=d.insitu, y=d.satellite, z=d.model, mode="markers", name=SEASON_NAME[s],
            marker=dict(size=2.5, color=col, opacity=0.7),
            text=[f"{st} {t.date()}" for st, t in zip(d.station, d.index)],
            hovertemplate="%{text}<br>in situ %{x:.2f} °C<br>satellite %{y:.2f} °C<br>model %{z:.2f} °C<extra></extra>"))
    lo, hi = float(j[["insitu", "satellite", "model"]].min().min()), float(j[["insitu", "satellite", "model"]].max().max())
    fig.add_trace(go.Scatter3d(x=[lo, hi], y=[lo, hi], z=[lo, hi], mode="lines", name="1:1:1 line",
                               line=dict(color=MUTED, width=4, dash="dash"), hoverinfo="skip"))
    ax = dict(range=[lo - 0.5, hi + 0.5])
    fig.update_layout(
        title="SST, three sources on the same days (all offshore buoys). Points on the grey diagonal = full agreement.",
        scene=dict(xaxis=dict(title="in situ buoy [°C]", **ax), yaxis=dict(title="satellite [°C]", **ax),
                   zaxis=dict(title="model [°C]", **ax), aspectmode="cube"),
        legend=dict(itemsizing="constant"), margin=dict(l=0, r=0, t=50, b=0), template="plotly_white")
    p = FIG / "sst_3d.html"
    fig.write_html(p, include_plotlyjs="cdn")
    return p


# ---------------------------------------------------------------------------------------------- report
def _fmt(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if isinstance(x, (float, np.floating)):
        return f"{x:.{nd}f}"
    return str(x)


def md_table(df: pd.DataFrame, cols: list[str], heads: list[str] | None = None, nd=2) -> str:
    heads = heads or cols
    lines = ["| " + " | ".join(heads) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(_fmt(r.get(c), nd) for c in cols) + " |")
    return "\n".join(lines)


def findings(var: str, metrics: pd.DataFrame) -> list[str]:
    """Rule-based plain-language lines per variable (numbers straight from the metric table)."""
    v = VARIABLES[var]
    m = metrics[(metrics.variable == var) & metrics.pair.str.startswith("in situ")]
    out = []
    for st in STATIONS:
        ms = m[m.station == st]
        if ms.empty:
            continue
        parts = []
        for _, r in ms.iterrows():
            src = r["pair"].replace("in situ vs ", "")
            if v["transform"] == "z":
                parts.append(f"{src}: seasonal shape R² {r['r2']:.2f}, Spearman {r['spearman']:.2f} (n = {int(r['n'])})")
            elif v["transform"] == "log10":
                parts.append(f"{src} reads {r['median_ratio']:.2f} x the buoy value (median ratio), R² {r['r2']:.2f} "
                             f"in log space (n = {int(r['n'])})")
            else:
                word = "warmer" if var == "sst" else "higher"
                word_neg = "colder" if var == "sst" else "lower"
                parts.append(f"{src} is {abs(r['bias']):.2f} {v['unit']} {word if r['bias'] > 0 else word_neg} on "
                             f"average, typical daily difference (RMSE) {r['rmse']:.2f} {v['unit']}, R² {r['r2']:.2f} "
                             f"(n = {int(r['n'])})")
        best = None
        if v["transform"] is None and len(ms) > 1:
            b = ms.sort_values("rmse").iloc[0]
            best = f" Closest to in situ: {b['pair'].replace('in situ vs ', '')} (lowest RMSE)."
        out.append(f"- **{st}**: " + "; ".join(parts) + "." + (best or ""))
    return out


INTERPRETATION_FILE = OUT / "interpretation.md"


def write_report(inv: pd.DataFrame, metrics: pd.DataFrame, seasonal: pd.DataFrame, figs: dict) -> Path:
    L = []
    L += ["# Source validation: in situ vs satellite vs model",
          "",
          "Romanian Black Sea shelf. Generated by `scripts/validation/compare_sources.py` on "
          f"{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} (re-run the script to refresh numbers and figures).",
          "",
          "First step before trend detection: how well do the three kinds of source agree where we can check them? "
          "Later steps: choose a reference source per variable with its uncertainty, then a power spectrum, then trends.",
          "",
          "## Method",
          "",
          "- **In situ drives the comparison.** Only trusted in situ data are used: offshore buoys EUXRoOB01-03 "
          "(GeoEcoMar ERDDAP, Feb 2024 onwards), the older offshore buoy EUXRo03 (Copernicus In Situ TAC, 2013-2023) "
          "and EMODnet Chemistry bottle samples (0-5 m, within 30 km) at the Constanta coast. The coastal buoys "
          "EUXRoCB0x and NIMH station 15480 are untrusted (repo rule) and left out.",
          "- **Satellite and model are fetched only where and when in situ exists**: at the station position, over the "
          "in situ period, then kept only on days with an in situ value. Variables without in situ data are not compared "
          "(waves: marinekit has no in situ wave source, so no wave validation here).",
          "- **Matching**: daily means on both sides (buoy records averaged per day by `marinekit.datahub`; model daily "
          "means; satellite daily L4 analyses), nearest valid grid cell or pixel; the distance is in the inventory. "
          "A point measurement against a 1-5 km satellite pixel or a 2.5 km model cell is not like for like: part of the "
          "difference is sub-grid variability, not error.",
          "- **In situ QC added here** (`marinekit.datahub` returns buoy data without these checks): (1) OB01-03 values "
          "before 2024-04-06 are dropped: the buoys then read about 21 °C and 35 mg/m³ chlorophyll while satellite and "
          "model give 8-10 °C and 0.3 mg/m³, so the instruments were not yet in the sea (inferred from the data, no "
          "deployment log seen); (2) a spike test against the buoy's own centred 15-day running median (SST 3 °C, "
          "salinity 2 PSU, O2 2.5 mg/L, chlorophyll a factor 5; thresholds OURS); (3) buoy surface O2 kept only when its "
          "saturation (own temperature, S = 18) is 60-150 % (OURS). None of the checks uses satellite or model values, "
          "so they do not pull the comparison towards them. Removed counts are in the inventory.",
          "- **Data access**: everything through `marinekit.datahub.get_series` (read-only). Bottle temperature, salinity "
          "and O2 at the coast use the module's bottle reader (`_fetch_bottles`), because the source register lists "
          "bottles only for nutrients. Bottle O2 is converted from umol/L to mg/L (x 0.032); the unit is inferred from the "
          "magnitude of the values.",
          "- **Metrics per pair**: n, bias (second source minus first), RMSE, unbiased RMSE (RMSE with the mean bias "
          "removed), Pearson r and R², slope and intercept of the least-squares fit of the second source on the first; "
          "the same split by season (DJF, MAM, JJA, SON) in `seasonal_metrics.md`.",
          "- **Chlorophyll** is compared in log10 space (log-normal, standard practice for ocean colour); its table also "
          "gives the median ratio (other / in situ) in linear units.",
          "- **Nutrients** (nitrate, phosphate): the repo rule says model nutrients are not usable as absolute values, so "
          "both sides are standardised (z-scores) and only the shape (timing, seasonal cycle, ranking) is compared.",
          "",
          "### Why R² is not enough",
          "",
          "R² measures how well the two sources move together (correlation), not whether they agree on the 1:1 line. "
          "A source that is always 1 °C too warm, or that doubles every value, can still have R² = 1. That is why every "
          "panel also gives the bias (systematic offset), the RMSE (typical size of the daily difference) and the fitted "
          "slope (1 = same amplitude). For SST most of R² comes from the shared seasonal cycle; it says little about "
          "day-to-day skill.",
          ""]
    # inventory
    L += ["## Inventory", "",
          "One row per station, variable and source. Gap share = share of days without a value between the first and "
          "last date of that source (for satellite and model: over the in situ period). Overlap = days with both this "
          "source and in situ. Distance = from the station to the grid cell or pixel used (km).", ""]
    inv2 = inv.copy()
    inv2["overlap"] = inv2.apply(lambda r: f"{r.get('overlap_start')} to {r.get('overlap_end')}"
                                 if pd.notna(r.get("overlap_start")) else "-", axis=1)
    L += [md_table(inv2, ["station", "variable", "source", "native", "start", "end", "n_days", "gap_share", "overlap",
                          "n_matched", "distance_km", "qc_removed", "status"],
                   ["station", "variable", "source", "native interval", "start", "end", "days", "gap share", "overlap",
                    "matched days", "distance km", "in situ QC removed", "status"]), ""]
    # per variable
    L += ["## Results by variable", ""]
    interp = {}
    if INTERPRETATION_FILE.exists():
        cur = None
        for line in INTERPRETATION_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                cur = line[3:].strip()
                interp[cur] = []
            elif cur:
                interp[cur].append(line)
    for var, v in VARIABLES.items():
        mv = metrics[metrics.variable == var]
        if mv.empty:
            continue
        unit = {"log10": "log10 " + v["unit"], "z": "z (unitless)"}.get(v["transform"], v["unit"])
        L += [f"### {v['title']}", ""]
        if var in interp:
            L += [ln for ln in interp[var]] + [""]
        L += ["Numbers from the table (generated):", ""] + findings(var, metrics) + [""]
        cols = ["station", "pair", "start", "end", "n", "bias", "rmse", "ubrmse", "r", "r2", "r2_anom", "slope",
                "intercept"]
        heads = ["station", "pair", "from", "to", "n", f"bias [{unit}]", f"RMSE [{unit}]", f"ubRMSE [{unit}]", "r",
                 "R²", "R² anomalies", "slope", "intercept"]
        if v["transform"] == "log10":
            cols.append("median_ratio"), heads.append("median ratio (linear)")
        if v["transform"] == "z":
            cols = ["station", "pair", "start", "end", "n", "r", "r2", "spearman", "slope"]
            heads = ["station", "pair", "from", "to", "n", "r", "R²", "Spearman", "slope"]
        L += [md_table(mv, cols, heads), ""]
        for p in figs.get(var, []):
            L += [f"![{v['title']}: {p.stem.replace('_', ' ')}](figures/{p.name})", ""]
        if var == "sst" and figs.get("sst_3d"):
            L += ["Optional interactive view: [3D scatter of in situ, satellite and model SST](figures/sst_3d.html) "
                  "(open in a browser; rotate with the mouse). The 2D pairs plus the Taylor diagram remain the main view: "
                  "a 3D cloud is hard to read on a static slide and hides which pair disagrees.", ""]
        if var in ("no3", "po4") and figs.get("nutrients"):
            L += [f"![Nutrient seasonal shape](figures/{figs['nutrients'].name})", ""]
    if "general" in interp:
        L += ["## Overall reading", ""] + interp["general"] + [""]
    if "limits" in interp:
        L += ["## Limits", ""] + interp["limits"] + [""]
    L += ["## Files", "",
          "- `inventory.csv`, `metrics.csv`, `metrics_seasonal.csv`: the tables above, full precision.",
          "- `seasonal_metrics.md`: metrics split by season.",
          "- `matched_daily.csv`: the matched daily values (station, variable, date, in situ, satellite, model), input for "
          "the next steps (reference source, uncertainty, spectrum, trends).",
          "- `figures/`: scatter rows (`scatter_<var>.png`), Taylor diagrams (`taylor_<var>.png`), nutrient seasonal "
          "shape, interactive `sst_3d.html`.",
          "- `interpretation.md`: the hand-written reading included above (kept separate so the script can re-run).",
          "",
          "Needs `matplotlib` in the venv (not yet in `requirements.txt`: add `matplotlib>=3.9`).", ""]
    p = OUT / "README.md"
    p.write_text("\n".join(L), encoding="utf-8")
    # seasonal
    S = ["# Seasonal metrics", "", "Same pairs as README.md, split by season (DJF winter, MAM spring, JJA summer, "
         "SON autumn). Bias = second source minus first. Chlorophyll in log10 space; nutrients standardised.", ""]
    for var, v in VARIABLES.items():
        sv = seasonal[seasonal.variable == var]
        if sv.empty:
            continue
        S += [f"## {v['title']}", "",
              md_table(sv, ["station", "pair", "season", "n", "bias", "rmse", "ubrmse", "r2", "slope"],
                       ["station", "pair", "season", "n", "bias", "RMSE", "ubRMSE", "R²", "slope"]), ""]
    (OUT / "seasonal_metrics.md").write_text("\n".join(S), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="read cached files only")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    data, inv = collect(args.offline)
    inv.to_csv(OUT / "inventory.csv", index=False)
    matched = []
    for (st, var), df in data.items():
        d = df.copy()
        d.index.name = "date"
        matched.append(d.reset_index().assign(station=st, variable=var))
    if matched:
        mm = pd.concat(matched)
        cols = ["station", "variable", "date", "insitu", "satellite", "model"]
        mm.reindex(columns=cols).to_csv(OUT / "matched_daily.csv", index=False, float_format="%.4f")
    metrics, seasonal = metric_tables(data)
    metrics.to_csv(OUT / "metrics.csv", index=False)
    seasonal.to_csv(OUT / "metrics_seasonal.csv", index=False)
    log("figures")
    figs: dict = {}
    for p in scatter_figures(data, metrics):
        figs.setdefault(p.stem.replace("scatter_", ""), []).append(p)
    for p in taylor_figures(metrics):
        figs.setdefault(p.stem.replace("taylor_", ""), []).append(p)
    figs["nutrients"] = nutrient_cycle_figure(data)
    figs["sst_3d"] = sst_3d(data)
    p = write_report(inv, metrics, seasonal, figs)
    log(f"report: {p}")


if __name__ == "__main__":
    main()
