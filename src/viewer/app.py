"""Black Sea Health Viewer (EfxINNOs hackathon, Challenge 04 Ecosystem Health).

Run:  .venv/bin/streamlit run src/viewer/app.py --server.port 8502 --server.headless true
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import folium  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

from viewer import adapters as A  # noqa: E402
from viewer import maps as M  # noqa: E402
from viewer import onboarding as OB  # noqa: E402
from viewer import panels as PN  # noqa: E402
from viewer import profiles as P  # noqa: E402
from viewer import screens as SC  # noqa: E402
from viewer.style import CSS, SECTOR, esc, pill  # noqa: E402

st.set_page_config(page_title="Black Sea Health Viewer", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
ss = st.session_state
T0 = time.perf_counter()

# ------------------------------------------------------------------------------------------ questionnaire
# demo shortcut: ?role=stakeholder&sector=tourism&goal=risk skips the questionnaire
qp = st.query_params
if "profile" not in ss and qp.get("role") in P.ROLES:
    OB.finish(dict(role=qp["role"], sector=qp.get("sector") if qp.get("sector") in P.SECTORS else None,
                   focus=qp.get("focus") if qp.get("focus") in P.FOCUS else None,
                   goal=qp.get("goal") if qp.get("goal") in P.GOALS else "now"))

ob_slot = st.empty()  # the questionnaire lives here; an empty slot on later runs clears it at once
if "profile" not in ss or ss.get("onboarding"):
    with ob_slot.container():
        OB.render()
    st.stop()

profile = ss.profile
detail = P.show_detail(profile)
if "sel" not in ss:
    OB.apply_defaults(profile)

SCREENS = ["Map", "Health cards", "Sectors", "Data and methods"]

# ------------------------------------------------------------------------------------------ header
h1, h2, h3 = st.columns([1.5, 2.2, 1.1], vertical_alignment="center")
with h1:
    st.markdown("<p class='bsv-title'>Black Sea Health Viewer</p><p class='bsv-sub'>Romanian coast - conditions, "
                "change and pressures</p>", unsafe_allow_html=True)
with h2:
    ss.setdefault("screen", "Map")
    screen = st.segmented_control("Screen", SCREENS, key="screen", label_visibility="collapsed") or "Map"
with h3:
    with st.popover(f"Profile: {P.describe(profile)}", width="stretch"):
        st.markdown(f"<span class='bsv-chip'>{esc(P.describe(profile))}</span>"
                    f"<span class='bsv-chip'>{esc(P.GOALS[profile['goal']])}</span>", unsafe_allow_html=True)
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

# ------------------------------------------------------------------------------------------ sidebar
today = A.today().date()


def _place_options() -> dict:
    opts = {}
    for name, (la, lo) in A.stations().items():
        opts[f"Station: {name}"] = dict(name=name, lat=la, lon=lo, kind="station", wkt=None)
    p = A.platforms()
    for _, r in p[p.recent & p.type.isin(["Mooring", "Gliders"])].iterrows():
        tag = {"under_qc": " (under QC)", "context": " (shore station)"}.get(r.trust, "")
        opts[f"Buoy: {r['name']}{tag}"] = dict(name=f"Buoy {r['name']}", lat=float(r.lat), lon=float(r.lon), kind="platform",
                                               wkt=None, platform=r.id)
    for _, r in p[p.id.isin(["EUXRoOB02", "EUXRoOB03"])].iterrows():
        opts[f"Buoy: {r['name']} (offshore, data to {r.time_end:%b %Y})"] = dict(
            name=f"Buoy {r['name']}", lat=float(r.lat), lon=float(r.lon), kind="platform", wkt=None, platform=r.id)
    stamp = A._zones_stamp()
    for k, (lab, _) in SECTOR.items():
        g = A.sector_zone_geom(k, stamp)
        if g is not None and not g.is_empty:
            rp = g.representative_point()
            opts[f"Zone: {lab}"] = dict(name=f"{lab} zones", lat=rp.y, lon=rp.x, kind="zone", wkt=g.simplify(0.002).wkt)
    hs = A.hotspots(stamp)
    for _, r in hs.head(12).iterrows():
        n = int(r.get("max_n_sectors", 0) or 0)
        opts[f"Overlap area: {r['name']}"] = dict(name=str(r["name"]), lat=float(r.lat), lon=float(r.lon),
                                                          kind="zone", wkt=r.wkt)
    return opts


def _on_place():
    k = ss.get("w_place")
    if k and k in ss._place_opts:
        ss.sel = dict(ss._place_opts[k])


with st.sidebar:
    st.markdown("**Place**")
    ss._place_opts = _place_options()
    st.selectbox("Pick a station, buoy or zone", list(ss._place_opts), index=None, key="w_place", on_change=_on_place,
                 placeholder="Pick a station, buoy or zone", label_visibility="collapsed")
    sel = ss.sel
    st.caption(f"Selected: **{sel['name']}** ({sel['lat']:.3f} N, {sel['lon']:.3f} E). Or click the map.")

    st.markdown("**Date**")
    ss.setdefault("w_day", today)
    day = st.slider("Date", min_value=today - pd.Timedelta(days=365), max_value=today + pd.Timedelta(days=5),
                    format="DD MMM YYYY", key="w_day", label_visibility="collapsed")
    st.caption("Satellite maps: latest is usually yesterday. Model: up to 5 days ahead (forecast).")
    auto_season = A.season_for_date(day)
    smode = st.radio("Season for pressure zones", ["auto", "summer", "winter"], horizontal=True, key="w_season",
                     format_func=lambda s: f"From date ({auto_season})" if s == "auto" else s.capitalize())
    season = auto_season if smode == "auto" else smode
    st.caption("Summer = bathing season, 1 June to 15 September: tourism zones are on.")

    if screen == "Map":
        st.markdown("**Map layers**")
        grid_opts = ["none"] + list(A.LAYERS)
        if ss.get("w_grid") not in grid_opts:
            ss["w_grid"] = "none"
        st.selectbox("Gridded layer", grid_opts, key="w_grid",
                     format_func=lambda k: "No gridded layer" if k == "none" else
                     f"{A.LAYERS[k]['title']} ({A.LAYERS[k]['origin']})")
        st.toggle("Use Copernicus map tiles (faster, online only)", key="w_tiles")
        for group, items in M.CATALOGUE.items():
            if group.startswith("Conditions"):
                continue
            st.caption(group)
            for lid, lab in items.items():
                st.checkbox(lab, key=f"w_{lid}")
            if group == "Pressures" and profile.get("sector"):
                ss.setdefault("w_mysector", True)
                st.checkbox(f"Zones and activities: only {P.SECTORS[profile['sector']].lower()}", key="w_mysector")
        if detail:
            st.caption(f"Zones: {A.zones_version()}. Cards: {A.cards_source()}.")

layers = {lid for g, items in M.CATALOGUE.items() for lid in items if ss.get(f"w_{lid}")}
if ss.get("w_grid") and ss["w_grid"] != "none":
    layers.add(ss["w_grid"])
day_s = str(day)


# ------------------------------------------------------------------------------------------ helpers
def selection_header(sel):
    inside = A.zones_containing(sel["lat"], sel["lon"], A._zones_stamp())
    n, secs = A.overlap_at(sel["lat"], sel["lon"], season)
    bits = [f"<b>{esc(sel['name'])}</b> <span class='bsv-note'>{sel['lat']:.3f} N, {sel['lon']:.3f} E</span>"]
    ov = f"{n} of 5 sectors overlap here ({season})" if n else f"outside the sector pressure zones ({season})"
    bits.append(f"<div class='bsv-note'>{esc(ov)}" + (f": {esc(secs.replace(',', ', '))}" if secs else "") + "</div>")
    nat = [z["sector"] for z in inside if z["kind"] == "Natura 2000"]
    if nat:
        bits.append(f"<div class='bsv-note'>Inside Natura 2000: {esc('; '.join(nat[:2]))}</div>")
    return "".join(bits)


# ------------------------------------------------------------------------------------------ screens
if screen == "Map":
    left, right = st.columns([2.15, 1])
    with left:
        only = profile.get("sector") if (profile.get("sector") and ss.get("w_mysector", True)) else None
        m, fd, msgs = M.build(ss.view, layers, day_s, season, None, detail, tiles_mode=ss.get("w_tiles", False),
                              only_sector=only)
        fg = folium.FeatureGroup(name="Selection")
        M.add_selection(fg, ss.sel)
        out = st_folium(m, height=560, use_container_width=True, key=f"map_{ss.get('map_nonce', 0)}",
                        feature_group_to_add=fg, returned_objects=["last_clicked"])
        for msg in msgs:
            st.caption(msg)
        click = (out or {}).get("last_clicked")
        if click and click != ss.get("last_click"):
            ss.last_click = click
            ss.sel = dict(name="Clicked point", lat=round(click["lat"], 4), lon=round(click["lng"], 4), kind="point", wkt=None)
            st.rerun()
    with right:
        sel = ss.sel
        st.markdown(f"<div class='bsv-box'>{selection_header(sel)}</div>", unsafe_allow_html=True)
        if fd:
            v = A.sample_field(fd, sel["lat"], sel["lon"])
            if v is not None:
                st.markdown(f"<div class='bsv-box'><span class='bsv-note'>{esc(fd['title'])} here</span><br>"
                            f"<span style='font-size:1.3rem;font-weight:650'>{v:.2f} {esc(fd['unit'])}</span> "
                            f"<span class='bsv-note'>{esc(fd['origin'])}, {esc(fd['time'])}"
                            + (f", {esc(fd['dataset'])}" if detail else "") + "</span></div>", unsafe_allow_html=True)
        cards = A.zone_cards(sel["lat"], sel["lon"], day_s, P.card_profile(profile), sel.get("wkt"), wait=6)
        if A.cards_pending(cards):
            st.markdown("<div class='bsv-box'><b>Health at a glance</b><div class='bsv-note'>Computing the cards for "
                        "this place (up to a minute the first time).</div></div>", unsafe_allow_html=True)
            PN.poll_cards(sel, day_s, profile)
            cards = []
        rows = "".join(f"<div style='display:flex;justify-content:space-between;margin:3px 0'><span>{esc(c['title'])}</span>"
                       f"{pill(c.get('status'))}</div>" for c in cards if c.get("status") != "no_data")
        if cards:
            st.markdown(f"<div class='bsv-box'><b>Health at a glance</b>{rows or '<div class=bsv-note>No cards with data here.</div>'}"
                    f"<div class='bsv-note' style='margin-top:4px'>Open 'Health cards' for the reasons.</div></div>",
                    unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns([4.3, 1.2])
    with c1:
        if ss.get("w_view") not in PN.VIEWS:
            ss["w_view"] = PN.VIEWS[0]
        view = st.segmented_control("Panel", PN.VIEWS, key="w_view", label_visibility="collapsed",
                                    format_func=PN.VIEW_SHORT.get) or PN.VIEWS[0]
    with c2:
        if view not in ("Health cards", "Waves and currents"):
            st.selectbox("Variable", list(A.VARIABLES), key="w_var", label_visibility="collapsed",
                         format_func=lambda k: PN.var_label(k, profile))
    var = ss.get("w_var", "sst")
    sel = ss.sel
    if view == "Health cards":
        PN.cards_view(sel, day_s, profile, ncols=3, compact=True)
    elif view == "Compare sources":
        PN.compare_view(sel, var, profile)
    elif view == "Anomaly":
        PN.anomaly_view(sel, var, profile)
    elif view == "Long-term trend":
        PN.trend_view(sel, var, profile)
    elif view == "Obs vs model":
        PN.obs_model_view(sel, var, profile)
    else:
        PN.vector_view(sel, profile)

elif screen == "Health cards":
    sel = ss.sel
    st.markdown(f"<div class='bsv-box'>{selection_header(sel)}</div>", unsafe_allow_html=True)
    if profile.get("role") == "public":
        st.caption("Green = normal for the season, amber = keep an eye on it, red = unusual and worth checking, grey = no data.")
    PN.cards_view(sel, day_s, profile, ncols=3, compact=False)

elif screen == "Sectors":
    SC.sectors_screen(profile, day_s, season)

else:
    SC.methods_screen(profile)

if detail:
    st.caption(f"Page built in {time.perf_counter() - T0:.2f} s.")
