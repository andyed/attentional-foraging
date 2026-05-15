"""§4.3 diagnostic-ceiling producer — closes the LOSO-fit loop.

Paper-v5 footnote [^a] in §4.3 claims that the LAB gaze-gated extractor
(fixation-timed cursor sampling, not inference-deployable) reaches AUC 0.781
on the canonical seven-feature M4 vector under the same Δ = 500 ms
click-buffer the deployable classifier uses, and that the deployable
cursor classifier (0.753) lands within 0.028 AUC of this diagnostic upper
bound on identical features and protocol.

Per scripts/output/cikm-2026/diagnostic_claims.json the four headline
numbers (0.781 / 0.795 / 0.753 / 0.028 gap) had been computed inline as
a one-off bash invocation. This script regenerates them from committed
inputs so a reviewer can reproduce them with one command.

Protocol — matched to scripts/m5_cursor_only_taxonomy.py
--------------------------------------------------------
- Pool: approached non-click pool under [organic] (min_dist < 100 &
  ~was_clicked). Same gate as §4.3's deployable classifier.
- Target: NB22 gaze-regression label (deferred=1, eval_rejected=0).
  Cached in scripts/output/approach_threshold_sensitivity/
  regression_labels_cache_organic.json (positional w.r.t. the canonical
  Δ=0 features file). Re-keyed by (trial_id, position) so buffered files
  that drop trials with no surviving fixations stay aligned.
- Model: LOSO-by-participant balanced LR with in-fold StandardScaler.
- Metric: AUC on out-of-fold predict_proba.

Cells evaluated
---------------
                                                        target | paper §4.3
  (a) canonical extractor × M4 canonical (7 features)   0.753  | "deployable"
  (b) canonical extractor × M4 legacy   (9 features)    ~0.769 | (completeness)
  (c) gaze-gated extractor × M4 canonical (7 features)  0.781  | "diagnostic ceiling"
  (d) gaze-gated extractor × M4 legacy   (9 features)   0.795  | diagnostic_claims.json

Matched-protocol gap = (c).auc − (a).auc → target 0.028.

Output: scripts/output/cikm-2026/diagnostic_ceiling.json

Usage:
    python -m scripts.compute_diagnostic_ceiling
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from scipy.stats import wilcoxon

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
DATA = ROOT / "AdSERP/data"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json"
OUT_PATH = ROOT / "scripts/output/cikm-2026/diagnostic_ceiling.json"
APPROACH_THRESHOLD_PX = 100
CLICK_BUFFER_MS = 500
ATTRIBUTION = "organic"

# Paper §3.4 leakage-validated seven-feature M4. Legacy adds the two
# distance terms screened out by the click-buffer protocol.
M4_CANONICAL = ["min_dist", "mean_dist",
                "dwell_in_proximity_ms",
                "mean_approach_velocity", "max_approach_velocity",
                "direction_changes", "frac_decreasing"]
M4_LEGACY = M4_CANONICAL + ["final_dist", "retreat_dist"]

# Feature-file pairs: (extractor_label, canonical_path, buf500_path).
# canonical_path is the Δ=0 file the regression-label cache is positional
# against; buf500_path is the Δ=500ms file we actually fit on.
EXTRACTORS = {
    "canonical_extractor": (
        DATA / "cursor-approach-features-organic.json",
        DATA / "cursor-approach-features-organic-buf500.json",
    ),
    "gaze_gated_extractor": (
        DATA / "cursor-approach-features-lab-gaze-gated-organic.json",
        DATA / "cursor-approach-features-lab-gaze-gated-organic-buf500.json",
    ),
}


def participant_of(trial_id: str) -> str:
    return trial_id.split("-", 1)[0]


def load_pool(canonical_path: Path, buf500_path: Path) -> pl.DataFrame:
    """Load the buf500 features file with the gaze-regression label
    attached via (trial_id, position) re-keying off the canonical positional
    cache. Filter to the approached non-click pool."""
    canonical_records = json.load(open(canonical_path))
    cache_array = np.array(json.load(open(REG_CACHE)), dtype=bool)
    if len(cache_array) != len(canonical_records):
        raise RuntimeError(
            f"label cache length {len(cache_array)} != canonical records "
            f"length {len(canonical_records)} — re-key alignment broken")
    label_by_key = {
        (r["trial_id"], r["position"]): bool(cache_array[i])
        for i, r in enumerate(canonical_records)
    }

    buf500_records = json.load(open(buf500_path))
    for r in buf500_records:
        r["gaze_regressed"] = label_by_key.get((r["trial_id"], r["position"]), False)

    df = pl.DataFrame(buf500_records)
    return df.filter(
        (pl.col("min_dist") < APPROACH_THRESHOLD_PX) & ~pl.col("was_clicked")
    )


def fit_loso(df: pl.DataFrame, feature_list: list[str]) -> dict:
    """LOSO-by-participant class-balanced LR, in-fold StandardScaler.
    Returns AUC + per-participant AUCs + per-participant indices."""
    X = df.select(feature_list).to_numpy().astype(float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = df["gaze_regressed"].cast(int).to_numpy()
    groups = np.array([participant_of(t) for t in df["trial_id"].to_list()])

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced",
                                  C=1.0, solver="lbfgs")),
    ])
    n_groups = len(np.unique(groups))
    gkf = GroupKFold(n_splits=n_groups)
    oof = np.full(len(y), np.nan, dtype=float)
    per_participant: dict[str, float] = {}
    for tr_idx, te_idx in gkf.split(X, y, groups=groups):
        held = groups[te_idx[0]]
        m = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, class_weight="balanced",
                                      C=1.0, solver="lbfgs")),
        ])
        m.fit(X[tr_idx], y[tr_idx])
        oof[te_idx] = m.predict_proba(X[te_idx])[:, 1]
        if len(np.unique(y[te_idx])) == 2:
            per_participant[held] = float(roc_auc_score(y[te_idx], oof[te_idx]))
    auc = float(roc_auc_score(y, oof))
    pp_aucs = np.array(list(per_participant.values()))
    return {
        "auc": auc,
        "per_participant_mean": float(pp_aucs.mean()),
        "per_participant_sd": float(pp_aucs.std(ddof=1)),
        "per_participant_n": int(len(pp_aucs)),
        "per_participant_aucs": per_participant,
        "_oof": oof,
        "_y": y,
        "_groups": groups,
    }


def main() -> None:
    print("=" * 70)
    print("§4.3 diagnostic ceiling — LOSO LR producer")
    print("=" * 70)
    print(f"attribution = {ATTRIBUTION}, click_buffer_ms = {CLICK_BUFFER_MS}")

    pools: dict[str, pl.DataFrame] = {}
    for ext_name, (canonical_path, buf500_path) in EXTRACTORS.items():
        df = load_pool(canonical_path, buf500_path)
        pools[ext_name] = df
        n_def = int(df.filter(pl.col("gaze_regressed")).height)
        n_rej = int(df.filter(~pl.col("gaze_regressed")).height)
        print(f"\n[{ext_name}] pool n={len(df)} (deferred={n_def}, eval_rej={n_rej})")

    cells: dict[str, dict] = {}
    for ext_name in EXTRACTORS:
        df = pools[ext_name]
        for fset_name, feature_list in [("canonical_7", M4_CANONICAL),
                                         ("legacy_9",    M4_LEGACY)]:
            cell_key = f"{ext_name}__{fset_name}"
            res = fit_loso(df, feature_list)
            print(f"  [{cell_key}] AUC = {res['auc']:.4f}  "
                  f"per-part mean = {res['per_participant_mean']:.4f} ± "
                  f"{res['per_participant_sd']:.4f}  (n={res['per_participant_n']})")
            cells[cell_key] = res

    # Matched-protocol gap: gaze-gated canonical AUC − deployable canonical AUC.
    deployable = cells["canonical_extractor__canonical_7"]
    ceiling    = cells["gaze_gated_extractor__canonical_7"]
    gap_auc = ceiling["auc"] - deployable["auc"]
    print()
    print(f"matched-protocol gap (ceiling − deployable, canonical-7) = {gap_auc:+.4f}")
    print(f"  paper §4.3 footnote target: 0.028")

    # Paired Wilcoxon on per-participant AUCs (ceiling > deployable).
    common_participants = sorted(set(deployable["per_participant_aucs"]) &
                                 set(ceiling["per_participant_aucs"]))
    pp_dep = np.array([deployable["per_participant_aucs"][p] for p in common_participants])
    pp_ceil = np.array([ceiling["per_participant_aucs"][p] for p in common_participants])
    try:
        w = wilcoxon(pp_ceil, pp_dep, alternative="greater")
        wilcoxon_p = float(w.pvalue)
    except Exception:
        wilcoxon_p = float("nan")
    n_ceil_geq_dep = int(np.sum(pp_ceil >= pp_dep))
    print(f"paired Wilcoxon (ceiling > deployable, per-participant): "
          f"p = {wilcoxon_p:.4f}, ceiling>=deployable in "
          f"{n_ceil_geq_dep}/{len(common_participants)}")

    # Strip the heavy arrays before serializing.
    out_cells: dict[str, dict] = {}
    for k, c in cells.items():
        out_cells[k] = {
            "auc": c["auc"],
            "per_participant_mean": c["per_participant_mean"],
            "per_participant_sd": c["per_participant_sd"],
            "per_participant_n": c["per_participant_n"],
            "per_participant_aucs": c["per_participant_aucs"],
        }

    summary = {
        "experiment": "§4.3 diagnostic ceiling — gaze-gated vs deployable LOSO LR",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "config": {
            "attribution": ATTRIBUTION,
            "click_buffer_ms": CLICK_BUFFER_MS,
            "approach_threshold_px": APPROACH_THRESHOLD_PX,
            "model": "LOSO-by-participant class-balanced LR + in-fold StandardScaler",
            "target_label": "NB22 gaze_regression label (deferred=1, eval_rejected=0)",
            "pool_definition": "approached non-click episodes under [organic]: "
                               "min_dist < 100 & ~was_clicked",
            "label_alignment": "(trial_id, position) re-keyed off canonical Δ=0 cache",
            "m4_canonical": M4_CANONICAL,
            "m4_legacy_extras": ["final_dist", "retreat_dist"],
            "input_files": {
                ext_name: {
                    "canonical_features": str(canonical_path.relative_to(ROOT)),
                    "buf500_features": str(buf500_path.relative_to(ROOT)),
                }
                for ext_name, (canonical_path, buf500_path) in EXTRACTORS.items()
            },
            "regression_label_cache": str(REG_CACHE.relative_to(ROOT)),
        },
        "cells": out_cells,
        "matched_protocol_gap": {
            "definition": "gaze_gated_extractor.canonical_7.auc - "
                          "canonical_extractor.canonical_7.auc",
            "auc_gap": float(gap_auc),
            "ceiling_canonical_auc": float(ceiling["auc"]),
            "deployable_canonical_auc": float(deployable["auc"]),
            "wilcoxon_per_participant_p_one_sided": wilcoxon_p,
            "ceiling_geq_deployable_n": n_ceil_geq_dep,
            "ceiling_geq_deployable_total": len(common_participants),
        },
        "paper_targets_v5_footnote_a": {
            "deployable_canonical_auc": 0.753,
            "diagnostic_ceiling_canonical_auc": 0.781,
            "diagnostic_ceiling_legacy_auc": 0.795,
            "matched_protocol_gap_auc": 0.028,
            "tolerance_note": "values rounded to 3 dp in the paper; this script "
                              "reports 4 dp",
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
