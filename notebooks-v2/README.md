# Attentional Foraging — Analysis Notebooks (v2)

Sequentially numbered notebooks matching the paper section structure.
Shared utilities live in `data_loader.py`.

## Notebook Map

| File | Section | Topic |
|------|---------|-------|
| `01_convergence.ipynb` | §1 | Convergence analysis — gaze/cursor signal quality |
| `02_gaze_cursor_lag.ipynb` | §2 | Temporal lag between gaze and cursor |
| `03_early_predictors.ipynb` | §3 | Early-trial predictors of task success |
| `04_fixation_coverage.ipynb` | §4 | Fixation spatial coverage of SERP |
| `05_lhipa.ipynb` | §5 | LHIPA cognitive load validation |
| `06_orientation_evaluation.ipynb` | §6 | Orientation phase evaluation |
| `07a_regressions_prevalence.ipynb` | §7a | Scroll regressions — prevalence & rates |
| `07b_regressions_triggers.ipynb` | §7b | Regression decision triggers |
| `07c_regressions_kinematics.ipynb` | §7c | Regression scroll kinematics |
| `08_priming.ipynb` | §8 | SERP priming effects |
| `09_difficulty.ipynb` | §9 | SERP difficulty factors |
| `10_strategies.ipynb` | §10 | User foraging strategies |
| `11_individual_differences.ipynb` | §11 | Individual difference dimensions |

## Data Layout

Expected under `../data/` (one level up from this directory):

```
data/
  sessions.csv        — session-level metadata
  fixations.csv       — fixation events (t, x, y, duration_ms)
  events.csv          — raw event stream (gaze, mouse, scroll, click)
  serps.csv           — SERP metadata (query, condition, difficulty)
  participants.csv    — participant demographics / ID measures
```

## Quick Start

```python
from data_loader import load_sessions, load_fixations, load_events, DATA_DIR

sessions   = load_sessions()
fixations  = load_fixations()
events     = load_events()
```

## Shared Environment

Install once from the repo root:

```bash
uv pip install -r requirements.txt   # or: pip install -r requirements.txt
```

Python ≥ 3.11 recommended. Core deps: `pandas`, `numpy`, `matplotlib`, `scipy`, `statsmodels`.
