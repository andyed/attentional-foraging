# Attribution Cascade Synthesis

**Stable ID:** `M:attribution-cascade-synthesis`
**Last verified against executed notebook output:** 2026-05-02
**Companion to:** [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md) (the pipeline spec)

---

## What this document is for

Between 2026-05-01 and 2026-05-02 we migrated the AdSERP analysis stack from
**absolute-rank attribution** (h3 + ads pooled, band-estimated AOIs) to
**bbox-organic attribution** (CV-extracted organic-result bounding boxes,
ads excluded by construction). This document is the synthesis: which
findings hold under the new attribution, which weaken, which collapse,
which flip — and what that means for each paper strand.

This is the gate for theoretical pivots: before any paper prose moves to
organic-rank as the primary frame, the empirical diff must be on the
table.

The driving question, framed by Andy: *does the prior utility and story
hold up under organic rank?* If yes, we move full-steam-ahead and aim to
generalize back to ad+organic behavior (a third attribution we don't yet
have wired through cursor-approach). If no, we stop and rebuild.

The short answer: **the approach-retreat / four-class-taxonomy strand
holds up cleanly. The R1 RIPA2-leg dissociation does not. Paper-by-paper
implications below.**

---

## §1 Why bbox-organic is the right primary

Three reasons documented in [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md):

1. **Construct cleanliness.** "Position 3" under absolute pools an ad-3
   with an organic-3; under bbox they are different surfaces with
   different policies. Ads are essential distractors, not first-class
   attentional targets — the cursor/gaze geometry that matters for the
   task model is *what the user did with the organic ranking*, with ads
   as dynamic noise.
2. **Pixel accuracy.** Band estimation assumes uniform result heights;
   organic results are 80–320 px tall in practice. Bbox AOIs are within
   ±2 px of the rendered HTML.
3. **Click attribution audit.** Tolerance-aware bbox attribution
   (rejecting clicks that fall in ad rects before snapping to the
   nearest organic) reassigns 411 of 2,762 prior "clicks" — most of
   which were ad-clicks pooled into organic-3 by the absolute scheme.

The cascade trail is in [`organic-result-aoi-extraction.md §10`](./organic-result-aoi-extraction.md);
the two-pass producer-then-consumer migration shipped on
`feat/aoi-pipeline-v2` between commits `60a2e7b9` and `85697062`.

---

## §2 Per-finding category table

Each row cites the canonical K-ID (or figure name) and gives the legacy
absolute value, the bbox-organic value, and a one-line interpretation.
Source-of-truth: [`docs/notebook-key-claims.md`](../notebook-key-claims.md)
(generated from the in-notebook K-claims cells).

### §2.1 PRESERVED (sign + significance unchanged)

| K-ID / Figure | Absolute | Bbox-organic | Reading |
|---|---|---|---|
| **NB21:K-bbox-3** M3 LOSO AUC (position+dwell+approach) | 0.859 ± 0.044 | **0.865 ± 0.044** | AR brand claim ("9 cursor features → AUC ≈ 0.86 LOSO") tightens |
| **NB21:K-bbox-4** M4 LOSO AUC (approach-only) | 0.861 | **0.864** | Approach features still load-bearing without rank |
| **NB21:K-bbox-8** Leakage Δ (KFold − LOSO) | +0.002 / −0.000 / −0.002 | **+0.001 / +0.000 / +0.000** | Subject-shuffle invariance preserved |
| **NB21:K-bbox-9** Per-participant LOSO M3 AUC median | 0.860 | **0.872** | Tighter at the per-subject level |
| **NB21:K-bbox-10** Brier score (M3 OOF) | 0.1526 | **0.1437** | Calibration improves |
| **NB22** four-class motor-signature dissociation (`deferred_vs_rejected_four_panel.png`) | p < 10⁻⁹ / p < 10⁻¹⁹ | **p < 10⁻⁹ / p < 10⁻¹⁹** | Cursor-gaze distance and dwell deltas survive cleanly |
| **NB23** rank-effects framework-compilation pattern | sign preserved | **sign preserved** | Unified rank effects (load decreases with position) holds |
| **NB24** retreat-arc geometry coverage | 1,490 raw arcs (absolute-only) | **5,201 raw arcs (organic_hybrid 3.5× coverage)** | Hybrid attribution dominates; top-ad lateral/arc 0.166 → 0.170 (replicates) |
| **NB14:K6** steep-phase position-load slope (P0–P3) | ρ = −1.000 | **ρ = −1.000, p = 3.2 × 10⁻²³** | ETTAC headline holds tightly |
| **NB18:R1** LF/HF leg of will-regress vs no-regress | d=+0.041, p=0.011 | **d=+0.041, p=1.1e-03** | "Lingered first time" survives |

