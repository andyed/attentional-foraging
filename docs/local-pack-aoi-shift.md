# Local-pack (maps) blocks and the typed-AOI rank shift

**Status:** fixed 2026-08-28 (Phase-1 extractor); typed maps rebuilt both
flavors. The residual card/bbox count-mismatch shift (below) was fixed the
same day by replacing index matching with y-aware geometric alignment —
see §Resolution.

**Provenance:** Sara Allawati (2026-08-28) flagged
AdSERPs where a Google Maps / local-results block sits in the main column
among the ranked results — e.g. p040-b4-t6 ("Camera Stores"),
p040-b1-t7 ("Grocery Stores") — with no corresponding AOI in the typed map.

## The bug

In 2022-era Google SERPs the local pack is rendered *outside* `#rso`, as a
sibling subtree (`div#Odp5De` under `.M8OgIe` under `#rcnt`), above the
first `#rso` card. Phase 1 (`scripts/extract_html_widget_types.py`) walked
only `#rso` / `#botstuff` / `#rhs`, so no HTML card was emitted for the
pack. The CV extractor *does* bbox the pack (it looks like a big main-column
card), and Phase 2 (`scripts/build_typed_aoi_map.py`) matches the k-th
non-ad bbox to the k-th main-column HTML card by index — so the pack's bbox
absorbed the first card's label and **every main-column label below it
shifted up one slot**. Same failure class as the dd_top cellsplit rank
shift ([dd-top-cell-promiscuity.md](dd-top-cell-promiscuity.md)).

The in-`#rso` variant of the pack was already detected (`g-map` element,
`kc:/local` data-attrid, "Local results" heading → `top_places`); the
out-of-`#rso` variant has none of those markers.

## Extent (audit_local_pack_aois.py, pre-fix state)

| quantity | value |
|---|---|
| trials with local-results content (`.uMdZh` / `rllt__`) | 353 / 2,776 (12.7%) |
| pack outside `#rso` (main column) → mis-shifted | **268 (9.7% of corpus)** |
| pack inside `#rso` (already typed `top_places`) | 85 |
| pack position in main column (post-fix) | 0–4, mode 1 (123 trials) |
| AOI slots below a pack in affected trials | 2,828 (mean 10.6/trial) |
| **organic AOIs whose rank was one slot early** | **1,930** (8.6% of 22,530) |

## The fix

`extract_html_widget_types.py` now detects `div.uMdZh` local-business
entries outside `#rso`/`#rhs`/`#botstuff` and emits one `top_places` card,
ordered by DOM position relative to `#rso` (in the corpus the pack always
precedes `#rso`). Heading comes from the visible `div.gsmt` pack header
("Camera Stores"), not the hidden a11y `h1` ("Search Results").

Post-fix, rebuilt `data/aoi-typed{,-gapfill}`:
`top_places` typed-map entries 86 → 354 (+268), matched card↔bbox pairs
25,587 → 25,848, unmatched bboxes 3,011 → 2,750, audit `n_mis_shifted`
268 → 0. Validation overlays (`scripts/verify_typed_aoi_map.py`, output in
`scripts/output/typed-aoi-verify/`) confirm both flagged trials and a
seeded 6-trial sample; p030-b4-t6 is a fully clean exemplar.

## Downstream exposure (rank-type disclosure rule)

Positions in `data/aoi-typed{,-gapfill}` changed for the 268 affected
trials (pack inserted at position 0–4; everything below +1). Consumers that
re-derive from these maps see moved ranks: `notebooks-v2/data_loader.py`,
`scripts/build_aois.py`, `add_etype_to_features.py` products
(`cursor-approach-features-typed*.json`), adsight features, layout
diversity, dd_top Markov extractor. Any typed-flavor K-ID computed on the
affected trials is `[typed, pending]` until re-derived.

**`organic`-flavor caveat:** the CV extractor's `organic_result` list still
contains the pack bbox as a phantom organic slot in these 268 trials (the
CV side has no type concept). The typed map now identifies which slot it
is; organic-flavor rank sequences are uncorrected. Anything ranked under
`organic` attribution in these trials carries a +1 rank inflation below the
pack.

## Residual known issue — count-mismatch index shift

The overlays surfaced a second, pre-existing member of the same failure
class: whenever the HTML card count ≠ CV bbox count in the main column,
the k-th↔k-th index matching shifts every label after the first mismatch
point. Two mechanisms observed on the flagged trials themselves:

- **CV over-segmentation** — p040-b1-t7's PAA block is two small bboxes
  (y=1097, y=1177), so labels below PAA sit one bbox early even post-fix.
- **HTML card merging** — p040-b4-t6 has two Amazon and two Ubuy results
  each nested in one unclassed wrapper div; Phase 1 emits one card per
  wrapper while CV bboxes each result, shifting labels below position 6.

