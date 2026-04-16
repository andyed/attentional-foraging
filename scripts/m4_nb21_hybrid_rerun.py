"""Option D: Hybrid xpath-grounded + linear-fallback feature extractor.

For each (trial, result) pair:
  - If the trial's mouse events include xpath-resolved events on result P,
    use the median of those observed positions as P's bounding-box center.
    (Production-equivalent: this mimics what the approach-retreat library
    would get from getBoundingClientRect() at init time.)
  - Otherwise fall back to result_band_tops(doc_h)[P] — the linear
    page-height-based estimate used by the MM v1 full-trial extractor.

All features are then computed uniformly from the full cursor trajectory
against those result centers. No gaze data at any step.

The fallback arm is an offline-reconstruction artifact: in production, the
approach-retreat library would use getBoundingClientRect() at registration
and have accurate bounding boxes for every result by construction. The
fallback only exists because we cannot re-render AdSERP's 2,776 SERPs from
static HTML without headless browser rendering.

Expected outcome: 100% population coverage, with xpath-accuracy on ~50% of
records and linear-estimated accuracy on the other ~50% (records where the
cursor never hovered on-result).

Outputs:
  scripts/output/m4_nb21_hybrid_rerun/hybrid_features.json
  scripts/output/m4_nb21_hybrid_rerun/summary.json
"""

from __future__ import annotations

import csv
import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import get_trial_meta, result_band_tops  # noqa: E402

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
MOUSE_DIR = ROOT / "AdSERP/data/mouse-movement-data"
OUT_DIR = ROOT / "scripts/output/m4_nb21_hybrid_rerun"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RESULT_XPATH_RE = re.compile(r"^//\*\[@id='rso'\]/div\[(\d+)\]")

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

PROX_THRESHOLD = 100
N_RESULTS_DEFAULT = 10


def extract_result_idx(xpath):
    if not xpath:
        return None
    m = RESULT_XPATH_RE.match(xpath)
    if m:
        return int(m.group(1)) - 1
    return None


def compute_hybrid_features(trial_id, n_results=N_RESULTS_DEFAULT):
    """Hybrid xpath-grounded + linear-fallback feature extractor."""
    csv_path = MOUSE_DIR / f"{trial_id}.csv"
    if not csv_path.exists():
        return None

    # Load mouse events with xpath column
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
            events.append({
                "t": t, "x": x, "y": y,
                "event": row.get("event", ""),
                "result_idx": extract_result_idx(row.get("xpath", "")),
            })
    if not events:
        return None

    POSITIONAL = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    positional = [e for e in events
                  if e["event"] in POSITIONAL and e["x"] > 0 and e["y"] > 0]
    if len(positional) < 2:
        return None

    # Phase 1a — learn xpath-grounded centers from observed on-result events
    xpath_on = defaultdict(list)
    for e in positional:
        if e["result_idx"] is not None:
            xpath_on[e["result_idx"]].append(e)

    xpath_centers = {}
    for pos, evts in xpath_on.items():
        if len(evts) < 1:
            continue
        xs = np.array([e["x"] for e in evts], dtype=float)
        ys = np.array([e["y"] for e in evts], dtype=float)
        xpath_centers[pos] = (float(np.median(xs)), float(np.median(ys)))

    # Phase 1b — linear fallback centers for positions without xpath events
    meta = get_trial_meta(trial_id)
    if meta is None:
        return None
    doc_h, _, _ = meta
    try:
        tops = result_band_tops(n_results, doc_h)
    except Exception:
        return None

    linear_centers = {}
    for pos in range(n_results):
        if pos < len(tops) - 1:
            cy = (tops[pos] + tops[pos + 1]) / 2
        else:
            cy = tops[pos] + (tops[1] - tops[0]) / 2 if len(tops) > 1 else tops[pos] + 100
        # X center is trial-invariant in a single-column SERP — use median of
        # all positional x values as a reasonable default.
        linear_centers[pos] = (
            float(np.median([e["x"] for e in positional])),
            float(cy),
        )

    # Phase 2 — compute features over the full cursor trajectory per result
    ts_all = np.array([e["t"] for e in positional], dtype=np.int64)
    xs_all = np.array([e["x"] for e in positional], dtype=float)
    ys_all = np.array([e["y"] for e in positional], dtype=float)

    out = []
    for pos in range(n_results):
        if pos in xpath_centers:
            cx, cy = xpath_centers[pos]
            grounding = "xpath"
        else:
            cx, cy = linear_centers[pos]
            grounding = "linear"

        # 1-D vertical distance only — matches MM v1's signal model.
        # In a single-column SERP the horizontal component adds noise
        # without signal (results span the full column width), so using
        # only |dy| both improves the linear-fallback records (where x
        # center is unreliable) and doesn't hurt the xpath-grounded
        # records (where vertical distance is the dominant signal anyway).
        dist = np.abs(ys_all - cy)

        if len(dist) < 2:
            continue

        min_dist = float(dist.min())
        mean_dist = float(dist.mean())
        final_dist = float(dist[-1])
        min_idx = int(np.argmin(dist))
        retreat_dist = float(dist[-1] - dist[min_idx])

        in_prox = dist < PROX_THRESHOLD
        dwell_ms = 0.0
        for i in range(1, len(ts_all)):
            if in_prox[i]:
                dt = int(ts_all[i] - ts_all[i - 1])
                if 0 < dt < 2000:
                    dwell_ms += dt

        if len(ts_all) >= 2:
            dts = np.diff(ts_all).astype(float)
            dts[dts == 0] = 1.0
            vels = -np.diff(dist) / dts * 1000.0
            mean_vel = float(vels.mean())
            max_vel = float(vels.max())
            direction_changes = int(np.sum(np.diff(np.sign(vels)) != 0))
            frac_decreasing = float(np.mean(np.diff(dist) < 0))
        else:
            mean_vel = max_vel = 0.0
            direction_changes = 0
            frac_decreasing = 0.0

        out.append({
            "trial_id": trial_id,
            "position": pos,
            "grounding": grounding,
            "min_dist": min_dist,
            "mean_dist": mean_dist,
            "final_dist": final_dist,
            "retreat_dist": retreat_dist,
            "dwell_in_proximity_ms": dwell_ms,
            "mean_approach_velocity": mean_vel,
            "max_approach_velocity": max_vel,
            "direction_changes": direction_changes,
            "frac_decreasing": frac_decreasing,
        })
    return out


