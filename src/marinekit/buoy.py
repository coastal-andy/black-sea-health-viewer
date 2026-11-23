"""Smart-buoy time-series QC, anomaly detection and event alerts.

    df = io.load_table("buoy.csv")
    df = buoy.qc(df)                    # range + spike QC, adds <var>_qc flag columns
    z  = buoy.robust_z(df, "temp")      # rolling robust z-score
    ev = buoy.detect_events(df)         # hypoxia / bloom / heatwave-like / anomalies -> tidy table
    buoy.alert_text(ev)                 # plain-language lines for a dashboard or bulletin

Thresholds are defaults for the Black Sea; adjust them once NIMRD tells us what they use.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Plausible physical ranges (Black Sea, surface/near-surface). Outside -> flagged bad.
RANGES = {
    "temp": (-2, 35),
    "sal": (0, 40),  # Black Sea surface ~17-18 PSU
    "do": (0, 20),  # mg/L
    "do_sat": (0, 250),  # %
    "chl": (0, 300),  # µg/L
    "turb": (0, 2000),  # NTU
    "ph": (6.5, 9.8),
    "wave_height": (0, 15),
    "wind_speed": (0, 60),
}

LABELS = {
    "temp": "Water temperature", "sal": "Salinity", "do": "Dissolved oxygen", "do_sat": "Oxygen saturation",
    "chl": "Chlorophyll-a", "turb": "Turbidity", "ph": "pH", "wave_height": "Wave height",
    "wind_speed": "Wind speed", "cond": "Conductivity", "air_temp": "Air temperature",
}

# Generic robust-z anomaly check only on "smooth" state variables; skewed ones (chl, turb, waves, wind)
# are naturally spiky and already have their own event rules.
ANOMALY_VARS = {"temp", "sal", "do", "do_sat", "ph", "cond"}

# MSFD descriptor each event type speaks to (useful for the governance angle of the pitch)
MSFD = {"hypoxia": "D5 Eutrophication", "bloom": "D5 Eutrophication", "heatwave": "D1 Biodiversity / climate",
        "anomaly": "-", "low_ph": "D5 / acidification", "turbidity": "D5 / D6 Seafloor integrity"}


def numeric_vars(df: pd.DataFrame) -> list[str]:
    skip = {"lat", "lon", "depth"}
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in skip and not c.endswith("_qc")]


def oxygen_to_mgl(s: pd.Series) -> pd.Series:
    """Guess DO units and convert to mg/L. µmol/L (median > 25) -> ×0.032; ml/L is not auto-detected."""
    med = s.median()
    if med is not None and med > 25:  # µmol/L or µmol/kg
        return s * 0.032
    return s


def qc(df: pd.DataFrame, spike_window: str = "6h", spike_z: float = 6.0) -> pd.DataFrame:
    """Flag out-of-range values and single-point spikes. Bad values become NaN; flags in <var>_qc.

    Flag codes: 1 good, 3 suspect (spike), 4 bad (out of range), 9 missing (roughly following IOOS/QARTOD).
    """
    out = df.copy()
    if "do" in out:
        out["do"] = oxygen_to_mgl(out["do"])
    for v in numeric_vars(out):
        flag = pd.Series(1, index=out.index, dtype="int8")
        flag[out[v].isna()] = 9
        if v in RANGES:
            lo, hi = RANGES[v]
            bad = (out[v] < lo) | (out[v] > hi)
            flag[bad] = 4
            out.loc[bad, v] = np.nan
        if isinstance(out.index, pd.DatetimeIndex):
            z = robust_z(out, v, window=spike_window)
            spike = z.abs() > spike_z
            flag[spike & (flag == 1)] = 3
            out.loc[spike, v] = np.nan
        out[f"{v}_qc"] = flag
    return out


def robust_z(df: pd.DataFrame, var: str, window: str = "24h") -> pd.Series:
    """Rolling robust z-score: (x - rolling median) / (1.4826 * rolling MAD). Time-based window."""
    s = df[var].astype(float)
    med = s.rolling(window, center=True, min_periods=3).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=3).median()
    scale = 1.4826 * mad
    scale = scale.where(scale > 1e-9, np.nan).fillna(s.std() or 1.0)
    return (s - med) / scale


def _runs(mask: pd.Series, min_duration: pd.Timedelta, merge_gap: pd.Timedelta) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Contiguous True runs in a time-indexed boolean Series, merged across small gaps."""
    m = mask.fillna(False).astype(bool)
    if not m.any():
        return []
    t = m.index[m]
    runs, start, prev = [], t[0], t[0]
    for ti in t[1:]:
        if ti - prev > merge_gap:
            runs.append((start, prev))
            start = ti
        prev = ti
    runs.append((start, prev))
    return [(a, b) for a, b in runs if (b - a) >= min_duration]


@dataclass
class Thresholds:
    hypoxia_mgl: float = 2.0            # classic hypoxia threshold
    low_oxygen_mgl: float = 4.0         # "stress" level for benthic fauna
    bloom_chl: float = 10.0             # µg/L absolute
    bloom_ratio: float = 3.0            # or N x the 7-day rolling median
    heatwave_pct: float = 90.0          # Hobday-style percentile (series-relative proxy)
    heatwave_days: int = 5
    low_ph: float = 7.8
    turbidity_ntu: float = 50.0
    anomaly_z: float = 5.0


