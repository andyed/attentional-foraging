# Abualsaud & Smucker (CIKM 2019) — Patterns of Search Result Examination: Query to First Action

**Paper:** Patterns of Search Result Examination: Query to First Action
**Authors:** Mustafa Abualsaud, Mark D. Smucker (University of Waterloo)
**Venue:** CIKM '19, Beijing, November 3–7, 2019
**Pages:** 10 pages
**DOI:** 10.1145/3357384.3358041
**Open access:** https://uwspace.uwaterloo.ca/handle/10012/15454 (UWaterloo institutional repository)
**Cited by Allawati et al. SIGIR 2026 as [2]** — the canonical "survey-phase" operationalization in modern IR.

## Why this paper matters for our portfolio

This is the **closest published prior art to OSEC's evaluation-episode framework** in the IR-eye-tracking literature. Abualsaud & Smucker explicitly window the time-from-query-issuance-to-first-action as a discrete behavioral phase and characterize examination patterns within it. They operationalize the Orient–Survey–Evaluate–Commit model up to the first decision point; OSEC extends that operationalization across the full session.

Also the conceptual ancestor of why a per-AOI **episode geometry** (visits, sequences, return-rates) is a better primitive than aggregate dwell — Abualsaud & Smucker get to per-rank examination probability and per-user-type behavior using sequence-level signals, where Allawati et al. 2026 (and most of the F-pattern literature) aggregate fixations across the full SERP viewing.

## Study design

- **N = 24 desktop + 11 mobile** university students (15F/19M/1 other across desktop; recruited via posters). Avg age 20.5, mostly STEM undergraduates.
- **Eye tracker:** Tobii Pro X3-120, 120 Hz. Tobii Pro Studio + Tobii Pro Lab. Tobii Mobile Device Stand for the Google Pixel 2 mobile condition. Internet Explorer for desktop, Chrome for mobile (Tobii browser compatibility).
- **Page fold:** desktop = after rank 7; mobile = after rank 3. Both interfaces show 10 results, no pagination.
- **Tasks:** 12 factoid questions (e.g., "color of the Hope Diamond", "Las Vegas monorail length"), reusing Zhang et al. 2018 [21] question set with one swap.
- **SERP manipulation — 12 treatments, fully crossed 12×12 Graeco-Latin square:**
  - Correct@1 through Correct@10 — single relevant result at the named rank, 9 distractors
  - NoCorrect (NC) — 10 distractors, no relevant result
  - Bing — uncontrolled Bing API results (baseline)
- After the first action on the manipulated SERP, subsequent queries fell through to live Bing API. Manipulated SERPs were triggered by participant queries matching pre-defined "relevant terms" for each question.
- **Within-subjects** — each participant saw each topic and each treatment once.

## The QFA window (operational definition of the survey-phase analog)

**"Time to action"** = elapsed time from SERP rendered → first action triggered.
First action ∈ {click a result, click the search bar to requery, announce answer from snippet alone}.
All within-window measurements (mouse moves, fixation counts, AOI dwells, fixation sequences) are restricted to this window.

This is the empirically rigorous definition of "survey phase" Andy's been working with — the window between query submission and the user's first commitment, before evaluation collapses into a single chosen target.

## AOI definitions

10 AOIs, one per search result. Per-AOI metrics:
- Fixation duration at that AOI
- Membership in the **eye fixation sequence** (e.g., 1→2→1 means looked at rank 1, then 2, then back to 1)
- **Unique fixation sequence** = sequence of unique ranks fixated (dedupes consecutive revisits to the same rank)

The eye fixation sequence is exactly the visit-level abstraction OSEC and approach-retreat use. Abualsaud & Smucker compute it but only summarize as a sequence length; they don't characterize per-visit dwell distributions or first-vs-revisit composition. That decomposition is the gap.

## Key findings

### Finding 1: Seeing → clicking is near-deterministic
> "If a user sees the relevant result, they are very likely to click it ... rank does not seem to have an influence on their clicking decision."

Per-rank click probability when the correct item has been **seen ≥ 1 second**, desktop, ranks 1–10:
- P(correct click | seen) = .7, .9, .8, .9, 1.0, 1.0, .9, .9, .9, 1.0
- P(requery | seen) = .3, .1, .2, .1, 0, 0, .1, .1, .1, 0

**This is a major result for the F-pattern misinformation thesis.** It directly contradicts the "users disengage at lower ranks" interpretation. If users *see* a lower-ranked result, they evaluate and click it normally. The aggregate rank-vs-click correlation is entirely driven by P(seen), not by P(click | seen). Headcount, not reading.

Table 3 desktop totals (frequency of action grouped by fixation duration at the correct item):
- < 200 ms fixation at correct item → 64 requeries, 10 wrong-clicks, 1 correct click
- ≥ 200 ms < 1s → 18 requeries, 1 wrong click, 26 correct clicks
- ≥ 1 s → 14 requeries, 0 wrong clicks, **106 correct clicks**

The pattern: **fixating ≥ 1s on the correct item produces a click 88% of the time, regardless of rank.**

### Finding 2: Two user types (economic vs exhaustive), separable by fixation count

