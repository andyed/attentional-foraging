# NB11:K12 satopt × LHIPA — duration confound (reframe)

**Date:** 2026-04-16
**Type:** Framing reframe, not a pure null. The originally reported correlation reproduces; its mechanistic interpretation does not.
**Status:** Affects how ETTAC introduces individual-difference findings. Not yet propagated into briefing docs or paper drafts.

## TL;DR

NB11:K12 reports per-participant Spearman ρ(regression_rate, mean_LHIPA) = −0.568, p < 0.001 — interpreted as "optimizers carry higher cognitive load." The correlation reproduces (we measured −0.593 on the same data, n = 47). But once trial duration is partialed out, the correlation collapses to ρ = +0.135 (p = 0.37), while the analogous duration × LHIPA partial correlation **stays massively significant** at ρ = −0.862 (p = 1.4 × 10⁻¹⁴). The deliberation-style → cognitive-load mechanism the original framing implied is not supported. The mechanism is trial duration → mean LHIPA: longer trials accumulate more low-LHIPA samples, and regression rate is just collinear with duration (raw ρ = +0.705, p = 3 × 10⁻⁸).

The companion finding is that the LF/HF × position gradient (the framework-compilation curve) is **invariant** across both satopt and speed terciles — slopes of −1.48 / −1.49 / −1.34 across satisficer / mixed / optimizer, bootstrap CI for the slope difference brackets zero (p = 0.47), and per-position Kruskal-Wallis is null at every position. Combined with the LHIPA reframe, the cleanest story is: **per-event load (LF/HF) is task-structural; the appearance of a participant-level overall-load difference is duration accumulation.**

## What was run

- **Script:** `scripts/lfhf_satopt_speed_deep_dive.py`
- **First-pass companion:** `scripts/lfhf_satopt_tercile_moderator.py` (tercile-stratified curves only)
- **Inputs:**
  - `AdSERP/data/butterworth-lfhf-by-position.json` — 2,719 trials × 11 positions, 6,099 non-null trial × position LF/HF observations across 47 participants
  - `scripts/output/survey_bimodality/per_participant_with_traits.csv` — `regression_rate`, `mean_lhipa`, `mean_fixations` per participant
  - `notebooks-v2/chattiness_per_participant.json` — `median_duration_s` per participant (the metric the original speed tercile uses)
  - `scripts/output/ski_jump_satopt/summary.json` — satopt tercile boundaries (t1 = 0.467, t2 = 0.700)
- **Tercile assignments:** Satopt boundaries are inherited from the ski-jump satopt analysis; speed boundaries are reproduced from `regenerate_lfhf_plots.py:308-316` (sort by `median_duration_s`, equal thirds).
- **Stats:** Spearman correlations on participant-level aggregates; partial Spearman computed via residuals of rank-rank linear fits with t-test approximation on n − 3 df; bootstrap CIs on per-participant slope and intercept (5 000 resamples, seeded).

## Numbers

### Cross-tab (the redundancy finding)

|                | fast | medium | slow |
|----------------|-----:|-------:|-----:|
| satisficer     |  11  |   2    |   3  |
| mixed          |   3  |  10    |   3  |
| optimizer      |   1  |   4    |  10  |

- χ²(4) = 23.78, p = 8.8 × 10⁻⁵
- Cramér's V = 0.503
- Spearman ρ(regression_rate, median_duration_s) = +0.705, p = 3 × 10⁻⁸
- 31/47 participants (66 %) sit on the diagonal vs ~33 % expected by chance

### LHIPA partial-correlation diagnostic

| Test                                                    |   ρ    |     p     |
|---------------------------------------------------------|-------:|----------:|
| Raw ρ(regression_rate, mean_LHIPA)                       | −0.593 | 1.1 × 10⁻⁵ |
| Raw ρ(median_duration_s, mean_LHIPA)                     | −0.920 | 6.4 × 10⁻²⁰ |
| Raw ρ(regression_rate, median_duration_s)                | +0.705 | 3.2 × 10⁻⁸ |
| Partial ρ(regression_rate, mean_LHIPA \| duration)       | **+0.135** | **0.37** |
| Partial ρ(median_duration_s, mean_LHIPA \| reg. rate)    | **−0.862** | 1.4 × 10⁻¹⁴ |

### LF/HF × position gradient by tercile

Per-participant slopes (LF/HF per position), median ± 95 % bootstrap CI:

| Tercile axis | Group       |   median slope | 95 % CI            |  n |
|--------------|-------------|---------------:|--------------------|---:|
| Satopt       | satisficer  | −1.48          | [−3.72, +0.06]     | 15 |
| Satopt       | mixed       | −1.49          | [−1.94, −0.70]     | 16 |
| Satopt       | optimizer   | −1.34          | [−1.60, −0.57]     | 15 |
| —            | (opt − sat) | +0.29          | [−1.16, +2.37], p = 0.47 | — |

