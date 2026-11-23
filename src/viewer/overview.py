"""Overview page parts (direction B1): profile tabs, verdict, counts, compact card rows, bottom timeline."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from viewer import adapters as A
from viewer import panels as PN
from viewer import profiles as P
from viewer.style import ORIGIN_LABEL, STATUS, STATUS_LABEL, esc, status_square

# tab label -> role key
TABS = {"public": "Public", "student": "Student", "stakeholder": "Sector", "researcher": "Research"}
# card id -> variable of the Water quality chart (cards without one get no chart link)
CARD_VAR = {"temperature": "sst", "oxygen": "o2_bottom", "blooms": "chl", "clarity": "kd490", "drivers": "sal"}
ORDER = ("alert", "watch", "normal", "no_data")
_CHEV = ("<svg width='10' height='10' viewBox='0 0 10 10' aria-hidden='true'><path d='M3 1.5 L7 5 L3 8.5' fill='none' "
         "stroke='currentColor' stroke-width='1.5'/></svg>")
_CHEV_OPEN = ("<svg width='10' height='10' viewBox='0 0 10 10' aria-hidden='true'><path d='M1.5 3 L5 7 L8.5 3' fill='none' "
              "stroke='currentColor' stroke-width='1.5'/></svg>")


# ------------------------------------------------------------------------------------------ profile tabs
def _on_tab():
    ss = st.session_state
    role = ss.get("w_ptab") or ss.profile["role"]
    pr = dict(ss.profile)
    pr["role"] = role
    pr["sector"] = (pr.get("sector") or ss.get("w_psector") or "ports") if role == "stakeholder" else None
    pr["focus"] = (pr.get("focus") or list(P.FOCUS)[0]) if role == "researcher" else None
    ss.profile = pr
    ss.open_card = None


def _on_sector():
    ss = st.session_state
    pr = dict(ss.profile)
    pr["sector"] = ss.get("w_psector") or "ports"
    ss.profile = pr


def profile_tabs():
    ss = st.session_state
    role = ss.profile.get("role", "public")
    ss["w_ptab"] = role  # follow the profile (it can also change from the questionnaire or the other pages)
    with st.container(key="ptabs"):
        st.segmented_control("Viewing as", list(TABS), key="w_ptab", format_func=TABS.get, on_change=_on_tab, required=True,
                             label_visibility="collapsed", width="stretch")
    if role == "stakeholder":
        ss["w_psector"] = ss.profile.get("sector") or "ports"
        with st.container(key="bsv_pad"):
            st.selectbox("Sector", list(P.SECTORS), key="w_psector", format_func=P.SECTORS.get, on_change=_on_sector)


# ------------------------------------------------------------------------------------------ verdict and counts
def _counts(cards) -> dict:
    s = pd.Series([c.get("status") or "no_data" for c in cards]).value_counts()
    return {k: int(s.get(k, 0)) for k in ORDER}


def _names(cards, status) -> list[str]:
    return [c.get("title", "") for c in cards if c.get("status") == status]


def verdict(cards, profile, season, n_sectors: int, secs: str, day: str) -> tuple[str, str]:
    """One sentence for the profile, plus a shorter second line."""
    n = _counts(cards)
    role = profile.get("role", "public")
    with_data = len(cards) - n["no_data"]
    when = pd.Timestamp(day)
    part = "early" if when.day <= 10 else ("mid" if when.day <= 20 else "late")
    season_txt = f"{part} {when:%B}"
    watch, alert = _names(cards, "watch"), _names(cards, "alert")
    flagged = ", ".join(t.lower() for t in alert + watch)
    if role == "student":
        head = f"{n['normal']} of {with_data} health signs are normal for {season_txt}."
        sub = ("Amber means outside the usual seasonal range or close to a limit; red means clearly unusual. "
               "Each row says how the value is measured.")
    elif role == "stakeholder":
        sector = P.SECTORS.get(profile.get("sector"), "your sector").lower()
        head = (f"{n_sectors} of 5 sectors share this water: {secs.replace(',', ', ')}." if n_sectors
                else "This point is outside the five sectors' pressure zones.")
        k = n["alert"] + n["watch"]
        sub = (f"{k} sign{'s' if k != 1 else ''} to check before planning {sector} work: {flagged}." if k
               else f"Nothing flagged for {sector} work here today.")
    elif role == "researcher":
        head = (f"{len(cards)} cards: {n['normal']} normal, {n['watch']} watch, {n['alert']} alert"
                + (f", {n['no_data']} no data." if n["no_data"] else "."))
        sub = ("Natural-vs-pressure rule chain applied. Coastal buoys EUXRoCB0x and station 15480 excluded (no QC). "
               "Model nitrate and phosphate not used.")
    else:
        if n["alert"]:
            head = f"Something is unusual here today: {', '.join(t.lower() for t in alert)}."
        elif n["watch"]:
            k = n["watch"]
            head = f"Mostly normal today. {'One thing' if k == 1 else f'{k} things'} to keep an eye on."
        else:
            head = "Everything we track looks normal for the season."
        sub = (f"To watch: {flagged}. Not an alarm." if (n["watch"] and not n["alert"])
               else ("Scientists would check these first." if n["alert"] else
                     f"Compared with the usual values for {season_txt}."))
    return head, sub


def counts_html(cards) -> str:
    n = _counts(cards)
    bits = []
    for k in ("normal", "watch", "alert", "no_data"):
        if k == "no_data" and not n[k]:
            continue
        dim = " bsv-dim" if not n[k] else ""
        bits.append(f"<span class='bsv-count{dim}'>{status_square(k)}{n[k]} {STATUS_LABEL[k].lower()}</span>")
    return f"<div class='bsv-counts'>{''.join(bits)}</div>"


# ------------------------------------------------------------------------------------------ card rows
def _origin(c) -> str:
    ev = (c.get("evidence") or "").lower()
    return ORIGIN_LABEL.get("in-situ" if ev == "measured" else ev, ev or "")


def _value(c) -> str:
    v = c.get("value")
    if v is None:
        return "-"
    return PN._num(v, c.get("unit") or "")


def _means(c, lvl) -> str:
    why = c.get("why") or ""
    if lvl == "public":
        return why
    ref = c.get("reference")
    extra = ""
    if isinstance(ref, dict) and ref.get("threshold") and lvl != "public":
        tt = ref.get("threshold_type")
        extra = f" Threshold: {ref['threshold']}" + (f" ({tt})." if tt else ".")
    return why + extra


def _source(c, detail) -> str:
    out, seen = [], set()
    for s in c.get("sources") or []:
        if s.get("dataset") == "zone sampling":
            continue
        name = (s.get("dataset") if detail else (s.get("label") or s.get("dataset"))) or ""
        if not name or name in seen:
            continue
        seen.add(name)
        b = name
        if s.get("date"):
            b += f", {s['date']}"
        if s.get("distance_km") not in (None, ""):
            b += f", {s['distance_km']} km away"
        out.append(b)
    if detail and c.get("confidence"):
        out.append(f"confidence {c['confidence']}")
    return "; ".join(out[: (4 if detail else 2)])


def _toggle(cid):
    ss = st.session_state
    ss.open_card = None if ss.get("open_card") == cid else cid


def _to_chart(cid):
    ss = st.session_state
    ss["w_var"] = CARD_VAR[cid]
    ss["w_wview"] = "Anomaly"
    ss["_goto"] = "water"


def card_rows(cards, profile):
    ss = st.session_state
    lvl = P.level(profile)
    detail = P.show_detail(profile)
    for c in cards:
        cid = c.get("id") or c.get("title")
        is_open = ss.get("open_card") == cid
        txt = c.get("text") if isinstance(c.get("text"), dict) else {}
        line = txt.get(lvl) or c.get("why") or ""
        col = STATUS.get(c.get("status") or "no_data", STATUS["no_data"])[0]
        with st.container(key=f"crow_{cid}"):
            st.markdown(
                f"<div class='bsv-row{' open' if is_open else ''}'>"
                f"<span class='bsv-sq' style='width:8px;height:8px;background:{col}'></span>"
                f"<span class='bsv-rt'>{esc(c.get('title'))}</span>"
                f"<span class='bsv-rv'>{esc(_value(c))}</span>"
                f"<span class='bsv-chev'>{_CHEV_OPEN if is_open else _CHEV}</span>"
                f"<span></span><span class='bsv-rl'>{esc(line)}</span>"
                f"<span class='bsv-ro'>{esc(_origin(c))}</span><span></span></div>", unsafe_allow_html=True)
            st.button(f"{'Close' if is_open else 'Open'} details: {c.get('title')}", key=f"cbtn_{cid}",
                      on_click=_toggle, args=(cid,))
        if is_open:
            with st.container(key=f"cdet_{cid}"):
                st.markdown(
                    "<div class='bsv-det'>"
                    f"<span class='bsv-lbl'>Means</span><span>{esc(_means(c, lvl))}</span>"
                    f"<span class='bsv-lbl'>Source</span><span>{esc(_source(c, detail) or 'not given')}</span></div>",
                    unsafe_allow_html=True)
                if cid in CARD_VAR:
                    st.button("Open the chart in Water quality", key=f"cchart_{cid}", on_click=_to_chart,
                              args=(cid,))


# ------------------------------------------------------------------------------------------ timeline
def timeline_days() -> list:
    today = A.today().date()
    return [today + pd.Timedelta(days=d) for d in range(-6, 6)]


def _toggle_legend():
    ss = st.session_state
    ss.w_legend = not ss.get("w_legend", True)


def timeline():
    """Last 7 days, today, forecast +5: one date for the map, the cards and the season."""
    ss = st.session_state
    days = timeline_days()
    today = A.today().date()
    if ss.get("w_day") not in days:
        ss["w_day"] = today
    labels = []
    for i, d in enumerate(days):
        if d == today:
            labels.append(f"<span class='today'>{d:%d %b} today</span>")
        elif i == 0:
            labels.append(f"<span>{d:%d %b}</span>")
        elif i == len(days) - 1:
            labels.append(f"<span class='fc'>{d.day} forecast</span>")
        else:
            labels.append(f"<span class='{'fc' if d > today else ''}'>{d.day}</span>")
    fc_left = 100 * (days.index(today)) / (len(days) - 1)
    with st.container(key="timeline", horizontal=True, vertical_alignment="center"):
        with st.container(key="tl_track"):
            st.select_slider("Date", options=days, key="w_day", label_visibility="collapsed",
                             format_func=lambda d: f"{d:%d %b %Y}" + (" (today)" if d == today else
                                                                      (" (forecast)" if d > today else "")))
            st.markdown(f"<div class='bsv-tl-labels' style='--fc:{fc_left:.1f}%'>{''.join(labels)}</div>",
                        unsafe_allow_html=True)
        st.button("Hide legend" if ss.get("w_legend", True) else "Legend", key="legend_btn", on_click=_toggle_legend)
