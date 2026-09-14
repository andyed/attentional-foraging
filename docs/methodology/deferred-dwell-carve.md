# Deferred-class carve, reduction baselines and rate curve on the cursor-only typed stream

**Status:** current as of 2026-09-13 (late); regime `[LAB, AdSERP, typed]`.
Canonical implementations: `scripts/deferred_dwell_carve.py`,
`scripts/reduction_baselines.py`, `scripts/rate_curve_canonical.py`,
`scripts/scroll_only_carve.py`, `scripts/scroll_kinematics.py`.
Outputs under `scripts/output/deferred_dwell_carve/` and
`scripts/output/reduction_baselines/` (ignored under the output policy;
promote deliberately). All read the canonical buf500 feature cache
`AdSERP/data/cursor-only-typed-features-mousedown.json`, hash-checked against
`scripts/output/m4_cursor_aoi_mousedown/summary.json`, and the typed
regression label cache `scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json`.

Three rules bind every producer on this page, and each was violated once on
2026-09-13 before being fixed the same day:

1. **One pool per table.** Every model in a table is scored on the same rows,
   and the permutation null is computed on those rows.
2. **The carve uses the label's own assignment.** Visit structure (first
   visit, return) is built with the fixation→AOI path that produced the label,
   and the producer asserts zero disagreement before reporting.
3. **The stamp describes what the run did.** Provenance carries every axis
   that changed the input (anchor, sampling mode, and thinning rate).

## 1. The rule, in one line

Split gaze dwell on a result into the first visit and everything after it;
score the deferred-vs-evaluated-rejected label with each half, with the cursor
vector, and with prior-work projections, all on the label-complete pool of
approached non-clicked results that were fixated at least once.

## 2. Why this rule

`total_dwell_ms`, the M2 gaze-dwell baseline, sums every fixation on a result
including the return fixations that define `deferred`
(`p in visited and p < max_seen`). A baseline that contains its own label
cannot be compared with a cursor vector that does not. `first_visit_dwell_ms`
is what a system holds at the moment it must predict a return. The same
carve applies to any time-windowed feature, which is why the scroll producers
truncate viewport residence at the same boundary.

The pool is label-complete (rows present in the label cache). The 663
approached non-click rows absent from it are **approached but never fixated**
(zero gaze visits; the producer asserts this). They are not examined, so they
are neither deferred nor evaluated-rejected; excluding them is a construct
boundary, not a data gap. The shipped §4.3 number counted them as rejected via
`.get(key, False)`, which is why M4-7 reads 0.691 there and 0.680 here. The
producer still reproduces the shipped number as its gate, so both are on disk
and the difference is documented.

## 3. Where this lives in code

| Claim | Implementation |
|---|---|
| Fixation→position assignment for visits and label | `data_loader.typed_aoi_tops` + `data_loader.assign_fixation_to_position`, called from `deferred_dwell_carve.visit_decomposition`; label from `compute_regression_labels.regressed_positions(tid, 'typed')` |
| Visit = maximal run of consecutive assigned fixations on one position | `deferred_dwell_carve.visit_decomposition` |
| Gate 1: reproduce shipped §4.3 deployable M4-7 on the shipped pool | `deferred_dwell_carve.main` (`out['gate']`, tolerance 5e-4) |
| Gate 2: in-script label rule == shipped label cache on every labeled pool row | `deferred_dwell_carve.main` (`out['label_agreement']`, zero tolerance) |
| Never-fixated assertion on the 663 excluded rows | `deferred_dwell_carve.main` (`population.never_fixated_with_gaze_visit`) |
| Same-rows blocks (`carve[rule]['pool']`, `carve[rule]['dwell_rows']`) | `deferred_dwell_carve.main` |
| LOSO logistic protocol, pooled + per-fold AUC | `m4_cursor_only_downstream.loso_proba`, `summarize` |
| Prior-work projections B1–B5 | `reduction_baselines.py` (`MODELS`, `globals_for`, `per_candidate`) |
| Within-trial AUC (same-trial pairs only) | `reduction_baselines.within_trial_auc` |
| Tie-aware MRR@10 / NDCG@1 (expected value under uniform tie-breaking) | `reduction_baselines.within_trial_ranking` |
| Rate curve on producer-thinned caches, native approach gate | `rate_curve_canonical.py` (`CONDS`, rate and monotone-thinning assertions) |
| Scroll floor and viewport-pointer kinematics, first-visit carve | `scroll_only_carve.scroll_features`, `scroll_kinematics.kinematics` |
| Same-rows sensor comparison with within-trial and paired readouts | `notebooks-v2/36_scroll_vs_cursor_deferred.ipynb` |

