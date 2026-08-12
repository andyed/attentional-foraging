"""Fifth-fixation (early-scan boundary) sensitivity ablation.

Where the "5th fixation" actually lives (investigated 2026-08-12):
  - Paper: 3_method.tex line 64 — "We operationalize the early-scan /
    deliberation boundary at the end of the fifth fixation", and the
    temporal-window ablation claim at 3_method.tex line 63 ("post-fixation-5
    deliberation window reproduces whole-trial M4 performance within fold
    noise (delta = +0.003), whereas the early-scan window collapses to 0.694
    AUC (delta = -0.187)").
  - Code: `scripts/phase_restricted_ablation.py :: SURVEY_END = 5` (lifted
    from notebooks-v2/13_survey_phase.ipynb's OSEC operationalization,
    "saccades 1-5 are survey"). The stored run that the paper's numbers
    match is scripts/output/phase_restricted_ablation/summary_organic.json
    (attribution=organic, feature_set=canonical M4-7): whole = 0.8803,
    post_survey = 0.8836, survey = 0.6938.
  - The headline M4 = 0.847 click model itself is whole-trial and does NOT
    use the fifth fixation; the constant only enters the phase-restricted
    temporal-window ablation (and the OSEC phase narrative).

Sweep: k in {3, 4, 5, 6, 7} for the survey-end fixation index. For each k,
recompute the phase-restricted LOSO AUC for the survey window (t < end of
k-th fixation) and the post-survey window (t >= end of k-th fixation),
under the same protocol as the stored canonical runs (--attribution
organic). Both feature vectors are reported per cell: M4-7 (paper
definition of M4, leakage-corrected) and M4-9 (adds final_dist +
retreat_dist). The module is loaded with --feature-set legacy so
build_feature_matrix emits all nine columns; the M4-7 design matrix is the
corresponding column subset of the same records. The whole-trial window is
k-independent and is computed once as a baseline.

Anchoring caveat (found 2026-08-12): the current script does NOT reproduce
the 2026-05-15 stored summaries, because commit b9084a42 (2026-07-25) added
velocity dt-floor/clamp sanitization to phase_restricted_ablation.py after
they were generated — whole-trial M4-7 is now 0.8906 vs stored 0.8803, so
the paper's 3_method.tex temporal-window numbers are stale relative to the
current canonical extractor. The sweep is anchored self-consistently on the
current script (every cell shares the same extractor and the same LOSO
split), asserts the exact 14,760-record substrate, and records the drift
vs the stored summaries (aborting only if it exceeds 0.02, i.e. beyond
what the velocity guard explains).

Honesty note on record sets: unlike the proximity/anchor sweeps, the record
set necessarily varies with k (trials need > k fixations for a boundary, and
a window with < 2 cursor events is skipped), so n_records is reported per
cell rather than asserted identical.

Output: scripts/output/ablations/fixation_k_ablation.json

Run:
    .venv/bin/python scripts/fixation_k_ablation.py
"""
from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from constant_ablation_common import (  # noqa: E402
    OUT_DIR, PHASE_PATH, load_patched_module, loso_eval_matrix,
    per_trial_ranking_metrics,
)

# Exact source line carrying the constant (verified unique with the comment).
SURVEY_PATTERN = "SURVEY_END = 5  # NB13: saccades 1-5 are Survey phase"

K_SWEEP = [3, 4, 5, 6, 7]
ANCHOR_K = 5

# Stored runs at k = 5, for drift reporting (NOT a hard anchor):
# scripts/output/phase_restricted_ablation/summary_organic.json (M4-7, the
# source of the paper's 3_method.tex temporal-window numbers, generated
# 2026-05-15) and summary_organic_legacy.json (M4-9, same date).
#
# The current phase_restricted_ablation.py does NOT reproduce these stored
# values: commit b9084a42 (2026-07-25) added the velocity dt-floor/clamp
# sanitization (dts floored at 8 ms, velocities clipped to +/-5000 px/s)
# AFTER the stored summaries were generated. On the identical 14,760-record
# organic substrate the current script gives whole-trial M4-7 = 0.8906
# (stored 0.8803) and M4-9 = 0.9199 (stored 0.9312). The k-sweep is
# therefore anchored SELF-CONSISTENTLY on the current script (every cell
# shares the same extractor), and the deltas vs the stored summaries are
# recorded in the output for the paper-staleness audit trail.
STORED_2026_05_15 = {
    "M4_7": {"whole": 0.8803, "post_survey": 0.8836, "survey": 0.6938},
    "M4_9": {"whole": 0.9312, "post_survey": 0.9307, "survey": 0.6937},
}

