"""Power spectra of the marine time series: which cycles exist before trend detection.

    .venv\\Scripts\\python.exe scripts/spectra/psd.py           # cache only (MARINEKIT_OFFLINE=1 is always set)

Second analysis step (after scripts/validation/compare_sources.py, before trends). For each trusted offshore buoy and
variable it overlays three spectra on one chart: buoy (in situ), satellite and model at the same point and period.

Method (agreed with the user):
  * Gap-free series (satellite L4, model daily means): Welch, Hann window, 50 % overlap.
  * Gappy series (buoy daily means, 10-56 % missing days): Lomb-Scargle on the same segments, the same Hann taper and
    the same frequency grid (k / segment length), averaged over segments ("WOSA Lomb-Scargle", as in REDFIT,
    Schulz and Mudelsee 2002). Both are scaled as one-sided power spectral density, so the curves are comparable.
  * Two spectra per series: "full" (linear trend removed, segment = up to 3 years, resolves the annual cycle) and
    "anomalies" (trend + annual + semi-annual harmonics removed, segment = 365 days, more averaging for 2-180 days).
  * Significance: AR(1) red-noise background fitted to the anomalies (lag-1 autocorrelation from consecutive days,
    variance of the anomalies); a peak is significant when it is a local maximum above the 95 % chi-square level of
    that background with the Welch/WOSA equivalent degrees of freedom.

Real data are read from the cache through the validation step's own loading and QC (imported, not edited). SYNTHETIC
series (scripts/spectra/synthetic.py) cover the long-period and sub-daily parts and serve as a method check.

Outputs in docs/indicators/spectra/: README.md, peaks.csv, band_variance.csv, method_check.csv, figures/*.png.
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal, stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "indicators" / "spectra"
FIG = OUT / "figures"

ANNUAL_D = 365.25
SEMIANNUAL_D = ANNUAL_D / 2
HANN_C = 0.167          # correlation between 50 %-overlapping Hann-windowed segments (Percival and Walden 1993)
P_SIG = 0.95

# Okabe-Ito, same source colours as the validation figures
COL = {"insitu": "#000000", "satellite": "#0072B2", "model": "#D55E00", "synthetic": "#009E73",
       "synthetic_gaps": "#CC79A7"}
SRC_LABEL = {"insitu": "buoy (in situ)", "satellite": "satellite", "model": "model"}
INK, MUTED, GRID, BAND = "#1f2328", "#59636e", "#d8dee4", "#F0E442"


# ============================================================================================== spectral core
def wosa_dof(k: int, c: float = HANN_C) -> float:
    """Equivalent degrees of freedom of a Welch / WOSA average of k Hann segments with 50 % overlap."""
    if k <= 1:
        return 2.0
    return 2.0 * k / (1.0 + 2.0 * c ** 2 * (1.0 - 1.0 / k))


def fit_remove(t: np.ndarray, y: np.ndarray, periods: tuple = ()) -> np.ndarray:
    """Least-squares removal of mean + linear trend (+ harmonics of the given periods, same time unit as t)."""
    cols = [np.ones_like(t), t - t.mean()]
    for p in periods:
        cols += [np.cos(2 * np.pi * t / p), np.sin(2 * np.pi * t / p)]
    a = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(a, y, rcond=None)
    return y - a @ coef


def ar1_params(t: np.ndarray, x: np.ndarray, step: float) -> tuple[float, float]:
    """Lag-1 autocorrelation (pairs exactly one step apart, gaps allowed) and variance of x."""
    x = x - x.mean()
    d = np.diff(t)
    ok = np.abs(d - step) < 0.01 * step
    a, b = x[:-1][ok], x[1:][ok]
    rho = float(np.sum(a * b) / np.sqrt(np.sum(a * a) * np.sum(b * b))) if ok.sum() > 10 else 0.0
    return float(np.clip(rho, 0.0, 0.999)), float(np.var(x))


def ar1_spectrum(f: np.ndarray, rho: float, var: float, fs: float) -> np.ndarray:
    """One-sided PSD of an AR(1) process (integrates to var over 0..fs/2)."""
    return 2.0 * var * (1 - rho ** 2) / (fs * (1 - 2 * rho * np.cos(2 * np.pi * f / fs) + rho ** 2))


def robust_ar1_background(f: np.ndarray, psd: np.ndarray, dof: float, fs: float,
                          half_width_dec: float = 0.15, min_bins: int = 5,
                          fit_ar1: bool = True) -> tuple[np.ndarray, float]:
    """Robust red-noise background (Mann and Lees 1996): running median of the PSD over +-half_width_dec decades of
    frequency (at least min_bins bins), converted from median to mean of a chi-square(dof) variable, then an AR(1)
    spectrum fitted to it by least squares in log space (grid search on rho, closed-form level). Spectral lines barely
    move a median, so the background follows the continuum, not the peaks. Returns (background, rho_fit).
    fit_ar1=False keeps the median-smoothed continuum itself (no AR(1) shape): used for the anomaly spectra, whose
    continuum is not AR(1)-shaped (steeper than AR(1) at 2-5 days), so a fitted AR(1) would flag broad stretches
    of continuum as peaks. It detects sharp peaks only, not broad bumps."""
    lf = np.log10(f)
    med = np.empty_like(psd)
    for i in range(len(f)):
        m = np.abs(lf - lf[i]) <= half_width_dec
        if m.sum() < min_bins:
            j = np.argsort(np.abs(lf - lf[i]))[:min_bins]
            m = np.zeros_like(m)
            m[j] = True
        med[i] = np.median(psd[m])
    smooth = med * dof / stats.chi2.ppf(0.5, dof)
    if not fit_ar1:
        return smooth, float("nan")
    ly = np.log(smooth)
    best = (np.inf, 0.0, 0.0)
    for rho in np.linspace(0.0, 0.995, 400):
        shape = np.log(ar1_spectrum(f, rho, 1.0, fs))
        c = np.mean(ly - shape)
        err = np.sum((ly - shape - c) ** 2)
        if err < best[0]:
            best = (err, rho, c)
    _, rho, c = best
    return ar1_spectrum(f, rho, 1.0, fs) * np.exp(c), float(rho)


def ls_power(t: np.ndarray, y: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Classical Lomb-Scargle power (Scargle 1982), un-normalised: about |sum y exp(-i w t)|^2 / n on a regular grid."""
    w = 2 * np.pi * f[:, None]
    tau = np.arctan2(np.sum(np.sin(2 * w * t), 1), np.sum(np.cos(2 * w * t), 1)) / (2 * w[:, 0])
    arg = w * (t[None, :] - tau[:, None])
    c, s = np.cos(arg), np.sin(arg)
    return 0.5 * ((c @ y) ** 2 / np.sum(c * c, 1) + (s @ y) ** 2 / np.sum(s * s, 1))


def welch_psd(y: np.ndarray, step: float, seg: float) -> dict:
    """Welch PSD of a regular, gap-free series. step and seg in days, frequency in cycles per day."""
    fs = 1.0 / step
    nper = int(min(len(y), round(seg / step)))
    f, p = signal.welch(y, fs=fs, window="hann", nperseg=nper, noverlap=nper // 2, detrend="constant",
                        scaling="density")
    k = 1 + (len(y) - nper) // (nper // 2)
    return dict(freq=f[1:], psd=p[1:], n_seg=int(k), dof=wosa_dof(k), seg_days=nper * step, method="Welch")


def lomb_wosa_psd(t: np.ndarray, y: np.ndarray, step: float, seg: float, min_cover: float = 0.4,
                  prewhiten: bool = True) -> dict:
    """Lomb-Scargle PSD for a gappy series: Hann-tapered 50 %-overlapping segments of length seg (days), frequency grid
    k / seg (the Welch grid), each segment scaled like Welch's density and then averaged. Segments with fewer than
    min_cover of their expected samples are skipped.

    prewhiten: gaps let the strong low-frequency power leak to short periods and lift the floor there. The series is
    first prewhitened with an AR(1) filter z_t = y_t - rho y_(t-step), on samples whose previous step exists, and the
    spectrum of z is then recoloured by 1 / |1 - rho exp(-i 2 pi f step)|^2 (Percival and Walden 1993, ch. 6)."""
    fs = 1.0 / step
    rho = 0.0
    if prewhiten:
        rho, _ = ar1_params(t, y, step)
        ok = np.abs(np.diff(t) - step) < 0.01 * step
        t, y = t[1:][ok], y[1:][ok] - rho * y[:-1][ok]
    out = _lomb_wosa(t, y, step, seg, min_cover)
    if prewhiten:
        out["psd"] = out["psd"] / (1 - 2 * rho * np.cos(2 * np.pi * out["freq"] / fs) + rho ** 2)
        out["prewhiten_rho"] = rho
    return out


