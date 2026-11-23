# EMODnet in-situ data (Physics + Chemistry) for the Romanian Black Sea coast

Module: `src/marinekit/sources/emodnet_insitu.py` · cache: `data/cache/emodnet_insitu/` (raw ERDDAP CSV, one file per request)
Everything below was checked with live HTTP requests on **2026-11-23** unless marked NOT VERIFIED.

## TL;DR

| What | Where | Auth | Use in the dashboard |
|---|---|---|---|
| Platform catalogue (all EMODnet Physics platforms, daily update) | `erddap.emodnet-physics.eu` → `EP_PLATFORMS_METADATA_V2` | none | map of platforms, filters |
| Per-platform time series (buoys, tide gauges, met stations, gliders, Argo) | `platform-erddap.emodnet-physics.eu` → `TS_70_<CODE>_MO_UND` etc. | none | observation series, NRT anomalies |
| Water samples: O2, nutrients, chl, T, S (1963-2021) | `erddap.emodnet-chemistry.eu` → `EUT_BLACKSEA_PROFILES` | none | historical reference / validation points |
| DIVAnd gridded climatologies chl, DIN, PO4, Si, O2 | `erddap.emodnet.eu` (griddap) + raw NetCDF on `ec.oceanbrowser.net` | none | **reference conditions** at a point |
| SeaDataNet monthly T/S climatology Black Sea | `erddap.emodnet-physics.eu` → `SDC_BLS_CLIM_TS_V2_m` | none | temperature / salinity anomaly baseline |

Public functions:

```python
list_platforms(bbox=BBOX_RO, parameters=None, types=None, include_bottle=False, min_days=1.0, with_dataset=True) -> DataFrame
fetch_platform(platform_or_dataset, start=None, end=None, variables=None, depth="surface", qc=(1, 2), resample=None) -> DataFrame
fetch_chemistry_samples(lat=None, lon=None, radius_km=30, bbox=None, start=None, end=None, variables=None,
                        max_depth=10.0, dataset="EUT_BLACKSEA_PROFILES", qc=("1", "2")) -> DataFrame
chemistry_climatology_at(lat, lon, variable="chl", product="danube", depth=0.0, start=None, end=None) -> DataFrame
ts_climatology_at(lat, lon, depth=0.0, period="1995-2019", masked=True) -> DataFrame
```

Run the smoke test: `cd src && ../.venv/bin/python -m marinekit.sources.emodnet_insitu` (~30 s once cached).

## 1. EMODnet Physics

### Endpoints
* Main ERDDAP: `https://erddap.emodnet-physics.eu/erddap` (ERDDAP 2.x, ~800 datasets: catalogues, products, gliders, HF radar, Argo, climatologies). The individual fixed platforms are **not** here.
* Platform ERDDAP: `https://platform-erddap.emodnet-physics.eu/erddap` (ERDDAP 2.30, ~106 000 datasets, one per platform). Dataset id pattern
  `{TS|PR}_{integrator}_{PLATFORMCODE}_{type}_UND`, integrator `70` = Copernicus Marine In Situ TAC (INSTAC), `01` = IOC sea level monitoring, `02`/`73` = Argo; type `MO` mooring, `TG` tide gauge, `GL` glider, `DB` drifter, `VA` vessel ADCP.
* Raw monthly NetCDF files per platform: `https://platform-erddap.emodnet-physics.eu/erddap/files/<datasetID>/<CODE>_MMYYYY.nc` (302 redirect to `er3webapps.emodnet-physics.eu/platforms3/...`). Listing per platform: `EP_PLATFORMS_FILES_METADATA` on the main ERDDAP. Not used by the module (20 MB/month for a 15-min buoy) but useful as a fallback.
* Platform web page: `https://map.emodnet-physics.eu/platformpage/?platformcode=<CODE>&integrator=instac`.

