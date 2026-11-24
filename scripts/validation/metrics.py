"""Pairwise agreement metrics for source validation (in situ vs satellite vs model).

All functions take two aligned 1-D arrays: x = reference (usually in situ), y = the other source.
Pure numpy, no network: tested in tests/test_validation.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
SEASON_NAME = {"DJF": "winter (DJF)", "MAM": "spring (MAM)", "JJA": "summer (JJA)", "SON": "autumn (SON)"}


def season_of(index) -> np.ndarray:
    return np.array([SEASONS[m] for m in pd.DatetimeIndex(index).month])


def pair_metrics(x, y, min_n: int = 3) -> dict:
    """n, mean_ref, mean_other, bias (y - x), RMSE, unbiased RMSE, Pearson r, R2, OLS slope / intercept of y on x,
    std of both and the normalised std (std_y / std_x, for the Taylor diagram)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = int(len(x))
    out = dict(n=n, mean_ref=np.nan, mean_other=np.nan, bias=np.nan, rmse=np.nan, ubrmse=np.nan, r=np.nan, r2=np.nan,
               slope=np.nan, intercept=np.nan, std_ref=np.nan, std_other=np.nan, std_ratio=np.nan)
    if n == 0:
        return out
    d = y - x
    out.update(mean_ref=float(x.mean()), mean_other=float(y.mean()), bias=float(d.mean()),
               rmse=float(np.sqrt(np.mean(d ** 2))))
    # unbiased (centred) RMSE: RMSE with the mean bias removed; ubRMSE^2 = RMSE^2 - bias^2
    out["ubrmse"] = float(np.sqrt(max(out["rmse"] ** 2 - out["bias"] ** 2, 0.0)))
    if n >= min_n and np.std(x) > 0 and np.std(y) > 0:
        r = float(np.corrcoef(x, y)[0, 1])
        slope, intercept = np.polyfit(x, y, 1)
        out.update(r=r, r2=r * r, slope=float(slope), intercept=float(intercept), std_ref=float(np.std(x)),
                   std_other=float(np.std(y)), std_ratio=float(np.std(y) / np.std(x)))
    return out


def metrics_by_season(x: pd.Series, y: pd.Series, min_n: int = 3) -> pd.DataFrame:
    """pair_metrics for all days and for each season. x, y share a DatetimeIndex."""
    j = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    rows = [{"season": "all", **pair_metrics(j["x"], j["y"], min_n)}]
    if len(j):
        s = season_of(j.index)
        for k in SEASON_ORDER:
            m = s == k
            rows.append({"season": k, **pair_metrics(j["x"][m], j["y"][m], min_n)})
    return pd.DataFrame(rows)


def despike(s: pd.Series, threshold: float, window: int = 15, min_periods: int = 5, log: bool = False) -> pd.Series:
    """Boolean mask of daily values to KEEP: drop values farther than `threshold` from the centred running median of
    the series itself (window in days, on a daily grid). Self-referenced: no other source is used, so the QC does not
    bias the comparison towards satellite or model. log=True works in log10 (for chlorophyll)."""
    v = np.log10(s.where(s > 0)) if log else s.astype(float)
    full = v.reindex(pd.date_range(v.index.min(), v.index.max(), freq="D"))
    med = full.rolling(window, center=True, min_periods=min_periods).median().reindex(v.index)
    keep = ~((v - med).abs() > threshold)
    return keep & v.notna()


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and np.isfinite(sd) else s * np.nan


def spearman(x, y) -> float:
    x, y = pd.Series(np.asarray(x, float)), pd.Series(np.asarray(y, float))
    ok = x.notna() & y.notna()
    if ok.sum() < 3:
        return np.nan
    return float(x[ok].rank().corr(y[ok].rank()))


def gap_share(s: pd.Series, start, end) -> float:
    """Share of days in [start, end] without a value (0 = complete, 1 = empty)."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    days = (end - start).days + 1
    if days <= 0:
        return np.nan
    v = s.dropna()
    v = v[(v.index >= start) & (v.index <= end)]
    return float(1 - v.index.normalize().nunique() / days)
