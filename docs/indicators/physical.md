# Physical indicators: Romanian Black Sea shelf

Challenge 04 "Ecosystem Health" asks for indicators that are scientifically justified, use reference conditions, separate natural variability from real change, and state their uncertainty and the origin of every value. This file does that for the **physical** side. Chemistry and biology have their own files, `chemical.md` and `biological.md`.

- **Test point:** Constanța, 44.17 N 28.72 E. The model cell used is 44.175 N 28.725 E, 0.7 km away, with a water depth of about 26.5 m.
- **Proof of computability:** [`scripts/indicators/physical_check.py`](../../scripts/indicators/physical_check.py). Its output, run on 2026-11-23, is in [`physical_check_output.txt`](../../scripts/indicators/physical_check_output.txt). Every number marked "(live)" below comes from that run.
- **Caching:** all data goes through `src/marinekit/sources/`, which caches it on disk, so a re-run works offline.

**Labels used on every number:**

| Label | What it means |
|---|---|
| **(live)** | We fetched or computed it ourselves on 2026-11-23. |
| **(lit)** | Taken from a publication; the link is given. |
| **(official)** | A threshold set in EU law or in Romania's MSFD reporting. |
| **(proposed)** | A threshold the team chose. NIMRD should confirm or replace it. |

---

## 1. Shortlist for the dashboard (ranked)

### 1.1 How we ranked them

Each indicator was scored on four questions:
1. How strongly does it link to ecosystem state (oxygen, blooms, benthos)?
2. How reliable and long is the data record?
3. Does it help explain other anomalies, so we can tell natural from real change?
4. Does a sector manager act on it?

### 1.2 The seven indicators

| Rank | Indicator | Data key(s) | Reference | Status (2026-11-23, Constanța) |
|---|---|---|---|---|
| 1 | SST anomaly, marine heatwaves and cold spells | `sst_l4_rep` + `sst_l4_nrt` (copernicus) | Day-of-year climatology 1991-2020 | **Computed live** |
| 2 | Upwelling flag | `sst_l4_rep`/`sst_l4_nrt` at the coast and 47 km offshore, plus `od.marine_weather` wind (ERA5) | Summer 1991-2020 distribution | **Computed live** |
| 3 | Danube freshwater influence | `od.danube_discharge` (GloFAS), `phy_sal`, `rea_phy_sal` | Discharge 1997-2025, salinity 1993-2022 | **Computed live** |
| 4 | Stratification strength (hypoxia precursor) | `phy_temp` (surface `thetao` and `bottomT`), `phy_sal` (surface and 26 m), `phy_mld`, plus the `rea_*` versions | Reanalysis 1993-2022 | **Computed live** |
| 5 | Transparency and light at the seabed | `sat_kd490_my` (`sat_kd490_nrt` for the latest days) | Satellite 1998-2022; Romanian Secchi GES values | **Computed live** at a point. **Not yet as a map** (needs bathymetry). |
| 6 | Bottom-temperature anomaly (benthic thermal stress) | `phy_temp` `bottomT`, `rea_phy_temp` | Reanalysis 1993-2022, bias-corrected | **Computed live** |
| 7 | Storm and resuspension index, plus surge | `wav`, `od.marine_weather` waves, emodnet `IOC-csta2`, `phy_ssh` | Hs 2021-2026 percentiles | **Computed live** |

**Two parameters are context layers, not indicators:**
- Surface currents (`phy_cur`).
- Turbidity and SPM (`spm_dineof`, `sat_hr_l3`, buoy `TUR4`). The chemical/biological sessions own water quality; we use these to explain clarity anomalies.

### 1.3 Formulas and algorithms

Shared notation:
- `clim(d)`, `sd(d)`, `p10(d)` and `p90(d)` are day-of-year statistics.
- They are pooled over an 11-day window around day `d` across the reference years, then smoothed with a 31-day circular running mean. This is the Hobday et al. (2016) recipe. It is built into `copernicus.climatology()` and reproduced for derived series by `doy_clim()` in the script.

**Status rule for every card:**

| Status | Condition |
|---|---|
| normal | Inside p10-p90. |
| watch | Outside p10-p90 for 1-4 days. |
| alert | Outside p10-p90 for 5 days or more. |

The persistence part of this rule comes from Hobday. Applying it to the other indicators is (proposed).

#### P1. SST anomaly, marine heatwave (MHW) and marine cold spell (MCS)

**Formula**
```
anom(t) = SST(t) - clim(doy)               reference 1991-2020 (WMO normal), sst_l4_rep
z(t)    = anom(t) / sd(doy)
MHW     = SST > p90(doy) for >= 5 consecutive days; gaps <= 2 days merge two events   (Hobday et al. 2016)
MCS     = SST < p10(doy), same duration rules
category = floor( peak anom / (p90 - clim) ):  1 moderate, 2 strong, 3 severe, >= 4 extreme   (Hobday et al. 2018)
```

**Data handling**
- The recent end comes from `sst_l4_nrt`.
- We remove its mean offset against REP over the overlap. That offset was **+0.53 °C (live)** over 54 days.

**Live result**

| Item | Value |
|---|---|
| SST on 2026-11-23 | 13.39 °C |
| Anomaly | **+1.78 °C**, z = 1.21 |
| p90 threshold that day | 13.50 °C |
| Status | normal, at the warm edge |

- No heatwave since late June.
- The last heatwave was 2-6 Apr 2026 (moderate). It followed a long warm winter run: 19 Nov-7 Dec 2025, 12-23 Dec 2025 and 8-14 Jan 2026.
- Over 1982-2026 there were 86 heatwaves and 94 cold spells.
- Heatwave days per year rose from about 3 (1982-1991) to about 71 (2016-2025). The trend is **+18.7 ± 7.1 days per decade (live)**.
- Annual-mean SST trend 1982-2025: **+0.53 ± 0.13 °C per decade (live)**, 95 % CI, corrected for autocorrelation.

**Audience one-liners**
- **Public:** "The sea off Constanța is 1.8 °C warmer than usual for late November. That is not yet a heatwave."
- **Student:** "Anomaly = today's SST minus the 1991-2020 average for the same date. A heatwave means more than 5 days above the warmest 10 % for that date."
- **Stakeholder:** "Heatwave days have risen from a few per year to about 70 per year. Expect more heat stress for mussel farms and more summer bloom risk."

**Researcher note**
- The fixed 1991-2020 baseline counts long-term warming as heatwave days.
- For "events on top of the trend", also show a detrended or moving baseline (Hobday 2016 discusses both).
- The climatology pixel (REP, 1.1 km away) and the NRT pixel (3.1 km away) are not the same cell.
- The L4 analysis masks the first 1-3 km from the shore.

#### P2. Upwelling flag (summer, wind-driven)

**Formula**
```
dT_up(t) = SST_coast(44.17N 28.72E) - SST_offshore(44.17N 29.30E)            sst_l4_rep / sst_l4_nrt
UI(t)    = 100 * tau_along / (rho_w * f)     [m3 s-1 per 100 m of coast; + = offshore Ekman transport]
           tau_along = rho_a * Cd * |U10| * U10 . e_coast,  e_coast = 10 deg true (SSW->NNE),  Cd = 1.3e-3
           f = 2 * Omega * sin(44.17 deg);  hourly ERA5 wind, daily mean
UPWELLING  = month in Jun-Sep  AND  dT_up <= -2.0 C                              (proposed)
confirmed  = UPWELLING AND mean UI over the 3 previous days > 0                    (proposed)
```

**Why these thresholds**
- In summer the coastal strip is normally slightly warmer than offshore water, because it is shallow. The median Jun-Sep difference for 1991-2020 is **-0.39 °C (live)**.
- A drop of 2 °C or more below offshore is therefore an unusual event. The record is -5.4 °C on 2017-07-01 (live).
- Over 2015-2025, **88 % (live)** of SST-detected events followed 3 days of upwelling-favourable (southerly to south-westerly) wind.
- The correlation between dT_up and the lagged UI is r = **-0.44 (live)**.

**Live result**

| Item | Value |
|---|---|
| Mean upwelling days per summer, 1991-2020 | 4.8 |
| Maximum | 23 days (2003) |
| Recent summers | 20 days (2023), 12 (2025), 13 (2026) |
| Trend 1982-2025 | +1.5 ± 1.5 days per decade (not significant) |

- The cold spell of 27 Jul-11 Aug 2023 (P1, "strong") falls inside the 2023 upwelling season. That is natural variability, not degradation.
- The current flag is off, because it is not summer.

**Audience one-liners**
- **Public:** "Some summer days the beach water suddenly turns cold. South-west winds push the warm surface water out to sea, and cold deep water rises in its place."
- **Student:** "Ekman transport moves water 90° to the right of the wind. With the sea to the east, a southerly wind pushes surface water offshore."
- **Stakeholder:** "An upwelling flag explains sudden cold, salty and nutrient-rich water. Do not report it as pollution. It can stress farmed mussels, and it can trigger a bloom a few days later."

**Researcher note**
- Mihailov (2024) uses the CUTI and BEUTI indices. Our UI is the CUTI-like Ekman term without the geostrophic part.
- Validating against NIMRD's divergence-event list (31 events, 2000-2018) would be the natural test.

#### P3. Danube freshwater influence

**Formula**
```
Q_ratio(t)   = Q(t) / clim_Q(doy)              GloFAS v4 at Ceatal Izmail, reference 1997-2025
SSS_anom(t)  = SSS_model(t) - clim_SSS(doy)    phy_sal vs rea_phy_sal 1993-2022; correct the -0.44 system offset
PLUME        = SSS < p10(doy) AND mean Q_ratio over the previous 30 days > 1.2     (proposed)
LOW-FLOW     = 30-day mean Q_ratio < 0.6                                           (proposed)
```

