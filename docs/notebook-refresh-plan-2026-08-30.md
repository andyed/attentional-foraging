# Notebook refresh plan — 2026-08-30 (phase 04 remainder + phase 05 propagation)

Companion to [`realignment-consumer-plan-2026-08-30.md`](realignment-consumer-plan-2026-08-30.md)
(phases 01–03 complete) and [`local-pack-aoi-shift.md`](local-pack-aoi-shift.md). This document is
the ordered worklist for the notebook tier (phase 04) and the exact claims-surface edits (phase 05),
for both **attentional-foraging** and **approach-retreat**.

**Substrate state this plan is written against.** The aoi-card-collision fix merged today at 16:28
(`574218b6`; producer fix `86f800a3`, regen `2da0544d`) and both typed map flavors were regenerated —
**454 maps changed in each of `data/aoi-typed/` and `data/aoi-typed-gapfill/`, on top of the
2026-08-28 y-DP realignment**. The alignment-exclusion list changed membership: **14 → 12 tids**
(removed `p034-b6-t5`, `p041-b1-t9`, `p046-b6-t5`; added `p018-b3-t1`). Background jobs are
regenerating the typed-flavor `AdSERP/data` / `scripts/output` artifacts as this is written
(mtimes 16:31–16:36 and counting). **Rule: before re-executing any notebook, verify every typed
input it reads has an mtime after 2026-08-30 12:00 local.** The freshness table below is a
snapshot at 16:38; re-stat before acting.

---

## 0 · Input freshness snapshot (2026-08-30 16:38)

Fresh = regenerated on the collision-fixed maps (post-16:28 merge). Stale = still carries
pre-collision-fix content (usually the 2026-08-28 y-DP-only state).

