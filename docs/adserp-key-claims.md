# AdSERP Key Claims Analysis

**Paper:** Latifzadeh, Gwizdka & Leiva (2025). "A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages." SIGIR '25, 3412-3421. [DOI](https://doi.org/10.1145/3726302.3730325)

**Assessment:** This is a dataset paper, not a theory paper. The conceptual contributions are empirical observations, not mechanistic models. The gaps are where our work connects.

> **Note:** Sections A and "What our reanalysis adds" below use v0 (uncorrected) numbers. See [findings.md](findings.md) for v1-corrected values — notably, the convergence curve shape changed after scroll correction (starts low, rises, then converges) and distance-only AUC dropped from 0.631 to 0.548.

---

## What they claim

### 1. Self-reported attention labels are noisy; fixation-based labels are better

> "Previous work has relied on mouse movements as a low-cost large-scale behavioral proxy but also has relied on self-reported ground-truth labels, collected at post-task, which can be inaccurate and prone to biases."

They train GRU/SVM/kNN classifiers and show fixation-based labels outperform self-reported labels, especially for organic ad attention. The margin is meaningful but not dramatic.

### 2. Mouse-gaze spatial alignment is substantial but imperfect

> "The mean Euclidean distance is 372.89 px (SD=293.78, Mdn=329.83), which is almost twice the value reported by Huang et al. (2011) (M=178, SD=139)."

They find Y-axis divergence exceeds X-axis, opposite to Huang et al. 2012. No explanation offered for this discrepancy — likely task differences (transactional vs. informational queries) and display setup.

### 3. DD ads modulate mouse-gaze coupling

KL divergence is lower (= more alignment) when display ads are present:
- Left-aligned DD + organic: KL = 17.27
- Organic only: KL = 21.90
- ANOVA: F(2,2644) = 11.93, p < .0001

Mutual information is non-significant (p = .4451). They conclude eye and mouse "disagree more on SERPs with only organic ads" but offer no mechanistic explanation.

### 4. Early mouse trajectory is most informative

> "our results showed that a short duration of 5 or 10 seconds is sufficient to predict visual attention from mouse movements"

> "it was more convenient to consider the first few mouse movements instead of considering the full mouse trajectory" (citing Bruckner et al. 2021)

Best classification: F1=93% for organic ads (GRU, 5s window), F1=73% for DD ads (GRU, 10s window). Mouse is a much better predictor of organic-ad attention than DD-ad attention.

### 5. DD ads capture disproportionate visual attention

> "DD ads tend to capture user attention in much larger proportions than previously known, while organic ads receive comparatively less attention."

But clicks tell the opposite story: 82.42% of clicks land on non-ad elements. DD ads attract gaze but not clicks — a gaze-action dissociation.

---

## Opportunities the dataset enables

The authors' contribution is the dataset itself — a generous, well-structured public resource that makes all of the following analyses possible. These are directions we pursued, not criticisms of what a dataset paper chose to scope.

### A. Conditioning on click intent

Their aggregate 372px distance does not condition on whether or when a click occurs. **Our reanalysis** (N=128,887 pairs) shows this distance drops monotonically from ~334px (scanning) to ~172px (1-2s before click) — a 48% reduction. The reported aggregate inflates divergence by pooling high- and low-intent fixations.

### B. Temporal dynamics

The dataset's timestamped mouse and gaze data enables temporal analyses beyond concurrent spatial distance:
- Mouse lag/lead relative to gaze
- Phase-dependent coupling (scanning vs. evaluation vs. acquisition)
- Convergence rate or derivative analysis

### C. Mechanistic modeling of coupling/decoupling

The dataset supports connecting mouse-gaze divergence to established motor/decision frameworks:
- Motor planning literature (when does the hand start moving toward a gaze target?)
- Decision-making dynamics (evaluation phase, approach-avoidance)
- Response vigor framework (Shadmehr & Ahmed 2020)

### D. Pre-attentive and peripheral vision analysis

The SERP screenshots + fixation sequences enable questions about peripheral processing:
- Whether SERP elements are detected peripherally before fixation
- Visual search strategy (F-pattern, golden triangle)
- How peripheral degradation affects which elements get fixated
- Pre-attentive features that guide the first saccade to an ad

Structured SERP layouts with repeated visual patterns (blue links, green URLs, ad badges) are exactly the kind of content where pre-attentive feature detection matters.

### E. Individual differences in mouse-gaze coupling

**Our analysis** finds per-participant acquisition onset ranges from 0.2s to 13.8s (mean=2.4s, SD=2.5s) — the dataset supports rich individual-differences analysis.

### F. Click dynamics

The dataset's click events could be connected to approach dynamics, hold duration, and pre-click motor behavior — complementing work like ClickSense on motor commitment signals.

### G. Forced-choice purchase task as a foraging paradigm

