# Cursor Approach-Retreat as Covert Evaluation Signal

> **Refreshed 2026-04-12** to reflect the fixation-side coordinate-space audit (symmetric to the 2026-04-09 cursor-side audit). Pre-2026-04-09 numbers were contaminated by a scroll double-count on cursor Y; pre-2026-04-12 numbers carried a similar double-count on gaze (FPOGY). The canonical post-fix values live in `docs/notebook-key-claims.md` §NB21/§NB22. Headline direction preserved through both audits; magnitudes **strengthened** in the second audit. Key shifts from the 2026-04-12 fix: M3 LOSO AUC **0.792 → 0.859**, clicked N **2,214 → 2,228**, Deferred N **1,178 → 1,916**, Evaluated-rejected N **278 → 439**, retreat-distance dissociation *p* **1.9 × 10⁻¹¹ → 1.76 × 10⁻³⁸**. See `CHANGELOG.md` and `docs/drafts/coord_fix_snapshot_20260412/` for before/after.

## The finding

During SERP evaluation, the mouse cursor makes partial approach movements toward results that are ultimately rejected. This is not idle hovering — it's a covert evaluation signal with a distinctive motor signature, cognitive load confirmation, and predictive power.

### Key numbers (notebook 15, N = 2,340 trials)

- **17.5%** of fixated results had the cursor approach within 100px and then withdraw without a click (**2,355 / 13,419** post-fix)
- **Universal:** 100% of participants (47/47) show it. 55% of trials have at least one instance.
- **Cognitively loaded:** Pupil LF/HF is **22.7** (close, <100px) vs **18.0** (far, >300px), *p* = **6.99 × 10⁻⁵**. These are genuine evaluation episodes.
- **Distinctive motor signature:** Retreat distance for approached-rejected results is **208 px** vs **75.5 px** for clicked results (*p* = **1.15 × 10⁻¹³¹**). The cursor approaches, the user evaluates, then actively withdraws.
- **Predictive:** Position + dwell + approach features → **AUC 0.859 ± 0.044 (LOSO M3)** vs position-only **0.613**. Cursor-only signal, no eye tracker needed.

### The consideration set

Approach-retreat reveals a hidden class that click models can't see:

| Class | What it means | Current click model treatment |
|-------|-------------|------------------------------|
| **Clicked** | Selected | Positive signal |
| **Approached-rejected** | Evaluated, found wanting | Collapsed into "non-click" |
| **Never approached** | Unseen or dismissed without evaluation | Collapsed into "non-click" |

Feed-forward models collapse the last two into one class. Approach-retreat splits them — and the split is deployable from standard mouse telemetry.

### Retreat distance predicts click outcome

Four-class taxonomy (NB22, regression-based split, post coordinate-space audit 2026-04-12):

| Category | N | % | Retreat (px) | Gaze Dwell (ms) | Prox Dwell (ms) |
|----------|---|---|---|---|---|
| **Clicked** | 2,228 | 16.6% | — | — | — |
| **Deferred** (approached + regressed) | 1,916 | 14.3% | 234.5 | 4,137 | 1,212.5 |
| **Evaluated-rejected** (approached, no regression) | 439 | 3.3% | 90.8 | 1,612 | 690.0 |
| **Not approached** | 8,836 | 65.8% | — | — | — |

Deferred vs rejected motor separation: **2.6× retreat distance (234.5 vs 90.8 px, *p* = 1.76 × 10⁻³⁸)**, **2.6× gaze dwell (*p* = 9.76 × 10⁻⁷⁰)**, **1.8× proximity dwell (*p* = 1.36 × 10⁻¹⁶)**. Source: NB22:K5–K7. All three separations strengthened dramatically after the 2026-04-12 fixation-side fix (retreat-distance *p* went from 10⁻¹¹ → 10⁻³⁸, gaze-dwell *p* from 10⁻²⁶ → 10⁻⁷⁰).

**Methodology note:** The regression-based split (NB22) uses scroll regression as the deferred/rejected criterion. The classifier-derived split (NB21:K13–K16) uses the LOSO M3 predicted probability at Youden's J threshold (*p* = 0.493) and yields 1,381 deferred / 974 evaluated-rejected. Both approaches are available; the classifier-derived version is the paper's canonical taxonomy (§4.3).

### Approach + regression = the return-to-click pathway

Cursor approach predicts scroll regression (odds ratio **3.21×**, χ² = 661.1, *p* = 8.72 × 10⁻¹⁴⁶):

| Pathway | N | Click Rate |
|---------|---|-----------|
| **Approach + regression** | 3,087 | 37.9% |
| **Approach + no regression** | 696 | 36.9% |
| **No approach + regression** | 5,589 | 8.1% |
| **No approach + no regression** | 4,047 | 8.6% |

**Short retreat + regression = future return to click.** The cursor lingered, the user scrolled away to compare, then came back. 78.3% of approached results get regressed to.

**Long retreat + no regression = hard negative.** The user evaluated, rejected, and moved on. The 70.5% non-click rate in the "approach + no regression" pathway is the clearest hard-negative signal available from cursor data. The regression is the behavioral commitment to re-evaluate — without it, approach-then-retreat is a rejection.

