# Findings

Reanalysis of the AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). The [journey doc](journey.md) records how this started; this document records what we think we found.

**Status:** v6, 2026-04-02. Priming hypothesis tested at three granularities (bag-of-words, semantic embeddings, within-position) — null at all. Forward-only dwell increases with position (ρ = +0.82). §9 added: where relaxing serial evaluation helps. Orientation time (194ms median) reflects well-memorized SERP layout.

---

## Theoretical framework: The Attentional-Foraging Equilibrium

These findings are interpreted through the **Attentional-Foraging Equilibrium (AFE)** — a framework synthesizing Rational Inattention (Sims 2003) with Information Foraging Theory (Pirolli & Card 1999). The core equation: **ρ = V / (τ + T_s + σ²)**, where V = expected value, τ = handling time, T_s = travel time between patches, σ² = uncertainty. The user leaves a patch when ρ falls below threshold.

How each finding maps to AFE:

- **Lexical priming** (Finding 2) — tested at three levels of granularity (bag-of-words, semantic embeddings, within-position controls) and null at all of them. Forward-only dwell *increases* with position (ρ = +0.82). Lower dwell during regressions is explained by repetition/recognition and ballistic scroll kinematics, not content priming. The mechanism, if it exists, operates below the result level (possibly token-level fixation duration) — but the most parsimonious explanation is that evaluation slows with foraging depth because the candidate set in working memory grows.
- **Scroll regressions** (Finding 4) are travel costs (T_s) paid for re-evaluation. What triggers regressions remains untested — SERP-level homogeneity does not predict regression count (r = -0.015), and per-result novelty triggering has not been analyzed.
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

## 2. Cumulative content overlap does not predict evaluation speed

Tested at three levels of granularity. Null at all of them.

**The hypothesis:** As users scan down a SERP, they accumulate vocabulary from prior results. This cumulative exposure should make later results cheaper to evaluate — a priming effect from redundancy. If true, higher overlap with prior results should predict faster evaluation at the same rank.

**Bag-of-words overlap × evaluation metrics (within-position):**

| Metric | Within-position r | Significant at any position? |
|--------|------------------|------|
| Total fixation time (TFT) | r ≈ 0 at all positions | No |
| Fixation count (TFC) | r ≈ 0 at all positions | No |
| Mean single-fixation duration | r ≈ 0 at all positions | No |
| Viewport time | r ≈ 0 at all positions | No |
| Gaze dwell ratio (fixation/viewport) | r = -0.049 at position 1 only (p=0.01) | Marginal, one position |

**Semantic embeddings (mxbai-embed-large):** Cosine similarity between each result's snippet embedding and the centroid of all prior result embeddings. Also null within-position — sentence-level semantic similarity does not predict evaluation time any better than bag-of-words.

**The forward-only curve reverses the prediction:** Isolating forward-scanning periods (excluding regressions), gaze dwell ratio *increases* with position (Spearman ρ = +0.82). Users dwell longer on later results during first-pass scanning. The most parsimonious explanation: cognitive load increases with foraging depth because the candidate set in working memory grows. Each new result must be compared against an expanding set of already-evaluated alternatives.

**Why the aggregate correlation was misleading:** Position and overlap are confounded — both increase monotonically down the SERP. The aggregate partial r = -0.054 (p = 2.4×10⁻⁹) was driven by this confound, not by content. The regression-vs-no-regression split compounded the problem: lower dwell on revisit reflects recognition/memory and ballistic scroll kinematics (§8), not semantic priming.

**What remains:** Token-level fixation analysis (do previously-encountered words receive shorter fixations within a result?) and at-scale production logs with larger N. But the result-level hypothesis — that cumulative overlap predicts faster evaluation — is tested and null.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 4; [fixation_coverage.ipynb](../notebooks/fixation_coverage.ipynb), decomposition analysis

## 2a. p(fixate | visible) is also null — and structurally uninformative for forward scanning

The dwell ratio analysis (Finding 2) excluded results with zero fixations. If priming causes users to *skip* high-overlap results entirely, the signal would live in the binary fixation decision, not dwell duration.

We tested p(fixate | visible ≥100ms) as a function of cumulative overlap:

| Analysis | r_pb | p | N |
|----------|------|---|---|
| Aggregate, positions 1-9 | -0.059 | 2.4×10⁻¹³ | 15,527 |
| Within-position weighted mean | -0.031 | — | — |
| **Forward-only, positions 1-9** | **0.002** | **0.83** | **11,216** |
| Forward-only within-position mean | -0.0003 | — | 3/9 skip direction |

