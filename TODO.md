# TODO

Organized by paper track, then by infrastructure / open research.

CIKM 2026 paper shipped at `v1.0.0` (2026-05-24). Items that were
CIKM-anchored or covered by 2026-05-24 findings are archived at the
bottom of this file.

---

## AllSERP arxiv update queue (active)

The 2D cell-aware merge landed 2026-05-24 (commits `5f694be6` family +
the four 2026-05-24 findings on the dd_top substrate). The arxiv update
should land 1D-analysis reproducibility against v1.0.0 plus the cell-
aware extensions that the v1.0.0 substrate physically cannot resolve.

- [ ] **Validate 1D-analysis reproducibility against v1.0.0 anchor.**
  Re-run the §5 driver scripts (the five drivers in
  [`cikm-leakycursor/reproducibility-map.tex`](../cikm-leakycursor/reproducibility-map.tex))
  against `v1.0.0`-tagged code; confirm numbers in summary sidecars
  reproduce. The v1.0.0 tag freezes the CIKM-cited state for the
  arxiv update to anchor against.
- [ ] **Promote `F:ad-utility-prior` into AllSERP §X.** Per-participant
  ad-utility axis (gaze-derived prior × click behavior). Source:
  [`docs/ad-utility-prior.md`](docs/ad-utility-prior.md). Methodology
  framing in [`docs/methodology/gaze-prior-elicitation.md`](docs/methodology/gaze-prior-elicitation.md)
  — non-disruptive prior elicitation as a generalizable protocol.
- [ ] **Promote `F:dd-top-cell-promiscuity` into AllSERP §X.** Within-
  ad-carousel sampling as a stable individual-difference trait
  (split-half r = 0.83, SB = 0.90, n = 47), independent of the gaze
  prior. Source: [`docs/dd-top-cell-promiscuity.md`](docs/dd-top-cell-promiscuity.md).
  Pair with the prior-elicitation framing: same cursor instrument,
  two spatial grains, two traits.
- [ ] **Promote `F:long-regression-event-class` into AllSERP §X.** Event-
  level dissociation: long organic regressions are near-pure vertical
  saccades + cursor lag. Mostly distance-controlled stride with soft
  top-of-stream attractor (slope of dest on source = +0.63 for size
  >= 4; 73% land at positions 1-3). Source:
  [`docs/long-regression-event-class.md`](docs/long-regression-event-class.md)
  + [`docs/null-findings/2026-05-24-long-regression-rate-not-trait.md`](docs/null-findings/2026-05-24-long-regression-rate-not-trait.md)
  (two addenda: dwell-vs-distance null; absolute-vs-relative model).
- [ ] **Promote the dd_top Markov substrate.** 1,581 trials, 132K
  fixations, 131K transitions, alphabet size 30. Sequence-level
  structure with weighted transition entropy 2.17 bits (vs 4.91-bit
  ceiling). Substrate for any future semi-Markov / matrix-cluster
  segmentation work. Source: [`scripts/output/dd_top_markov/`](scripts/output/dd_top_markov/).
- [ ] **CIKM headline: 4-fixation visual budget.** Internal anchor at
  [`docs/findings.md`](docs/findings.md) §10c (committed `60c2cc7a`).
  Held for arxiv preprint anchor; now land in the AllSERP update
  rather than as a separate post.
- [ ] **4-construct attention decomposition framing.** Decomposing
  "attention" on SERPs into four measurable constructs (overt fixation,
  viewport exposure, interaction latency, processing speed) where the
  field uses one undifferentiated term (Zhang et al. CHIIR '26). Frame
  relative to AdSight (same data, prediction focus) and Zhang et al.
  (same lab, definitional focus). Slot into AllSERP §X or §Discussion.
- [ ] **AI authorship disclosure paragraph for arxiv preprint.** Scope:
  tools used (Claude analysis/prose, embedding model for content features),
  role taxonomy, ACM rules. Two-tier draft: short acknowledgements
  sentence + longer methods paragraph for venues that want detail.
  GitHub history records every AI-assisted commit via `Co-Authored-By`
  trailers — footnote pointer strengthens the disclosure.

## ETTAC pupil-LFHF paper (Duchowski; deadline 2026-05-15 passed)

Status: held until next-pass review. The stat-traceability gaps below
need re-derivation or original-computation surfacing before any
external pass.

- [ ] **2,719 trials retained (1-second LF/HF window).** Methodology-
  specific filter; doesn't match NB14:K1 (2,416 absolute / 2,174
  organic). Re-derive from `validate_adserp.py` or document the filter
  difference.
