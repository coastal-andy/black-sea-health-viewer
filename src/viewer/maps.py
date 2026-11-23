"""Folium map for the viewer: basemaps, gridded layer, pressure overlap, sector zones, in-situ points, Natura 2000."""

from __future__ import annotations

import logging

import folium
import numpy as np
import pandas as pd

from viewer import adapters as A
from viewer.style import FONT_NUM, FONT_UI, OVERLAP, SECTOR, OI, esc, overlap_levels, theme_name, tokens

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


def _fs_icon(colour: str) -> str:
    from urllib.parse import quote
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 18 18'><path d='M2 7 V2 H7 "
           f"M11 2 H16 V7 M16 11 V16 H11 M7 16 H2 V11' fill='none' stroke='{colour}' stroke-width='1.6'/></svg>")
    return "url(\"data:image/svg+xml;utf8," + quote(svg, safe=" =:/;,'()") + "\")"


def base_map(lat, lon, zoom, theme: str | None = None) -> folium.Map:
    """Basemap matched to the viewer theme: Esri dark grey (dark) or light grey canvas (light), others in the layer list."""
    t = tokens(theme)
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=True, max_zoom=16, min_zoom=5,
                   prefer_canvas=False, zoom_control="topright")  # SVG renderer: needed for the hatch patterns
    from folium.plugins import Fullscreen
    Fullscreen(position="topright", title="Full-screen map", title_cancel="Exit full screen").add_to(m)
    # Esri dark / light grey canvas (no API key needed; CARTO tiles now ask for one), with its label layer on top
    folium.TileLayer(ESRI.format(f"Canvas/World_{t['basemap']}_Gray_Base"), attr="Esri, HERE, Garmin, OpenStreetMap",
                     name="Basemap (matches the theme)", max_native_zoom=16, max_zoom=16, show=True).add_to(m)
    folium.TileLayer(ESRI.format(f"Canvas/World_{t['basemap']}_Gray_Reference"), attr="Esri", name="Place names",
                     overlay=True, control=False, max_native_zoom=16, max_zoom=16, show=True, pane="shadowPane"
                     ).add_to(m)
    folium.TileLayer(ESRI.format("Ocean/World_Ocean_Base"), attr="Esri, GEBCO, NOAA, DeLorme",
                     name="Ocean basemap (bathymetry)", max_native_zoom=10, max_zoom=16, show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    folium.TileLayer(ESRI.format("World_Imagery"), attr="Esri World Imagery", name="Satellite image",
                     max_zoom=16, show=False).add_to(m)
    # fill the iframe height (the viewer sets the iframe to the page height) and theme the Leaflet controls
    m.get_root().header.add_child(folium.Element(
        f"<style>html,body{{background:{t['bg']};}} .folium-map,#map_div{{height:100vh !important;}}"
        f".leaflet-container{{background:{t['bg']};font-family:{FONT_UI};}}"
        f".leaflet-bar a,.leaflet-control-layers{{background:{t['overlay']} !important;color:{t['text']} !important;"
        f"border-color:{t['ctrl']} !important;border-radius:4px !important;}}"
        f".leaflet-bar{{border:1px solid {t['ctrl']} !important;border-radius:4px !important;box-shadow:none !important;}}"
        f".leaflet-control-layers{{box-shadow:none !important;border:1px solid {t['ctrl']} !important;}}"
        f".leaflet-control-layers label{{color:{t['text']};}}"
        f".leaflet-control-zoom-fullscreen,.leaflet-control-zoom-fullscreen.fullscreen-icon{{background-image:{_fs_icon(t['text'])} !important;background-size:18px 18px !important;"
        f"background-position:center !important;background-repeat:no-repeat !important;}}"
        f".leaflet-control-attribution{{background:{t['overlay']} !important;color:{t['muted']} !important;}}"
        f".leaflet-control-attribution a{{color:{t['muted']} !important;}}"
        f".leaflet-control-scale-line{{background:transparent;color:{t['muted']};border-color:{t['muted']};}}"
        f".leaflet-popup-content-wrapper,.leaflet-popup-tip,.leaflet-tooltip{{background:{t['panel']};color:{t['text']};"
        f"border-radius:4px;border:1px solid {t['ctrl']};box-shadow:none;}}</style>"))
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
    """Compact themed legend (flat panel, hairline border, 4 px corners), collapsible and height-capped."""
    t = tokens()
    lab = (f"font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:{t['muted']};"
           "display:block;margin:8px 0 4px 0")
    num = f"font-family:{FONT_NUM};font-size:12.5px"
    row = "display:flex;align-items:center;gap:7px;margin:2px 0"
    parts = []
    if fd:
        grad = ", ".join(fd["colors"])
        ticks = "".join(f"<span>{_fmt(x)}</span>" for x in _ticks(fd))
        src = f"{fd['origin']}, {fd['time']}" + (f", {fd['dataset']}" if detail else "") + (", log scale" if fd["log"] else "")
        parts.append(
            f"<span style='{lab};margin-top:2px'>{esc(fd['title'])} {esc(fd['unit'])} &middot; {esc(fd['origin'])}</span>"
            f"<div style='height:6px;width:200px;background:linear-gradient(to right,{grad})'></div>"
            f"<div style='display:flex;justify-content:space-between;width:200px;{num};margin-top:2px'>{ticks}</div>"
            f"<div style='font-size:10.5px;color:{t['muted']}'>{esc(src)}</div>")
    if "overlap" in layers:
        lv = overlap_levels()
        present = sorted(levels or lv)

        def sw(n):
            col, op, _ = lv[n]
            if hatched:
                gap = max(2, int(9 - 1.6 * n))
                bg = (f"repeating-linear-gradient(-45deg,{col} 0 {1 + 0.6 * n:.1f}px,transparent {1 + 0.6 * n:.1f}px "
                      f"{1 + 0.6 * n + gap:.1f}px)")
                return (f"<span style='display:inline-block;width:22px;height:12px;background:{bg};"
                        f"border:{STROKE.get(n, 2):.1f}px solid {col}'></span>")
            return f"<span style='display:inline-block;width:22px;height:12px;background:{col};opacity:{max(op, 0.6)}'></span>"
        cells = "".join(f"<span style='{row};margin:0 6px 0 0'>{sw(n)}<span style='{num}'>{n}</span></span>"
                        for n in present if n in lv)
        parts.append(f"<span style='{lab}'>Sectors overlapping, of 5 ({esc(season)})</span>"
                     f"<div style='display:flex;flex-wrap:wrap;gap:2px 0'>{cells}</div>")
    if "zones" in layers or "features" in layers:
        rows = "".join(f"<div style='{row}'><span style='width:10px;height:10px;border:2px solid {c}'></span>{esc(l)}</div>"
                       for k, (l, c) in SECTOR.items())
        parts.append(f"<span style='{lab}'>Sectors</span>{rows}"
                     f"<div style='{row};color:{t['muted']}'><span style='width:10px;height:10px;"
                     f"border:2px dashed {t['muted']}'></span>dashed = location assumed</div>")
    if "insitu" in layers:
        parts.append(f"<span style='{lab}'>In-situ</span>"
                     f"<div style='{row}'><span style='width:9px;height:9px;border-radius:50%;background:{OI['blue']};"
                     f"border:1px solid {t['text']}'></span>trusted or not assessed</div>"
                     f"<div style='{row}'><span style='width:9px;height:9px;border-radius:50%;background:#9AA3AD'></span>"
                     "under QC, context only, or old</div>")
    if "natura" in layers:
        parts.append(f"<div style='{row};margin-top:8px'><span style='width:10px;height:10px;"
                     "border:1.5px dashed #1B7F3B'></span>Natura 2000 site</div>")
    if not parts:
        return ""
    return (f"<details open class='bsv-legend' style='position:absolute;bottom:26px;right:10px;z-index:9999;"
            f"background:{t['overlay']};color:{t['text']};padding:6px 12px 8px 12px;border-radius:4px;"
            f"border:1px solid {t['ctrl']};font:12px/1.35 {FONT_UI};max-width:250px'>"
            f"<summary style='cursor:pointer;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;"
            f"color:{t['muted']}'>Legend</summary>"
            "<div style='max-height:min(46vh,330px);overflow-y:auto'>" + "".join(parts) + "</div></details>")


def build(view: dict, layers: set, day: str, season: str, sel: dict | None, detail: bool, tiles_mode: bool = False,
          only_sector: str | None = None, theme: str | None = None,
          legend: bool = True) -> tuple[folium.Map, dict | None, list[str]]:
    """Return (map, field dict or None, messages)."""
    msgs = []
    m = base_map(view["lat"], view["lon"], view["zoom"], theme)
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
    lg = legend_html(fd, layers, season, detail, levels, hatched=bool(grid)) if legend else ""
    if lg:
        m.get_root().html.add_child(folium.Element(lg))
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m, fd, msgs
