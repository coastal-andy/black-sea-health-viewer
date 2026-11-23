"""Point / zone panel: compare sources, long-term trend, anomaly band, obs vs model, waves and currents; health cards."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from viewer import adapters as A
from viewer import profiles as P
from viewer.style import table_html, ORIGIN, ORIGIN_LABEL, OI, STATUS, esc, origin_tag, pill, plotly_layout, theme_name, tokens

FONT = dict(family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif", size=12, color="#1C2430")
VIEWS = ["Health cards", "Compare sources", "Anomaly", "Long-term trend", "Obs vs model", "Waves and currents"]
VIEW_SHORT = {"Health cards": "Cards", "Compare sources": "Compare sources", "Anomaly": "Anomaly",
              "Long-term trend": "Trend", "Obs vs model": "Obs vs model", "Waves and currents": "Waves, currents, wind"}


def _layout(fig, title="", ytitle="", height=360, log=False):
    fig.update_layout(template="simple_white", height=height, margin=dict(l=55, r=15, t=40 if title else 15, b=40),
                      title=dict(text=title, font=dict(size=14)), font=FONT, hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)))
    fig.update_yaxes(title=ytitle, showgrid=True, type="log" if log else "linear")
    fig.update_xaxes(showgrid=False)
    return plotly_layout(fig)


def _src_line(meta: dict, detail: bool) -> str:
    bits = []
    if meta.get("platform"):
        bits.append(f"platform {meta['platform']}")
    if meta.get("distance_km") is not None:
        bits.append(f"{meta['distance_km']} km from the point")
    if meta.get("grid_lat") is not None and detail:
        bits.append(f"grid cell {meta['grid_lat']:.3f} N {meta['grid_lon']:.3f} E")
    if detail and meta.get("dataset"):
        bits.append(str(meta["dataset"]))
    if detail and meta.get("depth_m") not in (None, "", {}):
        bits.append(f"depth {meta['depth_m']}")
    return ", ".join(bits)


def _ready(items):
    pending = [i for i in items if i.get("series") is None]
    for i in pending:
        st.caption(f"{i['label']}: {i.get('note', 'still downloading')}")
    return [i for i in items if i.get("series") is not None]


def var_label(var: str, profile: dict) -> str:
    v = A.VARIABLES[var]
    t = P.VAR_TEXT.get(var, {}).get(P.level(profile))
    return f"{t or v['label']} ({v['unit']})"


# ------------------------------------------------------------------------------------------ compare
def compare_view(sel, var, profile):
    detail = P.show_detail(profile)
    with st.spinner("Loading series from each source..."):
        items = _ready(A.series_for(var, sel["lat"], sel["lon"]))
    st.caption(P.text(P.EXPLAIN, "compare", profile))
    if not items:
        st.info("No source has data for this variable at this point.")
        return
    v = A.VARIABLES[var]
    fig = go.Figure()
    for it in items:
        o = it["origin"]
        col = ORIGIN.get(o, OI["grey"])
        s = it["series"]
        s = s.asfreq("D") if isinstance(s.index, pd.DatetimeIndex) and len(s) > 1 else s  # gaps stay gaps
        name = f"{ORIGIN_LABEL.get(o, o)}: {it['dataset'] if detail else it['label'].split(': ', 1)[-1]}"
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines" if o != "in-situ" else "lines+markers",
                                 marker=dict(size=3), line=dict(color=col, width=1.6 if o != "in-situ" else 1.2,
                                                                dash="dot" if it.get("untrusted") else None)))
    t = A.today()
    fig.add_vline(x=t, line=dict(color="#999", width=1, dash="dash"))
    _layout(fig, ytitle=var_label(var, profile), log=v.get("log", False))
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
    rows = []
    for it in items:
        s = it["series"]
        last = s[s.index <= A.today()].dropna()
        rows.append({"Source": it["label"], "Origin": ORIGIN_LABEL.get(it["origin"], it["origin"]),
                     "Latest": f"{last.iloc[-1]:.2f} {v['unit']}" if len(last) else "-",
                     "Date": f"{last.index[-1]:%d %b %Y}" if len(last) else "-",
                     "Where": _src_line(it["meta"], detail) or "-", "Note": it.get("note") or ""})
    st.markdown(table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
    if any(it.get("untrusted") for it in items):
        st.caption("Dotted line: buoy under quality control. Do not use it for decisions yet.")


# ------------------------------------------------------------------------------------------ anomaly
def anomaly_view(sel, var, profile):
    detail = P.show_detail(profile)
    with st.spinner("Loading the series and the reference climatology..."):
        items = _ready(A.series_for(var, sel["lat"], sel["lon"]))
        clim = A.soft(A.climatology, var, sel["lat"], sel["lon"])
    trusted = [i for i in items if not i.get("untrusted")]
    main = next((i for i in trusted if i["origin"] == "satellite"), None) or next(
        (i for i in trusted if i["origin"] == "in-situ"), None) or next(
        (i for i in trusted if i["origin"] in ("model", "reanalysis")), None) or (trusted[0] if trusted else None)
    if main is None or clim is None:
        st.info("No series or no reference climatology for this variable at this point.")
        return
    s = main["series"]
    c = clim.reindex(A.doy365(s.index))
    c.index = s.index
    v = A.VARIABLES[var]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=c["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s.index, y=c["p10"], fill="tonexty", fillcolor="rgba(140,140,140,0.22)",
                             line=dict(width=0), name="usual range (p10-p90)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s.index, y=c["mean"], line=dict(color="#666", width=1.2, dash="dash"), name="long-term average"))
    above = s.where(s > c["p90"])
    below = s.where(s < c["p10"])
    fig.add_trace(go.Scatter(x=s.index, y=s.values, line=dict(color=ORIGIN.get(main["origin"], OI["blue"]), width=1.8),
                             name=f"{ORIGIN_LABEL.get(main['origin'])}: {main['dataset'] if detail else 'this point'}"))
    fig.add_trace(go.Scatter(x=above.index, y=above.values, mode="markers", marker=dict(color=OI["vermillion"], size=5),
                             name="above usual"))
    fig.add_trace(go.Scatter(x=below.index, y=below.values, mode="markers", marker=dict(color=OI["sky"], size=5),
                             name="below usual"))
    _layout(fig, ytitle=var_label(var, profile), log=v.get("log", False))
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
    a = (s - c["mean"]).dropna()
    yrs = clim.attrs.get("years")
    cols = st.columns(4)
    if len(a):
        if "log_mean" in c and c["log_mean"].notna().any():
            last = s.reindex(a.index).iloc[-1]
            z = (np.log10(max(last, 1e-6)) - c["log_mean"].reindex(a.index).iloc[-1]) / c["log_std"].reindex(a.index).iloc[-1]
        else:
            z = a.iloc[-1] / c["std"].reindex(a.index).iloc[-1]
        cols[0].metric("Latest anomaly", f"{a.iloc[-1]:+.2f} {v['unit']}", help="Value minus the long-term average for that day of the year.")
        cols[1].metric("Standardised (z)", f"{z:+.1f}")
        cols[2].metric("Days above usual (last 30)", int((s.tail(30) > c["p90"].tail(30)).sum()))
        cols[3].metric("Reference period", f"{yrs[0]}-{yrs[1]}" if isinstance(yrs, (list, tuple)) and len(yrs) == 2 else (str(yrs) if yrs else "-"))
    st.caption(P.text(P.EXPLAIN, "anomaly", profile))
    if detail:
        ca = {k: v for k, v in clim.attrs.items() if k in ("dataset", "years", "window_days", "smooth_days", "n_years", "space", "origin")}
        st.caption("Climatology: " + ", ".join(f"{k} {v}" for k, v in ca.items() if v not in (None, "")) +
                   f". Series: {main['label']} ({_src_line(main['meta'], True)}).")


# ------------------------------------------------------------------------------------------ trend
def trend_view(sel, var, profile):
    detail = P.show_detail(profile)
    with st.spinner("Loading the multi-year series (first time can take 10-20 s)..."):
        s = A.soft(A.long_series, var, sel["lat"], sel["lon"])
    if s is None or s.empty:
        st.info("No multi-year series for this variable at this point.")
        return
    tr = A.annual_trend(s)
    v = A.VARIABLES[var]
    if tr is None:
        st.info("Not enough complete years for a trend.")
        return
    ann = tr["annual"]
    x = ann.index.to_numpy(float)
    fig = go.Figure()
    o = s.attrs.get("origin", "satellite")
    fig.add_trace(go.Scatter(x=ann.index, y=ann.values, mode="markers+lines", name="annual mean",
                             line=dict(color=ORIGIN.get(o, OI["blue"]), width=1), marker=dict(size=7)))
    fig.add_trace(go.Scatter(x=ann.index, y=tr["intercept"] + tr["slope"] * x, mode="lines", name="trend",
                             line=dict(color=OI["vermillion"], width=2.4)))
    _layout(fig, ytitle=var_label(var, profile), log=False)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
    c = st.columns(3)
    c[0].metric("Change per decade", f"{tr['slope_decade']:+.2f} {v['unit']}",
                help="Slope of the straight line through the annual means, times ten years.")
    c[1].metric("Uncertainty (95 %)", f"± {tr['ci_decade']:.2f} {v['unit']}")
    c[2].metric("Years used", f"{tr['years'][0]}-{tr['years'][1]} ({tr['n']})")
    sig = tr["ci_decade"] < abs(tr["slope_decade"])
    direction = "rising" if tr["slope_decade"] > 0 else "falling"
    st.markdown(f"**{'Clear' if sig else 'No clear'} long-term change**: {direction} by {abs(tr['slope_decade']):.2f} "
                f"{v['unit']} per decade" + ("" if sig else " (the uncertainty is larger than the change)") + ".")
    st.caption(P.text(P.EXPLAIN, "trend", profile) + f" Source: {ORIGIN_LABEL.get(o, o)}"
               + (f", {s.attrs.get('dataset', '')}, p = {tr['p']:.3g}" if detail else "") + ".")


# ------------------------------------------------------------------------------------------ obs vs model
def obs_model_view(sel, var, profile):
    detail = P.show_detail(profile)
    if A.has_module("marinekit.datahub"):
        with st.spinner("Pairing measurements and model..."):
            r = A.soft(A.hub_obs_model, var, round(sel["lat"], 4), round(sel["lon"], 4), str(A.today().date()))
        if r is not None:
            return _obs_model_hub(r, var, profile, detail)
    with st.spinner("Pairing measurements and model..."):
        items = _ready(A.series_for(var, sel["lat"], sel["lon"]))
    obs = [i for i in items if i["origin"] in ("in-situ", "satellite")]
    mods = [i for i in items if i["origin"] in ("model", "reanalysis")]
    if not obs or not mods:
        st.info("Needs both an observation (buoy or satellite) and a model series at this point. "
                "Try sea temperature or salinity near a buoy, or pick a buoy from the list.")
        return
    mod = mods[0]
    rows = []
    figs = []
    for ob in obs:
        mt = A.obs_vs_model(ob["series"], mod["series"])
        if mt is None:
            continue
        rows.append({"Observation": ob["label"], "Model": mod["label"], "Days paired": mt["n"],
                     "Bias (model - obs)": round(mt["bias"], 3), "RMSE": round(mt["rmse"], 3), "Correlation r": round(mt["r"], 3),
                     "Period": f"{mt['start']:%d %b %Y} - {mt['end']:%d %b %Y}",
                     "Trust": "under QC" if ob.get("untrusted") else "ok"})
        figs.append((ob, mt))
    if not rows:
        st.info("The observation and the model do not overlap in time at this point.")
        return
    v = A.VARIABLES[var]
    st.markdown(table_html(pd.DataFrame(rows)), unsafe_allow_html=True)
    ob, mt = figs[0]
    j = mt["joined"]
    lo, hi = float(np.nanmin(j.values)), float(np.nanmax(j.values))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color="#999", dash="dash"), name="perfect agreement"))
    fig.add_trace(go.Scatter(x=j["obs"], y=j["mod"], mode="markers", name="one day",
                             marker=dict(color=ORIGIN.get(ob["origin"], OI["black"]), size=6, opacity=0.65),
                             text=[f"{t:%d %b %Y}" for t in j.index], hovertemplate="%{text}<br>obs %{x:.2f}<br>model %{y:.2f}"))
    _layout(fig, ytitle=f"Model ({v['unit']})", height=340)
    fig.update_xaxes(title=f"{ORIGIN_LABEL.get(ob['origin'])} ({v['unit']})")
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
    st.caption("Bias above zero means the model is too high. RMSE is the typical size of the error. "
               "r close to 1 means the model follows the ups and downs."
               + (f" Model: {mod['dataset']} ({_src_line(mod['meta'], True)})." if detail else ""))


def _obs_model_hub(r, var, profile, detail):
    v = A.VARIABLES[var]
    unit = r.get("unit") or v["unit"]
    if not r.get("n"):
        st.info("The observation and the model do not overlap in time here. " + (r.get("note") or ""))
        return
    c = st.columns(4)
    c[0].metric("Days compared", r["n"])
    c[1].metric("Bias (model - obs)", f"{r['bias']:+.2f} {unit}" if r.get("bias") is not None else "-")
    c[2].metric("RMSE", f"{r['rmse']:.2f} {unit}" if r.get("rmse") is not None else "-")
    c[3].metric("Correlation r", f"{r['r']:.2f}" if r.get("r") is not None else "-")
    st.markdown(f"Observation: **{esc(r.get('obs_label'))}**" + (f" (platform {esc(r['obs_platform'])})" if r.get("obs_platform") else "")
                + f"  \nModel: **{esc(r.get('model_label'))}**", unsafe_allow_html=True)
    j = r.get("joined")
    if j is not None and len(j):
        lo, hi = float(np.nanmin(j.values)), float(np.nanmax(j.values))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color="#999", dash="dash"),
                                 name="perfect agreement"))
        fig.add_trace(go.Scatter(x=j["obs"], y=j["mod"], mode="markers", name="one day",
                                 marker=dict(color=OI["blue"], size=6, opacity=0.6),
                                 text=[f"{t:%d %b %Y}" for t in j.index],
                                 hovertemplate="%{text}<br>observed %{x:.2f}<br>model %{y:.2f}<extra></extra>"))
        lg = bool(v.get("log"))
        _layout(fig, ytitle=f"Model ({unit})", height=340, log=lg)
        fig.update_xaxes(title=f"Observed ({unit})", type="log" if lg else "linear")
        fig.update_layout(hovermode="closest")
        st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
    st.caption("Bias above zero means the model is too high. RMSE is the typical size of the error. "
               "r close to 1 means the model follows the ups and downs."
               + (f" {r['note']}." if r.get("note") else "")
               + (f" Period {r.get('start')} to {r.get('end')}, sampled at {r['lat']:.3f} N {r['lon']:.3f} E." if detail else ""))


# ------------------------------------------------------------------------------------------ vectors
def vector_view(sel, profile):
    vv = A.vectorviz()
    if vv is None or not (hasattr(vv, "point_chart") and hasattr(vv, "load_point")):
        st.info("The combined waves / currents / wind chart comes from the vector visualisation module, which is not ready yet.")
        return
    st.session_state.setdefault("vec_kind", "all three")
    kind = st.segmented_control("Show", ["all three", "waves", "currents", "wind"], key="vec_kind",
                                format_func=str.capitalize) or "all three"
    t = A.today()
    start, end = t - pd.Timedelta(days=10), t + pd.Timedelta(days=4)
    kinds = ["waves", "currents", "wind"] if kind == "all three" else [kind]
    dfs = {}
    with st.spinner("Loading waves, currents and wind..."):
        for k in kinds:
            try:
                dfs[k] = A.timed(_vec_point, k, round(sel["lat"], 3), round(sel["lon"], 3), str(start.date()),
                                 str(end.date()), timeout=45)
            except Exception as ex:
                st.caption(f"{k.capitalize()}: {str(ex)[:160]}")
    if not dfs:
        return
    try:
        if len(dfs) > 1 and hasattr(vv, "combined_chart"):
            fig = plotly_layout(vv.combined_chart(dfs, theme=theme_name()))
        else:
            k, df = next(iter(dfs.items()))
            fig = plotly_layout(vv.point_chart(df, k, theme=theme_name()))
        st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
        st.caption("Arrows point where the water or air is going (up = north). For waves, a longer arrow means a "
                   "longer wave period (swell). The dashed line marks today; later values are forecast.")
    except Exception as ex:
        st.warning(f"Could not draw the chart: {str(ex)[:200]}")


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _vec_point(kind, lat, lon, start, end):
    return A.vectorviz().load_point(kind, lat, lon, start, end)


# ------------------------------------------------------------------------------------------ cards
def _num(x, unit=""):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    if isinstance(x, (int, float)):
        s = f"{x:.2f}" if abs(x) < 10 else f"{x:.1f}"
        s = s.rstrip("0").rstrip(".") if "." in s else s
        return f"{s} {unit}".strip()
    return f"{x} {unit}".strip()


def _ttype_badge(tt: str) -> str:
    if not tt:
        return ""
    col = tokens()["normal"] if "OFFICIAL" in tt else tokens()["muted"]
    return (f"<span style='font-size:0.7rem;font-weight:650;color:{col};border:1px solid {col};border-radius:3px;"
            f"padding:0 4px;margin-left:4px'>{esc(tt)}</span>")


def _reference_html(ref, unit, lvl) -> str:
    if not ref:
        return ""
    if isinstance(ref, str):
        return f"<div class='ref'>Usual: {esc(ref)}</div>"
    parts = []
    val, lo, hi = ref.get("value"), ref.get("low"), ref.get("high")
    period = ref.get("period") or ref.get("season")
    if val is not None:
        rng = f", usual range {_num(lo)}-{_num(hi, unit)}" if (lo is not None and hi is not None) else ""
        parts.append(f"Usual: {_num(val, unit if not isinstance(val, str) else '')}{rng}" + (f" ({esc(period)})" if period else ""))
    if lvl != "public":
        thr = ref.get("threshold") or ref.get("classes")
        if thr:
            parts.append(f"Threshold: {esc(thr)}{_ttype_badge(ref.get('threshold_type', ''))}")
        elif ref.get("threshold_type"):
            parts.append(f"Threshold type{_ttype_badge(ref.get('threshold_type'))}")
    if lvl == "researcher":
        for k in ("basis", "threshold_source", "season_test"):
            if ref.get(k):
                parts.append(f"{k.replace('_', ' ').capitalize()}: {esc(ref[k])}")
    return "".join(f"<div class='ref'>{p}</div>" for p in parts)


def _investigate_html(inv, lvl) -> str:
    if not inv:
        return ""
    if isinstance(inv, str):
        items = [inv]
    else:
        items = []
        for x in inv:
            if isinstance(x, dict):
                s = x.get("action", "")
                if lvl != "public" and x.get("who"):
                    s += f" ({x['who']})"
                if lvl in ("researcher", "student") and x.get("trigger"):
                    s = f"{x['trigger']}: {s}"
                items.append(s)
            else:
                items.append(str(x))
    if lvl == "public":
        return "<div class='row'><span class='lbl'>What happens next</span>Scientists may check this with samples.</div>"
    lis = "".join(f"<li>{esc(s)}</li>" for s in items if s)
    return f"<div class='row'><span class='lbl'>What to check</span><ul style='margin:2px 0 0 18px;padding:0'>{lis}</ul></div>"


def card_html(c: dict, profile: dict, compact: bool = False) -> str:
    lvl = P.level(profile)
    detail = P.show_detail(profile)
    col = STATUS.get(c.get("status") or "no_data", STATUS["no_data"])[0]
    unit = c.get("unit") or ""
    txt = c.get("text") if isinstance(c.get("text"), dict) else {}
    main = txt.get(lvl) or c.get("why") or ""
    html = [f"<div class='bsv-card' style='border-left-color:{col}'>",
            f"<div style='display:flex;justify-content:space-between;align-items:center;gap:8px'><h4>{esc(c.get('title'))}</h4>"
            f"{pill(c.get('status'))}</div>"]
    if c.get("value") is not None:
        z = c.get("z")
        ztxt = f" <span class='ref'>z = {z:+.1f}</span>" if (lvl in ("researcher", "student") and isinstance(z, (int, float))) else ""
        html.append(f"<div><span class='val'>{esc(_num(c['value']))}</span> <span class='ref'>{esc(unit)}</span>{ztxt}</div>")
    html.append(_reference_html(c.get("reference"), unit, lvl))
    meta = []
    if c.get("evidence"):
        meta.append(origin_tag("in-situ" if c["evidence"] == "measured" else c["evidence"]))
    if c.get("confidence"):
        meta.append(f"<span class='bsv-note'>confidence: <b>{esc(c['confidence'])}</b></span>")
    if meta:
        html.append(f"<div class='row'>{' '.join(meta)}</div>")
    if main:
        html.append(f"<div class='row'>{esc(main)}</div>")
    if detail and c.get("why") and c.get("why") != main:
        html.append(f"<div class='row'><span class='lbl'>Why</span>{esc(c['why'])}</div>")
    if not compact:
        dn = c.get("driver_note")
        if dn and not dn.startswith("No anomaly") and not dn.startswith("No cause"):
            html.append(f"<div class='row'><span class='lbl'>Natural or pressure?</span>{esc(dn)}</div>")
        html.append(_investigate_html(c.get("investigate"), lvl))
        sup = c.get("supporting") or []
        if sup and lvl in ("researcher", "student", "stakeholder"):
            lis = "".join(f"<li>{esc(s.get('name'))}: <b>{esc(_num(s.get('value'), s.get('unit') or ''))}</b>"
                          + (f" <span class='ref'>{esc(s.get('note'))}</span>" if s.get("note") and lvl != "stakeholder" else "")
                          + (_ttype_badge(s.get("threshold_type") or "") if lvl == "researcher" else "") + "</li>"
                          for s in sup[: (8 if lvl == "researcher" else 3)])
            html.append(f"<details style='margin-top:3px'><summary class='bsv-note'>Supporting indicators ({len(sup)})"
                        f"</summary><ul style='margin:2px 0 0 18px;padding:0;font-size:0.84rem'>{lis}</ul></details>")
    srcs = [s for s in (c.get("sources") or []) if s.get("dataset") != "zone sampling"]
    zone = [s for s in (c.get("sources") or []) if s.get("dataset") == "zone sampling"]
    if srcs:
        seen, bits = set(), []
        for s in srcs:
            name = (s.get("dataset") if detail else (s.get("label") or s.get("dataset"))) or ""
            if name in seen:
                continue
            seen.add(name)
            b = f"{ORIGIN_LABEL.get(s.get('origin'), s.get('origin') or '')}: {name}"
            if s.get("date"):
                b += f", {s['date']}"
            if s.get("distance_km") not in (None, ""):
                b += f", {s['distance_km']} km away"
            bits.append(b)
        bits = bits[: (6 if detail else 2)]
        html.append(f"<div class='src'>Source: {esc('; '.join(bits))}"
                    + (f"<br>{esc(zone[0].get('label'))}" if zone and detail else "") + "</div>")
    html.append("</div>")
    return "".join(html)


def poll_cards(sel, day, profile):
    """Re-run the page once the background card job for this place has finished."""
    args = (sel["lat"], sel["lon"], day, P.card_profile(profile), sel.get("wkt"))

    @st.fragment(run_every=3)
    def _poll():
        if A.cards_ready(*args):
            st.rerun(scope="app")

    _poll()


def cards_view(sel, day, profile, ncols=3, compact=False, only=None):
    with st.spinner("Computing health cards..."):
        cards = A.zone_cards(sel["lat"], sel["lon"], day, P.card_profile(profile), sel.get("wkt"))
    if A.cards_pending(cards):
        st.info("The health cards for this place are still being computed (the first time takes up to a minute; "
                "after that they are cached). They appear here by themselves.")
        poll_cards(sel, day, profile)
        return cards
    if only:
        cards = [c for c in cards if c.get("id") in only] or cards
    if profile.get("role") == "public":
        cards = [c for c in cards if c.get("status") != "no_data"] + [c for c in cards if c.get("status") == "no_data"]
    counts = pd.Series([c.get("status", "no_data") for c in cards]).value_counts()
    summary = " ".join(f"{pill(k)} {counts.get(k, 0)}" for k in ("alert", "watch", "normal", "no_data") if counts.get(k, 0))
    st.markdown(f"<div style='margin-bottom:8px'>{summary} <span class='bsv-note'>&nbsp; cards from the "
                f"{A.cards_source()}, date {day}</span></div>", unsafe_allow_html=True)
    cols = st.columns(ncols)
    for i, c in enumerate(cards):
        with cols[i % ncols]:
            st.markdown(card_html(c, profile, compact), unsafe_allow_html=True)
    return cards
