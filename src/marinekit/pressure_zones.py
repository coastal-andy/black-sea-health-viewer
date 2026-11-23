"""Pressure zones v2 for the Romanian Black Sea coast: confirmed features, one buffer per activity, overlap count.

Interface Z -> U (docs/plan/WORKFLOW.md); all files in data/zones/, EPSG:4326:
  sector_features.geojson   feature_id, sector, activity, name, source, source_url, confidence, season, note
  sector_zones.geojson      one buffer polygon per sector x activity x confidence: sector, activity, buffer_m,
                            buffer_basis (law|literature|rule), basis_ref, season, confidence
  overlap_grid.geojson      250 m cells: cell_id, n_summer, n_winter (0-5), sectors_summer, sectors_winter, lon, lat
  overlap_summer.geojson    dissolved cells per overlap count 1-5 (bathing season, tourism on)
  overlap_winter.geojson    the same outside the bathing season (tourism off)
  buffers.yaml              the buffer table (the single editable config)
  *.qml                     QGIS styles (count 1-5 as a light-to-dark warm ramp; assumed features hatched or dashed)

The pressure map is a plain count of how many of the 5 sectors are present in a cell (no weights). A sector is
present when any of its zones touches the cell. Tourism zones are on only in the bathing season
(1 June - 15 September); all other sectors are year-round.

confidence of a feature:
  official  port authority, ANPA, EMODnet, EEA, a legal text or permit
  mapped    OpenStreetMap / visible on satellite imagery
  assumed   located from a place name, approximate or secondary source: drawn hatched/dashed, to confirm with NIMRD

Raw downloads are cached in data/cache/pressure_zones/, so a rebuild works offline:
    cd src && ../.venv/bin/python -m marinekit.pressure_zones [--cell 250] [--no-map]

Public API
    season_for_date(date) -> "summer" | "winter"
    load_features(sector=None) -> GeoDataFrame
    load_buffers(path=None) -> dict
    build_zones(buffers=None) -> GeoDataFrame
    overlap_grid(zones=None, cell_m=250) -> GeoDataFrame
    overlap_polygons(grid, season) -> GeoDataFrame
    top_overlap_areas(grid, season, min_count=3) -> GeoDataFrame
    overlap_at(lat, lon, date=None) -> {season, n, sectors, cell_id}   (reads overlap_grid.geojson)
    export_all(cell_m=250, render=True) -> dict[str, Path]
    sea_polygon(), ro_sea(), coastline() -> shapely geometries in EPSG:32635
The earlier weighted version (rings, AHP weights, hotspot index) is archived in data/zones/archive_v1/.
"""

from __future__ import annotations

import copy
import io
import json
import re
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely
from PIL import Image
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box, shape
from shapely.ops import linemerge, polygonize, substring, unary_union

from .sources import BBOX_RO, CACHE, ROOT

SOURCE = "pressure_zones"
CACHE_DIR = CACHE / SOURCE
OUT_DIR = ROOT / "data" / "zones"
CRS_M = "EPSG:32635"  # UTM 35N, metres
CRS_LL = "EPSG:4326"
UA = {"User-Agent": "marinekit-hackathon/0.1 (python-requests)"}
TIMEOUT = (15, 150)

SECTORS = ("ports", "shipyards", "tourism", "fishing", "aquaculture")
SECTOR_LABELS = {
    "ports": "Ports and maritime logistics",
    "shipyards": "Shipyards and marine engineering",
    "tourism": "Coastal and marine tourism",
    "fishing": "Fishing",
    "aquaculture": "Aquaculture",
}
# Okabe-Ito, one colour per sector (same in the map and the dashboard)
SECTOR_COLORS = {
    "ports": "#0072B2",
    "shipyards": "#D55E00",
    "tourism": "#E69F00",
    "fishing": "#009E73",
    "aquaculture": "#CC79A7",
}

OSM = "OpenStreetMap contributors"
ODBL = "ODbL 1.0"
EMOD_HA = "EMODnet Human Activities"
EMOD_LIC = "CC BY 4.0 (EMODnet data policy)"
RO_LAW = "Romanian official act (not under copyright, Law 8/1996 art. 9)"


CONFIDENCE = ("official", "mapped", "assumed")

# Bathing season: tourism zones are on from 1 June to 15 September (inclusive)
BATHING_SEASON = {"start": (6, 1), "end": (9, 15),
                  "basis_ref": "Ministry of Health / INSP bathing-water monitoring season 1 June - 15 September "
                               "(practice under HG 546/2008; no statutory article fixing the dates was found)"}

# Optional fishing closure toggle: documented, NOT applied by default
FISHING_CLOSURES: list[dict] = [
    {"name": "turbot ban", "start": "04-15", "end": "06-15", "applies_to": "turbot gillnets (part of the fishing sector)",
     "source": "Ordin MADR/MMAP 23/297/2025 art. 6(3), MO 95/01.02.2025",
     "source_url": "https://legislatie.just.ro/Public/DetaliiDocumentAfis/294196", "applied": False},
]

AIS_SETTINGS = {"years": ["2023", "2024"], "quantile": {"all": 0.90, "fishing": 0.90, "dredging": 0.95}}

# Anchorages from ship traffic: cells where cargo + tanker ships spend many hours per passage (they wait, not transit)
ANCHORAGE_DETECT = {
    "years": ["2023", "2024"],
    "vessel_density": ["vesseldensity_09avg", "vesseldensity_10avg"],  # cargo, tanker: hours/km2/month (annual avg)
    "route_density": ["routedensity_01avg", "routedensity_04avg"],     # cargo, tanker: passages per year
    "min_routes": 20,          # passages per year in the cell (enough traffic to judge)
    "quantile": 0.95,          # seeds: top 5% of hours-per-passage among candidate cells with enough traffic
    "quantile_grow": 0.90,     # hysteresis: seeds grow into connected cells in the top 10%
    "port_reach_m": 25000,     # candidate cells within 25 km of a port area ...
    "port_exclude_m": 1000,    # ... but at least 1 km outside it (berths and shipyard quays)
    "closing": 3,              # 3x3 binary closing (fills one-cell gaps)
    "min_cells": 2,            # minimum area: 2 cells (~3 km2)
}
# Ports used to name the detected areas (EMODnet port points; Sulina = OSM Bazinul Mare) and published references
# used to confirm them (Admiralty Black Sea Pilot NP24, 2003; Constanta Port Handbook polygon via JICA)
ANCHORAGE_PORTS = {"Constanta": (28.65708, 44.13813), "Midia": (28.67828, 44.34473),
                   "Mangalia": (28.59131, 43.80627), "Sulina": (29.6785, 45.1561)}
NP24 = ("Admiralty Black and Azov Seas Pilot NP24 (UKHO 2003), https://ivms.mil.gov.ua/wp-content/uploads/2020/10/"
        "Black_and_Azov_seas_PilotNP-24_2003.pdf")
ANCHORAGE_REFS = {  # port -> published description used to confirm a detected area
    "Mangalia": {"offset_nm": (3.5, 45), "depth": (23, 29), "ref": "NP24: 3.5 nm NE of the harbour entrance, 23-29 m"},
    "Midia": {"depth": (16, 22), "ref": "NP24: 4 nm E of Capul Midia light, 16-22 m"},
    "Sulina": {"depth": (7, 22), "max_km": 15, "ref": "NP24: anchorage in Rada Sulina, 7-22 m"},
    "Constanta": {"polygon": "Constanta roadstead anchorage (zones 1-3)",
                  "ref": "Port Handbook 2000-2001 roadstead zones 1-3 (via JICA) and NP24: 3-8 nm ESE of Capul Constanta"},
}

# --------------------------------------------------------------------------------------------- buffers
# One buffer per activity (no rings). buffer_basis: law | literature | rule. buffer_m = 0 means the mapped area
# itself is the zone (AIS density footprints, published polygons). Editable copy: data/zones/buffers.yaml.
BUFFERS_PATH = OUT_DIR / "buffers.yaml"
LAW_PLATFORM = ("Law 17/1990 art. 16(2): safety zones 'up to 500 m from each point of their outer limits' around "
                "installations in the Romanian EEZ; UNCLOS art. 60(5)")
LAW_RECREATION = ("OMT 1079/2014 Annex 2: nautical recreation zones 'may not extend more than 300 m from the shore'; "
                  "user rule: 300 m seaward from the beach line")
DEFAULT_BUFFERS: dict = {
    "ports": {
        "port_area": {"buffer_m": 1000, "buffer_basis": "rule", "season": "all",
                      "basis_ref": "1 km around basins and terminals: berths, entrance channel, propeller wash and "
                                   "maintenance dredging (harbour turbidity and sediment-contamination near field)"},
        "anchorage": {"buffer_m": 300, "buffer_basis": "rule", "season": "all",
                      "basis_ref": "anchor and chain swing radius: chain about 5-7 x water depth (20-30 m) plus ship length"},
        "shipping_lane": {"buffer_m": 0, "buffer_basis": "rule", "season": "all",
                          "basis_ref": "the AIS cells themselves (top decile of EMSA vessel density, ~1.2 km cells)"},
    },
    "shipyards": {
        "shipyard": {"buffer_m": 500, "buffer_basis": "rule", "season": "all",
                     "basis_ref": "500 m: dry-dock discharge, blasting grit and antifouling residues near the yard"},
        "offshore_platform": {"buffer_m": 500, "buffer_basis": "law", "season": "all", "basis_ref": LAW_PLATFORM},
        "pipeline_cable": {"buffer_m": 1000, "buffer_basis": "law", "season": "all",
                           "basis_ref": "Law 17/1990 (republished MO 252/2014) art. 12(2): safety and protection zones "
                                        "'up to 1,000 m on either side' of the axis of cables and pipelines laid in the sea"},
        "coastal_protection": {"buffer_m": 200, "buffer_basis": "rule", "season": "all",
                               "basis_ref": "200 m: structure footprint plus scour and accretion cell next to it"},
        "beach_nourishment": {"buffer_m": 300, "buffer_basis": "rule", "season": "all",
                              "basis_ref": "300 m seaward of the nourished beach: placement, burial and plume"},
        "dredging_activity": {"buffer_m": 0, "buffer_basis": "rule", "season": "all",
                              "basis_ref": "the AIS cells themselves (top 5% of EMSA dredging / underwater-ops density)"},
    },
    "tourism": {
        "beach": {"buffer_m": 300, "buffer_basis": "law", "season": "summer", "basis_ref": LAW_RECREATION},
        "bathing_water": {"buffer_m": 300, "buffer_basis": "law", "season": "summer",
                          "basis_ref": LAW_RECREATION + "; applied to 500 m of coastline at each EEA bathing-water site"},
        "marina": {"buffer_m": 300, "buffer_basis": "rule", "season": "summer",
                   "basis_ref": "300 m, same as the nautical recreation zone: leisure craft leaving the marina"},
    },
    "fishing": {
        "landing_point": {"buffer_m": 1000, "buffer_basis": "rule", "season": "all",
                          "basis_ref": "1 km around the landing point: boats launching and landing, nets set nearby"},
        "fishing_ground": {"buffer_m": 0, "buffer_basis": "rule", "season": "all",
                           "basis_ref": "the AIS cells themselves (top decile of EMSA fishing-vessel density)"},
        "pound_net_zone": {"buffer_m": 0, "buffer_basis": "rule", "season": "all",
                           "basis_ref": "potential zone only (5-13 m isobaths within 5 km of shore); shown, not counted "
                                        "until NIMRD/ANPA supply the pound-net sites"},
    },
    "aquaculture": {
        "aquaculture_lease": {"buffer_m": 100, "buffer_basis": "literature", "season": "all",
                              "basis_ref": "benthic effects of shellfish longlines and fish cages are mostly within "
                                           "50-100 m of the farm edge (Wilding and Nickell 2013, PLoS ONE 8:e68313; "
                                           "Kalantzi and Karakassis 2006, Mar Pollut Bull 52:484)"},
        "aquaculture_planned": {"buffer_m": 0, "buffer_basis": "rule", "season": "all",
                                "basis_ref": "perimeter offered in a tender but not awarded: shown, not counted"},
    },
}

