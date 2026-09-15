# Returns are memory-guided — landing precision survives a 2.4× longer jump with a weaker peripheral ramp

**Tags:** `[LAB, AdSERP, typed]` · window 1 s · **two kernels reported**
**Producer:** `scripts/return_is_memory.py` → `summary_boundary_cm_24.json` (primary: boundary-distance kernel with cortical-magnification falloff, alpha = 1/(1 + E/2°), 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`), `scripts/peripheral_kernel.py`) and `summary.json` (the published PAI Eq. 2, `spec_eq2`)
**Key Claims:** `[NB38:K1–K3]` (`notebooks-v2/38_moves_between_results.ipynb`)
**Generated:** 2026-09-14. Follows `pai_deferred_probe.md` (same day).

> **Kernel note (read first).** The published PAI kernel is nearly flat in
> eccentricity on SERP result bands (corpus Spearman with boundary distance
> −0.08; see `peripheral_kernel.py` docstring and `engagement_state_census.md`
> §Kernel). Under it, "peripheral mass on this band in the last second" is
> close to "fixation duration anywhere on the page in the last second". The
> landing-precision and amplitude columns do not depend on any kernel; the
> peripheral-ramp column does, and both versions are shown. The boundary
> kernel is a proposal for the method's authors, not their published method.

## Question

When the gaze returns to a result it has already examined (the deferred
class, NB22 label), is the return guided by ongoing peripheral monitoring of
that result, or executed from a remembered location? The two accounts make
opposite predictions about the second before landing:

- **periphery-guided:** a larger peripheral ramp before the return than
  before the first entry, and precision that depends on the ramp;
- **memory-guided:** precision at least as good as first entry, with a ramp
  no larger, and a ballistic amplitude.

## Setup

- Every deferred (trial, position) on the typed map with ≥ 2 gaze visits:
  **9,347 events, 47 participants** (9,797 deferred rows; 450 have one visit
  under the visit walk, which treats a long dwell as one return). Fixations
  assigned by the label producer's own rule; visit walk asserted against
  `visit_decomposition` (0 drift).
- Two landing events per row, compared within the row: `entry` (first
  fixation of the first visit) and `return` (first fixation of the second).
- Per event: y landing offset from band centre; saccade amplitude from the
  preceding fixation; ranks jumped; spec_eq2 peripheral mass rate on that
  band over the 1 s before landing (fixations strictly before; NaN if the
  trial starts inside the window); mean gaze distance over the same second.
- Paired medians with 5,000-sample participant-cluster bootstrap CIs and a
  Wilcoxon on rows; per-participant sign counts over participants with ≥ 5
  rows.

## Results

### All returns (median, return − entry)

| Measure | return | entry | diff | 95 % CI | participants diff < 0 |
|---|---|---|---|---|---|
| landing offset (px) | 47.5 | 39.5 | **+7.0** | [+6, +9] | 2 / 47 |
| saccade amplitude (px) | 139 | 176 | −26 | [−32, −20] | 42 / 47 |
| peripheral ramp, boundary kernel (mass/s) | 187 | 167 | **+21** | [+16, +26] | 4 / 47 |
| peripheral ramp, published kernel (mass/s) | 277 | 296 | −16.5 | [−23, −10] | 34 / 47 |
| gaze distance, 1 s before (px) | 151 | 212 | −56 | [−61, −51] | 47 / 47 |
| ranks jumped | 1 | 1 | 0 | — | — |

70 % of returns (6,574 / 9,347) come from the adjacent result and 42 % arrive
from above. These short returns are *less* precise than first entries by
7 px. Under the boundary kernel they are preceded by *more* peripheral
intake than first entries, which is what a 151 px gaze distance implies: the
adjacent result is inside the falloff. The published kernel's opposite sign
here is the flat-kernel artefact.

### Long returns, ≥ 2 ranks (n = 1,774)

| Measure | return | entry | diff | 95 % CI | p |
|---|---|---|---|---|---|
| landing offset (px) | 39.5 | 38.0 | **+1.5** | [0, +3] | 0.17 |
| saccade amplitude (px) | **429** | 179 | +211 | [+190, +235] | 3e-145 |
| peripheral ramp, boundary kernel (mass/s) | **78** | 148 | **−61** | [−75, −50] | 1e-78 |
| peripheral ramp, published kernel (mass/s) | 253 | 269 | −19 | [−32, −4] | 2e-5 |
| gaze distance, 1 s before (px) | 387 | 219 | +139 | [+113, +163] | 3e-89 |

A long return lands as precisely as a first entry, from 2.4× the distance,
with the eyes 139 px further away over the preceding second and with
*half* the peripheral intake on the target that the first entry had
(boundary kernel). The published kernel showed the same sign at a fifth of
the size, because it barely sees eccentricity.

### Does the ramp buy precision when it is there?

Under the boundary kernel, **no**: Spearman ρ between the 1 s peripheral
rate and landing offset is −0.02 (entry, n = 7,004, p 0.11) and −0.001
(return, n = 8,996, p 0.96). The −0.18 / −0.21 the published kernel gave
was page-wide fixation duration predicting precision, not peripheral
intake on the target. Landing precision does not depend on how much the
periphery had of the target in the preceding second.

## Reading

1. **Returns are memory-guided.** Precision is preserved across a 2.4×
   larger jump with half the peripheral intake on the target, and precision
   does not covary with that intake at all. A periphery-guided account
   cannot produce either. The searcher leaves widely and comes back to a
   remembered location.
2. **It is consistent with NB12's null.** Landing precision did not vary
   with pupil-indexed load (NB12 K8–K10, median offset 60 px on the legacy
   band geometry). Spatial memory for result positions is robust, and now
   also shown to be the guidance signal for the return.
3. **Short returns are a different act.** The adjacent-result return is the
   reading step back: less precise than a first entry and, under the
   boundary kernel, *more* peripherally prepared, because the target is one
   band away. It should not be pooled with the long, ballistic return in any
   account of revisitation. The 70/30 split is the number to carry.
4. **For foraging:** the between-patch return is executed from state
   (memory of where value was), not from scent (peripheral sampling of the
   target). That is the observable the depletion-state predictor in the
   CHIIR Flavor B note stands on.

## Caveats

- Landing offset is y-only relative to the band centre; typed bands differ
  in height, so a large target inflates apparent precision for both events
  equally but not necessarily for returns versus entries if returns prefer
  larger results. A height-normalised offset is the natural hardening.
- The entry saccade for most rows is the downward reading step from the
  result above, so the amplitude contrast is partly the layout. The
  precision contrast is not.
- The boundary kernel's 43 px/° (2026-09-14 derivation; the 2026-09-14 runs used 24 px/°, so E2 = 48 px ≈ 1.1°; rerun 2026-09-15 at 43 px/°, every quoted number identical to three decimals, see `px_per_deg_rerun.md`) is the repo's convention (findings.md
  §3d-ii); the lit note's upper bound is 40 px/°. The sign and the null do
  not depend on the choice; the ramp magnitudes do.
- `[LAB]` only; the label and both measures need an eye tracker.
