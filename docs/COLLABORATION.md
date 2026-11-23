# Working in parallel on GitHub

Two people, two branches, merged through pull requests into `main`.

| Who | Branch | Owns (edits freely) | Leaves alone |
|---|---|---|---|
| Andrei: design and app | `design` | `src/viewer/` (except `vectorviz.py` internals), `.streamlit/`, `pitch/`, `docs/plan/` | `src/marinekit/` |
| Colleague: data analysis and checks | `data` | `src/marinekit/` (sources, indicators, datahub, pressure_zones), `scripts/`, `tests/`, `docs/indicators/`, `docs/data_sources/`, `data/zones/` | `src/viewer/` |

The two sides talk only through the interfaces in [plan/WORKFLOW.md](plan/WORKFLOW.md): `indicators.card()`, `datahub.get_series()`, the `data/zones/*.geojson` fields, and `vectorviz.field_layer()`. As long as neither person renames those, the branches don't conflict.

Both people's Claude sessions follow [CLAUDE.md](../CLAUDE.md) at the repo root. Claude Code loads it automatically, so the sessions know the branch areas, the interfaces and the git routine.

## Daily routine
1. Start of each work block: `git switch <your-branch>`, then `git pull origin main` to get the other person's merged work.
2. Work in small steps, and commit often with clear messages.
3. Push your branch: `git push`.
4. When a piece works, open a pull request into `main` (`gh pr create --base main`). The other person glances at it and merges it. Keep pull requests small, and merge at least twice a day.
5. Right after a merge, the other person runs `git pull origin main` on their branch.

## Changing an interface
If the design side needs a new field, e.g. an extra key in a card dict, or the data side wants to rename one:
1. Agree on it first: a short message, plus an issue on GitHub.
2. The data side adds the new field without removing the old one, and merges to `main`.
3. The design side switches to it.
4. Remove the old field later.

## If a conflict happens anyway
Run `git pull origin main` on your branch, and git marks the conflicting lines in the file. Keep both changes where it makes sense, then `git add` the file, `git commit` and `git push`. Ask Claude to resolve it if it's messy.

## Rules
- Never commit secrets: `.streamlit/secrets.toml`, `.env` and Copernicus credentials are git-ignored.
- `data/cache/` is not in git, because it's large and rebuilt with `scripts/preload_cache.py`.
- Each person needs their own free Copernicus Marine account (`.venv/bin/copernicusmarine login`).
- Setup on a new laptop: `uv venv .venv --python 3.12`, then `uv pip install --python .venv/bin/python -r requirements.txt`.
