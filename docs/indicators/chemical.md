# Chemical indicators: Romanian Black Sea shelf (Challenge 04, Ecosystem Health)

Scope: the chemistry of ecosystem health off Romania (Sulina to Vama Veche, 0-50 m shelf), with Constanța
(44.17 N, 28.72 E; model cell 44.175/28.725, about 26 m deep) as the test point. Each parameter is tied to data
we can fetch through `src/marinekit/sources/`. Every number in the "live check" lines comes from
[`scripts/indicators/chemical_check.py`](../../scripts/indicators/chemical_check.py)
(output: [`chemical_check_output.txt`](../../scripts/indicators/chemical_check_output.txt), run on 2026-11-23, all
8 sections computed) or from the exploration runs logged in section 5.

Labels used throughout:
- **Origin of a value**: MEASURED (sensor or lab), DERIVED (computed from measurements, e.g. %saturation, ratios,
  gridded climatologies), MODELLED (Copernicus BAMHBI model, forecast or reanalysis).
- **Threshold status**: OFFICIAL (in a legal act or an official assessment), LIT (common literature convention),
  OURS (proposed by this team; must be presented as a proposal).

---

## 0. Summary

### Ranked shortlist for the dashboard

| # | Indicator | Formula (short) | Data key(s) | Status at Constanța | Confidence |
|---|---|---|---|---|---|
| 1 | **Bottom-oxygen status class** (+ hypoxia days, + cause test) | daily class A >= 5, B 4-5, C 2-4, D < 2 mg/L; season test = official RO D5C5 (May-Sep P10 >= 5 mg/L and >= 60 % sat); days < 2; cause test with bottom T and S (section 4) | `bgc_o2` var `o2_bottom` (live), `rea_bgc_o2` (1993-2024), `phy_temp` `bottom_temp`, `phy_sal`; EMODnet bottles (1963-2021) | COMPUTED. 2026-11-23: 3.59 mg/L, class C, caused by cold saline deep-water intrusion (natural). D5C5 2025 pass (P10 5.69 mg/L, 63 %); reanalysis fails 7 of 32 years, incl. 2024 | MEDIUM-LOW (model only at the bottom; no live bottom sensor) |
| 2 | **Surface O2 saturation** and its anomaly | %sat = O2 / O2sat(T,S) (Garcia and Gordon 1992); flags > 120 % (bloom) and < 80 % (respiration, upwelling) | buoy `EUXRoOB01-03` OSAT (MEASURED); `bgc_o2` + `phy_temp` + `phy_sal` (MODELLED) | COMPUTED. Our formula matches buoy OSAT: bias -0.2 %, r 0.98. Model last 30 days 99 % | HIGH offshore, LOW on the coastal buoy |
| 3 | **Eutrophication index** (simplified BEAST/HEAT) | ER = observed / target per criterion (O2 inverted), mean within category, one-out-all-out across nutrients / direct (chl) / indirect (O2) | `sat_chl_l4_my`, `bgc_o2`, DIVAnd `din`/`po4` | COMPUTED with OFFICIAL RO marine thresholds. Index 0.88 = GOOD, near the boundary, driven by bottom O2. The official NIMRD BEAST 2020-22 rates the 0-50 m shelf NOT GOOD | LOW-MEDIUM (model O2, gridded nutrients to 2020; mean vs official P75) |
| 4 | **Nutrient status vs reference** (DIN, PO4, Si) | value / official threshold (marine DIN 10.5, PO4 0.23 µM P75; coastal 13.5, 0.30) and value / seasonal climatology | EMODnet `fetch_chemistry_samples` (to 1999 here), `chemistry_climatology_at` (danube, blacksea) | COMPUTED for the latest trusted windows: summer 2020 DIN 9.80 (ER 0.93), PO4 0.12 (ER 0.51) µM; winter DIN 5.27 (2016), PO4 0.29 (2012), about half the 1970-2022 climatology | MEDIUM for history, NONE live |
| 5 | **Nutrient ratios N:P and Si:N** | DIN/PO4 vs Redfield 16; Si/DIN vs 1 | same as 4 | COMPUTED. Summer 2020 window: N:P 84, Si:N 0.57 (P-limited, Si-poor) | MEDIUM (historical), NONE live |
| 6 | **Bathing-water class** (EU BWD) | per site and season: official class; coast-wide share Excellent; sites downgraded vs last season | `emodnet_layers.bathing_water_history()` (per-year `status`, fixed today) | COMPUTED. 49 sites; share Excellent 31 % (2015) to 92 % (2022), 69 % (2023), 84 % (2024); matches EEA exactly | HIGH (official, lab-measured), annual |
| 7 | **pH / carbonate watch** | pH anomaly vs reanalysis day-of-year climatology; reanalysis trend | `bgc_car`, `rea_bgc_car` | COMPUTED. pH 8.20 (anomaly -0.03, z -0.26); 1993-2023 trend -0.007 per decade | LOW (model only; 4 observed pH samples here) |

Context driver (not a chemical indicator, but required to interpret all of the above): Danube discharge
(`open_data.danube_discharge`). Last 30 days 2,954 m3/s = 0.57 of the November mean.
Contaminants (MSFD D8/D9) are not on the list: there is no feed. They appear as "needs sampling" markers (section 6).

### Model vs observation verdict

- **Surface O2: usable.** The analysis/forecast (`bgc_o2`) against the offshore buoy EUXRoOB03 (2025-26, 349 days):
  bias +0.15 mg/L, RMSE 0.37, r 0.93. Against EUXRoOB02: bias +0.75, r 0.70, though part of that comes from a
  suspicious low-O2 month at the buoy (June 2025, 3.6 mg/L at the surface offshore). The reanalysis against
  EUXRo03 (2013-23, 1,842 days): bias -0.32, RMSE 1.44, r 0.65 (the buoy has sensor drop-outs).
