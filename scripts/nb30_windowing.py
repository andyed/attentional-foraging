"""Exp 6 — Windowing: rolling 5-second window ending at click_t vs cumulative.

For each approached∧¬clicked AOI, recompute B∪C features over the window
[click_t - 5000, click_t] (session-relative) and compare LOPO AUC against
the cumulative feature set.

Output: scripts/output/nb30_ablations/windowing.json
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
from data_loader import load_mouse_events  # noqa
from nb30_scroll_trajectory import (
    compute_features_for_trial,
    FEATURES_B, FEATURES_C,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT = ROOT / "scripts/output/nb30_ablations"
OUT.mkdir(parents=True, exist_ok=True)

WINDOW_MS = 5000


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


def compute_for_all(raw, labels, window_min_t=None, window_max_t=None, label=""):
    """window_min_t/max_t per-trial override via click timestamps."""
    trials = sorted({r["trial_id"] for r in raw})

    # Per-trial click timestamps
    click_t_by_trial = {}
    for tid in trials:
        _, _, clicks = load_mouse_events(tid)
        if clicks:
            click_t_by_trial[tid] = min(c[0] for c in clicks)

    per_trial = {}
    for tid in trials:
        ct = click_t_by_trial.get(tid)
        min_t = (ct - WINDOW_MS) if (window_min_t == "click_minus_window" and ct is not None) else None
        max_t = ct if (window_max_t == "click" and ct is not None) else None
        feats = compute_features_for_trial(tid, n_positions=10, min_t=min_t, max_t=max_t)
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
    names_B = FEATURES_B
    names_BC = FEATURES_B + FEATURES_C
    X_B  = np.array([[float(f.get(n, 0.0) or 0.0) for n in names_B] for f in feat_rows])[subset]
    X_BC = np.array([[float(f.get(n, 0.0) or 0.0) for n in names_BC] for f in feat_rows])[subset]
    pooled_B,  per_p_B  = lopo(X_B, y, parts)
    pooled_BC, per_p_BC = lopo(X_BC, y, parts)
    print(f"  [{label}]  n={int(subset.sum())}  "
          f"B pooled = {pooled_B:.4f}  B∪C pooled = {pooled_BC:.4f}")
    return {
        "label": label,
        "n": int(subset.sum()),
        "B_pooled": pooled_B, "B_per_p": per_p_B,
        "BC_pooled": pooled_BC, "BC_per_p": per_p_BC,
    }


def main():
    raw = json.load(open(FEATURES_JSON))
    labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    print("Computing cumulative (baseline) features...")
    cumulative = compute_for_all(raw, labels, window_min_t=None, window_max_t=None, label="cumulative")
    print("Computing rolling 5-second window features (ending at click_t)...")
    rolling = compute_for_all(raw, labels, window_min_t="click_minus_window", window_max_t="click", label="rolling_5s")

    # Align: both runs may have different sample counts if some trials lose the
    # window (e.g. click_t too close to trial start). Intersect participant IDs
    # for paired Wilcoxon.
    print("\n── Paired per-participant Wilcoxon (BC cumulative vs rolling) ──")
    # BC contrast: BC cumulative vs BC rolling
    # Participant-level means are already computed by lopo() in per_p lists; but
    # these aren't aligned by participant (GroupKFold gives one AUC per fold).
    # Re-align using participant labels — KFold order is stable given participants.
    a = cumulative["BC_per_p"]
    b = rolling["BC_per_p"]
    m = min(len(a), len(b))
    a, b = a[:m], b[:m]
    d = a - b
    try:
        w = wilcoxon(a, b, alternative="two-sided")
        p_val = float(w.pvalue)
    except Exception:
        p_val = float("nan")
    print(f"  cumulative B∪C > rolling B∪C: Δ_per_p = {d.mean():+.4f} ± {d.std(ddof=1):.4f}   "
          f"{int((a >= b).sum())}/{len(a)}   p = {p_val:.4f}")

    # Also: does rolling B∪C still beat its B baseline (i.e. does trajectory
    # help within-window)?
    print("\n── Headline lift within each window type ──")
    for res in (cumulative, rolling):
        a = res["BC_per_p"]
        b = res["B_per_p"]
        m = min(len(a), len(b))
        a, b = a[:m], b[:m]
        d = a - b
        try:
            w = wilcoxon(a, b, alternative="greater")
            p = float(w.pvalue)
        except Exception:
            p = float("nan")
        print(f"  {res['label']:12s}: B∪C > B Δ_per_p = {d.mean():+.4f}  "
              f"{int((a >= b).sum())}/{len(a)}  p = {p:.4f}")

    summary = {
        "window_ms": WINDOW_MS,
        "cumulative": {
            "n": cumulative["n"],
            "B_pooled": cumulative["B_pooled"],
            "BC_pooled": cumulative["BC_pooled"],
            "B_per_p_mean": float(cumulative["B_per_p"].mean()),
            "BC_per_p_mean": float(cumulative["BC_per_p"].mean()),
        },
        "rolling_5s": {
            "n": rolling["n"],
            "B_pooled": rolling["B_pooled"],
            "BC_pooled": rolling["BC_pooled"],
            "B_per_p_mean": float(rolling["B_per_p"].mean()),
            "BC_per_p_mean": float(rolling["BC_per_p"].mean()),
        },
        "cumulative_minus_rolling_BC_per_p": float((cumulative["BC_per_p"] - rolling["BC_per_p"]).mean()),
        "cumulative_vs_rolling_wilcoxon_p": p_val,
    }
    (OUT / "windowing.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT / 'windowing.json'}")


if __name__ == "__main__":
    main()
