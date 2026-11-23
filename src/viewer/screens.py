"""Sectors screen and Data and methods screen."""

from __future__ import annotations

import time

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from viewer import adapters as A
from viewer import maps as M
from viewer import panels as PN
from viewer import profiles as P
from viewer.style import table_html, OVERLAP, SECTOR, esc, pill

PRESSURES = {
    "ports": ["Ship traffic and underwater noise", "Oil and fuel spills, ballast water (new non-native species)",
              "Dredging of channels: sediment plumes, murkier water", "Contaminants: antifouling paint, metals, hydrocarbons"],
    "shipyards": ["Hull cleaning and antifouling paints (copper, legacy TBT)", "Metals and hydrocarbons in sediments",
                  "Coastal works, sea walls and beach nourishment change seabed habitats",
                  "Dredging and offshore construction"],
    "tourism": ["Wastewater load peaks in summer (bathing-water quality)", "Litter on beaches and at sea",
                "Beach nourishment and coastal protection works", "Boat traffic and anchoring near the shore"],
    "fishing": ["Removal of target species (sprat, turbot, rapa whelk)", "Bottom dredging for rapa whelk disturbs the seabed",
                "Bycatch of dolphins and harbour porpoise in turbot gillnets", "Lost nets (ghost fishing)"],
    "aquaculture": ["Organic matter under mussel longlines raises local oxygen demand",
                    "Farms are also receptors: blooms, toxins and low oxygen hit them first",
                    "Spread of non-native species with seed stock"],
}

SECTOR_START = {"ports": (44.12, 28.70, 10), "shipyards": (44.05, 28.66, 9), "tourism": (44.05, 28.66, 9),
                "fishing": (44.40, 29.05, 8), "aquaculture": (43.95, 28.70, 9)}


