# Pitch plan: Black Sea Health Viewer

Pitch today, 24 Nov 2026. Presentations run 11:00-13:00 for up to 5 teams (agenda in the invitation), so plan for **7 minutes plus Q&A**, with a 5-minute cut ready. The brief does not state the length: ask the organisers at 10:00 and pick the version.

Status: plan only. No slides are built until Andrei approves this plan.

One-sentence pitch: *A map-first viewer for the Romanian coast that says, for each place and day, whether the water is normal, whether a change is natural or a likely pressure, how much to trust each number, and what to check next, for five blue-economy sectors.*

---

## 1. Pitch structure (7:00)

| Time | Part | Sprint | Speaker | Key message | Scoring criteria hit |
|---|---|---|---|---|---|
| 0:00-0:40 | Problem | 1 | Andrei | Change is not damage. Upwelling, the Danube and storms move every parameter; managers need to know when a change is natural and when it is us. | Impact (20) |
| 0:40-1:40 | Pressure map | 1 | Andrei | Five sectors share one coast. A plain count of overlapping sectors (0-5), with tourism only in summer, shows where monitoring matters most. | Integration across sectors (15) |
| 1:40-2:40 | Architecture and trust | 2 | Joseph | Every value comes from a named source with a known error. We checked satellite and model against buoys and bottles before trusting them. | Technical monitoring logic (20) |
| 2:40-3:30 | Data-to-decision canvas | 3 | Joseph | Indicator, reference, natural-or-pressure rule chain, status with confidence, then a concrete "investigate" action and who acts. | Data to decisions (15) |
| 3:30-6:00 | Live demo | 4 | Andrei | One tool, four users. The same coast reads differently for the public, a student, a sector manager and a researcher. | Ease of use (10), Feasibility (15) |
| 6:00-6:40 | Impact and measurement needs | 5 | Joseph | The tool also says what to measure next: a ranked list of 7 needs, most of them low cost. | Impact (20), Feasibility (15) |
| 6:40-7:00 | Roadmap and close | 5 | Andrei | Built on free open data, runs offline today; a 3-month pilot with NIMRD makes it operational. | Feasibility (15), Presentation (5) |

**5-minute cut:** drop the problem slide to 20 s, merge architecture and canvas into one 1:20 slide (Joseph), demo 2:00, impact and close 0:40.

Teamwork (5 points) is shown by the hand-overs: Andrei opens, Joseph takes the science, Andrei demos, Joseph gives the measurement needs, Andrei closes. Each names the other at the hand-over.

---

## 2. Slide outline (11 slides plus backup)

