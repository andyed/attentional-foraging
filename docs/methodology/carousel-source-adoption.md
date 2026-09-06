# Versioned carousel-source adoption contract

Integration audit, 2026-09-04. This records the remaining steps from the
[full-corpus candidate validation](carousel-full-corpus-validation.md) to
source adoption and cell-dependent analysis.

## Existing paths that must remain distinguishable

| Consumer | Actual source and integration consequence |
|---|---|
| `scripts/build_aois.py:100-123` | Rebuilds organic boxes, gapfill and typed maps, then exports. Even `--trial` only limits the initial CV step; later steps are corpus-wide. A cell-only adoption must not trigger those parent rebuilds. |
| `scripts/export_aois_by_trial_id.py:289-355` | Current gapfill parent rows plus cells/right-rail parents from `probe_cellsplit_features.load_aois`. Missing snapshot silently returns unsubdivided base. Main cells attach to the first Y-containing parent; unmatched cells silently disappear. |
| `scripts/probe_cellsplit_features.py:36,85-140` | Hardcoded `cascade-baseline/aoi-snapshot-v1`; groups all cells of a kind and expands them against the first parent. Does not apply typed exclusions. Changing this global source silently changes direct analysis callers. |
| NB23, cell 17 | Reads `scripts/output/nb23_cellsplit_rank/summary.json`, without source/hash validation. `compute_nb23_cellsplit_rank.py` calls the snapshot loader directly, not the export. |
| NB25 composition, cell 12 | Reads `scripts/output/nb25_cellsplit_composition/summary.json`, without source/hash validation. Its producer also calls the snapshot loader and separately reads old organic/native parent boxes from the same snapshot. |

The separate `25_lexical_novelty_dwell.ipynb` has no cellsplit consumer. Notebook
numbers alone are not unique names in this directory.

## Required source contract

1. **Immutable version and explicit selection.** Add one explicit cell-source
   selector/manifest through the build/export path and the two direct producers.
   Retain the frozen source under its original identifier; no implicit fallback
   from rejected/missing new cells to old cells. Versioned outputs must not share
   the existing summary/cache filenames until deliberately adopted.
2. **Pinned current parent baseline.** Preserve every current parent base-schema
   field, rank, type, identity and geometry under the chosen `typed` or
   `typed_gapfill` flavor. Candidate CSV parents are currently **tight typed**,
   whereas the release flavor is **typed_gapfill**. Join explicitly by the pinned
   typed parent identity/position and verify compatibility with the gapfill map;
   do not reassign by first Y overlap. Cell counts are added annotations, not
   permission to change a parent rectangle or to rebuild the CV/typing pipeline.
3. **Declare scope per source.** This candidate repairs top/main product cells.
   It does not validate organic subcells or right-rail cells. A top-only version
   is simplest. Retaining other frozen subcell classes requires explicit
   per-class lineage; it must not imply all cells share the new extraction.
   Right-rail parent covariates can remain at their independently pinned grain.
4. **Measured geometry stays measured.** Store raw DOM, clipped DOM and registered
   screenshot rectangles separately. No midpoint expansion or absorption of
   unseen edge space in the measured source. Optional gap-attribution regions
   are a separately named derived policy, built per identified parent.
5. **Identity and numbering.** Preserve DOM handle, product-link card ID,
   source order and visible order with `(trial_id, parent_identity, card_id)` as
   the key. Candidate visible indices are zero-based; NB23 `position` is
   one-based and its output loop starts at 1. Adapt explicitly rather than
   dropping cell zero. Contiguous indices do not prove semantic identity.
6. **Exclusion at admission.** Record all trial diagnostics, but gate analytical
   export before appending any role/type. Preserve the current 12-ID list and
   hash it. `load_typed_aois` and `load_typed_gapfill_aois` already apply the same
   list (`data_loader.py:907-934,1045-1054`); direct JSON readers do not.
7. **Provenance binds bytes.** Manifest: source version/schema, exact corpus IDs,
   hashes of extractor/registration/fixture/HTML/screenshot/metadata/typed inputs,
   exclusion hash, browser/library versions, viewport, coordinate model, thresholds,
   registration/visibility policy and status counts. Bind each CSV/JSONL/Parquet
   to its hash; a release label on an unrelated summary is insufficient.