### Platforms on the Romanian shelf (BBOX_RO lon 28.4-30.6, lat 43.6-45.4), excluding bottle casts and one-day ADCP sections

Coverage from the catalogue (`firstdateobservation`/`lastdateobservation`), n_months = months with data (`availabledates`).

| id (dataset) | name / owner | lat, lon | coverage | months | parameters (OceanSITES codes) |
|---|---|---|---|---|---|
| **EUXRo02** (`TS_70_EUXRo02_MO_UND`) | offshore EuxRo buoy, GeoEcoMar (EMSO) | 44.318, 30.417 | 2013-06 → 2023-11 | 120 | TEMP, PSAL, CNDC, FLU2 (chl fluo), DOXY, OSAT, TUR4, currents, met |
| **EUXRo03** (`TS_70_EUXRo03_MO_UND`) | offshore EuxRo buoy, GeoEcoMar | 43.980, 29.936 | 2013-06 → 2023-11 | 120 | same as EUXRo02 |
| EUXRo01 (`TS_70_EUXRo01_MO_UND`) | GeoEcoMar, just east of bbox (30.78E) | 44.700, 30.779 | 2013-06 → 2022-10 | ~110 | same |
| **EUXRoOB02 / OB03 / OB01** | new offshore buoys, GeoEcoMar | 44.325,30.410 / 43.977,29.924 / 44.706,30.765 | 2025-01 → 2026-09 | 16 | TEMP, PSAL, CNDC, DOXY, OSAT, FLU2, TUR4, currents, met |
| **EUXRoCB02** | coastal buoy off Constanța/Mamaia, GeoEcoMar | 44.226, 28.678 | 2026-09 → 2026-11-22 (NRT) | 3 | TEMP, PSAL, DOXY, OSAT, FLU2, TUR4, CDOM, currents, met; waves in `EUXRoCB02AWAC` |
| EUXRoCB01 | coastal buoy off Sulina | 45.114, 29.783 | 2026-03 → 2026-11-22 | 5 | TEMP, PSAL, DOXY, FLU2, TUR4, met; waves `EUXRoCB01AWAC` |
| EUXRoCB03 | coastal buoy off Mangalia | 43.810, 28.607 | 2026-09 → 2026-11-22 | 3 | currents + met only; waves `EUXRoCB03AWAC` |
| **CG** (`TS_70_CG_MO_UND`) | Mangalia mooring, GeoEcoMar | 43.802, 28.606 | 2016-01 → 2024-01 | 92 | TEMP, FLU2, DOXY, TUR4, currents, met |
| 15480 Constanța, 15360 Sulina, 15499 Mangalia, 15428 Gura Portiței | coastal met stations, Romanian Nat. Meteo Admin. | | 2018/2021 → 2026-11 | 56-92 | TEMP (water), air T, wind, pressure, humidity |
| SPOT1624, SPOT1622, SPOT1383 | Sofar Spotter wave buoys off Constanța/Eforie, NIEP | 44.23, 28.67 | 2022 → 2026-11 (1624) | 17-39 | VHM0, VTPK, VTM02, VMDR, TEMP, wind |
| **IOC-csta2** (`TS_70_IOC-csta2_TG_UND`), IOC-csta3, IOC-mang; `TS_01_csta2_TG_UND` | Constanța / Mangalia tide gauges, NIEP | 44.148, 28.672 | 2018 → today (5-min) | ~90 | SLEV |
| 42804 Izmail, 42814 Vylkove | Danube tide gauges, Ukrainian Hydromet | 45.33-45.39 | 2023-06 → 2026-05 | 36 | SLEV, TEMP |
| 8901034 (`PR_70_8901034_GL_UND`) | ALSEAMAR glider Sea087 | 43.97, 28.74 (track to 35E) | 2023-06 → 2024-10 | 7 | TEMP, PSAL, DOX2, CDOM, chl |
| Argo (`ArgoFloats` on main ERDDAP) | 5907217, 6903866, 6903867, 6990663, 7902193 | 41.5-42.7N, 30-31E (deep basin, outside BBOX_RO) | active Nov 2025 → | | TEMP, PSAL (+DOXY/CHLA on BGC floats) |

