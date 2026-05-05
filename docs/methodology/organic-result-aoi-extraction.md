# AOI Extraction Pipeline (CV bboxes + HTML widget typing)

**Stable ID:** M:organic-result-aoi-extraction
**Status:** current as of 2026-05-04; canonical implementations: `scripts/extract_organic_bboxes.py` (Phase A), `scripts/extract_html_widget_types.py` (Phase B), `scripts/build_typed_aoi_map.py` (Phase C). Applied to the full corpus (2,776 trials, 0 errors).
**Companion to:** [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md) (downstream impact across K-IDs under all four rank-attribution flavors)

---

## TL;DR

AdSERP v1 ships shipped ad bboxes (`native_ad`, `dd_top`, `dd_right`) and full-page screenshots, but no organic-result bboxes, no per-cell carousel subdivision, no widget separation, and no semantic typing of the cards. The pipeline below recovers all four through three phases: **(A)** CV row-projection on the screenshots reconstructs pixel-accurate bboxes; **(B)** BeautifulSoup over the SERP HTML labels each card with one of 13 etypes (organic, dd_top, native_ad, paa, image_pack, knowledge_panel, top_places, related_searches, pagination, dd_right, other_widget, unknown_widget, chrome); **(C)** a spatial join attaches the labels to the bboxes by document order with ad-overlap arbitration and a chrome heuristic.

Output is per-trial JSON at `data/aoi-typed/<tid>.json` (45,041 entries across 2,776 trials), schema additive to v1's ad-boundary JSON. Four rank-attribution flavors (`absolute`, `organic`, `organic_hybrid`, `typed`) coexist; the canonical post-2026-05-04 primary is **`typed`**.

**Validated against shipped gold.** AdSERP v1's shipped ad bboxes (`native_ad`, `dd_top`, `dd_right`) provide a labeled gold standard for the ad/non-ad partition. The pipeline matches it with **0 disagreements across 38,250 classifications** on 2,776 trials: 0/26,590 Phase A `organic_result` bboxes overlap any shipped ad (Phase A ad-subtraction is clean); F1 = 1.000 on Phase C ad propagation across all three ad etypes; mean IoU = 1.000; no cross-type misclassifications. The deeper non-ad partition (`organic` vs `widget` vs `paa` vs `image_pack`) lacks an external gold and is validated against HTML structure plus visual spot-check. See §5.6 + [`validation-typed-vs-shipped-ads.md`](./validation-typed-vs-shipped-ads.md).

**Visible proof.** The AR replay viewer renders typed AOIs as colored overlay rectangles on the source SERP screenshots: <https://andyed.github.io/approach-retreat/replay/>. Browse the trial index for representative cases of organic, dd_top, native_ad, paa, image_pack, knowledge_panel, top_places, related_searches, and pagination AOIs as they were attributed; e.g., <https://andyed.github.io/approach-retreat/replay/trials/p007-b5-t6.html> (typed widgets) or <https://andyed.github.io/approach-retreat/replay/trials/p047-b1-t3.html> (CLK + DEF + REJ in one SERP).

---

## 1. The rule, in one line

For each trial, **(A)** detect content-bearing card runs in the SERP main column by row-projection on the grayscale screenshot (`std(screenshot[y, COL_X:COL_RIGHT]) >= ROW_STD_THRESHOLD`), drop runs that overlap shipped ad rectangles, drop runs at or below the trial's widget y-floor; **(B)** parse the SERP HTML and type each card via an 8-tier priority chain (heading text → structural descendants → `data-attrid` → class → fallback); **(C)** join the typed list onto the bbox geometry by kth-bbox-↔-kth-HTML-card document order with ≥30% asymmetric ad-overlap arbitration; sweep deep short cv-only entries to `chrome` (off-axis); assign positions 0..N by y. Off-axis cards (right-rail, bottom-of-page widgets, dd_right, chrome) get `position = −1`.

## 2. Why this rule

Per-rank analyses without this enrichment had three options, all bad:

1. **Band estimation.** Divide document height by `count_results_html(tid)` and assign each fixation to the nearest band. Bands are wrong wherever ads sit between organics, where rich snippets vary card height, or where bottom-of-page widgets are h3-anchored alongside organics. Per-result claims at this resolution silently mislabel any fixation on the AOI margin and silently include refinement-widget visits in the per-rank denominator.
2. **HTML-derived bboxes alone.** The SERP HTML snapshots ship with the corpus, but they don't carry rendered pixel coordinates. Re-rendering them in a headless browser is fragile (Google A/B-tests rendering, fonts drift, snapshots aren't byte-stable). Most attempts fail trial-by-trial without a clear failure signal.
3. **Pool ads with organics under "absolute" rank.** Easy, but per-rank claims become uninterpretable when a "rank-1" is sometimes an organic and sometimes an ad with very different click policies.

Phase A (row-projection on rendered pixels) gets pixel-accurate geometry without depending on HTML reproducibility. Phase B (BeautifulSoup over the static HTML) gets stable semantic labels without depending on rendering. Phase C joins the two by document order. The bboxes come from CV; the etypes come from HTML; geometry is never re-derived in Phase C. The split lets each layer fail loudly: a trial with broken HTML still gets bboxes and falls back to `unknown_widget`; a trial with column-drift gets typed cards but no main-axis position.

Earlier-cascade alternatives the pipeline replaced:

- The v2 `widget` filter is a **bottom-of-page-only** signal (h3 heading regex + y-gap heuristic). It correctly excludes `related_searches` from the organic-rank denominator but pools all widget types under one bucket and lets inline / mid-page widgets (image packs, knowledge panels, top_places, PAA) pass through as `organic_result` entries with rank numbers — mis-attributing their ~7% click rate as if it were organic-result behavior. Phase B's per-card typing fixes this.
- A spatial-only HTML↔bbox match (nearest-y, IoU) requires both to live in the same coordinate space, which they don't. Document order is the only stable axis.

## 3. Where this lives in code

### Phase A — CV bbox extraction

