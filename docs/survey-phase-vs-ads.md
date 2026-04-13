# Survey Phase vs Ad Locations — Ad Mapping or Gist Formation?

*Computed by `scripts/analyze_survey_vs_ads.py` on 2,768 of 2,776 AdSERP trials (8 skipped for <2 in-column fixations or missing data). Outputs under `scripts/output/survey_vs_ads/`. Coordinate convention per `notebooks-v2/data_loader.py`: FPOGX/FPOGY and ad rects are both document/page-space after the 2026-04-12 audit. Ad rectangles are `dd_top` and `native_ad` only, clipped to the result column x ∈ [162, 702]; `dd_right` is excluded.*

*Scope: a 7-test reanalysis of the OSEC Survey phase asking whether its characteristic saccade-amplitude compression and fixation placement are consistent with ad-mapping-for-avoidance, gist formation, or both. NB13 defines Survey as saccades 1–5 (K = 5 fixations); we replicate at K = 3/5/7 to check sensitivity. Cohorts:*

- *`ad_top`: n = 1,580 trials with ≥ 1 `dd_top` ad rect in-column*
- *`plain_top`: n = 1,188 trials with 0 `dd_top` rects (most still carry `native_ad` rects lower on the page)*
- *`no_any_ad`: n = 52 trials with neither `dd_top` nor `native_ad` (degenerate for this analysis; reported only for completeness)*

---

## 1. Base rate — how much of the SERP column is ad?

For each trial, we compute `ad_area_frac` = (sum of `dd_top + native_ad` rect area clipped to the result column) / (result-column width × per-trial Y extent spanned by fixations and ad rects). This is the null p(fixation on ad) under a uniform fixation model.

| cohort | n_trials | median ad_area_frac | IQR | mean ad_area_frac |
| --- | ---: | ---: | ---: | ---: |
| all | 2,768 | 0.275 | 0.203 – 0.315 | 0.257 |
| ad_top | 1,580 | 0.293 | 0.241 – 0.330 | 0.297 |
| plain_top | 1,188 | 0.193 | 0.168 – 0.244 | 0.205 |

**Interpretation:** A random fixation thrown at the result column has a ~26% chance of landing inside an ad. On ad-top trials it is 30%, on plain-top trials 21%. Baseline is the number every Survey rate must beat.

---

## 2. Survey-phase vs Evaluate-phase fixations on ads

For each trial we partition in-column fixations into Survey (first K) and Evaluate (K+1..last). Corpus-wide rates are reported fixation-weighted (pool all fixations, then divide) and trial-weighted (mean of per-trial fractions). K sensitivity is in §2.3.

### 2.1 K = 5 (NB13-canonical Survey window)

| cohort | n_trials | p_ad_survey (fix-wt) | p_ad_eval (fix-wt) | ratio S/E | ratio S/base_rate | median survey_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 2,768 | 0.512 | 0.260 | 1.97 | 1.99 | 1,122 ms |
| ad_top | 1,580 | 0.726 | 0.343 | 2.12 | 2.45 | 1,078 ms |
| plain_top | 1,188 | 0.227 | 0.133 | 1.70 | 1.10 | 1,228 ms |

Fixation-weighted and trial-weighted rates agree to within 0.003 for every cohort (see `summary_k5.csv`), so no dilution effects from trial-size heterogeneity.

### 2.2 Per-trial paired comparison, K = 5

For every trial with ≥ 1 Survey fixation and ≥ 1 Evaluate fixation we compute `diff = p_ad_survey − p_ad_evaluate` and run a paired Wilcoxon signed-rank test.

| cohort | n | mean diff | frac trials S > E | Wilcoxon p |
| --- | ---: | ---: | ---: | ---: |
| all | 2,749 | +0.262 | 63.6% | 4.9 × 10⁻²³² |
| ad_top | 1,579 | +0.386 | 86.4% | 9.8 × 10⁻²⁰³ |
| plain_top | 1,170 | +0.095 | 32.8% | 2.3 × 10⁻²¹ |

### 2.3 K sensitivity (cohort `all`, fixation-weighted)

| K | p_ad_survey | p_ad_eval | ratio S/E | ratio S/base |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 0.517 | 0.267 | 1.94 | 2.01 |
| 5 | 0.512 | 0.260 | 1.97 | 1.99 |
| 7 | 0.489 | 0.255 | 1.92 | 1.90 |

**Interpretation of §2:** Survey fixations over-index on ads by a factor of ~2 corpus-wide and ~2.45 on ad-top trials, stable across K = 3/5/7. The effect is driven almost entirely by the ad-top cohort: 86% of ad-top trials place more Survey than Evaluate fixations on ads. On plain-top trials the S/E ratio drops to 1.70 but the base-rate ratio is only 1.10 — meaning Survey on plain-top trials is essentially at chance with respect to ad coverage. The ad-top effect (+0.386) is four times larger than the plain-top effect (+0.095) and is what produces the corpus-level signal.

