# Copernicus Marine Service (CMEMS): Black Sea / Romanian coast

Module: `src/marinekit/sources/copernicus.py` (smoke test: `PYTHONPATH=src .venv/bin/python -m marinekit.sources.copernicus`, add `--all` for every catalogue key).
Toolbox: `copernicusmarine` 2.5.1. Everything below was **verified live on 2026-11-23** unless marked **NOT VERIFIED**.

## 1. What works without login, and what needs it

| Operation | Login? | Verified 2026-11-23 |
|---|---|---|
| `copernicusmarine.describe(...)` (catalogue, variables, units, time ranges, versions, DOIs) | **No** | Ran with `HOME` pointed at an empty folder and no env vars. `describe(dataset_id="cmems_mod_blk_phy-temp_anfc_2.5km_P1D-m")` returned the product in 2.4 s. A full `describe(contains=["Black Sea"])` took 57 s and returned 278 dataset parts. |
| WMTS `GetCapabilities` / `GetTile` / `GetLegend` (`https://wmts.marine.copernicus.eu/teroWmts`) | **No** | `curl` GetCapabilities returned HTTP 200 with 33 kB of XML. GetTile z=6/x=37/y=23 for `phy_temp/thetao` and `sat_chl_l4_nrt/CHL` returned HTTP 200 `image/png` 256x256, and I looked at the chl tile: it shows the real western Black Sea. GetLegend returned 200 `image/svg+xml`. `check_tile()` in the module does the same check. |
| `open_dataset`, `subset` (even `dry_run=True`), `read_dataframe`, `get` | **Yes** | Without credentials the toolbox **prompts `Copernicus Marine username:` on stdin**. In a TTY or web app it blocks forever. With stdin closed it prints `Abort` and **returns `None`, with no exception**. The module checks credentials first and raises `CopernicusLoginRequired` (tested: raised in 0.00 s). |
| `login(check_credentials_valid=True)` | — | Returns `False` immediately when there are no credentials and `True` (0.3 s) when they are valid. It does not prompt. |
| Observation, not used by our code: the ARCO Zarr store URLs that `describe` lists (`https://s3.waw3-1.cloudferro.com/mdl-arco-*/…/.zmetadata`) answered HTTP 200 anonymously. | — | We do **not** rely on this. The licence and service terms assume a registered (free) account, so the code always goes through the toolbox with credentials. |

### Logging in (one-off, per machine)
1. Register for free at https://data.marine.copernicus.eu/register
2. Run `.venv/bin/copernicusmarine login`. It asks for a username and password and writes `~/.copernicusmarine/.copernicusmarine-credentials`.
   Without a TTY (server/CI), set `COPERNICUSMARINE_SERVICE_USERNAME` and `COPERNICUSMARINE_SERVICE_PASSWORD` instead. `COPERNICUSMARINE_CREDENTIALS_DIRECTORY` can point to a different folder that holds the credentials file.
3. Check with `.venv/bin/copernicusmarine login --check-credentials-valid`. It should print "Valid credentials from configuration file".

Our code picks credentials up automatically: the toolbox reads the env vars, then the credentials file. `is_logged_in()` checks that they exist without contacting the server, and `is_logged_in(check_online=True)` also validates them. `login_help()` returns the steps above as text for the UI.
**On this machine:** `~/.copernicusmarine/.copernicusmarine-credentials` exists and is valid. I checked existence and validity only; the contents were never printed.

## 2. Catalogue (CATALOG keys in the module)

Romanian coast test point: Constanța (44.17 N, 28.72 E) → nearest grid cell 44.175/28.725 (0.68 km) on the 2.5 km model grids.
Time ranges are the catalogue values on 2026-11-23.