| Function | File | Role |
|---|---|---|
| `detect_cards(png_path)` | `scripts/extract_organic_bboxes.py:72` | Row-projection + gap-merge + min-card filter. Returns `[(y_top, y_bottom), ...]` for content runs in the main column. |
| `is_ad(card, ads)` | `scripts/extract_organic_bboxes.py:193` | Tests a card against shipped ad rectangles. Requires y-overlap (≥ `AD_OVERLAP_THRESHOLD`) AND x-overlap with `[COL_X, COL_RIGHT]`. |
| `subdivide_horizontal(png, bbox)` | `scripts/extract_organic_bboxes.py:98` | Vertical-edge peak detection on \|dx\| column-summed across bbox rows. Used for dd_top carousels. |
| `subdivide_vertical(png, bbox)` | `scripts/extract_organic_bboxes.py:147` | Row-projection inside a parent bbox. Used for dd_right product stacks AND composite-organic sub-segmentation. |
| `find_widget_y_floor(trial_id)` | `scripts/extract_organic_bboxes.py:214` | HTML walk for widget-heading h3s. Returns the band-y backstop floor when widget heading is found, or None. |
| `_widget_floor_from_gap(spans)` | `scripts/extract_organic_bboxes.py:276` | Layout-aware floor: y of the first card after the largest anomalous inter-card gap. |
| `extract_trial(trial_id)` | `scripts/extract_organic_bboxes.py:311` | Top-level orchestrator: detection → ad subtraction → widget classification → composite sub-segmentation → output JSON. |

Phase A output schema (per-trial JSON in `AdSERP/data/organic-boundary-data/{trial}.json`):

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
    "trial": "p007-b6-t8", "card_count": 16, "organic_count": 9,
    "widget_count": 1, "widget_y_floor": 2597,
    "organic_cell_count": 0, "dd_top_cell_count": 4,
    "dd_right_cell_count": 0, "flags": [...], "params": {...}
  }
}
```

Schema is **additive** to AdSERP v1's ad-boundary JSON: top-level keys for shipped ad data (`native_ad`, `dd_top`, `dd_right`) pass through unchanged; new keys are added without renaming or restructuring v1 fields.

### Phase B — HTML widget extraction

| Function | File | Role |
|---|---|---|
| `parse_serp(html)` | `scripts/extract_html_widget_types.py:260` | Top-level: walks `#rso` (with descent into "Main results" wrappers), `#botstuff`, `#rhs`. Emits ordered typed cards. |
| `_walk_rso_cards(rso)` | `scripts/extract_html_widget_types.py:224` | Yields cards from `#rso`. Detects the `ULSxyf` "Main results" wrapper (heading match OR > 2 organic-class descendants) and descends INTO it. |
| `_find_card_descendants(div)` | `scripts/extract_html_widget_types.py:172` | Card-class descendant enumeration with nested-element dedupe and source-line ordering. |
| `_detect_type(div)` | `scripts/extract_html_widget_types.py:63` | 8-tier priority chain returning `(type_label, signature)`. |
| `_heading_text(div)` | `scripts/extract_html_widget_types.py:45` | Extract h3 / h2 / role=heading text, in priority order. |
| `_is_main_results_wrapper(div)` | `scripts/extract_html_widget_types.py:154` | True iff the wrapper hosts > 2 organic-class descendants OR has heading "Main results". |

The 8-tier type-detection chain (`_detect_type`):

```python
# Tier 1 — heading text (highest priority; ULSxyf wrapper class is reused)
heading = "people also ask"        → 'paa'
heading = "related searches"        → 'related_searches'
heading = "local results"           → 'top_places'
heading = "complementary results"   → 'knowledge_panel'
heading.startswith("top stories")   → 'other_widget' (news pack)
heading.startswith("videos for ")   → 'other_widget' (video pack)
heading.startswith("images for ")   → 'image_pack'

# Tier 2 — structural descendants
.related-question-pair              → 'paa'
g-map                               → 'top_places'

# Tier 3 — data-attrid (knowledge-card namespace, stable across drift)
data-attrid="kc:/local..."          → 'top_places'
data-attrid="kc:/..."               → 'knowledge_panel'

# Tier 4 — class markers
TQc1id                              → 'knowledge_panel'

# Tier 5 — ULSxyf with image descendant → image_pack; otherwise other_widget
ULSxyf + img[data-src,...]          → 'image_pack'
ULSxyf                              → 'other_widget'

# Tier 6 — sectioned widget
g-section-with-header               → 'other_widget'

# Tier 7 — class-based organic
class ∋ {g, tF2Cxc, hlcw0c}         → 'organic'

# Tier 8 — structural organic (heading + outbound link)
heading + <a href>                  → 'organic'

# Fallback                          → 'other_widget' or None
```

Tier 1 fires before Tier 5 so that `<h2>People also ask</h2>` inside a `ULSxyf` wins over the class-based image_pack heuristic. Google reuses `div.ULSxyf` as a generic widget wrapper for PAA, image packs, news, video, and Related searches; only the heading disambiguates them.

Phase B output schema (per-trial JSON at `data/aoi-html-types/<tid>.json`):

```json
[
  {"order": 0, "type": "organic", "html_handle": "rso[0]",
   "html_signature": "div.g.tF2Cxc", "heading_text": "Lemfoerder...",
   "container": "rso", "container_index": "0"},
  {"order": 7, "type": "image_pack", "html_handle": "rso[7]",
   "html_signature": "ULSxyf+img div.ULSxyf", ..., "container": "rso"},
  {"order": 12, "type": "related_searches", "html_handle": "botstuff.ULSxyf[0]",
   "html_signature": "h=\"rs\" div.ULSxyf", ..., "container": "botstuff"},
  {"order": 13, "type": "pagination", "html_handle": "botstuff.nav[0]",
   "html_signature": "div[role=navigation] in botstuff", ...},
  {"order": 14, "type": "knowledge_panel", "html_handle": "#rhs",
   "html_signature": "rhs.kp[data-attrid=kc:/...]", "container": "rhs"}
]
```

Phase B is purely textual — no bboxes, no pixel coordinates. `html_handle` and `html_signature` are debug breadcrumbs that survive Phase C.

### Phase C — Spatial join

| Function | File | Role |
|---|---|---|
| `join_one_trial(tid)` | `scripts/build_typed_aoi_map.py:73` | Top-level orchestrator. Walks Phase-A bboxes and ad rectangles, matches non-ad bboxes to Phase-B HTML cards by document order, applies chrome heuristic, emits per-trial typed JSON. |
| `_bbox_overlap_frac(a, b)` | `scripts/build_typed_aoi_map.py:56` | Fraction of bbox `a`'s area covered by bbox `b`. Asymmetric. |

Algorithm:

