# PAI on the deferred class — does peripheral gaze mass separate the results the eyes come back to?

**Tags:** `[LAB, AdSERP, typed, buf500 mousedown]` · **two kernels reported**
**Producer:** `scripts/pai_deferred_probe.py` → `summary_w1000_full_boundary_cm_24.json` (1 s, untruncated, boundary-distance kernel with cortical-magnification falloff, `scripts/peripheral_kernel.py`, 43 px/° (2026-09-14 derivation; runs were made with 24 px/°, so E2 = 48 px ≈ 1.1°)) and, under the published PAI Eq. 2 (`spec_eq2`): `summary.json` (2 s, truncated), `summary_w2000_full.json`, `summary_w1000_full.json`
**Generated:** 2026-09-14. Assessment probe for whether PAI has a place in the CHIIR 2027 divergence framing.

> **Kernel note (added later the same day, read first).** The published Eq. 2
> alpha is nearly flat in eccentricity on SERP result bands (corpus Spearman
> with boundary distance −0.08; `engagement_state_census.md` §Kernel), so its
> "peripheral mass on this band" is close to "fixation duration anywhere on
> the page in the window". Under a boundary-distance kernel with a
> cortical-magnification falloff, the increment reported below **vanishes**:
>
> | 1 s untruncated window, 6,154 rows | published kernel | boundary kernel |
> |---|---|---|
> | PAI alone | 0.546 | 0.532 |
> | M4-7 | 0.682 | 0.682 |
> | M4-7 + PAI | 0.691 | 0.681 |
> | paired gain over M4-7 | +0.010 [+0.003, +0.016] | **−0.000 [−0.001, +0.000]** |
> | deferred vs rejected median intake | 274 vs 301 (deferred lower) | 177 vs 158 (deferred higher) |
>
> The +0.010 was page-wide fixation duration in the second after exit, not
> peripheral intake on the target; the "deferred gets less" sign was the
> same artefact. With a real eccentricity falloff, the deferred result gets
> slightly *more* intake after the eyes leave it (it is nearer), and that
> carries nothing the cursor vector does not already have. The verdict
> below stands, for a stronger reason.

## Question

The CHIIR 2027 spine is gaze–cursor divergence: the *deferred* class is the
result the cursor abandoned while the eyes came back. PAI is the gaze-side
measurement of the same phenomenon — attention on a result the eyes have not
(or no longer) foveated. If PAI carries the deferred split, it belongs in the
paper. Scored on the carve's own rows so it sits beside the shipped numbers:
M4-7 0.680, `mean_dist` 0.665, first-visit gaze dwell 0.514, on the 9,269
label-complete approached non-click rows (`deferred_dwell_carve.py
--labeled-only`, `summary_labeled_only.json`).

## Setup

- **Rows, labels, scorer:** identical to the carve. Cursor-only typed
  mousedown cache (hash-checked against its sidecar), NB22 gaze-regression
  label from `regression_labels_cache_typed.json`, 47-fold LOSO logistic
  regression, balanced, C = 1. **Gate — PASS:** M4-7 on the 9,269-row pool
  reproduces the carve's 0.6802 to four decimals in every run.
- **Map:** typed bands (`typed_aoi_bands`), fixations assigned by the label
  producer's own rule; the probe's visit walk is asserted against
  `visit_decomposition` on `first_visit_end_ms` for every row (0 drift).
- **PAI channel:** `pai_spec.rect_alpha_grid` Eq. 2, column extent
  [162, 702], peripheral = strictly outside the band rect. Rate = mass / window
  (not accumulation — the record-length trap, `pai_exposure_validation.md`
  Probe A).
- **Windows per (trial, position):** `pre` = the W before the first visit
  starts; `post` = the W after the first visit ends, truncated at the return
  (deferred rows) and at the trial's last fixation; `post_x500` additionally
  drops the 500 ms before the return so approach fixations do not read the
  label back. In the post window point-in-AOI dwell is zero for every row by
  construction, so PAI is the only gaze channel with content.
- **Controls scored on the same rows:** `gaze_dist_post` (mean |fixation y −
  band centre|, the non-PAI gaze-proximity comparator), `n_fix_post`
  (fixation count), `avail_post_ms` (window length, the leak check).

## Results

### The truncated-window run is contaminated — do not quote it

2 s window, truncation allowed, 7,092 rows. `avail_post_ms` **alone** scores
0.613: window length predicts the label because deferred rows have a return
that truncates the window (median gap 2.5 s vs a full 2 s for rejected rows).
The M4-7 + PAI increment there (+0.022, CI [+0.013, +0.032]) inherits that
channel. Kept in `summary.json` as the cautionary row.

### Untruncated windows (the clean design)

Rows whose post window is a full W (no return inside it, not at trial end).

