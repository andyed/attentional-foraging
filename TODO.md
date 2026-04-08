# TODO

## Publication

- [ ] **Single arXiv paper → CHI/CHIIR submission, if findings warrant.** Core contribution: decomposing "attention" on SERPs into four measurable constructs (overt fixation, viewport exposure, interaction latency, processing speed) where the field uses one undifferentiated term (Zhang et al. CHIIR '26). Novel findings: (1) lexical priming does NOT predict first-pass evaluation — forward-only gaze dwell ratio reverses (ρ = +0.82); aggregate correlation was position confound + regression artifact; regression-trial signal is triply confounded (position, repetition/recognition, scroll kinematics), (2) TTI-to-first-scroll calibrates individual processing speed at r=0.77 (zero-training-data signal, complementary to AdSight's Transformer approach), (3) satisfice/optimize is a continuous user trait visible from scroll regressions. Frame relative to AdSight (same data, prediction focus) and Zhang et al. (same lab, definitional focus). Venue candidates: CHI, CHIIR, CIKM, SIGIR resource track.

## Next Pass

- [ ] **Temporal dynamics: approach velocity over trial and over session (priority).** Two effects to separate: (a) within-trial — does approach velocity slow as working memory fills with candidates? Framework compilation (§3b-iv) predicts later approach episodes are *faster* (criteria already compiled), not slower. (b) Across-trial (learning curve) — the ~60-trial-per-participant practiced effect likely dominates any within-trial temporal dynamic. Trial ordinal 1–10 vs 51–60 should show massive sharpening of phase transitions, approach precision, and regression targeting. This is really an argument for prioritizing 18_learning_curve.ipynb, which subsumes the temporal question.

- [x] **Scroll kinematics analysis (viewport mechanics confound):** `notebooks/scroll_kinematics.ipynb`. Confirmed: backward scrolling is ballistic (ρ = 0.867), 87.3% of regression targets are positions 0-4, and regression velocity mediates the dwell delta (ρ = -0.762, p = 0.017). The "priming during regressions" pattern is a viewport mechanics artifact.

- [ ] **Scroll velocity decomposition (Peter Dixon-Moses):** Separate forward vs backward scroll velocity as distinct features. Backward velocity is high because the user *knows* where the target was — different signal than forward deceleration (approaching novel target). Compute acceleration/deceleration derivatives in each direction separately. Relevant to mobile/touch where mouse signal is unavailable. Feeds into the kinematics notebook above.

- [ ] **Gwizdka 2010 — cognitive load distribution in web search:** "Distribution of Cognitive Load in Web Search" (JASIST 61(11), 2167-2187). Same Gwizdka who co-authored AdSERP. Found cognitive load peaks during query formulation and document evaluation, not during SERP scanning. Re-evaluation during scroll regressions may be a distinct load peak — connect to the forward-only gaze dwell ratio increase (ρ = +0.82), which reflects growing comparison-set cost with compiled criteria, not cognitive load (per §3b-iv, cognitive effort decreases with position). [Scholar link](https://scholar.google.com/citations?view_op=view_citation&hl=en&user=gto9D-8AAAAJ&citation_for_view=gto9D-8AAAAJ:Se3iqnhoufwC)

- [x] **Semantic similarity (embeddings):** Tested with mxbai-embed-large cosine similarity. Also null within-position — sentence-level semantic similarity does not predict evaluation time. Both bag-of-words and embedding similarity are dead ends as difficulty measures. See "SERP Difficulty — Better Measures" section for why and what to try instead.

- [ ] **Local novelty → regression triggers:** Per-result novelty (deviation from cumulative overlap trend) predicting next scroll-back event. Time-series analysis, not aggregate.

- [ ] **AOI-filtered analysis:** Use ad boundary data to separate navigational fixations from result-evaluation fixations. Their Figure 7 shows most fixations are revisits to non-ad areas — many may be navigational.

- [ ] **AdSERP attention metric:** Use their Attention_trial (fixation duration on AOI / total fixation duration) as the dependent variable instead of raw fixation duration.

- [ ] **Pupil dilation × regressions:** Do pupils dilate during scroll regressions? Cognitive load / surprise signal. Pupil data available on Zenodo (129MB).

- [ ] **Earliest predictor refinement:** The 14.9s first-fixation signal uses a 150px Y radius. Sensitivity analysis on radius. Also: does first-fixation duration on the eventual target differ from first-fixation duration on non-clicked results?

- [ ] **Search abandonment literature:** Connect to the forced-choice paradigm insight. Search abandonment (Diriye et al. 2012, Bruckner et al. 2020 "Query Abandonment Prediction") is the observable patch-leaving decision in AFE terms. The AdSERP forced-choice task eliminates abandonment as an outcome, which isolates the foraging-to-exploitation transition — but the abandonment literature characterizes the alternative outcome. Understanding both paths (click vs. abandon) completes the AFE picture.

- [x] **Citation audit (priority):** Completed 2026-04-01. Surveyed Gwizdka's full 2025-2026 publication list (10 papers), Latifzadeh follow-ups (AdSight, LaborTrack), Leiva related work. Key finding: **AdSight** (SIGIR '25, same data) does Transformer-based mouse→fixation prediction — we should position TTI calibrator relative to it. **No overlap with priming analysis** — lexical overlap → evaluation speed appears novel. Zhang et al. CHIIR '26 "Attention! Rethinking" supports our fixation/viewport/TTI decomposition. All references in `references.bib`.