**Read:** the approach-retreat strand and the four-class taxonomy
strand transfer cleanly. The brand claim ("9 task-model-derived cursor
features reach AUC ≈ 0.86 in LOSO") survives and tightens. **AR-strand:
go.**

### §2.2 WEAKENED but significant (effect size shrinks, sign holds)

| K-ID / Figure | Absolute | Bbox-organic | Reading |
|---|---|---|---|
| **NB14:K3** Butterworth LF/HF Spearman ρ vs position | ρ = −0.927 | **ρ = −0.655, p < 10⁻⁴** | Cognitive-load-decreases-with-position survives. Effect size shrinks because rank pooling under absolute had ads inflating "position 0" at the top of the steep part of the curve. |
| **NB14:K10** Steep phase MW p | 3.2 × 10⁻¹⁰¹ | **3.2 × 10⁻²³** | Still strongly significant; smaller N (4,450 segments vs 6,112) drives the smaller p, not effect-size attenuation. |
| **NB21:K-bbox-1** Click rate | 16.6% (2,228 clicks) | **14.9% (2,205 clicks)** | Click rate "drops" only because some prior clicks were ad-clicks reattributed away from organics. |
| **NB21:K-bbox-7** M3 LOSO AP | 0.611 | **0.575** | AP baseline shifts with click rate; M3 AUC unaffected. |
| **NB21:K-bbox-2** Trials with valid features | 2,339 | **2,701** | Coverage *improves* under bbox (+15.5%) — pipeline finds organics on trials that were previously skipped because absolute attribution couldn't disambiguate. |

**Read:** every weakening is principled — it traces to either the
pool-with-ads inflation (K3 effect size) or the smaller-N-after-bbox
trials (K10 p-value), not to a structural breakdown.

### §2.3 STRENGTHENED under bbox

| K-ID / Figure | Absolute | Bbox-organic | Reading |
|---|---|---|---|
| **NB21:K-bbox-6** M1 LOSO AUC (position-only) | 0.613 ± 0.090 | **0.727** | **+0.114** — position is *much* more predictive when organic-rank is properly defined. The legacy 0.613 was diluted because absolute "rank 1" pooled top-organic with top-ad, two surfaces with different click policies. |
| **NB21** M3 standardized `position` coefficient | −0.130 | **−0.248** | Coefficient nearly doubles in magnitude: rank is a cleaner predictor when ads aren't mixed in. |
| **NB14** per-participant `vt_top` median direction | positive at P0, attenuating to 0 at P5 | **same shape, sharper** | Calibration target preserved (NB28 retrain pending). |

**Read:** these are the *new* findings that the cascade unlocked. They
deserve prose attention in the CIKM paper §5 viewport-bands result and
in the click-prediction §4 results. Position is a paper-relevant
predictor — not a control variable to absorb away.

### §2.4 COLLAPSED (significance lost; claim retired or reframed)

| K-ID / Figure | Absolute | Bbox-organic | Reading |
|---|---|---|---|
| **NB18:R1 RIPA2 leg** of will-regress dissociation | d=+0.006, p=0.0058 | **d=+0.006, p=8.0e-01** | Per-fixation arousal-amplitude differential between will-regress and no-regress items disappears. Direction unchanged, statistical leverage lost. **Most likely:** the legacy p=0.0058 was a rank-pooling artifact that benefitted from N inflation; under bbox the per-fixation RIPA2 means are essentially identical. |
| `coupling_traces.png` three-band separation | eval-rej ≈ 220 / def ≈ 300 / click ≈ 390 px | **all three traces collapse to ~400 px with overlapping IQR** | The "coupling set at episode entry, held for the duration" mechanism story was confounded with AOI size. Wide ad+organic AOIs gave eval-rejected episodes room to track gaze closely; tight bbox AOIs constrain coupling distance into a single ribbon. **Sub-claim retired**, motor-signature dissociation (cursor-gaze *distance*, dwell — different metrics) preserved. |
| **NB14:K11** plateau-phase position-load slope (P4–P10) | ρ = +0.482 | **ρ = +0.321, p = 0.482 (n.s.)** | Plateau "rebound" loses statistical leverage. Direction preserved (positive); story is now "steep then flat" not "steep then re-rises." |

**Read:** R1 RIPA2 collapse is the most consequential. It says the
"lingered but processed shallowly" *joint* signature was a pooled-rank
artifact — only the LF/HF (sustained autonomic engagement) leg holds
per-fixation under clean attribution. The coupling-traces collapse is
mechanistic rather than headline (the four-panel motor dissociation
preserves the deferred-vs-rejected dissociation through different
metrics).

### §2.5 FLIPPED (sign change)

None at the K-ID level. The plateau ρ flipped (+0.482 → +0.321) but
the sign is unchanged. No K-ID has a directional reversal under the
cascade.

**Read:** absence of sign-flips is a sanity check. If bbox attribution
were structurally pathological, we'd expect at least one direction
reversal among 30+ headline numbers.

### §2.6 NOT YET MEASURED

| K-ID / Figure | Status | Blocker |
|---|---|---|
| **NB28** viewport-band calibration retrain | Inputs ready (`cursor-approach-features-organic.json` + `regression_labels_cache_organic.json`); calibration not rerun | Multi-hour bootstrap (1,000 seeds × 47-fold StratifiedGroupKFold). Gates the CIKM §5 viewport-bands result. |
| **NB21** four-class taxonomy thresholds (K10/K11) | Stale under bbox | M3 score distribution shifts; threshold re-derivation pending |
| **NB22:K-bbox-5..8** four-class taxonomy fold-by-fold validation | Pending | Same regression-label producer migrated; full taxonomy re-validation requires re-running NB22 cells 6+ |
| **`plot_approach_retreat_hero.png`** exemplar trials | Pinned to absolute | Curated COMMIT trial reattributes away from 'clicked' under bbox; new exemplars need hand-picking |

---

## §3 Paper-strand implications

### CIKM 2026 (algorithmic, four-class taxonomy primary) — **GO**

Every load-bearing claim in the algorithmic submission survives the
cascade with sign + significance preserved or strengthened (§2.1, §2.3).
The brand statement ("9 task-model-derived cursor features reach AUC ≈
0.86 in LOSO") tightens. The four-class taxonomy structure is intact;
the deferred / evaluated-rejected motor-signature dissociation
(cursor-gaze distance p < 10⁻⁹, dwell p < 10⁻¹⁹) is preserved.

**Required prose updates:**
1. Move K-bbox-* values into result-section tables; demote legacy
   K-IDs to a "robustness across attribution" supplementary table.
2. Add the "position becomes more predictive under bbox" finding
   (M1 0.613 → 0.727) as a §4 paragraph: it's a result on its own,
   not a control-variable footnote.
3. Drop the `coupling_traces.png` three-band claim. Replace with
   the four-panel motor dissociation in `deferred_vs_rejected_four_panel.png`
   (which carries different and stronger evidence for the same dissociation).

### ETTAC 2026 (pupil-LF/HF, May 15 deadline) — **GO with one cut**

NB14 steep-phase result (ρ = −1.000 over P0–P3, p = 3.2 × 10⁻²³) holds
tightly. Full-corpus result (ρ = −0.655) holds with weaker effect size.
Plateau result loses statistical leverage; reframe as "steep then flat,"
not "steep then re-rises."

**Required prose updates:**
1. Update NB14 numbers in §3 results.
2. Reframe plateau-phase claim around the weaker ρ, no longer
   significance-claiming.
3. Acknowledge attribution choice in methods — bbox is primary; legacy
   absolute results available in supplementary.

### R1 / RIPA2 standalone (Gwizdka collaboration) — **REFRAME**

**The joint LF/HF × RIPA2 dissociation does not survive bbox.** Per
§2.4, RIPA2 leg p drops from 0.0058 → 0.80; LF/HF leg holds at p =
1.1e-03. This is a substantive empirical finding — the "lingered first
time, processed shallowly" *joint* signature was a rank-pooling
artifact at the per-fixation level. The story splits into two:

- **LF/HF-only "lingered first time" claim:** survives, smaller story,
  publishable as a methodology validation of Butterworth IIR per-fixation
  windowing on AdSERP.
- **RIPA2 per-fixation arousal-amplitude differential:** does not survive
  bbox attribution. Gavindya/team's separate RIPA2 publication track
  needs to know before it leans on the AdSERP per-fixation result.

**Recommended action (to discuss with Gwizdka):** treat this as a
positive scientific result — the bbox cascade is a stronger validation
test than the legacy attribution allowed, and the LF/HF leg passing
while the RIPA2 leg fails is informative about the two metrics'
respective sensitivities. The R1 paper either publishes the LF/HF
leg alone, or holds absolute as primary with the bbox shift acknowledged
as a sensitivity finding.

Cross-link: this collapse is documented in
[`docs/null-findings/r1-ripa2-bbox-collapse.md`](../null-findings/r1-ripa2-bbox-collapse.md).

### Approach-retreat library + replay (CIKM data-curation submission) — **GO**

NB22 four-class taxonomy preserved; NB24 retreat-arc geometry
*improved* (3.5× coverage under organic_hybrid). The 80 curated AR-replay
trials were rebuilt on the new bboxes (commit `b5fb9f48`-adjacent).
Library API (`load_aois`, `organic_aoi_bands`, `attribute_click_to_organic`)
is bbox-aware end to end.

**Required:** AR README + gh-pages deploy carries the new captions and
the cascade audit trail. (Pending; tracked separately.)

---

## §4 Path to ad+organic generalization

If the AR-strand validation passes (it does), the next move is
generalizing back to ad+organic behavior — not to abandon ad attribution
but to bring it under the same pixel-accurate AOI regime as organics.

### What we already have

- **Per-trial ad bbox files** at `AdSERP/data/ads/{trial_id}.json`. Each
  contains `dd_top` (top-of-page ads), `native_ad`, `dd_right`
  (right-rail), already used by `scripts/compute_retreat_arcs.py`.
- **`compute_retreat_arcs.py --attribution organic_hybrid`** combines
  bbox organics with shipped ad rectangles in the result column
  (excludes `dd_right`). 5,201 raw arcs vs 1,490 absolute-only; top-ad
  lateral/arc replicates (0.166 → 0.170). This is a working hybrid
  pattern.
- **`extract_organic_bboxes.py`** has an `is_ad` x-overlap check that
  correctly excludes ad-overlapping organics. The pipeline knows about
  ads; it just doesn't currently surface them as first-class AOIs in
  the consumer JSONs.

### Gap: `compute_cursor_approach_features.py` has no hybrid mode

Currently `--attribution {absolute, organic}`. Adding `organic_hybrid`
means:
1. In feature computation, iterate AOIs in display order across both
   organic bboxes and ad rects (excluding `dd_right`).
2. Tag each record with `etype` (organic / dd_top / native_ad) so the
   downstream classifier and four-class labeler can stratify.
3. Emit `cursor-approach-features-organic-hybrid.json` (~17–18k records
   per estimated count, ~+20% over organic-only).

### Gap: regression-labels under hybrid attribution

`compute_regression_labels.py --attribution organic_hybrid` needs the
same etype-aware AOI list. The four-class taxonomy needs to decide
whether ad-clicks are "clicked" or a separate class — recommended
treatment (per the methodology spec): ad-clicks are `clicked_ad` (a new
fourth-class branch), not pooled with organic clicks.

### Validation plan once hybrid lands

1. **Reproduce M3 LOSO AUC under hybrid.** Expectation: between
   organic-only (0.865) and absolute (0.859) — should be near absolute
   since the pool resembles it. If hybrid AUC < absolute, ads are
   noisier than the legacy attribution assumed.
2. **Re-derive position coefficient under hybrid.** Expectation: between
   −0.130 (absolute) and −0.248 (organic). The size of the ad-pooling
   dilution effect.
3. **Four-class taxonomy under hybrid + ad-click branch.** Expectation:
   the "evaluated-rejected" class composition shifts (some prior
   eval-rejected at top-of-page were ads being scanned, not organics
   being rejected).
4. **Coupling-traces under hybrid.** Expectation: partial recovery of
   the three-band shape — wider AOIs allow more separation between
   classes than tight organic-only bboxes do, but less than absolute's
   pool-everything approach.

This is the next experiment to run. Estimated cost: 2–3 hours producer
work + 1 LOSO retrain + figure regen.

### §4.1 Validation results (2026-05-02)

Producer migration shipped: `compute_cursor_approach_features.py
--attribution organic_hybrid` writes `cursor-approach-features-organic-hybrid.json`
with **19,908 records / 2,774 trials / 13.0% click rate** (vs absolute's
13,419 / 2,339 / 16.6% and organic's 14,760 / 2,701 / 14.9%). Each record
carries an `etype` field: `organic`, `dd_top`, or `native_ad`. Hybrid
expands corpus coverage by another ~+15 % over organic-only because top-
and embedded-ads were previously unmodelled positions that the classifier
now sees.

**LOSO results (`scripts/nb21_loso_retrain_hybrid.py`,
`scripts/output/aoi-consumer-cascade/nb21_loso_hybrid.json`):**

| Model | Absolute (legacy) | Organic-only | **Hybrid** | Direction |
|---|---|---|---|---|
| M1 (position only) | 0.613 | 0.727 | **0.667** | ↗ above absolute, ↘ below organic |
| M2 (position + dwell) | 0.743 | 0.784 | **0.762** | between |
| M3 (full nine-cursor + position + dwell) | 0.859 | 0.865 | **0.870** | **best of three** |
| M4 (approach-only nine cursor) | 0.861 | 0.864 | **0.870** | **best of three** |
| Position standardized coefficient | −0.130 | −0.248 | **−0.112** | weakest under hybrid |
| Per-participant median M3 AUC | 0.860 | 0.872 | 0.864 | between |
| M3 Brier (OOF) | 0.1526 | 0.1437 | **0.1422** | best of three |
| KFold − LOSO leakage Δ | +0.002/−0.000/−0.002 | +0.001/+0.000/+0.000 | **+0.001/+0.001/+0.001** | clean across the board |

**Per-etype headline (M3 OOF on hybrid):**

| Etype | n | Click rate | M3 AUC on subset |
|---|---|---|---|
| `dd_top` (top-of-page ad) | 1,581 | **17.1%** | **0.916** |
| `organic` | 14,657 | 14.6% | 0.868 |
| `native_ad` (embedded ad) | 3,670 | 5.2% | 0.831 |

**Three findings the hybrid run surfaces:**

1. **The full-feature M3 wins under hybrid (0.870 > 0.865 > 0.859).**
   Adding ads as first-class AOIs *improves* classifier performance.
   The legacy absolute attribution mixed ads into the rank pool but
   didn't expose the etype-correlated motion patterns; the hybrid
   classifier sees both rank and surface type and benefits from the
   structure.

2. **Position is *weakest* under hybrid (−0.112), strongest under
   organic-only (−0.248).** This confirms the cleaner-construct logic:
   organic-only sees position most clearly because the rank label is
   homogeneous (all organics, no surface heterogeneity); hybrid pools
   surfaces with different click policies (dd_top click rate 17.1% vs
   native_ad 5.2%), so the rank-as-predictor signal is diluted in
   exactly the way absolute attribution diluted it. **Implication for
   paper prose:** the −0.130 → −0.248 strengthening under organic-only
   is *not* a methodology artifact — it's a finding about what kind of
   rank predicts behavior.

3. **Top-of-page ads have the highest click rate of any SERP surface
   (17.1%).** This was invisible under absolute attribution because
   dd_top fixations and clicks were pooled into "organic position 1."
   The hybrid surface-aware view says: the most clicked-on slot at the
   top of an AdSERP page is *the ad*, not the first organic. This is
   a publishable result on its own (and is consistent with the
   ad-pooling-inflation explanation for the legacy K-bbox-1 click-rate
   "drop" 16.6 % → 14.9 %).

**Open follow-ups from this validation:**
- Four-class taxonomy under hybrid (needs `compute_regression_labels.py
  --attribution organic_hybrid`; the gaze-regression detector is AOI-
  list-aware and ports cleanly).
- Coupling-traces under hybrid (figure regen with the hybrid features +
  hybrid regression labels; predicts partial recovery of three-band shape).
- Hybrid Bbox + click-policy stratified analysis: does the model that
  knows etype outperform a model that doesn't, on held-out clicks? If
  yes, etype is a recoverable feature — even from cursor-only WILD
  data — via classifier inversion.

**Bottom line:** the hybrid attribution validates §2 per-finding
synthesis. Organic-only is the cleaner *position* signal. Hybrid is the
better *predictive* signal. Absolute is dominated by both. The path
forward is to run paper prose against organic-only as primary (per §3)
while reporting hybrid as the deployment-aware variant.

### §4.2 Top-of-page is Survey-phase across surfaces (2026-05-02)

Tested whether the position-0 ambient-K + horizontal-saccade signal is
a top-multi-panel-carousel-ad (`dd_top`) phenomenon or a top-of-page
phenomenon, by computing saccade orientation and per-fixation K under
hybrid attribution and grouping by etype. Audit:
[`scripts/saccade_k_by_etype.py`](../../scripts/saccade_k_by_etype.py).

**Globally** dd_top is the most ambient etype (median K = −0.008 vs
organic +0.088, native_ad +0.012) and slightly more horizontal-biased
(38.9 % vs 37.4 % organic, 34.1 % native_ad). dd_top fixations behave
more like scanning than like reading, consistent with a carousel
layout where the user sweeps across cells.

**At position 0 specifically**, however, the ambient/horizontal signal
extends across surfaces: organic-pos-0 shows median K = **−0.067**
(more ambient than dd_top in the same slot), and 39.8 % horizontal
saccades (matches dd_top's 38.9 %). The Survey-phase-at-top pattern
is *not* surface-specific — it's a top-of-page property that captures
whatever sits in the first slot.

| etype | pos | n_sacc | %horiz | median K |
|---|---|---|---|---|
| dd_top | 0 | 41,755 | 38.9% | −0.008 |
| **organic** | **0** | 15,583 | **39.8%** | **−0.067** |
| native_ad | 0 | 8,936 | 33.9% | −0.102 |
| organic | 1 | 28,035 | 39.3% | +0.068 |
| organic | 2 | 21,090 | 39.2% | +0.117 |
| organic | 3 | 18,360 | 38.1% | +0.124 |
| organic | 5 | 10,491 | 35.1% | +0.136 |

**Three-signal convergence at the Survey → Evaluate boundary.** Three
independent families flip together between pos 0 and pos 1 on organics:

1. **Saccade amplitude** (NB13:K3, established 2026-04-12): per-trial
   amplitude slope ρ = −0.135, *t* = −29.63, *p* = 9.33 × 10⁻¹⁶⁸ within
   trial. Amplitude drops between fixation 5 and fixation 6 — Survey
   ends.
2. **Saccade orientation** (this audit): horizontal share drops
   39.8 % → 35.1 % across organic positions 0 → 5. Pos 0 is
   horizontal-biased; deeper ranks shift to vertical.
3. **K-coefficient** (this audit): median K −0.067 → +0.136 across
   organic positions 0 → 5. Pos 0 is ambient (short fixations + long
   saccades = scanning); deeper ranks become focal (long fixations +
   short saccades = reading).

The signals come from different feature spaces (amplitude / direction /
duration-vs-amplitude balance) and they converge cleanly. This is
convergent validation for the OSEC Survey → Evaluate transition that
NB13's amplitude-only result has carried so far.

**Surface contrast.** native_ads are the inverse of dd_top: most
vertical (42.1 %), least horizontal (34.1 %), borderline-focal K. This
matches their typical embedded-text-link layout where the user reads
top-down rather than scans left-right. The three etypes carry three
distinct motor signatures, and only dd_top's ambient signature partly
overlaps with the position-0 Survey signature.

**Implication for paper prose.** The OSEC Survey-phase claim now has
three convergent signal families instead of one. Worth promoting from
NB13-only to a multi-signal §3 paragraph in any task-model writeup.
The top-of-page is Survey across whatever surface lives there;
specific etypes (dd_top, native_ad) carry their own additional motor
signatures on top.

### §4.3 Will-regress per-fixation replacements for the dead RIPA2 leg (2026-05-02)

Following the R1 RIPA2-leg collapse (§2.4) and the dilution-mechanism
resolution (`docs/null-findings/r1-ripa2-bbox-collapse.md`), scanned
candidate per-(trial, organic position) predictors of will-regress
under bbox attribution. Audit:
[`scripts/will_return_predictor_scan.py`](../../scripts/will_return_predictor_scan.py).

n = 8,844 per-(trial, organic position) records, 6,332 will-regress
vs 2,512 no-regress, 2,649 trials with complete fixation-pupil data.

**Multiple replacements survive bbox at p < 10⁻⁵:**

| metric | median wr | median nr | *p* | *d* | reading |
|---|---|---|---|---|---|
| **n_fix** | 5 | 4 | **3.3 × 10⁻¹⁶** | +0.134 | will-regress = more fixations on first-pass visit |
| **sum_fix_duration** | 1,070 ms | 957 ms | **7.6 × 10⁻⁸** | +0.093 | longer total dwell |
| **mean_fix_duration** | 222 ms | 231 ms | **2.6 × 10⁻⁷** | −0.106 | individual fixations shorter (faster scanning per fixation) |
| **first_pd** | 14.72 | 15.06 | **5.2 × 10⁻⁷** | −0.108 | lower pupil at entry |
| **pd_change_max** | 0.0244 | 0.0197 | **5.1 × 10⁻⁶** | +0.102 | **larger peak dilation events** during the visit |
| **pd_change_min** | −0.041 | −0.036 | **1.9 × 10⁻⁵** | −0.081 | **larger peak constriction events** during the visit |
| mean_pd_mean | 14.72 | 14.99 | 7.6 × 10⁻⁶ | −0.098 | lower mean pupil overall |
| LF/HF (existing) | 20.2 | 17.2 | 9.5 × 10⁻⁴ | +0.042 | baseline (the surviving leg of R1) |
| RIPA2 (existing) | 0.000414 | 0.000411 | **0.88** | +0.006 | baseline (the collapsed leg of R1) |
| pd_change_mean | −0.0082 | −0.0078 | **0.84** | +0.004 | **mean-based pupil change is null — same fate as RIPA2** |

**The pattern.** Mean-based per-fixation pupil metrics (RIPA2,
`pd_change_mean`, `mean_pd_mean` partly) all weaken or die under bbox
when the no-regress comparator group is no longer ad-inflated.
**Peak-based** per-fixation pupil metrics survive cleanly:
`pd_change_max` and `pd_change_min` both at *p* < 10⁻⁵. Will-regress
positions have *more variable* pupil dynamics during the visit —
bigger swings up and down — consistent with cognitive engagement that
includes both attention bursts (dilation peaks) and disengagement
breaks (constriction peaks).

The result is also consistent with a *baseline-shifted* engagement
story: will-regress positions are entered with lower pupil
(`first_pd` median 14.72 vs 15.06, *p* = 5.2 × 10⁻⁷), the user
fixates more often (n_fix 5 vs 4) for shorter durations each (222 vs
231 ms) but for longer total dwell (1,070 vs 957 ms), and the pupil
swings harder (peak ± dilation events). The original R1 "lingered
first time, processed shallowly" reading was per-fixation amplitude;
the bbox-clean version is per-fixation *excursion* rather than
amplitude.

**Replacement framing for the R1 paper.** "Lingered first time + more
pupillary excursion + lower baseline + more brief fixations." Three
per-fixation metric families coexist as bbox-clean predictors of
will-regress: LF/HF (sustained autonomic engagement),
`pd_change_max`/`pd_change_min` (peak per-fixation arousal events),
and `n_fix` / `mean_fix_duration` (visit-structure). The "shallow
processing" interpretation gets retired; the empirical claim moves to
"will-regress positions are visited more times, more briefly, with
lower baseline pupil and higher peak excursions." This is a cleaner
cognitive-engagement story than the joint LF/HF × RIPA2 mean-amplitude
dissociation, and every component survives the bbox cascade.

**Implication for the standalone RIPA2 publication track.** RIPA2
itself is unchanged as a method (peri-click TEPR p = 3.3 × 10⁻²¹
preserved; per-(trial,position) load gradient preserved). The
specific *will-regress per-fixation amplitude* claim does not
survive bbox; the standalone paper either drops that contrast or
notes it as an absolute-attribution boundary condition.

---

## §5 Decision checkpoint

The validation in §2.1 + §2.3 says **AR-strand survives bbox**. The
empirical collapses in §2.4 are mechanistically interpretable
(R1 RIPA2 = pooled-rank artifact; coupling-traces = AOI-size confound;
plateau ρ = small-N effect under bbox).

**Recommended next moves**, ordered by paper-strand priority:

1. **CIKM algorithmic prose pass** — propagate K-bbox-* values through
   `docs/findings.md` and `docs/drafts/cikm-2026/paper.md`. (Highest
   immediate value; deadline pressure.)
2. **ETTAC §3 prose update** — NB14 numbers + plateau reframe + drop
   joint LF/HF×RIPA2 dissociation claim. (May 15 deadline.)
3. **`compute_cursor_approach_features.py --attribution organic_hybrid`**
   — implement, run, validate per §4. (Unlocks ad-class extension and
   strengthens the methodology comparison.)
4. **NB28 calibration retrain** — multi-hour bootstrap, deferred until
   scheduling allows. (Gates CIKM §5 viewport-bands.)
5. **R1 paper reframe with Gwizdka** — the RIPA2 collapse is a real
   empirical finding worth a careful conversation, not a footnote.

The AR-strand answer to the validation question is yes. **Full steam
ahead, with three specific carve-outs above.**
