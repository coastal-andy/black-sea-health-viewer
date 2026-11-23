# Biological indicators: Romanian Black Sea shelf

Part of Challenge 04 "Ecosystem Health" (see [CHALLENGE_04.md](../challenge/CHALLENGE_04.md)). Sibling documents: `physical.md` and `chemical.md`.

**Purpose.** The jury says an environmental anomaly is not automatically ecological damage, and asks what biological evidence is needed. This document lists:
- which biological indicators matter on the Romanian shelf;
- what their normal values and reference conditions are;
- which of them we can actually compute from data we can fetch;
- how the dashboard should label each one honestly (measured, proxy, or needs a field survey).

**Verified.** Every number marked "(check)" was computed live at Constanța (44.17 N, 28.72 E) on 2026-11-23 by [`scripts/indicators/biological_check.py`](../../scripts/indicators/biological_check.py). Its output is in [`biological_check_output.txt`](../../scripts/indicators/biological_check_output.txt). Once the cache is warm the script runs in about 3 s; the first run takes about 1 min.

**Status labels used throughout:**

| Label | Meaning |
|---|---|
| **OFFICIAL-EU** | Adopted in EU law: the WFD intercalibration Decision (EU) 2024/721, or Commission Decision 2017/848 for the MSFD. |
| **OFFICIAL-RO** | Romania's thresholds and results in its MSFD reporting. The main source is the 2024 study by NIMRD (the Grigore Antipa institute), RO-MSFD-2024 (data 2018-2023), [PDF](https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf). Most of these thresholds were set nationally by expert judgement; the EU did not adopt them. |
| **LIT** | Values from a paper or report. The source is linked. |
| **OURS** | Proposed by our team for the dashboard. Not an official threshold. |

---

## 1. Ranked shortlist for the dashboard

The full formulas and audience texts are in section 4. "Status" means the indicator was computed at Constanța today.

| # | Indicator | Data key | Evidence type | Confidence | Status |
|---|---|---|---|---|---|
| B1 | Chl-a anomaly in log space against the 1998-2020 day-of-year climatology, plus the official D5C2 test | `sat_chl_l4_nrt` + `sat_chl_l4_my` (cross-check: `open_data.chl_occi_8day`) | satellite, measured proxy of phytoplankton biomass | high offshore, medium in the coastal strip | computed |
| B2 | Bloom days per season and per year, with long-term trend | `sat_chl_l4_my` (1998 onward) | satellite, derived | medium | computed (28 years) |
| B3 | Phytoplankton community structure: satellite micro-size share now, NIMRD diatom/dinoflagellate counts historically | `sat_pft_l3_my` / `sat_pft_l3_nrt` + OBIS NIMRD counts | satellite proxy + in-situ archive | low (satellite), high but historical (in-situ, to 2015) | computed |
| B4 | Primary production anomaly, satellite vs model | `sat_pp_my` / `sat_pp_nrt` + `rea_bgc_o2` / `bgc_o2` `npp` | satellite + model | medium (satellite), low (model at the coast) | computed (2024; climatology 1998-2022 works) |
| B5 | Mussel-bed hypoxia exposure: bottom-O2 class days (A-D, shared with the chemical session) and the official D5C5 seasonal test at NIMRD Mytilus-reef stations | `rea_bgc_o2` / `bgc_o2` `o2_bottom` + `rea_phy_temp` `bottom_temp` + `rea_phy_sal` + OBIS station positions + `depth_at` | model, a habitat-exposure proxy | medium-low | computed (2010-2024) |
| B6 | Non-indigenous and gelatinous species: occurrence evidence (presence, last record, records since 2015) | OBIS API, Romanian box | occurrence records, biased by sampling effort | low for trends, good for presence | computed |
| B7 | Biological evidence coverage and "investigate" layer: EurOBIS record grid, strandings, ROV habitat labels | `emodnet_layers.biology_records_grid`, OBIS, `vision.py` | evidence map | n/a (shows where evidence exists) | computed (grid, strandings); ROV needs footage |

Recommended dashboard set:
- **Core biology tab:** B1, B2, B5 and B6.
- **Context and "what to check next":** B3, B4 and B7.

---

## 2. What the data can actually give (checked live 2026-11-23)

### 2.1 Copernicus Marine (via `src/marinekit/sources/copernicus.py`)

| Need | Dataset (key) | Variables actually present | Notes |
|---|---|---|---|
| Chl-a, long record | `cmems_obs-oc_blk_bgc-plankton_my_l4-gapfree-multi-1km_P1D` (`sat_chl_l4_my`) | CHL only | 10,202 daily values 1998-2025 at the cell 0.39 km from Constanța (check) |
| Chl-a, near real time | `..._nrt_l4-gapfree-multi-1km_P1D` (`sat_chl_l4_nrt`) | CHL | rolling window of about 3 weeks |
| **Phytoplankton size classes** | `cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D` (OCEANCOLOUR_BLK_BGC_L3_MY_009_153) | **CHL, MICRO, NANO, PICO** (mg m-3), QI_CHL | CATALOG keys `sat_pft_l3_my` and `sat_pft_l3_nrt` (NRT twin `cmems_obs-oc_blk_bgc-plankton_nrt_l3-multi-1km_P1D`, DOI 10.48670/moi-00301). The L4 and OLCI-300 m datasets have CHL only. In the NRT values of 19-20 Nov 2026, NANO equals PICO exactly; check before using the split. These are **size classes, not taxonomic groups**: diatoms and large dinoflagellates both fall into MICRO, and coccolithophores into NANO. |
| Primary production | `cmems_obs-oc_blk_bgc-pp_my_l4-multi-4km_P1D` (L4_MY_009_154, DOI 10.48670/moi-00304) | PP (g C m-2 d-1) | CATALOG keys `sat_pp_my` and `sat_pp_nrt` (NRT twin `cmems_obs-oc_blk_bgc-pp_nrt_l4-multi-4km_P1D`, DOI 10.48670/moi-00302). `climatology("sat_pp_nrt", ...)` works (1998-2022): monthly means 0.24 g C m-2 d-1 (Dec) to 1.39 (Jun). |
| Model plankton | `bgc_chl` (anfc 2024 onward): chl, phyc, zooc. `rea_bgc_chl` (1992-2024): chl, phyc | no functional types | The published BAMHBI output has **no diatom / flagellate / gelatinous split**. `zooc` exists only in the forecast product. |
| Model NPP, bottom O2 | `bgc_o2`, `rea_bgc_o2`: nppv, o2, o2b | | used for B4 and B5 |

### 2.2 ESA OC-CCI via `open_data.py`
- `chl_occi_8day` (1997 onward) gives an independent product for the climatology and anomaly cross-check.
- At Constanța the 8-day pixel lies 2.1 km from the point (check).

### 2.3 OBIS and EMODnet Biology

OBIS API (`https://api.obis.org/v3`), Romanian box 28.4-30.6 E, 43.6-45.4 N:
- **325,159 records, 1,369 species, 110 datasets, 1927-2026.**
- Occurrence records can be pulled with coordinates and dates. Pages of 5,000 records with measurement-or-fact data take about 4-7 s.

The largest datasets are NIMRD's (via EurOBIS):
- "Romanian Black Sea Zooplankton data" (1956-2015): 58k + 29k + 13k + 12k + 9k records across its periods;
- "Romanian Black Sea Phytoplankton data" (1956-2015): 24k + 21k + 16k + 8k + 7k records.

The phytoplankton records carry **abundance in cells per litre**, from Niskin samples at standard depths. That makes historical bloom counts and diatom/dinoflagellate shares off Constanța computable (B3).

**Counts per taxon in the Romanian box** (check; records / datasets / year range / records since 2015):

