"""Colours, CSS and small HTML helpers for the viewer. Okabe-Ito palette, no emoji."""

from __future__ import annotations

import html

# ------------------------------------------------------------------------------------------ themes (direction B)
# Two flat token sets. Dark is the default; light is the same design on light colours.
THEMES = {
    "dark": dict(
        bg="#06131D", panel="#0C1F2C", rail="#0A1B27", raised="#13293A", row_open="#102838",
        line="#1E3646", line2="#16303F", ctrl="#2A4558", overlay="rgba(10,27,39,0.90)",
        text="#E6EEF3", soft="#C9D7E0", sub="#A9BDCA", muted="#8FA7B6",
        accent="#4CC3E6", accent_hi="#8ADBF2", on_accent="#06131D",
        normal="#2BB38A", watch="#F2B134", alert="#F07B3F", no_data="#6E8392",
        basemap="Dark", grid="rgba(255,255,255,0.07)",
        arrow_core="#ffffff", arrow_edge="rgba(6,19,29,0.9)", arrow_bg="#2E5A73",
    ),
    "light": dict(
        bg="#F4F7F9", panel="#FFFFFF", rail="#EAF0F4", raised="#DCE7EE", row_open="#EEF4F8",
        line="#D3DDE4", line2="#E2E9EE", ctrl="#C3D0D9", overlay="rgba(255,255,255,0.94)",
        text="#0E2230", soft="#24394A", sub="#3E5666", muted="#5A7180",
        accent="#0A7FAE", accent_hi="#06648A", on_accent="#FFFFFF",
        normal="#1B7F5E", watch="#9A6700", alert="#C2410C", no_data="#6B7F8C",
        basemap="Light", grid="rgba(14,34,48,0.08)",
        arrow_core="#0E2230", arrow_edge="rgba(255,255,255,0.95)", arrow_bg="#C9D8E2",
    ),
}
STATUS_LABEL = {"normal": "Normal", "watch": "Watch", "alert": "Alert", "no_data": "No data"}
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&"
             "family=Barlow+Condensed:wght@400;500;600&display=swap")
FONT_UI = "'Barlow', system-ui, -apple-system, 'Segoe UI', sans-serif"
FONT_NUM = "'Barlow Condensed', 'Barlow', system-ui, sans-serif"


def theme_name() -> str:
    """'dark' (default) or 'light', from st.session_state['theme']."""
    try:
        import streamlit as st
        if not st.runtime.exists():
            return "dark"
        t = st.session_state.get("theme", "dark")
    except Exception:
        t = "dark"
    return t if t in THEMES else "dark"


def tokens(name: str | None = None) -> dict:
    return THEMES[name or theme_name()]


class _ThemedStatus(dict):
    """STATUS[k] -> (colour for the current theme, label). Same shape as the old constant."""

    def __getitem__(self, k):
        return tokens()[k], STATUS_LABEL[k]

    def get(self, k, default=None):
        return self[k] if k in STATUS_LABEL else default


STATUS = _ThemedStatus({k: None for k in STATUS_LABEL})


def status_square(status: str, size: int = 8) -> str:
    col = STATUS.get(status or "no_data", STATUS["no_data"])[0]
    return f"<span class='bsv-sq' style='width:{size}px;height:{size}px;background:{col}'></span>"


def _svg_url(svg: str) -> str:
    from urllib.parse import quote
    return "url(\"data:image/svg+xml;utf8," + quote(svg, safe=" =:/;,'()") + "\")"


# rail icons (22 px, stroke only), from the direction B mockup; {c} = stroke colour
RAIL_ICONS = {
    "overview": "<path d='M2 5 L8 3 L14 5 L20 3 V17 L14 19 L8 17 L2 19 Z M8 3 V17 M14 5 V19'/>",
    "water": "<path d='M11 2 C11 2 4 10 4 14 A7 7 0 0 0 18 14 C18 10 11 2 11 2 Z'/>",
    "seabed": "<path d='M2 8 C5 5 8 11 11 8 S17 5 20 8 M2 13 C5 10 8 16 11 13 S17 10 20 13 M2 19 L8 16 L14 18 L20 15'/>",
    "pressures": "<rect x='3' y='3' width='10' height='10'/><rect x='9' y='9' width='10' height='10'/>",
    "methods": "<path d='M4 4 H18 M4 9 H18 M4 14 H13 M4 19 H10'/>",
}
LOGO_SVG = ("<svg width='30' height='30' viewBox='0 0 28 28' role='img' aria-label='Black Sea Health'>"
            "<circle cx='14' cy='14' r='12.5' fill='none' stroke='{c}' stroke-width='1.5'/>"
            "<path d='M4 16 C8 12 11 20 15 16 S22 12 24 15' fill='none' stroke='{c}' stroke-width='2'/></svg>")


def rail_icon(key: str, colour: str) -> str:
    return _svg_url(f"<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 22 22' fill='none' "
                    f"stroke='{colour}' stroke-width='1.6'>{RAIL_ICONS[key]}</svg>")


def plotly_layout(fig, height=None):
    """Apply the current theme to a plotly figure (transparent paper, hairline grid, Barlow)."""
    t = tokens()
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=FONT_UI, size=12, color=t["text"]),
                      hoverlabel=dict(bgcolor=t["panel"], bordercolor=t["ctrl"], font=dict(color=t["text"])),
                      legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"])),
                      title_font_color=t["text"])
    fig.update_xaxes(gridcolor=t["line2"], linecolor=t["line"], zerolinecolor=t["line"], tickcolor=t["line"],
                     tickfont=dict(color=t["muted"]), title_font=dict(color=t["muted"]))
    fig.update_yaxes(gridcolor=t["line2"], linecolor=t["line"], zerolinecolor=t["line"], tickcolor=t["line"],
                     tickfont=dict(color=t["muted"]), title_font=dict(color=t["muted"]))
    if height:
        fig.update_layout(height=height)
    return fig


