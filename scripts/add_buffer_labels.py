"""Add the hover label `buffer_label` to every feature of data/zones/sector_zones.geojson (additive, in place).

Example labels: "300 m (law)", "1000 m (rule)", "AIS density cells, no buffer" (shipping lanes: the zone is the
top-decile EMSA vessel-density cells, so a 0 m buffer is correct by design). Re-run after rebuilding the zones
with `python -m marinekit.pressure_zones`, which does not write this property.

    .venv/Scripts/python.exe scripts/add_buffer_labels.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marinekit import pressure_zones as pz  # noqa: E402

if __name__ == "__main__":
    n = pz.add_buffer_labels()
    print(f"buffer_label written on {n} features of {pz.OUT_DIR / 'sector_zones.geojson'}")
