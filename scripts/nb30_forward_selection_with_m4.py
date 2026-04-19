"""Peter's cursor-as-fourth-viewport extension of NB30 forward selection.

Starting baseline: B (4 continuous viewport features).
Candidate pool: C (7 trajectory) ∪ M4 (9 cursor-approach features, including
`dwell_in_proximity_ms` which IS time-in-cursor-viewport at 100px).

Stopping rule: paired one-sided Wilcoxon p < 0.10 vs. current best.
Report which candidates land, at which step, and what the final minimal set
looks like relative to the published NB30:K18 (B + min_abs_velocity + n_reversals).
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
from nb30_scroll_trajectory import compute_features_for_trial, FEATURES_B, FEATURES_C

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)

# M4 cursor-approach features (per attentional-foraging/CLAUDE.md).
# dwell_in_proximity_ms is the cursor-viewport-residence feature Peter
# proposed: time during which |cursor_page_y − aoi_center_y| < 100 px.
M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]


def lopo(X, y, groups):
    pipe = lambda: Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(np.unique(groups)))
    per_p = []
    for tr, te in gkf.split(X, y, groups=groups):
        m = pipe()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        if len(np.unique(y[te])) == 2:
            per_p.append(roc_auc_score(y[te], p))
    return np.array(per_p)


def main():
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)

    trials = sorted({r["trial_id"] for r in raw})
    per_trial = {}
    for tid in trials:
        feats = compute_features_for_trial(tid, n_positions=10)
        if feats is not None:
            per_trial[tid] = feats

    # Build per-row feature map: merge NB30 features + M4 cursor features from raw.
    feat_rows = []
    keep = []
    for i, r in enumerate(raw):
        if r["trial_id"] not in per_trial or r["position"] >= 10:
            continue
        nb30 = per_trial[r["trial_id"]][r["position"]]
        merged = dict(nb30)
        # Pull M4 features straight from the raw record
        for f in M4_FEATURES:
            merged[f] = float(r.get(f) or 0.0)
        feat_rows.append(merged)
        keep.append(i)
    keep = np.array(keep)
    raw_k = [raw[i] for i in keep]
    md = np.array([r["min_dist"] for r in raw_k])
    wc = np.array([r["was_clicked"] for r in raw_k], dtype=bool)
    subset = (md < 100) & ~wc
    y = labels[keep][subset].astype(int)
    parts = np.array([r["trial_id"].split("-")[0] for r in raw_k])[subset]
    print(f"subset (approached ∧ ¬clicked): {int(subset.sum()):,}")

    def X_for(names):
        return np.array([[float(f.get(n, 0.0) or 0.0) for n in names] for f in feat_rows])[subset]

    # Baseline: B alone
    best_per_p = lopo(X_for(FEATURES_B), y, parts)
    print(f"baseline B (4 features) per-p mean: {best_per_p.mean():.4f}")
    print()

    selected = []
    remaining = list(FEATURES_C) + list(M4_FEATURES)
    history = []
    step = 0

    while remaining:
        step += 1
        candidates = []
        for f in remaining:
            names = FEATURES_B + selected + [f]
            per_p = lopo(X_for(names), y, parts)
            d = per_p - best_per_p
            try:
                w = wilcoxon(per_p, best_per_p, alternative="greater")
                p_val = float(w.pvalue)
            except Exception:
                p_val = 1.0
            candidates.append({
                "feature": f,
                "delta_per_p": float(d.mean()),
                "wilcoxon_p": p_val,
                "per_p": per_p,
                "pooled_like_mean": float(per_p.mean()),
            })

        candidates.sort(key=lambda c: -c["delta_per_p"])
        # Print the top-5 at each step for transparency
        print(f"── Step {step}: top-5 candidates (Δ per-p vs current best) ──")
        for c in candidates[:5]:
            flag = "[M4]" if c["feature"] in M4_FEATURES else "[C ]"
            print(f"  {flag} {c['feature']:28s}  Δ = {c['delta_per_p']:+.4f}  p = {c['wilcoxon_p']:.4f}  per-p = {c['pooled_like_mean']:.4f}")

        top = candidates[0]
        if top["wilcoxon_p"] < 0.10 and top["delta_per_p"] > 0:
            selected.append(top["feature"])
            remaining.remove(top["feature"])
            best_per_p = top["per_p"]
            history.append({
                "step": step,
                "picked": top["feature"],
                "family": "M4" if top["feature"] in M4_FEATURES else "C",
                "delta_per_p": top["delta_per_p"],
                "wilcoxon_p": top["wilcoxon_p"],
                "per_p_mean": top["pooled_like_mean"],
            })
            print(f"  → PICK: {top['feature']}\n")
        else:
            print(f"  → STOP at step {step} (best p = {top['wilcoxon_p']:.4f} > 0.10)\n")
            break

    print("\n── FINAL ──")
    print(f"selected ({len(selected)}): {selected}")
    final_per_p = best_per_p
    print(f"final per-p mean: {final_per_p.mean():.4f} ± {final_per_p.std(ddof=1):.4f}")

    # Compare to NB30:K18 canonical: B + min_abs_velocity + n_reversals
    nb30_k18 = lopo(X_for(FEATURES_B + ["min_abs_velocity", "n_reversals"]), y, parts)
    d = final_per_p - nb30_k18
    try:
        w = wilcoxon(final_per_p, nb30_k18, alternative="two-sided")
        p_val = float(w.pvalue)
    except Exception:
        p_val = float("nan")
    print(f"\nCompare to NB30:K18 (B + min_abs_velocity + n_reversals):")
    print(f"  K18 per-p mean: {nb30_k18.mean():.4f}")
    print(f"  Final per-p mean: {final_per_p.mean():.4f}")
    print(f"  Δ(final − K18) = {d.mean():+.4f}  p = {p_val:.4f}  "
          f"{int((final_per_p >= nb30_k18).sum())}/{len(final_per_p)}")

    # Check specifically: does dwell_in_proximity_ms get picked?
    print(f"\nPeter's question: did dwell_in_proximity_ms (cursor-viewport residence) get picked?")
    print(f"  → {'YES — at step ' + str([h['step'] for h in history if h['picked']=='dwell_in_proximity_ms'][0]) if any(h['picked']=='dwell_in_proximity_ms' for h in history) else 'NO — not in the final selected set'}")

    summary = {
        "baseline_B_per_p_mean": float(lopo(X_for(FEATURES_B), y, parts).mean()),
        "history": history,
        "final_set": FEATURES_B + selected,
        "final_per_p_mean": float(final_per_p.mean()),
        "nb30_k18_per_p_mean": float(nb30_k18.mean()),
        "delta_vs_k18": float(d.mean()),
        "p_vs_k18": p_val,
        "dwell_in_proximity_picked": any(h["picked"] == "dwell_in_proximity_ms" for h in history),
    }
    (OUT / "forward_selection_with_m4.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT / 'forward_selection_with_m4.json'}")


if __name__ == "__main__":
    main()