### (a) Model analysis/forecast: physics, `BLKSEA_ANALYSISFORECAST_PHY_007_001` (CMCC, NEMO; DOI 10.48670/mds-00355)
Grid 0.025° (~2.5 km), 40.5–47.3 N, 27.25–42 E. 121 depth levels; the first is 0.50 m. Daily means from **2024-12-01 to 2026-12-02**: analysis plus a ~10-day forecast. Hourly (`PT1H-m`, `PT15M-i`) and monthly (`P1M-m`) variants also exist.
| key | dataset_id | variables (native → canonical, units) |
|---|---|---|
| phy_temp | cmems_mod_blk_phy-temp_anfc_2.5km_P1D-m | thetao→temp (°C), bottomT→bottom_temp (°C) |
| phy_sal | cmems_mod_blk_phy-sal_anfc_2.5km_P1D-m | so→sal (1e-3 = PSU) |
| phy_cur | cmems_mod_blk_phy-cur_anfc_2.5km_P1D-m | uo→current_u, vo→current_v (m/s). wo (m/s) is also available |
| phy_ssh | cmems_mod_blk_phy-ssh_anfc_2.5km_P1D-m (also `_detided-2.5km`) | zos→ssh (m), from 2024-11-19 |
| phy_mld | cmems_mod_blk_phy-mld_anfc_2.5km_P1D-m | mlotst→mld (m), from 2024-11-19 |
| wav | cmems_mod_blk_wav_anfc_2.5km_PT1H-i (`BLKSEA_ANALYSISFORECAST_WAV_007_003`, DOI 10.48670/mds-00360) | VHM0→wave_height (m), VTPK→wave_period (s), VMDR→wave_dir (deg). Hourly, 2024-08-17 to 2026-12-02 |
There is also a 500 m nested model, `cmems_mod_blk_phy-tem/sal/cur/ssh_anfc_mrm-500m_P1D-m`, but it covers only 39.5–41.5 N, 25–30 E (Bosphorus/Marmara), **not Romania**.

### (b) Model analysis/forecast: biogeochemistry, `BLKSEA_ANALYSISFORECAST_BGC_007_010` (BAMHBI; DOI 10.48670/mds-00354)
Grid 0.025°, 40.5–47 N. 59 levels; the first is 0.25 m. Daily from **2024-10-03 to 2026-12-01**.
| key | dataset_id | variables |
|---|---|---|
| bgc_chl | cmems_mod_blk_bgc-pft_anfc_2.5km_P1D-m | chl→chl (mg m-3), phyc, zooc (mmol m-3) |
| bgc_o2 | cmems_mod_blk_bgc-pp-o2_anfc_2.5km_P1D-m | o2→o2 (mmol m-3), o2b→o2_bottom, nppv→npp (mg m-3 day-1) |
| bgc_nut | cmems_mod_blk_bgc-nut_anfc_2.5km_P1D-m | no3, po4, odu (mmol m-3) |
| bgc_car | cmems_mod_blk_bgc-car_anfc_2.5km_P1D-m | ph (total scale), dissic→dic, talk→alk (mol m-3) |
| bgc_optics | cmems_mod_blk_bgc-optics_anfc_2.5km_P1D-m | kd→kd (m-1; generic downwelling attenuation, **not** Kd490), lght (W m-2) |
| (not wrapped) | cmems_mod_blk_bgc-co2_anfc_2.5km_P1D-m | spco2, fpco2 |
To convert O2: mg/L = mmol m-3 × 0.032.

