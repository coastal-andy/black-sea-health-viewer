"""Soft-edged pressure map: the same plain count of overlapping sectors (0-5), drawn with soft zone edges.

Zone limits are approximate (buffers around ports, beaches, farms; some locations assumed), so a hard 500 m cell
edge looks more precise than the data is. Here each sector's zones are rasterised on a fine grid over the Romanian
shelf (about 160 m). Inside a zone the sector counts 1; outside, it fades with a Gaussian of the distance to the
zone, exp(-d^2 / 2 sigma^2), with sigma 0.75 km for official and mapped zones and 1.5 km for assumed ones (it
drops to 10% at about 1.6 km and 3.2 km). The fade stands for edge uncertainty, never for importance. The five
sector layers are summed into a 0-5 surface.

- Inside k overlapping zones the surface is exactly k, so the colour is still the count. No weights, no index.
- Why not a plain Gaussian blur of each layer: most zones are coastal buffers 1-2 km wide, and a blur with
  sigma 1 km lowers them to well under 1 (checked on the zone files: the median of single-sector cells fell to
  0.76 and 4-sector cells to about 1.2), so the colour would no longer be the number of sectors.
- Tourism zones count only in summer (1 June - 15 September), as in the sharp map.
- Some zones are made of grid cells in the source data (shipping lanes, fishing grounds, 2-3 km cells with gaps).
  The faded layer is smoothed once more with the same sigma, which rounds the corners and fills narrow gaps, and
  the zone itself is then set back to 1, so the count inside every zone is never lowered.
- Contour lines at 1, 2 and 3 are drawn on a lightly smoothed copy (sigma 0.5 km) at 0.5, 1.5 and 2.5, so they
  are rounded and sit close to the edges where the count reaches 1, 2 and 3.
- The exact count from the original 500 m grid stays available on hover (transparent polygons in maps.py).

Everything is computed from data/zones/ at render time and cached on disk (st.cache_data persist), keyed by the
zone files' modification times (adapters._zones_stamp)."""

from __future__ import annotations

import base64
import io
import json

import numpy as np
import streamlit as st

from viewer import adapters as A
from viewer.style import SECTOR, overlap_levels

# grid over the shelf zones plus a margin for the blur (zones span 28.54-30.60 E, 43.67-45.19 N)
LON0, LON1, LAT0, LAT1 = 28.40, 30.75, 43.55, 45.30
DLON, DLAT = 0.002, 0.0015  # about 160 m x 167 m at 44.4 N
SIGMA_KM = {"official": 0.75, "mapped": 0.75, "assumed": 1.5}  # edge uncertainty, not importance
CONTOUR_LEVELS = (1, 2, 3)  # lines where the count reaches 1, 2, 3 (see the module note)
SHOW_STEP = 2  # the drawn image keeps every 2nd pixel (about 330 m); the browser smooths it when scaling
ZONE_ALPHA = 0.30  # peak opacity of a soft sector zone
NOTE = "Soft edges show that zone limits are approximate; the colour is still the number of overlapping sectors."


def _grid():
    lons = np.arange(LON0 + DLON / 2, LON1, DLON)
    lats = np.arange(LAT1 - DLAT / 2, LAT0, -DLAT)  # north to south: row 0 is the top of the image
    return lons, lats


def _km_per_px():
    lat = (LAT0 + LAT1) / 2
    return DLAT * 111.32, DLON * 111.32 * np.cos(np.radians(lat))


def _rasterise(geom, lons, lats) -> np.ndarray:
    """1 inside the (multi)polygon, 0 outside, on the grid. PIL draws polygons fast; the union is drawn polygon by
    polygon with its holes cut out, so overlapping input features never cancel each other."""
    from PIL import Image, ImageDraw
    w, h = len(lons), len(lats)
    img = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(img)

    def px(coords):
        c = np.asarray(coords)[:, :2]
        return list(zip(((c[:, 0] - LON0) / DLON).tolist(), ((LAT1 - c[:, 1]) / DLAT).tolist()))

    polys = list(getattr(geom, "geoms", [geom]))
    for p in polys:
        if p.is_empty or p.geom_type != "Polygon":
            continue
        dr.polygon(px(p.exterior.coords), fill=1)
        for ring in p.interiors:
            dr.polygon(px(ring.coords), fill=0)
    return np.asarray(img, dtype=np.float32)


