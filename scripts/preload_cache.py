"""Warm the disk cache so the viewer and the health cards work offline.

    .venv/bin/python scripts/preload_cache.py                 # 7 stations + zone centroids, today
    .venv/bin/python scripts/preload_cache.py --no-zones      # stations only
    .venv/bin/python scripts/preload_cache.py --dates 2024-07-20 --workers 2
    MARINEKIT_OFFLINE=1 .venv/bin/python scripts/preload_cache.py   # check: everything must come from the cache

For each point it computes every health card at each date (this fetches the card window: the last 366 days up to
today + 10 days of forecast, or the calendar year for older dates), the day-of-year climatologies, the series of the
last 60 days for the main variables (datahub.recent_window(60), the window the viewer should use for its charts) and,
for the 7 stations, compare_sources() over the same 60 days. Everything goes through the source modules' disk caches
(data/cache/...), so re-running is safe and fast; failures are printed and do not stop the run.
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

from marinekit import datahub as dh  # noqa: E402
from marinekit import indicators as ind  # noqa: E402
from marinekit.sources import STATIONS  # noqa: E402

SERIES_VARS = ["sst", "chl", "kd490", "o2", "o2_bottom", "o2_sat", "sal", "bottom_temp", "mld", "ph",
               "wave_height", "discharge"]
CLIM_VARS = ["sst", "chl", "kd490", "o2", "o2_bottom", "sal", "bottom_temp", "mld", "ph", "discharge"]
COMPARE_VARS = ["sst", "chl", "o2", "sal"]


def zone_points() -> dict[str, tuple[float, float]]:
    """One sample point per pressure-zone feature (centroid, or an interior point), de-duplicated to ~2 km."""
    import json
    from shapely.geometry import shape
    p = ROOT / "data" / "zones" / "sector_zones.geojson"
    if not p.exists():
        return {}
    out: dict[str, tuple[float, float]] = {}
    for f in json.loads(p.read_text()).get("features", []):
        try:
            g = shape(f["geometry"])
        except Exception:  # noqa: BLE001
            continue
        la, lo, how = ind.zone_sample_points(g, 1)[0]
        pr = f.get("properties") or {}
        name = f"zone {pr.get('sector')}/{pr.get('activity') or pr.get('ring') or ''}".rstrip("/")
        if any(abs(la - a) < 0.02 and abs(lo - b) < 0.02 for a, b in out.values()):
            continue
        out[name] = (la, lo)
    return out


def warm_point(name: str, lat: float, lon: float, dates: list[str], compare: bool) -> dict:
    t0 = time.time()
    fails, nodata, n = [], [], 0
    for d in dates:
        for cid in ind.CARDS:
            c = ind.card(cid, lat, lon, d)
            n += 1
            if c.get("error"):
                fails.append(f"card {cid} {d}: {c['why'][:160]}")
            elif c["status"] == "no_data":
                nodata.append(f"{cid} {d}: {c['why'][:140]}")
    for v in CLIM_VARS:
        try:
            dh.get_climatology(v, lat, lon)
        except Exception as e:  # noqa: BLE001
            fails.append(f"clim {v}: {type(e).__name__}: {str(e)[:160]}")
    s, e = dh.recent_window(60)
    for v in SERIES_VARS:
        try:
            dh.get_series(v, lat, lon, s, e)
        except Exception as ex:  # noqa: BLE001
            fails.append(f"series {v}: {type(ex).__name__}: {str(ex)[:160]}")
    if compare:
        for v in COMPARE_VARS:
            try:
                df = dh.compare_sources(v, lat, lon, s, e)
                for sid, why in df.attrs.get("failed", {}).items():
                    # untrusted platforms often carry no water sensors (EUXRoCB03): a note, not a failure
                    (nodata if sid in ("coastal buoy", "station 15480") else fails).append(
                        f"compare {v}/{sid}: {why[:120]}")
            except Exception as ex:  # noqa: BLE001
                fails.append(f"compare {v}: {type(ex).__name__}: {str(ex)[:160]}")
        for v in ("o2", "sal", "sst"):
            try:
                dh.obs_vs_model(v, lat, lon, s, e)
            except Exception as ex:  # noqa: BLE001
                fails.append(f"obs_vs_model {v}: {type(ex).__name__}: {str(ex)[:160]}")
    return {"name": name, "lat": lat, "lon": lon, "seconds": round(time.time() - t0, 1), "cards": n, "fails": fails,
            "nodata": nodata}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dates", nargs="*", default=None, help="card dates (default: today)")
    ap.add_argument("--no-zones", action="store_true", help="skip the pressure-zone sample points")
    ap.add_argument("--no-compare", action="store_true", help="skip compare_sources (in-situ platforms are slow)")
    ap.add_argument("--workers", type=int, default=3, help="points warmed in parallel (network bound)")
    a = ap.parse_args()
    dates = a.dates or [str(dh.today().date())]
    pts = [(n, la, lo, True) for n, (la, lo) in STATIONS.items()]
    if not a.no_zones:
        pts += [(n, la, lo, False) for n, (la, lo) in zone_points().items()]
    print(f"Preloading {len(pts)} points x {len(ind.CARDS)} cards x {len(dates)} date(s): {', '.join(dates)}; "
          f"offline={dh.OFFLINE}; workers={a.workers}", flush=True)
    t0 = time.time()
    res = []
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = {ex.submit(warm_point, n, la, lo, dates, cmp and not a.no_compare): n for n, la, lo, cmp in pts}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                r = {"name": futs[f], "seconds": None, "cards": 0, "fails": [f"crashed: {type(e).__name__}: {e}"],
                     "lat": None, "lon": None, "nodata": []}
            res.append(r)
            print(f"  {r['name']:32s} {str(r['seconds']):>7s} s  {r['cards']:3d} cards  {len(r['fails'])} failures"
                  f"  {len(r['nodata'])} no_data", flush=True)
            for x in r["fails"]:
                print(f"      - FAIL {x}", flush=True)
            for x in r["nodata"]:
                print(f"      - no_data {x}", flush=True)
    nf = sum(len(r["fails"]) for r in res)
    print(f"Done in {time.time() - t0:.0f} s; {nf} failures over {len(res)} points.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