**Lag**
- Monthly anomalies of discharge and of salinity at Constanța correlate best at a **1-month lag, r = -0.49 (live, reanalysis 1997-2022)**.
- At lag 0 the correlation is -0.30.
- So the dashboard should show the Danube with about 1 month of lead.

**Live result**
- Danube flow in Oct-Nov 2026 was **0.37-0.79 of normal**. The 2026 mean to date is 4,348 m³/s, against a 1997-2025 mean of 6,611 m³/s. The forecast returns to normal by early December.
- Surface salinity at Constanța has been **+0.4 to +1.5 above climatology** since September. It is consistent with the low flow: a natural driver of the observed state, not a sign of degradation.

**Audience one-liners**
- **Public:** "The Danube is carrying about half its usual water this autumn, so the sea off Constanța is saltier than usual."
- **Student:** "The Danube supplies about 70 % of the river water entering the Black Sea. Its plume turns south along the Romanian coast and reaches Constanța about a month later."
- **Stakeholder:** "High Danube flow means fresher, more turbid water rich in nutrients, so blooms are likely 2-6 weeks later. Use it to anticipate, not to blame."

**Researcher note**
- GloFAS is a model, but its long-term mean is within 4 % of the published value (Kara et al. 2008).
- The model salinity in the anfc system is biased by -0.44 against the reanalysis (Dec 2024-Jul 2025).

#### P4. Stratification strength (hypoxia precursor)

**Formula**
```
dsig(t)   = sigma_theta(T_bottom, S_bottom) - sigma_theta(T_surface, S_surface)    [kg m-3]   UNESCO EOS-80, p = 0
            split into a thermal part  dsig_T = sigma(T_b, S_s) - sigma(T_s, S_s)  and a haline part dsig_S = dsig - dsig_T
classes   : < 0.5 mixed;  0.5-2 weak;  > 2 stratified                                         (proposed)
anomaly   : dsig vs day-of-year clim of the reanalysis 1993-2022 (same cell, same levels)
HYPOXIA-RISK = Jun-Sep AND dsig > p90(doy) for >= 10 days                                     (proposed)
support   : MLD / water depth  (phy_mld; >= 0.9 means the whole column is mixed)
```

**Seasonal cycle (live, reanalysis 1993-2022, median Δσ in kg m⁻³)**

| Jan | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov |
|---|---|---|---|---|---|---|---|---|---|
| 0.1 | 0.3 | 0.8 | 2.2 | 3.7 | **4.0** | 3.7 | 2.3 | 0.8 | 0.3 |

- Salinity contributes about **37 %** of summer stratification at Constanța. That is the Danube's signature.

**Live result**
- The column was fully mixed from early October to early November: Δσ = 0.0, with MLD up to 20.7 m out of 26.5 m.
- On 2026-11-23, Δσ = 1.01 against a climatology of 0.49 (p90 1.20). It is weak but unusual for November.
- That stratification is mostly haline: bottom water is 1 unit saltier than the surface.

**Audience one-liners**
- **Public:** "In summer the sea forms layers, like oil on water, and the bottom layer can run out of oxygen."
- **Student:** "Δσ is the density difference between the bottom and the surface. Above about 2 kg m⁻³, wind can barely mix oxygen down to the seabed."
- **Stakeholder:** "Strong and long stratification in July-September is the early warning for bottom hypoxia and fish or mussel kills. Check bottom-oxygen data when it is flagged."

**Researcher note**
- Capet et al. (2013) found hypoxia on the north-western shelf at the end of every summer, 1981-2009, with SST before and late in the stratified season among its predictors.
- Our Δσ uses two model levels. A potential-energy anomaly (Simpson φ) over the full profile would be more robust and is a cheap upgrade.

#### P5. Transparency and light at the seabed

**Formula**
```
Kd490 anomaly : z_log = (log10 Kd490 - clim_log(doy)) / sd_log(doy);  ratio = 10^(log10 Kd490 - clim_log)   reference 1998-2022
Kd_PAR  = 0.0864 + 0.884*Kd490 - 0.00137/Kd490          (Morel et al. 2007, eq. 9)
Z_eu    = 4.605 / Kd_PAR                                  (1 % light depth)
Secchi ~= 1.1 / Kd_PAR                                    (factor tuned to INCDM coastal Secchi 2018-2023; the open-water rule 1.7 overestimates here)
E_bottom(%) = 100 * exp(-Kd_PAR * depth)                  (depth from EMODnet bathymetry)
SEAGRASS-OK = E_bottom >= 11 %                            (Duarte 1991, average seagrass depth limit) (lit)
habitat light depth  z_X = ln(100 / X) / Kd_PAR,   X = 11 % seagrass, 0.5 % leathery brown algae (Gongolaria/Cystoseira),
                     0.1 % foliose red algae (Phyllophora)          (Markager & Sand-Jensen 1992) (lit)
compare with RO-BG macrophyte targets: Gongolaria barbata max depth >= 10 m, Phyllophora / shade algae >= 17 m
                     (MSFD 2024 Annex 3, agreed with Bulgaria, "to be validated") (official, provisional)
D5C4 check: warm-season (May-Sep) 10th percentile of Secchi vs Romanian GES value 5.6 m (coastal), 2.3 m (transitional) (official, RO 2024)
```

**Live result**

| Item | Value |
|---|---|
| Kd490 on recent clear days | 0.18-0.48 m⁻¹ |
| Ratio to climatology | 0.4-1.0, i.e. clearer than usual |
| Approximate Secchi depth | 2.2-4.6 m (with the open-water factor 1.7 it would be 3.3-7.0 m) |
| 1 % light depth | 9-19 m |

- In the climatology, 8-21 % of surface light reaches 5 m depth, and only 0.7-4.4 % reaches 10 m.
- Habitat light depths (live, 1998-2022 climatology, annual median):

| Place | Seagrass (11 %) | Leathery brown algae (0.5 %) | Red algae (0.1 %) |
|---|---|---|---|
| Constanța | 6.2 m | 15.0 m | 19.5 m |
| Vama Veche | 6.5 m | 15.5 m | 20.3 m |
| Observed now (literature) | 0.8-3.3 m | 1-5 m | stable stands to about 10 m |

- The satellite-implied depths are deeper than what is observed (details in 2.13).

**Audience one-liners**
- **Public:** "You can see about 3-4 m down off Constanța this month, which is clearer than usual for November."
- **Student:** "Kd490 measures how fast blue light fades with depth. From it we estimate how much sunlight reaches the seabed."
- **Stakeholder:** "Seagrass and mussel beds need clear water. Dredging plumes, Danube floods and blooms all reduce clarity, and the indicator shows where and for how long."

**Researcher note**
- Morel 2007 was fitted on Case-1 waters. It diverges for Kd490 > 0.3 m⁻¹, which happens here, so Kd_PAR carries roughly ±30 % uncertainty.
- **Secchi calibration (live, rough).** The warm-season (May-Sep 2018-2022) satellite Kd_PAR at Constanța has a median of 0.28 m⁻¹. The open-water rule 1.7/Kd_PAR then gives a 6.0 m Secchi. INCDM's coastal stations measured a 4.0 m median over 2018-2023 (n = 49). A factor of **c ≈ 1.1** reproduces the observations, so the dashboard uses 1.1 and states the range 1.1-1.7. This is a one-pixel versus many-stations comparison, and satellites only see clear-sky days, so treat c as provisional.
- The L3 1 km product is cloud-gappy: 49 of the last 90 days were valid.

#### P6. Bottom-temperature anomaly (benthic thermal stress)

**Formula**
```
Tb_anom(t) = (bottomT_anfc(t) - bias) - clim_bottomT(doy)       rea_phy_temp 1993-2022, bias = +0.41 C (anfc - rea, Dec 2024-Jul 2025)
bottom MHW = Hobday rules on bottomT (p90, >= 5 days)
```

**Live result**
- The anfc model is **+0.41 °C warmer** than the reanalysis over the overlap (RMSD 0.61, r 0.96), so we correct for it.
- **Validation against NIMRD casts (live).** The reanalysis was compared with the deepest sample of 26 casts on the Constanța transect (stations CT1 and CT2, 30-40 m, 1993-1999, EMODnet Chemistry). Bottom temperature: bias +0.50 °C, RMSD 2.6 °C, r 0.89. The large RMSD comes from thermocline timing: when the model mixes a few days early or late, the bottom value jumps by several degrees. So read single-day values loosely, and weekly means with more confidence.
- The bottom anomaly was +1.3 to +4.1 °C from October to November.
- Two "bottom heatwaves" were flagged: 20-27 Oct and 13-19 Nov 2026 (moderate).
- Most of this is the autumn overturn (P4) bringing the still-warm surface water down to the seabed. Its timing varies by weeks from year to year, which is why the bottom climatology has sd up to 5 °C in September.

**Audience one-liners**
- **Public:** "The seabed water is warmer than usual this autumn."
- **Student:** "Bottom temperature follows the surface only when the water column is mixed. In summer the bottom stays cold under the thermocline."
- **Stakeholder:** "Mussel beds and benthic fish feel bottom temperature, not SST. Long warm spells at the bottom in late summer add to low-oxygen stress."

**Researcher note**
- This indicator is model-only. Interpret it only together with P4.
- The bottom-temperature series has a very wide seasonal spread. Prefer flagging "warm AND stratified" (stress) over "warm AND mixed" (overturn).

