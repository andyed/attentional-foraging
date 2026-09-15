# Findings — the four states of result evaluation

**Regime:** `[LAB, AdSERP, typed]` throughout. **Kernel:** wherever peripheral intake is involved, the primary definition is intake within 200 px (≈ 5°) of the result (the published PAI alpha gated at 200 px); the published kernel ungated and a boundary-distance cortical-magnification falloff are reported beside it, because the share depends on the reach and the published kernel is flat on SERP bands (§1). **Substrate:** cursor-only typed buf500 mousedown cache, hash-checked; NB22 gaze-regression labels; fixations assigned by the label producer's own rule; AllSERP v1.1.1 typed maps. **Status:** every number below comes from a gated producer sidecar under `scripts/output/` and its ablation note; none has a Key Claims row yet (NB37/NB38 pending). Cite the note, not this page, until then.

Companion pages: [`findings.md`](findings.md) (the full narrative, older numbering kept), [`foraging-constructs.md`](foraging-constructs.md) (construct → observable map), [`foraging-refresh-plan-2026-09-14.md`](foraging-refresh-plan-2026-09-14.md).

---

## Read this first — what this page is, and whose work it stands on

This page is the working summary behind a proposed CHIIR 2027 paper and is
written to be read by its intended coauthors. Two bodies of prior work carry
it, and the page tries to be exact about which is which.

**The theory is Leif Azzopardi's.** The C/W/L framework describes a searcher
by a continuation function C(i), the probability of proceeding past result i
having viewed it, and every metric built on it is expected gain under that
function; the SIGIR 2018 information-foraging instance (Azzopardi, Thomas &
Craswell) gives each SERP element its own examination cost and derives
stopping from the marginal value theorem. Both leave "viewed" and "cost" to
the metric designer. What this corpus adds is measurement: C(i) comes out
five ways at once (viewport, periphery, any fixation, first-pass fixation,
cursor) and they diverge with depth; the per-element cost model comes out as
four tiers with the cheapest at zero fixations. The theory is not revised
here. It is instrumented.

**The instrument is Andrew Duchowski's.** The Peripheral Attention Index
(Duchowski, Gehrer & Svaldi, ETTAC 2026) is the graded-membership construct
on the gaze side: a fixation contributes to every area of interest by a
distance-based weight, not only to the one it lands in. It is what makes a
result that was on screen, never fixated, and still taken in, measurable at
all. On this corpus it also turned up a method question worth bringing back
to its authors: on wide, short SERP result bands the published Eq. 2 weight
is nearly flat in eccentricity (§1 below), so the numbers here are reported
under the published kernel *and* under a boundary-distance kernel with a
cortical-magnification falloff, offered as a proposal rather than a
correction. That extension is the joint-work item the earlier track notes
called Q1.

**What this page does not contain.** Nothing from Sara Allawati's AO-SERP
corpus or her abandonment results (the design differences between the two
corpora, and which results here should be expected to move across them, are
in [`methodology/adserp-vs-ao-corpus-differences.md`](methodology/adserp-vs-ao-corpus-differences.md)); no PAI number computed before the
2026-09-04 lineage audit; no fitted gain curve or give-up threshold, so the
language stays "depletion-state prediction" rather than "MVT". Every number
comes from a producer under `scripts/` that reproduces a shipped value
before computing a new one, with the sidecar under `scripts/output/`.

---

## The states

Once a result is on screen, its evaluation ends in one of four states. Each is witnessed by a different channel, and each costs the searcher a different amount.

| state | definition | witnessed by | slots | share of 34,317 | median gaze dwell | median cursor dwell | visits |
|---|---|---|---|---|---|---|---|
| **peripheral** | on screen ≥ 500 ms, never fixated, intake within 200 px (≈ 5°) at or above the fixated median for its type | PAI | 618 | 1.8 % | 0 ms | 0 ms | 0 |
| **rejected** | fixated, not clicked, the gaze never returned | gaze | 6,077 | 17.7 % | 541 ms | 0 ms | 1 |
| **deferred** | fixated, not clicked, the gaze came back | gaze; readable from the cursor | 9,797 | 28.6 % | 1,695 ms | 384 ms | 4 |
| **clicked** | the harvested result | cursor, click | 2,607 | 7.6 % | 4,052 ms | 1,617 ms | 5 |

Two pre-evaluation conditions complete the census: **never on screen** (8,279 slots, 24.1 %) and **brief on screen** under 500 ms (714, 2.1 %). A further 1,847 slots (5.4 %) were on screen, never fixated and below the peripheral threshold (*unsampled*), and 4,378 (12.8 %) sit in trials without a usable scroll stream, where opportunity is unknown. The fixated and clicked rows do not depend on any kernel; the peripheral / unsampled split does, and §1 gives it as a ladder.