---

## 3. Does Survey exist on plain-top trials at all?

If Survey is a stable cognitive stage independent of ad presence, its saccade-amplitude compression signature should appear on plain-top trials too. Per-cohort mean saccade amplitude by ordinal index (first 20 saccades) from `saccade_amplitude_profile.csv`:

| saccade | all (mean px) | plain_top (mean px) | ad_top (mean px) |
| ---: | ---: | ---: | ---: |
| 1 | 150.3 | 159.0 | 143.7 |
| 2 | 159.1 | 178.8 | 144.2 |
| 3 | 151.5 | 162.1 | 143.5 |
| 4 | 129.7 | 136.1 | 124.9 |
| 5 | 126.8 | 129.1 | 125.1 |
| 6 | 118.9 | 123.3 | 115.6 |
| 10 | 122.9 | 119.7 | 125.2 |
| 20 | 119.6 | 120.1 | 119.2 |

Saccade 1–3 amplitudes on plain-top (159–179 px) are actually **wider** than on ad-top (144 px), and both cohorts compress to a steady ~120 px baseline by saccade 6. Survey median duration is 1,228 ms on plain-top and 1,078 ms on ad-top — plain-top Survey is **longer**, not shorter. The amplitude-compression signature reproduces on both cohorts.

**Interpretation:** Survey exists, and is at least as pronounced, on trials where there is no `dd_top` ad to avoid. The phase is not ad-contingent.

---

## 4. Saccade endpoint proximity to ad rectangles

For every Survey and Evaluate fixation we compute signed distance to the nearest ad-rect edge (negative = inside). Per-trial median, then median across trials.

| cohort | K | median d_to_ad Survey (px) | median d_to_ad Evaluate (px) |
| --- | ---: | ---: | ---: |
| all | 5 | −10 | +140 |
| ad_top | 5 | −45 | +86 |
| plain_top | 5 | +1,106 | +645 |

Negative-signed medians mean the median Survey fixation is **inside** an ad rect on the ad-top cohort (−45 px penetration). Evaluate fixations sit 86 px outside the nearest ad edge on the same cohort. On plain-top trials the Survey median is 1,106 px *away* from the nearest (native) ad, because native ads tend to live mid-to-lower page and Survey fixations cluster near the top.

**Interpretation:** On ad-top trials the first 5 fixations routinely land **inside** the top-ad rectangle rather than near its edge. This is a "land-on" pattern, not a "skirt-along" pattern. Ad-mapping in the sense of *circumscribing* an ad would predict fixations at the boundary; these land in the middle.

---

## 5. First-fixation location

Per-trial, where does fixation 0 sit relative to the nearest ad?

| cohort | n | % inside any ad | % within 50 px of edge | % > 200 px from edge | median d_to_ad (px) |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 2,768 | 39.5% | 15.4% | 24.1% | 33 |
| ad_top | 1,580 | 54.1% | 18.7% | 1.2% | −7 |
| plain_top | 1,188 | 20.1% | 10.9% | 54.5% | 942 |

On ad-top trials, more than half of all trials start with the very first fixation inside a `dd_top` rectangle. On plain-top trials, only 20% do — and 55% land more than 200 px from any ad.

But: the **median first-fixation Y** is 182.5 px on ad-top and 170 px on plain-top (from `per_trial.csv`), and 96% of trials in both cohorts have first_fix_y < 500 px. The first fixation goes to the top of the page regardless of ad presence. On ad-top trials, "the top of the page" simply happens to be occupied by a `dd_top` ad.

**Interpretation:** First-fixation-inside-ad rates on ad-top trials are a geometric artifact of top-of-page landing combined with top-of-page ad placement. The same "land near y = 170" behavior on plain-top lands 942 px from any ad. Both readings (attention capture by ad; reading-start at page top) fit the ad-top number; the plain-top number falsifies the strong "ad magnetism" reading — if first fixations were actively drawn to ads, plain-top trials would show lower first_fix_y scatter hunting for native ads further down, and they don't.

---

## 6. Per-trial ad count × Survey length

Spearman ρ between per-trial ad count (`dd_top + native_ad` in-column) and Survey-phase duration or fixation count at K = 5:

| cohort | n | ρ(n_ads, survey_ms_K5) | p | ρ(n_ads, n_col_fix) | p |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 2,768 | −0.005 | 0.81 | +0.019 | 0.31 |
| ad_top | 1,580 | −0.032 | 0.21 | +0.040 | 0.12 |

**Interpretation:** Survey length is uncorrelated with ad count. Adding a fifth native-ad rect to a trial does not extend Survey duration. An ad-mapping-for-avoidance model predicts a positive correlation (more ads to map → more mapping time); the observed ρ is indistinguishable from zero, with the sign slightly negative.

