# Coordinator handover

For a fresh Claude session taking over as coordinator. Read this, then `CLAUDE.md`, `docs/STATUS.md` and `docs/plan/WORKFLOW.md`. Update this file before handing over again.

Last update: 23 Nov 2026, evening (Day 1 of the hackathon). Pitch: Day 2 (24 Nov), 11:00, in Constanța.

## The user and how they work
- Andrei: GIS background, works on the **design** of the app (`design` branch). Colleague **josephfournier0212** works on data analysis (`data` branch); his GitHub invite is sent, and his setup is driven by `CLAUDE.md` section 0.
- Wants Claude as **coordinator**: plan, split work into sub-sessions or agents with clear briefs, verify results yourself (run the code, look at the output), integrate, and report briefly.
- **Usage must stay efficient**: at most 1-2 working sessions at a time, light verification (one pass, no repeated browser walkthroughs), cheaper models for mechanical work, and archive finished sessions (with the user's okay).
- **No emoji anywhere** (UI, docs, messages). Plain text, bullets, simple colours.
- Prefers simple, explainable methods over clever ones. For example, the weights and composite index were dropped for a plain overlap count.
- QGIS 3.44 runs locally with a QGIS MCP server. Only the coordinator drives the GUI QGIS (project `gis/black_sea_pressures.qgz`).

## Where things are
- Repo: https://github.com/coastal-andy/black-sea-health-viewer (public). Branches `main`, `design` and `data` are all at the same commit as of this handover; the local checkout is on `design`.
- Product: `src/viewer/` (Streamlit, port 8502). Data and science: `src/marinekit/` (sources, indicators, datahub, pressure_zones).
- Science reference: `docs/indicators/SHORTLIST.md` (cards, rule chain, data quality register, investigate actions, NIMRD questions).
- Pressure zones: `docs/pressure_zones.md`, `data/zones/` (v2: overlap count, tourism on 1 Jun-15 Sep, confidence levels, AIS anchorages).
- Challenge brief and scoring: `docs/challenge/CHALLENGE_04.md`. Team plan page: https://claude.ai/artifact/B5RmGDig2zsHdZ8eUj88wF (partly outdated: it still mentions weights).
- Copernicus Marine login is valid on Andrei's Mac (`~/.copernicusmarine/`). The data cache is in `data/cache/` (not in git; rebuild it with `scripts/preload_cache.py`).

## Sessions
| Session | State |
|---|---|
| data agents, indicator research x3, vector-viz, indicator-cards | archived; work committed |
| pressure-zones (`local_b6bdd44c-0e25-4295-a92b-c3d27efa5123`) | idle, but not archivable while a background process runs; work committed. Archive it when free (ask the user). |
| viewer (`local_19f8d34b-2ff6-4e06-903c-2745dd9bdbf0`) | idle; it owns the running Streamlit server on 8502. Archive it when the server isn't needed (ask the user). |

## Open tasks, in priority order
1. **Final viewer check as each profile** (public, student, stakeholder, researcher): one quick pass each. The overlap-hatching, sector-sites and framing fixes are reported done but not re-checked by the coordinator.
2. **Offline test**: run the preload, turn Wi-Fi off, and run the demo path.
3. **Pitch**: deck and demo script in `pitch/` (empty). It must cover the 5 sprints: (1) the pressure map, (2) the architecture (the diagram is in the team plan page), (3) the data-to-decision canvas (SHORTLIST sections 3 and 5), (4) the prototype, (5) impact and roadmap. Scoring is in CHALLENGE_04.md.
4. **NIMRD questions**: SHORTLIST section 6 and the to-confirm list in `docs/pressure_zones.md`. Ask the lecturers before the pitch.
5. Optional: update the team plan artifact to match decisions (no weights, overlap count, seasons).

## Decisions already made (don't reopen)
- Pressure map = plain count of overlapping sectors (0-5); no weights or index. Tourism zones only 1 Jun-15 Sep.
- One buffer per activity: law or literature where possible, otherwise a stated rule (see `data/zones/buffers.yaml`).
- Combined vector view: colour = magnitude, arrows = direction, arrow length = wave period.
- The viewer opens with a 3-step questionnaire (profile, focus or sector, goal).
- Nutrients from observations and climatology only; Copernicus model nitrate and phosphate are unusable.

## Gotchas
- Copernicus switches catalogue release on 24 Nov at 15:00 Romanian time (after the pitch). The cache protects the demo.
- `preview_start` with a server name fails on the Desktop folder (macOS permission). Start servers with Bash in the background and open `http://localhost:PORT` with `preview_start(url=...)`.
- Folium maps in hidden Streamlit tabs: set centre and zoom in Python, not with `fitBounds`.
- Archiving sessions in auto mode: a hook adds a `session` label. Retry once with the exact input from the error message.
