# Findings

Reanalysis of the [AdSERP dataset](https://github.com/kayhan-latifzadeh/AdSERP) (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). The [journey doc](journey.md) records how this started; this document records what we found.

**Status:** v12, 2026-04-12. §0 ski-jump rebuilt on post-coord-fix data (cohort A only; full-corpus uptick at pos 10 was a pre-audit artifact). Prior: v11 Key Claims refs + stale value corrections. v10 element-type approach-retreat (§10b), parafoveal preview null (§3d-ii), survey phase pupil trajectory (§3b-iii), ski-jump (§0), OSEC (§3b), difficulty (§3c), priming null (§2), scroll kinematics (§8).

---

## Task model

SERP evaluation decomposes into four measurable phases. See the [pre-submission draft](arxiv/task-model-paper.pdf) for the full argument.

```
Orient → Survey → Evaluate ─┬─→ Click result
                  ↑          ├─→ Next page / Reformulate query
                  └──────────┘   └─→ Abandon search
                  (regression)
```

AdSERP's forced-choice task eliminates reformulation and abandonment, isolating the inner loop. Each phase has been studied in isolation in the literature (click models encode examination assumptions, Liu et al. 2014 identified skimming→reading, Pirolli & Card 1999 provided the foraging framework). The contribution is identifying them as phases of a single task with measurable saccadic transitions.

---

## Dataset constraints

Two major caveats versus generalized SERP behavior. These pervade all findings.

**1. Forced choice with optimizing intent.** Participants were instructed to "click on the item they would typically choose" for product purchase queries, with up to 1 minute per trial and a confirmation step. Every trial ends with a click — no abandonment, no query reformulation. This is optimizing behavior ("what would I actually buy?"), not satisficing ("is this good enough?"). The 65% regression rate and thorough evaluation patterns reflect this constraint.

**2. Limited X-axis variation.** SERPs were served via localhost in a controlled lab environment. No competing browser chrome, no tabs, no bookmarks bar, no address bar. Mouse position variance is artificially constrained compared to real browsing where attention splits across the full browser window.

**However:** The within-SERP scanning behavior converges with free-reformulation studies. Lorigo et al. (2008) found ~66% nonlinear scanpaths under informational queries where users could freely reformulate, abandon, and navigate — compared to our 65% under forced choice. The phase structure, reading depth, and position effects appear to be intrinsic properties of SERP evaluation, not artifacts of forced choice. What the forced-choice task limits is generalization about the **exit decision** (stay, refine, abandon) — not about how people read the results once they're on the page.

---

## 0. The ski-jump: click distribution upticks at the boundary

*Updated 2026-04-12 (post coordinate-space audit).* The pre-audit version of this section reported a 39% excess at position 10 (χ² = 10.0, p = 0.0015) using `count_absolute_ranks` and a click-y coordinate that mis-applied scroll. After the coord fix, the full-cohort click distribution is monotonic: pos 0 = 18.9%, pos 1 = 18.7%, pos 2 = 25.0% (first organic after DoubleDeck ads), then a clean decay to pos 9 = 1.1%, pos 10 = 0.4%. **The full-corpus rank-10 uptick does not survive the audit.**

The uptick DOES survive in the cohort where the industry ski-jump actually lives: plain-top SERPs (no ads above the first organic result), ≥10 organic results, and the user actually scrolled rank 9 into view. In this cohort (n=131 trials), rank 7 = 6.1% → rank 8 = 2.3% → **rank 9 = 3.1%**, a +33% relative uptick.

| Rank | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | **9** |
|-----|---|---|---|---|---|---|---|---|---|--------|
| Click % | 35.1 | 7.6 | 9.2 | 9.9 | 10.7 | 6.1 | 6.9 | 6.1 | 2.3 | **3.1** |

The magnitude is muted relative to production search for a structural reason: AdSERP is forced-choice. In this cohort, only 3 of 131 trials (2.3%) regress without clicking. In naturalistic search that number is 20–30% — users who reach the bottom routinely give up or refine, and the residual "I'll just click the last one" population produces the large industry spike. AdSERP closes that escape valve, so the uptick can only grow as large as the small fraction of users who, having seen everything, genuinely prefer the last result. The shape is the same; the task structure caps its magnitude.

Full-corpus numbers: `scripts/output/ski_jump_canonical.csv`. Cohort A numbers: `scripts/output/ski_jump_rank10/ctr_by_rank_by_cohort.csv`.

**Who clicks at the boundary?** Optimizers (high regression rate) are 1.56× more likely to click at positions 9–10 than satisficers (14.5% vs 9.3%). They evaluated the whole SERP before committing.

**Cognitive load at the boundary.** LHIPA drops sharply at positions 9–10 (0.041 vs 0.049, p < 0.0001). Lower LHIPA = higher cognitive load. Boundary clickers are working harder, not giving up. They've seen everything and still need to pick.

**Difficulty modulation.** Easy SERPs (high relevance spread) produce more boundary clicks (13.6% vs 10.0%). Users who scroll all the way down on an easy SERP are likelier to click at the boundary because the standout was lower in the ranking.

**Investment.** Boundary clickers invested ~100 fixations and 26.5s, vs ~89 fixations and ~23s for mid-range clickers (positions 3–6).

**Why the ski-jump happens.** The decline is attention allocation under diminishing returns. Each successive result gets fewer fixations (not shorter ones — per-fixation duration is flat at ~220ms). The user invests less in each new candidate because the marginal value of evaluating one more drops as evaluation criteria compile and the remaining uncertainty shrinks (§3a, §3b-iv).

The uptick at the boundary is a micro-economic phenomenon. By position 9–10, three costs collapse simultaneously:

- **Handling cost (τ) drops.** The user has built well-formed selection criteria from evaluating 8+ results. Each remaining result is evaluated against a crisp comparison set, not a vague initial intent. The question has narrowed from "is this what I want?" to "is this better than the one I liked at position 3?"
- **Travel cost (T_s) approaches zero.** There's nowhere left to scroll. The cost that normally competes with continued evaluation — paginate, reformulate, abandon — is eliminated (in this task) or maximized (in production search, where "next page" is the expensive alternative).
- **Uncertainty (σ²) is low.** The user has seen the full page. There's no possibility of a better result below the fold.

These cost reductions are observable in the data: boundary clickers show higher cognitive load (LHIPA, confirming they're doing real evaluation, not satisficing), more fixations (confirming continued investment), and are disproportionately optimizers (confirming thorough evaluation preceded the decision). The reward rate spikes not because the last result is better, but because the cost of evaluating it is near zero and the comparison framework is maximally refined.

In production search, the boundary is "next page" and the same dynamics apply: the uptick represents users deciding that the cost of pagination exceeds the cost of picking from what they've already seen.

**Notebook:** [00_skijump.ipynb](../notebooks-v2/00_skijump.ipynb)

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

**The forward-only curve reverses the prediction:** Isolating forward-scanning periods (excluding regressions), gaze dwell ratio *increases* with position (Spearman ρ = +0.82 on *N* = 9 position means). Users dwell longer on later results during first-pass scanning. The naive explanation — cognitive load increases with foraging depth as working memory grows — is contradicted by per-position pupillometry (§3b-iv), which shows cognitive load *decreasing* with position. The dissociation suggests evaluation becomes *routinized*: the comparison set grows (more time), but compiled evaluation criteria make each comparison cheaper (less cognitive effort per unit time).

**Why the aggregate correlation was misleading:** Position and overlap are confounded — both increase monotonically down the SERP. The aggregate partial r = -0.054 (p = 2.4×10⁻⁹) was driven by this confound, not by content. The regression-vs-no-regression split compounded the problem: lower dwell on revisit reflects recognition/memory and ballistic scroll kinematics (§8), not semantic priming.

**Survey-to-evaluate vocabulary transfer (fourth test):** If the survey builds a lexical context that primes subsequent reading, then results whose vocabulary was well-represented in the survey-fixated results should get faster evaluation. Tested on 24,025 forward-only evaluate episodes at non-surveyed positions. Survey vocabulary overlap with the evaluated result (mean 0.31) does not predict episode duration (ρ = 0.011, p = 0.094) or fixation count (ρ = 0.012, p = 0.063). Null at every position within-position (all p > 0.06). Tercile split: low-overlap episodes are if anything slightly *faster* (689ms vs 718ms, KW p = 0.10). The survey's output is a strategy decision, not a processing facilitation.

**What remains:** Token-level fixation analysis (do previously-encountered words receive shorter fixations within a result?) and at-scale production logs with larger N. But the result-level hypothesis — that content overlap predicts faster evaluation — is now tested at four granularities and null at all of them.

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

**Notebook:** [fixation_coverage.ipynb](../notebooks/fixation_coverage.ipynb), [04_fixation_coverage.ipynb](../notebooks-v2/04_fixation_coverage.ipynb)

## 3b. Orient–Survey–Evaluate–Commit: the phase structure

Saccade amplitude distinguishes two scanning modes within each trial:

| Phase | Saccade amplitude | Duration | Behavior |
|-------|-------------------|----------|----------|
| **Survey** (fixations 1–~5) | 107.8 px median, 53% major | ~1.3s (median) | Wide jumps between results, gist sampling [NB13:K5] |
| **Evaluate** (fixations ~6+) | 69.4 px median, 40% major | Variable | Narrow saccades within results, reading episodes [NB13:K6] |

Per-trial amplitude slope over first 20 saccades: mean ρ = −0.135, p = 9.33 × 10⁻¹⁶⁸ (N = 2,754) [NB13:K2–K3]. The transition is detectable within individual trials (71.8% have negative slope) [NB13:K4].

**Survey duration is fixed.** Median 1.28s (IQR 1.06–1.58s). Survey duration shows weak negative correlation with total fixation count (ρ = −0.163) — quick deciders may spend relatively more time surveying — but does not respond to SERP content difficulty.

**SERP complexity is not driving the survey.** Splitting 2,768 trials by right-panel presence (858 complex vs 1,910 simple): the survey amplitude drop survives in simple SERPs (107px vs 74px, p = 10⁻¹⁵⁰). Only 3.4% of survey fixations land on the right panel. The survey is cognitive gist sampling, not feature-driven navigation.

**Prior work:** Zhang, Abualsaud & Smucker (CHIIR 2018) documented a "result inspection phase" where users evaluate the top 2–3 results to decide whether the SERP is worth continued evaluation or immediate requery. This is the survey phase in the context of the stay/reformulate decision — the naturalistic exit path that AdSERP's forced-choice task eliminates. Their observation dates to ~2011. In naturalistic search, the survey phase serves a dual purpose: assessing result quality (what we measure here) AND deciding whether to stay on the SERP at all (what we cannot measure here).

**Orientation is a learned prior.** Median orientation time: 0ms. 58% of first fixations land directly on a result. No learning effect across 60 trials (ρ = 0.02, p = 0.30). The SERP layout is memorized.

**Survey and scroll are decoupled.** Survey ends at fixation ~5. First scroll at fixation ~21 (median). 94.6% of trials: survey ends well before the first scroll. The user evaluates ~16 fixations of first-viewport results between survey and scroll.

**Notebook:** [06_orientation_evaluation.ipynb](../notebooks-v2/06_orientation_evaluation.ipynb), [13_survey_phase.ipynb](../notebooks-v2/13_survey_phase.ipynb)

## 3b-ii. Survey phase characterization

Three analyses of what the survey phase does:

**1. Saccade direction: survey reads across, evaluate reads down.** Survey saccades are more horizontal (45.7% primarily vertical) than evaluate saccades (51.2%). Mean horizontal displacement: 149px (survey) vs 72px (evaluate). The survey is scanning across titles and snippets — gist extraction from text — not just jumping between result slots.

**2. Survey fixations predict clicks at mid-fold positions.** Controlling for position, with viewport-bounded analysis (FPOGY clamped to screen height, positions 0–6 only — positions 7+ are below the fold and not visible during the pre-scroll survey phase):

| Position | P(click \| surveyed) | P(click \| not surveyed) | Lift | p (Fisher) |
|----------|---------------------|-------------------------|------|------------|
| 0–2 | 8–9% | 7–10% | ~1.0x | n.s. |
| 3 | 22.7% | 16.1% | 1.4x | 0.002 |
| 4 | 6.8% | 6.9% | 1.0x | n.s. |
| 5 | 19.7% | 16.8% | 1.2x | n.s. |
| 6 | 7.5% | 8.2% | 0.9x | n.s. |

Position 3 is the only individually significant position (p = 0.002). Aggregate positions 3–6: 16.9% vs 11.9%, 1.4x lift. The survey identifies candidates at the edge of the first viewport, modestly but reliably.

**Correction (v7):** Earlier analysis reported 4–7x lifts at positions 7–9. These were artifacts of out-of-bounds FPOGY values (24.5% of Gazepoint fixations exceed screen height) mapped to below-fold positions that aren't visible during the survey phase (94.6% of surveys end before the first scroll). Clamping FPOGY to screen height and restricting to above-fold positions eliminates the spurious signal.

In naturalistic search (Zhang et al. CHIIR 2018), this same signal gates the stay/reformulate decision: if survey fixations at the top land on relevant-looking results, the user stays. In AdSERP, that exit path is closed, so the survey output only modulates evaluation depth.

**3. Spatial spread is 3.3x higher during survey.** Unique result positions per fixation: 0.447 (survey) vs 0.137 (evaluate), p ≈ 0. Survey fixations scatter across many result positions; evaluate fixations cluster within one or two. This is the strongest evidence that survey and evaluate are qualitatively different scanning modes.

**4. The survey does not repeat after scrolling.** Post-scroll saccades are not wider than pre-scroll (median 78px vs 75px). No amplitude spike after forward scroll events. The user goes straight into reading newly exposed content. The survey happens once at the beginning of the trial; scrolling does not reset the phase.

## 3b-iii. Pupil dilation confirms the survey is low-load

Per-fixation mean pupil diameter (binocular average, blink-cleaned, N = 2,720 trials) reveals a three-phase trajectory:

| Phase | Fixations | Pupil change from baseline | Interpretation |
|-------|-----------|---------------------------|----------------|
| **Orienting** | 1–2 | +1.2% dilation | Arousal/novelty response to new stimulus |
| **Survey** | 3–5 | −3.0% constriction | Low-load gist sampling; visual system calibrating |
| **Evaluate** | 6–20 | −1.3% → 0% (gradual recovery) | Cognitive work; evaluation deepens (but per-position load decreases — see §3b-iv) |

Survey vs evaluate pupil diameter: p = 10⁻¹¹⁷. The survey phase *constricts* pupils — it is a cheap sampling routine, not effortful processing. The cognitive work comes during committed reading (evaluate phase), where the pupil gradually recovers toward baseline during deliberate evaluation of each candidate.

**Notebook:** [13_survey_phase.ipynb](../notebooks-v2/13_survey_phase.ipynb)

## 3b-iv. Per-position cognitive load decreases, not increases — framework compilation, not working memory overload

Duchowski (2026) Butterworth IIR method enables per-result cognitive load measurement at the ~2-second per-position granularity where wavelet LHIPA cannot operate (minimum 7.5s). Two 4th-order Butterworth filters (LF: 0–1.6 Hz, HF: 1.6–4 Hz) applied to the full blink-cleaned 150 Hz pupil stream; LF/HF variance ratio computed per position during forward scanning. Higher LF/HF = higher cognitive load.

**The working memory hypothesis is wrong.** LF/HF *decreases* with position (**ρ = −0.927, p < 0.0001** on *N* = 11 position medians aggregated from 2,719 trials) [NB14:K3]. Cognitive load peaks at position 0 and drops steeply through positions 0–3, then plateaus at approximately half the initial level through positions 4–10.

| Positions | Median LF/HF | N valid segments |
|-----------|-------------|-----------------|
| 0 | 29.64 | 1,036 |
| 1–3 | 19.7 | 3,193 |
| 4–10 | 14.9 | 1,870 |

Within-trial: median ρ = −0.400 (61.0% of 1,025 trials show declining load) [NB14:K5]. Cross-validation: trial-mean LF/HF anti-correlates with LHIPA (ρ = −0.125, p = 7.47 × 10⁻¹⁰, N = 2,416) [NB14:K7], confirming both measures capture the same construct.

**Interpretation.** The first result demands the highest cognitive effort because the user is constructing evaluation criteria from scratch. As criteria compile, subsequent results require less effort per unit of committed evaluation time — even as behavioral gaze dwell *ratio* increases (forward-only dwell ratio ρ = +0.82, §2). This dissociation between time and cognitive effort indicates evaluation becomes *routinized*, not *overloaded*.

**Connection to priming (§2).** The declining cognitive load profile is superficially consistent with lexical priming (repeated tokens easier to process). But priming was null at four granularities, and the load decrease happens within the first 3 positions before substantial overlap accumulates. Framework compilation — not lexical facilitation — is the parsimonious explanation.

**Canonical values:** [NB14:K1–K8](notebook-key-claims.md#nb14-14_butterworth_cognitive_load). **Notebook:** [14_butterworth_cognitive_load.ipynb](../notebooks-v2/14_butterworth_cognitive_load.ipynb)

## 3c. SERP difficulty is discriminability, not similarity

Three difficulty measures tested:

| Measure | Mean | What it measures |
|---------|------|-----------------|
| Jaccard | 0.151 | Bag-of-words token overlap between results |
| Relevance spread | 0.052 | Std of query–result embedding cosine similarity |
| Distinctive density | 0.460 | TF-IDF-weighted unique-token fraction per result |

Jaccard and relevance spread are strongly anti-correlated (ρ = −0.450) — different constructs.

**Relevance spread is the strongest predictor.** Within-participant: coverage (ρ̄ = 0.089, p < 0.001), duration (ρ̄ = 0.042, p = 0.031). Between-trial: coverage (ρ = 0.098, p < 0.001), click position (ρ = 0.046, p = 0.047), duration (ρ = 0.043, p = 0.03). Jaccard is null for duration, fixations, and regressions.

**Why token overlap fails for transactional queries.** All AdSERP queries are "buy [brand] [product]." Results *should* share vocabulary — they're all selling the same thing. High overlap doesn't mean the results are hard to tell apart. What matters is whether one result clearly matches the query better than the others (high relevance spread) or whether they're all equidistant (low spread). Low spread → satisfice early (49% coverage). High spread → explore deeply (53% coverage).

**Notebook:** [09_difficulty.ipynb](../notebooks-v2/09_difficulty.ipynb); [compute_difficulty_measures.py](../scripts/compute_difficulty_measures.py)

## 3d. Reading episodes and parafoveal processing

Consecutive fixations on the same result connected by minor saccades (<100px) form **reading episodes** — continuous processing units where the parafovea preprocesses the next landing during each fixation.

| Metric | Value |
|--------|-------|
| Total episodes | 95,328 across 2,334 trials |
| Single-fixation episodes | 50.5% |
| Multi-fixation episodes | 49.5% (mean 2.16 fixations, 499ms) |
| Parafoveal time per trial | ~866ms (inter-fixation gap time within episodes) |

**Difficulty effect.** Proportion of multi-fixation episodes is higher on hard SERPs (51% vs 49%, p = 0.004). Other episode metrics (fixations per episode, episode duration, parafoveal time) are null against Jaccard difficulty.

The ~866ms of parafoveal processing time per trial is invisible to raw FPOGD summation. Episode pooling recovers it.

**Notebook:** [09_difficulty.ipynb](../notebooks-v2/09_difficulty.ipynb)

## 3d-ii. Parafoveal preview benefit is null between results (margin fixations)

Within reading episodes, parafoveal preprocessing helps (~866ms recovered per trial, §3d above). But **between results**, the classic parafoveal preview benefit (Rayner 1998, 2009) does not transfer to SERP reading.

20.2% of fixations (39,442 of 195,468) fall within 48 px (~2° visual angle) of the next result's boundary — the vertical parafoveal preview zone. These "margin fixations" are geometrically more likely to saccade to result N+1 (23.4% vs 6.1%), but the preview benefit test is null:

| Test | Effect | p |
|------|--------|---|
| Raw next-fixation duration (margin vs interior) | Δ = -3 ms | 0.20 |
| Amplitude-matched comparison | Δ = -2 to -5 ms | n.s. |
| Partial r(dist, next_dur \| current_dur) | r = 0.013 | 0.053 |
| 2×2 (short/long) × (margin/interior) | Δ = -6 ms (short), -3 ms (long) | 0.06 / 0.37 |
| By OSEC phase (survey / evaluate) | Δ = -4 ms / -3 ms | n.s. |

The apparent benefit of short margin fixations (-49 ms) is fixation duration autocorrelation (lag-1 r = 0.191): short fixations beget short fixations regardless of position.

**Why preview fails between results:** In text reading, the preview zone contains the next word with distinctive orthographic features. On a SERP, the preview zone shows another structurally identical result block — title, URL, snippet, in the same layout. There is nothing distinctive to preview. This is consistent with the content-independence of survey saccades (§3b).

Left-margin fixations (x < 200 px) near boundaries are shorter (207 ms vs 225 ms) and cluster in the survey phase (39% vs 31% center). These are vertical sweep landmarks — the scan's structural skeleton — not preview-guided planning saccades.

**Notebook:** [19_margin_fixations.ipynb](../notebooks-v2/19_margin_fixations.ipynb)

## 3e. Forward-pass reading depth is constant; the position effect is revisitation

Separating forward-pass episodes (first encounter during the scan) from regression episodes (revisits after scrolling back) reveals two different processes:

**Forward pass (generalizable):**

| Pos | Episodes | Fix/Episode | Episode Duration |
|-----|----------|-------------|-----------------|
| 0 | 3.2 | 2.11 | 529ms |
| 4 | 2.2 | 2.15 | 528ms |
| 8 | 2.0 | 2.01 | 506ms |

Fix/episode declines 5% from position 0 to 8. Episode duration declines 4%. Both are essentially flat. **On first encounter, the user reads each result at roughly the same depth regardless of position.** What declines is how many episodes the result receives (38% decline) — how many times the user's gaze returns to it during the forward scan.

**Regression revisits (task-specific):**

| Pos | Episodes | Fix/Episode | Episode Duration |
|-----|----------|-------------|-----------------|
| 0 | 6.0 | 2.10 | 497ms |
| 4 | 3.5 | 1.87 | 418ms |
| 8 | 2.5 | 1.74 | 383ms |

Fix/episode declines 17%. Duration declines 23%. Both reading depth and revisit frequency drop substantially. This is recognition/confirmation behavior, not re-reading — and it's heavily shaped by the forced-choice constraint. Users who would normally abandon or reformulate are forced to scroll back, producing revisit patterns that may not generalize to naturalistic search.

**The correct decomposition of the position effect:** On first encounter, reading depth per episode is constant. The position effect comes from fewer episodes per result (fewer returns to it during scanning). The regression revisit pattern adds a second layer — shallower, declining re-reading — but this layer is entangled with the forced-choice paradigm and should not be treated as a general property of search behavior.

**Notebook:** [00_skijump.ipynb](../notebooks-v2/00_skijump.ipynb)

---

## 4. Scroll regressions are the dominant browsing pattern

65% of trials contain at least one scroll regression (catalog computation; 2,341 trials with behavioral tags). Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Regression count correlates with decision time (r=0.660).

**Caveat:** The 65% rate is likely inflated by the forced-choice optimizing task. Participants who would normally abandon and reformulate are instead forced to re-evaluate. In real browsing, regression rates are probably lower.

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

The task model (§3b) maps onto several theoretical traditions:

- **Information foraging** (Pirolli & Card 1999): The survey phase is patch quality assessment. The commit decision is the marginal value threshold. Scroll regressions are travel costs. The satisfice/optimize dimension maps to individual differences in foraging strategy.
- **Surprisal theory** (Hale 2001, Levy 2008): Predicts high-overlap content has low surprisal → faster processing. The theory is sound; the measure (result-level bag-of-words) was too coarse. Token-level surprisal within fixation sequences is the right test — untested.
- **E-Z Reader** (Reichle et al. 1998): Per-fixation duration is flat (~220ms) across positions — consistent with a fixed-duration sampling process. The reading episode (§3d) is the appropriate unit, not the individual fixation.
- **Rational Inattention** (Sims 2003): Per-participant variance in regression rates and TTI reflects differences in processing bandwidth. Well-supported by the user strategies analysis (regression rate 0%–98% range, TTI calibration at r = 0.77).

The decomposition finding — that position-dependent evaluation decline comes from fewer fixations per result, not shorter fixations — means the mechanism operates at the **allocation** level (how many looks to invest) rather than the **processing** level (how long each look takes).

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

- **65% of trials contain at least one scroll regression.** Mean 2.8 regressions/trial, ~7 result positions of travel. This aligns with Lorigo et al.'s (2008) ~66% nonlinear scanpaths from a different era and task. **However:** both studies are lab-scale with constrained tasks. The AdSERP forced-click design (no abandonment option) likely inflates regression rates — participants *must* choose, so they re-evaluate rather than leave. We don't know the at-scale regression rate on production SERPs because, remarkably, nobody has measured it. NN/g's 130K-fixation scrolling study (2020) measures only forward attention allocation. Huang, White & Buscher (2012) use scroll events to infer examination but don't decompose direction. Click models don't model it.

- **Regression targets are position-specific** (ANOVA η² = 0.87) but landing precision is region-level, not result-level (offset from nearest result center ≈ random baseline). After landing, ~6 fixations of visual search are needed to locate the target. This implies spatial memory for SERP layout that is coarser than individual results — consistent with Solman & Kingstone (2024) on spatial memory in naturalistic visual search.

- **Revisit behavior is asymmetric.** Clicked results get +32% more fixations and +37% more time on revisit (deep confirmation). Non-clicked results get −17% fewer fixations (quick rejection). Per-fixation duration drops slightly on revisit (210 vs 216ms) — recognition, not re-reading.

- **The satisfice/optimize dimension maps to regression rate.** Per-participant regression rate correlates with LHIPA (pupillometric cognitive load) at ρ = −0.55. Optimizers (86% regression rate, lower LHIPA = more load) click higher (mean position 2.7) than satisficers (43% rate, position 3.4). Optimizers don't forage deeper — they forage more thoroughly.

**Where complexity helps:**

1. **Position bias estimation.** Cascade models absorb regression effects into the position parameter. The "position 7 penalty" includes both natural examination decay and the ballistic transit effect (§8) — users fly past position 7 at 1400 px/s on the way to their regression target at position 2-4. Separating these would sharpen position bias estimates for sessions where regressions occur.

2. **The stopping/regression/paginate decision.** Maxwell & Azzopardi (ECIR 2018) model SERP-level stopping using information scent, but the model has one exit: leave. Our data suggests three competing actions at the bottom-of-page deliberation point: click what you've seen, scroll back to re-evaluate, or paginate. The forced-choice task makes regression visible where naturalistic search allows abandonment — regressions may be what abandonment looks like when leaving isn't an option.

3. **Evaluation metrics for re-finding tasks.** Navigational and re-finding queries may have higher natural regression rates than informational queries, because the user has a specific target in memory. Serial evaluation metrics would penalize SERPs that support efficient regression (e.g., distinctive visual landmarks at each result).

**An unmeasured signal at scale.** The simplest regression indicator — `click_position < max_scroll_depth` — is trivially computable from standard search telemetry. Every search engine logs scroll events and click positions. Yet as of this writing, no published work reports the at-scale prevalence of this signal on production SERPs. Huang, White & Buscher (2012) recorded "all SERP interactions including cursor and scroll movements" at Bing and used scroll to infer examination — but didn't decompose scroll direction. NN/g's 130K-fixation scrolling study (2020) measured only forward attention allocation. The cascade model's success at ranking evaluation may have created a blind spot: if the forward-only assumption produces useful metrics, there's no pressure to instrument for the thing it can't represent.

The natural rate is almost certainly much lower than AdSERP's 65%. From personal observation (unverifiable; internal data), `click_rank < max_scroll_offset` appears in roughly 15% of sessions in large-scale e-commerce search logs — still a meaningful minority, but the forced-click task inflates regression prevalence by roughly 4–5x by eliminating the abandonment alternative. The true question for production systems is whether that ~15% is random noise or a behaviorally coherent segment worth modeling.

**Where simplification is fine:** For aggregate ranking evaluation, offline metrics, and most A/B testing, the serial assumption produces useful rankings. The regression phenomenon matters most at the session level — understanding individual search episodes, detecting struggle, and modeling the foraging dynamics within a single query.

**Notebooks:** [regression_decisions.ipynb](../notebooks/regression_decisions.ipynb), [scroll_kinematics.ipynb](../notebooks/scroll_kinematics.ipynb)

## 10. Mouse proximity predicts click — and reveals the consideration set

Gaze-cursor distance during fixations on a result predicts whether that result will be clicked. Per-result `min_dist` thresholds (NB15, post coordinate-space audit 2026-04-12, **N = 13,419 records / 2,340 trials / 16.6% click rate**) [NB15:K1]:

| Threshold | Prevalence | Click rate | Lift |
|---|---|---|---|
| min_dist < 58px | 14.6% | 42.7% | 2.6× |
| min_dist < 100px | 28.2% | 37.7% | 2.3× |
| min_dist < 150px | 41.3% | 32.3% | 1.9× |

Closer approach → higher click probability. The gradient is monotonic and strong.

**The "almost clicked" segment.** **8.4%** of all result-position records (**1,122 / 13,419**) had `min_dist < 58px` and were not clicked — the consideration set made visible. These received **more fixations** than clicked results (24.0 vs 24.4 mean). Users evaluated them deeply, moved the cursor close, then chose something else. [NB21:K15] ("Evaluated-rejected" class) contains **974 records (7.3% of corpus)** in the classifier-derived taxonomy, or **439 records (3.3%)** using the NB22 cursor-approach + regression definition.

**Why this matters for production.** Click models treat non-clicks as ambiguous — maybe the user examined the result and found it irrelevant, maybe they never saw it. Mouse proximity resolves this ambiguity without eye tracking. A non-clicked result where `min_cursor_distance < 100px` is a high-confidence **evaluated-and-rejected** signal. A non-clicked result where the cursor never approached is **unseen or unconsidered**. These carry opposite relevance implications.

Huang, White & Buscher (2012) showed cursor proximity is the best single predictor of gaze location, but used it to predict *where* the eyes were, not to infer *what the user thought* about what they saw. The step from gaze prediction to implicit relevance judgment — particularly for unclicked results — appears to be novel.

The signal is deployable from standard mouse telemetry: `min_cursor_distance_to_result_center` per impression. No eye tracker needed. The eye tracking in AdSERP validates the interpretation (mouse proximity during genuine visual evaluation, not accidental hover), but the production metric is cursor-only.

**Notebooks:** [individual_differences.ipynb](../notebooks/individual_differences.ipynb)

## 10b. Cursor approach-retreat: the consideration set has a motor signature

Cursor approach-retreat goes beyond proximity. During evaluation, the mouse makes partial approach movements toward results that are ultimately rejected. This is a covert evaluation signal with a distinctive motor signature:

Four-class taxonomy (NB22, regression-based split, post coordinate-space audit 2026-04-12):

| Category | N | % | Retreat (px) | Gaze Dwell (ms) | Dwell in Proximity (ms) |
|----------|---|---|---|---|---|
| **Clicked** | 2,228 | 16.6% | — | — | — |
| **Deferred** (approached + regressed to) | 1,916 | 14.3% | 234.5 | 4,137 | 1,212.5 |
| **Evaluated-rejected** (approached + no regression) | 439 | 3.3% | 90.8 | 1,612 | 690.0 |
| **Not approached** | 8,836 | 65.8% | — | — | — |

Motor signature separation: deferred vs rejected shows **2.6× retreat distance (234.5 vs 90.8 px, p = 1.76 × 10⁻³⁸)**, **2.6× gaze dwell (4,137 vs 1,612 ms, p = 9.76 × 10⁻⁷⁰)**, **1.8× proximity dwell (1,212.5 vs 690.0 ms, p = 1.36 × 10⁻¹⁶)** [NB22:K5–K7]. All three separations strengthened dramatically with the fixation-side coordinate fix (retreat-distance p went from 10⁻¹¹ to 10⁻³⁸, gaze-dwell p went from 10⁻²⁶ to 10⁻⁷⁰).

**Approach predicts regression.** **81.6%** of approached results get regressed to (odds ratio **3.21×**, χ² = 661.1, p = 8.72 × 10⁻¹⁴⁶) [NB15:K6–K7]. Approach + regression → **37.9%** click rate (N = 3,087). Approach + no regression → **36.9%** (N = 696). No approach + regression → **8.1%** (N = 5,589). No approach + no regression → **8.6%** (N = 4,047) [NB15:K8–K11].

**Scroll doesn't carry this signal on desktop.** Scroll dwell and deceleration during regression are identical for clicked vs non-clicked results (all p > 0.3, notebook 17). The scroll is ballistic transportation; the cursor is the evaluation probe. On mobile, where scroll is the only motor channel, this may differ.

**Element-type cost surprise.** Top ads show the highest pupil dilation during evaluation (+0.41%), contradicting the prediction that ads are cheaper to evaluate. Users may work harder to discriminate ads from organic results (notebook 16).

**Element-type approach signatures confirm this from motor data (notebook 20).** Top ads have 2× the approach rate (42.9% vs 21.0% organic), 50 px more retreat (279 vs 228 px, p = 7×10⁻⁸), 2.3× longer dwell in proximity (4,586 vs 2,023 ms for clicked results, p = 3×10⁻¹³), and 1.7× more direction changes (2.7 vs 1.6). All effects survive position controls. Azzopardi's C/W/L cost framework (SIGIR 2018) is overturned for top ads — discrimination cost outweighs reading cost. Native ads show avoidance: lowest approach rate (17.5%), largest cursor distance, lowest click rate (8.0%).

**Notebooks:** [cursor_approach.ipynb](../notebooks-v2/15_cursor_approach.ipynb), [element_type.ipynb](../notebooks-v2/16_element_type.ipynb), [scroll_retreat.ipynb](../notebooks-v2/17_scroll_retreat.ipynb), [approach_by_element.ipynb](../notebooks-v2/20_approach_by_element.ipynb). Detailed findings: [findings-approach-retreat.md](findings-approach-retreat.md).

**Deep dive:** [findings-approach-retreat.md](findings-approach-retreat.md)

**Notebooks:** [15_cursor_approach.ipynb](../notebooks-v2/15_cursor_approach.ipynb), [16_element_type.ipynb](../notebooks-v2/16_element_type.ipynb), [17_scroll_retreat.ipynb](../notebooks-v2/17_scroll_retreat.ipynb)

## 11. Two orthogonal individual difference dimensions

Per-participant correlations across 46 participants reveal two independent axes of variation:

**Dimension 1: Deliberation style.** TTI-to-first-scroll, regression rate, LHIPA (cognitive load), fixation count, and trial duration are all highly intercorrelated (Spearman ρ = 0.57 to 0.94). This is the satisfice/optimize axis: some users evaluate quickly with few regressions and low cognitive load (satisficers), others take longer with more re-evaluation and higher load (optimizers). Regression rate × LHIPA: ρ = −0.568 (p < 0.001) [NB11:K12].

**Dimension 2: Motor coupling.** Gaze-cursor lag (median −650 ms, gaze leads) [NB11:K1] is a reliable individual trait (split-half reliability 0.838 Spearman–Brown corrected, raw r = 0.721) [NB11:K3] but is **uncorrelated** with any deliberation measure (lag × TTI: ρ = −0.072 ns; lag × LHIPA: ρ = −0.149 ns; lag × regression rate: ρ = +0.159, p = 0.293) [NB11:K9–K11]. Some people keep their cursor tracking their eyes; others park it. This style is stable across trials but orthogonal to how deliberate the search strategy is.

The gaze-cursor lag replicates Huang, White & Buscher (2012) in direction and magnitude (our −650 ms vs their −700 ms, both gaze-leads) [NB11:K1] but extends it: the lag is a stable trait that varies independently of search depth.

**Notebooks:** [individual_differences.ipynb](../notebooks/individual_differences.ipynb), [gaze_cursor_lag.ipynb](../notebooks/gaze_cursor_lag.ipynb)

---

## v4 corrections

**Viewport time computation (v3 → v4):** The prior `compute_viewport_time` only counted time between scroll events. Pre-scroll periods (page load → first scroll, where position 0 is visible the entire time) and post-scroll periods were dropped. This caused position 0 dwell ratios >1.0 (e.g., 13,000ms fixation on 183ms computed viewport — a 73x ratio). Fixed by covering the full trial window. Position 0 dwell ratio corrected from 1.35 → 0.28.

**Forward-only shape test (new):** Isolating forward-scanning periods (excluding scroll regressions), the gaze dwell ratio *increases* with position (Spearman ρ = +0.73 on position means 0-8 (corrected to +0.82 after FPOGY clamp in v5), permutation p = 0.98 against priming). Users dwell longer on later results during first-pass scanning — reflecting growing comparison-set cost. (Note: this was initially interpreted as increasing cognitive load from working memory accumulation. §3b-iv subsequently showed cognitive load *decreases* with position via Butterworth LF/HF. The dwell ratio increase reflects comparison cost with compiled — not accumulating — criteria.) The aggregate partial r = -0.060 was driven by regressions, but this does not indicate priming: lower dwell on revisit is expected from repetition/recognition (the user already encoded the content), and is further confounded by ballistic backward scroll dynamics that create systematically shorter viewport windows at intermediate positions (see `scroll_kinematics.ipynb`). The within-position test is null for regression trials too.

**Metric rename:** "Eval rate" / "attention density" → "gaze dwell ratio" (fixation duration / visible duration). Both numerator and denominator are durations in ms; the result is a dimensionless ratio, not a rate.

## v5 corrections (2026-04-02)

**FPOGY out-of-bounds clamp (fixation attribution bug).** The Gazepoint GP3 HD reports gaze Y coordinates that exceed the screen boundaries — 24.5% of fixations have FPOGY > screen_height (1024px), with the 95th percentile at 1830px. These out-of-bounds samples were added to `scroll_offset` to compute `page_y`, attributing fixations to SERP positions below the viewport. Position 9 was the primary victim: mean per-trial dwell ratio was 2.9× (89% of trials >1.0). The fix: clamp `FPOGY` to `[0, screen_height]` before computing `page_y = fy + scroll_offset`. Position 9 dwell ratio corrected from 1.25 → 0.79. Forward-only shape test strengthened slightly (ρ from +0.73 to +0.82).

**Anyone working with AdSERP fixation data** should be aware that FPOGY values can substantially exceed screen bounds. Always clamp or filter gaze coordinates to the viewport before mapping to page-space positions.

---

*v12, 2026-04-12. v12: §0 ski-jump rebuilt on post-fix data — full-corpus uptick at pos 10 does not survive the coord audit; the rank-9 uptick only survives in the homogeneous cohort A (plain-top, ≥10 organic, reached rank 9, n=131). v11: Key Claims refs + stale value corrections. v10: element-type approach-retreat. v9: coordinate-space audit post-fix values. v8: approach-retreat motor signature. v7: ski-jump decomposition (§0); task model OSEC (§3b); SERP difficulty (§3c); reading episode pooling (§3d). v6: §9 relaxing serial evaluation. v5: FPOGY clamp; ballistic kinematics confound. v4: viewport time bug fix; forward-only dwell reversal (ρ = +0.73). v3: within-position controls null. v2: regression-stratified split. v1: aggregate priming correlation.*