- [ ] **Residual dwell model (Peter Dixon-Moses):** Map fixation-time per result as a function of lexical overlap to establish a baseline. Residuals (deviation from expected dwell) predict interest/click — "this result held attention longer than priming alone would predict." Baseline may need per-user calibration from early-session features (e.g., time-to-first-scroll as a proxy for processing speed). See user_strategies.ipynb for satisfice/optimize segmentation that could serve as the calibration axis.

- [ ] **Priming × user strategy interaction:** Re-run serp_priming.ipynb with user segmentation (satisfice/optimize terciles from user_strategies.ipynb) as a moderator. Given the forward-only null and regression-trial confounds (position, repetition, scroll kinematics), this is low priority unless a finer-grained overlap metric (embeddings, token-level) shows promise first.

- [ ] **Personalized lexical divergence (Peter Dixon-Moses):** If dwell-time residuals flag "lexical divergences of interest," those terms could enhance subsequent queries — a user-specific signal of what information they found novel vs. already-known. Applied potential for search personalization.

- [ ] **TTI as individual calibrator (Peter Dixon-Moses):** Time-to-first-scroll as proxy for individual information processing speed. If TTI predicts per-user evaluation rate, it's a session-start calibration signal available without any training data.

## Follow-ups from v4 (2026-04-01)

