# TODO

## Publication

- [ ] **Single arXiv paper → CHI/CHIIR submission, if findings warrant.** Core contribution: decomposing "attention" on SERPs into four measurable constructs (overt fixation, viewport exposure, interaction latency, processing speed) where the field uses one undifferentiated term (Zhang et al. CHIIR '26). Novel findings: (1) lexical priming does NOT predict first-pass evaluation — forward-only dwell curve reverses (ρ = +0.82); aggregate correlation was position confound + regression artifact; regression-trial signal is triply confounded (position, repetition/recognition, scroll kinematics), (2) TTI-to-first-scroll calibrates individual processing speed at r=0.77 (zero-training-data signal, complementary to AdSight's Transformer approach), (3) satisfice/optimize is a continuous user trait visible from scroll regressions. Frame relative to AdSight (same data, prediction focus) and Zhang et al. (same lab, definitional focus). Venue candidates: CHI, CHIIR, CIKM, SIGIR resource track.

## Next Pass

- [x] **Scroll kinematics analysis (viewport mechanics confound):** `notebooks/scroll_kinematics.ipynb`. Confirmed: backward scrolling is ballistic (ρ = 0.867), 87.3% of regression targets are positions 0-4, and regression velocity mediates the dwell delta (ρ = -0.762, p = 0.017). The "priming during regressions" pattern is a viewport mechanics artifact.

- [ ] **Scroll velocity decomposition (Peter Dixon-Moses):** Separate forward vs backward scroll velocity as distinct features. Backward velocity is high because the user *knows* where the target was — different signal than forward deceleration (approaching novel target). Compute acceleration/deceleration derivatives in each direction separately. Relevant to mobile/touch where mouse signal is unavailable. Feeds into the kinematics notebook above.

- [ ] **Gwizdka 2010 — cognitive load distribution in web search:** "Distribution of Cognitive Load in Web Search" (JASIST 61(11), 2167-2187). Same Gwizdka who co-authored AdSERP. Found cognitive load peaks during query formulation and document evaluation, not during SERP scanning. Re-evaluation during scroll regressions may be a distinct load peak — connect to the forward-only dwell increase (ρ = +0.82), which is consistent with increasing cognitive load from holding more candidates in working memory. [Scholar link](https://scholar.google.com/citations?view_op=view_citation&hl=en&user=gto9D-8AAAAJ&citation_for_view=gto9D-8AAAAJ:Se3iqnhoufwC)

- [x] **Semantic similarity (embeddings):** Tested with mxbai-embed-large cosine similarity. Also null within-position — sentence-level semantic similarity does not predict evaluation time. Sentence-level embeddings would capture paraphrase and synonym priming.

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
- [ ] **Re-export HTML notebooks.** `html/serp_priming.html` is stale — pre-v4 metric names and viewport computation. Re-export after notebook is stable.
- [ ] **Pupil dilation × position (cognitive load from comparative decision-making).** The forward-only dwell increase (ρ = +0.82) suggests increasing cognitive load as users hold more candidates in working memory. AdSERP Gazepoint GP3 HD records pupil diameter. Shi, Jayawardena & Gwizdka (2025) and Jayawardena et al. (2025) provide methodology. Pupil data available on Zenodo (129MB). Test: does pupil dilation increase with position during forward scanning? If so, the dwell increase is cognitive load, not attention.

## Design / Product Connections (from Peter Dixon-Moses)

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. If content similarity affects re-evaluation speed (still unconfirmed — the bag-of-words signal was confounded by position, repetition, and scroll kinematics), then diversity would slow *re-evaluation* of previously seen items. Topic shifts may recapture attention on return visits, but this needs testing with finer-grained similarity measures.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.