## 4. Parameters

| Parameter | Default | Controls |
|---|---|---|
| `--buffer` | 500 ms | cache condition `buf500`; samples strictly before mousedown(final click) − buffer |
| `--flavor` | `typed` | AOI map; must match the label cache flavor |
| `--labeled-only` | off | carve pool: shipped (9,932) vs label-complete (9,269); gate always runs on shipped |
| `--perms` | 100 | within-participant label permutations for the null |
| `APPROACH_PX` | 100 px | approached gate, evaluated on the native stream |
| fixation duration fallback | 200 ms | used only if `d` is missing from a fixation row |
| `PROX` (B2), `IDLE_GAP_MS` (B4) | 100 px, 500 ms | Huang hover zone; idle interval definition |
| `pause_threshold_ms` (kinematics) | 500 ms | inter-scroll-event gap counted as a pause |

## 5. Sensitivity tested

Label-complete pool, 9,269 rows, 2,608 trials, 47 participants, cache rule
(deferred 6,800 / evaluated-rejected 2,469). Null on the same rows: mean 0.511,
p95 0.525, p99 0.537.

| model | pooled AUC | fold mean ± sd |
|---|---|---|
| total dwell (gaze) | 0.807 | 0.812 ± 0.053 |
| first-visit dwell (gaze) | 0.514 | 0.537 ± 0.064 |
| first-visit fixation count | 0.538 | 0.561 ± 0.057 |
| mean_dist (cursor) | 0.665 | 0.675 ± 0.075 |
| M4-7 (cursor) | 0.680 | 0.683 ± 0.072 |
| M4-7 + first-visit dwell | 0.680 | 0.682 ± 0.072 |
| M4-7 + total dwell | 0.794 | 0.805 ± 0.052 |

Medians, deferred vs rejected: first-visit dwell 454 vs 415 ms; total dwell
1,965 vs 594 ms; 73 % of a deferred result's dwell arrives after the return.
Under the re-entry rule (`p != last`; deferred 6,575) the shape holds: total
dwell 0.823, first-visit 0.501.

Rate curve (rows common to all six caches, 33,518; deferred pool 9,871):

| rate | samples/trial | deferred | click |
|---|---|---|---|
| native | 151 | 0.691 | 0.934 |
| 30 Hz | 68 | 0.691 | 0.934 |
| 15 Hz | 44 | 0.692 | 0.934 |
| 5 Hz | 21 | 0.691 | 0.933 |
| 2 Hz | 12 | 0.692 | 0.923 |
| 1 Hz | 8 | 0.701 | 0.901 |

Reduction baselines (click: all 34,328 rows; deferred: 9,269):

| model | click AUC | MRR@10 | deferred pooled | deferred within-trial |
|---|---|---|---|---|
| B1 mouse length | 0.501 | 0.227 | 0.526 | 0.500 |
| B2 proximity dwell (Huang 2011) | 0.853 | 0.630 | 0.593 | 0.604 |
| B3 per-result summary (Liu 2014) | 0.864 | 0.679 | 0.603 | 0.635 |
| B4 page-grain battery | 0.502 | 0.227 | 0.599 | 0.500 |
| B5 rank position | 0.792 | 0.447 | 0.678 | 0.744 |
| B3 + B4 | 0.906 | 0.690 | 0.659 | 0.637 |
| M4-7 | 0.935 | 0.777 | 0.680 | 0.706 |
| B5 + M4-7 | 0.935 | 0.775 | 0.703 | 0.738 |
| everything | 0.946 | 0.809 | 0.753 | 0.744 |

