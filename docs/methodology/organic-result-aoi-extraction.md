# Organic-Result AOI Extraction

**Stable ID:** M:organic-result-aoi-extraction
**Status:** v2 reference; CV bboxes here remain the geometry source of truth. The v3 typed cascade (2026-05-04, [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md)) builds on these bboxes by adding an HTML widget-typing pass and is now the post-cascade primary attribution. Canonical implementation for v2: `scripts/extract_organic_bboxes.py`. Applied to the full corpus (2,776 trials) via the volume-mounted Zenodo screenshots. Commit `60a2e7b9` on `feat/aoi-pipeline-v2` is the v2 reference state for the schema and audit numbers below.

This is a **core contribution** of the project to the AdSERP corpus. AdSERP v1 ships ad bounding boxes (`native_ad`, `dd_top`, `dd_right`) and full-page screenshots, but **no organic-result bounding boxes**, no per-product subdivision of the ad rails, and no separation of refinement widgets from organic results. The pipeline below recovers all four in pixel coordinates that mirror the v1 ad-boundary schema for drop-in compatibility.

---

## 1. The rule, in one line

For each trial, detect content-bearing card runs in the SERP main column (`COL_X=162, COL_W=586`) by row-projection on the grayscale screenshot, drop runs that overlap a shipped ad rectangle in **both** y and x, drop runs at or below the trial's widget y-floor (when the HTML signals refinement-widget headings), and number the survivors top-to-bottom as `organic_result[1..N]`. Tall organics (`>= COMPOSITE_TRIGGER_H`) are also fed into row-projection sub-segmentation and emit `organic_cell` entries that retain a back-pointer to the parent organic.

## 2. Why this rule

AdSERP per-rank analyses without this enrichment had two options, both bad:

1. **Band estimation** — divide the document height by `count_results_html(tid)` and assign each fixation to the nearest band. The bands are wrong wherever ads sit between organics, where rich snippets vary card height, or where bottom-of-page widgets are h3-anchored alongside organics. Per-result claims at this resolution silently mislabel any fixation on the AOI margin and silently include refinement-widget visits in the per-rank denominator.
2. **HTML-derived bboxes** — the SERP HTML snapshots ship with the corpus, but they don't carry rendered pixel coordinates. Re-rendering them in a headless browser is fragile (Google A/B-tests rendering, fonts drift, the snapshots aren't byte-stable). Most attempts fail trial-by-trial without a clear failure signal.

Row-projection on the screenshots themselves is the cheapest method that operates on the rendered pixels rather than the source HTML. Each AdSERP card is a vertically-bounded region of high pixel-variance separated from neighbors by a band of low pixel-variance whitespace. The detection rule:

```
content_row[y] = std(screenshot[y, COL_X : COL_RIGHT]) >= ROW_STD_THRESHOLD
```

A run of consecutive content rows is a card; a gap of `< GAP_MERGE` rows between runs is a within-card text-line gap (collapsed); a gap of `≥ GAP_MERGE` is a card boundary.

Three classification passes then run on each detected card:

**Ad subtraction (`is_ad`).** A card is reclassified as an ad iff it overlaps a shipped ad rectangle in **both** y and x. The earlier (y-only) version silently classified main-column cards as ads whenever a tall right-rail (`dd_right`) ad's y-span covered them, dropping real organics — the worst pre-fix under-counters had `pipeline=1` when `count_organic_ranks=9`. With x-overlap required, `dd_right` rails (x ≥ 750) no longer touch main-column cards (x = 162..748).

**Widget filtering.** AdSERP SERPs frequently render bottom-of-page refinement widgets (Related searches, People also search for) as cards in the main column. They aren't ads, so ad-subtraction leaves them in. Without filtering they appear as fake high-rank organics: 41% of trials over-counted by 1–6 organics in the audit. The filter combines two signals:

- HTML signal: walk the document for an `<h3>` whose text matches `WIDGET_HEADING_RE` (Related searches / People also search for, plus Spanish equivalents). If found, widgets exist on this trial.
- Layout signal: y-gap analysis on the post-ad-subtraction cards. Real organic results are vertically packed (median inter-card whitespace ~30–60 px). When trailing refinement widgets are present, a much larger empty band separates the last real organic from the first widget. The first card after the largest gap is the floor — provided the gap is both `> 3× median` and `> 150 px absolute`.

The HTML signal gates the layout signal: we only trust the gap-floor when the HTML confirms widgets exist. Cards at-or-below the floor land in `widget` instead of `organic_result`.

**Composite-organic sub-segmentation.** Local 3-packs, "People also ask" inline expansions, and image carousels emerge from `detect_cards` as a single tall organic. Per-result claims on these silently aggregate fixations across sub-listings. Any organic taller than `COMPOSITE_TRIGGER_H = 320 px` is fed into `subdivide_vertical` with parameters tuned for sub-listing geometry; if `≥ 2` sub-cells are found, they're emitted as `organic_cell` entries with `parent_position` pointing back to the parent organic. The parent's `position` (its rank) is unchanged — cells are a **second-column variable, not a rank overload**.

The same machinery is reused for two ad-rail outputs:

- **`dd_top_cell`** — vertical-edge peak detection on the dd_top carousel resolves it into per-product cells.
- **`dd_right_cell`** — row-projection inside the dd_right vertical product stack resolves it into per-product rows.

## 3. Where this lives in code

| Function | File | Role |
|---|---|---|
| `detect_cards(png_path)` | `scripts/extract_organic_bboxes.py:72` | Row-projection + gap-merge + min-card filter. Returns `[(y_top, y_bottom), ...]` for content runs in the main column. |
| `is_ad(card, ads)` | `scripts/extract_organic_bboxes.py:193` | Tests a card against shipped ad rectangles. Requires both y-overlap (≥ `AD_OVERLAP_THRESHOLD`) and x-overlap with `[COL_X, COL_RIGHT]`. |
| `subdivide_horizontal(png, bbox)` | `scripts/extract_organic_bboxes.py:98` | Vertical-edge peak detection on |dx| column-summed across bbox rows. Used for dd_top carousels. |
| `subdivide_vertical(png, bbox)` | `scripts/extract_organic_bboxes.py:147` | Row-projection inside a parent bbox. Used for dd_right product stacks **and** composite-organic sub-segmentation. |
| `find_widget_y_floor(trial_id)` | `scripts/extract_organic_bboxes.py:214` | HTML walk for widget-heading h3s. Returns the band-y backstop floor when widget heading is found, or None. |
| `_widget_floor_from_gap(spans)` | `scripts/extract_organic_bboxes.py:276` | Layout-aware floor: the y of the first card after the largest anomalous inter-card gap. Preferred over the band-y backstop when both are available. |
| `extract_trial(trial_id)` | `scripts/extract_organic_bboxes.py:311` | Top-level orchestrator. Detection → ad subtraction → widget classification → composite sub-segmentation → output JSON. |
| `render(trial_id)` | `scripts/verify_organic_bboxes.py:23` | Visual verification. Writes screenshot + colored bbox overlay. Spot-check tool, not a corpus validator. |

Output schema (per trial JSON in `AdSERP/data/organic-boundary-data/{trial}.json`):

```json
{
  "organic_result":  [{"position": 1, "location": {...}, "size": {...}}, ...],
  "widget":          [{"position": 1, "location": {...}, "size": {...}, "reason": "below_widget_y_floor"}, ...],
  "organic_cell":    [{"position": 1, "parent_position": 5, "location": {...}, "size": {...}}, ...],
  "native_ad":       [...],
  "dd_top":          [...],
  "dd_right":        [...],
  "dd_top_cell":     [...],
  "dd_right_cell":   [...],
  "_meta": {
    "trial": "p007-b6-t8",
    "card_count": 16,
    "organic_count": 9,
    "widget_count": 1,
    "widget_y_floor": 2597,
    "organic_cell_count": 0,
    "dd_top_cell_count": 4,
    "dd_right_cell_count": 0,
    "flags": ["organic_3_suspiciously_tall_h=412"],
    "params": {...}
  }
}
```

