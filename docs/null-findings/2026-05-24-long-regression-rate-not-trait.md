# Long-regression-rate is not an individual-difference trait

**Date:** 2026-05-24
**Type:** Null on a candidate trait. Population-level structure exists; per-participant signature does not.
**Status:** Pre-noted before any task-model or paper consumption. Affects the framing of the dd_top Markov substrate as a per-participant transition-matrix object.

## TL;DR

The dd_top-topped substrate ([`scripts/output/dd_top_markov/`](../../scripts/output/dd_top_markov/)) shows a clean **population-level** asymmetry: short organic regressions (1–2 positions) are forward-biased (F:R ≈ 1.5:1), but long regressions (≥4 positions) are regression-dominant (F:R = 0.27–0.56). One natural follow-up was to test whether the *mix* — `long_regression_rate` = (n_regressions of size ≥4) / (n_regressions total) — is a stable per-participant trait, plausibly distinct from total regression rate. **It is not.** Split-half r = 0.257 (Spearman-Brown 0.408), below the trait floor.

The asymmetric long-regression tail is real but lives at population grain, not individual grain. Participants don't differ in *which kind* of regression they prefer; they differ in *how many* regressions they make.

## What was tested

Across 47 participants × 1,581 dd_top-topped trials (median 34 trials/participant), per-participant aggregates:

- `regression_per_trial` — fixation-level organic→organic backward transitions per trial
- `long_regression_per_trial` — same restricted to |delta| ≥ 4
- **`long_regression_rate`** — long_regressions / total_regressions (the candidate trait)
- `any_long_reg_trial_rate` — fraction of trials with at least one long regression
- `mean_regression_size` — mean |delta| across all regressions

Split-half reliability (random within-participant trial split, Spearman-Brown corrected to full length):

| Metric | r split-half | Spearman-Brown |
|---|---:|---:|
| `regression_per_trial` | 0.811 | **0.896** |
| `long_regression_per_trial` | 0.575 | 0.730 |
| `any_long_reg_trial_rate` | 0.579 | 0.733 |
| `mean_regression_size` | 0.418 | 0.589 |
| **`long_regression_rate`** | **0.257** | **0.408** |

Only `regression_per_trial` clears the strong-trait threshold (SB > 0.85). `long_regression_rate` specifically — the candidate that would identify "commit-jumpers" as a distinct sub-population — is unreliable. Two random halves of the same participant's trials disagree on whether they prefer long vs short regressions.

## What this means structurally

The population-level forward/regression asymmetry at size ≥4 (F:R = 0.27–0.56, n = 5,738 regressions) is not driven by a specialized sub-population of long-jumpers. Every participant's regression-size distribution is broadly the same shape; some just generate more of them.

This is the regression-size analogue of the existing chattiness finding: **rate is the per-participant signal; distribution shape is task-structural.** Cursor chattiness shipped as a stable trait (NB11.5, r > 0.96). Long-vs-short regression mix does not.

## What this means for the dd_top Markov substrate

Per-participant transition matrices on the dd_top-topped substrate remain useful, but:

- Clustering participants by **the long-regression *cells* of the transition matrix** (organic_5 → organic_1, organic_6 → organic_2, etc.) is the wrong cut — there is no clean cluster structure at that resolution.
- Clustering by **total regression activity in the matrix** is the right cut, and it reproduces the existing `regression_rate` axis (Spearman ρ = +0.693 between `regression_per_trial` here and the prior CSV's `regression_rate`, p < 10⁻⁷).
- Clustering by **the full row-distribution similarity** (transition-matrix KL divergence across participants) is the only path that could surface novel sub-populations beyond the existing axes. That remains untested.

## Side observation: cross-axis dissociation

The fixation-level organic regression rate (`regression_per_trial`, the only stable trait among the candidates here) is **fully independent** of the cell-promiscuity trait ([`dd-top-cell-promiscuity.md`](../dd-top-cell-promiscuity.md)):

| Pair | Spearman ρ | p | n |
|---|---:|---:|---:|
| `regression_per_trial` × `cell_promiscuity_rate` | +0.017 | 0.91 | 47 |
| `regression_per_trial` × `mean_touched_fraction` | +0.049 | 0.75 | 47 |
| `regression_per_trial` × `any_cell_engagement_rate` | +0.025 | 0.87 | 47 |

Organic regression (within the organic stream) and within-ad-carousel cell sampling are **different deliberation behaviors**. Both are stable per-participant traits (r > 0.8). Neither predicts the other. This extends the existing four-axis dissociation:

1. Sat-opt (regression rate — corroborated here at fixation grain)
2. Cognitive load (LHIPA — see caveat below)
3. Ad-utility prior (between-surface gaze allocation)
4. Cell promiscuity (within-ad-surface sampling)

…with the regression-rate axis now validated at fixation grain (not only scroll grain), and orthogonal to cell promiscuity.

## Caveat that the LHIPA correlation does *not* break

`regression_per_trial` correlates with `mean_lhipa` at ρ = −0.695 (p < 10⁻⁷) in this stratum. This matches the strength of the previously-noted ρ = −0.593 in the full corpus, which the **2026-04-16 satopt-LHIPA duration confound** ([`2026-04-16-satopt-lhipa-duration-confound.md`](2026-04-16-satopt-lhipa-duration-confound.md)) reframed: the raw correlation reproduces but collapses to ρ = +0.135 once trial duration is partialed out. The mechanism is duration → mean LHIPA (longer trials accumulate more low-LHIPA samples), not regression → load. The fixation-grain replication here inherits the same confound and the same reframe. Recorded for completeness; not a new finding.

## Files

- `scripts/dd_top_regression_traits.py` — analysis driver
- `scripts/output/dd_top_regression_traits/{summary.json, per_participant.csv}` — n=47 × 8 metrics

## Reading order

1. [`docs/dd-top-cell-promiscuity.md`](../dd-top-cell-promiscuity.md) — the *positive* trait finding that motivated this analysis
2. This doc — the *negative* trait finding on the regression-size mix
3. [`docs/null-findings/2026-04-16-satopt-lhipa-duration-confound.md`](2026-04-16-satopt-lhipa-duration-confound.md) — the LHIPA-confound reframe that this doc inherits
