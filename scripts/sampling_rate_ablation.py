"""15 Hz cursor sampling-rate ablation for §5.1.

The paper claims a ~15 Hz cursor-sampling floor for the seven-feature M4
approach vector, justified only by a Nyquist argument. This script produces
the empirical curve: M4 click-prediction AUC vs. cursor sample rate.

Method — identical to the §5.1 headline EXCEPT for the downsampling:
  - attribution = organic_hybrid       (paper headline flavor)
  - click_buffer_ms = 500              (paper headline buffer)
  - feature vector = APPROACH_7        (the canonical M4-7)
  - LOSO = 47-fold LeaveOneGroupOut logistic regression, balanced,
    StandardScaler, C=1.0 — the exact pipeline from click_buffer_ablation.py
  - metrics = LOSO AUC, per-trial MRR@10, per-trial NDCG@1

The only difference from the headline is that, before feature aggregation,
each trial's `mousemove` event stream is greedily thinned to simulate an
N Hz cursor sample rate (compute_cursor_approach_features.downsample_hz).
`click` events are never thinned, so the click label/position survives.

Rates: {5, 10, 15, 20, 30, 60} Hz plus a "native" (no-downsample) baseline.

CRITICAL ANCHOR: the native run's M4 AUC must reproduce the paper's
canonical §5.1 headline of 0.847 (within ~+/-0.005). If it does not, the
script aborts before emitting any downsampled numbers.

Output:
  scripts/output/cikm-2026/sampling_rate_ablation.json

Run:
    .venv/bin/python scripts/sampling_rate_ablation.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# The §5.1 feature extractor (with the new downsample_hz capability) and
# the canonical M4-7 feature list / per-trial ranking metrics — reused
# verbatim so the ablation differs from the headline ONLY in downsampling.
from compute_cursor_approach_features import compute_approach_features  # noqa: E402
from click_buffer_ablation import APPROACH_7, per_trial_ranking_metrics  # noqa: E402

sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import get_trial_ids, load_mouse_events  # noqa: E402

# §5.1 headline config — held fixed across every rate.
ATTRIBUTION = "organic_hybrid"
CLICK_BUFFER_MS = 500

# Sampling rates to sweep. 0 == native (no downsampling) baseline.
# The 1-4 Hz rates probe BELOW the native cursor sample rate (AdSERP's
# mousemove stream is itself only ~10 Hz median / ~13 Hz mean, p90 ~23 Hz),
# which is the only regime where a sampling-rate floor could degrade AUC.
RATES_HZ = [1, 2, 3, 4, 5, 10, 15, 20, 30, 60]

# Canonical §5.1 headline anchor (organic_hybrid, buf500, M4-7).
CANONICAL_M4_AUC = 0.847
ANCHOR_TOL = 0.005

OUT_PATH = ROOT / "scripts/output/cikm-2026/sampling_rate_ablation.json"


def extract_features(downsample_hz: int) -> list[dict]:
    """Run the §5.1 extractor over every trial at a given sample rate.

    downsample_hz = 0 -> native (no thinning).
    """
    trial_ids = get_trial_ids()
    records: list[dict] = []
    n_ok = n_fail = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f"    {i+1}/{len(trial_ids)} trials", file=sys.stderr)
        try:
            recs = compute_approach_features(
                tid,
                attribution=ATTRIBUTION,
                click_buffer_ms=CLICK_BUFFER_MS,
                downsample_hz=downsample_hz,
            )
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print(f"    SKIP {tid}: {e}", file=sys.stderr)
            continue
        if recs:
            records.extend(recs)
            n_ok += 1
        else:
            n_fail += 1
    print(f"    extracted {len(records):,} records "
          f"({n_ok} trials ok, {n_fail} skipped)", file=sys.stderr)
    return records


def native_cursor_rate_stats() -> dict:
    """Measure the AdSERP cursor stream's *native* sample rate per trial.

    Context for the ablation: downsampling to N Hz can only degrade AUC if
    N is below the native rate. This quantifies how far below native the
    swept rates actually reach.
    """
    rates = []
    for tid in get_trial_ids():
        try:
            ev, _, _ = load_mouse_events(tid)
        except Exception:  # noqa: BLE001
            continue
        mm = [e for e in ev if e[1] == "mousemove"]
        if len(mm) < 5:
            continue
        dur_s = (mm[-1][0] - mm[0][0]) / 1000.0
        if dur_s <= 0:
            continue
        rates.append(len(mm) / dur_s)
    arr = np.array(rates, dtype=float)
    return {
        "n_trials": int(len(arr)),
        "median_hz": float(np.median(arr)),
        "mean_hz": float(arr.mean()),
        "p10_hz": float(np.percentile(arr, 10)),
        "p90_hz": float(np.percentile(arr, 90)),
        "max_hz": float(arr.max()),
        "frac_trials_below_15hz": float((arr < 15).mean()),
        "frac_trials_below_30hz": float((arr < 30).mean()),
    }


def m4_loso_eval(records: list[dict]) -> dict:
    """47-fold LOSO logistic regression on the canonical M4-7 vector.

    Mirrors click_buffer_ablation.fit_eval for the M4-7 variant exactly:
    StandardScaler + balanced LR (C=1.0, max_iter=5000), LeaveOneGroupOut
    by participant, AUC pooled over OOF predictions, plus per-trial
    MRR@10 / NDCG@1.
    """
    X = np.array(
        [[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records],
        dtype=float,
    )
    y = np.array([r["was_clicked"] for r in records], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in records])

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    logo = LeaveOneGroupOut()
    proba = cross_val_predict(
        pipe, X, y, groups=groups, cv=logo,
        method="predict_proba", n_jobs=-1,
    )[:, 1]
    auc = float(roc_auc_score(y, proba))
    mrr, ndcg1, n_trials = per_trial_ranking_metrics(records, proba)
    return {
        "m4_auc": auc,
        "m4_mrr10": float(mrr),
        "m4_ndcg1": float(ndcg1),
        "n_records": int(len(records)),
        "n_clicks": int(y.sum()),
        "n_participants": int(len(set(groups))),
        "n_ranked_trials": int(n_trials),
    }


def main() -> int:
    print("=" * 72)
    print("§5.1 cursor sampling-rate ablation — M4-7, organic_hybrid, buf500")
    print("=" * 72)

    results: dict[str, dict] = {}

    # ── Native cursor sample-rate diagnostic ──────────────────────────
    print("\n[diag] measuring AdSERP native cursor sample rate...",
          file=sys.stderr)
    rate_stats = native_cursor_rate_stats()
    print(f"  native cursor rate: median={rate_stats['median_hz']:.1f} Hz, "
          f"mean={rate_stats['mean_hz']:.1f} Hz, "
          f"p90={rate_stats['p90_hz']:.1f} Hz; "
          f"{rate_stats['frac_trials_below_15hz']*100:.0f}% of trials "
          f"already below 15 Hz")

    # ── Native baseline (anchor) ──────────────────────────────────────
    print("\n[native] extracting features (no downsampling)...", file=sys.stderr)
    t0 = time.time()
    native_recs = extract_features(downsample_hz=0)
    native = m4_loso_eval(native_recs)
    native["downsample_hz"] = None
    results["native"] = native
    print(f"\n  native   M4 AUC = {native['m4_auc']:.4f}  "
          f"MRR@10 = {native['m4_mrr10']:.4f}  "
          f"NDCG@1 = {native['m4_ndcg1']:.4f}  "
          f"({time.time()-t0:.0f}s)")

    # ── CRITICAL ANCHOR CHECK ─────────────────────────────────────────
    delta = native["m4_auc"] - CANONICAL_M4_AUC
    print(f"\n  anchor check: native M4 AUC {native['m4_auc']:.4f} vs "
          f"canonical {CANONICAL_M4_AUC:.3f}  (Δ = {delta:+.4f})")
    if abs(delta) > ANCHOR_TOL:
        print(f"\n  *** ANCHOR FAILED *** |Δ| = {abs(delta):.4f} > "
              f"tol {ANCHOR_TOL:.3f}")
        print("  Pipeline does NOT reproduce the §5.1 headline. "
              "Aborting before emitting downsampled numbers.")
        # Persist the failed native run for inspection, then bail.
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps({
            "status": "ANCHOR_FAILED",
            "canonical_m4_auc": CANONICAL_M4_AUC,
            "native": native,
            "anchor_delta": delta,
        }, indent=2))
        return 1
    print("  anchor OK — native baseline reproduces the §5.1 headline.")

    # ── Downsampled rates ─────────────────────────────────────────────
    for hz in RATES_HZ:
        print(f"\n[{hz} Hz] extracting downsampled features...", file=sys.stderr)
        t0 = time.time()
        recs = extract_features(downsample_hz=hz)
        res = m4_loso_eval(recs)
        res["downsample_hz"] = hz
        results[f"{hz}hz"] = res
        print(f"  {hz:>3d} Hz   M4 AUC = {res['m4_auc']:.4f}  "
              f"MRR@10 = {res['m4_mrr10']:.4f}  "
              f"NDCG@1 = {res['m4_ndcg1']:.4f}  "
              f"n={res['n_records']:,}  ({time.time()-t0:.0f}s)")

    # ── Summary table ─────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"{'rate':>8s}  {'M4 AUC':>8s}  {'MRR@10':>8s}  {'NDCG@1':>8s}  "
          f"{'n_rec':>8s}  {'ΔAUC vs native':>15s}")
    print("-" * 72)
    order = ["native"] + [f"{hz}hz" for hz in RATES_HZ]
    for key in order:
        r = results[key]
        d = r["m4_auc"] - native["m4_auc"]
        print(f"{key:>8s}  {r['m4_auc']:>8.4f}  {r['m4_mrr10']:>8.4f}  "
              f"{r['m4_ndcg1']:>8.4f}  {r['n_records']:>8,}  {d:>+15.4f}")

    payload = {
        "experiment": "§5.1 cursor sampling-rate ablation (15 Hz floor validation)",
        "config": {
            "attribution": ATTRIBUTION,
            "click_buffer_ms": CLICK_BUFFER_MS,
            "feature_vector": "M4-7 (APPROACH_7)",
            "features": APPROACH_7,
            "loso": "47-fold LeaveOneGroupOut LR, balanced, StandardScaler, C=1.0",
            "downsampling": "greedy mousemove thinning, clicks never thinned",
        },
        "canonical_m4_auc": CANONICAL_M4_AUC,
        "anchor_tolerance": ANCHOR_TOL,
        "anchor_delta": delta,
        "native_cursor_rate": rate_stats,
        "rates_hz": RATES_HZ,
        "results": results,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
