# LF/HF argmax → click prediction (organic_hybrid)

_Generated 2026-05-03 by `scripts/lfhf_argmax_predicts_click.py`._

## Question

Given a SERP consideration set of size N (positions the user visited),
does the position with the highest first-pass LF/HF coincide with the
click position more often than chance (1/N)?

## Headline

**n trials eligible**: 2,449 (skipped: 325)

- **hit rate** (argmax = click): **0.319**
- **mean chance baseline** (1/N): **0.534**
- **lift**: +-21.5 pp absolute, 0.60× chance
- *p* (binomial, greater than chance): **1.00e+00**

## By consideration-set size N

| N visited | n trials | hit rate | chance | lift (pp) | lift (×) | p |
|---|---|---|---|---|---|---|
| 1 | 657 | 0.478 | 1.000 | +-52.2 | 0.48× | 1.00e+00 |
| 2 | 716 | 0.323 | 0.500 | +-17.7 | 0.65× | 1.00e+00 |
| 3 | 511 | 0.258 | 0.333 | +-7.5 | 0.77× | 1.00e+00 |
| 4 | 301 | 0.213 | 0.250 | +-3.7 | 0.85× | 9.43e-01 |
| 5 | 151 | 0.146 | 0.200 | +-5.4 | 0.73× | 9.66e-01 |
| 6 | 66 | 0.182 | 0.167 | +1.5 | 1.09× | 4.20e-01 |
| 7 | 33 | 0.121 | 0.143 | +-2.2 | 0.85× | 7.13e-01 |
| 8 | 6 | 0.333 | 0.125 | +20.8 | 2.67× | 1.67e-01 |
| 9 | 5 | 0.200 | 0.111 | +8.9 | 1.80× | 4.45e-01 |