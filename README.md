# Attentional Foraging on SERPs

[Demo](https://andyed.github.io/attentional-foraging/) | [Why](#why-this-project-exists) | [Findings](#findings) | [Notebooks](#notebooks) | [Data](#data) | [Docs](#docs) | [What's Next](#whats-next) | [Citation](#citation)

---

## Why this project exists

This project has three goals:

1. **Test the priming hypothesis.** In a [2021 CHIIR workshop talk](https://www.linkedin.com/in/andyed/), I conjectured that result evaluation speeds up down the SERP partly because of cumulative lexical priming — previously encountered terms get cheaper to process on re-encounter. The AdSERP dataset provided the first opportunity to test this directly with eye-tracking fixation data. (Result: [null at three granularities](#cumulative-content-overlap-does-not-predict-evaluation-speed) — bag-of-words, semantic embeddings, and within-position controls. The most parsimonious explanation for slower evaluation at lower positions is growing working memory load, not content priming. Token-level fixation analysis remains untested.)

2. **Build out gaze replay for [Scrutinizer](https://github.com/andyed/scrutinizer2025).** Scrutinizer is a neuroscience-based foveated vision simulator. AdSERP's simultaneous gaze + mouse + scroll recordings on real Google SERPs were the ideal stress test for a new scanpath replay pipeline — importing eye-tracking data and rendering what the searcher could actually resolve at each fixation.

3. **Stress-test and evolve a working model of search as attentional foraging.** The [Attentional-Foraging Equilibrium (AFE)](#theoretical-framework) is an unpublished framework that synthesizes Rational Inattention (Sims 2003) with Information Foraging Theory (Pirolli & Card 1999). It treats SERP browsing as patch foraging: scroll regressions as travel costs, the mouse-gaze convergence curve as the exploitation transition, per-participant variance as individual bandwidth differences. This model is grounded in the academic literature but also in a decade of shipping search and recommendation systems at scale (eBay, Microsoft, Meta, Quora) — industrial contexts where the same foraging dynamics play out across billions of queries. The AFE is a working model, not a published theory; this project is where it gets tested against real behavioral data.

## Interactive foveated scanpath replays

**[andyed.github.io/attentional-foraging](https://andyed.github.io/attentional-foraging/)** — 8 curated search sessions replayed through [Scrutinizer](https://github.com/andyed/scrutinizer2025)'s foveated vision pipeline. Full-page renders showing what each participant could actually resolve at each fixation: sharp where they looked, degraded through LGN/V1/DoG peripheral pooling where they didn't. Scanpath overlay with numbered fixations, saccade lines, timeline scrubbing, and playback.

---

## Dataset

[AdSERP](https://github.com/kayhan-latifzadeh/AdSERP) ([paper](https://doi.org/10.1145/3726302.3730325), [Zenodo](https://zenodo.org/records/15236546)) — Latifzadeh, Gwizdka & Leiva, SIGIR 2025.

2,776 transactional search queries on Google, 47 participants, simultaneous eye tracking (Gazepoint GP3 HD, 150 Hz), mouse tracking, scroll events, pupil dilation, SERP HTML snapshots, and ad bounding boxes. One of the richest public datasets on how people actually look at and interact with search results.

![Eye and mouse heatmaps from AdSERP](plots-v1/adserp_heatmaps.png)
*Eye vs. mouse heatmaps from the AdSERP paper (Figure 9). Eye fixations spread across results; mouse clusters in a single region. From [Latifzadeh et al. 2025](https://doi.org/10.1145/3726302.3730325).*

---

## Findings

### Results get less evaluation time as you scroll down

Total fixation time per result (eye-tracker, scroll-corrected page-space coordinates):

| Position | Fixation (ms) | Viewport (ms) | Dwell Ratio | Overlap |
|----------|--------------|---------------|-------------|---------|
| 0 | 4,085 | 14,584 | 0.28 | 0% |
| 1 | 3,071 | 17,990 | 0.18 | 38% |
| 3 | 2,154 | 16,488 | 0.16 | 46% |
| 5 | 2,288 | 9,479 | 0.33 | 55% |
| 7 | 1,997 | 6,401 | 0.42 | 58% |
| 9 | 2,035 | 3,454 | 0.79 | 59% |

Fixation time drops from position 0 to position 3. Gaze dwell ratio — fixation duration / visible duration — drops from 0.28 to 0.16 by position 3, then *rises* back through positions 4-9. The U-shape means later results get more intense evaluation per unit of visible time, not less. This pattern has been observed in click share data at eBay, Redbubble, MSN Search, and others (also reported by SLI Systems, Jakob Nielsen, Lou Rosenfeld). The explanation: people make a locally rational decision between the last set of results and the temporal/attentional cost of Next (Edmonds, ["Search as Augmented Cognition,"](https://www.linkedin.com/in/andyed/) CHIIR Made to Measure Workshop, 2021). The same talk proposed the priming hypothesis tested here: *"Why does result evaluation speed up? Hypothesis: Semantic priming and reduced cost of lexical processing, verifiable by manipulating heterogeneity of search results."* In this lab study, the forced-click task likely amplifies the ski jump — there is no Next button, so position 9 *is* the boundary.

### Cumulative content overlap does not predict evaluation speed

By position 9, 62% of a result's vocabulary has already appeared in prior results. We hypothesized this cumulative exposure would make later results cheaper to evaluate — a priming effect from redundancy.

**Tested at three levels of granularity, null at all of them.** Bag-of-words overlap, semantic embeddings (mxbai-embed-large cosine similarity), and within-position controls all show no relationship between content overlap and evaluation speed. The aggregate correlation (partial r = -0.054) was an artifact of position-overlap confounding. Forward-only dwell *increases* with position (Spearman ρ = +0.82), opposite the priming prediction — evaluation slows as the candidate set in working memory grows.

![Priming](plots-v1/plot_priming1_overview.png)

![Per-result evaluation](plots-v1/plot_priming3_fixation.png)

Token-level fixation analysis (do previously-encountered words receive shorter fixations within a result?) and at-scale production logs remain untested. But the result-level hypothesis is tested and null. See [findings.md](docs/findings.md) for the full decomposition.

### p(fixate | visible) is also null — and structurally uninformative

We tested whether overlap predicts *skipping* results entirely (binary: fixated or not). The aggregate signal looks real (r_pb = -0.059, 8/9 positions in skip direction) but forward-only p(fixate) is ~99.8% at every position. During first-pass scanning, users fixate virtually everything visible — there is no skip decision for overlap to predict. The 12.5% skip rate is concentrated in regressions.

### Evaluation time decomposes into four components

Per-fixation duration is **flat at ~220ms** regardless of position. The position-dependent decline in total fixation time comes from investing fewer fixations at lower positions — an attention allocation decision. Page orientation (median **194ms** — participants locate the first result almost instantly, consistent with a well-memorized SERP layout) and linear scanning rate (~1.7-2.6s/position) are the other components. This reframes the priming question: if content effects exist, they should appear in fixation *count*, not fixation *duration*.

### Scroll regressions are the dominant pattern

69% of trials involve scrolling back up. Mean 2.8 regressions/trial, ~7 result slots of travel. Regression count correlates with decision time (r=0.660). The high rate is likely inflated by the forced-choice task — participants must click, so they re-evaluate rather than abandon.

![Regressions](plots-v1/plot_reg1_overview.png)

### Mouse-gaze convergence depends on click intent

With scroll-corrected page-space coordinates, mouse-gaze distance starts low (~90px, both near page top), then rises monotonically as the user scrolls (gaze follows content down the page, mouse stays in screen space — the offset accumulates). Distance peaks near ~500px. A modest downturn appears in the final 1-2 seconds before click, but the "sharp convergence" we reported in v0 was largely an artifact of uncorrected coordinates. The corrected picture is dominated by scroll accumulation, not by motor convergence.

![Convergence curve](plots-v1/plot1_convergence_curve.png)

### Viewport state predicts clicks better than distance

At a 5s horizon, viewport features (target visible, time since scroll) outperform mouse-gaze distance alone (AUC 0.704 vs 0.548). The scroll-stop event is the stronger click signal.

![Scroll dynamics](plots-v1/plot10_scroll_dynamics.png)

---

## Theoretical framework

These findings are interpreted through the **Attentional-Foraging Equilibrium (AFE)**, which synthesizes Rational Inattention (Sims 2003) with Information Foraging Theory (Pirolli & Card 1999). AFE models SERP browsing as patch foraging: scroll regressions are travel costs paid for re-evaluation, the convergence curve traces the transition from foraging to exploitation, and per-participant variance maps to individual bandwidth differences. The forced-choice purchase task in AdSERP is useful here because it creates a defined stopping criterion — making the patch-leaving decision observable where most SERP studies cannot (cf. [Diriye et al. 2012](https://doi.org/10.1145/2396761.2398399) on search abandonment as the alternative outcome). Full framework: [AFE presentation](https://gamma.app/docs/The-Attentional-Foraging-Equilibrium-A-Synthesis-of-Digital-Behav-aq0bw2ujjxwypbt). Detailed mapping in [findings.md](docs/findings.md).

---

## Notebooks

| Notebook | nbviewer | Topic |
|----------|----------|-------|
| **Convergence** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/convergence_analysis.ipynb) | Mouse-gaze distance conditioned on click intent, scroll-enriched prediction |
| **Regressions** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/scroll_regressions.ipynb) | Scroll regression prevalence, magnitude, timing, sparklines |
| **Priming** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/serp_priming.ipynb) | Cumulative lexical overlap × evaluation time; within-position controls null, forward-only dwell reverses |
| **Coverage & TTI** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/fixation_coverage.ipynb) | Fixation coverage above click, TTI, processing speed calibration |
| **User Strategies** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/user_strategies.ipynb) | Satisfice vs optimize segmentation by regression rate |
| **Scroll Kinematics** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/scroll_kinematics.ipynb) | Viewport mechanics confound: ballistic backward scrolling biases regression dwell ratios |
| **LHIPA Validation** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/lhipa_validation.ipynb) | Pupillometric cognitive load (Duchowski et al. 2020) on AdSERP: validates against behavior, monotonic with foraging depth |
| **Orientation & Evaluation** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/orientation_evaluation.ipynb) | Cognitive phases: 194ms orientation, 220ms/fixation constant, working memory ramp, TTI as individual calibrator |
| **Regression Decisions** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/regression_decisions.ipynb) | What triggers regressions, confirmation vs rejection on revisit, satisfice/optimize × LHIPA |

## Data

Behavioral data (~15MB) from [Zenodo](https://zenodo.org/records/15236546). SERP HTML (~535MB) for notebook 3 only.

```bash
cd AdSERP/data
curl -L -o fixation-data.zip "https://zenodo.org/records/15236546/files/fixation-data.zip?download=1"
curl -L -o mouse-movement-data.zip "https://zenodo.org/records/15236546/files/mouse-movement-data.zip?download=1"
curl -L -o trial-metadata.zip "https://zenodo.org/records/15236546/files/trial-metadata.zip?download=1"
unzip -q fixation-data.zip && unzip -q mouse-movement-data.zip && unzip -q trial-metadata.zip
```

```bash
uv sync && uv run jupyter execute convergence_analysis.ipynb --inplace
```

## Docs

- **[CHANGELOG.md](CHANGELOG.md)** — Version history, bug fixes, corrections
- **[findings.md](docs/findings.md)** — What we think we found, with caveats
- **[journey.md](docs/journey.md)** — The first session, frozen at v0
- **[adserp-key-claims.md](docs/adserp-key-claims.md)** — The AdSERP paper's claims and what the dataset enables
- **[adsight-key-claims.md](docs/adsight-key-claims.md)** — AdSight companion paper analysis (Transformer mouse→fixation prediction)
- **[shi2025-key-claims.md](docs/shi2025-key-claims.md)** — Shi et al. CHIIR 2025: LHIPA pupillometry, mismatch finding, comparison to our replication
- **[references.bib](references.bib)** — Verified BibTeX library (20 entries, all with DOIs or arXiv IDs)

## History

This started as a 4-hour morning sprint after finding the AdSERP dataset at 5am. The [journey doc](docs/journey.md) is frozen at that v0 — wrong turns and all. The [findings](docs/findings.md) continue to be revised. Built collaboratively by a human researcher and [Claude Code](https://claude.ai/claude-code).

<a id="whats-next"></a>
## What's Next

- ~~**Per-result priming → evaluation speed**~~ Tested at three granularities (bag-of-words, semantic embeddings, within-position controls). Null at all of them. Forward-only dwell increases with position (ρ = +0.82). The most parsimonious explanation: cognitive load increases with foraging depth as the working memory candidate set grows.
- **Token-level fixation analysis:** Do previously-encountered words receive shorter fixations within a result? Requires word-level AOI mapping against the SERP HTML. The only untested priming granularity.
- **First-click-only at scale:** Production logs, no forced choice, natural satisficing — the clean first-pass test this dataset can't provide.
- **Earliest click predictors:** First fixation revisit, mouse drift onset, scroll deceleration
- **Local novelty → regression triggers:** Per-result novelty predicting next scroll-back (time-series)
- **Pupil dilation × regressions**
- **AOI-filtered analysis:** Separate navigational from result-evaluation fixations
- **Full-page foveated video replays** of complete search sessions through Scrutinizer

## Citation

```
Latifzadeh, K., Gwizdka, J., & Leiva, L. A. (2025).
A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages.
Proc. 48th ACM SIGIR Conference, 3412-3421.
https://doi.org/10.1145/3726302.3730325
```

## License

Analysis code: MIT. The AdSERP dataset has its own [license](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/LICENSE).
