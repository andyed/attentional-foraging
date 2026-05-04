# Typed AOI Pipeline (HTML + Vision Joint Widget Typing)

**Stable ID:** M:typed-aoi-pipeline
**Status:** current as of 2026-05-04; canonical implementations: `scripts/extract_html_widget_types.py` (Phase 1) and `scripts/build_typed_aoi_map.py` (Phase 2). Applied to the full corpus (n=2,776 trials, 0 errors).
**Companion to:** [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md) (v2 CV-only pipeline, retained as bbox provider), [`aoi-coverage-contribution.md`](./aoi-coverage-contribution.md) (Jacek-facing summary), [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md) (downstream impact across K-IDs).

---

## TL;DR

The v2 pipeline (`organic-result-aoi-extraction`) gives pixel-accurate bboxes but only one AOI label per cell (`organic_result` / `widget` / ad). Per-rank claims that distinguish, e.g., `paa` from `top_places` from `image_pack` weren't expressible — non-ad widgets pooled under a single `widget` bucket and were filtered out below the y-floor, so 5,148 widget surfaces were silently dropped from the rank ordering.

The typed pipeline adds a second pass: parse the SERP HTML, type every card by container + heading + structural markers, then spatially join the typed list onto the v2 bbox AOIs. Output is a per-trial ordered list with **9 scroll-axis etypes** (organic, dd_top, native_ad, top_places, knowledge_panel, paa, image_pack, other_widget, unknown_widget) plus 4 off-axis etypes (related_searches, pagination, chrome, dd_right). The bboxes come from CV; the etypes come from HTML; the join is by document order with ad-overlap arbitration.

---

## §1 The two-phase rule

**Phase 1 — HTML widget extraction.** Walk `#rso` (main results) and `#botstuff` (bottom widgets) in DOM order. Type each substantive child div. Type detection runs an 8-tier priority chain: heading text → structural descendants → `data-attrid` → class markers → fallback to `organic`. Output: per-trial typed card list at `data/aoi-html-types/<tid>.json` (n=2,776).

**Phase 2 — Spatial join.** For each CV-extracted bbox in the main column (organic_result + widget from v2, plus shipped ad bboxes), check ad-overlap (≥30%) → label as ad. Otherwise match non-ad bboxes to HTML `#rso` cards in document order (kth bbox ↔ kth HTML card). Append ads CV missed; sweep deep short cv-only entries to `chrome`; assign positions 0..N by y. `#botstuff` / `#rhs` / `dd_right` get `position=−1` (off scroll axis). Output: per-trial typed AOI list at `data/aoi-typed/<tid>.json` (n=2,776, 45,041 entries).

## §2 Why this rule

The v2 widget filter (`organic-result-aoi-extraction.md` §2) is a **bottom-of-page-only** signal: an HTML walk for "Related searches" / "People also search for" h3 headings that sets a y-floor, plus a layout-aware gap heuristic. It correctly excludes `related_searches` and bottom-of-page PASF from the organic-rank denominator. But it has three consequences:

1. **Inline / mid-page widgets pass through as organics.** Image packs, knowledge panels, top_places, and PAA expansions that render *between* organics in the main column are not at-or-below the y-floor, so they emerge from v2 as `organic_result` entries with rank numbers. Per-rank click-rate analyses then mis-attribute their ~7% click rate as if it were organic-result behavior.
2. **All widgets pool under one label.** `widget` is a binary kind in v2; `paa` vs `top_places` vs `image_pack` are not distinguishable from the JSON alone. Any analysis that conditions on widget *type* (CTR by widget, fixation duration by widget, etc.) had to be cut.
3. **HTML structure is unused.** The full SERP HTML ships with the corpus and contains stable widget markers (`#kp-blk`, `data-attrid="kc:/local"`, `<g-map>`, `related-question-pair`). The v2 pipeline only consults HTML for the bottom-of-page widget heading regex, leaving most of the HTML's structural information on the floor.

**Joint typing recovers all three.** The HTML pass labels every card by its semantic kind (cheap, BeautifulSoup over a static document); the spatial join carries those labels onto the bbox geometry the v2 pipeline already computed (no re-extraction). The CV bboxes remain the geometric source of truth — Phase 2 does not move or re-detect any rectangle, it only attaches labels.