### (c) Satellite ocean colour (CNR-GOS; high-resolution coastal products by Brockmann Consult)
| key | dataset_id | var → canonical | res | time range (catalogue, 2026-11-23) |
|---|---|---|---|---|
| sat_chl_l4_nrt | cmems_obs-oc_blk_bgc-plankton_nrt_l4-gapfree-multi-1km_P1D (OCEANCOLOUR_BLK_BGC_L4_NRT_009_152) | CHL→chl mg m-3 | ~1 km | **rolling ~3 weeks**: 2026-10-31 to 2026-11-22 |
| sat_chl_l4_my | cmems_obs-oc_blk_bgc-plankton_my_l4-gapfree-multi-1km_P1D (…L4_MY_009_154) | CHL→chl | ~1 km | 1997-09-16 to 2026-11-11 (includes interim data, ~12 days behind) |
| sat_chl_l3_nrt | cmems_obs-oc_blk_bgc-plankton_nrt_l3-olci-300m_P1D (…L3_NRT_009_151) | CHL→chl | 300 m | 2026-11-09 to 2026-11-22 |
| sat_chl_l3_my | cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D, falling back to …_my_l3-olci-300m_P1D | CHL→chl | 1 km / 300 m | 1997-09-16 to 2026-11-15 (OLCI from 2016-04-26) |
| sat_kd490_my | cmems_obs-oc_blk_bgc-transp_my_l3-multi-1km_P1D, falling back to …transp_my_l4-gapfree-multi-1km_P1D-m, then …transp_my_l3-olci-300m_P1D | KD490→kd490 m-1 | 1 km | 1997-09-16 to 2026-11-15 |
| sat_kd490_nrt | cmems_obs-oc_blk_bgc-transp_nrt_l4-gapfree-multi-1km_P1D-m, falling back to …transp_nrt_l3-multi-1km_P1D | KD490→kd490 | 1 km | last ~2 weeks (the L4 id already served data today) |
| sat_hr_l3 | cmems_obs_oc_blk_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m (…HR_L3_NRT_009_206) | CHL→chl, SPM→spm (g m-3), TUR→turb (FNU) | ~100 m | 2020-01-01 to 2026-11-21 (very gappy) |
| sat_hr_l4_month | cmems_obs-oc_blk_bgc-tur-spm-chl_nrt_l4-hr-mosaic_P1M-m (…HR_L4_NRT_009_212) | CHL, SPM, TUR | ~100 m | monthly |
| sat_chl_clim_ref | cmems_obs-oc_blk_bgc-plankton_my_l4-multi-climatology-1km_P1D | CHL_median, CHL_standard_deviation | 1 km | ready-made daily climatology on the dummy year 2000 |
Other ocean-colour data: monthly L4 chl/Kd490 (`…_l4-multi-1km_P1M`, `…_l4-olci-300m_P1M`), primary production (`…pp_my/nrt_l4-multi-4km_P1D`, PP g m-2 d-1), reflectances, IOPs. There is also a daily high-res L4 dataset, `cmems_obs_oc_blk_bgc_tur-spm-chl_nrt_l4-hr-mosaic_P1D-m`, but it currently ends 2026-08-31.

### (c') Satellite SST (CNR)
| key | dataset_id | var | res | time range |
|---|---|---|---|---|
| sst_l4_nrt | SST_BS_SST_L4_NRT_OBSERVATIONS_010_006_a_V2 | analysed_sst (K, converted to °C) → sst | 0.0625° | 2008-01-01 to 2026-11-23, daily |
| sst_l4_nrt_hr | SST_BS_SST_L4_NRT_OBSERVATIONS_010_006_c_V2 | analysed_sst → sst | 0.01° | 2008 to 2026-11-23 |
| sst_anom_nrt | SST_BS_SSTA_L4_NRT_OBSERVATIONS_010_006_b (_d = 0.01°) | sst_anomaly (°C) **vs the 1991-2020 climatology** (read from the file attrs) | 0.0625° | 2008 to 2026-11-23 |
| sst_l4_rep | cmems_SST_BS_SST_L4_REP_OBSERVATIONS_010_022 | analysed_sst → sst | 0.05° | 1982-01-01 to 2026-10-24 (~1 month behind) |
| (not wrapped) | cmems_obs-sst_bs_phy_my_l3s_P1D-m (SST_BS_PHY_L3S_MY_010_041) | adjusted_sea_surface_temperature (K) | 0.05° | 1982 to 2026-10-24 |
| (not wrapped) | cmems_obs-sst_blk_phy-sst_nrt_diurnal-oi-0.0625deg_PT1H-m | hourly diurnal subskin SST | 0.0625° | 2020 to present |