B1 and B4 are constant within trial (asserted), so their within-trial AUC is
0.500 by construction and their MRR is the uniform-guess value.

Scroll producers (rows with at least two scroll events; the carve cutoff is the
end of the first gaze visit and is a diagnostic, not a deployable feature):

| producer / model | n | deferred pooled AUC |
|---|---|---|
| scroll_only: seven viewport features, full trial | 5,255 | 0.715 |
| scroll_only: same, first visit only | 5,255 | 0.634 |
| scroll_only: cursor M4-7, same rows | 5,255 | 0.662 |
| scroll_only: `vp_residence_ms` alone, full → first | 5,255 | 0.702 → 0.479 |
| scroll_only: null (mean / p95 / p99) | 5,255 | 0.526 / 0.544 / 0.549 |
| kinematics: viewport-pointer vector, full | 5,249 | 0.723 |
| kinematics: same, first-visit carve | 5,249 | 0.632 |
| kinematics: cursor M4-7, same rows | 5,249 | 0.662 |

The producers' pooled viewport-over-cursor gap does not survive the direct
same-rows test in `notebooks-v2/36_scroll_vs_cursor_deferred.ipynb`: on the
full scroll-eligible pool (8,653 rows) the cursor wins within-trial and the
participant-paired test is null (`[NB36:K2]`, `[NB36:K4]`); the producers'
5,1xx-row subset is selected by scroll-before-first-look timing (`[NB36:K10]`).
The pooled gap is between-trial base rate. The sensors are complementary and
the carve removes more from the viewport than from the cursor (`[NB36:K7]`). Both scroll
producers are label-complete by construction (a first-visit entry requires a
gaze visit, and every visit is in the label cache).


## 6. Sensitivity NOT tested

- The carve at a fixed post-first-visit horizon (e.g. first visit + 500 ms)
  rather than at the first departure; the current boundary is the cleanest
  but a deployable horizon would be a time, not a gaze event.
- Gap-fill flavor (`typed_gapfill`) for both label and visits.
- Return rules beyond the two in the lineage (e.g. requiring a minimum
  intervening depth).
- Reduction baselines under their sources' own targets and grains (page-grain
  targets for B1/B4); here they are scored at candidate grain only.

## 7. What's robust regardless of tweaking

- First-visit gaze dwell is inside the permutation null under both return
  rules and both pools; total dwell is above every cursor model on the same
  rows. The direction does not depend on pool, assignment rule, or return rule.
- The deferred rate curve is flat from native to 1 Hz; the click curve is not.
- Position beats the cursor vector within-trial on the deferred target
  (0.744 vs 0.706) because the label is defined on rank order; adding the
  cursor to position moves within-trial AUC by −0.006 and pooled by +0.025.

## 8. Limitations to disclose in papers

- The first-visit boundary is a gaze event. First-visit dwell is a leakage
  diagnostic for the baseline, not a deployable feature; the same is true of
  the first-visit scroll carve.
- The deferred label is order-defined, so rank position carries a prior on it
  by construction. Cursor claims on this target must be stated over position.
- The 663 never-fixated rows are excluded from the deferred pool; the shipped
  §4.3 number included them as rejected.
- Pooled AUC on a per-result target rewards between-trial base rate; report
  within-trial concordance beside it.

## 9. Where this rule appears in published / draft work

- CIKM 2026 rejection response → CHIIR 2027 resubmission
  (`cikm-leakycursor/notes/chiir-framing-2026-09-13.md`, §2 reduction table,
  §4.3, reviewer map R1-W2a). Not yet in `source/paper.md`.
- AO-SERP replication (`collab/allawati-ai-overviews/abandonment-2026-09-13/`,
  separate implementation; RMIT ethics permission required before citing).

## 10. Status

Current as of 2026-09-13. Earlier same-day outputs from the strict-band map
(total dwell 0.747, first-visit 0.504, 67 %) are superseded; their producers
are retained as `scripts/retired_2026-09-13_*.py` and their outputs under
`scripts/output/visit_decomposition.RETIRED-2026-09-13/`.
