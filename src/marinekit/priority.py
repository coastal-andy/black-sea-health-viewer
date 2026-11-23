"""Sensitive-area scoring and MPA candidate areas from habitat labels and threat detections.

    cells = priority.score_cells(habitat_pts, threat_pts, cell_m=50)   # one row per grid cell
    stab  = priority.stability(cells)                                  # does the class survive ±20 % weight changes?
    areas = priority.candidate_areas(cells)                            # connected sensitive cells -> candidate MPAs
    priority.cells_geojson(cells), priority.areas_geojson(cells, areas)

How the score works (a transparent weighted overlay, MCDA style):
  factors (each 0-1, higher = more sensitive)
    value      mean ecological value of the habitats seen in the cell (HABITAT_TABLE, editable)
    protected  share of observations that are a protected/priority habitat
    diversity  Shannon diversity of habitat labels, divided by ln(K), K = habitat classes in the survey
  sensitivity = w_value*value + w_protected*protected + w_diversity*diversity   (weights sum to 1)
  constraint  cells with fewer than `min_obs` labelled images get no score ("insufficient data").
              It is applied last and never blended into the weights.
Threat is kept SEPARATE from sensitivity, so a heavily littered cell can't look "less valuable".
The two together give the action class (2×2): Protect & restore now / Protect / Clean up / Monitor.

All values, weights and thresholds are placeholders until NIMRD gives us theirs.
"""

from __future__ import annotations

import json
from collections import deque

import numpy as np
import pandas as pd

M_PER_DEG_LAT = 111_320.0

# label -> (ecological value 0-1, protected/priority habitat?, note). Labels match vision.HABITAT_CLASSES.
# Values are a first guess for the Romanian coast. Ask NIMRD and replace them.
HABITAT_TABLE: dict[str, tuple[float, bool, str]] = {
    "seagrass": (1.00, True, "Zostera meadows: nursery, O₂, N removal; Habitats Dir. 1110/1160, Black Sea Red List"),
    "phyllophora": (0.90, True, "Phyllophora red-algae field"),
    "brown_algae": (0.90, True, "Cystoseira / Gongolaria belts, indicator of good status"),
    "mussel_bed": (0.70, True, "Mytilus biogenic reef (1170)"),
    "rock": (0.60, True, "Rocky reef (1170)"),
    "algae": (0.40, False, "Opportunistic green algae (often eutrophication)"),
    "shell_debris": (0.35, False, "Shell hash"),
    "sand": (0.30, False, "Sand (1110 only if a sandbank)"),
    "mud": (0.20, False, "Soft mud"),
    "litter": (0.00, False, "Litter-dominated seabed"),
}
IGNORE_LABELS = {"water_column"}  # seabed not visible: not evidence of any habitat

# Threat item weights (per detection). Anything not listed counts 1.
THREAT_WEIGHTS = {
    "fishing net": 3.0, "ghost net": 3.0, "trawl mark": 3.0, "fishing line": 2.0, "tire": 2.0,
    "rapana": 2.0, "Rapana venosa": 2.0, "rope": 1.5,
}

DEFAULT_WEIGHTS = {"value": 0.5, "protected": 0.3, "diversity": 0.2}
SENS_BREAKS = (0.4, 0.6)   # low < 0.4 <= medium < 0.6 <= high  (fixed absolute breaks, not quantiles)
THREAT_HIGH = 0.5

ACTIONS = {  # (sensitive?, threatened?) -> action
    (True, True): "Protect & restore now",
    (True, False): "Protect",
    (False, True): "Clean up / mitigate",
    (False, False): "Monitor",
}
ACTION_COLORS = {"Protect & restore now": "#D55E00", "Protect": "#009E73", "Clean up / mitigate": "#E69F00",
                 "Monitor": "#56B4E9", "Insufficient data": "#999999"}


# ----------------------------------------------------------------- grid ---

