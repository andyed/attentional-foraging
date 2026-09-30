# Cursor marking: how often the pointer holds a result while the eyes check others

**Tags:** `[LAB, AdSERP, typed]` · rank type `typed` (all main-column elements; positions numbered from 1 below) · 2,650 trials, 47 participants
**Producer:** `scripts/cursor_marking.py` → `scripts/output/cursor_marking/summary.json`; `--hold-sensitivity` (needs the raw AdSERP recordings) → `hold_sensitivity.json` · tests `scripts/test_cursor_marking.py`
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

## Cursor-hold sensitivity

The tables above use the poster's primary rule: a mousemove position is held
for at most 2 s. The logger records the cursor only when it moves, so a
pointer left completely still for longer drops out of "rest". That is the
prototypical mark in Rodden's description. `--hold-sensitivity` rebuilds every
trial's pauses from the raw recordings through `scripts/attention_atlas/atlas_core.py`
under two relaxed rules:

- **no cap:** each position is held until the next mousemove;
- **no cap, follows scroll:** as above, and the held page position moves with
  the scroll offset. A still pointer keeps its screen position while the page
  scrolls under it.

Gates: the capped rebuild reproduces the shipped per-trial pauses, gaze
segments and rest totals for all 2,650 trials. Each uncapped rebuild
reproduces the resting-cursor producer's sensitivity totals (rest share
27.6% and 25.0%). The capped rebuild also reproduces this note's primary
summary.

| At ≥100 ms other-gaze | 2 s cap (primary) | No cap | No cap, follows scroll |
|---|---|---|---|
| Cursor pauses (≥1 s) | 5,058 | 6,039 | 5,953 |
| … lasting ≥4 s / ≥8 s | 3.2% / 0.1% | 16.2% / 3.3% | 16.3% / 3.3% |
| Marking share of pre-approach pauses | 65.1% [62.0, 68.4] | 74.5% [71.4, 77.5] | 71.1% [68.1, 74.3] |
| Marking share of pre-approach pause time | 65.8% [62.3, 69.5] | 78.6% [75.4, 81.7] | 76.2% [73.0, 79.4] |
| Trials with a pre-approach marking pause | 42.5% [36.0, 49.1] | 45.8% [38.9, 52.6] | 46.2% [39.4, 52.9] |
| A: marked result is the click (lift) | 25.4% (1.53) | 24.5% (1.46) | 21.7% (1.40) |
| A: most-gazed other is the click (lift) | 20.6% (1.41) | 20.5% (1.52) | 20.8% (1.52) |
| A: paired difference, marked − other | +4.8 [0.0, 8.8] | +3.9 [−0.2, 7.7] | +0.9 [−2.7, 4.2] |
| B: later − earlier mark (transitions) | +5.1 [2.1, 8.9] (1,186) | +4.7 [1.8, 8.3] (1,298) | +2.2 [0.2, 4.1] (1,857) |
| Marks ≥4 s: marked / most-gazed other is the click | 31.0% / 21.8% (87) | 28.6% / 24.6% (574) | 27.5% / 24.2% (563) |

Under the scroll-following rule, a still pointer can land on a different
result because the page moved, not the hand. Those passive changes add
pauses and "moves" that are not placements. That is why test B has 1,857
transitions under this rule against 1,298 without it, and they dilute both
tests. The no-cap rule without scroll keeps the result where the hand last
put the pointer. The scroll-following rule tracks what is physically under it.

## Reading

1. **Marking is common and universal, more so than the capped figures showed.**
   Once long still periods count, 71–75% of pre-approach cursor pauses contain
   gaze on another result, and about 46% of trials and all 47 participants show
   the pattern. The cap had hidden the long marks: pauses of 4 s or more rise
   from 3.2% to 16% of pauses. Rodden et al. named the pattern; this supplies
   the rate.
2. **The parked result carries choice information beyond its position.** It is
   the eventual click 1.40–1.53 times as often as its position predicts under
   every hold rule. The effect is strongest when the cursor is parked below the
   top three results (2.60× primary). A cursor resting on the first element,
   often an ad block where the hand happens to be, is barely diagnostic (1.13×).
3. **The hand's mark does not reliably beat the eyes' excursion.** Under the
   primary rule the marked result wins by +4.8 points [0.0, 8.8]. The margin
   shrinks to +3.9 [−0.2, 7.7] without the cap and +0.9 [−2.7, 4.2] when the
   pointer follows scroll. Relative to position, the eyes' most-examined result
   is as diagnostic (lift 1.52 without the cap). In the last 2 s before the
   approach the eyes' target is ahead under every rule, consistent with gaze
   reaching the choice before the hand (Huang, White & Buscher, CHI 2012).
4. **Moving the mark tracks the choice, weakly.** The later of two marks is the
   click more often: +5.1 points primary, +4.7 without the cap, +2.2 [0.2, 4.1]
   with scroll. Later marks are also closer in time to the click, and under the
   scroll rule some moves are the page, not the hand.

Supported: the pattern is common, and the parked result predicts the choice
above position. Not supported as a distinct effect: the parked result is the
best candidate so far *compared with* what the eyes check during the pause;
both carry comparable choice information. Not tested: whether the user
*intends* the pointer as a bookmark. A cleaner test would separate hand
placements from scroll-induced changes, keeping only pauses whose result was
under the pointer when the hand last moved.

## Limits

- **Cursor hold.** Under the primary 2 s cap the prevalence figures are lower
  bounds. The hold sensitivity above measures them without the cap: 71–75% of
  pauses and about 46% of trials. The no-cap rules assume the pointer stayed
  exactly where the last mousemove left it, which is how the logger behaves.
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
  checks other results. The eyes' most-examined result during the pause is
  about as predictive, and whether the mark is a deliberate bookmark remains open.

## Citation

`references.bib`: `rodden2008eyemouse` (metadata checked against Crossref, 2026-09-29).
