# Viewport bands (AR-V3) re-derived on the cursor-only deferred pool

**Tags:** `[LAB, AdSERP, typed, cursor-only]` · 47-fold LOSO balanced logistic regression, per-fold StandardScaler · target = NB22 gaze-regression label (deferred = 1, evaluated-rejected = 0), typed label cache keyed by (trial, position); the 663 approached non-click rows absent from the cache count as rejected, as in the shipped §4.3 number
**Producer:** `scripts/viewport_bands_cursor_only.py` → `scripts/output/viewport_bands_cursor_only/summary.json`
**Gate:** LOSO M4-7 on the shipped pool reproduces `m4_cursor_only_downstream/summary.json` `section_4_3.deployable_M4_7.pooled_auc` (0.691066) to 1e-6 (diff 0.0) before any band is computed.
**Key Claims:** none yet. Candidate replacement rows for `approach-retreat/docs/key-claims.md` §V3 (K-bbox-1, -2, -3, -5, K6–K8, K-bbox-9..14), which are all on the retired fixation-selected stream.
**Generated:** 2026-09-18.

## Question

approach-retreat's V3 rows say: retreat alone 0.775, the three viewport
bands alone 0.743, combined 0.811; `vt_top` > `vt_mid` > `vt_bot`; and the
`vt_top` coefficient is positive at P0–P3, attenuates at P4 and has a CI
including zero by P5. Those were computed on the fixation-selected organic
pool (n = 2,351 → 2,067) with the nine-feature LAB cursor vector, whose
"cursor" features sample the cursor at fixation times and weight dwell by
fixation duration. `docs/ablations/deferred_drop_decomposition.md` showed
that vector carries part of the label. What do the same three bands do on the
rows the paper now reports, against the tracker's own APPROACH_7 vector, with
the same observation window as every cursor number?

## Definitions

Bands follow `viewport_time_calibration.viewport_ms_for_trial`
(`edmonds-2026-vpbands-v1`): scrollY = 0 from the first mouse event, stepped
at each scroll event; a result accrues `vp_any` while any part of it
intersects the viewport, and `vt_top` / `vt_mid` / `vt_bot` by which third of
the viewport its centre lies in. Two things are not the old producer's, and
are choices rather than reproductions:

- **Window.** The timeline is cut at `mousedown(final click) − 500 ms`, the
  boundary every cursor feature on this pool is computed to
  (`scroll_kinematics.scroll_stream`). The old producer ran to the last mouse
  event, after the click.
- **Space.** Typed cards, scroll y × `ratio_y`, viewport height =
  `screen_height × ratio_y` (921–928 px), the convention
  `scroll_only_carve.py` and NB36 use on this pool. The old producer mixed
  document-space scroll y with band tops and the raw 1024 px screen height.
  A raw-height sensitivity row is in the table.