def detect_events(df: pd.DataFrame, th: Thresholds | None = None, anomaly_vars: list[str] | None = None) -> pd.DataFrame:
    """Rule-based events + generic robust-z anomalies. Returns one row per event, newest first."""
    th = th or Thresholds()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("detect_events needs a DatetimeIndex (use io.load_table).")
    step = df.index.to_series().diff().median()
    step = step if pd.notna(step) else pd.Timedelta("1h")
    merge = max(step * 3, pd.Timedelta("1h"))
    rows = []

    def add(kind, var, a, b, sev, extreme="min", note=""):
        seg = df.loc[a:b, var]
        peak_t = seg.idxmin() if extreme == "min" else seg.idxmax()
        rows.append(dict(kind=kind, variable=var, start=a, end=b, duration_h=round((b - a).total_seconds() / 3600, 1),
                         peak=round(float(seg.loc[peak_t]), 3), peak_time=peak_t, severity=sev, msfd=MSFD.get(kind, "-"), note=note))

    if "do" in df:
        for a, b in _runs(df["do"] < th.hypoxia_mgl, pd.Timedelta("1h"), merge):
            add("hypoxia", "do", a, b, "high", "min", f"DO < {th.hypoxia_mgl} mg/L")
        hyp = pd.Series(False, index=df.index)
        for r in rows:
            hyp.loc[r["start"]:r["end"]] = True
        for a, b in _runs((df["do"] < th.low_oxygen_mgl) & ~hyp, pd.Timedelta("2h"), merge):
            add("hypoxia", "do", a, b, "medium", "min", f"DO < {th.low_oxygen_mgl} mg/L (low oxygen)")

    if "chl" in df:
        base = df["chl"].rolling("7D", min_periods=6).median()
        m = (df["chl"] > th.bloom_chl) | (df["chl"] > th.bloom_ratio * base)
        for a, b in _runs(m, pd.Timedelta("6h"), merge):
            sev = "high" if df.loc[a:b, "chl"].max() > 2 * th.bloom_chl else "medium"
            add("bloom", "chl", a, b, sev, "max", "possible algal bloom")

    if "temp" in df:
        daily = df["temp"].resample("1D").mean()
        thr = np.nanpercentile(daily, th.heatwave_pct) if daily.notna().sum() > 10 else np.inf
        for a, b in _runs(daily > thr, pd.Timedelta(days=th.heatwave_days - 1), pd.Timedelta("1D")):
            add("heatwave", "temp", a, b + pd.Timedelta("23h59min"), "medium", "max",
                f"daily mean > p{th.heatwave_pct:.0f} ({thr:.1f} °C) for ≥{th.heatwave_days} d (series-relative proxy)")

    if "ph" in df:
        for a, b in _runs(df["ph"] < th.low_ph, pd.Timedelta("2h"), merge):
            add("low_ph", "ph", a, b, "medium", "min", f"pH < {th.low_ph}")

    if "turb" in df:
        for a, b in _runs(df["turb"] > th.turbidity_ntu, pd.Timedelta("2h"), merge):
            add("turbidity", "turb", a, b, "medium", "max", f"turbidity > {th.turbidity_ntu} NTU")

    for v in anomaly_vars or [v for v in numeric_vars(df) if v in ANOMALY_VARS]:
        z = robust_z(df, v)
        for a, b in _runs(z.abs() > th.anomaly_z, pd.Timedelta(0), merge):
            seg = z.loc[a:b]
            add("anomaly", v, a, b, "low", "max" if seg.mean() > 0 else "min", f"|robust z| > {th.anomaly_z}")

    ev = pd.DataFrame(rows)
    if ev.empty:
        return pd.DataFrame(columns=["kind", "variable", "start", "end", "duration_h", "peak", "peak_time", "severity", "msfd", "note"])
    order = {"high": 0, "medium": 1, "low": 2}
    return ev.sort_values(["start"], ascending=False).assign(_o=ev.severity.map(order)).sort_values(["_o", "start"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)


def alert_text(events: pd.DataFrame, units: dict | None = None, max_items: int = 20, severity_prefix: bool = True) -> list[str]:
    """Plain-language alert lines a beach manager or mussel farmer can read.

    One line per event, in the same order as `events`. With severity_prefix the line starts with "HIGH: " etc.
    """
    units = {"do": "mg/L", "chl": "µg/L", "temp": "°C", "turb": "NTU", "ph": "", "sal": "PSU", **(units or {})}
    out = []
    for _, e in events.head(max_items).iterrows():
        lab = LABELS.get(e.variable, e.variable)
        when = f"{e.start:%d %b %H:%M} → {e.end:%d %b %H:%M}" if e.duration_h > 0 else f"{e.start:%d %b %H:%M}"
        u = units.get(e.variable, "")
        what = {
            "hypoxia": f"Low oxygen: {lab} fell to {e.peak} {u}",
            "bloom": f"Possible algal bloom: chlorophyll peaked at {e.peak} {u}",
            "heatwave": f"Warm-water episode: temperature peaked at {e.peak} {u}",
            "low_ph": f"Low pH: reached {e.peak}",
            "turbidity": f"High turbidity: {e.peak} {u}",
            "anomaly": f"Unusual reading in {lab.lower()}: {e.peak} {u}",
        }.get(e.kind, f"{e.kind}: {lab} {e.peak} {u}")
        prefix = f"{str(e.severity).upper()}: " if severity_prefix else ""
        out.append(f"{prefix}{what} ({when}, {e.duration_h} h). {e.note}")
    return out


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """Daily mean/min/max for each variable: handy for the chat tool and bulletins."""
    vs = numeric_vars(df)
    return df[vs].resample("1D").agg(["mean", "min", "max"]).round(3)
