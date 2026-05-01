"""Build the canonical per-(trial, position) viewport + trajectory features JSON.

Analog to AdSERP/data/cursor-approach-features.json. One row per (trial, position)
covering all 10 positions per trial (unfiltered — downstream consumers decide
which subset to use).

Features emitted (14):
  Viewport bands (4):       vt_any, vt_top, vt_mid, vt_bot
  Continuous viewport (3):  vt_center_ms, avg_viewport_y, max_overlap_frac
  Trajectory (7):           max_abs_velocity, min_abs_velocity, pause_ms,
                            n_reversals, max_decel_near_center,
                            entry_velocity, exit_velocity

Extractor is lifted verbatim from scripts/nb30_scroll_trajectory.py
(compute_features_for_trial) so numbers match NB30's validation.

Usage:
  .venv/bin/python scripts/build_viewport_trajectory_features.py

Output:
  AdSERP/data/viewport-trajectory-features.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import get_trial_ids  # noqa: E402
from nb30_scroll_trajectory import compute_features_for_trial  # noqa: E402

OUT_PATH = ROOT / "AdSERP/data/viewport-trajectory-features.json"

FEATURE_NAMES = [
    # bands
    "vt_any", "vt_top", "vt_mid", "vt_bot",
    # continuous viewport
    "vt_center_ms", "avg_viewport_y", "max_overlap_frac",
    # trajectory
    "max_abs_velocity", "min_abs_velocity", "pause_ms", "n_reversals",
    "max_decel_near_center", "entry_velocity", "exit_velocity",
]


def main() -> None:
    trials = get_trial_ids()
    print(f"[build] {len(trials):,} trials from data_loader.get_trial_ids()")

    rows = []
    missing = 0
    t0 = time.time()
    for i, tid in enumerate(trials):
        feats = compute_features_for_trial(tid, n_positions=10)
        if feats is None:
            missing += 1
            continue
        for pos, f in enumerate(feats):
            row = {"trial_id": tid, "position": pos}
            for name in FEATURE_NAMES:
                row[name] = float(f.get(name, 0.0) or 0.0)
            rows.append(row)
        if (i + 1) % 250 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta_s = (len(trials) - (i + 1)) / rate
            print(f"  {i+1}/{len(trials)} ({rate:.1f} trials/s, ETA {eta_s:.0f}s, missing={missing})")

    print(f"[build] done. rows={len(rows):,} trials_with_data={len(rows)//10:,} missing={missing}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows))
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"[build] wrote {OUT_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
