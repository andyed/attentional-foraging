"""Shared harness for the constant-sensitivity ablations.

Motivation: several pipeline constants could be called ad-hoc — why the 5th
fixation, why a 100 px proximity zone, why the AOI center rather than the
result link as the distance anchor. Each deserves a sweep, not an assertion.

Three sweep scripts sit on top of this module:
  - proximity_zone_ablation.py   (the 100 px proximity zone)
  - distance_anchor_ablation.py  (AOI-center vs top-edge vs nearest-boundary)
  - fixation_k_ablation.py       (the fifth-fixation early-scan boundary)

Protocol — identical to the canonical Sec. 4.1/5.1 headline except for the one
swept constant:
  - attribution   = organic_hybrid   (paper headline flavor)
  - click buffer  = 500 ms           (paper headline leakage control)
  - features      = APPROACH_7 (M4-7), from click_buffer_ablation.py
  - LOSO          = 47-fold leave-one-participant-out logistic regression,
                    StandardScaler, balanced class weights, C = 1.0
  - anchor check  = the unmodified-constant run must reproduce the paper's
                    canonical M4 AUC of 0.847 within +/-0.005 (same guard as
                    sampling_rate_ablation.py) or the sweep aborts.

Constant isolation mechanism: instead of copy-pasting the canonical extractor
(which drifts), each sweep loads scripts/compute_cursor_approach_features.py
(or phase_restricted_ablation.py) as SOURCE TEXT, applies an exact-string
replacement of the one constant under study (asserting the pattern occurs
exactly once), and exec's the result into a fresh module. Every other byte of
the extractor is guaranteed identical to the canonical script on disk.

The LOSO split is a deterministic function of the participant ids, and the
record set (trial_id, position) is unchanged by any of the swept constants,
so per-value AUC differences are attributable to the constant alone. Each
sweep script asserts record-set identity across its sweep values.

n_jobs is capped at 4 (this Mac hosts concurrent work; do not fan out wider).

Not a standalone script — import from the three sweep scripts.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "notebooks-v2"))

# click_buffer_ablation.py imports muriel.provenance via the
# ~/.claude/skills/muriel symlink, which since 2026-08-07 points at the
# plugin skill dir rather than the package root — add the real package root
# so the import resolves without touching the canonical script.
sys.path.insert(0, "/Users/andyed/Documents/dev/muriel")

# Canonical feature lists + per-trial ranking metrics — reused verbatim
# from the Sec. 4.1/4.4 canonical grid script (same imports as
# sampling_rate_ablation.py). Both vectors are reported per sweep condition:
# M4-7 is the paper's leakage-corrected definition of M4; M4-9 adds
# final_dist + retreat_dist (the pair the Sec. 5.2 leakage screen excludes)
# and matches m4_nb21_hybrid_rerun.py's nine-feature M4_FEATURES as-is.
from click_buffer_ablation import (  # noqa: E402
    APPROACH_7, APPROACH_9, per_trial_ranking_metrics,
)
from data_loader import get_trial_ids  # noqa: E402

CCAF_PATH = ROOT / "scripts/compute_cursor_approach_features.py"
PHASE_PATH = ROOT / "scripts/phase_restricted_ablation.py"

# Canonical Sec. 4.1/5.1 headline configuration — held fixed in every sweep.
ATTRIBUTION = "organic_hybrid"
CLICK_BUFFER_MS = 500

# Canonical headline anchors (organic_hybrid, buf500) and tolerance.
# M4-7 value matches sampling_rate_ablation.py's anchor (the paper's 0.847);
# M4-9 value is the organic_hybrid|buf500|M4-9 cell of
# scripts/output/paper-output/click_buffer_ablation.json (0.8671).
CANONICAL_M4_AUC = 0.847      # M4-7 (paper definition of M4)
CANONICAL_M4_9_AUC = 0.8671   # M4-9 (adds final_dist + retreat_dist)
ANCHOR_TOL = 0.005

OUT_DIR = ROOT / "scripts/output/ablations"

# Host courtesy: this Mac runs other work; never fan out beyond 4 processes.
N_JOBS = 4


def load_patched_module(src_path: Path, replacements: list[tuple[str, str]],
                        name: str) -> types.ModuleType:
    """Load a script as a module with exact-string constant substitutions.

    Every pattern must occur exactly once in the source; otherwise the
    substitution would be ambiguous and we abort rather than guess.
    An empty replacement list loads the canonical script byte-identical.
    """
    src = Path(src_path).read_text()
    for old, new in replacements:
        n = src.count(old)
        if n != 1:
            raise RuntimeError(
                f"patch pattern occurs {n} times (need exactly 1) in "
                f"{src_path}: {old!r}")
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(src_path)
    sys.modules[name] = mod  # so dataclasses/pickling inside behave
    exec(compile(src, str(src_path), "exec"), mod.__dict__)
    return mod


def extract_records(compute_fn, label: str) -> list[dict]:
    """Run a compute_approach_features-compatible extractor over every trial
    under the canonical organic_hybrid + 500 ms click-buffer configuration.
    Mirrors sampling_rate_ablation.extract_features."""
    trial_ids = get_trial_ids()
    records: list[dict] = []
    n_ok = n_fail = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f"    [{label}] {i + 1}/{len(trial_ids)} trials",
                  file=sys.stderr)
        try:
            recs = compute_fn(
                tid,
                attribution=ATTRIBUTION,
                click_buffer_ms=CLICK_BUFFER_MS,
            )
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print(f"    [{label}] SKIP {tid}: {e}", file=sys.stderr)
            continue
        if recs:
            records.extend(recs)
            n_ok += 1
        else:
            n_fail += 1
    print(f"    [{label}] extracted {len(records):,} records "
          f"({n_ok} trials ok, {n_fail} skipped)", file=sys.stderr)
    return records


def loso_eval_matrix(X: np.ndarray, y: np.ndarray,
                     groups: np.ndarray) -> dict:
    """Canonical LOSO logistic regression on a prebuilt design matrix.

    Same pipeline as click_buffer_ablation.fit_eval / sampling_rate_ablation
    (StandardScaler + balanced LR, C=1.0, max_iter=5000, leave-one-
    participant-out), with n_jobs capped at N_JOBS instead of -1.

    Returns pooled OOF AUC plus per-participant fold AUCs (mean +/- sd),
    matching fit_eval's per-fold inclusion rule (>= 10 records, both classes).
    """
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced",
                                  C=1.0)),
    ])
    logo = LeaveOneGroupOut()
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=logo,
                              method="predict_proba", n_jobs=N_JOBS)[:, 1]
    auc = float(roc_auc_score(y, proba))
    per_fold = []
    for pid in sorted(set(groups)):
        m = groups == pid
        if m.sum() < 10 or len(set(y[m])) < 2:
            continue
        per_fold.append(float(roc_auc_score(y[m], proba[m])))
    pf = np.array(per_fold, dtype=float)
    return {
        "m4_auc": auc,
        "per_fold_auc_mean": float(pf.mean()) if len(pf) else float("nan"),
        "per_fold_auc_sd": float(pf.std(ddof=1)) if len(pf) >= 2 else float("nan"),
        "n_folds": int(len(pf)),
        "n_records": int(len(y)),
        "n_clicks": int(y.sum()),
        "n_participants": int(len(set(groups))),
        "_proba": proba,  # stripped before JSON serialization
    }


def m4_loso_eval(records: list[dict], features: list[str]) -> dict:
    """47-fold LOSO on the given feature vector from raw feature records.
    Adds per-trial MRR@10 / NDCG@1 (click_buffer_ablation metrics)."""
    X = np.array(
        [[float(r.get(f, 0.0) or 0.0) for f in features] for r in records],
        dtype=float,
    )
    y = np.array([r["was_clicked"] for r in records], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in records])
    res = loso_eval_matrix(X, y, groups)
    proba = res.pop("_proba")
    mrr, ndcg1, n_trials = per_trial_ranking_metrics(records, proba)
    res["m4_mrr10"] = float(mrr)
    res["m4_ndcg1"] = float(ndcg1)
    res["n_ranked_trials"] = int(n_trials)
    return res


def m4_loso_eval_both(records: list[dict]) -> dict:
    """Both canonical feature vectors on the same records: M4-7 (paper
    definition of M4, leakage-corrected) and M4-9 (adds the structurally
    leaky final_dist + retreat_dist; matches m4_nb21_hybrid_rerun.py's
    nine-feature M4_FEATURES). The extractor emits all nine features
    regardless, so this costs one extra LOSO fit, not a re-extraction."""
    return {
        "M4_7": m4_loso_eval(records, APPROACH_7),
        "M4_9": m4_loso_eval(records, APPROACH_9),
    }


def record_key_set(records: list[dict]) -> set:
    return {(r["trial_id"], r["position"]) for r in records}


def check_anchor(auc: float, canonical: float = CANONICAL_M4_AUC,
                 tol: float = ANCHOR_TOL, label: str = "") -> float:
    """Abort-worthy anchor check; returns the delta."""
    delta = auc - canonical
    print(f"  anchor check {label}: AUC {auc:.4f} vs canonical "
          f"{canonical:.3f}  (delta = {delta:+.4f})")
    if abs(delta) > tol:
        raise SystemExit(
            f"ANCHOR FAILED ({label}): |delta| = {abs(delta):.4f} > "
            f"tol {tol:.3f} — pipeline does not reproduce the canonical "
            f"headline; aborting before emitting sweep numbers.")
    print("  anchor OK.")
    return delta
