# Continuation four ways — what "viewed" means when viewport, periphery, gaze and cursor disagree

**Tags:** `[LAB, AdSERP, typed]` · kernel inherited from the census it consumes
**Producer:** `scripts/engagement_continuation.py --census-dir …` → `scripts/output/engagement_continuation/gate_200px/summary.json` (**primary**, intake within 200 px (≈ 5°)), `kernel_boundary_cm_24/summary.json` (soft falloff), `summary.json` (the flat published kernel, artefact rows)
**Key Claims:** `[NB37:K5–K9]`
**Inputs:** the census `states.csv` (matched-opportunity rule), the cursor-only typed mousedown cache, organic content features, split title/snippet embeddings
**Generated:** 2026-09-14.

## Why this exists

The C/W/L framework (Moffat et al.; Azzopardi, Thomas & Craswell SIGIR 2018
for the IFT-based instance) describes a user by one continuation function
C(i): the probability of proceeding to result i + 1 having viewed result i.
Evaluation metrics are the expected gain under C. "Viewed" is left to the
metric designer. This corpus can measure it four ways at once, and they do
not agree.

## (a) Continuation and reach, four channels

Computed on the **2,151 trials** where viewport opportunity is known for every
slot, so all columns share a denominator. Four columns use the state flag at
any time in the trial; **first-pass** is the strict C/W/L viewing order: a
result counts only if its first fixation precedes the first fixation on
every deeper result.

Reach R(i), share of trials in which result i was reached:

| i | viewport | periphery (within 200 px (≈ 5°)) | fixation (any time) | fixation (first pass) | cursor |
|---|---|---|---|---|---|
| 0 | 1.000 | 0.996 | 0.995 | 0.909 | 0.835 |
| 2 | 0.999 | 0.963 | 0.943 | 0.777 | 0.753 |
| 4 | 0.940 | 0.823 | 0.791 | 0.684 | 0.535 |
| 6 | 0.760 | 0.602 | 0.578 | 0.483 | 0.320 |
| 8 | 0.567 | 0.455 | 0.425 | 0.357 | 0.210 |
| 9 | 0.486 | 0.379 | 0.356 | 0.297 | 0.181 |

(Periphery column under the soft falloff: 0.831 / 0.632 / 0.482 / 0.407 at
i = 4 / 6 / 8 / 9; under the flat published kernel 0.849 / 0.672 / 0.519 /
0.450. Only this column depends on the kernel.)

Continuation C(i) = P(reached i + 1 | reached i):

| i → i+1 | viewport | periphery | fixation (any) | fixation (first pass) | cursor |
|---|---|---|---|---|---|
| 0→1 | 1.000 | 0.979 | 0.971 | 0.843 | 0.854 |
| 2→3 | 0.986 | 0.938 | 0.899 | 0.767 | 0.735 |
| 4→5 | 0.914 | 0.873 | 0.812 | 0.699 | 0.666 |
| 6→7 | 0.857 | 0.836 | 0.789 | 0.645 | 0.638 |
| 8→9 | 0.855 | 0.844 | 0.738 | 0.601 | 0.688 |

At the tenth result, half the trials still have it on screen, 38 % have
taken it in within 200 px (≈ 5°) (41 % under the soft falloff), 36 % have fixated it
at some point, 30 % reached it on the first pass, and 18 % have brought the
cursor near it. With an eccentricity-aware kernel the periphery column
sits just above fixation, which is what "the eyes get close to what they
read" predicts. The first-pass
curve is the only one that declines smoothly from 0.84 to 0.60, which is the
shape C/W/L metrics assume; every any-time curve flattens at depth because
returns refill the deeper slots. Nine percent of trials fixate a deeper
result before result 0, which is the survey phase showing up in C(0).
Each column is a different C(i); a metric that picks one picks a user model.

## (b) Examination cost by state

