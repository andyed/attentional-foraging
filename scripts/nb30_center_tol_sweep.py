"""CENTER_TOL sweep — sensitivity of vt_center_ms (which is in the minimal
6-feature emission) to the ±px threshold defining "near viewport center."

PAUSE_VEL_THRESHOLD is not swept because pause_ms is dropped from the
minimal set (K17: collinear with vt_any).

Grid: CENTER_TOL ∈ {25, 50, 100, 200, 400} px.
Report: pooled + per-p LOPO AUC on the minimal 6-feature set at each
threshold; paired Wilcoxon vs canonical CENTER_TOL = 100 px.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))
from data_loader import get_trial_meta, load_mouse_events, result_bands

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)

MINIMAL_FEATURES = ["vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac",
                    "min_abs_velocity", "n_reversals"]


def compute_with_center_tol(trial_id, center_tol, n_positions=10):
    """Re-implementation of compute_features_for_trial but parameterized on
    CENTER_TOL (affects vt_center_ms). PAUSE_VEL_THRESHOLD is kept at 5.0
    because pause_ms is not in the minimal feature set."""
    try:
        doc_h, scr_h, _ = get_trial_meta(trial_id)
    except Exception:
        return None
    events, scrolls, _ = load_mouse_events(trial_id)
    if not events:
        return None
    ts = [e[0] for e in events]
    t_start, t_end = min(ts), max(ts)
    if t_end <= t_start:
        return None

    bands = result_bands(n_positions, doc_h)
    third = scr_h / 3.0
    center_y_vp = scr_h / 2.0
    PAUSE = 5.0
    CENTER = float(center_tol)

    timeline = [(t_start, 0.0)]
    for (t, y) in sorted(scrolls):
        if t_start <= t <= t_end:
            timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    out = []
    for _ in range(n_positions):
        out.append({
            "vt_any": 0.0, "vt_center_ms": 0.0, "_sum_center_y": 0.0,
            "_max_overlap_frac": 0.0, "_max_abs_v": 0.0, "_min_abs_v": 1e9,
            "_reversals": 0, "_last_v_sign": 0, "_entered": False,
        })

    for (t0, y0), (t1, y1) in zip(timeline, timeline[1:]):
        dt_s = (t1 - t0) / 1000.0
        dt_ms = t1 - t0
        if dt_ms <= 0:
            continue
        v = (y1 - y0) / dt_s if dt_s > 0 else 0.0
        abs_v = abs(v)
        vp_top = y0
        vp_bot = y0 + scr_h

        for p, (a_top, a_bot) in enumerate(bands):
            ov_top = max(a_top, vp_top)
            ov_bot = min(a_bot, vp_bot)
            if ov_bot <= ov_top:
                continue
            out[p]["vt_any"] += dt_ms
            center_vp_y = (a_top + a_bot) / 2.0 - y0
            if abs(center_vp_y - center_y_vp) <= CENTER:
                out[p]["vt_center_ms"] += dt_ms
            out[p]["_sum_center_y"] += center_vp_y * dt_ms
            overlap_frac = (ov_bot - ov_top) / (a_bot - a_top)
            if overlap_frac > out[p]["_max_overlap_frac"]:
                out[p]["_max_overlap_frac"] = overlap_frac
            if abs_v > out[p]["_max_abs_v"]:
                out[p]["_max_abs_v"] = abs_v
            if abs_v < out[p]["_min_abs_v"]:
                out[p]["_min_abs_v"] = abs_v
            sign_v = 0 if abs_v < 1e-6 else (1 if v > 0 else -1)
            if out[p]["_last_v_sign"] != 0 and sign_v != 0 and sign_v != out[p]["_last_v_sign"]:
                out[p]["_reversals"] += 1
            if sign_v != 0:
                out[p]["_last_v_sign"] = sign_v
            out[p]["_entered"] = True

    results = []
    for p in range(n_positions):
        r = out[p]
        vt_any = r["vt_any"]
        avg_vp_y = (r["_sum_center_y"] / vt_any) if vt_any > 0 else 0.0
        if r["_min_abs_v"] >= 1e9:
            r["_min_abs_v"] = 0.0
        results.append({
            "vt_any": r["vt_any"],
            "vt_center_ms": r["vt_center_ms"],
            "avg_viewport_y": avg_vp_y,
            "max_overlap_frac": r["_max_overlap_frac"],
            "min_abs_velocity": r["_min_abs_v"],
            "n_reversals": r["_reversals"],
        })
    return results


def lopo(X, y, groups):
    pipe = lambda: Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(np.unique(groups)))
    pred = np.zeros(len(y), dtype=float)
    per_p = []
    for tr, te in gkf.split(X, y, groups=groups):
        m = pipe()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        pred[te] = p
        if len(np.unique(y[te])) == 2:
            per_p.append(roc_auc_score(y[te], p))
    return roc_auc_score(y, pred), np.array(per_p)


def main():
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    trials = sorted({r["trial_id"] for r in raw})
    grid = [25, 50, 100, 200, 400]

    canonical_per_p = None
    rows = []
    for ct in grid:
        print(f"CENTER_TOL = {ct} px...")
        per_trial = {}
        for tid in trials:
            feats = compute_with_center_tol(tid, ct)
            if feats is not None:
                per_trial[tid] = feats
        feat_rows, keep = [], []
        for i, r in enumerate(raw):
            if r["trial_id"] not in per_trial or r["position"] >= 10:
                continue
            feat_rows.append(per_trial[r["trial_id"]][r["position"]])
            keep.append(i)
        keep = np.array(keep)
        raw_k = [raw[i] for i in keep]
        md = np.array([r["min_dist"] for r in raw_k])
        wc = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
        subset = (md < 100) & ~wc
        y = labels[keep][subset].astype(int)
        parts = np.array([r["trial_id"].split("-")[0] for r in raw_k])[subset]
        X = np.array([[float(f.get(n, 0.0) or 0.0) for n in MINIMAL_FEATURES] for f in feat_rows])[subset]

        pooled, per_p = lopo(X, y, parts)
        if ct == 100:
            canonical_per_p = per_p
        rows.append({"center_tol": ct, "pooled": float(pooled),
                     "per_p_mean": float(per_p.mean()), "per_p_sd": float(per_p.std(ddof=1)),
                     "per_p": per_p.tolist()})
        print(f"  pooled AUC = {pooled:.4f}   per-p mean = {per_p.mean():.4f}")

    print("\n── Paired Wilcoxon vs CENTER_TOL = 100 px (canonical) ──")
    for row in rows:
        if row["center_tol"] == 100:
            continue
        per_p = np.array(row["per_p"])
        d = per_p - canonical_per_p
        try:
            w = wilcoxon(per_p, canonical_per_p, alternative="two-sided")
            p_val = float(w.pvalue)
        except Exception:
            p_val = float("nan")
        print(f"  {row['center_tol']:3d} px vs 100 px: Δ per-p = {d.mean():+.4f}  p = {p_val:.4f}")

    # Summary: flat vs peaked
    pooled_vals = [r["pooled"] for r in rows]
    max_v = max(pooled_vals)
    min_v = min(pooled_vals)
    spread = max_v - min_v
    print(f"\nPooled AUC spread across CENTER_TOL ∈ {grid}: {spread:.4f}")
    if spread < 0.005:
        print("  VERDICT: FLAT — CENTER_TOL is not a load-bearing hyperparameter.")
    else:
        print(f"  VERDICT: PEAKED — CENTER_TOL matters; report robustness band.")

    (OUT / "center_tol_sweep.json").write_text(json.dumps({
        "grid": grid, "rows": rows, "pooled_spread": spread,
    }, indent=2))
    print(f"\nwrote {OUT / 'center_tol_sweep.json'}")


if __name__ == "__main__":
    main()