Sources: [`ablations/engagement_state_census.md`](ablations/engagement_state_census.md) (census, thresholds, transitions), [`ablations/engagement_continuation.md`](ablations/engagement_continuation.md) §(b) (cost tiers). Producers: [`scripts/engagement_state_census.py`](../scripts/engagement_state_census.py), [`scripts/engagement_continuation.py`](../scripts/engagement_continuation.py). Lineage: the deferred / rejected split is NB22's `gaze_regression_label` ([`22_four_class_taxonomy.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/22_four_class_taxonomy.ipynb)); the PAI construct on this corpus was first censused in [`35_pai_census.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/35_pai_census.ipynb) (pre-fix substrate, orphan-fixation recovery).

---

## 1. Peripheral — a quarter to a third of on-screen skips are sampled at read level, and the periphery is thin on the rest

**The method finding first.** The published PAI kernel (Eq. 2) was designed for compact polygons. On SERP result bands, 540 px wide and about 80 px tall, its vertex distance and area weight remove the eccentricity dependence: across 638,963 fixation-band pairs the alpha has Spearman −0.08 with boundary distance, sits at 0.46 within 50 px and 0.40 beyond 1,600 px, and is 0 for 6.8 % of adjacent pairs because the vertex distance exceeds the centroid distance below the middle of a wide band. Under that kernel "peripheral intake on this result" is a page-wide fixation-duration count weighted by band size; the mass-weighted median intake distance on never-fixated results was 933 px. The first draft of this page quoted 73 % from it. Source: [`ablations/engagement_state_census.md`](ablations/engagement_state_census.md) §Read-this-first; kernels in [`scripts/peripheral_kernel.py`](../scripts/peripheral_kernel.py).

**The share, as a function of reach.** Of the 2,465 results that were on screen for at least half a second and never fixated, the share receiving as much intake per second of unfixated screen time as the results the searcher went on to read is:

| definition | share | participant median [IQR] |
|---|---|---|
| intake within 200 px (≈ 5°) (**primary**) | **25 %** | 0.27 [0.20, 0.37] |
| within 400 px (≈ 9°) | 34 % | 0.38 [0.26, 0.52] |
| soft cortical-magnification falloff, 1/(1 + E/2°) | 44 % | 0.53 [0.38, 0.60] |
| published kernel, ungated | 73 % | 0.79 [0.69, 0.85] |

At matched type and page position, a skipped result receives *less* near-peripheral intake per unfixated second than a read result (AUC 0.33 within 200 px (≈ 5°), 0.46 under the soft falloff). The eyes get close to what they read; the periphery is thin on what they skip. The flat kernel had said the opposite (0.60).

