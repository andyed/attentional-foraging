# Return counts and scroll regressions beyond M4

**Stable ID:** M:m4-return-scroll-ablation
**Status:** current as of 2026-09-28; canonical implementation: `scripts/m4_return_scroll_ablation.py`

Computed 2026-09-28. **Cursor-return counts add a small improvement
to M4. The tested trial-wide scroll-regression count provides no clear
incremental benefit. Gaze returns add information in a separate gaze-dependent
model. These results do not support saying that dwell subsumes return counts.**

## Matched experiment

The dependent measure is **whether a typed main-axis result/AOI received the
trial's final click**. There are 34,328 result rows, 2,608 trials/clicks and 47
participants. Every model uses exactly the same rows and participant-held-out
splits. All added observations have timestamps strictly earlier than the final
mousedown minus 500 ms. No gaze or viewport requirement selects rows.

M4 means the canonical seven cursor features, excluding final distance and
retreat distance. Estimation is unchanged: train-fold StandardScaler followed
by balanced logistic regression, C=1, max_iter=5000, leave one participant out.
The source cache, raw mouse/metadata, typed AOI maps, geometry and click labels
were checked against the canonical run. M4's saved pooled AUC reproduced
exactly, with difference 0.0. M3 also reproduced to the required tolerance.

## Primary gaze-free results

| Model | Pooled click AUC | MRR@10 | Top-1 clicked-result accuracy |
| --- | ---: | ---: | ---: |
| M4 | 0.934750 | 0.777330 | 63.38% |
| M4 + cursor returns | 0.935924 | 0.785212 | 64.57% |
| M4 + scroll regressions | 0.934854 | 0.776223 | 63.15% |
| M4 + cursor returns + scroll regressions | 0.936439 | 0.783014 | 64.19% |

Uncertainty below concerns **paired participant AUC differences**, rather than
differences between the pooled AUCs above. Each participant contributes equally.

| Addition to M4 | Mean participant AUC change | 95% participant-bootstrap interval | Holm-adjusted p |
| --- | ---: | ---: | ---: |
| Cursor returns | +0.001844 | [+0.000816, +0.002976] | 0.00253 |
| Scroll regressions | −0.000048 | [−0.000472, +0.000316] | 0.51863 |
| Both | +0.001956 | [+0.000752, +0.003202] | 0.00549 |

The tests are two-sided paired Wilcoxon tests, adjusted over these three primary
contrasts. Intervals use 10,000 participant bootstrap resamples, seed 20260904.
Training folds overlap; these intervals describe participant variability
conditional on this corpus, rather than uncertainty from independently retraining
on new datasets. Remaining comparisons are exploratory.

The combined model has the largest pooled AUC of the primary models, but adding
scroll count to M4 + cursor returns has a participant AUC change of only
+0.000112, CI [−0.000469, +0.000656], unadjusted p=0.40962. Its ranking scores
are also lower than those of M4 + cursor returns. Thus the combined model's
improvement over M4 is not evidence of an independent scroll-count contribution.
This contrast is directly reproducible with `paired_comparison` on the two
saved `fold_aucs` dictionaries in the summary.

## Does dwell account for the overlap?

| Model without dwell-in-proximity | Pooled click AUC |
| --- | ---: |
| M4 − dwell | 0.931667 |
| M4 − dwell + cursor returns | 0.933720 |
| M4 − dwell + scroll regressions | 0.931426 |
| M4 − dwell + both | 0.933975 |

Cursor returns improve mean participant AUC by +0.002953 without dwell,
CI [+0.001387, +0.004809], versus +0.001844 with dwell. The paired difference
between those improvements is +0.001109, CI [+0.000228, +0.002150]. This supports
some shared predictive information, while the positive gain with dwell retained
provides evidence against complete predictive redundancy under this model specification.
It does not establish causal mediation.

Scroll regressions do not clearly help even when dwell is omitted:
−0.000161 participant AUC, CI [−0.000409, +0.000064]. We therefore cannot
specifically attribute their lack of added value to dwell absorbing the signal.

## Separate gaze diagnostic and definition sensitivity

| Model | Pooled click AUC | MRR@10 | Top-1 accuracy |
| --- | ---: | ---: | ---: |
| M4 + cursor returns, no gap merging | 0.936504 | 0.785593 | 64.80% |
| M4 + upward scroll gestures | 0.934912 | 0.776464 | 63.19% |
| M4 + gaze returns | 0.938903 | 0.799458 | 66.64% |
| M4 + regressive gaze returns | 0.936718 | 0.789867 | 65.15% |

