"""Seasonal cycle and long-term trend for the viewer, behind a quality gate (issue #2, request 2).

Two parts:

1. Fit code (moved here from scripts/seasonal/harmonic.py and trend.py, which now re-export it unchanged):
   aggregate, fit_harmonics, compare_nested, select_periods, acf, ljung_box, phase_label (harmonic regression with
   Newey-West HAC errors, periods from the power spectra) and annual_means, linear_trend (OLS on complete years).

2. Viewer API (additive, all values carry unit, origin and trust):

    seasonal_cycle(variable, lat, lon, source="auto") -> dict
    usual_range(variable, lat, lon, dates, source="auto") -> DataFrame(fit, lo, hi)
    long_term_trend(variable, lat, lon, source="auto") -> dict
    gate_summary() -> DataFrame        (which variable / station / source passes which gate; for the Methods page)

   Precomputed results in docs/indicators/seasonal/*.csv (scripts/seasonal/run_seasonal.py) are used when the point is
   within NEAR_STATION_KM of a fitted station; otherwise the fit is done on the fly from cached datahub.get_series
   data (offline-safe: no cached data -> show False with the reason).

Quality gate (level 2 of the two-level rule; all thresholds OURS, see docs/indicators/SHORTLIST.md, last section):
  * source trust: attrs["trust"] returned by marinekit.datahub.get_series must be "good" or "usable";
  * seasonal cycle shown when the annual cycle (or the strongest fitted cycle if no annual one) is significant
    (p < 0.05, Newey-West HAC Wald test) AND the adjusted R2 of trend + cycles on weekly means is >= 0.5;
  * trend: no number below 8 complete years ("not enough years yet"); 8-19 years: number shown, labelled
    "indicative"; 20 years or more: "climate trend" wording; p >= 0.05 always adds "not significant".
Every result has show (bool) and gate_reason (plain text), so the viewer shows either the result or the reason.
"""
from __future__ import annotations

import functools
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ======================================================================================================================
# Fit code (from scripts/seasonal/harmonic.py)
# ======================================================================================================================
YEAR_D = 365.25


# ----------------------------------------------------------------------------------------------------- aggregation
def aggregate(s: pd.Series, freq: str = "MS", how: str = "mean", min_n: int | None = None) -> pd.DataFrame:
    """Aggregate a daily series into bins (freq "MS" = calendar months, "W" = weeks).

    how = "mean" (temperature, salinity, O2, log10 chlorophyll) or "median" (linear chlorophyll).
    Returns a DataFrame indexed by the mean date of the valid days in each bin, columns value, n, sd, se.
    se = sd / sqrt(n) for the mean, 1.2533 sd / sqrt(n) for the median (large-sample normal approximation). Daily
    values inside a bin are autocorrelated, so this se is a lower bound; it is used for relative weights only.
    Bins with fewer than min_n days are dropped (default: 10 days for a month, 4 for a week; OURS)."""
    s = s.dropna().astype(float)
    s = s[~s.index.duplicated()].sort_index()
    if min_n is None:
        min_n = 4 if freq.upper().startswith("W") else 10
    g = s.groupby(pd.Grouper(freq=freq))
    if how not in ("mean", "median"):
        raise ValueError("how must be 'mean' or 'median'")
    val = g.mean() if how == "mean" else g.median()
    n = g.count()
    sd = g.std()
    k = 1.0 if how == "mean" else 1.2533
    se = k * sd / np.sqrt(n)
    tmean = s.index.to_series().groupby(pd.Grouper(freq=freq)).apply(lambda x: x.mean() if len(x) else pd.NaT)
    out = pd.DataFrame(dict(value=val, n=n, sd=sd, se=se, time=tmean))
    out = out[(out.n >= min_n) & out.value.notna()]
    out = out.set_index(pd.DatetimeIndex(out.pop("time")).normalize())
    out.index.name = "time"
    out.attrs = dict(freq=freq, how=how, min_n=min_n)
    return out


