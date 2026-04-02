# AdSight Key Claims Analysis

**Paper:** Villaizán-Vallelado, Salvatori, Latifzadeh, Penta, Leiva & Arapakis (SIGIR '25)
**DOI:** [10.1145/3726302.3729891](https://doi.org/10.1145/3726302.3729891)
**Relationship:** Uses the same 2,776-trial / 47-participant dataset as AdSERP. Companion paper — AdSERP describes the dataset, AdSight builds a model on it.

## Core Claims

### 1. Seq2Seq Transformer predicts per-slot fixation from mouse cursor trajectories

- **Architecture:** Encoder processes cursor trajectory embeddings (time series: x, y, time spent, slot type, sequence index). Decoder incorporates slot-specific metadata (normalized center position, slot type). Shared MLP readout predicts TFT/TFC per slot.
- **Best config:** Seq2Seq readout + Transformer encoder + time series representation.
- **Performance:** TFT prediction MSE = 2.86 ± 0.02 (≈1.69s average error), NDCG = 96.07 ± 0.04.
- **Baseline comparison:** Seq2Seq consistently outperforms MLP baseline across all embeddings, targets, and loss functions (Wilcoxon signed-rank, p < .05).
- **Verified:** Table 1. Numbers are consistent across the paper.

### 2. Classification: did the user notice this slot category?

- Four binary classifiers (direct-top, direct-right, organic-top, organic-bottom).
- **Best AUC:** 85.85 ± 0.04 (organic-top), with average ~82%.
- **Best F1:** ~76% average.
- **Fixation rates in dataset:** 42% direct-top, 46% direct-right, 44% organic-top, 29% organic-bottom.
- **Verified:** Table 2.

### 3. Sequence index is the most important cursor feature

- Ablation study (Table 5): removing sequence index causes the largest MSE/NDCG degradation.
- This is the temporal position of each cursor event in the trajectory — essentially "when in the trial did this cursor movement happen."
- **Implication for us:** The temporal position signal dominates. This aligns with our finding that result position (which correlates with temporal order of evaluation) is the strongest predictor of fixation time.

### 4. Slot metadata matters: position > type

- Removing slot type causes the biggest drop (Table 4). Removing normalized position (xc, yc) also hurts.
- Slot order is irrelevant — shuffling slot sequence doesn't affect performance.
- **Implication for us:** Where a result sits on the page matters more than what kind of result it is.

### 5. Auxiliary slots improve performance

- Adding N=3 virtual AOIs in gaps between real slots is optimal (Table 6).
- These help categorize cursor positions when the cursor is near but not inside a real slot.
- Moderate auxiliary loss weight (α=0.33) beats both 0 and 1 (Table 7).
- **Implication for us:** Cursor position is ambiguous about which result is being evaluated. Their engineering solution is to add virtual boundaries. Our approach (mapping fixations directly via scroll-corrected coordinates) avoids this problem by using eye tracking directly.

### 6. Rank loss outperforms MSE for NDCG

- Models optimized with Listwise Rank Loss achieve better NDCG than MSE-optimized models.
- Models predicting TFC generally achieve better NDCG than TFT predictors.
- **Verified:** Table 1, consistent across configurations.

## What AdSight Does NOT Do

These gaps are where our work is complementary or novel:

1. **No individual differences.** No per-user calibration, no user-level features, no analysis of satisfice/optimize strategies. Every user is treated identically. Our TTI calibrator (r=0.77 for fixation prediction at user level) could be an input feature to their model.

2. **No content features.** Purely geometric — cursor trajectory + slot position. No lexical features, no overlap between results, no priming. The priming hypothesis is entirely absent from their framing. (Our bag-of-words overlap test was null within-position controls; finer-grained content measures remain untested.)

3. **No temporal dynamics of evaluation.** They predict total fixation per slot but don't model how evaluation time changes across results within a trial. Our position-dependent evaluation curve (65% fixation drop from position 0→7) and the ski-jump are absent.

4. **No scroll analysis.** Scroll events are used only to track cursor position. No regression analysis, no scroll-as-behavioral-signal framing.

5. **No first-viewport vs scrolled distinction.** All trials treated the same regardless of scrolling behavior.

6. **Ad-centric framing.** The paper is positioned as a tool for computational advertising (ad placement, PPA auctions). The cognitive science of SERP evaluation is not their concern.

## Key References to Follow Up

From their bibliography, relevant to our work:

- **[50] Liu et al. (CIKM '14):** "From Skimming to Reading: A Two-stage Examination Model for Web Search." Two phases of SERP evaluation, both predictable from mouse. Directly relevant to our first-viewport vs scrolled finding.
- **[38] Jaiswal et al. (2023):** "Predicting users' behavior using mouse movement information: an information foraging theory perspective." IFT framing for mouse-based prediction — connects to our AFE angle.
- **[14] Brückner et al. (SIGIR '21):** "A Systematic Examination of Mouse Movement Length for Decision Making in Web Search." Same Leiva/Arapakis team. Mouse movement length as decision signal.
- **[29] Guo & Agichtein (SIGIR '10):** "Ready to buy or just browsing? detecting web searcher goals from interaction data." Goal detection from interaction — relevant to satisfice/optimize.
- **[30] Guo & Agichtein (SIGIR '10):** "Beyond dwell time: estimating document relevance from cursor movements and other post-click searcher behavior." Dwell time alternatives.
- **[19] Chukelin & de Rijke (CIKM '16):** "Incorporating Clicks, Attention and Satisfaction into a Search Engine Result Page Evaluation Model." Multi-signal SERP evaluation.

## Positioning Our Work Relative to AdSight

AdSight answers: "Can we predict where a user looked from where their mouse went?" (Yes, with ~1.69s error using a Transformer.)

We answer different questions:
- "What do users actually look at before clicking?" → Fixation coverage (95% above click)
- "Does cumulative content exposure speed up evaluation?" → Priming (aggregate r=-0.054, but does not survive within-position controls; forward-only dwell increases with position, ρ = +0.73)
- "Are there stable individual differences in evaluation strategy?" → Satisfice/optimize segmentation
- "Can we calibrate individual processing speed from early behavior?" → TTI calibrator (r=0.77)

The approaches are complementary. AdSight is a sophisticated prediction model; we're doing exploratory cognitive analysis of the same data. If anything, our TTI finding could improve AdSight — adding a per-user processing speed scalar as a decoder feature should reduce their 1.69s prediction error.
