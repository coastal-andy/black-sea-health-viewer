"""The five pages of the rail (direction B). Each is a plain function passed to st.Page."""

from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from viewer import adapters as A
from viewer import maps as M
from viewer import overview as OV
from viewer import panels as PN
from viewer import profiles as P
from viewer import screens as SC
from viewer import pressures as PR
from viewer import seabed as SB
from viewer import shell as SH
from viewer import water as WQ
from viewer.style import esc, theme_name

MAP_RATIO = [2.3, 1]  # map column : docked panel


def map_key(prefix, *parts) -> str:
    """A short widget key that changes whenever any of the parts changes."""
    import hashlib
    return f"{prefix}_" + hashlib.md5(repr(parts).encode()).hexdigest()[:10]


def _layers() -> set:
    ss = st.session_state
    layers = {lid for g, items in M.CATALOGUE.items() for lid in items if ss.get(f"w_{lid}")}
    if ss.get("w_grid") and ss["w_grid"] != "none":
        layers.add(ss["w_grid"])
    return layers


def _layer_controls(profile: dict):
    ss = st.session_state
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
        if group == "Pressures":
            SH.edges_control()


# ------------------------------------------------------------------------------------------ Overview
def overview():
    ss = st.session_state
    profile = ss.profile
    detail = P.show_detail(profile)
    day_s, season = SH.day_season()
    layers = _layers()
    left, right = st.columns(MAP_RATIO, gap=None)
    with left:
        with st.container(key="bsv_map"):
            with st.container(key="map_tools"):
                SH.place_picker()
                with st.popover("Map layers and season", width="stretch"):
                    _layer_controls(profile)
                    SH.season_control()
                note_slot = st.empty()  # map notes without a legend to go in (rare): a short line here
            only = profile.get("sector") if (profile.get("sector") and ss.get("w_mysector", True)) else None
            edges = SH.edges()
            m, fd, msgs = M.build(ss.view, layers, day_s, season, None, detail, tiles_mode=ss.get("w_tiles", False),
                                  only_sector=only, theme=theme_name(), edges=edges)
            fg = folium.FeatureGroup(name="Selection")
            M.add_selection(fg, ss.sel)
            # st_folium draws the base map only when it first mounts; later changes to layers, date, season or
            # legend are ignored unless the key changes, so the key carries every input that changes the base map
            mkey = map_key("map", ss.get("map_nonce", 0), theme_name(), sorted(layers), day_s, season,
                           ss.get("w_tiles", False), only, ss.view, edges)
            out = st_folium(m, height=700, use_container_width=True, key=mkey,
                            feature_group_to_add=fg, returned_objects=["last_clicked"])
            M.notes_slot(note_slot, msgs)
            OV.timeline()
            click = (out or {}).get("last_clicked")
            if click and click != ss.get("last_click"):
                ss.last_click = click
                ss.sel = dict(name="Clicked point", lat=round(click["lat"], 4), lon=round(click["lng"], 4),
                              kind="point", wkt=None)
                ss.open_card = None
                st.rerun()
    with right:
        with st.container(key="bsv_panel"):
            overview_panel(day_s, season)


@st.fragment
def overview_panel(day_s, season):
    """The docked panel. A fragment: tabs and row clicks rerun only this, not the map."""
    ss = st.session_state
    OV.profile_tabs()
    profile = ss.profile
    sel = ss.sel
    cards = A.zone_cards(sel["lat"], sel["lon"], day_s, P.card_profile(profile), sel.get("wkt"), wait=1.5)
    pending = A.cards_pending(cards)
    n, secs = A.overlap_at(sel["lat"], sel["lon"], season)
    head = SH.selection_header(sel, season)
    if pending:
        st.markdown(f"<div class='bsv-sec'>{head}<p class='bsv-verdict'>Computing the health signs for this "
                    "place.</p><p class='bsv-vsub'>The first time takes up to a minute; after that it is "
                    "cached. The rows appear by themselves.</p></div>", unsafe_allow_html=True)
        PN.poll_cards(sel, day_s, profile)
        return
    if profile.get("role") == "public":
        cards = [c for c in cards if c.get("status") != "no_data"] + \
                [c for c in cards if c.get("status") == "no_data"]
    v1, v2 = OV.verdict(cards, profile, season, n, secs, day_s)
    st.markdown(f"<div class='bsv-sec'>{head}<p class='bsv-verdict'>{esc(v1)}</p>"
                f"<p class='bsv-vsub'>{esc(v2)}</p>{OV.counts_html(cards)}</div>", unsafe_allow_html=True)
    OV.card_rows(cards, profile)
    with st.container(key="panel_foot", horizontal=True, vertical_alignment="center"):
        st.page_link(SH.PAGE_OBJS["water"], label="Water quality analysis")
        st.markdown(f"<span class='bsv-note'>vs. usual for {pd.Timestamp(day_s):%d %B}, "
                    f"cards from the {esc(A.cards_source())}</span>", unsafe_allow_html=True)
    if ss.pop("_goto", None):
        st.switch_page(SH.PAGE_OBJS["water"])


# ------------------------------------------------------------------------------------------ Water quality
def water():
    WQ.page()


# ------------------------------------------------------------------------------------------ Coast and seabed
def seabed():
    SB.page()


# ------------------------------------------------------------------------------------------ Pressures
def pressures():
    PR.page()


# ------------------------------------------------------------------------------------------ Methods
def methods():
    ss = st.session_state
    with st.container(key="page_body"):
        SC.methods_screen(ss.profile)
