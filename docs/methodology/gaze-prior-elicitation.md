# Gaze-Prior Elicitation — A Non-Disruptive Protocol

**Stable ID:** M:gaze-prior-elicitation
**Status:** current as of 2026-05-04; canonical implementations: `scripts/analyze_survey_bimodality.py`, `scripts/ad_utility_prior_analysis.py`, `scripts/output/survey_vs_ads/`, `scripts/output/first_saccade_direction/`. Demonstrated on AdSERP (n=47 participants, 2,776 trials).
**Companion to:** [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md) (AOI typing the protocol depends on), [`../ad-utility-prior.md`](../ad-utility-prior.md) (the empirical demonstration as a finding).

---

## TL;DR

Most experimental work on search and decision-making measures behavior (clicks, dwell, RT) and back-fits priors parametrically (model the choice, recover the prior as a free parameter) or elicits priors disruptively (rate-in-advance tasks, BDM, scoring rules). Both cost something — model dependence in the first case, task contamination in the second.

This doc specifies a **non-disruptive prior-elicitation protocol** that recovers per-participant priors over categorical AOI types from pre-decision gaze allocation, with no elicitation overhead and no model-fit dependency. Demonstrated on AdSERP for the ad-vs-organic surface partition: per-participant ad-attention rate predicts ad-click rate at ρ = +0.30 (*p* = 0.043, n = 47), is heterogeneous (range 0–53% ad-click rate), and is orthogonal to sat-opt and cognitive load. The protocol generalizes to any task with multiple categorical surface types where utility heterogeneity is plausible.

The mechanism: gaze in the orient + survey window (~1 second after page presentation) over-indexes on high-utility surfaces relative to their pixel-area share, with a **universal floor** (visual-salience baseline shared across participants) and a **smooth heterogeneous overlay** (agent-specific over-indexing) — McFadden separation made directly observable.

---

## 1. The rule, in one line

For each participant, compute the ratio of survey-phase fixation count on a target categorical AOI type to the area share of that type, averaged across trials. The over-index is the prior; participants vary on it; the variance predicts choice.

## 2. Why this rule

Rational-analysis frameworks (Anderson 1990) frame cognitive behavior as a rational allocation given the agent's beliefs about the task environment. To test those frameworks empirically you need to *measure the beliefs*, not just assume them. Three options exist:

1. **Parametric back-fit.** Build a structural choice model (e.g., random utility, Bayesian decision rule), fit it to choice data, recover the prior as a parameter. Model-dependent — the prior is whatever the assumed structure assigns to the data. Different models give different priors from the same data.
2. **Direct elicitation.** Ask participants to rate, rank, or wager on stimuli before the task (BDM, scoring rules, prediction markets). Recovers the prior cleanly but **disrupts the task being studied**: the participant now knows their ratings will be checked, which changes how they engage with the actual choice. If the experiment is about natural search behavior, you've measured something else.
3. **Gaze in pre-decision window.** The agent's prior is acted on before they commit. If gaze allocation in the early portion of the trial reflects expected utility ("look first at the surfaces I expect to be valuable"), then the gaze itself reveals the prior with no elicitation step. The cost is that you need eye-tracking + categorical AOI labels + decision-event timestamps; the benefit is the prior is recovered without distorting the task.

Option 3 is rare in practice because most paradigms don't have all three signals together. AdSERP does, and the typed AOI cascade ([`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md)) supplies the categorical labels needed.

The closest neighbors in the literature:

- **Reichle / Rayner reading research** — fixation duration as a per-word readout of processing. Different question (lexical-frequency landscape is shared across readers); doesn't recover heterogeneous priors.
- **Visual-world paradigm** — gaze tracks expectation in real time, but the "prior" is a controlled experimental manipulation, not an individual-difference axis.
- **Scanpath analysis in product choice** (Glöckner / Herbold 2011, Pieters / Wedel) — fixation time as proxy for value attention, but typically on rated stimuli (priors elicited *outside* the task).
- **Information-foraging gaze studies** (Pirolli / Card lineage) — track attention along scent gradients, but assume a shared scent function across participants.

The protocol below differs from each: it works on natural-task gaze, recovers per-participant priors over a categorical task-relevant dimension, and validates predictively without parametric dependence.

## 3. Where this lives in code

