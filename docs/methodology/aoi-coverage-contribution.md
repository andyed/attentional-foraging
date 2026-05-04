# AdSERP AOI Coverage — Contribution Spec

**For:** Jacek Gwizdka et al.
**Date:** 2026-05-04 (typed cascade landed; v2 framing retained as historical comparison)
**Stable ID:** M:aoi-coverage-contribution
**Companion to:** [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md) (v2 CV pipeline spec, ~600 lines), [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md) (v3 HTML+vision joint pipeline spec, post-2026-05-04 primary), [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md) (downstream impact across K-IDs)

---

## TL;DR

AdSERP v1 ships ad bboxes (`native_ad`, `dd_top`, `dd_right`) and full-page screenshots, but **no organic-result bboxes**, no per-cell carousel subdivision, and no separation of refinement widgets from organics. We've added all four. Pipeline runs on the public corpus, schema mirrors v1 ad-boundary JSON, full corpus (n=2,776) extracted as of 2026-05-01.

The contribution unlocks per-organic-rank analyses that band-estimation can't support cleanly: the four-class consideration-set taxonomy, organic-only LF/HF gradient, organic-only LOSO click prediction, and a properly-attributed click rate per surface (organic, dd_top, native_ad).

---

## §1 The gap

For per-rank analyses, AdSERP v1 leaves three options:

1. **Band estimation** — divide document height by `count_results_html(tid)`, assign fixations to nearest band. Bands are wrong wherever ads sit between organics, where rich snippets vary card height, or where bottom-of-page widgets are h3-anchored alongside organics. Per-result claims at this resolution silently mislabel marginal fixations and silently include refinement-widget visits in the per-rank denominator.
2. **HTML-derived bboxes** — the SERP HTML snapshots ship with the corpus, but they don't carry rendered pixel coordinates. Re-rendering them in a headless browser is fragile (Google A/B-tests rendering, fonts drift, snapshots aren't byte-stable). Most attempts fail trial-by-trial without a clear failure signal.
3. **Pool ads with organics under "absolute" rank** — the legacy approach. Easy, but per-rank claims become un-interpretable when a "rank-1" is sometimes an organic and sometimes an ad with very different click policies.

## §2 What we contributed

**Two complementary AOI extraction passes** that AdSERP v1 doesn't ship:

1. **CV row-projection on the screenshots** (v2, organic-bbox pipeline) — pixel-accurate bboxes for organics, ad-rail cells, and bottom-of-page widgets. Spec: [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md). Covers geometry.
2. **HTML+vision joint widget typing** (v3, typed cascade, 2026-05-04) — every card gets a semantic etype label by parsing the SERP HTML and spatially joining the labels onto the v2 bboxes. Spec: [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md). Covers labels.

The two passes compose: typed reuses v2 geometry without modification and adds a 9-etype taxonomy on top via a kth-bbox-↔-kth-HTML-card document-order join.

### §2.1 v2 CV row-projection (geometry source of truth)

CV row-projection operates on rendered pixels, not source HTML. Each AdSERP card is a vertically-bounded region of high pixel-variance separated from neighbors by a band of low pixel-variance whitespace. The detection rule is one line:

```
content_row[y] = std(screenshot[y, COL_X : COL_RIGHT]) >= ROW_STD_THRESHOLD
```

with parameters tuned and recorded per-trial. A run of consecutive content rows is a card; small gaps (<24 px) collapse as within-card line gaps; larger gaps separate cards. Detected cards are then classified:

