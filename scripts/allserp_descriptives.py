"""AllSERP §3+§4 descriptives — per-etype counts under typed attribution.

Whole-corpus, per-etype, [LAB, AdSERP, typed]. Three numbers in one pass:

  (1) regressive share — of fixated AOIs of etype E, what fraction were
      gaze-revisited regressively at least once? (gaze_regression_label
      semantics from NB22, lifted to typed bbox AOIs.)
  (2) click share — n_clicks per etype, both as raw count and as %
      of all clicks. Click is any click_y/click_x falling inside an AOI bbox.
  (3) above-fold incidence — fraction of trials in which at least one AOI
      of etype E sits above the initial fold (top_y < screen_height,
      initial scroll = 0).

Output:
  scripts/output/allserp_descriptives/summary.json
  scripts/output/allserp_descriptives/per_etype_table.csv

Tag: [LAB, AdSERP, typed, AllSERP-descriptives]
"""

from __future__ import annotations

import csv
import datetime
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    get_trial_meta, load_fixations, load_mouse_events,
)

import argparse  # noqa: E402

CSV_BY_FLAVOR = {
    "typed": ROOT / "scripts/output/adserp_aois_by_trial_id_typed.csv",
    "typed_gapfill": ROOT / "scripts/output/adserp_aois_by_trial_id_typed_gapfill.csv",
}
OUT_DIR_BY_FLAVOR = {
    "typed": ROOT / "scripts/output/allserp_descriptives",
    "typed_gapfill": ROOT / "scripts/output/allserp_descriptives_gapfill",
}

# Click-attribution tolerance. Typed bboxes are row-projection-tight on visible
# text; many real clicks land on link padding / margin within ~10px of bbox
# edges (audit 2026-05-05). Apply tolerance ONLY to clicks; fixations stay
# strict (gaze has its own spatial slop, no need to compound).
CLICK_X_TOL = 5.0
CLICK_Y_TOL = 10.0


def load_typed_aois(csv_path):
    """Returns: dict trial_id -> list of AOI dicts in display order (rank ascending)."""
    by_trial = defaultdict(list)
    with open(csv_path, newline="") as f:
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


def assign_to_aoi(x, y, aois, x_tol=0.0, y_tol=0.0):
    """Return the rank of the AOI whose bbox contains (x, y), or -1 if none.

    AOIs in typed.csv are non-overlapping by construction (post-CV ad-subtraction
    + display-order spatial join). On the rare overlap, prefer the smaller (more
    specific) AOI.

    With non-zero x_tol/y_tol, the bbox is inflated symmetrically. Used for
    click attribution to capture clicks on link padding / margin just outside
    the row-projected text bbox.
    """
    best_rank = -1
    best_area = float("inf")
    for a in aois:
        in_x = a["left_x"] - x_tol <= x <= a["right_x"] + x_tol
        in_y = a["top_y"] - y_tol <= y <= a["bottom_y"] + y_tol
        if in_x and in_y:
            area = (a["bottom_y"] - a["top_y"]) * (a["right_x"] - a["left_x"])
            if area < best_area:
                best_area = area
                best_rank = a["rank"]
    return best_rank