- [ ] **Bootstrap 95% CI [−0.893, +0.143] on plateau Spearman.** Bootstrap
  value, source not located. NB14:K11 has ρ = −0.714, p = 0.071
  absolute; CI not in any output JSON.
- [ ] **Capped plateau ρ = −0.786, p = 0.036** (participant-concentration
  audit, cap at 10 segments per ppt per pos). One-off audit value, not
  in canonical Key Claims.
- [ ] **§3 prose reframe.** NB14 numbers update (steep ρ = −1.000 holds;
  full corpus −0.655; plateau ρ flips n.s. under typed). Drop joint
  LF/HF × RIPA2 dissociation claim or hold absolute as primary with
  cascade shift as sensitivity finding.
- [ ] **Within-trial peak-load paragraph.** Local edit landed at
  `pupil-lfhf/ettac/adserp.tex` after the Spearman paragraph (line ~99).
  Headline: peak-LF/HF position has 35.0% click rate vs 10.2% same-trial
  (N=2,174 trials / 10,234 records, 3.4× lift, z=+29.7); peak position
  regresses LESS than other positions (53.0% vs 61.5%, p=2.1e-13).
  Source: `scripts/max_lfhf_uniqueness.py`.

§Predicting return: **resolved** via within-item paired Δ (replaces the
6,112-record cluster bootstrap). New paragraph in v2.4 draft.

## RIPA2 standalone

- [ ] **R1 / RIPA2-paper coordination.** R1 per-fixation amplitude
  differential dies under bbox (rank-pooling artifact); replacement in
  [`docs/null-findings/r1-ripa2-bbox-collapse.md`](docs/null-findings/r1-ripa2-bbox-collapse.md).
  Discuss before paper framing locks. Flag if standalone draft includes
  the AdSERP per-fixation will-regress claim.

## Task model paper (future submission)

Canonical: `docs/drafts/task-model-paper.md`. The `.tex` is a
derivative artifact with known drift. When ready, regenerate from .md
rather than editing both.

- [ ] **Unplaced citations in §2.** Kuhlthau, Marchionini, Bates, Belkin,
  Hornof & Kieras, Payne & Duggan mentioned inline without `\cite{}`;
  no `references.bib` entries. Add bib entries before any arxiv compile.
- [ ] **"Click models cannot see this" rhetoric.** Rephrase as construct-
  inventory claim, not expressivity. A neural ranker *with* saccade
  features can see phase structure; it just isn't trained on them.
- [ ] **Null-as-support on survey duration.** §5.3 concludes fixed-
  duration from three null difficulty correlations. Reframe as "not
  detected at this granularity (spread, Jaccard, density all ρ ≈ 0,
  p > 0.3), consistent with a fixed-budget sampling routine."
- [ ] **Overly-general claim in §5.8.** Soften "click models cannot
  represent" to "as currently specified do not represent; the present
  result motivates doing so."
- [ ] **Mind-reading in §3.5.** Drop scare-quoted "cognitive state of
  'I already know what I'm looking for'" at `task-model-paper.md:68`.
  Hedge to "consistent with a verification-mode interpretation, not
  uniquely identifying one."
- [ ] **"~866 ms parafoveal processing time" load-bearing and uncited.**
  Source to NB04. Don't use "parafoveal processing" loosely — prefer
  "inter-fixation time not integrated by FPOGD."
- [ ] **NB25 K9 as second empirical anchor for fixation-5 phase
  boundary.** Per-result absolute gaze dwell ρ(dwell, click) = +0.014
  ns (n=2,836) Survey vs +0.262 (p≈10⁻¹⁹⁴, n=12,392) post-Survey —
  18.9× ratio. Click-level dissociation at the same boundary saccade-
  amplitude transition identifies.
