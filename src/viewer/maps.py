"""Folium map for the viewer: basemaps, gridded layer, pressure overlap, sector zones, in-situ points, Natura 2000."""

from __future__ import annotations

import logging

import folium
import numpy as np
import pandas as pd

from viewer import adapters as A
from viewer.style import OVERLAP, SECTOR, OI, esc, overlap_levels

log = logging.getLogger("viewer")

ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"

# map layer catalogue (id -> label, group); gridded ones come from adapters.LAYERS
CATALOGUE = {
    "Conditions (gridded, with date)": {k: v["title"] for k, v in A.LAYERS.items()},
    "Measurements": {"insitu": "In-situ buoys and stations"},
    "Pressures": {"overlap": "Pressure overlap (number of sectors, 1-5)", "zones": "Sector zones (buffers)",
                  "features": "Sector activities (ports, beaches, farms...)"},
    "Context": {"natura": "Natura 2000 protected sites", "bathy": "Bathymetry (EMODnet depth)"},
    "Waves, currents and wind": {"vec_waves": "Waves (height, direction, period)",
                                 "vec_currents": "Currents (speed and direction)", "vec_wind": "Wind (speed and direction)"},
}
GRIDDED = set(A.LAYERS)
VECTOR = {"vec_waves": "waves", "vec_currents": "currents", "vec_wind": "wind"}


