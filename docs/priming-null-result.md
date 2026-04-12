# The priming conjecture — null result, with a more interesting alternate explanation

*A standalone record of a hypothesis that drove years of this research, turned out to be wrong, and led to something better.*

## TL;DR

The priming conjecture was: as users scan down a SERP, they accumulate vocabulary from prior results, and that redundancy should make later results cheaper to evaluate. Tested at four granularities — bag-of-words Jaccard overlap, sentence-level semantic embeddings, within-position controls, and survey-to-evaluate vocabulary transfer — **all null**.

What the pupil data pointed to instead was **framework compilation**: users build evaluation criteria at the first result and apply them with decreasing effort thereafter. The dwell-time decline at later positions is not priming from repetition; it is compiled criteria doing less work per comparison. That reframe is documented in [findings.md §3a–§3b-iv](findings.md#3a-evaluation-time-decomposes-into-four-independent-components).

## The original conjecture

By position 5 on a typical product-search SERP, roughly 55% of a result's words have already appeared in earlier results. This is not noise — it is the structural consequence of retrieval: if ten results are returned for "buy winter jacket", the word "jacket" is in all ten, the word "winter" is in most, and the brand and feature words overlap heavily across the top candidates. The hypothesis was that this cumulative vocabulary exposure should make later results *faster* to evaluate: your visual system has already processed many of the tokens, so each successive result costs less.

The intuition came out of two decades of working on search and cursor instrumentation (Lucidity → Optimoz → Uzilla 2003 → ClickSense) where the position-by-dwell curve was a familiar shape, and the prevailing explanations — "position bias", "satisficing" — always felt incomplete. Priming was attractive because it gave the curve a *mechanism* at the vocabulary level rather than treating it as a consequence of giving up.

I presented this idea at the CHIIR 2021 workshop as a proposal for how to decompose the position-by-dwell curve into a content-driven component. The AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025) finally made it testable: simultaneous eye tracking and SERP HTML snapshots across 2,776 trials, enough content to compute overlap at multiple granularities and enough trials to detect a small effect.

## What we tested

Four granularities, ordered from coarsest to finest.

### 1. Bag-of-words overlap × evaluation metrics (within-position)

For each result at position *i*, compute the Jaccard overlap between its tokenized snippet and the union of all previously-fixated snippets at positions 0…*i*−1. Correlate with five evaluation metrics, controlling for position (within-position partial correlation).

| Metric | Within-position *r* | Significant at any position? |
|---|---|---|
| Total fixation time (TFT) | *r* ≈ 0 at all positions | No |
| Fixation count (TFC) | *r* ≈ 0 at all positions | No |
| Mean single-fixation duration | *r* ≈ 0 at all positions | No |
| Viewport time | *r* ≈ 0 at all positions | No |
| Gaze dwell ratio (fixation / viewport) | *r* = −0.049 at position 1 only, *p* = 0.01 | Marginal, one position |

Null at every metric, every position, except a single marginal effect at position 1 that does not hold up to any reasonable multiple-comparison correction.

### 2. Sentence-level semantic embeddings

Bag-of-words was the obvious first cut but it ignores synonyms, paraphrase, and partial matches. We re-tested using `mxbai-embed-large` embeddings: cosine similarity between each result's snippet embedding and the centroid of all prior result embeddings, again controlling for position.

Also null within-position. Sentence-level semantic similarity does not predict evaluation time any better than bag-of-words.

### 3. Forward-only isolation

The aggregate (ignoring forward vs regression direction) showed a small negative correlation, *r* = −0.054, *p* = 2.4 × 10⁻⁹. This is the number I would have reported if I had stopped at the aggregate.

It turned out to be a position-overlap confound. Both overlap and position decline monotonically down the SERP — higher positions naturally have more overlap *and* less dwell — and the correlation reflected this joint monotonicity, not content-driven priming. Isolating forward-scanning periods (excluding regressions) made the effect disappear.

Worse, the forward-only curve *reversed* the prediction: gaze dwell ratio (fixation time divided by viewport time) **increases** with position in forward scanning (Spearman ρ = +0.82). Users dwell *longer* on later results during first-pass scanning, not less. The naive "working memory overload" explanation would predict this, but per-position pupillometry (§3b-iv in findings.md) shows cognitive load *decreasing* with position. So it is not overload either.

### 4. Survey-to-evaluate vocabulary transfer

The fourth and strongest test, proposed as a rescue for the hypothesis: maybe priming operates not across results in a single forward pass but from the Survey phase (the ~1.3s gist sweep at the top of the trial) into the subsequent Evaluate phase. If users build a lexical context during Survey that primes subsequent reading, then results whose vocabulary is well-represented in the survey-fixated results should get faster evaluation.

Tested on 24,025 forward-only evaluate episodes at non-surveyed positions. Mean survey-vocabulary overlap with the evaluated result was 0.31.

| Test | Result |
|---|---|
| Overall ρ (overlap × episode duration) | 0.011, *p* = 0.094 |
| Overall ρ (overlap × fixation count) | 0.012, *p* = 0.063 |
| Within-position | All *p* > 0.06 |
| Tercile split — low vs high overlap duration | 689 ms vs 718 ms, Kruskal–Wallis *p* = 0.10 |