The AdSERP task design — participants must click an item they would "typically choose" to purchase — is a serendipitous experimental paradigm for studying the foraging-to-exploitation transition. The forced choice with optimizing intent creates a defined stopping criterion: the user *must* commit. Most SERP studies use open-ended informational tasks where the user can abandon, reformulate, or leave without clicking. This means the patch-leaving decision (in Information Foraging Theory terms) is unobservable. In AdSERP, every trial ends with an observable commitment, and the 69% regression rate captures the cost of re-evaluation before that commitment.

This deserves a literature review: forced-choice vs open-ended SERP task designs and what each reveals about the decision process. Key questions: How does the forced stopping criterion change regression behavior? Do open-ended tasks show the same priming × re-evaluation interaction, or does the ability to abandon short-circuit it? What other forced-choice SERP paradigms exist, and do they report comparable regression rates?

---

## Key citations they use (our overlap)

| Their citation | Our connection |
|---|---|
| Huang, White & Buscher 2012 — gaze-cursor alignment | Our reanalysis overturns their aggregate-distance framing |
| Arapakis & Leiva 2016, 2020 — mouse predicts engagement | Same Leiva behind evtrack; our work extends from prediction to mechanism |
| Bruckner et al. 2021 — early mouse movements most informative | Aligns with our finding that the 2s horizon has peak AUC (0.720) |
| Boi et al. 2016 — mouse doesn't match eye | We show it depends on p(click) |
| Smucker et al. 2014 — for simple tasks, mouse ≠ attention | Task complexity moderates coupling — supports per-session calibration |

## What our reanalysis adds

1. **p(click) conditioning** — mouse-gaze distance is not a fixed property; it's a function of decision state
2. **Three-phase structure** — scanning (>5s, ~330px) → evaluation (2-5s, declining) → acquisition (0-2s, ~170px)
3. **X-Y crossover** — X divergence dominates during scanning (mouse parked to side); Y catches up near click (vertical verification)
4. **Verification saccade** — 0.5-1s before click, gaze briefly diverges from mouse (checking something before committing)
5. **Individual calibration** — 2.5s SD in acquisition onset across participants
6. **Prediction ceiling with linear features** — raw distance gives AUC=0.631; convergence rate adds only +0.002; peak prediction at 2s horizon (AUC=0.720), not 5s

---

## Citation audit: prior work by finding

Audit conducted 2026-04-01. Searched Gwizdka, Leiva, Latifzadeh, Arapakis publication lists and broader literature.

| Finding | Prior work | Our contribution | Key citations |
|---------|-----------|-----------------|---------------|
| Mouse-gaze distance conditioned on click intent | Gaze-cursor alignment tightens near clicks (Huang et al. CHI 2012). ~66% nonlinear scanpaths (Lorigo et al. JASIST 2008). | Continuous time-to-click curve, scroll correction showing aggregate mixes two regimes | Huang, White & Buscher 2012; Chen, Anderson & Sohn 2001 |
| Scroll features beat distance for click prediction | Viewport visibility used in prefetching (Diaz et al. TOIS 2017). Click+scroll > click-only (Lagun et al. SIGIR 2014). | Direct AUC comparison: viewport (0.704) vs distance (0.548) after scroll correction | Diaz et al. 2017; Wang et al. SIGIR 2018; Lagun et al. 2014 |
| 69% scroll regression prevalence | ~66% nonlinear SERP scanpaths (Lorigo et al. 2008). No scroll-level quantification. | Scroll-level regression frequency, magnitude (~7 slots), decision-time correlation (r=0.660) | Lorigo et al. JASIST 2008; Granka et al. SIGIR 2004 |
| **Lexical priming predicts evaluation speed** | **No prior work found.** Position bias literature (Joachims 2005, Craswell 2008) attributes speed-up to trust. Gwizdka 2010/2014 on cognitive load. | **Novel.** Partial r = -0.054 after position control. First test of content redundancy driving SERP evaluation speed. | Joachims et al. 2005; Hale 2001 / Levy 2008 (surprisal theory); Gwizdka 2010 |
| Eye finds target ~15s before click | Eyes lead mouse ~300ms (Chen et al. 2001; Huang et al. 2012). 2-3s mouse trajectory predictive (Bruckner et al. 2021). | Macro-level temporal gaps: eye 14.9s, revisit 13.6s, mouse 9.1s. Different scale than micro-level 300ms. | Chen et al. 2001; Bruckner, Arapakis & Leiva 2021 |

### Key papers from the AdSERP team to cite

- Latifzadeh, Gwizdka & Leiva (2025) — AdSERP dataset. The foundation.
- Villazan-Vallelado et al. (2025) — AdSight. Slot-level attention from cursor at scale.
- Bruckner, Arapakis & Leiva (2021) — "When Choice Happens." Closest to our temporal analysis.
- Arapakis & Leiva (2020) — SIGIR. Neural attention prediction from cursor.
- Gwizdka (2010) — JASIST. Cognitive load distribution in web search.
- Shi & Gwizdka (2024) — Confirmation bias + readability. Closest to evaluation speed.

---

*Generated 2026-04-01. Citation audit added 2026-04-01.*