#### P7. Storm and resuspension index, plus storm surge

**Formula**
```
STORM       = Hs > p95 (1.66 m at Constanta, 2021-2026) for >= 6 h                                (proposed)
              cf. literature: wind > 12 m/s for >= 12 h and sea state 4 (Hs 1.25-2.5 m) (Chiotoroiu & Tomescu 2009) (lit)
u_b         = pi * Hs / (Tp * sinh(k h))        linear theory, k from dispersion (Fenton & McKee 1990), h = local depth
RESUSPENSION = u_b > 0.10 m/s (fine sediment), > 0.20 m/s (fine sand)                            (proposed)
SURGE       = tide-gauge level - 30-day running median > +0.30 m                                 (proposed; tide is only 7-11 cm)
```

**Live result**
- Hs off Constanța (2021-2026): median 0.58 m, p95 1.66 m, p99 2.24 m. The maximum was 4.24 m on 2023-11-19.
- 82 storm events in 5.1 years.
- Near-bed orbital velocity over the last 90 days plus forecast:

| Depth | Hours above 0.10 m/s |
|---|---|
| 10 m | 1,579 |
| 20 m | 643 |
| 26.5 m | 323 |

- The model forecasts Hs above 2 m on 27-28 Nov.
- Tide gauge IOC-csta2 over the last 30 days: range 0.37 m, largest positive residual +0.14 m. It agrees with model SSH at r = 0.89.

**Audience one-liners**
- **Public:** "A storm stirs up the seabed, so the water turns brown for a few days. That is normal, not pollution."
- **Student:** "Waves move water in circles that reach the seabed in shallow water. Above about 0.1 m/s they lift mud into the water."
- **Stakeholder:** "Ports and shipyards: plan dredging and works outside storm windows. Tourism: expect murky water after storms. Aquaculture: check moorings."

**Researcher note**
- The resuspension thresholds depend on grain size. EMODnet seabed substrate could set the threshold per pixel.
- The orbital velocity uses Hs (significant) rather than an rms value, so it is an upper-side estimate.

---

## 2. Parameter sheets

Each sheet follows the same six points:
1. Why it matters, including the five sectors.
2. Typical values and seasonal cycle.
3. Reference conditions and thresholds.
4. Natural vs real change.
5. Best data source, with a live check at Constanța.
6. Resolution needed vs offered.

Sector abbreviations: **PL** ports and logistics, **SY** shipyards and marine engineering, **TO** coastal and marine tourism, **FI** fishing, **AQ** aquaculture.

### 2.1 Sea surface temperature

**1. Why it matters**
- Temperature sets metabolism, oxygen solubility (warmer water holds less O₂), the timing of blooms and the spawning of sprat and anchovy.
- Heatwaves are a direct stressor for mussel beds (*Mytilus galloprovincialis*) and for jellyfish or invasive species outbreaks.
- Sectors:
  - **TO:** bathing season, jellyfish.
  - **FI:** sprat and anchovy distribution, timing of the turbot season.
  - **AQ:** mussel growth and mortality, farm siting.
  - **PL/SY:** cooling-water intakes and outfall plumes are thermal pressures.

**2. Typical values (live, satellite climatology 1991-2020 at Constanța)**

| Mid-Feb | Mid-May | Mid-Aug | 23 Nov |
|---|---|---|---|
| 4.4 °C (p10 2.5) | 15.2 °C | 24.8 °C (p90 26.4) | 11.6 °C |

