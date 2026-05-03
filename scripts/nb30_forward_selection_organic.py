"""STUB-C-3: NB30 forward-selection re-derivation under bbox-organic attribution.

Closes the LR-completeness claim in paper-v4 §4.5 ([NB30:K17–K22]).

Greedy forward-selection starting from FEATURES_B (4 continuous viewport
residence features), adding FEATURES_C (7 trajectory features) one at a
time. Stops when the next-best candidate fails to produce a paired-Wilcoxon
lift at p < α (here α = 0.05 to match the original NB30 protocol).

Inputs:
  cursor-approach-features-organic.json
  regression_labels_cache_organic.json
  Trajectory features per (trial, organic_pos) via
    nb30_scroll_trajectory.compute_features_for_trial(attribution='organic')

Output:
  scripts/output/nb30_ablations/forward_selection_organic.json

Run:
  .venv/bin/python scripts/nb30_forward_selection_organic.py
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

from nb30_scroll_trajectory import compute_features_for_trial, FEATURES_B, FEATURES_C  # noqa

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features-organic.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)
APPROACH_THRESHOLD_PX = 100.0


def lopo(X, y, groups):
    """LOPO: leave-one-participant-out. Returns (pooled AUC, per-participant AUC array)."""
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
    print("[load] cursor-approach-features-organic + regression_labels_cache_organic", file=sys.stderr)
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(raw) == len(labels)

    trials = sorted({r["trial_id"] for r in raw})
    print(f"[walk] computing trajectory features for {len(trials):,} trials under [organic]", file=sys.stderr)
    per_trial = {}
    for i, tid in enumerate(trials):
        if (i + 1) % 250 == 0:
            print(f"  {i+1}/{len(trials)}", file=sys.stderr)
        feats = compute_features_for_trial(tid, attribution='organic')
        if feats is not None:
            per_trial[tid] = feats

    # Build the per-record feature table; under organic, position is the
    # bbox-organic rank, and per_trial[tid] is a list indexed by that rank.
    feat_rows = []
    keep = []
    for i, r in enumerate(raw):
        tid = r["trial_id"]
        pos = int(r["position"])
        if tid not in per_trial:
            continue
        if pos >= len(per_trial[tid]):
            continue
        feat_rows.append(per_trial[tid][pos])
        keep.append(i)
    keep = np.array(keep)
    print(f"  joined records: {len(keep):,}", file=sys.stderr)

    raw_k = [raw[i] for i in keep]
    md = np.array([float(r.get("min_dist", 1e9) or 1e9) for r in raw_k])
    wc = np.array([bool(r.get("was_clicked", False)) for r in raw_k])
    subset = (md < APPROACH_THRESHOLD_PX) & ~wc
    y = labels[keep][subset].astype(int)
    parts = np.array([r["trial_id"].split("-")[0] for r in raw_k])[subset]
    print(f"  approached non-click subset: n = {int(subset.sum()):,}  "
          f"(deferred = {int(y.sum()):,}, eval-rejected = {int((1 - y).sum()):,})", file=sys.stderr)

    def X_for(names):
        return np.array([[float(f.get(n, 0.0) or 0.0) for n in names]
                         for f in feat_rows])[subset]

    # Baseline: B alone (4 features)
    _, per_p_base = lopo(X_for(FEATURES_B), y, parts)
    best_per_p = per_p_base
    selected = []
    remaining = list(FEATURES_C)
    history = []
    print(f"\nB baseline (FEATURES_B = {FEATURES_B})  per-p mean: {best_per_p.mean():.4f}")
    print()

    alpha = 0.05
    step = 0
    while remaining:
        step += 1
        candidates = []
        for f in remaining:
            names = FEATURES_B + selected + [f]
            pooled, per_p = lopo(X_for(names), y, parts)
            d = per_p - best_per_p
            try:
                w = wilcoxon(per_p, best_per_p, alternative="greater")
                p_val = float(w.pvalue)
            except Exception:
                p_val = 1.0
            candidates.append({
                "feature": f, "pooled": pooled,
                "per_p_mean": float(per_p.mean()),
                "delta_per_p": float(d.mean()),
                "wilcoxon_p": p_val,
                "per_p": per_p,
            })

        candidates.sort(key=lambda c: -c["delta_per_p"])
        top = candidates[0]
        print(f"step {step}: pick {top['feature']:24s}  "
              f"Δ = {top['delta_per_p']:+.4f}  p = {top['wilcoxon_p']:.4f}  "
              f"pooled = {top['pooled']:.4f}")

        if top["wilcoxon_p"] < alpha and top["delta_per_p"] > 0:
            selected.append(top["feature"])
            remaining.remove(top["feature"])
            best_per_p = top["per_p"]
            history.append({
                "step": step, "selected": list(selected),
                "new_feature": top["feature"],
                "delta_per_p": top["delta_per_p"],
                "wilcoxon_p": top["wilcoxon_p"],
                "pooled": top["pooled"], "per_p_mean": top["per_p_mean"],
            })
        else:
            print(f"  → STOP. Best candidate doesn't clear p < {alpha} at step {step}.")
            break

    print("\n── Final minimal set (greedy forward-selection, α = 0.05) ──")
    print(f"selected C features ({len(selected)}):")
    for f in selected:
        print(f"  - {f}")
    final_names = FEATURES_B + selected
    pooled_final, per_p_final = lopo(X_for(final_names), y, parts)
    full_names = FEATURES_B + FEATURES_C
    pooled_full, per_p_full = lopo(X_for(full_names), y, parts)
    d_full = per_p_full - per_p_final
    try:
        w = wilcoxon(per_p_full, per_p_final, alternative="greater")
        p_full_vs_min = float(w.pvalue)
    except Exception:
        p_full_vs_min = float("nan")
    print(f"\nminimal B∪C' ({len(final_names)} features) pooled AUC: {pooled_final:.4f}")
    print(f"full    B∪C  ({len(full_names)}  features) pooled AUC: {pooled_full:.4f}")
    print(f"Δ(full − minimal) per-p: {d_full.mean():+.4f}  "
          f"p = {p_full_vs_min:.4f}  "
          f"{int((per_p_full >= per_p_final).sum())}/{len(per_p_full)} parts with full > minimal")

    # Lift over baseline B-only
    delta_min_vs_base = per_p_final - per_p_base
    try:
        w_min_base = wilcoxon(per_p_final, per_p_base, alternative="greater")
        p_min_vs_base = float(w_min_base.pvalue)
    except Exception:
        p_min_vs_base = float("nan")
    print(f"\nMinimal vs B-baseline lift: per-p Δ = {delta_min_vs_base.mean():+.4f}  "
          f"p = {p_min_vs_base:.4f}  "
          f"{int((per_p_final >= per_p_base).sum())}/{len(per_p_final)} parts with minimal > B")

    # Pause_ms collinearity sanity-check
    paused_idx = FEATURES_C.index("pause_ms") if "pause_ms" in FEATURES_C else None
    vt_any_idx = FEATURES_B.index("vt_any") if "vt_any" in FEATURES_B else None
    pause_corr = None
    if paused_idx is not None and vt_any_idx is not None:
        all_X = X_for(FEATURES_B + FEATURES_C)
        pause_col = all_X[:, len(FEATURES_B) + paused_idx]
        vt_any_col = all_X[:, vt_any_idx]
        pause_corr = float(np.corrcoef(pause_col, vt_any_col)[0, 1])
        print(f"\npause_ms × vt_any correlation: r = {pause_corr:.4f}")

    summary = {
        "attribution": "organic",
        "alpha": alpha,
        "n_records": int(subset.sum()),
        "n_deferred": int(y.sum()),
        "n_eval_rejected": int((1 - y).sum()),
        "n_participants": int(len(np.unique(parts))),
        "FEATURES_B": FEATURES_B,
        "FEATURES_C": FEATURES_C,
        "baseline_B": {"per_p_mean": float(per_p_base.mean()),
                       "per_p_sd": float(per_p_base.std(ddof=1))},
        "selected": selected,
        "history": history,
        "final_minimal_set": final_names,
        "final_minimal_pooled_auc": float(pooled_final),
        "final_minimal_per_p_mean": float(per_p_final.mean()),
        "full_BC_pooled_auc": float(pooled_full),
        "full_BC_per_p_mean": float(per_p_full.mean()),
        "full_minus_minimal_delta_per_p": float(d_full.mean()),
        "full_minus_minimal_p": p_full_vs_min,
        "minimal_minus_baseline_delta_per_p": float(delta_min_vs_base.mean()),
        "minimal_minus_baseline_p": p_min_vs_base,
        "pause_ms_vt_any_correlation": pause_corr,
    }
    out_path = OUT / "forward_selection_organic.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
