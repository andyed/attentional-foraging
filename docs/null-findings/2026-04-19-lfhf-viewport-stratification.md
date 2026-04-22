# LF/HF × viewport stratification — position survives, viewport is rank-confounded

**Date:** 2026-04-19
**Script:** `scripts/lfhf_viewport_stratification.py`
**Output:** `scripts/output/lfhf_viewport_stratification/summary.json`
**Regime:** `[LAB]`

## Why this was run

The 2026-04-19 ETTAC brief leads with **position** as the organizing axis of
the LF/HF gradient (framework compilation by rank). Peter Dixon-Moses's
viewport feedback (2026-04-19) proposed that much of what we attribute to
rank may actually stratify by viewport position (visible vs scrolled-past).
That is a load-bearing alternative — if LF/HF is actually viewport-mediated,
the brief's interpretation would need a rewrite before being sent to
Duchowski.

Test: partial-correlation disambiguation on a new per-(trial, position)
viewport feature table joined to NB14's per-(trial, position) LF/HF.

## Data

- **LF/HF:** `../pupil-lfhf/validation/butterworth-lfhf-by-position.json`
  (6,112 records).
- **Viewport+trajectory features:** `AdSERP/data/viewport-trajectory-features.json`
  (27,760 records; 14 features per (trial, position) covering bands,
  continuous viewport analytics, and scroll trajectory; producer script:
  `scripts/build_viewport_trajectory_features.py`, extractor lifted verbatim
  from `nb30_scroll_trajectory.compute_features_for_trial`).
- **Join:** inner on `(trial_id, position)` → **6,062 records**.

## Headline results

### Steep phase P0–P3 (ETTAC-critical; N = 4,229)

| Measure | Pooled ρ (p) | Partial ρ \| position (p) | Partial ρ \| avg_viewport_y (p) |
|---|---:|---:|---:|
| position             | −0.1437 (5.9 × 10⁻²¹) | — | **−0.0975** (2.1 × 10⁻¹⁰) |
| avg_viewport_y       | −0.1068 (3.3 × 10⁻¹²) | **+0.0126** (0.41) | — |
| vt_any (ms visible)  | +0.0933 (1.2 × 10⁻⁹)  | **+0.1109** (4.7 × 10⁻¹³) | — |
| vt_center_ms         | −0.0308 (0.045)       | +0.0094 (0.54) | — |

- **Position survives partialling on avg_viewport_y** (ρ = −0.098, *p* = 2.1 × 10⁻¹⁰).
- **Avg_viewport_y collapses when controlled for position** (ρ = +0.013,
  *p* = 0.41). The pooled avg_viewport_y effect was the position gradient
  in disguise.
- **vt_any strengthens on partialling** (ρ = +0.111, *p* = 4.7 × 10⁻¹³).
  Longer time visible → higher LF/HF, independent of rank. This is a new
  positive finding, not a confound.
- **Position survives joint partialling on all three viewport features**
  (ρ = −0.099, *p* = 9.8 × 10⁻¹¹).

### Full range P0–P10 (N = 6,062)

| Measure | Pooled ρ (p) | Partial ρ (p) |
|---|---:|---:|
| position \| avg_viewport_y                  | — | −0.1416 (p ≈ 0) |
| avg_viewport_y \| position                  | — | +0.0193 (0.13) |
| vt_any \| position                          | — | +0.0920 (7 × 10⁻¹³) |
| vt_center_ms \| position                    | — | −0.0013 (0.92) |
| position \| {avy, vt_any, vt_center}        | — | −0.0986 (1 × 10⁻¹⁴) |

Same pattern at full range. Position survives; avg_viewport_y is
rank-confounded; vt_any adds independent positive signal.

### Plateau P4–P10 (N = 1,833, qualified)

Pooled effects are weaker. Position partial is ρ = −0.062 (*p* = 0.008).
Avg_viewport_y partial is ρ = +0.055 (*p* = 0.019) — here viewport has
**marginal independent signal**, and position collapses when all three
viewport measures are jointly controlled (ρ = −0.027, *p* = 0.25). Consistent
with the plateau audit (`2026-04-19-nb14-plateau-concentration-audit.md`):
the plateau is sparse and noisy; both rank and viewport effects become
marginal at depth.

### Per-tercile sweep (pooled P0–P10)

Split rows by avg_viewport_y tercile, then compute ρ(position, LF/HF median)
within each bin:

| Tercile (avg_viewport_y) | N | ρ(position, LF/HF median) |
|---|---:|---:|
| Low (<481 px)     | 2,021 | −0.406 (10 positions) |
| Mid (481–733 px)  | 2,020 | −0.905 (8 positions)  |
| High (>733 px)    | 2,021 | −0.667 (8 positions)  |

Position gradient persists inside every viewport-y tercile. Direct evidence
the effect is not a hidden viewport gradient.

## Verdict

> **POSITION WINS — ETTAC brief stands.**
> The LF/HF-by-rank story is not viewport-mediated in the steep phase. The
> partial-on-viewport correlation attenuates the rank effect by ≈ 32 %
> (ρ_pool = −0.144 → ρ_partial = −0.098), but the residual is
> robust (*p* = 2.1 × 10⁻¹⁰). Avg_viewport_y contributes **zero** independent
> signal on the steep phase (*p* = 0.41).

## New finding: vt_any independent positive effect

The time an AOI spends visible in the viewport (`vt_any`) has a positive
independent effect on LF/HF after partialling on position
(ρ = +0.111, *p* = 4.7 × 10⁻¹³ on P0–P3; +0.092, *p* = 7 × 10⁻¹³ full range).
This is a new positive-finding candidate — longer dwell on visible content
indexes higher cognitive load, independent of rank. Consistent with the
framework-compilation reading: once the framework is compiled at a given
rank, additional fixated viewport time pushes load back up.

## Implication for ETTAC brief

1. Brief language on framework compilation by rank **stays**.
2. Add one sentence on viewport disambiguation as a robustness check.
3. Optional: the `vt_any | position` finding is a defensible small addition
   to the brief's dissociation story — cognitive load decreases with rank
   (framework compilation) but increases with dwell time at a given rank
   (ongoing evaluation effort). This is consistent with the
   content-crossover null: LF/HF indexes position on the evaluation surface,
   not content complexity, and now also scales with visible-time at position.

## Filing

Clean positive result on the primary disambiguation; no brief rewrite
needed. Supplementary `vt_any | position` finding is a candidate addition.
Filed alongside the 2026-04-19 ETTAC audit family.
