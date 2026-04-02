# TODO

## Publication

- [ ] **Single arXiv paper → CHI/CHIIR submission, if findings warrant.** Core contribution: decomposing "attention" on SERPs into four measurable constructs (overt fixation, viewport exposure, interaction latency, processing speed) where the field uses one undifferentiated term (Zhang et al. CHIIR '26). Novel findings: (1) lexical priming predicts re-evaluation speed, not first-pass (content effect absent from SERP attention literature), (2) TTI-to-first-scroll calibrates individual processing speed at r=0.77 (zero-training-data signal, complementary to AdSight's Transformer approach), (3) satisfice/optimize is a continuous user trait visible from scroll regressions. Frame relative to AdSight (same data, prediction focus) and Zhang et al. (same lab, definitional focus). Venue candidates: CHI, CHIIR, CIKM, SIGIR resource track.

## Next Pass

- [ ] **Scroll velocity decomposition (Peter Dixon-Moses):** Separate forward vs backward scroll velocity as distinct features. Backward velocity is high because the user *knows* where the target was — different signal than forward deceleration (approaching novel target). Compute acceleration/deceleration derivatives in each direction separately. Relevant to mobile/touch where mouse signal is unavailable.

- [ ] **Gwizdka 2010 — cognitive load distribution in web search:** "Distribution of Cognitive Load in Web Search" (JASIST 61(11), 2167-2187). Same Gwizdka who co-authored AdSERP. Found cognitive load peaks during query formulation and document evaluation, not during SERP scanning. If priming reduces evaluation cost, it's reducing peak cognitive load. Connect to our priming finding. [Scholar link](https://scholar.google.com/citations?view_op=view_citation&hl=en&user=gto9D-8AAAAJ&citation_for_view=gto9D-8AAAAJ:Se3iqnhoufwC)

- [ ] **Semantic similarity (embeddings):** Bag-of-words overlap likely underestimates the priming effect. Sentence-level embeddings would capture paraphrase and synonym priming.

- [ ] **Local novelty → regression triggers:** Per-result novelty (deviation from cumulative overlap trend) predicting next scroll-back event. Time-series analysis, not aggregate.

- [ ] **AOI-filtered analysis:** Use ad boundary data to separate navigational fixations from result-evaluation fixations. Their Figure 7 shows most fixations are revisits to non-ad areas — many may be navigational.

- [ ] **AdSERP attention metric:** Use their Attention_trial (fixation duration on AOI / total fixation duration) as the dependent variable instead of raw fixation duration.

- [ ] **Pupil dilation × regressions:** Do pupils dilate during scroll regressions? Cognitive load / surprise signal. Pupil data available on Zenodo (129MB).

- [ ] **Earliest predictor refinement:** The 14.9s first-fixation signal uses a 150px Y radius. Sensitivity analysis on radius. Also: does first-fixation duration on the eventual target differ from first-fixation duration on non-clicked results?

- [ ] **Search abandonment literature:** Connect to the forced-choice paradigm insight. Search abandonment (Diriye et al. 2012, Bruckner et al. 2020 "Query Abandonment Prediction") is the observable patch-leaving decision in AFE terms. The AdSERP forced-choice task eliminates abandonment as an outcome, which isolates the foraging-to-exploitation transition — but the abandonment literature characterizes the alternative outcome. Understanding both paths (click vs. abandon) completes the AFE picture.

- [x] **Citation audit (priority):** Completed 2026-04-01. Surveyed Gwizdka's full 2025-2026 publication list (10 papers), Latifzadeh follow-ups (AdSight, LaborTrack), Leiva related work. Key finding: **AdSight** (SIGIR '25, same data) does Transformer-based mouse→fixation prediction — we should position TTI calibrator relative to it. **No overlap with priming analysis** — lexical overlap → evaluation speed appears novel. Zhang et al. CHIIR '26 "Attention! Rethinking" supports our fixation/viewport/TTI decomposition. All references in `references.bib`.

- [ ] **Residual dwell model (Peter Dixon-Moses):** Map fixation-time per result as a function of lexical overlap to establish a baseline. Residuals (deviation from expected dwell) predict interest/click — "this result held attention longer than priming alone would predict." Baseline may need per-user calibration from early-session features (e.g., time-to-first-scroll as a proxy for processing speed). See user_strategies.ipynb for satisfice/optimize segmentation that could serve as the calibration axis.

- [ ] **Priming × user strategy interaction:** Re-run serp_priming.ipynb with user segmentation (satisfice/optimize terciles from user_strategies.ipynb) as a moderator. Optimizers encounter more cumulative overlap before clicking — the priming effect should be stronger for them. Satisficers who click at position 2 have barely accumulated priming signal.

- [ ] **Personalized lexical divergence (Peter Dixon-Moses):** If dwell-time residuals flag "lexical divergences of interest," those terms could enhance subsequent queries — a user-specific signal of what information they found novel vs. already-known. Applied potential for search personalization.

- [ ] **TTI as individual calibrator (Peter Dixon-Moses):** Time-to-first-scroll as proxy for individual information processing speed. If TTI predicts per-user evaluation rate, it's a session-start calibration signal available without any training data.

## Design / Product Connections (from Peter Dixon-Moses)

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. The priming curve is the mechanism — high overlap = fast reject. Topic shifts recapture attention.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.
