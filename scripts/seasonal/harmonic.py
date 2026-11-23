"""Seasonal / cycle analysis: OLS (or WLS) harmonic regression with periods taken from the power spectra.

The code now lives in marinekit.seasonal (src/marinekit/seasonal.py); this module re-exports it unchanged so
run_seasonal.py, report.py and tests/test_seasonal.py keep working.

  * aggregate(series, freq, how)           daily series -> weekly or monthly means (or medians) with n and SE
  * fit_harmonics(series, periods, ...)    one fit -> dict (cycles, model stats, residual checks, HAC errors)
  * compare_nested(series, periods, ...)   models with 0, 1, ..., K cycles -> what each cycle adds
  * select_periods(peaks, ...)             the K strongest significant, fittable periods from peaks.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from marinekit.seasonal import (  # noqa: E402,F401
    HARMONIC_CYCLES, YEAR_D, _design, _fmt_doy, _normalise, _ols, _pick, _src, _truthy, _wald, acf, aggregate,
    compare_nested, fit_harmonics, ljung_box, newey_west_lags, phase_label, select_periods,
)
