# Four-grade cursor AOI dwell control for approach-retreat LTR

**Stable ID:** M:ltr-four-grade-cursor-dwell
**Status:** current as of 2026-09-28; canonical implementation: `scripts/ltr_four_grade_cursor_dwell.py`

Computed 2026-09-28. **With the current M4 ranker inputs fixed, four grades
derived from cursor AOI dwell perform similarly to the current approach-retreat
four-grade scheme. There is no demonstrated ranking advantage for the latter.
The richer M4 input features, however, substantially outperform raw AOI dwell
as the ranker's sole input under either grading scheme.**

This is the requested four-level comparison (3/2/1/0), not the three-grade
collapse. Input features and training grades are separate experimental factors.

## Primary comparison: change grades, retain our features

Both rows use the same seven M4 input features and the same LambdaMART ranker.

| Four-grade training supervision | Click NDCG@10 | Click MRR@10 |
| --- | ---: | ---: |
| Current nested cursor-predicted approach-retreat grades | 0.831862 | 0.779158 |
| Cursor-in-AOI-time grades | 0.833075 | 0.780349 |

The difference, approach-retreat minus dwell grades, is **−0.001534 mean
participant NDCG@10**, 95% bootstrap CI **[−0.009618, +0.006364]**. Mean
participant MRR@10 difference is −0.001631, CI [−0.011975, +0.008642].
The small numerical lead for dwell grades is not a demonstrated advantage;
nor does the interval establish equivalence. This test does not show that the
more elaborate approach-retreat grading improves ranking over this dwell-based
control.

For context, the reproduced binary-click LambdaMART baseline on the same M4
inputs is NDCG@10 0.826504, MRR@10 0.774191. Both four-grade methods are
numerically above it. The study should not promote these small differences
to an established graded-supervision gain: the primary family of adjusted
comparisons does not establish either improvement over binary clicks.

## Exactly what the four levels mean

| Grade | Current approach-retreat supervision | Cursor AOI dwell supervision | Training gain |
| ---: | --- | --- | ---: |
| 3 | Clicked | Clicked, regardless of dwell | 7 |
| 2 | Approached and predicted deferred | Nonclicked positive dwell above the training median | 3 |
| 1 | Approached and predicted nondeferred | Nonclicked positive dwell at or below the training median | 1 |
| 0 | Other retained nonclicked rows | Nonclicked zero dwell | 0 |

The gain schedule is the unchanged LightGBM default: grade 0/1/2/3 maps to
gain 0/1/3/7. Grade numbers themselves are not the gain values.

The dwell threshold is learned independently in each outer training fold,
using only positive-dwell, nonclicked, training-eligible rows. It ranges from
**905.0 to 944.5 ms** across the 47 folds. Held-out rows and excluded training
rows cannot influence that threshold. Median ties receive grade 1. This
median split was specified before inspecting the four-grade ranker results;
it was not selected for performance.

The approach-retreat grades are the existing **nested cursor-predicted**
grades. The labeler uses the full M4 features and LAB gaze-regression training
targets; inner participant LOSO is contained within each outer training fold.
These are not the library's directly observed cursor-episode labels, and are
not bins of predicted click probability. All 47 training-label hashes match
the saved four-grade experiment exactly.

Grade frequencies differ despite the identical number of levels and gain
mapping. Across outer-fold training assignments, the fractions at grades
0/1/2/3 are approximately 9.84%/29.28%/42.12%/18.75% for approach-retreat and
18.12%/31.59%/31.53%/18.75% for dwell. This is not a class-frequency-matched test.

## Crossed control: change features as well

| Ranker input features | Training grades | NDCG@10 | MRR@10 |
| --- | --- | ---: | ---: |
| M4 | Approach-retreat four grades | 0.831862 | 0.779158 |
| Raw AOI dwell only | Approach-retreat four grades | 0.707832 | 0.630469 |
| M4 | Dwell four grades | 0.833075 | 0.780349 |
| Raw AOI dwell only | Dwell four grades | 0.706139 | 0.627208 |

With approach-retreat grades fixed, using M4 instead of a single raw dwell
feature improves mean participant NDCG@10 by **+0.122728**, CI
[+0.101261, +0.144254]. With dwell grades fixed, the improvement is
**+0.126035**, CI [+0.103971, +0.148991]. Both survive Holm adjustment over
the ten NDCG comparisons (adjusted p < 3e-11).

The evidence therefore supports the value of the **feature representation**
beyond a dwell timer. It does not establish additional ranking value for the
current four-grade interpretation over the tested dwell-based grading.
The dwell-only feature arms retain the canonical training selection rule,
which itself uses approach distance and position; they are not completely
independent dwell-only data pipelines.

## Position in the same LTR configuration

