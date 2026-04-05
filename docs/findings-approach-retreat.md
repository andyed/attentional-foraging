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

## Cost structures by element type

Azzopardi, Thomas & Craswell (SIGIR 2018) formalized per-element cost within the C/W/L framework: ads cost less to evaluate than organic results, answer boxes cost less than both. Their model predicts that approach-retreat behavior should differ by element type — if evaluation cost varies, so should the motor signature of evaluation.

### Hypothesis: approach-retreat differs by SERP element type

AdSERP has ad boundary data (`ad-boundary-data/*.json`) with three element types:
- `native_ad`: Sponsored results embedded in organic listings
- `dd_top`: Top-of-page ad block
- `dd_right`: Right-side panel (Knowledge Panel, Shopping sidebar)

**Predicted cost ordering** (from Azzopardi's framework):
- **Right panel** (visual, image-heavy): Lowest evaluation cost → shortest approach, fastest retreat, lowest pupil load
- **Top ads** (text, familiar format): Medium cost → moderate approach, standard retreat
- **Organic results** (text, novel content): Highest evaluation cost → longest approach, deepest pupil load, longest retreat distance when rejected

**What to test:**
1. Approach rate by element type (controlling for position)
2. Retreat distance by element type (approached-rejected only)
3. Dwell-in-proximity by element type
4. Pupil LF/HF during approach by element type
5. Approach-to-click conversion rate by element type

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

## Open questions

- [ ] **Element-type cost structure validation:** Run notebook 15 analysis split by ad boundary data. Do approach signatures differ by element type as Azzopardi's framework predicts?
- [ ] **Regression-triggered approaches:** Do approach-retreat episodes cluster near scroll regressions? If users regress to re-evaluate, the approach signal during regressions should be stronger.
- [ ] **Cross-dataset generalizability:** AdSERP is transactional product search with forced choice. Does approach-retreat appear in informational queries? In naturalistic (non-forced) search? The motor signature should generalize; the rates may differ.
- [ ] **Temporal dynamics:** Does approach velocity change during the trial? If working memory fills, later approach-retreat episodes should show longer evaluation (higher dwell-in-proximity) as the comparison gets harder.

## Notebooks

- [15_cursor_approach.ipynb](../notebooks-v2/15_cursor_approach.ipynb) — Core analysis
- [13_survey_phase.ipynb](../notebooks-v2/13_survey_phase.ipynb) — OSEC phase model, survey fixation targets
- [05_lhipa.ipynb](../notebooks-v2/05_lhipa.ipynb) — Pupillometric validation
