# TODO

## AOI cascade (2026-05-01 → 2026-05-02)

The bbox-organic AOI cascade landed across both `attentional-foraging` and `approach-retreat` and merged to main on both repos. Synthesis: [`docs/methodology/attribution-cascade-synthesis.md`](docs/methodology/attribution-cascade-synthesis.md). Per-finding category audit and replacement-predictor scan complete; AR replay re-deployed under bbox AOIs.

### Done
- [x] **AOI-filtered analysis (was line 67):** AdSERP v1's ad-only bboxes augmented with pixel-accurate organic + native_ad + dd_top per-cell + widget filtering. CV row-projection on screenshots; 88.3% within ±2 of HTML count; 78.6/20.1/0.2/1.2 click attribution. Spec at `docs/methodology/organic-result-aoi-extraction.md`. Three rank-attribution flavors (`absolute` / `organic` / `organic_hybrid`) supported across producer chain.
- [x] **Notebook K-claims migrated to bbox-organic (NB04, NB14, NB15, NB18, NB21, NB22, NB23, NB24, NB25, NB28).** `update_key_claims.py` refactored to read notebooks (notebooks canonical).
- [x] **Producer chain accepts `--attribution organic` (and `organic_hybrid` where applicable).** `compute_cursor_approach_features.py`, `compute_butterworth_lfhf.py`, `compute_ripa2.py`, `compute_regression_labels.py`, `compute_retreat_arcs.py`, `compute_k_coefficient.py`, `compute_saccade_orientation.py`, `m5_cursor_only_taxonomy.py`, `forward_classifier_robustness.py`, `viewport_bands_bootstrap.py`. Render scripts default-organic.
- [x] **NB28 viewport-band calibration retrained under bbox-organic.** Pooled retreat+bands AUC 0.811 [0.788, 0.833]; per-position vt_top P0–P3 positive, attenuating to 0 at P5, P6+ null — NB28:K38 pattern preserved.
- [x] **NB21 LOSO retrained under all three attributions.** Hybrid M3 = M4 = 0.870 (best); organic M3 = 0.865; absolute 0.859. Position coefficient cleanest under organic (−0.248).
- [x] **Hybrid attribution surfaces dd_top click-rate finding.** dd_top (top-of-page ads) click rate 17.1% — highest of any SERP surface; was structurally invisible under absolute (pooled into "organic position 1").
- [x] **R1 RIPA2 leg collapse mechanism resolved.** Intersection-of-trials sensitivity test confirms dilution, not selection (`scripts/r1_intersection_sensitivity.py`). Replacement predictors found in will-return scan (`scripts/will_return_predictor_scan.py`): peak-pupil metrics survive (`pd_change_max` p=5.1e-6, `pd_change_min` p=1.9e-5), mean-based metrics all die. `n_fix` = strongest single predictor (p=3.3e-16, median 4 vs 5 fixations).
- [x] **Saccade orientation + K-coefficient by etype** confirms top-of-page Survey-phase across surfaces — 3-signal convergence with NB13:K3 amplitude transition (`scripts/saccade_k_by_etype.py`).
- [x] **AR replay deploy refreshed.** 80 trial bundles regenerated under bbox AOIs; M5 model swapped to bbox-organic-trained (LOSO AUC 0.769); 28 curated captions audited (1 corrected).

