# AdSERP AOI Coverage — Contribution Spec

**For:** Jacek Gwizdka et al.
**Date:** 2026-05-02
**Stable ID:** M:aoi-coverage-contribution
**Companion to:** [`organic-result-aoi-extraction.md`](./organic-result-aoi-extraction.md) (full pipeline spec, ~600 lines), [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md) (downstream impact across K-IDs)

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

CV row-projection on the screenshots themselves — operating on rendered pixels, not source HTML. Each AdSERP card is a vertically-bounded region of high pixel-variance separated from neighbors by a band of low pixel-variance whitespace. The detection rule is one line:

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

## §3 Coverage and validation

### Pipeline-vs-HTML alignment (full corpus, n=2,776)

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

Per-flavor headlines from the click-prediction LOSO retrain (NB21:K-bbox-* series; typed values pending NB21 retrain — see Phase-4 recompute plan):

| Model | absolute | organic | hybrid | typed |
|---|---|---|---|---|
| M3 LOSO AUC (full nine-feature) | 0.859 | **0.865** | **0.870** | *[pending]* |
| M4 LOSO AUC (approach-only) | 0.861 | **0.864** | **0.870** | *[pending]* |
| M1 LOSO AUC (position-only) | 0.613 | **0.727** | 0.667 | *[pending]* |
| Position standardized coefficient | −0.130 | **−0.248** | −0.112 | *[pending]* |

Hybrid attribution surfaces an empirical finding that absolute structurally hid: **dd_top (top-of-page ads) clicks at 17.1%, the highest rate of any SERP surface** — vs organic 14.6%, native_ad 5.2%. The previous absolute-attribution analysis pooled dd_top fixations into "organic position 1," masking this.

**Typed attribution adds non-ad widgets** to the rank ordering: image packs (1,600 trial-instances), knowledge panels (826), People Also Ask (769), top places / local pack (86), and assorted long-tail widgets (51 other_widget + 756 unknown_widget after a chrome heuristic sweeps bottom-of-page furniture off the scroll axis). 5,148 widget surfaces that were previously pooled with organics or filtered out are now correctly typed. Click coverage holds at ~98% (matches hybrid) since typed retains all ad surfaces; the difference is that widget surfaces gain their own etype labels rather than being mis-counted.

**Typed cascade replication** (full per-finding audit in [CHANGELOG 2026-05-04](../../CHANGELOG.md)): every 2026-05-03 stress-test finding reproduces under typed within ±0.02 in correlation strength. Headline numbers shift by < 0.05 — within-item paired Δ +6.31 → +6.44; pre-scroll Spearman ρ identical at −0.857; pooled steep-vs-plateau MW p = 2.6×10⁻²⁵ → 2.3×10⁻²⁵; satopt × knee MW p = 0.022 (identical). The cognitive findings are properties of the trial-level operations, not of widget-vs-organic mis-attribution.

Other downstream cascade impacts (full audit at [`attribution-cascade-synthesis.md`](./attribution-cascade-synthesis.md)):

- **NB14 Butterworth LF/HF position gradient:** ρ = −0.927 → −0.655 (full corpus, p < 10⁻⁴); steep-phase ρ = −1.000 over P0–P3 (p = 3.2 × 10⁻²³) holds. Plateau ρ flips +0.482 → +0.321 (n.s.).
- **NB22 four-class motor dissociation:** preserved (cursor-gaze distance p < 10⁻⁹, dwell p < 10⁻¹⁹).
- **R1 will-regress vs no-regress dissociation:** LF/HF leg strengthens (p = 0.011 → p = 1.1 × 10⁻³); RIPA2 leg collapses (p = 0.0058 → p = 0.80) — most parsimonious reading is per-fixation rank-pooling artifact under absolute. Documented at [`docs/null-findings/r1-ripa2-bbox-collapse.md`](../null-findings/r1-ripa2-bbox-collapse.md).

## §5 Limitations to disclose

- Under **organic** and **organic_hybrid**, the 1.2% truly-off-AOI residual is content the pipeline doesn't model (Knowledge Panel, image carousels, footer). **Resolved under typed** (2026-05-04): non-ad widgets (image packs, KP, PAA, top_places, related_searches) are now first-class etype labels via HTML+vision joint typing.
- Under **typed**, a 1.8% residual `unknown_widget` rate persists for cells the CV bbox extractor finds that HTML doesn't structure as named widgets. These cluster at deep position (median y = 2,371 px, p25 position = P11) and short height (median 102 px) — primarily bottom-of-page furniture. A chrome heuristic (cv-only entries at position ≥ 10 with height < 200 px) sweeps 5.3% of cells off the scroll axis to keep the analysis surface clean.
- Carousel cell sub-segmentation works on tall organics (`≥320 px`) — a few smaller composites slip through. Built-in `SUSPICIOUS_H = 350 px` flag catches the dual case of false composites.
- The ROW_STD_THRESHOLD is global, not per-trial-tuned. Trials with unusual contrast can drift; the visual audit pass catches them.
- Coverage above 88.3% within ±2 of HTML organic count is principled (organic flavor); under typed, 90% of trials have |Δ| ≤ 2 between HTML card count and CV bbox count, with the residual driven by composite-cell splits and "Main results" wrappers (Phase 1 descends into ULSxyf wrappers when they contain >2 organic-class descendants).

## §6 Reproducibility

```bash
git clone https://github.com/andyed/attentional-foraging
cd attentional-foraging

# Pipeline (operates on /Volumes/andyed/.../adserp-dataset/ screenshots)
.venv/bin/python scripts/extract_organic_bboxes.py

# Producer chain
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic
.venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic_hybrid
.venv/bin/python scripts/compute_butterworth_lfhf.py --attribution organic
.venv/bin/python scripts/compute_ripa2.py --attribution organic
.venv/bin/python scripts/compute_regression_labels.py --attribution organic

# Validation (NB21 LOSO retrain)
.venv/bin/python scripts/nb21_loso_retrain_organic.py
.venv/bin/python scripts/nb21_loso_retrain_hybrid.py
```

All output JSONs land at `AdSERP/data/<filename>-organic.json` (or `-organic-hybrid.json`) as siblings to the legacy absolute-attribution files. Schema is unchanged.

A 2.4 MB consolidated AOI export ships at commit [`cee14805`](https://github.com/andyed/attentional-foraging/commit/cee1480503527f2d259c269c1ba33c9c13f0a7ca) for direct loading without re-running the pipeline.

## §7 Stable IDs for citation

Cite this contribution via the project's K-claims system: rows in [`docs/notebook-key-claims.md`](../notebook-key-claims.md) carry stable `[NB##:K##]` (or `K-bbox-##` for cascade-era) tags. Pipeline reproducibility is `M:organic-result-aoi-extraction`; cascade impact synthesis is `M:attribution-cascade-synthesis`; this document is `M:aoi-coverage-contribution`.
