# LF/HF is confounded with window duration — NB14:K6 does not survive, K3 shrinks

**2026-08-16.** `[LAB, AdSERP, see §5 on rank-type]`

Found while auditing an LF/HF pipeline on a collaborator corpus; the confound is a property
of the **statistic**, not of any one dataset, so it was carried back to AdSERP. Companion write-up:
`collab/allawati-ai-overviews/lfhf-diagnostic-2026-08-16/FINDINGS.md`.

## The mechanism

LF/HF rises with observation length regardless of what is being observed. The LF band
(0–1.6 Hz) needs long windows before its slow oscillations enter the variance; the HF band
(1.6–4 Hz, periods 0.25–0.6 s) saturates almost immediately. The ratio therefore climbs with
duration until LF saturates.

Synthetic control — 1/f pink noise, no behaviour, 300 reps per length, at 120 Hz:

| window | 1 s | 2 s | 4 s | 8 s | 16 s | 24 s | 32 s |
|---|---|---|---|---|---|---|---|
| median LF/HF | 1.73 | 2.40 | 3.11 | 3.77 | 4.62 | 5.13 | 5.30 |

Pure duration produces a 3× swing.

In AdSERP: **Spearman(n_samples, LF/HF) = +0.310, p = 2.7e-122** (n = 5,461 valued positions).
Present at +0.296 to +0.310 under every rank-type flavor, so it is not an attribution artifact.

Duchowski's 1-second minimum guarantees a *stable* estimate. It does not make estimates from
different-length windows *comparable*. Every LF/HF comparison across conditions that differ in
dwell time inherits this.

## K6 — clicked vs non-clicked: does not survive

Unmatched, on `-typed`: clicked 25.35 (N=1358) vs non-clicked 20.40 (N=4103), p = 8.1e-08.

But clicked windows are **1.34× longer** (median 340 vs 253 samples). Stratifying by
`n_samples` decile:

| window (samples) | clicked | non-clicked | n_c | n_nc | p |
|---|---|---|---|---|---|
| 150–166 | 14.90 | 12.24 | 84 | 486 | 0.33 |
| 166–185 | 11.70 | 12.75 | 75 | 448 | 0.99 |
| 185–208 | 12.01 | 14.73 | 95 | 464 | 0.11 |
| 208–235 | 14.84 | 16.78 | 120 | 425 | 0.28 |
| 235–269 | 18.87 | 18.71 | 108 | 431 | 0.82 |
| 269–316 | 20.89 | 22.66 | 141 | 404 | 0.89 |
| 316–375 | 23.82 | 24.74 | 135 | 411 | 0.98 |
| 375–469 | 28.73 | 24.90 | 171 | 372 | 0.33 |
| 469–653 | 33.85 | 28.40 | 180 | 365 | 0.25 |
| 653–3684 | 43.03 | 37.99 | 249 | 297 | 0.22 |

**0 of 10 deciles significant**, and in five of them non-clicked is nominally higher. Meanwhile
LF/HF nearly triples down the length axis (14.9 → 43.0). The duration effect is an order of
magnitude larger than the effect K6 claims, and once duration is held fixed nothing remains.

**K6 should be treated as retired pending a length-controlled re-derivation.** The
interpretation attached to it — "users invest more effort in items they commit to" — is not
supported by this statistic. Users *dwell longer* on items they commit to, which is a much
weaker and already-known claim.

## K3 — position gradient: real but far smaller than published

Published: Spearman(position, median LF/HF) = −0.673, p = 0.023.

Two problems compound.

**(a) Duration.** Spearman(position, median window) = **−0.855, p = 0.0008** — the dwell
gradient across positions is *stronger* than the LF/HF gradient. Position → dwell → LF/HF is
an available complete explanation.

**(b) Correlating medians inflates rho.** K3 is computed on 11 per-position medians. Within
the tightest length-control stratum available (windows 150–166 samples, i.e. 1.00–1.11 s,
n=570), the medians-based rho is −0.891 (p=0.0002) but the same data on **raw observations**
gives **rho = −0.159 (p=0.0001)**, or −0.127 (p=0.005) for positions 1–10 only.

So a real negative gradient does survive length control — but at roughly a fifth of the
published magnitude, and the published figure owes much of its size to aggregating before
correlating. **K3 should be restated on raw observations with length control**, not retired.

## What is unaffected

Comparisons between windows of *similar* duration — on the collaborator corpus that is a
within-widget contrast (first pass vs revisit). Any AdSERP claim where the compared
conditions have matched dwell distributions is likewise untouched — but that has to be
checked per claim, not assumed.

## Two provenance issues found in passing

**1. NB14 cell 2 loads the same file twice.** Both `bw_data` (labelled "organic-rank,
primary") and `bw_data_abs` (labelled "absolute-rank legacy, for robustness") open
`butterworth-lfhf-by-position-typed.json`. A separate
`butterworth-lfhf-by-position-organic.json` exists and is not loaded. The robustness section
therefore compares a file against itself, and the Key Claims block's "organic-rank" rank-type
tag does not match the file actually read. Under this repo's own rank-type disclosure rule
that is a citation bug.

**2. The published K6 tuple does not reproduce from any single flavor file.**

| file | rows | clicked | non-clicked | p |
|---|---|---|---|---|
| `-typed` | 5461 | 25.35 | 20.40 | 8.1e-08 |
| `-organic` | 4428 | **23.53** | 18.03 | 5.0e-10 |
| `(base)` | 6099 | 22.40 | **19.27** | **7.5e-06** |
| **published K6** | N=1165/2829 | **23.53** | **19.27** | **7.5e-06** |

The clicked median matches `-organic`; the non-clicked median and p match `(base)`. This may
be explained by a notebook-level filter I did not replicate (the N values match none of my
counts), but it needs verifying before K6 is quoted again — independently of the duration
problem above.

## Reproduce

```bash
.venv/bin/python collab/allawati-ai-overviews/lfhf-diagnostic-2026-08-16/lfhf_window_diagnostic.py
```

AdSERP tests were run directly against `AdSERP/data/butterworth-lfhf-by-position-*.json`;
no re-derivation from raw pupil was needed because `n_samples` is already stored per position.
