# Attentional Foraging in Search: Initial Sampling and Recurrent Evaluation

How do people sample a search page, evaluate a result, return to something
already seen, and decide where to go? This project studies that process through
synchronized gaze, cursor, scroll and pupil recordings from
[AdSERP](https://github.com/kayhan-latifzadeh/AdSERP), with
[AllSERP](https://arxiv.org/abs/2605.04949) supplying typed areas of interest
(AOIs) for the page's results, ads and widgets.

**Repository scope:** attentional-foraging characterizes the search cognitive
process and hosts the LAB analysis substrate. Click modeling is developed in
[approach-retreat](https://github.com/andyed/approach-retreat), which validates
against the claims recorded here.

Start with the [two linked posters](docs/visualizations/README.md), or the
[observed pause](#not-a-cascade) below. The
[construct-to-observable map](docs/foraging-constructs.md) connects the
foraging account to the measurements that can support or challenge it.

## Not a cascade

The cascade model of click position bias assumes that a searcher examines
results once, from the top, and stops at the first worthwhile one
([Craswell et al., WSDM 2008](https://doi.org/10.1145/1341531.1341545)).
Later click models relax that assumption with revisits
([Xu et al., WSDM 2012](https://doi.org/10.1145/2124295.2124334)),
non-sequential examination ([Wang et al., SIGIR 2015](https://doi.org/10.1145/2766462.2767712))
and comparison with adjacent results ([Zhang et al., WWW 2021](https://doi.org/10.1145/3442381.3449918)).
The recordings here show the loops directly: a result is fixated, left and
fixated again, and the cursor can stay on one result while the eyes visit others.

[![During a four-second cursor pause on AOI 1, gaze visits AOIs 3, 2, 3 and 1. Gaps with no fixation are shown separately.](docs/visualizations/gaze-cursor-echo/pause.png)](docs/visualizations/gaze-cursor-echo/poster.pdf)

This is one recorded interval from trial `p021-b1-t6`. A fixed rule chose it
from 63 cursor pauses of 2–8 s that contain at least three gaze AOIs and a gaze
return, so it shows the pattern rather than a typical pause. The aggregates
below say how common each part of it is. **[LAB, AdSERP, typed]**

- **First visits often end with a move back.** In the separate first-visit
  analysis, a move to an earlier position ends 50–57% of first visits at
  positions 2–10, and 75–92% of those moves land on a result already visited,
  depending on position. Positions include ads and widgets, and fixations are
  assigned to positions by vertical band. These are per-position shares, not
  shares of trials. **[LAB, AdSERP, typed, NB38:K8]**
  [First-visit evidence, 2,606 trials](docs/ablations/next_action_by_position.md)
- **Gaze changes results more often than the cursor.** During time covered by
  both signals, gaze makes 2.84× as many AOI changes (95% CI 2.43–3.36) and
  3.38× as many backward steps (2.80–4.14), with one visit definition for both
  channels. The ratio depends on the minimum visit duration: on the full clock
  it is 2.97 at 100 ms and 1.76 at 200 ms. **[LAB, AdSERP, typed; poster producer]**
  [Common-coverage evidence, 2,650 trials](docs/visualizations/gaze-cursor-echo/checks.json)
- **The eyes often move on while the cursor rests.** During 23.8% (22.2–25.2)
  of the time the cursor rests inside an AOI, a recorded fixation is on a
  different AOI; among rest time with a matched fixation the share is 35.6%
  (33.3–37.7). The logger records the cursor only when it moves, and a position
  is held for at most 2 s, so stillness beyond 2 s falls outside this measure.
  **[LAB, AdSERP, typed; poster producer]**
  [Definition and denominators](docs/visualizations/gaze-cursor-echo/methods.md)

Revisiting is consistent with comparison and re-evaluation. A fixation alone
cannot establish what was understood, remembered or preferred. “Not a cascade”
describes the observed examination sequence; it does not assume that every
searcher uses the same strategy. [Full account and limits](docs/not-a-cascade.md)

<a id="the-task-model"></a>
<a id="two-decisions-three-channels-five-states"></a>
## Initial sampling and recurrent evaluation

The opening of a trial establishes where examination begins and how broadly
the eyes move. Subsequent evaluation includes local reading, forward moves,
returns, pauses and longer excursions before the final action. The research
question is how these activities are organized and coordinated across gaze,
cursor and scroll. Their timing need not follow a fixed sequence of stages.

| Process | Observable evidence | Interpretation to investigate |
| --- | --- | --- |
| Initial sampling | Initial fixation locations, saccade amplitudes, visible page area | Establishing where useful material might be |
| Local examination | Fixation sequences and dwell within a result | Reading and assessing the result |
| Recurrent examination | Re-entry into an earlier AOI; excursion and return geometry | Comparison, checking or memory-guided reinspection |
| Commitment | Final approach and physical press, aligned with gaze | The transition from examination to action |

These are functional descriptions of observable activity, and more than one
can be under way at the same time. Gaze, cursor and scroll provide different
observations of the process. Pupil measures add an effort-related signal;
none of them directly reports a person's reason for returning.

AdSERP requires a result selection. It supports analysis of examination and
commitment within that task; it cannot establish when people naturally abandon
a page, reformulate a query, or decide that further search is not worthwhile.
The wider foraging account needs those stopping decisions too.

## Two posters, from time budgets to individual excursions

**[One clock, many views](docs/visualizations/information-space-poster/index.html)**
([PDF](docs/visualizations/information-space-poster/poster.pdf)) partitions
recorded time by AOI membership, initial fold, motion and gaze–cursor location.
The aggregate views lead into a shared timeline, an observed trial and its
final seconds. Each view names its denominator. The spatial views keep
unavailable time in the denominator; the motion view conditions it out and
states the classifiable share.

**[While the mouse waits, the eyes travel](docs/visualizations/gaze-cursor-echo/index.html)**
([PDF](docs/visualizations/gaze-cursor-echo/poster.pdf)) links first-entry timing,
rank changes and cursor rest to a whole trial and a four-second pause. Gaze
enters jointly visited results first in 66.5% of trial–AOIs, but nearby matched
visits have little median lag. The cursor's sparser path is not sufficient to
establish that it is a delayed copy of gaze. **[LAB, AdSERP, typed]**

Both posters use the same 2,650-trial, 47-participant cohort and clock, from
first native mousemove to final press. The [atlas guide](docs/visualizations/README.md)
includes static exports, source values, measurement notes and rebuild commands.
The HTML views work locally; GitHub's file viewer does not render them as pages.

<a id="key-insights"></a>
## Evidence

- [First visits and the next action](docs/ablations/next_action_by_position.md):
  when attention stays, advances, moves back, or leaves the result column.
- [Return geometry and memory](docs/ablations/return_is_memory.md): the evidence
  for a memory-guided interpretation, including precision and approach geometry.
- [First fixations on ad-topped pages](docs/ablations/survey_above_fold.md):
  where the first five fixations land when advertising tops the page.
- [Peripheral exposure](docs/ablations/engagement_state_census.md): distinguish
  being on screen, receiving nearby gaze exposure and receiving a fixation.
- [Null findings](docs/null-findings/README.md): hypotheses that did not survive,
  including the lexical-priming account of declining dwell.

<a id="dataset"></a>
<a id="notebooks"></a>
<a id="reusable-components"></a>
<a id="figure-gallery"></a>
## Dataset and analysis

AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025;
[paper](https://doi.org/10.1145/3726302.3730325), [Zenodo](https://zenodo.org/records/15236546))
contains 2,776 trials from 47 participants, with eye tracking, mouse events,
scroll, pupil recordings and captured search pages. AllSERP adds per-element
geometry and types, so observations can be assigned to a result's box rather
than to a vertical band estimated from the page. Analysis cohorts vary with
signal availability and geometry exclusions.

Use the [canonical Python environment](docs/canonical-environment.md) and the
shared [data loader](notebooks-v2/data_loader.py). The [notebook guide](notebooks-v2/README.md),
[claim registry](docs/notebook-key-claims.md) and [methodology directory](docs/methodology/README.md)
provide the analysis and measurement definitions. The
[figure gallery](scripts/output/figures/INDEX.md) records other figures and their producers.

For individual trials, the [foveated replay](https://andyed.github.io/attentional-foraging/)
shows accumulated gaze on a perception-oriented background. The
[screenshot-based replay](https://andyed.github.io/approach-retreat/replay/)
uses original captured page geometry. The foveated version re-renders archived
HTML, so page layout can differ from the original capture.

<a id="quick-start--allserp-data-files"></a>
## Using the AllSERP data

AllSERP v1.1.1 ([release](https://github.com/andyed/attentional-foraging/releases/tag/allserp-v1.1.1),
[notes](docs/releases/allserp-v1.1.1.md)) ships corpus CSVs with one row per
AOI (geometry, element type and organic rank) as release assets and under
`scripts/output/`, and one typed map per trial under `data/aoi-typed-gapfill/`
and `data/aoi-typed/`. Existing AdSERP signal files join on `trial_id`. The
AdSERP corpus itself is not redistributed; download it from Zenodo.

```python
import json
import polars as pl

# One row per AOI: geometry, element type and organic rank (2,764 trials).
aois = pl.read_csv("scripts/output/adserp_aois_by_trial_id_typed_gapfill.csv")
print(aois.group_by("etype").len().sort("len", descending=True))

# Organic results whose top edge lies within the first screen (page coordinates).
first_screen = aois.filter(
    (pl.col("etype") == "organic") & (pl.col("top_y") < pl.col("screen_height")))
print(first_screen.height, "organic AOIs start on the first screen")

# One trial's typed map: a list of AOIs with type, box and main-column position.
# Position -1 marks elements outside the result column, such as pagination.
with open("data/aoi-typed-gapfill/p010-b2-t6.json") as f:
    trial = json.load(f)
print([(a["type"], a["position"], a["x"], a["y"], a["width"], a["height"])
       for a in trial if a["position"] >= 0])
```

`scripts/build_aois.py --trial p010-b2-t6` rebuilds one trial's map from the
AdSERP screenshot and HTML, and `--all` rebuilds the corpus. `--flavor` selects
`typed_gapfill` (the default), `typed` or `typed_gapfill_cellsplit`. Moving from
v1.1.0: [migration guide](docs/allserp-v1.1.0-migration.md).

<a id="paper"></a>
<a id="docs"></a>
<a id="citation"></a>
## Papers and provenance

- [AllSERP: Exhaustive Per-Element Enrichment of the Versatile AdSERP Dataset](https://arxiv.org/abs/2605.04949)
  and its [source repository](https://github.com/andyed/allserp-paper).
- [Earlier OSEC task-model draft](docs/arxiv/task-model-paper.pdf) — retained as
  a historical framing; its four-stage account is being reassessed.
- [Measurement threats and limitations](docs/methodological-threats.md),
  [references](references.bib), and [change history](CHANGELOG.md).
- [CITATION.cff](CITATION.cff) gives the AllSERP paper as the preferred citation
  and lists the AdSERP dataset paper; cite both when you use the data.

## License

Analysis code: MIT. Derived AllSERP data (the per-AOI corpus CSVs under `scripts/output/`, the per-trial typed maps under `data/aoi-typed*/`, and the exclusion list) and the derived poster evidence under `docs/visualizations/` are released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/), matching the AdSERP corpus licence; cite both (see `CITATION.cff`). The AdSERP dataset itself has its own [license](https://github.com/kayhan-latifzadeh/AdSERP/blob/main/LICENSE) and is not redistributed here.
