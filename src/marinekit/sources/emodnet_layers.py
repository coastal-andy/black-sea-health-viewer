"""GIS layers (vector WFS + raster WMS) for the Sprint-1 "map of pressures" on the Romanian Black Sea coast.

Sources (all open, no key):
  * EMODnet Human Activities  - ports, port traffic, vessel/route density (EMSA AIS), marinas, bathing waters,
                                fishing effort, wastewater, wind farms, Natura 2000, nationally designated areas ...
  * EMODnet Bathymetry        - DTM WMS + REST depth sampling
  * EMODnet Seabed Habitats   - EUSeaMap broad-scale habitats WMS (service intermittently 503, see docs)
  * EMODnet Geology           - seabed substrate WMS (fallback for habitats)
  * EMODnet Biology (VLIZ)    - EurOBIS occurrence-count grid (WFS)
  * OpenStreetMap (Overpass)  - shipyards and offshore platforms (EMODnet has no shipyard layer, and no Romanian
                                platforms)

Conventions (see marinekit.sources): vector layers come back as a GeoJSON FeatureCollection in EPSG:4326 with the
service's properties untouched, plus a top-level foreign member "meta" (source, layer, count, truncated, ...).
Every network call goes through the on-disk cache in data/cache/emodnet_layers, so the demo works offline once fetched.

Docs + verification log: docs/data_sources/emodnet_layers.md

    from marinekit.sources.emodnet_layers import fetch_wfs, wms_tile_layer, depth_at, sector_layers
    gj = fetch_wfs("natura2000")                       # 24 sites in BBOX_RO
    folium.raster_layers.WmsTileLayer(**wms_tile_layer("vessel_density_fishing")).add_to(m)
    depth_at(44.17, 28.72)                             # ~26.3 m
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone

import requests

from . import BBOX_RO, cache_key, cached_path

SOURCE = "emodnet_layers"
SECTORS = ("ports", "shipyards", "tourism", "fishing", "aquaculture", "context")
TIMEOUT = 120
UA = {"User-Agent": "marinekit-hackathon/0.1 (python-requests)"}

HA_WFS = "https://ows.emodnet-humanactivities.eu/wfs"
HA_WMS = "https://ows.emodnet-humanactivities.eu/wms"
BATHY_WMS = "https://ows.emodnet-bathymetry.eu/wms"
BATHY_WCS = "https://ows.emodnet-bathymetry.eu/wcs"
BATHY_REST = "https://rest.emodnet-bathymetry.eu"
SEABED_WMS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms"
GEOLOGY_WMS = "https://drive.emodnet-geology.eu/geoserver/gtk/wms"
BIOLOGY_WFS = "https://geo.vliz.be/geoserver/Dataportal/wfs"
OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

ATTR_HA = "EMODnet Human Activities (emodnet-humanactivities.eu)"
ATTR_HA_EMSA = "EMODnet Human Activities, vessel density from EMSA AIS (emodnet-humanactivities.eu)"
ATTR_HA_EEA = "EMODnet Human Activities, data from EEA (emodnet-humanactivities.eu)"
ATTR_BATHY = "EMODnet Bathymetry Consortium, EMODnet Digital Bathymetry (DTM)"
ATTR_SEABED = "EMODnet Seabed Habitats, EUSeaMap broad-scale habitat map"
ATTR_GEO = "EMODnet Geology, seabed substrate"
ATTR_BIO = "EMODnet Biology / EurOBIS (VLIZ)"
ATTR_OSM = "© OpenStreetMap contributors (ODbL)"


def _ha(layer, sector, title, description, attribution=ATTR_HA, kind="wfs", group="pressure", **extra):
    """Shorthand for an EMODnet Human Activities layer; every HA WFS layer is also served by the WMS."""
    d = {
        "url": HA_WFS if kind == "wfs" else HA_WMS,
        "wms_url": HA_WMS,
        "layer": layer if kind == "wms" or layer.startswith("emodnet:") else f"emodnet:{layer}",
        "wms_layer": layer.removeprefix("emodnet:"),
        "kind": kind,
        "sector": sector,
        "group": group,
        "title": title,
        "description": description,
        "attribution": attribution,
    }
    d.update(extra)
    return d


# key -> layer spec. Keys: url, layer, kind ('wfs'|'wms'|'overpass'), sector, group ('pressure'|'context'), title,
# description, attribution; optional: wms_url/wms_layer (WMS rendering of a WFS layer), cql (server-side CQL filter;
# bbox is then applied client-side), time (WMS TIME), styles.
# Status of each one is logged in docs/data_sources/emodnet_layers.md.
LAYERS: dict[str, dict] = {
    # ---------------------------------------------------------------- (1) ports & maritime logistics
    "ports": _ha("portlocations", "ports", "Main ports (locations)",
                 "Eurostat/GISCO main ports. RO: Constanta, Midia, Mangalia, Tulcea."),
    "port_goods": _ha("portgoods", "ports", "Main ports: goods traffic (1997-2025)",
                      "One feature per port x year x cargo type x direction; field thousand_of_tonnes.",
                      cql="country='RO' AND year=2024"),
    "port_vessels": _ha("portvessels", "ports", "Main ports: vessel traffic (1997-2025)",
                        "Calls per port x year x vessel type x tonnage class; fields nofvessels, gross_tonnage__gt_thousand.",
                        cql="country='RO' AND year=2024 AND tonnage='TOTAL'"),
    "port_passengers": _ha("portpassengers", "ports", "Main ports: passenger traffic (1997-2025)",
                           "Passengers per port x year x direction (also cruise/tourism relevant).",
                           cql="country='RO' AND year=2024"),
    "port_waste": _ha("wasteatports", "ports", "Waste delivered at ports (MARPOL annexes, m3/t)",
                      "Ship-generated waste received at port reception facilities (Constanta and others)."),
    "vessel_density_all": _ha("vesseldensity_allavg", "ports", "Vessel density, all ships (annual avg)",
                              "EMSA AIS vessel density, hours per km2 per month, 1 km grid; TIME 2017-2024.",
                              ATTR_HA_EMSA, kind="wms", time="2024-01-01T00:00:00Z"),
    "vessel_density_cargo": _ha("vesseldensity_09avg", "ports", "Vessel density, cargo (annual avg)",
                                "EMSA AIS density of cargo ships.", ATTR_HA_EMSA, kind="wms",
                                time="2024-01-01T00:00:00Z"),
    "vessel_density_tanker": _ha("vesseldensity_10avg", "ports", "Vessel density, tankers (annual avg)",
                                 "EMSA AIS density of tankers (oil-spill risk proxy).", ATTR_HA_EMSA, kind="wms",
                                 time="2024-01-01T00:00:00Z"),
    "vessel_density_tug": _ha("vesseldensity_07avg", "ports", "Vessel density, tug & towing (annual avg)",
                              "EMSA AIS density of tugs: port operations footprint.", ATTR_HA_EMSA, kind="wms",
                              time="2024-01-01T00:00:00Z"),
    "route_density_all": _ha("routedensity_allavg", "ports", "Route density, all ships (EMSA, annual)",
                             "Number of routes crossing each cell (shipping lanes); TIME 2019-2025.", ATTR_HA_EMSA,
                             kind="wms", time="2025-01-01T00:00:00Z"),
    # ---------------------------------------------------------------- (2) shipyards & marine engineering
    "vessel_density_dredging": _ha("vesseldensity_03avg", "shipyards",
                                   "Vessel density, dredging / underwater operations (annual avg)",
                                   "EMSA AIS density of dredgers and underwater-ops vessels (marine works footprint).",
                                   ATTR_HA_EMSA, kind="wms", time="2024-01-01T00:00:00Z"),
    "shipyards_osm": {
        "url": OVERPASS[0], "layer": 'nwr["industrial"="shipyard"];nwr["landuse"="shipyard"];',
        "kind": "overpass", "sector": "shipyards", "group": "pressure",
        "title": "Shipyards (OpenStreetMap)",
        "description": "OSM features tagged industrial=shipyard / landuse=shipyard (Constanta, Mangalia, Midia, "
                       "Tulcea, Braila, Galati...; Galati/Braila need a bbox west of 28.4). EMODnet has no shipyard "
                       "layer. Falls back to Nominatim name search when Overpass is overloaded.",
        "attribution": ATTR_OSM,
        "nominatim": ["[shipyard]", "șantierul naval", "santier naval", "shipyard", "ship repair", "Damen", "Vard"],
    },
    "offshore_platforms_osm": {
        "url": OVERPASS[0], "layer": 'nwr["man_made"="offshore_platform"];',
        "kind": "overpass", "sector": "shipyards", "group": "pressure",
        "title": "Offshore platforms (OpenStreetMap)",
        "description": "Oil/gas platforms on the Romanian shelf (EMODnet 'platforms' has none for Romania).",
        "attribution": ATTR_OSM,
    },
    # ---------------------------------------------------------------- (3) coastal & marine tourism
    "bathing_waters": _ha("bathingwaters", "tourism", "State of bathing waters (EEA, BWD)",
                          "Coastal bathing-water sites, one feature per site x year. Per-year class is in 'status'; "
                          "'class' is the LATEST class repeated on every year (use bathing_water_history()). "
                          "RO: 49 sites x 2007-2024.",
                          ATTR_HA_EEA, cql="countrycod='RO' AND year='2024'"),
    "marinas_osm": _ha("osmmarinas", "tourism", "Marinas (OpenStreetMap, via EMODnet)",
                       "Marinas as points (Tomis, Mangalia, Limanu...)."),
    "tourism_nuts3": _ha("tourismnuts3", "tourism", "Tourism ecosystem indicators by NUTS3",
                         "Nights spent, bed capacity, blue flags, % excellent bathing water per NUTS3 (RO223 Constanta, "
                         "RO225 Tulcea).", group="context"),
    "tourism_lau": _ha("tourismlau", "tourism", "Nights spent by municipality (LAU)",
                       "Tourist nights per coastal municipality (Mamaia/Constanta, Eforie, Mangalia...).",
                       group="context"),
    "vessel_density_passenger": _ha("vesseldensity_08avg", "tourism", "Vessel density, passenger (annual avg)",
                                    "EMSA AIS density of passenger ships / ferries / cruise.", ATTR_HA_EMSA, kind="wms",
                                    time="2024-01-01T00:00:00Z"),
    "vessel_density_pleasure": _ha("vesseldensity_05avg", "tourism", "Vessel density, pleasure craft (annual avg)",
                                   "EMSA AIS density of pleasure craft.", ATTR_HA_EMSA, kind="wms",
                                   time="2024-01-01T00:00:00Z"),
    "vessel_density_sailing": _ha("vesseldensity_04avg", "tourism", "Vessel density, sailing (annual avg)",
                                  "EMSA AIS density of sailing vessels.", ATTR_HA_EMSA, kind="wms",
                                  time="2024-01-01T00:00:00Z"),
    # ---------------------------------------------------------------- (4) fishing
    "vessel_density_fishing": _ha("vesseldensity_01avg", "fishing", "Vessel density, fishing (annual avg)",
                                  "EMSA AIS density of fishing vessels - best spatial proxy for fishing pressure "
                                  "(only AIS-equipped vessels, mostly >15 m).", ATTR_HA_EMSA, kind="wms",
                                  time="2024-01-01T00:00:00Z"),
    "route_density_fishing": _ha("routedensity_02avg", "fishing", "Route density, fishing (EMSA, annual)",
                                 "Number of fishing-vessel routes per cell.", ATTR_HA_EMSA, kind="wms",
                                 time="2025-01-01T00:00:00Z"),
    "fishing_effort_ro": _ha("gfcmsubareaeffortbycountry", "fishing",
                             "Fishing effort by GFCM sub-area and country (GSA 29 Black Sea)",
                             "Romanian fleet effort per year in GSA 29 (fishing days, kW-days, GT-days); polygon = "
                             "whole GSA, i.e. a statistic, not a spatial pattern.",
                             cql="country='Romania'"),
    "fishing_effort_gear": _ha("gfcmsubareaeffort", "fishing",
                               "Fishing effort by GFCM sub-area, country, gear, vessel length (GSA 29)",
                               "Effort by fishing technique (fishtech) and length class, Black Sea GSA 29.",
                               cql="sect_cod='GSA29' AND country='Romania'"),
    "fish_sales": _ha("fishsales", "fishing", "First sales of fish (EUMOFA) by port",
                      "Monthly first-sale volumes/values by landing place (only Bulgarian ports in the area)."),
    # ---------------------------------------------------------------- (5) aquaculture
    "shellfish_production": _ha("shellfish", "aquaculture", "Shellfish production sites",
                                "Mussel/oyster farm points. Black Sea: Bulgarian farms only, none in Romania."),
    "finfish_production": _ha("finfish", "aquaculture", "Finfish production sites",
                              "Marine finfish farms (none in the Black Sea)."),
    "shellfish_licences": _ha("shellfishlics", "aquaculture", "Shellfish aquaculture licensed sites",
                              "Licensed polygons (FR/IE/UK... no Black Sea data)."),
    # ---------------------------------------------------------------- context: protected areas
    "natura2000": _ha("natura2000areas", "context", "Natura 2000 sites",
                      "SCI/SAC (sitetype B) and SPA (A) with marine share mar_perc. RO marine: ROSAC0269 Vama Veche - "
                      "2 Mai, ROSCI0066 Delta Dunarii marine, ROSPA0076 Marea Neagra, ROSCI0311 Canionul Viteaz...",
                      ATTR_HA_EEA, group="context"),
    "nationally_designated": _ha("nationallydesignatedareas", "context", "Nationally designated areas (CDDA)",
                                 "National protected areas (e.g. Vama Veche - 2 Mai marine reserve, Agigea dunes).",
                                 ATTR_HA_EEA, group="context"),
    "wdpa": _ha("wdpaareas", "context", "World Database on Protected Areas",
                "WDPA polygons (in the RO bbox only Ukrainian Danube sites are returned).", group="context"),
    # ---------------------------------------------------------------- context: other pressures
    "wastewater_plants": _ha("treatmentplants", "context", "Urban wastewater treatment plants (UWWTD)",
                             "Plants with capacity (p.e.), land-based nutrient pressure on coastal waters.",
                             ATTR_HA_EEA),
    "discharge_points": _ha("dischargepoints", "context", "Wastewater discharge points (UWWTD)",
                            "Outfalls of urban wastewater into rivers/sea.", ATTR_HA_EEA),
    "wind_farms": _ha("windfarms", "context", "Offshore wind farms (points)",
                      "Planned Romanian projects (e.g. Black Sea 1, 500 MW)."),
    "wrecks": _ha("wwshipwrecks", "context", "Wrecks (UKHO)", "Wreck locations incl. dangerous wrecks."),
    "lighthouses": _ha("lighthouses", "context", "Lighthouses", "Coastal lighthouses (context)."),
    "military_areas": _ha("militaryareaspoly", "context", "Military areas (polygons)", "Military exercise areas."),
    # ---------------------------------------------------------------- context: bathymetry / habitats / biology
    "bathymetry": {
        "url": BATHY_WMS, "layer": "emodnet:mean_atlas_land", "kind": "wms", "sector": "context", "group": "context",
        "title": "Bathymetry (EMODnet DTM, atlas style with land)",
        "description": "Mean depth of the EMODnet DTM, 1/16 arc-min; raw grid via WCS coverage emodnet__mean.",
        "attribution": ATTR_BATHY,
    },
    "bathymetry_colour": {
        "url": BATHY_WMS, "layer": "emodnet:mean_multicolour", "kind": "wms", "sector": "context",
        "group": "context", "title": "Bathymetry (EMODnet DTM, multicolour, sea only)",
        "description": "Same DTM, transparent over land.", "attribution": ATTR_BATHY,
    },
    "depth_contours": {
        "url": BATHY_WMS, "layer": "emodnet:contours", "kind": "wms", "sector": "context", "group": "context",
        "title": "Depth contours (EMODnet)", "description": "Isobaths from the EMODnet DTM.",
        "attribution": ATTR_BATHY,
    },
    "seabed_habitats": {
        "url": SEABED_WMS, "layer": "eusm2023_eunis2019_full", "kind": "wms", "sector": "context",
        "group": "context", "title": "Seabed habitats (EUSeaMap 2023, EUNIS 2019)",
        "description": "Broad-scale predicted seabed habitats incl. Black Sea. Service returned HTTP 503 on "
                       "2026-11-23; use seabed_substrate as fallback.",
        "attribution": ATTR_SEABED,
    },
    "seabed_substrate": {
        "url": GEOLOGY_WMS, "layer": "seabed_substrate_250k", "kind": "wms", "sector": "context",
        "group": "context", "title": "Seabed substrate 1:250k (EMODnet Geology, Folk classes)",
        "description": "Mud / sand / coarse / mixed sediment / rock; proxy for benthic habitats.",
        "attribution": ATTR_GEO,
    },
    "seabed_substrate_1m": {
        "url": GEOLOGY_WMS, "layer": "seabed_substrate_1m", "kind": "wms", "sector": "context",
        "group": "context", "title": "Seabed substrate 1:1M (EMODnet Geology)",
        "description": "Coarser, full-coverage version.", "attribution": ATTR_GEO,
    },
    "biology_records_grid": {
        "url": BIOLOGY_WFS, "layer": "Dataportal:eurobis_grid_15m-obisenv", "kind": "wfs", "sector": "context",
        "group": "context", "title": "Biodiversity records per 15' cell (EurOBIS)",
        "description": "Count of species occurrence records per 0.25 deg cell (sampling effort / data density, "
                       "not abundance). Occurrences themselves: OBIS API api.obis.org/v3/occurrence.",
        "attribution": ATTR_BIO,
    },
}


# ------------------------------------------------------------------------------------------------ helpers
def sector_layers() -> dict[str, list[str]]:
    """sector -> [layer keys], sectors in the order of the challenge (ports, shipyards, tourism, fishing, aquaculture,
    context)."""
    out = {s: [] for s in SECTORS}
    for k, v in LAYERS.items():
        out[v["sector"]].append(k)
    return out


def _get(url: str, params: dict | None = None, *, retries: int = 1, timeout: int = TIMEOUT, **kw) -> requests.Response:
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=UA, **kw)
            if r.status_code in (502, 503, 504) and i < retries:
                time.sleep(2 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            if i < retries:
                time.sleep(2 * (i + 1))
    raise RuntimeError(f"request failed: {url} {params}: {last}")


def _in_bbox(geom: dict | None, bbox) -> bool:
    """Cheap client-side bbox test (any vertex inside, or geometry envelope overlapping the bbox)."""
    if not geom:
        return False
    xs, ys = [], []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]), ys.append(c[1])
        else:
            for cc in c:
                walk(cc)

    if geom["type"] == "GeometryCollection":
        return any(_in_bbox(g, bbox) for g in geom["geometries"])
    walk(geom["coordinates"])
    if not xs:
        return False
    x0, y0, x1, y1 = bbox
    return not (max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_cache(p):
    if p.exists():
        return json.loads(p.read_text())
    return None


# ------------------------------------------------------------------------------------------------ vector layers
def fetch_wfs(key: str, bbox=BBOX_RO, max_features: int = 5000, cql: str | None = None,
              refresh: bool = False) -> dict:
    """Fetch a vector layer as a GeoJSON FeatureCollection (EPSG:4326, lon/lat) for bbox=(lon0, lat0, lon1, lat1).

    WFS 1.0.0 GetFeature, outputFormat=application/json. If the layer has a default CQL filter (LAYERS[key]['cql'],
    e.g. country/year for port statistics) or `cql` is passed, the filter runs server side and the bbox is applied
    client side (GeoServer does not combine BBOX and CQL_FILTER). cql="" disables the default filter.
    Also handles kind='overpass' (OpenStreetMap) layers. Result has a foreign member 'meta'
    {source, key, layer, url, bbox, cql, count, total, truncated, fetched, attribution}.
    Cached under data/cache/emodnet_layers; refresh=True forces a new request. On network failure a cached copy is
    returned if one exists.
    """
    spec = LAYERS[key]
    if spec["kind"] == "wms":
        raise ValueError(f"{key} is a WMS-only raster layer; use wms_tile_layer({key!r})")
    cql = spec.get("cql") if cql is None else (cql or None)
    bbox = tuple(float(v) for v in bbox)
    p = cached_path(SOURCE, cache_key("wfs", key, spec["layer"], bbox, max_features, cql), "geojson")
    if not refresh and (gj := _read_cache(p)) is not None:
        return gj
    try:
        if spec["kind"] == "overpass":
            gj = _fetch_overpass(spec, bbox)
        else:
            params = dict(service="WFS", version="1.0.0", request="GetFeature", typeName=spec["layer"],
                          outputFormat="application/json", srsName="EPSG:4326", maxFeatures=int(max_features))
            if cql:
                params["CQL_FILTER"] = cql
            else:
                params["bbox"] = ",".join(map(str, bbox)) + ",EPSG:4326"
            r = _get(spec["url"], params)
            try:
                gj = r.json()
            except ValueError:
                raise RuntimeError(f"WFS {spec['layer']} did not return JSON: {r.text[:300]}")
            if cql:
                gj["features"] = [f for f in gj["features"] if _in_bbox(f.get("geometry"), bbox)]
    except Exception:
        if (gj := _read_cache(p)) is not None:
            return gj
        raise
    n = len(gj.get("features", []))
    total = gj.get("totalFeatures")
    total = total if isinstance(total, int) else None
    gj = {"type": "FeatureCollection", "features": gj.get("features", []),
          "meta": {"source": SOURCE, "key": key, "layer": spec["layer"], "url": spec["url"], "bbox": bbox,
                   "cql": cql, "count": n, "total": total,
                   "truncated": bool(total and total > n and not cql) or n >= max_features,
                   "fetched": _now(), "attribution": spec["attribution"], "title": spec["title"]}}
    p.write_text(json.dumps(gj))
    return gj


def _fetch_overpass(spec: dict, bbox) -> dict:
    x0, y0, x1, y1 = bbox
    b = f"({y0},{x0},{y1},{x1})"
    stmts = "".join(s.strip()[:-1] + b + ";" for s in spec["layer"].split(";") if s.strip())
    q = f"[out:json][timeout:60];({stmts});out center tags;"
    last = None
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": q}, timeout=75, headers=UA)
            r.raise_for_status()
            els = r.json()["elements"]
            break
        except Exception as e:  # try next mirror
            last = e
    else:
        if spec.get("nominatim"):
            return _fetch_nominatim(spec["nominatim"], bbox)
        raise RuntimeError(f"all Overpass mirrors failed: {last}")
    feats = []
    for e in els:
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        if c.get("lat") is None:
            continue
        props = {"osm_type": e["type"], "osm_id": e["id"], **e.get("tags", {})}
        feats.append({"type": "Feature", "id": f"{e['type']}/{e['id']}", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]}})
    return {"type": "FeatureCollection", "features": feats, "totalFeatures": len(feats)}


NOMINATIM = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_SKIP = {"highway", "amenity", "shop", "office", "place", "boundary"}


def _fetch_nominatim(queries: list[str], bbox) -> dict:
    """Fallback when Overpass is overloaded: OSM free-text search bounded to bbox (1 request/s, Nominatim policy).
    Less complete than Overpass; dedupes by OSM id and drops bus stops, banks, etc."""
    x0, y0, x1, y1 = bbox
    feats, seen = {}, set()
    for i, q in enumerate(queries):
        if i:
            time.sleep(1.1)
        r = _get(NOMINATIM, dict(q=q, viewbox=f"{x0},{y1},{x1},{y0}", bounded=1, format="geojson", limit=50),
                 timeout=60)
        for f in r.json().get("features", []):
            p = f["properties"]
            oid = f"{p.get('osm_type')}/{p.get('osm_id')}"
            if oid in seen or p.get("category") in _NOMINATIM_SKIP:
                continue
            seen.add(oid)
            p = {"osm_type": p.get("osm_type"), "osm_id": p.get("osm_id"), "name": p.get("name"),
                 "category": p.get("category"), "type": p.get("type"), "display_name": p.get("display_name"),
                 "via": "nominatim", "query": q}
            feats[oid] = {"type": "Feature", "id": oid, "properties": p, "geometry": f["geometry"]}
    return {"type": "FeatureCollection", "features": list(feats.values()), "totalFeatures": len(feats)}


def fetch_gdf(key: str, **kw):
    """fetch_wfs as a GeoDataFrame (EPSG:4326)."""
    import geopandas as gpd

    gj = fetch_wfs(key, **kw)
    gdf = gpd.GeoDataFrame.from_features(gj["features"], crs="EPSG:4326")
    gdf.attrs = gj["meta"]
    return gdf


# ------------------------------------------------------------------------------------------------ raster / WMS
def wms_tile_layer(key: str, time: str | None = None) -> dict:
    """kwargs for folium.raster_layers.WmsTileLayer(**d): url, layers, attr, fmt, transparent, name, styles, version
    (+ 'time' for EMSA density layers; Leaflet forwards it as the WMS TIME parameter). Works for WFS layers too
    (rendered by the same GeoServer's WMS with its default style)."""
    spec = LAYERS[key]
    if spec["kind"] == "overpass":
        raise ValueError(f"{key} is an OpenStreetMap vector layer; use fetch_wfs({key!r})")
    url = spec.get("wms_url") or spec["url"]
    layer = spec.get("wms_layer") or spec["layer"]
    d = dict(url=url, layers=layer, attr=spec["attribution"], fmt="image/png", transparent=True,
             name=spec["title"], styles=spec.get("styles", ""), version="1.1.1")
    t = time or spec.get("time")
    if t:
        d["time"] = t
    return d


def wms_getmap(key: str, bbox=BBOX_RO, width: int = 800, height: int = 660, time: str | None = None,
               refresh: bool = False) -> bytes:
    """Static PNG (bytes) of a WMS layer for bbox (EPSG:4326). Cached. Raises if the server returns no image."""
    d = wms_tile_layer(key, time)
    params = dict(service="WMS", version="1.1.1", request="GetMap", layers=d["layers"], styles=d["styles"],
                  srs="EPSG:4326", bbox=",".join(map(str, bbox)), width=width, height=height, format="image/png",
                  transparent="true")
    if "time" in d:
        params["time"] = d["time"]
    p = cached_path(SOURCE, cache_key("wms", d["url"], params), "png")
    if not refresh and p.exists():
        return p.read_bytes()
    r = _get(d["url"], params)
    if not r.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"WMS {key} returned {r.headers.get('content-type')}: {r.text[:300]}")
    p.write_bytes(r.content)
    return r.content


