# Engagement has five states — the four-class taxonomy plus a peripheral tier

**Tags:** `[LAB, AdSERP, typed]` · peripheral = outside the typed band rect · **five kernel variants reported, one primary**
**Producer:** `scripts/engagement_state_census.py` (+ `states.csv`, one row per result slot). Variants under `scripts/output/engagement_state_census/`: `gate_200px/` (**primary**: published alpha, fixations further than 200 px ≈ 5° from the band contribute nothing), `gate_400px/` (≈ 9°), `kernel_boundary_cm_24/` and `kernel_boundary_cm/` (boundary-distance kernel with cortical-magnification falloff, 24 and 40 px/°), `summary.json` (the published PAI Eq. 2 ungated) and `kernel_listing/` (its other weight placement).
**Generated:** 2026-09-14, revised the same evening after the kernel finding below.

> **Read this first — the published kernel is flat on SERP bands.** On
> 638,963 fixation-band pairs from 600 trials, the published Eq. 2 alpha
> has Spearman −0.08 with rect-boundary distance; mean alpha is 0.46 within
> 50 px and 0.40 beyond 1,600 px; on the modal bands under 90 px tall it is
> 0.54 adjacent and 0.50 at 800 px and beyond; and 6.8 % of adjacent pairs
> get alpha 0 because the vertex distance exceeds the centroid distance
> below the middle of a wide band. The kernel was designed for compact
> polygons; on 540 × 80 px bands the vertex distance and the area weight
> remove the eccentricity dependence. Under it, "peripheral mass on this
> band" is a page-wide fixation-duration count weighted by band size: the
> mass-weighted median intake distance on never-fixated slots was 933 px.
> The first version of this note quoted 73 % from that kernel. Every share
> below is now reported as a function of how far the kernel looks, with an
> 200 px gate (≈ 5° at the derived 43 px/°) as the primary because it is the only definition that does not
> assume a falloff shape. The pixels-per-degree figure (24, the repo's
> convention from findings.md §3d-ii; 40 in the lit note) moves the gate
> between about 4° and 6° across the tracker's 50–80 cm operating range.

## Question

The consideration-set taxonomy (clicked / deferred / evaluated-rejected /
not-approached) is gaze- and cursor-defined and says nothing about results
the eyes never landed on. Between "not on screen" and "fixated" there is a
third condition: a result that was on screen, was never fixated, and
received peripheral intake anyway. Is that a real tier of engagement or a
geometric artefact, and how much of the page does it cover?

## Setup

- **Rows:** every main-axis typed AOI in the cursor-only typed buf500
  mousedown cache (hash-checked): **34,317 result slots, 2,607 trials, 47
  participants**. `was_clicked`, `etype`, `min_dist` from the cache.
- **Fixated / deferred / rejected:** fixations assigned by the label
  producer's own rule (`visit_decomposition`); deferred vs rejected from the
  NB22 label cache. 0 fixated rows lack a label.
- **On screen:** viewport residence from `scroll_only_carve.scroll_features`
  on the canonical scroll stream (cut at mousedown − 500 ms). 457 trials have
  no usable scroll stream; their 4,378 never-fixated slots are
  `unknown_opportunity` and excluded from the split below.
- **Peripheral intake:** full-trial spec_eq2 mass from fixations strictly
  outside the band.