def process_trial(tid, aois):
    """Return per-AOI dict keyed by rank with click_count, fixation_count,
    regressive_fix_count, distinct_returns. Also returns above-fold flags."""
    meta = get_trial_meta(tid)
    if meta[0] is None:
        return None
    doc_h, scr_h, _ = meta
    try:
        fixations = load_fixations(tid)
    except Exception:
        return None
    if fixations is None or len(fixations) == 0:
        return None
    mouse_data = load_mouse_events(tid)
    if mouse_data is None:
        return None
    _, _, clicks = mouse_data

    # Above-fold-at-start: initial scroll = 0, viewport = [0, scr_h].
    # An AOI is above the initial fold if its top is strictly less than scr_h.
    above_fold = {a["rank"]: (a["top_y"] < scr_h) for a in aois}

    # Click attribution: each click's (x, y) is in page-space.
    # Apply CLICK_X_TOL / CLICK_Y_TOL to capture clicks on link padding outside
    # the row-projected text bbox. Tight (no-tol) variant counted in parallel
    # for the robustness column.
    click_count = Counter()
    click_count_tight = Counter()
    for c in clicks:
        # c is (t, x, y) per data_loader convention
        if len(c) < 3:
            continue
        cx, cy = float(c[1]), float(c[2])
        rank_padded = assign_to_aoi(cx, cy, aois, CLICK_X_TOL, CLICK_Y_TOL)
        if rank_padded >= 0:
            click_count[rank_padded] += 1
        rank_tight = assign_to_aoi(cx, cy, aois, 0.0, 0.0)
        if rank_tight >= 0:
            click_count_tight[rank_tight] += 1

    # Fixation pos sequence + per-AOI fixation count.
    pos_seq = []
    fixation_count = Counter()
    for fix in fixations:
        fy = float(fix["y"]) if isinstance(fix, dict) else float(fix[2])
        fx = float(fix["x"]) if isinstance(fix, dict) else float(fix[1])
        rank = assign_to_aoi(fx, fy, aois)
        if rank >= 0:
            pos_seq.append(rank)
            fixation_count[rank] += 1

    # Regression detection — same algorithm as NB22, lifted to typed AOIs.
    # max_seen tracks highest rank ever visited; visited tracks all ever visited.
    # A regressive fixation: rank in visited AND rank < max_seen.
    # A distinct return: regressive AND last_pos != rank (transition into rank
    # from elsewhere during the regressive regime).
    regressive_fix = Counter()
    distinct_returns = Counter()
    max_seen = -1
    visited = set()
    last_pos = None
    for r in pos_seq:
        if r in visited and r < max_seen:
            regressive_fix[r] += 1
            if last_pos != r:
                distinct_returns[r] += 1
        visited.add(r)
        if r > max_seen:
            max_seen = r
        last_pos = r

    per_aoi = {}
    for a in aois:
        r = a["rank"]
        per_aoi[r] = {
            "etype": a["etype"],
            "above_fold": above_fold[r],
            "click_count": click_count.get(r, 0),
            "click_count_tight": click_count_tight.get(r, 0),
            "fixation_count": fixation_count.get(r, 0),
            "regressive_fix_count": regressive_fix.get(r, 0),
            "distinct_returns": distinct_returns.get(r, 0),
        }
    return per_aoi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flavor", choices=list(CSV_BY_FLAVOR.keys()), default="typed",
        help="typed = legacy tight bboxes; typed_gapfill = midpoint-split applied",
    )
    args = parser.parse_args()

    csv_path = CSV_BY_FLAVOR[args.flavor]
    out_dir = OUT_DIR_BY_FLAVOR[args.flavor]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"loading {args.flavor} AOI CSV from {csv_path.name} ...")
    aois_by_trial = load_typed_aois(csv_path)
    print(f"  {len(aois_by_trial):,} trials, "
          f"{sum(len(v) for v in aois_by_trial.values()):,} AOIs")

    # Per-etype accumulators
    by_etype = defaultdict(lambda: {
        "n_aois": 0,
        "n_fixated": 0,
        "n_clicked_aois": 0,
        "n_clicks": 0,
        "n_clicks_tight": 0,
        "n_with_regressive_fix": 0,
        "n_with_distinct_return": 0,
        "n_above_fold": 0,
        "regressive_fix_total": 0,
        "distinct_returns_total": 0,
    })
    n_trials_with_etype_above_fold = defaultdict(set)

    n_trials_processed = 0
    n_trials_skipped = 0
    trial_ids = sorted(aois_by_trial.keys())
    total_clicks_attributed = 0

    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done:,}/{len(trial_ids):,} trials")
        per_aoi = process_trial(tid, aois_by_trial[tid])
        if per_aoi is None:
            n_trials_skipped += 1
            continue
        n_trials_processed += 1
        for rank, info in per_aoi.items():
            et = info["etype"]
            agg = by_etype[et]
            agg["n_aois"] += 1
            if info["fixation_count"] > 0:
                agg["n_fixated"] += 1
            if info["click_count"] > 0:
                agg["n_clicked_aois"] += 1
                agg["n_clicks"] += info["click_count"]
                total_clicks_attributed += info["click_count"]
            agg["n_clicks_tight"] += info["click_count_tight"]
            if info["regressive_fix_count"] > 0:
                agg["n_with_regressive_fix"] += 1
            if info["distinct_returns"] > 0:
                agg["n_with_distinct_return"] += 1
            if info["above_fold"]:
                agg["n_above_fold"] += 1
                n_trials_with_etype_above_fold[et].add(tid)
            agg["regressive_fix_total"] += info["regressive_fix_count"]
            agg["distinct_returns_total"] += info["distinct_returns"]

    print(f"\nprocessed: {n_trials_processed:,} trials, skipped: {n_trials_skipped}")
    print(f"clicks attributed to typed AOIs: {total_clicks_attributed:,}")

    # Build per-etype table
    rows = []
    grand_clicks = sum(v["n_clicks"] for v in by_etype.values())
    grand_clicks_tight = sum(v["n_clicks_tight"] for v in by_etype.values())
    grand_regressive_fixated_aois = sum(
        v["n_with_regressive_fix"] for v in by_etype.values())
    grand_distinct_return_aois = sum(
        v["n_with_distinct_return"] for v in by_etype.values())

    for etype in sorted(by_etype.keys()):
        agg = by_etype[etype]
        n_aois = agg["n_aois"]
        n_fixated = agg["n_fixated"]
        regressive_share_of_fixated = (
            agg["n_with_regressive_fix"] / n_fixated if n_fixated else 0.0)
        distinct_return_share_of_fixated = (
            agg["n_with_distinct_return"] / n_fixated if n_fixated else 0.0)
        click_share_pct = (
            100.0 * agg["n_clicks"] / grand_clicks if grand_clicks else 0.0)
        click_share_tight_pct = (
            100.0 * agg["n_clicks_tight"] / grand_clicks_tight
            if grand_clicks_tight else 0.0)
        n_trials_above = len(n_trials_with_etype_above_fold[etype])
        above_fold_trial_pct = (
            100.0 * n_trials_above / n_trials_processed if n_trials_processed else 0.0)

        rows.append({
            "etype": etype,
            "n_aois": n_aois,
            "n_fixated": n_fixated,
            "fixated_pct_of_aois": (
                100.0 * n_fixated / n_aois if n_aois else 0.0),
            "n_clicks": agg["n_clicks"],
            "click_share_pct": click_share_pct,
            "n_clicks_tight": agg["n_clicks_tight"],
            "click_share_tight_pct": click_share_tight_pct,
            "n_with_regressive_fix": agg["n_with_regressive_fix"],
            "regressive_share_of_fixated_pct": 100.0 * regressive_share_of_fixated,
            "n_with_distinct_return": agg["n_with_distinct_return"],
            "distinct_return_share_of_fixated_pct": (
                100.0 * distinct_return_share_of_fixated),
            "regressive_fix_total": agg["regressive_fix_total"],
            "regressive_fix_share_of_total_pct": (
                100.0 * agg["regressive_fix_total"]
                / sum(v["regressive_fix_total"] for v in by_etype.values())
                if sum(v["regressive_fix_total"] for v in by_etype.values()) else 0.0),
            "n_trials_with_etype_above_fold": n_trials_above,
            "above_fold_trial_pct": above_fold_trial_pct,
        })

    # Print table
    print("\n" + "=" * 100)
    print("PER-ETYPE DESCRIPTIVES [LAB, AdSERP, typed]")
    print("=" * 100)
    hdr = ("etype", "n_aois", "fix%", "n_clicks", "clk%",
           "reg-share%", "ret-share%", "abf-trial%")
    print(f"{hdr[0]:<18s}{hdr[1]:>8s}{hdr[2]:>7s}{hdr[3]:>10s}"
          f"{hdr[4]:>8s}{hdr[5]:>12s}{hdr[6]:>12s}{hdr[7]:>12s}")
    print("-" * 100)
    for r in rows:
        print(f"{r['etype']:<18s}{r['n_aois']:>8,d}"
              f"{r['fixated_pct_of_aois']:>6.1f}%"
              f"{r['n_clicks']:>10,d}"
              f"{r['click_share_pct']:>7.1f}%"
              f"{r['regressive_share_of_fixated_pct']:>11.1f}%"
              f"{r['distinct_return_share_of_fixated_pct']:>11.1f}%"
              f"{r['above_fold_trial_pct']:>11.1f}%")

    summary = {
        "experiment": "AllSERP §3+§4 per-etype descriptives",
        "regime_tag": "[LAB, AdSERP, typed]",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "click_attribution_tolerance_px": {"x": CLICK_X_TOL, "y": CLICK_Y_TOL},
        "click_attribution_tolerance_rationale": (
            "Typed bboxes are row-projection-tight on visible text; per audit "
            "2026-05-05, ~80% of unattributed clicks (audit_unattributed_clicks.py) "
            "fall within ±10px Y of an organic bbox edge, on link padding. Padded "
            "attribution recovers these. Tight (no-tolerance) numbers reported "
            "alongside as a robustness column."
        ),
        "n_trials_processed": n_trials_processed,
        "n_trials_skipped": n_trials_skipped,
        "total_clicks_attributed_to_typed_aois": total_clicks_attributed,
        "total_clicks_attributed_tight": grand_clicks_tight,
        "regression_definition": (
            "Per-AOI regressive fixation == fixation lands in AOI of rank R "
            "where R was previously visited AND R < max_seen (the highest "
            "rank ever fixated so far). Distinct return == regressive fixation "
            "preceded by a different rank. Lifted from NB22 (gaze_regression_label)."
        ),
        "above_fold_definition": (
            "AOI top_y < screen_height (initial viewport, before any scroll). "
            "Trial-level: at least one AOI of etype E satisfies the criterion."
        ),
        "click_attribution": (
            "Per-trial: click (x, y) in page-space pixels. Assign to the AOI "
            "whose bbox contains (x, y); on overlap, prefer the smaller AOI. "
            "Unattributed clicks (off all bboxes) excluded."
        ),
        "per_etype": rows,
    }
    summary["flavor"] = args.flavor
    summary["regime_tag"] = f"[LAB, AdSERP, {args.flavor}]"
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_dir / 'summary.json'}")

    # Also a flat CSV
    csv_path = out_dir / "per_etype_table.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