def css(name: str | None = None, active: str = "overview") -> str:
    """All page CSS for one theme. `active` is the rail key of the current page."""
    t = tokens(name)
    icons = "\n".join(
        f".st-key-rail_{k} a::before {{background-image: {rail_icon(k, t['accent'] if k == active else t['muted'])};}}"
        for k in RAIL_ICONS)
    out = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{FONTS_URL}" rel="stylesheet">
<style>
:root {{--bsv-bg:{t['bg']}; --bsv-panel:{t['panel']}; --bsv-rail:{t['rail']}; --bsv-line:{t['line']};
  --bsv-line2:{t['line2']}; --bsv-text:{t['text']}; --bsv-muted:{t['muted']}; --bsv-accent:{t['accent']};}}
html, body, .stApp, [data-testid="stAppViewContainer"] {{background:{t['bg']} !important; color:{t['text']};}}
.stApp, .stApp p, .stApp li, .stApp label, input, textarea, button, .stApp select,
[data-testid="stMarkdownContainer"], [data-baseweb] {{font-family:{FONT_UI};}}
.stApp {{font-variant-numeric: tabular-nums;}}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{font-family:{FONT_NUM}; font-weight:500; color:{t['text']}; letter-spacing:0.2px;}}
.stApp a {{color:{t['accent']};}} .stApp a:hover {{color:{t['accent_hi']};}}
.stApp p, .stApp li, .stApp label, [data-testid="stMarkdownContainer"] {{color:{t['text']};}}
[data-testid="stCaptionContainer"], .stApp small {{color:{t['muted']} !important;}}
hr {{border-color:{t['line']} !important;}}

/* chrome: no header bar, no page padding: the map fills the page */
header[data-testid="stHeader"] {{display:none !important;}}
[data-testid="stDecoration"] {{display:none !important;}}
[data-testid="stMain"] {{background:{t['bg']};}}
.block-container, [data-testid="stMainBlockContainer"] {{padding:0 !important; max-width:none !important;}}
[data-testid="stElementContainer"]:has(> div > div > style), [data-testid="stElementContainer"]:has(style) {{display:none !important;}}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]:has(> [data-testid="stHorizontalBlock"] [class*="st-key-bsv_map"]) {{gap:0;}}

/* left icon rail (72 px) */
section[data-testid="stSidebar"] {{width:72px !important; min-width:72px !important; max-width:72px !important;
  background:{t['rail']} !important; border-right:1px solid {t['line']}; transform:none !important;}}
section[data-testid="stSidebar"] > div {{width:72px !important; background:{t['rail']} !important;}}
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {{display:none !important;}}
section[data-testid="stSidebar"] div[style*="cursor: col-resize"], section[data-testid="stSidebar"] + div[style*="col-resize"] {{display:none !important;}}
[data-testid="stSidebarContent"] {{padding:0 !important; overflow:hidden !important;}}
[data-testid="stSidebarUserContent"] {{padding:10px 0 0 0 !important; width:72px;}}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{gap:2px;}}
.st-key-logo_block {{height:64px; min-height:64px; flex:0 0 64px; margin:0 0 10px 0; overflow:hidden;
  display:flex; align-items:center; justify-content:center;}}
.st-key-logo_block [data-testid="stElementContainer"], .st-key-logo_block [data-testid="stMarkdown"] {{margin:0 !important; height:52px;}}
.st-key-logo_block [data-testid="stMarkdownContainer"] {{margin:0 !important;}}
.bsv-logo {{height:52px; width:72px; display:flex; align-items:center; justify-content:center;}}
[class*="st-key-rail_"] {{height:64px; min-height:64px; flex:0 0 64px; overflow:hidden;}}
[class*="st-key-rail_"] [data-testid="stElementContainer"], [class*="st-key-rail_"] [data-testid="stPageLink"] {{margin:0 !important; height:64px;}}
[class*="st-key-rail_"] a[data-testid="stPageLink-NavLink"] {{height:64px; width:72px; margin:0; padding:0; border-radius:0;
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; text-decoration:none;
  background:transparent;}}
[class*="st-key-rail_"] a[data-testid="stPageLink-NavLink"] p, [class*="st-key-rail_"] a[data-testid="stPageLink-NavLink"] span {{
  font-size:10.5px !important; letter-spacing:0.4px; color:{t['muted']} !important; margin:0; line-height:1.1;
  overflow:visible !important; max-width:none !important; white-space:nowrap; text-overflow:clip;}}
[class*="st-key-rail_"] a[data-testid="stPageLink-NavLink"]::before {{content:""; display:block; width:22px; height:22px;
  background-repeat:no-repeat; background-size:22px 22px;}}
[class*="st-key-rail_"] a[data-testid="stPageLink-NavLink"]:hover {{background:{t['raised']};}}
.st-key-rail_{active} a[data-testid="stPageLink-NavLink"] {{background:{t['raised']};}}
.st-key-rail_{active} a[data-testid="stPageLink-NavLink"] p, .st-key-rail_{active} a[data-testid="stPageLink-NavLink"] span {{color:{t['text']} !important;}}
{icons}
.st-key-theme_switch {{position:fixed; left:0; bottom:12px; width:72px; z-index:1000; display:flex; align-items:center;}}
.st-key-theme_switch button {{width:56px; min-height:28px; height:28px; margin:0 8px; padding:0; border-radius:4px;
  border:1px solid {t['ctrl']} !important; background:transparent !important;}}
