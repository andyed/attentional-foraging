# Deliberation-phase leakage control

Generated 2026-08-12. Regime: **[LAB]** throughout (AdSERP, 47 participants, LOSO by participant).
Rank-type per section: §2-§4 `[LAB, AdSERP, organic_hybrid]`, §5 `[LAB, AdSERP, organic]`, §6 `[LAB, AdSERP, typed]`.

Producers (new scripts, no existing script modified):

- `scripts/approach_truncation_ablation.py` → `scripts/output/ablations/approach_truncation_ablation.json`, `approach_truncation_trial_stats.json`, plus truncated feature files for `organic_hybrid` / `organic` / `typed`
- `scripts/nonclicked_absorption_check.py` → `scripts/output/ablations/nonclicked_absorption_check.json`

## 1. The concern

In a forced-choice setting, cursor proximity or dwell to a result is close to a
direct proxy for clicking it, because the cursor must travel to the clicked target. The
published click-blinding buffer (Δ ∈ {0, 200, 500, 1000} ms before the click) removes only
the terminal lock-on window, not the full deliberation-phase approach to the to-be-clicked
AOI, so the very large effect (M4 vs M1, Cohen's d_z = 2.55 at Δ = 500 ms) is consistent
with a partly mechanical signal. The same worry applies to the graded-label ranking
results as label leakage into the test set. Both concerns operate exclusively through
the clicked AOI.

Two controls answer this: (a) excise the **entire** committed approach, not just the terminal
buffer, and re-run the §4.1 grid; (b) re-derive the graded-label results restricted to
**non-clicked AOIs**, the population where mechanical travel-to-target cannot operate.

Feature-vector naming, to prevent the known M4 ambiguity: **M4-9** is the legacy
nine-feature approach vector (includes `final_dist`, `retreat_dist`, both already shown
structurally leaky by `scripts/figures/m3_loso_diagnostic.py` — `final_dist` alone-AUC 0.80,
`retreat_dist` pinned at 0 px for clicked AOIs by construction). **M4-7** is the canonical
seven-feature vector with those two dropped; the paper's headline "M4 = 0.847" is **M4-7 at
Δ = 500 ms** (`scripts/output/paper-output/click_buffer_ablation.json`, cell
`organic_hybrid|buf500|M4-7` = 0.8468). The label "M4 (9 approach)" inside
`scripts/m4_nb21_hybrid_rerun.py` refers to the legacy nine-feature vector. Both variants are
reported at every condition below.

## 2. Operational definition: committed-approach onset

Per trial, let (x_c, y_c) be the final click coordinate and t_click its timestamp (ms).
Over the pre-click positional cursor samples (`mousemove` / `mouseover` / `click` events,
x > 0 px, t < t_click), define d(t) = Euclidean cursor distance (px) to (x_c, y_c).

Walking **backward** from the click, the committed-approach onset t_onset is the most recent
sample where all three hold:

1. d(t) is a local maximum (d[i] ≥ d[i−1] and d[i] ≥ d[i+1]) — the last moment the cursor
   moved *away* from the eventual click location before its final descent;
2. prominence ≥ 50 px relative to the minimum of d over the subsequent samples (jitter guard:
   sub-50 px wiggles during the descent do not restart the approach);
3. d(t) ≥ 100 px — the onset lies outside the click target's proximity band (the same
   100 px threshold that defines `dwell_in_proximity_ms`).

Fallback when no such maximum exists (monotone descent): the most recent sample with
d(t) ≥ the pre-click median of d. In practice the primary rule covers nearly everything:
**2,770 / 2,776 trials (99.8 %) via the local-maximum rule, 5 via the median fallback,
1 trial with no click.**

Everything at t ≥ t_onset is excluded from feature computation for **all** AOIs — the cursor
stream and the fixation stream are truncated at t_onset through the canonical extractor
(`compute_cursor_approach_features.compute_approach_features` with per-trial
`click_buffer_ms = t_click − t_onset`), so the control is symmetric across AOIs rather than a
clicked-AOI-only surgery. Click **attribution** still uses the raw click record: the label
survives, only the feature inputs are truncated — the same contract as the published
terminal-buffer control, of which this is the per-trial generalization.

