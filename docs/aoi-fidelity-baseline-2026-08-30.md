# AOI fidelity baseline — v1.1.0 substrate, 2026-08-30

> **The `aoi` figures in the original table below are VOID.** That check
> resolved cards by `css_path`, which is itself unreliable, so it measured the
> harness on the failing tail. The check was rewritten to resolve by
> class+heading identity and re-run; corrected numbers are in the final section.
> `click` and `cell` never used `css_path` and are unchanged.

First full-corpus run of `scripts/aoi_fidelity.py`. This is the number every
later change is measured against; before it there was no measurement of the
substrate that could fail.

Substrate: `allserp-v1.1.0` as shipped (no fixes applied). 2,776 trials.

| check | score |
|---|--:|
| **click** — recorded coordinate inside the element its own xpath names | **2,434 / 2,775 (87.7 %)** |
| **aoi** — stored box vs the DOM element it claims (IoU) | median **0.879**, p10 0.428, p90 0.917 |
| **aoi** — IoU >= 0.5 | **2,416 / 2,776 (87.0 %)** |
| **cell** — visible DOM carousel cells vs the cellsplit export | **agree 451 / 1,551 (29.1 %)** |

## What the distribution says

**The AOI layer fails on a minority, hard.** 181 trials sit below IoU 0.2 and a
further 179 between 0.2 and 0.5 — 13 % of the corpus materially misaligned,
while the other 87 % sit around 0.88. This is not gradual drift; it is a clean
bimodal split between trials where extraction worked and trials where it
collapsed. The worst are 0.000: `p004-b1-t10`, `p004-b1-t5`, `p004-b2-t2`,
`p004-b4-t6`, `p004-b5-t2`, `p004-b6-t3` and others, where AOIs kept their
`html_handle` but inherited a neighbour's geometry after a dropped card.

**The cell layer is the worst by a wide margin.** Agreement is 29.1 %, the
export is short on 902 trials, and the median shortfall is **exactly 1 cell** —
the trailing-drop, corpus-wide. 1,551 trials carry a comparable carousel, which
matches the paper's independently stated 1,550 that subdivide, so the
denominator is right and the disagreement is real.

**The checks are related but not redundant.** Trials failing the AOI check fail
the click check 45 % of the time, against 7 % for trials passing it. Two
distinct defects with a shared cause; either alone would have missed cases the
other catches, which is the argument for keeping three scores rather than one
composite.

## What this baseline should move

| change | expected to move |
|---|---|
| `fix/aoi-card-collision` | **aoi** — the 360 low-IoU trials are collision/renumbering casualties |
| `fix/coordinate-space-loader`, wired into consumers | **click** — 87.7 % should approach the 96 % measured on converted clicks |
| DOM-derived cells replacing the frozen snapshot | **cell** — 29.1 % is the number to beat |

If a change does not move its score, it did not do what it claimed.

## Caveats

- The click check renders at viewport 1389 to reproduce the recorded document
  width. That is not the original capture environment (Chrome 110 / Windows,
  2023), so a residual mismatch is expected and 100 % is not the target.
- 341 clicks resolve no element at all (xpath no longer matches the saved DOM);
  they are excluded rather than counted as failures.
- IoU is computed only where an AOI carries an `html_handle` that resolves.
  Orphaned AOIs (`position: -1`) contribute nothing, so the AOI score
  *understates* damage on trials that dropped cards entirely.


---

## Corrected baseline (identity resolution) and accuracy statement

Re-run on the shipped v1.1.0 substrate after rewriting the `aoi` check:

| check | void v1 (css_path) | **corrected** |
|---|--:|--:|
| click | 87.7 % | **87.7 %** (unchanged — never used css_path) |
| aoi median IoU | 0.879 | **0.881** |
| aoi p10 | 0.428 | **0.853** |
| aoi IoU >= 0.5 | 87.0 % | **93.4 %** (2,593 / 2,776) |
| cell | 29.1 % | **29.1 %** (unchanged) |

The p10 is the informative line: 0.428 -> 0.853. The "catastrophic tail" that
drove a day of diagnosis was almost entirely the harness's own selector, not the
data. 183 trials remain below 0.5 and are not yet explained.

## Best estimate of substrate accuracy, and the delta from this morning

| quantity | before | after | where the change came from |
|---|--:|--:|---|
| click -> AOI attribution | 78.0 % | **96.2 %** | coordinate conversion (merged) |
| cursor -> AOI mean distance | 57.3 px | **37.5 px** | same |
| cursor vertical bias | +8.5 px | **+0.4 px** | same |
| cards duplicating another's box | 508 | **0** | collision fix (NOT merged) |
| orphaned main-column results | 480 trials | **167** | collision fix (NOT merged) |
| AOI box vs DOM identity (IoU >= 0.5) | 93.4 % | 93.4 % | unchanged; was never as bad as reported |
| carousel cell counts | short on 902/1,551 | unchanged | not fixed |
| **fixation -> AOI attribution** | correct | **correct** | never affected |

**Read this carefully before quoting it.** The largest number in the table is a
correction to what we *knew*, not to what changed. Fixation attribution — which
carries most of the published results — was always right. The gains are real but
land on the **mouse stream**: the cellsplit family,
`attribute_click_to_typed_gapfill`, and Leaky Cursor's `final_dist` /
`retreat_dist`. crforager's verdicts do not move (T1 L1 shifts 0.01 against a
0.20 gate).

Two rows above are on an unmerged branch (`fix/aoi-card-collision`), so the
shipped substrate still has 508 duplicate cards and 480 orphan trials.

The honest summary: **the substrate is in better shape than this morning, and
substantially better than the middle of the day suggested it was.** The worst
remaining layer is `cell` at 29.1 %, which is a real defect and unfixed.