## §3 Phase 1: HTML widget extraction

### 3.1 Container scan

```python
soup = BeautifulSoup(html, 'html.parser')

# #rso: main result column (organic + inline widgets)
for handle_idx, child in walk_rso_cards(soup.select_one('#rso')):
    type_label, signature = detect_type(child)
    ...

# #botstuff: bottom widgets (Related searches + pagination)
for ulsxyf in botstuff.select('div.ULSxyf'):
    type_label, signature = detect_type(ulsxyf)
    ...
for nav in botstuff.find_all(attrs={'role': 'navigation'}):
    type_label = 'pagination'
    ...

# #rhs: right-rail KP (off scroll axis)
kp = rhs.select_one('[data-attrid^="kc:/"], .kp-blk')
if kp is not None:
    type_label = 'top_places' if data_attrid.startswith('kc:/local') else 'knowledge_panel'
```

### 3.2 "Main results" wrapper descent

Modern Google SERPs nest organic cards inside a wrapper `<div class="ULSxyf">` with heading "Main results" — typing the wrapper as a single card would collapse all organics into one entry. `_is_main_results_wrapper` detects these (heading text "Main results" OR > 2 organic-class descendants) and `_walk_rso_cards` descends INTO the wrapper to enumerate cards via `_find_card_descendants`. This descent operates on the wrapper subtree, not at `#rso` level, so dedupe doesn't sweep the wrapper's own contents.

### 3.3 Type detection priority chain (8 tiers)

```python
def _detect_type(div):
    classes  = ' '.join(div.get('class') or [])
    heading  = _heading_text(div)            # h3 → h2 → role=heading
    attrid   = div.get('data-attrid', '')

    # Tier 1 — heading text (highest priority; same wrapper class is reused)
    if heading.lower() == 'people also ask':       return 'paa'
    if heading.lower() == 'related searches':      return 'related_searches'
    if heading.lower() == 'local results':         return 'top_places'
    if heading.lower() == 'complementary results': return 'knowledge_panel'
    if heading.lower().startswith('top stories'):  return 'other_widget'
    if heading.lower().startswith('videos for '):  return 'other_widget'
    if heading.lower().startswith('images for '):  return 'image_pack'

    # Tier 2 — structural descendants
    if div.select_one('.related-question-pair'):   return 'paa'
    if div.select_one('g-map'):                    return 'top_places'

    # Tier 3 — data-attrid (knowledge-card namespace, stable across drift)
    if attrid.startswith('kc:/local'):             return 'top_places'
    if attrid.startswith('kc:/'):                  return 'knowledge_panel'

    # Tier 4 — class markers
    if 'TQc1id' in classes:                        return 'knowledge_panel'

    # Tier 5 — ULSxyf with image descendant → image_pack
    if 'ULSxyf' in classes:
        if div.select_one('img[data-src], img[src*="googleusercontent"]'):
            return 'image_pack'
        return 'other_widget'

    # Tier 6 — g-section-with-header (sectioned widget)
    if div.select_one('g-section-with-header'):    return 'other_widget'

    # Tier 7 — class-based organic
    if {'g', 'tF2Cxc', 'hlcw0c'} & set(div.get('class') or []):
        return 'organic'

    # Tier 8 — structural organic (heading + outbound link)
    if heading and div.find('a', href=True):       return 'organic'

    return 'other_widget' or None
```

The priority is deliberate: Google reuses `div.ULSxyf` as a generic widget wrapper for PAA, image packs, news, video, and Related searches. Only the heading text inside disambiguates them. Tier 1 fires before Tier 5 so `<h2>People also ask</h2>` inside a `ULSxyf` wins over the class-based image_pack heuristic.

### 3.4 Output schema (per trial)

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

Phase 1 is purely textual: no bboxes, no pixel coordinates. `html_handle` and `html_signature` are debug breadcrumbs that survive the spatial join.

## §4 Phase 2: spatial join

### 4.1 Inputs

- **`data/aoi-html-types/<tid>.json`** — Phase 1 output (typed cards in DOM order).
- **`AdSERP/data/organic-boundary-data/<tid>.json`** — v2 CV pipeline output (`organic_result` + `widget` bboxes; the geometric source of truth).
- **`AdSERP/data/ad-boundary-data/<tid>.json`** — v1 shipped ad bboxes (`dd_top`, `native_ad`, `dd_right`).