- [ ] **NB25 phase-dependent baseline sign flip.** Cell 13: Survey-phase
  cos-sim → dwell slope +0.10 (predictable content gets longer dwell,
  *wrong direction*); post-Survey slope −1.46 (novel content gets longer
  dwell, correct direction). Reichle/Rayner reading-time novelty curve
  only exhibited in deliberative phase.
- [ ] **Long-regression transition class.** Today's `F:long-regression-
  event-class` gives the task model a clean event-class to parameterize:
  distance-controlled stride (~4-5 back) with soft top-of-stream
  attractor, no participant-level latent required.

## Cross-cutting infrastructure

- [ ] **Ad text + embeddings.** `serp-embeddings.json` covers organic h3
  only — ad text/embeddings absent. To enable per-etype content analyses
  (LF/HF × content × etype, query-cosine for ad copy, ad-vs-organic TTR
  distribution): (a) ad-text extractor for `dd_top` / `native_ad`
  regions; (b) embed via mxbai-embed-large at port 8890; (c) emit
  `serp-ad-embeddings.json`; (d) extend `compute_content_features.py`
  with `--attribution organic_hybrid`/`typed`. Volume: 1,581 dd_top +
  3,670 native_ad ≈ 5,251 positions.
- [ ] **Refresh `scripts/output/figures/INDEX.md` for cascade.** Several
  render outputs got new captions/findings under bbox/typed; index is
  pre-cascade. Coupling-traces caption needs rewrite.
- [ ] **`plot_approach_retreat_hero.py` exemplar trials hand-pick.**
  Pinned to absolute because curated COMMIT exemplar (p015-b1-t5
  pos=2) reattributes away from 'clicked' under bbox. Pick from
  `cursor-approach-features-typed.json`.
- [ ] **AR README: promote NB28 placeholders to actual numbers.**
  Calibration retrain done; [`docs/methodology/attribution-cascade-synthesis.md`](docs/methodology/attribution-cascade-synthesis.md)
  §4.3 has the numbers ready. (Cross-repo: edit lives in `approach-retreat`.)
- [ ] **Place Dumais, Buscher & Cutrell (IIiX 2010) citation** wherever
  satisficer/optimizer is introduced. Lit-note stub at [`docs/lit-notes/lit-review-scroll-regressions.md`](docs/lit-notes/lit-review-scroll-regressions.md)
  §6b. Bibtex entry needed.
- [ ] **Extend Key Claims to remaining cited notebooks.** Four worth
  promoting: NB01 (mouse-gaze AUC, scroll-enriched click prediction),
  NB02 (Huang −700ms gaze-leads-cursor replication), NB08 (§2 four-
  granularity null), NB10 (satisficer/optimizer split). Pattern: pull
  5–8 numbers per notebook, add `NB##_BODY` to
  `notebooks-v2/update_key_claims.py`. Est. 1–2 hours.
- [ ] **Forward-only vs regressive split across all analyses.** Most
  current findings pool forward with regressive. 1,465 of 2,341 tagged
  trials are `regressive_scroller`. Re-run NB23, NB24, NB20, NB01, NB05
  with explicit partition. Retreat direction and "retreat as epistemic
  action" claims likely direction-specific.
- [ ] **Mouse dwell vs time on screen.** Current cursor dwell conflates
  "lingered at X" with "X visible in viewport." Normalize per-result
  cursor dwell by viewport exposure time (NB06). Likely affects
  consideration-set finding in NB01.
- [ ] **Mouse resting position.** Where do cursors park between
  interactions? Right margin, last clicked, viewport center, off-screen?
  Individual-difference candidate (`mouse_independent` tag, 1,434
  trials). May reveal default "home" that retreat episodes return to.
- [ ] **`references.bib` duplicates** — chore.

## Schul-replay viewer (AF gh-pages)