- **Opportunity baseline (three rules, all reported).** A never-fixated,
  on-screen (≥ 500 ms) slot is *peripheral* if its intake is at or above the
  median of **fixated** slots of the same etype, where intake is:
  - **matched (primary):** mass per second of on-screen-*unfixated* time
    (residence minus the slot's own dwell). A fixated result's own reading
    time is not peripheral opportunity, so it is removed from its denominator.
  - **lenient:** mass per second of residence (fixated slots' rates are
    diluted by their own dwell).
  - **conservative:** raw full-trial mass (never-fixated slots are on screen
    less, so raw mass penalises them).

## Results

### The census (primary: intake within 200 px (≈ 5°), matched-opportunity rule)

| state | slots | share of 34,317 | witnessed by |
|---|---|---|---|
| never on screen | 8,279 | 24.1 % | scroll |
| brief on screen (< 500 ms) | 714 | 2.1 % | scroll |
| on screen, never fixated, **unsampled** | 1,847 | 5.4 % | PAI |
| on screen, never fixated, **peripheral** | 618 | 1.8 % | PAI |
| fixated, rejected | 6,077 | 17.7 % | gaze |
| fixated, deferred | 9,797 | 28.6 % | gaze |
| clicked | 2,607 | 7.6 % | cursor, click |
| opportunity unknown (no scroll stream) | 4,378 | 12.8 % | — |

The fixated and clicked rows do not depend on any kernel. Only the
unsampled / peripheral split does.

### The split that matters: never fixated but on screen (n = 2,465)

Peripheral = intake per second of on-screen-*unfixated* time at or above
the median of fixated slots of the same etype (the matched rule). The share
is a function of how far the kernel looks:

| kernel | reach | peripheral share | participant median [IQR] | skipped vs read at matched etype × position (AUC) |
|---|---|---|---|---|
| published Eq. 2, gated at 200 px (**primary**) | ≈ 5° | **25.1 %** | 0.27 [0.20, 0.37] | **0.33** (skipped get *less*) |
| published Eq. 2, gated at 400 px | ≈ 9° | 34.1 % | 0.38 [0.26, 0.52] | — |
| boundary distance, 1/(1 + E/2°), 43 px/° (2026-09-14 derivation; runs were made with 24 px/°, so E2 = 48 px ≈ 1.1°) | soft | 44.5 % | 0.53 [0.38, 0.60] | 0.46 (skipped get less) |
| boundary distance, 1/(1 + E/2°), 40 px/° | soft | 49.2 % | 0.56 [0.43, 0.65] | — |
| published Eq. 2, ungated (the 73 % row) | flat | 72.8 % | 0.79 [0.69, 0.85] | 0.60 (skipped get *more*) |

The last column is the honest version of the earlier "skipped results
receive more peripheral intake than read ones": that was the flat kernel.
Under any eccentricity-aware definition, a skipped result receives *less*
near-peripheral intake per unfixated second than a read result at the same
position. The periphery is thin on skipped results, not thick.

By etype under the primary: organic 25.7 % (n = 1,681), native_ad 22.1 %
(589). The raw-mass rule under the primary gives 2.7 %; it is the lower
bound and mostly measures how briefly skipped results are on screen.

### The CHIIR paper's "approached but never fixated" rows

The carve excludes 663 approached non-click rows because they were never
fixated (660 present here). Under the primary they split: **168
peripherally sampled, 374 unsampled**, 48 brief on screen, 8 never on
screen, 62 opportunity unknown (under the flat kernel it read 356 / 186).
The construct boundary the paper draws ("examined non-clicks") is right;
about a third of the excluded rows were taken in peripherally at read
level and passed by with the cursor, and most were not.

### What follows what (display order, row-normalised, boundary kernel 43 px/° (2026-09-14 derivation; runs were made with 24 px/°, so E2 = 48 px ≈ 1.1°))

| from ↓ / to → | never on | unsampled | peripheral | rejected | deferred | clicked |
|---|---|---|---|---|---|---|
| unsampled (n 1,279) | 0.13 | 0.36 | 0.08 | 0.24 | 0.14 | 0.01 |
| peripheral (n 977) | 0.29 | 0.06 | 0.24 | 0.19 | 0.10 | 0.01 |
| rejected (n 5,629) | 0.09 | 0.10 | 0.10 | 0.36 | 0.22 | 0.03 |
| deferred (n 9,797) | 0.00 | 0.02 | 0.01 | 0.25 | 0.52 | 0.19 |
| clicked (n 2,596) | 0.02 | 0.04 | 0.04 | 0.30 | 0.47 | 0.00 |

Deferred runs cluster (0.52 self-transition) and precede the click (0.19);
these rows do not depend on the kernel. A peripheral skip is followed by
the page ending or another skip more often than by a read.

## Reading

1. **A peripheral tier exists, and it is a quarter to a third of on-screen
   skips, not three quarters.** Within 200 px (≈ 5°) a quarter of the results a
   searcher passed over while they were on screen received as much
   near-peripheral intake per second as the results they went on to read;
   under a soft falloff the figure is 44 %. Most skipped results receive
   *less* near-peripheral intake than read results at the same position
   (AUC 0.33): the eyes get close to what they read. The "never examined"
   category of a click model is therefore partly wrong, not mostly wrong.
2. **The share is a per-participant trait** (primary: median 0.27, IQR
   [0.20, 0.37]; soft kernel: 0.53 [0.38, 0.60]). The ordering of
   participants is what the Q5 individual-differences lead should use, not
   the level, which is kernel-defined.
2b. **The published kernel is the method finding.** On wide, short bands
   it does not see eccentricity. That is the concrete, checkable
   observation to bring to the method's authors, with the boundary-distance
   falloff in `scripts/peripheral_kernel.py` as one proposal and the hard
   gate as the assumption-free alternative.
3. **A quarter of the page is never on screen.** 24 % of result slots never
   entered the viewport before the press. The between-patch "leave" decision
   is made before most of the page has been seen, on forced-choice trials
   where leaving the page is not even an option.
4. **For the cursor papers:** "approached but never fixated" is now
   "approached, peripherally sampled, passed by" for most of those rows. One
   sentence in the CHIIR limitations, no number change.

## Kernel sensitivity

Two different questions, answered separately.

**Weight placement (the manuscript's D2 ambiguity).** Under the ungated
published kernel, `eq2` vs `listing` agree on 98.3 % of peripheral /
unsampled calls (2,422 / 2,465) and every share moves under two points.
Weight placement does not matter.

**Eccentricity (whether the kernel sees distance at all).** This is what
moves the number, from 73 % to 25 %, and it is the substance of the
"read this first" note above. Intake eccentricity by state under the
boundary kernel (median per-slot mass-weighted distance): peripheral 611
px, unsampled 551, rejected 390, deferred 227, clicked 154. Even under a
1/(1 + E/2°) falloff the intake on never-fixated slots is dominated by far
fixations, which is why the hard gate is the primary.

## Caveats

- The threshold is relative to fixated slots of the same etype; the
  position-matched version is in `engagement_continuation.md` §(c) and is
  the source of the AUC column above.
- There is no kernel-free share. Any sentence that quotes one number must
  name the reach it assumes.
- Typed bands are contiguous, so peripheral mass on a slot is mostly
  parafoveal preview from fixations on its neighbours. That is the construct
  (preview at result grain), stated, not hidden.
- The 457 trials without a scroll stream are not missing at random (they are
  the trials with fewer than three scroll events before the cutoff, i.e.
  short pages or fast decisions), so the census shares are for the scrolled
  corpus.
- `[LAB]` only; every state but "clicked" needs an eye tracker.
