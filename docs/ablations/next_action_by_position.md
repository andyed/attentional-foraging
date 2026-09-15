# Given the first fixation on position p, what happens next — the stutter step in numbers

**Tags:** `[LAB, AdSERP, typed]` · positions 1–10 on the typed AOI map, all element types · 2,606 trials, 47 participants
**Producer:** `scripts/next_action_by_position.py` → `scripts/output/next_action_by_position/summary.json` (`--organic-only` writes `summary_organic.json`; see the caveat)
**Key Claims:** `[NB38:K7–K9]`
**Generated:** 2026-09-15. Quantitative companion to the idealized figure `scripts/output/figures/idealized_navigation.png` and to `render_result_moves.py`.

## Definitions

- **First entry** onto p: the first fixation assigned to typed position p in the trial. Every position is entered at most once here, so n falls with p as pages run out and gazes stop short.
- **First visit**: the run of consecutive fixations on p that the first entry starts.
- **Next action**: the position of the fixation that follows, as read on (same result), forward 1, forward 2+, back, off the result column (no typed AOI), or trial ends.
- **Clicked**: p is the trial's clicked result (census `was_clicked`).

## A. The fixation after the first entry

| pos | n | read on | forward 1 | forward 2+ | back | off results |
|---|---|---|---|---|---|---|
| 1 | 2,592 | 0.82 | 0.07 | 0.02 | 0.00 | 0.09 |
| 2 | 2,487 | 0.61 | 0.09 | 0.03 | 0.25 | 0.02 |
| 3 | 2,331 | 0.57 | 0.12 | 0.02 | 0.27 | 0.02 |
| 4 | 2,081 | 0.57 | 0.13 | 0.02 | 0.27 | 0.01 |
| 5 | 1,804 | 0.56 | 0.11 | 0.03 | 0.29 | 0.01 |
| 6 | 1,483 | 0.54 | 0.13 | 0.04 | 0.29 | 0.00 |
| 7 | 1,248 | 0.55 | 0.12 | 0.05 | 0.28 | 0.00 |
| 8 | 1,070 | 0.52 | 0.13 | 0.06 | 0.29 | 0.00 |
| 9 | 910 | 0.51 | 0.15 | 0.06 | 0.27 | 0.00 |
| 10 | 753 | 0.50 | 0.15 | 0.04 | 0.32 | 0.00 |

A first fixation on result 1 is followed by another on result 1 four times in five. From result 2 down the page the second fixation stays only 50–60 % of the time, and a quarter to a third of first entries are followed *immediately* by a move back up. Skipping ahead by two or more from a single fixation is rare (2–6 %).

## B. Where the first visit ends

| pos | n | forward 1 | forward 2+ | back | off results | P(clicked) | fixations / visit (median) | ms / visit (median) | back lands on a seen result |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2,592 | 0.46 | 0.10 | 0.00 | 0.44 | 0.20 | 4 | 745 | — |
| 2 | 2,487 | 0.32 | 0.07 | 0.55 | 0.06 | 0.26 | 2 | 415 | 0.92 |
| 3 | 2,331 | 0.35 | 0.06 | 0.55 | 0.03 | 0.16 | 2 | 423 | 0.89 |
| 4 | 2,081 | 0.38 | 0.06 | 0.53 | 0.03 | 0.16 | 2 | 415 | 0.85 |
| 5 | 1,804 | 0.34 | 0.07 | 0.57 | 0.02 | 0.18 | 2 | 428 | 0.82 |
| 6 | 1,483 | 0.37 | 0.09 | 0.53 | 0.01 | 0.09 | 2 | 408 | 0.85 |
| 7 | 1,248 | 0.36 | 0.12 | 0.51 | 0.01 | 0.07 | 2 | 415 | 0.82 |
| 8 | 1,070 | 0.36 | 0.13 | 0.51 | 0.00 | 0.05 | 2 | 368 | 0.80 |
| 9 | 910 | 0.36 | 0.13 | 0.50 | 0.00 | 0.06 | 2 | 401 | 0.76 |
| 10 | 753 | 0.38 | 0.11 | 0.51 | 0.00 | 0.03 | 1 | 348 | 0.75 |

