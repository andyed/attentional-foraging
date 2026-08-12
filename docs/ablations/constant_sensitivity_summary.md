# Constant-sensitivity ablations

Three pipeline constants could reasonably be called ad-hoc: the 5th-fixation
early-scan boundary, the 100 px proximity zone, and the choice of AOI center
(rather than, e.g., the result link) as the distance anchor. Each gets a
sensitivity sweep here instead of an assertion.

Generated 2026-08-12. All numbers are `[LAB, AdSERP]` LOSO click-prediction
AUCs: 47-fold leave-one-participant-out logistic regression (StandardScaler,
balanced class weights, C = 1.0), 19,848 (trial, AOI) records / 2,589 clicks
for sweeps A–B (`organic_hybrid`, 500 ms click buffer — the canonical
Sec. 4.1/5.1 headline protocol) and 14,760 records for sweep C (`organic`,
the phase-restricted protocol behind the paper's temporal-window claim).
Both feature vectors are reported per cell: **M4-7** (the paper's definition
of M4 — seven leakage-corrected features) and **M4-9** (adds `final_dist` +
`retreat_dist`, the pair the Sec. 5.2 leakage screen excludes; matches
`m4_nb21_hybrid_rerun.py`'s nine-feature `M4_FEATURES`). "fold mean ± sd" is
the per-participant fold AUC distribution (n = 47 folds). Anchor runs
reproduced the canonical values before any sweep cell was emitted
(M4-7 = 0.8468 vs canonical 0.847, Δ = −0.0002; M4-9 = 0.8671, Δ = +0.0000).

Scripts: `scripts/proximity_zone_ablation.py`,
`scripts/distance_anchor_ablation.py`, `scripts/fixation_k_ablation.py`
(shared harness `scripts/constant_ablation_common.py`; each sweep exec's the
canonical extractor source with a single exact-string constant substitution,
so every other byte of the pipeline is identical to the script on disk).
JSON sidecars sit next to this file.

---

## A. Proximity-zone width (the 100 px zone)

**Where it lives:** `compute_cursor_approach_features.py ::
compute_approach_features :: PROX_THRESHOLD = 100` (px, local constant).
Only `dwell_in_proximity_ms` reads it — dwell accumulates while the cursor's
vertical distance to the AOI anchor is below the threshold; the other
features are independent of it. Record sets are identical across all five
values (asserted), so differences are attributable to the width alone.

| proximityPx | M4-7 AUC | M4-7 fold mean ± sd | M4-7 MRR@10 | M4-9 AUC | M4-9 fold mean ± sd | ΔM4-7 vs 100 px |
|---:|---:|---:|---:|---:|---:|---:|
| 50 px  | 0.8486 | 0.8523 ± 0.0439 | 0.7517 | 0.8672 | 0.8676 ± 0.0411 | +0.0018 |
| 75 px  | 0.8508 | 0.8543 ± 0.0438 | 0.7550 | 0.8703 | 0.8706 ± 0.0405 | +0.0040 |
| **100 px (canonical)** | **0.8468** | 0.8510 ± 0.0446 | 0.7414 | 0.8671 | 0.8678 ± 0.0405 | — |
| 150 px | 0.8412 | 0.8462 ± 0.0469 | 0.7326 | 0.8621 | 0.8635 ± 0.0419 | −0.0056 |
| 200 px | 0.8367 | 0.8420 ± 0.0481 | 0.7303 | 0.8579 | 0.8593 ± 0.0426 | −0.0101 |

**Defense sentence:** M4 AUC stays within 0.837–0.851 across a 4× range of
zone width (50–200 px) — a total spread of 0.014 AUC, under one-third of the
0.045 between-participant fold SD — with a mild decline only when the zone
grows past 150 px (where a 100 px-tall zone starts spanning neighboring
results); 100 px was not tuned to the headline (75 px would have scored
+0.004 higher).

**Honest characterization:** not perfectly flat — the trend is gently
single-peaked around 75–100 px and loses ~0.010 AUC by 200 px, consistent
across both feature vectors and mirrored in MRR@10 (0.730–0.755). The
conclusion (M4 ≈ 0.85, +0.17–0.18 over position alone) is unchanged at every
width. Complementary prior sweep: the same 100 px constant's *other* use —
the `min_dist < 100 px` "approached" gate in the NB22 four-class taxonomy —
was already swept in `scripts/approach_threshold_sensitivity.py`
(50–200 px); the deferred vs evaluated-rejected motor-signature dissociation
holds at every threshold (K5/K6 Mann-Whitney p ≤ 7.7e-13 everywhere). This
sweep closes the gap that script declared out of scope (regenerating the
dwell feature itself at each radius).

## B. Distance anchor (AOI center vs the link)

**Where it lives:** `compute_cursor_approach_features.py ::
compute_approach_features :: result_centers` — the anchor is the **vertical
midpoint between consecutive AOI band tops** (center-Y only; the geometry is
1-D vertical and AOI x-extent is never used). It feeds
`dwell_in_proximity_ms` and the three velocity-derived features;
`min_dist` / `mean_dist` / `frac_decreasing` (and `final_dist` /
`retreat_dist` in M4-9) are gaze-cursor coupling distances that never
reference the anchor.

**Why no true link anchor:** no title/link sub-geometry exists anywhere in
the data — the AllSERP typed AOI exports
(`scripts/output/adserp_aois_by_trial_id_typed*.jsonl`) carry whole-result
boxes only (`top_y`/`bottom_y`/`left_x`/`right_x`), and AdSERP's static SERP
HTML cannot be re-rendered to recover element boxes (same limitation
documented in `m4_nb21_hybrid_rerun.py`). Since the title link renders at
the top of a result block, the **AOI top edge is the link proxy** and is
documented as such. Record sets are identical across anchors (asserted).

| anchor | M4-7 AUC | M4-7 fold mean ± sd | M4-7 MRR@10 | M4-9 AUC | M4-9 fold mean ± sd | ΔM4-7 vs center |
|---|---:|---:|---:|---:|---:|---:|
| **center (canonical)** | **0.8468** | 0.8510 ± 0.0446 | 0.7414 | 0.8671 | 0.8678 ± 0.0405 | — |
| top edge (link proxy) | 0.8291 | 0.8331 ± 0.0496 | 0.7200 | 0.8502 | 0.8513 ± 0.0442 | −0.0177 |
| nearest boundary | 0.8336 | 0.8388 ± 0.0497 | 0.7226 | 0.8554 | 0.8571 ± 0.0441 | −0.0132 |

**Defense sentence:** the AOI center is not an arbitrary choice but the
best-performing of the three candidate anchors — measuring distance to the
top edge (the link proxy, since no per-element link boxes exist in the data)
costs 0.018 AUC and to the nearest AOI boundary costs 0.013 AUC — and even
the worst anchor leaves M4 at 0.829, so no qualitative conclusion depends on
the choice.

**Honest characterization:** this is the least-flat of the three sweeps
(spread 0.018 AUC ≈ 0.4 fold-SD), and the direction favors the paper's
choice: the center is the unique interior point that makes the distance
signal symmetric over a result's full card height, while the top edge
systematically under-credits dwell over the lower part of tall results. The
ordering (center > boundary > top edge) is identical for M4-9 and for
MRR@10.

## C. The fifth fixation (early-scan / deliberation boundary)

**Where it lives:** NOT in the M4 = 0.847 headline model (which is
whole-trial). The constant is `scripts/phase_restricted_ablation.py ::
SURVEY_END = 5` (lifted from `notebooks-v2/13_survey_phase.ipynb`'s OSEC
operationalization, "saccades 1–5 are survey"), and in the paper at
`3_method.tex:63–64` — the temporal-window ablation that shows the click
signal concentrates in the post-fixation-5 deliberation window. Sweep
protocol: `--attribution organic`, M4-7/M4-9, survey window = cursor events
before the end of the k-th fixation, post-survey = from it onward.
Whole-trial baseline (k-independent): M4-7 = 0.8906, M4-9 = 0.9199 on
14,760 records. Record counts necessarily vary with k (a trial needs > k
fixations to have a boundary); n is reported per cell.

| k | post-survey M4-7 AUC (n) | survey M4-7 AUC (n) | Δpost vs whole | Δsurvey vs whole | post-survey M4-9 | survey M4-9 |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0.8922 (14,754) | 0.6958 (6,570) | +0.0016 | −0.1948 | 0.9200 | 0.6957 |
| 4 | 0.8930 (14,753) | 0.6953 (7,936) | +0.0024 | −0.1953 | 0.9201 | 0.6949 |
| **5 (canonical)** | **0.8933 (14,748)** | **0.6937 (8,663)** | +0.0027 | −0.1969 | 0.9199 | 0.6936 |
| 6 | 0.8936 (14,735) | 0.6935 (9,208) | +0.0030 | −0.1971 | 0.9197 | 0.6931 |
| 7 | 0.8938 (14,720) | 0.6939 (9,641) | +0.0032 | −0.1967 | 0.9192 | 0.6936 |

(fold sd ≈ 0.039 for post-survey cells, ≈ 0.070 for survey cells, n = 47
folds throughout.)

**Defense sentence:** the fifth-fixation cut is not load-bearing — moving
the boundary anywhere in k ∈ {3…7} changes the post-survey AUC by ≤ 0.0016
and the survey-window AUC by ≤ 0.0023 (both under 1/20 of a fold SD), so the
paper's claim (deliberation window reproduces whole-trial performance while
the early-scan window collapses by ~0.20 AUC) holds identically at every
plausible boundary; k = 5 is retained because it is where the saccade-
amplitude compression transition sits (107.8 px → 69.4 px median, N = 2,754
trials, AllSERP supplement).

**Paper-consistency finding (flag for the revision):** the stored run behind
`3_method.tex:63` (whole = 0.8803, post = 0.8836, Δ = +0.003, survey =
0.6938; `summary_organic.json`, 2026-05-15) predates commit `b9084a42`
(2026-07-25), which added velocity dt-floor/clamp sanitization to
`phase_restricted_ablation.py`. The current canonical extractor gives
whole = 0.8906 (+0.0103) and post = 0.8933 (+0.0097); the survey cell is
essentially unchanged (0.6937, −0.0001). The paper's qualitative claim is
unaffected (Δpost = +0.0027 is still "within fold noise", and "collapses to
0.694" still matches), but the prose Δ = −0.187 becomes −0.197 under the
current extractor — the tex numbers should either be refreshed from a rerun
of the current script or pinned to the pre-b9084a42 version explicitly.

---

## One-line answers to R2

- **100 px zone:** swept 50–200 px; M4 AUC 0.837–0.851, spread 0.014 ≈ 1/3
  fold SD; not tuned (75 px scores higher than 100 px).
- **AOI center:** best of three anchors tested; the link proxy (top edge,
  used because no link sub-geometry exists in AdSERP/AllSERP) costs
  0.018 AUC; worst case still 0.829.
- **5th fixation:** only enters the temporal-window ablation, not the
  headline model; k ∈ {3…7} moves both windows' AUC by < 0.003; grounded
  independently in the saccade-amplitude transition.
