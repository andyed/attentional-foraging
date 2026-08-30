# AOI fidelity baseline — v1.1.0 substrate, 2026-08-30

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
