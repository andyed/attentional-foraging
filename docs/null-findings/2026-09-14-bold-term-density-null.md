# Bold query-term density does not separate any engagement state — null

**Tags:** `[LAB, AdSERP, typed]` · organic slots · states from the engagement census (primary: intake within 200 px (≈ 5°); also the soft-falloff census)
**Producer:** `scripts/bold_term_density.py` → `scripts/output/bold_term_density/summary.json`, `by_trial.json`
**Key Claims:** `[NB37:K14]`
**Date:** 2026-09-14

## Why it was tested

The peripheral tier of the engagement census (`docs/ablations/engagement_state_census.md`) raised the question whether the periphery *evaluates* what it samples. Semantic relevance proxies were null and, by the crowding argument, never well targeted: at three to six degrees the critical spacing is one and a half to three degrees and title letters sit an order of magnitude inside it. Bold weight is the one crowding-robust feature on a result that is also a relevance cue, because Google marks query terms in snippets with `<em>`. Two opposite predictions were live: bold as an attractor (fixated results carry more of it than on-screen unfixated ones) and bold as a rejection cue (peripherally sampled skips carry less than unsampled skips).

## Setup

- 2,776 snapshots parsed with the same `#rso` h3 enumeration and container walk as `embed_serp_results.py`, so the index equals the content features' `source_h3_pos`. 29,361 results.
- Per result: number of `<em>`, em characters, snippet characters, bold share = em characters / snippet characters, em in title.
- 16,380 typed organic slots joined by page geometry to the organic-flavour card, then to the h3 index; 4,651 without a twin excluded.
- Mann–Whitney AUC between states, position-stratified, and the layout confound checked.

## Result

| state (within 200 px (≈ 5°)) | n | bold share median | mean | n em | share with no em |
|---|---|---|---|---|---|
| unsampled | 952 | 0.106 | 0.107 | 3 | 0.08 |
| peripheral | 334 | 0.105 | 0.113 | 3 | 0.05 |
| rejected | 3,290 | 0.106 | 0.108 | 3 | 0.08 |
| deferred | 5,055 | 0.104 | 0.107 | 2 | 0.08 |
| clicked | 2,004 | 0.101 | 0.105 | 3 | 0.07 |

| contrast | bold share AUC | p |
|---|---|---|
| peripheral vs unsampled | 0.513 | 0.47 |
| peripheral vs rejected | 0.514 | 0.40 |
| fixated vs on-screen unfixated | 0.491 | 0.32 |
| rejected vs deferred | 0.503 | 0.61 |
| deferred vs clicked | 0.511 | 0.15 |

Position-stratified peripheral-vs-unsampled AUCs run 0.42–0.57 with no trend; bold share does not vary with position (ρ +0.011). The soft-falloff census gives the same picture (peripheral vs unsampled 0.500). Em never appears in titles. The one nominally significant contrast, rejected vs deferred on em *count* (AUC 0.517, p 0.009), is a count difference of one em between medians of 3 and 2 and does not appear on bold share.

## Reading

Bold is neither an attractor nor a rejection cue here. The likely reason is in the corpus, not the searcher: on transactional product queries every snippet matches the query, so Google bolds something in 92 % of results and the share is about a tenth of the snippet everywhere. A cue with no variance between the results on a page cannot separate states, whatever the periphery can see. The test would have power on informational queries with heterogeneous match; it has none on AdSERP.

## Consequence

The last crowding-robust cue available in this corpus is null. The peripheral tier stands as a finding about **sampling** (a quarter of on-screen skips receive near-peripheral intake at read level within 200 px (≈ 5°), and the share is a participant trait) and not about **evaluation**. "Skipping is peripheral rejection" is not supported; "skipping is not invisibility" is, for a quarter to a third of skips. Recorded here so the claim is not re-litigated from prose.