def _grid(df: pd.DataFrame, cell_m: float, lat0: float) -> pd.DataFrame:
    d = df.dropna(subset=["lat", "lon"]).copy()
    m_lon = M_PER_DEG_LAT * np.cos(np.radians(lat0))
    d["gx"] = np.floor(d.lon * m_lon / cell_m).astype(int)
    d["gy"] = np.floor(d.lat * M_PER_DEG_LAT / cell_m).astype(int)
    return d


def _cell_center(gx, gy, cell_m: float, lat0: float):
    m_lon = M_PER_DEG_LAT * np.cos(np.radians(lat0))
    return (np.asarray(gy) + 0.5) * cell_m / M_PER_DEG_LAT, (np.asarray(gx) + 0.5) * cell_m / m_lon


def _cell_square(gx: int, gy: int, cell_m: float, lat0: float) -> list[list[float]]:
    m_lon = M_PER_DEG_LAT * np.cos(np.radians(lat0))
    x0, x1 = gx * cell_m / m_lon, (gx + 1) * cell_m / m_lon
    y0, y1 = gy * cell_m / M_PER_DEG_LAT, (gy + 1) * cell_m / M_PER_DEG_LAT
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


# --------------------------------------------------------------- scoring ---

def _norm_weights(w: dict | None) -> dict:
    w = {**DEFAULT_WEIGHTS, **(w or {})}
    s = sum(max(0.0, v) for v in w.values()) or 1.0
    return {k: max(0.0, v) / s for k, v in w.items()}


def _sens(cells: pd.DataFrame, w: dict) -> pd.Series:
    w = _norm_weights(w)
    s = sum(w[k] * cells[k] for k in DEFAULT_WEIGHTS)
    return s.where(cells["valid"])


def _sens_class(s: pd.Series) -> pd.Series:
    lo, hi = SENS_BREAKS
    out = pd.Series("insufficient data", index=s.index, dtype=object)
    out[s < lo] = "low"
    out[(s >= lo) & (s < hi)] = "medium"
    out[s >= hi] = "high"
    return out