- [ ] **Progressive foveation reveal.** Synch foveated content with
  playback timeline. Currently disabled (Progressive button removed).
  DOM-anchored clip-mask approach implemented but has coordinate/canvas
  sizing issues.
- [ ] **Pupil dilation visualization.** Overlay pupil diameter on
  timeline and/or as fixation circle size modulation. More immediately
  valuable than progressive foveation.
- [ ] **Reading span in batch gazeplots.** SERP reading is asymmetric
  (~5 deg right, ~1.3 deg left per Rayner). Scrutinizer v2.4 has this
  for live replay (velocity-gated); batch mode has no velocity signal.
  Infer reading direction from consecutive fixation dx.
- [ ] **Scrutinizer gazeplot at window width.** Re-capture at 1422px
  (original CSS viewport) using DOM-anchored fixation positions.
  Currently 1280px (screen pixel width).
- [ ] **Time offset hash param.** Support `#t=1.4s` in viewer URLs to
  jump to specific timestamp.
- [ ] **Gaze velocity timeline tracks.** Add X-velocity and Y-velocity
  as multitrack lines. Wide X jumps + big Y drops during survey, tight
  X oscillations + small Y steps during evaluate. Makes orient→survey→
  evaluate transition visually obvious.
- [ ] **Scanpath overlay controls.** Replace Lines/Numbers toggles with:
  scanpath on/off, foveated filter on/off. Popover menus with
  transparency sliders.
- [ ] **Sub-segmenter for tall organic cards.** Row-projection merges
  visually-dense blocks. First seen on `p007-b6-t8` (Sephora + Barcelona
  Maps + local pack collapsed into h=436 organic). Within any flagged
  tall card (h ≥ SUSPICIOUS_H), run second pass that finds horizontal
  edges or color-transition rows. Implement when >2 curated AR replay
  trials hit this.

## Open research / next pass

- [ ] **Ski-jump null-finding update (2026-05-06).** AllSERP's flavor-
  comparison rank-effect chart shows organic-only click rate at rank 7
  = 4.1 %, jumping to 7.6 % at rank 8 and 8.2 % at rank 9 — a +85 %
  uptick larger than the documented cohort-A result. Under organic-
  hybrid, the uptick disappears. Three plausible reasons: sample
  thinning under organic-only; cohort-A leakage; stale file.
  - [ ] Confirm whether `cursor-approach-features-organic.json` was
    regenerated post-coord-fix or carries pre-fix labels.
  - [ ] Re-run the ski-jump null-finding's full-corpus check using the
    AllSERP-style per-record-at-position click rate.
  - [ ] Add cross-reference from `2026-04-12-ski-jump-audit-collapse.md`
    to AllSERP's §4.2 flavor comparison.
- [ ] **Temporal dynamics: approach velocity over trial and over
  session.** Two effects: (a) within-trial — does approach velocity
  slow as WM fills? Framework compilation (§3b-iv) predicts later
  approach episodes are *faster* (criteria already compiled), not
  slower. (b) Across-trial — ~60-trial-per-ppt practiced effect likely
  dominates within-trial.
- [ ] **Practiced-participant learning curve.** ~60 trials each. Plot
  all key metrics by trial ordinal: orientation time, survey duration/
  amplitude, saccade slope, regression rate, click position, approach-
  retreat rate, pupil shape. Asymptotic = power users; early = first-
  time. Could be its own notebook (18_learning_curve.ipynb).
- [ ] **Forward-only regression stratification.** Forward-only ρ = +0.82
  pools all trials. Separate: (a) trials with zero regressions, (b)
  forward segments within regression trials. Different?
- [ ] **Satisficer vs optimizer LHIPA.** Do satisficers (low-regression)
  have higher trial-level LHIPA than optimizers? Notebook 10 ×
  notebook 05. Subject to the duration confound noted in
  [`docs/null-findings/2026-04-16-satopt-lhipa-duration-confound.md`](docs/null-findings/2026-04-16-satopt-lhipa-duration-confound.md).
