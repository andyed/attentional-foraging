# TODO

## Ski-jump null-finding update (2026-05-06, prompted by AllSERP flavor comparison)

The 2026-04-12 audit (`docs/null-findings/2026-04-12-ski-jump-audit-collapse.md`) said the full-corpus uptick at organic-rank tail collapsed after the coord-space fix; only the cohort-A narrow result (n=131 plain-top SERPs, +33 %) survives. **AllSERP's flavor-comparison rank-effect chart contradicts that read on the surface:** under `organic-only` flavor, click rate at rank 7 is 4.1 %, jumping to 7.6 % at rank 8 and 8.2 % at rank 9 — a +85 % uptick larger than the documented cohort-A result. Under `organic-hybrid` flavor, the uptick disappears (4.4 % at both 8 and 9). Numbers computed directly from `AdSERP/data/cursor-approach-features-organic.json` and `cursor-approach-features-organic-hybrid.json`.

Three plausible reasons for the discrepancy with the post-audit story:

1. **Sample thinning under organic-only.** N drops sharply: pos 0 has 2,658 records, pos 9 has 401. The organic-only file enumerates only trials where ≥ N organics are present; the surviving cohort at deep ranks is self-selected.
2. **Cohort-A leakage.** ~40 % of trials are plain-top SERPs with ≥ 10 organics. The cohort-A narrow finding (n=131) may be present in the full-corpus organic-only aggregate diluted across the rest.
3. **Stale or unaudited file.** Verify whether `cursor-approach-features-organic.json` was regenerated post-2026-04-12 audit.

**Action items:**

- [ ] Confirm whether `cursor-approach-features-organic.json` was regenerated post-coord-fix or carries pre-fix labels. If pre-fix, regenerate.
- [ ] Re-run the ski-jump null finding's full-corpus check using the AllSERP-style per-record-at-position click rate (not NB15's denominator). Document the discrepancy with the existing post-audit numbers.
- [ ] Add a cross-reference from `2026-04-12-ski-jump-audit-collapse.md` to AllSERP's §4.2 flavor comparison so consumers reading either artifact see the other read of the data.
- [ ] Decide whether the +85 % organic-only uptick is real (cohort-A leakage in the aggregate; sample thinning amplifies it) or measurement-driven (file regen needed). If real, update the audit doc; if measurement, add a regeneration entry to the cascade log.

## ETTAC stat-traceability gaps (2026-05-03)

Three numeric claims in `ettac-paper/sections/adserp.tex` need re-derivation or original-computation surfacing before next external pass. Verification status documented in 2026-05-03 audit run.

- [ ] **2,719 trials retained (1-second LF/HF window).** Methodology-specific filter; doesn't match NB14:K1 (2,416 absolute / 2,174 organic). Re-derive from `validate_adserp.py` or document the filter difference.
- [ ] **Bootstrap 95% CI [−0.893, +0.143] on plateau Spearman.** Bootstrap value, source not located. NB14:K11 has ρ = −0.714, p = 0.071 absolute; CI not in any output JSON.
- [ ] **Capped plateau ρ = −0.786, p = 0.036** (participant-concentration audit, cap at 10 segments per ppt per pos). One-off audit value, not in canonical Key Claims.

§Predicting return: **resolved** via within-item paired Δ (replaces the 6,112-record cluster bootstrap). New paragraph in v2.4 draft.

## Ordinal reframe + LambdaMART (2026-05-02)

NB21×NB22 confusion under bbox-organic (Jaccard 0.26, 41% disagreement) collapses to two cuts on a within-trial gaze-dwell ordinal: `total_dwell_ms` predicts NB21 at AUC 0.738 / NB22 at 0.725; `n_fixations` 0.722 / 0.759. ~73% of binary deferred/eval-rejected recoverable from a single ordinal.

LambdaMART experiments (M3 features, LOSO ppt, n=2,020 eval trials):
- Pointwise LR baseline: NDCG@5 = 0.8221, MRR = 0.7872
- LambdaMART binary-gain: NDCG@5 = 0.8376, MRR = 0.8029 (+0.016)
- LambdaMART 32-grade p_click gain: collapses to LR baseline (same-feature distillation carries no information)