Style: dark background matching the viewer (#06131D, text #E6EEF3, accent #4CC3E6), Barlow, one idea per slide, no emoji, no icons for decoration, status colours only as small squares with a word. Okabe-Ito for sectors; the overlap ramp from `data/zones/overlap_style.json`.

| # | Title | Content | Visual |
|---|---|---|---|
| 1 | Black Sea Health Viewer | One-sentence pitch; team names and roles; EfxINNOs Challenge 04. | Full-screen viewer screenshot, Overview, dark. |
| 2 | Change is not damage | Temperature swings 17-18 °C every year (annual cycle 8.7-9.1 °C, warmest mid-August). Upwelling, the Danube plume and storms move oxygen, salinity and clarity. Data sit in 5+ portals with different trust. Question: is this change natural, or a pressure? | Joseph's seasonal fit, SST at EUXRo03 (`seasonal/figures/fit_EUXRo03_sst_satellite_monthly.png`). |
| 3 | Five sectors, one coast (Sprint 1) | 330 features in 5 sectors, each with a confidence (official / mapped / assumed; assumed drawn dashed). One buffer per activity, from law, literature or a stated rule. Plain count, no weights. Summer: 76 cells of 250 m with 4 sectors (Olimp, Mangalia, Eforie Nord, 2 Mai). Winter: 2 cells (the Agigea lease). No cell has all 5. Monitoring need per sector in one line each. | QGIS export from `gis/black_sea_pressures.qgz`: summer and winter side by side (or `docs/pressure_zones_map.png`). |
| 4 | Monitoring architecture (Sprint 2) | Parameters: T, S, O2, chl-a, clarity, nutrients, pH, waves, currents, wind, depth. Platforms: offshore buoys, bottle samples, satellite, Copernicus models, EMODnet layers. QC and trust flags per platform and variable, cached store, indicators, viewer. Space: 250 m (zones) to 1-5 km (satellite). Time: daily, 10-day forecast, climatology 1991-2020. | Architecture diagram redrawn from `docs/plan/team_plan.html` (Sources > Data hub (QC, cache) > Indicators > Screening < Pressure zones > Viewer > Users). |
| 5 | Which source to trust | SST: satellite within about 0.45 °C of the buoys (4 buoys, about 5400 days). Salinity: model at the coast, about 1 PSU; offshore buoy salinity fouled. Surface O2: model about 1 mg/L offshore, 2 mg/L at the coast. Chl-a: satellite as reference; buoy fluorescence reads 2-3x high. Nutrients: bottles and climatology only; model nitrate and phosphate not used as values. | Taylor diagram for SST (`validation/figures/taylor_sst.png`) beside a 5-row "reference per variable" table. |
| 6 | From data to decision (Sprint 3) | Canvas: harmonise and QC > indicator vs reference (climatology anomaly, z-score) > threshold labelled OFFICIAL-RO / OFFICIAL-EU / OURS > natural-or-pressure rule chain (8 rules, first match wins) > status and confidence > investigate action > who acts. | Canvas diagram (new, simple boxes and arrows, drawn from SHORTLIST sections 3 and 5). |
| 7 | Natural or pressure? One example | Every bottom-oxygen episode below 4 mg/L in the forecast since Dec 2024 is in the cold season, with bottom salinity 19.1-19.9: rule 3, cold saline intrusion, natural. "Pressure" is used only when no natural driver explains a change. | Viewer screenshot: an open card showing its rule chain. |
| 8 | Live demo (Sprint 4) | Title only, plus the local URL. | 4 small fallback screenshots in a row (Overview, Water, Seabed, Pressures). |
| 9 | One tool, four users | Public: is it fine to swim. Student: how the sea works. Sector manager: my sites, what to check. Researcher: sources, errors, data download. Every value shows unit and origin (measured / satellite / model). | 4 cropped viewer screenshots, one per profile. |
| 10 | What to measure next (Sprint 5) | Joseph's ranked list, top 5 with cost and who: 1 chl-a bottles at the buoys (low, GeoEcoMar and NIMRD); 2 checked coastal O2 sensor (low); 3 post-2021 nutrient bottles (medium, NIMRD); 4 bottom O2 at the mussel farms May-Sep (high); 5 clean the buoy conductivity cells (low). Long satellite SST 1982-2025: +0.56 °C per decade at the buoys (95 % CI 0.46-0.66). | Table from `docs/indicators/methods/MEASUREMENT_NEEDS.md` (origin/data). |
| 11 | Roadmap and limits | Now: working prototype, free open data, offline cache. Next 3 months: pilot with NIMRD (confirm thresholds, add post-2021 monitoring data, QC the coastal buoys), host on a server. Then: Bulgarian and Ukrainian coasts (same Copernicus and EMODnet products), EfxINNOs final in Varna. Limits said openly (see below). | Simple three-step timeline. |

Backup slides (for Q&A only): data sources table; buffer table (`data/zones/buffers.yaml`); salinity and O2 scatter plots; trend figure for SST; the full 8-rule chain; the "to confirm with NIMRD" list.

**Known limits (exact wording for slide 11 and Q&A):**
- Copernicus model nitrate and phosphate are unreliable, so nutrients come from historical samples and climatology.
- Seabed oxygen is model-only (there is no seabed sensor), so its confidence is low.
- The new coastal buoys EUXRoCB0x are not quality-controlled. Station 15480 is on shore.
- Some fishing and shipyard features are assumed (landing points, pound nets, dumping sites) and are drawn dashed.
- The pressure count shows where sectors overlap, not how much impact they cause. AIS covers vessels of 15 m or more only, so small-scale fishing is under-counted near shore.

---

## 3. Live demo script (2:30)

Start state: viewer at `http://localhost:8502`, dark theme, Overview, place Constanța, profile Public, browser full screen, zoom set so the panel and the map both fit the projector (check at 10:30).

| # | Click | Say (one or two sentences) | Time |
|---|---|---|---|
| 1 | Overview, profile Public | "A beach manager opens it and gets one sentence: how the water at Constanța is today compared with a normal day in late November." | 0:15 |
| 2 | Point at the verdict and counts, then the timeline | "Nine indicators, each a square with a word, normal, watch or alert, plus its origin: measured, satellite or model. The timeline covers the last week and the forecast." | 0:20 |
| 3 | Open the Oxygen card (or the card on watch today) | "Open one: the value, the usual range for this date, and the rule chain, which says whether a natural driver explains the change before anything is called a pressure." (Check at 10:20 which card is on watch today and adjust the sentence to what it shows.) | 0:25 |
| 4 | Switch profile to Sector, choose aquaculture | "A mussel farmer sees the same coast through their sites, and what to check: for example a drop-camera transect if bottom oxygen falls to class D." | 0:20 |
| 5 | Water quality, temperature, then chlorophyll | "The 60-day chart against the usual range. Under Sources: which product we trust for this variable, and why the buoy chlorophyll is greyed out." | 0:25 |
| 6 | Coast and seabed, waves | "Colour is wave height, arrows are direction, arrow length is wave period. The depth profile shows the shelf." | 0:15 |
| 7 | Pressures, summer, then winter | "In summer four sectors overlap along the resort coast. Switch to winter: tourism goes off, and the pressure sits at the port approaches." | 0:20 |
| 8 | EN/RO switch (only if merged and tested by 10:15) | "And for local users, in Romanian." | 0:05 |
| 9 | Back to slides | "That is the prototype. What it tells us to measure next: Joseph." | 0:05 |

Fallback, in order:
1. App slow or a page fails: switch to the browser tab with the same page pre-opened (keep one tab per page open before starting).
2. App down or no projector link to the laptop: play the screen recording (2:30, no sound, Andrei narrates) from the desktop, or from Joseph's laptop.
3. No laptop at all: slide 8 screenshots plus slide 9, narrated with the same script.

Basemap tiles are the only online part. With Wi-Fi off the map shows the data layers on a blank background, which still works for the demo.

---

## 4. Q&A preparation

Answer in two or three sentences, give a number, say what is not known. Joseph takes data and validation, Andrei takes product, users and roadmap.

1. **Where do the data come from, and why trust them?** (Joseph) Copernicus Marine (satellite, model, reanalysis), EMODnet Physics buoys, EMODnet Chemistry bottles and climatology, GloFAS Danube discharge, EMODnet and OSM layers for the sectors. Each variable has one reference source chosen by comparison with in situ data, and every value in the app shows its origin.
2. **How do you separate natural variability from a pressure?** (Joseph) Anomalies against a day-of-year climatology, then an 8-rule chain applied in order: model artefact, upwelling, cold saline intrusion, Danube plume, storm, bloom decay, outfall, and only then "possible pressure, investigate". Example: all bottom-oxygen lows since Dec 2024 were cold-season intrusions.
3. **Why no weights in the pressure map?** (Andrei) Weights between sectors are a value judgement we cannot defend in two days, and they hide what is underneath. We built a weighted version first (literature weights), then chose a plain count that anyone can check. Weights can be added with NIMRD later; the v1 is kept.
4. **Why are nutrients not taken from the model?** (Joseph) We tested it: model nitrate gets only the broad seasonal shape (Spearman 0.41 against 35 bottle days) and peaks in February while bottles peak in April; model phosphate has no agreement (Spearman 0.01). So nutrient levels come from bottles and climatology, and we show model nutrients nowhere as values.
5. **Which buoys do you not trust, and why?** (Joseph) The new coastal buoys EUXRoCB0x: oxygen units unclear and saturation 3.6 %, not quality-controlled yet. Station 15480 is on shore, 3.5 °C colder than open water. Offshore buoy salinity shows weeks-long drops that look like conductivity-cell fouling, and buoy chlorophyll reads 2-3x high. They stay visible but greyed out.
6. **What are your validation numbers?** (Joseph) SST: satellite RMSE about 0.45 °C against 4 buoys, bias under 0.15 °C. Salinity: model RMSE 1.1 PSU against 41 coastal bottle days. Surface O2: model about 1 mg/L offshore, 2.3 mg/L at the coast, and it follows the seasons but not day-to-day changes. Bottom O2 has no sensor, so it is not validated.
7. **Are the thresholds official?** (Joseph) Each is labelled: OFFICIAL-RO (Romanian MSFD 2024: D5C2 chlorophyll, D5C5 oxygen, DIN and PO4 P75, Secchi), OFFICIAL-EU (bathing water), or OURS (climatology bands, saturation flags). We ask NIMRD to confirm the RO values.
8. **Who uses it, and what is the value for the blue economy?** (Andrei) Port and dredging managers, mussel farmers, beach and tourism managers, fishers, NIMRD and the environment agency. The value is a shared screen: one place to see conditions, where sectors overlap, and a concrete next check with who should do it, instead of five portals.
9. **Does it scale to other coasts?** (Andrei) The data layer uses basin-wide Copernicus and EMODnet products, so Bulgaria and Ukraine need only their sector layers and local thresholds. The sector zones are the part that needs local work.
10. **What is the role of NIMRD?** (Andrei) Confirm thresholds, give post-2021 monitoring data (bottom O2, nutrients, chl), confirm the coastal-buoy QC and units, and the official lists of aquaculture, dredging and dumping sites. We have the questions written down.
11. **Did you use EfxINNOs data (buoys, AUV, ROV)?** (Joseph) Yes for buoys: the offshore buoys are the independent check for SST, O2, salinity and chlorophyll. ROV and AUV imagery are not in the prototype; the evidence-coverage layer is where ROV habitat labels would go. Say exactly which buoys are EfxINNOs only if confirmed.
12. **What is next, and what would it cost?** (Andrei) A 3-month pilot: NIMRD data, the coastal buoys QC'd, hosting on a server. The measurement list says the cheapest wins are bottle checks at existing buoy visits; the only expensive item is a bottom-oxygen mooring at the mussel farms.

Hard questions to expect: "Is the +0.56 °C per decade significant?" Yes for the 1982-2025 satellite record at the buoys (95 % CI 0.46-0.66); the 10-year buoy records are too short for a trend, and we say so in the app. "Is your app just a dashboard?" No: it adds the rule chain, trust per source and the investigate actions.

---

## 5. Preparation checklist (now to 11:00)

| Time | Task | Owner | Matters for the pitch? |
|---|---|---|---|
| 09:45 | Approve this plan; decide slide tool, speaker split, live or recorded demo | Andrei | yes |
| 09:45 | Ask the organisers: pitch length, Q&A length, own laptop or theirs, HDMI or USB-C | Joseph | yes |
| 09:50-10:25 | Build the slides (11 + backup) from this outline | Claude session, Andrei reviews | yes |
| 09:50 | Export the QGIS summer/winter map (or reuse `docs/pressure_zones_map.png`) | coordinator (QGIS MCP) | yes |
| 09:50 | Copy Joseph's figures for slides 2, 5, 10 into `pitch/assets/` (from `origin/data`, no merge needed) | slides session | yes |
| 10:00 | Viewer feature freeze: viewer-c finishes or stops; restart the server once; no edits after 10:15 | coordinator | yes |
| 10:00 | Decide on PR #3 (Joseph's data branch): merge into `main` only if the viewer runs with it by 10:15; otherwise after the pitch. The slides do not need the merge. | Andrei and Joseph | low |
| 10:15 | Warm cache check: `scripts/preload_cache.py` (0 failures expected), then one offline run with `MARINEKIT_OFFLINE=1` | coordinator | yes |
| 10:20 | Take the 9 viewer screenshots (Overview, open card, 4 profiles, Water, Seabed, Pressures summer and winter) | coordinator | yes |
| 10:25 | Record the 2:30 demo screen recording (QuickTime, no sound), save to the desktop and to a USB stick or Joseph's laptop | Andrei | yes |
| 10:30 | Laptop setup: projector test, mirror display, browser zoom so the panel fits, Do Not Disturb on, close other apps, power cable in | Andrei | yes |
| 10:30 | Default demo state: dark, Overview, Constanța, Public profile; one tab per page pre-opened | Andrei | yes |
| 10:35 | Rehearse once with a timer; cut if over 7:00 | both | yes |
| 10:50 | Second rehearsal of hand-overs and the first 30 s only | both | yes |
| 10:55 | Slides open in presenter view; viewer tab one click away; recording ready | Andrei | yes |

Open items from HANDOVER and whether they matter today:

| Item | Status | Matters for the pitch? |
|---|---|---|
| NIMRD questions (SHORTLIST section 6, pressure_zones to-confirm list) | not asked | Only as a slide 11 line and Q&A 10. If a NIMRD person is free before 10:30, ask questions 2 and 4 (thresholds, coastal buoy QC). Drop question 6 (weights), it is retired. |
| SST in the summary box differs from the temperature card | fixed on `data` (`indicators.sst_display`); viewer not wired yet | Low. Avoid pointing at both numbers in the demo, or label the summary value "map pixel". |
| Clarity card 2.5 m vs text "about 3 m" | fixed on `data` (PR #3) | Low. Do not open the clarity card in the demo unless PR #3 is merged. |
| Shipping-lane hover "buffer 0 m (rule)" | `buffer_label` added on `data`; viewer not wired yet | Low. Do not hover the shipping lane in the demo. |
| Fishing under-counted near shore; ANAR PDFs not read | documented in PR #3 | Yes, as a stated limit (slide 11, Q&A). |

What Joseph must bring: his laptop with the repo and cache as a second demo machine, the validation and seasonal numbers in his head (Q&A 4-6), and the measurement-needs table for slide 10.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Venue Wi-Fi fails | Data run from the cache (offline check at 10:15). Basemap tiles need internet: the map still shows data on a blank background. Screen recording as a fallback. |
| Copernicus catalogue switch at 15:00 | After the pitch; the cache serves the demo. Do not clear `data/cache/` or re-run downloads today. |
| Viewer restarts during viewer-c edits | Freeze at 10:15; restart once and click through every page. No `runOnSave` edits during the pitch. |
| A page errors live | Pre-opened tabs per page; say "this one is from the cache, here is the screenshot" and move on. |
| Projector resolution or colours wash out the dark theme | Test at 10:30; switch the viewer and slides to the Light theme if the room is bright. |
| Time overrun | Hard stops: demo ends at 6:00 whatever the state. The 5-minute cut is rehearsed. Joseph signals at 5:30. |
| Jury asks about weights, nutrients or untrusted data | Prepared answers 3-5 above; backup slides ready. |
| Claims that are too strong | Use only the wording in this plan: "screening of co-location, not impact", "possible pressure, investigate", model nutrients "shape only". |

---

## Decisions for Andrei

1. Slide tool and format: (a) Claude-made slide deck artifact (opens in a browser, exports to PDF/PPTX), (b) PowerPoint file, (c) Google Slides. Recommended: (a) with a PDF export as backup.
2. Speaker split as above (Andrei: problem, pressure map, demo, close; Joseph: architecture, trust, canvas, measurement needs)?
3. Demo: live with the recording as fallback (recommended), or the recording only.
4. Include the EN/RO switch in the demo only if it is merged and tested by 10:15?