Three regularities:

1. **From position 2 down, the modal end of a first visit is a move back, in 50–57 % of visits at every position**, and the back move lands on a result already examined 75–92 % of the time. The stutter step is not an occasional pattern; it is the majority case for every result below the first.
2. **Forward by one is the second outcome (32–38 %)**; skipping two or more results from the end of a visit is 6–13 %, rising with depth. Reading order is the forward rule; long forward jumps are the minority the survey and the pre-jump timing describe.
3. **Result 1 is different.** Its first visit is twice as long (4 fixations, 745 ms vs 2 and ~415 ms) and ends off the result column 44 % of the time, always *above* the results: at y ≈ 121 px (IQR 86–143), the query box and the results header (the first typed AOI starts at y = 158). Reading result 1 and then re-reading the query is the commonest opening after reading straight on to result 2.

## C. When the trial starts on p

2,376 of 2,606 trials start their fixations on result 1 (148 on result 2, 35 on result 3). For those, the first visit ends forward 1 in 47 %, above the results in 44 %, forward 2+ in 8 %; P(clicked) 0.20. The table above is therefore mostly a table of first entries reached in reading order, not of trial openings, except at position 1.

## D. What the back excursion resolves to

For first visits that ended in a back move: does the gaze come back to p, move on to a new result, or does the trial end during the excursion?

| pos | n | returns to p | new: p+1 | new: beyond p+1 | new: above p | trial ends |
|---|---|---|---|---|---|---|
| 2 | 1,377 | 0.75 | 0.08 | 0.04 | 0.08 | 0.05 |
| 3 | 1,289 | 0.64 | 0.08 | 0.05 | 0.14 | 0.09 |
| 4 | 1,109 | 0.54 | 0.08 | 0.04 | 0.21 | 0.14 |
| 5 | 1,032 | 0.50 | 0.07 | 0.03 | 0.24 | 0.16 |
| 6 | 789 | 0.46 | 0.08 | 0.04 | 0.23 | 0.20 |
| 7 | 631 | 0.43 | 0.09 | 0.05 | 0.26 | 0.18 |
| 8 | 542 | 0.39 | 0.09 | 0.03 | 0.29 | 0.20 |
| 9 | 453 | 0.35 | 0.06 | 0.04 | 0.32 | 0.23 |
| 10 | 387 | 0.27 | 0.07 | 0.04 | 0.35 | 0.27 |

At the top of the page the back move is a **bounce**: three quarters of back excursions from result 2 return to result 2 before any new result is entered, and only 8 % proceed directly to result 3. Deeper, the excursion increasingly resolves elsewhere: to an above-p result the survey skipped (35 % at position 10) or to the click (the trial ends during the excursion in 27 % at position 10, mostly a click on the result returned to). "New: above p" is not a contradiction: it is a result the eyes passed over on the way down and enter for the first time on the way back.

## Reading

The sequence the idealized figure draws (read p, go back to a seen result, come back to p, then move on) is the modal first-visit trajectory for every result from position 2 down. Two mechanisms already documented fit it: the return is memory-guided (`return_is_memory.md`: precision at first-entry level, no peripheral ramp, 70 % of returns from the adjacent result), and continuation beyond p is reading order with opportunity (`periphery_navigates.md` §A). What this table adds is the *rate*: a searcher on AdSERP compares the result just read with one already seen before continuing more often than not, and the comparison is a two-result loop at the top of the page and a widening one deeper down.

## Caveats

- Typed positions, all element types pooled; the ad and widget bands on top of these pages are positions like any other. `--organic-only` maps non-organic bands to "off results" and keeps typed indices, so it is a filter, not an organic-rank table (position 1 is organic in 444 trials only); read it for the organic-only shares at a given typed position, not as a rank table.
- "Off results" is any fixation outside every typed AOI; on these pages that is the page top (query box, header) in every case with n ≥ 30.
- First visits only. Second and later visits are in `return_is_memory.md`.
- Transactional product queries with a forced final click; the AI-Overview corpus has links below an overview and a different opening (`docs/methodology/adserp-vs-ao-corpus-differences.md`).