### Next (post-merge)
- [ ] **Ad text + embeddings (cascade follow-up).** `serp-embeddings.json` covers organic h3 content only — ad text and embeddings are absent. The `find_all('h3')` extractor in `embed_serp_results.py` doesn't surface dd_top or native_ad copy. To enable per-etype content analyses under `[organic_hybrid]` (e.g., LF/HF × content × etype, query-cosine for ad copy, ad-vs-organic TTR distribution), need: (a) an ad-text extractor that pulls title + snippet + display URL from the SERP HTML for `dd_top` / `native_ad` regions (or OCR fallback on the screenshot if the HTML isn't reliable); (b) embed via mxbai-embed-large at port 8890 (same model as organics for parity); (c) emit `AdSERP/data/serp-ad-embeddings.json` parallel to the organic file; (d) extend `compute_content_features.py` with `--attribution organic_hybrid` to read both. Volume estimate: 1,581 dd_top + 3,670 native_ad ≈ 5,251 positions to embed; potentially more if dd_top carousels subdivide into per-cell text. Effort: 4–6 hours depending on HTML parseability. Cascade context: 2026-05-02 thread; current organic content-features producer (`compute_content_features.py --attribution organic`) is shipped, this follow-up extends to hybrid.
- [ ] **Promote bbox K-bbox-* values into the CIKM paper draft.** `docs/drafts/cikm-2026/paper-v3.md` still cites legacy absolute-attribution K-IDs in places. Replace with K-bbox-* tier; the brand claim ("9 task-model-derived cursor features reach AUC ≈ 0.86 in LOSO") tightens to 0.865 / 0.870. The dd_top 17.1% click-rate finding deserves a paragraph.
- [ ] **CIKM paper headline: 4-fixation visual budget.** Internal anchor at `docs/findings.md` §10c (committed `60c2cc7a`). Hold for arxiv preprint anchor before any LinkedIn / public posting; bad mojo to publish a key finding casually pre-preprint per 2026-05-02 thread with Andy.
- [ ] **ETTAC §3 prose reframe.** NB14 numbers update (steep ρ = −1.000 holds; full corpus −0.655; plateau ρ flips n.s.). Drop the joint LF/HF × RIPA2 dissociation claim or hold absolute as primary with the bbox shift as a sensitivity finding. Peter has the lead.
- [ ] **ETTAC: port the within-trial peak-load paragraph to Overleaf.** Local edit landed at `/Users/andyed/Documents/dev/pupil-lfhf/ettac/adserp.tex` after the existing within-trial Spearman paragraph (line ~99, before the LHIPA convergent-validity paragraph). New paragraph: "Within-trial peak-load position predicts the click." Headline: peak-LF/HF position has 35.0% click rate vs 10.2% on other positions in the same trial (N=2,174 trials / 10,234 comparison records, 3.4× lift, z=+29.7, p<10⁻¹⁰⁰); click rate decays monotonically in within-trial LF/HF rank; peak position also regresses LESS than other positions (53.0% vs 61.5%, p=2.1e-13) — mechanistically clean (commit at peak load → no need to revisit). Sharpens the population-level NB14:K3 gradient into a within-subject commit-prediction result; LF/HF *locates* the click within the trial, not only the distribution-of-clicks across rank. Source: `scripts/max_lfhf_uniqueness.py` + `scripts/output/aoi-consumer-cascade/max_lfhf_uniqueness.json`. Also relevant for CIKM (replaces or sharpens STUB-H).
- [ ] **R1 / RIPA2-paper coordination with Gwizdka.** R1 per-fixation amplitude differential dies under bbox (rank-pooling artifact); replacement framing in `docs/null-findings/r1-ripa2-bbox-collapse.md` and synthesis §4.3. Discuss before paper framing locks. Standalone RIPA2 publication (Gavindya/team) — flag if their draft includes the AdSERP per-fixation will-regress claim.
- [ ] **Refresh `scripts/output/figures/INDEX.md` for cascade.** Several render outputs got new captions/findings under bbox; the index is still pre-cascade. Coupling-traces caption needs rewrite (legacy three-band pattern collapses; motor-signature dissociation lives at different metrics).
- [ ] **`plot_approach_retreat_hero.py` exemplar trials hand-pick.** Currently pinned to absolute because the curated COMMIT exemplar (p015-b1-t5 pos=2) reattributes away from 'clicked' under bbox. Pick new exemplars from `cursor-approach-features-organic.json`.
- [ ] **AR README: promote NB28 placeholders to actual numbers.** Now that the calibration retrain is done, `docs/methodology/attribution-cascade-synthesis.md §4.3` has the numbers ready to drop into AR's README §11 viewport-bands paragraph.
- [ ] **Place the Dumais, Buscher & Cutrell (IIiX 2010) citation** (see "Citations to place" below; lit-note stub exists, bib entry pending).

