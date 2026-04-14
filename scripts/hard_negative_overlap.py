"""Compute the overlap between NB21's classifier-threshold hard-negative
definition and NB22's regression-rule hard-negative definition, and
validate the cursor-gaze coupling claim for the Peter/Leif email.

Two hard-negative definitions of "evaluated-rejected" exist in the
four-class taxonomy:

  (a) NB22 regression-rule: min_dist < 100 px AND not clicked AND
      user did NOT scroll-regress back to this position.
  (b) NB21 classifier-threshold: min_dist < 100 px AND not clicked AND
      LOSO M3 p_click <= Youden-J threshold.

The paper should report both. This script quantifies how much the two
definitions agree.

It also dumps the per-record K7/K6 ratio (dwell_in_proximity_ms /
total_dwell_ms) for deferred vs evaluated-rejected under each
definition, so we can sanity-check whether the "cursor parked while
eyes wander" narrative is what the numbers actually support.

Outputs:
  scripts/output/hard_negative_overlap/overlap.json
  scripts/output/hard_negative_overlap/coupling_ratios.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_curve

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/hard_negative_overlap"
OUT.mkdir(parents=True, exist_ok=True)

M3_FEATURES = [
    "position",
    "total_dwell_ms",
    "min_dist",
    "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity",
    "max_approach_velocity",
    "direction_changes",
    "frac_decreasing",
]


def main():
    print(f"loading {FEATURES}")
    raw = json.load(open(FEATURES))
    n = len(raw)
    print(f"records: {n}")

    print(f"loading regression-rule cache from {CACHE}")
    regression_labels = np.array(json.load(open(CACHE)), dtype=bool)
    assert len(regression_labels) == n

    # Build feature matrix for M3. Note: NB21 adds `position` derived
    # from result_band_tops; here we approximate it by reading the
    # `position` field already present in cursor-approach-features.json.
    X_rows = []
    for r in raw:
        row = []
        for f in M3_FEATURES:
            val = r.get(f, 0.0)
            if val is None:
                val = 0.0
            row.append(float(val))
        X_rows.append(row)
    X = np.array(X_rows)
    y = np.array([r["was_clicked"] for r in raw], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in raw])
    min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
    total_dwell = np.array([r["total_dwell_ms"] for r in raw], dtype=float)
    dwell_prox = np.array([r["dwell_in_proximity_ms"] for r in raw], dtype=float)
    retreat = np.array([r["retreat_dist"] for r in raw], dtype=float)

    print(f"features shape: {X.shape}, positive rate: {y.mean():.4f}")
    print(f"unique participants: {len(set(groups))}")

    # LOSO (GroupKFold) with M3 (Pipeline for no leakage)
    n_groups = len(set(groups))
    print(f"running LOSO M3 with {n_groups} folds...")
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced")),
    ])
    gkf = GroupKFold(n_splits=n_groups)
    y_p = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf, method="predict_proba", n_jobs=1
    )[:, 1]

    # Youden-J threshold
    fpr, tpr, thr = roc_curve(y, y_p)
    j = tpr - fpr
    j_idx = int(np.argmax(j))
    j_threshold = float(thr[j_idx])
    print(f"Youden-J threshold: p* = {j_threshold:.4f}")

    # Definitions
    approached = min_dist < 100
    clicked = y == 1

    # (a) regression-rule
    reg_eval_rejected = approached & ~clicked & ~regression_labels
    reg_deferred = approached & ~clicked & regression_labels

    # (b) classifier-threshold
    cls_eval_rejected = approached & ~clicked & (y_p <= j_threshold)
    cls_deferred = approached & ~clicked & (y_p > j_threshold)

    n_reg_rej = int(reg_eval_rejected.sum())
    n_cls_rej = int(cls_eval_rejected.sum())
    n_reg_def = int(reg_deferred.sum())
    n_cls_def = int(cls_deferred.sum())

    print(f"\n=== Evaluated-rejected cohort sizes ===")
    print(f"  regression-rule:     N = {n_reg_rej} ({n_reg_rej/n*100:.1f}% of corpus)")
    print(f"  classifier-threshold: N = {n_cls_rej} ({n_cls_rej/n*100:.1f}% of corpus)")

    # Overlap: records labeled eval-rejected by BOTH definitions
    both_rej = reg_eval_rejected & cls_eval_rejected
    only_reg = reg_eval_rejected & ~cls_eval_rejected
    only_cls = cls_eval_rejected & ~reg_eval_rejected
    either = reg_eval_rejected | cls_eval_rejected

    print(f"\n=== Overlap (eval-rejected set intersection) ===")
    print(f"  Both definitions agree (intersection): {int(both_rej.sum())}")
    print(f"  Only regression-rule:                 {int(only_reg.sum())}")
    print(f"  Only classifier-threshold:             {int(only_cls.sum())}")
    print(f"  Union (either):                       {int(either.sum())}")
    print(f"  Jaccard = |∩| / |∪| = {both_rej.sum() / either.sum():.3f}")
    print(f"  Of NB22 regression-rule set, fraction ALSO classifier-labeled: {both_rej.sum() / n_reg_rej:.3f}")
    print(f"  Of NB21 classifier-threshold set, fraction ALSO regression-labeled: {both_rej.sum() / n_cls_rej:.3f}")

    # Coupling claim: K7/K6 ratio per class
    def _ratio_stats(mask, label):
        tdw = total_dwell[mask]
        pdw = dwell_prox[mask]
        safe = tdw > 0
        ratio = pdw[safe] / tdw[safe]
        print(
            f"  {label:>38s}  N={int(mask.sum()):>5d}  "
            f"K6 med={np.median(tdw):>6.0f}ms  K7 med={np.median(pdw):>6.0f}ms  "
            f"K7/K6 median={np.median(ratio):.3f}  mean={ratio.mean():.3f}"
        )
        return {
            "n": int(mask.sum()),
            "k6_median_ms": float(np.median(tdw)),
            "k7_median_ms": float(np.median(pdw)),
            "k7_over_k6_median": float(np.median(ratio)),
            "k7_over_k6_mean": float(ratio.mean()),
            "retreat_dist_median_px": float(np.median(retreat[mask])),
        }

    print(f"\n=== Cursor-gaze coupling sanity check (K7/K6 ratio) ===")
    print(f"   K7/K6 = dwell_in_proximity_ms / total_gaze_dwell_ms")
    print(f"   Higher = cursor stays near result for a larger fraction of gaze-on-result time")
    print()
    coupling = {
        "regression_rule_deferred": _ratio_stats(reg_deferred, "regression-rule deferred"),
        "regression_rule_rejected": _ratio_stats(reg_eval_rejected, "regression-rule eval-rejected"),
        "classifier_deferred": _ratio_stats(cls_deferred, "classifier-threshold deferred"),
        "classifier_rejected": _ratio_stats(cls_eval_rejected, "classifier-threshold eval-rejected"),
    }

    summary = {
        "youden_j_threshold": j_threshold,
        "cohort_sizes": {
            "regression_rule_deferred": n_reg_def,
            "regression_rule_rejected": n_reg_rej,
            "classifier_threshold_deferred": n_cls_def,
            "classifier_threshold_rejected": n_cls_rej,
            "corpus_total": n,
            "clicked": int(clicked.sum()),
            "approached": int(approached.sum()),
        },
        "overlap": {
            "both_definitions": int(both_rej.sum()),
            "only_regression_rule": int(only_reg.sum()),
            "only_classifier_threshold": int(only_cls.sum()),
            "union": int(either.sum()),
            "jaccard": float(both_rej.sum() / either.sum()),
            "fraction_of_regression_rule_also_classifier": float(
                both_rej.sum() / n_reg_rej
            ) if n_reg_rej else None,
            "fraction_of_classifier_also_regression_rule": float(
                both_rej.sum() / n_cls_rej
            ) if n_cls_rej else None,
        },
        "coupling_k7_over_k6": coupling,
    }

    with open(OUT / "overlap.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {OUT / 'overlap.json'}")


if __name__ == "__main__":
    main()