Trials with no scroll event keep a viewport at scrollY = 0 for the whole
window, as before; nothing is dropped on a scroll-count rule (the scroll
producers' ≥ 3-scroll rule loses 457 trials, this one loses none). Geometry
resolved for 2,608 / 2,608 trials, so the pool is the shipped 9,932 rows
(6,800 deferred, 47 participants, 2,437 trials), one pool for every row of
the main table.

## Same rows, pooled and within-trial

Within-trial AUC (`reduction_baselines.within_trial_auc`) scores only pairs
inside one trial, because NB36 found the viewport vector's pooled advantage
over the cursor was between-trial base rate.

| model | features | pooled AUC | fold mean ± sd | within-trial AUC |
|---|---|---|---|---|
| cursor M4-7 (gate) | 7 | 0.691 | 0.694 ± 0.070 | 0.718 |
| `vp_any` alone | 1 | 0.746 | 0.720 ± 0.079 | 0.720 |
| bands alone (`vt_top`, `vt_mid`, `vt_bot`) | 3 | **0.789** | 0.776 ± 0.064 | **0.773** |
| cursor M4-7 + bands | 10 | **0.789** | 0.782 ± 0.057 | 0.776 |
| bands + `vp_any` | 4 | 0.789 | 0.777 ± 0.064 | 0.775 |
| cursor M4-7 + bands + `vp_any` | 11 | 0.790 | 0.783 ± 0.057 | 0.777 |
| bands alone, viewport height = raw `screen_height` | 3 | 0.797 | 0.786 ± 0.058 | 0.777 |

Paired by participant (fold-AUC differences, 10,000-draw participant-cluster
bootstrap of the mean, two-sided Wilcoxon):

| comparison | Δ | 95 % CI | p |
|---|---|---|---|
| bands − cursor | **+0.082** | [+0.064, +0.100] | 5e-11 |
| combined − cursor | +0.088 | [+0.072, +0.105] | 2e-13 |
| combined − bands | +0.006 | [+0.002, +0.011] | 0.014 |
| `vp_any` − bands | −0.056 | [−0.069, −0.043] | 1e-11 |
| raw-height bands − scaled bands | +0.011 | [+0.006, +0.015] | 1e-5 |

## Coefficient signs (bands alone, pooled standardized, + = deferred)

| feature | old (AR-V3:K6–K8) | now |
|---|---|---|
| `vt_top` | +1.83 | **+1.45** |
| `vt_mid` | +0.83 | +0.83 |
| `vt_bot` | +0.21 | +0.28 |

Ordering preserved. In the combined model the three keep their signs
(+1.35 / +0.66 / +0.23) and every cursor coefficient is under 0.26 in
magnitude.

## Rank dependence of `vt_top` (bands-alone LR per position, 1,000 participant-cluster draws)

| position | n | `vt_top` | bootstrap median | 95 % CI | old organic row |
|---|---|---|---|---|---|
| P0 | 1,705 | +1.39 | +1.40 | [+1.05, +1.88] | +0.62 [+0.28, +1.08] |
| P1 | 1,530 | +1.27 | +1.27 | [+1.02, +1.57] | +0.50 [+0.16, +1.21] |
| P2 | 1,447 | +0.91 | +0.90 | [+0.73, +1.13] | +1.09 [+0.67, +1.65] |
| P3 | 1,136 | +0.75 | +0.74 | [+0.50, +1.08] | +1.29 [+0.77, +2.16] |
| P4 | 910 | +0.77 | +0.77 | [+0.60, +1.00] | +0.24 [−0.10, +0.85] |
| P5 | 787 | +0.57 | +0.58 | [+0.31, +0.90] | +0.05 [−0.19, +0.58] |

No CI includes zero. The pool is three to seven times larger per position
than the old one, so the P4–P5 "significance transition" the AR doc names
does not survive; what remains is a decline from +1.4 at P0 to +0.6 at P5.

## First-visit carve (diagnostic, not deployable)

The same bands cut at the end of the first gaze visit to that result
(`deferred_dwell_carve.visit_decomposition`, the label's own fixation→AOI
assignment). One pool of 9,141 rows: the shipped pool minus the 663
never-fixated rows and 128 labeled rows whose first gaze visit ended before
the first mouse event.

| model | pooled AUC | within-trial AUC |
|---|---|---|
| cursor M4-7 | 0.679 | 0.706 |
| bands, full window | 0.771 | 0.759 |
| bands, first visit only | **0.553** | 0.551 |
| `vp_any`, full window | 0.729 | 0.705 |
| `vp_any`, first visit only | 0.464 | 0.500 |
| cursor M4-7 + first-visit bands | 0.683 | 0.710 |

First-visit − full-window bands, paired by participant: −0.195
[−0.213, −0.176]. First-visit bands − cursor: −0.121 [−0.144, −0.097]. The
carved coefficients are +0.10 / +0.07 / −0.05, indistinguishable from a
flat fit.

## Reading

**The three bands beat the cursor on this pool, pooled and within-trial.**
On identical rows, labels and window, bands alone score 0.789 to the
cursor's 0.691, +0.082 per participant with a CI clear of zero, and the
gap holds inside trials (0.773 vs 0.718). This is not the NB36 pattern: the
viewport *kinematics* vector's pooled lead there vanished within-trial;
the band triplet's does not. Adding the cursor to the bands buys +0.006.

**Signs and ordering of AR-V3 K6–K8 hold; the magnitudes are the old
stream's.** `vt_top` > `vt_mid` > `vt_bot` at +1.45 / +0.83 / +0.28.

**The rank-dependence story changes.** Every position P0–P5 has a positive
`vt_top` with a CI clear of zero; the old organic rows' peak at P3 and the
zero-crossing at P5 were features of a pool with 116–494 rows per position.

**The band signal is mostly the return.** Cut at the end of the first gaze
visit, bands fall to 0.553 pooled / 0.551 within-trial and `vp_any` to
chance, a −0.195 drop; the cursor on the same rows moves 0.691 → 0.679.
The result has to be on screen for the return fixation that defines
`deferred`, so time-on-screen over the whole window contains the label the
way `total_dwell_ms` does (`docs/methodology/deferred-dwell-carve.md`).
The AR-V3 headline numbers were carrying that; a deployment that reads
bands up to the click reads the return, not a prediction of it.

## Not established

- Whether the old 0.775 / 0.743 / 0.811 are reproducible at all: they are
  on a retired stream (fixation-selected rows, nine-feature LAB vector,
  uncut window, mixed coordinate spaces) that this producer does not
  rebuild. The rows above are replacements, not reproductions.
- The uncut-window and raw-height variants only as sensitivity rows
  (raw height +0.011); the uncut window was not run because no cursor
  number on this pool uses it.
- Whether a band feature restricted to a cutoff a deployment can compute
  (e.g. the first scroll past the result) retains anything; the carve here
  uses a gaze boundary.
- The fully-contextual 10-AOI × bands model (AR-V3:K4) was not rerun.
