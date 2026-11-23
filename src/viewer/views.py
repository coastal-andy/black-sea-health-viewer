"""The five pages of the rail (direction B). Each is a plain function passed to st.Page."""

from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium

from viewer import adapters as A
from viewer import maps as M
from viewer import panels as PN
from viewer import profiles as P
from viewer import screens as SC
from viewer import shell as SH
from viewer.style import esc, theme_name

MAP_RATIO = [2.6, 1]  # map column : docked panel


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
                with st.popover("Map layers", width="stretch"):
                    _layer_controls(profile)
            only = profile.get("sector") if (profile.get("sector") and ss.get("w_mysector", True)) else None
            m, fd, msgs = M.build(ss.view, layers, day_s, season, None, detail, tiles_mode=ss.get("w_tiles", False),
                                  only_sector=only, theme=theme_name())
            fg = folium.FeatureGroup(name="Selection")
            M.add_selection(fg, ss.sel)
            out = st_folium(m, height=760, use_container_width=True,
                            key=f"map_{ss.get('map_nonce', 0)}_{theme_name()}",
                            feature_group_to_add=fg, returned_objects=["last_clicked"])
            if msgs:
                with st.container(key="map_msgs"):
                    for msg in msgs:
                        st.caption(msg)
            click = (out or {}).get("last_clicked")
            if click and click != ss.get("last_click"):
                ss.last_click = click
                ss.sel = dict(name="Clicked point", lat=round(click["lat"], 4), lon=round(click["lng"], 4),
                              kind="point", wkt=None)
                st.rerun()
    with right:
        with st.container(key="bsv_panel"):
            with st.container(key="bsv_pad"):
                SH.profile_menu()
            sel = ss.sel
            st.markdown(f"<div class='bsv-sec'>{SH.selection_header(sel, season)}</div>", unsafe_allow_html=True)
            if fd:
                v = A.sample_field(fd, sel["lat"], sel["lon"])
                if v is not None:
                    st.markdown(f"<div class='bsv-sec'><div class='bsv-lbl'>{esc(fd['title'])} here &middot; "
                                f"{esc(fd['origin'])}, {esc(fd['time'])}</div><span class='bsv-num' style='font-size:26px'>"
                                f"{v:.2f} {esc(fd['unit'])}</span></div>", unsafe_allow_html=True)
            with st.expander("Date and season"):
                SH.date_controls()
            with st.container(key="bsv_cards"):
                PN.cards_view(sel, day_s, profile, ncols=1, compact=True)


# ------------------------------------------------------------------------------------------ Water quality
def water():
    ss = st.session_state
    profile = ss.profile
    with st.container(key="page_body"):
        SH.page_head("Water quality", "Water")
        views = ["Compare sources", "Anomaly", "Long-term trend", "Obs vs model"]
        if ss.get("w_wview") not in views:
            ss["w_wview"] = "Anomaly"
        c1, c2 = st.columns([3, 1.2])
        with c1:
            view = st.segmented_control("View", views, key="w_wview", label_visibility="collapsed",
                                        format_func=PN.VIEW_SHORT.get) or "Anomaly"
        with c2:
            st.selectbox("Variable", list(A.VARIABLES), key="w_var", label_visibility="collapsed",
                         format_func=lambda k: PN.var_label(k, profile))
        var = ss.get("w_var", "sst")
        sel = ss.sel
        if view == "Compare sources":
            PN.compare_view(sel, var, profile)
        elif view == "Anomaly":
            PN.anomaly_view(sel, var, profile)
        elif view == "Long-term trend":
            PN.trend_view(sel, var, profile)
        else:
            PN.obs_model_view(sel, var, profile)


# ------------------------------------------------------------------------------------------ Coast and seabed
def seabed():
    ss = st.session_state
    with st.container(key="page_body"):
        SH.page_head("Coast and seabed", "Seabed")
        PN.vector_view(ss.sel, ss.profile)


# ------------------------------------------------------------------------------------------ Pressures
def pressures():
    ss = st.session_state
    day_s, season = SH.day_season()
    with st.container(key="page_body"):
        SH.page_head("Pressures", "Five sectors, overlap count 0-5")
        SC.sectors_screen(ss.profile, day_s, season)


# ------------------------------------------------------------------------------------------ Methods
def methods():
    ss = st.session_state
    with st.container(key="page_body"):
        SC.methods_screen(ss.profile)