### (d) Multi-year reanalysis (reference conditions / climatology)
`BLKSEA_MULTIYEAR_PHY_007_004` (CMCC; DOI 10.48670/mds-00356): daily **1993-01-01 to 2025-07-31**, same grid and levels as (a).
`BLKSEA_MULTIYEAR_BGC_007_005` (ULiège BAMHBI; DOI 10.48670/mds-00372): daily **1992-01-02 to 2024-12-31**, 59 levels.
| key | dataset_id | vars |
|---|---|---|
| rea_phy_temp / _sal / _cur / _ssh / _mld | cmems_mod_blk_phy-{temp,sal,cur,ssh,mld}_my_2.5km_P1D-m | thetao, bottomT / so / uo, vo / zos / mlotst |
| rea_bgc_chl | cmems_mod_blk_bgc-plankton_my_2.5km_P1D-m | chl, phyc |
| rea_bgc_o2 | cmems_mod_blk_bgc-bio_my_2.5km_P1D-m | o2, o2b, nppv |
| rea_bgc_nut | cmems_mod_blk_bgc-nut_my_2.5km_P1D-m | no3, po4 |
| rea_bgc_car | cmems_mod_blk_bgc-car_my_2.5km_P1D-m | ph, dissic, talk |
Ready-made monthly climatologies also exist, for example `cmems_mod_blk_phy-temp_my_2.5km-climatology_P1M-m` (vars `thetao_mean`, `thetao_std`, …) and `cmems_mod_blk_bgc-*_my_2.5km_climatology_P1M-m`. They are not wrapped, because `climatology()` computes p10/p90 itself.

### (e) In situ: `INSITU_BLK_PHYBGCWAV_DISCRETE_MYNRT_013_034` (In Situ TAC; DOI 10.48670/moi-00033)
There is one dataset, `cmems_obs-ins_blk_phybgcwav_mynrt_na_irr`, with three parts: `history` (archive up to 2026-10-31), `monthly` (2020 to 2026-11-22) and `latest` (last 30 days, up to 2026-11-23 10:46Z, so close to real time). Services: original NetCDF files, plus "sparse" ARCO data that the toolbox reads with `read_dataframe(dataset_id, dataset_part, platform_ids=[...], variables, start_datetime, end_datetime)`. That returns a long table: variable, platform_id, platform_type, time, lat, lon, depth, value, value_qc, institution, doi. One platform-month takes about 3 s.
Variables we map: TEMP→temp (°C), PSAL→sal, DOXY→o2 (mmol m-3), OSAT→o2_sat (%), CPHL/FLU2→chl (mg m-3; FLU2 = fluorescence-derived), TUR4→turb (units "1", turbidity), NTRA→no3, PHOS→po4, PHPH→ph, SLEV→sea_level (m, relative to the gauge datum), VHM0→wave_height, WSPD→wind_speed, EWCT/NSCT/HCSP→currents.
Platform list: `insitu_platforms()` downloads `index_platform.txt` and `index_history.txt` with `copernicusmarine.get(..., index_parts=True)` (needs login). On 2026-11-23 there were **202 platforms in 43.4–45.6 N / 28–31 E, of which 12 were live (an observation in the last 7 days)**.

Romanian platforms worth using (codes as in `platform_ids`):
| platform | where | variables | data |
|---|---|---|---|
| EUXRoOB01 / OB02 / OB03 | offshore buoys 44.71N 30.76E / 44.33N 30.41E / 43.98N 29.92E (GeoEcoMar) | TEMP PSAL FLU2 DOXY OSAT TUR4, currents, met | 2025-01 to 2026-09-01. **Best for ecosystem health** (T, S, chl, O2, turbidity together). Verified: EUXRoOB02 June 2025 gave 613 rows with chl, o2, o2_sat, sal, temp, turb, wind_speed, current_speed. |
| EUXRo01 / 02 / 03 | same sites, older buoys | as above | 2013 to 2022/2023 |
| CG | Mangalia mooring 43.80N 28.61E | TEMP FLU2 DOXY TUR4, currents | 2016 to 2023-12 |
| 15480 / 15360 / 15428 / 15499 | NIMH coastal stations Constanța / Sulina / ~Gura Portiței / Mangalia | TEMP (6-hourly) | 2018 onwards. 15480 and 15360 are live. Verified: 15480 last value 2026-11-22 12:00, ~11 °C |
| SPOT1622 / SPOT1624 / SPOT1383, WAVEB04 | wave buoys off Constanța–Mangalia | TEMP, VHM0, waves, wind | SPOT1624 and WAVEB04 are live |
| EUXRoCB01 / 02 / 03 (+ AWAC) | coastal buoys Sulina / Constanța / Mangalia | currents, met, waves (no temperature) | live |
| IOC-csta2, IOC-csta3, IOC-mang, Sulina | tide gauges | SLEV | csta2 and csta3 are live |
| PO1–5, SG1–4, SU1–3, ML1–3, MG4–5, EC3–5, GB2, CZ3 | ADCP transects (Grigore Antipa), May–June 2021 | currents only | one cruise |
| 6900807 (Argo), 8901034 (glider) | offshore profiles | T S O2 chl … | occasional |

