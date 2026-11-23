"""EfxINNOs hackathon starter dashboard.

Run:  .venv/bin/streamlit run src/app.py
Tabs: Buoy data · Map · Detection (ROV/AUV litter) · Habitat (seabed classification) · Priorities (sensitive areas / MPA candidates)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent))
from marinekit import buoy, geo, io, priority  # noqa: E402
from marinekit import demo_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Black Sea Monitor", layout="wide")

PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]  # Okabe-Ito
HAB_COLORS = {"seagrass": "#009E73", "brown_algae": "#8C510A", "phyllophora": "#CC79A7", "algae": "#9BD39B", "mussel_bed": "#000000",
              "rock": "#666666", "shell_debris": "#F0E442", "sand": "#E69F00", "mud": "#0072B2", "litter": "#D55E00", "water_column": "#BBBBBB"}
SEV_COLOR = {"high": "rgba(213,94,0,0.25)", "medium": "rgba(230,159,0,0.18)", "low": "rgba(240,228,66,0.12)"}


# ------------------------------------------------------------------ helpers ---

def save_upload(f) -> Path:
    p = UPLOADS / f.name
    p.write_bytes(f.getbuffer())
    return p


@st.cache_data(show_spinner=False)
def load_buoy(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = io.load_table(path)
    attrs = dict(raw.attrs)
    clean = buoy.qc(raw)
    clean.attrs.update(attrs)
    return raw, clean


@st.cache_data(show_spinner=False)
def events_for(path: str, th: dict) -> pd.DataFrame:
    _, clean = load_buoy(path)
    return buoy.detect_events(clean, buoy.Thresholds(**th))


@st.cache_data(show_spinner=False)
def load_points(path: str) -> pd.DataFrame:
    return io.load_table(path, set_index=False)


@st.cache_resource(show_spinner="Loading detector…")
def get_detector(weights: str, classes: tuple[str, ...] | None):
    from marinekit.vision import Detector

    return Detector(weights, list(classes) if classes else None)


@st.cache_resource(show_spinner="Loading embedding model…")
def get_embedder(name: str):
    from marinekit.vision import Embedder

    return Embedder(name)


def ts_figure(df: pd.DataFrame, variables: list[str], events: pd.DataFrame | None = None, title: str = "") -> go.Figure:
    units = df.attrs.get("units", {})
    fig = make_subplots(rows=len(variables), cols=1, shared_xaxes=True, vertical_spacing=0.03)
    for i, v in enumerate(variables, 1):
        fig.add_trace(go.Scattergl(x=df.index, y=df[v], mode="lines", name=buoy.LABELS.get(v, v),
                                   line=dict(width=1.2, color=PALETTE[(i - 1) % len(PALETTE)])), row=i, col=1)
        fig.update_yaxes(title_text=f"{v} [{units.get(v, '')}]" if units.get(v) else v, row=i, col=1)
        if events is not None and len(events):
            for _, e in events[(events.variable == v) & (events.kind != "anomaly")].iterrows():
                fig.add_vrect(x0=e.start, x1=e.end + pd.Timedelta("1h"), fillcolor=SEV_COLOR.get(e.severity), line_width=0, row=i, col=1)
            an = events[(events.variable == v) & (events.kind == "anomaly")]
            if len(an):
                fig.add_trace(go.Scatter(x=an.peak_time, y=an.peak, mode="markers", marker=dict(color="#D55E00", size=7, symbol="x"),
                                         name=f"{v} anomaly", showlegend=False), row=i, col=1)
    fig.update_layout(height=max(260, 190 * len(variables)), margin=dict(l=10, r=10, t=30 if title else 10, b=10),
                      title=title, showlegend=False)
    return fig


def base_map(center=geo.CONSTANTA, zoom=11) -> folium.Map:
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True, max_zoom=19)
    esri = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"
    folium.TileLayer(esri.format("Ocean/World_Ocean_Base"), attr="Esri, GEBCO, NOAA", name="Esri Ocean (bathymetry)", max_native_zoom=13, max_zoom=19, show=False).add_to(m)
    folium.TileLayer(esri.format("World_Imagery"), attr="Esri World Imagery", name="Satellite", max_zoom=19, show=False).add_to(m)
    return m


def add_track(m, nav: pd.DataFrame, color="#0072B2", name="AUV track"):
    pts = nav[["lat", "lon"]].dropna().values[::3].tolist()
    if pts:
        folium.PolyLine(pts, color=color, weight=2, opacity=0.8, tooltip=name).add_to(folium.FeatureGroup(name=name).add_to(m))


def add_points(m, pts: pd.DataFrame, color_col: str, name: str, radius=4):
    fg = folium.FeatureGroup(name=name).add_to(m)
    cats = list(pd.unique(pts[color_col].dropna()))
    cmap = {c: HAB_COLORS.get(c, PALETTE[i % len(PALETTE)]) for i, c in enumerate(cats)}
    for _, r in pts.dropna(subset=["lat", "lon"]).iterrows():
        tip = " · ".join(f"{k}: {r[k]}" for k in (color_col, "conf", "depth", "time") if k in r and pd.notna(r[k]))
        folium.CircleMarker([r.lat, r.lon], radius=radius, color=cmap.get(r[color_col], "#555"), fill=True, fill_opacity=0.8,
                            weight=0, tooltip=tip).add_to(fg)
    legend = "".join(f"<div><span style='display:inline-block;width:10px;height:10px;background:{c};margin-right:6px;border-radius:50%'></span>{k}</div>"
                     for k, c in cmap.items())
    m.get_root().html.add_child(folium.Element(
        f"<div style='position:absolute;bottom:20px;left:20px;z-index:9999;background:white;color:#222;padding:8px 10px;border-radius:6px;font:12px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)'><b>{name}</b>{legend}</div>"))
    return cmap


def add_density(m, pts: pd.DataFrame, cell_m: float, name="Density"):
    g = geo.grid_density(pts, cell_m)
    if g.empty:
        return
    fg = folium.FeatureGroup(name=f"{name} ({cell_m:.0f} m cells)").add_to(m)
    mx = g.n.max()
    lat0 = g.lat.mean()
    dlat = cell_m / 111_320 / 2
    dlon = cell_m / (111_320 * np.cos(np.radians(lat0))) / 2
    for _, r in g.iterrows():
        a = 0.15 + 0.7 * r.n / mx
        folium.Rectangle([[r.lat - dlat, r.lon - dlon], [r.lat + dlat, r.lon + dlon]], color=None, fill=True,
                         fill_color="#D55E00", fill_opacity=a, tooltip=f"{int(r.n)} items").add_to(fg)


def add_cells(m, cells: pd.DataFrame, color_by: str = "action", name: str = "Grid cells"):
    """Draw scored grid cells: coloured by action class, or by sensitivity / threat (0-1, white→colour)."""
    fg = folium.FeatureGroup(name=name).add_to(m)
    cm, lat0 = cells.attrs["cell_m"], cells.attrs["lat0"]
    ramp = {"sensitivity": "#009E73", "threat": "#D55E00"}
    for _, r in cells.iterrows():
        sq = priority._cell_square(r.gx, r.gy, cm, lat0)
        if color_by == "action":
            col = priority.ACTION_COLORS.get(r.action, "#999")
            op = 0.25 if r.action in ("Monitor", "Insufficient data") else 0.65
        else:
            v = r[color_by]
            col, op = ramp[color_by], (0.08 if pd.isna(v) else 0.1 + 0.75 * float(v))
        tip = (f"<b>{r.action}</b><br>sensitivity {r.sensitivity:.2f} ({r.sens_class}) · threat {r.threat:.2f}<br>"
               f"{r.habitats}<br>{int(r.n_obs)} images · {r.threat_items:g} threat items"
               + (f" · stability {r.stability:.0%}" if "stability" in r and pd.notna(r.stability) else ""))
        folium.Polygon([[y, x] for x, y in sq], color=None, fill=True, fill_color=col, fill_opacity=op, tooltip=tip).add_to(fg)


def add_areas(m, cells: pd.DataFrame, areas: pd.DataFrame, name: str = "Candidate MPAs"):
    fg = folium.FeatureGroup(name=name).add_to(m)
    cm, lat0 = cells.attrs["cell_m"], cells.attrs["lat0"]
    for _, a in areas.iterrows():
        tip = f"<b>Candidate area {a.area_id}</b>: {a.area_ha} ha · {a.main_habitats} · {a.action}"
        for gx, gy in a.cells:
            sq = priority._cell_square(gx, gy, cm, lat0)
            folium.Polygon([[y, x] for x, y in sq], color="#000000", weight=1.5, fill=False, tooltip=tip).add_to(fg)
        folium.Marker([a.lat, a.lon], icon=folium.DivIcon(html=f"<div style='font:bold 13px sans-serif;color:#000;"
                      f"background:#fff;border:1px solid #000;border-radius:50%;width:20px;height:20px;text-align:center;line-height:18px'>{a.area_id}</div>"),
                      tooltip=tip).add_to(fg)


def fit(m, df, width_px: int = 900, height_px: int = 500):
    """Centre and zoom the map on the data. Computed in Python because Leaflet's fitBounds breaks
    for maps in tabs that are hidden when the page loads (zero-size container -> max zoom)."""
    d = df.dropna(subset=["lat", "lon"])
    if not len(d):
        return
    lat_c, lon_c = (d.lat.min() + d.lat.max()) / 2, (d.lon.min() + d.lon.max()) / 2
    lon_span = max(d.lon.max() - d.lon.min(), 1e-4)
    lat_span = max(d.lat.max() - d.lat.min(), 1e-4) / np.cos(np.radians(lat_c))
    zoom = np.log2(min(width_px / lon_span, height_px / lat_span) * 360 / 256)
    m.location = [float(lat_c), float(lon_c)]
    m.options["zoom"] = int(np.clip(np.floor(zoom - 0.3), 2, 18))


# ------------------------------------------------------------------ sidebar ---

st.sidebar.title("Black Sea Monitor")
st.sidebar.caption("EfxINNOs hackathon starter · buoys · AUV · ROV")

demo = demo_data.OUT
if not (demo / "buoy_constanta_demo.csv").exists():
    demo_data.write_all()

src = st.sidebar.radio("Data source", ["Demo data (synthetic)", "Upload files"], index=0)
buoy_path = nav_path = det_path = hab_path = None
if src.startswith("Demo"):
    buoy_path, nav_path = str(demo / "buoy_constanta_demo.csv"), str(demo / "auv_nav_demo.csv")
    det_path, hab_path = str(demo / "litter_detections_demo.csv"), str(demo / "habitat_track_demo.csv")
    st.sidebar.warning("Synthetic demo data. Not real measurements.")
else:
    exts = ["csv", "tsv", "txt", "xlsx", "xls", "nc", "parquet", "json"]
    f = st.sidebar.file_uploader("Buoy time series", type=exts)
    if f:
        buoy_path = str(save_upload(f))
    f = st.sidebar.file_uploader("AUV/ROV navigation log (time, lat, lon, depth)", type=exts)
    if f:
        nav_path = str(save_upload(f))

with st.sidebar.expander("Event thresholds"):
    th = dict(
        hypoxia_mgl=st.number_input("Hypoxia DO < (mg/L)", value=2.0, step=0.5),
        low_oxygen_mgl=st.number_input("Low-oxygen DO < (mg/L)", value=5.0, step=0.5),
        bloom_chl=st.number_input("Bloom chl > (µg/L)", value=10.0, step=1.0),
        heatwave_pct=st.number_input("Warm episode percentile", value=90.0, step=1.0),
        heatwave_days=int(st.number_input("Warm episode min days", value=5, step=1)),
        turbidity_ntu=st.number_input("Turbidity > (NTU)", value=50.0, step=5.0),
        anomaly_z=st.number_input("Anomaly |z| >", value=5.0, step=0.5),
    )

nav = geo.load_nav(nav_path) if nav_path else None

tab_buoy, tab_map, tab_det, tab_hab, tab_pri = st.tabs(["Buoy data", "Map", "Detection", "Habitat", "Priorities"])

# ------------------------------------------------------------------ buoy tab ---

with tab_buoy:
    if not buoy_path:
        st.info("Upload a buoy file in the sidebar (CSV/Excel/NetCDF). Columns are auto-recognised.")
    else:
        raw, clean = load_buoy(buoy_path)
        ev = events_for(buoy_path, th)
        vars_ = buoy.numeric_vars(clean)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Records", f"{len(clean):,}")
        c2.metric("Period", f"{clean.index.min():%d %b} → {clean.index.max():%d %b %Y}")
        c3.metric("High-severity events", int((ev.severity == "high").sum()))
        c4.metric("All events", len(ev))

        left, right = st.columns([3, 2])
        with left:
            default = [v for v in ["temp", "do", "chl", "turb"] if v in vars_] or vars_[:3]
            sel = st.multiselect("Variables", vars_, default=default)
            show_raw = st.toggle("Show raw (before QC)", value=False)
            if sel:
                d = raw if show_raw else clean
                d.attrs.update(clean.attrs)
                st.plotly_chart(ts_figure(d, sel, None if show_raw else ev), use_container_width=True)
        with right:
            st.subheader("Alerts")
            alerts = ev[ev.kind != "anomaly"].head(12)
            sev_md = {"high": "red", "medium": "orange", "low": "gray"}
            for sev, line in zip(alerts.severity, buoy.alert_text(alerts, severity_prefix=False)):
                st.markdown(f":{sev_md.get(sev, 'gray')}[**{str(sev).upper()}**] {line}")
            with st.expander(f"Sensor anomalies ({int((ev.kind == 'anomaly').sum())})"):
                st.dataframe(ev[ev.kind == "anomaly"], hide_index=True, use_container_width=True)

        with st.expander("Dataset overview (column mapping, units, coverage)"):
            st.dataframe(io.describe(raw), hide_index=True, use_container_width=True)
            qc_cols = [c for c in clean.columns if c.endswith("_qc")]
            if qc_cols:
                st.caption("QC flags: 1 good · 3 spike · 4 out of range · 9 missing")
                st.dataframe(clean[qc_cols].apply(lambda s: s.value_counts()).fillna(0).astype(int), use_container_width=True)
        st.download_button("Download events (CSV)", ev.to_csv(index=False), "events.csv", "text/csv")

# ------------------------------------------------------------------- map tab ---

with tab_map:
    m = base_map()
    layers = []
    if buoy_path:
        _, clean = load_buoy(buoy_path)
        if {"lat", "lon"} <= set(clean.columns):
            folium.Marker([clean.lat.iloc[0], clean.lon.iloc[0]], tooltip="Smart buoy",
                          icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
            layers.append("buoy")
    if nav is not None:
        add_track(m, nav)
        layers.append("track")
        fit(m, nav)
    view = st.radio("Overlay", ["Litter detections", "Litter density", "Habitat"], horizontal=True)
    if view.startswith("Litter") and det_path:
        dets = load_points(det_path)
        if view == "Litter density":
            add_density(m, dets, st.slider("Cell size (m)", 10, 200, 50, 10), "Litter density")
        else:
            add_points(m, dets, "label", "Litter detections")
    if view == "Habitat" and hab_path:
        add_points(m, load_points(hab_path), "pred", "Habitat", radius=3)
    folium.LayerControl(collapsed=True).add_to(m)
    st_folium(m, height=620, use_container_width=True, returned_objects=[])
    if nav is not None:
        s = geo.track_stats(nav)
        st.caption(f"Track: {s['length_m']/1000:.2f} km · {s['duration_min']:.0f} min · depth {s.get('depth_min', 0):.1f}–{s.get('depth_max', 0):.1f} m")

# ------------------------------------------------------------- detection tab ---

with tab_det:
    st.markdown("Detect litter or objects in **ROV/AUV video or images**, then geotag each detection from the nav log.")
    mode = st.selectbox("Model", ["Open-vocabulary (YOLO-World: type classes)", "COCO YOLO11n (generic objects)", "Custom weights (.pt path)"])
    classes = None
    if mode.startswith("Open"):
        from marinekit.vision import LITTER_CLASSES

        classes = tuple(c.strip() for c in st.text_input("Classes (comma-separated)", ", ".join(LITTER_CLASSES)).split(",") if c.strip())
        weights = "yolov8s-worldv2.pt"
    elif mode.startswith("COCO"):
        weights = "yolo11n.pt"
    else:
        weights = st.text_input("Weights path", str(ROOT / "models" / "best.pt"))
    c1, c2, c3 = st.columns(3)
    conf = c1.slider("Confidence", 0.05, 0.9, 0.2, 0.05)
    every_s = c2.number_input("Video: sample every (s)", value=1.0, min_value=0.1, step=0.5)
    enhance = c3.toggle("Underwater enhancement", value=True)
    files = st.file_uploader("Images or one video", type=["jpg", "jpeg", "png", "tif", "mp4", "mov", "avi", "mkv"], accept_multiple_files=True)
    vid_start = st.text_input("Video start time (for geotagging, e.g. 2026-09-10 09:00:00)", "") if nav is not None else ""

    if files and st.button("Run detection", type="primary"):
        from marinekit import vision

        det = get_detector(weights, classes)
        imgs, ids, times = [], [], []
        vids = [f for f in files if f.name.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))]
        if vids:
            vp = save_upload(vids[0])
            with st.spinner("Extracting frames…"):
                for i, t, fr in vision.iter_video_frames(vp, every_s=every_s, max_frames=600):
                    imgs.append(fr); ids.append(f"frame_{i}"); times.append(t)
            if vid_start:
                times = [pd.Timestamp(vid_start) + pd.Timedelta(seconds=t) for t in times]
            else:
                times = [None] * len(times)
        else:
            for f in files:
                p = save_upload(f)
                imgs.append(p); ids.append(f.name)
                times.append(geo.time_from_filename(f.name) or geo.time_from_exif(p))
        if enhance:
            imgs = [vision.enhance_underwater(im) for im in imgs]
        prog = st.progress(0.0, "Detecting…")
        parts = []
        for k in range(0, len(imgs), 16):
            parts.append(det.detect(imgs[k:k + 16], conf=conf, ids=ids[k:k + 16]))
            prog.progress(min(1.0, (k + 16) / len(imgs)))
        boxes = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        st.session_state["det_result"] = dict(boxes=boxes, imgs=dict(zip(ids, imgs)), times=dict(zip(ids, times)))

    res = st.session_state.get("det_result")
    if res:
        boxes = res["boxes"]
        st.success(f"{len(boxes)} detections in {boxes.image_id.nunique() if len(boxes) else 0} of {len(res['imgs'])} images/frames")
        if len(boxes):
            st.bar_chart(boxes.label.value_counts())
            from marinekit.vision import Detector

            shown = list(dict.fromkeys(boxes.image_id))[:12]
            cols = st.columns(3)
            for j, iid in enumerate(shown):
                cols[j % 3].image(Detector.annotate(res["imgs"][iid], boxes[boxes.image_id == iid]), caption=str(iid), use_container_width=True)
            per_img = boxes.groupby("image_id").agg(n=("label", "size"), labels=("label", lambda s: ", ".join(sorted(set(s))))).reset_index()
            per_img["time"] = per_img.image_id.map(res["times"])
            if nav is not None and per_img.time.notna().any():
                tagged = geo.geotag(per_img.time, nav)
                per_img[["lat", "lon", "depth"]] = tagged[["lat", "lon", "depth"]].values
                m2 = base_map(); add_track(m2, nav); add_points(m2, per_img.assign(label=per_img.labels), "label", "Detections"); fit(m2, nav)
                st_folium(m2, height=450, use_container_width=True, returned_objects=[])
                st.download_button("Download GeoJSON (QGIS)", json.dumps(geo.to_geojson(per_img)), "detections.geojson")
            st.download_button("Download boxes (CSV)", boxes.to_csv(index=False), "boxes.csv", "text/csv")

# --------------------------------------------------------------- habitat tab ---

with tab_hab:
    st.markdown("Zero-shot **seabed habitat / species** labelling from AUV/ROV stills using CLIP or BioCLIP. Edit the prompts to fit what NIMRD cares about.")
    from marinekit.vision import HABITAT_CLASSES, SPECIES_CLASSES

    c1, c2 = st.columns([1, 2])
    model_name = c1.selectbox("Model", ["clip-b32", "bioclip"])
    preset = c1.selectbox("Class set", ["Habitats", "Species"])
    prompts = c2.text_area("Classes → prompts (JSON)", json.dumps(HABITAT_CLASSES if preset == "Habitats" else SPECIES_CLASSES, indent=1), height=220)
    hfiles = st.file_uploader("Seabed images", type=["jpg", "jpeg", "png", "tif"], accept_multiple_files=True, key="hab")
    folder = st.text_input("…or a local folder path with images", "")
    smooth = st.slider("Transect smoothing window (frames)", 1, 15, 1, 2)
    if (hfiles or folder) and st.button("Classify", type="primary"):
        from marinekit import vision

        paths = [save_upload(f) for f in hfiles] if hfiles else vision.list_images(folder)
        emb = get_embedder(model_name)
        with st.spinner(f"Embedding {len(paths)} images…"):
            E = emb.embed_images([vision.enhance_underwater(p) for p in paths])
        out = emb.zero_shot(E, json.loads(prompts))
        out.insert(0, "file", [p.name for p in paths])
        out.insert(1, "time", [geo.time_from_filename(p.name) or geo.time_from_exif(p) for p in paths])
        if smooth > 1:
            out = out.sort_values("time") if out.time.notna().all() else out
            out["pred"] = vision.smooth_labels(out.pred, smooth)
        st.session_state["hab_result"] = (out, {p.name: p for p in paths})

    hr = st.session_state.get("hab_result")
    if hr:
        out, pmap = hr
        st.bar_chart(out.pred.value_counts())
        cols = st.columns(4)
        for j, (_, r) in enumerate(out.head(16).iterrows()):
            cols[j % 4].image(str(pmap[r.file]), caption=f"{r.pred} ({r.conf:.2f})", use_container_width=True)
        st.dataframe(out, hide_index=True, use_container_width=True)
        if nav is not None and out.time.notna().any():
            tagged = geo.geotag(out.time, nav)
            out[["lat", "lon"]] = tagged[["lat", "lon"]].values
            m3 = base_map(); add_track(m3, nav); add_points(m3, out, "pred", "Habitat"); fit(m3, nav)
            st_folium(m3, height=450, use_container_width=True, returned_objects=[])
        st.download_button("Download labels (CSV)", out.to_csv(index=False), "habitat_labels.csv", "text/csv")

# ------------------------------------------------------------ priorities tab ---

with tab_pri:
    st.markdown("**Sensitive areas and MPA candidates.** Each grid cell is scored for **sensitivity** (habitat value, protected habitat share, "
                "habitat diversity) and, separately, **threat** (litter, ghost nets, invasive species). Together they give an action class. "
                "Touching high-sensitivity cells become candidate protected areas.")

    # habitat points: Habitat-tab result (if geotagged) > uploaded CSV > demo
    hab_pts, src_note = None, ""
    hr = st.session_state.get("hab_result")
    if hr is not None and nav is not None and hr[0].time.notna().any():
        o = hr[0].copy()
        o[["lat", "lon"]] = geo.geotag(o.time, nav)[["lat", "lon"]].values
        hab_pts, src_note = o, "Habitat tab results (geotagged from the nav log)"
    c1, c2 = st.columns(2)
    up_h = c1.file_uploader("Habitat points CSV (lat, lon, pred)", type=["csv", "xlsx"], key="pri_hab")
    up_t = c2.file_uploader("Threat points CSV (lat, lon, label)", type=["csv", "xlsx"], key="pri_thr")
    if up_h:
        hab_pts, src_note = load_points(str(save_upload(up_h))), up_h.name
    elif hab_pts is None and hab_path:
        hab_pts, src_note = load_points(hab_path), "demo habitat track (synthetic)"

    thr_pts, thr_note = None, "none"
    dr = st.session_state.get("det_result")
    if dr is not None and len(dr["boxes"]) and nav is not None:
        b = dr["boxes"].copy()
        b["time"] = b.image_id.map(dr["times"])
        if b.time.notna().any():
            b[["lat", "lon"]] = geo.geotag(b.time, nav)[["lat", "lon"]].values
            thr_pts, thr_note = b, "Detection tab results"
    if up_t:
        thr_pts, thr_note = load_points(str(save_upload(up_t))), up_t.name
    elif thr_pts is None and det_path:
        thr_pts, thr_note = load_points(det_path), "demo litter detections (synthetic)"

    if hab_pts is None:
        st.info("Needs habitat points: run the Habitat tab on images with a nav log, or upload a CSV with lat, lon and pred columns.")
    else:
        if "pred" not in hab_pts and "label" in hab_pts:
            hab_pts = hab_pts.rename(columns={"label": "pred"})
        st.caption(f"Habitat: {src_note} · Threats: {thr_note}")
        with st.expander("Settings: weights, habitat values, grid", expanded=False):
            a, b, c, d = st.columns(4)
            w = dict(value=a.slider("Weight: habitat value", 0.0, 1.0, 0.5, 0.05),
                     protected=b.slider("Weight: protected share", 0.0, 1.0, 0.3, 0.05),
                     diversity=c.slider("Weight: diversity", 0.0, 1.0, 0.2, 0.05))
            cell_m = d.select_slider("Cell size (m)", [20, 25, 50, 75, 100, 200], 50)
            min_obs = d.number_input("Min images per cell", 1, 50, 3)
            st.caption("Weights are renormalised to sum to 1. Values and protected flags are first guesses: replace them with NIMRD's.")
            table_df = pd.DataFrame([(k, v, p, n) for k, (v, p, n) in priority.HABITAT_TABLE.items()],
                                    columns=["habitat", "value", "protected", "note"])
            extra = sorted(set(hab_pts.pred.dropna()) - set(table_df.habitat) - priority.IGNORE_LABELS)
            if extra:
                table_df = pd.concat([table_df, pd.DataFrame({"habitat": extra, "value": 0.3, "protected": False, "note": "added: set a value"})], ignore_index=True)
            table_df = st.data_editor(table_df, hide_index=True, use_container_width=True, key="hab_table",
                                      column_config={"value": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.05)})
        table = {r.habitat: (float(r.value), bool(r.protected), str(r.note)) for r in table_df.itertuples()}
        try:
            cells = priority.stability(priority.score_cells(hab_pts, thr_pts, cell_m=cell_m, weights=w, habitat_table=table, min_obs=int(min_obs)))
        except ValueError as e:
            st.error(str(e))
            cells = None
        if cells is not None:
            areas = priority.candidate_areas(cells)
            cm = cells.attrs["cell_m"]
            hi = cells[cells.sens_class == "high"]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(f"High-sensitivity seabed ({len(hi)} of {int(cells.valid.sum())} cells)", f"{len(hi) * cm * cm / 10_000:.2f} ha")
            k2.metric("Candidate MPAs", len(areas))
            k3.metric("Cells to protect & restore now", int((cells.action == "Protect & restore now").sum()))
            k4.metric("Cells keeping their class if weights shift ±20 %", f"{1 - cells.attrs['changed_share']:.0%}")

            color_by = st.radio("Colour cells by", ["action", "sensitivity", "threat"], horizontal=True)
            m4 = base_map()
            if nav is not None:
                add_track(m4, nav)
            add_cells(m4, cells, color_by)
            add_areas(m4, cells, areas)
            if color_by == "action":
                leg = "".join(f"<div><span style='display:inline-block;width:12px;height:12px;background:{c};opacity:.8;margin-right:6px'></span>{k}</div>"
                              for k, c in priority.ACTION_COLORS.items())
                m4.get_root().html.add_child(folium.Element(
                    "<div style='position:absolute;bottom:20px;left:20px;z-index:9999;background:white;color:#222;padding:8px 10px;border-radius:6px;"
                    f"font:12px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)'><b>Action</b>{leg}<div style='margin-top:4px'><span style='display:inline-block;width:10px;height:10px;border:1.5px solid #000;margin-right:6px'></span>candidate MPA</div></div>"))
            folium.LayerControl(collapsed=True).add_to(m4)
            fit(m4, nav if nav is not None else cells)
            st_folium(m4, height=560, use_container_width=True, returned_objects=[])

            left, right = st.columns([3, 2])
            with left:
                st.subheader("Candidate protected areas")
                if areas.empty:
                    st.caption("No group of 2+ touching high-sensitivity cells. Try a larger cell size or check the habitat values.")
                else:
                    st.dataframe(areas.drop(columns=["cells", "lat", "lon"]), hide_index=True, use_container_width=True)
            with right:
                st.subheader("Pressures")
                if thr_pts is not None and len(thr_pts):
                    lab = "label" if "label" in thr_pts else thr_pts.columns[0]
                    st.markdown("**Seen on the seabed** (imagery)")
                    st.dataframe(thr_pts[lab].value_counts().rename_axis("item").reset_index(name="count"), hide_index=True, use_container_width=True)
                if buoy_path:
                    st.markdown("**Area-wide** (smart buoy)")
                    st.dataframe(priority.buoy_pressures(events_for(buoy_path, th)), hide_index=True, use_container_width=True)

            with st.expander("Cell table"):
                st.dataframe(cells.drop(columns=["gx", "gy", "valid"]).round(3), hide_index=True, use_container_width=True)
            d1, d2 = st.columns(2)
            d1.download_button("Download cells (GeoJSON)", priority.cells_geojson(cells), "priority_cells.geojson")
            d2.download_button("Download candidate MPAs (GeoJSON)", priority.areas_geojson(cells, areas), "candidate_mpas.geojson")