The schema is **additive** to AdSERP v1's ad-boundary JSON shape. Old top-level keys (`native_ad`, `dd_top`, `dd_right`) pass through unchanged; new keys are added without renaming or restructuring v1 fields.

## 4. Parameters

All thresholds are emitted into `_meta.params` per trial so a downstream consumer can verify the configuration that produced any given output.

### Card detection (main column)

| Parameter | Default | What it controls |
|---|---|---|
| `COL_X` | 162 px | Left edge of the SERP main column on Google ES with `hl=en`. |
| `COL_W` | 586 px | Main column width. Picks the larger of observed `dd_top` and `native_ad` widths to avoid right-edge clipping. |
| `ROW_STD_THRESHOLD` | 3 | Per-row pixel-std cutoff below which a row is "blank." |
| `GAP_MERGE` | 24 px | Maximum vertical gap that's still considered within-card. |
| `MIN_CARD_H` | 50 px | Drop merged runs shorter than this. Filters favicon strips, breadcrumbs, "People also ask" sub-rows. |
| `SUSPICIOUS_H` | 350 px | Cards taller than this get a `_meta.flags` entry for human spot-check. Audit threshold, not a filter. |

### Ad subtraction

| Parameter | Default | What it controls |
|---|---|---|
| `AD_OVERLAP_THRESHOLD` | 0.5 | Card classified as an ad iff y-overlap ≥ this fraction of card height **AND** ad's x-extent intersects `[COL_X, COL_RIGHT]`. |

### Widget filter

| Parameter | Default | What it controls |
|---|---|---|
| `WIDGET_HEADING_RE` | regex | Matches widget heading h3 text: `Related searches`, `People also search for`, plus Spanish equivalents (`Búsquedas relacionadas`, `Otras personas también buscan`). HTML signal that widgets exist on the trial. |
| Gap-floor `min_multiplier` | 3.0 | Largest inter-card gap must exceed this multiple of the median gap to qualify as the widget y-floor. |
| Gap-floor `min_absolute_px` | 150 | Largest inter-card gap must also exceed this absolute floor (suppresses false positives on very dense or very sparse SERPs). |
| `find_widget_y_floor` band-y backstop | n/a | When the gap heuristic is inconclusive but the HTML still signals widgets, fall back to the band-y estimate computed via `absolute_rank_band_tops`. |

### Composite-organic sub-segmentation

| Parameter | Default | What it controls |
|---|---|---|
| `COMPOSITE_TRIGGER_H` | 320 px | Organics taller than this are candidates for sub-segmentation. Sized below `SUSPICIOUS_H` so most flagged tall cards are tested. |
| `COMPOSITE_GAP_MERGE` | 12 px | Tighter than top-level `GAP_MERGE` — sub-listings inside a composite sit closer than full organic cards do. |
| `COMPOSITE_MIN_CELL_H` | 60 px | Filters sub-listing chrome (rating bars, divider lines). |
| `COMPOSITE_STD_THRESHOLD` | 3 | Same as top-level row-projection. |

### Ad-rail cell subdivision

| Parameter | Default | What it controls |
|---|---|---|
| `subdivide_horizontal` `peak_height_frac` | 0.4 | Vertical-edge peaks must reach 40% of the column max edge magnitude to qualify as carousel-cell boundaries. |
| `subdivide_horizontal` `peak_distance` | 80 px | Minimum cell width. |
| `subdivide_vertical` `gap_merge` | 12 px | Same role as top-level `GAP_MERGE`, tuned for the denser dd_right layout. |

## 5. Sensitivity tested

### 5.1 Pipeline-vs-h3 alignment audit (full corpus, n=2,776; 2026-05-01)

Compared `_meta.organic_count` (pipeline) to `count_organic_ranks(tid)` (HTML-derived organic-h3 count, ad-overlapping h3s excluded). Note: `count_organic_ranks` is **not** ground truth — it includes widget-heading h3s ("People also ask", "Related searches") as "organic" slots, so a pipeline result of `delta < 0` is sometimes the pipeline being correctly stricter than the HTML enumeration.