# --------------------------------------------------------------------------------------------- manual features
# Only coordinates published by a source (exact or converted); nothing estimated by us.
MANUAL_FEATURES: list[dict] = [
    # Ports: anchorages
    {"sector": "ports", "ftype": "anchorage", "name": "Constanta roadstead anchorage (zones 1-3)", "used": False,
     "note": "superseded by the AIS-derived Constanta roadstead anchorage (93% of the AIS area lies inside this "
             "polygon); shown, not counted",
     "coords": [(28.73333, 44.17500), (28.82500, 44.17500), (28.82500, 44.10833), (28.73333, 44.10833)],
     "geom": "polygon", "location_quality": "exact, dated (Constantza Port Handbook 2000-2001)",
     "source": "JICA port study citing the Constantza Port Handbook, https://openjicareport.jica.go.jp/pdf/11682309_03.pdf",
     "licence": "JICA report, public"},
    {"sector": "ports", "ftype": "anchorage", "name": "Midia anchorage",
     "note": "no AIS anchorage signal here in 2023-2024 (cargo/tanker hours per passage < 1): to confirm",
     "coords": [(28.75833, 44.36667), (28.80833, 44.36667), (28.81000, 44.32500), (28.75833, 44.32500)],
     "geom": "polygon", "location_quality": "approximate (port listing citing Admiralty Pilot NP24)",
     "source": "https://shipnext.com/port/5826f924da72a50108cc71cd", "licence": "web listing, facts only"},
    # Shipyards and marine engineering: Neptun Deep (environmental permit, Stereo 70 converted to WGS84)
    {"sector": "shipyards", "ftype": "offshore_platform", "name": "Neptun Alpha production platform (Neptun Deep)",
     "coords": [(30.58746, 44.04751)], "geom": "point", "location_quality": "exact (environmental permit)",
     "source": "APM Constanta environmental permit Neptun Deep, authorised EN translation, https://www.moew.government.bg/static/media/ups/articles/attachments/Neptun%20Deep%20Environmetnal%20Permit%20(EN)%20-%20authorized%20translation%202e9f05664dde01b7d36551c46451d9084.pdf",
     "licence": RO_LAW},
    {"sector": "shipyards", "ftype": "offshore_platform", "name": "Pelican South drill centre PSDC1 (Neptun Deep)",
     "coords": [(30.59985, 44.05533)], "geom": "point", "location_quality": "exact (environmental permit)",
     "source": "APM Constanta environmental permit Neptun Deep (see Neptun Alpha)", "licence": RO_LAW},
    {"sector": "shipyards", "ftype": "offshore_platform", "name": "Ana platform (Midia Gas Development)",
     "coords": [(29.9699, 44.0717)], "geom": "point",
     "location_quality": "approximate (secondary source, Global Energy Monitor wiki; no permit coordinates found)",
     "source": "https://gem.wiki/Ana_Gas_Field_(Romania)", "licence": "CC BY-NC-SA 4.0 (GEM wiki)"},
    {"sector": "shipyards", "ftype": "pipeline_cable",
     "name": "Neptun Deep 30-inch gas pipeline and fibre cable, Tuzla landfall to Neptun Alpha",
     "coords": [(28.65325, 43.97377), (28.66369, 43.97107), (28.69225, 43.96366), (29.63987, 44.02963),
                (29.79992, 44.03412), (29.84227, 44.04054), (29.97840, 44.04048), (30.19947, 44.07861),
                (30.41314, 44.05838), (30.44967, 44.05978), (30.49717, 44.05573), (30.54205, 44.05666),
                (30.58785, 44.04804)],
     "geom": "line", "location_quality": "exact vertices (environmental permit, published selection)",
     "source": "APM Constanta environmental permit Neptun Deep (see Neptun Alpha)", "licence": RO_LAW},
]

# Beach nourishment (Coastal Erosion Reduction project, Phase I 2013-2015 and Phase II 2020-2025):
# place names only in the sources -> EEA bathing-water points whose names match are the location proxy.
NOURISHMENT_LOTS = {
    "Mamaia": r"MAMAIA", "Tomis": r"TOMIS|MODERN|3 PAPUCI|TREI PAPUCI|CAZINO", "Agigea": r"AGIGEA",
    "Eforie": r"EFORIE", "Costinesti": r"COSTINESTI", "Olimp": r"OLIMP", "Jupiter-Neptun": r"JUPITER|NEPTUN",
    "Venus-Aurora": r"VENUS|AURORA", "Mangalia-Saturn": r"MANGALIA|SATURN", "2 Mai": r"2 MAI|DOI MAI",
}
NOURISHMENT_SOURCE = ("Romanian Waters 'Reduction of coastal erosion' Phase I (2013-2015) and Phase II lots, "
                      "https://rowater.ro/institution-activity/projects/projects-under-implementation/"
                      "reduction-and-rehabilitation-of-the-coastal-zone/?lang=en")

# Fishing landing points, Ordin MADR 650/2015 annex (place names only) -> OSM name used to locate each
LANDING_POINTS = {  # Ordin MADR 5/2026 annex 3 (place names / addresses) -> OSM place, beach or EMODnet lighthouse
    "Vama Veche (Usa din Vama)": ("place", "Vama Veche"), "2 Mai": ("place", "2 Mai"),
    "Mangalia (pescarie, pod mobil)": ("place", "Mangalia"), "Olimp": ("place", "Olimp"),
    "23 August": ("place", "Plaja 23 August"), "Tuzla": ("place", "Tuzla"), "Eforie Sud (dig nou)": ("place", "Eforie Sud"),
    "Eforie Nord (Belona)": ("place", "Eforie Nord"), "Agigea (cherhana)": ("place", "Agigea"),
    "Mamaia (bd. Mamaia 306/312D)": ("place", "Mamaia"), "Mamaia Sat (canal dyke)": ("place", "Mamaia-Sat"),
    "Midia (Navodari south dyke: Dig Teu, Bujor)": ("place", "Năvodari"), "Cap Midia": ("lighthouse", "Capul Midia"),
    "Corbu (beach)": ("place", "Corbu"), "Vadu (cherhana)": ("place", "Vadu"),
    "Periboina / Gura Portitei": ("place", "Gura Portiței"), "Edighiol (Sinoe outlet)": ("place", "Plaja Edighiol"),
    "Sfantu Gheorghe": ("place", "Sfântu Gheorghe"), "Sulina": ("place", "Sulina"),
}
LANDING_SOURCE = ("Ordin MADR 5/15.01.2026 annex 3 (landing points and first-sale centres, MO 32/16.01.2026), "
                  "https://faolex.fao.org/docs/pdf/rom244461.pdf")

# Aquaculture: stretches named in the 2024 Apele Romane tender (10 perimeters awarded, 60 ha), 2-3 km offshore
AQUA_STRETCHES = {
    "Mamaia - Constanta (off Lake Siutghiol)": ("Mamaia", "Pescărie"),
    "Agigea - Eforie Nord": ("Agigea", "Eforie Nord"),
    "Venus": ("Venus", None),
    "2 Mai - Vama Veche": ("2 Mai", "Vama Veche"),
}
AQUA_OFFSHORE_M = (2000, 3000)
AQUA_SOURCE = ("2024 ABA Dobrogea-Litoral tender, 28 perimeters offered, 10 awarded: https://economedia.ro/?p=225348 ; "
               "https://www.economica.net/apele-romane-scot-la-licitatie-28-de-perimetre-din-mediul-marin-pentru-inchirierea-pe-20-de-ani_775331.html")

# Management areas used to subtract potential fishing grounds (no fishing all year)
NO_FISHING_AREAS = [
    {"name": "2 Mai - Vama Veche marine reserve, zone B (no fishing all year)",
     "coords": [(28.58085, 43.78828), (28.72770, 43.78356), (28.72394, 43.72423), (28.57897, 43.73891)],
     "source": "Ordin MADR/MMAP 10/235/2023 art. 3, https://faolex.fao.org/docs/pdf/rom216716.pdf"},
]

FIXED_GEAR_MAX_OFFSHORE_M = 5000  # assumption: pound nets / fixed gillnets set within 5 km of the shore

AIS_TYPES = {"all": "allavg", "fishing": "01avg", "dredging": "03avg"}


# --------------------------------------------------------------------------------------------- download helpers
def _cache(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


OVERPASS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def _overpass(name: str, body: str, bbox=(43.5, 28.3, 45.5, 30.7)) -> dict:
    """Run an Overpass query (body uses {B} for the bbox), cached as data/cache/pressure_zones/osm_<name>.json."""
    p = _cache(f"osm_{name}.json")
    if p.exists():
        return json.loads(p.read_text())
    b = ",".join(str(v) for v in bbox)
    q = "[out:json][timeout:150];" + body.replace("{B}", b)
    last = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=TIMEOUT)
            if r.status_code == 200 and r.content[:1] == b"{":
                j = r.json()
                p.write_text(json.dumps(j))
                return j
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = e
    raise RuntimeError(f"all Overpass mirrors failed for {name}: {last}")


def _wfs(url: str, layer: str, name: str, cql: str | None = None, bbox=BBOX_RO) -> dict:
    """WFS 1.0.0 GetFeature as GeoJSON (lon/lat axis order), cached."""
    p = _cache(f"{name}.json")
    if p.exists():
        return json.loads(p.read_text())
    params = {"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": layer,
              "outputFormat": "application/json", "srsName": "EPSG:4326"}
    if cql:
        params["CQL_FILTER"] = cql
    else:
        params["bbox"] = ",".join(str(v) for v in bbox)
    r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    p.write_text(json.dumps(j))
    return j


def _ha(layer: str) -> dict:
    return _wfs("https://ows.emodnet-humanactivities.eu/wfs", f"emodnet:{layer}", f"ha_{layer}")


def _read_geotiff(path: Path):
    """Minimal GeoTIFF reader (no rasterio): array, affine (a, c, e, f) with x = c + a*col, y = f + e*row, EPSG."""
    im = Image.open(path)
    arr = np.array(im).astype("float64")
    t = im.tag_v2.get(34264)  # ModelTransformationTag
    geo = im.tag_v2.get(34735)  # GeoKeyDirectory
    if t is None:  # fall back to ModelPixelScale + ModelTiepoint
        sx, sy, _ = im.tag_v2[33550]
        _, _, _, tx, ty, _ = im.tag_v2[33922]
        a, c, e, f = sx, tx, -sy, ty
    else:
        a, c, e, f = t[0], t[3], t[5], t[7]
    epsg = None
    if geo:
        keys = [geo[i:i + 4] for i in range(4, len(geo), 4)]
        for k in keys:
            if k[0] in (2048, 3072):
                epsg = k[3]
    nod = im.tag_v2.get(42113)
    if nod is not None:
        arr[arr == float(nod)] = np.nan
    arr[arr < -1e30] = np.nan
    return arr, (a, c, e, f), epsg


def _bathymetry():
    """EMODnet DTM (mean depth), 1/240 deg (~330-460 m) over BBOX_RO, elevation m (negative = below sea level)."""
    p = _cache("bathy_ro.tif")
    if not p.exists():
        x0, y0, x1, y1 = BBOX_RO
        url = ("https://ows.emodnet-bathymetry.eu/wcs?service=WCS&version=1.0.0&request=GetCoverage"
               f"&coverage=emodnet:mean&crs=EPSG:4326&BBOX={x0},{y0},{x1},{y1}&format=image/tiff"
               "&RESX=0.004166667&RESY=0.004166667")
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        p.write_bytes(r.content)
    return _read_geotiff(p)


