# Attentional Foraging — Analysis Notebooks (v2)

Sequentially numbered notebooks with shared utilities in [`data_loader.py`](data_loader.py).

## Notebook Map

| File | Topic |
|------|-------|
| `00_skijump.ipynb` | Click distribution by position, boundary uptick, satisficer/optimizer split, LHIPA, difficulty |
| `01_convergence.ipynb` | Mouse-gaze distance conditioned on click intent, scroll-enriched prediction |
| `02_gaze_cursor_lag.ipynb` | Temporal lag between gaze and cursor, split-half reliability |
| `03_early_predictors.ipynb` | Early-trial predictors of click target |
| `04_fixation_coverage.ipynb` | Fixation coverage, TTI, evaluation time decomposition |
| `05_lhipa.ipynb` | LHIPA pupillometric cognitive load validation |
| `06_orientation_evaluation.ipynb` | Cognitive phases, evaluation effort by position, TTI calibrator |
| `07a_regressions_prevalence.ipynb` | Scroll regression prevalence and rates |
| `07b_regressions_triggers.ipynb` | Regression decision triggers, confirmation vs rejection |
| `07c_regressions_kinematics.ipynb` | Scroll kinematics, ballistic backward scrolling |
| `08_priming.ipynb` | Lexical priming — null at three granularities |
| `09_difficulty.ipynb` | SERP difficulty (relevance spread, TF-IDF density), reading episodes |
| `10_strategies.ipynb` | Satisfice vs optimize segmentation |
| `11_individual_differences.ipynb` | Two independent individual difference dimensions |
| `23_rank_effects.ipynb` | **Unified rank effects** — all by-position measures on one page, framework compilation narrative |

## Quick Start

```python
from data_loader import *
setup_plotting()

trial_ids = get_trial_ids()                    # all 2,776 trial IDs
fixations = load_fixations('p004-b1-t1')       # [{t, x, y, d}, ...]
events, scrolls, clicks = load_mouse_events('p004-b1-t1')
doc_h, scr_h, ts = get_trial_meta('p004-b1-t1')
trial = load_trial('p004-b1-t1')               # everything at once
```

See `data_loader.py` for the full API: scroll interpolation, result band estimation, SERP text extraction, fixation-to-position mapping, catalog/LHIPA/difficulty loaders.

## Data

Loads directly from `../AdSERP/data/` (per-trial CSV/XML/HTML files). No preprocessing step needed.

## Environment

```bash
uv sync   # from repo root
source .venv/bin/activate
```

Python 3.13. Core deps: `numpy`, `scipy`, `polars`, `matplotlib`, `beautifulsoup4`, `ipykernel`. **No pandas, no seaborn.**

To run a script without activating the venv:

```bash
PYTHON=$(pwd)/.venv/bin/python
$PYTHON scripts/<name>.py
```
