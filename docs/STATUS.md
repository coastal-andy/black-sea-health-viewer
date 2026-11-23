# Project status (23 Nov 2026, evening)

Challenge 04 Ecosystem Health. Pitch: Day 2, 11:00. Plan and interfaces: [plan/WORKFLOW.md](plan/WORKFLOW.md).

## How to run
```bash
.venv/bin/streamlit run src/viewer/app.py --server.port 8502   # the viewer
.venv/bin/python scripts/preload_cache.py                      # warm the cache for an offline demo
.venv/bin/python -m pytest -q tests/test_indicators.py         # indicator tests
```
The QGIS project is `gis/black_sea_pressures.qgz`. The old starter dashboard (`src/app.py`, port 8501) is no longer part of the product.

## Done and verified
| Piece | Where | State |
|---|---|---|
| Data access: Copernicus Marine, EMODnet in-situ and chemistry, EMODnet layers, NOAA/ESA/Open-Meteo/GloFAS | `src/marinekit/sources/` | live fetches checked; on-disk cache; docs in `docs/data_sources/` |
| Indicator research: physical, chemical, biological | `docs/indicators/*.md`, `scripts/indicators/*_check.py` | 21 indicators computed live at Constanța |
| Combined shortlist: 9 health cards, natural-vs-pressure rule chain, data quality register, investigate actions | `docs/indicators/SHORTLIST.md` | done |
| Pressure zones v2: 330 features with confidence, one buffer per activity, overlap count 0-5, summer/winter, AIS-derived anchorages | `src/marinekit/pressure_zones.py`, `data/zones/`, `docs/pressure_zones.md` | done; loaded in QGIS |
| Combined waves/currents/wind view | `src/viewer/vectorviz.py`, `docs/viz/` | done; works inside the viewer |
| Indicator cards and data hub | `src/marinekit/indicators.py`, `datahub.py`, `tests/test_indicators.py` | tests 8/8; offline preload finishing |
| Viewer: questionnaire, map, health cards, source comparison, anomaly, trend, obs vs model, sectors, methods | `src/viewer/` | works end to end |

## In progress
- Viewer fixes: overlap colour clash with warm map layers, sector cards at representative sites, sector map framing.

## Still needed before the pitch
1. Final run-through as each profile (public, student, stakeholder, researcher).
2. Full preload, then test with Wi-Fi off.
3. Pitch deck and demo script (`pitch/` is empty), covering:
   - Sprint 1 pressure map: QGIS export or viewer screenshot
   - Sprint 2 and 3 architecture diagram: in `docs/plan/team_plan.html`
   - Sprint 5 impact and roadmap
4. Ask NIMRD the questions in `docs/indicators/SHORTLIST.md` section 6 and `docs/pressure_zones.md` (to-confirm list).

## Known limits to say openly in the pitch
- Copernicus model nitrate and phosphate are unreliable, so nutrients come from historical samples and climatology.
- Seabed oxygen is model-only (there is no seabed sensor), so its confidence is low.
- The new coastal buoys EUXRoCB0x are not quality-controlled. Station 15480 is on shore.
- Some fishing and shipyard features are assumed (landing points, pound nets, dumping sites) and are drawn dashed.
- The Copernicus catalogue changes on 24 Nov at 15:00 Romanian time, after the pitch. The cache covers the demo.

## Update 23 Nov 2026, late evening (design branch)
- Viewer rebuilt in design direction B: dark by default with a Light switch, a 72 px icon rail, and five pages (Overview, Water quality, Coast and seabed, Pressures, Methods). Commits e4f3bc5, 1779536, d8d5c6c, 857a8f6, 5c495c8 on `design`. Details and known gaps are in `docs/plan/HANDOVER.md`, under "Built".
