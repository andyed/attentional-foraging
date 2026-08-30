# AllSERP v1.1.0 — consumer migration plan (drafted 2026-08-30)

> **Status: phases 01–03 complete (2026-08-30).** Every typed-flavor artifact in AF is now
> exclusion-clean (`excl=0` across all 11, plus both `.jsonl` exports). Phases 04–08 open.
> Two corrections to this plan, found by doing it, are marked **[CORRECTED]** below.

Propagating the typed-AOI geometric realignment into **attentional-foraging** and
**approach-retreat**. Companion to `docs/allserp-v1.1.0-migration.md` (which tells a
consumer *what* changed); this one is the ordered worklist and what an inventory of both
repos on 2026-08-30 actually found.

Substrate pinned at `allserp-v1.1.0` / `e340be52d7a6`, typed maps `sha256 bb08721ac61920c5`,
working tree clean.

---

## Scope check first: the 2026-08-28 batch is sound

Worth settling before planning anything, because it decides how big this is. The typed maps
carry mtimes of `08-28 08:35` — *after* every artifact derived from them at 05:53–08:01 —
which looks like the whole batch was built on non-final maps.

It wasn't:

- Re-deriving crforager's `human_targets.json` against today's definitively-final maps
  returns **byte-identical** values.
- Joining the sibling artifacts on `(position, etype)` gives **0 mismatches**:
  `retreat-arcs-typed` (1,960 trials), `adsight-noticed-features-typed-gapfill` (2,539),
  `cursor-approach-features-typed` (2,760).

The 08:35 rewrite was an idempotent re-run. **Nothing from 2026-08-28 needs redoing**, in AF
or crforager. Everything below is debt that pass did not cover.

---

## Two artifacts that are silently wrong

Both resolve by trial id and fail no check. Neither is stale-marked.

### BLOCKER — the `.jsonl` exports say v1.1.0 and contain v1.0.0

`scripts/output/adserp_aois_by_trial_id_typed.jsonl` and its `_gapfill` twin (12.4 MB each)
carry a post-realignment mtime of `08-28 06:56` and sit beside a summary that correctly reads
`1.1.0` — but their content is pre-realignment.

| field | stale CSV 06:45 | **the .jsonl 06:56** | current CSV 08:35 |
|---|---:|---:|---:|
| trials | 2,776 | **2,776** | 2,762 |
| `knowledge_panel` | 746 | **746** | 0 |
| `top_places` | 84 | **84** | 338 |
| `organic` | 22,354 | **22,354** | 21,910 |

**1,162 of 2,762 common trials (42.1%) have a different rank→etype sequence.** All 746 phantom
main-column knowledge panels and all 14 excluded trials are still present.

*Why this is the dangerous one:* the "check which release you have" recipe in
`docs/allserp-v1.1.0-migration.md` reads the **summary** JSON. A consumer on the `.jsonl` gets
a false all-clear from the repo's own migration guide.

### BLOCKER — `compute_saccade_orientation.py` leaks all 14 excluded trials

Its two typed outputs carry 2,774 trials where every sibling carries 2,759–2,760, and all 14
`alignment_suspect` trials are present. Root cause at lines 174–177: the typed branch sets
`tops = None` when `typed_aoi_tops()` returns empty — which *is* the exclusion signal — but
never `continue`s, so execution falls through to lines 202–212 and still writes the trial.

`compute_k_coefficient.py:162` handles the identical situation correctly with
`n_skipped += 1; continue`. Two producers, same idiom, diverging.

### DEFECT — an unflavored 2026-04-25 file joined into the typed run

The same script reads `ENC_PATH = AdSERP/data/encoding-vs-retrieval.json` as a module
constant. Its `pos` values were assigned under a pre-typed AOI definition. `resolve_paths()`
flavors the RIPA2 input and both outputs per attribution but leaves this one alone, so a
pre-typed rank space is joined into typed results. Trial ids resolve; the join is wrong.

**[CORRECTED — confirmed and fixed 2026-08-30.]** Mid-fix I briefly concluded this was dead
code, because the first `enc` reference (Test 1) loads it, loops with a bare `pass`, and then
overwrites `clicked_set` from the correctly-flavored `RIPA2_PATH`. Removing it broke Test 3,
which is the *real* consumer: it builds `wr_map[(tid, int(fix['pos']))]` from `enc` and joins
that against `by_pos[tid]['positions'][*]['pos']` — typed ranks under `--attribution typed`.
So the mis-join is real, and confirmed at the producer: `compute_encoding_vs_retrieval.py`
takes no `--attribution` and positions via `result_band_tops()`, i.e. **absolute** rank space,
with no flavored variant on disk.