The catalogue has 868 Black Sea entries in BBOX_WBS (474 bottle casts, 100 moorings, 69 tide gauges, 68 Argo, 62 drifters, 55 ADCP sections, 14 BGC Argo, 2 ferrybox, 1 glider). No ferrybox line crosses the Romanian shelf.

### Parameters → canonical columns
`TEMP→temp`, `PSAL→sal`, `DOXY/DOX2→o2` (mmol/m³) **and** `do` (mg/L = o2·31.998/1000), `OSAT→do_sat`, `FLU2/CPHL→chl`, `TUR4→turb` (NTU), `CDOM→cdom`, `SLEV→ssh`, `VHM0→wave_height`, `VTPK→wave_period_peak`, `WSPD→wind_speed`, `DRYT→air_temp`, `ATMS→pressure_atm`, `HCSP/HCDT→current_speed/dir`, `EWCT/NSCT→current_u/v` (full map: `PARAM_MAP`).

### QC flags (OceanSITES / Copernicus INSTAC, variable `<VAR>_QC`)
0 no QC · **1 good** · **2 probably good** · 3 bad but potentially correctable · 4 bad · 5 value changed · 6/7 not used · 8 interpolated · 9 missing · -127 / -32767 fill.
Module keeps 1 and 2, then drops |value| > 1e30 (netCDF fill leaking through) and values outside broad physical bounds (`_BOUNDS`, e.g. temp −2…35 °C, sal 0…40, do 0.03…22 mg/L). `<VAR>_DM`: R real-time, P provisional, D delayed mode, M mixed.

### Depth handling
ERDDAP flattens the netCDF `TIME × DEPTH` grid: each timestamp comes as N rows (one per depth level, in level order) but the `depth` column is usually only filled on the first row of each monthly file. The module recovers the level index from row order, maps it to the depths that are reported (EUXRoCB02: level 0 = −2 m met sensors, 1 = 0 m, 2 = 3 m water sensors), and in `depth="surface"` mode takes, per variable and timestamp, the shallowest level with a good value. `df.attrs["depth_m"]` says which depth was used (or "unknown" when the provider never reports it, e.g. EUXRo02/03 whose sensors are near-surface). `depth="all"` returns the long table with `level`, `depth`.

### Gotchas (all seen live)
1. **Advertised time coverage lags the data**: `TS_70_EUXRoCB02_MO_UND` advertised `time_coverage_end = 2026-11-07` but returned rows up to 2026-11-22 16:00; a query with `time>=` later than the advertised end fails with 404. The module clamps the start and filters client-side.
2. Constraints must be URL-encoded (`>=`, `<`), otherwise Tomcat returns a bare HTTP 400.
3. Full-history queries are slow (~30 s per year of hourly data on EUXRo03). The module fetches in yearly chunks, each cached forever (recent chunks refresh after 3 h).
4. NRT coastal buoys (deployed 2026) are rough: EUXRoCB02 DOXY ≈ 7 in Sept 2026 in a field labelled mmol/m³ (clearly mg/L → module converts and writes a note), and **0 with QC=1 in October 2026** (sensor failure; dropped by the >0 bound); PSAL ≈ 7.7 at Constanța in Oct 2026 (low for 3 m depth, possibly sensor issue or Danube plume, not filtered); EUXRoCB01 has DOXY = 29.78 (= its longitude) with QC=1 and garbage values ~1e-306 with nonsense QC codes at the tail. The physical bounds catch some of this, not all: plot before trusting.
5. EUXRo02 `FLU2` values ~0.01 mg/m³ in July 2021 are far below realistic shelf chlorophyll: fluorescence is uncalibrated; use for relative variability only. EUXRo02 DOXY in 2021 is all QC=9 (missing).
6. Tide-gauge `SLEV` is relative to a local datum (Constanța ≈ −7.4 m): use anomalies (subtract the mean), not absolute values.
7. Sea level NRT collection `ERD_EP_SLEV_NRT_60m` returned no Romanian rows for Nov 2026; use the per-platform datasets instead.

