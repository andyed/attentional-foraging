"""Paired statistical tests for the the paper §5.3 Table 6 (tab:ltr).

Reads per-trial MRR / NDCG arrays from
scripts/output/ltr_typed_four_distinct_grades/summary_gaze_buf500.json
(produced by scripts/ltr_typed_four_distinct_grades.py with
--click-buffer-ms 500 after the per-trial-storage modification).

Runs three paired comparisons (paired by trial ID, since the same trials
are scored by every ranker):
  - L3  (3-grade collapse, 2/1/0/0)         vs Binary-click LambdaMART
  - L4  (4 distinct grades, 3/2/1/0, gaze)  vs Binary-click LambdaMART
  - L4  vs L3 (the absorption-relative-to-graded-ceiling comparison)

Tests applied for each pair (separately on MRR@10 and NDCG@10):
  - Wilcoxon signed-rank (paired, non-parametric -- primary)
  - Paired t-test (parametric)
  - Mean Δ across trials (effect size)
  - Bootstrap 95% CI on the mean delta

Output:
  - scripts/output/paper-output/paper_stat_tests_ltr.json
  - stdout: human-readable per-pair stats for §5.3.3 prose integration

Run:
    .venv/bin/python scripts/paper_stat_tests_ltr.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SRC_GAZE = ROOT / "scripts/output/ltr_typed_four_distinct_grades/summary_gaze_buf500.json"
SRC_CURSOR = ROOT / "scripts/output/ltr_typed_four_distinct_grades/summary_cursor_buf500.json"
OUT = ROOT / "scripts/output/paper-output/paper_stat_tests_ltr.json"

N_BOOT = 5000
RNG = np.random.default_rng(20260523)

ROW_KEY_BINARY = "LambdaMART (binary click)"
ROW_KEY_L3 = "LambdaMART (3-grade collapse, 2/1/0/0)"
ROW_KEY_L4 = "LambdaMART (4 distinct grades, 3/2/1/0)"


def align(a_vals, a_tids, b_vals, b_tids):
    """Align two per-trial arrays by trial id (intersect keys)."""
    a_map = dict(zip(a_tids, a_vals))
    b_map = dict(zip(b_tids, b_vals))
    common = sorted(set(a_tids) & set(b_tids))
    a_paired = np.array([a_map[t] for t in common], dtype=float)
    b_paired = np.array([b_map[t] for t in common], dtype=float)
    return a_paired, b_paired, common


def paired_tests(a: Sequence[float], b: Sequence[float],
                 label_a: str, label_b: str, metric: str) -> dict:
    """Paired tests on per-trial metric. a is the proposed ranker, b the baseline."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(a)
    diffs = a - b
    mean_delta = float(np.mean(diffs))
    median_delta = float(np.median(diffs))

    try:
        w_stat, w_p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        w_stat = float(w_stat); w_p = float(w_p)
    except ValueError:
        w_stat, w_p = float("nan"), 1.0

    t_stat, t_p = stats.ttest_rel(a, b, alternative="two-sided")
    t_stat = float(t_stat); t_p = float(t_p)

    sd = float(np.std(diffs, ddof=1)) if n >= 2 else float("nan")
    cohens_d_z = mean_delta / sd if sd > 0 else float("nan")

    # Bootstrap 95% CI on mean delta.
    boot = []
    for _ in range(N_BOOT):
        idx = RNG.integers(0, n, size=n)
        boot.append(float(np.mean(diffs[idx])))
    boot = np.asarray(boot)
    ci_lo, ci_hi = (float(np.percentile(boot, 2.5)),
                    float(np.percentile(boot, 97.5)))

    return {
        "metric": metric,
        "comparison": f"{label_a} vs {label_b}",
        "n_trials": int(n),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "mean_delta": mean_delta,
        "median_delta": median_delta,
        "delta_ci_95_lo": ci_lo,
        "delta_ci_95_hi": ci_hi,
        "wilcoxon_stat": w_stat,
        "wilcoxon_p": w_p,
        "paired_t_stat": t_stat,
        "paired_t_p": t_p,
        "cohens_d_z": cohens_d_z,
    }


def format_p(p: float) -> str:
    if not np.isfinite(p):
        return "n/a"
    if p < 0.001:
        return "< 0.001"
    if p < 0.01:
        return f"{p:.3f}"
    return f"{p:.2f}"


