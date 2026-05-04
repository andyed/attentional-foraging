# LF/HF first-visit vs return-visit — paired within-item

_Generated 2026-05-03 by `scripts/lfhf_first_vs_return_paired.py`._

Tests Duchowski 2026 §2.2 archetype-switch hypothesis: return-visit LF/HF < first-visit LF/HF (if regressive pass = recall, polarity flips).

## Counts

| Attribution | total records | paired | no return visit | return < 1 s |
|---|---|---|---|---|
| absolute | 13,413 | **2,851** | 4,070 | 0 |
| organic | 12,471 | **1,689** | 3,273 | 0 |
| organic_hybrid | 16,745 | **2,646** | 3,681 | 0 |
| typed | 16,653 | **2,652** | 3,688 | 0 |

Return-visit window samples (paired records): p25 / median / p75 across all attributions.

## Headline — paired observation level

Δ = LF/HF (return) − LF/HF (first). Hypothesis: Δ < 0 (return is recall, polarity flips per Duchowski 2026 §2.2).

| Attribution | n paired | median Δ | mean Δ | % Δ < 0 | p (two-sided) | p (less than 0) |
|---|---|---|---|---|---|---|
| absolute | 2,851 | +4.062 | +9.752 | 44.7% | 8.07e-13 | 1.00e+00 |
| organic | 1,689 | +7.241 | +15.304 | 38.5% | 1.02e-22 | 1.00e+00 |
| organic_hybrid | 2,646 | +6.311 | +12.549 | 40.2% | 5.66e-23 | 1.00e+00 |
| typed | 2,652 | +6.443 | +12.641 | 40.1% | 2.45e-23 | 1.00e+00 |

## Participant-level paired Wilcoxon

| Attribution | participants | mean-of-means Δ | median-of-means Δ | % participants Δ < 0 | p (two-sided) | p (less than 0) |
|---|---|---|---|---|---|---|
| absolute | 46 | +7.235 | +7.229 | 34.8% | 4.12e-03 | 9.98e-01 |
| organic | 46 | +11.507 | +8.742 | 17.4% | 2.20e-04 | 1.00e+00 |
| organic_hybrid | 46 | +10.730 | +9.336 | 19.6% | 3.10e-04 | 1.00e+00 |
| typed | 46 | +10.898 | +9.461 | 19.6% | 3.10e-04 | 1.00e+00 |

## Per-rank paired Δ (absolute attribution)

| Rank | n paired | median Δ | mean Δ | % Δ < 0 | p (two-sided) | p (less than 0) |
|---|---|---|---|---|---|---|
| 0 | 759 | -0.170 | +3.513 | 50.1% | 7.294e-01 | 6.353e-01 |
| 1 | 846 | +3.781 | +10.054 | 44.8% | 3.618e-05 | 1.000e+00 |
| 2 | 577 | +5.893 | +11.294 | 41.4% | 1.171e-06 | 1.000e+00 |
| 3 | 299 | +4.532 | +17.685 | 41.5% | 2.597e-04 | 9.999e-01 |
| 4 | 174 | +7.775 | +15.501 | 38.5% | 4.360e-04 | 9.998e-01 |
| 5 | 102 | +6.552 | +16.458 | 41.2% | 5.430e-02 | 9.729e-01 |
| 6 | 60 | +3.791 | +7.258 | 43.3% | 7.851e-02 | 9.607e-01 |
| 7 | 24 | -0.636 | +6.914 | 50.0% | 7.683e-01 | 6.265e-01 |
| 8 | 10 | +5.483 | -15.234 | 40.0% | 9.219e-01 | 5.771e-01 |