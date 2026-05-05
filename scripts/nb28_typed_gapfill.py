"""NB28 viewport bands — typed_gapfill variant.

Mirrors `notebooks-v2/_build_nb28_viewport_bands.py` but reads
cursor-approach-features-typed-gapfill.json and computes viewport_ms_for_trial
against typed_gapfill AOI bands (not absolute-rank equal-interval bands).

Headline metric: LOSO LR AUC for deferred-vs-eval-rejected discrimination on
the approached-non-clicked subset, using viewport-band features.

Regime tag: [LAB, AdSERP, typed_gapfill, NB28]
See: docs/null-findings/2026-05-05-bbox-y-coverage.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import typed_gapfill_aoi_bands  # noqa
from viewport_time_calibration import viewport_ms_for_trial  # noqa

FEATURES = ROOT / "AdSERP" / "data" / "cursor-approach-features-typed-gapfill.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed_gapfill.json"

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def fit_loso(X, y, groups, label):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    n_users = len(set(groups))
    if n_users < 3 or y.sum() < 5 or (len(y) - y.sum()) < 5:
        return None
    gkf = GroupKFold(n_splits=n_users)
    proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf, method="predict_proba", n_jobs=-1
    )[:, 1]
    auc = roc_auc_score(y, proba)
    pipe.fit(X, y)
    coefs = pipe.named_steps["lr"].coef_.ravel().tolist()
    return {"label": label, "auc": auc, "coefs": coefs}


def main():
    print("=" * 72)
    print("NB28 typed_gapfill — viewport bands × deferred-vs-eval-rejected")
    print("=" * 72)

    raw = json.load(open(FEATURES))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    n = len(raw)
    assert len(labels) == n
    print(f"records: {n:,}, deferred=true: {labels.sum():,} ({labels.mean()*100:.1f}%)")

    # Compute viewport_ms per trial against typed_gapfill bands
    trials = sorted({r["trial_id"] for r in raw})
    print(f"computing viewport_ms for {len(trials):,} trials (typed_gapfill bands)...")
    per_trial = {}
    missing = 0
    for i, tid in enumerate(trials):
        gf_bands_full = typed_gapfill_aoi_bands(tid)  # (top, bot, etype)
        if not gf_bands_full:
            missing += 1
            continue
        bands = [(b[0], b[1]) for b in gf_bands_full]
        v = viewport_ms_for_trial(tid, bands=bands)
        if v is None:
            missing += 1
            continue
        per_trial[tid] = v
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(trials)} (missing: {missing})")
    print(f"done. computed: {len(per_trial):,}. missing: {missing}")

    # Augment feature rows with viewport_ms (any/top/mid/bot)
    keep = []
    vt_any, vt_top, vt_mid, vt_bot = [], [], [], []
    for i, r in enumerate(raw):
        tid, pos = r["trial_id"], r["position"]
        if tid not in per_trial:
            continue
        if pos < 0 or pos >= len(per_trial[tid]):
            continue
        a, t, m, b = per_trial[tid][pos]
        keep.append(i)
        vt_any.append(a); vt_top.append(t); vt_mid.append(m); vt_bot.append(b)
    keep = np.array(keep)
    vt_any = np.array(vt_any); vt_top = np.array(vt_top)
    vt_mid = np.array(vt_mid); vt_bot = np.array(vt_bot)
    raw_k = [raw[i] for i in keep]
    labels_k = labels[keep]

    min_dist = np.array([r["min_dist"] for r in raw_k])
    was_clicked = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
    approached = min_dist < 100
    subset = approached & ~was_clicked
    pos_arr = np.array([r["position"] for r in raw_k])
    participants = np.array([r["trial_id"].split("-")[0] for r in raw_k])
    X4 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in raw_k])

    print(f"\nrows after band join:           {len(raw_k):,}")
    print(f"target (approached ∧ ¬clicked): {int(subset.sum()):,}")
    print(f"  deferred:  {int((subset & labels_k).sum()):,}")
    print(f"  eval-rej:  {int((subset & ~labels_k).sum()):,}")

    # Fit per-feature-group classifiers on the subset
    y = labels_k[subset].astype(int)
    g = participants[subset]
    vt_any_col = vt_any[subset].reshape(-1, 1)
    vt_bands_m = np.column_stack([vt_top[subset], vt_mid[subset], vt_bot[subset]])
    x4 = X4[subset]

    print(f"\nLOSO LR — {len(set(g))} folds")
    for X, label in [
        (vt_any_col, "vt_any"),
        (vt_bands_m, "vt_top/mid/bot bands"),
        (x4, "M4 retreat features"),
        (np.hstack([vt_any_col, x4]), "M4 + vt_any"),
        (np.hstack([vt_bands_m, x4]), "M4 + vt_bands"),
    ]:
        out = fit_loso(X, y, g, label)
        if out is None:
            print(f"  {label:<26s}: SKIP (insufficient data)")
        else:
            print(f"  {label:<26s}: AUC = {out['auc']:.4f}")

    # Band-time descriptive stats on the subset
    print("\nBand-time ms distribution, deferred-vs-eval-rejected subset:")
    print(f"  {'band':<6s} {'median':>8s} {'mean':>8s} {'p10':>8s} {'p90':>8s}")
    for name, arr in [("any", vt_any[subset]), ("top", vt_top[subset]),
                      ("mid", vt_mid[subset]), ("bot", vt_bot[subset])]:
        print(f"  {name:<6s} {int(np.median(arr)):>8d} {int(arr.mean()):>8d} "
              f"{int(np.percentile(arr, 10)):>8d} {int(np.percentile(arr, 90)):>8d}")


if __name__ == "__main__":
    main()