---

## 7. Directional evidence summary

- **Survey over-indexes on ads by ~2× corpus-wide and ~2.45× on ad-top trials** (p_ad_survey ≈ 0.51 vs base 0.26, K-stable). The effect is real and strong.
- **The effect is almost entirely carried by ad-top trials.** On plain-top trials the Survey-over-base ratio is 1.10 (near chance). 86% of ad-top trials vs 33% of plain-top trials show Survey > Evaluate on ad rates. Whatever Survey is doing on ad-top trials, it is not doing on plain-top trials.
- **Survey's saccade-compression signature exists on plain-top trials.** Saccade-1 amplitude is actually wider on plain-top (159 px vs 144 px), and both cohorts converge to a steady ~120 px by saccade 6. Plain-top median Survey duration (1,228 ms) is longer than ad-top (1,078 ms). The stage is not ad-contingent.
- **First-fixation placement is y = 170–180 px on both cohorts.** The 54% "first-fixation-inside-ad" number on ad-top is a geometric consequence of reading-start behavior meeting top-of-page ad placement, not evidence of attention capture by the ad. If gaze were hunting ads, plain-top first-fixations would chase native ads and they don't.
- **Survey duration is uncorrelated with ad count** (Spearman ρ = −0.005, p = 0.81). Trials with more ads do not spend more time in Survey. Ad-mapping-for-avoidance predicts the opposite.
- **Median Survey fixation on ad-top trials is 45 px *inside* the nearest ad rect**, not at its edge. Boundary-skirting (the geometric signature of "avoiding" an ad) is absent; fixations land in the middle of the rect.

---

## 8. Takeaway question for interpretation

The numbers above are not a verdict. They map out which hypothesis each measurement is consistent with. The reader — paper author, reviewer, Andy — has to decide which reading to prefer. The two candidate readings:

**(A) Gist formation.** Survey is a stable early scanning phase whose function is to build an impression of the result set before committing to reading. Predicts: Survey exists regardless of ad presence (yes: §3), compresses from wide to narrow (yes: §3), does not scale with ad count (yes: §6), first-fixation goes to the page-top reading start (yes: §5). Does not straightforwardly predict: Survey fixations over-indexing 2.45× on ads on ad-top trials (§2, §4).

**(B) Ad-mapping-for-avoidance.** Survey is a subroutine for locating ads early so the user can route around them. Predicts: Survey fixations land on/near ads (yes on ad-top, §2 and §4), on-ad rate rises when ads are present (yes, §2.1 ad-top vs plain-top). Does not predict: Survey exists on plain-top trials with essentially the same amplitude profile (§3 contradicts), Survey duration flat in ad count (§6 contradicts), first fixations at y ≈ 170 regardless of whether an ad is there (§5 contradicts), fixations landing *inside* rather than *at the edge of* ads (§4 contradicts).

**(C) Attention capture by the top ad.** A third reading worth naming: not deliberate mapping, not gist formation, but the dd_top ad being visually salient enough that the reading-start fixation and the next few saccades get pulled into it. This is consistent with every number in §2–§5 on the ad-top cohort and is consistent with the §3 plain-top results (no ad to capture → Survey still runs, just not on an ad). It also fits §6 (capture is a one-shot event, not a mapping routine that scales).

The numbers mildly favor a **gist-formation base stage modulated by top-ad capture on ad-top trials**. (A) alone under-predicts the §2 ad-top effect. (B) alone is falsified by §3, §5, and §6. A mixture where Survey is structurally a scanning stage (A) that gets hijacked by `dd_top` salience (C) reproduces every number in the memo.

### What would further tip the verdict

- **First-saccade-direction analysis.** On ad-top trials, does the first saccade away from the `dd_top` land back on the ad, skirt around it, or jump past it into organic territory? Deliberate mapping would make the second saccade a *different* ad location; capture-plus-escape would put the second saccade on the first post-ad organic result.
- **Survey on `dd_top` ranks vs visually-matched organic-top controls.** If the AdSERP corpus contains enough trials where the top slot is a visually-prominent organic result (shopping card, knowledge panel), compare Survey rates on those. If they also attract ~54% first fixations, the effect is about visual prominence of the top slot, not ad-specific salience.
- **Per-participant variance.** Is the on-ad Survey rate bimodal (some participants avoid, some get captured), or unimodal? Bimodality would complicate both readings and suggest strategy heterogeneity.
- **Cursor-gaze lag within the Survey window.** If mouse leads gaze into `dd_top` early, deliberate (motor-planned approach). If gaze leads and the cursor never enters, pure visual capture without behavioral engagement.

*Numbers only. No interpretation fights in this memo; those belong in the paper body.*
