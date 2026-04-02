# Changelog

## v6 — 2026-04-02

### Semantic embeddings tested and null

Sentence-level cosine similarity (mxbai-embed-large) between each result's snippet embedding and the centroid of all prior result embeddings. Null within-position — same as bag-of-words. The priming hypothesis is now tested at three granularities (bag-of-words, semantic embeddings, within-position controls) and null at all of them.

### §9: Where relaxing the serial evaluation assumption helps

New findings section analyzing when non-serial SERP models add value. Acknowledges forced-choice inflation of regression rates, notes that at-scale regression prevalence (`click_rank < max_scroll_depth`) is unmeasured. Identifies three areas where complexity helps: position bias estimation, stop/regress/paginate decision, re-finding task metrics.

### Orientation time: 194ms median

Page orientation (time from page load to first fixation on any result) is 194ms median across all groups — consistent with a well-memorized SERP layout. Previously reported as ~1-3s from a regression intercept (a different metric).

### Lit review and references

11 new bibtex entries. Literature review on scroll regressions identifies 5 novelty claims. Key finding from the review: nobody has published the at-scale prevalence of `click_rank < max_scroll_depth` despite every search engine having this data.

## v5 — 2026-04-02

### Bug fix: FPOGY out-of-bounds clamp

The Gazepoint GP3 HD reports gaze Y coordinates that exceed screen boundaries. 24.5% of fixations have `FPOGY > screen_height` (1024px); the 95th percentile is 1830px. These out-of-bounds samples were added to scroll offset to compute page-space Y, attributing fixations to SERP positions below the visible viewport.

**Impact:** Position 9 dwell ratios were inflated by 3-50x per trial (mean 2.9×, 89% of trials >1.0). The aggregate dwell ratio for position 9 was 1.25 — now corrected to 0.79.

**Fix:** Clamp `FPOGY` to `[0, screen_height]` before computing `page_y = fy + scroll_offset` in `compute_fixation_per_result()`. Applied in `serp_priming.ipynb` (Cells 13, 16) and `fixation_coverage.ipynb` (Cell 3).

**Note for AdSERP users:** If you are working with the AdSERP fixation data and mapping gaze coordinates to page-space positions, always clamp or filter FPOGY to screen bounds first. The eye tracker does not constrain gaze reports to the application window.

**Other v5 changes:**
- Forward-only shape test ρ strengthened from +0.73 to +0.82 (positions 0-8)
- Dwell table in README and findings updated with corrected values

### New: Scroll kinematics analysis (`scroll_kinematics.ipynb`)

Tests the viewport mechanics confound hypothesis: does ballistic backward scrolling explain the apparent "priming during regressions" pattern?

**Results:**
- Backward scroll velocity > forward: median 915 vs 784 px/s, peak 1852 vs 1111 px/s
- Velocity profile is ballistic: ρ = 0.867 between distance-from-target and velocity
- 87.3% of regression targets are positions 0-4 (median: position 2)
- Regression velocity mediates the dwell delta: ρ = -0.762 (p = 0.017) across positions

Positions 6-8 are ballistic transit zones (high velocity, short viewport, suppressed fixations). The "priming during regressions" pattern is a viewport mechanics artifact.

### Prose cleanup: unsupported priming claims

Corrected language in README.md, TODO.md, findings.md, and adserp-key-claims.md that framed the regression-trial overlap correlation (r = -0.033) as evidence that "priming operates in re-evaluation." The signal is triply confounded:

1. **Position-overlap covariation** — within-position controls null (v3)
2. **Repetition/recognition** — revisiting already-read content produces shorter dwell (v4)
3. **Ballistic scroll kinematics** — high-velocity transit biases viewport time and fixation count (v5)

---

## v4 — 2026-04-01

### Bug fix: viewport time computation

The prior `compute_viewport_time` only counted time between scroll events. Pre-scroll periods (page load → first scroll) and post-scroll periods were dropped. Position 0 dwell ratios were >1.0 (up to 73×). Fixed by covering the full trial window. Position 0 dwell ratio corrected from 1.35 → 0.28.

### New: forward-only shape test

Isolating forward-scanning periods, gaze dwell ratio *increases* with position (ρ = +0.73), opposite the priming prediction. The aggregate priming correlation was entirely driven by regression artifacts.

### New: p(fixate | visible) analysis

Forward-only p(fixate) is ~99.8% at every position. Users fixate virtually everything during first-pass scanning. No skip decision for overlap to predict.

### Metric rename

"Eval rate" / "attention density" → "gaze dwell ratio" (fixation duration / visible duration).

---

## v3 — 2026-04-01

### Within-position controls

Testing high-overlap vs low-overlap at the same rank: null across all metrics (TFT, TFC, mean fixation duration, viewport time). The aggregate priming correlation (r = -0.054) was driven by the position-overlap confound.

---

## v2 — 2026-04-01

### Regression-stratified analysis

Aggregate effect concentrated in regression trials (r = -0.033), null in first-pass (r = -0.002). Initially reframed as "priming facilitates re-evaluation" — later shown to be confounded (v3-v5).

---

## v1 — 2026-04-01

### Initial analysis

- Lexical overlap builds rapidly down the SERP (62% by position 9)
- Aggregate priming correlation: partial r = -0.054 (p = 2.4×10⁻⁹)
- 69% scroll regression prevalence, mean 2.8 per trial
- Mouse-gaze convergence depends on click intent
- Viewport state predicts clicks better than distance (AUC 0.704 vs 0.548)
- Per-participant variance large (acquisition onset SD = 2.5s)
