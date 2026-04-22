# LF/HF × content features — clean null (ETTAC gap audit)

**Date:** 2026-04-19
**Script:** `scripts/lfhf_content_crossover.py`
**Output:** `scripts/output/lfhf_content_crossover/{summary,per_position}.json`
**Regime:** `[LAB]` — AdSERP eye + pupil + per-result sentence embeddings

## Why this was run

Project gap audit noticed that the content/embedding work (NB25
lexical-novelty-per-fixation, NB27 lexical-novelty-per-viewport, NB29
content-residualized bands) had *never* been crossed with the
Butterworth LF/HF cognitive-load signal (NB14). All three content
notebooks targeted click prediction and viewport dwell; NB14 contains
zero references to `novelty`, `embedding`, `query_cosine`, or
`centroid_novelty`. This script fills the gap.

**Hypotheses.**
- **H1 (semantic load).** LF/HF correlates with per-result content
  features beyond the position-bound K10/K3 gradient. A positive
  extends cognitive-load measurement from *structural position* to
  *item-level semantics*.
- **H0 (position-bound).** LF/HF is position-bound (framework
  compilation sharpens by rank), and per-result content adds nothing.

## Design

- Inner-join **6,056 records** on `(trial_id, position ∈ P0–P9)`
  between NB14's `butterworth-lfhf-by-position.json` and the NB29
  content-feature computation (2,413 trials, 46 participants).
- Content features: `token_count`, `char_count`, `ttr`,
  `query_cosine`, `centroid_novelty` — identical definitions to
  `_build_nb29_content_residualization.py`.
- Three tests per feature:
  1. **Pooled Spearman(LF/HF, feature)** across all records
  2. **Partial Spearman controlling for position** (rank-residualized)
  3. **Fixed-effects OLS**: standardized β on feature, with position
     dummies + participant dummies (46 + 9 = 55 additional
     regressors); a stand-in for a random-intercept mixed model without
     the `statsmodels` dependency.
- Bonferroni α = 0.05 / 15 = **0.0033**.

## Results

| Feature | Pooled ρ (p) | Partial ρ \| pos (p) | FE β (p) |
|---|---:|---:|---:|
| token_count       | −0.028 (0.029) | −0.002 (0.87) | −0.0003 (0.98) |
| char_count        | −0.018 (0.155) | −0.013 (0.30) | −0.022 (0.065) |
| ttr               | +0.017 (0.18) | −0.005 (0.73) | +0.003 (0.79) |
| query_cosine      | +0.015 (0.24) | −0.011 (0.41) | +0.000 (0.995) |
| centroid_novelty  | −0.020 (0.12) | +0.012 (0.37) | +0.029 (0.018) |

**No feature × test survives Bonferroni α = 0.0033.**

The largest unadjusted p-value is FE β on `centroid_novelty`
(p = 0.018), which does not survive correction for 15 tests. Per-position
Spearman |ρ| rarely exceeds 0.10 and the signs are inconsistent across
positions (e.g. `token_count` is P8 ρ = +0.149 and P7 ρ = −0.061 in the
same column) — exactly the fingerprint of noise around zero.

## Positive control

The position gradient is intact on the **same joined subset**:

    Position × median LF/HF  ρ = −0.927, p = 1.1 × 10⁻⁴ (N = 6,062, 10 positions)

Medians by position: 29.64 → 22.17 → 18.96 → 18.30 → 17.23 → 16.77 →
14.41 → 13.82 → 13.31 → 15.58. This matches NB14:K3 exactly (ρ = −0.927
post-audit), ruling out that the content null is a join or filtering
artifact.

## Why the null matters

LF/HF is **position-bound, not item-semantics-bound**. Framework
compilation sharpens by rank, not by novelty / query-similarity /
length / lexical diversity. This is directly consistent with:

- **NB29 content-residualized bands null** (2026-04-19) — residualizing
  viewport-band dwell against per-result content features does not
  improve deferred-vs-evaluated discrimination.