Without merging cursor visits, the mean participant AUC gain remains positive:
+0.002133, CI [+0.001190, +0.003131]. The upward-scroll-gesture alternative
remains inconclusive: −0.000018, CI [−0.000371, +0.000310].

All gaze returns improve participant AUC by +0.006857,
CI [+0.005096, +0.008778]; regressive gaze returns by +0.003395,
CI [+0.002008, +0.004961]. These are gaze-dependent models. They retain all rows
and add a gaze-unavailable indicator alongside the count. One trial,
`p031-b4-t5`, has no valid pre-cutoff fixation; its counts are encoded as zero
with that indicator set, rather than treated as observed zero returns.

M3 (M4 + position) remains at pooled AUC 0.93475013 versus M4's 0.93475035.
This analysis does not test adding position to the newly augmented models.

## What the counts mean

- **Cursor returns:** per-result qualifying cursor visits minus one, floored at
  zero. Native mousemove coordinates are converted to screenshot space and
  assigned to typed XY boxes expanded by 40 px. Visits require at least 100 ms;
  qualifying visits separated by at most 5 seconds merge. Overlap goes to the
  lowest display position. The last episode ends at the last retained mousemove.
  This adapts the existing downstream visit definition to M4's native-mousemove
  stream and cutoff; it does not use other pointer event types. Counts are
  positive on 1,756 AOI rows in 903 trials. The unmerged sensitivity is positive
  on 3,580 rows in 1,526 trials.
- **Scroll regressions:** historical NB09 count of downward-to-upward transitions
  in successive scroll deltas, ignoring changes of 5 document CSS px or less.
  This is a trial-level feature, shared by every candidate, positive in 1,487
  trials. It offers no direct distinction between candidates within a trial;
  refitting can nevertheless change the other coefficients and ranking scores.
- **Upward-scroll sensitivity:** NB07a-style groups of scroll samples separated
  by at most 200 ms, with net upward displacement greater than 10 document CSS
  px. A timestamp reversal breaks the group. Positive in 1,486 trials.
- **Gaze returns:** a fixation-sequence re-entry to a previously visited typed
  Y band, after another band or an off-band fixation. Consecutive fixations in
  the same band remain one visit. Only fixation onsets before the cutoff are
  counted. This is Y-band assignment, not strict XY fixation containment.
  Positive on 11,357 AOI rows in 2,472 trials.
- **Regressive gaze returns:** the same re-entries restricted to results above
  the maximum previously visited position (the NB22 rule). Positive on 8,697
  rows in 2,323 trials.

The extraction detected one backwards scroll timestamp in `p043-b1-t5`:
669 ms, with its later endpoint 37,472 ms before the analysis cutoff. The
primary direction count preserves logger order, as the historical producer
does; the gesture sensitivity splits there. No trial was removed or silently
sorted because of this anomaly. This handling was set before model results
were inspected.

## Claim boundary and reproduction

We can say **cursor returns retain incremental click-prediction information
beyond M4; the tested trial-wide scroll count has no demonstrated incremental
benefit**. A nonsignificant gain does not establish statistical independence,
equivalence, or redundancy of every possible scroll feature. No practical
equivalence margin was prespecified. Candidate-specific scroll revisits and
nonlinear interactions were not tested here.

- Producer: [m4_return_scroll_ablation.py](../../scripts/m4_return_scroll_ablation.py)
- Full metrics, paired contrasts and provenance: [summary.json](../../scripts/output/m4_return_scroll_ablation/summary.json)
- Derived row features and timing audit: [features.json](../../scripts/output/m4_return_scroll_ablation/features.json)
- Reproduction-gate audit: [repro-audit.json](../../scripts/output/m4_return_scroll_ablation/repro-audit.json)
- Boundary tests: [test_m4_return_scroll_ablation.py](../../scripts/test_m4_return_scroll_ablation.py)

Run from this repository:

```sh
.venv/bin/python -m unittest discover -s scripts -p test_m4_return_scroll_ablation.py -v
.venv/bin/python scripts/m4_return_scroll_ablation.py
```

Seven boundary tests passed. The science-agent gate audit, resolved against the
repository root, found no issues and confirmed the baseline pin is current.
Outputs are local derived research artifacts under the ignored output directory;
no canonical caches, paper text, or existing analyses were overwritten.