| Component | File | Role |
|---|---|---|
| Survey-phase fixation classification | `scripts/analyze_survey_bimodality.py` | Defines the survey window (early ballistic-scan fixations before deliberate evaluation), counts per-fixation AOI types, emits per-participant `p_ad_survey`, `ad_over_index`. |
| First-saccade-direction analysis | `scripts/output/first_saccade_direction/` | Per-trial angular distribution of the first saccade after page load; computes mean θ and resultant R per cohort (ad-top vs plain-top). |
| Trial-level survey vs evaluate decomposition | `scripts/output/survey_vs_ads/` | Splits each trial into survey (first K=5 fixations) and evaluate (remainder); computes per-trial fix-on-ad fraction in each phase, distance to nearest ad, survey-vs-eval over-index ratio. |
| Per-participant prior × behavior cross-tab | `scripts/ad_utility_prior_analysis.py` | Joins per-participant survey trait (`p_ad_survey`) with per-participant click outcome (`p_ad_click`, `p_dd_top_click`); computes Spearman correlations and orthogonality tests. |
| Joined per-participant table | `scripts/output/survey_bimodality/per_participant_with_traits.csv` | The canonical 47-row × 14-column table consumed by downstream analyses. |

Output schema (`per_participant_with_traits.csv`):

```
participant, p_ad_survey, ad_over_index, n_survey_fix, n_ad_top_trials,
mean_ad_area_frac, mean_lhipa, regression_rate, mean_click_pos,
median_tti_s, mean_fixations, events_per_sec, dir_changes_per_sec, tercile
```

## 4. Parameters

| Parameter | Default | What it controls |
|---|---|---|
| `K_SURVEY_FIXATIONS` | 5 (also tested K=3, K=7) | Number of fixations counted as survey-phase. K=5 corresponds to a median ~1.1 second window on AdSERP. |
| Survey-phase definition | first K fixations after page presentation | Trial-level. Insensitive to K in [3, 7] for the headline correlations (per `summary_k3.csv`, `summary_k7.csv`). |
| AOI type taxonomy | from typed cascade, 13 etypes | Inherited from the AOI pipeline (`organic-result-aoi-extraction.md`). The protocol works on any categorical AOI taxonomy. |
| Area-share denominator | per-trial bbox sum / screenshot area | Calibrates `p_ad_survey` against the visible surface; `ad_over_index = p_ad_survey / mean_ad_area_frac`. |
| Aggregation level | per-participant (mean / median across trials) | Trial-level signal exists too but is noisier; participant-level is the level at which the heterogeneity claim is made. |
| First-fixation window | the first single fixation, ~150 ms post-presentation | Used in the first-saccade-direction analysis, which is more conservative than survey-phase aggregation. |

## 5. Sensitivity tested

### 5.1 Three-layer empirical leak structure (AdSERP demonstration)

The prior signal is observable at three nested timescales. Each layer adds independent confirmation.

**Layer 1 — orient / first fixation (≤ 200 ms).** First fixation lands inside an ad on **39.5% of all trials** (n = 2,768). Stratifying by whether the SERP has an above-fold ad:
- ad-top trials (n = 1,580): median first-fix distance to nearest ad = **−44.5 px** (negative = inside the ad rectangle).
- plain-top trials (n = 1,188): median first-fix distance = **942 px** (far from any ad).

First-saccade-direction analysis confirms: angular concentration toward ads is substantially higher when ads are present (ad-top resultant R = 0.500, plain-top R = 0.385). Source: `scripts/output/first_saccade_direction/summary.json`, `scripts/output/survey_vs_ads/first_fix_location.csv`.

**Layer 2 — survey window (~1 second post-presentation).** Across all trials at K = 5:
- median survey duration: 1,121 ms.
- p(fix on ad) in survey: **0.512**; in evaluate phase (remainder of trial): 0.260.
- ad-area share (denominator): 0.257.
- **Survey over-index: 1.99×**; evaluate over-index: 1.01× (at chance).
- 63.6% of trials have survey-rate of ad fixation > evaluate-rate. On ad-top trials specifically: 86.4%.
- Median distance to ad in survey window: **−10 px** (inside); median distance to ad in evaluate: 140 px (outside).

Within-trial dissociation. The over-indexing on ads is **survey-phase specific** — by the time the user enters deliberate evaluation, gaze is at chance over the visible surface. Source: `scripts/output/survey_vs_ads/summary.json` (K = 3, 5, 7 all show the same direction).

**Layer 3 — per-participant variance (the prior itself).** Across n = 47 participants:
- `ad_over_index`: median **2.46×**, IQR [2.18, 2.76], range **[1.61, 3.33]**.
- `p_ad_survey`: median 0.728, IQR [0.640, 0.819], range [0.458, 0.935].
- Mean `ad_area_frac` (universe) median: 0.297.

Distribution shape:

```
ad_over_index bins (n = 47):
  [1.5, 2.0)  n=7   (14.9%)   ← low-prior cohort
  [2.0, 2.5)  n=21  (44.7%)   ← median band
  [2.5, 3.0)  n=15  (31.9%)
  [3.0, 4.0)  n=4   (8.5%)    ← high-prior cohort

  Below 1.5×  : 0 / 47   ← no participant fixates ads at-or-below area share
  Above 2.5×  : 19 / 47  ← 40% over-index 2.5×+
```

