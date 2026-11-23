# Build workflow: Black Sea Health Viewer (Challenge 04)

Every work session reads this file first. The main session coordinates, checks each piece and integrates. Workstreams own separate files and talk only through the interfaces below.

## Decisions (from the user, 23 Nov evening)
1. **No weights, no composite index.** The pressure map is a plain **overlap count**: how many of the 5 sectors are present in a cell (0–5). 5 of 5 is the highest pressure. Weighted fields are removed from the outputs the viewer uses; the earlier weights work stays in git history and docs only as background.
2. **Seasonality is binary.** Tourism zones are **on in the bathing season (1 June – 15 September)** and **off outside it**. Other sectors are year-round unless an official closure is confirmed; e.g. a confirmed fishing ban period may be added later as a second toggle.
3. **Zones must be confirmed.** Every feature carries its source and a confidence level: `official` (port authority, ANPA, EMODnet, EEA, legal text), `mapped` (OpenStreetMap, satellite-visible), or `assumed`. Assumed features are drawn hatched or dashed and listed for NIMRD to confirm.
4. **Buffer method.** Use a distance from the literature or the law where one exists; otherwise a simple, stated buffer rule (e.g. 300 m seaward from the beach line for tourism). One buffer per activity type, no inner/middle/outer rings.
5. **Combined vector visualisation.** Waves, currents and wind are shown as one view: magnitude as a colour field, direction as arrows, and (for waves) period as arrow length. They are not separate maps.
6. **No emoji** anywhere in the UI or docs. Plain text, bullets, simple status colours.

## Workstreams and ownership

| Workstream | Session | Owns (writes only these) | Output |
|---|---|---|---|
| Z. Pressure zones v2 | pressure-zones | `src/marinekit/pressure_zones.py`, `data/zones/`, `docs/pressure_zones.md` | confirmed features, simple buffers, overlap grid for summer and winter |
| V. Vector visualisation | vector-viz | `src/viewer/vectorviz.py`, `scripts/viz/`, `docs/viz/` | map layer and point chart combining magnitude, direction and period |
| I. Indicator cards | indicator-cards | `src/marinekit/indicators.py`, `src/marinekit/datahub.py`, `scripts/preload_cache.py`, `tests/test_indicators.py` | one function per health card, same output format |
| U. Viewer | viewer | `src/viewer/` except `vectorviz.py`; `.streamlit/` theme | the app: questionnaire, map, panels, sectors view |
| Coordination | main | `docs/plan/`, `docs/indicators/SHORTLIST.md` | checks, integration, QGIS project `gis/` |

Shared and read-only for everyone: `src/marinekit/sources/*` (data access, already verified) and `docs/indicators/*.md` (indicator research). If a source module needs a fix, ask the main session.

## Interfaces

### Z → U: pressure zones files (`data/zones/`, EPSG:4326)
- `sector_features.geojson`: properties `feature_id, sector, activity, name, source, source_url, confidence (official|mapped|assumed), season (all|summer)`.
- `sector_zones.geojson`: one buffer polygon per activity, with properties `sector, activity, buffer_m, buffer_basis (law|literature|rule), basis_ref, season, confidence`.
- `overlap_grid.geojson` (250 m cells over the Romanian shelf): `cell_id, n_summer, n_winter (0-5), sectors_summer, sectors_winter, lon, lat`.
- `overlap_summer.geojson`, `overlap_winter.geojson`: dissolved polygons per count level (1–5), for fast map drawing.
- `buffers.yaml`: the buffer table, the single editable config.
- Helper: `pressure_zones.season_for_date(date) -> "summer"|"winter"`.

### V → U: vector visualisation (`src/viewer/vectorviz.py`)
- `field_layer(m, ds, kind, time)`: adds to a folium map a colour field of magnitude, direction arrows on a thinned grid and, for waves, arrow length scaled by period, plus the legend. `kind` is one of `"waves"` (Hs, Tp, mean direction from `copernicus` key `wav`), `"currents"` (`phy_cur` u/v) or `"wind"` (`open_data.marine_weather`).
- `point_chart(df, kind) -> plotly.Figure`: a single time-series chart where the line or area is the magnitude and arrows along it show direction, with arrow length showing period for waves.
- `load_field(kind, bbox, time)` and `load_point(kind, lat, lon, start, end)` wrap the source modules.

### I → U: indicator cards (`src/marinekit/indicators.py`)
- `CARDS`: ordered list of card ids, following `docs/indicators/SHORTLIST.md` section 1.
- `card(card_id, lat, lon, date, profile="public") -> dict` with keys `id, title, status (normal|watch|alert|no_data), value, unit, reference, z, evidence (measured|satellite|model), confidence (high|medium|low), why, driver_note, investigate, sources [ {dataset, origin, date, distance_km} ], text {public, student, stakeholder, researcher}`.
- `zone_cards(zone_geom_or_point, date, profile) -> list[dict]`.
- `datahub.get_series(variable, lat, lon, start, end, source="auto") -> DataFrame` and `datahub.get_climatology(variable, lat, lon, source="auto") -> DataFrame`.
- Natural vs pressure rule chain from SHORTLIST section 3 fills `driver_note`.

### U: the app
- Run with `.venv/bin/streamlit run src/viewer/app.py --server.port 8502` (8501 is the old starter dashboard).
- Screens: questionnaire (profile: public / student / stakeholder with sector / researcher), map (layers, time slider, in-situ points, pressure overlap with the season switch), point and zone panel (compare sources, trend, anomaly band, obs vs model, vector chart), health cards, sectors view, data and methods.

## Phases
1. **Now: build the pieces in parallel** (Z, V, I, U). The viewer uses the old zone files and placeholder cards until the new ones land.
2. **Tonight:** integrate, then run `scripts/preload_cache.py` for all stations and zones. Test with Wi-Fi off.
3. **Day 2, 09:30–10:30:** polish and test as each user profile. Freeze code at 10:30, rehearse the demo twice.

## Definition of done for each workstream
- Runs from a clean start with `.venv/bin/python`; no new packages unless agreed with the main session.
- Has a smoke test or script that proves it works on real data at Constanța.
- Its docs list what is verified, what is assumed and what needs NIMRD.
- Reports back to the main session with files changed, how to run it and its known gaps.
