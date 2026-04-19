"""NB30 pre-implementation ablations.

Runs the must-run experiments before we freeze the approach-retreat library
feature set:

  Exp 1 (LOFO on C): leave-one-of-7-out, keep B fixed, 47-fold LOPO, paired
         Wilcoxon vs full B∪C, Holm-Bonferroni over 7 tests.
  Exp 2 (Redundancy): Spearman correlation matrix + VIF on the 11 B∪C
         features. Flag |r| > 0.85 or VIF > 10.
  Exp 3 (Event-rate): decimate scroll events to 30/10/5/2 Hz, recompute B∪C,
         pooled + per-p LOPO AUC at each rate.
  Exp 4 (Hyperparam sweep): grid over PAUSE_VEL_THRESHOLD × CENTER_TOL.
  Exp 5 (LGBM vs LR): LGBMClassifier on B∪C, 47-fold LOPO, compare AUC.

Writes scripts/output/nb30_ablations/summary.json + per-experiment detail
files.
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, wilcoxon
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
from nb30_scroll_trajectory import (
    compute_features_for_trial,
    FEATURES_A, FEATURES_B, FEATURES_C,
    PAUSE_VEL_THRESHOLD, CENTER_TOL,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)


def load_data():
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(labels) == len(raw)
    return raw, labels


def compute_feature_rows(raw, labels, feature_fn, label="default"):
    """Wrapper: for each unique trial, run feature_fn(trial_id) (which returns
    per-position feature dicts of length 10), then join to raw row order.
    Returns (feat_rows, keep_idx, labels_k)."""
    trials = sorted({r["trial_id"] for r in raw})
    print(f"  [{label}] computing features for {len(trials):,} trials...")
    per_trial = {}
    missing = 0
    for i, tid in enumerate(trials):
        feats = feature_fn(tid)
        if feats is None:
            missing += 1
            continue
        per_trial[tid] = feats
    print(f"  [{label}] computed: {len(per_trial):,}  missing: {missing}")

    keep_idx = []
    feat_rows = []
    for i, r in enumerate(raw):
        tid, pos = r["trial_id"], r["position"]
        if tid not in per_trial or pos >= 10:
            continue
        feat_rows.append(per_trial[tid][pos])
        keep_idx.append(i)
    keep_idx = np.array(keep_idx)
    labels_k = labels[keep_idx]
    return feat_rows, keep_idx, labels_k


def subset_arrays(feat_rows, keep_idx, labels_k, raw, names):
    """Return X, y, participants for the approached∧¬clicked subset."""
    raw_k = [raw[i] for i in keep_idx]
    min_dist = np.array([r["min_dist"] for r in raw_k])
    was_clicked = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
    subset = (min_dist < 100) & ~was_clicked
    y = labels_k[subset].astype(int)
    participants = np.array([r["trial_id"].split("-")[0] for r in raw_k])[subset]
    X = np.array([[float(f.get(n, 0.0) or 0.0) for n in names] for f in feat_rows])[subset]
    return X, y, participants


def lopo_auc(X, y, groups):
    pipe = lambda: Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(np.unique(groups)))
    pred = np.zeros(len(y), dtype=float)
    per_p = []
    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        m = pipe()
        m.fit(X[train_idx], y[train_idx])
        p = m.predict_proba(X[test_idx])[:, 1]
        pred[test_idx] = p
        if len(np.unique(y[test_idx])) == 2:
            per_p.append(roc_auc_score(y[test_idx], p))
    return roc_auc_score(y, pred), np.array(per_p)


def exp1_lofo(feat_rows, keep_idx, labels_k, raw):
    """Leave-one-of-7-out on C, keep B fixed. Paired Wilcoxon vs full B∪C.
    Holm-Bonferroni correction over 7 tests."""
    print("\n" + "=" * 72)
    print("EXP 1 — LOFO on C (leave-one-out over 7 trajectory features)")
    print("=" * 72)
    X_BC_full, y, pids = subset_arrays(feat_rows, keep_idx, labels_k, raw, FEATURES_B + FEATURES_C)
    pooled_full, per_p_full = lopo_auc(X_BC_full, y, pids)
    print(f"\n  full B∪C         pooled AUC = {pooled_full:.4f}   "
          f"per-p mean = {per_p_full.mean():.4f}")

    lofo_rows = []
    for drop_feat in FEATURES_C:
        reduced_names = FEATURES_B + [f for f in FEATURES_C if f != drop_feat]
        X_red, _, _ = subset_arrays(feat_rows, keep_idx, labels_k, raw, reduced_names)
        pooled_red, per_p_red = lopo_auc(X_red, y, pids)
        delta_pooled = pooled_full - pooled_red
        delta_per_p = per_p_full - per_p_red
        try:
            w = wilcoxon(per_p_full, per_p_red, alternative="greater")
            p_raw = float(w.pvalue)
        except Exception:
            p_raw = float("nan")
        lofo_rows.append({
            "drop": drop_feat,
            "pooled_full": pooled_full,
            "pooled_reduced": pooled_red,
            "delta_pooled": delta_pooled,
            "delta_per_p_mean": float(delta_per_p.mean()),
            "full_ge_red": int((per_p_full >= per_p_red).sum()),
            "n": len(per_p_full),
            "p_raw": p_raw,
        })
    # Holm-Bonferroni
    sorted_rows = sorted(lofo_rows, key=lambda r: r["p_raw"])
    n_tests = len(sorted_rows)
    for rank, row in enumerate(sorted_rows, 1):
        row["p_holm"] = min(1.0, row["p_raw"] * (n_tests - rank + 1))
        row["keep"] = row["p_holm"] < 0.05  # keep if full > reduced significantly
    print(f"\n  LOFO results (sorted by raw p, Holm-adj α=0.05):")
    print(f"  {'drop feature':28s}  ΔAUC   ΔAUC_p  win/n  p_raw   p_holm  verdict")
    print("  " + "-" * 80)
    for r in sorted_rows:
        v = "KEEP (drop hurts)" if r["keep"] else "drop-candidate"
        print(f"  {r['drop']:28s}  {r['delta_pooled']:+.4f}  {r['delta_per_p_mean']:+.4f}  "
              f"{r['full_ge_red']:2d}/{r['n']}  {r['p_raw']:.4f}  {r['p_holm']:.4f}  {v}")
    return {"lofo": sorted_rows,
            "full_pooled_auc": pooled_full,
            "full_per_p_mean": float(per_p_full.mean())}


def exp2_redundancy(feat_rows, keep_idx, labels_k, raw):
    """Spearman + VIF on the 11 features. Flag |r| > 0.85 or VIF > 10."""
    print("\n" + "=" * 72)
    print("EXP 2 — Redundancy audit (Spearman + VIF on B ∪ C)")
    print("=" * 72)
    names = FEATURES_B + FEATURES_C
    X, y, pids = subset_arrays(feat_rows, keep_idx, labels_k, raw, names)

    # Spearman pairwise on the 2,351-row sample
    n = len(names)
    rho = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                rho[i, j] = 1.0
            else:
                rho[i, j] = spearmanr(X[:, i], X[:, j]).correlation

    flagged_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if abs(rho[i, j]) >= 0.85:
                flagged_pairs.append({"a": names[i], "b": names[j], "rho": float(rho[i, j])})

    # VIF — fit each feature against the others, VIF = 1/(1-R²)
    # Use StandardScaler then linear regression via sklearn closed-form.
    from sklearn.linear_model import LinearRegression
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    vifs = []
    for i, name in enumerate(names):
        others = np.delete(Xs, i, axis=1)
        m = LinearRegression()
        m.fit(others, Xs[:, i])
        r2 = m.score(others, Xs[:, i])
        vif = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
        vifs.append({"name": name, "r2": float(r2), "vif": float(vif),
                     "flag_vif_gt_10": vif > 10})

    print(f"\n  Spearman |r| ≥ 0.85 pairs:")
    if flagged_pairs:
        for pr in flagged_pairs:
            print(f"    {pr['a']:28s} <-> {pr['b']:28s}  r = {pr['rho']:+.3f}")
    else:
        print("    (none)")
    print(f"\n  VIF table:")
    print(f"  {'feature':28s}  R²     VIF    flag")
    print("  " + "-" * 55)
    for v in sorted(vifs, key=lambda x: -x["vif"]):
        flag = "HIGH (>10)" if v["flag_vif_gt_10"] else ""
        print(f"  {v['name']:28s}  {v['r2']:.3f}  {v['vif']:6.2f}   {flag}")
    return {"rho_matrix": rho.tolist(),
            "feature_order": names,
            "flagged_pairs": flagged_pairs,
            "vif": vifs}


def _decimated_feature_fn(hz):
    """Return a closure that computes features using scroll events decimated
    to approximately hz Hz. 'Decimate' = drop events so that the minimum
    inter-event dt is 1/hz seconds; the first event and the end anchor are
    always kept."""
    min_dt_ms = 1000.0 / hz

    def inner(trial_id, n_positions=10):
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

        # Decimate: keep a scroll only if it's at least min_dt_ms after the
        # previous kept scroll. Always keep the first and last.
        scrolls_sorted = sorted(scrolls)
        kept = []
        last_t = -1e18
        for (t, y) in scrolls_sorted:
            if not (t_start <= t <= t_end):
                continue
            if t - last_t >= min_dt_ms:
                kept.append((t, y))
                last_t = t
        if scrolls_sorted and scrolls_sorted[-1] not in kept:
            if t_start <= scrolls_sorted[-1][0] <= t_end:
                kept.append(scrolls_sorted[-1])

        # Monkey-patch: call compute_features_for_trial's timeline by reusing
        # load_mouse_events results but substituting the decimated scrolls.
        # Simplest: re-implement the core with kept scrolls. We do so by
        # temporarily replacing the raw scrolls list. But compute_features_for_trial
        # calls load_mouse_events internally. Refactor: inline the core logic.
        return _compute_from_scrolls(doc_h, scr_h, kept, t_start, t_end, n_positions)

    return inner


def _compute_from_scrolls(doc_h, scr_h, kept_scrolls, t_start, t_end, n_positions):
    """Re-implementation of compute_features_for_trial core that takes the
    pre-decimated scrolls directly. Mirrors compute_features_for_trial."""
    bands = result_bands(n_positions, doc_h)
    third = scr_h / 3.0
    center_y_viewport = scr_h / 2.0

    timeline = [(t_start, 0.0)]
    for (t, y) in kept_scrolls:
        timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    out = []
    for _ in range(n_positions):
        out.append({
            "vt_any": 0.0, "vt_top": 0.0, "vt_mid": 0.0, "vt_bot": 0.0,
            "vt_center_ms": 0.0, "_sum_center_y": 0.0, "_max_overlap_frac": 0.0,
            "_max_abs_v": 0.0, "_min_abs_v": 1e9, "_pause_ms": 0.0,
            "_reversals": 0, "_last_v_sign": 0, "_max_decel_near_center": 0.0,
            "_prev_v": None, "_prev_t": None, "_entered": False,
            "_entry_v": 0.0, "_exit_v": 0.0,
        })

    PAUSE = 5.0
    CENTER = 100.0
    for (t0, y0), (t1, y1) in zip(timeline, timeline[1:]):
        dt_s = (t1 - t0) / 1000.0
        dt_ms = t1 - t0
        if dt_ms <= 0:
            continue
        v = (y1 - y0) / dt_s if dt_s > 0 else 0.0
        abs_v = abs(v)
        vp_top, vp_bot = y0, y0 + scr_h
        for p, (a_top, a_bot) in enumerate(bands):
            overlap_top = max(a_top, vp_top)
            overlap_bot = min(a_bot, vp_bot)
            if overlap_bot <= overlap_top:
                if out[p]["_entered"] and out[p]["_exit_v"] == 0.0:
                    out[p]["_exit_v"] = abs_v
                continue
            out[p]["vt_any"] += dt_ms
            center_vp_y = (a_top + a_bot) / 2.0 - y0
            if 0 <= center_vp_y < third:
                out[p]["vt_top"] += dt_ms
            elif third <= center_vp_y < 2 * third:
                out[p]["vt_mid"] += dt_ms
            elif 2 * third <= center_vp_y <= scr_h:
                out[p]["vt_bot"] += dt_ms
            if abs(center_vp_y - center_y_viewport) <= CENTER:
                out[p]["vt_center_ms"] += dt_ms
            out[p]["_sum_center_y"] += center_vp_y * dt_ms
            overlap_frac = (overlap_bot - overlap_top) / (a_bot - a_top)
            if overlap_frac > out[p]["_max_overlap_frac"]:
                out[p]["_max_overlap_frac"] = overlap_frac
            if abs_v > out[p]["_max_abs_v"]:
                out[p]["_max_abs_v"] = abs_v
            if abs_v < out[p]["_min_abs_v"]:
                out[p]["_min_abs_v"] = abs_v
            if abs_v < PAUSE:
                out[p]["_pause_ms"] += dt_ms
            sign_v = 0 if abs_v < 1e-6 else (1 if v > 0 else -1)
            if out[p]["_last_v_sign"] != 0 and sign_v != 0 and sign_v != out[p]["_last_v_sign"]:
                out[p]["_reversals"] += 1
            if sign_v != 0:
                out[p]["_last_v_sign"] = sign_v
            if out[p]["_prev_v"] is not None and out[p]["_prev_t"] is not None:
                dt_between = (t0 - out[p]["_prev_t"]) / 1000.0
                if dt_between > 0 and abs(center_vp_y - center_y_viewport) <= CENTER:
                    decel = (out[p]["_prev_v"] - abs_v) / dt_between
                    if decel > out[p]["_max_decel_near_center"]:
                        out[p]["_max_decel_near_center"] = decel
            out[p]["_prev_v"] = abs_v
            out[p]["_prev_t"] = t0
            if not out[p]["_entered"]:
                out[p]["_entered"] = True
                out[p]["_entry_v"] = abs_v

    results = []
    for p in range(n_positions):
        r = out[p]
        vt_any = r["vt_any"]
        avg_vp_y = (r["_sum_center_y"] / vt_any) if vt_any > 0 else 0.0
        if r["_min_abs_v"] >= 1e9:
            r["_min_abs_v"] = 0.0
        results.append({
            "vt_any": r["vt_any"], "vt_top": r["vt_top"], "vt_mid": r["vt_mid"], "vt_bot": r["vt_bot"],
            "vt_center_ms": r["vt_center_ms"], "avg_viewport_y": avg_vp_y,
            "max_overlap_frac": r["_max_overlap_frac"],
            "max_abs_velocity": r["_max_abs_v"], "min_abs_velocity": r["_min_abs_v"],
            "pause_ms": r["_pause_ms"], "n_reversals": r["_reversals"],
            "max_decel_near_center": r["_max_decel_near_center"],
            "entry_velocity": r["_entry_v"], "exit_velocity": r["_exit_v"],
        })
    return results


def exp3_event_rate(raw, labels):
    """Decimate scroll events and measure AUC degradation."""
    print("\n" + "=" * 72)
    print("EXP 3 — Event-rate sensitivity (decimate scroll events)")
    print("=" * 72)

    rates = [("native", None), ("30Hz", 30), ("10Hz", 10), ("5Hz", 5), ("2Hz", 2)]
    rows = []
    for label, hz in rates:
        feature_fn = _decimated_feature_fn(hz) if hz else compute_features_for_trial
        feat_rows, keep_idx, labels_k = compute_feature_rows(raw, labels, feature_fn, label=label)
        X_BC, y, pids = subset_arrays(feat_rows, keep_idx, labels_k, raw, FEATURES_B + FEATURES_C)
        X_B, _, _  = subset_arrays(feat_rows, keep_idx, labels_k, raw, FEATURES_B)
        pooled_BC, per_p_BC = lopo_auc(X_BC, y, pids)
        pooled_B, per_p_B = lopo_auc(X_B, y, pids)
        delta = per_p_BC - per_p_B
        try:
            w = wilcoxon(per_p_BC, per_p_B, alternative="greater")
            p_val = float(w.pvalue)
        except Exception:
            p_val = float("nan")
        rows.append({
            "rate_label": label, "hz": hz,
            "B_pooled": pooled_BC, "B_per_p_mean": float(per_p_B.mean()),
            "BC_pooled": pooled_BC, "BC_per_p_mean": float(per_p_BC.mean()),
            "BuC_minus_B_delta_per_p": float(delta.mean()),
            "wilcoxon_p": p_val, "n_participants": len(per_p_BC),
        })
        print(f"  {label:8s}  B pooled = {pooled_B:.4f}  B∪C pooled = {pooled_BC:.4f}  "
              f"Δ(per-p) = {delta.mean():+.4f}  p = {p_val:.4f}")
    return rows


def exp5_lgbm(feat_rows, keep_idx, labels_k, raw):
    """LGBM classifier on B∪C, 47-fold LOPO."""
    print("\n" + "=" * 72)
    print("EXP 5 — LGBM vs LR on B∪C")
    print("=" * 72)
    from lightgbm import LGBMClassifier
    X_BC, y, pids = subset_arrays(feat_rows, keep_idx, labels_k, raw, FEATURES_B + FEATURES_C)
    # LR baseline
    pooled_lr, per_p_lr = lopo_auc(X_BC, y, pids)
    # LGBM
    gkf = GroupKFold(n_splits=len(np.unique(pids)))
    pred = np.zeros(len(y), dtype=float)
    per_p_lgbm = []
    for train_idx, test_idx in gkf.split(X_BC, y, groups=pids):
        m = LGBMClassifier(n_estimators=300, num_leaves=31, learning_rate=0.05,
                           min_child_samples=10, random_state=0, verbose=-1)
        m.fit(X_BC[train_idx], y[train_idx])
        p = m.predict_proba(X_BC[test_idx])[:, 1]
        pred[test_idx] = p
        if len(np.unique(y[test_idx])) == 2:
            per_p_lgbm.append(roc_auc_score(y[test_idx], p))
    pooled_lgbm = roc_auc_score(y, pred)
    per_p_lgbm = np.array(per_p_lgbm)
    delta = per_p_lgbm - per_p_lr
    try:
        w = wilcoxon(per_p_lgbm, per_p_lr, alternative="greater")
        p_val = float(w.pvalue)
    except Exception:
        p_val = float("nan")
    print(f"  LR   pooled = {pooled_lr:.4f}   per-p = {per_p_lr.mean():.4f}")
    print(f"  LGBM pooled = {pooled_lgbm:.4f}  per-p = {per_p_lgbm.mean():.4f}")
    print(f"  Δ(LGBM − LR) per-p = {delta.mean():+.4f}  p = {p_val:.4f}  "
          f"{int((per_p_lgbm >= per_p_lr).sum())}/{len(per_p_lr)}")
    return {
        "lr_pooled": pooled_lr, "lr_per_p_mean": float(per_p_lr.mean()),
        "lgbm_pooled": pooled_lgbm, "lgbm_per_p_mean": float(per_p_lgbm.mean()),
        "delta_per_p": float(delta.mean()),
        "wilcoxon_p": p_val,
        "lgbm_ge_lr": int((per_p_lgbm >= per_p_lr).sum()),
        "n": len(per_p_lr),
    }


def main():
    raw, labels = load_data()

    # Shared compute: canonical (native rate) features — used by Exp 1, 2, 5.
    feat_rows, keep_idx, labels_k = compute_feature_rows(
        raw, labels, lambda tid: compute_features_for_trial(tid, n_positions=10),
        label="native",
    )
    print(f"\nshared feature rows: {len(feat_rows):,}")

    result = {
        "meta": {
            "n_feat_rows": len(feat_rows),
            "PAUSE_VEL_THRESHOLD": PAUSE_VEL_THRESHOLD,
            "CENTER_TOL": CENTER_TOL,
        },
    }

    result["exp1_lofo"] = exp1_lofo(feat_rows, keep_idx, labels_k, raw)
    result["exp2_redundancy"] = exp2_redundancy(feat_rows, keep_idx, labels_k, raw)
    result["exp3_event_rate"] = exp3_event_rate(raw, labels)
    result["exp5_lgbm"] = exp5_lgbm(feat_rows, keep_idx, labels_k, raw)

    (OUT / "summary.json").write_text(json.dumps(result, indent=2, default=float))
    print(f"\nwrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
