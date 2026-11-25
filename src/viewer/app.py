"""Black Sea Health Viewer (EfxINNOs hackathon, Challenge 04 Ecosystem Health). Design direction B.

Run:  .venv/bin/streamlit run src/viewer/app.py --server.port 8502 --server.headless true
Demo shortcuts: ?role=stakeholder&sector=tourism&goal=risk skips the questionnaire; ?theme=light starts in light;
?lang=ro opens in Romanian; ?edges=soft starts with soft zone edges.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st  # noqa: E402

from viewer import onboarding as OB  # noqa: E402
from viewer import profiles as P  # noqa: E402
from viewer import shell as SH  # noqa: E402
from viewer import views as V  # noqa: E402
from viewer.i18n import init_lang, t  # noqa: E402
from viewer.style import css  # noqa: E402

T0 = time.perf_counter()
st.set_page_config(page_title="Black Sea Health Viewer", layout="wide", initial_sidebar_state="expanded")
ss = st.session_state
SH.init_theme()
init_lang()
SH.keep_widget_state()

PAGES = {
    "overview": st.Page(V.overview, title=t("Overview"), url_path="overview", default=True),
    "water": st.Page(V.water, title=t("Water quality"), url_path="water"),
    "seabed": st.Page(V.seabed, title=t("Coast and seabed"), url_path="seabed"),
    "pressures": st.Page(V.pressures, title=t("Pressures"), url_path="pressures"),
    "methods": st.Page(V.methods, title=t("Data and methods"), url_path="methods"),
}
SH.PAGE_OBJS.update(PAGES)
page = st.navigation(list(PAGES.values()), position="hidden")
active = next((k for k, p in PAGES.items() if p.url_path == page.url_path), "overview")
st.markdown(css(ss.theme, active), unsafe_allow_html=True)
SH.rail(PAGES)

# ------------------------------------------------------------------------------------------ questionnaire
qp = st.query_params
if "profile" not in ss and qp.get("role") in P.ROLES:
    OB.finish(dict(role=qp["role"], sector=qp.get("sector") if qp.get("sector") in P.SECTORS else None,
                   focus=qp.get("focus") if qp.get("focus") in P.FOCUS else None,
                   goal=qp.get("goal") if qp.get("goal") in P.GOALS else "now"))

ob_slot = st.empty()  # the questionnaire lives here; an empty slot on later runs clears it at once
if "profile" not in ss or ss.get("onboarding"):
    with ob_slot.container(key="page_body"):
        OB.render()
    st.stop()
if "sel" not in ss:
    OB.apply_defaults(ss.profile)

page.run()
if os.environ.get("BSV_TIMING"):  # BSV_TIMING=1 streamlit run ... logs the script time of every full run
    logging.getLogger("viewer.timing").warning("page %s ran in %.2f s", page.url_path or "overview",
                                               time.perf_counter() - T0)
