"""Cell-aware xpath-grounded M4 retrain — extends m4_nb21_hybrid_rerun.py
to include dd_top_cell / dd_right_cell / organic_cell AOIs from the
AllSERP cascade-baseline snapshot. Produces the cell-aware analog of
the paper §4.1 headline M1=0.668 / M4=0.847.

For each trial:
  1. Run the canonical xpath+linear extractor (compute_hybrid_features)
     for positions 0..9 — these are the PARENT records.
  2. Load cascade-baseline cells (dd_top_cell, dd_right_cell, organic_cell).
  3. For each cell, compute the 7 M4 features against cell.cy using the
     trial's positional cursor stream, X-gated to cell.x range.
  4. Click attribution at cell level: click (x,y) inside cell bbox → clicked.
  5. Emit both parent AND cell records.

Then run M1→M4 LOSO LR in two views and compare AUC + per-fold deltas:
  canonical:  parent records only
  cell_aware: parent records for non-dd_top/dd_right + cells for those etypes

Caveats vs canonical extractor:
  - compute_hybrid_features doesn't know etype, so we infer etype per
    position via the cascade-baseline snapshot (position 0 with dd_top
    parent → etype=dd_top, etc.)
  - For positions corresponding to dd_top parent, cell-aware replaces
    the parent record with N cell records.

Run:
    .venv/bin/python scripts/m4_nb21_hybrid_rerun_cellsplit.py
"""
from __future__ import annotations

import csv
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
sys.path.insert(0, str(ROOT))
from scripts.m4_nb21_hybrid_rerun import (  # noqa: E402
    compute_hybrid_features, PROX_THRESHOLD,
    MOUSE_DIR, FEATURES_JSON,
)
from scripts.probe_cellsplit_features import load_aois  # noqa: E402

# Paper §4.1 canonical M4 = 7 features (drops final_dist + retreat_dist
# per the §3.4 leakage screen — both are pinned by terminal cursor lock-on).
# The script's own M4_FEATURES has 9; the paper uses 7. We use 7 here to
# match the paper's headline AUC 0.847.
M4_FEATURES = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

OUT_DIR = ROOT / "scripts/output/m4_nb21_hybrid_rerun_cellsplit"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CASCADE_DIR = ROOT / "scripts/output/cascade-baseline/aoi-snapshot-v1"


