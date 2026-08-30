# Per-participant knee vs click distribution

_Generated 2026-05-03 by `scripts/knee_vs_click_distribution.py`._

## Hypothesis

Under the rank-value-prior framing:
- Satisficer prior (top-heavy): high P(value | top) → invest in top → DEEPER knee, higher concentration of clicks on top positions.
- Optimizer prior (flatter): wider sampling → SHALLOWER knee, flatter click distribution.

Predictions:
- mean_knee × mean_click_pos: positive (deeper knee → deeper clicks, since satisficer evaluates top carefully and may take what comes next)
- mean_knee × click_at_P0_frac: weak/negative (deeper knee = satisficer; satisficers don't always click P0 since they take first acceptable)
- mean_knee × click_entropy_bits: positive (deeper knee = satisficer = more concentrated commit decisions; lower entropy if clicks cluster)
- regression_rate × mean_knee: negative (already known: high regr-rate = optimizer = shallow knee)

## Cohort: 45 participants

## Cross-participant correlations

| Pair | n | Spearman ρ | p | Pearson r | p |
|---|---|---|---|---|---|
| mean_knee × mean_click_pos | 45 | +0.486 | 7.146e-04 | +0.476 | 9.366e-04 |
| mean_knee × click_at_P0_frac | 45 | -0.437 | 2.686e-03 | -0.437 | 2.693e-03 |
| mean_knee × click_at_P0_or_P1_frac | 45 | -0.357 | 1.599e-02 | -0.340 | 2.226e-02 |
| mean_knee × click_at_P3_or_deeper_frac | 45 | +0.361 | 1.493e-02 | +0.348 | 1.903e-02 |
| mean_knee × click_entropy_bits | 45 | +0.449 | 1.955e-03 | +0.468 | 1.190e-03 |
| mean_knee × regression_rate | 45 | +0.001 | 9.923e-01 | -0.005 | 9.735e-01 |
| regression_rate × click_entropy_bits | 45 | +0.066 | 6.665e-01 | +0.095 | 5.359e-01 |
| regression_rate × click_at_P0_frac | 45 | +0.113 | 4.598e-01 | +0.140 | 3.596e-01 |
| regression_rate × mean_click_pos | 45 | +0.041 | 7.896e-01 | +0.057 | 7.113e-01 |