.st-key-theme_switch button p {{font-size:10.5px !important; letter-spacing:1px; text-transform:uppercase; color:{t['sub']} !important;}}
.st-key-theme_switch .bsv-lbl {{display:block; text-align:center; width:72px; margin-bottom:4px;}}

/* docked panel on the right */
[data-testid="stHorizontalBlock"]:has(> div > .st-key-bsv_panel), [data-testid="stHorizontalBlock"]:has([class*="st-key-bsv_map"]) {{flex-wrap:nowrap !important;}}
div[data-testid="stColumn"]:has([class*="st-key-bsv_map"]) {{min-width:0 !important;}}
div[data-testid="stColumn"]:has(.st-key-bsv_panel) {{min-width:280px; background:{t['panel']}; border-left:1px solid {t['line']};
  height:100vh; overflow-y:auto; position:sticky; top:0;}}
.st-key-bsv_panel {{padding:0 0 24px 0;}}
.st-key-bsv_panel > div {{gap:0;}}
.bsv-sec {{padding:16px 22px; border-bottom:1px solid {t['line']};}}
.st-key-bsv_panel [data-testid="stElementContainer"], .st-key-bsv_panel [data-testid="stExpander"] {{padding-left:0; padding-right:0;}}
.st-key-bsv_panel .stPlotlyChart, .st-key-bsv_panel [data-testid="stHorizontalBlock"],
.st-key-bsv_panel [data-testid="stWidgetLabel"] + div, .st-key-bsv_pad {{padding-left:22px; padding-right:22px;}}
.st-key-bsv_pad {{padding-top:10px; padding-bottom:10px;}}

/* map column: map fills the height, tools float over it */
div[data-testid="stColumn"]:has([class*="st-key-bsv_map"]) {{position:relative;}}
[class*="st-key-bsv_map"] iframe {{height:calc(100vh - 64px) !important; display:block;}}
.st-key-bsv_map_po iframe {{height:calc(100vh - 222px) !important;}}
.st-key-bsv_map_pc iframe {{height:calc(100vh - 57px) !important;}}
[class*="st-key-bsv_map"] {{gap:0 !important;}}
[class*="st-key-bsv_map"] [data-testid="stElementContainer"] {{margin:0;}}
.st-key-map_tools {{position:absolute; left:16px; top:16px; z-index:20; width:min(380px, calc(100% - 96px)); gap:8px;
  background:{t['overlay']}; border:1px solid {t['ctrl']}; border-radius:4px; padding:10px;}}
.st-key-map_msgs {{position:absolute; left:16px; bottom:16px; z-index:20; max-width:60%;}}
.st-key-map_msgs p {{background:{t['overlay']}; padding:4px 8px; border:1px solid {t['ctrl']}; border-radius:4px; font-size:12px; color:{t['sub']} !important;}}
.st-key-page_body {{padding:24px 28px 40px 28px;}}
/* Overview panel (B1) */
.st-key-ptabs {{border-bottom:1px solid {t['line']}; padding:0 8px;}}
.st-key-ptabs {{container-type:inline-size;}}
@container (max-width: 270px) {{
  .st-key-ptabs [data-testid="stButtonGroup"] > div {{flex-wrap:wrap !important;}}
  .st-key-ptabs [data-testid="stButtonGroup"] button {{flex:1 1 50% !important; height:38px !important;}}
}}
.st-key-ptabs [data-testid="stButtonGroup"] {{width:100%;}}
.st-key-ptabs [data-testid="stButtonGroup"] > div {{width:100%; gap:0; flex-wrap:nowrap;}}
.st-key-ptabs [data-testid="stButtonGroup"] button {{flex:1 1 0; min-width:0; padding:0 4px !important; height:48px; border:0 !important; border-radius:0 !important;
  background:transparent !important; color:{t['muted']} !important;}}
.st-key-ptabs [data-testid="stButtonGroup"] button p {{font-size:clamp(10px, 0.85vw, 12px) !important;
  letter-spacing:clamp(0px, 0.07vw, 1px); text-transform:uppercase;
  overflow:visible !important; text-overflow:clip !important; white-space:nowrap;}}
.st-key-ptabs [data-testid="stButtonGroup"] button div {{overflow:visible !important; max-width:none !important;}}
.st-key-ptabs [data-testid="stButtonGroup"] button[kind*="Active"] {{color:{t['text']} !important; background:transparent !important;
  box-shadow:inset 0 -2px 0 {t['accent']} !important;}}
.st-key-ptabs [data-testid="stButtonGroup"] button[kind*="Active"] p {{font-weight:600;}}
.bsv-sec .bsv-place {{margin-top:8px;}}
.bsv-verdict {{margin:10px 0 0 0 !important; font-size:16px; line-height:1.4; color:{t['text']} !important;}}
.bsv-vsub {{margin:4px 0 0 0 !important; font-size:13.5px; line-height:1.45; color:{t['sub']} !important;}}
.bsv-counts {{display:flex; flex-wrap:nowrap; gap:18px; margin-top:12px; font-family:{FONT_NUM}; font-size:15px;
  letter-spacing:0.6px; text-transform:uppercase; color:{t['text']}; white-space:nowrap;}}
.bsv-count {{display:inline-flex; align-items:center;}}
.bsv-count.bsv-dim {{color:{t['muted']};}}
[class*="st-key-crow_"] {{position:relative; gap:0 !important;}}
.bsv-row {{display:grid; grid-template-columns:8px minmax(0,1fr) auto 12px; column-gap:12px; row-gap:2px; align-items:baseline;
  padding:12px 18px 12px 22px; border-bottom:1px solid {t['line2']};}}
