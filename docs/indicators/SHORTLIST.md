# Indicator shortlist for the Black Sea Health Viewer

This combines the three research sessions; the full detail is in [physical.md](physical.md), [chemical.md](chemical.md) and [biological.md](biological.md).
Every indicator below was computed live at Constanța on 2026-11-23 by `scripts/indicators/*_check.py` (each runs in 2–8 s from the cache).

**Labels used below**
- Evidence: **M** measured in situ, **S** satellite (a measured proxy), **Mod** model, **F** needs field sampling.
- Threshold type: **OFFICIAL-RO** = Romanian MSFD 2024 (NIMRD), **OFFICIAL-EU** = EU directive, **OURS** = climatology band or proposed by us.

## 1. Health cards in the dashboard

Each zone (sector buffer, hotspot or clicked point) shows these cards. Card status comes from the worst core indicator, and its confidence from how many independent sources agree.

| Card | Core indicators (dashboard) | Supporting / context | Main five-sector link |
|---|---|---|---|
| **Water temperature** | P1 SST anomaly + marine heatwave / cold spell | P6 bottom-temperature anomaly | aquaculture (mussel heat stress), tourism, fishing |
| **Oxygen** | C1 bottom-oxygen class + hypoxia days; C2 surface O₂ saturation | B5 mussel-bed hypoxia exposure | aquaculture, fishing (benthic habitats) |
| **Eutrophication and blooms** | B1 chl anomaly (log) + official D5C2 test; B2 bloom days per season | C3 eutrophication index (simplified BEAST); B3 community; B4 primary production | aquaculture (toxins), tourism (discoloured water), ports (dredging plumes) |
| **Water clarity** | P5 transparency (Kd490 → Secchi) and light at the seabed | P7 storm / resuspension index; buoy turbidity | tourism, ports and engineering (dredging, coastal works), seagrass |
| **Nutrients (historical)** | C4 nutrient status vs reference | C5 N:P and Si:N | all (Danube and outfalls) |
| **Bathing water** | C6 EU bathing-water class | wastewater plants and discharge points layer | tourism |
| **Biodiversity evidence** | B6 invasive and gelatinous species (presence) | B7 evidence coverage grid, strandings, ROV labels | ports (ballast), shipyards (hull fouling), tourism (jellyfish) |
| **Drivers** (shown beside every card, never as damage) | P3 Danube influence (GloFAS discharge + salinity) | P2 upwelling flag; P4 stratification; P7 storms | explains natural variability |
| **Acidification** (watch only) | C7 pH anomaly | | aquaculture (shell formation) |

## 2. Indicator table

