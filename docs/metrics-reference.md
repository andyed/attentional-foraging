# Metrics Reference

Canonical definitions for every metric used in this project. Each metric is grounded in prior art where it exists, or marked as novel with rationale. The goal: anyone reading our notebooks or a future paper can trace every number back to a precise definition and know how it relates to established measures.

## Conventions

- **Time origin (t₀):** Trial metadata timestamp (page load) or first recorded event, whichever is earlier
- **Position:** Zero-indexed result rank on the SERP (position 0 = top result)
- **Visible result:** A result whose top edge was below the viewport top at any point during the trial (i.e., scrolled into view or present in the initial viewport)
- **Fixated result:** A result that received ≥1 fixation (any duration)

---

## Eye-Tracking Metrics

### Fixation Duration (per fixation)
**Definition:** Duration of a single fixation event as reported by the eye tracker.
**Units:** Milliseconds.
**Prior art:** Standard eye-tracking measure. AdSERP uses Gazepoint GP3 HD at 150 Hz; fixation detection is built into the tracker firmware. Huang et al. (2012) used Tobii x50 at 50 Hz. Typical range 100-600ms for reading fixations.
**Our usage:** Raw input. Not directly reported — we aggregate to per-result totals.

### Total Fixation Time (TFT) per result
**Definition:** Sum of all fixation durations that fall within a result's estimated page-space Y band, using scroll-interpolated coordinates.
**Units:** Milliseconds.
**Prior art:** Called "Total Fixation Time" (TFT) in AdSight (Villaizán-Vallelado et al. 2025). Called "total fixation duration" in most CHIIR literature (Zhang et al. 2026, Table 2). Smith et al. (2016) and Teixeira Lopes & Ramos (2020) use the same operationalization.
**Our usage:** Primary evaluation measure in serp_priming.ipynb and fixation_coverage.ipynb. Conditioned on visibility in the decomposition analysis.
**Caveat:** Depends on result band estimation (approximate Y boundaries from document height and result count). AdSERP ad-boundary data could sharpen this.

### Total Fixation Count (TFC) per result
**Definition:** Number of distinct fixations within a result's Y band.
**Units:** Count.
**Prior art:** Called "Total Fixation Count" (TFC) in AdSight. Standard in eye-tracking literature.
**Our usage:** Used in decomposition to separate "how many times looked" from "how long each look."

### Mean Single-Fixation Duration per result
**Definition:** TFT / TFC for a given result. The average duration of one fixation on this result.
**Units:** Milliseconds.
**Prior art:** Reported in CHIIR literature as "average fixation duration." Typical values 200-300ms for text reading (Rayner 1998, Reichle et al. 1998).
**Our usage:** The decomposition finding: ~220ms across all positions, nearly flat. This is the per-fixation cognitive cost — invariant to position.
**Key insight:** Position-dependent decline in total fixation time comes from fewer fixations, not shorter ones.

### First Fixation Time (on result)
**Definition:** Timestamp of the first fixation within a result's Y band, relative to t₀.
**Units:** Milliseconds from page load.
**Prior art:** "Time to first fixation" is standard in eye-tracking. Kim et al. (2017) used it for SERP AOIs. Wu & Zhang (2020) measured it for Answer-Like results.
**Our usage:** The linear ramp in the decomposition: first_fix = orientation + β × position.

### Page Orientation Time
**Definition:** Time from page load (t₀) to first fixation on any SERP result.
**Units:** Milliseconds.
**Prior art:** Not a standard named metric in SERP literature. Huang et al. (2012) describe the 0-1s post-pageload period as an alignment phase where "gaze and cursor are closely aligned... perhaps from the previous action that led to the page." Mao et al. (2018) model a "skimming stage" that precedes evaluation. In our regression, this is the **intercept** of time-to-first-fixation ~ position.
**Our values:** FV clickers ~1619ms, scrollers ~2993ms.
**Note:** This is NOT the same as TTI (time to first interaction), which measures mouse/scroll behavior, not gaze. Orientation time is a gaze measure; TTI is a motor measure. They capture different things — the eye orients before the hand moves.

### Evaluation Scanning Rate
**Definition:** The slope of time-to-first-fixation ~ position. How many additional milliseconds per result position before first fixation arrives there.
**Units:** Milliseconds per position.
**Prior art:** Granka et al. (2004) established that scanning is roughly top-to-bottom. Lorigo et al. (2008) showed ~2/3 of scanpaths are nonlinear. Our linear regression is an approximation.
**Our values:** FV clickers ~2608ms/position, scrollers ~1730ms/position.

---

## Behavioral / Interaction Metrics

### Time to First Interaction (TTI)
**Definition:** Time from page load (t₀) to the first recorded mouse or scroll event.
**Units:** Milliseconds.
**Prior art:** "Time to interact" is a web performance metric (Google Lighthouse). In SERP research, not formally named but implicitly measured. Huang et al. (2012) show gaze-cursor alignment changing in the first seconds post-pageload.
**Our usage:** User-level calibrator for processing speed (r=0.77 with fixation time). Distinct from page orientation time — TTI is motor, orientation is gaze.

### TTI (first mousemove)
**Definition:** Time from t₀ to first mousemove event.
**Units:** Milliseconds.
**Our values:** Median ~1.7s for both FV and scrolled groups. Weakly predictive of evaluation speed (r=0.46).

### TTI (first scroll)
**Definition:** Time from t₀ to first scroll event.
**Units:** Milliseconds.
**Our values:** Median ~5.9s for scrollers. Strongly predictive (r=0.77). FV clickers have no scroll events by definition.
**Key insight:** Scrolling requires a decision ("I need to see more") — that decision latency reveals processing style.

