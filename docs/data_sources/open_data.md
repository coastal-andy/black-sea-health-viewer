# No-login open data sources (satellite ERDDAP/THREDDS + Open-Meteo)

Module: `src/marinekit/sources/open_data.py`. Cache: `data/cache/open_data/`.
All checks below were run live on **2026-11-23** from the team laptop (python requests / curl) unless marked NOT VERIFIED.
Test point: Constanța (44.17 N, 28.72 E); test map: `BBOX_RO` = (28.4, 43.6, 30.6, 45.4).

## Quick pick

| Need | Key in `CATALOG` | Latest date on server (2026-11-23) | Record start |
|---|---|---|---|
| SST, freshest, gap-free | `sst_blended` | 2026-11-22 | 2019-07-22 |
| SST, climatology base | `sst_coraltemp` (PIFSC `CRW_sst_v3_1`, fallback CoastWatch) | 2026-11-21 | 1985-01-01 |
| SST anomaly, ready-made | `sst_anom_crw` (PIFSC `CRW_sst_anom_v1_0`) | 2026-11-21 | 1985-01-01 |
| Chl-a, freshest (cloud gaps) | `chl_olci_s3a` / `chl_olci_s3b` | 2026-11-21 | 2019-06 |
| Chl-a, gap-filled | `chl_dineof` | 2026-11-05 | 2018-01-01 |
| Chl-a, long record (climatology) | `chl_occi_8day` / `chl_occi_daily` | 2026-09-22 / 2026-09-30 | 1997-09-04 |
| Chl-a, 2012- daily (S-NPP) | `chl_viirs_snpp_sq` (PIFSC `noaa_snpp_chla_daily`) | 2026-11-06 | 2012-01-02 |
| Chl-a monthly | `chl_occi_monthly` | 2026-09-01 | 1997-09 |
| Kd490 (turbidity proxy) | `kd490_dineof`, `kd490_viirs_snpp_sq`, `kd490_occi_8day` | 2026-11-05 / 11-06 / 09-22 | 2018 / 2012 / 1997 |
| SPM (turbidity proxy) | `spm_dineof` | 2026-11-05 | 2018-01-01 |
| Waves, currents, model SST, sea level | `marine_weather()` | forecast to +7 d | waves 2021-10, currents 2022-01, SST/SSH 2022-11 |
| Wind, air temperature | `marine_weather()` | today (+16 d forecast) | 1940 (ERA5) |
| Danube discharge | `danube_discharge()` | today (+~30 d forecast) | 1997-01-01 |

## 1. NOAA CoastWatch central ERDDAP — `https://coastwatch.noaa.gov/erddap`

Fallback mirror with the same dataset IDs: `https://polarwatch.noaa.gov/erddap` (verified reachable; list of IDs identical).
Access: griddap, e.g. `.../griddap/<id>.csv?<var>[(t0):1:(t1)][(0.0)][(lat0):1:(lat1)][(lon0):1:(lon1)]` (the `[(0.0)]` altitude
dimension only for ocean-colour datasets). Licence: NOAA data, public domain; Copernicus OLCI data "courtesy of the Copernicus Programme".

| ID | Variable | Grid | Coverage (time_coverage_end on 2026-11-23) |
|---|---|---|---|
| `noaacrwsstDaily` (CoralTemp v3.1) | `analysed_sst` °C | 0.05°, daily L4 | 1985-01-01 → 2026-11-21 |
| `noaacwBLENDEDsstDNDaily` (Geo-Polar Blended D+N) | `analysed_sst` °C | 0.05°, daily L4 | 2019-07-22 → 2026-11-22 |
| `noaacwS3AOLCIchlaDaily` / `noaacwS3BOLCIchlaDaily` | `chlor_a` mg m⁻³ | 0.0375°, daily L3 | 2019-06 → 2026-11-21 |
| `noaacwN20VIIRSchlaDaily` | `chlor_a` | 0.0375°, daily L3 | 2021-08-26 → 2026-11-15 |
| `noaacwNPPVIIRSSQchlaDaily` (science quality) | `chlor_a` | 0.0375°, daily L3 | 2012-01-02 → 2026-11-06 |
| `noaacwNPPN20S3ASCIDINEOF2kmDaily` (gap-filled) | `chlor_a` | ~0.0208°, daily L4 | 2018-01-01 → 2026-11-05 |
| `noaacwNPPN20S3AkdSCIDINEOF2kmDaily` (gap-filled) | `kd_490` m⁻¹ | ~0.0208° | 2018-01-01 → 2026-11-05 |
| `noaacwNPPVIIRSSQkd490Daily` | `kd_490` | 0.0375° | 2012-01-02 → 2026-11-06 |
| `noaacwNPPN20S3AspmSCIDINEOF2kmDaily` (gap-filled) | `spm` mg L⁻¹ (= g m⁻³) | ~0.0208° | 2018-01-01 → 2026-11-05 |