| ID | Indicator | Formula (short) | Data key(s) | Reference / threshold | Evidence | Confidence |
|---|---|---|---|---|---|---|
| P1 | SST anomaly, heatwave, cold spell | anomaly = SST − DOY climatology mean; z = anomaly / std; heatwave = above p90 for ≥ 5 days (Hobday) | `sst_l4_rep` + `sst_l4_nrt` | DOY climatology 1991–2020 (OURS, standard WMO period) | S | high |
| P2 | Upwelling flag (Jun–Sep) | coastal SST − SST 47 km offshore ≤ −2 °C and a wind-based upwelling index > 0 over 3 days | `sst_l4_*`, `open_data.marine_weather` wind | summer 1991–2020 distribution (OURS) | S + reanalysis | medium |
| P3 | Danube influence | discharge ratio vs 1997–2025 DOY mean; surface-salinity anomaly | `open_data.danube_discharge`, `phy_sal`, `rea_phy_sal` | 1997–2025 (OURS) | Mod | medium |
| P4 | Stratification strength | Δσ surface − bottom (from T, S); MLD | `phy_temp`, `phy_sal`, `phy_mld`, `rea_*` | reanalysis 1993–2022 (OURS) | Mod | medium |
| P5 | Transparency, light at seabed | Secchi ≈ k / Kd490 (k calibrated); light at bottom = exp(−Kd490 × depth) | `sat_kd490_my`, `sat_kd490_nrt`, `emodnet_layers.depth_at` | Romanian Secchi GES values (OFFICIAL-RO) + DOY band (OURS) | S | medium |
| P6 | Bottom-temperature anomaly | as P1, bias-corrected model | `phy_temp` bottomT, `rea_phy_temp` | reanalysis 1993–2022 (OURS) | Mod | medium |
| P7 | Storm / resuspension, surge | Hs above p95; sea-level surge | `wav`, `open_data.marine_weather`, tide gauge `IOC-csta2`, `phy_ssh` | Hs 2021–2026 percentiles (OURS) | Mod + M | medium |
| C1 | Bottom-oxygen class | daily class A ≥ 5, B 4–5, C 2–4, D < 2 mg/L; season test May–Sep P10 ≥ 5 mg/L and ≥ 60 % saturation | `bgc_o2` (o2_bottom), `rea_bgc_o2`, bottles 1963–2021 | D5C5 (OFFICIAL-RO); hypoxia < 2 mg/L | Mod (no bottom sensor) | medium-low |
| C2 | Surface O₂ saturation | %sat = O₂ / O₂sat(T, S) (Garcia & Gordon 1992); flags > 120 % bloom, < 80 % respiration or upwelling | buoys `EUXRoOB01–03` (OSAT), `bgc_o2` + `phy_temp` + `phy_sal` | flags (OURS) | M + Mod | high offshore |
| C3 | Eutrophication index | ratio observed / target per criterion, one-out-all-out across nutrients, chl, O₂ | `sat_chl_l4_my`, `bgc_o2`, DIVAnd DIN / PO₄ | RO marine thresholds (OFFICIAL-RO) | S + Mod + climatology | low-medium |
| C4 | Nutrient status | value / official threshold, and value / seasonal climatology | `emodnet_insitu.fetch_chemistry_samples`, `chemistry_climatology_at` | DIN 10.5, PO₄ 0.23 µM marine P75 (OFFICIAL-RO) | M (to 2020 at best) | medium, historical only |
| C5 | N:P, Si:N | DIN / PO₄ vs 16; Si / DIN vs 1 | as C4 | Redfield (literature) | M | medium, historical |
| C6 | Bathing-water class | share Excellent / Good / Sufficient / Poor per year | `emodnet_layers.bathing_water_history()` (49 sites, 2007–2024) | EU Bathing Water Directive (OFFICIAL-EU) | M (lab) | high, annual |
| C7 | pH watch | pH − DOY climatology; trend | `bgc_car`, `rea_bgc_car` | OURS | Mod | low |
| B1 | Chl anomaly + D5C2 | log10(chl) − DOY climatology; official D5C2 seasonal test | `sat_chl_l4_nrt` + `sat_chl_l4_my` (cross-check `open_data.chl_occi_8day`) | 1998–2020 (OURS) + D5C2 (OFFICIAL-RO) | S | high offshore, medium at the coast |
| B2 | Bloom days | days with chl above the bloom threshold per season; trend since 1998 | `sat_chl_l4_my` | OURS | S | medium |
| B3 | Community structure | micro-size share (satellite); diatoms vs dinoflagellates (NIMRD counts, to 2015) | `sat_pft_l3_my`, OBIS | OURS | S + M historical | low |
| B4 | Primary production anomaly | satellite PP vs model NPP | `sat_pp_my`, `bgc_*` npp | OURS | S + Mod | medium |
| B5 | Mussel-bed hypoxia exposure | days with bottom O₂ < 2 and < 3 mg/L at *Mytilus* bed depths | `rea_bgc_o2` / `bgc_o2`, OBIS *Mytilus*, `depth_at` | C1 classes; 3 mg/L from literature, not official | Mod proxy | medium-low |
| B6 | Invasive and gelatinous species | presence, last record, records since 2015 (shown as presence over sampling effort, never as a trend) | OBIS API | — | M (occurrences) | good for presence only |
| B7 | Evidence coverage | records per grid cell, strandings, ROV habitat labels | `emodnet_layers.biology_records_grid`, OBIS, `vision.py` | — | evidence map | n/a |

