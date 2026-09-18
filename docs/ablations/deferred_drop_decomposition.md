# Why the deferred-class classifier moved from ~0.75 to 0.691 — one rung at a time

**Tags:** `[LAB, AdSERP, typed]` · 47-fold LOSO balanced logistic regression on the seven M4 features · target = NB22 gaze-regression label (deferred = 1, evaluated-rejected = 0), the typed cache keyed by (trial, position) at every rung
**Producer:** `scripts/deferred_drop_decomposition.py` → `scripts/output/deferred_drop_decomposition/summary.json`
**Gate:** the final rung reproduces `m4_cursor_only_downstream/summary.json` `section_4_3.deployable_M4_7.pooled_auc` (0.6911) to 1e-6 (diff 0.0).
**Key Claims:** none yet.
**Generated:** 2026-09-17, in answer to Peter Dixon-Moses's question of 2026-09-16.

## Question

The May cheat sheet reported the cursor-only deferred classifier at 0.753
(organic flavour, 2,067 fixation-selected rows). The current paper reports
0.691 (typed, 9,932 cursor-only approached non-click rows). Four things
changed between them: the feature definition (the May stream selected rows
by fixation, sampled the cursor at fixation times, and measured
gaze-to-cursor distance; the current stream is the real tracker's
one-dimensional cursor-to-centre distance on native `mousemove` events), the
sampling, the press buffer (the May click-anchored buffer removed no
samples), and the row population. Which one is it, and is the 100 px
standoff threshold still there?

## The ladder

Each rung changes one thing. The first three cursor-only rungs use the same
3,706 rows as the LAB rung, so population is held fixed until the last step.

| rung | rows | pooled AUC | fold mean ± sd | n (deferred / rejected) |
|---|---|---|---|---|
| L · LAB typed: fixation-selected rows, gaze-to-cursor distance at fixation times, click-anchored buf500 | full LAB pool | 0.764 | 0.751 ± 0.119 | 3,875 (3,297 / 578) |
| L · same, restricted to the shared rows | shared | **0.771** | 0.757 ± 0.121 | 3,706 (3,148 / 558) |
| G0 · cursor-only tracker features, cursor sampled at fixation onsets, buf0 | shared | **0.665** | 0.689 ± 0.142 | 3,706 |
| N0 · cursor-only, native sampling, buf0 | shared | 0.663 | 0.687 ± 0.154 | 3,706 |
| N5 · cursor-only, native, press-anchored buf500 | shared | 0.659 | 0.682 ± 0.156 | 3,706 |
| C · cursor-only, native, buf500 | full cursor pool | **0.691** | 0.694 ± 0.070 | 9,932 (6,800 / 3,132) |

(G5, fixation-onset sampling with buf500 on the shared rows, is 0.662; the
paper's matched-row ceiling protocol on these rows.)

| step | what changes | paired participant Δ, 95 % CI |
|---|---|---|
| L → G0 | feature definition | **−0.068 [−0.116, −0.017]** |
| G0 → N0 | sampling, fixation onsets → native | −0.002 [−0.021, +0.016] |
| N0 → N5 | press buffer, 0 → 500 ms | −0.005 [−0.012, +0.002] |
| N5 → C | rows, fixation-selected → full cursor pool | +0.012 [−0.026, +0.052] |

The organic-flavour LAB rung on the current (post-coordinate-conversion)
cache is 0.724 on 2,464 rows, so the May 0.753 was the organic flavour on
the pre-fix substrate; the typed LAB rung is its counterpart here.

## Reading

**The drop is the feature definition, and it is the right drop.** On
identical rows and labels, replacing the LAB stream's features with the
tracker's costs 0.07 AUC, and nothing else in the pipeline moves the number
outside its interval. The LAB features were not cursor-only: `mean_dist`
and `min_dist` there are distances from the *fixation position* to the
cursor, sampled at fixation times, and `dwell_in_proximity_ms` is weighted
by fixation duration. The label is whether the fixation sequence returns to
the result. A feature built from fixation positions and durations carries
part of that label. The ~0.75 figure was cursor geometry plus a gaze term;
0.69 is cursor geometry. That is the same lineage finding that raised the
click headline (the tracker's features are cleaner for the click task) and
lowered this one (the old features had gaze in them for the return task).

**Sampling and the buffer are free.** Native sampling and a real 500 ms
press buffer together cost under 0.01, inside their intervals.

**Population raises the pooled number slightly and tightens it a lot.** The
full cursor pool adds the rows the eyes never selected; pooled AUC moves
+0.03 (paired participant Δ +0.012, CI including zero) and the
per-participant spread halves (sd 0.156 → 0.070). The LAB pool is 85 / 15
deferred / rejected; the full pool is 68 / 32.

**The standoff threshold.** Yes, a constant 100 px proximity zone still
defines "approached" (now on the one-dimensional cursor-to-centre distance).
It is not doing the work:

| approached = min_dist < | pool | pooled AUC |
|---|---|---|
| 50 px | 7,849 | 0.690 |
| **100 px** | **9,932** | **0.691** |
| 200 px | 12,710 | 0.701 |

**Not answered here.** Whether a gaze-free feature could recover the 0.07;
the LOFO in the main note says `mean_dist` carries what is left. And the
per-participant spread on the shared rows is wide at every cursor-only
rung (sd ≈ 0.15 on 3,706 rows), which is a small-fold artefact the full
pool removes.
