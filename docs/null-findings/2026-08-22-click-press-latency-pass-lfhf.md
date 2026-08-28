# Click press duration does not distinguish first-forward from regressive-return clicks

**2026-08-22.** `[LAB, AdSERP, typed_gapfill]`

## TL;DR

AdSERP's evtrack stream does support same-target `mousedown`/`mouseup`
pairing, but the resulting **button-hold duration is not detectably different**
when a click follows the target's first forward encounter versus a regressive
return. Raw medians were 103 vs 110 ms; after participant clustering, the
median within-participant difference was +2.5 ms (95% bootstrap CI −7 to +7,
paired Wilcoxon *p* = .886). A covariate-adjusted participant-demeaned model
estimated +1.9% for regressive returns (95% cluster-bootstrap CI −3.0% to
+7.5%). Fixed-window pre-press LF/HF was likewise null. The one corrected
exploratory association was motoric: more cursor travel in the preceding 500
ms accompanied a shorter button hold.

## What was run

Producer: [`scripts/click_press_latency_pass_analysis.py`](../../scripts/click_press_latency_pass_analysis.py)

The terminal click was paired backward to the nearest preceding same-XPath
`mouseup`, then to the nearest preceding same-XPath `mousedown`. This matters
because the corpus's synthesized `click` row is delayed after `mouseup`; gaze
state and physiological windows are therefore anchored to `mousedown`, not
the click timestamp. Press duration is `mouseup − mousedown`.

The clicked result was attributed with the current `typed_gapfill` X+Y AOI
path. Its latest gaze episode before `mousedown` was classified as:

- **first-forward:** first encounter with the clicked target while at or
  advancing the rank high-water mark;
- **regressive-return:** revisit to an already-seen clicked target below the
  rank high-water mark.

Only gaze at or before `mousedown` enters the classifier. Backfilled first
looks, repeated frontier looks, target looks more than 1.5 s old, off-main-axis
clicks, and holds over 1 s are excluded from the primary comparison.

LF/HF uses exactly 150, 300, or 450 pupil samples ending at `mousedown`
(nominally 1, 2, or 3 s). The pupil stream is truncated at `mousedown` before
zero-phase filtering, so post-press samples cannot leak backward. The 300-
sample/2-s version is primary. This fixed-sample design avoids the known LF/HF
window-duration confound documented in
[`lfhf-window-duration-confound.md`](lfhf-window-duration-confound.md).

## Numbers

### Sample flow

- 2,342 main-axis clicks had a paired press and a pre-press target fixation.
- Before primary filters: 1,634 regressive-return, 350 first-forward, 301
  repeated-frontier, and 57 backfilled-first labels.
- Primary sample: **1,592 clicks from 47 participants** — 232 first-forward and
  1,360 regressive-return.
- 229 terminal clicks were off the main axis; 203 had no pre-press target
  fixation; 476 target fixations were older than 1.5 s; 17 holds exceeded 1 s.

### Press-duration contrast

| analysis | estimate | uncertainty / test |
|---|---:|---:|
| raw median, first-forward | 103 ms | IQR 85–133 ms |
| raw median, regressive-return | 110 ms | IQR 85–142 ms |
| median participant difference, regressive − forward | +2.5 ms | bootstrap 95% CI [−7, +7]; Wilcoxon *p* = .886; 43 paired participants |
| participant-demeaned log model, unadjusted | +0.7% | bootstrap 95% CI [−4.0%, +5.3%] |
| participant-demeaned log model, adjusted | +1.9% | bootstrap 95% CI [−3.0%, +7.5%] |

The adjusted model includes clicked rank, decision time, target-fixation
recency, pre-press cursor speed, and down/up displacement. All six threshold
combinations (target recency 0.5/1.0/1.5 s × max hold 0.5/1.0 s) remain null;
participant-median differences range from +1.0 to +3.75 ms and every
Wilcoxon *p* is at least .626.

### By display rank

These are 1-based `typed_gapfill` **display ranks** (ads/widgets included),
not organic-only ranks.

| rank | first n / median ms | regressive n / median ms | raw Δ ms | paired participants | participant median Δ ms | paired *p* |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 48 / 98 | 401 / 110 | +12 | 13 | −1.0 | .485 |
| 2 | 42 / 102 | 436 / 116 | +14 | 18 | +2.2 | .777 |
| 3 | 27 / 117 | 165 / 110 | −7 | 13 | −3.5 | .698 |
| 4 | 29 / 94 | 142 / 117.5 | +23.5 | 15 | −6.0 | .158 |
| 5 | 30 / 95 | 119 / 110 | +15 | 17 | +2.5 | .570 |
| 6 | 19 / 118 | 36 / 98.5 | −19.5 | 6 | −6.0 | .844 |
| 7 | 14 / 108 | 18 / 78 | −30 | 5 | −24.0 | .438 |

