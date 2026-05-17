"""Cell-aware vs canonical LOFO (leave-one-feature-out) ablation on M4.

For each of the 7 M4 features, drop it and refit LOSO LR. Report ΔAUC
in both views — canonical (parent-only) and cell-aware (cells for
dd_top/dd_right, parents elsewhere). Companion to m4_cellsplit_loso.py.

Tells us whether cells change WHICH features drive the click signal,
not just the total AUC.

Run:
    .venv/bin/python scripts/m4_cellsplit_lofo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from m4_cellsplit_loso import build_records, M4_FEATURES  # noqa: E402


def fit_auc(X, y, groups):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=LeaveOneGroupOut(),
                              method="predict_proba", n_jobs=-1)[:, 1]
    return float(roc_auc_score(y, proba))


def run(view: str):
    records = build_records(view)
    clicked = np.array([r["was_clicked"] for r in records], dtype=int)
    participants = np.array([r["trial_id"].split("-")[0] for r in records])
    X_full = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in records])

    print(f"\n=== view={view} (n={len(records)}, pos={clicked.sum()}) ===", file=sys.stderr)
    full_auc = fit_auc(X_full, clicked, participants)
    print(f"  Full M4 AUC: {full_auc:.4f}", file=sys.stderr)

    lofo = {}
    for i, fname in enumerate(M4_FEATURES):
        cols = [j for j in range(len(M4_FEATURES)) if j != i]
        X_minus = X_full[:, cols]
        auc = fit_auc(X_minus, clicked, participants)
        delta = auc - full_auc
        lofo[fname] = {"auc_minus": auc, "delta": delta}
        print(f"  drop {fname:<28} AUC={auc:.4f}  Δ={delta:+.4f}", file=sys.stderr)
    return {"view": view, "full_auc": full_auc, "lofo": lofo}


def main():
    canon_lofo = run("canonical")
    cell_lofo = run("cell_aware")

    print("\n" + "=" * 80)
    print("LOFO ΔAUC: canonical vs cell-aware (sorted by canonical |Δ|)")
    print("=" * 80)
    print(f"{'feature':<30} {'canonical Δ':>14} {'cell-aware Δ':>16}  {'rank changed?':>15}")

    # Rank features by |delta| in each view
    def ranked(lofo):
        return sorted(lofo["lofo"].items(), key=lambda kv: -abs(kv[1]["delta"]))

    canon_rank = {f: i for i, (f, _) in enumerate(ranked(canon_lofo))}
    cell_rank = {f: i for i, (f, _) in enumerate(ranked(cell_lofo))}

    for fname, _ in ranked(canon_lofo):
        c = canon_lofo["lofo"][fname]["delta"]
        a = cell_lofo["lofo"][fname]["delta"]
        rank_shift = cell_rank[fname] - canon_rank[fname]
        rank_note = f"{'+' if rank_shift > 0 else ''}{rank_shift}" if rank_shift else "0"
        print(f"{fname:<30} {c:>+14.4f} {a:>+16.4f}  {rank_note:>15}")

    out = {
        "canonical_full_auc": canon_lofo["full_auc"],
        "cell_aware_full_auc": cell_lofo["full_auc"],
        "canonical_lofo": canon_lofo["lofo"],
        "cell_aware_lofo": cell_lofo["lofo"],
    }
    out_path = ROOT / "scripts/output/m4_cellsplit_loso/lofo_summary.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
