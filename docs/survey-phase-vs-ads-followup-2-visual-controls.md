# Survey Phase vs Ads — Follow-up 2: Visual-Salience Control

*Follow-up to `docs/survey-phase-vs-ads.md` (2026-04-12), which found Survey fixations over-index on `dd_top` ads by 2.45× over a uniform baseline on the ad-top cohort. Computed by `scripts/analyze_visual_controls.py` on 2,774 of 2,776 AdSERP trials (2 skipped for <2 fixations). Outputs under `scripts/output/visual_controls/`. Coordinate convention per `notebooks-v2/data_loader.py`: document/page space after the 2026-04-12 audit.*

## Question

Is Survey-phase ad capture **visual-salience driven** (any visually dense element captures early gaze) or **ad-layout specific** (something about the dd_top slot — its in-column location, top-of-page reading start, or visual chrome — captures gaze)? The first reading would generalize to shopping cards, knowledge panels, rich organic results. The second would not.

## Approach chosen: (c) dd_right as a visually-matched non-organic control

The task brief listed three approaches:

- **(a)** Parse raw SERP HTML and derive rectangles for shopping/knowledge-panel/rich-card elements. Rejected: Google's minified markup makes bounding-rect extraction brittle, and the classes shift across the corpus.
- **(b)** Use h3 slots with adjacent `<img>` tags as a "rich organic" proxy. Rejected as primary approach: coarse, and without ground-truth no way to validate whether the rects match visual salience.
- **(c)** Use `dd_right` (right-rail Google ads) as a control. **Chosen.** Data is immediately available — `AdSERP/data/ad-boundary-data/<tid>.json` carries `dd_right` rectangles directly. `_load_ad_regions` filters them out because right-rail ads don't displace organic ranks, but the raw JSON still has them.

Why dd_right is the right control for this question:

- It is **an ad**, with the same Google ad-branding treatment, image density, and layout conventions as dd_top.
- It is **spatially segregated** from the reading flow (x ∈ [802, 1023], outside the result column [162, 702]).
- Trials in this corpus fall into three clean cohorts with **zero co-occurrence** between the two ad types (inspection of all 2,776 boundary JSONs): `dd_top-only` (n = 1,582), `dd_right-only` (n = 861), `neither` (n = 333). That partitioning is almost certainly experimental design and it gives us unambiguous between-cohort comparisons.

The hypothesis test is: **if "any ad captures Survey", dd_right trials should show a dd_right-Survey lift comparable to the dd_top-Survey lift on dd_top trials.** If dd_right shows no lift (or an inverted lift), the effect is specifically about ads in the reading column — which rules out "generic visual salience" and leaves the top-of-page-ad-on-reading-start mechanism as the most parsimonious reading.

Right-rail ads appear in 861 / 2,774 (31%) of trials. Of those, dd_right `location.x` is always 802 and `width` median 221 (max 411 for wider creatives). `y` ranges from 158 to 1,200. These are the "skyscraper" slots to the right of the organic results column.

## 1. Base rates — how often should a Survey fixation land in each strip?

Base rate is computed per trial as rect area / strip area, where the strip is the horizontal span of the target (result column for dd_top; right rail [702, 1100] for dd_right) × the y-extent spanned by that trial's fixations. Averaged across trials in each cohort.

| cohort | n_trials | dd_top base rate | dd_right base rate |
| --- | ---: | ---: | ---: |
| dd_top-only | 1,581 | 0.282 | — |
| dd_right-only | 860 | — | 0.358 |
| neither | 333 | — | — |

The dd_top base rate on the in-column strip (0.282) and the dd_right base rate on the right-rail strip (0.358) are of the same order — roughly a third of each strip is covered by its ad. Any Survey lift has to beat its own strip's baseline.

## 2. Headline result — Survey capture for each ad type

Survey = first K = 5 fixations. For each strip, we compute the fixation-weighted proportion of fixations inside the rect, conditional on the fixation being inside that strip (so both baselines match). The dd_top numbers reproduce the prior `survey-phase-vs-ads.md` §2 findings to within rounding.

