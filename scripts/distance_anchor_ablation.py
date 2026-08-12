"""Distance-anchor sensitivity ablation.

A natural question is why the CENTER of the AOI is a good candidate to define
distances from, rather than e.g. the result's title link.

What the canonical extractor actually anchors to (investigated 2026-08-12):
  - `compute_cursor_approach_features.compute_approach_features` builds
    `result_centers[pos]` as the vertical midpoint between consecutive AOI
    band tops (`(tops[pos] + tops[pos+1]) / 2`). The anchor is center-Y
    ONLY — the geometry is 1-D vertical; AOI x-extent is never used.
  - The anchor feeds 4 of the 7 M4-7 features: dwell_in_proximity_ms
    (cursor-to-anchor distance < 100 px gate) and the three velocity-derived
    features (mean/max_approach_velocity, direction_changes), which
    differentiate the cursor-to-anchor distance. min_dist / mean_dist /
    frac_decreasing are gaze-cursor coupling distances sampled at fixations
    and do not reference the AOI anchor at all.

Link-anchor availability: no title/link sub-geometry exists anywhere in the
dataset. The AllSERP typed AOI exports
(scripts/output/adserp_aois_by_trial_id_typed*.jsonl) carry whole-result
boxes only (top_y, bottom_y, left_x, right_x, center_y — no per-element
title/link boxes), and AdSERP's static SERP HTML cannot be re-rendered to
recover element boxes without headless browser rendering (same limitation
documented in m4_nb21_hybrid_rerun.py). Since the title link renders at the
TOP of a result block, the AOI TOP EDGE is the honest link proxy and is
documented as such in the output.

Sweep (three anchors, everything else canonical Sec. 4.1/5.1 headline —
organic_hybrid, 500 ms click buffer, M4-7, 47-fold LOSO LR):
  - center            (canonical; anchor run, must reproduce M4 AUC 0.847)
  - top_edge          (link proxy: distance measured to tops[pos])
  - nearest_boundary  (distance 0 inside the AOI band
                       [tops[pos], tops[pos+1]), else distance to the
                       nearest band edge)

Anchor choice cannot change which (trial, position) records exist — record
identity vs the center run is asserted per variant.

Output: scripts/output/ablations/distance_anchor_ablation.json

Run:
    .venv/bin/python scripts/distance_anchor_ablation.py
"""
from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from constant_ablation_common import (  # noqa: E402
    ANCHOR_TOL, APPROACH_7, APPROACH_9, ATTRIBUTION, CANONICAL_M4_9_AUC,
    CANONICAL_M4_AUC, CCAF_PATH, CLICK_BUFFER_MS, OUT_DIR, check_anchor,
    extract_records, load_patched_module, m4_loso_eval_both, record_key_set,
)

# ── Exact source blocks carrying the anchor (verified unique) ────────────
CENTER_BLOCK = (
    "        if pos < len(tops) - 1:\n"
    "            center_y = (tops[pos] + tops[pos + 1]) / 2\n"
    "        elif len(tops) > 1:\n"
    "            center_y = tops[pos] + (tops[1] - tops[0]) / 2\n"
    "        else:\n"
    "            center_y = tops[pos] + 100"
)

# top_edge: the anchor point becomes the AOI band's top edge (link proxy).
TOP_EDGE_BLOCK = "        center_y = float(tops[pos])"

# nearest_boundary: the "anchor" becomes the band interval; distance is 0
# inside the band, else distance to the nearest edge. The last band's bottom
# is estimated with the same first-band-height fallback the canonical center
# uses for its half-height offset.
BOUNDARY_BLOCK = (
    "        lo = float(tops[pos])\n"
    "        if pos < len(tops) - 1:\n"
    "            hi = float(tops[pos + 1])\n"
    "        elif len(tops) > 1:\n"
    "            hi = lo + float(tops[1] - tops[0])\n"
    "        else:\n"
    "            hi = lo + 200.0\n"
    "        center_y = (lo, hi)"
)

DIST_CURSOR = "            cursor_to_result = abs(my - result_center_y)"
DIST_BEFORE = "                dist_before = abs(y_before - result_center_y)"
DIST_AFTER = "                dist_after = abs(y_after - result_center_y)"

BOUNDARY_DIST_CURSOR = ("            cursor_to_result = max("
                        "result_center_y[0] - my, my - result_center_y[1], 0.0)")
BOUNDARY_DIST_BEFORE = ("                dist_before = max("
                        "result_center_y[0] - y_before, "
                        "y_before - result_center_y[1], 0.0)")
BOUNDARY_DIST_AFTER = ("                dist_after = max("
                       "result_center_y[0] - y_after, "
                       "y_after - result_center_y[1], 0.0)")

