"""Pressures page (direction B4): sector and season switches on the map, 3 headline numbers, main sites with
4 status squares each (summary and what to check on click), and the pressures the sector causes, folded.

Rules kept from the zones work: the map is a plain overlap count of the 5 sectors (0-5, ramp from
data/zones/overlap_style.json), assumed features are drawn dashed, tourism zones only 1 Jun - 15 Sep."""

from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from viewer import adapters as A
from viewer import maps as M
from viewer import profiles as P
from viewer import screens as SC
from viewer import shell as SH
from viewer.i18n import data, num, t
from viewer.style import SECTOR, STATUS, esc, status_square, theme_name, tokens

SHORT_SECTOR = {"ports": "Ports", "shipyards": "Shipyards", "tourism": "Tourism", "fishing": "Fishing",
                "aquaculture": "Aquaculture"}
# 4 health signs per sector, from adapters.CARD_SECTORS (the ones that matter most for that sector)
SITE_CARDS = {
    "ports": ["blooms", "clarity", "nutrients", "biodiversity"],
    "shipyards": ["clarity", "nutrients", "biodiversity", "oxygen"],
    "tourism": ["bathing", "blooms", "clarity", "temperature"],
    "fishing": ["temperature", "oxygen", "nutrients", "biodiversity"],
    "aquaculture": ["oxygen", "blooms", "temperature", "acidification"],
}
CARD_SHORT = {"temperature": "Temp.", "oxygen": "Oxygen", "blooms": "Blooms", "clarity": "Clarity",
              "nutrients": "Nutr.", "bathing": "Bathing", "biodiversity": "Life", "drivers": "Drivers",
              "acidification": "pH"}


# ------------------------------------------------------------------------------------------ helpers
def _season_default() -> str:
    day, _ = SH.day_season()
    return A.season_for_date(pd.Timestamp(day).date())


def _first_action(c) -> str:
    inv = c.get("investigate")
    if not inv:
        return ""
    if isinstance(inv, str):
        return inv
    for x in inv:
        if isinstance(x, dict) and x.get("action"):
            return x["action"]
        if isinstance(x, str) and x:
            return x
    return ""


def site_summary(cards: list[dict]) -> tuple[str, str]:
    """(summary, what to check) from the site's cards."""
    flagged = [c for c in cards if c.get("status") in ("alert", "watch")]
    nodata = [c for c in cards if (c.get("status") or "no_data") == "no_data"]
    if not cards:
        return t("No health signs computed here."), t("Nothing to check yet.")
    if not flagged:
        s = (t("All {n} signs with data are normal.", n=len(cards) - len(nodata)) if nodata
             else t("All {n} signs normal.", n=len(cards)))
        if nodata:
            s += " " + t("No data for {names}.", names=", ".join(data(c["title"]).lower() for c in nodata))
        return s, t("Nothing flagged.")
    alert = [data(c["title"]).lower() for c in flagged if c.get("status") == "alert"]
    watch = [data(c["title"]).lower() for c in flagged if c.get("status") == "watch"]
    bits = []
    if alert:
        bits.append(t("{names} on alert", names=", ".join(alert)))
    if watch:
        bits.append(t("{names} on watch", names=", ".join(watch)))
    first = sorted(flagged, key=lambda c: c.get("status") != "alert")[0]
    s = "; ".join(bits).capitalize() + ". " + data(first.get("why") or "")
    check = data(_first_action(first)) or t("Check the card on the Overview page.")
    dn = first.get("driver_note")
    if dn and not dn.startswith(("No anomaly", "No cause")):
        check += " " + t("Rule chain:") + " " + data(dn)
    return s.strip(), check


def _open_site(s):
    ss = st.session_state
    ss.sel = dict(name=s["name"], lat=float(s["lat"]), lon=float(s["lon"]), kind="point", wkt=None)
    ss.view = dict(lat=float(s["lat"]), lon=float(s["lon"]), zoom=10)
    ss.map_nonce = ss.get("map_nonce", 0) + 1
    ss.open_card = None
    ss["_goto"] = "overview"


def _toggle_site(i):
    ss = st.session_state
    ss.open_site = None if ss.get("open_site") == i else i


def _toggle_press():
    ss = st.session_state
    ss.w_press_open = not ss.get("w_press_open", False)


