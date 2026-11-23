# Instructions for Claude sessions in this repo

Black Sea Health Viewer: EfxINNOs Hackathon Romania, Challenge 04 Ecosystem Health. Two people work in parallel on two branches. These rules keep their Claude sessions from overwriting each other's work.

Read first: `docs/STATUS.md` (what is done and what's left), `docs/plan/WORKFLOW.md` (interfaces and decisions), `docs/COLLABORATION.md` (the human workflow).

## 0. First-time setup on a new laptop
When the user asks to set up the project, or `.venv/` doesn't exist yet, do these steps in order and report each one:
1. `git switch data` if the user is the data-analysis colleague, or `git switch design` if it's Andrei. Ask if unsure.
2. If `uv` is missing, tell the user to install it with `brew install uv`.
3. `uv venv .venv --python 3.12`, then `uv pip install --python .venv/bin/python -r requirements.txt`.
4. Copernicus Marine login: check with `.venv/bin/copernicusmarine login --check-credentials-valid`. If it isn't valid, ask the user to run `.venv/bin/copernicusmarine login` themselves in a terminal, with their own free account from data.marine.copernicus.eu. Never ask for, type or print their credentials.
5. `.venv/bin/python scripts/preload_cache.py` (run it in the background; the first run takes a while).
6. `.venv/bin/python -m pytest -q tests/test_indicators.py` to confirm everything works.
7. Summarise for the user: the branch they're on, what they own (section 1), and how to start the viewer.

## 1. Check the branch before editing anything
Run `git branch --show-current` at the start of every session, and work only inside your branch's area:

| Branch | Owner | You may edit | Do NOT edit |
|---|---|---|---|
| `design` | Andrei: app and design | `src/viewer/` (everything except `vectorviz.py` data loaders), `.streamlit/`, `pitch/`, `docs/plan/`, `README.md` | anything in `src/marinekit/`, `scripts/`, `tests/`, `data/zones/` |
| `data` | colleague: data analysis and checks | `src/marinekit/` (sources, indicators, datahub, pressure_zones), `scripts/`, `tests/`, `data/zones/`, `docs/indicators/`, `docs/data_sources/`, `docs/pressure_zones.md` | anything in `src/viewer/`, `.streamlit/`, `pitch/` |
| `main` | merge target only | nothing directly: changes reach `main` through pull requests | |

If the task needs a change in the other side's area, don't make it. Write a note at the end of your reply saying exactly what change is needed, so it can go to the other person (or into a GitHub issue).

Shared files that either side may touch with care: `docs/STATUS.md` (append only) and `requirements.txt` (add lines, never remove).

## 2. Interfaces you must not break
The two sides meet only here. Never rename or remove these, and never change their meaning without agreement:
- `marinekit.indicators`: `CARDS`, `card(card_id, lat, lon, date, profile)`, `zone_cards(...)`, and the card dict keys `id, title, status, value, unit, reference, z, evidence, confidence, why, driver_note, investigate, sources, text`.
- `marinekit.datahub`: `get_series`, `get_climatology`, `compare_sources`, `obs_vs_model`.
- `marinekit.pressure_zones`: `season_for_date`, `overlap_at`. The `data/zones/` files and their fields (`sector_features`, `sector_zones`, `overlap_grid` with `n_summer`/`n_winter`, `overlap_summer`/`overlap_winter`, `overlap_style.json`, `sector_sites.json`).
- `viewer.vectorviz`: `load_field`, `load_point`, `field_layer`, `point_chart`.

To change an interface: add the new field or function next to the old one, keep the old one working, say so in the commit message and in your reply, and remove the old one only after the other branch has switched.

## 3. Git routine for every session
1. At the start: `git pull origin main`, to merge the other side's latest work into your branch. Resolve conflicts if any, keeping both sides' intent.
2. Commit small, focused changes with clear messages. Commit only files from your branch's area (check `git status` first).
3. Push your own branch only: `git push origin <branch>`. Never push to `main`, never force-push, never rewrite shared history.
4. When a piece works, offer to open a pull request into `main` with `gh pr create --base main`. Don't merge pull requests yourself unless the user asks.
5. Never commit secrets (`.streamlit/secrets.toml`, `.env`, Copernicus credentials in `~/.copernicusmarine/`), `data/cache/`, model weights, PDFs or .docx files. `.gitignore` covers these; don't override it.

## 4. Running things
```bash
.venv/bin/streamlit run src/viewer/app.py --server.port 8502      # the viewer
.venv/bin/python scripts/preload_cache.py                         # warm the data cache (needed once per laptop, and before an offline demo)
.venv/bin/python -m pytest -q tests/test_indicators.py            # indicator tests (data branch: run before every push)
```
- Setup on a new laptop: `uv venv .venv --python 3.12`, then `uv pip install --python .venv/bin/python -r requirements.txt`, then `.venv/bin/copernicusmarine login`. The person types their own credentials; never handle or print them.
- Use only `.venv/bin/python`. Add a package only if really needed, and then add it to `requirements.txt` in the same commit.
- Data access goes through `src/marinekit/sources/`, which caches every download under `data/cache/`. Keep requests small (a point or small box, short periods).

## 5. Style and content rules
- **No emoji anywhere**: UI, docs, commit messages, chat. Use plain text, bullets, and simple status colours (green / amber / red / grey).
- Keep the UI readable for non-scientists. Every value shows its unit and its origin (measured / satellite / model).
- Science rules, from `docs/indicators/SHORTLIST.md`:
  - label thresholds OFFICIAL-RO / OFFICIAL-EU / OURS
  - apply the natural-vs-pressure rule chain before calling anything a pressure
  - never present Copernicus model nitrate or phosphate as absolute values
  - treat coastal buoys `EUXRoCB0x` and station 15480 as untrusted
- Pressure map: a plain overlap count of the 5 sectors (0-5), with tourism on only from 1 June to 15 September. No weights or composite index.
- Zones carry `confidence` (official / mapped / assumed), and assumed features are drawn dashed.
- Okabe-Ito colours for categories. The overlap ramp comes from `data/zones/overlap_style.json`.

## 6. Before ending a session
- Run what you changed (tests on `data`, the viewer in a browser on `design`).
- Commit and push your branch.
- Tell the user, in a few lines: what changed, what was verified, anything the other side needs to know (interface notes), and whether a pull request is ready.
