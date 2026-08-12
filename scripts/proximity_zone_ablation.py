"""Proximity-zone width sensitivity ablation.

A natural question is whether the 100 px proximity zone is the right width. The zone
enters the canonical extractor at exactly one point: the local constant
`PROX_THRESHOLD = 100` inside
`compute_cursor_approach_features.compute_approach_features`, which gates
`dwell_in_proximity_ms` (fixation dwell accumulates only while the cursor's
vertical distance to the AOI band center is below the threshold). No other
M4-7 feature reads it.

Sweep: proximityPx in {50, 75, 100, 150, 200}. Everything else is the
canonical Sec. 4.1/5.1 headline protocol (organic_hybrid attribution, 500 ms
click buffer, 47-fold LOSO LR) — see constant_ablation_common.py. Both
feature vectors are reported per value: M4-7 (paper definition of M4,
leakage-corrected) and M4-9 (adds final_dist + retreat_dist; matches
m4_nb21_hybrid_rerun.py's nine-feature M4_FEATURES). The 100 px cell doubles
as the anchor run and must reproduce the canonical AUCs (M4-7 = 0.847,
M4-9 = 0.8671) within +/-0.005 or the sweep aborts.

The swept constant cannot change which (trial, position) records exist —
record identity vs the 100 px run is asserted per value — so AUC differences
are attributable to the zone width alone.

Output: scripts/output/ablations/proximity_zone_ablation.json

Run:
    .venv/bin/python scripts/proximity_zone_ablation.py
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

# Exact source line carrying the constant (verified unique in
# compute_cursor_approach_features.py).
PROX_PATTERN = "    PROX_THRESHOLD = 100  # px"

SWEEP_PX = [50, 75, 100, 150, 200]
ANCHOR_PX = 100  # canonical value; run first as the anchor

OUT_PATH = OUT_DIR / "proximity_zone_ablation.json"


def run_one(px: int) -> tuple[dict, set]:
    replacements = []
    if px != ANCHOR_PX:
        replacements = [(PROX_PATTERN,
                         f"    PROX_THRESHOLD = {px}  # px [ablation sweep]")]
    mod = load_patched_module(CCAF_PATH, replacements, f"ccaf_prox{px}")
    t0 = time.time()
    recs = extract_records(mod.compute_approach_features, f"prox{px}")
    res = m4_loso_eval_both(recs)
    res["proximity_px"] = px
    for vec in ("M4_7", "M4_9"):
        r = res[vec]
        print(f"  prox={px:>3d} px  {vec}  AUC = {r['m4_auc']:.4f}  "
              f"(per-fold {r['per_fold_auc_mean']:.4f} "
              f"+/- {r['per_fold_auc_sd']:.4f}, n_folds={r['n_folds']})  "
              f"MRR@10 = {r['m4_mrr10']:.4f}  n = {r['n_records']:,}")
    print(f"  ({time.time() - t0:.0f}s)")
    return res, record_key_set(recs)


def main() -> int:
    print("=" * 72)
    print("Constant-sensitivity ablation A — proximity-zone width "
          f"(organic_hybrid, buf{CLICK_BUFFER_MS}, M4-7)")
    print("=" * 72)

    results: dict[str, dict] = {}

    # Anchor run first: canonical 100 px must reproduce the headline.
    print(f"\n[{ANCHOR_PX} px] anchor run (canonical constant)...")
    anchor_res, anchor_keys = run_one(ANCHOR_PX)
    anchor_delta = check_anchor(anchor_res["M4_7"]["m4_auc"],
                                label=f"{ANCHOR_PX}px M4-7")
    anchor_delta_9 = check_anchor(anchor_res["M4_9"]["m4_auc"],
                                  canonical=CANONICAL_M4_9_AUC,
                                  label=f"{ANCHOR_PX}px M4-9")
    results[f"{ANCHOR_PX}px"] = anchor_res

    for px in [p for p in SWEEP_PX if p != ANCHOR_PX]:
        print(f"\n[{px} px] sweep run...")
        res, keys = run_one(px)
        if keys != anchor_keys:
            raise SystemExit(
                f"record-set mismatch at {px} px vs anchor "
                f"({len(keys)} vs {len(anchor_keys)}) — zone width should "
                f"not change record identity; aborting.")
        results[f"{px}px"] = res

    print("\n" + "=" * 78)
    print(f"{'proximityPx':>12s}  {'vector':>6s}  {'AUC':>8s}  "
          f"{'fold mean+/-sd':>18s}  {'MRR@10':>8s}  {'dAUC vs 100px':>14s}")
    print("-" * 78)
    for vec in ("M4_7", "M4_9"):
        base = results[f"{ANCHOR_PX}px"][vec]["m4_auc"]
        for px in SWEEP_PX:
            r = results[f"{px}px"][vec]
            print(f"{px:>10d}px  {vec:>6s}  {r['m4_auc']:>8.4f}  "
                  f"{r['per_fold_auc_mean']:>8.4f} +/- "
                  f"{r['per_fold_auc_sd']:.4f}  "
                  f"{r['m4_mrr10']:>8.4f}  {r['m4_auc'] - base:>+14.4f}")

    payload = {
        "experiment": ("Constant-sensitivity ablation A: "
                       "proximity-zone width (dwell_in_proximity_ms gate)"),
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "constant_location": ("compute_cursor_approach_features.py :: "
                              "compute_approach_features :: "
                              "PROX_THRESHOLD (local constant, 100 px)"),
        "feature_dependence": ("Only dwell_in_proximity_ms reads the zone "
                               "width; the other features are independent "
                               "of it."),
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
        "sweep_px": SWEEP_PX,
        "results": results,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
