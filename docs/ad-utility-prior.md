# Ad-utility prior — an individual-difference axis orthogonal to sat-opt

**Date:** 2026-05-04
**Stable ID:** F:ad-utility-prior
**Source:** `scripts/ad_utility_prior_analysis.py` → `scripts/output/ad_utility_prior/{summary.json, per_participant.csv}`
**Anchor for:** task-model paper (rank-value-prior framing, central premise); CIKM 2026 paper (worth premise candidate)
**Method spec:** [`methodology/gaze-prior-elicitation.md`](./methodology/gaze-prior-elicitation.md) frames this finding as the demonstration of a non-disruptive prior-elicitation protocol — three-layer leak structure (orient / survey / per-participant variance), McFadden floor + agent-specific overlay made directly observable.

---

## TL;DR

There is a measurable per-participant axis on **ad utility** — operationalized as the fraction of survey-phase fixations that landed on ads (the prior) and the fraction of clicks that landed on ad surfaces (the behavior) — that is independent of the satisficer / optimizer axis. Across 47 participants, ad-click rate ranges from 0% to 52.7% (median 13.2%, IQR [6.3%, 24.5%]); 16/47 participants (34%) click ads on ≥ 20% of trials. The pre-decision ad-attention rate predicts the ad-click rate (Spearman ρ = +0.30 on dd_top, *p* = 0.043) but is uncorrelated with regression rate (sat-opt: ρ = +0.02, *p* = 0.87) and trial-mean LHIPA (cognitive load: ρ = +0.13, *p* = 0.37). Ad-utility is a separate axis from sat-opt and from cognitive load — a third individual-difference dimension that the task-model paper's rank-value-prior framing has been pointing at.

---

## §1 The two measures

Per-participant **prior** (from `scripts/output/survey_bimodality/per_participant_with_traits.csv`, n=47):
- `p_ad_survey` — fraction of survey-phase fixations that landed on ads. Median **0.728**, IQR [0.640, 0.819], range [0.458, 0.935]. Every participant allocates substantial pre-decision attention to ads; the variance is in *how much*.
- `ad_over_index` — `p_ad_survey / area_share_ads`. Calibrates against the visible ad surface. Above 1.0 means the participant looks at ads more than their pixel-area share would imply.

Per-participant **behavior** (from `cursor-approach-features-typed.json` aggregated by participant, n=47):
- `p_ad_click` — fraction of all clicks landing on ad surfaces (`dd_top` + `native_ad` + `dd_right` combined). Median **0.132**, IQR [0.063, 0.245], **range [0.000, 0.527]**.
- `p_dd_top_click` — fraction of all clicks landing specifically on `dd_top` (top-of-page ads, the highest-CTR ad surface; population mean dd_top click rate is 17.1% per the cascade synthesis). Median **0.065**, max 0.397.
- `p_native_ad_click` — analogue for `native_ad`.

The prior is observable from gaze before any click; the behavior is the click outcome. Both span the full range from low to high.

## §2 Heterogeneity

Across the 47 participants, ad-click rate is genuinely heterogeneous:

```
zero-ad-clickers (p_ad_click = 0.000)      : 2 / 47    (4.3%)
low-ad-clickers (0.000 < p_ad_click < 0.10): 18 / 47   (38.3%)
moderate (0.10 ≤ p_ad_click < 0.20)        : 11 / 47   (23.4%)
high (0.20 ≤ p_ad_click < 0.40)            : 14 / 47   (29.8%)
very high (p_ad_click ≥ 0.40)              : 2 / 47    (4.3%)
```

Two participants click on ads in over 40% of their trials; two never do. The 16/47 (34%) "high-ad-clicker" cohort with `p_ad_click ≥ 0.20` is a distinct sub-population by behavior alone, before any task-model construct is invoked.

## §3 Prior predicts behavior

Ad-attention rate during survey predicts ad-click rate at the participant level:

| Prior × Behavior | n | Spearman ρ | p | Pearson r |
|---|---|---|---|---|
| `p_ad_survey` × `p_ad_click` | 47 | **+0.249** | 0.091 | +0.242 |
| **`p_ad_survey` × `p_dd_top_click`** | 47 | **+0.297** | **0.043** | +0.231 |
| `p_ad_survey` × `p_native_ad_click` | 47 | +0.108 | 0.469 | +0.145 |
| `ad_over_index` × `p_ad_click` | 47 | +0.232 | 0.116 | +0.209 |
| `ad_over_index` × `p_dd_top_click` | 47 | +0.267 | 0.070 | +0.205 |

Effect sizes are small to moderate (ρ ≈ +0.25–0.30) — consistent with a prior that informs but does not determine click choice. The headline is the dd_top channel: the prior's predictive lift is on the highest-CTR ad surface, not on `native_ad` (which is more interleaved with organic and harder to spot pre-click).

