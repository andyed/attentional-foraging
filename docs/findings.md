# Findings

Reanalysis of the AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). The [journey doc](journey.md) records how this started; this document records what we think we found.

**Status:** v1, 2026-04-01. Scroll-corrected coordinates applied. Priming × fixation duration tested.

---

## 1. Mouse-gaze distance is a function of click intent

The AdSERP paper reports a mean mouse-gaze distance of 372px. Conditioning on time-to-click (N=128,887 fixation-mouse pairs, 2,762 trials) reveals this aggregate mixes two regimes:

- **>10s before click:** Target is in the viewport ~50% of the time. Distance metric is measuring proximity to something often not on screen.
- **<10s before click:** Target increasingly in viewport. Distance drops monotonically.

With scroll-corrected page-space coordinates (v1), distance starts low (both gaze and mouse near top of page), increases as the user scrolls down, then converges sharply in the last few seconds. The convergence is more dramatic than the v0 uncorrected version suggested.

**Notebook:** convergence_analysis.ipynb

## 2. Scroll features beat distance for click prediction

Viewport state — target visible, time since scroll — predicts clicks better than mouse-gaze distance (AUC 0.704 vs 0.548). Distance-only baseline dropped from 0.631 (v0, uncorrected) to 0.548 (v1, corrected) — the distance signal was inflated by the coordinate mismatch. Scroll features were doing most of the work all along.

**Notebook:** convergence_analysis.ipynb

## 3. Scroll regressions are the dominant browsing pattern

69.1% of trials contain at least one scroll regression. Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Trials with regressions take 11.9s longer. Regression count correlates with decision time (r=0.660). Per-participant regression rates range from 11% to 98%.

**Notebook:** scroll_regressions.ipynb

## 4. Lexical overlap builds rapidly down the SERP

By position 9, 62% of a result's vocabulary has already appeared in prior results. Novel tokens per result drop from 28 to 10.

**Notebook:** serp_priming.ipynb

## 5. Lexical priming predicts evaluation speed

**This is the key result.** After controlling for position, cumulative lexical overlap predicts shorter fixation duration on that result.

| Measure | Value |
|---------|-------|
| Raw r (overlap × log fixation) | -0.117 (p < 10⁻⁴⁵) |
| Partial r (position-controlled) | **-0.043** (p = 1.2×10⁻⁷) |
| Within-position sign consistency | 8/9 positions negative |
| Strongest within-position effect | Position 9: r = -0.152 (p = 2.2×10⁻⁶) |
| Novel tokens × log fixation | +0.030 (p = 2.5×10⁻⁴) |

The partial correlation is the clean test: within the same rank, across ~2,700 different queries, results with higher lexical overlap with prior results receive shorter fixation. The effect strengthens at lower positions — exactly where cumulative priming is strongest.

Fixation duration by position confirms the base finding: 4,085ms at position 0 → 1,426ms at position 7 (65% reduction). The priming analysis offers an alternative to the standard "declining effort/attention" explanation: users evaluate faster because the vocabulary is increasingly redundant, not because they care less.

This is bag-of-words overlap. Semantic similarity (embeddings) would likely show a stronger effect.

**Notebook:** serp_priming.ipynb, Step 4

## 6. SERP-level homogeneity does not predict regressions

r = -0.015 (null). Regressions aren't driven by overall page homogeneity. The signal is likely local — a single high-novelty result triggering re-evaluation. Per-result novelty → next-regression event prediction is the right test.

**Notebook:** serp_priming.ipynb, Step 3

## 7. Individual differences are large

Per-participant acquisition onset ranges from 0.2s to 13.8s (SD=2.5s). Regression rates vary from 11% to 98% (SD=20.6%).

---

## Theoretical connections

The priming result connects to established frameworks:

- **Surprisal theory** (Hale 2001, Levy 2008): Processing difficulty proportional to information-theoretic surprise. Low-overlap results have high surprisal → longer fixation.
- **E-Z Reader** (Reichle, Rayner, Pollatsek): Regressions triggered by integration failure. A result that breaks the lexical pattern is an integration failure at the SERP level.
- **Given-new contract** (Clark & Haviland 1977): Processing fast when framed as "given" + incremental "new." Results with high overlap are mostly "given."

Whether the priming explanation has been proposed before for SERP evaluation speed is an open question. The position bias / trust bias literature (Craswell et al., Joachims et al.) attributes the speed-up to user trust in ranking quality, not to content redundancy.

---

## Caveats

### Forced-click task constraint (systematic)

The AdSERP participants were served SERPs via `localhost` in a controlled lab environment with transactional queries ("buy X"). Every trial ends with a click on a SERP result. This is a **forced-choice, single-task** design — no competing tabs, no address bar navigation, no query reformulation, no abandonment.

This constrains generalizability across all three notebooks:

| Finding | Effect of forced-click | What changes in the wild |
|---------|----------------------|--------------------------|
| **Convergence** | Mouse X variance is artificially low — the mouse has nowhere to go except toward results. In real browsing, attention splits across tabs, bookmarks bar, URL entry. The convergence signal is likely weaker and noisier. | Baseline divergence higher, convergence slope may be shallower |
| **Regressions** | Regression rate (69%) may be inflated — participants *must* find something satisfactory, so they re-evaluate more thoroughly than a user who might abandon and reformulate. | Regression rate probably lower in the wild; abandonment competes with regression |
| **Priming** | Priming effect should be robust — it depends on SERP content structure, not task constraints. But fixation durations may be longer than natural (forced thoroughness), compressing the variance that overlap needs to explain. | Effect direction holds; magnitude may change |

The findings describe the **underlying mechanisms** (priming, convergence dynamics, regression patterns) rather than the **base rates** (exact regression frequency, exact convergence timing). The mechanisms should transfer; the numbers are specific to this task design.

### Other caveats

- **Coordinate correction applied (v1):** Page-space fixations reconciled with screen-space mouse via scroll offset interpolation. v0 findings used uncorrected coordinates; absolute distance values were wrong, relative trends held.
- **Result boundary estimation:** Fixation-to-result mapping uses estimated Y boundaries (document height / N results). Without rendering the SERP HTML, exact pixel boundaries are unavailable. Misattribution at result boundaries adds noise.
- **Priming effect is small:** Partial r = -0.043. Real but modest at bag-of-words granularity. The effect may be larger with semantic similarity or when controlling for result relevance.
- **Priming is not the whole story:** Position bias, trust bias, and declining effort likely all contribute. Priming is an additional mechanism, not a replacement.
- **Literature survey incomplete:** Claims about novelty of the priming hypothesis are based on our reading, not an exhaustive review.

---

*v1, 2026-04-01. Updated from v0: scroll-corrected coordinates, priming × fixation duration analysis.*