.bsv-row.open {{background:{t['row_open']}; border-bottom-color:transparent;}}
[class*="st-key-crow_"]:hover .bsv-row {{background:{t['row_open']};}}
.bsv-row .bsv-sq {{margin:0; align-self:center;}}
.bsv-rt {{font-size:14.5px; font-weight:500; color:{t['text']};}}
.bsv-rv {{font-family:{FONT_NUM}; font-size:22px; font-weight:500; white-space:nowrap; color:{t['text']};}}
.bsv-chev {{display:flex; align-items:center; align-self:center; color:{t['muted']};}}
.bsv-rl {{font-size:12.5px; line-height:1.35; color:{t['sub']}; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;}}
.bsv-ro {{font-size:10.5px; letter-spacing:1px; text-transform:uppercase; color:{t['muted']}; text-align:right; white-space:nowrap;}}
[class*="st-key-cbtn_"] {{position:absolute !important; inset:0; width:100% !important; max-width:none !important;
  height:100% !important; z-index:3; margin:0 !important;}}
[class*="st-key-cbtn_"] *, [class*="st-key-cbtn_"] button {{width:100% !important; max-width:none !important; height:100% !important;}}
[class*="st-key-cbtn_"] button {{opacity:0; cursor:pointer; border:0 !important;}}
[class*="st-key-cbtn_"] button:focus-visible {{opacity:1; background:transparent !important; outline:2px solid {t['accent']};}}
[class*="st-key-cbtn_"] button:focus-visible p {{display:none;}}
[class*="st-key-cdet_"] {{background:{t['row_open']}; padding:0 22px 14px 42px; border-bottom:1px solid {t['line2']}; gap:6px !important;}}
.bsv-det {{display:grid; grid-template-columns:64px minmax(0,1fr); gap:4px 10px; font-size:12.5px; line-height:1.45; color:{t['soft']};}}
.bsv-det .bsv-lbl {{font-size:10.5px; letter-spacing:1px; padding-top:2px;}}
[class*="st-key-cchart_"] button {{border:0 !important; padding:0 !important; min-height:0 !important; height:auto;
  background:transparent !important;}}
[class*="st-key-cchart_"] button p {{font-size:12.5px !important; color:{t['accent']} !important;}}
[class*="st-key-cchart_"] button:hover p {{color:{t['accent_hi']} !important; text-decoration:underline;}}
.st-key-panel_foot {{padding:16px 22px 22px 22px; justify-content:space-between; flex-wrap:wrap; gap:8px;}}
.st-key-panel_foot a[data-testid="stPageLink-NavLink"] {{padding:0; background:transparent;}}
.st-key-panel_foot a[data-testid="stPageLink-NavLink"] p {{font-size:14px !important; font-weight:600; color:{t['accent']} !important;}}
.st-key-panel_foot .bsv-note {{font-size:11.5px;}}
/* Water quality (B2) */
[data-testid="stHorizontalBlock"]:has(.st-key-bsv_aside) {{flex-wrap:nowrap !important;}}
div[data-testid="stColumn"]:has(.st-key-bsv_aside) {{min-width:230px; max-width:300px; background:{t['panel']};
  border-right:1px solid {t['line']}; height:100vh; overflow-y:auto; position:sticky; top:0;}}
.st-key-bsv_aside {{gap:0 !important; padding-bottom:24px;}}
[class*="st-key-vrow_"] {{position:relative; gap:0 !important;}}
.bsv-vrow {{display:flex; align-items:center; gap:12px; height:48px; padding:0 20px; font-size:14.5px; color:{t['soft']};}}
.bsv-vrow .bsv-sq {{margin:0;}}
.bsv-vrow .nm {{flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}}
.bsv-vrow .vl {{font-family:{FONT_NUM}; font-size:16px; color:{t['sub']}; white-space:nowrap;}}
.bsv-vrow.active {{background:{t['raised']}; color:{t['text']}; box-shadow:inset 2px 0 0 {t['accent']};}}
.bsv-vrow.active .vl {{color:{t['text']};}}
[class*="st-key-vrow_"]:hover .bsv-vrow {{background:{t['raised']};}}
[class*="st-key-vbtn_"] {{position:absolute !important; inset:0; width:100% !important; max-width:none !important;
  height:100% !important; z-index:3; margin:0 !important;}}
[class*="st-key-vbtn_"] *, [class*="st-key-vbtn_"] button {{width:100% !important; max-width:none !important; height:100% !important;}}
[class*="st-key-vbtn_"] button {{opacity:0; cursor:pointer; border:0 !important;}}
[class*="st-key-vbtn_"] button:focus-visible {{opacity:1; background:transparent !important; outline:2px solid {t['accent']};}}
[class*="st-key-vbtn_"] button:focus-visible p {{display:none;}}
.st-key-aside_foot {{padding:18px 20px 0 20px; gap:12px !important;}}
.st-key-aside_foot a[data-testid="stPageLink-NavLink"] {{padding:0; background:transparent;}}
.st-key-aside_foot a[data-testid="stPageLink-NavLink"] p {{font-size:14px !important; font-weight:600; color:{t['accent']} !important;}}
.st-key-page_body:has(.bsv-whead) {{padding:24px 36px 48px 36px; max-width:1100px;}}
.bsv-whead {{display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:6px;}}
.bsv-whead .bsv-place {{font-size:36px; margin:0;}}
.st-key-wtabs {{border-bottom:1px solid {t['line']}; margin-bottom:18px;}}
.st-key-wtabs [data-testid="stButtonGroup"] > div {{gap:0;}}
.st-key-wtabs [data-testid="stButtonGroup"] button {{height:48px; padding:0 16px !important; border:0 !important; border-radius:0 !important;
  background:transparent !important; color:{t['muted']} !important;}}
