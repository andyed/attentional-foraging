# dd_top cell promiscuity — within-carousel sampling as an individual-difference axis

**Date:** 2026-05-24
**Stable ID:** F:dd-top-cell-promiscuity
**Source:** `scripts/dd_top_cell_segmentation.py` → `scripts/output/dd_top_cell_segmentation/{summary.json, per_participant.csv}`
**Anchor for:** AllSERP arxiv update (within-surface deliberation as a complement to the ad-utility prior); downstream cognitive modeling (sub-trial deliberation depth).
**Companion to:** [`ad-utility-prior.md`](./ad-utility-prior.md) (the *between-surface* gaze prior); [`methodology/gaze-prior-elicitation.md`](./methodology/gaze-prior-elicitation.md). Cell substrate from AF cellsplit cascade (commit `16cd63a6 bulk: cell-aware features for all 2,776 trials`).

---

## TL;DR

When the dd_top "top ad" carousel is split into its constituent cards (mean ~4 cells per carousel), per-participant cursor engagement at the cell level reveals a trait dimension that `p_dd_top_click` and `p_ad_click` collapse:

- **Strong split-half reliability** — cell_promiscuity_rate r = 0.826 (Spearman-Brown 0.905); mean_touched_fraction r = 0.883 (SB 0.938); any_cell_engagement_rate r = 0.817 (SB 0.899). Comparable to the NB11.5 cursor-chattiness reliability (r > 0.96), well above the threshold for treating as a trait.
- **Wide between-participant spread** — cell_promiscuity_rate ranges 0.000 to 0.912 across n=47, median 0.387, IQR [0.166, 0.587]. The 47 participants stratify into 4 "never-shop" (touch ≥2 cells on <5% of carousels), 10 "always-shop" (>60%), and a middle 33.
- **Correlated with deliberation, not with the gaze prior** — promiscuity correlates with regression rate (ρ = +0.330, *p* = 0.025, n = 46) and overall ad-click rate (ρ = +0.334, *p* = 0.025, n = 45) but is **uncorrelated with `p_ad_survey`** (the pre-decision gaze prior, ρ = −0.064, *p* = 0.67). This is the key dissociation: gaze prior predicts *which surface* a user clicks; cell promiscuity predicts *how thoroughly they sample within it*.

**Caveats already accounted for here**: nominal p < 0.05 effects do *not* survive Bonferroni across the 30 reported correlation tests (corrected α ≈ 0.0017). Treat as a candidate axis. Replication on a second cohort or pre-registered single-test analysis is the next bar.

---

## §1 The measure

For each AdSERP trial with a `dd_top` carousel and resolved cell sub-bboxes (1,550 / 2,776 trials = 56% of the corpus), we walk the cursor stream against each `dd_top_cell` bbox and count enter→exit episodes with dwell ≥ 100ms (same threshold as `build_replay_trial.derive_aoi_labels`). Per trial we record `n_cells` (cell count in the carousel), `n_touched` (cells with ≥1 qualifying episode), `n_clicked` (cells with ≥1 click event inside the bbox).

Per-participant aggregates over trials with a dd_top carousel:

| Metric | Definition |
|---|---|
| `n_dd_top_trials` | denominator (per-participant range 19–45, median 33) |
| `mean_cells_per_carousel` | trial-mean of `n_cells` (≈ 4.0–4.2 for all participants — carousels are similar across users) |
| `any_cell_engagement_rate` | fraction with `n_touched ≥ 1` (any cell touched) |
| **`cell_promiscuity_rate`** | **fraction with `n_touched ≥ 2` (the headline)** |
| `mean_n_touched_when_engaged` | conditional mean of `n_touched` given engagement |
| `mean_touched_fraction` | trial-mean of `n_touched / n_cells` (continuous variant of promiscuity) |
| `p_carousel_click` | fraction with ≥1 cell click (different from `p_dd_top_click` — denominator is dd_top trials, not all trials) |