def score_cells(habitat: pd.DataFrame, threats: pd.DataFrame | None = None, cell_m: float = 50.0,
                weights: dict | None = None, habitat_table: dict | None = None, min_obs: int = 3,
                label_col: str = "pred", threat_label_col: str = "label", threat_saturation: float | None = None) -> pd.DataFrame:
    """Score every grid cell that has habitat observations.

    habitat: points with lat, lon and a habitat label column (e.g. vision zero-shot output geotagged).
    threats: points with lat, lon and a label (litter / ghost-net / Rapana detections). Optional.
    threat_saturation: weighted items per 100 m² that counts as maximum threat (1.0). Default: 95th
        percentile of non-zero cells (relative to this survey; say so in the pitch).
    """
    table = habitat_table or HABITAT_TABLE
    h = habitat[~habitat[label_col].isin(IGNORE_LABELS)].dropna(subset=["lat", "lon", label_col])
    h = h[h[label_col].isin(table)]
    if h.empty:
        raise ValueError(f"no habitat labels matching the table; got {sorted(habitat[label_col].dropna().unique())}")
    lat0 = float(h.lat.mean())
    g = _grid(h, cell_m, lat0)
    g["value"] = g[label_col].map(lambda k: table[k][0])
    g["protected"] = g[label_col].map(lambda k: float(table[k][1]))

    counts = g.groupby(["gx", "gy", label_col]).size().unstack(fill_value=0)
    k = max(2, (counts.sum() > 0).sum())
    p = counts.div(counts.sum(1), axis=0)
    shannon = -(p * np.log(p.where(p > 0))).sum(1).fillna(0)

    cells = g.groupby(["gx", "gy"]).agg(n_obs=("lat", "size"), value=("value", "mean"), protected=("protected", "mean"))
    cells["diversity"] = (shannon / np.log(k)).clip(0, 1) + 0.0
    cells["dominant"] = counts.idxmax(1)
    cells["habitats"] = p.apply(lambda r: ", ".join(f"{c} {v:.0%}" for c, v in r[r > 0].sort_values(ascending=False).items()), axis=1)
    cells = cells.reset_index()
    cells["valid"] = cells.n_obs >= min_obs

    # threats on the same grid
    cells["threat_items"] = 0.0
    if threats is not None and len(threats):
        t = _grid(threats, cell_m, lat0)
        lab = t[threat_label_col] if threat_label_col in t else pd.Series("item", index=t.index)
        t["w"] = lab.map(lambda x: THREAT_WEIGHTS.get(str(x), 1.0))
        tw = t.groupby(["gx", "gy"]).w.sum()
        cells = cells.merge(tw.rename("tw").reset_index(), on=["gx", "gy"], how="left")
        cells["threat_items"] = cells.pop("tw").fillna(0.0)
    cells["threat_per_100m2"] = cells.threat_items / (cell_m * cell_m) * 100
    nz = cells.threat_per_100m2[cells.threat_per_100m2 > 0]
    sat = threat_saturation or (float(np.percentile(nz, 95)) if len(nz) else 1.0)
    cells["threat"] = (cells.threat_per_100m2 / sat).clip(0, 1)

    cells["sensitivity"] = _sens(cells, weights)
    cells["sens_class"] = _sens_class(cells.sensitivity)
    sensitive = cells.sens_class == "high"
    threatened = cells.threat >= THREAT_HIGH
    cells["action"] = [ACTIONS[(s, t)] for s, t in zip(sensitive, threatened)]
    cells.loc[~cells.valid, "action"] = "Insufficient data"
    cells["lat"], cells["lon"] = _cell_center(cells.gx, cells.gy, cell_m, lat0)
    cells.attrs.update(cell_m=cell_m, lat0=lat0, weights=_norm_weights(weights), threat_saturation=sat, min_obs=min_obs)
    return cells


def stability(cells: pd.DataFrame, delta: float = 0.2) -> pd.DataFrame:
    """One-at-a-time weight perturbation (each weight ×(1±delta), renormalised).

    Adds `stability` (share of perturbed runs where the sensitivity class matches the baseline) and
    returns the cells. cells.attrs['changed_share'] = mean share of cells that change class per run.
    """
    base_w = cells.attrs.get("weights", DEFAULT_WEIGHTS)
    base = _sens_class(_sens(cells, base_w))
    same, changed = [], []
    for k in DEFAULT_WEIGHTS:
        for f in (1 - delta, 1 + delta):
            w = {**base_w, k: base_w[k] * f}
            c = _sens_class(_sens(cells, w))
            eq = (c == base)
            same.append(eq)
            changed.append(float((~eq[cells.valid]).mean()) if cells.valid.any() else 0.0)
    out = cells.copy()
    out["stability"] = pd.concat(same, axis=1).mean(1).round(2)
    out.attrs.update(cells.attrs, changed_share=float(np.mean(changed)), delta=delta)
    return out


# ------------------------------------------------------- candidate areas ---