Resolution: the dead Test-1 load is gone, and **Test 3 is now gated to
`--attribution absolute`**, recording a `skipped` reason in the summary rather than emitting a
number from two different rank definitions. A flavored `encoding-vs-retrieval` would be needed
to restore Test 3 under typed — that is new work, not a re-derivation.

---

## Phase order

AF first throughout — AR consumes it. **Everything here runs offline**: only
`full-page-screenshots` is on the unmounted volume, and none of this touches it.

### 01 · Fix the two AF producers, then re-run — *AF, ~20 min*

Add the `continue` so excluded trials are skipped, and flavor `ENC_PATH` inside
`resolve_paths()` the way RIPA2 already is. Stale-mark first — these artifacts are untracked,
so git cannot restore them.

```bash
cp AdSERP/data/saccade-orientation-by-position-typed.json \
   AdSERP/data/saccade-orientation-by-position-typed.stale-preAlignment-2026-08-30.json
.venv/bin/python scripts/compute_saccade_orientation.py --attribution typed
```

**DONE.** Both outputs went 2,774 → **2,760 trials, 14 excluded → 0**. The typed flavor is now
internally consistent: 2,760 / 2,759 / 2,706 / 2,706 across saccade-orientation, k-coefficient,
ripa2 and butterworth, where the remaining differences are legitimate coverage filters.

A third defect surfaced in the same file and is fixed: **`n_results` was unbound on the
`organic` and `organic_hybrid` branches** (assigned only under `typed` and the legacy `else`),
so `--attribution organic` would raise `UnboundLocalError` at the first trial with non-empty
tops. The May 2026 organic artifacts predate the typed branch, which is why this was never hit.

*Open question — now settled.* `saccade-orientation-by-trial-typed.json` was byte-identical to
`-organic` (md5 `a248198a…`). That was a **symptom of the leak**, not correct-by-construction:
with the same 2,774-trial set and an attribution-invariant per-trial aggregate, the flavors
could not differ. Post-fix the typed file has its own hash (`1103040c…`) because it now carries
the correct 2,760-trial set.

### 02 · Regenerate the `.jsonl` exports — *AF, ~10 min* — **DONE**

`scripts/export_aois_by_trial_id.py:444` is already exclusion-gated, so this was a straight
re-run; the artifacts were simply never regenerated. Both stale-marked first — they were the
only copies of the v1.0.0 export in that format.

Both flavors now agree **exactly** with their sibling CSV (same trial set, same etype counts),
2,762 trials, 0 excluded. The v1.0.0 signature is gone: `knowledge_panel` 746 → 0,
`top_places` 84 → 338, `organic` 22,354 → 21,910.

The migration guide's release check now reads **the export itself**. Verified both ways: it
reports `v1.1.0` on the regenerated file and `PRE-1.1.0 — re-derive` on the stale-marked copy.
It also documents a second tell that needs no exclusion list — v1.0.0 typed exports carry ~746
main-column `knowledge_panel` rows and ~84 `top_places`; v1.1.0 carries 0 and ~338.

### 03 · Gate the seven direct readers — *AF, ~30 min* — **scripts DONE, notebooks open**

These glob `data/aoi-typed-gapfill/` themselves and never see the exclusion list.
`compute_cursor_approach_features.py:468` is the working pattern to copy.

- **`serp_layout_diversity.py` — gated.** Filters the glob against
  `typed_alignment_exclusions()`; now reports `[exclusions] 14` and runs on 2,762 trials.
- **`cursor_arc_prevalence.py` — [CORRECTED] no gate needed.** It looked ungated (zero
  exclusion references) but takes its trial set from `cursor-approach-features-typed-gapfill.json`,
  which is already gated, and only ever indexes `AOI_DIR` by trial id — so it inherits the
  filter transitively. Documented in place rather than double-gated, with a note to add the
  explicit gate if the trial source is ever changed to a glob.
- **`dd_top_markov_extractor.py` — gated and de-shadowed.** Its local `load_typed_aois()` is
  renamed `_read_typed_gapfill_raw()`, since shadowing `data_loader`'s gated name is what made
  an ungated read look gated; the trial loop now filters `get_trial_ids()`.
- **Open:** `notebooks-v2/33_intra_patch_reading.ipynb`, `34_regression_load_coupling.ipynb`,
  `35_pai_census.ipynb` — fix their loading cells as part of phase 04, since they get
  re-executed there anyway.

Leave the audit tools ungated on purpose — `audit_local_pack_aois.py`,
`verify_typed_aoi_map.py`, `validate_typed_aoi_migration.py` need to see excluded trials. Worth
a one-line comment saying so, so a later sweep doesn't "fix" them.

### 04 · Re-execute the notebook tier — *AF, half day* — **NB18 + NB14 DONE**

