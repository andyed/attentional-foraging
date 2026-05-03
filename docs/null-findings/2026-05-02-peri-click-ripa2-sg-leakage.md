# Peri-click RIPA2 "fires before the click" — SG-VLF leakage artifact

**Date filed:** 2026-05-02
**Status:** finding retracted; pre-click RIPA2 elevation does not survive a leakage-clean test window.
**Affects:** Thursday RIPA2 findings deck slide 4 (Peri-click TEPR — RIPA2 fires before the click) and the RIPA2 leg of slide 5 (Time-locked dissociation). Both retired in `ripa2-team-thursday-findings-v2.pdf` build.

## What was claimed

Per-fixation RIPA2 around click events shows a population-averaged peak in the [−1500, −100] ms window before the click, *p* = 4.2 × 10⁻¹⁹ (Wilcoxon, per-event window mean vs early-baseline [−3000, −2000] ms). Matched non-clicked control fixations don't show the peak, *p* = 1.0 × 10⁻⁸ (Mann-Whitney, clicked vs control). Reading was: pre-decision pupil signal at fixation scale — the SERP-side analog of Gwizdka's 2022 talk-slide "largest pupil before relevance decision" claim, operationalized via RIPA2.

## Why it doesn't hold

RIPA2 is `SG_LF² − SG_VLF²` where SG_VLF is a Savitzky-Golay smoother with **window = 243 samples at 150 Hz = ±810 ms around each timepoint**. At any timepoint *t*, the SG-VLF value is computed from pupil data in [*t* − 810, *t* + 810] ms.

The original test window [−1500, −100] ms therefore has every timepoint after *t* = −810 ms reading post-click pupil data:
- At *t* = −100 ms (right edge of pre-window), SG-VLF spans [−910, +710] ms — **710 ms of post-click pupil dynamics smeared backward** into the "pre-click" RIPA2 value.
- ~57% of the [−1500, −100] window has at least some post-click contamination.

The early baseline [−3000, −2000] is fully pre-click — no leakage in the comparison side. So the asymmetry between windows is partly the SG-VLF smoother spreading post-click motor-execution / pupil-dilation activity backward, not signal.

The control trace (matched non-clicked fixation) doesn't absorb the artifact: random fixations don't have a specific post-event signal to smear backward, so the control-side comparison is not symmetric in the leakage either.

## Quantitative collapse

Same per-event arrays (*N* = 2,662 click events), per-event Wilcoxon (alternative='greater', same statistic on pre-window vs early-baseline window):

| Pre-window | MEAN vs MEAN | PEAK vs PEAK | MEDIAN vs MEDIAN |
|---|---|---|---|
| Original [−1500, −100] (contaminated) | **4.2 × 10⁻¹⁹** | 5.6 × 10⁻⁷¹ | 1.0 |
| **Leakage-clean** [−1500, −900] (SG-VLF entirely pre-click for every *t*) | **0.196 (n.s.)** | 1.0 (n.s.; direction reverses) | 0.003 |
| Strict [−2000, −900] | 0.010 | 1.0 | < 0.001 |

The mean test drops 18 orders of magnitude when the leakage zone is excluded. The peak test outright reverses direction in the clean window. The only marginal positive shift is in the median (clean *p* = 0.003), but the magnitude is small and the mean test refusing to track it suggests this isn't a clean pre-decision rise either.

## What survives

- **The peri-click LF/HF dissociation** is unaffected by SG-VLF leakage because LF/HF is a band-limited power ratio computed over a defined window, not an SG-derivative smoother. The "LF/HF moves opposite, dropping toward the click" component of the time-locked dissociation slide stands as written.
- **The RIPA2 unique-instrument story** for *non-event-locked* claims — per-fixation amplitude, per-(trial, position) aggregates, click-rate quadrant cross-products — remains valid. RIPA2 still carries unique signal at scales where the SG-VLF smoother span is small relative to the analytic window.
- **Per-fixation RIPA2 dissociation under bbox attribution** — already retracted on a separate basis (rank-pooling artifact, see `r1-ripa2-bbox-collapse.md`). This null-finding is a second, independent retirement of the peri-click variant.

## Two-tool framing intact

Despite the peri-click RIPA2 retraction, the project's broader claim that **RIPA2 and LF/HF are two useful instruments operating at different temporal scales for different observations** stands and is arguably strengthened by this analysis. The two retractions reinforce, rather than contradict, the position:

- **RIPA2** is the right instrument for **per-fixation phasic arousal** at scales where the SG-VLF window is small relative to the analytic window. It picks up sub-second amplitude spikes in pupil first-derivative power. It is *not* the right instrument for event-locked windows that straddle the SG-VLF span (±810 ms at 150 Hz) — there the smoother smears post-event signal backward and the test scoping has to control for that.
- **LF/HF** is the right instrument for **windowed cognitive effort** at the per-(trial, position) and per-trial scales — load that integrates over hundreds of milliseconds to seconds. It does not have the SG-derivative leakage character because it is a band-limited power ratio computed over a defined window. The peri-click LF/HF "drops toward the click" finding is unaffected by this audit.

Practical scoping rule going forward: **RIPA2 for phasic/per-fixation, LF/HF for tonic/per-window**. Each instrument's test design has to respect its own filter span. Peri-event RIPA2 test windows must exclude the ±810 ms zone around the event; per-window LF/HF tests must respect the analytic window length.

## What this means for the project

Two AdSERP RIPA2 findings have now been retracted in 2026-05:

1. **Per-fixation will-regress vs no-regress** (`r1-ripa2-bbox-collapse.md`) — rank-pooling artifact under absolute attribution, collapses to *p* = 0.80 under bbox-organic.
2. **Peri-click pre-decision peak** (this file) — SG-VLF leakage artifact, collapses from *p* = 4 × 10⁻¹⁹ to *p* = 0.20 under leakage-clean window.

The remaining defensible per-event RIPA2 claims at the AdSERP level are population-aggregate — the click-rate × RIPA2 × LF/HF quadrant analysis, the per-(trial, position) cross-products, etc. Per-fixation event-locked RIPA2 claims need leakage-aware test scoping going forward.

## Producer + reproduction

- Original test producer: `scripts/ripa2_around_click.py` — extended with PEAK and MEDIAN tests on 2026-05-02 (commit landing TBD).
- Inline comparison run: see Bash output captured in the 2026-05-02 conversation buffer (per-event arrays not cached on disk; reproduce by re-running the script and applying the [−1500, −900] window mask).
- Underlying SG-VLF window param: `scripts/compute_ripa2.py:74` — `VLF_WINDOW = 243` samples at 150 Hz.
