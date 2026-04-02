# Findings

Reanalysis of the AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). The [journey doc](journey.md) records how this started; this document records what we think we found.

**Status:** v3, 2026-04-01. Within-position controls show bag-of-words overlap effect does not survive position confound. Evaluation time decomposed into orientation, scanning rate, fixation count, and per-fixation duration. Honest corrections throughout.

---

## Theoretical framework: The Attentional-Foraging Equilibrium

These findings are interpreted through the **Attentional-Foraging Equilibrium (AFE)** — a framework synthesizing Rational Inattention (Sims 2003) with Information Foraging Theory (Pirolli & Card 1999). The core equation: **ρ = V / (τ + T_s + σ²)**, where V = expected value, τ = handling time, T_s = travel time between patches, σ² = uncertainty. The user leaves a patch when ρ falls below threshold.

How each finding maps to AFE:

- **Lexical priming** (Finding 2) — bag-of-words overlap correlates with faster evaluation in aggregate, but the effect does not survive within-position controls. The position-overlap confound remains unresolved. Finer-grained measures (semantic embeddings, token-level fixation analysis) may be needed to detect the mechanism.
- **Scroll regressions** (Finding 4) are travel costs (T_s) paid for re-evaluation when a novel result disrupts the reward rate estimate.
- **Mouse-gaze convergence** (Finding 5) traces the transition from foraging (high T_s, moving between patches) to exploitation (low τ, evaluating within a patch).
- **Per-participant variance** (Finding 7) maps to bandwidth λ — individual cognitive capacity differences.
- The **forced-choice purchase task** creates a defined stopping criterion that makes the patch-leaving decision observable. Most SERP studies use open-ended tasks where the user can leave without clicking.