The aggregate signal (8/9 positions in skip direction) again does not survive forward-only isolation. The structural reason: **forward-only p(fixate) is ~99.8% at every position.** During first-pass scanning, users fixate virtually everything visible. There is no skip decision to predict — the variance that overlap could explain doesn't exist during forward scanning.

The 12.5% overall skip rate (2,280/18,299 visible results) is concentrated in regression trials and late-trial positions where viewport windows are short.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 6

## 3. SERP-level homogeneity does not predict trial duration or regressions

Neither trial duration (r = -0.027, p = 0.15) nor regression count (r = -0.015) varies with overall SERP homogeneity. The signal is local (per-result overlap), not global. SERP-level homogeneity is too blunt — the variance that matters is which specific results have high vs low overlap with their predecessors.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Steps 2.5 and 3

## 3a. Evaluation time decomposes into four independent components

Position-dependent decline in total fixation time conflates several processes. Decomposing:

| Component | What it measures | Position-dependent? | Value |
|-----------|-----------------|-------------------|-------|
| **Page orientation** | Time from page load to first fixation on any result | No (fixed cost) | Median **194ms** (all groups identical — SERP layout is well-memorized) |
| **Scanning rate** | Additional time per position before first fixation arrives | Yes (linear ramp) | FV: ~2.6s/pos, Scrollers: ~1.7s/pos |
| **Fixation count** | Number of fixations on a result (once reached) | Yes (declines with position) | ~10 at pos 0 → ~7 at pos 9 |
| **Per-fixation duration** | Duration of each individual fixation | **No (~220ms, flat)** | 202-228ms across all positions |

The key insight: **per-fixation duration does not vary with position.** Each reading fixation costs ~220ms regardless of where you are on the page. The position-dependent decline in total fixation time comes entirely from investing fewer fixations at lower positions — an attention allocation decision, not a processing speed change.

**Note on per-fixation duration as a priming metric:** It isn't one. Fixation duration is a low-level oculomotor parameter driven by saccade planning and foveal information extraction mechanics, not by result-level content familiarity. No one in the reading literature would predict that result-level lexical overlap changes individual fixation durations — the grain size is wrong. The flat ~220ms finding is a useful decomposition fact but says nothing about priming. The valid priming metrics at this granularity are fixation *count* (fewer looks needed) and p(fixate) (skip entirely). Both are null within-position. See "What we got wrong" in [journey.md](journey.md) for how we initially misframed this.

**Notebook:** [fixation_coverage.ipynb](../notebooks/fixation_coverage.ipynb), decomposition analysis

## 4. Scroll regressions are the dominant browsing pattern

69.1% of trials contain at least one scroll regression. Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Regression count correlates with decision time (r=0.660).

**Caveat:** The 69% rate is likely inflated by the forced-choice optimizing task. Participants who would normally abandon and reformulate are instead forced to re-evaluate. In real browsing, regression rates are probably lower.

**Notebook:** [scroll_regressions.ipynb](../notebooks/scroll_regressions.ipynb)

## 5. Mouse-gaze convergence depends on click intent

With scroll-corrected coordinates, distance starts low (~90px), rises as the user scrolls (gaze follows content, mouse stays in screen space), peaks near ~500px, with a modest downturn in the final 1-2s before click. The "sharp convergence" reported in v0 was largely an artifact of uncorrected coordinates; the corrected picture is dominated by scroll accumulation.

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

Tested at three granularities — bag-of-words, semantic embeddings (mxbai-embed-large cosine similarity), and within-position controls — all null. The remaining paths:

1. **Token-level fixation analysis:** Map individual fixations to specific words within results. Test whether previously-seen tokens receive fewer refixations than novel tokens within the same result. This is the E-Z Reader prediction and requires word-level AOI mapping from the SERP HTML. The only untested granularity.

2. ~~**Semantic embeddings:**~~ Tested. Sentence-level cosine similarity (mxbai-embed-large) between each result's snippet embedding and the centroid of all prior result embeddings. Null within-position, same as bag-of-words.

3. **At-scale production logs:** Millions of queries with natural satisficing behavior. Measure time-to-first-click by position, conditioned on SERP content similarity. The larger N may detect small effects invisible in 2,776 lab trials. This also provides the natural-stopping-criterion test that the forced-choice paradigm cannot.

4. **Within-result fixation sequences:** For results that are revisited (regression trials), compare fixation patterns on the first vs second visit. If priming operates, the second visit should show a different scanpath (skipping familiar tokens, fixating novel ones).