def sectors_screen(profile, day, season):
    ss = st.session_state
    default = ss.get("w_sector") or profile.get("sector") or "ports"
    ss.setdefault("w_sector", default)
    sector = st.segmented_control("Sector", list(P.SECTORS), key="w_sector",
                                  format_func=lambda k: P.SECTORS[k], label_visibility="collapsed") or default
    lab, col = SECTOR[sector]
    stamp = A._zones_stamp()
    left, right = st.columns([1.25, 1])
    with left:
        sites = A.sector_sites(sector, stamp)
        # frame: the sector's sites plus the Midia - Mangalia coast, where most activity is
        pts = [(s["lat"], s["lon"]) for s in sites] + [(44.34, 28.68), (43.79, 28.58)]
        view = fit_view(pts)
        m, _, msgs = M.build(view, {"overlap", "zones", "features"}, day, season, None,
                             P.show_detail(profile), only_sector=sector)
        for s in sites:
            folium.CircleMarker([s["lat"], s["lon"]], radius=7, color="#000", weight=2, fill=True, fill_color="#fff",
                                fill_opacity=0.9, tooltip=f"Site: {esc(s['name'])}").add_to(m)
        st_folium(m, height=470, use_container_width=True, returned_objects=[], key=f"secmap_{sector}_{season}")
        st.caption(f"{lab}: its zones (outlined), its activities (points and shapes), and the overlap with the other "
                   f"sectors underneath. Season: {season}. Dashed = location assumed, to confirm with NIMRD.")
    with right:
        st.markdown(f"### {esc(lab)}")
        cells = A.overlap_cells(season, stamp)
        mine = cells[cells.sectors.str.contains(sector, na=False)]
        if season == "winter" and sector == "tourism":
            st.info("Tourism zones are switched off outside the bathing season (1 June - 15 September).")
        if len(mine):
            dist = mine.n.value_counts().reindex(range(1, 6), fill_value=0)
            share = (mine.n >= 3).mean()
            c = st.columns(3)
            c[0].metric("Cells in zones", f"{len(mine):,}", help="Grid cells (500 m) inside this sector's zones.")
            c[1].metric("3+ sectors overlap", f"{share:.0%}", help="Share of this sector's cells where 3 or more sectors overlap.")
            c[2].metric("Highest overlap", f"{int(mine.n.max())} of 5")
            bars = "".join(
                f"<div style='display:flex;align-items:center;margin:2px 0'><span style='width:84px;font-size:12px'>"
                f"{n} sector{'s' if n > 1 else ''}</span><span style='display:inline-block;height:12px;width:"
                f"{max(2, 220 * dist[n] / max(dist.max(), 1)):.0f}px;background:{OVERLAP[n]};border:1px solid #ccc'></span>"
                f"<span style='font-size:12px;margin-left:6px'>{dist[n]:,}</span></div>" for n in range(1, 6))
            st.markdown(f"<div class='bsv-box'><b>Overlap level inside its zones</b>{bars}</div>", unsafe_allow_html=True)
        st.markdown("**Pressures this sector causes**")
        st.markdown("\n".join(f"- {p}" for p in PRESSURES[sector]))
        linked = [k for k, v in A.CARD_SECTORS.items() if sector in v]
        st.markdown("**Indicators that matter most here:** " + ", ".join(A.CARD_TITLES[k] for k in linked))
    st.markdown("#### Health at this sector's main sites")
    sites = A.sector_sites(sector, stamp)
    if not sites:
        st.info("No sites found for this sector.")
        return
    st.caption("Each row is one representative site: the sector's main features (official locations first) or its "
               "highest-overlap places, at least 15 km apart. Hover a status for its value and source; open a site for "
               "the full cards.")
    t0 = time.perf_counter()
    # stakeholders get the sentence for the sector on screen, not only their own
    prof = f"stakeholder:{sector}" if profile.get("role") == "stakeholder" else P.card_profile(profile)
    all_cards = A.cards_for_sites(sites, day, prof, wait=2.0)
    site_rows(sites, all_cards, linked, profile)
    if any(A.cards_pending(cs) for cs in all_cards):
        st.caption("Some sites are still being computed; the rows fill in by themselves.")
        poll_sites(sites, day, prof)
    elif P.show_detail(profile):
        st.caption(f"Site cards loaded in {time.perf_counter() - t0:.1f} s.")


SHORT = {"temperature": "Temperature", "oxygen": "Oxygen", "blooms": "Blooms", "clarity": "Clarity",
         "nutrients": "Nutrients", "bathing": "Bathing", "biodiversity": "Biodiversity", "drivers": "Drivers",
         "acidification": "pH"}


def _tip(c) -> str:
    v = c.get("value")
    vt = f"{PN._num(v, c.get('unit') or '')}" if v is not None else "no value"
    src = [s for s in (c.get("sources") or []) if s.get("dataset") != "zone sampling"][:1]
    st_ = f" Source: {src[0].get('label') or src[0].get('dataset')}, {src[0].get('date') or ''}" if src else ""
    return f"{c.get('title')}: {c.get('status')}, {vt}. {c.get('why') or ''}{st_}"


