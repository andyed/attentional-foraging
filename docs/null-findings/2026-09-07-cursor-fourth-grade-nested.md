# Four cursor grades: the extra-grade advantage is unestablished

**September 7, 2026 — [LAB, AdSERP, typed].**

## TL;DR

Four-grade cursor ranking did not stop working: its MRR@10 rose from
0.778818 to 0.779158 after correcting the validation split. Three grades
rose more, from 0.775815 to 0.779716. Both remain numerically above binary
LambdaMART (0.774191); the corrected four-minus-three difference is
−0.000558. This is a near-zero point estimate, **not a demonstrated null,
equivalence, or statistically established three-grade advantage**. The question
left open is whether the extra ranking grade adds useful signal. The four
behavioral classes have not been invalidated by this comparison.

## What was run

The [nested producer](../../scripts/ltr_cursor_only_nested_grades.py) uses
seven cursor-only features, a 500 ms pre-mousedown cutoff, 2,608 trials,
34,328 scored rows, and 47 outer participant-held-out folds. Training keeps
13,909 rows under the existing geometry-based inclusion rule. For each outer
fold, 46 inner participant-held-out labelers generate cursor training labels
without access to the outer participant; each scaler fits on its own training
rows and the deferred-probability threshold stays at 0.5. Ranker settings,
features, candidate population, and click evaluation are unchanged.

The [dependency audit](../methodology/ltr-nested-label-audit.md) explains how
the old global out-of-fold label vector allowed an outer test participant's
gaze to influence other participants' training grades. That was a validation
defect, but it does not imply that every affected estimate was inflated.

## Numbers

All entries below are [LAB, AdSERP, typed]. Old cursor-label rows are
non-nested historical diagnostics. The five noncursor rows reproduce exactly.

| Model / labels | Old MRR@10 | Nested-run MRR@10 | Nested-run NDCG@10 | MRR gain over binary LambdaMART |
|---|---:|---:|---:|---:|
| SERP position | 0.447052 | 0.447052 | 0.576393 | -0.327140 |
| Binary-click LR | 0.783732 | 0.783732 | 0.836971 | +0.009540 |
| Binary-click LambdaMART | 0.774191 | 0.774191 | 0.826504 | +0.000000 |
| Cursor, three grades | 0.775815 | 0.779716 | 0.832034 | +0.005525 |
| Cursor, four grades | 0.778818 | 0.779158 | 0.831862 | +0.004966 |
| Gaze, three grades | 0.782080 | 0.782080 | 0.834491 | +0.007889 |
| Gaze, four grades | 0.785635 | 0.785635 | 0.837236 | +0.011444 |

## What changed, and what remains unexplained

Both schemes retain clicked, deferred, evaluated-rejected, and not-approached
as behavioral classes. They differ in how those classes supervise ranking:

| Behavioral class | Three ranking grades | Four ranking grades |
|---|---:|---:|
| Clicked | 2 | 3 |
| Deferred | 1 | 2 |
| Evaluated-rejected | 0 | 1 |
| Not-approached | 0 | 0 |

The fourth grade adds an ordering between evaluated-rejected and
not-approached. Correct nesting changed the training-label generation and the
relative scores, but the retained aggregates do not identify which label
changes caused the larger improvement for three grades.

Possible explanations, **not findings**, are imperfect cursor predictions of
the gaze-defined deferred/rejected boundary, an extra behavioral ordering
that contributes little to an observed-click target, and variation across
participants or fitted rankers. Direct gaze labels still give four grades a
numerical +0.003555 MRR advantage over three; this motivates examining the
cursor-label conversion without establishing the mechanism. Both cursor
rankers also remain below binary-click LR.

The grade mappings change clicked and deferred numeric grades too. A future
claim that isolates the rejected/not-approached distinction must account for
the ranker's effective gain mapping, not just the number of classes.

## Planned exploration — not executed in this documentation pass

1. **Paired uncertainty first.** Regenerate local per-trial scores using the
   unchanged nested protocol. Estimate four-minus-three and each scheme versus
   binary on the same trials, resampling participants as clusters. Report the
   trial-weighted headline separately from an equal-participant summary; retain
   the number and direction of participant differences. Do not infer
   equivalence from an interval containing zero or select a winner from the
   current point estimates alone.
2. **Trace changed labels.** Within each outer fold, compare the old global
   labels with nested labels only on that fold's training rows. Summarize
   deferred/rejected flips, probability shifts and proximity to 0.5, and
   relate these descriptively to held-out score changes. Repeated appearances
   of a row in different outer folds are not independent observations. Keep
   row identifiers and predictions local; retain aggregate diagnostics.
3. **Separate grade ordering from gain weights.** Record the effective ranker
   gain mapping, then compare merging versus separating rejected/not-approached
   while holding clicked/deferred gains and the rest of the protocol fixed.
   Treat this as a new sensitivity experiment, not a replacement baseline.
4. **If tuning follows, keep it inside training.** Threshold or model selection
   must occur within outer-training data. Do not choose a threshold against
   outer-test clicks or gaze and report those same folds as held-out evidence.
   Nested cursor-label feature ablations also remain pending.

The immediate decision is to preserve both grade schemes and avoid claiming
a universal four-grade benefit or a failed four-class taxonomy. Click-ranking
utility does not establish independently judged relevance or WILD transfer.

## Evidence and handoff

- [Original aggregate](../../scripts/output/ltr_cursor_only_four_grades/summary_buf500.json), historical cursor-label path.
- [Nested aggregate](../../scripts/output/ltr_cursor_only_nested_grades/summary_buf500.json), SHA-256 `811e1179bd7525f652b099b7a0ad619d22cd78dcb3efb2fe1690636dbc52b101`.
- [Nested supervision audit and reproduction commands](../methodology/ltr-nested-label-audit.md).
- [Approach-retreat evidence snapshot](../../../approach-retreat/docs/evidence/2026-09-07-nested-cursor-ranking.json).

This note documents the completed comparison and proposed diagnostics; it adds
no new model run. Source and aggregate remain uncommitted. The aggregate is
under the existing ignored output directory and requires deliberate promotion
in a later authorized commit; scratch predictions must remain local.
