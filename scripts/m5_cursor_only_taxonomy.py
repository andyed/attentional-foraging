"""M5 — Cursor-only classifier trained on NB22 gaze-regression labels.

The [LAB]->[WILD] bootstrap: take the 2,355 approached non-click episodes,
label each with NB22's gaze_regression_label (1 = deferred, 0 = evaluated-
rejected — the [LAB] eye-tracker ground truth), and train a LOSO logistic
regression on the M4 approach-only feature set to predict that label.

Produces a cursor-only classifier that approximates NB22 and is WILD-
compatible by construction (no position, no dwell, no gaze, no scroll —
just approach kinematics). Its FN rate at the operating threshold is the
paper's hard-negative purity estimate for at-scale mining — the
cleanness you can get from click-log-only inputs after training on LAB
eye-tracker supervision.

Compared to:
  - NB21 classifier-threshold (trained on CLICK, used to split non-clicks
    via Youden-J) → 6.8% FN on hard negatives
  - NB22 gaze-regression rule (uses eye tracker) → 0% FN but [LAB]-only

M5's expected FN rate lives between these two, ideally much closer to 0.

Output:
    scripts/output/m5_cursor_only_taxonomy/summary.json
    scripts/output/m5_cursor_only_taxonomy/results.txt
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix, precision_recall_curve, roc_auc_score, roc_curve,
)
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

FEATURES_JSON_BY_ATTRIBUTION = {
    "absolute": ROOT / "AdSERP/data/cursor-approach-features.json",
    "organic": ROOT / "AdSERP/data/cursor-approach-features-organic.json",
}


def features_path_for(attribution: str, click_buffer_ms: int) -> Path:
    base = FEATURES_JSON_BY_ATTRIBUTION[attribution]
    if click_buffer_ms == 0:
        return base
    return base.with_name(f"{base.stem}-buf{click_buffer_ms}.json")
REG_CACHE_BY_ATTRIBUTION = {
    "absolute": ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json",
    "organic": ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json",
}
OUT_DIR_BY_ATTRIBUTION = {
    "absolute": ROOT / "scripts/output/m5_cursor_only_taxonomy",
    "organic": ROOT / "scripts/output/m5_cursor_only_taxonomy_organic",
}

# Canonical M4 feature set — cursor features minus position, total_dwell_ms,
# and the two structurally-leakage-prone distance terms (final_dist,
# retreat_dist) screened out by the click-buffer protocol of §3.4.
M4_CANONICAL_FEATURES = [
    "min_dist",
    "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity",
    "max_approach_velocity",
    "direction_changes",
    "frac_decreasing",
]
# Legacy nine-feature variant retained for direct comparison only; the
# canonical M4 vector above is the leakage-validated set used in §4.1.
M4_LEGACY_FEATURES = M4_CANONICAL_FEATURES + ["final_dist", "retreat_dist"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution", choices=["absolute", "organic"], default="absolute",
                        help="AOI attribution mode. 'absolute' = legacy band/h3 (default); "
                             "'organic' = bbox-extracted organic AOIs (2026-05-01 cascade).")
    parser.add_argument("--click-buffer-ms", type=int, default=0,
                        help="Click-buffer Δ used for the underlying feature file.")
    parser.add_argument("--feature-set", choices=["canonical", "legacy"], default="canonical",
                        help="canonical = 7 leakage-validated features (paper headline); "
                             "legacy = 9-feature variant including final_dist, retreat_dist.")
    args = parser.parse_args()

    feature_list = M4_CANONICAL_FEATURES if args.feature_set == "canonical" else M4_LEGACY_FEATURES
    features_json = features_path_for(args.attribution, args.click_buffer_ms)
    reg_cache = REG_CACHE_BY_ATTRIBUTION[args.attribution]
    out_dir = OUT_DIR_BY_ATTRIBUTION[args.attribution]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"M5 — Cursor-only classifier ({args.attribution} attribution)")
    print("=" * 70)

    print(f"\nloading {features_json}")
    raw = json.load(open(features_json))
    n = len(raw)
    print(f"  total records: {n}  (click_buffer_ms={args.click_buffer_ms}, "
          f"feature_set={args.feature_set})")

    # Regression labels are derived from gaze events in NB22 and are
    # independent of the click-buffer. The cache is positional w.r.t. the
    # canonical (buf=0) features file; for buffered files, look up by
    # (trial_id, position) instead since record ordering can shift when
    # trials lose all fixations to truncation.
    canonical_features_json = FEATURES_JSON_BY_ATTRIBUTION[args.attribution]
    canonical_raw = json.load(open(canonical_features_json))
    cache_array = np.array(json.load(open(reg_cache)), dtype=bool)
    assert len(cache_array) == len(canonical_raw)
    label_by_key = {
        (r["trial_id"], r["position"]): bool(cache_array[i])
        for i, r in enumerate(canonical_raw)
    }
    regression_labels = np.array(
        [label_by_key.get((r["trial_id"], r["position"]), False) for r in raw],
        dtype=bool,
    )
    print(f"  gaze_regression_label (cached from NB22): "
          f"{regression_labels.sum():,} True ({regression_labels.mean() * 100:.1f}%)")

    min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
    was_clicked = np.array([r["was_clicked"] for r in raw], dtype=bool)
    approached = min_dist < 100

    # ── Target population: approached non-click episodes (the 2,355) ──
    subset_mask = approached & ~was_clicked
    n_subset = int(subset_mask.sum())
    n_deferred = int((subset_mask & regression_labels).sum())
    n_eval_rej = int((subset_mask & ~regression_labels).sum())
    print(f"\nTarget population (approached AND NOT clicked): {n_subset:,}")
    print(f"  deferred   (NB22 gaze_regression = True):  {n_deferred:,} ({n_deferred / n_subset * 100:.1f}%)")
    print(f"  eval-rej   (NB22 gaze_regression = False): {n_eval_rej:,} ({n_eval_rej / n_subset * 100:.1f}%)")

    # ── Build feature matrix (M4 set, approach only) ──
    X_rows = []
    for r in raw:
        row = []
        for f in feature_list:
            v = r.get(f, 0.0)
            if v is None:
                v = 0.0
            row.append(float(v))
        X_rows.append(row)
    X_all = np.array(X_rows)

    # Restrict to target population
    X = X_all[subset_mask]
    y = regression_labels[subset_mask].astype(int)  # 1 = deferred, 0 = eval-rej
    groups = np.array([r["trial_id"].split("-")[0] for r in raw])[subset_mask]

    print(f"\nfeature matrix: {X.shape}  (features = {feature_list})")
    print(f"participants (LOSO groups): {len(set(groups))}")

    # ── LOSO logistic regression ──
    print(f"\nrunning LOSO logistic regression ({len(set(groups))} folds)...")
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            max_iter=5000, class_weight="balanced", C=1.0
        )),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]

    # ── Headline metric: AUC ──
    auc = float(roc_auc_score(y, y_proba))
    print(f"\nLOSO AUC (deferred vs eval-rejected, cursor-only M4 features): {auc:.4f}")

    # Per-participant AUC for stability check
    per_user = {}
    for g in set(groups):
        m = groups == g
        if len(set(y[m])) == 2:
            per_user[g] = float(roc_auc_score(y[m], y_proba[m]))
    if per_user:
        vals = np.array(list(per_user.values()))
        print(f"  per-participant AUC: median {np.median(vals):.3f}, "
              f"IQR [{np.percentile(vals, 25):.3f}, {np.percentile(vals, 75):.3f}], "
              f"min {vals.min():.3f}, N users with both classes = {len(vals)}")

    # ── Operating threshold: Youden-J ──
    fpr, tpr, thresholds = roc_curve(y, y_proba)
    j_stats = tpr - fpr
    j_idx = int(np.argmax(j_stats))
    j_threshold = float(thresholds[j_idx])
    print(f"\nYouden-J operating threshold: p* = {j_threshold:.4f}")
    print(f"  at p*: TPR = {tpr[j_idx]:.3f}, FPR = {fpr[j_idx]:.3f}")

    # Confusion matrix at threshold
    y_pred = (y_proba >= j_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    print(f"\nConfusion matrix at Youden-J:")
    print(f"                   predicted deferred  predicted eval-rej")
    print(f"  deferred (NB22)  {tp:>18d}  {fn:>18d}")
    print(f"  eval-rej (NB22)  {fp:>18d}  {tn:>18d}")
    print(f"\n  precision (deferred) = {precision:.3f}")
    print(f"  recall    (deferred) = {recall:.3f}")
    print(f"  F1        (deferred) = {f1:.3f}")

    # ── Hard-negative mining purity ──
    # Key question for the paper: if we use M5's predicted "eval-rejected"
    # class (p_proba < threshold) as the hard-negative pool for embedding
    # training, what fraction of them are actually NB22-deferred? That's
    # the FN rate analogue on hard negatives.
    pred_neg_mask = (y_proba < j_threshold)
    pred_neg_n = int(pred_neg_mask.sum())
    pred_neg_true_deferred = int((pred_neg_mask & (y == 1)).sum())
    m5_fn_rate = pred_neg_true_deferred / max(pred_neg_n, 1)
    print(f"\n── Hard-negative purity (M5 predicted 'eval-rej' pool) ──")
    print(f"  pool size:                           {pred_neg_n:,}")
    print(f"  of which are NB22-deferred (FN):     {pred_neg_true_deferred:,}")
    print(f"  M5 contamination rate (FN fraction): {m5_fn_rate * 100:.2f}%")
    print(f"  (NB22 ground truth: 0.00% by construction, LAB-only)")
    print(f"  (NB21 classifier-threshold:   6.80% on Peter FN question)")

    # ── Predicted 'deferred' pool also useful for contrastive training ──
    # (a semantically-similar-to-query pool earned by cursor behavior)
    pred_pos_mask = (y_proba >= j_threshold)
    pred_pos_n = int(pred_pos_mask.sum())
    pred_pos_true_deferred = int((pred_pos_mask & (y == 1)).sum())
    m5_deferred_purity = pred_pos_true_deferred / max(pred_pos_n, 1)
    print(f"\n── Deferred pool purity (M5 predicted 'deferred') ──")
    print(f"  pool size:                           {pred_pos_n:,}")
    print(f"  of which are truly NB22-deferred:    {pred_pos_true_deferred:,}")
    print(f"  M5 deferred precision:               {m5_deferred_purity * 100:.2f}%")

    # ── Feature coefficients (standardized, full-data refit) ──
    print(f"\n── Feature coefficients (standardized, full-data refit) ──")
    pipe_full = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            max_iter=5000, class_weight="balanced", C=1.0
        )),
    ])
    pipe_full.fit(X, y)
    coefs = pipe_full.named_steps["lr"].coef_[0]
    intercept = float(pipe_full.named_steps["lr"].intercept_[0])
    scaler = pipe_full.named_steps["scaler"]
    scaler_mean = scaler.mean_.tolist()
    scaler_scale = scaler.scale_.tolist()
    coef_pairs = sorted(
        zip(feature_list, coefs),
        key=lambda p: abs(p[1]), reverse=True,
    )

    # ── Save the full-data model so it can be applied at inference time ──
    model_json = out_dir / "m5_final_model.json"
    json.dump({
        "model": "LogisticRegression(class_weight='balanced', C=1.0) + StandardScaler",
        "trained_on": "all 47 participants, no holdout (full-data refit)",
        "n_episodes": int(len(y)),
        "n_deferred": int((y == 1).sum()),
        "n_eval_rej": int((y == 0).sum()),
        "operating_threshold": float(j_threshold),
        "operating_threshold_method": "Youden-J on LOSO out-of-fold predictions",
        "loso_auc": float(auc),
        "features": list(feature_list),
        "scaler_mean": scaler_mean,
        "scaler_scale": scaler_scale,
        "coefficients_raw": [float(c) for c in coefs],
        "intercept": intercept,
        "apply": "score = sigmoid(sum_i(coef_i * (feat_i - scaler_mean_i) / scaler_scale_i) + intercept); pred_deferred = score >= operating_threshold",
        "regime_for_inference": "WILD-compatible (cursor features only); supervision was [LAB, NB22 gaze-derived]",
    }, open(model_json, "w"), indent=2)
    print(f"wrote {model_json}")
    for name, c in coef_pairs:
        sign = "+" if c >= 0 else "-"
        direction = "→ deferred" if c > 0 else "→ eval-rej"
        print(f"  {name:>30s}  {sign}{abs(c):.3f}  {direction}")

    # ── Write summary JSON ──
    summary = {
        "experiment": "M5 — cursor-only classifier for NB22 taxonomy bootstrap",
        "script": "scripts/m5_cursor_only_taxonomy.py",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "LAB",  # model trained on [LAB] labels; inference is WILD-compatible
        "inference_wild_compatible": True,
        "training_features": feature_list,
        "training_features_note": "M4 approach-only feature set — no position, no total_dwell, no gaze, no scroll. WILD-compatible at inference time.",
        "target_label": "NB22 gaze_regression_label (1 = deferred, 0 = eval-rejected)",
        "target_label_note": "Labels are [LAB]-only (require eye tracker). The classifier learns to approximate them from cursor-only features.",
        "population": {
            "description": "approached non-click episodes from AdSERP",
            "approached_threshold_px": 100,
            "n_total": int(n_subset),
            "n_deferred_nb22": int(n_deferred),
            "n_eval_rej_nb22": int(n_eval_rej),
        },
        "protocol": {
            "model": "LogisticRegression(class_weight='balanced', C=1.0) + StandardScaler",
            "cv": f"GroupKFold by participant, {len(set(groups))} folds (LOSO)",
            "metric_reporting": "AUC on out-of-fold predict_proba; Youden-J for operating threshold",
        },
        "results": {
            "loso_auc": auc,
            "per_participant_auc": {
                "median": float(np.median(list(per_user.values()))) if per_user else None,
                "p25": float(np.percentile(list(per_user.values()), 25)) if per_user else None,
                "p75": float(np.percentile(list(per_user.values()), 75)) if per_user else None,
                "min": float(min(per_user.values())) if per_user else None,
                "n_users_with_both_classes": len(per_user),
            },
            "youden_j_threshold": j_threshold,
            "confusion_matrix_at_youden_j": {
                "tp_deferred_correct": int(tp),
                "fn_deferred_missed": int(fn),
                "fp_eval_rej_flagged_as_deferred": int(fp),
                "tn_eval_rej_correct": int(tn),
            },
            "precision_deferred": float(precision),
            "recall_deferred": float(recall),
            "f1_deferred": float(f1),
        },
        "hard_negative_purity": {
            "question": "If we use M5's predicted 'eval-rejected' pool as the hard-negative training source, what fraction are actually NB22-deferred?",
            "pool_size": int(pred_neg_n),
            "true_deferred_contamination_count": int(pred_neg_true_deferred),
            "m5_fn_rate": float(m5_fn_rate),
            "comparison": {
                "nb21_classifier_threshold_fn_rate": 0.068,
                "nb22_gaze_regression_fn_rate": 0.0,
                "m5_cursor_only_fn_rate": float(m5_fn_rate),
            },
        },
        "deferred_pool_purity": {
            "question": "If we use M5's predicted 'deferred' pool as a semantically-considered-but-declined pool, what fraction are actually NB22-deferred?",
            "pool_size": int(pred_pos_n),
            "true_deferred_count": int(pred_pos_true_deferred),
            "m5_deferred_precision": float(m5_deferred_purity),
        },
        "coefficients_standardized": {
            name: float(c) for name, c in zip(feature_list, coefs)
        },
    }

    out_json = out_dir / "summary.json"
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"\nwrote {out_json}")

    # Also dump a text log
    out_txt = out_dir / "results.txt"
    with open(out_txt, "w") as f:
        f.write(f"M5 — cursor-only classifier trained on NB22 labels\n")
        f.write(f"Generated: {summary['generated']}\n\n")
        f.write(f"Population: {n_subset:,} approached non-click episodes\n")
        f.write(f"  deferred:   {n_deferred:,}\n")
        f.write(f"  eval-rej:   {n_eval_rej:,}\n\n")
        f.write(f"LOSO AUC: {auc:.4f}\n")
        f.write(f"Youden-J threshold: {j_threshold:.4f}\n\n")
        f.write(f"Confusion at Youden-J:\n")
        f.write(f"  TP deferred correct:    {tp}\n")
        f.write(f"  FN deferred missed:     {fn}\n")
        f.write(f"  FP eval-rej flagged:    {fp}\n")
        f.write(f"  TN eval-rej correct:    {tn}\n\n")
        f.write(f"Hard-negative purity (M5 'eval-rejected' pool):\n")
        f.write(f"  size: {pred_neg_n}  contamination: {m5_fn_rate * 100:.2f}%\n")
        f.write(f"  vs NB21 6.80%  vs NB22 0.00% ([LAB]-only)\n\n")
        f.write(f"Coefficients (standardized):\n")
        for name, c in coef_pairs:
            sign = "+" if c >= 0 else "-"
            direction = "-> deferred" if c > 0 else "-> eval-rej"
            f.write(f"  {name:>30s}  {sign}{abs(c):.3f}  {direction}\n")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
