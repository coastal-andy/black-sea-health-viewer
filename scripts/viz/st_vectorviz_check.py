"""Minimal Streamlit page that embeds vectorviz the way the viewer will (st_folium + st.plotly_chart).
Proves the custom canvas arrow layer and legends survive streamlit_folium. Not part of the app.
Run: .venv/bin/streamlit run scripts/viz/st_vectorviz_check.py --server.port 8766
"""
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from viewer import vectorviz as vv  # noqa: E402

st.set_page_config(layout="wide", page_title="vectorviz check")
kind = st.radio("Layer", ["waves", "currents", "wind"], horizontal=True)


@st.cache_data(show_spinner=False)
def field(k):
    return vv.load_field(k)


@st.cache_data(show_spinner=False)
def point(k):
    end = pd.Timestamp.now("UTC").tz_localize(None).floor("h")
    return vv.load_point(k, 44.17, 28.72, end - pd.Timedelta(days=7), end)


m = vv.base_map()
vv.field_layer(m, field(kind))
folium.LayerControl(collapsed=True).add_to(m)
out = st_folium(m, height=520, use_container_width=True, returned_objects=["last_clicked"])
theme = "dark" if (st.get_option("theme.base") == "dark") else "light"
st.plotly_chart(vv.point_chart(point(kind), kind, theme=theme), use_container_width=True)
st.caption(f"last click: {out.get('last_clicked') if out else None}")
