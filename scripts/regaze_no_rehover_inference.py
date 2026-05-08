"""Can cursor dynamics infer "regaze but not re-hover" — the trials where the
gaze deliberated (regressed back) but the cursor only visited the clicked
result once?

Population:
  - all (trial, position) records that were clicked AND approached
    (min_dist < 100) AND have cursor visit_count == 1 (no cursor reapproach)

Target:
  - 1 if gaze had ≥1 distinct return to this position (regaze-without-rehover)
  - 0 otherwise (single-pass click, no gaze deliberation either)

Features (the canonical M4 nine-feature vector from the AdSERP cursor
extractor — same vector NB21 / NB26 / NB28 use):
  min_dist, mean_dist, final_dist, retreat_dist, dwell_in_proximity_ms,
  mean_approach_velocity, max_approach_velocity, direction_changes,
  frac_decreasing

Model: logistic regression with LOPO (leave-one-participant-out) CV. Reports
overall AUC + per-feature univariate AUC and standardized coefficients.

Output: scripts/output/regaze_no_rehover/summary.json + console table.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
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

M4_FEATURES = [
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


def main():
    # 1. Canonical features file.
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)
    feat_idx = {(r["trial_id"], r["position"]): r for r in feats}
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Trials: {len(trials):,}")

    # 2. Per-trial cursor visit counts (Python AR port).
    cursor_visits_by_trial = {}
    print("Computing cursor visit counts...", flush=True)
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            visits, click_pos = visit_counts_for_trial(tid)
        except Exception:
            continue
        if visits is None:
            continue
        cursor_visits_by_trial[tid] = visits

    # 3. Per-trial gaze distinct-return counts.
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

    # 4. Build the "clicked + approached + cursor visit==1" filter set.
    #    Then label by gaze ≥1 distinct return.
    X_rows = []
    y = []
    groups = []  # participant id for LOPO

    for (tid, pos), row in feat_idx.items():
        if not row["was_clicked"]:
            continue
        if row["min_dist"] >= 100:
            continue  # not approached
        c_visits = cursor_visits_by_trial.get(tid, {}).get(pos, 0)
        if c_visits != 1:
            continue  # we want the "no re-hover" subset only
        gaze_n = gaze_returns_by_trial.get(tid, {}).get(pos, 0)
        target = 1 if gaze_n >= 1 else 0
        feat_vec = [row[k] for k in M4_FEATURES]
        if any(v is None for v in feat_vec):
            continue
        X_rows.append(feat_vec)
        y.append(target)
        groups.append(tid.split("-")[0])

    X = np.array(X_rows, dtype=float)
    y = np.array(y, dtype=int)
    groups = np.array(groups)
    n = len(y)
    n_pos = int(y.sum())
    n_neg = n - n_pos

    print(f"\nFilter set: clicked + approached + cursor visit_count == 1")
    print(f"  records: {n:,}")
    print(f"  regaze-without-rehover (target=1): {n_pos:,} ({100 * n_pos / n:.1f}%)")
    print(f"  no-regaze single-pass (target=0): {n_neg:,} ({100 * n_neg / n:.1f}%)")
    print(f"  participants: {len(set(groups))}")

    if n_pos < 5 or n_neg < 5:
        print("Insufficient class balance — aborting.")
        return

    # 5. Univariate feature AUCs (do they each carry signal?).
    print(f"\nUnivariate AUC per feature (target = gaze regressed without cursor re-hover):")
    print(f"{'feature':>28} | {'AUC':>6} | {'n':>6}")
    print("-" * 50)
    univariate = {}
    for j, name in enumerate(M4_FEATURES):
        col = X[:, j]
        # Higher value of feature → higher predicted target. flip later if needed.
        try:
            auc = roc_auc_score(y, col)
        except Exception:
            auc = float("nan")
        # Symmetric AUC: report direction as max(auc, 1-auc) with sign indicator.
        directional = auc if auc >= 0.5 else 1 - auc
        sign = "+" if auc >= 0.5 else "-"
        univariate[name] = {"auc": auc, "directional": directional, "sign": sign}
        print(f"{name:>28} | {directional:>.3f}{sign} | {n:>6}")

    # 6. LOPO logistic regression with all 9 features.
    logo = LeaveOneGroupOut()
    fold_aucs = []
    fold_coefs = []
    print(f"\nLOPO LR with all {len(M4_FEATURES)} M4 features:")
    for tr, te in logo.split(X, y, groups):
        X_tr, X_te = X[tr], X[te]
        y_tr, y_te = y[tr], y[te]
        if len(set(y_tr)) < 2 or len(set(y_te)) < 2:
            continue
        scaler = StandardScaler().fit(X_tr)
        X_tr_s = scaler.transform(X_tr)
        X_te_s = scaler.transform(X_te)
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(X_tr_s, y_tr)
        prob = clf.predict_proba(X_te_s)[:, 1]
        try:
            fold_aucs.append(roc_auc_score(y_te, prob))
        except Exception:
            pass
        fold_coefs.append(clf.coef_[0].copy())

    fold_aucs = np.array(fold_aucs)
    print(f"  folds with both classes in test: {len(fold_aucs)}")
    print(f"  mean LOPO AUC: {fold_aucs.mean():.3f} ± {fold_aucs.std():.3f}")
    print(f"  median LOPO AUC: {np.median(fold_aucs):.3f}")
    print(f"  min/max: {fold_aucs.min():.3f} / {fold_aucs.max():.3f}")

    # Average standardized coefficients across folds → feature ranking.
    mean_coef = np.mean(fold_coefs, axis=0)
    print(f"\nMean standardized LR coefficient (positive = predicts regaze-without-rehover):")
    print(f"{'feature':>28} | {'coef':>7} | {'|coef|':>7}")
    print("-" * 50)
    coef_ranking = sorted(
        zip(M4_FEATURES, mean_coef), key=lambda r: -abs(r[1])
    )
    for name, coef in coef_ranking:
        print(f"{name:>28} | {coef:>+.3f} | {abs(coef):>.3f}")

    # 7. Save summary.
    summary = {
        "n_records": int(n),
        "n_regaze_without_rehover": int(n_pos),
        "n_single_pass_no_regaze": int(n_neg),
        "n_participants": int(len(set(groups))),
        "lopo_auc_mean": float(fold_aucs.mean()),
        "lopo_auc_std": float(fold_aucs.std()),
        "lopo_auc_median": float(np.median(fold_aucs)),
        "n_folds": int(len(fold_aucs)),
        "univariate_auc": {
            k: {"directional_auc": float(v["directional"]), "sign": v["sign"]}
            for k, v in univariate.items()
        },
        "mean_standardized_coef": {
            k: float(v) for k, v in zip(M4_FEATURES, mean_coef)
        },
        "feature_ranking_by_abs_coef": [
            {"feature": k, "coef": float(v)} for k, v in coef_ranking
        ],
    }
    out = OUT_DIR / "summary.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
