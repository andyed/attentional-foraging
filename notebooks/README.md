# Notebooks — AdSERP Analysis

Analysis notebooks for the AdSERP eye-tracking dataset (2,776 trials, 150Hz gaze + mouse + pupil). Each notebook is a self-contained investigation of one aspect of SERP examination behavior.

## Dataset

**Source:** [Latifzadeh, Gwizdka & Leiva, SIGIR 2025](https://github.com/kayhan-latifzadeh/AdSERP) — forced-choice web search task with 11 results per SERP.

**Location:** `../AdSERP/data/`

### Per-trial files (keyed by `p{participant}-b{block}-t{trial}`)

| Directory | Columns | Description |
| --- | --- | --- |
| `fixation-data/*.csv` | `timestamp, FPOGX, FPOGY, FPOGD` | Fixation point-of-gaze (x, y in px, duration in ms) |
| `mouse-movement-data/*.csv` | `timestamp, xpos, ypos, event, xpath` | Mouse events with DOM xpath |
| `pupil-data/*.csv` | `timestamp, BPOGX, BPOGY, LPD, LPV, RPD, RPV` | Binocular POG + left/right pupil diameter + validity |
| `serps/*.html` | — | Full HTML snapshot of the rendered SERP |
| `ad-boundary-data/*.json` | `native_ad, dd_top, dd_right` | Ad element positions and sizes |
| `trial-metadata/*.xml` | — | Task description, query, timestamps, participant info |
| `fixation-coords/*.json` | — | Per-fixation x,y mapped to result positions |
| `fixation-pupil/*.json` | — | Fixations joined with pupil diameter |

### Derived/aggregated files

| File | Description |
| --- | --- |
| `interesting-trials.json` | Curated trials tagged by behavior pattern (prototypical examples per tag) |
| `butterworth-lfhf-by-position.json` | LF/HF ratio per SERP position (Butterworth decomposition) |
| `trial-lhipa.json` | LHIPA (Low/High Index of Pupillary Activity) per trial |
| `serp-difficulty-measures.json` | Per-SERP difficulty metrics |
| `query-embeddings.json` / `serp-embeddings.json` | Semantic embeddings for query and SERP content |
| `saliency/` | Per-trial visual saliency values from Scrutinizer's export pipeline |
| `resource-cache/` | Cached intermediate computations |

### Trial naming convention

`p{NNN}-b{N}-t{N}` — participant, block, trial. 2,776 total trials across the dataset.

## Notebooks

### Behavioral decomposition

| Notebook | What it investigates |
| --- | --- |
| `orientation_evaluation.ipynb` | OSEC phase decomposition (Orient → Survey → Evaluate → Commit). Phase transitions, timing, pupil LF/HF per phase. |
| `regression_decisions.ipynb` | Regressions — revisits to previously evaluated results before committing. 69% of trials include regressions. |
| `convergence_analysis.ipynb` | How gaze, cursor, and pupil signals converge on the eventual click target. |

### Mouse & cursor behavior

| Notebook | What it investigates |
| --- | --- |
| `gaze_cursor_lag.ipynb` | Temporal lag between gaze fixation and cursor movement to the same result. |
| `scroll_kinematics.ipynb` | Scroll velocity, acceleration, and ballistic patterns during SERP examination. |
| `scroll_regressions.ipynb` | Upward scrolls (regressions) — frequency, distance, relationship to evaluation depth. |

### Pupil & cognitive load

| Notebook | What it investigates |
| --- | --- |
| `lhipa_validation.ipynb` | LHIPA validation on AdSERP: satisficers vs optimizers, per-trial cognitive load. |

### Individual differences & SERP properties

| Notebook | What it investigates |
| --- | --- |
| `individual_differences.ipynb` | User strategy clusters — scanning speed, regression frequency, evaluation depth. |
| `user_strategies.ipynb` | Strategy classification: exhaustive vs satisficing vs focused. |
| `serp_difficulty.ipynb` | What makes a SERP hard? Semantic similarity, result quality variance, ad density. |
| `serp_priming.ipynb` | Lexical overlap between results — does token repetition speed evaluation? |

### Predictive signals

| Notebook | What it investigates |
| --- | --- |
| `early_predictors.ipynb` | Which signals predict the eventual click before it happens? |
| `fixation_coverage.ipynb` | How much of the SERP gets fixated, and what gets skipped? |

## Loading data

All notebooks use polars. Standard pattern:

```python
import polars as pl
from pathlib import Path

DATA = Path("../AdSERP/data")

# Load one trial's fixations
fix = pl.read_csv(DATA / "fixation-data" / "p004-b1-t1.csv")

# Load all fixation files
fixation_files = sorted((DATA / "fixation-data").glob("p*.csv"))
all_fix = pl.concat([
    pl.read_csv(f).with_columns(pl.lit(f.stem).alias("trial_id"))
    for f in fixation_files
])

# Load derived data
import json
lhipa = json.loads((DATA / "trial-lhipa.json").read_text())
interesting = json.loads((DATA / "interesting-trials.json").read_text())
```

## Output

Notebooks save plots as `plot_*.png` in this directory. These are referenced by the main README and docs.

## Dependencies

```
polars
matplotlib
seaborn
scipy
numpy
scikit-learn
```

Install: `uv pip install polars matplotlib seaborn scipy numpy scikit-learn`
