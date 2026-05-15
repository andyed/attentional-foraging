"""Cursor-ablation experiment: does scroll + viewport carry residual signal?

Peter Dixon-Moses's question: "If we ablate the cursor approach signal,
would the residual contain something worth capturing?" — motivated by
the observation that mobile interfaces have no cursor, so the cursor
approach features M4 depends on are not available in a mobile deployment.

This script trains an LTR-style click predictor on four feature sets and
compares LOSO AUC:

  M1          : position only                                       (baseline)
  M2          : position + cursor dwell_in_proximity_ms              (§4.1 baseline)
  M_mobile    : M2 + scroll_regression_count + time_in_viewport      (no cursor approach)
  M4          : cursor approach features                            (§4.1 canonical)

The comparison measures the residual click-prediction signal available
*without* cursor approach features, using only signals a mobile telemetry
pipeline could capture (scroll kinematics + viewport dwell).

M4 defaults to the canonical seven-feature vector (paper §3.4 — final_dist
and retreat_dist screened out as structurally leaky); pass --feature-set
legacy for the pre-§3.4 nine-feature run.

Output: scripts/output/cursor_ablation_mobile_residual/summary.json
"""

from __future__ import annotations

import csv
import datetime
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
from data_loader import (  # noqa: E402
    get_trial_meta, load_mouse_events, result_band_tops, interpolate_scroll,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
MOUSE_DIR = ROOT / "AdSERP/data/mouse-movement-data"
OUT_DIR = ROOT / "scripts/output/cursor_ablation_mobile_residual"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Canonical M4 = leakage-validated seven-feature vector (paper §3.4):
# final_dist + retreat_dist are screened out by the click-buffer protocol.
# Legacy M4 = nine-feature variant retained for direct comparison only.
M4_CANONICAL = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
M4_LEGACY = ["min_dist", "mean_dist", "final_dist", "retreat_dist",
             "dwell_in_proximity_ms",
             "mean_approach_velocity", "max_approach_velocity",
             "direction_changes", "frac_decreasing"]

N_RESULTS = 10


def count_scroll_regressions(trial_id):
    """Count scroll regressions (upward scrolls after a downward scroll).
    Lifted from notebooks-v2/09_difficulty.ipynb."""
    path = MOUSE_DIR / f"{trial_id}.csv"
    if not path.exists():
        return 0
    scrolls = []
    with open(path) as f:
        for row in csv.DictReader(f):
            if row.get("event") == "scroll":
                try:
                    scrolls.append(float(row["ypos"]))
                except (ValueError, KeyError):
                    continue
    if len(scrolls) < 2:
        return 0
    regressions = 0
    prev_direction = None
    for i in range(1, len(scrolls)):
        dy = scrolls[i] - scrolls[i - 1]
        if dy < -5:
            direction = "up"
        elif dy > 5:
            direction = "down"
        else:
            continue
        if direction == "up" and prev_direction == "down":
            regressions += 1
        prev_direction = direction
    return regressions


def compute_time_in_viewport(trial_id, n_results=N_RESULTS):
    """Return array of per-result time-in-viewport (ms).

    Walks the scroll-event timeline and, for each constant-scroll interval,
    accumulates Δt into every result band whose center falls inside the
    current viewport [scroll, scroll + scr_h].
    """
    meta = get_trial_meta(trial_id)
    if meta is None:
        return None
    doc_h, scr_h, _ = meta
    try:
        tops = result_band_tops(n_results, doc_h)
    except Exception:
        return None

    # Band centers: midway between adjacent tops; last band uses uniform spacing.
    centers = np.zeros(n_results)
    for p in range(n_results):
        if p < len(tops) - 1:
            centers[p] = (tops[p] + tops[p + 1]) / 2
        elif len(tops) > 1:
            centers[p] = tops[p] + (tops[1] - tops[0]) / 2
        else:
            centers[p] = tops[p] + 100

    mouse = load_mouse_events(trial_id)
    if mouse is None:
        return None
    all_events, scrolls, clicks = mouse

    # Build a chronological list of (timestamp, scroll_y). Seed with
    # (trial_start, 0) because the viewport starts at page top before any
    # scroll events. load_mouse_events returns tuples, not dicts:
    #   all_events: list of (t, event_type, x, y)
    #   scrolls:    list of (t, y)
    #   clicks:     list of (t, x, y)
    ts, ys = [], []
    for (t, y) in scrolls:
        ts.append(int(t))
        ys.append(float(y))
    if not all_events:
        return None
    t_event_start = int(all_events[0][0])
    t_event_end = int(all_events[-1][0])
    if not ts:
        ts = [t_event_start, t_event_end]
        ys = [0.0, 0.0]
    else:
        if t_event_start < ts[0]:
            ts = [t_event_start] + ts
            ys = [0.0] + ys
        if t_event_end > ts[-1]:
            ts.append(t_event_end)
            ys.append(ys[-1])

    time_in_viewport = np.zeros(n_results, dtype=float)
    for i in range(len(ts) - 1):
        dt = ts[i + 1] - ts[i]
        if dt <= 0 or dt > 60000:
            continue  # skip pathological gaps (> 1 min)
        y_scroll = ys[i]
        viewport_top = y_scroll
        viewport_bottom = y_scroll + scr_h
        for p in range(n_results):
            if viewport_top <= centers[p] <= viewport_bottom:
                time_in_viewport[p] += dt

    return time_in_viewport


def loso_auc(X, y, groups, label):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    n_groups = len(set(groups))
    gkf = GroupKFold(n_splits=n_groups)
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]
    concat_auc = float(roc_auc_score(y, y_proba))

    per_fold = []
    for _, test_idx in gkf.split(X, y, groups=groups):
        yt = y[test_idx]
        if len(np.unique(yt)) < 2:
            continue
        per_fold.append(float(roc_auc_score(yt, y_proba[test_idx])))
    per_fold_arr = np.array(per_fold, dtype=float)
    fold_mean = float(per_fold_arr.mean()) if len(per_fold_arr) else float("nan")
    fold_sd = float(per_fold_arr.std(ddof=1)) if len(per_fold_arr) >= 2 else float("nan")

    print(f"  {label}: concat AUC = {concat_auc:.4f}  "
          f"(per-fold {fold_mean:.4f} ± {fold_sd:.4f}, n_folds={len(per_fold_arr)}/{n_groups})")
    return concat_auc, fold_mean, fold_sd, per_fold_arr


