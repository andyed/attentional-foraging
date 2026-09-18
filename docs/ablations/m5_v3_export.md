# M5 v3 export: a deferred SCORE from cursor + viewport bands (+ rank)

**Tags:** `[LAB, AdSERP, typed, cursor-only + viewport bands]` · 47-fold LOSO balanced logistic regression, per-fold StandardScaler · target = NB22 gaze-regression label (deferred = 1, evaluated-rejected = 0), typed label cache keyed by (trial, position); the 663 approached non-click rows absent from the cache count as rejected, as in the shipped §4.3 number
**Producer:** `scripts/export_m5_v3.py` → `scripts/output/m5_v3/{m5_v3_cursor_bands.json, m5_v3_cursor_bands_rank.json, summary.json}`, copied to `approach-retreat/scripts/models/`
**Gate:** balanced LOSO pooled AUC for `cursor_M4_7` (0.691065519), `bands_3` (0.788615666) and `cursor_M4_7 + bands_3` (0.789133048) each reproduce `viewport_bands_cursor_only/summary.json` to 1e-6 (all three diffs 0.0) before any v3 model is fitted or exported.
**Key Claims:** none yet.
**Generated:** 2026-09-19.

## Question

`m5_cursor_only_v2.json` is the shipped detector: seven cursor features, LOSO
0.691. At its own Youden-J point it calls 6,800 deferred and 3,132
evaluated-rejected rows with TPR 0.7276 and FPR 0.4425, which puts the
**rejected-label precision at 48.5 %** — a hard `EVALUATED_REJECTED` call from
the cursor alone is a coin flip. `docs/ablations/viewport_bands_cursor_only.md`
scores the three viewport-band features at 0.789 on the identical pool, and the
library already emits those bands at runtime
(`edmonds-2026-vpbands-v1`). Two questions follow: what does a deployable
model that reads both look like, and should the artifact ship a threshold at
all rather than a score with an operating-point table?

## What is exported

Same pool, rows, labels and window as `viewport_bands_cursor_only.py` (9,932
approached non-click rows, 47 participants, 2,437 trials; bands full-window
only, no first-visit carve). Both files keep every v2 JSON key — `features`,
`scaler_mean`, `scaler_scale`, `coefficients_raw`, `intercept`,
`operating_threshold`, `apply`, provenance — so
`approach-retreat/scripts/m5_inference.py` loads them unchanged, and add
`score_semantics`, `operating_points`, `calibration`, `feature_units`,
`loso_within_trial_auc` and the per-fold standardized coefficients.

| file | features | role |
|---|---|---|
| `m5_v3_cursor_bands.json` | APPROACH_7 + `vt_top`, `vt_mid`, `vt_bot` | primary |
| `m5_v3_cursor_bands_rank.json` | the above + `position` | variant |

`operating_threshold` still carries the Youden-J point because the schema and
`M5Classifier` need one number, but `score_semantics` says in the file that the
score is the product and the threshold is the consumer's choice.

**The exported fits are unweighted (`class_weight: null`).** The gate and every
science row below use `class_weight='balanced'`, as v2 and the bands ablation
do. That fit is not a probability: it fits as though the classes were even
while the pool prior is 0.685, so its out-of-fold score under-predicts in nine
of ten deciles (Brier 0.1918, worst bin off by 0.226; the block is kept in
`summary.json` under `balanced_score_not_exported`). Since the consumer's
product is the continuous score, that is a defect in the instrument rather than
a footnote, so the deployable models are refitted with no class weighting and
carry `training_prior` (6,800 / 9,932 = 0.6847) plus a prior-shift recipe in
`score_semantics`: to move the score to another base rate, add
`log((p_new/(1−p_new)) / (p_train/(1−p_train)))` to the logit.

## LOSO, same pool for every row

| model | weighting | features | pooled AUC | fold mean ± sd | within-trial AUC |
|---|---|---|---|---|---|
| cursor M4-7 (gate) | balanced | 7 | 0.691 | 0.694 ± 0.070 | 0.718 |
| bands alone (gate) | balanced | 3 | 0.789 | 0.776 ± 0.064 | 0.773 |
| cursor M4-7 + bands (gate) | balanced | 10 | 0.789 | 0.782 ± 0.057 | 0.776 |
| cursor M4-7 + bands + rank | balanced | 11 | 0.790 | 0.783 ± 0.060 | 0.775 |
| cursor M4-7 + `vp_any` + bands | balanced | 11 | 0.790 | 0.783 ± 0.057 | 0.777 |
| bands + rank | balanced | 4 | 0.791 | 0.780 ± 0.064 | 0.774 |
| rank alone | balanced | 1 | 0.691 | 0.714 ± 0.073 | 0.759 |
| **cursor M4-7 + bands (DEPLOYED)** | **none** | 10 | **0.789** | 0.782 ± 0.057 | **0.776** |
| cursor M4-7 + bands + rank (deployed variant) | none | 11 | 0.790 | 0.783 ± 0.060 | 0.776 |

