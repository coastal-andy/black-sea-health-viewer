# Health cards and data hub: API

Workstream I of [WORKFLOW.md](../plan/WORKFLOW.md) (interface "I -> U"). Code: [indicators.py](../../src/marinekit/indicators.py), [datahub.py](../../src/marinekit/datahub.py). The science behind every number is in [SHORTLIST.md](SHORTLIST.md) and the physical, chemical and biological docs.

## Quick start

```python
from marinekit import indicators as ind, datahub as dh

ind.CARDS
# ['temperature', 'oxygen', 'blooms', 'clarity', 'nutrients', 'bathing', 'biodiversity', 'drivers', 'acidification']

c = ind.card("oxygen", 44.17, 28.72, "2026-11-23", profile="public")
c["status"], c["value"], c["unit"], c["driver_note"]

cards = ind.zone_cards((44.17, 28.72), "2026-11-23", "stakeholder:aquaculture")   # point
cards = ind.zone_cards(feature_or_geometry, "2024-07-20", "researcher")             # polygon: centroid
cards = ind.zone_cards(polygon, "2024-07-20", "public", samples=3)                  # worst of 3 interior points

df = dh.get_series("sst", 44.17, 28.72, *dh.recent_window(60))                     # source="auto"
cl = dh.get_climatology("sst", 44.17, 28.72)                                        # day-of-year reference
cmp = dh.compare_sources("sst", 44.17, 28.72, *dh.recent_window(60))                # one column per source
st = dh.obs_vs_model("o2", 44.17, 28.72, "2026-06-01", "2026-09-01")                # bias, rmse, r, n
```

Use `dh.recent_window(60)` for charts: it is the window `scripts/preload_cache.py` warms, so it works offline.

## Card dict

`card(card_id, lat, lon, date=None, profile="public") -> dict`. It never raises for missing data: it returns `status="no_data"` with the reason in `why`.

| Key | Type | Meaning |
|---|---|---|
| `id`, `title` | str | card id from `CARDS`, display title |
| `status` | str | `normal`, `watch`, `alert` or `no_data` |
| `value`, `unit` | float or str, str | main value (bathing: class label) |
| `reference` | dict | `value` (normal for the date or the threshold), `low`/`high` (usual band p10-p90), `period`, `basis`, `threshold`, `threshold_type` |
| `z` | float or None | standardised anomaly; None when not meaningful (forecast bottom O2, historical nutrients) |
| `evidence` | str | `measured`, `satellite` or `model` |
| `confidence` | str | `high`, `medium`, `low` |
| `why` | str | one or two sentences with the numbers |
| `driver_note` | str | result of the natural-vs-pressure rule chain (`classify_cause`) |
| `investigate` | list | `{trigger, action, who}` from SHORTLIST section 5 |
| `sources` | list | `{dataset, origin, date, distance_km, label, trust}`; zone cards add `{"dataset": "zone sampling", ...}` with the point used |
| `text` | dict | `public`, `student`, `stakeholder`, `researcher` (all four always present) |
| `supporting` | list | extra: secondary indicators `{name, value, unit, note, threshold_type}` |
| `seconds` | float | extra: compute time |

`threshold_type` labels: **OFFICIAL-RO** (Romanian MSFD 2024, NIMRD), **OFFICIAL-EU** (directive), **LIT** (literature), **OURS** (our proposal or a climatology band). Combined labels like `"OFFICIAL-RO + OURS"` mean the card uses both.

`profile` may be `"stakeholder:<sector>"` with sector in ports, shipyards, tourism, fishing, aquaculture: it adds a sector sentence to `text["stakeholder"]`.

## Cards and status rules