## Publication

- [ ] **Single arXiv paper → CHI/CHIIR submission, if findings warrant.** Core contribution: decomposing "attention" on SERPs into four measurable constructs (overt fixation, viewport exposure, interaction latency, processing speed) where the field uses one undifferentiated term (Zhang et al. CHIIR '26). Novel findings: (1) lexical priming does NOT predict first-pass evaluation — forward-only gaze dwell ratio reverses (ρ = +0.82); aggregate correlation was position confound + regression artifact; regression-trial signal is triply confounded (position, repetition/recognition, scroll kinematics), (2) TTI-to-first-scroll calibrates individual processing speed at r=0.77 (zero-training-data signal, complementary to AdSight's Transformer approach), (3) satisfice/optimize is a continuous user trait visible from scroll regressions. Frame relative to AdSight (same data, prediction focus) and Zhang et al. (same lab, definitional focus). Venue candidates: CHI, CHIIR, CIKM, SIGIR resource track.

## Citations to place

- [ ] **Cite Dumais, Buscher & Cutrell (IIiX 2010, DOI 10.1145/1840784.1840812)** wherever satisficer/optimizer is introduced — both in **CIKM 2026** (`docs/drafts/cikm-2026/paper-v3.md`) and the **task-model paper** (`docs/drafts/task-model-paper.md`). Their k=3 clustering on gaze patterns (*Exhaustive* / *Economic-Results* / *Economic-Ads*) is the methodological precedent for the satisficer/optimizer dimension. Their Economic-Ads vs Economic-Results split is a 2D taxonomy (depth × surface-attended-to) that parallels the four-class taxonomy. Lit-note stub at `docs/lit-notes/lit-review-scroll-regressions.md` §6b. Bibtex entry needed in `references.bib`. Added 2026-04-30 after Andy spotted the paper while prepping for the Gwizdka/Jayawardena/Jayawardana meeting.

## Task-model paper — post-audit (2026-04-08)

**Canonical source:** `docs/drafts/task-model-paper.md`. The `.tex` is a derivative artifact with known drift — see the warning header in `docs/arxiv/task-model-paper.tex`. When ready to submit, regenerate the .tex from the .md rather than editing both.

**Blocking + High items resolved 2026-04-08** (B1, B2, B3, H1, H5 — see commits). Remaining audit items:

