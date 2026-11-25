"""Water quality page (direction B2): variable list, 4 headline numbers, 60-day chart against the usual range,
and folded Sources / Natural or pressure? / Data sections."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from viewer import adapters as A
from viewer import panels as PN
from viewer import profiles as P
from viewer import shell as SH
from viewer.i18n import data, dt, num, t as tr_
from viewer.style import ORIGIN_LABEL, STATUS, esc, plotly_layout, status_square, tokens

# list key -> (name, series variable in adapters.VARIABLES or None, health card id)
WVARS = {
    "sst": ("Temperature", "sst", "temperature"),
    "sal": ("Salinity", "sal", None),
    "o2_bottom": ("Oxygen, seabed", "o2_bottom", "oxygen"),
    "o2": ("Oxygen, surface", "o2", None),
    "chl": ("Chlorophyll-a", "chl", "blooms"),
    "kd490": ("Water clarity", "kd490", "clarity"),
    "nutrients": ("Nutrients", None, "nutrients"),
    "ph": ("Acidity (pH)", None, "acidification"),
}
VIEWS = {"now": "Now vs usual", "trend": "Long-term trend", "obsmod": "Measured vs model"}
WINDOW = 60


# ------------------------------------------------------------------------------------------ data helpers
def _cards(sel, day, profile) -> dict:
    cards = A.zone_cards(sel["lat"], sel["lon"], day, P.card_profile(profile), sel.get("wkt"), wait=1.5)
    if A.cards_pending(cards):
        return {}
    return {c.get("id"): c for c in cards}


def _main_item(items):
    trusted = [i for i in items if not i.get("untrusted") and i.get("series") is not None]
    for o in ("satellite", "in-situ", "model", "reanalysis"):
        hit = next((i for i in trusted if i["origin"] == o and (o != "in-situ" or (i["meta"].get("distance_km") or 99) < 30)),
                   None)
        if hit:
            return hit
    return trusted[0] if trusted else None


def _seasonal(var, sel):
    """(result, pending) from marinekit.seasonal: result is {cycle, trend} or None when the variable is not covered."""
    try:
        return A.seasonal(var, sel["lat"], sel["lon"], wait=1.5), False
    except A.SlowSource:
        return None, True
    except Exception:
        return None, False


def _poll_seasonal(var, sel):
    """Re-run the page once the background seasonal fit for this place has finished."""
    @st.fragment(run_every=3)
    def _poll():
        try:
            A.seasonal(var, sel["lat"], sel["lon"], wait=0.05)
            st.rerun(scope="app")
        except A.SlowSource:
            pass
        except Exception:
            st.rerun(scope="app")

    _poll()


def _window_txt(cyc) -> str:
    """'weekly means 2016-11-27 to 2026-11-22' -> '2016-2026' (years of the fitted record)."""
    ys = re.findall(r"\d{4}", str(cyc.get("window") or ""))
    return f"{ys[0]}-{ys[-1]}" if len(ys) >= 2 else "-"


def _clim_note(clim) -> str:
    if clim is None:
        return ""
    yrs = clim.attrs.get("years")
    y = f"{yrs[0]}-{yrs[1]}" if isinstance(yrs, (list, tuple)) and len(yrs) == 2 else str(yrs or "")
    return tr_("Usual range: 10th to 90th percentile of the same days of the year, {y}. Thresholds OURS.", y=y)


def plain_gate(reason: str, kind: str, profile) -> str:
    """The gate reason for the profile: researchers and stakeholders get marinekit's reason (translated), the public
    and students a plain sentence."""
    r = (reason or "").lower()
    if P.level(profile) in ("researcher", "stakeholder"):
        return data(reason or "")
    if "trust" in r:
        return tr_("The source here is not reliable enough to show this.")
    if kind == "trend":
        return tr_("Not enough complete years of reliable data here yet: a trend needs at least 8.")
    if "too little" in r or "no significant" in r:
        return tr_("The seasons explain too little of the ups and downs here, so a usual range would mislead.")
    return tr_("Not enough years of data at this point yet to work out the usual range.")


def _fmt(x, unit="", sign=False) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    a = abs(x)
    s = f"{x:+.2f}" if sign and a < 10 else (f"{x:+.1f}" if sign else (f"{x:.2f}" if a < 10 else f"{x:.1f}"))
    return f"{s} {unit}".strip()


@st.cache_data(ttl=3600, show_spinner=False)
def _series_status_cached(var, lat, lon, day):
    items = A.series_for(var, lat, lon)
    clim = A.soft(A.climatology, var, lat, lon)
    main = _main_item(items)
    if main is None:
        return "no_data", ""
    s = main["series"]
    s = s[s.index <= pd.Timestamp(A.today())].dropna()
    if not len(s):
        return "no_data", ""
    last, when = float(s.iloc[-1]), s.index[-1]
    unit = A.VARIABLES[var]["unit"]
    status = "no_data"
    if clim is not None:
        c = clim.reindex(A.doy365(pd.DatetimeIndex([when])))
        lo, hi = c["p10"].iloc[0], c["p90"].iloc[0]
        if pd.notna(lo) and pd.notna(hi):
            status = "normal" if lo <= last <= hi else "watch"
    return status, PN._num(last, unit)


def _series_status(var, sel):
    """For variables without a health card: latest value, and normal / watch from the usual p10-p90 range."""
    try:
        return _series_status_cached(var, round(sel["lat"], 4), round(sel["lon"], 4), str(A.today().date()))
    except Exception:
        return "no_data", ""


# ------------------------------------------------------------------------------------------ left list
def _pick(k):
    st.session_state["w_var"] = k


def var_list(sel, cards, current):
    ss = st.session_state
    st.markdown(f"<div class='bsv-sec'><div class='bsv-lbl'>{tr_('Place')}</div><div class='bsv-place' style='font-size:26px'>"
                f"{esc(SH.place_name(sel['name']))}</div><div class='bsv-lbl' style='margin-top:4px'>{num(f'{sel["lat"]:.3f}')} N &middot; "
                f"{num(f'{sel["lon"]:.3f}')} E</div></div>", unsafe_allow_html=True)
    with st.container(key="bsv_pad"):
        SH.place_picker("Search another place")
    st.markdown(f"<div class='bsv-lbl' style='padding:18px 20px 10px 20px'>{tr_('Water quality')}</div>",
                unsafe_allow_html=True)
    for k, (name, var, cid) in WVARS.items():
        c = cards.get(cid) if cid else None
        status = c.get("status") if c else "no_data"
        val = PN._num(c.get("value"), c.get("unit") or "") if (c and c.get("value") is not None) else ""
        if c is None and var:
            status, val = _series_status(var, sel)
        active = " active" if k == current else ""
        with st.container(key=f"vrow_{k}"):
            st.markdown(f"<div class='bsv-vrow{active}'>{status_square(status)}<span class='nm'>{esc(tr_(name))}</span>"
                        f"<span class='vl'>{esc(num(val))}</span></div>", unsafe_allow_html=True)
            st.button(tr_("Show {name}", name=tr_(name)), key=f"vbtn_{k}", on_click=_pick, args=(k,))
    with st.container(key="aside_foot"):
        st.page_link(SH.PAGE_OBJS["seabed"], label=tr_("Waves, currents and depth"))
        SH.profile_menu()


# ------------------------------------------------------------------------------------------ headline numbers
def _stat(label, value, unit="", extra="") -> str:
    return (f"<div class='bsv-stat'><span class='bsv-lbl'>{esc(label)}</span><span class='v'>{esc(value)}"
            f"<span class='u'>{esc(unit)}</span>{extra}</span></div>")


def _status_tag(status) -> str:
    if not status:
        return ""
    lab = STATUS[status][1].lower()
    return f"<span class='tag'>{status_square(status)}{esc(lab)}</span>"


# ------------------------------------------------------------------------------------------ 60-day chart
def chart_60(s, c, unit, log, origin) -> go.Figure:
    t = tokens()
    fig = go.Figure()
    if c is not None:
        fig.add_trace(go.Scatter(x=s.index, y=c["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=s.index, y=c["p10"], fill="tonexty", fillcolor=t["line2"], line=dict(width=0),
                                 name=tr_("usual range (p10-p90)"), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=s.index, y=c["mean"], line=dict(color=t["muted"], width=1.5, dash="dash"),
                                 name=tr_("usual"), hovertemplate=tr_("usual") + " %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, line=dict(color=t["accent"], width=2.5), name=tr_("this year"),
                             text=[dt(x, "%d %b") for x in s.index],
                             hovertemplate="%{text}: %{y:.2f} " + unit + "<extra>" + esc(origin) + "</extra>"))
    last = s.dropna()
    if len(last):
        fig.add_trace(go.Scatter(x=[last.index[-1]], y=[last.iloc[-1]], mode="markers", showlegend=False,
                                 marker=dict(color=t["accent"], size=9), hoverinfo="skip"))
    fig.update_layout(height=320, margin=dict(l=44, r=12, t=8, b=30), hovermode="x unified", showlegend=False)
    if log:
        fig.update_yaxes(type="log", showgrid=True, zeroline=False, dtick="D2", tickformat=".2~g", minor=dict(showgrid=False))
    else:
        fig.update_yaxes(type="linear", showgrid=True, nticks=5, zeroline=False)
    fig.update_xaxes(showgrid=False, tickformat="%d %b", nticks=4)
    return plotly_layout(fig)


def _sentence(s, c, unit, var, yrs, status) -> str:
    s = s.dropna()
    if len(s) < 5:
        return ""
    d = s.iloc[-1] - s.iloc[max(0, len(s) - 30)]
    rng = float(np.nanmax(s) - np.nanmin(s)) or 1.0
    move = "Rising" if d > 0.15 * rng else ("Falling" if d < -0.15 * rng else "Steady")
    usual_move = c["mean"].dropna()
    um = usual_move.iloc[-1] - usual_move.iloc[max(0, len(usual_move) - 30)] if len(usual_move) > 5 else 0
    same = (np.sign(um) == np.sign(d)) and move != "Steady"
    first = tr_(f"{move} over the last month") + (tr_(", as usual for the season") if same else "")
    last, mean = s.iloc[-1], c["mean"].reindex(s.index).iloc[-1]
    lo, hi = c["p10"].reindex(s.index).iloc[-1], c["p90"].reindex(s.index).iloc[-1]
    ref = tr_("the {yrs} average", yrs=yrs) if yrs else tr_("the usual value")
    if A.VARIABLES[var].get("log") and mean and mean > 0:
        ratio = last / mean
        second = tr_("about {x} times {ref}", x=num(f"{ratio:.1f}"), ref=ref)
    else:
        diff = last - mean
        word = {"sst": ("warmer", "colder")}.get(var, ("higher", "lower"))[0 if diff >= 0 else 1]
        second = tr_(f"about {{x}} {{unit}} {word} than {{ref}}", x=num(f"{abs(diff):.2g}"), unit=unit, ref=ref)
    inside = lo <= last <= hi if (pd.notna(lo) and pd.notna(hi)) else None
    third = ("Still within the usual range." if inside else
             ("Above the usual range." if (inside is False and last > hi) else
              ("Below the usual range." if inside is False else "")))
    return f"{first}, {second}. {tr_(third) if third else ''}".strip()


# ------------------------------------------------------------------------------------------ folded sections
def _sources_html(items, unit, var) -> str:
    """Every source compared at this point. Sources that are not used (untrusted, indicative only, under QC) stay
    in the table, greyed out, with the reason."""
    t = tokens()
    rows = []
    for it in items:
        s = it.get("series")
        last = s[s.index <= A.today()].dropna() if s is not None else None
        latest = f"{_fmt(float(last.iloc[-1]))} {unit}" if (last is not None and len(last)) else "-"
        dist = it["meta"].get("distance_km")
        where = num(f"{dist} km") if dist is not None else "-"
        style = ""
        if it.get("untrusted"):
            trust = it["meta"].get("trust") or "untrusted"
            reason = it["meta"].get("trust_reason")
            if not reason:
                reason = tr_({"indicative": "Indicative only: used for comparison, never for thresholds or trends.",
                              "not_usable_absolute": "Not usable as absolute values."}.get(
                    trust, "Not quality-checked yet (under QC)."))
            else:
                reason = data(reason)
            where = tr_({"indicative": "indicative only"}.get(trust, "not used")) + ". " + reason
            style = f" style='color:{t['muted']}'"
        rows.append(f"<tr{style}><td>{esc(data(it['label']))}</td>"
                    f"<td>{esc(tr_(ORIGIN_LABEL.get(it['origin'], it['origin'])))}</td>"
                    f"<td class='n'>{esc(num(latest))}</td><td>{esc(where)}</td></tr>")
    return (f"<table class='bsv-table'><thead><tr><th>{tr_('Source')}</th><th>{tr_('Origin')}</th><th>{tr_('Latest')}</th>"
            f"<th>{tr_('Distance or status')}</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")


def _validation_html(var, profile) -> str:
    """What the source check says for this variable (marinekit.validation.source_summary): the trusted source,
    its typical error and bias, a plain reading, caveats, and the sources not used with their reason."""
    s = A.source_summary(var)
    if not s:
        return ""
    lvl = P.level(profile)
    t = tokens()
    conf = {"high": "Reliable", "medium": "Fairly reliable", "low": "Rough guide only"}.get(s.get("confidence"), "")
    out = [f"<div class='bsv-lbl' style='margin:18px 0 6px 0'>{esc(tr_('Source check: {x}', x=data(s['title'])))}</div>",
           "<table class='bsv-table'><tbody>"]

    def row(k, v):
        out.append(f"<tr><td style='width:28%'>{esc(k)}</td><td>{esc(v)}</td></tr>")
    row(tr_("Trusted source"), data(s["trusted_label"]))
    row(tr_("Typical error"), data(s["uncertainty"]))
    if lvl != "public" and s.get("bias") is not None:
        eu = s.get("error_unit") or ""
        rng = s.get("bias_range")
        b = num(f"{s['bias']:+.2f} {eu}")
        if lvl == "researcher" and rng:
            b += " " + tr_("(by station {a} to {b})", a=num(f"{rng[0]:+.2f}"), b=num(f"{rng[1]:+.2f}"))
        row(tr_("Bias"), b)
    if lvl == "researcher" and s.get("rmse") is not None:
        row("RMSE", num(f"{s['rmse']:.2f} {s.get('error_unit') or ''}"))
    if conf:
        row(tr_("Confidence"), tr_(conf))
    row(tr_("In plain words"), data(s["reading"]))
    out.append("</tbody></table>")
    cav = s.get("caveats") or []
    if lvl in ("student", "stakeholder"):
        cav = cav[:1]
    elif lvl == "public":
        cav = []
    if cav:
        out.append(f"<div class='bsv-lbl' style='margin:14px 0 4px 0'>{esc(tr_('Caveats'))}</div><ul class='bsv-list'>"
                   + "".join(f"<li>{esc(data(c))}</li>" for c in cav) + "</ul>")
    if s.get("untrusted"):
        out.append(f"<div class='bsv-lbl' style='margin:14px 0 4px 0'>{esc(tr_('Not used'))}</div>"
                   f"<ul class='bsv-list' style='color:{t['muted']}'>"
                   + "".join(f"<li>{esc(data(u['source']))}: {esc(data(u['reason']))}</li>" for u in s["untrusted"])
                   + "</ul>")
    if lvl == "researcher":
        bs = s.get("basis") or {}
        out.append("<p class='bsv-note'>" + esc(tr_(
            "Headline pair {pair}, {n} matched days at {st}; validation run of {run}. All numbers indicative.",
            pair=data(s.get("headline_pair") or ""), n=s.get("n"), st=", ".join(s.get("stations") or []),
            run=dt(bs.get("run_date") or "2026-11-23", "%d %b %Y"))) + "</p>")
    return "".join(out)


def _chain(card, drivers, s, c, var) -> list[str]:
    steps = []
    if s is not None and c is not None and len(s.dropna()):
        x = s.dropna()
        lo, hi = c["p10"].reindex(x.index).iloc[-1], c["p90"].reindex(x.index).iloc[-1]
        inside = pd.notna(lo) and pd.notna(hi) and lo <= x.iloc[-1] <= hi
        steps.append(tr_("Season: the value is inside the usual range for this date, so the season explains it.") if inside
                     else tr_("Season: the value is outside the usual range for this date; the season alone does not explain it."))
    else:
        steps.append(tr_("Season: no recent series here; see the card value and its reference period."))
    if drivers:
        steps.append(tr_("River and upwelling drivers: {x}", x=data(drivers.get('why')) or tr_('no driver active')))
    else:
        steps.append(tr_("River and upwelling drivers: not computed for this place yet."))
    steps.append(tr_("Weather: storms and wind mixing in the last days are checked by the waves and wind data (Seabed page)."))
    dn = (card or {}).get("driver_note")
    steps.append(tr_("Left after natural causes: {x}", x=data(dn)) if dn else
                 tr_("Left after natural causes: no anomaly to explain, so nothing is attributed to a pressure."))
    return steps


# ------------------------------------------------------------------------------------------ long-term trend tab
def trend_view(sel, var, profile):
    """Long-term trend behind the quality gate (marinekit.seasonal.long_term_trend): the number only when the gate
    passes, otherwise the reason."""
    detail = P.show_detail(profile)
    if var not in A.SEASONAL_VARS:
        st.info(tr_("No checked long-term trend for this variable. The quality-checked trend analysis covers sea "
                    "temperature, salinity, surface oxygen and chlorophyll-a."))
        return
    seas, pending = _seasonal(var, sel)
    if pending:
        st.info(tr_("Working out the long-term trend for this place (the first time takes up to a minute)."))
        _poll_seasonal(var, sel)
        return
    trd = (seas or {}).get("trend") or {}
    if not trd.get("show"):
        st.markdown(f"<p class='bsv-verdict'>{esc(tr_('No long-term trend shown here.'))}</p>"
                    f"<p class='bsv-vsub'>{esc(plain_gate(trd.get('gate_reason'), 'trend', profile))}</p>",
                    unsafe_allow_html=True)
        return
    unit = str(trd.get("unit") or "").replace(" per decade", "")
    slope, (lo, hi) = trd["slope_per_decade"], trd["ci"]
    y0, y1 = trd["years"] if trd.get("years") else ("-", "-")
    climate = trd.get("level") == "climate"
    if trd.get("significant"):
        head = tr_("Rising by {x} {u} per decade", x=num(f"{abs(slope):.2f}"), u=unit) if slope > 0 else \
            tr_("Falling by {x} {u} per decade", x=num(f"{abs(slope):.2f}"), u=unit)
    else:
        head = tr_("No clear long-term change")
    sub = (tr_("Climate trend: {n} complete years ({a}-{b}).", n=trd["n_years"], a=y0, b=y1) if climate else
           tr_("Indicative trend: {n} complete years ({a}-{b}); a climate trend needs 20.", n=trd["n_years"], a=y0, b=y1))
    if not trd.get("significant"):
        sub += " " + tr_("The year-to-year ups and downs are as large as the change.")
    st.markdown(f"<p class='bsv-verdict'>{esc(head)}</p><p class='bsv-vsub' style='margin-bottom:18px'>{esc(sub)}</p>",
                unsafe_allow_html=True)
    origin = tr_(ORIGIN_LABEL.get(trd.get("origin"), trd.get("origin") or ""))
    st.markdown("<div class='bsv-stats'>"
                + _stat(tr_("Change per decade"), num(_fmt(slope, sign=True)), unit)
                + _stat(tr_("Uncertainty (95 %)"), num(f"{lo:+.2f} {tr_('to')} {hi:+.2f}"), unit)
                + _stat(tr_("Years used"), f"{y0}-{y1}", f" ({trd['n_years']})")
                + _stat(tr_("Source"), origin)
                + "</div>", unsafe_allow_html=True)
    ann = _annual(var, sel)
    if ann is not None and trd.get("years"):
        ann = ann[(ann.index >= y0) & (ann.index <= y1)]
        if len(ann) >= 3:
            x = ann.index.to_numpy(float)
            line = float(ann.mean()) + slope / 10 * (x - x.mean())
            t = tokens()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ann.index, y=ann.values, mode="markers+lines", name=tr_("annual mean"),
                                     line=dict(color=t["accent"], width=1), marker=dict(size=7)))
            fig.add_trace(go.Scatter(x=ann.index, y=line, mode="lines", name=tr_("trend"),
                                     line=dict(color=STATUS["alert"][0], width=2.2)))
            fig.update_layout(height=300, margin=dict(l=44, r=12, t=8, b=30), hovermode="closest", showlegend=False)
            fig.update_yaxes(title=unit)
            st.plotly_chart(plotly_layout(fig), width="stretch", theme=None,
                            config={"displaylogo": False, "displayModeBar": False})
            st.caption(tr_("Dots: annual means of the long record at this point. Line: the checked trend, drawn "
                           "through their average."))
    note = tr_("Trend gate (OURS): a trend needs 8 complete years of a reliable source; below 20 years it is "
               "indicative, from 20 years a climate trend.")
    if detail:
        note += " " + data(trd.get("gate_reason") or "") + "."
        note += " " + tr_("Source: {s}; p = {p}.", s=data(trd.get("source_label") or trd.get("source") or ""),
                          p=num(f"{trd['p_value']:.2f}"))
        if trd.get("station"):
            note += " " + tr_("Precomputed at station {st} ({d} km away).", st=trd["station"],
                              d=num(f"{trd.get('distance_km') or 0:.1f}"))
    st.markdown(f"<p class='bsv-note'>{esc(note)}</p>", unsafe_allow_html=True)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _annual_cached(var, lat, lon):
    s = A.long_series(var, lat, lon)
    if s is None or s.empty:
        return None
    s = s[s.index.year < A.today().year]
    g = s.groupby(s.index.year)
    return g.mean()[g.count() >= 300]


def _annual(var, sel):
    try:
        return _annual_cached(var, round(sel["lat"], 4), round(sel["lon"], 4))
    except Exception:
        return None


# ------------------------------------------------------------------------------------------ page
def page():
    ss = st.session_state
    profile = ss.profile
    detail = P.show_detail(profile)
    day_s, _ = SH.day_season()
    sel = ss.sel
    if ss.get("w_var") not in WVARS:
        ss["w_var"] = "sst"
    if ss.get("w_wview") not in VIEWS:
        ss["w_wview"] = "now"
    key = ss["w_var"]
    name, var, cid = WVARS[key]
    cards = _cards(sel, day_s, profile)
    card = cards.get(cid) if cid else None
    aside, main = st.columns([1, 3.4], gap=None)
    with aside:
        with st.container(key="bsv_aside"):
            var_list(sel, cards, key)
    with main:
        with st.container(key="page_body"):
            if var is None:
                _card_only(name, key, card, cards.get("drivers"), profile, detail)
                return
            _variable(name, var, card, cards.get("drivers"), sel, profile, detail)


def _variable(name, var, card, drivers, sel, profile, detail):
    ss = st.session_state
    v = A.VARIABLES[var]
    unit = v["unit"]
    with st.spinner(tr_("Loading the series and the usual range...")):
        items = A.series_for(var, sel["lat"], sel["lon"])
        clim = A.soft(A.climatology, var, sel["lat"], sel["lon"])
    main = _main_item(items)
    yrs = clim.attrs.get("years") if clim is not None else None
    yrs_s = f"{yrs[0]}-{yrs[1]}" if isinstance(yrs, (list, tuple)) and len(yrs) == 2 else (str(yrs) if yrs else "")
    origin = tr_(ORIGIN_LABEL.get(main["origin"], main["origin"])) if main else tr_("no data")
    title = tr_(P.VAR_TEXT.get(var, {}).get(P.level(profile)) or v["label"])
    src = data(main["label"]) if main else tr_("no source at this point")

    seas, pending = _seasonal(var, sel) if var in A.SEASONAL_VARS else (None, False)
    cyc = (seas or {}).get("cycle") or {}
    gated = var in A.SEASONAL_VARS  # band and trend come from the quality-gated seasonal analysis
    s60 = c60 = None
    band_note = ""
    if main is not None:
        s = main["series"]
        s = s[s.index <= pd.Timestamp(A.today())].dropna()
        s60 = s[s.index > s.index.max() - pd.Timedelta(days=WINDOW)] if len(s) else s
    if s60 is not None and len(s60) and not gated and clim is not None:
        c60 = clim.reindex(A.doy365(s60.index))
        c60.index = s60.index
    elif s60 is not None and len(s60) and gated and cyc.get("show"):
        b = A.usual_band(var, sel["lat"], sel["lon"], s60.index)
        if b is not None and b["fit"].notna().any():
            c60 = pd.DataFrame({"mean": b["fit"].to_numpy(), "p10": b["lo"].to_numpy(), "p90": b["hi"].to_numpy()},
                               index=s60.index)
            ys = re.findall(r"\d{4}", str(cyc.get("window") or ""))
            yrs_s = f"{ys[0]}-{ys[-1]}" if len(ys) >= 2 else yrs_s
            band_note = tr_("Usual range: seasonal fit to {w}, plus or minus 1.28 times the weekly spread (about "
                            "the 10th to 90th percentile). Thresholds OURS.", w=_window_txt(cyc))
    elif gated and pending:
        band_note = tr_("Working out the usual range and the long-term trend for this place (the first time takes "
                        "up to a minute).")
    elif gated:
        why = plain_gate(cyc.get("gate_reason"), "cycle", profile)
        band_note = tr_("No usual range shown: {why}", why=why[:1].lower() + why[1:])
    if var == "sst" and s60 is not None and len(s60):
        sd = A.sst_display(sel["lat"], sel["lon"], str(A.today().date()))
        if sd and sd.get("value") is not None:  # the same SST as the temperature card
            s60 = s60.copy()
            s60.loc[pd.Timestamp(sd["date"])] = float(sd["value"])
            s60 = s60.sort_index()
            if c60 is not None:
                c60 = c60.reindex(s60.index).interpolate(limit_direction="both")
    # 4 headline numbers
    today_v = float(s60.iloc[-1]) if (s60 is not None and len(s60)) else None
    usual_v = float(c60["mean"].iloc[-1]) if (c60 is not None and len(c60)) else None
    if v.get("log") and today_v and usual_v:
        diff_txt, diff_unit = f"{today_v / usual_v:.1f}", tr_("x usual")
    else:
        diff_txt = _fmt(today_v - usual_v, sign=True) if (today_v is not None and usual_v is not None) else "-"
        diff_unit = unit
    st.markdown(f"<div class='bsv-whead'><div><div class='bsv-place'>{esc(title)}</div>"
                f"<div class='bsv-lbl' style='margin-top:6px'>{esc(origin)} &middot; {esc(src)}"
                + (f" &middot; {tr_('usual')} = {esc(yrs_s)}" if (yrs_s and c60 is not None) else "")
                + "</div></div></div>", unsafe_allow_html=True)
    with st.container(key="wtabs"):
        view = st.segmented_control(tr_("Analysis"), list(VIEWS), key="w_wview", format_func=lambda k: tr_(VIEWS[k]),
                                    required=True, label_visibility="collapsed") or "now"
    if view == "trend":
        trend_view(sel, var, profile)
        return
    if view == "obsmod":
        PN.obs_model_view(sel, var, profile)
        return
    trd = (seas or {}).get("trend") or {}
    tr = trd if trd.get("show") else None
    trend_lab = (tr_("Trend since {y}", y=tr["years"][0]) if (tr and tr.get("years")) else tr_("Long-term trend"))
    trend_val = _fmt(tr["slope_per_decade"], sign=True) if tr else "-"
    status = card.get("status") if card else None
    when = f" ({dt(s60.index[-1], '%d %b')})" if (s60 is not None and len(s60)) else ""
    st.markdown("<div class='bsv-stats'>"
                + _stat(tr_("Latest") + when, num(_fmt(today_v)), unit)
                + _stat(tr_("Usual"), num(_fmt(usual_v)), unit)
                + _stat(tr_("Difference"), num(diff_txt), diff_unit, _status_tag(status))
                + _stat(trend_lab, num(trend_val), tr_("{u} / decade", u=trd.get("unit", unit).replace(" per decade", ""))
                        if tr else "")
                + "</div>", unsafe_allow_html=True)
    if s60 is None or not len(s60):
        st.info(tr_("No recent series for this variable at this point."))
        if band_note:
            st.markdown(f"<p class='bsv-note'>{esc(band_note)}</p>", unsafe_allow_html=True)
        if pending:
            _poll_seasonal(var, sel)
    elif c60 is None:
        t = tokens()
        st.markdown(f"<div class='bsv-fighead'><span class='bsv-lbl'>{tr_('Last {n} days', n=WINDOW)}</span>"
                    f"<span class='bsv-key'><span><i style='background:{t['accent']};height:3px'></i>"
                    f"{tr_('this year')}</span></span></div>", unsafe_allow_html=True)
        st.plotly_chart(chart_60(s60, None, unit, bool(v.get("log")), origin), width="stretch", theme=None,
                        config={"displaylogo": False, "displayModeBar": False})
        st.markdown(f"<p class='bsv-vsub' style='margin:0 0 18px 0'>{esc(band_note)}</p>", unsafe_allow_html=True)
        if pending:
            _poll_seasonal(var, sel)
    else:
        t = tokens()
        st.markdown(f"<div class='bsv-fighead'><span class='bsv-lbl'>{tr_('Last {n} days', n=WINDOW)}</span>"
                    "<span class='bsv-key'>"
                    f"<span><i style='background:{t['accent']};height:3px'></i>{tr_('this year')}</span>"
                    f"<span><i style='background:{t['line2']};height:10px'></i>{tr_('usual range')}</span>"
                    f"<span><i style='border-top:2px dashed {t['muted']};height:0'></i>{tr_('usual')}</span></span></div>",
                    unsafe_allow_html=True)
        st.plotly_chart(chart_60(s60, c60, unit, bool(v.get("log")), origin), width="stretch", theme=None,
                        config={"displaylogo": False, "displayModeBar": False})
        st.markdown(f"<p class='bsv-vsub' style='margin:0 0 6px 0'>{esc(_sentence(s60, c60, unit, var, yrs_s, status))}</p>",
                    unsafe_allow_html=True)
        st.markdown(f"<p class='bsv-note' style='margin:0 0 18px 0'>{esc(band_note or _clim_note(clim))}</p>",
                    unsafe_allow_html=True)
    # folded sections
    n_used = sum(1 for i in items if not i.get("untrusted"))
    n_out = sum(1 for i in items if i.get("untrusted"))
    with st.expander(tr_("Sources  ·  {n} compared", n=n_used) + (tr_(", {n} excluded", n=n_out) if n_out else "")):
        st.markdown(_sources_html(items, unit, var) + _validation_html(var, profile), unsafe_allow_html=True)
        if detail and clim is not None:
            st.caption(tr_("Usual range: ") + ", ".join(f"{tr_(k)} {num(str(val))}" for k, val in clim.attrs.items()
                                                    if k in ("dataset", "years", "window_days", "n_years", "space")))
    with st.expander(tr_("Natural or pressure?  ·  rule chain, 4 steps")):
        steps = _chain(card, drivers, s60, c60, var)
        st.markdown("<ol class='bsv-chain'>" + "".join(f"<li>{esc(x)}</li>" for x in steps) + "</ol>",
                    unsafe_allow_html=True)
    with st.expander(tr_("Data  ·  CSV download")):
        if s60 is not None and len(s60):
            cc = c60 if c60 is not None else pd.DataFrame(index=s60.index, columns=["mean", "p10", "p90"], dtype=float)
            df = pd.DataFrame({"date": s60.index.date, f"value_{unit}": s60.values, "usual_mean": cc["mean"].values,
                               "usual_p10": cc["p10"].values, "usual_p90": cc["p90"].values})
            df.insert(1, "origin", origin)
            st.download_button(tr_("Download the {n}-day series (CSV)", n=WINDOW), df.to_csv(index=False).encode(),
                               file_name=f"{var}_{WINDOW}d_{sel['lat']:.3f}_{sel['lon']:.3f}.csv", mime="text/csv",
                               key="dl_60")
        st.caption(tr_("Dataset IDs and licences are on the Methods page."))


def _card_only(name, key, card, drivers, profile, detail):
    """Nutrients and pH: no daily series here, so the card's numbers and wording stand in for the chart."""
    lvl = P.level(profile)
    origin = tr_(ORIGIN_LABEL.get("in-situ" if (card or {}).get("evidence") == "measured" else (card or {}).get("evidence"),
                                  "")) if card else ""
    sub = tr_({"nutrients": "Past ship samples (EMODnet Chemistry). No live nutrient data after about 2020.",
               "ph": "Model estimate (Copernicus BGC). No pH sensor on this coast."}[key])
    st.markdown(f"<div class='bsv-whead'><div><div class='bsv-place'>{esc(tr_(name))}</div>"
                f"<div class='bsv-lbl' style='margin-top:6px'>{esc(origin)} &middot; {esc(sub)}</div></div></div>",
                unsafe_allow_html=True)
    if not card:
        st.info(tr_("The health card for this place is still being computed; it appears here by itself."))
        return
    ref = card.get("reference") if isinstance(card.get("reference"), dict) else {}
    unit = card.get("unit") or ""
    usual = ref.get("value")
    st.markdown("<div class='bsv-stats'>"
                + _stat(tr_("Latest"), num(PN._num(card.get("value"))), unit)
                + _stat(tr_("Reference") if key == "nutrients" else tr_("Usual"),
                        num(PN._num(usual)) if usual is not None else "-", unit if usual is not None else "")
                + _stat(tr_("Status"), STATUS[card.get("status") or "no_data"][1], "", "")
                + _stat(tr_("Confidence"), data(card.get("confidence") or "-"))
                + "</div>", unsafe_allow_html=True)
    txt = card.get("text") if isinstance(card.get("text"), dict) else {}
    st.markdown(f"<p class='bsv-verdict'>{esc(data(txt.get(lvl) or ''))}</p><p class='bsv-vsub' style='margin-bottom:18px'>"
                f"{esc(data(card.get('why') or ''))}</p>", unsafe_allow_html=True)
    if ref.get("threshold"):
        st.markdown(f"<p class='bsv-note'>{tr_('Threshold')}: {esc(data(ref['threshold']))}"
                    + (f" ({esc(ref.get('threshold_type'))})" if ref.get("threshold_type") else "") + "</p>",
                    unsafe_allow_html=True)
    with st.expander(tr_("Sources")):
        rows = "".join(f"<tr><td>{esc(data(s.get('label') or s.get('dataset')))}</td>"
                       f"<td>{esc(tr_(ORIGIN_LABEL.get(s.get('origin'), s.get('origin')) or ''))}</td><td>{esc(PN.day_txt(s.get('date')))}</td>"
                       f"<td>{esc(num(str(s.get('distance_km')) + ' km') if s.get('distance_km') not in (None, '') else '-')}</td></tr>"
                       for s in card.get("sources") or [] if s.get("dataset") != "zone sampling")
        st.markdown(f"<table class='bsv-table'><thead><tr><th>{tr_('Source')}</th><th>{tr_('Origin')}</th>"
                    f"<th>{tr_('Date')}</th><th>{tr_('Distance')}</th></tr></thead><tbody>{rows}</tbody></table>"
                    + (_validation_html("nutrients", profile) + _validation_html("po4", profile)
                       if key == "nutrients" else ""), unsafe_allow_html=True)
    with st.expander(tr_("Natural or pressure?  ·  rule chain")):
        steps = _chain(card, drivers, None, None, key)
        st.markdown("<ol class='bsv-chain'>" + "".join(f"<li>{esc(x)}</li>" for x in steps) + "</ol>",
                    unsafe_allow_html=True)