Full presentation: [The Attentional-Foraging Equilibrium](https://gamma.app/docs/The-Attentional-Foraging-Equilibrium-A-Synthesis-of-Digital-Behav-aq0bw2ujjxwypbt)

---

## Dataset constraints

Two major caveats versus generalized SERP behavior. These pervade all findings.

**1. Forced choice with optimizing intent.** Participants were instructed to "click on the item they would typically choose" for product purchase queries, with up to 1 minute per trial and a confirmation step. Every trial ends with a click — no abandonment, no query reformulation. This is optimizing behavior ("what would I actually buy?"), not satisficing ("is this good enough?"). The 69% regression rate and thorough evaluation patterns reflect this constraint.

**2. Limited X-axis variation.** SERPs were served via localhost in a controlled lab environment. No competing browser chrome, no tabs, no bookmarks bar, no address bar. Mouse position variance is artificially constrained compared to real browsing where attention splits across the full browser window.

**Bottom line:** The findings describe underlying mechanisms (priming, convergence, regression patterns), not base rates. The mechanisms should transfer to real SERP behavior; the exact numbers are specific to this task design.

---

## 1. Lexical overlap builds rapidly down the SERP

By position 9, 62% of a result's vocabulary has already appeared in prior results. Novel tokens per result drop from 28 to 10. This is a content-structural fact, independent of behavior.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 2

## 2. Overlap correlates with evaluation speed — but does not survive within-position controls

**v3 correction: the aggregate priming effect is confounded with position.**

We initially reported that cumulative lexical overlap predicted faster evaluation (attention density), especially in regression trials. The aggregate correlations were:

| Analysis | Partial r | p | N |
|----------|-----------|---|---|
| All trials, positions 1-9 | -0.054 | 2.4×10⁻⁹ | 12,121 |
| Regression trials, positions 1-7 | -0.033 | 0.003 | 8,342 |
| No-regression trials, positions 1-9 | -0.002 | 0.92 | 2,640 |

**The problem:** Position and overlap are confounded — both increase monotonically down the SERP. The aggregate correlations could reflect position-dependent attention decline rather than a content-driven priming effect.

**The within-position test:** For each position (1-9), we tested whether trials with higher-than-median overlap at that position showed different evaluation metrics. This controls for position entirely.

| Metric | Within-position r | Significant at any position? |
|--------|------------------|------|
| Total fixation time (TFT) | r ≈ 0 at all positions | No |
| Fixation count (TFC) | r ≈ 0 at all positions | No |
| Mean single-fixation duration | r ≈ 0 at all positions | No |
| Viewport time | r ≈ 0 at all positions | No |
| Eval rate (fixation/viewport) | r = -0.049 at position 1 only (p=0.01) | Marginal, one position |

**What this means:** Bag-of-words lexical overlap at the result level does not predict any evaluation metric once position is controlled. The effect we initially attributed to priming was driven by the position-overlap confound.

**What this does NOT mean:** The priming hypothesis is not rejected — it's untested at the right granularity. Bag-of-words overlap is a coarse measure. Several paths remain:

1. **Semantic embeddings** (TODO) — sentence-level similarity captures paraphrase and synonym priming that bag-of-words misses
2. **Token-level analysis** — within a result, do previously-seen tokens receive shorter fixations than novel tokens? Requires word-level AOI mapping.
3. **Working memory preloading** — the hypothesis that prior exposure reduces cognitive load may operate below the result level, at the phrase or concept level
4. **At-scale production logs** — millions of queries with natural satisficing behavior may have enough power to detect small effects that are invisible in 2,776 lab trials

The regression-vs-no-regression split (v2 finding) may still be informative: it showed the aggregate effect was concentrated in re-evaluation trials. But since the within-position test is null for both subsets, the re-evaluation framing also needs revisiting with finer-grained measures.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 4; [fixation_coverage.ipynb](../notebooks/fixation_coverage.ipynb), decomposition analysis

## 3. SERP-level homogeneity does not predict trial duration or regressions

Neither trial duration (r = -0.027, p = 0.15) nor regression count (r = -0.015) varies with overall SERP homogeneity. The signal is local (per-result overlap), not global. SERP-level homogeneity is too blunt — the variance that matters is which specific results have high vs low overlap with their predecessors.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Steps 2.5 and 3

## 3a. Evaluation time decomposes into four independent components

Position-dependent decline in total fixation time conflates several processes. Decomposing:

| Component | What it measures | Position-dependent? | Value |
|-----------|-----------------|-------------------|-------|
| **Page orientation** | Time from page load to first fixation on any result | No (fixed cost) | FV: ~1.6s, Scrollers: ~3.0s |
| **Scanning rate** | Additional time per position before first fixation arrives | Yes (linear ramp) | FV: ~2.6s/pos, Scrollers: ~1.7s/pos |
| **Fixation count** | Number of fixations on a result (once reached) | Yes (declines with position) | ~10 at pos 0 → ~7 at pos 9 |
| **Per-fixation duration** | Duration of each individual fixation | **No (~220ms, flat)** | 202-228ms across all positions |

The key insight: **per-fixation duration does not vary with position.** Each reading fixation costs ~220ms regardless of where you are on the page. The position-dependent decline in total fixation time comes entirely from investing fewer fixations at lower positions — an attention allocation decision, not a processing speed change.

This means the priming hypothesis (Finding 2) needs reframing. If priming operates, it should reduce fixation *count* (fewer looks needed to extract information from familiar vocabulary), not fixation *duration* (each look is the same speed). The within-position test for fixation count is null at bag-of-words granularity, but the mechanistic prediction for finer-grained measures remains: fewer refixations on previously-encountered tokens.

**Notebook:** [fixation_coverage.ipynb](../notebooks/fixation_coverage.ipynb), decomposition analysis

## 4. Scroll regressions are the dominant browsing pattern

69.1% of trials contain at least one scroll regression. Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Regression count correlates with decision time (r=0.660).

**Caveat:** The 69% rate is likely inflated by the forced-choice optimizing task. Participants who would normally abandon and reformulate are instead forced to re-evaluate. In real browsing, regression rates are probably lower.

**Notebook:** [scroll_regressions.ipynb](../notebooks/scroll_regressions.ipynb)

## 5. Mouse-gaze convergence depends on click intent

With scroll-corrected coordinates, distance starts low (~90px), rises as the user scrolls (gaze follows content, mouse stays in screen space), peaks near ~500px, then converges sharply in the last ~2s before click.

**Notebook:** [convergence_analysis.ipynb](../notebooks/convergence_analysis.ipynb)

## 6. Viewport state predicts clicks better than distance

At a 5s horizon, viewport features (target visible, time since scroll) outperform mouse-gaze distance (AUC 0.704 vs 0.548). The scroll-stop event is the stronger click signal.

**Notebook:** [convergence_analysis.ipynb](../notebooks/convergence_analysis.ipynb)

## 7. Individual differences are large

Per-participant acquisition onset ranges from 0.2s to 13.8s (SD=2.5s). Regression rates vary from 11% to 98% (SD=20.6%).

---

## Theoretical connections

The **Attentional-Foraging Equilibrium** provides the overarching frame. AFE models the SERP as a patch environment where the user's reward rate ρ = V / (τ + T_s + σ²) determines when to stop evaluating and commit to a click. The mechanisms below all operate on components of that equation.

The theoretical connections remain relevant even though the bag-of-words overlap measure didn't survive within-position controls:

- **Surprisal theory** (Hale 2001, Levy 2008): Predicts that high-overlap content has low surprisal → faster processing. The theory is sound; the measure (result-level bag-of-words) may be too coarse. Token-level surprisal within fixation sequences is the right test.
- **E-Z Reader** (Reichle, Rayner, Pollatsek): Predicts fewer refixations on familiar words. Our decomposition confirms per-fixation duration is flat (~220ms) across positions — the right level for this model is word-level, not result-level.
- **Given-new contract** (Clark & Haviland 1977): Predicts faster integration of "given" information. Still theoretically grounded — needs a measure that tracks given/new at the appropriate granularity.
- **Rational Inattention** (Sims 2003): Per-participant variance in regression rates and TTI reflects differences in bandwidth λ. This is well-supported by the user strategies analysis (regression rate 0%–98% range, TTI calibration at r=0.77).

The decomposition finding — that position-dependent evaluation decline comes from fewer fixations per result, not shorter fixations — suggests the mechanism operates at the **allocation** level (how many fixations to invest) rather than the **processing** level (how long each fixation takes). This is an attention-allocation decision, not a lexical processing effect. It may still be content-driven, but the signal pathway is different from what we initially hypothesized.

---

## What would test priming properly

The bag-of-words overlap measure at the result level is too coarse and too confounded with position. Paths forward:

1. **Token-level fixation analysis:** Map individual fixations to specific words within results. Test whether previously-seen tokens receive fewer refixations than novel tokens within the same result. This is the E-Z Reader prediction and requires word-level AOI mapping from the SERP HTML.

2. **Semantic embeddings:** Sentence-level similarity (e.g., via embedding cosine distance) captures paraphrase and synonym priming that bag-of-words misses. A result about "delay pedals" is semantically primed by a prior result about "echo effects" even with zero token overlap.

3. **At-scale production logs:** Millions of queries with natural satisficing behavior. Measure time-to-first-click by position, conditioned on SERP content similarity. The larger N may detect small effects invisible in 2,776 lab trials. This also provides the natural-stopping-criterion test that the forced-choice paradigm cannot (cf. Huang, White & Buscher 2012 on production-scale cursor data).

4. **Within-result fixation sequences:** For results that are revisited (regression trials), compare fixation patterns on the first vs second visit. If priming operates, the second visit should be shorter *and* show a different scanpath (skipping familiar tokens, fixating novel ones).

5. **Residual dwell model (Peter Dixon-Moses):** Establish a per-user baseline for expected evaluation time using TTI as a calibrator (r=0.77). Residuals from this model — "this result held attention longer than expected" — may reveal content-driven effects that position-level analysis cannot.

---

*v3, 2026-04-01. v1: aggregate priming correlation. v2: regression-stratified split (re-evaluation vs first-pass). v3: within-position controls show bag-of-words overlap does not survive position confound. Evaluation time decomposed into four components; per-fixation duration is position-invariant. Priming hypothesis reframed as fixation-count mechanism requiring finer-grained measures.*