| Taxon | Group | Records | Datasets | Years | Since 2015 | Main providers |
|---|---|---|---|---|---|---|
| *Mnemiopsis leidyi* | NIS ctenophore | 624 | 10 | 1991-2025 | 8 | NIMRD zooplankton 1981-2010 (564) |
| *Beroe ovata* | NIS ctenophore | 95 | 11 | 1997-2023 | 18 | |
| *Rapana venosa* | NIS gastropod | 148 | 6 | 2006-2026 | 142 | iNaturalist (117), 62 within about 20 km of Constanța |
| *Mya arenaria* | NIS bivalve | 555 | 12 | 1977-2026 | 72 | |
| *Anadara kagoshimensis* | NIS bivalve | 127 | 5 | 1985-2026 | 84 | |
| *Rhithropanopeus harrisii* | NIS crab | 4 | 2 | 2006-2025 | 3 | |
| *Acartia tonsa* | NIS copepod | 65 | 6 | 2003-2021 | 13 | |
| *Aurelia aurita* | jellyfish | 464 | 13 | 1956-2026 | 40 | |
| *Rhizostoma pulmo* | jellyfish | 83 | 1 | 2013-2026 | 82 | |
| *Noctiluca scintillans* | dinoflagellate | 3,850 | 20 | 1952-2021 | 71 | |
| *Emiliania huxleyi* | coccolithophore | 2,797 | 20 | 1957-2019 | | |
| *Skeletonema costatum* | diatom | 4,131 | 17 | 1957-2016 | | |
| *Prorocentrum cordatum* (= *P. minimum*) | dinoflagellate | 4,973 | 20 | 1956-2019 | | |
| *Pseudo-nitzschia* spp. | diatom | 3,107 | 17 | 1956-2019 | | |
| *Mytilus galloprovincialis* | mussel | 765 | 14 | 1954-2026 | 57 | NIMRD (284), GeoEcoMar (236); 713 records have depth: median 34 m, 10-90% range 20-52 m |
| *Modiolula phaseolina* | mussel | 460 | 10 | 1954-2017 | 2 | |
| *Zostera noltei* | seagrass | 10 | 2 | 2023-2024 | 10 | SeagrassSpotter only. *Zostera marina*: 0 |
| *Gongolaria* / *Cystoseira barbata* | brown alga | 1 | 1 | none | 0 | the name *Gongolaria barbata* is not found in OBIS |
| *Phyllophora crispa* | red alga | 2 | 1 | none | 0 | |
| *Ulva* / *Cladophora* | green algae | 5 / 17 | 1 | none | 0 | |
| *Phocoena phocoena* | porpoise | 686 | 13 | 2004-2026 | 317 | Mare Nostrum strandings 2010-2016 (411) |
| *Tursiops truncatus* | dolphin | 263 | 11 | 2003-2025 | 149 | |
| *Delphinus delphis* | dolphin | 92 | 10 | 2003-2026 | 38 | |
| *Sprattus sprattus* / *Engraulis* / turbot (*Scophthalmus maeoticus*) | fish | 17 / 29 / 3 | | | | **OBIS is useless for fish stocks** |

**EMODnet Biology** (`biology_records_grid`, EurOBIS 15-minute grid):
- 68 cells in BBOX_RO, 293,220 records; median 1,222 records per cell, maximum 30,633 (check).
- This map shows **sampling effort**, not abundance.