Within-trial AUC scores only pairs inside one trial
(`reduction_baselines.within_trial_auc`, 9,752 pairs).

Paired by participant (fold-AUC differences, 10,000-draw bootstrap of the
mean, two-sided Wilcoxon):

| comparison | Δ | 95 % CI | p |
|---|---|---|---|
| cursor + bands − cursor | **+0.0882** | [+0.0722, +0.1046] | 2e-13 |
| + rank − cursor + bands | +0.0009 | [−0.0017, +0.0034] | 0.37 |
| + `vp_any` − cursor + bands | +0.0015 | [−0.0000, +0.0031] | 0.044 |
| unweighted − balanced, cursor + bands | +0.0004 | [−0.0001, +0.0008] | 0.038 |
| unweighted − balanced, + rank | +0.0001 | [−0.0005, +0.0006] | 0.64 |

Dropping the class weighting does not move the ranking: pooled AUC is
unchanged to three decimals in both variants, and the per-participant deltas
are within 0.001 of zero. What it moves is the calibration.

## Operating points, DEPLOYED model (unweighted, LOSO out-of-fold, 9,932 rows, prior 0.6847)

| threshold | method | predicted-deferred share | deferred P / R | rejected P / R |
|---|---|---|---|---|
| 0.300 | grid | 0.961 | 0.703 / 0.986 | 0.765 / 0.095 |
| 0.400 | grid | 0.886 | 0.736 / 0.953 | 0.714 / 0.258 |
| 0.500 | grid | 0.765 | 0.786 / 0.878 | 0.646 / 0.482 |
| 0.550 | grid | 0.694 | 0.810 / 0.820 | 0.599 / 0.582 |
| **0.556** | **prior-matching** | **0.685** | **0.814 / 0.814** | **0.596 / 0.596** |
| 0.600 | grid | 0.630 | 0.833 / 0.766 | 0.567 / 0.666 |
| 0.650 | grid | 0.564 | 0.854 / 0.704 | 0.535 / 0.739 |
| **0.660** | **Youden-J** | **0.551** | **0.859 / 0.692** | **0.529 / 0.753** |
| 0.700 | grid | 0.495 | 0.872 / 0.631 | 0.500 / 0.799 |
| 0.750 | grid | 0.426 | 0.888 / 0.552 | 0.466 / 0.848 |

The full 12-row table (0.30–0.75 in 0.05 steps plus the two named points, with
raw tp/fp/fn/tn) is inside each model JSON; the rank variant's is within 0.01
of this one at every threshold. Thresholds are not comparable with the
balanced fit's — the unweighted score sits higher because it is centred on the
0.685 prior rather than on 0.5 — which is the point of reading the share
column rather than carrying a number over.

## Calibration (equal-count decile bins of the out-of-fold score)

Deployed (unweighted) fit, primary model — Brier **0.1679**, worst bin off by
**0.044**, inside the 0.05 tolerance, so **no Platt layer was added** and
`apply` stays the v2 formula:

| bin | score range | mean score | observed deferred rate | n |
|---|---|---|---|---|
| 1 | 0.123–0.385 | 0.308 | 0.268 | 994 |
| 2 | 0.385–0.471 | 0.431 | 0.390 | 994 |
| 3 | 0.471–0.545 | 0.510 | 0.532 | 993 |
| 4 | 0.545–0.624 | 0.584 | 0.602 | 993 |
| 5 | 0.624–0.696 | 0.661 | 0.705 | 993 |
| 6 | 0.696–0.769 | 0.733 | 0.776 | 993 |
| 7 | 0.769–0.847 | 0.808 | 0.820 | 993 |
| 8 | 0.847–0.915 | 0.881 | 0.883 | 993 |
| 9 | 0.915–0.971 | 0.943 | 0.909 | 993 |
| 10 | 0.971–1.000 | 0.989 | 0.962 | 993 |

The rank variant is the same picture: Brier 0.1674, worst bin 0.049, no Platt
layer. For contrast, the balanced fit on the identical rows scores Brier 0.1918
with a worst bin of 0.226 and under-predicts in nine of ten deciles
(`summary.json` → `balanced_score_not_exported`).

