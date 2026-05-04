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
| mean_knee × mean_click_pos | 45 | +0.471 | 1.105e-03 | +0.471 | 1.096e-03 |
| mean_knee × click_at_P0_frac | 45 | -0.408 | 5.454e-03 | -0.424 | 3.683e-03 |
| mean_knee × click_at_P0_or_P1_frac | 45 | -0.363 | 1.420e-02 | -0.347 | 1.964e-02 |
| mean_knee × click_at_P3_or_deeper_frac | 45 | +0.337 | 2.378e-02 | +0.335 | 2.433e-02 |
| mean_knee × click_entropy_bits | 45 | +0.465 | 1.274e-03 | +0.470 | 1.134e-03 |
| mean_knee × regression_rate | 45 | -0.021 | 8.912e-01 | -0.014 | 9.276e-01 |
| regression_rate × click_entropy_bits | 45 | +0.043 | 7.790e-01 | +0.085 | 5.769e-01 |
| regression_rate × click_at_P0_frac | 45 | +0.101 | 5.099e-01 | +0.136 | 3.725e-01 |
| regression_rate × mean_click_pos | 45 | +0.046 | 7.619e-01 | +0.063 | 6.786e-01 |