# Is the graded signal there at gaze fidelity? — LambdaMART with gaze-census training labels on cursor-only features

**Tags:** `[LAB, AdSERP, typed]` · cursor-only typed buf500 records (34,328; 2,608 trials; 47 participants) · 47-fold participant LOSO · LGBMRanker lambdarank, NDCG@10 objective, 200 trees, lr 0.05, 31 leaves, min 20 · the NotApprBelow training exclusion held fixed for every scheme (13,909 training rows) · inference on the seven cursor features, every main-axis AOI scored
**Producer:** `scripts/ltr_gaze_graded_labels.py` → `scripts/output/ltr_gaze_graded_labels/summary_buf500.json`
**Gate:** the binary and four-grade gaze rows reproduce `ltr_cursor_only_nested_grades/summary_buf500.json` MRR@10 (0.7742, 0.7856) to 1e-6.
**Key Claims:** none yet.
**Generated:** 2026-09-17.

## Question

The deferred state is gaze-defined and the cursor reads it at 0.69
(`deferred_drop_decomposition.md`). Does the graded-relevance signal exist
at the fidelity gaze now gives — five states, return counts, dwell — and
does a ranker on cursor features gain from being trained on it? Two
evaluations, because they reward different things:

- **click MRR@10** on the binary click vector: the harvest. A grade
  ordering among non-clicked results can only help here if it lifts the
  click.
- **graded NDCG@10** against the six-state gaze grade as relevance, scored
  on results that were on screen (so "never on screen = 0" does not hand
  the metric to position): the examination order. This is the
  relevance-judgment view of the same rankers. The oracle that scores each
  result by its own grade is 1.0 by construction.