**Read.** Listwise loss is a small lever (~10× smaller than NB26's 3-grade→10-grade jump). Soft-label distillation only helps if the teacher has features the student lacks.

### Next
- [ ] **Run gaze-derived label → cursor-only LambdaMART student.** Teacher = gaze-dwell rank within trial (or PCA-1 over `n_fix`, `total_dwell`, `n_returns`); student = M3 cursor-only LambdaMART. The true distillation: gaze-richness → cursor-only ranking. If MRR lifts above 0.8029, the LAB→WILD gaze-distillation story is real.
- [ ] **Decide ordinal target.** Single-axis (`total_dwell_ms`) vs composite (`dwell × log(1 + n_returns)`, or PCA-1).
- [ ] **Reframe paper-v4 §4.2 + §4.5 around ordinal collapse.** Currently presented as Venn-diagram complementarity; ordinal reframe makes it "two cuts on a shared distribution." Decide for v4 or hold for v5.

## AOI cascade follow-ups (post-typed)

The typed cascade landed 2026-05-04 across `attentional-foraging`, `approach-retreat`, `pupil-lfhf`. Pipeline spec: [`docs/methodology/organic-result-aoi-extraction.md`](docs/methodology/organic-result-aoi-extraction.md). Synthesis: [`docs/methodology/attribution-cascade-synthesis.md`](docs/methodology/attribution-cascade-synthesis.md).

- [ ] **Ad text + embeddings.** `serp-embeddings.json` covers organic h3 only — ad text/embeddings absent. To enable per-etype content analyses (LF/HF × content × etype, query-cosine for ad copy, ad-vs-organic TTR distribution): (a) ad-text extractor for `dd_top` / `native_ad` regions; (b) embed via mxbai-embed-large at port 8890; (c) emit `serp-ad-embeddings.json`; (d) extend `compute_content_features.py` with `--attribution organic_hybrid`/`typed`. Volume: 1,581 dd_top + 3,670 native_ad ≈ 5,251 positions.
- [ ] **Promote bbox K-bbox-* values into CIKM paper draft.** `docs/drafts/cikm-2026/paper-v3.md` still cites legacy absolute K-IDs in places. Replace with K-bbox-* / K-typed-*. Brand claim "9 cursor features → AUC ≈ 0.86 LOSO" tightens to 0.871 typed. dd_top 17.1% click-rate finding deserves a paragraph.
- [ ] **CIKM headline: 4-fixation visual budget.** Internal anchor at `docs/findings.md` §10c (committed `60c2cc7a`). Hold for arxiv preprint anchor before any LinkedIn / public posting.
- [ ] **ETTAC §3 prose reframe.** NB14 numbers update (steep ρ = −1.000 holds; full corpus −0.655; plateau ρ flips n.s. under typed). Drop joint LF/HF × RIPA2 dissociation claim or hold absolute as primary with cascade shift as sensitivity finding.
- [ ] **Within-trial peak-load paragraph** for ETTAC. Local edit landed at `pupil-lfhf/ettac/adserp.tex` after the Spearman paragraph (line ~99). Headline: peak-LF/HF position has 35.0% click rate vs 10.2% same-trial (N=2,174 trials / 10,234 records, 3.4× lift, z=+29.7); peak position regresses LESS than other positions (53.0% vs 61.5%, p=2.1e-13). Source: `scripts/max_lfhf_uniqueness.py`.
- [ ] **R1 / RIPA2-paper coordination.** R1 per-fixation amplitude differential dies under bbox (rank-pooling artifact); replacement in `docs/null-findings/r1-ripa2-bbox-collapse.md`. Discuss before paper framing locks. Standalone RIPA2 publication track — flag if draft includes the AdSERP per-fixation will-regress claim.
- [ ] **Refresh `scripts/output/figures/INDEX.md` for cascade.** Several render outputs got new captions/findings under bbox/typed; index is pre-cascade. Coupling-traces caption needs rewrite.
- [ ] **`plot_approach_retreat_hero.py` exemplar trials hand-pick.** Pinned to absolute because curated COMMIT exemplar (p015-b1-t5 pos=2) reattributes away from 'clicked' under bbox. Pick from `cursor-approach-features-typed.json`.
- [ ] **AR README: promote NB28 placeholders to actual numbers.** Calibration retrain done; `attribution-cascade-synthesis.md §4.3` has the numbers ready.
- [ ] **Place Dumais, Buscher & Cutrell (IIiX 2010) citation** wherever satisficer/optimizer is introduced. Lit-note stub at `docs/lit-notes/lit-review-scroll-regressions.md` §6b. Bibtex entry needed.
- [ ] **Revisit null findings under typed.** Some R1-style nulls were computed pre-cascade; triage pass to identify which still hold.

## AI authorship disclosure plan (cross-paper)

- [ ] **Draft and circulate disclosure paragraph.** Triggered 2026-05-02. Scope:
    - **Tools used.** Claude (analysis, prose drafting, code review, synthesis docs, figure scripts), GitHub Copilot if any, embedding model (mxbai-embed-large for content features).
    - **Role taxonomy** (ACM/IR/HCI venues distinguish): idea generation, lit review, analysis/stats, code authoring, prose drafting/editing, figure generation, review/sanity-check.
    - **Venue rules.** ACM 2024: "Authors are required to disclose any use of generative AI tools, the specific tools, and how they were used." CIKM/SIGIR/CHIIR are ACM. Workshops may have separate rules.
    - **Disclosure placement.** Acknowledgements vs dedicated declaration vs methods paragraph.
    - **Reproducibility commitment.** GitHub history records every AI-assisted commit via `Co-Authored-By: Claude` trailers — footnote pointer to commit history strengthens the disclosure.
    - **Two-tier draft** to circulate: short acknowledgements sentence + longer methods paragraph for venues that want detail.

## Publication

- [ ] **Single arXiv paper → CHI/CHIIR submission, if findings warrant.** Core: decomposing "attention" on SERPs into four measurable constructs (overt fixation, viewport exposure, interaction latency, processing speed) where the field uses one undifferentiated term (Zhang et al. CHIIR '26). Novel findings: (1) lexical priming does NOT predict first-pass evaluation — forward-only gaze dwell ratio reverses (ρ = +0.82); aggregate correlation was position confound + regression artifact, (2) TTI-to-first-scroll calibrates individual processing speed at r=0.77 (zero-training-data signal), (3) satisfice/optimize is a continuous user trait visible from scroll regressions. Frame relative to AdSight (same data, prediction focus) and Zhang et al. (same lab, definitional focus). Venue candidates: CHI, CHIIR, CIKM, SIGIR resource.

## Task-model paper — post-audit (2026-04-08)

**Canonical:** `docs/drafts/task-model-paper.md`. The `.tex` is a derivative artifact with known drift. When ready, regenerate from .md rather than editing both. Blocking + High items resolved 2026-04-08.

- [ ] **H2 / L2 — Unplaced citations in §2.** Kuhlthau, Marchionini, Bates, Belkin, Hornof & Kieras, Payne & Duggan mentioned inline without `\cite{}`; no `references.bib` entries. Add bib entries before any arxiv compile.
- [ ] **M1 — "click models cannot see this" rhetoric.** Rephrase as construct-inventory claim, not expressivity. A neural ranker *with* saccade features can see phase structure; it just isn't trained on them.
- [ ] **M2 — Null-as-support on survey duration.** §5.3 concludes fixed-duration from three null difficulty correlations. Reframe as "not detected at this granularity (spread, Jaccard, density all ρ ≈ 0, p > 0.3), consistent with a fixed-budget sampling routine."
- [ ] **M3 — Overly-general claim in §5.8.** Soften "click models cannot represent" to "as currently specified do not represent; the present result motivates doing so."
- [ ] **M4 — Mind-reading in §3.5.** Drop scare-quoted "cognitive state of 'I already know what I'm looking for'" at `task-model-paper.md:68`. Hedge to "consistent with a verification-mode interpretation, not uniquely identifying one."
- [ ] **M5 — Ski-jump table units.** §5.8 position × fixation-count table doesn't specify per-trial-mean or per-row-median. Match CIKM sibling's "mean fix count" label.
- [ ] **M6 — "~866 ms parafoveal processing time" load-bearing and uncited.** Source to NB04. Don't use "parafoveal processing" loosely — prefer "inter-fixation time not integrated by FPOGD."
- [ ] **M8 — Cross-paper drift on "> 15 s time-to-click" boundary.** .md §5.7 mentions; CIKM sibling doesn't. Align both to whichever notebook produced the cutoff.
- [ ] **L6 — Four-class taxonomy cross-ref.** Intro alludes to "approach-retreat taxonomy" without unpacking; add "(see companion CIKM 2026 paper for the four-class taxonomy)" for reviewer orientation.
- [ ] **NB25 — K9 as second empirical anchor for fixation-5 phase boundary.** Per-result absolute gaze dwell ρ(dwell, click) = +0.014 ns (n=2,836) Survey vs +0.262 (p≈10⁻¹⁹⁴, n=12,392) post-Survey — 18.9× ratio. Click-level dissociation at the same boundary saccade-amplitude transition identifies. Strengthens "real phase boundary, not a saccade-metric artifact."
- [ ] **NB25 — Phase-dependent baseline sign flip.** Cell 13: Survey-phase cos-sim → dwell slope +0.10 (predictable content gets longer dwell, *wrong direction*); post-Survey slope −1.46 (novel content gets longer dwell, correct direction). Reichle/Rayner reading-time novelty curve only exhibited in deliberative phase.

## Cross-cutting refactors

- [ ] **Extend Key Claims to remaining cited notebooks.** Four worth promoting: NB01 (mouse-gaze AUC, scroll-enriched click prediction), NB02 (Huang −700ms gaze-leads-cursor replication), NB08 (§2 four-granularity null), NB10 (satisficer/optimizer split). Pattern: pull 5–8 numbers per notebook, add `NB##_BODY` to `notebooks-v2/update_key_claims.py`. Est. 1–2 hours.
- [ ] **Forward-only vs regressive split across all analyses.** Most current findings pool forward with regressive. 1,465 of 2,341 tagged trials are `regressive_scroller`. Re-run NB23, NB24, NB20, NB01, NB05 with explicit partition. Retreat direction and "retreat as epistemic action" claims likely direction-specific.
- [ ] **Mouse dwell vs time on screen.** Current cursor dwell conflates "lingered at X" with "X visible in viewport." Normalize per-result cursor dwell by viewport exposure time (NB06). Likely affects consideration-set finding in NB01.
- [ ] **Mouse resting position.** Where do cursors park between interactions? Right margin, last clicked, viewport center, off-screen? Individual-difference candidate (`mouse_independent` tag, 1,434 trials). May reveal default "home" that retreat episodes return to (empirical evidence for home zone in approach-retreat brand).
- [ ] **References.bib duplicates** — chore.

## Next pass

- [ ] **Temporal dynamics: approach velocity over trial and over session.** Two effects: (a) within-trial — does approach velocity slow as WM fills? Framework compilation (§3b-iv) predicts later approach episodes are *faster* (criteria already compiled), not slower. (b) Across-trial — ~60-trial-per-ppt practiced effect likely dominates within-trial. Argues for prioritizing 18_learning_curve.ipynb.
- [ ] **Practiced-participant learning curve.** ~60 trials each. Plot all key metrics by trial ordinal: orientation time, survey duration/amplitude, saccade slope, regression rate, click position, approach-retreat rate, pupil shape. Asymptotic = power users; early = first-time. Both publishable. Could be its own notebook (18_learning_curve.ipynb).
- [ ] **Forward-only regression stratification.** Forward-only ρ = +0.82 pools all trials. Separate: (a) trials with zero regressions, (b) forward segments within regression trials. Different?
- [ ] **Satisficer vs optimizer LHIPA.** Do satisficers (low-regression) have higher trial-level LHIPA than optimizers? Notebook 10 × notebook 05.
- [ ] **RecGaze replication (CIKM priority).** de León Martínez et al. (SIGIR 2025) — 87 users, 3,477 interactions on horizontal carousel interfaces. Test: does survey phase (wide saccade → narrow) appear in horizontal lists? Swipe-back = scroll regression. GitHub: santideleon/RecGaze_Dataset.
- [ ] **COLET dataset for ETTAC LF/HF validation.** Cognitive workLoad Estimation from Eye-Tracking (ScienceDirect 2022). Validates LHIPA vs Butterworth on independent data.
- [ ] **Explicit attention definitions per notebook.** Zhang et al. (CHIIR 2026) argues "attention" conflates 4+ constructs. Each notebook should state which it measures.
- [ ] **Scroll velocity decomposition.** Forward vs backward scroll velocity as distinct features. Backward velocity is high because user *knows* target location — different signal than forward deceleration. Compute acceleration/deceleration derivatives separately. Relevant to mobile/touch.
- [ ] **Local novelty → regression triggers.** Per-result novelty (deviation from cumulative overlap trend) predicting next scroll-back event. Time-series, not aggregate.
- [ ] **AdSERP attention metric.** Use Attention_trial (fixation duration on AOI / total fixation duration) as DV instead of raw fixation duration.
- [ ] **Pupil dilation × regressions.** Do pupils dilate during scroll regressions? Cognitive load / surprise signal.
- [ ] **Earliest predictor refinement.** 14.9s first-fixation signal uses 150px Y radius. Sensitivity on radius. Does first-fixation duration on eventual target differ from non-clicked results?
- [ ] **Search abandonment literature.** Connect to forced-choice paradigm. Diriye et al. 2012, Bruckner et al. 2020 ("Query Abandonment Prediction") characterize the alternative outcome.
- [ ] **Residual dwell model.** Map fixation-time per result as function of lexical overlap to establish baseline. Residuals (deviation from expected dwell) predict interest/click. May need per-user calibration from early-session features.
- [ ] **Priming × user strategy interaction.** Re-run serp_priming.ipynb with sat/opt terciles as moderator. Low priority unless finer-grained overlap metric (embeddings, token-level) shows promise.
- [ ] **Personalized lexical divergence.** If dwell-time residuals flag "lexical divergences of interest," those terms could enhance subsequent queries — user-specific signal of novel-vs-already-known.
- [ ] **TTI as individual calibrator.** Time-to-first-scroll as proxy for individual processing speed. Session-start calibration without training data.

## Content analyses — backlog (deprioritized 2026-04-19)

Bring back if active items land positive and we need more mechanism.

- [ ] **#3 Ad vs organic content contrast.** NB25 already tags etypes. Recompute content features within each class. Test whether LF/HF spikes on ad interruptions vs organic.
- [ ] **#5 Within-trial embedding-trajectory.** Distance traveled in embedding space across inspection order. Straight-line = scent crystallized; wandering = scent unformed.
- [ ] **#6 LLM graded relevance (0–3).** Extends NB26 LTR idea to LF/HF as outcome.
- [ ] **#7 Entity-type density.** spaCy NER or one-shot LLM — count BRAND / PRODUCT / PRICE / NUMBER per result.
- [ ] **#8 Query-term bolding density.** Google bolds query-match in snippets; literal visual saliency. Verify HTML preserves markup first.
- [ ] **#9 Title ↔ URL dissonance.** cosine(title, URL-domain) — high dissonance could drive reorienting.
- [ ] **#10 Rank-cosine surprise.** Residual of query_cosine after regressing on position. High-cosine at deep ranks = "surprise."
- [ ] **#11 Cross-trial domain carryover.** Per-ppt brand/domain familiarity across consecutive queries.
- [ ] **#12 Parafoveal content acquisition** (word-bbox dependent, backlogged).
- [ ] **#13 Per-word content features** (word-bbox dependent). Frequency, concreteness, length, POS at fixated word rather than snippet aggregate.

## SERP difficulty — better measures

Bag-of-words Jaccard (mean=0.151) and sentence embeddings both null within-position. % multi-fixation episode signal (p=0.004) suggests something is there, but token overlap is wrong lens. AdSERP queries are "buy [brand] [product]" — results *should* share vocabulary. High token overlap doesn't mean results are hard to discriminate.

Alternative operationalizations (ordered by conceptual promise):

- [ ] **Relevance spread (query-result alignment variance).** Embed query + each result, compute cosine similarities. If all results equidistant from query (low variance), SERP is hard. If one is much closer, easy. Captures "is there an obvious best answer?"
- [ ] **Distinctive feature density.** Measure what's *unique* to each result. Count tokens appearing in only one result. High unique-token density = easy. Weight by TF-IDF.
- [ ] **Named entity / brand diversity.** Extract brand names, model numbers, prices. SERPs where all results are different brands are easier.
- [ ] **Price variance (where extractable).** Product SERPs often show prices. High price variance = easy discrimination axis. Regex on snippet text.
- [ ] **Visual distinctiveness (rendered SERP).** Image-level perceptual hashing or SSIM between result blocks. Captures what the *eye* discriminates, not what NLP measures.
- [ ] **Product taxonomy partition.** Classify queries into product categories (heuristic or LLM). Analyze foraging *within* category. "Difficulty" may be categorical, not continuous.
- [ ] **Information sufficiency.** Some products evaluable from snippet (price, brand, rating); others require click-through. Measure decision-relevant info visible in snippet vs requiring a click.
- [ ] **Adjacent-pair similarity.** All-pairs Jaccard weights pos 0 vs 9 equally with pos 3 vs 4. Users scan sequentially. Consecutive-pair similarity = "didn't I just read this?" = re-reading trigger.

## Interactive demo (gh-pages)

- [ ] **Progressive foveation reveal.** Synch foveated content with playback timeline. Currently disabled (Progressive button removed). DOM-anchored clip-mask approach implemented but has coordinate/canvas sizing issues.
- [ ] **Pupil dilation visualization.** Overlay pupil diameter on timeline and/or as fixation circle size modulation. More immediately valuable than progressive foveation.
- [ ] **Reading span in batch gazeplots.** SERP reading is asymmetric (~5 deg right, ~1.3 deg left per Rayner). Scrutinizer v2.4 has this for live replay (velocity-gated); batch mode has no velocity signal. Infer reading direction from consecutive fixation dx.
- [ ] **Scrutinizer gazeplot at window width.** Re-capture at 1422px (original CSS viewport) using DOM-anchored fixation positions. Currently 1280px (screen pixel width).
- [ ] **Time offset hash param.** Support `#t=1.4s` in viewer URLs to jump to specific timestamp.
- [ ] **Gaze velocity timeline tracks.** Add X-velocity and Y-velocity as multitrack lines. Wide X jumps + big Y drops during survey, tight X oscillations + small Y steps during evaluate. Makes orient→survey→evaluate transition visually obvious.
- [ ] **Scanpath overlay controls.** Replace Lines/Numbers toggles with: scanpath on/off, foveated filter on/off. Popover menus with transparency sliders.
- [ ] **Sub-segmenter for tall organic cards.** Row-projection merges visually-dense blocks. First seen on `p007-b6-t8` (Sephora + Barcelona Maps + local pack collapsed into h=436 organic). Within any flagged tall card (h ≥ SUSPICIOUS_H), run second pass that finds horizontal edges or color-transition rows. Implement when >2 curated AR replay trials hit this.

## Design / product connections

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. If content similarity affects re-evaluation speed (still unconfirmed), diversity would slow *re-evaluation* of previously-seen items. Topic shifts may recapture attention on return visits.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.

## Individual differences (2026-04-11)

- [ ] **LF/HF trajectory segments vs satisficer/optimizer.** Cross-tab is null (chi2 = 0.52, p = 0.77); LOO logistic from 6 LF/HF features → AUC = 0.43. **LF/HF trajectory orthogonal to sat/opt.** Strongest trend: early/late ratio (p = 0.106, d = 0.44). Meaningful null: load trajectory and behavioral strategy independent dimensions.
- [ ] **Connect to Dumais et al. (IIiX 2010).** Their economic vs exhaustive evaluator clusters (gaze AOI fixation impact, scanpath completeness/linearity) map conceptually to our speed terciles. Do our 3 LF/HF segments align with their 3 gaze clusters? Need scanpath completeness and linearity from AdSERP.
- [ ] **Connect to Buscher/Huang et al. (WSDM 2012).** Cursor-feature clustering on Bing. AdSERP has cursor data — replicate cursor-based strategy ID, cross-reference with LF/HF segments.
- [ ] **Stability of LF/HF segments across blocks.** "Increasing" group (N=8) could be noise. Test within-subject consistency across the 6 blocks per ppt.