The script tier is done; no notebook had been re-executed since the realignment.

**A defect in both notebooks run so far, unrelated to the realignment and larger than it.**
The 2026-05-04 typed cascade edit replaced *every* load path with the typed file, including
the `_abs` robustness pair. So `bw_data_abs` held the same data as the primary and the
"Absolute" robustness column was a **self-comparison** — NB18's stored output literally read
`2719 / 2719 / 2719`. Both notebooks also kept printing and documenting "organic primary"
while loading typed. Robustness pairs restored to the genuine legacy absolute files in both;
re-executed; Key Claims rebuilt from executed output and the aggregate regenerated.

**NB18** (`2,706` typed vs `2,719` absolute). K3/K4 had stood as *(re-run pending)* since
2026-05-01 — now resolved (Pearson −0.023 ns; Spearman −0.097, p = 3.4e-13, significant but
negligible at n = 5,650, so the discriminant headline stands). Its Key Claims also carried a
**botched scrape**: three "typed" values were fragments of captured stdout rather than
numbers — one Spearman ρ whose value read ``RIPA2 (organic primary)\n2719 / 2719 in legacy
absolute-rank…``. Removed and superseded.

**NB14** — resolved its own long-pending K5 (`N = 868, mean ρ = −0.186, median −0.500,
62.1% neg`).

**Two headline claims reverse, and it is the flavor, not the realignment.** Isolated by
re-running against the stale-marked pre-realignment typed inputs:

| claim | organic (as documented) | typed (current) | realignment's own effect |
|---|---|---|---|
| NB18 K6 RIPA2 × position | −0.080, ns — *"null under both attributions"* | **−0.682, p = 0.021** | −0.855 → −0.682, significant either way |
| NB14 K10 steep-phase monotone | −0.800, ns — *"does not survive bbox attribution"* | **−1.000, p ≈ 0** | unchanged |
| NB14 K11 plateau sign | +0.321 (sign flip) | **−0.571**, ns | 0.000 → −0.571 |
| NB18 K3/K4 | *(never run)* | −0.023 / −0.097 | invariant (Δρ ≤ 0.001) |

So two "this doesn't survive attribution" notes were properties of the **organic** flavor and
are false under typed. Both notes are corrected in place.

**Remaining:** NB23, NB26, NB15 read changed typed artifacts and still need re-running.
NB33, NB34, NB35 read no changed *artifact* but raw-glob `data/aoi-typed-gapfill/` ungated —
they need the phase-03 gate before re-execution, which will drop 14 trials from each.

**Also found, not fixed (separate hygiene):** the same scrape defect left multi-line stdout
fragments as claim values in NB08, NB24 (×2), NB28 (×2), NB30, NB32. Pre-existing, unrelated
to attribution — worth a sweep of its own.

Also pre-realignment and unmarked: the `ltr_typed_*` summaries (2026-05-05) feeding K27–K29,
and `adserp_aois_by_trial_id_typed_gapfill_cellsplit.*` (2026-06-23), which no realignment doc
mentions at all.

### 05 · Propagate into the claims surfaces — *AF, ~1 hour*

The realignment is documented thoroughly in four places and has reached neither canonical
surface. `docs/notebook-key-claims.md` is dated Jun 3; `docs/findings.md` Jul 25. Neither
contains `2026-08-28`, `y-DP`, or `realign`, and the
`(re-derived 2026-08-28: y-DP aligned typed maps)` annotation that both realignment docs
*mandate* appears in neither.

Two corrections while in there:

- `local-pack-aoi-shift.md` §Resolution quotes matched pairs 24,512 / `unknown_widget` 375,
  but the on-disk `build_typed_aoi_map_summary.json` says 24,698 / 984. The residuals (2.01 px
  mean, 4.6 px p90) and suspect count (14) *do* match, so the on-disk build is final and those
  Resolution figures describe a superseded intermediate. Live trap for anyone quoting the doc.
- The same doc's "Regeneration state" still lists NB14/NB18 as pending; both ran on 08-28.

### 06 · Rebuild AR's typed surface — *AR, half day*

Nothing in AR has been rebuilt since the realignment. Of 141 curated replay bundles, **90
differ** from AF's current map — and of the 80 built May 24, whose only upstream delta *is* the
realignment, **38 differ**. Labels move, not just geometry: `knowledge_panel` appears to have
been reclassified or dropped wholesale.

Rebuild in order: `build_replay_trial.py` → `build_replay_pages.py` →
`emit_master_labeled_csv.py` → `export_ias.py`. The `.ias` exports and PAI proof images
(Aug 12) read the May bundles, not AF, so they inherit staleness without looking stale.

