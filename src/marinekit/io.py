"""Load whatever tabular data the organisers hand us into a tidy, time-indexed DataFrame.

Supports CSV/TSV/TXT, Excel, Parquet, JSON and NetCDF. Column names are normalised to
canonical short names (time, lat, lon, depth, temp, sal, do, chl, turb, ph, ...) so the
rest of the toolkit does not care what the source called them. Original names are kept
in ``df.attrs["original_columns"]`` and units (if found in headers) in ``df.attrs["units"]``.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# canonical name -> regex patterns matched against a cleaned, lower-case header
ALIASES: dict[str, list[str]] = {
    "time": [r"^time$", r"^datetime$", r"^date_?time$", r"^timestamp$", r"^date$", r"^utc", r"^time_?utc", r"^t$"],
    "lat": [r"^lat$", r"^latitude", r"^lat_?deg", r"^y$"],
    "lon": [r"^lon$", r"^long$", r"^longitude", r"^lon_?deg", r"^lng$", r"^x$"],
    "depth": [r"^depth", r"^dep$", r"^z$", r"^pressure$", r"^pres$"],
    "alt": [r"^altitude", r"^alt$", r"^height_above"],
    "heading": [r"^heading", r"^hdg$", r"^yaw$"],
    "temp": [r"^temp", r"^water_?temp", r"^sst$", r"^t_?water", r"^sea_?water_?temperature"],
    "sal": [r"^sal", r"^psal$", r"^practical_?salinity"],
    "cond": [r"^cond", r"^conductivity"],
    "do": [r"^do$", r"^d_?o$", r"^oxygen", r"^o2", r"^dissolved_?oxygen", r"^doxy"],
    "do_sat": [r"^do_?sat", r"^o2_?sat", r"^oxygen_?sat"],
    "chl": [r"^chl", r"^chlorophyll", r"^chla"],
    "turb": [r"^turb", r"^turbidity", r"^ntu$"],
    "ph": [r"^ph$", r"^ph_"],
    "wind_speed": [r"^wind_?speed", r"^wspd$", r"^ws$"],
    "wind_dir": [r"^wind_?dir", r"^wdir$", r"^wd$"],
    "wave_height": [r"^wave_?height", r"^hs$", r"^swh$", r"^hm0$", r"^vhm0$"],
    "air_temp": [r"^air_?temp", r"^atmp$"],
    "pressure_atm": [r"^air_?pres", r"^baro", r"^atm_?pres", r"^slp$"],
    "current_speed": [r"^current_?speed", r"^cur_?spd"],
    "current_dir": [r"^current_?dir", r"^cur_?dir"],
}

UNIT_RE = re.compile(r"[\[\(]([^\]\)]*)[\]\)]")


def _clean_header(name: str) -> tuple[str, str | None]:
    """'Water Temp (°C)' -> ('water_temp', '°C')."""
    s = str(name).strip()
    unit = None
    m = UNIT_RE.search(s)
    if m:
        unit = m.group(1).strip() or None
        s = UNIT_RE.sub("", s)
    s = s.lower().strip()
    s = re.sub(r"[^\w]+", "_", s).strip("_")
    return s, unit


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical names where we recognise them; keep the rest (cleaned)."""
    rename, units, used = {}, {}, set()
    for col in df.columns:
        clean, unit = _clean_header(col)
        target = clean
        for canon, pats in ALIASES.items():
            if canon in used:
                continue
            if any(re.search(p, clean) for p in pats):
                target = canon
                break
        if target in used:  # avoid collisions: keep the cleaned original
            target = clean
        used.add(target)
        rename[col] = target
        if unit:
            units[target] = unit
    out = df.rename(columns=rename)
    out.attrs["original_columns"] = {v: k for k, v in rename.items()}
    out.attrs["units"] = units
    return out


def _combine_date_time(df: pd.DataFrame) -> pd.DataFrame:
    """If there are separate 'date' and 'time'/'hour' columns, merge them into 'time'."""
    cols = {c.lower(): c for c in df.columns}
    if "date" in cols and ("hour" in cols or "time" in cols) and "datetime" not in cols:
        tcol = cols.get("hour") or cols.get("time")
        try:
            df["datetime"] = pd.to_datetime(df[cols["date"]].astype(str) + " " + df[tcol].astype(str))
            df = df.drop(columns=[cols["date"], tcol])
        except (ValueError, TypeError):
            pass
    return df


def parse_time(df: pd.DataFrame, col: str = "time", set_index: bool = True) -> pd.DataFrame:
    """Parse the time column (strings, epoch seconds or ms, Excel serials) and sort."""
    if col not in df.columns:
        return df
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        v = s.dropna()
        if v.between(1e9, 2e10).all():  # epoch seconds
            t = pd.to_datetime(s, unit="s", utc=True)
        elif v.between(1e12, 2e13).all():  # epoch ms
            t = pd.to_datetime(s, unit="ms", utc=True)
        elif v.between(20000, 80000).all():  # Excel serial days
            t = pd.to_datetime(s, unit="D", origin="1899-12-30", utc=True)
        else:
            t = pd.to_datetime(s, errors="coerce", utc=True)
    else:
        t = pd.to_datetime(s, errors="coerce", utc=True, format="mixed", dayfirst=False)
    df = df.assign(**{col: t.dt.tz_convert(None)}).dropna(subset=[col]).sort_values(col)
    if set_index:
        df = df.set_index(col)
    return df


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Turn '12,5' / '  3.1 ' / 'NaN' strings into floats where most of a column is numeric."""
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            conv = pd.to_numeric(df[c].astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")
            if conv.notna().mean() > 0.8:
                df[c] = conv
    return df


def read_raw(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a file into a DataFrame without any normalisation."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in {".csv", ".txt", ".tsv", ".dat"}:
        return pd.read_csv(p, sep=None, engine="python", **kwargs)  # sniff delimiter
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(p, **kwargs)
    if ext == ".parquet":
        return pd.read_parquet(p, **kwargs)
    if ext == ".json":
        return pd.read_json(p, **kwargs)
    if ext in {".nc", ".nc4", ".netcdf", ".cdf"}:
        import xarray as xr

        with xr.open_dataset(p) as ds:
            return ds.to_dataframe().reset_index()
    raise ValueError(f"Unsupported file type: {ext}")


def load_table(path: str | Path, set_index: bool = True, **kwargs) -> pd.DataFrame:
    """One call to get a clean, time-indexed DataFrame from any supported file."""
    df = read_raw(path, **kwargs)
    df = _combine_date_time(df)
    df = normalize_columns(df)
    df = _coerce_numeric(df)
    attrs = dict(df.attrs)
    df = parse_time(df, "time", set_index=set_index)
    df.attrs.update(attrs)
    return df


def describe(df: pd.DataFrame) -> pd.DataFrame:
    """Quick per-column overview: dtype, coverage, range. Good first look at a new dataset."""
    rows = []
    for c in df.columns:
        s = df[c]
        num = pd.api.types.is_numeric_dtype(s)
        rows.append(
            {
                "column": c,
                "original": df.attrs.get("original_columns", {}).get(c, c),
                "unit": df.attrs.get("units", {}).get(c, ""),
                "dtype": str(s.dtype),
                "non_null_%": round(100 * s.notna().mean(), 1),
                "min": s.min() if num else None,
                "median": s.median() if num else None,
                "max": s.max() if num else None,
            }
        )
    out = pd.DataFrame(rows)
    if isinstance(df.index, pd.DatetimeIndex) and len(df):
        out.attrs["time_range"] = (df.index.min(), df.index.max())
        out.attrs["median_step"] = df.index.to_series().diff().median()
    return out
