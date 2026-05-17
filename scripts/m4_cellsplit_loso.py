"""Cell-aware M1→M4 LOSO retrain. Compares cell-aware AUC vs canonical
parent-only AUC (paper §4.1 headline: M1=0.668, M4=0.847).

Cell-aware input mix:
  - organic + native_ad records: canonical hybrid-buf500 (unchanged)
  - dd_top, dd_right records: REPLACED by their cellsplit cells
    (X-gated with midpoint-split tolerance per AllSERP §2.2)

Run:
    .venv/bin/python scripts/m4_cellsplit_loso.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-buf500.json"
CELLSPLIT = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-cellsplit-buf500.json"

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def fit_loso(X, y, groups, name):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    logo = LeaveOneGroupOut()
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=logo,
                              method="predict_proba", n_jobs=-1)[:, 1]
    auc = roc_auc_score(y, proba)
    ap = average_precision_score(y, proba)
    per = []
    for pid in sorted(set(groups)):
        m = groups == pid
        if m.sum() >= 10 and len(set(y[m])) >= 2:
            per.append(roc_auc_score(y[m], proba[m]))
    per_arr = np.array(per)
    return {
        "name": name, "n_records": int(len(y)), "n_pos": int(y.sum()),
        "auc": float(auc), "ap": float(ap),
        "auc_per_part_median": float(np.median(per_arr)) if len(per) else None,
        "auc_per_part_iqr": (float(np.percentile(per_arr, 25)),
                              float(np.percentile(per_arr, 75))) if len(per) else None,
    }


def build_records(view: str) -> list[dict]:
    """view = 'canonical' (parent-only) or 'cell_aware' (cells for dd_top/dd_right)"""
    canon = json.load(open(CANON))
    cellsplit_data = json.load(open(CELLSPLIT))
    cellsplit_records = cellsplit_data["records"]

    if view == "canonical":
        return canon

    # cell-aware: keep organic + native_ad from canonical; replace dd_top/dd_right
    # with their cellsplit cells.
    organic_native = [r for r in canon if r.get("etype") in ("organic", "native_ad")]
    cells = [r for r in cellsplit_records if r["role"] == "cell"
             and r["kind"] in ("dd_top_cell", "dd_right_cell")]
    # Map cell record schema → canonical schema
    cells_mapped = []
    for c in cells:
        # Cells may have null features (n_samples=0) — treat as NOT_APPROACHED
        # (M4 features default to 0; position from c.position or fallback)
        cells_mapped.append({
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
    return organic_native + cells_mapped


def run(view: str):
    records = build_records(view)
    print(f"\n=== view={view}: {len(records)} records ===", file=sys.stderr)

    from collections import Counter
    et_counts = Counter(r.get("etype") for r in records)
    print(f"  etype: {dict(et_counts)}", file=sys.stderr)

    clicked = np.array([r["was_clicked"] for r in records], dtype=int)
    participants = np.array([r["trial_id"].split("-")[0] for r in records])
    positions = np.array([r["position"] for r in records], dtype=float)
    total_dwell = np.array([r["total_dwell_ms"] for r in records], dtype=float)
    X4 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in records])
    X3 = np.column_stack([positions.reshape(-1, 1), total_dwell.reshape(-1, 1), X4])
    X2 = np.column_stack([positions.reshape(-1, 1), total_dwell.reshape(-1, 1)])
    X1 = positions.reshape(-1, 1)

    return {
        "view": view,
        "n_records": len(records),
        "n_positive": int(clicked.sum()),
        "etype_counts": dict(et_counts),
        "M1": fit_loso(X1, clicked, participants, "M1"),
        "M2": fit_loso(X2, clicked, participants, "M2"),
        "M3": fit_loso(X3, clicked, participants, "M3"),
        "M4": fit_loso(X4, clicked, participants, "M4"),
    }


def main():
    print("Running canonical (parent-only) LOSO...", file=sys.stderr)
    canon_result = run("canonical")
    print("\nRunning cell-aware LOSO...", file=sys.stderr)
    cell_result = run("cell_aware")
    print("\n" + "=" * 70)
    print("M1→M4 LOSO comparison: canonical vs cell-aware")
    print("=" * 70)
    for model in ["M1", "M2", "M3", "M4"]:
        c = canon_result[model]
        a = cell_result[model]
        delta = a["auc"] - c["auc"]
        print(f"  {model}: canonical AUC={c['auc']:.4f} (n={c['n_records']}, pos={c['n_pos']}) | "
              f"cell-aware AUC={a['auc']:.4f} (n={a['n_records']}, pos={a['n_pos']}) | Δ={delta:+.4f}")
    out_dir = ROOT / "scripts/output/m4_cellsplit_loso"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w") as f:
        json.dump({"canonical": canon_result, "cell_aware": cell_result}, f, indent=2)
    print(f"\nSaved to {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
