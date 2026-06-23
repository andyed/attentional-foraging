# dd_top cell split — the `typed_gapfill_cellsplit` flavor

**Date:** 2026-06-23
**Stable ID:** M:dd-top-cellsplit
**Producer (flavor):** `scripts/export_aois_by_trial_id.py --attribution typed_gapfill_cellsplit`
(wired into the public entry point `scripts/build_aois.py --flavor typed_gapfill_cellsplit`)
**Outputs:**
`scripts/output/adserp_aois_by_trial_id_typed_gapfill_cellsplit.csv` (+ `.jsonl`, `_summary.json`),
`scripts/output/cellsplit_coverage.json` (coverage),
`scripts/output/cellsplit_click_composition/` (within-carousel click descriptive).
**Companion:** [`dd-top-cell-promiscuity.md`](../dd-top-cell-promiscuity.md) is the *individual-difference* read of the same cells (a downstream sibling-track finding, out of scope for this resource layer). This note covers only the **resource** layer: extraction, coverage, schema.

---

## What it is

`typed_gapfill_cellsplit` is a **cell-aware superset** of the public `typed_gapfill`
flavor. Every `typed_gapfill` main-axis card is emitted unchanged as a `role='parent'`
row — so filtering `role == 'parent' and main_axis` recovers `typed_gapfill` exactly —
and the cards the cascade-baseline snapshot resolves into sub-cells gain extra
`role='cell'` rows.

Cells come from `scripts/output/cascade-baseline/aoi-snapshot-v1/<tid>.json`
(`dd_top_cell` / `organic_cell` / `dd_right_cell` arrays) via
`probe_cellsplit_features.load_aois(tid, midpoint_split=True)`. The X-axis
midpoint-split mirrors AllSERP's Phase-D Y-midpoint split for adjacent organics:
a horizontal carousel's cell X-ranges are expanded to cover inter-card gaps so a
click in a card margin attributes to the nearest cell rather than being lost.

## Three tiers (by maturity — document them honestly)

| tier | etype | coverage | alignment to backbone | status |
|---|---|---|---|---|
| **1 — headline** | `dd_top_cell` | 6,373 cells / 1,550 trials (55.8 %); modal 4 cells/carousel (range 2–6) | **100 %** aligned to block-level `dd_top` bboxes | ship as primary |
| 2 — sparse | `organic_cell` | 174 aligned cells / 75 trials (2.7 %) | **45.8 %** of 380 cascade candidates align to a public organic | least-mature; ship aligned subset only |
| 3 — covariate | `dd_right` (+`dd_right_cell`) | 861 right-rail blocks (31.0 %); 184 cells / 92 trials | off-axis (`main_axis=False`) | covariate, not a modeling target |

Tier 2 caveat: the cascade's organic sub-segmentation is preliminary and its X
midpoint-split is deferred. We emit only the sub-cells whose center falls inside a
public `typed_gapfill` organic card (45.8 %); the rest sit on widgets/gaps and are
dropped rather than mislabeled as organic subdivisions.

## dd_right is a variance-reduction covariate, not a modeling target

The right rail (`dd_right`) is **off-axis** — `typed_gapfill` drops it. The cell-split
flavor re-introduces it (parent block for every right-rail trial, plus cells where
resolved) with `main_axis = False`. The presumption: **most use cases will not model
the right rail**, but right-rail exposure is a nuisance variable, and consumers should
be able to *condition on it to reduce variance* in main-axis models. Filter
`main_axis = True` to exclude it from attention/click analyses; join the `dd_right`
rows per trial (`has_dd_right`, right-rail dwell) when you want the covariate. Shipping
it as a control is the affirmative reason it is in the release — not an apology for a
sparse tier.

## Schema (six columns added to the typed schema)

`role` (`parent`|`cell`) · `cell_index` (0-based within parent; null for parents) ·
`n_cells` (cells in this parent; 0 = not subdivided) · `parent_rank` (the parent
card's display rank; −1 for off-axis) · `parent_etype` · `main_axis` (bool).

Cell rows inherit the parent's display `rank` (they share the SERP slot); `left_x` /
`right_x` carry the cell's (midpoint-split) X-range — the meaningful subdivision —
and `top_y` / `bottom_y` the cell's Y-range. Cell etypes are `dd_top_cell` /
`organic_cell` / `dd_right_cell`, so `n_by_etype` in the summary reports the coverage
breakdown directly.

## Regenerate

```sh
.venv/bin/python scripts/export_aois_by_trial_id.py --attribution typed_gapfill_cellsplit
.venv/bin/python scripts/cellsplit_click_composition.py    # within-carousel descriptive
```

Regime tag: `[LAB, AdSERP, typed_gapfill_cellsplit]`.