- The SeaDataNet climatology gives about 4.4 °C in February and 26.5 °C in August at the surface (`docs/data_sources/emodnet_insitu.md`).
- Trend:
  - Constanța: **+0.53 ± 0.13 °C per decade, 1982-2025 (live)**.
  - Basin-wide: 0.65 ± 0.07 °C per decade, 1982-2020 ([Mohamed et al. 2022](https://doi.org/10.3390/rs14102383)) (lit).
  - EEA: about 0.5 °C per decade for the Black Sea, 1991-2025 ([EEA SST indicator](https://www.eea.europa.eu/en/analysis/indicators/european-sea-surface-temperature)) (lit).

**3. Reference and thresholds**
- Day-of-year climatology over 1991-2020, the WMO normal. The ready-made CMEMS anomaly product uses the same period.
- The MHW definition follows [Hobday et al. 2016](https://doi.org/10.1016/j.pocean.2015.12.014), with categories from [Hobday et al. 2018](https://doi.org/10.5670/oceanog.2018.205) (lit).
- **Baseline decision:** Hobday 2018 suggests 1983-2012. We use **1991-2020**, because it is the current WMO normal and the period of the ready-made CMEMS anomaly product, so our numbers match what users see in MyOcean. The card also shows how many of the heatwave days would remain against a detrended baseline, so the trend is not mistaken for events.
- No official MSFD threshold exists for temperature.

**4. Natural vs real**
- Always compare with the same day of year.
- Before calling a cold anomaly in Jun-Sep, check upwelling (P2).
- Before calling a warm anomaly, check a calm, sunny spell with a shallow MLD (P4).
- Separate events from the trend by reporting both the fixed-baseline and detrended heatwave counts.

**5. Best source**
- `sst_l4_rep` (0.05°, 1982 to about one month ago) for reference and trend.
- `sst_l4_nrt` (1/16°, today) for the current state.
- No-login backup: `od` `sst_coraltemp` / `sst_blended`.
- **Live:** 13.39 °C, +1.78 °C, z 1.21 on 2026-11-23.

**6. Resolution**
- **Needed:** daily, 1 km or better near the coast. Beaches and farms sit within 1-3 km of the shore.
- **Offered:** daily, 5-6 km effective, masked within 1-3 km of the coast. The 0.01° `sst_l4_nrt_hr` helps.
- **Observation vs model at the coast (live):** NIMH station 15480 reads about 11 °C, while the model and satellite read about 14 °C, a bias of +3.5 to +3.9 °C.
  - That is representativeness, not error. The platform metadata puts the station on the shoreline at Mamaia (44.22 N, 28.63 E), in very shallow water that cools fast in autumn.
  - Do not validate offshore pixels with shore stations. Use the buoys about 3-4 km out (EUXRoCB02 at 44.23 N 28.68 E, SPOT1624) instead.
- **Model and satellite vs NIMRD casts (live, 1993-1999, Constanța transect):**
  - Reanalysis surface temperature: bias +0.19 °C, RMSD 1.1 °C, r 0.99 (44 casts).
  - Reanalysis surface salinity: bias +0.28, RMSD 1.2, r 0.84 (41 casts).

### 2.2 Bottom temperature and the cold intermediate layer

**1. Why it matters**
- Benthic habitats (mussel beds, *Modiolula* and *Mytilus* banks, the remnant *Phyllophora* field) feel bottom temperature.
- The cold intermediate layer (CIL) is the winter-formed cold water mass that ventilates the sub-surface layer. Its warming reduces oxygen supply.
- Sectors:
  - **FI:** turbot, whiting and sprat sheltering in cold bottom water.
  - **AQ:** longline mussel farms reach 10-20 m.
  - **SY/PL:** cable, pipeline and anchoring works disturb benthos at the same depths.

**2. Typical values**
- At the 26.5 m Constanța cell (live, reanalysis 1993-2022): about 9-13 °C in summer under the thermocline. In September the spread is huge (p10 9.3, p90 23.1) because the overturn timing varies.
- The CIL lies at about 50-100 m, defined as T < 8 °C, or 8.35 °C in the "cold content" metric ([Stanev 2005](https://tos.org/oceanography/assets/docs/18-2_stanev.pdf); [Capet et al. 2018](https://doi.org/10.1080/1755876X.2018.1489208)) (lit).
- The CIL core warmed by about 0.7 °C over 2005-2018 according to Argo ([Stanev et al. 2019](https://doi.org/10.1029/2019JC015076); value from the AGU press release) (lit).
- The CIL touches only the outer Romanian shelf, not Constanța.

**3. Reference and thresholds**
- Reanalysis day-of-year climatology 1993-2022, with Hobday rules applied to bottomT (proposed).
- CIL threshold 8 °C (lit, convention).

**4. Natural vs real**
- Check P4 first. A warm bottom in a mixed column (autumn) is normal overturn.
- A warm bottom under strong stratification is real stress.
- Upwelling brings cold bottom water to the shore.

**5. Best source**
- `phy_temp` `bottomT` (model, today plus 10 days), with `rea_phy_temp` `bottomT` as reference.
- In situ: EUXRoOB buoys (surface only), glider 8901034 (2023-2024), EMODnet Chemistry casts.
- **Live:** 12.58 °C on 2026-11-23, anomaly +1.26 °C. Bias against the reanalysis is +0.41 °C.

**6. Resolution**
- **Needed:** weekly, habitat-scale (1-5 km).
- **Offered:** daily, 2.5 km, model only.
- Recent bottom observations near the coast are scarce in open data. The 1990s NIMRD casts validate the reanalysis: bias +0.5 °C, RMSD 2.6 °C (P6). Anything after 2021 would have to come from new sampling or loggers.

### 2.3 Marine heatwaves and cold spells

**1. Why it matters**
- Heatwaves cause mass mortality of sessile fauna, favour invasive species and jellyfish (*Mnemiopsis*, *Rhizostoma*), and intensify stratification and hypoxia.
- Cold spells in summer are mostly upwelling and mainly shock farmed mussels and tourists.
- Sectors:
  - **AQ:** mortality, spawning failure.
  - **TO:** jellyfish, algal scums.
  - **FI:** displacement of pelagic fish.

**2. Typical values**
- About 3 heatwave days per year in 1982-1991, against about 71 in 2016-2025 (live).
- Recent events: winter 2025-2026 was almost continuously in heatwave state.
- Literature: basin-wide heatwave frequency rose by 1.4 ± 0.3 events per decade, and more than two-thirds of events occurred after 2010 ([Mohamed et al. 2022](https://doi.org/10.3390/rs14102383)) (lit).

**3. Reference and thresholds**
- Hobday 2016 and 2018, as an international convention (lit).
- Using 1991-2020 is our choice (proposed). Hobday recommends a 30-year baseline.

**4. Natural vs real**
- A summer cold spell plus favourable wind plus coastal-minus-offshore SST of -2 °C or less means upwelling.
- A heatwave in winter has low ecological impact. A heatwave in July-August stacked on stratification is high impact.
- Show the season in the card.

**5. Best source and 6. Resolution**
- As in 2.1. **Live:** 86 heatwaves and 94 cold spells since 1982. None is ongoing.

### 2.4 Salinity, the Danube plume and freshening

**1. Why it matters**
- Salinity marks the Danube plume, which carries nutrients, sediment and contaminants south along the coast. Low salinity means high risk of nutrients and blooms.
- The haline layer stabilises the water column (P4), so a big plume year is a hypoxia-risk year.
- Many Ponto-Caspian and marine species have narrow salinity windows.
- Sectors:
  - **AQ:** mussel growth and pathogen risk.
  - **TO:** turbidity and algal blooms at beaches.
  - **FI:** anchovy and sprat spawning grounds in the frontal zone.
  - **PL:** Sulina and Midia channels lie in the plume.

**2. Typical values**
- Surface salinity at Constanța (live, reanalysis climatology): about 16.1 at the end of August and 17.0 at the end of November. The p10 in August is 14.3.
- The SeaDataNet climatology gives 13.8 in May (flood peak) to 16.7 in October.
- Romania's MSFD water bodies are defined by salinity ([INCDM 2024 MSFD study, pp. 14-15](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (lit, official typology):

| Water body | Extent | Salinity |
|---|---|---|
| Transitional | Danube to Portița, to 20-30 m | seasonal mean up to 8, annual up to 14.5 |
| Coastal | Portița to Vama Veche, to 20 m | 8-16 |
| Marine | 20-200 m | 16-17.5 |
| Offshore | beyond 200 m | above 17.5 |

**3. Reference and thresholds**
- Reanalysis day-of-year climatology 1993-2022.
- The MSFD water-body salinity ranges above are the official reference typology.
- The plume flag is (proposed).

**4. Natural vs real**
- Always read it next to Danube discharge with about 1 month of lag (r = -0.49, live).
- Freshening with high discharge is natural.
- Freshening without high discharge needs a look at the model, local outfalls and the coastal lakes.
- Salinification during low flow is natural. That is the current state.
- Upwelling also raises salinity.

**5. Best source**
- `phy_sal` (model, daily, plus forecast) with `rea_phy_sal` as reference.
- In situ: EUXRoCB02 (Constanța, NRT), EUXRoCB01 (Sulina), EUXRoOB buoys. Check new buoys against the model before trusting them (see 6 below).
- **Live:** 17.8 on 2026-11-23, +0.8 above climatology. The model system offset is -0.44.

**6. Resolution**
- **Needed:** daily, 1-2 km. The plume front is sharp.
- **Offered:** 2.5 km model.
- Satellite salinity (SMOS/SMAP) is too coarse at about 40 km and not used.
- Buoys are the only direct measurement, but they need QC.
- **QC example (live):**
  - The new coastal buoy EUXRoCB02, deployed September 2026, reported salinity at an almost constant 7.5-7.8 from 1 to 19 September. The model at the same spot (0.3 km away) gave 16.9-17.5, and the Danube was at about 40 % of normal flow.
  - A plume would vary from day to day and would need high river flow. A steady offset of about 9.5 points instead to a conductivity calibration problem on a newly deployed sensor.
  - The dashboard should flag a new platform whose difference from the model is large and constant as "check sensor", not as an anomaly. This is the cross-source consistency the jury asks for.

### 2.5 Stratification, mixed-layer depth, seasonal thermocline

**1. Why it matters**
- Stratification isolates the bottom water from the atmosphere. Bottom O₂ consumption then wins, and late-summer hypoxia develops on the north-western shelf, sometimes reaching the Bay of Constanța ([Capet et al. 2013](https://doi.org/10.5194/bg-10-3943-2013)) (lit).
- It is the main physical control on D5 (eutrophication) consequences.
- Sectors:
  - **AQ:** low-oxygen events at farm depth.
  - **FI:** benthic fish kills, turbot.
  - **TO:** scums under calm stratified conditions.
  - **PL/SY:** dredged-material dispersion depends on stratification.

**2. Typical values (live)**
- Δσ at Constanța: median about 0.1 kg m⁻³ in January, rising to 2.2 in May and **4.0 in July**, then back to 0.8 in October.
- About 37 % of summer stratification is haline.
- Model MLD is about 10-12 m in August and about 16 m in November. The p90 of 27 m equals full depth.
- The seasonal thermocline at the outer shelf is typically 10-30 m. We could not confirm that range in the literature we opened, so the dashboard uses the model's MLD instead of a fixed range.

**3. Reference and thresholds**
- Reanalysis 1993-2022 day-of-year climatology.
- The mixed / weak / stratified classes and the hypoxia-risk rule are (proposed).
- No official threshold exists. The MSFD handles the consequence under D5C5 (dissolved oxygen in bottom water).

**4. Natural vs real**
- Seasonal by nature.
- Anomalies come from Danube flow (haline part), heat and calm weather (thermal part), and storms or upwelling (which destroy or tilt it).
- Report the thermal and haline parts separately so the cause is visible.

**5. Best source**
- `phy_temp` and `phy_sal` at the surface and the deepest level, plus `phy_mld`, with the `rea_*` versions for reference.
- In situ: glider 8901034 profiles and EMODnet Chemistry CTD casts for validation.
- **Live:** Δσ 1.01 on 2026-11-23, against a climatology of 0.49.

**6. Resolution**
- **Needed:** daily, 2-5 km, full profile.
- **Offered:** 2.5 km, 121 levels.
- Validation is scarce: there are no routine CTD profiles in open data after 2021.

### 2.6 Upwelling along the Romanian coast

**1. Why it matters**
- Upwelling brings cold, salty, nutrient-rich water to the shore in hours. It can cause:
  - a sudden SST drop that looks like a cold anomaly;
  - nutrient pulses, followed by blooms;
  - occasionally low-oxygen water at the coast.
- It is the classic false alarm for an anomaly detector.
- Sectors:
  - **TO:** swimmers notice 10 °C drops.
  - **AQ:** thermal shock and food pulse.
  - **FI:** fish move.

**2. Typical values**
- Driven by W and SW winds in early summer, when the thermocline is shallow.
- Example: in July 2004 the temperature fell from 22.9 to 13.6 °C (a 9.3 °C drop) in 3 days.
- In the 1970s it was well developed in 7 of 10 summers ([Mihailov et al. 2012, Rom. Rep. Phys.](https://rrp.nipne.ro/2012_64_1/art21MIHAILOV.pdf)) (lit).
- 31 divergence events in 2000-2018, mostly in late spring and early summer ([Mihailov 2024, Atmosphere](https://doi.org/10.3390/atmos15080999)) (lit).
- Ours (live): 4.8 detected days per summer on average, 20 in 2023.

**3. Reference and thresholds**
- No official threshold.
- The literature uses wind indices (CUTI, BEUTI) and station SST drops. We found no published coastal-minus-offshore SST threshold for this coast.
- Our -2 °C rule plus the wind confirmation is (proposed), justified above by its 88 % wind agreement.

**4. Natural vs real**
- Upwelling is itself the natural explanation.
- Check UI over the previous 3 days, the SST gradient to offshore, and salinity (rises) and Kd490 (often clearer).
- If the SST drops without favourable wind, look for other causes (in-situ sensor, river plume).

**5. Best source**
- `sst_l4_nrt` / `sst_l4_rep` at two points, plus `od.marine_weather` wind (ERA5 archive, forecast for coming days).
- **Live:** 60 events in 2015-2025, 88 % wind-confirmed. Currently off, because it is not summer.

**6. Resolution**
- **Needed:** daily, 1 km, coast-hugging.
- **Offered:** daily, 5 km SST, masked near the shore. 1-3 day events are resolved; their spatial structure is not.
- Use `sst_l4_nrt_hr` (0.01°) for maps.

### 2.7 Currents: Rim Current, coastal jets, retention

**1. Why it matters**
- Currents set where the Danube plume, larvae, pollutants and dredge spoils go, and how long water stays in bays (retention, which feeds local eutrophication).
- Sectors:
  - **PL:** sediment in channels, oil-spill drift.
  - **SY:** construction loads.
  - **AQ:** water renewal and larval supply.
  - **TO:** bathing safety, rip currents.
  - **FI:** larval transport.

**2. Typical values**
- The Rim Current flows offshore at about 0.5 m/s, more than 1 m/s in places ([Stanev 2005](https://tos.org/oceanography/assets/docs/18-2_stanev.pdf)) (lit).
- On the Romanian shelf the flow runs north to south: about 50 cm/s at the surface and 5 cm/s near the bottom (Mihailov et al. 2013, [EGU2013-9161](https://meetingorganizer.copernicus.org/EGU2013/EGU2013-9161.pdf)) (lit).
- Coastal currents range 0.1-80 cm/s. They strengthen under northerly winds and weaken or reverse under southerly winds ([INCDM 2024, p. 111](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (lit).
- Ours (live): mean surface speed 0.16 m/s over the last 30 days. The flow went south on 58 % of days.

**3. Reference and thresholds**
- None official. A retention index could be "days with |along-shore current| < 0.05 m/s", which is (proposed) and not computed.

**4. Natural vs real**
- Current reversals follow the wind.
- Hydrographic change counts as "real" under the MSFD only when it is permanent and caused by structures (D7, see section 3).

**5. Best source**
- `phy_cur` (model, 2.5 km), `rea_phy_cur`.
- Buoys EUXRoCB01-03 (currents, NRT) for validation; no HF radar.
- **Live:** computed.

**6. Resolution**
- **Needed:** about 1 km near harbours.
- **Offered:** 2.5 km. It cannot resolve port-scale circulation (Midia, Constanța Sud), which needs a local model.

### 2.8 Sea level and storm surge

**1. Why it matters**
- Coastal flooding, erosion of beaches and dunes, and inundation of the Razim-Sinoie and Danube Delta lagoons.
- Surges push salt water into lakes and resuspend sediment.
- Sectors:
  - **PL/SY:** quay levels, draught.
  - **TO:** beach loss; Mamaia and Eforie have needed artificial nourishment.

**2. Typical values**
- Micro-tidal: the tide is about 7-11 cm ([Dinu et al. 2010](https://geoecomar.ro/website/publicatii/Nr.16-2010/07_dinu_fin.pdf)) (lit).
- Long-term trend at Constanța: about 1.3 mm/yr over 1933-1998, strongly modulated by Danube discharge and without land-motion correction ([Malciu & Diaconu, PSMSL/GLOSS](https://psmsl.org/train_and_info/training/gloss/gb/gb7/romania/romania.html)) (lit).
- 2011-2023 has been described as a stagnation phase within the rising trend ([INCDM 2024, pp. 115-116](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (lit).
- Surges come mainly with persistent NE winds ([Mihailov et al. 2026, EGUsphere preprint](https://doi.org/10.5194/egusphere-2026-3628)) (lit). We found no peer-reviewed surge heights for Constanța. One thesis summary mentions storm variations "up to 1.3 m", but we could not confirm it.
- Ours (live): 30-day range 0.37 m. Model SSH agrees with the gauge at r = 0.89.

**3. Reference and thresholds**
- The SURGE flag (+0.30 m above the 30-day median) is (proposed). It is about three times the tidal range, and it would be replaced by an official alert level if one exists.

**4. Natural vs real**
- Surges are weather. Set-up also follows Danube flow.
- A trend needs more than 30 years and a vertical land-motion correction (GNSS).

**5. Best source**
- Tide gauges `IOC-csta2` / `IOC-csta3` (emodnet `fetch_platform` or copernicus `insitu_bs`, 5 min, NRT).
- `phy_ssh` (detided variant exists) for forecasts.
- **Live:** computed. The gauge datum is local (-7.4 m offset), so only relative values are meaningful.

**6. Resolution**
- **Needed:** hourly, at each port and beach.
- **Offered:** two gauges plus a 2.5 km model. That is enough at Constanța; Mamaia and Eforie depend on the model.

### 2.9 Waves and storms (sediment resuspension)

**1. Why it matters**
- Storms resuspend fine sediment, which reduces light (P5) and moves contaminants out of the seabed.
- They erode beaches, damage mussel farms and break up stratification (which helps oxygen).
- Sectors:
  - **PL:** port downtime.
  - **SY:** works windows.
  - **TO:** beach erosion, murky water.
  - **AQ:** longline damage.
  - **FI:** days at sea.

**2. Typical values**
- At Constanța (1971-2010): mean Hs about 0.5 m, calm conditions about 60 % of the time, and a 6 m maximum in 40 years ([Mihailov et al. 2013](https://meetingorganizer.copernicus.org/EGU2013/EGU2013-9161.pdf)) (lit).
- Large waves come from the NE, and more than 90 % of waves come from the NE-SE sectors ([INCDM 2024, p. 117](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (lit).
- Storms peak in November-March: 316 storms in 1974-2005 ([Chiotoroiu & Tomescu 2009](https://www.essl.org/ECSS/2009/preprints/P03-23-chiotoroiu.pdf)) (lit).
- Ours (live): median 0.58 m, p95 1.66 m, maximum 4.24 m (2023-11-19).

**3. Reference and thresholds**
- Literature storm definition: wind > 12 m/s for 12 h or more and sea state 4, i.e. Hs 1.25-2.5 m (lit).
- Our p95 storm rule and the u_b resuspension rule are (proposed).
- We found no published resuspension threshold for this coast.

**4. Natural vs real**
- A turbidity, Kd490 or SPM spike within 1-3 days after a storm is natural. Check P7 before flagging water clarity.

**5. Best source**
- `wav` (CMEMS, hourly, 2.5 km, since 2024-08).
- `od.marine_weather` waves (since 2021-10) for percentiles.
- SPOT1624 / WAVEB04 / EUXRoCB0xAWAC buoys for validation.
- **Live:** computed. Hs above 2 m is forecast for 27-28 Nov.

**6. Resolution**
- **Needed:** hourly, about 1 km near beaches.
- **Offered:** hourly, 2.5 km.
- The wave climatology is short (5 years). The CMEMS wave reanalysis (BLKSEA_MULTIYEAR_WAV_007_006) would give 1950s onward but is **not wrapped yet**.

### 2.10 Water transparency (Secchi depth, Kd490)

**1. Why it matters**
- Transparency is the integrating signal of phytoplankton plus sediment plus CDOM.
- It sets light for benthic primary producers.
- It is an official MSFD criterion: D5C4, photic limit, in [Decision (EU) 2017/848](https://www.legislation.gov.uk/eudn/2017/848/annex) (official).
- Sectors:
  - **TO:** bathing-water aesthetics.
  - **AQ:** food signal.
  - **PL/SY:** dredging plumes are the visible pressure.

**2. Typical values (Romanian Secchi 2018-2023, [INCDM 2024, p. 149](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (lit)**

| Water body | Mean Secchi |
|---|---|
| Transitional | 2.0 m |
| Coastal | 4.6 m |
| Shelf | 8.1 m |
| Offshore | 14.0 m |

- Only offshore waters reached GES.
- Satellite Kd490 at Constanța (live, 1998-2022 geometric means):

| Mid-Jan | Mid-Apr | Mid-Jul | Mid-Oct |
|---|---|---|---|
| 0.30 m⁻¹ | 0.38 m⁻¹ | 0.27 m⁻¹ | 0.37 m⁻¹ |

  The p90 in April is 1.2 m⁻¹: the spring flood and bloom.

**3. Reference and thresholds**
- **Official GES (Romania, D5C4):** warm-season (May-Sep) 10th percentile of Secchi of at least 5.6 m in coastal waters and 2.3 m in transitional waters.
- **National bathing-water limit:** 2 m (Ord. 161/2006) ([INCDM 2024, p. 125](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (official).
- **Anomaly:** log-space day-of-year climatology (proposed).

**4. Natural vs real**
- Low transparency after a storm (P7), during a Danube flood (P3), or during the spring bloom season is natural.
- Persistent low transparency (7 days or more) without those drivers, or a downward trend in the May-Sep p10, is the real eutrophication or pressure signal.

**5. Best source**
- `sat_kd490_my` / `sat_kd490_nrt`, 1 km.
- No-login backups: `od` `kd490_dineof` (gap-filled), `kd490_occi_8day` (since 1997).
- **Live:** Kd490 of 0.18-0.48, implying a Secchi depth of about 2.2-4.6 m (factor 1.1). Clearer than usual.

**6. Resolution**
- **Needed:** daily, 300 m to 1 km.
- **Offered:** 1 km L3 (cloud gaps, 49/90 valid days) or gap-free L4.
- Case-2 waters bias the algorithms. We calibrated Kd490 to Secchi roughly against INCDM's published coastal statistics (factor 1.1, see P5). A station-by-station match-up would tighten it.

### 2.11 Turbidity and suspended particulate matter (SPM)

**1. Why it matters**
- Sediment reduces light, clogs filter feeders, smothers benthos and carries contaminants.
- It is the main visible signature of dredging, port works, coastal-defence works and beach nourishment.
- It is the cleanest physical "pressure" signal for **PL** and **SY**.

**2. Typical values (live)**
- DINEOF SPM at the 0.8 km pixel: about 1 g m⁻³ in autumn 2026, although the nearshore box mean was about 20.
- High-resolution L3: turbidity 1.9-4.0 FNU and SPM 1.1-2.3 g m⁻³ (5 usable days in 60).
- Buoy EUXRoCB02: 29 NTU in early September. Treat it with caution, because the same new buoy's salinity looks miscalibrated in that period (see 2.4).
- We did not find a long published turbidity series for the Romanian coast. The satellite products are the reference for now.

**3. Reference and thresholds**
- None official for the open coast.
- The WFD and the bathing directive only reference transparency.
- Proposed: anomaly against a satellite climatology, flagged when persistent.

**4. Natural vs real**
- Storm (P7), Danube (P3) and spring bloom first.
- A turbidity hotspot that stays fixed at a works site regardless of weather is a pressure signal.

**5. Best source**
- `sat_hr_l3` / `sat_hr_l4_month` (about 100 m; best for port and dredging plumes).
- `od` `spm_dineof`.
- Buoys `TUR4`.

**6. Resolution**
- **Needed:** about 100 m, daily, during works.
- **Offered:** 100 m but gappy (clouds). A monthly L4 mosaic is the reliable layer.

### 2.12 Danube discharge (main driver)

**1. Why it matters**
- The Danube supplies freshwater, nutrients, sediment and contaminants. It controls salinity, stratification, turbidity and blooms on the whole Romanian shelf.
- It is the single most important "natural variability" covariate.
- It is also partly a pressure (agricultural N and P), so it sits between natural and anthropogenic.
- Sectors: all of them, especially **AQ** and **TO**, through blooms and turbidity.

**2. Typical values**
- Mean discharge about 6,365 m³/s, or about 204 km³/yr. That is about 70 % of all river input to the Black Sea ([Kara et al. 2008](https://doi.org/10.1016/j.jmarsys.2007.11.010)) (lit).
- GloFAS 1997-2025 mean: **6,611 m³/s (live)**.
- Annual means range from 4,838 (2003) to 9,042 (2010).
- 2026 is a low year at 4,348.
- The seasonal peak comes in April-May.

**3. Reference and thresholds**
- Day-of-year climatology 1997-2025 (proposed). The LOW-FLOW and PLUME rules are in P3.

**4. Natural vs real**
- This is the driver itself. Its own anomalies are climatic (drought or flood).

**5. Best source**
- `od.danube_discharge()` (GloFAS v4 via Open-Meteo, 1997 to today plus a 30-day forecast).
- **Live:** 4,216 m³/s on 2026-11-23, ratio 0.79. Rising, forecast near normal by 30 Nov.

**6. Resolution**
- **Needed:** daily.
- **Offered:** daily.
- GloFAS is a model. Its 1997-2025 mean (6,611 m³/s) is within 4 % of the published mean (6,365 m³/s, Kara et al. 2008), which is good enough for anomalies. An official gauge (Isaccea or Ceatal Izmail, INHGA) would be better for single events.

### 2.13 Light at the seabed (seagrass and macroalgae)

**1. Why it matters**
- Light at the seabed decides whether seagrass, perennial brown algae, red algae and microphytobenthos can grow. These habitats are nurseries, oxygen sources and biodiversity hotspots.
- The Mangalia eelgrass bed raises biodiversity even in the bare sediment around it ([Surugiu et al. 2021](https://doi.org/10.3389/fmars.2021.745137)) (lit).
- Habitat depth limits respond to eutrophication. On the Romanian coast they shrank sharply after the 1970s:
  - The *Zostera* beds disappeared in the 1980s (Surugiu et al. 2021).
  - Red-algae richness fell from 41 species in 1977 to 10 in 1995-2002 ([Sava et al. 2011](https://botanicaserbica.bio.bg.ac.rs/arhiva/pdf/2011_35_1_528_full.pdf)) (lit).
  - The north-western shelf *Phyllophora* field (about 11,000 km², 20-60 m, up to 70 m) collapsed through bloom shading and hypoxia ([Revkov et al. 2018](https://doi.org/10.24189/ncr.2018.045); [Stevens et al. 2019](https://doi.org/10.3389/fmars.2019.00474)) (lit).
- Sectors:
  - **TO:** clear water, reefs, snorkelling at 2 Mai - Vama Veche.
  - **FI:** nursery habitat.
  - **AQ:** a site-selection constraint, since farm shading and biodeposits harm meadows.
  - **SY/PL:** dredging plumes and new breakwaters shade or bury habitats. This is where light links to D7C2.

**2. Typical values: where the habitats are now (lit)**

| Habitat | Where | Depth now | History |
|---|---|---|---|
| *Zostera noltei* (dwarf eelgrass) | Only in the south, at Mangalia. Seven meadow sites mapped by drone in 2023 ([Marin et al. 2024](https://doi.org/10.3390/jmse12122346)). Also a mixed meadow with *Zannichellia* at Năvodari. | 0.8-3.3 m; 2-4 m at Năvodari | The Mangalia bed grew from about 940 m² in 2010 to 1,132 m² in 2020 (Surugiu et al. 2021), which is recent re-establishment. In the 1970s-80s meadows existed at Midia, Eforie, Tuzla, Costinești and Mangalia (Marin et al. 2024; snippet only, UNVERIFIED). Transplanting from Mangalia started in 2023. |
| *Zostera marina* (eelgrass) | First genetically confirmed Romanian record, in a shallow bay north of Constanța: 16 patches, 41 m² in March 2026 ([Teacă et al. 2026](https://doi.org/10.1016/j.gecco.2026.e04378)) | 1.6-2.4 m | — |
| *Gongolaria barbata* (formerly *Cystoseira barbata*), the habitat-forming brown alga on infralittoral rock | 5 of 13 historical areas remain, mainly Jupiter to Vama Veche, plus Constanța | 1-5 m (1-3 m at Vama Veche, 0.5-2 m in sheltered Mangalia) | 0-6 m in the 1960s. The Bulgarian coast has it at 3-5 m and 7-10 m. The authors attribute the Romanian absence from the lower infralittoral to higher nutrients and lower transparency ([Marin & Spinu 2023](https://doi.org/10.18054/pb.v125i3-4.26815)). Biomass at some sites is back to 1962-1971 levels. |
| *Coccotylus brodiei* (red alga, Red List) | Only off Constanța | 6-8 m | INCDM 2024, p. 309 |
| Macrophyte communities in general | Midia to Vama Veche | Stable stands only to about 10 m, single plants deeper | Opportunistic *Ulva-Cladophora-Ceramium* dominated in 2018-2023 (INCDM 2024, pp. 131, 153) |
| *Phyllophora* field | North-western shelf, mostly outside Romanian waters. A 1971 Romanian-shelf estimate exists (Vasiliu & Bodeanu 1972), seen as a snippet only, UNVERIFIED. | Historically 20-60 m | Partial re-establishment below 35 m in 2008-2010 (Stevens et al. 2019) |

**Habitat light depths (live, 1998-2022 satellite climatology)**

| Place | Seagrass (11 %) | Leathery brown algae (0.5 %) | Foliose red algae (0.1 %) |
|---|---|---|---|
| Constanța, annual median | 6.2 m | 15.0 m | 19.5 m |
| Constanța, May-Sep | 6.5 m | 15.6 m | 20.3 m |
| Vama Veche, annual median | 6.5 m | 15.5 m | 20.3 m |
| Vama Veche, May-Sep | 7.4 m | 17.7 m | 23.0 m |

**3. Reference and thresholds**
- **Light requirements (lit):**
  - Seagrass: 11 % of surface light on average ([Duarte 1991](https://doi.org/10.1016/0304-3770(91)90081-F)). *Z. noltei* needs about twice the light of *Z. marina*: compensation irradiance 44 vs 22 µmol m⁻² s⁻¹ ([Krause-Jensen & Carstensen 2018, DCE note](https://dce.au.dk/fileadmin/dce.au.dk/Udgivelser/Notater_2018/Light_requirements_of_marine_rooted_macrophytes.pdf), after Lee et al. 2007).
  - Leathery macroalgae such as *Cystoseira*/*Gongolaria*: about 0.5 %.
  - Foliose red algae such as *Phyllophora*: about 0.1 %.
  - Encrusting algae: about 0.01 % ([Markager & Sand-Jensen 1992](https://doi.org/10.3354/meps088083)).
- **Romanian and Bulgarian macrophyte thresholds** ([INCDM 2024](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf), pp. 138-139 and Annex 3 p. 370) (official; the depth targets are marked "to be validated"):
  - Ecological Index EI ≥ 6.
  - Opportunistic species < 40 % of biomass (D5C6).
  - Sensitive species ≥ 60 % of biomass and ≥ 35 % cover.
  - **Maximum depth of *Gongolaria barbata* ≥ 10 m, of *Ericaria crinita* ≥ 4 m, and of *Phyllophora crispa* / shade algae ≥ 17 m** (D5C7).
  - ZoNI > 0.55 for *Z. noltei* meadows. Mangalia stations scored 0.55-0.74 in 2020-2023 (INCDM 2024, pp. 306, 311).
- In the MSFD, light enters through D5C4 (photic limit) and D5C7 (depth distribution of macrophytes), and through the D6 benthic-habitat criteria.

**4. Natural vs real (and what the gap tells us)**

Light from the satellite should allow brown algae to 15-18 m. They are observed only to about 5 m, against a target of at least 10 m. Seagrass should reach about 6-7 m but is observed only to 3.3 m. Three causes, which the dashboard should not merge into one:

1. **The satellite overestimates clarity near the coast.**
   - It only sees cloud-free days.
   - Morel's open-water relation is applied in turbid water.
   - Our Secchi calibration suggests real attenuation is about 1.5 times higher (factor 1.7/1.1).
   - With Kd_PAR × 1.55, the depths become about 4 m for seagrass, about 10 m for brown algae and about 13 m for red algae. These are close to the observed and target limits.
   - So the "calibrated" column is the one to show. The uncorrected value is the optimistic bound.
2. **Light is not the only limit.**
   - Hard substrate on the Romanian coast is mostly shallow.
   - Sedimentation, grazing, the 1972 sea-ice event and competition from opportunistic algae all act.
   - Bulgaria's deeper *Gongolaria* (7-10 m) is consistent with clearer water there.
3. **Short-term darkening is natural.** Storms (P7), Danube floods (P3) and blooms reduce light for days. Perennial vegetation integrates light over weeks to a season, so use 30-day and May-Sep means, never single days.

**5. Best source**
- `sat_kd490_my` / `sat_kd490_nrt` (or `od` `kd490_dineof`), with EMODnet bathymetry for a map of % light at the seabed (`emodnet_layers`, owned by another session).
- **Live:** point values at Constanța and Vama Veche are computed. **Not yet as a map.**
- Validation targets: the mapped *Z. noltei* sites at Mangalia (Marin et al. 2024) and the *Gongolaria* stations Jupiter to Vama Veche (INCDM 2024).

**6. Resolution**
- **Needed:** 100 m to 1 km, monthly to seasonal.
- **Offered:** 1 km Kd490 plus about 115 m EMODnet DTM. The 100 m high-resolution turbidity product (`sat_hr_l4_month`) is the better input near meadows.
- The meadows themselves are 0.1-1 ha patches, far below satellite optical resolution. The indicator is "is there enough light for the habitat in this zone", not a habitat map.
- Uncertainty: about ±30 % in Kd_PAR, which means ±1-2 m in the seagrass depth and ±3-5 m for algae.

---

## 3. MSFD Descriptor 7 (hydrographical conditions) and where our indicators fit

D7 has two criteria, both secondary, in [Decision (EU) 2017/848 Annex I](https://www.legislation.gov.uk/eudn/2017/848/annex) (official):

| Criterion | What it covers | Unit |
|---|---|---|
| D7C1 | Spatial extent and distribution of permanent alteration of hydrographical conditions (waves, currents, salinity, temperature) to the seabed and water column, mainly linked to physical loss of seabed | km² |
| D7C2 | Spatial extent of each benthic habitat type adversely affected by that alteration | km², or % of the habitat |

- Romania did not report D7 under Art. 8 in 2018.
- In the 2024 Art. 17 study, D7 GES thresholds are "not set" (nedeterminate).
- The permanently altered area is estimated at about **96.8 km², or 2.2 % of Romanian coastal waters**. Breakdown: Sulina jetties 30, Constanța port 26.1, WWTP outfalls 17, new breakwaters 14, Midia 6, new beaches 2.5, Mangalia 1.1 km².
- That assessment uses **the same CMEMS reanalysis we use** (BLKSEA_MULTIYEAR_PHY_007_004, 1993-2023), plus INCDM in-situ T, S, sea level and waves ([INCDM 2024, pp. 109-117](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)) (official).

**What this means for us:**
- D7 is about **permanent, structure-induced** change, not about weather or climate anomalies. Our seven indicators describe the **state** and its **natural drivers**. They are the context needed to judge D5 (eutrophication: P4, P5), D1/D6 (habitats: P5, P6, light) and climate pressure (P1).
- For a D7 view in the dashboard, overlay the pressure-zones layer (ports, breakwaters, outfalls, beach nourishment) with persistent multi-year anomalies of currents, salinity, turbidity or wave height inside versus outside those zones. That is a natural "next step" card.

---

## 4. Natural variability vs real change: check before you flag

The rules below are (proposed) but follow the literature mechanisms cited above.

| Anomaly seen | Check first | If yes, label as |
|---|---|---|
| Cold SST in Jun-Sep | P2 upwelling: dT_up ≤ -2 °C and UI > 0 over the 3 previous days | natural: upwelling |
| Warm SST | Season (winter heatwaves have low impact); P4 shallow MLD and calm weather | natural, or climate pressure if persistent (heatwave) |
| Warm bottom water | P4: is the column mixed (Δσ < 0.5)? | natural: autumn overturn |
| Low salinity | P3: Danube Q_ratio > 1.2 over the last 30 days | natural: plume |
| High salinity | Low Danube flow, upwelling | natural: low flow or upwelling |
| Low transparency / high SPM | P7 storm in the last 3 days; P3 flood; April-May bloom season | natural: resuspension, plume or bloom |
| Strong stratification | High Danube flow (haline part) or a heatwave (thermal part) | driver identified, but still a hypoxia risk: investigate O₂ |
| Anomaly persists 5+ days, has no driver, and sits inside a pressure zone | — | possible pressure signal: recommend sampling |

**Model and observation consistency** feeds the confidence level of each card:
- Physics: anfc against reanalysis, +0.41 °C for bottom temperature and -0.44 for salinity.
- SST: NRT against REP, +0.53 °C.
- Station 15480 is 3.5 °C colder than the model, because it is a shore station.
- The sea-level gauge agrees with the model at r = 0.89.
- Reanalysis against NIMRD casts, 1993-1999:
  - surface temperature: +0.19 °C, r 0.99;
  - bottom temperature: +0.50 °C, RMSD 2.6 °C;
  - surface salinity: +0.28, r 0.84.

---

## 5. Thresholds: official vs proposed

| Threshold | Value | Status | Source |
|---|---|---|---|
| Marine heatwave and cold spell | > p90 (< p10), ≥ 5 days, gaps ≤ 2 days merged | International convention | Hobday et al. 2016 |
| Heatwave categories | 1-2-3-4 × (p90 - clim) | International convention | Hobday et al. 2018 |
| SST baseline | 1991-2020 | Our choice (matches CMEMS anomaly) | — |
| D7C1, D7C2 | km² permanently altered; thresholds not set in Romania | Official | Dec. 2017/848; INCDM 2024 |
| Secchi GES (D5C4) | May-Sep p10 ≥ 5.6 m coastal, ≥ 2.3 m transitional | Official (Romania) | INCDM 2024 |
| Bathing-water transparency | ≥ 2 m | Official (Romania) | Ord. 161/2006 |
| Salinity typology of water bodies | < 8 / 8-16 / 16-17.5 / > 17.5 | Official (Romania) | INCDM 2024 |
| CIL | T < 8 °C (or 8.35 °C) | Literature convention | Stanev 2005; Capet 2018 |
| Seagrass light | ≥ 11 % of surface PAR | Literature | Duarte 1991 |
| Macroalgae light | about 0.5 % (leathery brown), 0.1 % (foliose red) of surface light | Literature | Markager & Sand-Jensen 1992 |
| Macrophyte depth (D5C7) | *Gongolaria barbata* ≥ 10 m, *Ericaria crinita* ≥ 4 m, *Phyllophora* / shade algae ≥ 17 m | Official, provisional (RO-BG, "to be validated") | INCDM 2024 Annex 3 |
| Macrophyte indices | EI ≥ 6; opportunistic < 40 % of biomass (D5C6); ZoNI > 0.55 | Official (Romania) | INCDM 2024 |
| Secchi from Kd_PAR | Secchi ≈ 1.1 / Kd_PAR | **Proposed** (tuned to INCDM Secchi) | this file |
| Storm (literature) | Wind > 12 m/s ≥ 12 h and Hs 1.25-2.5 m | Literature (Romania) | Chiotoroiu & Tomescu 2009 |
| Upwelling | Jun-Sep, coastal minus offshore SST ≤ -2 °C, plus UI > 0 over 3 days | **Proposed** | this file |
| Stratification classes and hypoxia risk | 0.5 / 2 kg m⁻³; > p90 for ≥ 10 days in Jun-Sep | **Proposed** | this file |
| Plume and low flow | Q_ratio > 1.2 with SSS < p10; Q_ratio < 0.6 | **Proposed** | this file |
| Storm (dashboard) | Hs > p95 (1.66 m) ≥ 6 h | **Proposed** | this file |
| Resuspension | u_b > 0.10 / 0.20 m/s | **Proposed** | this file |
| Surge | > +0.30 m above the 30-day median | **Proposed** | this file |
| Card status | normal / watch (1-4 days beyond p10-p90) / alert (≥ 5 days) | **Proposed** | this file |

---

## 6. Resolution needed vs offered

| Parameter | Needed | Offered (best) | Main limitation |
|---|---|---|---|
| SST | daily, ≤ 1 km | daily, 0.05° REP / 0.01° NRT-HR | masked 1-3 km from the shore; REP lags about 1 month |
| Bottom T, stratification, MLD | daily, 2-5 km, profile | daily, 2.5 km model, 121 levels | model only; two systems with offsets (2024-12 switch) |
| Salinity / plume | daily, 1 km | 2.5 km model; 3 buoys | sharp front under-resolved; no satellite SSS |
| Upwelling | daily, 1 km | 5 km SST + 0.25° ERA5 wind | event timing resolved, structure not |
| Currents | hourly, 1 km at ports | daily, 2.5 km | no port-scale circulation; no HF radar |
| Sea level | hourly, every port | 2 gauges (5 min) + 2.5 km model | local datum; no GNSS land-motion correction |
| Waves | hourly, 1 km | hourly, 2.5 km; buoys | wave record only 2021 onward (reanalysis not wrapped) |
| Kd490 / Secchi / light | daily, 300 m-1 km | 1 km L3/L4; HR 100 m (gappy) | clouds; Case-2 algorithm bias; Morel ±30 % |
| SPM / turbidity | daily, 100 m | 100 m L3 (about 5 days in 60), monthly L4 | gaps; no long climatology |
| Danube | daily | daily GloFAS + forecast | model, not the gauge |

---

## 7. Open points

### 7.1 Answered from our own data and the literature

| Question | Answer | Where |
|---|---|---|
| Is the Kd490-to-Secchi rule right for this coast? | Not the open-water factor 1.7. A factor of about 1.1 reproduces INCDM's coastal Secchi median of 4.0 m. | P5 |
| Does the model's temperature and salinity match real measurements? | Yes. Against NIMRD casts on the Constanța transect (1993-1999), the reanalysis is +0.19 °C at the surface (r 0.99), +0.50 °C at the bottom (RMSD 2.6 °C) and +0.28 in salinity. | 2.1, P6 |
| Why is coastal station 15480 so cold? | It is a shore station at Mamaia (44.22 N, 28.63 E). Do not use it to validate offshore pixels. | 2.1 |
| Which heatwave baseline? | 1991-2020, to match CMEMS. The card also shows the detrended count. | 2.1 |
| Is our upwelling rule credible? | 88 % of the events it detects follow upwelling-favourable wind. This matches the S/SW-wind mechanism in Mihailov et al. (2012, 2024). | P2 |
| How deep do seagrass and macroalgae grow now, and what is the target? | Literature, and the RO-BG depth targets of ≥ 10 m for *Gongolaria* and ≥ 17 m for *Phyllophora*. | 2.13 |
| Is GloFAS realistic for the Danube? | Its 1997-2025 mean of 6,611 m³/s is within 4 % of the published 6,365 m³/s (Kara et al. 2008). | 2.12 |

### 7.2 Still open (general questions for NIMRD, short)

1. Which bottom-oxygen level do you treat as hypoxia on the Romanian shelf? (We currently propose stratification > p90 for 10 days or more as the physical early warning.)
2. Are our proposed thresholds (upwelling -2 °C, storm Hs > p95, resuspension 0.1-0.2 m/s near-bed velocity, surge +0.3 m) reasonable for this coast, or do you use others?
3. Do you have recent (post-2021) water-column or bottom measurements we could use to check the model, even only as yearly summaries?
4. Would a "light reaching the seabed vs habitat target depth" card be useful for reporting under D5C7 and D6?
5. Would a D7 card comparing long-term conditions inside vs outside port, breakwater and outfall zones help the next D7 assessment?

Literature gaps we could not close today:
- A citable critical shear or orbital velocity for the local sediments.
- A light requirement specific to Black Sea *Gongolaria* or *Phyllophora*.

---

## 8. References (opened and checked on 2026-11-23 unless noted)

**EU law and Romanian MSFD reporting**
- Commission Decision (EU) 2017/848, Annex Part I (D5, D7 criteria). https://eur-lex.europa.eu/eli/dec/2017/848/oj (text read at https://www.legislation.gov.uk/eudn/2017/848/annex)
- INCDM "Grigore Antipa" (2024). *Studiu pentru elaborarea raportului national privind starea ecologica a ecosistemului marin Marea Neagra conform art. 17 DCSMM.* Ministry of Environment. https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf

**Marine heatwaves and warming**
- Hobday, A.J. et al. (2016). A hierarchical approach to defining marine heatwaves. *Progress in Oceanography* 141, 227-238. https://doi.org/10.1016/j.pocean.2015.12.014
- Hobday, A.J. et al. (2018). Categorizing and naming marine heatwaves. *Oceanography* 31(2), 162-173. https://doi.org/10.5670/oceanog.2018.205
- Mohamed, B., Ibrahim, O., Nagy, H. (2022). Sea surface temperature variability and marine heatwaves in the Black Sea. *Remote Sensing* 14, 2383. https://doi.org/10.3390/rs14102383
- EEA (2026). European sea surface temperature (indicator). https://www.eea.europa.eu/en/analysis/indicators/european-sea-surface-temperature

**Upwelling**
- Mihailov, M.E., Tomescu-Chivu, M.I., Dima, V. (2012). Black Sea water dynamics on the Romanian littoral: case study, the upwelling phenomena. *Romanian Reports in Physics* 64(1), 232-245. https://rrp.nipne.ro/2012_64_1/art21MIHAILOV.pdf
- Mihailov, M.E. (2024). The Black Sea upwelling system: analysis on the western shallow waters. *Atmosphere* 15(8), 999. https://doi.org/10.3390/atmos15080999

**Hydrography, circulation and hypoxia**
- Kara, A.B., Wallcraft, A.J., Hurlburt, H.E., Stanev, E.V. (2008). *J. Marine Systems* 74, 74-95. https://doi.org/10.1016/j.jmarsys.2007.11.010
- Stanev, E.V. (2005). Understanding Black Sea dynamics: an overview of recent numerical modeling. *Oceanography* 18(2), 56-75. https://tos.org/oceanography/assets/docs/18-2_stanev.pdf
- Stanev, E.V., Peneva, E., Chtirkova, B. (2019). *J. Geophys. Res. Oceans.* https://doi.org/10.1029/2019JC015076 (value taken from the AGU press release)
- Capet, A., Vandenbulcke, L., Grégoire, M. (2018). Decline of the Black Sea oxygen inventory. CMEMS Ocean State Report 2, *J. Operational Oceanography* 11 sup1. https://doi.org/10.1080/1755876X.2018.1489208
- Capet, A., Beckers, J.-M., Grégoire, M. (2013). Drivers, mechanisms and long-term variability of seasonal hypoxia on the Black Sea northwestern shelf. *Biogeosciences* 10, 3943-3962. https://doi.org/10.5194/bg-10-3943-2013
- Mihailov, M.E. et al. (2013). EGU2013-9161 (Romanian shelf currents and waves). https://meetingorganizer.copernicus.org/EGU2013/EGU2013-9161.pdf

**Sea level and storms**
- Dinu, I. et al. (2010). Preliminary simulations of coastal currents. *Geo-Eco-Marina* 16. https://geoecomar.ro/website/publicatii/Nr.16-2010/07_dinu_fin.pdf
- Malciu, V., Diaconu, V. Long term trend of the sea level at the Romanian littoral. PSMSL/GLOSS training. https://psmsl.org/train_and_info/training/gloss/gb/gb7/romania/romania.html
- Mihailov, M.E., Spinu, A. et al. (2026). EGUsphere preprint. https://doi.org/10.5194/egusphere-2026-3628
- Chiotoroiu, B., Tomescu, M. (2009). Similarities between severe storms produced along the Romanian Black Sea coast. 5th ECSS. https://www.essl.org/ECSS/2009/preprints/P03-23-chiotoroiu.pdf

**Light, transparency and habitats**
- Morel, A. et al. (2007). Examining the consistency of products derived from various ocean color sensors in open ocean (Case 1) waters. *Remote Sensing of Environment* 111, 69-88. https://doi.org/10.1016/j.rse.2007.03.012
- Duarte, C.M. (1991). Seagrass depth limits. *Aquatic Botany* 40, 363-377. https://doi.org/10.1016/0304-3770(91)90081-F (value via secondary quote)
- Stevens, T.F. et al. (2019). Partial recovery of macro-epibenthic assemblages on the north-west shelf of the Black Sea. *Frontiers in Marine Science* 6, 474. https://doi.org/10.3389/fmars.2019.00474
- Revkov, N.K. et al. (2018). *Nature Conservation Research* 3 (Zernov's Phyllophora field). https://doi.org/10.24189/ncr.2018.045
- Surugiu, V., Teacă, A., Şvedu, I., Quijón, P.A. (2021). A hotspot in the Romanian Black Sea: eelgrass beds drive local biodiversity in surrounding bare sediments. *Frontiers in Marine Science* 8. https://doi.org/10.3389/fmars.2021.745137
- Marin, O., Timofte, F., Filimon, A., Croitoru, E. et al. (2024). An integrative approach to assess and map *Zostera noltei* meadows along the Romanian Black Sea coast. *J. Mar. Sci. Eng.* 12(12), 2346. https://doi.org/10.3390/jmse12122346 (abstract only)
- Teacă, A., Menabit, S., Begun, T. (2026). First molecular confirmation of *Zostera marina* from the Romanian Black Sea coast based on ITS barcoding. *Global Ecology and Conservation*. https://doi.org/10.1016/j.gecco.2026.e04378 (abstract)
- Marin, O., Spinu, A. (2023). Long-term succession of the engineering species *Gongolaria barbata* along the Romanian Black Sea coast. *Periodicum Biologorum* 125(3-4), 155-166. https://doi.org/10.18054/pb.v125i3-4.26815
- Sava, D., Doroftei, E., Arcuş, M. (2011). Ecology and distribution of macrophytic red algae from the Romanian Black Sea coast. *Botanica Serbica* 35(1), 37-41. https://botanicaserbica.bio.bg.ac.rs/arhiva/pdf/2011_35_1_528_full.pdf
- Bologa, A.S., Sava, D. (2012). *J. Black Sea/Mediterranean Environment* 18(2), 144-154. https://dergipark.org.tr/en/download/article-file/103668
- Markager, S., Sand-Jensen, K. (1992). Light requirements and depth zonation of marine macroalgae. *Mar. Ecol. Prog. Ser.* 88, 83-92. https://doi.org/10.3354/meps088083
- Krause-Jensen, D., Carstensen, J. (2018). Light requirements of marine rooted macrophytes. DCE, Aarhus University. https://dce.au.dk/fileadmin/dce.au.dk/Udgivelser/Notater_2018/Light_requirements_of_marine_rooted_macrophytes.pdf

**Data and methods (code)**
- Data products: see `docs/data_sources/*.md` for the DOIs. Acknowledgement: "Generated using E.U. Copernicus Marine Service Information".
- Fenton, J.D., McKee, W.D. (1990). On calculating the lengths of water waves. *Coastal Engineering* 14, 499-513 (dispersion approximation used in the script). Not re-opened today.
- UNESCO (1981). EOS-80 equation of state, used for sigma-theta. Standard; not re-opened today.

**Could not be opened (do not cite without checking)**
- WISE Art. 8 and Art. 9 D7 pages for Romania.
- Black Sea Commission State of Environment reports.
- NIMRD "State of the Romanian marine and coastal environment" report.
