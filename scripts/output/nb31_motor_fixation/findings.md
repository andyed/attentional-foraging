# NB31 — Motor-event → fixation-location findings

**Date:** 2026-04-19
**Source:** Peter Dixon-Moses Slack thread 2026-04-19 (four predictions).
**Dataset:** AdSERP LAB, 2,775 usable trials, median viewport 1,024 px.
**Method:** Find the next fixation within 1 s of each motor event; compute fixation viewport-y as a fraction of `scr_h`; aggregate.

## Results

### Test 1 — Scroll event → fixation at viewport bottom?

**Falsified.** After *any* scroll event, the next fixation is predominantly in the **upper half** of the viewport.

| Statistic | Value |
|---|---:|
| N events with valid next-fix | 272,150 |
| Mean fix viewport-y (as fraction of `scr_h`) | **0.410** |
| Median fix viewport-y | 0.418 |
| % in top third | **35.9 %** |
| % in bottom third | 10.0 % |
| One-sample Wilcoxon (fix > 0.5 of `scr_h`) | p = 1.0000 |

Interpretation: reading is top-down, so scrolling brings new content into view and the user re-orients to the *top* of the new viewport to continue examining. Peter predicted fixation at the bottom (where new content appears during downward scroll); the data show the opposite.

### Test 2 — Large scroll → fixation moves back toward top?

**Partially supported with a reversal at the extreme tails.** Bins ordered by signed scroll delta:

| Bin (px) | N | Mean fix vp-y | Median |
|---|---:|---:|---:|
| (−∞, −200) | 14 | 0.679 | 0.931 |
| (−200, −50) | 6,342 | **0.216** | **0.184** |
| (−50, +50) | 262,273 | 0.414 | 0.422 |
| (+50, +200) | 3,505 | 0.479 | 0.487 |
| (+200, +∞) | 16 | 0.649 | 0.740 |

The strongest signal is in the modest up-scroll bin (−200 to −50 px, N = 6,342): fixation lands at vp-y = 0.18 — deep in the top third. That is the regression pattern Peter predicted. The extreme tails (|Δ| > 200 px) reverse direction but are noise (N = 14 and 16); they cannot be read as supporting "large scroll → top." Mann-Whitney in the predicted direction fails (p = 0.99) because of the tail reversal.

### Test 3 — Scroll regression → fixation at viewport top?

**Strongly confirmed.** This is the cleanest result in the set.

| Statistic | Value |
|---|---:|
| N scroll-regression events (Δ < −30 px) with valid next-fix | 15,413 |
| Mean fix viewport-y | **0.223** |
| Median fix viewport-y | 0.192 |
| % in top third | **80.5 %** |
| % in bottom third | 2.1 % |
| One-sample Wilcoxon (fix < 0.5 of `scr_h`) | ***p ≈ 0*** |

80 % of post-regression fixations land in the top third of the viewport. Scroll-back is an epistemic action: the user scrolls up specifically to re-access content that had scrolled off the top, and fixation goes there.

### Test 4 — Mouse event → fixation co-located with mouse y?

**Null.** Page-space offset `|fix_y − mouse_y|` is not smaller at the nearest fixation in time than at a random fixation in the same trial.

| Statistic | Value |
|---|---:|
| N events sampled | 230,749 |
| Median |fix_y − mouse_y| (nearest) | 416 px |
| Median |fix_y − mouse_y| (random baseline) | 389 px |
| Ratio (actual / random) | **1.07** |
| Mann-Whitney (actual < random) | p = 1.0000 |

The nearest-in-time fixation is not closer to the mouse than a random one in the same trial — if anything, slightly farther. This is consistent with the cursor-gaze coupling literature's established finding that coupling is *episodic* (brief, phase-dependent moments of co-location) rather than *pervasive*. Huang & Diriye-style coupling shows up in per-episode alignment tests, not in a blanket "every mouse event has a fixation at the same y."

## Summary for Peter

| Prediction | Status | Headline |
|---|---|---|
| Scroll → fix at bottom | Falsified | Fix lands at mid-upper (0.41), 35.9 % in top third. Reading orientation dominates. |
| Large scroll → fix toward top | Partially supported | Modest up-scrolls (N = 6,342) → top (0.18); extreme tails noisy. |
| Scroll regression → fix at top | **Strongly confirmed** | 80.5 % of post-regression fixations in top third (p ≈ 0). |
| Mouse event → fix at mouse y | Null | Same-trial random baseline is as close. Coupling is episodic, not event-level. |

The regression → top-fix finding (Test 3) is the publishable headline — a clean 80 % concentration in the predicted region with N = 15,413 events. It operationalizes "scroll-back is a re-read action" at the single-event level, grounds the NB22 gaze-regression four-class taxonomy behaviorally, and complements §4.5's viewport-dynamics framing (the EWM reload fingerprint).

## Pointers

- Script: `scripts/nb31_motor_event_fixation.py`
- Numeric dump: `scripts/output/nb31_motor_fixation/summary.json`
- Related NB17 scroll-regression detection (threshold tuning): `notebooks-v2/17_scroll_retreat.ipynb`
- NB22 gaze-regression label definition: `notebooks-v2/22_four_class_taxonomy.ipynb`