- [ ] **H2 / L2 — Unplaced citations in §2 Related Work.** Kuhlthau, Marchionini, Bates, Belkin, Hornof & Kieras, Payne & Duggan are mentioned inline without `\cite{}` and have no entries in `references.bib`. Add bib entries before any arxiv compile. Not invented, just never placed.
- [x] **H3 — Stale `ρ = −0.762` regression-velocity mediation figure.** 2026-04-13 — Sourced to `notebooks/scroll_kinematics.ipynb` (old tree). Three reasons to drop: tiny *N* = 9 positions (survivor-bias trap), "mediation" overclaims a Spearman correlation, *p* = 0.017 borderline. Replaced the .tex sentence (line 144) with an HTML comment documenting the drop rationale; surrounding "ballistic backward scrolling, ρ = 0.867" claim survives unchanged.
- [x] **H4 — Uncited fixation duration stats.** 2026-04-13 — Computed canonical post-audit values (mean 218.1 ms, median 187.0 ms, *N* = 234,339 single fixations; pre-audit was 219 ms / 193 ms — drifted ~3% on median). Added as **NB04:K24–K27** in `update_key_claims.py` and re-injected. `task-model-paper.tex` line 150 now cites NB04:K24–K27 with the post-fix values.
- [ ] **M1 — Thesis rhetoric: "click models cannot see this."** Rephrase as a construct-inventory claim, not an expressivity claim. A neural ranker *with* saccade features can see phase structure; it just isn't trained on them. Frame around what constructs are named, not what functions can be approximated.
- [ ] **M2 — Null-as-support on survey duration "content-independence."** §5.3 concludes fixed-duration from three null difficulty correlations. Reframe as "not detected at this granularity (spread, Jaccard, density all ρ ≈ 0, *p* > 0.3), consistent with a fixed-budget sampling routine." Andy's own "empirical results are detection limits" rule applies.
- [ ] **M3 — Overly-general claim in §5.8.** "The task model's Commit transition has an alternative pathway that click models cannot represent" is a structural claim about the click-model family from one forced-choice dataset. Soften to "that click models as currently specified do not represent; the present result motivates doing so."
- [ ] **M4 — Mind-reading in §3.5.** Drop the scare-quoted "cognitive state of 'I already know what I'm looking for'" framing at `task-model-paper.md:68`. CHI reviewers will circle it. Hedge to "consistent with a verification-mode interpretation, not uniquely identifying one."
- [ ] **M5 — Ski-jump table needs units.** The §5.8 position × fixation count table does not specify per-trial-mean or per-row-median. Match the CIKM sibling's "mean fix count" label.
- [ ] **M6 — "~866 ms parafoveal processing time" is load-bearing and uncited.** Source to NB04 (fixation decomposition) on next pass. Also: "parafoveal processing" has a specific Reichle-et-al meaning in reading research; don't use the term loosely — prefer "inter-fixation time not integrated by FPOGD."
- [x] **M7 — MD's Appendix references `docs/references.bib`** 2026-04-13 — References section now cites `references.bib (repo root)`.
- [ ] **M8 — Cross-paper drift on "> 15 s time-to-click" boundary.** The .md §5.7 mentions this as the window where the cursor-gaze gap collapses; the CIKM sibling doesn't mention the 15 s boundary. Check which notebook produced the 15 s cutoff and align both papers.
- [x] **L3 — Draft-only title note in MD:3** 2026-04-13 — wrapped in an HTML comment so it can't leak into .tex / arxiv rendering.
- [x] **L4 — Abstract underscore italics.** 2026-04-13 — abstract unwrapped; only "Stub." and inline stats are italicized now, not the whole paragraph.
- [x] **L5 — §6.5 productization claim.** 2026-04-13 — split into a scientific claim (~100 px alignment tightening) and an explicit "Deployability note (not a contribution of this paper)" labeled aside.
- [ ] **L6 — Four-class taxonomy cross-ref.** Intro alludes to "the approach-retreat taxonomy" without unpacking; add one sentence "(see companion CIKM 2026 paper for the four-class taxonomy)" for reviewer orientation.
- [ ] **NB25 — Add K9 as a second independent empirical anchor for the fixation-5 phase boundary.** The task-model paper's current empirical anchor for the Survey → Evaluate boundary is the saccade-amplitude transition at fixation ~5 (*p* = 10⁻⁶¹, task-model-paper.tex:91; NB13 operationalization). `notebooks-v2/25_lexical_novelty_dwell.ipynb` K9 provides a second, independent signal at the same boundary measured on a completely different variable: **per-result absolute gaze dwell, Spearman ρ(dwell, click) = +0.014 (ns, n = 2,836) in Survey phase vs +0.262 (p ≈ 10⁻¹⁹⁴, n = 12,392) in post-Survey phase — 18.9× ratio**. The click-prediction signal collapses to noise before the boundary and lights up after. This is a click-level dissociation at the same boundary the saccade-amplitude transition identifies, and it strengthens the "this is a real phase boundary, not a saccade-metric artifact" claim. Pulled from the CIKM sibling because it is gaze-dependent and CIKM's story is cursor-deployable-at-inference; it is load-bearing for the task-model paper where gaze data is acceptable. The auxiliary K1–K8 in the same notebook (honest null on the lexical-novelty framing, Posner/Cohen-adjacent rubbernecking vs passing split) also belong here as a research arc — the novelty-deviation framing didn't survive the multivariate test, but the phase-dependence did.
- [ ] **NB25 — Also capture the phase-dependent baseline sign flip.** Cell 13 in NB25: the Survey-phase cos-sim → dwell fit has slope +0.10 (predictable content gets longer dwell, *wrong direction* for novelty prediction); the post-Survey fit has slope −1.46 (novel content gets longer dwell, correct direction). The Reichle/Rayner reading-time novelty curve is only exhibited in the deliberative phase, not in Survey-phase ballistic scanning. This is a direct micro-confirmation of the OSEC phase distinction at a level of granularity that saccade-amplitude metrics can't see, and worth a sentence in the task-model paper's phase-boundary discussion.

