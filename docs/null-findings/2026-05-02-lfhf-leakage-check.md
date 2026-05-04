# Peri-click LF/HF "drops toward the click" — Butterworth filtfilt leakage retraction

**Date filed:** 2026-05-02
**Status:** finding retracted; the peri-click LF/HF drop is plausibly a Butterworth-filtfilt edge-leakage artifact at the same scale as the SG-VLF leakage retired earlier today on the RIPA2 leg.
**Companion to:** `2026-05-02-peri-click-ripa2-sg-leakage.md` (RIPA2 leg). Together: both legs of the time-locked dissociation slide retire under the same audit class — filter memory smears post-event signal into the pre-event test window.

## What was claimed

Slide 5 of `ripa2-team-thursday-findings.pdf` (Thursday) and the merged peri-click slide of `ripa2-team-thursday-findings-v2.pdf` (today, prior to this revision):
*LF/HF drops toward the click — post-window mean 0.2 vs early baseline 82, time-locked across click + last fixation.*

Reading was: phasic-tonic dissociation at the peri-click temporal scope; LF/HF tonic load relaxes as the user commits.

## Why it doesn't hold

`scripts/lfhf_around_click.py:90-98` computes per-sample LF/HF as:
```python
lf_b, lf_a = butter(2, [0.04 / nyq, 0.15 / nyq], btype='band')
hf_b, hf_a = butter(2, [0.15 / nyq, 0.40 / nyq], btype='band')
lf = filtfilt(lf_b, lf_a, pupil)   # zero-phase IIR
hf = filtfilt(hf_b, hf_a, pupil)   # zero-phase IIR
return (lf ** 2) / (hf ** 2 + 1e-9)
```

`filtfilt` is acausal — it convolves the signal forward, time-reverses, and convolves again — producing a zero-phase output at the cost of bidirectional filter memory. For a 2nd-order Butterworth bandpass at LF=[0.04, 0.15] Hz, the filter response decays over multiple periods of the lowest cutoff. **One LF period at 0.04 Hz is 25 seconds.** Filter memory at this scale is much larger than the 4-second peri-click analytic window, so any post-event step in pupil dynamics at *t* = 0 reaches every sample of the test window in advance.

## Two independent probes

**Probe 1 — synthetic step impulse.** Pass a 30-sec signal `pupil = 5.0 mm with step to 5.5 mm at midpoint` through the same Butterworth+filtfilt pipeline:
- `filtfilt` pre-event contamination begins at *t* ≈ **−15,000 ms** (deviation > 20% of far-baseline value).
- Pre-event mean ≈ post-event mean (0.73 vs 0.73), because filtfilt is acausal — the response to the post-event step is identical in both directions.
- Even the "far baseline" reading (>5 sec from event) is contaminated by trial-edge transients; there is no leakage-clean zone within a typical AdSERP trial length using this filter.

**Probe 2 — empirical signature in real data.** From `scripts/output/lfhf_around_click/summary.json`:

| event-lock | baseline_mean | pre_window_mean | post_window_mean | pre/baseline ratio |
|---|---|---|---|---|
| `lfhf_click` (n=2,662) | 82.26 | **16.20** (1.5 sec pre-click) | 0.20 | 0.197 |
| `lfhf_lastfix` (n=2,660) | 87.76 | **25.94** (1.5 sec pre-fixation) | 2.84 | 0.296 |

LF/HF is already 5× lower than baseline in the pre-click window — the "drop" is **already underway 1.5 sec before the click**. A real causal cognitive-state transition toward the click would show drop sharpness at *t* = 0; the observed gradual ramp is the filter memory signature.

The Wilcoxon `w_pre_gt_baseline_p = 1.0` in the summary — recorded as part of the original sanity check — confirms the pre-window is *lower*, not higher, than baseline. The slide's narrative of "drops toward the click" elides that the drop has already happened *before* the click.

## What survives

- **The two-tool framing position is unchanged**: RIPA2 for per-fixation phasic, LF/HF for windowed tonic. Both instruments retain their non-event-locked roles. The asymmetric framing previously asserted ("RIPA2 leaks, LF/HF doesn't") is wrong; both leak under the same edge-leakage class. The right framing is: **event-locked tests of either signal must respect the analytic filter span**, and for a 0.04 Hz LF cutoff there is no leakage-clean window inside a 4-sec analytic span.
- **The Position-gradient / two-band engagement claim** (NB14 K6 / K9 / K3) is unaffected — those are per-(trial, position) integrals over the full trial, not event-locked, no edge-leakage exposure.
- **The Click-rate × RIPA2 × LF/HF quadrant** (NB18 K7-K10 bbox-pending) is unaffected — same reason; aggregated over the trial, no event lock.

## What this means for the project

Three RIPA2 / LF/HF findings have now been retracted in 2026-05:

1. **Per-fixation will-regress vs no-regress amplitude dissociation** (`r1-ripa2-bbox-collapse.md`) — rank-pooling artifact under absolute attribution.
2. **Peri-click RIPA2 pre-decision peak** (`2026-05-02-peri-click-ripa2-sg-leakage.md`) — SG-VLF leakage.
3. **Peri-click LF/HF drop toward the click** (this file) — Butterworth filtfilt leakage at the same temporal scale.

Both event-locked retractions reinforce a project rule: **for any event-locked test of a smoothed/filtered pupil signal, the test window must clear the filter span on both sides of the event, and the filter memory must be quantified before claims**. AdSERP's analytic window (4 sec around event) is too short to clear a 0.04 Hz LF cutoff (~25 sec period). Any event-locked LF/HF claim will need either (a) a longer analytic window (15–30 sec), (b) a higher LF cutoff that compresses the filter span, or (c) a causal filter (lfilter) with explicit transient padding.

For the Thursday deck (`ripa2-team-thursday-findings-v2.pdf`): the merged Peri-click pupil-dynamics slide is removed. The change-notes slide records the retraction.

## Producer + reproduction

- Probe script: `/tmp/lfhf_leakage_check.py` (synthetic step impulse).
- Empirical signature: `scripts/output/lfhf_around_click/summary.json` lines 28-46 (lfhf_click, lfhf_lastfix per-window means).
- Filter implementation under audit: `scripts/lfhf_around_click.py:90-98`.

## Cross-references

- `docs/null-findings/2026-05-02-peri-click-ripa2-sg-leakage.md` — RIPA2 sibling retraction.
- `docs/null-findings/r1-ripa2-bbox-collapse.md` — earlier RIPA2 retraction under bbox attribution.
- `feedback_lfhf_polarity_before_pathology.md` — diagnostic-order rule (polarity before pathology); this file is its companion for the *temporal* axis (filter span before event-lock).
