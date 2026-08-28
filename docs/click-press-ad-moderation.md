# Click press duration: top-ad surface moderation and ad-utility segmentation

**Date:** 2026-08-22  
**Regime:** `[LAB, AdSERP, typed_gapfill]`  
**Source:** `scripts/click_press_ad_segmentation.py` →
`scripts/output/click_press_ad_segmentation/{summary.json,report.md}`  
**Status:** theoretically motivated exploratory follow-up; the overall
first-forward versus regressive-return press-duration effect remains null.

**Multiplicity disclosure.** No confirmatory test family was registered before
this follow-up. The `dd_top`, `native_ad`, pooled-paid, user-prior, and DOM-node
decompositions were inspected together; bootstrap *p*-values are descriptive.
The `dd_top` interaction clears a three-surface Bonferroni threshold
(.05/3 = .0167) but not a maximally conservative correction over every model
reported here. Threshold stability strengthens the candidate, but those six
sensitivity fits are not independent replications.

## TL;DR

The overall mouse-button hold does not distinguish first-forward from
regressive-return clicks, but clicked **surface type moderates the contrast**.
After participant and exact display-rank control, regressive organic clicks are
estimated at +2.9% relative to first-forward (95% CI −4.1% to +9.1%), whereas
regressive `dd_top` clicks are **−7.1% shorter** (95% CI −14.3% to −1.7%). The
pass × `dd_top` contrast is **−9.8%** (95% CI −17.2% to −2.3%, participant-
cluster bootstrap *p* = .009) and survives all six target-recency/maximum-hold
threshold combinations. `native_ad` does not reproduce it.

The existing pre-decision ad-utility segmentation is directionally relevant
but not confirmed as the moderator: on ad clicks, the regressive effect changes
by +5.35% per +0.10 in `p_ad_survey`, but the 95% CI is −2.52% to +10.10%
(*p* = .140). Link/DOM node type cannot be interpreted independently because
it is nearly aliased with AOI type.

## Surface decomposition

Pooled and participant-paired descriptives:

| clicked surface | first n / median | regressive n / median | paired participants | participant median Δ | paired *p* |
|---|---:|---:|---:|---:|---:|
| organic | 166 / 103 ms | 1,059 / 110 ms | 38 | +6.0 ms | .473 |
| paid (`dd_top` + `native_ad`) | 55 / 101 ms | 257 / 112 ms | 18 | −2.75 ms | .486 |
| other widget | 11 / 109 ms | 44 / 106 ms | 8 | +3.5 ms | .969 |

Pooling paid surfaces conceals the result. Participant-demeaned log-duration
models with categorical `typed_gapfill` display-rank fixed effects show:

| contrast | estimate | participant-bootstrap 95% CI | *p* |
|---|---:|---:|---:|
| regressive effect on organic | +2.92% | [−4.10%, +9.10%] | .460 |
| regressive effect on `dd_top` | **−7.13%** | **[−14.28%, −1.75%]** | **.010** |
| pass × `dd_top` relative to organic | **−9.77%** | **[−17.20%, −2.32%]** | **.009** |
| pass × `native_ad` relative to organic | +11.13% | [−8.88%, +51.19%] | .339 |
| pass × pooled-paid relative to organic | −4.81% | [−12.85%, +3.90%] | .215 |

The `dd_top` interaction stays negative in all threshold sensitivities:

| target recency | maximum hold | interaction |
|---:|---:|---:|
| 0.5 s | 0.5 s | −8.72%, CI [−16.26%, −1.88%] |
| 0.5 s | 1.0 s | −10.57%, CI [−17.70%, −3.52%] |
| 1.0 s | 0.5 s | −9.56%, CI [−17.04%, −2.78%] |
| 1.0 s | 1.0 s | −11.53%, CI [−19.03%, −4.45%] |
| 1.5 s | 0.5 s | −8.83%, CI [−16.29%, −2.24%] |
| 1.5 s | 1.0 s | −9.77%, CI [−17.25%, −2.38%] |

This is a conditional interaction, not a resurrection of the overall pass
effect. The participant-paired `dd_top` cell by itself has only 11 paired
participants and is null; the model gains precision by using the repeated
within-participant observations while controlling exact display rank.

## Existing ad-utility user segmentation

The join uses the canonical **pre-decision** segmentation from
[`ad-utility-prior.md`](ad-utility-prior.md): terciles of `p_ad_survey`, the
fraction of survey-phase fixations landing on ads. It does not define the
cohorts from the current click outcome.

| ad-prior tercile | all: first / regressive median | participant median Δ | ad only: first / regressive median | ad participant Δ |
|---|---:|---:|---:|---:|
| low | 86 / 109 ms | +1.75 ms | 85 / 117 ms | −7.25 ms |
| mid | 95 / 109 ms | −7.5 ms | 95 / 110 ms | −5.5 ms |
| high | 117 / 118 ms | +10.0 ms | 117 / 117 ms | +7.75 ms |

