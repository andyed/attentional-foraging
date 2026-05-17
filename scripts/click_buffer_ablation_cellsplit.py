"""Cell-aware version of click_buffer_ablation.py — the canonical extractor
for paper §4.1 M1=0.668 / M4-7=0.847 headlines.

Builds two views: canonical (parent-only, paper) and cell_aware
(dd_top/dd_right parents replaced by per-cell records from
cursor-approach-features-organic-hybrid-cellsplit-buf500.json).

Runs the same M1 / M2 / M3 / M3-7 / M4-9 / M4-7 variants under
organic_hybrid attribution + buf500 click-buffer. Reports AUC, MRR@10,
NDCG@1 — the paper §4.1 + §4.6 headline metrics.

Run:
    .venv/bin/python scripts/click_buffer_ablation_cellsplit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
)
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
DATA = ROOT / "AdSERP/data"
CANON_PATH = DATA / "cursor-approach-features-organic-hybrid-buf500.json"
CELLSPLIT_PATH = DATA / "cursor-approach-features-organic-hybrid-cellsplit-buf500.json"

APPROACH_9 = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
APPROACH_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def per_trial_ranking_metrics(records, proba):
    by_trial = defaultdict(list)
    for r, p in zip(records, proba):
        by_trial[r["trial_id"]].append((r["was_clicked"], p))
    rrs, ndcg1s = [], []
    for tid, rows in by_trial.items():
        if not any(c for c, _ in rows):
            continue
        rows.sort(key=lambda x: -x[1])
        for rank, (clicked, _) in enumerate(rows, 1):
            if clicked:
                rrs.append(1.0 / rank)
                ndcg1s.append(1.0 if rank == 1 else 0.0)
                break
    return float(np.mean(rrs)), float(np.mean(ndcg1s)), len(rrs)


def fit_eval(X, y, groups, records):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=LeaveOneGroupOut(),
                              method="predict_proba", n_jobs=-1)[:, 1]
    auc = float(roc_auc_score(y, proba))
    ap = float(average_precision_score(y, proba))
    brier = float(brier_score_loss(y, proba))
    mrr, ndcg1, n_trials = per_trial_ranking_metrics(records, proba)
    return {
        "auc": auc, "ap": ap, "brier": brier,
        "mrr_at_10": mrr, "ndcg_at_1": ndcg1, "n_ranked_trials": n_trials,
        "n_records": int(len(records)),
    }


def build_features(records, variant: str):
    positions = np.array([r["position"] for r in records], dtype=float)
    total_dwell = np.array([r.get("total_dwell_ms", 0) or 0 for r in records], dtype=float)
    if variant == "M1":
        return positions.reshape(-1, 1)
    if variant == "M2":
        return np.column_stack([positions, total_dwell])
    if variant == "M3":
        X9 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
        return np.column_stack([positions, total_dwell, X9])
    if variant == "M3-7":
        X7 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
        return np.column_stack([positions, total_dwell, X7])
    if variant == "M4-9":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
    if variant == "M4-7":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
    raise ValueError(variant)


def load_canonical():
    return json.load(open(CANON_PATH))


def load_cellsplit_records():
    d = json.load(open(CELLSPLIT_PATH))
    return d["records"]


def build_cell_aware_view():
    """Return records for cell-aware view: keep organic + native_ad from
    canonical; replace dd_top and dd_right parents with their cells.

    Cell records inherit parent's etype tag (dd_top / dd_right) so
    downstream etype-aware analyses still see them as ads.
    """
    canon = load_canonical()
    cellsplit = load_cellsplit_records()

    # Keep canonical records whose etype is organic or native_ad
    organic_native = [r for r in canon if r.get("etype") in ("organic", "native_ad")]

    # Cell records (role=cell, kind=dd_top_cell or dd_right_cell)
    cells = [r for r in cellsplit if r.get("role") == "cell"
             and r.get("kind") in ("dd_top_cell", "dd_right_cell")]

    # Convert cell records to the same schema as canonical
    cell_records = []
    for c in cells:
        cell_records.append({
            "trial_id": c["trial_id"],
            "position": c.get("position") or 0,
            "was_clicked": bool(c["was_clicked"]),
            "n_fixations": 0,
            "total_dwell_ms": float(c.get("dwell_in_proximity_ms") or 0),
            "click_pos": -1,
            "etype": "dd_top" if c["kind"] == "dd_top_cell" else "dd_right",
            "min_dist": c.get("min_dist") if c.get("min_dist") is not None else 999.0,
            "mean_dist": c.get("mean_dist") if c.get("mean_dist") is not None else 999.0,
            "final_dist": c.get("final_dist") if c.get("final_dist") is not None else 999.0,
            "retreat_dist": c.get("retreat_dist") if c.get("retreat_dist") is not None else 0,
            "dwell_in_proximity_ms": float(c.get("dwell_in_proximity_ms") or 0),
            "mean_approach_velocity": float(c.get("mean_approach_velocity") or 0),
            "max_approach_velocity": float(c.get("max_approach_velocity") or 0),
            "direction_changes": int(c.get("direction_changes") or 0),
            "frac_decreasing": float(c.get("frac_decreasing") if c.get("frac_decreasing") is not None else 0.5),
        })
    return organic_native + cell_records


def run_view(view_name: str, records: list[dict]):
    y = np.array([r["was_clicked"] for r in records], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in records])
    print(f"\n=== {view_name}  n={len(records)}  pos={y.sum()} ===", file=sys.stderr)
    results = {}
    for variant in ["M1", "M2", "M3", "M3-7", "M4-9", "M4-7"]:
        X = build_features(records, variant)
        r = fit_eval(X, y, groups, records)
        results[variant] = r
        print(
            f"  {variant:6s}  AUC={r['auc']:.4f}  MRR={r['mrr_at_10']:.3f}  "
            f"NDCG@1={r['ndcg_at_1']:.3f}  n={r['n_records']:,}",
            file=sys.stderr,
        )
    return results


def main():
    print("Loading canonical (parent-only) features...", file=sys.stderr)
    canon = load_canonical()
    print(f"  {len(canon):,} records", file=sys.stderr)

    print("\nLoading cell-aware features...", file=sys.stderr)
    cell_view = build_cell_aware_view()
    print(f"  {len(cell_view):,} records", file=sys.stderr)

    canon_res = run_view("canonical", canon)
    cell_res = run_view("cell_aware", cell_view)

    print("\n" + "=" * 80)
    print("CELL-AWARE EXTENSION OF PAPER §4.1 / §4.6 (canonical extractor)")
    print("=" * 80)
    print(f"{'variant':<10} {'canonical AUC':>14} {'cell-aware AUC':>16} {'Δ':>10} "
          f"{'canon MRR':>12} {'cell MRR':>12} {'Δ':>10}")
    for v in ["M1", "M2", "M3-7", "M4-7"]:
        c = canon_res[v]
        a = cell_res[v]
        print(f"{v:<10} {c['auc']:>14.4f} {a['auc']:>16.4f} {a['auc']-c['auc']:>+10.4f}  "
              f"{c['mrr_at_10']:>12.3f} {a['mrr_at_10']:>12.3f} {a['mrr_at_10']-c['mrr_at_10']:>+10.3f}")

    print("\n[paper headlines]  M1 = 0.668  M4-7 = 0.847")

    out_dir = ROOT / "scripts/output/click_buffer_ablation_cellsplit"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w") as f:
        json.dump({"canonical": canon_res, "cell_aware": cell_res}, f, indent=2)
    print(f"\nSaved {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
