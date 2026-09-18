# Does fixation duration buy parafoveal attribution? — the skip test

**Tags:** `[LAB, AdSERP, typed]` · first-pass forward moves only
**Producer:** `scripts/duration_parafoveal_accrual.py` → `scripts/output/duration_parafoveal_accrual/summary.json` (promoted 2026-09-18 from the 2026-09-14 inline analysis; the producer's numbers below supersede the inline ones, which are kept in the sidecar as `inline_reference_2026_09_14`). Inputs: typed bands, fixations by the label producer's rule, the primary census states for the trial list
**Question:** PAI accrues peripheral mass as fixation duration × a spatial weight, which is the gradient-accrual assumption (SWIFT-like): the longer the eyes rest on result k, the more parafoveal processing result k+1 receives. A probabilistic reading would be P(k+1 attended parafoveally) = 1 − exp(−d·α/τ). The serial-attention alternative (E-Z Reader-like) says attention shifts to k+1 only when foveal processing of k completes, so a long fixation on k means k was hard and k+1 got *less* preview. The two make opposite predictions for the next forward saccade: under accrual, longer visits on k → more skipping of k+1 (already processed); under serial attention, longer visits → less skipping.

## Test

7,205 first-pass forward moves out of a first visit to result k where k+1 and k+2 exist (2,319 trials, 47 participants; skip rate 0.205). Outcome: the next fixated result is beyond k+1 (skip) vs k+1. Controls: position, k+1's block height, k+1 non-organic. *(The 2026-09-14 inline walk counted 6,834 moves; the producer's first-visit definition is the label producer's run rule and admits a few more.)*

| visit duration quintile on k | shortest | 2 | 3 | 4 | longest |
|---|---|---|---|---|---|
| P(skip k+1) | 0.256 | 0.247 | 0.198 | 0.186 | **0.138** |

LOSO logistic regression: position + height + ad-next AUC 0.629; adding log visit duration 0.643 with a standardized coefficient of **−0.233**; log last-fixation duration alone −0.124 (AUC 0.632); log fixation count alone −0.197 (0.637); all three together 0.643 with the visit-duration term carrying it (−0.209; last-fixation −0.054, count −0.005). Per participant, Spearman(duration, skip) is negative in **36 of 47**, median −0.081. *(Inline 2026-09-14: 0.217 → 0.131; 0.637 → 0.642; coefficient −0.156; 34/47, median −0.046. Same sign, same reading.)*

## Reading

Longer time on a result makes the next result *more* likely to be read, not less. That is the serial-attention signature, not accrual: duration on k does not translate into processed-and-dismissed k+1. Two cautions. Visit duration also indexes mode (a long visit is committed reading, a short one is scanning, and scanning skips more), so the sign is consistent with a mode account as well as with E-Z Reader's timing; the test does not separate them. And the effect is small (about one and a half AUC points, 0.629 to 0.643).

For PAI: fixation duration is a defensible *exposure* weight (how long the target sat in the periphery) but not, on this evidence, a *probability of attribution* weight. A probabilistic version would need the attribution to depend on when attention shifts, not on how long the fovea rested, and the next-saccade target is the observable that would fit it. That fits the rest of the day's picture: the periphery guides the next fixation and does not process what it does not get.
