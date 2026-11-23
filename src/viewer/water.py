"""Water quality page (direction B2): variable list, 4 headline numbers, 60-day chart against the usual range,
and folded Sources / Natural or pressure? / Data sections."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from viewer import adapters as A
from viewer import panels as PN
from viewer import profiles as P
from viewer import shell as SH
from viewer.style import ORIGIN_LABEL, STATUS, esc, plotly_layout, status_square, tokens

# list key -> (name, series variable in adapters.VARIABLES or None, health card id)
WVARS = {
    "sst": ("Temperature", "sst", "temperature"),
    "sal": ("Salinity", "sal", None),
    "o2_bottom": ("Oxygen, seabed", "o2_bottom", "oxygen"),
    "chl": ("Chlorophyll-a", "chl", "blooms"),
    "kd490": ("Water clarity", "kd490", "clarity"),
    "nutrients": ("Nutrients", None, "nutrients"),
    "ph": ("Acidity (pH)", None, "acidification"),
}
VIEWS = {"now": "Now vs usual", "trend": "Long-term trend", "obsmod": "Measured vs model"}
WINDOW = 60


# ------------------------------------------------------------------------------------------ data helpers
def _cards(sel, day, profile) -> dict:
    cards = A.zone_cards(sel["lat"], sel["lon"], day, P.card_profile(profile), sel.get("wkt"), wait=4)
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


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def _trend(var, lat, lon):
    s = A.soft(A.long_series, var, lat, lon)
    if s is None or s.empty:
        return None
    tr = A.annual_trend(s)
    if tr is None:
        return None
    return dict(slope=tr["slope_decade"], ci=tr["ci_decade"], start=int(tr["years"][0]), end=int(tr["years"][1]),
                annual=tr["annual"])


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
    st.markdown(f"<div class='bsv-sec'><div class='bsv-lbl'>Place</div><div class='bsv-place' style='font-size:26px'>"
                f"{esc(sel['name'])}</div><div class='bsv-lbl' style='margin-top:4px'>{sel['lat']:.3f} N &middot; "
                f"{sel['lon']:.3f} E</div></div>", unsafe_allow_html=True)
    with st.container(key="bsv_pad"):
        SH.place_picker("Search another place")
    st.markdown("<div class='bsv-lbl' style='padding:18px 20px 10px 20px'>Water quality</div>", unsafe_allow_html=True)
    for k, (name, var, cid) in WVARS.items():
        c = cards.get(cid) if cid else None
        status = c.get("status") if c else "no_data"
        val = PN._num(c.get("value"), c.get("unit") or "") if (c and c.get("value") is not None) else ""
        if c is None and var:
            status, val = _series_status(var, sel)
        active = " active" if k == current else ""
        with st.container(key=f"vrow_{k}"):
            st.markdown(f"<div class='bsv-vrow{active}'>{status_square(status)}<span class='nm'>{esc(name)}</span>"
                        f"<span class='vl'>{esc(val)}</span></div>", unsafe_allow_html=True)
            st.button(f"Show {name}", key=f"vbtn_{k}", on_click=_pick, args=(k,))
    with st.container(key="aside_foot"):
        st.page_link(SH.PAGE_OBJS["seabed"], label="Waves, currents and depth")
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
    fig.add_trace(go.Scatter(x=s.index, y=c["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s.index, y=c["p10"], fill="tonexty", fillcolor=t["line2"], line=dict(width=0),
                             name="usual range (p10-p90)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s.index, y=c["mean"], line=dict(color=t["muted"], width=1.5, dash="dash"), name="usual",
                             hovertemplate="usual %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, line=dict(color=t["accent"], width=2.5), name="this year",
                             hovertemplate="%{x|%d %b}: %{y:.2f} " + unit + "<extra>" + esc(origin) + "</extra>"))
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
    first = f"{move} over the last month" + (", as usual for the season" if same else "")
    last, mean = s.iloc[-1], c["mean"].reindex(s.index).iloc[-1]
    lo, hi = c["p10"].reindex(s.index).iloc[-1], c["p90"].reindex(s.index).iloc[-1]
    ref = f"the {yrs} average" if yrs else "the usual value"
    if A.VARIABLES[var].get("log") and mean and mean > 0:
        ratio = last / mean
        second = f"about {ratio:.1f} times {ref}"
    else:
        diff = last - mean
        word = {"sst": ("warmer", "colder")}.get(var, ("higher", "lower"))[0 if diff >= 0 else 1]
        second = f"about {abs(diff):.2g} {unit} {word} than {ref}"
    inside = lo <= last <= hi if (pd.notna(lo) and pd.notna(hi)) else None
    third = ("Still within the usual range." if inside else
             ("Above the usual range." if (inside is False and last > hi) else
              ("Below the usual range." if inside is False else "")))
    return f"{first}, {second}. {third}".strip()


# ------------------------------------------------------------------------------------------ folded sections
def _sources_html(items, unit, cid_card) -> str:
    t = tokens()
    rows = []
    for it in items:
        s = it.get("series")
        last = s[s.index <= A.today()].dropna() if s is not None else None
        latest = f"{_fmt(float(last.iloc[-1]))} {unit}" if (last is not None and len(last)) else "-"
        dist = it["meta"].get("distance_km")
        where = f"{dist} km" if dist is not None else "-"
        if it.get("untrusted"):
            latest, where = "not used", "not quality-checked"
        rows.append(f"<tr><td>{esc(it['label'])}</td><td>{esc(ORIGIN_LABEL.get(it['origin'], it['origin']))}</td>"
                    f"<td class='n'>{esc(latest)}</td><td>{esc(where)}</td></tr>")
    return ("<table class='bsv-table'><thead><tr><th>Source</th><th>Origin</th><th>Latest</th><th>Distance</th></tr>"
            f"</thead><tbody>{''.join(rows)}</tbody></table>")


def _chain(card, drivers, s, c, var) -> list[str]:
    steps = []
    if s is not None and c is not None and len(s.dropna()):
        x = s.dropna()
        lo, hi = c["p10"].reindex(x.index).iloc[-1], c["p90"].reindex(x.index).iloc[-1]
        inside = pd.notna(lo) and pd.notna(hi) and lo <= x.iloc[-1] <= hi
        steps.append("Season: the value is inside the usual range for this date, so the season explains it." if inside
                     else "Season: the value is outside the usual range for this date; the season alone does not explain it.")
    else:
        steps.append("Season: no recent series here; see the card value and its reference period.")
    if drivers:
        steps.append(f"River and upwelling drivers: {drivers.get('why') or 'no driver active'}")
    else:
        steps.append("River and upwelling drivers: not computed for this place yet.")
    steps.append("Weather: storms and wind mixing in the last days are checked by the waves and wind data (Seabed page).")
    dn = (card or {}).get("driver_note")
    steps.append(f"Left after natural causes: {dn}" if dn else
                 "Left after natural causes: no anomaly to explain, so nothing is attributed to a pressure.")
    return steps


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
    with st.spinner("Loading the series and the usual range..."):
        items = A.series_for(var, sel["lat"], sel["lon"])
        clim = A.soft(A.climatology, var, sel["lat"], sel["lon"])
    main = _main_item(items)
    yrs = clim.attrs.get("years") if clim is not None else None
    yrs_s = f"{yrs[0]}-{yrs[1]}" if isinstance(yrs, (list, tuple)) and len(yrs) == 2 else (str(yrs) if yrs else "")
    origin = ORIGIN_LABEL.get(main["origin"], main["origin"]) if main else "no data"
    title = P.VAR_TEXT.get(var, {}).get(P.level(profile)) or v["label"]
    src = main["label"] if main else "no source at this point"
    st.markdown(f"<div class='bsv-whead'><div><div class='bsv-place'>{esc(title)}</div>"
                f"<div class='bsv-lbl' style='margin-top:6px'>{esc(origin)} &middot; {esc(src)}"
                + (f" &middot; usual = {esc(yrs_s)}" if yrs_s else "") + "</div></div></div>", unsafe_allow_html=True)
    with st.container(key="wtabs"):
        view = st.segmented_control("Analysis", list(VIEWS), key="w_wview", format_func=VIEWS.get, required=True,
                                    label_visibility="collapsed") or "now"
    if view == "trend":
        PN.trend_view(sel, var, profile)
        return
    if view == "obsmod":
        PN.obs_model_view(sel, var, profile)
        return

    s60 = c60 = None
    if main is not None and clim is not None:
        s = main["series"]
        s = s[s.index <= pd.Timestamp(A.today())].dropna()
        s60 = s[s.index > s.index.max() - pd.Timedelta(days=WINDOW)] if len(s) else s
        c60 = clim.reindex(A.doy365(s60.index))
        c60.index = s60.index
    # 4 headline numbers
    today_v = float(s60.iloc[-1]) if (s60 is not None and len(s60)) else None
    usual_v = float(c60["mean"].iloc[-1]) if (c60 is not None and len(c60)) else None
    if v.get("log") and today_v and usual_v:
        diff_txt, diff_unit = f"{today_v / usual_v:.1f}", "x usual"
    else:
        diff_txt = _fmt(today_v - usual_v, sign=True) if (today_v is not None and usual_v is not None) else "-"
        diff_unit = unit
    tr = _trend(var, round(sel["lat"], 4), round(sel["lon"], 4))
    trend_lab = f"Trend since {tr['start']}" if tr else "Long-term trend"
    trend_val = _fmt(tr["slope"], sign=True) if tr else "-"
    status = card.get("status") if card else None
    when = f" ({s60.index[-1]:%d %b})" if (s60 is not None and len(s60)) else ""
    st.markdown("<div class='bsv-stats'>"
                + _stat(f"Latest{when}", _fmt(today_v), unit)
                + _stat("Usual", _fmt(usual_v), unit)
                + _stat("Difference", diff_txt, diff_unit, _status_tag(status))
                + _stat(trend_lab, trend_val, f"{unit} / decade" if tr else "")
                + "</div>", unsafe_allow_html=True)
    if s60 is None or not len(s60):
        st.info("No recent series or no usual range for this variable at this point.")
    else:
        t = tokens()
        st.markdown(f"<div class='bsv-fighead'><span class='bsv-lbl'>Last {WINDOW} days</span><span class='bsv-key'>"
                    f"<span><i style='background:{t['accent']};height:3px'></i>this year</span>"
                    f"<span><i style='background:{t['line2']};height:10px'></i>usual range</span>"
                    f"<span><i style='border-top:2px dashed {t['muted']};height:0'></i>usual</span></span></div>",
                    unsafe_allow_html=True)
        st.plotly_chart(chart_60(s60, c60, unit, bool(v.get("log")), origin), width="stretch", theme=None,
                        config={"displaylogo": False, "displayModeBar": False})
        st.markdown(f"<p class='bsv-vsub' style='margin:0 0 18px 0'>{esc(_sentence(s60, c60, unit, var, yrs_s, status))}</p>",
                    unsafe_allow_html=True)
    # folded sections
    n_used = sum(1 for i in items if not i.get("untrusted"))
    n_out = sum(1 for i in items if i.get("untrusted"))
    with st.expander(f"Sources  ·  {n_used} compared" + (f", {n_out} excluded" if n_out else "")):
        st.markdown(_sources_html(items, unit, card), unsafe_allow_html=True)
        if n_out:
            st.caption("Excluded: coastal buoys EUXRoCB0x and shore station 15480 are not quality-checked yet.")
        if detail and clim is not None:
            st.caption("Usual range: " + ", ".join(f"{k} {val}" for k, val in clim.attrs.items()
                                                    if k in ("dataset", "years", "window_days", "n_years", "space")))
    with st.expander("Natural or pressure?  ·  rule chain, 4 steps"):
        steps = _chain(card, drivers, s60, c60, var)
        st.markdown("<ol class='bsv-chain'>" + "".join(f"<li>{esc(x)}</li>" for x in steps) + "</ol>",
                    unsafe_allow_html=True)
    with st.expander("Data  ·  CSV download"):
        if s60 is not None and len(s60):
            df = pd.DataFrame({"date": s60.index.date, f"value_{unit}": s60.values, "usual_mean": c60["mean"].values,
                               "usual_p10": c60["p10"].values, "usual_p90": c60["p90"].values})
            df.insert(1, "origin", origin)
            st.download_button(f"Download the {WINDOW}-day series (CSV)", df.to_csv(index=False).encode(),
                               file_name=f"{var}_{WINDOW}d_{sel['lat']:.3f}_{sel['lon']:.3f}.csv", mime="text/csv",
                               key="dl_60")
        if tr is not None:
            ann = tr["annual"].rename(f"annual_mean_{unit}").to_frame()
            ann.index.name = "year"
            st.download_button(f"Download the {tr['start']}-{tr['end']} annual means (CSV)", ann.to_csv().encode(),
                               file_name=f"{var}_annual_{sel['lat']:.3f}_{sel['lon']:.3f}.csv", mime="text/csv",
                               key="dl_ann")
        st.caption("Dataset IDs and licences are on the Methods page.")


def _card_only(name, key, card, drivers, profile, detail):
    """Nutrients and pH: no daily series here, so the card's numbers and wording stand in for the chart."""
    lvl = P.level(profile)
    origin = ORIGIN_LABEL.get("in-situ" if (card or {}).get("evidence") == "measured" else (card or {}).get("evidence"),
                              "") if card else ""
    sub = {"nutrients": "Past ship samples (EMODnet Chemistry). No live nutrient data after about 2020.",
           "ph": "Model estimate (Copernicus BGC). No pH sensor on this coast."}[key]
    st.markdown(f"<div class='bsv-whead'><div><div class='bsv-place'>{esc(name)}</div>"
                f"<div class='bsv-lbl' style='margin-top:6px'>{esc(origin)} &middot; {esc(sub)}</div></div></div>",
                unsafe_allow_html=True)
    if not card:
        st.info("The health card for this place is still being computed; it appears here by itself.")
        return
    ref = card.get("reference") if isinstance(card.get("reference"), dict) else {}
    unit = card.get("unit") or ""
    usual = ref.get("value")
    st.markdown("<div class='bsv-stats'>"
                + _stat("Latest", PN._num(card.get("value")), unit)
                + _stat("Reference" if key == "nutrients" else "Usual", PN._num(usual) if usual is not None else "-",
                        unit if usual is not None else "")
                + _stat("Status", STATUS[card.get("status") or "no_data"][1], "", "")
                + _stat("Confidence", card.get("confidence") or "-")
                + "</div>", unsafe_allow_html=True)
    txt = card.get("text") if isinstance(card.get("text"), dict) else {}
    st.markdown(f"<p class='bsv-verdict'>{esc(txt.get(lvl) or '')}</p><p class='bsv-vsub' style='margin-bottom:18px'>"
                f"{esc(card.get('why') or '')}</p>", unsafe_allow_html=True)
    if ref.get("threshold"):
        st.markdown(f"<p class='bsv-note'>Threshold: {esc(ref['threshold'])}"
                    + (f" ({esc(ref.get('threshold_type'))})" if ref.get("threshold_type") else "") + "</p>",
                    unsafe_allow_html=True)
    with st.expander("Sources"):
        rows = "".join(f"<tr><td>{esc(s.get('label') or s.get('dataset'))}</td>"
                       f"<td>{esc(ORIGIN_LABEL.get(s.get('origin'), s.get('origin')))}</td><td>{esc(s.get('date') or '-')}</td>"
                       f"<td>{esc(str(s.get('distance_km')) + ' km' if s.get('distance_km') not in (None, '') else '-')}</td></tr>"
                       for s in card.get("sources") or [] if s.get("dataset") != "zone sampling")
        st.markdown("<table class='bsv-table'><thead><tr><th>Source</th><th>Origin</th><th>Date</th><th>Distance</th>"
                    f"</tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    with st.expander("Natural or pressure?  ·  rule chain"):
        steps = _chain(card, drivers, None, None, key)
        st.markdown("<ol class='bsv-chain'>" + "".join(f"<li>{esc(x)}</li>" for x in steps) + "</ol>",
                    unsafe_allow_html=True)
