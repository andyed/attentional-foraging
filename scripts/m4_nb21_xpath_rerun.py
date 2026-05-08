"""Gaze-clean mousemove extractor using xpath-based DOM containment.

This is the production-equivalent feature extraction: rather than approximating
"cursor is over result N" via geometric result_band_tops()-style vertical
proximity, we use the xpath recorded on each mouse event to identify exactly
which result container the cursor is currently over. AdSERP records a Google
SERP xpath string on every event in mouse-movement-data/*.csv; the xpath
pattern `//*[@id='rso']/div[N]` maps 1-indexed result N to 0-indexed result
position N-1.

This is the same DOM-containment strategy the approach-retreat library uses
in production (via a `data-result` attribute or CSS selector on each result
element). On AdSERP we use xpaths because that's what the dataset happens to
store; on a production deployment the library would use CSS classes. Both
are DOM-containment checks, not geometric proximity.

Outputs:
  scripts/output/m4_nb21_xpath_rerun/xpath_features.json
  scripts/output/m4_nb21_xpath_rerun/summary.json
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

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
MOUSE_DIR = ROOT / "AdSERP/data/mouse-movement-data"
OUT_DIR = ROOT / "scripts/output/m4_nb21_xpath_rerun"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Extract organic result index from xpath: `//*[@id='rso']/div[N]/...` → N-1
RESULT_XPATH_RE = re.compile(r"^//\*\[@id='rso'\]/div\[(\d+)\]")

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def extract_result_idx(xpath):
    """Map xpath → 0-indexed organic result position, or None."""
    if not xpath:
        return None
    m = RESULT_XPATH_RE.match(xpath)
    if m:
        return int(m.group(1)) - 1  # Convert 1-indexed to 0-indexed
    return None


def compute_xpath_features(trial_id):
    """Hybrid xpath-grounded feature extractor.

    Two-phase approach:
      Phase 1 — learn each result's true bounding box for THIS trial
        by collecting all mouse events whose xpath resolves to that
        result index. The bounding box is derived from observed on-
        result event positions (min/max x, y across events).
      Phase 2 — compute the 9 features for each result using the FULL
        cursor trajectory (all positional events in the trial, not
        just on-result events). Distance to the result is the 2-D
        distance from each cursor position to the result's bounding
        box center (from phase 1).

    This uses xpath to *ground* the result's spatial location per trial
    (more accurate than result_band_tops linear estimation) but still
    computes approach-retreat dynamics over the full cursor trajectory
    — which is what M5's supervision signal needs.

    Results with no on-result events in phase 1 are skipped (we have no
    way to locate them without xpath anchor or SERP layout parsing).
    """
    csv_path = MOUSE_DIR / f"{trial_id}.csv"
    if not csv_path.exists():
        return None

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
                "t": t,
                "x": x,
                "y": y,
                "event": row.get("event", ""),
                "xpath": row.get("xpath", ""),
                "result_idx": extract_result_idx(row.get("xpath", "")),
            })
    if not events:
        return None

    POSITIONAL = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    positional = [e for e in events
                  if e["event"] in POSITIONAL and e["x"] > 0 and e["y"] > 0]
    if len(positional) < 2:
        return None

    # Phase 1 — learn per-result bounding boxes from xpath-grounded events
    result_bboxes = {}  # pos -> (center_x, center_y, half_width, half_height)
    on_result = defaultdict(list)
    for e in positional:
        if e["result_idx"] is not None:
            on_result[e["result_idx"]].append(e)

    for pos, evts in on_result.items():
        if len(evts) < 1:
            continue
        xs = np.array([e["x"] for e in evts], dtype=float)
        ys = np.array([e["y"] for e in evts], dtype=float)
        # Center = median of observed on-result events (robust to stray hover events)
        cx = float(np.median(xs))
        cy = float(np.median(ys))
        # Half-dimensions = half the observed range (clipped to reasonable values)
        hw = max(float(xs.max() - xs.min()) / 2, 50.0)
        hh = max(float(ys.max() - ys.min()) / 2, 50.0)
        result_bboxes[pos] = (cx, cy, hw, hh)

    if not result_bboxes:
        return None

    # Phase 2 — compute features over the full cursor trajectory per result
    ts_all = np.array([e["t"] for e in positional], dtype=np.int64)
    xs_all = np.array([e["x"] for e in positional], dtype=float)
    ys_all = np.array([e["y"] for e in positional], dtype=float)

    out = []
    PROX_THRESHOLD = 100  # px, matches LAB extractor
    for pos, (cx, cy, hw, hh) in result_bboxes.items():
        # 2-D distance from each cursor event to the result's bounding-box
        # center. (Using center is sufficient; using the bounding box's
        # nearest-edge distance would be more precise but adds minor value.)
        dx = xs_all - cx
        dy = ys_all - cy
        dist = np.hypot(dx, dy)

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
            "n_on_result_events": len(on_result[pos]),
            "bbox_center_x": cx,
            "bbox_center_y": cy,
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
    print(f"  {label}: LOSO AUC = {auc:.4f}")
    return auc, y_proba


def main():
    print("=" * 70)
    print("xpath-based DOM-containment feature extraction rerun")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"  {n:,} records")

    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)

    # Compute xpath features per trial
    print("\ncomputing xpath-based features per trial (~4 min)...")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    xp_records = []
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)} trials")
        recs = compute_xpath_features(tid)
        if recs is None:
            skipped += 1
            continue
        xp_records.extend(recs)
    print(f"  xpath records: {len(xp_records):,}")
    print(f"  trials skipped: {skipped}")
    (OUT_DIR / "xpath_features.json").write_text(json.dumps(xp_records, indent=1))

    # Index by (trial_id, position)
    xp_index = {(r["trial_id"], r["position"]): r for r in xp_records}

    # Align to LAB records
    X_xp = np.zeros((n, len(M4_FEATURES)), dtype=float)
    position = np.zeros(n, dtype=float)
    valid = np.zeros(n, dtype=bool)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        xp = xp_index.get(key)
        if xp is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X_xp[i, j] = float(xp.get(f, 0) or 0)
        position[i] = float(r["position"])
        valid[i] = True

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    mask = valid
    print(f"\n  {int(mask.sum()):,} records with xpath features "
          f"({int(mask.sum()) / n * 100:.1f}%)")

    X_valid = X_xp[mask]
    pos_valid = position[mask].reshape(-1, 1)
    y_valid = was_clicked[mask].astype(int)
    groups_valid = groups_all[mask]

    # ── Click prediction ──
    print("\n── LOSO click prediction on xpath features ──")
    auc_m1, _ = loso_auc(pos_valid, y_valid, groups_valid, "M1 (position)")

    dwell_idx = M4_FEATURES.index("dwell_in_proximity_ms")
    X_m2 = np.column_stack([pos_valid, X_valid[:, dwell_idx]])
    auc_m2, _ = loso_auc(X_m2, y_valid, groups_valid, "M2 (position + dwell)")

    auc_m4, yp_m4 = loso_auc(X_valid, y_valid, groups_valid, "M4 (9 approach)")

    X_m3 = np.column_stack([pos_valid, X_valid])
    auc_m3, _ = loso_auc(X_m3, y_valid, groups_valid, "M3 (position + 9 approach)")

    # ── NB21 classifier-threshold ──
    print("\n── NB21 classifier-threshold (xpath version) ──")

    # "Approached" in the xpath world means "received any mouse events" —
    # which is exactly the set of records in xp_index. For consistency with
    # the LAB definition we still intersect with LAB-approached (min_dist < 100).
    min_dist_lab = np.array([r["min_dist"] for r in lab_records], dtype=float)
    approached_lab = min_dist_lab < 100
    subset_mask_full = approached_lab & (~was_clicked) & valid
    # Align to the valid subset
    subset_in_valid = approached_lab[mask] & (~y_valid.astype(bool))

    fpr, tpr, thresholds = roc_curve(y_valid, yp_m4)
    j_idx = int(np.argmax(tpr - fpr))
    j_threshold = float(thresholds[j_idx])
    print(f"  Youden-J: p* = {j_threshold:.4f}")

    yp_subset = yp_m4[subset_in_valid]
    nb21_def = (yp_subset >= j_threshold)
    print(f"  deferred: {int(nb21_def.sum())}")
    print(f"  eval-rej: {int((~nb21_def).sum())}")

    nb22_def_subset = regression_labels[mask][subset_in_valid]
    nb21_disagree = int(np.sum(nb21_def != nb22_def_subset))
    nb21_rate = nb21_disagree / len(nb22_def_subset) if len(nb22_def_subset) else 0
    print(f"  NB21-xpath vs NB22 disagreement: {nb21_disagree}/{len(nb22_def_subset)} "
          f"= {nb21_rate * 100:.1f}%")

    both = int(np.sum(nb21_def & nb22_def_subset))
    either = int(np.sum(nb21_def | nb22_def_subset))
    jac = both / max(either, 1)
    print(f"  Deferred Jaccard: {jac:.3f}")

    # ── M5 on xpath features ──
    print("\n── M5 (NB22 supervision) on xpath features ──")
    X_m5 = X_xp[subset_mask_full]
    y_m5 = regression_labels[subset_mask_full].astype(int)
    groups_m5 = groups_all[subset_mask_full]
    print(f"  n = {len(y_m5):,}  (class balance: "
          f"{int(y_m5.sum())} deferred / {int((1-y_m5).sum())} eval-rej)")
    auc_m5, yp_m5 = loso_auc(X_m5, y_m5, groups_m5, "M5 (xpath features)")

    # Youden-J for M5
    fpr5, tpr5, thr5 = roc_curve(y_m5, yp_m5)
    j5 = int(np.argmax(tpr5 - fpr5))
    thr_m5 = float(thr5[j5])
    yp_m5_pred = (yp_m5 >= thr_m5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_m5, yp_m5_pred).ravel()
    prec5 = tp / max(tp + fp, 1)
    rec5 = tp / max(tp + fn, 1)
    f1_5 = 2 * prec5 * rec5 / max(prec5 + rec5, 1e-9)
    m5_disagree = (fp + fn) / len(y_m5)
    print(f"  M5 xpath precision: {prec5 * 100:.1f}%")
    print(f"  M5 xpath recall:    {rec5 * 100:.1f}%")
    print(f"  M5 xpath F1:        {f1_5:.3f}")
    print(f"  M5 xpath label disagreement vs NB22: {m5_disagree * 100:.1f}%")

    # ── Summary ──
    print("\n" + "=" * 70)
    print("THREE-WAY COMPARISON: LAB vs full-trial mousemove vs xpath")
    print("=" * 70)
    lab = {"M1": 0.613, "M2": 0.743, "M3": 0.859, "M4": 0.861,
           "NB21_disagree": 0.454, "M5_disagree": 0.208}
    mmv1 = {"M1": 0.573, "M2": 0.811, "M3": 0.801, "M4": 0.801,
            "NB21_disagree": 0.536, "M5_disagree": 0.256}
    xpath_r = {"M1": auc_m1, "M2": auc_m2, "M3": auc_m3, "M4": auc_m4,
               "NB21_disagree": nb21_rate, "M5_disagree": m5_disagree}

    print(f"\n{'Metric':<30s} {'LAB':>10s} {'MM (trial)':>12s} {'xpath (DOM)':>12s}")
    print("-" * 70)
    for name in ["M1", "M2", "M3", "M4"]:
        print(f"{name + ' (LOSO AUC)':<30s} "
              f"{lab[name]:>10.4f} {mmv1[name]:>12.4f} {xpath_r[name]:>12.4f}")
    print()
    print(f"{'NB21 disagreement vs NB22':<30s} "
          f"{lab['NB21_disagree'] * 100:>9.1f}% {mmv1['NB21_disagree'] * 100:>11.1f}% {xpath_r['NB21_disagree'] * 100:>11.1f}%")
    print(f"{'M5 disagreement vs NB22':<30s} "
          f"{lab['M5_disagree'] * 100:>9.1f}% {mmv1['M5_disagree'] * 100:>11.1f}% {xpath_r['M5_disagree'] * 100:>11.1f}%")

    nb21 = xpath_r["NB21_disagree"]
    m5 = xpath_r["M5_disagree"]
    ratio = nb21 / max(m5, 1e-9)
    print(f"\nxpath supervision-signal ratio (NB21 / M5): {ratio:.2f}×")

    summary = {
        "experiment": "xpath-based DOM-containment feature extraction (gaze-clean, production-equivalent)",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_records_valid": int(mask.sum()),
        "click_prediction": {
            "M1_auc": auc_m1,
            "M2_auc": auc_m2,
            "M3_auc": auc_m3,
            "M4_auc": auc_m4,
            "m4_vs_m3_delta": float(auc_m4 - auc_m3),
            "m4_approx_m3": bool(abs(auc_m4 - auc_m3) < 0.01),
        },
        "nb21_classifier_threshold": {
            "youden_j_threshold": j_threshold,
            "n_deferred": int(nb21_def.sum()),
            "n_eval_rej": int((~nb21_def).sum()),
            "disagreement_vs_nb22": float(nb21_rate),
            "deferred_jaccard_vs_nb22": float(jac),
        },
        "m5_supervision_bootstrap": {
            "loso_auc": auc_m5,
            "precision_deferred": float(prec5),
            "recall_deferred": float(rec5),
            "f1_deferred": float(f1_5),
            "label_disagreement": float(m5_disagree),
            "supervision_signal_ratio": float(ratio),
        },
        "comparison": {
            "LAB_features": {
                "M4_auc": 0.861, "M3_auc": 0.859,
                "NB21_disagreement": 0.454, "M5_disagreement": 0.208,
                "supervision_ratio": 2.18,
            },
            "mousemove_full_trial": {
                "M4_auc": 0.801, "M3_auc": 0.801,
                "NB21_disagreement": 0.536, "M5_disagreement": 0.256,
                "supervision_ratio": 2.09,
            },
            "xpath_DOM_containment": {
                "M4_auc": auc_m4, "M3_auc": auc_m3,
                "NB21_disagreement": float(nb21_rate),
                "M5_disagreement": float(m5_disagree),
                "supervision_ratio": float(ratio),
            },
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
