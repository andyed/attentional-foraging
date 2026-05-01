# Organic-Result AOI Extraction

**Stable ID:** M:organic-result-aoi-extraction
**Status:** current as of 2026-04-30; canonical implementation: `scripts/extract_organic_bboxes.py`. Applied to 86 trials to date; full-corpus run (n=2,776) pending.

This is a **core contribution** of the project to the AdSERP corpus. AdSERP v1 ships ad bounding boxes (`native_ad`, `dd_top`, `dd_right`) and full-page screenshots, but **no organic-result bounding boxes**. Per-rank claims previously had to rely on band estimation from h3 count and document height. The pipeline below recovers per-trial organic AOIs in screenshot pixel coordinates, plus per-cell subdivisions of the dd_top carousel and dd_right product stack.

---

## 1. The rule, in one line

For each trial, detect content-bearing card runs in the SERP main column (`COL_X=162, COL_W=586`) by row-projection on the grayscale screenshot, merge text-line gaps, drop runs that overlap any shipped ad rectangle by ≥ 50%, and number the survivors top-to-bottom as `organic_result[1..N]`.

## 2. Why this rule

AdSERP per-rank analyses pre-enrichment had two options:

1. **Band estimation** — divide the document height by `count_results_html(tid)` and assign each fixation to the nearest band. Cheap, but the band edges are wrong wherever an ad sits between organics, where a knowledge panel intrudes, or where snippet rendering varies card height. Per-result claims at this resolution silently mislabel any fixation on the AOI margin.
2. **HTML-derived bboxes** — the SERP HTML snapshots ship with the corpus, but they don't carry rendered pixel coordinates. Re-rendering them in a headless browser is fragile (Google A/B-tests rendering, fonts drift, the snapshots aren't byte-stable). Most attempts fail trial-by-trial without a clear failure signal.

Row-projection on the screenshots themselves is the cheapest method that operates on the rendered pixels rather than the source HTML. Each AdSERP card is a vertically-bounded region of high pixel-variance separated from neighbors by a band of low pixel-variance whitespace. The row-projection rule:

```
content_row[y] = std(screenshot[y, COL_X : COL_RIGHT]) >= ROW_STD_THRESHOLD
```

A run of consecutive content rows is a card; a gap of `< GAP_MERGE` rows between runs is a within-card text-line gap (collapsed); a gap of ≥ `GAP_MERGE` is a card boundary. After detection, any card whose y-range overlaps a shipped ad rectangle (`native_ad`, `dd_top`, or `dd_right`) by ≥ `AD_OVERLAP_THRESHOLD` is discarded; the remainder are numbered top-to-bottom as organic results.

The same machinery is reused for two additional outputs the dataset's intended granularity left implicit:

- **`dd_top_cell`** — vertical-edge peak detection on the dd_top carousel resolves the carousel into per-product cells.
- **`dd_right_cell`** — row-projection inside the dd_right vertical product stack resolves it into per-product rows.

These cell-level subdivisions enable per-product-card analyses on the ad rails that dataset v1 treats as monolithic blocks.

## 3. Where this lives in code

| Function | File | Role |
|---|---|---|
| `detect_cards(png_path)` | `scripts/extract_organic_bboxes.py:51` | Row-projection + gap-merge + min-card filter. Returns `[(y_top, y_bottom), ...]` for content runs in the main column. |
| `is_ad(card, ads)` | `scripts/extract_organic_bboxes.py:165` | Tests a card against the shipped ad rectangles via fractional y-overlap. |
| `subdivide_horizontal(png, bbox)` | `scripts/extract_organic_bboxes.py:77` | Vertical-edge peak detection (scipy `find_peaks`) on |dx| column-summed across bbox rows. Used for dd_top carousel. |
| `subdivide_vertical(png, bbox)` | `scripts/extract_organic_bboxes.py:119` | Row-projection inside a parent bbox. Used for dd_right product stack. |
| `extract_trial(trial_id)` | `scripts/extract_organic_bboxes.py:173` | Top-level: orchestrates detection, ad subtraction, cell subdivision, output JSON construction. |
| `render(trial_id)` | `scripts/verify_organic_bboxes.py:23` | Visual verification: writes screenshot + bbox overlay to `scripts/output/organic-bbox-verify/{trial}.png`. Spot-check tool. |

Output schema (per trial JSON in `AdSERP/data/organic-boundary-data/{trial}.json`):

