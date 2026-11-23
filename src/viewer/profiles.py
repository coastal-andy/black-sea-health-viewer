"""User profiles from the first-visit questionnaire, and what each profile changes.

A profile is a small dict kept in st.session_state["profile"]:
    {"role": "public|student|stakeholder|researcher", "sector": <sector key or None>,
     "focus": "physical|chemical|biological|None", "goal": "now|change|compare|risk"}
It sets: the wording level, the default map layers, the starting area and how much detail shows.
"""

from __future__ import annotations

ROLES = {
    "public": "General public",
    "student": "Student",
    "stakeholder": "Sector stakeholder",
    "researcher": "Researcher",
}
ROLE_HELP = {
    "public": "Plain language, the main layers only.",
    "student": "Short explanations of what each measurement means.",
    "stakeholder": "Starts on your sector's zones and the risks there.",
    "researcher": "Dataset IDs, QC flags and uncertainty numbers shown.",
}
SECTORS = {
    "ports": "Ports and logistics",
    "shipyards": "Shipyards and marine engineering",
    "tourism": "Coastal and marine tourism",
    "fishing": "Fishing",
    "aquaculture": "Aquaculture",
}
FOCUS = {"physical": "Physical (temperature, salinity, waves, currents)",
         "chemical": "Chemical (oxygen, nutrients, pH)",
         "biological": "Biological (chlorophyll, blooms, species)"}
GOALS = {
    "now": "See conditions now",
    "change": "See long-term change",
    "compare": "Compare data sources",
    "risk": "Check risks in my area",
}

# starting view (lat, lon, zoom) and a representative point for the panel
START = {
    "default": dict(lat=44.35, lon=29.05, zoom=8, point=("Constanța offshore", 44.17, 28.72)),
    "ports": dict(lat=44.12, lon=28.68, zoom=11, point=("Port of Constanța approaches", 44.10, 28.70)),
    "shipyards": dict(lat=44.05, lon=28.66, zoom=10, point=("Constanța - Agigea shipyards", 44.08, 28.68)),
    "tourism": dict(lat=44.15, lon=28.66, zoom=10, point=("Mamaia beach waters", 44.25, 28.70)),
    "fishing": dict(lat=44.40, lon=29.10, zoom=8, point=("Shelf fishing grounds", 44.40, 29.50)),
    "aquaculture": dict(lat=43.85, lon=28.66, zoom=10, point=("Mangalia / 2 Mai", 43.79, 28.64)),
}

# default map layers by goal; researchers' focus adds its own layer
_GOAL_LAYERS = {
    "now": ["sst", "insitu", "natura"],
    "change": ["sst_anom", "insitu"],
    "compare": ["chl", "insitu"],
    "risk": ["overlap", "natura", "insitu"],
}
_FOCUS_LAYER = {"physical": "sst", "chemical": "o2_bottom", "biological": "chl"}
_GOAL_PANEL = {"now": "Health cards", "change": "Long-term trend", "compare": "Compare sources", "risk": "Health cards"}
_GOAL_VAR = {"physical": "sst", "chemical": "o2", "biological": "chl"}


def default_profile() -> dict:
    return {"role": "public", "sector": None, "focus": None, "goal": "now"}


def describe(p: dict) -> str:
    s = ROLES.get(p.get("role"), "Visitor")
    if p.get("role") == "stakeholder" and p.get("sector"):
        s += f" - {SECTORS[p['sector']]}"
    if p.get("role") == "researcher" and p.get("focus"):
        s += f" - {p['focus']}"
    return s


def default_layers(p: dict) -> list[str]:
    layers = list(_GOAL_LAYERS.get(p.get("goal"), _GOAL_LAYERS["now"]))
    if p.get("role") == "stakeholder":
        layers = [l for l in layers if l not in ("sst_anom",)] + ["zones", "overlap"]
    if p.get("role") == "researcher" and p.get("focus"):
        f = _FOCUS_LAYER[p["focus"]]
        gridded = {"sst", "sst_anom", "chl", "kd490", "model_temp", "o2", "o2_bottom"}
        layers = [l for l in layers if l not in gridded] + [f]
    return list(dict.fromkeys(layers))


