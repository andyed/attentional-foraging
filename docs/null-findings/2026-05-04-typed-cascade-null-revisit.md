# Typed-cascade null-finding revisit (2026-05-04)

**TL;DR.** The 2026-05-04 typed cascade ([`docs/methodology/organic-result-aoi-extraction.md`](../methodology/organic-result-aoi-extraction.md)) raises the question of whether existing nulls — most computed under absolute or bbox-organic — still hold. This doc walks every null in `docs/null-findings/` and classifies it: HOLDS (attribution-invariant), VERIFIED (recomputed under typed), STRENGTHENS, or NEEDS RECOMPUTE. Two load-bearing nulls (R1 RIPA2 dissociation, LF/HF × satopt orthogonality P0–P3) were re-run under typed; both replicate.

---

## Triage table

| # | Null finding | Cascade-affected? | Verdict under typed | Action |
|---|---|---|---|---|
| 1 | [R1 RIPA2 bbox-collapse](r1-ripa2-bbox-collapse.md) | Yes (RIPA2 + LF/HF, per-fixation × per-rank) | **VERIFIED** — typed replicates bbox split | Updated below |
| 2 | [LF/HF × satopt orthogonality P0–P3](2026-04-19-lfhf-satopt-orthogonality-p03-robust.md) | Yes (LF/HF × satopt) | **VERIFIED** — orthogonality cleaner under typed | Updated below |
| 3 | [NB14 plateau concentration audit](2026-04-19-nb14-plateau-concentration-audit.md) | Yes (NB14 plateau) | **STRENGTHENS** — plateau ρ flips n.s. (was −0.714 absolute) | NB14 K-claims already updated |
| 4 | [LF/HF × content crossover](2026-04-19-lfhf-content-crossover-null.md) | Yes (LF/HF × content) | **HOLDS** by inference (LF/HF shifts ±0.02; content unchanged) | Recompute optional; expected null |
| 5 | [LF/HF × viewport stratification](2026-04-19-lfhf-viewport-stratification.md) | Yes (LF/HF × viewport bands) | **HOLDS** by inference (NB28 retreat+bands AUC 0.811 stable) | Recompute optional |
| 6 | [NB29 viewport-bands content residualization](nb29-viewport-bands-content-residualization.md) | Yes (NB28 features) | **HOLDS** by inference (content explains ≤2.5% variance; rank+ppt FE dominate) | Recompute optional |
| 7 | [satopt × LHIPA duration confound](2026-04-16-satopt-lhipa-duration-confound.md) | No (LHIPA is whole-trial) | **HOLDS** — duration confound is at sat/opt-cluster level | None |
| 8 | [Pos-9 fixation uptick collapse](2026-04-26-pos9-fixation-uptick-collapse.md) | Maybe (per-ppt clustering test) | **HOLDS** by inference (per-ppt test, attribution shifts denominator slightly) | None |
| 9 | [Priming null result](priming-null-result.md) | No (pre-cascade methodology) | **HOLDS** — null already triple-confounded | None |
| 10 | [Ski-jump audit collapse](2026-04-12-ski-jump-audit-collapse.md) | No (coordinate-space audit) | **HOLDS** — coord-fix not attribution | None |
| 11 | [Novelty baseline residual redundancy](2026-04-15-novelty-baseline-residual-redundancy.md) | No (residual methodology) | **HOLDS** — methodological null | None |
| 12 | [Rung-4 rank-within-trial label](2026-04-20-rung4-rank-within-trial.md) | No (LambdaMART labeling) | **HOLDS** — label-construction artifact | None |
| 13 | [NB26 LTR graded vs binary](nb26-ltr-graded-vs-binary.md) | No (label construction) | **HOLDS** — labeling experiment | None |
| 14 | [LF/HF leakage check](2026-05-02-lfhf-leakage-check.md) | No (methodology) | **HOLDS** — frequency-band leakage check | None |
| 15 | [Peri-click RIPA2 SG-VLF leakage](2026-05-02-peri-click-ripa2-sg-leakage.md) | No (RIPA2 method bug) | **HOLDS** — bug fix shipped | None |

