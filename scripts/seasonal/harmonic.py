"""Seasonal / cycle analysis: OLS (or WLS) harmonic regression with periods taken from the power spectra.

    y(t) = a0 + b t + sum_k [ a_k cos(2 pi t / P_k) + b_k sin(2 pi t / P_k) ]

Pure functions (numpy / scipy / pandas only, no statsmodels), written so they can later move into a marinekit analysis
package for a Research page:

  * aggregate(series, freq, how)           daily series -> weekly or monthly means (or medians) with n and SE
  * fit_harmonics(series, periods, ...)    one fit -> dict (cycles with amplitude, phase, SE, 95 % CI, p; model stats;
                                           residual checks; HAC / Newey-West standard errors)
  * compare_nested(series, periods, ...)   models with 0, 1, ..., K cycles -> how much each cycle adds (F-test, HAC
                                           Wald test, AIC, BIC)
  * select_periods(peaks, ...)             the K strongest significant, fittable periods from the PSD step's peaks.csv

Time origin: t = days since 1 January of the first year in the series, so a phase converts directly to a calendar date.
Periods are never hard-coded here: they are always a parameter.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

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
