"""Minimal-model variant of regaze-without-rehover inference.

Uses only the top four features identified by |standardized coefficient| in
the full-M4 model run (regaze_no_rehover_inference.py):

  1. mean_dist               (+0.571)
  2. dwell_in_proximity_ms   (+0.445)
  3. min_dist                (−0.314)
  4. direction_changes       (+0.238)

If the 4-feature LOPO AUC matches the 9-feature AUC (0.699) within
confidence intervals, the four-feature kit becomes the deployable claim:
"these four cursor-dynamics features alone recover gaze-deliberation
signal even in the cursor-blind population."

Reports both models side by side with a paired-fold test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))
from cursor_arc_prevalence import visit_counts_for_trial  # noqa: E402
from nb22_revisit_count import count_revisits_per_trial  # noqa: E402

OUT_DIR = ROOT / "scripts/output/regaze_no_rehover"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FULL = [
    "min_dist",
    "mean_dist",
    "final_dist",
    "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity",
    "max_approach_velocity",
    "direction_changes",
    "frac_decreasing",
]
MINIMAL_4 = [
    "mean_dist",
    "dwell_in_proximity_ms",
    "min_dist",
    "direction_changes",
]


def build_dataset():
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)
    feat_idx = {(r["trial_id"], r["position"]): r for r in feats}
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Trials: {len(trials):,}")

    cursor_visits_by_trial = {}
    print("Computing cursor visit counts...", flush=True)
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            visits, _ = visit_counts_for_trial(tid)
        except Exception:
            continue
        if visits is None:
            continue
        cursor_visits_by_trial[tid] = visits

    gaze_returns_by_trial = {}
    print("Computing gaze distinct returns...", flush=True)
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            res = count_revisits_per_trial(tid)
        except Exception:
            continue
        if res is None:
            continue
        gaze_returns_by_trial[tid] = res["distinct_returns"]

    X_full_rows = []
    X_min_rows = []
    y = []
    groups = []

    for (tid, pos), row in feat_idx.items():
        if not row["was_clicked"]:
            continue
        if row["min_dist"] >= 100:
            continue
        c_visits = cursor_visits_by_trial.get(tid, {}).get(pos, 0)
        if c_visits != 1:
            continue
        gaze_n = gaze_returns_by_trial.get(tid, {}).get(pos, 0)
        target = 1 if gaze_n >= 1 else 0
        full_vec = [row[k] for k in M4_FULL]
        min_vec = [row[k] for k in MINIMAL_4]
        if any(v is None for v in full_vec):
            continue
        X_full_rows.append(full_vec)
        X_min_rows.append(min_vec)
        y.append(target)
        groups.append(tid.split("-")[0])

    X_full = np.array(X_full_rows, dtype=float)
    X_min = np.array(X_min_rows, dtype=float)
    y = np.array(y, dtype=int)
    groups = np.array(groups)
    return X_full, X_min, y, groups


def lopo_aucs(X, y, groups):
    logo = LeaveOneGroupOut()
    aucs = []
    fold_pids = []
    for tr, te in logo.split(X, y, groups):
        X_tr, X_te = X[tr], X[te]
        y_tr, y_te = y[tr], y[te]
        if len(set(y_tr)) < 2 or len(set(y_te)) < 2:
            aucs.append(np.nan)
            fold_pids.append(groups[te][0])
            continue
        scaler = StandardScaler().fit(X_tr)
        X_tr_s = scaler.transform(X_tr)
        X_te_s = scaler.transform(X_te)
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(X_tr_s, y_tr)
        prob = clf.predict_proba(X_te_s)[:, 1]
        aucs.append(roc_auc_score(y_te, prob))
        fold_pids.append(groups[te][0])
    return np.array(aucs), fold_pids


def main():
    X_full, X_min, y, groups = build_dataset()
    n = len(y)
    n_pos = int(y.sum())
    print(f"\nFilter set: clicked + approached + cursor visit_count == 1")
    print(f"  records: {n:,}")
    print(f"  regaze-without-rehover: {n_pos:,} ({100 * n_pos / n:.1f}%)")
    print(f"  no-regaze single-pass: {n - n_pos:,}")
    print(f"  participants: {len(set(groups))}")

    print("\nFull M4 (9 features) — LOPO LR")
    aucs_full, fold_pids = lopo_aucs(X_full, y, groups)
    valid_full = aucs_full[~np.isnan(aucs_full)]
    print(f"  folds with both classes in test: {len(valid_full)}")
    print(f"  mean AUC: {valid_full.mean():.3f} ± {valid_full.std():.3f}")
    print(f"  median AUC: {np.median(valid_full):.3f}")

    print(f"\nMinimal 4 ({', '.join(MINIMAL_4)}) — LOPO LR")
    aucs_min, _ = lopo_aucs(X_min, y, groups)
    valid_min = aucs_min[~np.isnan(aucs_min)]
    print(f"  folds with both classes in test: {len(valid_min)}")
    print(f"  mean AUC: {valid_min.mean():.3f} ± {valid_min.std():.3f}")
    print(f"  median AUC: {np.median(valid_min):.3f}")

    # Paired-fold comparison.
    paired = [
        (a, b)
        for a, b in zip(aucs_full, aucs_min)
        if not (np.isnan(a) or np.isnan(b))
    ]
    diffs = np.array([a - b for a, b in paired])
    print(f"\nPaired-fold delta (full − minimal): n={len(paired)}")
    print(f"  mean Δ: {diffs.mean():+.4f}")
    print(f"  median Δ: {np.median(diffs):+.4f}")
    print(f"  std Δ: {diffs.std():.4f}")
    print(f"  full > minimal: {(diffs > 0).sum()}/{len(diffs)} folds")
    if len(diffs) >= 10:
        try:
            stat, p = wilcoxon(diffs)
            print(f"  Wilcoxon signed-rank: stat={stat:.2f}, p={p:.4f}")
        except Exception as e:
            print(f"  Wilcoxon failed: {e}")

    # Per-fold worst case for minimal model — to flag participants where
    # the minimal model lost a lot of signal.
    worst_idx = np.argsort(diffs)[-5:]  # top 5 folds where full beat minimal
    print(f"\nTop 5 folds where full M4 beat minimal-4 the most:")
    print(f"{'pid':>8} | {'full':>6} | {'min':>6} | {'Δ':>7}")
    for idx in reversed(worst_idx):
        a, b = paired[idx]
        # Need to map back to pid — use the same order paired was built in
        valid_pids = [
            p for p, a, b in zip(fold_pids, aucs_full, aucs_min)
            if not (np.isnan(a) or np.isnan(b))
        ]
        print(f"{valid_pids[idx]:>8} | {a:.3f} | {b:.3f} | {(a-b):+.3f}")

    # Save.
    summary = {
        "n_records": int(n),
        "n_regaze_without_rehover": int(n_pos),
        "full_m4": {
            "n_features": 9,
            "features": M4_FULL,
            "mean_auc": float(valid_full.mean()),
            "median_auc": float(np.median(valid_full)),
            "std_auc": float(valid_full.std()),
            "n_folds": int(len(valid_full)),
        },
        "minimal_4": {
            "n_features": 4,
            "features": MINIMAL_4,
            "mean_auc": float(valid_min.mean()),
            "median_auc": float(np.median(valid_min)),
            "std_auc": float(valid_min.std()),
            "n_folds": int(len(valid_min)),
        },
        "paired_delta": {
            "mean": float(diffs.mean()),
            "median": float(np.median(diffs)),
            "std": float(diffs.std()),
            "n_folds": int(len(diffs)),
            "full_better_count": int((diffs > 0).sum()),
        },
    }
    out = OUT_DIR / "minimal_4_summary.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
