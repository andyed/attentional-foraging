# AllSERP v1.1.0 — migration guide

For anyone consuming the typed AOI enrichment. **Schema is unchanged;
values are corrected.** Identical code produces different numbers, so
re-derive rather than mixing v1.0.0-era artifacts with v1.1.0 maps.

## Check which release you have

```bash
python -c "import json;d=json.load(open('scripts/output/adserp_aois_by_trial_id_typed_gapfill_summary.json'));print(d.get('allserp_release','pre-1.1.0'), d.get('alignment_exclusions',{}).get('n'))"
```

`1.1.0 14` = current. A missing `allserp_release` key means the export
predates this release.

Every export summary now carries `allserp_release` and the full
`alignment_exclusions` block, so a bare CSV is identifiable.

## If you consume the CSV export

One file:

```
scripts/output/adserp_aois_by_trial_id_typed_gapfill.csv
```

(or `_typed.csv` for the non-gapfill flavor). Same columns, same
`trial_id` / `rank` / `etype` / `top_y` / `bottom_y` semantics, same
page-space coordinate convention.

| | v1.0.0 | v1.1.0 |
|---|---:|---:|
| rows | 37,174 | 36,370 |
| trials | 2,776 | 2,762 |
| `knowledge_panel` rows | 746 | **0** |
| `top_places` rows | 84 | **338** |
| `organic` rows | 22,354 | 21,917 |

**42.2% of retained trials have a corrected main-column etype sequence.**

## If you consume the per-trial JSON maps

`data/aoi-typed/<tid>.json` and `data/aoi-typed-gapfill/<tid>.json` are
rebuilt in place. Entries gain a `source` suffix recording how the card
was matched (`+y_dp`, `+merged_segment`, `+span_rescue`,
`html_rendered_offcolumn`).

If you load these through `notebooks-v2/data_loader.py`, the alignment
exclusions are applied for you — `load_typed_aois` and
`load_typed_gapfill_aois` return `[]` for excluded trials. If you read the
directory directly, apply
`data_loader.typed_alignment_exclusions()` yourself.

## Three substantive changes

1. **Local packs are typed.** Google Maps / local-results blocks render
   outside `#rso`, so Phase 1 never emitted a card for them while the CV
   extractor still bboxed the block — the bbox took the *next* card's
   label and pushed everything below it down one slot. 268 trials
   recovered; `top_places` 84 → 338.
2. **746 phantom main-column `knowledge_panel` rows removed.** These
   render at x≈804, width 369, height ~3,000 px on a 1,280 px page — the
   right rail — while the main column sits at x≈108. Screenshot-verified.
   They were occupying a main-column rank slot they never visually
   occupied, pushing every organic below them one rank deeper. They are
   now `position = -1` (off-axis) and do not appear in the main-axis
   export. Expect this category to be empty by construction.
3. **14 trials excluded.** Pages whose rank lattice cannot be verified
   geometrically (shift-periodic layouts where a one-rank-wrong lattice
   can't be ruled out). The list and the rule that produced it are in
   `data/aoi-typed/alignment-exclusions.json`, and are embedded in every
   export summary. Excluding them is deliberate: these are exactly the
   cases where silent inclusion would be the risk.

## What to re-derive

Anything computed from AOI ranks — depth/knee measures, per-position
aggregates, click attribution, four-class taxonomies. Rank *medians* over
thousands of trials proved robust (the LF/HF per-rank claims are unchanged
to three decimals), but per-trial click and depth quantities moved.

If you have your own DOM-correction layer on top of these boxes, note that
the local-pack cards carry an `Odp5De[0]` handle rather than an
`rso[...]` handle, so handle-based lookups will not resolve them — fall
back to the exported geometry, as you would for `native_ad` / `dd_top`.

## Provenance

- Root cause and fix: `docs/local-pack-aoi-shift.md`
- Downstream delta: `docs/typed-realignment-delta.md`
- Release notes: `CHANGELOG.md` (AllSERP enrichment v1.1.0)
