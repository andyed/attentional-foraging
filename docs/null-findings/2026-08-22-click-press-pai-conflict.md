# Peripheral-attention weighting does not explain click press duration

**2026-08-22.** `[LAB, AdSERP, typed_gapfill]`

## TL;DR

Weighting semantic competition by strictly peripheral PAI does not strengthen
the forward-versus-regressive click-hold lead. In a fixed 1 s window ending at
`mousedown`, the pass × PAI-weighted semantic-conflict interaction is **+1.15%
per SD** (95% participant-cluster bootstrap CI **−3.44% to +6.58%**, raw *p* =
.569). A text-free PAI competition measure across organic, `dd_top`,
`native_ad`, and widget AOIs is also flat: **−0.21%** (CI **−4.78% to +5.69%**,
*p* = .953). Both primary Holm-adjusted *p* values are 1.0. The earlier
unweighted semantic-disadvantage lead remains visible after PAI adjustment;
peripheral attention mass neither amplifies nor explains it.

## What was run

Producer:
[`scripts/click_press_pai_conflict_analysis.py`](../../scripts/click_press_pai_conflict_analysis.py)

The analysis starts from the 1,592 primary same-XPath
`mousedown`→`mouseup` pairs defined by
[`click_press_latency_pass_analysis.py`](../../scripts/click_press_latency_pass_analysis.py).
All gaze evidence is truncated at `mousedown`. The primary exposure interval is
the same 1,000 ms for every click; a 2,000 ms window is a sensitivity. Fixation
duration is clipped to its actual overlap with the interval.

PAI uses each `typed_gapfill` AOI's full page-space rectangle:

`alpha = clip(1 − sqrt(OGD / max(CGD, 1)) × w_A, 0, 1)`, with
`w_A = (Amax / A)^(phi^3)`.

Only mass with exact rectangle-boundary distance `OGD > 0` counts as PAI.
Strict in-rectangle (`OGD = 0`) fixation dwell is retained as a separate model
covariate. This follows the PAI exposure ablation: peripheral PAI complements
binary dwell; it does not replace it. Within each fixed window, PAI mass is
normalized to shares across candidate AOIs rather than interpreted as raw
accumulation time.

Two primary pass interactions form one Holm-corrected family:

1. **PAI-weighted semantic conflict, organic clicks:** sum over every nonclicked
   joinable organic candidate of `peripheral PAI share × max(0, candidate query
   cosine − clicked query cosine)`. The model also includes the unweighted
   best-candidate semantic disadvantage, clicked-target PAI share, and
   clicked-target strict binary-dwell share.
2. **Geometry-only PAI competition, all surfaces:** strongest nonclicked AOI
   PAI share minus clicked AOI PAI share. The model includes distinct organic,
   `dd_top`, `native_ad`, and pooled-widget surface effects and all pass ×
   surface terms, plus clicked-target PAI and binary-dwell shares.

Both log-duration models use participant fixed effects, categorical
`typed_gapfill` display-rank effects, log decision time, target-fixation
recency, and log pre-press cursor speed. Inference uses 5,000 participant-
cluster bootstrap resamples.

## Numbers

### Sample flow

- **1,578 / 1,592 clicks** have positive strictly peripheral PAI mass in the
  primary 1 s window: 231 first-forward and 1,347 regressive-return, across all
  47 participants.
- Exclusions are 12 zero-peripheral-mass windows and two windows with no
  overlapping fixation. Fifteen retained clicks have no strict in-AOI dwell;
  the model includes an explicit no-binary-dwell indicator.
- Surface counts are 1,220 organic, 223 `dd_top`, 81 `native_ad`, and 54 pooled
  widget clicks.
- The semantic model has **1,196 organic clicks**: 160 first-forward and 1,036
  regressive-return. PAI semantic conflict is exactly zero for 453 of these
  clicks, as it should be when no semantically better alternative receives
  peripheral mass.

### Primary interactions

Effects are percent change in button-hold duration per 1-SD increase in the PAI
feature.