@st.cache_data(show_spinner="Preparing the soft-edged pressure map...", persist="disk")
def sector_surfaces(season: str, stamp: tuple) -> dict:
    """{sector: soft 0-1 layer} on the fine grid, plus 'total' (their sum, 0-5). float32 arrays."""
    import geopandas as gpd
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    from shapely.ops import unary_union
    lons, lats = _grid()
    kmy, kmx = _km_per_px()
    g = gpd.read_file(A.ZONES / "sector_zones.geojson")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.buffer(0)
    if "season" not in g.columns:
        g["season"] = np.where(g["sector"] == "tourism", "summer", "all")
    if season == "winter":
        g = g[g["season"].astype(str) != "summer"]
    conf = g["confidence"].astype(str) if "confidence" in g.columns else "mapped"
    g["unc"] = np.where(conf == "assumed", "assumed", "certain")
    out = {}
    for sector in SECTOR:
        layer = np.zeros((len(lats), len(lons)), np.float32)
        for unc, sub in g[g["sector"] == sector].groupby("unc"):
            mask = _rasterise(unary_union(list(sub.geometry)), lons, lats)
            if not mask.any():
                continue
            s_km = SIGMA_KM["assumed" if unc == "assumed" else "official"]
            d_km = distance_transform_edt(mask < 0.5, sampling=(kmy, kmx))  # 0 inside the zone
            soft = np.exp(-0.5 * (d_km / s_km) ** 2)
            soft[d_km > 3.5 * s_km] = 0
            # round off corners and fill the gaps between grid-cell zones (shipping lanes, fishing grounds), then put
            # the full count back inside the zone itself
            soft = np.maximum(mask, gaussian_filter(soft, sigma=(s_km / kmy, s_km / kmx), mode="constant", truncate=3.0))
            layer = np.maximum(layer, soft)  # a sector counts once, however many of its zones overlap here
        out[sector] = np.clip(layer, 0, 1).astype(np.float32)
    out["total"] = np.sum([out[s] for s in SECTOR], axis=0).astype(np.float32)
    return out


def _bounds():
    return [[LAT0, LON0], [LAT1, LON1]]


def _png_url(rgba: np.ndarray) -> str:
    """RGBA float (0-1) image on the lat/lon grid -> Web Mercator rows -> PNG data URL."""
    from folium.utilities import mercator_transform
    from PIL import Image
    img = rgba[::SHOW_STEP, ::SHOW_STEP]
    img = mercator_transform(img, (LAT0, LAT1), origin="upper")
    buf = io.BytesIO()
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGBA").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _hex(c: str) -> np.ndarray:
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def overlap_ramp() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stops of the continuous ramp: counts 0..5, colours and opacities from overlap_style.json. Below 1 the
    colour of level 1 fades to transparent at 0."""
    lv = overlap_levels()
    xs = np.arange(0, 6, dtype=np.float32)
    cols = [lv[1][0]] + [lv[k][0] for k in range(1, 6)]
    alps = [0.0] + [lv[k][1] for k in range(1, 6)]
    return xs, np.array([_hex(c) for c in cols]), np.array(alps, np.float32)


@st.cache_data(show_spinner=False, persist="disk")
def overlap_image(season: str, stamp: tuple) -> dict:
    """The summed surface coloured with the overlap ramp, as a PNG data URL with its bounds."""
    total = sector_surfaces(season, stamp)["total"]
    xs, cols, alps = overlap_ramp()
    v = np.clip(total, 0, 5)
    rgba = np.zeros(v.shape + (4,), np.float32)
    for i in range(3):
        rgba[..., i] = np.interp(v, xs, cols[:, i])
    rgba[..., 3] = np.interp(v, xs, alps)
    rgba[v < 0.03, 3] = 0
    return dict(url=_png_url(rgba), bounds=_bounds())


@st.cache_data(show_spinner=False, persist="disk")
def zone_image(sector: str, season: str, stamp: tuple) -> dict | None:
    """One sector's blurred zones in its Okabe-Ito colour, opacity falling off towards the uncertain edge."""
    layer = sector_surfaces(season, stamp).get(sector)
    if layer is None or float(layer.max()) < 0.03:
        return None
    rgba = np.zeros(layer.shape + (4,), np.float32)
    rgba[..., :3] = _hex(SECTOR[sector][1])
    rgba[..., 3] = ZONE_ALPHA * layer
    rgba[layer < 0.03, 3] = 0
    return dict(url=_png_url(rgba), bounds=_bounds())


@st.cache_data(show_spinner=False, persist="disk")
def contours(season: str, stamp: tuple) -> dict:
    """GeoJSON lines of the summed surface at CONTOUR_LEVELS (lon/lat), lightly simplified: the edges of the
    areas where at least 1, 2 or 3 sectors overlap."""
    import contourpy
    from scipy.ndimage import gaussian_filter
    from shapely.geometry import LineString, mapping
    kmy, kmx = _km_per_px()
    total = gaussian_filter(sector_surfaces(season, stamp)["total"], sigma=(0.5 / kmy, 0.5 / kmx), mode="constant")
    lons, lats = _grid()
    gen = contourpy.contour_generator(lons, lats, total, line_type="Separate")
    feats = []
    for lev in CONTOUR_LEVELS:
        for seg in gen.lines(lev - 0.5):
            if len(seg) < 4:
                continue
            ls = LineString(seg).simplify(0.0006)
            if ls.length < 0.01:  # drop specks shorter than about 1 km
                continue
            k = int(lev)
            feats.append(dict(type="Feature", geometry=mapping(ls),
                              properties=dict(level=float(lev), k=k,
                                              label=f"Edge of {k}+ sector{'s' if k > 1 else ''} overlapping")))
    return json.loads(json.dumps(dict(type="FeatureCollection", features=feats)))