## 3. Public API (module `marinekit.sources.copernicus`)
```python
CATALOG: dict[str, dict]        # key -> dataset_id (str or candidate list), product, vars{native: canonical}, origin, res_deg, freq, clim, doi, description
INSITU_RO: dict[str, str]       # notable Romanian in-situ platforms
is_logged_in(check_online=False) -> bool
login_help() -> str
class CopernicusLoginRequired(RuntimeError)
fetch_timeseries(key, lat, lon, start, end, variables=None, depth=None, method=None, box_deg=None, max_age_h=None, platform=None) -> pd.DataFrame
fetch_field(key, bbox=BBOX_RO, time=None, variable=None, depth=None, max_age_h=None) -> xr.DataArray   # dims (time[1], lat, lon)
climatology(key, lat, lon, variable=None, years=None, freq="doy"|"month", window=11, smooth=31, depth=None) -> pd.DataFrame  # mean,std,p10,p50,p90,n
anomalies(df, clim, variable=None) -> pd.DataFrame   # + clim_mean, clim_p10, clim_p90, anomaly, zscore, flag(+1 > p90, -1 < p10)
insitu_platforms(bbox=(28.0, 43.4, 31.0, 45.6)) -> pd.DataFrame
nearest_platform(lat, lon, variables=None, live_only=False) -> str
nearest_platforms(lat, lon, variables=None, start=None, end=None, live_only=False, n=5) -> list[str]
fetch_insitu(platform_id, start, end, variables=None, depth=None, good_qc_only=True, max_age_h=None) -> pd.DataFrame
wmts_layers(key=None, product_id=None) -> list[dict]              # no login
wmts_tile_url(key, variable=None, time=None, style=None, elevation=None) -> str   # XYZ template for folium
wmts_legend_url(key, variable=None) -> str | None
check_tile(key, variable=None, z=6, lat=44.17, lon=28.72, time=None) -> dict
describe_dataset(key) -> dict                                       # no login
```
- **Point extraction.** The module asks the server for a small box around the point, with half-width 2.5 × the grid step and at least 0.03°. `method="nearest"` (models, L4) takes the nearest cell that has valid data, so it avoids land cells. `method="box"` (the default for gappy L3) averages all cells in the box. If no valid cell is found, it retries once with a box 3× larger. `df.attrs` records `grid_lat`, `grid_lon`, `distance_km`, `depth_m`, `n_cells`, `dataset` (the id actually used), `citation` and `retrieved`.
- **Depth.** Surface by default (first level: 0.50 m physics, 0.25 m BGC). `depth=d` takes the nearest model level.
- **`climatology`** uses the entry's `clim` key: phy_* → rea_phy_*, bgc_* → rea_bgc_*, sat_chl_l4_nrt → sat_chl_l4_my, sat_kd490_nrt → sat_kd490_my, sst_* → sst_l4_rep. Default periods: reanalysis 1993-2022, ocean colour 1998-2022, SST 1991-2020. The method is day-of-year statistics pooled over an 11-day window, then smoothed with a 31-day circular running mean (as in Hobday et al. 2016). Each climatology is a single point download of 30 years: **about 4-7 s, a few hundred kB**.
- **Cache** lives in `data/cache/copernicus/`: parquet plus `.json` attrs for series, `.nc` for fields, and the WMTS XML and in-situ index files. Requests whose end date is more than 10 days ago are cached forever. Recent, NRT and forecast requests are refreshed after 12 h (`max_age_h` overrides). After the full sweep the cache was about 10 MB.
- **folium:** `folium.TileLayer(tiles=wmts_tile_url("sat_chl_l4_nrt", time="2026-11-20"), attr="E.U. Copernicus Marine Service", overlay=True, name="Chl-a")`.