def site_rows(sites, all_cards, linked, profile):
    cols = linked or list(SHORT)
    head = "".join(f"<th style='padding:4px 6px;font-size:0.78rem;color:var(--bsv-muted);font-weight:600'>{SHORT.get(k, k)}</th>"
                   for k in cols)
    body = []
    for s, cs in zip(sites, all_cards):
        by = {c.get("id"): c for c in cs}
        cells = []
        for k in cols:
            c = by.get(k)
            if c is None:
                cells.append("<td></td>")
            elif c.get("pending"):
                cells.append("<td style='padding:4px 6px'><span class='bsv-note'>computing</span></td>")
            else:
                cells.append(f"<td style='padding:4px 6px' title='{esc(_tip(c))}'>{pill(c.get('status'))}</td>")
        body.append(f"<tr style='border-top:1px solid var(--bsv-line2)'><td style='padding:5px 6px'><b>{esc(s['name'])}</b><br>"
                    f"<span class='bsv-note'>near {esc(s.get('near', ''))}, {s['lat']:.3f} N {s['lon']:.3f} E - "
                    f"{esc(s.get('why', ''))}</span></td>{''.join(cells)}</tr>")
    st.markdown(f"<div style='overflow-x:auto'><table style='border-collapse:collapse;width:100%'>"
                f"<tr><th style='text-align:left;padding:4px 6px;font-size:0.78rem;color:var(--bsv-muted)'>Site</th>{head}</tr>"
                f"{''.join(body)}</table></div>", unsafe_allow_html=True)
    for s, cs in zip(sites, all_cards):
        if A.cards_pending(cs):
            continue
        with st.expander(f"Cards at {s['name']}"):
            shown = [c for c in cs if c.get("id") in cols] or cs
            cc = st.columns(3)
            for i, c in enumerate(shown):
                with cc[i % 3]:
                    st.markdown(PN.card_html(c, profile, compact=True), unsafe_allow_html=True)


def poll_sites(sites, day, prof):

    @st.fragment(run_every=4)
    def _poll():
        if all(A.cards_ready(s["lat"], s["lon"], day, prof) for s in sites):
            st.rerun(scope="app")

    _poll()