- **What stands.** A peripheral tier exists: a quarter of on-screen skips, a third under a wider reach, received near-peripheral intake at the level of read results. The participant *ordering* is stable across kernels and is the individual-differences lead; the *level* is kernel-defined and should never be quoted without its reach.
- **What it is, mechanically.** Typed bands are contiguous, so near-peripheral intake on a result is mostly parafoveal preview from fixations on the results beside it. It is not the margin-fixation preview NB19 tested and found null ([`19_margin_fixations.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/19_margin_fixations.ipynb)): that asked whether fixations *between* results carry preview; this measures intake on a result from fixations on its neighbours.
- **What the periphery can carry.** Crowding, not acuity, is the limit: at three to six degrees the critical spacing is one and a half to three degrees and title letters are spaced about 10 px, an order of magnitude inside it. Letter identity is gone for titles and snippets alike; colour, weight, line length, numerals and bold query-term density survive. A semantic relevance test was therefore never well targeted, and the coarse cues already in the content features (query-term overlap in the title, numerals, price presence, title length) are null by state. Bold query-term density, parsed from the `<em>` markup in all 2,776 snapshots, is null on every contrast too, for a corpus reason: on transactional queries Google bolds something in 92 % of snippets and the share is a tenth of the snippet in every state, so the cue has no variance between the results on a page. The peripheral tier is a fact about **sampling**, not about **evaluation**. Sources: [`ablations/engagement_continuation.md`](ablations/engagement_continuation.md) §(d); [`null-findings/2026-09-14-bold-term-density-null.md`](null-findings/2026-09-14-bold-term-density-null.md); producer [`scripts/bold_term_density.py`](../scripts/bold_term_density.py).
- **For the cursor work.** The 663 "approached but never fixated" rows the CHIIR carve excludes split 168 peripherally sampled / 374 unsampled / 48 brief / 8 never on screen / 62 unknown under the primary. The construct boundary is right; about a third of those rows were taken in at read level and passed by with the cursor.

**Not established:** that the periphery *evaluates*, and any single share without its reach.

**What the periphery does, then.** Two tests of a role other than evaluation ([`ablations/periphery_navigates.md`](ablations/periphery_navigates.md); producer [`scripts/periphery_navigates.py`](../scripts/periphery_navigates.py)):

- *Is skipping a layout decision?* Among 16,145 on-screen non-clicked slots, position plus block height plus element type predicts fixation at 0.713 against 0.696 for position alone, with an interval that includes zero; content adds nothing over layout (0.651 → 0.651). Skipping is reading order and time on screen, not format and not content.
- *Does the survey leave a map?* Intake during the first five fixations on slots not yet fixated predicts later fixation at 0.747 within trial; the top-intake candidate is fixated later in 96 % of trials, the bottom one in 49 %. Plain gaze distance during the survey does exactly as well (0.748), and intake adds +0.001 over it. The map is proximity, and within 200 px (≈ 5°) it covers five neighbourhoods, not the page (87 % of candidates receive no survey intake).

One more signature, from the fixation *before* a jump ([`ablations/major_saccade_selection.md`](ablations/major_saccade_selection.md)): major saccades follow shorter fixations, 154 ms before jumps over 600 px against 200 ms before minor ones, in 35 of 43 participants, the ambient-mode timing of layout-driven scanning; and far jumps land on a result the eyes were near in the last second twice as often as chance, though never more often than plain recency-proximity predicts, so the kernel adds nothing there either. Landing precision is flat across amplitude and prior intake does not improve it.

Put with the return result below, the periphery's measurable job on a results page is local next-fixation guidance, the reading-science role. It does not evaluate content, it does not steer on format beyond reading order, and it does not guide returns. Search on a SERP is foveal and serial, with the survey seeding a small proximity map and memory carrying the between-patch return. That is a smaller role than the pre-attentive-scan intuition assigns the periphery, and it is the one the data support.

**What the corpus says back to PAI.** A kernel is a claim about what a fixation delivers to a result it does not land on, and later fixation tests the claim without a content model ([`ablations/pai_kernel_validation.md`](ablations/pai_kernel_validation.md); producer [`scripts/pai_kernel_validation.py`](../scripts/pai_kernel_validation.py)). The published Eq. 2, ungated, predicts later fixation at 0.520 and adds −0.001 to position; its +0.009 over position and distance is the area weight, a layout term. Every eccentricity-aware kernel, a hyperbolic falloff at 1°, 2° or 4°, a hard gate at 100 or 200 px, or duration-within-reach with no alpha at all, scores 0.745–0.748 and adds +0.001 over gaze distance. On this layout the falloff shape is unidentifiable, and a kernel's value is units and interpretability rather than information. Two concrete suggestions for the authors follow from the corpus: boundary distance instead of vertex distance on wide AOIs, and the area weight outside the distance ratio. The shape question is answerable on the compact, well-separated AOIs PAI was designed for, which is an experiment the authors are better placed to run.

## 2. Rejected — one visit, half a second, and the cursor stays away

A rejected result gets a single gaze visit of about 541 ms and, at the median, no cursor proximity dwell at all; 41 % of rejected results are approached within 100 px. In display order, a rejected result is followed by another rejection 36 % of the time, by a deferred result 22 %, by a peripheral skip 16 %, and by the click 3 %.

The relevance gradient across the fixated tiers is small on the embedding proxy: rejected < deferred on title cosine (AUC 0.48, p 0.002), deferred < clicked (0.48, p 0.009). Source: census transitions table; continuation note §(d). Cursor-side characterisation of the evaluated-rejected class (approach geometry, retreat) is in [`15_cursor_approach.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/15_cursor_approach.ipynb) and [`20_approach_by_element.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/20_approach_by_element.ipynb).

---

## 3. Deferred — the gaze comes back, and the return is memory-guided

Deferred is the largest evaluative state (28.6 % of slots) and the one clicks cannot represent. Three findings, all 2026-09-14 on the post-fix substrate:

**The return is executed from memory, not from the periphery.** On 9,347 return events, long returns (≥ 2 ranks, 30 % of returns; n 1,774) land at first-entry precision (39.5 vs 38.0 px, CI on the difference [0, +3]) from 2.4× the saccade amplitude (429 vs 179 px) with *half* the peripheral intake on the target in the preceding second that a first entry gets (78 vs 148 mass/s under the eccentricity-aware kernel, CI [−75, −50]), and landing precision does not covary with that intake at all (ρ −0.001). Short one-rank returns (70 %) are 7 px less precise than entries and are the reading step back, a different act. Consistent with NB12's null on load and landing precision ([`12_regression_precision_by_load.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/12_regression_precision_by_load.ipynb)). Source: [`ablations/return_is_memory.md`](ablations/return_is_memory.md); producer [`scripts/return_is_memory.py`](../scripts/return_is_memory.py).