The low/mid-to-high sign change is theoretically suggestive: high ad-prior
participants do not show the same compressed regressive-ad motor signature.
But the continuous, rank-controlled test is not resolved at this sample size:

| subset | pass × `p_ad_survey`, per +0.10 | 95% CI | *p* |
|---|---:|---:|---:|
| all clicks | +0.37% | [−3.22%, +4.49%] | .848 |
| organic clicks | −1.67% | [−6.35%, +3.39%] | .423 |
| paid clicks | +5.35% | [−2.52%, +10.10%] | .140 |
| `dd_top` only | +4.49% | [−1.49%, +8.18%] | .120 |
| `native_ad` only | +10.46% | [−75.28%, +89.19%] | .392 |

The defensible claim is therefore **surface moderation**. The user-segment
interaction is a pre-specified replication target: on a larger sample, test a
single `pass × dd_top × p_ad_survey` interaction rather than rediscovering the
tercile pattern post hoc.

### Temporal-separation test

As a stricter within-cohort check, `p_ad_survey` was estimated only from blocks
1–3 and used to predict press behavior only in blocks 4–6. The outcome model
was restricted to organic and `dd_top` clicks and included participant
demeaning, categorical display-rank fixed effects, and the complete lower-order
hierarchy for `pass × dd_top × prior`.

The early prior itself is stable: early versus late `p_ad_survey` has Spearman
ρ = .745 (participant-bootstrap 95% CI [.550, .861], *p* = 1.93×10⁻⁹). The
motor moderation, however, is not resolved. The three-way interaction is
+8.80% per +0.10 in early prior (95% CI [−3.74%, +23.81%], cluster-bootstrap
*p* = .142). Its direction matches the full-session exploratory pattern, but
the late outcome contains only 21 first-forward `dd_top` clicks. Early prior
also does not significantly predict late `dd_top` click share (ρ = .211,
*p* = .155).

Across nine survey-K/block-cutoff sensitivity fits, all three-way point
estimates are positive (+2.8% to +16.6%), but every interval crosses zero.
This is **not a successful temporal confirmation**: it shows that the gaze
segmentation persists across the session while leaving its proposed motor
consequence uncertain. A new cohort with this one three-way model fixed in
advance is the appropriate next test.

## Link/DOM target type

The terminal evtrack XPath ends at `h3` for 1,167 clicks, `span` for 283,
`div` for 65, an ID-only wildcard for 59, and `cite` for 16. This is not an
independent link-type manipulation:

- **86.9% of `span` targets are paid ads** (179 `dd_top`, 67 `native_ad`);
- **96.1% of `h3` targets are organic** (1,122/1,167).

The raw node comparison is therefore an alternate encoding of clicked AOI
type. It cannot tell whether the shorter regressive `dd_top` hold is caused by
ad utility, the visual/link affordance, or both. A DOM-normalized design in
which the same node affordance appears on paid and organic cards is needed to
separate them.

## Theoretical read

The narrow observation is compatible with a **surface-specific commit mode**:
returning to a top direct-display ad ends in a more abbreviated physical
commit than returning to an organic result. The effect is absent for native
in-stream ads, so it is not a generic “ad click” property. `dd_top` combines
top-of-page placement, a distinct visual template, strong prior visibility,
and commercial utility; this dataset cannot identify which component is
causal.

The ad-utility segmentation offers a sharper future hypothesis: high-prior
users may treat `dd_top` as an evaluated alternative on return, while low-prior
users may use it as a fast opportunistic exit. The current segment interaction
does not clear its uncertainty interval, so this remains theory for
replication—not an established mechanism.

### Peripheral-attention mechanism check

A fixed-window, strictly peripheral PAI follow-up does not explain the surface
lead. On the 1,578 clicks with positive pre-press PAI mass, the pass × `dd_top`
contrast changes only from −6.77% before PAI terms to −6.34% after adding
geometry competition, clicked-target PAI share, and strict binary-dwell share.
The PAI competition × pass interaction itself is −0.21%, CI [−4.78%, +5.69%].
This is a mechanism null on a slightly reduced, more controlled sample—not a
replacement estimate for the primary surface model. See
[`null-findings/2026-08-22-click-press-pai-conflict.md`](null-findings/2026-08-22-click-press-pai-conflict.md).

## Reproduce

```bash
.venv/bin/python scripts/click_press_latency_pass_analysis.py
.venv/bin/python scripts/click_press_ad_segmentation.py
.venv/bin/python scripts/click_press_prior_temporal_test.py
.venv/bin/python scripts/click_press_semantic_margin_analysis.py
.venv/bin/python scripts/click_press_pai_conflict_analysis.py
```
