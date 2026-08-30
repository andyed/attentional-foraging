# What actually breaks the AOI score: handle drift, not geometry (2026-08-30)

The fidelity baseline put 13 % of trials below IoU 0.5 on the `aoi` check. This
diagnoses them. The answer is not what the roadmap assumed, and the collision
fix — while correct — is not the remedy.

## The collision fix moves it only a little

`fix/aoi-card-collision` scored against the baseline, full corpus:

| check | v1.1.0 | collision-fixed |
|---|--:|--:|
| click | 87.7 % | 87.7 % (unchanged, as expected) |
| aoi median IoU | 0.879 | 0.878 |
| aoi p10 | 0.428 | **0.460** |
| aoi IoU >= 0.5 | 87.0 % | **89.3 %** (+62 trials) |
| cell | 29.1 % | 29.1 % (unchanged, as expected) |

122 trials improved by >0.05, 6 got worse, **297 remain below 0.5**. The roadmap
claimed the 360 low-IoU trials were collision casualties. They are mostly not:
the fix rescues 62 of them. That `click` and `cell` did not move is a good sign
for the harness — a change to AOI extraction moved only the AOI score.

## The remaining failures are one defect, not two

Across the 298 still-broken trials, 1,984 AOIs fail against their own
`html_handle`. Splitting them by whether the geometry matches *some* DOM card:

| | n | share |
|---|--:|--:|
| geometry matches a **different** DOM card | 770 | 38.8 % |
| geometry matches **nothing** at IoU >= 0.5 | 1,214 | 61.2 % |

That split looked like two problems. It is one. Among the 770, the handle offset
is **-1 in 677 cases (88 %)**, -2 in 74, -3 in 12. Among the 1,214, the best
achievable IoU is a median of **0.362** (only 146 are truly 0), AOI height is
**0.92x** the DOM element's, and the vertical centre offset is a median of
**-42 px = -0.45 card heights**, with 368 of 584 measured between 0.25 and 0.75
cards and 210 beyond 0.75.

So the AOI sequence drifts **upward** relative to the handle sequence. Where the
drift exceeds roughly three quarters of a card it lands cleanly on the previous
card and reads as a -1 mislabel; where it is around half a card it straddles two
cards and matches neither. Same defect, sampled at different magnitudes.

Worked case, `p004-b1-t10`, after the collision fix:

    AOI rso[5]  own-handle IoU 0.000  ->  matches DOM rso[4] at 0.902
    AOI rso[6]  own-handle IoU 0.000  ->  matches DOM rso[5] at 0.936
    AOI rso[8]  own-handle IoU 0.000  ->  matches DOM rso[6] at 0.855
    AOI rso[9]  own-handle IoU 0.000  ->  matches DOM rso[8] at 0.886

The geometry is excellent. The boxes are wearing the wrong names.

## Where it lives

Not in `measure_card_geometry.py`. That measures a card against its own
`css_path` and, after the collision fix, does so correctly. The drift is in
`build_typed_aoi_map.py`: the y-DP alignment pairs CV bboxes to HTML cards by
sequence position and cost, and after a dropped or unmatched card the pairing
slips. The output then takes `html_handle` from the card and `x`/`y` from the
bbox, so a slipped pair produces exactly this — right box, wrong identity.

This is the mechanism behind Al-Lawati's §3b downstream claim that "ranks below
the drop renumber". She was right about the consequence; the cause is the
pairing, not the geometry.

## The fix, and how to know it worked

Assign the handle from **which DOM element the bbox actually overlaps**, not
from DP sequence position. Every card already carries a `css_path`
(`data/aoi-html-types/<tid>.json`), so the correct handle is directly
resolvable rather than inferable. Use the DP only where no DOM element claims
the bbox.

Falsifiable prediction: the 122 trials scoring exactly 0.000 should move to
approximately 0.9, and `aoi` IoU >= 0.5 should exceed 95 %. If it does not, this
diagnosis is wrong.

## What this changes about the roadmap

Phase 2 (DOM-derived cells) is not the next bet, and neither was the collision
fix. Both are worth having. But the AOI score is dominated by handle assignment,
and that is the same lesson as Phase 2 in a different place: **the pipeline
infers by sequence and geometry what the saved HTML states outright.** Cells
have numbered ids; cards have css_paths. Reading them is cheaper and correct.
