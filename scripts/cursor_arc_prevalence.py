"""Cursor-side approach-retreat-reclick prevalence on AdSERP.

Counterpart to the gaze-regression-based prevalence used in the v0.2.1 release
notes thread. Computes, per (trial, position), the cursor visit_count using
the AR library's visit-detection rules ported to Python:

  - approach margin: 40 px around AOI bbox
  - min visit dwell: 100 ms (visits shorter than this don't count)
  - re-approach window: 5000 ms (re-entries within 5 s of exit count as
    the same visit, not a new one — exact AR library semantics)

A trial exhibits cursor approach-retreat-reclick iff the click position has
visit_count >= 2 (cursor entered, exited, came back, and clicked).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import load_mouse_events  # noqa: E402

AOI_DIR = ROOT / "data/aoi-typed-gapfill"
APPROACH_MARGIN_PX = 40
MIN_DWELL_MS = 100
REAPPROACH_WINDOW_MS = 5000


def in_aoi(x, y, aoi):
    return (
        x >= aoi["x"] - APPROACH_MARGIN_PX
        and x <= aoi["x"] + aoi["width"] + APPROACH_MARGIN_PX
        and y >= aoi["y"] - APPROACH_MARGIN_PX
        and y <= aoi["y"] + aoi["height"] + APPROACH_MARGIN_PX
    )


def visit_counts_for_trial(trial_id):
    """Return dict pos -> visit_count and (clicked_pos or None).

    visit_count is the number of finalized cursor visits to that AOI: enter,
    dwell >= 100 ms, exit, and (if re-entered within 5 s) merged into the
    prior visit rather than starting a new one.
    """
    aoi_path = AOI_DIR / f"{trial_id}.json"
    if not aoi_path.exists():
        return None, None
    with open(aoi_path) as f:
        aois = json.load(f)
    if not aois:
        return None, None
    pos_aois = {a["position"]: a for a in aois if "position" in a}

    try:
        events, _scrolls, clicks = load_mouse_events(trial_id)
    except FileNotFoundError:
        return None, None

    pos_events = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup"}
    cursor = sorted(
        [(t, x, y) for (t, evt, x, y) in events if evt in pos_events],
        key=lambda r: r[0],
    )
    if not cursor:
        return None, None

    # Walk cursor; track current AOI per (position) and finalized visits.
    visit_counts = defaultdict(int)
    last_exit_t = {}  # pos -> t of most recent exit
    current_pos = None
    enter_t = None

    def finalize(pos, et, xt):
        if xt - et < MIN_DWELL_MS:
            return
        prev_exit = last_exit_t.get(pos)
        if prev_exit is not None and (et - prev_exit) <= REAPPROACH_WINDOW_MS:
            # Re-entry within reapproach window — same visit, don't increment.
            pass
        else:
            visit_counts[pos] += 1
        last_exit_t[pos] = xt

    for t, x, y in cursor:
        # Find which AOI (if any) the cursor is in. First match wins.
        in_pos = None
        for pos, aoi in pos_aois.items():
            if in_aoi(x, y, aoi):
                in_pos = pos
                break

        if in_pos == current_pos:
            continue
        # Cursor changed AOI (or left).
        if current_pos is not None and enter_t is not None:
            finalize(current_pos, enter_t, t)
        current_pos = in_pos
        enter_t = t if in_pos is not None else None

    # Finalize trailing visit, if any.
    if current_pos is not None and enter_t is not None and cursor:
        finalize(current_pos, enter_t, cursor[-1][0])

    clicked_pos = None
    if clicks:
        # Use the LAST click — AdSERP trials terminate on a result click.
        ct, cx, cy = clicks[-1]
        for pos, aoi in pos_aois.items():
            if in_aoi(cx, cy, aoi):
                clicked_pos = pos
                break

    return dict(visit_counts), clicked_pos


def main():
    # Trial set comes from the canonical features file so we line up with the
    # gaze-side number (49.59% of 2,545 trials).
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Processing {len(trials):,} trials...", flush=True)

    n_arc_trials = 0          # cursor approach-retreat-reclick
    n_clicked_trials = 0       # any click attributed to a position
    n_skipped = 0
    arc_participants = set()
    all_participants = set()

    by_pos_arc = defaultdict(int)  # click position -> count of ARC trials at that pos

    for i, tid in enumerate(trials):
        if i % 200 == 0:
            print(f"  {i}/{len(trials)} ({tid})", flush=True)
        pid = tid.split("-")[0]
        all_participants.add(pid)
        try:
            visits, click_pos = visit_counts_for_trial(tid)
        except Exception as e:
            n_skipped += 1
            continue
        if visits is None:
            n_skipped += 1
            continue
        if click_pos is None:
            continue
        n_clicked_trials += 1
        if visits.get(click_pos, 0) >= 2:
            n_arc_trials += 1
            arc_participants.add(pid)
            by_pos_arc[click_pos] += 1

    n_trials = len(trials)
    n_participants = len(all_participants)
    print(f"\nTotal trials processed: {n_trials:,}  (skipped: {n_skipped})")
    print(f"Trials with a cursor-attributable click: {n_clicked_trials:,}")
    print(f"\nCursor approach-retreat-reclick (visit_count>=2 at clicked position):")
    print(
        f"  trials: {n_arc_trials:,}  "
        f"({100 * n_arc_trials / n_trials:.2f}% of {n_trials:,} all trials, "
        f"{100 * n_arc_trials / max(n_clicked_trials,1):.2f}% of {n_clicked_trials:,} click-attributable trials)"
    )
    print(
        f"  participants: {len(arc_participants)}  "
        f"({100 * len(arc_participants) / n_participants:.2f}% of {n_participants})"
    )

    print("\nARC trials by clicked position:")
    for pos in sorted(by_pos_arc):
        print(f"  pos {pos}: {by_pos_arc[pos]}")


if __name__ == "__main__":
    main()
