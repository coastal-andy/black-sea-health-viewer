"""Romanian completeness check: runs every page through Streamlit's AppTest in RO and flags likely English.

    .venv/bin/python src/viewer/ro_check.py              # full run (pages x profiles x places x dates), a few minutes
    .venv/bin/python src/viewer/ro_check.py --quick      # one profile and place per page
    .venv/bin/python src/viewer/ro_check.py --lang en    # the same scenarios in English: exceptions only

It walks every rendered element (markdown, captions, labels, options, tables, expanders, tabs, chart traces and
axis titles, map tooltips and legends), strips HTML, and flags any text with words from an English stop-list.
Allowed: dataset IDs, product names, units, station codes and place names (ALLOW below). Also counted: blocks
shown with the "[EN]" marker (marinekit text without a Romanian template) and cedilla diacritics (ş ţ).
Exit code 1 when anything is flagged. Set MARINEKIT_OFFLINE=1 to stay on the local cache.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]

STOP = set("""
the and of is are' from near this that these those above below with without records satellite water sea temperature
oxygen salinity chlorophyll for to on at by or be was were has have it its than more less usual here there today
when where which what why how but if only still also about day days year years week weeks value values source
sources range buoy buoys sample samples measured coast coastal offshore shown used not yes should would could can
will may might each every all any some after before between under over into out up down our your you we they their
been being does do did see show click open close page map layer layers zone zones level warning trust trusted
untrusted indicative reliable error cycle seasonal season summer winter spring autumn mean average beach bathing
shipyard shipyards fishing tourism aquaculture nutrients decade decades trend trends change changes rising falling
higher lower warmer colder clearer murkier normal-range threshold thresholds computing loading downloading still
waves currents wind depth seabed health signs place point station stations analysis quality checked check
uncertainty typical plain words caveats confidence none unknown months month week weekly daily annual algae bloom
blooms clarity nitrate phosphate surface bottom near-bottom dissolved river danube flow carrying
""".split()) - {"are'"}

# words that are also Romanian or proper names: never flagged even if listed above by mistake
NOT_ENGLISH = {"model", "normal", "data", "are", "sector", "sectoare", "port", "trend", "bias", "in", "a", "pe", "per",
               "global", "total", "local", "minim", "maxim", "variabil", "standard", "stop", "start", "risc"}

# text allowed as is (IDs, product and place names): removed before the word check
ALLOW = [
    r"cmems_[\w\-.]+", r"[A-Z]{2,}_[\w\-.]+", r"EUXRo\w+", r"\b15\d{3}\b", r"Copernicus[\w\s]*?(?=[,.;)]|$)",
    r"EMODnet[\w\s]*?(?=[,.;)]|$)", r"Open-Meteo", r"OpenStreetMap", r"GloFAS", r"NOAA", r"ESA Ocean Colour CCI",
    r"Natura 2000", r"OceanSITES", r"marinekit\.[\w.]+", r"docs/[\w/.\-*]+", r"\b[\w-]+\.(?:csv|md|py|json|geojson)\b",
    r"Esri[\w\s,]*", r"Leaflet", r"Tiles &copy;[^<]*", r"&copy;[^<]*", r"Garcia & Gordon \(1992\)", r"Hobday",
    r"Newey-West", r"\(HAC\)", r"Sulina \(Danube mouth\)", r"Sfantu Gheorghe \(Danube\)",
]
_ALLOW = re.compile("|".join(ALLOW))
_WORD = re.compile(r"[A-Za-zăâîșțĂÂÎȘȚ'][A-Za-zăâîșțĂÂÎȘȚ'\-]*")
_SKIP_KEYS = {"id", "formId", "key", "type", "componentName", "url", "pageScriptHash", "icon", "color", "format",
              "theme", "uniqueId", "deltaColor", "id_", "help_", "elementId", "fragmentId", "scriptHash"}


def _strip_html(s: str) -> str:
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<svg.*?</svg>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


def _from_folium(h: str) -> list[str]:
    """Visible text of a folium map: tooltips, popups, legend and layer names (not the Leaflet code)."""
    out = []
    for m in re.finditer(r"bind(?:Tooltip|Popup)\(\s*`(.*?)`", h, re.S):
        out.append(m.group(1))
    for m in re.finditer(r'\.setContent\(\s*`(.*?)`', h, re.S):
        out.append(m.group(1))
    for m in re.finditer(r'"(?:label|sitename)"\s*:\s*"((?:[^"\\]|\\.)*)"', h):
        out.append(json.loads(f'"{m.group(1)}"'))
    for m in re.finditer(r"aliases\s*:\s*(\[[^\]]*\])", h):
        try:
            out.extend(json.loads(m.group(1)))
        except Exception:
            pass
    for m in re.finditer(r"overlays\s*:\s*\{(.*?)\}", h, re.S):
        out.extend(re.findall(r'"([^"]+)"\s*:', m.group(1)))
    body = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    out.append(body)
    return out


def _from_plotly(spec: str) -> list[str]:
    out = []
    try:
        d = json.loads(spec)
    except Exception:
        return out

    def walk(x, k=None):
        if isinstance(x, dict):
            for kk, v in x.items():
                walk(v, kk)
        elif isinstance(x, list):
            for v in x:
                walk(v, k)
        elif isinstance(x, str) and k in ("name", "text", "hovertemplate", "ticktext", "title"):
            out.append(re.sub(r"%\{[^}]*\}", " ", x))
    walk(d.get("data")), walk(d.get("layout"))
    return out


def _strings(x, key=None, out=None):
    out = [] if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            if k in _SKIP_KEYS:
                continue
            _strings(v, k, out)
    elif isinstance(x, list):
        for v in x:
            _strings(v, key, out)
    elif isinstance(x, str):
        if key == "spec":
            out.extend(_from_plotly(x))
        elif key in ("jsonArgs", "argsJson") or (x.lstrip().startswith("{") and "leaflet" in x[:20000].lower()):
            try:
                args = json.loads(x)
                h = args.get("fig") or args.get("html") or json.dumps(args)
            except Exception:
                h = x
            out.extend(_from_folium(h))
        elif x.lstrip().startswith("<style"):
            pass
        else:
            out.append(x)
    return out


def collect(at) -> list[str]:
    from google.protobuf.json_format import MessageToDict
    texts = []

    def walk(node):
        proto = getattr(node, "proto", None)
        if proto is not None:
            try:
                texts.extend(_strings(MessageToDict(proto)))
            except Exception:
                pass
        ch = getattr(node, "children", None)
        if isinstance(ch, dict):
            for c in ch.values():
                walk(c)
    walk(at._tree)
    out = []
    for t in texts:
        t = " ".join(_strip_html(t).split())
        if t:
            out.append(t)
    return out


def english(text: str) -> list[str]:
    """English stop-words found in the text (after removing allowed names and IDs)."""
    t = _ALLOW.sub(" ", text)
    words = [w.lower().strip("'-") for w in _WORD.findall(t)]
    return [w for w in words if w in STOP and w not in NOT_ENGLISH]


# ------------------------------------------------------------------------------------------ scenarios
PLACES = {"constanta": ("Constanța offshore", 44.17, 28.72), "mangalia": ("Mangalia / 2 Mai", 43.79, 28.64),
          "midia": ("Midia port", 44.33, 28.72), "sulina": ("Sulina (Danube mouth)", 45.15, 29.78)}
PROFILES = {"public": dict(role="public"), "student": dict(role="student"),
            "researcher": dict(role="researcher", focus="physical"),
            "stakeholder:tourism": dict(role="stakeholder", sector="tourism"),
            "stakeholder:aquaculture": dict(role="stakeholder", sector="aquaculture"),
            "stakeholder:fishing": dict(role="stakeholder", sector="fishing"),
            "stakeholder:ports": dict(role="stakeholder", sector="ports"),
            "stakeholder:shipyards": dict(role="stakeholder", sector="shipyards")}
WVARS = ["sst", "sal", "o2_bottom", "o2", "chl", "kd490", "nutrients", "ph"]
CARDS = ["temperature", "oxygen", "blooms", "clarity", "nutrients", "bathing", "biodiversity", "drivers",
         "acidification"]


def page_script(page, prof, place, day, extra, lang_code):
    import sys
    sys.path.insert(0, "/Users/andy/Desktop/Projects/Hackaton Constanta_11.2026/src")
    import pandas as pd
    import streamlit as st
    from viewer import onboarding as OB, shell as SH, views as V
    from viewer.style import css
    ss = st.session_state
    ss.lang = lang_code
    ss.theme = extra.get("theme", "dark")
    if "profile" not in ss:
        OB.finish(dict(role=prof["role"], sector=prof.get("sector"), focus=prof.get("focus"), goal="now"))
        nm, la, lo = place
        ss.sel = dict(name=nm, lat=la, lon=lo, kind="point", wkt=None)
        ss["w_day"] = pd.Timestamp(day).date()
        for k, v in extra.items():
            ss[k] = v
    pages = {k: st.Page(getattr(V, k), title=k, url_path=k, default=(k == "overview"))
             for k in ["overview", "water", "seabed", "pressures", "methods"]}
    SH.PAGE_OBJS.update(pages)
    st.navigation(list(pages.values()), position="hidden")
    st.markdown(css(ss.theme, page), unsafe_allow_html=True)
    SH.rail(pages)
    getattr(V, page)()


def scenarios(quick: bool):
    import pandas as pd
    today = str(pd.Timestamp.now().date())
    summer = "2026-07-15"
    profs = ["public"] if quick else list(PROFILES)
    places = ["constanta"] if quick else list(PLACES)
    out = []
    for pr in profs:
        for pl in places:
            out.append(("overview", pr, pl, today, {}))
            out.append(("overview", pr, pl, today, {"w_overlap": True, "w_zones": True, "w_features": True,
                                                   "w_platforms": True, "w_grid": "sst"}))
    for pr in (["public"] if quick else ["public", "researcher", "stakeholder:tourism", "student"]):
        for cid in CARDS:
            out.append(("overview", pr, "constanta" if pr != "stakeholder:tourism" else "mangalia", today,
                        {"open_card": cid}))
    for pr in profs:
        for pl in (places if pr in ("public", "researcher") else places[:1]):
            for v in WVARS:
                views = ["now", "trend", "obsmod"] if v not in ("nutrients", "ph") else ["now"]
                for vw in views:
                    out.append(("water", pr, pl, today, {"w_var": v, "w_wview": vw}))
    for pr in profs:
        out.append(("seabed", pr, "constanta", today, {}))
        for f in ("waves", "currents", "wind", "depth"):
            if pr in ("public", "researcher"):
                out.append(("seabed", pr, "constanta", today, {"w_field": f, "open_sea": f}))
    for pr in profs:
        for sec in ("ports", "shipyards", "tourism", "fishing", "aquaculture"):
            for season, day in (("winter", today), ("summer", summer)):
                if pr not in ("public", "stakeholder:tourism") and season == "summer" and sec != "tourism":
                    continue
                out.append(("pressures", pr, "constanta", day, {"w_sector": sec, "w_pseason": season,
                                                                 "open_site": 0, "w_press_open": True}))
    for pr in profs:
        out.append(("methods", pr, "constanta", today, {}))
    out.append(("overview", "public", "constanta", summer, {"w_season": "summer", "w_zones": True,
                                                            "w_features": True}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--lang", default="ro")
    ap.add_argument("--only", default="", help="comma list of pages")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sys.path.insert(0, str(SRC))
    from streamlit.testing.v1 import AppTest
    from viewer import i18n_data
    flagged = defaultdict(set)
    excs, n = [], 0
    sc = scenarios(a.quick)
    if a.only:
        sc = [s for s in sc if s[0] in a.only.split(",")]
    t_start = time.time()
    from viewer import adapters as A  # warm the background seasonal fits, so the pages show results, not "computing"
    for _, la, lo in PLACES.values():
        for v in A.SEASONAL_VARS:
            try:
                A.seasonal(v, la, lo, wait=600)
            except Exception as ex:  # noqa: BLE001
                print("seasonal warm-up", v, la, lo, ex)
    print(f"seasonal warm-up {time.time() - t_start:.0f} s", flush=True)
    for page, pr, pl, day, extra in sc:
        t0 = time.time()
        at = AppTest.from_function(page_script, args=(page, PROFILES[pr], PLACES[pl], day, extra, a.lang),
                                   default_timeout=300)
        try:
            at.run()
        except Exception as ex:  # noqa: BLE001
            excs.append(f"{page} {pr} {pl} {day} {extra}: run failed {ex}")
            continue
        n += 1
        for e in at.exception:
            excs.append(f"{page} {pr} {pl} {day} {extra}: {str(e.message)[:200]} | {''.join(e.stack_trace[-2:])[:300]}")
        if a.lang == "ro":
            for txt in collect(at):
                bad = english(txt)
                marked = "[EN]" in txt
                ced = bool(re.search("[şţŞŢ]", txt))
                if bad or marked or ced:
                    flagged[txt[:400]].add(f"{page}/{pr}/{pl}/{day[5:]}")
        print(f"{page:9} {pr:24} {pl:9} {day} {json.dumps(extra)[:60]:60} {time.time() - t0:5.1f}s "
              f"exc={len(at.exception)}", flush=True)
    print(f"\n{n} runs in {time.time() - t_start:.0f} s; exceptions: {len(excs)}")
    for e in excs[:30]:
        print("  EXC", e)
    if a.lang == "ro":
        print(f"English or marked strings: {len(flagged)}")
        for txt, where in sorted(flagged.items(), key=lambda kv: -len(kv[1])):
            print(f"  [{len(where):3}] {sorted(where)[0]:40} | {sorted(set(english(txt)))[:6]} | {txt[:300]}")
        print(f"[EN] marker blocks (no RO template): {len(i18n_data.MISSES)}")
    if a.out:
        Path(a.out).write_text(json.dumps(dict(flagged={k: sorted(v) for k, v in flagged.items()},
                                               misses=sorted(i18n_data.MISSES), exceptions=excs),
                                          ensure_ascii=False, indent=1))
    sys.exit(1 if (flagged or excs) else 0)


if __name__ == "__main__":
    main()
