"""Test (and refute) the calibration-bias hypothesis for typed bboxes.

Hypothesis under test: the apparent +20 px downward click drift seen in 5
visually-inspected replay trials is a corpus-wide systematic Y bias (either
in click ingestion or in bbox extraction).

For every (trial, click) and (trial, fixation), measure signed Y-distance
to the nearest typed bbox. If there's a systematic bias, the median signed
distance will be non-zero. Report:

  (1) For ATTRIBUTED clicks: position within bbox, normalized to [0, 1].
      No bias -> median 0.5. +Y bias -> median > 0.5.

  (2) For UNATTRIBUTED clicks: signed distance to nearest bbox. Positive =
      below bbox bottom; negative = above bbox top. A pure +Y bias predicts
      a sharp peak at +5 to +30 px (just below bbox).

  (3) Same analysis for FIXATIONS. Tests whether bias is in click stream
      specifically (evtrack ingestion) or shared across streams (screenshot/
      bbox coordinate frame).

  (4) Per-participant click bias. Per-session calibration drift would show as
      participant-specific outliers.

Regime tag: [LAB, AdSERP, typed, audit-2026-05-05]
Headline: REFUTED. Clicks attributed-bbox-center median +12.5 px (mean +11.2,
IQR -21 to +40); unattributed-clicks median signed distance only +3 px with
59% below / 41% above (roughly symmetric). Fixations are biased UPWARD
(median normalized 0.440, 66.5% of unattributed fixations above bbox top) -
opposite direction to clicks. If bboxes were Y-shifted, both streams would
shift the same way; they don't. The 5-example visual sample was selection-
biased on small N. Bboxes are well-positioned; the gap-fill is still needed
but as a midpoint-split, not a one-sided shift.

See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#3 calibration bias
test, refuted).
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    get_trial_meta, load_fixations, load_mouse_events,
)

TYPED_CSV = ROOT / "scripts/output/adserp_aois_by_trial_id_typed.csv"


def load_typed_aois():
    by_trial = defaultdict(list)
    with open(TYPED_CSV, newline="") as f:
        for row in csv.DictReader(f):
            by_trial[row["trial_id"]].append({
                "rank": int(row["rank"]),
                "etype": row["etype"],
                "top_y": float(row["top_y"]),
                "bottom_y": float(row["bottom_y"]),
                "left_x": float(row["left_x"]),
                "right_x": float(row["right_x"]),
            })
    for tid in by_trial:
        by_trial[tid].sort(key=lambda a: a["top_y"])
    return dict(by_trial)


def find_containing(x, y, aois):
    for a in aois:
        if a["top_y"] <= y <= a["bottom_y"] and a["left_x"] <= x <= a["right_x"]:
            return a
    return None


def nearest_aoi_signed_y(x, y, aois, x_tol=20):
    """Return signed Y-distance to nearest bbox where X is in-column.
    Positive = click is below the nearest bbox bottom.
    Negative = click is above the nearest bbox top."""
    best = None
    best_abs = float("inf")
    for a in aois:
        if not (a["left_x"] - x_tol <= x <= a["right_x"] + x_tol):
            continue
        if y < a["top_y"]:
            d = y - a["top_y"]   # negative
        elif y > a["bottom_y"]:
            d = y - a["bottom_y"]  # positive
        else:
            d = 0
        if abs(d) < best_abs:
            best_abs = abs(d)
            best = d
    return best


# ── 1. Attributed clicks: position-within-bbox ────────────────────────────
print("loading typed AOIs...")
aois_by_trial = load_typed_aois()

attr_pos_norm = []  # within-bbox normalized position [0, 1]
attr_y_offset_from_center_px = []  # raw px offset from bbox center
unattr_signed_y = []  # signed Y to nearest bbox
fix_attr_pos_norm = []
fix_unattr_signed_y = []

per_participant_attr_norm = defaultdict(list)
per_participant_unattr_signed = defaultdict(list)

n_trials = 0
n_clicks_attr = 0
n_clicks_unattr = 0
n_fix_attr = 0
n_fix_unattr = 0

for tid, aois in aois_by_trial.items():
    if not aois:
        continue
    meta = get_trial_meta(tid)
    if meta[0] is None:
        continue
    try:
        mouse = load_mouse_events(tid)
        fixations = load_fixations(tid)
    except Exception:
        continue
    if mouse is None or fixations is None:
        continue
    _, _, clicks = mouse

    pid = tid.split("-")[0]  # 'p004'
    n_trials += 1

    # Final click only
    if clicks:
        final = clicks[-1]
        if len(final) >= 3:
            cx, cy = float(final[1]), float(final[2])
            hit = find_containing(cx, cy, aois)
            if hit is not None:
                n_clicks_attr += 1
                center = (hit["top_y"] + hit["bottom_y"]) / 2
                height = hit["bottom_y"] - hit["top_y"]
                norm = (cy - hit["top_y"]) / height if height > 0 else 0.5
                attr_pos_norm.append(norm)
                attr_y_offset_from_center_px.append(cy - center)
                per_participant_attr_norm[pid].append(norm)
            else:
                signed = nearest_aoi_signed_y(cx, cy, aois)
                if signed is not None:
                    n_clicks_unattr += 1
                    unattr_signed_y.append(signed)
                    per_participant_unattr_signed[pid].append(signed)

    # All fixations
    for fix in fixations:
        fy = float(fix["y"]) if isinstance(fix, dict) else float(fix[2])
        fx = float(fix["x"]) if isinstance(fix, dict) else float(fix[1])
        hit = find_containing(fx, fy, aois)
        if hit is not None:
            height = hit["bottom_y"] - hit["top_y"]
            norm = (fy - hit["top_y"]) / height if height > 0 else 0.5
            fix_attr_pos_norm.append(norm)
            n_fix_attr += 1
        else:
            signed = nearest_aoi_signed_y(fx, fy, aois)
            if signed is not None:
                fix_unattr_signed_y.append(signed)
                n_fix_unattr += 1


def stats(arr, name):
    a = np.array(arr)
    print(f"\n  {name} (n={len(a):,})")
    print(f"    median: {np.median(a):.3f}")
    print(f"    mean:   {np.mean(a):.3f}")
    print(f"    p10/25/50/75/90: "
          f"{np.percentile(a, 10):.2f} / {np.percentile(a, 25):.2f} / "
          f"{np.percentile(a, 50):.2f} / {np.percentile(a, 75):.2f} / "
          f"{np.percentile(a, 90):.2f}")


print(f"\n=== {n_trials:,} trials processed ===\n")

print("=== TEST 1: Attributed click position WITHIN bbox (normalized) ===")
print("  No bias → median 0.5. +Y bias → median > 0.5.")
stats(attr_pos_norm, "click within-bbox normalized [0=top, 1=bottom]")
stats(attr_y_offset_from_center_px,
      "click Y offset from bbox center (px). +Y bias → median > 0.")

print("\n=== TEST 2: Unattributed click signed Y to nearest bbox (px) ===")
print("  +Y bias → sharp peak at +10 to +30 px (clicks just BELOW bboxes).")
stats(unattr_signed_y, "unattributed click signed Y (px)")
# Sign breakdown
arr = np.array(unattr_signed_y)
n_above = int((arr < 0).sum())
n_below = int((arr > 0).sum())
print(f"\n    above any bbox top (negative): {n_above:,}")
print(f"    below any bbox bottom (positive): {n_below:,}")
print(f"    asymmetry ratio below/total: {n_below / (n_above + n_below):.3f}")
print("    (0.50 = symmetric, > 0.50 = downward-biased)")

print("\n=== TEST 3: Fixation Y-bias (to compare against click bias) ===")
print("  Tests whether bias is click-stream-only or shared.")
stats(fix_attr_pos_norm,
      "fixation within-bbox normalized [0=top, 1=bottom]")
arr_fix = np.array(fix_unattr_signed_y)
print(f"\n  unattributed fixations: n={len(arr_fix):,}")
if len(arr_fix):
    n_above_f = int((arr_fix < 0).sum())
    n_below_f = int((arr_fix > 0).sum())
    print(f"    above bbox top: {n_above_f:,}")
    print(f"    below bbox bottom: {n_below_f:,}")
    print(f"    asymmetry: {n_below_f / (n_above_f + n_below_f):.3f}")

print("\n=== TEST 4: Per-participant click bias ===")
print("  If corpus-wide: every participant median should be near identical.")
print("  If session calibration: a few participants will have outlier medians.")
print(f"  {'pid':<8s}{'n':>6s}{'median norm':>14s}{'median offset px':>20s}")
print("  " + "-" * 50)
pids_sorted = sorted(per_participant_attr_norm.keys())
medians = []
for pid in pids_sorted:
    arr = per_participant_attr_norm[pid]
    if len(arr) >= 5:
        med_n = np.median(arr)
        unattr_arr = per_participant_unattr_signed.get(pid, [])
        med_unattr = np.median(unattr_arr) if unattr_arr else float("nan")
        medians.append(med_n)
        print(f"  {pid:<8s}{len(arr):>6d}{med_n:>14.3f}{med_unattr:>20.2f}")

if medians:
    print(f"\n  cross-participant median spread (IQR): "
          f"{np.percentile(medians, 25):.3f} - {np.percentile(medians, 75):.3f}")
    print(f"  cross-participant min/max: "
          f"{min(medians):.3f} / {max(medians):.3f}")
