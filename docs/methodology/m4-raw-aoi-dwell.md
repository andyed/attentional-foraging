# Raw cursor AOI dwell versus approach-retreat features

**Stable ID:** M:m4-raw-aoi-dwell
**Status:** current as of 2026-09-28; canonical implementation: `scripts/m4_raw_aoi_dwell.py`

Computed 2026-09-28. **The seven M4 approach features provide substantially
better click prediction than total cursor time inside the result rectangle.**
The comparison uses the same 34,328 typed AOI rows, 2,608 trials/clicks,
47 participants and 500 ms pre-press cutoff as the canonical M4 evaluation.
It requires no gaze data.

## Main comparison

The dependent measure is whether each result received the final click.

| Predictor | Pooled click AUC | MRR@10 | Top-1 clicked-result accuracy |
| --- | ---: | ---: | ---: |
| Position alone, logistic regression | 0.791791 | 0.447052 | 19.75% |
| Raw AOI dwell as a direct score, no fitted model | 0.849458 | 0.639355 | 43.44% |
| Raw AOI dwell, logistic regression | 0.839530 | 0.639355 | 43.44% |
| Raw AOI dwell + position, logistic regression | 0.839052 | 0.513712 | 28.34% |
| log(1 + AOI dwell), logistic regression | 0.838180 | 0.639355 | 43.44% |
| log(1 + AOI dwell) + position, logistic regression | 0.871057 | 0.579811 | 34.70% |
| M4: seven cursor approach features | **0.934750** | **0.777330** | **63.38%** |
| M3: M4 + position | 0.934750 | 0.774823 | 62.92% |

All fitted models use the unchanged canonical evaluator: leave one participant
out, train-fold StandardScaler, balanced LogisticRegression(C=1,max_iter=5000).
The direct-score baseline simply ranks by observed dwell milliseconds; it does
not need training or calibration. It uses the same rows and participant groups.

Direct dwell, raw-dwell logistic regression and log-dwell logistic regression
have identical within-participant AUC and within-trial ranking scores. Their
pooled AUCs differ because the fitted models change probability scales between
held-out folds. Reporting the unfitted baseline avoids making the case for M4
depend on that scaling difference. The log transform was specified before
results were inspected, as a sensitivity to the skewed duration distribution.

## Paired evidence and position

These intervals concern mean **participant AUC differences**, not differences
between pooled AUCs in the table. There are 47 participant pairs; bootstrap
intervals use 10,000 resamples with seed 20260904. Training folds overlap, so
intervals describe participant variability conditional on this corpus.

| Comparison | Mean participant AUC difference | 95% bootstrap interval |
| --- | ---: | ---: |
| M4 − raw AOI dwell | +0.071170 | [+0.059287, +0.083550] |
| M4 − log AOI dwell + position | +0.057602 | [+0.048070, +0.067223] |
| Adding position to log AOI dwell | +0.013568 | [+0.006372, +0.020968] |
| Adding position to M4 | −0.000019 | [−0.000434, +0.000409] |

The M4 versus raw-dwell paired result is identical for direct scores and either
one-feature logistic model. In the prespecified family of four primary fitted
model contrasts, M4 versus raw dwell has Holm-adjusted Wilcoxon p=2.98e-13;
M3 versus M4 has adjusted p=0.99582. The log-dwell comparisons are sensitivity
analyses, not members of that adjusted family.

Position's contribution to a dwell baseline depends on its functional form:
adding position to raw linear dwell reduces mean participant AUC by 0.022788,
while adding it to log dwell improves AUC as shown above. Thus we should not
claim that raw dwell generally absorbs position. M4 outperforms both variants
and shows essentially no additional AUC benefit from explicit position.

The practical finding is: **the library's approach features add
predictive information beyond a simple cursor dwell timer, and retain their
click-prediction performance when rank position is omitted.** This is an
offline result using the library's actual feature tracker; it is not proof of
position-unbiased relevance or validation of every browser deployment lifecycle.

## What raw AOI dwell means here

For each result, sum the time the cursor lies inside its actual typed XY
rectangle. There is no expansion margin, 100 px proximity zone, minimum dwell
duration, episode merge rule, or gaze assignment. Multiple visits contribute
to the same total. AOI boxes are converted from screenshot to document CSS
coordinates with the verified trial geometry.

The estimate holds each native mousemove's viewport cursor coordinates until
the next observation. Scroll events update document-space Y beneath that
stationary cursor. The primary window begins at the first retained mousemove
and ends at the last retained mousemove, matching M4's observed temporal extent.
Every input timestamp is strictly before final mousedown minus 500 ms.

This is reconstructed cursor residence, not a directly logged DOM hover timer.
Cursor absence outside the browser cannot be identified from these records.
It is distinct from gaze fixation dwell, viewport residence, and M4's
`dwell_in_proximity_ms` (time near the result's vertical center).

There are 12,887 AOI rows with positive dwell and 21,441 with zero dwell. The
median across all rows is zero; the 75th percentile is 420.25 ms. Zero dwell
does not imply the result was unseen by the participant.

## Sensitivities and complementary information

| Predictor | Pooled click AUC |
| --- | ---: |
| Proximity dwell alone, logistic regression | 0.852988 |
| Raw AOI dwell held through the cutoff | 0.854516 |
| Raw AOI dwell without scroll updates between mousemove observations | 0.854272 |
| M4 + raw AOI dwell | 0.935992 |
| M4 with raw AOI dwell replacing proximity dwell | 0.935126 |

The two timing/scroll sensitivities remain below M4: paired participant AUC
gains for M4 are +0.056961 [0.045632, 0.068890] and +0.060571
[0.049847, 0.071755], respectively.

Raw AOI dwell also supplies a small complementary signal when added to M4:
mean participant AUC +0.001942, CI [+0.001187, +0.002732]. Replacing proximity
dwell with AOI dwell yields +0.001178, CI [−0.000167, +0.002625], which does
not establish an improvement. These exploratory comparisons do not justify
changing the library's model or defaults without further validation.

The known backwards scroll timestamp in `p043-b1-t5` is retained. Joint mouse/
scroll integration uses stable timestamp ordering; the no-scroll sensitivity
avoids dependence on this alignment. No trial or AOI was dropped.

## Reproduction

The saved M4 baseline reproduced exactly. Canonical features, raw mouse and
metadata, geometry, and typed AOI maps were hash-checked. Five boundary tests
cover strict containment without a minimum dwell, repeated visits, scroll
under a stationary cursor, initial scroll, exact cutoff exclusion, observation
boundaries and duplicate timestamps. The reproduction-gate audit passes.

- [Producer](../../scripts/m4_raw_aoi_dwell.py)
- [Boundary tests](../../scripts/test_m4_raw_aoi_dwell.py)
- [Metrics, paired contrasts and provenance](../../scripts/output/m4_raw_aoi_dwell/summary.json)
- [Derived row features](../../scripts/output/m4_raw_aoi_dwell/features.json)
- [Gate audit](../../scripts/output/m4_raw_aoi_dwell/repro-audit.json)

```sh
.venv/bin/python -m unittest discover -s scripts -p test_m4_raw_aoi_dwell.py -v
.venv/bin/python scripts/m4_raw_aoi_dwell.py
```

The producer verifies and reuses the geometry manifest from the preceding
return/scroll ablation. All new outputs are separate local research artifacts;
canonical caches and the library itself are unchanged.
