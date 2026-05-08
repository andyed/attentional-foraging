"""Robustness check: M4 ≈ M3 with organic_rank instead of absolute_rank.

Andy 2026-04-16 spec: the M1/M2/M3 baseline in §4.1 uses position = absolute
slot index (ads + organic pooled, max 11 per cache). This means M1's
"position only" baseline partly measures ad-intrusion geometry, not pure
organic position bias. A reviewer could argue absolute_rank is a weaker
adversary than organic_rank, and the M4 ≈ M3 absorption claim should hold
against the stronger organic_rank baseline before being treated as
bulletproof.

This script re-runs M1–M4 LOSO with organic_rank as the position feature
(via data_loader.absolute_to_organic_rank). Records whose absolute slot is
an ad (no organic mapping) are dropped from M1/M2/M3 and re-included with
the organic_rank feature for M2/M3/M4 (M1 needs only position so ad records
are dropped). M4 (cursor approach features only, no position) is unchanged
in feature set but is re-fit on the same population for fair comparison.

Output: scripts/output/m4_organic_rank_robustness/summary.json
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import absolute_to_organic_rank  # noqa: E402

# Reuse the canonical Option D extractor's feature computation.
sys.path.insert(0, str(ROOT / "scripts"))
from m4_nb21_hybrid_rerun import compute_hybrid_features, M4_FEATURES  # noqa: E402

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
OUT_DIR = ROOT / "scripts/output/m4_organic_rank_robustness"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def loso_auc(X, y, groups, label):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    n_groups = len(set(groups))
    gkf = GroupKFold(n_splits=n_groups)
    y_proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=gkf, method="predict_proba", n_jobs=1
    )[:, 1]
    concat_auc = float(roc_auc_score(y, y_proba))

    per_fold = []
    for _, test_idx in gkf.split(X, y, groups=groups):
        yt = y[test_idx]
        if len(np.unique(yt)) < 2:
            continue
        per_fold.append(float(roc_auc_score(yt, y_proba[test_idx])))
    arr = np.array(per_fold, dtype=float)
    fold_mean = float(arr.mean()) if len(arr) else float("nan")
    fold_sd = float(arr.std(ddof=1)) if len(arr) >= 2 else float("nan")
    print(f"  {label}: concat AUC = {concat_auc:.4f}  "
          f"(per-fold {fold_mean:.4f} ± {fold_sd:.4f}, n_folds={len(arr)}/{n_groups})")
    return concat_auc, fold_mean, fold_sd, arr, y_proba


def main():
    print("=" * 70)
    print("M4 ≈ M3 robustness re-run with organic_rank")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    n = len(lab_records)
    print(f"  {n:,} records")

    # Build organic_rank lookup per (trial_id, absolute_position)
    print("\ncomputing absolute → organic rank mapping per trial (~1 min)...")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    abs2org = {}
    for n_done, tid in enumerate(trial_ids):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(trial_ids)}  ({len(abs2org):,} mappings)")
        try:
            mapping = absolute_to_organic_rank(tid)
        except Exception:
            continue
        if mapping is None:
            continue
        for abs_rank, org_rank in mapping.items():
            abs2org[(tid, int(abs_rank))] = org_rank  # may be None for ad slots
    print(f"  total (trial, absolute) → organic mappings: {len(abs2org):,}")

    # Build hybrid feature cache (same Option D extractor as §4.1)
    print("\ncomputing hybrid features per trial (~3 min)...")
    hy_records = []
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)}  (skipped {skipped})")
        recs = compute_hybrid_features(tid)
        if recs is None:
            skipped += 1
            continue
        hy_records.extend(recs)
    print(f"  hybrid records: {len(hy_records):,}, trials skipped: {skipped}")

    hy_index = {(r["trial_id"], r["position"]): r for r in hy_records}

    # Align features + labels + organic_rank to LAB records
    X_m4 = np.zeros((n, len(M4_FEATURES)), dtype=float)
    abs_pos = np.zeros(n, dtype=float)
    org_pos = np.full(n, -1.0, dtype=float)  # -1 = ad slot or no mapping
    valid_features = np.zeros(n, dtype=bool)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        hy = hy_index.get(key)
        if hy is not None:
            for j, f in enumerate(M4_FEATURES):
                X_m4[i, j] = float(hy.get(f) or 0)
            valid_features[i] = True
        abs_pos[i] = float(r["position"])
        org_rank = abs2org.get(key)
        if org_rank is not None:
            org_pos[i] = float(org_rank)

    has_organic = org_pos >= 0
    valid = valid_features & has_organic

    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    groups_all = np.array([r["trial_id"].split("-")[0] for r in lab_records])

    n_full = int(valid_features.sum())
    n_org_only = int(valid.sum())
    n_dropped = n_full - n_org_only
    print(f"\n  records with hybrid features:           {n_full:,}")
    print(f"  records with organic_rank assignment:    {n_org_only:,}")
    print(f"  records dropped (ad slots, no organic):  {n_dropped:,}  "
          f"({100 * n_dropped / max(n_full, 1):.1f} %)")

    # Subset to organic-only population for the comparison
    Xv = X_m4[valid]
    abs_v = abs_pos[valid].reshape(-1, 1)
    org_v = org_pos[valid].reshape(-1, 1)
    yv = was_clicked[valid].astype(int)
    gv = groups_all[valid]
    dwell_idx = M4_FEATURES.index("dwell_in_proximity_ms")
    dwell_v = Xv[:, dwell_idx].reshape(-1, 1)

    print("\n── Baseline reproduction with absolute_rank (subset to organic-only records) ──")
    auc_m1_abs, m_m1_abs, sd_m1_abs, _, _ = loso_auc(abs_v, yv, gv, "M1 abs (position only)")
    X_m2_abs = np.column_stack([abs_v, dwell_v])
    auc_m2_abs, m_m2_abs, sd_m2_abs, _, _ = loso_auc(X_m2_abs, yv, gv, "M2 abs (pos + dwell)")
    auc_m4, m_m4, sd_m4, _, _ = loso_auc(Xv, yv, gv, "M4 (9 approach, no position) — same on both schemes")
    X_m3_abs = np.column_stack([abs_v, Xv])
    auc_m3_abs, m_m3_abs, sd_m3_abs, _, _ = loso_auc(X_m3_abs, yv, gv, "M3 abs (pos + 9 approach)")

    print("\n── Organic-rank baseline ──")
    auc_m1_org, m_m1_org, sd_m1_org, _, _ = loso_auc(org_v, yv, gv, "M1 org (organic_rank only)")
    X_m2_org = np.column_stack([org_v, dwell_v])
    auc_m2_org, m_m2_org, sd_m2_org, _, _ = loso_auc(X_m2_org, yv, gv, "M2 org (org_rank + dwell)")
    X_m3_org = np.column_stack([org_v, Xv])
    auc_m3_org, m_m3_org, sd_m3_org, _, _ = loso_auc(X_m3_org, yv, gv, "M3 org (org_rank + 9 approach)")

    delta_m4_m3_abs = m_m4 - m_m3_abs
    delta_m4_m3_org = m_m4 - m_m3_org

    print("\n" + "=" * 70)
    print("SUMMARY — organic-only population (n = {:,})".format(n_org_only))
    print("=" * 70)
    fmt = "  {:<35s}  per-fold {:.4f} ± {:.4f}   concat {:.4f}"
    print("  ── absolute_rank baseline ──")
    print(fmt.format("M1 abs (position only)", m_m1_abs, sd_m1_abs, auc_m1_abs))
    print(fmt.format("M2 abs (pos + dwell)", m_m2_abs, sd_m2_abs, auc_m2_abs))
    print(fmt.format("M3 abs (pos + 9 approach)", m_m3_abs, sd_m3_abs, auc_m3_abs))
    print(fmt.format("M4    (9 approach only)", m_m4, sd_m4, auc_m4))
    print(f"  paired Δ (M4 − M3 abs):  {delta_m4_m3_abs:+.4f}")
    print()
    print("  ── organic_rank baseline ──")
    print(fmt.format("M1 org (organic_rank only)", m_m1_org, sd_m1_org, auc_m1_org))
    print(fmt.format("M2 org (org_rank + dwell)", m_m2_org, sd_m2_org, auc_m2_org))
    print(fmt.format("M3 org (org_rank + 9 approach)", m_m3_org, sd_m3_org, auc_m3_org))
    print(fmt.format("M4    (9 approach only)", m_m4, sd_m4, auc_m4))
    print(f"  paired Δ (M4 − M3 org):  {delta_m4_m3_org:+.4f}")

    print()
    if abs(delta_m4_m3_org) <= sd_m4:
        print("  → M4 ≈ M3 with organic_rank as well: claim is bulletproof.")
    else:
        print("  → M4 vs M3-organic delta exceeds fold-SD; the absorption claim "
              "may depend on baseline strength. INVESTIGATE.")

    summary = {
        "experiment": "M4 organic_rank robustness re-run",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_records_evaluated": n_org_only,
        "n_records_dropped_ad_slots": n_dropped,
        "absolute_rank": {
            "M1": {"per_fold_mean": m_m1_abs, "per_fold_sd": sd_m1_abs, "concat": auc_m1_abs},
            "M2": {"per_fold_mean": m_m2_abs, "per_fold_sd": sd_m2_abs, "concat": auc_m2_abs},
            "M3": {"per_fold_mean": m_m3_abs, "per_fold_sd": sd_m3_abs, "concat": auc_m3_abs},
            "M4": {"per_fold_mean": m_m4, "per_fold_sd": sd_m4, "concat": auc_m4},
            "delta_M4_minus_M3": delta_m4_m3_abs,
        },
        "organic_rank": {
            "M1": {"per_fold_mean": m_m1_org, "per_fold_sd": sd_m1_org, "concat": auc_m1_org},
            "M2": {"per_fold_mean": m_m2_org, "per_fold_sd": sd_m2_org, "concat": auc_m2_org},
            "M3": {"per_fold_mean": m_m3_org, "per_fold_sd": sd_m3_org, "concat": auc_m3_org},
            "M4": {"per_fold_mean": m_m4, "per_fold_sd": sd_m4, "concat": auc_m4},
            "delta_M4_minus_M3": delta_m4_m3_org,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
