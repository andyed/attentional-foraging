# Position-9 fixation uptick: does not survive participant clustering (2026-04-26)

**Date:** 2026-04-26
**Status:** Retired from `task-model-paper.md` §5.8 and from the abstract on 2026-04-26. Sibling-collapse to the [2026-04-12 click ski-jump audit](2026-04-12-ski-jump-audit-collapse.md). The §5.7 motor pillar carries the forward/regressive task-mode argument on its own.
**Scripts:** [`scripts/check_pos9_fixation_uptick_clustering.py`](../../scripts/check_pos9_fixation_uptick_clustering.py)
**Sibling notebook (where the original row-level test lives):** [`notebooks-v2/23_rank_effects.ipynb`](../../notebooks-v2/23_rank_effects.ipynb) cell #7

## TL;DR

The pre-audit `task-model-paper.md` §5.8 claimed that splitting the fixation-count-by-position curve into forward and regressive entries reveals a forward-only uptick at position 9 (Mann–Whitney *p* = 1.7 × 10⁻¹⁶), interpreted as a "click-vs-regress" decision signature distinct from the classical click-share ski-jump. Recomputed on 2026-04-26 with participant-clustered tests, **the per-participant version of the test reverses sign**: 8 of 9 non-tied participants show median pos 9 < pos 8 (the opposite of the predicted direction), Wilcoxon signed-rank *p* = 0.016 *wrong-sign*, sign test 1/9 positive (*p* = 0.039 *wrong-sign*).

This is the same audit-collapse pattern as the [2026-04-12 click ski-jump](2026-04-12-ski-jump-audit-collapse.md): a row-level test inflated by participant pseudo-replication where rows are not independent. Of the 47 participants, only **13 contributed any forward pos-9 rows** at all, and the top 4 contributing participants (p009, p010, p005, p037) account for 59 % of the pos-9 row pool. Drop those four and the row-level test goes from "*p* < 10⁻¹⁶" to a clean null in the wrong direction.

## What the audit actually showed

Re-run via `classify_fixations` (HWM tolerance 50 px) over all 2,776 trials, organic-rank position assignment via `result_bands(10, doc_height)`:

### Row-level (matches the §5.8 framing)
| Test | n | medians | one-sided p (greater) |
|---|---|---|---|
| Forward pos 8 vs pos 9 | 361 / 34 | 2 vs 1 | **0.999** |
| Regressive pos 8 vs pos 9 | 31 / 5 | 1 vs 1 | **0.974** |

Both directions go the wrong way relative to the §5.8 claim, on row counts roughly half what §5.8 cites (640 / 729 vs 361 / 34 for forward). The discrepancy in row counts is itself a flag — either NB23 cell #7 used a different row-pooling rule, or the row counts were also a coordinate-fix victim. Either way, the participant-clustering verdict makes the row-count question moot.

### Per-participant (the test row-level pseudo-replication hides)
| Stat | Value |
|---|---|
| Participants contributing any pos-9 forward rows | 13 / 47 |
| Top-4 share of pos-9 rows | 59 % (p009, p010, p005, p037) |
| Participants with both pos-8 and pos-9 forward data | 13 / 47 |
| Direction: pos9 > pos8 (predicted) | **1** |
| Direction: tied | 4 |
| Direction: pos9 < pos8 (opposite) | **8** |
| Median delta (pos 9 − pos 8) | **−1 fixation** |
| Wilcoxon signed-rank *p* (two-sided) | 0.016, *wrong sign* |
| Sign test (1/9 positive) | 0.039, *wrong sign* |

### Robustness: drop top contributors, redo row-level test
| Drop | n_8 / n_9 | medians | one-sided p (greater) |
|---|---|---|---|
| top 1 (p009) | 322 / 28 | 2 vs 1 | 0.996 |
| top 2 (p009, p010) | 297 / 22 | 2 vs 1 | 0.999 |
| top 4 (p005, p009, p010, p037) | 278 / 14 | 2 vs 1 | 0.989 |

## Why it's a null (what changed)

Same root cause as the [click ski-jump](2026-04-12-ski-jump-audit-collapse.md): a small number of participants have many trials reaching position 9, and within those participants the trials are correlated. A row-level Mann–Whitney treats all rows as independent, which inflates the apparent test power. The honest test pairs participants — for each participant who reached both pos 8 and pos 9, ask "which is bigger?" — and almost no one shows the §5.8 direction.

The original NB23 cell #7 numbers (640 / 729 row counts) cannot be replicated cleanly by `classify_fixations` + organic rank. The discrepancy may also indicate the original cell used absolute rank, included regressive entries in some way, or a different fixation-to-position assignment rule. Regardless: the per-participant test is the right test, and it kills the finding.

## What survives

The §5.7 motor pillar — cursor-gaze coupling tighter for regressive than forward fixations — does survive participant clustering, with 37 of 46 participants in the predicted direction (Wilcoxon *p* = 4.8 × 10⁻⁵, sign test *p* = 4.1 × 10⁻⁵, median within-participant gap +37.5 px); robustness check confirms: drop the four most-extreme deltas and 34/42 participants still show the predicted direction. That finding carries the forward/regressive distinction on its own. See [`scripts/check_motor_pillar_clustering.py`](../../scripts/check_motor_pillar_clustering.py) for the per-participant motor-pillar verification.

The §5.7 geometric arc-ratio finding was already self-flagged as "suggestive, not clustered-significant" (*p* ≈ 0.08 with 12 regressive participants) and stays in that posture.

The §5.7 LHIPA pupillometric finding was already self-flagged as a confound rather than an independent claim.

## What was learned anyway

1. **Run the per-participant test first.** Both AdSERP ski-jump variants (click-share at pos 10, fixation-count at pos 9) failed the same way: row-level p inflated by participant pseudo-replication. Per-participant tests should be the default for any rank-effect claim on AdSERP, not an audit afterthought.

2. **Coordinate-fix audits do not always strengthen findings the way the M4 cursor audit did.** The 2026-04-12 audit strengthened M4 retreat-distance dissociation (p went 10⁻¹¹ → 10⁻³⁸); the same audit window collapsed the click ski-jump and did not save the fixation ski-jump from per-participant collapse. The pattern is not "audits surface real signal" — the pattern is "audits surface whatever the underlying data actually contains, including the absence of the hoped-for signal."

3. **The motor pillar's pooled-vs-per-participant agreement is itself diagnostic.** Pooled gap 44 px, within-participant median gap +37.5 px, sign test 37/46 — those numbers should agree if the pooled finding is real. They do. For the position-9 uptick, the pooled and per-participant tests went in *opposite directions*, and that disagreement was the telltale.

## Pointers

- §5.7 motor pillar (surviving): `docs/drafts/task-model-paper.md` §5.7
- Sibling click-side null: [`2026-04-12-ski-jump-audit-collapse.md`](2026-04-12-ski-jump-audit-collapse.md)
- Pre-retire snapshot: §5.8 of `task-model-paper.md` as of 2026-04-25 (in git history)
- Recompute scripts:
  - [`check_pos9_fixation_uptick_clustering.py`](../../scripts/check_pos9_fixation_uptick_clustering.py) — the audit that killed the §5.8 claim
  - [`check_motor_pillar_clustering.py`](../../scripts/check_motor_pillar_clustering.py) — the audit that confirmed §5.7 survives
- Original row-level test source: [`notebooks-v2/23_rank_effects.ipynb`](../../notebooks-v2/23_rank_effects.ipynb) cell #7