def _lomb_wosa(t, y, step, seg, min_cover) -> dict:
    fs = 1.0 / step
    seg = min(seg, t[-1] - t[0] + step)
    f = np.arange(1, int(np.floor(seg * fs / 2)) + 1) / seg
    acc, k, start = np.zeros_like(f), 0, t[0]
    while start + seg <= t[-1] + step * 1.001:
        m = (t >= start) & (t < start + seg)
        if m.sum() >= min_cover * seg / step:
            tt = t[m] - start
            w = 0.5 - 0.5 * np.cos(2 * np.pi * (tt + step / 2) / seg)
            z = w * (y[m] - y[m].mean())
            acc += 2.0 * ls_power(tt, z, f) * m.sum() / (fs * np.sum(w * w))
            k += 1
        start += seg / 2
    if k == 0:
        raise ValueError("no segment with enough data")
    return dict(freq=f, psd=acc / k, n_seg=k, dof=wosa_dof(k), seg_days=seg, method="Lomb-Scargle")


def is_regular(t: np.ndarray, step: float) -> bool:
    return len(t) > 1 and np.allclose(np.diff(t), step, rtol=1e-3)


def series_time(s: pd.Series) -> np.ndarray:
    idx = pd.DatetimeIndex(s.index)
    return ((idx - idx[0]) / pd.Timedelta(days=1)).to_numpy(float)


def spectrum(s: pd.Series, step: float = 1.0, seg: float = 1096.0, anomalies: bool = False,
             method: str = "auto", band: tuple[float, float] | None = None, background: str = "auto") -> dict:
    """PSD of one series (DatetimeIndex, step in days). method auto: Welch when gap-free, else Lomb-Scargle.
    band = (shortest, longest) period in days where peaks are reported (default 2 steps to half a segment).
    Returns freq (cpd), psd, background (robust AR(1)), level (95 %), dof, n_seg, method, rho_lag1 (from the data),
    rho_fit (of the background), var, peaks (DataFrame), n_tested (local maxima tested in the band)."""
    s = s.dropna().astype(float)
    s = s[~s.index.duplicated()].sort_index()
    t, y = series_time(s), s.to_numpy()
    harm = (ANNUAL_D, SEMIANNUAL_D) if (t[-1] - t[0]) >= 300 else ()
    anom = fit_remove(t, y, harm)
    r = anom if anomalies else fit_remove(t, y)
    if method == "auto":
        method = "welch" if is_regular(t, step) else "lomb"
    if method == "welch":
        if not is_regular(t, step):
            raise ValueError("Welch needs a gap-free regular series")
        out = welch_psd(r, step, seg)
    else:
        out = lomb_wosa_psd(t, r, step, seg)
    rho, var = ar1_params(t, anom, step)
    fs = 1.0 / step
    if background == "auto":
        background = "median" if anomalies else "ar1"
    bg, rho_fit = robust_ar1_background(out["freq"], out["psd"], out["dof"], fs, fit_ar1=(background == "ar1"))
    out["background_kind"] = "robust AR(1) (Mann-Lees)" if background == "ar1" else "running-median continuum"
    out.update(background=bg, level=bg * stats.chi2.ppf(P_SIG, out["dof"]) / out["dof"], rho_lag1=rho,
               rho_fit=rho_fit, var=var, variance_total=float(np.var(r)), n=len(s), gap_share=gap_share(t, step),
               step=step, band=band or (2 * step, out["seg_days"] / 2))
    out["peaks"], out["n_tested"] = find_peaks(out)
    return out


def gap_share(t: np.ndarray, step: float) -> float:
    expected = round((t[-1] - t[0]) / step) + 1
    return float(1 - len(t) / expected)


def find_peaks(sp: dict) -> tuple[pd.DataFrame, int]:
    """Local maxima above the 95 % red-noise level, inside sp['band'] (periods, days). The period is refined by a
    parabola through the log-PSD of the peak and its two neighbours. Also returns how many frequency bins were tested
    (about 5 % of bins exceed the level by chance; neighbouring exceedances merge into one peak)."""
    f, p, lev, bg = sp["freq"], sp["psd"], sp["level"], sp["background"]
    lo, hi = sp["band"]
    hi = min(hi, sp["seg_days"] / 2)
    rows = []
    per_all = 1 / f
    n_tested = int(np.sum((per_all >= lo) & (per_all <= hi)))     # frequency bins tested (5 % exceed by chance)
    for i in range(1, len(f) - 1):
        per = 1 / f[i]
        if not (p[i] >= p[i - 1] and p[i] >= p[i + 1]) or per < lo or per > hi:
            continue
        if p[i] <= lev[i]:
            continue
        a, b, c = np.log(p[i - 1]), np.log(p[i]), np.log(p[i + 1])
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den != 0 else 0.0
        fr = f[i] + np.clip(off, -0.5, 0.5) * (f[1] - f[0])
        rows.append(dict(period_d=1 / fr, psd=p[i], background=bg[i], ratio=p[i] / bg[i], level_ratio=p[i] / lev[i]))
    return pd.DataFrame(rows, columns=["period_d", "psd", "background", "ratio", "level_ratio"]), n_tested


def band_of(period_d: float) -> str:
    """Plain name of the cycle a period belongs to (band limits are OURS, for labelling only)."""
    h = period_d * 24
    for lo, hi, name in [(11.9, 12.1, "semi-diurnal S2 / diurnal harmonic"), (12.2, 12.7, "semi-diurnal tide M2"),
                         (16.3, 18.3, "inertial"), (22.5, 25.5, "diurnal")]:
        if lo <= h <= hi:
            return name
    for lo, hi, name in [(1000, 1e9, "multi-year"), (300, 450, "annual"), (160, 205, "semi-annual"),
                         (85, 135, "3-4 month (seasonal harmonics)"), (10, 85, "intraseasonal"), (3, 10, "synoptic"),
                         (1.05, 3, "2-3 day")]:
        if lo <= period_d < hi:
            return name
    if period_d < 1:
        return "other sub-daily"
    return "other"


BANDS = [("seasonal (> 120 d)", 120, 1e9), ("intraseasonal (10-120 d)", 10, 120), ("synoptic (3-10 d)", 3, 10),
         ("short (2-3 d)", 2, 3)]


def n_above(sp: dict, lo: float | None = None, hi: float | None = None) -> int:
    """Number of frequency bins inside the reporting band (or lo-hi days) whose PSD is above the 95 % level."""
    per = 1 / sp["freq"]
    blo, bhi = sp["band"]
    lo, hi = (blo if lo is None else lo), min(bhi if hi is None else hi, sp["seg_days"] / 2)
    m = (per >= lo) & (per <= hi)
    return int(np.sum(sp["psd"][m] > sp["level"][m]))


def consistency_test(res: dict, kind: str = "anomalies", lo: float = 2.0, hi: float = 85.0) -> pd.DataFrame:
    """Per frequency bin (shared grid), how many of the real spectra exceed their 95 % level, and the binomial
    probability of that count under the null (5 % each, spectra treated as independent; they are not, since sources
    at one station share the weather, so the test is liberal). Bonferroni over the bins tested."""
    sps = [sp for k, sp in res.items() if k[3] == kind]
    f = sps[0]["freq"]
    sps = [sp for sp in sps if len(sp["freq"]) == len(f) and np.allclose(sp["freq"], f)]
    per = 1 / f
    m = (per >= lo) & (per <= hi)
    exc = np.array([sp["psd"][m] > sp["level"][m] for sp in sps])
    n = len(sps)
    cnt = exc.sum(0)
    pv = stats.binom.sf(cnt - 1, n, 0.05)
    return pd.DataFrame(dict(period_d=per[m], n_spectra=n, n_exceed=cnt, share=cnt / n, p=pv,
                             p_bonferroni=np.minimum(pv * m.sum(), 1.0)))