def default_panel(p: dict) -> str:
    return _GOAL_PANEL.get(p.get("goal"), "Health cards")


def default_variable(p: dict) -> str:
    if p.get("role") == "researcher" and p.get("focus"):
        return _GOAL_VAR[p["focus"]]
    if p.get("role") == "stakeholder" and p.get("sector") == "aquaculture":
        return "o2"
    if p.get("goal") == "compare":
        return "chl"
    return "sst"


def start_view(p: dict) -> dict:
    if p.get("role") == "stakeholder" and p.get("sector") in START:
        return START[p["sector"]]
    return START["default"]


def level(p: dict) -> str:
    """Wording key used by the indicator cards' text dict: public|student|stakeholder|researcher."""
    return p.get("role") or "public"


def card_profile(p: dict) -> str:
    """Profile string for marinekit.indicators: 'stakeholder:<sector>' adds a sector-specific sentence."""
    if p.get("role") == "stakeholder" and p.get("sector"):
        return f"stakeholder:{p['sector']}"
    return level(p)


def show_detail(p: dict) -> bool:
    """Researchers see dataset IDs, QC and uncertainty numbers."""
    return p.get("role") == "researcher"


# wording that changes with the profile (labels for the variables on the map and in charts)
VAR_TEXT = {
    "sst": {"public": "Sea temperature", "student": "Sea surface temperature",
            "stakeholder": "Sea surface temperature", "researcher": "SST (L4, satellite)"},
    "chl": {"public": "Algae in the water (chlorophyll)", "student": "Chlorophyll-a (algae indicator)",
            "stakeholder": "Chlorophyll-a (algae, blooms)", "researcher": "Chlorophyll-a"},
    "o2": {"public": "Oxygen in the water", "student": "Dissolved oxygen", "stakeholder": "Dissolved oxygen",
           "researcher": "Dissolved O2"},
    "o2_bottom": {"public": "Oxygen near the seabed", "student": "Bottom oxygen", "stakeholder": "Bottom oxygen",
                  "researcher": "Bottom O2 (model)"},
    "sal": {"public": "Saltiness of the water", "student": "Salinity", "stakeholder": "Salinity", "researcher": "Salinity"},
    "kd490": {"public": "Water clarity (murkiness)", "student": "Light attenuation (Kd490)",
              "stakeholder": "Water clarity (Kd490)", "researcher": "Kd490"},
}

EXPLAIN = {
    "anomaly": {
        "public": "The shaded band shows what is normal for this time of year. Points outside it are unusual.",
        "student": "Anomaly = today's value minus the long-term average for the same day of the year. "
                   "The band is the 10th to 90th percentile of past years.",
        "stakeholder": "Outside the band means unusual for the season; check the health cards for what it may mean for your work.",
        "researcher": "Day-of-year climatology (11-day window, 31-day smoothing); band = p10 to p90 of the reference period.",
    },
    "trend": {
        "public": "Each dot is the average of one year. The line shows the long-term direction.",
        "student": "Annual means with a least-squares trend. 'Change per decade' is the slope times ten years.",
        "stakeholder": "A rising or falling line means conditions in your area are shifting over decades.",
        "researcher": "OLS on annual means (years with at least 300 daily values); 95 % CI from the t distribution, no autocorrelation correction.",
    },
    "compare": {
        "public": "The same thing measured three ways: by a buoy in the water, from space and by a computer model.",
        "student": "Measured (buoy) is the ground truth, satellite sees only the surface, the model fills gaps.",
        "stakeholder": "When the lines agree, you can trust the value more.",
        "researcher": "Daily means at the nearest valid grid cell or platform; distances are in the source line.",
    },
}


def text(table: dict, key: str, p: dict) -> str:
    d = table.get(key, {})
    return d.get(level(p)) or d.get("public") or key
