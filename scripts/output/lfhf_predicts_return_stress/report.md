# LF/HF first-pass → predicts regressive return — stress test

_Generated 2026-05-03 by `scripts/lfhf_predicts_return_stress.py`._

## Headline

Paper claim (`adserp.tex` L174): participant-Wilcoxon **p = 0.0055**, 63% direction, CI [+0.94, +3.85], N=6,112 / 46 participants.

| Angle | Absolute | Organic (bbox) | Organic-hybrid |
|---|---|---|---|
| Angle | absolute | organic | organic_hybrid |
|---|---|---|---|
| records / participants | 6,112 / 46 | 4,450 / 46 | 4,450 / 46 |
| A1 obs MW p (one-sided greater) | 4.24e-04 | 1.53e-01 | 6.55e-03 |
| A1 Cohen's d | +0.025 | -0.020 | +0.020 |
| A1 Cliff's δ | +0.050 | +0.018 | +0.052 |
| A2 obs AUC [95% CI] | 0.525 [0.511, 0.539] | 0.509 [0.491, 0.526] | 0.526 [0.506, 0.546] |
| A3 ppt mean-Δ | +1.701 | -1.352 | +0.215 |
| A3 Wilcoxon p (two-sided) | 0.5733 | 0.6808 | 0.1993 |
| A3 % participants Δ > 0 | 54% | 50% | 65% |
| A4 ppt median-of-medians Δ | +1.616 | -0.667 | +1.580 |
| A4 Wilcoxon p (two-sided) | 0.0173 | 0.7210 | 0.2192 |
| A6 ppt AUC mean | 0.526 | 0.495 | 0.509 |
| A6 % participants AUC > 0.5 | 65% | 46% | 57% |
| A6 sign-test p (one-sided) | 0.0270 | 0.7693 | 0.2307 |
| A9 ppt-cluster 95% CI on mean Δ | [-1.72, +5.68] | [-4.94, +2.10] | [-4.09, +3.99] |
| A9 trial-cluster 95% CI on mean Δ | [-1.57, +4.31] | [-4.74, +2.39] | [-3.65, +5.65] |
| A12a ≥3-pos trials, MW p | 4.73e-04 | 2.71e-01 | 2.06e-02 |
| A12b log-transform, MW p | 4.24e-04 | 1.53e-01 | 6.55e-03 |
| A12c trimmed (2.5/97.5), MW p | 3.10e-04 | 2.14e-01 | 5.21e-03 |

## A8 — rank stratified (one-sided greater)

| Attribution | P0–P3 N / p / d | P4–P10 N / p / d |
|---|---|---|
| absolute | 4,229 / 8.95e-02 / -0.023 | 1,870 / 9.45e-01 / -0.041 |
| organic | 2,999 / 6.84e-01 / -0.075 | 1,429 / 8.16e-01 / -0.025 |
| organic_hybrid | 2,999 / 2.85e-01 / -0.055 | 1,429 / 1.50e-01 / +0.052 |

## A11 — per-rank Δ (median(returned) − median(not), absolute attribution)

| Rank | n_returned | n_not | Δ median | d | p (two-sided) |
|---|---|---|---|---|---|
| 0 | 854 | 182 | +0.67 | -0.131 | 7.001e-01 |
| 1 | 856 | 276 | -1.42 | -0.065 | 8.337e-01 |
| 2 | 677 | 497 | -1.31 | -0.042 | 6.759e-01 |
| 3 | 450 | 437 | -0.86 | -0.100 | 2.143e-01 |
| 4 | 261 | 340 | -0.96 | -0.098 | 4.826e-01 |
| 5 | 184 | 253 | -5.99 | -0.094 | 3.858e-02 |
| 6 | 102 | 214 | -2.14 | -0.193 | 1.447e-01 |
| 7 | 69 | 167 | -1.68 | +0.003 | 7.468e-01 |
| 8 | 13 | 140 | +3.17 | +0.325 | 8.933e-01 |
| 9 | 6 | 84 | -0.75 | -0.323 | 8.191e-01 |

## A10 — RIPA2 same test (sanity check on the dissociation)

- **absolute**: n=6,112, p_two_sided=5.87e-01, d=-0.028, medians wr=0.000413 vs nr=0.000415
- **organic**: n=4,450, p_two_sided=1.06e-03, d=-0.012, medians wr=0.000409 vs nr=0.00042
- **organic_hybrid**: n=4,450, p_two_sided=1.62e-01, d=+0.019, medians wr=0.000416 vs nr=0.0003935

## Limitations

- Mixed-effects (Angle 5) skipped — `statsmodels` not in venv. Variance partition reported via obs-vs-participant p-value gap and per-participant AUC distribution.
- Angle 13/14 (within-item paired first-visit vs return-visit LF/HF) requires Phase 2 — return-visit LF/HF must be computed via pupil-lfhf gated to revisit fixations.
- LHIPA comparator skipped — trial-level only, can't do per-(trial, position) test.