## 4. Verification log (2026-11-23, Europe/Bucharest afternoon)
- `copernicusmarine login --check-credentials-valid` → "Valid credentials from configuration file".
- Full catalogue sweep (script loop over every CATALOG key except in-situ, at Constanța): **33/33 gridded keys: 33/33 time series OK, 33/33 small fields OK (bbox 28.5–29.2E, 43.9–44.5N), 25/25 climatologies OK (every key with a reference dataset), 0 failures.** Each first request took 3–7 s. Sample values:
  - phy_temp, 2026-11-09 to 11-25 (includes forecast): mean 13.9 °C. Reanalysis climatology at doy 327: mean 11.74, p10 9.9, p90 13.51 °C.
  - sst_l4_nrt on 2026-11-23: 13.92 °C. Climatology from sst_l4_rep 1991-2020 at doy 327: mean 11.61, p90 13.5, so `anomalies()` gives +2.3 °C, z = 1.57, flag +1. This agrees with the ready-made `sst_anom_nrt` product (+0.6 to +2.3 °C in the last 2 weeks, 3 km offshore).
  - sat_chl_l4_nrt, last 2 weeks: 2.4 mg m-3. Satellite chl climatology 1998-2022 (25 years), monthly: Jan mean 2.72, May mean 7.2 (spring bloom).
  - bgc_o2: 283 mmol m-3. Reanalysis O2 climatology at doy 327: 300 (p10 284, p90 321).
  - wav: 385 hourly values, mean Hs 0.83 m. bgc_car pH 8.27. phy_sal 17.3. phy_mld 12.6 m.
  - Long reads: 32 years of daily reanalysis temperature at one point took 4.2 s. SST REP 1982–2026 (16 368 days) took 3.3 s. 29 years of satellite chl L4 MY took 4.6 s.
- In-situ: `insitu_platforms()` gave 202 platforms, 12 live. `fetch_insitu("15480", last 10 days, ["temp"])` gave 25 values, last 2026-11-22 12:00. `fetch_insitu("EUXRoOB02", 2025-06)` gave 613 rows × 8 variables. `fetch_timeseries("insitu_bs", Constanța, last 5 days, ["temp"])` picked platform 15480 automatically.
- Without credentials (fake HOME): `is_logged_in()` returned False, `fetch_timeseries` and `fetch_insitu` raised `CopernicusLoginRequired`, and `check_tile` and `describe_dataset` still worked.
- Built-in smoke test (`python -m marinekit.sources.copernicus`): **29/29 steps OK**.
- **NOT VERIFIED:** the exact update schedules. They are inferred from today's time ranges: model analysis/forecast daily, with ~10 days of forecast; ocean-colour NRT ~1 day behind; SST NRT same day; SST REP ~1 month behind; in-situ `latest` hours behind; reanalysis extended about yearly. The vertical datum of the tide-gauge `SLEV` is also not verified. `TUR4` units ("1") are taken from the catalogue and are probably NTU/FTU.

## 5. Gotchas (important)
1. **A catalogue release goes live on 2026-11-24 at 13:00Z, during the hackathon.** `describe(show_all_versions=True)` shows new **202611** versions of most Black Sea model and ocean-colour datasets, released 2026-11-24. The old versions retire either on 2026-11-24 (ocean-colour MY) or on 2027-01-12 (models, SST). The code never pins a version, so the toolbox switches to the new default automatically and dataset IDs stay the same. However:
   - These four datasets **retire on 2026-11-24 with no newer version listed**: `cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D`, `…transp_my_l3-multi-1km_P1D`, `…optics_my_l3…`, `…reflectance_my_l3…`. The catalogue therefore lists fallbacks: OLCI 300 m L3 MY, and the new `…transp_my_l4-gapfree-multi-1km_P1D-m`.
   - New ids that appear: `cmems_obs-oc_blk_bgc-{transp,optics,reflectance,car}_{my,nrt}_l4-gapfree-multi-1km_P1D-m` and `cmems_mod_blk_phy-temp_anfc_mrm-500m_*`.
   - New 202611 BGC versions add a `processing_status` variable. Variable names for the new MY ocean-colour versions were still empty in the catalogue today (**NOT VERIFIED**).
   - **Re-run the smoke test after 13:00Z on the 24th.** The cache keeps the demo working even if something breaks.
