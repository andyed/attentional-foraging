# PAI vs binary exposure — does PAI add information over point-in-AOI metrics?

**Tags:** `[LAB, AdSERP, organic_hybrid]`
**Producer:** `scripts/pai_exposure_ablation.py` → `scripts/output/ablations/pai_exposure_ablation.json`
**Generated:** 2026-08-18 (direct answer to Duchowski's 2026-08-17 ask)

## Question

Duchowski (email, 2026-08-17): *"The key to doing so would be to somehow
show that the PAI provides additional info over traditional
gaze-point-in-AOIs metrics."* Operationalized on the control-ladder
harness: does PAI-weighted soft AOI exposure improve click prediction
(LOSO AUC) and result ranking (MRR@10 / NDCG@1) beyond per-AOI binary
fixation dwell — the grid's `total_dwell_ms`, in which each fixation is
assigned to exactly one AOI by point-in-band bisection?

## Setup

- **Records:** the published buf500 grid population (19,848 (trial, AOI)
  records, 2,589 clicks, 2,774 trials, 47 participants) and the
  truncation-grid excision population (18,919 records) — identical to
  `viewport_exposure_ablation.py`. PAI coverage 2,774/2,774 trials
  (100.0%), 0 records dropped.
- **PAI channel:** every fixation contributes soft mass to *every* AOI
  via the exact delivered-demo formula (verified against
  `glias2poly_1920x1080.py`): α = clip(1 − √(OGD/max(CGD,1))·w_A, 0, 1),
  w_A = (A_max/A)^φ³, OGD = exact rectangle-boundary distance (0 inside).
  - `pai_dwell_ms` = Σ d·α (total soft mass)
  - `pai_periph_ms` = Σ d·α over strictly-outside fixations only — the
    component binary point-in-AOI assignment **cannot see, by
    construction**.
  - Sensitivity form `α35` = clip(1 − OGD/CGD, 0, 1) (NB35 abstract-only
    form: no area weight, no √) → `pai35_periph_ms`.
- **Geometry:** organic_hybrid bands extruded to the result column
  x-extent [162, 702], so `position` indexes match the grid exactly.
- **Conditions:** buf500 (t < t_click − 500 ms) and the committed-
  approach excision (t < t_onset, timestamps verbatim from
  `approach_truncation_trial_stats.json`).
- **Protocol:** 47-fold LOSO logistic regression, StandardScaler,
  balanced class weights, C = 1.0 — identical to the grid.
- **Anchor — PASS:** recomputed buf500 M2 AUC 0.7636 vs published
  0.7636, |diff| = 0.0000 ≤ 0.002.

## Ladder (LOSO AUC / MRR@10)

| Model | Features | buf500 AUC | buf500 MRR | excision AUC | excision MRR |
|---|---|---|---|---|---|
| D1 | total_dwell_ms (1) | 0.7616 | 0.669 | 0.6980 | 0.616 |
| P1 | pai_dwell_ms (1) | 0.7549 | 0.629 | 0.6954 | 0.589 |
| Pp1 | pai_periph_ms (1) | 0.6548 | 0.500 | 0.6157 | 0.502 |
| M1 | position (1) | 0.6679 | 0.464 | 0.6749 | 0.478 |
| M2 | position + dwell | 0.7636 | 0.623 | 0.7249 | 0.552 |
| M2-PAI | position + pai_dwell | 0.7523 | 0.569 | 0.7174 | 0.515 |
| **M2+Pp** | M2 + pai_periph | 0.7688 | 0.645 | **0.7323** | **0.573** |
| **M2+Pp35** | M2 + pai35_periph | 0.7803 | 0.644 | **0.7468** | **0.577** |
| M3-7 | M2 + 7 cursor geometry | 0.8463 | 0.739 | 0.7532 | 0.616 |
| M3-7+Pp | M3-7 + pai_periph | 0.8484 | 0.743 | 0.7582 | 0.623 |
| M4-7 | 7 geometry alone | 0.8468 | 0.741 | 0.7328 | 0.626 |

## Paired per-fold stats (47 folds; Wilcoxon two-sided, Cohen's d_z, bootstrap 95% CI)

| Comparison | ΔAUC | 95% CI | d_z | Wilcoxon p |
|---|---|---|---|---|
| **M2+Pp vs M2, excision** | **+0.0061** | [+0.0015, +0.0108] | +0.36 | **1.3e-02** |
| M2+Pp vs M2, buf500 | +0.0019 | [−0.0024, +0.0063] | +0.12 | 5.7e-01 |
| **M2+Pp35 vs M2, excision** | **+0.0162** | [+0.0091, +0.0239] | +0.63 | **2.4e-05** |
| M2+Pp35 vs M2, buf500 | +0.0056 | [−0.0014, +0.0126] | +0.23 | 1.3e-01 |
| **M3-7+Pp vs M3-7, excision** | **+0.0033** | [+0.0007, +0.0057] | +0.37 | **6.5e-03** |
| M3-7+Pp vs M3-7, buf500 | −0.0000 | [−0.0014, +0.0013] | −0.00 | 5.5e-01 |
| M2-PAI vs M2, buf500 | −0.0165 | [−0.0226, −0.0104] | −0.77 | 2.6e-06 |
| M2-PAI vs M2, excision | −0.0114 | [−0.0154, −0.0074] | −0.81 | 2.0e-06 |
| P1 vs D1, buf500 | −0.0074 | [−0.0145, −0.0005] | −0.30 | 4.3e-02 |
| P1 vs D1, excision | −0.0040 | [−0.0115, +0.0031] | −0.16 | 2.3e-01 |
| Pp increment, buf500 vs excision | −0.0042 | — | — | 8.3e-04 |

## Reading

1. **PAI adds information over traditional point-in-AOI metrics — as a
   complement, not a replacement.** The peripheral-only channel
   (`pai_periph_ms`), which binary assignment cannot represent at all,
   adds +0.0061 AUC over position+dwell under excision (p = 0.013) and
   +0.0033 over the *full seven-feature cursor-geometry model*
   (p = 0.0065). Ranking improves too: MRR@10 0.552 → 0.573, NDCG@1
   0.327 → 0.367 (M2 → M2+Pp, excision).
2. **The added information is pre-decision, not decision leakage.** The
   Pp increment is *larger* after committed-approach excision than at
   buf500 (+0.0061 vs +0.0019; paired difference p = 8.3e-04) — the
   opposite profile of cursor hover (which collapses −0.19 under
   excision). Peripheral soft exposure behaves like early-scan
   parafoveal information: it becomes *more* valuable exactly when the
   mechanically-leaky terminal approach is removed. This is the
   strongest framing for the ETRA argument: PAI's increment survives —
   indeed concentrates under — the leakage control that guts the
   channels traditional metrics lean on.
3. **Soft assignment should not replace binary assignment.** Swapping
   `pai_dwell_ms` in for `total_dwell_ms` *loses* AUC (−0.011 to −0.017,
   both p < 1e-5): blurring foveal assignment discards which result was
   actually read. PAI's value is the skirt, not the smoothing — report
   binary + peripheral, not soft-instead-of-binary.
4. **Functional-form sensitivity favors the wider skirt.** The NB35
   abstract-only form (α = 1 − OGD/CGD, no √, no area weight) carries
   *more* incremental signal than the exact demo form (+0.0162 vs
   +0.0061 under excision). The √ compresses the long-range skirt; for
   *predictive* use, longer-range peripheral mass is more informative.
   Worth flagging to Duchowski as a design observation, not a
   correction — his form is tuned for visualization opacity, not
   prediction.

## Caveats

- **Conservative by construction:** the grid population only contains
  (trial, AOI) records with ≥1 binary-assigned fixation (0 zero-dwell
  records), so PAI's orphan-recovery advantage (NB35 Q1: fixations
  binary assignment drops entirely) cannot contribute here. An
  all-AOI-slots population would likely widen the increment; that is a
  separate, additive analysis.
- **Geometry:** column-rect extrusion of the hybrid bands (x ∈
  [162, 702]) rather than true snippet bboxes; contiguous vertical
  bands mean most peripheral mass lands on adjacent results
  (parafoveal preview up/down the list). Real bbox geometry (the .ias
  export path) is the natural refinement.
- **α values are implementation-specific** (boundary OGD; delivered-demo
  formula). Rank-order conclusions are robust to monotone reshaping;
  absolute α magnitudes are not.
- `[LAB]`-only; click prediction is within-SERP. No WILD analog exists
  (peripheral gaze requires an eye tracker by definition).

## Verdict

**Supported.** PAI provides statistically reliable additional
information over traditional gaze-point-in-AOI metrics on AdSERP — the
strictly-peripheral soft-membership mass improves click prediction and
ranking beyond binary dwell (and beyond the full cursor-geometry
model) under the deliberation-leakage control, where the increment is
largest. The right claim for the ETRA short paper: *binary AOI metrics
miss peripheral exposure entirely; PAI recovers it, and that recovered
component is predictive precisely in the leakage-robust, pre-decision
regime.*
