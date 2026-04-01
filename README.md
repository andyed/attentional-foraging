# Attentional Foraging on SERPs

In July 2025, Latifzadeh, Gwizdka & Leiva published [AdSERP](https://github.com/kayhan-latifzadeh/AdSERP) — a dataset of 2,776 transactional search queries on Google, with simultaneous eye tracking (Gazepoint GP3 HD, 150 Hz), mouse tracking, scroll events, pupil dilation, SERP HTML snapshots, and ad bounding boxes from 47 participants. It's one of the richest public datasets on how people actually look at and interact with search results.

![Eye and mouse heatmaps from AdSERP](plots-v1/adserp_heatmaps.png)
*Eye vs. mouse heatmaps from the AdSERP paper (Figure 9). Eye fixations spread across results; mouse clusters in a single region. From [Latifzadeh et al. 2025](https://doi.org/10.1145/3726302.3730325).*

We found this dataset, got excited, and spent an afternoon exploring it. This repo is three notebooks of preliminary analysis — questions we wanted to ask, first-pass answers, and a transparent record of how we got there.

> **v1 — 2026-04-01. This is a <4 hour first pass.**
>
> **Revision strategy:** The [journey doc](docs/journey.md) is frozen at v0 — the first session as it happened, including wrong turns. Future updates add a "What we got wrong" section and revise the [findings](docs/findings.md). The point is to show the full arc.
>
> Built collaboratively by a human researcher and [Claude Code](https://claude.ai/claude-code). See [docs/journey.md](docs/journey.md).

---

## Findings

Full writeup with caveats: **[docs/findings.md](docs/findings.md)**

### Mouse-gaze distance depends on click intent

Conditioning the reported 372px aggregate on time-to-click reveals it mixes two regimes. Before ~10s the target is often not in the viewport. In the last 10s, distance drops as the mouse converges on the visible target.

![Convergence curve](plots-v1/plot1_convergence_curve.png)

*128,887 fixation-mouse pairs. Scroll-corrected page-space coordinates (v1).*

### Eye movements coordinate scrolling

Viewport state — target visible, time since scroll — predicts clicks better than mouse-gaze distance (AUC 0.704 vs 0.548).

![Scroll dynamics](plots-v1/plot10_scroll_dynamics.png)

### Scroll regressions are the dominant pattern

69% of trials involve scrolling back up. Mean 2.8 regressions/trial, ~7 result slots of travel.

![Regressions](plots-v1/plot_reg1_overview.png)

### Lexical overlap builds rapidly

By position 9, 62% of a result's vocabulary already appeared in prior results. Whether this priming mediates evaluation speed — the alternative to "declining effort" — is our most interesting open question.

![Priming](plots-v1/plot_priming1_overview.png)

---

## Notebooks

| Notebook | nbviewer | Topic |
|----------|----------|-------|
| **Convergence** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/convergence_analysis.ipynb) | Mouse-gaze distance conditioned on click intent, scroll-enriched prediction |
| **Regressions** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/scroll_regressions.ipynb) | Scroll regression prevalence, magnitude, timing, sparklines |
| **Priming** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/serp_priming.ipynb) | Cumulative lexical overlap, SERP homogeneity |

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

- **Per-result priming → evaluation speed:** Link lexical overlap to fixation duration using the paper's attention metric (fixation duration on AOI / total fixation duration)
- **Local novelty → regression triggers**
- **Pupil dilation × regressions**
- **AOI-filtered analysis:** Separate navigational fixations from result-evaluation fixations using ad boundary data
- **Citation audit**

## Citation

```
Latifzadeh, K., Gwizdka, J., & Leiva, L. A. (2025).
A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages.
Proc. 48th ACM SIGIR Conference, 3412-3421.
https://doi.org/10.1145/3726302.3730325
```

## License

Analysis code: MIT. The AdSERP dataset has its own [license](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/LICENSE).
