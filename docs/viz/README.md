# Vector visualisation (workstream V)

Module: `src/viewer/vectorviz.py`. Demo: `.venv/bin/python scripts/viz/demo_vectorviz.py` writes the HTML previews in this folder. Direction check: `.venv/bin/python scripts/viz/check_directions.py` writes `direction_check.txt`.

## What it shows
Each quantity is shown in one combined view, not as separate maps or charts.

| | Colour / line | Arrows | Extra |
|---|---|---|---|
| Waves | significant wave height, viridis, 0-4 m | where the waves travel to | arrow length = peak period (3 s short, 10 s long; short = wind sea, long = swell) |
| Currents | surface speed, plasma, 0-0.5 m/s | where the water flows to | a dot instead of an arrow below 0.02 m/s |
| Wind | speed, cividis, 0-20 m/s (discs at reference points) | where the wind blows to | points only: no gridded wind source in the modules |

The colour scales are fixed, so maps from different days can be compared. Map arrows are white with a dark outline, so they read on both the colour field and the grey basemap. They sit on a regular lattice whose step is picked at each zoom, so spacing stays at about 40 px (waves) or 30 px (currents) from zoom 7 to 13. Clicking the sea opens a popup with every value. Each legend shows and hides with its layer.

## API (interface V -> U)
```python
from viewer import vectorviz as vv
ds = vv.load_field(kind, bbox=BBOX_RO, time=None)          # xarray.Dataset, one time step
df = vv.load_point(kind, lat, lon, start, end, source="auto")  # DataFrame, 7-14 days
fg = vv.field_layer(m, ds, kind=None, time=None, name=None, show=True, opacity=0.75,
                    legend=True, legend_pos="bottomright", spacing_px=None)  # folium.FeatureGroup, added to m
fig = vv.point_chart(df, kind, every_hours=None, theme="light", title=None, height=360)  # plotly Figure
fig = vv.combined_chart({"waves": dw, "currents": dc, "wind": dd}, theme="light")  # 3 rows, one time axis
m = vv.base_map()            # optional: Esri light grey basemap fitted to BBOX_RO
```
`kind` is `"waves"`, `"currents"` or `"wind"`. Every dataset and DataFrame has a `dir_to` column: degrees clockwise from north, pointing where the water or air goes. In Streamlit, pass `theme="dark"` when `st.get_option("theme.base") == "dark"`, and wrap the loaders in `st.cache_data`.

## Direction conventions (checked)
- Copernicus wave `VMDR`, Open-Meteo `wave_direction` and ERA5 `wind_direction_10m` give the direction the waves or wind come **from**. The module adds 180 degrees.
- Copernicus `uo/vo` (u, v) and Open-Meteo `current_direction` give the direction the water flows **to**. `dir_to = atan2(u, v)`.
- On screen, the arrow vector is `(sin(dir_to), -cos(dir_to))` (canvas y points down). Web Mercator keeps angles, so compass directions are true on the map. On charts, up = north.

Evidence (`direction_check.txt`, 14 days to 23 Nov 2026):
1. Copernicus VMDR against Open-Meteo/MFWAM wave direction (both "from"): median difference 9 degrees at Constanța and 5 degrees offshore. 98-99 % of hours agree within 45 degrees.
2. Offshore (44.40 N, 29.50 E), wave travel direction against wind travel direction when the wind is 8 m/s or more: median difference 21 degrees, 81 % within 45 degrees. A missing or doubled 180-degree flip would give about 180 degrees. At the Constanța coast the difference is larger (median 62 degrees): near shore, waves refract towards the beach, and westerly offshore winds do not build waves there.
3. Copernicus daily currents against Open-Meteo SMOC daily vector means (speed 0.05 m/s or more): median 17 degrees at Constanța. Offshore it is 58 degrees, but the mean difference is 0: two different models with weak currents, and no sign of a flip.
4. Unit checks: a wave from the north is drawn pointing south; u = +1, v = 0 is drawn pointing east; wind from the west is drawn pointing east.

## Timings (warm cache, Romanian shelf 73 x 89 cells)
| step | seconds |
|---|---|
| `field_layer` waves (image + arrows + legend) | 0.22 (first call includes the matplotlib/PIL import) |
| `field_layer` currents | 0.01 |
| `point_chart` waves, 7 days hourly | 0.2 |
| `load_field` waves, cached / first fetch | 0.03-1 / about 13 (three variables) |
| `load_field` currents, cached / first fetch | 0.03 / about 9 |
| `load_field` wind (7 points) | about 3 (Open-Meteo is re-requested for recent dates; falls back to cache offline) |

HTML sizes: wave map about 130 KB, current map about 100 KB, charts 10-75 KB (plotly.js from the CDN).

## Previews in this folder
- `wave_map.html`: latest analysis hour (23 Nov 2026 14:00 UTC). Hs 0.7-2.7 m, waves coming from SSE to SW and travelling north to north-east, Tp about 6-8 s.
- `current_map.html`: 23 Nov daily mean. Northward coastal jet off Mangalia (about 0.4 m/s), eddies offshore.
- `combined_map.html`: waves (on), currents (off) and wind discs (on) in one map with a layer switcher.
- `wave_chart.html`, `current_chart.html`, `wind_chart.html`, `combined_chart.html`: 7 days at Constanța (44.17 N, 28.72 E). `wave_chart_dark.html` is the dark theme.

## Known limits
- Wind is points only (the 7 reference STATIONS). A gridded wind layer needs a gridded source. Open-Meteo accepts many coordinates in one request, so a 0.25-degree grid over the shelf is one call, but that has to be added to `open_data.py` by the main session.
- Currents are daily means (`phy_cur` is P1D), so the current chart has one arrow per day. `load_point("currents", ..., source="open-meteo")` gives hourly SMOC currents instead.
- If both the wave and current colour fields are switched on, the top one hides the other. Show one field at a time; arrows from both stay readable.
- The colour field shows the 2.5 km model cells. The coastline looks stepped at zoom 11 and above.
- CartoDB tiles now need an API key in folium 1.0, so `base_map()` uses Esri Light Gray.
- The custom arrow layer is plain Leaflet JS inside folium (a `folium.map.Layer` subclass). It is checked visually in standalone HTML. For Streamlit, `streamlit_folium` was checked at code level only: the JS it generates defines `L.VectorArrows`, creates the layer and adds it to the feature group. It has not been seen rendered inside Streamlit (the browser pane refused the test port). `scripts/viz/st_vectorviz_check.py` is a ready test page. Use `st_folium(m, returned_objects=["last_clicked"])` so panning does not rerun the app.

## Optional alternative for waves (not built)
An animated particle layer: short white streaks move along the wave travel direction, with streak speed set by peak period (swell moves faster than wind sea, as real wave groups do) and streak density set by Hs. It fits into the same canvas layer as about 60 more lines of JS (a requestAnimationFrame loop over a few thousand particles, re-seeded inside the sea mask). It catches the eye in a demo, but a moving map is harder to read for non-scientists and costs CPU in Streamlit. I would offer it as an opt-in "animate" switch, keeping the arrows as the default.
