# Knee position by satopt — organic_hybrid

_Generated 2026-05-03 by `scripts/knee_by_satopt.py`._

**N trials**: 2,229  (regression-rate median split at 0.567)

## By median split

| Group | n | median knee | p25 / p50 / p75 | mean |
|---|---|---|---|---|
| satisficer | 896 | P2 | P1 / P2 / P3 | 1.94 |
| optimizer | 1,333 | P1 | P1 / P1 / P3 | 1.84 |

**Mann-Whitney (optimizer vs satisficer)**: two-sided *p* = 2.24e-02, one-sided (optimizer > satisficer) *p* = 9.89e-01

## By tercile

| Tercile | n | median knee | p25 / p75 | mean |
|---|---|---|---|---|
| low | 727 | P2 | P1 / P3 | 2.03 |
| mid | 812 | P2 | P1 / P3 | 1.92 |
| high | 690 | P1 | P1 / P2 | 1.68 |