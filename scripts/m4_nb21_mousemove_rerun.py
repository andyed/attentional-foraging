"""Full gaze-clean rerun of M1–M4 click prediction and NB21 taxonomy.

Refits every classifier cited in paper-v3 §4.1 and §4.2 on mousemove-only
features, with no fixation or gaze data at any step. Answers two questions
that the LAB-features version cannot:

  1. Does M4 ≈ M3 hold on mousemove-only features?
     If yes, the "9 task-aware features match the 11-feature baseline"
     headline survives the gaze-contamination removal.
     If no, M4 ≈ M3 becomes a LAB-features-only finding.

  2. Does the NB21 classifier-threshold taxonomy still disagree with
     NB22 ground truth at ~45 % on mousemove features?
     If disagreement rate holds, the M5 vs NB21 label-fidelity
     comparison can be made entirely on gaze-clean cursor data.
     If the rate shifts substantially, the paper's label-fidelity
     story has to be recalibrated.

Reuses compute_mousemove_only_features from m5_mousemove_equivalence.py.

Outputs:
  scripts/output/m4_nb21_mousemove_rerun/summary.json
  scripts/output/m4_nb21_mousemove_rerun/results.txt
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "notebooks-v2"))

# Reuse the mousemove-only feature extractor from Path B v1
from m5_mousemove_equivalence import (
    compute_mousemove_only_features,
    M4_FEATURES,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/m4_nb21_mousemove_rerun"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MM_CACHE = ROOT / "scripts/output/m5_mousemove_equivalence/mousemove_features.json"


def loso_auc(X, y, groups, label):
    """Standard LOSO LR with StandardScaler pipeline; return (auc, y_proba)."""
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            max_iter=5000, class_weight="balanced", C=1.0,
        )),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]
    auc = float(roc_auc_score(y, y_proba))
    print(f"  {label}: LOSO AUC = {auc:.4f}")
    return auc, y_proba


def main():
    print("=" * 70)
    print("Full gaze-clean rerun: M1–M4 + NB21 on mousemove-only features")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"  {n:,} records")

    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)

    # Load cached mousemove-only features (full-trial extractor, Path B v1)
    # If cache exists from the equivalence run, reuse it; otherwise compute.
    if MM_CACHE.exists():
        print(f"\nloading cached mousemove features from {MM_CACHE}")
        mm_records = json.load(open(MM_CACHE))
        mm_index = {(r["trial_id"], r["position"]): r for r in mm_records}
        print(f"  {len(mm_records):,} cached mousemove records")
    else:
        print("\ncomputing mousemove-only features (~4 min)...")
        trial_ids = sorted(set(r["trial_id"] for r in lab_records))
        mm_records = []
        for n_done, tid in enumerate(trial_ids):
            if n_done % 300 == 0:
                print(f"  {n_done}/{len(trial_ids)} trials")
            recs = compute_mousemove_only_features(tid)
            if recs is not None:
                mm_records.extend(recs)
        mm_index = {(r["trial_id"], r["position"]): r for r in mm_records}

    # ── Build mousemove feature matrix aligned to LAB records ──
    print("\nbuilding aligned mousemove feature matrix...")
    X_mm = np.zeros((n, len(M4_FEATURES)), dtype=float)
    position = np.zeros(n, dtype=float)
    valid = np.zeros(n, dtype=bool)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        mm = mm_index.get(key)
        if mm is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X_mm[i, j] = float(mm.get(f, 0) or 0)
        position[i] = float(r["position"])  # position is not gaze-dependent
        valid[i] = True

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    mask = valid
    print(f"  {int(mask.sum()):,} records with mousemove features")

    X_valid = X_mm[mask]
    pos_valid = position[mask].reshape(-1, 1)
    y_valid = was_clicked[mask].astype(int)
    groups_valid = groups_all[mask]

    # ── LOSO classification across four model tiers (mousemove-only) ──
    print("\n── LOSO click prediction on mousemove features ──")
    # M1: position only
    auc_m1, _ = loso_auc(pos_valid, y_valid, groups_valid, "M1 (position)")

    # M2: position + cursor dwell_in_proximity_ms (NOT fixation total_dwell)
    dwell_idx = M4_FEATURES.index("dwell_in_proximity_ms")
    X_m2 = np.column_stack([pos_valid, X_valid[:, dwell_idx]])
    auc_m2, _ = loso_auc(X_m2, y_valid, groups_valid, "M2 (position + cursor dwell)")

    # M4: 9 mousemove approach features (canonical, no position)
    auc_m4, yp_m4 = loso_auc(X_valid, y_valid, groups_valid, "M4 (9 approach features, canonical)")

    # M3 (reference): position + 9 mousemove approach features (10 features)
    X_m3 = np.column_stack([pos_valid, X_valid])
    auc_m3, _ = loso_auc(X_m3, y_valid, groups_valid, "M3 (position + 9 approach, reference)")

    # ── NB21 classifier-threshold taxonomy on mousemove M4 ──
    print("\n── NB21 classifier-threshold (mousemove version) ──")

    # Get click prediction probabilities on approached non-clicks only
    # (the population NB21 partitions)
    min_dist_mm = X_valid[:, M4_FEATURES.index("min_dist")]
    approached_mm = min_dist_mm < 100
    subset_mask = approached_mm & (~y_valid.astype(bool))

    # Youden-J on the full valid population (not just approached non-clicks)
    fpr, tpr, thresholds = roc_curve(y_valid, yp_m4)
    j_idx = int(np.argmax(tpr - fpr))
    j_threshold = float(thresholds[j_idx])
    print(f"  Youden-J threshold (M4 mousemove): p* = {j_threshold:.4f}")

    # Partition approached non-clicks by mousemove M4 prediction
    approached_noclick_idxs = np.where(subset_mask)[0]
    yp_subset = yp_m4[subset_mask]
    nb21_deferred_mm = (yp_subset >= j_threshold)
    n_nb21_deferred = int(nb21_deferred_mm.sum())
    n_nb21_rejected = int((~nb21_deferred_mm).sum())
    print(f"  NB21 mousemove deferred:   {n_nb21_deferred:,}")
    print(f"  NB21 mousemove eval-rej:   {n_nb21_rejected:,}")

    # Compare to NB22 ground truth on the same subset
    nb22_deferred = regression_labels[mask][subset_mask]
    nb21_disagreement = int(np.sum(nb21_deferred_mm != nb22_deferred))
    nb21_disagreement_rate = nb21_disagreement / len(nb22_deferred)
    print(f"\n  NB21 mm vs NB22 disagreement: {nb21_disagreement} / {len(nb22_deferred)} "
          f"= {nb21_disagreement_rate * 100:.1f}%")

    # Jaccard on the deferred class sets
    both_deferred = int(np.sum(nb21_deferred_mm & nb22_deferred))
    either_deferred = int(np.sum(nb21_deferred_mm | nb22_deferred))
    jaccard_def = both_deferred / max(either_deferred, 1)
    print(f"  Deferred Jaccard (NB21-mm vs NB22): {jaccard_def:.3f}")

    # ── Summary table ──
    print("\n" + "=" * 70)
    print("SUMMARY: mousemove-only results vs. LAB-features reference")
    print("=" * 70)
    print(f"\n{'Model':<35s} {'LAB AUC':>10s} {'MM AUC':>10s} {'Δ':>8s}")
    print("-" * 65)
    lab_aucs = {"M1": 0.613, "M2": 0.743, "M3": 0.859, "M4": 0.861}
    for name, mm_auc in [("M1 (position)", auc_m1),
                         ("M2 (position + dwell)", auc_m2),
                         ("M3 (position + approach)", auc_m3),
                         ("M4 (approach only)", auc_m4)]:
        key = name.split()[0]
        lab = lab_aucs[key]
        d = mm_auc - lab
        print(f"{name:<35s} {lab:>10.4f} {mm_auc:>10.4f} {d:>+8.4f}")

    print(f"\nM4 vs M3 equivalence test (mousemove features only):")
    print(f"  M4 AUC: {auc_m4:.4f}")
    print(f"  M3 AUC: {auc_m3:.4f}")
    print(f"  Δ     : {auc_m4 - auc_m3:+.4f}")
    if abs(auc_m4 - auc_m3) < 0.01:
        print(f"  ✓ M4 ≈ M3 holds on mousemove features (|Δ| < 0.01)")
    else:
        print(f"  ✗ M4 ≈ M3 DOES NOT hold on mousemove features")

    print(f"\nNB21 classifier-threshold disagreement vs NB22 ground truth:")
    print(f"  LAB features (paper-v3):       45.4 % (1,070 / 2,355)")
    print(f"  Mousemove features (this run): {nb21_disagreement_rate * 100:.1f} %")
    print(f"  Δ: {(nb21_disagreement_rate - 0.454) * 100:+.1f} pt")

    # ── Persist ──
    summary = {
        "experiment": "Full gaze-clean rerun of M1–M4 + NB21 on mousemove-only features",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_records_valid": int(mask.sum()),
        "click_prediction": {
            "M1_position_only": {
                "lab_features_auc": 0.613,
                "mousemove_features_auc": auc_m1,
                "delta": auc_m1 - 0.613,
            },
            "M2_position_plus_dwell": {
                "lab_features_auc": 0.743,
                "mousemove_features_auc": auc_m2,
                "delta": auc_m2 - 0.743,
                "note": "M2 uses cursor dwell_in_proximity_ms (not fixation total_dwell_ms)",
            },
            "M3_reference_position_plus_approach": {
                "lab_features_auc": 0.859,
                "mousemove_features_auc": auc_m3,
                "delta": auc_m3 - 0.859,
                "n_features": 10,
                "note": "Mousemove M3 drops total_dwell_ms (gaze-gated) and includes position + 9 approach features = 10",
            },
            "M4_canonical_approach_only": {
                "lab_features_auc": 0.861,
                "mousemove_features_auc": auc_m4,
                "delta": auc_m4 - 0.861,
                "n_features": 9,
            },
            "m4_vs_m3_delta_mousemove": float(auc_m4 - auc_m3),
            "m4_approx_m3_on_mousemove": bool(abs(auc_m4 - auc_m3) < 0.01),
        },
        "nb21_classifier_threshold_mousemove": {
            "youden_j_threshold": j_threshold,
            "n_approached_noclick": int(subset_mask.sum()),
            "n_deferred": n_nb21_deferred,
            "n_eval_rejected": n_nb21_rejected,
            "disagreement_vs_nb22": {
                "n_disagreements": nb21_disagreement,
                "n_total": len(nb22_deferred),
                "rate": float(nb21_disagreement_rate),
            },
            "deferred_jaccard_vs_nb22": float(jaccard_def),
            "lab_reference_disagreement_rate": 0.454,
            "delta": float(nb21_disagreement_rate - 0.454),
        },
        "m5_wild_reference_from_path_b_v1": {
            "loso_auc": 0.7064,
            "precision_deferred": 0.881,
            "recall_deferred": 0.793,
            "label_disagreement_vs_nb22": 0.256,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