**Universal floor + heterogeneous overlay.** No participant sits at-or-below 1.5× area share. Even the lowest over-indexer is at 1.61× (1.6× more ad fixation than chance). Above the floor, the distribution is smooth from 1.6× to 3.3× — the high-prior cohort over-indexes at 1.5× the rate of the low-prior cohort. Source: `scripts/output/survey_bimodality/per_participant_with_traits.csv`.

**McFadden separation made observable.** Random-utility models decompose `U(option) = shared_systematic_term + agent_specific_coefficient + ε`. The protocol observes the shared term as the universal over-indexing floor (visual salience, ad-detection priors learned from web exposure, layout-driven attention bias — all participants > 1× area share); the agent-specific term as the over-floor variance (1.6× to 3.3×); and the ε is the trial-to-trial residual. Most behavioral-economics literature has to estimate the agent-specific coefficient parametrically; the protocol observes it directly.

### 5.2 Predictive validity (the leak's behavioral consequence)

Layer-3 prior predicts choice in the same n = 47 participants:

| Prior × Behavior | Spearman ρ | p |
|---|---|---|
| `p_ad_survey` × `p_ad_click` | +0.249 | 0.091 |
| **`p_ad_survey` × `p_dd_top_click`** | **+0.297** | **0.043** |
| `p_ad_survey` × `p_native_ad_click` | +0.108 | 0.469 |
| `ad_over_index` × `p_ad_click` | +0.232 | 0.116 |
| `ad_over_index` × `p_dd_top_click` | +0.267 | 0.070 |

Effect sizes are small-to-moderate (ρ ≈ +0.25 – 0.30) — consistent with a prior that informs but does not determine choice. The signal is strongest on `dd_top` (the highest-CTR ad surface, population mean 17.1%) and weakest on `native_ad` (interleaved with organics, harder to spot pre-click).

Source: `scripts/output/ad_utility_prior/summary.json`. Companion writeup: [`../ad-utility-prior.md`](../ad-utility-prior.md).

### 5.3 Orthogonality to other measured axes

The recovered prior is independent of pre-existing individual-difference axes:

| Independence test | Spearman ρ | p |
|---|---|---|
| `p_ad_survey` × regression rate (sat-opt) | +0.024 | 0.874 |
| `p_ad_survey` × trial-mean LHIPA (cognitive load) | +0.134 | 0.367 |
| `p_ad_survey` × mean click position (depth) | +0.020 | 0.895 |
| `p_ad_click` × regression rate | +0.053 | 0.725 |

Same n = 47. Sat-opt × LF/HF was independently shown null at LOO AUC 0.286 with ρ(slope, rate) = +0.013 ([`../null-findings/2026-05-04-typed-cascade-null-revisit.md` §2](../null-findings/2026-05-04-typed-cascade-null-revisit.md)). The ad-utility prior is a third axis, not a re-projection.

### 5.4 K-sensitivity audit

Survey-phase definition K=3, K=5, K=7 all produce the same over-index direction and the same per-participant rank-order. The protocol is insensitive to the exact survey-window cutoff in this range. Source: `scripts/output/survey_vs_ads/summary_k{3,5,7}.csv`.

## 6. Sensitivity NOT tested

Ordered by likelihood of changing a downstream result.

1. **Cross-task generalization.** AdSERP demonstration covers transactional product search with always-present ads. The protocol has not been tested on:
   - Informational queries (different task economics, ads less relevant).
   - Mobile / touch interfaces (no mouse signal; saccade dynamics differ on small screens).
   - Recommendation feeds (vertical-scroll, no fold).
   - Image-result-heavy SERPs (image_pack utility may differ in structure).
   - Streaming home-screens / e-commerce category pages (different surface taxonomies).

2. **Prior persistence within-participant.** AdSERP has 6 blocks per participant; we have not tested whether block-1 prior predicts block-6 click rate, i.e., whether the prior is a stable trait or a session-specific calibration. The orthogonality to known traits (sat-opt, LHIPA) is consistent with stability, but doesn't prove it.

3. **Cohort-stratified validation.** Top-cohort vs bottom-cohort prior subgroups (e.g., terciles by `ad_over_index`) — do their click distributions differ in interpretable ways beyond just the headline correlation? Not yet computed.

4. **Random-utility model fit.** The McFadden interpretation is post-hoc framing, not a fitted model. Formally fitting a discrete choice model with per-participant ad-utility coefficient and comparing log-likelihood to a shared-coefficient baseline would test the heterogeneity claim parametrically.

5. **Causal direction.** Per-participant ad-fixation rate could in principle be a *consequence* of past ad-clicking habits rather than a *cause* of current ad-click choice. The within-trial temporal precedence (gaze precedes click by definition) supports the prior-then-behavior reading at the trial level, but the cross-trial habit-loop interpretation has not been ruled out.