## Cross-cutting refactors

- [x] **Fix NB02 `compute_lag`.** ~~Uses an undefined `RY` global.~~ Resolved 2026-04-13: set `RY = 1.0` (gaze and cursor share pixel space) and switched the driver to `load_fixations_tuples` to match the tuple destructure. NB02 green, 202 KB output.

- [ ] **Extend Key Claims to remaining exploratory-but-cited notebooks.** After the 2026-04-12 stale-notebook triage (see CHANGELOG), 9 notebooks were re-executed and 3 of the most-cited (NB09, NB06, NB04) got first-class Key Claims blocks. Four more are worth promoting:
    - `01_convergence` — mouse-gaze distance AUC curves, scroll-enriched click prediction (1 findings citation). Candidate K-IDs: ROC-AUC per model variant, per-participant model stability.
    - `02_gaze_cursor_lag` — Huang −700 ms gaze-leads-cursor replication (1 citation). Candidate K-IDs: median lag by cohort (scroll vs no-scroll), within-participant SD, Huang CI overlap.
    - `08_priming` — §2 four-granularity null result (1 citation). Candidate K-IDs: Jaccard/semantic/forward-only/survey-vocabulary each with the null test statistic. The null-result story is load-bearing; hardcoding its values protects it from future drift.
    - `10_strategies` — satisficer/optimizer split, 1.56× boundary effect at positions 9–10 (1 citation, §0). Candidate K-IDs: tercile boundaries on regression rate, boundary-click proportion by tercile, investment-by-tercile deltas.
    Pattern: pull 5–8 numbers per notebook from current cell output, add `NB##_BODY` to `notebooks-v2/update_key_claims.py`, register in `NOTEBOOK_LABELS` + `TARGETS`, run once to inject. Est. 1–2 hours.


- [ ] **Forward-only vs regressive split across all analyses.** Most current findings pool forward reading with regressive (scroll-back) behavior. 1,465 of 2,341 tagged trials are `regressive_scroller`. Re-run NB23 (rank effects), NB24 (retreat arc geometry), NB20 (cursor features), NB01 (convergence / mouse-gaze distance), and NB05 (LHIPA) with an explicit forward-only vs regressive partition. Expected impact: the retreat direction and the "retreat as epistemic action" claims are likely direction-specific. The approach-retreat four-class taxonomy needs this split to handle regressive seeking cleanly. Track which findings survive the split and which are artifacts of pooling.

- [ ] **Mouse dwell vs time on screen.** Current cursor dwell measures conflate "cursor lingered at position X" with "position X was actually visible in the viewport for a long time." Normalize per-result cursor dwell by viewport exposure time (from NB06 viewport tracking). A result that was on-screen for 3 seconds with 2 seconds of cursor dwell is a different signal than a result on-screen for 30 seconds with 2 seconds of cursor dwell. Likely affects the consideration-set finding in NB01.