**Peripheral intake carries nothing about the deferred split that the cursor does not.** On the CHIIR carve's own 9,269 deferred-vs-rejected rows, peripheral intake in the second after the eyes leave a result adds −0.000 AUC [−0.001, +0.000] to the seven-feature cursor vector under an eccentricity-aware kernel; deferred results receive slightly more of it than rejected ones, which is proximity. Under the published PAI kernel the same probe read +0.010 with the opposite sign, and that was page-wide fixation duration, not intake on the target. A first run showing +0.022 was window-length leakage; both artefact rows are kept in the note. Source: [`ablations/pai_deferred_probe.md`](ablations/pai_deferred_probe.md); producer [`scripts/pai_deferred_probe.py`](../scripts/pai_deferred_probe.py).

**Gaze dwell reads the label back.** Total gaze dwell scores 0.807 on the deferred split but 73 % of a deferred result's dwell arrives after the return; first-visit dwell scores 0.514 against a permutation null of 0.511. The cursor vector scores 0.680 on the same 9,269 rows with mean distance alone at 0.665. Source: [`methodology/deferred-dwell-carve.md`](methodology/deferred-dwell-carve.md), `scripts/output/deferred_dwell_carve/summary_labeled_only.json`. The scroll-channel analogue and its pooled-only artefact are in [`36_scroll_vs_cursor_deferred.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/36_scroll_vs_cursor_deferred.ipynb).

Deferred runs cluster: a deferred result is followed by another deferred result 52 % of the time and by the click 19 %.

---

## 4. Clicked — the costliest tier, and the one the cursor owns

The harvested result carries about 4 s of gaze across 5 visits and 1.6 s of cursor proximity dwell; 94 % are approached. Seven approach-geometry features on the press-anchored, 500 ms-buffered cursor stream predict it at 0.935 pooled LOSO AUC on 2,608 trials, position adds nothing once they are in the model (paired Δ 0.0000), and the 500 ms buffer costs 0.015. Source: `scripts/output/m4_cursor_aoi_mousedown/summary.json`, producer `scripts/m4_cursor_aoi_rerun.py`; history in [`21_click_prediction.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/21_click_prediction.ipynb) (the notebook's own numbers predate the cursor-only rerun; read [`methodology/feature-extractor-lineage.md`](methodology/feature-extractor-lineage.md) first).

Motor engagement is graded by outcome, not merely correlated with it: 187 vs 88 ms cursor dwell on harvested vs never-chosen results, duration-matched (`scripts/output/exploitation_vs_travel/summary.json`).

---

## 5. Continuation, four ways

C/W/L describes a searcher by one continuation function C(i). This corpus measures "viewed" five ways on the 2,151 trials where viewport opportunity is known for every slot:

| reach at result 10 | viewport | periphery (within 200 px (≈ 5°)) | fixation (any time) | fixation (first pass) | cursor |
|---|---|---|---|---|---|
| | 49 % | 38 % | 36 % | 30 % | 18 % |

Under the soft falloff the periphery column reads 41 %; under the flat published kernel 45 %. The other four columns do not depend on the kernel.

The first-pass curve is the only one that declines smoothly (C from 0.84 to 0.60); every any-time curve flattens at depth because returns refill the deeper slots. A metric that picks one column picks a user model. Source: [`ablations/engagement_continuation.md`](ablations/engagement_continuation.md) §(a). Phase structure (survey shows up as 9 % of trials fixating a deeper result before the first) is [`13_survey_phase.ipynb`](https://github.com/andyed/attentional-foraging/blob/main/notebooks-v2/13_survey_phase.ipynb).

---

## What is not in this page

- Anything from Sara Allawati's AO-SERP corpus, or the H01 PAI-by-abandonment result: hers.
- Any PAI number computed before the 2026-09-04 lineage audit (`ablations/pai_exposure_validation.md`, `pai_preentry_probe.json`): retired rows, re-derivation pending.
- The depletion-state predictor quoted in the CHIIR framing note: no producer in this repo yet.
- A gain curve or give-up threshold: not fitted anywhere; the language stays "depletion-state prediction", never "MVT".
