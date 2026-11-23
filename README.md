# Black Sea Health Viewer

EfxINNOs Hackathon Romania (Constanța, Nov 2026), Challenge 04 Ecosystem Health. A map-first viewer for the Romanian Black Sea coast: sea conditions, long-term change, anomalies against reference conditions, health cards, and the overlap of five blue-economy sectors.

Run the viewer: `.venv/bin/streamlit run src/viewer/app.py --server.port 8502`. Current state: [docs/STATUS.md](docs/STATUS.md). Working together: [docs/COLLABORATION.md](docs/COLLABORATION.md). Data licences: [DATA_LICENSES.md](DATA_LICENSES.md).

---

## Original starter kit

See [CONTEXT.md](CONTEXT.md) for the event, [notes/](notes/) for lecture notes and [ideas/IDEAS.md](ideas/IDEAS.md) for the idea bank (lead idea: **0, SeabedGuard**).

## Run the dashboard
```bash
.venv/bin/streamlit run src/app.py
```
Open http://localhost:8501. It starts on **synthetic demo data**. Switch to "Upload files" in the sidebar for the real data.

## What's in `src/marinekit/`
| Module | What it does | Matching idea |
|---|---|---|
| `io.py` | Loads CSV, Excel, NetCDF, Parquet or JSON. Recognises column names automatically (temp, sal, do, chl, …), pulls units out of headers, parses time columns, and `describe()` gives a first look at a new dataset | all |
| `geo.py` | Nav-log loader (converts NMEA ddmm to degrees), `geotag()` to give each video frame or image a position, timestamps from filenames or EXIF, track stats, density grid, GeoJSON export for QGIS | 1, 2, 6 |
| `buoy.py` | QC (range and spike checks with flags), rolling robust z-score, event detection (hypoxia, algal bloom, warm episode, low pH, turbidity, anomalies), plain-language alerts, links to the EU marine strategy descriptors | 3, 4 |
| `vision.py` | Video frame sampling, underwater colour enhancement, YOLO and **YOLO-World** detection (type class names, no training needed), CLIP/BioCLIP zero-shot and few-shot classification, label smoothing along a transect | 1, 2, 6 |
| `priority.py` | Sensitive-area scoring per grid cell (habitat value, protected share, diversity; editable weights), threat score kept separate, action classes (Protect & restore now / Protect / Clean up / Monitor), ±20 % weight stability check, candidate MPA areas, GeoJSON export, buoy events summarised as pressures | 0 |
| `assistant.py` | Claude chat over the buoy data. **Not used by the dashboard** (dropped: it needs a paid API key). Kept in case we want it later | 5 |
| `demo_data.py` | Fake buoy series, AUV survey track, litter detections and habitat labels | n/a |

Pretrained weights are stored in `models/`: `yolo11n.pt` and `yolov8s-worldv2.pt`. CLIP downloads on first use.

## Quick use from Python or a notebook
```python
import sys; sys.path.insert(0, "src")
from marinekit import io, buoy, geo
df = buoy.qc(io.load_table("data/their_buoy.csv"))
events = buoy.detect_events(df)
print("\n".join(buoy.alert_text(events)))
```

## Notes
- The thresholds (hypoxia below 2 mg/L, bloom above 10 µg/L, and so on) are generic defaults. Ask the NIMRD lecturers which ones they use.
- The "warm episode" check compares against this dataset's own 90th percentile. Proper marine-heatwave detection needs a 30-year baseline, so call it a proxy in the pitch.
- Habitat values, protected flags and priority weights in `priority.py` are first guesses. Replace them with NIMRD's (editable in the Priorities tab).
- Demo data is fake. Never put it in pitch slides as real results.