```
exact (delta=0):     683/2,776 = 24.6%
|delta| ≤ 1:       1,801/2,776 = 64.9%
|delta| ≤ 2:       2,451/2,776 = 88.3%
mean:                                -0.20
median, IQR:               0,  [-1, 0, +1]
distribution: symmetric around 0, long thin left tail
```

The within-±1 figure (64.9%) is the right framing for downstream consumers: most disagreement is small and within the noise expected from two independent enumerations of the same SERP. Within ±2 captures 88% of the corpus.

### 5.2 Widget filter activity

```
trials where filter fired:    1,652 / 2,776 = 59.5%
total widgets caught:                             2,206
```

Not every trial has refinement widgets — only those with HTML widget headings AND a layout-detected gap. The remaining 40.5% of trials produced zero widgets, either because their SERPs had no refinement widgets or because the gap heuristic was inconclusive (and no band-y backstop fired).

### 5.3 Composite-cell activity

```
trials with composite cells: 166 / 2,776 = 6.0%
total cells emitted:                          376
```

Composite organics (local 3-packs, multi-row PAA expansions, image carousels) are real but uncommon in the AdSERP corpus, which is dominated by transactional product queries.

### 5.4 Tolerance-aware click attribution audit (full corpus, n=2,775)

`data_loader.attribute_click_to_organic(click_y, trial_id, tolerance_px=30)` snaps clicks within 30 px of an organic edge to that organic, rejecting clicks inside any ad / widget rectangle first. The 30 px elbow was chosen empirically: 92.5% of off-AOI clicks are within 30 px of the nearest organic edge; further loosening (50, 100, 200 px) rescues only ~0.3 percentage points more.

Click bucket distribution under tolerance-aware bbox attribution:

| Bucket | Count | Share |
|---|---|---|
| Organic (strict containment + 30 px snap) | **2,181** | **78.6%** |
| All ads (`native_ad` + `dd_top` + `dd_right`) | 557 | 20.1% |
| Filtered widgets (`Related searches`, `People also search for`) | 5 | 0.2% |
| Truly off-AOI (KP / image carousel / footer / large gaps) | **32** | **1.2%** |

For comparison, strict containment (`tolerance_px=0`) attributes only 64.3% of clicks to organic AOIs — the remaining 14.3% land in the small visual gaps between adjacent organic rectangles (median 10 px, P75 15 px, P90 22 px). Those gap clicks are visual-margin artifacts, not off-AOI events; the 30 px tolerance correctly recovers them.

The headline: **78.6% of clicks on organic, 20.1% on ads, 1.2% on content the pipeline doesn't model**. The 1.2% is the actual methodology-limitation residual (Knowledge Panel, image carousel, large-gap content) — not 15.4% as the strict-containment number would suggest.

### 5.5 Built-in invariants

- **Reproducibility metadata.** `_meta.params` records every threshold per trial. Any extracted JSON is self-describing and reproducible by re-running with the recorded parameters.
- **Schema parity with AdSERP v1.** Top-level keys for shipped ad data (`native_ad`, `dd_top`, `dd_right`) pass through unchanged. New keys are additive.
- **Self-flagging on tall cards.** `SUSPICIOUS_H = 350 px` flags non-composite candidates for human review.
- **Visual spot-check tool.** `scripts/verify_organic_bboxes.py` renders any trial's bbox overlay on the source screenshot. Per-trial dev tool; not a systematic validator.

## 6. Sensitivity NOT tested

Ordered by likelihood of changing a downstream result.

