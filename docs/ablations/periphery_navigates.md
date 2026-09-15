# What the periphery does on a results page — two tests of navigation

**Tags:** `[LAB, AdSERP, typed]` · states from the primary census (intake within 200 px (≈ 5°)) · 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`)
**Producer:** `scripts/periphery_navigates.py` → `scripts/output/periphery_navigates/summary.json`
**Generated:** 2026-09-14. Companion to `pai_kernel_validation.md` and the null-findings entry on bold density.

## Why

Every content cue is null by engagement state, so if the periphery has a
job on a SERP it is not evaluation. Reading and scene research give it two
other jobs: choosing where the eyes go next from coarse layout, and holding
a gist map. Both are testable here.

## (A) Is skipping a layout decision?

Among 16,145 on-screen (≥ 500 ms), non-clicked result slots with known
opportunity, predict "fixated at all" by participant-held-out logistic
regression.

| features | LOSO AUC |
|---|---|
| position only | 0.696 |
| position + block height | 0.711 |
| position + element type | 0.699 |
| position + height + type (layout, opportunity held out) | 0.713 (Δ over position +0.006 [−0.001, +0.013]) |
| time on screen only | 0.738 |
| layout + time on screen | 0.803 |
| element type only | 0.514 |

On the 8,577 organic slots with content features: layout (position +
height) 0.651; content (query-to-text cosine + snippet length + bold share)
0.525; layout + content 0.651 (Δ −0.002 [−0.003, −0.000]).

**Reading.** Whether an on-screen result gets fixated is reading order and
opportunity. Block height and element type add a hair over position, and
the interval includes zero; content adds nothing over layout. The periphery
is not steering on format in any way that shows above position, and it is
not steering on content at all. The ad-versus-organic fixation gap seen in
the raw census is position and time on screen, not a format decision.

## (B) Does the survey leave a map?

For each trial, intake during the first five fixations (the survey phase)
on every on-screen, non-clicked slot *not* fixated during those five,
versus whether that slot is fixated later. 16,436 candidates over 2,603
trials; 13,288 fixated later. Intake = boundary-distance kernel, 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`),
gated at 200 px; control = mean gaze distance to the slot during the survey;
position removed by within-trial rank.

| predictor | LOSO AUC |
|---|---|
| position only | 0.654 |
| survey intake, within-trial rank | 0.747 |
| survey gaze distance, within-trial rank | 0.748 |
| position + intake rank | 0.751 (Δ over position +0.050 [+0.025, +0.073]) |
| position + distance rank | 0.752 (Δ over position +0.050 [+0.025, +0.073]) |
| position + both | 0.753 (Δ over position + distance +0.001 [+0.000, +0.002]) |

Within trial, the candidate with the most survey intake is fixated later
in **96 %** of trials, the one with the least in **49 %** (n = 2,118 trials
with ≥ 3 candidates).

**Reading.** The survey does leave a map that the evaluate phase follows,
and it is a map of proximity: where the five survey fixations were is where
the eyes go afterwards, beyond position, and intake carries nothing beyond
distance. `pai_kernel_validation.md` shows this holds for every
eccentricity-aware kernel. Within 200 px (≈ 5°), 87 % of unfixated candidates receive
no survey intake at all, so the map covers five neighbourhoods, not the page.

## The account these two tests support

- The periphery's measurable job on a SERP is **local next-fixation
  guidance**: the reading-science role, one or two results ahead, captured
  entirely by proximity.
- It does not evaluate content (all cues null), it does not steer on
  format beyond reading order (A), and it does not guide returns
  (`return_is_memory.md`: long returns land at first-entry precision from
  memory with half the peripheral intake).
- Search on a results page is therefore **foveal and serial**, with the
  survey seeding a small proximity map and memory carrying the between-
  patch return. The peripheral sampling tier of the census is real and
  trait-like, but what is sampled is not used for anything the corpus can
  detect beyond where to look next.

That is a smaller role for the periphery than the pre-attentive-scan
intuition assigns it, and it is the role the data support.

## Caveats

- (A) uses "fixated at all"; a first-pass version would tighten the
  reading-order claim.
- (B) treats the NB13 five-fixation survey as fixed; a per-trial survey
  boundary from saccade amplitude would be stricter.
- Element type is one-hot over eight types; a richer format vector (image
  presence, price, star ratings from the DOM) is possible from the
  snapshots and not run.
- `[LAB]` only.
