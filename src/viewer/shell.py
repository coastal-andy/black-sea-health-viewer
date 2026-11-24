"""App shell for direction B: theme state, the 72 px icon rail, and controls shared by every page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from viewer import adapters as A
from viewer import onboarding as OB
from viewer import profiles as P
from viewer import i18n as I
from viewer.i18n import dt, t
from viewer.style import LOGO_SVG, SECTOR, THEMES, esc, tokens

# rail key -> label; the order is the rail order
PAGE_OBJS: dict = {}  # rail key -> st.Page, filled by app.py
PAGES = {"overview": "Overview", "water": "Water", "seabed": "Seabed", "pressures": "Pressures", "methods": "Methods"}


# ------------------------------------------------------------------------------------------ theme
def init_theme():
    """Dark by default; ?theme=light in the URL starts in light (handy for checks and demos)."""
    ss = st.session_state
    if "theme" not in ss:
        q = st.query_params.get("theme")
        ss.theme = q if q in THEMES else "dark"


def _toggle_theme():
    ss = st.session_state
    ss.theme = "light" if ss.get("theme", "dark") == "dark" else "dark"
    ss.map_nonce = ss.get("map_nonce", 0) + 1  # rebuild maps with the matching basemap


def keep_widget_state():
    """Widget values survive page switches: re-assign every w_ key at the top of each run."""
    ss = st.session_state
    for k in list(ss.keys()):
        if isinstance(k, str) and k.startswith("w_"):
            ss[k] = ss[k]


# ------------------------------------------------------------------------------------------ resizable panels
# Drag handles for the docked right panel and the Water page's variable list, plus a tab that folds the panel away.
# They are plain elements on <body> (outside Streamlit's React tree, so reruns never remove them); their position
# and the column widths come from the CSS variables --bsv-pw / --bsv-aw (style.css). Widths are kept for the browser
# session (sessionStorage). Below 900 px the CSS hides the handles and the page stacks as before. The map iframes
# resize with their column, and Leaflet redraws on the iframe's own resize event (invalidateSize); a resize event
# is also sent after each drag for anything that listens on the page. No '<' followed by a letter inside the script:
# Streamlit's HTML sanitiser drops a script whose text looks like markup, so the SVG tags are written as \x3c.
RESIZE_JS = """<script>
(function () {
  var d = document, root = d.documentElement;
  if (d.getElementById('bsv-ph')) return;
  var RAIL = 72, KP = 'bsv-panel-w', KA = 'bsv-aside-w', KC = 'bsv-panel-closed';
  function get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch (e) {} }
  if (get(KP)) root.style.setProperty('--bsv-pw', get(KP) + 'px');
  if (get(KA)) root.style.setProperty('--bsv-aw', get(KA) + 'px');
  if (get(KC) === '1') root.classList.add('bsv-pc');
  function el(tag, id, attrs) {
    var e = d.createElement(tag); e.id = id;
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    d.body.appendChild(e); return e;
  }
  var ph = el('div', 'bsv-ph', {role: 'separator', 'aria-orientation': 'vertical', tabindex: '0',
    'aria-label': 'Resize the panel', title: 'Drag to resize the panel. Double-click to reset.'});
  var ah = el('div', 'bsv-ah', {role: 'separator', 'aria-orientation': 'vertical', tabindex: '0',
    'aria-label': 'Resize the list', title: 'Drag to resize the list. Double-click to reset.'});
  var pt = el('button', 'bsv-pt', {type: 'button', title: 'Hide the panel', 'aria-label': 'Hide the panel'});
  pt.innerHTML = "\\x3csvg class='cl' width='10' height='10' viewBox='0 0 10 10' aria-hidden='true'>\\x3cpath d='M3 1.5 L7 5 L3 8.5' " +
    "fill='none' stroke='currentColor' stroke-width='1.5'/>\\x3c/svg>\\x3csvg class='op' width='10' height='10' viewBox='0 0 10 10' " +
    "aria-hidden='true'>\\x3cpath d='M7 1.5 L3 5 L7 8.5' fill='none' stroke='currentColor' stroke-width='1.5'/>\\x3c/svg>";
  el('div', 'bsv-shield', {});
  function nudge() { setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 30); }
  function width(v, fromRight, x) {
    var main = window.innerWidth - RAIL;
    var w = fromRight ? window.innerWidth - x : x - RAIL;
    return Math.round(Math.max(fromRight ? 280 : 200, Math.min(main * (fromRight ? 0.5 : 0.4), w)));
  }
  function current(h, fromRight) {
    var r = h.getBoundingClientRect();
    return fromRight ? window.innerWidth - r.left - 4 : r.left + 4 - RAIL;
  }
  function wire(h, v, key, fromRight) {
    h.addEventListener('pointerdown', function (ev) {
      if (ev.button !== 0) return;
      ev.preventDefault();
      try { h.setPointerCapture(ev.pointerId); } catch (e) {}
      root.classList.add('bsv-drag');
      function move(e) { root.style.setProperty(v, width(v, fromRight, e.clientX) + 'px'); }
      function up() {
        h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up);
        h.removeEventListener('pointercancel', up); root.classList.remove('bsv-drag');
        var w = parseInt(root.style.getPropertyValue(v), 10);
        if (w) put(key, String(w));
        nudge();
      }
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
    });
    h.addEventListener('dblclick', function () { root.style.removeProperty(v); put(key, null); nudge(); });
    h.addEventListener('keydown', function (e) {
      var step = e.shiftKey ? 64 : 16, dir = 0;
      if (e.key === 'ArrowLeft') dir = fromRight ? 1 : -1;
      if (e.key === 'ArrowRight') dir = fromRight ? -1 : 1;
      if (!dir) return;
      e.preventDefault();
      var w = current(h, fromRight) + dir * step;
      w = width(v, fromRight, fromRight ? window.innerWidth - w : w + RAIL);
      root.style.setProperty(v, w + 'px'); put(key, String(w)); nudge();
    });
  }
  wire(ph, '--bsv-pw', KP, true);
  wire(ah, '--bsv-aw', KA, false);
  pt.addEventListener('click', function () {
    var closed = root.classList.toggle('bsv-pc');
    put(KC, closed ? '1' : null);
    pt.title = closed ? 'Show the panel' : 'Hide the panel';
    pt.setAttribute('aria-label', pt.title);
    nudge();
  });
  if (root.classList.contains('bsv-pc')) { pt.title = 'Show the panel'; pt.setAttribute('aria-label', pt.title); }
})();
</script>"""


# ------------------------------------------------------------------------------------------ rail
def rail(pages: dict):
    """Logo, one link per page (icons come from CSS), and the Dark/Light switch at the bottom."""
    tk = tokens()
    with st.sidebar:
        with st.container(key="logo_block"):
            st.markdown(f"<div class='bsv-logo'>{LOGO_SVG.format(c=tk['accent'])}</div>", unsafe_allow_html=True)
        for k, label in PAGES.items():
            with st.container(key=f"rail_{k}"):
                st.page_link(pages[k], label=t(label))
        dark = st.session_state.get("theme", "dark") == "dark"
        with st.container(key="bsv_js"):
            st.html(RESIZE_JS, unsafe_allow_javascript=True)
        ro = I.lang() == "ro"
        with st.container(key="lang_switch"):  # shows the language you switch to
            st.button("EN" if ro else "RO", key="lang_btn", on_click=I.toggle_lang,
                      help="Switch to English" if ro else "Comută pe limba română")
        with st.container(key="theme_switch"):
            st.button(t("Light") if dark else t("Dark"), key="theme_btn", on_click=_toggle_theme,
                      help=t("Switch to the light theme") if dark else t("Switch to the dark theme"))


# ------------------------------------------------------------------------------------------ place, date, season
def place_options() -> dict:
    opts = {}
    for name, (la, lo) in A.stations().items():
        opts[t("Station: {name}", name=name)] = dict(name=name, lat=la, lon=lo, kind="station", wkt=None)
    p = A.platforms()
    for _, r in p[p.recent & p.type.isin(["Mooring", "Gliders"])].iterrows():
        tag = {"under_qc": t(" (under QC)"), "context": t(" (shore station)")}.get(r.trust, "")
        opts[t("Buoy: {name}", name=r['name']) + tag] = dict(name=t("Buoy {name}", name=r['name']), lat=float(r.lat), lon=float(r.lon),
                                               kind="platform", wkt=None, platform=r.id)
    for _, r in p[p.id.isin(["EUXRoOB02", "EUXRoOB03"])].iterrows():
        opts[t("Buoy: {name} (offshore, data to {when})", name=r['name'], when=dt(r.time_end, "%b %Y"))] = dict(
            name=t("Buoy {name}", name=r['name']), lat=float(r.lat), lon=float(r.lon), kind="platform", wkt=None, platform=r.id)
    stamp = A._zones_stamp()
    for k, (lab, _) in SECTOR.items():
        g = A.sector_zone_geom(k, stamp)
        if g is not None and not g.is_empty:
            rp = g.representative_point()
            opts[t("Zone: {name}", name=lab)] = dict(name=t("{name} zones", name=lab), lat=rp.y, lon=rp.x, kind="zone",
                                        wkt=g.simplify(0.002).wkt)
    hs = A.hotspots(stamp)
    for _, r in hs.head(12).iterrows():
        opts[t("Overlap area: {name}", name=r['name'])] = dict(name=str(r["name"]), lat=float(r.lat), lon=float(r.lon),
                                                  kind="zone", wkt=r.wkt)
    return opts


def _on_place():
    ss = st.session_state
    k = ss.get("w_place")
    if k and k in ss._place_opts:
        ss.sel = dict(ss._place_opts[k])


def place_picker(placeholder: str = "Search a beach, port, station or zone"):
    ss = st.session_state
    ss._place_opts = place_options()
    if ss.get("w_place") not in ss._place_opts:
        ss["w_place"] = None
    st.selectbox(t("Place"), list(ss._place_opts), index=None, key="w_place", on_change=_on_place,
                 placeholder=t(placeholder), label_visibility="collapsed")


def day_season() -> tuple[str, str]:
    """Current date (str) and season, from session state; the widgets below change them."""
    ss = st.session_state
    today = A.today().date()
    day = ss.get("w_day", today)
    auto = A.season_for_date(day)
    mode = ss.get("w_season", "auto")
    return str(day), (auto if mode == "auto" else mode)


def season_control():
    day, _ = day_season()
    auto = A.season_for_date(pd.Timestamp(day).date())
    st.radio(t("Season for pressure zones"), ["auto", "summer", "winter"], horizontal=True, key="w_season",
             format_func=lambda s: t("From date ({season})", season=t(auto)) if s == "auto" else t(s.capitalize()),
             help=t("Summer = bathing season, 1 June to 15 September: tourism zones are on."))


def date_controls():
    ss = st.session_state
    today = A.today().date()
    ss.setdefault("w_day", today)
    day = st.slider("Date", min_value=today - pd.Timedelta(days=365), max_value=today + pd.Timedelta(days=5),
                    format="DD MMM YYYY", key="w_day")
    auto = A.season_for_date(day)
    st.radio("Season for pressure zones", ["auto", "summer", "winter"], horizontal=True, key="w_season",
             format_func=lambda s: f"From date ({auto})" if s == "auto" else s.capitalize(),
             help="Summer = bathing season, 1 June to 15 September: tourism zones are on.")


EDGES = {"soft": "Soft edges", "sharp": "Sharp edges"}
EDGES_SHORT = {"soft": "Soft", "sharp": "Sharp"}
EDGES_DEFAULT = "soft"  # checked by the coordinator on 24 Nov; "?edges=sharp" shows the grid cells


def edges() -> str:
    """'soft' or 'sharp': how the pressure overlap and sector zones are drawn (one setting for every map)."""
    ss = st.session_state
    if ss.get("w_edges") not in EDGES:  # ?edges=soft in the URL starts with soft edges (handy for checks and demos)
        q = st.query_params.get("edges")
        ss["w_edges"] = q if q in EDGES else EDGES_DEFAULT
    return ss["w_edges"]


def edges_control(compact: bool = False):
    """Edges: Soft / Sharp. Soft fades the zone limits (they are approximate); the colour is still the count."""
    edges()
    st.segmented_control(t("Edges"), list(EDGES), key="w_edges",
                         format_func=lambda k: t(EDGES_SHORT[k] if compact else EDGES[k]),
                         required=True, label_visibility="collapsed" if compact else "visible",
                         help=t("Soft: zone limits fade out, because they are approximate. Sharp: the 500 m grid "
                                "cells and the zone outlines. Both show the same count of overlapping sectors."))


# ------------------------------------------------------------------------------------------ profile
def describe(p: dict) -> str:
    """profiles.describe in the viewer language."""
    s = t(P.ROLES.get(p.get("role"), "Visitor"))
    if p.get("role") == "stakeholder" and p.get("sector"):
        s += f" - {t(P.SECTORS[p['sector']])}"
    if p.get("role") == "researcher" and p.get("focus"):
        s += f" - {t(p['focus'])}"
    return s


def profile_menu():
    ss = st.session_state
    profile = ss.profile
    with st.popover(t("Viewing as: {who}", who=describe(profile)), width="stretch"):
        role = st.radio(t("Who are you?"), list(P.ROLES), index=list(P.ROLES).index(profile["role"]),
                        format_func=lambda k: t(P.ROLES[k]), key="pf_role")
        sector = focus = None
        if role == "stakeholder":
            sector = st.selectbox(t("Sector"), list(P.SECTORS), format_func=lambda k: t(P.SECTORS[k]), key="pf_sector",
                                  index=list(P.SECTORS).index(profile["sector"]) if profile.get("sector") else 0)
        if role == "researcher":
            focus = st.selectbox(t("Focus"), list(P.FOCUS), format_func=lambda k: t(P.FOCUS[k]), key="pf_focus",
                                 index=list(P.FOCUS).index(profile["focus"]) if profile.get("focus") else 0)
        goal = st.selectbox(t("What do you want to do?"), list(P.GOALS), format_func=lambda k: t(P.GOALS[k]),
                            key="pf_goal", index=list(P.GOALS).index(profile["goal"]))
        if st.button(t("Apply"), type="primary", width="stretch"):
            OB.finish(dict(role=role, sector=sector, focus=focus, goal=goal))
            st.rerun()
        if st.button(t("Start the questionnaire again"), width="stretch"):
            ss.onboarding = True
            st.rerun()


# ------------------------------------------------------------------------------------------ selection
def selection_header(sel: dict, season: str) -> str:
    """Small uppercase coordinates line, the place name, and the overlap / Natura lines."""
    inside = A.zones_containing(sel["lat"], sel["lon"], A._zones_stamp())
    n, secs = A.overlap_at(sel["lat"], sel["lon"], season)
    ov = t("{n} of 5 sectors", n=n) if n else t("outside the sector zones")
    out = [f"<div class='bsv-lbl'>{sel['lat']:.3f} N &middot; {sel['lon']:.3f} E &middot; {esc(ov)} ({esc(t(season))})</div>",
           f"<div class='bsv-place'>{esc(place_name(sel['name']))}</div>"]
    if secs:
        names = ", ".join(t(x.strip()) for x in secs.split(","))
        out.append(f"<div class='bsv-note'>{esc(t('Sectors here: {names}', names=names))}</div>")
    nat = [z["sector"] for z in inside if z["kind"] == "Natura 2000"]
    if nat:
        out.append(f"<div class='bsv-note'>{esc(t('Inside Natura 2000: {names}', names='; '.join(nat[:2])))}</div>")
    return "".join(out)


def place_name(name: str) -> str:
    """Names the viewer gives to places (start points, 'Clicked point') in the viewer language; real place names
    such as Constanța or Mangalia stay as they are."""
    return t(name) if isinstance(name, str) else name


def page_head(title: str, sub: str = ""):
    """Header strip for the non-map pages: title on the left, place, date and profile on the right."""
    ss = st.session_state
    c1, c2, c3 = st.columns([1.3, 1.6, 1], vertical_alignment="bottom")
    with c1:
        st.markdown(f"<div class='bsv-lbl'>{esc(sub)}</div><div class='bsv-place'>{esc(title)}</div>",
                    unsafe_allow_html=True)
    with c2:
        place_picker()
        sel = ss.sel
        st.caption(f"Selected: {sel['name']} ({sel['lat']:.3f} N, {sel['lon']:.3f} E)")
    with c3:
        profile_menu()