def loso_auc(X, y, groups, label):
    """Return (concat_auc, per_fold_mean_auc, per_fold_sd, per_fold_aucs, y_proba).

    Two AUC summaries are computed on the same cross_val_predict output:
      - concat_auc: single ROC computed on the concatenated OOF predictions
        (stable when any single fold has too few positives for its own ROC)
      - per_fold_mean ± per_fold_sd: mean and SD of per-fold AUCs, the
        standard "fold SD" reporting used in the IR / click-prediction
        literature (reviewers expect an error bar on LOSO AUC).
    """
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            max_iter=5000, class_weight="balanced", C=1.0,
        )),
    ])
    n_groups = len(set(groups))
    gkf = GroupKFold(n_splits=n_groups)
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]
    concat_auc = float(roc_auc_score(y, y_proba))

    # Per-fold AUCs — iterate the same CV splitter over held-out indices.
    per_fold = []
    for _, test_idx in gkf.split(X, y, groups=groups):
        yt = y[test_idx]
        if len(np.unique(yt)) < 2:
            continue  # fold has only one class — ROC undefined, skip
        per_fold.append(float(roc_auc_score(yt, y_proba[test_idx])))
    per_fold_arr = np.array(per_fold, dtype=float)
    fold_mean = float(per_fold_arr.mean()) if len(per_fold_arr) else float("nan")
    fold_sd = float(per_fold_arr.std(ddof=1)) if len(per_fold_arr) >= 2 else float("nan")

    print(f"  {label}: LOSO AUC = {concat_auc:.4f}  "
          f"(per-fold {fold_mean:.4f} ± {fold_sd:.4f}, "
          f"n_folds={len(per_fold_arr)}/{n_groups})")
    return concat_auc, fold_mean, fold_sd, per_fold_arr, y_proba


