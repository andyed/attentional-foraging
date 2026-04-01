# Findings

Preliminary findings from reanalysis of the AdSERP dataset. These are first-pass observations from a single session. The [journey doc](journey.md) records how we got here; this document records what we think we found.

**Status:** v0, 2026-04-01. Coordinate correction not yet applied (see Caveats below).

---

## 1. Mouse-gaze distance is a function of click intent

The AdSERP paper reports a mean mouse-gaze distance of 372px. Conditioning on time-to-click (N=128,887 fixation-mouse pairs, 2,762 trials) reveals this aggregate mixes two regimes:

- **>10s before click:** Target is in the viewport ~50% of the time. Distance metric is measuring proximity to something often not on screen — an abstract "distance to goal," not a spatial relationship.
- **<10s before click:** Target increasingly in viewport. Distance drops monotonically from ~330px to ~172px at 1-2s before click.

We haven't exhaustively surveyed whether prior work has conditioned mouse-gaze distance on click intent. If it hasn't been done, the finding is that the aggregate conflates two different signals.

**Notebook:** convergence_analysis.ipynb, Plots 1, 10

## 2. Eye movements coordinate scrolling

The convergence signal is downstream of viewport state. When the viewport is settled, distance shows a clean ramp. During active scrolling, distance stays flat and high. Viewport features (target visible, time since scroll, scroll velocity) boost click prediction AUC from 0.631 to 0.704.

The deeper question: how does gaze drive scroll behavior? The eye finds a candidate peripherally or through scanning, the hand scrolls to bring it into comfortable viewing position, evaluation begins. The scroll-stop event marks the transition from foraging to evaluation.

**Notebook:** convergence_analysis.ipynb, Plots 10-11

## 3. X and Y divergence tell different stories

On vertical SERP layouts, horizontal (X) divergence dominates during scanning — the mouse parks to the side while the eye reads down. Near click, the vertical (Y) component catches up. The Y/X ratio flips from 0.73 (scanning) to 1.12 (click), suggesting a vertical verification check before commitment.

**Notebook:** convergence_analysis.ipynb, Plot 2b

## 4. Scroll regressions are the dominant browsing pattern

69.1% of trials contain at least one scroll regression (scrolling back up). Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Trials with regressions take 11.9s longer. Regression count correlates with decision time (r=0.660). Per-participant regression rates range from 11% to 98%.

This page-level behavior — analogous to fixation regressions in the reading literature — appears undercharacterized relative to its prevalence.

**Notebook:** scroll_regressions.ipynb

## 5. Lexical overlap builds rapidly down the SERP

By position 9, 62% of a result's vocabulary has already appeared in prior results. Novel tokens per result drop from 28 to 10.

Prior work reports users evaluate results faster as they scroll down, typically attributed to declining effort or attention. An alternative explanation: cumulative lexical priming reduces the cognitive cost of evaluation. Whether overlap actually mediates evaluation speed — rather than merely covarying with position — requires linking per-result overlap to per-result fixation duration. This is our most interesting open question.

SERP-level homogeneity does not predict scroll regressions (r=-0.015). If regressions are triggered by content, the signal is likely local (a single novel result) rather than global.

**Notebook:** serp_priming.ipynb

## 6. Individual differences are large

Per-participant acquisition onset ranges from 0.2s to 13.8s (SD=2.5s). Regression rates vary from 11% to 98% (SD=20.6%). Any model of SERP browsing behavior needs to account for this variance.

**Notebook:** convergence_analysis.ipynb Plot 4, scroll_regressions.ipynb

---

## Caveats

- **Coordinate mismatch:** Fixation data is in page-space (gaze Y exceeds screen height during scrolling). Mouse data is in screen-space. Scroll offset is available but not yet applied to reconcile them. Absolute distance values are approximate. Relative trends and scroll-state conditioning are robust because the mismatch is roughly constant within scroll states.
- **Priming is correlational:** We show lexical overlap increases with position. We have not yet shown it mediates evaluation speed. The link from overlap → fixation duration → behavioral outcome is the critical test.
- **Regression triggers unknown:** We know regressions are common and scale with decision time. We don't yet know what triggers them — local novelty is a hypothesis, not a finding.
- **Literature survey incomplete:** Claims about what has/hasn't been studied are based on our reading, not an exhaustive review.

---

*First pass, 2026-04-01.*
