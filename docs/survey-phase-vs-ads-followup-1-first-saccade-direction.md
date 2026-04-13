# Survey Phase Follow-up #1 — First-Saccade Direction

*Computed by `scripts/analyze_first_saccade_direction.py` on 2,774 of 2,776 AdSERP trials (2 skipped for <2 fixations; 53 more lack ad-boundary JSON and are reported without ad-angle metrics). Outputs under `scripts/output/first_saccade_direction/`. Coordinate convention per `notebooks-v2/data_loader.py`: FPOGX/FPOGY and ad rects are page-space (post-2026-04-12 audit). Ad rects = `dd_top + native_ad` clipped to result column x ∈ [162, 702]; `dd_right` excluded.*

*Scope: follow-up to `survey-phase-vs-ads.md` §8. Question: does the vector from fixation 0 to fixation 1 carry any systematic bias toward detected ad rectangles beyond what page geometry already implies? Cohorts (from `trial_snapshot.csv`): `plain_top` n = 775, `ad_top` n = 1,999 (any top-area ad; wider than the prior memo's dd_top-only cut).*

---

## 1. θ₀ distribution (Test A)

Angles are page-coordinate: 0° = rightward, 90° = downward. Fractions in each 30° bin:

| bin | direction | plain_top | ad_top |
| --- | --- | ---: | ---: |
| 60–90 | down-right | 0.141 | 0.126 |
| 90–120 | down / down-left | 0.120 | 0.149 |
| 120–150 | down-left | 0.146 | 0.179 |
| **150–180** | **down-left / left** | **0.161** | **0.207** |
| 180–210 | left / up-left | 0.088 | 0.083 |
| all other bins combined | other | 0.344 | 0.256 |

Circular mean θ: 120.0° (plain_top) vs 131.5° (ad_top). Resultant length R: 0.385 vs 0.500 — ad_top is more concentrated. Modal bin is **150–180° (down-left) for both cohorts** — i.e. a reading-return sweep (finish the first line, drop and return left for the next slot). Neither cohort shows a secondary mode in any ad-specific direction. Ad_top is a *tightened* version of the same shape, not a different shape.

## 2. Angular distance to nearest ad — split by fix-0 containment (Test B)

Because fix 0 sits *inside* an ad rect on 46% of ad_top trials, the geometry of "angle to nearest edge" flips, and the test has to be split:

| subgroup | n | obs median angdiff | null median (shuffle) | p(null ≤ obs) |
| --- | ---: | ---: | ---: | ---: |
| ad_top pooled | 1,988 | 71.6° | 82.1° [79.0–85.0] | 0.000 |
| ad_top \| fix 0 **outside** | 1,068 | 35.1° | 46.8° | 0.000 |
| ad_top \| fix 0 **inside** | 920 | 125.7° | 110.0° | **1.000** |
| plain_top control | 721 | 60.6° | — | — |

Three things:

1. **plain_top has the smallest median angdiff (60.6°)** even though plain_top has no top ad. 91% of plain_top "angle to nearest ad" values are in the 90° bin — the native ad sits straight below, and the reading-start first saccade goes straight-ish down. "Ad alignment" here is pure page geometry.
2. **ad_top-outside (35°)** is *better-aligned* than plain_top, but for the same reason. Fix 0 is at y ≈ 170, dd_top sits at y ≈ 158–258, any downward saccade is trivially close to the "direction to nearest ad" vector. Significance vs shuffle is real, but it's geometry, not targeting.
3. **ad_top-inside (125.7°) is worse than its null (110.0°)**, p = 1.000. When fix 0 is already inside a top ad, the first saccade points systematically *away* from the nearest edge. Median r₀ = 120 px but median distance to nearest edge = only 40 px, and **76% of inside-ad trials exit the rect on saccade 1**. The eye does not dwell on the ad and does not skirt its boundary; it pushes through.

## 3. First-saccade magnitude (Test C)

| cohort | n | median r₀ | mean r₀ |
| --- | ---: | ---: | ---: |
| plain_top | 775 | 119.1 px | 148.8 px |
| ad_top | 1,999 | 125.4 px | 151.9 px |

Permutation test on median difference: Δ = −6.3 px, p = 0.31. **No significant difference.** The prior memo's "159 vs 144" numbers came from mean amplitude at Survey ordinal 1 on a slightly different cohort definition; on a like-for-like fix 0 → fix 1 comparison the gap disappears. A "jump to the ad" mechanism would predict a *longer* saccade-1 on ad_top; there is no such signal.

## 4. dd_top block depth (Test D)

dd_top rects always sit at y ∈ [158, 258] px — they never move below the first-screen fold, so "upper vs lower" is degenerate. We substitute block depth using `first_org_abs`:

| stratum | n | mean θ | down_frac (60–120°) | median angdiff | median r₀ |
| --- | ---: | ---: | ---: | ---: | ---: |
| shallow_top (1 top ad) | 991 | 129.5° | 0.297 | 70.8° | 118.7 px |
| deep_top (2–3 top ads) | 1,008 | 133.4° | 0.252 | 72.2° | 134.5 px |

deep_top's first saccade is slightly longer (+15.8 px median) and more down-left. If a deeper ad block were pulling saccade 1 onto itself, down_frac would *rise* — instead it drops by 4.5 pp. Deeper ad block → more pixels to traverse before the saccade clears the ad region, not more saccades aimed at the ad region.

## 5. Verdict

**First-saccade direction does not carry evidence for active ad detection**, and removes one candidate mechanism cleanly:

- **Reading-return sweeps, not ad jumps.** The modal first saccade on both cohorts is down-left (150–180°). No cohort-specific secondary mode. Same shape, slightly tighter on ad_top.
- **When fix 0 is already inside a top ad, saccade 1 exits the rect 76% of the time** and points *away* from the nearest edge (p = 1.000 vs shuffle). That is the opposite of both "dwelling on the ad" and "hugging its boundary."
- **Saccade-1 length is the same on plain_top and ad_top** (Δ = −6.3 px, p = 0.31). No "jump to the ad" signature.

The apparent "ad-directedness" of saccade 1 on ad_top-outside trials is a page-geometry artifact: dd_top lives directly below the reading-start fixation, and plain_top's even smaller median angdiff (with no top ad present) demonstrates the same effect on the native ads that sit further down.

This supports the prior memo's **(A) gist formation + (C) passive capture** reading. Capture is a *landing* phenomenon — 54% of ad_top trials have fix 0 inside the dd_top rect — but it does not extend to the saccade-direction level. Once the reader is there, the next saccade leaves. If Survey were actively hunting ads, saccade 1 on inside-rect trials would re-fixate within the rect to enumerate it, or hug the boundary to map it. It does neither. This moves the question modestly: saccade-level ad-detection is ruled out, landing-level salience capture is untouched.
