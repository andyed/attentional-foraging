# Soft-falloff kernel at the derived 43 px/° — nothing moves

**Tags:** `[LAB, AdSERP, typed]` · boundary-distance kernel alpha = 1/(1 + E/2°) · 2026-09-15
**Producers:** the six below, rerun with `--px-per-deg 43` (outputs suffixed `_43` / `_px43` / `kernel_boundary_cm_43`) against their 2026-09-14 runs at 24 px/°

## Why

The 2026-09-14 kernel runs used the repo's older 24 px/° convention. The
same day the scale was derived from the AdSERP hardware as ≈ 43 px/° at the
tracker's ideal 65 cm (`docs/methodology/adserp-vs-ao-corpus-differences.md`).
Under the soft kernel that changes E2 from 48 px (1.1° in truth) to 86 px
(2°), so every number computed under it was rerun.

## Result

| producer | quantity | 24 px/° | 43 px/° |
|---|---|---|---|
| `return_is_memory.py` | landing offset, return − entry (px) | +7.0 [+6, +9] | +7.0 [+6, +9] |
| | peripheral ramp, return − entry (mass/s) | +21 [+16, +26] | +18.9 [+13, +26] |
| | long returns: landing diff / ramp diff | +1.5 / lower | +1.5 [0, +3] / −81.5 [−96, −66] |
| | ramp-vs-precision Spearman (entry / return) | ≈ 0 / ≈ 0 | −0.019 / −0.003 |
| `pai_deferred_probe.py` (1 s, full window) | pooled AUC, pai_post / gaze_dist_post / mean_dist | 0.542 / 0.524 / 0.667 | 0.543 / 0.524 / 0.667 |
| | paired M4-7 + PAI vs M4-7 | ≈ 0 | −0.0002 [−0.0004, +0.0001] |
| `periphery_navigates.py` (B) | position + intake rank / + distance rank / + both | 0.751 / 0.752 / 0.753 | 0.751 / 0.752 / 0.752 |
| | top- vs bottom-intake candidate later fixated | 0.96 / 0.49 | 0.96 / 0.49 |
| `pai_kernel_validation.py` | every kernel, +pos+dist over position + distance | +0.000 to +0.001 (eq2 ungated +0.009) | +0.000 to +0.001 (eq2 ungated +0.009) |
| `major_saccade_selection.py` | P(top intake) vs P(top proximity), 0.5 / 1 / 2 / 4 s | 0.545/0.543, 0.499/0.498, 0.481/0.478, 0.471/0.468 | 0.545/0.543, 0.499/0.498, 0.482/0.478, 0.469/0.468 |
| | pre-move fixation, landing offsets | unchanged by construction (no kernel) | same |
| `engagement_state_census.py` (soft variant) | peripheral slots among on-screen never-fixated (matched threshold) | 1,096 | 1,222 |
| | peripheral-tier intake eccentricity, median OGD (px) | 611 | 651 |
| `engagement_continuation.py` (soft variant) | position-matched peripheral share; matched AUC skipped vs read | 46.2 %; 0.465 | 50.3 %; 0.494 |
| | peripheral vs unsampled, query-cosine AUC (p) | 0.492 (0.64) | 0.501 (0.95) |
| | peripheral vs rejected, query-cosine AUC (p) | 0.475 (0.07) | 0.480 (0.12) |
| | cost tiers, approached share by state | unchanged | unchanged |

Every rank-based or model-based quantity moves by less than 0.003 AUC or
3 mass/s, inside every bootstrap interval. The reason is the one
`pai_kernel_validation.md` gives: on SERP bands every eccentricity-aware kernel
is a monotone transform of gaze distance, and the LOSO models and rank-based
tests see only the order. Scaling E2 does not change the order.

The one place the scale shows is the **soft-variant census**, whose peripheral
tier is a *threshold* on intake rate (at or above the fixated median). A wider
kernel lifts every slot's intake, but far slots more, so about 130 borderline
slots cross the threshold: the soft peripheral tier goes from 1,096 to 1,222
slots and its position-matched share from 46 % to 50 %. Every test on the tier
stays null (skipped vs read 0.49; content cues 0.48–0.51). The **primary census
(hard gate, 200 px) does not use the kernel and is unchanged**, which is one
more reason it is primary.

## Consequence

The degree labels in the 2026-09-14 notes are corrected in place (200 px ≈ 5°,
48 px ≈ 1.1°); the numbers under them stand. The 24 px/° outputs stay the cited
ones; the 43 px/° outputs sit beside them for the record. No note needs its
tables regenerated.
