"""Coast and seabed page (direction B3): wave / current / wind / depth map from viewer.vectorviz and EMODnet,
4 sea-state rows with "why it matters" on click, and a depth profile in a bottom panel you can hide."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from viewer import adapters as A
from viewer import maps as M
from viewer import panels as PN
from viewer import profiles as P
from viewer import shell as SH
from viewer.style import esc, plotly_layout, theme_name, tokens

FIELDS = {"waves": "Waves", "currents": "Currents", "wind": "Wind", "depth": "Depth"}
LAYER = {"waves": "vec_waves", "currents": "vec_currents", "wind": "vec_wind", "depth": "bathy_colour"}
def _sea_word(h):
    """WMO sea-state words for significant wave height (m)."""
    for lim, w in ((0.1, "calm"), (0.5, "smooth"), (1.25, "slight"), (2.5, "moderate"), (4.0, "rough"), (6.0, "very rough")):
        if h < lim:
            return w
    return "high"


def _towards_south(deg):
    return deg is not None and np.isfinite(deg) and 100 <= deg % 360 <= 260


def why_waves(r):
    base = ("Waves stir up the seabed in shallow water and make it murky. Long-period swell reaches deeper than "
            "short wind waves.")
    if r is None:
        return base
    kind = "mostly wind waves" if r.wave_period <= 6 else ("swell from farther away" if r.wave_period >= 8 else
                                                             "a mix of wind waves and swell")
    return f"{base} Today: {r.wave_height:.1f} m ({_sea_word(r.wave_height)} sea), {r.wave_period:.0f} s, {kind}."


def why_current(r, wind_r):
    base = ("The main coastal current usually runs south along this coast, carrying Danube water, nutrients and "
            "mud.")
    if r is None:
        return base
    today = f" Today the model shows {r.current_speed:.2f} m/s towards {_compass(r.dir_to)}"
    if _towards_south(r.dir_to):
        return base + today + ", in line with the usual flow."
    if wind_r is not None and np.isfinite(wind_r.dir_to):
        diff = abs((r.dir_to - wind_r.dir_to + 180) % 360 - 180)
        if diff <= 60:
            return (base + today + ", against the usual flow. The wind is also blowing towards "
                    f"{_compass(wind_r.dir_to)} today, which can push the surface water that way.")
    return base + today + ", against the usual flow. The model does not say why; short reversals near the coast happen."


def why_wind(r):
    base = ("Wind from the south or south-west along this coast can push surface water offshore and pull cold deep "
            "water up (upwelling), mostly in summer; the sea temperature then drops fast.")
    if r is None:
        return base
    upw = 157.5 <= r.wind_dir % 360 <= 247.5 and r.wind_speed >= 5
    return base + (f" Today: {r.wind_speed:.1f} m/s from {_compass(r.wind_dir)}, "
                   + ("a direction and strength that can cause upwelling." if upw else "not an upwelling wind."))


def why_depth(d):
    base = "Shallow water warms and loses oxygen faster than deep water; the shelf here deepens slowly."
    if d is None or not np.isfinite(d) or d <= 0:
        return base
    if d < 20:
        return base + f" At {d:.0f} m, storms can mix the water down to the seabed."
    if d < 60:
        return base + f" At {d:.0f} m, the bottom water can stay cut off from the surface in summer, when oxygen can drop."
    return base + f" At {d:.0f} m this is the outer shelf, less affected by the coast."


PROFILE_EAST = 1.6  # degrees of longitude east of the place: from the coast out over the shelf


# ------------------------------------------------------------------------------------------ data
def _vv():
    return A.vectorviz()


def _point(kind, lat, lon):
    t = A.today()
    start, end = str((t - pd.Timedelta(days=10)).date()), str((t + pd.Timedelta(days=4)).date())
    try:
        return A.timed(PN._vec_point, kind, round(lat, 3), round(lon, 3), start, end, timeout=30)
    except Exception:
        return None


def _at(df, when):
    if df is None or df.empty:
        return None
    df = df.dropna(how="all")
    i = df.index.get_indexer([pd.Timestamp(when)], method="nearest")[0]
    return df.iloc[i], df.index[i]


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _depth_at(lat, lon):
    from marinekit.sources import emodnet_layers as el
    return el.depth_at(lat, lon)


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _profile(lat, lon0, lon1):
    from marinekit.sources import emodnet_layers as el
    return el.depth_profile(lat, lon0, lat, lon1)


def _safe(fn, *args, timeout=25):
    try:
        return A.timed(fn, *args, timeout=timeout)
    except Exception:
        return None


def _compass(deg):
    vv = _vv()
    if deg is None or not np.isfinite(deg):
        return "-"
    return vv.compass(deg) if vv is not None and hasattr(vv, "compass") else f"{deg:.0f} deg"


def map_time(field, day):
    """One time step for the map and the panel: 12:00 UTC of the day. If that step cannot be loaded for the map
    within 25 s (first download, or offline), both use 00:00 UTC, the step the map used before."""
    T = pd.Timestamp(day) + pd.Timedelta(hours=12)
    if field in ("waves", "wind"):
        try:
            A.timed(_load_field_cached, field, str(T), timeout=25)
        except Exception:
            T = pd.Timestamp(day)
    return T


@st.cache_data(ttl=6 * 3600, show_spinner=False, max_entries=32)
def _load_field_cached(kind, when):
    return _vv().load_field(kind, A.BBOX_RO, when)


def sea_state(sel, day, when=None):
    """Rows: key -> (title, value, sub line, origin, time, why it matters), all at the time step `when`."""
    when = pd.Timestamp(when) if when is not None else pd.Timestamp(day) + pd.Timedelta(hours=12)
    rows = {}
    w = _at(_point("waves", sel["lat"], sel["lon"]), when)
    c = _at(_point("currents", sel["lat"], sel["lon"]), when.normalize())  # daily mean of that day, as on the map
    wd = _at(_point("wind", sel["lat"], sel["lon"]), when)
    if w:
        r, t = w
        rows["waves"] = ("Waves", f"{r.wave_height:.1f} m · {r.wave_period:.0f} s",
                         f"height · period · from {_compass(r.wave_dir)}", "model", t, why_waves(r))
    if c:
        r, t = c
        rows["currents"] = ("Surface current", f"{r.current_speed:.2f} m/s",
                            f"flowing towards {_compass(r.dir_to)} · daily mean",
                            "model", t, why_current(r, wd[0] if wd else None))
    if wd:
        r, t = wd
        rows["wind"] = ("Wind", f"{r.wind_speed:.1f} m/s", f"from {_compass(r.wind_dir)}", "model", t, why_wind(r))
    d = _safe(_depth_at, round(sel["lat"], 4), round(sel["lon"], 4))
    if d is not None and np.isfinite(d):
        rows["depth"] = ("Seabed depth here", f"{d:.0f} m" if d > 0 else "on land", "EMODnet Bathymetry DTM",
                         "measured", None, why_depth(d))
    fallback = {"waves": why_waves(None), "currents": why_current(None, None), "wind": why_wind(None),
                "depth": why_depth(None)}
    for k, title in (("waves", "Waves"), ("currents", "Surface current"), ("wind", "Wind"),
                     ("depth", "Seabed depth here")):
        rows.setdefault(k, (title, "-", "no data here (or still downloading)", "", None, fallback[k]))
    return {k: rows[k] for k in ("waves", "currents", "wind", "depth")}


# ------------------------------------------------------------------------------------------ panel rows
def _toggle(k):
    ss = st.session_state
    ss.open_sea = None if ss.get("open_sea") == k else k


def _rows(rows):
    ss = st.session_state
    from viewer.overview import _CHEV, _CHEV_OPEN
    for k, (title, value, sub, origin, _, why) in rows.items():
        is_open = ss.get("open_sea") == k
        with st.container(key=f"crow_sea_{k}"):
            st.markdown(f"<div class='bsv-row bsv-row4{' open' if is_open else ''}'>"
                        f"<span class='bsv-rt'>{esc(title)}</span><span class='bsv-rv'>{esc(value)}</span>"
                        f"<span class='bsv-chev'>{_CHEV_OPEN if is_open else _CHEV}</span>"
                        f"<span class='bsv-rl'>{esc(sub)}</span><span class='bsv-ro'>{esc(origin)}</span><span></span>"
                        "</div>", unsafe_allow_html=True)
            st.button(f"{'Close' if is_open else 'Open'}: why {title.lower()} matters", key=f"cbtn_sea_{k}",
                      on_click=_toggle, args=(k,))
        if is_open:
            with st.container(key=f"cdet_sea_{k}"):
                st.markdown(f"<div class='bsv-det'><span class='bsv-lbl'>Why</span><span>{esc(why)}</span></div>",
                            unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------ depth profile
def _toggle_profile():
    ss = st.session_state
    ss.w_profile = not ss.get("w_profile", True)


def profile_chart(lat, lon0, lon1, d):
    t = tokens()
    x = np.linspace(0, 1, len(d))
    km = x * (lon1 - lon0) * 111.32 * np.cos(np.radians(lat))
    depth = np.array(d, float)
    sea = np.where(depth > 0, depth, np.nan)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=km, y=np.nan_to_num(-sea, nan=0.0), mode="lines", fill="tozeroy",
                             fillcolor=t["raised"], line=dict(color=t["accent"], width=1.6),
                             hovertemplate="%{x:.0f} km: %{customdata:.0f} m<extra></extra>", customdata=sea))
    fig.update_layout(height=150, margin=dict(l=44, r=12, t=6, b=26), showlegend=False, hovermode="x")
    fig.update_yaxes(title=None, ticksuffix=" m", nticks=4, zeroline=True)
    fig.update_xaxes(title=None, ticksuffix=" km", nticks=8, showgrid=False)
    return plotly_layout(fig)


def depth_panel(sel):
    ss = st.session_state
    open_ = ss.get("w_profile", True)
    lat, lon0 = round(sel["lat"], 3), round(sel["lon"] - 0.12, 3)
    lon1 = round(sel["lon"] + PROFILE_EAST, 3)
    with st.container(key="depthpanel"):
        with st.container(key="dp_head", horizontal=True, vertical_alignment="center"):
            st.markdown(f"<span class='bsv-dp-t'>Depth profile along the line</span>"
                        f"<span class='bsv-note' style='margin-left:16px'>{esc(sel['name'])} to open sea, {lat:.2f} N &middot; "
                        "EMODnet Bathymetry</span>", unsafe_allow_html=True)
            st.button("Hide" if open_ else "Show", key="profile_btn", on_click=_toggle_profile)
        if open_:
            d = _safe(_profile, lat, lon0, lon1, timeout=20)
            if not d:
                st.caption("Depth profile not available (EMODnet Bathymetry needs the internet the first time).")
            else:
                st.plotly_chart(profile_chart(lat, lon0, lon1, d), width="stretch", theme=None,
                                config={"displaylogo": False, "displayModeBar": False})


# ------------------------------------------------------------------------------------------ page
def page():
    ss = st.session_state
    profile = ss.profile
    detail = P.show_detail(profile)
    day_s, season = SH.day_season()
    sel = ss.sel
    if ss.get("w_field") not in FIELDS:
        ss["w_field"] = "waves"
    field = ss["w_field"]
    open_ = ss.get("w_profile", True)
    left, right = st.columns([2.3, 1], gap=None)
    with left:
        with st.container(key="bsv_map_po" if open_ else "bsv_map_pc"):
            with st.container(key="map_tools"):
                SH.place_picker()
                st.segmented_control("Field", list(FIELDS), key="w_field", format_func=FIELDS.get, required=True,
                                     label_visibility="collapsed", width="stretch")
                note_slot = st.empty()
            T = map_time(field, day_s)
            ss["_sea_time"] = str(T)  # the panel reads the same time step
            extra = {"depth": _depth_legend, "wind": lambda mm: _wind_labels(mm, T, msgs_extra, sel)}.get(field)
            msgs_extra = []
            m, fd, msgs = M.build(ss.view, {LAYER[field]}, day_s, season, None, detail, theme=theme_name(),
                                  legend=True, extra=extra, vec_time=str(T))
            msgs = msgs + msgs_extra
            fg = __import__("folium").FeatureGroup(name="Selection")
            M.add_selection(fg, sel)
            out = st_folium(m, height=640, use_container_width=True,
                            key=f"seamap_{field}_{T:%Y%m%d%H}_{ss.get('map_nonce', 0)}_{theme_name()}",
                            feature_group_to_add=fg, returned_objects=["last_clicked"])
            M.notes_slot(note_slot, msgs)
            depth_panel(sel)
            click = (out or {}).get("last_clicked")
            if click and click != ss.get("last_click"):
                ss.last_click = click
                ss.sel = dict(name="Clicked point", lat=round(click["lat"], 4), lon=round(click["lng"], 4),
                              kind="point", wkt=None)
                st.rerun()
    with right:
        with st.container(key="bsv_panel"):
            sea_panel(sel, day_s, profile)


@st.fragment
def sea_panel(sel, day_s, profile):
    """Right panel. A fragment: opening a row or the chart section does not redraw the map."""
    T = pd.Timestamp(st.session_state.get("_sea_time") or (pd.Timestamp(day_s) + pd.Timedelta(hours=12)))
    rows = sea_state(sel, day_s, T)
    when = f"{T:%d %b %H:%M} UTC, currents as daily mean"
    st.markdown(f"<div class='bsv-sec'><div class='bsv-lbl'>Sea state &middot; {esc(when)}</div>"
                f"<div class='bsv-place'>{esc(sel['name'])}</div>"
                "<p class='bsv-vsub'>How the water moves and how deep it is. Values come from the Copernicus "
                "wave and current models, Open-Meteo wind and EMODnet Bathymetry.</p></div>",
                unsafe_allow_html=True)
    _rows(rows)
    with st.expander("Waves, currents and wind  ·  10 days and forecast"):
        PN.vector_view(sel, profile)
    with st.container(key="panel_foot", horizontal=True, vertical_alignment="center"):
        st.page_link(SH.PAGE_OBJS["water"], label="Water quality analysis")
        SH.profile_menu()


def _depth_legend(m):
    """The depth colour layer comes from maps.build ('bathy_colour'); this adds its matching legend."""
    import folium
    m.get_root().html.add_child(folium.Element(M.depth_legend_html()))


def _wind_labels(m, when, msgs, sel=None):
    """Wind has no gridded source in vectorviz (Open-Meteo reference points only): label each point with its speed,
    and add the selected place with the same value as the panel (same source, same time step)."""
    import folium
    t = tokens()
    try:
        ds = _load_field_cached("wind", str(when))
    except Exception as ex:
        msgs.append(f"Wind not available: vectorviz.load_field('wind') failed ({str(ex)[:100]}).")
        return
    if "time" in ds.dims:
        ds = ds.isel(time=0)

    def label(lat, lon, text, strong=False):
        folium.Marker([lat, lon], icon=folium.DivIcon(
            icon_size=(150, 20), icon_anchor=(-18, 10),
            html=f"<div style='font:{600 if strong else 500} 12px sans-serif;color:{t['text']};background:{t['overlay']};"
                 f"border:1px solid {t['accent'] if strong else t['ctrl']};border-radius:4px;padding:1px 6px;"
                 f"white-space:nowrap;display:inline-block'>{text}</div>")).add_to(m)

    n = 0
    for i in range(ds.sizes.get("station", 0)):
        sp, frm = float(ds.wind_speed.values[i]), float(ds.wind_dir.values[i])
        if not np.isfinite(sp):
            continue
        n += 1
        label(float(ds.lat.values[i]), float(ds.lon.values[i]), f"{sp:.1f} m/s from {_compass(frm)}")
    if sel is not None:
        w = _at(_point("wind", sel["lat"], sel["lon"]), when)
        if w:
            r, _ = w
            label(sel["lat"], sel["lon"], f"Here: {r.wind_speed:.1f} m/s from {_compass(r.wind_dir)}", strong=True)
    if not n:
        msgs.append("Wind not available here: Open-Meteo returned no values (offline and not in the cache?).")
    m.get_root().html.add_child(folium.Element(
        f"<div style='position:absolute;left:10px;bottom:62px;z-index:9998;max-width:260px;background:{t['overlay']};"
        f"color:{t['sub']};border:1px solid {t['ctrl']};border-radius:4px;padding:5px 8px;font:11.5px/1.35 sans-serif'>"
        f"Wind: Open-Meteo model values at {n} reference points and at the selected place, {pd.Timestamp(when):%d %b %H:%M} "
        "UTC. There is no gridded wind field, so the map shows points.</div>"))