- [ ] **RecGaze replication.** de León Martínez et al. (SIGIR 2025) —
  87 users, 3,477 interactions on horizontal carousel interfaces. Test:
  does survey phase (wide saccade → narrow) appear in horizontal lists?
  Swipe-back = scroll regression. GitHub: santideleon/RecGaze_Dataset.
- [ ] **COLET dataset for ETTAC LF/HF validation.** Cognitive workLoad
  Estimation from Eye-Tracking (ScienceDirect 2022). Validates LHIPA
  vs Butterworth on independent data.
- [ ] **Explicit attention definitions per notebook.** Zhang et al.
  (CHIIR 2026) argues "attention" conflates 4+ constructs. Each
  notebook should state which it measures.
- [ ] **Scroll velocity decomposition.** Forward vs backward scroll
  velocity as distinct features. Backward velocity is high because user
  *knows* target location — different signal than forward deceleration.
- [ ] **Local novelty → regression triggers.** Per-result novelty
  (deviation from cumulative overlap trend) predicting next scroll-back
  event. Time-series, not aggregate.
- [ ] **AdSERP Attention_trial metric.** Use Attention_trial (fixation
  duration on AOI / total fixation duration) as DV instead of raw
  fixation duration.
- [ ] **Pupil dilation × regressions.** Do pupils dilate during scroll
  regressions? Cognitive load / surprise signal.
- [ ] **Earliest predictor refinement.** 14.9s first-fixation signal
  uses 150px Y radius. Sensitivity on radius. Does first-fixation
  duration on eventual target differ from non-clicked results?