ANCHORS: dict[str, list[tuple[str, str]]] = {
    "center": [],  # canonical — byte-identical extractor
    "top_edge": [(CENTER_BLOCK, TOP_EDGE_BLOCK)],
    "nearest_boundary": [
        (CENTER_BLOCK, BOUNDARY_BLOCK),
        (DIST_CURSOR, BOUNDARY_DIST_CURSOR),
        (DIST_BEFORE, BOUNDARY_DIST_BEFORE),
        (DIST_AFTER, BOUNDARY_DIST_AFTER),
    ],
}

OUT_PATH = OUT_DIR / "distance_anchor_ablation.json"


def run_one(name: str) -> tuple[dict, set]:
    mod = load_patched_module(CCAF_PATH, ANCHORS[name], f"ccaf_anchor_{name}")
    t0 = time.time()
    recs = extract_records(mod.compute_approach_features, name)
    res = m4_loso_eval_both(recs)
    res["anchor"] = name
    for vec in ("M4_7", "M4_9"):
        r = res[vec]
        print(f"  anchor={name:<17s} {vec}  AUC = {r['m4_auc']:.4f}  "
              f"(per-fold {r['per_fold_auc_mean']:.4f} "
              f"+/- {r['per_fold_auc_sd']:.4f}, n_folds={r['n_folds']})  "
              f"MRR@10 = {r['m4_mrr10']:.4f}  n = {r['n_records']:,}")
    print(f"  ({time.time() - t0:.0f}s)")
    return res, record_key_set(recs)


def main() -> int:
    print("=" * 72)
    print("Constant-sensitivity ablation B — AOI distance anchor "
          f"(organic_hybrid, buf{CLICK_BUFFER_MS}, M4-7)")
    print("=" * 72)

    results: dict[str, dict] = {}

    print("\n[center] anchor run (canonical)...")
    center_res, center_keys = run_one("center")
    anchor_delta = check_anchor(center_res["M4_7"]["m4_auc"],
                                label="center M4-7")
    anchor_delta_9 = check_anchor(center_res["M4_9"]["m4_auc"],
                                  canonical=CANONICAL_M4_9_AUC,
                                  label="center M4-9")
    results["center"] = center_res

    for name in ["top_edge", "nearest_boundary"]:
        print(f"\n[{name}] sweep run...")
        res, keys = run_one(name)
        if keys != center_keys:
            raise SystemExit(
                f"record-set mismatch for anchor '{name}' vs center "
                f"({len(keys)} vs {len(center_keys)}) — anchor choice should "
                f"not change record identity; aborting.")
        results[name] = res

    print("\n" + "=" * 78)
    print(f"{'anchor':>18s}  {'vector':>6s}  {'AUC':>8s}  "
          f"{'fold mean+/-sd':>18s}  {'MRR@10':>8s}  {'dAUC vs center':>15s}")
    print("-" * 78)
    for vec in ("M4_7", "M4_9"):
        base = results["center"][vec]["m4_auc"]
        for name in ["center", "top_edge", "nearest_boundary"]:
            r = results[name][vec]
            print(f"{name:>18s}  {vec:>6s}  {r['m4_auc']:>8.4f}  "
                  f"{r['per_fold_auc_mean']:>8.4f} +/- "
                  f"{r['per_fold_auc_sd']:.4f}  "
                  f"{r['m4_mrr10']:>8.4f}  {r['m4_auc'] - base:>+15.4f}")

    payload = {
        "experiment": ("Constant-sensitivity ablation B: "
                       "AOI distance anchor (center vs top-edge/link-proxy "
                       "vs nearest-boundary)"),
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "constant_location": ("compute_cursor_approach_features.py :: "
                              "compute_approach_features :: result_centers "
                              "(vertical midpoint of consecutive AOI band "
                              "tops; 1-D vertical geometry, x never used)"),
        "feature_dependence": ("The anchor feeds dwell_in_proximity_ms and "
                               "the three velocity-derived features (4 of 7 "
                               "M4-7 features); min_dist / mean_dist / "
                               "final_dist / retreat_dist / frac_decreasing "
                               "are gaze-cursor coupling distances and do "
                               "not reference the anchor."),
        "link_anchor_note": ("No title/link sub-geometry exists in AdSERP or "
                             "the AllSERP typed AOI exports (whole-result "
                             "boxes only: top_y/bottom_y/left_x/right_x); "
                             "static SERP HTML cannot be re-rendered for "
                             "element boxes. top_edge (title link renders at "
                             "the top of the result block) is the documented "
                             "link proxy."),
        "config": {
            "attribution": ATTRIBUTION,
            "click_buffer_ms": CLICK_BUFFER_MS,
            "feature_vectors": {"M4_7": APPROACH_7, "M4_9": APPROACH_9},
            "loso": "47-fold LeaveOneGroupOut LR, balanced, StandardScaler, C=1.0",
        },
        "canonical_m4_auc": {"M4_7": CANONICAL_M4_AUC,
                             "M4_9": CANONICAL_M4_9_AUC},
        "anchor_tolerance": ANCHOR_TOL,
        "anchor_delta": {"M4_7": anchor_delta, "M4_9": anchor_delta_9},
        "anchors": list(ANCHORS.keys()),
        "results": results,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