- [ ] **Mouse resting position analyses.** Characterize where cursors park between interactions — right margin, last clicked position, viewport center, off-screen? Individual differences candidate (connects to `mouse_independent` tag, 1,434 trials). Resting position distribution per participant as a trait dimension alongside deliberation style and motor coupling (§11). May also reveal a default "home" that retreat episodes return to (empirical evidence for the home zone concept in the approach-retreat brand).

## Next Pass

- [ ] **Temporal dynamics: approach velocity over trial and over session (priority).** Two effects to separate: (a) within-trial — does approach velocity slow as working memory fills with candidates? Framework compilation (§3b-iv) predicts later approach episodes are *faster* (criteria already compiled), not slower. (b) Across-trial (learning curve) — the ~60-trial-per-participant practiced effect likely dominates any within-trial temporal dynamic. Trial ordinal 1–10 vs 51–60 should show massive sharpening of phase transitions, approach precision, and regression targeting. This is really an argument for prioritizing 18_learning_curve.ipynb, which subsumes the temporal question.

- [x] **Scroll kinematics analysis (viewport mechanics confound):** `notebooks/scroll_kinematics.ipynb`. Confirmed: backward scrolling is ballistic (ρ = 0.867), 87.3% of regression targets are positions 0-4, and regression velocity mediates the dwell delta (ρ = -0.762, p = 0.017). The "priming during regressions" pattern is a viewport mechanics artifact.

- [ ] **Scroll velocity decomposition (Peter Dixon-Moses):** Separate forward vs backward scroll velocity as distinct features. Backward velocity is high because the user *knows* where the target was — different signal than forward deceleration (approaching novel target). Compute acceleration/deceleration derivatives in each direction separately. Relevant to mobile/touch where mouse signal is unavailable. Feeds into the kinematics notebook above.