# ------------------------------------------------------------------------------------------ page
def page():
    ss = st.session_state
    profile = ss.profile
    detail = P.show_detail(profile)
    day_s, _ = SH.day_season()
    if ss.get("w_sector") not in SHORT_SECTOR:
        ss["w_sector"] = profile.get("sector") or "ports"
    if ss.get("w_pseason") not in ("winter", "summer"):
        ss["w_pseason"] = _season_default()
    sector, season = ss["w_sector"], ss["w_pseason"]
    lab, col = SECTOR[sector]
    stamp = A._zones_stamp()
    sites = A.sector_sites(sector, stamp)
    left, right = st.columns([2.3, 1], gap=None)
    with left:
        with st.container(key="bsv_map_full"):
            with st.container(key="map_tools_wide", horizontal=True):
                st.segmented_control(t("Sector"), list(SHORT_SECTOR), key="w_sector", format_func=lambda k: t(SHORT_SECTOR[k]),
                                     required=True, label_visibility="collapsed")
                st.segmented_control(t("Season"), ["winter", "summer"], key="w_pseason",
                                     format_func=lambda k: t(k.capitalize()),
                                     required=True, label_visibility="collapsed")
                with st.container(key="edges_ctl", horizontal=True, vertical_alignment="center"):
                    st.markdown(f"<span class='bsv-lbl'>{esc(t('Edges'))}</span>", unsafe_allow_html=True)
                    SH.edges_control(compact=True)
            edges = SH.edges()
            pts = [(s["lat"], s["lon"]) for s in sites] + [(44.34, 28.68), (43.79, 28.58)]
            view = SC.fit_view(pts, width_px=900, height_px=760)
            notes = ([t("Tourism zones are switched off outside the bathing season (1 June - 15 September).")]
                     if sector == "tourism" and season == "winter" else [])
            m, _, msgs = M.build(view, {"overlap", "zones", "features"}, day_s, season, None, detail,
                                 only_sector=sector, theme=theme_name(), notes=notes, edges=edges)
            tk = tokens()
            for i, s in enumerate(sites):
                folium.CircleMarker([s["lat"], s["lon"]], radius=8, color=tk["text"], weight=2, fill=True,
                                    fill_color=tk["panel"], fill_opacity=0.95,
                                    tooltip=t("Site {i}: {name}", i=i + 1, name=esc(SH.site_name(s["name"], 80)))).add_to(m)
                folium.Marker([s["lat"], s["lon"]], icon=folium.DivIcon(
                    html=f"<div style='font:600 11px sans-serif;color:{tk['text']};transform:translate(-3px,-7px)'>"
                         f"{i + 1}</div>")).add_to(m)
            st_folium(m, height=720, use_container_width=True, returned_objects=[],
                      key=f"pmap_{sector}_{season}_{theme_name()}_{edges}")
            if msgs:  # only when the map has no legend to hold them
                with st.container(key="map_tools_note"):
                    M.notes_slot(st.empty(), msgs)
    with right:
        with st.container(key="bsv_panel"):
            sname = t("summer, tourism on (1 Jun - 15 Sep)") if season == "summer" else t("winter, tourism off")
            st.markdown(f"<div class='bsv-sec'><div class='bsv-lbl'>{esc(t('Sector'))} &middot; {esc(sname)}</div>"
                        f"<div class='bsv-place'><span class='bsv-sq' style='width:12px;height:12px;background:{col};"
                        f"margin-right:10px;vertical-align:6px'></span>{esc(t(lab))}</div></div>", unsafe_allow_html=True)
            cells = A.overlap_cells(season, stamp)
            mine = cells[cells.sectors.str.contains(sector, na=False)]
            if len(mine):
                share = (mine.n >= 3).mean()
                st.markdown("<div class='bsv-stats bsv-stats3'>"
                            f"<div class='bsv-stat'><span class='bsv-lbl'>{esc(t('Cells (500 m)'))}</span><span class='v'>"
                            f"{num(f'{len(mine):,}')}</span></div>"
                            f"<div class='bsv-stat'><span class='bsv-lbl'>{esc(t('3+ overlap'))}</span><span class='v'>{share:.0%}</span></div>"
                            f"<div class='bsv-stat'><span class='bsv-lbl'>{esc(t('Highest'))}</span><span class='v'>{int(mine.n.max())}"
                            f"<span class='u'>{esc(t('of 5'))}</span></span></div></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='bsv-sec'><p class='bsv-vsub'>{esc(t('No zones of this sector in this season.'))}"
                            "</p></div>", unsafe_allow_html=True)
            site_list(sites, sector, season, day_s, profile)
            press = SC.PRESSURES[sector]
            is_open = ss.get("w_press_open", False)
            from viewer.overview import _CHEV, _CHEV_OPEN
            with st.container(key="crow_press"):
                st.markdown(f"<div class='bsv-row bsv-row4{' open' if is_open else ''}'>"
                            f"<span class='bsv-rt'>{esc(t('Pressures this sector causes'))}</span><span class='bsv-rv'>{len(press)}</span>"
                            f"<span class='bsv-chev'>{_CHEV_OPEN if is_open else _CHEV}</span><span></span><span></span>"
                            "<span></span></div>", unsafe_allow_html=True)
                st.button(t("Show the pressures this sector causes"), key="cbtn_press", on_click=_toggle_press)
            if is_open:
                with st.container(key="cdet_press"):
                    st.markdown("<ul class='bsv-chain'>" + "".join(f"<li>{esc(t(x))}</li>" for x in press) + "</ul>",
                                unsafe_allow_html=True)
            how = t("soft edges: zone limits fade out over 1-3 km because they are approximate; inside the zones the "
                    "colour is the exact count") if edges == "soft" else t("counted in each 500 m cell")
            note = t("Map: number of the 5 sectors whose zones overlap (no weights), {how}. Dashed outlines are assumed "
                     "locations, to confirm with NIMRD.", how=how)
            st.markdown(f"<div class='bsv-sec' style='border-bottom:0'><p class='bsv-note'>{esc(note)}</p></div>",
                        unsafe_allow_html=True)
    if ss.pop("_goto", None) == "overview":
        st.switch_page(SH.PAGE_OBJS["overview"])


