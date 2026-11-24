"""Add the team's slides (steps 2-7 and the close) after the sector slides in the shared deck.

Usage: python pitch/build_deck.py <her_deck.pptx> <out.pptx>
Needs python-pptx. Matches her deck: white background, Calibri, title in three lines
(blue bold caps, green bold caps, black subtitle), sector colours from the Kumu diagram.
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).parent
A = HERE / "assets"

BLUE = RGBColor(0x44, 0x72, 0xC4)   # her title line 1 (theme accent1)
GREEN = RGBColor(0x00, 0xB0, 0x50)  # her title line 2
INK = RGBColor(0x1F, 0x1F, 0x1F)
MUTED = RGBColor(0x59, 0x59, 0x59)
LINE = RGBColor(0xBF, 0xBF, 0xBF)
PANEL = RGBColor(0xF3, 0xF6, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SECTOR = {
    "Ports": RGBColor(0x3D, 0x6F, 0xB6),
    "Shipyards": RGBColor(0x7E, 0x4C, 0xA3),
    "Tourism": RGBColor(0xE3, 0x8C, 0x34),
    "Fishing": RGBColor(0x3F, 0x91, 0x55),
    "Aquaculture": RGBColor(0x37, 0x96, 0x96),
}
STATUS = {"normal": RGBColor(0x2B, 0xB3, 0x8A), "watch": RGBColor(0xF2, 0xB1, 0x34),
          "alert": RGBColor(0xF0, 0x7B, 0x3F), "no data": RGBColor(0x6E, 0x83, 0x92)}


def blank_layout(prs):
    for lay in prs.slide_layouts:
        if lay.name.lower() == "blank":
            return lay
    return prs.slide_layouts[6]


def text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, margin=0.05):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, opts) tuples."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", Inches(margin))
    paras = [runs] if isinstance(runs, str) else runs
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        items = [(para, {})] if isinstance(para, str) else para
        for t, o in items:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = "Calibri"
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.color.rgb = o.get("color", color)
        p.space_after = Pt(o.get("after", 4)) if items else Pt(4)
    return tb


def box(slide, x, y, w, h, fill=PANEL, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.shadow.inherit = False
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    return s


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.5)
    ln = c.line._get_or_add_ln()
    from pptx.oxml.ns import qn
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def square(slide, x, y, color, size=0.16):
    return box(slide, x, y, size, size, fill=color)


def title(slide, line1, line2, sub):
    text(slide, 0.14, 0.13, 9.6, 1.2, [
        [(line1, {"size": 26, "bold": True, "color": BLUE, "after": 0})],
        [(line2, {"size": 20, "bold": True, "color": GREEN, "after": 2})],
        [(sub, {"size": 14, "color": INK})],
    ], margin=0.02)


def picture_fit(slide, path, x, y, w, h):
    from PIL import Image
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    return slide.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2),
                                    Inches(pw), Inches(ph))


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# ---------------------------------------------------------------------------------------------

def slide_pressure(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "PRESSURE MAP", "WHERE THE FIVE SECTORS MEET",
          "Step 2  |  Number of sectors present in each 250 m cell (0-5)")
    picture_fit(s, A / "pressure_soft_map.png", 0.3, 1.45, 9.2, 5.5)
    text(s, 0.3, 7.0, 9.0, 0.35, "Soft edges: zone limits are approximate, so they fade over 1-3 km. Inside the zones the "
         "colour is the exact count. Lines mark 1, 2 and 3 sectors.", size=11, color=MUTED)
    x = 9.75
    stats = [("330", "features mapped in 5 sectors, each with a confidence: official, mapped or assumed"),
             ("76  to  2", "cells with 4 sectors, summer to winter: tourism drives the summer overlap"),
             ("0", "cells with all 5 sectors: the mussel leases sit away from the ports")]
    y = 1.55
    for big, small in stats:
        text(s, x, y, 3.3, 0.6, big, size=36, bold=True, color=BLUE)
        text(s, x, y + 0.68, 3.3, 0.8, small, size=13, color=INK)
        y += 1.62
    text(s, x, 6.4, 3.3, 0.9, "Plain count, no weights. One buffer per activity, from law, literature "
         "or a stated rule.", size=12, color=MUTED)
    notes(s, "Teammate. Five sectors share one coast. We mapped 330 features, each with how sure we are. "
             "The map counts how many sectors meet in each 250 m cell. In summer 76 cells have four sectors, "
             "along the resort coast; in winter only 2. No cell has all five. It shows where sectors overlap, "
             "not how much harm they do. Hand over to Joseph.")


def slide_architecture(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "MONITORING ARCHITECTURE", "ONE CHECKED DATA HUB",
          "Step 3  |  Observation technologies, parameters and data flows")
    sources = [
        ("Offshore buoys", "EMODnet Physics: temperature, salinity, oxygen, chlorophyll"),
        ("Bottle samples", "EMODnet Chemistry 1963-2021: nutrients, oxygen, chlorophyll"),
        ("Satellite", "Copernicus Marine: sea temperature, chlorophyll-a, water clarity"),
        ("Models and reanalysis", "Copernicus Marine: T, S, oxygen, pH, waves, currents; GloFAS Danube, wind"),
        ("Sector layers", "EMODnet, OpenStreetMap, ship tracks (AIS): ports, farms, beaches, lanes"),
    ]
    y0, bh, gap = 1.6, 0.86, 0.14
    for i, (h, d) in enumerate(sources):
        y = y0 + i * (bh + gap)
        box(s, 0.35, y, 3.7, bh, fill=PANEL)
        text(s, 0.45, y + 0.06, 3.5, bh - 0.1, [[(h, {"bold": True, "size": 14, "after": 1})],
                                                [(d, {"size": 11, "color": MUTED})]])
    # hub
    hub_y = y0 + 0.2
    box(s, 4.75, hub_y, 2.7, 3.4, fill=BLUE)
    text(s, 4.85, hub_y + 0.15, 2.5, 3.1, [
        [("Data hub", {"bold": True, "size": 18, "color": WHITE, "after": 8})],
        [("Same units and grid", {"size": 13, "color": WHITE})],
        [("Quality control and a trust flag per sensor and variable", {"size": 13, "color": WHITE})],
        [("Local cache: works offline", {"size": 13, "color": WHITE})],
    ])
    for i in range(4):
        y = y0 + i * (bh + gap) + bh / 2
        arrow(s, 4.05, y, 4.75, min(max(y, hub_y + 0.3), hub_y + 3.1))
    # indicators and zones
    box(s, 8.15, 1.8, 2.3, 1.5, fill=PANEL)
    text(s, 8.25, 1.88, 2.1, 1.4, [[("Indicators", {"bold": True, "size": 14, "after": 2})],
                                   [("9 health cards, anomaly against the usual range, model against observation",
                                     {"size": 11, "color": MUTED})]])
    box(s, 8.15, 4.0, 2.3, 1.5, fill=PANEL)
    text(s, 8.25, 4.08, 2.1, 1.4, [[("Pressure zones", {"bold": True, "size": 14, "after": 2})],
                                   [("5 sectors, one buffer per activity, overlap count",
                                     {"size": 11, "color": MUTED})]])
    arrow(s, 7.45, 2.55, 8.15, 2.55)
    arrow(s, 4.05, y0 + 4 * (bh + gap) + bh / 2, 8.15, 5.3)
    # viewer and users
    box(s, 11.05, 2.6, 1.95, 1.9, fill=GREEN)
    text(s, 11.12, 2.7, 1.8, 1.7, [[("Viewer", {"bold": True, "size": 16, "color": WHITE, "after": 4})],
                                   [("map, cards, charts, 4 user profiles", {"size": 12, "color": WHITE})]])
    arrow(s, 10.45, 2.55, 11.05, 3.2)
    arrow(s, 10.45, 4.75, 11.05, 3.9)
    text(s, 11.05, 4.6, 1.95, 1.0, "Sector managers, NIMRD, agencies, public", size=12, color=INK)
    # requirements strip
    text(s, 7.6, 5.85, 5.5, 1.3, [
        [("Space  ", {"bold": True, "size": 13}), ("250 m zones, 1-5 km satellite, 2.5 km model, buoys",
                                                   {"size": 13})],
        [("Time  ", {"bold": True, "size": 13}), ("daily values, 10-day forecast, climatology 1991-2020",
                                                  {"size": 13})],
        [("Origin  ", {"bold": True, "size": 13}), ("every value labelled measured, satellite or model",
                                                    {"size": 13})],
    ])
    notes(s, "Joseph. Five kinds of source feed one data hub. It puts them on the same units and grid, "
             "checks quality and gives every sensor a trust flag, and caches everything, so the demo runs "
             "offline. From there come the indicators and the pressure zones, and the viewer shows both.")


def slide_decision(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "DATA TO DECISION", "NATURAL CHANGE OR PRESSURE?",
          "Step 4  |  Integration, quality control, indicators and analysis")
    steps = [("1", "Integrate and check", "same units, QC, trust flag"),
             ("2", "Compare with normal", "anomaly against the usual range for that date"),
             ("3", "Threshold", "labelled OFFICIAL-RO, OFFICIAL-EU or OURS"),
             ("4", "Rule chain", "natural drivers are tested first"),
             ("5", "Status", "normal, watch or alert, with a confidence"),
             ("6", "Investigate", "a concrete next check, and who acts")]
    w, gap, y = 1.95, 0.17, 1.6
    for i, (n, h, d) in enumerate(steps):
        x = 0.35 + i * (w + gap)
        box(s, x, y, w, 1.45, fill=BLUE if i in (3, 5) else PANEL)
        c = WHITE if i in (3, 5) else INK
        cm = WHITE if i in (3, 5) else MUTED
        text(s, x + 0.08, y + 0.06, w - 0.16, 1.35, [[(f"{n}  {h}", {"bold": True, "size": 14, "color": c,
                                                                      "after": 2})],
                                                     [(d, {"size": 11, "color": cm})]])
        if i < 5:
            arrow(s, x + w, y + 0.72, x + w + gap, y + 0.72)
    # rule chain
    text(s, 0.35, 3.3, 6.4, 0.4, "The rule chain: first match wins", size=16, bold=True)
    rules = ["Model-only anomaly where the model is weak: model artefact",
             "Upwelling, June to September: natural",
             "Cold salty water reaching the seabed: natural",
             "Danube plume or flood: natural, or mixed",
             "Storm in the last 3 days: natural",
             "Bloom decay under a stratified sea: eutrophication pressure",
             "High ammonium or phosphate near an outfall: wastewater pressure",
             "5+ days, no driver, inside a sector zone: possible pressure, investigate"]
    text(s, 0.35, 3.75, 6.6, 3.4, [[(f"{i + 1}.  ", {"bold": True, "size": 13, "color": BLUE}),
                                    (r, {"size": 13})] for i, r in enumerate(rules)])
    # example
    box(s, 7.3, 3.35, 5.7, 1.5, fill=PANEL)
    text(s, 7.45, 3.42, 5.45, 1.4, [
        [("Example: low oxygen at the seabed", {"bold": True, "size": 14, "after": 3})],
        [("Every episode below 4 mg/L in the forecast since Dec 2024 is in the cold season, with seabed "
          "salinity 19.1-19.9. Rule 3: cold salty water, natural. No pressure is claimed.", {"size": 13})],
    ])
    box(s, 7.3, 5.05, 5.7, 1.3, fill=PANEL)
    text(s, 7.45, 5.12, 5.45, 1.2, [
        [("Example: what the tool recommends", {"bold": True, "size": 14, "after": 3})],
        [("Seabed oxygen class D at a mussel bed: camera transect and a grab sample within 2 weeks, "
          "by NIMRD and the farm operator.", {"size": 13})],
    ])
    notes(s, "Joseph. Six steps from a raw number to a decision. The key one is the rule chain: before we call "
             "anything a pressure, we test the natural explanations: upwelling, cold water at the seabed, the "
             "Danube, storms. Example: every low-oxygen episode at the seabed since December 2024 is explained "
             "by cold salty water, so it is natural. The output is a concrete check and who should do it. "
             "Hand over to Andrei for the demo.")


def slide_prototype(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "PROTOTYPE", "LIVE DEMO",
          "Step 5  |  Black Sea Health Viewer, built on free open data, runs offline")
    users = [("Public", "Is the water fine today? One sentence and 9 status squares."),
             ("Student", "How the sea works: seasons, upwelling, the Danube."),
             ("Sector manager", "My sites, what overlaps with them, and what to check."),
             ("Researcher", "Sources, errors, model against observation, data download.")]
    text(s, 0.35, 1.55, 6.0, 0.4, "One tool, four users", size=16, bold=True)
    for i, (h, d) in enumerate(users):
        y = 2.05 + i * 1.02
        box(s, 0.35, y, 6.0, 0.88, fill=PANEL)
        text(s, 0.5, y + 0.08, 5.8, 0.8, [[(h, {"bold": True, "size": 14, "after": 1})],
                                          [(d, {"size": 12, "color": MUTED})]])
    text(s, 6.95, 1.55, 6.0, 0.4, "What the demo shows", size=16, bold=True)
    path = ["Overview: today at Constanța against a normal late-November day",
            "One indicator opened: value, usual range, rule chain",
            "Sector view: a mussel farm and what to check",
            "Water quality: 60-day chart and which source we trust",
            "Coast and seabed: waves, currents and wind on one map",
            "Pressures: summer against winter"]
    text(s, 6.95, 2.05, 6.0, 3.5, [[(f"{i + 1}.  ", {"bold": True, "size": 14, "color": BLUE}),
                                    (p, {"size": 14})] for i, p in enumerate(path)])
    y = 4.6
    text(s, 6.95, y - 0.05, 6.0, 0.35, "Status words, never colour alone", size=12, color=MUTED)
    for i, (k, c) in enumerate(STATUS.items()):
        x = 6.95 + i * 1.5
        square(s, x, y + 0.42, c)
        text(s, x + 0.22, y + 0.33, 1.25, 0.35, k, size=13)
    text(s, 0.35, 6.3, 6.0, 0.8, "Every value shows its unit and its origin: measured, satellite or model.",
         size=13, color=MUTED)
    notes(s, "Andrei. Switch to the viewer (localhost:8502). Follow the demo script in pitch/PLAN.md, 2 minutes. "
             "If the app fails, play the screen recording.")


def slide_validation(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "VALIDATION", "HOW MUCH TO TRUST EACH NUMBER",
          "Step 6  |  Reliability, uncertainty and ecological interpretation")
    rows = [("Variable", "Reference we use", "Typical error", "Checked against"),
            ("Sea temperature", "satellite", "about 0.45 °C", "4 buoys, about 5400 days"),
            ("Salinity", "model", "about 1 PSU at the coast", "41 bottle days"),
            ("Surface oxygen", "buoy after QC, else model", "1 mg/L offshore, 2 at the coast", "4 buoys, 41 bottle days"),
            ("Chlorophyll-a", "satellite", "not known, factor 1.6 or more", "model only (no trusted sensor)"),
            ("Nitrate, phosphate", "bottles and climatology", "model: shape only, or none", "35-38 bottle days")]
    tbl = s.shapes.add_table(len(rows), 4, Inches(0.35), Inches(1.6), Inches(8.0), Inches(3.2)).table
    widths = [1.75, 2.05, 2.25, 1.95]
    for j, wv in enumerate(widths):
        tbl.columns[j].width = Inches(wv)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = BLUE if i == 0 else (PANEL if i % 2 == 0 else WHITE)
            tf = cell.text_frame
            tf.text = v
            for p in tf.paragraphs:
                for run in p.runs:
                    run.font.name = "Calibri"
                    run.font.size = Pt(13)
                    run.font.bold = i == 0 or j == 0
                    run.font.color.rgb = WHITE if i == 0 else INK
            cell.margin_left = cell.margin_right = Inches(0.08)
    picture_fit(s, A / "taylor_sst.png", 8.55, 1.35, 4.65, 3.55)
    text(s, 8.6, 4.85, 4.5, 0.4, "Sea temperature: satellite and model sit next to the buoys "
         "(Taylor diagram).", size=11, color=MUTED)
    text(s, 0.35, 5.25, 6.2, 0.4, "Not trusted, shown greyed out", size=15, bold=True)
    text(s, 0.35, 5.65, 6.2, 1.6, [
        "Buoy chlorophyll reads 2-3 times too high",
        "Offshore buoy salinity: fouled sensor",
        "New coastal buoys EUXRoCB0x: not quality-controlled",
        "Station 15480: on shore, not sea temperature"], size=13)
    text(s, 6.9, 5.25, 6.2, 0.4, "Ecological interpretation", size=15, bold=True)
    text(s, 6.9, 5.65, 6.2, 1.6, [
        "An anomaly is not damage.",
        "Pressure only when the rule chain finds no natural driver.",
        "Seabed oxygen is model-only: low confidence, said in the app."], size=13)
    notes(s, "Joseph. We checked every source against buoys and bottle samples before trusting it. Satellite sea "
             "temperature is within about half a degree. Salinity from the model is within about 1 PSU at the "
             "coast. Model nitrate and phosphate do not match the bottles, so we never show them as values. "
             "Sensors that fail the checks stay visible but greyed out. Hand over to Andrei.")


def slide_impact(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "IMPACT AND ROADMAP", "FROM PROTOTYPE TO PILOT",
          "Step 7  |  Users, environmental benefits and pilot requirements")
    users = [("Ports", "dredging plumes, water clarity, new species from ballast water"),
             ("Shipyards", "footprint of coastal works"),
             ("Tourism", "bathing water, blooms, jellyfish"),
             ("Fishing", "oxygen and heat on the fishing grounds"),
             ("Aquaculture", "seabed oxygen and algal toxins at the farms")]
    text(s, 0.35, 1.55, 5.6, 0.4, "Who uses it, for what", size=16, bold=True)
    for i, (k, d) in enumerate(users):
        y = 2.05 + i * 0.6
        box(s, 0.35, y + 0.08, 0.3, 0.3, fill=SECTOR[k], shape=MSO_SHAPE.OVAL)
        text(s, 0.8, y, 5.2, 0.55, [[(k + "  ", {"bold": True, "size": 13}), (d, {"size": 13})]])
    text(s, 0.35, 5.15, 5.6, 1.9, [
        [("Benefit  ", {"bold": True, "size": 13}),
         ("samples go where and when they matter; natural events stop raising false alarms; "
          "one shared view for NIMRD, agencies and the five sectors.", {"size": 13})]])
    # timeline
    stages = [("Now", ["Working prototype", "Free open data", "Runs offline"]),
              ("Pilot, 3 months", ["With NIMRD: confirm thresholds", "Add monitoring data after 2021",
                                   "Check the coastal buoys", "Host on a server"]),
              ("Scale", ["Bulgarian and Ukrainian coasts", "Same Copernicus and EMODnet data",
                         "EfxINNOs final, Varna"])]
    x0, w, gap = 6.5, 2.05, 0.2
    for i, (h, items) in enumerate(stages):
        x = x0 + i * (w + gap)
        box(s, x, 1.6, w, 0.5, fill=BLUE if i == 1 else PANEL)
        text(s, x + 0.08, 1.62, w - 0.16, 0.45, h, size=14, bold=True, color=WHITE if i == 1 else INK,
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, x, 2.2, w, 2.0, items, size=12)
        if i < 2:
            arrow(s, x + w, 1.85, x + w + gap, 1.85)
    text(s, 6.5, 4.3, 6.5, 0.4, "Measure next (ranked by the tool)", size=16, bold=True)
    needs = [("Chlorophyll bottle samples at buoy visits", "low cost"),
             ("A checked coastal oxygen sensor", "low cost"),
             ("Nutrient samples after 2021 (NIMRD)", "medium"),
             ("Seabed oxygen at the mussel farms, May-Sep", "high")]
    for i, (n, c) in enumerate(needs):
        y = 4.8 + i * 0.55
        text(s, 6.5, y, 5.0, 0.5, [[(f"{i + 1}.  ", {"bold": True, "size": 13, "color": BLUE}), (n, {"size": 13})]])
        text(s, 11.5, y, 1.5, 0.5, c, size=13, color=MUTED, align=PP_ALIGN.RIGHT)
    notes(s, "Andrei: users and benefit. Joseph: pilot and measure next. A 3-month pilot with NIMRD makes it "
             "operational. The tool also ranks what to measure next: most of it is cheap, such as bottle "
             "samples at existing buoy visits. Then the same method for Bulgaria and Ukraine.")


def slide_close(prs):
    s = prs.slides.add_slide(blank_layout(prs))
    title(s, "BLACK SEA HEALTH VIEWER", "WHAT WE CLAIM, AND WHAT WE DO NOT", "")
    text(s, 0.35, 1.6, 6.0, 0.4, "Limits we state openly", size=16, bold=True)
    text(s, 0.35, 2.05, 6.0, 4.8, [
        "Copernicus model nitrate and phosphate are unreliable, so nutrients come from historical samples "
        "and climatology.",
        "Seabed oxygen is model-only (there is no seabed sensor), so its confidence is low.",
        "The new coastal buoys EUXRoCB0x are not quality-controlled. Station 15480 is on shore.",
        "Some fishing and shipyard features are assumed (landing points, pound nets, dumping sites) "
        "and are drawn dashed.",
        "The pressure count shows where sectors overlap, not how much impact they cause.",
    ], size=14)
    box(s, 6.95, 1.6, 6.05, 3.0, fill=BLUE)
    text(s, 7.2, 1.8, 5.6, 2.7, [
        [("For each place and day on the Romanian coast:", {"size": 18, "color": WHITE, "bold": True,
                                                            "after": 10})],
        [("is the water normal,", {"size": 18, "color": WHITE})],
        [("is a change natural or a likely pressure,", {"size": 18, "color": WHITE})],
        [("how much to trust each number,", {"size": 18, "color": WHITE})],
        [("and what to check next, for five blue-economy sectors.", {"size": 18, "color": WHITE})],
    ])
    text(s, 6.95, 4.95, 6.05, 0.6, "Thank you. Questions?", size=20, bold=True, color=GREEN)
    notes(s, "Andrei. Read the blue box as the closing sentence. Then questions: see Q&A in pitch/PLAN.md.")


def fill_title(prs):
    """Her slide 1 is an empty title layout: fill it in her title style, only if still empty."""
    s = prs.slides[0]
    if any(sh.has_text_frame and sh.text_frame.text.strip() for sh in s.shapes):
        return
    for sh in list(s.shapes):
        if sh.is_placeholder:
            sh._element.getparent().remove(sh._element)
    text(s, 0.9, 2.0, 11.5, 3.2, [
        [("BLACK SEA HEALTH VIEWER", {"size": 48, "bold": True, "color": BLUE, "after": 6})],
        [("ECOSYSTEM HEALTH FOR FIVE BLUE-ECONOMY SECTORS", {"size": 24, "bold": True, "color": GREEN,
                                                             "after": 18})],
        [("Is a change on the Romanian coast natural, or a pressure? How sure are we? What should be "
          "checked next?", {"size": 20, "color": INK})],
    ])
    text(s, 0.9, 5.9, 11.5, 0.8, "EfxINNOs Hackathon Romania  |  Challenge 04: Ecosystem Health  |  "
         "Constanța, 24 November 2026", size=14, color=MUTED)
    notes(s, "Teammate. One sentence: a map-first viewer that says, for each place and day, whether the water is "
             "normal, whether a change is natural or a likely pressure, how much to trust each number, and "
             "what to check next.")


def main(src, out):
    prs = Presentation(src)
    fill_title(prs)
    for fn in (slide_pressure, slide_architecture, slide_decision, slide_prototype, slide_validation,
               slide_impact, slide_close):
        fn(prs)
    prs.save(out)
    print("saved", out, "slides:", len(prs.slides))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