| Card | Value | Normal for the date | Watch | Alert | Evidence |
|---|---|---|---|---|---|
| temperature (P1, P6) | satellite SST, °C | DOY clim 1991-2020 | outside p10-p90 or moderate heatwave / cold spell ongoing (LIT) | strong or worse heatwave / cold spell ongoing (Hobday 2018, LIT) | satellite |
| oxygen (C1, C2, B5) | model bottom O2, mg/L | classes A >= 5 (OFFICIAL-RO), B 4-5, C 2-4 (OURS), D < 2 (LIT) | class B or C, or surface saturation > 120 % or < 80 % (OURS) | class D | model |
| blooms (B1, B2, D5C2, C3) | satellite chl, mg/m³ | DOY clim 1998-2020, log space | above p90 (OURS) or D5C2 season proxy fails (P75 May-Sep > 5.97, OFFICIAL-RO) | above p90 for >= 5 days in Jun-Sep, or above p90 while D5C2 fails | satellite |
| clarity (P5, P7) | Secchi estimate, m (1.1 / Kd_PAR) | DOY clim of Kd490 1998-2022 | Kd490 above p90 (OURS) | above p90 and >= 2 times normal | satellite |
| nutrients (C4, C5) | summer DIN, µmol/L (DIVAnd 6-year window) | DIN 10.5, PO4 0.23 marine P75 (OFFICIAL-RO) | worst ratio 1-1.5 | worst ratio > 1.5 | measured (historical) |
| bathing (C6) | class of the nearest official site within 10 km | Excellent or Good (OFFICIAL-EU) | Sufficient, or any site within 10 km Sufficient/Poor | Poor | measured |
| biodiversity (B6, B7) | number of tracked non-indigenous species since 2015 | presence over effort, never a trend | a species new to the Romanian coast since 2015, or invaders present inside a port or shipyard zone (OURS) | never | measured |
| drivers (P2, P3, P4, P7) | Danube 30-day flow / normal | 1.0 | any driver active: Danube > 1.2 or < 0.6, upwelling, storm, stratified | never | model |
| acidification (C7) | model pH | DOY clim 1993-2022 | below p10 (OURS) | never (watch only) | model |

## Rule chain (`classify_cause`)

`classify_cause(kind, drivers, model_only=False, persist_days=0, bloom_recent=False, nutrient_obs=None)` implements SHORTLIST section 3 once. The first matching rule labels the event; later matches are kept in `also` and quoted after "If the value is real:". Labels: `natural`, `mixed`, `model artefact`, `pressure-related`, `pressure`, `possible pressure`, `unexplained`, `climate`, `none`.

- `drivers = ind.drivers_at(lat, lon, date)`: Danube ratio and spring flow vs p75, surface salinity and anomaly, surface minus bottom temperature, bottom-temperature drop over 7 days, bottom salinity (model level about 2 m above the EMODnet depth), upwelling (Jun-Sep, coast minus 47 km offshore SST), storm (max Hs over 3 days vs hourly p95), and the sector zones containing the point (`data/zones/sector_zones.geojson`, summer-only zones counted 1 June - 15 September).
- Our one addition: a warm or cold surface event that no rule explains is labelled `climate` (regional, weather-driven), never `possible pressure`, because local activities cannot cause a heatwave.
- Rule 7 (wastewater) needs ammonium or nitrite observations near an outfall. None are live, so it fires only when `nutrient_obs` is passed.

## Data hub: source choice

`get_series(variable, lat, lon, start, end, source="auto")` returns a daily DataFrame with one column named after the variable; `attrs` hold `source_id, label, origin, evidence, trust, unit, datasets, distance_km, notes`.

| Variable | auto | Other sources (`source=`) |
|---|---|---|
| sst | satellite REP, then NRT minus 0.53 °C | model, buoy, station 15480 (untrusted), coastal buoy (untrusted) |
| chl | satellite L4 multi-year + NRT | model, buoy (fluorescence) |
| kd490 | satellite multi-year + NRT | |
| o2, o2_sat | offshore buoy if within 30 km, else model | coastal buoy (untrusted) |
| o2_bottom, bottom_temp, sal, mld, ph | model: reanalysis up to its end, then analysis/forecast | buoy for sal |
| no3, po4, si, nh4 | EMODnet Chemistry bottles 0-5 m within 30 km | model for no3/po4 only on request, trust `not_usable_absolute` |
| wave_height | Copernicus wave model, daily max | open-meteo |
| wind_speed | ERA5 via Open-Meteo | |
| discharge | GloFAS Danube | |

