Hand-written reading of the validation results. compare_sources.py inserts each "## <variable>" section into
README.md under that variable; "## general" and "## limits" become their own sections. Numbers quoted here come
from metrics.csv (run of 2026-11-23); re-check them if the script is re-run on new data.

## sst
**Plain reading.** Satellite and model SST both agree with the offshore buoys to within about half a degree on a
typical day (RMSE 0.40-0.49 °C at all four buoys, 2013-2026). Both read slightly cooler than the buoys, by 0.0-0.15 °C
on average. That is small next to the 0.5 °C day-to-day scatter, and part of it is expected: the buoy measures at about
1 m, while satellite SST is a skin-to-subskin analysis averaged over a 1-5 km pixel. At the Constanta coast the scatter
is larger (RMSE about 0.9 °C, 43 bottle days 1993-2021), as expected for samples up to 30 km apart in a coastal zone.

**R² versus agreement.** R² is 0.99-1.00 everywhere, but almost all of it comes from the shared seasonal cycle
(8 °C in winter, 27 °C in summer). With each source's monthly mean removed, R² drops to about 0.9 ("R² anomalies"),
which is still high: both sources follow day-to-day and interannual changes, not only the seasons.

**Which source to trust.** Satellite SST, by a small margin: its RMSE is 0.02-0.08 °C lower than the model's at every
buoy, and it is an observation. Indicative uncertainty for a daily value at a point: about 0.45 °C (RMSE against the
buoys), with a bias under 0.15 °C. By season (median over the buoys), both read cooler than the buoys in winter
(satellite -0.2 °C, model -0.3 °C), the model also in spring (-0.25 °C), and both agree in summer
(`seasonal_metrics.md`).

**Caution.** Satellite and model agree with each other as closely as each agrees with the buoys (RMSE 0.45-0.49 °C).
The Black Sea physics system very probably assimilates satellite SST (inferred; to confirm in the product user manual),
so the two are not independent. Only the buoys are a fully independent check.

## chl
**Plain reading.** Buoy chlorophyll (fluorescence) cannot be used as an absolute reference. At OB01-03 (2024-2026) the
buoys read 2 to 3 times more than both the satellite and the model (median ratio satellite / buoy 0.36-0.51), with
autumn values up to about 100 mg/m³ that neither other source shows. At EUXRo03 (2013-2023) the buoy values sit in flat
bands that jump between levels from one period to the next, and R² with the satellite is 0.00. Likely causes (inferred):
factory calibration of the fluorometer (manufacturer calibrations often read high in the field), daytime
fluorescence quenching, and biofouling of the optical window between maintenance visits.

**Satellite versus model.** On the same buoy days they agree on average (bias 0.00-0.07 log10, i.e. within about 17 %)
and share part of the variability (R² 0.30-0.54 in log space). This shows consistency, not accuracy: no trusted
in situ chlorophyll exists offshore to arbitrate, and bottles at the coast give only 3 chlorophyll days.

**Which source to trust.** Satellite chlorophyll as the working reference, with uncertainty not quantified here
(at least a factor of about 1.6, from the 0.2 log10 spread between satellite and model; indicative). Do not use buoy
fluorescence for thresholds or trends until it is calibrated against bottle samples.

## sal
**Plain reading.** Offshore buoy salinity is not reliable in this record. It is derived from conductivity
(PSS-78 in `marinekit.datahub`) and shows drops to 13-15 PSU lasting weeks to months that end in steps, e.g. OB02 from
October 2025 to March 2026 and OB01 in spring 2025. Open-sea surface salinity near 30 °E stays around 18 PSU, and the
model shows no such events. The pattern matches conductivity-cell fouling (inferred; maintenance logs would confirm).
As a result, R² against the model is 0.00-0.17 at the buoys.

**At the coast** the model does much better against bottle samples (Constanta, 41 days 1993-2021): R² 0.55,
Spearman 0.81, bias -0.21 PSU, RMSE 1.1 PSU. It reproduces the low-salinity Danube plume episodes, but smooths them.

**Which source to trust.** The model for now, with an indicative uncertainty of about 1 PSU for a daily coastal value
(the bottle RMSE). Buoy salinity needs a fouling screen before it can serve as a reference.

## o2
**Plain reading.** After QC, the model's surface O2 differs from the buoys by about 0.9-1.2 mg/L on a typical day
(RMSE), but the sign of the bias depends on the buoy generation: the model reads higher than OB01-03 in 2024-2026
(+0.5 to +0.7 mg/L) and lower than EUXRo03 in 2013-2023 (-0.5 mg/L). Different sensors and calibrations are the likely
reason (inferred), so the true model bias is not known to better than about +/- 0.7 mg/L.