## 3. What the truncation removes (cost accounting)

Across the 2,775 trials with a detected onset:

| Quantity removed | median | IQR | mean |
|---|---|---|---|
| time before click | 2,880 ms | [2,098, 4,455] ms | 3,747 ms |
| cursor path length | 149 px | [121, 212] px | 202 px |
| fraction of trial time (t_first_sample → t_click) | 18.8 % | [11.4 %, 35.0 %] | 27.2 % |

This is an order of magnitude more than the published terminal buffers (median excision
2,880 ms vs the fixed 500 ms canonical buffer), and it is deliberately conservative: the
excised window contains the mechanical travel **and** any genuine late deliberation
(terminal hovering, final re-reading), so the surviving AUC below is a *lower bound* on the
behavioral signal. Truncated feature coverage: 18,919 records / 2,768 trials
(`organic_hybrid`; vs 19,908 records / buf0), 13,882 records (`organic`),
18,794 records (`typed`).

## 4. §4.1 click-prediction grid under full-approach truncation `[LAB, organic_hybrid]`

Pooled LOSO AUC (47-fold leave-one-participant-out, logistic regression, class-balanced;
buffer columns from the published grid, not recomputed):

| Variant | Δ=0 ms | Δ=200 ms | Δ=500 ms | Δ=1000 ms | **approach-truncated** |
|---|---|---|---|---|---|
| M1 (position) | 0.667 | 0.667 | 0.668 | 0.668 | **0.675** |
| M2 (position + dwell) | 0.762 | 0.762 | 0.764 | 0.760 | **0.725** |
| M3 (M2 + 9 approach) | 0.870 | 0.870 | 0.867 | 0.858 | **0.763** |
| M3-7 (M2 + 7 approach) | 0.848 | 0.848 | 0.846 | 0.839 | **0.753** |
| M4-9 (9 approach only, legacy) | 0.870 | 0.870 | 0.867 | 0.858 | **0.744** |
| **M4-7 (7 approach only, canonical)** | 0.848 | 0.848 | **0.847** | 0.839 | **0.733** |

Per-trial ranking metrics for the canonical vector, truncated: MRR@10 = 0.626,
NDCG@1 = 0.428 (vs 0.741 / 0.593 at Δ = 500 ms). M1 is essentially buffer-invariant
(0.668 → 0.675; position needs no cursor stream), confirming the truncation hits exactly the
channel under suspicion.

Paired per-fold statistics (47 folds; Wilcoxon signed-rank; bootstrap 95 % CI on mean ΔAUC;
d_z = mean(Δ)/SD(Δ), the convention of `scripts/paper_stat_tests.py`):

| Contrast | mean ΔAUC | 95 % CI | d_z | Wilcoxon p |
|---|---|---|---|---|
| **M4-7 vs M1, both approach-truncated** | **+0.089** | [+0.069, +0.109] | **1.25** | 5.7 × 10⁻¹⁰ |
| M4-7 vs M1, published Δ = 500 ms | +0.210 | — | 2.55 | 1.4 × 10⁻¹⁴ |
| M4-7 @ Δ=500 ms vs M4-7 truncated (cost of control) | +0.116 | [+0.103, +0.129] | 2.45 | 1.4 × 10⁻¹⁴ |
| M4-9 @ Δ=0 (legacy headline) vs M4-7 truncated | +0.137 | [+0.123, +0.152] | 2.66 | 1.4 × 10⁻¹⁴ |
| M3-7 vs M4-7, both truncated (position re-emergence) | +0.010 | [+0.003, +0.017] | 0.41 | 1.1 × 10⁻² |

Reading: excising the whole committed approach costs the canonical vector 0.114 pooled AUC
(0.847 → 0.733), yet the cursor features still beat position by +0.089 per-fold AUC
(d_z = 1.25, p = 5.7 × 10⁻¹⁰). Of the published +0.210 per-fold M4-7−M1 margin at
Δ = 500 ms, **+0.089 (≈ 43 %) survives full-approach excision; the remaining ≈ 57 % is
attributable to the committed-approach segment** — an upper bound on the mechanical share,
since that segment also contains genuine terminal deliberation.

