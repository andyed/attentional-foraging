"""Phase-restricted feature-extraction ablation.

§3.2 of paper-v3 claims OSEC Evaluate-phase approach-episode windowing
is where the signal lives. The canonical Option D extractor in
`m4_nb21_hybrid_rerun.py` is spatially proximity-weighted (via min_dist
and dwell_in_proximity_ms) but NOT temporally phase-gated — it aggregates
features over the whole-trial cursor stream. This script runs the
phase-restriction check §3.2 implicitly claims:

  - Whole-trial (baseline, matches §4.1 headline): AUC ≈ 0.821
  - Post-Survey only (t ≥ fixations[5].t, OSEC Evaluate+Commit phase):
    expected ≈ 0.82 if the causal claim is right
  - Survey-only (t < fixations[5].t, OSEC Survey phase):
    expected near-chance if the causal claim is right

SURVEY_END = 5 is lifted from notebooks-v2/13_survey_phase.ipynb's OSEC
operationalization: "saccades 1-5 are survey".

For each trial we compute the nine M4 features against per-result centers
under each of the three time-window restrictions, then run LOSO M4 click
prediction on each.

Output: scripts/output/phase_restricted_ablation/summary.json
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
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    get_trial_meta, load_fixations, result_band_tops, organic_aoi_tops,
)

import argparse as _argparse
_ap = _argparse.ArgumentParser()
_ap.add_argument('--attribution', choices=['absolute', 'organic'], default='organic',
                 help='organic (default; bbox-attributed) or absolute (legacy h3+ads pooled)')
_ARGS = _ap.parse_args()
_OUT_SUFFIX = '_organic' if _ARGS.attribution == 'organic' else ''
print(f'[attribution] {_ARGS.attribution}', file=sys.stderr)

if _ARGS.attribution == 'organic':
    FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features-organic.json"
else:
    FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
MOUSE_DIR = ROOT / "AdSERP/data/mouse-movement-data"
OUT_DIR = ROOT / "scripts/output/phase_restricted_ablation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RESULT_XPATH_RE = re.compile(r"^//\*\[@id='rso'\]/div\[(\d+)\]")

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

SURVEY_END = 5  # NB13: saccades 1-5 are Survey phase
PROX_THRESHOLD = 100
N_RESULTS_DEFAULT = 10


def extract_result_idx(xpath):
    if not xpath:
        return None
    m = RESULT_XPATH_RE.match(xpath)
    if m:
        return int(m.group(1)) - 1
    return None


def load_mouse_events(trial_id):
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
                "t": t, "x": x, "y": y,
                "event": row.get("event", ""),
                "result_idx": extract_result_idx(row.get("xpath", "")),
            })
    return events


def get_survey_boundary_t(trial_id):
    """Return the timestamp at the end of the SURVEY_END-th fixation.
    This is the Survey → Evaluate boundary per OSEC (NB13)."""
    fixations = load_fixations(trial_id)
    if fixations is None or len(fixations) <= SURVEY_END:
        return None
    fix = fixations[SURVEY_END]
    # fix['t'] is start, fix['d'] is duration — use end of the fixation
    return int(fix["t"] + fix.get("d", 0))


def compute_features_with_time_window(trial_id, window, n_results=N_RESULTS_DEFAULT):
    """window ∈ {"whole", "survey", "post_survey"}.

    Returns list of per-result feature dicts or None on skip.
    """
    events = load_mouse_events(trial_id)
    if not events:
        return None

    POSITIONAL = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    positional = [e for e in events
                  if e["event"] in POSITIONAL and e["x"] > 0 and e["y"] > 0]
    if len(positional) < 2:
        return None

    # Phase 1a — xpath-grounded centers (computed on ALL events, not just the
    # window — centers are trial-invariant geometric anchors).
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

    # Phase 1b — linear fallback centers for remaining positions
    meta = get_trial_meta(trial_id)
    if meta is None:
        return None
    doc_h, _, _ = meta
    try:
        if _ARGS.attribution == 'organic':
            tops = organic_aoi_tops(trial_id)
            n_results = len(tops)
            if n_results == 0:
                return None
        else:
            tops = result_band_tops(n_results, doc_h)
    except Exception:
        return None
    linear_centers = {}
    for pos in range(n_results):
        if pos < len(tops) - 1:
            cy = (tops[pos] + tops[pos + 1]) / 2
        else:
            cy = tops[pos] + (tops[1] - tops[0]) / 2 if len(tops) > 1 else tops[pos] + 100
        linear_centers[pos] = (
            float(np.median([e["x"] for e in positional])),
            float(cy),
        )

    # Phase 2 — apply the time-window filter to positional events
    if window == "whole":
        windowed = positional
    else:
        boundary_t = get_survey_boundary_t(trial_id)
        if boundary_t is None:
            return None
        if window == "survey":
            windowed = [e for e in positional if e["t"] < boundary_t]
        elif window == "post_survey":
            windowed = [e for e in positional if e["t"] >= boundary_t]
        else:
            raise ValueError(f"unknown window: {window}")
    if len(windowed) < 2:
        return None

    ts_all = np.array([e["t"] for e in windowed], dtype=np.int64)
    ys_all = np.array([e["y"] for e in windowed], dtype=float)

    out = []
    for pos in range(n_results):
        if pos in xpath_centers:
            _, cy = xpath_centers[pos]
        else:
            _, cy = linear_centers[pos]

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

        dts = np.diff(ts_all).astype(float)
        dts[dts == 0] = 1.0
        vels = -np.diff(dist) / dts * 1000.0
        mean_vel = float(vels.mean())
        max_vel = float(vels.max())
        direction_changes = int(np.sum(np.diff(np.sign(vels)) != 0))
        frac_decreasing = float(np.mean(np.diff(dist) < 0))

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


def build_feature_matrix(lab_records, window):
    """For the given time window, compute features per trial and align
    to the LAB record order. Returns (X, valid_mask)."""
    print(f"\n── building features for window = '{window}' ──")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    hy_records = []
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)}  (skipped {skipped})")
        recs = compute_features_with_time_window(tid, window)
        if recs is None:
            skipped += 1
            continue
        hy_records.extend(recs)
    print(f"  records: {len(hy_records):,}   trials skipped: {skipped}")
    hy_index = {(r["trial_id"], r["position"]): r for r in hy_records}

    n = len(lab_records)
    X = np.zeros((n, len(M4_FEATURES)), dtype=float)
    valid = np.zeros(n, dtype=bool)
    for i, r in enumerate(lab_records):
        hy = hy_index.get((r["trial_id"], r["position"]))
        if hy is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X[i, j] = float(hy.get(f, 0) or 0)
        valid[i] = True
    return X, valid


def loso_auc(X, y, groups, label):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf,
        method="predict_proba", n_jobs=1,
    )[:, 1]
    auc = float(roc_auc_score(y, y_proba))
    print(f"  {label}: LOSO AUC = {auc:.4f}  (n={len(y)}, pos_rate={y.mean():.3f})")
    return auc


def main():
    print("=" * 70)
    print("Phase-restricted extraction ablation")
    print("=" * 70)

    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"\nloaded {n:,} LAB records")

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    results = {}
    for window in ("whole", "post_survey", "survey"):
        X, valid = build_feature_matrix(lab_records, window)
        y = was_clicked[valid].astype(int)
        g = groups_all[valid]
        Xv = X[valid]
        print(f"\n── LOSO click prediction, window = '{window}' ──")
        auc = loso_auc(Xv, y, g, f"M4 ({window})")
        results[window] = {
            "n_records": int(valid.sum()),
            "coverage": float(valid.sum() / n),
            "click_rate": float(y.mean()),
            "m4_auc": auc,
        }

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for window, d in results.items():
        print(f"  {window:>14s}  AUC = {d['m4_auc']:.4f}   "
              f"n = {d['n_records']:,}   cov = {d['coverage']:.3f}")

    print("\nInterpretation:")
    whole = results["whole"]["m4_auc"]
    post = results["post_survey"]["m4_auc"]
    survey = results["survey"]["m4_auc"]
    print(f"  post_survey vs whole: Δ = {post - whole:+.4f}")
    print(f"  survey      vs whole: Δ = {survey - whole:+.4f}")
    if post >= whole - 0.02 and survey < whole - 0.10:
        print("  → Consistent with OSEC Evaluate-phase causal claim.")
    elif survey >= whole - 0.02:
        print("  → NOT consistent with phase-specific signal; features generalize across phases.")
    else:
        print("  → Partial support; interpret carefully.")

    summary = {
        "experiment": "Phase-restricted feature-extraction ablation",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "survey_end_fixation_index": SURVEY_END,
        "results": results,
    }
    summary['attribution'] = _ARGS.attribution
    out_path = OUT_DIR / f"summary{_OUT_SUFFIX}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