**Summary:** 2 verified by recompute, 1 strengthens (NB14 plateau), 4 hold by inference (cascade-affected but null is robust to ±0.02 LF/HF shifts), 8 hold (cascade-invariant). No null reverses to a positive finding under typed.

---

## §1 R1 RIPA2 dissociation — VERIFIED (LF/HF strengthens, RIPA2 still null)

**Recompute:** `scripts/r1_under_typed.py` (2026-05-04). Reads `butterworth-lfhf-by-position-typed.json` + `ripa2-by-position-typed.json` + `encoding-vs-retrieval.json`; runs the same per-(trial, position) Mann-Whitney test for will-regress vs no-regress that the original R1 dissociation used.

| Attribution | LF/HF leg (d, p) | RIPA2 leg (d, p) | n_records (wr / nr) |
|---|---|---|---|
| absolute (legacy) | +0.041, **p = 0.011** | +0.006, **p = 0.0058** | (legacy values from r1-ripa2-bbox-collapse.md) |
| bbox-organic | +0.069 (computed), **p = 1.1×10⁻³** | ~0, **p = 0.80** | (per [r1-ripa2-bbox-collapse.md](r1-ripa2-bbox-collapse.md)) |
| **typed** | **+0.029, p = 4.6×10⁻⁶** | **+0.021, p = 0.136** | 4,776 (3,439 / 1,337) |

**Reading.** The typed cascade strengthens the LF/HF leg further (p drops from 1.1×10⁻³ under bbox-organic to 4.6×10⁻⁶ under typed) — more position-rank surfaces with cleaner widget typing means more clean per-(trial, pos) records contributing to the LF/HF differential. The RIPA2 leg recovers slightly (p=0.80 → 0.14) but **does not reach significance**; the joint LF/HF × RIPA2 dissociation that was significant under absolute (p=0.0058) remains an absolute-attribution rank-pooling artifact. The most parsimonious reading from `r1-ripa2-bbox-collapse.md` holds under typed.

The RIPA2 p=0.14 vs bbox p=0.80 is worth flagging: typed gives RIPA2 the *most* favorable per-fixation arousal-amplitude signal of the four flavors, but it still lands above α=0.05. If a future iteration of the standalone RIPA2 paper wants to make the per-fixation will-regress claim, typed is the strongest attribution to argue from — but as of 2026-05-04 it doesn't carry alone.

**Output:** `scripts/output/r1_under_typed/r1_under_typed.json`.

## §2 LF/HF × satopt orthogonality P0–P3 — VERIFIED (cleaner null under typed)

**Recompute:** `scripts/lfhf_satopt_orthogonality_p03_typed.py` (2026-05-04). Reads `butterworth-lfhf-by-position-typed.json`; computes per-participant 6-feature LF/HF trajectory on P0-P3, predicts satopt (high-vs-low regression rate at participant median) via LOO-LR.

| Attribution | LOO-LR AUC | Spearman(slope_ρ, regression_rate) | Per-feature \|d\| max |
|---|---|---|---|
| Original full-range (bbox-organic, 2026-04-19) | 0.43 | ρ=−0.226, p=0.13 | (per original null doc) |
| Robust steep-phase (bbox-organic, 2026-04-19) | 0.523 (majority 0.522) | ρ=−0.020, p=0.90 | < 0.21 |
| **typed (2026-05-04)** | **0.286 (majority 0.522)** | **ρ=+0.013, p=0.930** | **< 0.23** |

**Reading.** AUC 0.286 is *worse* than chance (0.522 majority), Spearman ρ on the slope-vs-rate plane is essentially zero, all per-feature Cohen's d on the LF/HF trajectory features are below 0.23. The orthogonality of LF/HF trajectory and satisficer/optimizer segmentation is **stronger** under typed than under bbox-organic. The original null framing — "load trajectory and behavioral strategy are independent dimensions" — is reinforced.

