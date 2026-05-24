#!/usr/bin/env python3
"""
M3 LOSO logistic regression — diagnostic visualization (not a paper figure).

Three panels:
  (A) Per-fold AUC across 47 participants (LOSO).
  (B) Coefficient stability across folds (per-feature strip plot).
  (C) Predicted-probability density by class with Youden-J operating threshold.

M3 = position + 9 approach features (paper convention).
Source: AdSERP/data/cursor-approach-features-organic.json.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEAT = REPO / "AdSERP/data/cursor-approach-features-organic.json"
OUT = REPO / "scripts/output/figures"
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_9 = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
M3_FEATURES = ["position"] + APPROACH_9


def load() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    records = json.load(open(FEAT))
    y = np.array([r["was_clicked"] for r in records], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in records])
    X = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_FEATURES] for r in records])
    return X, y, groups, M3_FEATURES


def loso_fit(X: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """Run LOSO; return (proba, per_fold_auc, per_fold_coefs, fold_pids)."""
    logo = LeaveOneGroupOut()
    proba = np.zeros_like(y, dtype=float)
    per_fold_auc, per_fold_coefs, fold_pids = [], [], []
    for fold_i, (train_idx, test_idx) in enumerate(logo.split(X, y, groups)):
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
        ])
        pipe.fit(X[train_idx], y[train_idx])
        p = pipe.predict_proba(X[test_idx])[:, 1]
        proba[test_idx] = p
        # Per-fold AUC requires both classes in the held-out fold
        if len(set(y[test_idx])) == 2:
            per_fold_auc.append(roc_auc_score(y[test_idx], p))
        else:
            per_fold_auc.append(np.nan)
        per_fold_coefs.append(pipe.named_steps["lr"].coef_.ravel().copy())
        fold_pids.append(groups[test_idx][0])
    return proba, np.array(per_fold_auc), np.array(per_fold_coefs), fold_pids


def youden_j(y: np.ndarray, proba: np.ndarray) -> float:
    fpr, tpr, thr = roc_curve(y, proba)
    return float(thr[np.argmax(tpr - fpr)])


def render(per_fold_auc, per_fold_coefs, feature_names, y, proba, j_thresh, pooled_auc):
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2),
                             gridspec_kw={"width_ratios": [1.0, 1.4, 1.1]})

    # ── Panel A: per-fold AUC ────────────────────────────────────────
    ax = axes[0]
    aucs = np.sort(per_fold_auc[~np.isnan(per_fold_auc)])
    n = len(aucs)
    ax.scatter(aucs, np.arange(n), s=18, color="#0072B2", alpha=0.85, zorder=3)
    ax.axvline(np.median(aucs), color="#D55E00", lw=1.0, ls="--",
               label=f"median {np.median(aucs):.3f}")
    ax.axvline(np.mean(aucs), color="#009E73", lw=1.0, ls=":",
               label=f"mean {np.mean(aucs):.3f}")
    ax.axvline(pooled_auc, color="#000000", lw=1.0, label=f"pooled {pooled_auc:.3f}")
    ax.axvline(0.5, color="#999999", lw=0.5)
    ax.set_xlabel("AUC")
    ax.set_ylabel("Participant rank")
    ax.set_title(f"(a) Per-fold AUC ({n} participants)", fontsize=10, loc="left")
    ax.set_xlim(0.4, 1.02)
    ax.legend(fontsize=8, loc="lower right", framealpha=0.9)
    ax.grid(axis="x", alpha=0.25)

    # ── Panel B: coefficient stability ───────────────────────────────
    ax = axes[1]
    mean_abs = np.abs(per_fold_coefs).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    pos = np.arange(len(order))
    for j, fi in enumerate(order):
        vals = per_fold_coefs[:, fi]
        ax.scatter(vals, np.full_like(vals, j) + np.random.uniform(-0.12, 0.12, size=len(vals)),
                   s=10, color="#56B4E9", alpha=0.55, zorder=2)
        ax.scatter([np.median(vals)], [j], s=42, color="#D55E00",
                   marker="|", linewidth=2.0, zorder=4)
    ax.axvline(0, color="#555555", lw=0.5)
    ax.set_yticks(pos)
    ax.set_yticklabels([feature_names[fi] for fi in order], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Standardized coefficient (z-units)")
    ax.set_title("(b) Coefficients across 47 LOSO folds", fontsize=10, loc="left")
    ax.grid(axis="x", alpha=0.25)

    # ── Panel C: score density by class + Youden-J ───────────────────
    ax = axes[2]
    bins = np.linspace(0, 1, 41)
    ax.hist(proba[y == 0], bins=bins, color="#999999", alpha=0.55,
            density=True, label=f"non-click (n={int((y==0).sum()):,})")
    ax.hist(proba[y == 1], bins=bins, color="#E69F00", alpha=0.75,
            density=True, label=f"click (n={int((y==1).sum()):,})")
    ax.axvline(j_thresh, color="#000000", lw=1.2, ls="--",
               label=f"Youden-J = {j_thresh:.3f}")
    ax.set_xlabel("Predicted P(click)")
    ax.set_ylabel("Density")
    ax.set_title("(c) Score distribution by class", fontsize=10, loc="left")
    ax.legend(fontsize=8, loc="upper center", framealpha=0.9)
    ax.grid(axis="y", alpha=0.25)

    fig.suptitle(
        f"M3 LOSO LR on AdSERP `[organic]` — pooled AUC {pooled_auc:.3f}, "
        "47-fold leave-one-subject-out, class-balanced",
        fontsize=11, y=1.0,
    )
    fig.tight_layout()
    png = OUT / "m3_loso_diagnostic.png"
    pdf = OUT / "m3_loso_diagnostic.pdf"
    fig.savefig(png, dpi=180, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(f"wrote {png}")
    print(f"wrote {pdf}")


def main() -> None:
    X, y, groups, names = load()
    print(f"n={len(y):,} records, {len(set(groups))} participants, click rate {y.mean():.3f}")
    proba, per_fold_auc, per_fold_coefs, _ = loso_fit(X, y, groups)
    pooled = roc_auc_score(y, proba)
    j = youden_j(y, proba)
    print(f"pooled AUC {pooled:.4f}, Youden-J p={j:.4f}")
    print(f"per-fold AUC: median {np.nanmedian(per_fold_auc):.3f}, "
          f"IQR [{np.nanpercentile(per_fold_auc, 25):.3f}, {np.nanpercentile(per_fold_auc, 75):.3f}], "
          f"std {np.nanstd(per_fold_auc):.3f}")
    render(per_fold_auc, per_fold_coefs, names, y, proba, j, pooled)


if __name__ == "__main__":
    main()
