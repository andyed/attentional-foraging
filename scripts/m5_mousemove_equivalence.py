"""Mousemove-only feature extractor equivalence test (Path B from the
paper-v3 audit). Answers: do the nine cursor approach features computed
*without* fixation gating (i.e., the way the approach-retreat library
computes them in production) match the LAB gaze-gated features used to
train M5 in cursor-approach-features.json?

The test:
  1. For each (trial_id, position) record in cursor-approach-features.json,
     recompute the nine features from scratch using *only* mousemove events
     (no fixation data at all), relative to the same result position.
  2. Compare feature-by-feature against the LAB gaze-gated values:
     Pearson r, Spearman ρ, mean absolute error, median |Δ|, and a
     distribution summary.
  3. Optionally refit M5 on the mousemove-only features and report LOSO
     AUC vs the LAB-trained M5's 0.794 — establishing whether M5's
     training signal transfers through the feature-extractor change.

The semantic difference:
  LAB extractor (notebooks-v2/15_cursor_approach.ipynb):
    for each fixation on result R, interpolate cursor at fixation time,
    record distance to R's band center; aggregate the 9 features over
    the set of per-fixation cursor samples.

  Library / production extractor (this script):
    for every mousemove sample in the trial, compute distance to each
    result R's band center; aggregate the 9 features over the full trial
    of mousemove samples per result. No gaze data used at any step.

The populations differ by which (trial, position) pairs are kept: the LAB
extractor only emits records for positions that received fixations. For
the equivalence test we only compare the (trial_id, position) pairs that
exist in both feature files; the mousemove-only version would produce
extra records we ignore.

Outputs:
  scripts/output/m5_mousemove_equivalence/mousemove_features.json
  scripts/output/m5_mousemove_equivalence/feature_comparison.json
  scripts/output/m5_mousemove_equivalence/m5_mousemove_summary.json
  scripts/output/m5_mousemove_equivalence/results.txt
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    extract_serp_results, get_trial_meta, load_mouse_events,
    interpolate_scroll, result_band_tops,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/m5_mousemove_equivalence"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

PROX_THRESHOLD = 100  # px, matches LAB extractor


def compute_library_episode_features(trial_id, prox_threshold=PROX_THRESHOLD):
    """Library-faithful cursor-approach episode feature extraction.

    Mirrors the approach-retreat library's production path: iterate mousemove
    samples, detect cursor-approach episodes (cursor enters the result's
    proximity band, stays, exits), and compute features over the IN-EPISODE
    mousemove samples only. No gaze data at any step.

    For positions with multiple approach episodes, concatenate all in-episode
    samples into one aggregate record. Positions with no episodes are skipped.
    """
    mouse_data = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if mouse_data is None or meta is None:
        return None

    all_events, scrolls, _ = mouse_data
    doc_h, _, _ = meta
    if not all_events:
        return None

    serp = extract_serp_results(trial_id)
    n_results = len(serp) if serp else 10
    tops = result_band_tops(n_results, doc_h)

    # Positional mousemove events only
    positional = [
        (e[0], e[2], e[3]) for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(positional) < 2:
        return None

    ts = np.array([p[0] for p in positional], dtype=np.int64)
    ys = np.array([p[2] for p in positional], dtype=float)

    # Result center Ys (page coordinates)
    centers = {}
    for pos in range(n_results):
        if pos < len(tops) - 1:
            centers[pos] = (tops[pos] + tops[pos + 1]) / 2
        else:
            centers[pos] = (
                tops[pos] + (tops[1] - tops[0]) / 2
                if len(tops) > 1 else tops[pos] + 100
            )

    out = []
    for pos in range(n_results):
        cy = centers[pos]
        dist = np.abs(ys - cy)
        in_prox = dist < prox_threshold
        if not in_prox.any():
            continue

        # Scan for episodes (contiguous runs of in_prox=True)
        episode_ranges = []
        i = 0
        while i < len(in_prox):
            if in_prox[i]:
                start = i
                while i < len(in_prox) and in_prox[i]:
                    i += 1
                episode_ranges.append((start, i))  # [start, end) half-open
            else:
                i += 1
        if not episode_ranges:
            continue

        # Concatenate all in-episode sample indices
        all_idx = np.concatenate([
            np.arange(s, e) for (s, e) in episode_ranges
        ])
        if len(all_idx) < 2:
            continue

        ep_ts = ts[all_idx]
        ep_dist = dist[all_idx]

        min_dist = float(ep_dist.min())
        mean_dist = float(ep_dist.mean())
        final_dist = float(ep_dist[-1])
        min_idx = int(np.argmin(ep_dist))
        retreat_dist = float(ep_dist[-1] - ep_dist[min_idx])

        # Dwell_in_proximity = total in-episode duration
        dwell_ms = 0.0
        for (s, e) in episode_ranges:
            if e - s >= 2:
                dwell_ms += int(ts[e - 1] - ts[s])

        # Velocities across consecutive in-episode samples (within same episode)
        # Use concatenated arrays — velocity across episode boundaries is
        # noisy but the magnitude effect is small at typical mousemove rates.
        if len(ep_ts) >= 2:
            dts = np.diff(ep_ts).astype(float)
            dts[dts == 0] = 1.0
            vels = -np.diff(ep_dist) / dts * 1000.0
            mean_vel = float(vels.mean())
            max_vel = float(vels.max())
            direction_changes = int(np.sum(np.diff(np.sign(vels)) != 0))
            frac_decreasing = float(np.mean(np.diff(ep_dist) < 0))
        else:
            mean_vel = max_vel = 0.0
            direction_changes = 0
            frac_decreasing = 0.0

        out.append({
            "trial_id": trial_id,
            "position": pos,
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


def compute_mousemove_only_features(trial_id, n_results_hint=None):
    """Full-trial mousemove-only feature extraction (Path B v1 — baseline).

    Kept for comparison purposes. Unlike the library-faithful episode
    extractor above, this version computes the 9 features over ALL mousemove
    samples in the trial without any episode segmentation.
    """
    mouse_data = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if mouse_data is None or meta is None:
        return None

    all_events, scrolls, clicks = mouse_data
    doc_h, scr_h, _ = meta
    if not all_events:
        return None

    serp = extract_serp_results(trial_id)
    n_results = len(serp) if serp else (n_results_hint or 10)
    tops = result_band_tops(n_results, doc_h)

    positional = [
        (e[0], e[2], e[3]) for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(positional) < 2:
        return None

    ts = np.array([p[0] for p in positional], dtype=np.int64)
    ys = np.array([p[2] for p in positional], dtype=float)

    centers = {}
    for pos in range(n_results):
        if pos < len(tops) - 1:
            centers[pos] = (tops[pos] + tops[pos + 1]) / 2
        else:
            centers[pos] = (
                tops[pos] + (tops[1] - tops[0]) / 2
                if len(tops) > 1 else tops[pos] + 100
            )

    out = []
    for pos in range(n_results):
        cy = centers[pos]
        dist_abs = np.abs(ys - cy)
        if len(dist_abs) < 2:
            continue

        min_dist = float(dist_abs.min())
        mean_dist = float(dist_abs.mean())
        final_dist = float(dist_abs[-1])
        min_idx = int(np.argmin(dist_abs))
        retreat_dist = float(dist_abs[-1] - dist_abs[min_idx])

        in_prox = dist_abs < PROX_THRESHOLD
        dwell_ms = 0.0
        for i in range(1, len(ts)):
            if in_prox[i]:
                dt = int(ts[i] - ts[i - 1])
                if 0 < dt < 1000:
                    dwell_ms += dt

        if len(ts) >= 2:
            dts = np.diff(ts).astype(float)
            dts[dts == 0] = 1.0
            vels = -np.diff(dist_abs) / dts * 1000.0
            mean_vel = float(vels.mean())
            max_vel = float(vels.max())
            direction_changes = int(np.sum(np.diff(np.sign(vels)) != 0))
            frac_decreasing = float(np.mean(np.diff(dist_abs) < 0))
        else:
            mean_vel = max_vel = 0.0
            direction_changes = 0
            frac_decreasing = 0.0

        out.append({
            "trial_id": trial_id,
            "position": pos,
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


def main():
    print("=" * 70)
    print("M5 mousemove-only equivalence test")
    print("=" * 70)

    print(f"\nloading LAB gaze-gated features from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    print(f"  {len(lab_records):,} records")

    # Group by trial for single-pass mousemove extraction
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    print(f"  {len(trial_ids):,} unique trials")

    print("\ncomputing library-episode mousemove-only features per trial (~4 min)...")
    mousemove_records = []
    skipped_trials = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)} trials")
        recs = compute_library_episode_features(tid)
        if recs is None:
            skipped_trials += 1
            continue
        mousemove_records.extend(recs)
    print(f"  mousemove-only records: {len(mousemove_records):,}")
    print(f"  skipped trials: {skipped_trials}")

    # Cache
    (OUT_DIR / "mousemove_features.json").write_text(
        json.dumps(mousemove_records, indent=1)
    )

    # ── Compare: only pairs that exist in both ──
    mm_index = {(r["trial_id"], r["position"]): r for r in mousemove_records}
    pairs = []
    for lab_r in lab_records:
        key = (lab_r["trial_id"], lab_r["position"])
        if key in mm_index:
            pairs.append((lab_r, mm_index[key]))
    print(f"\nmatched pairs (in both LAB and mousemove): {len(pairs):,}")

    # Per-feature correlations
    print("\n── Per-feature LAB vs mousemove correlation ──")
    print(f"{'feature':>30s}  {'pearson r':>10s}  {'spearman ρ':>11s}  {'MAE':>10s}  {'median|Δ|':>10s}")
    print("-" * 78)
    comparison = {}
    for f in M4_FEATURES:
        lab_vals = np.array([float(p[0].get(f, 0) or 0) for p in pairs])
        mm_vals = np.array([float(p[1].get(f, 0) or 0) for p in pairs])
        # Filter out non-finite
        finite = np.isfinite(lab_vals) & np.isfinite(mm_vals)
        lab_vals = lab_vals[finite]
        mm_vals = mm_vals[finite]
        if len(lab_vals) < 2 or np.std(lab_vals) == 0 or np.std(mm_vals) == 0:
            pear = spear = mae = med_abs = float("nan")
        else:
            pear, _ = pearsonr(lab_vals, mm_vals)
            spear, _ = spearmanr(lab_vals, mm_vals)
            diffs = mm_vals - lab_vals
            mae = float(np.mean(np.abs(diffs)))
            med_abs = float(np.median(np.abs(diffs)))
        print(f"{f:>30s}  {pear:>10.4f}  {spear:>11.4f}  {mae:>10.2f}  {med_abs:>10.2f}")
        comparison[f] = {
            "pearson_r": float(pear) if np.isfinite(pear) else None,
            "spearman_rho": float(spear) if np.isfinite(spear) else None,
            "mae": mae if np.isfinite(mae) else None,
            "median_abs_diff": med_abs if np.isfinite(med_abs) else None,
            "lab_median": float(np.median(lab_vals)),
            "mm_median": float(np.median(mm_vals)),
        }

    (OUT_DIR / "feature_comparison.json").write_text(json.dumps({
        "n_pairs": len(pairs),
        "per_feature": comparison,
    }, indent=2))

    # ── Refit M5 on mousemove-only features and compare to LAB-trained M5 ──
    print("\n── Refitting M5 on mousemove-only features ──")
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(regression_labels) == len(lab_records)

    # Build parallel mousemove feature matrix in lab_records index order
    X_mm = np.zeros((len(lab_records), len(M4_FEATURES)), dtype=float)
    valid = np.zeros(len(lab_records), dtype=bool)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        mm = mm_index.get(key)
        if mm is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X_mm[i, j] = float(mm.get(f, 0) or 0)
        valid[i] = True

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    min_dist_lab = np.array([r["min_dist"] for r in lab_records], dtype=float)
    approached_lab = min_dist_lab < PROX_THRESHOLD  # LAB-defined approach
    subset_mask = approached_lab & ~was_clicked & valid
    n_subset = int(subset_mask.sum())
    print(f"  subset (LAB-approached non-click with mm features): {n_subset:,}")

    X = X_mm[subset_mask]
    y = regression_labels[subset_mask].astype(int)
    groups = np.array([r["trial_id"].split("-")[0] for r in lab_records])[subset_mask]

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(
            max_iter=5000, class_weight="balanced", C=1.0,
        )),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]

    auc = float(roc_auc_score(y, y_proba))
    fpr, tpr, thr = roc_curve(y, y_proba)
    j_idx = int(np.argmax(tpr - fpr))
    j_threshold = float(thr[j_idx])
    y_pred = (y_proba >= j_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    label_err = (fp + fn) / max(len(y), 1)

    print(f"  mousemove M5 LOSO AUC: {auc:.4f}")
    print(f"  Youden-J threshold:    {j_threshold:.4f}")
    print(f"  Confusion: tp={tp} fn={fn} fp={fp} tn={tn}")
    print(f"  Precision (deferred):  {precision * 100:.1f}%")
    print(f"  Recall (deferred):     {recall * 100:.1f}%")
    print(f"  F1 (deferred):         {f1:.3f}")
    print(f"  Label disagreement:    {label_err * 100:.1f}%")
    print()
    print(f"  LAB M5 for comparison: AUC 0.7935, precision 90.2%, recall 83.4%, F1 0.867, disagreement 20.8%")
    print(f"  ΔAUC (mm - LAB):       {auc - 0.7935:+.4f}")

    summary = {
        "experiment": "M5 mousemove-only equivalence test",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_matched_pairs": len(pairs),
        "n_m5_subset": int(n_subset),
        "m5_mousemove": {
            "loso_auc": auc,
            "youden_j_threshold": j_threshold,
            "confusion_matrix": {
                "tp": int(tp), "fn": int(fn), "fp": int(fp), "tn": int(tn),
            },
            "precision_deferred": float(precision),
            "recall_deferred": float(recall),
            "f1_deferred": float(f1),
            "label_disagreement": float(label_err),
        },
        "m5_lab_reference": {
            "loso_auc": 0.7935,
            "precision_deferred": 0.902,
            "recall_deferred": 0.834,
            "f1_deferred": 0.867,
            "label_disagreement": 0.208,
        },
        "m5_delta": {
            "delta_auc": float(auc - 0.7935),
            "delta_precision": float(precision - 0.902),
            "delta_recall": float(recall - 0.834),
            "delta_label_disagreement": float(label_err - 0.208),
        },
        "per_feature_equivalence": comparison,
    }
    (OUT_DIR / "m5_mousemove_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'm5_mousemove_summary.json'}")


if __name__ == "__main__":
    main()