Verified 2026-11-23: ran a point box ±0.1° around Constanța, 2026-09-20 → last:
- CoralTemp: 63/63 days valid, 23/25 pixels valid (coast masked), 2026-11-21 window mean 13.85 °C (21 s).
- Blended SST: 64/64 days valid, 2026-11-22 mean 13.64 °C.
- OLCI S-3A chl: only 24/60 days with any valid pixel (November clouds); values 0.8–30 mg m⁻³ near the coast.
- VIIRS N20 chl: 24/54 days valid, 4.7–9.6 mg m⁻³.
- DINEOF chl / Kd490 / SPM: every day valid (gap-filled), 2026-11-05: chl 2.1 mg m⁻³, Kd490 0.44 m⁻¹, SPM 19.9 mg L⁻¹.

Gotchas
- **Coastal masking**: 2 of 25 CoralTemp pixels in the ±0.1° box are land; `fetch_timeseries` picks the nearest pixel that
  is valid ≥50 % as often as the best pixel in the window and reports `pixel_lat/pixel_lon/pixel_dist_km`.
- **Case-2 waters**: standard OC algorithms overestimate chl in the Danube-influenced, sediment-rich coastal strip
  (values of 10–30 mg m⁻³ are partly CDOM/SPM). Compare against climatology/anomaly, not absolute thresholds.
- S-NPP VIIRS series titles say "2017/2012 to 2026-11-02": S-NPP ocean colour appears to end in early Nov 2026 → use NOAA-20/OLCI going forward.
- `noaacwNPPN20VIIRSkd490Daily` ends 2021-09-01 (do not use).
- DINEOF products lag ~18 days (latest 2026-11-05).
- Intermittent `SSLEOFError` from coastwatch.noaa.gov on parallel requests → module retries and falls back to polarwatch.
- Latitude axis of the ocean-colour sets is descending; ERDDAP on this server accepts (min):(max) anyway.
- **Proxy time-out ≈ 20 s**: a 1-year single-pixel CoralTemp request returned `502 Proxy Error` after ~21 s (twice); a 63-day
  ±0.1° box took 21 s and succeeded. The module therefore splits CoastWatch/PolarWatch requests into 40-day chunks
  (cached individually) and serves long records from PIFSC instead.
- Requests whose end is after the last time step return 404 "no matching results" → the module clamps the period to
  `[record_start, latest_time(key)]`.

## 2. NOAA PIFSC OceanWatch ERDDAP — `https://oceanwatch.pifsc.noaa.gov/erddap` (OC-CCI, CoralTemp, VIIRS; fast for long series)

All global, longitude 0–360 (module converts). No proxy time-out: a 30-year single-pixel CoralTemp request
(1991-01-01 → 2020-12-31, 10 958 rows) took 329 s and succeeded; OC-CCI 8-day 1998–2020 single pixel took 28.5 s.

| ID | Variable | Grid | Coverage |
|---|---|---|---|
| `CRW_sst_v3_1` (CoralTemp) | `analysed_sst` °C | 0.05°, daily | 1985-01-01 → 2026-11-21 |
| `CRW_sst_anom_v1_0` | `sea_surface_temperature_anomaly` °C | 0.05°, daily | 1985-01-01 → 2026-11-21 |
| `CRW_sst_v3_1_monthly` | SST monthly | 0.05° | 1985- (NOT tested) |
| `goes-poes-1d-ghrsst-RAN` | Geo-Polar blended reanalysis, `analysed_sst` in **K** | 0.05°, daily | 2002-09-01 → 2026-11-22 (not in catalog) |
| `noaa_snpp_chla_daily` / `noaa_snpp_kd490_daily` | `chlor_a` / `kd_490` | 0.0375° | 2012-01-02 → 2026-11-06 |
| `aqua_chla_1d_2018_0` (MODIS-Aqua) | `chlor_a` | 1/24° | 2002-07-04 → **2022-05-31** (stale, not used) |
| `esa-cci-chla-8d-v6-0` | `chlor_a` | 1/24°, 8-day | 1997-09-04 → 2026-09-22 |
| `esa-cci-chla-monthly-v6-0` | `chlor_a` | 1/24°, monthly | 1997-09 → 2026-09-01 |
| `esa-cci-kd-8d-v6-0` | `kd_490` | 1/24°, 8-day | 1997-09-04 → 2026-09-22 |

