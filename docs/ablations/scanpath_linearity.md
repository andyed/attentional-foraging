# Scanpath linearity: Lorigo et al.'s classification replicated on AdSERP

**Tags:** `[LAB, AdSERP, typed]` · rank types `organic` (primary; matches Lorigo's ten organic abstracts) and `typed` (ads and widgets ranked) · 2,606 trials, 47 participants
**Producer:** `scripts/scanpath_linearity.py` → `scripts/output/scanpath_linearity/summary.json`, `trials.csv` · tests `scripts/test_scanpath_linearity.py`
**Key Claims:** none yet. Cite this note until a notebook row exists.
**Generated:** 2026-09-29.

## Why

Lorigo et al. (2006) measured how often searchers read Google results in rank
order. It is the eye-tracking precedent for any claim that examination is not
a single top-down pass. This note applies their definitions to AdSERP, gives
their figures and ours side by side, and splits their nonlinear class by how
the path leaves rank order.

Source: Lorigo, Pan, Hembrooke, Joachims, Granka & Gay, *The influence of task
and gender on search and evaluation behavior using Google*, Information
Processing & Management 42(4):1123–1131, 2006,
[doi:10.1016/j.ipm.2005.10.001](https://doi.org/10.1016/j.ipm.2005.10.001).
Definitions from section 3; reported figures from section 4.1. Their study:
23 subjects with usable eye data, 5 navigational and 5 informational
questions, ASL 504 at 60 Hz, AOIs on the ten ranked abstracts, scanpaths over
600+ Google result pages, including pages left without a click.

## Definitions (Lorigo et al., section 3)

- **Scanpath:** the sequence of result abstracts fixated. Here: fixations in
  time order up to the final press (AdSERP fixations end there), each assigned
  to a ranked result or to nothing; fixations on nothing are dropped.
- **Compressed sequence:** consecutive fixations on one result merged into one visit.
- **Minimal sequence:** the compressed sequence with repeat visits removed, i.e. the order of first entries.
- **Linear:** the minimal sequence rises in steps of exactly 1.
- **Strictly linear:** the compressed sequence rises in steps of exactly 1
  (no skips, no regressions). A one-result path is strictly linear by default,
  and no path has to start at rank 1.
- **Complete:** a path ending in a selection contains every result ranked at or above the selected one.

The two nonlinear classes below are this note's addition, not Lorigo's:

| Class | Rule |
|---|---|
| strictly linear | Lorigo's strictly linear |
| linear with regression | Lorigo's linear, not strictly: first entries advance one rank at a time; at least one result is revisited |
| nonlinear, backfill | some result is entered for the first time after a lower-ranked one: the path goes back for a result it passed over |
| nonlinear, skip only | first entries only move down the page, but at least one jumps more than one rank |

The worked example in section 3 (scanpath 2 2 3 2 1 1 1, compressed 2 3 2 1,
minimal 2 3 1) is a unit test; it classifies as nonlinear, backfill.

## Gate

The band/typed view recomputes the end of the first visit to each typed
position 1–10 (`next_action_by_position.py`, table B) and reproduces the
shipped `scripts/output/next_action_by_position/summary.json` exactly: same
2,606 trials, same n and shares at all 10 positions. One census trial is
dropped for having fewer than two fixations, as in that producer.

## Result: Lorigo et al. beside AdSERP

Primary view: strict rectangles, organic ranks, every fixation counted.
2,518 paths (88 trials fixated no organic result). 95% CIs from a
participant-cluster bootstrap (2,000 draws).

| Measure | Lorigo et al. 2006 | AdSERP |
|---|---|---|
| Strictly linear | 19% | 16.6% [12.8, 21.0] |
| Linear, incl. strictly | 34% | 52.7% [47.1, 58.4] |
| Nonlinear | 66% | 47.3% [41.6, 52.9] |
| Paths with a regression | 59% | 82.1% [77.8, 86.0] |
| Paths with a skip | 50% | 54.0% [47.4, 60.0] |
| Mean length: fixations on results / compressed / minimal | 16 / 5.8 / 3.2 | 36.0 / 9.8 / 4.46 |
| Mean rank distance between sequential results | 1.67 | 1.47 (22,113 pairs) |
| Complete before the click | 67% of paths with a selection | 94.0% [92.0, 95.7] of 2,125 organic clicks |

This note's split of the AdSERP classes:

| Class | Share | 95% CI |
|---|---|---|
| strictly linear | 16.6% | [12.8, 21.0] |
| linear with regression | 36.1% | [31.8, 40.5] |
| nonlinear, backfill | 34.6% | [29.7, 39.6] |
| nonlinear, skip only | 12.7% | [11.0, 14.3] |

- 87.3% [84.7, 89.6] of paths start on organic rank 1.
- Skips average 2.5 ranks; 67% are two-rank jumps (one result passed over).
  Regressions average 1.68 ranks.
- Per participant, the nonlinear share has median 52% (IQR 30–60%); 25 of 47
  participants are majority nonlinear.

### By minimal length (distinct organic results entered)

Longer paths have more chances to leave rank order, so comparisons across
studies need matched lengths. Lorigo et al. report a mean of 3.2, not the
distribution.

| Results | Paths | Strictly linear | Linear with regression | Backfill | Skip only |
|---|---|---|---|---|---|
| 1 | 304 | 100.0% | 0.0% | 0.0% | 0.0% |
| 2 | 423 | 18.7% | 64.1% | 9.9% | 7.3% |
| 3 | 333 | 6.3% | 54.4% | 26.4% | 12.9% |
| 4 | 255 | 3.5% | 41.6% | 36.1% | 18.8% |
| 5–6 | 544 | 0.9% | 30.0% | 47.8% | 21.3% |
| 7+ | 659 | 0.2% | 28.4% | 59.2% | 12.3% |

### Sensitivity

| View | Paths | Strictly linear | Linear (incl. strict) | Nonlinear | Mean distinct results |
|---|---|---|---|---|---|
| rect, organic, ≥0 ms | 2,518 | 16.6% [12.8, 21.0] | 52.7% [47.1, 58.4] | 47.3% [41.6, 52.9] | 4.46 |
| rect, organic, ≥100 ms | 2,514 | 17.3% [13.4, 21.7] | 52.8% [47.3, 58.3] | 47.2% [41.7, 52.7] | 4.39 |
| band, organic, ≥0 ms | 2,527 | 13.6% [10.2, 17.4] | 56.1% [50.5, 61.6] | 43.9% [38.4, 49.5] | 4.73 |
| band, organic, ≥100 ms | 2,524 | 14.3% [10.9, 18.3] | 56.0% [50.6, 61.6] | 44.0% [38.4, 49.4] | 4.66 |
| rect, typed, ≥0 ms | 2,603 | 3.2% [1.8, 4.7] | 36.4% [30.7, 41.9] | 63.6% [58.1, 69.3] | 6.66 |
| rect, typed, ≥100 ms | 2,603 | 3.7% [2.3, 5.4] | 36.0% [30.7, 41.5] | 64.0% [58.5, 69.3] | 6.54 |
| band, typed, ≥0 ms | 2,605 | 2.3% [1.1, 3.6] | 40.8% [35.0, 46.4] | 59.2% [53.6, 65.0] | 7.09 |
| band, typed, ≥100 ms | 2,605 | 2.5% [1.3, 4.0] | 40.8% [35.2, 46.2] | 59.2% [53.8, 64.8] | 6.98 |

A 100 ms minimum visit moves the three Lorigo shares by at most 0.7 points,
and this note's four classes by at most 2.0. Assignment matters more for the
skip-only class: y-bands give 7.3% against 12.7% for strict rectangles,
because a rectangle leaves glances in card margins and gaps unassigned, and
some of those register as passed-over results. Part of the skip-only class is
an AOI-coverage effect.

## Reading

1. **Strictly linear reading replicates.** 16.6% against Lorigo's 19%, which
   lies inside the interval. Most strictly linear paths are short: of 419,
   304 enter one result and 383 enter one or two. Lorigo et al. also attribute
   theirs mostly to lengths one and two.
2. **Nonlinearity does not replicate at Lorigo's level, even though AdSERP paths are longer.**
   47.3% against 66%, with 4.46 distinct results per path against 3.2. At a
   minimal length of 3, 39.3% of AdSERP paths are nonlinear. The difference
   goes into linear paths with regressions, not into strictly linear ones:
   82% of AdSERP paths revisit a result, against 59%.
3. **Coverage above the click is far higher.** 94.0% of AdSERP paths ending on
   an organic click have entered every organic result above it, against 67%.
   The examined-above-the-click assumption of click models holds for most
   AdSERP selections; what fails is a single ordered pass.
4. **Counting ads and widgets as ranked results reaches Lorigo's nonlinear share.**
   63.6% nonlinear, on paths of 6.7 elements, with 3.2% strictly linear.
5. **Two departures, about equally common.** 36.1% of paths revisit while
   first entries stay in rank order; 34.6% go back for a result they passed
   over. The first is the stutter step counted per path; the second is where
   first-entry order itself breaks.

## Comparability limits

- **Task and selection.** Lorigo et al. used navigational and informational
  questions under a two-minute limit. More than half of queries ended in a
  reformulation without a click, and linearity is reported over all pages.
  AdSERP uses transactional product queries, and every trial ends in a
  selection. This is the most likely source of the longer, more complete paths.
- **Page and era.** Lorigo's AOIs cover only the ten organic abstracts, which
  the organic view matches. AdSERP pages carry ad blocks and widgets, and on
  ad-topped pages organic rank 1 sits below the ads.
- **Instrument.** ASL 504 at 60 Hz, with precision the authors describe as too
  coarse for sub-abstract regions, against Gazepoint GP3 HD at 150 Hz. Lower
  precision would add spurious transitions between adjacent abstracts. The
  direction of the difference is consistent with that, but its size is not
  established here.
- **Denominators.** Lorigo reports linearity over all scanpaths and
  completeness over paths with a selection. AdSERP has only the latter.
- **Length.** Only Lorigo's mean lengths are known, so the length-matched
  comparison is approximate.

## Relation to other notes

- The linear-with-regression class is the stutter step counted per path.
  Per-position rates are in [`next_action_by_position.md`](next_action_by_position.md);
  how returns are executed is in [`return_is_memory.md`](return_is_memory.md).
- For [`../not-a-cascade.md`](../not-a-cascade.md): the evidence supports "first-entry
  order often breaks, and ordered paths usually revisit". It does not support
  "results above the click go unexamined": 94% are entered.

## Bibliography entries to add

Not yet in `references.bib` (metadata checked against Crossref, 2026-09-29):
- `lorigo2006taskgender`: Lorigo, L., Pan, B., Hembrooke, H., Joachims, T.,
  Granka, L., Gay, G. *The influence of task and gender on search and evaluation
  behavior using Google.* Information Processing & Management 42(4):1123–1131,
  2006. doi:10.1016/j.ipm.2005.10.001
- The note on the existing `lorigo2008eyetracking` entry says "~2/3 of
  scanpaths are nonlinear". That figure is from the 2006 paper (34% linear).
