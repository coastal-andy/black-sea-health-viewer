"""First-visit questionnaire: three short steps that set st.session_state['profile']."""

from __future__ import annotations

import streamlit as st

from viewer import profiles as P


def _choice(label: str, options: dict, key: str, help_map: dict | None = None):
    """A column of large buttons; returns the chosen key or None."""
    st.markdown(f"#### {label}")
    picked = None
    for k, text in options.items():
        h = (help_map or {}).get(k)
        if st.button(text if not h else f"{text}  \n{h}", key=f"{key}_{k}", width="stretch"):
            picked = k
    return picked


def render():
    ss = st.session_state
    draft = ss.setdefault("ob_draft", P.default_profile() | {"role": None})
    step = ss.setdefault("ob_step", 1)
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown("<p class='bsv-title' style='font-size:1.7rem'>Black Sea Health Viewer</p>"
                    "<p class='bsv-sub'>Romanian coast: sea conditions, long-term change, and the pressures from five "
                    "blue-economy sectors. Three quick questions set up the view for you.</p>", unsafe_allow_html=True)
        st.progress(step / 3, text=f"Step {step} of 3")
        if step == 1:
            r = _choice("Who are you?", P.ROLES, "role", P.ROLE_HELP)
            if r:
                draft.update(role=r, sector=None, focus=None)
                ss.ob_step = 2
                st.rerun()
        elif step == 2:
            role = draft["role"]
            if role == "stakeholder":
                s = _choice("Which sector do you work in?", P.SECTORS, "sector")
                if s:
                    draft["sector"] = s
                    ss.ob_step = 3
                    st.rerun()
            elif role == "researcher":
                f = _choice("What is your main focus?", P.FOCUS, "focus")
                if f:
                    draft["focus"] = f
                    ss.ob_step = 3
                    st.rerun()
            else:
                ss.ob_step = 3
                st.rerun()
        elif step == 3:
            g = _choice("What do you want to do?", P.GOALS, "goal")
            if g:
                draft["goal"] = g
                finish(dict(draft))
                st.rerun()
        c1, c2 = st.columns(2)
        if step > 1 and c1.button("Back", key="ob_back"):
            ss.ob_step = 1 if (step == 3 and draft["role"] in ("public", "student")) else step - 1
            st.rerun()
        if c2.button("Skip, use the general view", key="ob_skip"):
            finish(P.default_profile())
            st.rerun()
        st.caption("You can change this at any time with the profile control at the top of the page.")


def finish(profile: dict):
    ss = st.session_state
    ss.profile = profile
    ss.onboarding = False
    ss.ob_step = 1
    ss.pop("ob_draft", None)
    apply_defaults(profile)


def apply_defaults(profile: dict):
    """Reset layers, panel view, variable, starting area to the profile's defaults."""
    ss = st.session_state
    layers = P.default_layers(profile)
    ss.layers = layers
    from viewer.maps import GRIDDED
    g = [l for l in layers if l in GRIDDED]
    ss["w_grid"] = g[0] if g else "none"
    for lid in ("insitu", "overlap", "zones", "features", "natura", "bathy", "vec_waves", "vec_currents", "vec_wind"):
        ss[f"w_{lid}"] = lid in layers
    ss["w_view"] = P.default_panel(profile)
    ss["w_var"] = P.default_variable(profile)
    sv = P.start_view(profile)
    ss.view = dict(lat=sv["lat"], lon=sv["lon"], zoom=sv["zoom"])
    name, lat, lon = sv["point"]
    ss.sel = dict(name=name, lat=lat, lon=lon, kind="point", wkt=None)
    ss["w_place"] = None
    ss.map_nonce = ss.get("map_nonce", 0) + 1
    if profile.get("role") == "stakeholder" and profile.get("sector"):
        ss["w_sector"] = profile["sector"]
