"""NB22 2×2 feature ablation — cursor × viewport on the four-class taxonomy.

Andy 2026-04-19: "four class taxonomy was my focus". The hypothesis is that
viewport + trajectory features improve 4-class classification substantially
beyond cursor-only.

The 2×2:

                    | − Viewport  | + Viewport   |
    ----------------|-------------|--------------|
    − Cursor (M4)   | BASE   (2f) | BASE+VP (8f) |
    + Cursor (M4)   | M3    (11f) | M3+VP  (17f) |

  BASE = [position, total_dwell_ms]  (NB22's minimal frame)
  M3   = BASE + 9 M4 cursor features (NB22 K11, binary AUC 0.859)
  VP   = 6 viewport+trajectory features (NB30 forward-selection optimum)
         vt_any, vt_center_ms, avg_viewport_y, max_overlap_frac,
         min_abs_velocity, n_reversals

Target: 4-class multinomial — clicked / deferred / evaluated-rejected / not-approached
(per NB22 cell 7).

CV: LOSO by participant, 47 folds.
Metrics: macro F1, weighted F1, per-class F1, confusion matrix.
Paired Wilcoxon per-participant for each off-diagonal Δ.

Output: scripts/output/nb22_viewport_2x2/summary.json
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
LAB_RECORDS = ROOT / "AdSERP/data/cursor-approach-features.json"
VP_FEATURES = ROOT / "AdSERP/data/viewport-trajectory-features.json"
REGRESSION_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/nb22_viewport_2x2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_FEATURES = ["position", "total_dwell_ms"]
M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
VP_MINIMAL = [
    "vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac",
    "min_abs_velocity", "n_reversals",
]

CLASS_ORDER = ["not_approached", "evaluated_rejected", "deferred", "clicked"]


def build_four_class_labels(records, regression_labels):
    clicked = np.array([bool(r.get("was_clicked")) for r in records])
    approached = np.array([float(r.get("min_dist", 9999)) < 100 for r in records])
    labels = np.full(len(records), "", dtype="U25")
    labels[clicked] = "clicked"
    labels[~clicked & approached & regression_labels] = "deferred"
    labels[~clicked & approached & ~regression_labels] = "evaluated_rejected"
    labels[~clicked & ~approached] = "not_approached"
    return labels


def extract_features(records, vp_by_key, names):
    X = np.zeros((len(records), len(names)), dtype=float)
    for i, r in enumerate(records):
        for j, name in enumerate(names):
            if name in VP_MINIMAL:
                vp = vp_by_key.get((r["trial_id"], r["position"]), {})
                X[i, j] = float(vp.get(name, 0.0) or 0.0)
            else:
                v = r.get(name)
                X[i, j] = float(v) if v is not None else 0.0
    return X


def loso_multiclass(X, y, groups, classes):
    logo = LeaveOneGroupOut()
    pipe = Pipeline([
        ("scaler", StandardScaler(with_mean=False)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced",
                                   solver="lbfgs")),
    ])
    y_true_all, y_pred_all, groups_all = [], [], []
    per_p_macro_f1: dict[str, float] = {}
    per_p_weighted_f1: dict[str, float] = {}
    per_p_accuracy: dict[str, float] = {}
    per_p_per_class_f1: dict[str, dict[str, float]] = {}

    for fold_i, (train_idx, test_idx) in enumerate(logo.split(X, y, groups)):
        pipe.fit(X[train_idx], y[train_idx])
        pred = pipe.predict(X[test_idx])
        y_true_all.extend(y[test_idx].tolist())
        y_pred_all.extend(pred.tolist())
        groups_all.extend(groups[test_idx].tolist())

        pid = groups[test_idx][0]
        macro = f1_score(y[test_idx], pred, average="macro",
                         labels=classes, zero_division=0)
        weighted = f1_score(y[test_idx], pred, average="weighted",
                            labels=classes, zero_division=0)
        acc = float((y[test_idx] == pred).mean())
        per_class = dict(zip(classes, f1_score(y[test_idx], pred,
                                               average=None, labels=classes,
                                               zero_division=0).tolist()))
        per_p_macro_f1[pid] = macro
        per_p_weighted_f1[pid] = weighted
        per_p_accuracy[pid] = acc
        per_p_per_class_f1[pid] = per_class

    y_true_all = np.array(y_true_all)
    y_pred_all = np.array(y_pred_all)
    rep = classification_report(y_true_all, y_pred_all, labels=classes,
                                output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true_all, y_pred_all, labels=classes).tolist()
    return {
        "pooled_classification_report": rep,
        "confusion_matrix": cm,
        "confusion_matrix_classes": classes,
        "per_participant_macro_f1": per_p_macro_f1,
        "per_participant_weighted_f1": per_p_weighted_f1,
        "per_participant_accuracy": per_p_accuracy,
        "per_participant_per_class_f1": per_p_per_class_f1,
        "pooled_macro_f1": float(rep["macro avg"]["f1-score"]),
        "pooled_weighted_f1": float(rep["weighted avg"]["f1-score"]),
        "pooled_accuracy": float(rep["accuracy"]),
    }


def paired_delta(res_a, res_b, key="per_participant_macro_f1", alternative="greater"):
    a_map, b_map = res_a[key], res_b[key]
    pids = sorted(set(a_map.keys()) & set(b_map.keys()))
    a = np.array([a_map[p] for p in pids])
    b = np.array([b_map[p] for p in pids])
    delta = a - b
    try:
        w = wilcoxon(a, b, alternative=alternative)
        W, p = float(w.statistic), float(w.pvalue)
    except Exception:
        W, p = float("nan"), float("nan")
    return {
        "delta_mean": float(delta.mean()),
        "delta_sd": float(delta.std(ddof=1)) if len(delta) > 1 else 0.0,
        "a_ge_b": int((a >= b).sum()),
        "n": len(pids),
        "W": W, "p": p,
    }


def main():
    print("[load] cursor-approach-features.json")
    records = json.load(open(LAB_RECORDS))
    print(f"       {len(records):,} records")
    print("[load] viewport-trajectory-features.json")
    vp_by_key = {(r["trial_id"], r["position"]): r for r in json.load(open(VP_FEATURES))}
    print(f"       {len(vp_by_key):,} rows")
    print("[load] regression-labels cache")
    regression_labels = np.array(json.load(open(REGRESSION_CACHE)), dtype=bool)
    assert len(regression_labels) == len(records)

    labels = build_four_class_labels(records, regression_labels)
    groups = np.array([r["trial_id"].split("-")[0] for r in records])

    print("\n-- Class distribution --")
    for cls in CLASS_ORDER:
        n = int((labels == cls).sum())
        print(f"  {cls:20s} {n:>6,}  ({100*n/len(labels):.1f}%)")

    cells = {
        "BASE":      BASE_FEATURES,
        "BASE+VP":   BASE_FEATURES + VP_MINIMAL,
        "M3":        BASE_FEATURES + M4_FEATURES,
        "M3+VP":     BASE_FEATURES + M4_FEATURES + VP_MINIMAL,
    }

    results = {}
    for tag, feat_names in cells.items():
        print(f"\n[run] {tag}  ({len(feat_names)} features)")
        X = extract_features(records, vp_by_key, feat_names)
        results[tag] = loso_multiclass(X, labels, groups, CLASS_ORDER)
        r = results[tag]
        print(f"       macro F1 = {r['pooled_macro_f1']:.4f}   "
              f"weighted F1 = {r['pooled_weighted_f1']:.4f}   "
              f"accuracy = {r['pooled_accuracy']:.4f}")
        per_class = r["pooled_classification_report"]
        for cls in CLASS_ORDER:
            c = per_class.get(cls, {"f1-score": float("nan")})
            print(f"         {cls:22s} F1 = {c['f1-score']:.4f}  "
                  f"(precision = {c.get('precision', 0):.3f}  recall = {c.get('recall', 0):.3f})")

    # Paired deltas: cursor effect (with − without) and viewport effect
    print("\n-- Paired per-participant deltas --")
    deltas = {}
    for metric in ("per_participant_macro_f1", "per_participant_weighted_f1", "per_participant_accuracy"):
        print(f"\n  metric: {metric}")
        for a, b, tag in [
            ("M3",     "BASE",    "cursor_effect_no_vp"),
            ("M3+VP",  "BASE+VP", "cursor_effect_with_vp"),
            ("BASE+VP","BASE",    "viewport_effect_no_cursor"),
            ("M3+VP",  "M3",      "viewport_effect_with_cursor"),
            ("M3+VP",  "BASE",    "joint_effect_both_vs_none"),
        ]:
            d = paired_delta(results[a], results[b], key=metric)
            print(f"    {tag:32s}  Δ = {d['delta_mean']:+.4f} ± {d['delta_sd']:.4f}  "
                  f"{d['a_ge_b']:>2d}/{d['n']}  p = {d['p']:.4f}")
            deltas[f"{metric}__{tag}"] = d

    # Summary 2×2 table
    print("\n" + "=" * 64)
    print("2×2 macro F1 / weighted F1 / accuracy")
    print("=" * 64)
    print(f"{'':16s}  {'−viewport':>18s}  {'+viewport':>18s}")
    for row_tag, (no_vp, with_vp) in [
        ("−cursor (BASE)", ("BASE", "BASE+VP")),
        ("+cursor (M3)",   ("M3",   "M3+VP")),
    ]:
        cells_txt = []
        for cell in (no_vp, with_vp):
            r = results[cell]
            cells_txt.append(
                f"{r['pooled_macro_f1']:.4f} / {r['pooled_weighted_f1']:.4f} / {r['pooled_accuracy']:.4f}"
            )
        print(f"{row_tag:16s}  {cells_txt[0]:>18s}  {cells_txt[1]:>18s}")

    # Per-class F1 2×2 for the two interesting minority classes
    print("\n-- Per-class F1 2×2 (deferred & evaluated_rejected) --")
    for cls in ("deferred", "evaluated_rejected", "clicked", "not_approached"):
        print(f"\n  {cls}")
        print(f"  {'':16s}  {'−viewport':>10s}  {'+viewport':>10s}")
        for row_tag, (no_vp, with_vp) in [
            ("−cursor", ("BASE", "BASE+VP")),
            ("+cursor", ("M3",   "M3+VP")),
        ]:
            vs = []
            for cell in (no_vp, with_vp):
                r = results[cell]["pooled_classification_report"]
                vs.append(r[cls]["f1-score"])
            print(f"  {row_tag:16s}  {vs[0]:>10.4f}  {vs[1]:>10.4f}")

    # Save
    summary = {
        "feature_sets": {tag: feat_names for tag, feat_names in cells.items()},
        "class_distribution": {
            cls: int((labels == cls).sum()) for cls in CLASS_ORDER
        },
        "cells": {
            tag: {
                "pooled_macro_f1": r["pooled_macro_f1"],
                "pooled_weighted_f1": r["pooled_weighted_f1"],
                "pooled_accuracy": r["pooled_accuracy"],
                "per_class_f1": {
                    cls: float(r["pooled_classification_report"][cls]["f1-score"])
                    for cls in CLASS_ORDER
                },
                "per_class_precision": {
                    cls: float(r["pooled_classification_report"][cls]["precision"])
                    for cls in CLASS_ORDER
                },
                "per_class_recall": {
                    cls: float(r["pooled_classification_report"][cls]["recall"])
                    for cls in CLASS_ORDER
                },
                "confusion_matrix": r["confusion_matrix"],
                "confusion_matrix_classes": r["confusion_matrix_classes"],
                "per_participant_macro_f1": r["per_participant_macro_f1"],
            }
            for tag, r in results.items()
        },
        "paired_deltas": deltas,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
