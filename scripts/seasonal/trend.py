"""Interannual linear trend on annual means (deliberately simple: OLS slope only, no Mann-Kendall).

The code now lives in marinekit.seasonal (src/marinekit/seasonal.py); this module re-exports it unchanged.

  * annual_means(series, ...)   daily series -> complete calendar years only, with n days and SE of each mean
  * linear_trend(series, ...)   -> dict: slope per decade with 95 % CI, p-value, R2, n years; meaningful=False
                                and no slope below min_years complete years
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from marinekit.seasonal import SEASON, annual_means, linear_trend  # noqa: E402,F401
