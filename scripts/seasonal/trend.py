"""Interannual linear trend on annual means (deliberately simple: OLS slope only, no Mann-Kendall).

  * annual_means(series, ...)   daily series -> complete calendar years only (>= 80 % of days and every season
                                present), with n days and the standard error of each mean
  * linear_trend(series, ...)   -> dict: slope per decade with 95 % CI, p-value, R2, n years; or, with fewer than
                                min_years complete years, meaningful=False and no slope

Completeness rule (OURS): a year counts when at least 80 % of its days have a value and each season (DJF = Jan, Feb
and Dec of the same calendar year, MAM, JJA, SON) has values on at least 50 % of its days. The current (incomplete)
year is excluded by default.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

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
