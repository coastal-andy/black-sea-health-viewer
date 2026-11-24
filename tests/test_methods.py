"""Tests for marinekit.methods (measurement needs and uncertainty text for the Methods page). Committed CSVs only."""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from marinekit import methods as M  # noqa: E402
from marinekit import validation as val  # noqa: E402

CRIT = list(M.CRITERIA)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


@pytest.fixture(scope="module")
def needs():
    return M.measurement_needs()


def test_needs_columns_and_counts(needs):
    for c in ["rank", "need_id", "what", "where", "how", "why", "cost", "who", "lat", "lon", "n_reasons",
              "reasons", "evidence", "label", *CRIT]:
        assert c in needs.columns
    assert list(needs["rank"]) == list(range(1, len(needs) + 1))
    assert needs.need_id.is_unique
    assert (needs[CRIT].sum(axis=1) == needs.n_reasons).all()
    assert needs.cost.isin(M.COST_ORDER).all()
    assert needs.lat.between(43.5, 45.5).all() and needs.lon.between(28.5, 31.0).all()


def test_ranking_is_ordered_rule_not_weights(needs):
    key = list(zip(-needs.n_reasons, ~needs.decision_at_stake, needs.cost.map(M.COST_ORDER)))
    assert key == sorted(key)


def test_known_findings(needs):
    r = needs.set_index("need_id")
    assert r.loc["chl_buoys", CRIT].all()                       # buoy chl: 5 of 5
    assert r.loc["sst", "n_reasons"] == 0                        # SST: nothing needed
    assert r.loc["sal_buoys", "untrusted_sensor"] and not r.loc["sal_buoys", "decision_at_stake"]
    assert r.loc["o2_bottom", "no_trusted_insitu"] and r.loc["o2_bottom", "hand_set"] == "disagree"
    assert not r.loc["chl_plume", "disagree"]                    # not testable: only 3 bottle days
    assert not r.loc["buoy_continuity", "no_trusted_insitu"]     # OB01 / OB03 O2 trusted and reporting
    assert needs.iloc[0].need_id in {"chl_buoys", "o2_coast"}


def test_evidence_numbers_match_metrics(needs):
    ev = needs.set_index("need_id").evidence
    assert "-1.46" in ev["o2_coast"]
    assert "Spearman 0.41" in ev["nutrients"] and "0.01" in ev["nutrients"]
    assert "44 complete years" in ev["sst"]


@pytest.mark.parametrize("profile", ["public", "student", "stakeholder", "stakeholder:aquaculture",
                                     {"role": "stakeholder", "sector": "tourism"}, "researcher"])
def test_needs_by_profile(needs, profile):
    d = M.measurement_needs(profile)
    assert len(d) == len(needs) and list(d["rank"]) == list(needs["rank"])
    role, sector = M._parse_profile(profile)
    if role == "researcher":
        assert list(d.columns) == list(needs.columns)
    else:
        assert set(M.PROFILE_COLUMNS[role]) <= set(d.columns)
    assert ("concerns_you" in d.columns) == bool(sector)


@pytest.mark.parametrize("var", M.uncertainty_variables())
@pytest.mark.parametrize("profile", ["public", "student", "stakeholder", "stakeholder:aquaculture",
                                     "stakeholder:tourism", "researcher"])
def test_uncertainty_text_every_level(var, profile):
    t = M.uncertainty_text(var, profile)
    assert isinstance(t, str) and len(t) > 40
    assert not EMOJI.search(t)


def test_levels_differ_and_grow():
    for v in ["sst", "chl", "o2", "o2_bottom"]:
        p, s, r = (M.uncertainty_text(v, x) for x in ("public", "student", "researcher"))
        assert len(p) < len(s) < len(r)
        assert s.startswith(p)                                   # student = public sentence + explanation


def test_numbers_follow_validation():
    s = val.source_summary("sst")
    assert f"{s['rmse']:.2f}" in M.uncertainty_text("sst", "student")
    assert "0.56" in M.uncertainty_text("sst", "researcher")     # long satellite trend per decade
    assert "Spearman" in M.uncertainty_text("no3", "student")


def test_sector_text_changes_and_aliases():
    assert M.uncertainty_text("o2", "stakeholder:aquaculture") != M.uncertainty_text("o2", "stakeholder")
    assert "probe" in M.uncertainty_text("oxygen", {"role": "stakeholder", "sector": "aquaculture"})
    assert M.uncertainty_text("temperature", "public") == M.uncertainty_text("sst", "public")
    assert M.uncertainty_text("sst", "unknown-role") == M.uncertainty_text("sst", "public")
    with pytest.raises(ValueError):
        M.uncertainty_text("wind", "public")


@pytest.mark.parametrize("profile", ["public", "student", "stakeholder:fishing", "researcher"])
def test_primer(profile):
    t = M.uncertainty_primer(profile)
    assert "model" in t.lower() and not EMOJI.search(t)