def main():
    print("=" * 70)
    print("Option D: Hybrid xpath + linear fallback feature extractor")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"  {n:,} records")

    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)

    print("\ncomputing hybrid features per trial (~3 min)...")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    hy_records = []
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)} trials")
        recs = compute_hybrid_features(tid)
        if recs is None:
            skipped += 1
            continue
        hy_records.extend(recs)
    print(f"  hybrid records: {len(hy_records):,}")
    print(f"  trials skipped: {skipped}")

    xpath_count = sum(1 for r in hy_records if r["grounding"] == "xpath")
    linear_count = sum(1 for r in hy_records if r["grounding"] == "linear")
    print(f"  xpath-grounded: {xpath_count:,} ({xpath_count / len(hy_records) * 100:.1f}%)")
    print(f"  linear-fallback: {linear_count:,} ({linear_count / len(hy_records) * 100:.1f}%)")

    (OUT_DIR / "hybrid_features.json").write_text(json.dumps(hy_records, indent=1))

    hy_index = {(r["trial_id"], r["position"]): r for r in hy_records}

    # Align to LAB records
    X_hy = np.zeros((n, len(M4_FEATURES)), dtype=float)
    position = np.zeros(n, dtype=float)
    valid = np.zeros(n, dtype=bool)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        hy = hy_index.get(key)
        if hy is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X_hy[i, j] = float(hy.get(f, 0) or 0)
        position[i] = float(r["position"])
        valid[i] = True

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    mask = valid
    print(f"\n  {int(mask.sum()):,} records with hybrid features "
          f"({int(mask.sum()) / n * 100:.1f}%)")

    X_valid = X_hy[mask]
    pos_valid = position[mask].reshape(-1, 1)
    y_valid = was_clicked[mask].astype(int)
    groups_valid = groups_all[mask]

    # ── Click prediction ──
    print("\n── LOSO click prediction on hybrid features ──")
    auc_m1, m1_mean, m1_sd, _, _ = loso_auc(pos_valid, y_valid, groups_valid, "M1 (position)")
    dwell_idx = M4_FEATURES.index("dwell_in_proximity_ms")
    X_m2 = np.column_stack([pos_valid, X_valid[:, dwell_idx]])
    auc_m2, m2_mean, m2_sd, _, _ = loso_auc(X_m2, y_valid, groups_valid, "M2 (position + dwell)")
    auc_m4, m4_mean, m4_sd, m4_folds, yp_m4 = loso_auc(X_valid, y_valid, groups_valid, "M4 (9 approach)")
    X_m3 = np.column_stack([pos_valid, X_valid])
    auc_m3, m3_mean, m3_sd, m3_folds, _ = loso_auc(X_m3, y_valid, groups_valid, "M3 (position + 9 approach)")

    # Paired per-fold M4 vs M3 comparison: is the +0.001 delta within noise?
    if len(m4_folds) == len(m3_folds) and len(m4_folds) >= 2:
        paired_delta = m4_folds - m3_folds
        print(f"\n  M4 − M3 per-fold delta: "
              f"mean = {paired_delta.mean():+.4f}, "
              f"sd = {paired_delta.std(ddof=1):.4f}, "
              f"min = {paired_delta.min():+.4f}, "
              f"max = {paired_delta.max():+.4f}")
        print(f"  M4 beats M3 in {int((paired_delta > 0).sum())}/{len(m4_folds)} folds")

    # ── NB21 classifier-threshold ──
    print("\n── NB21 classifier-threshold (hybrid) ──")
    min_dist_hy = X_valid[:, M4_FEATURES.index("min_dist")]
    approached_hy = min_dist_hy < PROX_THRESHOLD
    subset_mask = approached_hy & (~y_valid.astype(bool))

    fpr, tpr, thresholds = roc_curve(y_valid, yp_m4)
    j_idx = int(np.argmax(tpr - fpr))
    j_threshold = float(thresholds[j_idx])
    print(f"  Youden-J: p* = {j_threshold:.4f}")

    yp_subset = yp_m4[subset_mask]
    nb21_def = (yp_subset >= j_threshold)
    n_def = int(nb21_def.sum())
    n_rej = int((~nb21_def).sum())
    print(f"  NB21 hybrid deferred: {n_def}, eval-rej: {n_rej}")

    nb22_def_subset = regression_labels[mask][subset_mask]
    disagreement = int(np.sum(nb21_def != nb22_def_subset))
    disagreement_rate = disagreement / len(nb22_def_subset) if len(nb22_def_subset) else 0
    print(f"  NB21 hybrid vs NB22 disagreement: {disagreement}/{len(nb22_def_subset)} "
          f"= {disagreement_rate * 100:.1f}%")

    both = int(np.sum(nb21_def & nb22_def_subset))
    either = int(np.sum(nb21_def | nb22_def_subset))
    jac = both / max(either, 1)
    print(f"  Deferred Jaccard: {jac:.3f}")

    # ── M5 on hybrid features ──
    print("\n── M5 (NB22 supervision) on hybrid features ──")
    # Use LAB-approached non-click subset to be comparable to LAB M5 numbers
    min_dist_lab = np.array([r["min_dist"] for r in lab_records], dtype=float)
    approached_lab = min_dist_lab < 100
    subset_m5 = approached_lab & (~was_clicked) & valid
    X_m5 = X_hy[subset_m5]
    y_m5 = regression_labels[subset_m5].astype(int)
    groups_m5 = groups_all[subset_m5]
    print(f"  n = {len(y_m5):,}  (class balance: "
          f"{int(y_m5.sum())} deferred / {int((1 - y_m5).sum())} eval-rej)")
    auc_m5, m5_mean, m5_sd, _, yp_m5 = loso_auc(X_m5, y_m5, groups_m5, "M5 hybrid")

    fpr5, tpr5, thr5 = roc_curve(y_m5, yp_m5)
    j5 = int(np.argmax(tpr5 - fpr5))
    thr_m5 = float(thr5[j5])
    yp_m5_pred = (yp_m5 >= thr_m5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_m5, yp_m5_pred).ravel()
    prec5 = tp / max(tp + fp, 1)
    rec5 = tp / max(tp + fn, 1)
    f1_5 = 2 * prec5 * rec5 / max(prec5 + rec5, 1e-9)
    m5_disagree = (fp + fn) / len(y_m5)
    print(f"  Youden-J: p* = {thr_m5:.4f}")
    print(f"  M5 hybrid precision: {prec5 * 100:.1f}%")
    print(f"  M5 hybrid recall:    {rec5 * 100:.1f}%")
    print(f"  M5 hybrid F1:        {f1_5:.3f}")
    print(f"  M5 hybrid label disagreement vs NB22: {m5_disagree * 100:.1f}%")

    # ── Four-way comparison ──
    print("\n" + "=" * 76)
    print("FOUR-WAY COMPARISON: LAB | MM v1 | xpath | hybrid (Option D)")
    print("=" * 76)
    print(f"\n{'Metric':<30s} {'LAB':>10s} {'MM v1':>10s} {'xpath':>10s} {'hybrid':>10s}")
    print("-" * 80)

    lab_row = {"M1": 0.613, "M2": 0.743, "M3": 0.859, "M4": 0.861,
               "NB21": 0.454, "M5": 0.208, "n": 13419}
    mmv1_row = {"M1": 0.573, "M2": 0.811, "M3": 0.801, "M4": 0.801,
                "NB21": 0.536, "M5": 0.256, "n": 9076}
    xpath_row = {"M1": 0.5712, "M2": 0.5912, "M3": 0.6711, "M4": 0.6765,
                 "NB21": 0.319, "M5": 0.231, "n": 6781}
    hyb_row = {"M1": auc_m1, "M2": auc_m2, "M3": auc_m3, "M4": auc_m4,
               "NB21": disagreement_rate, "M5": m5_disagree,
               "n": int(mask.sum())}

    for k in ["M1", "M2", "M3", "M4"]:
        label = k + " AUC"
        print(f"{label:<30s} "
              f"{lab_row[k]:>10.4f} {mmv1_row[k]:>10.4f} "
              f"{xpath_row[k]:>10.4f} {hyb_row[k]:>10.4f}")
    print()
    print(f"{'NB21 disagree vs NB22':<30s} "
          f"{lab_row['NB21'] * 100:>9.1f}% {mmv1_row['NB21'] * 100:>9.1f}% "
          f"{xpath_row['NB21'] * 100:>9.1f}% {hyb_row['NB21'] * 100:>9.1f}%")
    print(f"{'M5 disagree vs NB22':<30s} "
          f"{lab_row['M5'] * 100:>9.1f}% {mmv1_row['M5'] * 100:>9.1f}% "
          f"{xpath_row['M5'] * 100:>9.1f}% {hyb_row['M5'] * 100:>9.1f}%")
    print(f"{'Records':<30s} "
          f"{lab_row['n']:>10,} {mmv1_row['n']:>10,} "
          f"{xpath_row['n']:>10,} {hyb_row['n']:>10,}")

    ratio = disagreement_rate / max(m5_disagree, 1e-9)
    print(f"\nhybrid supervision-signal ratio (NB21 / M5): {ratio:.2f}×")

    summary = {
        "experiment": "Option D — hybrid xpath-grounded + linear-fallback feature extractor",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_records": len(hy_records),
        "n_records_aligned_to_lab": int(mask.sum()),
        "coverage_vs_lab": float(int(mask.sum()) / n),
        "xpath_grounded_records": int(xpath_count),
        "linear_fallback_records": int(linear_count),
        "xpath_grounded_fraction": float(xpath_count / len(hy_records)),
        "click_prediction": {
            "M1_auc": auc_m1, "M2_auc": auc_m2,
            "M3_auc": auc_m3, "M4_auc": auc_m4,
            "m4_vs_m3_delta": float(auc_m4 - auc_m3),
        },
        "nb21_classifier_threshold": {
            "youden_j": j_threshold,
            "n_deferred": n_def, "n_eval_rej": n_rej,
            "disagreement_vs_nb22": float(disagreement_rate),
            "deferred_jaccard_vs_nb22": float(jac),
        },
        "m5_supervision_bootstrap": {
            "loso_auc": auc_m5,
            "youden_j": thr_m5,
            "precision_deferred": float(prec5),
            "recall_deferred": float(rec5),
            "f1_deferred": float(f1_5),
            "label_disagreement": float(m5_disagree),
            "supervision_signal_ratio": float(ratio),
        },
        "four_way_comparison": {
            "LAB": lab_row,
            "mousemove_full_trial": mmv1_row,
            "xpath_dom_only": xpath_row,
            "hybrid_option_d": hyb_row,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