## 3. Natural variability or pressure? One rule chain for all cards

Apply in order; the first match labels the event. "Pressure" is used only when no natural driver explains it.

1. **Is it a model-only anomaly for a variable the model gets wrong?** (bottom O₂: forecast − reanalysis −2 mg/L; nitrate and phosphate unusable) → **model artefact** until an observation confirms it.
2. **Upwelling** (P2) in Jun–Sep → cold SST, low surface O₂ saturation, low pH, high nutrients = **natural**.
3. **Cold saline intrusion** (bottom T drop > 1.5 °C in 7 days, or bottom S > 18.5) with low bottom O₂ = **natural**.
4. **Danube plume or flood** (P3 discharge ratio > 1.2 over 30 days, salinity < 14) → low salinity, high nutrients, low clarity, bloom = **natural**, or **mixed** when the spring discharge is above p75 (river load is partly a human pressure).
5. **Storm** (P7 in the previous 3 days) → low clarity, high SPM = **natural**.
6. **Bloom decay under stratification** (P4 stratified May–Oct, chl peak or O₂ saturation > 120 % 1–4 weeks earlier) followed by low bottom O₂ = **pressure-related (eutrophication)**.
7. **High NH₄, NO₂ or PO₄ at normal salinity near an outfall in summer** = **pressure (wastewater)**.
8. **Anomaly lasting 5+ days with no driver, inside a sector pressure zone or hotspot** = **possible pressure signal → investigate** (see section 5).

Live example: every bottom O₂ < 4 mg/L episode in the forecast since Dec 2024 is in the cold season, with bottom salinity 19.1–19.9. Rule 3 labels them all natural.

## 4. Data quality register (what to trust)

| Source | Status | Use |
|---|---|---|
| Offshore buoys `EUXRoOB01–03`, `EUXRo02/03` | good for T and O₂; formula matches buoy O₂ saturation (r 0.98) | measured reference for O₂ and T (chl and S: see the two rows below) |
| Buoy chlorophyll (fluorescence) at `EUXRoOB01–03`, `EUXRo03` | **indicative**: OB01-03 (2024-2026) read 2-3x satellite and model (median ratio satellite / buoy 0.36-0.51, R² 0.15-0.23 vs satellite); EUXRo03 (2013-2023) R² 0.00 vs satellite. Likely factory calibration, daytime quenching, biofouling | comparison only, never thresholds or trends; `datahub` "auto" uses satellite, then model |
| Buoy salinity at `EUXRoOB01–03` | **not trusted**: fouling-like drops to 13-15 PSU for weeks to months (e.g. OB02 Oct 2025-Mar 2026), R² 0.00-0.17 vs model, RMSE 1.1-3.5 PSU | show greyed out; `datahub` "auto" uses the model (about 1 PSU vs coastal bottles) |
| Buoy salinity at `EUXRo03` (2013-2023) | kept as before (good): no step-like drops reported, model 0.43 PSU above the buoy, RMSE 0.98 PSU (but R² 0.05), within the model's own 1 PSU coastal error | usable as a measured check; the record ends in 2023, so recent dates fall back to the model |
| Coastal buoys `EUXRoCB01/02` (new, Sep 2026+) | **not trusted**: O₂ units unclear, O₂ saturation 3.6 %, salinity 7.5 | show greyed out, "under QC" |
| Station 15480 (Constanța) | **shore station**: 3.5 °C colder than open water | air and harbour context only, not sea temperature |
| Copernicus physics (T, S) | good: reanalysis vs NIMRD casts, surface T r 0.99, bias +0.19 °C | maps, stratification, model vs obs |
| Copernicus BGC surface O₂ | usable: forecast vs buoy r 0.93 | maps, C2 |
| Copernicus BGC bottom O₂ | indicative: model systems disagree by ~2 mg/L | C1/B5 with low confidence |
| Copernicus BGC nitrate, phosphate | **not usable** as absolute values | not shown; use observations and climatology |
| Satellite SST, chl | good; NRT vs REP SST offset +0.53 °C | P1, B1, B2 |
| Bathing-water history (`emodnet_layers.bathing_water_history`) | fixed and verified: 2022 45/4, 2023 34/15, 2024 41/8 Excellent/Good, matching the EEA factsheet; seasons before 2015 use an older scheme | C6 per year from 2015; earlier years marked "not comparable" |