Cells are loaded from `scripts/output/cascade-baseline/aoi-snapshot-v1/` with midpoint-split enabled (cell X-ranges expanded to cover inter-cell gaps inside the parent bbox), matching the canonical cellsplit extractor used in `m4_nb21_hybrid_rerun_cellsplit.py`.

---

## §2 Heterogeneity

Across the 47 participants, cell-shopping behavior is **more dispersed than ad-click behavior** (range 0–0.91 vs ad-click 0–0.53 in the prior cohort):

```
never-shop      [0.00-0.05): 4 / 47   (8.5%)  - touch 2+ cells on <5% of dd_top trials
rare-shop       [0.05-0.15): 7 / 47   (14.9%)
sometimes-shop  [0.15-0.30): 9 / 47   (19.1%)
often-shop      [0.30-0.60): 17 / 47  (36.2%) - modal
always-shop     [0.60-1.00): 10 / 47  (21.3%) - touch 2+ cells on 60-91% of trials
```

**Top-5 always-shop**: p015 (0.91), p032 (0.88), p028 (0.85), p033 (0.81), p011 (0.75). These five touch ≥1 cell on essentially every dd_top trial (any_eng ≥ 0.91) and sample multiple cells on the majority.

**Bottom-5 never-shop**: p022 (0.00), p018 (0.03), p014 (0.03), p007 (0.03), p010 (0.06). Two distinct sub-patterns inside this bucket: p022 *does* touch a cell on 61% of trials but never two, while p018 / p014 barely touch cells at all (any_eng 0.22 / 0.25).

The mean carousel size is ~4 cells for every participant — the spread isn't an exposure artifact. Promiscuous users see the same dd_top carousels as never-shop users; they just engage with more of the cards.

---

## §3 Trait stability

Random-split each participant's dd_top trials into two halves, recompute the metric on each half, correlate the halves across participants:

| Metric | Spearman r | Spearman-Brown (corrected to full length) | n |
|---|---:|---:|---:|
| `any_cell_engagement_rate` | 0.817 | **0.899** | 47 |
| `cell_promiscuity_rate` | 0.826 | **0.905** | 47 |
| `mean_n_touched_when_engaged` | 0.637 | 0.778 | 47 |
| `p_carousel_click` | 0.693 | 0.819 | 47 |
| `mean_touched_fraction` | **0.883** | **0.938** | 47 |

Three of five metrics clear r > 0.80 split-half (SB > 0.90). The two looser metrics (`mean_n_touched_when_engaged`, `p_carousel_click`) both conditioning on a smaller subset of trials, so the per-participant denominator drops and the noise floor rises — consistent with their lower split-half. **`mean_touched_fraction` is the most trait-like single measure** (continuous, no conditioning); `cell_promiscuity_rate` is the readable categorical analogue.

This is comparable to the published-trait threshold in NB11.5 (cursor chattiness, r > 0.96). Cell promiscuity is a real, trait-level individual difference.

---

## §4 Correlations with prior axes

How does cell promiscuity relate to the existing individual-difference axes? Spearman correlations against the prior cohort:

|  | `p_ad_survey` (gaze prior) | `p_dd_top_click` | `p_ad_click` | `regression_rate` (sat-opt) | `mean_lhipa` (load) | `ad_over_index` |
|---|---:|---:|---:|---:|---:|---:|
| `any_cell_engagement_rate` | +0.04 | +0.28 | **+0.32 ***| +0.27 | −0.11 | +0.03 |
| **`cell_promiscuity_rate`** | **−0.06** | +0.31 | **+0.33 *** | **+0.33 *** | −0.11 | −0.05 |
| `mean_n_touched_when_engaged` | +0.01 | +0.28 | **+0.31 ***| **+0.37 *** | −0.14 | +0.03 |
| `p_carousel_click` | +0.24 | **+0.97 *** | **+0.80 *** | +0.09 | +0.03 | +0.22 |
| `mean_touched_fraction` | −0.02 | +0.31 | **+0.33 *** | **+0.33 *** | −0.14 | −0.00 |

