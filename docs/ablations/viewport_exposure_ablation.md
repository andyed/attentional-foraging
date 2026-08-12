# Viewport-exposure leakage ablation — control-ladder final tier

**Tags:** `[LAB, AdSERP, organic_hybrid]`
**Producer:** `scripts/viewport_exposure_ablation.py` → `scripts/output/ablations/viewport_exposure_ablation.json`
**Generated:** 2026-08-12 (deliberation-phase leakage control family)

## Question

Is "time on screen per result" — viewport residence, computable with no
cursor at all — robust to deliberation-phase leakage, compared against
hover/dwell (M2) and the full cursor episode geometry (M3-7 / M4-7)?

## Caveat under test (not assumed away)

Scroll-to-click is travel-to-target one level up: the viewport must be
scrolled to the to-be-clicked result before the click, so exposure time
is **not leakage-free by construction**. That is exactly why the
buf500 → full-excision drop is measured for the exposure model on the
same per-trial excision timestamps as the cursor grid, instead of
asserting robustness.

## Setup

- **Exposure features** per (trial, AOI): cumulative ms the AOI
  intersected the scroll viewport (`vt_any_ms`), plus the viewport-third
  split (`vt_top_ms` / `vt_mid_ms` / `vt_bot_ms`), piecewise-constant
  over scroll events — the viewport-bands calibration machinery (tag
  `edmonds-2026-vpbands-v1`, `scripts/viewport_time_calibration.py`),
  re-implemented with a time cutoff. AOI geometry is the organic_hybrid
  (top, bottom) bands from `build_hybrid_aois`, so AOI indices match the
  cursor feature records exactly.
- **Conditions** (identical excision to the cursor ablation):
  - **buf500** — exposure accumulated up to t_click − 500 ms; records =
    the published buf500 grid population (19,848 (trial, AOI) records,
    2,589 clicks, 2,774 trials, 47 participants).
  - **excision** — exposure accumulated up to the per-trial
    committed-approach onset t_onset, reused **verbatim** from
    `approach_truncation_trial_stats.json` (not re-detected); records =
    the truncation grid population (18,919 records, 2,439 clicks,
    2,768 trials, 47 participants).
- **Protocol:** LOSO (leave-one-participant-out, 47 folds) logistic
  regression, StandardScaler, `class_weight='balanced'`, C = 1.0 —
  identical to `click_buffer_ablation.py` / `approach_truncation_ablation.py`.
- **M2** is the grid's dwell model as implemented there: position +
  `total_dwell_ms` (per-AOI gaze fixation dwell, ms). The cursor-hover
  channel (`dwell_in_proximity_ms`) enters via the 7-feature geometry
  set in M3-7 / M4-7.

## Coverage

Exposure computed for **2,774 / 2,774 trials (100.0 %)** — 0 trials
failed meta/event/AOI loading, 0 trials missing truncation stats, 0
records dropped, 0 position-out-of-bounds records. No ladder row is on a
restricted subset; both conditions use their full prior populations.

Exposure magnitudes: `vt_any_ms` median 13,413 ms (p10 4,710 ms, p90
30,951 ms) at buf500; median 11,679 ms (p10 4,006 ms, p90 27,557 ms)
under excision.

## Anchor check — PASS

Recomputed buf500 M2 LOSO AUC = **0.7636** vs published grid
(`scripts/output/paper-output/click_buffer_ablation.json`) **0.7636**;
|diff| = 0.0000 ≤ 0.002 tolerance, same 19,848 records. The other
recomputed cursor rows also reproduce both prior grids to 4 decimals
(buf500: M1 0.6679, M3-7 0.8463, M4-7 0.8468; excision: M1 0.6749,
M2 0.7249, M3-7 0.7532, M4-7 0.7328).

## Combined control ladder (LOSO AUC)