def main(feature_set="canonical"):
    m4_list = M4_CANONICAL if feature_set == "canonical" else M4_LEGACY
    print("=" * 70)
    print("Cursor ablation: does scroll + viewport carry residual signal?")
    print(f"M4 feature set: {feature_set} ({len(m4_list)} features)")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"  {n:,} records")

    print("\ncomputing per-trial scroll-regression counts + per-result time-in-viewport (~2 min)...")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    scroll_reg_by_trial = {}
    tiv_by_trial = {}
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)} trials")
        scroll_reg_by_trial[tid] = count_scroll_regressions(tid)
        tiv = compute_time_in_viewport(tid)
        if tiv is None:
            skipped += 1
            continue
        tiv_by_trial[tid] = tiv
    print(f"  trials with viewport data: {len(tiv_by_trial):,}")
    print(f"  skipped: {skipped}")

    # Build feature matrices
    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    position = np.array([r["position"] for r in lab_records], dtype=float)
    dwell_in_prox = np.array([r.get("dwell_in_proximity_ms") or 0
                              for r in lab_records], dtype=float)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    valid = np.zeros(n, dtype=bool)
    scroll_reg = np.zeros(n, dtype=float)
    tiv = np.zeros(n, dtype=float)
    for i, r in enumerate(lab_records):
        tid = r["trial_id"]
        if tid in tiv_by_trial and int(r["position"]) < N_RESULTS:
            valid[i] = True
            scroll_reg[i] = scroll_reg_by_trial.get(tid, 0)
            tiv[i] = tiv_by_trial[tid][int(r["position"])]

    print(f"\n  valid records: {int(valid.sum()):,}/{n:,}")

    # Build M4 feature matrix from lab_records
    X_m4 = np.zeros((n, len(m4_list)), dtype=float)
    for j, feat in enumerate(m4_list):
        X_m4[:, j] = np.array([r.get(feat) or 0 for r in lab_records], dtype=float)

    X_m4_v = X_m4[valid]
    position_v = position[valid].reshape(-1, 1)
    dwell_v = dwell_in_prox[valid].reshape(-1, 1)
    scroll_reg_v = scroll_reg[valid].reshape(-1, 1)
    tiv_v = tiv[valid].reshape(-1, 1)
    y_v = was_clicked[valid].astype(int)
    g_v = groups_all[valid]

    print("\n── LOSO click prediction ──")
    results = {}

    # M1: position only
    auc, mean, sd, _ = loso_auc(position_v, y_v, g_v, "M1 (position)")
    results["M1"] = {"concat": auc, "per_fold_mean": mean, "per_fold_sd": sd,
                     "features": ["position"]}

    # M2: position + dwell_in_proximity_ms
    X_m2 = np.column_stack([position_v, dwell_v])
    auc, mean, sd, _ = loso_auc(X_m2, y_v, g_v, "M2 (position + dwell)")
    results["M2"] = {"concat": auc, "per_fold_mean": mean, "per_fold_sd": sd,
                     "features": ["position", "dwell_in_proximity_ms"]}

    # M_mobile: M2 + scroll regression + time in viewport
    X_mob = np.column_stack([position_v, dwell_v, scroll_reg_v, tiv_v])
    auc, mean, sd, _ = loso_auc(X_mob, y_v, g_v, "M_mobile (M2 + scroll_reg + time_in_viewport)")
    results["M_mobile"] = {
        "concat": auc, "per_fold_mean": mean, "per_fold_sd": sd,
        "features": ["position", "dwell_in_proximity_ms",
                     "scroll_regression_count", "time_in_viewport"],
    }

    # M_mobile_no_dwell: drop cursor dwell (it's still a cursor feature)
    X_mob_nd = np.column_stack([position_v, scroll_reg_v, tiv_v])
    auc, mean, sd, _ = loso_auc(X_mob_nd, y_v, g_v,
                                 "M_mobile_no_cursor (position + scroll_reg + time_in_viewport)")
    results["M_mobile_no_cursor"] = {
        "concat": auc, "per_fold_mean": mean, "per_fold_sd": sd,
        "features": ["position", "scroll_regression_count", "time_in_viewport"],
    }

    # M4: cursor approach features
    auc, mean, sd, _ = loso_auc(X_m4_v, y_v, g_v,
                                 f"M4 ({len(m4_list)} cursor approach features)")
    results["M4"] = {"concat": auc, "per_fold_mean": mean, "per_fold_sd": sd,
                     "features": list(m4_list)}

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    def fmt(key, label):
        r = results[key]
        return f"  {label:<55s}  concat {r['concat']:.4f}   per-fold {r['per_fold_mean']:.4f} ± {r['per_fold_sd']:.4f}"

    print(fmt("M1", "M1: position only"))
    print(fmt("M2", "M2: + cursor dwell_in_proximity_ms (ceiling w/o cursor approach)"))
    print(fmt("M_mobile_no_cursor",
              "M_mobile_no_cursor: position + scroll_reg + time_in_viewport"))
    print(fmt("M_mobile", "M_mobile: M2 + scroll_reg + time_in_viewport"))
    print(fmt("M4", f"M4: {len(m4_list)} cursor approach features (§4.1 {feature_set})"))

    # Residual signal interpretation
    gap_m1_m4 = results["M4"]["concat"] - results["M1"]["concat"]
    gap_m2_m4 = results["M4"]["concat"] - results["M2"]["concat"]
    recovered_by_mobile_no_cursor = results["M_mobile_no_cursor"]["concat"] - results["M1"]["concat"]
    recovered_by_mobile = results["M_mobile"]["concat"] - results["M1"]["concat"]

    print("\nInterpretation:")
    print(f"  Total M1 → M4 AUC gap ........................ {gap_m1_m4:+.4f}")
    print(f"  M2 → M4 gap (remains after adding cursor dwell) {gap_m2_m4:+.4f}")
    print(f"  M_mobile_no_cursor closes .................... {recovered_by_mobile_no_cursor:+.4f}  "
          f"({recovered_by_mobile_no_cursor / gap_m1_m4 * 100:.1f}% of the M1→M4 gap)")
    print(f"  M_mobile (with cursor dwell) closes .......... {recovered_by_mobile:+.4f}  "
          f"({recovered_by_mobile / gap_m1_m4 * 100:.1f}% of the M1→M4 gap)")

    summary = {
        "experiment": "Cursor ablation: scroll + viewport residual signal for mobile transfer",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "feature_set": feature_set,
        "m4_features": list(m4_list),
        "n_records": int(valid.sum()),
        "results": results,
        "interpretation": {
            "M1_to_M4_gap": gap_m1_m4,
            "M2_to_M4_gap": gap_m2_m4,
            "M_mobile_no_cursor_fraction_of_gap_recovered":
                recovered_by_mobile_no_cursor / gap_m1_m4,
            "M_mobile_fraction_of_gap_recovered": recovered_by_mobile / gap_m1_m4,
        },
    }
    out_name = ("summary.json" if feature_set == "canonical"
                else "summary_legacy.json")
    (OUT_DIR / out_name).write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / out_name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-set", choices=["canonical", "legacy"], default="canonical",
        help="canonical = 7 leakage-validated M4 features (paper §3.4 headline); "
             "legacy = 9-feature variant including final_dist + retreat_dist.")
    args = parser.parse_args()
    main(feature_set=args.feature_set)
