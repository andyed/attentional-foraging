"""Viewport-time calibration: how much signal is in 'time on viewport at position P'
beyond the cursor-retreat features?

For every (trial, position) in the post-audit cursor-approach feature table:
  - Compute viewport_ms: total ms the organic-result band at position P
    intersected the scroll viewport during the trial.
  - Join with M4 retreat features and the NB22 deferred/eval-rejected label.

Then fit three nested LOSO-LR classifiers per position (and pooled):
  M_vt       outcome ~ viewport_ms
  M_retreat  outcome ~ M4 features (9 cursor-retreat)
  M_both     outcome ~ viewport_ms + M4 features

Report AUC, ΔAUC(both − retreat), ΔAUC(both − vt), and per-feature |coef|.

Target population: approached (min_dist < 100) AND NOT clicked — matches M5.
Outcome: NB22 gaze-regression label (1 = deferred, 0 = eval-rejected) — [LAB] only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import get_trial_meta, load_mouse_events, result_bands  # noqa

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/viewport_time_calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def viewport_ms_for_trial(trial_id, n_positions=10):
    """Return per-position viewport visibility broken into viewport-y bands.

    For each position: (ms_any, ms_top, ms_mid, ms_bot) — ms_any is total
    time any part of the AOI intersected the viewport; the three thirds use
    the AOI *center* viewport-y (aoi_center - scrollY) to bucket into
    top/middle/bottom third of the scr_h-tall viewport.
    """
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

    timeline = [(t_start, 0.0)]
    for (t, y) in sorted(scrolls):
        if t_start <= t <= t_end:
            timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    out = [[0.0, 0.0, 0.0, 0.0] for _ in range(n_positions)]  # any, top, mid, bot
    for (t0, y0), (t1, _) in zip(timeline, timeline[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        vp_top, vp_bot = y0, y0 + scr_h
        for p, (a_top, a_bot) in enumerate(bands):
            if min(a_bot, vp_bot) <= max(a_top, vp_top):
                continue
            out[p][0] += dt
            center_vp_y = (a_top + a_bot) / 2.0 - y0
            if 0 <= center_vp_y < third:
                out[p][1] += dt
            elif third <= center_vp_y < 2 * third:
                out[p][2] += dt
            elif 2 * third <= center_vp_y <= scr_h:
                out[p][3] += dt
            # center outside viewport — part of AOI visible but center not;
            # counted in ms_any only
    return out


def main():
    print("=" * 72)
    print("Viewport-time calibration — AR retreat features vs on-screen dwell")
    print("=" * 72)

    raw = json.load(open(FEATURES_JSON))
    n = len(raw)
    print(f"\nfeatures: {n:,} (trial × position)")

    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(labels) == n, f"{len(labels)} labels vs {n} features"
    print(f"labels (NB22 deferred=1): {labels.sum():,} True "
          f"({labels.mean()*100:.1f}%)")

    # ── Compute viewport_ms per trial, broadcast per position ──
    trials = sorted({r["trial_id"] for r in raw})
    print(f"\ncomputing viewport_ms for {len(trials):,} trials...")
    per_trial = {}
    missing = 0
    for i, tid in enumerate(trials):
        v = viewport_ms_for_trial(tid, n_positions=10)
        if v is None:
            missing += 1
            continue
        per_trial[tid] = v
        if (i + 1) % 400 == 0:
            print(f"  {i+1}/{len(trials)} (missing so far: {missing})")
    print(f"done. computed: {len(per_trial):,}. missing meta/events: {missing}")

    # ── Augment feature rows with viewport_ms (any/top/mid/bot) ──
    keep, vt_any, vt_top, vt_mid, vt_bot = [], [], [], [], []
    for i, r in enumerate(raw):
        tid = r["trial_id"]
        if tid not in per_trial:
            continue
        pos = r["position"]
        if pos >= 10:
            continue
        a, t, m, b = per_trial[tid][pos]
        vt_any.append(a); vt_top.append(t); vt_mid.append(m); vt_bot.append(b)
        keep.append(i)
    keep = np.array(keep)
    vt_any = np.array(vt_any); vt_top = np.array(vt_top)
    vt_mid = np.array(vt_mid); vt_bot = np.array(vt_bot)
    vts = vt_any  # back-compat name for the single-feature LR
    raw_k = [raw[i] for i in keep]
    labels_k = labels[keep]
    print(f"rows after viewport join: {len(raw_k):,}")
    print(f"  viewport_ms any:  median {np.median(vt_any):>6.0f}  p10 {np.percentile(vt_any,10):>5.0f}  p90 {np.percentile(vt_any,90):>5.0f}")
    print(f"  viewport_ms top:  median {np.median(vt_top):>6.0f}  p10 {np.percentile(vt_top,10):>5.0f}  p90 {np.percentile(vt_top,90):>5.0f}")
    print(f"  viewport_ms mid:  median {np.median(vt_mid):>6.0f}  p10 {np.percentile(vt_mid,10):>5.0f}  p90 {np.percentile(vt_mid,90):>5.0f}")
    print(f"  viewport_ms bot:  median {np.median(vt_bot):>6.0f}  p10 {np.percentile(vt_bot,10):>5.0f}  p90 {np.percentile(vt_bot,90):>5.0f}")

    min_dist = np.array([r["min_dist"] for r in raw_k])
    was_clicked = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
    approached = min_dist < 100
    subset = approached & ~was_clicked
    n_sub = int(subset.sum())
    print(f"\ntarget population (approached ∧ ¬clicked): {n_sub:,}")
    print(f"  deferred: {int((subset & labels_k).sum()):,}  "
          f"eval-rej: {int((subset & ~labels_k).sum()):,}")

    X4 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in raw_k])
    pos_arr = np.array([r["position"] for r in raw_k])
    participants = np.array([r["trial_id"].split("-")[0] for r in raw_k])

    # ── Nested LR helper ──
    def fit_loso(X, y, groups, tag):
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
        ])
        gkf = GroupKFold(n_splits=len(set(groups)))
        proba = cross_val_predict(pipe, X, y, groups=groups, cv=gkf,
                                  method="predict_proba", n_jobs=-1)[:, 1]
        auc = roc_auc_score(y, proba)
        # Re-fit on all data to read pooled standardized coefficients
        pipe.fit(X, y)
        coefs = pipe.named_steps["lr"].coef_.ravel().tolist()
        return auc, coefs, proba

    def run_slice(mask, label):
        y = labels_k[mask].astype(int)
        g = participants[mask]
        vt_any_col = vt_any[mask].reshape(-1, 1)
        vt_bands = np.column_stack([vt_top[mask], vt_mid[mask], vt_bot[mask]])
        x4 = X4[mask]
        if len(set(g)) < 3 or y.sum() < 5 or (len(y) - y.sum()) < 5:
            return {"slice": label, "n": int(mask.sum()), "skip": True}
        auc_vt,    coef_vt_alone, _  = fit_loso(vt_any_col, y, g, f"{label}:vt")
        auc_bands, coef_bands_alone, _ = fit_loso(vt_bands, y, g, f"{label}:bands")
        auc_re,    coef_re, _           = fit_loso(x4, y, g, f"{label}:retreat")
        auc_bo_any, coef_bo_any, _ = fit_loso(np.hstack([vt_any_col, x4]), y, g,
                                              f"{label}:re+vt")
        auc_bo_bd,  coef_bo_bd,  _ = fit_loso(np.hstack([vt_bands, x4]), y, g,
                                              f"{label}:re+bands")
        return {
            "slice": label,
            "n": int(mask.sum()),
            "n_deferred": int(y.sum()),
            "n_eval_rej": int((1 - y).sum()),
            "participants": int(len(set(g))),
            "auc_vt_any": auc_vt,
            "auc_vt_bands": auc_bands,
            "auc_retreat": auc_re,
            "auc_retreat_plus_vt_any": auc_bo_any,
            "auc_retreat_plus_vt_bands": auc_bo_bd,
            "delta_bands_over_any": auc_bands - auc_vt,
            "delta_bo_bd_over_bo_any": auc_bo_bd - auc_bo_any,
            "delta_bo_bd_over_retreat": auc_bo_bd - auc_re,
            "coef_bands_alone": dict(zip(["vt_top", "vt_mid", "vt_bot"], coef_bands_alone)),
            "coef_re_plus_bands": dict(
                zip(["vt_top", "vt_mid", "vt_bot"] + M4_FEATURES, coef_bo_bd)
            ),
        }

    # Pooled + per-position
    results = []
    print("\n── Pooled (all positions) ──")
    r_all = run_slice(subset, "all_positions")
    results.append(r_all)
    compact = {k: v for k, v in r_all.items() if not k.startswith("coef_")}
    print(json.dumps(compact, indent=2))
    print("coef_bands_alone:", {k: f"{v:+.3f}" for k, v in r_all["coef_bands_alone"].items()})

    print("\n── Per-position sweep ──")
    print(f"{'pos':>4} {'n':>6} {'def':>5} {'rej':>5}  "
          f"{'AUC_any':>7} {'AUC_bnd':>7} {'AUC_re':>7} "
          f"{'re+any':>7} {'re+bnd':>7}  {'Δbnd-any':>9} {'Δrebnd-re':>10}")
    for p in range(10):
        mask = subset & (pos_arr == p)
        r = run_slice(mask, f"position_{p}")
        results.append(r)
        if r.get("skip"):
            print(f"{p:>4} {r['n']:>6}  (skip — too few)")
            continue
        print(f"{p:>4} {r['n']:>6} {r['n_deferred']:>5} {r['n_eval_rej']:>5}  "
              f"{r['auc_vt_any']:>7.3f} {r['auc_vt_bands']:>7.3f} "
              f"{r['auc_retreat']:>7.3f} "
              f"{r['auc_retreat_plus_vt_any']:>7.3f} "
              f"{r['auc_retreat_plus_vt_bands']:>7.3f}  "
              f"{r['delta_bands_over_any']:>+9.3f} "
              f"{r['delta_bo_bd_over_retreat']:>+10.3f}")

    # ── "Fully modeled viewport" — all 10 AOIs' band times + rank dummies ──
    # For each row, the 30-feature vector is its trial's per-position band times
    # (top, mid, bot for positions 0..9); plus 10 rank-dummy columns indicating
    # which position this row is scoring.
    print("\n── Fully modeled viewport (pooled) ──")
    trial_ctx = {}
    for tid, bands_list in per_trial.items():
        flat = []
        for b in bands_list:  # b = [any, top, mid, bot]
            flat.extend([b[1], b[2], b[3]])
        trial_ctx[tid] = np.array(flat, dtype=float)

    X_ctx = np.array([trial_ctx[r["trial_id"]] for r in raw_k])  # (N, 30)
    pos_oh = np.eye(10)[pos_arr]                                 # (N, 10)
    X_vpt_full = np.hstack([X_ctx, pos_oh])                      # (N, 40)
    X_ret_pool = np.hstack([X4, pos_oh])                         # (N, 19)
    X_all_pool = np.hstack([X_ctx, X4, pos_oh])                  # (N, 49)

    sub = subset
    y = labels_k[sub].astype(int)
    g = participants[sub]
    auc_vf, _, _ = fit_loso(X_vpt_full[sub], y, g, "pool:vpt_full")
    auc_rp, _, _ = fit_loso(X_ret_pool[sub], y, g, "pool:retreat+pos")
    auc_ap, _, _ = fit_loso(X_all_pool[sub], y, g, "pool:all")

    vpt_full_summary = {
        "n": int(sub.sum()),
        "auc_viewport_full (30 bands + 10 pos dummies)": auc_vf,
        "auc_retreat_plus_pos (9 retreat + 10 pos)": auc_rp,
        "auc_all (viewport_full + retreat)": auc_ap,
        "delta_all_minus_viewport_full": auc_ap - auc_vf,
        "delta_all_minus_retreat_plus_pos": auc_ap - auc_rp,
    }
    print(json.dumps(vpt_full_summary, indent=2))
    results.append({"slice": "pool_fully_modeled_viewport", **vpt_full_summary})

    out_path = OUT_DIR / "results.json"
    with open(out_path, "w") as f:
        json.dump({
            "generated": "viewport_time_calibration.py",
            "features_file": str(FEATURES_JSON),
            "target": "NB22 gaze-regression label (1=deferred, 0=eval-rej)",
            "subset": "approached (min_dist < 100) AND NOT clicked",
            "m4_features": M4_FEATURES,
            "results": results,
        }, f, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
