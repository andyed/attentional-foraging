# Regression does not re-enter Survey — the resumed-pass amplitude test

*2026-07-25. Rank-type: `[LAB, AdSERP, organic_hybrid]`. Producer: [`scripts/epoch_saccade_amplitude.py`](../../scripts/epoch_saccade_amplitude.py).*

## TL;DR

The OSEC task model as stated in `README.md` claimed that regressions "loop from evaluate back to
survey" — an arrow from Evaluate to Survey in the phase diagram. The claim had never been tested
non-circularly. The [OSEC Markov pass](../drafts/osec-markov-aoi-blend-findings-2026-05-31.md)
Finding 1 (regressions are 99.6 % Evaluate-phase) looks like a test but is partly definitional:
NB13 operationalizes Survey as trial saccades 1–5, so no mid-trial segment *can* be labeled Survey
under that construct.

The non-circular version uses the amplitude signature instead of the index. Survey's real signature
is wide saccades — 107.4 px vs 69.9 px evaluate, 1.54× [NB13:K5–K7]. If a regress-then-resume cycle
re-enters Survey, the *opening* saccades of the resumed pass should rebound toward ~108 px.

They don't. A resumed pass opens at **76.0 px**, recovering **20.9 % [95 % CI 16.7–24.7]** of the
survey/evaluate gap, and only **54.0 % [95 % CI 51.7–56.2]** of individual trials rebound at all —
barely off a coin flip. By the third pass the signature is gone (8.2 %). At the regression landing
itself there is nothing (8.1 %). The Evaluate→Survey arrow is not supported; a small graded
re-orientation cost at pass resumption is.

## What was run

[`scripts/epoch_saccade_amplitude.py --attribution both`](../../scripts/epoch_saccade_amplitude.py).

- **Epoch segmentation** — identical state machine to
  [`scripts/scan_epochs_per_trial.py`](../../scripts/scan_epochs_per_trial.py), instrumented to emit
  the fixation index at each epoch onset instead of just the count. Epoch 1 = initial forward sweep;
  a new epoch begins when, after a regression, the trial HWM advances past its prior max.
- **Saccades** — scroll-aware per [`docs/methodology/scroll-aware-saccades.md`](../methodology/scroll-aware-saccades.md):
  any saccade whose time window `(t[i-1], t[i]]` contains a scroll event measures page motion, not
  eye motion, and is dropped. Same code path as `13_survey_phase.ipynb` cell 3.
- **Windows** — "opening" = first 5 surviving saccades of an epoch (NB13's survey window applied to a
  pass instead of a trial); "body" = saccades 6+ within the same epoch.
- **Two anchors**, because "where the new pass starts" is arguable. **A:** epoch onset (the HWM
  advance that resumes forward scanning). **B:** regression landing (first fixation after the
  backward jump).
- **Cohort** — 2,760 trials (hybrid), 78.9 % multi-epoch; 2,690 trials (organic), 62.7 % multi-epoch.
  Matches the `scan_epochs_summary.json` ≥ 2-epoch rates (78.5 % / 62.4 %) to within rounding.

**Positive control.** Epoch-1 opening = 108.2 px against [NB13:K5]'s 107.4 px. The window definition
reproduces canonical Survey, so a failure to detect re-entry is not a failure of the instrument.

## Numbers

`[LAB, AdSERP, organic_hybrid]`, N = 2,760 trials:

| Window | Median amplitude | N saccades |
|---|---|---|
| epoch 1 opening (canonical Survey) | **108.2 px** | 13,694 |
| epoch 1 body (Evaluate baseline) | 67.5 px | 74,994 |
| **epoch 2 opening** | **76.0 px** | 10,250 |
| epoch 2 body | 68.6 px | 35,022 |
| epoch 3+ opening | 70.9 px | 16,098 |
| epoch 3+ body | 69.1 px | 60,120 |
| post-regression landing (anchor B) | 70.8 px | 568,406 |

Fraction of the 40.7 px survey↔evaluate gap recovered (1.0 = full Survey re-entry, 0 = none),
bootstrap 2,000 resamples, seed 20260725:

| Window | Recovered | 95 % CI |
|---|---|---|
| epoch 2 opening | **20.9 %** | 16.7–24.7 |
| epoch 3+ opening | 8.2 % | 5.2–11.0 |
| post-regression landing | 8.1 % | 7.7–8.6 |

Significance tests, reported for completeness — at these sample sizes they carry no information about
effect size and should not be quoted as if they did:

| Contrast | Values | Test |
|---|---|---|
| epoch 1 opening > epoch 2 opening | 108.2 vs 76.0 px (1.42×) | Mann–Whitney *p* = 9.83 × 10⁻⁹⁶ |
| epoch 1 opening > epoch 3+ opening | 108.2 vs 70.9 px (1.53×) | Mann–Whitney *p* = 1.38 × 10⁻²⁰¹ |
| epoch 2 opening > epoch 1 body | 76.0 vs 67.5 px | Mann–Whitney *p* = 1.70 × 10⁻³⁵ |
| within-trial paired (N = 1,970 trials) | epoch 2 opening 74.3 vs epoch 1 body 69.5 px | Wilcoxon *W* = 796,773, *p* = 5.63 × 10⁻¹² |

