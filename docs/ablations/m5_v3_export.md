# M5 v3 export: a deferred SCORE from cursor + viewport bands (+ rank)

**Tags:** `[LAB, AdSERP, typed, cursor-only + viewport bands]` · 47-fold LOSO balanced logistic regression, per-fold StandardScaler · target = NB22 gaze-regression label (deferred = 1, evaluated-rejected = 0), typed label cache keyed by (trial, position); the 663 approached non-click rows absent from the cache count as rejected, as in the shipped §4.3 number
**Producer:** `scripts/export_m5_v3.py` → `scripts/output/m5_v3/{m5_v3_cursor_bands.json, m5_v3_cursor_bands_rank.json, summary.json}`, copied to `approach-retreat/scripts/models/`
**Gate:** LOSO pooled AUC for `cursor_M4_7` (0.691065519), `bands_3` (0.788615666) and `cursor_M4_7 + bands_3` (0.789133048) each reproduce `viewport_bands_cursor_only/summary.json` to 1e-6 (all three diffs 0.0) before any v3 model is fitted or exported.
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

## LOSO, same pool for every row

| model | features | pooled AUC | fold mean ± sd | within-trial AUC |
|---|---|---|---|---|
| cursor M4-7 (gate) | 7 | 0.691 | 0.694 ± 0.070 | 0.718 |
| bands alone (gate) | 3 | 0.789 | 0.776 ± 0.064 | 0.773 |
| **cursor M4-7 + bands (gate, exported)** | 10 | **0.789** | 0.782 ± 0.057 | **0.776** |
| cursor M4-7 + bands + rank (exported) | 11 | 0.790 | 0.783 ± 0.060 | 0.775 |
| cursor M4-7 + `vp_any` + bands (not exported) | 11 | 0.790 | 0.783 ± 0.057 | 0.777 |
| bands + rank | 4 | 0.791 | 0.780 ± 0.064 | 0.774 |
| rank alone | 1 | 0.691 | 0.714 ± 0.073 | 0.759 |

Within-trial AUC scores only pairs inside one trial
(`reduction_baselines.within_trial_auc`, 9,752 pairs).

Paired by participant (fold-AUC differences, 10,000-draw bootstrap of the
mean, two-sided Wilcoxon):

| comparison | Δ | 95 % CI | p |
|---|---|---|---|
| cursor + bands − cursor | **+0.0882** | [+0.0722, +0.1046] | 2e-13 |
| + rank − cursor + bands | +0.0009 | [−0.0017, +0.0034] | 0.37 |
| + `vp_any` − cursor + bands | +0.0015 | [−0.0000, +0.0031] | 0.044 |

## Operating points, primary model (LOSO out-of-fold, 9,932 rows, prior 0.6847)

| threshold | method | predicted-deferred share | deferred P / R | rejected P / R |
|---|---|---|---|---|
| 0.300 | grid | 0.800 | 0.772 / 0.903 | 0.667 / 0.422 |
| 0.350 | grid | 0.722 | 0.801 / 0.845 | 0.618 / 0.544 |
| **0.373** | **prior-matching** | **0.685** | **0.814 / 0.814** | **0.596 / 0.596** |
| 0.400 | grid | 0.647 | 0.826 / 0.780 | 0.574 / 0.643 |
| 0.450 | grid | 0.583 | 0.847 / 0.721 | 0.543 / 0.718 |
| **0.466** | **Youden-J** | **0.562** | **0.856 / 0.702** | **0.535 / 0.743** |
| 0.500 | grid | 0.519 | 0.865 / 0.656 | 0.510 / 0.778 |
| 0.600 | grid | 0.403 | 0.895 / 0.527 | 0.457 / 0.865 |
| 0.700 | grid | 0.310 | 0.919 / 0.416 | 0.420 / 0.920 |
| 0.750 | grid | 0.263 | 0.925 / 0.355 | 0.401 / 0.937 |

The full 12-row table (0.30–0.75 in 0.05 steps plus the two named points, with
raw tp/fp/fn/tn) is inside each model JSON. The rank variant's table is within
0.01 of this one at every threshold.