def bathymetry_wcs_url(bbox=BBOX_RO) -> str:
    """GetCoverage URL for the raw EMODnet DTM (GeoTIFF float32, elevation m, negative below sea) over bbox.
    Reading it needs rasterio/rioxarray (not installed); depth_at / depth_profile cover point/line needs."""
    x0, y0, x1, y1 = bbox
    return (f"{BATHY_WCS}?service=WCS&version=2.0.1&request=GetCoverage&coverageId=emodnet__mean"
            f"&format=image/tiff&subset=Lat({y0},{y1})&subset=Long({x0},{x1})")


# ------------------------------------------------------------------------------------------------ bathymetry REST
def _bathy_rest(endpoint: str, wkt: str):
    p = cached_path(SOURCE, cache_key("bathy", endpoint, wkt), "json")
    if p.exists():
        return json.loads(p.read_text())
    j = _get(f"{BATHY_REST}/{endpoint}", {"geom": wkt}, timeout=60).json()
    p.write_text(json.dumps(j))
    return j


def depth_at(lat: float, lon: float) -> float:
    """Water depth in metres, POSITIVE DOWN, from the EMODnet DTM (REST depth_sample, 'avg' of the cell).
    Negative values = land elevation above MSL. NaN if the service has no value."""
    j = _bathy_rest("depth_sample", f"POINT({lon} {lat})")
    v = j.get("avg") if isinstance(j, dict) else None
    return float("nan") if v is None else -float(v)