| artifact | mtime | state |
|---|---|---|
| `data/aoi-typed/`, `data/aoi-typed-gapfill/` (the maps + exclusion list) | merged 16:28 | **FINAL** |
| `AdSERP/data/butterworth-lfhf-by-position-typed.json` | 16:32 | fresh |
| `AdSERP/data/ripa2-by-position-typed.json` | 16:32 | fresh |
| `AdSERP/data/k-coefficient-by-position-typed.json` (+ `scripts/output/k_coefficient/summary_typed.json`) | 16:32 | fresh |
| `AdSERP/data/saccade-orientation-by-{position,trial}-typed.json` | 16:32 | fresh |
| `AdSERP/data/retreat-arcs-typed.json` | 16:32 | fresh |
| `scripts/output/adserp_aois_by_trial_id_typed{,_gapfill}.{jsonl,csv}` + summaries | 16:32 | fresh |
| `scripts/output/serp_layout_diversity/summary.json` | 16:32 | fresh (2,764 trials, 12 excluded) |
| `scripts/output/dd_top_markov/*` | 16:32 | fresh |
| `AdSERP/data/cursor-approach-features-typed.json`, `-typed-gapfill.json` | 16:36 | fresh |
| `AdSERP/data/cursor-approach-features-typed-buf500.json`, `-gapfill-buf500.json` | Aug 28 05:54 | **STALE — waiting on regen** |
| `AdSERP/data/adsight-noticed-features-typed-gapfill.json` | Aug 28 05:56 | **STALE — waiting on regen** |
| `scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed{,_gapfill}.json` | Aug 28 06:56 | **STALE** (producer re-run needed; not observed in today's batch) |
| `scripts/output/adsight_noticed_replication/summary.json` | May 24 | STALE (behind adsight regen) |
| `scripts/output/k_phase_trajectory/summary.json` | May 24 | STALE |
| `scripts/output/ltr_typed_*/summary.json` (all variants) | May 5 / May 24 | STALE (feeds NB26 K27–K29) |
| `scripts/output/nb23_cellsplit_rank/*` | May 31 | STALE (cellsplit lineage, see §5) |
| `scripts/output/adserp_aois_by_trial_id_typed_gapfill_cellsplit.*` | Jun 23 | STALE, unmarked (see §5) |

The 2026-08-30 morning NB14/NB18 executions (08:19/08:23) predate the 16:28 collision-fix merge —
**both are stale again** and are back on the worklist (§2).

---

## 1 · DONE this session — NB33 / NB34 / NB35 gated and re-executed (phase 03 remainder + phase 04)

The three raw-glob notebooks now route AOI loading through `data_loader`'s gated surface
(`load_typed_gapfill_aois()` for per-trial reads; glob/trial lists filtered against
`typed_alignment_exclusions()`), copying the `scripts/serp_layout_diversity.py` /
`compute_cursor_approach_features.py:468` pattern. All three re-executed headlessly
(`.venv/bin/jupyter nbconvert --to notebook --execute --inplace`, the convention used for the
2026-05 cascade re-runs per CHANGELOG). Corpus: 2,776 → **2,764 trials (12 excluded)**. Inputs
(fixation-coords + the final collision-fixed `data/aoi-typed-gapfill/` maps) needed no waiting.

Headline movement (gate + collision-fixed maps combined; all three notebooks' conclusions stand):

- **NB33** (`33_intra_patch_reading.ipynb`): K1 2,776 → 2,764; K2 pairs 126,514 → 126,691;
  K3 organic leftward fraction unchanged at 40.2%; K4b height gate still passes
  (ρ +0.108 → +0.104, p = 2.1e-13); K4 snippet_chars still FAILS at the notebook's α = 0.01
  (ρ +0.022 → +0.029, p now 0.048 — worth watching, it crossed 0.05); K5 first-pass vs re-entry
  42.4% vs 39.3% (p = 1.4e-04). Type census shifted visibly for the collision-fix types
  (image_pack, paa, top_places, chrome, other_widget) — expected, those are the relabeled cards.
- **NB34** (`34_regression_load_coupling.ipynb`): events 46,610 → 46,514; all nulls hold
  (K6 two-mechanism dissociation still ABSENT; K2 intra ρ −0.026 ns, K3 inter ρ +0.033 ns).
  Note: the *pooled* inter_rate × LHIPA correlation moved from ns to ρ = +0.070, p = 2.4e-03 —
  the within-participant version (the K-row) stays ns; do not promote the pooled value.
- **NB35** (`35_pai_census.ipynb`): fixations 234,339 → 233,209; unary-discarded 22.8% → 22.7%;
  K3 peripheral ad mass 0.484; K5 soft-weighted leftward 42.2% (hard 40.2%); conclusions unchanged.

These notebooks carry **"Key Claims candidates"** code cells, not authoritative Key Claims markdown
blocks, and are not in `update_key_claims.py`'s `NOTEBOOK_LABELS` — per current convention there is
no aggregate entry to update. When they're promoted to Tier-A, transcribe from the 2026-08-30
executed output.

## 2 · DONE this session — NB23 re-executed, Key Claims rebuilt

`23_rank_effects.ipynb` inputs: `butterworth-lfhf-by-position-typed.json` (fresh 16:32),
`data/aoi-typed` maps via gated `data_loader` (final), LHIPA (static), plus the **stale**
`nb23_cellsplit_rank/summary.json` (see §5 — the K-cellsplit rows are annotated
`[typed_gapfill-cellsplit, pending]` rather than blocking the run). Executed clean; what moved:

| quantity | pre (2026-05-04 run) | post (2026-08-30) |
|---|---|---|
| trials with Butterworth (typed join) | 2,719 | **2,707** |
| Butterworth LF/HF × position ρ (0–10) | −0.673, p = 0.023 | **−0.809, p = 0.0026** |
| LHIPA × click position ρ (0–10) | −0.873, p = 0.0005 | **−0.791, p = 0.0037** |
| LHIPA × click position ρ (0–8, boundary excl.) | −0.783, p = 0.013 | **−0.617, p = 0.077 (ns — significance lost)** |
| click share / fixation / dwell monotonicity | −0.973 / −1.000 / −1.000 | unchanged |

The Key Claims cell's typed-cascade table — which had carried a botched stdout scrape since
2026-05-04 (one value read `*(see executed cell output)*`, one was a captured printout fragment) —
is replaced with transcribed values, and the aggregate regenerated via
`notebooks-v2/update_key_claims.py`.

Decomposition note: NB18's morning run put the y-DP-realignment-only LF/HF gradient at −0.882, so
the collision fix itself moved it −0.882 → −0.809 (still stronger than the pre-realignment −0.673).

## 3 · NB14 / NB18 — third pass (collision-fix re-run) — **execute next; inputs fresh**

Both were re-executed this morning (08:19/08:23) on the 2026-08-28 y-DP artifacts and are stale
w.r.t. the 16:32 regen. Inputs (`butterworth-lfhf-by-position-typed.json`,
`ripa2-by-position-typed.json`, legacy absolute robustness files) are all fresh/static — nothing
to wait on. Expected movement: NB18:K5 −0.882 → ≈−0.809 (NB23's computation of the same join);
K1/K2 trial counts move with the 12-tid list; K3/K4 were realignment-invariant and should barely
move. After execution, update both Key Claims blocks ("typed (current)" columns + the
2026-08-30 header note gains "aoi card-collision fix" wording) and re-run `update_key_claims.py`.
**Status: DONE this session — see the addendum at the bottom for results.**

## 4 · NB15 — **BLOCKED on a producer conflict, do not execute yet**

`15_cursor_approach.ipynb` reads `butterworth-lfhf-by-position-typed.json` (fresh) — but its
**cell 25 writes `AdSERP/data/cursor-approach-features-typed.json`**, the same artifact
`scripts/compute_cursor_approach_features.py --attribution typed` regenerated at 16:36 under the
coordinating session's batch. Two producers, one filename (the notebook is the historical producer;
the script is the phase-01/03 gated one; `scripts/add_etype_to_features.py` is a third writer of
the same path). Executing NB15 now would clobber the freshly regenerated, exclusion-gated artifact
with notebook-derived records of unverified parity.

Resolve before executing, in one of two ways:
1. **Point cell 25 elsewhere** (e.g. a `scripts/output/nb15/` scratch path) and declare the script
   the sole producer — preferred, matches the phase-08 provenance direction; or
2. Verify NB15's records are byte-identical to the script's output on the new substrate and retire
   one producer explicitly.

Also confirm which upstream (`data_loader` typed helpers — gated, fine) NB15's feature loop uses
before trusting a re-run. Queue: after the producer decision.

## 5 · Ordered worklist — everything else reading a typed-flavor artifact

Grep-verified inventory (code cells only). Order respects the dependency chain.

| # | item | typed inputs | state / gate |
|---|---|---|---|
| 1 | **NB14, NB18** third pass | butterworth-typed, ripa2-typed | §3 — inputs fresh, execute now |
| 2 | **NB20** (`20_approach_by_element`) | `cursor-approach-features-typed.json` | input fresh 16:36 — executable now; its header warns the feature file lacks `entry_t`; re-check that warning against the regenerated file |
| 3 | **NB22** (`22_four_class_taxonomy`) | `cursor-approach-features-typed.json` | input fresh 16:36 — executable now. Taxonomy producer: downstream `regression_labels` consumers (AR M5, LTR) re-derive after it |
| 4 | `approach_threshold_sensitivity` producer re-run → `regression_labels_cache_typed{,_gapfill}.json` | cursor-approach-typed (fresh) | STALE cache (Aug 28 06:56), not in today's observed batch — run producer, then #5 |
| 5 | **NB28** (`28_viewport_bands`), **NB30** (`30_scroll_trajectory`) | cursor-approach-typed + `regression_labels_cache_typed.json` | blocked on #4 |
| 6 | `ltr_typed_*` producer re-runs (`ltr_typed_four_class.py`, `ltr_typed_lfhf_feature.py`, `ltr_typed_lfhf_pairwise.py`, `ltr_typed_5class_confidence.py`, `ltr_typed_four_distinct_grades.py`, cellsplit/canonical-buf500 variants) | `cursor-approach-features-typed.json` (fresh); buf500 variants **wait on the buf500 regen** (still Aug 28) | run plain variants now, buf500 variants when their input lands → refreshes the May-05/May-24 `ltr_typed_*` summaries feeding NB26 K27–K29 |
| 7 | **NB26** (`26_ltr_graded_relevance`) | quotes `ltr_typed_*` summaries in its Key Claims (its own code reads only `regression_labels_cache.json`, unflavored) | blocked on #6; then transcribe K27–K29 with re-derivation annotations |
| 8 | **NB31** (`31_adsight_replication`) | `adsight_noticed_replication/summary.json` ← `adsight-noticed-features-typed-gapfill.json` | blocked on the adsight regen (still Aug 28 05:56), then its producer, then the notebook |
| 9 | **NB32** (`32_k_coefficient`) | `scripts/output/k_coefficient/summary.json` (unflavored, May 24!) + `k_phase_trajectory/summary.json` (May 24); `summary_typed.json` is fresh 16:32 | re-run `k_phase_trajectory` producer; check whether NB32 should read `summary_typed.json` — its Key Claims typed section is one of the scrape-defect sites (§6) |
| 10 | **cellsplit lineage** | `adserp_aois_by_trial_id_typed_gapfill_cellsplit.*` (Jun 23, pre-realignment, **no stale-mark, no realignment doc mentions it**), `nb23_cellsplit_rank` (May 31), `cursor-approach-features-organic-hybrid-cellsplit-buf500.json` (May 16), `m4_cellsplit_loso`, `ltr_*_cellsplit` | decide: re-derive the cellsplit export on the collision-fixed maps (producer: `export_aois_by_trial_id.py --cellsplit` or sibling — verify), stale-mark the Jun-23 files first (untracked, git can't restore), then `compute_nb23_cellsplit_rank.py`, then NB23's K-cellsplit rows lose their `pending` tag. Until then every K-cellsplit-* row and NB25's cellsplit cell stay `[typed_gapfill-cellsplit, pending]` |
| 11 | **NB25** (`25_serp_composition`) | `nb25_cellsplit_composition/summary.json` | same cellsplit gate as #10 |
| 12 | **`ltr_typed_*` summaries** (the standing May-05 K27–K29 values) | — | covered by #6/#7; listed separately because the realignment plan calls them out as unmarked-stale: stale-mark them if #6 doesn't run promptly |

Notebooks that read **no** typed-flavor artifact (verified by grep of code cells): NB04, NB06, NB08,
NB09, NB11, NB11.5, NB12, NB13, NB16, NB17, NB21 (organic_hybrid — explicitly unmoved), NB24
(loader-only reads; its `retreat-arcs` input is the *organic* flavor via DATA_DIR), NB29. No action.

## 6 · Pre-existing stdout-scrape defect sweep (plan only — do not mix into refresh commits)

The 2026-05-04 cascade edit that added "typed cascade" tables to Key Claims blocks pasted raw
captured stdout as claim values in several notebooks. NB18's instance was removed 2026-08-30
(morning); NB23's was removed today (§2). Verified remaining sites (grep of Key Claims markdown
cells for multi-line backtick fragments and `*(see executed cell output)*` placeholders):

- **NB24** `24_retreat_arc_geometry` cell 1 — ×2: "Top-Ad lateral/arc ratio" and "Organic vs Top-Ad
  MW p-value" both carry multi-line table fragments.
- **NB28** `28_viewport_bands` cell 21 — ×2: "Combined retreat + bands LOSO AUC" and "Bands-alone
  LOSO AUC" carry stdout fragments (the real numbers are visible inside the fragments: 0.830 / 0.765).
- **NB30** `30_scroll_trajectory` cell 1 — ×2: "Forward-selection minimal AUC" =
  `*(see executed cell output)*`; "n_reversals deferred vs eval-rejected" duplicate row carries a
  progress-log fragment.
- **NB32** `32_k_coefficient` cell 1 — ×2: "K clicked vs non-clicked" fragment; "K × LF/HF position
  correlation" = `*(see executed cell output)*`.
- **NB15** `15_cursor_approach` — ×2 placeholders: "Click prediction LOSO AUC (M3 full)" and
  "M4 approach-only LOSO AUC" (visible in the aggregate at lines ~389–390).
- **NB04** `04_fixation_coverage` — ×1 placeholder: "TTI calibrator (first 5 → remaining)".

(The realignment plan's list said "NB08, NB24 ×2, NB28 ×2, NB30, NB32". **NB08 has no Key Claims
cell at all** — that entry appears to have been a miscount; the placeholders it anticipated live in
NB04 and NB15. Treat this section's grep-verified list as the sweep's scope.)

Sweep protocol (one commit, `docs(claims): remove stdout-scrape fragments from Key Claims`):
for each site, either transcribe the real value from the notebook's *current executed* output
(only if that execution post-dates today's substrate) or replace with an explicit
`[typed, pending re-run]` marker. Never leave a fragment; never hand-invent a number. Re-run
`update_key_claims.py` once at the end. Most of these notebooks are on the §5 worklist anyway —
fold each fix into that notebook's refresh commit if the sweep lands second.

## 7 · Approach-retreat (AR) side

**Notebooks:** AR has one notebook, `analysis/attcur-validation/notebook.ipynb` — WILD/ACD,
single-AOI, `rank-type-N/A`, reads no AdSERP typed data. **No AR notebook re-execution needed.**

**Claims surfaces:**

- `docs/key-claims.md` — V1 (WILD), V2 (M5, organic flavor), V3 (viewport bands, organic flavor):
  **no typed-flavor rows; unmoved** by this realignment (matches the realignment plan's
  "explicitly not affected" table). One addition worth making while in there: a lineage note that
  the typed/typed_gapfill substrate was realigned 2026-08-28 and collision-fixed 2026-08-30, so
  any future typed-flavor row must post-date those. Also resolve the pre-existing three-way M5 AUC
  pin (0.794 / 0.769 / 0.709) the realignment plan flags.
- `docs/findings.md` §5 (line ~144) — quotes the typed_gapfill layout-diversity stats and **is now
  wrong twice**: "all 2,776 AdSERP trials" → **2,764** (12 alignment-excluded); "median of 6
  distinct element types (range 2–12)" → **median 7 (range 2–11)** per the fresh
  `serp_layout_diversity/summary.json` (16:32). "≈16 AOIs" and "100% carry a non-organic element"
  survive. Annotate `(re-derived 2026-08-30: collision-fixed y-DP typed maps, 12-tid exclusion)`.
- `docs/bbox-attribution-lineage.md`, `docs/research.md`, `README.md`, `CHANGELOG.md` — mention
  typed flavors descriptively; extend the lineage doc's flavor table with the 2026-08-28/08-30
  correctness passes (same names, values re-derived in place — cite
  `local-pack-aoi-shift.md` §Regeneration policy).
- **Replay/curation surfaces** (bundles, `.ias` exports, master CSV, PAI proof images) — owned by
  phases 06–07 of the realignment plan, not this document. One interaction to respect: when AR's
  exclusion mechanism lands (phase 06 "handle first"), it must consume the **12-tid** list —
  `p021-b1-t3` and `p023-b3-t7` (the two live on the replay site) are still on it.

## 8 · Phase 05 — exact edits to the AF claims surfaces

`docs/notebook-key-claims.md` is generated — edit the notebooks' Key Claims cells, then run
`notebooks-v2/update_key_claims.py`. `docs/findings.md` is hand-maintained prose.

### 8.1 `docs/notebook-key-claims.md` (via notebook Key Claims cells)

- **Done 2026-08-30 (morning + this session):** NB18, NB14 rebuilt from execution; NB23 rebuilt
  (§2). Remaining:
- **NB14/NB18 after the §3 third pass:** refresh the "typed (current)" columns; extend each block's
  attribution-history bullet: `2026-08-30 (afternoon) — aoi card-collision fix (574218b6) regenerated
  both map flavors (454 maps each) and shrank the exclusion list 14 → 12; re-executed.` Keep the
  mandated annotation format: every re-derived row carries
  `(re-derived 2026-08-28: y-DP aligned typed maps; 2026-08-30: aoi card-collision fix)` — rows
  re-derived only today may carry just the 08-30 clause with the 08-28 lineage implied by the block
  header.
- **Each §5 notebook as it lands:** same treatment — values from executed output only, annotation on
  changed rows, `pending` tags on rows whose producer hasn't re-run (the NB23 K-cellsplit precedent).
- **Aggregate header:** `update_key_claims.py` regenerates it; no manual edit.

### 8.2 `docs/findings.md`

Currently contains **no** `2026-08-28`, `y-DP`, or `realign` token — the annotation both
realignment docs mandate has reached neither canonical surface. Edits:

1. **Status header** (line 5): bump to v16, dated 2026-08-30: *"typed-AOI substrate realigned
   (2026-08-28 y-DP geometric alignment) and collision-fixed (2026-08-30, 454 maps/flavor,
   12-tid alignment-exclusion list). Typed-flavor narrative values below are being re-derived;
   rows not yet annotated `(re-derived 2026-08-28/30)` reflect the pre-realignment typed run or the
   organic_hybrid cascade primary."* Link both realignment docs.
2. **§3b-iv** (lines ~229–249): the quoted NB14:K3 gradient (ρ = −0.927, N = 2,719 trials) is the
   legacy absolute value; after the NB14 third pass, restate under typed current with the
   annotation, keeping the absolute value as explicit legacy comparison. Same for the K5/K7
   within-trial and LHIPA-convergence numbers if they moved.
3. **Any prose citing NB18:K5/K6:** the "null under both attributions" language was already
   corrected in the notebook (2026-08-30 morning); ensure findings.md doesn't still carry it
   (grep `RIPA2` — the §"will-return predictor scan" passage at line ~548 discusses the R1 RIPA2
   bbox collapse, which is organic-flavor and stands; no edit unless it cites K6).
4. **NB23-derived prose** (§0 ski jump, rank-effects passages): the boundary-excluded LHIPA ×
   click-position correlation lost significance today (−0.617, p = 0.077) — if any prose leans on
   the 0–8 variant, soften to the 0–10 result (−0.791, p = 0.0037) with the annotation.
5. Add one line to the v15 "per-section prose update pending" note pointing at this plan as the
   tracker.

### 8.3 `docs/local-pack-aoi-shift.md` corrections (from the realignment plan §05, updated by today)

1. **§Resolution figures are now two generations stale.** The doc quotes matched pairs 24,512 /
   `unknown_widget` 375 / residuals 2.0 px mean, 4.6 px p90 / **14** suspects. The realignment plan
   corrected this to the then-on-disk 24,698 / 984; after today's collision fix the on-disk
   `scripts/output/aoi-typed/build_typed_aoi_map_summary.json` reads **matched 25,054,
   unknown_widget 650, mean residual 1.95 px, p90 4.5 px, `n_alignment_suspect` 12**. Correct the
   doc against the *current* summary and note the intermediate values as superseded build states.
2. **"14 trials (0.5%) remain flagged"** (§Quality gate) → 12, with the membership change spelled
   out (−p034-b6-t5, −p041-b1-t9, −p046-b6-t5, +p018-b3-t1) and a pointer that the canonical list
   is the JSON, not the doc.
3. **§Regeneration state** — append the 2026-08-30 collision-fix pass: producer fix `86f800a3`,
   substrate regen `2da0544d`/`574218b6`, artifact regen 16:31–16:36, and the notebook-tier status
   from this plan (NB33/34/35/23 done; NB14/NB18 third pass; rest queued per §5).
4. The "still pending is the notebook tier" closing paragraph → point at this document.

## 9 · Standing rules for whoever picks this up

- Verify input mtimes (> 2026-08-30 12:00) immediately before each execution; the regen batch was
  still writing when this snapshot was taken.
- `.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1`
  from the repo root; never hack a failing notebook to pass — capture the error and record it here.
- Key Claims values come from executed output only; K-IDs never renumbered; annotations per §8.1.
- Commit only files you edit, explicit `git add <path>`, conventional commits, no `-q`, no push
  (and none 10:00–15:00 PT weekdays). The regenerated data artifacts belong to the coordinating
  session — leave them unstaged.
- Audit tools (`audit_local_pack_aois.py`, `verify_typed_aoi_map.py`,
  `validate_typed_aoi_migration.py`) stay ungated on purpose.

---

## Addendum — NB14/NB18 third-pass results (this session)

Both re-executed ~16:40–16:45 on the 16:32 collision-fixed inputs; Key Claims blocks updated from
executed output; aggregate regenerated. Every conclusion survives; magnitudes moved on the LF/HF
positional axis only:

**NB14** (`14_butterworth_cognitive_load.ipynb`):
- K1 2,706 → **2,707** trials; K2 5,650 → **5,647** segments.
- K3 full-range gradient **−0.882 → −0.809** (p = 3.3e-04 → 2.6e-03); K4 (positions 1–10)
  −0.842 → **−0.745** (p = 0.013).
- K9 steep-vs-plateau dichotomy holds (U = 3,667,489, p = 3.3e-18); K10 steep-phase ρ = −1.000
  holds; K11 plateau **−0.571 → −0.286** (still ns, still negative); K12 medians 23.9 / 16.8.
- K5 within-trial N 868 → 866 (mean ρ −0.185, median −0.500, 62.1% neg); K6 clicked-vs-non
  25.76 (1,378) vs 20.28 (4,096), p < 10⁻⁴; K7 LHIPA convergence −0.119 — all effectively
  invariant.
- The block's bottom "2026-05-04 typed cascade" table carried three more stdout-scrape fragments
  (same family as §6) — replaced with transcribed 2026-05-04 historical values.

**NB18** (`18_ripa2_vs_lfhf.ipynb`):
- K1 2,706 → **2,707**; K2 5,650 → **5,647**.
- K5 LF/HF × position **−0.882 → −0.809** (p = 2.6e-03) — matching NB23's independent computation
  of the same join, as predicted in §2.
- **K6 RIPA2 × position is collision-fix-invariant: −0.682, p = 0.021, to three decimals.** The
  2026-08-30-morning correction ("the organic-flavor null was flavor, not substrate") stands.
- K3/K4 discriminant-validity rows unmoved (−0.023 ns / −0.097, p = 2.5e-13). Quadrants: effortful
  click rate 28.9% → **29.1%** (joint lift HH−LL +9.9 → **+10.1 pp**); ordering HH > HL > LH > LL
  intact.

**Freshness updates since the §0 snapshot** (re-statted 16:50): `adsight-noticed-features-typed-gapfill.json`
landed 16:39 and both `cursor-approach-features-typed*-buf500.json` landed 16:41 — all three now
fresh, unblocking §5 #6 (buf500 LTR variants) and #8 (NB31's producer chain).
`regression_labels_cache_typed{,_gapfill}.json` remains the notable stale gate (Aug 28 06:56).