# Substrate integrity check: the stored runs aligned exactly 14,760 records
# from cursor-approach-features-organic.json. A different count means the
# wrong feature substrate (e.g. the organic_hybrid file or a regenerated
# AOI table) and the sweep must abort.
EXPECTED_N_LAB_RECORDS = 14760
# Sanity ceiling on drift vs the stored summaries: the b9084a42 velocity
# guard explains ~0.010-0.012; anything beyond 0.02 means a second,
# unexplained source of drift.
DRIFT_CEILING = 0.02

OUT_PATH = OUT_DIR / "fixation_k_ablation.json"


def load_phase_module(k: int):
    # phase_restricted_ablation.py parses argv at import time — pin the
    # configuration before exec. feature-set legacy makes
    # build_feature_matrix emit all nine columns; the M4-7 matrix is a
    # column subset of the same build (identical records and values).
    sys.argv = ["phase_restricted_ablation.py",
                "--attribution", "organic", "--feature-set", "legacy"]
    replacements = []
    if k != ANCHOR_K:
        replacements = [(SURVEY_PATTERN,
                         f"SURVEY_END = {k}  # [ablation sweep]")]
    return load_patched_module(PHASE_PATH, replacements, f"phase_k{k}")


def eval_window(mod, lab_records, was_clicked, groups, window: str) -> dict:
    t0 = time.time()
    X9, valid = mod.build_feature_matrix(lab_records, window)
    # M4-7 = column subset of the nine-feature build (same records/values).
    idx7 = [mod.M4_LEGACY.index(f) for f in mod.M4_CANONICAL]
    y = was_clicked[valid].astype(int)
    g = groups[valid]
    recs_valid = [{"trial_id": r["trial_id"], "was_clicked": r["was_clicked"]}
                  for r, v in zip(lab_records, valid) if v]
    out: dict = {"coverage": float(valid.sum() / len(lab_records))}
    for vec, Xv in (("M4_7", X9[valid][:, idx7]), ("M4_9", X9[valid])):
        res = loso_eval_matrix(Xv, y, g)
        proba = res.pop("_proba")
        mrr, ndcg1, n_trials = per_trial_ranking_metrics(recs_valid, proba)
        res["m4_mrr10"] = float(mrr)
        res["m4_ndcg1"] = float(ndcg1)
        res["n_ranked_trials"] = int(n_trials)
        out[vec] = res
        print(f"  window={window:<12s} {vec}  AUC = {res['m4_auc']:.4f}  "
              f"(per-fold {res['per_fold_auc_mean']:.4f} "
              f"+/- {res['per_fold_auc_sd']:.4f}, n_folds={res['n_folds']})  "
              f"n = {res['n_records']:,}")
    print(f"  ({time.time() - t0:.0f}s)")
    return out


