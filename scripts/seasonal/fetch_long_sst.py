"""Long satellite SST record (CMEMS L4 REP from 1982, then NRT minus its offset) at the 4 offshore buoy points.

    .venv\\Scripts\\python.exe scripts/seasonal/fetch_long_sst.py          # online: downloads into data/cache/ (minutes)
    MARINEKIT_OFFLINE=1 .venv\\Scripts\\python.exe scripts/seasonal/fetch_long_sst.py   # recompute from the cache only

Everything goes through marinekit.datahub.get_series(source="satellite"), so the files land in the normal cache.
Output: docs/indicators/seasonal/trends_long.csv (same columns as trends.csv plus trust and record), read by
marinekit.seasonal.long_term_trend for SST when present. Stations whose fetch fails are logged and skipped.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from marinekit import datahub as dh  # noqa: E402
from marinekit.seasonal import PRECOMPUTED, STATIONS, linear_trend  # noqa: E402

START = "1982-01-01"
OUT = PRECOMPUTED / "trends_long.csv"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main() -> None:
    end = f"{pd.Timestamp.today().year - 1}-12-31"
    rows = []
    for st, (lat, lon) in STATIONS.items():
        t = time.time()
        try:
            df = dh.get_series("sst", lat, lon, START, end, source="satellite")
        except Exception as ex:  # noqa: BLE001
            log(f"{st}: failed ({type(ex).__name__}: {str(ex)[:200]})")
            continue
        s = df["sst"].dropna()
        tr = linear_trend(s)
        rows.append(dict(station=st, variable="sst", source="satellite", n_years=tr["n_years"],
                         years="" if not tr["years"] else f"{tr['years'][0]}-{tr['years'][1]}",
                         meaningful=tr["meaningful"], slope_per_decade=tr["slope_per_decade"], ci_lo=tr["ci"][0],
                         ci_hi=tr["ci"][1], p_value=tr["p_value"], r2=tr["r2"], note=tr.get("note", ""),
                         trust=df.attrs.get("trust"), record=f"{s.index.min():%Y-%m-%d} to {s.index.max():%Y-%m-%d}",
                         label=df.attrs.get("label")))
        log(f"{st}: {len(s)} days, {tr['n_years']} complete years, slope {tr['slope_per_decade']:+.3f} C/decade "
            f"({time.time() - t:.0f} s)")
    if rows:
        pd.DataFrame(rows).to_csv(OUT, index=False, float_format="%.4g")
        log(f"wrote {OUT} ({len(rows)} stations)")
    else:
        log("nothing written")


if __name__ == "__main__":
    main()