def load_metric_arrays(src: Path):
    """Return dict of {ranker_key: {mrr, ndcg, tids}} arrays."""
    with src.open() as f:
        d = json.load(f)
    out = {}
    for k, v in d["metrics"].items():
        if "per_trial_mrr" in v:
            out[k] = {
                "mrr": v["per_trial_mrr"],
                "ndcg": v["per_trial_ndcg"],
                "tids": v["per_trial_tids"],
            }
    return out


def main() -> int:
    if not SRC_GAZE.exists() or not SRC_CURSOR.exists():
        for s in (SRC_GAZE, SRC_CURSOR):
            print(f"missing: {s}" if not s.exists() else f"ok: {s}", file=sys.stderr)
        return 1

    gaze = load_metric_arrays(SRC_GAZE)
    cursor = load_metric_arrays(SRC_CURSOR)

    # Binary is identical across both (LambdaMART on binary click, no graded labels).
    bin_ = gaze[ROW_KEY_BINARY]
    # Cursor-labelled deployable variants (the row that ships at inference).
    l3_cursor = cursor[ROW_KEY_L3]
    l4_cursor = cursor[ROW_KEY_L4]
    # Gaze-supervised diagnostic ceiling.
    l4_gaze = gaze[ROW_KEY_L4]

    results = {"_provenance": {
        "source_gaze":   str(SRC_GAZE.relative_to(ROOT)),
        "source_cursor": str(SRC_CURSOR.relative_to(ROOT)),
    }}

    pairs = [
        ("L3cursor_vs_Binary",   "L3 (3-class cursor)",       "Binary click",       l3_cursor, bin_),
        ("L4cursor_vs_Binary",   "L4 (4-class cursor)",       "Binary click",       l4_cursor, bin_),
        ("L4gaze_vs_Binary",     "L4 (4-class gaze ceiling)", "Binary click",       l4_gaze,   bin_),
        ("L4cursor_vs_L3cursor", "L4 (4-class cursor)",       "L3 (3-class cursor)", l4_cursor, l3_cursor),
        ("L4gaze_vs_L4cursor",   "L4 (gaze ceiling)",         "L4 (cursor)",         l4_gaze,   l4_cursor),
        ("L4gaze_vs_L3cursor",   "L4 (gaze ceiling)",         "L3 (cursor)",         l4_gaze,   l3_cursor),
    ]
    pairs = [(k, la, lb, a["mrr"], a["tids"], a["ndcg"], b["mrr"], b["tids"], b["ndcg"])
             for (k, la, lb, a, b) in pairs]

    print("=" * 88, file=sys.stderr)
    print("Table 6 (§5.3.3, tab:ltr) -- paired tests on per-trial MRR@10 and NDCG@10",
          file=sys.stderr)
    print("=" * 88, file=sys.stderr)

    for key, la, lb, a_mrr, a_tids, a_ndcg, b_mrr, b_tids, b_ndcg in pairs:
        print(f"\n[{la} vs {lb}]", file=sys.stderr)

        # MRR
        am, bm, common = align(a_mrr, a_tids, b_mrr, b_tids)
        # NDCG (aligned on same trial set)
        an, bn, _ = align(a_ndcg, a_tids, b_ndcg, b_tids)

        res_mrr = paired_tests(am, bm, la, lb, "MRR@10")
        res_ndcg = paired_tests(an, bn, la, lb, "NDCG@10")
        results[key] = {"mrr10": res_mrr, "ndcg10": res_ndcg, "n_trials_paired": len(common)}

        print(
            f"  MRR@10:  ΔMRR = {res_mrr['mean_delta']:+.4f} "
            f"[95% CI {res_mrr['delta_ci_95_lo']:+.4f}, {res_mrr['delta_ci_95_hi']:+.4f}], "
            f"Wilcoxon p = {format_p(res_mrr['wilcoxon_p'])}, d_z = {res_mrr['cohens_d_z']:.2f}, "
            f"n = {res_mrr['n_trials']}",
            file=sys.stderr,
        )
        print(
            f"  NDCG@10: ΔNDCG = {res_ndcg['mean_delta']:+.4f} "
            f"[95% CI {res_ndcg['delta_ci_95_lo']:+.4f}, {res_ndcg['delta_ci_95_hi']:+.4f}], "
            f"Wilcoxon p = {format_p(res_ndcg['wilcoxon_p'])}, d_z = {res_ndcg['cohens_d_z']:.2f}",
            file=sys.stderr,
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
