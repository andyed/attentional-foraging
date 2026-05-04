# LF/HF rank gradient under organic_hybrid

_Generated 2026-05-03 by `scripts/lfhf_rank_gradient_hybrid.py`._

**N trials**: 2,452 | **N (trial, pos) records**: 6,340

## Per-position medians

| Pos | N | median | Q25 | Q75 | 95% CI on median |
|---|---|---|---|---|---|
| 0 | 1,488 | 27.93 | 12.98 | 57.02 | [25.97, 30.47] |
| 1 | 1,035 | 21.54 | 8.89 | 43.15 | [19.48, 23.35] |
| 2 | 841 | 17.83 | 7.41 | 39.54 | [16.38, 19.71] |
| 3 | 692 | 17.01 | 7.34 | 36.88 | [15.39, 18.86] |
| 4 | 639 | 17.18 | 7.59 | 37.36 | [15.41, 19.61] |
| 5 | 403 | 15.38 | 6.21 | 32.35 | [12.96, 16.54] |
| 6 | 322 | 12.83 | 5.70 | 30.59 | [11.03, 15.44] |
| 7 | 223 | 15.48 | 6.02 | 34.98 | [12.06, 17.54] |
| 8 | 177 | 16.37 | 5.09 | 30.85 | [12.42, 17.89] |
| 9 | 156 | 12.86 | 6.11 | 32.41 | [10.29, 15.39] |
| 10 | 116 | 15.39 | 5.83 | 32.89 | [10.26, 22.38] |
| 11 | 118 | 11.13 | 5.03 | 24.69 | [7.76, 15.51] |
| 12 | 74 | 17.27 | 7.34 | 29.27 | [11.82, 24.76] |
| 13 | 34 | 12.04 | 5.82 | 36.18 | [7.98, 29.62] |
| 14 | 13 | 12.48 | 6.53 | 34.08 | [6.53, 34.08] |
| 15 | 8 | 13.79 | 4.89 | 22.31 | [1.93, 30.49] |
| 16 | 1 | 1.51 | 1.51 | 1.51 | [nan, nan] |

## Cross-trial Spearman on position medians

- **Full**: rho = -0.765, p = 3.50e-04, N = 17 position medians
- **Steep (P0-P3)**: rho = -1.000, p = 0.00e+00, N = 4
- **Plateau (P4-P10)**: rho = -0.214, p = 6.45e-01, N = 7

## Pooled steep vs plateau (Mann-Whitney on raw segments)

- U = 4,798,635, p = 2.29e-25 (one-sided, steep > plateau)
- Steep median 22.15 (N = 4,056)
- Plateau median 15.41 (N = 2,036)

## Cap-10 audit (per-participant <=10 segments per rank)

- Full: rho = -0.733, p = 8.19e-04
- Steep: rho = -1.000, p = 0.00e+00
- Plateau: rho = -0.500, p = 2.53e-01

## Per-trial Spearman rho (rank vs LF/HF within trial)

| Min segments | N trials | median rho | % negative |
|---|---|---|---|
| >=3 | 1,078 | -0.400 | 61.8% |
| >=5 | 264 | -0.200 | 62.5% |
| >=7 | 47 | -0.143 | 61.7% |