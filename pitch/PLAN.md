# Pitch plan: Black Sea Health Viewer

Pitch today, 24 Nov 2026. Presentations run 11:00-13:00 for up to 5 teams (agenda in the invitation), so plan for **7 minutes plus Q&A**, with a 5-minute cut ready. The brief does not state the length: ask the organisers at 10:00 and pick the version.

Status: plan only. No slides are built until Andrei approves this plan.

The pitch follows the **7 steps on the organisers' deliverables sheet** (step 8, "final presentation", is the pitch itself), one slide per step, and opens with the team's Kumu diagram of how the five sectors interact.

Innovation in one sentence (said at the start and at the end): *A map-first viewer for the Romanian coast that says, for each place and day, whether the water is normal, whether a change is natural or a likely pressure, how much to trust each number, and what to check next, for five blue-economy sectors.*

---

## 1. Pitch structure: 7 steps in 7:00

| Time | Step (organisers' sheet) | Speaker | Key message | Scoring criteria hit |
|---|---|---|---|---|
| 0:00-0:15 | Title | Teammate (third member) | The innovation sentence above. | Presentation (5) |
| 0:15-1:00 | 1. Problem definition | Teammate | The five sectors interact and all depend on the same water (Kumu diagram). Their pressures and natural change (upwelling, the Danube, storms) move the same parameters. The problem: telling natural change from pressure, at a place and a date, from scattered data of uneven trust. | Impact (20) |
| 1:00-1:45 | 2. Relevance for the five sectors | Teammate | Where the sectors overlap: a plain count (0-5), tourism only in summer. What each sector gets from the tool, in one line each. | Integration across sectors (15) |
| 1:45-2:30 | 3. Monitoring architecture | Joseph | Observation technologies, parameters and data flows: buoys, bottles, satellite, Copernicus models and sector layers feed one QC'd, cached data hub. | Technical monitoring logic (20) |
| 2:30-3:15 | 4. Data processing methodology | Joseph | Integration, QC, indicators against reference conditions, then the natural-or-pressure rule chain, ending in an "investigate" action and who acts. | Technical logic (20), Data to decisions (15) |
| 3:15-5:15 | 5. Prototype (live demo) | Andrei | One tool, four users: the same coast reads differently for the public, a sector manager and a researcher. | Ease of use (10), Feasibility (15) |
| 5:15-6:00 | 6. Validation approach | Joseph | Reliability: each source checked against buoys and bottles. Uncertainty: a number per variable. Ecological interpretation: an anomaly is not damage until the rule chain has ruled out natural drivers. | Technical logic (20) |
| 6:00-6:50 | 7. Impact and implementation roadmap | Andrei (users, benefits), Joseph (pilot requirements) | Users and environmental benefits; a 3-month pilot with NIMRD; the ranked list of what to measure next, most of it low cost. | Impact (20), Feasibility (15) |
| 6:50-7:00 | Close | Andrei | The innovation sentence again, and thank you. | Presentation (5) |

Speaker order: teammate (title, 1-2), Joseph (3-4), Andrei (5), Joseph (6), Andrei and Joseph (7), Andrei (close). Three voices, each on the part they built; each names the next speaker at the hand-over, which shows the teamwork. The teammate prepared the sector work and is styling the PowerPoint, so her deck is the master file: slides 4-9 are built in her template.

**5-minute cut:** step 1 to 30 s (Kumu diagram and one sentence), steps 3 and 4 merged into one 1:00 slide, demo 1:30, step 6 to 30 s, step 7 to 40 s.

---

## 2. Slide outline (9 slides plus backup)

One slide per step, no more. Style: dark background matching the viewer (#06131D, text #E6EEF3, accent #4CC3E6), Barlow, no emoji, no decorative icons, status colours only as small squares with a word. Okabe-Ito for sectors; the overlap ramp from `data/zones/overlap_style.json`. The Kumu slide keeps the team's diagram as it is.

| # | Step | Title | Content | Visual |
|---|---|---|---|---|
| 1 | Title | Black Sea Health Viewer | Innovation sentence; team names and roles; EfxINNOs Challenge 04. | Full-screen viewer screenshot, Overview, dark. |
| 2 | 1 | Five sectors, one sea | Positive and negative links between ports, shipyards, tourism, fishing and aquaculture (from the diagram). All of them change, and depend on, the same water. Natural change is large too: temperature swings 17-18 °C a year; upwelling, the Danube plume and storms move oxygen, salinity and clarity. Question: is this change natural, or a pressure? | **The team's Kumu diagram** (screenshot from the existing PowerPoint), with one line of text under it. |
| 3 | 2 | Where the sectors meet | 330 features with a confidence (official / mapped / assumed; assumed drawn dashed). One buffer per activity. Plain count, no weights. Summer: 76 cells of 250 m with 4 sectors (Olimp, Mangalia, Eforie Nord, 2 Mai); winter: 2. No cell has all 5. Per sector, one line: what it gets (ports: dredging plumes and clarity; shipyards: works footprint; tourism: bathing water, blooms, jellyfish; fishing: oxygen and heat at the grounds; aquaculture: bottom oxygen and toxins at the leases). | QGIS export from `gis/black_sea_pressures.qgz`, summer and winter side by side (or `docs/pressure_zones_map.png`). |
| 4 | 3 | Monitoring architecture | Parameters: T, S, O2, chl-a, clarity, nutrients, pH, waves, currents, wind, depth. Technologies: offshore buoys, bottle samples, satellite, Copernicus models and reanalysis, EMODnet and OSM sector layers. Flow: sources > data hub (harmonise, QC, trust flags, cache) > indicators > screening (with pressure zones) > viewer > users. Space 250 m to 5 km; daily, 10-day forecast, climatology 1991-2020. | Architecture diagram redrawn from `docs/plan/team_plan.html`. |
| 5 | 4 | From data to decision | Indicator vs reference (day-of-year climatology anomaly, z-score) > threshold labelled OFFICIAL-RO / OFFICIAL-EU / OURS > rule chain (8 rules, first match wins: model artefact, upwelling, cold saline intrusion, Danube plume, storm, bloom decay, outfall, unexplained) > status and confidence > investigate action > who acts. Example: every bottom-oxygen episode below 4 mg/L in the forecast since Dec 2024 is cold-season, bottom salinity 19.1-19.9: rule 3, natural. | Canvas diagram (simple boxes and arrows, from SHORTLIST sections 3 and 5). |
| 6 | 5 | Prototype | Title and local URL only; the demo does the talking. | 4 small fallback screenshots (Overview, Water, Seabed, Pressures). |
| 7 | 6 | How much to trust each number | SST: satellite within about 0.45 °C of 4 buoys. Salinity: model about 1 PSU at the coast; buoy salinity at EUXRoOB01-03 fouled (EUXRo03, 2013-2023, still usable). Surface O2: model about 1 mg/L offshore, 2 mg/L coast. Chl-a: satellite as reference; buoy fluorescence reads 2-3x high. Nutrients: bottles and climatology only; model nitrate and phosphate never shown as values. Untrusted sensors stay visible, greyed out. | Taylor diagram for SST (`validation/figures/taylor_sst.png`) beside a 5-row "reference per variable" table. |
| 8 | 7 | Impact and pilot | Users: port and dredging managers, mussel farmers, beach managers, fishers, NIMRD, the environment agency, the public. Benefits: one shared screen, earlier and targeted sampling, fewer false alarms. Pilot (3 months, with NIMRD): confirm thresholds, add post-2021 monitoring data, QC the coastal buoys, host on a server. Measure next (top 3): chl-a bottles at buoy visits (low cost), checked coastal O2 sensor (low), bottom O2 at the mussel farms May-Sep (high). Then: Bulgarian and Ukrainian coasts, EfxINNOs final in Varna. | Left: three-step timeline. Right: top-5 measurement needs from `docs/indicators/methods/MEASUREMENT_NEEDS.md` (origin/data). |
| 9 | Close | What we do not claim | The known limits below in 4 short lines, then the innovation sentence. | Text only. |

Backup slides (for Q&A only): data sources table; buffer table (`data/zones/buffers.yaml`); salinity and O2 scatter plots; SST seasonal fit and long-term trend (satellite at the 4 buoy sites, 1982-2025: +0.56 to +0.57 °C per decade, 95 % CI 0.45-0.68); the full 8-rule chain; the "to confirm with NIMRD" list; the 4 profiles side by side.

**Known limits (exact wording for slide 9 and Q&A):**
- Copernicus model nitrate and phosphate are unreliable, so nutrients come from historical samples and climatology.
- Seabed oxygen is model-only (there is no seabed sensor), so its confidence is low.
- The new coastal buoys EUXRoCB0x are not quality-controlled. Station 15480 is on shore.
- Some fishing and shipyard features are assumed (landing points, pound nets, dumping sites) and are drawn dashed.
- The pressure count shows where sectors overlap, not how much impact they cause. AIS covers vessels of 15 m or more only, so small-scale fishing is under-counted near shore.

---

## 3. Live demo script (2:00)

Start state: viewer at `http://localhost:8502`, dark theme, Overview, place Constanța, profile Public, browser full screen, zoom set so the panel and the map both fit the projector (check at 10:30).

| # | Click | Say (one or two sentences) | Time |
|---|---|---|---|
| 1 | Overview, profile Public | "A beach manager opens it and gets one sentence: how the water at Constanța is today compared with a normal day in late November. Nine indicators, each with a status word and its origin: measured, satellite or model." | 0:20 |
| 2 | Open the card on watch today (or Oxygen) | "Open one: the value, the usual range for this date, and the rule chain, which says whether a natural driver explains the change before anything is called a pressure." (Check at 10:20 which card is on watch and adjust.) | 0:25 |
| 3 | Switch profile to Sector, choose aquaculture | "A mussel farmer sees the same coast through their sites, and what to check: for example a drop-camera transect if bottom oxygen falls to class D." | 0:20 |
| 4 | Water quality, chlorophyll, open Sources | "The 60-day chart against the usual range, and which source we trust for this variable: the buoy chlorophyll is greyed out." | 0:20 |
| 5 | Coast and seabed, waves | "Colour is wave height, arrows are direction, arrow length is wave period." | 0:10 |
| 6 | Pressures, summer, then winter | "In summer four sectors overlap along the resort coast. In winter tourism goes off, and the pressure sits at the port approaches." | 0:20 |
| 7 | EN/RO switch (only if merged and tested by 10:15), then back to slides | "And in Romanian for local users. How far can you trust these numbers? Joseph." | 0:05 |

Fallback, in order:
1. App slow or a page fails: switch to the browser tab with the same page pre-opened (keep one tab per page open before starting).
2. App down or no projector link to the laptop: play the screen recording (2:00, no sound, Andrei narrates) from the desktop, or from Joseph's laptop.
3. No laptop at all: slide 6 screenshots, narrated with the same script.

Basemap tiles are the only online part. With Wi-Fi off the map shows the data layers on a blank background, which still works for the demo.

---

## 4. Q&A preparation

Answer in two or three sentences, give a number, say what is not known. Joseph takes data and validation, Andrei takes product, users and roadmap.

1. **Where do the data come from, and why trust them?** (Joseph) Copernicus Marine (satellite, model, reanalysis), EMODnet Physics buoys, EMODnet Chemistry bottles and climatology, GloFAS Danube discharge, EMODnet and OSM layers for the sectors. Each variable has one reference source chosen by comparison with in situ data, and every value in the app shows its origin.
2. **How do you separate natural variability from a pressure?** (Joseph) Anomalies against a day-of-year climatology, then an 8-rule chain applied in order: model artefact, upwelling, cold saline intrusion, Danube plume, storm, bloom decay, outfall, and only then "possible pressure, investigate". Example: all bottom-oxygen lows since Dec 2024 were cold-season intrusions.
3. **Why no weights in the pressure map?** (Andrei) Weights between sectors are a value judgement we cannot defend in two days, and they hide what is underneath. We built a weighted version first (literature weights), then chose a plain count that anyone can check. Weights can be added with NIMRD later; the v1 is kept.
4. **Why are nutrients not taken from the model?** (Joseph) We tested it: model nitrate gets only the broad seasonal shape (Spearman 0.41 against 35 bottle days) and peaks in February while bottles peak in April; model phosphate has no agreement (Spearman 0.01). So nutrient levels come from bottles and climatology, and we show model nutrients nowhere as values.
5. **Which buoys do you not trust, and why?** (Joseph) The new coastal buoys EUXRoCB0x: oxygen units unclear and saturation 3.6 %, not quality-controlled yet. Station 15480 is on shore, 3.5 °C colder than open water. Buoy salinity at EUXRoOB01-03 shows weeks-long drops that look like conductivity-cell fouling (the older EUXRo03 record is usable), and buoy chlorophyll reads 2-3x high. They stay visible but greyed out.
6. **What are your validation numbers?** (Joseph) SST: satellite RMSE about 0.45 °C against 4 buoys, bias under 0.15 °C. Salinity: model RMSE 1.1 PSU against 41 coastal bottle days. Surface O2: model about 1 mg/L offshore, 2.3 mg/L at the coast, and it follows the seasons but not day-to-day changes. Bottom O2 has no sensor, so it is not validated.
7. **Are the thresholds official?** (Joseph) Each is labelled: OFFICIAL-RO (Romanian MSFD 2024: D5C2 chlorophyll, D5C5 oxygen, DIN and PO4 P75, Secchi), OFFICIAL-EU (bathing water), or OURS (climatology bands, saturation flags). We ask NIMRD to confirm the RO values.
8. **Who uses it, and what is the value for the blue economy?** (Andrei) Port and dredging managers, mussel farmers, beach and tourism managers, fishers, NIMRD and the environment agency. The value is a shared screen: one place to see conditions, where sectors overlap, and a concrete next check with who should do it, instead of five portals.
9. **Does it scale to other coasts?** (Andrei) The data layer uses basin-wide Copernicus and EMODnet products, so Bulgaria and Ukraine need only their sector layers and local thresholds. The sector zones are the part that needs local work.
10. **What is the role of NIMRD?** (Andrei) Confirm thresholds, give post-2021 monitoring data (bottom O2, nutrients, chl), confirm the coastal-buoy QC and units, and the official lists of aquaculture, dredging and dumping sites. We have the questions written down.
11. **Did you use EfxINNOs data (buoys, AUV, ROV)?** (Joseph) Yes for buoys: the offshore buoys are the independent check for SST, O2, salinity and chlorophyll. ROV and AUV imagery are not in the prototype; the evidence-coverage layer is where ROV habitat labels would go. Say exactly which buoys are EfxINNOs only if confirmed.
12. **What is next, and what would it cost?** (Andrei) A 3-month pilot: NIMRD data, the coastal buoys QC'd, hosting on a server. The measurement list says the cheapest wins are bottle checks at existing buoy visits; the only expensive item is a bottom-oxygen mooring at the mussel farms.

Hard questions to expect: "Is the +0.56 °C per decade significant?" Yes: 44 years of satellite SST at the 4 buoy sites, 1982-2025, give +0.56 to +0.57 °C per decade (95 % CI 0.45-0.68, p < 0.001); it passes our quality gate as a "climate trend" (20+ years; gate thresholds OURS). It is satellite only. The buoy records (1-5 complete years) and the 10-year model and satellite series at EUXRo03 are too short or not significant, and the app shows no trend for them. "Is your app just a dashboard?" No: it adds the rule chain, trust per source and the investigate actions.

---

## 5. Preparation checklist (now to 11:00)

| Time | Task | Owner | Matters for the pitch? |
|---|---|---|---|
| 09:45 | Approve this plan; decide slide tool, speaker split, live or recorded demo | Andrei | yes |
| 09:50 | Get the teammate's current .pptx (unfinished is fine) into `pitch/`, so slides 4-9 use her template; agree that she owns slides 1-3 and the rest are added after them. Also ask her whether her sector slide already has a map, or should use the QGIS overlap map | Andrei asks the teammate | yes |
| 09:45 | Ask the organisers: pitch length, Q&A length, own laptop or theirs, HDMI or USB-C | Joseph | yes |
| 09:50-10:25 | Build the slides (9 + backup) from this outline | Claude session, Andrei reviews | yes |
| 09:50 | Export the QGIS summer/winter map (or reuse `docs/pressure_zones_map.png`) | coordinator (QGIS MCP) | yes |
| 09:50 | Copy Joseph's figures for slides 7 and 8 (and backup) into `pitch/assets/` (from `origin/data`, no merge needed) | slides session | yes |
| 10:00 | Viewer feature freeze: viewer-c finishes or stops; restart the server once; no edits after 10:15 | coordinator | yes |
| 10:00 | Decide on PR #3 (Joseph's data branch): merge into `main` only if the viewer runs with it by 10:15; otherwise after the pitch. The slides do not need the merge. | Andrei and Joseph | low |
| 10:15 | Warm cache check: `scripts/preload_cache.py` (0 failures expected), then one offline run with `MARINEKIT_OFFLINE=1` | coordinator | yes |
| 10:20 | Take the 9 viewer screenshots (Overview, open card, 4 profiles, Water, Seabed, Pressures summer and winter) | coordinator | yes |
| 10:25 | Record the 2:00 demo screen recording (QuickTime, no sound), save to the desktop and to a USB stick or Joseph's laptop | Andrei | yes |
| 10:30 | Laptop setup: projector test, mirror display, browser zoom so the panel fits, Do Not Disturb on, close other apps, power cable in | Andrei | yes |
| 10:30 | Default demo state: dark, Overview, Constanța, Public profile; one tab per page pre-opened | Andrei | yes |
| 10:35 | Rehearse once with a timer, all three speakers; cut if over 7:00 | all three | yes |
| 10:50 | Second rehearsal of the two hand-overs (teammate to Joseph, Joseph to Andrei) and the first 30 s | all three | yes |
| 10:55 | Slides open in presenter view; viewer tab one click away; recording ready | Andrei | yes |

Open items from HANDOVER and whether they matter today:

| Item | Status | Matters for the pitch? |
|---|---|---|
| NIMRD questions (SHORTLIST section 6, pressure_zones to-confirm list) | not asked | Only as a slide 8 line and Q&A 10. If a NIMRD person is free before 10:30, ask questions 2 and 4 (thresholds, coastal buoy QC). Drop question 6 (weights), it is retired. |
| SST in the summary box differs from the temperature card | fixed on `data` (`indicators.sst_display`); viewer not wired yet | Low. Avoid pointing at both numbers in the demo, or label the summary value "map pixel". |
| Clarity card 2.5 m vs text "about 3 m" | fixed on `data` (PR #3) | Low. Do not open the clarity card in the demo unless PR #3 is merged. |
| Shipping-lane hover "buffer 0 m (rule)" | `buffer_label` added on `data`; viewer not wired yet | Low. Do not hover the shipping lane in the demo. |
| Fishing under-counted near shore; ANAR PDFs not read | documented in PR #3 | Yes, as a stated limit (slide 9, Q&A). |

What Joseph must bring: his laptop with the repo and cache as a second demo machine, the validation and seasonal numbers in his head (Q&A 4-6), and the measurement-needs table for slide 8.

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

1. Slide tool: since the Kumu diagram already lives in a PowerPoint, (a) build the deck as a .pptx and paste the Kumu slide in as slide 2 (recommended, one file, presenter view, works offline), or (b) a slide-deck artifact in the browser with the Kumu diagram as an image and a PDF export as backup. Either way, send the .pptx (or a PNG of the Kumu slide) so it can go in `pitch/assets/`.
2. Speaker split as above: teammate title and steps 1-2; Joseph steps 3, 4, 6 and the pilot requirements in step 7; Andrei step 5 (demo), users and benefits in step 7, and the close.
3. Demo: live with the recording as fallback (recommended), or the recording only.
4. Include the EN/RO switch in the demo only if it is merged and tested by 10:15?
