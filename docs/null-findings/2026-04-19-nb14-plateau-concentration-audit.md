# NB14 Plateau Concentration Audit (ETTAC queue item 1)

**Date:** 2026-04-19
**Notebook:** NB14 `14_butterworth_cognitive_load`
**Script:** `scripts/lfhf_per_position_concentration.py`
**Output:** `scripts/output/lfhf_per_position_concentration/`

## Motivation

NB14:K11 reports plateau (P4–P10) Spearman ρ = −0.714, *p* = 0.071 — marginal.
If a handful of participants contributed the bulk of segments at deep positions,
the plateau claim would be small-*n* rather than a population-level shape, and
the ETTAC brief should not lean on it quantitatively. Parallels the NB28 P6+
viewport-bands audit pattern.

## Concentration stats (per-position)

Segment counts (valid LF/HF only) and how concentrated each position's sample is
across the 47 participants:

| Pos | N_seg | N_part | top4 | top6 | top10 | Gini |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1,036 | 46 | 16.3% | 23.3% | 36.8% | 0.30 |
| 1 | 1,132 | 46 | 14.7% | 21.5% | 34.3% | 0.23 |
| 2 | 1,174 | 46 | 13.4% | 19.6% | 31.4% | 0.20 |
| 3 |   887 | 46 | 15.1% | 21.3% | 32.7% | 0.21 |
| 4 |   601 | 43 | 19.8% | 27.1% | 40.1% | 0.28 |
| 5 |   437 | 44 | 22.4% | 30.4% | 44.2% | 0.35 |
| 6 |   316 | 38 | 24.7% | 35.1% | 51.3% | 0.34 |
| 7 |   236 | 40 | 22.9% | 32.2% | 49.6% | 0.39 |
| 8 |   153 | 34 | 27.5% | 37.9% | 57.5% | 0.39 |
| 9 |    90 | 25 | 37.8% | 50.0% | 68.9% | 0.38 |
| 10|    37 | 18 | 48.7% | 59.5% | 78.4% | 0.35 |

Total: **6,099** segments (NB14:K2 = 6,112; 13 discrepancy is rounding-to-null at
segments with exactly MIN_SAMPLES-1 — within tolerance).

**Verdict on concentration:** P0–P3 are balanced. P4–P7 are moderately
concentrated. P8–P10 are heavily concentrated — P9 (N=25) and P10 (N=18) drop
below full-cohort representation. The concentration rises with depth because
participants who scroll deep are a self-selecting subset.

## Sensitivity: does the plateau gradient survive per-participant downsampling?

Random cap on segments-per-participant-per-position, then recompute position
medians and Spearman ρ over each range.

| Cap | Full (P0–P10) | Steep (P0–P3) | Plateau (P4–P10) |
|:---|:---:|:---:|:---:|
| cap3     | ρ = −0.755, p = 0.0073 | ρ = −0.400, p = 0.60 | ρ = −0.464, p = 0.29 |
| cap5     | ρ = −0.764, p = 0.0062 | ρ = −1.000, p ≈ 0 | ρ = −0.393, p = 0.38 |
| cap10    | ρ = −0.945, p = 1.1e-5 | ρ = −1.000, p ≈ 0 | **ρ = −0.786, p = 0.036** |
| cap20    | ρ = −0.918, p = 6.7e-5 | ρ = −1.000, p ≈ 0 | ρ = −0.679, p = 0.094 |
| uncapped | ρ = −0.927, p = 4.0e-5 | ρ = −1.000, p ≈ 0 | ρ = −0.714, p = 0.071 |

**Cap-10 is the informative row.** It caps the heaviest contributors while
leaving most of the cohort intact. Under cap-10 the plateau gradient
*strengthens* to ρ = −0.786 (p = 0.036) — the opposite of what we'd see if a
few participants were driving K11. The weakening at cap-3 / cap-5 reflects loss
of power (median over ~1–2 segments per participant is noisy at depth), not
concentration.

## Bootstrap CIs (participant-cluster, 2,000 resamples)

Participant-level cluster bootstrap to get proper CIs given that segments within
a participant are not independent.

| Cap | Full median [95% CI] | Steep [95% CI] | Plateau [95% CI] |
|:---|:---|:---|:---|
| cap3     | −0.655 [−0.900, −0.255] | [−1.000, −0.400] | [−0.821, +0.429] |
| cap5     | −0.755 [−0.927, −0.373] | [−1.000, −0.600] | [−0.893, +0.250] |
| cap10    | −0.836 [−0.955, −0.473] | [−1.000, −0.800] | [−0.893, +0.179] |
| cap20    | −0.864 [−0.955, −0.545] | [−1.000, −0.800] | [−0.893, +0.143] |
| uncapped | −0.873 [−0.964, −0.573] | [−1.000, −0.800] | [−0.893, +0.143] |

**Full K3 and steep K10 are unambiguous** — CIs always negative, steep CI
tight around ρ ≈ −1.

**Plateau K11 is genuinely noisy** — the 95% CI crosses zero under every cap,
even uncapped. The marginal *p* = 0.071 is driven by only 7 position medians,
not by participant concentration.

## Verdict for ETTAC

1. **K3 (full range) is robust** — cite quantitatively. Cap-10 actually
   strengthens it (ρ = −0.945). Bootstrap CI [−0.964, −0.573] uncapped.
2. **K10 (steep phase) is rock-solid** — ρ = −1.000 across every cap;
   bootstrap CI [−1.000, −0.800]. This is the load-bearing claim.
3. **K11 (plateau) is directional but noisy at depth** — cite qualitatively
   as "flatter, marginal gradient." Do NOT lead with the plateau ρ. The
   bootstrap CI crossing zero is the honest framing.
4. **K9 (Mann–Whitney on segments, N_steep=4,229 vs N_plat=1,870)** is
   unaffected by this audit — segment-level tests have enormous power
   regardless of position-median concentration. Cite K9 to anchor the
   steep-vs-plateau contrast.

## Implications for the brief

Current brief leads with K3 (ρ = −0.927). That's justified — audit
confirms — but the pedagogically stronger framing is:

- **Lead:** K10 (steep-phase perfect monotone) + K9 (segment-level
  MW p = 3.2e-23) — the "scent model crystallizes" phase.
- **Back:** K3 (full range) as the robustness-convergent statistic.
- **Caveat K11 qualitatively** — the plateau is "where the gradient
  flattens," not "where ρ = −0.714 certifies a weaker slope."

No changes to NB14 Key Claims values. K11's interpretation note could
be updated to cite this audit.

## Null-finding framing

Not a null. This is a *concentration audit that confirms the headline* and
clarifies the plateau claim's uncertainty source. Filed in `null-findings/`
because the file-drawer cost of not documenting K11's CI is the same as for
any negative check — a future reader needs to know what was verified.
