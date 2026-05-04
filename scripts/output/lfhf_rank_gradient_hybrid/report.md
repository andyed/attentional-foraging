# LF/HF rank gradient under organic_hybrid

_Generated 2026-05-03 by `scripts/lfhf_rank_gradient_hybrid.py`._

**N trials**: 2,449 | **N (trial, pos) records**: 6,327

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
| 9 | 132 | 12.95 | 5.95 | 31.27 | [9.75, 15.66] |
| 10 | 109 | 13.17 | 4.87 | 33.99 | [9.38, 20.46] |
| 11 | 112 | 11.13 | 4.91 | 27.31 | [7.55, 15.97] |
| 12 | 74 | 17.27 | 7.01 | 31.08 | [11.59, 24.44] |
| 13 | 45 | 17.54 | 6.26 | 40.34 | [8.93, 27.41] |
| 14 | 20 | 13.22 | 6.68 | 32.24 | [7.09, 30.07] |
| 15 | 7 | 12.48 | 5.22 | 22.61 | [1.93, 28.20] |
| 16 | 6 | 10.07 | 6.68 | 31.40 | [3.26, 41.07] |
| 17 | 1 | 1.51 | 1.51 | 1.51 | [nan, nan] |
| 21 | 1 | 8.71 | 8.71 | 8.71 | [nan, nan] |

## Cross-trial Spearman on position medians

- **Full**: rho = -0.749, p = 2.23e-04, N = 19 position medians
- **Steep (P0-P3)**: rho = -1.000, p = 0.00e+00, N = 4
- **Plateau (P4-P10)**: rho = -0.393, p = 3.83e-01, N = 7

## Pooled steep vs plateau (Mann-Whitney on raw segments)

- U = 4,728,133, p = 2.62e-25 (one-sided, steep > plateau)
- Steep median 22.15 (N = 4,056)
- Plateau median 15.41 (N = 2,005)

## Cap-10 audit (per-participant <=10 segments per rank)

- Full: rho = -0.689, p = 1.09e-03
- Steep: rho = -0.800, p = 2.00e-01
- Plateau: rho = -0.393, p = 3.83e-01

## Per-trial Spearman rho (rank vs LF/HF within trial)

| Min segments | N trials | median rho | % negative |
|---|---|---|---|
| >=3 | 1,074 | -0.400 | 62.0% |
| >=5 | 260 | -0.200 | 62.3% |
| >=7 | 44 | -0.161 | 65.9% |