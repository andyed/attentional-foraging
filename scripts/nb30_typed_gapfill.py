"""NB30 hybrid etype × continuous-viewport — typed_gapfill variant.

Mirrors `nb30_hybrid_etype.py` but uses `typed_gapfill` AOI bands and
`cursor-approach-features-typed-gapfill.json` instead of organic_hybrid.

Headline: per-etype max_overlap_frac slope (the dissociation between
organic, dd_top, native_ad in click prediction at high viewport overlap).
Under organic_hybrid the legacy values were:
  organic    baseline:  -0.278
  dd_top:    -0.387 (interaction -0.108)
  native_ad: -0.515 (interaction -0.236)

Regime tag: [LAB, AdSERP, typed_gapfill, NB30]
See: docs/null-findings/2026-05-05-bbox-y-coverage.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa
    get_trial_meta, load_mouse_events,
    typed_gapfill_aoi_bands, typed_gapfill_aoi_etypes,
)

FEATURES_JSON = ROOT / "AdSERP" / "data" / "cursor-approach-features-typed-gapfill.json"
CENTER_TOL = 100.0


def compute_b_features_typed_gapfill(trial_id):
    """Per-AOI continuous-viewport B features over typed_gapfill bands."""
    try:
        doc_h, scr_h, _ = get_trial_meta(trial_id)
    except Exception:
        return None, None
    mouse = load_mouse_events(trial_id)
    if not mouse:
        return None, None
    events, scrolls, _ = mouse
    if not events:
        return None, None

    bands_full = typed_gapfill_aoi_bands(trial_id)  # (top, bot, etype) on main axis
    if not bands_full:
        return None, None
    tops = [b[0] for b in bands_full]
    bottoms = [b[1] for b in bands_full]
    etypes = [b[2] for b in bands_full]
    bands = list(zip(tops, bottoms))
    n = len(bands)

    center_y_viewport = scr_h / 2.0
    ts = [e[0] for e in events]
    t_start, t_end = min(ts), max(ts)

    timeline = [(t_start, 0.0)]
    for (t, y) in sorted(scrolls):
        if t_start <= t <= t_end:
            timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    out = [{"vt_any": 0.0, "vt_center_ms": 0.0, "_sum_center_y": 0.0,
            "_max_overlap_frac": 0.0} for _ in range(n)]

    for (t0, y0), (t1, _) in zip(timeline, timeline[1:]):
        dt_ms = t1 - t0
        if dt_ms <= 0:
            continue
        vp_top, vp_bot = y0, y0 + scr_h
        for p, (a_top, a_bot) in enumerate(bands):
            overlap_top = max(a_top, vp_top)
            overlap_bot = min(a_bot, vp_bot)
            if overlap_bot <= overlap_top:
                continue
            out[p]["vt_any"] += dt_ms
            center_vp_y = (a_top + a_bot) / 2.0 - y0
            if abs(center_vp_y - center_y_viewport) <= CENTER_TOL:
                out[p]["vt_center_ms"] += dt_ms
            out[p]["_sum_center_y"] += center_vp_y * dt_ms
            overlap_frac = (overlap_bot - overlap_top) / max(a_bot - a_top, 1.0)
            if overlap_frac > out[p]["_max_overlap_frac"]:
                out[p]["_max_overlap_frac"] = overlap_frac

    feats = []
    for p in range(n):
        vt_any = out[p]["vt_any"]
        avg_vp_y = (out[p]["_sum_center_y"] / vt_any) if vt_any > 0 else 0.0
        feats.append({
            "vt_any": vt_any,
            "vt_center_ms": out[p]["vt_center_ms"],
            "avg_viewport_y": avg_vp_y,
            "max_overlap_frac": out[p]["_max_overlap_frac"],
        })
    return feats, etypes


def main():
    print("=" * 72)
    print("NB30 typed_gapfill — etype × continuous-viewport on click outcome")
    print("=" * 72)

    raw = json.load(open(FEATURES_JSON))
    print(f"loaded {len(raw):,} records from {FEATURES_JSON.name}")

    by_trial = defaultdict(list)
    for r in raw:
        by_trial[r["trial_id"]].append(r)
    print(f"trials: {len(by_trial):,}")

    rows = []
    n_skipped = 0
    n_etype_mismatch = 0
    for tid, recs in by_trial.items():
        feats, etypes = compute_b_features_typed_gapfill(tid)
        if feats is None:
            n_skipped += len(recs)
            continue
        for r in recs:
            pos = r["position"]
            if pos < 0 or pos >= len(feats):
                continue
            if r.get("etype") != etypes[pos]:
                n_etype_mismatch += 1
                continue
            rows.append({
                "trial_id": tid,
                "participant": tid.split("-")[0],
                "position": pos,
                "etype": etypes[pos],
                "was_clicked": bool(r["was_clicked"]),
                "min_dist": float(r["min_dist"]),
                **feats[pos],
            })
    print(f"joined: {len(rows):,} (skipped {n_skipped:,}, etype mismatch {n_etype_mismatch:,})")

    # Restrict to organic + dd_top + native_ad for parity with legacy NB30
    rows_3et = [r for r in rows if r["etype"] in ("organic", "dd_top", "native_ad")]
    approached = [r for r in rows_3et if r["min_dist"] < 100]
    print(f"\napproached (min_dist < 100), 3-etype subset: {len(approached):,}")
    for et in ("organic", "dd_top", "native_ad"):
        n = sum(1 for r in approached if r["etype"] == et)
        clk = sum(r["was_clicked"] for r in approached if r["etype"] == et)
        print(f"  {et:<10s}: n={n:,}, clicks={clk:,}")

    feat_names = [
        "vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac", "position",
        "is_dd_top", "is_native_ad",
        "dd_top:max_overlap_frac", "native_ad:max_overlap_frac",
    ]

    def feat_row(r):
        is_dd = 1.0 if r["etype"] == "dd_top" else 0.0
        is_na = 1.0 if r["etype"] == "native_ad" else 0.0
        mof = r["max_overlap_frac"]
        return [
            r["vt_any"], r["vt_center_ms"], r["avg_viewport_y"], r["max_overlap_frac"],
            float(r["position"]),
            is_dd, is_na,
            is_dd * mof, is_na * mof,
        ]

    X = np.array([feat_row(r) for r in approached])
    y = np.array([1 if r["was_clicked"] else 0 for r in approached])
    groups = np.array([r["participant"] for r in approached])

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    proba = np.zeros(len(y))
    for train, test in gkf.split(X, y, groups=groups):
        pipe.fit(X[train], y[train])
        proba[test] = pipe.predict_proba(X[test])[:, 1]
    auc = roc_auc_score(y, proba)
    print(f"\nLOPO AUC (click prediction, typed_gapfill + etype interactions): {auc:.4f}")

    pipe.fit(X, y)
    coef = pipe.named_steps["lr"].coef_[0]
    base_mof = coef[feat_names.index("max_overlap_frac")]
    dd_int = coef[feat_names.index("dd_top:max_overlap_frac")]
    na_int = coef[feat_names.index("native_ad:max_overlap_frac")]
    print("\nPer-etype max_overlap_frac slope (standardized; positive → click):")
    print(f"  organic   baseline:                {base_mof:+.4f}")
    print(f"  dd_top    (organic + interaction): {base_mof + dd_int:+.4f}  (Δ = {dd_int:+.4f})")
    print(f"  native_ad (organic + interaction): {base_mof + na_int:+.4f}  (Δ = {na_int:+.4f})")

    print("\nFor comparison, legacy organic_hybrid values:")
    print(f"  organic   baseline:                -0.2785")
    print(f"  dd_top:                            -0.3867  (Δ = -0.1082)")
    print(f"  native_ad:                         -0.5146  (Δ = -0.2362)")


if __name__ == "__main__":
    main()