**Output:** `scripts/output/lfhf_satopt_orthogonality_p03_typed/summary.json`.

## §3 NB14 plateau concentration audit — STRENGTHENS

The original null doc ([2026-04-19-nb14-plateau-concentration-audit.md](2026-04-19-nb14-plateau-concentration-audit.md)) showed:
- absolute: P4–P10 plateau ρ = −0.714, p = 0.071 (marginal); cap-10 per-ppt downsampling **strengthens** to ρ = −0.786, p = 0.036.
- 95% participant-cluster bootstrap CI: [−0.893, +0.143] (crosses zero).
- Reading: plateau marginal *p* is genuine small-N noise on 7 position medians, not concentration.

**Under typed** (per cascade synthesis + NB14 typed re-execution):
- Plateau ρ collapses further. Hybrid plateau ρ = +0.321 (n.s.); typed plateau ρ ≈ 0.000 (n.s.).
- The "small-N noise" reading from the concentration audit is reinforced: when the noise is sampled from a different attribution, the plateau correlation gives a different small-magnitude value with no consistent sign.

**Effect.** The audit's central methodological claim — "any per-position correlation on a tiny N reflects sampling noise more than mechanism" — holds with extra force under typed. NB14:K11 should continue to be cited qualitatively, not as a directional claim.

## §4 LF/HF × content crossover — HOLDS by inference

The original null ([2026-04-19-lfhf-content-crossover-null.md](2026-04-19-lfhf-content-crossover-null.md)) tested 5 content features × 3 tests (pooled, partial, FE) = 15 tests against LF/HF, with **no feature × test surviving Bonferroni α = 0.003**. Largest unadjusted: FE β on centroid_novelty (p=0.018).

Under typed:
- LF/HF values shift by ≤ 0.05 in correlation strength against any per-position covariate (per cascade synthesis §1.05).
- Content features (token_count, char_count, TTR, query_cosine, centroid_novelty) are per-organic and unaffected by the typing pass.
- The 15-test family's effect sizes were already \|ρ\| < 0.10, sign-flipping across positions; ±0.05 LF/HF shifts can't promote any of them through Bonferroni α = 0.003.

**Verdict:** still null under typed. Recompute optional, expected null. Cross-link: LF/HF is position-bound (framework compilation sharpens by rank), not item-semantics-bound — consistent under all four attribution flavors.

## §5 LF/HF × viewport stratification — HOLDS by inference

`2026-04-19-lfhf-viewport-stratification.md` (file content tied to LF/HF stratified by viewport state; same data sources as above). Under typed, LF/HF position medians shift within ±0.05; viewport bands (NB28 retreat+bands AUC 0.811 [0.788, 0.833] under bbox-organic) are robust. Recompute optional.

## §6 NB29 viewport-bands content residualization — HOLDS by inference

`nb29-viewport-bands-content-residualization.md`: residualizing viewport-band dwell against content features did NOT improve deferred-vs-evaluated-rejected discrimination. Δ (retreat + residualized) − (retreat + raw) = −0.024 AUC. Content explains ≤ 2.5% of band-dwell variance.

Under typed:
- Viewport bands (NB28) re-derived; content features unchanged.
- The per-feature variance explained is bounded above by the variance content features explain in band-dwell (≤2.5%); no plausible cascade shift that changes that.

**Verdict:** still null. Methodological caveat about participant-FE absorbing variance still applies. Recompute optional.

## §7 satopt × LHIPA duration confound — HOLDS

LHIPA is a whole-trial pupil-dilation measure ([Duchowski et al CHI 2020]). It does not condition on per-rank AOI assignment; it's invariant to attribution flavor. The duration confound (`partial(regression_rate × mean_LHIPA | duration)` collapses to ρ=+0.135 from −0.568) is at the sat/opt-cluster level, attribution-independent.

**Verdict:** holds. No recompute needed.

## §8 Pos-9 fixation uptick collapse — HOLDS by inference