def candidate_areas(cells: pd.DataFrame, min_sensitivity: float | None = None, min_cells: int = 2) -> pd.DataFrame:
    """Merge touching (8-neighbour) sensitive cells into candidate protected areas."""
    thr = SENS_BREAKS[1] if min_sensitivity is None else min_sensitivity
    sel = cells[cells.valid & (cells.sensitivity >= thr)]
    idx = {(r.gx, r.gy): i for i, r in sel.iterrows()}
    seen, groups = set(), []
    for key in idx:
        if key in seen:
            continue
        q, comp = deque([key]), []
        seen.add(key)
        while q:
            x, y = q.popleft()
            comp.append(idx[(x, y)])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (x + dx, y + dy)
                    if nb in idx and nb not in seen:
                        seen.add(nb)
                        q.append(nb)
        if len(comp) >= min_cells:
            groups.append(comp)

    cell_m = cells.attrs.get("cell_m", 50.0)
    rows = []
    for gid, comp in enumerate(sorted(groups, key=lambda c: -cells.loc[c, "sensitivity"].sum()), start=1):
        c = cells.loc[comp]
        hab = c.dominant.value_counts(normalize=True)
        threatened = (c.threat >= THREAT_HIGH).mean()
        rows.append(dict(
            area_id=gid, n_cells=len(c), area_ha=round(len(c) * cell_m * cell_m / 10_000, 2),
            mean_sensitivity=round(c.sensitivity.mean(), 3), protected_share=round(c.protected.mean(), 2),
            main_habitats=", ".join(f"{k} {v:.0%}" for k, v in hab.head(3).items()),
            threat_items=round(c.threat_items.sum(), 1), threatened_cells=f"{threatened:.0%}",
            stability=round(c.stability.mean(), 2) if "stability" in c else None,
            action="Protect & restore now" if threatened >= 0.25 else "Protect",
            lat=round(c.lat.mean(), 6), lon=round(c.lon.mean(), 6), cells=[(int(a), int(b)) for a, b in zip(c.gx, c.gy)],
        ))
    return pd.DataFrame(rows, columns=["area_id", "n_cells", "area_ha", "mean_sensitivity", "protected_share", "main_habitats",
                                       "threat_items", "threatened_cells", "stability", "action", "lat", "lon", "cells"])


# ---------------------------------------------------------------- export ---

def cells_geojson(cells: pd.DataFrame) -> str:
    cm, lat0 = cells.attrs["cell_m"], cells.attrs["lat0"]
    keep = ["n_obs", "dominant", "habitats", "value", "protected", "diversity", "sensitivity", "sens_class",
            "threat_items", "threat", "action", "stability"]
    feats = []
    for _, r in cells.iterrows():
        props = {k: (None if pd.isna(r[k]) else (round(float(r[k]), 4) if isinstance(r[k], (float, np.floating)) else
                                                (int(r[k]) if isinstance(r[k], (np.integer,)) else r[k])))
                 for k in keep if k in r}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Polygon", "coordinates": [_cell_square(r.gx, r.gy, cm, lat0)]}})
    return json.dumps({"type": "FeatureCollection", "features": feats})


def areas_geojson(cells: pd.DataFrame, areas: pd.DataFrame) -> str:
    cm, lat0 = cells.attrs["cell_m"], cells.attrs["lat0"]
    feats = []
    for _, a in areas.iterrows():
        props = {k: (a[k].item() if hasattr(a[k], "item") else a[k]) for k in areas.columns if k not in ("cells",)}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "MultiPolygon", "coordinates": [[_cell_square(x, y, cm, lat0)] for x, y in a.cells]}})
    return json.dumps({"type": "FeatureCollection", "features": feats})


# -------------------------------------------------- area-wide pressures ---

def buoy_pressures(events: pd.DataFrame) -> pd.DataFrame:
    """Summarise buoy events as area-wide pressures on the seabed (one row per pressure)."""
    if events is None or events.empty:
        return pd.DataFrame(columns=["pressure", "episodes", "hours", "worst", "msfd"])
    names = {"hypoxia": "Low oxygen / hypoxia", "bloom": "Algal bloom (eutrophication)", "heatwave": "Warm-water episode",
             "turbidity": "High turbidity (sediment, smothering)", "low_ph": "Low pH"}
    ev = events[events.kind.isin(names)]
    out = ev.groupby("kind").agg(episodes=("kind", "size"), hours=("duration_h", "sum"),
                                 worst=("severity", lambda s: "high" if (s == "high").any() else "medium"),
                                 msfd=("msfd", "first")).reset_index()
    out.insert(0, "pressure", out.pop("kind").map(names))
    return out.sort_values("hours", ascending=False).reset_index(drop=True)
