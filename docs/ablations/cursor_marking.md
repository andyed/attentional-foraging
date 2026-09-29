# Cursor marking: how often the pointer holds a result while the eyes check others

**Tags:** `[LAB, AdSERP, typed]` · rank type `typed` (all main-column elements; positions numbered from 1 below) · 2,650 trials, 47 participants
**Producer:** `scripts/cursor_marking.py` → `scripts/output/cursor_marking/summary.json` · tests `scripts/test_cursor_marking.py`
**Key Claims:** none yet. Cite this note until a notebook row exists.
**Generated:** 2026-09-29.

## Why

Rodden, Fu, Aula & Spiro (2008) described three active mouse patterns on
result pages from manual inspection of 32 participants' eye and mouse paths.
In one, *marking*, the user leaves the pointer on or near the most promising
result read so far while the eyes continue to check other results, and moves
it when another result looks more promising. The paper reports no prevalence.
The sequence poster's close-up ("while the mouse waits, the eyes travel") is an
instance. This note measures how common the pattern is and tests the two
predictions that follow from Rodden's description.

Source: Rodden, K., Fu, X., Aula, A., Spiro, I. *Eye-mouse coordination
patterns on web search results pages.* CHI '08 Extended Abstracts, 2997–3002,
[doi:10.1145/1358628.1358797](https://doi.org/10.1145/1358628.1358797)
([PDF](https://ianspiro.com/chi2008.pdf)).

## Definitions

- **Cursor pause:** the sequence poster's unit. Continuous cursor rest
  (< 50 screenshot px/s over complete 100 ms windows with no scroll) inside
  one strict typed AOI rectangle for at least 1 s. Clock from first mousemove
  to final press. See the [sequence poster methods](../visualizations/gaze-cursor-echo/methods.md).
- **Marking pause:** a pause during which gaze occupies at least one *other*
  AOI for at least 100 ms, the poster's minimum visit. 0 ms and 300 ms are
  sensitivity rows.
- **Pre-approach:** the pause ends at or before the final-approach onset.
  Pauses overlapping the final approach are excluded from the tests: 67.2% of
  the 1,558 such pauses already sit on the target, because the hand is
  arriving to click.
- **Marked result:** the AOI under the resting cursor. **Most-gazed other:**
  the AOI other than the cursor's with the most gaze time in the pause (ties
  go to the earliest entry).
- **Position-matched expectation:** the cohort's click rate at the result's
  position (position 1: 19.8%, 2: 24.9%, 3: 14.7%, 4: 13.1%, …). Lift is
  observed divided by expected.

Test A: the marked result is the eventual click more often than the
most-gazed other result from the same pause. Test B: when consecutive
pre-approach pauses sit on different results, the later one is the eventual
click more often than the earlier.

## Gates

Before computing, the producer checks two things against the shipped
sequence-poster summary. First, the per-trial rest totals sum exactly to its
`totals_ms`. Second, re-running the poster's illustration rule selects the
same example pause (`p021-b1-t6`, 4.4–8.4 s) from the same 63 qualifying
pauses. The information-space trials supply the clicked result for all 2,650
trials.

## Prevalence

5,058 cursor pauses, of which 3,500 end before the final approach.

| Measure | ≥0 ms | **≥100 ms (primary)** | ≥300 ms |
|---|---|---|---|
| Marking share of pre-approach pauses | 69.3% [66.2, 72.4] | **65.1% [62.0, 68.4]** | 48.4% [45.1, 52.1] |
| Marking share of pre-approach pause time | 69.6% [66.1, 73.1] | **65.8% [62.3, 69.5]** | 50.4% [46.3, 54.9] |
| Trials with a pre-approach marking pause | 43.7% [37.0, 50.3] | **42.5% [36.0, 49.1]** | 35.7% [29.9, 41.6] |
| Participants with at least one | 47 of 47 | **47 of 47** | 47 of 47 |

95% CIs from a participant-cluster bootstrap. At 100 ms, the median
participant shows the pattern in 41% of trials (IQR 23–60%). A marking pause
visits 1.37 other results on average; 32% visit two or more.

## Test A: the marked result against the eyes' most-examined result

Pre-approach marking pauses, n = 2,279 at 100 ms.

| | Eventual click | Position-matched expectation | Lift |
|---|---|---|---|
| Marked result (cursor) | 25.4% [22.7, 28.2] | 16.7% | 1.53 |
| Most-gazed other result (eyes) | 20.6% [18.3, 23.7] | 14.6% | 1.41 |
| Paired difference, marked − other | +4.8 points [0.0, 8.8] | | |

Sensitivity: +5.6 [0.9, 9.6] at 0 ms, +1.9 [−3.4, 6.5] at 300 ms.

By time from the pause's end to the approach onset:

| Lead | Pauses | Marked is click | Most-gazed other is click |
|---|---|---|---|
| 0–2 s | 340 | 28.2% | 29.4% |
| 2–5 s | 369 | 26.0% | 21.1% |
| 5–10 s | 479 | 25.9% | 17.3% |
| ≥ 10 s | 1,091 | 24.2% | 19.2% |

By the marked result's position:

| Marked position | Pauses | Marked is click | Position's click rate | Lift | Most-gazed other is click |
|---|---|---|---|---|---|
| 1 | 638 | 22.4% | 19.8% | 1.13 | 26.2% |
| 2 | 598 | 37.3% | 24.9% | 1.50 | 20.9% |
| 3 | 293 | 18.8% | 14.7% | 1.28 | 27.3% |
| 4 and below | 750 | 21.2% | 8.2% | 2.60 | 13.1% |

## Test B: moving the mark

1,186 transitions between consecutive pre-approach pauses on different results.

| | Eventual click |
|---|---|
| Later marked result | 24.3% [21.6, 27.6] |
| Earlier marked result | 19.2% [17.2, 21.5] |
| Difference | +5.1 points [2.1, 8.9] |

## Reading

1. **Marking is common and universal.** About two thirds of pre-approach
   cursor pauses contain gaze on another result. The pattern appears in 42.5%
   of trials and in all 47 participants. Rodden et al. named it; this supplies
   the rate.
2. **The parked result carries choice information beyond its position.** It is
   the eventual click 1.53 times as often as its position predicts. The effect
   is strongest when the cursor is parked below the top three results (2.60×)
   and at position 2 (1.50×). A cursor resting on the first element, often an
   ad block where the hand happens to be, is barely diagnostic (1.13×).
3. **The hand's mark beats the eyes' excursion, except just before the approach.**
   From 2 s to more than 10 s before the approach, the marked result is the
   click more often than the most-gazed other (by 4.9 to 8.6 points). In the last
   2 s the eyes' target catches up (29.4% against 28.2%). That is consistent
   with gaze moving to the choice before the hand, as in Huang, White & Buscher
   (CHI 2012). Overall the paired advantage is small and depends on the
   threshold for counting a look: +4.8 [0.0, 8.8] at 100 ms, gone at 300 ms.
4. **Moving the mark tracks the choice.** The later of two marks is the click
   more often (+5.1 points). This agrees with Rodden's description, but later
   marks are also closer in time to the click. The lead-time table bounds that
   effect only loosely: the marked hit rate rises from 24.2% to 28.2% as the
   approach nears.

Supported: the pattern is common, and the parked result predicts the choice
above position. Weakly supported: the parked result is the best candidate so
far, compared with what the eyes are checking. Not tested: whether the user
*intends* the pointer as a bookmark.

## Limits

- **The 2 s cursor-hold cap truncates the canonical case.** The cursor logger
  records only movement, and the poster's convention treats a cursor with no
  event for 2 s as unavailable. A pause therefore persists only while the hand
  keeps making small movements. A pointer left completely still for longer,
  which is Rodden's prototypical mark, is cut at 2 s or dropped. The prevalence
  figures are lower bounds. A hold-until-next-event sensitivity on the raw
  recordings is the next step.
- "Rest" is < 50 px/s endpoint displacement, not physiological stillness.
- AOIs include ads and widgets. The position-1 element is often an ad block,
  which dilutes the top row.
- The position-matched expectation is the cohort's marginal click rate. It
  does not condition on page layout.
- AdSERP requires a selection, so "eventual click" is always defined. On pages
  people abandon, a mark may mean something else.

## Relation to other notes

- The poster close-up and the 23.8% rest share: [sequence poster](../visualizations/gaze-cursor-echo/methods.md).
- The order in which results are first entered: [`scanpath_linearity.md`](scanpath_linearity.md).
- For [`../not-a-cascade.md`](../not-a-cascade.md): "anchor" is no longer
  untested at the level Rodden described it. The resting cursor marks a
  result that is chosen more often than its position predicts, while gaze
  checks other results. Whether that is a deliberate bookmark remains open.

## Bibliography entry to add

Not yet in `references.bib` (metadata checked against Crossref, 2026-09-29):
- `rodden2008eyemouse`: Rodden, K., Fu, X., Aula, A., Spiro, I. *Eye-mouse
  coordination patterns on web search results pages.* CHI '08 Extended
  Abstracts on Human Factors in Computing Systems, 2997–3002, 2008.
  doi:10.1145/1358628.1358797