def compute_cell_features(trial_id: str, parent_records: list[dict]) -> list[dict]:
    """Compute cell-level M4 features using the same cursor-stream logic as
    compute_hybrid_features but against cell-specific centers + X-gating.
    Mirrors m4_nb21_hybrid_rerun.py:166-211 (1D-Y, full cursor stream).
    """
    # Reload positional cursor events from CSV (same as compute_hybrid_features)
    csv_path = MOUSE_DIR / f"{trial_id}.csv"
    if not csv_path.exists():
        return []
    events = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = int(row["timestamp"])
                x = float(row["xpos"])
                y = float(row["ypos"])
            except (ValueError, KeyError):
                continue
            events.append({"t": t, "x": x, "y": y, "event": row.get("event", "")})
    if not events:
        return []
    POSITIONAL = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    positional = [e for e in events
                  if e["event"] in POSITIONAL and e["x"] > 0 and e["y"] > 0]
    if len(positional) < 2:
        return []

    ts_all = np.array([e["t"] for e in positional], dtype=np.int64)
    xs_all = np.array([e["x"] for e in positional], dtype=float)
    ys_all = np.array([e["y"] for e in positional], dtype=float)

    # Click: last click event
    clicks = [e for e in positional if e["event"] == "click"]
    click_xy = (clicks[-1]["x"], clicks[-1]["y"]) if clicks else (None, None)

    # Load cells from cascade-baseline (with midpoint-split tolerance)
    try:
        aois = load_aois(trial_id, midpoint_split=True)
    except FileNotFoundError:
        return []
    cells = [a for a in aois if a["role"] == "cell"]
    if not cells:
        return []

    cell_records = []
    for cell in cells:
        cy = cell["y"] + cell["h"] / 2
        # X-gate
        mask = (xs_all >= cell["x"]) & (xs_all <= cell["x"] + cell["w"])
        if mask.sum() < 2:
            # Empty cell — emit a record with null-ish features that LR can
            # safely interpret (matches the NOT_APPROACHED semantics)
            rec = {
                "trial_id": trial_id, "position": 0,
                "kind": cell["kind"], "role": "cell",
                "parent_kind": cell["parent_kind"],
                "cell_position": cell.get("position"),
                "grounding": "cell",
                "min_dist": 999.0, "mean_dist": 999.0, "final_dist": 999.0,
                "retreat_dist": 0.0,
                "dwell_in_proximity_ms": 0.0,
                "mean_approach_velocity": 0.0, "max_approach_velocity": 0.0,
                "direction_changes": 0, "frac_decreasing": 0.5,
                "was_clicked": False,
                "n_samples": int(mask.sum()),
            }
            cell_records.append(rec)
            continue
        ys_g = ys_all[mask]
        ts_g = ts_all[mask]
        dist = np.abs(ys_g - cy)
        if len(dist) < 2:
            continue
        in_prox = dist < PROX_THRESHOLD
        dwell_ms = 0.0
        for i in range(1, len(ts_g)):
            if in_prox[i]:
                dt = int(ts_g[i] - ts_g[i - 1])
                if 0 < dt < 2000:
                    dwell_ms += dt
        dts = np.diff(ts_g).astype(float)
        # Floor dt + clamp velocity so a tiny gap can't manufacture an
        # impossible speed (rationale in m4_nb21_hybrid_rerun.py). Clamp is
        # symmetric → sign-based features and the negative mean unaffected.
        dts = np.maximum(dts, 8.0)  # MIN_VEL_DT_MS
        vels = -np.diff(dist) / dts * 1000.0
        vels = np.clip(vels, -5000.0, 5000.0)  # MAX_PLAUSIBLE_VEL px/s

        was_clicked = False
        if click_xy[0] is not None:
            cx, cclk_y = click_xy
            if (cell["x"] <= cx <= cell["x"] + cell["w"]
                    and cell["y"] <= cclk_y <= cell["y"] + cell["h"]):
                was_clicked = True

        rec = {
            "trial_id": trial_id, "position": 0,  # placeholder; cells share parent position
            "kind": cell["kind"], "role": "cell",
            "parent_kind": cell["parent_kind"],
            "cell_position": cell.get("position"),
            "grounding": "cell",
            "min_dist": float(dist.min()),
            "mean_dist": float(dist.mean()),
            "final_dist": float(dist[-1]),
            "retreat_dist": float(dist[-1] - dist[int(np.argmin(dist))]),
            "dwell_in_proximity_ms": dwell_ms,
            "mean_approach_velocity": float(vels.mean()),
            "max_approach_velocity": float(vels.max()),
            "direction_changes": int(np.sum(np.diff(np.sign(vels)) != 0)),
            "frac_decreasing": float(np.mean(np.diff(dist) < 0)),
            "was_clicked": was_clicked,
            "n_samples": int(mask.sum()),
        }
        cell_records.append(rec)
    return cell_records


