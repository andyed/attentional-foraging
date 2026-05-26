"""Paired statistical tests for the the paper §5.1/§5.2 tables.

Reads per-fold (per-participant) AUCs from
scripts/output/paper-output/click_buffer_ablation.json
(produced by scripts/click_buffer_ablation.py).

Runs:
  - Table 4 (§5.1, tab:m1m4) — M4 vs {M1, M2, M3} at attribution=organic_hybrid,
    buffer=500ms canonical.
      Hypotheses: M4 > M1 (significant), M4 > M2 (significant),
                  M4 ≈ M3 (the absorption result -- NOT significantly different).
  - Table 5 (§5.2, tab:click_buffer) — M4 across buffer Δ ∈ {0, 200, 500, 1000} ms
    at attribution=organic_hybrid.
      Hypothesis: AUC is statistically equivalent across Δ
                  (the signal is not a terminal click-window artifact).

Tests applied for each pair:
  - Wilcoxon signed-rank (paired, non-parametric -- primary)
  - Paired t-test (paired, parametric)
  - Mean ΔAUC across folds (effect size)
  - Bootstrap 95% CI on ΔAUC (paired-by-participant resampling)

Output:
  - scripts/output/paper-output/paper_stat_tests.json
  - stdout: human-readable per-pair stats for paper integration

Run:
    .venv/bin/python scripts/paper_stat_tests.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts/output/paper-output/click_buffer_ablation.json"
OUT = ROOT / "scripts/output/paper-output/paper_stat_tests.json"

ATTRIBUTION = "organic_hybrid"
CANONICAL_BUFFER = 500
BUFFER_GRID = [0, 200, 500, 1000]
N_BOOT = 5000
RNG = np.random.default_rng(20260523)


def load_grid() -> dict:
    with SRC.open() as f:
        return json.load(f)["grid"]


def cell(grid: dict, buffer: int, variant: str) -> dict:
    return grid[f"{ATTRIBUTION}|buf{buffer}|{variant}"]


def paired_tests(a: Sequence[float], b: Sequence[float], label_a: str, label_b: str) -> dict:
    """Run paired tests comparing per-fold AUCs of two models.

    a > b under the alternative if a is the proposed (better) model.
    Reports two-sided tests so the user can interpret regardless of direction.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    assert len(a) == len(b), f"length mismatch: {len(a)} vs {len(b)}"
    n = len(a)
    diffs = a - b
    mean_delta = float(np.mean(diffs))
    median_delta = float(np.median(diffs))

    # Wilcoxon signed-rank (paired, non-parametric) -- primary test.
    # zero_method='wilcox' drops exact zeros from the analysis.
    try:
        w_stat, w_p = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        w_stat = float(w_stat)
        w_p = float(w_p)
    except ValueError:
        # All differences zero -- not significantly different by construction.
        w_stat, w_p = float("nan"), 1.0

    # Paired t-test (parametric).
    t_stat, t_p = stats.ttest_rel(a, b, alternative="two-sided")
    t_stat = float(t_stat)
    t_p = float(t_p)

    # Cohen's d_z for paired differences = mean(diff) / sd(diff).
    sd = float(np.std(diffs, ddof=1)) if n >= 2 else float("nan")
    cohens_d_z = mean_delta / sd if sd > 0 else float("nan")

    # Bootstrap 95% CI on the mean ΔAUC (paired-by-participant resampling).
    boot_means = []
    for _ in range(N_BOOT):
        idx = RNG.integers(0, n, size=n)
        boot_means.append(float(np.mean(diffs[idx])))
    boot_means = np.asarray(boot_means)
    ci_lo, ci_hi = (float(np.percentile(boot_means, 2.5)),
                    float(np.percentile(boot_means, 97.5)))

    return {
        "comparison": f"{label_a} vs {label_b}",
        "n_folds": int(n),
        "mean_auc_a": float(np.mean(a)),
        "mean_auc_b": float(np.mean(b)),
        "mean_delta_auc": mean_delta,
        "median_delta_auc": median_delta,
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


def main() -> int:
    grid = load_grid()
    results = {"table4_m1m4": {}, "table5_click_buffer": {}}

    # --- Table 4 (§5.1): M4-7 vs {M1, M2, M3-7} at canonical buffer ---
    print("\n" + "=" * 78, file=sys.stderr)
    print("Table 4 (§5.1, tab:m1m4) -- canonical buffer = 500 ms, organic_hybrid", file=sys.stderr)
    print("=" * 78, file=sys.stderr)

    m4_cell = cell(grid, CANONICAL_BUFFER, "M4-7")
    m4_aucs = m4_cell["per_part_aucs"]
    print(f"M4-7 per-fold n={len(m4_aucs)}, mean={np.mean(m4_aucs):.4f}, "
          f"sd={np.std(m4_aucs, ddof=1):.4f}", file=sys.stderr)

    for variant_label, variant_key in [("M1", "M1"), ("M2", "M2"), ("M3 (M3-7)", "M3-7")]:
        b_cell = cell(grid, CANONICAL_BUFFER, variant_key)
        b_aucs = b_cell["per_part_aucs"]
        assert m4_cell["per_part_pids"] == b_cell["per_part_pids"], \
            f"pid mismatch between M4-7 and {variant_key} -- per-fold AUCs not paired"
        res = paired_tests(m4_aucs, b_aucs, "M4-7 (canonical)", variant_label)
        results["table4_m1m4"][f"M4-7_vs_{variant_key}"] = res
        print(
            f"\n  M4-7 vs {variant_label}: ΔAUC = {res['mean_delta_auc']:+.4f} "
            f"[95% CI {res['delta_ci_95_lo']:+.4f}, {res['delta_ci_95_hi']:+.4f}], "
            f"Wilcoxon p = {format_p(res['wilcoxon_p'])}, "
            f"paired t p = {format_p(res['paired_t_p'])}, "
            f"d_z = {res['cohens_d_z']:.2f}",
            file=sys.stderr,
        )

    # --- Table 5 (§5.2): M4-7 across buffer Δ grid ---
    print("\n" + "=" * 78, file=sys.stderr)
    print("Table 5 (§5.2, tab:click_buffer) -- M4-7 across Δ ∈ {0, 200, 500, 1000} ms",
          file=sys.stderr)
    print("=" * 78, file=sys.stderr)

    m4_by_buf = {buf: cell(grid, buf, "M4-7")["per_part_aucs"] for buf in BUFFER_GRID}
    pids_by_buf = {buf: cell(grid, buf, "M4-7")["per_part_pids"] for buf in BUFFER_GRID}
    canonical_pids = pids_by_buf[CANONICAL_BUFFER]

    # All pairwise comparisons within the M4-7 buffer grid.
    pairs = [(0, 200), (0, 500), (0, 1000),
             (200, 500), (200, 1000),
             (500, 1000)]
    for buf_a, buf_b in pairs:
        # Sanity check: pids align across buffers (LOSO over the same 47 participants).
        if pids_by_buf[buf_a] != pids_by_buf[buf_b]:
            print(f"  WARN: pid mismatch buf{buf_a} vs buf{buf_b}", file=sys.stderr)
        res = paired_tests(m4_by_buf[buf_a], m4_by_buf[buf_b],
                           f"M4-7@Δ={buf_a}", f"M4-7@Δ={buf_b}")
        results["table5_click_buffer"][f"buf{buf_a}_vs_buf{buf_b}"] = res
        print(
            f"\n  Δ={buf_a:>4d} vs Δ={buf_b:>4d}: "
            f"ΔAUC = {res['mean_delta_auc']:+.4f} "
            f"[95% CI {res['delta_ci_95_lo']:+.4f}, {res['delta_ci_95_hi']:+.4f}], "
            f"Wilcoxon p = {format_p(res['wilcoxon_p'])}, "
            f"paired t p = {format_p(res['paired_t_p'])}",
            file=sys.stderr,
        )

    # Friedman test (omnibus across all four buffers, non-parametric).
    n_folds = len(canonical_pids)
    friedman_matrix = np.column_stack([m4_by_buf[buf] for buf in BUFFER_GRID])
    fr_stat, fr_p = stats.friedmanchisquare(*[friedman_matrix[:, i] for i in range(4)])
    results["table5_click_buffer"]["friedman_omnibus"] = {
        "n_folds": int(n_folds),
        "buffers_ms": BUFFER_GRID,
        "friedman_stat": float(fr_stat),
        "friedman_p": float(fr_p),
        "df": 3,
    }
    print(f"\n  Friedman omnibus (k=4 buffers, n={n_folds}): "
          f"χ² = {fr_stat:.3f}, df=3, p = {format_p(fr_p)}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
