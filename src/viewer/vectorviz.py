"""Combined vector visualisation: waves, currents and wind in one view (workstream V).

One map layer and one chart per quantity, each showing magnitude, direction and (for waves) period together:

* map  (folium): magnitude as a colour field (perceptually uniform colormap + colorbar with units),
                 direction as arrows on a regular lattice thinned per zoom (readable at every zoom), and for waves
                 arrow length = peak period (short = wind sea, long = swell). Click a spot for the values.
* chart (plotly): magnitude as line + area over time, arrows on the line every N hours pointing where the
                 water / air goes (up = north); for waves, arrow size = peak period. Hover shows all values.

Direction conventions (checked, see docs/viz/README.md):
* Copernicus wave VMDR and Open-Meteo wave_direction: direction waves come FROM, degrees clockwise from north.
  Arrows add 180 deg so they point where the waves GO.
* Copernicus currents u/v and Open-Meteo current_direction: direction the water flows TO. Arrows use it as is.
* Wind (Open-Meteo / ERA5 wind_direction_10m): direction the wind blows FROM. Arrows add 180 deg.
Every arrow in this module points where the water or air is going. Legends say so.

Public API (interface V -> U in docs/plan/WORKFLOW.md):
    load_field(kind, bbox=BBOX_RO, time=None)               -> xarray.Dataset
    load_point(kind, lat, lon, start, end, source="auto")    -> pandas.DataFrame
    field_layer(m, ds, kind=None, time=None, ...)           -> folium.FeatureGroup (already added to m)
    point_chart(df, kind, every_hours=None, theme="light")   -> plotly.graph_objects.Figure
    combined_chart({"waves": df, "currents": df, "wind": df}) -> plotly Figure, three stacked rows, shared time
kind is one of "waves", "currents", "wind".

Wind: the source modules have no gridded wind product, so load_field("wind") samples Open-Meteo/ERA5 wind at
the reference STATIONS inside the bbox (one cached request each). field_layer draws those as coloured discs with
arrows; there is no wind colour field.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from marinekit.sources import BBOX_RO, STATIONS  # noqa: E402

KINDS = ("waves", "currents", "wind")

# Okabe-Ito
OKABE_ITO = {"blue": "#0072B2", "green": "#009E73", "orange": "#E69F00", "vermillion": "#D55E00",
             "sky": "#56B4E9", "purple": "#CC79A7", "yellow": "#F0E442", "black": "#000000"}

SPEC = {
    "waves": dict(
        label="Waves", mag="wave_height", mag_label="Significant wave height", unit="m",
        vmin=0.0, vmax=4.0, cmap="viridis", line=OKABE_ITO["blue"],
        period="wave_period", period_label="Peak period", dir_from="wave_dir",
        convention="Arrows point where the waves travel to. The model gives the direction waves come from; "
                   "180 degrees is added.",
        source="Copernicus Marine BLKSEA_ANALYSISFORECAST_WAV_007_003 (hourly, 2.5 km)",
    ),
    "currents": dict(
        label="Surface currents", mag="current_speed", mag_label="Current speed", unit="m/s",
        vmin=0.0, vmax=0.5, cmap="plasma", line=OKABE_ITO["green"], period=None, dir_from=None,
        convention="Arrows point where the water flows to.",
        source="Copernicus Marine BLKSEA_ANALYSISFORECAST_PHY_007_001 (daily mean, surface, 2.5 km)",
    ),
    "wind": dict(
        label="Wind at 10 m", mag="wind_speed", mag_label="Wind speed", unit="m/s",
        vmin=0.0, vmax=20.0, cmap="cividis", line=OKABE_ITO["orange"], period=None, dir_from="wind_dir",
        convention="Arrows point where the wind blows to. The source gives the direction wind comes from; "
                   "180 degrees is added.",
        source="ERA5 reanalysis / forecast via Open-Meteo (hourly, about 25 km)",
    ),
}

# wave arrow length on the map (px) as a function of peak period (s)
_WAVE_LEN = dict(a=3.2, b=4.0, lo=10.0, hi=44.0)
# and on the charts
_CHART_LEN = dict(a=2.6, b=4.0, lo=10.0, hi=34.0)
_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg) -> str:
    """16-point compass name for a direction in degrees (clockwise from north)."""
    if deg is None or not np.isfinite(deg):
        return ""
    return _COMPASS[int((float(deg) % 360) / 22.5 + 0.5) % 16]


def _wave_len_px(tp):
    tp = np.asarray(tp, dtype=float)
    return np.clip(_WAVE_LEN["a"] * tp + _WAVE_LEN["b"], _WAVE_LEN["lo"], _WAVE_LEN["hi"])


def _check_kind(kind: str) -> str:
    if kind not in SPEC:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    return kind


def _now() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None)


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


# =============================================================================================
# Loading
# =============================================================================================
def load_field(kind: str, bbox=BBOX_RO, time=None) -> xr.Dataset:
    """One time step of a vector field over bbox = (lon_min, lat_min, lon_max, lat_max).

    time: None = latest step up to now (waves: current hour; currents: today's daily mean).
    Returns an xarray.Dataset with dims (lat, lon) and variables
      waves:    wave_height (m), wave_period (s, peak), wave_dir (deg, FROM), dir_to (deg, TO)
      currents: current_u, current_v, current_speed (m/s), dir_to (deg, TO)
    and for wind (no gridded source available) dims (station,) with coords lat, lon, name and
      wind_speed (m/s), wind_dir (deg, FROM), dir_to (deg, TO).
    attrs: kind, time (ISO), source, citation, convention.
    """
    _check_kind(kind)
    from marinekit.sources import copernicus as cp

    if kind == "waves":
        t = _ts(time) if time is not None else _now().floor("h")
        parts = {v: cp.fetch_field("wav", bbox, t, variable=v) for v in ("wave_height", "wave_period", "wave_dir")}
        ref = parts["wave_height"]
        ds = xr.Dataset({k: v.isel(time=0, drop=True).astype("float32") for k, v in parts.items()})
        ds["dir_to"] = (ds["wave_dir"] + 180.0) % 360.0
        tt = pd.Timestamp(ref.time.values[0])
        cit = ref.attrs.get("citation", "")
    elif kind == "currents":
        t = (_ts(time) if time is not None else _now()).normalize()
        u = cp.fetch_field("phy_cur", bbox, t, variable="current_u")
        v = cp.fetch_field("phy_cur", bbox, t, variable="current_v")
        ds = xr.Dataset({"current_u": u.isel(time=0, drop=True).astype("float32"),
                         "current_v": v.isel(time=0, drop=True).astype("float32")})
        ds = ds.drop_vars([c for c in ("depth",) if c in ds.coords])
        ds["current_speed"] = np.hypot(ds.current_u, ds.current_v)
        ds["dir_to"] = (np.degrees(np.arctan2(ds.current_u, ds.current_v)) + 360.0) % 360.0
        tt = pd.Timestamp(u.time.values[0])
        cit = u.attrs.get("citation", "")
    else:
        ds, tt = _wind_stations(bbox, time)
        cit = "Open-Meteo.com (CC BY 4.0); ERA5 (Hersbach et al. 2020)"
    ds.attrs = dict(kind=kind, time=tt.isoformat(), source=SPEC[kind]["source"], citation=cit,
                    convention=SPEC[kind]["convention"])
    return ds


def _wind_stations(bbox, time) -> tuple[xr.Dataset, pd.Timestamp]:
    from marinekit.sources import open_data as od

    t = _ts(time) if time is not None else _now().floor("h")
    lon0, lat0, lon1, lat1 = bbox
    rows = []
    for name, (la, lo) in STATIONS.items():
        if not (lat0 <= la <= lat1 and lon0 <= lo <= lon1):
            continue
        df = od.marine_weather(la, lo, t.normalize(), t.normalize())
        df = df[["wind_speed", "wind_dir"]].dropna()
        if df.empty:
            continue
        i = int(np.argmin(np.abs((df.index - t).total_seconds())))
        rows.append(dict(name=name, lat=la, lon=lo, wind_speed=float(df.wind_speed.iloc[i]),
                         wind_dir=float(df.wind_dir.iloc[i]), time=df.index[i]))
    if not rows:
        raise ValueError("no wind data for the reference stations in this bbox")
    r = pd.DataFrame(rows)
    ds = xr.Dataset(
        {"wind_speed": ("station", r.wind_speed.values), "wind_dir": ("station", r.wind_dir.values)},
        coords={"lat": ("station", r.lat.values), "lon": ("station", r.lon.values), "name": ("station", r.name.values)},
    )
    ds["dir_to"] = (ds.wind_dir + 180.0) % 360.0
    return ds, pd.Timestamp(r.time.iloc[0])


def load_point(kind: str, lat: float, lon: float, start, end, source: str = "auto") -> pd.DataFrame:
    """Time series at a point. Keep start..end to 7-14 days.

    source: "auto" | "copernicus" | "open-meteo". auto = Copernicus for waves (hourly) and currents (daily mean),
    Open-Meteo/ERA5 for wind (the only wind source). "open-meteo" gives hourly currents (SMOC) and waves (MFWAM).
    Columns (canonical names): magnitude column (wave_height / current_speed / wind_speed), dir_to (deg, TO),
    plus wave_period and wave_dir (FROM) for waves, current_u/current_v for currents, wind_dir (FROM) for wind.
    df.attrs: source metadata + kind, convention, lat, lon.
    """
    _check_kind(kind)
    from marinekit.sources import copernicus as cp
    from marinekit.sources import open_data as od

    start, end = _ts(start), _ts(end)
    if source == "auto":
        source = "open-meteo" if kind == "wind" else "copernicus"
    if kind == "wind" and source != "open-meteo":
        raise ValueError("wind is only available from open-meteo (ERA5)")

    if source == "copernicus":
        if kind == "waves":
            df = cp.fetch_timeseries("wav", lat, lon, start, end)
            df["dir_to"] = (df["wave_dir"] + 180.0) % 360.0
        else:
            df = cp.fetch_timeseries("phy_cur", lat, lon, start.normalize(), end)
            df["current_speed"] = np.hypot(df.current_u, df.current_v)
            df["dir_to"] = (np.degrees(np.arctan2(df.current_u, df.current_v)) + 360.0) % 360.0
        attrs = dict(df.attrs)
    else:
        mw = od.marine_weather(lat, lon, start, end)
        attrs = dict(mw.attrs)
        if kind == "waves":
            df = mw[["wave_height", "wave_period", "wave_dir"]].dropna(subset=["wave_height"]).copy()
            df["dir_to"] = (df["wave_dir"] + 180.0) % 360.0
            attrs["source_note"] = "Open-Meteo marine: wave_period is the MEAN period, not peak"
        elif kind == "currents":
            df = mw[["current_speed", "current_dir", "current_u", "current_v"]].dropna(subset=["current_speed"]).copy()
            df["dir_to"] = df["current_dir"]  # already 'towards'
        else:
            df = mw[["wind_speed", "wind_dir"]].dropna().copy()
            df["dir_to"] = (df["wind_dir"] + 180.0) % 360.0
        df = df.loc[start:end]
    attrs.update(kind=kind, convention=SPEC[kind]["convention"], lat=lat, lon=lon, point_source=source)
    df.attrs = attrs
    return df


# =============================================================================================
# Map layer (folium)
# =============================================================================================
def _cmap(name: str):
    import matplotlib

    return matplotlib.colormaps[name]


def _hex(rgba) -> str:
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgba[:3])


def _png_data_url(rgba: np.ndarray) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG", optimize=False, compress_level=3)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _merc_y(lat):
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _field_image(da: xr.DataArray, vmin, vmax, cmap, opacity, rows_per_cell: int = 3):
    """RGBA image of a regular lat/lon grid, rows resampled so it sits right on a Web Mercator map.
    Returns (data_url, bounds [[s, w], [n, e]])."""
    da = da.sortby("lat").sortby("lon")
    lat, lon = da.lat.values.astype(float), da.lon.values.astype(float)
    dlat, dlon = float(np.median(np.diff(lat))), float(np.median(np.diff(lon)))
    s, n = lat[0] - dlat / 2, lat[-1] + dlat / 2
    w, e = lon[0] - dlon / 2, lon[-1] + dlon / 2
    nrow = len(lat) * rows_per_cell
    y = np.linspace(_merc_y(n), _merc_y(s), nrow)  # top row first
    lat_rows = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    src = np.clip(np.round((lat_rows - lat[0]) / dlat).astype(int), 0, len(lat) - 1)
    z = da.values[src, :]
    norm = np.clip((z - vmin) / (vmax - vmin), 0, 1)
    rgba = (cmap(np.nan_to_num(norm)) * 255).astype(np.uint8)
    rgba[..., 3] = np.where(np.isfinite(z), int(opacity * 255), 0)
    return _png_data_url(rgba), [[s, w], [n, e]]


def _arrow_svg(length: float, angle_to: float = 90.0, h: int = 18) -> str:
    """Inline SVG of one legend arrow in the same style as the map arrows (white with dark outline)."""
    L = float(length)
    W = int(L + 8)
    x0, x1, yc = 4, 4 + L, h / 2
    hl = max(5.0, 0.32 * L)
    path = f"M{x0},{yc} L{x1},{yc} M{x1 - hl},{yc - hl * 0.55} L{x1},{yc} L{x1 - hl},{yc + hl * 0.55}"
    return (f'<svg width="{W}" height="{h}" style="vertical-align:middle">'
            f'<rect x="0" y="0" width="{W}" height="{h}" rx="3" fill="#5b6f86"/>'
            f'<path d="{path}" stroke="#1a1a1a" stroke-width="4" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="0.85"/>'
            f'<path d="{path}" stroke="#ffffff" stroke-width="1.8" fill="none" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg>')


def legend_html(kind: str, when: str = "", opacity: float = 1.0) -> str:
    """HTML legend: colorbar with units, arrow meaning and, for waves, period examples (3, 6, 10 s)."""
    sp = SPEC[_check_kind(kind)]
    cm = _cmap(sp["cmap"])
    # colours blended on white with the field opacity, so the bar matches what the map shows
    stops = ", ".join(f"{_hex(np.array(cm(x)[:3]) * opacity + (1 - opacity))} {x * 100:.0f}%"
                      for x in np.linspace(0, 1, 9))
    ticks = np.linspace(sp["vmin"], sp["vmax"], 5)
    fmt = (lambda v: f"{v:g}") if sp["vmax"] >= 2 else (lambda v: f"{v:.2g}")
    tick_html = "".join(
        f'<span style="position:absolute;left:{i * 25}%;transform:translateX(-{0 if i == 0 else (100 if i == 4 else 50)}%)">'
        f'{fmt(v)}{"+" if i == 4 else ""}</span>' for i, v in enumerate(ticks))
    parts = [
        f'<div style="font-weight:600;margin-bottom:2px">{sp["label"]}</div>',
        f'<div style="font-size:11px;color:#444;margin-bottom:3px">{sp["mag_label"]} ({sp["unit"]})'
        f'{" - " + when if when else ""}</div>',
        f'<div style="height:10px;width:190px;border-radius:2px;background:linear-gradient(to right, {stops})"></div>',
        f'<div style="position:relative;height:14px;width:190px;font-size:11px;color:#333">{tick_html}</div>',
    ]
    if kind == "waves":
        ex = "".join(f'<div style="display:flex;align-items:center;gap:6px;height:18px">'
                     f'<span style="width:30px;text-align:right">{p} s</span>{_arrow_svg(float(_wave_len_px(p)))}</div>'
                     for p in (3, 6, 10))
        parts.append('<div style="margin-top:4px;font-size:11px">Arrow length = peak period</div>'
                     f'<div style="font-size:11px">{ex}</div>'
                     '<div style="font-size:11px;color:#444">short = wind sea, long = swell</div>')
    elif kind == "currents":
        parts.append('<div style="margin-top:4px;font-size:11px">Dot = slower than 0.02 m/s (no clear direction)</div>')
    elif kind == "wind":
        parts.append('<div style="margin-top:4px;font-size:11px">Disc colour = wind speed at reference points '
                     '(no gridded wind source)</div>')
    parts.append(f'<div style="margin-top:4px;font-size:11px;max-width:200px">{_arrow_svg(22)} '
                 f'{sp["convention"].split(".")[0]}.</div>')
    parts.append('<div style="font-size:10px;color:#666;max-width:200px">Click the sea for values.</div>')
    return ('<div style="background:rgba(255,255,255,0.92);color:#1a1a1a;padding:6px 8px;border-radius:4px;'
            'box-shadow:0 1px 4px rgba(0,0,0,0.3);font:12px/1.3 system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            + "".join(parts) + "</div>")


_JS_LAYER = r"""
if (!L.VectorArrows) {
L.VectorArrows = L.Layer.extend({
  // d: grid mode {lat0, lon0, dlat, dlon, ii, jj, dir, mag, [per], [frm]} or point mode {lat, lon, dir, mag, frm, col, name}
  // o: {spacing, len, disc, unit, label, magLabel, perLabel, lenA, lenB, lenLo, lenHi, still, legend, legendPos}
  initialize: function (d, o) {
    this._d = d; this._o = o; var n = d.dir.length;
    if (!d.lat) { d.lat = new Array(n); d.lon = new Array(n);
      for (var i = 0; i < n; i++) { d.lat[i] = d.lat0 + d.ii[i] * d.dlat; d.lon[i] = d.lon0 + d.jj[i] * d.dlon; } }
  },
  onAdd: function (map) {
    this._map = map;
    if (!map.getPane('vvArrows')) { var p = map.createPane('vvArrows'); p.style.zIndex = 450; p.style.pointerEvents = 'none'; }
    var c = this._c = L.DomUtil.create('canvas', 'leaflet-zoom-hide');
    c.style.position = 'absolute'; c.style.pointerEvents = 'none';
    map.getPane('vvArrows').appendChild(c);
    map.on('moveend zoomend resize viewreset', this._redraw, this);
    map.on('click', this._click, this);
    if (this._o.legend) {
      var html = this._o.legend, ctl = this._leg = L.control({position: this._o.legendPos || 'bottomright'});
      ctl.onAdd = function () { var el = L.DomUtil.create('div', 'vv-legend'); el.innerHTML = html;
        L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el); return el; };
      ctl.addTo(map);
    }
    this._redraw();
  },
  onRemove: function (map) {
    L.DomUtil.remove(this._c);
    map.off('moveend zoomend resize viewreset', this._redraw, this);
    map.off('click', this._click, this);
    if (this._leg) { map.removeControl(this._leg); }
  },
  _len: function (i) {
    var o = this._o, d = this._d;
    if (d.per) { var v = o.lenA * d.per[i] + o.lenB; return Math.max(o.lenLo, Math.min(o.lenHi, v)); }
    return o.len;
  },
  _redraw: function () {
    var map = this._map, d = this._d, o = this._o, size = map.getSize(), c = this._c;
    var dpr = window.devicePixelRatio || 1;
    L.DomUtil.setPosition(c, map.containerPointToLayerPoint([0, 0]));
    c.width = size.x * dpr; c.height = size.y * dpr; c.style.width = size.x + 'px'; c.style.height = size.y + 'px';
    var ctx = c.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, size.x, size.y);
    var stride = 1, n = d.dir.length, i, p, sel = [];
    if (d.ii) {  // regular lattice: every k-th cell, k from the on-screen cell size
      var c0 = map.getCenter(), a = map.latLngToContainerPoint(c0),
          b = map.latLngToContainerPoint([c0.lat, c0.lng + d.dlon]);
      var cellPx = Math.max(0.1, Math.abs(b.x - a.x));
      stride = Math.max(1, Math.ceil(o.spacing / cellPx));
    }
    var b0 = map.getBounds().pad(0.05);
    var placed = [];
    for (i = 0; i < n; i++) {
      if (d.ii && (d.ii[i] % stride || d.jj[i] % stride)) continue;
      if (!b0.contains([d.lat[i], d.lon[i]])) continue;
      if (d.col) {  // points: skip a disc that would overlap one already placed (list order = priority)
        var q = map.latLngToContainerPoint([d.lat[i], d.lon[i]]), clash = false;
        for (var k = 0; k < placed.length; k++) {
          if (Math.pow(q.x - placed[k].x, 2) + Math.pow(q.y - placed[k].y, 2) < Math.pow(2 * o.disc + 4, 2)) { clash = true; break; }
        }
        if (clash) continue;
        placed.push(q);
      }
      sel.push(i);
    }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (var pass = 0; pass < 2; pass++) {
      for (var j = 0; j < sel.length; j++) {
        i = sel[j]; p = map.latLngToContainerPoint([d.lat[i], d.lon[i]]);
        if (pass === 0 && d.col) {
          ctx.beginPath(); ctx.arc(p.x, p.y, o.disc, 0, 2 * Math.PI);
          ctx.fillStyle = d.col[i]; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = '#1a1a1a'; ctx.stroke();
        }
        ctx.strokeStyle = pass === 0 ? 'rgba(26,26,26,0.85)' : '#ffffff';
        ctx.fillStyle = ctx.strokeStyle;
        ctx.lineWidth = pass === 0 ? 4 : 1.8;
        if (o.still && d.mag[i] < o.still) {  // too weak to have a meaningful direction: small dot
          ctx.beginPath(); ctx.arc(p.x, p.y, pass === 0 ? 2.6 : 1.4, 0, 2 * Math.PI); ctx.fill(); continue;
        }
        var L_ = this._len(i), an = d.dir[i] * Math.PI / 180, sx = Math.sin(an), sy = -Math.cos(an);
        var hx = p.x + sx * L_ / 2, hy = p.y + sy * L_ / 2, tx = p.x - sx * L_ / 2, ty = p.y - sy * L_ / 2;
        var hl = Math.max(5, 0.32 * L_), w = 0.55;
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy);
        ctx.moveTo(hx - sx * hl + sy * hl * w, hy - sy * hl - sx * hl * w);
        ctx.lineTo(hx, hy);
        ctx.lineTo(hx - sx * hl - sy * hl * w, hy - sy * hl + sx * hl * w);
        ctx.stroke();
      }
    }
  },
  _compass: function (deg) {
    var n = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
    return n[Math.floor(((deg % 360) + 360) % 360 / 22.5 + 0.5) % 16];
  },
  _text: function (i) {
    var d = this._d, o = this._o, s = '<b>' + o.label + '</b>' + (d.name ? ' - ' + d.name[i] : '');
    s += '<br>' + o.magLabel + ': ' + d.mag[i].toFixed(2) + ' ' + o.unit;
    if (d.per) { var t = d.per[i]; s += '<br>' + o.perLabel + ': ' + t.toFixed(1) + ' s (' +
      (t >= 8 ? 'swell' : (t >= 5 ? 'mixed' : 'wind sea')) + ')'; }
    if (d.frm) { s += '<br>Coming from ' + this._compass(d.frm[i]) + ' (' + Math.round(d.frm[i]) +
      ' deg), going to ' + this._compass(d.dir[i]); }
    else { s += '<br>Flowing to ' + this._compass(d.dir[i]) + ' (' + Math.round(d.dir[i]) + ' deg)'; }
    return s + '<br><span style="color:#666">' + d.lat[i].toFixed(3) + ' N, ' + d.lon[i].toFixed(3) + ' E</span>';
  },
  _click: function (e) {
    var map = this._map, d = this._d, p0 = e.containerPoint, best = -1, bd = 1e9;
    for (var i = 0; i < d.dir.length; i++) {
      if (Math.abs(d.lat[i] - e.latlng.lat) > 0.3 || Math.abs(d.lon[i] - e.latlng.lng) > 0.3) continue;
      var p = map.latLngToContainerPoint([d.lat[i], d.lon[i]]);
      var dd = Math.pow(p.x - p0.x, 2) + Math.pow(p.y - p0.y, 2);
      if (dd < bd) { bd = dd; best = i; }
    }
    var lim = this._o.clickPx || 30;
    if (best < 0 || bd > lim * lim) return;
    L.popup({maxWidth: 280}).setLatLng([d.lat[best], d.lon[best]]).setContent(this._text(best)).openOn(map);
  }
});
}
"""


def _arrow_layer_class():
    import folium
    from branca.element import MacroElement
    from jinja2 import Template

    class VectorArrows(folium.map.Layer):
        _template = Template(
            "{% macro header(this, kwargs) %}{% endmacro %}"
            "{% macro script(this, kwargs) %}" + _JS_LAYER +
            "var {{ this.get_name() }} = new L.VectorArrows({{ this.data }}, {{ this.opts }});\n"
            "{% if this.show %}{{ this.get_name() }}.addTo({{ this._parent.get_name() }});{% endif %}\n"
            "{% endmacro %}")

        def __init__(self, data: dict, opts: dict, name=None, show=True):
            super().__init__(name=name, overlay=True, control=False, show=show)
            self._name = "VectorArrows"
            self.data = json.dumps(data, separators=(",", ":"))
            self.opts = json.dumps(opts, separators=(",", ":"))

    _ = MacroElement
    return VectorArrows


def _fmt(v, nd=2):
    return "n/a" if v is None or not np.isfinite(v) else f"{v:.{nd}f}"


def _r(a, nd):
    """Rounded list for compact JSON."""
    a = np.round(np.asarray(a, dtype=float), nd)
    return a.astype(int).tolist() if nd == 0 else a.tolist()


def field_layer(m, ds: xr.Dataset, kind: str | None = None, time=None, name: str | None = None,
                show: bool = True, opacity: float = 0.75, legend: bool = True, legend_pos: str = "bottomright",
                spacing_px: int | None = None):
    """Add one combined layer (colour field + direction arrows + legend) to folium map m.

    ds: output of load_field (a 'time' dim, if present, is reduced with `time` -> nearest, default first).
    kind: defaults to ds.attrs['kind'].
    Arrows are drawn on a canvas on a regular lattice: every k-th grid cell, with k chosen at each zoom so
    arrows are at least spacing_px apart (default 40 px waves, 30 px currents). Readable from zoom 7 to 13.
    Click on the sea opens a popup with all values. The legend shows and hides with the layer.
    Returns the folium.FeatureGroup (already added to m); put several in one map with folium.LayerControl.
    """
    import folium

    kind = _check_kind(kind or ds.attrs.get("kind"))
    sp = SPEC[kind]
    if "time" in ds.dims:
        ds = ds.sel(time=_ts(time), method="nearest") if time is not None else ds.isel(time=0)
    when = ds.attrs.get("time", "")
    when_txt = pd.Timestamp(when).strftime("%d %b %Y %H:%M UTC") if when else ""
    if kind == "currents" and when:
        when_txt = pd.Timestamp(when).strftime("%d %b %Y") + " daily mean"
    fg = folium.FeatureGroup(name=name or (f"{sp['label']} ({when_txt})" if when_txt else sp["label"]), show=show)
    cm = _cmap(sp["cmap"])
    opts = dict(label=sp["label"], magLabel=sp["mag_label"], unit=sp["unit"], perLabel=sp.get("period_label", ""))

    if "station" in ds.dims:  # wind at points
        mag = ds[sp["mag"]].values
        norm = np.clip((mag - sp["vmin"]) / (sp["vmax"] - sp["vmin"]), 0, 1)
        data = dict(lat=_r(ds.lat.values, 4), lon=_r(ds.lon.values, 4), dir=_r(ds.dir_to.values, 0),
                    mag=_r(mag, 2), frm=_r(ds[sp["dir_from"]].values, 0), col=[_hex(cm(x)) for x in norm],
                    name=[str(x) for x in ds.name.values])
        opts.update(spacing=0, len=20, disc=14, clickPx=24)
    else:
        ds = ds.sortby("lat").sortby("lon")
        url, bounds = _field_image(ds[sp["mag"]], sp["vmin"], sp["vmax"], cm, opacity)
        folium.raster_layers.ImageOverlay(url, bounds=bounds, opacity=1.0, interactive=False, zindex=2,
                                          pixelated=False, name=sp["label"]).add_to(fg)
        lat, lon = ds.lat.values.astype(float), ds.lon.values.astype(float)
        ii, jj = np.meshgrid(np.arange(lat.size), np.arange(lon.size), indexing="ij")
        mag, dto = ds[sp["mag"]].values, ds.dir_to.values
        ok = np.isfinite(mag) & np.isfinite(dto)
        data = dict(lat0=float(lat[0]), lon0=float(lon[0]), dlat=float(np.median(np.diff(lat))),
                    dlon=float(np.median(np.diff(lon))), ii=ii[ok].tolist(), jj=jj[ok].tolist(),
                    dir=_r(dto[ok], 0), mag=_r(mag[ok], 2))
        if kind == "waves":
            data["per"] = _r(ds[sp["period"]].values[ok], 1)
            data["frm"] = _r(ds[sp["dir_from"]].values[ok], 0)
            opts.update(spacing=spacing_px or 40, lenA=_WAVE_LEN["a"], lenB=_WAVE_LEN["b"], lenLo=_WAVE_LEN["lo"],
                        lenHi=_WAVE_LEN["hi"])
        else:
            opts.update(spacing=spacing_px or 30, len=22, still=0.02)
    if legend:
        opts.update(legend=legend_html(kind, when_txt, opacity), legendPos=legend_pos)
    _arrow_layer_class()(data, opts, name=f"{sp['label']} arrows").add_to(fg)
    fg.add_to(m)
    return fg


LIGHT_GRAY = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"


def base_map(bbox=BBOX_RO, zoom_start: int = 8, tiles: str | None = None, **kw):
    """Plain folium map fitted to bbox, a convenience for demos. Default basemap: Esri Light Gray (no key,
    low contrast, so the colour field and arrows stand out). CartoDB tiles now need an API key."""
    import folium

    lon0, lat0, lon1, lat1 = bbox
    m = folium.Map(location=[(lat0 + lat1) / 2, (lon0 + lon1) / 2], zoom_start=zoom_start, control_scale=True,
                   tiles=None, max_zoom=16, **kw)
    if tiles:
        folium.TileLayer(tiles, name="Basemap").add_to(m)
    else:
        folium.TileLayer(LIGHT_GRAY, attr="Esri, HERE, Garmin, OpenStreetMap contributors", name="Basemap (light grey)",
                         max_native_zoom=16, max_zoom=16).add_to(m)
    m.fit_bounds([[lat0, lon0], [lat1, lon1]])
    return m


# =============================================================================================
# Point chart (plotly)
# =============================================================================================
_THEMES = {
    "light": dict(fg="#222222", muted="#666666", grid="rgba(0,0,0,0.08)", bg="#ffffff", arrow="#1a1a1a",
                  outline="#ffffff"),
    "dark": dict(fg="#e6e6e6", muted="#a0a0a0", grid="rgba(255,255,255,0.10)", bg="#0e1117", arrow="#f2f2f2",
                 outline="#0e1117"),
}


def _auto_every(df: pd.DataFrame, target: int = 32) -> int:
    if len(df) < 2:
        return 1
    step_h = max(1.0, pd.Series(df.index).diff().median().total_seconds() / 3600)
    span_h = (df.index[-1] - df.index[0]).total_seconds() / 3600
    raw = max(step_h, span_h / target)
    for nice in (1, 2, 3, 6, 12, 24, 48):
        if nice >= raw and nice >= step_h:
            return nice
    return int(raw)


def _hover(kind: str, df: pd.DataFrame) -> list[str]:
    sp = SPEC[kind]
    out = []
    per = df[sp["period"]].values if sp["period"] and sp["period"] in df else None
    dfrom = df[sp["dir_from"]].values if sp["dir_from"] and sp["dir_from"] in df else None
    for k, (t, mag, dto) in enumerate(zip(df.index, df[sp["mag"]].values, df["dir_to"].values)):
        s = [t.strftime("%a %d %b %H:%M UTC"), f"{sp['mag_label']}: {_fmt(mag)} {sp['unit']}"]
        if per is not None:
            sea = "swell" if per[k] >= 8 else ("mixed" if per[k] >= 5 else "wind sea")
            s.append(f"{sp['period_label']}: {_fmt(per[k], 1)} s ({sea})")
        if dfrom is not None and np.isfinite(dfrom[k]):
            s.append(f"From {compass(dfrom[k])} ({dfrom[k]:.0f} deg), going to {compass(dto)}")
        elif np.isfinite(dto):
            s.append(f"Flowing to {compass(dto)} ({dto:.0f} deg)")
        out.append("<br>".join(s))
    return out


def _add_kind_traces(fig, df: pd.DataFrame, kind: str, every_hours, theme: dict, row=None, col=None,
                     show_legend=True):
    import plotly.graph_objects as go

    sp = SPEC[kind]
    df = df.dropna(subset=[sp["mag"]]).sort_index()
    rc = dict(row=row, col=col) if row else {}
    c = sp["line"]
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    daily = len(df) > 1 and pd.Series(df.index).diff().median() >= pd.Timedelta(hours=20)
    hover = _hover(kind, df)
    fig.add_trace(go.Scatter(
        x=df.index, y=df[sp["mag"]], mode="lines+markers" if daily else "lines",
        line=dict(color=c, width=2), marker=dict(size=5),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.14)",
        name=f"{sp['mag_label']} ({sp['unit']})", text=hover, hoverinfo="text",
        hoverlabel=dict(bgcolor="#ffffff", font=dict(color="#1a1a1a")), showlegend=show_legend), **rc)

    every = every_hours or _auto_every(df)
    step_h = max(1.0, pd.Series(df.index).diff().median().total_seconds() / 3600) if len(df) > 1 else 1
    stride = max(1, int(round(every / step_h)))
    pos = np.arange(0, len(df), stride)
    pos = pos[np.isfinite(df["dir_to"].values[pos])]
    a = df.iloc[pos]
    if sp["period"] and sp["period"] in a:
        length = np.clip(_CHART_LEN["a"] * a[sp["period"]].values + _CHART_LEN["b"], _CHART_LEN["lo"], _CHART_LEN["hi"])
    else:
        length = np.full(len(a), 20.0)
    # Arrows as annotations: true arrows (shaft + head) of an exact pixel length, centred on the line point with
    # xshift/yshift. Screen up = north. Plotly: ax > 0 = tail to the right, ay > 0 = tail below the head.
    for t, y, d, L, k in zip(a.index, a[sp["mag"]].values, a["dir_to"].values, length, pos):
        th = np.radians(d)
        ex, ny, L = float(np.sin(th)), float(np.cos(th)), float(L)
        fig.add_annotation(x=pd.Timestamp(t).isoformat(), y=y, text="", showarrow=True, arrowhead=2, arrowsize=1.1, arrowwidth=1.7,
                           arrowcolor=theme["arrow"], standoff=0, startstandoff=0,
                           ax=-ex * L, ay=ny * L, axref="pixel", ayref="pixel",
                           xshift=ex * L / 2, yshift=ny * L / 2, hovertext=hover[k],
                           hoverlabel=dict(bgcolor="#ffffff", font=dict(color="#1a1a1a")), **rc)
    ymax = float(np.nanmax(df[sp["mag"]].values)) if len(df) else 1.0
    fig.update_yaxes(range=[0, ymax * 1.22 + 1e-9], **rc)
    return df, every


def _layout(fig, theme: dict, title: str, subtitle: str, height: int):
    fig.update_layout(
        title=dict(text=f"{title}<br><span style='font-size:12px;color:{theme['muted']}'>{subtitle}</span>",
                   x=0.01, xanchor="left", font=dict(size=16, color=theme["fg"])),
        paper_bgcolor=theme["bg"], plot_bgcolor=theme["bg"], height=height,
        font=dict(family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif", size=12, color=theme["fg"]),
        margin=dict(l=56, r=20, t=78, b=40), hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right", font=dict(size=11),
                    bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=theme["grid"], linecolor=theme["grid"], tickformat="%a %d %b",
                     color=theme["muted"])
    fig.update_yaxes(showgrid=True, gridcolor=theme["grid"], zeroline=False, rangemode="tozero", color=theme["muted"])


def point_chart(df: pd.DataFrame, kind: str, every_hours: int | None = None, theme: str = "light",
                title: str | None = None, height: int = 360):
    """One time-series chart: magnitude as line + area, arrows along the line every N hours pointing where the
    water or air goes (up = north). Waves: arrow size grows with peak period (small = wind sea, large = swell).
    Hover shows all values. theme: "light" | "dark" (match Streamlit's theme.base)."""
    import plotly.graph_objects as go

    kind = _check_kind(kind)
    sp, th = SPEC[kind], _THEMES[theme]
    fig = go.Figure()
    df, every = _add_kind_traces(fig, df, kind, every_hours, th)
    where = ""
    if "lat" in df.attrs:
        where = f" at {df.attrs['lat']:.2f} N, {df.attrs['lon']:.2f} E"
    sub = f"Arrows every {every} h point where it goes (up = north)"
    if sp["period"]:
        sub += ". Arrow length = peak period: short = wind sea, long = swell"
    fig.update_layout(showlegend=False)
    _layout(fig, th, title or f"{sp['label']}{where}", sub, height)
    fig.update_yaxes(title_text=f"{sp['mag_label']} ({sp['unit']})", title_font=dict(size=12))
    fig.add_annotation(text=_source_line(df, kind), xref="paper", yref="paper", x=0, y=-0.2, showarrow=False,
                       xanchor="left", font=dict(size=10, color=th["muted"]))
    fig.update_layout(margin=dict(b=62))
    return fig


def _source_line(df, kind) -> str:
    src = SPEC[kind]["source"]
    if df.attrs.get("point_source") == "open-meteo" and kind != "wind":
        src = "Open-Meteo marine (Copernicus/Meteo-France models)"
    d = df.attrs.get("distance_km")
    return f"Source: {src}" + (f"; nearest model cell {d:.1f} km away" if d else "")


def combined_chart(dfs: dict, every_hours: int | None = None, theme: str = "light", title: str | None = None,
                   height: int = 640):
    """Waves, currents and wind stacked in one figure with a shared time axis (pass any subset)."""
    from plotly.subplots import make_subplots

    kinds = [k for k in KINDS if k in dfs and dfs[k] is not None and len(dfs[k])]
    th = _THEMES[theme]
    fig = make_subplots(rows=len(kinds), cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=[SPEC[k]["label"] for k in kinds])
    for i, k in enumerate(kinds, start=1):
        _add_kind_traces(fig, dfs[k], k, every_hours, th, row=i, col=1, show_legend=False)
        fig.update_yaxes(title_text=f"{SPEC[k]['unit']}", row=i, col=1)
    d0 = dfs[kinds[0]]
    where = f" at {d0.attrs['lat']:.2f} N, {d0.attrs['lon']:.2f} E" if "lat" in d0.attrs else ""
    _layout(fig, th, title or f"Sea state{where}",
            "Line = strength. Arrows point where it goes (up = north). Wave arrow length = period (long = swell).",
            height)
    for a in fig.layout.annotations:
        if a.xref == "paper" and a.text:  # subplot titles only, not the arrows
            a.font = dict(size=12, color=th["fg"])
            a.x, a.xanchor = 0.0, "left"
    return fig
