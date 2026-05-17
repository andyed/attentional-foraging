"""Cell-aware 3-class LambdaMART LTR vs canonical (paper §4.6 deployable scheme).

The paper's 3-class deployable scheme:
  CLICKED              → 2
  APPROACHED_NOT_CLICKED → 1   (min_dist < 100 px AND not clicked)
  NOT_APPROACHED       → 0    (min_dist ≥ 100 px)

Cursor-derivable end-to-end (no gaze required), so cell-aware port is
direct: each cell gets its own 3-class label from its own min_dist /
was_clicked. Compare ΔMRR vs binary-click baseline in both views.

Headline paper number to beat:
  3-class scheme ΔMRR@10 = +0.051 over binary clicks (deployable)

Run:
    .venv/bin/python scripts/ltr_3class_cellsplit.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from lightgbm import LGBMRanker
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
DATA = ROOT / "AdSERP/data"
CANON_PATH = DATA / "cursor-approach-features-organic-hybrid-buf500.json"
CELLSPLIT_PATH = DATA / "cursor-approach-features-organic-hybrid-cellsplit-buf500.json"

# 7-feature M4 (paper canonical, after leakage screen)
M4_FEATURES = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
# M3-no-position = 8 features (total_dwell + 7 approach) — paper §4.6 spec
LTR_FEATURES = ["total_dwell_ms"] + M4_FEATURES

APPROACH_THRESHOLD_PX = 100


def label_3class(rec):
    if rec.get("was_clicked"):
        return 2
    if float(rec.get("min_dist", 999) or 999) < APPROACH_THRESHOLD_PX:
        return 1
    return 0


def build_canonical_records():
    return json.load(open(CANON_PATH))


def build_cell_aware_records():
    canon = json.load(open(CANON_PATH))
    cellsplit = json.load(open(CELLSPLIT_PATH))["records"]

    organic_native = [r for r in canon if r.get("etype") in ("organic", "native_ad")]
    cells = [c for c in cellsplit if c.get("role") == "cell"
             and c.get("kind") in ("dd_top_cell", "dd_right_cell")]

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


def contiguous_group_sizes(tids):
    sizes = []
    cur_tid = None
    cur_size = 0
    for t in tids:
        if t != cur_tid:
            if cur_tid is not None:
                sizes.append(cur_size)
            cur_tid = t
            cur_size = 1
        else:
            cur_size += 1
    if cur_size > 0:
        sizes.append(cur_size)
    return sizes


def loso_ranker(X, labels, tids, pids):
    pooled = np.zeros(len(labels), dtype=float)
    parts = np.unique(pids)
    for p in parts:
        train_mask = pids != p
        test_mask = pids == p
        order = np.argsort(tids[train_mask])
        X_tr = X[train_mask][order]
        y_tr = labels[train_mask][order]
        tids_tr = tids[train_mask][order]
        sizes = contiguous_group_sizes(tids_tr)
        ranker = LGBMRanker(
            objective="lambdarank", metric="ndcg",
            eval_at=[10], n_estimators=200,
            learning_rate=0.05, num_leaves=31,
            min_data_in_leaf=20, verbose=-1,
        )
        ranker.fit(X_tr, y_tr, group=sizes)
        pooled[test_mask] = ranker.predict(X[test_mask])
    return pooled


def loso_lr(X, y, pids):
    pooled = np.zeros(len(y), dtype=float)
    for p in np.unique(pids):
        tr = pids != p
        te = pids == p
        m = Pipeline([("s", StandardScaler()),
                      ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0))])
        m.fit(X[tr], y[tr])
        pooled[te] = m.predict_proba(X[te])[:, 1]
    return pooled


def per_trial_mrr(records, scores):
    by_trial = defaultdict(list)
    for r, s in zip(records, scores):
        by_trial[r["trial_id"]].append((bool(r["was_clicked"]), s))
    rrs = []
    for rows in by_trial.values():
        if not any(c for c, _ in rows):
            continue
        rows.sort(key=lambda x: -x[1])
        for rank, (clk, _) in enumerate(rows, 1):
            if clk:
                rrs.append(1.0 / rank)
                break
    return float(np.mean(rrs)), len(rrs)


def baseline_position_mrr(records):
    scores = -np.array([int(r["position"]) for r in records], dtype=float)
    return per_trial_mrr(records, scores)


def run_view(view_name, records):
    print(f"\n=== {view_name}  n={len(records)} ===", file=sys.stderr)
    tids = np.array([r["trial_id"] for r in records])
    pids = np.array([t.split("-")[0] for t in tids])
    was_clicked = np.array([bool(r["was_clicked"]) for r in records], dtype=int)
    X = np.array([[float(r.get(f, 0) or 0) for f in LTR_FEATURES] for r in records], dtype=float)
    labels_3 = np.array([label_3class(r) for r in records], dtype=int)

    print(f"  label distribution: 0={int((labels_3==0).sum())}  1={int((labels_3==1).sum())}  2={int((labels_3==2).sum())}",
          file=sys.stderr)

    # Baseline: original SERP position
    mrr_serp, n_ranked = baseline_position_mrr(records)
    print(f"  baseline position MRR: {mrr_serp:.4f}  (n_ranked_trials={n_ranked})", file=sys.stderr)

    # Pointwise LR on binary click
    proba_lr = loso_lr(X, was_clicked, pids)
    mrr_lr, _ = per_trial_mrr(records, proba_lr)
    print(f"  pointwise LR on binary:  MRR={mrr_lr:.4f}", file=sys.stderr)

    # LambdaMART on binary click
    binary_labels = was_clicked.astype(int)
    scores_lm_binary = loso_ranker(X, binary_labels, tids, pids)
    mrr_lm_binary, _ = per_trial_mrr(records, scores_lm_binary)
    print(f"  LambdaMART binary clicks: MRR={mrr_lm_binary:.4f}", file=sys.stderr)

    # LambdaMART on 3-class graded
    scores_lm_3class = loso_ranker(X, labels_3, tids, pids)
    mrr_lm_3class, _ = per_trial_mrr(records, scores_lm_3class)
    print(f"  LambdaMART 3-class graded: MRR={mrr_lm_3class:.4f}", file=sys.stderr)

    delta_3class = mrr_lm_3class - mrr_lm_binary
    print(f"  ΔMRR (3-class over binary): {delta_3class:+.4f}", file=sys.stderr)

    return {
        "view": view_name, "n_records": len(records),
        "baseline_position_mrr": mrr_serp,
        "pointwise_lr_mrr": mrr_lr,
        "lambdamart_binary_mrr": mrr_lm_binary,
        "lambdamart_3class_mrr": mrr_lm_3class,
        "delta_3class_over_binary": delta_3class,
        "label_dist": {"0": int((labels_3==0).sum()), "1": int((labels_3==1).sum()), "2": int((labels_3==2).sum())},
    }


def main():
    canon = build_canonical_records()
    cell_aware = build_cell_aware_records()
    canon_res = run_view("canonical", canon)
    cell_res = run_view("cell_aware", cell_aware)

    print("\n" + "=" * 80)
    print("3-CLASS LAMBDAMART LTR: canonical vs cell-aware (organic_hybrid, buf500)")
    print("=" * 80)
    print(f"{'metric':<32} {'canonical':>14} {'cell-aware':>14} {'Δ':>10}")
    for k, label in [
        ("baseline_position_mrr", "SERP position baseline MRR"),
        ("pointwise_lr_mrr", "Pointwise LR (binary) MRR"),
        ("lambdamart_binary_mrr", "LambdaMART binary MRR"),
        ("lambdamart_3class_mrr", "LambdaMART 3-class MRR"),
        ("delta_3class_over_binary", "Δ 3-class vs binary"),
    ]:
        c = canon_res[k]
        a = cell_res[k]
        print(f"{label:<32} {c:>14.4f} {a:>14.4f} {a-c:>+10.4f}")

    print("\n[paper §4.6 headline]  3-class deployable Δ = +0.051")

    out_dir = ROOT / "scripts/output/ltr_3class_cellsplit"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w") as f:
        json.dump({"canonical": canon_res, "cell_aware": cell_res}, f, indent=2)
    print(f"\nSaved {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
