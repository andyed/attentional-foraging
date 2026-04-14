"""Two followup computations for the Peter/Leif email:

1. Peter's false-negative recall question (2026-04-08 call):
   On the approached-and-clicked subset, what fraction does the LOSO M3
   classifier misclassify as "rejected" (p_click below Youden threshold)?
   Report FN rate, TP rate, and confusion matrix restricted to approached.

2. Per-class cursor-gaze coupling statistic:
   For each cursor-approach episode, compute the median Euclidean distance
   between gaze and cursor during the episode window (entry_t → exit_t).
   Split by NB22 regression-rule class (deferred vs evaluated-rejected)
   and test the dissociation. Gives a direct quantitative anchor for
   the §5 mechanism language ("cursor left behind during deferred
   re-evaluation; cursor co-located with gaze during evaluated-rejected
   single-pass dismissal") instead of inferring from K7/K6 dwell ratios.

Outputs:
  scripts/output/followup_peter_leif/summary.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_curve, confusion_matrix

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import load_fixations, load_mouse_events

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/followup_peter_leif"
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

    regression_labels = np.array(json.load(open(CACHE)), dtype=bool)
    assert len(regression_labels) == n

    # Build features for LOSO M3
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

    print(f"\nrunning LOSO M3 (47 folds)...")
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced")),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    y_p = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf, method="predict_proba", n_jobs=1
    )[:, 1]

    fpr, tpr, thr = roc_curve(y, y_p)
    j_idx = int(np.argmax(tpr - fpr))
    j_threshold = float(thr[j_idx])
    print(f"Youden-J threshold: p* = {j_threshold:.4f}")

    # ========================================================
    # PART 1: Peter's FN rate on the approached subset
    # ========================================================
    approached = min_dist < 100

    # Full-corpus confusion matrix at Youden-J
    y_pred_full = (y_p >= j_threshold).astype(int)
    tn_f, fp_f, fn_f, tp_f = confusion_matrix(y, y_pred_full).ravel()
    tpr_full = tp_f / (tp_f + fn_f)
    fnr_full = fn_f / (tp_f + fn_f)  # false NEGATIVE RATE = miss rate

    # Approached-subset confusion matrix
    y_sub = y[approached]
    y_pred_sub = y_pred_full[approached]
    tn_a, fp_a, fn_a, tp_a = confusion_matrix(y_sub, y_pred_sub).ravel()
    tpr_sub = tp_a / (tp_a + fn_a) if (tp_a + fn_a) else 0.0
    fnr_sub = fn_a / (tp_a + fn_a) if (tp_a + fn_a) else 0.0
    precision_sub = tp_a / (tp_a + fp_a) if (tp_a + fp_a) else 0.0

    print("\n" + "=" * 70)
    print("PART 1 — Peter's FN rate question")
    print("=" * 70)
    print(f"Youden-J threshold: p* = {j_threshold:.4f}")
    print()
    print("Full corpus (all 13,419 records):")
    print(f"  TP: {tp_f:>5d}   FN: {fn_f:>5d}   TN: {tn_f:>5d}   FP: {fp_f:>5d}")
    print(f"  TPR (recall): {tpr_full:.3f}")
    print(f"  FN rate (miss rate): {fnr_full:.3f}")
    print()
    n_approached = int(approached.sum())
    print(f"Approached subset (min_dist < 100 px, N = {n_approached}):")
    print(f"  TP: {tp_a:>5d}   FN: {fn_a:>5d}   TN: {tn_a:>5d}   FP: {fp_a:>5d}")
    print(f"  N clicked in subset:   {tp_a + fn_a}")
    print(f"  N non-clicked in subset: {tn_a + fp_a}")
    print(f"  TPR (recall):         {tpr_sub:.4f}")
    print(f"  FN rate (miss rate):  {fnr_sub:.4f}  ← Peter's question")
    print(f"  Precision:            {precision_sub:.4f}")
    print()
    print(f"Interpretation: of {tp_a + fn_a} clicked-and-approached records,")
    print(f"the classifier misses {fn_a} ({fnr_sub*100:.1f}%) as 'rejected'.")
    print(f"On the 2026-04-08 call this was quoted at ~10.3%.")

    # ========================================================
    # PART 2: Per-class cursor-gaze coupling statistic
    # ========================================================
    # For each record, compute median Euclidean gaze-cursor distance during
    # the episode window [entry_t, exit_t]. Cursor positions come from
    # mouse events; gaze positions come from fixations. For each fixation
    # in the window, find the nearest-in-time mouse event and compute
    # distance.

    print("\n" + "=" * 70)
    print("PART 2 — Per-class cursor-gaze coupling")
    print("=" * 70)
    print("computing per-episode median gaze-cursor distance...")

    # Group records by trial for single pass
    records_by_trial = defaultdict(list)
    for i, r in enumerate(raw):
        records_by_trial[r["trial_id"]].append(i)

    coupling_dist = np.full(n, np.nan)

    for n_done, (tid, idxs) in enumerate(records_by_trial.items()):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(records_by_trial)} trials...")
        try:
            fixes = load_fixations(tid)
            events, _, _ = load_mouse_events(tid)
        except Exception:
            continue
        # Filter mouse events to positional only
        mouse_pos = [(e[0], e[2], e[3]) for e in events
                     if e[1] in ("mousemove", "mouseover", "click", "mousedown", "mouseup")]
        if not mouse_pos or not fixes:
            continue
        m_ts = np.array([m[0] for m in mouse_pos], dtype=np.int64)
        m_xs = np.array([m[1] for m in mouse_pos], dtype=float)
        m_ys = np.array([m[2] for m in mouse_pos], dtype=float)

        for idx in idxs:
            r = raw[idx]
            entry = r.get("entry_t")
            exit_ = r.get("exit_t")
            if entry is None or exit_ is None:
                continue
            # Fixations in window
            window_fixes = [f for f in fixes if entry <= f["t"] <= exit_]
            if not window_fixes:
                continue
            dists = []
            for f in window_fixes:
                # Nearest mouse event in time
                pos = int(np.searchsorted(m_ts, f["t"]))
                if pos == 0:
                    j = 0
                elif pos >= len(m_ts):
                    j = len(m_ts) - 1
                else:
                    j = pos if abs(m_ts[pos] - f["t"]) < abs(m_ts[pos - 1] - f["t"]) else pos - 1
                dx = f["x"] - m_xs[j]
                dy = f["y"] - m_ys[j]
                dists.append(float(np.hypot(dx, dy)))
            if dists:
                coupling_dist[idx] = float(np.median(dists))

    valid = ~np.isnan(coupling_dist)
    print(f"\nRecords with valid coupling distance: {int(valid.sum())} of {n}")

    clicked_mask = y == 1
    approached_mask = min_dist < 100
    def_mask = approached_mask & ~clicked_mask & regression_labels
    rej_mask = approached_mask & ~clicked_mask & ~regression_labels
    cli_mask = approached_mask & clicked_mask
    na_mask = ~approached_mask

    def _stats(mask, label):
        m = mask & valid
        vals = coupling_dist[m]
        n_m = int(m.sum())
        if n_m == 0:
            return None
        return {
            "label": label,
            "n": n_m,
            "median_px": float(np.median(vals)),
            "mean_px": float(vals.mean()),
            "p25_px": float(np.percentile(vals, 25)),
            "p75_px": float(np.percentile(vals, 75)),
        }

    classes = {
        "clicked": _stats(cli_mask, "clicked"),
        "deferred_regression_rule": _stats(def_mask, "deferred (regression rule)"),
        "evaluated_rejected_regression_rule": _stats(rej_mask, "evaluated-rejected (regression rule)"),
        "not_approached": _stats(na_mask, "not approached"),
    }
    print(f"\n{'class':>38s}  {'N':>5s}  {'median':>8s}  {'mean':>8s}  {'IQR':>15s}")
    print("-" * 85)
    for key, d in classes.items():
        if d is None:
            continue
        iqr = f"[{d['p25_px']:.0f}, {d['p75_px']:.0f}]"
        print(f"{d['label']:>38s}  {d['n']:>5d}  {d['median_px']:>8.1f}  {d['mean_px']:>8.1f}  {iqr:>15s}")

    # Mann-Whitney: deferred vs evaluated-rejected
    def_vals = coupling_dist[def_mask & valid]
    rej_vals = coupling_dist[rej_mask & valid]
    if len(def_vals) > 2 and len(rej_vals) > 2:
        u, p = stats.mannwhitneyu(def_vals, rej_vals, alternative="two-sided")
        print(f"\nMann-Whitney U (deferred vs eval-rejected): U = {u:.0f}, p = {p:.2e}")
        print(f"  Deferred median cursor-gaze dist: {np.median(def_vals):.1f} px (N = {len(def_vals)})")
        print(f"  Eval-rejected median cursor-gaze dist: {np.median(rej_vals):.1f} px (N = {len(rej_vals)})")
        print(f"  Ratio (deferred / eval-rejected): {np.median(def_vals) / np.median(rej_vals):.2f}")
        mw_result = {
            "mannwhitney_u": float(u),
            "mannwhitney_p": float(p),
            "deferred_median_px": float(np.median(def_vals)),
            "evaluated_rejected_median_px": float(np.median(rej_vals)),
            "n_deferred": len(def_vals),
            "n_evaluated_rejected": len(rej_vals),
        }
    else:
        mw_result = None

    # Write summary
    summary = {
        "youden_j_threshold": j_threshold,
        "part1_peter_fn_rate": {
            "full_corpus": {
                "tp": int(tp_f),
                "fn": int(fn_f),
                "tn": int(tn_f),
                "fp": int(fp_f),
                "tpr": float(tpr_full),
                "fn_rate": float(fnr_full),
            },
            "approached_subset": {
                "n_approached": n_approached,
                "tp": int(tp_a),
                "fn": int(fn_a),
                "tn": int(tn_a),
                "fp": int(fp_a),
                "n_clicked_in_subset": int(tp_a + fn_a),
                "n_non_clicked_in_subset": int(tn_a + fp_a),
                "tpr_recall": float(tpr_sub),
                "fn_rate_miss_rate": float(fnr_sub),
                "precision": float(precision_sub),
            },
        },
        "part2_per_class_coupling": {
            "classes": classes,
            "dissociation_test": mw_result,
        },
    }

    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