Longitude is 0–360 (fine for the Black Sea, the module handles it). Licence: ESA CCI data policy, free and open; cite
Sathyendranath et al. (2019), *Sensors* 19:4285, and ESA OC-CCI v6.0.
Verified 2026-11-23: box ±0.1° at Constanța, 2026-07-01 → last: 1.4 s, 31–32 valid pixels per 8-day step, 2026-09-22 mean 2.48 mg m⁻³.

## 3. ESA OC-CCI THREDDS (Plymouth Marine Laboratory) — `https://www.oceancolour.org/thredds`

Datasets `CCI_ALL-v6.0-DAILY`, `-5DAY`, `-8DAY`, `-MONTHLY` (also v5.0). Variables include `chlor_a`, `kd_490`, Rrs, IOPs, per-sensor nobs.
- NCSS (used by the module): `https://www.oceancolour.org/thredds/ncss/CCI_ALL-v6.0-DAILY?var=chlor_a&latitude=..&longitude=..&time_start=..&time_end=..&accept=csv`
  (point) or `north/south/west/east ... accept=netcdf` (grid).
- Verified 2026-11-23: point CSV 2026-07-01 → 2026-12-31 returned up to 2026-09-30 (15 s), e.g. 2026-09-30 chl 4.07 mg m⁻³, Kd490 0.52 m⁻¹;
  NCSS netCDF grid of BBOX_RO for 2026-09-27: 44×54 cells, 931 valid (2.5 s). `dataset.xml` TimeSpan end = 2026-09-30.
- Gotcha: missing values come as `9.969e36` in CSV (module masks > 1e30).
- Gotcha: OPeNDAP (`/thredds/dodsC/...`) failed from Python here: the netCDF4 wheel's libcurl reported
  "Problem with the SSL CA cert" (setting `CURL_CA_BUNDLE` did not help). NCSS over requests works, so we use that.

## 4. NOAA CoastWatch West Coast (pfeg) ERDDAP — `https://coastwatch.pfeg.noaa.gov/erddap` (and `upwell.pfeg.noaa.gov`)

Hosts MUR SST (`jplMURSST41`, 0.01°), OISST (`ncdcOisst21Agg_LonPM180`) and OC-CCI (`pmlEsaCCI60OceanColor*`).
**NOT VERIFIED — unreachable 2026-11-23**: TCP connect timeouts (200 s) on both hostnames, repeated several times. Not used by
the module. If it comes back, MUR adds 1 km coastal SST detail.
NOAA PSL OISST THREDDS (`psl.noaa.gov/thredds/ncss/Datasets/noaa.oisst.v2.highres/...`) returned a "maintenance downtime" page. NOT VERIFIED.

## 5. Open-Meteo Marine API — `https://marine-api.open-meteo.com/v1/marine` (origin = model)

No key, CC BY 4.0, fair-use < 10 000 calls/day. Hourly variables used: `wave_height, wave_period, wave_direction,
sea_surface_temperature, ocean_current_velocity, ocean_current_direction, sea_level_height_msl`;
`wind_speed_unit=ms` also converts current speed to m/s; `cell_selection=sea`.
Models behind `best_match` in the Black Sea (verified by `models=`): `meteofrance_wave` (MFWAM), `ewam`, `gwam`, `ecmwf_wam025`
(waves) and `meteofrance_currents` (SMOC: SST, currents, SSH). `era5_ocean` gives waves only (no SST) here.
Verified 2026-11-23:
- Constanța request snaps to cell 44.208 N, 28.792 E (marine grid ≈ 0.083°); Mangalia (43.79, 28.64) snaps to 43.708, 28.708 (~9 km away!) — check `attrs['marine_cell']`.
- History depth at Constanța (first non-null hour): waves 2021-10-01, currents 2022-01-01, SST and SSH 2022-11-23. Requests back to 1950 succeed but return nulls.
- 2026-11-20 → 11-25 hourly returned SST 14.0 °C, Hs 0.38 m.
- Model SST (SMOC) is effectively daily (same value every hour of a day). Before 2022 the marine columns are NaN; weather columns still filled.

