# Attentional Foraging on SERPs

Reanalysis of the [AdSERP dataset](https://github.com/kayhan-latifzadeh/AdSERP) (Latifzadeh, Gwizdka & Leiva, SIGIR 2025) — 2,776 transactional queries on Google SERPs with simultaneous eye tracking + mouse tracking from 47 participants.

Three notebooks exploring mouse-gaze convergence, scroll regressions, and lexical priming as signals of attentional foraging and click intent.

## Notebooks

| Notebook | nbviewer | Key finding |
|----------|----------|-------------|
| **1. Mouse-Gaze Convergence** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/convergence_analysis.ipynb) | Mouse-gaze distance drops 48% (334→172px) as click approaches. Scroll viewport state (AUC=0.704) beats raw distance (0.631) for click prediction. |
| **2. Scroll Regressions** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/scroll_regressions.ipynb) | 69.1% of trials contain scroll regressions. Mean 2.8 regressions/trial, 1,118px magnitude (~7 result slots). Correlates with decision time (r=0.660). |
| **3. Lexical Priming** | [View](https://nbviewer.org/github/andyed/attentional-foraging/blob/main/serp_priming.ipynb) | Cumulative lexical overlap reaches 62% by SERP position 9. Novel tokens per result drop from 28 to 10. SERP-level homogeneity doesn't predict regressions — local novelty events likely trigger them. |

## The Core Argument

The widely reported mouse-gaze distance (~372px in AdSERP) has never been conditioned on **click intent**. We show this aggregate hides two distinct regimes:

1. **Before ~10s to click:** The click target is in the viewport only ~50% of the time (chance). "Distance to target" is an abstract distance-to-goal metric, not a spatial-motor signal.
2. **After ~10s to click:** The target enters the viewport, and mouse-gaze distance becomes spatially meaningful. Three phases emerge — scanning (~330px), evaluation (declining), acquisition (~172px).

Scroll-stop is the real event. Viewport state predicts clicks better than gaze-mouse distance.

### Scroll regressions are the norm, not the exception

69% of SERP trials involve scrolling back up to re-examine previously viewed results. This page-level behavior — analogous to fixation regressions in reading — is barely characterized in the literature despite being the dominant browsing pattern.

### Acceleration down the SERP is priming, not fatigue

Users evaluate results faster as they scroll down. The standard interpretation is declining effort or attention. We show cumulative lexical overlap rises steeply (62% by position 9) — faster evaluation is predicted by vocabulary priming, not disengagement.

## Data

Behavioral data (~15MB) downloads from [Zenodo](https://zenodo.org/records/15236546). SERP HTML (~535MB) needed for notebook 3 only.

```bash
cd AdSERP/data
# Required for notebooks 1 & 2:
curl -L -o fixation-data.zip "https://zenodo.org/records/15236546/files/fixation-data.zip?download=1"
curl -L -o mouse-movement-data.zip "https://zenodo.org/records/15236546/files/mouse-movement-data.zip?download=1"
curl -L -o trial-metadata.zip "https://zenodo.org/records/15236546/files/trial-metadata.zip?download=1"
unzip -q fixation-data.zip && unzip -q mouse-movement-data.zip && unzip -q trial-metadata.zip

# Required for notebook 3 (lexical priming):
curl -L -o serps.zip "https://zenodo.org/records/15236546/files/serps.zip?download=1"
unzip -q serps.zip
```

## Setup

```bash
uv sync   # installs Python deps from pyproject.toml
uv run jupyter execute convergence_analysis.ipynb --inplace
uv run jupyter execute scroll_regressions.ipynb --inplace
uv run jupyter execute serp_priming.ipynb --inplace
```

## Relationship to AdSERP

This is a reanalysis, not a fork. The [AdSERP dataset paper](https://doi.org/10.1145/3726302.3730325) is a dataset contribution — it provides the data and baseline classifiers. Our analysis asks different questions: when does mouse track gaze (conditioned on intent), what role does scrolling play, and how does SERP content structure shape the foraging process.

See [docs/adserp-key-claims.md](docs/adserp-key-claims.md) for a detailed analysis of the paper's theoretical claims and gaps, and [docs/journey.md](docs/journey.md) for the research narrative.

## What's Next

- Per-result novelty → regression trigger analysis (does a single novel result cause the user to scroll back?)
- Pupil dilation × scroll regressions (cognitive load/surprise signal)
- Fixation-to-result mapping via ad bounding boxes (per-result evaluation time)
- Scrutinizer foveated replay on SERP scanpaths (what does peripheral vision deliver at each fixation?)
- Coordinate correction: scroll-adjusted page-space distances

## Citation

If you use this analysis, please cite both this repository and the original dataset:

```
Latifzadeh, K., Gwizdka, J., & Leiva, L. A. (2025).
A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages.
Proc. 48th ACM SIGIR Conference, 3412-3421.
https://doi.org/10.1145/3726302.3730325
```

## License

Analysis code: MIT. The AdSERP dataset has its own [license](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/LICENSE).