.st-key-wtabs [data-testid="stButtonGroup"] button p {{font-size:12px !important; letter-spacing:1.2px; text-transform:uppercase;}}
.st-key-wtabs [data-testid="stButtonGroup"] button[kind*="Active"] {{color:{t['text']} !important; background:transparent !important;
  box-shadow:inset 0 -2px 0 {t['accent']} !important;}}
.st-key-wtabs [data-testid="stButtonGroup"] button[kind*="Active"] p {{font-weight:600;}}
.bsv-stats {{display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); border-top:1px solid {t['line']};
  border-bottom:1px solid {t['line']}; margin:0 0 20px 0;}}
.bsv-stat {{display:flex; flex-direction:column; gap:4px; padding:14px 18px 14px 0;}}
.bsv-stat + .bsv-stat {{border-left:1px solid {t['line']}; padding-left:18px;}}
.bsv-stat .v {{font-family:{FONT_NUM}; font-size:34px; font-weight:500; line-height:1.05; color:{t['text']}; white-space:nowrap;}}
.bsv-stat .u {{font-size:15px; color:{t['muted']}; margin-left:4px;}}
.bsv-stat .tag {{display:inline-flex; align-items:center; font-family:{FONT_UI}; font-size:11px; letter-spacing:1px;
  text-transform:uppercase; color:{t['soft']}; margin-left:10px; vertical-align:middle;}}
.bsv-fighead {{display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:4px;}}
.bsv-key {{display:flex; gap:16px; font-size:12px; color:{t['sub']};}}
.bsv-key > span {{display:inline-flex; align-items:center; gap:6px;}}
.bsv-key i {{display:inline-block; width:18px;}}
.bsv-table {{width:100%; border-collapse:collapse; font-size:13px; color:{t['soft']};}}
.bsv-table th {{text-align:left; font-weight:500; font-size:10.5px; letter-spacing:1px; text-transform:uppercase;
  color:{t['muted']}; padding:6px 10px 6px 0; border-bottom:1px solid {t['line']};}}
.bsv-table td {{padding:8px 10px 8px 0; border-bottom:1px solid {t['line2']}; vertical-align:top;}}
.bsv-tablebox {{margin:4px 0 14px 0;}}
.bsv-tablebox thead th {{position:sticky; top:0; background:{t['bg']};}}
.bsv-table td.n {{font-family:{FONT_NUM}; font-size:15px; white-space:nowrap;}}
.bsv-chain {{margin:4px 0 0 18px; padding:0; font-size:13.5px; line-height:1.5; color:{t['soft']};}}
.bsv-chain li {{margin:4px 0;}}
.st-key-page_body [data-testid="stExpander"] summary {{padding:12px 0 !important;}}
.st-key-page_body [data-testid="stExpanderDetails"] {{padding:4px 0 14px 0 !important;}}
.st-key-page_body [data-testid="stExpander"] details {{border-top:0 !important;}}
.st-key-page_body [data-testid="stExpander"]:first-of-type details {{border-top:1px solid {t['line']} !important;}}
/* Coast and seabed (B3) */
.bsv-row.bsv-row4 {{grid-template-columns:minmax(0,1fr) auto 12px;}}
.st-key-map_tools [data-testid="stButtonGroup"] > div {{gap:0; flex-wrap:nowrap;}}
.st-key-map_tools [data-testid="stButtonGroup"] button {{flex:1 1 0; height:38px; padding:0 8px !important;}}
.st-key-map_tools [data-testid="stButtonGroup"] button[kind*="Active"] {{box-shadow:inset 0 -2px 0 {t['accent']} !important;}}
.st-key-depthpanel {{background:{t['bg']}; border-top:1px solid {t['line']}; padding:0 16px 6px 16px; gap:0 !important;}}
.st-key-dp_head {{height:56px; gap:16px !important; flex-wrap:nowrap !important;}}
.st-key-dp_head [data-testid="stMarkdownContainer"] {{display:flex; gap:16px; align-items:baseline;}}
.bsv-dp-t {{font-size:14px; font-weight:500; color:{t['text']}; white-space:nowrap;}}
.st-key-profile_btn button {{height:32px; min-height:32px; padding:0 12px;}}
.st-key-profile_btn button p {{font-size:12px !important; letter-spacing:1px; text-transform:uppercase; color:{t['soft']} !important;}}
/* Pressures (B4) */
.st-key-bsv_map_full iframe {{height:100vh !important;}}
.st-key-map_tools_wide {{position:absolute; left:16px; top:16px; z-index:20; width:auto; max-width:calc(100% - 96px);
  gap:8px !important; flex-wrap:wrap;}}
.st-key-map_tools_wide [data-testid="stButtonGroup"] {{background:{t['overlay']}; border:1px solid {t['ctrl']}; border-radius:4px;}}
.st-key-map_tools_wide [data-testid="stButtonGroup"] > div {{gap:0; flex-wrap:nowrap;}}
.st-key-map_tools_wide [data-testid="stButtonGroup"] button {{height:40px; padding:0 14px !important; border:0 !important;
  border-right:1px solid {t['ctrl']} !important;}}
