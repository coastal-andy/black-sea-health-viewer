"""App shell for direction B: theme state, the 72 px icon rail, and controls shared by every page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from viewer import adapters as A
from viewer import onboarding as OB
from viewer import profiles as P
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


# ------------------------------------------------------------------------------------------ rail
def rail(pages: dict):
    """Logo, one link per page (icons come from CSS), and the Dark/Light switch at the bottom."""
    t = tokens()
    with st.sidebar:
        st.markdown(f"<div class='bsv-logo'>{LOGO_SVG.format(c=t['accent'])}</div>", unsafe_allow_html=True)
        for k, label in PAGES.items():
            with st.container(key=f"rail_{k}"):
                st.page_link(pages[k], label=label)
        dark = st.session_state.get("theme", "dark") == "dark"
        with st.container(key="theme_switch"):
            st.button("Light" if dark else "Dark", key="theme_btn", on_click=_toggle_theme,
                      help="Switch to the light theme" if dark else "Switch to the dark theme")


# ------------------------------------------------------------------------------------------ place, date, season
def place_options() -> dict:
    opts = {}
    for name, (la, lo) in A.stations().items():
        opts[f"Station: {name}"] = dict(name=name, lat=la, lon=lo, kind="station", wkt=None)
    p = A.platforms()
    for _, r in p[p.recent & p.type.isin(["Mooring", "Gliders"])].iterrows():
        tag = {"under_qc": " (under QC)", "context": " (shore station)"}.get(r.trust, "")
        opts[f"Buoy: {r['name']}{tag}"] = dict(name=f"Buoy {r['name']}", lat=float(r.lat), lon=float(r.lon),
                                               kind="platform", wkt=None, platform=r.id)
    for _, r in p[p.id.isin(["EUXRoOB02", "EUXRoOB03"])].iterrows():
        opts[f"Buoy: {r['name']} (offshore, data to {r.time_end:%b %Y})"] = dict(
            name=f"Buoy {r['name']}", lat=float(r.lat), lon=float(r.lon), kind="platform", wkt=None, platform=r.id)
    stamp = A._zones_stamp()
    for k, (lab, _) in SECTOR.items():
        g = A.sector_zone_geom(k, stamp)
        if g is not None and not g.is_empty:
            rp = g.representative_point()
            opts[f"Zone: {lab}"] = dict(name=f"{lab} zones", lat=rp.y, lon=rp.x, kind="zone",
                                        wkt=g.simplify(0.002).wkt)
    hs = A.hotspots(stamp)
    for _, r in hs.head(12).iterrows():
        opts[f"Overlap area: {r['name']}"] = dict(name=str(r["name"]), lat=float(r.lat), lon=float(r.lon),
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
    st.selectbox("Place", list(ss._place_opts), index=None, key="w_place", on_change=_on_place,
                 placeholder=placeholder, label_visibility="collapsed")


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
    st.radio("Season for pressure zones", ["auto", "summer", "winter"], horizontal=True, key="w_season",
             format_func=lambda s: f"From date ({auto})" if s == "auto" else s.capitalize(),
             help="Summer = bathing season, 1 June to 15 September: tourism zones are on.")


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


# ------------------------------------------------------------------------------------------ profile
def profile_menu():
    ss = st.session_state
    profile = ss.profile
    with st.popover(f"Viewing as: {P.describe(profile)}", width="stretch"):
        role = st.radio("Who are you?", list(P.ROLES), index=list(P.ROLES).index(profile["role"]),
                        format_func=P.ROLES.get, key="pf_role")
        sector = focus = None
        if role == "stakeholder":
            sector = st.selectbox("Sector", list(P.SECTORS), format_func=P.SECTORS.get, key="pf_sector",
                                  index=list(P.SECTORS).index(profile["sector"]) if profile.get("sector") else 0)
        if role == "researcher":
            focus = st.selectbox("Focus", list(P.FOCUS), format_func=P.FOCUS.get, key="pf_focus",
                                 index=list(P.FOCUS).index(profile["focus"]) if profile.get("focus") else 0)
        goal = st.selectbox("What do you want to do?", list(P.GOALS), format_func=P.GOALS.get, key="pf_goal",
                            index=list(P.GOALS).index(profile["goal"]))
        if st.button("Apply", type="primary", width="stretch"):
            OB.finish(dict(role=role, sector=sector, focus=focus, goal=goal))
            st.rerun()
        if st.button("Start the questionnaire again", width="stretch"):
            ss.onboarding = True
            st.rerun()


# ------------------------------------------------------------------------------------------ selection
def selection_header(sel: dict, season: str) -> str:
    """Small uppercase coordinates line, the place name, and the overlap / Natura lines."""
    inside = A.zones_containing(sel["lat"], sel["lon"], A._zones_stamp())
    n, secs = A.overlap_at(sel["lat"], sel["lon"], season)
    ov = f"{n} of 5 sectors" if n else "outside the sector zones"
    out = [f"<div class='bsv-lbl'>{sel['lat']:.3f} N &middot; {sel['lon']:.3f} E &middot; {esc(ov)} ({esc(season)})</div>",
           f"<div class='bsv-place'>{esc(sel['name'])}</div>"]
    if secs:
        out.append(f"<div class='bsv-note'>Sectors here: {esc(secs.replace(',', ', '))}</div>")
    nat = [z["sector"] for z in inside if z["kind"] == "Natura 2000"]
    if nat:
        out.append(f"<div class='bsv-note'>Inside Natura 2000: {esc('; '.join(nat[:2]))}</div>")
    return "".join(out)


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