@st.fragment
def site_list(sites, sector, season, day, profile):
    ss = st.session_state
    keys = SITE_CARDS[sector]
    heads = "".join(f"<span>{esc(t(CARD_SHORT[k]))}</span>" for k in keys)
    st.markdown(f"<div class='bsv-sites-head'><span class='bsv-lbl'>{esc(t('Main sites'))}</span>"
                f"<span class='cols'>{heads}</span></div>", unsafe_allow_html=True)
    if not sites:
        st.markdown(f"<div class='bsv-sec'><p class='bsv-vsub'>{esc(t('No sites found for this sector.'))}</p></div>",
                    unsafe_allow_html=True)
        return
    prof = f"stakeholder:{sector}" if profile.get("role") == "stakeholder" else P.card_profile(profile)
    all_cards = A.cards_for_sites(sites, day, prof, wait=2.0)
    pending = False
    from viewer.overview import _CHEV, _CHEV_OPEN
    for i, (s, cs) in enumerate(zip(sites, all_cards)):
        is_open = ss.get("open_site") == i
        waiting = A.cards_pending(cs)
        pending = pending or waiting
        by = {c.get("id"): c for c in cs} if not waiting else {}
        sq = []
        for k in keys:
            c = by.get(k)
            stt = (c.get("status") or "no_data") if c else "no_data"
            tip = f"{t(CARD_SHORT[k])}: {STATUS[stt][1] if not waiting else t('computing')}"
            sq.append(f"<span class='cell' title='{esc(tip)}'>{status_square(stt, 10)}</span>")
        n, _ = A.overlap_at(s["lat"], s["lon"], season)
        note = t("near {place}", place=SH.place_name(s.get("near") or "")).strip()
        if n and n > 1:
            note += " · " + t("{n} sectors overlap", n=n)
        with st.container(key=f"crow_site{i}"):
            st.markdown(f"<div class='bsv-site{' open' if is_open else ''}'>"
                        f"<span class='bsv-chev'>{_CHEV_OPEN if is_open else _CHEV}</span>"
                        f"<span class='nm'><span class='t'>{i + 1}. {esc(SH.site_name(s['name']))}</span><span class='n'>{esc(note)}</span></span>"
                        f"<span class='cols'>{''.join(sq)}</span></div>", unsafe_allow_html=True)
            st.button(t("Close site {name}" if is_open else "Open site {name}", name=SH.site_name(s["name"])),
                      key=f"cbtn_site{i}",
                      on_click=_toggle_site,
                      args=(i,))
        if is_open:
            with st.container(key=f"cdet_site{i}"):
                if waiting:
                    st.markdown(f"<div class='bsv-det1'>{esc(t('Still computing the health signs for this site.'))}</div>",
                                unsafe_allow_html=True)
                else:
                    summ, check = site_summary([by[k] for k in keys if k in by])
                    st.markdown(f"<div class='bsv-det1'><span>{esc(summ)}</span><span><span class='bsv-lbl'>"
                                f"{esc(t('Check'))}</span> {esc(check)}</span></div>", unsafe_allow_html=True)
                st.button(t("Full report for this site"), key=f"cchart_site{i}", on_click=_open_site, args=(s,))
    if pending:
        SC.poll_sites(sites, day, prof)
    if ss.get("_goto") == "overview":
        ss.pop("_goto")
        st.switch_page(SH.PAGE_OBJS["overview"])
