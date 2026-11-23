# Methods page content: measurement needs and uncertainty by user level

For the viewer's Data and methods page (`src/viewer/screens.py`, `methods_screen`). Data side: `src/marinekit/methods.py`,
tests in `tests/test_methods.py`, snapshot in `MEASUREMENT_NEEDS.md` and `measurement_needs.csv` (regenerate with
`scripts/methods/write_methods_docs.py`). Offline and read-only: no download, reads the committed validation and
seasonal results. No existing interface changes; this is a new module.

## For the design side: how to call it

```python
from marinekit import methods as M

# profile: "public" | "student" | "stakeholder" | "stakeholder:<sector>" | "researcher",
# or the viewer's profile dict {"role": ..., "sector": ...} as kept in st.session_state["profile"]

st.markdown(M.uncertainty_primer(profile))            # short intro, top of the page or of a new tab

# suggested new tab "Measurement needs"
needs = M.measurement_needs(profile)                   # ranked DataFrame; columns depend on the profile
st.dataframe(needs)                                    # or table_html(needs)
# researcher: all columns incl. the five criteria (bool), n_reasons, evidence (one line per criterion)
# stakeholder with a sector: extra bool column concerns_you (highlight those rows)
# map markers: M.measurement_needs() has lat, lon (approximate) and what / why for the hover

# suggested "Uncertainty" block, one expander per variable
for v in ["sst", "chl", "sal", "o2", "o2_bottom", "no3"]:
    st.markdown(M.uncertainty_text(v, profile))        # markdown; researcher text contains two tables
```

Card ids are accepted as aliases (`temperature`, `oxygen`, `blooms`, `nutrients`, ...), so a card can link to its
own uncertainty text: `M.uncertainty_text(card["id"], profile)`.

## What each level gets

| Level | Measurement needs | Uncertainty text |
|---|---|---|
| public | rank, what, where, why | a confidence word (reliable / fairly reliable / rough guide only) and one sentence |
| student | + the reasons met and their count | the public sentence, then what RMSE and bias mean with this variable's numbers, and one lesson (R² mostly from the seasons; agreement is not accuracy; a bad reference makes a good source look bad; an average hides opposite errors) |
| stakeholder | + how, who, cost, sectors; `concerns_you` with a sector | what the uncertainty means for the decision of that sector (e.g. aquaculture: bottom O2 is not measured near the farms, so an alert means lower a probe first) |
| researcher | everything, with the evidence per criterion | trusted source, the full metrics table, method, R² vs R² of anomalies, autocorrelation, the quality gate table, caveats, sources not used |

## Ranking rule (OURS)
Five yes/no criteria, counted: D sources disagree, N no trusted in-situ sensor, S a sensor exists but is not trusted,
T gap in time, P an official threshold depends on it. More reasons first; ties go to official thresholds, then to the
cheaper action. No weights, no composite index (same spirit as the pressure overlap count). Details and the
evidence per row: `MEASUREMENT_NEEDS.md`.
