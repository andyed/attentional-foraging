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

## Findings

Full writeup with caveats: **[docs/findings.md](docs/findings.md)**

### Lexical priming facilitates re-evaluation, not first-pass scanning

By position 9, 62% of a result's vocabulary already appeared in prior results. We hypothesized this cumulative priming would predict faster evaluation generally. **The result is more specific:** in trials where users scroll back to re-examine results, higher overlap predicts lower attention density (partial r = -0.033, p = 0.003). But in pure sequential first-pass evaluation (no regressions), the effect vanishes (r = -0.002, p = 0.92). Priming helps when you return to a result, not when you first encounter it — at least at bag-of-words granularity. Finer-grained semantic similarity may reveal a first-pass effect.

![Priming](plots-v1/plot_priming1_overview.png)

### Scroll regressions are the dominant pattern

69% of trials involve scrolling back up. Mean 2.8 regressions/trial, ~7 result slots of travel. Regression count correlates with decision time (r=0.660).

![Regressions](plots-v1/plot_reg1_overview.png)

### Mouse-gaze distance depends on click intent

With scroll-corrected coordinates, distance starts low (~90px, both gaze and mouse near page top), rises steadily as the user scrolls down (gaze follows content, mouse stays in screen space), peaks near ~500px, then converges sharply in the last ~2s before click. The reported 372px aggregate sits mid-curve.

![Convergence curve](plots-v1/plot1_convergence_curve.png)

*128,887 fixation-mouse pairs. Scroll-corrected page-space coordinates (v1).*

### Viewport state predicts clicks

When modeling click prediction at a 5s horizon, viewport state (target visible, time since scroll) outperforms mouse-gaze distance alone (AUC 0.704 vs 0.548). The scroll-stop event — when the viewport locks onto a result — is a stronger click signal than spatial proximity.

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