**Two-level quality rule.** Level 1 (sensor trust, in `marinekit.datahub`): a whole platform carries a trust in
`PLATFORMS`, and a single platform-variable pair can be overridden in `VARIABLE_TRUST` (trust, reason). `get_series(...,
source="auto")` never picks a pair whose trust is indicative, untrusted or not_usable_absolute; an explicit
`source="buoy"` and `compare_sources` still return it, with `attrs["trust"]` set to the flag and the reason in
`attrs["notes"]`, so the viewer can grey it out. `obs_vs_model` adds `obs_trust`. Level 2 (value screening, e.g. a
fouling screen on salinity) is not implemented yet; a flag is lifted only after a calibration against bottle samples.
Evidence: `docs/indicators/validation/interpretation.md` and `metrics.csv`.

## 5. "Investigate" recommendations (the decision output)

| Trigger | Recommended action | Who acts |
|---|---|---|
| C1 class D or B5 flag at a mussel bed | ROV or drop-camera transect plus grab sample within 2 weeks | NIMRD, aquaculture operators |
| B1/B2 high in Jun–Sep | Water samples for harmful species; shellfish toxin test for farms | NIMRD, sanitary authority, farms |
| B6 new non-indigenous species near a port | Plankton tow, ballast-water check | port authority |
| Any flag inside a Natura 2000 marine site | Check seagrass and brown and red algae condition | ANANP (protected areas agency), NIMRD |
| Persistent anomaly in a hotspot (rule 8) | Targeted sampling campaign at that hotspot | environment agency |
| C6 bathing water Sufficient or Poor | Check nearby wastewater outfalls | municipality, water operator |

## 6. Top questions for NIMRD (ask at the lectures, before the pitch)

1. Can we get post-2000 monitoring data (bottom O₂, nutrients, chl) for Constanța, Mamaia and Eforie, even as seasonal means?
2. Please confirm the 2024 MSFD thresholds we use (D5C2, D5C5, DIN and PO₄ P75, Secchi GES).
3. Were there bottom-hypoxia or mussel-mortality events in 2024–2026?
4. Are the coastal buoys `EUXRoCB0x` quality-controlled, and in what units is O₂?
5. Is there an official list of licensed aquaculture sites and of dredging and dumping areas?
6. Pressure weights: do you agree with the literature-derived sector weights (ports 0.36, fishing 0.35, shipyards 0.21, tourism 0.05, aquaculture 0.03; `data/zones/weights.yaml`)? Two values are our assumptions: the aquaculture floor and the fishing winter factor of 0.5.

## 7. Seasonal cycle and trend gate (analysis level)

Added 23 Nov 2026 (issue #2, request 2). Applied by `marinekit.seasonal` before the Water quality panel shows a spectrum-based cycle or a trend. Every result carries `show` and `gate_reason`. All thresholds are **OURS**.

- **Source**: trust from `datahub.get_series` (section 4 and its per-platform flags) must be good or usable.
- **Seasonal cycle** (usual-range band, amplitude, date of the maximum): shown when the annual cycle is significant (p < 0.05, Newey-West HAC) and trend + cycles explain adjusted R² >= 0.5 of the weekly means.
- **Trend** (OLS on complete annual means): fewer than 8 complete years: no number ("not enough years yet"); 8-19 years: number labelled "indicative"; 20 years or more: "climate trend". If p >= 0.05, the text says "not significant".
- Details and the current result per variable: `docs/indicators/seasonal/README.md`, section "Contract for the viewer".