def _vessel_density(kind: str):
    """EMSA AIS vessel density (EMODnet HA WCS, hours/km2/month), mean over AIS_SETTINGS years, EPSG:3857 grid."""
    cov = "emodnet__vesseldensity_" + AIS_TYPES[kind]
    t = Transformer.from_crs(CRS_LL, "EPSG:3857", always_xy=True)
    x0, y0 = t.transform(BBOX_RO[0], BBOX_RO[1])
    x1, y1 = t.transform(BBOX_RO[2], BBOX_RO[3])
    arrs, aff, epsg = [], None, None
    for yr in AIS_SETTINGS["years"]:
        p = _cache(f"vd_vesseldensity_{AIS_TYPES[kind]}_{yr}.tif")
        if not p.exists():
            params = [("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"), ("coverageId", cov),
                      ("format", "image/tiff"), ("subset", f"X({x0},{x1})"), ("subset", f"Y({y0},{y1})"),
                      ("subset", f'time("{yr}-01-01T00:00:00.000Z")')]
            r = requests.get("https://ows.emodnet-humanactivities.eu/wcs", params=params, headers=UA,
                             timeout=TIMEOUT)
            if not r.headers.get("content-type", "").startswith("image"):
                raise RuntimeError(f"WCS {cov} {yr}: {r.text[:200]}")
            p.write_bytes(r.content)
        a, aff, epsg = _read_geotiff(p)
        arrs.append(a)
    return np.nanmean(np.stack(arrs), axis=0), aff, epsg