def combined_bands(full: dict, anom: dict) -> dict:
    """Seasonal band from the full spectrum, shorter bands from the anomaly spectrum (better averaged)."""
    a, b = band_variance(full), band_variance(anom)
    return {name: (a if lo >= 120 else b)[name] for name, lo, _ in BANDS}


def band_variance(sp: dict) -> dict:
    """Variance (units^2) in each period band, by integrating the PSD over the frequency bins."""
    f, p = sp["freq"], sp["psd"]
    df = f[1] - f[0]
    per = 1 / f
    return {name: float(np.sum(p[(per >= lo) & (per < hi)]) * df) for name, lo, hi in BANDS}


# ============================================================================================== real data
VARS = ["sst", "chl", "sal", "o2"]
STATIONS = ["EUXRo03", "EUXRoOB01", "EUXRoOB02", "EUXRoOB03"]
FULL_SEG, ANOM_SEG = 1096.0, 365.0
# Each spectrum reports peaks only in the band it resolves best: the full spectrum (long segments, few dof) for
# seasonal periods, the anomaly spectrum (365-day segments, more dof) for 2 days to 4 months.
FULL_BAND, ANOM_BAND = (120.0, 1e9), (2.0, 120.0)
TESTS: list[dict] = []
YLAB = {"sst": "(°C)²", "chl": "(log10 mg/m³)²", "sal": "(PSU)²", "o2": "(mg/L)²"}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def regularise(s: pd.Series, max_fill: int = 5, max_share: float = 0.01) -> tuple[pd.Series, str]:
    """Daily series: fill short holes (<= max_fill days, <= 1 % of days) by linear interpolation so Welch applies;
    otherwise leave the gaps (Lomb-Scargle)."""
    s = s.groupby(pd.DatetimeIndex(s.index).normalize()).mean()
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))
    miss = full.isna()
    if not miss.any():
        return full, "gap-free"
    runs = miss.groupby((~miss).cumsum()).sum()
    if miss.mean() <= max_share and runs.max() <= max_fill:
        return full.interpolate(limit_area="inside"), f"{int(miss.sum())} missing days interpolated"
    return s, f"{miss.mean():.0%} missing days"


def collect() -> dict:
    """{(station, var): {source: Series}} from the cache, via the validation step's loaders and QC."""
    os.environ["MARINEKIT_OFFLINE"] = "1"
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts" / "validation"))
    import compare_sources as cs  # noqa: E402  (read-only reuse: STATIONS, VARIABLES, fetch_insitu, fetch_other)
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
    return data, cs


def analyse_real(data: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    res, peaks, bands = {}, [], []
    for (st, var), d in data.items():
        span = (d["insitu"].index.max() - d["insitu"].index.min()).days + 1
        seg_full = min(FULL_SEG, float(span))
        for src, s in d.items():
            s2, note = regularise(s)
            for kind, seg, anom, band in [("full", seg_full, False, FULL_BAND), ("anomalies", ANOM_SEG, True, ANOM_BAND)]:
                try:
                    sp = spectrum(s2, 1.0, seg, anomalies=anom, band=band)
                except Exception as ex:  # noqa: BLE001
                    log(f"{st} {var} {src} {kind}: {ex}")
                    continue
                sp["note"] = note
                res[(st, var, src, kind)] = sp
                TESTS.append(dict(station=st, variable=var, source=src, spectrum=kind, method=sp["method"],
                                  n_tested=sp["n_tested"], n_significant=len(sp["peaks"]),
                                  bins_above_95=n_above(sp), share_above_95=round(n_above(sp) / max(sp["n_tested"], 1), 3),
                                  expected_by_chance=round(0.05 * sp["n_tested"], 1), dof=round(sp["dof"], 1),
                                  rho_lag1=round(sp["rho_lag1"], 3), rho_background=round(sp["rho_fit"], 3)))
                pk = sp["peaks"].sort_values("ratio", ascending=False)
                for _, r in pk.iterrows():
                    peaks.append(dict(station=st, variable=var, source=src, spectrum=kind, method=sp["method"],
                                      period_d=round(r.period_d, 2), cycle=band_of(r.period_d),
                                      psd_over_background=round(r.ratio, 1),
                                      psd_over_95_level=round(r.level_ratio, 2), dof=round(sp["dof"], 1),
                                      segments=sp["n_seg"], seg_days=round(sp["seg_days"]), data_note=note))
            if (st, var, src, "full") in res and (st, var, src, "anomalies") in res:
                full_sp, an_sp = res[(st, var, src, "full")], res[(st, var, src, "anomalies")]
                bands.append(dict(station=st, variable=var, source=src, method=full_sp["method"],
                                  variance_total=full_sp["variance_total"], **combined_bands(full_sp, an_sp)))
            # gap-effect check: the model/satellite sampled on buoy days only, through Lomb-Scargle
            if src != "insitu" and (st, var, src, "full") in res:
                on = s2.reindex(d["insitu"].index).dropna()
                try:
                    a = spectrum(on, 1.0, seg_full, method="lomb")
                    b = spectrum(on, 1.0, ANOM_SEG, anomalies=True, method="lomb")
                    bands.append(dict(station=st, variable=var, source=f"{src} on buoy days", method="Lomb-Scargle",
                                      variance_total=a["variance_total"], **combined_bands(a, b)))
                except Exception:  # noqa: BLE001
                    pass
    return res, pd.DataFrame(peaks), pd.DataFrame(bands)


SRC_NAME = {"insitu": "in situ", "satellite": "satellite", "model": "model"}


def _peak_rows(sp: dict, base: dict, kind: str) -> list[dict]:
    meth = "welch" if sp["method"] == "Welch" else "lomb-scargle"
    rows = []
    for r in sp["peaks"].itertuples():
        rows.append(dict(base, method=meth, period_days=float(r.period_d), power=float(r.psd), significant_95=True,
                         spectrum=kind, cycle=band_of(r.period_d), psd_over_background=round(r.ratio, 3),
                         psd_over_95_level=round(r.level_ratio, 3), dof=round(sp["dof"], 1)))
    if kind == "full":
        f, p = sp["freq"], sp["psd"]
        per = 1 / f
        sig = sp["peaks"].period_d.to_numpy()
        for target in (ANNUAL_D, SEMIANNUAL_D):
            if target > sp["seg_days"] / 2 or np.any(np.abs(np.log(sig / target)) < 0.15):
                continue
            # local maximum nearest the target period (within +-15 %); significant_95 = above the 95 % level
            cand = [i for i in range(1, len(f) - 1) if p[i] >= p[i - 1] and p[i] >= p[i + 1]
                    and abs(np.log(per[i] / target)) < 0.15]
            if not cand:   # no local maximum (e.g. a monotonic rise): take the bin nearest the target period
                cand = [int(np.argmin(np.abs(np.log(per / target))))]
            i = min(cand, key=lambda i: abs(np.log(per[i] / target)))
            rows.append(dict(base, method=meth, period_days=float(per[i]), power=float(p[i]),
                             significant_95=bool(p[i] > sp["level"][i]),
                             spectrum=kind, cycle=band_of(per[i]),
                             psd_over_background=round(p[i] / sp["background"][i], 3),
                             psd_over_95_level=round(p[i] / sp["level"][i], 3), dof=round(sp["dof"], 1)))
    return rows


def peak_table(res: dict, mc: dict) -> pd.DataFrame:
    """Machine-readable peak table (peaks.csv) for the next steps (e.g. picking cycles for a harmonic fit)."""
    rows = []
    for (st, var, src, kind), sp in res.items():
        rows += _peak_rows(sp, dict(variable=var, source=SRC_NAME[src], station=st, synthetic=False), kind)
    syn = [("SYNTHETIC_40yr_daily", mc["long"]["sp"], "full"),
           ("SYNTHETIC_hourly_gapfree", mc["hourly"]["sp_full"], "anomalies"),
           ("SYNTHETIC_hourly_gaps", mc["hourly"]["sp_gaps"], "anomalies")]
    for name, sp, kind in syn:
        rows += _peak_rows(sp, dict(variable="sst", source="synthetic", station=name, synthetic=True), kind)
    df = pd.DataFrame(rows)
    df["rank"] = pd.array([pd.NA] * len(df), dtype="Int64")
    sig = df[df.significant_95]
    df.loc[sig.index, "rank"] = (sig.groupby(["variable", "source", "station"]).power
                                 .rank(ascending=False, method="first").astype("Int64"))
    cols = ["variable", "source", "station", "synthetic", "method", "period_days", "power", "significant_95", "rank",
            "spectrum", "cycle", "psd_over_background", "psd_over_95_level", "dof"]
    df = df[cols].sort_values(["synthetic", "station", "variable", "source", "rank"], na_position="last")
    df["period_days"] = df.period_days.round(4)
    df["power"] = df.power.map(lambda x: float(f"{x:.5g}"))
    return df.reset_index(drop=True)


# ============================================================================================== synthetic
def method_check() -> tuple[dict, pd.DataFrame]:
    """Run the spectra on the SYNTHETIC series and check that the planted periods come back."""
    sys.path.insert(0, str(HERE))
    from synthetic import synthetic_hourly, synthetic_long_daily

    out, rows = {}, []
    long = synthetic_long_daily()
    s = long["sst"]
    sp = spectrum(s, 1.0, 20 * ANNUAL_D, band=FULL_BAND)
    out["long"] = dict(series=long, sp=sp)
    p = long.attrs["planted"]
    for name, per in [("annual", p["annual_period_d"]), ("semi-annual", p["semiannual_period_d"]),
                      ("6-year oscillation", p["multiyear_period_d"])]:
        rows.append(_recover("SYNTHETIC 40-year daily", "Welch", name, per, sp, "d"))
    # trend: OLS slope of the raw series (for the next step; the spectrum itself is computed after detrending)
    t = series_time(s) / ANNUAL_D
    slope = np.polyfit(t, s.to_numpy(), 1)[0]
    rows.append(dict(series="SYNTHETIC 40-year daily", method="OLS", planted="linear trend",
                     planted_value=f"{p['trend_per_year'] * 10:.2f} °C/decade",
                     recovered_value=f"{slope * 10:.2f} °C/decade",
                     rel_error_pct=round(100 * abs(slope - p["trend_per_year"]) / p["trend_per_year"], 1),
                     significant="n/a", ok=bool(abs(slope - p["trend_per_year"]) < 0.25 * p["trend_per_year"])))

    hg, hf = synthetic_hourly(gaps=True), synthetic_hourly(gaps=False)
    sp_f = spectrum(hf["sst"], 1 / 24, 30.0, anomalies=True, method="welch")
    sp_g = spectrum(hg["sst"], 1 / 24, 30.0, anomalies=True, method="lomb")
    out["hourly"] = dict(series=hg, series_full=hf, sp_full=sp_f, sp_gaps=sp_g)
    ph = hg.attrs["planted"]
    for lab, sp_, meth in [("SYNTHETIC hourly, gap-free", sp_f, "Welch"),
                           (f"SYNTHETIC hourly, {ph['gap_share']:.0%} gaps", sp_g, "Lomb-Scargle")]:
        for name, per_h in [("diurnal 24 h", ph["diurnal_period_h"]), ("inertial 44 N", ph["inertial_period_h"]),
                            ("M2 tide", ph["m2_period_h"])]:
            rows.append(_recover(lab, meth, name, per_h / 24, sp_, "h"))
    # same method on both: Welch vs Lomb-Scargle on the gap-free hourly series (variance in the 2 h - 15 d range)
    sp_l = spectrum(hf["sst"], 1 / 24, 30.0, anomalies=True, method="lomb")
    ratio = float(np.median(sp_l["psd"] / sp_f["psd"]))
    rows.append(dict(series="SYNTHETIC hourly, gap-free", method="Lomb-Scargle vs Welch", planted="same spectrum",
                     planted_value="ratio 1", recovered_value=f"median ratio {ratio:.3f}",
                     rel_error_pct=round(100 * abs(ratio - 1), 1), significant="n/a", ok=bool(abs(ratio - 1) < 0.1)))
    return out, pd.DataFrame(rows)


def _recover(series: str, method: str, name: str, per_d: float, sp: dict, unit: str) -> dict:
    pk = sp["peaks"]
    fmt = (lambda d: f"{d * 24:.2f} h") if unit == "h" else (lambda d: f"{d:.1f} d")
    if len(pk):
        j = (np.log(pk.period_d) - np.log(per_d)).abs().idxmin()
        got = pk.loc[j, "period_d"]
        err = abs(got - per_d) / per_d
        ok = err < (0.2 if per_d > 1000 else 0.05)
        return dict(series=series, method=method, planted=name, planted_value=fmt(per_d), recovered_value=fmt(got),
                    rel_error_pct=round(100 * err, 1), significant=f"yes ({pk.loc[j, 'ratio']:.0f} x background)",
                    ok=bool(ok))
    return dict(series=series, method=method, planted=name, planted_value=fmt(per_d), recovered_value="none",
                rel_error_pct=np.nan, significant="no", ok=False)


# ============================================================================================== figures
def _style(ax):
    ax.grid(True, which="major", color=GRID, lw=0.6)
    ax.grid(True, which="minor", color=GRID, lw=0.3, alpha=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def _period_axis(ax, lo, hi, unit="d"):
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
    ax.set_xscale("log")
    ax.set_xlim(lo, hi)
    ticks = [t for t in ([2, 3, 6, 12, 17.27, 24, 48, 96, 168, 360, 720] if unit == "h"
                         else [2, 3, 5, 10, 20, 30, 60, 90, 182.6, 365.25, 730, 1096, 2191, 3652, 7305])
             if lo <= t <= hi]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_formatter(NullFormatter())
    fm = {182.6: "182", 365.25: "365", 17.27: "17.3", 2191: "6 yr", 3652: "10 yr", 7305: "20 yr", 1096: "3 yr",
          730: "2 yr"}
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fm.get(round(v, 2), f"{v:g}")))
    ax.set_xlabel("Period (hours, log scale)" if unit == "h" else "Period (days, log scale)", color=INK, fontsize=9)