.st-key-map_tools_wide [data-testid="stButtonGroup"] button:last-child {{border-right:0 !important;}}
.st-key-map_tools_wide [data-testid="stButtonGroup"] button[kind*="Active"] {{box-shadow:inset 0 -2px 0 {t['accent']} !important;}}
.bsv-stats.bsv-stats3 {{grid-template-columns:repeat(3, minmax(0,1fr)); margin:0; border-top:0;}}
.bsv-stats3 .bsv-stat:first-child {{padding-left:22px;}}
.bsv-stats3 .bsv-stat .v {{font-size:28px;}}
.bsv-sites-head {{display:flex; justify-content:space-between; align-items:flex-end; padding:18px 18px 8px 22px;}}
.bsv-sites-head .cols, .bsv-site .cols {{display:grid; grid-template-columns:repeat(4, 52px); text-align:center;}}
.bsv-sites-head .cols span {{font-size:9.5px; letter-spacing:0.3px; text-transform:uppercase; color:{t['muted']};}}
.bsv-site {{display:grid; grid-template-columns:12px minmax(0,1fr) auto; column-gap:10px; align-items:center;
  padding:12px 18px 12px 22px; border-bottom:1px solid {t['line2']};}}
.bsv-site.open {{background:{t['row_open']}; border-bottom-color:transparent;}}
[class*="st-key-crow_site"]:hover .bsv-site {{background:{t['row_open']};}}
.bsv-site .nm {{display:flex; flex-direction:column; min-width:0;}}
.bsv-site .t {{font-size:14.5px; font-weight:500; color:{t['text']};}}
.bsv-site .n {{font-size:12px; color:{t['sub']};}}
.bsv-site .cell {{display:flex; justify-content:center;}}
.bsv-site .cell .bsv-sq {{margin:0;}}
.bsv-det1 {{display:flex; flex-direction:column; gap:6px; font-size:12.5px; line-height:1.45; color:{t['soft']};}}
.bsv-det1 .bsv-lbl {{font-size:10.5px; margin-right:4px;}}
/* bottom timeline */
.st-key-timeline {{height:64px; background:{t['bg']}; border-top:1px solid {t['line']}; padding:0 16px; gap:16px !important;
  flex-wrap:nowrap !important;}}
.st-key-tl_track {{flex:1 1 auto; min-width:0; gap:0 !important; position:relative;}}
.st-key-tl_track [data-testid="stSlider"] {{padding:0 6px; margin-top:-6px;}}
.st-key-tl_track [data-testid="stSliderTickBar"] {{display:none;}}
.bsv-tl-labels {{display:flex; justify-content:space-between; font-family:{FONT_NUM}; font-size:12.5px; color:{t['muted']};
  margin-top:-10px; position:relative;}}
.bsv-tl-labels::before {{content:""; position:absolute; left:var(--fc); right:0; top:-14px; height:8px;
  background:repeating-linear-gradient(-45deg, {t['ctrl']} 0 1px, transparent 1px 5px); pointer-events:none;}}
.bsv-tl-labels .today {{color:{t['text']}; font-weight:600;}}
.bsv-tl-labels .fc {{color:{t['muted']};}}
.st-key-tl_track {{container-type:inline-size;}}
@container (max-width: 520px) {{ .bsv-tl-labels .mid {{visibility:hidden;}} }}
.st-key-legend_btn button {{height:40px; padding:0 12px;}}
.st-key-legend_btn button p {{font-size:12px !important; letter-spacing:1px; text-transform:uppercase; color:{t['soft']} !important;}}

/* native widgets: flat, 4 px corners, theme colours (light theme overrides the dark config theme) */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] > div,
input, textarea, [data-baseweb="textarea"] {{background:{t['panel']} !important; color:{t['text']} !important;
  border-color:{t['ctrl']} !important; border-radius:4px !important;}}
[data-baseweb="select"] svg {{fill:{t['muted']};}}
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
[data-testid="stDateInput"] [role="group"], [data-testid="stNumberInput"] [role="group"] {{background:{t['panel']} !important;
  border-color:{t['ctrl']} !important; border-radius:4px !important;}}
[role="combobox"], [role="combobox"]::placeholder {{color:{t['text']} !important; background:transparent !important;}}
[role="combobox"]::placeholder {{color:{t['muted']} !important;}}
[role="listbox"], .react-aria-Popover, [data-rac][role="dialog"] {{background:{t['panel']} !important; color:{t['text']} !important;
  border:1px solid {t['ctrl']} !important; border-radius:4px !important;}}
[role="option"] {{color:{t['text']} !important; background:transparent;}}
[role="option"][data-focused], [role="option"]:hover, [role="option"][aria-selected="true"] {{background:{t['raised']} !important;}}
[data-baseweb="select"] span, [data-baseweb="select"] div {{color:{t['text']};}}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"], [data-testid="stPopoverBody"],
[data-baseweb="popover"] > div {{background:{t['panel']} !important; color:{t['text']} !important; border-color:{t['ctrl']} !important;}}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] {{background:{t['raised']} !important;}}
[data-testid="stPopoverBody"] * {{color:{t['text']};}}
button[kind], [data-testid="stPopover"] button, [data-testid="stDownloadButton"] button {{border-radius:4px !important;
  background:transparent !important; color:{t['text']} !important; border:1px solid {t['ctrl']} !important; box-shadow:none !important;}}
button[kind="primary"], button[kind="primaryFormSubmit"] {{background:{t['accent']} !important; color:{t['on_accent']} !important; border-color:{t['accent']} !important;}}
button[kind="primary"] p {{color:{t['on_accent']} !important;}}
button[kind]:hover {{border-color:{t['accent']} !important;}}
button p {{color:inherit;}}
[data-testid="stButtonGroup"] button {{border-radius:0 !important; background:transparent !important; color:{t['muted']} !important;
  border-color:{t['ctrl']} !important; font-size:13px;}}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{background:{t['raised']} !important; color:{t['text']} !important;}}