2. Without credentials the toolbox **prompts on stdin**, or returns `None` silently. Never call it without checking `is_logged_in()` first; the module does this for you.
3. Toolbox bug: `coordinates_selection_method="nearest"` with `maximum_depth` but no `minimum_depth` crashes (`TypeError '<' float and NoneType`). Also, a depth window of `[0, 0]` is rejected as out of bounds, because the first level is 0.25 or 0.50 m. The module requests a depth window and picks the level itself.
4. SST comes in **kelvin**. The module converts to °C. Model and in-situ O2 are in **mmol m-3** (canonical `o2`); mg/L = × 0.032.
5. The SST L4 grid is masked near the coast. At Constanța the nearest valid SST cell is 3 km offshore. The coastal station 15480 reads ~11 °C while satellite SST 3 km out reads ~13.9 °C: a real coastal versus offshore difference to keep in mind when comparing observations with models and satellites.
6. **Model nitrate is inconsistent across systems.** Reanalysis surface NO3 at Constanța averages 12–41 mmol m-3 per year over 1993–2023, then falls to ~0.01 in 2024 (quarterly means 0.9, 0.001, 0.009, 0.009). The analysis/forecast system gives 0–7. Over the Oct–Dec 2024 overlap, analysis/forecast minus reanalysis was +1.76 mg m-3 for chl (r = 0.10), −6.6 mmol m-3 for O2 (r = −0.25) and +1.3 for NO3. For temperature (Dec 2024–Jul 2025) it was +0.22 °C (r = 1.00), and for salinity −0.44 (r = 0.88). **Anomalies of model BGC against a reanalysis climatology mostly reflect differences between the two model systems.** Use the satellite chl climatology (sat_chl_l4_my) for chl, and treat nutrient and O2 anomalies with care. Temperature and salinity are fine.
7. `sat_chl_l4_nrt` is a rolling window of only ~3 weeks. For longer recent series use `sat_chl_l4_my`, which runs to about 12 days ago.
8. L3 products are gappy. The high-res L3 (`sat_hr_l3`) had only 3 usable days between 2026-10-20 and 11-21 in the Constanța box (10-25, 11-07, 11-12). `fetch_field` searches up to 16 days back for a cloud-free step, and `fetch_timeseries` uses box averaging.
9. The physics reanalysis ends 2025-07-31 and the BGC reanalysis ends 2024-12-31. The physics analysis/forecast starts 2024-12-01 and the BGC analysis/forecast 2024-10-03. No single model system covers 1993 to today.
10. The toolbox logs a lot (INFO lines, retirement warnings). The module sets the `copernicusmarine` logger to ERROR; override with env `MARINEKIT_CMEMS_LOGLEVEL=INFO`. Note that `import copernicusmarine` re-runs `dictConfig`, so the module imports it first.
11. In-situ: data is spread over three parts (`history`, `monthly`, `latest`), so `fetch_insitu` queries the ones that overlap the window and de-duplicates. Only QC 1/2 values are kept by default.

## 6. Citation and licence
- Acknowledge every product as: "Generated using E.U. Copernicus Marine Service Information; https://doi.org/<product DOI>". The DOIs (read from `describe()` on 2026-11-23) are mds-00355 (PHY anfc), mds-00354 (BGC anfc), mds-00360 (WAV anfc), mds-00356 (PHY MY), mds-00372 (BGC MY), moi-00301/00302/00303/00304 (OC L3 NRT / L4 NRT / L3 MY / L4 MY), moi-00086/00087 (HR OC L3/L4), moi-00159/00160 (SST NRT/REP), moi-00033 (In Situ BS). Every DataFrame/DataArray carries a `citation` attr.
- Licence: Copernicus Marine Service data is free and open, under the Copernicus Marine licence (https://marine.copernicus.eu/user-corner/service-commitments-and-licence); attribution is required. The exact licence text was **NOT VERIFIED** today. In-situ files also carry per-network DOIs (the `doi` column), which should be cited when the data are published.