Bimodal distribution of total fixations per user (Figure 6) split desktop users at ≈ 650 fixations:
- **Economic users (13):** ~449 fixations avg, shorter sequences, rarely scroll past fold
- **Exhaustive users (11):** ~870 fixations avg, longer sequences, scroll past fold

All differences between groups significant at p < 0.001 (Table 5 left): #fixations, sequence length, unique sequence length, top/mid/bottom-ranks duration, time-to-action, mouse moves.

Mobile distribution was not bimodal; mobile users treated as one group.

**For the survey-phase pitch:** the bimodality in fixation count is a direct empirical signature of two distinct behavioral types within the QFA window. Equivalent visit-segmentation work on Allawati's AIO data would test whether the AIO collapses or preserves this distinction.

### Finding 3: Query quality is a new factor (the paper's headline novelty)

Two assessors rated each query as **weak (under-specified)** or **strong**, Krippendorff α = 0.80 ("substantial agreement"). 27–28% of submitted queries judged weak; 18% of weak queries were misspellings.

**Decision tree (Figure 3A, desktop):**
- Root split: is the correct result above-fold (Correct@1–7) or below (8–10, NC)?
- Above-fold + strong query → click 79%
- Above-fold + weak query + Correct@1–3 → click 71%
- Above-fold + weak query + Correct@4–7 + economic user → requery 61%
- Above-fold + weak query + Correct@4–7 + exhaustive user → click 59%
- Below-fold + economic user → requery 87%
- Below-fold + exhaustive user → requery 57% (still mostly requery, but less)

**The "first three ranks are special" finding:** for economic users with weak queries, the first three ranks function as a "satisficing window." If the answer isn't there, they reformulate rather than scroll deeper. This is the survey-phase commitment-truncation mechanism, empirically demonstrated.

### Finding 4: Mobile is different

Mobile decision tree (Figure 3B) uses only `task_type` (no user_type split, no query quality split):
- Correct@1–5 → click 80%
- Correct@6–10 + Correct@8–10 → click 55% (above), requery 91% (NoCorrect)

Mobile users are willing to scroll to view the first ~5 results but rarely past that. The page-fold-at-rank-3 design means scroll behavior carries more weight than user-type/query-quality on mobile.

## The OSEC connection

Abualsaud & Smucker's Orient–Survey–Evaluate–Commit framing maps cleanly:

| Phase | Their operationalization | OSEC operationalization |
|---|---|---|
| Orient | Implicit (post-render, pre-first-fixation) | Same — pre-first-AOI-entry |
| Survey | Within-QFA-window fixation sequence | Per-AOI **first-visit** (gaze-defined, episode-level) |
| Evaluate | Fixation duration ≥ 1s at any AOI before action | Per-AOI **sustained-visit** (cursor + dwell threshold) |
| Commit | First action: click / requery / snippet answer | First click / first commit-eligible event |

**Where OSEC extends them:**
- Per-visit dwell distribution (they aggregate)
- First-visit vs revisit composition (they don't decompose)
- Within-evaluation regression behavior (they end at the first action)
- Multi-action sessions (they stop at first action; OSEC follows the full session)

## What this paper is NOT (and where Allawati 2026 doesn't either)

- **No AIO/generative content** — pre-LLM-era SERPs, single relevant result among distractors. The survey-phase findings haven't been retested on AIO SERPs. This is the open question for the Sanderson collaboration pitch.
- **No within-AOI segmentation** — each search result is one AOI; no title-vs-snippet decomposition.
- **No saccade-amplitude analysis within QFA** — they report sequence length and fixation count but don't characterize the spatial trajectory of the survey scan.
- **No temporal-density analysis** — fixations within the QFA window are aggregated rather than profiled across the window's duration (e.g., first 500 ms vs 500 ms – 1 s vs 1 s+).

The Allawati 2026 dataset could answer all four of these on AIO-era SERPs using the same QFA-window definition.

## How to cite

For the survey-phase framing: cite **Abualsaud & Smucker CIKM 2019 [10.1145/3357384.3358041]** as the operationalization. The Zhang/Abualsaud/Smucker CHIIR 2018 paper (see `zhang2018-immediate-requery.md`) is the prior immediate-requery work that motivated it — both papers can be cited together when grounding the "Orient–Survey–Evaluate–Commit" framing.

For "first-three-results window as satisficing zone" — this paper's Section 4 + decision tree.

For "P(click | seen) is near-constant across ranks; rank-vs-click correlation is driven by P(seen)" — this paper's Table 4 + Figure 5. Strongest single empirical claim available for the F-pattern misinformation thesis.

## Open questions for our work

1. **Does the QFA window's bimodal user-type signature survive on AIO SERPs?** Or does the AIO short-circuit the survey for economic users, collapsing them toward exhaustive-like AIO-reading behavior?
2. **Per-AOI visit composition within QFA** — what fraction of visits to rank *i* during QFA are survey-like (short, isolated) vs evaluation-like (long, clustered)?
3. **Saccade amplitude during QFA as a survey-phase fingerprint** — the AdSERP saccade-amplitude signal (~3.5 saccades, ~1s, wide jumps top 2–5) ports cleanly. Compare AIO-present vs AIO-absent.
4. **Does "first three results are special" still hold when an AIO occupies the top of page?** Or does the AIO shift the satisficing window to include the AIO + first 1–2 results?
