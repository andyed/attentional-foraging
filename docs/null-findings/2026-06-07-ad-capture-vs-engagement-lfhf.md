# Ad attention decomposes: bottom-up CAPTURE vs dispositional ENGAGEMENT — and LF/HF rides with Capture

**Date:** 2026-06-07
**Status:** INTERNAL. Touches LF/HF (mean_lhipa) → Duchowski-sensitive; coordinate any disclosure.
**Scripts (CRForager repo):** `scripts/ad_engagement.py` (the decomposition), `scripts/af_backprop_lfhf.py` (the LF/HF dissociation).
**Trait artifact:** `crforager/results/fitted_ad_aversion_stay.csv` — per-user CR-fitted `ad_penalty` (+CI), join on `participant`.

## The finding (two parts)

Ad attention is not one thing. Decompose each ad fixation into the **first** (arrival) and **whether a
second follows**:
- **CAPTURE** — ad-arrival rate (a fixation lands on an ad element). Bottom-up pull.
- **ENGAGEMENT** — `p_stay` = p(2nd fixation on the same ad | 1st). Top-down; whether you dwell.

These are behaviorally **dissociated**, and they have **different correlates** (per-participant, n=47;
median 382 ad-arrivals/user — dense):

| measure | p_ad_click | p_ad_survey | ad_over_index | regression_rate | **mean_lhipa** |
|---|--:|--:|--:|--:|--:|
| **CAPTURE** (1st-fixation pull) | +0.14 | −0.03 | −0.09 | −0.15 | **+0.29*** |
| **ENGAGEMENT** `p_stay` (2nd\|1st) | **+0.60*** | **+0.42*** | **+0.35*** | −0.22 | +0.09 |

(* perm-p < .05.) capture × p_stay = −0.33 (separable). So:
- **CAPTURE carries no ad disposition** (click +0.14 n.s.) but **is the LF/HF correlate** (+0.29*).
- **ENGAGEMENT is the ad disposition** (every ad measure significant) and is **not** the LF/HF correlate.

## The LF/HF dissociation (`af_backprop_lfhf.py`)

| | rho | perm-p |
|---|--:|--:|
| CAPTURE × mean_lhipa | +0.29 | 0.047 |
| ENGAGEMENT p_stay × mean_lhipa | +0.09 | 0.53 |
| **CR-fitted ad_penalty (disposition) × mean_lhipa** | **−0.06** | 0.69 |

Robustness of the CAPTURE × LF/HF link (partial Spearman): controlling for ad exposure
(`mean_ad_area_frac`) +0.25, gaze volume (`mean_fixations`) +0.24, engagement (`p_stay`) +0.34 — not an
exposure/volume artifact. **Polarity-agnostic:** we report the *association* with mean_lhipa, not a
load-direction interpretation (that is Duchowski's call).

Honest nuance: `p_stay × lhipa` controlling for capture is +0.21 (the capture–stay −0.33 coupling), so
`p_stay` itself isn't perfectly LF/HF-free. The clean load-free quantity is the **CR-fitted ad_penalty
(−0.06)** — the disposition isolated by the model.

## Why it matters for AF

1. **A new dissociation for the LF/HF series.** Bottom-up ad CAPTURE has an LF/HF signature; the
   ad-aversion DISPOSITION does not. This sits alongside `2026-04-19-lfhf-satopt-orthogonality` — LF/HF
   indexes the bottom-up/exogenous component of attention, dissociated from top-down strategy axes
   (satopt there, ad-disposition here).
2. **A model-derived covariate for AF.** `crforager/results/fitted_ad_aversion_stay.csv` is a per-user
   ad-aversion trait with a CR-parameter meaning and calibrated CI — identified from the dense gaze-stay
   signal (not sparse clicks), convergent with held-out ad-click (−0.58) and the survey prior (−0.41),
   LF/HF-free (−0.06). AF can join it on `participant` and stratify LF/HF / OSEC / LTR / click-prediction
   the way it uses measured `p_ad_survey` / `regression_rate`, but as an *engagement* trait rather than a
   raw count.

## Provenance
The decomposition came from the CRForager fit (`crforager/docs/notes/gaze-stay-fit.md`): per-user
`ad_penalty` was not identifiable from sparse ad-clicks; conditioning on the first fixation isolates the
disposition and makes it identifiable. The AF-level reading is the reverse — the model's parameter told
us *where in the gaze record the ad disposition lives*, and AF's own LF/HF data corroborates the split.