The frozen cellsplit CSV is already stale at parent grain: versus the current
gapfill CSV, 10,754 common `(trial_id,rank)` rows differ on type, geometry or
HTML handle across 1,565 trials, with 878 legacy-only and 111 current-only keys.
Thus parent preservation must be checked against a **pinned current parent
baseline**, not claimed against the frozen cellsplit file. Exact hashes and
examples are in [the retained reproductions](../evidence/carousel-2026-09-04/corpus/integration-reproductions.json).

## Whole-corpus denominator requirements

- Canonical mouse inventory: **2,776 trials**. Current raw typed maps contain
  **1,582 top parents in 1,582 trials**; seven of those are alignment-excluded,
  leaving **1,575 eligible top trials**. No multiple-top trials or noncontiguous
  main positions were found in this current map inventory. Still retain the
  parent grain and reject ambiguity rather than assuming this never changes.
- Keep separate: all requested, true no-top, excluded, missing/unreadable input,
  unsupported/ambiguous DOM, registration rejected, and analytically admitted.
  A no-top trial is not a failed registration and is not a successful product
  extraction. A zero/missing cell export cannot remove a positive parent from
  the coverage denominator. Separate count agreement, boundary support and
  reviewed identity; none substitutes for another.
- An empty admitted-cell CSV alone cannot describe coverage. Emit a per-trial /
  per-parent status ledger, including known parents with no extracted DOM parent.
  Existing `write_candidate_csv` only emits parents it can bind, so the JSON
  ledger and fixed inventory must remain authoritative for missing cases.
- Resume only when trial-input and producer hashes match. Duplicate trial/parent
  keys, mixed producer versions and incomplete records must be rejected. Bound
  external-volume reads as well as browser waits; a filesystem `is_file` sweep
  stalled on the mounted screenshot path during this audit.
- Summarize coverage/failures by participant, cell count, clipping fraction,
  spelling block and layout class. Full-corpus coverage is not unbiased
  accuracy if only the supported border template is admitted.

## Proven integration failures to fix before analysis adoption

**Excluded off-axis rows — exporter guard repaired in this update.** The frozen CSV contains all 12
excluded IDs (213 rows). A rerun with the current exporter drops main-axis rows
but still emits `dd_right` parents for excluded `p018-b3-t1`, `p021-b1-t3`, and
`p049-b4-t3`: `base=[]` does not stop `rows_typed_cellsplit` at lines 289-355.
A synthetic empty-base reproduction confirmed this branch. The exporter now
calls the canonical `typed_alignment_exclusions()` before reading either source.
Three isolated regression tests cover exclusion, eligible right-only trials,
and unchanged parent fields. The frozen CSV itself has not been regenerated.

**NB23 needs an explicit protocol/source update.** Its current sequence inventory
contains 1,572 unique IDs, not the 1,581 in comments, and excludes the current
12-ID list. That inventory is a historical selection, not the new corpus
denominator (`compute_nb23_cellsplit_rank.py:59-97`). CTR denominators count
trials with cells before checking click availability; fixation means have a
separate denominator. Keep both explicit. `position=0` would disappear from the
reported rows (`:139-143,188-191`). Missing cells and missing snapshots require
separate status counts rather than bare `continue` (`:129-135`).

**Coordinates and click policy remain separate changes.** NB23 `:84` and NB25
`:197` request the default document-space clicks and compare them to screenshot
boxes. NB23 fixations already use screenshot coordinates. Correct conversion
must be explicit and validated; the new DOM window-width X mapping does not
by itself validate a change to evtrack coordinate conversion. Keep the historic
first-click target policy separate from M4's final-click policy.

**NB25 is not a current-parent cellsplit analysis.** It independently reloads
old organic/native boxes (`compute_nb25_cellsplit_composition.py:104-123`) and
includes right-rail parents as absolute slots (`:78-79`). Its nearest-Y fallback
ignores X (`:148-157`): a synthetic click at x=999 is assigned to a cell spanning
x=20..130 when Y overlaps. With missing cells, the standard view retains a
top parent but the cellsplit view can remove it. Rank percentages normalize
separately over assigned clicks (`:254-280`), masking differential attrition.
Choose a main-axis policy and matched trial/click denominators before reusing
the two-peak interpretation.

After the source is adopted and those protocols are resolved, execute only the
affected producers/notebook sections, add new stable K IDs, retire old rows with
their source date, regenerate HTML and the key-claim aggregate, and update
AllSERP per-cell claims. Preserve historical IDs and outputs. This corpus audit
does not itself refresh NB23/NB25 or M4 results.