## What carries the model (standardized coefficients, mean over 47 LOSO folds)

Deployed fit: `vt_top` +1.412, `vt_mid` +0.721, `vt_bot` +0.244, then every
cursor term under 0.26 in magnitude — `mean_dist` −0.250,
`dwell_in_proximity_ms` +0.096, `min_dist` −0.107, `mean_approach_velocity`
+0.069, `max_approach_velocity` −0.064, `direction_changes` −0.022,
`frac_decreasing` −0.022. The balanced fit's are within 0.06 of these
(`vt_top` +1.351, `vt_mid` +0.662, `vt_bot` +0.232). The band ordering
`vt_top` > `vt_mid` > `vt_bot` is the same as in the bands-alone fit.

## Aggregate use: not established

The instrument's real validation — does a 0.69-to-0.79 per-instance score
become a clean separation when averaged over many participants seeing the same
result — cannot be run on AdSERP. Page identity is available (the
`page.php?q=<slug>` URL and the `<task>` batch id in each trial's metadata
XML), and across the 2,437 pool trials there are 2,437 distinct slugs and 2,437
distinct task ids: **no page is seen by more than one participant.** The claim
needs a corpus where one page is served to many sessions; it is recorded in
`summary.json` under `aggregate_use` as `not_established` with those counts.

## Reading

**The deployed fit is unweighted, and the reason is calibration, not ranking.**
`class_weight='balanced'` stays on the gate and on every comparison row so this
note lines up with v2 and the bands ablation, but the two exported files are
refitted with no class weighting. Ranking is untouched (pooled AUC 0.789 either
way; paired delta +0.0004 [−0.0001, +0.0008]) while the score becomes a
probability: Brier 0.1918 → **0.1679**, worst decile 0.226 → **0.044**. No Platt
layer was needed, so `apply` is still the v2 formula and any consumer that
computes `sigmoid(z)` gets the calibrated score. Each file names the prior it is
calibrated to (`training_prior` 0.6847) and how to shift it.

**The instrument emits a score.** Per-instance hard labels from cursor alone
are near a coin flip on the rejected side: v2 at its Youden point has rejected
precision 0.485 (derived from TPR 0.7276 / FPR 0.4425 on 6,800 / 3,132), i.e.
half of everything it calls `EVALUATED_REJECTED` was in fact returned to. The
deployed v3 gives rejected precision 0.529 at Youden (t = 0.660: deferred
0.859 / 0.692, rejected 0.529 / 0.753) and 0.596 at the prior-matching point
(t = 0.556: deferred 0.814 / 0.814, rejected 0.596 / 0.596). Better, and still
not a label to treat as a fact about one result.

**The bands are what moved the discrimination.** +0.0882 per participant over
the cursor alone, CI clear of zero, and the gap survives within trials (0.776
vs 0.718). The exported model's weight sits in `vt_top`.

**Rank does not help.** `position` adds +0.0009 with a CI spanning zero
(p = 0.37); it is exported only so a consumer that already knows the rank can
check that for itself. `vp_any` adds +0.0015 and is not exported.

**Choosing a point.** Youden buys rejected recall (0.753) at rejected precision
0.529; the prior-matching point makes the two classes symmetric and keeps the
predicted-deferred share equal to the pool's own rate, which is the sane
default for a consumer that aggregates rather than acts per result.

One science caveat, carried from `viewport_bands_cursor_only.md`: the band
signal is mostly the return (cut at the end of the first gaze visit, bands fall
0.771 → 0.553), which does not matter for an instrument whose consumer wants to
know whether the user came back, but does mean the bands are not a prediction
made before the return happened.

## Not established

- Aggregate use, as above — AdSERP serves each trial a unique page.
- Whether the score transfers to WILD. Supervision is the LAB gaze-regression
  label, and the bands need a scroll timeline the ACD stream does not carry.
- Isotonic calibration was not tried; the unweighted fit came inside tolerance
  (0.044, against 0.05) on its own, so no calibration layer of any kind is in
  the exported files. The residual is not flat: the worst bin is the fifth
  decile, where the score under-predicts by 0.044, and the top two deciles
  over-predict by 0.034 and 0.027 — a consumer that cares specifically about
  either end may still want its own layer.
- The operating-point table is out-of-fold on 47 LAB participants; the numbers
  a deployment sees depend on its own prior, which is not 0.685 unless its pool
  is built the same way (approached, not clicked).
