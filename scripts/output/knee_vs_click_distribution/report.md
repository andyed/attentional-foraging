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
| mean_knee × mean_click_pos | 45 | +0.459 | 1.504e-03 | +0.458 | 1.562e-03 |
| mean_knee × click_at_P0_frac | 45 | -0.424 | 3.704e-03 | -0.442 | 2.392e-03 |
| mean_knee × click_at_P0_or_P1_frac | 45 | -0.366 | 1.339e-02 | -0.342 | 2.134e-02 |
| mean_knee × click_at_P3_or_deeper_frac | 45 | +0.331 | 2.627e-02 | +0.326 | 2.877e-02 |
| mean_knee × click_entropy_bits | 45 | +0.437 | 2.702e-03 | +0.459 | 1.529e-03 |
| mean_knee × regression_rate | 45 | +0.003 | 9.841e-01 | -0.005 | 9.745e-01 |
| regression_rate × click_entropy_bits | 45 | +0.077 | 6.138e-01 | +0.114 | 4.553e-01 |
| regression_rate × click_at_P0_frac | 45 | +0.121 | 4.267e-01 | +0.133 | 3.828e-01 |
| regression_rate × mean_click_pos | 45 | +0.038 | 8.043e-01 | +0.066 | 6.653e-01 |