## 6. Open-Meteo weather: archive (ERA5) + forecast — origin = reanalysis (past) / model (future)

- `https://archive-api.open-meteo.com/v1/archive` — ERA5/ERA5-Land blend, 1940 → today. Verified: 1940-01-01 daily mean T2m −10.6 °C at cell 44.11 N 28.63 E;
  2026-11-10 → 2026-11-23 returned complete daily values (most recent days are ERA5T / IFS-filled).
- `https://api.open-meteo.com/v1/forecast` — used for days after today (up to 16 d). Verified: past_days=7 hourly wind returned.
- Variables: `temperature_2m, wind_speed_10m, wind_direction_10m, precipitation, shortwave_radiation`.

## 7. Danube discharge — Open-Meteo Flood API (GloFAS v4) — `https://flood-api.open-meteo.com/v1/flood`

No key (unlike CDS/EWDS GloFAS, which needs an account). Daily `river_discharge` (+ ensemble `river_discharge_median/p25/p75/min/max/mean`).
- **Location matters**: the 0.05° GloFAS river network does not resolve the delta: 45.2 N 29.6 E (Sulina area) returns ~0.05 m³/s.
  A scan of 49 cells found the main channel; the module uses **45.225 N, 28.675 E** (Ceatal Izmail, just upstream of the
  Chilia/Tulcea bifurcation = total Danube inflow to the Black Sea). Upstream cells (Isaccea 45.275/28.375, Reni 45.475/28.175) give ~the same flow.
- Allowed range 1984-01-01 → 2027-11-23, but this cell is **null before 1997-01-01**; 10 919 valid days 1997-01-01 → 2026-11-23.
- Verified 2026-11-23: annual means 1997–2025 of 4 838 (2003, drought) to 9 042 m³/s (2010, flood), long-term ≈ 6 500 m³/s (matches literature);
  2026 is low (mean 4 348; Q3–Q4 ≈ 2 700 m³/s). 2026-11-15 → 11-25: 2 850 → 5 046 m³/s (rising, forecast part from 11-24).
  `models=seamless_v4` and `forecast_v4` identical for recent days; `consolidated_v4` is null for recent days.
- Licence: Open-Meteo CC BY 4.0; GloFAS © Copernicus Emergency Management Service.
- Other open Danube sources checked: GRDC (grdc.bafg.de, site up) requires a data request form — not instant. Romanian
  INHGA / Danube Delta daily bulletins: NOT VERIFIED (HTML/PDF, no API known).

## 8. Other options (login required — documented only)

- **NASA OceanColor (oceandata.sci.gsfc.nasa.gov)**: `getfile` L3 downloads redirect to Earthdata URS login (verified: HTTP 302 → `/getfile/urs/`);
  OPeNDAP root returned HTTP 429 (rate limited). Needs a free Earthdata account. The same VIIRS/OLCI products are available via CoastWatch above.
- **PO.DAAC MUR / GHRSST**: Earthdata login (NOT VERIFIED today; known requirement).
- **Copernicus Data Space Ecosystem**: OData catalogue search is open (verified HTTP 200), downloads need a (free) account token.
- **Copernicus Marine / CDS / EWDS (GloFAS)**: account needed — handled by other modules.

## Climatology approach (`climatology()`)

1. Pick the pixel once: nearest-valid pixel in a ±0.1° window from a 92-day summer probe (Jun–Aug of the last reference year; cheap, handles coastal masks).
2. Download only that pixel for the full reference period (PIFSC: ≤10-year chunks; CoralTemp 1991–2020 = 10 958 rows, ~4–5 min once, then cached).
3. For each day-of-year 1–366 pool all values within ±15 days (31-day window, circular) over the reference years →
   mean, std, p10, p50, p90, n. For chl/Kd490/SPM statistics are computed in log10 space (mean = geometric mean,
   std in log10 units).