```
main_bboxes  ← organic_result ∪ widget   (from Phase A, sorted by y)
ad_bboxes    ← dd_top ∪ native_ad         (from v1 ad-boundary)
html_rso     ← Phase B cards with container='rso'

# Step 1: arbitrate ad-vs-non-ad on each main bbox
for b in main_bboxes:
    if any(overlap(b, ad) ≥ 0.30 OR overlap(ad, b) ≥ 0.30 for ad in ad_bboxes):
        emit (type=ad.type, geometry=b, source='cv_bbox+ad_overlap')
        mark ad as used
    else:
        non_ad_bboxes.append(b)

# Step 2: positional match non-ad bboxes ↔ HTML #rso cards in DOM order
for k in range(min(len(non_ad_bboxes), len(html_rso))):
    emit (type=html_rso[k].type, geometry=non_ad_bboxes[k],
          source='html_rso+cv_bbox')

# Step 3: residuals
unmatched_bbox  → unknown_widget   (cv saw, html had no card at this index)
unmatched_html  → no geometry      (html had, cv didn't bbox; position=-1)
unused_ads      → ad_only          (cv missed the ad; appended)

# Step 4: chrome heuristic — sweep bottom-of-page furniture off scroll axis
for tentative_pos, e in enumerate(main_entries by y):
    if e.type == 'unknown_widget' and e.height < 200 and tentative_pos >= 10:
        relabel as 'chrome', position=-1

# Step 5: append off-scroll-axis cards
botstuff cards     → position=-1 (related_searches, pagination)
rhs cards          → position=-1 (top_places, knowledge_panel from #rhs)
dd_right ads       → position=-1
```

**Why ad-overlap arbitration before HTML matching.** The Phase-A ad-subtraction (`is_ad`, with x-overlap requirement) is correct for top-of-page ads at typical aspect ratios but occasionally lets through low-contrast `dd_top` cards (4–5 carousel cells with thin dividers) as a single tall organic. If those reach Step 2 they consume an HTML `rso[0]` slot that should have gone to a real organic, shifting every downstream match by one. Step 1 catches them: any main-column bbox with ≥30% area overlap with a shipped ad rectangle is the ad, regardless of CV classification, and is removed from the HTML-matching queue. The 30% threshold is asymmetric: `overlap(bbox, ad) ≥ 0.30 OR overlap(ad, bbox) ≥ 0.30` handles a thin overlay band and a CV bbox that fully contains a small ad symmetrically.