def base_map(lat, lon, zoom) -> folium.Map:
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=True, max_zoom=16, min_zoom=5,
                   prefer_canvas=False)  # SVG renderer: needed for the hatch patterns
    folium.TileLayer(ESRI.format("Ocean/World_Ocean_Base"), attr="Esri, GEBCO, NOAA, DeLorme",
                     name="Ocean basemap (bathymetry)", max_native_zoom=10, max_zoom=16, show=True).add_to(m)
    folium.TileLayer(ESRI.format("Canvas/World_Light_Gray_Base"), attr="Esri, HERE, DeLorme",
                     name="Light grey basemap", max_native_zoom=16, max_zoom=16, show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    folium.TileLayer(ESRI.format("World_Imagery"), attr="Esri World Imagery", name="Satellite image",
                     max_zoom=16, show=False).add_to(m)
    return m


def add_field(m, fd: dict, opacity: float = 0.85):
    # own pane below the vector overlay pane (400), so zones and overlap always draw on top of the field
    folium.map.CustomPane("gridfield", z_index=350, pointer_events=False).add_to(m)
    folium.raster_layers.ImageOverlay(image=fd["rgba"], bounds=fd["bounds"], opacity=opacity, mercator_project=True,
                                      name=f"{fd['title']} ({fd['time']})", interactive=False,
                                      pane="gridfield").add_to(m)


def add_tiles(m, url: str, title: str, opacity: float = 0.8):
    folium.TileLayer(tiles=url, attr="Copernicus Marine Service", name=title, overlay=True, opacity=opacity,
                     max_native_zoom=9, max_zoom=16).add_to(m)


def add_bathy(m):
    try:
        from marinekit.sources import emodnet_layers as el
        d = el.wms_tile_layer("depth_contours")
        folium.raster_layers.WmsTileLayer(url=d["url"], layers=d["layers"], fmt="image/png", transparent=True,
                                          attr=d["attr"], name="Depth contours (EMODnet)", overlay=True,
                                          opacity=0.6, version=d["version"]).add_to(m)
    except Exception as ex:
        log.info("bathy: %s", ex)


STROKE = {1: 0.8, 2: 1.3, 3: 2.0, 4: 2.8, 5: 3.4}


def add_overlap(m, gj: dict, season: str, hatched: bool = False):
    """Solid fill on its own; outlines plus hatching per level when a gridded layer is underneath, so both stay
    readable (1 sector = thin and sparse, 4-5 = thick, dense and dark). Colours from overlap_style.json."""
    from folium.plugins import StripePattern
    lv = overlap_levels()
    pats = {}
    if hatched:
        for n, (col, op, _) in lv.items():
            pats[n] = StripePattern(angle=-45, color=col, space_color="#ffffff", opacity=min(0.95, op + 0.1),
                                    space_opacity=0.0, weight=1 + 0.6 * n, space_weight=max(2.0, 9 - 1.6 * n))
            pats[n].add_to(m)

    def style(f):
        n = int(f["properties"]["n"])
        col, op, _ = lv.get(n, ("#cccccc", 0.6, ""))
        if hatched:
            return {"color": col, "weight": STROKE.get(n, 2), "opacity": min(1.0, op + 0.15),
                    "fillPattern": pats.get(n), "fillOpacity": 1.0}
        return {"fillColor": col, "color": col, "weight": 0, "fillOpacity": op}

    for f in gj["features"]:
        n = int(f["properties"]["n"])
        f["properties"]["label"] = f"{n} of 5 sectors overlap ({season})"
    folium.GeoJson(gj, name=f"Pressure overlap ({season})", style_function=style, zoom_on_click=False,
                   tooltip=folium.GeoJsonTooltip(["label"], labels=False)).add_to(m)


def add_zones(m, gj: dict, season: str, only_sector: str | None = None):
    fg = folium.FeatureGroup(name="Sector zones").add_to(m)
    for f in gj["features"]:
        p = f["properties"]
        if only_sector and p["sector"] != only_sector:
            continue
        if season == "winter" and str(p.get("season")) == "summer":
            continue
        lab, col = SECTOR.get(p["sector"], (p["sector"], "#555"))
        dashed = str(p.get("confidence")) == "assumed"
        buf = p.get("buffer_m")
        tip = (f"<b>{esc(lab)}</b><br>{esc(p.get('activity') or '')}<br>"
               f"buffer {buf:.0f} m ({esc(p.get('buffer_basis'))})<br>confidence: {esc(p.get('confidence'))}"
               if buf == buf and buf is not None else f"<b>{esc(lab)}</b>")
        folium.GeoJson(f, style_function=lambda _f, col=col, dashed=dashed: {
            "color": col, "weight": 1.6, "fillColor": col, "fillOpacity": 0.06, "dashArray": "6 5" if dashed else None},
            tooltip=folium.Tooltip(tip), zoom_on_click=False).add_to(fg)


def add_features(m, gj: dict, season: str, only_sector: str | None = None):
    fg = folium.FeatureGroup(name="Sector activities").add_to(m)
    for f in gj["features"]:
        p = f["properties"]
        if only_sector and p["sector"] != only_sector:
            continue
        if season == "winter" and str(p.get("season")) == "summer":
            continue
        lab, col = SECTOR.get(p["sector"], (p["sector"], "#555"))
        conf = str(p.get("confidence") or "")
        tip = (f"<b>{esc(p.get('name') or p.get('activity'))}</b><br>{esc(lab)}: {esc(p.get('activity'))}<br>"
               f"confidence: {esc(conf)}<br><span style='color:#666'>{esc(str(p.get('source'))[:90])}</span>")
        url = str(p.get("source_url") or "")
        pop = folium.Popup(tip + (f"<br><a href='{esc(url)}' target='_blank' rel='noopener'>open source</a>"
                                  if url.startswith("http") else ""), max_width=320)
        g = f.get("geometry") or {}
        if g.get("type") == "Point":
            x, y = g["coordinates"][:2]
            folium.CircleMarker([y, x], radius=3.5, color=col, weight=1.5 if conf != "assumed" else 1,
                                fill=conf != "assumed", fill_opacity=0.9, dash_array="2 2" if conf == "assumed" else None,
                                tooltip=folium.Tooltip(tip), popup=pop).add_to(fg)
        else:
            folium.GeoJson(f, style_function=lambda _f, col=col, conf=conf: {
                "color": col, "weight": 2, "fillColor": col,
                "dashArray": "4 4" if conf == "assumed" else None, "fillOpacity": 0.0 if conf == "assumed" else 0.25},
                tooltip=folium.Tooltip(tip), popup=pop, zoom_on_click=False).add_to(fg)


def add_natura(m, gj: dict | None):
    if not gj:
        return
    folium.GeoJson(gj, name="Natura 2000", style_function=lambda f: {
        "color": "#1B7F3B", "weight": 1.4, "fillColor": "#1B7F3B", "fillOpacity": 0.05, "dashArray": "3 3"},
        tooltip=folium.GeoJsonTooltip(["sitename", "sitecode"], aliases=["Natura 2000", "Code"]),
        zoom_on_click=False).add_to(m)


PTYPE_COLOR = {"Mooring": OI["blue"], "Tide Gauge": OI["sky"], "Gliders": OI["purple"], "Drifting Buoys": OI["purple"]}


def add_platforms(m, p: pd.DataFrame, detail: bool):
    fg = folium.FeatureGroup(name="In-situ platforms").add_to(m)
    for _, r in p.iterrows():
        trust = r.trust
        col = PTYPE_COLOR.get(r.type, OI["blue"])
        grey = trust in ("under_qc", "context") or not r.recent
        if grey:
            col = "#9AA3AD"
        params = ", ".join(r.canonical[:8]) if isinstance(r.canonical, list) else ""
        status = {"under_qc": "under QC (not trusted yet)", "context": "context only",
                  "good": "trusted", "not_assessed": "not assessed"}[trust]
        last = r.time_end.strftime("%d %b %Y") if pd.notna(r.time_end) else "unknown"
        tip = (f"<b>{esc(r['name'])}</b> ({esc(r.id)})<br>{esc(r.type)} - last data {last}<br>"
               f"status: {status}<br>{esc(params)}")
        if detail:
            tip += f"<br><span style='color:#666'>{esc(r.trust_note)}</span>"
        folium.CircleMarker([r.lat, r.lon], radius=6 if r.recent else 4.5, color="#1C2430" if not grey else "#9AA3AD",
                            weight=1.2, fill=True, fill_color=col, fill_opacity=0.95 if not grey else 0.5,
                            tooltip=folium.Tooltip(tip)).add_to(fg)


def add_selection(m, sel: dict | None):
    if not sel:
        return
    folium.CircleMarker([sel["lat"], sel["lon"]], radius=9, color="#000", weight=2.5, fill=False,
                        tooltip=f"Selected: {esc(sel['name'])}").add_to(m)
    folium.CircleMarker([sel["lat"], sel["lon"]], radius=2.5, color="#000", fill=True, fill_opacity=1).add_to(m)
    if sel.get("wkt"):
        try:
            from shapely import wkt
            from shapely.geometry import mapping
            folium.GeoJson(mapping(wkt.loads(sel["wkt"])), style_function=lambda f: {
                "color": "#000", "weight": 2.2, "fill": False}).add_to(m)
        except Exception:
            pass


def _ticks(fd):
    if fd["log"]:
        lo, hi = np.log10(max(fd["vmin"], 1e-3)), np.log10(max(fd["vmax"], 1e-3))
        return [10 ** x for x in np.linspace(lo, hi, 4)]
    return list(np.linspace(fd["vmin"], fd["vmax"], 4))


def _fmt(x):
    return f"{x:.2f}" if abs(x) < 1 else (f"{x:.1f}" if abs(x) < 20 else f"{x:.0f}")


def legend_html(fd: dict | None, layers: set, season: str, detail: bool, levels: list | None = None,
                hatched: bool = False) -> str:
    parts = []
    if fd:
        grad = ", ".join(fd["colors"])
        ticks = "".join(f"<span>{_fmt(t)}</span>" for t in _ticks(fd))
        src = f"{fd['origin']}, {fd['time']}" + (f" - {fd['dataset']}" if detail else "")
        parts.append(
            f"<div style='font-weight:650'>{esc(fd['title'])} ({esc(fd['unit'])})</div>"
            f"<div style='height:10px;width:190px;background:linear-gradient(to right,{grad});border-radius:2px'></div>"
            f"<div style='display:flex;justify-content:space-between;width:190px;font-size:11px'>{ticks}</div>"
            f"<div style='color:#666;font-size:10.5px;margin-bottom:4px'>{esc(src)}{' - log scale' if fd['log'] else ''}</div>")
    if "overlap" in layers:
        lv = overlap_levels()
        present = sorted(levels or lv)
        def sw(n):
            col, op, _ = lv[n]
            if hatched:
                gap = max(2, int(9 - 1.6 * n))
                bg = (f"repeating-linear-gradient(-45deg,{col} 0 {1 + 0.6 * n:.1f}px,transparent {1 + 0.6 * n:.1f}px "
                      f"{1 + 0.6 * n + gap:.1f}px)")
                return (f"<span style='display:inline-block;width:18px;height:11px;background:{bg};"
                        f"border:{STROKE.get(n, 2):.1f}px solid {col};margin-right:5px;vertical-align:middle'></span>")
            return (f"<span style='display:inline-block;width:18px;height:10px;background:{col};"
                    f"opacity:{max(op, 0.55)};margin-right:5px;vertical-align:middle'></span>")
        rows = "".join(f"<div>{sw(n)}{esc(lv[n][2])}</div>" for n in present if n in lv)
        parts.append(f"<div style='font-weight:650;margin-top:2px'>Sectors overlapping ({season}), of 5</div>{rows}")
    if "zones" in layers or "features" in layers:
        rows = "".join(f"<div><span style='display:inline-block;width:10px;height:10px;border:2px solid {c};"
                       f"margin-right:5px'></span>{esc(l)}</div>" for k, (l, c) in SECTOR.items())
        parts.append(f"<div style='font-weight:650;margin-top:4px'>Sectors</div>{rows}"
                     f"<div style='color:#666;font-size:10.5px'>dashed = location assumed, to confirm with NIMRD</div>")
    if "insitu" in layers:
        parts.append("<div style='font-weight:650;margin-top:4px'>In-situ</div>"
                     f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{OI['blue']};"
                     "border:1px solid #1C2430;margin-right:5px'></span>trusted or not assessed</div>"
                     "<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#9AA3AD;"
                     "margin-right:5px'></span>under QC, context only, or no recent data</div>")
    if "natura" in layers:
        parts.append("<div style='margin-top:4px'><span style='display:inline-block;width:10px;height:10px;"
                     "border:1.5px dashed #1B7F3B;margin-right:5px'></span>Natura 2000 site</div>")
    if not parts:
        return ""
    # collapsible, height-capped legend so it never hides the coast it explains
    return ("<details open style='position:absolute;bottom:22px;right:10px;z-index:9999;background:rgba(255,255,255,0.94);"
            "color:#1C2430;padding:6px 10px;border-radius:6px;font:11.5px/1.3 -apple-system,Segoe UI,sans-serif;"
            "box-shadow:0 1px 4px rgba(0,0,0,.25);max-width:230px'>"
            "<summary style='cursor:pointer;font-weight:650;color:#444'>Legend</summary>"
            "<div style='max-height:min(48vh,340px);overflow-y:auto;margin-top:4px'>" + "".join(parts) + "</div></details>")


def build(view: dict, layers: set, day: str, season: str, sel: dict | None, detail: bool, tiles_mode: bool = False,
          only_sector: str | None = None) -> tuple[folium.Map, dict | None, list[str]]:
    """Return (map, field dict or None, messages)."""
    msgs = []
    m = base_map(view["lat"], view["lon"], view["zoom"])
    stamp = A._zones_stamp()
    fd = None
    grid = [l for l in layers if l in GRIDDED]
    if grid:
        lay = grid[0]
        grid_op = 0.45 if "overlap" in layers else 0.85
        if tiles_mode:
            url = A.tile_url(lay, day)
            if url:
                add_tiles(m, url, A.LAYERS[lay]["title"], opacity=grid_op)
            else:
                msgs.append(f"{A.LAYERS[lay]['title']}: no map tiles available.")
        else:
            try:
                fd = A.field(lay, day)
            except A.SlowSource:
                fd = None
                msgs.append(f"{A.LAYERS[lay]['title']}: still downloading for {day}; it will appear on the next refresh.")
            if A.LAYERS[lay].get("note"):
                msgs.append(A.LAYERS[lay]["note"])
            if fd:
                add_field(m, fd, opacity=grid_op)
                if fd["time"] != day:
                    msgs.append(f"{fd['title']}: nearest available day is {fd['time']}.")
            else:
                url = A.tile_url(lay, day)
                if url:
                    add_tiles(m, url, A.LAYERS[lay]["title"])
                    msgs.append(f"{A.LAYERS[lay]['title']}: the grid could not be downloaded, showing Copernicus map tiles instead (online only).")
                else:
                    msgs.append(f"{A.LAYERS[lay]['title']}: no data for {day}.")
    if "bathy" in layers:
        add_bathy(m)
    levels = None
    if "overlap" in layers:
        ogj = A.overlap_geojson(season, stamp)
        levels = sorted({int(f["properties"]["n"]) for f in ogj["features"]})
        add_overlap(m, ogj, season, hatched=bool(grid))
    if "zones" in layers:
        add_zones(m, A.sector_zones(stamp), season, only_sector)
    if "features" in layers:
        add_features(m, A.sector_features(stamp), season, only_sector)
    if "natura" in layers:
        add_natura(m, A.natura())
    for lid, kind in VECTOR.items():
        if lid in layers:
            vv = A.vectorviz()
            if vv is None or not hasattr(vv, "field_layer"):
                msgs.append("Waves, currents and wind: the vector module is not ready yet.")
                continue
            try:
                ds = vv.load_field(kind, A.BBOX_RO, day) if hasattr(vv, "load_field") else None
                vv.field_layer(m, ds, kind, day)
            except Exception as ex:
                msgs.append(f"{kind.capitalize()} layer failed: {str(ex)[:120]}")
    if "insitu" in layers:
        add_platforms(m, A.platforms(), detail)
    add_selection(m, sel)
    lg = legend_html(fd, layers, season, detail, levels, hatched=bool(grid))
    if lg:
        m.get_root().html.add_child(folium.Element(lg))
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m, fd, msgs