4. `anomalies()` joins a recent series with the climatology at the same pixel → anomaly (or ratio for log variables), z-score,
   above_p90 / below_p10 flags. Default reference periods: SST 1991–2020 (WMO normal, CoralTemp), OC-CCI chl/Kd490 1998–2020,
   VIIRS S-NPP 2012–2025.

Verified 2026-11-23 (`cd src && python -m marinekit.sources.open_data --clim`):
- `climatology("chl_occi_8day", 44.17, 28.72)` (1998–2020): 859 valid 8-day values, 10 s; DOY 327 geometric mean 2.98 mg m⁻³
  (p10 1.90, p90 5.24). Sept 2026 chl was 0.56–0.85× climatology (z −0.3 to −1.0).
- `climatology("sst_coraltemp", 44.17, 28.72)` (1991–2020): 10 958 daily values, 256 s first call (then cached); DOY 327 mean 11.99 °C,
  std 1.72, p10 9.75, p90 14.13. 2026-11-21 SST 13.83 °C → anomaly +1.56 °C, z 0.90.
- Note: CRW's own anomaly (`sst_anom_crw`) for the same day is +2.57 °C, because CRW uses a different base (1985–2012, built from
  monthly means) — always state the reference period when showing anomalies.

## Module usage

```python
from marinekit.sources import open_data as od, STATIONS, BBOX_RO
lat, lon = STATIONS["Constanta"]
od.CATALOG.keys(); od.DEFAULTS["chl"]          # pick datasets
od.latest_time("chl_dineof")                    # -> Timestamp('2026-11-05 12:00')
ts = od.fetch_timeseries("sst_blended", lat, lon, "2026-09-01", "2026-11-23")   # df['sst'], attrs['pixel_lat'] ...
da = od.fetch_field("chl_dineof", BBOX_RO, None)  # latest map, DataArray (time, lat, lon)
cl = od.climatology("sst_coraltemp", lat, lon)    # DOY table mean/std/p10/p50/p90/n
an = od.anomalies("sst_coraltemp", lat, lon, "2026-10-01", "2026-11-23")
mw = od.marine_weather(lat, lon, "2026-11-01", "2026-11-26", freq="daily")
dq = od.danube_discharge("2000-01-01", "2026-12-20")   # includes GloFAS forecast rows (is_forecast)
```

Smoke test results 2026-11-23 at Constanța (pixel actually used / distance):
| key | latest | pixel | last valid value |
|---|---|---|---|
| sst_blended | 2026-11-22 | 44.175, 28.725 (0.7 km) | 13.61 °C |
| sst_coraltemp | 2026-11-21 | 44.175, 28.725 | 13.83 °C |
| sst_anom_crw | 2026-11-21 | 44.175, 28.725 | +2.57 °C |
| chl_olci_s3a | 2026-11-21 | 44.156, 28.706 (1.9 km) | 2026-11-20: 0.92 mg m⁻³ (18/57 days valid) |
| chl_dineof | 2026-11-05 | 44.177, 28.719 (0.8 km) | 1.49 mg m⁻³ |
| kd490_dineof | 2026-11-05 | 44.177, 28.719 | 0.20 m⁻¹ |
| spm_dineof | 2026-11-05 | 44.177, 28.719 | 0.96 mg L⁻¹ (box mean incl. near-shore pixels ≈ 20) |
| chl_occi_8day | 2026-09-22 | 44.188, 28.729 (2.1 km) | 2.78 mg m⁻³ |
| chl_occi_daily | 2026-09-30 | 44.188, 28.729 | 4.07 mg m⁻³ (51/67 days valid) |
Fields over BBOX_RO: sst_blended 2026-11-21 38×44 cells (1234 valid, median 13.67 °C); chl_dineof 2026-11-05 88×106 (7536 valid,
median 0.86 mg m⁻³); chl_occi_daily 2026-09-27 44×54 (931 valid). Open-Meteo marine daily 2026-11-20…25 and Danube discharge
2026-11-13…12-03 (2 910 → 5 584 m³/s, forecast from 11-24) returned without gaps.

Caching: every request chunk is pickled under `data/cache/open_data/` (chunks aligned to fixed day boundaries so they are
reused); chunks ending within the last 21 days are re-fetched, but the cached copy is used if the network is down.
Open-Meteo responses are cached as JSON the same way.