5. **Residual dwell model:** Establish a per-user baseline for expected evaluation time using TTI as a calibrator (r=0.77). Residuals from this model — "this result held attention longer than expected" — may reveal content-driven effects that position-level analysis cannot.

---

## 8. Backward scrolling is ballistic — the viewport mechanics confound

Backward scroll velocity is significantly higher than forward (median 915 vs 784 px/s, peak 1852 vs 1111 px/s). The velocity profile is ballistic (Spearman ρ = 0.867 between distance-from-target and velocity): users start fast and decelerate near the regression target.

87.3% of regression targets are at positions 0-4 (median: position 2). Positions 6-8 are ballistic transit zones — high velocity, short viewport windows, suppressed fixations. Position 9 is near the regression origin and reverses.

**The key test:** Regression velocity at each position correlates with the dwell ratio delta (all-inclusive minus forward-only) at ρ = -0.762 (p = 0.017). Scroll speed explains 58% of the variance in the "priming" pattern across positions.

This confirms that the lower dwell ratios at positions 6-8 when regressions are included are a viewport mechanics artifact, not evidence of content-driven re-evaluation. The user is flying past these positions at 1400+ px/s on the way to their actual target at positions 2-4.

**Notebook:** [scroll_kinematics.ipynb](../notebooks/scroll_kinematics.ipynb)

## 9. Where does relaxing the serial evaluation assumption help?

Click models (Chuklin et al. 2015), cascade models (Craswell et al. 2008), and the two-stage examination model (Liu et al. CIKM 2014) assume monotonic top-to-bottom examination. This has been a useful simplification — it makes position bias estimable and evaluation metrics tractable (Azzopardi SIGIR 2014, C/W/L framework). The question isn't whether serial evaluation is "wrong" but where allowing for complexity buys you something.

**What we observe in AdSERP (with caveats):**

- **69% of trials contain at least one scroll regression.** Mean 2.8 regressions/trial, ~7 result positions of travel. This aligns with Lorigo et al.'s (2008) ~66% nonlinear scanpaths from a different era and task. **However:** both studies are lab-scale with constrained tasks. The AdSERP forced-click design (no abandonment option) likely inflates regression rates — participants *must* choose, so they re-evaluate rather than leave. We don't know the at-scale regression rate on production SERPs because, remarkably, nobody has measured it. NN/g's 130K-fixation scrolling study (2020) measures only forward attention allocation. Huang, White & Buscher (2012) use scroll events to infer examination but don't decompose direction. Click models don't model it.

- **Regression targets are position-specific** (ANOVA η² = 0.87) but landing precision is region-level, not result-level (offset from nearest result center ≈ random baseline). After landing, ~6 fixations of visual search are needed to locate the target. This implies spatial memory for SERP layout that is coarser than individual results — consistent with Solman & Kingstone (2024) on spatial memory in naturalistic visual search.

- **Revisit behavior is asymmetric.** Clicked results get +32% more fixations and +37% more time on revisit (deep confirmation). Non-clicked results get −17% fewer fixations (quick rejection). Per-fixation duration drops slightly on revisit (210 vs 216ms) — recognition, not re-reading.

- **The satisfice/optimize dimension maps to regression rate.** Per-participant regression rate correlates with LHIPA (pupillometric cognitive load) at ρ = −0.55. Optimizers (86% regression rate, lower LHIPA = more load) click higher (mean position 2.7) than satisficers (43% rate, position 3.4). Optimizers don't forage deeper — they forage more thoroughly.

**Where complexity helps:**

1. **Position bias estimation.** Cascade models absorb regression effects into the position parameter. The "position 7 penalty" includes both natural examination decay and the ballistic transit effect (§8) — users fly past position 7 at 1400 px/s on the way to their regression target at position 2-4. Separating these would sharpen position bias estimates for sessions where regressions occur.

2. **The stopping/regression/paginate decision.** Maxwell & Azzopardi (ECIR 2018) model SERP-level stopping using information scent, but the model has one exit: leave. Our data suggests three competing actions at the bottom-of-page deliberation point: click what you've seen, scroll back to re-evaluate, or paginate. The forced-choice task makes regression visible where naturalistic search allows abandonment — regressions may be what abandonment looks like when leaving isn't an option.

3. **Evaluation metrics for re-finding tasks.** Navigational and re-finding queries may have higher natural regression rates than informational queries, because the user has a specific target in memory. Serial evaluation metrics would penalize SERPs that support efficient regression (e.g., distinctive visual landmarks at each result).

