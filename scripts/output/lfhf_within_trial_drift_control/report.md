# Within-trial LF/HF drift control

_Generated 2026-05-03 by `scripts/lfhf_within_trial_drift_control.py`._

## Question

Could the +9.75 LF/HF return-vs-first paired Δ reflect within-trial pupil
drift (autonomic regulation, fatigue, baseline shift) rather than cognitive
content of the return moment?

## Test

WITHIN each trial, compare LF/HF at the **earliest forward-pass position**
(early in trial time) vs the **latest forward-pass position** (later in trial
time). Forward-only — no return visits in this control.

## Decision rule

- If Δ ≈ 0 (later time ≠ different LF/HF): drift hypothesis cannot explain
  the paired finding. Paired finding is genuine cognitive content.
- If Δ > 0 (later time = higher LF/HF, mirroring the paired Δ): drift
  hypothesis is plausible. Paired finding may be confounded.
- If Δ < 0 (later time = lower LF/HF, matching the cross-trial rank
  gradient): drift hypothesis is decisively rejected.

## Result

**Trial-level paired Wilcoxon, n = 1,241 trials with ≥2 forward-pass positions**

- median Δ = **-1.969**
- mean Δ = -3.977
- 54.2% of trials show Δ < 0
- *p* (two-sided) = 5.14e-04
- *p* (less than 0, rank-gradient prediction) = 2.57e-04

**Participant-level**

- 46 participants, mean-of-means = -3.434
- 56.5% of participants show Δ < 0
- *p* (less than 0) = 4.63e-02

## Per-rank-span sensitivity

| rank span | n | median Δ | mean Δ | % Δ < 0 | p (less than 0) |
|---|---|---|---|---|---|
| 1 | 258 | -4.501 | -4.456 | 57.4% | 1.11e-02 |
| 2 | 176 | +0.653 | +7.088 | 48.9% | 8.37e-01 |
| 3 | 132 | +0.438 | +0.565 | 47.7% | 6.02e-01 |
| 4 | 119 | -3.760 | -12.796 | 57.1% | 5.09e-03 |
| 5 | 102 | -3.384 | -7.158 | 58.8% | 7.35e-02 |
| 6 | 90 | -5.765 | -7.575 | 58.9% | 1.96e-02 |
| 7+ | 364 | -1.077 | -5.971 | 53.6% | 2.43e-02 |