The coastal buoys EUXRoCB01-03 and station 15480 are `trust="untrusted"` and never auto-picked. `compare_sources` lists them only within 30 km. `get_climatology` returns a day-of-year table (`mean, std, p10, p50, p90, n`); for chl and kd490 it is in log10 space (`mean` = geometric mean, `std` = sd of log10, `attrs["space"] == "log10"`). For nutrients it returns the DIVAnd seasonal table.

Offline: `MARINEKIT_OFFLINE=1` reads every cached file regardless of age. Without it, recent files count as fresh for 24 h (`MARINEKIT_MAX_AGE_H`), and a failed refresh falls back to the stale file.

## Timing

Measured on 2026-11-23 with `MARINEKIT_OFFLINE=1` after `scripts/preload_cache.py`. Each run used a fresh Python process, so the figures include reading every parquet file once.

| Case | Time |
|---|---|
| `import marinekit.indicators` | 0.3 s |
| All 9 cards, Constanța, today | 1.1 s (first card 1.0 s: it computes the shared drivers; the others take 0.01-0.03 s) |
| All 9 cards, Constanța, 2024-07-20 | 1.0 s |
| All 9 cards, Mangalia / Sulina, today | 1.1 s / 0.9 s |
| All 9 cards again in the same process (memory caches cleared) | 0.1 s |
| `zone_cards(polygon)`, sample point already cached | 0.1 s |
| `compare_sources("sst", ...)`, `obs_vs_model("o2", ...)` on `recent_window(60)` at a station | < 0.05 s |
| A point or year not in the cache (network) | 3-8 s per series; 30-70 s for all cards the first time |
| `preload_cache.py`, first run (20 points) / re-run | 25 min / 1-7 min |

Targets (WORKFLOW: about 3 s per card, about 10 s per point) are met for every cached point. Clicking a new point on the map needs the network once.

## Preload and tests

```bash
.venv/bin/python scripts/preload_cache.py
```

```bash
.venv/bin/python tests/test_indicators.py
```

The preload covers the 7 `STATIONS` and one point per pressure-zone feature, all cards at today, the climatologies, the last 60 days of the main variables and `compare_sources` at the stations. The test runs offline (cache only) and also works under pytest.

## Known gaps

- **Offline demo uses preloaded points.** A new map click or year fetches from the network once. Offline, use the 7 stations and the zone sample points, or run the preload with `--dates` for extra dates.
- **Bottom oxygen is model only.** The forecast system runs about 2 mg/L below the reanalysis, so `z` is left empty for forecast values and rule 1 (model artefact) is always quoted first. The D5C5 season test is computed on the concentration part only, not the 60 % saturation part.
- **Nutrients are historical.** The value is the latest DIVAnd 6-year window (centred 2020 at Constanța). Near the shore, where those windows are masked, it falls back to the 2000-2022 seasonal climatology. The marine-water thresholds are applied everywhere; the coastal ones (13.5 / 0.30) are listed in `reference`. Rule 7 (wastewater) cannot fire on live data.
- **Offshore buoys come from the GeoEcoMar ERDDAP.** It is read directly in `datahub.py`; DOXY has no QC there, and salinity is derived from conductivity with PSS-78. The Copernicus In Situ TAC returns nothing for EUXRoOB01-03, and EMODnet stops in September 2026. Every station is more than 30 km from a buoy, so `auto` uses the model for O2, and `obs_vs_model` samples the model at the buoy position (said in `note`). Check: model minus EUXRoOB03 surface O2, last 60 days, bias +0.42 mg/L, r 0.98, n 61.
- **Fixed corrections** come from the Constanța checks and are applied at every point: SST NRT minus 0.53 °C, forecast bottom temperature minus 0.41 °C, Secchi factor 1.1.
- **Clarity** uses cloud-gappy L3 Kd490 (value up to 16 days old) until the L4 gap-free product takes over on 2026-11-24.
- **Drivers:** upwelling is tested only in June-September, against a point 0.58° east. Bottom salinity is read about 2 m above the EMODnet depth, and the model may take it from a neighbouring cell.
- **Biodiversity** is presence only, in a ±0.15° x ±0.2° box (OBIS checklist). The watch rule (a species new to the Romanian coast since 2015, or invaders inside a port or shipyard zone) is ours.
- **Pressure zones** are read from `data/zones/sector_zones.geojson` once per process. A long-running app picks up a new zone file only after a restart.
