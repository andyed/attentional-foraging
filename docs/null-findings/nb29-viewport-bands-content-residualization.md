# NB29 — content-residualized viewport bands (null)

## TL;DR

Residualizing viewport-band dwell against content-complexity features (token
count, character count, type–token ratio, query cosine, centroid novelty)
before the deferred-vs-evaluated-rejected LR does **not** improve the
classifier — it *destroys* signal. Δ (retreat + residualized bands) −
(retreat + raw bands) = **−0.024 AUC**, bands-alone Δ = **−0.103 AUC**,
per-participant median Δ = −0.066 with only 21 % of participants benefiting.
The ACT-R-flavored "evaluation is dwell-beyond-content-expected-baseline"
framing is falsified at AOI-summary granularity, with a methodological
caveat that the baseline's participant fixed effects absorb the variance
where the signal lives — so the null is partly tautological under this
specific protocol.

## What was run

Notebook: [`notebooks-v2/29_content_residualized_bands.ipynb`](../../notebooks-v2/29_content_residualized_bands.ipynb)
(18 cells, executed).

Subset: approached-not-clicked AOIs (min_dist < 100 px and NOT clicked) on
AdSERP, n = 2,351, 47 LOSO participants. Post 2026-04-12 coordinate-space
audit. Target label: NB22 gaze-regression (1 = deferred, 0 = evaluated-
rejected).

Content features per (trial, position):
- `token_count` — space-split tokens in title + snippet
- `char_count` — characters in title + snippet
- `ttr` — type–token ratio
- `query_cosine` — cosine(result_embedding, query_embedding), both 1,024-dim
  `mxbai-embed-large` from `AdSERP/data/{serp,query}-embeddings.json`
- `centroid_novelty` — 1 − cosine(result_embedding, trial_SERP_centroid)

Baseline: ordinary least squares fit of `log1p(vp_band_ms) ~ content +
one-hot(rank) + one-hot(participant)`. Residual = observed log1p dwell
minus predicted.

Classifier: LOSO LR (47 folds) with `class_weight='balanced'`, comparing
seven feature sets — retreat alone, bands_raw alone, bands_residualized
alone, content alone, retreat + bands_raw, retreat + bands_residualized,
retreat + bands_raw + content.

## Numbers

### Expected-duration baseline R² (OLS, log1p target)

| Target | content only | content + rank | content + rank + participant FE |
|---|---|---|---|
| vp_top_ms | 0.019 | 0.273 | 0.371 |
| vp_mid_ms | 0.025 | 0.448 | 0.467 |

Content features explain **≤ 2.5 % of band-dwell variance alone**. Adding
rank dummies jumps R² to 27–45 %; adding participant FE pushes it to
37–47 %. Dwell is governed by *where on the page* and *who's doing the
reading*, not by *what the content is like*.

### Content coefficients (log1p vp_top_ms, standardized)

| Feature | vp_top_ms | vp_mid_ms |
|---|---|---|
| token_count | −0.251 | +0.373 |
| char_count | +0.090 | −0.066 |
| ttr | +0.313 | −0.085 |
| query_cosine | +0.216 | −0.439 |
| centroid_novelty | +0.019 | −0.018 |

Sign flips across bands for most features. At the level where content could
theoretically affect dwell, it does not have a stable directional effect.

### Classifier AUC (LOSO, deferred vs evaluated-rejected)

| Model | AUC |
|---|---|
| retreat alone | 0.792 |
| bands_raw alone | 0.799 |
| **bands_residualized alone** | **0.696** |
| content alone | 0.512 |
| retreat + bands_raw | 0.837 |
| **retreat + bands_residualized** | **0.813** |
| retreat + bands_raw + content | 0.834 |

Δ (retreat + residualized) − (retreat + raw) = **−0.024 AUC**.
Δ bands_residualized_alone − bands_raw_alone = **−0.103 AUC**.

### Per-participant (34 of 47 meet ≥ 5-per-class threshold)