**An unmeasured signal at scale.** The simplest regression indicator — `click_position < max_scroll_depth` — is trivially computable from standard search telemetry. Every search engine logs scroll events and click positions. Yet as of this writing, no published work reports the at-scale prevalence of this signal on production SERPs. Huang, White & Buscher (2012) recorded "all SERP interactions including cursor and scroll movements" at Bing and used scroll to infer examination — but didn't decompose scroll direction. NN/g's 130K-fixation scrolling study (2020) measured only forward attention allocation. The cascade model's success at ranking evaluation may have created a blind spot: if the forward-only assumption produces useful metrics, there's no pressure to instrument for the thing it can't represent.

The natural rate is almost certainly much lower than AdSERP's 69%. From personal observation (unverifiable; internal data), `click_rank < max_scroll_offset` appears in roughly 15% of sessions in large-scale e-commerce search logs — still a meaningful minority, but the forced-click task inflates regression prevalence by roughly 4–5x by eliminating the abandonment alternative. The true question for production systems is whether that ~15% is random noise or a behaviorally coherent segment worth modeling.

**Where simplification is fine:** For aggregate ranking evaluation, offline metrics, and most A/B testing, the serial assumption produces useful rankings. The regression phenomenon matters most at the session level — understanding individual search episodes, detecting struggle, and modeling the foraging dynamics within a single query.

**Notebooks:** [regression_decisions.ipynb](../notebooks/regression_decisions.ipynb), [scroll_kinematics.ipynb](../notebooks/scroll_kinematics.ipynb)

---

## v4 corrections

**Viewport time computation (v3 → v4):** The prior `compute_viewport_time` only counted time between scroll events. Pre-scroll periods (page load → first scroll, where position 0 is visible the entire time) and post-scroll periods were dropped. This caused position 0 dwell ratios >1.0 (e.g., 13,000ms fixation on 183ms computed viewport — a 73x ratio). Fixed by covering the full trial window. Position 0 dwell ratio corrected from 1.35 → 0.28.

**Forward-only shape test (new):** Isolating forward-scanning periods (excluding scroll regressions), the gaze dwell ratio *increases* with position (Spearman ρ = +0.73 on position means 0-8 (corrected to +0.82 after FPOGY clamp in v5), permutation p = 0.98 against priming). Users dwell longer on later results during first-pass scanning — consistent with increasing cognitive load from holding more candidates in working memory. The aggregate partial r = -0.060 was driven by regressions, but this does not indicate priming: lower dwell on revisit is expected from repetition/recognition (the user already encoded the content), and is further confounded by ballistic backward scroll dynamics that create systematically shorter viewport windows at intermediate positions (see `scroll_kinematics.ipynb`). The within-position test is null for regression trials too.

**Metric rename:** "Eval rate" / "attention density" → "gaze dwell ratio" (fixation duration / visible duration). Both numerator and denominator are durations in ms; the result is a dimensionless ratio, not a rate.

## v5 corrections (2026-04-02)

**FPOGY out-of-bounds clamp (fixation attribution bug).** The Gazepoint GP3 HD reports gaze Y coordinates that exceed the screen boundaries — 24.5% of fixations have FPOGY > screen_height (1024px), with the 95th percentile at 1830px. These out-of-bounds samples were added to `scroll_offset` to compute `page_y`, attributing fixations to SERP positions below the viewport. Position 9 was the primary victim: mean per-trial dwell ratio was 2.9× (89% of trials >1.0). The fix: clamp `FPOGY` to `[0, screen_height]` before computing `page_y = fy + scroll_offset`. Position 9 dwell ratio corrected from 1.25 → 0.79. Forward-only shape test strengthened slightly (ρ from +0.73 to +0.82).

**Anyone working with AdSERP fixation data** should be aware that FPOGY values can substantially exceed screen bounds. Always clamp or filter gaze coordinates to the viewport before mapping to page-space positions.

---

*v6, 2026-04-02. v1: aggregate priming correlation. v2: regression-stratified split (re-evaluation vs first-pass). v3: within-position controls show bag-of-words overlap does not survive position confound. v4: viewport time bug fix; forward-only shape test shows dwell increases with position (ρ = +0.73), reversing priming prediction; metric renamed to gaze dwell ratio. v5: FPOGY clamp fix (24.5% of fixations out-of-bounds); position 9 dwell ratio 1.25 → 0.79; scroll kinematics analysis confirms ballistic regression confound (ρ = -0.762); regression-trial "priming" reframed as triple confound (position, repetition, kinematics).*