## Cost structures by element type

Azzopardi, Thomas & Craswell (SIGIR 2018) formalized per-element cost within the C/W/L framework: ads cost less to evaluate than organic results, answer boxes cost less than both. Their model predicts that approach-retreat behavior should differ by element type — if evaluation cost varies, so should the motor signature of evaluation.

### Hypothesis: approach-retreat differs by SERP element type

AdSERP has ad boundary data (`ad-boundary-data/*.json`) with three element types:
- `native_ad`: Sponsored results embedded in organic listings
- `dd_top`: Top-of-page ad block
- `dd_right`: Right-side panel (Knowledge Panel, Shopping sidebar)

**Predicted cost ordering** (from Azzopardi's framework):
- **Right panel** (visual, image-heavy): Lowest evaluation cost
- **Top ads** (text, familiar format): Medium cost
- **Organic results** (text, novel content): Highest evaluation cost

### Notebook 16 results: Evaluation cost by element type

| Element | Med. Duration | Med. Saccade | Pupil %chg | N fixations |
|---------|--------------|-------------|-----------|------------|
| **Organic** | 193ms | 61px | −0.25% | 162,479 |
| **Native Ad** | 181ms | 71px | −0.08% | 13,249 |
| **Top Ad Block** | 187ms | 74px | **+0.41%** | 33,329 |
| **Right Panel** | 201ms | 71px | +0.11% | 11,424 |

**Azzopardi's prediction partially holds, partially overturned:**

- Organic results have the **tightest saccades** (61px) — most within-result text processing. Confirms highest reading cost.
- Native ads have the **shortest duration** (181ms) — quickest to dismiss. Confirms low evaluation cost for familiar ad format.
- **Top ads show the HIGHEST pupil dilation** (+0.41%) — the opposite of the predicted ordering. Users work harder evaluating top ads than organic results. Possible explanation: discrimination cost ("is this what I want or an ad trying to sell me something else?") adds cognitive load that pure text similarity doesn't capture.
- Right panel has the **longest duration** (201ms) — visual/image content takes time to process even though pupil load is moderate.

### Survey phase oversamples top ads

| Element | Survey % | Evaluate % |
|---------|---------|-----------|
| Organic | 48.1% | 73.7% |
| Top Ad Block | 39.2% | 15.1% |
| Native Ad | 9.3% | 6.0% |
| Right Panel | 3.4% | 5.2% |

Top ads capture 39% of survey fixations but only 15% of evaluate fixations — the survey phase oversamples them 2.6×. This may reflect their visual prominence in the first viewport, or it may indicate that the survey is doing ad-vs-organic discrimination as part of its gist sampling.

### Approach-retreat by element type (notebook 20)

Items 1–4 below are now tested. All four confirm the discrimination cost hypothesis.

| Metric | Organic | Top Ad | Native Ad | p (Org vs Top) |
|--------|---------|--------|-----------|----------------|
| Approach rate | 21.0% | **42.9%** | 17.5% | 10⁻⁹² |
| Retreat distance (rejected) | 228 px | **279 px** | 281 px | 7×10⁻⁸ |
| Dwell in proximity (clicked) | 2,023 ms | **4,586 ms** | 2,001 ms | 3×10⁻¹³ |
| Direction changes | 1.6 | **2.7** | 1.7 | — |
| Min distance (clicked) | 170 px | **56 px** | 307 px | — |

Position-controlled (organic vs top-ad at positions 0–2): retreat 232 vs 279 px (p = 2×10⁻⁵), dwell 1,634 vs 2,525 ms (p = 2×10⁻⁷). Effects survive.

**Azzopardi's prediction is overturned for top ads.** The C/W/L framework predicted ads cost LESS to evaluate. Top ads cost MORE — by every metric: pupil dilation (notebook 16), cursor dwell, retreat distance, and hesitation. The cost is discrimination ("is this what I want or an ad?"), not reading difficulty.

**Native ads show avoidance**, not evaluation: lowest approach rate, largest cursor distance, lowest click rate. Users don't evaluate them — they keep the cursor away.

### Remaining to test
1. ~~Approach rate by element type (controlling for position)~~ Done — notebook 20
2. ~~Retreat distance by element type (approached-rejected only)~~ Done
3. ~~Dwell-in-proximity by element type during approach~~ Done
4. ~~Approach-to-click conversion rate by element type~~ Done
5. Rosenholtz Feature Congestion scores by element type (requires rendering all 2,776 SERPs)

### Why this matters

The cost structure prediction is **partially validated, partially overturned** — and the surprise is the interesting part. Azzopardi's framework correctly predicts native ad behavior (low cost, fast dismissal) but wrong for top ads (high cost from discrimination burden). The approach-retreat signal must be calibrated by element type in production: a cursor approach to a top ad means deliberation, while an approach to an organic result is more likely commitment.

## Optimizer vs satisficer approach profiles

From notebook 15:
- **Optimizers** (high regression rate): 7.5% almost-clicked rate, mean retreat 152px, dwell-in-proximity 555ms
- **Satisficers** (low regression rate): 5.3% almost-clicked rate, mean retreat 131px, dwell-in-proximity 428ms

Optimizers approach more results and spend longer evaluating them before retreating. Their consideration sets are larger. This maps directly onto Pirolli & Card's patch exhaustion model — optimizers exhaust the patch more thoroughly, and the approach-retreat signal captures the exhaustion process.

## Position effects

| Position | N | Click Rate | Almost-Clicked | Mean Min Distance | Mean Retreat |
|----------|---|-----------|----------------|-------------------|-------------|
| 0 | 2,310 | 21.0% | 15.8% | 174px | 252px |
| 1 | 2,208 | 15.0% | 9.2% | 228px | 170px |
| 2 | 1,999 | 15.7% | 7.2% | 264px | 145px |
| 3 | 1,793 | 15.9% | 5.9% | 283px | 134px |
| 4 | 1,620 | 11.5% | 6.4% | 284px | 138px |
| 5 | 1,426 | 8.1% | 5.6% | 314px | 131px |
| 6 | 1,201 | 6.0% | 3.2% | 387px | 133px |
| 7 | 988 | 5.5% | 2.2% | 511px | 120px |
| 8 | 814 | 4.2% | 0.9% | 646px | 99px |
| 9 | 661 | 6.8% | 0.3% | 779px | 87px |

Position 0 has the highest almost-clicked rate (15.8%) and shortest cursor distance (174px) — consistent with the survey phase depositing the cursor near the top result before committed evaluation begins. After controlling for orient-phase confound (fixations 1-5 vs 6+), the approach signal remains. Almost-clicked rate drops ~50× from position 0 to 9. Mean cursor distance grows monotonically (174→779px), confirming users hold the cursor progressively farther from lower-ranked results. Retreat distance stabilizes around 130–145px for positions 2–6, then drops below 100px at the SERP bottom where evaluation episodes are rare.

## Connection to the F-pattern decomposition

The approach-retreat signal is invisible in aggregate heatmaps — it's a temporal motor behavior that requires per-fixation cursor tracking. Just as the F-pattern's horizontal bars and vertical stem are two overlaid operations, the non-click class is two overlaid populations (evaluated-rejected vs never-evaluated). Both are examples of temporal structure that aggregate spatial analysis collapses.

## Scroll retreat: the transportation vs evaluation split (notebook 17)

On desktop, scroll kinematics during regression do NOT discriminate click targets:
- Scroll velocity doesn't decelerate near the click target (ρ = −0.013, n.s.)
- Scroll dwell: 167ms for both clicked and non-clicked results (p = 0.31)
- Scroll pause duration: 440ms for both (p = 0.46)

3,617 scroll approach-retreat episodes exist (regression → pause → resume forward) but the pattern doesn't predict click outcome. **The scroll is ballistic transportation; the cursor is the evaluation probe.** On desktop, the two motor channels specialize.

**Mobile prediction:** On touch devices where scroll is the only motor channel, scroll dwell and deceleration SHOULD discriminate click targets — because there's no cursor to absorb the evaluation function. The desktop null result is specific to a two-channel motor system. A mobile eye-tracking dataset would test this directly.

## Open questions

- [x] **Element-type approach signatures:** Done — notebook 20. Top ads 2× approach rate, 50px more retreat, 2.3× longer dwell. Azzopardi's cost framework overturned for top ads. See §"Approach-retreat by element type" above.
- [x] **Scroll × cursor cross-reference:** Done — notebook 17. Null result on desktop: scroll kinematics don't discriminate click targets (all p > 0.3). Scroll is ballistic transportation; cursor is the evaluation probe.
- [ ] **Mobile scroll evaluation:** Test the prediction that touch scroll dwell discriminates click targets on mobile datasets (no cursor available). RecGaze dataset is the best candidate.
- [ ] **Cross-dataset generalizability:** AdSERP is transactional product search with forced choice. Does approach-retreat appear in informational queries? In naturalistic search?
- [~] **Temporal dynamics:** Notebook 18 (learning curve) addresses across-trial dynamics. Within-trial approach velocity change still open — framework compilation predicts later approaches should be *faster* (criteria already compiled), not slower.
- [ ] **Rosenholtz Feature Congestion:** Score visual clutter by element type — does congestion predict approach-retreat rate? Requires rendering all 2,776 SERPs.
- [ ] **Regression click model:** Fit a logistic regression (or gradient-boosted tree) predicting click from approach features alone: retreat distance, min distance, dwell in proximity, direction changes, approach velocity. This replaces the current post-hoc category split (which makes the 0% click rate tautological) with a learned threshold — producing an ROC curve and optimal operating point for approach-retreat severity. Compare against the position+dwell AUC baseline (0.613 → 0.859 with approach features). Element-type calibration needed (§"Cost structures").

## Notebooks

- [15_cursor_approach.ipynb](../notebooks-v2/15_cursor_approach.ipynb) — Core analysis
- [13_survey_phase.ipynb](../notebooks-v2/13_survey_phase.ipynb) — OSEC phase model, survey fixation targets
- [05_lhipa.ipynb](../notebooks-v2/05_lhipa.ipynb) — Pupillometric validation