- **Bottom O2: indicative only.** No bottom sensor exists. The reanalysis against the deepest bottle (>= 15 m,
  1993-2021, n = 40): bias -0.70 mg/L, RMSE 2.0, r 0.65. In the 2024 overlap, forecast minus reanalysis is
  **-2.04 mg/L** (RMSE 3.1, r 0.47), so the two model systems disagree by more than the class width. Against the
  official observations: in 2018-2023 (May-Sep, pooled) the reanalysis at Constanța gives mean 8.31, P10 6.77
  and min 3.86 mg/L. NIMRD measured mean 8.02, P10 5.44 and min 3.33 at its 20-50 m stations. **The mean is right,
  but the low tail is about 1.3 mg/L too optimistic**, which is exactly the tail that matters for hypoxia. Part of
  the gap is spatial (one cell vs all stations).
  Copernicus validates O2 only against deep-basin BGC-Argo floats (bias 1.6-2.3 mmol m-3, r 0.97;
  [QUID 007-010 issue 6.0](https://documentation.marine.copernicus.eu/QUID/CMEMS-BLK-QUID-007-010.pdf)). No shelf
  validation is published.
- **Nitrate: not usable as an absolute value.** The reanalysis is 8x the observations (bottle mean 3.5 vs model
  28.4 mmol m-3, n = 35, r 0.36). Against NIMRD's 2018-2023 statistics it is about 9x: reanalysis median 15.9 vs
  observed shelf median 1.72 µM (coastal median 3.67). Its 2024 annual mean then collapses to 0.23. The forecast is about 0 from May to
  September. Over the 2024 overlap, forecast minus reanalysis is +1.29 mmol m-3 (r 0.30). The QUID says
  nutrients "could not be validated in NRT due to a lack of observations". The Danube nitrate load was cut to 0.63x
  and phosphate raised to 3.46x in the V202511 release (QUID Table 8).
- **Phosphate: right order of magnitude, no skill day to day.** The reanalysis against bottles shows bias -0.18
  and r -0.09; forecast against reanalysis, r -0.09. The 2018-2023 distribution, however, is comparable (reanalysis
  median 0.04 and P75 0.32 vs observed shelf median 0.08 and P75 0.27 µM).
- **pH: plausible range, unvalidated.** The QUID says the carbonate system was only compared with climatologies.

### Open questions: mostly answered by our own research (section 8)

We could not reach NIMRD in time, so we answered the questions from public sources: the NIMRD study behind the
2024 MSFD report (downloaded and read), NIMRD bulletins, papers, news and live data. What changed:
- **Post-2000 data:** official 2018-2023 statistics now anchor every indicator.
  - Bottom O2 P10 5.44 mg/L and 54 % saturation: D5C5 fails on saturation.
  - Coastal waters fail every nutrient limit, and ammonium is about half of DIN (wastewater).
  - D8 and D9 (contaminants) are not good in every unit.
- **Thresholds:** all official numbers found. The coastal NO3 limit is 4.0 µM; P90 applies to coastal waters,
  P75 to marine waters.
- **Events:**
  - July 2010 hypoxic fish kill at Mamaia-Constanța (bottom saturation 25 %);
  - NIMRD: no anoxic fish kill since 2010;
  - surface "hypoxic regime" at Mamaia on 15 Jul 2025 (3.0 mg/L);
  - biotoxin closure of mussel harvesting in June 2024;
  - the Rapana and mussel strandings of Jan 2026 were caused by a storm, not hypoxia.
- **Model:** right on average; the low tail of bottom O2 is about 1.3 mg/L too optimistic; nutrients come from
  Danube climatology after 2010. Live surface check against buoy OB03 today: r 0.89, bias +0.45 mg/L.
- **Organism thresholds:** they support our 5 / 4 / 2 mg/L classes. Mussels survive days to weeks of anoxia, so
  we now report runs of consecutive low days.
- **Dead shells:** shell beds are time-averaged and need dating; Mn/Ca in shells is a usable O2 proxy.

Still needed from NIMRD (section 8.9): station data for 2024-25, exact farm coordinates, and the D5C5 wording.

---

## 1. Why chemistry, and how it links to the five sectors

Black Sea specifics that shape every indicator:
- **Permanently anoxic below ~100-200 m.** About 90 % of the basin volume is anoxic and holds hydrogen sulphide.
  Only a thin oxygenated surface layer supports life. On the Romanian shelf (< 50-60 m) the water column is oxic,
  but bottom water can lose O2 seasonally (hypoxia).
- **The Danube dominates.** Mean discharge is about 6,500 m3/s (our series: 6,667 m3/s, 1997-2024). It brings
  nutrients, silicate, suspended matter, CDOM and contaminants. Its plume normally turns south along the Romanian
  coast, so Constanța is a river-influenced coastal water body.
- **Brackish water.** Surface salinity is 7-18 (15-17 near Constanța). This lowers O2 solubility less than
  temperature does, but it changes the reference values: Mediterranean or Baltic thresholds cannot be copied.
- **A recovering, not pristine, system.** Strong eutrophication in the 1970s-80s was followed by partial
  recovery after the early 1990s, when the economy collapsed and fertiliser use and phosphate detergents fell.
  "Reference conditions" are therefore a choice: the 1960s, or a recent normal.

| Sector | Chemical pressure it causes | Chemical state it depends on |
|---|---|---|
| Ports and logistics (Constanța, Midia, Mangalia) | dredging (resuspension of contaminated sediment, TSM), ballast water, oil and fuel spills (TPH, PAH), antifouling (Cu, TBT) | low: port operations are not O2-sensitive, but dredging permits need sediment-contaminant data |
| Shipyards and marine engineering (Constanța, Mangalia, Midia) | metals, TBT/antifouling, hydrocarbons, paints; outfalls | corrosion and biofouling depend on O2, pH, temperature |
| Coastal and marine tourism (Mamaia to Vama Veche) | sewage overflows in summer, nutrient loads | bathing-water microbiology (BWD class), water clarity, no algal scum or jellyfish, no hypoxic odour or dead-fish events |
| Fishing (2,527 t marine catch in 2024, over 70 % Rapana venosa; 2023: Rapana 2,670 t, mussels 317 t, sprat 92 t (NIMRD 2024 study); sprat and turbot under TAC; [Eurofish 2026](https://eurofish.dk/?p=106)) | bottom dredging and trawling resuspend sediment and nutrients; fuel | bottom O2 (Rapana grounds, turbot), fish kills in hypoxia (about 2 t of fish on the Romanian coast in July 2010, linked to hypoxia after the Danube flood; [CORDIS/HYPOX](https://cordis.europa.eu/article/id/35397-why-fish-populations-are-running-out-of-oxygen)) |
| Aquaculture (small but opening up). Only one commercial mussel farm (SC Maricultura SRL) ran, until 2016, producing a few t/yr. An experimental long-line run by NIMRD and SC Maty Fish SRL now operates at the same site. In autumn 2020 ANSVSA classified all **three bivalve production and relocation zones as class A**: Chituc-Perișor, Baia Mamaia and Agigea-Mangalia. A DG SANTE audit in 2023 was positive. Allocated Zones for Aquaculture were drafted in the CreAZA project. Wild mussel catch 2018-2023: 231, 158, 117, 125, 446, 317 t (NIMRD 2024 study, chapters II.4-II.5; [Niță et al. 2019](https://animalsciencejournal.usamv.ro/pdf/2019/issue_2/Art58.pdf)) | organic enrichment under farms | **most exposed**: bottom O2, harmful-bloom risk (via N:P and Si:N), contaminant levels in mussel tissue (food safety), bathing-water-type microbiology for shellfish waters |

---

## 2. Parameters

### 2.1 Dissolved oxygen and O2 saturation (surface and bottom)

**Why it matters.** O2 is the clearest single signal of eutrophication damage. Algal blooms sink and decay, and
in a stratified summer column (warm, Danube-freshened surface over cooler saltier bottom water) respiration uses
up the bottom O2. Below about 2 mg/L most benthic animals die or flee. On the north-western shelf (NWS) in the
1970s-90s this killed mussel beds (Mytilus galloprovincialis and Modiolula phaseolina communities) and the
Phyllophora red-algae field, with fish and invertebrate kills on beaches. Sublethal effects (reduced growth,
avoidance) start well above 2 mg/L. The meta-analysis of Vaquer-Sunyer and Duarte (2008) gives a mean lethal
concentration of 2.61 mg/L and sublethal effects up to about 4.6 mg/L. Surface O2 saturation is a bloom
detector: supersaturation (> 110-120 %) means strong photosynthesis, and undersaturation (< 80-90 %) at the
surface means upwelled or deep-mixed respired water.
- Aquaculture: mussel farms and natural beds are killed directly by hypoxia. This is the main chemical risk.
- Fishing: hypoxia removes Rapana and turbot grounds and causes fish kills or displacement.
- Tourism: dead fish and mussels on the beach and H2S smell after hypoxic events.
- Ports and shipyards: an indirect link. Dredging releases organic-rich sediment that consumes O2.

**Typical values near Constanța** (MEASURED unless stated):
- Surface: winter 11-14 mg/L (cold water, high solubility), summer 8-9.5 mg/L. Bottles <= 30 km, 1960-1999:
  monthly medians from 9.0 (Aug) to 14.1 (Mar). Offshore buoy EUXRoOB03 (2025): 7.0 mg/L (Aug) to 9.9 (Mar),
  saturation 90-102 %.
- Bottom (deepest bottle >= 15 m, Jul-Oct): median 7.8 mg/L in the 1960s, 7.5 in the 1970s, **6.4 in the
  1980s**, 7.5 in the 1990s. The 10th percentile was 2.7 mg/L in the 1970s. Share of casts < 2 mg/L: 2 %, 7 %,
  4 %, 0 %. Lowest values: **0.46 mg/L (1975), 0.53 (1986), 1.56 (1966), 1.60 (1989), 1.69 (1979)**.
  There are almost no public casts after 2004 (5 in the 2000s, 2 in 2021 at 3.3-3.6 mg/L).
- DIVAnd Danube-Delta climatology (1970-2022, DERIVED) at Constanța, 20 m: winter 11.2, spring 10.6,
  **summer 6.7**, autumn 7.8 mg/L. Surface summer 10.2 mg/L.
- Reanalysis (MODELLED, 1993-2023): bottom monthly mean from 7.2 (Sep) to 10.5 (Mar), p10 in August 5.3 mg/L.
  No day < 2 mg/L in 32 years. 8 of 32 years have a Jul-Oct minimum < 4 mg/L (some of them in October, after
  stratification breaks down), e.g. 1994 2.50, 1999 2.43, 2016
  2.33. Trend: bottom +0.17 mg/L per decade, surface -0.12 per decade.

**Long-term trend (LIT).**
- **1970s-80s: hypoxia appears and spreads.** Summer bottom hypoxia was first seen in the early 1970s at 30 m
  between the Danube and Dniester mouths ([Capet et al. 2013](https://doi.org/10.5194/bg-10-3943-2013), citing
  Zaitsev). Its extent grew from about 3,500 km2 (1973) to 40,000 km2 (1990)
  ([Schrimpf et al. 2008, JRC33363](https://publications.jrc.ec.europa.eu/repository/handle/JRC33363)). A Ukrainian
  report gives a maximum of 20,000 km2 in 1983. About 60 million t of bottom fauna (including 5 million t of fish)
  were lost in 1972-1990. Mytilus galloprovincialis beds nearly disappeared in the 1980s, and dead benthos washed
  up on Romanian beaches in the late 1980s ([Mee et al. 2005](https://doi.org/10.5670/oceanog.2005.45);
  [Zaitsev 1992](https://doi.org/10.1111/j.1365-2419.1992.tb00036.x)).
- **The "recovery" after the 1990s is partial.** A 3-D model checked against 14,123 O2 observations finds
  end-of-summer bottom hypoxia in every year from 1981 to 2009. In severe years it reached the Bay of Constanța,
  between the coast and the 45 m isobath ([Capet et al. 2013](https://doi.org/10.5194/bg-10-3943-2013)). Four
  predictors explain 82 % of the year-to-year variability: river nitrate load, SST before stratification, organic
  matter stored in the sediment, and late-summer SST. The apparent post-1995 recovery was overestimated because
  sampling missed hypoxic areas and months. Recovering benthic communities take years
  ([Friedrich et al. 2014](https://doi.org/10.5194/bg-11-1215-2014)).
- **After 2010 on the Romanian coast:**
  - A 30 m mooring off Portița (2010, 2016) recorded intermittent bottom hypoxia from mid-July to mid-October
    ([EGU2019-16147](https://meetingorganizer.copernicus.org/EGU2019/EGU2019-16147.pdf)).
  - Nearly 2 t of fish died on the Romanian coast in July 2010, linked to hypoxia after the Danube flood
    ([phys.org/HYPOX](https://phys.org/news/2013-01-hypox-fish-populations-oxygen.html)).
  - NIMRD recorded three summer events below 60 % saturation at Sf. Gheorghe and Portița 30 m in 2012-2017
    ([Lazăr et al. 2019](http://www.marine-research-journal.org/index.php/cmrm/article/download/142/107)).
  - In 2018-2023, bottom water at 20-50 m (n = 145) had a minimum of 3.33 mg/L and 33.9 % saturation, with
    events below 60 % in every reporting unit (NIMRD 2024 study, Table III.7.13).

**Official measured bottom O2, May-Sep 2018-2023, 20-50 m** (NIMRD 2024 study, Table III.7.13, read from the
PDF). This is the post-2000 observational baseline we were missing.

| Unit | n O2 | mean | median | min | P10 (mg/L) | n sat | P10 saturation | D5C5 (>= 5 mg/L and >= 60 %) |
|---|---|---|---|---|---|---|---|---|
| all stations | 145 | 8.02 | 8.24 | 3.33 | 5.44 | 126 | 54.3 % | fails on saturation |
| transitional TT03 | 18 | 7.74 | 7.99 | 4.99 | 5.33 | 17 | 50.4 % | fails on saturation |
| coastal CT | 52 | 8.17 | 8.61 | 3.49 | 5.44 | 44 | 53.2 % | fails on saturation |
| shelf MT01 (<= 50 m) | 75 | 7.99 | 8.20 | 3.33 | 5.51 | 65 | 57.3 % | fails on saturation |

The study's text says the P10 of 54.3 % does "not meet the conditions of good status for saturation". The next
sentence says the status "is good". The chapter conclusions say good status is not achieved in transitional,
coastal or shelf waters. **We read D5C5 as failed, on saturation, and the "is good" sentence as an editorial
error.** Note that the mg/L test alone passes everywhere (P10 5.3-5.5): the saturation test is what fails.
Warm bottom water holds less O2, so 5 mg/L at 25 °C is only about 60 % saturation.
- **Our numbers agree.** The bottle record shows the 1980s minimum (median bottom O2 6.4 mg/L) and a 1990s
  rebound. The reanalysis has no days < 2 mg/L at Constanța itself (1993-2024), but it fails the official D5C5
  test (P10 >= 5 mg/L and >= 60 % saturation, May-Sep) in 7 of 32 years, including 2024 (P10 5.09 mg/L, 57 %).

**Thresholds.** See section 3.1. The official Romanian D5C5 is P10 >= 5 mg/L and >= 60 % saturation
(May-Sep, <= 50 m). Hypoxia is < 2 mg/L (LIT). Our daily class limits are 5 / 4 / 2 mg/L, and the surface
saturation flags are 80 % / 120 % (OURS).

**Natural vs real change.** See section 4. Three natural mechanisms create low bottom O2 near Constanța without
any change in pressure: (1) upwelling or onshore bottom flow of cold, saline, O2-poor water from the shelf break
after persistent northerly or north-westerly winds (the 19-27 Nov 2026 forecast episode is exactly this: bottom
T fell 14.4 to 10 °C, S at 24 m rose 17.5 to 19.5, O2 fell 8.1 to 2.5 mg/L, and a storm restored 9 mg/L on
28-29 Nov); (2) years with high Danube discharge, which bring stronger stratification and more nutrients
(reanalysis: r = -0.52 between Mar-Jun discharge and the Jul-Oct bottom O2 minimum, 27 years); (3) warm calm
summers, which bring longer stratification and lower solubility. **Check first:** bottom temperature and
salinity (or the stratification index from `physical.md`) and Danube discharge.

**Best source and live check.**
| Need | Key / function | Live result (2026-11-23) | Origin |
|---|---|---|---|
| Bottom O2 today plus 7-day forecast | `cm.fetch_timeseries("bgc_o2", lat, lon, ..., variables=["o2_bottom"])` | 3.59 mg/L today; forecast min 2.53 on 11-26, back to 9.1 on 11-30 | MODELLED |
| Bottom O2 reference | `cm.climatology("bgc_o2", lat, lon, variable="o2_bottom")` (uses `rea_bgc_o2` 1993-2022) | doy 327: mean 260 mmol m-3 (8.3 mg/L), p10 203 | MODELLED |
| Surface O2 and OSAT offshore | `ei.fetch_platform("EUXRoOB03", ..., ["o2","do_sat","temp","sal"])` (also OB01, OB02) | 2025-01 to 2026-09; monthly 7.0-9.9 mg/L | MEASURED |
| Surface O2 at the Constanța coast | `ei.fetch_platform("EUXRoCB02", ...)` | Sep-Nov 2026; **not trustworthy** (section 2.1 note) | MEASURED, bad QC |
| History | `ei.fetch_chemistry_samples(lat, lon, 30, max_depth=None, variables=["o2",...])` | 4,567 rows within 30 km, 1963-2021 | MEASURED |
| Seasonal reference | `ei.chemistry_climatology_at(lat, lon, "o2", "danube", depth=0 or 20)` | see above | DERIVED |

Buoy quality notes (live checks): EUXRoCB02 (coastal, Constanța, deployed 2026) reports DOXY with a median of
4.9 in a field labelled mmol m-3. The module treats it as mg/L, but at 20 °C the value fits mL/L better
(4.9 mL/L = 7.0 mg/L, about 80 % saturation). Its OSAT median is 3.6 (should be 80-110 %), salinity is a constant
7.5 (Constanța is 15-17), October DOXY is 0 with QC = 1, and CDOM and chl fluorescence correlate at r = 0.95
(cross-talk or fouling). Against the model it shows bias -2.0 mg/L and RMSE 3.3. **Use it for nothing
quantitative until GeoEcoMar confirms units and QC.** EUXRoOB02 had a month (June 2025) with surface O2 at
3.6 mg/L offshore, which is not physically plausible and suggests fouling. EUXRo02 DOXY in 2021 is all QC 9.
EUXRo03 (2013-2023) has drop-outs to 0.03 mg/L.

### 2.2 Nutrients: nitrate, nitrite, ammonium, phosphate, silicate, and the ratios N:P and Si:N

**Why it matters.** Dissolved inorganic nitrogen (DIN = NO3 + NO2 + NH4) and phosphate (PO4) fuel
phytoplankton. An excess causes the bloom, decay and hypoxia chain described in 2.1. Ammonium and nitrite are
also indicators of fresh sewage or organic decay; nitrite is toxic to fish at high levels. Silicate (Si) is
needed only by diatoms. When Si:N falls below about 1, diatoms are limited and non-siliceous groups
(dinoflagellates, coccolithophores, Emiliania huxleyi blooms, some harmful species) gain. That shift fed the
jellyfish and Mnemiopsis food web in the 1980s. N:P above 16 (Redfield) means P limitation; below 16 means N
limitation.
- Aquaculture: blooms feed mussels, but harmful algae (Prorocentrum, Pseudo-nitzschia, Dinophysis) cause shellfish
  toxin closures. Si:N and N:P are early warnings.
- Tourism: blooms bring discoloured water, foam and reduced clarity, plus beach odour.
- Fishing: very high nutrient loads give jellyfish-dominated, low-quality food webs. Moderate loads are productive.
- Ports and shipyards: urban and port wastewater outfalls (Constanța Nord and Sud WWTPs, Eforie) are point
  sources of NH4 and PO4.

**Typical values near Constanța** (mmol m-3 = µmol/L):
- Bottles within 30 km, surface medians by decade (MEASURED):

| decade | NO3 | NH4 | DIN | PO4 | Si | N:P | Si:N | n (PO4) |
|---|---|---|---|---|---|---|---|---|
| 1960s | - | - | - | 0.10 | 28.5 | - | - | 256 |
| 1970s | 9.37 | - | 11.0 | 0.73 | 38.1 | 26 | 2.5 | 739 |
| 1980s | 2.91 | 3.46 | 8.4 | 0.21 | 5.1 | 36 | 0.78 | 529 |
| 1990s | 2.90 | 2.43 | 5.5 | 0.22 | 4.6 | 26 | 0.81 | 163 |

  The last public nutrient sample within 30 km is from 1999-09-15. Seasonal cycle 1960-79: NO3 13-15 in winter,
  4-5 in Jul-Aug; Si 45-56 in winter, 22-32 in summer. In 1980-99 Si was 19 in winter and 4-5 in summer.
- DIVAnd Danube-Delta climatology (DERIVED; DIN 1980-2022, PO4/Si 1970-2022), surface: DIN winter 10.8 / spring
  12.6 / summer 7.4 / autumn 8.1; PO4 0.51 / 0.31 / 0.26 / 0.32; Si 30.0 / 11.9 / 7.1 / 11.6.
- DIVAnd Black-Sea 6-year moving windows (DERIVED; trusted cells only, relative error < 0.3): summer DIN 4.7
  (1995) to 6.5 (2005) to 9.6 (2015) to **9.8 (2020)**; summer PO4 0.26 (1995) to 0.13 (2005) to 0.11 to **0.12
  (2020)**; summer Si 4.6 to 2.7 to 3.1 to **5.6 (2020)**. Winter windows after 2012-2016 are masked (too few
  winter cruises). The latest trusted winter values are DIN 5.27 (2016), PO4 0.29 (2012) and Si 15.4 (2012).
- Reading: phosphate fell clearly after the 1980s. DIN fell in the 1990s, but summer DIN rose again in the 2010s.
  Silicate fell sharply in the 1970s-80s. The current summer stoichiometry is N:P about 80 and Si:N about 0.6:
  strongly P-limited and Si-poor.

**Long-term trend and eutrophication history (LIT).**
- **Danube loads.** Basin loads rose from about 400 to 900 kt N/yr (1950 to 1985-90) and from about 40 to 115 kt
  P/yr (1950 to the mid-1990s) (BSC 2008, as cited in the NIMRD 2024 study). Loads peaked in the late 1980s and
  have declined since ([Kovács and Závadsky 2021](https://doi.org/10.1080/02508060.2021.1891703)). The DIN load
  at Reni is now reported to be below the 1960 level
  ([Neumann et al. 2026](https://doi.org/10.5194/bg-23-1103-2026)). ICPDR load numbers could not be opened
  (NOT VERIFIED).
- **Phosphate.** Near the Danube delta PO4 rose from 1-2 µM in the 1960s to 10-20 µM in the 1970s-80s. Danube PO4
  loads fell sharply in 1992-93, and phosphate limitation followed. The post-eutrophication state "cannot be
  considered as a major improvement" ([Oguz and Velikova 2010](https://doi.org/10.3354/meps08538)).
- **Silicate.** Si fell by more than 60 % after the Iron Gates dams (1972). Si:N dropped and the plankton shifted
  from diatoms to coccolithophores and flagellates ([Humborg et al. 1997](https://doi.org/10.1038/386385a0)).
  Off Constanța, Si:N went from > 4 to 1-2 and Si from 30-60 to 5-10 µM after 1974-75
  ([Oguz 2005](https://doi.org/10.5670/oceanog.2005.46)). Our bottles agree: Si 38 (1970s) to 5 (1980s) µM.
- **Ecosystem.** The 1980s to early 1990s were the catastrophic phase, with recovery signs from the mid-1990s
  ([Kideys 2002](https://doi.org/10.1126/science.1073002)). NIMRD's 1960-2023 series shows warming, declining O2,
  a rising N:P ratio and more Noctiluca blooms ([Ristea et al. 2025](https://doi.org/10.3390/su17031090), abstract).
- **Today (official, 2018-2023).** Station statistics from the NIMRD 2024 study (Tables III.7.7 and III.7.8,
  read from the PDF), µmol/L:

| Unit (n) | statistic | PO4 | NO3 | NO2 | NH4 | DIN |
|---|---|---|---|---|---|---|
| coastal CT (104) | mean / median / **P90** | 0.70 / 0.17 / **0.91** | 8.87 / 3.67 / **22.27** | 4.05 / 0.41 / 10.79 | 7.86 / 4.23 / **13.94** | 20.78 / 11.73 / **43.43** |
| shelf MT01 (144) | mean / median / **P75** | 0.18 / 0.08 / **0.27** | 4.12 / 1.72 / 3.62 | 1.41 / 0.13 / 0.54 | 5.03 / 2.72 / 7.46 | 10.56 / 7.22 / **13.78** |
| offshore MT02 | P75 | 0.08 | | | | 2.53 |

  Coastal water fails every WFD limit: P90 PO4 0.91 vs 0.30, NO3 22.3 vs 4.0, NH4 13.9 vs 6.5, DIN 43.4 vs 13.5.
  The shelf slightly exceeds the marine limits (DIN 13.78 vs 10.5, PO4 0.27 vs 0.23). Only offshore is good.
  Ammonium is about half of DIN, which points to wastewater and organic decay rather than river nitrate. The
  study names the Constanța Sud, Eforie and Mangalia WWTPs and the Constanța and Mangalia ports. In 2019, 93 % of
  the wastewater discharged to the sea was insufficiently treated, and Constanța Sud and Mangalia exceed discharge
  limits (NTPA-001/2002). The Constanța Sud 5 m station shows "permanent extremes". The required load reductions
  are: P -35 % (north) and -64 % (south), N -72 % (north) and -37 % (south) (NIMRD 2024 study, chapters II.7
  and III.7.5).
  **Our DIVAnd numbers agree with these:** summer 2020 DIN 9.8 µM vs shelf mean 10.6 and median 7.2; PO4 0.12 vs
  shelf mean 0.18 and median 0.08. The gridded climatology is a fair stand-in for the shelf.
  On the Danube side, basin emissions in 2015-2018 were about 500 kt N/yr and 31 kt P/yr (ICPDR 2021, cited in the
  study). Point-source emissions fell 44 % (N) and 56 % (P) since 2009, and about 30 % (N) and 15 % (P) more
  could be cut before loads reach early-1960s levels. ICPDR modelling gives 2015-2018 loads at Reni of about 314 kt N/yr
  and 15.5 kt P/yr (from search extracts of the [ICPDR 2021 report](https://www.icpdr.org/sites/default/files/2023-09/2021%20Report%20on%20nutrient%20emission%20modelling%20in%20the%20DRB_1.pdf); NOT DIRECTLY VERIFIED).

**Thresholds.** See section 3.2.

**Natural vs real change.** Nutrients near Constanța are mostly a mixing line between Danube water (high DIN and
Si, low salinity) and shelf water. **Check salinity first.** A high-nutrient sample at low salinity is the plume
(natural, discharge-driven). A high-nutrient sample at normal salinity is a local source (outfall) or upwelling,
which is cold and also O2-poor. Then check the season (winter maximum, summer depletion), Danube discharge
anomaly, and whether chl or O2 respond. The robust way to compare years is the salinity-normalised
concentration: regress nutrient on salinity, then compare residuals or the value at a fixed salinity
(e.g. S = 15). This is standard in WFD transitional and coastal assessments. Ammonium and nitrite spikes at
normal salinity in summer point to sewage.

**Best source and live check.**
- `ei.fetch_chemistry_samples(...)`: historical bottles (MEASURED), 1963-2021 on the shelf, but nothing after
  1999 within 30 km of Constanța.
- `ei.chemistry_climatology_at(lat, lon, v, "danube"|"blacksea", depth)`, v in din/po4/si: the reference
  conditions (DERIVED). Seasonal, not live.
- `cm.fetch_timeseries("bgc_nut", ...)` (no3, po4) and `rea_bgc_nut`: MODELLED. **Do not show absolute nitrate
  or phosphate from the model** (section 5). At most show "model says nutrient-depleted / replete" as a
  qualitative flag, labelled as model.
- Copernicus in-situ (`insitu_bs`) has NTRA/PHOS only from historical casts and one Ukrainian cruise in
  September 2019 (stations CTA, CTB, CTC, CTM, EFGD, MDA-MDC, MGA-MGC around Constanța, Midia and Mangalia),
  plus the ALSEAMAR glider 8901034 (2023-24, NTRA sensor). Nothing is live.
- **Status: there is no live nutrient observation on the Romanian coast in any public feed.** This is the main
  data gap. NIMRD samples monthly at fixed coastal stations, but the data are not public at sample level.

### 2.3 Eutrophication status (synthesis)

**Why it matters.** MSFD Descriptor 5 asks whether "human-induced eutrophication is minimised". The
assessment combines causes (nutrients, criteria D5C1-D5C2), direct effects (chl, harmful blooms, transparency)
and indirect effects (bottom O2, loss of macroalgae and seagrass) (Commission Decision (EU) 2017/848).
A single index is what stakeholders understand.

**Official tool (BEAST).** Romania assesses D5 with BEAST, the Black Sea Eutrophication Assessment Tool. It was
built in the Baltic2Black project (Black Sea Commission with HELCOM) on the HEAT model, uses the warm season,
counts the good/moderate boundary as good status, and applies one-out-all-out between criteria.

Romania's official 2018-2023 assessment (NIMRD 2024 study for the Ministry of Environment, MSFD Art. 17;
[Studiu_raport_MSFD-2024.pdf](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf)):
- **D5C1 nutrients:** good only offshore (MT02). The shelf MT01 slightly exceeds the thresholds (P75 DIN 13.78,
  PO4 0.27 µM); transitional and coastal waters fail.
- **D5C2 chl:** thresholds met at 77-94 % of stations.
- **D5C5 bottom O2:** P10 of 5.44 mg/L and 54.3 % saturation (n = 145/126). This is below the 60 % saturation
  threshold, although the same paragraph calls the status "good" (flag this as an internal inconsistency).
- **BEAST, warm season 2020-2022:** about 50 % of stations and about 59 % of the Romanian EEZ area reached good
  status. Not good: transitional waters, the northern marine area, the shelf to 50-60 m, and the southern coast
  with the Constanța Sud, Eforie and Mangalia WWTPs and the ports.
- **Overall:** good status is not achieved in transitional, coastal or shelf waters.
- Lazăr et al. 2024 estimate that cuts of 38 % in DIP and 37 % in DIN are needed in coastal waters
  ([doi:10.3390/su16125146](https://doi.org/10.3390/su16125146)).
- The previous cycle, 2012-2017, is assessed in Lazăr et al. 2019
  ([Cercetări Marine 49](http://www.marine-research-journal.org/index.php/cmrm/article/view/142)).

**Our simplified index (indicator 3).** We use a HEAT-style eutrophication ratio, ER = observed / threshold. For
O2 we use threshold / observed, so ER > 1 is always worse. ER is averaged within each category, and the worst
category sets the index (one-out-all-out). Classes follow HELCOM HEAT 3.0: <= 0.5 high, <= 1.0 good, <= 1.5
moderate, <= 2.0 poor, > 2.0 bad ([Andersen et al. 2017](https://doi.org/10.1111/brv.12221)). All criteria are
warm season (May-Sep), and the thresholds are the **official Romanian MSFD values for marine waters**. The
Constanța point is about 5 km offshore, outside the 1-nautical-mile WFD coastal strip. Live result at Constanța
(2026-11-23 run):

| criterion | value used | threshold (OFFICIAL) | ER | class |
|---|---|---|---|---|
| nutrients: DIN summer | 9.80 µmol/L (DIVAnd window 2020) | 10.5 (P75) | 0.93 | good |
| nutrients: PO4 summer | 0.12 µmol/L (DIVAnd window 2020) | 0.23 (P75) | 0.51 | good |
| direct: chl May-Sep 2025 (satellite mean, 153 days) | 1.26 mg m-3 | 2.79 | 0.45 | high |
| indirect: bottom O2 P10 May-Sep 2025 (model) | 5.69 mg/L | 5.0 | 0.88 | good |
| **index** (worst category) | | | **0.88** | **good, close to the boundary (driven by O2)** |

**Replay check: the same algorithm fed the official 2018-2023 shelf statistics** (DIN P75 13.78, PO4 P75 0.27,
chl P75 south 0.69, O2 P10 5.51 mg/L and 57.3 %) gives ER 1.31, 1.17, 0.25, 0.91 and 1.05. The index is
**1.24 = moderate (not good), driven by nutrients**. That matches the official BEAST verdict for the shelf, so
the method is sound and the difference comes from the input data (`chemical_check.py` C5).

Measured chl P75 for the warm season 2018-2023 (NIMRD 2024 study, Table III.7.10) was below the limit everywhere:
transitional 10.25 (limit 11.88), coastal 4.9 (5.97), shelf north 1.86 (4.11), shelf south 0.69 (2.79) µg/L.
Our satellite May-Sep mean at Constanța (1.26 mg m-3) sits between the coastal and southern-shelf values, as
expected for a point 5 km offshore.

**Our live index says good; the official BEAST says the 0-50 m shelf is not good.** The reasons are known:
- our nutrients are a gridded mean, while the official statistic is the P75 of station samples;
- our O2 is modelled and has no saturation criterion. The reanalysis fails the 60 % saturation test in 2024
  (P10 57 %; section 2.1);
- one point is not an assessment unit;
- the official assessment uses NIMRD's 2018-2023 station data, which we do not have.

The dashboard should show the official NIMRD class as the headline and our live index as a "provisional, model
and satellite based" companion that updates daily. Further caveats shown in the UI: bottom O2 is model-only,
and coastal satellite chl can be biased by Danube CDOM and TSM. The biological-indicators session
(`biological.md`) owns chl; this index only consumes it.

### 2.4 pH and the carbonate system (acidification)

**Why it matters.** Lower pH and lower carbonate saturation (Ω aragonite and calcite) make it harder for
mussels, oyster larvae and coccolithophores to build shells. Larval mussels are the sensitive stage. pH also
swings with biology: high in blooms (CO2 uptake), low in respired bottom water and in upwelled water. That makes
pH a second eutrophication signal ("coastal acidification" from organic-matter respiration, on top of the
CO2-driven trend).
- Aquaculture: shell growth and larval survival. This is the main sector link.
- Shipyards and marine engineering: corrosion of concrete and steel depends on pH, O2 and temperature, but only weakly
  in this range.
- Others: minor.

**Typical values.** Black Sea surface water has very high total alkalinity because of river input. The model
gives TA about 3,300-3,450 µmol/L at Constanța (Atlantic surface water is about 2,300), DIC about 3,100-3,200.
Surface pH (total scale) is 8.1-8.5. The reanalysis monthly mean ranges from 8.15 (June) to 8.33 (November).
The forecast shows 8.48 in April (spring bloom) and 8.11 in July.

Literature (MEASURED):
- Open-sea upper-layer TA is 3.30-3.31 mg-eq/L (= mmol/L) in 2010-11, with a minimum of 3.20 off the Danube
  mouth. TA rises with salinity, and in the aerobic layer it did not change noticeably from 1988 to 2010.
  pH falls with depth from about 8.4 to 7.8 across the aerobic zone
  ([Kondratev et al. 2017](https://doi.org/10.22449/1573-160X-2017-4-35-45)).
- On the western shelf (a Bulgarian coastal station; preliminary EGU 2026 abstract):
  - monthly pCO2 is 340-500 µatm, mostly driven by temperature;
  - Danube water pushes pCO2 below 200 µatm, and upwelling pushes it above 800 µatm
  ([EGU26-12600](https://meetingorganizer.copernicus.org/EGU26/EGU26-12600.html)).
- The model's TA (~3.4 mmol/L) is therefore realistic.
- A Romanian coastal pH range from observations: NOT VERIFIED.

**Long-term trend.** Reanalysis 1993-2023 at Constanța: pH -0.007 per decade (not significant against
year-to-year noise; e.g. 1998-99 show a large dip linked to a DIC and TA drop in the model). DIC +0.04 and TA
+0.04 mol m-3 per decade. Global open-ocean surface pH declines at about -0.017 per decade. For the Black Sea, the reconstruction by
Polonsky and Grebneva (2019) gives only about -0.06 pH per 50 years (1956-2010)
([abstract](https://dergipark.org.tr/en/download/article-file/1500902)), because high and rising alkalinity
buffers part of the decline. Larger decadal swings reported for the 1960s and 1980-2000 are attributed to
natural variability and are contested ([trjfas.org](https://trjfas.org/abstract.php?id=518)). Copernicus pH
trend indicators are global only; there is no Black Sea pH OMI. Observed pH near Constanța: only 4 public samples (2021).
**We cannot measure an acidification trend here with public data.**

**Thresholds.** The MSFD has no pH criterion. The Romanian surface-water classification (Order 161/2006)
is said to use a 6.5-8.5 class band, but this is NOT VERIFIED (we could not open the order text). That band is
meant for freshwater, and 8.5 is exceeded naturally in Black Sea blooms. For the dashboard: show pH as anomaly vs the reanalysis climatology (z-score) and
flag only |z| > 2, labelled "model-based watch". OURS.

**Natural vs real change.** pH below the seasonal normal together with low O2, cold and saline bottom water
means upwelling. pH above normal with O2 supersaturation means a bloom. The Danube plume changes alkalinity and
pH through mixing. A real acidification signal is a multi-year drift that remains after removing these effects.
That needs decades of carbonate measurements we do not have.

**Best source.** `cm.fetch_timeseries("bgc_car", ...)` (ph, dic, alk; MODELLED) and `rea_bgc_car` for the
reference. Live check: pH 8.202, DIC 3,214 µmol/L, TA 3,454 µmol/L on 2026-11-23. Last 30 days anomaly -0.031
(z -0.26). Surface pCO2 and air-sea CO2 flux exist in `cmems_mod_blk_bgc-co2_anfc_2.5km_P1D-m` (not wrapped).

### 2.5 Hydrogen sulphide and the anoxic layer (why the Black Sea is special)

**The basin.** The Black Sea is the world's largest anoxic marine basin. A thin oxygenated layer (about 10 % of
the volume; [Copernicus OSR2, Capet et al. 2018](https://doi.org/10.1080/1755876X.2018.1489208)) lies over
sulphidic water. Strong haline stratification (fresh river input, saltier Bosporus inflow at depth) blocks
ventilation.

The onset of sulphide tracks the σt = 16.2 density surface. That sits at about 90-190 m depending on the
cyclonic gyres (shallow in the centre, deep at the rim). A suboxic zone lies between the oxycline and the
sulphide onset. During the 1980s eutrophication its upper boundary rose from σt ~15.9 to ~15.3, while the
sulphide onset stayed fixed in density
([Konovalov, Murray and Luther 2005](https://tos.org/oceanography/article/basic-processes-of-black-sea-biogeochemistry);
[Konovalov and Murray 2001](https://ftp.soest.hawaii.edu/glazer/Chen%20References/Papers1/Konovalov%202001.pdf)).

**Trend.** From 1955 to 2015 the oxygen inventory fell by 44 %, and the oxygen penetration depth (O2 < 20 µM)
shoaled from about 140 m to 90 m. The 1985-1995 "recovery" was an artefact of a thicker Cold Intermediate Layer.
Warming now limits winter ventilation ([Capet et al. 2016](https://doi.org/10.5194/bg-13-1287-2016)). Three Argo
floats gave 72 m in 2016, the shallowest in the Argo era (poor coverage; OSR2). Copernicus maintains this
as the indicator `BLKSEA_OMI_HEALTH_oxygen_trend` (1955-2021, open basin deeper than 50 m;
[product page](https://data.marine.copernicus.eu/product/BLKSEA_OMI_HEALTH_oxygen_trend/description)). BGC-Argo
shows the oxic/anoxic structure is very stable in density space basin-wide
([Stanev et al. 2018](https://doi.org/10.1002/2017GL076206)). So the shoaling is a change in where the
isopycnals sit and in ventilation, not a chemical change in the interface itself.

What this means for the dashboard: H2S never reaches the Romanian shelf water column in normal conditions.
Shelf depth is < 60 m, and the oxic/anoxic interface is at 100-200 m offshore. It matters in three ways:
(1) upwelling at the shelf break brings water from the upper oxycline (low O2, high nutrients) onto the shelf.
That is exactly the cold, saline, O2-poor intrusion seen in the forecast on 19-27 Nov 2026 (bottom S 19.5).
(2) During severe shelf hypoxia, sulphate reduction in sediments releases H2S into bottom water, which kills
what hypoxia spared. (3) The shoaling of the basin's oxygenated layer is a basin-scale climate signal for
context. Data: `bgc_nut` var `odu` ("oxygen demand units", the model's reduced substances including H2S;
MODELLED) is about 0 at Constanța, which is expected. The QUID shows the model's oxygenated-layer depth against
Argo with a bias of 8 m and r 0.81. **Indicator status: context layer only** (offshore depth of the
O2 = 20 mmol m-3 surface from `bgc_o2` profiles). Not on the shortlist.

### 2.6 Total suspended matter (TSM) and CDOM, as they relate to chemistry

**Why it matters (chemistry view).** TSM carries particle-bound phosphorus, metals and hydrophobic organics
(PAH, PCB, pesticides). High TSM after floods, storms or dredging therefore means high contaminant flux even
when dissolved values look fine. TSM and CDOM also make satellite chlorophyll unreliable in the plume (case-2
water). CDOM is a conservative tracer of Danube freshwater (inverse to salinity). It tells us whether a nutrient
or chl anomaly is plume water. The physical session owns turbidity and transparency (`physical.md`, Kd490);
here we only use them as covariates.

**Values.**
- In-situ SPM on the shelf is about 1-10 mg/L and turbidity 0-10 NTU. A regional SPM algorithm cut the
  satellite RMSD from 7.3 to 1.9 g m-3 (EO4SIBS, [Grégoire et al. 2023](https://doi.org/10.3389/fmars.2022.998970)).
  The same project built an SMOS-based coloured-detrital-matter product (2011-2019), which uses CDOM as a
  freshwater tracer.
- Plume turbidity correlates strongly with Danube discharge, with wind as a second driver
  ([Constantin et al. 2016](https://doi.org/10.1016/j.csr.2015.11.009)). Regional OLCI SPM and turbidity
  algorithms exist for the western Black Sea ([Constantin et al. 2024](https://doi.org/10.1016/j.ecss.2024.108871)).
- Satellite SPM (DINEOF, `open_data` key `spm_dineof`) at the Constanța pixel, Aug-Nov 2026: 0.5-1.3
g m-3 (median 0.74). Near-shore pixels in the box reach ~20 g m-3. EUXRoCB02 turbidity is 20-56 NTU (Sep-Nov
2026), and its CDOM reads 0.17-1.6 ppb (questionable; r = 0.95 with chl fluorescence). The offshore buoy
EUXRoOB03 read 57 NTU on 2025-06-01.

**Natural vs real change.** High TSM with low salinity is the plume (natural). High TSM with normal salinity and
high waves is resuspension (natural; check Hs in `physical.md`). High TSM with calm seas next to a port is
dredging (pressure). **Use as covariate, not as a chemical indicator.**

**Best source.** `sat_hr_l3` / `sat_hr_l4_month` (SPM, TUR; ~100 m), `open_data` `spm_dineof`; buoys TUR4.
CDOM: EUXRoCB02 (bad QC) and the glider 8901034 (2023-24). No CDOM product is wrapped in our Copernicus
catalogue.

### 2.7 Contaminants: heavy metals, petroleum hydrocarbons, pesticides, PAH, PCB (MSFD D8 and D9)

**Why it matters.** D8 asks for contaminant concentrations at levels "not giving rise to pollution effects".
D9 asks that contaminants in seafood stay below food-safety limits. Mussels concentrate metals and organics,
which is why they are the monitoring organism. Sources on the Romanian coast are the Danube, the ports of
Constanța, Midia and Mangalia, the Midia refinery (Năvodari), shipyards, WWTP outfalls and shipping.
- Ports and shipyards: the main sources (TPH, PAH, Cu, Zn, TBT). Dredged-material management depends on
  sediment-contaminant classes.
- Aquaculture and fishing: D9 compliance of mussels, Rapana and fish (Pb, Cd, Hg, benzo[a]pyrene, PCB, dioxins).
- Tourism: oil slicks and tar on beaches.

**Values (MEASURED by NIMRD, from recent papers).**

Oros et al. 2025, data 2018-2023 ([doi:10.3390/w17162406](https://doi.org/10.3390/w17162406)):
- Seawater (n = 298), mean µg/L: Cu 10.8 (range 0.14-51.6), Ni 7.2, Cr 7.2, Pb 5.7, Cd 0.46. Cd and Pb
  sometimes exceeded the MAC-EQS, mainly in Danube-influenced waters.
- Sediment (n = 277), mean µg/g dry weight: Ni 40.2, Cr 25.5, Cu 22.8, Cd 0.29.
  - Ni exceeded the ERL of 20.9 in over 75 % of samples, which is largely the natural background.
  - Cu exceeded its ERL of 34 in 21 % of samples, Pb exceeded 46.7 in 4 %.
  - There are no binding EU sediment standards for metals. ERL is the NOAA effects-range-low benchmark
    (Long et al. 1995).
- Molluscs mostly comply with Regulation (EU) 2023/915, with occasional Cd exceedances.

Damir et al. 2024, data 2016-2023 ([doi:10.3390/fishes9070274](https://doi.org/10.3390/fishes9070274)):
- Seawater 75th percentiles, µg/L: Cu 10.3, Cd 0.89, Pb 9.4, Ni 7.3, Cr 4.2.
- Sediment 75th percentiles, µg/g: Cu 43.8, Cd 0.52, Pb 20.8, Ni 61.0, Cr 47.8.
- Exceedances of safe limits were found for Cd, Pb, heptachlor, dieldrin, total DDT, the sum of 6 PCBs,
  benzo[a]pyrene and the sum of 4 PAHs.
- Organochlorine pesticides exceeded Romanian food limits (Order 147/2004), mostly in molluscs.

Petroleum hydrocarbon (TPH) concentrations from NIMRD: NOT VERIFIED (the annual reports were not found online).

**Thresholds (OFFICIAL).**

EQS for "other surface waters" (coastal), Directive 2008/105/EC as amended by 2013/39/EU
([EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32013L0039)), µg/L:

| Substance | AA-EQS | MAC-EQS |
|---|---|---|
| Cd | 0.2 | 0.45-1.5 (by hardness class) |
| Pb | 1.3 | 14 |
| Ni | 8.6 | 34 |
| Hg | - | 0.07 (biota 20 µg/kg) |
| HCH | 0.002 | 0.02 |
| DDT total | 0.025 | - |
| Benzo[a]pyrene | 1.7e-4 | 0.027 (biota 5 µg/kg) |

Seafood maximum levels for bivalves (wet weight), Regulation (EU) 2023/915, which replaced 1881/2006
([EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32023R0915)):
Pb 1.5 mg/kg, Cd 1.0 mg/kg, BaP 5.0 µg/kg, sum of 4 PAHs 30 µg/kg.

Reading: the mean dissolved Pb (5.7) is above the AA-EQS (1.3), and the 75th percentile of Cd (0.89) is above
the AA-EQS (0.2). Metals are a real D8 issue on the Romanian coast, but **only lab data can show it.**

**Official status 2018-2023** (NIMRD 2024 study, chapters III.8.5 and III.9.5, read from the PDF):
- **D8 (contaminants in the environment): not good in every reporting unit.**
  - Persistent organic pollutants fail in all units and all matrices.
  - Heavy metals fail in transitional waters (all matrices) and in coastal and marine sediments. They pass in
    coastal, shelf and offshore water and in biota.
  - PAHs fail in transitional waters, coastal sediments, shelf sediments and biota, and offshore sediments.
- **D9 (contaminants in seafood, molluscs): not good in every reporting unit.**
  - Metals fail in transitional waters.
  - POPs fail in coastal and shelf waters.
  - PAHs fail on the shelf.
- **Pressure data.** WWTP effluent TPH, nutrients and suspended solids are given per plant for 2018-2022:
  Rompetrol (Midia) refinery WWTP, Constanța Nord, Constanța Sud, Eforie Sud, Mangalia and Constanța Port (study
  chapter II.7). These are the right anchor points for "needs sampling" markers.

**Data status.** Lab-only. Romanian data are reported yearly by NIMRD (water, sediment, mussels) and in the MSFD
reports. EMODnet Chemistry hosts the "Black Sea - Contaminants aggregated datasets 1974/2023 v2025"
(`CONTAMINANTS_BLACKSEA_{WATER,SEDIMENT,BIOTA}`: water 1974-2023, sediment 1990-2023, biota 2008-2019;
[record](https://b2find.eudat.eu/dataset/415116b9-25a9-53d7-acc1-b7dcaab06b54)). These are listed in
`emodnet_insitu.md` but are not wrapped by our module, and we did not check them for Romanian rows today.
They are the best candidate for historical "needs sampling" tooltips. **Not fetchable as a
time series for the dashboard.** See section 6 for how to show it.

### 2.8 Bathing-water microbiology (tourism link)

**Why it matters.** The EU Bathing Water Directive (2006/7/EC) classifies each site from 4 seasons of
Escherichia coli and intestinal enterococci samples. It is the only chemical/biological water-quality number most
tourists ever see, and it is a direct indicator of sewage pressure (WWTP overflows during the summer
population peak). Mussel harvesting areas fall under similar E. coli rules (Regulation (EU) 2019/627 shellfish
classes A/B/C).

**Thresholds (OFFICIAL, Directive 2006/7/EC Annex I, coastal waters, cfu/100 mL)**
([EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32006L0007)):

| Parameter | Excellent | Good | Sufficient |
|---|---|---|---|
| Intestinal enterococci | 100 (95th percentile) | 200 (95th percentile) | 185 (90th percentile) |
| E. coli | 250 (95th percentile) | 500 (95th percentile) | 500 (90th percentile) |

**Romania (OFFICIAL, EEA country factsheet 2025).** 49 coastal sites (plus 1 inland). None was Sufficient or
Poor in any of these years, and 448 samples were taken in 2025
([EEA RO factsheet 2025](https://www.eea.europa.eu/en/topics/in-depth/bathing-water/state-of-bathing-water/bathing-water-country-factsheets-2025/ro-bathing-water-country-factsheet-2025.pdf)):

| Year | Excellent | Good |
|---|---|---|
| 2022 | 45 | 4 |
| 2023 | 34 | 15 |
| 2024 | 41 | 8 |
| 2025 | 41 | 8 |

Sewage context:
- The Eforie Sud WWTP opened in 2013. It serves Eforie, Agigea, Tuzla, Techirghiol, Costinești and Schitu
  ([Ziua de Constanța](https://ziuaconstanta.ro/english/latest/great-inauguration-of-the-south-eforie-wastewater-treatment-plant-felix-stroe-this-unit-is-a-benchmark-for-all-treatment-plants-in-romania-456212.html)).
- A burst sewage pipe off Eforie on 6 July 2023 (news report,
  [playtech.ro](https://playtech.ro/2023/dezastru-in-marea-neagra-deversare-de-fecale-si-urina-in-apa-intre-eforie-sud-si-nord/))
  is the kind of event the 4-year class cannot show.
- Recurring summer overflows at Constanța Sud: NOT VERIFIED.

**Live check (fixed 2026-11-23).** `el.bathing_water_history("RO")` (new function in `emodnet_layers.py`) returns
one row per site and season: site_id, name, lat, lon, year, class, class_code, latest_class, scheme. 49 sites,
2007-2024, 867 site-years. In the EMODnet layer the field `class` repeats the latest class on every year. The
season's own class is in `status`, which the function now uses. It matches the EEA factsheet exactly
(2022 45/4, 2023 34/15, 2024 41/8). Seasons before 2015 follow the old 76/160/EEC scheme ("Good or Sufficient"),
so the function flags them in `scheme` and the indicator uses 2015 onwards only.

| season | Excellent | Good | Sufficient | Poor | share Excellent |
|---|---|---|---|---|---|
| 2015 | 15 | 23 | 10 | 1 | 31 % |
| 2016 | 34 | 15 | 0 | 0 | 69 % |
| 2017 | 25 | 23 | 1 | 0 | 51 % |
| 2018 | 28 | 19 | 2 | 0 | 57 % |
| 2019 | 38 | 10 | 1 | 0 | 78 % |
| 2020 | 35 | 13 | 1 | 0 | 71 % |
| 2021 | 42 | 7 | 0 | 0 | 86 % |
| 2022 | 45 | 4 | 0 | 0 | 92 % |
| 2023 | 34 | 15 | 0 | 0 | 69 % |
| 2024 | 41 | 8 | 0 | 0 | 84 % |

Reading:
- Clear improvement since 2015.
- The 2023 dip coincides with the July 2023 E. coli exceedances at Mamaia (4,000 cfu/100 mL vs the limit of 500;
  [Radio Constanța](https://radioconstanta.ro/2023/07/19/ce-spun-specialistii-despre-valorile-crescute-de-e-coli-inregistrate-pe-litoral))
  and the Eforie pipe burst.
- One site has never been Excellent since 2015: Cordon Venus-Saturn II Actetis (43.830, 28.591).

The class is MEASURED (lab) and OFFICIAL, but it is a 4-season statistic published once a year, so it cannot
detect a single overflow event. Short events show up in DSP Constanța notices (e.g. Vadu and Corbu, August 2024,
[g4media](https://www.g4media.ro/probele-de-apa-de-mare-prelevate-din-zona-plajelor-neamenajate-din-localitatile-vadu-si-corbu-contin-cantitati-mari-de-e-coli-anunta-dsp-constanta.html)).

---

## 3. Reference conditions and thresholds

### 3.1 Oxygen

| Threshold | Value | Status | Where we use it |
|---|---|---|---|
| Hypoxia | < 2 mg/L (= 62.5 µmol/L, about 1.4 mL/L) | LIT (Diaz and Rosenberg 2008; used by Capet et al. 2013 for the NWS) | class D, "hypoxic days" |
| **Romanian MSFD D5C5 (GES)** | **P10 of bottom O2 in May-Sep at stations <= 50 m must be >= 5 mg/L and >= 60 % saturation**. Offshore (MT02) it is replaced by D5C8 macrozoobenthos (M-AMBI) | **OFFICIAL** (NIMRD 2024 Art. 17 study, Table III.7.1). Lazăr et al. 2019 mention "6 mg/L" in the text but 5 mg/L in the figure: use 5 | season test in indicator 1, O2 criterion in the index |
| EU D5C5 wording | O2 "is not reduced, due to nutrient enrichment, to levels that indicate adverse effects on benthic habitats"; no EU number | OFFICIAL (Decision (EU) 2017/848; via [HELCOM](https://indicators.helcom.fi/indicator/oxygen-debt/)) | |
| 3 mg/L or 30 % saturation | used in some other seas | not found for Romania (NOT VERIFIED) | not used |
| Sublethal effects begin | ~4.6 mg/L (90th percentile of sublethal thresholds) | LIT ([Vaquer-Sunyer and Duarte 2008](https://doi.org/10.1073/pnas.0803833105)) | class B/C boundary rounded to 4 |
| Daily class limits 5 / 4 / 2 mg/L | 5 = the official D5C5 level applied to a daily value; 4 and 2 as above | OURS (the daily classification), built on OFFICIAL and LIT numbers | indicator 1 |
| Surface saturation flags | > 120 % bloom; < 80 % respired or upwelled water | OURS | indicator 2 |
| Reference | reanalysis day-of-year climatology 1993-2022 (p10, mean, p90) and DIVAnd seasonal climatology 1970-2022 | DERIVED | anomaly display only |

### 3.2 Nutrients, chl and the index targets

Romanian thresholds used in the official MSFD 2018-2023 report (NIMRD 2024 study, Table III.7.1), in µmol/L
unless stated:

| Water category | PO4 (DIP) | TP | NO3 | NO2 | NH4 | DIN | Chl a, warm season (µg/L) | Status |
|---|---|---|---|---|---|---|---|---|
| Transitional (RO-TT03, Danube RBMP 2021-2027 Annex 6.1.3.D); statistic = **P90** | 0.45 | 1.50 | 8 | 1.20 | 7.14 | 20 | 11.88 | OFFICIAL (WFD) |
| Coastal (RO-CT01/CT02); statistic = **P90** | 0.30 | 1.00 | **4.0** (0.056 mg/L N-NO3; we converted the mg/L value) | 0.30 | 6.50 | 13.5 | 5.97 | OFFICIAL (WFD) |
| Marine waters (MSFD, statistic = P75) | 0.23 | - | - | - | - | 10.50 | 4.11 (north) / **2.79 (south)** | OFFICIAL in the report; derived by expert judgement on historical data (reference DIP 0.15 + 50 % ≈ 0.23; the derivation is from a search snippet only) |

Notes:
- Secchi depth: marine 6.8 m (P10); WFD minimum 2 m.
- Order 161/2006 gives freshwater-style maxima (TP 0.1 mg/L, NH4-N 0.1 mg/L, etc.; the NO3 and NO2 limits are
  printed swapped). Its 5 mg/L chl limit was rejected for the sea as unrealistic.
- **We now use the official marine values in the index:** DIN 10.5, PO4 0.23, chl 2.79, and bottom-O2 P10 5 mg/L.
- The coastal values (DIN 13.5, PO4 0.30) apply within 1 nautical mile of the shore, e.g. for Mamaia and Eforie
  beaches.
- The official statistic is the P75 of samples. Comparing a DIVAnd seasonal mean with it is an approximation
  (it underestimates P75), so our ER values lean optimistic.

Pre-eutrophication context (LIT): at a station 20 nmi off Constanța, Si was 30-60 µM and PO4 0.2-1.5 µM in
1968-74. NO3 was about 15 µM in the early 1980s, falling to 4-5 µM in the early 1990s
([Oguz 2005](https://doi.org/10.5670/oceanog.2005.46), using the
[Cociașu et al. 1996](https://doi.org/10.1016/0025-326X(95)00106-W) series).

### 3.3 pH and contaminants
- pH: no MSFD criterion. The Order 161/2006 band (6.5-8.5) is NOT VERIFIED and was designed for freshwater.
  We use a z-score watch (OURS).
- Contaminants: water EQS (Directive 2013/39/EU) and seafood maximum levels (Regulation 2023/915) are
  OFFICIAL (tables in 2.7). Sediment: ERL/ERM benchmarks are LIT, since there is no binding EU sediment standard.
- Bathing water: BWD class limits are OFFICIAL (table in 2.8).

### 3.4 Which reference period
- **Pre-eutrophication (1960s)** is the "natural" benchmark the MSFD and WFD aim at. We have bottles for O2, PO4
  and Si from the 1960s, but no nitrate.
- **Recent normal (1993-2022 reanalysis, 1998-2022 satellite chl, DIVAnd seasonal)** is used for
  anomalies, i.e. "unusual for the season". An anomaly is not a status. A normal value can still be eutrophic,
  and an anomaly can be natural.
- The dashboard shows both: status against threshold (traffic light) and anomaly against climatology (z-score).

---

## 4. Natural variability vs real change: decision rules

Apply in this order. The first matching rule labels the event; the "pressure" label is given only if no
natural rule explains it.

| Observation | Check first | If true | Label |
|---|---|---|---|
| Bottom O2 < 4 mg/L | bottom T fell > 1.5 °C in 7 days, or S near the bottom > 18.5 | cold saline water from the shelf break (wind-driven upwelling or onshore flow) | NATURAL (implemented in `chemical_check.py` C1) |
| Bottom O2 < 4 mg/L | surface-bottom ΔT > 2 °C in May-Oct (stratified) and a chl peak or high O2 saturation 1-4 weeks before | bloom decay under stratification | PRESSURE-RELATED (eutrophication) |
| Bottom O2 < 4 mg/L | Danube Mar-Jun discharge above the 75th percentile | plume-driven stratification and nutrients; part natural (flood year), part pressure (river load) | MIXED; report the discharge anomaly beside it |
| Surface O2 sat < 80 % | coastal SST more than 2 °C below offshore SST (`physical.md` upwelling index) | upwelling | NATURAL |
| Surface O2 sat > 120 % | chl above its p90 | bloom | report as a bloom; pressure only if recurring above the seasonal norm |
| High DIN, PO4 or Si | salinity below 14 (plume) | Danube water | NATURAL at that moment; compare salinity-normalised values across years |
| High NH4, NO2 or PO4 | normal salinity, near an outfall, summer | sewage | PRESSURE |
| Low pH | low O2 and cold saline water | upwelling | NATURAL |
| Any model-only anomaly | is the variable validated? | forecast-reanalysis offset (O2 bottom -2 mg/L, NO3, PO4) | MODEL ARTEFACT until confirmed by an observation |

Live example (C1 output): all five < 4 mg/L episodes in the forecast since Dec 2024 (2024-12-17/20,
2025-11-27/28, 2026-01-01/05, 2026-01-10/11, 2026-11-20/27) are in the cold season with bottom S 19.1-19.9 and
are labelled NATURAL. None occurred in the stratified Jul-Oct season of 2025 or 2026. The Oct-Nov 2024 episodes
(min 1.38-1.48 mg/L) fall in the first weeks of the forecast record, before physics data start in our series
(2024-12-01). They could not be attributed and may include model spin-up.

---

## 5. Model vs observations (quantified)

All daily means, at Constanța unless stated. Units mg/L for O2, mmol m-3 (= µmol/L) for nutrients.
Bias = model - observation.

| Comparison | n | obs mean | model mean | bias | RMSE | r |
|---|---|---|---|---|---|---|
| Forecast vs reanalysis, surface O2 (overlap 2024-10-03..12-31) | 90 | 9.32 (rea) | 9.11 | -0.21 | 0.91 | -0.25 |
| Forecast vs reanalysis, **bottom O2** | 90 | 8.47 (rea) | 6.43 | **-2.04** | 3.08 | 0.47 |
| Forecast vs reanalysis, NO3 | 90 | 0.01 (rea) | 1.29 | +1.29 | 2.44 | 0.30 |
| Forecast vs reanalysis, PO4 | 90 | 0.40 (rea) | 0.14 | -0.26 | 0.32 | -0.09 |
| Reanalysis vs bottles, surface O2 (<= 30 km, 1993-2021) | 41 | 11.20 | 9.74 | -1.46 | 2.31 | 0.63 |
| Reanalysis vs deepest bottle >= 15 m, O2 | 40 | 8.60 | 7.90 | -0.70 | 2.00 | 0.65 |
| Reanalysis vs bottles, surface **NO3** | 35 | 3.46 | 28.41 | **+24.95** | 31.1 | 0.36 |
| Reanalysis vs bottles, surface PO4 | 38 | 0.28 | 0.10 | -0.18 | 0.38 | -0.09 |
| Reanalysis vs buoy EUXRo03 surface O2 (2013-2023) | 1,842 | 9.22 | 8.90 | -0.32 | 1.44 | 0.65 |
| Forecast vs buoy EUXRoOB03 surface O2 (2025-26) | 349 | 8.70 | 8.85 | **+0.15** | **0.37** | **0.93** |
| Forecast vs buoy EUXRoOB02 surface O2 (2025-26) | 338 | 8.00 | 8.75 | +0.75 | 1.54 | 0.70 |
| Forecast vs buoy OB03 via GeoEcoMar ERDDAP (1-23 Nov 2026, live) | 23 | 8.51 | 8.95 | +0.45 | 0.45 | 0.89 |
| Forecast vs coastal buoy EUXRoCB02 (Sep-Nov 2026) | 26 | 5.53 | 7.55 | +2.01 | 3.26 | 0.67 |

Seasonal cycle of surface NO3 at Constanța (mmol m-3): bottles 1980-99 median 2-7; reanalysis 1993-2023
monthly mean 13-29; forecast 2024-26 0-7, and 0.00 from May to September. Reanalysis annual means:
2019 16.8, 2020 18.5, 2021 19.5, 2022 18.5, 2023 17.1, **2024 0.23**. The 2024 collapse coincides with the
period the reanalysis was extended with the newer forcing. The QUID V202511 Table 8 shows the Danube nitrate
load changed by 0.63x and phosphate by 3.46x relative to V202411. Danube nutrient concentrations in the model
are 1996-2021 TNMN monthly means "extrapolated to present", multiplied by the real-time discharge from the
Romanian hydrological institute (QUID section VI). So model nutrients carry **no information on present-day
changes in river nutrient concentration**, only on discharge.

**Verdict.**
- O2 surface: forecast reliable offshore (r 0.93 at OB03); use with a "model" label inshore.
- O2 bottom: classes are indicative. Never compare the forecast with the reanalysis climatology without stating
  the 2 mg/L offset. Prefer absolute classes, with the attribution test.
- Nitrate and phosphate: model values unsuitable for status or anomaly. Use EMODnet and DIVAnd for reference and
  ask NIMRD for recent data.
- pH: no validation data on the shelf; model-based watch only.

---

## 6. What cannot be fetched, and how the dashboard should show it

| Parameter | Why not | What the dashboard shows |
|---|---|---|
| Live nutrients (DIN, PO4, Si, NH4, NO2) | no public live or recent observations on the Romanian coast; model unreliable | DIVAnd seasonal reference map plus historical bottle points (grey, with year); badge "last public observation 1999 (Constanța) / 2021 (shelf)"; a "needs sampling" marker at NIMRD stations |
| Bottom O2 measurement | no bottom sensor on any Romanian buoy | model value with a hatched "MODELLED" badge and the bias line from section 5; historical bottle bottom O2 points |
| Contaminants in water, sediment, biota (D8/D9) | lab analysis, yearly | static "needs sampling" markers at ports (Constanța, Midia, Mangalia), refinery (Năvodari), WWTP outfalls (`wastewater_plants`, `discharge_points` layers) and mussel farms; tooltip with the latest NIMRD reported status (to be filled from the annual report) and the EQS/MAC threshold |
| Bathing-water microbiology events | weekly lab samples in season, published yearly as a 4-year class | `bathing_waters` layer with the official class per site and year; link to the EEA profile; no live claim |
| Shellfish toxins, harmful algae counts | lab | "needs sampling" at mussel farms; biological session's bloom risk as a proxy |
| H2S on the shelf | not measured routinely | not shown, except the offshore oxic/anoxic depth context layer |

Design rule: every tile carries (a) origin (MEASURED, DERIVED or MODELLED), (b) date of the newest value, and
(c) confidence (HIGH, MEDIUM or LOW from section 0). A missing measurement is shown as an empty marker with "needs
sampling", never as a modelled value presented as fact. This answers the jury's question "direct measurement
vs derived indicator".

---

## 7. Indicator cards (shortlist detail)

### 1. Bottom-oxygen status class
- **Algorithm.** Daily `o2_bottom` (mmol m-3) times 0.032 gives mg/L. Daily class A >= 5, B 4-5, C 2-4, D < 2.
  Season test (official RO D5C5): May-Sep P10 >= 5 mg/L and P10 saturation >= 60 %. Saturation uses the bottom
  T from `phy_temp`/`rea_phy_temp` and S = 18. Also: minimum, days < 2, days < 4. Attribution test for each
  episode < 4 mg/L (section 4).
  Anomaly vs `rea_bgc_o2` climatology shown only with the offset warning.
- **Source.** `bgc_o2` (live plus 10-day forecast), `rea_bgc_o2`, EMODnet bottles (validation), `phy_temp`
  `bottom_temp`, `phy_sal` at 24 m.
- **Confidence.** MEDIUM-LOW.
- **Public.** "How much oxygen is left near the seabed, where mussels and fish live. Red means animals there
  can suffocate."
- **Student.** "Bottom O2 drops when stratification traps decaying algae under warm water, or when deep, oxygen-poor
  Black Sea water is pushed onto the shelf. We check temperature and salinity to tell which."
- **Stakeholder.** "Early warning for mussel farms and fishing grounds: a red class in summer means expect
  mortality. Notify ANPA and NIMRD, and check farms and benthic grounds."
- **Researcher note.** The model's `o2b` field is the deepest wet level (~26 m here). The forecast system
  (V202511) runs about 2 mg/L lower than the reanalysis at this cell, and no shelf validation is published.
  Classes are therefore indicative. A bias correction needs post-2004 bottom casts (NIMRD). The official
  2018-2023 values (P10 5.44 mg/L, 54.3 %; minimum 3.33 mg/L) come from NIMRD station data and should be shown
  next to the model as the reference.

### 2. Surface O2 saturation
- **Algorithm.** O2sat from Garcia and Gordon (1992) (Benson-Krause fit, µmol/kg) times density gives µmol/L;
  %sat = 100 x O2 / O2sat. Our implementation matches buoy OSAT within 0.2 % (r 0.98, n 317). Flags: > 120 %,
  < 80 %. Anomaly vs the buoy's own monthly climatology once 3+ years exist.
- **Source.** EUXRoOB01-03 (measured, near real time, monthly upload), `bgc_o2` + `phy_temp` + `phy_sal`.
- **Confidence.** HIGH offshore buoys; LOW coastal buoy CB02.
- **Public.** "Is the surface water breathing normally? Over 100 % means a plankton bloom; well under 100 %
  means deep or used-up water has come up."
- **Student.** "Saturation removes the temperature effect, so a value below 80 % in summer is a biological or
  upwelling signal, not just warm water."
- **Stakeholder.** "A supersaturation streak means a bloom, which can lead to low bottom oxygen 1-4 weeks later
  under calm warm weather."
- **Researcher note.** The OSAT from the buoys uses the provider's formula. Ours matches it. Brackish salinity
  (15-18) is inside the fit range.

### 3. Eutrophication index (simplified BEAST/HEAT)
- **Algorithm.** Section 2.3. ER per criterion, category mean, worst category. Five classes.
- **Source.** `sat_chl_l4_my`, `bgc_o2`, `chemistry_climatology_at` (din, po4, blacksea, winter).
- **Confidence.** LOW-MEDIUM.
- **Public.** "One grade for 'too many nutrients' in the sea: from high (clean) to bad (algae and dead zones)."
- **Student.** "It combines cause (nutrients), effect (algae, chl) and consequence (bottom O2), and the worst
  part sets the grade, as in the HELCOM and Black Sea assessment tools."
- **Stakeholder.** "Shows whether the coastal water body meets the MSFD good-environmental-status target for
  eutrophication, and which part fails (here: bottom oxygen)."
- **Researcher note.** The thresholds are the official Romanian marine-water values (section 3.2). The statistics
  are not: DIVAnd means instead of station P75, and model O2 without the saturation criterion. Nutrients use the
  2020 summer DIVAnd window, a temporal mismatch with chl and O2 (2025). Treat it as provisional and show the
  official BEAST class (NIMRD) as the headline.

### 4. Nutrient status vs reference
- **Algorithm.** For each nutrient: value / Danube DIVAnd seasonal climatology (anomaly ratio) and value /
  target (ER). Salinity-normalise when the sample salinity is known (section 2.2).
- **Source.** EMODnet bottles, DIVAnd (danube, blacksea). Model only as a qualitative flag.
- **Confidence.** MEDIUM (history), NONE (live).
- **Public.** "How much fertiliser-type nutrients are in the sea compared with the past."
- **Student.** "DIN and phosphate peaked in the 1970s-80s from Danube farming and sewage; phosphate is now near
  1960s levels, nitrogen is not."
- **Stakeholder.** "Tracks whether reduced river and sewage loads work; needs NIMRD's monitoring data to be
  current."
- **Researcher note.** Winter DIVAnd windows after 2012-2016 are masked (relerr > 0.3). Summer windows reach 2020.
  Bottles end in 1999 near Constanța.

### 5. N:P and Si:N
- **Algorithm.** DIN/PO4 (molar) vs 16; Si/DIN vs 1. Warning if Si:N < 1 and N:P > 30 (diatom limitation plus P
  limitation, which favours non-diatom blooms).
- **Source.** As 4.
- **Confidence.** MEDIUM (history).
- **Public.** "The recipe balance for algae; when the balance is wrong, the 'wrong' algae win."
- **Student.** "The Iron Gates dam trapped silicate after 1972; Si:N fell below 1 and diatoms lost ground."
- **Stakeholder.** "A harmful-bloom early-warning factor for mussel farms."
- **Researcher note.** Summer 2020 DIVAnd window: N:P 84, Si:N 0.57. Summer ratios mostly reflect uptake, not
  the supply. Winter ratios are the better supply indicator but are masked after 2012.

### 6. Bathing-water class
- **Algorithm.** Per site: official class (Excellent, Good, Sufficient, Poor) per year. Coast-wide share
  Excellent, and any change from last year.
- **Source.** `emodnet_layers.bathing_water_history()` (per-season class from the layer's `status` field; `fetch_wfs("bathing_waters")` for the map).
- **Confidence.** HIGH (official, lab-measured), annual.
- **Public.** "Is the beach water clean enough to swim? Official EU grade for each of the 49 Romanian beaches."
- **Student.** "Measured from E. coli and enterococci in water samples over four summers."
- **Stakeholder.** "Tourism and WWTP planning: a drop from Excellent to Good near an outfall flags sewage pressure."
- **Researcher note.** The 4-year percentile method hides single events. Pair it with summer NH4 and PO4 where
  NIMRD data exist.

### 7. pH / carbonate watch
- **Algorithm.** pH anomaly and z-score vs the reanalysis day-of-year climatology; flag |z| > 2; show the
  1993-2023 trend line.
- **Source.** `bgc_car`, `rea_bgc_car`.
- **Confidence.** LOW.
- **Public.** "Is the sea getting more acidic? Model estimate; no local measurements yet."
- **Student.** "The Black Sea is strongly buffered by river alkalinity, so pH stays above 8 even as CO2 rises."
- **Stakeholder.** "Relevant for mussel hatcheries and larvae. A sensor on the coastal buoy would make this
  measurable."
- **Researcher note.** Model TA and DIC are not validated on the shelf (QUID). The 1998-99 dip is a model
  artefact candidate (a simultaneous TA and DIC drop).

---

## 8. Answers we found without NIMRD (research 2026-11-23)

We could not ask NIMRD in time, so each question below was answered from public documents. The key source is
the NIMRD study behind Romania's 2024 MSFD report, which we downloaded and read
([Studiu_raport_MSFD-2024.pdf](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf),
375 pp., data 2018-2023), cited below as "MSFD 2024". Its 2018 predecessor
([STUDIU MSFD V1.9](https://mmediu.ro/app/webroot/uploads/files/STUDIU%20MSFD%20V1.9.pdf), data 2012-2017) is
cited as "MSFD 2018".

### 8.1 Post-2000 observations near Constanța (was: "please share your monitoring data")
**Answered with statistics; raw station data remain restricted.**
- **MSFD 2024:** bottom O2 2018-2023 by unit (table in 2.1) and nutrients for coastal and shelf waters
  (table in 2.2). The full set is 1,089 water samples from 78 stations.
- **MSFD 2018 (2012-2017):** bottom O2 P10 **6.8 mg/L** (n = 137), with three events below 60 % saturation at
  Sf. Gheorghe and Portița 30 m. Marine P75 DIP 0.32 and DIN 13.74 µM.
- **Trend:** the P10 fell from 6.8 (2012-17) to 5.44 mg/L (2018-23). Bottom oxygen got worse while phosphate
  improved.
- **October 2023 survey** (n = 72; Oros et al. 2024,
  [Cercetări Marine 54](https://www.marine-research-journal.org/index.php/cmrm/article/download/283/220)), means
  with ranges:
  - O2 6.26 mL/L (2.33-11.78), about 8.9 mg/L (3.3-16.8);
  - PO4 0.37 µM (max 12.5);
  - SiO4 7.8 µM (1.4-47.4);
  - NO3 3.15 µM (0.9-32.7);
  - NH4 4.33 µM, with a maximum of 114 µM at **Constanța Sud 10 m**, next to the WWTP outfall.
- **NIMRD 2025 bathing-season bulletins**, Mamaia surface water
  ([Info-2025.06.30](https://www.nimrd.ro/uploads/Info-2025.06.30.pdf),
  [.07.14](https://www.nimrd.ro/uploads/Info-2025.07.14.pdf),
  [.07.28](https://www.nimrd.ro/uploads/Info-2025.07.28.pdf), .08.11, .08.25):
  - O2 per fortnight ranged 2.12-6.06 mL/L, i.e. 39.9-112 % saturation.
  - **15 Jul 2025: 2.12 mL/L (3.0 mg/L, 39.9 %), described as a "hypoxic regime" at the surface.**
  - 14 Jul: a multispecies bloom of 1.3 million cells/L.
  - SST 14.0-26.5 °C.
  - These bulletins show surface hypoxia can occur in the bathing zone when upwelling and bloom decay combine.
- **Open download:** EMODnet Chemistry "Black Sea Eutrophication and Acidity aggregated datasets 1935/2023 v2023",
  aggregated by NIMRD ([record](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/c80fbb3e-575c-4c18-bd2d-2376a71ccebf),
  [unrestricted zip](https://nodc.ogs.it/repository/aggregated-datasets/eutrophication/EMD_Eutrophication_BlackSea_2023_unrestricted.zip)).
  It is the same family as our ERDDAP source. NIMRD's 2008+ monitoring sets are listed in EDMED as "by
  negotiation" ([6579](https://www.bodc.ac.uk/resources/inventories/edmed/report/6579/)).
- **WFD status** (3rd river basin plan 2021-2027, quoted in MSFD 2024): both natural coastal water bodies have
  **bad** ecological status, both heavily modified ones have **bad** ecological potential, and the marine
  transitional body is **moderate**.

### 8.2 Thresholds (was: "which thresholds do you use?")
**Answered (section 3.2).**
- Coastal NO3 = 0.056 mg/L N, which is 4.0 µM.
- Transitional and coastal limits are tested on the **P90**, marine limits on the **P75**.
- D5C5 contradiction: the study says P10 saturation of 54.3 % "does not meet good status", then "status is good".
  The chapter conclusion says good status is not achieved in transitional, coastal or shelf waters. **We read
  D5C5 as failed on saturation.**

### 8.3 Hypoxia and mortality events, 2009-2026 (was: "were there events in 2024-26?")
**Answered: dated list.**
- Sep 2009: bottom saturation 25.6 % at Sulina 30 m and below 30 % at East Constanța
  ([Lazăr et al. 2012, Geo-Eco-Marina 18](https://zenodo.org/records/56875/files/09_lazar_BT.pdf)).
- **29-31 Jul 2010: thousands of dead fish at Mamaia, Năvodari, Constanța and Tomis port**
  ([ProTV](https://stirileprotv.ro/stiri/eveniment/sute-de-pesti-morti-au-ajuns-pe-plajele-din-mamaia-navodari-si-constanta.html)).
  - NIMRD measured near-anoxic bottom water off East Constanța: saturation 25.3 %, among the lowest of 1963-2010.
    The cause was upwelling plus decay of organic matter (Lazăr et al. 2012).
  - GeoEcoMar reported mass benthic mortality in a bay near Constanța, during a Prorocentrum cordatum bloom with
    water at 27-28 °C ([edupedu](https://www.edupedu.ro/de-ce-apare-fenomenul-de-eutrofizare-in-apele-costiere-romanesti-explicatiile-cercetatorilor-tatiana-begun-si-dan-vasiliu-de-la-geoecomar/)).
  - Literature gives a minimum of about 34.8 µM (1.1 mg/L) at Constanța.
- MSFD 2018: **no anoxia with fish mortality recorded on the Romanian coast since 2010.**
- 6 Jun 2024: DSVSA (the county veterinary and food-safety authority) **banned mussel harvesting at Agigea and
  Mangalia because of phycotoxins**
  ([bzi.ro](https://www.bzi.ro/pescarilor-li-s-a-interzis-sa-mai-adune-scoici-din-marea-neagra-nivelul-toxinelor-din-apa-a-crescut-4998745)).
- 21-22 Oct 2024: red-brown water in Tomis port, the dinoflagellate Lingulodinium identified by NIMRD, with advice
  not to harvest shellfish ([TVR](https://tvrinfo.ro/marea-neagra-s-a-colorat-in-rosu-in-portul-turistic-tomis-cercetator-stiintific-sunt-alge-microscopice-care-produc-aceasta-culoare/)).
  This overlaps the forecast model's Oct 2024 bottom-O2 episode (min 1.48 mg/L on 14 Oct) only loosely.
- Jul 2025:
  - surface hypoxic regime at Mamaia (above);
  - upwelling took the sea from 23-24 to 13 °C (22 Jul), and Mangalia fell to 9 °C (29 Jul)
    ([digi24](https://www.digi24.ro/stiri/actualitate/social/fenomenul-care-strica-vacanta-turistilor-de-pe-litoral-apa-marii-s-a-racit-brusc-de-la-23-de-grade-la-doar-13-grade-3337763));
  - 375-1,310 t of algae and 10-60 t of mussels were removed from beaches per fortnight (NIMRD bulletins).
- 30 Sep 2025: thousands of dead Rhizostoma jellyfish from Saturn to Constanța
  ([Observator](https://observatornews.ro/eveniment/fenomen-ciudat-pe-litoral-au-aparut-mii-de-meduze-moarte-pe-zeci-de-kilometri-de-tarm-632919.html)).
- **27-28 Jan 2026: "carpets" of Rapana and mussels stranded at Vadu and Mamaia Nord** after a storm (the sea
  advanced about 15 m), attributed to the storm, not pollution
  ([Euronews RO](https://www.euronews.ro/articole/video-peisaj-inedit-pe-litoral-un-covor-de-rapane-si-scoici-a-invadat-plaja-dupa)).
  The forecast model's low-O2 episode was earlier (1-5 Jan 2026), so the stranding is not evidence for it
  (section 8.8).
- 15 Jun and 23 Jul 2026: upwelling from about 19-25 °C to 13 °C at Mamaia and Mangalia. In June a tourist died
  of thermal shock
  ([bzi.ro](https://www.bzi.ro/tragedie-in-mamaia-un-turist-german-si-a-pierdut-viata-barbatul-a-suferit-un-soc-termic-dupa-scaderea-brusca-a-temperaturii-apei-5554301)).
  Upwelling is the same mechanism behind our "natural" low-O2 attribution rule.
- Nov 2026: no report found, so nothing confirms or rejects the model's 19-27 Nov bottom-O2 episode.

### 8.4 Is the model's bottom O2 right? (was: "do your casts confirm the forecast?")
**Answered indirectly (section 5).**
- Reanalysis 2018-2023 at Constanța: mean 8.31, P10 6.77, min 3.86 mg/L.
- NIMRD observed at its stations: mean 8.02, P10 5.44, min 3.33.
- So the model is right on average and about 1.3 mg/L too optimistic in the low tail.
- The forecast system runs about 2 mg/L lower than the reanalysis, so it may be closer in the tail. That cannot
  be checked until 2024+ casts are public.
- Copernicus' own validation of the reanalysis on the NW shelf (regions 4 and 5, < 50 m; QUID 007-005 issue 1.0,
  Table 4, [PDF](https://documentation.marine.copernicus.eu/QUID/CMEMS-BLK-QUID-007-005.pdf)):
  - O2 bias -7.6 mmol m-3 (-3.4 %), RMSD 34.6 mmol m-3 (1.1 mg/L), Nash-Sutcliffe 0.90.
  - Caveat: "almost no observations on the NWS after 1995". The shelf skill is validated mostly against 1990s
    Romanian and Bulgarian data.
  - Nitrate is "overestimated on the shelf", especially surface nitrate in summer, while phosphate is "well
    simulated". This matches our 9x nitrate finding.
  - Danube loads: 1992-2010 annual loads with a repeated seasonal pattern; **2010-2022 climatological means** "due
    to the lack of observations"; nutrient retention in the delta is ignored.
  - So the model's nutrients cannot show any real change after 2010.
- Capet et al. 2013 (the same model family, 15 km grid) reach r = 0.67 against 14,123 O2 observations. They note
  the model predicts hypoxia at depths under 20 m that is not observed, and still puts hypoxia into the bay of
  Constanța ([PDF](https://bg.copernicus.org/articles/10/3943/2013/bg-10-3943-2013.pdf)). Romanian-shelf hypoxia
  episodes in the model should be read as "risk", not fact.
- **Live surface check today:** forecast `bgc_o2` vs GeoEcoMar buoy OB03 for 1-23 Nov 2026 (23 days): bias
  +0.45 mg/L, RMSE 0.45, r 0.89 (obs 8.6 mg/L, model 9.1 mg/L on 23 Nov).

### 8.5 Contaminants (was: "latest status near ports and refinery?")
**Answered (section 2.7).**
- D8 and D9 are **not good in every reporting unit** (MSFD 2024).
- Values by matrix come from Oros et al. 2025 and Damir et al. 2024.
- MSFD 2024 chapter II.7 holds effluent TPH and nutrients per WWTP for 2018-2022. Those plants are the hot spots:
  - the Rompetrol refinery (Midia);
  - Constanța Nord, Constanța Sud, Eforie Sud and Mangalia;
  - the Constanța Port WWTP.
- Earlier NIMRD values (Black Sea Commission conference book 2013,
  [VLIZ PDF](https://www.vliz.be/imisdocs/publications/316785.pdf)):
  - TPH in water in 2012 "< 200 µg/L", lower than in 2006-2009;
  - Σ16 PAH in sediments deeper than 20 m (2011-2012) 82-6,983 µg/kg dry weight, mostly from combustion sources.
- Midia port sediments are "critical" for C>12 hydrocarbons, PAH and PCB (Catianis et al. 2016,
  doi:10.1515/geo-2016-0018; values NOT VERIFIED).

### 8.6 Coastal buoys (was: "units and QC of EUXRoCB0x?")
**Answered by our own checks: not usable.**
- The Copernicus In Situ copy shows the same faults as EMODnet, with QC flag 1/2:
  - EUXRoCB02 O2 median 5.2 "mmol m-3" and saturation at most 36 %;
  - EUXRoCB01 saturation median 17 %, with O2 drifting from 27 to 115 over Sep-Nov;
  - salinity about 7 at both.
- This is a sensor or calibration fault, not a units issue we can correct. We did not find public sensor
  documentation for these buoys.
- The NIMRD bulletins quote "NIMRD buoys" for SST, so NIMRD runs its own coastal buoys. That data is not in
  EMODnet or Copernicus.
- **Better source for the offshore buoys:** GeoEcoMar's own ERDDAP, `https://erddap.geoecomar.ro/erddap`, datasets
  `EUXRoOB01_2026`, `EUXRoOB02_2026` and `EUXRoOB03_2026` (also 2024 and 2025).
  - Checked live: data run to **2026-11-23 11:00 UTC**, against Sep 2026 in EMODnet.
  - DOXY units are "Micromoles per litre" (divide by 31.25 for mg/L); the sensor is an RBR Coda T.ODO at 3 m.
  - There is no QC flag on DOXY, and values of 500.0 are a range cap. Some single-point spikes exist.
  - Surface only, so these buoys cannot validate bottom O2.
  - Our modules do not wrap this server (one `requests` call to the tabledap CSV is enough).
- The coastal buoys CB01-03 came from the POC SMIS 125943 project (2021-2024). They are not on that server, and
  their sensor sheets are not public ([GeoEcoMar activity report 2024](https://geoecomar.ro/beta/wp-content/uploads/2025/06/GeoEcoMar-Raport-Activitate-2024.pdf)).

### 8.7 Mussel farms and shellfish areas (was: "locations and classification?")
**Answered (sector table in section 1).**
- Three ANSVSA class A production and relocation zones: Chituc-Perișor, Baia Mamaia, Agigea-Mangalia.
- One experimental long-line run by NIMRD and Maty Fish at the former Maricultura site.
- Biotoxin closures happen: June 2024 at Agigea and Mangalia.
- ANSVSA zone areas: Perișor-Chituc about 215, Năvodari-Port Constanța (Baia Mamaia) about 109, Agigea-Mangalia
  about 101 (units printed as "Mm2", probably km2)
  ([Newsweek RO, 2020](https://newsweek.ro/economie/autoritatile-au-stabilit-trei-zone-de-unde-pot-fi-exploatate-midii-si-vongole-din-marea-neagra)).
- NIMRD's 2019 E. coli survey points: Năvodari 44.3242 N 28.6456 E, Constanța 44.0843 N 28.6439 E, Mangalia
  43.7895 N 28.5869 E, all class A ([Art68 2020](https://www.animalsciencejournal.usamv.ro/pdf/2020/issue_1/Art68.pdf)).
- Agigea farm: "in front of the Agigea fishery, at 15 m depth"
  ([TVR, Oct 2025](https://tvrinfo.ro/specia-marina-care-s-a-aclimatizat-cu-succes-in-romania/)).
- ANAR leased 10 of 28 aquaculture perimeters in Dec 2024 (60 ha). The three mollusc perimeters are off Lake
  Siutghiol (Mamaia-Constanța), Agigea-Eforie Nord and Venus-2 Mai-Vama Veche
  ([Economedia](https://economedia.ro/?p=225348)).
- Rapana grounds: beam trawl at Cape Midia-Chituc on the 18-25 m isobaths, divers at Mangalia-Vama Veche
  3-12 m. Catch rose from 588 t (2012) to 6,504 t (2016)
  ([Danilov et al. 2018](https://animalsciencejournal.usamv.ro/pdf/2018/issue_2/Art48.pdf)).
- **For the map:** the exposure points for bottom-O2 indicator 1 are the Agigea farm at 15 m and the beam-trawl
  belt at 18-25 m. Both sit at the depth where the Constanța model cell (26 m) is representative.

### 8.8 What dying organisms and dead shells can tell us
**Tolerance thresholds** (literature; they support our 5 / 4 / 2 mg/L classes):

| Group or species | Evidence | Source |
|---|---|---|
| All benthos (meta-analysis) | LC50 mean 2.05, median 1.60 mg/L; 90 % of LC50 below 4.59; sublethal mean 2.61 mg/L (90 % below 5.0) | [Vaquer-Sunyer and Duarte 2008](https://doi.org/10.1073/pnas.0803833105) |
| Fish / crustaceans / bivalves / gastropods | mean LC50 1.54 / 2.45 / 1.42 / 0.89 mg/L; fish sublethal 4.41 mg/L | same |
| Sulphide | shortens survival under hypoxia by 30 % on average | [Vaquer-Sunyer and Duarte 2010, L&O](https://doi.org/10.4319/lo.2010.55.3.1075) |
| Warming | lethal threshold +0.07 mg/L per °C; survival time -74 % on average in warm treatments | [Vaquer-Sunyer and Duarte 2011, GCB](https://doi.org/10.1111/j.1365-2486.2010.02343.x) |
| Mytilus edulis, anoxia | LT90 16.7-19.9 days (cool water); larvae LT50 14-38 h | [Babarro and de Zwaan 2008](https://doi.org/10.1016/j.cbpa.2008.06.006); [Wang and Widdows 1991](https://doi.org/10.3354/meps070223) |
| M. galloprovincialis vs Chamelea | Chamelea gallina is the most anoxia-sensitive; M. galloprovincialis is intermediate | [de Zwaan et al. 2001](https://doi.org/10.3354/meps211169) |
| Turbot | growth and feeding reduced at 5.0 and 3.5 mg/L (17 °C) | [Pichavant et al. 2000](https://doi.org/10.1016/s0044-8486(00)00316-1) |
| In-situ community (Adriatic, 24 m) | deaths start below 0.5 mL/L (0.7 mg/L); molluscs survive longest, crustaceans and echinoderms die first | [Riedel et al. 2012](https://doi.org/10.3354/meps09724) |
| M. galloprovincialis, heat | mortality rises above 24 °C. Odesa, Jul-Aug 2010 at 29-30 °C: mussel biomass fell 95 % | [Anestis et al. 2007](https://doi.org/10.1152/ajpregu.00124.2007); [Govorin and Shatsillo](https://ruthenica.net/sites/default/files/2020-02/Vol22_101-110_Govorin_Shatsillo.pdf) |
| Low salinity | salinity below 8 caused mass mussel mortality at 1-3 m (Odesa 2023, Kakhovka dam breach) | [doi:10.71424/azb77.4.002933](https://doi.org/10.71424/azb77.4.002933) |
| Regulatory analogues | US EPA Virginian Province: 4.8 mg/L protects growth, below 2.3 mg/L survival is not protected. Chesapeake: 5 / 4 / 3 / 2.3 / 1.7 / 1 mg/L by use. OSPAR: 6 mg/L (5th percentile, Jul-Oct). HELCOM shallow water: 2 / 4 / 6 mg/L | [EPA 2000](https://www.waterboards.ca.gov/water_issues/programs/tmdl/records/state_board/2013/ref4080.pdf); [EPA 2003](https://19january2021snapshot.epa.gov/sites/static/files/documents/Executive_Summary.pdf); [OSPAR QSR 2023](https://oap.ospar.org/media/filer_public/e8/d1/e8d1668d-fdf7-49f0-a694-db1bb1100133/p00929_qsr2023_dissolved_oxygen.pdf); [HELCOM](https://indicators.helcom.fi/indicator/shallow-water-oxygen) |

What this means for the dashboard:
- **Class D (< 2 mg/L)** kills fish and crustaceans within hours to days.
- **Mussels survive days to weeks** of anoxia. Mussel-bed mortality therefore depends on **how many consecutive
  days** stay low, plus temperature and sulphide, not on a single day. We add the longest run of consecutive
  days below 2 and below 4 mg/L to indicator 1 (C1 output).
- Above about 24 °C, heat alone stresses Mytilus. A summer with bottom T > 24 °C and O2 < 4 mg/L is the
  worst case.
- A sudden salinity drop below about 8 also kills shallow mussels. Danube floods can do this on the northern
  coast.

**Dead shells as evidence.**
- **Shell beds and death assemblages are time-averaged.** Shells on shelves typically span centuries to
  millennia, so a shell layer cannot be tied to an event without dating (radiocarbon, amino-acid racemisation,
  210Pb). In the Adriatic, dating 311 Corbula gibba shells reconstructed repeated hypoxia over about 500 years
  ([Tomašových et al. 2017, Geology](https://doi.org/10.1130/g38676.1)). Hypoxia-sensitive species were lost
  in the 20th century ([PLoS ONE 2017](https://doi.org/10.1371/journal.pone.0180820)).
- **Shell chemistry records oxygen.** In Baltic bivalves, Mn/Ca correlates with bottom O2 at r = -0.66 to -0.75
  (error about ±1.5 mL/L) ([Frontiers 2022](https://doi.org/10.3389/fmars.2022.820731);
  [ECSS 2021](https://doi.org/10.1016/j.ecss.2021.107257)). Mn-rich growth disturbance lines mark events below
  about 45 µmol/L ([Frontiers 2023](https://doi.org/10.3389/fmars.2023.1219716)). No Black Sea mussel-shell
  O2 reconstruction was found. **This is a research opportunity:** NIMRD's Mytilus archive plus Mn/Ca could
  date the hypoxia history of the Romanian beds.
- **Fresh beach strandings: tell hypoxia from storms.**
  - Hypoxia kill: calm, warm, stratified weeks; mixed species; fish, crabs and gaping bivalves with tissue still
    inside; often a bloom or upwelling just before; dead animals smell of H2S.
  - Storm stranding: high waves; mostly live or freshly torn-up Rapana and mussels; no fish kill; cold water.
  - The January 2026 Vadu "carpet" fits the storm pattern.
  - Dashboard rule: show a stranding report only when it coincides with an O2 class C or D episode at the
    nearest model cell and the previous 7 days had Hs < 1 m (the wave data are in `physical.md`).
- **Jellyfish and dolphin strandings** (Rhizostoma in Sep 2025; a record 266 dolphins by Sep 2026, cause
  unknown) are biological signals. The biological session owns them; they are not O2 evidence on their own.

### 8.9 What still needs NIMRD (one short email after the hackathon)
1. Station-level data for 2018-2025 (or at least the 2024-2025 bottom-O2 casts) to validate the forecast
   model's low tail and its autumn and winter low-O2 episodes.
2. Exact coordinates of the experimental mussel long-line and the CreAZA allocated aquaculture zones.
3. Confirmation of the D5C5 wording, so we can show "failed on saturation" with confidence.
4. Whether NIMRD's own coastal buoys (quoted in the 2025 bulletins) have an open data feed.

---

## 9. Sources

Data and products (all checked live 2026-11-23):
- Copernicus Marine BGC analysis/forecast BLKSEA_ANALYSISFORECAST_BGC_007_010, DOI
  [10.48670/mds-00354](https://doi.org/10.48670/mds-00354); quality document
  [CMEMS-BLK-QUID-007-010 issue 6.0, approved 18/11/2025](https://documentation.marine.copernicus.eu/QUID/CMEMS-BLK-QUID-007-010.pdf).
- Copernicus Marine BGC reanalysis BLKSEA_MULTIYEAR_BGC_007_005, DOI [10.48670/mds-00372](https://doi.org/10.48670/mds-00372).
- Copernicus Marine physics analysis/forecast, DOI [10.48670/mds-00355](https://doi.org/10.48670/mds-00355);
  ocean colour L4 MY, DOI [10.48670/moi-00304](https://doi.org/10.48670/moi-00304).
- EMODnet Chemistry, Eutrophication v2025 Black Sea aggregated dataset (`EUT_BLACKSEA_PROFILES`,
  [ERDDAP](https://erddap.emodnet-chemistry.eu/erddap/tabledap/EUT_BLACKSEA_PROFILES.html)); DIVAnd Danube-Delta
  and Black-Sea seasonal products on [erddap.emodnet.eu](https://erddap.emodnet.eu/erddap/).
- EMODnet Physics / Copernicus In Situ TAC platforms EUXRo01-03, EUXRoOB01-03, EUXRoCB01-03 (GeoEcoMar).
- EMODnet Human Activities, bathing waters (EEA BWD) layer `emodnet:bathingwaters`.
- GloFAS / Open-Meteo Danube discharge via `open_data.danube_discharge`.

Literature and official reports (links checked 2026-11-23 by our literature agents; items marked NOT VERIFIED in
the text were not confirmed):
- INCDM "Grigore Antipa" (2024). *Studiu pentru elaborarea raportului national privind starea ecologica a
  ecosistemului marin Marea Neagra conform art. 17 DCSMM*. Ministry of Environment, Romania.
  [PDF](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf). **Key source** for the
  official thresholds (Table III.7.1) and 2018-2023 status.
- Lazăr L. et al. (2019). Black Sea eutrophication status: the integrated assessment, limitations and obstacles.
  *Cercetări Marine* 49:57-74. [link](http://www.marine-research-journal.org/index.php/cmrm/article/view/142)
- Lazăr L. et al. (2024). *Sustainability* 16:5146 (BEAST 2020-2022). [doi:10.3390/su16125146](https://doi.org/10.3390/su16125146)
- Ristea E. et al. (2025). *Sustainability* 17:1090 (NIMRD 1960-2023 trends). [doi:10.3390/su17031090](https://doi.org/10.3390/su17031090)
- Capet A., Beckers J.-M., Grégoire M. (2013). Drivers, mechanisms and long-term variability of seasonal hypoxia
  on the Black Sea northwestern shelf. *Biogeosciences* 10:3943-3962. [doi:10.5194/bg-10-3943-2013](https://doi.org/10.5194/bg-10-3943-2013)
- Capet A. et al. (2016). Decline of the Black Sea oxygen inventory. *Biogeosciences* 13:1287-1297.
  [doi:10.5194/bg-13-1287-2016](https://doi.org/10.5194/bg-13-1287-2016)
- Capet A., Vandenbulcke L., Grégoire M. (2018). Copernicus Ocean State Report 2, Black Sea oxygen.
  [doi:10.1080/1755876X.2018.1489208](https://doi.org/10.1080/1755876X.2018.1489208)
- Mee L. et al. (2005). Restoring the Black Sea in times of uncertainty. *Oceanography* 18(2).
  [doi:10.5670/oceanog.2005.45](https://doi.org/10.5670/oceanog.2005.45)
- Oguz T. (2005). Long-term impacts of anthropogenic forcing on the Black Sea ecosystem. *Oceanography* 18(2):112-121.
  [doi:10.5670/oceanog.2005.46](https://doi.org/10.5670/oceanog.2005.46)
- Oguz T., Velikova V. (2010). *MEPS* 405:231-242. [doi:10.3354/meps08538](https://doi.org/10.3354/meps08538)
- Cociașu A. et al. (1996). *Mar. Pollut. Bull.* 32(1):32-38. [doi:10.1016/0025-326X(95)00106-W](https://doi.org/10.1016/0025-326X(95)00106-W)
- Humborg C. et al. (1997). *Nature* 386:385-388. [doi:10.1038/386385a0](https://doi.org/10.1038/386385a0)
- Kideys A. (2002). *Science* 297:1482. [doi:10.1126/science.1073002](https://doi.org/10.1126/science.1073002)
- Zaitsev Yu. (1992). *Fish. Oceanogr.* 1(2). [doi:10.1111/j.1365-2419.1992.tb00036.x](https://doi.org/10.1111/j.1365-2419.1992.tb00036.x)
- Friedrich J. et al. (2014). *Biogeosciences* 11:1215. [doi:10.5194/bg-11-1215-2014](https://doi.org/10.5194/bg-11-1215-2014)
- Schrimpf W. et al. (2008). JRC33363. [link](https://publications.jrc.ec.europa.eu/repository/handle/JRC33363)
- Kovács A., Závadsky I. (2021). *Water International* 46:176-194. [doi:10.1080/02508060.2021.1891703](https://doi.org/10.1080/02508060.2021.1891703)
- Konovalov S., Murray J., Luther G. (2005). Basic processes of Black Sea biogeochemistry. *Oceanography* 18(2).
  [link](https://tos.org/oceanography/article/basic-processes-of-black-sea-biogeochemistry)
- Stanev E. et al. (2018). *GRL* 45. [doi:10.1002/2017GL076206](https://doi.org/10.1002/2017GL076206)
- Kondratev S. et al. (2017). Alkalinity of the NW Black Sea. [doi:10.22449/1573-160X-2017-4-35-45](https://doi.org/10.22449/1573-160X-2017-4-35-45)
- Grégoire M. et al. (2023). EO4SIBS. *Front. Mar. Sci.* 9:998970. [doi:10.3389/fmars.2022.998970](https://doi.org/10.3389/fmars.2022.998970)
- Oros A. et al. (2025). *Water* 17:2406. [doi:10.3390/w17162406](https://doi.org/10.3390/w17162406)
- Damir N. et al. (2024). *Fishes* 9:274. [doi:10.3390/fishes9070274](https://doi.org/10.3390/fishes9070274)
- Vaquer-Sunyer R., Duarte C. (2008). *PNAS* 105:15452. [doi:10.1073/pnas.0803833105](https://doi.org/10.1073/pnas.0803833105)
- Diaz R., Rosenberg R. (2008). *Science* 321:926. [doi:10.1126/science.1156401](https://doi.org/10.1126/science.1156401)
- Andersen J. et al. (2017). HEAT 3.0. *Biol. Rev.* 92:135-149. [doi:10.1111/brv.12221](https://doi.org/10.1111/brv.12221)
- Garcia H., Gordon L. (1992). Oxygen solubility in seawater. *Limnol. Oceanogr.* 37:1307. [doi:10.4319/lo.1992.37.6.1307](https://doi.org/10.4319/lo.1992.37.6.1307)
- Niță V. et al. (2019). Romanian mussel aquaculture. [PDF](https://animalsciencejournal.usamv.ro/pdf/2019/issue_2/Art58.pdf)
- EU law: Directive 2006/7/EC (bathing water), Directive 2013/39/EU (EQS), Regulation (EU) 2023/915 (food
  contaminants), Decision (EU) 2017/848 (MSFD criteria); EEA Romania bathing-water factsheet 2025 (links in 2.7, 2.8).
- Not reachable today: Black Sea Commission SoE reports (2008, 2009-2014), ICPDR load data, NIMRD annual report 2024.
- Added in the research round (section 8, all opened 2026-11-23):
  - NIMRD, MSFD 2018 study ([PDF](https://mmediu.ro/app/webroot/uploads/files/STUDIU%20MSFD%20V1.9.pdf)).
  - Lazăr et al. 2012, Geo-Eco-Marina 18 ([PDF](https://zenodo.org/records/56875/files/09_lazar_BT.pdf)).
  - Oros et al. 2024, Cercetări Marine 54 ([PDF](https://www.marine-research-journal.org/index.php/cmrm/article/download/283/220)).
  - NIMRD 2025 bathing bulletins ([Info-2025.07.14](https://www.nimrd.ro/uploads/Info-2025.07.14.pdf)).
  - Copernicus QUID 007-005 ([PDF](https://documentation.marine.copernicus.eu/QUID/CMEMS-BLK-QUID-007-005.pdf)).
  - GeoEcoMar ERDDAP (https://erddap.geoecomar.ro/erddap).
  - Danilov et al. 2018, Rapana grounds ([PDF](https://animalsciencejournal.usamv.ro/pdf/2018/issue_2/Art48.pdf)).
  - Organism-tolerance and shell-proxy papers (table in 8.8).
