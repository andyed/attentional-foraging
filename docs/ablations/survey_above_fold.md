# The survey and the block above the fold — ads on AdSERP, and what the eyes do with them

**Tags:** `[LAB, AdSERP, typed]` · survey = first five fixations (NB13) · 2,603 trials, 47 participants · ad = `native_ad` + `dd_top` (top-of-page ads in the typed taxonomy)
**Producer:** `scripts/survey_above_fold.py` → `scripts/output/survey_above_fold/summary.json`
**Generated:** 2026-09-15. AI-Overview mirror (collab-only, Sara's data): `collab/allawati-ai-overviews/engagement-census-ao-2026-09-14/survey_above_fold_ao.py`, numbers in that folder's README.

## Question

Above the fold on these pages sits an ad block on 78 % of trials (2,019 of 2,603: 1,544 `dd_top`, 475 `native_ad`), an organic on 17 %, a widget on 5 %. Does the survey dance *around* the ad block, skipping to the first organic, or into it?

## 1. Where the five survey fixations go

Share of survey fixations by class, against the class's share of above-fold band height (ratio > 1 = fixated more than its size).

| layout | class | fixation share | area share | ratio |
|---|---|---|---|---|
| ad-topped (n 2,019) | page top (query box, header) | 0.23 | — | — |
| | **ad** | **0.71** | 0.46 | **1.53** |
| | widget | 0.01 | 0.11 | 0.12 |
| | organic | 0.05 | 0.43 | 0.13 |
| not ad-topped (n 584) | page top | 0.20 | — | — |
| | widget | 0.20 | 0.22 | 0.94 |
| | organic | 0.59 | 0.78 | 0.76 |

First fixation of the trial: page top 0.44, ad 0.39, organic 0.13, widget 0.04. First *band* fixated on an ad-topped page: the ad 0.93, an organic 0.03.

## 2. The ad block on ad-topped pages

| measure | value |
|---|---|
| ad block height (median) | 351 px, about a third of the fold |
| survey lands on the ad block | 0.955 |
| first band fixation is the ad | 0.930 |
| survey skips over the block to an organic | 0.032 (landing 155 px below it) |
| survey fixations on the ad (of 5) | median 4, mean 3.5 |
| ad block fixated at any time in the trial | 0.999 |
| of those, first fixated in the survey | 0.957 |
| share of the trial's ad dwell that falls inside the survey (median) | 0.13 |
| returns to the ad block after the survey | 0.933 |
| per participant, P(survey lands on the ad) | median 0.98, IQR 0.94–1.00, min 0.78 |

## 3. Transitions within the survey (row-normalised)

| from \ to | page top | ad | widget | organic | n |
|---|---|---|---|---|---|
| page top | 0.46 | 0.43 | 0.03 | 0.08 | 2,374 |
| ad | 0.09 | **0.87** | 0.01 | 0.04 | 5,749 |
| widget | 0.07 | 0.04 | 0.78 | 0.11 | 572 |
| organic | 0.08 | 0.05 | 0.03 | 0.84 | 1,717 |

Only 0.9 % of surveys reach below the fold.

## Reading

- **The survey does not dance around the ads. It reads into them.** On an ad-topped page the first band fixated is the ad in 93 % of trials, the block takes three and a half of the five survey fixations, and its selection ratio (1.5) is the highest of any class while the organics below it are fixated at an eighth of their size share. Skipping over the block to the first organic happens in 3 % of trials. Every participant does this: the lowest per-participant rate is 0.78.
- **Nor is the survey a glance at the ad.** Only 13 % of the trial's ad dwell falls inside the survey, and 93 % of trials come back to the block after it. The top ads are examined like results, at length, with returns, which is what the state census already showed for their engagement states.
- **Five fixations is the top block.** With a 351 px block and 200–250 ms reading fixations, the first five fixations rarely leave it (0.9 % reach the fold). The NB13 survey (amplitude compression after about five fixations) is therefore a description of how the *top block* is scanned, not of the page. Where a page has no ad block the same five fixations are spent on the organics (0.59) and page top (0.20) in about their size shares.
- **The page top is the other destination.** A fifth of survey fixations are on the query box and results header, 44 % of trials start there, and leaving the ad block goes to the page top twice as often as to an organic. Re-reading the query is part of the opening on every layout (`next_action_by_position.md` §B found the same after the first visit to result 1).

For the periphery account this is a boundary condition: whatever the near periphery does, it does not steer the survey *away* from the ad block on a page where the block is the first thing under the query box. Reading order wins at the top of the page as it does below (`periphery_navigates.md` §A).

## Caveats

- Ads are the typed `native_ad` and `dd_top` classes; `dd_right` and other off-axis elements are not on the main axis and are not counted anywhere here.
- The fold is the browser window height from trial geometry (median 1,137 px, larger than the 1,024 px screen; the geometry records it as such and the choice moves no survey number, since 99 % of surveys stay in the top 400 px).
- Survey = first five fixations regardless of time; a 1.5 s window gives the same top-block picture.
- Transactional product queries; the ad block is commercially relevant to the task by construction. The informational mirror is the AI-Overview corpus, where the block is an answer, not an ad.