| Model | W = 2 s, n = 4,752 (2,919 deferred) | W = 1 s, n = 6,154 (4,153 deferred) |
|---|---|---|
| `avail_post_ms` alone (leak check) | 0.500 | 0.500 |
| `pai_post_x500` alone | 0.545 | 0.546 |
| `gaze_dist_post` alone | 0.561 | 0.524 |
| `n_fix_post` alone | 0.532 | 0.523 |
| `mean_dist` (cursor) | 0.679 | 0.667 |
| **M4-7 (cursor)** | **0.698** | **0.682** |
| M4-7 + `gaze_dist_post` | 0.697 | 0.681 |
| M4-7 + `n_fix_post` | 0.698 | 0.682 |
| M4-7 + `pai_post_x500` | 0.708 | 0.691 |
| permutation null, PAI alone (mean / p95) | 0.501 / 0.516 | 0.493 / 0.519 |

Paired per-participant ΔAUC (47 folds, 10k bootstrap):

| Comparison | W = 2 s | W = 1 s |
|---|---|---|
| M4-7 + PAI vs M4-7 | **+0.008 [+0.002, +0.015]** | **+0.010 [+0.003, +0.016]** |
| M4-7 + gaze-dist vs M4-7 | −0.001 [−0.004, +0.001] | −0.001 [−0.004, +0.001] |
| M4-7 + PAI + gaze-dist vs M4-7 + gaze-dist | +0.008 [+0.001, +0.016] | +0.011 [+0.005, +0.018] |
| M4-7 + PAI + n-fix vs M4-7 + n-fix | +0.010 [+0.002, +0.018] | +0.011 [+0.004, +0.019] |
| PAI alone vs gaze-dist alone | −0.005 [−0.042, +0.033] | +0.031 [−0.001, +0.063] |

Pre-entry window: PAI alone 0.528 (2 s) / 0.523 (1 s); M4-7 + PAI paired
+0.008 [+0.002, +0.015] at 2 s and +0.002 [−0.002, +0.007] at 1 s. Not
reliable.

**Direction.** Deferred results receive *less* peripheral mass in the window
after the eyes leave them (median `pai_post_x500` 292 vs 316 at 2 s; 274 vs
301 at 1 s). The periphery does not "keep the candidate alive"; if anything
the gaze moves further off the results it will return to. Gaze distance
medians differ in the same direction at 2 s (270 vs 303 px) and not at 1 s
(215 vs 222 px), so the PAI increment is not reducible to plain proximity.

## Reading

1. **PAI carries a real but small piece of the deferred split** — about
   0.545 alone, +0.01 AUC over the seven-feature cursor vector, robust to the
   window-length, fixation-count and gaze-proximity controls, above the
   permutation null, and stable across the two window lengths.
2. **It is an order of magnitude below the cursor.** On the same rows the
   cursor vector alone is 0.68–0.70 and `mean_dist` alone 0.67–0.68. In the
   divergence frame the cursor is the better witness to the eyes' return;
   the periphery adds a footnote, not a section.
3. **The sign contradicts the story that would have made it a section.**
   "The periphery keeps sampling what the eyes will come back to" is not
   what the data say. A negative-sign +0.01 increment is not a CHIIR
   contribution.
4. **The first run reproduced the LF/HF record-length trap on a new
   feature.** Any windowed PAI feature that ends at an event the label
   defines (the return) must be scored on untruncated rows or the window
   length is the feature.

## Verdict

**PAI stays out of CHIIR 2027.** The 2026-08-31 boundary decision stands,
now on post-fix evidence (cursor-only stream, label producer's own map,
label-complete pool) rather than on track-separation grounds alone. At most
the two-sentence discussion note already budgeted, and if a number is ever
quoted it is the untruncated 1 s row under the boundary kernel: PAI 0.532
alone, −0.000 paired over M4-7. The published-kernel +0.010 is the
flat-kernel artefact row, not a result.

The result is a PAI-track finding (Q2/Q6 territory: what the periphery
carries about the deferred class, and where it sits beside the cursor) and
belongs with the method's authors — ETRA 2027 short papers are due
2027-02-11 (abstract 02-04), after CHIIR's 2026-10-15 full-paper deadline.

## Re-derivation debt (pre-fix PAI numbers)

Every number in `pai_exposure_validation.md` and `pai_preentry_probe.json`
was computed before the 2026-09-04 lineage audit and the 2026-09-13 carve
fix: organic_hybrid bands, and rows/labels from the gaze-selected
`compute_cursor_approach_features.py` caches. In particular the "+0.0156 over
the full 7-feature cursor model" increment was over gaze-dependent M3-7 rows
that the paper has retired. Before any of it is quoted outside the track
doc, re-run the ablation on the cursor-only typed mousedown cache with the
same gate this probe uses. The Q3 per-etype census (`pai_etype_census.py`)
is gaze-only and unaffected by the cursor lineage, but is still on
organic_hybrid bands.
