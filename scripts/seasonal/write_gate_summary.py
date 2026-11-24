"""Snapshot of marinekit.seasonal.gate_summary() for the Methods page (fast to read in the viewer).

    MARINEKIT_OFFLINE=1 .venv\Scripts\python.exe scripts/seasonal/write_gate_summary.py

Writes docs/indicators/seasonal/gate_summary.csv. Re-run after run_seasonal.py, fetch_long_sst.py or a change of
source trust in marinekit.datahub.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from marinekit.seasonal import PRECOMPUTED, gate_summary  # noqa: E402

if __name__ == "__main__":
    g = gate_summary()
    g.to_csv(PRECOMPUTED / "gate_summary.csv", index=False, float_format="%.4g")
    print(f"wrote {PRECOMPUTED / 'gate_summary.csv'}: {len(g)} rows, cycle shown {int(g.cycle_show.sum())}, "
          f"trend shown {int(g.trend_show.sum())}")