- **NB25 / NB27 novelty-baseline-residual-redundancy null** (2026-04-15)
  — novelty residuals are empirically indistinguishable from raw dwell
  because the embedding-centroid baseline explains ≤ 2.5 % of dwell
  variance.
- **LF/HF × satopt orthogonality** (memory:
  `project_lfhf_orthogonality.md`, P0–P3 re-check 2026-04-19) — load
  trajectory is independent of the regression-rate / satisficer-optimizer
  axis.

Three independent nulls at the content side of the house, all pointing
the same direction: AdSERP LF/HF indexes *where you are on the
evaluation surface*, not *what you are looking at* or *how you're
strategizing*. That is exactly what the ETTAC framing asks of a
real-time cognitive-load measure.

## Implication for ETTAC

This null is **good news for the brief's K10 + K9 framing**. It rules
out the most obvious alternative interpretation — that the steep-phase
gradient reflects top-ranked results being richer / more novel /
better-matched. If that were the mechanism, we'd see residual LF/HF
variance explained by `centroid_novelty` or `query_cosine` within a
position. We don't.

**Brief language to consider adding:** "Per-position LF/HF does not
correlate with token count, character count, TTR, query cosine, or
centroid novelty (Bonferroni α = 0.003, N = 6,056 records, 15 tests).
The load gradient indexes rank position, not item-level content
complexity."

## Extended battery (2026-04-19 evening)

After the initial 5-feature crossover landed null, three follow-up analyses were run to rule out that the features themselves were ineffective, or that the signal lived in a more specific content dimension:

- **Feature-effectiveness positive control** (`scripts/content_feature_effectiveness.py`). All five features (minus `char_count`, which is inert) move at least one behavioral outcome (click / total_dwell_ms / n_fixations) at α = 0.001 with |ρ| ≤ 0.07. Features are weak but real — not the reason LF/HF is null.

- **Content analysis #1 — price/numeral saliency** (`scripts/lfhf_price_numeral_saliency.py`). Price presence, numeral count, percent-off tagging, numeral density. `has_price` shows a suspicious pooled ρ = +0.028 (p = 0.029) and MW median 22.72 vs 19.81 (p = 0.029), but per-position breakdown is ≈ 0 everywhere — pooled effect is the ads-at-top-carry-prices-and-top-has-high-LF/HF position confound. No test survives Bonferroni α = 0.0025. Positive control on behavior is strong (numeral_density × n_fix p = 10⁻⁶).

- **Content analysis #4 — Pirolli scent-sharpening** (`scripts/lfhf_pirolli_scent.py`). Within-trial cosine from each newly-visited result to the centroid of previously-visited results (4,909 scent-computable rows). Pooled ρ = −0.020 (p = 0.16). **Partial ρ given visit ordinal is exactly 0.000 (p = 0.999). Partial ρ given ordinal + position is −0.003 (p = 0.86).** Per-visit-ordinal and per-position breakdowns all flat. Scent-sharpening does not predict LF/HF. Caveat: scent cosines on commercial SERPs cluster tightly (mean 0.850, p05 / p95 = 0.741 / 0.938), so dynamic range is narrow — but zero-valued partial correlation rules out even subtle signal.

- **Content analysis #2 — title vs snippet split** (`scripts/lfhf_title_snippet_split.py`). All non-embedding features computed separately on title text and snippet text. Only `snippet__ttr × LF/HF` survived Bonferroni α = 0.0045 at pooled ρ = +0.053 (p = 3.4 × 10⁻⁵). Partial correlation on position collapses this to ρ = +0.010 (p = 0.44) — position confound again. Snippet TTR has ρ = −0.253 (p = 10⁻⁸⁹) with position itself, i.e. top-rank snippets are lexically richer. Per-position snippet_ttr × LF/HF effects are all non-significant (P0 closest at p = 0.037 uncorrected).

**Conclusion across all four content tests:** every apparent positive on LF/HF unwinds to a position confound once partialled on rank. The position-bound framework-compilation reading survives three independent attempts to find item-level content modulation.

## Filing

Clean null. Filed alongside the two other 2026-04-19 ETTAC audits.