Exposure: Δ = n_html_rso − n_bbox_main ≠ 0 in 1,909 / 2,776 trials
(Δ=−1: 950, Δ=−2: 541, …). A shift only occurs when the mismatch happens
*above* real content, so this was an upper bound.

## Resolution — y-aware geometric alignment (2026-08-28, same day)

Index matching is gone. The pipeline now measures real card geometry and
aligns on it:

**Phase 1.5** — `scripts/measure_card_geometry.py`: renders every SERP
snapshot (`AdSERP/data/serps-cached/`, offline assets) in headless
Chromium (Playwright, added to `pyproject.toml`) at the dataset's 1280 px
capture width and records each card's rendered page-space bbox, located
via a `css_path` Phase 1 now emits per card. Output:
`data/aoi-html-geometry/<tid>.json`. 2,776 trials, 0 errors; 745/30,614
cards (2.4%) have css_paths that miss in the browser DOM — those cards
sit out of alignment (`html_only+no_geometry`) rather than corrupting it.

**Phase 2** — `build_typed_aoi_map.py` replaces the k-th↔k-th match with:

1. **Monotonic DP alignment** (Needleman-Wunsch; gap penalties for
   unmatched bboxes/cards) between y-sorted CV bboxes and rendered cards.
   The Chromium re-render drifts progressively vs the dataset capture
   (fonts), so the DP runs under a per-trial linear map
   `dataset_y ≈ a + s·render_y`: pass 1 selects the best of several
   head-anchored scale candidates by DP cost (span-matching alone is a
   trap — card-less footer bboxes stretch the span and lock in a shifted
   local minimum); pass 2 refits with Theil-Sen on the matched pairs and
   realigns. Fitted slope lands near 0.90; corpus mean residual **2.6 px**,
   p90 **4.9 px**.
2. **Segment absorption** — an unmatched bbox whose center falls inside a
   matched card's corrected span merges into that card's entry (CV
   over-segmentation: split PAA rows, duplicate-domain sub-results).
3. **Span rescue** — an unmatched card (e.g. a 700 px+ in-`#rso` local
   pack that CV chopped into per-business segments, matching none 1-1)
   claims all unmatched bboxes whose centers fall in its span, as one
   union entry.

Trials without usable geometry fall back to legacy index matching
(`alignment_mode: index_fallback` in the audit; 2/2,776).

**Corpus outcome:** 2,774 trials aligned geometrically; 1,728 segment
bboxes merged; 764 cards span-rescued; spurious force-matches eliminated
(matched pairs 25,848 → 24,512 — the removed ~1.3k were index-matched
pairs with no geometric support, i.e. exactly the mislabeled ones);
`unknown_widget` entries 1,325 → 375. Local-pack audit unchanged at
`n_mis_shifted = 0`, main-column `top_places` = 352. Validation overlays
(`scripts/output/typed-aoi-verify/`) on both flagged trials now verify
label-correct end to end, including the regions below PAA/duplicate-domain
mismatches that stayed shifted after the pack fix alone.

**Downstream note:** this rebuild changes positions/labels in many more
trials than the 268-pack fix (any trial that had a count mismatch above
content). The `[typed, pending]` gate on affected K-IDs applies corpus-wide
until typed-flavor features are re-derived.

## Geometry verification pass (2026-08-28, follow-up on the 2.4% gap)

Inspecting the first geometry run's 745 `found:false` cards before the
downstream regen surfaced a worse defect than the miss count implied:
**html.parser and Chromium parse some SERPs into different trees.**
Observed mechanism: a right-rail knowledge panel (`TQc1id ... rhstc4`)
that html.parser keeps as an `#rso` child but Chromium re-parents up to
`#rcnt` (rendering at x≈804 — the right rail, matching the dataset
screenshots). Every later sibling's `nth-of-type` index then shifts by
one, so a bare `querySelector` silently measured the **next** element:
the 745 misses were just the last card falling off the end, while
**2,606 cards across those same 745 trials carried their neighbor's
geometry** — re-introducing an off-by-one below the divergence point.

Fixes (all landed same day):

- **Identity-verified measurement.** Phase 1 emits per-card identity
  fields (class tokens, heading, whitespace-stripped text length);
  `measure_card_geometry.py` accepts a measurement only when identity
  verifies, repairs failures by shifting the last `nth-of-type` index
  ±1..3 and re-verifying, and reports `found:false` otherwise instead of
  inventing geometry. Post-fix: 2,606 cards repaired (all shift −1),
  **57/30,638 (0.19%) unverifiable** — the honest gap.