| Ranker inputs | Training grades | NDCG@10 | MRR@10 |
| --- | --- | ---: | ---: |
| M4 + position | Approach-retreat four grades | 0.836297 | 0.784791 |
| M4 + position | Dwell four grades | 0.822305 | 0.770576 |
| Raw AOI dwell + position | Approach-retreat four grades | 0.725201 | 0.641756 |
| Raw AOI dwell + position | Dwell four grades | 0.715357 | 0.631564 |

For the current approach-retreat four-grade model, adding position produces a
small numerical increase: mean participant NDCG@10 +0.004841,
CI [−0.002296, +0.012357], Holm-adjusted p=0.4773. Thus there is **no clear
incremental position benefit**, but this LTR result is not the exact equality
previously found for logistic click AUC. It does not prove zero ranking cost
from removing position.

Under dwell grading, position decreases the M4 ranker's scores numerically;
under dwell-only input features, it increases them numerically. These effects
are label- and feature-dependent. The full paired results and multiplicity
adjustments are in the summary; they should not be collapsed into a universal
claim that position is either useful or redundant.

Even models without position as an input inherit the original position-based
training exclusion described below. None of these LTR arms is a wholly
position-free training pipeline.

## What stayed fixed

- **Ranker:** LightGBM 4.6.0 LGBMRanker, objective `lambdarank`, metric `ndcg`,
  `eval_at=[10]`, 200 estimators, learning rate 0.05, 31 leaves,
  minimum leaf data 20, one thread, all remaining parameters unchanged.
- **Rows and splits:** 34,328 result rows, 2,608 trials and 47 participants;
  outer leave-one-participant-out. The original 13,909 training-eligible rows
  are retained, with the same 20,419 NotApprBelow exclusions. Actual training
  folds additionally exclude the held-out participant. All 34,328 rows are
  scored when their participant is held out.
- **Training inclusion:** non-approached results below the final clicked
  position are excluded in every arm. This rule uses M4 minimum distance
  and final-click position and is held fixed to match the existing experiment.
- **Observation cutoff:** all cursor observations precede final mousedown by
  at least 500 ms, with strict timestamp exclusion at the boundary.
- **Dwell measurement:** the same reconstructed strict XY cursor-in-AOI dwell
  as the [raw-dwell analysis](m4-raw-aoi-dwell.md), without proximity margin
  or minimum-visit threshold; scroll-adjusted between native mousemoves,
  from the first through last retained mousemove. It is neither gaze dwell
  nor viewport residence.
- **Evaluation target:** observed held-out binary clicks for every arm, using
  the canonical per-trial NDCG@10 and MRR@10 implementation and its tie rules.
  Neither grading scheme is evaluated against itself.
- **Uncertainty:** participant means of per-trial scores, paired bootstrap
  with 10,000 resamples and seed 20260904. NDCG is primary and MRR secondary.
  Paired Wilcoxon p-values also receive Holm adjustment across ten contrasts
  separately for each metric. The primary grade-source contrast was specified
  before fitting. Other contrasts describe feature and position sensitivity.
  The overlapping outer training folds limit interpretation of these
  participant-bootstrap intervals to the present corpus.

This is offline post-interaction behavioral ranking. It does not validate a
pre-impression ranker, unbiased relevance labels, or continuous soft-label
training. The median-threshold dwell grades are one explicit control, not
an optimized benchmark over all possible dwell transformations.

## Verification and artifacts

Both the binary-click and current four-grade M4 rankers reproduce the saved
NDCG@10 and MRR@10 exactly. Five existing nested-label isolation tests pass;
three new dwell-grade tests cover click priority, median ties, held-out and
excluded-row isolation, and the no-positive-dwell case. The reproduction audit
passes with all four source pins current.

- [Producer](../../scripts/ltr_four_grade_cursor_dwell.py)
- [Dwell-grade boundary tests](../../scripts/test_ltr_four_grade_cursor_dwell.py)
- [Full results, fold grade counts and provenance](../../scripts/output/ltr_four_grade_cursor_dwell/summary.json)
- [Per-trial metric arrays](../../scripts/output/ltr_four_grade_cursor_dwell/per_trial_metrics.json)
- [Reproduction audit](../../scripts/output/ltr_four_grade_cursor_dwell/repro-audit.json)

```sh
.venv/bin/python -m unittest discover -s scripts -p test_ltr_four_grade_cursor_dwell.py -v
.venv/bin/python scripts/ltr_four_grade_cursor_dwell.py
```

The initial three-grade input-feature control is retained separately under
`scripts/output/ltr_raw_aoi_dwell_ablation`; it is not the primary comparison
reported here. Canonical experiment outputs, library defaults and paper text
were not modified.