**What OBIS/EMODnet cannot give:**
- **Macrophytes.** *Zostera*, *Cystoseira*/*Gongolaria*, *Phyllophora*, *Ulva* and *Cladophora* are almost absent: NIMRD macroalgae monitoring is not published there.
- **Fish stocks.**
- **Biomass time series after about 2015.** The NIMRD plankton series in OBIS stop at 2015, and benthos records are sparse after 2017.

---

## 3. Indicators by group

Each group covers:
- why it matters, with the effect on each sector: Ports (ports and logistics), Ship (shipyards and marine engineering), Tour (tourism), Fish (fishing) and Aqua (aquaculture);
- typical values and long-term change;
- thresholds;
- natural versus human-caused change, and what to check first;
- whether it can be measured remotely or needs a field survey.

### 3.1 Phytoplankton: chlorophyll-a, blooms, functional types, primary production

**Why it matters.** Phytoplankton respond first to nutrient load, which is MSFD D5 eutrophication. Too much biomass leads to:
- organic matter sinking to the bottom;
- bottom hypoxia, which kills mussel beds;
- murky water;
- loss of seagrass and *Cystoseira*.

Some bloom species are harmful or nuisance species:
- *Prorocentrum cordatum*, *Pseudo-nitzschia* (domoic acid) and *Dinophysis* (shellfish toxins);
- *Noctiluca* (red tides, smell);
- *Emiliania huxleyi* (milky turquoise water).

Effect on each sector:
- **Aqua:** toxin and closure risk for mussel farms; low oxygen after blooms.
- **Tour:** discoloured water, foam, smell, and bathing-water complaints in July and August.
- **Fish:** blooms are the base of the sprat and anchovy food web. Too much biomass leads to hypoxia; too little means poor recruitment.
- **Ports:** dredging and ballast water can move cysts of harmful species.
- **Ship:** fouling and biofilm grow faster in eutrophic water (minor).

**Typical values and seasonal cycle near Constanța.**

From the satellite record (check, `sat_chl_l4_my` 1998-2025, geometric means in mg m-3):
- Jan 2.3, Feb 2.3, Mar 2.5, Apr 2.8, **May 4.0**, Jun 3.1, Jul 1.9, Aug 2.0, Sep 1.9, Oct 2.6, Nov 2.6, Dec 1.8.
- Day-of-year climatology 1998-2020: mid-May geometric mean 4.1, with a 90th percentile of 16.1. Mid-January: 2.25 (90th percentile 4.3).

In-situ values:
- Mamaia Bay 2002-2010: 0.17 to 76 µg/L ([Vasiliu et al. 2012](https://doi.org/10.12681/mms.301)).
- Inner shelf 2009 means: Feb 6.2, May 9.5, Jul 5.5, Sep 10.3 µg/L ([Vasiliu et al. 2010](https://geoecomar.ro/website/publicatii/Nr.16-2010/02_vasiliu_fin.pdf)).

The cycle has:
- a late-winter diatom peak;
- a stronger April-May peak driven by the Danube flood;
- a July minimum;
- a September-October peak.

The satellite and in-situ shapes agree. The satellite autumn peak is weaker.

**Long-term change** (LIT, Bodeanu in [Bologa et al. 1995, CIESM](https://ciesm.org/online/monographs/CSS-1/CSS_1_85_110.pdf)), Romanian shelf:
- Mean phytoplankton biomass rose from 495 mg m-3 (1959-63) to 4,105 mg m-3 (1983-90).
- There were 46 blooms of 15 species in 1981-90.
- The diatom share of cell numbers fell from 92% to 38%.

Bloom maxima in the 1980s, with the 1960s value in brackets:

| Species | 1980s maximum (cells/L) | 1960s maximum (cells/L) |
|---|---|---|
| *P. cordatum* | 808 million | 51 million |
| *E. huxleyi* | 291 million | 95 thousand |
| *Skeletonema* | 141 million | 18 million |

After about 1990 single-species blooms became fewer and diatoms came back:
- only one bloom above 10 million cells/L in 2006-2011 ([Lazăr et al. 2013](https://www.marine-research-journal.org/index.php/cmrm/article/view/115));
- basin primary production went from below 100 g C m-2 yr-1 before the 1970s to 300-500 during eutrophication (Oguz 2005, *Oceanography* 18(2)).

Our own numbers (check):
- **Satellite 1998-2025:** the Theil-Sen trend of annual geometric-mean chl is **-1.3% per year**. The 1998-2007 mean was 2.69 and the 2016-2025 mean 2.12 mg m-3.
- **Bloom days:** the relative count (above the day-of-year 90th percentile) falls by 0.8 days per year. The absolute count (above 10 mg m-3) falls by 0.6 days per year. Ranges: 10-70 and 2-45 days per year.
- **2021-2025:** 8.2% of days were above the 90th percentile (10% expected) and 13.9% below the 10th percentile. This slightly favours low values.
- **NIMRD counts in OBIS** (surface samples within about 15 km of Constanța, 452 samples 1961-2015): the median diatom share of cells is in the table below. Samples above 1 million cells/L occur in every decade.

| Decade | Median diatom share of cells |
|---|---|
| 1960s | 0.98 |
| 1970s | 0.66 |
| 1980s | 0.71 |
| 1990s | 0.84 |
| 2000s | 0.86 |

- **Bloom-forming taxa** (records with more than 1 million cells/L): *Skeletonema costatum* 41, *Cerataulina* 20, *Prorocentrum cordatum* 19, *Cyclotella* spp. 17, *Chaetoceros socialis* 6 and *Pseudo-nitzschia delicatissima* 5.
- This repeats the published story: a diatom-dominated baseline, a dinoflagellate shift in the 1970s-80s, and partial recovery after 1990.
- Caveat: only 7 samples come from the 2010s.

**Thresholds:**

| Criterion | Value | Status |
|---|---|---|
| D5C2 chl-a, 75th percentile of May-Sep, euphotic layer | transitional 11.88, **coastal (Periboina to Vama Veche, includes Constanța) 5.97**, shelf north 4.11, shelf south 2.79 µg/L. 2018-2023 in-situ 75th percentiles 10.25 / 4.9 / 1.86 / 0.69, so all good | OFFICIAL-RO (RO-MSFD-2024 Table III.7.1; [Lazăr et al. 2019](https://www.marine-research-journal.org/index.php/cmrm/article/view/142)) |
| Phytoplankton biomass, warm-season 90th percentile | coastal and marine 950, transitional 3,000 mg m-3. In 2018-2023 the target was exceeded in 75% of coastal and 77% of marine samples | OFFICIAL-RO (D1 pelagic habitats) |
| D5C3 *Noctiluca* biomass, warm season | 350 mg m-3 coastal, 240 transitional and marine | OFFICIAL-RO |
| D4 diatom/dinoflagellate ratio | used officially; not in good status in all areas (2020-21) | OFFICIAL-RO (RO-MSFD-2024 ch. IV.3) |
| WFD phytoplankton index IBI (Ecological Quality Ratio), coastal type CW-BL1. Note: in the Danube basin plan 2021-2027, the Romanian natural coastal water bodies are in poor ecological status (RO-MSFD-2024 p. 143) | High/Good 0.80, Good/Moderate 0.63 (transitional 0.70 / 0.42). The decision gives no chl values | OFFICIAL-EU ([Decision 2024/721](https://eur-lex.europa.eu/eli/dec/2024/721/oj)) |
| Bloom | above 1 million cells/L for one species, or above 5 million for 2-3 species, or biomass above 10,000 mg m-3 | LIT (Black Sea Commission manual, [Moncheva and Parr](http://www.blackseacommission.org/Downloads/Phytoplankton_%20Mannual-Final-1.pdf)); NIMRD uses 1 million cells/L |
| Satellite bloom day | chl above the day-of-year 90th percentile (1998-2020), or above 10 mg m-3 | OURS |

**D5C2 proxy from satellite** (check):
- The satellite May-September 75th percentile at Constanța exceeded 5.97 in 1999, 2001, 2002, 2006 and 2010, and in no year since 2011.
- The pooled 2018-2023 value is 3.2 µg/L, below NIMRD's in-situ 4.9. At this pixel the satellite reads lower than the bottle samples, not higher.

**Natural versus human-caused.** The Danube dominates.

Annual geometric-mean chl at Constanța against GloFAS Danube discharge (check, 1998-2025):

| Pair compared | Spearman rho |
|---|---|
| Annual chl vs annual discharge | **+0.79** |
| Absolute bloom days vs annual discharge | +0.73 |
| Spring chl vs February-May discharge | +0.44 |

- **2025** had the lowest chl in the record (1.60 mg m-3; OC-CCI summer values were 0.2-0.7 times normal). It was also one of the three lowest discharge years (5,038 m3/s).
- So **a low-chl year is first a dry-river year, not a recovery signal**. A bloom after a flood is mostly natural plus the nutrient load the river carries.

Check in this order:
1. Danube discharge, including the previous 1-2 months (`open_data.danube_discharge`).
2. Salinity, as plume extent (`phy_sal`).
3. SST and mixed-layer depth: warm, stratified summers favour dinoflagellates, *Noctiluca* and *E. huxleyi* (`sst_*`, `phy_mld`).
4. Wind and upwelling (`marine_weather`).
5. Then nutrients (`bgc_nut`, chemical session).

A human signal is left when chl stays high after these are accounted for. One test is the residual of log(chl) regressed on log(discharge).

**Remote versus field:**
- Chl, size classes and PP are satellite.
- Species, toxins, cell counts and the diatom/dinoflagellate ratio need Niskin samples and microscopy, or an imaging flow cytometer.
- Satellite chl in the turbid Danube strip is biased by sediment and dissolved organic matter (CDOM). Use anomalies, not absolute values, within about 10 km of the coast.
- Satellite size classes (check): the MICRO share is 0.68-0.93 all year at Constanța in both 2005 and 2024. It drops only in summer. The algorithm is tuned for open water and saturates in coastal water. Treat it as low confidence and **never label it "diatoms"**.

### 3.2 Zooplankton and gelatinous species

**Why it matters.**
- ***Mnemiopsis leidyi*** arrived in ballast water in the early 1980s. It ate fish eggs, larvae and fodder zooplankton, and contributed to the 1989 anchovy collapse:
  - Black Sea anchovy catch: 295 kt (1988), 97 kt (1989), 66 kt (1990) (Kideys 1994, *J. Mar. Syst.* 5:171).
  - Mnemiopsis peak in 1989: 1.5-2.5 kg wet weight m-2 ([Kideys 2005](https://tos.org/oceanography/assets/docs/18-2_kideys.pdf); [Daskalov 2002](https://doi.org/10.3354/meps225053)).
- ***Beroe ovata*** arrived in about 1997. It eats *Mnemiopsis* and keeps its peaks to 1-2 months in late summer.
- ***Aurelia*** and ***Rhizostoma*** cause beach nuisance and clog intake screens. ***Noctiluca*** causes red tides.
- **Fodder zooplankton** (copepods) is the food of sprat and anchovy.

Effect on each sector:
- **Tour:** jellyfish swarms on beaches, July-September.
- **Fish:** competition with fish for food and predation on fish eggs; nets clogged.
- **Ports:** the ballast-water vector; cooling-water intakes clogged.
- **Ship:** cooling-water intakes clogged.
- **Aqua:** jellyfish damage to cages and lines.

**Values and change** (LIT):
- Romanian shelf mean wet biomass 2010-2013: *Mnemiopsis* 3.3 g m-3, *Beroe* 0.4, *Aurelia* 6.1, *Pleurobrachia* 0.33 ([Harcotă et al. 2017](https://www.marine-research-journal.org/index.php/cmrm/article/view/62)).
- *Noctiluca* made up 91-100% of summer zooplankton biomass in 1980-91. Its August 1987 peak near Constanța was 164 g m-3; the 2015-2017 maximum was 2.5 g m-3.
- In 1988 fodder zooplankton was only 2% of total zooplankton biomass.

**Thresholds** (OFFICIAL-RO, RO-MSFD-2018/2024):

| Criterion | Value | Recent result |
|---|---|---|
| *Mnemiopsis* biomass | at most 4 g m-3 | 2018-2023 good status overall: 245 of 278 stations pass |
| Warm-season fodder zooplankton | above 240 / 210 / 70 mg m-3 (transitional / coastal / marine) | failed everywhere in 2012-2017 |
| Copepods | above 45 / 65 / 45 mg m-3 | in good status only in marine waters in 2018-2023 |
| Zooplankton Shannon index (D4) | above 3 | fails everywhere |

**Natural versus human-caused:**
- Gelatinous blooms follow warm summers and calm, stratified water. *Mnemiopsis* reproduces above about 20 °C.
- Check SST anomaly and mixed-layer depth first (physical session).
- The human drivers are eutrophication (more food), overfishing of plankton-eating fish (less competition) and ballast water (introduction).

**Remote versus field:**
- None of these can be seen from satellite.
- The model's `zooc` (total zooplankton carbon, forecast only) does not resolve gelatinous species.
- The evidence is net tows (NIMRD), beach and citizen reports (iNaturalist and Observation.org reach OBIS, with *Rhizostoma* records from 2013 to 2026), and ROV or camera footage.

### 3.3 Benthic habitats

**Why it matters.** Benthic habitats integrate months to years of conditions. A mussel bed that dies is real ecological damage; a chl anomaly is not.

| Habitat | Role and state |
|---|---|
| ***Mytilus galloprovincialis*** beds (35-60 m) | Filter the water, are a habitat themselves, and are the Romanian mussel fishery (317 t in 2023) and aquaculture seed. They die en masse under late-summer bottom hypoxia. |
| ***Modiolula phaseolina*** beds (55-100 m) | |
| ***Zostera noltei*** meadows | Nursery, sediment stabiliser. Gone from the Romanian coast in the 1980s. One Mangalia bed grew from 940 m2 (2010) to 1,132 m2 (2020), biomass 438-1,325 g m-2 ([Surugiu et al. 2021](https://doi.org/10.3389/fmars.2021.745137)). |
| ***Gongolaria*** (*Cystoseira*) ***barbata*** forests | Lost about 80% after the 1971-72 sea ice and eutrophication. Recovering from Mangalia to Vama Veche since the 2000s: 5,000-9,000 g m-2 in 2016. |
| ***Phyllophora*** (Zernov's field) | 10,000 km2 in the 1950s, about 3,000 in 1980, 50 km2 by 1990. Only small patches remain in Romanian waters (protected site ROSCI0413). |
| Opportunistic ***Ulva*** and ***Cladophora*** | A sign of eutrophication. 2009-2021 ranges 5-2,510 and 3-2,800 g m-2; *Cladophora* surged in 2010 and again from 2019 ([Marin 2022](https://doi.org/10.55268/CM.2022.52.78)). |

Effect on each sector:
- **Aqua:** bed health equals farm health; hypoxia equals mortality.
- **Fish:** mussel dredging, and turbot and goby habitat.
- **Ship:** coastal works, dredging and anchoring destroy beds; fouling.
- **Tour:** seagrass and *Cystoseira* are dive and snorkel assets in the 2 Mai - Vama Veche reserve; *Ulva* and *Cladophora* wrack piles up on beaches.
- **Ports:** dredge spoil smothers beds.

**Hypoxia history** (LIT):
- 3,500 km2 in 1973; 30,000 km2 by 1978.
- Hypoxia still forms in late summer and reaches Constanța Bay in bad years. The post-1995 recovery was overstated ([Capet et al. 2013](https://doi.org/10.5194/bg-10-3943-2013); [Chevalier et al. 2024](https://doi.org/10.1016/j.marpolbul.2024.116857)).
- Mytilus and Modiolula biocoenoses were in good status on their benthic index (M-AMBI) in 2015-2018. Shallow infralittoral sands were not ([Abaza et al. 2019](https://www.marine-research-journal.org/index.php/cmrm/article/view/143)).
- In 2024 the Mytilus reef was in good status on its index, but live biomass was very low (RO-MSFD-2024).

**Thresholds:**

| Criterion | Value | Status |
|---|---|---|
| WFD M-AMBI(n), CW-BL1 | High/Good 0.90, Good/Moderate 0.68 | OFFICIAL-EU (Decision 2024/721) |
| WFD macroalgae index EI | High/Good 0.837, Good/Moderate 0.644 | OFFICIAL-EU |
| M-AMBI*(n) per habitat | at least 0.68 for coastal and Mytilus, at least 0.61 for transitional and Modiolula | OFFICIAL-RO (2018) |
| Macroalgae | perennial sensitive species above 60% of biomass; EI above 6 = good. 2015-2018 scores: *Cystoseira* 7.7, *Zostera* 7.6, *Phyllophora* 7.25; infralittoral rock 3.1 (fails) | OFFICIAL-RO |
| *Cystoseira* biomass target | at least 2,500 g m-2 | OFFICIAL-RO (target) |
| *Zostera* biomass target | at least 1,500 g m-2 | OFFICIAL-RO (target) |
| Bottom O2 (D5) | 10th percentile at least 6 mg/L and 60% saturation | OFFICIAL-RO (2018) |
| D5C5 bottom O2, as used in 2024 | May-Sep 10th percentile at least 5 mg/L and at least 60% saturation. Method: Winkler at the water-sediment interface. Stations: 20 m in transitional and coastal waters, 30-50 m on the shelf. The NIMRD 2018-2023 data (145 samples) gave P10 5.44 mg/L and 54.3% saturation, minimum 3.33 mg/L | OFFICIAL-RO (RO-MSFD-2024 pp. 137-151; the report contradicts itself on whether the saturation part passes) |
| Bottom-O2 classes | A at least 5, B 4-5, C 2-4, D below 2 mg/L. Shared with the chemical session ([chemical.md](chemical.md)) | OURS (team convention) |
| Hypoxia | below 2 mg/L (62.5 mmol m-3) = class D | LIT (common definition, Diaz and Rosenberg 2008, [doi:10.1126/science.1156401](https://doi.org/10.1126/science.1156401)) |
| Mussel-stress marker | below 3 mg/L | **OURS, not official.** Chosen just above the mean lethal O2 concentration across benthic taxa (2.61 mg/L) in the meta-analysis of [Vaquer-Sunyer and Duarte 2008, PNAS 105:15452](https://doi.org/10.1073/pnas.0803833105). The same study puts sublethal effects up to about 4.6 mg/L, which is why class C (2-4 mg/L) already counts as stress. No Mytilus-specific Black Sea threshold was found. |

**Our check (B5), at NIMRD Mytilus-reef stations:**
- OBIS Mytilus records lie at 20-52 m (median 34 m).
- The stations are on the Est Constanța profile. Their positions come from OBIS (section 6.2), and RO-MSFD-2024 lists Est Constanța 2-4 as Mytilus reef stations.
- Data: reanalysis bottom O2, with bottom temperature and salinity for saturation (Garcia and Gordon 1992), 2010-2024.

| Station | Days in class D (below 2 mg/L) | Days in class C (2-4 mg/L) | Years failing the D5C5 test | Worst year |
|---|---|---|---|---|
| 47 m (44.167 N 29.133 E) | 3 in 2017, 3 in 2024 | 13 in 2024, 6 in 2023 | 2010, 2022, 2024 | **2024**: minimum 1.53 mg/L, May-Sep P10 4.69 mg/L and 45% saturation |
| 36 m (44.167 N 28.900 E) | none | in 6 of 15 years | 2010, 2024 | 2024: P10 4.58 mg/L, 47% saturation |
| Inshore point (26 m) | none | some years | 2010, 2024 | |

- This agrees with the chemical session: its reanalysis fails D5C5 in 7 of 32 years at Constanța, including 2024.
- The model is smooth. Real hypoxia is patchy and often shorter or deeper than the model shows, so these are **exposure flags, not mortality**. No mussel mass mortality after 2010 is documented in the literature (section 6.1).

**Natural versus human-caused:**
1. Check stratification and calm weather first: late-summer SST, mixed-layer depth, wind.
2. Then bottom O2.
3. Then the Danube nutrient pulse 1-3 months earlier, and organic load (chl B1/B2).

**Remote versus field.** Nothing benthic is visible from satellite.

| Evidence | Source | Notes |
|---|---|---|
| Bed depth and substrate | EMODnet Bathymetry and Geology | `depth_at`, `seabed_substrate` |
| Habitat map | EUSeaMap | 503 errors on 2026-11-23 |
| Bed condition | ROV or drop camera | `vision.py` labels mussel bed, shell debris, seagrass, *Phyllophora*, brown algae, green algae, sand, mud, rock and litter (zero-shot CLIP/BioCLIP, unvalidated) |
| M-AMBI | grab samples | |
| Macrophyte biomass | diver quadrats | |

### 3.4 Non-indigenous species (MSFD D2)

**Why it matters.** Romania has a validated list of **37 alien species, 13 of them invasive** ([Băncilă et al. 2022](https://doi.org/10.3391/ai.2022.17.3.02)). Older counts of about 49 included species now treated as cryptogenic. The main pathway is shipping: ballast water and hull fouling. Key species:
- *Rapana venosa*: first Black Sea record 1947. It ate the oyster and mussel beds. It is now **over 90% of Romanian landings** (2,670 t in 2023) and its F is above Fmsy.
- *Mya arenaria* and *Anadara kagoshimensis*: tolerate hypoxia and replace native bivalves.
- *Mnemiopsis* and *Beroe*: see 3.2.
- *Rhithropanopeus harrisii* and *Acartia tonsa*.

Effect on each sector:
- **Ports:** the main entry point; the Ballast Water Management Convention applies.
- **Ship:** hull fouling and dry-dock cleaning.
- **Fish:** *Rapana* is both a resource and a pest.
- **Aqua:** *Rapana* preys on mussel lines; fouling.
- **Tour:** minor.

**Thresholds:**
- D2C1 is the number of new NIS per 6-year cycle.
- RO-MSFD-2024 (Table III.2.5, pp. 87-88) reports **7 new NIS, all phytoplankton**, so D2C1 is not in good status. There were 8 in 2018. The 7, with first record:
  - *Thalassiosira minima* (2018)
  - *Lennoxia faveolata* (2019)
  - *Dinobryon faculiferum*, *Leucocryptos marina*, *Plagioselmis prolonga* and *Thalassiosira punctigera* (2020)
  - *Miraltia throndsenii* (2023)
- Ballast water is the probable vector. The national count used in the report is 35 NIS for 2018-2023: about 2% of native species, against a 4% threshold, so good status on that criterion.
- Port monitoring was a single 2023 survey of Tomis, Constanța and Mangalia ports. Midia was not included, and there were no settlement plates, eDNA or ballast-water sampling.
- The NIS/native ratio and the bio-pollution index were in good status (OFFICIAL-RO).
- The EU sets no numeric D2C2 threshold.

**Our B6:**
- All 7 NIS we listed have OBIS records since 2015.
- The *Mnemiopsis* / *Beroe* yearly record counts show *Beroe* appearing in 1997 and the *Mnemiopsis* records thinning after 2003.
- **That thinning is a sampling-effort artefact as much as biology.** The NIMRD zooplankton series in OBIS stop around 2010-2015.

**Remote versus field.** Field only: port monitoring (ballast water, settlement plates), NIMRD trawl and grab samples, citizen science, eDNA, and ROV for *Rapana* on beds.

### 3.5 Fish (MSFD D3, D4, nurseries)

**Official Romanian D3 status** (OFFICIAL-RO, RO-MSFD-2024 pp. 279-289; F and SSB are basin-wide GSA 29 values from STECF/GFCM):

| Stock | F, 2018 to 2023 | Reference | Status | Biomass |
|---|---|---|---|---|
| Sprat | 0.62 to 0.46 | Fmsy 0.64 | good status every year | SSB fell from 308 kt (2020) to 66 kt (2023), near the 60 kt threshold |
| Turbot | 0.47 to 0.13 | Fmsy 0.15 / 0.19 | good status only in 2023 | SSB 1.6-1.9 kt, above 1.5 kt. GFCM reports F down 86% and biomass up 310% since 2013 ([SoMFi 2025](https://www.fao.org/gfcm/publications/somfi/2025/en)) |
| Horse mackerel | 1.28 (2023) | Fmsy 0.59 | not in good status | |
| Whiting | 0.84 (2023) | Fmsy 0.31 | not in good status | |
| Rapa whelk | 2.30 | Fmsy 1.33 | not in good status | |

Anchovy is "possibly overexploited" (GFCM, qualitative advice only).

**Romanian catches in 2023:** rapa whelk 2,670 t, mussels 317, sprat 92, turbot 70, anchovy 26 t.

**Quotas and management:**
- Sprat EU quota: 11,475 t, of which Romania has 3,442.5 t and uses about 3%.
- Turbot: GFCM regional TAC 890 t per year for 2025-28.
- Turbot closure 15 April to 15 June; minimum size 45 cm.

**Food web (D4).**
- History (LIT): regime shifts in the early 1970s (predator depletion) and the early 1990s (*Mnemiopsis*), both triggered by fishing-driven trophic cascades ([Daskalov et al. 2007, PNAS](https://doi.org/10.1073/pnas.0701100104)).
- Romania's official D4 uses **plankton indicators only**: the diatom/dinoflagellate ratio, diversity indices, copepod biomass and *Mnemiopsis*.
- Mean trophic level of catches and the large-fish indicator are **not** used officially.

**Nurseries.**
- Turbot spawn April-June (peak in May) and use shallow 5-10 m nurseries, especially between Agigea and Vama Veche.
- There is no official Romanian nursery-area layer. That is a gap to raise with NIMRD.

**Remote versus field.**
- Only stock assessments (GFCM/STECF) and NIMRD surveys give this.
- Satellite chl and SST give habitat context only, such as anchovy and sprat feeding conditions.
- OBIS has 3 turbot records, so it is not usable.
- Dashboard: show the official status as a static table with its year and source, not a live layer.

Effect on each sector: Fish (directly), Aqua (feed and competition), Tour (the seafood supply chain).

### 3.6 Marine mammals

All three Black Sea cetaceans are endemic subspecies: harbour porpoise *Phocoena phocoena relicta*, bottlenose dolphin *Tursiops truncatus ponticus* and common dolphin *Delphinus delphis ponticus*. Porpoise and bottlenose are listed Endangered (ACCOBAMS reassessment, provisional).

**Abundance** (2019 ASI aerial survey, Romanian waters of 18,611 km2; [Paiu et al. 2024](https://doi.org/10.3389/fmars.2024.1248950)):

| Species | Estimate | 95% CI |
|---|---|---|
| Harbour porpoise | 6,258 | 4,582-8,547 |
| Bottlenose dolphin | 3,608 | 2,515-5,177 |
| Common dolphin | 2,424 | 1,580-3,718 |

**Bycatch:**
- Basin-wide porpoise bycatch is 11,826-16,200 per year, mainly in turbot gillnets ([Popov et al. 2023](https://doi.org/10.3389/fmars.2023.1119983)).
- The official D1C1 limit (bycatch at most 1.7% of abundance) gives **106 porpoises per year for Romania**. The reported bycatch of 208 means the criterion is failed (OFFICIAL-RO, 2024).

**Strandings:**
- OBIS Mare Nostrum dataset (check): 2010-2016 porpoise 15-150 per year, with a 2012 peak of 150 porpoise records.
- 2021-2025: 76 stranded cetaceans on the Romanian coast, 71% of identified animals harbour porpoise ([Harcotă and Ciucă 2026, Animals 16:3422](https://doi.org/10.3390/ani16213422)).
- The full Mare Nostrum/NIMRD dataset (OBIS-SEAMAP 899, 1,157 records 2010-2022, [doi:10.82144/5094a4d2](https://doi.org/10.82144/5094a4d2)) is download-restricted.
- Press and conference figures (203 in Jan-Oct 2022; a record 2026) are not consistent with the peer-reviewed count. Do not mix the two sources (UNVERIFIED).
- Mortality rose after 2022 (war, noise, Kakhovka dam) ([Wegrzyn et al. 2023](https://doi.org/10.1098/rsbl.2022.0562); ACCOBAMS SC16 2024).

Effect on each sector:
- **Fish:** bycatch, closures, pingers (porpoise alarm devices).
- **Ports and Ship:** underwater noise, collisions, pile-driving for offshore works.
- **Tour:** dolphin watching; stranding response on beaches.

**Remote versus field.** Aerial or ship surveys, acoustic loggers (C-PODs), strandings networks, and bycatch observers. Nothing comes from satellite.

### 3.7 Seabirds (brief)

| Species | Reference | Status |
|---|---|---|
| Yelkouan shearwater (*Puffinus yelkouan*) | about 0.09 birds km-2 offshore | favourable |
| European shag (*Gulosus aristotelis desmarestii*) | first Romanian breeding in over 60 years in 2019, on a platform near Constanța port; reference 7 pairs | unfavourable |

- The marine Special Protection Area for birds is ROSPA0076 Marea Neagra, about 140,000 ha.
- Sector links: offshore wind and platforms; oil spills (Ports); fishing bycatch.
- Field surveys only. OBIS holds 115 shag records for 2013-2026.

---

## 4. Shortlist: formulas, sources, confidence and plain-language texts

Notation:
- `c(t)` is daily satellite chl at the pixel nearest the point.
- `G(d)`, `s(d)`, `P10(d)` and `P90(d)` are the geometric mean, std(log10), 10th and 90th percentiles of chl for day of year `d`, from 1998-2020. They pool ±15 days (circular) and are computed in log10 space.

### B1. Chl-a anomaly (log space) and the official D5C2 test

**Formula:**
```
ratio(t) = c(t) / G(doy)                                 # 2.0 = twice normal for the date
z(t)     = (log10 c(t) - log10 G(doy)) / s(doy)
flag     = "high" if c > P90(doy);  "low" if c < P10(doy);  else "normal"
D5C2 proxy (yearly) = P75 of c(t) over May-Sep;  compare with 5.97 ug/L (coastal) / 4.11 / 2.79 (shelf N/S)
```

**Data:** `sat_chl_l4_nrt` for now and `sat_chl_l4_my` for the climatology. Cross-check with `open_data.chl_occi_8day` (OC-CCI v6) and its `anomalies()`.

**Confidence:** high offshore. Medium within about 10 km of the coast and in the Danube plume, where sediment and CDOM bias the signal. Anomalies remove part of that bias, because the climatology shares it.

**Today (check):**
- 2026-11-15 to 11-22: ratio 0.48-1.13. Normal, with one low day.
- D5C2 proxy: passes every year since 2011.

**Plain-language texts:**
- **Public:** "Green colour of the sea compared with what is normal for this week of the year. Higher means more microscopic algae."
- **Student:** "Satellite chlorophyll, compared in log space with a 23-year day-of-year climatology. Values above the 90th percentile are flagged."
- **Stakeholder:** "Early warning of algal blooms: a high value means check the water quality for bathing and shellfish, not that damage has happened."

**Researcher note.** Chl is log-normal, so use geometric means and log ratios. Case-2 bias makes the absolute D5C2 comparison a proxy only: the official metric uses in-situ euphotic-layer samples. The satellite pooled 2018-2023 75th percentile (3.2) is lower than NIMRD's in-situ value (4.9). Attribution: regress log c on log Q (Danube discharge) and read the residual.

### B2. Bloom days per season, with long-term trend

**Formula:**
```
bloom_rel_days(year, season) = count of days with c(t) > P90(doy)
bloom_abs_days(year, season) = count of days with c(t) > 10 mg m-3            # OURS
trend = Theil-Sen slope of yearly values; report the 1998-2007 vs latest-10-year geometric means
```

**Data:** `sat_chl_l4_my` (gap-free L4, so no cloud bias in the counts). An L3 version would need a valid-day fraction.

**Confidence:** medium. Gap-filling smooths short blooms. Use an L3 or OLCI 300 m spot-check for a specific event.

**Result (check):**
- 10-70 relative bloom days per year; -0.8 days per year trend.
- 2024 had 54 relative bloom days, driven by spring (spring geometric mean 5.9 mg m-3, the highest in the record).
- 2025 had 21.

**Plain-language texts:**
- **Public:** "How many days this year the sea had an unusual algal bloom."
- **Student:** "Count of days above the 90th percentile of the climatology, per season. The trend is a robust Theil-Sen slope."
- **Stakeholder:** "More bloom days means more risk of low oxygen near the bottom later in summer, a concern for mussel farms and beaches."

**Researcher note.** Bloom-day counts correlate with Danube discharge (rho +0.73), so show discharge on the same panel before calling a trend human-driven.

### B3. Phytoplankton community structure

**Formula:**
```
micro_share(t) = MICRO / (MICRO + NANO + PICO)          # satellite size classes, monthly median
diatom_share(sample) = sum(Bacillariophyceae cells/L) / sum(Bacillariophyceae + Dinophyceae + Coccolithophyceae cells/L)
bloom_sample = total cells/L > 1e6 (NIMRD / BSC convention)
```

**Data:** the CATALOG keys `sat_pft_l3_my` / `sat_pft_l3_nrt` (dataset `cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D`), and OBIS NIMRD phytoplankton 1961-2015 with surface abundance from measurement-or-facts.

**Confidence:**
- Satellite: low. It saturates (0.68-0.93) in coastal water, and size is not taxonomy.
- In-situ: high, but the record ends in 2015 in OBIS.

**Plain-language texts:**
- **Public:** "Which kinds of microscopic algae dominate: the 'good food' diatoms or the bloom-forming dinoflagellates."
- **Student:** "Diatom share of cell counts. It fell during the eutrophication of the 1970s-80s and has since partly recovered."
- **Stakeholder:** "A shift to dinoflagellates raises the risk of toxic or nuisance blooms. This needs lab samples; the satellite only gives a rough hint."

**Researcher note.** This is Romania's official D4 criterion (diatom/dinoflagellate ratio), which was not in good status in 2020-21. Recent counts must come from NIMRD directly.

### B4. Primary production

**Formula:**
```
monthly mean of PP (g C m-2 d-1);  annual = mean * 365
log-ratio anomaly vs same-month mean (once a multi-year PP climatology is pulled)
model vs satellite: compare seasonal shapes only (model nppv is volumetric at the surface, mg C m-3 d-1)
```

**Data:** the CATALOG keys `sat_pp_my` / `sat_pp_nrt`; model `rea_bgc_o2` / `bgc_o2` `npp`.

**Result (check, 2024 at Constanța):**
- Satellite PP: 0.25 (December) to 1.77 (July) g C m-2 d-1, about **312 g C m-2 yr-1**. That is in the eutrophic 300-500 range Oguz gives for the 1980s-90s.
- Model surface NPP peaks in winter and autumn (40-48 mg C m-3 d-1) and is lowest in April-June (11-14).
- The seasonal cycles disagree. This is a useful **observations vs model** example for the jury.

**Confidence:** medium (satellite PP is a modelled product from chl, light and temperature); low for the model at the coast.

**Plain-language texts:**
- **Public:** "How fast the sea's algae grow, like the harvest of a field."
- **Student:** "Satellite-derived net primary production, integrated over depth. Compare it with the model to see where the model is wrong."
- **Stakeholder:** "The productivity behind the fish catch. A sustained rise means too many nutrients; a fall can mean less food for sprat and anchovy."

**Researcher note.** No measured primary-production series exists for the Romanian shelf (gap). Use PP as context, not as a pass/fail indicator.

### B5. Mussel-bed hypoxia exposure

**Formula:**
```
sites  = NIMRD Mytilus-reef stations (Est Constanta 36 m and 47 m; positions from OBIS) or Mytilus/Modiolula OBIS records;
         depth from depth_at()
O2(t)  = model bottom O2, mg/L = mmol m-3 x 0.032;  sat(t) = O2 / O2sat(bottom T, S)  (Garcia and Gordon 1992)
class(t) = A >= 5 | B 4-5 | C 2-4 | D < 2 mg/L        (shared with the chemical session)
per year: days in each class; days < 3 mg/L (OURS); D5C5 = May-Sep P10(O2) >= 5 mg/L and P10(sat) >= 60 %  (OFFICIAL-RO)
flag "investigate bed" if any class-D day, or >= 3 consecutive class-C days in Jul-Oct, or D5C5 fails
```

**Data:** `rea_bgc_o2` (1992-2024) and `bgc_o2` (2024 onward), both `o2_bottom`; `rea_phy_temp` / `phy_temp` `bottom_temp`; `rea_phy_sal` / `phy_sal` at site depth; OBIS; `emodnet_layers.depth_at`.

**Confidence:** medium-low. The model has 2.5 km cells and smooths short hypoxia events. There is no in-situ bottom O2 at the beds. The Romanian offshore buoys `EUXRoOB0x` measure DOXY near the surface only (to verify).

**Result (check):** see 3.3. At the 47 m Est Constanța reef station there were class-D days in 2017 and 2024, and D5C5 failed in 2010, 2022 and 2024.

**Plain-language texts:**
- **Public:** "Did the water at the seabed run short of oxygen where mussels live?"
- **Student:** "Days of modelled bottom hypoxia at known mussel-bed locations. A proxy for stress, not a count of dead mussels."
- **Stakeholder:** "A warning for mussel farms and the mussel fishery: when this lights up, send divers or an ROV to check the bed."

**Researcher note.** Damage is confirmed only by an ROV or grab survey (mortality, empty shells, M-AMBI). The `vision.py` "mussel_bed" against "shell_debris" labels on ROV frames give a fast first look.

### B6. Non-indigenous and gelatinous species: occurrence evidence

**Formula:**
```
for taxon in NIS list (Rapana, Mya, Anadara, Mnemiopsis, Beroe, Rhithropanopeus, Acartia tonsa ...) and gelatinous (Aurelia, Rhizostoma):
    presence_recent = records since (current year - 6) > 0          # one MSFD cycle
    last_seen, n_records, n_datasets per 0.25 deg cell (OBIS /occurrence, Romanian box)
    new_NIS_cycle = taxa whose first Romanian record falls in the cycle (cross-check with the official national list)
effort = all-taxa records per cell (biology_records_grid) -> show presence on top of effort, never "absence"
```

**Data:** OBIS API (cached in `data/cache/obis/`), EMODnet Biology grid.

**Confidence:** low for trends (records track sampling effort and citizen science); good for presence and location.

**Plain-language texts:**
- **Public:** "Where introduced species, like the rapa whelk or the comb jelly, have been reported."
- **Student:** "Occurrence records from OBIS. Many records means many observers, not necessarily many animals."
- **Stakeholder:** "Ports and shipyards are the entry points. New sightings near a terminal mean checking ballast-water and hull-cleaning practice."

**Researcher note.** The official D2C1 uses NIMRD's validated list: 7 new NIS in 2018-2023. Do not compute "new NIS" from OBIS alone.

### B7. Biological evidence coverage and the "investigate" layer

**Components:**
- the EurOBIS record grid as an effort map;
- cetacean strandings per year;
- ROV and AUV habitat labels from `vision.py` (zero-shot classes: mussel bed, shell debris, seagrass, *Phyllophora*, brown algae, green algae, sand, mud, rock, litter);
- Natura 2000 marine sites (`natura2000`) to prioritise.

**Purpose:** answers the jury's question "what biological evidence do you have here, and what is missing?" Wherever B1, B2 or B5 raises a flag and B7 shows little biological evidence, the dashboard recommends a survey.

**Plain-language texts:**
- **Public:** "Where scientists have actually looked at sea life."
- **Student:** "Sampling-effort map. Use it to judge how much to trust absence."
- **Stakeholder:** "Where to send the next survey: high environmental warning plus low biological evidence equals the top priority."

---

## 5. How the dashboard should show biological evidence honestly

1. **Three badges on every value:**
   - **Measured:** in-situ count, biomass or survey.
   - **Proxy:** satellite chl, size classes, PP, or model O2 at the beds.
   - **Needs field:** species, toxins, M-AMBI, macrophyte biomass, stock status.
   Each value also shows its source, dataset id, date and distance from the requested point, all of which the modules already return in `attrs`.
2. **Two-step wording.** An environmental anomaly gives "conditions favour X". Only biological evidence gives "X is happening".
   - Example: "Bottom O2 below 2 mg/L modelled for 3 days at the Constanța East mussel bed: conditions for mussel mortality. Status: not verified. Recommended: ROV transect or grab sample within 2 weeks."
3. **Natural-driver panel next to every biological anomaly:**
   - Danube discharge (the previous 60 days);
   - SST anomaly and mixed-layer depth;
   - wind.
   If the driver explains it (for example a flood followed by a bloom), label it "likely natural / river-driven".
4. **Reference line, with its type labelled:**
   - official thresholds (OFFICIAL-RO or OFFICIAL-EU) as solid lines;
   - our climatology bands (10th-90th percentile, OURS) as shaded areas;
   - never mix the two without a label.
5. **Occurrence data is shown as presence over effort.** Never show it as absence or as a trend, unless the effort-normalised share (taxon records / all records in the cell) is shown.
6. **Static official status table** (D1-D6, from RO-MSFD-2024) with the assessment period 2018-2023. It is clearly not live.
7. **"Investigate" recommendations**, in priority order:

| Trigger | Recommendation |
|---|---|
| B5 flag at a mussel bed | ROV or drop-camera transect plus grab sample (mortality, M-AMBI) |
| B1/B2 high in June-September | Niskin samples for species, *Pseudo-nitzschia*, *Dinophysis* and *Noctiluca*; shellfish toxin test for farms |
| Jellyfish reports, or B6 new presence near a port | Plankton net tow; ballast-water check |
| Any flag inside a Natura 2000 marine site | Check *Zostera*, *Cystoseira* and *Phyllophora* condition (EI index) |

### Sector matrix (biological indicators to the five sectors)

| Indicator | Ports and logistics | Shipyards and marine engineering | Tourism | Fishing | Aquaculture |
|---|---|---|---|---|---|
| B1/B2 chl, blooms | cyst transport, dredging plumes | (minor) | discoloured water, smell, bathing complaints | food-web base | **toxins, closures, O2 crash** |
| B3 community | ballast-water HAB species | | *Noctiluca* red tides | diatoms = good food | **toxic dinoflagellates** |
| B4 productivity | | | | **stock productivity** | growth rate |
| B5 mussel-bed hypoxia | dredge spoil adds to the effect | coastal works | dive sites | mussel fishery, turbot habitat | **mortality of seed and farm stock** |
| B6 NIS / gelatinous | **ballast vector** | **hull fouling** | **jellyfish on beaches** | *Rapana*, *Mnemiopsis* | fouling, *Rapana* predation |
| Fish stocks (static) | | | | **quota, closures** | |
| Cetaceans (static plus strandings) | noise, collisions | pile-driving noise | dolphin watching | **bycatch** | |

---

## 6. Open questions: what desk research answered (2026-11-23)

Sources for this section:
- the full text of RO-MSFD-2024 (page references are the printed pages);
- 2016-2026 papers;
- live OBIS, EMODnet and nodc.ro checks.

The underlying notes are kept outside the repo, in the shared session notes folder: `bio_lit_fish_mammals_msfd.md` and `bio_lit_plankton_benthos.md`, each under "Follow-up".

### 6.1 Answers by question

| # | Question | Answer we found ourselves | Still needs NIMRD? |
|---|---|---|---|
| Q1 | Phytoplankton after 2015 | See "Q1 detail" below | Yes: the raw counts |
| Q2 | Official D5C2 input | See "Q2 detail" below | Only: are the 491 samples available as data? |
| Q3 | Mussel beds, hypoxia, mortality | See "Q3 detail" below | Yes: bed polygons, and confirmation that no die-off happened in 2017 or 2024 (B5 flags) |
| Q4 | Macrophytes | See "Q4 detail" below | Yes: areas in hectares, a *Phyllophora* survey |
| Q5 | NIS list, port monitoring | See section 3.4. **7 new NIS 2018-2023, all phytoplankton; 35 NIS in total.** Port survey only in 2023 (Tomis, Constanța, Mangalia); no plates, eDNA or ballast sampling. Validated literature list: 37 alien species, 13 invasive ([Băncilă et al. 2022](https://doi.org/10.3391/ai.2022.17.3.02)) | Only: the reason the two counts differ |
| Q6 | Gelatinous after 2013 | See "Q6 detail" below | Yes: means by water body, beach reports |
| Q7 | Nursery and spawning maps | See "Q7 detail" below | Yes: the GIS layers |
| Q8 | Strandings, bycatch, acoustics | See "Q8 detail" below | Yes: data access, a new bycatch estimate |
| Q9 | ROV labels for `vision.py` | No open labelled Romanian imagery and no published NIMRD or GeoEcoMar ROV reef survey. The nearest set is the Bulgarian MSFD 2017 rocky-reef photo and video set (CC-BY, not QC'd): [catalogue](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/1643f473-efbb-4a80-a6cf-0758f7d31f5b). Not downloaded, labels unchecked | **Yes** (core ask) |
| Q10 | Constanța East benthos series | **Ends in 1999** (234 samples, 5 stations 14-55 m, [marineinfo 5661](https://marineinfo.org/id/dataset/5661)). Later Romanian benthos in OBIS: GeoEcoMar 2003-2011 and NIMRD Danube mouths to 2015. New compiled dataset: 237 stations 1995-2017 with modelled O2 ([Chevalier et al. 2025, Sci. Data](https://doi.org/10.1038/s41597-025-05311-2), data [figshare](https://doi.org/10.6084/m9.figshare.27888843)). Per-station M-AMBI exists only for the Tuzla and Mangalia marine protected areas ([Begun et al. 2022](https://doi.org/10.3389/fmars.2022.845507)); NIMRD publishes per habitat and year | Yes: per-station M-AMBI |

**Q1 detail: phytoplankton after 2015.** Partly answered.

- RO-MSFD-2024 gives 90th-percentile biomass per profile, for example Mangalia coastal 12,145 mg m-3. The biomass target is exceeded in 75% of coastal and 77% of marine samples.
- Official D4 diatom/dinoflagellate ratio (spring, 0-20 m):

| Area | 2020 | 2021 | Target | Status |
|---|---|---|---|---|
| Coastal | 0.14 | 0.52 | above 0.7 | fails |
| Marine | 0.04 | 0.53 | above 0.7 | fails |

- Papers:
  - Portița diatom bloom, June 2015: 3.4 million cells/L, chl 33.8 µg/L.
  - 2016: no species above 1 million cells/L.
  - Northern blooms in June 2023 ([Tabarcea et al. 2026](https://doi.org/10.3390/jmse14080730)).
  - Harmful species, September 2021 cruise ([Dzhembekova et al. 2025, Harmful Algae](https://doi.org/10.1016/j.hal.2025.103025)): *Pseudo-nitzschia* present without domoic acid; *Dinophysis* and *Gonyaulax* with pectenotoxins and yessotoxins; first Black Sea record of *Alexandrium fragae* with GTX-2/3.
  - Satellite *E. huxleyi* blooms nearly every June ([Cazzaniga et al. 2021](https://doi.org/10.1016/j.rse.2021.112607)).
- **No raw counts after 2015 are public.** OBIS has no NIMRD plankton after 2015, and nodc.ro lists no biological downloads.
- **No shellfish-toxin data exists for Romanian mussels.** That is a gap, not a clean record.

**Q2 detail: official D5C2 input.** **Answered.**
- Spectrophotometric chl (SCOR-UNESCO), 0-10 m layer, May-September, 75th percentile per area.
- 10 cruises from 2018 to 2023, 78 stations, 491 samples (Transitional 72, Coastal 154, North shelf 78, South shelf 187).
- **Satellite chl is not used.** It served only to draw the area boundaries, and satellite bloom indicators are listed as future work (pp. 130-151, 293, 369).
- So our daily satellite B1/B2 adds about 180 values per pixel per season where the official test has about 25-50 samples per area per year. That is the dashboard's value-add, as long as it stays labelled a proxy.

**Q3 detail: mussel beds, hypoxia, mortality.** Mostly answered.
- 19 Mytilus-reef stations at 30-57 m (Sulina to Mangalia, including Est Constanța 2-4). 89% are in good status on M-AMBI*(n) (threshold 0.68); Periboina 30 and 37 m fail.
- Mytilus biomass is 5-3,593 g m-2 against a 5,000 g m-2 target, mostly young mussels.
- Modiolula: 22 stations at 53-111 m, 95% in good status.
- NIMRD bottom O2 2018-2023 at 20-50 m: minimum 3.33 mg/L.
- **No mass mortality after 2010 is documented** in the report or in papers. The nearest items are three events below 60% saturation at 30 m (Sf. Gheorghe, Portița, 2012-2017).
- **No bed polygons are published.** We use the station positions (section 6.2).

**Q4 detail: macrophytes.** Mostly answered.
- 2018-2023: 504 samples at 0-8 m.

| Habitat | Result |
|---|---|
| All stations, EI index (target above 6) | mean 3.83; only Constanța Nord, Jupiter, Saturn and Mangalia pass |
| Opportunistic algae (D5C6) | 54.6% of biomass; fails |
| *Gongolaria barbata* | EI 7.21, good status. Only 5-6 of 13 historical sites remain (Cazino Constanța to Vama Veche); density back to 1960s levels inside them ([Marin and Spînu 2023](https://doi.org/10.18054/pb.v125i3-4.26815)) |
| *Zostera noltei* (Mangalia) | ZoNI 0.648 (target above 0.55), good status. 2023 drone and field baseline: 7 meadow sites, up to 1,223 shoots/m2 ([Marin et al. 2024](https://doi.org/10.3390/jmse12122346)) |
| *Ulva* | maximum 2,200 g/m2 at 2 Mai, 2019-2023 |
| ***Phyllophora* (ROSCI0413)** | **not assessed and no recent survey** |

**Q6 detail: gelatinous species after 2013.** Partly answered.
- *Mnemiopsis*, 2018-2023 (278 stations, target at most 4 g m-3): 92% / 95% / 87% / 80% of stations pass in transitional / coastal / marine / offshore waters. Maxima are 18 g m-3 coastal and up to 1,600 g m-3 offshore, as printed in the report.
- *Noctiluca*, coastal mean 666 mg m-3; only 60% of samples are in good status (target 350).
- *Aurelia* (May trawl survey): 21 kt in 2016, then **268 kt in 2017**, when sprat juveniles collapsed (Radu et al. 2017, *Cercetări Marine* 47).
- *Rhizostoma*: no peer-reviewed record. OBIS citizen records are rising (45 in 2025), but that tracks the number of observers.

**Q7 detail: nursery and spawning maps.** Partly answered.
- RO-MSFD-2024 has none.
- Turbot habitat-suitability model, monthly 2013-2022 ([Constantin et al. 2025, *Cercetări Marine* 55](https://doi.org/10.55268/CM.2025.55.13)): best habitat at 40-70 m, highest in May in the south.
- Sprat juveniles were mostly at 30-60 m (May 2016).
- The Maritime Spatial Plan (Government Ordinance 97/2023) describes spawning and nursery areas qualitatively, with no layer.

**Q8 detail: strandings, bycatch, acoustics.** Partly answered.
- Peer-reviewed count: 76 strandings in 2021-2025, mostly porpoise.
- The full Mare Nostrum dataset (1,157 records, 2010-2022) is restricted.
- The official bycatch figure of 208 per year is the 2014 estimate, reused. The report itself says it must be recalculated.
- Acoustics: 19 F-PODs ran in the Black Sea in 2020-2022 (BlackCeTrends, with Mare Nostrum as partner). There are no Romanian results.

### 6.2 NIMRD monitoring profiles (positions derived from OBIS)

Neither RO-MSFD-2024 nor nodc.ro gives station coordinates. The NIMRD plankton datasets in OBIS do (2011-2015). They were computed by the stations section of [`biological_check.py`](../../scripts/indicators/biological_check.py).

| Profile | Lat (N) | Lon range (E) | Positions | Deepest sample (m) |
|---|---|---|---|---|
| Sulina | 45.13 | 29.79-29.96 | 5 | 34 |
| Mila 9 | 45.00 | 29.65-29.92 | 7 | 30 |
| Sf. Gheorghe | 44.88 | 29.64-29.85 | 7 | 40 |
| Portița | 44.67 | 29.00-29.92 | 11 | 70 |
| Gura Buhaz | 44.40-44.47 | 28.77-28.90 | 6 | 20 |
| Cazino Mamaia | 44.235 | 28.64-28.90 | 6 | 30 |
| Constanța Nord | 44.217 | 28.65-28.70 | 2 | 20 |
| **Est Constanța** | **44.167** | **28.683 (15 m), 28.783 (28 m), 28.900 (36 m), 29.133 (47 m), 29.367 (54 m)**, plus 30.20 (90 m, 2015 only) | 8 | 90 |
| Constanța Sud | 44.12-44.13 | 28.685 | 2 | 20 |
| Eforie Sud | 44.02-44.05 | 28.65-28.68 | 5 | 21 |
| Costinești | 43.945 | 28.64-28.73 | 5 | 30 |
| Mangalia | 43.80 | 28.60-28.83 (and 30.02, 100 m) | 10 | 100 |
| Vama Veche | 43.751 | 28.60-28.62 | 3 | 21 |

- A few OBIS records carry the wrong profile name. For example, "Sulina" and "Mangalia" appear at 44.677 N 29.474 E, which is on the Portița line, so treat the names there with care.
- Use these positions for the "investigate" layer (B7), as the B5 sites, and as matchup points for satellite chl.

### 6.3 Remaining questions for NIMRD (the ones desk research cannot close)

1. **Data access:** the post-2015 phytoplankton, zooplankton and gelatinous counts behind RO-MSFD-2024, and the 491 D5C2 chl samples. Can they be published to EMODnet Biology/OBIS or shared for the pilot?
2. **Mussel beds:** bed polygons (Mytilus, Modiolula). Were the modelled bottom-O2 lows of **August-September 2017 and 2024** at Est Constanța 47 m seen in cruises or in bed condition?
3. ***Phyllophora* in ROSCI0413:** is any survey planned? **Macrophyte habitat areas** in hectares?
4. **Shellfish toxins:** does ANSVSA or NIMRD test DSP, ASP and PSP in Romanian mussels from the three class-A production zones?
5. **Nursery and spawning:** the GIS layers behind the Maritime Spatial Plan and the turbot habitat model.
6. **Cetaceans:** access to the Mare Nostrum/NIMRD stranding dataset for 2010-2026, and a new bycatch estimate. Are any Romanian F-POD stations active?
7. **Validation:** label ROV and drop-camera frames from Romanian reefs (mussel bed, *Gongolaria*, *Zostera*, *Coccotylus*, shell debris), to validate the `vision.py` classes. Station M-AMBI per year?
8. **NIS:** why does the 2024 count (35) differ from the validated list of 37? Is Midia port in future NIS surveys?

---

## 7. Sources

**Romanian MSFD and WFD**
- RO-MSFD-2024, NIMRD study for the 2024 Art. 8 reporting (data 2018-2023): https://www.mmediu.ro/app/webroot/uploads/files/Studiu_raport_MSFD-2024.pdf
- RO-MSFD-2018 (Boicenco et al., data 2012-2017): https://mmediu.ro/app/webroot/uploads/files/STUDIU%20MSFD%20V1.9.pdf
- Lazăr et al. 2019, *Cercetări Marine* 49:57-74 (D5 thresholds): https://www.marine-research-journal.org/index.php/cmrm/article/view/142
- Boicenco et al. 2019, *Cercetări Marine* 49:34-56: https://www.marine-research-journal.org/index.php/cmrm/article/view/141
- Commission Decision (EU) 2024/721, WFD intercalibration: https://eur-lex.europa.eu/eli/dec/2024/721/oj

**Phytoplankton**
- Dzhembekova et al. 2025, Harmful Algae 151:103025: https://doi.org/10.1016/j.hal.2025.103025
- Tabarcea et al. 2026, JMSE 14:730: https://doi.org/10.3390/jmse14080730
- Cazzaniga, Zibordi and Mélin 2021, RSE 264:112607: https://doi.org/10.1016/j.rse.2021.112607
- Bologa et al. 1995 (Bodeanu data), CIESM: https://ciesm.org/online/monographs/CSS-1/CSS_1_85_110.pdf
- Black Sea Commission phytoplankton manual (Moncheva and Parr): http://www.blackseacommission.org/Downloads/Phytoplankton_%20Mannual-Final-1.pdf
- Vasiliu et al. 2012, *Mediterranean Marine Science* 13:213: https://doi.org/10.12681/mms.301
- Vasiliu et al. 2010, GeoEcoMarina 16: https://geoecomar.ro/website/publicatii/Nr.16-2010/02_vasiliu_fin.pdf
- Lazăr et al. 2013, *Cercetări Marine*: https://www.marine-research-journal.org/index.php/cmrm/article/view/115
- Oguz 2005, *Oceanography* 18(2)
- Grégoire and Beckers 2004: https://doi.org/10.5194/bg-1-33-2004

**Zooplankton and gelatinous species**
- Kideys 2005: https://tos.org/oceanography/assets/docs/18-2_kideys.pdf
- Kideys 1994, *J. Mar. Syst.* 5:171-181
- Harcotă et al. 2017: https://www.marine-research-journal.org/index.php/cmrm/article/view/62

**Benthos and hypoxia**
- Diaz and Rosenberg 2008, Science 321:926: https://doi.org/10.1126/science.1156401
- Vaquer-Sunyer and Duarte 2008, PNAS 105:15452: https://doi.org/10.1073/pnas.0803833105
- Chevalier et al. 2025, Sci. Data: https://doi.org/10.1038/s41597-025-05311-2
- Begun et al. 2022: https://doi.org/10.3389/fmars.2022.845507
- Marin and Spînu 2023: https://doi.org/10.18054/pb.v125i3-4.26815
- Marin et al. 2024: https://doi.org/10.3390/jmse12122346
- Capet et al. 2013: https://doi.org/10.5194/bg-10-3943-2013
- Chevalier et al. 2024: https://doi.org/10.1016/j.marpolbul.2024.116857
- Abaza et al. 2019: https://www.marine-research-journal.org/index.php/cmrm/article/view/143
- Surugiu et al. 2021: https://doi.org/10.3389/fmars.2021.745137
- Marin 2022: https://doi.org/10.55268/CM.2022.52.78

**Non-indigenous species**
- Băncilă et al. 2022: https://doi.org/10.3391/ai.2022.17.3.02

**Food web and fish**
- Constantin et al. 2025, Cercetări Marine 55 (turbot habitat): https://doi.org/10.55268/CM.2025.55.13
- Daskalov 2002: https://doi.org/10.3354/meps225053
- Daskalov et al. 2007: https://doi.org/10.1073/pnas.0701100104
- GFCM SoMFi 2025: https://www.fao.org/gfcm/publications/somfi/2025/en

**Marine mammals**
- Harcotă and Ciucă 2026, Animals 16:3422: https://doi.org/10.3390/ani16213422
- Paiu et al. 2024: https://doi.org/10.3389/fmars.2024.1248950
- Popov et al. 2023: https://doi.org/10.3389/fmars.2023.1119983
- Wegrzyn et al. 2023: https://doi.org/10.1098/rsbl.2022.0562
- ACCOBAMS SC16 2024: https://accobams.org/wp-content/uploads/2024/12/SC16.Doc07_Report-on-the-conservation-status-of-cetaceans-and-relevant-activities-in-Black-Sea.pdf

**Data**
- Copernicus Marine:
  - OCEANCOLOUR_BLK_BGC_L3_MY_009_153 / L4_MY_009_154 (DOI 10.48670/moi-00303, 10.48670/moi-00304)
  - BLKSEA_MULTIYEAR_BGC_007_005 (10.48670/mds-00372)
  - BLKSEA_ANALYSISFORECAST_BGC_007_010 (10.48670/mds-00354)
- ESA OC-CCI v6 via NOAA PIFSC ERDDAP.
- GloFAS v4 via the Open-Meteo Flood API.
- OBIS: https://api.obis.org/v3 (accessed 2026-11-23); NIMRD datasets via EurOBIS IPT, e.g. https://ipt.vliz.be/eurobis/resource?r=ro_black_sea_fpk_2006_2015
- EMODnet Biology (VLIZ).

Full literature notes with page references and OFFICIAL / PROPOSED / UNVERIFIED labels were collected during this research and kept in the shared session notes folder: `bio_lit_plankton_benthos.md` and `bio_lit_fish_mammals_msfd.md`.

**Unverified items to check before quoting:**
- strandings for 2021 and 2026 (press reports);
- the Romanian turbot quota of 82.5 t;
- first Romanian records of *Rapana* (1963) and *Mya* (1966);
- the marine Noctiluca warm-season threshold (sources give 240 or 60 mg m-3).
