"""Greedy forward-selection starting from B, adding C features one at a time.
Stops when adding the next-best feature fails to produce a paired-Wilcoxon
lift at p < 0.05. Purpose: find the minimal B∪C' subset that retains the
NB30 headline lift. Informs the JS library's emission feature list.
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
from data_loader import get_trial_meta, load_mouse_events, result_bands  # noqa
from nb30_scroll_trajectory import compute_features_for_trial, FEATURES_B, FEATURES_C

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)


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
    per_trial = {}
    for tid in trials:
        feats = compute_features_for_trial(tid, n_positions=10)
        if feats is not None:
            per_trial[tid] = feats

    feat_rows = []
    keep = []
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

    def X_for(names):
        return np.array([[float(f.get(n, 0.0) or 0.0) for n in names] for f in feat_rows])[subset]

    # Baseline: B alone (4 features)
    _, per_p_base = lopo(X_for(FEATURES_B), y, parts)
    best_per_p = per_p_base
    selected = []
    remaining = list(FEATURES_C)
    history = []
    print(f"B baseline per-p mean: {best_per_p.mean():.4f}")
    print()

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
                "feature": f,
                "pooled": pooled,
                "per_p_mean": float(per_p.mean()),
                "delta_per_p": float(d.mean()),
                "wilcoxon_p": p_val,
                "per_p": per_p,
            })

        # Pick the candidate with the largest delta_per_p
        candidates.sort(key=lambda c: -c["delta_per_p"])
        top = candidates[0]
        print(f"step {step}: pick {top['feature']:24s}  "
              f"Δ = {top['delta_per_p']:+.4f}  p = {top['wilcoxon_p']:.4f}  "
              f"pooled = {top['pooled']:.4f}")

        # Stopping rule: accept only if p < 0.10 (looser than LOFO's 0.05 per feedback's "add it if it helps")
        if top["wilcoxon_p"] < 0.10 and top["delta_per_p"] > 0:
            selected.append(top["feature"])
            remaining.remove(top["feature"])
            best_per_p = top["per_p"]
            history.append({
                "step": step,
                "selected": list(selected),
                "new_feature": top["feature"],
                "delta_per_p": top["delta_per_p"],
                "wilcoxon_p": top["wilcoxon_p"],
                "pooled": top["pooled"],
                "per_p_mean": top["per_p_mean"],
            })
        else:
            print(f"  → STOP. Best candidate doesn't clear p < 0.10 at step {step}.")
            break

    print("\n── Final minimal set (greedy forward-selection) ──")
    print(f"selected C features ({len(selected)}):")
    for f in selected:
        print(f"  - {f}")
    final_names = FEATURES_B + selected
    pooled_final, per_p_final = lopo(X_for(final_names), y, parts)
    # Compare minimal vs full B∪C
    _, per_p_full = lopo(X_for(FEATURES_B + FEATURES_C), y, parts)
    d_full = per_p_full - per_p_final
    try:
        w = wilcoxon(per_p_full, per_p_final, alternative="greater")
        p_full_vs_min = float(w.pvalue)
    except Exception:
        p_full_vs_min = float("nan")
    print(f"\nminimal B∪C' ({len(final_names)} features) pooled AUC: {pooled_final:.4f}")
    print(f"full    B∪C  ({len(FEATURES_B + FEATURES_C)} features) pooled AUC: "
          f"{lopo(X_for(FEATURES_B + FEATURES_C), y, parts)[0]:.4f}")
    print(f"Δ(full − minimal) per-p: {d_full.mean():+.4f}  "
          f"p = {p_full_vs_min:.4f}  "
          f"{int((per_p_full >= per_p_final).sum())}/{len(per_p_full)}")

    summary = {
        "baseline_B": {"per_p_mean": float(per_p_base.mean())},
        "selected": selected,
        "history": history,
        "final_minimal_set": final_names,
        "final_minimal_pooled_auc": pooled_final,
        "full_pooled_auc": lopo(X_for(FEATURES_B + FEATURES_C), y, parts)[0],
        "full_minus_minimal_delta_per_p": float(d_full.mean()),
        "full_minus_minimal_p": p_full_vs_min,
    }
    (OUT / "forward_selection.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT / 'forward_selection.json'}")


if __name__ == "__main__":
    main()
