# AdSERP Key Claims Analysis

**Paper:** Latifzadeh, Gwizdka & Leiva (2025). "A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages." SIGIR '25, 3412-3421. [DOI](https://doi.org/10.1145/3726302.3730325)

**Assessment:** This is a dataset paper, not a theory paper. The conceptual contributions are empirical observations, not mechanistic models. The gaps are where our work connects.

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

## What they don't claim (the gaps)

### A. No conditioning on click intent

Their aggregate 372px distance does not condition on whether or when a click occurs. **Our reanalysis** (N=128,887 pairs) shows this distance drops monotonically from ~334px (scanning) to ~172px (1-2s before click) — a 48% reduction. The reported aggregate inflates divergence by pooling high- and low-intent fixations.

### B. No temporal dynamics

Despite having timestamped mouse and gaze data, they compute spatial distance at concurrent timepoints only. No analysis of:
- Mouse lag/lead relative to gaze
- Phase-dependent coupling (scanning vs. evaluation vs. acquisition)
- Convergence rate or derivative analysis

### C. No mechanistic model of coupling/decoupling

They report *that* mouse and gaze diverge but not *why*. No engagement with:
- Motor planning literature (when does the hand start moving toward a gaze target?)
- Decision-making dynamics (evaluation phase, approach-avoidance)
- Response vigor framework (Shadmehr & Ahmed 2020)

### D. No pre-attentive or peripheral vision analysis

Zero discussion of:
- Whether SERP elements are detected peripherally before fixation
- Visual search strategy (F-pattern, golden triangle)
- How peripheral degradation affects which elements get fixated
- Pre-attentive features that guide the first saccade to an ad

This is a significant gap given the SERP context — structured layouts with repeated visual patterns (blue links, green URLs, ad badges) are exactly the kind of content where pre-attentive feature detection matters.

### E. No individual differences in mouse-gaze coupling

They report population-level statistics only. **Our analysis** finds per-participant acquisition onset ranges from 0.2s to 13.8s (mean=2.4s, SD=2.5s) — individual differences are large enough to warrant per-session calibration.

### F. No connection to click dynamics

The paper treats clicks as binary events (happened/didn't). No analysis of click approach dynamics, hold duration, or pre-click motor behavior — the signals ClickSense captures.

---

## Key citations they use (our overlap)

| Their citation | Our connection |
|---|---|
| Huang, White & Buscher 2012 — gaze-cursor alignment | Our reanalysis overturns their aggregate-distance framing |
| Arapakis & Leiva 2016, 2020 — mouse predicts engagement | Same Leiva behind evtrack; our work extends from prediction to mechanism |
| Bruckner et al. 2021 — early mouse movements most informative | Aligns with our finding that the 2s horizon has peak AUC (0.720) |
| Boi et al. 2016 — mouse doesn't match eye | We show it depends on p(click) |
| Smucker et al. 2014 — for simple tasks, mouse ≠ attention | Task complexity moderates coupling — supports per-session calibration |

## What they missed that we found

1. **p(click) conditioning** — mouse-gaze distance is not a fixed property; it's a function of decision state
2. **Three-phase structure** — scanning (>5s, ~330px) → evaluation (2-5s, declining) → acquisition (0-2s, ~170px)
3. **X-Y crossover** — X divergence dominates during scanning (mouse parked to side); Y catches up near click (vertical verification)
4. **Verification saccade** — 0.5-1s before click, gaze briefly diverges from mouse (checking something before committing)
5. **Individual calibration** — 2.5s SD in acquisition onset across participants
6. **Prediction ceiling with linear features** — raw distance gives AUC=0.631; convergence rate adds only +0.002; peak prediction at 2s horizon (AUC=0.720), not 5s

---

*Generated 2026-04-01 from AdSERP dataset reanalysis in attentional-foraging project.*
