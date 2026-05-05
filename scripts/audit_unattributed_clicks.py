"""Audit click-attribution gap under typed bboxes.

For each trial, take the FINAL click (the trial-terminating choice) and check:
- did it land in any typed bbox? which etype?
- if not, what's its (x, y) and how does it relate to nearby bboxes?
- specifically: does it land just outside (near-miss), or far away (chrome)?

Regime tag: [LAB, AdSERP, typed, audit-2026-05-05]
Headline: 2,084/2,774 final-clicks attributed (75.1%) under tight bboxes; 80%
of unattributed are within +/-10 px Y of an organic bbox edge with X strictly
inside the result column (link-padding clicks).

See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#2.1)
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import get_trial_meta, load_mouse_events  # noqa: E402

TYPED_CSV = ROOT / "scripts/output/adserp_aois_by_trial_id_typed.csv"


def load_typed_aois():
    by_trial = defaultdict(list)
    with open(TYPED_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row["trial_id"]
            by_trial[tid].append({
                "rank": int(row["rank"]),
                "etype": row["etype"],
                "top_y": float(row["top_y"]),
                "bottom_y": float(row["bottom_y"]),
                "left_x": float(row["left_x"]),
                "right_x": float(row["right_x"]),
                "screen_height": float(row["screen_height"]),
            })
    for tid in by_trial:
        by_trial[tid].sort(key=lambda a: a["rank"])
    return dict(by_trial)


def assign_to_aoi(x, y, aois):
    best_rank = -1
    best_area = float("inf")
    for a in aois:
        if a["top_y"] <= y <= a["bottom_y"] and a["left_x"] <= x <= a["right_x"]:
            area = (a["bottom_y"] - a["top_y"]) * (a["right_x"] - a["left_x"])
            if area < best_area:
                best_area = area
                best_rank = a["rank"]
    return best_rank


def near_miss_diagnostic(x, y, aois, x_tol=20, y_tol=10):
    """For an unattributed click, find what would have matched with relaxed bounds."""
    near_x = []
    near_y = []
    near_both = []
    for a in aois:
        in_x = a["left_x"] - x_tol <= x <= a["right_x"] + x_tol
        in_y = a["top_y"] - y_tol <= y <= a["bottom_y"] + y_tol
        in_x_strict = a["left_x"] <= x <= a["right_x"]
        in_y_strict = a["top_y"] <= y <= a["bottom_y"]
        if in_x_strict and in_y and not in_y_strict:
            near_y.append((a["etype"], a["rank"]))
        if in_y_strict and in_x and not in_x_strict:
            near_x.append((a["etype"], a["rank"]))
        if in_x and in_y and not (in_x_strict and in_y_strict):
            near_both.append((a["etype"], a["rank"]))
    return near_x, near_y, near_both


def main():
    aois_by_trial = load_typed_aois()
    print(f"loaded {len(aois_by_trial):,} trials of typed AOIs")

    # Categories
    cat = Counter()
    cat_n_clicks_per_trial = Counter()  # for trials, what n_clicks looked like
    final_click_etype = Counter()
    final_click_unattr_examples = []
    near_miss_etype_x = Counter()  # x-near-miss by etype
    near_miss_etype_y = Counter()  # y-near-miss by etype
    near_miss_etype_both = Counter()
    final_y_unattr = []  # for histogram of unattributed final-click Ys
    final_x_unattr = []
    final_x_attr = []
    final_y_attr = []

    # Doc geometry stats for unattributed clicks
    n_above_screen_top = 0  # y < 0
    n_below_doc = 0  # y > doc_h
    n_in_doc = 0

    n_no_clicks = 0
    n_total = 0

    for tid, aois in aois_by_trial.items():
        meta = get_trial_meta(tid)
        if meta[0] is None:
            continue
        doc_h, scr_h, _ = meta
        try:
            mouse_data = load_mouse_events(tid)
        except Exception:
            continue
        if mouse_data is None:
            continue
        _, _, clicks = mouse_data
        n_total += 1

        if not clicks:
            n_no_clicks += 1
            cat["no_clicks_in_trial"] += 1
            continue

        cat_n_clicks_per_trial[len(clicks)] += 1

        # Use the FINAL click (trial-terminating choice)
        final = clicks[-1]
        if len(final) < 3:
            cat["final_click_malformed"] += 1
            continue
        cx, cy = float(final[1]), float(final[2])
        rank = assign_to_aoi(cx, cy, aois)
        if rank >= 0:
            etype = next(a["etype"] for a in aois if a["rank"] == rank)
            final_click_etype[etype] += 1
            cat["final_click_attributed"] += 1
            final_x_attr.append(cx)
            final_y_attr.append(cy)
        else:
            cat["final_click_unattributed"] += 1
            final_x_unattr.append(cx)
            final_y_unattr.append(cy)
            if cy < 0:
                n_above_screen_top += 1
            elif cy > doc_h:
                n_below_doc += 1
            else:
                n_in_doc += 1
            nx, ny, nb = near_miss_diagnostic(cx, cy, aois)
            for e, r in nx:
                near_miss_etype_x[e] += 1
            for e, r in ny:
                near_miss_etype_y[e] += 1
            for e, r in nb:
                near_miss_etype_both[e] += 1
            if len(final_click_unattr_examples) < 30:
                final_click_unattr_examples.append({
                    "trial_id": tid,
                    "click_xy": (cx, cy),
                    "doc_h": doc_h,
                    "scr_h": scr_h,
                    "near_x": nx[:3],
                    "near_y": ny[:3],
                })

    print(f"\ntrials examined: {n_total:,}")
    print(f"no clicks at all: {n_no_clicks}")
    print(f"\nfinal-click categorization:")
    for k, v in cat.most_common():
        print(f"  {k}: {v:,}")

    n_attr = cat["final_click_attributed"]
    n_unattr = cat["final_click_unattributed"]
    print(f"\nfinal-click attribution rate: "
          f"{n_attr:,}/{n_attr + n_unattr:,} = "
          f"{100.0 * n_attr / (n_attr + n_unattr):.1f}%")

    print(f"\nfinal-click attributed etype breakdown:")
    for etype, n in final_click_etype.most_common():
        print(f"  {etype}: {n:,} ({100.0 * n / n_attr:.1f}%)")

    print(f"\nclicks-per-trial distribution:")
    for n, v in sorted(cat_n_clicks_per_trial.items()):
        print(f"  {n} click(s): {v:,} trials")

    print(f"\nfor UNATTRIBUTED final clicks, doc-geometry buckets:")
    print(f"  click_y < 0 (above page top): {n_above_screen_top}")
    print(f"  click_y > doc_h (below page): {n_below_doc}")
    print(f"  inside doc: {n_in_doc}")

    print(f"\nfor UNATTRIBUTED final clicks, NEAR-MISS analysis:")
    print(f"  total unattributed: {n_unattr}")
    print(f"  near-miss in X only (within ±20px of bbox L/R, Y inside bbox):")
    for etype, n in near_miss_etype_x.most_common():
        print(f"    {etype}: {n:,}")
    print(f"  near-miss in Y only (within ±10px of bbox top/bottom, X inside bbox):")
    for etype, n in near_miss_etype_y.most_common():
        print(f"    {etype}: {n:,}")
    print(f"  near-miss in both:")
    for etype, n in near_miss_etype_both.most_common():
        print(f"    {etype}: {n:,}")

    # Quick stats on Y / X distributions
    import numpy as np
    if final_y_unattr:
        print(f"\nUnattributed final click Y (page-space pixel) percentiles:")
        for p in [0, 10, 25, 50, 75, 90, 100]:
            print(f"  p{p}: {np.percentile(final_y_unattr, p):.0f}")
        print(f"\nUnattributed final click X percentiles:")
        for p in [0, 10, 25, 50, 75, 90, 100]:
            print(f"  p{p}: {np.percentile(final_x_unattr, p):.0f}")
    if final_y_attr:
        print(f"\nAttributed final click Y percentiles (for comparison):")
        for p in [0, 25, 50, 75, 100]:
            print(f"  p{p}: {np.percentile(final_y_attr, p):.0f}")
        print(f"Attributed final click X percentiles:")
        for p in [0, 25, 50, 75, 100]:
            print(f"  p{p}: {np.percentile(final_x_attr, p):.0f}")

    print(f"\nFirst 10 unattributed final clicks:")
    for ex in final_click_unattr_examples[:10]:
        print(f"  {ex['trial_id']}: click@{ex['click_xy']}, doc_h={ex['doc_h']}, "
              f"scr_h={ex['scr_h']}, near_x={ex['near_x']}, near_y={ex['near_y']}")


if __name__ == "__main__":
    main()
