# Attentional Foraging on SERPs

In July 2025, Latifzadeh, Gwizdka & Leiva published [AdSERP](https://github.com/kayhan-latifzadeh/AdSERP) — a dataset of 2,776 transactional search queries on Google, with simultaneous eye tracking (Gazepoint GP3 HD, 150 Hz), mouse tracking, scroll events, pupil dilation, SERP HTML snapshots, and ad bounding boxes from 47 participants. It's one of the richest public datasets on how people actually look at and interact with search results.

![Eye and mouse heatmaps from AdSERP](plots-v1/adserp_heatmaps.png)
*Eye vs. mouse heatmaps from the AdSERP paper (Figure 9). Eye fixations spread across results; mouse clusters in a single region. From [Latifzadeh et al. 2025](https://doi.org/10.1145/3726302.3730325).*

We found this dataset at 5am, got excited, and spent a morning exploring it. This repo is three notebooks of preliminary analysis — questions we wanted to ask, first-pass answers, and a transparent record of how we got there.

> **v1 — 2026-04-01. This is a <4 hour first pass.**
>
> **Revision strategy:** The [journey doc](docs/journey.md) is frozen at v0 — the first session as it happened, including wrong turns. Future updates add a "What we got wrong" section and revise the [findings](docs/findings.md). The point is to show the full arc.
>
> Built collaboratively by a human researcher and [Claude Code](https://claude.ai/claude-code). See [docs/journey.md](docs/journey.md).

---

## How we measure evaluation time

The eye tracker (Gazepoint GP3 HD, 150 Hz) records **fixation duration** — how long the eye holds still on a location. This is the direct measure of how long someone looked at something. We sum all fixation durations that fall within each result's page-space Y band to get **total fixation time per result** — our primary measure of evaluation time.

To assign fixations to results, we estimate each result's vertical boundaries from the SERP document height and number of results extracted. This is approximate. The AdSERP dataset includes **ad boundary data** (`ad-boundary-data.zip` on [Zenodo](https://zenodo.org/records/15236546)) with exact pixel bounding boxes for native ads, top display ads, and right-rail display ads. These give us precise Y positions for ad elements — the organic results fill the space around them. Combining ad boundaries with our h3-based result extraction would sharpen the fixation-to-result mapping. Pending.

We also compute **viewport time** — how long each result was ≥50% visible on screen (IAB viewability threshold), derived from the scroll event timeline. This lets us distinguish "evaluated briefly because it wasn't visible long" from "evaluated briefly because it was easy to process."

Full writeup with caveats: **[docs/findings.md](docs/findings.md)**

---

## Findings

### Results get less evaluation time as you scroll down

Total fixation time per result (eye-tracker, scroll-corrected page-space coordinates):

| Position | Fixation (ms) | Viewport (ms) | Overlap |
|----------|--------------|---------------|---------|
| 0 | 4,073 | 7,978 | 0% |
| 1 | 2,994 | 11,832 | 38% |
| 3 | 2,131 | 13,783 | 46% |
| 5 | 1,589 | 9,505 | 56% |
| 7 | 1,325 | 6,501 | 58% |
| 9 | 2,497 | 3,366 | 59% |

Fixation time drops 65% from position 0 to position 7. The uptick at position 9 is the "ski jump" — likely a pseudo forced-choice effect where the cost of loading page 2 concentrates attention on the last visible results.

### Lexical overlap builds rapidly — and that should matter

By position 9, 62% of a result's vocabulary has already appeared in prior results. Novel tokens per result drop from 28 to 10.

Why this matters: **lexical priming**. In reading research, previously encountered words are processed faster on re-encounter — less cognitive effort to recognize, categorize, and integrate. If a SERP user has already read "electro-harmonix tone tattoo analog delay" in results 1-3, encountering those same terms in result 7 should be cheaper to evaluate. The standard explanation for faster evaluation at lower positions is declining effort or attention fatigue. The alternative: it's cumulative priming from vocabulary redundancy.

![Priming](plots-v1/plot_priming1_overview.png)

![Per-result evaluation](plots-v1/plot_priming3_fixation.png)

### Priming predicts faster re-evaluation, not first-pass scanning

We hypothesized cumulative lexical overlap would predict shorter evaluation time generally — the alternative to "declining effort" as an explanation for faster evaluation at lower positions. **We detected the effect in re-evaluation but not in first-pass scanning:** in trials where users scroll back to re-examine results, higher overlap predicts less evaluation time per unit of visibility (partial r = -0.033, p = 0.003, 6/7 positions in the priming direction). In pure sequential first-pass evaluation (no scroll regressions), we did not detect the effect at bag-of-words granularity (r = -0.002, p = 0.92).

This is likely a detection sensitivity issue — bag-of-words token overlap is a crude measure. Stemming, sentence embeddings, and TF-IDF weighting would capture semantic priming that word-level set intersection misses. The first-pass effect may be real but below the threshold of this instrument.

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

## Notebooks

| Notebook | nbviewer | Topic |
|----------|----------|-------|
| **Convergence** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/convergence_analysis.ipynb) | Mouse-gaze distance conditioned on click intent, scroll-enriched prediction |
| **Regressions** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/scroll_regressions.ipynb) | Scroll regression prevalence, magnitude, timing, sparklines |
| **Priming** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/notebooks/serp_priming.ipynb) | Cumulative lexical overlap, priming × fixation duration |

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

- **[findings.md](docs/findings.md)** — What we think we found, with caveats
- **[journey.md](docs/journey.md)** — The first session, frozen at v0
- **[adserp-key-claims.md](docs/adserp-key-claims.md)** — The paper's claims and what the dataset enables

<a id="whats-next"></a>
## What's Next

- ~~**Per-result priming → evaluation speed**~~ Tested. **Prior hypothesis: lexical priming would predict faster evaluation generally.** Confirmed in re-evaluation (regression trials, r=-0.033, p=0.003) but null in first-pass sequential scanning (no-regression trials, r=-0.002, p=0.92). Priming facilitates re-evaluation, not first-pass scanning — at least at bag-of-words granularity.
- **Sharpen the overlap metric** (may reveal first-pass effect the crude measure missed):
  - Stemmed tokens (running/runs/runner → run)
  - Sentence embeddings (mxbai-embed-large) for paraphrase/synonym priming
  - TF-IDF weighted overlap — distinguish high-information from noise
  - Bigram/trigram overlap — phrase-level priming
- **Per-fixation analysis:** First-fixation duration (initial orientation) vs total fixation. Classic reading measure, more sensitive to priming.
- **First-click-only at scale:** Production logs, no forced choice, natural satisficing — the clean first-pass test this dataset can't provide.
- **Earliest click predictors:** First fixation revisit, mouse drift onset, scroll deceleration
- **Local novelty → regression triggers:** Per-result novelty predicting next scroll-back (time-series)
- **Pupil dilation × regressions**
- **AOI-filtered analysis:** Separate navigational from result-evaluation fixations

## Citation

```
Latifzadeh, K., Gwizdka, J., & Leiva, L. A. (2025).
A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages.
Proc. 48th ACM SIGIR Conference, 3412-3421.
https://doi.org/10.1145/3726302.3730325
```

## License

Analysis code: MIT. The AdSERP dataset has its own [license](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/LICENSE).
