# First scroll vs gaze coverage — organic_hybrid

_Generated 2026-05-03 by `scripts/first_scroll_vs_gaze.py`._

## Question

When the user issues their first significant downward scroll, how much
of the above-fold consideration set have they fixated? Pre-emptive vs
post-evaluation scrolling.

## Cohort

- 2,719 trials with usable geometry
- **2,229 trials** had a first significant scroll (scroll_y > 100 px)
- **490 trials** committed without scrolling

## Coverage of above-fold set before first scroll

| stat | value |
|---|---|
| mean coverage | 0.562 |
| median coverage | 0.500 |
| p25 / p50 / p75 | 0.40 / 0.50 / 0.75 |
| fraction reaching last-visible position | 0.103 |

## Per-position: fraction of trials where this above-fold position was fixated before first scroll

| Pos | trials w/ P above fold | fraction fixated before scroll |
|---|---|---|
| P0 | 2,229 | 0.983 |
| P1 | 2,229 | 0.811 |
| P2 | 2,175 | 0.477 |
| P3 | 1,907 | 0.293 |
| P4 | 1,344 | 0.196 |
| P5 | 662 | 0.109 |
| P6 | 205 | 0.059 |

## Stratified by P0 etype (top of display order)

Hypothesis: a top-of-page ad (`dd_top`) at P0 invites pre-emptive scroll.

| P0 etype | n trials | median coverage | reached last visible | deepest median | P0 fixated |
|---|---|---|---|---|---|
| dd_top | 1,306 | 0.500 | 0.109 | 1 | 0.992 |
| image_pack | 75 | 0.500 | 0.080 | 1 | 1.000 |
| native_ad | 452 | 0.600 | 0.106 | 3 | 0.978 |
| organic | 376 | 0.571 | 0.074 | 2 | 0.984 |
| other_widget | 8 | 0.500 | 0.250 | 2 | 1.000 |
| unknown | 12 | 0.367 | 0.333 | 2 | 0.000 |