[data-testid="stButtonGroup"] button p {{color:inherit !important;}}
[data-testid="stExpander"] details {{border:0 !important; border-bottom:1px solid {t['line']} !important; border-radius:0 !important; background:transparent !important;}}
[data-testid="stExpander"] summary, [data-testid="stExpander"] details[open] > summary,
[data-testid="stExpander"] summary:focus, [data-testid="stExpander"] summary:active {{padding:12px 22px !important;
  color:{t['text']} !important; background:transparent !important; border-radius:0 !important;}}
[data-testid="stExpander"] summary:hover, [data-testid="stExpander"] details[open] > summary:hover {{background:{t['row_open']} !important;}}
[data-testid="stExpander"] summary svg {{fill:{t['muted']} !important; color:{t['muted']} !important;}}
[data-testid="stExpander"] summary *:not(svg):not(path) {{background:transparent !important;}}
[data-testid="stExpander"] summary p {{font-size:12px !important; letter-spacing:1.2px; text-transform:uppercase; color:{t['sub']} !important;}}
[data-testid="stExpanderDetails"] {{padding:4px 22px 14px 22px !important;}}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{gap:0; border-bottom:1px solid {t['line']};}}
[data-testid="stTabs"] [data-baseweb="tab"] {{background:transparent; padding:0 14px; height:44px;}}
[data-testid="stTabs"] [data-baseweb="tab"] p {{font-size:12px; letter-spacing:1.2px; text-transform:uppercase; color:{t['muted']};}}
[data-testid="stTabs"] [aria-selected="true"] p {{color:{t['text']}; font-weight:600;}}
[data-baseweb="tab-highlight"] {{background:{t['accent']} !important;}}
[data-baseweb="tab-border"] {{background:{t['line']} !important;}}
[data-testid="stSlider"] [role="slider"] {{background:{t['accent']}; border-color:{t['accent']};}}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"], [data-testid="stSliderThumbValue"] {{color:{t['muted']} !important;}}
[data-baseweb="checkbox"] span, [data-baseweb="radio"] div {{border-color:{t['ctrl']};}}
[data-testid="stAlert"] {{border-radius:4px; background:{t['row_open']} !important; color:{t['text']};}}
[data-testid="stDataFrame"] {{border:1px solid {t['line']};}}
[data-testid="stCheckbox"] label > div:first-of-type {{background:{t['panel']} !important; border:1px solid {t['ctrl']} !important;
  border-radius:3px !important;}}
[data-testid="stCheckbox"][data-selected] label > div:first-of-type {{background:{t['accent']} !important; border-color:{t['accent']} !important;}}
[data-testid="stCheckbox"] label > div:first-of-type svg, [data-testid="stCheckbox"] label > div:first-of-type polyline {{stroke:{t['on_accent']} !important;}}
[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type {{background:{t['ctrl']} !important; border-radius:999px !important;
  border:0 !important;}}
[data-testid="stCheckbox"][data-selected]:has(input[role="switch"]) label > div:first-of-type {{background:{t['accent']} !important;}}
[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type > div {{background:{t['panel']} !important;}}
[data-testid="stRadioOption"] > div > div:first-child {{background:{t['panel']} !important; border:1px solid {t['ctrl']} !important;}}
[data-testid="stRadioOption"][data-selected] > div > div:first-child {{background:{t['accent']} !important; border-color:{t['accent']} !important;}}
[data-testid="stRadioOption"] > div > div:first-child > div {{background:{t['panel']} !important;}}
[data-testid="stTooltipIcon"] svg, [data-testid="stTooltipIcon"] button {{color:{t['muted']} !important; background:transparent !important;}}
[data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] label, [data-testid="stPopoverBody"] span {{color:{t['text']};}}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] * {{color:{t['muted']} !important;}}
[data-testid="stSlider"] [role="slider"] {{background:{t['accent']} !important; border-color:{t['accent']} !important; box-shadow:none !important;}}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input {{background:{t['panel']} !important; color:{t['text']} !important;}}
[data-testid="stNumberInput"] button {{background:{t['row_open']} !important; color:{t['text']} !important;}}
[data-testid="stProgressBarTrack"] {{background:{t['line']} !important;}}
[data-testid="stProgressBarFill"], [data-testid="stProgressBarTrack"] > div {{background:{t['accent']} !important;}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{color:{t['text']} !important;
  font-family:{FONT_NUM}; font-weight:500;}}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{color:{t['muted']} !important;}}
[data-testid="stAlert"] *, [data-testid="stCaptionContainer"] * {{color:inherit;}}
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentInfo"] * {{color:{t['text']} !important;}}
[data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] code {{color:{t['text']};}}
[data-testid="stMarkdownContainer"] code {{background:{t['row_open']};}}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {{color:{t['sub']} !important;}}
[data-baseweb="checkbox"] p, [data-testid="stRadio"] p {{color:{t['text']} !important;}}

/* text styles */
.bsv-title {{font-family:{FONT_NUM}; font-size:1.6rem; font-weight:500; margin:0; line-height:1.15; color:{t['text']};}}
.bsv-sub {{color:{t['muted']}; font-size:0.88rem; margin:0;}}
.bsv-lbl {{font-size:11px; letter-spacing:1.2px; text-transform:uppercase; color:{t['muted']};}}
.bsv-place {{font-family:{FONT_NUM}; font-size:34px; font-weight:500; line-height:1.05; margin:6px 0 2px 0; color:{t['text']};}}
.bsv-num {{font-family:{FONT_NUM}; font-weight:500;}}
.bsv-note {{color:{t['muted']}; font-size:0.82rem;}}
.bsv-sq {{display:inline-block; vertical-align:middle; margin-right:6px; flex:0 0 auto;}}
.bsv-pill {{display:inline-flex; align-items:center; gap:0; font-family:{FONT_NUM}; font-size:13px; letter-spacing:0.6px;
  text-transform:uppercase; color:{t['soft']};}}
