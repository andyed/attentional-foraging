"""M5 calibration diagnostic: answers Peter Dixon-Moses's question
about why DEFERRED is bleeding heavily into EVALUATED_REJECTED in the
AR replay viewer's testbed sample.

Two tests:

(1) **Inference parity.** Apply approach-retreat/scripts/m5_inference.py
    to the same training data M5 was fit on (cursor-approach-features.json
    filtered to the 2,355 approached non-click episodes labeled by NB22's
    gaze regression). Reproduce LOSO AUC ≈ 0.794 and predicted-DEFERRED
    rate close to the 81% prior. If this passes, our inference code is
    correct and the issue is upstream (population skew or feature
    extraction in the viewer).

(2) **Population skew.** Bin all 13,419 NB15 (trial, position) feature
    rows by trial-score decile (joining on trial-scores.csv). Compute
    M5's predicted DEFERRED rate per decile. If the rate climbs from
    low-score to high-score decile, the issue is sampling bias in the
    AR testbed's top-80 pool, not the model.

Output: scripts/output/m5_calibration/diagnostic.json + summary printed.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_LABELS = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
SCORES = ROOT / "AdSERP/data/trial-scores.csv"
MODEL = ROOT / "scripts/output/m5_cursor_only_taxonomy/m5_final_model.json"
OUT = ROOT / "scripts/output/m5_calibration"

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def m5_predict_proba(feats_arr: np.ndarray, model: dict) -> np.ndarray:
    """Vectorized port of m5_inference.M5Classifier.predict_proba."""
    mean = np.asarray(model["scaler_mean"])
    scale = np.asarray(model["scaler_scale"])
    coef = np.asarray(model["coefficients_raw"])
    intercept = float(model["intercept"])
    z = ((feats_arr - mean) / scale) @ coef + intercept
    return 1.0 / (1.0 + np.exp(-z))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Loading...")
    feats = json.loads(FEATURES.read_text())
    reg = json.loads(REG_LABELS.read_text())
    model = json.loads(MODEL.read_text())
    threshold = model["operating_threshold"]
    assert len(feats) == len(reg), f"feature/label length mismatch: {len(feats)} vs {len(reg)}"

    # ── Test 1: inference parity on the 2,355 approached non-click pop ──
    train_mask = []
    train_X, train_y = [], []
    for f, label in zip(feats, reg):
        approached = f.get("min_dist", 1e9) < 100  # M5 training filter
        is_click = f.get("was_clicked", False)
        if approached and not is_click:
            train_mask.append(True)
            train_X.append([f[k] for k in M4_FEATURES])
            train_y.append(int(bool(label)))
        else:
            train_mask.append(False)
    train_X = np.asarray(train_X, dtype=float)
    train_y = np.asarray(train_y)
    train_p = m5_predict_proba(train_X, model)
    auc_train = roc_auc_score(train_y, train_p)
    pred_def_rate = (train_p >= threshold).mean()
    actual_def_rate = train_y.mean()
    print(f"\n── Test 1: inference parity on M5 training data ──")
    print(f"  pop size: {len(train_y)} (M5 paper: 2,355)")
    print(f"  AUC on this fit: {auc_train:.4f}  (M5 LOSO out-of-fold: 0.794)")
    print(f"  predicted DEFERRED rate at p* = {threshold:.3f}: {pred_def_rate*100:.1f}%")
    print(f"  actual DEFERRED rate (NB22 ground truth): {actual_def_rate*100:.1f}%")

    # ── Test 2: population skew across full corpus by trial-score decile ──
    # Load trial scores, compute decile bin per trial
    score_rows = list(csv.DictReader(SCORES.open()))
    score_by_trial = {r["trial_id"]: float(r["score"]) for r in score_rows}
    sorted_scores = sorted(score_by_trial.values())
    n = len(sorted_scores)
    decile_edges = [sorted_scores[min(n - 1, int(n * i / 10))] for i in range(11)]
    decile_edges[-1] = max(sorted_scores) + 1e-9
    def decile_of(s):
        for i in range(10):
            if s < decile_edges[i + 1]:
                return i
        return 9

    # Apply M5 to ALL approached organic rows (regardless of click), grouped by score decile
    decile_X: dict[int, list] = defaultdict(list)
    decile_y: dict[int, list] = defaultdict(list)  # ground-truth where available
    decile_clicked: dict[int, int] = defaultdict(int)
    for f, label in zip(feats, reg):
        if f.get("min_dist", 1e9) >= 100:
            continue  # not approached
        if f["trial_id"] not in score_by_trial:
            continue
        d = decile_of(score_by_trial[f["trial_id"]])
        x = [f[k] for k in M4_FEATURES]
        decile_X[d].append(x)
        if not f.get("was_clicked", False):
            decile_y[d].append(int(bool(label)))
        else:
            decile_clicked[d] += 1

    print(f"\n── Test 2: population skew by trial-score decile ──")
    print(f"  {'decile':>6} {'n_apr':>6} {'n_clk':>5} {'pred_DEF%':>10} {'actual_DEF%(non-click)':>22}")
    decile_table = []
    for d in range(10):
        if d not in decile_X:
            continue
        X = np.asarray(decile_X[d], dtype=float)
        p = m5_predict_proba(X, model)
        pred_def = (p >= threshold).mean()
        actual_def = np.mean(decile_y[d]) if decile_y[d] else float("nan")
        n_apr = len(X)
        n_clk = decile_clicked[d]
        print(f"  {d:>6} {n_apr:>6} {n_clk:>5} {pred_def*100:>10.1f} {actual_def*100:>22.1f}")
        decile_table.append({
            "decile": d, "n_approached": n_apr, "n_clicked": n_clk,
            "predicted_deferred_rate": float(pred_def),
            "actual_deferred_rate_non_click": float(actual_def) if decile_y[d] else None,
            "score_band": [decile_edges[d], decile_edges[d + 1]],
        })

    out_json = OUT / "diagnostic.json"
    out_json.write_text(json.dumps({
        "test_1_inference_parity": {
            "n_episodes": int(len(train_y)),
            "auc_on_full_data_refit": float(auc_train),
            "loso_auc_published": 0.794,
            "predicted_deferred_rate": float(pred_def_rate),
            "actual_deferred_rate": float(actual_def_rate),
            "operating_threshold": float(threshold),
        },
        "test_2_population_skew": decile_table,
    }, indent=2))
    print(f"\nwrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