Label schemes, all from gaze plus click, on identical training rows:
**gaze4** (clicked 3 / approached-and-returned 2 / approached-not-returned 1
/ not approached 0, the paper's label, which carries a cursor-approach filter
inside it); **gaze4 census** and **gaze3 census** (the same coarse grades
from gaze alone: clicked / fixated-and-returned / fixated-not-returned /
not fixated, and the three-grade collapse with rejected folded to 0; no
approach filter anywhere); **states6** (clicked 5 / deferred with ≥ 3 visits 4 /
deferred 3 / rejected 2 / peripheral 1 / unsampled, brief, never on screen
0); **cost4** (four states with the measured cost tiers as LightGBM gain,
0 / 5.41 / 16.95 / 40.52); **dwell10** and **visits10** (click pinned at
grade 9, the rest ranked within trial by total gaze dwell or visit count
into 8..0, exponential gain; NB26's K24 construction with a gaze scalar);
**dwell10 linear** (linear gain).

## Results

| ranker (training labels) | click MRR@10 | paired Δ vs binary [95 % CI], participants > 0 | graded NDCG@10, on-screen | paired Δ vs binary [CI], > 0 |
|---|---|---|---|---|
| SERP position (no ML) | 0.447 | | 0.930 | |
| LambdaMART, binary click | 0.774 | — | 0.931 | — |
| **LambdaMART, gaze4** | **0.786** | **+0.012 [+0.004, +0.019], 33/47** | **0.943** | **+0.011 [+0.009, +0.014], 44/47** |
| LambdaMART, gaze4 from gaze alone (no approach filter) | 0.763 | −0.011 [−0.020, −0.001], 16/47 | 0.931 | +0.000 [−0.002, +0.002], 23/47 |
| LambdaMART, gaze3 from gaze alone (rejected folded to 0) | 0.765 | −0.009 [−0.018, −0.002], 20/47 | 0.932 | +0.001 [−0.001, +0.002], 26/47 |
| LambdaMART, six grades within cursor reach (clicked 5 / deferred ≥ 3 visits 4 / deferred 3 / rejected 2 / approached-unfixated 1 / not approached 0) | 0.780 | +0.006 [−0.003, +0.016], 27/47 | 0.942 | +0.011 [+0.009, +0.014], 41/47 |
| LambdaMART, click-pinned dwell rank among approached rows | 0.775 | +0.001 [−0.009, +0.011], 26/47 | 0.940 | +0.009 [+0.007, +0.012], 39/47 |
| LambdaMART, states6 | 0.760 | −0.013 [−0.022, −0.005], 20/47 | 0.932 | +0.001 [−0.002, +0.003], 24/47 |
| LambdaMART, cost4 | 0.764 | −0.010 [−0.019, −0.002], 20/47 | 0.931 | −0.000 [−0.002, +0.002], 19/47 |
| LambdaMART, dwell10 exp | 0.752 | −0.022 [−0.035, −0.010], 13/47 | 0.930 | −0.001 [−0.004, +0.001], 18/47 |
| LambdaMART, visits10 exp | 0.750 | −0.024 [−0.037, −0.012], 16/47 | 0.929 | −0.002 [−0.004, +0.000], 18/47 |
| LambdaMART, dwell10 linear | 0.737 | −0.036 [−0.052, −0.021], 9/47 | 0.933 | +0.002 [−0.002, +0.005], 34/47 |
| position + cursor, binary | 0.768 | −0.007 [−0.017, +0.003], 21/47 | 0.927 | −0.004 [−0.006, −0.003], 8/47 |
| **position + cursor, gaze4** | **0.798** | **+0.024 [+0.015, +0.033], 37/47** | **0.944** | **+0.013 [+0.010, +0.016], 45/47** |
| position + cursor, gaze4 from gaze alone | 0.769 | −0.006 [−0.016, +0.003], 22/47 | 0.933 | +0.001 [−0.001, +0.004], 24/47 |
| position + cursor, gaze3 from gaze alone | 0.769 | −0.006 [−0.017, +0.005], 21/47 | 0.933 | +0.002 [−0.000, +0.004], 29/47 |
| position + cursor, six grades within reach | 0.791 | +0.017 [+0.006, +0.027], 31/47 | 0.945 | +0.014, 44/47 |
| LGBM pointwise regression on the four-grade label | 0.765 | −0.008 [−0.022, +0.005], 24/47 | 0.945 | +0.014 [+0.011, +0.018], 40/47 |
| LGBM pointwise regression on six-within-reach | 0.751 | −0.022 [−0.036, −0.008], 16/47 | 0.944 | +0.013 [+0.009, +0.017], 38/47 |
| position + cursor, states6 | 0.769 | −0.005 [−0.015, +0.005], 20/47 | 0.937 | +0.006 [+0.003, +0.009], 34/47 |
| position + cursor, cost4 | 0.769 | −0.005 [−0.016, +0.004], 21/47 | 0.933 | +0.001 [−0.001, +0.004], 27/47 |

NDCG@10 against the paper's four-grade relevance itself (on-screen): binary
0.898 · four grades 0.945 · six within reach 0.944 · pointwise regression on
four grades **0.954** · pure-gaze four grades 0.880 · SERP position 0.884.
Paired deltas are per-participant means of per-trial metrics, 10,000-sample
bootstrap. Graded NDCG is scored on 2,564 trials over on-screen AOIs (trials with no on-screen non-zero grade beyond the click are skipped).

## Reading

**The signal is there, and the ordinal model does learn it.** Against the
paper's own four-grade relevance, a cursor ranker trained on binary clicks
scores 0.898 NDCG@10; trained on the four grades it scores 0.945; a
pointwise ordinal regression on the same label scores 0.954. That is a
+0.05 label effect on the examination order, learnable from the seven
cursor features. On the click metric the same labels give +0.012 (or
+0.024 with position). The two evaluations pull in different directions:
lambdarank with an NDCG objective concentrates on the top item and gets
most of the click gain, pointwise regression orders everything and gets
most of the examination gain while losing 0.008 on the click.

**Resolution beyond four grades adds nothing, and does not hurt within
reach.** Six grades confined to cursor-approached rows (returns split by
visit count, approached-but-unfixated as its own grade) match the four-grade
label on the graded metric (+0.011, 41/47) and are neutral on the click
(+0.006, CI including zero). Click-pinned dwell rank among approached rows,
the same. The gradation a cursor ranker can consume is clicked > deferred >
rejected > unseen; splitting deferred by return count or dwell adds no
orderable information.

**The effect is gaze inside the cursor's reach, and that is the constraint
that matters.** Take any label that grades a result the eyes revisited but
the cursor never approached above zero, and the lift reverses on both
metrics: the pure-gaze four grades score −0.011 on the click (16/47) and
0.880 on the graded metric, *below* the binary-trained ranker's 0.898 and
below SERP position. A result with an empty cursor trace is, to a cursor
ranker, an unseen result; grading it high asks the model to separate
identical inputs, and it learns noise. The earlier reading of this note,
that finer labels hurt because lambdarank wastes gradient on pairs the
cursor cannot see, was the approach filter leaking: every "finer" label
that failed also removed the filter. The paper's deferred class (approached
∧ returned, 6,800 rows) is the one that trains; the census's deferred state
(fixated ∧ returned, 9,797 slots) describes examination and must not be
used as a training label. State this in §3.4 where the two populations are
named.

**The examination order is mostly position.** On on-screen results, SERP
position alone scores 0.930 on the graded metric and no cursor-only ranker
beats it by more than 0.013. Whatever graded structure the gaze states
carry beyond reading order is small, and the four-grade label recovers most
of what a cursor ranker can get.

**One new positive.** Position plus the seven cursor features, trained on
gaze4, reaches MRR@10 0.798, the best ranker on this protocol, above
pointwise LR at 0.784, with a +0.024 paired lift over its own binary
counterpart in 37 of 47 participants. The paper's rankers omit position by
the original spec; this row says the gaze label's value roughly doubles
when position is in the model, which is consistent with the label carrying
the examination order that position proxies.

**What this settles for the paper.** Graded gaze labels, restricted to
cursor-approached results, give a small gain on the click (+0.012; +0.024
with position) and a large gain on ordering examination (+0.05 NDCG against
the four-grade relevance). Neither grows with label resolution, and both
disappear when the cursor filter is removed. The ranking footnote should
carry both numbers and name the deferred definition it uses; the graded-NDCG
result is the one that speaks to relevance judgments and belongs beside the
C/W/L discussion rather than in a deployment claim. The five-state census is a
description of examination and its costs, not a better training label.

**Not established.** Whether gaze grades help a ranker that also sees
gaze features (trivially leaky on the click, and near-circular on the
graded metric, so not run); whether the graded metric would separate labels
on an informational corpus with heterogeneous relevance (this one has none
to speak of).
