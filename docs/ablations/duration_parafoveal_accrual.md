# Does fixation duration buy parafoveal attribution? — the skip test

**Tags:** `[LAB, AdSERP, typed]` · first-pass forward moves only
**Producer:** inline analysis 2026-09-14 (to be promoted to a script if quoted); inputs: typed bands, fixations by the label producer's rule, the primary census states for the trial list
**Question:** PAI accrues peripheral mass as fixation duration × a spatial weight, which is the gradient-accrual assumption (SWIFT-like): the longer the eyes rest on result k, the more parafoveal processing result k+1 receives. A probabilistic reading would be P(k+1 attended parafoveally) = 1 − exp(−d·α/τ). The serial-attention alternative (E-Z Reader-like) says attention shifts to k+1 only when foveal processing of k completes, so a long fixation on k means k was hard and k+1 got *less* preview. The two make opposite predictions for the next forward saccade: under accrual, longer visits on k → more skipping of k+1 (already processed); under serial attention, longer visits → less skipping.

## Test

6,834 first-pass forward moves out of a visit to result k where k+1 and k+2 exist (2,283 trials, 47 participants). Outcome: the next fixated result is beyond k+1 (skip) vs k+1. Controls: position, k+1's block height, k+1 non-organic.

| visit duration quintile on k | shortest | 2 | 3 | 4 | longest |
|---|---|---|---|---|---|
| P(skip k+1) | 0.217 | 0.201 | 0.182 | 0.171 | **0.131** |

LOSO logistic regression: position + height + ad-next AUC 0.637; adding log visit duration 0.642 with a standardized coefficient of **−0.156**; log last-fixation duration −0.093; log fixation count in the visit −0.122. Per participant, Spearman(duration, skip) is negative in **34 of 47**, median −0.046.

## Reading

Longer time on a result makes the next result *more* likely to be read, not less. That is the serial-attention signature, not accrual: duration on k does not translate into processed-and-dismissed k+1. Two cautions. Visit duration also indexes mode (a long visit is committed reading, a short one is scanning, and scanning skips more), so the sign is consistent with a mode account as well as with E-Z Reader's timing; the test does not separate them. And the effect is small (five AUC points from 0.637 to 0.642).

For PAI: fixation duration is a defensible *exposure* weight (how long the target sat in the periphery) but not, on this evidence, a *probability of attribution* weight. A probabilistic version would need the attribution to depend on when attention shifts, not on how long the fovea rested, and the next-saccade target is the observable that would fit it. That fits the rest of the day's picture: the periphery guides the next fixation and does not process what it does not get.