- [x] **Position 9 dwell ratio still >1.0 (1.25).** Root cause: FPOGY out-of-bounds — 24.5% of Gazepoint fixations exceed screen height (95th pctl = 1830px on 1024px screen). Fixations were attributed to positions below the viewport. Fix: clamp FPOGY to [0, screen_height] before adding scroll offset. Corrected 1.25 → 0.79. Forward-only ρ strengthened from +0.73 to +0.82.
- [x] **p(fixate) as binary outcome.** Tested. Forward-only p(fixate) is ~99.8% at every position — users fixate everything during forward scanning. No skip decision to predict. Aggregate skip signal (r_pb = -0.059) is again position confound + regression artifact. The 12.5% skip rate is concentrated in regression trials. Structurally uninformative for priming.
- [ ] **Forward-only regression stratification.** The ρ = +0.82 forward-only shape test pools all trials. Separate: (a) trials with zero regressions (pure forward scan), (b) forward segments within regression trials. Are they different?
- [ ] **Practiced-participant learning curve (rich gradient).** Participants completed ~60 trials each. The learning curve across trials is itself a finding, not just a caveat. Plot ALL key metrics by trial ordinal: (1) orientation time, (2) survey duration and amplitude, (3) saccade slope steepness, (4) regression rate, (5) click position, (6) approach-retreat rate, (7) pupil trajectory shape. If phase structure sharpens with practice, we're watching SERP expertise form in real time — from naive layout discovery to automatic motor routines. The asymptotic pattern is what power users do in production; the early-trial pattern is what first-time visitors do. Both are publishable. This could be its own notebook (18_learning_curve.ipynb) and a standalone finding.
- [ ] **Satisficer vs optimizer LHIPA.** Do satisficers (low-regression users) have higher trial-level LHIPA (less cognitive load) than optimizers? The satisfice/optimize segmentation (notebook 10) + LHIPA (notebook 05) should cross. From shi2025-key-claims.md.
- [ ] **RecGaze replication (CIKM priority).** de León Martínez et al. (SIGIR 2025) — 87 users, 3,477 interactions on horizontal carousel interfaces. Eye tracking + clicks + cursor + swipe. Test: does the survey phase (wide saccade → narrow) appear in horizontal ranked lists? Swipe-back = their scroll regression. GitHub: santideleon/RecGaze_Dataset. No pupil data — saccade amplitude only. Contact de León Martínez for collaboration.
- [ ] **COLET dataset for ETTAC pupil-lfhf validation.** Cognitive workLoad Estimation from Eye-Tracking (ScienceDirect 2022). Eye tracking with pupil data during cognitive tasks. Not SERP-specific but validates LHIPA vs Butterworth on independent data. Would strengthen ETTAC submission.
- [ ] **Explicit attention definitions per notebook.** Zhang et al. (CHIIR 2026) argues "attention" conflates 4+ constructs. Each notebook should state which it measures: overt visual attention (fixation coverage), processing speed (TTI), cognitive load (LHIPA), engagement (dwell). From zhang2026-attention-chiir.md.
- [x] **Re-export HTML notebooks.** All 9 HTML exports regenerated 2026-04-03.
- [x] **Pupil dilation × position (cognitive load).** LHIPA correlates with click position (ρ = −0.90), but the effect is a boundary step at positions 9–10 (flat across 0–8, delta = 0.0008), not a gradual gradient. Done in notebook 05. See CHANGELOG v9 correction.

## SERP Difficulty — Better Measures

Bag-of-words Jaccard (mean=0.151) and sentence embeddings both null within-position. The % multi-fixation episode signal (p=0.004) suggests *something* is there, but token overlap is the wrong lens. The problem: these are transactional product queries. "Difficulty" isn't about lexical similarity — it's about **discriminability of the purchase decision.**

### Why token overlap fails