```json
{
  "organic_result": [{"position": 1, "location": {"x": ..., "y": ...}, "size": {"height": ..., "width": ...}}, ...],
  "native_ad":      [...],
  "dd_top":         [...],
  "dd_right":       [...],
  "dd_top_cell":    [...],
  "dd_right_cell":  [...],
  "_meta": {
    "trial": "p007-b6-t8",
    "card_count": 16,
    "organic_count": 5,
    "dd_top_cell_count": 0,
    "dd_right_cell_count": 0,
    "flags": ["organic_3_suspiciously_tall_h=412"],
    "params": {...}
  }
}
```

The schema deliberately mirrors AdSERP v1's ad-boundary JSON shape so a single loader can read both with a structural union.

## 4. Parameters

All thresholds are emitted into `_meta.params` per trial so a downstream consumer can verify which configuration produced any given output.

| Parameter | Default | What it controls | Sensitivity |
|---|---|---|---|
| `COL_X` | 162 px | Left edge of the SERP main column on Google ES with `hl=en`. | Hardcoded; would shift if Google changes left-rail width. |
| `COL_W` | 586 px | Main column width. Derived from observed `dd_top` and `native_ad` widths (540 / 586) — picks the larger to avoid clipping at the right edge. | Hardcoded; same shift risk as `COL_X`. |
| `ROW_STD_THRESHOLD` | 3 | Per-row pixel-std cutoff below which a row is "blank." | Drives card-edge sensitivity. Higher → more forgiving of text gaps; lower → more cards split. **Not yet swept.** |
| `GAP_MERGE` | 24 px | Maximum vertical gap that's still considered within-card. | Drives card-merging behavior. Lower → more cards (text lines split into separate cards); higher → more under-segmentation (suspicious-tall flag picks up the failures). |
| `MIN_CARD_H` | 50 px | Drop merged runs shorter than this. | Filters favicon strips, "People also ask" sub-rows, and breadcrumbs that survive the gap-merge step. |
| `SUSPICIOUS_H` | 350 px | Cards taller than this get a `_meta.flags` entry for human spot-check. | Audit threshold, not a filter. Current flag rate: 11/86 trials = 12.8%. |
| `AD_OVERLAP_THRESHOLD` | 0.5 | Card is classified as an ad and excluded from organics if it overlaps any ad rectangle by ≥ this fraction of its height. | The asymmetry matters: 0.5 prevents an organic card from being misclassified when its band edge clips a tall dd_right rail; 1.0 would over-include ads that abut organics; 0.0 would drop everything below an ad. |
| `subdivide_horizontal` `peak_height_frac` | 0.4 | Vertical-edge peaks must reach 40% of the column max edge magnitude. | Carousel-cell sensitivity. Returns `[]` if fewer than 2 cells found, in which case the parent bbox is retained as-is. |
| `subdivide_horizontal` `peak_distance` | 80 px | Minimum cell width. | Floor on per-product card width. |
| `subdivide_vertical` `gap_merge` | 12 px | Same role as top-level `GAP_MERGE`, tuned tighter for the denser dd_right layout. | Tighter than top-level `GAP_MERGE=24` because dd_right product rows pack more tightly than full-column organic cards. |

## 5. Sensitivity tested

### 5.1 Visual spot-check (2026-04-08 onward)

`scripts/verify_organic_bboxes.py` renders each extracted JSON as a colored bbox overlay on the source screenshot. Three trials currently rendered for human review (`scripts/output/organic-bbox-verify/`). Used as the sanity gate before any per-result claim cites organic bboxes.

### 5.2 Self-flagging on tall cards

Trials where an extracted organic exceeds `SUSPICIOUS_H = 350 px` are flagged in `_meta.flags`. Flag rate on the 86 extracted trials: 11/86 = 12.8%. Tall cards usually mean two cards merged across a within-card gap that exceeded the threshold; spot-checks show roughly half are genuine tall cards (rich snippets, multi-line knowledge entries) and half are merge errors that need parameter tuning.

### 5.3 Schema parity with AdSERP v1

The output JSON mirrors the v1 ad-boundary schema (`location` and `size` keys, integer pixel coordinates), so `notebooks-v2/data_loader.py` reads both with the same logic. Verified by structural comparison of v1 ad files vs. extracted organic files.

## 6. Sensitivity NOT tested

Ordered by likelihood of changing a downstream result.

