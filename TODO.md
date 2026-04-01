# TODO

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

- [ ] **Citation audit (priority):** Survey Gwizdka's full publication list and the AdSERP team's prior/subsequent work before claiming any finding as novel. 1,200 eye tracking sessions is serious labor — they likely have analyses in progress or published that overlap with our observations. Check JASIST, SIGIR, CHIIR proceedings. Also verify p(click) conditioning and priming hypothesis novelty claims against the broader literature.

## Design / Product Connections (from Peter Dixon-Moses)

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. The priming curve is the mechanism — high overlap = fast reject. Topic shifts recapture attention.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.