### 4.2 Algorithm

```
main_bboxes  ← organic_result ∪ widget   (from v2, sorted by y)
ad_bboxes    ← dd_top ∪ native_ad         (from v1)
html_rso     ← Phase 1 cards with container='rso'

# Step 1: arbitrate ad-vs-non-ad on each main bbox
for b in main_bboxes:
    if any(overlap(b, ad) ≥ 0.30 for ad in ad_bboxes):
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

### 4.3 Why ad-overlap arbitration before HTML matching

The bbox `organic_result` extractor's ad-subtraction (v2 `is_ad`, with x-overlap requirement) is correct for top-of-page ads at typical aspect ratios but occasionally lets through low-contrast `dd_top` cards (4–5 carousel cells with thin dividers) as a single tall organic. If those reach Step 2 they consume an HTML `rso[0]` slot that should have gone to a real organic, shifting every downstream match by one. Step 1 catches them: any main-column bbox with ≥30% area overlap with a shipped ad rectangle is the ad, regardless of CV classification, and is removed from the HTML-matching queue.

The 30% threshold is asymmetric: `overlap(bbox, ad) ≥ 0.30 OR overlap(ad, bbox) ≥ 0.30`. Asymmetry handles two pathological cases — a thin overlay band (`overlap(bbox, ad)` small but `overlap(ad, bbox)` large) and a CV bbox that fully contains a small ad (the reverse).

### 4.4 Why positional matching (kth bbox ↔ kth HTML card)

Document order is the only stable matching axis. HTML cards have `sourceline` but no rendered y; CV bboxes have y but no DOM identity. Any spatial-only match (nearest-y, IoU) requires both to live in the same coordinate space, which they don't. Empirically the kth-bbox-to-kth-HTML rule holds because Google renders `#rso` children in document order down the page (modulo float/grid layout, which AdSERP queries don't trigger at any scale).

The match fails when the two enumerations disagree on **count** — e.g., CV merges two adjacent cards into one composite, or CV splits one tall composite into two cells, or HTML has a card hidden by CSS. §5 quantifies the disagreement.

### 4.5 Chrome heuristic

A residual class of cv-only entries (no HTML match) cluster at deep tentative positions with short heights — pagination strips, bottom promotional bands, footer regions, "next page" UI furniture. They aren't widgets in the editorial sense; they shouldn't be counted in the rank denominator. The heuristic relabels them to `chrome` and moves them to `position=-1`:

- `tentative_pos ≥ 10` (deep enough that any real organic is unusual)
- `height < 200 px` (short enough to be UI furniture, not a content card)
- `type == 'unknown_widget'` (cv saw, html didn't)

Sweeps 5.0% of total entries (2,255 of 45,041); residual `unknown_widget` rate after sweep is 1.7%.

### 4.6 Output schema (per trial)

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

`source` is the provenance breadcrumb. Eight values in the corpus (in descending share):

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

## §5 Coverage and validation

### 5.1 Etype distribution (full corpus, n=2,776; 45,041 entries)

| Etype | Count | Share | On scroll axis? |
|---|---|---|---|
| organic | 22,530 | 50.0% | yes |
| native_ad | 9,217 | 20.5% | yes |
| pagination | 2,697 | 6.0% | no (position=-1) |
| chrome | 2,255 | 5.0% | no (position=-1) |
| related_searches | 1,811 | 4.0% | no (position=-1) |
| image_pack | 1,600 | 3.6% | yes |
| dd_top | 1,582 | 3.5% | yes |
| dd_right | 861 | 1.9% | no (position=-1) |
| knowledge_panel | 826 | 1.8% | yes |
| paa | 769 | 1.7% | yes |
| unknown_widget | 756 | 1.7% | yes (residual) |
| top_places | 86 | 0.2% | yes |
| other_widget | 51 | 0.1% | yes |

**Newly recovered surfaces (vs v2 organic-only attribution):** image_pack 1,600, knowledge_panel 826, paa 769, top_places 86, other_widget 51 = **3,332 widget surfaces with first-class etype labels**, plus 1,816 cells reclassified from organic to typed-widget within the existing match. Total 5,148 widget surfaces that v2 either pooled into a `widget` bucket or filtered out below the y-floor.

### 5.2 HTML-vs-CV count alignment (full corpus, n=2,776)

`Δ = n_html_rso − n_bbox_main` per trial:

```
exact (Δ=0):     816 / 2,776 = 29.4%
|Δ| ≤ 1:       1,928 / 2,776 = 69.5%
|Δ| ≤ 2:       2,492 / 2,776 = 89.8%
|Δ| ≤ 3:       2,685 / 2,776 = 96.7%
|Δ| ≥ 4:          91 / 2,776 = 3.3%
```

Skew is left-of-zero (HTML undercounts CV) — CV picks up composite-cell fragments and bottom-of-page furniture that HTML doesn't structure as cards. The Δ ≤ −4 tail (91 trials) is dominated by SERPs with rich PAA expansions where HTML has 1 PAA card + many CV-detected expansion rows, plus chrome that hasn't been swept.

The within-±2 figure (89.8%) is the right framing: most disagreement is small and absorbed by the chrome sweep + unknown_widget residual.

### 5.3 Click-attribution coverage

Click coverage holds at ~98% under typed (matches hybrid) since typed retains all ad surfaces from v1 + v2; the difference is that widget surfaces gain their own etype labels rather than being mis-counted as organic_position=N or filtered out. The 1.2% truly-off-AOI residual from v2's hybrid attribution is reduced under typed because Knowledge Panel, image carousels, and top_places — the three biggest contributors to v2's residual — are now typed first-class.

### 5.4 Replication of cascade-era findings

Every 2026-05-03 stress-test finding under `organic_hybrid` reproduces under `typed` within ±0.05 in correlation strength. Headline numbers:

| Finding | hybrid | typed | source |
|---|---|---|---|
| Within-item paired Δ (return − first LF/HF) | +6.31 | **+6.44** | `scripts/lfhf_first_vs_return_paired.py` |
| Pre-scroll Spearman ρ (LF/HF × position) | −0.857 | **−0.857** | NB14 typed re-execution |
| Steep-vs-plateau MW (pooled) | p = 2.6×10⁻²⁵ | **p = 2.3×10⁻²⁵** | NB14 typed re-execution |
| Satopt × knee MW | p = 0.022 | **p = 0.022** | NB30 typed re-execution |
| Click prediction LOSO AUC (M3 nine-feature) | 0.870 | **0.871** | `scripts/nb21_loso_retrain_typed.py` |
| Click prediction LOSO AUC (M4 approach-only) | 0.870 | **0.871** | NB21 typed re-execution |
| Click prediction LOSO AUC (M1 position-only) | 0.667 | **0.665** | NB21 typed re-execution |

The cognitive findings are properties of the trial-level operations, not of widget-vs-organic mis-attribution. Typed cleans up rank-denominator hygiene and unlocks per-etype analyses; it does not move the signal.

## §6 Parameters

All Phase 1 + Phase 2 parameters are recorded in code (no per-trial _meta.params equivalent yet; output schema is what travels). Reproducibility is via the script source under a tagged commit.

### Phase 1 (HTML extraction)

| Parameter | Default | What it controls |
|---|---|---|
| `WIDGET_HEADING_RE` | implicit in tier-1 chain | Heading text → etype map (PAA, Related searches, Local results, Complementary results, Top stories, Videos, Images for, etc.) |
| `ORGANIC_CARD_CLASSES` | `{g, tF2Cxc, hlcw0c, MjjYud}` | DOM classes that mark a div as a card descendant when descending into "Main results" wrappers |
| `_is_main_results_wrapper` threshold | > 2 organic-class descendants | Distinguishes a section-wrapper ULSxyf from a single-widget ULSxyf |
| `data-attrid` prefixes | `kc:/local` → top_places, `kc:/` → knowledge_panel | Knowledge-card namespace; stable across HTML drift |
| `SKIP_TAGS` | `{script, style, noscript, span}` | DOM children that cannot host a card |

### Phase 2 (spatial join)

| Parameter | Default | What it controls |
|---|---|---|
| `AD_OVERLAP_THRESHOLD` (typed) | 0.30 | Min asymmetric overlap for cv_bbox to be reclassified as an ad. Lower than v2's 0.50 because dd_top arbitration (Phase 2) is over a smaller candidate set than v2's `is_ad` (Phase 1). |
| Chrome heuristic — `tentative_pos` floor | 10 | Position depth below which short cv-only entries become chrome candidates |
| Chrome heuristic — `height` ceiling | 200 px | Max height for chrome candidacy (real cards are taller) |
| Chrome heuristic — `type` precondition | `unknown_widget` | Only sweeps cv-only residuals; never touches matched HTML+bbox entries |

## §7 Sensitivity not tested

Ordered by likelihood of changing a downstream result.

1. **HTML class drift.** `tF2Cxc`, `hlcw0c`, `ULSxyf`, `TQc1id`, `MjjYud` are Google's compiled CSS class names. They drift between A/B-test buckets and date-of-capture. The AdSERP corpus was captured 2024 ES; the same script run against a different vintage will misclassify. Mitigation: rely on heading text + `data-attrid` (Tiers 1–3) before class (Tiers 4–7); but if Google removes those signals on a future capture, every Tier-7 fallback to `organic` becomes a fragile match.
2. **`AD_OVERLAP_THRESHOLD` sweep.** 0.30 is a defensible boundary chosen empirically. A `{0.20, 0.30, 0.50}` sweep would establish how many ads slip into `unknown_widget` at the conservative end and how many real organics get reclassified at the permissive end.
3. **Chrome heuristic sensitivity.** The `pos ≥ 10 AND height < 200` rule sweeps 2,255 entries. Both bounds are integer-defensible; sweeping `{8, 10, 12} × {150, 200, 250}` would test the chrome-vs-real-widget boundary. None of the swept entries currently propagate to scroll-axis analyses (they get position=−1), so the cost of error is bounded.
4. **Positional kth-match correctness.** When `n_bbox_main` and `n_html_rso` disagree (70% of trials by ≥ 1), the kth match is by document-order which is *not* the same as y-order in pathological cases. Spot-check on Δ ≤ −2 trials confirms the dominant disagreement is "CV split a composite that HTML kept as one card" — meaning the kth bbox correctly matches the (k − splits)th HTML card up to the split, and after the split the bbox enumeration over-counts. The downstream type label on those over-counted bboxes is `unknown_widget` (no HTML to match), which is the conservative fallback. A composite-aware merge step in Phase 2 could rescue them; not implemented.
5. **Right-rail (#rhs) coverage.** RHS cards (knowledge_panel, top_places-by-attrid) are appended with no geometry (`x = y = null`, position = −1). Per-fixation analyses on RHS content currently can't condition on AOI inside the panel. Adding HTML-derived child-bbox extraction to RHS is a future-work item.
6. **`other_widget` residual.** 51 entries (0.1%) end up in `other_widget` — featured snippets, news packs, video packs that didn't trigger a more specific tier. Their click rate is too small to estimate per-class but they're worth typing first-class in a future iteration.
7. **Composite-cell handling under typed.** v2's `organic_cell` sub-segmentation (composite organics ≥ 320 px get `subdivide_vertical`) happens upstream of Phase 2 and is unchanged. Cells inherit their parent's typed label by inheritance from the v2 `parent_position` field; per-cell types are not separately HTML-derived.

## §8 What's robust regardless of tweaking

- **Schema parity with v2.** The typed JSON does not modify or replace the v2 `organic_result` / `widget` / ad bboxes — it produces a new sibling file that keys etype + geometry + source + html_handle. Downstream code can opt in via `data_loader.typed_aoi_tops()` or stay on `organic_aoi_tops()` for v2 attribution.
- **Geometry source of truth.** Bboxes come from CV. Phase 2 never moves a rectangle. If a downstream consumer trusts v2 geometry, typed adds labels on top without geometric drift.
- **Off-axis convention.** Anything with `position == −1` is off the main scroll axis (right rail, bottom-of-page widgets, chrome, dd_right). Per-rank analyses filter `position >= 0` and the off-axis surfaces never enter the rank denominator.
- **Source provenance.** Every entry carries a `source` breadcrumb identifying its derivation path (HTML+bbox / ad+overlap / chrome-swept / cv-only / html-only / RHS). Audits can re-derive the typing decision without re-running the pipeline.

## §9 Reproducibility

```bash
git clone https://github.com/andyed/attentional-foraging
cd attentional-foraging

# Prerequisites: v2 organic-bbox JSONs must exist (run extract_organic_bboxes.py first)
.venv/bin/python scripts/extract_organic_bboxes.py

# Phase 1 — HTML widget extraction (BeautifulSoup over AdSERP/data/serps/)
.venv/bin/python scripts/extract_html_widget_types.py
# Output: data/aoi-html-types/<tid>.json (n=2,776)

# Phase 2 — Spatial join (typed list with bbox geometry)
.venv/bin/python scripts/build_typed_aoi_map.py
# Output: data/aoi-typed/<tid>.json (n=2,776, 45,041 entries)
# Audit:  scripts/output/aoi-typed/build_typed_aoi_map_summary.json

# Producer cascade (typed-attribution downstream JSONs)
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution typed
.venv/bin/python scripts/compute_butterworth_lfhf.py            --attribution typed
.venv/bin/python scripts/compute_ripa2.py                       --attribution typed
.venv/bin/python scripts/compute_regression_labels.py           --attribution typed
.venv/bin/python scripts/compute_retreat_arcs.py                --attribution typed

# Validation (typed-cascade replication of v2 cascade findings)
.venv/bin/python scripts/lfhf_rank_gradient_typed.py
.venv/bin/python scripts/lfhf_first_vs_return_paired.py --attribution typed
.venv/bin/python scripts/nb21_loso_retrain_typed.py

# Cross-lab export (Jacek-facing per-AOI table)
.venv/bin/python scripts/export_aois_by_trial_id.py --attribution typed
# Output: scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}
#         (37,142 rows × 9 visible etypes; off-axis surfaces excluded)
```

All output JSONs land at `AdSERP/data/<filename>-typed.json` (or `data/aoi-typed/<tid>.json`) as siblings to the legacy absolute and v2 organic files. Schema is documented in §3.4 (HTML) and §4.6 (typed).

## §10 Cross-lab transfer schema

The typed cascade ships a flat per-AOI table at `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 18 columns) suitable for direct loading without re-running the pipeline. Schema mirrors the SIGIR-2025 AdSERP v1 distribution conventions:

| Column | Type | Meaning |
|---|---|---|
| `trial_id` | str | `p{PPP}-b{B}-t{T}` (zero-padded participant uid, 1-indexed batch / trial) |
| `uid` | int | Participant id (1..47) |
| `batch` | int | Block id within participant |
| `trial` | int | Trial id within block |
| `rank` | int | Display-order position on the main scroll axis (0-indexed; `−1` excluded from this export) |
| `etype` | str | One of: `organic`, `dd_top`, `native_ad`, `top_places`, `knowledge_panel`, `paa`, `image_pack`, `unknown_widget`, `other_widget` |
| `organic_rank` | int / null | Within-organic position number (null for non-organics) |
| `top_y` / `bottom_y` / `center_y` | float | Page-space pixel coordinates (document, not viewport) |
| `left_x` / `right_x` | float | Main-column edges (162 / 702 by default) |
| `n_total` | int | Number of AOIs on this trial's scroll axis |
| `n_organic` | int | Number of organics on this trial's scroll axis |
| `doc_height` | int | Full screenshot height in px |
| `screen_height` | int | Viewport height (typically 1024) |
| `html_handle` | str | Phase-1 DOM breadcrumb (`rso[0]`, `botstuff.ULSxyf[0]`, etc.) |
| `html_signature` | str | Phase-1 detection signature (debug provenance) |

Off-axis AOIs (`related_searches`, `pagination`, `chrome`, `dd_right`, RHS knowledge panels) are **excluded** from this export to keep the table focused on the scroll-axis analysis surface. The full per-trial JSONs at `data/aoi-typed/<tid>.json` retain them with `position = −1`.

Coordinate convention: page-space pixels (document coordinates, not viewport). FPOGY from AdSERP gaze logs is already page-space (per the corpus README); bisect `top_y / bottom_y` directly without adding scroll. Click `click_y` is also page-space.

## §11 Where this rule appears in published / draft work

- **AdSERP corpus enrichment, v1.2** — primary artifact. Per-trial typed JSONs in `data/aoi-typed/` (n=2,776). Companion to v1.1 organic-bbox enrichment. Candidate for back-contribution to Zenodo if the AdSERP authors agree.
- **`notebooks-v2/data_loader.py`** — `load_typed_aois`, `typed_aoi_bands`, `typed_aoi_tops`, `typed_aoi_etypes`, `attribute_click_to_typed` consume these JSONs; producer scripts route through these functions when `--attribution typed`.
- **ETTAC 2026 (Lyon, Aug 21)** — every per-rank claim using pixel-accurate AOIs runs under typed by default (within-item paired return-vs-first LF/HF, organic-only LF/HF gradient, four-class motor dissociation). Companion paper figure: `paired-return.{pdf,png}` (within-item paired Δ scatter + per-rank forest plot).
- **CIKM 2026 paper** — algorithmic submission. Per-result-AOI episode geometry depends on typed for the four-class taxonomy (clicked / deferred / evaluated-rejected / not-approached) when widget surfaces enter the consideration set.
- **`approach-retreat`** — gh-pages replay viewer (andyed.github.io/approach-retreat/replay/) renders typed AOIs as overlay rectangles per trial; widget injection (image_pack, knowledge_panel, paa, top_places, related_searches, pagination) reads from `data/aoi-typed/` directly.
- **`pupil-lfhf`** — Butterworth LF/HF + RIPA2 validation pipelines support `--attribution typed`; Fig 5 (`make_fig5.py`) defaults to typed.
- **Upstream conversation with AdSERP authors** (Latifzadeh / Gwizdka / Leiva) — Jacek-facing methodology pack: this doc + `aoi-coverage-contribution.md` + the cross-lab export at §10. Lead deliverable for Thursday meeting.

## §12 Status

**Status:** current as of 2026-05-04; canonical implementations: `scripts/extract_html_widget_types.py` + `scripts/build_typed_aoi_map.py`. Applied to the full corpus (2,776 trials, 0 errors).

History:

- 2026-05-03 — scope captured in `docs/drafts/aoi-html-vision-pipeline-scope-2026-05-03.md` (gitignored). Motivated by missing widget surfaces in `organic_hybrid` attribution: image_pack 1,600, knowledge_panel 826, paa 769, top_places 86 — pooled into `widget` and filtered below the y-floor under v2.
- 2026-05-04 — Phase 1 + Phase 2 first-pass implementations on `feat/aoi-pipeline-v3-typed` branches across `attentional-foraging`, `approach-retreat`, `pupil-lfhf`. Phase 2 ad-overlap arbitration revised to walk main bboxes (not ad bboxes) to prevent double-counting; "Main results" wrapper descent fixed in Phase 1 to descend INTO wrappers; chrome heuristic added to sweep bottom-of-page furniture.
- 2026-05-04 — Producer migrations: `compute_cursor_approach_features.py`, `compute_butterworth_lfhf.py`, `compute_ripa2.py`, `compute_regression_labels.py`, `compute_retreat_arcs.py` all gain `--attribution typed`. Tier-A notebooks (NB04, NB14, NB15, NB18, NB22, NB23, NB24, NB25, NB28, NB30, NB32) re-executed under typed; Key Claims appended with typed-cascade subsections.
- 2026-05-04 — NB21 LOSO retrain under typed: M3 = 0.871, M4 = 0.871, M1 = 0.665 (matches `organic_hybrid` ±0.005 across all three).
- 2026-05-04 — Cross-lab export: `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 9 etypes) generated for Jacek's lab.
- 2026-05-04 — Replay viewer (`approach-retreat/site/replay/`) regenerates 141 trial JSONs with typed widget injection; cache-safe image load + type-specific WIDGET_TAG dict (IP, KP, PAA, TP, RS, PG, OW, ?W).

**Pending downstream work:**
- Composite-aware merge step in Phase 2 to rescue Δ ≤ −2 trials where CV splits HTML composites.
- RHS child-bbox extraction so per-fixation analyses can condition on AOI inside knowledge panels.
- Class-drift sensitivity audit on a non-AdSERP capture to confirm Tiers 1–3 (heading + data-attrid + structural descendants) carry the load when Tiers 4–7 drift.
- Per-etype click-rate publication: organic 15.9%, dd_top 17.1%, paa 7.6% (currently in NB22 typed; needs lift into the contribution doc and ETTAC §3.3 prose).