| test | pass × PAI feature | bootstrap 95% CI | raw *p* | Holm *p* | first-forward slope | regressive slope |
|---|---:|---:|---:|---:|---:|---:|
| semantic conflict | +1.15% | [−3.44%, +6.58%] | .569 | 1.000 | −1.15% [−5.34%, +3.25%] | −0.01% [−2.04%, +2.13%] |
| geometry competition | −0.21% | [−4.78%, +5.69%] | .953 | 1.000 | −0.88% [−5.64%, +3.53%] | −1.09% [−4.09%, +2.02%] |

The semantic interaction changes sign in one of 47 leave-one-participant-out
fits and ranges from −0.73% to +2.09%. The geometry interaction is also weakly
stable at best: 34/47 leave-one-out fits retain its negative sign, spanning
−1.79% to +0.67%.

The unweighted all-candidate semantic-disadvantage interaction remains
directionally consistent in the joint model: **−4.25%**, CI [−10.78%, +0.35%],
raw *p* = .065. Its first-forward slope is +5.23%, CI [+0.83%, +12.57%], while
the regressive slope is approximately +0.76%. This is the same unconfirmed
competitive-mismatch lead documented in the parent semantic analysis, not a
new PAI result.

### PAI sensitivities

| PAI specification | semantic interaction | geometry interaction |
|---|---:|---:|
| 2,000 ms, exact formula | +2.12% [−2.75%, +7.09%], *p* = .391 | −0.07% [−3.67%, +4.74%], *p* = .972 |
| 1,000 ms, NB35 linear form | +3.01% [−2.72%, +9.86%], *p* = .284 | −0.46% [−5.93%, +5.75%], *p* = .854 |

Changing the exposure horizon or PAI functional form does not reveal the
proposed moderation.

### Does PAI explain the top-ad lead?

On the same 1,578-click PAI-complete subset and with the same shared controls,
the pass × `dd_top` contrast is −6.77% before PAI terms (CI −14.62% to +0.67%,
*p* = .083) and −6.34% after adding PAI competition and clicked-target PAI/
dwell terms (CI −13.85% to +0.53%, *p* = .070). The point estimate attenuates
by only 0.43 percentage points. This mechanism check is less powered and more
controlled than the original surface model, so it does not replace that
result; it says the top-ad lead is not accounted for by this peripheral PAI
competition measure.

## Why this is a null

Both primary interaction estimates sit near zero, both intervals cover effects
in either direction, and the null is stable across two reasonable PAI
sensitivities. Neither pass-specific slope suggests that peripheral PAI
competition changes hold duration within first-forward or regressive clicks.
The result is not caused by substituting PAI for conventional fixation
evidence: clicked-target strict dwell is present in both models as a separate
control.

PAI is still an exposure proxy, not proof that a peripheral alternative was
consciously evaluated. The semantic calculation covers organic result text
only because there is no equivalent defensible text embedding join for
`dd_top` and `native_ad`. The geometry analysis covers those surfaces but does
not encode their content or utility.

## What was learned anyway

The semantic lead does **not** generalize by simply multiplying better-
alternative advantage by pre-press peripheral attention mass. The immediate
gaze-sequence follow-up is now also complete and null: neither a final better-
alternative→target transition nor a strict target→better→target chain explains
the hold. What remains worth replicating is the simpler presence of a better
alternative during a first-forward choice, without claiming a PAI or sequence
mechanism.

The top-ad hold compression also appears unlikely to be a generic peripheral
competition effect. Surface affordance, utility, or a direct-display commit
mode remain more plausible candidates than PAI geometry in this dataset.

## Pointers

- Generated per-click records, JSON summary, report, and coefficient plot:
  `scripts/output/click_press_pai_conflict/` (gitignored)
- Parent semantic analysis:
  [`2026-08-22-click-press-semantic-margin.md`](2026-08-22-click-press-semantic-margin.md)
- Temporal sequence follow-up:
  [`2026-08-22-click-press-semantic-sequence.md`](2026-08-22-click-press-semantic-sequence.md)
- Surface-specific result:
  [`../click-press-ad-moderation.md`](../click-press-ad-moderation.md)
- PAI validation and formula provenance:
  [`../ablations/pai_exposure_validation.md`](../ablations/pai_exposure_validation.md)

## Reproduce

```bash
.venv/bin/python scripts/click_press_latency_pass_analysis.py
.venv/bin/python scripts/click_press_semantic_margin_analysis.py
.venv/bin/python scripts/click_press_pai_conflict_analysis.py
```
