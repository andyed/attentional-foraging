# 2026-05-05 — Y-pixel bbox coverage gap and the `typed_gapfill` mitigation

**Tag:** `[LAB, AdSERP, typed → typed_gapfill, audit-2026-05-05]`
**Sibling docs:** [`docs/methodology/attribution-cascade-synthesis.md §1.06`](../methodology/attribution-cascade-synthesis.md), [`docs/methodology/aoi-coverage-contribution.md`](../methodology/aoi-coverage-contribution.md), [`docs/methodology/organic-result-aoi-extraction.md`](../methodology/organic-result-aoi-extraction.md)

---

## TL;DR

Click attribution under `typed` AOI extraction was found to silently mis-attribute right-rail and inter-result-gap clicks via legacy Y-band assignment in `data_loader.click_to_position`. The hypothesis that bboxes had a systematic Y-pixel calibration drift was tested and **refuted**: clicks bias downward and fixations bias upward (opposite directions), consistent with where users look (title text, top of card) vs click (link area, center-of-card). The mitigation is a pragmatic midpoint-split gap-fill flavor (`typed_gapfill`) that extends adjacent organic bboxes to fill inter-result Y gaps, plus an `is_main_axis_click()` trial-level filter that drops the 158–231 hard-error trials whose final click is genuinely off-axis.

This is **not the right fix in principle** (the principled alternative is DOM-anchored bbox extraction, deferred as future work). It is a defensible heuristic that recovers signal previously dropped, with both the legacy `typed` and new `typed_gapfill` flavors kept queryable side-by-side so any K-claim can be reported under the flavor most apt to its question.

---

## §1. Discovery context