def _marks_daily(ax, lo, hi, ytop, ybot=None):
    ax.axvspan(3, 10, color=BAND, alpha=0.25, lw=0)
    if ybot is None:
        ax.text(np.sqrt(30), ytop, "synoptic\n3-10 d", ha="center", va="top", fontsize=7, color=MUTED)
    else:
        ax.text(np.sqrt(30), ybot, "synoptic 3-10 d", ha="center", va="bottom", fontsize=7, color=MUTED)
    for per, lab in [(ANNUAL_D, "annual"), (SEMIANNUAL_D, "semi-annual")]:
        if lo <= per <= hi:
            ax.axvline(per, color=MUTED, lw=0.8, ls=":")
            ax.text(per, ytop, lab, rotation=90, ha="right", va="top", fontsize=7, color=MUTED)


def _plot_sp(ax, sp, color, label, per_scale=1.0, lw=1.4, ls="-"):
    per = per_scale / sp["freq"]
    ax.plot(per, sp["psd"], color=color, lw=lw, ls=ls, label=label)
    ax.plot(per, sp["level"], color=color, lw=0.8, ls="--", alpha=0.8)
    pk = sp["peaks"]
    if len(pk):
        f = 1 / sp["freq"]
        idx = [int(np.argmin(np.abs(f - p))) for p in pk.period_d]
        ax.plot(pk.period_d * per_scale, sp["psd"][idx], "o", ms=5, mfc="white", mec=color, mew=1.3, ls="none")


def sentence(st: str, var: str, res: dict, bands: pd.DataFrame, title: str) -> str:
    """Plain-language sentence for one station / variable (what, so what)."""
    parts = []
    full = {s: res.get((st, var, s, "full")) for s in ("insitu", "satellite", "model")}
    names = {"insitu": "buoy", "satellite": "satellite", "model": "model"}
    has_ann = [names[s] for s, sp in full.items() if sp is not None and
               any(band_of(p) == "annual" for p in sp["peaks"].period_d)]
    avail = [names[s] for s, sp in full.items() if sp is not None]
    miss = [n for n in avail if n not in has_ann]
    if has_ann:
        parts.append(f"The annual cycle stands out above red noise for the {', '.join(has_ann)}"
                     + (f" (no separate significant annual peak for the {', '.join(miss)}: the power is there but the "
                        "record is too short or too gappy to resolve it as a peak; see peaks.csv)" if miss else ""))
    else:
        parts.append("No annual peak passes the test here (too few years or too many gaps), although the seasonal "
                     "rise is visible")
    b = bands[(bands.station == st) & (bands.variable == var)].set_index("source")
    if "insitu" in b.index:
        for src in ("satellite", "model"):
            if src in b.index and b.loc["insitu", "synoptic (3-10 d)"] > 0:
                r = b.loc[src, "synoptic (3-10 d)"] / b.loc["insitu", "synoptic (3-10 d)"]
                parts.append(f"the {src} has {r:.1f} times the buoy's 3-10 day variance"
                             if r >= 1 else f"the {src} has {r:.2f} of the buoy's 3-10 day variance")
    return "; ".join(parts) + "."