- **Off-column routing.** A card whose verified rendered x sits far from
  the main-column median (the re-parented right-rail panels: 690 trials,
  one card each) is excluded from the main-column DP and parked at
  position −1 with `source: html_rendered_offcolumn`. Zero tall
  (>250 px) unmatched main-column bboxes exist in those trials — the
  original capture also rendered these panels in the right rail, so the
  routing matches ground truth corpus-wide.
- **Y-ordered DP input.** Cards enter the DP sorted by verified rendered
  y, not bs4 list order (which parser re-parenting can scramble).

**Quality gate (final form, after the suspect-trial deep dive).**
Dissecting the initial 48 flagged trials produced three further fixes
and a two-signal gate:

- **Outlier-pair filter.** The DP's cost cap made one terrible match
  (capped ~200–250) cheaper than skipping both sides (230), so a trial
  with sub-pixel alignment elsewhere could carry a single forced wrong
  pair (100–700 px residual — a mislabel). Pairs with residual above
  `max(100, 3·median+40)` are dropped; the freed bbox/card falls through
  to absorption / span rescue / honest unmatched. 356 such pairs across
  309 trials — most sat quietly *below* the old suspect threshold.
- **Tail/median fit anchors.** Head-anchored candidates alone anchor the
  fit in the region that renders most pathologically (top widgets: a
  maps block collapsing 367→140 px, a local pack expanding 93→553 px on
  p047-b5-t2), locking a one-slot-shifted compromise. Tail and median
  anchors sit in the stable organic run; adding them collapsed most
  "drifty" suspects to ~1 px (they were shifted, not drifting).
- **Owns-no-more-than-it-renders guard.** Absorption and span rescue
  refuse to grow an entry past 1.4× the card's rendered height, so a
  span test under drift cannot swallow a neighbor's bbox.

Corpus after all three: **mean residual 2.0 px, p90 4.6 px**. Suspect
flag is now two signals: `mean_residual > 30`, OR `mean_h_mismatch > 60`
with `mean_residual > 8` — height mismatch catches the failure
y-residuals cannot (an evenly spaced organic run is shift-periodic, so a
one-slot-shifted lattice has self-consistent y but pairs cards with the
wrong heights); the `resid > 8` guard keeps out correct lattices whose
widgets legitimately render divergent heights (verified on p036-b2-t6).
**14 trials (0.5%) remain flagged `alignment_suspect: true`** in
`scripts/output/aoi-typed/build_typed_aoi_map_audits.jsonl` — these are
shift-periodic pages with pathological widget rendering where a wrong
lattice cannot be ruled out geometrically. **Downstream re-derivation
should exclude or sensitivity-check them.** Related known issue, not
fixed: "Find results on" maps-block variants are Phase-1-typed
`image_pack`/`other_widget` via the ULSxyf heuristics.

## Regeneration policy — update in place (decision 2026-08-28)

This fix does NOT mint a new rank-type flavor or new artifact names.
Flavor names (`absolute` / `organic` / `organic_hybrid`, and the
`typed`/`typed_gapfill` attribution variants) exist to keep two
*meaningfully different attribution definitions* citable side by side;
the y-DP alignment is a correctness fix *within* the `typed` definition
(same taxonomy, same sources), and keeping the mis-aligned values
citable under their own name would enshrine a bug. So: same names, same
files, values re-derived in place; the paper trail is git history plus
this document. K-ID rows re-derived under the aligned maps get a
`(re-derived 2026-08-28: y-DP aligned typed maps)` annotation rather
than new IDs.

**The 14-trial exclusion** is a derivation filter, not a flavor:

- canonical list: `data/aoi-typed/alignment-exclusions.json` (tids +
  rule + provenance); applies to `typed` AND `typed_gapfill` (the
  exclusion derives from render geometry, not flavor)
- `data_loader.typed_alignment_exclusions()` exposes it;
  `load_typed_aois` / `load_typed_gapfill_aois` return `[]` for excluded
  trials, so every consumer going through the loaders (scripts and
  notebooks) drops them uniformly
- producers that read AOI files directly are gated explicitly
  (`compute_cursor_approach_features.py`, `adsight_noticed_features.py`)

**Regeneration state:** re-derived in place —
`cursor-approach-features-typed{,-buf500,-gapfill,-gapfill-buf500}.json`
(typed: 2,760 trials / 19,382 records; typed_gapfill: 2,538 / 17,926),
`retreat-arcs-typed.json`, `adsight-noticed-features-typed-gapfill.json`.
Still pending (notebook-tier, K-ID re-derivation):
NB14 → `butterworth-lfhf-by-position-typed.json`, NB18 →
`ripa2-by-position-typed.json`, then `compute_k_coefficient.py
--attribution typed` and `compute_saccade_orientation.py --attribution
typed` which consume them.
