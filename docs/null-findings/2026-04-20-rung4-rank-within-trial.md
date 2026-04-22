# Rung 4 rank-within-trial withstood labels: null (but informative)

**Date:** 2026-04-20
**Notebooks/scripts:** `scripts/nb26_rung4_withstood.py`, `scripts/nb26_rung4_variants.py`
**Artifacts:** `scripts/output/nb26_rung4_withstood/summary.json`, `scripts/output/nb26_rung4_variants/summary.json`

## TL;DR

We had a Phase 3 hypothesis that **denser labels beat 3-grade** on the NB26 LTR task: replace the 3-grade `{clicked, deferred, eval-rejected/not-approached}` label with a 10-way continuous label derived from the `withstood_evaluation` composite (see `scripts/build_withstood_evaluation_score.py` and Phase 2 validation `scripts/withstood_evaluation_validation.py`). Three naive operationalisations (R4a `g10_pre` exp gain, R4b `g10_full` exp gain, R4e `g10_pre` linear gain) all **under-performed** the 3-grade baseline by ≈ 2.6 MRR points on the same text + M4 + VP feature set, Wilcoxon p ≈ 0.98. Ridge pointwise MSE on continuous `w_pre` (R4c) *matched* 3-grade but didn't beat it (Δ MRR = +0.008, p = 0.29). The null is *why this specific label noise kills the denser-supervision win*: when `withstood_pre_click` is ranked within-trial, 47 / 2,115 (2.2 %) of clicked items land at the lowest grade, and LambdaMART trains to rank them at the bottom. The hybrid remedy (click pinned at grade 9, remaining 9 positions ranked by withstood among themselves) *does* deliver the denser-label win (+0.143 MRR, p < 10⁻⁹, see R4f) — that's the **positive** writeup companion to this null and lives elsewhere.

## What was run

**Feature set (all variants):** text (5) + M4 cursor (9 + 1 approached flag) + viewport/trajectory (6) = 21 features. Same `text_m4_vp` mode as NB26 Rung 3 (the "kitchen sink").

**CV protocol:** 47-fold leave-one-participant-out, seeds 0 / 1 / 2 averaged, full-SERP evaluation (all 10 positions per held-out trial scored, MRR and NDCG@10 computed against the clicked position).

**Trials:** 2,115 full-SERP trials with a click + all 10 positions having embeddings.

**Labels — the variants:**
- `g3` (baseline): 2 = clicked, 1 = approached ∧ gaze-regressed, 0 = eval-rejected / not-approached-above-click.
- `g10_pre`: rank-within-trial of `withstood_pre_click`. Highest within-trial withstood → grade 9.
- `g10_full`: same but `withstood_full` (leakage upper bound).
- `w_pre`: continuous `withstood_pre_click` as MSE target.

**Rankers:**
- LambdaMART 3-grade: `label_gain = [0, 1, 2]`.
- LambdaMART 10-grade exp: `label_gain = [2^0, 2^1, ..., 2^9]`.
- LambdaMART 10-grade linear: `label_gain = [0, 1, ..., 9]`.
- Ridge MSE: `StandardScaler → Ridge(α=1.0)`, pointwise.

## Numbers

| rung | MRR | NDCG@10 | Δ MRR vs R3 | p (greater) |
|---|---|---|---|---|
| **R3_3grade (baseline)** | 0.6770 | 0.7588 | — | — |
| R4a_10grade_pre, exp gain | 0.6559 | 0.7410 | −0.0261 | 0.977 |
| R4b_10grade_full, exp gain | 0.6549 | 0.7402 | −0.0269 | 0.984 |
| R4c_continuous Ridge | 0.6885 | 0.7656 | +0.0080 | 0.287 |
| R4e_10grade_pre, linear gain | 0.6552 | 0.7403 | −0.0271 | 0.979 |

**Clicked-item distribution across `g10_pre` buckets:**

```
bucket:   0   1   2   3   4   5   6   7    8    9
clicks:  47  12  19  20  63  79 138 224  567  946
```

Grades 8+9 hold 71.5 % of clicks. 47 / 2,115 (2.2 %) clicks are at grade 0, the lowest within-trial withstood rank. `g10_full` is indistinguishable (46, 13, 21, 20, 63, 75, 138, 226, 563, 950).

## Why it's a null

Two hypotheses pre-registered; both falsified:

1. **Gradient-weighting hypothesis: `[2^i]` concentrates lambda on top-vs-rest pairs, leaving middle-grade pairs unused.** Falsified by R4e: linear `label_gain` gave Δ MRR = −0.001 (p = 0.70) vs exp, i.e. the gradient shape is not the story.
2. **More-pairs-helps hypothesis: 10-grade gives ≈ 45 informative pairs per trial vs ≤ 3 from 3-grade, so pairwise supervision should sharpen.** Falsified because the denser label *injects* noise: 2.2 % of ground-truth clicks are at grade 0, and LambdaMART optimises to put them at the bottom. The extra pairs are consistent with a *wrong* ordering at the click-distinguishing boundary.

What the hybrid variant (R4f, click pinned at 9) demonstrates by contrast: the extra ordering signal among non-clicks *is* real and adds +0.143 MRR when the click-boundary noise is removed. So the "denser labels help" intuition is vindicated — the rank-within-trial operationalisation was simply the wrong way to encode it.

## What was learned anyway

- **`withstood_evaluation` is strongly correlated with clicks (+0.654 mean z-score on clicked items, 71.5 % at top 2 within-trial grades) but not co-linear.** The 2.2 % grade-0-click rate is the measurement of "compiled evaluation withstood" for items the user decided to click *despite* low sustained engagement — interrupted decisions, final-item satisficing, possibly click errors. Treating this subset as ground-truth relevance is a separate research question, not a labeling bug to route around.
- **Ridge MSE pointwise matches LambdaMART 3-grade on this task.** The pairwise-ranking benefit over pointwise regression is small (+0 to +0.01 MRR, not significant) when features already encode most of the relevance signal. This is relevant for any downstream deployment that can't carry LightGBM.
- **Linear vs exp `label_gain` is second-order when labels are fine-grained.** If the label already encodes a stable ordering near the top (R4f hybrid), exp gain wins by +0.033 MRR (R4f 0.8248 vs R4g 0.7912). If the top is noisy (R4a/e), the gain shape doesn't rescue it.

## Pointers

- Producer: `scripts/build_withstood_evaluation_score.py`, output `AdSERP/data/withstood-evaluation-score.json` (27,760 rows, 7.3 MB).
- Validation (Phase 2 gate): `scripts/withstood_evaluation_validation.py`, output `scripts/output/withstood_evaluation_validation/summary.json`.
- Rung 4 runs: `scripts/nb26_rung4_withstood.py` (4 configs), `scripts/nb26_rung4_variants.py` (3 remedial configs).
- Companion positive finding (R4f hybrid click-pinned): to be written to `docs/findings.md` as a new §8 addition.