def _ha_wcs(coverage: str, year: str):
    """One EMODnet Human Activities WCS coverage (e.g. 'vesseldensity_09avg', 'routedensity_01avg') for one year over
    BBOX_RO, EPSG:3857 grid, cached as GeoTIFF. Returns (array, affine (a, c, e, f), epsg); nodata -> NaN."""
    t = Transformer.from_crs(CRS_LL, "EPSG:3857", always_xy=True)
    x0, y0 = t.transform(BBOX_RO[0], BBOX_RO[1])
    x1, y1 = t.transform(BBOX_RO[2], BBOX_RO[3])
    p = _cache(f"wcs_{coverage}_{year}.tif")
    if not p.exists():
        params = [("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
                  ("coverageId", f"emodnet__{coverage}"), ("format", "image/tiff"), ("subset", f"X({x0},{x1})"),
                  ("subset", f"Y({y0},{y1})"), ("subset", f'time("{year}-01-01T00:00:00.000Z")')]
        r = requests.get("https://ows.emodnet-humanactivities.eu/wcs", params=params, headers=UA, timeout=TIMEOUT)
        if not r.headers.get("content-type", "").startswith("image"):
            raise RuntimeError(f"WCS {coverage} {year}: {r.text[:200]}")
        p.write_bytes(r.content)
    return _read_geotiff(p)


def _mask_to_polygon(mask: np.ndarray, aff, crs_from) -> shapely.Geometry:
    """Union of raster cells where mask is True (row runs merged), reprojected to CRS_M."""
    a, c, e, f = aff
    boxes = []
    for r in range(mask.shape[0]):
        row = mask[r]
        if not row.any():
            continue
        d = np.diff(np.concatenate([[0], row.astype(int), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        for s, en in zip(starts, ends):
            boxes.append(box(c + a * s, f + e * (r + 1), c + a * en, f + e * r))
    if not boxes:
        return Polygon()
    g = gpd.GeoSeries([unary_union(boxes)], crs=crs_from).to_crs(CRS_M).iloc[0]
    return shapely.make_valid(g)


# --------------------------------------------------------------------------------------------- coastline / sea
def _to_m(geom, crs_from=CRS_LL):
    return gpd.GeoSeries([geom], crs=crs_from).to_crs(CRS_M).iloc[0]


@lru_cache(maxsize=1)
def _coast_lines_ll():
    j = _overpass("coastline", 'way["natural"="coastline"]({B});out geom;')
    ls = [LineString([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in j["elements"] if e.get("geometry")]
    merged = linemerge(unary_union(ls))
    parts = list(getattr(merged, "geoms", [merged]))
    open_lines = [g for g in parts if not g.is_ring]
    islands = [Polygon(g.coords) for g in parts if g.is_ring]
    return open_lines, islands


@lru_cache(maxsize=1)
def sea_polygon() -> shapely.Geometry:
    """Black Sea water inside BBOX_RO (EPSG:32635), from the OSM coastline (land on the left of each way).
    The bbox is split by the mainland coastline; the face whose centre is below sea level in the EMODnet DTM is
    the sea. Islands (closed coastline rings, incl. moles and breakwater 'islands') are removed. Lagoons
    (Razim-Sinoe, Siutghiol, Tasaul) are not sea."""
    p = _cache("sea_polygon_utm35n.wkb")
    if p.exists():
        return shapely.from_wkb(p.read_bytes())
    open_lines, islands = _coast_lines_ll()
    bb = box(*BBOX_RO)
    faces = list(polygonize(unary_union([bb.boundary] + [ln.intersection(bb) for ln in open_lines])))
    arr, aff, _ = _bathymetry()
    a, c, e, f = aff

    def elev(pt):
        col = int((pt.x - c) / a)
        row = int((pt.y - f) / e)
        row, col = min(max(row, 0), arr.shape[0] - 1), min(max(col, 0), arr.shape[1] - 1)
        return arr[row, col]

    sea = [fc for fc in faces if elev(fc.representative_point()) < 0]
    geom = unary_union(sea).difference(unary_union(islands))
    geom = shapely.make_valid(_to_m(geom))
    p.write_bytes(shapely.to_wkb(geom))
    return geom


@lru_cache(maxsize=1)
def coastline() -> shapely.Geometry:
    """Mainland + island coastline inside BBOX_RO as lines (EPSG:32635)."""
    open_lines, islands = _coast_lines_ll()
    bb = box(*BBOX_RO)
    lines = [ln.intersection(bb) for ln in open_lines] + [i.exterior.intersection(bb) for i in islands]
    return _to_m(unary_union(lines))


@lru_cache(maxsize=1)
def _main_coast_m() -> LineString:
    """The single mainland coastline line (unclipped, EPSG:32635), used for along-shore stretches."""
    open_lines, _ = _coast_lines_ll()
    return _to_m(max(open_lines, key=lambda g: g.length))


@lru_cache(maxsize=1)
def ro_domain() -> shapely.Geometry:
    """Romania EEZ + land (Marine Regions eez_land, CC BY 4.0), EPSG:32635."""
    j = _wfs("https://geo.vliz.be/geoserver/MarineRegions/wfs", "MarineRegions:eez_land", "mr_eez_land",
             cql="territory1='Romania'")
    return shapely.make_valid(_to_m(unary_union([shape(f["geometry"]) for f in j["features"]])))


@lru_cache(maxsize=1)
def ro_sea() -> shapely.Geometry:
    """Romanian sea inside the bbox: sea_polygon() inside the Romanian EEZ (Marine Regions eez, CC BY 4.0)."""
    j = _wfs("https://geo.vliz.be/geoserver/MarineRegions/wfs", "MarineRegions:eez", "mr_eez",
             cql="sovereign1='Romania'")
    eez = shapely.make_valid(_to_m(unary_union([shape(f["geometry"]) for f in j["features"]])))
    # the EEZ polygon starts at its own (coarser) shoreline: grow it 2 km landward so harbours and the
    # surf zone along the OSM coastline are kept, then cut with the OSM sea
    eez_plus = eez.buffer(2000).intersection(ro_domain())
    return shapely.make_valid(sea_polygon().intersection(eez_plus))


# --------------------------------------------------------------------------------------------- OSM features
# Split in small queries: public Overpass servers time out on one big request. Coastal strip bbox only
# (the Romanian coast lies east of 28.55 E), so inland Dobrogea pipelines and quarries are not downloaded.
OSM_STRIP = (43.6, 28.5, 45.4, 30.6)
OSM_FEATURE_QUERIES = {
    "tourism": """(nwr["natural"="beach"]({B});nwr["leisure"="marina"]({B}););out geom;""",
    "ports": """(nwr["landuse"="port"]({B});nwr["landuse"="harbour"]({B});nwr["industrial"="port"]({B});
                 nwr["industrial"="shipyard"]({B});nwr["seamark:type"="harbour_basin"]({B});
                 nwr["seamark:type"="anchorage"]({B});nwr["landuse"="aquaculture"]({B}););out geom;""",
    "structures": """(nwr["man_made"~"^(breakwater|groyne|offshore_platform)$"]({B}););out geom;""",
    "pipelines": """(way["man_made"="pipeline"]({B}););out geom;""",
}

COASTAL_PLACES = ("Vama Veche|2 Mai|Mangalia|Saturn|Venus|Cap Aurora|Jupiter|Neptun|Olimp|Costinești|Tuzla|"
                  "Eforie Sud|Eforie Nord|Agigea|Constanța|Mamaia|Mamaia-Sat|Năvodari|Corbu|Vadu|Grindul Lupilor|"
                  "Gura Portiței|Periboina|Sfântu Gheorghe|Sulina|Sinoe|Istria|Jurilovca|Lumina|Ovidiu")
OSM_PLACES_Q = """(
 node["place"]["name"~"^(""" + COASTAL_PLACES + """)$"]({B});
 nwr["natural"="beach"]["name"]({B});
);out center tags;"""


def _osm_geom(e: dict):
    if e["type"] == "node":
        return Point(e["lon"], e["lat"])
    if e["type"] == "way":
        pts = [(p["lon"], p["lat"]) for p in e.get("geometry", [])]
        if len(pts) < 2:
            return None
        if len(pts) >= 4 and pts[0] == pts[-1] and e.get("tags", {}).get("man_made") not in (
                "pipeline", "breakwater", "groyne"):
            return Polygon(pts)
        return LineString(pts)
    if e["type"] == "relation":
        outers, inners = [], []
        for m in e.get("members", []):
            if m.get("type") != "way" or not m.get("geometry"):
                continue
            ln = LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
            (inners if m.get("role") == "inner" else outers).append(ln)
        polys = list(polygonize(unary_union(outers))) if outers else []
        if not polys:
            return None
        g = unary_union(polys)
        if inners:
            g = g.difference(unary_union(list(polygonize(unary_union(inners)))))
        return g
    return None


def _osm_elements() -> list[dict]:
    els, seen = [], set()
    for name, q in OSM_FEATURE_QUERIES.items():
        try:
            got = _overpass(f"features_{name}", q, bbox=OSM_STRIP)["elements"]
        except RuntimeError as err:  # keep building with what is cached; say what is missing
            import warnings

            warnings.warn(f"OSM {name} layer missing from this build: {err}")
            continue
        for e in got:
            if (e["type"], e["id"]) not in seen:
                seen.add((e["type"], e["id"]))
                els.append(e)
    return els


@lru_cache(maxsize=1)
def places() -> gpd.GeoDataFrame:
    """Named OSM places and named beaches (point), EPSG:32635; used to geocode place-name-only sources and to
    name hotspots."""
    j = _overpass("places", OSM_PLACES_Q, bbox=(43.6, 28.4, 45.4, 29.9))
    rows = []
    for e in j["elements"]:
        t = e.get("tags", {})
        if "name" not in t:
            continue
        c = e.get("center") or {"lon": e.get("lon"), "lat": e.get("lat")}
        if c.get("lon") is None:
            continue
        rows.append({"name": t["name"], "kind": t.get("place", "beach"), "osm": f"{e['type']}/{e['id']}",
                     "geometry": Point(c["lon"], c["lat"])})
    g = gpd.GeoDataFrame(rows, crs=CRS_LL).to_crs(CRS_M)
    return g[g.intersects(ro_domain())].reset_index(drop=True)


def _place(name: str, kind: str = "place") -> Point | None:
    """Location of a named place (OSM place node / beach, or EMODnet lighthouse), EPSG:32635, nearest the coast."""
    if kind == "lighthouse":
        j = _ha("lighthouses")
        for f in j["features"]:
            if f["properties"].get("name") == name:
                return _to_m(shape(f["geometry"]))
        return None
    pl = places()
    hit = pl[pl["name"] == name]
    if hit.empty:
        return None
    coast = _main_coast_m()
    return min(hit.geometry, key=lambda g: g.distance(coast))


def _snap_to_coast(pt: Point) -> Point:
    coast = _main_coast_m()
    return coast.interpolate(coast.project(pt))


def _coast_stretch(p0: Point, p1: Point | None, half_m: float = 2000) -> LineString:
    """Mainland coastline between two points (or +-half_m around one point), EPSG:32635."""
    coast = _main_coast_m()
    s0 = coast.project(p0)
    if p1 is None:
        a, b = s0 - half_m, s0 + half_m
    else:
        s1 = coast.project(p1)
        a, b = min(s0, s1), max(s0, s1)
    return substring(coast, max(a, 0), min(b, coast.length))




# --------------------------------------------------------------------------------------------- season
def season_for_date(date) -> str:
    """'summer' (bathing season, 1 June - 15 September inclusive: tourism on) or 'winter' (tourism off).
    date: datetime.date / datetime / pandas Timestamp / ISO string."""
    d = pd.Timestamp(date)
    md = (d.month, d.day)
    return "summer" if BATHING_SEASON["start"] <= md <= BATHING_SEASON["end"] else "winter"


# --------------------------------------------------------------------------------------------- features
OSM_URL = "https://www.openstreetmap.org/{}/{}"
EMOD_WFS_URL = "https://ows.emodnet-humanactivities.eu/wfs?service=WFS&request=GetFeature&typeName=emodnet:{}"
NEPTUN_PERMIT_URL = ("https://www.moew.government.bg/static/media/ups/articles/attachments/Neptun%20Deep%20Environmetnal"
                     "%20Permit%20(EN)%20-%20authorized%20translation%202e9f05664dde01b7d36551c46451d9084.pdf")


def _first_url(s: str) -> str:
    m = re.search(r"https?://[^\s;,)]+", s or "")
    return m.group(0) if m else ""


def _row(sector, activity, name, geom_m, source, source_url, confidence, note="", season=None, used=True, **extra):
    assert confidence in CONFIDENCE, confidence
    if season is None:
        season = DEFAULT_BUFFERS.get(sector, {}).get(activity, {}).get("season", "all")
    return {"sector": sector, "activity": activity, "name": name or "", "source": source, "source_url": source_url,
            "confidence": confidence, "season": season, "note": note, "used_in_zones": used, "geometry": geom_m,
            **extra}


def _osm_rows() -> list[dict]:
    rows = []
    sea = sea_polygon()
    for e in _osm_elements():
        t = e.get("tags", {})
        g = _osm_geom(e)
        if g is None or g.is_empty:
            continue
        g = shapely.make_valid(_to_m(g))
        name = t.get("name") or t.get("seamark:name") or ""
        src = f"OpenStreetMap {e['type']}/{e['id']} (ODbL)"
        url = OSM_URL.format(e["type"], e["id"])
        mm, ind, lu, st = t.get("man_made"), t.get("industrial"), t.get("landuse"), t.get("seamark:type")

        def add(sector, activity, nm, note=""):
            rows.append(_row(sector, activity, nm, g, src, url, "mapped", note))

        if t.get("natural") == "beach":
            add("tourism", "beach", name)
        elif t.get("leisure") == "marina" and re.match(r"Doc ", name):
            add("shipyards", "shipyard", name, "tagged leisure=marina in OSM; a dry dock")
        elif t.get("leisure") == "marina" and re.match(r"Dana ", name):
            add("ports", "port_area", name, "tagged leisure=marina in OSM; a port berth")
        elif t.get("leisure") == "marina":
            add("tourism", "marina", name)
        elif ind == "shipyard" or re.search(r"[Șș]antierul Naval|Shipyard|SORENA", name, re.I):
            add("shipyards", "shipyard", name)
        elif mm == "offshore_platform":
            pass  # superseded by the official ACROPO installation list (EXTRA_FEATURES)
        elif mm in ("breakwater", "groyne"):
            add("shipyards", "coastal_protection", name or mm)
        elif mm == "pipeline":
            if g.intersection(sea).length > 200:  # only pipelines that run in the sea
                add("shipyards", "pipeline_cable", name or f"pipeline {t.get('substance', '')}".strip())
        elif ind == "port" or lu in ("port", "harbour") or st == "harbour_basin":
            add("ports", "port_area", name or "harbour basin")
        elif st in ("anchorage", "anchor_berth"):
            add("ports", "anchorage", name)
        elif lu == "aquaculture":
            add("aquaculture", "aquaculture_lease", name)
    return rows


def _emodnet_rows() -> list[dict]:
    rows = []
    for f in _ha("portlocations")["features"]:
        p = f["properties"]
        rows.append(_row("ports", "port_area", f"{p['portname']} (EMODnet port location)", _to_m(shape(f["geometry"])),
                         f"{EMOD_HA} portlocations {p['port_id']} ({EMOD_LIC})", EMOD_WFS_URL.format("portlocations"),
                         "official", "port reference point"))
    bw = [f for f in _ha("bathingwaters")["features"]
          if f["properties"].get("countrycod") == "RO" and str(f["properties"].get("year")) == "2024"]
    for f in bw:
        p = f["properties"]
        rows.append(_row("tourism", "bathing_water", p["bwname"].title(), _to_m(shape(f["geometry"])),
                         f"EEA bathing water {p['bwid']} via {EMOD_HA} bathingwaters, 2024, class {p.get('class')}",
                         EMOD_WFS_URL.format("bathingwaters"), "official", "EU Bathing Water Directive site"))
    for f in []:  # EMODnet wind-farm points superseded by the 2026 official perimeter list (EXTRA_FEATURES)
        p = f["properties"]
        if p.get("country") == "Romania":
            rows.append(_row("shipyards", "offshore_wind_planned",
                             f"{p['name']} ({p.get('status')}, {p.get('power_mw')} MW)", _to_m(shape(f["geometry"])),
                             f"{EMOD_HA} windfarms ({EMOD_LIC})", EMOD_WFS_URL.format("windfarms"), "official",
                             "planned project: shown, not counted", used=False))
    return rows


def _manual_confidence(m: dict) -> str:
    if "confidence" in m:
        return m["confidence"]
    q = m.get("location_quality", "")
    return "official" if q.startswith("exact") and "dated" not in q else "assumed"


def _manual_rows() -> list[dict]:
    rows = []
    for m in MANUAL_FEATURES:
        g = {"point": lambda c: Point(c[0]), "line": LineString, "polygon": Polygon}[m["geom"]](m["coords"])
        url = m.get("url") or _first_url(m["source"]) or (NEPTUN_PERMIT_URL if "Neptun" in m["name"] else "")
        note = "; ".join(x for x in (m.get("location_quality", ""), m.get("note", "")) if x)
        rows.append(_row(m["sector"], m.get("activity", m.get("ftype")), m["name"], _to_m(g), m["source"], url,
                         _manual_confidence(m), note, used=m.get("used", True)))
    # beach nourishment lots (project lists place names only): coastline at the resort's EEA bathing-water points
    bw = [f for f in _ha("bathingwaters")["features"]
          if f["properties"].get("countrycod") == "RO" and str(f["properties"].get("year")) == "2024"]
    for lot, rx in NOURISHMENT_LOTS.items():
        pts = [_to_m(shape(f["geometry"])) for f in bw if re.search(rx, f["properties"]["bwname"], re.I)]
        if not pts:
            continue
        segs = [_coast_stretch(_snap_to_coast(pt), None, half_m=250) for pt in pts]
        rows.append(_row("shipyards", "beach_nourishment", f"Beach nourishment lot {lot}", unary_union(segs),
                         NOURISHMENT_SOURCE, _first_url(NOURISHMENT_SOURCE), "assumed",
                         f"lot listed by the project (place name only); located at {len(pts)} EEA bathing-water "
                         "site(s) of the resort"))
    # fishing landing points (Ordin 650/2015 lists place names only)
    for lp, (kind, osm_name) in LANDING_POINTS.items():
        pt = _place(osm_name, kind)
        if pt is None:
            continue
        rows.append(_row("fishing", "landing_point", lp, _snap_to_coast(pt), LANDING_SOURCE, _first_url(LANDING_SOURCE),
                         "assumed", f"listed in an official order (place name only); located at '{osm_name}' "
                                    "and snapped to the coastline"))
    return rows


def _depth_band(dmin, dmax) -> shapely.Geometry:
    """Seabed between dmin and dmax metres deep (EMODnet DTM, ~400 m cells), EPSG:32635."""
    arr, aff, epsg = _bathymetry()
    depth = -arr
    return _mask_to_polygon((depth >= dmin) & (depth <= dmax), aff, f"EPSG:{epsg or 4326}")


def _ais_footprint(kind: str):
    """Cells of EMSA AIS vessel density above the AIS_SETTINGS quantile (of cells with traffic in Romanian waters)."""
    import warnings

    rs = ro_sea()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        arr, aff, epsg = _vessel_density(kind)
        if kind == "all":  # shipping = all ships minus dredgers / underwater ops (counted under shipyards)
            dr, _, _ = _vessel_density("dredging")
            arr = np.where(np.isfinite(arr), arr - np.nan_to_num(dr), np.nan)
    a, c, e, f = aff
    cols, rws = np.meshgrid(np.arange(arr.shape[1]) + 0.5, np.arange(arr.shape[0]) + 0.5)
    mx, my = Transformer.from_crs(f"EPSG:{epsg or 3857}", CRS_M, always_xy=True).transform(c + a * cols, f + e * rws)
    shapely.prepare(rs)
    inside = shapely.contains_xy(rs, mx, my)
    vals = arr[inside & np.isfinite(arr) & (arr > 0)]
    thr = float(np.quantile(vals, AIS_SETTINGS["quantile"][kind])) if vals.size else np.inf
    g = _mask_to_polygon(np.isfinite(arr) & (arr >= thr), aff, f"EPSG:{epsg or 3857}").intersection(rs)
    return g, thr


def detect_anchorages() -> tuple[list[dict], dict]:
    """Anchorage areas from EMODnet AIS: cells where cargo + tanker vessels spend many hours per passage.
    ratio = 12 * vessel density (h/km2/month) / route density (passages/yr) = hours per km2 per passage.
    Returns (rows for sector_features, info dict with the threshold and per-area statistics)."""
    from scipy import ndimage

    cfg = ANCHORAGE_DETECT

    def mean(covs):
        tot = None
        for cov in covs:
            a = np.nanmean(np.stack([_ha_wcs(cov, y)[0] for y in cfg["years"]]), axis=0)
            tot = np.nan_to_num(a) if tot is None else tot + np.nan_to_num(a)
        return tot

    vd, rd = mean(cfg["vessel_density"]), mean(cfg["route_density"])
    _, aff, epsg = _ha_wcs(cfg["vessel_density"][0], cfg["years"][0])
    a, c, e, f = aff
    cols, rws = np.meshgrid(np.arange(vd.shape[1]) + 0.5, np.arange(vd.shape[0]) + 0.5)
    mx, my = Transformer.from_crs(f"EPSG:{epsg or 3857}", CRS_M, always_xy=True).transform(c + a * cols, f + e * rws)
    feats = _all_features_m_base()
    ports = unary_union(feats[feats.activity == "port_area"].geometry.values)
    near, excl, rs = ports.buffer(cfg["port_reach_m"]), ports.buffer(cfg["port_exclude_m"]), ro_sea()
    for g in (near, excl, rs):
        shapely.prepare(g)
    cand = shapely.contains_xy(rs, mx, my) & shapely.contains_xy(near, mx, my) & ~shapely.contains_xy(excl, mx, my)
    ratio = np.where(rd > 0, 12 * vd / np.maximum(rd, 1), 0.0)
    ok = cand & (rd >= cfg["min_routes"])
    thr = float(np.quantile(ratio[ok], cfg["quantile"]))
    thr_grow = float(np.quantile(ratio[ok], cfg["quantile_grow"]))
    seeds = ok & (ratio >= thr)
    grow_lab, _ = ndimage.label(ok & (ratio >= thr_grow), structure=np.ones((3, 3)))
    sel = np.isin(grow_lab, np.unique(grow_lab[seeds & (grow_lab > 0)]))  # hysteresis thresholding
    k = cfg["closing"]
    sel = ndimage.binary_closing(sel, structure=np.ones((k, k))) & cand
    lab, n = ndimage.label(sel, structure=np.ones((3, 3)))
    arr_b, aff_b, _ = _bathymetry()
    to_ll = Transformer.from_crs(CRS_M, CRS_LL, always_xy=True)

    def median_depth(g):
        x0, y0, x1, y1 = g.bounds
        X, Y = np.meshgrid(np.linspace(x0, x1, 40), np.linspace(y0, y1, 40))
        ins = shapely.contains_xy(g, X, Y)
        lo, la = to_ll.transform(X[ins], Y[ins])
        ab, cb, eb, fb = aff_b
        cc = np.clip(((np.asarray(lo) - cb) / ab).astype(int), 0, arr_b.shape[1] - 1)
        rr = np.clip(((np.asarray(la) - fb) / eb).astype(int), 0, arr_b.shape[0] - 1)
        return float(np.nanmedian(-arr_b[rr, cc]))

    port_pts = {k: _to_m(Point(v)) for k, v in ANCHORAGE_PORTS.items()}
    published = {r["name"]: r["geometry"] for r in _manual_rows() if r["activity"] == "anchorage"}
    compass = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    yrs = "+".join(cfg["years"])
    url = ("https://ows.emodnet-humanactivities.eu/wcs?service=WCS&request=DescribeCoverage&version=2.0.1&"
           "coverageId=emodnet__routedensity_01avg")
    rows, info = [], {"threshold_h_per_passage": round(thr, 2), "grow_threshold_h_per_passage": round(thr_grow, 2),
                      "candidate_cells": int(ok.sum()), "areas": []}
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < cfg["min_cells"]:
            continue
        g = _mask_to_polygon(m, aff, f"EPSG:{epsg or 3857}").intersection(rs)
        cpt = g.representative_point()
        port = min(port_pts, key=lambda k: port_pts[k].distance(cpt))
        pp = port_pts[port]
        d = pp.distance(cpt) / 1000
        brg = (np.degrees(np.arctan2(cpt.x - pp.x, cpt.y - pp.y)) + 360) % 360
        depth = median_depth(g)
        ref, confirm = ANCHORAGE_REFS.get(port, {}), ""
        if "polygon" in ref and ref["polygon"] in published:
            pg = published[ref["polygon"]]
            share = g.intersection(pg).area / g.area
            if share >= 0.5:
                confirm = (f"{share:.0%} of the area lies inside the published roadstead, covering "
                           f"{g.intersection(pg).area / pg.area:.0%} of it ({ref['ref']})")
        elif "offset_nm" in ref:
            nm, b = ref["offset_nm"]
            rp = Point(pp.x + nm * 1852 * np.sin(np.radians(b)), pp.y + nm * 1852 * np.cos(np.radians(b)))
            lo, hi = ref["depth"]
            if g.distance(rp) <= 2000 and lo - 3 <= depth <= hi + 3:
                confirm = f"{g.distance(rp) / 1000:.1f} km from the published position, median depth {depth:.0f} m ({ref['ref']})"
        elif "depth" in ref and d <= ref.get("max_km", 15):
            lo, hi = ref["depth"]
            if lo <= depth <= hi:
                confirm = f"median depth {depth:.0f} m within the published range ({ref['ref']})"
        kind = "anchorage" if confirm else "waiting area"
        name = f"{port} {kind}, {d:.0f} km {compass[int(((brg + 22.5) % 360) // 45)]} (AIS-derived)"
        stats = {"cells": int(m.sum()), "area_km2": round(g.area / 1e6, 1), "port": port, "distance_km": round(d, 1),
                 "bearing_deg": round(float(brg)), "median_depth_m": round(depth), "confirmed_by": confirm or "none",
                 "hours_per_passage_median": round(float(np.median(ratio[m])), 2),
                 "cargo_tanker_hours_km2_month_median": round(float(np.median(vd[m])), 1),
                 "passages_per_year_median": int(np.median(rd[m]))}
        info["areas"].append({"name": name, **stats})
        conf = "mapped" if confirm else "assumed"
        rows.append(_row("ports", "anchorage", name, g,
                         f"{EMOD_HA}: EMSA AIS vessel density (cargo vesseldensity_09avg + tanker _10avg) and route "
                         f"density (cargo routedensity_01avg + tanker _04avg), mean {yrs} ({EMOD_LIC})", url, conf,
                         f"derived {yrs}: cells with >= {cfg['min_routes']} cargo+tanker passages/yr, within "
                         f"{cfg['port_reach_m'] // 1000} km of a port and >= {cfg['port_exclude_m'] // 1000} km outside "
                         f"it, hours per passage in the top {round((1 - cfg['quantile']) * 100)}% (>= {thr:.2f}) grown into "
                         f"connected cells in the top {round((1 - cfg['quantile_grow']) * 100)}% (>= {thr_grow:.2f}); "
                         f"3x3 closing, min {cfg['min_cells']} cells. Median {stats['hours_per_passage_median']} h per "
                         f"passage, {stats['passages_per_year_median']} passages/yr, area {stats['area_km2']} km2, median depth "
                         f"{stats['median_depth_m']} m. " + (f"Confirmed: {confirm}." if confirm else
                         "Not in any published anchorage list: ships wait or drift here; to confirm with the harbour master.")))
    return rows, info


def _derived_rows() -> list[dict]:
    rows = []
    for a in NO_FISHING_AREAS:
        rows.append(_row("management", "no_fishing_area", a["name"], _to_m(Polygon(a["coords"])), a["source"],
                         _first_url(a["source"]), "official", "legal act, ETRS89 corners; context, not counted",
                         used=False))
    # pound nets: sites not public; potential zone = 5-13 m isobaths (Totoiu et al. 2016) within 5 km of shore,
    # minus the no-fishing reserve. Shown hatched, NOT counted until NIMRD / ANPA supply the sites.
    nofish = unary_union([_to_m(Polygon(a["coords"])) for a in NO_FISHING_AREAS])
    band = shapely.make_valid(_depth_band(5, 13)).intersection(ro_sea()).intersection(
        _main_coast_m().buffer(FIXED_GEAR_MAX_OFFSHORE_M)).difference(nofish)
    rows.append(_row("fishing", "pound_net_zone", "Potential pound-net (taliene) zone, 5-13 m depth", band,
                     "Totoiu et al. 2016, Turk J Fish Aquat Sci 16:371 (21 pound nets in 2014 on the 5-13 m isobaths); "
                     "Ordin 388/2016 (submersible pound nets at 3-14 m); EMODnet Bathymetry DTM",
                     "https://trjfas.org/pdf.php?id=881", "assumed",
                     "potential zone from depth limits; individual sites not public (NIMRD logged them by GPS, "
                     "Zaharia et al. 2014): shown, not counted", used=False))
    yrs = "+".join(AIS_SETTINGS["years"])
    url = "https://ows.emodnet-humanactivities.eu/wcs?service=WCS&request=DescribeCoverage&version=2.0.1&coverageId="
    for kind, sector, activity, nm, q in [
            ("all", "ports", "shipping_lane", "Shipping lanes and anchorage traffic (AIS, all ships except dredgers)", "top decile"),
            ("fishing", "fishing", "fishing_ground", "Fishing grounds (AIS fishing-vessel density)", "top decile"),
            ("dredging", "shipyards", "dredging_activity", "Dredging and underwater operations (AIS)", "top 5%")]:
        g, thr = _ais_footprint(kind)
        cov = f"emodnet__vesseldensity_{AIS_TYPES[kind]}"
        rows.append(_row(sector, activity, nm, g,
                         f"{EMOD_HA}, EMSA AIS vessel density {cov}, mean {yrs}, {q} of cells with traffic "
                         f"(>= {thr:.3g} h/km2/month) ({EMOD_LIC})", url + cov, "official",
                         "data-backed footprint, ~1.2 km raster cells; vessels >= 15 m only carry AIS"))
    return rows


def _extra_rows() -> list[dict]:
    """Features added from the location research (EXTRA_FEATURES): same keys as MANUAL_FEATURES plus
    activity, confidence and url."""
    rows = []
    for m in EXTRA_FEATURES:
        g = {"point": lambda c: Point(c[0]), "line": LineString, "polygon": Polygon}[m["geom"]](m["coords"])
        rows.append(_row(m["sector"], m["activity"], m["name"], _to_m(g), m["source"], m.get("url", ""),
                         m["confidence"], m.get("note", ""), used=m.get("used", True)))
    return rows


ACROPO_URL = "https://web.archive.org/web/20211228001834/http://acropo.gov.ro/web/wp-content/uploads/2020/12/Rap-EUOAG-2020.pdf"
ANAR_ZIP = "https://rowater.ro/wp-content/uploads/2024/09/Perimetre-MEDIU-MARIN.zip"
ANAR_2025 = "https://rowater.ro/wp-content/uploads/2025/11/Anunt-licitatii-3-perimetre-mediu-marin-nr.31796_24.11.2025.pdf"
ORD_2025_URL = "https://legislatie.just.ro/Public/DetaliiDocumentAfis/294196"
WIND_URL = "https://mmediu.ro/wp-content/uploads/2026/07/Lista-perimetrelor-eoliene-offshore-care-pot-fi-concesionate.pdf"
EXTRA_FEATURES: list[dict] = [
    # Offshore installations: ACROPO report to the EU on offshore oil and gas installations (2020; 2021 identical)
    *[{"sector": "shipyards", "activity": "offshore_platform", "name": n, "coords": [c], "geom": "point",
       "confidence": "official", "url": ACROPO_URL,
       "source": "ACROPO (Romanian offshore oil and gas authority) annual report to the EU, installation list 2020"}
      for n, c in [("Central Platform Complex PFCP + PFS-1 + PFS-2 (manned)", (29.566914, 44.523858)),
                   ("PFSS-8", (29.358944, 44.599917)), ("PFSS-U / Pescarus", (29.645361, 44.481083)),
                   ("PGSU-3", (29.548750, 44.527389)), ("PGSU-4", (29.547250, 44.534153)),
                   ("PGSU-6", (29.468222, 44.532472)), ("PGSU-7", (29.446833, 44.545167))]],
    # Submarine cable KAFOS (schematic route, city-level landing): TeleGeography
    {"sector": "shipyards", "activity": "pipeline_cable", "name": "KAFOS submarine cable (landing Mangalia)",
     "coords": [(28.80005, 43.42838), (28.80005, 43.67299), (28.582768, 43.817203)], "geom": "line",
     "confidence": "assumed", "url": "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json",
     "source": "TeleGeography Submarine Cable Map (CC BY-NC-SA): schematic route, city-level landing point",
     "note": "not a surveyed route"},
    # Aquaculture: ANAR / ABA Dobrogea-Litoral marine perimeters (plans in ETRS89-LAEA, converted), 2024 awards
    *[{"sector": "aquaculture", "activity": "aquaculture_lease", "name": f"Aquaculture perimeter {k} ({who})",
       "coords": c, "geom": "polygon", "confidence": "official", "url": ANAR_ZIP,
       "source": "ANAR / ABA Dobrogea-Litoral marine aquaculture perimeters (plan de situatie), awarded 2024 "
                 "(20-year lease); award notices rowater.ro 2024/10 and 2024/12",
       "note": f"{area} m2; {kind}"}
      for k, who, area, kind, c in [
          ("P3", "Serviciile Comerciale Romane SA", 74902, "fish perimeter", [(28.662613, 43.760872), (28.663659, 43.760042), (28.658162, 43.756402), (28.657116, 43.757232)]),
          ("P5", "Pastravul din Tara Ta", 27476, "fish perimeter", [(28.657082, 43.778564), (28.658596, 43.778498), (28.658534, 43.776456), (28.657048, 43.776514)]),
          ("P6", "Pastravul din Tara Ta", 27366, "fish perimeter", [(28.656762, 43.772342), (28.658226, 43.772339), (28.658257, 43.770259), (28.656754, 43.770297)]),
          ("P7", "Pastravul din Tara Ta", 28602, "fish perimeter", [(28.668368, 43.775684), (28.668209, 43.773537), (28.669698, 43.773512), (28.669870, 43.775631)]),
          ("P8", "Pastravul din Tara Ta", 26212, "fish perimeter", [(28.667767, 43.767423), (28.667865, 43.769350), (28.669359, 43.769237), (28.669245, 43.767242)]),
          ("P9", "Maty Fish SRL", 74918, "shellfish perimeter", [(28.659843, 44.081545), (28.663586, 44.081545), (28.663586, 44.079297), (28.659843, 44.079296)]),
          ("P11", "Deltaica Seafood SRL", 41833, "shellfish perimeter", [(29.204694, 44.646677), (29.205805, 44.645011), (29.208027, 44.645844), (29.207194, 44.647511)]),
          ("P12", "Bistromar La Timona SRL", 80157, "fish perimeter", [(28.652947, 43.837100), (28.652789, 43.832547), (28.650578, 43.832842), (28.650867, 43.836664)]),
          ("P13", "Bistromar La Timona SRL", 20047, "shellfish perimeter", [(28.646410, 43.836258), (28.646210, 43.833400), (28.647057, 43.833372), (28.647127, 43.836244)]),
          ("P28", "Nedsea SRL", 24139, "fish perimeter", [(28.648811, 44.215311), (28.650069, 44.216131), (28.651711, 44.215100), (28.650569, 44.214219)])]],
    # offered, not awarded (2024) and the November 2025 mollusc tender: shown, not counted
    *[{"sector": "aquaculture", "activity": "aquaculture_planned", "name": f"Aquaculture perimeter {k} (offered, not awarded)",
       "coords": c, "geom": "polygon", "confidence": "official", "url": u, "used": False,
       "source": src}
      for k, u, src, c in [(k, ANAR_ZIP, "ANAR / ABA Dobrogea-Litoral marine perimeters, 2024 tender, not awarded", c)
                           for k, c in [
          ("P1", [(28.660353, 43.762665), (28.654856, 43.759025), (28.655902, 43.758195), (28.661399, 43.761835)]),
          ("P2", [(28.655986, 43.758128), (28.661483, 43.761768), (28.662529, 43.760938), (28.657032, 43.757298)]),
          ("P4", [(28.663743, 43.759975), (28.664789, 43.759145), (28.659292, 43.755505), (28.658246, 43.756335)]),
          ("P10", [(28.759263, 44.249513), (28.761686, 44.248848), (28.761152, 44.247547), (28.758914, 44.248090)]),
          ("P14", [(28.687175, 44.077756), (28.691131, 44.077756), (28.691131, 44.075100), (28.687187, 44.075098)]),
          ("P15", [(28.619203, 43.898342), (28.619502, 43.895615), (28.624581, 43.895236), (28.624898, 43.898296)]),
          ("P16", [(28.666936, 44.065792), (28.666833, 44.062722), (28.670594, 44.062753), (28.670728, 44.065858)]),
          ("P17", [(28.673183, 44.065811), (28.676917, 44.065844), (28.676361, 44.063053), (28.672639, 44.062983)]),
          ("P18", [(28.681111, 44.080103), (28.684797, 44.080567), (28.684711, 44.077803), (28.681103, 44.077369)]),
          ("P19", [(28.680833, 44.080564), (28.684356, 44.080953), (28.684494, 44.083578), (28.680900, 44.083194)]),
          ("P20", [(28.683154, 44.067458), (28.680675, 44.067722), (28.681146, 44.069938), (28.683625, 44.069673)]),
          ("P21", [(28.672750, 44.061253), (28.672790, 44.059456), (28.669665, 44.059409), (28.669626, 44.061206)]),
          ("P22", [(28.727568, 44.253089), (28.727605, 44.251292), (28.724471, 44.251247), (28.724434, 44.253043)]),
          ("P23", [(28.734960, 44.253051), (28.734997, 44.251255), (28.731862, 44.251210), (28.731825, 44.253006)]),
          ("P24", [(28.724355, 44.308359), (28.726469, 44.308450), (28.726309, 44.310023), (28.724088, 44.309951)]),
          ("P25", [(28.623578, 43.835592), (28.626069, 43.835594), (28.625808, 43.833359), (28.623318, 43.833357)]),
          ("P26", [(28.668844, 43.798222), (28.666375, 43.798486), (28.666841, 43.800702), (28.669310, 43.800438)]),
          ("P27", [(28.666170, 43.780675), (28.663702, 43.780938), (28.664168, 43.783155), (28.666636, 43.782890)])]]
         + [(k, ANAR_2025, "ANAR mollusc tender November 2025 (Stereo 70 converted; no award found)", c) for k, c in [
          ("2025-P1", [(28.659517, 44.318050), (28.659317, 44.315350), (28.663067, 44.315200), (28.663283, 44.317900)]),
          ("2025-P2", [(28.693821, 44.292582), (28.693821, 44.289300), (28.699634, 44.289306), (28.699625, 44.292582)]),
          ("2025-P3", [(28.671454, 44.086613), (28.673917, 44.086533), (28.673817, 44.084367), (28.671393, 44.084420)])]]],
    # Fishing management areas (Ordin 23/297/2025 art. 4): context, not counted
    {"sector": "management", "activity": "fishing_restriction", "used": False, "confidence": "official",
     "name": "Delta marine zone Zatonul Mare - Periteasca: gillnets banned 9 Apr - 30 Nov (shore to 20 m isobath)",
     "coords": [(29.191419, 44.637131), (29.341803, 44.676525), (29.324400, 44.806064), (29.138911, 44.770069)],
     "geom": "polygon", "url": ORD_2025_URL, "source": "Ordin MADR/MMAP 23/297/2025 art. 4 lit. r"},
    {"sector": "management", "activity": "fishing_restriction", "used": False, "confidence": "official",
     "name": "Sahalin - Sfantu Gheorghe: all marine fishing banned all year (40-50 m isobaths)",
     "coords": [(29.647217, 44.759941), (29.791786, 44.664550), (29.981874, 44.812501), (29.851484, 44.903719)],
     "geom": "polygon", "url": ORD_2025_URL, "source": "Ordin MADR/MMAP 23/297/2025 art. 4 lit. s"},
    # Planned offshore wind perimeters (Law 121/2024 list, July 2026): context, not counted
    *[{"sector": "shipyards", "activity": "offshore_wind_planned", "name": f"Offshore wind perimeter {k} (planned)",
       "coords": c, "geom": "polygon", "confidence": "official", "used": False, "url": WIND_URL,
       "source": "Ministry of Environment, list of offshore wind perimeters that may be concessioned (Law 121/2024), "
                 "annex 2, July 2026", "note": "planned; approval status unclear in the press"}
      for k, c in [
          ("Z1 (phase 1)", [(29.910157, 44.419311), (30.092944, 44.542232), (30.244160, 44.532437), (30.179365, 44.404069), (30.173694, 44.391825), (30.152487, 44.369916), (30.121911, 44.325927), (30.112636, 44.297003), (30.105900, 44.292187), (30.101215, 44.275448), (30.095391, 44.267682), (29.974019, 44.268863), (29.973545, 44.208411), (29.895201, 44.221157), (29.836560, 44.225668)]),
          ("Z2 (phase 1)", [(29.649452, 44.262328), (29.637095, 44.055378), (29.528601, 44.048206), (29.528910, 44.140182)]),
          ("Z3 (phase 1)", [(29.779016, 44.015221), (29.876851, 44.003127), (29.915406, 43.986719), (29.906765, 43.955541), (29.917234, 43.935420), (29.913473, 43.897258), (29.853557, 43.899920), (29.853998, 43.861374), (29.812463, 43.862608), (29.789310, 43.863661), (29.772031, 43.866816), (29.754828, 43.874128)]),
          ("Z4 (phase 2)", [(29.347766, 44.284552), (29.314073, 44.326125), (29.430494, 44.447933), (29.530137, 44.448411), (29.573435, 44.415324), (29.568255, 44.394546)]),
          ("Z5 (phase 2)", [(29.334562, 43.932638), (29.598610, 43.940622), (29.571644, 43.761365), (29.164867, 43.762190), (29.242068, 43.836817)]),
          ("Z6 (phase 3)", [(30.372958, 44.178007), (30.629090, 44.771935), (30.713886, 44.804606), (31.034999, 44.705646), (30.816664, 44.248737), (30.695485, 44.158720)])]],
]


@lru_cache(maxsize=1)
def _all_features_m_base() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(_osm_rows() + _emodnet_rows() + _manual_rows() + _extra_rows() + _derived_rows(), crs=CRS_M)


@lru_cache(maxsize=1)
def _all_features_m() -> gpd.GeoDataFrame:
    anch_rows, _ = detect_anchorages()
    gdf = pd.concat([_all_features_m_base(), gpd.GeoDataFrame(anch_rows, crs=CRS_M)], ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=CRS_M)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    # keep Romanian features whose buffer (plus 1 km) reaches the Romanian sea: drops river ports, inland
    # pipelines, Bulgarian and Ukrainian beaches
    dom, rs = ro_domain(), ro_sea()
    shapely.prepare(dom)
    shapely.prepare(rs)
    keep = []
    for _, r in gdf.iterrows():
        b = DEFAULT_BUFFERS.get(r.sector, {}).get(r.activity, {}).get("buffer_m", 0)
        ok = dom.intersects(r.geometry) and rs.intersects(r.geometry.buffer(b + 1000))
        keep.append(bool(ok) or r.sector == "management")
    gdf = gdf[keep].reset_index(drop=True)
    gdf.insert(0, "feature_id", [f"{s}:{a}:{i}" for i, (s, a) in enumerate(zip(gdf.sector, gdf.activity))])
    gdf["style_key"] = gdf.sector + "|" + gdf.confidence
    return gdf


def load_features(sector: str | None = None) -> gpd.GeoDataFrame:
    """Features where each sector operates, EPSG:4326. Columns: feature_id, sector, activity, name, source,
    source_url, confidence (official|mapped|assumed), season (all|summer), note, used_in_zones, style_key.
    sector: one of SECTORS, 'management' (no-fishing reserve, context only), or None for all."""
    gdf = _all_features_m()
    if sector is not None:
        if sector not in SECTORS + ("management",):
            raise ValueError(f"unknown sector {sector!r}; expected one of {SECTORS + ('management',)}")
        gdf = gdf[gdf.sector == sector]
    return gdf.to_crs(CRS_LL)


# Anchorages from ship traffic: cells where cargo + tanker ships spend many hours per passage (they wait, not transit)
ANCHORAGE_DETECT = {
    "years": ["2023", "2024"],
    "vessel_density": ["vesseldensity_09avg", "vesseldensity_10avg"],  # cargo, tanker: hours/km2/month (annual avg)
    "route_density": ["routedensity_01avg", "routedensity_04avg"],     # cargo, tanker: passages per year
    "min_routes": 20,          # passages per year in the cell (enough traffic to judge)
    "quantile": 0.95,          # seeds: top 5% of hours-per-passage among candidate cells with enough traffic
    "quantile_grow": 0.90,     # hysteresis: seeds grow into connected cells in the top 10%
    "port_reach_m": 25000,     # candidate cells within 25 km of a port area ...
    "port_exclude_m": 1000,    # ... but at least 1 km outside it (berths and shipyard quays)
    "closing": 3,              # 3x3 binary closing (fills one-cell gaps)
    "min_cells": 2,            # minimum area: 2 cells (~3 km2)
}
# Ports used to name the detected areas (EMODnet port points; Sulina = OSM Bazinul Mare) and published references
# used to confirm them (Admiralty Black Sea Pilot NP24, 2003; Constanta Port Handbook polygon via JICA)
ANCHORAGE_PORTS = {"Constanta": (28.65708, 44.13813), "Midia": (28.67828, 44.34473),
                   "Mangalia": (28.59131, 43.80627), "Sulina": (29.6785, 45.1561)}
NP24 = ("Admiralty Black and Azov Seas Pilot NP24 (UKHO 2003), https://ivms.mil.gov.ua/wp-content/uploads/2020/10/"
        "Black_and_Azov_seas_PilotNP-24_2003.pdf")
ANCHORAGE_REFS = {  # port -> published description used to confirm a detected area
    "Mangalia": {"offset_nm": (3.5, 45), "depth": (23, 29), "ref": "NP24: 3.5 nm NE of the harbour entrance, 23-29 m"},
    "Midia": {"depth": (16, 22), "ref": "NP24: 4 nm E of Capul Midia light, 16-22 m"},
    "Sulina": {"depth": (7, 22), "max_km": 15, "ref": "NP24: anchorage in Rada Sulina, 7-22 m"},
    "Constanta": {"polygon": "Constanta roadstead anchorage (zones 1-3)",
                  "ref": "Port Handbook 2000-2001 roadstead zones 1-3 (via JICA) and NP24: 3-8 nm ESE of Capul Constanta"},
}

# --------------------------------------------------------------------------------------------- buffers / zones
def load_buffers(path: Path | None = None) -> dict:
    """Buffer table from data/zones/buffers.yaml (or path) if it exists, else DEFAULT_BUFFERS."""
    import yaml

    p = Path(path) if path else BUFFERS_PATH
    if p.exists():
        return yaml.safe_load(p.read_text())["buffers"]
    return copy.deepcopy(DEFAULT_BUFFERS)


def save_buffers(buffers: dict, path: Path | None = None) -> Path:
    import yaml

    p = Path(path) if path else BUFFERS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"bathing_season": {"start": "06-01", "end": "09-15", "basis_ref": BATHING_SEASON["basis_ref"]},
           "fishing_closures_optional": FISHING_CLOSURES, "buffers": buffers}
    p.write_text("# Buffer table for marinekit.pressure_zones: one buffer per activity, seaward (clipped to the\n"
                 "# Romanian sea). buffer_basis: law | literature | rule. Edit and rebuild.\n"
                 + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return p


def build_zones(buffers: dict | None = None) -> gpd.GeoDataFrame:
    """One buffer polygon per sector x activity x confidence, clipped to the Romanian sea, EPSG:4326.
    Properties: sector, activity, buffer_m, buffer_basis, basis_ref, season, confidence, n_features, area_km2,
    style_key (sector|confidence, for the QML)."""
    buffers = buffers or load_buffers()
    feats = _all_features_m()
    feats = feats[feats.used_in_zones]
    rs = ro_sea()
    rows = []
    for (sector, activity, conf), sub in feats.groupby(["sector", "activity", "confidence"]):
        spec = buffers.get(sector, {}).get(activity)
        if spec is None:
            raise KeyError(f"no buffer for {sector}/{activity}: add it to buffers.yaml")
        d = float(spec["buffer_m"])
        geoms = sub.geometry.values
        g = unary_union([x.buffer(d, quad_segs=8) if d > 0 else
                         (x if x.geom_type in ("Polygon", "MultiPolygon") else x.buffer(1.0)) for x in geoms])
        g = shapely.make_valid(shapely.set_precision(shapely.make_valid(g).intersection(rs), 1.0))
        if g.is_empty:
            continue
        rows.append({"sector": sector, "activity": activity, "buffer_m": d, "buffer_basis": spec["buffer_basis"],
                     "basis_ref": spec["basis_ref"], "season": spec.get("season", "all"), "confidence": conf,
                     "n_features": len(sub), "area_km2": round(g.area / 1e6, 3),
                     "style_key": f"{sector}|{conf}", "geometry": g})
    return gpd.GeoDataFrame(rows, crs=CRS_M).to_crs(CRS_LL)


# --------------------------------------------------------------------------------------------- overlap
def overlap_grid(zones: gpd.GeoDataFrame | None = None, cell_m: float = 250) -> gpd.GeoDataFrame:
    """Square grid (cell_m, EPSG:32635) over the Romanian sea; a sector is present in a cell when any of its zones
    touches the cell. Summer = all zones; winter = zones with season 'all' (tourism off).
    Returns cells with n_summer >= 1, EPSG:4326: cell_id, n_summer, n_winter, sectors_summer, sectors_winter,
    lon, lat."""
    z = (zones if zones is not None else build_zones()).to_crs(CRS_M)
    rs = ro_sea()
    x0, y0, x1, y1 = z.total_bounds
    x0, y0 = np.floor(x0 / cell_m) * cell_m, np.floor(y0 / cell_m) * cell_m
    gx, gy = np.meshgrid(np.arange(x0, x1, cell_m), np.arange(y0, y1, cell_m))
    cells = shapely.box(gx.ravel(), gy.ravel(), gx.ravel() + cell_m, gy.ravel() + cell_m)
    shapely.prepare(rs)
    cells = cells[shapely.intersects(rs, cells)]
    tree = shapely.STRtree(cells)
    summer = np.zeros((len(cells), len(SECTORS)), dtype=bool)
    winter = np.zeros_like(summer)
    for sector, season, geom in zip(z.sector, z.season, z.geometry):
        idx = tree.query(geom, predicate="intersects")
        j = SECTORS.index(sector)
        summer[idx, j] = True
        if season == "all":
            winter[idx, j] = True
    keep = summer.any(axis=1)
    cells, summer, winter = cells[keep], summer[keep], winter[keep]
    cent = shapely.centroid(cells)
    lon, lat = Transformer.from_crs(CRS_M, CRS_LL, always_xy=True).transform(shapely.get_x(cent), shapely.get_y(cent))
    df = pd.DataFrame({
        "cell_id": np.arange(len(cells)),
        "n_summer": summer.sum(axis=1), "n_winter": winter.sum(axis=1),
        "sectors_summer": [",".join(s for s, p in zip(SECTORS, r) if p) for r in summer],
        "sectors_winter": [",".join(s for s, p in zip(SECTORS, r) if p) for r in winter],
        "lon": np.round(lon, 5), "lat": np.round(lat, 5)})
    g = gpd.GeoDataFrame(df, geometry=cells, crs=CRS_M)
    g.attrs["cell_m"] = cell_m
    return g.to_crs(CRS_LL)


def overlap_polygons(grid: gpd.GeoDataFrame, season: str) -> gpd.GeoDataFrame:
    """Dissolve grid cells into one (multi)polygon per overlap count 1-5 for 'summer' or 'winter', EPSG:4326.
    Properties: count, season, n_cells, area_km2."""
    col = f"n_{season}"
    g = grid.to_crs(CRS_M)
    rows = []
    for k in range(1, len(SECTORS) + 1):
        sub = g[g[col] == k]
        if sub.empty:
            continue
        geom = shapely.coverage_union_all(shapely.set_precision(sub.geometry.values, 0.5))
        rows.append({"count": k, "season": season, "n_cells": len(sub), "area_km2": round(geom.area / 1e6, 2),
                     "geometry": geom})
    return gpd.GeoDataFrame(rows, crs=CRS_M).to_crs(CRS_LL)


SETTLEMENT_KINDS = ("city", "town", "village", "hamlet", "locality")


def top_overlap_areas(grid: gpd.GeoDataFrame, season: str, min_count: int = 3) -> gpd.GeoDataFrame:
    """Connected areas of cells with overlap >= min_count, split by nearest coastal settlement, ranked by peak count
    then area. Properties: rank, name, season, max_count, area_km2, area_at_max_km2, sectors_at_max, near."""
    col = f"n_{season}"
    g = grid.to_crs(CRS_M)
    g = g[g[col] >= min_count].copy()
    if g.empty:
        return gpd.GeoDataFrame(columns=["rank", "geometry"], geometry="geometry", crs=CRS_LL)
    merged = shapely.coverage_union_all(shapely.set_precision(g.geometry.values, 0.5)).buffer(1)
    comps = list(getattr(merged, "geoms", [merged]))
    ctree = shapely.STRtree(comps)
    cent = g.geometry.centroid.values
    g["comp"] = [int(ctree.query(c, predicate="intersects")[0]) for c in cent]
    pl = places()
    st = pl[pl.kind.isin(SETTLEMENT_KINDS)].reset_index(drop=True)
    g["settlement"] = st.name.values[shapely.STRtree(st.geometry.values).nearest(cent)]
    cell_km2 = (grid.attrs.get("cell_m", 250) / 1000) ** 2
    rows = []
    for (_, sett), sub in g.groupby(["comp", "settlement"]):
        poly = shapely.coverage_union_all(shapely.set_precision(sub.geometry.values, 0.5))
        mx = int(sub[col].max())
        top = sub[sub[col] == mx]
        d = poly.distance(st[st.name == sett].geometry.iloc[0]) / 1000
        rows.append({"name": f"{sett} {'coast' if d < 5 else 'offshore'}", "season": season, "max_count": mx,
                     "area_km2": round(len(sub) * cell_km2, 2), "area_at_max_km2": round(len(top) * cell_km2, 2),
                     "sectors_at_max": top[f"sectors_{season}"].mode().iloc[0], "near": f"{sett} ({d:.1f} km)",
                     "geometry": poly})
    out = gpd.GeoDataFrame(rows, crs=CRS_M).sort_values(["max_count", "area_at_max_km2", "area_km2"],
                                                         ascending=False).reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    return out.to_crs(CRS_LL)


@lru_cache(maxsize=1)
def _grid_file() -> gpd.GeoDataFrame:
    return gpd.read_file(OUT_DIR / "overlap_grid.geojson")


def overlap_at(lat: float, lon: float, date=None) -> dict:
    """Overlap count and sectors at a point from data/zones/overlap_grid.geojson, for the season of `date`
    (today if None). Returns {season, n, sectors, cell_id} (n = 0 outside every zone)."""
    season = season_for_date(date or pd.Timestamp.today())
    g = _grid_file()
    hit = g[g.contains(Point(lon, lat))]
    if hit.empty:
        return {"season": season, "n": 0, "sectors": "", "cell_id": None}
    r = hit.iloc[0]
    return {"season": season, "n": int(r[f"n_{season}"]), "sectors": r[f"sectors_{season}"] or "",
            "cell_id": int(r["cell_id"])}


# --------------------------------------------------------------------------------------------- QGIS styles
# overlap count 1..5: light-to-dark warm sequential ramp (more sectors = stronger); lightness falls monotonically,
# so the order survives colour-vision deficiencies. Shared with the web viewer via data/zones/overlap_style.json.
OVERLAP_RAMP = [  # (count, colour, opacity)
    (1, "#FDE0B2", 0.45), (2, "#F4A259", 0.70), (3, "#D55E00", 0.85), (4, "#8C2D04", 0.90), (5, "#4A1402", 0.95)]
CIVIDIS5 = [c for _, c, _ in OVERLAP_RAMP]  # kept name for older callers


def overlap_style() -> dict:
    """Colours, opacities and labels of the overlap count, as written to data/zones/overlap_style.json."""
    return {"field_summer": "n_summer", "field_winter": "n_winter", "dissolved_field": "count",
            "outline": None,
            "levels": [{"count": k, "color": c, "opacity": a, "label": f"{k} sector{'s' if k > 1 else ''}"}
                       for k, c, a in OVERLAP_RAMP]}


def _rgba(hexcol: str, alpha: float = 1.0) -> str:
    h = hexcol.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{int(round(alpha * 255))}"


def _fill_symbol(name, color, alpha=1.0, outline="0,0,0,0", outline_w=0.0, style="solid", outline_style=None):
    col = _rgba(color, alpha) if color.startswith("#") else color
    os_ = outline_style or ("no" if outline_w == 0 else "solid")
    return (f'<symbol type="fill" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            '<layer class="SimpleFill" enabled="1" locked="0" pass="0"><Option type="Map">'
            f'<Option type="QString" name="color" value="{col}"/>'
            f'<Option type="QString" name="outline_color" value="{outline}"/>'
            f'<Option type="QString" name="outline_style" value="{os_}"/>'
            f'<Option type="QString" name="outline_width" value="{outline_w}"/>'
            '<Option type="QString" name="outline_width_unit" value="MM"/>'
            f'<Option type="QString" name="style" value="{style}"/>'
            '</Option></layer></symbol>')


def _line_symbol(name, color, dashed=False):
    return (f'<symbol type="line" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            '<layer class="SimpleLine" enabled="1" locked="0" pass="0"><Option type="Map">'
            f'<Option type="QString" name="line_color" value="{_rgba(color)}"/>'
            f'<Option type="QString" name="line_style" value="{"dash" if dashed else "solid"}"/>'
            '<Option type="QString" name="line_width" value="0.5"/>'
            '<Option type="QString" name="line_width_unit" value="MM"/></Option></layer></symbol>')


def _marker_symbol(name, color, hollow=False):
    return (f'<symbol type="marker" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            '<layer class="SimpleMarker" enabled="1" locked="0" pass="0"><Option type="Map">'
            f'<Option type="QString" name="color" value="{_rgba(color, 0.0 if hollow else 1.0)}"/>'
            '<Option type="QString" name="name" value="circle"/><Option type="QString" name="size" value="2.2"/>'
            '<Option type="QString" name="size_unit" value="MM"/>'
            f'<Option type="QString" name="outline_color" value="{_rgba(color) if hollow else "0,0,0,255"}"/>'
            f'<Option type="QString" name="outline_style" value="{"dash" if hollow else "solid"}"/>'
            f'<Option type="QString" name="outline_width" value="{0.5 if hollow else 0.2}"/></Option></layer></symbol>')


def _qml(renderer: str) -> str:
    return ('<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'>\n'
            '<qgis version="3.44.0" styleCategories="Symbology">\n' + renderer + '\n<blendMode>0</blendMode>'
            '<featureBlendMode>0</featureBlendMode><layerOpacity>1</layerOpacity>\n</qgis>\n')


def _categorized(attr: str, cats: list, value_type: str = "string") -> str:
    c = "".join(f'<category value="{v}" symbol="{i}" label="{lab}" render="true" type="{value_type}"/>'
                for i, (v, lab, _) in enumerate(cats))
    sy = "".join(sym for _, _, sym in cats)
    return (f'<renderer-v2 type="categorizedSymbol" attr="{attr}" symbollevels="0" forceraster="0" '
            f'enableorderby="0" referencescale="-1"><categories>{c}</categories><symbols>{sy}</symbols>'
            '</renderer-v2>')


def write_qml_styles(out_dir: Path = OUT_DIR) -> dict:
    """QGIS 3.x styles next to the outputs. Sectors in Okabe-Ito; official/mapped solid, assumed hatched (areas),
    dashed (lines) or hollow-dashed (points); overlap count 1-5 as a light-to-dark warm ramp (OVERLAP_RAMP)."""
    out = {}
    secs = list(SECTORS) + ["management"]
    col = dict(SECTOR_COLORS, management="#555555")
    lab = dict(SECTOR_LABELS, management="No-fishing reserve (context)")

    def area_sym(i, c, conf):
        if conf == "assumed":
            return _fill_symbol(i, c, 1.0, outline=_rgba(c), outline_w=0.4, style="b_diagonal", outline_style="dash")
        return _fill_symbol(i, c, 0.35 if conf == "official" else 0.25, outline=_rgba(c), outline_w=0.2)

    def cats_for(mk):
        return [(f"{s}|{cf}", f"{lab[s]}, {cf}", mk(len(secs) * 0 + i * 3 + j, col[s], cf))
                for i, s in enumerate(secs) for j, cf in enumerate(CONFIDENCE)]

    def renum(cats):  # symbol names must be 0..n-1 in category order
        fixed = []
        for k, (v, lb, sym) in enumerate(cats):
            fixed.append((v, lb, re.sub(r'name="\d+"', f'name="{k}"', sym, count=1)))
        return fixed

    for fname, mk in [("sector_zones", area_sym), ("sector_features", area_sym),
                      ("sector_features_line", lambda i, c, cf: _line_symbol(i, c, dashed=cf == "assumed")),
                      ("sector_features_point", lambda i, c, cf: _marker_symbol(i, c, hollow=cf == "assumed"))]:
        p = out_dir / f"{fname}.qml"
        p.write_text(_qml(_categorized("style_key", renum(cats_for(mk)))))
        out[fname] = p
    counts = [(str(k), f"{k} sector{'s' if k > 1 else ''}", _fill_symbol(k - 1, c, a))
              for k, c, a in OVERLAP_RAMP]
    for fname, attr in [("overlap_grid", "n_summer"), ("overlap_grid_winter", "n_winter"),
                        ("overlap_summer", "count"), ("overlap_winter", "count")]:
        p = out_dir / f"{fname}.qml"
        p.write_text(_qml(_categorized(attr, counts, value_type="integer")))
        out[fname] = p
    return out


# --------------------------------------------------------------------------------------------- map
def render_map(path: Path = ROOT / "docs" / "pressure_zones_map.png", grid: gpd.GeoDataFrame | None = None,
               features: gpd.GeoDataFrame | None = None) -> Path:
    """Check map: a) summer overlap count, b) winter overlap count, c) summer, Constanta to Vama Veche, with the
    features (assumed ones hollow/dashed)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                         "font.size": 7, "axes.labelsize": 7, "xtick.labelsize": 6, "ytick.labelsize": 6,
                         "legend.fontsize": 6, "axes.spines.top": False, "axes.spines.right": False,
                         "xtick.direction": "out", "ytick.direction": "out", "axes.linewidth": 0.6})
    grid = grid if grid is not None else overlap_grid()
    feats = (features if features is not None else load_features()).to_crs(CRS_LL)
    sea = gpd.GeoSeries([sea_polygon()], crs=CRS_M).to_crs(CRS_LL)
    rsea = gpd.GeoSeries([ro_sea()], crs=CRS_M).to_crs(CRS_LL)
    polys = {s: overlap_polygons(grid, s) for s in ("summer", "winter")}
    fig, axs = plt.subplots(1, 3, figsize=(183 / 25.4, 105 / 25.4), gridspec_kw={"width_ratios": [1, 1, 0.62]})
    ext_full, ext_zoom = (28.45, 30.6, 43.65, 45.35), (28.50, 28.85, 43.72, 44.25)
    for ax, season, ext in [(axs[0], "summer", ext_full), (axs[1], "winter", ext_full), (axs[2], "summer", ext_zoom)]:
        ax.set_facecolor("#E3E3E3")
        sea.plot(ax=ax, color="white", linewidth=0)
        rsea.boundary.plot(ax=ax, color="#999999", linewidth=0.4, linestyle=(0, (3, 2)))
        for _, r in polys[season].iterrows():
            _, c, a = OVERLAP_RAMP[int(r["count"]) - 1]
            gpd.GeoSeries([r.geometry], crs=CRS_LL).plot(ax=ax, color=c, alpha=a, linewidth=0)
        if ax is axs[2]:
            f = feats[feats.used_in_zones & (feats.sector != "management")]
            pts = f[f.geom_type == "Point"]
            for conf, hollow in (("official", False), ("mapped", False), ("assumed", True)):
                sub = pts[pts.confidence == conf]
                if len(sub):
                    sub.plot(ax=ax, markersize=8, facecolor="none" if hollow else "black",
                             edgecolor="black", linewidth=0.5, zorder=5)
        x0, x1, y0, y1 = ext
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)" if ax is not axs[1] else "")
    for ax, lab in zip(axs, "abc"):
        ax.text(-0.1, 1.02, lab, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")
    axs[0].add_patch(plt.Rectangle((ext_zoom[0], ext_zoom[2]), ext_zoom[1] - ext_zoom[0], ext_zoom[3] - ext_zoom[2],
                                   fill=False, edgecolor="#555555", linewidth=0.6))
    for ax, km in zip(axs, (20, 20, 5)):
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        lat = y0 + 0.05 * (y1 - y0)
        dlon = km / (111.32 * np.cos(np.radians(lat)))
        xs = x1 - 0.06 * (x1 - x0) - dlon
        ax.plot([xs, xs + dlon], [lat, lat], color="black", linewidth=1.2)
        ax.text(xs + dlon / 2, lat + 0.012 * (y1 - y0), f"{km} km", ha="center", va="bottom", fontsize=6)
    handles = [Patch(facecolor=c, alpha=a, label=f"{k} sector{'s' if k > 1 else ''}") for k, c, a in OVERLAP_RAMP]
    handles += [Line2D([], [], marker="o", linestyle="", markerfacecolor="black", markeredgecolor="black",
                       markersize=3, label="Point feature, official or mapped"),
                Line2D([], [], marker="o", linestyle="", markerfacecolor="none", markeredgecolor="black",
                       markersize=3, label="Point feature, assumed"),
                Line2D([], [], color="#999999", linewidth=0.4, linestyle=(0, (3, 2)), label="Romanian EEZ")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.01),
               handlelength=1.4, columnspacing=1.2)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------------------------- export
def _write(gdf: gpd.GeoDataFrame, path: Path, precision: int = 6):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    g = gdf.to_crs(CRS_LL).copy()
    for c in g.columns:
        if c != "geometry" and g[c].dtype == object:
            g[c] = g[c].astype(str)
    g.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=precision)
    return path


def summary() -> dict:
    """Feature counts per sector x confidence."""
    f = _all_features_m()
    return {s: f[f.sector == s].groupby("confidence").size().to_dict() for s in SECTORS + ("management",)}


def export_all(cell_m: float = 250, out_dir: Path = OUT_DIR, render: bool = True,
               buffers: dict | None = None) -> dict:
    """Rebuild every file of the Z -> U interface in data/zones/ (EPSG:4326). Returns {name: path}."""
    out = {}
    if buffers is None:
        buffers = load_buffers()
    out["buffers"] = save_buffers(buffers, out_dir / "buffers.yaml")
    feats = load_features()
    out["sector_features"] = _write(feats.drop(columns=["used_in_zones"]).assign(
        counted=feats.used_in_zones.map({True: "yes", False: "no"})), out_dir / "sector_features.geojson")
    zones = build_zones(buffers)
    out["sector_zones"] = _write(zones, out_dir / "sector_zones.geojson")
    grid = overlap_grid(zones, cell_m)
    out["overlap_grid"] = _write(grid, out_dir / "overlap_grid.geojson", precision=4)
    for s in ("summer", "winter"):
        out[f"overlap_{s}"] = _write(overlap_polygons(grid, s), out_dir / f"overlap_{s}.geojson", precision=5)
    tops = pd.concat([top_overlap_areas(grid, s).drop(columns="geometry") for s in ("summer", "winter")])
    out["top_overlap_areas"] = out_dir / "top_overlap_areas.csv"
    tops.to_csv(out["top_overlap_areas"], index=False)
    out.update({f"qml_{k}": v for k, v in write_qml_styles(out_dir).items()})
    out["anchorages_detected"] = out_dir / "anchorages_detected.json"
    out["anchorages_detected"].write_text(json.dumps({"settings": ANCHORAGE_DETECT, **detect_anchorages()[1]}, indent=1))
    out["overlap_style"] = out_dir / "overlap_style.json"
    out["overlap_style"].write_text(json.dumps(overlap_style(), indent=1))
    if render:
        out["map"] = render_map(grid=grid, features=feats)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Rebuild data/zones/* (pressure zones v2) and docs/pressure_zones_map.png")
    ap.add_argument("--cell", type=float, default=250, help="grid cell size in metres (default 250)")
    ap.add_argument("--no-map", action="store_true")
    args = ap.parse_args()
    paths = export_all(cell_m=args.cell, render=not args.no_map)
    for k, v in paths.items():
        print(f"{k:24s} {v.relative_to(ROOT)}  {v.stat().st_size / 1e6:.2f} MB")
    print(json.dumps(summary(), indent=1))
    # smoke test at Constanta (port entrance) and off Mangalia, summer and winter
    for nm, (la, lo) in {"Constanta port entrance": (44.150, 28.680), "Mangalia coast": (43.807, 28.600)}.items():
        for d in ("2026-07-15", "2026-01-15"):
            print(f"smoke {nm:24s} {d}: {overlap_at(la, lo, d)}")