- Median raw-bands held-in AUC: 0.872
- Median residualized-bands held-in AUC: 0.809
- Median Δ: **−0.066** (residualization hurts for the median participant)
- Fraction of participants where residualization helped (Δ > 0): **21 %**

## Why it's a null

Two reasons, one mechanistic and one methodological.

**Mechanistic (the actual finding).** Viewport-band dwell is not governed
by content complexity at AOI-summary granularity. Users don't spend
proportionally longer with semantically dense snippets or shorter with
familiar ones. Dwell is dominated by rank (where in the SERP the AOI is)
and by participant (their reading pace / strategy). The ACT-R-flavored
"dwell = baseline content time + engagement residual" intuition does not
hold at this aggregation level. What *does* generalize from this signal
is the geometric facts: top-of-viewport residence, not content-adjusted
residence.

**Methodological caveat (do not over-interpret the null).** The baseline
regression includes participant fixed effects, which absorb the between-
participant variance. Since 97 % of participants have positive `vt_top`
coefficients (per NB28:K12) and the signal's strength is partly a between-
participant magnitude phenomenon, subtracting the FE removes much of what
the calibration is detecting. The null is therefore partly tautological:
we subtracted the variance the signal lives in, then asked whether the
content-explained component was predictive.

A cleaner test would drop participant FE from the baseline and check
whether content alone explains any dwell variance *above rank*, then
residualize and re-test. Prediction: that version will also null (because
content R² is 1.9 % / 2.5 % without FE in the model too), but the test
would separate "content is irrelevant" from "FE consumed the signal."
Filed as follow-up; not blocking for the CIKM paper because the *direction*
of the Δ is robust — the residualization does not help, regardless of FE.

## What was learned anyway

1. **The viewport-band signal is content-invariant.** This is a *desirable*
   property for a calibration claim: the feature generalizes across corpora
   of differing content profiles. A reader encountering the feature on a
   different dataset does not need to rebuild a content model before using
   it.
2. **Snippet-complexity features are not a confound** for the bands-vs-
   retreat comparison. If content were driving band dwell, the combined
   AUC gain could be attributed to content-complexity information leaking
   through bands — but content-alone AUC is 0.512 (chance), so it cannot
   be. The +0.04 combined-vs-retreat gain survives this confound check.
3. **The NB29 content feature set is weak.** All five features combined
   reach 1.9–2.5 % R² on band dwell, not enough to be a baseline for
   anything. A stronger content model — Flesch readability, per-result
   attention-grabbing features (prices, numerics, brand recognition), or
   the serp-embedding space used for semantic novelty — might surface a
   non-null. Treated as low-priority follow-up.

## Pointers

- Notebook: `notebooks-v2/29_content_residualized_bands.ipynb`
- Key Claims JSON: `scripts/output/viewport_time_calibration/nb29_key_claims.json`
- Build script (gitignored): `notebooks-v2/_build_nb29_content_residualization.py`
- Related positive result: NB28 viewport-bands calibration (`notebooks-v2/28_viewport_bands.ipynb`)
- Related null (different target + different dwell signal): `docs/null-findings/2026-04-15-novelty-baseline-residual-redundancy.md` — Peter
  Dixon-Moses's earlier residualization idea applied to gaze-fixation dwell
  for click prediction; also null. NB29 is the viewport-bands × deferred/
  rejected version, hit-the-same-direction.
- Companion doc: `approach-retreat/docs/validation/viewport-bands-calibration.md`
  (library-side summary of what the *positive* calibration gives us).

## Framing caveat for anyone citing NB29

Do not cite as "content does not predict deferral." The target is
*deferred-vs-evaluated-rejected*, and content alone reaches AUC 0.512 —
chance. The honest claim is narrower: **content complexity (at the
five-feature granularity tested here) does not residualize viewport-band
dwell in a way that improves deferred/rejected discrimination**. Whether
richer content features, a different dwell signal, or a different target
would null is an open question.
