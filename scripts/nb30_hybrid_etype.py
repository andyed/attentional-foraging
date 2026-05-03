"""NB30 hybrid redo — does etype × continuous-viewport interaction predict click outcome?

Population: all approached AOIs (any etype) — extends NB30's organic-only
scope to include dd_top and native_ad AOIs in the result column.
Label: was_clicked (binary). Population gate: min_dist < 100 px (M5/NB28
"approached" convention) — kept consistent with NB30 V1.

Test (Peter's framing, 2026-05-02):
  Re-run the continuous-viewport B feature set on hybrid AOIs with etype
  interaction terms. If `dd_top : max_overlap_frac` coefficient is
  positive over the organic baseline at matched viewport overlap, that's
  the "dd_top items hold attention longer at the same overlap fraction"
  finding — a C/W/L wedge for the click-bias-by-etype paper.

Feature set (B continuous viewport only, NB30 nomenclature):
  vt_any, vt_center_ms, avg_viewport_y, max_overlap_frac

Hybrid AOI source: build_hybrid_aois() from compute_cursor_approach_features.py
(organic + dd_top + native_ad in display order, etype-tagged).

Run:
    .venv/bin/python scripts/nb30_hybrid_etype.py
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import get_trial_meta, load_mouse_events  # noqa
from compute_cursor_approach_features import build_hybrid_aois  # noqa

HYBRID_FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid.json"
OUT_DIR = ROOT / "scripts/output/nb30_hybrid_etype"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CENTER_TOL = 100.0  # px — same as NB30


def compute_b_features_hybrid(trial_id):
    """Per-AOI continuous-viewport B features over hybrid AOI list.

    Returns parallel lists: viewport_features (dict per AOI), etypes (str).
    Position index in the returned list matches display-order position used
    by build_hybrid_aois — the same indexing as
    cursor-approach-features-organic-hybrid.json.

    Returns (None, None) if data missing.
    """
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

    tops, bottoms, etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None, None

    bands = list(zip(tops, bottoms))
    n = len(bands)
    center_y_viewport = scr_h / 2.0

    ts = [e[0] for e in events]
    t_start, t_end = min(ts), max(ts)

    # Piecewise-constant scroll-y timeline — mirror nb30_scroll_trajectory.
    timeline = [(t_start, 0.0)]
    for (t, y) in sorted(scrolls):
        if t_start <= t <= t_end:
            timeline.append((t, float(y)))
    timeline.append((t_end, timeline[-1][1]))

    out = [{
        "vt_any": 0.0,
        "vt_center_ms": 0.0,
        "_sum_center_y": 0.0,
        "_max_overlap_frac": 0.0,
    } for _ in range(n)]

    for (t0, y0), (t1, _y1) in zip(timeline, timeline[1:]):
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
    print("NB30 hybrid — etype × continuous-viewport interaction on click outcome")
    print("=" * 72)

    raw = json.load(open(HYBRID_FEATURES_JSON))
    print(f"loaded {len(raw):,} (trial × AOI) records from {HYBRID_FEATURES_JSON.name}")

    # Group by trial to compute B features per trial once
    by_trial = defaultdict(list)
    for r in raw:
        by_trial[r["trial_id"]].append(r)
    print(f"trials: {len(by_trial):,}")

    # Compute B features and join
    rows = []
    n_skipped = 0
    for tid, recs in by_trial.items():
        feats, etypes = compute_b_features_hybrid(tid)
        if feats is None:
            n_skipped += len(recs)
            continue
        for r in recs:
            pos = r["position"]
            if pos < 0 or pos >= len(feats):
                continue
            # Sanity: etype from hybrid features file should agree with build_hybrid_aois
            if r.get("etype") != etypes[pos]:
                # Drop on mismatch — display-order may have drifted
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
    print(f"joined rows: {len(rows):,} (skipped {n_skipped:,} for missing data)")

    # Population: approached (min_dist < 100)
    approached = [r for r in rows if r["min_dist"] < 100]
    print(f"approached (min_dist < 100): {len(approached):,}")
    print(f"  organic:    {sum(1 for r in approached if r['etype']=='organic'):,}  "
          f"(clicks {sum(r['was_clicked'] for r in approached if r['etype']=='organic'):,})")
    print(f"  dd_top:     {sum(1 for r in approached if r['etype']=='dd_top'):,}  "
          f"(clicks {sum(r['was_clicked'] for r in approached if r['etype']=='dd_top'):,})")
    print(f"  native_ad:  {sum(1 for r in approached if r['etype']=='native_ad'):,}  "
          f"(clicks {sum(r['was_clicked'] for r in approached if r['etype']=='native_ad'):,})")

    # Build feature matrix:
    #   B continuous: vt_any, vt_center_ms, avg_viewport_y, max_overlap_frac (4)
    #   position (rank control — max_overlap_frac is mechanically tied to rank) (1)
    #   etype dummies: is_dd_top, is_native_ad (organic = ref, 2)
    #   etype × max_overlap_frac interactions: 2
    # Total: 9 features
    B = ["vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac", "position"]

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

    feat_names = B + ["is_dd_top", "is_native_ad", "dd_top:max_overlap_frac", "native_ad:max_overlap_frac"]

    X = np.array([feat_row(r) for r in approached])
    y = np.array([1 if r["was_clicked"] else 0 for r in approached])
    groups = np.array([r["participant"] for r in approached])

    n_users = len(set(groups))
    print(f"\nLOPO logistic regression — {n_users} folds, {X.shape[1]} features")
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=n_users)
    proba = np.zeros(len(y))
    for train, test in gkf.split(X, y, groups=groups):
        pipe.fit(X[train], y[train])
        proba[test] = pipe.predict_proba(X[test])[:, 1]
    auc = roc_auc_score(y, proba)
    print(f"\nLOPO AUC (click prediction, hybrid + etype interactions): {auc:.4f}")

    # Coefficients on full-data refit (interpretation)
    pipe.fit(X, y)
    scaler = pipe.named_steps["scaler"]
    coef = pipe.named_steps["lr"].coef_[0]
    intercept = pipe.named_steps["lr"].intercept_[0]
    # Standardized coefficients
    print("\nStandardized coefficients (full-data refit, sign indicates click direction):")
    for name, c in sorted(zip(feat_names, coef), key=lambda x: -abs(x[1])):
        direction = "→ click" if c > 0 else "→ skip "
        print(f"  {name:35s}  {c:+.4f}  {direction}")

    # Per-etype max_overlap_frac slope (raw scale) — combine main + interaction
    # In standardized space the interpretable test is: dd_top × max_overlap_frac
    # coefficient relative to organic baseline.
    base_mof = coef[feat_names.index("max_overlap_frac")]
    dd_int = coef[feat_names.index("dd_top:max_overlap_frac")]
    na_int = coef[feat_names.index("native_ad:max_overlap_frac")]
    print("\nPer-etype max_overlap_frac slope (standardized; positive = higher overlap → more click):")
    print(f"  organic   baseline:                   {base_mof:+.4f}")
    print(f"  dd_top    (organic + interaction):    {base_mof + dd_int:+.4f}  (interaction Δ = {dd_int:+.4f})")
    print(f"  native_ad (organic + interaction):    {base_mof + na_int:+.4f}  (interaction Δ = {na_int:+.4f})")

    # Bootstrap CI for the two interaction coefficients (1000 reps, BCa via percentile)
    print("\nBootstrap 95% CI for interaction coefficients (1000 reps, percentile):")
    rng = np.random.default_rng(42)
    n = len(y)
    boot_dd = np.zeros(1000)
    boot_na = np.zeros(1000)
    for b in range(1000):
        idx = rng.integers(0, n, size=n)
        Xb, yb = X[idx], y[idx]
        try:
            pipe.fit(Xb, yb)
            boot_dd[b] = pipe.named_steps["lr"].coef_[0][feat_names.index("dd_top:max_overlap_frac")]
            boot_na[b] = pipe.named_steps["lr"].coef_[0][feat_names.index("native_ad:max_overlap_frac")]
        except Exception:
            boot_dd[b] = np.nan
            boot_na[b] = np.nan
    dd_ci = np.nanpercentile(boot_dd, [2.5, 97.5])
    na_ci = np.nanpercentile(boot_na, [2.5, 97.5])
    print(f"  dd_top × max_overlap_frac:    {dd_int:+.4f}  CI [{dd_ci[0]:+.4f}, {dd_ci[1]:+.4f}]  "
          f"{'(excludes 0)' if dd_ci[0] > 0 or dd_ci[1] < 0 else '(crosses 0)'}")
    print(f"  native_ad × max_overlap_frac: {na_int:+.4f}  CI [{na_ci[0]:+.4f}, {na_ci[1]:+.4f}]  "
          f"{'(excludes 0)' if na_ci[0] > 0 or na_ci[1] < 0 else '(crosses 0)'}")

    # Save artifacts
    summary = {
        "experiment": "NB30 hybrid — etype × continuous-viewport on click outcome",
        "regime": "LAB",
        "rank_type": "organic_hybrid",
        "population": {
            "description": "approached (min_dist < 100) AOIs — any etype",
            "n_total": int(len(approached)),
            "n_clicks": int(y.sum()),
            "etype_counts": {
                e: int(sum(1 for r in approached if r["etype"] == e))
                for e in ("organic", "dd_top", "native_ad")
            },
            "etype_click_counts": {
                e: int(sum(r["was_clicked"] for r in approached if r["etype"] == e))
                for e in ("organic", "dd_top", "native_ad")
            },
        },
        "features": feat_names,
        "lopo_auc": float(auc),
        "coefficients_standardized": dict(zip(feat_names, coef.tolist())),
        "intercept_standardized": float(intercept),
        "per_etype_max_overlap_frac_slope": {
            "organic": float(base_mof),
            "dd_top": float(base_mof + dd_int),
            "native_ad": float(base_mof + na_int),
        },
        "interaction_bootstrap_ci": {
            "dd_top:max_overlap_frac": {"point": float(dd_int), "ci_lo": float(dd_ci[0]), "ci_hi": float(dd_ci[1])},
            "native_ad:max_overlap_frac": {"point": float(na_int), "ci_lo": float(na_ci[0]), "ci_hi": float(na_ci[1])},
        },
        "n_bootstrap": 1000,
    }
    out_json = OUT_DIR / "summary.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_json}")


if __name__ == "__main__":
    main()
