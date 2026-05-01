"""Phase 2 validation — does withstood_evaluation behave like a continuous
relevance scalar?

Four checks:

  1. Class ordering: median withstood by NB22 four-class label.
     EXPECT: clicked > deferred > evaluated_rejected > not_approached.
     FAIL CRITERION: ordering wrong → composite weights broken.

  2. Within-class spread: IQR of withstood within each class.
     EXPECT: deferred and eval-rejected have meaningful spread
     (continuous framing earning its keep).
     FAIL CRITERION: classes collapse to point masses → discretization
     already captures everything.

  3. LF/HF residual correlation: partial Spearman(withstood, LF/HF | position).
     EXPECT: positive, echoing today's `vt_any | position` finding (ρ=+0.111).
     FAIL CRITERION: null or negative → pupillometric legitimacy gone.

  4. Leakage magnitude: distribution of full − pre_click on clicked items.
     EXPECT: small but non-zero; larger magnitude means more click-
     correlated signal in the full-trial window.
     (Just descriptive — not a go/no-go.)

Output: scripts/output/withstood_evaluation_validation/summary.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, rankdata, t as tdist

ROOT = Path(__file__).resolve().parent.parent
WITHSTOOD = ROOT / "AdSERP/data/withstood-evaluation-score.json"
LAB_RECORDS = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
LFHF_JSON = ROOT.parent / "pupil-lfhf" / "validation" / "butterworth-lfhf-by-position.json"
OUT_DIR = ROOT / "scripts/output/withstood_evaluation_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def partial_rank_spearman(x, y, z_list):
    rx = rankdata(x).astype(float)
    ry = rankdata(y).astype(float)
    Z = np.column_stack([rankdata(z).astype(float) for z in z_list])
    Z = np.column_stack([np.ones(len(x)), Z])
    bx, *_ = np.linalg.lstsq(Z, rx, rcond=None)
    by, *_ = np.linalg.lstsq(Z, ry, rcond=None)
    rx_r = rx - Z @ bx
    ry_r = ry - Z @ by
    if rx_r.std() == 0 or ry_r.std() == 0:
        return float("nan"), float("nan")
    rho = float(np.corrcoef(rx_r, ry_r)[0, 1])
    n = len(x)
    if abs(rho) >= 1 or n < 5:
        return rho, 0.0
    df = max(n - 2 - Z.shape[1] + 1, 1)
    t = rho * math.sqrt(df / max(1 - rho ** 2, 1e-12))
    p = float(2 * (1 - tdist.cdf(abs(t), df=df)))
    return rho, p


def main():
    print("[load] withstood-evaluation-score.json")
    withstood = json.load(open(WITHSTOOD))
    w_by_key = {(r["trial_id"], int(r["position"])): r for r in withstood}
    print(f"       {len(withstood):,} rows")

    print("[load] cursor-approach-features.json + regression labels")
    records = json.load(open(LAB_RECORDS))
    regression = np.array(json.load(open(REG_CACHE)), dtype=bool)

    # Build 4-class labels aligned to cursor-approach rows, then join withstood
    rows_class: list[dict] = []
    for i, r in enumerate(records):
        key = (r["trial_id"], int(r["position"]))
        w = w_by_key.get(key)
        if w is None:
            continue
        clicked = bool(r.get("was_clicked"))
        approached = float(r.get("min_dist", 9999)) < 100
        if clicked:
            label = "clicked"
        elif approached and bool(regression[i]):
            label = "deferred"
        elif approached and not bool(regression[i]):
            label = "evaluated_rejected"
        else:
            label = "not_approached"
        rows_class.append({
            **w,
            "class": label,
            "clicked": clicked,
        })
    # Also add rows for (trial, pos) pairs NOT in cursor-approach-features
    # (those are below-click not-approached; still classifiable as not_approached)
    cursor_keys = {(r["trial_id"], int(r["position"])) for r in records}
    for key, w in w_by_key.items():
        if key in cursor_keys:
            continue
        rows_class.append({**w, "class": "not_approached", "clicked": False})
    print(f"[join] {len(rows_class):,} rows with class labels")

    # ── Check 1: class ordering by median ──
    print("\n-- Check 1: class ordering (median withstood_full) --")
    medians: dict[str, float] = {}
    spreads: dict[str, dict] = {}
    for cls in ("clicked", "deferred", "evaluated_rejected", "not_approached"):
        vs = np.array([r["withstood_full"] for r in rows_class if r["class"] == cls])
        if len(vs) == 0:
            continue
        medians[cls] = float(np.median(vs))
        spreads[cls] = {
            "n": int(len(vs)),
            "mean": float(vs.mean()),
            "median": float(np.median(vs)),
            "iqr_25": float(np.percentile(vs, 25)),
            "iqr_75": float(np.percentile(vs, 75)),
            "std": float(vs.std(ddof=1) if len(vs) > 1 else 0.0),
        }
        print(f"  {cls:22s} n={len(vs):>6,}  median={np.median(vs):+.3f}  "
              f"mean={vs.mean():+.3f}  "
              f"IQR=[{np.percentile(vs, 25):+.3f}, {np.percentile(vs, 75):+.3f}]")

    expected_order = ["clicked", "deferred", "evaluated_rejected", "not_approached"]
    actual_order = sorted(medians.keys(), key=lambda k: medians[k], reverse=True)
    ordering_ok = actual_order == expected_order
    print(f"\n  expected: {expected_order}")
    print(f"  actual  : {actual_order}")
    print(f"  {'PASS' if ordering_ok else 'FAIL'}: class ordering {'preserved' if ordering_ok else 'WRONG'}")

    # ── Check 2: within-class spread ──
    print("\n-- Check 2: within-class IQR --")
    spread_threshold = 0.1  # minimum IQR width (on z-score scale)
    all_ok = True
    for cls in ("deferred", "evaluated_rejected"):
        s = spreads[cls]
        iqr_w = s["iqr_75"] - s["iqr_25"]
        ok = iqr_w >= spread_threshold
        print(f"  {cls:22s} IQR width = {iqr_w:.3f}   {'PASS' if ok else 'FAIL'} (threshold {spread_threshold})")
        all_ok = all_ok and ok

    # ── Check 3: LF/HF residual correlation ──
    print("\n-- Check 3: partial Spearman(withstood, LF/HF | position) --")
    lfhf_raw = json.load(open(LFHF_JSON))
    lfhf_by_key: dict[tuple[str, int], float] = {}
    for tid, trial in lfhf_raw.items():
        for seg in trial["positions"]:
            v = seg["lfhf"]
            if v is None or not math.isfinite(v):
                continue
            lfhf_by_key[(tid, int(seg["pos"]))] = float(v)

    joined = []
    for r in rows_class:
        key = (r["trial_id"], int(r["position"]))
        v = lfhf_by_key.get(key)
        if v is None:
            continue
        joined.append({**r, "lfhf": v})
    print(f"  joined with LF/HF: {len(joined):,} rows")

    w_arr = np.array([r["withstood_full"] for r in joined])
    y_arr = np.array([r["lfhf"] for r in joined])
    p_arr = np.array([r["position"] for r in joined])

    rho_pool, p_pool = spearmanr(w_arr, y_arr)
    rho_pg, p_pg = partial_rank_spearman(w_arr, y_arr, [p_arr])
    print(f"  pooled:           ρ = {rho_pool:+.4f}  p = {p_pool:.3g}")
    print(f"  partial|position: ρ = {rho_pg:+.4f}  p = {p_pg:.3g}")
    lfhf_ok = rho_pg > 0 and p_pg < 0.01

    # Steep P0–P3 replication
    steep = [r for r in joined if r["position"] <= 3]
    ws = np.array([r["withstood_full"] for r in steep])
    ys = np.array([r["lfhf"] for r in steep])
    ps = np.array([r["position"] for r in steep])
    rho_ps, p_ps = partial_rank_spearman(ws, ys, [ps])
    print(f"  steep P0–P3 partial|position: ρ = {rho_ps:+.4f}  p = {p_ps:.3g}")

    # ── Check 4: leakage magnitude ──
    print("\n-- Check 4: full vs pre_click delta on clicked items --")
    clicked = [r for r in rows_class if r["clicked"]]
    delta = np.array([r["withstood_full"] - r["withstood_pre_click"] for r in clicked])
    print(f"  N clicked = {len(clicked):,}")
    print(f"  Δ(full − pre_click): mean={delta.mean():+.4f}  "
          f"median={np.median(delta):+.4f}  "
          f"IQR=[{np.percentile(delta, 25):+.4f}, {np.percentile(delta, 75):+.4f}]")

    # ── Verdict ──
    print("\n" + "=" * 64)
    print("GATE FOR PHASE 3")
    print("=" * 64)
    print(f"  Check 1 class ordering:       {'PASS' if ordering_ok else 'FAIL'}")
    print(f"  Check 2 within-class spread:  {'PASS' if all_ok else 'FAIL'}")
    print(f"  Check 3 LF/HF partial:        {'PASS' if lfhf_ok else 'FAIL'}")
    print(f"  Check 4 leakage magnitude:    descriptive (not gated)")
    gate_pass = ordering_ok and all_ok and lfhf_ok
    print(f"\n  >>> {'PROCEED to Phase 3' if gate_pass else 'GATE FAILED — revisit composite'}")

    # Save
    summary = {
        "n_rows": len(rows_class),
        "class_ordering": {
            "expected": expected_order,
            "actual": actual_order,
            "pass": ordering_ok,
            "medians": medians,
        },
        "within_class_spread": spreads,
        "lfhf_partial": {
            "pooled": {"rho": float(rho_pool), "p": float(p_pool), "n": len(joined)},
            "partial_given_position": {"rho": float(rho_pg), "p": float(p_pg)},
            "steep_P0_P3": {"rho": float(rho_ps), "p": float(p_ps), "n": len(steep)},
            "pass": lfhf_ok,
        },
        "leakage_delta_clicked": {
            "n": len(clicked),
            "mean": float(delta.mean()),
            "median": float(np.median(delta)),
            "p25": float(np.percentile(delta, 25)),
            "p75": float(np.percentile(delta, 75)),
        },
        "gate_pass": gate_pass,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