1. **Threshold sweep on `ROW_STD_THRESHOLD`, `GAP_MERGE`, `MIN_CARD_H`.** Each parameter has a defensible default but no formal robustness sweep. A {2, 3, 5} × {16, 24, 32} grid would establish the parameter envelope. **Not yet run.**
2. **Inter-rater agreement on hand-labeled organics.** No human-labeled gold standard exists for any subset of trials. The only validation is visual spot-check by the author. A 30-trial gold set with ≥ 2 raters would let us report precision/recall.
3. **Full-corpus run.** 86 of 2,776 trials extracted. Whether the fixed parameters generalize to all blocks and queries is untested. The 2,690 unprocessed trials are a homogeneity assumption, not a measurement.
4. **Cross-rendering stability.** All extractions ran against the screenshots shipped in AdSERP v1. If Google re-renders these queries, the column geometry will shift; the pipeline does not detect column-width drift.
5. **`AD_OVERLAP_THRESHOLD` sensitivity.** 0.5 is a defensible boundary but not tested at 0.3, 0.7, or 1.0. An organic card that abuts a `dd_right` rail can have a 0.4–0.6 overlap depending on rail length; the current threshold may toggle that card's classification.
6. **Sub-pixel separator robustness on dd_top carousels.** Cards with no whitespace between them (only sub-pixel anti-aliased separators) rely on the vertical-edge peak detector; carousels with low contrast between products may produce spurious or missing peaks.

## 7. What's robust regardless of tweaking

- **The schema.** Output JSON shape, key names, integer pixel coordinates, and structural parity with AdSERP v1 ad-boundary files are fixed by the contract. Any methodology tweak that produces different bboxes still produces the same JSON shape.
- **The ordering rule.** Cards are numbered top-to-bottom by `y_top`. This is independent of detection thresholds.
- **Reproducibility metadata.** `_meta.params` records every threshold used per trial, so any extracted JSON is self-describing and reproducible by re-running with the recorded parameters.
- **Provenance separation.** Shipped ad rectangles (`native_ad`, `dd_top`, `dd_right`) pass through unchanged; the pipeline's contribution (`organic_result`, `dd_top_cell`, `dd_right_cell`) is keyed separately. Downstream code can mix v1 ad data with v1.x organic data without ambiguity.

## 8. Limitations to disclose in papers

- The pipeline is **not validated against a hand-labeled gold standard**. Per-rank claims that depend on bbox precision should note: "organic AOIs were extracted by row-projection CV (`scripts/extract_organic_bboxes.py`); validation is by visual spot-check, not against an inter-rater-agreed reference."
- **Subset coverage.** As of 2026-04-30, organic bboxes exist for 86 of 2,776 trials. Any per-rank claim that cites pixel-accurate AOIs must restrict to the extracted subset, or fall back to band estimation for the remainder. Mixed-mode aggregation (some trials with bboxes, some with bands) silently introduces resolution drift; do not pool without flagging.
- **Column-geometry assumption.** `COL_X=162, COL_W=586` is fixed for `google.es?hl=en` 2024 desktop renders. Re-running the pipeline on any other corpus requires a measurement of the new column geometry.
- **Ad-overlap classification is binary.** Cards that overlap an ad by 30–70% are forced into one bucket. A future revision could expose a per-card `ad_overlap_fraction` for downstream filters.
- **`dd_top_cell` and `dd_right_cell` are heuristic subdivisions** of monolithic ad blocks. AdSERP v1 treats each ad rail as one rectangle; this pipeline subdivides where the visual structure permits but does not validate the per-cell labeling against any external rendering.

## 9. Where this rule appears in published / draft work

- **AdSERP corpus enrichment** — primary artifact. JSON files in `AdSERP/data/organic-boundary-data/` (86 trials as of 2026-04-30). Schema mirrors v1 ad-boundary JSON; intended for direct concatenation into the dataset.
- **README §Reusable components** — listed as an enrichment that downstream consumers of AdSERP can adopt.
- **`notebooks-v2/data_loader.py`** — `extract_serp_results` and band-fallback path consume these JSONs when present.
- **CIKM 2026 paper-v3, §3 (data)** — every per-rank claim that uses pixel-accurate AOIs depends on this enrichment; band-estimation fallback should be acknowledged for the unprocessed remainder.
- **`approach-retreat`** — AOI-based retreat geometry uses these bboxes for the AdSERP testbed. The dataset enrichment is what makes screenshot-accurate cursor replay possible at andyed.github.io/approach-retreat/replay/.
- **Upstream conversation with AdSERP authors** (Latifzadeh / Gwizdka / Leiva) — candidate v1.1 release: organic bbox JSONs back-contributed to Zenodo. **Not yet initiated.**

## 10. Status

**Status:** current as of 2026-04-30; canonical implementation: `scripts/extract_organic_bboxes.py`. Applied to 86 trials to date; full-corpus run (n=2,776) pending.

Pre-meeting context, 2026-04-30: Jacek Gwizdka flagged this work positively in the RIPA2 team meeting today, with the qualifier "if not at scale." The scale concern is the documented gap above (item §6.3, full-corpus run pending) — the pipeline is shipping; the corpus-wide application is the work that closes the loop.
