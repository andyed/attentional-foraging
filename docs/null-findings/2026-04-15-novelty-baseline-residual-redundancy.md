# Sentence-embedding lexical-novelty residuals are redundant with raw dwell at the per-result grain on AdSERP

**Date:** 2026-04-15
**Notebooks:** [`25_lexical_novelty_dwell.ipynb`](../../notebooks-v2/25_lexical_novelty_dwell.ipynb), [`27_mobile_portable_ablation.ipynb`](../../notebooks-v2/27_mobile_portable_ablation.ipynb)
**Regime:** `[LAB]` — both analyses use AdSERP gaze fixation data and scroll-derived viewport dwell.
**Outcome:** **Kept out of the CIKM paper.** Documented here because the pattern appeared twice and is worth flagging as a project-level methodological constraint, not just an accident of one run.

## TL;DR

Peter Dixon-Moses's "rubbernecking vs passing" framing inspired two different versions of a *novelty-deviation-based dwell residual* feature:

- **NB25 version** (per-fixation, 2026-04-15): expected fixation duration = f(cos-sim to centroid of previously-fixated results). Residual = log(actual dwell) − log(expected).
- **NB27 version** (per-viewport, 2026-04-15): expected viewport dwell = f(text length, cos-sim query↔combined result text). Residual = log(1 + actual viewport dwell) − log(1 + expected).

**In both cases the residual was empirically indistinguishable from the raw (log-transformed) dwell variable it was derived from**, because the novelty-baseline regression explained essentially none of the dwell variance. The "residual" was `raw − small_correction`, and the small correction did not move downstream Spearman correlations, LOSO AUC contributions, or multivariate feature-ablation checks. The framing survives theoretically — it is an instance of the soft-constraints-hypothesis prediction that attention allocation deviates from content-predicted baselines — but the embedding-centroid baseline is too weak to separate the deviation from the raw signal at the per-result grain available on AdSERP.

## The evidence

### NB25 version — per-fixation lexical novelty residual

| Comparison | Value |
|---|---:|
| Spearman ρ(residual, clicked) — **K2** | +0.234, p ≈ 10⁻¹²⁷ |
| Spearman ρ(absolute log fixation dwell, clicked) — **K9** | +0.262, p ≈ 10⁻¹⁹⁴ |
| K2 / K9 ratio | 0.89 (residual ~11% *weaker*) |
| M4 + residual vs M4 alone (LOSO concat AUC, K3) | Δ = +0.0022 (noise-equivalent) |
| Feature-ablation: drop `dwell_in_proximity_ms` from M4, add residual — does residual recover the lost AUC? (K6) | **No.** AUC loss = −0.023, recovery = −0.0002. |
| Query-centroid baseline instead of fixated-centroid baseline (K8) | Residual-click ρ = +0.237, **ratio to K2 = 1.01 (identical)**. Baseline choice does not matter because the baseline has near-zero explanatory power. |

### NB27 version — per-viewport lexical novelty residual

| Comparison | Value |
|---|---:|
| Spearman ρ(raw viewport_dwell_ms, clicked) — **K1** | **+0.1623**, p ≈ 10⁻⁷⁵ |
| Spearman ρ(viewport_dwell_residual, clicked) — **K2** | **+0.1617**, p ≈ 10⁻⁷⁴ |
| K1 − K2 | **+0.0006 (same to 4th decimal)** |
| Expected-dwell baseline coefficients | `log(1 + vpd) = 1.49 × 10⁻⁴ · text_length + 0.32 · cos_query + 9.12` |
| Residual variance / raw variance | essentially 1.0 (baseline barely moves the distribution) |

### Both versions in one sentence

When the "expected dwell" baseline has near-zero R² against the raw dwell variable — which it does, in both NB25 and NB27, because sentence-embedding cos-sim explains very little of per-result dwell at this grain — the residual is numerically almost identical to the raw variable, and every downstream predictive test treats them as the same feature.

## Why the baseline has near-zero R²

Three candidate explanations, not mutually exclusive:

