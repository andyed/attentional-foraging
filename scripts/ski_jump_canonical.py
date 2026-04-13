"""Reproduce the canonical ski-jump from notebooks-v2/00_skijump.ipynb
using the post-coord-fix data and current data_loader contract.

Bins the FIRST click of each trial by absolute-rank band. This counts
clicks at positions 0..10+ including ads, and reports click SHARE
(fraction of total clicks landing at each position). This is the
distribution shown in README.md and is the origin of the canonical
"ski jump" shape with the position-10 uptick.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    count_absolute_ranks,
    absolute_rank_band_tops,
)


def click_to_position(clicks, tops, n_res):
    if not clicks or not tops:
        return None
    _, _, cy = clicks[0]
    pos = -1
    for i, top in enumerate(tops):
        if cy >= top:
            pos = i
        else:
            break
    if pos < 0 or pos >= n_res:
        return None
    return pos


def main():
    tids = get_trial_ids()
    print(f"trials: {len(tids)}")

    counts = {}
    total = 0
    for i, tid in enumerate(tids):
        if i % 500 == 0:
            print(f"  processed {i}/{len(tids)}")
        doc_h, _, _ = get_trial_meta(tid)
        if not doc_h:
            continue
        n_res = count_absolute_ranks(tid)
        if n_res < 3:
            continue
        _, _, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        tops = absolute_rank_band_tops(n_res, doc_h)
        pos = click_to_position(clicks, tops, n_res)
        if pos is None:
            continue
        counts[pos] = counts.get(pos, 0) + 1
        total += 1

    print(f"\ntotal first-click trials: {total}")
    print(" Pos   Clicks    Share")
    print("-------------------------")
    for pos in sorted(counts):
        c = counts[pos]
        share = c / total
        print(f"  {pos:>2}   {c:>6}   {share*100:5.2f}%")

    # Dump as CSV
    out = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/ski_jump_canonical.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        f.write("position,clicks,share\n")
        for pos in sorted(counts):
            c = counts[pos]
            share = c / total
            f.write(f"{pos},{c},{share:.4f}\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