## Calibration (equal-count decile bins of the out-of-fold score)

| bin | score range | mean score | observed deferred rate | n |
|---|---|---|---|---|
| 1 | 0.061–0.231 | 0.176 | 0.275 | 994 |
| 2 | 0.231–0.300 | 0.266 | 0.392 | 994 |
| 3 | 0.300–0.363 | 0.332 | 0.522 | 993 |
| 4 | 0.363–0.437 | 0.398 | 0.602 | 993 |
| 5 | 0.437–0.514 | 0.475 | 0.701 | 993 |
| 6 | 0.514–0.602 | 0.557 | 0.776 | 993 |
| 7 | 0.602–0.710 | 0.655 | 0.822 | 993 |
| 8 | 0.710–0.819 | 0.764 | 0.886 | 993 |
| 9 | 0.820–0.932 | 0.876 | 0.909 | 993 |
| 10 | 0.932–1.000 | 0.973 | 0.962 | 993 |

Brier 0.1918; worst bin off by 0.226. The score is monotone in the observed
rate but is not a probability: nine of ten bins under-predict, which is what
`class_weight='balanced'` does — it fits as though the classes were even while
the pool prior is 0.685, so the scores are pulled toward the balanced prior.
A consumer that needs probabilities has to recalibrate (Platt or isotonic on
its own data); a consumer that ranks or thresholds does not.

## What carries the model (standardized coefficients, mean over 47 LOSO folds)

`vt_top` +1.351, `vt_mid` +0.662, `vt_bot` +0.232, then every cursor term under
0.26 in magnitude: `mean_dist` −0.260, `dwell_in_proximity_ms` +0.105,
`min_dist` −0.104, `mean_approach_velocity` +0.069, `max_approach_velocity`
−0.060, `direction_changes` −0.038, `frac_decreasing` −0.020. The band ordering
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

**The instrument emits a score.** Per-instance hard labels from cursor alone
are near a coin flip on the rejected side: v2 at its Youden point has rejected
precision 0.485 (derived from TPR 0.7276 / FPR 0.4425 on 6,800 / 3,132), i.e.
half of everything it calls `EVALUATED_REJECTED` was in fact returned to. v3
raises that to 0.535 at Youden and 0.596 at the prior-matching point, which is
better and still not a label a consumer should treat as a fact about one
result.

**The bands are what moved it.** +0.0882 per participant over the cursor alone,
CI clear of zero, and the gap survives within trials (0.776 vs 0.718). The
exported model's weight sits in `vt_top`.

**Rank does not help.** `position` adds +0.0009 with a CI spanning zero
(p = 0.37); it is exported only so a consumer that already knows the rank can
check that for itself. `vp_any` adds +0.0015 and is not exported.

**The score is not calibrated,** by construction of the balanced fit; it is
monotone and usable for ranking and thresholding as it stands.

**Choosing a point.** Youden buys rejected recall (0.743) at rejected precision
0.535; the prior-matching point at 0.373 makes the two classes symmetric
(0.814/0.814 deferred, 0.596/0.596 rejected) and keeps the predicted-deferred
share equal to the pool's own rate, which is the sane default for a consumer
that aggregates rather than acts per result.

One science caveat, carried from `viewport_bands_cursor_only.md`: the band
signal is mostly the return (cut at the end of the first gaze visit, bands fall
0.771 → 0.553), which does not matter for an instrument whose consumer wants to
know whether the user came back, but does mean the bands are not a prediction
made before the return happened.

## Not established

- Aggregate use, as above — AdSERP serves each trial a unique page.
- Whether the score transfers to WILD. Supervision is the LAB gaze-regression
  label, and the bands need a scroll timeline the ACD stream does not carry.
- Calibration after recalibration: no Platt/isotonic variant was fitted, and no
  `class_weight=None` refit was run to see whether the under-prediction is
  wholly the balanced weighting.
- The operating-point table is out-of-fold on 47 LAB participants; the numbers
  a deployment sees depend on its own prior, which is not 0.685 unless its pool
  is built the same way (approached, not clicked).
