# The survey-to-evaluate saccade-amplitude transition, as a sidecar

**Tags:** `[LAB, AdSERP]` · scroll-aware saccades (`docs/methodology/scroll-aware-saccades.md`) · no AOI dependence
**Producer:** `scripts/survey_amplitude_transition.py` → `scripts/output/survey_amplitude_transition/summary.json` (2026-10-11). Mirrors `notebooks-v2/13_survey_phase.ipynb` cells 3/5/7/9 line for line; the `all` cohort reproduces the notebook's 2026-06-03 executed output to the printed digit.
**Key Claims:** `[NB13:K1–K8, K20–K22]`
**Why it exists:** the Leaky Cursor manuscript (§3.3) grounds its fifth-fixation cut on this transition and, until 2026-10-11, quoted the pre-scroll-aware clamped pair (107.8 / 69.4 px, N = 2,754) with a citation to the AllSERP paper, which does not report them. NB13 had no sidecar; now a paper can name a file.

## Numbers (cohort `all`: every trial with a mouse CSV, 2,768 loaded of 2,776)

| Quantity | Value |
|---|---|
| Survey median amplitude, saccades 1–5 (K5) | 107.4 px (N = 13,671 saccades) |
| Evaluate median, saccades 6–30, first-30 cap (K6) | 69.9 px (N = 61,001) |
| Evaluate median, saccades 6+, no cap | 68.9 px (N = 197,764) |
| Ratio K5 / K6 (K7) | 1.54× |
| Mann–Whitney survey > evaluate (K8) | *p* underflows to 0 in IEEE-754 (U = 5.72 × 10⁸) |
| Trials with ≥ 10 saccades (K1) | 2,748 |
| Mean per-trial Spearman ρ, first 20 saccades (K2) | −0.133; *t* = −29.41, *p* = 1.50 × 10⁻¹⁶⁵ (K3) |
| Trials with ρ < 0 (K4) | 72.0 % |
| Participants whose median ρ < 0 (K20) | 46 / 47; sign *p* = 3.4 × 10⁻¹³, Wilcoxon *p* = 1.3 × 10⁻⁹ (K21) |

Per-saccade medians (px): 123.8, 136.0, 113.3, **87.5**, 80.5, 74.7, 74.3, 72.8, 70.2, 74.1 for saccades 1–10. The midpoint between the two phase medians is 88.6 px; the per-index median first falls below it at saccade 4, the saccade that lands on the fifth fixation. That is the sense in which the manuscript's "end of the fifth fixation" cut sits at the transition.

## Cohort `typed` (minus the 12 alignment-suspect trials)

2,756 trials loaded, 2,736 with ≥ 10 saccades. Medians unchanged at 107.4 / 69.9 px; mean ρ = −0.132, *p* = 1.6 × 10⁻¹⁶⁴, 72.0 % negative, 46 / 47 participants. The exclusions do not touch the result; quote whichever cohort matches the corpus a paper states (Leaky Cursor states 2,776, so `all`).

## Stale values to stop quoting

107.8 / 69.4 px, N = 2,754, ρ = −0.135, *p* = 9.33 × 10⁻¹⁶⁸ are the pre-2026-06-03 clamped-coordinate values (`scripts/output/verify_nb13_post_bugfix/summary.json` records that generation). `docs/findings.md` §3b carried them until 2026-10-11.
