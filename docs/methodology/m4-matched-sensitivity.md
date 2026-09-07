# M4 window and sampling comparisons on matched cohorts

**Executed September 7, 2026 — [LAB, AdSERP, typed].**

The September 6 sensitivity runs admitted different trials. This follow-up
refits the seven-feature cursor model on a whole-trial intersection within
each comparison family. Every condition has the same AOIs, element types,
click labels, and participant folds. No individual AOI is dropped to force
a match. The position-only model is refit on the same rows.

The feature cutoff is 500 ms before the final `mousedown`. Native features
retain the headline grid's stricter eligibility rule (two distinct cursor
timestamps before the 1,000 ms cutoff); sensitivity runs retain their
original 500 ms eligibility rule before the intersection. These estimates
are conditional on shared eligibility, not the full trial population.

[Aggregate and hashes](../../scripts/output/m4_cursor_matched_sensitivity/summary.json) ·
[Producer](../../scripts/m4_cursor_matched_sensitivity.py) ·
[Canonical workflow](../../scripts/CANONICAL.md#matched-window-and-sampling-comparisons-september-7)

## Protocol and provenance

The runner regenerates the six sensitivity feature sets through the
canonical producer and real JS `ResultFeatureTracker`, then requires exact
feature-hash agreement with the retained September 6 aggregates. The flavor
option was added between those runs and the latest producer; the original
and replay producer hashes are both retained. The native cache is checked
against its press-grid aggregate, and current source, substrate, exclusion,
and solver-environment checks must pass before and after the fits.

Only the time-window family reads gaze: the end of the fifth fixation
defines its boundary and affects eligibility. Predictors remain cursor-only.
The rate family uses greedy thinning of native mousemove timestamps.
Scaling and balanced logistic regression are fit within each held-out
participant fold. Seven features and solver settings are fixed in advance
of these comparisons; there is no feature selection on the test folds.

## Time windows

Shared population: **1,382 trials / 18,227 AOI rows / 46 participants**. Position-only pooled AUC: **0.7943**.

| Condition | Trials before matching | Trials removed by intersection | Matched M4-7 pooled AUC | Matched MRR@10 |
|---|---:|---:|---:|---:|
| native | 2,608 | 1,226 | 0.9318 | 0.7683 |
| pre5 | 1,399 | 17 | 0.7830 | 0.4454 |
| post5 | 2,629 | 1,247 | 0.9370 | 0.7786 |

| Comparison | Pooled AUC difference | Mean participant AUC difference | Participant bootstrap 95% CI | Wilcoxon p |
|---|---:|---:|---|---:|
| pre5 minus native | -0.1488 | -0.1522 | [-0.1685, -0.1349] | 5.684e-14 |
| post5 minus native | +0.0052 | +0.0044 | [+0.0022, +0.0067] | 0.000745 |
| post5 minus pre5 | +0.1540 | +0.1566 | [+0.1385, +0.1735] | 5.684e-14 |

## Sampling rates

Shared population: **2,544 trials / 33,518 AOI rows / 47 participants**. Position-only pooled AUC: **0.7895**.

| Condition | Trials before matching | Trials removed by intersection | Matched M4-7 pooled AUC | Matched MRR@10 |
|---|---:|---:|---:|---:|
| native | 2,608 | 64 | 0.9338 | 0.7760 |
| 30hz | 2,649 | 105 | 0.9338 | 0.7746 |
| 15hz | 2,648 | 104 | 0.9341 | 0.7773 |
| 5hz | 2,640 | 96 | 0.9332 | 0.7711 |
| 1hz | 2,551 | 7 | 0.9012 | 0.6863 |

| Comparison | Pooled AUC difference | Mean participant AUC difference | Participant bootstrap 95% CI | Wilcoxon p |
|---|---:|---:|---|---:|
| 30hz minus native | -0.000049 | -0.000012 | [-0.0009, +0.0009] | 0.8462 |
| 15hz minus native | +0.0003 | +0.0001 | [-0.0012, +0.0015] | 0.9041 |
| 5hz minus native | -0.0006 | -0.0012 | [-0.0033, +0.0011] | 0.2239 |
| 1hz minus native | -0.0327 | -0.0329 | [-0.0393, -0.0268] | 9.948e-14 |

## Interpretation limits

- Matching removes the differing trial/AOI populations as an explanation
  within each family. The two families still have different intersections.
- AUC and MRR measure discrimination/ranking against the observed click,
  not independent relevance or psychological deliberation.
- Pre/post windows differ in elapsed duration and number of cursor samples.
  The post-fifth-fixation window can retain terminal approach despite the
  pre-press buffer. Full terminal-approach excision remains an open control.
- Small observed rate differences do not establish equivalence or rate
  invariance. No equivalence margin was specified. A nominal thinning rate
  is also not a test of a browser's visibility/throttling lifecycle.
- Pooled AUC differences and means of participant AUC differences are
  separate estimands. The 10,000-resample bootstrap resamples held-out
  participant differences; it does not refit models in each resample.
  Wilcoxon tests are exploratory and unadjusted for multiple comparisons.

## Reproduce

```sh
.venv/bin/python -m unittest discover -s scripts -p 'test_m4_cursor*.py'
.venv/bin/python scripts/m4_cursor_matched_sensitivity.py
```

Per-record scratch caches are local only. The default runner removes its
temporary cache after completion; the aggregate contains counts and hashes,
not trial IDs, rows, or participant-level predictions.

The repository ignores `scripts/output/` by default. When deliberately committing
this cited result, promote only `scripts/output/m4_cursor_matched_sensitivity/summary.json`
with `git add -f`; do not add the scratch feature caches.

Aggregate SHA-256: `a76898e48d911fab01ec86884b8a0589ddfa539940b99996e2f5b36153958e88`.
Producer SHA-256: `7c1cadedb5682e0b4f3294f35c1becf9b01950b4eb222db6e615876b5625b0ee`.