.bsv-chip {{display:inline-block; margin-right:12px; font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{t['muted']};}}
.bsv-origin {{display:inline-block; font-size:10.5px; letter-spacing:1px; text-transform:uppercase; margin-right:6px;}}
.bsv-box {{border:0; border-bottom:1px solid {t['line']}; padding:14px 0; margin:0; background:transparent;}}
.bsv-card {{border:0; border-bottom:1px solid {t['line2']}; border-left:0 !important; border-radius:0; padding:12px 0; margin:0;
  background:transparent;}}
.bsv-card h4 {{margin:0 0 4px 0; font-family:{FONT_UI}; font-size:14.5px; font-weight:500;}}
.bsv-card .val {{font-family:{FONT_NUM}; font-size:22px; font-weight:500;}}
.bsv-card .ref, .bsv-card .lbl {{color:{t['muted']};}}
.bsv-card .row {{font-size:13px; margin:3px 0; color:{t['sub']};}}
.bsv-card .lbl {{font-size:10.5px; letter-spacing:1px; text-transform:uppercase; margin-right:6px;}}
.bsv-card .src {{color:{t['muted']}; font-size:11.5px; margin-top:6px; border-top:1px solid {t['line2']}; padding-top:4px;}}
.bsv-card summary {{cursor:pointer;}}
.stApp table {{color:{t['text']};}}
</style>
"""
    # no blank lines: a blank line would end the HTML block and Markdown would print the rest as text
    return "\n".join(line for line in out.splitlines() if line.strip())


# Okabe-Ito
OI = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "grey": "#8C8C8C",
}

# evidence / origin -> colour used in every chart, so "measured / satellite / model" always look the same
class _ThemedOrigin(dict):
    """Origin colours; 'measured' is black on light and the text colour on dark, so it reads on both."""

    def __getitem__(self, k):
        v = dict.__getitem__(self, k)
        return tokens()["text"] if v == OI["black"] else v

    def get(self, k, default=None):
        return self[k] if k in self else default


ORIGIN = _ThemedOrigin({
    "measured": OI["black"], "in-situ": OI["black"],
    "satellite": OI["blue"],
    "model": OI["orange"], "reanalysis": OI["vermillion"],
    "climatology": OI["grey"], "derived": OI["purple"],
})
ORIGIN_LABEL = {"in-situ": "measured", "measured": "measured", "satellite": "satellite", "model": "model",
                "reanalysis": "model (reanalysis)", "derived": "derived", "climatology": "reference"}

# the sector colours already used in data/zones (pressure_zones.py), kept identical
SECTOR = {
    "ports": ("Ports and logistics", "#0072B2"),
    "shipyards": ("Shipyards and marine engineering", "#D55E00"),
    "tourism": ("Coastal and marine tourism", "#E69F00"),
    "fishing": ("Fishing", "#009E73"),
    "aquaculture": ("Aquaculture", "#CC79A7"),
}

# overlap count 1..5: read from data/zones/overlap_style.json (shared with the QGIS project), with this fallback
_OVERLAP_FALLBACK = [(1, "#FDE0B2", 0.45), (2, "#F4A259", 0.70), (3, "#D55E00", 0.85), (4, "#8C2D04", 0.90),
                     (5, "#4A1402", 0.95)]


def overlap_levels() -> dict:
    """{count: (colour, opacity, label)} from data/zones/overlap_style.json, else the agreed fallback ramp."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / "data" / "zones" / "overlap_style.json"
    try:
        lv = json.loads(f.read_text())["levels"]
        out = {int(x["count"]): (x["color"], float(x.get("opacity", 0.8)), x.get("label") or f"{x['count']} sectors")
               for x in lv}
        if out:
            return out
    except Exception:
        pass
    return {k: (c, a, f"{k} sector{'s' if k > 1 else ''}") for k, c, a in _OVERLAP_FALLBACK}


OVERLAP = {k: v[0] for k, v in overlap_levels().items()}

CSS = css("dark")  # kept for older imports; app.py injects css(theme_name()) instead


def table_html(df, height: int | None = None) -> str:
    """A DataFrame as a flat themed HTML table (st.dataframe draws on a canvas and ignores the light theme)."""
    import pandas as pd
    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for v in r.values:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = ""
            elif isinstance(v, pd.Timestamp):
                v = v.strftime("%d %b %Y")
            elif isinstance(v, float):
                v = f"{v:.4g}"
            elif isinstance(v, (list, tuple)):
                v = ", ".join(map(str, v))
            cells.append(f"<td>{esc(v)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    box = f"max-height:{height}px;overflow:auto" if height else "overflow-x:auto"
    return (f"<div class='bsv-tablebox' style='{box}'><table class='bsv-table'><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def pill(status: str) -> str:
    """Status as a small square plus a text label (direction B: no pills)."""
    lab = STATUS_LABEL.get(status or "no_data", "No data")
    return f"<span class='bsv-pill'>{status_square(status)}{lab}</span>"


def origin_tag(origin: str) -> str:
    o = (origin or "").lower()
    return f"<span class='bsv-origin' style='color:{tokens()['muted']}'>{esc(ORIGIN_LABEL.get(o, o or 'unknown'))}</span>"


def swatch(color: str, label: str, dashed: bool = False) -> str:
    border = f"2px dashed {color}" if dashed else f"1px solid {color}"
    return (f"<span style='display:inline-block;width:12px;height:12px;background:{color if not dashed else 'transparent'};"
            f"border:{border};margin-right:6px;vertical-align:middle'></span>{esc(label)}")