### Time to Click (TTC)
**Definition:** Time from t₀ to the click event (final click in trial).
**Units:** Milliseconds.
**Prior art:** Standard. Called "task completion time" or "decision time" in various studies.
**Our values:** FV clickers median 11.4s, scrollers median 23.8s.

### Viewport Time per result
**Definition:** Total time a result was ≥50% visible in the viewport, computed from scroll event timeline using IAB viewability threshold.
**Units:** Milliseconds.
**Prior art:** IAB viewability standard (50% of pixels visible for ≥1 second). White, Diaz & Guo (2017) used viewport visibility for prefetching. AdSERP provides scroll events that enable this computation.
**Our usage:** Denominator for gaze dwell ratio (fixation_ms / viewport_ms). Separates "didn't look because it wasn't visible" from "didn't look because it wasn't interesting."
**v4 fix:** Prior computation only counted time between scroll events. Pre-scroll periods (page load → first scroll) and post-scroll periods were missing, severely undercounting viewport time for position 0 (dwell ratios were >1.0, some as high as 73x). Fixed to cover full trial window.

### Gaze Dwell Ratio
**Definition:** Total fixation duration on a result / total time that result was ≥50% visible. Both numerator and denominator are durations in ms; the ratio is dimensionless.
**Units:** Dimensionless ratio. Typical range 0.1–0.6; can exceed 1.0 at boundary positions (position 9) where viewport window is truncated by click.
**Prior names (deprecated):** "evaluation rate," "eval rate," "attention density," "gaze dwell fraction." All were imprecise — "rate" implies frequency, "density" implies spatial, "fraction" implies a 0–1 ceiling.
**Prior art:** Novel combination. Viewport-normalized fixation is not standard in CHIIR literature.
**Our usage:** serp_priming.ipynb step 4. Controls for exposure time when comparing evaluation across positions.

### Scroll Regression
**Definition:** An upward scroll gesture (net negative Y displacement ≥10px) within a scroll gesture segment (events separated by ≤200ms gap).
**Units:** Count per trial, or binary (has_regression).
**Prior art:** Analogous to reading regressions in eye-tracking (Rayner 1998). Applied to SERP scrolling in our scroll_regressions.ipynb. Not standard in SERP literature — most studies don't analyze scroll direction.
**Our usage:** User segmentation (satisfice/optimize) is based on regression rate across trials.

### Regression Rate (per user)
**Definition:** Fraction of a user's trials containing ≥1 scroll regression.
**Units:** Proportion (0-1).
**Prior art:** Novel. Conceptually related to Simon's satisficing (1956) — users with low regression rates accept early results; high regression rates indicate exhaustive comparison.
**Our values:** Range 0%–98% across 47 participants. Tercile split: satisficers ≤47%, optimizers >70%.

---

## Content Metrics

### Cumulative Lexical Overlap
**Definition:** For result at position p, the fraction of its content tokens (lowercased, stopwords removed) that appeared in any result at positions 0 through p-1.
**Units:** Proportion (0-1).
**Prior art:** Bag-of-words overlap is standard in NLP. Applied to SERP result sequences: novel. Related to information-theoretic surprisal (Hale 2001, Levy 2008) — high overlap = low surprisal = lower processing cost.
**Our values:** Rises from 0% at position 0 to ~62% at position 9.

### Novel Tokens per result
**Definition:** Count of unique content tokens in a result that did not appear in any prior result.
**Units:** Count.
**Our values:** Drops from ~28 at position 0 to ~10 at position 9.

---

## Production / Applied Metrics (not in academic literature)

*Reserved section for metrics from at-scale production systems and personal research. These bridge the gap between lab measurement and deployed systems.*

### Click-Through Rate by Position (CTR@k)
**Definition:** Probability of clicking the result at position k, across all impressions where position k was visible.
**Units:** Proportion.
**Context:** Standard in search engine evaluation. The position-dependent CTR curve is the production analog of our fixation-time-by-position curve. Key difference: CTR is a binary outcome (clicked/not), fixation is continuous (how long).
**Source:** Production search logs at Bing, Google, etc. Published in aggregate by Craswell et al. (2008) as position-bias models.

### p(click | mouse-gaze distance)
**Definition:** Probability of clicking a result conditioned on the distance between mouse cursor and gaze at the moment of the click approach.
**Units:** Conditional probability.
**Context:** From the convergence analysis (notebook 1). Not a standard metric — novel to this project.

<!-- 
PLACEHOLDER: Andy to add production metrics (Quora/Poe, eBay, etc.) 
and personal research metrics (clicksense down-up latency, etc.)
-->

---

## Decomposition Summary

The old framing conflated multiple processes into "fixation time by position":

| Component | What it measures | Position-dependent? | Metric |
|-----------|-----------------|-------------------|--------|
| **Page orientation** | Time to begin evaluating any result | No (fixed cost) | Intercept of first-fix ~ position regression |
| **Scanning arrival** | When evaluation reaches position p | Yes (linear ramp) | Slope of first-fix ~ position regression |
| **Number of fixations** | How many times a result is looked at | Yes (declines) | TFC per result |
| **Per-fixation duration** | Cognitive cost of one reading fixation | **No (~220ms, flat)** | TFT / TFC |
| **Total evaluation** | Aggregate time on a result | Yes (product of count × duration) | TFT per result |
| **Visibility** | Was the result ever on screen? | Yes (structural) | Viewport time > 0 |

The key finding: **per-fixation duration is position-invariant.** The position-dependent decline in total fixation time comes entirely from fewer fixations at lower positions, not shorter ones. This matters for the priming hypothesis — if priming reduces processing cost, it should show up in per-fixation duration, not just total fixation time.

---

*Last updated: 2026-04-01*