def figure_station(st: str, var: str, res: dict, bands: pd.DataFrame, title: str) -> tuple[Path, str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    seg_full = None
    for ax, kind in zip(axes, ["full", "anomalies"]):
        _style(ax)
        ymax = 0
        for src in ("insitu", "satellite", "model"):
            sp = res.get((st, var, src, kind))
            if sp is None:
                continue
            lab = f"{SRC_LABEL[src]}: {sp['method']}, {sp['n_seg']} seg, dof {sp['dof']:.0f}"
            _plot_sp(ax, sp, COL[src], lab)
            ymax = max(ymax, np.nanmax(sp["psd"]))
            if kind == "full":
                seg_full = sp["seg_days"]
        ax.set_yscale("log")
        hi = (seg_full or FULL_SEG) / 2 if kind == "full" else ANOM_SEG / 2   # 2 cycles per segment at least
        _period_axis(ax, 2, hi)
        ax.set_ylim(top=ymax * 4)
        _marks_daily(ax, 2, hi, ymax * 3, ybot=ax.get_ylim()[0] * 1.3)
        ax.set_ylabel(f"PSD, {YLAB[var]} per cycle/day", color=INK, fontsize=9)
        ax.set_title("Full series (linear trend removed)" if kind == "full"
                     else "Anomalies (trend, annual and semi-annual cycles removed)", fontsize=9.5, color=INK,
                     loc="left")
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    s = sentence(st, var, res, bands, title)
    srcs = " vs ".join(n for k, n in [("insitu", "buoy"), ("satellite", "satellite"), ("model", "model")]
                       if (st, var, k, "full") in res)
    fig.suptitle(f"{st}: {title}, power spectra ({srcs})", fontsize=11, color=INK, x=0.01, ha="left")
    fig.text(0.01, -0.06, "Dashed lines: 95 % level of the red-noise background, same colour as the source (left: "
             "robust AR(1) fit; right: running-median continuum); open circles: significant peaks (left: periods of "
             "120 days and more; right: 2 to 120 days).\n" + s, fontsize=8.5, color=INK, ha="left", va="top",
             wrap=True)
    p = FIG / f"psd_{st}_{var}.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p, s


def figure_synthetic(mc: dict) -> list[tuple[Path, str]]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = []
    # --- long daily
    lg = mc["long"]
    s, sp = lg["series"]["sst"], lg["sp"]
    fig, (a0, a1) = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True,
                                 gridspec_kw=dict(height_ratios=[1, 1.6]))
    _style(a0)
    a0.plot(s.index, s.to_numpy(), color=COL["synthetic"], lw=0.4)
    yr = s.resample("YE").mean()
    a0.plot(yr.index - pd.Timedelta(days=182), yr.to_numpy(), color=INK, lw=1.4, label="annual mean")
    a0.set_ylabel("SST (°C)", color=INK, fontsize=9)
    a0.legend(fontsize=8, frameon=False, loc="upper left")
    a0.set_title("SYNTHETIC daily series, 1982-2021 (not real data)", fontsize=9.5, loc="left", color=INK)
    _style(a1)
    _plot_sp(a1, sp, COL["synthetic"], f"SYNTHETIC: Welch, Hann, {sp['seg_days'] / ANNUAL_D:.0f}-year segments, "
             f"{sp['n_seg']} seg, dof {sp['dof']:.0f}")
    a1.set_yscale("log")
    _period_axis(a1, 2, sp["seg_days"] / 2)
    a1.set_ylim(top=np.nanmax(sp["psd"]) * 4)
    _marks_daily(a1, 2, sp["seg_days"] / 2, np.nanmax(sp["psd"]) * 3, ybot=a1.get_ylim()[0] * 1.3)
    a1.axvline(6 * ANNUAL_D, color=MUTED, lw=0.8, ls=":")
    a1.text(6 * ANNUAL_D, np.nanmax(sp["psd"]) * 3, "planted 6 yr", rotation=90, ha="right", va="top", fontsize=7,
            color=MUTED)
    a1.set_ylim(top=np.nanmax(sp["psd"]) * 4)
    a1.set_ylabel("PSD, (°C)² per cycle/day", color=INK, fontsize=9)
    a1.legend(fontsize=8, frameon=False, loc="upper left")
    txt = ("Method check: the spectrum finds the three planted cycles (annual, semi-annual, 6-year) above the red-noise "
           "level; a 40-year record is what it takes to see multi-year cycles, the 2.6- and 10-year buoy records "
           "cannot.")
    fig.suptitle("SYNTHETIC 40-year daily SST: power spectrum (Welch)", fontsize=11, x=0.01, ha="left", color=INK)
    fig.text(0.01, -0.02, "Dashed line: 95 % level of the robust AR(1) red-noise background; open circles: "
             "significant peaks.\n" + txt,
             fontsize=8.5, ha="left", va="top", color=INK, wrap=True)
    p = FIG / "SYNTHETIC_long_daily_psd.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    out.append((p, txt))

    # --- hourly
    h = mc["hourly"]
    g, spf, spg = h["series"]["sst"], h["sp_full"], h["sp_gaps"]
    fig, (a0, a1) = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True,
                                 gridspec_kw=dict(height_ratios=[1, 1.6]))
    _style(a0)
    wk = g[(g.index >= "2025-07-01") & (g.index < "2025-07-22")]
    full = wk.reindex(pd.date_range("2025-07-01", "2025-07-21 23:00", freq="h"))
    a0.plot(full.index, full.to_numpy(), color=COL["synthetic_gaps"], lw=0.9)
    a0.set_ylabel("SST (°C)", color=INK, fontsize=9)
    a0.set_title("SYNTHETIC hourly series, three weeks of July shown (blank = gaps; not real data)", fontsize=9.5,
                 loc="left", color=INK)
    _style(a1)
    _plot_sp(a1, spf, COL["synthetic"], f"SYNTHETIC gap-free: Welch, 30-day segments, dof {spf['dof']:.0f}",
             per_scale=24)
    _plot_sp(a1, spg, COL["synthetic_gaps"], f"SYNTHETIC with {spg['gap_share']:.0%} gaps: Lomb-Scargle, "
             f"dof {spg['dof']:.0f}", per_scale=24, lw=1.1)
    a1.set_yscale("log")
    _period_axis(a1, 2, 360, unit="h")
    ytop = max(np.nanmax(spf["psd"]), np.nanmax(spg["psd"]))
    for per, lab in [(24, "diurnal 24 h"), (12 / np.sin(np.deg2rad(44)), "inertial 17.3 h"), (12.42, "M2 12.42 h")]:
        a1.axvline(per, color=MUTED, lw=0.8, ls=":")
        a1.text(per, ytop * 3, lab, rotation=90, ha="right", va="top", fontsize=7, color=MUTED)
    a1.axvspan(72, 240, color=BAND, alpha=0.25, lw=0)
    a1.set_ylim(top=ytop * 4)
    a1.text(np.sqrt(72 * 240), a1.get_ylim()[0] * 1.3, "synoptic 3-10 d", ha="center", va="bottom", fontsize=7,
            color=MUTED)
    a1.set_ylabel("PSD, (°C)² per cycle/day", color=INK, fontsize=9)
    a1.legend(fontsize=8, frameon=False, loc="upper left")
    txt = ("Method check: with or without gaps, the spectrum finds the diurnal cycle, the inertial oscillation (17.3 h "
           "at 44 N) and the small M2 tide (12.42 h); real buoy files would need hourly records, not daily means, to "
           "show these. The small circles at 2-10 h are chance exceedances (about 5 % of frequencies pass a 95 % "
           "level by chance).")
    fig.suptitle("SYNTHETIC 1-year hourly SST: power spectrum (Welch vs Lomb-Scargle)", fontsize=11, x=0.01,
                 ha="left", color=INK)
    fig.text(0.01, -0.02, "Dashed lines: 95 % levels of the red-noise background (running-median continuum); open "
             "circles: significant peaks.\n" + txt,
             fontsize=8.5, ha="left", va="top", color=INK, wrap=True)
    p = FIG / "SYNTHETIC_hourly_psd.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    out.append((p, txt))
    return out