One published framing does **not** survive intact: "position absorbed at no AUC cost."
Under truncation, adding position + dwell back (M3-7 = 0.753 pooled) beats M4-7 by +0.010
per-fold AUC (d_z = 0.41, p = 0.011). The absorption result was partly carried by the
committed approach; the honest revision framing is REVISION-PLAN's contingency wording:
*position is partly absorbed by deliberation-phase cursor geometry*, fully absorbed only
when the approach segment is in the feature window.

## 5. Non-clicked population I: deferred vs evaluated-rejected (M5) `[LAB, organic]`

Population: approached (min_dist < 100 px) AND not clicked — the clicked AOI is excluded by
construction, so travel-to-target leakage cannot supply the signal. Labels:
NB22 `gaze_regression_label` (gaze-derived, buffer-invariant). LOSO logistic regression,
protocol of `scripts/m5_cursor_only_taxonomy.py`. Population sizes: n = 2,070 records
(buf0; 1,557 deferred / 513 evaluated-rejected, 75/25), 2,067 (Δ = 500 ms), 1,833
(approach-truncated; smaller because some AOIs' only sub-100 px proximity fell inside the
excised window).

Pooled LOSO AUC (deferred vs evaluated-rejected):

| Feature set | Δ=0 ms | Δ=500 ms | approach-truncated |
|---|---|---|---|
| position alone | 0.674 | 0.675 | 0.699 |
| M4-7 (canonical cursor) | 0.759 | 0.753 | **0.740** |
| M4-7 + position | 0.787 | 0.783 | 0.787 |
| M4-9 (legacy, lineage anchor) | 0.769 | — | — |

The buf0 legacy row reproduces the published §4.3 M5 = 0.769. The leakage-immune result:
**cursor-only discrimination of deferred vs evaluated-rejected loses only 0.019 pooled AUC
under full-approach excision (0.759 → 0.740)**, versus the 0.114 AUC the click-prediction
task loses under the same excision. The signal in the population where the mechanism cannot
operate is nearly untouched.

Position-absorption statistic in this population (paired per-participant, n = 45–46 folds
with both classes):

| Contrast | mean ΔAUC | 95 % CI | d_z | Wilcoxon p |
|---|---|---|---|---|
| (M4-7+position) vs M4-7, Δ=0 | +0.035 | [+0.015, +0.056] | 0.48 | 3.5 × 10⁻³ |
| (M4-7+position) vs M4-7, Δ=500 ms | +0.035 | [+0.015, +0.057] | 0.47 | 2.6 × 10⁻³ |
| (M4-7+position) vs M4-7, truncated | +0.052 | [+0.024, +0.081] | 0.53 | 1.6 × 10⁻³ |
| M4-7 vs position alone, truncated | +0.000 | [−0.056, +0.057] | 0.00 | 0.73 |

So in the non-clicked population position is **not** absorbed at any buffer level — it adds
+0.035 to +0.052 AUC over cursor features (deferral covaries with rank). The absorption
claim is a property of the click-prediction task, and §4 above shows it weakens there too
once the approach is excised. Consistent story across both populations: cursor geometry and
position are complementary, with cursor dominant only when the approach segment is
observable.

## 6. Non-clicked population II: graded-label LambdaMART `[LAB, typed]`

Protocol of `scripts/ltr_typed_four_distinct_grades.py` (gaze label source, LightGBM
LambdaRank, NDCG@10-optimized, MRR@10 vs binary-click gold, LOSO, M3-no-position features),
re-run on the approach-truncated typed features. The four-class grades exclude the clicked
AOI from the deferred/evaluated-rejected split by construction. Class distribution under
truncation: 2,440 clicked / 2,348 deferred / 502 evaluated-rejected / 5,281 not-approached-
above; 8,223 NotApprBelow excluded (class composition shifts vs buf0 because the
approached gate uses truncated `min_dist`; the gaze labels themselves are fixed).

MRR@10 (n = 2,369 trials):