Null at every position. Low-overlap episodes are if anything *slightly* faster, which is the wrong direction. The survey's output is a strategy decision (how much effort to invest in the Evaluate phase), not a processing facilitation.

### 5. p(fixate | visible) — the skip-rate version of the hypothesis

If priming causes users to *skip* high-overlap results entirely rather than fixate them faster, the signal would live in the binary fixation decision, not dwell duration. We tested this separately (findings.md §2a).

Also null in forward scanning. The structural reason is that forward-only p(fixate) is ~99.8% at every position — users fixate virtually everything visible during first-pass scanning. There is no skip decision to predict in forward mode; the variance that overlap could explain does not exist. The 12.5% overall skip rate is concentrated in regression trials and late-trial positions where viewport windows are short, and it is not predicted by content overlap either.

## What the investigation uncovered instead

The more interesting question, once priming was ruled out, became *why* dwell time declines with position at all if content overlap is not the mechanism. The pupil data answered it.

**Per-position cognitive load decreases with position, not increases** (Butterworth LF/HF, ρ = −0.927, *p* < 0.0001; findings.md §3b-iv). Load peaks at position 0 where the user is building evaluation criteria from scratch, drops steeply through positions 0–3, then plateaus. By position 4 the framework is built and load stays flat all the way down.

This is **framework compilation**: the user becomes a domain-specific expert evaluator within a single SERP scan. The first result is expensive because the user is constructing selection criteria — "I want this price range, this brand tier, these features". Subsequent results are cheaper because the criteria are already compiled; each comparison just matches a candidate against a fixed rubric.

The dwell-ratio increase at later positions (+0.82) then has a clean explanation: the comparison set grows as more results are inspected, so time-per-decision grows too, but the *cognitive cost per unit time* drops because the criteria are already compiled. The time-load dissociation is the fingerprint of a compilation process, not a priming process.

Framework compilation reframes the position-by-dwell curve from "declining effort" to "declining cost of compiled evaluation", and it does so with an independent measurement (pupil dilation) that is not part of the priming test at all. The reframe is stronger than the original hypothesis would have been, because it makes a second, testable prediction (load should peak at position 0 and plateau by position 3), which the data supports.

## What would still be worth testing

One priming granularity remains untested: **token-level fixation analysis**. Map individual eye fixations to specific words on the page, and test whether previously-encountered tokens receive shorter fixations within a given result. This would be priming at the perceptual level — the visual system recognizing a word faster on its second exposure — rather than at the result-summary level where all four tests above operated.

This is technically tractable on AdSERP (fixation resolution is ~1 character) but requires word-level bounding boxes, which means rendering each SERP in a headless browser and extracting per-word text layout. It is on the [TODO.md](../TODO.md) but not a priority now, because the framework-compilation reframe already explains what the original conjecture was trying to explain, and because a token-level effect — if it exists — would be a psycholinguistic finding about word recognition rather than a model of SERP evaluation strategy. It is a different paper.

The other open direction is testing the whole sequence at scale on production logs with larger *N* and naturally-varying SERP compositions. AdSERP has 2,776 trials across 60 unique queries; a production-log test would have orders of magnitude more, and the residual signal — if there is one — might become visible. This is also on the TODO but requires production log access.

## Related reading

- [findings.md §2](findings.md#2-cumulative-content-overlap-does-not-predict-evaluation-speed) — the null results in their original analytic context, with the full statistical tests.
- [findings.md §2a](findings.md#2a-p-fixate-visible-is-also-null--and-structurally-uninformative-for-forward-scanning) — the skip-rate version of the hypothesis.
- [findings.md §3a–§3b-iv](findings.md#3a-evaluation-time-decomposes-into-four-independent-components) — the framework-compilation reframe.
- [notebooks-v2/08_priming.ipynb](../notebooks-v2/08_priming.ipynb) — the code behind the null tests, all four granularities.
- [notebooks-v2/14_butterworth_cognitive_load.ipynb](../notebooks-v2/14_butterworth_cognitive_load.ipynb) — the per-position cognitive load measurement that grounds the compilation account.
- CHIIR 2021 workshop talk — the original presentation of the conjecture, now superseded by this writeup.

## On being wrong

The priming conjecture drove this project for longer than it should have. Framework compilation is a better answer to the original question and came out of the same investigation, so calling the result "null" undersells what was learned. But the specific hypothesis was wrong, and recording that explicitly matters more than salvaging it. The discipline of committing to a falsifiable prediction and then accepting the verdict is what made the better answer visible — if I had treated the aggregate *r* = −0.054 as a weak confirmation and moved on, the framework-compilation finding would never have surfaced.

Keeping this as a standalone document rather than a footnote in the main README is deliberate: the failure mode in research is usually not "I tested a bad hypothesis" but "I tested a plausible hypothesis and the null result was too quiet to hear". Writing down a good idea that did not work, and what it led to, is the only way to keep the signal from the second kind of outcome.