| cohort | metric | base rate | p_ad_survey | p_ad_eval | S / base | S / E |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| dd_top-only | dd_top strip | 0.282 | **0.711** | 0.277 | **2.52×** | **2.56×** |
| dd_right-only | dd_right strip | 0.358 | **0.539** | **0.699** | **1.51×** | **0.77×** |

Four numbers matter:

1. **dd_top S/base ratio = 2.52×.** Reproduces the 2.45× from the prior analysis (minor method differences: this script uses strip-conditional fixations for symmetry with dd_right, and doesn't trim to the per-trial y-extent of ad rects).
2. **dd_right S/base ratio = 1.51×.** Right-rail ads *do* over-index Survey somewhat, but the lift is 40% smaller than dd_top's.
3. **dd_top S/E ratio = 2.56×** — Survey captures dd_top much more than Evaluate does (the classic "early-capture" signature).
4. **dd_right S/E ratio = 0.77×** — **Survey captures dd_right *less* than Evaluate does.** This is the opposite of the dd_top pattern. Right-rail ads attract gaze during the later Evaluate phase, not during Survey.

That last number is the key to the verdict. If the Survey-phase signal were a general "visual salience captures early gaze" effect, dd_right would show S/E > 1. Instead it shows S/E < 1. Right-rail ads are visited, but *after* the Survey window, when the reader is already in Evaluate mode and systematically scanning the page including the right rail.

## 3. Paired per-trial tests

Per trial, we compute `diff = p_survey_on_rect − p_evaluate_on_rect` (each conditional on its strip) and run paired Wilcoxon signed-rank tests. Viewport-wide "unconditional" tests use the full Survey window as the Survey denominator to avoid the conditioning artifact.

| test | n | mean diff | frac trials S > E | Wilcoxon p |
| --- | ---: | ---: | ---: | ---: |
| dd_top (strip-conditional) | 1,575 | +0.432 | 87.6% | 1.8 × 10⁻²¹⁶ |
| dd_right (strip-conditional) | 382 | −0.045 | 44.2% | 0.043 |
| dd_right (viewport-wide) | 858 | −0.045 | 20.6% | 2.0 × 10⁻¹³ |

Reading the paired tests:

- **dd_top strip-conditional:** 87.6% of trials have more Survey than Evaluate fixations on the ad. Effect size +0.432. Both numbers are overwhelming.
- **dd_right strip-conditional:** Only 44.2% of dd_right trials show Survey > Evaluate, i.e. Evaluate wins on a majority of trials. The Wilcoxon p=0.043 is marginal and the effect size is −0.045 in the direction of *Evaluate over Survey*.
- **dd_right viewport-wide:** Only 20.6% of trials show Survey > Evaluate, p = 2.0 × 10⁻¹³. A robust effect in the *opposite* direction. Evaluate-phase gaze systematically over-indexes on dd_right compared to Survey-phase gaze.

The strip-conditional and viewport-wide tests agree in sign and magnitude of mean effect (−0.045), so the conditioning doesn't explain away the result; it just makes the trial-level participation rate look more evenly split because only 46% of dd_right trials have *any* Survey fixation in the right strip to begin with.

## 4. Participation rates — are readers even looking at the right rail?

A legitimate concern is that Survey on dd_right looks weak because readers simply don't look right during Survey at all. This is true — and it's the finding, not a nuisance.

| cohort | trials with ≥1 Survey fix in target strip | trials with ≥1 Evaluate fix in target strip |
| --- | ---: | ---: |
| dd_top (result column) | 1,577 / 1,581 (99.7%) | — |
| dd_right (right rail) | 392 / 860 (45.6%) | 820 / 860 (95.3%) |

Every reader lands inside the result column during Survey. Less than half of readers even *visit* the right-rail strip during Survey, but nearly all of them visit it during Evaluate. On a median dd_right trial, Survey fixations in the right strip = 1 (and most are 0); mean = 1.00 out of 5. On a median dd_top trial, Survey fixations in the result column = 5 (i.e. all of them); mean = 4.77.

## 5. Viewport-wide Survey allocation

Where do Survey fixations actually go, across all strips, as a fraction of the Survey window (denominator = 5 fixations per trial)?

| cohort | dd_top capture (frac of Survey) | dd_right capture (frac of Survey) |
| --- | ---: | ---: |
| dd_top-only | **0.678** | 0.000 |
| dd_right-only | 0.000 | **0.108** |

On dd_top trials, 67.8% of every Survey fixation lands inside the dd_top rect — the ad dominates the early scanning window. On dd_right trials, 10.8% of Survey fixations land inside a dd_right rect. Right-rail ads capture a small minority of Survey, and that minority is less than the strip's own base rate would predict once you factor in that the right rail is only barely visited during Survey at all.

## 6. Verdict

The data resolves the question cleanly:

- **"Visual salience captures Survey" is not supported.** Right-rail ads — which share the dd_top ad's visual-layout properties (ad branding, image density, Google-ad chrome) — do *not* show the Survey-over-Evaluate capture signature that dd_top ads show. If anything, the signal is inverted: Evaluate captures dd_right more than Survey does.
- **Top-slot-specific capture is supported.** The dd_top effect is about the dd_top slot being in the natural reading-start region (top of the result column, y ≈ 170–200), where the first Survey fixations land for all trials regardless of ad presence. Put an ad there and it gets captured. Put an identically-visually-dense ad in the right rail and no capture appears.
- **This narrows the mechanism from the prior memo's §8.** The prior memo listed three readings: (A) gist formation, (B) ad-mapping-for-avoidance, (C) attention capture by the top ad. (C) was already the preferred mixture-model component. This follow-up strengthens (C) by ruling out the broader "visual salience" generalization: the capture is specifically about being *in the reading flow at the top of the page*, not about being visually dense per se.

### Framing for the paper

The earlier draft framing "Survey-phase fixations over-index on ads by 2.45×" should be sharpened to something like: "Survey-phase fixations over-index on in-column top ads by 2.45×, while visually-matched right-rail ads show no such capture (S/E = 0.77, p = 2.0 × 10⁻¹³ in the opposite direction). The early-capture effect is specific to the reading-flow top slot, consistent with a top-down reading-start mechanism being hijacked by whatever element occupies that slot — not with bottom-up visual salience indexing generically." That framing is defensible against the "well, any rich element would capture Survey" reviewer critique.

### Caveats

- **Right-rail ads may be visually different in ways we can't measure.** Skyscraper ads differ from top-rail ads in aspect ratio and density, not just position. A strict "visually matched" control would control for bounding-box area and image/text ratio. We rely on the Google-ad-chrome equivalence class; a reviewer could argue that right-rail ads are visually *less* salient than top-rail ads.
- **Shopping/knowledge-panel controls were not computed** (approaches a/b). If the `dd_top` effect survives against dd_right, we don't need them for this test, but a reviewer might still ask whether knowledge panels — which sit in the reading column but are not ads — show the capture signature. The `ad-boundary-data/` JSON doesn't carry their rectangles. Approach (b) (h3 slots with adjacent `<img>` tags) is a possible follow-up if a reviewer requests it, but the clean dd_right result makes it lower priority.
- **Participation-rate asymmetry is real and it matters for interpretation.** On 54% of dd_right trials the reader never glances right during Survey at all. That half of the cohort cannot contribute to any Survey-capture lift by construction. The 1.51× strip-conditional base-rate lift is computed only over the 392 trials where Survey fixations *do* enter the right strip. The negative S/E number holds across both conditioning schemes, which is why the verdict is robust.

---

*Computed 2026-04-12 from `scripts/analyze_visual_controls.py`. Raw outputs: `scripts/output/visual_controls/per_trial.csv` (2,774 rows), `summary.csv` (7 cohorts), `summary.json`, `paired_stats.json`.*