- **Drop ads.** Cards overlapping a shipped ad rectangle in *both* y and x are removed (so that what's left is non-ad content).
- **Drop widgets.** Cards at or below a per-trial widget y-floor (set when HTML signals refinement-widget headings like "People also ask" or "Related searches") are removed.
- **Number top-to-bottom.** Survivors become `organic_result[1..N]`.
- **Sub-segment composites.** Tall organics (≥320 px) are also fed into row-projection sub-segmentation and emit `organic_cell` entries with a back-pointer to the parent — captures local 3-packs, multi-row PAA expansions, image carousels.
- **Subdivide ad rails.** `dd_top` and `dd_right` become per-cell entries (`dd_top_cell[1..M]`, `dd_right_cell[1..K]`) so that fixations on individual carousel items are attributable.

Schema is **additive** to v1 — new keys (`organic_result`, `organic_cell`, `dd_top_cell`, `dd_right_cell`) coexist with the v1 ad keys unchanged.

### §2.2 v3 HTML+vision joint widget typing (etype labels)

The v2 widget filter is a **bottom-of-page-only** signal: an h3-heading regex (`Related searches` / `People also search for`) plus a layout-aware gap heuristic. It correctly excludes bottom-of-page widgets from the organic-rank denominator but pools every typed widget under one `widget` bucket and silently passes inline / mid-page widgets (image packs, knowledge panels, top_places, PAA) through as `organic_result` entries — so 5,148 widget surfaces ended up either filtered out or mis-typed under v2.

The typed cascade adds a **two-phase** post-processor on top of v2:

- **Phase 1 — HTML widget extraction** (`scripts/extract_html_widget_types.py`). BeautifulSoup walks `#rso` (with descent into "Main results" `ULSxyf` wrappers when they contain > 2 organic-class descendants) and `#botstuff`. Each substantive child div is typed via an 8-tier priority chain: heading text → structural descendants (`.related-question-pair`, `<g-map>`) → `data-attrid` (`kc:/local`, `kc:/`) → class markers (`TQc1id`, `tF2Cxc`, `g`, `hlcw0c`) → fallback. Output: per-trial typed card list at `data/aoi-html-types/<tid>.json` (n=2,776).
- **Phase 2 — Spatial join** (`scripts/build_typed_aoi_map.py`). For each main-column bbox from v2, check ≥ 30% asymmetric overlap with shipped ad rectangles (`dd_top` + `native_ad`) → label as ad. Otherwise match non-ad bboxes to HTML `#rso` cards in document order (kth bbox ↔ kth HTML card). Append ads CV missed; sweep deep short cv-only entries to `chrome` (`pos ≥ 10 ∧ height < 200 px`); assign positions 0..N by y. `#botstuff` / `#rhs` / `dd_right` get `position = −1` (off scroll axis). Output: per-trial typed AOI list at `data/aoi-typed/<tid>.json` (n=2,776, 45,041 entries, 0 errors).

The bboxes come from CV; the etypes come from HTML; the join is by document order with ad-overlap arbitration. Phase 2 never moves a rectangle — geometry inherits from v2.

**Etype taxonomy (13 labels, 9 on scroll axis + 4 off-axis):**

| Etype | Detection signal (Tier) | On scroll axis? | Click rate (typed corpus) |
|---|---|---|---|
| `organic` | class `g`/`tF2Cxc`/`hlcw0c` (T7) or heading + outbound link (T8) | yes | 15.9% |
| `dd_top` | bbox-vs-ad overlap ≥ 30% with `dd_top` (Phase 2) | yes | **17.1%** |
| `native_ad` | bbox-vs-ad overlap ≥ 30% with `native_ad` (Phase 2) | yes | 5.2% |
| `paa` | heading "People also ask" (T1) or `.related-question-pair` (T2) | yes | 7.6% |
| `image_pack` | heading "Images for ..." (T1) or `ULSxyf` + `<img>` (T5) | yes | low (n estimate) |
| `knowledge_panel` | heading "Complementary results" (T1) / `data-attrid="kc:/..."` (T3) / `TQc1id` (T4) | yes | low (n estimate) |
| `top_places` | heading "Local results" (T1) / `<g-map>` (T2) / `data-attrid="kc:/local..."` (T3) | yes | low (n estimate) |
| `other_widget` | featured snippet / news / video / sectioned widget (T1, T6) | yes | low (n estimate) |
| `unknown_widget` | cv saw, html had no card at this index (Phase-2 residual) | yes | residual |
| `related_searches` | heading "Related searches" in `#botstuff` (T1) | no (pos=−1) | n/a |
| `pagination` | `<div role="navigation">` in `#botstuff` | no (pos=−1) | n/a |
| `chrome` | swept by chrome heuristic (cv-only, deep, short) | no (pos=−1) | n/a |
| `dd_right` | shipped `dd_right` ads | no (pos=−1) | low |

Schema is again **additive** to v1 + v2: typed JSONs live at `data/aoi-typed/<tid>.json` as siblings to the v2 organic-bbox JSONs; downstream code opts in via `data_loader.typed_aoi_tops()` / `typed_aoi_etypes()` while v2 attribution remains available.

## §3 Coverage and validation

### v3 typed pipeline alignment (full corpus, n=2,776; 2026-05-04)

`Δ = n_html_rso − n_bbox_main` per trial:

```
exact (Δ=0):     816 / 2,776 = 29.4%
|Δ| ≤ 1:       1,928 / 2,776 = 69.5%
|Δ| ≤ 2:       2,492 / 2,776 = 89.8%
|Δ| ≤ 3:       2,685 / 2,776 = 96.7%
```

Skew is left-of-zero (HTML undercounts CV) — CV picks up composite-cell fragments and bottom-of-page furniture that HTML doesn't structure as cards. The chrome heuristic absorbs 2,255 of those (5.0% of total entries), leaving a 1.7% residual `unknown_widget` rate.

**Etype distribution across 45,041 entries:**

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

Newly typed widget surfaces vs v2 `organic_hybrid`: image_pack 1,600 + knowledge_panel 826 + paa 769 + top_places 86 + other_widget 51 = **3,332 first-class etyped widgets**, plus 1,816 reclassified within the existing match. Total **5,148 widget surfaces** that v2 either pooled into a single `widget` bucket or dropped below the y-floor.

### v2 pipeline-vs-HTML alignment (full corpus, n=2,776; 2026-05-01)

```
exact (delta = 0):       683 / 2,776  =  24.6%
|delta| ≤ 1:           1,801 / 2,776  =  64.9%
|delta| ≤ 2:           2,451 / 2,776  =  88.3%
mean delta = -0.20  ·  median 0  ·  IQR [-1, 0, +1]
```

`delta` = pipeline organic count − HTML-derived organic-h3 count (ad-overlapping h3s excluded). The HTML count is **not** ground truth: it counts widget-heading h3s (PAA, Related searches) as "organic" slots, so `delta < 0` is sometimes the pipeline being correctly stricter than the HTML enumeration.

### Click-attribution audit (full corpus, n=2,775 trials)

Tolerance-aware bbox attribution: clicks within 30 px of an organic edge snap to that organic, **after** rejecting clicks inside any ad/widget rectangle. The 30 px elbow is empirical (92.5% of off-AOI clicks are within 30 px of the nearest organic edge; further loosening rescues ~0.3 pp).

| Bucket | Count | Share |
|---|---|---|
| Organic (strict + 30 px snap) | **2,181** | **78.6%** |
| All ads (`native_ad` + `dd_top` + `dd_right`) | 557 | 20.1% |
| Filtered widgets (PAA / Related searches) | 5 | 0.2% |
| Truly off-AOI (KP / image carousel / footer / large gaps) | **32** | **1.2%** |

The 1.2% is the actual methodology-limitation residual — content the pipeline doesn't model (Knowledge Panel cards, image carousels above results, footer regions). Not 15.4%, as strict-containment-only numbers would suggest.

### Visual audit and self-checks

- Per-trial `_meta.params` records every threshold (reproducible by re-running with the recorded parameters).
- `SUSPICIOUS_H = 350 px` flags non-composite cards for human review.
- The full corpus (2,776 PNGs) was visually spot-checked via a side-by-side overlay viewer; the iteration that landed on `feat/aoi-pipeline-v2` came out of three rounds of visual review (widget filter / composite cells / band-y guard against featured-snippet false positives).
- Claude 4.7's vision capability partially audits the pipeline against the rendered screenshots — a fixable gap surfaced this way during the followup.

## §4 What this unlocks

**Four rank-attribution flavors** now coexist on the same corpus (post-2026-05-04 typed cascade):

| Flavor | Definition | Records (NB21 LOSO) | Trials | Click rate | Etype taxonomy |
|---|---|---|---|---|---|
| **absolute** | Legacy h3 + ads pooled, band-estimated | 13,419 | 2,339 | 16.6% | 2 (organic / ad) |
| **organic** | Bbox organics only, ads excluded | 14,760 | 2,701 | 14.9% | 1 (organic) |
| **organic_hybrid** | Bbox organics + dd_top + native_ad in display order, dd_right excluded | 19,908 | 2,774 | 13.0% | 3 (organic / dd_top / native_ad) |
| **typed** *(2026-05-04)* | HTML+vision joint widget typing across all SERP cards (organic + ads + non-ad widgets), display order | 19,774 | 2,774 | 13.0% | 9 (organic / dd_top / native_ad / top_places / knowledge_panel / paa / image_pack / unknown_widget / other_widget) |

Per-flavor headlines from the click-prediction LOSO retrain (NB21:K-bbox-* series; typed numbers from `scripts/nb21_loso_retrain_typed.py`, 2026-05-04):

| Model | absolute | organic | hybrid | typed |
|---|---|---|---|---|
| M3 LOSO AUC (full nine-feature) | 0.859 | **0.865** | **0.870** | **0.871** |
| M4 LOSO AUC (approach-only) | 0.861 | **0.864** | **0.870** | **0.871** |
| M1 LOSO AUC (position-only) | 0.613 | **0.727** | 0.667 | **0.665** |
| Position standardized coefficient | −0.130 | **−0.248** | −0.112 | **−0.108** |

The typed retrain confirms the v2-cascade reading: the rank denominator hygiene matters for M1 (position-only), where pooling ads with organics under `absolute` deflates the coefficient and underestimates position's standalone predictive lift; correctly typed widget+ad surfaces hold M3/M4 at 0.871 — within ±0.005 of `organic_hybrid` and ±0.012 of legacy `absolute`. The signal is in the cursor approach geometry, not in the AOI taxonomy.

Hybrid attribution surfaces an empirical finding that absolute structurally hid: **dd_top (top-of-page ads) clicks at 17.1%, the highest rate of any SERP surface** — vs organic 14.6%, native_ad 5.2%. The previous absolute-attribution analysis pooled dd_top fixations into "organic position 1," masking this.

**Typed attribution adds non-ad widgets** to the rank ordering: image packs (1,600 trial-instances), knowledge panels (826), People Also Ask (769), top places / local pack (86), and assorted long-tail widgets (51 other_widget + 756 unknown_widget after a chrome heuristic sweeps bottom-of-page furniture off the scroll axis). 5,148 widget surfaces that were previously pooled with organics or filtered out are now correctly typed. Click coverage holds at ~98% (matches hybrid) since typed retains all ad surfaces; the difference is that widget surfaces gain their own etype labels rather than being mis-counted.

**Typed cascade replication** (full per-finding audit in [CHANGELOG 2026-05-04](../../CHANGELOG.md)): every 2026-05-03 stress-test finding reproduces under typed within ±0.02 in correlation strength. Headline numbers shift by < 0.05 — within-item paired Δ +6.31 → +6.44; pre-scroll Spearman ρ identical at −0.857; pooled steep-vs-plateau MW p = 2.6×10⁻²⁵ → 2.3×10⁻²⁵; satopt × knee MW p = 0.022 (identical). The cognitive findings are properties of the trial-level operations, not of widget-vs-organic mis-attribution.

Other downstream cascade impacts (full audit at [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md)):

- **NB14 Butterworth LF/HF position gradient:** ρ = −0.927 → −0.655 (full corpus, p < 10⁻⁴); steep-phase ρ = −1.000 over P0–P3 (p = 3.2 × 10⁻²³) holds. Plateau ρ flips +0.482 → +0.321 (n.s.).
- **NB22 four-class motor dissociation:** preserved (cursor-gaze distance p < 10⁻⁹, dwell p < 10⁻¹⁹).
- **R1 will-regress vs no-regress dissociation:** LF/HF leg strengthens (p = 0.011 → p = 1.1 × 10⁻³); RIPA2 leg collapses (p = 0.0058 → p = 0.80) — most parsimonious reading is per-fixation rank-pooling artifact under absolute. Documented at [`docs/null-findings/r1-ripa2-bbox-collapse.md`](../null-findings/r1-ripa2-bbox-collapse.md).

## §5 Limitations to disclose

- Under **organic** and **organic_hybrid**, the 1.2% truly-off-AOI residual is content the pipeline doesn't model (Knowledge Panel, image carousels, footer). **Resolved under typed** (2026-05-04): non-ad widgets (image packs, KP, PAA, top_places, related_searches) are now first-class etype labels via HTML+vision joint typing.
- Under **typed**, a 1.7% residual `unknown_widget` rate persists for cells the CV bbox extractor finds that HTML doesn't structure as named widgets. These cluster at deep position (tentative pos ≥ 10) and short height (< 200 px) — primarily bottom-of-page furniture. A chrome heuristic sweeps 5.0% of total entries (2,255 of 45,041) off the scroll axis to keep the analysis surface clean.
- **HTML class drift.** The Phase-1 detector relies on Google's compiled CSS class names (`tF2Cxc`, `hlcw0c`, `ULSxyf`, `TQc1id`, `MjjYud`) at Tiers 4–7. These drift between A/B-test buckets and capture vintage. The AdSERP corpus was captured in 2024 ES; running Phase 1 against a different vintage will misclassify Tier-7 fallbacks. Mitigation: Tiers 1–3 (heading text, structural descendants, `data-attrid`) are stable across drift and carry the load on widgets; class-only matches degrade gracefully to `other_widget` rather than misattribute.
- **"Main results" wrapper edge cases.** Modern Google nests organics inside a wrapper `<div class="ULSxyf">` with heading "Main results"; Phase 1 detects this (heading match OR > 2 organic-class descendants) and descends into it. Trials where the wrapper has ≤ 2 organic-class descendants but is still a wrapper (rare; not observed in the audit) would collapse all organics into one entry.
- **Composite-cell splits drive the Δ ≤ −2 left tail.** When CV's `subdivide_vertical` splits a tall composite organic into multiple cells but HTML kept it as one card, the kth-bbox-↔-kth-HTML join over-counts on the bbox side and emits the extra cells as `unknown_widget`. Spot-check confirms this is the dominant source of Δ ≤ −2 (91 trials).
- Carousel cell sub-segmentation works on tall organics (`≥320 px`) — a few smaller composites slip through. Built-in `SUSPICIOUS_H = 350 px` flag catches the dual case of false composites.
- The ROW_STD_THRESHOLD is global, not per-trial-tuned. Trials with unusual contrast can drift; the visual audit pass catches them.
- Coverage above 88.3% within ±2 of HTML organic count is principled (organic flavor); under typed, 89.8% of trials have |Δ| ≤ 2 between HTML card count and CV bbox count, with the residual driven by composite-cell splits and "Main results" wrappers (Phase 1 descends into ULSxyf wrappers when they contain >2 organic-class descendants).
- **Right-rail (#rhs) bbox coverage.** RHS knowledge panels and top_places-by-attrid are typed and emitted with `position = −1` and `x = y = null`. Per-fixation analyses on RHS content currently can't condition on AOI inside the panel. Adding HTML-derived child-bbox extraction to RHS is future work.

## §6 Reproducibility

```bash
git clone https://github.com/andyed/attentional-foraging
cd attentional-foraging

# ── v2 CV pipeline (geometry source of truth) ──────────────────────
.venv/bin/python scripts/extract_organic_bboxes.py

# v2 producer chain
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic_hybrid
.venv/bin/python scripts/compute_butterworth_lfhf.py        --attribution organic
.venv/bin/python scripts/compute_ripa2.py                   --attribution organic
.venv/bin/python scripts/compute_regression_labels.py       --attribution organic

# ── v3 typed cascade (HTML+vision joint widget typing, 2026-05-04) ─
# Phase 1: HTML widget extraction (BeautifulSoup over AdSERP/data/serps/)
.venv/bin/python scripts/extract_html_widget_types.py
# → data/aoi-html-types/<tid>.json (n=2,776)

# Phase 2: spatial join (typed list with bbox geometry)
.venv/bin/python scripts/build_typed_aoi_map.py
# → data/aoi-typed/<tid>.json (n=2,776, 45,041 entries)
# → scripts/output/aoi-typed/build_typed_aoi_map_summary.json (audit)

# v3 producer chain (typed-attribution downstream JSONs)
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

# ── Cross-lab export (Jacek-facing per-AOI table) ──────────────────
.venv/bin/python scripts/export_aois_by_trial_id.py --attribution typed
# → scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}
#   (37,142 rows × 9 visible etypes; off-axis surfaces excluded)
```

All output JSONs land at `AdSERP/data/<filename>-organic.json` / `-organic-hybrid.json` / `-typed.json` (or `data/aoi-typed/<tid>.json`) as siblings to the legacy absolute-attribution files. Schema is unchanged.

A 2.4 MB consolidated v2 AOI export ships at commit [`cee14805`](https://github.com/andyed/attentional-foraging/commit/cee1480503527f2d259c269c1ba33c9c13f0a7ca); a v3 typed export is described in §7 below.

## §7 Cross-lab export schema (Jacek-facing typed deliverable)

Flat per-AOI table at `scripts/output/adserp_aois_by_trial_id_typed.{csv,jsonl}` (37,142 rows × 18 columns) — the headline cross-lab deliverable for the typed cascade. Schema mirrors the SIGIR-2025 AdSERP v1 distribution conventions and is loadable without re-running the pipeline.

| Column | Type | Meaning |
|---|---|---|
| `trial_id` | str | `p{PPP}-b{B}-t{T}` (zero-padded participant uid, 1-indexed batch / trial); regex `^p(\d{3})-b(\d+)-t(\d+)$` |
| `uid` | int | Participant id (1..47) |
| `batch` | int | Block id within participant |
| `trial` | int | Trial id within block |
| `rank` | int | Display-order position on the main scroll axis (0-indexed; off-axis AOIs excluded from this export) |
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

**Off-axis AOIs** (`related_searches`, `pagination`, `chrome`, `dd_right`, RHS knowledge panels) are **excluded** from this export to keep the table focused on the scroll-axis analysis surface. The full per-trial JSONs at `data/aoi-typed/<tid>.json` retain them with `position = −1` for any consumer that wants to reason about right-rail or bottom-of-page surfaces.

**Coordinate convention.** Page-space pixels (document coordinates, not viewport). FPOGY from AdSERP gaze logs is already page-space (per the corpus README); bisect `top_y` / `bottom_y` directly without adding scroll offset. Click `click_y` is also page-space.

**Per-etype trial coverage** (rows in summary file `adserp_aois_by_trial_id_typed_summary.json`):

```
organic         22,354    image_pack       1,584    knowledge_panel    746
native_ad        9,217    paa                769    other_widget        50
dd_top           1,582    top_places          84    unknown_widget     756
```

Companion pipeline spec for the typing logic itself: [`typed-aoi-pipeline.md`](./typed-aoi-pipeline.md).

## §8 Stable IDs for citation

Cite this contribution via the project's K-claims system: rows in [`docs/notebook-key-claims.md`](../notebook-key-claims.md) carry stable `[NB##:K##]` (or `K-bbox-##` for v2 cascade-era, `K-typed-##` for v3 cascade-era) tags. Methodology stable IDs:

- **`M:organic-result-aoi-extraction`** — v2 CV row-projection pipeline (geometry source of truth).
- **`M:typed-aoi-pipeline`** — v3 HTML+vision joint widget typing pipeline (etype source of truth, post-2026-05-04 primary).
- **`M:attribution-cascade-synthesis`** — downstream cascade impact across K-IDs under all four flavors.
- **`M:aoi-coverage-contribution`** — this document (Jacek-facing summary).