**Handle first:** `p021-b1-t3` and `p023-b3-t7` are on AF's exclusion list and are *live on the
published replay site* with AOI overlays. AF cannot rule out a one-slot-wrong lattice on
either. AR has no exclusion mechanism at all — add one, and decide whether to pull the two
pages or badge them.

### 07 · Join on `html_handle`, not position — *AR, ~2 hours*

`build_replay_trial.py:461` gates typed widgets on `c.get("position", -1) >= 0` — a positional
test on the exact field the realignment moved. A card that shifts a slot is silently added or
dropped.

The fix is already in the data: bundles carry a stable handle (`rso[2]`, `botstuff.nav[0]`)
faithfully copied from AF and never joined on. Switch the join to it.

Two more in the same family:

- `emit_master_labeled_csv.py:80` intersects two independently-computed rank spaces as bare
  integers (`regression_labels[r['_idx']] = r['position'] in regressed`).
- `aoi_corrections.json` + `apply_aoi_corrections()` renumbers surviving organics contiguously,
  so bundle `position` silently stops matching AF's for that trial. One entry today
  (`p048-b1-t6`), keyed on a bare integer with no bbox to re-verify against — the
  fixture-hides-a-bug shape.

### 08 · Stamp provenance so this is detectable next time — *both, ~2 hours*

Every problem above was invisible because no artifact records what it was built from. AF is the
publisher and should say so once, rather than four consumers each fingerprinting 2,776 files:
publish `data/aoi-typed/substrate.json` beside the exclusion list, carrying the release tag and
a content hash.

Consumers then pin that. crforager's `substrate_stamp()` is a working reference — note it keys
on **content, not mtime**, precisely because the 08:35 rewrite proved mtime lies (it reported
drift against a substrate that had not changed).

AR additionally needs the AOI flavor and AF commit in each bundle's `_meta`; today a May-4
bundle is indistinguishable from a May-24 one without checking mtimes.

---

## Explicitly not affected

Worth stating, because the natural assumption is that a 1,900-trial relabeling moves everything.

| surface | status | why |
|---|---|---|
| M4 / M1 headline `0.847` / `0.668` | **unmoved** | computed under `organic_hybrid`; no organic-flavor artifact was rebuilt (all still May–Jul) |
| M5 suite `AUC 0.769` | **unmoved** | `organic` flavor, same reason |
| AR library core (`src/approach-retreat.js`) | **unmoved** | pure geometry over AOI rects read from the host page's live DOM; AF maps are not an input |
| JS↔Python parity tests | **unmoved** | golden values are Python-reference outputs on synthetic trajectories |
| ACD / WILD validation suite | **unmoved** | single-AOI cohort, no rank structure; already tagged `rank-type-N/A` |
| `pupil-lfhf` | **code dep only** | self-contained loader over fixation/pupil CSVs, never typed AOIs. AF imports its `assign_fixation_to_position`, which takes `tops` as an argument and is flavor-agnostic. Its own artifacts are April, `absolute` flavor — a separate pre-cascade matter. Note its tree is currently dirty. |

**Pre-existing, not realignment debt:** three different M5 AUCs are pinned across AR — `0.794`
in the curation docs (unlabelled by rank-type), `0.769` in key-claims, `0.709` as the legacy
value. Worth resolving while that surface is open.

---

## Blocked on the dataset volume

Only `AdSERP/data/full-page-screenshots` lives on `/Volumes/andyed` (a broken symlink while
unmounted; 111 of 2,776 survive in `.local-cache.bak`). Fixation, pupil, mouse, boundary, and
cached-SERP data are all local — so **nothing in phases 01–08 is blocked**.

What is: **16 OCR-dependent scripts** (`scent_*`, `value_*`, `within_result_acuity`,
`span_anisotropy`, …) and crforager's `word_relevances.json`, the one artifact still carrying
pre-realignment content.

That one is now guarded rather than merely documented: its per-word profiles are positional per
organic, and in that code path `scent` *is* the environment's reward target, so a silent
mis-join would corrupt the reward rather than a reported number. `build_word_trial_bank` refuses
on a substrate-stamp mismatch. Re-derive when the drive is back — it is also a 600 → 2,762 trial
coverage expansion.

---

## The general rule this exposed

Two failure shapes, neither caught by a stamp on loader callers:

1. **Absolute upstream paths.** Four crforager producers and four AR producers read sibling-repo
   outputs by hardcoded absolute path, bypassing every loader and guard. In crforager this hid
   three-month-old inputs under the entire third axis. A migration sweep must grep for absolute
   paths, not just for loader callers.
2. **Positional joins.** An artifact keyed positionally to AOI order is unsafe across a
   realignment *even when its trial ids resolve*. Lookup success is not join validity.