All AdSERP queries are "buy [brand] [product]" — results *should* share vocabulary (they're all selling the same thing). High token overlap doesn't mean the results are hard to tell apart. A user can instantly discriminate two flashlights if one costs $12 and the other $45, even if they share 80% of tokens. Conversely, two results with low token overlap might both be plausible purchases.

### Product-type taxonomy

The queries span a product taxonomy (flashlights, padlocks, adhesives, wine decanters, brake shoes...). Different product categories have different discriminability structures:
- **Commodity products** (batteries, cables, basic tools): results are genuinely interchangeable → high difficulty regardless of overlap
- **Branded differentiated** (specific model flashlights, electronics): brand/model is the discriminating feature → difficulty depends on whether brand names differ
- **Experiential** (wine, music, art supplies): harder to evaluate from snippet text alone → difficulty comes from information insufficiency, not similarity

A product-type classifier on the query (even a simple keyword heuristic) could partition trials into categories where "difficulty" means different things. Then test: do commodity-product SERPs show different foraging patterns than branded-differentiated ones?

### Alternative difficulty operationalizations

Ordered by conceptual promise, not implementation effort:

- [ ] **Relevance spread (query-result alignment variance):** Embed query + each result, compute cosine similarities. If all results are equidistant from the query (low variance in query-result similarity), the SERP is hard. If one result is much closer, it's easy. This captures "is there an obvious best answer?" which is the actual decision difficulty.

- [ ] **Distinctive feature density:** Instead of measuring what results *share*, measure what's *unique* to each result. Count tokens that appear in only one result on the SERP. High unique-token density = easy (each result has clear distinguishing features). Low = hard (results blur together). Weight by TF-IDF so product-category terms ("buy", "flashlight") don't count.

- [ ] **Named entity / brand diversity:** Extract brand names, model numbers, prices from snippets. SERPs where all results are from different brands are easier (brand is a fast heuristic). SERPs with multiple results from the same brand or no recognizable brands are harder.

- [ ] **Price variance (where extractable):** Product SERPs often show prices. High price variance = easy discrimination axis. Low/no price variance = must read deeper. Extractable via regex on snippet text.

- [ ] **Visual distinctiveness (rendered SERP):** Token-level analysis ignores that SERPs have visual structure — bold titles, star ratings, thumbnails, price callouts. Render the SERP HTML, compute image-level perceptual hashing or SSIM between result blocks. This captures what the *eye* actually discriminates, not what NLP measures.

- [ ] **Product taxonomy partition:** Classify queries into product categories (heuristic or LLM-based). Analyze foraging behavior *within* category. "Difficulty" may not be a continuous variable — it may be categorical, with different foraging strategies for different product types.

- [ ] **Information sufficiency:** Some products can be evaluated from a snippet (price, brand, rating). Others require clicking through (fit, compatibility, reviews). Measure how much decision-relevant information is visible in the SERP snippet vs. requiring a click. Low snippet informativeness = harder evaluation = more fixations needed.

- [ ] **Adjacent-pair similarity:** All-pairs Jaccard weights position 0 vs position 9 equally with position 3 vs position 4. But users scan sequentially. Consecutive-pair similarity (result N vs N+1) is what the eye actually encounters. High adjacent similarity = "didn't I just read this?" = re-reading trigger.

### Reading episode analysis (completed 2026-04-02)

`notebooks/serp_difficulty.ipynb` — Episode pooling (minor saccade threshold 100px) merges consecutive same-result fixations into reading episodes. 50.5% single-fixation, 49.5% multi-fixation. Mean episode = 2.16 fixations, 499ms (vs raw 222ms). One signal: % multi-fixation episodes higher on hard SERPs (p=0.004). All other episode metrics null against Jaccard difficulty.

## Interactive Demo (gh-pages)

- [ ] **Progressive foveation reveal:** Synch foveated content with the playback timeline — only show foveated (sharp) regions for fixations that have already been reached. Currently disabled (Progressive button removed). Requires per-fixation gazeplot captures or a client-side foveation shader. The DOM-anchored clip-mask approach (radial gradient mask over gazeplot image, composited with `source-in`) is implemented but has coordinate/canvas sizing issues.
- [ ] **Pupil dilation visualization:** Overlay pupil diameter data on the timeline and/or as fixation circle size modulation. AdSERP pupil data available on Zenodo (129MB). More immediately valuable than progressive foveation — shows cognitive load in real time.
- [ ] **Reading span in batch gazeplots:** Batch mode uses symmetric foveal circles, but SERP reading is asymmetric (~5 deg rightward, ~1.3 deg leftward per Rayner). Scrutinizer v2.4 has this for live replay (velocity-gated) but batch mode has no velocity signal. Fix: infer reading direction from consecutive fixation dx, apply asymmetric radius for text-element fixations (check DOM anchor tag). VM buffer needs elliptical support or offset-circle approximation.
- [ ] **Scrutinizer gazeplot at window width:** Re-capture gazeplots at 1422px (original CSS viewport) using DOM-anchored fixation positions in the batch capture pipeline. Currently at 1280px (screen pixel width). Would eliminate the layout mismatch between gazeplot and SERP render.
- [ ] **Time offset hash param:** Support `#t=1.4s` in viewer URLs to jump to a specific timestamp (not just fixation index). Useful for deep-linking to phase transitions in explainer iframes.
- [ ] **Gaze velocity timeline tracks:** Add X-velocity and Y-velocity as two multitrack lines below the existing timeline. Wide X jumps + big Y drops during survey phase, tight X oscillations + small Y steps during evaluate. Would make the orient→survey→evaluate transition visually obvious in the timeline — the saccade amplitude difference rendered as raw speed.
- [ ] **Scanpath overlay controls:** Replace Lines/Numbers toggles with: scanpath overlay on/off, foveated filter on/off. Popover menus with transparency sliders for gazeplot and scanpath layers.

## Design / Product Connections (from Peter Dixon-Moses)

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. If content similarity affects re-evaluation speed (still unconfirmed — the bag-of-words signal was confounded by position, repetition, and scroll kinematics), then diversity would slow *re-evaluation* of previously seen items. Topic shifts may recapture attention on return visits, but this needs testing with finer-grained similarity measures.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.
