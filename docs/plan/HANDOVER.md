# Coordinator handover

For a fresh Claude session taking over as coordinator. Read this, then `CLAUDE.md`, `docs/STATUS.md` and `docs/plan/WORKFLOW.md`. Update this file before handing over again.

Last update: 23 Nov 2026, late evening (Day 1 of the hackathon), second coordinator. Pitch: Day 2 (24 Nov), 11:00, in Constanța.

## The user and how they work
- Andrei: GIS background, owns the **design** of the app (`design` branch). Colleague **Joseph (josephfournier0212)** owns data analysis (`data` branch). He has accepted the repo invite and cloned it, but has **pushed nothing yet** (as of 23 Nov late evening `data` = `main` = 10d31db, no pull requests). Check `git log main..origin/data` before touching anything near his area.
- Wants Claude as **coordinator**: plan, delegate self-contained work to sub-sessions, verify results yourself, report briefly.
- **Usage must stay lean**: at most 1-2 working sessions at a time, one light verification pass, archive finished sessions (with the user's okay).
- **No emoji anywhere.** Plain text, bullets, simple colours.
- Prefers simple, explainable methods. Dislikes UI that looks "AI-made / Claude-like" (rounded white cards, pills, tinted rows, cream and serif). Wants a professional, uncluttered look: essentials first, details on click.
- QGIS 3.44 runs locally with a QGIS MCP server; only the coordinator drives it (project `gis/black_sea_pressures.qgz`).

## Where things are
- Repo: https://github.com/coastal-andy/black-sea-health-viewer (public). Local checkout on `design`, which is 1 commit ahead of `main` plus this handover commit.
- Product: `src/viewer/` (Streamlit, port 8502). Data and science: `src/marinekit/`.
- Science reference: `docs/indicators/SHORTLIST.md`. Pressure zones: `docs/pressure_zones.md`, `data/zones/`.
- Challenge brief and scoring: `docs/challenge/CHALLENGE_04.md`.
- **Redesign mockup (approved direction B):** canvas https://claude.ai/artifact/WW1uNDRq37LpgqBoMnMbTk (private to Andrei; boards B1-B4 in the bottom two rows; the top five boards are the rejected first direction). Source copies of the four B pages: `docs/plan/design_mockup/*.dc.html` (HTML with inline styles; the colours, fonts and layout can be lifted from there).
- Copernicus Marine login valid on Andrei's Mac. Data cache `data/cache/` (~500 MB, not in git).

## State at this handover
- Viewer final check done for all four profiles (public, student, stakeholder, researcher): overlap hatched over a dimmed gridded layer, Sectors screen has 4 real sites per sector, sector maps framed correctly. Fixed: map legend is now collapsible and height-capped (`src/viewer/maps.py`, commit 523642e on `design`).
- Preload done: `scripts/preload_cache.py` 0 failures over 39 points; `MARINEKIT_OFFLINE=1` check passed in 29 s. Only basemap tiles need internet. The user says the venue has Wi-Fi.
- Streamlit server on 8502 was restarted by the coordinator (background process, `--server.runOnSave true`). Module edits under `src/viewer/` still need a server restart to show (kill the `streamlit run` process and start it again).
- Old sessions (viewer, pressure-zones) are archived; all their work is committed.

## Open tasks, in priority order
1. **Rebuild the Streamlit viewer in design direction B** (the user approved it; see the spec below). Work only in `src/viewer/` and `.streamlit/` on `design`. Check Joseph's commits first so the Water quality and Coast and seabed pages use his analysis rather than duplicating it.
2. **Pitch deck and demo script** in `pitch/` (empty). Must cover the 5 sprints: pressure map, architecture, data-to-decision canvas (SHORTLIST sections 3 and 5), prototype, impact and roadmap. Scoring in CHALLENGE_04.md. Deferred by the user for now.
3. **NIMRD questions**: SHORTLIST section 6 and the to-confirm list in `docs/pressure_zones.md`. Deferred by the user for now.
4. Small issues for the `data` side (to pass to Joseph, or as GitHub issues only if the user okays it; the repo is public):
   - SST in the summary box (13.75 °C, gridded field pixel) differs from the temperature card (13.4 °C, L4 at 1.1 km).
   - Clarity card shows 2.5 m but its text says "about 3 m".
   - Shipping-lane hover shows "buffer 0 m (rule)".
   - Pressure-zones notes for the pitch: fishing is under-counted near shore (AIS covers vessels of 15 m or more only); ANAR scanned PDFs not read (could move some aquaculture perimeter corners).

## Redesign spec: direction B
Look:
- Dark, map-first, like real ocean-data viewers (Global Fishing Watch, Copernicus MyOcean). Background #06131D, panels #0C1F2C, rail #0A1B27, hairlines #1E3646 / #16303F, text #E6EEF3, muted #8FA7B6, accent #4CC3E6.
- Status colours on dark: normal #2BB38A, watch #F2B134, alert #F07B3F, no data #6E8392, shown as small squares with a text label.
- Fonts: Barlow (UI) and Barlow Condensed (large numbers, place names), tabular numbers. Small uppercase letter-spaced labels.
- Square-ish corners (4 px), 1 px dividers instead of cards and shadows. No pills, no tinted cards, no emoji.

Layout:
- Left icon rail (72 px): Overview, Water, Seabed, Pressures, Methods. Replaces the top tabs.
- Map fills the page. The docked panel goes on the **right**, because the coast is on the left of the map.
- A compact legend that can be hidden; a full-screen map button; a bottom timeline (last 7 days, today, forecast +5) on the overview.

Pages:
- B1 Overview: profile tabs (Public, Student, Sector, Research) at the top of the panel; place name, one verdict sentence, counts; 9 compact rows (status, title, value, one line, origin). Click a row to open "means" and "source" plus a link to the chart.
- B2 Water quality (Joseph's split): variable list (temperature, salinity, oxygen, chlorophyll-a, clarity, nutrients, pH); 4 headline numbers; 60-day chart against the usual range; folded sections: Sources, Natural or pressure? (rule chain), Data (CSV).
- B3 Coast and seabed (Joseph's split, morphology): wave/current/wind/depth map (colour = magnitude, arrows = direction, arrow length = period, from `viewer.vectorviz`); 4 condition rows with "why it matters" on click; depth profile in a bottom panel you can hide (EMODnet Bathymetry).
- B4 Pressures: sector and season switches on the map; 3 headline numbers; main sites with 4 status squares each, click for summary and what to check; "Pressures this sector causes" folded.

Streamlit notes for the rebuild: multipage via `st.navigation`, CSS injected with `st.markdown(..., unsafe_allow_html=True)` plus a dark `.streamlit/config.toml` theme, folium `Fullscreen` plugin, details on click via `st.expander` styled flat or a selected-row state. Keep the existing interfaces in `src/viewer/adapters.py` and the `marinekit` contracts unchanged.

## Decisions already made (don't reopen)
- Pressure map = plain count of overlapping sectors (0-5); no weights or index. Tourism zones only 1 Jun-15 Sep.
- One buffer per activity (law or literature where possible, else a stated rule).
- Combined vector view: colour = magnitude, arrows = direction, arrow length = wave period.
- The viewer adapts to the profile (public, student, stakeholder with sector, researcher).
- Nutrients from observations and climatology only; Copernicus model nitrate and phosphate unusable.
- Hosting: keep Streamlit and restyle it (Streamlit Community Cloud if hosted; GitHub Pages was rejected because it cannot run Python).
- Design: direction B above.

## Gotchas
- Copernicus switches catalogue release on 24 Nov at 15:00 Romanian time (after the pitch). The cache protects the demo.
- `preview_start` with a server name fails on the Desktop folder (macOS permission). Start servers with Bash in the background and open `http://localhost:PORT` with `preview_start(url=...)`.
- Folium maps in hidden Streamlit tabs: set centre and zoom in Python, not with `fitBounds`.
- Archiving sessions in auto mode: a hook adds a `session` label. Retry once with the exact input from the error message.
- The Design canvas artifact is private; Joseph cannot open it until Andrei shares it from the page's Share menu.
