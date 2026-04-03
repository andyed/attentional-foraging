# Regression Decisions — Literature Review Summary

*From external lit review, 2026-04-02.*

## What exists

| Paper | Finding | Gap our work fills |
|---|---|---|
| **Lorigo et al. JASIST 2008** | ~66% nonlinear scanpaths on SERPs | Our 69% confirms across 17 years; we add scroll-level quantification (magnitude, timing, kinematics) |
| **Azzopardi & Maxwell (IFT stopping models)** | Model SERP-level stopping decisions | Single-pass assumption — don't model within-page re-evaluation. Our regressions break this. |
| **Liu et al. CIKM 2014** | Two-stage model: skim → read | Needs a third stage: **re-evaluate**. Our confirmation/rejection split on revisit characterizes it. |
| **RecGaze, SIGIR 2025** | Carousel analog — horizontal scroll regressions | Same behavioral pattern in a different UI paradigm. Cross-validates. |
| **eyeScrollR, BRM 2024** | Validates scroll-correction methodology for eye tracking | Confirms our approach to coordinate correction. |
| **Chuklin et al. (click models)** | Assume monotonic examination (top-to-bottom, single pass) | Our data breaks monotonic assumption — 69% of trials are non-monotonic. |

## What's novel (not in the literature)

1. **Within-page re-evaluation modeling** — MVT/IFT model patch-leaving but not patch-revisiting. We show regressions serve two distinct functions: confirmation (to the winner, +32% fixations) and rejection (of alternatives, -17% fixations). This is a new behavioral decomposition.

2. **Spatial memory precision for SERP positions** — η²=0.87 for position-specific scroll targeting, but landing precision ≈ random baseline. Region-level spatial memory with salience weighting (click target remembered ~1.8x better). No prior work on SERP spatial memory at this granularity.

3. **Ballistic scroll kinematics as methodological confound** — Backward velocity > forward (915 vs 784 px/s), ballistic profile (ρ=0.87). Nobody has reported the velocity asymmetry or its implications for dwell ratio analysis during regressions. This is a methods contribution.

4. **LHIPA × foraging depth × satisficing** — Three-way connection: trial-level LHIPA decreases with click position (ρ=-0.90), regression rate correlates with LHIPA (ρ=-0.55), optimizers click higher not deeper. Each pair may exist in isolation in the literature; the triangle is new.

5. **Regression as alternative to abandonment** — Forced-choice reveals what naturalistic search hides: when users can't abandon, they regress. The 69% regression rate is the behavioral cost of forced commitment. Connects to Diriye et al. 2012 (abandonment) and Bruckner et al. 2020 (query abandonment prediction) as the other side of the decision.

## Papers to acquire

- **Azzopardi & Maxwell** — IFT stopping models (need specific citation)
- **Liu et al. CIKM 2014** — two-stage skim→read model
- **RecGaze SIGIR 2025** — carousel scroll regressions
- **eyeScrollR BRM 2024** — scroll-correction validation
- **Chuklin et al.** — click model survey (monotonic examination assumption)

## Framing for the paper

The existing literature models SERP examination as a **single forward pass** with a **stopping decision**. Our contribution: examination is a **multi-pass process** with distinct cognitive phases (orientation → evaluation → working memory accumulation → regression/commitment), and the regression decision is where the interesting cognitive work happens — not at the stopping point, but at the *re-evaluation* point.

The forced-choice paradigm makes regressions visible that would be hidden as abandonment in naturalistic search. This is a feature, not a limitation: it isolates the foraging-to-exploitation transition.
