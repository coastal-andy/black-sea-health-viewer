"""Folium map for the viewer: basemaps, gridded layer, pressure overlap, sector zones, in-situ points, Natura 2000."""

from __future__ import annotations

import logging

import folium
from jinja2 import Template
import numpy as np
import pandas as pd

from viewer import adapters as A
from viewer.i18n import data, dt, num
from viewer.i18n import t as tr  # 't' is the theme tokens in this module
from viewer.style import FONT_NUM, FONT_UI, OVERLAP, SECTOR, OI, esc, overlap_levels, theme_name, tokens

log = logging.getLogger("viewer")
# the font stacks without quotes: they go inside style='...' attributes, where a quote would end the attribute
FONT_UI, FONT_NUM = FONT_UI.replace("'", ""), FONT_NUM.replace("'", "")

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
    Fullscreen(position="topright", title=tr("Full-screen map"), title_cancel=tr("Exit full screen")).add_to(m)
    # Esri dark / light grey canvas (no API key needed; CARTO tiles now ask for one), with its label layer on top
    folium.TileLayer(ESRI.format(f"Canvas/World_{t['basemap']}_Gray_Base"), attr="Esri, HERE, Garmin, OpenStreetMap",
                     name=tr("Basemap (matches the theme)"), max_native_zoom=16, max_zoom=16, show=True).add_to(m)
    folium.TileLayer(ESRI.format(f"Canvas/World_{t['basemap']}_Gray_Reference"), attr="Esri", name="Place names",
                     overlay=True, control=False, max_native_zoom=16, max_zoom=16, show=True, pane="shadowPane"
                     ).add_to(m)
    folium.TileLayer(ESRI.format("Ocean/World_Ocean_Base"), attr="Esri, GEBCO, NOAA, DeLorme",
                     name=tr("Ocean basemap (bathymetry)"), max_native_zoom=10, max_zoom=16, show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    folium.TileLayer(ESRI.format("World_Imagery"), attr="Esri World Imagery", name=tr("Satellite image"),
                     max_zoom=16, show=False).add_to(m)
    # fill the iframe height (the viewer sets the iframe to the page height) and theme the Leaflet controls
    from viewer.style import FONTS_URL
    m.get_root().header.add_child(folium.Element(f"<link href='{FONTS_URL}' rel='stylesheet'>"))
    m.get_root().header.add_child(folium.Element(
        f"<style>html,body{{background:{t['bg']};}} .folium-map,#map_div{{height:100vh !important;}}"
        f".leaflet-container{{background:{t['bg']};font-family:{FONT_UI};}}"
        "details.bsv-legend[open] .lg-closed,details.bsv-legend:not([open]) .lg-open{display:none;}"
        f".leaflet-bar a,.leaflet-control-layers{{background:{t['overlay']} !important;color:{t['text']} !important;"
        f"border-color:{t['ctrl']} !important;border-radius:4px !important;}}"
        f".leaflet-bar{{border:1px solid {t['ctrl']} !important;border-radius:4px !important;box-shadow:none !important;}}"
        f".leaflet-control-layers{{box-shadow:none !important;border:1px solid {t['ctrl']} !important;}}"
        f".leaflet-control-layers label{{color:{t['text']};}}"
        f".leaflet-control-zoom-fullscreen,.leaflet-control-zoom-fullscreen.fullscreen-icon{{background-image:{_fs_icon(t['text'])} !important;background-size:18px 18px !important;"
        f"background-position:center !important;background-repeat:no-repeat !important;}}"
        f".leaflet-control-attribution{{background:{t['overlay']} !important;color:{t['muted']} !important;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:calc(100vw - 120px);font-size:10px;}}"
        f".leaflet-control-attribution a{{color:{t['muted']} !important;}}"
        f".leaflet-control-scale-line{{background:transparent;color:{t['muted']};border-color:{t['muted']};}}"
        f".leaflet-popup-content-wrapper,.leaflet-popup-tip,.leaflet-tooltip{{background:{t['panel']};color:{t['text']};"
        f"border-radius:4px;border:1px solid {t['ctrl']};box-shadow:none;}}</style>"))
    m.add_child(_LegendCollapse())
    return m


class _LegendCollapse(folium.MacroElement):
    """Starts the map legend folded in narrow windows (the viewer stacks the map above the panel below 900 px).
    Runs with the map script, because scripts inside the legend HTML are not executed by streamlit-folium."""
    _template = Template("""{% macro script(this, kwargs) %}
    setTimeout(function () {
        var w = window.innerWidth;
        try { w = window.parent.innerWidth; } catch (e) {}
        if (w < 900) { document.querySelectorAll('details.bsv-legend').forEach(function (d) { d.open = false; }); }
    }, 0);
    {% endmacro %}""")


def add_field(m, fd: dict, opacity: float = 0.85):
    # own pane below the vector overlay pane (400), so zones and overlap always draw on top of the field
    folium.map.CustomPane("gridfield", z_index=350, pointer_events=False).add_to(m)
    folium.raster_layers.ImageOverlay(image=fd["rgba"], bounds=fd["bounds"], opacity=opacity, mercator_project=True,
                                      name=f"{tr(fd['title'])} ({fd['time']})", interactive=False,
                                      pane="gridfield").add_to(m)


class _TileErrors(folium.MacroElement):
    """If Copernicus tiles fail to load (network drop, service error), say so on the map instead of leaving a
    silent blank: a small note at the top of the map after the third failed tile."""
    _template = Template("""{% macro script(this, kwargs) %}
    (function () {
        var n = 0;
        {{ this.layer.get_name() }}.on('tileerror', function () {
            n += 1;
            if (n !== 3) return;
            var d = document.createElement('div');
            d.textContent = {{ this.msg|tojson }};
            d.style.cssText = {{ this.css|tojson }};
            document.body.appendChild(d);
        });
    })();
    {% endmacro %}""")

    def __init__(self, layer, msg: str, css: str):
        super().__init__()
        self.layer, self.msg, self.css = layer, msg, css


def add_tiles(m, url: str, title: str, opacity: float = 0.8):
    t = tokens()
    lay = folium.TileLayer(tiles=url, attr="Copernicus Marine Service", name=title, overlay=True, opacity=opacity,
                           max_native_zoom=9, max_zoom=16).add_to(m)
    css = (f"position:absolute;left:50%;top:12px;transform:translateX(-50%);z-index:9999;max-width:70%;"
           f"background:{t['overlay']};color:{t['text']};border:1px solid {t['alert']};border-radius:4px;"
           f"padding:5px 10px;font:12px/1.35 {FONT_UI}")
    m.add_child(_TileErrors(lay, tr("Some Copernicus map tiles did not load. Turn the map tiles off in "
                                    "Map layers to use the local layer."), css))


# one fold control per legend; its label follows the state (CSS in base_map)
LEGEND_SUMMARY = "<span class='lg-open'>Hide legend</span><span class='lg-closed'>Legend</span>"  # English; _summary() translates
FIELD_ALPHA = 0.82  # alpha of the gridded image (adapters.field); the legend bar uses the same overall opacity


def _tiles(m, lay, day, opacity, msgs):
    """Copernicus WMTS tiles. If the grid is in the cache, the tiles get the viewer's ramp and range (and the legend
    matches); otherwise they keep the service's own colours and the legend says so. The tile TIME is the nearest day
    the service has published (it returns no image for an unpublished day, e.g. today for satellite SST).
    Returns a legend dict, or None when the service cannot be reached (the caller then draws the local layer)."""
    L = A.LAYERS[lay]
    try:
        tday = A.tile_day(lay, day)
    except Exception:
        tday = None
    if not tday:
        return None
    try:
        fd = A.timed(A.field, lay, day, timeout=1.5)  # never block long: unstyled tiles are fine meanwhile
    except Exception:
        fd = None
    if fd and fd["time"] != tday:  # tiles and legend must show the same day: use the cached grid's day if published
        tday2 = A.tile_day(lay, fd["time"])
        tday = tday2 if tday2 == fd["time"] else tday
        if tday != fd["time"]:
            fd = None
    url = A.tile_url_styled(lay, tday, fd["vmin"], fd["vmax"]) if fd else A.tile_url(lay, tday)
    if not url:
        return None
    add_tiles(m, url, f"{tr(L['title'])} ({tday})", opacity=opacity)
    if tday != day:
        msgs.append(day_note(L["title"], day, tday))
    if fd:
        return dict(fd, origin=tr("{origin}, Copernicus map tiles", origin=tr(fd["origin"])))
    return dict(title=L["title"], unit=L["unit"], origin=L["origin"], service_colours=True, time=tday)


def day_note(title: str, asked: str, got: str) -> str:
    """'Sea surface temperature: 24 Nov not published yet, showing 23 Nov.' (or 'nearest day' for the past)."""
    a, g = pd.Timestamp(asked), pd.Timestamp(got)
    if g < a:
        return tr("{title}: {a} not published yet, showing {g}, the latest day.", title=tr(title), a=dt(a, "%d %b"),
                  g=dt(g, "%d %b"))
    return tr("{title}: no data for {a}, showing the nearest day, {g}.", title=tr(title), a=dt(a, "%d %b"),
              g=dt(g, "%d %b"))


DEPTH_STOPS = [0, 10, 20, 50, 100, 200, 500, 1000, 2000]  # m; the shelf gets most of the ramp, deeper = last colour


def _depth_colours() -> list[str]:
    import matplotlib
    cm = A.colormap("cmo.deep")
    return [matplotlib.colors.to_hex(cm(i / (len(DEPTH_STOPS) - 1))) for i in range(len(DEPTH_STOPS))]


def add_bathy_colour(m):
    """EMODnet DTM mean depth drawn with the cmocean 'deep' ramp (sent to the EMODnet GeoServer as SLD_BODY):
    piecewise linear between DEPTH_STOPS, land transparent. depth_legend_html() draws the same stops."""
    try:
        from marinekit.sources import emodnet_layers as el
        d = el.wms_tile_layer("bathymetry_colour")
        cols = _depth_colours()
        entries = '<ColorMapEntry color="#000000" quantity="0.1" opacity="0"/>' + "".join(
            f'<ColorMapEntry color="{c}" quantity="{-z}" opacity="1"/>' for z, c in zip(DEPTH_STOPS, cols))
        entries = "".join(sorted(entries.replace("/>", "/>|").split("|")[:-1],
                                 key=lambda e: float(e.split('quantity="')[1].split('"')[0])))
        sld = ('<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" '
               'xmlns:ogc="http://www.opengis.net/ogc"><NamedLayer><Name>emodnet:mean</Name><UserStyle>'
               '<FeatureTypeStyle><Rule><RasterSymbolizer><ColorMap type="ramp">' + entries +
               '</ColorMap></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer>'
               '</StyledLayerDescriptor>')
        w = folium.raster_layers.WmsTileLayer(url=d["url"], layers="emodnet:mean", fmt="image/png", transparent=True,
                                              attr=d["attr"], name=tr("Depth (EMODnet DTM)"), overlay=True, opacity=0.85,
                                              version=d["version"])
        w.options["SLD_BODY"] = sld  # set directly: folium would rename the keyword to 'sldBody'
        w.add_to(m)
    except Exception as ex:
        log.info("bathy colour: %s", ex)


def depth_legend_html() -> str:
    """Legend for add_bathy_colour: the same stops, evenly spaced (the ramp is linear between them)."""
    t = tokens()
    cols = _depth_colours()
    n = len(DEPTH_STOPS) - 1
    grad = ", ".join(f"{c} {100 * i / n:.1f}%" for i, c in enumerate(cols))
    show = {0: "0", 50: "50", 100: "100", 200: "200", 2000: "2000+"}  # at their stop positions on the ramp
    ticks = "".join(
        f"<span style='position:absolute;left:{100 * i / n:.1f}%;transform:translateX("
        f"{'0' if i == 0 else ('-100%' if i == n else '-50%')})'>{show[z]}</span>"
        for i, z in enumerate(DEPTH_STOPS) if z in show)
    marks = "".join(f"<span style='position:absolute;left:{100 * i / n:.1f}%;top:0;width:1px;height:4px;"
                    f"background:{t['muted']}'></span>" for i, z in enumerate(DEPTH_STOPS) if z in show)
    return (f"<details open class='bsv-legend' style='position:absolute;bottom:26px;right:10px;z-index:9999;"
            f"background:{t['overlay']};color:{t['text']};padding:6px 12px 8px 12px;border-radius:4px;"
            f"border:1px solid {t['ctrl']};font:12px/1.35 {FONT_UI};max-width:320px'>"
            f"<summary style='cursor:pointer;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;"
            f"color:{t['muted']}'>{_summary(0)}</summary>"
            f"<span style='display:block;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:{t['muted']};"
            f"margin:8px 0 4px 0'>{esc(tr('Depth, m'))} &middot; EMODnet DTM</span>"
            f"<div style='height:8px;width:290px;background:linear-gradient(to right,{grad});opacity:0.85'></div>"
            f"<div style='position:relative;height:4px;width:290px'>{marks}</div>"
            f"<div style='position:relative;height:16px;width:290px;font-family:{FONT_NUM};font-size:12px'>{ticks}</div>"
            f"<div style='font-size:10.5px;color:{t['muted']}'>"
            + esc(tr("Scale stretched for the shelf (0-200 m). Lines: depth contours. Needs the internet "
                     "(EMODnet map service).")) + "</div></details>")


def add_bathy(m):
    try:
        from marinekit.sources import emodnet_layers as el
        d = el.wms_tile_layer("depth_contours")
        folium.raster_layers.WmsTileLayer(url=d["url"], layers=d["layers"], fmt="image/png", transparent=True,
                                          attr=d["attr"], name=tr("Depth contours (EMODnet)"), overlay=True,
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
        f["properties"]["label"] = tr("{n} of 5 sectors overlap ({season})", n=n, season=tr(season))
    folium.GeoJson(gj, name=tr("Pressure overlap ({season})", season=tr(season)), style_function=style,
                   zoom_on_click=False,
                   tooltip=folium.GeoJsonTooltip(["label"], labels=False)).add_to(m)


def add_overlap_soft(m, gj: dict, season: str, stamp: tuple, hatched: bool = False):
    """Soft overlap (viewer.softzones): a smooth 0-5 image in the overlap ramp, thin lines where the count reaches
    1, 2 and 3, and the original overlap polygons kept invisible on top, so hover still gives the exact count of
    the 500 m grid."""
    from viewer import softzones as SZ
    t = tokens()
    img = SZ.overlap_image(season, stamp)
    folium.map.CustomPane("softoverlap", z_index=390, pointer_events=False).add_to(m)
    folium.raster_layers.ImageOverlay(image=img["url"], bounds=img["bounds"], opacity=0.6 if hatched else 0.95,
                                      name=tr("Pressure overlap, soft edges ({season})", season=tr(season)),
                                      interactive=False,
                                      pane="softoverlap").add_to(m)
    weight, alpha = {1: 0.6, 2: 1.0, 3: 1.5}, {1: 0.3, 2: 0.55, 3: 0.8}
    lines = SZ.contours(season, stamp)
    for f in lines["features"]:  # labels translated here, outside the cached function
        f["properties"]["label"] = tr(f["properties"]["label"])
    folium.GeoJson(lines, name=tr("Overlap lines (1, 2, 3 sectors)"), zoom_on_click=False,
                   style_function=lambda f: {"color": t["text"], "weight": weight.get(f["properties"]["k"], 1.0),
                                             "opacity": alpha.get(f["properties"]["k"], 0.5)},
                   tooltip=folium.GeoJsonTooltip(["label"], labels=False)).add_to(m)
    for f in gj["features"]:
        n = int(f["properties"]["n"])
        f["properties"]["label"] = tr("{n} of 5 sectors overlap here ({season}, 500 m grid)", n=n, season=tr(season))
    folium.GeoJson(gj, name=tr("Exact count on hover"), control=False, zoom_on_click=False,
                   style_function=lambda f: {"fillColor": "#000000", "fillOpacity": 0.0, "weight": 0, "opacity": 0},
                   tooltip=folium.GeoJsonTooltip(["label"], labels=False)).add_to(m)


def add_zones_soft(m, gj: dict, season: str, stamp: tuple, only_sector: str | None = None):
    """Soft sector zones: each sector's zones as a fading image in its colour (wider fade for assumed locations),
    with the invisible polygons on top for the tooltips and a dashed outline for assumed zones."""
    from viewer import softzones as SZ
    folium.map.CustomPane("softzones", z_index=395, pointer_events=False).add_to(m)  # tint on top of the overlap
    for k in SECTOR:
        if only_sector and k != only_sector:
            continue
        img = SZ.zone_image(k, season, stamp)
        if img:
            folium.raster_layers.ImageOverlay(image=img["url"], bounds=img["bounds"], opacity=1.0, interactive=False,
                                              name=tr("{sector} zones, soft", sector=tr(SECTOR[k][0])),
                                              pane="softzones").add_to(m)
    fg = folium.FeatureGroup(name=tr("Sector zones (outlines of assumed ones)")).add_to(m)
    for f in gj["features"]:
        p = f["properties"]
        if only_sector and p["sector"] != only_sector:
            continue
        if season == "winter" and str(p.get("season")) == "summer":
            continue
        lab, col = SECTOR.get(p["sector"], (p["sector"], "#555"))
        dashed = str(p.get("confidence")) == "assumed"
        buf = p.get("buffer_m")
        tip = _zone_tip(lab, p, buf)
        folium.GeoJson(f, style_function=lambda _f, col=col, dashed=dashed: {
            "color": col, "weight": 1.2 if dashed else 0, "opacity": 0.85 if dashed else 0, "fillColor": col,
            "fillOpacity": 0.0, "dashArray": "6 5" if dashed else None},
            tooltip=folium.Tooltip(tip), zoom_on_click=False).add_to(fg)


def _zone_tip(lab, p, buf) -> str:
    """Zone hover: sector, activity, buffer (marinekit's buffer_label, e.g. '300 m (law)' or 'AIS density cells,
    no buffer'), confidence."""
    blab = p.get("buffer_label")
    if not blab and buf == buf and buf is not None:
        blab = f"{buf:.0f} m ({p.get('buffer_basis')})" if p.get("buffer_basis") else f"{buf:.0f} m"
    if not blab:
        return f"<b>{esc(tr(lab))}</b>"
    return (f"<b>{esc(tr(lab))}</b><br>{esc(data(p.get('activity') or ''))}<br>"
            f"{esc(tr('buffer'))}: {esc(num(data(str(blab))))}<br>"
            f"{esc(tr('confidence'))}: {esc(tr(str(p.get('confidence'))))}")


def add_zones(m, gj: dict, season: str, only_sector: str | None = None):
    fg = folium.FeatureGroup(name=tr("Sector zones")).add_to(m)
    for f in gj["features"]:
        p = f["properties"]
        if only_sector and p["sector"] != only_sector:
            continue
        if season == "winter" and str(p.get("season")) == "summer":
            continue
        lab, col = SECTOR.get(p["sector"], (p["sector"], "#555"))
        dashed = str(p.get("confidence")) == "assumed"
        buf = p.get("buffer_m")
        tip = _zone_tip(lab, p, buf)
        folium.GeoJson(f, style_function=lambda _f, col=col, dashed=dashed: {
            "color": col, "weight": 1.6, "fillColor": col, "fillOpacity": 0.06, "dashArray": "6 5" if dashed else None},
            tooltip=folium.Tooltip(tip), zoom_on_click=False).add_to(fg)


def add_features(m, gj: dict, season: str, only_sector: str | None = None, soft: bool = False):
    """Activities: points, lines and areas. With soft edges the areas are shown by the soft zones already, so their
    polygons stay invisible (hover and click still work), except the dashed outline of assumed ones; several are
    built from 1 km grid cells (shipping lanes, fishing grounds) and would bring the hard squares back."""
    fg = folium.FeatureGroup(name=tr("Sector activities")).add_to(m)
    for f in gj["features"]:
        p = f["properties"]
        if only_sector and p["sector"] != only_sector:
            continue
        if season == "winter" and str(p.get("season")) == "summer":
            continue
        lab, col = SECTOR.get(p["sector"], (p["sector"], "#555"))
        conf = str(p.get("confidence") or "")
        src = data(str(p.get("source") or ""))
        tip = (f"<b>{esc(data(p.get('name') or p.get('activity')))}</b><br>{esc(tr(lab))}: {esc(data(p.get('activity')))}<br>"
               f"{esc(tr('confidence'))}: {esc(tr(conf))}<br><span style='color:#666'>{esc(src[:90])}</span>")
        url = str(p.get("source_url") or "")
        pop = folium.Popup(tip + (f"<br><a href='{esc(url)}' target='_blank' rel='noopener'>{esc(tr('open source'))}</a>"
                                  if url.startswith("http") else ""), max_width=320)
        g = f.get("geometry") or {}
        if g.get("type") == "Point":
            x, y = g["coordinates"][:2]
            folium.CircleMarker([y, x], radius=3.5, color=col, weight=1.5 if conf != "assumed" else 1,
                                fill=conf != "assumed", fill_opacity=0.9, dash_array="2 2" if conf == "assumed" else None,
                                tooltip=folium.Tooltip(tip), popup=pop).add_to(fg)
        else:
            area = g.get("type") in ("Polygon", "MultiPolygon")
            hide = soft and area
            folium.GeoJson(f, style_function=lambda _f, col=col, conf=conf, hide=hide: {
                "color": col, "weight": (1.2 if conf == "assumed" else 0) if hide else 2, "fillColor": col,
                "opacity": (0.85 if conf == "assumed" else 0) if hide else 1,
                "dashArray": "4 4" if conf == "assumed" else None,
                "fillOpacity": 0.0 if (conf == "assumed" or hide) else 0.25},
                tooltip=folium.Tooltip(tip), popup=pop, zoom_on_click=False).add_to(fg)


def add_natura(m, gj: dict | None):
    if not gj:
        return
    folium.GeoJson(gj, name="Natura 2000", style_function=lambda f: {
        "color": "#1B7F3B", "weight": 1.4, "fillColor": "#1B7F3B", "fillOpacity": 0.05, "dashArray": "3 3"},
        tooltip=folium.GeoJsonTooltip(["sitename", "sitecode"], aliases=["Natura 2000", tr("Code")]),
        zoom_on_click=False).add_to(m)


PTYPE_COLOR = {"Mooring": OI["blue"], "Tide Gauge": OI["sky"], "Gliders": OI["purple"], "Drifting Buoys": OI["purple"]}


def add_platforms(m, p: pd.DataFrame, detail: bool):
    fg = folium.FeatureGroup(name=tr("In-situ platforms")).add_to(m)
    for _, r in p.iterrows():
        trust = r.trust
        col = PTYPE_COLOR.get(r.type, OI["blue"])
        grey = trust in ("under_qc", "context") or not r.recent
        if grey:
            col = "#9AA3AD"
        params = ", ".join(r.canonical[:8]) if isinstance(r.canonical, list) else ""
        status = tr({"under_qc": "under QC (not trusted yet)", "context": "context only",
                     "good": "trusted", "not_assessed": "not assessed"}[trust])
        last = dt(r.time_end, "%d %b %Y") if pd.notna(r.time_end) else tr("unknown")
        tip = (f"<b>{esc(r['name'])}</b> ({esc(r.id)})<br>{esc(tr(r.type))} - {esc(tr('last data'))} {last}<br>"
               f"{esc(tr('status'))}: {status}<br>{esc(params)}")
        if detail:
            tip += f"<br><span style='color:#666'>{esc(tr(r.trust_note))}</span>"
        folium.CircleMarker([r.lat, r.lon], radius=6 if r.recent else 4.5, color="#1C2430" if not grey else "#9AA3AD",
                            weight=1.2, fill=True, fill_color=col, fill_opacity=0.95 if not grey else 0.5,
                            tooltip=folium.Tooltip(tip)).add_to(fg)


def _place(name):
    """Viewer-made place names translated (shell.place_name); real names pass through."""
    try:
        from viewer.shell import place_name
        return place_name(name)
    except Exception:
        return name


def add_selection(m, sel: dict | None):
    if not sel:
        return
    folium.CircleMarker([sel["lat"], sel["lon"]], radius=9, color="#000", weight=2.5, fill=False,
                        tooltip=tr("Selected: {name}", name=esc(_place(sel["name"])))).add_to(m)
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
    return num(f"{x:.2f}" if abs(x) < 1 else (f"{x:.1f}" if abs(x) < 20 else f"{x:.0f}"))


def _summary(n_notes: int) -> str:
    """Fold control label; when folded it says how many notes the legend holds, so they are not missed."""
    extra = (" &middot; " + esc(tr("{n} notes" if n_notes > 1 else "{n} note", n=n_notes))) if n_notes else ""
    return (f"<span class='lg-open'>{esc(tr('Hide legend'))}</span>"
            f"<span class='lg-closed'>{esc(tr('Legend'))}{extra}</span>")


def notes_html(notes: list[str] | None) -> str:
    """Map notes (nearest available day, layer caveats) as small lines at the bottom of the legend."""
    if not notes:
        return ""
    t = tokens()
    rows = "".join(f"<div style='margin:3px 0 0 0'>{esc(n)}</div>" for n in dict.fromkeys(notes))
    return (f"<div style='margin-top:8px;padding-top:6px;border-top:1px solid {t['ctrl']};font-size:11px;"
            f"line-height:1.35;color:{t['sub']}'>{rows}</div>")


def notes_slot(slot, msgs: list[str] | None):
    """Map notes that found no legend: short muted lines in the page's map-tools box (never over the timeline)."""
    if msgs:
        slot.markdown("<div class='bsv-mapnote'>" + "".join(f"<div>{esc(x)}</div>" for x in dict.fromkeys(msgs)) +
                      "</div>", unsafe_allow_html=True)


def legend_html(fd: dict | None, layers: set, season: str, detail: bool, levels: list | None = None,
                hatched: bool = False, bar_opacity: float = 1.0, notes: list[str] | None = None,
                edges: str = "sharp") -> str:
    """Compact themed legend (flat panel, hairline border, 4 px corners), collapsible and height-capped.
    notes: short map notes shown at the bottom (they used to float over the map and the timeline)."""
    t = tokens()
    lab = (f"font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:{t['muted']};"
           "display:block;margin:8px 0 4px 0")
    num = f"font-family:{FONT_NUM};font-size:12.5px"
    row = "display:flex;align-items:center;gap:7px;margin:2px 0"
    parts = []
    if fd and fd.get("service_colours"):
        parts.append(f"<span style='{lab};margin-top:2px'>{esc(tr(fd['title']))} {esc(fd['unit'])} &middot; "
                     f"{esc(tr(fd['origin']))}</span><div style='font-size:11px;max-width:220px'>"
                     + esc(tr("Copernicus map tiles in the service's own colours and range (the grid is not in the "
                              "cache, so the viewer cannot set them).")) + "</div>")
    elif fd:
        grad = ", ".join(fd["colors"])
        vmin, vmax = fd["vmin"], fd["vmax"]

        def frac(x):
            if fd["log"]:
                return (np.log10(x) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin))
            return (x - vmin) / (vmax - vmin)
        ticks = "".join(
            f"<span style='position:absolute;left:{100 * frac(x):.2f}%;transform:translateX("
            f"{'0' if frac(x) < 0.02 else ('-100%' if frac(x) > 0.98 else '-50%')})'>{_fmt(x)}</span>"
            for x in (fd.get("ticks") or _ticks(fd)) if vmin <= x <= vmax)
        marks = "".join(f"<span style='position:absolute;left:{100 * frac(x):.2f}%;top:0;width:1px;height:4px;"
                        f"background:{t['muted']}'></span>" for x in (fd.get("ticks") or []) if vmin <= x <= vmax)
        src = (f"{tr(fd['origin'])}, {fd['time']}" + (f", {fd['dataset']}" if detail else "")
               + (", " + tr("log scale") if fd["log"] else ""))
        parts.append(
            f"<span style='{lab};margin-top:2px'>{esc(tr(fd['title']))} {esc(fd['unit'])}</span>"
            f"<div style='height:8px;width:200px;background:linear-gradient(to right,{grad});opacity:{bar_opacity:.2f}'></div>"
            f"<div style='position:relative;height:4px;width:200px'>{marks}</div>"
            f"<div style='position:relative;height:16px;width:200px;{num}'>{ticks}</div>"
            f"<div style='font-size:10.5px;color:{t['muted']}'>{esc(src)}</div>")
    if "overlap" in layers and edges == "soft":
        from viewer import softzones as SZ
        xs, cols, alps = SZ.overlap_ramp()
        stops = ", ".join(f"rgba({int(c[0] * 255)},{int(c[1] * 255)},{int(c[2] * 255)},{max(a, 0.0):.2f}) {100 * x / 5:.0f}%"
                          for x, c, a in zip(xs, cols, alps))
        ticks = "".join(f"<span style='position:absolute;left:{100 * k / 5:.0f}%;transform:translateX("
                        f"{'0' if k == 0 else ('-100%' if k == 5 else '-50%')})'>{k}</span>" for k in range(6))
        line = (f"<span style='display:inline-block;width:22px;border-top:1.2px solid {t['text']};opacity:0.7;"
                "vertical-align:middle'></span>")
        parts.append(f"<span style='{lab}'>{esc(tr('Sectors overlapping, of 5 ({season})', season=tr(season)))}</span>"
                     f"<div style='height:10px;width:200px;background:linear-gradient(to right,{stops});"
                     f"border:1px solid {t['ctrl']}'></div>"
                     f"<div style='position:relative;height:16px;width:200px;{num}'>{ticks}</div>"
                     f"<div style='{row};color:{t['sub']};font-size:11px'>{line}{esc(tr('where 1, 2, 3 sectors begin'))}</div>"
                     f"<div style='font-size:10.5px;color:{t['muted']}'>"
                     f"{esc(tr('Hover for the exact count (500 m grid).'))}</div>")
    elif "overlap" in layers:
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
        parts.append(f"<span style='{lab}'>{esc(tr('Sectors overlapping, of 5 ({season})', season=tr(season)))}</span>"
                     f"<div style='display:flex;flex-wrap:wrap;gap:2px 0'>{cells}</div>")
    if "zones" in layers or "features" in layers:
        sw = ("width:12px;height:12px;background:radial-gradient(circle,{c} 0 35%,transparent 75%)" if edges == "soft"
              else "width:10px;height:10px;border:2px solid {c}")
        rows = "".join(f"<div style='{row}'><span style='{sw.format(c=c)}'></span>{esc(tr(l))}</div>"
                       for k, (l, c) in SECTOR.items())
        parts.append(f"<span style='{lab}'>{esc(tr('Sectors'))}</span>{rows}"
                     f"<div style='{row};color:{t['muted']}'><span style='width:10px;height:10px;"
                     f"border:2px dashed {t['muted']}'></span>{esc(tr('dashed = location assumed'))}</div>")
    if "insitu" in layers:
        parts.append(f"<span style='{lab}'>{esc(tr('In-situ'))}</span>"
                     f"<div style='{row}'><span style='width:9px;height:9px;border-radius:50%;background:{OI['blue']};"
                     f"border:1px solid {t['text']}'></span>{esc(tr('trusted or not assessed'))}</div>"
                     f"<div style='{row}'><span style='width:9px;height:9px;border-radius:50%;background:#9AA3AD'></span>"
                     f"{esc(tr('under QC, context only, or old'))}</div>")
    if "natura" in layers:
        parts.append(f"<div style='{row};margin-top:8px'><span style='width:10px;height:10px;"
                     f"border:1.5px dashed #1B7F3B'></span>{esc(tr('Natura 2000 site'))}</div>")
    if not parts:
        return ""
    notes = list(dict.fromkeys(notes or []))
    return (f"<details open class='bsv-legend' style='position:absolute;bottom:26px;right:10px;z-index:9999;"
            f"background:{t['overlay']};color:{t['text']};padding:6px 12px 8px 12px;border-radius:4px;"
            f"border:1px solid {t['ctrl']};font:12px/1.35 {FONT_UI};max-width:250px'>"
            f"<summary style='cursor:pointer;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;"
            f"color:{t['muted']}'>{_summary(len(notes))}</summary>"
            "<div style='max-height:min(46vh,330px);overflow-y:auto'>" + "".join(parts) + notes_html(notes) +
            "</div></details>")


def build(view: dict, layers: set, day: str, season: str, sel: dict | None, detail: bool, tiles_mode: bool = False,
          only_sector: str | None = None, theme: str | None = None,
          legend: bool = True, extra=None, vec_time=None, notes: list[str] | None = None,
          edges: str = "sharp") -> tuple[folium.Map, dict | None, list[str]]:
    """Return (map, field dict or None, messages not shown on the map). extra(m), if given, adds page-specific
    layers. vec_time: the time step for the waves / currents / wind layers (default: the day at 00:00).
    Map notes (nearest available day, layer caveats, and `notes` from the page) go to the bottom of the legend;
    the returned messages are the ones that had no legend to go in, for the page to show in its own place.
    edges: 'sharp' (500 m cells and polygon outlines) or 'soft' (soft zone edges, viewer.softzones)."""
    msgs = []
    m = base_map(view["lat"], view["lon"], view["zoom"], theme)
    stamp = A._zones_stamp()
    fd = lfd = None
    grid_op = 0.85
    grid = [l for l in layers if l in GRIDDED]
    if grid:
        lay = grid[0]
        grid_op = 0.45 if "overlap" in layers else 0.85
        if tiles_mode:
            lfd = _tiles(m, lay, day, grid_op, msgs)
            if lfd is None:
                msgs.append(tr("Copernicus map tiles could not be reached; showing the local layer instead."))
            elif A.LAYERS[lay].get("note"):
                msgs.append(tr(A.LAYERS[lay]["note"]))
        if not tiles_mode or lfd is None:
            try:
                fd = A.field(lay, day)
            except A.SlowSource:
                fd = None
                msgs.append(tr("{title}: still downloading for {day}; it will appear on the next refresh.",
                               title=tr(A.LAYERS[lay]["title"]), day=dt(day, "%d %b")))
            if A.LAYERS[lay].get("note"):
                msgs.append(tr(A.LAYERS[lay]["note"]))
            if fd:
                add_field(m, fd, opacity=grid_op)
                if fd["time"] != day:
                    msgs.append(day_note(fd["title"], day, fd["time"]))
            elif not tiles_mode:
                lfd = _tiles(m, lay, day, grid_op, msgs)
                if lfd is not None:
                    msgs.append(tr("{title}: the grid could not be downloaded, showing Copernicus map tiles instead "
                                   "(online only).", title=tr(A.LAYERS[lay]["title"])))
    if "bathy_colour" in layers:
        add_bathy_colour(m)
    if "bathy" in layers or "bathy_colour" in layers:
        add_bathy(m)
    levels = None
    soft = edges == "soft"
    if soft and ("overlap" in layers or "zones" in layers):
        from viewer import softzones as SZ
        notes = list(notes or []) + [tr(SZ.NOTE)]
    if "zones" in layers and soft:  # under the overlap, as in the sharp map's drawing order
        add_zones_soft(m, A.sector_zones(stamp), season, stamp, only_sector)
    if "overlap" in layers:
        ogj = A.overlap_geojson(season, stamp)
        levels = sorted({int(f["properties"]["n"]) for f in ogj["features"]})
        if soft:
            add_overlap_soft(m, ogj, season, stamp, hatched=bool(grid))
        else:
            add_overlap(m, ogj, season, hatched=bool(grid))
    if "zones" in layers and not soft:
        add_zones(m, A.sector_zones(stamp), season, only_sector)
    if "features" in layers:
        add_features(m, A.sector_features(stamp), season, only_sector, soft=soft)
    if "natura" in layers:
        add_natura(m, A.natura())
    for lid, kind in VECTOR.items():
        if lid in layers:
            vv = A.vectorviz()
            if vv is None or not hasattr(vv, "field_layer"):
                msgs.append(tr("Waves, currents and wind: the vector module is not ready yet."))
                continue
            try:
                ds = vv.load_field(kind, A.BBOX_RO, vec_time or day) if hasattr(vv, "load_field") else None
                try:
                    vv.field_layer(m, ds, kind, vec_time or day, legend=legend,
                                   legend_theme=dict(tokens(theme), font=FONT_UI))
                except TypeError:  # older vectorviz without legend_theme
                    vv.field_layer(m, ds, kind, vec_time or day)
            except Exception as ex:
                msgs.append(tr("{kind} layer failed: {err}", kind=tr(kind.capitalize()), err=str(ex)[:120]))
    if "insitu" in layers:
        add_platforms(m, A.platforms(), detail)
    add_selection(m, sel)
    if extra is not None:  # page-specific layers go in before the layer control, or folium never adds them
        extra(m)
    all_notes = list(notes or []) + msgs
    lg = legend_html(fd or lfd, layers, season, detail, levels, hatched=bool(grid),
                     bar_opacity=FIELD_ALPHA * grid_op, notes=all_notes, edges=edges) if legend else ""
    if lg:
        m.get_root().html.add_child(folium.Element(lg))
        msgs = []
    else:
        msgs = all_notes
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m, fd, msgs