def main() -> int:
    print("=" * 72)
    print("Constant-sensitivity ablation C — survey-end fixation index k "
          "(phase-restricted M4-7, organic, canonical)")
    print("=" * 72)

    mod5 = load_phase_module(ANCHOR_K)
    lab_records = json.load(open(mod5.FEATURES_JSON))
    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups = np.array([r["trial_id"].split("-")[0] for r in lab_records])
    print(f"\nloaded {len(lab_records):,} LAB records "
          f"from {mod5.FEATURES_JSON.name}")

    results: dict[str, dict] = {}

    # Substrate integrity: exact record count of the stored canonical runs.
    if len(lab_records) != EXPECTED_N_LAB_RECORDS:
        raise SystemExit(
            f"substrate mismatch: {len(lab_records):,} LAB records, "
            f"expected {EXPECTED_N_LAB_RECORDS:,} "
            f"(cursor-approach-features-organic.json) — wrong feature "
            f"substrate; aborting.")

    # Whole-trial baseline (k-independent) + k=5 cells; drift vs the
    # 2026-05-15 stored summaries is reported, not anchored (see header).
    drift: dict[str, dict[str, float]] = {"M4_7": {}, "M4_9": {}}

    print("\n[whole] k-independent baseline...")
    whole = eval_window(mod5, lab_records, was_clicked, groups, "whole")
    results["whole"] = whole

    print(f"\n[k={ANCHOR_K}] canonical-constant run...")
    k5 = {
        window: eval_window(mod5, lab_records, was_clicked, groups, window)
        for window in ("post_survey", "survey")
    }
    results[f"k{ANCHOR_K}"] = k5

    for vec in ("M4_7", "M4_9"):
        cells = {"whole": whole[vec]["m4_auc"],
                 "post_survey": k5["post_survey"][vec]["m4_auc"],
                 "survey": k5["survey"][vec]["m4_auc"]}
        for window, auc in cells.items():
            d = auc - STORED_2026_05_15[vec][window]
            drift[vec][window] = d
            print(f"  drift vs stored 2026-05-15 {vec} {window}: "
                  f"{auc:.4f} vs {STORED_2026_05_15[vec][window]:.4f} "
                  f"(delta = {d:+.4f}; b9084a42 velocity guard)")
            if abs(d) > DRIFT_CEILING:
                raise SystemExit(
                    f"drift {abs(d):.4f} exceeds ceiling {DRIFT_CEILING} "
                    f"for {vec}/{window} — a second, unexplained drift "
                    f"source beyond the b9084a42 velocity guard; aborting.")

    for k in [k for k in K_SWEEP if k != ANCHOR_K]:
        print(f"\n[k={k}] sweep run...")
        mod = load_phase_module(k)
        results[f"k{k}"] = {
            window: eval_window(mod, lab_records, was_clicked, groups, window)
            for window in ("post_survey", "survey")
        }

    print("\n" + "=" * 78)
    print(f"{'k':>3s}  {'vector':>6s}  {'post-survey AUC':>16s}  "
          f"{'survey AUC':>11s}  {'d_post vs whole':>15s}  "
          f"{'d_survey vs whole':>17s}")
    print("-" * 78)
    for vec in ("M4_7", "M4_9"):
        w = results["whole"][vec]["m4_auc"]
        for k in K_SWEEP:
            r = results[f"k{k}"]
            print(f"{k:>3d}  {vec:>6s}  "
                  f"{r['post_survey'][vec]['m4_auc']:>16.4f}  "
                  f"{r['survey'][vec]['m4_auc']:>11.4f}  "
                  f"{r['post_survey'][vec]['m4_auc'] - w:>+15.4f}  "
                  f"{r['survey'][vec]['m4_auc'] - w:>+17.4f}")
        print(f"     whole-trial {vec} baseline: {w:.4f}")

    payload = {
        "experiment": ("Constant-sensitivity ablation C: survey-end "
                       "fixation index k (early-scan / deliberation "
                       "boundary)"),
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "constant_location": ("phase_restricted_ablation.py :: SURVEY_END "
                              "= 5 (from notebooks-v2/13_survey_phase.ipynb "
                              "OSEC operationalization); paper claim at "
                              "3_method.tex:63-64. The whole-trial M4 = "
                              "0.847 headline does not use this constant."),
        "config": {
            "protocol": ("phase_restricted_ablation.py --attribution "
                         "organic; both M4-7 (canonical) and M4-9 (legacy, "
                         "adds final_dist + retreat_dist) reported per "
                         "cell; 47-fold leave-one-participant-out LR, "
                         "balanced, StandardScaler, C=1.0"),
            "window_defs": {
                "survey": "cursor events with t < end of k-th fixation",
                "post_survey": "cursor events with t >= end of k-th fixation",
                "whole": "full-trial cursor stream (k-independent)",
            },
        },
        "stored_summaries_2026_05_15": STORED_2026_05_15,
        "drift_vs_stored": drift,
        "drift_explanation": ("phase_restricted_ablation.py velocity "
                              "dt-floor/clamp sanitization landed in commit "
                              "b9084a42 (2026-07-25), after the stored "
                              "summaries (2026-05-15); the paper's "
                              "3_method.tex temporal-window numbers "
                              "(delta=+0.003, collapse to 0.694) reflect "
                              "the pre-guard extractor."),
        "k_sweep": K_SWEEP,
        "record_set_note": ("Record sets vary with k by construction "
                            "(boundary requires > k fixations; windows with "
                            "< 2 cursor events are skipped); n_records "
                            "reported per cell."),
        "results": results,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