1. **Inter-rater agreement on hand-labeled organics.** No human-labeled gold standard exists for any subset of trials. Without it, "pipeline vs h3" disagreement is bidirectional and we can't report precision/recall.
2. **Threshold sweep on `ROW_STD_THRESHOLD`, `GAP_MERGE`, `MIN_CARD_H`.** Each parameter has a defensible default but no formal robustness sweep. A `{2, 3, 5} × {16, 24, 32}` grid would establish the parameter envelope.
3. **`AD_OVERLAP_THRESHOLD` sensitivity.** 0.5 is a defensible boundary but not tested at 0.3, 0.7, or 1.0.
4. **Widget-filter parameter sweep.** Gap multiplier (3.0) and absolute floor (150 px) were tuned empirically on a handful of visual spot-checks. A larger held-out set would validate these.
5. **Right-pane non-ad widgets are invisible.** The row-projection scan is bounded by `[COL_X, COL_X+COL_W]` (162..748). Maps panels, knowledge panels, and any other right-pane non-ad widget that AdSERP doesn't ship as a `dd_right` ad rectangle is never seen. Per-trial AOI inventories under-count visible content for any SERP that renders right-pane non-ad widgets.
6. **`dd_top` carousel cell precision on dense layouts.** The `find_peaks` edge-detector on the carousel can miss low-contrast dividers between adjacent product cards or fire on intra-card vertical edges (product-image silhouettes). A 5-card carousel can come out as 4 cells. A whitespace-based alternative was tested 2026-04-30 and regressed worse (cards touch with no whitespace columns); the current edge-peak version is the least-bad option pending a hybrid signal.
7. **Sub-pixel separator robustness on `dd_top` carousels.** Cards with no whitespace between them rely on the vertical-edge peak detector; carousels with low contrast between products may produce spurious or missing peaks.
8. **Cross-rendering stability.** All extractions ran against the screenshots shipped in AdSERP v1. If Google re-renders these queries, the column geometry will shift; the pipeline does not detect column-width drift.
9. **Inline / mid-page widget content is not classified as widget.** PAA expansion accordion items (each ~30–40 px tall, below `MIN_CARD_H = 50`) are silently dropped at the detection step — they don't appear as cards, organics, or widgets. PAA *headings* (where present and tall enough to detect) survive as a single short organic. "Related searches" *dropdown* items above a PASF grid (Andy's `t4` and `t10` cases) similarly pass through to organic_result rather than `widget`. The widget filter is bottom-of-page-only by design (HTML signal + y-gap heuristic). Inline widgets need a different signal — possibly per-card content classification (look for pill clusters, magnifier icons) or HTML container-aware extraction.
10. **Knowledge-Graph entity cards classified as organic_1.** Album cards, brand cards, person cards, and similar entity panels at the top of the SERP appear as one tall card in the row-projection; if they don't overlap any shipped ad rectangle (which they typically don't), they emerge as `organic_result.position=1`. Distinguishing them requires an HTML container check (h3 lives in `#kp-*` vs `#rso`) — not implemented. Andy's `p016-b3-t1` (Eric Clapton album) is the worked example. Click and fixation attribution in those trials is biased by ~one position (rank-0 dominance gets concentrated on the entity card rather than the first true result).

## 7. What's robust regardless of tweaking

- **The schema.** Output JSON shape, key names, integer pixel coordinates, and structural parity with AdSERP v1 ad-boundary files are fixed by the contract. Any methodology tweak that produces different bboxes still produces the same JSON shape.
- **The ordering rule.** Cards are numbered top-to-bottom by `y_top`. Independent of detection thresholds.
- **Rank semantics are unchanged by sub-segmentation.** `organic_result[].position` is the canonical AdSERP rank (1, 2, 3, …) and **does not change** when an organic happens to be a composite. `organic_cell.parent_position` points back to the parent organic; `organic_cell.position` is a within-parent ordinal. Cells are a **second-column variable**, never a rank overload. Per-rank analyses aggregate over all cells of a parent; per-cell analyses use `parent_position` × `cell_position` as an independent axis.
- **Widgets are AOIs, not organics.** `widget` entries live in their own top-level key; downstream consumers should never see them in the organic-rank denominator. Default exposure is opt-in (`include_widgets=False` in any future `data_loader.load_aois` API).
- **Reproducibility metadata.** `_meta.params` records every threshold used per trial.
- **Provenance separation.** Shipped ad rectangles pass through unchanged; the pipeline's contributions (`organic_result`, `widget`, `organic_cell`, `dd_top_cell`, `dd_right_cell`) are keyed separately. Downstream code can mix v1 ad data with v1.x enrichments without ambiguity.