**The load-bearing number is the paired rebound rate: 54.0 % [95 % CI 51.7–56.2] of trials open their
second pass wider than they closed their first.**

## Why it's a null

Three ways the positive framing fails:

1. **Magnitude.** 76.0 px is 1.42× narrower than Survey and only a fifth of the way back to it from
   the evaluate floor. Calling that "returning to Survey" would require accepting a state whose
   defining statistic lands closer to the state it supposedly left.
2. **Per-trial incidence.** 54.0 % rebound is a distributional shift, not a state change. A phase
   transition that fires in a bare majority of the trials that structurally qualify for it is not a
   phase transition — most trials resume scanning in the same motor mode they left in, and a minority
   open slightly wider.
3. **Decay and anchor-independence.** The residual is gone by epoch 3 (8.2 %) and absent at the
   regression landing itself (8.1 %). A genuine Survey re-entry should not care whether it is the
   second pass or the fourth, and should be strongest right where the eye lands after the jump. Both
   predictions fail.

Converging with the existing geometry: 89.9 % of regressions move 1–2 ranks with ~3 fixations of work
(`findings.md` §8a); long regressions have a *truncated* destination distribution (96.4 % land P1–P5);
P6–P8 are ballistic transit zones with suppressed fixations (§8); and post-landing first fixation is
on target only 23.5 % of the time with **median distance 1 position** ([NB07b Test 5b](../../notebooks-v2/07b_regressions_triggers.ipynb)) —
local reacquisition inside ±1 rank, not a sweep across the result set.

## What was learned anyway

- **The narrow claim that survives:** there is a small, decaying re-orientation cost at the resumption
  of a scan pass — roughly a fifth of the survey↔evaluate amplitude gap on pass 2, negligible by pass
  3. If OSEC is to model regression at all beyond a labeled Evaluate transition, this is a decay term
  on resumption, not an arrow back to Survey.
- **Survey has no re-entry detector, and now we know it doesn't need one.** The index-based
  operationalization (saccades 1–5) was a known limitation; this test shows the amplitude-based
  version would find almost nothing to detect. Survey is a once-per-trial orienting phase.
- **Use `organic_hybrid`, not `organic`, for any epoch-onset-anchored measure.** The organic run gives
  epoch-1 opening = 88.0 px, not 108. Cause: organic attribution drops `dd_top` carousel fixations, so
  "epoch 1" starts after the true trial opening and clips the survey window. Hybrid includes the
  widgets and recovers the canonical anchor. This is a general trap for any metric anchored on "first
  attributable fixation" — it is not the first fixation.
- **The anchor-B window count is inflated and its CI is too narrow.** 568,406 post-landing windows come
  from every non-HWM-advancing downward step in the position sequence; the windows overlap heavily and
  are not independent. The 8.1 % point estimate is descriptively fine; the ±0.4 pp CI is not credible
  and should not be quoted.

## Pointers

- **Producer:** [`scripts/epoch_saccade_amplitude.py`](../../scripts/epoch_saccade_amplitude.py)
- **Output:** `scripts/output/figures/epoch_saccade_amplitude_summary.json` (both flavors)
- **Retired claim:** `README.md` — the phase diagram's regression arrow terminated on Survey, and the
  prose read "*Regressions* — scrolling back up to re-examine earlier results — loop from evaluate
  back to survey." Both corrected 2026-07-25. The prose also described regression as *scrolling*,
  which conflicts with the project convention that the detector is gaze-based
  (`gaze_regression_label`, see root `CLAUDE.md`).
- **Related:** [`docs/drafts/osec-markov-aoi-blend-findings-2026-05-31.md`](../drafts/osec-markov-aoi-blend-findings-2026-05-31.md)
  Findings 1–2 (99.6 % Evaluate; Reconsider-as-OSEC-node falsified) — the circular version of this
  test and the phase-point version.
- **Related:** [`docs/findings.md`](../findings.md) §8 (ballistic kinematics), §8a (HWM-8 mechanism
  split, scan-epoch modality), which this extends.
- **Related:** [`docs/methodology/scroll-aware-saccades.md`](../methodology/scroll-aware-saccades.md)
  — without the scroll-aware filter, every epoch-onset saccade following a scroll would have been
  inflated by page motion and this test would have produced a spurious positive.
- **Notebooks:** [`13_survey_phase.ipynb`](../../notebooks-v2/13_survey_phase.ipynb) (K5–K7 anchor),
  [`07b_regressions_triggers.ipynb`](../../notebooks-v2/07b_regressions_triggers.ipynb) (Test 5b).