def depth_profile(lat0: float, lon0: float, lat1: float, lon1: float) -> list[float]:
    """Depths (m, positive down) sampled along a straight line, as returned by the EMODnet REST depth_profile."""
    j = _bathy_rest("depth_profile", f"LINESTRING({lon0} {lat0},{lon1} {lat1})")
    return [float("nan") if v is None else -float(v) for v in j]


# ------------------------------------------------------------------------------------------------ smoke test
BW_SCHEME_CHANGE = 2015  # first season classified under Directive 2006/7/EC (earlier: 76/160/EEC compliance codes)


def bathing_water_history(country: str = "RO", bbox=BBOX_RO, refresh: bool = False):
    """Per-year bathing-water classification for every site of `country` inside bbox, as a pandas DataFrame.

    Columns: site_id, name, lat, lon, year (int), class (that season's class label, e.g. '1 - Excellent'),
    class_code (int 0-4), latest_class (most recent class, what the layer's 'class' field holds), scheme.
    Source: EMODnet Human Activities 'emodnet:bathingwaters' (EEA Bathing Water Directive reporting). In that layer
    the field 'class' repeats the latest class on every year; the season's own class is in 'status' (checked
    2026-11-23: RO status counts 2022 45 Excellent/4 Good, 2023 34/15, 2024 41/8 match the EEA country factsheet).
    Seasons before 2015 use the old 76/160/EEC scheme ('3 - Good or Sufficient' = compliant with mandatory values,
    '1 - Excellent' = guide values), so they are not directly comparable with 2015+ classes: see `scheme`.
    """
    import pandas as pd

    gj = fetch_wfs("bathing_waters", bbox=bbox, cql=f"countrycod='{country}'", refresh=refresh)
    rows = []
    for f in gj["features"]:
        p = f["properties"]
        st = str(p.get("status") or "")
        year = int(p["year"])
        rows.append({
            "site_id": p.get("bwid"), "name": p.get("bwname"), "lat": p.get("lat"), "lon": p.get("lon"),
            "year": year, "class": st,
            "class_code": int(st.split(" - ")[0]) if st[:1].isdigit() else None,
            "latest_class": p.get("class"),
            "scheme": "2006/7/EC" if year >= BW_SCHEME_CHANGE else "76/160/EEC",
        })
    df = pd.DataFrame(rows, columns=["site_id", "name", "lat", "lon", "year", "class", "class_code",
                                     "latest_class", "scheme"])
    df = df.sort_values(["site_id", "year"]).reset_index(drop=True)
    df.attrs = {"source": "EMODnet Human Activities, emodnet:bathingwaters (EEA BWD)", "country": country,
                "attribution": LAYERS["bathing_waters"]["attribution"], "fetched": gj["meta"].get("fetched")}
    return df