**Why positional matching (kth bbox ↔ kth HTML card).** Document order is the only stable matching axis. HTML cards have `sourceline` but no rendered y; CV bboxes have y but no DOM identity. The kth-bbox-to-kth-HTML rule holds because Google renders `#rso` children in document order down the page (modulo float/grid layout, which AdSERP queries don't trigger at any scale). The match fails when the two enumerations disagree on **count** — §5.2 quantifies the disagreement.

**Chrome heuristic.** A residual class of cv-only entries (no HTML match) cluster at deep tentative positions with short heights — pagination strips, bottom promotional bands, footer regions, "next page" UI furniture. They aren't widgets in the editorial sense; they shouldn't be counted in the rank denominator. The heuristic relabels them to `chrome` and moves them to `position=-1` if all three predicates hold: `tentative_pos ≥ 10` AND `height < 200 px` AND `type == 'unknown_widget'`. Sweeps 5.0% of total entries (2,255 of 45,041).

Phase C output schema (per-trial JSON at `data/aoi-typed/<tid>.json`):

```json
[
  {"position": 0, "type": "organic", "x": 162, "y": 133, "width": 586,
   "height": 258, "html_handle": "rso[0]", "html_signature": "div.g.tF2Cxc",
   "heading_text": "Lemfoerder 3314801 Suspension Subframe Mount",
   "source": "html_rso+cv_bbox"},
  {"position": 7, "type": "image_pack", "x": 162, "y": 1842, ...,
   "html_handle": "rso[7]", "source": "html_rso+cv_bbox"},
  {"position": -1, "type": "related_searches", "x": null, "y": null, ...,
   "html_handle": "botstuff.ULSxyf[0]", "source": "html_botstuff"},
  {"position": -1, "type": "chrome", "x": 162, "y": 3104, "height": 80,
   "html_handle": null, "source": "cv_bbox_only+chrome_heuristic"}
]
```

`source` is the provenance breadcrumb. Eight values across the corpus:

| `source` | Share | Meaning |
|---|---|---|
| `html_rso+cv_bbox` | 56.8% | HTML typed it, CV bboxed it; full join. The healthy path. |
| `ad_only` | 24.0% | Shipped ad with no CV bbox match; geometry from ad-boundary-data. |
| `html_botstuff` | 10.0% | Off-axis bottom widget (related_searches, pagination); no geometry. |
| `cv_bbox_only+chrome_heuristic` | 5.0% | Bottom-of-page furniture, swept to position=-1. |
| `cv_ad_rhs` | 1.9% | Right-rail ad (`dd_right`); position=-1. |
| `cv_bbox_only` | 1.7% | CV saw a card HTML didn't structure; labeled `unknown_widget`. |
| `html_only` | 0.4% | HTML had a card CV didn't bbox; no geometry, position=-1. |
| `html_rhs` | 0.2% | Right-rail KP from `#rhs`; off-axis. |

## 4. Parameters

All Phase A parameters are written to `_meta.params` per trial so a downstream consumer can verify the configuration that produced any given output.

### Phase A — Card detection (main column)

| Parameter | Default | What it controls |
|---|---|---|
| `COL_X` | 162 px | Left edge of the SERP main column on Google ES with `hl=en`. |
| `COL_W` | 586 px | Main column width. Picks the larger of observed `dd_top` and `native_ad` widths to avoid right-edge clipping. |
| `ROW_STD_THRESHOLD` | 3 | Per-row pixel-std cutoff below which a row is "blank." |
| `GAP_MERGE` | 24 px | Maximum vertical gap that's still considered within-card. |
| `MIN_CARD_H` | 50 px | Drop merged runs shorter than this. Filters favicon strips, breadcrumbs, "People also ask" sub-rows. |
| `SUSPICIOUS_H` | 350 px | Cards taller than this get a `_meta.flags` entry for human spot-check. Audit threshold, not a filter. |

### Phase A — Ad subtraction

| Parameter | Default | What it controls |
|---|---|---|
| `AD_OVERLAP_THRESHOLD` | 0.5 | Card classified as an ad iff y-overlap ≥ this fraction of card height AND ad's x-extent intersects `[COL_X, COL_RIGHT]`. |

### Phase A — Widget filter

| Parameter | Default | What it controls |
|---|---|---|
| `WIDGET_HEADING_RE` | regex | Matches widget heading h3 text: `Related searches`, `People also search for`, plus Spanish equivalents. HTML signal that widgets exist on the trial. |
| Gap-floor `min_multiplier` | 3.0 | Largest inter-card gap must exceed this multiple of the median gap to qualify as the widget y-floor. |
| Gap-floor `min_absolute_px` | 150 | Largest inter-card gap must also exceed this absolute floor (suppresses false positives on very dense or sparse SERPs). |

### Phase A — Composite-organic sub-segmentation

| Parameter | Default | What it controls |
|---|---|---|
| `COMPOSITE_TRIGGER_H` | 320 px | Organics taller than this are candidates for sub-segmentation. |
| `COMPOSITE_GAP_MERGE` | 12 px | Tighter than top-level `GAP_MERGE` — sub-listings inside a composite sit closer than full organic cards do. |
| `COMPOSITE_MIN_CELL_H` | 60 px | Filters sub-listing chrome (rating bars, divider lines). |
| `COMPOSITE_STD_THRESHOLD` | 3 | Same as top-level row-projection. |

### Phase A — Ad-rail cell subdivision

| Parameter | Default | What it controls |
|---|---|---|
| `subdivide_horizontal` `peak_height_frac` | 0.4 | Vertical-edge peaks must reach 40% of the column max edge magnitude to qualify as carousel-cell boundaries. |
| `subdivide_horizontal` `peak_distance` | 80 px | Minimum cell width. |
| `subdivide_vertical` `gap_merge` | 12 px | Same role as top-level `GAP_MERGE`, tuned for the denser dd_right layout. |

### Phase B — HTML extraction

| Parameter | Default | What it controls |
|---|---|---|
| `WIDGET_HEADING_RE` | implicit in tier-1 chain | Heading text → etype map (PAA, Related searches, Local results, Complementary results, Top stories, Videos, Images for, etc.) |
| `ORGANIC_CARD_CLASSES` | `{g, tF2Cxc, hlcw0c, MjjYud}` | DOM classes that mark a div as a card descendant when descending into "Main results" wrappers |
| `_is_main_results_wrapper` threshold | > 2 organic-class descendants | Distinguishes a section-wrapper ULSxyf from a single-widget ULSxyf |
| `data-attrid` prefixes | `kc:/local` → top_places, `kc:/` → knowledge_panel | Knowledge-card namespace; stable across HTML drift |
| `SKIP_TAGS` | `{script, style, noscript, span}` | DOM children that cannot host a card |

### Phase C — Spatial join

| Parameter | Default | What it controls |
|---|---|---|
| `AD_OVERLAP_THRESHOLD` (Phase C) | 0.30 | Min asymmetric overlap for cv_bbox to be reclassified as an ad. Lower than Phase A's 0.50 because Phase C arbitrates over a smaller candidate set. |
| Chrome heuristic — `tentative_pos` floor | 10 | Position depth below which short cv-only entries become chrome candidates |
| Chrome heuristic — `height` ceiling | 200 px | Max height for chrome candidacy (real cards are taller) |
| Chrome heuristic — `type` precondition | `unknown_widget` | Only sweeps cv-only residuals; never touches matched HTML+bbox entries |

## 5. Sensitivity tested

### 5.1 Etype distribution (full corpus, n=2,776; 45,041 entries)

```
organic           22,530   50.0%      pagination   2,697   6.0%   (off-axis)
native_ad          9,217   20.5%      chrome       2,255   5.0%   (off-axis)
image_pack         1,600    3.6%      related_se   1,811   4.0%   (off-axis)
dd_top             1,582    3.5%      dd_right       861   1.9%   (off-axis)
knowledge_panel      826    1.8%
paa                  769    1.7%
unknown_widget       756    1.7%
top_places            86    0.2%
other_widget          51    0.1%
```

Newly typed widget surfaces vs the prior `organic_hybrid` flavor (which pooled all widgets under one `widget` bucket): image_pack 1,600 + knowledge_panel 826 + paa 769 + top_places 86 + other_widget 51 = **3,332 first-class etyped widgets**, plus 1,816 reclassified within the existing match. Total **5,148 widget surfaces** that prior attribution flavors either pooled into a single `widget` bucket or dropped below the y-floor.

### 5.2 HTML-vs-CV count alignment (full corpus, n=2,776)

`Δ = n_html_rso − n_bbox_main` per trial:

```
exact (Δ=0):     816 / 2,776 = 29.4%
|Δ| ≤ 1:       1,928 / 2,776 = 69.5%
|Δ| ≤ 2:       2,492 / 2,776 = 89.8%
|Δ| ≤ 3:       2,685 / 2,776 = 96.7%
```

Skew is left-of-zero (HTML undercounts CV) — CV picks up composite-cell fragments and bottom-of-page furniture that HTML doesn't structure as cards. The chrome heuristic absorbs 2,255 of those (5.0% of total entries), leaving a 1.7% residual `unknown_widget` rate.

### 5.3 v2-only Phase-A pipeline-vs-h3 alignment (legacy reference, full corpus)

Compared `_meta.organic_count` (Phase A pipeline) to `count_organic_ranks(tid)` (HTML-derived organic-h3 count, ad-overlapping h3s excluded):

```
exact (delta=0):     683/2,776 = 24.6%
|delta| ≤ 1:       1,801/2,776 = 64.9%
|delta| ≤ 2:       2,451/2,776 = 88.3%
mean: -0.20  ·  median 0  ·  IQR [-1, 0, +1]
```

`count_organic_ranks` is **not** ground truth — it includes widget-heading h3s ("People also ask", "Related searches") as "organic" slots, so a pipeline result of `delta < 0` is sometimes the pipeline being correctly stricter than the HTML enumeration.

### 5.4 Widget filter activity (Phase A, legacy reference)

```
trials where filter fired:    1,652 / 2,776 = 59.5%
total widgets caught:                             2,206
```

Not every trial has refinement widgets — only those with HTML widget headings AND a layout-detected gap. The remaining 40.5% of trials produced zero widgets. Phase B / C now type these directly without depending on the Phase A widget filter.

### 5.5 Composite-cell activity

```
trials with composite cells: 166 / 2,776 = 6.0%
total cells emitted:                          376
```

Composite organics (local 3-packs, multi-row PAA expansions, image carousels) are real but uncommon in the AdSERP corpus, which is dominated by transactional product queries.

### 5.6 Ad/non-ad partition validation against shipped gold (full corpus, n=2,776)

AdSERP v1 ships per-trial advertisement bounding boxes (`native_ad`, `dd_top`, `dd_right`) as part of the corpus distribution. These are the **only labeled ad/non-ad partition** in the dataset and serve as a usable gold standard for the ad classification question. Two independent stages of the pipeline are validated against this gold:

| Stage | Quantity | Result |
|---|---|---|
| **Phase A consistency** | `organic_result` bboxes overlapping any shipped ad (IoU ≥ 0.30 or ≥ 50% containment) | **0 / 26,590** (0 trials affected) |
| **Phase C propagation** | shipped ad bboxes recovered as same-etype typed entries | **11,660 / 11,660** (1.000 recall) |
| **Phase C precision** | typed `native_ad` / `dd_top` / `dd_right` entries matching a same-type shipped ad | **11,660 / 11,660** (1.000 precision) |

F1 (same-type) = 1.000, mean IoU = 1.000, no cross-type misclassifications (no `native_ad` typed where shipped says `dd_top`, etc.). For the **ad / non-ad partition specifically**, this is a 0-disagreement validation against shipped gold across 38,250 classifications (11,660 shipped ads + 26,590 Phase A organics) on 2,776 trials. Implication: Phase C's Step-1 ad-overlap arbitration (`cv_bbox+ad_overlap` source) never fires in the corpus — Phase A's CV `is_ad` subtraction is doing all the work, and Step-1 is a defensive correction for future captures where Phase A might miss an ad.

Spec: [`validation-typed-vs-shipped-ads.md`](./validation-typed-vs-shipped-ads.md). Reproducibility: `scripts/validate_typed_ads_vs_shipped.py` → `scripts/output/typed_ads_vs_shipped/`.

This validation does NOT cover the deeper `organic vs widget vs paa vs image_pack` partition, which has no labeled gold and remains validated against HTML structure plus visual spot-check via the AR replay viewer.

### 5.7 Click-attribution audit (Phase-A bbox + 30 px tolerance, full corpus, n=2,775)

`data_loader.attribute_click_to_organic(click_y, trial_id, tolerance_px=30)` snaps clicks within 30 px of an organic edge to that organic, rejecting clicks inside any ad / widget rectangle first. The 30 px elbow was chosen empirically: 92.5% of off-AOI clicks are within 30 px of the nearest organic edge; further loosening rescues only ~0.3 percentage points more.

| Bucket | Count | Share |
|---|---|---|
| Organic (strict containment + 30 px snap) | **2,181** | **78.6%** |
| All ads (`native_ad` + `dd_top` + `dd_right`) | 557 | 20.1% |
| Filtered widgets (`Related searches`, `People also search for`) | 5 | 0.2% |
| Truly off-AOI (KP / image carousel / footer / large gaps) | **32** | **1.2%** |

For comparison, strict containment (`tolerance_px=0`) attributes only 64.3% of clicks to organic AOIs — the remaining 14.3% land in the small visual gaps between adjacent organic rectangles (median 10 px, P75 15 px, P90 22 px). Those gap clicks are visual-margin artifacts, not off-AOI events; the 30 px tolerance correctly recovers them.

The headline: **78.6% of clicks on organic, 20.1% on ads, 1.2% on content the pipeline doesn't model**. Under typed (Phase B+C) the 1.2% residual is reduced because Knowledge Panel, image carousels, and top_places — the three biggest contributors to v2's residual — are now first-class etyped surfaces.

### 5.8 Click-prediction LOSO retrain (NB21, all four flavors)

| Model | absolute | organic | hybrid | typed |
|---|---|---|---|---|
| M3 LOSO AUC (full nine-feature) | 0.859 | 0.865 | 0.870 | **0.871** |
| M4 LOSO AUC (approach-only) | 0.861 | 0.864 | 0.870 | **0.871** |
| M1 LOSO AUC (position-only) | 0.613 | 0.727 | 0.667 | **0.665** |
| Position standardized coefficient | −0.130 | −0.248 | −0.112 | **−0.108** |

The signal is in the cursor approach geometry, not in the AOI taxonomy: M3/M4 hold at 0.871 within ±0.005 of `organic_hybrid` and ±0.012 of legacy `absolute`. M1 is sensitive to flavor — pooling ads with organics under `absolute` deflates the position-only coefficient and underestimates position's standalone predictive lift.

### 5.9 Replication of cascade-era findings under typed

Every 2026-05-03 stress-test finding under `organic_hybrid` reproduces under `typed` within ±0.05 in correlation strength:

| Finding | hybrid | typed | Source |
|---|---|---|---|
| Within-item paired Δ (return − first LF/HF) | +6.31 | **+6.44** | `scripts/lfhf_first_vs_return_paired.py` |
| Pre-scroll Spearman ρ (LF/HF × position) | −0.857 | **−0.857** | NB14 typed re-execution |
| Steep-vs-plateau MW (pooled) | p = 2.6×10⁻²⁵ | **p = 2.3×10⁻²⁵** | NB14 typed re-execution |
| Satopt × knee MW | p = 0.022 | **p = 0.022** | NB30 typed re-execution |
| Click prediction LOSO AUC (M3 nine-feature) | 0.870 | **0.871** | `scripts/nb21_loso_retrain_typed.py` |

The cognitive findings are properties of the trial-level operations, not of widget-vs-organic mis-attribution.

### 5.10 Built-in invariants

- **Reproducibility metadata.** `_meta.params` (Phase A) records every threshold per trial. Any extracted JSON is self-describing and reproducible by re-running with the recorded parameters. Phase B / C parameters are in source code under tagged commits.
- **Schema parity with AdSERP v1.** Top-level keys for shipped ad data (`native_ad`, `dd_top`, `dd_right`) pass through unchanged. New keys (Phase A: `organic_result`, `widget`, `organic_cell`, `dd_top_cell`, `dd_right_cell`; Phase C: `data/aoi-typed/<tid>.json` with etype + geometry + source + html_handle) are additive.
- **Self-flagging on tall cards.** `SUSPICIOUS_H = 350 px` flags non-composite candidates for human review.
- **Visual spot-check tool.** `scripts/verify_organic_bboxes.py` renders any trial's bbox overlay on the source screenshot. Per-trial dev tool; not a systematic validator.
- **Public replay viewer.** The AR replay viewer at <https://andyed.github.io/approach-retreat/replay/> renders typed AOIs (organic, dd_top, native_ad, paa, image_pack, knowledge_panel, top_places, related_searches, pagination) as colored overlay rectangles on the source screenshots across 141 curated trials. This is the systematic visual validator: a reader can browse and sanity-check attribution for any trial without running the pipeline.

## 6. Sensitivity NOT tested

Ordered by likelihood of changing a downstream result.

1. **Inter-rater agreement on hand-labeled non-ad cards.** AdSERP v1 ships labeled ad bboxes (validated against the typed pipeline at 0 disagreements / 38,250 classifications, see §5.6) but no human-labeled gold for the `organic` vs `widget` vs `paa` vs `image_pack` partition. Without it, "pipeline vs HTML-organic-h3 count" disagreement is bidirectional and precision/recall on the per-etype non-ad partition isn't reportable.
2. **HTML class drift (Phase B).** Tier 4–7 detectors rely on Google's compiled CSS class names (`tF2Cxc`, `hlcw0c`, `ULSxyf`, `TQc1id`, `MjjYud`). These drift between A/B-test buckets and capture vintage. The AdSERP corpus was captured 2024 ES; running Phase B against a different vintage will misclassify Tier-7 fallbacks. Mitigation: Tiers 1–3 (heading text, structural descendants, `data-attrid`) are stable across drift and carry the load on widgets; class-only matches degrade gracefully to `other_widget`.
3. **Threshold sweep on `ROW_STD_THRESHOLD`, `GAP_MERGE`, `MIN_CARD_H`.** Each parameter has a defensible default but no formal robustness sweep. A `{2, 3, 5} × {16, 24, 32}` grid would establish the parameter envelope.
4. **`AD_OVERLAP_THRESHOLD` sensitivity (Phase A and Phase C).** 0.5 (Phase A) and 0.30 (Phase C) are defensible boundaries but not tested at adjacent values.
5. **Chrome heuristic sensitivity.** The `pos ≥ 10 AND height < 200` rule sweeps 2,255 entries. Both bounds are integer-defensible; sweeping `{8, 10, 12} × {150, 200, 250}` would test the chrome-vs-real-widget boundary. Cost of error is bounded — swept entries get position=−1 and don't propagate to scroll-axis analyses.
6. **Positional kth-match correctness.** When `n_bbox_main` and `n_html_rso` disagree (70% of trials by ≥ 1), the kth match is by document-order which is *not* the same as y-order in pathological cases. Spot-check on Δ ≤ −2 trials confirms the dominant disagreement is "CV split a composite that HTML kept as one card" — meaning the kth bbox correctly matches the (k − splits)th HTML card up to the split, and after the split the bbox enumeration over-counts. The downstream type label on those over-counted bboxes is `unknown_widget` (the conservative fallback). A composite-aware merge step in Phase C could rescue them; not implemented.
7. **`dd_top` carousel cell precision on dense layouts.** The `find_peaks` edge-detector on the carousel can miss low-contrast dividers between adjacent product cards or fire on intra-card vertical edges (product-image silhouettes). A 5-card carousel can come out as 4 cells. A whitespace-based alternative was tested 2026-04-30 and regressed worse (cards touch with no whitespace columns); the current edge-peak version is the least-bad option pending a hybrid signal.
8. **Sub-pixel separator robustness on `dd_top` carousels.** Cards with no whitespace between them rely on the vertical-edge peak detector; carousels with low contrast between products may produce spurious or missing peaks.
9. **Cross-rendering stability.** All extractions ran against the screenshots shipped in AdSERP v1. If Google re-renders these queries, the column geometry will shift; the pipeline does not detect column-width drift.
10. **"Main results" wrapper edge cases.** Modern Google nests organics inside a wrapper `<div class="ULSxyf">` with heading "Main results"; Phase B detects this (heading match OR > 2 organic-class descendants) and descends into it. Trials where the wrapper has ≤ 2 organic-class descendants but is still a wrapper (rare; not observed in the audit) would collapse all organics into one entry.
11. **Inline / mid-page widget content not classified by Phase A widget filter.** PAA expansion accordion items (each ~30–40 px tall, below `MIN_CARD_H = 50`) are silently dropped at the detection step under Phase A alone. The widget filter is bottom-of-page-only by design (HTML signal + y-gap heuristic). Phase B+C resolves this for image_pack, knowledge_panel, paa, top_places via per-card typing; expansion accordion items remain below detection threshold.
12. **Knowledge-Graph entity cards classified as organic_1 (Phase A only).** Album cards, brand cards, person cards, and similar entity panels at the top of the SERP appear as one tall card in row-projection; if they don't overlap any shipped ad rectangle (which they typically don't), they emerge as `organic_result.position=1`. Distinguishing them requires HTML container check (h3 lives in `#kp-*` vs `#rso`) — handled by Phase B's `top_places` / `knowledge_panel` typing and Phase C's #rhs append.
13. **Right-rail (#rhs) bbox coverage.** RHS knowledge panels and top_places-by-attrid are typed and emitted with `position = −1` and `x = y = null`. Per-fixation analyses on RHS content currently can't condition on AOI inside the panel. Adding HTML-derived child-bbox extraction to RHS is future work.
14. **`other_widget` residual.** 51 entries (0.1%) end up in `other_widget` — featured snippets, news packs, video packs that didn't trigger a more specific tier. Click rate too small to estimate per-class.
15. **Composite-cell handling under typed.** Phase A's `organic_cell` sub-segmentation (composite organics ≥ 320 px get `subdivide_vertical`) happens upstream of Phase C and is unchanged. Cells inherit their parent's typed label by inheritance from the `parent_position` field; per-cell types are not separately HTML-derived.

## 7. What's robust regardless of tweaking

- **The schema.** Output JSON shape, key names, integer pixel coordinates, and structural parity with AdSERP v1 ad-boundary files are fixed by the contract. Any methodology tweak that produces different bboxes still produces the same JSON shape.
- **The ordering rule.** Cards are numbered top-to-bottom by `y_top`. Independent of detection thresholds.
- **Rank semantics are unchanged by sub-segmentation.** `organic_result[].position` is the canonical AdSERP rank (1, 2, 3, …) and **does not change** when an organic happens to be a composite. `organic_cell.parent_position` points back to the parent organic; `organic_cell.position` is a within-parent ordinal. Cells are a **second-column variable**, never a rank overload.
- **Widgets are AOIs, not organics.** Phase A `widget` entries live in their own top-level key; downstream consumers should never see them in the organic-rank denominator. Phase B+C extends this with first-class etype labels.
- **Geometry source of truth.** Bboxes come from Phase A. Phase C never moves a rectangle. If a downstream consumer trusts Phase A geometry, Phase C adds labels on top without geometric drift.
- **Off-axis convention.** Anything with `position == −1` is off the main scroll axis (right rail, bottom-of-page widgets, chrome, dd_right). Per-rank analyses filter `position >= 0` and the off-axis surfaces never enter the rank denominator.
- **Source provenance.** Every entry carries a `source` breadcrumb identifying its derivation path. Audits can re-derive the typing decision without re-running the pipeline.
- **Reproducibility metadata.** `_meta.params` records every Phase A threshold used per trial.
- **Provenance separation.** Shipped ad rectangles pass through unchanged; the pipeline's contributions (`organic_result`, `widget`, `organic_cell`, `dd_top_cell`, `dd_right_cell`, typed entries) are keyed separately. Downstream code can mix v1 ad data with these enrichments without ambiguity.

## 8. Limitations to disclose in papers

- **Validation status.** The ad / non-ad partition is validated against AdSERP v1's shipped ad bboxes at 0 disagreements / 38,250 classifications (see §5.6 and [`validation-typed-vs-shipped-ads.md`](./validation-typed-vs-shipped-ads.md)). The deeper non-ad partition (`organic` vs `widget` vs `paa` vs `image_pack` etc.) has no labeled gold standard. Per-rank claims that depend on the non-ad partition should note: "organic AOIs were extracted by row-projection CV (`scripts/extract_organic_bboxes.py`) with HTML widget typing on top (`scripts/extract_html_widget_types.py` + `scripts/build_typed_aoi_map.py`); the ad/non-ad partition is validated against shipped gold (0 disagreements); within the non-ad partition, validation is alignment with HTML organic-h3 count (within ±2 on 89.8% of trials under typed) plus visual spot-check via the AR replay viewer, not against an inter-rater-agreed reference."
- **Bidirectional disagreement.** `pipeline_count != html_count` does not imply the pipeline is wrong. The HTML enumeration includes widget-heading h3s as "organic" slots; the pipeline correctly excludes them via Phase B typing. Treat per-rank claims at high ranks (≥ 8) with extra caution.
- **HTML class drift.** Phase B Tier 4–7 detectors are sensitive to Google's compiled class names. Re-running on a different vintage requires class-list verification.
- **Right-pane content invisibility (geometry).** RHS knowledge panels and image carousels rendered to the right of the main column are typed by Phase B but get `position = −1` with no geometry. Per-fixation analyses on RHS content are not currently supported.
- **Column-geometry assumption.** `COL_X=162, COL_W=586` is fixed for `google.es?hl=en` 2024 desktop renders. Re-running on any other corpus requires column-geometry measurement.
- **Composite-organic detection threshold.** `COMPOSITE_TRIGGER_H = 320 px` is a defensible default but tuned empirically. Composites shorter than 320 px (e.g., a 2-row PAA expansion) currently emerge as a single organic.
- **`dd_top_cell` and `dd_right_cell` are heuristic.** AdSERP v1 treats each ad rail as one rectangle; this pipeline subdivides where the visual structure permits but doesn't validate per-cell labeling against any external rendering.

## 9. Reproducibility

```bash
git clone https://github.com/andyed/attentional-foraging
cd attentional-foraging

# ── Phase A: CV bbox extraction (geometry source of truth) ─────────
.venv/bin/python scripts/extract_organic_bboxes.py
# → AdSERP/data/organic-boundary-data/<tid>.json (n=2,776)

# ── Phase B: HTML widget extraction ────────────────────────────────
.venv/bin/python scripts/extract_html_widget_types.py
# → data/aoi-html-types/<tid>.json (n=2,776)

# ── Phase C: spatial join ──────────────────────────────────────────
.venv/bin/python scripts/build_typed_aoi_map.py
# → data/aoi-typed/<tid>.json (n=2,776, 45,041 entries)
# → scripts/output/aoi-typed/build_typed_aoi_map_summary.json (audit)

# ── Producer chain (cascade JSONs across all four flavors) ────────
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic_hybrid
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution typed
.venv/bin/python scripts/compute_butterworth_lfhf.py        --attribution typed
.venv/bin/python scripts/compute_ripa2.py                   --attribution typed
.venv/bin/python scripts/compute_regression_labels.py       --attribution typed
.venv/bin/python scripts/compute_retreat_arcs.py            --attribution typed

# ── Validation (LOSO retrain + cascade replication) ────────────────
.venv/bin/python scripts/nb21_loso_retrain_organic.py
.venv/bin/python scripts/nb21_loso_retrain_hybrid.py
.venv/bin/python scripts/nb21_loso_retrain_typed.py
.venv/bin/python scripts/lfhf_rank_gradient_typed.py
.venv/bin/python scripts/lfhf_first_vs_return_paired.py --attribution typed

# ── Per-AOI export (flat table for external consumers) ─────────────
.venv/bin/python scripts/export_aois_by_trial_id.py --attribution typed
# → scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}
#   (37,142 rows × 9 visible etypes; off-axis surfaces excluded)
```

All output JSONs land at `AdSERP/data/<filename>-organic.json` / `-organic-hybrid.json` / `-typed.json` (or `data/aoi-typed/<tid>.json`) as siblings to the legacy absolute-attribution files. Schema is unchanged.

## 10. External transfer schema

Flat per-AOI table at `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 18 columns) — loadable without re-running the pipeline. Schema mirrors AdSERP v1 distribution conventions:

| Column | Type | Meaning |
|---|---|---|
| `trial_id` | str | `p{PPP}-b{B}-t{T}` (zero-padded participant uid, 1-indexed batch / trial); regex `^p(\d{3})-b(\d+)-t(\d+)$` |
| `uid` | int | Participant id (1..47) |
| `batch` | int | Block id within participant |
| `trial` | int | Trial id within block |
| `rank` | int | Display-order position on the main scroll axis (0-indexed; off-axis AOIs excluded) |
| `etype` | str | One of: `organic`, `dd_top`, `native_ad`, `top_places`, `knowledge_panel`, `paa`, `image_pack`, `unknown_widget`, `other_widget` |
| `organic_rank` | int / null | Within-organic position number (null for non-organics) |
| `top_y` / `bottom_y` / `center_y` | float | Page-space pixel coordinates (document, not viewport) |
| `left_x` / `right_x` | float | Main-column edges (162 / 702 by default) |
| `n_total` | int | Number of AOIs on this trial's scroll axis |
| `n_organic` | int | Number of organics on this trial's scroll axis |
| `doc_height` | int | Full screenshot height in px |
| `screen_height` | int | Viewport height (typically 1024) |
| `html_handle` | str | Phase-B DOM breadcrumb (`rso[0]`, `botstuff.ULSxyf[0]`, etc.) |
| `html_signature` | str | Phase-B detection signature (debug provenance) |

Off-axis AOIs (`related_searches`, `pagination`, `chrome`, `dd_right`, RHS knowledge panels) are **excluded** from this export to keep the table focused on the scroll-axis analysis surface. The full per-trial JSONs at `data/aoi-typed/<tid>.json` retain them with `position = −1`.

**Coordinate convention.** Page-space pixels (document coordinates, not viewport). FPOGY from AdSERP gaze logs is already page-space (per the corpus README); bisect `top_y` / `bottom_y` directly without adding scroll offset. Click `click_y` is also page-space.

**Per-etype trial coverage** (rows in `adserp_aois_by_trial_id_typed_summary.json`):

```
organic         22,354    image_pack       1,584    knowledge_panel    746
native_ad        9,217    paa                769    other_widget        50
dd_top           1,582    top_places          84    unknown_widget     756
```

## 11. Where this rule appears in published / draft work

- **AdSERP corpus enrichment v1.2** — primary artifact. Per-trial JSONs at `AdSERP/data/organic-boundary-data/` (Phase A, n=2,776) and `data/aoi-typed/` (Phase C, n=2,776). Schema mirrors v1 ad-boundary JSON.
- **README §Augmentations contributed by this project** — listed as the headline enrichment.
- **`notebooks-v2/data_loader.py`** — `extract_serp_results`, `organic_aoi_tops`, `typed_aoi_tops`, `typed_aoi_etypes`, `attribute_click_to_organic`, `attribute_click_to_typed`, `load_typed_aois` consume these JSONs.
- **CIKM 2026 paper** — algorithmic submission. Per-result-AOI episode geometry depends on the typed cascade for the four-class taxonomy (clicked / deferred / evaluated-rejected / not-approached) when widget surfaces enter the consideration set.
- **`approach-retreat` replay viewer (visible proof)** — <https://andyed.github.io/approach-retreat/replay/>. 141 curated trials with typed AOIs rendered as colored overlay rectangles directly on the source SERP screenshots. Each rectangle is labeled with its etype tag (organic, IP image_pack, KP knowledge_panel, PAA, TP top_places, RS related_searches, PG pagination, OW other_widget, CLK click target) and the consideration-set pill (CLK / DEF / REJ / NA) per trial. Widget injection reads `data/aoi-typed/` directly; the viewer is the canonical way to sanity-check the pipeline output without re-running it. Representative trials: <https://andyed.github.io/approach-retreat/replay/trials/p007-b5-t6.html> (typed widgets), <https://andyed.github.io/approach-retreat/replay/trials/p047-b1-t3.html> (CLK + DEF + REJ in one SERP), <https://andyed.github.io/approach-retreat/replay/trials/p015-b5-t2.html> (image_pack + paa).
- **`pupil-lfhf`** — Butterworth LF/HF + RIPA2 validation pipelines support `--attribution typed`; Fig 5 (`make_fig5.py`) defaults to typed.

## 12. Status

**Status:** current as of 2026-05-04; canonical implementations: `scripts/extract_organic_bboxes.py` (Phase A), `scripts/extract_html_widget_types.py` (Phase B), `scripts/build_typed_aoi_map.py` (Phase C). Applied to the full corpus (2,776 trials, 0 errors).

History:

- 2026-04-08 — design captured in `docs/plans/forward-regressive-split.md` (separate methodology); same-day `extract_organic_bboxes.py` first commit.
- 2026-04-30 — methodology doc created with original framing (v1 schema, n=86 partial coverage, no widget filter, y-only `is_ad`).
- 2026-05-01 — three Phase-A corrections shipped (`60a2e7b9`): `is_ad` x-overlap fix, refinement-widget filter, composite-organic sub-segmentation. Schema gained `widget`, `organic_cell` top-level keys plus `_meta.widget_count`, `_meta.widget_y_floor`, `_meta.organic_cell_count`. Full-corpus extraction (2,776 trials).
- 2026-05-01 — band-y guard against featured-snippet false positives (`da0a8aae`).
- 2026-05-01 — consumer API in `data_loader.py` (`load_aois`, `organic_aoi_bands`, `organic_aoi_tops`); producer migrations for `compute_butterworth_lfhf.py`, `compute_ripa2.py`, `compute_cursor_approach_features.py`, `compute_retreat_arcs.py` with `--attribution {absolute, organic, organic_hybrid}` flags.
- 2026-05-01 — tolerance-aware click attribution (`9249ebce`): `attribute_click_to_organic(click_y, trial_id, tolerance_px=30)` rescues 14.3 percentage points of clicks that strict containment lost to visual-margin gaps.
- 2026-05-01 — Notebook K-claims migrations: NB14 + NB18a, NB25, NB23 K-bbox-* tier, NB04 + NB22 + NB24 + NB15. All cite this methodology doc as the source for attribution shift.
- 2026-05-01 — Approach-retreat parallel rebuild on `feat/aoi-rebuild-2026-05-01`: 80 curated replay bundles regenerated; 13 stale captions fixed.
- 2026-05-04 — Phase B + Phase C added on `feat/aoi-pipeline-v3-typed`. HTML widget extraction (`scripts/extract_html_widget_types.py`) and spatial join (`scripts/build_typed_aoi_map.py`) attach a 13-etype taxonomy on top of Phase A geometry. Phase A bboxes unchanged. Producer chain extended with `--attribution typed`; Tier-A notebooks (NB04, NB14, NB15, NB18, NB22, NB23, NB24, NB25, NB28, NB30, NB32) re-executed under typed; Key Claims appended with typed-cascade subsections.
- 2026-05-04 — NB21 LOSO retrain under typed: M3 = 0.871, M4 = 0.871, M1 = 0.665.
- 2026-05-04 — Per-AOI export at `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 9 etypes) for external transfer.
- 2026-05-04 — Replay viewer (`approach-retreat/site/replay/`) regenerates 141 trial JSONs with typed widget injection.
- 2026-05-04 — Methodology docs consolidated: `aoi-coverage-contribution.md` and `typed-aoi-pipeline.md` retired; their content folded into this doc as Phases A / B / C of one pipeline.

**Pending downstream work:**
- Composite-aware merge step in Phase C to rescue Δ ≤ −2 trials where CV splits HTML composites.
- RHS child-bbox extraction so per-fixation analyses can condition on AOI inside knowledge panels.
- Class-drift sensitivity audit on a non-AdSERP capture to confirm Tiers 1–3 (heading + data-attrid + structural descendants) carry the load when Tiers 4–7 drift.
- M5 classifier retraining against typed-attribution NB22 labels.
- Back-contribution to Zenodo as candidate v1.2 release: organic + widget + cell + typed JSONs.
