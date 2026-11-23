# Idea bank (first draft, before the challenge details)

Rule for choosing: we have **about 3.5 build hours**, so pick an idea where a **working demo on their real data** is reachable by Day 2 at 10:30. A smaller idea with a live demo beats a big vision shown only on slides.

Scores are 1–5 for feasibility (F), jury fit (J) and wow factor (W). They are guesses until we see the data and the criteria.

---

### 0. SeabedGuard: from AUV/ROV images to a prioritised MPA map (lead idea after the first talk)
The first presentation listed four objectives: habitat maps, protected species, sensitive areas / MPA priority, and threats. This idea answers all four with one pipeline, built from ideas 1, 2 and 4.
- **What:**
  1. **Map habitats.** Every AUV/ROV image is labelled (seagrass, *Phyllophora*, brown algae, mussel bed, rock, sand, mud…) with CLIP/BioCLIP, zero-shot or from a few labelled examples, then placed on the map using the nav log.
  2. **Map threats.** YOLO-World spots litter, ghost nets and invasive *Rapana* in the same images. Buoy data adds area-wide pressures (hypoxia hours, bloom days).
  3. **Score each 50 m grid cell for sensitivity**: habitat value, share of protected habitat, habitat diversity. The weights are transparent and editable, with a stability check (does the ranking hold if the weights shift ±20%?).
  4. **Sort cells into a 2×2 of sensitivity vs threat:** *Protect & restore now* (sensitive and threatened), *Protect* (sensitive, still intact), *Clean up / mitigate* (low value, threatened), *Monitor*.
  5. **Candidate MPAs**: connected high-sensitivity cells merged into areas with size, habitats inside, and threats. Export as GeoJSON for QGIS.
- **User:** NIMRD habitat scientists, the Romanian environment ministry / ANANP (protected areas agency), MSFD and Natura 2000 reporting.
- **Demo:** Load a survey, then show the habitat map → threat map → priority map → candidate MPA list. Change a weight live and watch the map update.
- **F4 J5 W5.** Most of it is already in the starter kit (`vision.py`, `geo.py`, `priority.py`). The risk is image quality and whether we get a nav log. Without one, show the habitat breakdown per dive or transect instead of a map.
- **Pitch hook:** "Seagrass makes ~10 L of oxygen per m² per day, and Romania has very little left. We show where it is, what threatens it, and which areas to protect first."
- **Policy:** Habitats Directive / Natura 2000, MSFD D1 biodiversity + D6 seafloor integrity + D10 litter, EU 30% protection target (Biodiversity Strategy 2030), Bucharest Convention.

---

### 1. LitterLens: marine litter detection from ROV/AUV footage → hotspot map
- **What:** A YOLO detector (pretrained on public underwater-litter sets such as TrashCan or the JAMSTEC deep-sea debris set) runs on ROV/AUV frames. Each detection is geotagged from the vehicle's navigation log, and the result is a litter-density map plus an MSFD D10 indicator report.
- **User:** NIMRD and environmental agencies, MSFD reporting, cleanup prioritisation.
- **Demo:** Upload a video → boxes on the frames → points on a map → a summary table.
- **F4 J5 W5.** It matches a named topic directly and is very visual. Risk: their footage may look nothing like the public training data, so we may need a quick few-shot fine-tune.

### 2. SeabedSense: automatic seabed habitat classification from AUV imagery
- **What:** Embed seabed images with a foundation model (DINOv2 or BioCLIP), then classify them with a few labels or zero-shot prompts: sand, mud, mussel beds (*Mytilus galloprovincialis*), *Phyllophora* red-algae fields, rock, and invasive *Rapana venosa*. Mapped along the AUV track, this gives a habitat map.
- **User:** Habitat mapping, Natura 2000 and MSFD D1/D6 seafloor-integrity assessment, restoration site selection.
- **Demo:** An AUV transect drawn on a map with each segment coloured by habitat. Click a segment to see its images.
- **F4 J5 W4.** Embedding plus k-NN is fast and needs very few labels. This plays well to our GIS strength.

### 3. BuoyWatch: early-warning anomaly detection on smart-buoy time series
- **What:** Clean the buoy streams (temperature, salinity, dissolved O₂, chlorophyll, turbidity, pH). Detect anomalies and events: hypoxia, algal-bloom precursors, upwelling, marine heatwaves. Output plain-language alerts.
- **User:** Mussel farms, beach and water-quality managers, port authorities, NIMRD forecasters.
- **Demo:** A live dashboard (Streamlit) with flagged events and an "alert" panel that a non-scientist can read.
- **F5 J4 W3.** This is the safest technically. To stand out, add a short-term forecast or link it to MSFD D5 eutrophication.

### 4. Black Sea Health Index: one scorecard combining buoys, AUV and ROV
- **What:** A per-zone ecosystem health score that combines indicators from all three platforms (water quality, habitat condition, litter), mapped to MSFD descriptors and shown traffic-light style.
- **User:** Policymakers and governance, which is exactly the "ocean governance" angle in the brief.
- **Demo:** A map of coastal zones, coloured, with a drill-down into the indicators behind each score.
- **F3 J5 W4.** This is the strongest governance story, but it depends on enough data from all three sources. Ideas 1–3 can each become one module of it.

### 5. "Ask the Black Sea": an AI assistant over the monitoring data
- **What:** A Claude-powered agent with tools that query the buoy, AUV and ROV data. A policymaker asks "Was there low oxygen near Constanța last month?" and gets a chart plus a short answer with sources. It can also auto-generate monthly bulletins.
- **User:** Non-technical stakeholders, ministries, municipalities.
- **Demo:** A chat interface that answers live, with plots.
- **F4 J4 W5.** Easy to make impressive. The jury may ask "where's the science?", so pair it with idea 3 or idea 4 underneath.

### 6. Invasive species and biodiversity counter from video
- **What:** Detect and count key taxa in ROV video, for example the invasive comb jellies *Mnemiopsis*/*Beroe*, jellyfish (*Aurelia*, *Rhizostoma*), fish and *Rapana*. Produce abundance indices per dive.
- **F3 J4 W4.** Depends heavily on labelled data. BioCLIP zero-shot could make it work.

### 7. Satellite × buoy fusion: in-situ calibration of Sentinel-3 chlorophyll
- **What:** Use buoy measurements to calibrate and validate satellite chlorophyll and turbidity, then extend the buoy's point view into maps covering the whole coast.
- **F3 J4 W4.** A strong remote-sensing angle, but the data download takes time. Better suited to the Varna final.

---

## Current recommendation, to revisit after the 14:00 challenge brief
- **After the first talk:** idea 0 (SeabedGuard) is the favourite. It answers their stated objectives one by one.
- **Image or video data provided →** idea 0. If time runs short, cut it down to idea 2 (habitat map only) or idea 1 (litter only).
- **Mostly buoy time series →** idea 3 (BuoyWatch) with the idea 5 chat layer on top.
- **Governance-heavy criteria →** pitch idea 4 as the vision and build one module of it as the demo.

## Pitch skeleton (whatever we pick)
1. **Problem** (1 slide): a concrete Black Sea pain point with one striking number.
2. **Who suffers / who decides** (user persona).
3. **Solution + live demo**, the bulk of the time.
4. **How it uses EfxINNOs data** (buoys / AUV / ROV): the jury wants to see their platforms used.
5. **Policy fit**: Bucharest Convention, European Ocean Pact, MSFD descriptor(s).
6. **Scalability**: other Black Sea countries, a path to the Varna final.
7. **Team + next steps.**