(* nominal *p* < 0.05; none survive Bonferroni at α′ = 0.0017 across 30 tests. `p_carousel_click` × `p_dd_top_click` = +0.97 is a near-tautology sanity check — they measure overlapping click surfaces.)

**The dissociation that defines this axis:**

1. **Independent of `p_ad_survey`** (gaze prior, ρ ≈ −0.06 to +0.04 for the four shopping metrics). The gaze prior tells you *which surface a user expects value from*; cell promiscuity tells you *how many options they sample once they're in that surface*. Different operations, different traits.
2. **Correlated with `regression_rate`** (sat-opt axis, ρ ≈ +0.33). Promiscuous samplers are also organic-regressors. But +0.33 leaves ~89% of variance unexplained, so cell promiscuity is *adjacent to* sat-opt, not the same.
3. **Correlated with `p_ad_click`** (ρ ≈ +0.33), which is also adjacent-but-not-identical. The +0.97 correlation with `p_dd_top_click` reflects the within-surface near-tautology (clicking *any* dd_top cell ≈ clicking dd_top), not a substantive finding.

The cleanest read: cell promiscuity sits **between** sat-opt (organic-side deliberation) and ad-click (surface-side outcome), without collapsing into either. It's a within-surface deliberation depth measure — and the gaze-prior axis (`p_ad_survey`) is upstream of *which* surface gets deliberated.

---

## §5 Implications

**For the prior-elicitation methodology**: cell promiscuity demonstrates that the same cursor instrument resolves *two* trait-level individual differences when you change the spatial grain:
- Parent bbox (`p_dd_top_click`): outcome-level — *did you click an ad*
- Cell bbox (`cell_promiscuity_rate`): process-level — *how many cards did you sample inside the ad*

Both signals come from the same cursor stream; the resolution comes from the cell-aware cascade (post-2D-merge state). The paper-frozen v1.0.0 substrate has parent only.

**For downstream cognitive modeling**: within-surface deliberation depth is a candidate cognitive primitive distinct from between-surface allocation. A user who reaches dd_top and samples 4 cells before committing is in a different cognitive mode than one who clicks the first cell on contact. The task model currently has phase boundaries (Orient / Survey / Evaluate) but no within-AOI sampling depth term. This measure is the empirical handle for it.

**For the AllSERP arxiv update**: the v1.0.0-anchored methods paper reports per-AOI labels at the result level. The arxiv update can use the cell-aware cascade (now on AR main + the live `site/replay/` demo) to introduce within-AOI sampling as a graded-relevance refinement, with this finding as the construct-validation companion.

---

## §6 Limitations

- **n = 47**, single cohort. 95% CIs at ρ ≈ +0.33 are roughly [+0.04, +0.57] (Fisher-z, n=46) — wide enough that the "moderate effect" reading is the honest one.
- **Multiplicity**: 30 correlation tests reported; none survive Bonferroni at α′ = 0.0017. The trait reliability evidence (§3) is the strongest part of the finding; the §4 correlations are exploratory.
- **Coverage**: 56% of trials have dd_top cells. Participants with few dd_top exposures (n ≤ 8 of their 60 trials) would have unreliable per-participant estimates — the §3/§4 stats are restricted to the n ≥ 8 cohort (all 47 qualify).
- **Click attribution to gap regions** (~10% of carousel clicks fall in inter-card gaps, per the AF bulk cellsplit summary) is partly mitigated by midpoint-split bboxes but introduces a small under-count in `p_carousel_click`. Doesn't affect the touch-based metrics (cell_promiscuity_rate, mean_touched_fraction).
- **Replication**: this finding should be re-run on Schul or a second AdSERP cohort before treating as established. The split-half reliability is strong enough that a pre-registered single-test correlation against `p_ad_click` is the natural next test.

---

## §7 Files

- `scripts/dd_top_cell_segmentation.py` — analysis driver.
- `scripts/output/dd_top_cell_segmentation/per_participant.csv` — n=47 × 7 metrics.
- `scripts/output/dd_top_cell_segmentation/summary.json` — reliability + correlation tables, definitions, coverage stats.