| state | n | gaze dwell (median ms) | cursor dwell (median ms) | visits | approached |
|---|---|---|---|---|---|
| peripheral | 1,794 | 0 | 0 | 0 | 0.20 |
| rejected | 6,077 | 541 | 0 | 1 | 0.41 |
| deferred | 9,797 | 1,695 | 384 | 4 | 0.69 |
| clicked | 2,607 | 4,052 | 1,617 | 5 | 0.94 |

The per-element cost model measured: a peripheral examination costs no
fixation, a rejection costs about half a second, a deferral about 1.7 s
across four visits, and the harvested result about 4 s. The cursor arrives
only at the two costliest tiers.

## (c) Position-matched peripheral split

With the threshold taken from fixated slots of the **same etype and
position** (n = 2,420 skipped slots with a threshold):

| kernel | position-matched peripheral share | skipped vs read AUC at matched (etype, position) |
|---|---|---|
| within 200 px (≈ 5°) (primary) | **31.8 %** | **0.33** |
| soft falloff, 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`) | 46.2 % | 0.46 At 43 px/° (2026-09-15 rerun): 50.3 %, matched AUC 0.49; see `px_per_deg_rerun.md`. |
| flat published kernel | 64.3 % | 0.60 |

Under either eccentricity-aware definition a skipped result receives *less*
near-peripheral intake per unfixated second than a read result at the same
position. The flat kernel's 0.60 said the opposite and was counting
page-wide fixation duration. The paper quotes the 200 px (≈ 5°) row and shows the
ladder.

## (d) Does the periphery evaluate? Relevance by state

Query-to-result cosine on organic slots (16,375 slots, 2,599 trials; typed
organic slot joined to the organic-flavour card by page geometry, then to
the h3 embedding). Medians are tightly bunched (title 0.835–0.854, snippet
0.766–0.785); AUC is P(first > second).

| contrast | within 200 px (≈ 5°) (primary), text cosine | soft falloff, text cosine | flat kernel: title / snippet |
|---|---|---|---|
| peripheral vs unsampled | 0.50 (p 0.81) | 0.49 (p 0.64) | 0.49 / 0.466 (p 0.04) |
| peripheral vs rejected | 0.48 (p 0.15) | 0.48 (p 0.07) | 0.49 / 0.468 (p 0.004) |
| rejected vs deferred (title) | — | — | 0.48 (p 0.002) |
| deferred vs clicked (title) | — | — | 0.48 (p 0.009) |

Under an eccentricity-aware kernel the peripheral-vs-unsampled contrast is
null on every proxy. The small snippet effect under the flat kernel does
not survive. Crowding-robust cues (query-term overlap in the title,
numerals, price presence, title length) were also tested by state under the
flat kernel: all null except snippet numerals (AUC 0.45, p 0.004), which is
weak and unreplicated under the gate.

**Reading.** There is no evidence here that the periphery evaluates
content. The one small effect (snippet cosine under the flat kernel) was
page-wide fixation duration, not intake on the target. The crowding
argument still stands as the reason a semantic test was never well
targeted: at three to six degrees, letter spacing is an order of magnitude
inside Bouma's critical spacing, so only coarse cues (colour, weight, line
length, numerals, bold query-term density) could carry anything, and every
coarse cue is null, bold density included
(`docs/null-findings/2026-09-14-bold-term-density-null.md`: bold share is
0.10 in every state because every snippet on a transactional query matches).
The peripheral tier is a fact about *sampling*, not about *evaluation*. The relevance gradient across the fixated tiers (rejected <
deferred < clicked) is likewise small, which says as much about
embedding cosine as a relevance proxy on a commercial SERP as about the
searcher. A human relevance judgment set for the AdSERP results is the
instrument that would settle it, and is the natural contribution for an
evaluation-theory coauthor.

## Caveats

- Any-time reach and first-pass reach are both reported; the first-pass
  column is the one C/W/L strictly wants.
- 456 trials without a scroll stream are excluded from (a) and are not
  missing at random (short pages, fast decisions).
- 4,651 typed organic slots have no geometric twin in the organic flavour
  and are excluded from (d).
- `[LAB]` only.