## §4 Independence from sat-opt and cognitive load

The ad-utility axis is **orthogonal** to the sat-opt segmentation and to LHIPA cognitive load:

| Independence test | n | Spearman ρ | p |
|---|---|---|---|
| `p_ad_survey` × regression rate (sat-opt) | 47 | +0.024 | 0.874 |
| `p_ad_click` × regression rate | 47 | +0.053 | 0.725 |
| `p_dd_top_click` × regression rate | 47 | +0.061 | 0.683 |
| `p_ad_survey` × trial-mean LHIPA | 47 | +0.134 | 0.367 |
| `p_ad_survey` × mean click position | 47 | +0.020 | 0.895 |

Sat-opt, cognitive load, click depth — none correlate with the ad-utility prior. This matters: it means a user's tendency to click ads is *not* explained by their breadth of evaluation (sat-opt), their cognitive effort (LHIPA), or their willingness to scroll deeper (mean click position). It's a separate axis.

This converges with the existing LF/HF × sat-opt orthogonality finding (load trajectory orthogonal to evaluation strategy at LOO AUC 0.286, ρ = +0.013, n = 46 — see [`docs/null-findings/2026-05-04-typed-cascade-null-revisit.md` §2](../null-findings/2026-05-04-typed-cascade-null-revisit.md)). We now have **three orthogonal individual-difference axes** on AdSERP:

1. **Sat-opt** (verification appetite) — regression rate, depth of comparison
2. **Cognitive load trajectory** — LF/HF position gradient, LHIPA trial means
3. **Ad-utility prior** — pre-decision ad-attention rate, ad-click rate

A four-construct user model decomposes more cleanly than a one-axis "engagement" continuum.

## §5 Interpretation for the rank-value-prior framing

The task-model paper's closing interpretation references "the agent's beliefs about SERP rank-value distributions" (Anderson rational-analysis framing). Ad-utility prior is the **first observable, behaviorally-grounded substrate** for that belief space. A participant who allocates 73% of survey fixations to ads is operationally placing higher rank-value mass on ad surfaces than one who allocates 46%, and that prior translates (modestly) into click behavior. The prior is observable from gaze in the first ~1 second of a trial — before any click event — and predicts the eventual ad-click outcome at ρ = +0.30.

For the **task-model paper**: this is the empirical anchor for the rank-value-prior axis. The framework is no longer hypothetical — there's a measured prior, a measured behavioral consequence, and an orthogonality to existing axes that makes it a third dimension rather than a re-projection.

For the **CIKM paper**: this is a candidate premise for the four-class taxonomy. If users have heterogeneous priors over rank-value (specifically ad-utility), the consideration set composition (clicked / deferred / evaluated-rejected / not-approached) per trial should differ in interpretable ways across the prior dimension. A participant with a high ad-utility prior is structurally more likely to commit to ad surfaces and structurally less likely to defer organics with similar dwell — testable.

## §6 Limitations

- **n = 47.** All correlations are at participant level on the AdSERP forced-choice task. ρ ≈ +0.30 with n = 47 puts *p* near 0.04, which is real but not bullet-proof under multiple testing. The orthogonality nulls (regression rate, LHIPA) are at *p* > 0.3, comfortably null.
- **Ad-utility is bundled with native_ad / dd_top / dd_right etypes.** A finer decomposition (per-etype ad-click prior) would distinguish "I look at top-page ads" from "I scan native ads" — currently averaged.
- **Forced-choice task.** Participants knew they had to click *something*. Ad-clicks here aren't accidental; they're real choices. But abandonment is not in the design space.
- **Prior measure depends on the survey-phase definition** — see `scripts/output/survey_bimodality/` for the operationalization. The prior is the fraction of survey fixations on ads, where survey is the early ballistic-scan portion of the trial.
- **No counterfactual.** We don't have AdSERP trials run without ads in the layout. The prior describes user behavior on ad-loaded SERPs; it doesn't tell us what users would do on ad-free SERPs.

## §7 Pointers

- Analysis script: `scripts/ad_utility_prior_analysis.py`.
- Output: `scripts/output/ad_utility_prior/summary.json` + `per_participant.csv`.
- Per-ppt traits source: `scripts/output/survey_bimodality/per_participant_with_traits.csv`.
- Behavior source: `AdSERP/data/cursor-approach-features-typed.json` (Phase C typed, 19,774 records).
- Population-level dd_top click rate (17.1%): cascade synthesis [`docs/methodology/attribution-cascade-synthesis.md`](../methodology/attribution-cascade-synthesis.md).
- Companion null: LF/HF × sat-opt orthogonality (load trajectory orthogonal to evaluation strategy) — [`docs/null-findings/2026-05-04-typed-cascade-null-revisit.md`](../null-findings/2026-05-04-typed-cascade-null-revisit.md) §2.
