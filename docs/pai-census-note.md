# PAI on AdSERP — open notebooks

Three working notebooks applying gaze-regression and Peripheral Attention Index
(PAI) analysis to a public SERP eye-tracking corpus. Posted for anyone in the
ETTAC 2026 session to look over ahead of Lyon.

- [`33_intra_patch_reading.ipynb`](../notebooks-v2/33_intra_patch_reading.ipynb) — within-element (intra-patch) reading-direction census
- [`34_regression_load_coupling.ipynb`](../notebooks-v2/34_regression_load_coupling.ipynb) — regression × pupil-load coupling test
- [`35_pai_census.ipynb`](../notebooks-v2/35_pai_census.ipynb) — PAI census and orphan-fixation recovery

**Sources:**
- PAI method: Duchowski, Gehrer & Svaldi, *Peripheral Attention Index (PAI):
  Area-Weighted Distal Polygonal Areas Of Interest*, to appear, ETTAC 2026
  (ICPR 2026 Workshops, Lyon). Implementation in NB35 is derived from the
  published abstract only — proceedings not yet available to check against;
  documented assumptions and open questions are in the notebook header.
- Corpus: AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025; Zenodo 15236546).
- AOI geometry: AllSERP (arXiv:2605.04949).

Andrew — flagging in case the OGD/vertex-vs-boundary distinction or the
alpha functional form in NB35 differs from what's in the paper; happy to
correct. Anyone else in the session, comments/issues welcome.