def main():
    print("Loading canonical LAB records (paper headline) ...")
    lab_records = json.load(open(FEATURES_JSON))
    print(f"  {len(lab_records):,} LAB records")

    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    print(f"  {len(trial_ids):,} unique trials")

    print("\nComputing canonical xpath+linear parent features ...")
    hy_records = []
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 500 == 0 and n_done > 0:
            print(f"  parents {n_done}/{len(trial_ids)}")
        recs = compute_hybrid_features(tid)
        if recs is None:
            skipped += 1
            continue
        for r in recs:
            r["role"] = "parent"
            r["kind"] = "parent"
        hy_records.extend(recs)
    print(f"  parent records: {len(hy_records):,}  (skipped: {skipped})")

    print("\nComputing cell-aware features for trials with cascade-baseline cells ...")
    cell_records = []
    for n_done, tid in enumerate(trial_ids):
        if n_done % 500 == 0 and n_done > 0:
            print(f"  cells {n_done}/{len(trial_ids)}")
        cells = compute_cell_features(tid, [])
        for c in cells:
            cell_records.append(c)
    print(f"  cell records: {len(cell_records):,}")

    # Save extracted features
    (OUT_DIR / "hybrid_features_cellsplit.json").write_text(
        json.dumps({"parent": hy_records, "cell": cell_records}, indent=1)
    )

    # ── Build canonical (parent-only) and cell-aware views ──
    # was_clicked for parents: pull from LAB records
    lab_index = {(r["trial_id"], r["position"]): r for r in lab_records}
    parent_recs = []
    for hy in hy_records:
        lab = lab_index.get((hy["trial_id"], hy["position"]))
        if lab is None:
            continue
        parent_recs.append({
            **hy,
            "was_clicked": bool(lab["was_clicked"]),
            "participant": hy["trial_id"].split("-")[0],
        })

    # Cell records — augment with participant
    cell_recs = [{**c, "participant": c["trial_id"].split("-")[0]} for c in cell_records]

    print(f"\n  parent_recs (with LAB join): {len(parent_recs):,}")
    print(f"  cell_recs:                   {len(cell_recs):,}")

    # Cell-aware view: parents minus dd_top/dd_right + cells for those etypes
    # We don't know parent etype directly here — use position 0 as dd_top heuristic
    # (in AdSERP organic_hybrid, position 0 is the topmost which is often dd_top).
    # For a cleaner mapping, infer etype from cascade-baseline snapshot per trial.
    def etype_of_parent(p_rec):
        # Load cascade-baseline for this trial to identify etype at position
        snap_path = CASCADE_DIR / f"{p_rec['trial_id']}.json"
        if not snap_path.exists():
            return "organic"
        try:
            snap = json.load(open(snap_path))
        except Exception:
            return "organic"
        # Position 0 with dd_top parent → dd_top
        if p_rec["position"] == 0 and snap.get("dd_top"):
            return "dd_top"
        # Last positions with native_ad → native_ad (approximate)
        # For lack of fine etype mapping, fallback to organic
        return "organic"

    # Mark each parent rec with inferred etype (slow but only runs once)
    print("\n  Inferring parent etypes from cascade-baseline (for dd_top swap)...")
    etype_cache = {}
    for p in parent_recs:
        tid = p["trial_id"]
        if tid not in etype_cache:
            snap_path = CASCADE_DIR / f"{tid}.json"
            if snap_path.exists():
                try:
                    snap = json.load(open(snap_path))
                    etype_cache[tid] = bool(snap.get("dd_top"))
                except Exception:
                    etype_cache[tid] = False
            else:
                etype_cache[tid] = False
        p["etype_dd_top"] = (p["position"] == 0 and etype_cache[tid])

    canonical_view = parent_recs
    # cell_aware: drop position-0 parents with dd_top; add cells
    cell_aware_view = (
        [p for p in parent_recs if not p.get("etype_dd_top", False)]
        + [c for c in cell_recs if c["kind"] == "dd_top_cell"]
    )

    # M4 LOSO
    def loso(records, view_name):
        y = np.array([r["was_clicked"] for r in records], dtype=int)
        groups = np.array([r["trial_id"].split("-")[0] for r in records])
        X = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in records])
        positions = np.array([float(r.get("position", 0)) for r in records]).reshape(-1, 1)
        pipe = Pipeline([("s", StandardScaler()),
                         ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0))])
        n_groups = len(set(groups))
        gkf = GroupKFold(n_splits=n_groups)
        proba_m4 = cross_val_predict(pipe, X, y, groups=groups, cv=gkf,
                                       method="predict_proba", n_jobs=1)[:, 1]
        auc_m4 = roc_auc_score(y, proba_m4)
        proba_m1 = cross_val_predict(pipe, positions, y, groups=groups, cv=gkf,
                                       method="predict_proba", n_jobs=1)[:, 1]
        auc_m1 = roc_auc_score(y, proba_m1)
        X3 = np.column_stack([positions, X])
        proba_m3 = cross_val_predict(pipe, X3, y, groups=groups, cv=gkf,
                                       method="predict_proba", n_jobs=1)[:, 1]
        auc_m3 = roc_auc_score(y, proba_m3)
        return {"view": view_name, "n": len(records), "pos": int(y.sum()),
                 "M1": float(auc_m1), "M3": float(auc_m3), "M4": float(auc_m4)}

    print("\nRunning canonical view LOSO (paper-canonical extractor) ...")
    canon = loso(canonical_view, "canonical")
    print("Running cell-aware view LOSO ...")
    cell_v = loso(cell_aware_view, "cell_aware")

    print("\n" + "=" * 70)
    print("Paper-canonical xpath-grounded extractor: canonical vs cell-aware")
    print("=" * 70)
    print(f"{'view':<14} {'n':>7} {'pos':>6} {'M1':>8} {'M3':>8} {'M4':>8}")
    print(f"{canon['view']:<14} {canon['n']:>7} {canon['pos']:>6} {canon['M1']:>8.4f} {canon['M3']:>8.4f} {canon['M4']:>8.4f}")
    print(f"{cell_v['view']:<14} {cell_v['n']:>7} {cell_v['pos']:>6} {cell_v['M1']:>8.4f} {cell_v['M3']:>8.4f} {cell_v['M4']:>8.4f}")
    print(f"{'delta':<14} {cell_v['n']-canon['n']:>+7} {cell_v['pos']-canon['pos']:>+6} "
          f"{cell_v['M1']-canon['M1']:>+8.4f} {cell_v['M3']-canon['M3']:>+8.4f} {cell_v['M4']-canon['M4']:>+8.4f}")

    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump({"canonical": canon, "cell_aware": cell_v}, f, indent=2)
    print(f"\nSaved {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