if __name__ == "__main__":
    import sys
    from collections import Counter

    from . import STATIONS

    print("sector_layers:", {s: len(k) for s, k in sector_layers().items()})
    print("\nDepth (m, positive down):")
    for name, (la, lo) in STATIONS.items():
        print(f"  {name:28s} {depth_at(la, lo):8.1f}")
    prof = depth_profile(44.17, 28.70, 44.17, 29.50)
    print(f"  profile Constanta->E 29.5: n={len(prof)}  {prof[0]:.1f} .. {prof[-1]:.1f} m")

    only = sys.argv[1:]
    print("\nVector layers (BBOX_RO):")
    for k, s in LAYERS.items():
        if s["kind"] == "wms" or (only and k not in only):
            continue
        try:
            gj = fetch_wfs(k)
            f = gj["features"]
            ex = ""
            if f:
                pr = f[0]["properties"]
                name = next((pr[c] for c in ("sitename", "name", "portname", "port", "bwname", "uwwname", "dcpname",
                                             "nuts_name", "lau_name", "country") if pr.get(c)), "")
                ex = f"e.g. {name!s:.40}"
            cc = Counter(str(x["properties"].get("country") or x["properties"].get("countrycod") or "")
                         for x in f).most_common(3)
            print(f"  OK   {k:26s} {len(f):5d} feats  {cc}  {ex}")
        except Exception as e:
            print(f"  FAIL {k:26s} {type(e).__name__}: {str(e)[:120]}")

    if not only or "bathing_waters" in only:
        print("\nBathing-water history (per-year 'status', RO):")
        try:
            bw = bathing_water_history()
            last = bw[bw.year >= bw.year.max() - 2].groupby(["year", "class"]).size().unstack(fill_value=0)
            print(f"  OK   {bw.site_id.nunique()} sites, {bw.year.min()}-{bw.year.max()}, {len(bw)} site-years")
            print("  " + last.to_string().replace("\n", "\n  "))
        except Exception as e:
            print(f"  FAIL bathing_water_history {type(e).__name__}: {str(e)[:120]}")

    print("\nWMS GetMap over BBOX_RO:")
    from io import BytesIO

    try:
        from PIL import Image
    except ImportError:
        Image = None
    for k, s in LAYERS.items():
        if s["kind"] != "wms" or (only and k not in only):
            continue
        try:
            png = wms_getmap(k, width=400, height=330)
            cov = ""
            if Image:
                a = Image.open(BytesIO(png)).convert("RGBA").getchannel("A")
                h = a.histogram()
                cov = f"non-transparent {1 - h[0] / sum(h):.0%}"
            print(f"  OK   {k:26s} {len(png):7d} B  {cov}")
        except Exception as e:
            print(f"  FAIL {k:26s} {type(e).__name__}: {str(e)[:120]}")