## 8. Limitations to disclose in papers

- **No hand-labeled gold standard.** Per-rank claims that depend on bbox precision should note: "organic AOIs were extracted by row-projection CV (`scripts/extract_organic_bboxes.py`); validation is alignment with HTML h3-organic count (within ±1 on 64.9% of trials, within ±2 on 88.3%) plus visual spot-check, not against an inter-rater-agreed reference."
- **Bidirectional disagreement.** `pipeline_organic_count != count_organic_ranks` does not imply the pipeline is wrong. The HTML enumeration includes widget-heading h3s as "organic" slots; the pipeline correctly excludes them via the widget filter. Treat per-rank claims at high ranks (≥ 8) with extra caution because that's where widget contamination concentrates in either direction.
- **Right-pane content invisibility.** Maps panels, knowledge panels, and image carousels rendered to the right of the main column are never measured by this pipeline.
- **Column-geometry assumption.** `COL_X=162, COL_W=586` is fixed for `google.es?hl=en` 2024 desktop renders. Re-running on any other corpus requires column-geometry measurement.
- **Composite-organic detection threshold.** `COMPOSITE_TRIGGER_H = 320 px` is a defensible default but tuned empirically. Composites shorter than 320 px (e.g., a 2-row PAA expansion) currently emerge as a single organic.
- **`dd_top_cell` and `dd_right_cell` are heuristic.** AdSERP v1 treats each ad rail as one rectangle; this pipeline subdivides where the visual structure permits but doesn't validate per-cell labeling against any external rendering. `dd_top_cell` precision on dense carousels is acknowledged in §6.6.

## 9. Where this rule appears in published / draft work

- **AdSERP corpus enrichment** — primary artifact. JSON files in `AdSERP/data/organic-boundary-data/` (2,776 trials as of 2026-05-01, full-corpus run complete). Schema mirrors v1 ad-boundary JSON; intended for direct concatenation into the dataset.
- **README §Augmentations contributed by this project** — listed as the headline enrichment.
- **`notebooks-v2/data_loader.py`** — `extract_serp_results` and band-fallback path consume these JSONs when present; future `load_aois` API will add `include_widgets` / `include_cells` flags.
- **CIKM 2026 paper-v3, §3 (data)** — every per-rank claim that uses pixel-accurate AOIs depends on this enrichment.
- **`approach-retreat`** — AOI-based retreat geometry uses these bboxes for the AdSERP testbed at andyed.github.io/approach-retreat/replay/.
- **Upstream conversation with AdSERP authors** (Latifzadeh / Gwizdka / Leiva) — candidate v1.1 release: organic + widget + cell JSONs back-contributed to Zenodo. **Not yet initiated.**

## 10. Status

**Status:** v2 reference; superseded as primary attribution by v3 typed cascade (2026-05-04). The CV bboxes produced by this pipeline are unchanged and remain the geometric source of truth for v3. Canonical v2 implementation: `scripts/extract_organic_bboxes.py`. Applied to the full corpus (2,776 trials). Notebook + producer cascade complete on branch `feat/aoi-pipeline-v2` (origin head `411851fa`).

**Successor:** [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md) (v3 HTML+vision joint widget typing). v3 reuses every bbox this pipeline produces and adds a per-card etype label via a Phase-1 HTML pass + Phase-2 spatial join. No geometric change. Read v3 for the post-2026-05-04 primary attribution; read this doc for the underlying CV mechanics.

History:

- 2026-04-08 — design captured in `docs/plans/forward-regressive-split.md` (separate methodology); same-day `extract_organic_bboxes.py` first commit.
- 2026-04-30 — methodology doc created with original framing (v1 schema, n=86 partial coverage, no widget filter, y-only `is_ad`).
- 2026-05-01 — three pipeline corrections shipped (`60a2e7b9`): `is_ad` x-overlap fix, refinement-widget filter, composite-organic sub-segmentation. Schema gained `widget`, `organic_cell` top-level keys plus `_meta.widget_count`, `_meta.widget_y_floor`, `_meta.organic_cell_count`, and three composite parameters in `_meta.params`. Full-corpus extraction (2,776 trials).
- 2026-05-01 — band-y guard against featured-snippet false positives (`da0a8aae`). Without it, the gap heuristic over-fired on Knowledge-Graph trials (e.g. p016-b3-t1, p033-b3-t10), eating real organics into the widget category.
- 2026-05-01 — consumer API in `data_loader.py` (`load_aois`, `organic_aoi_bands`, `organic_aoi_tops`); producer migrations for `compute_butterworth_lfhf.py` and `compute_ripa2.py` with `--attribution {absolute,organic}` flag; full-corpus organic-attribution sibling JSONs (`*-organic.json`).
- 2026-05-01 — tolerance-aware click attribution (`9249ebce`): `attribute_click_to_organic(click_y, trial_id, tolerance_px=30)` rescues 14.3 percentage points of clicks that strict containment lost to visual-margin gaps. See §5.4.
- 2026-05-01 — `compute_cursor_approach_features.py` extracted from NB15 into a standalone producer with `--attribution organic` (`8bb800fd`); cursor-approach-features-organic.json (14,760 records, 2,701 trials) unblocks NB20/21/24/28.
- 2026-05-01 — `compute_retreat_arcs.py` extracted from NB24 with `--attribution {absolute, organic_hybrid}` (`234700e9`). Retreat-as-lateral-displacement claim REPLICATES under bbox (top-ad lateral/arc 0.166 → 0.170; organic vs top-ad MW p=1e-5 → p=4e-17).
- 2026-05-01 — Notebook K-claims migrations: NB14 + NB18a (`16830c62`), NB25 (`352084f7`), NB23 K-bbox-* tier (`452554ca`), NB04 + NB22 + NB24 + NB15 (`b5fb9f48`). All cite this methodology doc as the source for attribution shift.
- 2026-05-01 — `update_key_claims.py` guarded with `--force-clobber` flag (`411851fa`) to prevent accidental regression of cascade-aware K-claims by the script's pre-cascade hardcoded values.
- 2026-05-01 — Approach-retreat parallel rebuild on `feat/aoi-rebuild-2026-05-01`: 80 curated replay bundles regenerated; 13 stale captions fixed; 1 trial swapped (p020-b1-t7 → p012-b4-t7) because its EVAL-REJ profile vanished under bbox attribution.
- 2026-05-04 — v3 typed cascade landed on `feat/aoi-pipeline-v3-typed`. v2 bboxes unchanged; v3 adds Phase-1 HTML widget extraction (`scripts/extract_html_widget_types.py`) and Phase-2 spatial join (`scripts/build_typed_aoi_map.py`) to attach a 9-etype taxonomy on top of v2 geometry. Tier-A notebook re-execution + producer migration + Jacek-facing cross-lab export at `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 9 etypes). Spec: [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md).

**Pending downstream work** (deferred to ETTAC weekend / next iteration):
- ETTAC paper draft revisions to incorporate the bbox-attribution shift (NB14:K3 weakens; NB14:K6, K9 strengthen; reframe to two-band engagement).
- NB28 viewport bands and NB21 click-prediction LOSO retrain — both consume `cursor-approach-features-organic.json` and need `regression_labels_cache_organic.json` (producer ready: `scripts/compute_regression_labels.py`).
- M5 classifier retraining against organic-attribution NB22 labels — currently the AR demos run M5 inference against new bboxes with old coefficients.
- Aggregate doc (`docs/notebook-key-claims.md`) regeneration — `update_key_claims.py` needs its hardcoded `body_md` values updated or refactored to read from notebooks. Until then in-notebook K-claims are canonical.

Post-meeting context, 2026-04-30: Jacek Gwizdka flagged this work positively in the RIPA2 team meeting with the qualifier "if not at scale." The full-corpus extraction (2,776 trials, 2026-05-01) closes the loop on the scale concern; the consumer-side cascade (K-claims migrations, AR rebuild, paper-draft prep) is what makes the pipeline's claims load-bearing for the ETTAC and CIKM submissions.