CYCLE_COLS = ["annual", "semi-annual", "3-4 month (seasonal harmonics)"]


def figure_matrix(peaks: pd.DataFrame, res: dict, titles: dict) -> Path:
    """Dot matrix: which seasonal cycles are significant per station / variable (rows) and source (marker), plus the
    share of 2-85 day frequencies above the 95 % level (about 5 % expected by chance)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [(st, v) for st in STATIONS for v in VARS]
    fig, ax = plt.subplots(figsize=(11, 0.36 * len(rows) + 1.8), constrained_layout=True)
    marker = {"insitu": "s", "satellite": "o", "model": "^"}
    off = {"insitu": -0.22, "satellite": 0.0, "model": 0.22}
    nc = len(CYCLE_COLS)
    for i, (st, v) in enumerate(rows):
        txt = []
        for src in ("insitu", "satellite", "model"):
            sel = peaks[(peaks.station == st) & (peaks.variable == v) & (peaks.source == src)]
            for j, c in enumerate(CYCLE_COLS):
                if (sel.cycle == c).any():
                    ax.plot(j + off[src], i, marker[src], color=COL[src], ms=7, mec="white", mew=0.8)
            sp = res.get((st, v, src, "anomalies"))
            if sp is not None:
                per = 1 / sp["freq"]
                nb = int(np.sum((per >= 2) & (per <= 85)))
                txt.append(f"{ {'insitu': 'buoy', 'satellite': 'sat', 'model': 'model'}[src]} "
                           f"{100 * n_above(sp, 2, 85) / nb:.0f} %")
        ax.text(nc - 0.45, i, "   ".join(txt), va="center", ha="left", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(rows)), [f"{st}  {titles.get(v, v)}" for st, v in rows], fontsize=8, color=INK)
    ax.set_xticks(list(range(nc)) + [nc + 0.6],
                  [c.replace(" (seasonal harmonics)", "\n(seasonal harmonics)") for c in CYCLE_COLS]
                  + ["2-85 days: share of frequencies\nabove the 95 % level\n(about 5 % expected by chance)"],
                  fontsize=8, color=INK)
    ax.set_xlim(-0.6, nc + 1.9)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    for i in range(len(rows)):
        if i % 4 == 0 and i:
            ax.axhline(i - 0.5, color=GRID, lw=0.8)
    ax.axvline(nc - 0.5, color=GRID, lw=0.8)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    for src in ("insitu", "satellite", "model"):
        ax.plot([], [], marker[src], color=COL[src], ms=7, label=SRC_LABEL[src], ls="none")
    ax.legend(ncol=3, fontsize=8, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title("Which cycles are significant (95 % against red noise), real daily data", fontsize=10, color=INK,
                 loc="left", pad=22)
    p = FIG / "cycles_matrix.png"
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


# ============================================================================================== report
def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r[c]) else (f"{r[c]:.3g}" if isinstance(r[c], float) else str(r[c]))
                                       for c in cols) + " |")
    return "\n".join(lines)


def write_report(res, peaks, bands, mcheck, figs, synfigs, matrix, titles, meta) -> Path:
    L = []
    L.append("# Power spectra: which cycles exist before trend detection")
    L.append("")
    L.append(f"Romanian Black Sea shelf, offshore buoys. Generated by `scripts/spectra/psd.py` on "
             f"{time.strftime('%Y-%m-%d %H:%M')} from cached data only (`MARINEKIT_OFFLINE=1`). Re-run the script to "
             "refresh numbers and figures.")
    L.append("")
    L.append("Second analysis step: after the source validation (`docs/indicators/validation/`), before trends. "
             "The question: which cycles are real in each series, and does the model reproduce them? The answer "
             "tells the trend step what to remove first (seasonal cycle) and which time scales are worth a trend.")
    L.append("")
    L.append("Real data are labelled by station and source. Everything marked **SYNTHETIC** is generated, not "
             "measured: it covers the long-period and sub-daily parts not downloaded yet, and checks the method.")
    L.append("")
    L.append("## Key findings")
    L.append("")
    for k in meta["findings"]:
        L.append(f"- {k}")
    L.append("")
    L.append("Variance ratio source / buoy, median over the stations (seasonal band from the full spectrum, "
             "shorter bands from the anomaly spectrum; chlorophyll in log10):")
    L.append("")
    L.append(_md(meta["ratio_tab"]))
    L.append("")
    L.append("![Which cycles are significant](figures/cycles_matrix.png)")
    L.append("")
    L.append("## Method")
    L.append("")
    L.append("- **Data**: the same trusted series as the validation step, loaded through its own code "
             "(`compare_sources.fetch_insitu` / `fetch_other`, imported read-only), with the same QC (deployment "
             "start, spike removal, O2 saturation check). Buoy daily means: EUXRo03 2013-06 to 2023-10 (Copernicus "
             "In Situ TAC), EUXRoOB01-03 2024-04 to 2026-11 (GeoEcoMar). Satellite (SST L4, chl L4 gap-free) and "
             "model (CMEMS Black Sea 2.5 km daily) at the buoy position over the buoy period, every day (not only "
             "buoy days). Satellite salinity and O2 do not exist, so those panels have buoy and model only. "
             "Chlorophyll is analysed as log10 (as in the validation step).")
    L.append("- **Gap-free series (satellite, model) -> Welch**: Hann window, 50 % overlap, segment mean removed, "
             "one-sided PSD (`scipy.signal.welch`, density scaling). Holes of at most 5 days covering at most 1 % "
             "of the record are filled by linear interpolation first; otherwise the series goes to Lomb-Scargle.")
    L.append("- **Gappy series (buoys, 10-56 % missing days) -> Lomb-Scargle**: classical Lomb-Scargle (Scargle "
             "1982) on the same 50 %-overlapping Hann-tapered segments, on the Welch frequency grid "
             "f_k = k / segment length (k = 1 .. segment length / 2 days), scaled like Welch's density and averaged "
             "over segments (WOSA, as REDFIT, Schulz and Mudelsee 2002). Segments with less than 40 % of their days "
             "are skipped. Gaps let the large low-frequency power leak to short periods (without correction the "
             "2-10 day band came out up to 40 times too high in the gap check), so the series is prewhitened first "
             "(z_t = y_t - rho y_(t-1 day), on days whose previous day exists) and the spectrum recoloured by "
             "1 / |1 - rho exp(-2 pi i f)|^2 (Percival and Walden 1993). On a gap-free series the result equals "
             "Welch (method check below).")
    L.append(f"- **Two spectra per series**: *full* = linear trend removed, segment = record length up to "
             f"{FULL_SEG:.0f} days (3 years, resolves the annual cycle; the 2.6-year buoys give a single segment, "
             f"2 degrees of freedom, so their full spectra are noisy); *anomalies* = linear trend plus annual "
             f"(365.25 d) and semi-annual (182.6 d) harmonics removed by least squares, segment = {ANOM_SEG:.0f} "
             "days (more averaging, for 2 to 180 days).")
    L.append("- **Significance**: robust red-noise background (Mann and Lees 1996): the PSD is median-smoothed "
             "over +-0.15 decade of frequency (lines barely move a median) and converted to a mean. For the *full* "
             "spectra an AR(1) spectrum is fitted to that smoothed curve (least squares in log space), which carries "
             "the background under the annual line. For the *anomaly* spectra the smoothed curve itself is the "
             "background, because the real continuum is not AR(1)-shaped (it falls faster than AR(1) at 2-5 days, "
             "and a fitted AR(1) flagged 20-30 % of frequencies). A peak is significant when it is a local maximum "
             "above the 95 % chi-square level with the Welch/WOSA equivalent degrees of freedom "
             "(dof = 2K / (1 + 2 c^2 (1 - 1/K)), K segments, c = 0.167 for 50 % Hann). The period is refined by a "
             "parabola through the log-PSD.")
    L.append("- **Which spectrum answers what**: peaks are reported from the full spectrum for periods of 120 days "
             "and longer (seasonal), and from the anomaly spectrum for 2 to 120 days (more degrees of freedom). The "
             "level is per frequency, so about 5 % of frequency bins exceed it by chance in every spectrum; the "
             "false-alarm table and an across-series consistency test (binomial, Bonferroni) say whether the "
             "short-period exceedances are more than chance.")
    L.append("- **Resolvable band** with daily means: 2 days (Nyquist) to about 1.5 years (half a 3-year segment). "
             "Marked on the figures: annual (365 d), semi-annual (182 d), synoptic band (3-10 days, weather).")
    L.append("- **Band variance** (table below): PSD integrated over period bands of the full spectrum, per source; "
             "the row *model on buoy days* recomputes the model spectrum through Lomb-Scargle on the buoy's days "
             "only, to show how much of a buoy-model difference comes from the gaps rather than the physics.")
    L.append("- Band names and limits are OURS, for labelling only.")
    L.append("")
    L.append("## Method check on SYNTHETIC series")
    L.append("")
    L.append("Built by `scripts/spectra/synthetic.py` in the same shape as `datahub.get_series()` output (DatetimeIndex "
             "named `time`, one column, attrs with `label` starting `SYNTHETIC`, and the planted values in "
             "`attrs['planted']`), so a real series replaces it with one line. The same checks run as unit tests in "
             "`tests/test_spectra.py`.")
    L.append("")
    L.append(_md(mcheck))
    L.append("")
    for p, txt in synfigs:
        L.append(f"![{p.stem}](figures/{p.name})")
        L.append("")
        L.append(txt)
        L.append("")
    L.append("## Significant peaks per station, variable and source (real data)")
    L.append("")
    L.append("Up to 4 strongest per spectrum, sorted by PSD / red-noise background. All rows are in `peaks.csv`. "
             "`x bg` = PSD over the AR(1) background; `x 95 %` = PSD over the 95 % level (> 1 = significant).")
    L.append("")
    top = (peaks.sort_values("psd_over_background", ascending=False)
           .groupby(["station", "variable", "source", "spectrum"], sort=False).head(4)
           .sort_values(["station", "variable", "source", "spectrum", "psd_over_background"],
                        ascending=[True, True, True, True, False]))
    top = top.rename(columns={"psd_over_background": "x bg", "psd_over_95_level": "x 95 %", "period_d": "period (d)"})
    L.append(_md(top[["station", "variable", "source", "spectrum", "method", "period (d)", "cycle", "x bg", "x 95 %",
                      "dof"]]))
    L.append("")
    ct = meta["ct"]
    L.append("## False-alarm check and lag-1 autocorrelation (anomaly spectra, 2-120 days)")
    L.append("")
    L.append(f"Across-series consistency test: for each frequency bin from 2 to 85 days ({ct['n_bins']} bins), the "
             f"number of the {ct['n_spectra']} anomaly spectra above their 95 % level, against a binomial with "
             "p = 0.05 (Bonferroni over bins; liberal, since sources at one station are correlated). Bins with "
             "corrected p < 0.05:")
    L.append("")
    sg = ct["sig"][["period_d", "n_exceed", "n_spectra", "share", "p_bonferroni"]].copy()
    sg["year / period"] = (ANNUAL_D / sg.period_d).round(2)
    L.append(_md(sg) if len(sg) else "none")
    L.append("")
    L.append("Per spectrum: bins tested, bins above the 95 % level and their share (5 % expected by chance). "
             "`rho_lag1` = lag-1 autocorrelation of the daily anomalies (for the trend step).")
    L.append("")
    L.append(_md(ct["tests"][["station", "variable", "source", "method", "n_tested", "bins_above_95",
                              "share_above_95", "dof", "rho_lag1"]]))
    L.append("")
    L.append("## Variance per band")
    L.append("")
    L.append("Units: variable units squared (chlorophyll in (log10 mg/m³)²). Seasonal band from the full spectrum, "
             "the shorter bands from the anomaly spectrum. Compare sources within a station and variable: a model "
             "that reproduces the variability has about the buoy's variance in each band. Rows *... on buoy days* "
             "are the gap check (same source, buoy days only, Lomb-Scargle).")
    L.append("")
    b = bands.copy()
    for c in ["variance_total"] + [n for n, *_ in BANDS]:
        b[c] = b[c].map(lambda x: float(f"{x:.3g}"))
    L.append(_md(b))
    L.append("")
    L.append("## Figures (real data)")
    L.append("")
    L.append("Each figure: left = full spectrum, right = anomaly spectrum. Black = buoy (Lomb-Scargle), blue = "
             "satellite (Welch), vermillion = model (Welch); dashed = 95 % red-noise level of the same source; open "
             "circles = significant peaks; yellow band = synoptic 3-10 days.")
    L.append("")
    for (st, v), (p, s) in figs.items():
        L.append(f"### {st}, {titles[v]}")
        L.append("")
        L.append(f"![{p.stem}](figures/{p.name})")
        L.append("")
        L.append(s)
        L.append("")
    L.append("## Limitations")
    L.append("")
    for k in meta["limits"]:
        L.append(f"- {k}")
    L.append("")
    L.append("## Next step: trends")
    L.append("")
    for k in meta["next"]:
        L.append(f"- {k}")
    L.append("")
    L.append("## Files")
    L.append("")
    L.append("- `scripts/spectra/psd.py`: spectral core (Welch, WOSA Lomb-Scargle, AR(1) level, peaks), real-data "
             "run, figures, this report. `scripts/spectra/synthetic.py`: SYNTHETIC series. `tests/test_spectra.py`: "
             "planted-period recovery and normalisation tests.")
    L.append("- `peaks.csv`: machine-readable peak table, one row per peak, real and SYNTHETIC series. Columns: "
             "`variable`, `source` (in situ / satellite / model / synthetic), `station`, `synthetic`, `method` "
             "(welch / lomb-scargle), `period_days` (sub-daily periods as fractions of a day), `power` (PSD, "
             "variable units squared per cycle/day), `significant_95` (above the 95 % level of the red-noise "
             "background), `rank` (1 = strongest significant peak by power for that variable / source / station, "
             "both spectra together; empty when not significant), then `spectrum` (full / anomalies), `cycle`, "
             "`psd_over_background`, `psd_over_95_level`, `dof`. Besides all significant peaks it lists the local "
             "maximum nearest the annual and semi-annual periods in each full spectrum (or the nearest bin when the "
             "PSD rises without a local maximum, as for the 2.6-year buoys, whose frequency grid puts the annual "
             "cycle at 320 days), with `significant_95` from the 95 % level, so a harmonic fit can always find "
             "them. Note: ranking by power mixes the full and anomaly spectra; the seasonal rows dominate, but "
             "short-period rows with `psd_over_95_level` close to 1 are often chance exceedances.")
    L.append("- `band_variance.csv`, `method_check.csv`, `false_alarm_check.csv`, `figures/`.")
    L.append("")
    p = OUT / "README.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def build_findings(res, peaks, bands, mcheck) -> dict:
    f = []
    full = peaks[peaks.spectrum == "full"]
    ann = full[full.cycle == "annual"].groupby(["variable", "source"]).station.nunique()
    f.append("Annual cycle: significant in the full spectrum for " + "; ".join(
        f"{v} {SRC_LABEL[s]} ({n} of 4 stations)" for (v, s), n in ann.items()) + ".")
    semi = peaks[peaks.cycle == "semi-annual"].groupby(["variable", "source"]).station.nunique()
    if len(semi):
        f.append("Semi-annual: " + "; ".join(f"{v} {SRC_LABEL[s]} ({n})" for (v, s), n in semi.items())
                 + " (mostly the non-sinusoidal shape of the annual cycle, a harmonic, not a separate process).")
    b = bands[bands.source.isin(["insitu", "satellite", "model"])]
    rows = []
    word = lambda r: "much smoother" if r < 0.5 else ("much more variable" if r > 2 else "similar")  # noqa: E731
    for v in VARS:
        bb = b[b.variable == v]
        for src in ("satellite", "model"):
            row = dict(variable=v, source=src)
            for name, *_ in BANDS:
                r = []
                for st in STATIONS:
                    x = bb[bb.station == st].set_index("source")
                    if "insitu" in x.index and src in x.index and x.loc["insitu", name] > 0:
                        r.append(x.loc[src, name] / x.loc["insitu", name])
                row[name] = f"{np.median(r):.2f} ({word(np.median(r))})" if r else ""
            if any(row[n] for n, *_ in BANDS):
                rows.append(row)
    ratio_tab = pd.DataFrame(rows)
    f.append("Does the source reproduce the buoy's variability? Median over stations of the variance ratio "
             "source / buoy per band (about 1 = similar; < 0.5 much smoother; > 2 much more variable). Table "
             "below the findings. Part of a buoy excess can be sensor noise, drift or fouling, and point vs "
             "grid-cell sampling (sub-grid patchiness); the gap check rules out the gaps. In short: SST is reproduced "
             "at every scale by both satellite and model. For salinity and oxygen the model has far less variance "
             "than the buoys below one season, consistent with the validation step's finding that buoy salinity "
             "suffers from conductivity fouling and drift (`docs/indicators/validation/interpretation.md`), so the "
             "excess is at least partly instrumental. For chlorophyll the buoy has about 10 times more seasonal "
             "variance than satellite and model (fluorometer drift or calibration, also flagged in the validation "
             "step), while the model is noisier than the buoy at 2-10 days.")
    harm = peaks[peaks.cycle == "3-4 month (seasonal harmonics)"]
    if len(harm):
        f.append("3-4 month peaks (" + ", ".join(sorted({f"{r.station} {r.variable} {SRC_LABEL[r.source]}"
                                                         for r in harm.itertuples()})) +
                 "): higher harmonics of the seasonal cycle (121.8 d, 91.3 d), i.e. its shape is not two sinusoids; "
                 "a day-of-year climatology removes them, two harmonics do not.")
    tests = pd.DataFrame(TESTS)
    ta = tests[tests.spectrum == "anomalies"]
    ct = consistency_test(res)
    meta_ct = dict(n_spectra=int(ct.n_spectra.iloc[0]), max_share=float(ct.share.max()),
                   max_period=float(ct.period_d[ct.share.idxmax()]), min_p=float(ct.p_bonferroni.min()),
                   n_bins=len(ct))
    sig = ct[ct.p_bonferroni < 0.05].sort_values("p")
    desc = []
    for r in sig.itertuples():
        k = ANNUAL_D / r.period_d
        kind = (f"{round(k)}th harmonic of the year, likely the seasonal-cycle shape or its year-to-year changes" if abs(k - round(k)) < 0.05 and k <= 12
                else "not a harmonic of the year")
        desc.append(f"{r.period_d:.1f} d ({r.n_exceed} of {r.n_spectra} spectra, Bonferroni p = "
                    f"{r.p_bonferroni:.2g}; {kind})")
    meta_ct["sig"] = sig
    nonh = [r.period_d for r in sig.itertuples()
            if not (abs(ANNUAL_D / r.period_d - round(ANNUAL_D / r.period_d)) < 0.05 and ANNUAL_D / r.period_d <= 12)]
    f.append(f"Between 2 days and about 3 months, {ta.bins_above_95.sum()} of {ta.n_tested.sum()} frequency bins of "
             f"the anomaly spectra ({100 * ta.bins_above_95.sum() / ta.n_tested.sum():.1f} %) are above the 95 % "
             "level, a little more than the 5 % expected by chance. Periods significant in more series than chance "
             "allows (binomial test across the " + str(meta_ct["n_spectra"]) + " spectra, Bonferroni over "
             + str(meta_ct["n_bins"]) + " bins): " + ("; ".join(desc) if desc else "none") + ". The harmonics "
             "mean that two sinusoids do not capture the seasonal cycle; a day-of-year climatology does. Apart from "
             "them, short-term variability is broadband red noise (weather, river-plume pulses, blooms), not a "
             "cycle" + (f"; the non-harmonic period(s) above ({', '.join(f'{x:.1f} d' for x in nonh)}) pass only a "
                        "test that treats correlated spectra as independent, so they are borderline (synoptic "
                        "weather systems), not a robust cycle" if nonh else "") +
             ". Isolated peaks in the table are not to be read as cycles.")
    gap = []
    for src in ("model", "satellite"):
        x = bands[bands.source == f"{src} on buoy days"].set_index(["station", "variable"])
        y = bands[bands.source == src].set_index(["station", "variable"]).reindex(x.index)
        for name in ("synoptic (3-10 d)", "short (2-3 d)"):
            r = (x[name] / y[name]).dropna()
            if len(r):
                gap.append(f"{src} {name.split(' (')[0]} {r.median():.2f} (range {r.min():.2f}-{r.max():.2f})")
    f.append("Gap check: the model and satellite resampled on the buoy's days and run through the same "
             "Lomb-Scargle give the same band variance as their gap-free Welch spectra (ratio, median over "
             "stations and variables: " + "; ".join(gap) + "), so the buoy-model differences above are not "
             "made by the gaps.")
    meta_ct["tests"] = ta
    ok = mcheck.ok.all()
    f.append(f"Method check on SYNTHETIC series: {int(mcheck.ok.sum())} of {len(mcheck)} checks passed"
             + (" (all planted periods recovered, Lomb-Scargle = Welch on gap-free data)." if ok else
                "; see the table for the failures."))
    limits = [
        "Daily means cannot show sub-daily cycles (diurnal, inertial 17.3 h, tides); only the SYNTHETIC hourly "
        "series shows what to expect from raw hourly buoy records.",
        "The 2.6-year OB buoys give one segment for the full spectrum (2 degrees of freedom): their annual peak is "
        "visible but its significance is weak, and periods longer than about 1.3 years are not resolved.",
        "Multi-year cycles (ENSO/NAO-like, 3-8 years) are not resolvable with 10 years at one point; only the "
        "SYNTHETIC 40-year series illustrates them. A real 40-year satellite SST series (from 1982) would replace "
        "it with one line once downloaded.",
        "The 95 % level is per frequency (no multiple-testing correction inside one spectrum); isolated "
        "short-period peaks need confirmation in another source or station before being called a cycle. The "
        "across-series consistency test treats the spectra as independent, which they are not (same weather at "
        "one station), so it errs towards finding a cycle; it still finds none.",
        "The running-median background of the anomaly spectra detects sharp peaks only: a broad bump (for example "
        "a preferred 5-10 day band) is absorbed into the background. Broad-band differences between sources are "
        "therefore read from the band-variance table, not from peaks.",
        "Satellite L4 SST and gap-free chlorophyll are interpolated analyses: their short-period variance is "
        "partly made by the analysis, not observed.",
    ]
    nxt = [
        "Remove the mean seasonal cycle before Mann-Kendall / Sen's slope: it is the dominant significant signal "
        "everywhere. Prefer a day-of-year climatology (it also removes the 3-4 month harmonics) over two "
        "harmonics.",
        "No significant cycle between 2 days and 4 months: weekly and daily aggregates can be trend-tested after "
        "deseasoning without removing other periodicities, but red noise (autocorrelation) must be handled "
        "(pre-whitening or block bootstrap), using the lag-1 autocorrelation of the daily anomalies computed here "
        "(`false_alarm_check.csv`, column `rho_lag1`), which shows that daily values are far from independent.",
        "Interannual trends need the long records (satellite SST from 1982, model from 1993); the 10-year buoy is "
        "too short to separate a trend from a multi-year oscillation.",
    ]
    return dict(findings=f, limits=limits, next=nxt, ct=meta_ct, ratio_tab=ratio_tab)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log("method check on SYNTHETIC series")
    mc, mcheck = method_check()
    mcheck.to_csv(OUT / "method_check.csv", index=False)
    log(f"  {int(mcheck.ok.sum())}/{len(mcheck)} checks ok")
    synfigs = figure_synthetic(mc)
    log("real data (cache only)")
    data, cs = collect()
    titles = {v: cs.VARIABLES[v]["title"] for v in VARS}
    res, peaks, bands = analyse_real(data)
    peak_table(res, mc).to_csv(OUT / "peaks.csv", index=False)
    bands.to_csv(OUT / "band_variance.csv", index=False)
    pd.DataFrame(TESTS).to_csv(OUT / "false_alarm_check.csv", index=False)
    figs = {}
    for (st, v) in data:
        figs[(st, v)] = figure_station(st, v, res, bands, titles[v])
    matrix = figure_matrix(peaks, res, titles)
    meta = build_findings(res, peaks, bands, mcheck)
    p = write_report(res, peaks, bands, mcheck, figs, synfigs, matrix, titles, meta)
    log(f"report {p.relative_to(ROOT)} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