The raw sign flips across ranks and none of the participant-paired rank cells
is significant. In a participant-demeaned log-duration model on ranks 1–7,
the rank × pass interaction is **+0.38% per rank**, cluster-bootstrap 95% CI
[−1.72%, +2.38%]. Thus there is no evidence that rank moderates the
forward/regressive contrast. Ranks 8+ contain fewer than ten first-forward
clicks per cell and are retained only as descriptives in `summary.json`.

### Press duration × physiology

| feature | n | pooled Spearman ρ | median within-participant ρ | participant *p* | BH-FDR *q* |
|---|---:|---:|---:|---:|---:|
| pre-press LF/HF, fixed 1 s | 1,576 | +.017 | +.008 | .931 | .964 |
| pre-press LF/HF, fixed 2 s (primary) | 1,560 | +.037 | −.011 | .323 | .586 |
| pre-press LF/HF, fixed 3 s | 1,531 | +.050 | −.021 | .495 | .718 |
| pre-press RIPA2, fixed 2 s | 1,560 | −.067 | −.082 | .046 | .297 |
| trial LHIPA | 1,576 | −.161 | +.018 | .721 | .836 |

The uncorrected RIPA2 result does not survive the 29-feature exploratory FDR
family. Fixed-window LF/HF is null both overall and when first-forward and
regressive-return clicks are tested separately.

For audit only, the old whole-target LF/HF value has median within-participant
ρ = +.041 with press duration. Its LF/HF value correlates with its own window
sample count at median within-participant ρ = +.325 (*p* = 2.3 × 10⁻¹²), so it
is not used as physiological evidence here.

### Exploratory correlates

Pre-press cursor travel rate was the only BH-FDR-surviving feature: pooled
ρ = −.290, median within-participant ρ = −.262, participant *p* = 7.1 ×
10⁻¹¹, *q* = 2.1 × 10⁻⁹. This is best read as a motor-vigor association.
Clicked rank, decision time, regression depth, target dwell/visit count,
gaze–cursor distance, scroll retreat, SERP relevance spread/Jaccard/
distinctiveness, approach/retreat geometry, pupil mean/slope, RIPA2, LHIPA,
and all LF/HF variants do not survive FDR.

## Why this is a null

The 7-ms pooled median gap is a composition effect, not a participant-stable
pass effect. Only 232 primary clicks are first-forward, participants contribute
unequally to the two classes, and the pooled estimate disappears under both a
paired participant summary and participant-demeaned regression. The confidence
intervals also bound the likely effect to a small fraction of a typical
~100-ms button hold.

LF/HF fails under the leakage-safe, fixed-sample window that is appropriate
for this question. The positive whole-target LF/HF/sample-count relationship
reproduces why unequal AOI windows cannot rescue the hypothesis.

### Conditional surface exception

A theoretically motivated follow-up does identify a surface-specific
interaction without overturning the marginal null. With participant and exact
display-rank control, regressive `dd_top` clicks have 7.1% shorter holds and
the pass × `dd_top` contrast relative to organic is −9.8% (95% CI [−17.2%,
−2.3%], cluster-bootstrap *p* = .009), robust across six thresholds. It is
absent for `native_ad`. The existing pre-decision ad-utility segmentation is
directionally suggestive but its continuous interaction remains uncertain.
See [`../click-press-ad-moderation.md`](../click-press-ad-moderation.md).

## What was learned anyway

`mousedown`→`mouseup` is usable as a clean **press-duration** variable, but it
should not be called end-to-end decision latency. The delayed `click` row is
unsuitable as the cognitive-state anchor. The target-episode classifier yields
a large regressive-return population and can support other time-locked motor
analyses, while the current result says that the physical button hold itself
does not carry the forward/regressive distinction.

AdSERP also has no correctness ground truth. Click rank and SERP difficulty can
be analyzed as outcomes or covariates, but this dataset cannot provide the
requested accuracy correlation without importing an external relevance label.

A semantic follow-up reaches the same boundary more directly: query→clicked
embedding distance and clicked-versus-best-viewed tie-closeness do not explain
regressive press duration. A stable but unconfirmed first-forward competitive-
disadvantage pattern is documented in
[`2026-08-22-click-press-semantic-margin.md`](2026-08-22-click-press-semantic-margin.md).

## Reproduce and outputs

```bash
.venv/bin/python scripts/click_press_latency_pass_analysis.py
```

Generated outputs (gitignored) are in
`scripts/output/click_press_latency_pass/`: per-click CSV, full JSON summary,
Markdown report, and a two-panel PNG.
