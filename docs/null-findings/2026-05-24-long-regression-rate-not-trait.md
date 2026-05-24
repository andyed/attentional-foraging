# Long-regression-rate is not an individual-difference trait

**Date:** 2026-05-24
**Type:** Null on a candidate trait. Population-level structure exists; per-participant signature does not.
**Status:** Pre-noted before any task-model or paper consumption. Affects the framing of the dd_top Markov substrate as a per-participant transition-matrix object.

## TL;DR

The dd_top-topped substrate ([`scripts/output/dd_top_markov/`](../../scripts/output/dd_top_markov/)) shows a clean **population-level** asymmetry: short organic regressions (1–2 positions) are forward-biased (F:R ≈ 1.5:1), but long regressions (≥4 positions) are regression-dominant (F:R = 0.27–0.56). One natural follow-up was to test whether the *mix* — `long_regression_rate` = (n_regressions of size ≥4) / (n_regressions total) — is a stable per-participant trait, plausibly distinct from total regression rate. **It is not.** Split-half r = 0.257 (Spearman-Brown 0.408), below the trait floor.

The asymmetric long-regression tail is real but lives at population grain, not individual grain. Participants don't differ in *which kind* of regression they prefer; they differ in *how many* regressions they make.

## What was tested

Across 47 participants × 1,581 dd_top-topped trials (median 34 trials/participant), per-participant aggregates:

- `regression_per_trial` — fixation-level organic→organic backward transitions per trial
- `long_regression_per_trial` — same restricted to |delta| ≥ 4
- **`long_regression_rate`** — long_regressions / total_regressions (the candidate trait)
- `any_long_reg_trial_rate` — fraction of trials with at least one long regression
- `mean_regression_size` — mean |delta| across all regressions

Split-half reliability (random within-participant trial split, Spearman-Brown corrected to full length):

| Metric | r split-half | Spearman-Brown |
|---|---:|---:|
| `regression_per_trial` | 0.811 | **0.896** |
| `long_regression_per_trial` | 0.575 | 0.730 |
| `any_long_reg_trial_rate` | 0.579 | 0.733 |
| `mean_regression_size` | 0.418 | 0.589 |
| **`long_regression_rate`** | **0.257** | **0.408** |

Only `regression_per_trial` clears the strong-trait threshold (SB > 0.85). `long_regression_rate` specifically — the candidate that would identify "commit-jumpers" as a distinct sub-population — is unreliable. Two random halves of the same participant's trials disagree on whether they prefer long vs short regressions.

## What this means structurally

The population-level forward/regression asymmetry at size ≥4 (F:R = 0.27–0.56, n = 5,738 regressions) is not driven by a specialized sub-population of long-jumpers. Every participant's regression-size distribution is broadly the same shape; some just generate more of them.

This is the regression-size analogue of the existing chattiness finding: **rate is the per-participant signal; distribution shape is task-structural.** Cursor chattiness shipped as a stable trait (NB11.5, r > 0.96). Long-vs-short regression mix does not.

## What this means for the dd_top Markov substrate

Per-participant transition matrices on the dd_top-topped substrate remain useful, but:

- Clustering participants by **the long-regression *cells* of the transition matrix** (organic_5 → organic_1, organic_6 → organic_2, etc.) is the wrong cut — there is no clean cluster structure at that resolution.
- Clustering by **total regression activity in the matrix** is the right cut, and it reproduces the existing `regression_rate` axis (Spearman ρ = +0.693 between `regression_per_trial` here and the prior CSV's `regression_rate`, p < 10⁻⁷).
- Clustering by **the full row-distribution similarity** (transition-matrix KL divergence across participants) is the only path that could surface novel sub-populations beyond the existing axes. That remains untested.

## Side observation: cross-axis dissociation

The fixation-level organic regression rate (`regression_per_trial`, the only stable trait among the candidates here) is **fully independent** of the cell-promiscuity trait ([`dd-top-cell-promiscuity.md`](../dd-top-cell-promiscuity.md)):

| Pair | Spearman ρ | p | n |
|---|---:|---:|---:|
| `regression_per_trial` × `cell_promiscuity_rate` | +0.017 | 0.91 | 47 |
| `regression_per_trial` × `mean_touched_fraction` | +0.049 | 0.75 | 47 |
| `regression_per_trial` × `any_cell_engagement_rate` | +0.025 | 0.87 | 47 |

Organic regression (within the organic stream) and within-ad-carousel cell sampling are **different deliberation behaviors**. Both are stable per-participant traits (r > 0.8). Neither predicts the other. This extends the existing four-axis dissociation:

1. Sat-opt (regression rate — corroborated here at fixation grain)
2. Cognitive load (LHIPA — see caveat below)
3. Ad-utility prior (between-surface gaze allocation)
4. Cell promiscuity (within-ad-surface sampling)

…with the regression-rate axis now validated at fixation grain (not only scroll grain), and orthogonal to cell promiscuity.

## Caveat that the LHIPA correlation does *not* break

`regression_per_trial` correlates with `mean_lhipa` at ρ = −0.695 (p < 10⁻⁷) in this stratum. This matches the strength of the previously-noted ρ = −0.593 in the full corpus, which the **2026-04-16 satopt-LHIPA duration confound** ([`2026-04-16-satopt-lhipa-duration-confound.md`](2026-04-16-satopt-lhipa-duration-confound.md)) reframed: the raw correlation reproduces but collapses to ρ = +0.135 once trial duration is partialed out. The mechanism is duration → mean LHIPA (longer trials accumulate more low-LHIPA samples), not regression → load. The fixation-grain replication here inherits the same confound and the same reframe. Recorded for completeness; not a new finding.

## Addendum (2026-05-24): forward dwell does not predict regression distance

A second mechanism test in the same substrate, prompted by the
event-class finding ([`../long-regression-event-class.md`](../long-regression-event-class.md))
that long regressions are near-pure vertical saccades. Natural follow-up:
does the time spent at organic_K during forward scan predict the
distance from which the user regresses back to K? (The "anchor
hypothesis" — long jumps go to results the user deliberated on.)

**Null.** Across all 5,738 regression events:

| Test | Spearman ρ | p | n |
|---|---:|---:|---:|
| `dwell_at_destination_before` × `size` | **+0.004** | 0.75 | 5,738 |
| `dwell_at_source_before` × `size` | −0.023 | 0.08 | 5,738 |
| `total_forward_dwell_before` × `size` | +0.093 | <0.001 | 5,738 |

Restricting to revisits only (n = 5,189, where the destination *was*
previously fixated) tightens nothing: ρ = −0.007 (p = 0.61), and the
median regression size is identically 1 across all four prior-dwell
quartiles (means 1.39 / 1.45 / 1.43 / 1.40 from q1 to q4).

The +0.09 total-forward-dwell correlation is real but mechanistic-trivial:
trials that have run longer have visited more positions, so larger jumps
become *possible*. Coverage effect, not a deliberation effect.

**Side observation: 90.4% / 9.6% revisit / first-visit split.** When
users regress, 90% of the time the destination position had already
been fixated; 10% are first-visit landings where the user skipped past
that position during forward scan. Both subsets show the same size
distribution (~80% size 1). First-visit regressions aren't a special
"jumping into uncharted territory" event — they're back-fills of
skipped positions, indistinguishable in size from true returns.

**Reading-together with the event-class finding.** Long regressions
are near-pure vertical saccades (90% vertical share) with the cursor
lagging ~100 px further behind than for short regressions. Now this
addendum says the destination's prior dwell history is irrelevant to
how far back the user jumps. Together these rule out a
**dwell-as-anchor** model — long regressions are not "I'm returning
to the result I previously deliberated on."

That originally pointed toward a pure "position-as-landmark" model,
but the next mechanism test refines it: long regressions are
mostly *distance-based* with a smaller *absolute attractor* toward
the top of the organic stream. See Addendum 2.

## Addendum 2 (2026-05-24): regressions are mostly relative-distance; long ones have an absolute top-of-stream pull

Pure absolute landmark ("always go to result 2") would predict slope ≈ 0
when regressing `dest_pos` on `source_pos`. Pure relative distance ("always
back by N") would predict slope ≈ +1. The data fits neither extreme and
splits cleanly by regression size:

| Subset | n | slope (dest_pos ~ source_pos) | r | σ²(dest_pos) / σ²(size) | dest_pos ≤ 3 share |
|---|---:|---:|---:|---:|---:|
| short (size 1–2) | 5,159 | **+0.984** | +0.99 | 49.7 (distance highly anchored) | 58.9% |
| mid (size 3) | 274 | +1.000 | +1.00 | ∞ (size constant by definition) | 66.4% |
| long (size ≥ 4) | 305 | **+0.634** | +0.75 | 1.6 (distance and dest roughly equally variable) | **72.8%** |

**Short regressions are pure relative.** Slope ≈ +1, distance has 50× lower variance than destination position. Every short regression is essentially "decrement by 1" — destination = source − 1 (sometimes −2).

**Long regressions are mixed.** Slope = +0.63 (relative pull, but attenuated). Destination concentrates at positions 1–3 (73% of all long regressions land there). Modal destinations by source position:

```
source=5 → dest=1 (39/39, all back-by-4)       source=9  → dest=4 (back 5)
source=6 → dest=2 (75% modal, back 4)          source=10 → dest=5 (back 5–6)
source=7 → dest=3 (54% modal, back 4)          source=11 → dest=5 (back 6)
source=8 → split dest 3–4 (back 4–5)
```

There's a clean back-by-4-to-5 stride that holds up to source ≈ 8. Beyond that, the absolute attractor toward the top wins: deeper sources don't extend back proportionally; they cap around dest = 5 with sizes growing to 6.

**Refined mechanism.** Long regressions are *distance-controlled saccades with an absolute soft-cap near the top of the organic stream*. The relative stride (~4 positions back) does most of the work; the absolute attractor pulls deep-source events toward positions 1–3 when a pure-relative jump would overshoot the top. Not pure relative; not pure absolute; a relative-with-boundary model.

For the task model: the long-regression transition class has a parameterizable stride (mean ~4–5 positions) with a top-of-stream attractor as a soft constraint, not a hard landing target. Implementation: sample stride from a distribution, then clip to position ≥ 1 — or model as a mixture of "relative stride" and "return-to-top" components.

## Files

- `scripts/dd_top_regression_traits.py` — per-participant trait analysis (§1-§4)
- `scripts/output/dd_top_regression_traits/{summary.json, per_participant.csv}` — n=47 × 8 metrics
- `scripts/dd_top_regression_dwell_vs_size.py` — dwell-vs-size mechanism test (addendum 1)
- `scripts/output/dd_top_regression_dwell_vs_size/summary.json` — 5,738-event correlations
- `scripts/dd_top_regression_absolute_vs_relative.py` — absolute vs relative model test (addendum 2)
- `scripts/output/dd_top_regression_absolute_vs_relative/summary.json` — slope decomposition + destination histogram

## Reading order

1. [`docs/dd-top-cell-promiscuity.md`](../dd-top-cell-promiscuity.md) — the *positive* trait finding that motivated this analysis
2. This doc (§1-§4) — the *negative* trait finding on the regression-size mix
3. [`docs/long-regression-event-class.md`](../long-regression-event-class.md) — long regressions ARE event-distinct (saccade geometry + cursor-eye sync)
4. This doc (addendum) — but their distance isn't dwell-anchored (position-as-landmark, not item-anchored)
5. [`docs/null-findings/2026-04-16-satopt-lhipa-duration-confound.md`](2026-04-16-satopt-lhipa-duration-confound.md) — the LHIPA-confound reframe that this doc inherits
