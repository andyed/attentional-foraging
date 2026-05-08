"""Conservative-regression threshold sweep for gaze approach-retreat-reclick.

Pairs `count_revisits_per_trial` (per-(trial,position) gaze revisit count)
with the canonical features file's `was_clicked` and `min_dist < 100` to
produce trial-level and participant-level prevalence at multiple thresholds.

The point: the v0.2.1 thread cited a 100% participant ceiling on the
loose definition (≥1 gaze return). This script asks whether 100% survives
when the regression criterion is "really deliberated" — ≥2 distinct returns,
or ≥3.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))
from nb22_revisit_count import count_revisits_per_trial  # noqa: E402


def main():
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)

    # Index features by (trial, position) for click + min_dist lookup.
    feat_idx = {(r["trial_id"], r["position"]): r for r in feats}
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Processing {len(trials):,} trials...", flush=True)

    # Per-(trial, position) revisit count.
    # Records: (trial_id, pid, position, revisits, was_clicked, approached)
    records = []
    skipped = 0
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            result = count_revisits_per_trial(tid)
            # Returns {"regressive_fix": {pos: n}, "distinct_returns": {pos: n}}
        except Exception:
            skipped += 1
            continue
        if result is None:
            skipped += 1
            continue
        pid = tid.split("-")[0]
        # Use distinct_returns — counts gaze re-entries from other positions,
        # so long dwell on one position doesn't inflate the count. This is
        # the cleaner "how many times did the gaze come back" metric.
        revisits = result["distinct_returns"]
        for pos, n in revisits.items():
            row = feat_idx.get((tid, pos))
            if row is None:
                continue
            approached = row["min_dist"] < 100
            clicked = row["was_clicked"]
            records.append((tid, pid, pos, n, clicked, approached))

    n_trials = len(trials)
    n_participants = len({pid for _, pid, *_ in records})
    print(f"\nRecords with revisit data: {len(records):,} (skipped {skipped} trials)")
    print(f"Distinct trials in features: {n_trials}")
    print(f"Distinct participants: {n_participants}\n")

    print("Gaze regression: ≥K distinct returns AND approached AND clicked")
    print(f"{'K':>3} | {'records':>9} | {'trials':>10} | {'%trials':>8} | {'parts':>6} | {'%parts':>7}")
    print("-" * 60)
    for k in (1, 2, 3, 4, 5):
        meeting = [
            (tid, pid)
            for tid, pid, _pos, n, clk, app in records
            if n >= k and clk and app
        ]
        meeting_trials = {tid for tid, _ in meeting}
        meeting_parts = {pid for _, pid in meeting}
        print(
            f"{k:>3} | {len(meeting):>9,} | {len(meeting_trials):>10,} | "
            f"{100 * len(meeting_trials) / n_trials:>7.2f}% | "
            f"{len(meeting_parts):>6} | "
            f"{100 * len(meeting_parts) / n_participants:>6.2f}%"
        )


if __name__ == "__main__":
    main()