During AllSERP descriptive work on 2026-05-05 (resource-paper draft for the Latifzadeh, Gwizdka & Leiva SIGIR '25 dataset), an audit of click attribution under `typed` AOI extraction surfaced an unexpectedly high unattributed-click rate:

- 690 / 2,774 final clicks (24.9 %) did **not** strictly fall inside any typed AOI bbox.
- The legacy click-attribution helper (`data_loader.click_to_position`) silently absorbs these into Y-band-matched organic positions with no X check.
- Cross-checking a 4 % approached-and-clicked record sample against the AR replay viewer confirmed the contamination pattern visually on:
  - `p008-b3-t7` — right-rail (dd_right) ad click rolled into organic 3
  - `p009-b5-t2` — page chrome (search tools) click rolled into dd_top 0
  - `p041-b5-t2` — right-rail (no shipped dd_right rect) click rolled into organic 2
  - `p038-b4-t3` — off-target click 92 px right of column, rolled into organic 7
  - `p005-b2-t2`, `p006-b2-t7` — clicks in inter-result Y gaps rolled into adjacent organics

Two distinct contamination buckets emerged: **off-axis clicks** (right-rail, chrome, far-off-target) where the user clicked something other than a result, and **in-column-edge clicks** where the user clicked link-padding within the result column but just outside the row-projection-tight bbox.

---

## §2. The four audits

All four audit scripts live in `scripts/` (regime tag `[LAB, AdSERP, typed, audit-2026-05-05]`) and are independently runnable. Each produces a headline number cited below.

### §2.1 `audit_unattributed_clicks.py` — the gap exists

For each trial, take the final click (the trial-terminating choice) and check:
- did it land in any typed bbox?
- if not, what's its (x, y) and how does it relate to nearby bboxes?

**Headline:** 2,084 / 2,774 final clicks attributed (75.1 %) under tight bboxes. **80 % of the 690 unattributed clicks** land within ±10 px Y of an organic bbox edge with X strictly inside the result column — link-padding clicks. A further small slice has X just past the result column edge (off-axis right-rail or far-right chrome).

### §2.2 `audit_dd_right.py` — the right-rail blind spot

For each trial, load shipped `dd_right` rectangles from `AdSERP/data/ad-boundary-data/{tid}.json` and check whether the final click falls inside any.

**Headline:** 861 dd_right rectangles in corpus (one per 31 % of trials). **67 final clicks (2.41 %)** land inside a dd_right rect. All have X 910–1128, well outside the typed result column [162, 702]. Typed extraction filters dd_right by design (it is off the main scroll axis); the legacy Y-band attribution silently rolls these clicks into whatever organic shares their Y.

### §2.3 `audit_cascade_contamination.py` — magnitude and existing-filter check

For each of the 690 strict-bbox-unattributed final clicks, ask `click_to_position` what etype the Y-band rule would assign, and check whether the trial's `approached & clicked` record (`min_dist < 100`, `was_clicked=True`) is silently in the contaminated pool.

**Headline (Q1):** 687 / 690 unattributed clicks (99.6 %) are silently mis-attributed by the Y-band rule. By bucket:

| bucket | n trials | Y-band mis-attribution |
|---|---:|---:|
| dd_right (right-rail, shipped rect) | 67 | 67 (100 %) |
| right_chrome (X > 702, no dd_right) | 91 | 91 (100 %) |
| in_column_edge (X 162–702, Y just outside any bbox) | 532 | 529 (99 %) |

**Headline (Q3):** 391 of 1,723 `approached & clicked` records (**22.7 %**) come from contaminated trials. The "approached" gate (cursor `min_dist < 100` to the labeled AOI) does **not** filter contamination out — long cursor trajectories in the result column naturally end at a Y that's also inside some legitimate AOI's Y-band, so the gate aligns with the artifact.

### §2.4 `audit_calibration_bias.py` — calibration hypothesis tested and refuted

Hypothesis under test: the apparent +20 px downward click drift seen in 5 visually-inspected replay trials is a corpus-wide systematic Y bias (in either click ingestion or bbox extraction).

**Method:** for every (trial, click) and (trial, fixation) pair, measure signed Y-distance to the nearest typed bbox. Compare:
- attributed-click position within bbox (normalized [0, 1]; no bias → median 0.5)
- unattributed-click signed distance to nearest bbox (positive = below bbox bottom)
- same metrics for fixations
- per-participant breakdown

**Headline: REFUTED.**

| signature | clicks | fixations |
|---|---|---|
| Median position within bbox (norm) | 0.589 (slightly below center) | 0.440 (slightly above center) |
| Median raw offset from bbox center | +12.5 px | (n/a) |
| Unattributed median signed distance | +3.0 px | n/a |
| Unattributed asymmetry (below / total) | 314 / 533 = **59 %** | 15,257 / 51,459 = **30 %** |

If bboxes were Y-shifted, both streams would shift the same way. **They shift opposite directions.** Per-participant medians range 0.477–0.746 with no obvious calibration outliers.

The pattern is consistent with normal user behavior: people **look** at the top of result cards (title text — slight upward fixation bias) and **click** near the center-mass of the link target (slight downward click bias). The 5-example visual sample was selection-biased on small N — those trials happened to all show downward; the corpus is roughly symmetric.

### §2.5 `audit_screenshot_alignment.py` — confirms data is screenshot-aligned

Added after a separate concern surfaced: the gh-pages demo at `andyed.github.io/attentional-foraging` (Scrutinizer-rendered SERP replay overlaid with gaze/cursor) shows a median <13 px residual misalignment between rendered DOM elements and the original screenshot, attributed to re-rendering 2022 SERP HTML in 2026 (`docs/plan-demo-fix.md`). This raised the question: is the **underlying gaze/cursor data** itself misaligned with the original screenshots?

**Method:** the shipped AdSERP ad rectangles in `ad-boundary-data/{tid}.json` were extracted against the same screenshots that the gaze/cursor streams were recorded against — they're pixel-anchored to the truth source. For each trial's final click and longest fixation, compute signed Y-distance to the nearest shipped ad-rect edge (negative = inside; positive = outside).

**Result:**

| stream | inside ad rect | median signed Y | near-edge ratio (inside : outside in [-50, +50]) |
|---|---:|---|---|
| final clicks | 442 | −84 px | **152 : 39** (~4:1) |
| longest fixation/trial | 771 | −87 px | **393 : 179** (~2:1) |

A coordinate-space drift would produce accumulation just-outside ad edges (clicks at signed Y = +N where they should be inside). We see the opposite: deep median inside ads, near-edge ratio strongly favoring inside. **Data is screenshot-aligned.** The +12.5 px attributed-click bbox-center offset reported in §2.4 reflects where users click within a card (link region, slightly below visual center) — not a coordinate-space bug.

This separates the demo's known re-rendering misalignment (a viewer issue, 13–45 px) from the underlying data, which is correctly aligned to the screenshot truth source.

**Implication for any DOM-anchored extraction proposal:** the demo's residual error is the empirical ceiling on what HTML re-rendering can achieve (median <13 px, max ~45 px at page bottom). Re-rendering 2022 SERP HTML in 2026 produces layout drift of that magnitude. Therefore the AOI extraction pipeline must remain **screenshot-anchored** (CV row-projection on the original screenshots) with HTML used only for structural labels (widget typing via spatial join), not for geometry.

---

## §3. The midpoint-split mitigation (`organic_gapfill` / `typed_gapfill`)

### §3.1 Semantics

For each trial's organic bboxes, sort by Y-top, then iterate adjacent pairs:

```
gap = lower.top_y - upper.bottom_y
if gap > 0:
    midpoint = upper.bottom_y + gap // 2
    upper.bottom_y = midpoint - 1
    lower.top_y = midpoint + 1
```

When an obstacle (widget, dd_top, native_ad, dd_right) sits in the gap, clamp the split to its boundaries — never extend an organic across an ad/widget rectangle. Don't extend the first organic's top (would expand into chrome/header) or the last organic's bottom (would expand into pagination / refinement widgets).

### §3.2 Pragmatic, not principled

The midpoint heuristic is **not** the right way to identify the boundary between two adjacent results. The principled answer is DOM/CSS — the link element has a precise rendered geometry that we could pull from the AdSERP HTML snapshots. We have not done that work here; we are making an empirical choice (split the gap evenly) that is reproducible, reversible, and recovers signal that the legacy tight bboxes were silently dropping.

This is documented as such in every artifact:
- `attribute_click_to_typed_gapfill` docstring
- `attribution-cascade-synthesis.md §1.06`
- `aoi-coverage-contribution.md` table footnote
- the AllSERP data-tables draft methodology footnote
- this null-finding entry

The principled alternative (DOM-anchored extraction) is named and deferred as future work.

### §3.3 Hard-error trial filter

Even with gap-fill applied, the 158 dd_right + right_chrome + far-off-target trials have no defensible main-axis click target. They are filtered at the consumer via `data_loader.is_main_axis_click(trial_id)` — returns `False` if the trial's final click does not attribute to a main-axis AOI under `typed_gapfill` with default tolerance (±5 px X / ±10 px Y). Producers that compute click-outcome features (`compute_cursor_approach_features.py --attribution typed_gapfill`) drop these trials entirely.

In practice the filter excludes 231 trials (158 hard-error + ~73 trials with no clicks recorded or pathological click coordinates).

---

## §4. Headline shifts under `typed_gapfill`

### §4.1 AllSERP descriptives (`scripts/allserp_descriptives.py --flavor typed_gapfill`)

| metric | typed (legacy) | typed_gapfill | Δ |
|---|---:|---:|---:|
| total clicks attributed (any AOI) | 2,479 | 2,634 | +155 |
| organic n_clicks | 1,942 | 2,084 | +142 |
| organic fixated % | 52.7 | 55.6 | +2.9 pp |
| organic regressive-share % | 52.5 | 57.8 | +5.3 pp |
| paa fixated % | 32.8 | 40.6 | +7.8 pp |
| KP fixated % | 46.3 | 48.6 | +2.3 pp |
| dd_top metrics (ads not gapfilled) | unchanged | unchanged | — |

Big movers: paa widgets had especially tight bboxes; gapfill recovers ~8 pp of fixation coverage that strict bboxes were dropping.

### §4.2 cursor-approach features (`compute_cursor_approach_features.py --attribution typed_gapfill`)

| | legacy typed | typed_gapfill | Δ |
|---|---:|---:|---:|
| total records | 19,774 | 18,218 | −1,556 |
| `was_clicked=True` | 2,594 | 2,375 | **−219** |
| approached & clicked (`min_dist < 100`) | 1,723 | 1,562 | **−161** |
| organic clicked records | 2,021 | 1,886 | **−135** |
| native_ad clicked records | 186 | 137 | **−49** |
| dd_top clicked records | 271 | 245 | −26 |
| paa clicked records | 27 | 31 | **+4** |

The −135 organic and −49 native_ad clicks are the contamination from Y-band rolling dd_right + right_chrome + chrome clicks into those etypes. The +4 paa is genuine recovery — paa widgets had gap-tight bboxes.

---

## §5. What AllSERP can cite directly

The resource paper's methodology section can read:

> Click attribution under `typed` AOI extraction was found to silently mis-attribute right-rail and inter-result-gap clicks via legacy Y-band assignment ([`audit_cascade_contamination.py`], 22.7 % contamination of approached-and-clicked records, n = 391 of 1,723). The hypothesis that bboxes had a systematic Y-pixel calibration drift was tested and refuted ([`audit_calibration_bias.py`], opposite-direction bias in clicks vs fixations, refuting a single-direction shift in the bbox coordinate frame). The mitigation is a pragmatic midpoint-split gap-fill flavor (`typed_gapfill`) that extends adjacent organic bboxes to fill inter-result Y gaps, plus an `is_main_axis_click()` trial-level filter that drops trials whose final click is genuinely off-axis (n = 231, primarily right-rail dd_right ads and page chrome). Findings are reported under both the legacy `typed` and the new `typed_gapfill` flavors so readers can judge which is more apt to their question. The principled alternative — DOM-anchored bbox extraction — is named as future work.

Cite-ready file references:
- `scripts/audit_unattributed_clicks.py`
- `scripts/audit_dd_right.py`
- `scripts/audit_cascade_contamination.py`
- `scripts/audit_calibration_bias.py`
- `scripts/extract_organic_bboxes.py` (midpoint-split implementation, function `apply_midpoint_split`)
- `scripts/apply_gapfill_to_existing.py` (no-screenshot path; reads existing organic bboxes and writes gapfill)
- `notebooks-v2/data_loader.py` (gapfill helpers; `attribute_click_to_typed_gapfill`, `is_main_axis_click`)
- `scripts/output/allserp_descriptives_gapfill/` (per-etype table under typed_gapfill)
- `AdSERP/data/cursor-approach-features-typed-gapfill.json` (cursor approach + click attribution under typed_gapfill)
- `data/aoi-typed-gapfill/` (per-trial typed AOI maps with gapfill bboxes)

---

## §6. What's still unresolved

1. **DOM-anchored bbox extraction** — the principled alternative. The AdSERP HTML snapshots include the rendered link element geometry; we could anchor each organic bbox to the link's actual rendered extent. Estimated effort: 2–3 days. Not done in this cascade.

2. **AdSERP shipped dd_right rects are incomplete.** Audit of `p041-b5-t2` (visually confirmed right-rail click) found that AdSERP did not ship a dd_right rectangle for that trial despite the ad being present. The audit script counts only clicks that fall in shipped rects (67); the true right-rail click count is likely higher. Out of scope for this cascade.

3. **Per-K-claim shift quantification.** The cascade re-run for NB15 / NB21 / NB22 / NB28 / NB30 (steps 7–9 of the implementation plan) is pending. K-bbox-y-# rows will be added alongside legacy K-bbox-# rows when those notebooks are re-run, with the legacy rows annotated `(superseded YYYY-MM-DD: see K-bbox-y-#)` per the cascade rule. Until then the K-bbox-* values remain canonical for cited findings.

4. **AR replay viewer rebuild.** Visual verification of `typed_gapfill` bboxes on the 147-trial replay set is queued as step 10; this is a visual gate before any K-claim re-derivation propagates to the AR repo.

---

## §7. Lessons / methodological notes

- **Y-band-only click attribution is not a safe default.** A Y-band rule with no X check absorbs off-axis clicks silently into whatever main-axis AOI shares the Y. This was hidden under multiple flavors (`absolute`, `organic`, `organic_hybrid`, `typed`) until this audit because the artifact aligns with cursor-trajectory geometry on commercial-intent SERPs.

- **Refute a calibration-bias hypothesis with the *opposite* signal stream.** The clicks-vs-fixations comparison is the cleanest test: if bboxes are Y-shifted, both streams shift together; if user behavior differs (look-vs-click), the streams shift opposite. The 5-example visual sample alone could not have refuted the hypothesis — corpus statistics did.

- **Pragmatic post-processing is OK if labeled as such.** The midpoint-split is not "the right answer" — it is a defensible heuristic that recovers signal previously dropped, kept queryable side-by-side with the legacy flavor. The honest framing of "we have not done DOM-anchored extraction; here is what we did instead and why" is what makes the resource paper's methodology readable.

- **Audit scripts belong in `scripts/`, not `/tmp/`.** All four audits were initially developed under `/tmp/`; moving them to `scripts/` with regime tags and headline-number docstrings makes them cite-ready for the resource paper. Future audits should land in `scripts/` from the first pass.
