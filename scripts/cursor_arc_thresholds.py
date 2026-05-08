"""Threshold sensitivity for cursor approach-retreat-reclick on AdSERP.

Reports trial-level and participant-level prevalence at multiple visit_count
thresholds so we can see whether the 100% participant ceiling on the gaze
side survives under a stricter cursor definition (visit_count >= 2 vs >= 3
vs >= 4).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))
from cursor_arc_prevalence import visit_counts_for_trial  # noqa: E402


def main():
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Processing {len(trials):,} trials...", flush=True)

    # Per trial: (clicked_position_visit_count, max_visit_count_any_pos, pid)
    per_trial = []
    skipped = 0
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            visits, click_pos = visit_counts_for_trial(tid)
        except Exception:
            skipped += 1
            continue
        if visits is None:
            skipped += 1
            continue
        pid = tid.split("-")[0]
        click_visits = visits.get(click_pos, 0) if click_pos is not None else 0
        max_visits = max(visits.values()) if visits else 0
        per_trial.append((tid, pid, click_pos, click_visits, max_visits))

    n_trials = len(trials)
    n_participants = len({pid for _, pid, *_ in per_trial})

    print(f"\nTotal trials: {n_trials}  (skipped {skipped} with no AOI/mouse data)")
    print(f"Distinct participants: {n_participants}\n")

    print("Cursor visit_count >= K at clicked position (approach-retreat-reclick):")
    print(f"{'K':>3} | {'trials':>10} | {'%trials':>8} | {'parts':>6} | {'%parts':>7}")
    print("-" * 50)
    for k in (2, 3, 4, 5, 6):
        trials_meeting = [t for t in per_trial if t[3] >= k]
        parts_meeting = {t[1] for t in trials_meeting}
        print(
            f"{k:>3} | {len(trials_meeting):>10,} | "
            f"{100 * len(trials_meeting) / n_trials:>7.2f}% | "
            f"{len(parts_meeting):>6} | "
            f"{100 * len(parts_meeting) / n_participants:>6.2f}%"
        )

    # Also: cursor visited the clicked AOI multiple times AND made multiple
    # passes through some other AOI before settling. A different operationalization
    # of "really deliberated, not just incidentally re-entered."
    print(
        "\nStricter: clicked-pos visit_count>=2 AND any other-pos visit_count>=2"
    )
    n_strict_trials = sum(1 for t in per_trial if t[3] >= 2 and t[4] >= 2)
    strict_parts = {
        t[1] for t in per_trial if t[3] >= 2 and t[4] >= 2
    }
    print(
        f"  trials: {n_strict_trials}  ({100 * n_strict_trials / n_trials:.2f}%)"
    )
    print(
        f"  participants: {len(strict_parts)}  "
        f"({100 * len(strict_parts) / n_participants:.2f}%)"
    )


if __name__ == "__main__":
    main()