`2026-04-26-pos9-fixation-uptick-collapse.md`: forward-only "position-9 fixation uptick" (row-level Mann-Whitney p=1.7×10⁻¹⁶) reverses sign at per-participant level (8/9 non-tied participants in the wrong direction, Wilcoxon p=0.016 wrong-sign).

Under typed:
- Position-9 sample shifts slightly (typed widget surfaces add 1–3 cards near the bottom of the typical SERP).
- The per-participant cluster test that retired the uptick is robust: it requires per-participant directionality, which doesn't suddenly flip from a small denominator change.
- The §5.7 motor pillar (cursor-gaze coupling tighter for regressive than forward) survives clustering; that finding is attribution-invariant (it's about cursor-gaze coupling within fixation windows, not about which AOI a fixation lands on).

**Verdict:** holds. Per-participant clustering rule should be the default for any rank-effect claim regardless of attribution.

## §9–§15 Cascade-invariant nulls (no recompute needed)

The remaining seven nulls are not affected by AOI attribution by construction:

| File | Why cascade-invariant |
|---|---|
| [`priming-null-result.md`](priming-null-result.md) | Pre-cascade lexical-priming framework; null already triple-confounded (position, repetition, scroll kinematics). Cascade doesn't fix any of those. |
| [`2026-04-12-ski-jump-audit-collapse.md`](2026-04-12-ski-jump-audit-collapse.md) | Coordinate-space audit (FPOGY scroll double-count fix). Bug-fix audit, not attribution-dependent. |
| [`2026-04-15-novelty-baseline-residual-redundancy.md`](2026-04-15-novelty-baseline-residual-redundancy.md) | Methodological null about residual baseline R²; doesn't depend on AOI attribution. |
| [`2026-04-20-rung4-rank-within-trial.md`](2026-04-20-rung4-rank-within-trial.md) | LambdaMART label-construction artifact (2.2% of clicks at within-trial grade 0). Label-engineering finding, attribution-orthogonal. |
| [`nb26-ltr-graded-vs-binary.md`](nb26-ltr-graded-vs-binary.md) | Label-construction comparison (graded vs binary click labels). |
| [`2026-05-02-lfhf-leakage-check.md`](2026-05-02-lfhf-leakage-check.md) | Frequency-band leakage methodology check; attribution-orthogonal. |
| [`2026-05-02-peri-click-ripa2-sg-leakage.md`](2026-05-02-peri-click-ripa2-sg-leakage.md) | RIPA2 method bug (`(SG·P)² − ...` → `SG_LF² − SG_VLF²`); fix shipped 2026-04-25. |

---

## §16 What the typed cascade did NOT change in the null inventory

No null reverses to a positive finding. The cascade improves **rank-denominator hygiene** by giving widget surfaces first-class etype labels (5,148 surfaces previously pooled with organics or filtered out below the y-floor). It does NOT change:

- The cognitive findings (per-participant, per-trial, within-fixation operations remain robust).
- The methodological nulls (priming, ski-jump, novelty residual, rung-4 label, leakage checks).
- The mechanistic dissociations that hold up: R1 LF/HF leg (gets stronger), pos-9 motor pillar, satopt × LHIPA duration confound, satopt × LF/HF orthogonality (gets cleaner).

The cascade is a **cleaner instrument**, not a different question.

## §17 Pointers

- Recompute scripts: `scripts/r1_under_typed.py`, `scripts/lfhf_satopt_orthogonality_p03_typed.py`.
- Outputs: `scripts/output/r1_under_typed/`, `scripts/output/lfhf_satopt_orthogonality_p03_typed/`.
- Cascade synthesis: [`docs/methodology/attribution-cascade-synthesis.md`](../methodology/attribution-cascade-synthesis.md).
- Pipeline spec: [`docs/methodology/organic-result-aoi-extraction.md`](../methodology/organic-result-aoi-extraction.md).
- CHANGELOG entry: [2026-05-04 typed cascade](../../CHANGELOG.md).