Position → exposure → hover/dwell → geometry, each under the terminal
buffer (buf500) and the full committed-approach excision. Drop = buf500
AUC − excision AUC (cross-condition pairing is per participant fold;
record populations differ between conditions as in the cursor ablation,
which is why M1's "drop" is slightly negative).

| Model | Features | buf500 AUC | excision AUC | drop (AUC) |
|---|---|---|---|---|
| E-any | vt_any_ms (1) | 0.5771 | 0.5457 | +0.0314 |
| E | 4 exposure bands | 0.6492 | 0.6034 | +0.0458 |
| M1 | position (1) | 0.6679 | 0.6749 | −0.0070 |
| M1+E | position + 4 exposure | 0.6873 | 0.6816 | +0.0057 |
| M2 | position + gaze dwell | 0.7636 | 0.7249 | +0.0387 |
| M2+E | M2 + 4 exposure | 0.7885 | 0.7540 | +0.0345 |
| M3-7 | position + dwell + 7 geometry | 0.8463 | 0.7532 | +0.0931 |
| M3-7+E | M3-7 + 4 exposure | 0.8561 | 0.7753 | +0.0808 |
| M4-7 | 7 geometry alone | 0.8468 | 0.7328 | +0.1140 |

## Paired per-fold stats (47 folds; Wilcoxon two-sided, Cohen's d_z, bootstrap 95 % CI on ΔAUC)

| Comparison | ΔAUC | 95 % CI | d_z | Wilcoxon p |
|---|---|---|---|---|
| E vs M2, excision | −0.1032 | [−0.1176, −0.0882] | −2.02 | 1.4e-13 |
| M1+E vs M2, excision | −0.0534 | [−0.0618, −0.0454] | −1.81 | 1.4e-13 |
| M2+E vs M2, excision | +0.0262 | [+0.0152, +0.0372] | +0.69 | 1.3e-05 |
| M3-7+E vs M3-7, excision | +0.0176 | [+0.0107, +0.0242] | +0.75 | 6.0e-06 |
| M3-7+E vs M3-7, buf500 | +0.0062 | [+0.0018, +0.0103] | +0.42 | 1.4e-03 |
| E drop (buf500 → excision) | +0.0503 | [+0.0429, +0.0575] | +1.94 | 1.0e-13 |
| M2 drop | +0.0580 | [+0.0472, +0.0696] | +1.45 | 1.4e-14 |
| M3-7 drop | +0.1045 | [+0.0905, +0.1195] | +2.06 | 1.4e-14 |
| M4-7 drop | +0.1158 | [+0.1024, +0.1297] | +2.45 | 1.4e-14 |

(Per-fold drop means differ slightly from the pooled-AUC drops in the
ladder table because folds are equal-weighted; both are reported in the
JSON.)

## Reading

1. **Exposure's leakage profile is hover-tier, not geometry-tier.** The
   buf500 → excision drop for E (+0.046 pooled AUC) sits next to M2's
   (+0.039) and well below the geometry models (+0.093 to +0.114). The
   scroll-to-click caveat is real but small: most of what exposure
   measures precedes the committed approach.
2. **But exposure alone is a weak predictor.** Under excision, E (0.603)
   is below even position alone (M1 0.675), and E vs M2 is −0.103 AUC
   (d_z = −2.02). Exposure does not replace hover/dwell as a control
   predictor; on-screen time is mostly shared exposure across co-visible
   results, so it separates viewed-region from rank, not result from
   result.
3. **Exposure adds a small, real increment on top of everything else,
   and the increment grows after excision:** +0.006 AUC over M3-7 at
   buf500 → +0.018 under excision (p = 6.0e-06). Once the mechanical
   approach is excised, viewport residence carries complementary
   information the cursor no longer provides.

## Verdict

**Partially supported** — "explicit time-on-screen per result" is
comparatively robust to deliberation-phase leakage (its excision drop is
hover-tier, ~40 % of the geometry models'), but it is not a viable
*standalone* control predictor: under full excision it trails position
alone by −0.07 AUC and position+dwell by −0.10 AUC; its honest role is a
small additive channel (+0.018 AUC over the full model under excision).

---

## Addendum — cursor hover isolated (H rows)

**Tags:** `[LAB, AdSERP, organic_hybrid]` — added 2026-08-12 at
coordinator request; same records, same 47 LOSO folds, same conditions.

The grid's M2 dwell is **gaze** fixation dwell (`total_dwell_ms`), so
the cursor-hover channel was never isolated in the ladder above. H
isolates it: `dwell_in_proximity_ms` (ms of gaze-fixation-sampled time
with the cursor within 100 px of the AOI center — the cursor-only hover
analog). All other rows above are unchanged; the anchor check
re-verified exactly (buf500 M2 = 0.7636, |diff| 0.0000). Regenerated by
the same producer script (H / M1+H / M1+H+E added to the variant list),
so JSON and md stay in sync.

| Model | Features | buf500 AUC | excision AUC | drop (AUC) |
|---|---|---|---|---|
| H | dwell_in_proximity_ms (1) | 0.8212 | 0.6321 | +0.1891 |
| M1+H | position + cursor hover | 0.8150 | 0.7040 | +0.1110 |
| M1+H+E | position + cursor hover + 4 exposure | 0.8185 | 0.7135 | +0.1049 |

Paired per-fold stats (47 folds), the deployability comparison of
record — cursor-hover analog vs gaze dwell:

| Comparison | ΔAUC | 95 % CI | d_z | Wilcoxon p |
|---|---|---|---|---|
| M1+H vs M2 (gaze), buf500 | +0.0496 | [+0.0398, +0.0600] | +1.37 | 7.8e-13 |
| M1+H vs M2 (gaze), excision | −0.0291 | [−0.0361, −0.0223] | −1.19 | 7.1e-11 |
| H drop (buf500 → excision) | +0.1798 | [+0.1616, +0.1992] | +2.69 | 1.4e-14 |
| M1+H drop | +0.1367 | [+0.1184, +0.1555] | +2.07 | 1.4e-14 |
| M1+H+E drop | +0.1293 | [+0.1112, +0.1487] | +1.91 | 1.4e-14 |

**Reading.** Cursor hover is the most leakage-loaded single channel in
the entire ladder: H alone posts 0.8212 AUC at buf500 — above M2's
0.7636 and nearly matching the full 7-feature geometry (0.8468) — then
collapses to 0.6321 under full excision, a +0.1891 pooled-AUC drop,
larger than any other model's (geometry: +0.093 to +0.114; gaze dwell
M2: +0.039). The M1+H vs M2 sign flip is the deployability answer: at
buf500 the cursor analog *beats* gaze dwell by +0.050 AUC (p = 7.8e-13),
but under excision it *loses* by −0.029 AUC (p = 7.1e-11). The cursor
analog retains little of gaze-dwell's robustness — its buf500 advantage
is largely committed-approach residence near the future click target,
i.e. exactly the deliberation-phase leakage this control ladder was
built to expose. Adding exposure bands recovers only +0.010 AUC (M1+H+E
0.7135 vs M1+H 0.7040 under excision). Ladder ordering by
leakage-robustness (smallest drop first): position ≈ position+exposure →
gaze dwell → viewport exposure → geometry → **cursor hover**.