**Seasons only.** R² (0.35-0.70) comes from the seasonal cycle (high O2 in cold water). With monthly means removed,
R² is 0.00-0.10: the model does not reproduce day-to-day O2 changes at the buoys. Even after QC the summer and autumn
buoy values spread widely below the model (see figure), so some sensor drift probably remains.

**At the coast** the model is 1.5 mg/L lower than the bottles (RMSE 2.3 mg/L, 41 days). Coastal bottles often show
supersaturation during blooms, which a 2.5 km model cell smooths out (inferred).

**Which source to trust.** For surface O2 offshore, the buoys after QC are the only measurement, but their calibration
is uncertain. Use the model for the seasonal cycle and for areas without buoys, with an indicative uncertainty of about
1 mg/L offshore and 2 mg/L at the coast. This check says nothing about bottom O2 (hypoxia), where no sensor exists.

## no3
**Shape only.** Model nitrate is not usable as absolute values (repo rule), so both series are standardised. With only
35 bottle days (Constanta, 1993-1999), the model gets the broad seasonal pattern (high in late winter and spring, low
in summer: Spearman 0.41), but its maximum comes in February while the bottles peak in April, probably with the Danube
spring flood (inferred). R² 0.13. Use bottle samples and the DIVAnd climatology for nitrate levels; at most, use the
model for the timing of the winter maximum.

## po4
**Shape only.** No agreement in shape between model and bottle phosphate (Spearman 0.01, R² 0.01, 38 bottle days
1993-1999). The model shows a February maximum and a flat rest of the year; the bottles do not. Do not use model
phosphate at the coast, even for timing.

## general
- **Ranking of agreement with in situ:** SST (excellent, about 0.45 °C) >> surface O2 (seasonal cycle only, about
  1 mg/L) > salinity (coast fair, offshore buoys unusable) > chlorophyll (buoy fluorescence unusable as a reference) >
  nutrients (shape at best for nitrate, none for phosphate).
- **The in situ data need QC before they become the reference.** Pre-deployment records, fouled conductivity cells,
  drifting O2 optodes and uncalibrated fluorometers all show up. `marinekit.datahub` passes the buoy values through
  without these checks; the QC here lives only in this script (see the follow-up note below).
- **Proposed reference per variable** (for step 2; uncertainties indicative):

| Variable | Reference | Indicative uncertainty (daily, point) | Based on |
|---|---|---|---|
| SST | satellite L4 | about 0.45 °C, bias < 0.15 °C | 4 buoys, about 5400 matched days |
| Chlorophyll-a | satellite L4 | not quantified, at least a factor 1.6 | satellite vs model only |
| Surface salinity | model | about 1 PSU (coast) | 41 bottle days |
| Surface O2 | buoy after QC where available, else model | about 1 mg/L offshore, 2 mg/L coast | 4 buoys, 41 bottle days |
| Nitrate, phosphate | bottles / DIVAnd climatology | model shape only (nitrate), none (phosphate) | 35-38 bottle days |

- **Follow-up for `marinekit` (data side, not done here):** move the commissioning cut-off (OB01-03 before
  2024-04-06), the spike test and the O2 saturation screen into `datahub._platform_frame`, so the app's buoy values
  get the same QC.

## limits
- Point versus cell: a buoy measures one point at about 1 m depth; the satellite pixel (1-5 km) and the model cell
  (2.5 km) average over an area and, for satellite SST, over the skin layer. Part of every RMSE is this
  representativeness error, not a fault of either source.
- Bottle samples at the coast are within 30 km of the point and 0-5 m deep, a few per year: small n (35-43), wide
  confidence intervals, and they mix nearshore and offshore water.
- The QC thresholds (commissioning date, spike limits, the 60-150 % saturation window) are ours, inferred from the
  data; no deployment or maintenance log was available. They remove gross errors only; slow drift and fouling remain
  (salinity, O2, chlorophyll).
- Satellite and model are probably not independent for SST (assimilation), so their mutual agreement is not
  validation.
- Daily means: sub-daily effects (diurnal warming, daytime fluorescence quenching) are averaged out, and the buoys'
  native sampling interval is not exposed by `marinekit.datahub` (only daily means).
- Waves are not validated: `marinekit` has no in situ wave source (the NIMRD AWAC is not in the API), and by the agreed
  rule nothing is compared without in situ.
- Old offshore bottle samples near OB01-03 (1971-2021) were not used; they could extend the salinity and O2 checks.
