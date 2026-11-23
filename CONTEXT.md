# EfxINNOs Regional Hackathon Romania: context

**Where / when:** Constanța, 23–24 Nov 2026 (09:30 start). Held in English. Bring a laptop.
**Host:** NIMRD "Grigore Antipa" (National Institute for Marine Research and Development).
**Project:** EfxINNOs (BSB00193), Interreg NEXT Black Sea Basin 2021–2027, co-funded by the EU.
A Marine Technology Transfer Network for a sustainable Blue Economy in the Black Sea and North Aegean.
**Format:** 5 supported teams of 3–4 people. Winners can go on to the **Final EfxINNOs Hackathon in Varna, Bulgaria**.

## The challenge (from the brochure)
Turn marine monitoring data from the project's platforms into practical digital tools for coastal and marine governance:
- **Smart buoys** (time series: physical/chemical parameters)
- **AUVs** (Autonomous Underwater Vehicles: seabed imagery, transects)
- **ROVs** (Remotely Operated Vehicles: video, images)

Topics they name:
- marine biodiversity mapping
- automated seabed image analysis
- marine litter detection
- ecosystem health assessment
- data visualization
- AI-driven environmental monitoring
- coastal/ecosystem monitoring and restoration
- ocean data processing and visualization
- research for ocean governance

Policy frames to name in the pitch: **Black Sea (Bucharest) Convention**, **European Ocean Pact**, **Blue Economy**.
Also worth citing where it fits: EU **MSFD** (Marine Strategy Framework Directive) descriptors (D1 biodiversity, D2 non-indigenous species, D5 eutrophication, D6 seafloor integrity, D10 litter).

## OUR CHALLENGE: 04 Ecosystem Health (chosen Day 1)
Full English summary and scoring: [docs/challenge/CHALLENGE_04.md](docs/challenge/CHALLENGE_04.md).
- Plan: a **dashboard that fetches and compares data series** from many sources (Copernicus Marine, EMODnet, satellite, buoys), with anomalies against **reference conditions / climatology**, observations vs model comparison, and a **five-sector pressure map** (ports, shipyards, tourism, fishing, aquaculture).
- Options the team starred: A dashboard, B anomaly detection, C coastal water-quality explorer, D risk screening, F AI-assisted. E (benthic viewer) is "maybe".
- Biggest scores: technical monitoring logic 20, environment and blue-growth impact 20, five-sector integration 15, data→decisions 15, pilot feasibility 15.
- Data source research and code: `src/marinekit/sources/`, docs in `docs/data_sources/`.

## What the first presentation said (Day 1): focus on seabed habitats
Full notes: [notes/day1_lecture1_context.md](notes/day1_lecture1_context.md).
- They monitor **seabed ecosystems** (seagrass, algae, fauna). Seagrass is the hero: it strips nitrogen and pumps oxygen (presenter: 1 m² ≈ 10 L O₂/day), and acts as a fish nursery and carbon sink.
- Project objectives: harmonise data and map the coast with underwater platforms; collect new images and video; **digital seabed habitat maps focused on protected species**; **delineate sensitive regions and prioritise potential MPAs**; identify **threats** to seabed habitats.
- So the challenge is probably **imagery → habitat map → sensitive areas / MPA priority → threats**. Lead idea is now idea 0 in [ideas/IDEAS.md](ideas/IDEAS.md).

## Timeline: the real build time is about 3.5 hours
| When | What |
|---|---|
| Day 1, 10:00–13:00 | Lectures (topics TBA: **take notes, the datasets are probably introduced here**) |
| Day 1, 14:00–14:15 | Challenges, expected outputs, **evaluation criteria** |
| Day 1, 14:15–14:30 | Team formation + challenge selection |
| Day 1, 14:30–15:30 | Problem definition + solution design |
| Day 1, 15:30–16:00 | Development, part 1 |
| Day 2, 09:30–10:30 | Development, part 2 |
| Day 2, 10:30–11:00 | Final development + **pitch prep** |
| Day 2, 11:00–13:00 | **Team presentations + jury Q&A** |
| Day 2, 14:30 | Results |

Working in the evening between days is the real advantage.

## Still unknown (fill in as we learn it)
- [ ] Exact challenge statements
- [ ] Evaluation criteria and their weights
- [ ] Dataset formats and access (buoy CSV/NetCDF? AUV image sets? ROV video?)
- [ ] Pitch length and format
- [ ] Team members and their skills
- [x] Lecture topics: first talk was seabed habitats, protected species, MPAs, threats. Next: "uses and analysis"
- [ ] Which habitat classes they use and which count as protected
- [ ] Whether images come with a nav log (needed for mapping)

## Workspace layout
- `docs/`: brochure, challenge sheets, lecture slides
- `notes/`: lecture and mentor notes
- `ideas/`: idea bank and scoring
- `data/`: the datasets we get given
- `src/`: prototype code
- `pitch/`: deck, script, demo plan
