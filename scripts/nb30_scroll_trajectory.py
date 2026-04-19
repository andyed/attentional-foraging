"""NB30 prototype — does scroll TRAJECTORY add AUC beyond viewport analytics?

Population: approached (min_dist < 100) AND NOT clicked, per M5/NB28 convention.
Label: NB22 gaze-regression (1 = deferred, 0 = eval-rejected). [LAB] only.

Feature sets:
  A  — Viewport bands (NB28 operationalization)         : 4 features per AOI
       vt_any, vt_top, vt_mid, vt_bot
  B  — Continuous viewport analytics (industry-standard): 4 features per AOI
       vt_any, vt_center_ms (time near viewport center),
       avg_viewport_y (mean AOI center viewport-y during visibility),
       max_visibility_fraction (max overlap with viewport)
  C  — Trajectory features (the question)               : 7 features per AOI
       max_abs_velocity, min_abs_velocity, pause_ms,
       n_reversals, max_decel_near_center, entry_velocity, exit_velocity

Nested LOPO LR (47-fold):
  AUC_A, AUC_B, AUC_C
  AUC_A∪C, AUC_B∪C
  Headline ΔAUC:
    C beats A     (trajectory beats bands alone)
    C beats B     (trajectory beats continuous viewport)
    A∪C beats A   (trajectory adds on top of bands)
    B∪C beats B   (trajectory adds on top of continuous viewport) — KEY

If the key paired Wilcoxon (B∪C − B) is not significant: NB17's scroll null
holds even under residualization — on desktop, cursor owns evaluation and
scroll adds nothing beyond where-you-parked-the-viewport.
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
OUT_DIR = ROOT / "scripts/output/nb30_scroll_trajectory"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAUSE_VEL_THRESHOLD = 5.0  # px/s; under this counts as "pause"
CENTER_TOL = 100.0  # px around viewport center for "near center"


def compute_features_for_trial(trial_id, n_positions=10, max_t=None, min_t=None):
    """Returns per-position dict with A (bands), B (continuous viewport), C (trajectory).
    None if data missing. If max_t is provided, the timeline is truncated at max_t
    (leakage check; K15 uses max_t = click_t). If min_t is provided, the timeline
    starts at min_t (windowing; Exp 6 uses min_t = click_t - 5000)."""
    try:
        doc_h, scr_h, _ = get_trial_meta(trial_id)
    except Exception:
        return None
    events, scrolls, _ = load_mouse_events(trial_id)
    if not events:
        return None
    ts = [e[0] for e in events]
    t_start, t_end = min(ts), max(ts)
    if max_t is not None:
        t_end = min(t_end, max_t)
    if min_t is not None:
        t_start = max(t_start, min_t)
    if t_end <= t_start:
        return None

    bands = result_bands(n_positions, doc_h)
    third = scr_h / 3.0
    center_y_viewport = scr_h / 2.0

    # Build timeline: (t, scrollY) piecewise-constant
    timeline = [(t_start, 0.0)]
    for (t, y) in sorted(scrolls):
        if t_start <= t <= t_end:
            timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    # Per-position accumulators
    out = []
    for p in range(n_positions):
        out.append({
            # A: bands
            "vt_any": 0.0, "vt_top": 0.0, "vt_mid": 0.0, "vt_bot": 0.0,
            # B: continuous viewport
            "vt_center_ms": 0.0,      # ms with AOI-center within ±CENTER_TOL of viewport center
            "_sum_center_y": 0.0,     # weighted sum for avg_viewport_y
            "_max_overlap_frac": 0.0, # max fraction of AOI visible
            # C: trajectory — ms-weighted stats; computed as running accumulators
            "_max_abs_v": 0.0,
            "_min_abs_v": 1e9,
            "_pause_ms": 0.0,
            "_reversals": 0,
            "_last_v_sign": 0,
            "_max_decel_near_center": 0.0,
            "_prev_v": None,
            "_prev_t": None,
            "_entered": False,
            "_entry_v": 0.0,
            "_exit_v": 0.0,
        })

    # Iterate adjacent timeline segments; each segment has a constant velocity
    # implied by the NEXT scroll event (forward difference). Piecewise-constant
    # scroll-y → velocity is a discretized derivative.
    for idx, ((t0, y0), (t1, y1)) in enumerate(zip(timeline, timeline[1:])):
        dt_s = (t1 - t0) / 1000.0  # seconds
        dt_ms = t1 - t0
        if dt_ms <= 0:
            continue
        # velocity for THIS segment: use forward diff between y0 and y1
        v = (y1 - y0) / dt_s if dt_s > 0 else 0.0
        abs_v = abs(v)
        vp_top, vp_bot = y0, y0 + scr_h

        for p, (a_top, a_bot) in enumerate(bands):
            # Overlap check: AOI intersect viewport at scroll-y y0
            overlap_top = max(a_top, vp_top)
            overlap_bot = min(a_bot, vp_bot)
            if overlap_bot <= overlap_top:
                # no overlap — if previously entered, record exit velocity
                if out[p]["_entered"] and out[p]["_exit_v"] == 0.0:
                    out[p]["_exit_v"] = abs_v
                continue

            # Overlap exists — update A features
            out[p]["vt_any"] += dt_ms
            center_vp_y = (a_top + a_bot) / 2.0 - y0
            if 0 <= center_vp_y < third:
                out[p]["vt_top"] += dt_ms
            elif third <= center_vp_y < 2 * third:
                out[p]["vt_mid"] += dt_ms
            elif 2 * third <= center_vp_y <= scr_h:
                out[p]["vt_bot"] += dt_ms

            # B features
            if abs(center_vp_y - center_y_viewport) <= CENTER_TOL:
                out[p]["vt_center_ms"] += dt_ms
            out[p]["_sum_center_y"] += center_vp_y * dt_ms
            overlap_frac = (overlap_bot - overlap_top) / (a_bot - a_top)
            if overlap_frac > out[p]["_max_overlap_frac"]:
                out[p]["_max_overlap_frac"] = overlap_frac

            # C features
            if abs_v > out[p]["_max_abs_v"]:
                out[p]["_max_abs_v"] = abs_v
            if abs_v < out[p]["_min_abs_v"]:
                out[p]["_min_abs_v"] = abs_v
            if abs_v < PAUSE_VEL_THRESHOLD:
                out[p]["_pause_ms"] += dt_ms
            sign_v = 0 if abs_v < 1e-6 else (1 if v > 0 else -1)
            if out[p]["_last_v_sign"] != 0 and sign_v != 0 and sign_v != out[p]["_last_v_sign"]:
                out[p]["_reversals"] += 1
            if sign_v != 0:
                out[p]["_last_v_sign"] = sign_v
            # deceleration near center
            if out[p]["_prev_v"] is not None and out[p]["_prev_t"] is not None:
                dt_between = (t0 - out[p]["_prev_t"]) / 1000.0
                if dt_between > 0 and abs(center_vp_y - center_y_viewport) <= CENTER_TOL:
                    decel = (out[p]["_prev_v"] - abs_v) / dt_between  # +ve = slowing
                    if decel > out[p]["_max_decel_near_center"]:
                        out[p]["_max_decel_near_center"] = decel
            out[p]["_prev_v"] = abs_v
            out[p]["_prev_t"] = t0
            if not out[p]["_entered"]:
                out[p]["_entered"] = True
                out[p]["_entry_v"] = abs_v

    # Finalize continuous features
    results = []
    for p in range(n_positions):
        r = out[p]
        vt_any = r["vt_any"]
        avg_vp_y = (r["_sum_center_y"] / vt_any) if vt_any > 0 else 0.0
        if r["_min_abs_v"] >= 1e9:
            r["_min_abs_v"] = 0.0
        results.append({
            # A
            "vt_any": r["vt_any"],
            "vt_top": r["vt_top"],
            "vt_mid": r["vt_mid"],
            "vt_bot": r["vt_bot"],
            # B
            "vt_center_ms": r["vt_center_ms"],
            "avg_viewport_y": avg_vp_y,
            "max_overlap_frac": r["_max_overlap_frac"],
            # C
            "max_abs_velocity": r["_max_abs_v"],
            "min_abs_velocity": r["_min_abs_v"],
            "pause_ms": r["_pause_ms"],
            "n_reversals": r["_reversals"],
            "max_decel_near_center": r["_max_decel_near_center"],
            "entry_velocity": r["_entry_v"],
            "exit_velocity": r["_exit_v"],
        })
    return results


FEATURES_A = ["vt_any", "vt_top", "vt_mid", "vt_bot"]
FEATURES_B = ["vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac"]
FEATURES_C = ["max_abs_velocity", "min_abs_velocity", "pause_ms", "n_reversals",
              "max_decel_near_center", "entry_velocity", "exit_velocity"]


def lopo_auc(X, y, groups, seeds=(0,)):
    """Leave-one-participant-out LR. Returns per-sample predicted probs AND
    per-participant AUC (mean of held-out AUCs).
    Linear LR is deterministic, so seeds is kept for API parity."""
    pipe = lambda: Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(np.unique(groups)))
    pred = np.zeros(len(y), dtype=float)
    per_p_auc = []
    for fold_i, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=groups)):
        m = pipe()
        m.fit(X[train_idx], y[train_idx])
        p = m.predict_proba(X[test_idx])[:, 1]
        pred[test_idx] = p
        # per-participant AUC on held-out
        if len(np.unique(y[test_idx])) == 2:
            per_p_auc.append(roc_auc_score(y[test_idx], p))
    pooled_auc = roc_auc_score(y, pred) if len(np.unique(y)) == 2 else float("nan")
    return pooled_auc, float(np.mean(per_p_auc)), np.array(per_p_auc)


def per_participant_auc_list(X, y, groups):
    """Return per-participant held-out AUC vector aligned to participant ids."""
    gkf = GroupKFold(n_splits=len(np.unique(groups)))
    ids, aucs = [], []
    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        m = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
        ])
        m.fit(X[train_idx], y[train_idx])
        p = m.predict_proba(X[test_idx])[:, 1]
        pid = groups[test_idx][0]
        if len(np.unique(y[test_idx])) == 2:
            ids.append(pid)
            aucs.append(roc_auc_score(y[test_idx], p))
    return np.array(ids), np.array(aucs)


def main():
    print("=" * 72)
    print("NB30 — Does scroll trajectory add AUC beyond viewport analytics?")
    print("=" * 72)

    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(labels) == len(raw)

    trials = sorted({r["trial_id"] for r in raw})
    print(f"\ntrials: {len(trials):,}  features rows: {len(raw):,}")

    print("\ncomputing trajectory + viewport features per trial...")
    per_trial = {}
    missing = 0
    for i, tid in enumerate(trials):
        feats = compute_features_for_trial(tid, n_positions=10)
        if feats is None:
            missing += 1
            continue
        per_trial[tid] = feats
        if (i + 1) % 400 == 0:
            print(f"  {i+1}/{len(trials)} (missing so far: {missing})")
    print(f"done. computed: {len(per_trial):,}  missing meta/events: {missing}")

    # ── Join features to (trial, position, label) rows ──
    keep_idx = []
    feat_rows = []
    for i, r in enumerate(raw):
        tid = r["trial_id"]
        pos = r["position"]
        if tid not in per_trial or pos >= 10:
            continue
        f = per_trial[tid][pos]
        feat_rows.append(f)
        keep_idx.append(i)
    keep_idx = np.array(keep_idx)
    labels_k = labels[keep_idx]
    raw_k = [raw[i] for i in keep_idx]
    print(f"rows after viewport+trajectory join: {len(raw_k):,}")

    min_dist = np.array([r["min_dist"] for r in raw_k])
    was_clicked = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
    approached = min_dist < 100
    subset = approached & ~was_clicked
    print(f"\napproached ∧ ¬clicked: {int(subset.sum()):,}")
    print(f"  deferred: {int((subset & labels_k).sum()):,}")
    print(f"  eval-rejected: {int((subset & ~labels_k).sum()):,}")

    # Subset arrays
    def feat_matrix(names):
        return np.array([[float(f.get(n, 0.0) or 0.0) for n in names] for f in feat_rows])[subset]

    y = labels_k[subset].astype(int)
    participants = np.array([r["trial_id"].split("-")[0] for r in raw_k])[subset]

    X_A = feat_matrix(FEATURES_A)
    X_B = feat_matrix(FEATURES_B)
    X_C = feat_matrix(FEATURES_C)
    X_AC = np.hstack([X_A, X_C])
    X_BC = np.hstack([X_B, X_C])
    X_ABC = np.hstack([X_A, X_B, X_C])

    print("\n── Pooled AUC (LOPO) ──")
    def run(tag, X):
        pooled, mean_p, per_p = lopo_auc(X, y, participants)
        print(f"  {tag:32s}  pooled AUC = {pooled:.4f}   "
              f"per-p mean = {mean_p:.4f} ± {per_p.std(ddof=1):.4f} (n={len(per_p)})")
        return pooled, mean_p, per_p

    res = {}
    for tag, X in [("A bands (NB28)", X_A),
                   ("B continuous viewport", X_B),
                   ("C trajectory", X_C),
                   ("A ∪ C", X_AC),
                   ("B ∪ C", X_BC),
                   ("A ∪ B ∪ C", X_ABC)]:
        res[tag] = run(tag, X)

    # Paired Wilcoxon on per-participant AUCs
    print("\n── Paired Wilcoxon on per-participant held-out AUCs (one-sided) ──")
    def paired(tag_a, tag_b):
        _, _, a = res[tag_a]
        _, _, b = res[tag_b]
        if len(a) != len(b):
            # Align by re-computing on same fold-order; lopo_auc uses same GroupKFold split
            # so len should match
            m = min(len(a), len(b))
            a, b = a[:m], b[:m]
        d = a - b
        try:
            w = wilcoxon(a, b, alternative="greater")
            W, p = float(w.statistic), float(w.pvalue)
        except Exception:
            W, p = float("nan"), float("nan")
        print(f"  {tag_a:32s} > {tag_b:28s}  "
              f"Δ = {d.mean():+.4f} ± {d.std(ddof=1):.4f}   "
              f"{int((a >= b).sum())}/{len(a)}   p = {p:.4f}")
        return {"delta": float(d.mean()), "sd": float(d.std(ddof=1)),
                "a_ge_b": int((a >= b).sum()), "n": len(a), "W": W, "p": p}

    comparisons = {}
    comparisons["C > A"]       = paired("C trajectory", "A bands (NB28)")
    comparisons["C > B"]       = paired("C trajectory", "B continuous viewport")
    comparisons["A ∪ C > A"]   = paired("A ∪ C", "A bands (NB28)")
    comparisons["B ∪ C > B"]   = paired("B ∪ C", "B continuous viewport")
    comparisons["A ∪ B ∪ C > B ∪ C"] = paired("A ∪ B ∪ C", "B ∪ C")

    summary = {
        "n_rows_used": int(subset.sum()),
        "n_deferred": int((subset & labels_k).sum()),
        "n_eval_rejected": int((subset & ~labels_k).sum()),
        "n_participants": int(len(np.unique(participants))),
        "features_A": FEATURES_A,
        "features_B": FEATURES_B,
        "features_C": FEATURES_C,
        "pooled_auc": {k: {"pooled": v[0], "per_p_mean": v[1]} for k, v in res.items()},
        "paired_wilcoxon": comparisons,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
