"""Click-buffer ablation grid for §4.1 / §4.4 leakage controls.

Runs LOSO LR on:
  - 4 buffers: {0, 200, 500, 1000} ms
  - 5 model variants: M1 (position), M2 (+dwell), M3 (+approach9),
    M4-9 (legacy 9-feat approach), M4-7 (leakage-corrected, drops
    final_dist + retreat_dist)
  - 2 attributions: organic_hybrid (paper headline), organic

Reports for each cell:
  - LOSO AUC across 47 participants (per-fold AUC summary)
  - Per-trial MRR@10 (rank of true click within trial's AOIs)
  - Per-trial NDCG@1 (top-ranked AOI is the click: 1/0)
  - Average Precision, Brier score

Output:
  - scripts/output/cikm-2026/click_buffer_ablation.json (full grid)
  - stdout: human-readable table for paper §4.1

Companion to docs/drafts/cikm-2026/REVISION-PLAN.md Steps 3 + 6.

Run:
    .venv/bin/python scripts/click_buffer_ablation.py
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
)
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "AdSERP/data"

sys.path.insert(0, "/Users/andyed/.claude/skills/muriel")
from muriel.provenance import stamp_json  # noqa: E402

BUFFERS = [0, 200, 500, 1000]
ATTRIBUTIONS = ["organic_hybrid", "organic"]

# Canonical feature lists. M4_9 is the legacy paper-v5 vector;
# M4_7 drops final_dist + retreat_dist (structurally leaky).
APPROACH_9 = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
APPROACH_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def feat_path(attribution: str, buf: int) -> Path:
    base = "cursor-approach-features"
    if attribution == "organic_hybrid":
        stem = f"{base}-organic-hybrid"
    elif attribution == "organic":
        stem = f"{base}-organic"
    else:
        raise ValueError(attribution)
    suffix = f"-buf{buf}" if buf > 0 else ""
    return DATA / f"{stem}{suffix}.json"


def load_records(attribution: str, buf: int):
    path = feat_path(attribution, buf)
    if not path.exists():
        raise FileNotFoundError(path)
    return json.load(open(path))


def per_trial_ranking_metrics(records, proba):
    """Compute per-trial MRR@10 and NDCG@1 over within-trial AOI rankings.

    Each trial contributes at most one positive (the clicked AOI). Trials
    with no positive in `records` (e.g. click on a non-fixated AOI) are
    excluded from MRR/NDCG; they remain in AUC since AUC pools globally.
    """
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
    logo = LeaveOneGroupOut()
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=logo,
                              method="predict_proba", n_jobs=-1)[:, 1]
    auc = roc_auc_score(y, proba)
    ap = average_precision_score(y, proba)
    brier = brier_score_loss(y, proba)
    per_part = []
    for pid in sorted(set(groups)):
        m = groups == pid
        if m.sum() < 10 or len(set(y[m])) < 2:
            continue
        per_part.append(roc_auc_score(y[m], proba[m]))
    mrr, ndcg1, n_trials = per_trial_ranking_metrics(records, proba)
    return {
        "auc": auc, "ap": ap, "brier": brier,
        "mrr_at_10": mrr, "ndcg_at_1": ndcg1, "n_ranked_trials": n_trials,
        "per_part_auc_median": float(np.median(per_part)),
        "per_part_auc_iqr": [float(np.percentile(per_part, 25)),
                             float(np.percentile(per_part, 75))],
        "n_records": int(len(records)),
    }


def build_features(records, variant: str):
    positions = np.array([r["position"] for r in records])
    total_dwell = np.array([r["total_dwell_ms"] for r in records])
    if variant == "M1":
        return positions.reshape(-1, 1)
    if variant == "M2":
        return np.column_stack([positions, total_dwell])
    if variant == "M3":  # M2 + 9 approach (matches paper-v5 canonical)
        X9 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
        return np.column_stack([positions, total_dwell, X9])
    if variant == "M3-7":  # leakage-corrected M3
        X7 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
        return np.column_stack([positions, total_dwell, X7])
    if variant == "M4-9":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
    if variant == "M4-7":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
    raise ValueError(variant)


VARIANTS = ["M1", "M2", "M3", "M3-7", "M4-9", "M4-7"]


def main():
    grid = {}
    for attribution in ATTRIBUTIONS:
        for buf in BUFFERS:
            print(f"\n=== {attribution}  buf={buf}ms ===", file=sys.stderr)
            recs = load_records(attribution, buf)
            y = np.array([r["was_clicked"] for r in recs], dtype=int)
            groups = np.array([r["trial_id"].split("-")[0] for r in recs])
            for variant in VARIANTS:
                X = build_features(recs, variant)
                res = fit_eval(X, y, groups, recs)
                cell_key = f"{attribution}|buf{buf}|{variant}"
                grid[cell_key] = {
                    "attribution": attribution, "buffer_ms": buf,
                    "variant": variant, **res,
                }
                print(
                    f"  {variant:6s}  AUC={res['auc']:.3f}  "
                    f"MRR={res['mrr_at_10']:.3f}  NDCG@1={res['ndcg_at_1']:.3f}  "
                    f"AP={res['ap']:.3f}  Brier={res['brier']:.4f}  "
                    f"n={res['n_records']:,}  trials={res['n_ranked_trials']}",
                    file=sys.stderr,
                )

    # Headline summary table for paper §4.1
    print("\n" + "=" * 88, file=sys.stderr)
    print("HEADLINE TABLE — organic_hybrid", file=sys.stderr)
    print("=" * 88, file=sys.stderr)
    print(f"{'variant':8s} {'buf':>5s}   {'AUC':>6s}  {'MRR':>6s}  {'NDCG@1':>7s}  {'AP':>6s}  {'Brier':>7s}",
          file=sys.stderr)
    for variant in VARIANTS:
        for buf in BUFFERS:
            r = grid[f"organic_hybrid|buf{buf}|{variant}"]
            print(f"{variant:8s} {buf:>5d}   {r['auc']:.3f}   {r['mrr_at_10']:.3f}   "
                  f"{r['ndcg_at_1']:.3f}    {r['ap']:.3f}   {r['brier']:.4f}",
                  file=sys.stderr)

    out_path = ROOT / "scripts/output/cikm-2026/click_buffer_ablation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "buffers_ms": BUFFERS,
        "attributions": ATTRIBUTIONS,
        "variants": VARIANTS,
        "approach_9": APPROACH_9,
        "approach_7": APPROACH_7,
        "grid": grid,
    }
    stamp_json(
        payload, out_path,
        script=__file__,
        dataset="AdSERP/data/cursor-approach-features-{organic,organic-hybrid}{,-buf{200,500,1000}}.json",
        h_ids=[],
        nb_k_ids=["NB21:K-bbox-3"],
        figure_version="click-buffer-ablation",
        notes=(
            f"Click-buffer Δ leakage screen. "
            f"buffers={BUFFERS}, attributions={ATTRIBUTIONS}, variants={VARIANTS}. "
            f"M4_9 vs M4_7 (final_dist + retreat_dist dropped as structurally leaky)."
        ),
    )
    print(f"\nWrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
