"""Re-train NB21's M1/M2/M3/M4 LOSO classifiers on cursor-approach-features-organic.

Mirrors NB21 cells 14-20 for the click-prediction LOSO task. Reports
new K3/K4/K5/K6/K9/K10/K11/K12 values for the bbox-attribution era.

Run:
    .venv/bin/python scripts/nb21_loso_retrain_organic.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    f1_score, confusion_matrix,
)
from sklearn.model_selection import LeaveOneGroupOut, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent

FEAT_PATH = ROOT / "AdSERP/data/cursor-approach-features-organic.json"
print(f"Loading {FEAT_PATH.name}", file=sys.stderr)
records = json.load(open(FEAT_PATH))
print(f"  {len(records):,} records", file=sys.stderr)

clicked = np.array([r["was_clicked"] for r in records], dtype=int)
participants = np.array([r["trial_id"].split("-")[0] for r in records])
positions = np.array([r["position"] for r in records])
total_dwell = np.array([r["total_dwell_ms"] for r in records])

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
X4 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in records])

M3_FEATURES = ["position", "total_dwell_ms"] + M4_FEATURES
X3 = np.column_stack([positions.reshape(-1, 1), total_dwell.reshape(-1, 1), X4])
X2 = np.column_stack([positions.reshape(-1, 1), total_dwell.reshape(-1, 1)])
X1 = positions.reshape(-1, 1)


def fit_loso(X, y, groups):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    logo = LeaveOneGroupOut()
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=logo,
                              method="predict_proba", n_jobs=-1)[:, 1]
    auc = roc_auc_score(y, proba)
    ap = average_precision_score(y, proba)
    brier = brier_score_loss(y, proba)
    # Per-fold AUCs
    per_part = []
    for pid in sorted(set(groups)):
        m = groups == pid
        if m.sum() < 10 or len(set(y[m])) < 2:
            continue
        per_part.append((pid, roc_auc_score(y[m], proba[m])))
    pipe.fit(X, y)
    coefs = pipe.named_steps["lr"].coef_.ravel().tolist()
    return {
        "auc": auc, "ap": ap, "brier": brier,
        "per_part_auc": per_part, "coefs": coefs,
    }


def fit_kfold(X, y, k=5):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    kf = KFold(n_splits=k, shuffle=True, random_state=42)
    proba = cross_val_predict(pipe, X, y, cv=kf, method="predict_proba", n_jobs=-1)[:, 1]
    return roc_auc_score(y, proba)


print("\nFitting M1/M2/M3/M4 (LOSO across 47 participants)...", file=sys.stderr)
m1 = fit_loso(X1, clicked, participants)
print(f"  M1 (position only): AUC = {m1['auc']:.3f}", file=sys.stderr)
m2 = fit_loso(X2, clicked, participants)
print(f"  M2 (position + dwell): AUC = {m2['auc']:.3f}", file=sys.stderr)
m3 = fit_loso(X3, clicked, participants)
print(f"  M3 (position + dwell + approach): AUC = {m3['auc']:.3f}", file=sys.stderr)
m4 = fit_loso(X4, clicked, participants)
print(f"  M4 (approach only): AUC = {m4['auc']:.3f}", file=sys.stderr)

print("\nKFold (random) for leakage check...", file=sys.stderr)
m2_kf = fit_kfold(X2, clicked)
m3_kf = fit_kfold(X3, clicked)
m4_kf = fit_kfold(X4, clicked)

per_aucs = sorted(a for _, a in m3["per_part_auc"])
import statistics

print("\n" + "=" * 60)
print("NB21 K-bbox values (organic-attribution LOSO retrain, n=2,701 trials)")
print("=" * 60)
print(f"K1  records / participants / click rate: {len(records):,} / {len(set(participants))} / {100*clicked.mean():.1f}%")
print(f"K3  M3 LOSO AUC: {m3['auc']:.3f} (per-part std {statistics.stdev([a for _, a in m3['per_part_auc']]):.3f})")
print(f"K4  M4 LOSO AUC: {m4['auc']:.3f}")
print(f"K5  M2 LOSO AUC: {m2['auc']:.3f}")
print(f"K6  M1 LOSO AUC: {m1['auc']:.3f}")
print(f"K7  M3 LOSO AP : {m3['ap']:.3f}")
print(f"K8  Leakage Δ (KFold − LOSO):")
print(f"    M2: {m2_kf - m2['auc']:+.3f}, M3: {m3_kf - m3['auc']:+.3f}, M4: {m4_kf - m4['auc']:+.3f}")
print(f"K9  Per-participant LOSO M3 AUC:")
print(f"    median {statistics.median(per_aucs):.3f}, "
      f"IQR [{np.percentile(per_aucs, 25):.3f}, {np.percentile(per_aucs, 75):.3f}], "
      f"range [{min(per_aucs):.3f}, {max(per_aucs):.3f}]")
print(f"K12 Brier score: {m3['brier']:.4f}")

print("\nM3 standardized coefficients:")
for name, coef in zip(M3_FEATURES, m3["coefs"]):
    direction = "→ click" if coef > 0 else "→ skip"
    print(f"  {name:30s}  {coef:+.3f}  {direction}")

# Save full result
out_path = ROOT / "scripts/output/aoi-consumer-cascade/nb21_loso_organic.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps({
    "n_records": len(records),
    "n_participants": int(len(set(participants))),
    "click_rate": float(clicked.mean()),
    "M1_auc": m1["auc"], "M2_auc": m2["auc"],
    "M3_auc": m3["auc"], "M4_auc": m4["auc"],
    "M3_ap": m3["ap"], "M3_brier": m3["brier"],
    "leakage_delta": {
        "M2": m2_kf - m2["auc"],
        "M3": m3_kf - m3["auc"],
        "M4": m4_kf - m4["auc"],
    },
    "M3_per_part_auc": [(p, float(a)) for p, a in m3["per_part_auc"]],
    "M3_features": M3_FEATURES,
    "M3_coefs": m3["coefs"],
}, indent=2))
print(f"\nWrote {out_path}", file=sys.stderr)