- [ ] **Gwizdka 2010 — cognitive load distribution in web search:** "Distribution of Cognitive Load in Web Search" (JASIST 61(11), 2167-2187). Same Gwizdka who co-authored AdSERP. Found cognitive load peaks during query formulation and document evaluation, not during SERP scanning. Re-evaluation during scroll regressions may be a distinct load peak — connect to the forward-only gaze dwell ratio increase (ρ = +0.82), which reflects growing comparison-set cost with compiled criteria, not cognitive load (per §3b-iv, cognitive effort decreases with position). [Scholar link](https://scholar.google.com/citations?view_op=view_citation&hl=en&user=gto9D-8AAAAJ&citation_for_view=gto9D-8AAAAJ:Se3iqnhoufwC)

- [x] **Semantic similarity (embeddings):** Tested with mxbai-embed-large cosine similarity. Also null within-position — sentence-level semantic similarity does not predict evaluation time. Both bag-of-words and embedding similarity are dead ends as difficulty measures. See "SERP Difficulty — Better Measures" section for why and what to try instead.

- [ ] **Local novelty → regression triggers:** Per-result novelty (deviation from cumulative overlap trend) predicting next scroll-back event. Time-series analysis, not aggregate.

- [x] **AOI-filtered analysis:** Use ad boundary data to separate navigational fixations from result-evaluation fixations. Their Figure 7 shows most fixations are revisits to non-ad areas — many may be navigational. **2026-05-01 — done via the bbox cascade. See "AOI cascade" section at the top of this file.**

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

## Content analyses — backlog (2026-04-19, after LF/HF content-crossover null)

Items #1, #4, #2 running 2026-04-19; below are deprioritized alternatives from the brainstorm. Bring back if #1/#4/#2 land positive and we need more mechanism.

- [ ] **#3 Ad vs organic content contrast.** NB25 already tags dd_top / native_ad / organic. Recompute content features within each class. Test whether LF/HF spikes on ad interruptions vs organic. Reasonable story if LF/HF has any ad-specific modulation.
- [ ] **#5 Within-trial embedding-trajectory.** Trial-level feature — distance traveled in embedding space across inspection order. Straight-line trajectory = scent crystallized; wandering = scent unformed. Aggregate correlate of within-trial LF/HF slope.
- [ ] **#6 LLM graded relevance (0–3).** Extends NB26 LTR idea to LF/HF as outcome. Likely orthogonal to organic rank on commercial SERPs.
- [ ] **#7 Entity-type density.** spaCy NER or one-shot LLM pass — count BRAND / PRODUCT / PRICE / NUMBER per result.
- [ ] **#8 Query-term bolding density.** Google bolds query-match in snippets; literal visual saliency. Verify AdSERP HTML preserves the markup first.
- [ ] **#9 Title ↔ URL dissonance.** cosine(title, URL-domain) — high dissonance could drive reorienting.
- [ ] **#10 Rank-cosine surprise.** Residual of query_cosine after regressing on position. High-cosine results at deep ranks = "surprise"; does LF/HF spike?
- [ ] **#11 Cross-trial domain carryover.** Per-participant brand/domain familiarity across consecutive queries. Load should drop when prior exists.
- [ ] **#12 Parafoveal content acquisition (word-bbox dependent, already backlogged).** Model what participant saw parafoveally at each saccade launch. Reichle E-Z-reader style.
- [ ] **#13 Per-word content features (word-bbox dependent).** Frequency, concreteness, length, POS at fixated word rather than snippet aggregate.

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
- [ ] **Sub-segmenter for tall organic cards (`extract_organic_bboxes.py`):** Row-projection merges visually-dense blocks (Maps places carousel, local-business pack, image carousels) into one tall card. First seen on `p007-b6-t8` where Sephora result + Barcelona Maps + local pack collapsed into a single h=436 organic. Fix: within any flagged tall card (h ≥ SUSPICIOUS_H), run a second pass that finds horizontal edges or color-transition rows to split into sub-cards. Implement when >2 of the curated AR replay trials hit this.

## Design / Product Connections (from Peter Dixon-Moses)

- E-comm intentionally introduces diversity to slow evaluation and reduce bounce. If content similarity affects re-evaluation speed (still unconfirmed — the bag-of-words signal was confounded by position, repetition, and scroll kinematics), then diversity would slow *re-evaluation* of previously seen items. Topic shifts may recapture attention on return visits, but this needs testing with finer-grained similarity measures.
- Mouse is "falling as an available signal" — mobile/touch has no cursor. Scroll + viewport features are the only behavioral signals. Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.

## v9 audit fixes (2026-04-07)

### Notebooks to update (from science-audit)

- [x] **NB 05 (lhipa):** 2026-04-13 — Cell 14 butterworth value updated to post-audit ρ = −0.927 on *N* = 11 position medians with survivor-bias caveat pointer. Cell 4 Key Measures table already correct (trial-level ρ = -0.088 with N disclosure). The full cell-by-cell "Cognitive Load Increases" / "monotonically decreases" stale headings were already superseded by the 2026-04-12 Key Claims re-injection.
- [x] **NB 06 (orientation_evaluation):** 2026-04-13 — Cells 0, 11, 15 updated: butterworth ρ = −0.618 → ρ = −0.927 (*N* = 11 position medians); forward-only gaze ρ = +0.82 → annotated with *N* = 9 position means. Working Memory framing was already removed in prior sweeps.
- [x] **NB 14 (butterworth):** 2026-04-13 — Cells 9 and 13 updated to post-audit ρ = −0.927 with *N* = 11 position medians, retaining reference to pre-fix ρ = −0.618 via the K3 audit note. Survivor-bias caveat now lives in `docs/methodological-threats.md` §8 and NB14 prose points there.
- [x] **NB 23 (rank_effects):** 2026-04-13 — Cells 0 and 13 renamed "per fixation" → "per position" (Butterworth LF/HF is a position-median statistic, not a per-fixation statistic). Cell 14 split of LHIPA vs Butterworth was superseded by the K18–K28 organic-rank re-indexing in the 2026-04-10 NB23 rebuild.

### Docs to update

- [x] **findings.md line ~217 (was ~211):** 2026-04-13 — "on position medians, N = 2,719 trials" → "on *N* = 11 position medians aggregated from 2,719 trials" for NB14:K3.
- [x] **findings.md line ~98 (was ~92):** 2026-04-13 — forward-only dwell ρ = +0.82 annotated with *N* = 9 position means.
- [x] **README lines 100–101, 106:** 2026-04-13 — N disclosures added to fixation-count / dwell-time rhos (N = 10), Butterworth rho (N = 11), forward-only gaze rho (N = 9), and steep-phase / plateau subranges (N = 4, N = 7).
- [x] **README line 117:** 2026-04-13 — Reconciled. Now cites trial-level ρ = −0.088 (*N* = 2,721 trials, *p* = 4.1 × 10⁻⁶) [NB05:K8] as primary; position-mean ρ = −0.903 (*N* = 10) demoted to boundary-step companion with explicit ecological-fallacy pointer [NB05:K9]. The stale `-0.87` is gone.
- [x] **methodological-threats.md:** 2026-04-13 — Added §8 "Survivor Bias in Per-Position Aggregates" covering all three tiny-N position-aggregate rhos, ecological-fallacy framing, mitigation strategies, and the trial-level-first reporting rule.

### Systemic: position-median correlations

All three headline rhos are on tiny N:
- LHIPA rho = -0.903: N=10 position means
- Butterworth rho = -0.618: N=11 position medians
- Forward dwell ratio rho = +0.82: N=9 position means

Every citation should state the actual N. The trial-level or within-trial statistics should lead.

### Individual differences & strategy segmentation (2026-04-11)

- [ ] **LF/HF trajectory segments vs satisficer/optimizer:** Cross-tab is null (chi2 = 0.52, p = 0.77). LOO logistic regression from 6 LF/HF features → AUC = 0.43 (below chance). **LF/HF trajectory is orthogonal to sat/opt.** Strongest trend: early/late ratio (p = 0.106, d = 0.44). This is a meaningful null: load trajectory and behavioral strategy are independent dimensions.
- [ ] **Connect to Dumais et al. (IIiX 2010):** Their economic vs exhaustive evaluator clusters (gaze AOI fixation impact, scanpath completeness/linearity) map conceptually to our speed terciles. Do our 3 LF/HF segments (declining/flat/increasing) align with their 3 gaze clusters? Need scanpath completeness and linearity from AdSERP fixation data.
- [ ] **Connect to Buscher/Huang et al. (WSDM 2012):** Cursor-feature clustering on Bing. AdSERP has cursor data — replicate cursor-based strategy identification and cross-reference with LF/HF segments.
- [ ] **Stability of LF/HF segments across blocks:** "Increasing" group (N=8) could be noise. Test within-subject consistency across the 6 blocks per participant.
- [ ] **Dumais 2010 as F-pattern reference:** Good empirical F-pattern characterization with individual differences decomposition — add to OSEC explainer references.

### Explainer TODO

- [x] **F-pattern survivor bias:** 2026-04-13 — Added a fifth panel "SUBTRACT SURVIVOR BIAS" to `f-dissection.png` that downsamples each fixation index to the minimum count, equalizing contribution across indices. Updated `scripts/generate_explainer_heatmaps.py` and `site/explainer/index.html` with the new panel and walkthrough prose. Finding: in the deep-evaluator cohort, residual attrition is small (1,076–1,184 fix-index range, ~10 %); the fifth panel is visually almost identical to the fourth. Most of the F's vertical fade comes from survey + regressions + quick-clicker confounds, not from survivor bias inside the deep cohort. Cross-link to `docs/methodological-threats.md` §8.