### Licence / citation
Platform datasets: licence "Creative Commons Attribution Share-Alike" (CC BY-SA) as stated in each dataset; citation attribute: "Data are the property of the producer/owner distributed through EMODnet Physics…". Cite: *EMODnet Physics (https://emodnet.ec.europa.eu/en/physics), data from <institution> (e.g. National Institute of Marine Geology and Geoecology GeoEcoMar; National Institute for Earth Physics NIEP), distributed via Copernicus Marine In Situ TAC.* `df.attrs["institution"]`, `["license"]`, `["citation"]` are filled per dataset.

## 2. EMODnet Chemistry

### In-situ samples: `https://erddap.emodnet-chemistry.eu/erddap`
Datasets (all "v2025"): `EUT_BLACKSEA_PROFILES` (bottle/CTD profiles, 1935-2024, lon 26.2-41.8), `EUT_BLACKSEA_TIMESERIES` (2003-2023, few Romanian rows), `CONTAMINANTS_BLACKSEA_{WATER,SEDIMENT,BIOTA}_*`, `SEAFLOOR_LITTER_BLACKSEA`, `BEACH_LITTER`.
Variables used: `ITS_90_water_temperature`, `Water_body_salinity`, `Water_body_dissolved_oxygen_concentration` (µmol/L), `Water_body_chlorophyll_a` (mg/m³), `Water_body_nitrate/nitrite/ammonium/phosphate/silicate` (µmol/L), DIN, TN, TP, pH; QC in `QV_SEADATANET_<var>`.

Romanian shelf (BBOX_RO, depth ≤ 10 m), all time: **14 746 rows, 1963-02 → 2021-09**; 8 165 rows from NIMRD "Grigore Antipa" (187 stations, 1963-1999 only), the rest HCMR, UkrSCES, Odessa SOI, UHMI, BGODC, METU, AWI/TÜBİTAK. Per variable: O2 11 947 rows (3 921 since 2000), PO4 9 971 (1 322 since 2000), NO3 6 370 (1 244 since 2000, last 2019-11), **chl only 129** (1993-2021). Since 2015 only 342 rows (2015-2021), mostly Ukrainian and international cruises. NIMRD's post-2000 monitoring data are not in the public aggregated set (they feed the DIVAnd products below but are restricted at sample level).

QC (SeaDataNet L20): 0 no QC · **1 good** · **2 probably good** · 3 probably bad · 4 bad · 5 changed · 6 below detection · 7 in excess · 8 interpolated · 9 missing · A uncertain phenomenon · B nominal · Q below quantification. Module keeps 1, 2.

Licence/citation (dataset attribute): *"This resource was generated in the framework of EMODnet Chemistry, under the support of DG MARE Call for Tender EASME/EMFF/2020/3.1.11/European Marine Observation and Data Network (EMODnet) - Lot 5 - Chemistry"* (mandatory citation).

### Gridded DIVAnd climatologies (reference conditions)
* **Danube Delta coastal product** (NIMRD, v2025): 0.01°, lon 28.5-30.5, lat 43.7-45.6, 11 depths 0-40 m, 4 seasons (DJF/MAM/JJA/SON) of 2000-2022 (chl) or 1970/1980-2022 (others). Griddap on `https://erddap.emodnet.eu/erddap`: chl `oceanbrowser_opendap_ebeb_bdb0_a194`, DIN `…13be_1148_6757`, O2 `…147b_ee8c_9d8c`, PO4 `…78b6_98d7_8c7e`, Si `…3433_052b_9d7b`. Raw NetCDF (3.8-5.6 MB each): `https://ec.oceanbrowser.net/data/emodnet-domains/Coastal_areas/Black_Sea-_Danube_Delta/Water_body_chlorophyll-a.nc`. Chl DOI 10.13120/2e99d11d-1c86-4f62-b7f6-087607199fbf.
* **Black Sea regional product** (v2025): 0.05°, depths 0-50 m, moving **6-year centred** seasonal analyses, one value per season per year (chl/DIN/PO4/Si 1992-2020, O2 1982-2021): chl `oceanbrowser_opendap_470c_8f10_72a6` (DOI 10.13120/8e74967a-5655-44fc-90b7-7eca192b7851), DIN `…af26_ec61_167f`, O2 `…bcfe_6547_14a6`, PO4 `…8ba2_e24f_6849`, Si `…63d5_3a17_0164`. Raw NetCDF 66-571 MB under `ec.oceanbrowser.net/data/emodnet-domains/By_sea_regions/Black_Sea/` (too big for the demo; use griddap point extraction).
* Fields: `<var>` full analysis, `<var>_L1` masked where relative error > 0.3, `_L2` > 0.5, `_relerr`. Use `_L1`. Winter values at the coast are often masked (relerr ~0.8: few winter cruises).
* The `oceanbrowser_opendap_*` ids are auto-generated; if they change, `_find_divand_id` re-discovers them by title. Licence: free use with the EMODnet Chemistry acknowledgement above.

### SeaDataNet T/S climatology
`SDC_BLS_CLIM_TS_V2_m` on the Physics ERDDAP (griddap, 0.125°, 67 depths, monthly). Three periods stored as nominal years: 1974 = 1955-1994, 1987 = 1955-2019, 2007 = 1995-2019 (inferred from the period mid-points; summary says "1955-2019 and 2 subperiods"). DOI 10.12770/847f1627-f39f-40af-b3b0-a2f6d29ff4dc.

## 3. Other portals (brief)
* **SeaDataNet CDI** (`https://cdi.seadatanet.org/search`, `cdi-chemistry.seadatanet.org`): search is public; downloading original files needs a **Marine-ID login** and per-file requests (restricted data needs owner approval). Not automated. NOT VERIFIED beyond the page loading.
* **EMODnet Ingestion** (`emodnet.ec.europa.eu/en/data-ingestion`): a data *submission* service, no data API.
* **EMODnet Central Portal**: geoviewer `https://emodnet.ec.europa.eu/geoviewer/` (web UI); the central ERDDAP `https://erddap.emodnet.eu/erddap` (478 datasets) is the useful API: it hosts the Chemistry DIVAnd grids above.
* EMODnet Chemistry GeoServer `geoserver.emodnet-chemistry.eu` did not resolve (connection failed) and `data.emodnet-chemistry.eu` did not answer; the Beacon endpoints tried (`beacon-emodnet-chemistry.maris.nl`, `beacon.emodnet-chemistry.eu`) did not answer either. NOT VERIFIED / unavailable today.
* Black Sea Commission data portal (`data.blacksea-commission.org`): no answer. NIMRD (`nimrd.ro`, redirect from rmri.ro) website loads; no public data API found.
* Copernicus Marine In Situ TAC holds the same INSTAC platforms (covered by the Copernicus agent; needs a free account).

## 4. Verification log (2026-11-23)

| Item | What I ran | What came back |
|---|---|---|
| Physics ERDDAP up | `GET erddap.emodnet-physics.eu/erddap/tabledap/allDatasets.csv` | 200, 803 datasets |
| Platform catalogue | `EP_PLATFORMS_METADATA_V2.csv?...&latitude>=41&latitude<=46.7&longitude>=27.4&longitude<=42` | 868 rows; Romanian table above |
| Platform ERDDAP | `platform-erddap…/allDatasets.csv` | 106 153 rows incl. all Romanian platforms |
| EUXRo02 series | `fetch_platform("EUXRo02","2021-07-01","2021-07-08",["temp","sal","chl","o2","turb"])` | ~160 hourly rows: temp 23.7-25.1 °C, sal 16.4-17.6, chl ~0.012 (fluo); o2/turb all QC 9 |
| EUXRoOB03 series | `fetch_platform("EUXRoOB03","2025-06-01","2025-09-01",…,resample="1D")` | daily rows: 2025-06-01 temp 18.0, sal 16.7, chl 3.9, do 8.5 mg/L (o2 267 mmol/m³), turb 57 NTU |
| EUXRo03 full history | `fetch_platform("EUXRo03","2014-01-01","2023-11-01",["temp","chl","o2","sal"],resample="1D")` | 2 881 days in 273 s (first call; 10 yearly chunks; cached after). Good-day counts: temp 2 827, chl 2 805, o2 1 642 (none in 2015-16), sal 1 515. Medians: temp 15.9 °C, chl 0.37, do 9.1 mg/L, sal 18.05. Some near-zero o2 days remain (sensor drop-outs) |
| EUXRoCB02 recent | `fetch_platform("EUXRoCB02","2026-11-15",None,["wind_speed","temp"])` | 639 rows 2026-11-16 → 2026-11-22 16:00 despite advertised end 2026-11-07 (clamp works); temp empty in Nov |
| EUXRoCB02 Sept | `fetch_platform("EUXRoCB02","2026-09-01","2026-09-03",["temp","sal","do","chl","turb"])` | 15-min rows at 3 m: temp 24.1, sal 7.8, do 7.3 mg/L (mg/L heuristic note), chl 1.5, turb 29; `depth="all"` gives level 0 = −2 m (met), 2 = 3 m (water) |
| Tide gauge | `fetch_platform("IOC-csta2", now-3d, now, ["ssh"])` | 620 rows at 5 min, last 2026-11-23 08:25, ssh ≈ −7.4 m (local datum) |
| Argo | `ArgoFloats` distinct platforms, WBS bbox, since 2025-11-01, pres ≤ 5 | 5 floats (list above) |
| Chemistry samples | `fetch_chemistry_samples(44.17, 28.72, 30, "2000-01-01", "2010-12-31")` | 76 rows, 6 stations, e.g. 2002-09-09 st. 00DT1 temp 23.0, sal 14.0, o2 337 µmol/L (10.8 mg/L) |
| Chemistry coverage | `EUT_BLACKSEA_PROFILES` BBOX_RO depth ≤ 10 | 14 746 rows 1963-2021 (18 s) |
| DIVAnd Danube chl | `chemistry_climatology_at(44.17, 28.72, "chl", "danube")` | winter 3.74, spring 3.20, summer 1.86, autumn 2.78 mg/m³ (relerr < 0.01) |
| DIVAnd Black Sea O2 | `chemistry_climatology_at(44.17, 28.72, "o2", "blacksea", start="2015")` | 2021: spring 304, summer 289, autumn 245 µmol/L; winter masked in L1 |
| DIVAnd PO4 / DIN griddap | griddap point 44.15N 28.7E | 2020 PO4 0.10-0.29, DIN 3-16 µmol/L |
| T/S climatology | `ts_climatology_at(44.17, 28.72)` (1995-2019) | Feb 4.4 °C … Aug 26.5 °C; sal 13.8 (May) … 16.7 (Oct) |
| DIVAnd NetCDF download | `GET ec.oceanbrowser.net/…/Black_Sea-_Danube_Delta/Water_body_chlorophyll-a.nc` | 200, 3.9 MB, dims time 4 × depth 11 × lat 191 × lon 201 |
| Platform NetCDF files | `GET platform-erddap…/files/TS_70_EUXRoCB02_MO_UND/EUXRoCB02_102026.nc` | 302 → 21.7 MB HDF5, TIME 2888 × DEPTH 3 |
