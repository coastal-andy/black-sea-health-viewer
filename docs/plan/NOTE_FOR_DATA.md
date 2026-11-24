# Note for the data side (Joseph and his Claude session)

From the design coordinator, 23 Nov 2026, evening. Read this after `git pull origin main`. It sums up what happened on `design`, the review of your three commits, and what the viewer needs from `data` next.

## What happened on design
- The viewer was rebuilt in the approved design direction B: dark, map-first, with an optional light theme. It has a left icon rail (Overview, Water, Seabed, Pressures, Methods), the panel on the right, a responsive layout, and caching for speed. The spec and the "Built" note are in `docs/plan/HANDOVER.md`.
- It is in pull request 1, `design` into `main` (https://github.com/coastal-andy/black-sea-health-viewer/pull/1), which is not merged yet. A second round of fixes is in progress: card text, the Wind and Depth layers on Seabed, and colour ramps for the gridded layers.
- **Interfaces unchanged.** `marinekit.indicators`, `datahub` and `pressure_zones`, and the `adapters.py` signatures, are all as before. In `viewer/vectorviz.py`, only the arrow and legend drawing gained an optional `theme` argument; `load_field` and `load_point` are untouched.
- The Water quality page (B2) and the Coast and seabed page (B3) use the existing `datahub` and indicator functions for now. They were built so your analysis can be plugged in without changing the layout.

## Review of your commits on data (954b4a6, 05206ce, 8993603)
- Every file is inside the data area, and `requirements.txt` only gains a line. All 48 tests pass offline (`MARINEKIT_OFFLINE=1`, warm cache).
- The validation, spectra and seasonal reports are clear and honest about their limits. They're useful for the pitch.
- Points to consider before your pull request:
  - The commits add about 22 MB of PNG figures and CSVs (`matched_daily.csv` alone is 19k lines). That's fine for the hackathon, but if the repo gets heavy, regenerate the figures from the scripts instead of committing every one.
  - `pytest` is not in `requirements.txt`, although `CLAUDE.md` tells both sides to run tests. Please add it in your pull request (add-only).

## What the viewer needs from data next
Each item is an additive change. Please keep the existing interfaces working.
1. **Source uncertainty per variable** for the Water page "Sources" section, for example a small function `marinekit.validation.source_summary(variable) -> dict` (or a stable CSV contract on `docs/indicators/validation/metrics.csv`). It should give the trusted source, the typical error (RMSE), the bias and a one-line plain reading. Your interpretation already has the content: SST satellite about 0.45 °C; salinity model about 1 PSU at the coast; chlorophyll satellite as the working reference, with the factor not quantified; O2 model about +/- 0.7 mg/L.
2. **Seasonal cycle** for the "usual range" band and the "Long-term trend" tab: annual and semi-annual amplitude, the date of the maximum, and the trend per decade with its CI and an "enough years?" flag, readable through `datahub` or a small helper.
3. **Sensor trust flags.** Your validation finds that buoy chlorophyll (fluorescence) at OB01-03 and EUXRo03, and buoy salinity at OB01-03, are not reliable. `CLAUDE.md` already treats `EUXRoCB0x` and station 15480 as untrusted. Should these be flagged in `datahub` or `indicators` too (for example via `confidence` or `evidence`), so the cards don't use them? Please decide and note it in `docs/indicators/SHORTLIST.md`.
4. **Small issues seen in the viewer** (data side):
   - The SST in the summary (13.75 °C, gridded field pixel) differs from the temperature card (13.4 °C, L4 at 1.1 km). Pick one source, or label both.
   - The clarity card shows 2.5 m, but its text says "about 3 m".
   - The shipping-lane hover shows "buffer 0 m (rule)".
   - For the pitch: fishing is under-counted near shore (AIS only covers vessels of 15 m or more), and the ANAR scanned PDFs were not read.

When a piece is ready, open a pull request from `data` into `main`. The design side will wire it into the Water and Seabed pages once it's merged.