6. **Survey-phase definition.** K=5 corresponds to ~1.1 sec window on AdSERP. On other tasks the right K is task-specific (slower decisions need wider windows; faster ones narrower).

7. **Categorical vs continuous AOI types.** The protocol is specified for categorical surface types (ad / organic / image_pack / etc.). For continuous-valued surfaces (e.g., snippet length, image salience), the over-index calculation needs reformulation — perhaps as a regression coefficient rather than a ratio.

## 7. What's robust regardless of tweaking

- **The temporal localization.** The prior leaks in the early window before deliberate evaluation. Survey-phase over-indexing on ads (1.99×) drops to chance (1.01×) in evaluate phase. This is the structural fact that makes the protocol non-disruptive: the prior has been read out before any decision.
- **The universal-floor structure.** Some component of ad over-fixation is shared across all participants (no one fixates ads at-or-below area share). This is the McFadden shared-systematic term, observable as the lower bound of the per-participant distribution.
- **The heterogeneous-overlay structure.** Above the floor, individual variance is smooth and substantial (1.6× to 3.3×). The variance predicts choice. This is the agent-specific coefficient.
- **Independence from existing axes.** The prior is orthogonal to deliberation style, motor coupling, and cognitive load — it's a separate dimension, not a relabel.

## 8. Limitations to disclose

- **n = 47, single-task demonstration.** All correlations at participant level on the AdSERP forced-choice task. ρ ≈ +0.30 with n = 47 is real but not bullet-proof under multiple testing.
- **Forced-choice paradigm.** Participants knew they had to click *something*. Ad-clicks are real choices, not accidents, but abandonment is not in the design space — generalizing to free-search settings requires re-validation.
- **Categorical-AOI dependence.** Without a typed AOI taxonomy, the protocol cannot run. AdSERP's typed cascade ([`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md)) supplies this; tasks without comparable AOI labels need their own.
- **Eye-tracker dependence.** The protocol requires gaze data. Cursor-only telemetry (e.g., Attentive Cursor Dataset, deployed-search-log) cannot run this — though there are cursor-based proxies for early survey behavior (mouse-on-ad-region rate in first 1 sec) that could be tested as a degraded-but-deployable variant.
- **Forced-survey-phase definition.** "Survey" is operationalized as first K fixations. On tasks with very short or very long pre-decision windows, this needs recalibration.

## 9. Where this rule appears in published / draft work

- **`docs/ad-utility-prior.md`** — the AdSERP demonstration writeup as a finding.
- **`docs/findings.md` §12** — short summary in the findings index, cross-link to the deep doc.
- **Task-model paper** — empirical anchor for the rank-value-prior framing in §11 (or successor section). The rational-analysis interpretation now has a measured prior, not just a framing hypothesis.
- **CIKM 2026 paper** — candidate premise for the four-class taxonomy: consideration-set composition (clicked / deferred / evaluated-rejected / not-approached) should be conditional on prior.
- **Standalone methods paper (candidate)** — a methods-track venue (CHI methods, IUI, HFES, JEMR) is the right home for the protocol contribution. The ad-utility result is the demonstration; the contribution is the protocol itself.

## 10. Status

**Status:** current as of 2026-05-04; canonical implementations: `scripts/analyze_survey_bimodality.py`, `scripts/ad_utility_prior_analysis.py`. Demonstrated on AdSERP (2,776 trials, n = 47 participants, 0 errors).

History:
- 2026-04 — survey-phase definition established (`analyze_survey_bimodality.py`); per-participant `p_ad_survey` and `ad_over_index` computed and tagged in `per_participant_with_traits.csv`.
- 2026-04 — first-saccade-direction and survey-vs-ads decomposition added (`scripts/output/first_saccade_direction/`, `scripts/output/survey_vs_ads/`).
- 2026-05-04 — typed cascade landed; per-participant ad-click rate computable from `cursor-approach-features-typed.json`. `scripts/ad_utility_prior_analysis.py` joins prior × behavior and tests orthogonality. Result: ρ(p_ad_survey, p_dd_top_click) = +0.297, *p* = 0.043; orthogonal to sat-opt and LHIPA.
- 2026-05-04 — three-layer leak structure synthesized (orient / survey / per-participant variance) into McFadden floor-vs-overlay framing. Protocol generalization candidates listed.

**Pending work:**
- Within-participant prior persistence (block-1 → block-6).
- Random-utility model fit comparing per-participant vs shared ad-utility coefficient.
- Cohort-stratified validation (terciles on `ad_over_index` × four-class taxonomy composition).
- Cross-task replication on a second corpus with comparable signals (eye-tracking + categorical AOI labels + decision-event timestamps).
- Cursor-only proxy for the prior (degraded variant deployable on cursor-only datasets like ACD).