# ------------------------------------------------------------------------------------------------------- linear algebra
def newey_west_lags(n: int) -> int:
    """Default bandwidth floor(4 (n/100)^(2/9)) (Newey and West 1994)."""
    return int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def _ols(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None, hac_lags: int | None = None) -> dict:
    """(Weighted) least squares with classic and Newey-West (Bartlett kernel) covariance.
    HAC treats consecutive rows as neighbours; with a few missing bins this is an approximation.
    hac_lags None = automatic: the larger of the Newey-West rule and the first lag where the residual
    autocorrelation drops below 0.1, capped at n / 4 (OURS: the plain rule is too short for weekly residuals
    with lag-1 r ~ 0.8)."""
    n, p = X.shape
    sw = np.ones(n) if w is None else np.sqrt(w / np.mean(w))
    Xw, yw = X * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Xw.T @ Xw)
    beta = XtX_inv @ Xw.T @ yw
    resid = y - X @ beta
    rw = resid * sw
    df = n - p
    s2 = float(rw @ rw / df)
    cov = s2 * XtX_inv
    if hac_lags is None:
        r_ = acf(rw, max(1, n // 4))
        below = np.nonzero(r_ < 0.1)[0]
        L = max(newey_west_lags(n), int(below[0]) if len(below) else n // 4)
        L = min(L, max(1, n // 4))
    else:
        L = int(hac_lags)
    u = Xw * rw[:, None]
    S = u.T @ u
    for lag in range(1, L + 1):
        wl = 1 - lag / (L + 1)
        G = u[lag:].T @ u[:-lag]
        S += wl * (G + G.T)
    cov_hac = XtX_inv @ S @ XtX_inv * n / df          # small-sample scaling n / (n - p)
    rss = float(rw @ rw)
    ybar = np.average(y, weights=sw ** 2)
    tss = float(((y - ybar) * sw) @ ((y - ybar) * sw))
    loglik = -0.5 * n * (math.log(2 * math.pi * rss / n) + 1)
    return dict(beta=beta, cov=cov, cov_hac=cov_hac, resid=resid, rss=rss, tss=tss, n=n, p=p, df=df, s2=s2,
                loglik=loglik, hac_lags=L, sw=sw)


def _design(t: np.ndarray, periods: list[float], t_mid: float) -> np.ndarray:
    cols = [np.ones_like(t), (t - t_mid) / YEAR_D]
    for P in periods:
        w = 2 * np.pi / P
        cols += [np.cos(w * t), np.sin(w * t)]
    return np.column_stack(cols)


def _wald(beta: np.ndarray, cov: np.ndarray, idx: list[int], df: int) -> tuple[float, float]:
    """Joint Wald test that beta[idx] = 0; returns (F statistic, p-value) with F(q, df)."""
    b = beta[idx]
    C = cov[np.ix_(idx, idx)]
    q = len(idx)
    stat = float(b @ np.linalg.pinv(C) @ b) / q
    return stat, float(stats.f.sf(stat, q, df))


# ----------------------------------------------------------------------------------------------------- residual checks
def acf(x: np.ndarray, nlags: int = 20) -> np.ndarray:
    x = np.asarray(x, float) - np.mean(x)
    d = float(x @ x)
    return np.array([1.0] + [float(x[k:] @ x[:-k]) / d for k in range(1, min(nlags, len(x) - 1) + 1)])


def ljung_box(x: np.ndarray, lags: int = 10, fitted_params: int = 0) -> tuple[float, float]:
    n = len(x)
    r = acf(x, lags)[1:]
    q = n * (n + 2) * float(np.sum(r ** 2 / (n - np.arange(1, len(r) + 1))))
    dof = max(1, len(r) - fitted_params)
    return q, float(stats.chi2.sf(q, dof))


# ---------------------------------------------------------------------------------------------------------- phase
def _fmt_doy(day0: float) -> str:
    """Day offset from 1 January (0 = 1 Jan) -> '5 Aug' (non-leap calendar)."""
    d = pd.Timestamp("2001-01-01") + pd.Timedelta(days=float(day0) % 365.0)
    return f"{d.day} {d.strftime('%b')}"


def phase_label(t_max: float, period: float, t0: pd.Timestamp | None = None) -> str:
    """Plain date of the maximum. Annual: one date. Integer fractions of a year (semi-annual, 4-month...): the
    k dates per year. Other periods: the first maximum after 1 January of the first year, then every P days."""
    k = YEAR_D / period
    if abs(k - round(k)) < 0.05 and round(k) >= 1:
        k = int(round(k))
        return ", ".join(_fmt_doy((t_max + i * period) % YEAR_D) for i in range(k))
    ref = f"1 Jan {t0.year}" if t0 is not None else "1 Jan of the first year"
    return f"day {t_max:.0f} of a {period:.0f}-d cycle counted from {ref}"


# ------------------------------------------------------------------------------------------------------------ fit
def fit_harmonics(s: pd.Series, periods: list[float], se: pd.Series | None = None, weighted: bool = False,
                  hac_lags: int | None = None, alpha: float = 0.05, bin_days: float | None = None) -> dict:
    """Harmonic regression of a series (DatetimeIndex) on a linear trend plus one cos/sin pair per period (days).

    se: standard error of each value (e.g. aggregate()["se"]); with weighted=True the fit is WLS with 1/se^2
    (missing or zero se replaced by the median se).
    bin_days: width of the averaging bin (about 30.4 for monthly, 7 for weekly means). A box-car mean shrinks a
    cycle of period P by g = sinc(bin / P) (1.1 % for the annual cycle in monthly means, 4.5 % for the semi-annual,
    11 % for a 97-day cycle); amplitude, its SE and CI are divided by g (amplitude_raw and attenuation keep the
    uncorrected value and g). The fitted curves (fitted, predict, component) stay those of the means.
    Standard errors, CIs and p-values use the Newey-West HAC covariance (residuals of daily, weekly and even monthly
    series are autocorrelated); the classic OLS values are kept next to them for comparison.
    Returns a dict: n, periods, t0, cycles (list of dicts), model (R2, adj R2, residual sd, AIC, BIC, trend),
    residuals (lag-1 autocorrelation, Durbin-Watson, Ljung-Box, effective n), fitted / resid Series, predict(dates)."""
    s = s.dropna().astype(float)
    s = s[~s.index.duplicated()].sort_index()
    idx = pd.DatetimeIndex(s.index)
    t0 = pd.Timestamp(year=idx[0].year, month=1, day=1)
    t = ((idx - t0) / pd.Timedelta(days=1)).to_numpy(float)
    y = s.to_numpy()
    periods = [float(p) for p in periods]
    t_mid = float(np.mean(t))
    X = _design(t, periods, t_mid)
    if X.shape[0] <= X.shape[1] + 1:
        raise ValueError(f"too few points ({len(y)}) for {X.shape[1]} parameters")
    w = None
    if weighted:
        if se is None:
            raise ValueError("weighted=True needs se")
        e = pd.Series(se).reindex(s.index).to_numpy(float)
        med = np.nanmedian(e[e > 0]) if np.any(e > 0) else 1.0
        e = np.where(np.isfinite(e) & (e > 0), e, med)
        w = 1.0 / e ** 2
    r = _ols(X, y, w, hac_lags)
    beta, cov, covh, df = r["beta"], r["cov"], r["cov_hac"], r["df"]
    tq = float(stats.t.ppf(1 - alpha / 2, df))

    cycles = []
    for k, P in enumerate(periods):
        i, j = 2 + 2 * k, 3 + 2 * k
        a, b = beta[i], beta[j]
        A = float(np.hypot(a, b))
        phi = float(np.arctan2(b, a))                 # a cos + b sin = A cos(w t - phi)
        omega = 2 * np.pi / P
        t_max = (phi / omega) % P
        g_amp = np.array([a / A, b / A]) if A > 0 else np.zeros(2)
        g_phi = np.array([-b / A ** 2, a / A ** 2]) if A > 0 else np.zeros(2)
        out = dict(period_d=P, a=float(a), b=float(b), amplitude=A, phase_rad=phi, t_max_d=float(t_max),
                   max_date=phase_label(t_max, P, t0))
        for tag, C in (("", covh), ("_ols", cov)):
            C2 = C[np.ix_([i, j], [i, j])]
            se_a = float(np.sqrt(max(g_amp @ C2 @ g_amp, 0)))
            se_p = float(np.sqrt(max(g_phi @ C2 @ g_phi, 0))) / omega       # days
            F, p = _wald(beta, C, [i, j], df)
            out.update({f"amplitude_se{tag}": se_a, f"phase_se_d{tag}": se_p, f"p_value{tag}": p, f"F{tag}": F})
        g = float(np.sinc(bin_days / P)) if bin_days else 1.0       # np.sinc(x) = sin(pi x) / (pi x)
        out.update(amplitude_raw=A, attenuation=g, amplitude=A / g, amplitude_se=out["amplitude_se"] / g,
                   amplitude_se_ols=out["amplitude_se_ols"] / g)
        A = A / g
        out["amplitude_ci"] = (A - tq * out["amplitude_se"], A + tq * out["amplitude_se"])
        out["phase_ci_d"] = (t_max - tq * out["phase_se_d"], t_max + tq * out["phase_se_d"])
        # amplitude CI is unreliable when amplitude ~ se (Rice bias); flag it
        out["amplitude_resolved"] = bool(A > 2 * out["amplitude_se"])
        cycles.append(out)

    fitted = X @ beta
    resid = r["resid"]
    n, p = r["n"], r["p"]
    r2 = 1 - r["rss"] / r["tss"] if r["tss"] > 0 else float("nan")
    adj = 1 - (1 - r2) * (n - 1) / df
    aic = 2 * p - 2 * r["loglik"]
    bic = p * math.log(n) - 2 * r["loglik"]
    trend = float(beta[1])                             # units per year
    trend_se = float(np.sqrt(covh[1, 1]))
    rho1 = float(acf(resid, 1)[1]) if n > 3 else float("nan")
    dw = float(np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2))
    lb_lags = int(min(10, max(1, n // 5)))
    lbq, lbp = ljung_box(resid, lb_lags)
    n_eff = n * (1 - rho1) / (1 + rho1) if np.isfinite(rho1) and rho1 > 0 else float(n)

    def predict(dates) -> pd.Series:
        d = pd.DatetimeIndex(dates)
        tt = ((d - t0) / pd.Timedelta(days=1)).to_numpy(float)
        return pd.Series(_design(tt, periods, t_mid) @ beta, index=d)

    def component(dates, k: int) -> pd.Series:
        d = pd.DatetimeIndex(dates)
        tt = ((d - t0) / pd.Timedelta(days=1)).to_numpy(float)
        om = 2 * np.pi / periods[k]
        return pd.Series(beta[2 + 2 * k] * np.cos(om * tt) + beta[3 + 2 * k] * np.sin(om * tt), index=d)

    return dict(
        n=n, periods=periods, t0=t0, start=idx[0], end=idx[-1], weighted=weighted, cycles=cycles,
        model=dict(r2=float(r2), r2_adj=float(adj), resid_sd=float(np.sqrt(r["s2"])), aic=float(aic), bic=float(bic),
                   n_params=p, df=df, intercept=float(beta[0]), trend_per_year=trend, trend_se_per_year=trend_se,
                   trend_p=float(2 * stats.t.sf(abs(trend / trend_se), df)) if trend_se > 0 else float("nan"),
                   hac_lags=r["hac_lags"]),
        residuals=dict(lag1_autocorr=rho1, durbin_watson=dw, ljung_box_q=lbq, ljung_box_lags=lb_lags,
                       ljung_box_p=lbp, n_eff=float(n_eff)),
        fitted=pd.Series(fitted, index=idx), resid=pd.Series(resid, index=idx), data=s,
        beta=beta, cov_hac=covh, predict=predict, component=component,
    )


def compare_nested(s: pd.Series, periods: list[float], se: pd.Series | None = None, weighted: bool = False,
                   hac_lags: int | None = None, bin_days: float | None = None) -> pd.DataFrame:
    """Fit models with 0, 1, ..., K cycles (periods added in the order given) and show what each cycle adds.

    Columns: k, added_period_d, R2, R2_adj, resid_sd, AIC, BIC, dAIC / dBIC (vs previous model; negative = better),
    F and p_F (classic nested F-test, assumes independent residuals), p_hac (Newey-West Wald test of the added pair in
    the bigger model, robust to autocorrelation; the one to trust)."""
    rows, prev = [], None
    for k in range(len(periods) + 1):
        f = fit_harmonics(s, periods[:k], se=se, weighted=weighted, hac_lags=hac_lags, bin_days=bin_days)
        m = f["model"]
        row = dict(k=k, added_period_d=periods[k - 1] if k else np.nan, r2=m["r2"], r2_adj=m["r2_adj"],
                   resid_sd=m["resid_sd"], aic=m["aic"], bic=m["bic"], dAIC=np.nan, dBIC=np.nan,
                   F=np.nan, p_F=np.nan, p_hac=np.nan)
        if prev is not None:
            rss1 = (1 - m["r2"]) * 1.0
            rss0 = (1 - prev["r2"]) * 1.0
            q, df = 2, m["df"]
            F = ((rss0 - rss1) / q) / (rss1 / df) if rss1 > 0 else np.inf
            row.update(dAIC=m["aic"] - prev["aic"], dBIC=m["bic"] - prev["bic"], F=F,
                       p_F=float(stats.f.sf(F, q, df)), p_hac=f["cycles"][-1]["p_value"])
        rows.append(row)
        prev = m
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------- period selection
HARMONIC_CYCLES = {"annual": 1, "semi-annual": 2, "4-month (3rd harmonic)": 3}


def select_periods(peaks: pd.DataFrame, station: str, variable: str, source: str, step_d: float,
                   record_d: float, k: int = 3, snap: bool = True, fallback: list[tuple[str, str, str]] = (),
                   fallback_min_period: float = 60.0) -> list[dict]:
    """The k strongest significant peaks of one series that a fit on this sampling step can resolve.

    Accepts both formats the PSD step has written: the current one (variable, source, station, synthetic, method,
    period_days, power, significant_95, rank, spectrum, cycle, psd_over_background, psd_over_95_level, dof; source
    spelled 'in situ') and the first one (period_d, psd_over_95_level, seg_days, no rank). Rules:
      * significant at 95 % (significant_95 true; in the first format psd_over_95_level > 1). Rows the PSD step adds
        with significant_95 false (nearest annual / semi-annual local maximum) are not used;
      * real rows preferred: synthetic rows are used only when no real row exists;
      * fittable: 2 sampling steps <= period <= record length;
      * ranked by the PSD rank (1 = strongest by power; first format: psd_over_95_level); peaks closer in frequency
        than one spectral resolution step (1 / segment length: 365 d for the anomaly spectrum, up to 1096 d for the
        full one) to an already chosen peak are skipped (same cycle seen twice);
      * snap: a peak labelled annual / semi-annual / 3rd harmonic whose frequency is within one resolution step of
        k / 365.25 d is fitted at exactly 365.25 / k d (the PSD period of a 3-year segment is only known to about
        +-1 / 1096 cpd, i.e. 330-410 d for the annual peak). The PSD period is kept in period_psd.
      * fallback: when the series' own spectrum gives fewer than k such peaks, the list is filled from the peaks of
        other series given as (station, variable, source), in that order, but only with periods >= fallback_min_period
        (default 60 d, OURS). Reason: a short record (one 2.6-year segment, 2 degrees of freedom) rarely reaches
        significance at seasonal periods even when the cycle is obvious; a co-located source with more averaging
        does. Borrowed rows carry from_series = "station/variable/source".
    Returns a list of dicts: period_d (used), period_psd, cycle, spectrum, strength, snapped, from_series."""
    chosen = _pick(peaks, station, variable, source, step_d, record_d, k, snap, [], 0.0)
    for st2, var2, src2 in fallback:
        if len(chosen) >= k:
            break
        chosen = _pick(peaks, st2, var2, src2, step_d, record_d, k, snap, chosen, fallback_min_period)
    return chosen


def _src(s: str) -> str:
    return str(s).replace(" ", "").replace("_", "").lower()


def _truthy(x: pd.Series) -> pd.Series:
    return x.astype(str).str.lower().isin(["true", "1", "yes", "1.0"])


def _normalise(peaks: pd.DataFrame) -> pd.DataFrame:
    """Both peaks.csv formats -> columns station, variable, source (no spaces: 'in situ' -> 'insitu'), period_d."""
    d = peaks.copy()
    if "period_d" not in d and "period_days" in d:
        d = d.rename(columns={"period_days": "period_d"})
    d["source"] = d["source"].map(_src)
    return d


def _pick(peaks, station, variable, source, step_d, record_d, k, snap, chosen, min_period) -> list[dict]:
    chosen = list(chosen)
    tag = f"{station}/{variable}/{source}"
    d = _normalise(peaks)
    d = d[(d.station == station) & (d.variable == variable) & (d.source == _src(source))]
    if "synthetic" in d:
        syn = _truthy(d.synthetic)
        d = d[~syn] if (~syn).any() else d
    if "significant_95" in d:                                   # format announced / written from 19:41 on
        d = d[_truthy(d.significant_95)]
        if "rank" in d and d["rank"].notna().any():
            d = d.assign(strength=-pd.to_numeric(d["rank"], errors="coerce").fillna(1e9))
        else:
            d = d.assign(strength=d.get("psd_over_95_level", d.get("power")))
    elif "psd_over_95_level" in d:                              # first written format
        d = d[d.psd_over_95_level > 1]
        d = d.assign(strength=d.psd_over_95_level)
    d = d[(d.period_d >= max(2 * step_d, min_period)) & (d.period_d <= record_d)]
    d = d.sort_values("strength", ascending=False)
    for _, r in d.iterrows():
        if len(chosen) >= k:
            break
        seg = r.get("seg_days", np.nan)
        if not np.isfinite(seg):
            seg = 365.0 if str(r.get("spectrum", "")) == "anomalies" else min(1096.0, record_d)
        res = 1.0 / float(seg)
        f = 1.0 / r.period_d
        if any(abs(f - 1.0 / c["period_psd"]) < res or abs(f - 1.0 / c["period_d"]) < res for c in chosen):
            continue
        P = float(r.period_d)
        cyc = str(r.get("cycle", ""))
        snapped = False
        if snap and cyc in HARMONIC_CYCLES:
            h = HARMONIC_CYCLES[cyc]
            if abs(f - h / YEAR_D) <= res:
                P, snapped = YEAR_D / h, True
        if any(abs(P - c["period_d"]) < 1e-6 for c in chosen):
            continue
        chosen.append(dict(period_d=P, period_psd=float(r.period_d), cycle=cyc, spectrum=r.get("spectrum", ""),
                           strength=float(r.strength), snapped=snapped, from_series=tag))
    return chosen


# ======================================================================================================================
# Interannual trend (from scripts/seasonal/trend.py): OLS slope on complete annual means, no Mann-Kendall.
# Completeness rule (OURS): >= 80 % of days and each season (DJF = Jan, Feb, Dec of the same year, MAM, JJA, SON)
# on >= 50 % of its days; the current year is excluded by default.
# ======================================================================================================================
SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA",
          9: "SON", 10: "SON", 11: "SON"}


def annual_means(s: pd.Series, min_share: float = 0.8, min_season_share: float = 0.5, how: str = "mean",
                 exclude_year: int | None = None) -> pd.DataFrame:
    """Annual mean (or median) of a daily series, with columns value, n_days, share, sd, se, complete, reason.
    se = sampling error of the mean: sd of the daily anomalies (daily value minus its 31-day running mean, so the
    seasonal cycle does not count as noise) / sqrt(n_eff), n_eff from their lag-1 autocorrelation (daily values are
    not independent). It reflects day-to-day noise and gaps, not year-to-year variability."""
    s = s.dropna().astype(float)
    s = s.groupby(pd.DatetimeIndex(s.index).normalize()).mean()
    if exclude_year is None:
        exclude_year = pd.Timestamp.today().year
    rows = []
    for yr, g in s.groupby(s.index.year):
        days = 366 if pd.Timestamp(year=yr, month=12, day=31).day_of_year == 366 else 365
        share = len(g) / days
        seas = pd.Series(g.index.month.map(SEASON)).value_counts()
        full = pd.Series(pd.date_range(f"{yr}-01-01", f"{yr}-12-31").month.map(SEASON)).value_counts()
        season_share = (seas.reindex(full.index).fillna(0) / full)
        reason = ""
        if yr >= exclude_year:
            reason = "current year"
        elif share < min_share:
            reason = f"{share:.0%} of days"
        elif (season_share < min_season_share).any():
            reason = "missing season " + ",".join(season_share[season_share < min_season_share].index)
        val = g.mean() if how == "mean" else g.median()
        x = g.reindex(pd.date_range(f"{yr}-01-01", f"{yr}-12-31"))
        anom = x - x.rolling(31, center=True, min_periods=5).mean()
        a = anom.to_numpy()
        ok = np.isfinite(a[1:]) & np.isfinite(a[:-1])
        rho = float(np.corrcoef(a[1:][ok], a[:-1][ok])[0, 1]) if ok.sum() > 10 else 0.0
        rho = min(max(rho, 0.0), 0.95)
        n_eff = len(g) * (1 - rho) / (1 + rho)
        sd = float(g.std())
        sd_anom = float(np.nanstd(a)) if np.isfinite(a).sum() > 2 else sd
        rows.append(dict(year=int(yr), value=float(val), n_days=len(g), share=share, sd=sd, sd_anom=sd_anom,
                         se=sd_anom / np.sqrt(max(n_eff, 1.0)), complete=reason == "", reason=reason))
    return pd.DataFrame(rows).set_index("year") if rows else pd.DataFrame(
        columns=["value", "n_days", "share", "sd", "se", "complete", "reason"])


def linear_trend(s: pd.Series, min_years: int = 8, alpha: float = 0.05, **kw) -> dict:
    """OLS of complete annual means on year. Slope reported per decade. With fewer than min_years complete years the
    trend is not meaningful (interannual variability and the record length do not allow it): no slope is returned."""
    am = annual_means(s, **kw)
    ok = am[am.complete] if len(am) else am
    n = len(ok)
    out = dict(annual=am, n_years=n, years=(int(ok.index.min()), int(ok.index.max())) if n else None,
               meaningful=n >= min_years, slope_per_decade=np.nan, ci=(np.nan, np.nan), p_value=np.nan,
               r2=np.nan, intercept=np.nan, slope_se_per_decade=np.nan)
    if n < max(min_years, 3):
        out["note"] = (f"only {n} complete year(s) (need {min_years}): trend not meaningful" if n
                       else "no complete year")
        return out
    x = ok.index.to_numpy(float)
    y = ok.value.to_numpy(float)
    r = stats.linregress(x, y)
    tq = stats.t.ppf(1 - alpha / 2, n - 2)
    out.update(slope_per_decade=10 * r.slope, slope_se_per_decade=10 * r.stderr,
               ci=(10 * (r.slope - tq * r.stderr), 10 * (r.slope + tq * r.stderr)), p_value=float(r.pvalue),
               r2=float(r.rvalue ** 2), intercept=float(r.intercept), slope_per_year=float(r.slope), note="")
    return out


# ======================================================================================================================
# Viewer API with the quality gate
# ======================================================================================================================
ROOT = Path(__file__).resolve().parents[2]
PRECOMPUTED = ROOT / "docs" / "indicators" / "seasonal"
PEAKS_CSV = ROOT / "docs" / "indicators" / "spectra" / "peaks.csv"

# Fitted stations (same positions as scripts/validation/compare_sources.py and datahub.PLATFORMS)
STATIONS = {"EUXRo03": (43.98, 29.936), "EUXRoOB01": (44.71, 30.76), "EUXRoOB02": (44.325, 30.41),
            "EUXRoOB03": (43.977, 29.924)}

# Gate thresholds, all OURS (docs/indicators/SHORTLIST.md, section "Seasonal cycle and trend gate")
GATE = dict(
    trust_ok=("good", "usable"),       # datahub trust levels accepted
    cycle_p=0.05,                      # HAC p-value of the annual (or strongest) cycle
    cycle_r2_adj=0.5,                  # adjusted R2 of trend + cycles, weekly means
    trend_min_years=8,                 # complete years for any trend number ("indicative")
    trend_climate_years=20,            # complete years for "climate trend" wording
    trend_p=0.05,                      # p-value under which a trend is called significant
    near_station_km=5.0,               # use the precomputed station fit within this distance
    band_z=1.2816,                     # usual range = fit +- z * residual sd (z of the 10th / 90th percentile)
)
GATE_LABEL = "OURS"
GATE_WINDOW = "weekly"                 # window of the precomputed fits used by the gate (10 years of weekly means)
WEEK_D = 7.0

UNITS = {"sst": "°C", "chl": "log10(mg/m³)", "sal": "PSU", "o2": "mg/L"}
NAMES = {"sst": "sea surface temperature", "chl": "chlorophyll-a (log10)", "sal": "surface salinity",
         "o2": "surface dissolved oxygen"}
# datahub source id <-> source name used in the precomputed CSVs
_CSV_SRC = {"buoy": "insitu", "satellite": "satellite", "model": "model"}
_DH_SRC = {v: k for k, v in _CSV_SRC.items()}
_LOG_VARS = {"chl"}                    # fitted in log10 (geometric means), as in run_seasonal.py


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _dh():
    from . import datahub
    return datahub


def _var(variable: str) -> str:
    v = {"temp": "sst", "salinity": "sal", "chlorophyll": "chl", "do": "o2"}.get(variable, variable)
    if v not in UNITS:
        raise KeyError(f"seasonal analysis covers {sorted(UNITS)}, not {variable!r}")
    return v


@functools.lru_cache(maxsize=None)
def _csv(name: str) -> pd.DataFrame:
    p = PRECOMPUTED / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


@functools.lru_cache(maxsize=None)
def _peaks() -> pd.DataFrame:
    return pd.read_csv(PEAKS_CSV) if PEAKS_CSV.exists() else pd.DataFrame()


def _near_stations(lat: float, lon: float) -> list[tuple[str, float]]:
    """Fitted stations within near_station_km, longest record first (EUXRo03 2013-2023 before EUXRoOB03 2024-),
    then nearest."""
    d = [(st, _haversine_km(lat, lon, *ll)) for st, ll in STATIONS.items()]
    d = [x for x in d if x[1] <= GATE["near_station_km"]]
    m = _csv("models")

    def span(st):
        r = m[(m.station == st)] if len(m) else m
        return -(pd.to_datetime(r.end).max() - pd.to_datetime(r.start).min()).days if len(r) else 0
    return sorted(d, key=lambda x: (span(x[0]), x[1]))


def _source_order(v: str) -> list[str]:
    """datahub source ids in datahub's own "auto" preference order (SOURCES register), restricted to those fitted."""
    return [sp["id"] for sp in _dh().SOURCES.get(v, []) if sp["id"] in _CSV_SRC]


@functools.lru_cache(maxsize=256)
def _trust(v: str, dh_source: str, lat: float, lon: float, start: str, end: str) -> tuple[str, str, str, str, str]:
    """(trust, how it was read, label, origin, platform) for one source at one point, from datahub.get_series attrs
    over the last 60 days of the analysed window. If the read fails (offline, no cache), datahub's register is used
    (SOURCES trust and, for buoys, variable_trust of the station) and that is said in `how`."""
    dh = _dh()
    e = pd.Timestamp(end)
    s = max(pd.Timestamp(start), e - pd.Timedelta(days=60))
    try:
        a = dh.get_series(v, lat, lon, str(s.date()), str(e.date()), source=dh_source).attrs
        return (str(a.get("trust")), "datahub.get_series attrs", str(a.get("label", "")), str(a.get("origin", "")),
                str(a.get("platform") or ""))
    except Exception as ex:  # noqa: BLE001
        spec = next((sp for sp in dh.SOURCES.get(v, []) if sp["id"] == dh_source), {})
        t = spec.get("trust", "unknown")
        plat = ""
        if dh_source == "buoy" and hasattr(dh, "variable_trust"):
            near = [(p, _haversine_km(lat, lon, *STATIONS[p])) for p in STATIONS]
            plat = min(near, key=lambda x: x[1])[0]
            t = dh.variable_trust(plat, v)[0]
        return (t, f"datahub register (get_series failed: {type(ex).__name__})", spec.get("label", ""),
                spec.get("origin", ""), plat)


def _amp_text(v: str, A: float) -> str:
    if v in _LOG_VARS:
        return f"a factor {10 ** A:.2f} above / below the mean (log10 amplitude {A:.2f})"
    return f"{A:.2f} {UNITS[v]}"


def _empty(kind: str, v: str, reason: str, **kw) -> dict:
    out = dict(kind=kind, variable=v, unit=UNITS.get(v, ""), show=False, gate_reason=reason, gate_label=GATE_LABEL,
               thresholds={k: GATE[k] for k in GATE}, text=reason)
    out.update(kw)
    return out


# --------------------------------------------------------------------------------------------- seasonal cycle
def _cycle_gate(trust: str, p: float, r2_adj: float) -> tuple[bool, str]:
    if trust not in GATE["trust_ok"]:
        return False, (f"source trust is '{trust}' (needs good or usable): the cycle of this source is not shown")
    if not (np.isfinite(p) and p < GATE["cycle_p"]):
        return False, f"no significant seasonal cycle (p = {p:.3f}, needs < {GATE['cycle_p']}, OURS)"
    if not (np.isfinite(r2_adj) and r2_adj >= GATE["cycle_r2_adj"]):
        return False, (f"the seasonal cycle explains too little of the variation (adjusted R2 {r2_adj:.2f}, "
                       f"needs >= {GATE['cycle_r2_adj']}, OURS): the usual-range band would be misleading")
    return True, (f"passes the gate: trust {trust}, cycle p {'< 0.001' if p < 0.001 else f'= {p:.3f}'}, adjusted "
                  f"R2 {r2_adj:.2f} (thresholds OURS)")


def _cycle_from_rows(cyc: pd.DataFrame, mod: pd.Series) -> dict:
    cycles = []
    for _, r in cyc.iterrows():
        cycles.append(dict(period_d=float(r.period_d), cycle=str(r.cycle) if pd.notna(r.cycle) else "",
                           amplitude=float(r.amplitude), amplitude_ci=(float(r.amp_ci_lo), float(r.amp_ci_hi)),
                           amplitude_raw=float(r.amplitude_raw), t_max_d=float(r.t_max_d),
                           max_date=str(r.max_date), p_value=float(r.p_hac),
                           period_from=str(r.get("period_from", ""))))
    return dict(cycles=cycles, r2_adj=float(mod.r2_adj), resid_sd=float(mod.resid_sd), n=int(mod.n),
                start=str(mod.start), end=str(mod.end), intercept=float(mod.intercept))


def _cycle_from_fit(f: dict) -> dict:
    cycles = [dict(period_d=c["period_d"], cycle="", amplitude=c["amplitude"], amplitude_ci=tuple(c["amplitude_ci"]),
                   amplitude_raw=c["amplitude_raw"], t_max_d=c["t_max_d"], max_date=c["max_date"],
                   p_value=c["p_value"], period_from="") for c in f["cycles"]]
    m = f["model"]
    return dict(cycles=cycles, r2_adj=m["r2_adj"], resid_sd=m["resid_sd"], n=f["n"], start=f"{f['start']:%Y-%m-%d}",
                end=f"{f['end']:%Y-%m-%d}", intercept=m["intercept"])


def _main_cycle(cycles: list[dict]) -> dict | None:
    ann = [c for c in cycles if abs(c["period_d"] - YEAR_D) < 1]
    return ann[0] if ann else (cycles[0] if cycles else None)


def _cycle_k(c: list[dict], k: int) -> dict | None:
    m = [x for x in c if abs(x["period_d"] - YEAR_D / k) < 1]
    return m[0] if m else None


def _cycle_dict(v, station, dist, dh_source, base, trust_info, how) -> dict:
    trust, trust_how, label, origin, platform = trust_info
    main = _main_cycle(base["cycles"])
    p = main["p_value"] if main else float("nan")
    show, reason = _cycle_gate(trust, p, base["r2_adj"]) if main else (False, "no cycle could be fitted")
    ann, semi = _cycle_k(base["cycles"], 1), _cycle_k(base["cycles"], 2)

    def brief(c):
        return None if c is None else dict(amplitude=c["amplitude"], ci=c["amplitude_ci"], max_date=c["max_date"],
                                           p_value=c["p_value"], period_d=c["period_d"])
    out = dict(kind="seasonal_cycle", variable=v, unit=UNITS[v], station=station, distance_km=round(dist, 2),
               source=dh_source, source_label=label, origin=origin, platform=platform or None, trust=trust,
               trust_from=trust_how, method=how, window=f"weekly means {base['start']} to {base['end']}",
               n=base["n"], annual=brief(ann), semi_annual=brief(semi),
               max_date=ann["max_date"] if ann else (main["max_date"] if main else None),
               periods_d=[round(c["period_d"], 2) for c in base["cycles"]], cycles=base["cycles"],
               r2_adj=base["r2_adj"], resid_sd=base["resid_sd"], show=show, gate_reason=reason,
               gate_label=GATE_LABEL, thresholds={k: GATE[k] for k in ("trust_ok", "cycle_p", "cycle_r2_adj")},
               _base=base)
    if show and ann:
        lo, hi = ann["amplitude_ci"]
        txt = (f"{NAMES[v].capitalize()} ({origin or dh_source}) follows a yearly cycle of about "
               f"{_amp_text(v, ann['amplitude'])} around its mean (95 % CI {lo:.2f} to {hi:.2f}), highest around "
               f"{ann['max_date']}")
        if semi and semi["p_value"] < GATE["cycle_p"]:
            txt += f", with a half-year component of {_amp_text(v, semi['amplitude'])}"
        txt += (f". The cycle explains {base['r2_adj']:.0%} of the weekly variation ({out['window']}, "
                f"{station or 'this point'}).")
    else:
        txt = f"Seasonal cycle not shown: {reason}."
    out["text"] = txt
    return out


def seasonal_cycle(variable: str, lat: float, lon: float, source: str = "auto") -> dict:
    """Seasonal cycle at a point with the quality gate. source: "auto" (datahub's preference order, first source that
    passes the trust gate) or a datahub source id ("satellite", "model", "buoy").
    Keys: variable, unit (log10(mg/m³) for chl), station, distance_km, source, source_label, origin, platform, trust,
    trust_from, method (precomputed / fitted on the fly), window, n, annual and semi_annual ({amplitude, ci, max_date,
    p_value, period_d} or None), max_date, periods_d (the 3 strongest significant PSD periods), cycles (all),
    r2_adj, resid_sd, show, gate_reason, gate_label ("OURS"), thresholds, text (plain sentence)."""
    v = _var(variable)
    res = _evaluate(v, float(lat), float(lon), source)
    res = {k: x for k, x in res.items() if k != "_base"}
    return res


def _evaluate(v: str, lat: float, lon: float, source: str) -> dict:
    """seasonal_cycle with the internal _base (for usual_range)."""
    sources = _source_order(v) if source == "auto" else [source]
    if any(s not in _CSV_SRC for s in sources):
        return _empty("seasonal_cycle", v, f"source {source!r} has no seasonal analysis (use satellite, model, buoy)")
    results = []
    for st, dist in _near_stations(lat, lon):
        mod, cyc = _csv("models"), _csv("cycles")
        for dh_src in sources:
            cs = _CSV_SRC[dh_src]
            m = mod[(mod.station == st) & (mod.variable == v) & (mod.source == cs) & (mod.window == GATE_WINDOW)]
            if not len(m):
                continue
            m = m.iloc[0]
            c = cyc[(cyc.station == st) & (cyc.variable == v) & (cyc.source == cs) & (cyc.window == GATE_WINDOW)]
            base = _cycle_from_rows(c, m)
            ti = _trust(v, dh_src, *STATIONS[st], base["start"], base["end"])
            results.append(_cycle_dict(v, st, dist, dh_src, base, ti,
                                       "precomputed (scripts/seasonal/run_seasonal.py, docs/indicators/seasonal)"))
            if source == "auto" and ti[0] in GATE["trust_ok"]:
                break                                       # datahub order: first trusted source wins
        if results:
            break
    if not results:
        for dh_src in sources:
            r = _fit_on_the_fly(v, lat, lon, dh_src)
            results.append(r)
            if r.get("show"):
                break
    if not results:
        return _empty("seasonal_cycle", v, "no fitted station nearby and no source for this variable")
    if source == "auto":
        ok = [r for r in results if r.get("trust") in GATE["trust_ok"]]
        return ok[0] if ok else results[0]
    return results[0]


@functools.lru_cache(maxsize=64)
def _series(v: str, lat: float, lon: float, dh_source: str, start: str, end: str) -> pd.DataFrame:
    return _dh().get_series(v, lat, lon, start, end, source=dh_source)


def _fit_on_the_fly(v: str, lat: float, lon: float, dh_src: str) -> dict:
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=10)
    try:
        df = _series(v, lat, lon, dh_src, str(start.date()), str(end.date()))
    except Exception as ex:  # noqa: BLE001
        return _empty("seasonal_cycle", v, f"no cached {dh_src} record at this point ({type(ex).__name__})",
                      source=dh_src, trust=None)
    s = df[v].dropna()
    if v in _LOG_VARS:
        s = np.log10(s.where(s > 0)).dropna()
    agg = aggregate(s, "W")
    if len(agg) < 2 * 52:
        return _empty("seasonal_cycle", v, f"record too short for a seasonal fit ({len(agg)} weeks, needs 2 years)",
                      source=dh_src, trust=df.attrs.get("trust"))
    rec = float((agg.index[-1] - agg.index[0]).days)
    near = min(STATIONS, key=lambda st: _haversine_km(lat, lon, *STATIONS[st]))
    cs = _CSV_SRC[dh_src]
    fb = [(near, v, o) for o in ("satellite", "model", "insitu") if o != cs] + [(o, v, cs) for o in STATIONS]
    pk = _peaks()
    sel = select_periods(pk, near, v, cs, step_d=WEEK_D, record_d=rec, k=3, fallback=fb) if len(pk) else []
    periods = [c["period_d"] for c in sel] or [YEAR_D, YEAR_D / 2]
    f = fit_harmonics(agg.value, periods, bin_days=WEEK_D)
    base = _cycle_from_fit(f)
    for c, sc in zip(base["cycles"], sel):
        c["period_from"] = sc["from_series"]
    a = df.attrs
    ti = (str(a.get("trust")), "datahub.get_series attrs", str(a.get("label", "")), str(a.get("origin", "")),
          str(a.get("platform") or ""))
    dist = _haversine_km(lat, lon, *STATIONS[near])
    out = _cycle_dict(v, None, dist, dh_src, base, ti, f"fitted on the fly (periods from {near} in peaks.csv)")
    out["distance_km"] = None
    return out


# ---------------------------------------------------------------------------------------------- usual range
def usual_range(variable: str, lat: float, lon: float, dates, source: str = "auto") -> pd.DataFrame:
    """The "usual range" band: mean seasonal cycle (record mean + fitted cycles, no trend) and fit +- z * residual sd
    of the weekly fit (z = 1.28, about the 10th-90th percentile band; OURS). Columns fit, lo, hi, in the variable's
    unit (chlorophyll back-transformed to mg/m³, so the band is geometric). attrs: the seasonal_cycle dict (without
    the cycle list), including show and gate_reason; when show is False the columns are still filled, and the viewer
    should display gate_reason instead of the band."""
    v = _var(variable)
    res = _evaluate(v, float(lat), float(lon), source)
    d = pd.DatetimeIndex(pd.to_datetime(dates))
    base = res.get("_base")
    if base is None or not base.get("cycles"):
        out = pd.DataFrame(dict(fit=np.nan, lo=np.nan, hi=np.nan), index=d)
    else:
        t0 = pd.Timestamp(year=pd.Timestamp(base["start"]).year, month=1, day=1)
        t = ((d - t0) / pd.Timedelta(days=1)).to_numpy(float)
        # the CSV start is the first weekly bin, so t0 matches the fit's t0 (1 January of the first year)
        y = np.full(len(d), base["intercept"])
        for c in base["cycles"]:
            y = y + c["amplitude_raw"] * np.cos(2 * np.pi * (t - c["t_max_d"]) / c["period_d"])
        z = GATE["band_z"] * base["resid_sd"]
        lo, hi = y - z, y + z
        if v in _LOG_VARS:
            y, lo, hi = 10 ** y, 10 ** lo, 10 ** hi
        out = pd.DataFrame(dict(fit=y, lo=lo, hi=hi), index=d)
    out.index.name = "time"
    meta = {k: x for k, x in res.items() if k not in ("_base", "cycles")}
    meta["unit"] = "mg/m³" if v in _LOG_VARS else UNITS[v]
    meta["band"] = f"fit +- {GATE['band_z']:.2f} x weekly residual sd (about p10-p90; OURS)"
    out.attrs = meta
    return out


# ---------------------------------------------------------------------------------------------- long-term trend
def _trend_gate(trust: str, n: int, p: float) -> tuple[bool, str, str]:
    """(show, gate_reason, wording level) for a trend."""
    if trust not in GATE["trust_ok"]:
        return False, f"source trust is '{trust}' (needs good or usable): no trend shown", "none"
    if n < GATE["trend_min_years"]:
        return False, (f"not enough years yet: {n} complete year(s), a trend needs at least "
                       f"{GATE['trend_min_years']} (OURS)"), "none"
    level = "climate" if n >= GATE["trend_climate_years"] else "indicative"
    sig = np.isfinite(p) and p < GATE["trend_p"]
    reason = (f"{n} complete years: " + ("climate trend" if level == "climate" else
                                          f"indicative (fewer than {GATE['trend_climate_years']} years)")
              + ("" if sig else f"; not significant (p = {p:.2f})") + " (thresholds OURS)")
    return True, reason, level


def _trend_row(v: str, st: str, cs: str) -> pd.Series | None:
    """Long record (trends_long.csv, scripts/seasonal/fetch_long_sst.py) when present, else trends.csv."""
    for name in ("trends_long", "trends"):
        t = _csv(name)
        if not len(t):
            continue
        r = t[(t.station == st) & (t.variable == v) & (t.source == cs)]
        if len(r):
            r = r.iloc[0].copy()
            r["table"] = name
            return r
    return None


def long_term_trend(variable: str, lat: float, lon: float, source: str = "auto") -> dict:
    """Linear trend of complete annual means with the gate. Keys: variable, unit (per decade), station, distance_km,
    source, source_label, origin, trust, trust_from, slope_per_decade, ci (95 %), p_value, n_years, years (first,
    last), enough_years (>= 8), level ("none" / "indicative" / "climate"), significant, text, show, gate_reason,
    gate_label ("OURS"), table (trends_long = 1982 onward satellite record, trends = analysed window)."""
    v = _var(variable)
    sources = _source_order(v) if source == "auto" else [source]
    results = []
    for st, dist in _near_stations(float(lat), float(lon)):
        for dh_src in sources:
            if dh_src not in _CSV_SRC:
                continue
            r = _trend_row(v, st, _CSV_SRC[dh_src])
            if r is None:
                continue
            m = _csv("models")
            mm = m[(m.station == st) & (m.variable == v) & (m.source == _CSV_SRC[dh_src])]
            start = str(mm.start.min()) if len(mm) else "2014-01-01"
            end = str(mm.end.max()) if len(mm) else "2023-12-31"
            if r["table"] == "trends_long" and isinstance(r.get("record"), str):
                start, end = r["record"].split(" to ")
            ti = _trust(v, dh_src, *STATIONS[st], start, end)
            results.append(_trend_dict(v, st, dist, dh_src, r, ti))
            if results[-1]["show"]:
                break                                       # first source (datahub order) with a shown trend
        if results:
            break
    if not results:
        for dh_src in sources:
            if dh_src in _CSV_SRC:
                results.append(_trend_on_the_fly(v, float(lat), float(lon), dh_src))
                if results[-1].get("show"):
                    break
    if not results:
        return _empty("long_term_trend", v, "no source for this variable", enough_years=False)
    ok = [r for r in results if r.get("show")] or [r for r in results if r.get("trust") in GATE["trust_ok"]]
    return (ok or results)[0]


def _trend_dict(v, st, dist, dh_src, r, ti) -> dict:
    trust, trust_how, label, origin, platform = ti
    n = int(r.n_years) if pd.notna(r.n_years) else 0
    p = float(r.p_value) if pd.notna(r.p_value) else float("nan")
    years = tuple(int(x) for x in str(r.years).split("-")) if isinstance(r.years, str) and r.years else None
    show, reason, level = _trend_gate(trust, n, p)
    slope = float(r.slope_per_decade) if pd.notna(r.slope_per_decade) else float("nan")
    ci = (float(r.ci_lo), float(r.ci_hi)) if pd.notna(r.ci_lo) else (float("nan"), float("nan"))
    sig = bool(np.isfinite(p) and p < GATE["trend_p"])
    out = dict(kind="long_term_trend", variable=v, unit=f"{UNITS[v]} per decade", station=st,
               distance_km=round(dist, 2) if dist is not None else None, source=dh_src, source_label=label,
               origin=origin, platform=platform or None, trust=trust, trust_from=trust_how,
               slope_per_decade=slope if show else float("nan"), ci=ci if show else (float("nan"), float("nan")),
               p_value=p if show else float("nan"), n_years=n, years=years,
               enough_years=n >= GATE["trend_min_years"], level=level, significant=sig if show else False,
               show=show, gate_reason=reason, gate_label=GATE_LABEL, table=str(r.get("table", "")),
               thresholds={k: GATE[k] for k in ("trust_ok", "trend_min_years", "trend_climate_years", "trend_p")})
    out["text"] = _trend_text(out)
    return out


def _trend_text(o: dict) -> str:
    v = o["variable"]
    if not o["show"]:
        return f"Long-term trend not shown: {o['gate_reason']}."
    y0, y1 = o["years"] if o["years"] else ("?", "?")
    what = "Climate trend" if o["level"] == "climate" else "Indicative trend"
    s = (f"{what} of {NAMES[v]} ({o['origin'] or o['source']}, {y0}-{y1}, {o['n_years']} complete years): "
         f"{o['slope_per_decade']:+.2f} {o['unit']} (95 % CI {o['ci'][0]:+.2f} to {o['ci'][1]:+.2f}, "
         f"p = {o['p_value']:.2f}).")
    if not o["significant"]:
        s += " Not significant: year-to-year variability is as large as the change."
    if o["level"] == "indicative":
        s += f" Fewer than {GATE['trend_climate_years']} years: read it as indicative, not as a climate trend."
    return s


def _trend_on_the_fly(v: str, lat: float, lon: float, dh_src: str) -> dict:
    end = pd.Timestamp(year=pd.Timestamp.today().year - 1, month=12, day=31)
    start = pd.Timestamp(year=end.year - 9, month=1, day=1)
    try:
        df = _series(v, lat, lon, dh_src, str(start.date()), str(end.date()))
    except Exception as ex:  # noqa: BLE001
        return _empty("long_term_trend", v, f"no cached {dh_src} record at this point ({type(ex).__name__})",
                      source=dh_src, trust=None, enough_years=False)
    s = df[v].dropna()
    if v in _LOG_VARS:
        s = np.log10(s.where(s > 0)).dropna()
    tr = linear_trend(s, min_years=GATE["trend_min_years"])
    r = pd.Series(dict(n_years=tr["n_years"], p_value=tr["p_value"], slope_per_decade=tr["slope_per_decade"],
                       ci_lo=tr["ci"][0], ci_hi=tr["ci"][1],
                       years=f"{tr['years'][0]}-{tr['years'][1]}" if tr["years"] else "", table="on the fly"))
    a = df.attrs
    ti = (str(a.get("trust")), "datahub.get_series attrs", str(a.get("label", "")), str(a.get("origin", "")),
          str(a.get("platform") or ""))
    out = _trend_dict(v, None, None, dh_src, r, ti)
    return out


# ---------------------------------------------------------------------------------------------- Methods page
def gate_summary(from_file: bool = False) -> pd.DataFrame:
    """One row per station x variable x source of the precomputed analysis: trust, cycle p and adjusted R2 (weekly
    means), complete years, and which gate passes, with the reason. Thresholds OURS.
    Live, it reads trust through about 40 get_series calls (1-2 minutes on a cold cache). from_file=True reads the
    snapshot docs/indicators/seasonal/gate_summary.csv (scripts/seasonal/write_gate_summary.py) when it exists."""
    if from_file and (PRECOMPUTED / "gate_summary.csv").exists():
        return pd.read_csv(PRECOMPUTED / "gate_summary.csv")
    rows = []
    mod, cyc = _csv("models"), _csv("cycles")
    for st, ll in STATIONS.items():
        for v in UNITS:
            for dh_src, cs in _CSV_SRC.items():
                m = mod[(mod.station == st) & (mod.variable == v) & (mod.source == cs) & (mod.window == GATE_WINDOW)]
                if not len(m):
                    continue
                m = m.iloc[0]
                c = cyc[(cyc.station == st) & (cyc.variable == v) & (cyc.source == cs) & (cyc.window == GATE_WINDOW)]
                base = _cycle_from_rows(c, m)
                ti = _trust(v, dh_src, *ll, base["start"], base["end"])
                cd = _cycle_dict(v, st, 0.0, dh_src, base, ti, "precomputed")
                r = _trend_row(v, st, cs)
                td = _trend_dict(v, st, 0.0, dh_src, r, ti) if r is not None else None
                main = _main_cycle(base["cycles"])
                rows.append(dict(station=st, variable=v, source=dh_src, trust=ti[0], trust_from=ti[1],
                                 cycle_p=main["p_value"] if main else np.nan, r2_adj=base["r2_adj"],
                                 cycle_show=cd["show"], cycle_reason=cd["gate_reason"],
                                 n_years=td["n_years"] if td else 0, trend_level=td["level"] if td else "none",
                                 trend_show=td["show"] if td else False,
                                 trend_reason=td["gate_reason"] if td else "no trend computed",
                                 trend_table=td["table"] if td else ""))
    return pd.DataFrame(rows)
