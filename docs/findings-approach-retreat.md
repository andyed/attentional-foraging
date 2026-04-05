# Cursor Approach-Retreat as Covert Evaluation Signal

## The finding

During SERP evaluation, the mouse cursor makes partial approach movements toward results that are ultimately rejected. This is not idle hovering — it's a covert evaluation signal with a distinctive motor signature, cognitive load confirmation, and predictive power.

### Key numbers (notebook 15, N = 2,340 trials)

- **14.8%** of fixated results had the cursor approach within 100px and then withdraw without a click
- **Universal:** 100% of participants (47/47) show it. 55% of trials have at least one instance.
- **Cognitively loaded:** Pupil LF/HF is 23.8 (close) vs 17.2 (far), p = 4.9×10⁻¹². These are genuine evaluation episodes.
- **Distinctive motor signature:** Retreat distance for rejected results is 244px vs 119px for clicked results (p = 5.3×10⁻⁹²). The cursor approaches, the user evaluates, then actively withdraws.
- **Predictive:** Position + dwell + approach features → AUC 0.823 vs position-only 0.618. Cursor-only signal, no eye tracker needed.

### The consideration set

Approach-retreat reveals a hidden class that click models can't see:

| Class | What it means | Current click model treatment |
|-------|-------------|------------------------------|
| **Clicked** | Selected | Positive signal |
| **Approached-rejected** | Evaluated, found wanting | Collapsed into "non-click" |
| **Never approached** | Unseen or dismissed without evaluation | Collapsed into "non-click" |

Feed-forward models collapse the last two into one class. Approach-retreat splits them — and the split is deployable from standard mouse telemetry.

### Retreat distance predicts click outcome

| Category | N | Retreat | Min Dist | Dwell in Proximity | Click Rate |
|----------|---|---------|----------|--------------------|-----------|
| **Clicked** | 1,981 | 119px | 167px | 2,360ms | 100% |
| **Approached-rejected** | 2,280 | 244px | 59px | 1,653ms | 0% |
| **Peripherally seen** | 4,548 | 180px | 191px | 592ms | — |
| **Unseen** | 6,588 | — | — | — | — |

Short retreat (119px) = the cursor stayed close and committed. Long retreat (244px) = the cursor actively withdrew. The difference is p = 5.3×10⁻⁹².

### Approach + regression = the return-to-click pathway

Cursor approach predicts scroll regression (odds ratio 3.67×, p = 10⁻¹⁹⁹):

| Pathway | N | Click Rate |
|---------|---|-----------|
| **Approach + regression** | 2,745 | 36.5% |
| **Approach + no regression** | 762 | 29.5% |
| **No approach + regression** | 5,892 | 6.6% |
| **No approach + no regression** | 5,998 | 6.1% |

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

### Remaining to test
1. Approach rate by element type (controlling for position)
2. Retreat distance by element type (approached-rejected only)
3. Dwell-in-proximity by element type during approach
4. Approach-to-click conversion rate by element type
5. Rosenholtz Feature Congestion scores by element type (requires rendering all 2,776 SERPs)

### Why this matters

If the cost structure prediction holds, it validates Azzopardi's theoretical framework with behavioral evidence — and it means the approach-retreat signal should be calibrated by element type in production. A cursor approach to an ad means something different than an approach to an organic result, because the evaluation cost is different.

This also connects to the OSEC model: the survey phase samples across element types (93% of survey fixations land on organic results or ads, only 3.4% on right panel), but the evaluate phase should show element-type-dependent approach signatures because that's where the cost differences manifest.

## Optimizer vs satisficer approach profiles

From notebook 15:
- **Optimizers** (high regression rate): 7.5% almost-clicked rate, mean retreat 152px, dwell-in-proximity 555ms
- **Satisficers** (low regression rate): 5.3% almost-clicked rate, mean retreat 131px, dwell-in-proximity 428ms

Optimizers approach more results and spend longer evaluating them before retreating. Their consideration sets are larger. This maps directly onto Pirolli & Card's patch exhaustion model — optimizers exhaust the patch more thoroughly, and the approach-retreat signal captures the exhaustion process.

## Position effects

| Position | Click Rate | Almost-Clicked | Mean Min Distance | Mean Retreat |
|----------|-----------|----------------|-------------------|-------------|
| 0 | 21.0% | 15.8% | 174px | 252px |
| 1 | 15.0% | 9.2% | — | — |
| 3 | — | — | — | — |

Position 0 has the highest almost-clicked rate (15.8%) — consistent with the survey phase depositing the cursor near the top result before committed evaluation begins. After controlling for orient-phase confound (fixations 1-5 vs 6+), the approach signal remains.

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

- [ ] **Element-type approach signatures:** Run notebook 15 split by ad boundary data. Do approach-retreat profiles differ by element type?
- [ ] **Scroll × cursor cross-reference:** For trials where both signals exist, does scroll retreat co-occur with cursor approach-retreat at the same result?
- [ ] **Mobile scroll evaluation:** Test the prediction that touch scroll dwell discriminates click targets on mobile datasets (no cursor available).
- [ ] **Cross-dataset generalizability:** AdSERP is transactional product search with forced choice. Does approach-retreat appear in informational queries? In naturalistic search?
- [ ] **Temporal dynamics:** Does approach velocity change during the trial? If working memory fills, later episodes should show longer evaluation.
- [ ] **Rosenholtz Feature Congestion:** Score visual clutter by element type — does congestion predict approach-retreat rate?

## Notebooks

- [15_cursor_approach.ipynb](../notebooks-v2/15_cursor_approach.ipynb) — Core analysis
- [13_survey_phase.ipynb](../notebooks-v2/13_survey_phase.ipynb) — OSEC phase model, survey fixation targets
- [05_lhipa.ipynb](../notebooks-v2/05_lhipa.ipynb) — Pupillometric validation