- [ ] **Search abandonment literature.** Connect to forced-choice
  paradigm. Diriye et al. 2012, Bruckner et al. 2020 ("Query
  Abandonment Prediction") characterize the alternative outcome.
- [ ] **Residual dwell model.** Map fixation-time per result as
  function of lexical overlap to establish baseline. Residuals predict
  interest/click. May need per-user calibration from early-session
  features.
- [ ] **Priming × user strategy interaction.** Re-run
  `serp_priming.ipynb` with sat/opt terciles as moderator.
- [ ] **Personalized lexical divergence.** If dwell-time residuals
  flag "lexical divergences of interest," those terms could enhance
  subsequent queries — user-specific signal of novel-vs-already-known.
- [ ] **TTI as individual calibrator.** Time-to-first-scroll as proxy
  for individual processing speed. Session-start calibration without
  training data.
- [ ] **LF/HF segment stability across blocks.** "Increasing" group
  (N=8) could be noise. Test within-subject consistency across the
  6 blocks per ppt. (The cross-tab × sat-opt was null; the three
  axes are confirmed independent by the 2026-05-24 work.)

## SERP difficulty — better measures

Bag-of-words Jaccard (mean=0.151) and sentence embeddings both null
within-position. % multi-fixation episode signal (p=0.004) suggests
something is there, but token overlap is wrong lens.

- [ ] **Relevance spread (query-result alignment variance).** Embed
  query + each result, compute cosine similarities. If all results
  equidistant from query (low variance), SERP is hard. If one is much
  closer, easy.
- [ ] **Distinctive feature density.** Count tokens appearing in only
  one result. High unique-token density = easy. Weight by TF-IDF.
- [ ] **Named entity / brand diversity.** Extract brand names, model
  numbers, prices. SERPs where all results are different brands are
  easier.
- [ ] **Price variance (where extractable).** Product SERPs often show
  prices. High price variance = easy discrimination axis. Regex on
  snippet text.
- [ ] **Visual distinctiveness (rendered SERP).** Image-level perceptual
  hashing or SSIM between result blocks. Captures what the *eye*
  discriminates, not what NLP measures.
- [ ] **Product taxonomy partition.** Classify queries into product
  categories. Analyze foraging *within* category. Difficulty may be
  categorical, not continuous.
- [ ] **Information sufficiency.** Some products evaluable from snippet
  (price, brand, rating); others require click-through.
- [ ] **Adjacent-pair similarity.** All-pairs Jaccard weights pos 0 vs
  9 equally with pos 3 vs 4. Consecutive-pair similarity = "didn't I
  just read this?" = re-reading trigger.

## Content analyses — deprioritized reference list (2026-04-19)

Kept for revisit if active items land positive and we need more
mechanism. Not active.

- [ ] **#3 Ad vs organic content contrast.** NB25 already tags etypes.
  Recompute content features within each class.
- [ ] **#5 Within-trial embedding-trajectory.** Distance traveled in
  embedding space across inspection order.
- [ ] **#6 LLM graded relevance (0–3).** Extends NB26 LTR idea to LF/HF
  as outcome.
- [ ] **#7 Entity-type density.** spaCy NER or one-shot LLM.
- [ ] **#8 Query-term bolding density.** Google bolds query-match in
  snippets; literal visual saliency.
- [ ] **#9 Title ↔ URL dissonance.** cosine(title, URL-domain).
- [ ] **#10 Rank-cosine surprise.** Residual of query_cosine after
  regressing on position.
- [ ] **#11 Cross-trial domain carryover.** Per-ppt brand/domain
  familiarity across consecutive queries.
- [ ] **#12 Parafoveal content acquisition** (word-bbox dependent).
- [ ] **#13 Per-word content features.** Frequency, concreteness,
  length, POS at fixated word.

## Design / product connections (notes, not tasks)

- E-comm intentionally introduces diversity to slow evaluation and
  reduce bounce. If content similarity affects re-evaluation speed
  (still unconfirmed), diversity would slow *re-evaluation* of
  previously-seen items.
- Mouse is "falling as an available signal" — mobile/touch has no
  cursor. Scroll + viewport features are the only behavioral signals.
  Our viewport-state finding (AUC 0.704 vs 0.548) is directly relevant.

---

## Archive (closed 2026-05-24)

### CIKM 2026 paper shipped at `v1.0.0`

The CIKM 2026 paper is frozen at the `v1.0.0` tag (attentional-foraging
`3fd6765a`, approach-retreat `4b1a010`). Items below were either landed
in the camera-ready or are now moot because the paper has shipped.
Subsequent extensions land in the AllSERP arxiv update (see top of file).

- Promote bbox `K-bbox-*` values into CIKM paper draft — done in
  camera-ready; paper frozen.
- Ordinal reframe + LambdaMART for paper-v4 §4.2/§4.5 — paper shipped
  at v1.0.0; ordinal/LambdaMART now part of the AllSERP update.
- Cross-paper drift on `> 15 s time-to-click` boundary — CIKM frozen;
  task-model paper aligns against v1.0.0 reference.
- Ski-jump table units cross-paper drift — same; CIKM frozen.
- Four-class taxonomy cross-ref in task-model paper — points to
  CIKM v1.0.0 anchor.

### Individual differences items (covered by 2026-05-24 findings)

- **LF/HF trajectory × sat/opt orthogonality** — confirmed by the
  three-axis dissociation in [`docs/ad-utility-prior.md`](docs/ad-utility-prior.md)
  (load × ad-utility ρ = +0.13 p = 0.37; sat-opt × ad-utility ρ = +0.02
  p = 0.87) and extended to a fourth axis by
  [`docs/dd-top-cell-promiscuity.md`](docs/dd-top-cell-promiscuity.md).
- **Connect to Dumais et al. (IIiX 2010)** — lit-note shipped at
  `approach-retreat/docs/references/dumais-2010-individual.md` and
  cited in the §4 companion-notebooks scaffold of CIKM v1.0.0.
- **Connect to Buscher/Huang et al. (WSDM 2012)** — covered in the
  cell-promiscuity finding's prior-art positioning; full citation
  treatment slots into AllSERP update.

### Methodology / infrastructure

- **Revisit null findings under typed cascade** — done as
  [`docs/null-findings/2026-05-04-typed-cascade-null-revisit.md`](docs/null-findings/2026-05-04-typed-cascade-null-revisit.md)
  (14 nulls triaged: 9 HOLDS, 2 VERIFIED under typed, 1 STRENGTHENS,
  2 HOLDS-by-inference; load-bearing R1 + LF/HF × satopt re-run under
  typed and replicate).