def fit_view(points: list[tuple[float, float]], width_px=650, height_px=470, pad=0.06, min_span=0.35) -> dict:
    """Centre and zoom computed in Python (Leaflet fitBounds breaks in containers hidden at load)."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    la0, la1 = min(lats) - pad, max(lats) + pad
    lo0, lo1 = min(lons) - pad, max(lons) + pad
    if la1 - la0 < min_span:
        c = (la0 + la1) / 2
        la0, la1 = c - min_span / 2, c + min_span / 2
    lat_c, lon_c = (la0 + la1) / 2, (lo0 + lo1) / 2
    lon_span = max(lo1 - lo0, 1e-3)
    lat_span = (la1 - la0) / np.cos(np.radians(lat_c))
    zoom = np.log2(min(width_px / lon_span, height_px / lat_span) * 360 / 256)
    return dict(lat=float(lat_c), lon=float(lon_c), zoom=int(np.clip(np.floor(zoom), 5, 13)))


def methods_screen(profile):
    detail = P.show_detail(profile)
    st.markdown("### Data and methods")
    st.markdown("Every value in this viewer shows where it comes from: **measured** (buoys, samples), **satellite** "
                "(a measured proxy for the surface), or **model** (computed, fills gaps, gives forecasts).")
    mods = A.status_of_modules()
    st.markdown("<div class='bsv-box'><b>Connected modules</b><br>" + "<br>".join(
        f"{esc(k)}: {'connected' if v else 'not yet (placeholder in use)'}" for k, v in mods.items())
        + f"<br>Pressure zones files: {esc(A.zones_version())}</div>", unsafe_allow_html=True)

    tabs = st.tabs(["Sources", "Reference periods and thresholds", "Quality control", "Natural or pressure?",
                    "What to investigate", "Limitations"])
    sl = A.md_tables(A.DOCS / "indicators" / "SHORTLIST.md")
    with tabs[0]:
        st.markdown("**Copernicus Marine Service** (model, reanalysis, satellite, in-situ; free account)")
        cat = A.catalog_table()
        cols = ["key", "origin", "product", "dataset_id", "variables", "resolution_deg", "frequency", "reference_years"]
        if not detail:
            cols = ["origin", "product", "variables", "reference_years"]
        st.markdown(table_html(cat[cols], height=320), unsafe_allow_html=True)
        st.markdown("**Other sources**")
        st.markdown(
            "- EMODnet Physics: buoys, coastal stations, tide gauges near Romania (ERDDAP, no login); QC flags 1 and 2 kept.\n"
            "- EMODnet Chemistry: 14,746 water samples 1963-2021 and DIVAnd seasonal climatologies (oxygen, nutrients).\n"
            "- EMODnet Human Activities, Bathymetry, Seabed Habitats; Natura 2000 (EEA); OpenStreetMap for ports, beaches, shipyards.\n"
            "- NOAA, ESA Ocean Colour CCI, Open-Meteo (waves, wind), GloFAS Danube discharge: no-login backups and drivers.")
        if detail:
            st.caption("Dataset IDs come from marinekit.sources.copernicus.CATALOG. Details: docs/data_sources/*.md.")
    with tabs[1]:
        st.markdown("Anomalies are always measured against the **same day of the year** (not the yearly mean). "
                    "OFFICIAL = Romanian MSFD 2024 (NIMRD) or an EU directive; OURS = a climatology band or a value we "
                    "propose. Draft thresholds are to be confirmed with NIMRD.")
        t = (sl.get("2. Indicator table") or [None])[0]
        if t is not None:
            t = t.map(A.strip_md)
            if not detail:
                t = t[["Indicator", "Reference / threshold", "Evidence", "Confidence"]]
            st.markdown(table_html(t, height=420), unsafe_allow_html=True)
        st.markdown("**Reference periods**: satellite SST 1991-2020 (WMO standard); satellite chlorophyll and Kd490 "
                    "1998-2022; model reanalysis 1993-2022; Danube discharge 1997-2025.")
    with tabs[2]:
        st.markdown("**In-situ QC rules**\n"
                    "- Only OceanSITES QC flags 1 (good) and 2 (probably good) are kept.\n"
                    "- Physical bounds per variable (e.g. temperature -2 to 35 °C, salinity 0 to 40) remove sensor spikes.\n"
                    "- New coastal buoys are shown greyed out ('under QC') until their units are confirmed.\n"
                    "- Shore stations are not used as sea temperature.")
        t = (sl.get("4. Data quality register (what to trust)") or [None])[0]
        if t is not None:
            st.markdown("**Data quality register**")
            st.markdown(table_html(t.map(A.strip_md)), unsafe_allow_html=True)
        p = A.platforms()
        if len(p):
            st.markdown("**In-situ platforms and their status**")
            show = p[["id", "name", "type", "lat", "lon", "time_end", "trust", "trust_note"]].rename(
                columns={"time_end": "last data", "trust": "status", "trust_note": "note"})
            st.markdown(table_html(show, height=300), unsafe_allow_html=True)
    with tabs[3]:
        st.markdown("One rule chain for all cards, applied in order. 'Pressure' is used only when no natural driver explains the event.")
        path = A.DOCS / "indicators" / "SHORTLIST.md"
        txt = path.read_text() if path.exists() else ""
        sec = txt.split("## 3.")[1].split("## 4.")[0] if "## 3." in txt else ""
        st.markdown("\n".join(l for l in sec.splitlines()[1:]))
    with tabs[4]:
        t = (sl.get('5. "Investigate" recommendations (the decision output)') or [None])[0]
        if t is not None:
            st.markdown(table_html(t.map(A.strip_md)), unsafe_allow_html=True)
    with tabs[5]:
        st.markdown(
            "- The model's chlorophyll, bottom oxygen and nutrients disagree with its own reanalysis: we use satellite and "
            "in-situ data for those, and keep the model for temperature, salinity and currents.\n"
            "- No bottom-oxygen sensor exists near the coast: the oxygen card has low confidence.\n"
            "- Nutrient observations end around 2020-2021: that card is historical only.\n"
            "- Satellite chlorophyll near the coast is affected by river sediment (medium confidence within about 20 km of shore).\n"
            "- Aquaculture sites, fishing landing points and some coastal works are located from place names: marked 'assumed'.\n"
            "- Basemap tiles and Copernicus map tiles need the internet; data layers and charts work offline from the cache.\n"
            "- Trends use annual means without correcting for autocorrelation, so the uncertainty is a lower bound.")
