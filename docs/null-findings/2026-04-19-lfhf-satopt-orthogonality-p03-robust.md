# LF/HF × Satisficer/Optimizer Orthogonality — P0–P3 Robustness (ETTAC queue item 3)

**Date:** 2026-04-19
**Script:** `scripts/lfhf_satopt_orthogonality_p03.py`
**Output:** `scripts/output/lfhf_satopt_orthogonality_p03/summary.json`

## Motivation

The original orthogonality finding (memory: `project_lfhf_orthogonality.md`):

> Per-participant LF/HF trajectory does NOT predict satisficer vs optimizer
> classification on AdSERP. Full P0–P9: χ² = 0.52, p = 0.77; LOO-LR AUC = 0.43;
> Spearman(slope, regression_rate) = −0.226, p = 0.13.

Framed as a **dissociation** for ETTAC — load trajectory is an independent
individual-difference axis from behavioral strategy.

Worry: satopt terciles are partly self-selected at depth (who scrolls to
P6+ is who), and NB11 has a satopt–LHIPA duration confound at depth. So
the orthogonality result might have been *depth-noise-assisted* — the
gradient and the strategy axis could have been swallowed up by missing-data
patterns at positions where neither measurement is clean.

This re-check computes the same dissociation using ONLY the **steep phase
(P0–P3)**, where K10 says the gradient is universal (ρ = −1.000 on
position medians) and where every participant contributes.

## Method

Per-participant features computed from position-median LF/HF within each
range: slope (OLS fit), mean, `pos_first`, early/late ratio, trial IQR.
Satopt binary label via median split on `regression_rate` (median = 0.567,
N = 24 satisficers / 22 optimizers). LOO-LR with standard scaling +
class-balanced weights. χ² on trajectory-category × satopt contingency.
Spearman(slope, regression_rate) as a continuous check.

## Results

| Metric | Full P0–P9 | Steep P0–P3 |
|:---|---:|---:|
| N with all features finite | 25 | **46** |
| LOO-LR AUC | 0.375 | 0.523 |
| Majority baseline | 0.68 | 0.52 |
| χ² p | 0.15 | n/a (flat cat N=0) |
| Spearman(slope, rate) ρ | −0.197 | **−0.020** |
| Spearman(slope, rate) p | 0.19 | **0.90** |

**Per-feature t-tests (Welch, P0–P3):** every feature |d| < 0.21, every p > 0.50.
No hint of a behavioral signature in steep-phase LF/HF features.

**Trajectory × satopt contingency (P0–P3):**

|  | Satisficer | Optimizer |
|:---|---:|---:|
| Declining | 17 | 19 |
| Flat      |  0 |  0 |
| Increasing |  7 |  3 |

In P0–P3 no participant qualifies as "flat" (consistent with K10
universality — everybody declines). The declining/increasing split is
the only residual variance, and it does not differentiate satopt.

## Verdict

Orthogonality is **stronger in P0–P3 than in the original full range**,
not weaker. The dissociation claim is robust.

1. **ρ(slope, regression_rate) drops from −0.197 (p = 0.19) to −0.020
   (p = 0.90)** — the already-weak full-range trend evaporates in the
   steep phase.
2. **LOO-LR AUC sits at chance (0.523 vs 0.522 baseline)** — no classifier
   can learn satopt from 5 LF/HF features in the steep phase.
3. **Every participant has finite features in steep phase (N = 46),
   vs only 25 in the full range.** The full-range AUC = 0.375 was
   dominated by 25 participants with deep-position data — a
   concentration-of-exposure artifact. Steep-phase AUC uses the whole
   cohort.

The original framing was not depth-noise-assisted; if anything, the
original full-range AUC = 0.375 was *weaker* than the true orthogonality
precisely because of deep-position missingness. The load-trajectory axis
is genuinely orthogonal to the regression-rate / satopt axis on the
range where the gradient claim lives.

## Implication for ETTAC

- Cite orthogonality at the steep phase (P0–P3) where the gradient claim
  (K10) also lives — the dissociation is tighter and the N is full-cohort.
- Note that the full-range orthogonality result suffered from deep-position
  missing data (25 / 46 participants with complete features). Steep-phase
  restricts to where every participant contributes.
- The "universal decline" (K10 ρ = −1.000) + "no behavioral signature"
  (this doc) → load-trajectory measurement is not a proxy for any
  existing behavioral segmentation. Framework compilation is a new
  axis of variation, operating orthogonally to exhaustiveness.

## Reconciliation with original memory

Original memory reported full-range AUC = 0.43 (6 features); re-computed
AUC = 0.375 (5 features, no "trial variance"). Direction matches (below
chance under the imbalanced classification). Memory's χ² = 0.52 p = 0.77
used 3×2 tercile × trajectory-category; re-computed here as 2×3 with
median-split satopt, yielding χ² = 3.75 p = 0.153 full range (n/a steep).
Substantive conclusion unchanged in both recodings.

## Filing

Not a null finding per se (it's a *positive* orthogonality result, which
is what the dissociation claim needs). Filed in `null-findings/` to keep
the robustness checks discoverable alongside the plateau concentration
audit from the same day.