| Ranker | buf0 (published) | Δ=500 ms (published) | approach-truncated |
|---|---|---|---|
| SERP position (no ML) | 0.460 | 0.450 | 0.461 |
| LambdaMART binary click | 0.685 | 0.677 | **0.461** |
| LambdaMART 3-grade (2/1/0/0, paper headline) | 0.736 | 0.731 | 0.546 |
| LambdaMART 4 distinct grades (3/2/1/0) | 0.742 | 0.734 | 0.565 |
| ΔMRR@10 (3-grade − binary) | **+0.051** | **+0.054** | **+0.085** |
| ΔMRR@10 (4-grade − binary) | +0.057 | +0.057 | **+0.104** |

Paired per-trial stats, truncated run: 3-grade − binary ΔMRR@10 = +0.085
[+0.072, +0.098], d_z = 0.26, Wilcoxon p = 4.7 × 10⁻³⁴; 4-grade − binary = +0.104
[+0.089, +0.119], d_z = 0.29, p = 1.8 × 10⁻³⁹.

The May 2026 REVISION-PLAN hypothesis — *the graded-label lift widens under
leakage-corrected features because the binary baseline loses its mechanical lift* — is
confirmed and amplified: the binary-click LambdaMART **collapses to the no-ML position
baseline** under full-approach excision (0.461 vs 0.461 MRR@10), while the graded models
retain 0.085–0.104 MRR@10 of lift. The binary target is exactly the label the mechanical
travel signal points at; the graded labels earn their lift from deliberation-phase behavior
on AOIs the cursor did *not* end on. (Caveat: all absolute MRRs drop under truncation, and
the widening is driven by the baseline's collapse rather than by the graded models
improving; the honest claim is robustness of the *ordering*, not of the absolute numbers.)

## 7. How much of the click-prediction margin is mechanical?

The concern is partly right, and the control quantifies exactly how much. Excising the
entire committed approach — from the last prominent (≥ 50 px) local maximum of cursor
distance to the click location, median 2,880 ms and 149 px of path before the click,
an order of magnitude more than the 500 ms terminal buffer — costs the canonical
seven-feature cursor model 0.114 pooled LOSO AUC (0.847 → 0.733) `[LAB, organic_hybrid]`,
and the M4-vs-M1 effect size drops from d_z = 2.55 to d_z = 1.25. Roughly 57 % of the
published cursor-over-position margin is therefore attributable to the approach segment and
is, at the upper bound, mechanical; we will say so in the paper. What survives is not
residue: +0.089 per-fold AUC over position (95 % CI [+0.069, +0.109], Wilcoxon
p = 5.7 × 10⁻¹⁰) with zero approach-phase samples available, and the two results that carry
the paper's contribution are nearly leakage-immune because they live on non-clicked AOIs
where travel-to-target cannot operate: deferred-vs-evaluated-rejected discrimination loses
only 0.019 AUC under the same excision (0.759 → 0.740 `[LAB, organic]`), and the graded-label
ranking lift over the binary-click baseline *widens* from +0.051 to +0.085 MRR@10
`[LAB, typed]` — under full excision the binary-click ranker collapses to the position
baseline while the graded models keep their lift. The mechanical component is real,
now measured, and concentrated precisely in the claim (raw click prediction) that the paper
treats as signal validation rather than contribution; the deliberation-phase claims stand on
the population the mechanism cannot reach. One honest retraction: "position absorbed at no
AUC cost" weakens to "partly absorbed" — position re-emerges at +0.010 AUC (d_z = 0.41)
once the approach is excised, and independently adds +0.035–0.052 AUC in the non-clicked
population.

## 8. Reproduction

```bash
.venv/bin/python scripts/approach_truncation_ablation.py    # ~4 min serial + LOSO (n_jobs=4)
.venv/bin/python scripts/nonclicked_absorption_check.py     # ~6 min, LGBM folds serial
```

Inputs: published buffer grid `scripts/output/paper-output/click_buffer_ablation.json`;
label caches `scripts/output/approach_threshold_sensitivity/regression_labels_cache_{organic,typed}.json`;
published LTR summaries `scripts/output/ltr_typed_four_distinct_grades/summary{,_gaze_buf500}.json`.
Truncated feature files land in `scripts/output/ablations/` and are not written into
`AdSERP/data/` (they are an ablation artifact, not a new canonical substrate).