1. **Sentence embeddings are too coarse for the effect.** The Reichle/Rayner E-Z Reader novelty-dwell relationship operates at the *per-word* level — a specific token has or hasn't been encountered before, and its predictability conditions a per-fixation pause. Sentence embeddings pool across all tokens and lose this resolution. A token-level analysis (requires word-level bounding-box rendering per SERP) might separate the effect from raw dwell; this is noted as unfinished work in `docs/lit-notes/huang2012-gaze-cursor.md` and was discussed with Peter 2026-04-15.

2. **The AdSERP forced-choice task compresses the novelty-dwell curve.** Users are *required* to click, so they read carefully regardless of novelty gradient. A naturalistic search task with an abandonment option would produce a wider range of content-predicted dwells and could separate the residual from the raw variable.

3. **The novelty-dwell relationship is genuinely weak at the per-result grain.** The surface-level content variance between top-10 SERP results is low relative to the within-result processing variance (a user spending 800 ms on a result that a sentence-embedding model would predict 600 ms for is doing 200 ms of cognitive work that is *not* mostly about reading novelty — it's about decision-making, comparison to prior candidates, or idiosyncratic semantic access). The residual framing would demand that the "not mostly about reading novelty" part is the signal; in practice the variance floor is above the novelty effect and the residual collapses.

Explanation 1 is the easiest to test with further work (requires SERP re-rendering for word bounding boxes, achievable with headless Chrome). Explanations 2 and 3 are structural to the AdSERP dataset and cannot be tested without a different behavioral task.

## What was learned anyway

1. **The raw dwell variable is load-bearing and unambiguous.** Absolute fixation dwell on a result (NB25:K9) correlates with click at ρ = +0.262 with exact phase-dependence at the OSEC Survey/Evaluate boundary (+0.014 Survey ns, +0.262 post-Survey, 18.9× ratio). Absolute viewport dwell on a result (NB27:K1) correlates at ρ = +0.162 and adds +10.4 AUC pts over text features alone. **The per-result absolute-dwell signal is real; you just don't need a novelty-deviation framing to extract it.**

2. **The residual idea is not dead in general — just at this grain on this data.** The Posner & Cohen / Gray / Rayner lineage is sound; a per-token residual on word-bounding-box SERPs may well show the cleaner effect (§5 research lead in NB25 and a stalled TODO in the repo). If future work re-opens this thread, **the baseline model needs R² > 0.05 against the raw variable before the residual is worth computing**. Check that floor first.

3. **When the baseline has near-zero R², the "residual" is just mean-centering.** This is numerically obvious in retrospect but was not our intuition going in. Future analyses in this project that propose a "residual feature" should compute the baseline R² before building downstream pipelines on top of the residual — if R² < 0.05, the residual is the raw variable in disguise and the extra complexity buys nothing. **Baseline R² check as a gate** before committing to a residual framing.

## Pointers

- NB25 retrospective (Cell 1 markdown): explicit retrospective walk-through of the residual-vs-raw-dwell equivalence (K2 vs K9) from the 2026-04-15 run. References the K1 novelty correlation (+0.10 ns) that established the baseline was too weak.
- NB27 Key Claims (Cell 0 markdown): K1 ≈ K2 flagged as a secondary null alongside the primary K7 cursor-free recovery ratio.
- `docs/findings-approach-retreat.md` Mobile portability section: mentions the secondary null inline alongside the primary cursor-free recovery finding.
- `docs/null-findings/README.md`: the project-level principle this entry implements.
- Upstream: Peter Dixon-Moses Slack thread, 2026-04-15 ~10:20 AM — initial proposal; ~13:00 — NB25/NB27 results and disposition.

## Status

**Documented, not forgotten.** The theoretical framing (soft-constraints-predicted dwell deviation as a cognitive signal) stands on its literature. The empirical operationalization on AdSERP at sentence-embedding grain does not. A future analyst revisiting this thread should:

1. Check the baseline R² against the raw dwell variable *first*.
2. If R² < 0.05, the residual is redundant; use the raw variable directly and drop the novelty framing.
3. If R² ≥ 0.05, proceed with the residual analysis and compare directly against the raw-variable baseline.
4. Consider token-level bounding-box rendering as the mechanism that could lift the baseline R² out of the near-zero regime.