Per-participant intercept (median LF/HF over positions 0–3) and slope correlations with each grouping metric:

|                          | regression_rate           | median_duration_s         |
|--------------------------|--------------------------:|--------------------------:|
| Intercept (positions 0–3)| ρ = +0.13, p = 0.39 (ns)  | ρ = +0.37, p = 0.012 (\*) |
| Slope                    | ρ = +0.06, p = 0.69 (ns)  | ρ = −0.09, p = 0.54 (ns)  |

Per-position Kruskal-Wallis across satopt terciles is non-significant at every position (smallest p = 0.13 at position 4).

## Why the original framing breaks

The mechanism implied by NB11:K12's framing was that optimizers exert more cognitive effort *per evaluation event* than satisficers, and LHIPA picks up the participant-level integral of that effort. If that were true, controlling for trial duration should leave a residual signal — the per-event difference would still pass through. It does not. Once duration is removed, the partial drops to ρ = +0.135 (and is in the *opposite* sign direction).

What does survive is duration → LHIPA at ρ = −0.86 even with regression_rate controlled. LHIPA is computed across the whole trial; longer trials simply contain more samples in a low-LHIPA regime. Optimizers spend longer on trials (because more regressions = more eye movements = more time, definitionally), and so their per-participant LHIPA aggregate sits lower. The per-event load is not different.

The companion LF/HF × position curves corroborate this. If optimizers truly carried higher per-event load, we would expect either (a) systematically elevated LF/HF at every position (intercept shift) or (b) a different gradient. Neither is observed: per-position Kruskal-Wallis is null everywhere, slopes are within sampling noise across terciles.

## What was learned anyway

1. **Satopt and speed are not orthogonal axes**, despite the team's working assumption. They are substantially redundant (Cramér's V = 0.50, raw ρ = +0.71). Treating them as separate moderators in the same paper would be misleading; cite one and note the other is collinear.
2. **The framework-compilation gradient is task-structural.** It does not depend on deliberation style or trial speed. This is the cleanest possible ETTAC headline: load decreases with position because of how SERP evaluation is structured, not because some participants are doing it differently.
3. **NB11:K12 should be reframed in `findings.md`** to attribute the effect to trial duration, not to deliberation style. The Spearman number itself stays in the Key Claims table; only the prose interpretation changes.
4. **For ETTAC paper:** instead of "the gradient is robust to deliberation style as a moderator" (which would be a Prediction-A confirmation framing), the line should be "the gradient is invariant across both deliberation-style and trial-speed terciles, and the apparent participant-level load difference between deliberation styles is mediated entirely by trial duration." Stronger and cleaner.
5. **Modest intercept × duration finding (ρ = +0.37, p = 0.012)** — early-scan LF/HF is slightly elevated for participants with longer median trials. Suggestive but small; would not be a load-bearing finding on its own.

## Pointers

- **Script outputs:** `scripts/output/figures/satopt_vs_speed_crosstab.{png,pdf}`, `scripts/output/figures/lfhf_speed_vs_satopt_curves.{png,pdf}`, `scripts/output/figures/lfhf_intercept_slope_by_metric.{png,pdf}`, `scripts/output/figures/lhipa_paradox_partial_correlation.{png,pdf}`
- **JSON dumps:** `scripts/output/lfhf_satopt_tercile/lfhf_satopt_tercile_summary.json` (first pass), `scripts/output/lfhf_satopt_tercile/deep_dive_summary.json` (this analysis)
- **Original NB11:K12:** `notebooks-v2/11_individual_differences.ipynb`, cell `key-correlations`
- **Speed-tercile pipeline:** `scripts/regenerate_lfhf_plots.py:308-316`
- **Satopt boundaries:** `scripts/output/ski_jump_satopt/summary.json`
- **Email thread (2026-04-16):** Andy → Samaneh, Sonja, Duchowski — the briefing that motivated this re-analysis posed Predictions A and B for satopt × LF/HF moderation. The actual data falsifies both predictions in their original forms while suggesting a stronger and simpler third reading.

## Suggested propagation (TODO)

- [ ] Update NB11:K12 Key Claim row to note the duration confound, with a `(reframed YYYY-MM-DD)` annotation per the project convention
- [ ] Replace any prose in `docs/findings.md` (or downstream briefings) that attributes the LHIPA difference to deliberation-style cognitive effort
- [ ] Decide whether to add a paragraph to the ETTAC paper or just update the briefing doc to the team
- [ ] Consider whether the `mean_lhipa` column in `per_participant_with_traits.csv` should be supplemented with a duration-residualized version for downstream individual-difference analyses
