# Changelog

## Unreleased — 2026-04-10

### ETTAC infrastructure

- **Key Claims expanded to 11 notebooks** (~145 canonical rows). New: NB05 (LHIPA, K1–K15), NB12 (regression precision null, K1–K14), NB18 (RIPA2 vs LF/HF, K1–K17).
- **NB14 piecewise gradient analysis** (K9–K15). Resolves K3's borderline p = 0.043:
  - Steep phase (pos 0–3): Mann–Whitney p = 4.1 × 10⁻²², medians 30.0 → 16.0
  - Plateau phase (pos 4–10): Spearman ns — flat, as predicted by framework compilation
  - Within-trial gradient strengthens with evaluation depth: 79.1% negative at ≥7 positions (K15)
- **findings.md v11**: corrected 8 stale values (NB13, NB11, NB14), added Key Claims `[NB__:K__]` references throughout.
- **NB14:K5 inclusion criterion documented**: ≥3 valid LF/HF segments at positions 0–10 (Spearman with N=2 is degenerate).
- **pupil-lfhf validation pipeline**: self-contained AdSERP analysis (`adserp_loader.py`, `validate_adserp.py`) with coordinate-audited click_pos. All values match Key Claims exactly.

## 2026-04-09

### Coordinate-space audit: scroll double-counting bug in click position

**The bug.** `scripts/compute_butterworth_lfhf.py:147` and `scripts/compute_ripa2.py:193` derived each trial's `click_pos` by calling `assign_fixation_to_position(last_click[2], click_scroll, …)`. That function is designed for **gaze** — it adds `scroll_y` to convert screen-space FPOGY into page-space. But `clicks[-1][2]` comes from evtrack `ypos`, which is **already page-space** (verified empirically: `p004-b2-t3` has cursor Y up to 1,902 px while the browser window is only 1,137 px tall). Adding scroll double-counted it, pushing clicks on scrolled trials to deeper bands than the user actually clicked.

The same pattern was cargo-culted into nine other notebooks (NB01, NB03, NB05, NB06, NB07b, NB10, NB12, NB15, NB18-learning_curve, NB23, NB24) and one additional script (`forward_regressive_tolerance_sweep.py`). The root cause is that half the notebooks reimplement their own mini-loader in cell 2 instead of importing `data_loader.py`, each with its own implicit coordinate-space assumption.

**Impact, corpus-wide (see `notebooks-v2/test_coordinate_invariants.py` Invariant 9):**

| | Correct formula | Buggy formula |
|---|---|---|
| Clicks landing in their reported band | **2,764 / 2,764** | 1,174 / 2,764 (57.5 % mis-placed) |
| Mis-placed clicks on scrolled trials | 0 | **1,590 / 2,266** |
| No-scroll trials (sanity bar) | — | **0 disagreements** |

The buggy formula also produced physically impossible `click_pos` values (up to 15, for 10-result SERPs) in **239 trials** of the old `butterworth-lfhf-by-position.json`.

**NB14 Key Claims — before / after the fix:**

| Claim | Before | After | Notes |
|---|---|---|---|
| K1 (trials) | 2,719 | 2,719 | — |
| K2 (position segments) | 6,874 | 6,874 | — |
| **K3 (position × median LF/HF)** | **ρ = −0.618, *p* = 0.0426** | **ρ = −0.618, *p* = 0.0426** | Exact — uses fixation position, not click_pos |
| K4 (positions 1–10) | ρ = −0.491, *p* = 0.150 | ρ = −0.491, *p* = 0.150 | — |
| K5 (within-trial) | N = 1,167, median ρ = −0.200 | N = 1,167, median ρ = −0.200 | — |
| **K6 (clicked vs non-clicked LF/HF)** | 22.86 (N = 1,145) vs 18.97 (N = 5,437); *p* ≈ 0 | **22.24 (N = 1,110)** vs **19.01 (N = 5,472)**; *U* = 3,257,823, *p* = 1.30 × 10⁻⁴ | Direction and significance preserved |
| K7 (LF/HF × LHIPA) | ρ = −0.122, *p* = 9.29 × 10⁻¹⁰, N = 2,492 | unchanged | — |
| K8 (position medians) | pos 0: 29.98 → pos 1: 21.20 → … | unchanged (uses fixation position, not click_pos) | — |

**The ETTAC 2026 load-bearing claim (K3) is unaffected.** The position-level correlation, within-trial decomposition, and LHIPA cross-index validation all use fixation position (gaze → page-space, which is the coordinate-correct direction). Only `click_pos`-dependent rows moved.

**The fix.**
1. `notebooks-v2/data_loader.py` — documented coordinate-space conventions in the module docstring, tightened `assign_fixation_to_position` to name its parameter `screen_fix_y` and warn that cursor/click Ys must not be passed. Added canonical helpers: `get_click_page_xy`, `click_to_position`, `cursor_to_position`, `screen_y_to_page_y`, `page_y_to_screen_y`, `gaze_cursor_distance`, `interpolate_cursor_at`.
2. `notebooks-v2/test_coordinate_invariants.py` — nine-section regression test locking in the conventions. Corpus-wide Invariant 9 produces the 1,590-trial headline number above.
3. `scripts/compute_butterworth_lfhf.py` — replaced the buggy `assign_fixation_to_position` call with `click_to_position(clicks, tops, n_results)`. Regenerated `butterworth-lfhf-by-position.json`.
4. `notebooks-v2/update_key_claims.py` — NB14 K6 row updated; aggregate `docs/notebook-key-claims.md` refreshed.

**NB15 cursor-approach fix** — the feature-generating hero notebook. Two bug sites: (1) `compute_approach_features` double-counted scroll on `mouse_page_y`, corrupting `min_dist`, `mean_dist`, `final_dist`, `dwell_in_proximity_ms`, and `was_clicked`; (2) `click_y_page = clicks[0][2] + click_scroll` corrupted click-position assignment. Fix: import `click_to_position` and `gaze_cursor_distance` from `data_loader`, replace both sites. Regenerated `cursor-approach-features.json` via `jupyter nbconvert --execute`; regenerated `cursor-approach-features-typed.json` via `scripts/add_etype_to_features.py`. Pre-fix JSONs preserved with `.prefix-bug.json` suffix.

**Feature-level diff (NB15):**

| Metric | Before | After | Δ |
|---|---|---|---|
| Clicked records | 1,981 | **2,214** | +233 (+11.8 %) — clicks correctly re-attributed to their real positions |
| Click rate | 12.87 % | **14.38 %** | +1.5 pp |
| Median gaze-cursor distance | 256.5 px | **354.7 px** | +98 px |
| "Almost clicked" (<58 px, non-clicked) | 7.98 % | **5.57 %** | −30 % |
| Position 3 close-distance rate | 11.49 % | **3.23 %** | −72 % |
| Position 5 close-distance rate | 7.36 % | **0.28 %** | −96 % |
| Position 9 close-distance rate | 0.45 % | **0.00 %** | −100 % |

NB15 §2b's orient-phase observation is preserved at position 0 (27.8 % → 29.0 %, essentially flat — consistent with cursor parked near first result during orient). The deep-position approach signal at positions 3–9 was almost entirely scroll-bug artifact.

**NB21 Key Claims — before / after:**

| Claim | Before | After | Notes |
|---|---|---|---|
| K1 click rate | 12.9 % (1,981) | **14.4 % (2,214)** | 233 re-attributed clicks |
| K3 M3 LOSO AUC | **0.827 ± 0.047** | **0.792 ± 0.062** | −0.035; direction preserved |
| K4 M4 (approach only) AUC | 0.821 ± 0.048 | 0.792 ± 0.061 | M3 = M4 to three sig figs — position+dwell add no information beyond approach features |
| K5 M2 (pos+dwell) AUC | 0.746 ± 0.069 | 0.707 ± 0.081 | −0.039 |
| K6 M1 (pos only) AUC | 0.592 ± 0.083 | **0.670 ± 0.085** | +0.078 — position now a stronger predictor with clicks correctly attributed |
| K12 Brier score | 0.1615 | 0.1781 | calibration slightly worse (consistent with dropped AUC) |
| K15 Evaluated-rejected (4-class) | 994 (6.5 %) | **344 (2.2 %)** | largest shift — pre-fix "rejected" was mostly scroll noise at deep positions |
| K21 `position` coefficient | +0.21 (→ click) | **−0.380 (→ skip)** | SIGN FLIP — rank effect now in the correct direction |
| K27 `direction_changes` | +0.20 (→ click) | ≈0 (neutral) | feature was largely scroll artifact |

The −0.035 AUC drop is a real loss of predictive power — the pre-fix 0.827 was partly driven by scroll-leak features. K27 (`direction_changes`, pre-fix +0.20 → click) collapses to ≈0 post-fix, and the deep-position approach artifacts that populated the 4-class "Evaluated-rejected" set (994 → 344) were not informative in the first place.

Model-level results are preserved: M3 > M2 > M1 (0.792 > 0.707 > 0.670), M3 = M4 to three sig figs (approach features carry the full signal), and all 47 participants remain above chance (min 0.589). Feature-level coefficient signs are NOT all preserved: K21 (`position`) flipped +0.21 → −0.380 — the post-fix sign is the one the SERP rank-effect literature predicts. The pre-fix "11×" lift claim and the "14 % almost clicked" figure in `docs/findings.md` §10 are overstatements; the corrected taxonomy lives in NB21:K13–K16.

**NB11.5 (chattiness) — replication updated:**

| Claim | Before | After | Notes |
|---|---|---|---|
| K9 Low events/s tercile AUC | 0.826 ± 0.061 (n = 15) | **0.803 ± 0.052 (n = 15)** | median events/s: 9.4 → 9.5 |
| K10 Mid tercile AUC | 0.817 ± 0.041 (n = 16) | **0.780 ± 0.065 (n = 16)** | median events/s: 14.7 → 14.7 |
| K11 High tercile AUC | 0.838 ± 0.034 (n = 16) | **0.793 ± 0.064 (n = 16)** | median events/s: 32.2 → 28.8 |
| K12 pooled replication of NB21 | **0.827** | **0.792** | tracks NB21:K3 exactly |
| K13–K16 chattiness × AUC Spearmans | +0.04 to +0.14, all ns | −0.11 to +0.00, all ns | direction shifted toward zero; no row crosses significance |

The "robust across chattiness terciles" framing holds at the *significance* level (K13–K16 are all still ns with p > 0.4) but the tercile AUCs themselves dropped 0.02–0.05 uniformly with the NB21 re-run. Paper §4.3 robustness claim needs both the new tercile values AND a narrower effect-size range if the prose described it as "flat."

**Remaining notebooks and scripts patched:**

NB01, 03 (×2 sites), 05, 06, 07b, 10, 12, 18-learning_curve, 24 — batch-patched via `notebooks-v2/_apply_coord_fixes.py`. None of these have Key Claims blocks yet, so re-execution has not been triggered; they will pick up the fix on next run. `scripts/compute_ripa2.py` and `scripts/forward_regressive_tolerance_sweep.py` also patched; their JSON outputs will be refreshed the next time they run.

NB23 (rank_effects) is a **separate case**: its local `click_positions` derivation (used for panel 1, click share by position) has been patched in place, but the notebook has not been re-executed. Panels 4–5 (butterworth LF/HF + LHIPA by click position) already consume the fixed `butterworth-lfhf-by-position.json`, so they reflect the post-fix click_pos from that feeder. NB23 does not yet have a Key Claims block even though it's the rank-effects hero chart cited in README and CHANGELOG v9 — promoting it to Tier A is tracked separately.

**Still pending:**
- ~~Regenerate `ripa2` output~~ **Done** (2026-04-11): `compute_ripa2.py -o AdSERP/data/ripa2-by-position.json` — 2,719 trials, ρ = −0.827 positional gradient confirmed. (NB18 re-execution deferred — it reads this JSON, will pick up new values on next run.)
- ~~Re-execute NB23~~ **Done** (2026-04-09): NB23 uses `click_to_position()` from `data_loader` (coordinate-safe); all 9 code cells executed with correct output. K1 = ρ = −0.973 on 2,764 trials.
- ~~Phase 3 structural migration~~ **Done** (2026-04-11): All dangerous coordinate patterns eliminated. NB00, NB04, NB19 were the last three with inline `assign_fixation_to_position(click_y, scroll_y, ...)` or `click_page_y = cy + interpolate_scroll(...)`. Replaced with `click_to_position(clicks, tops, n_res)`. Zero dangerous patterns remain across all 30 notebooks (verified via regex scan).
- ~~`docs/findings.md`~~ **Already current** (v11, 2026-04-10): §10 and §10b updated with post-fix values (14.4% click rate, N = 344, correct NB22 four-class Ns, [NB##:K##] refs throughout). `docs/findings-approach-retreat.md` intentionally frozen with SUPERSEDED banner — it's a journey doc, not canonical.
- ~~`docs/drafts/` grep pass~~ **Done** (2026-04-11): `model-analysis.html` given SUPERSEDED banner with before/after table. `model-analysis.md` line 270 fixed (0.821→0.792). `task-model-paper.md` line 179 fixed (994→344). `paper.md` references to 0.821 are all Bruckner ACD (correct, different dataset). Remaining stale values in `.html` left under the SUPERSEDED banner rather than surgically edited.
- ~~Approach-retreat repo~~ **Done** (2026-04-11): README fixed (NB24 arc ratios, 17× typo, discrimination cost values). CLAUDE.md added documenting upstream dependency. See approach-retreat commit `63d861a` and `257cd79`.

**Reference data:** pre-fix JSONs preserved for reproducibility:
- `AdSERP/data/butterworth-lfhf-by-position.prefix-bug.json`
- `AdSERP/data/cursor-approach-features.prefix-bug.json`
- `AdSERP/data/cursor-approach-features-typed.prefix-bug.json`

**Regression lock.** `notebooks-v2/test_coordinate_invariants.py` (nine sections, passes in a few seconds) now encodes the gaze-is-screen-space, cursor-is-page-space convention as an executable contract. Any future change to `data_loader.py`, any Tier B producer script, or any Tier A notebook's data path must keep this test green. The corpus-wide Invariant 9 is the headline: all 2,764 clicks must fall within their reported band under the correct formula, and the buggy formula must still misplace 1,590 scrolled trials (so we know the test hasn't silently lost its reference comparison).

## v9 — 2026-04-07

### LHIPA reinterpretation: boundary step, not position gradient

Trial-level LHIPA by click position is **flat across positions 0–8** (range: 0.0385–0.0392, delta = 0.0008), then steps down at positions 9–10 (0.0376–0.0380). The previously reported ρ = −0.87 is driven almost entirely by the boundary step, not a gradual decline. Excluding positions 9–10: ρ = −0.78 but delta is within noise.

**Correction:** Prior claims that "LHIPA decreases monotonically with foraging depth" (README §Behavioral signals, findings.md, lit-review-scroll-regressions.md) overstated the position effect. LHIPA tracks the **boundary decision cost** — the same phenomenon as the ski-jump click distribution uptick — not a per-position scanning cost. Butterworth LF/HF (NB 14) remains the valid per-position cognitive load measure, and it shows framework compilation (steep drop 0–3, plateau after).

### Unified rank effects notebook (NB 23)

New notebook `23_rank_effects.ipynb` consolidates all by-position effects:
- Click share, fixation count, dwell time, Butterworth LF/HF, LHIPA — all on shared x-axis
- Forward-pass vs regression dwell decomposition (stacked bar): regression share peaks at positions 2–3 (~30%), drops to ~10% at position 9
- Normalized dissociation plot: time and cognitive load both decline, but load drops faster (framework compilation)
- Publication-quality hero chart with IQR bands

**New files:** `notebooks-v2/23_rank_effects.ipynb`, `assets/rank-effects-dissociation.png`, `assets/temporal-spectrum.png`

**Updated:** `README.md` (temporal spectrum graphic, rank effects hero chart, LHIPA reframing), `notebooks-v2/README.md` (NB 23 entry)

### Methodological patterns identified (science audit)

Three systemic issues affecting how results were reported throughout the project:

**1. Position-aggregate correlations reported as if trial-level.** The three headline rhos — LHIPA ρ = −0.903, Butterworth ρ = −0.618, forward dwell ratio ρ = +0.82 — are all computed on N = 9–11 position-level aggregates (means or medians), not individual trials. Citing "N = 2,719 trials" alongside a correlation computed on 11 points creates a false impression of statistical power. Trial-level correlations are much weaker (e.g., LHIPA ρ = −0.088). Every position-aggregate statistic now states the actual N of the aggregation.

**2. Survivor bias in per-position analyses.** Not all trials reach every position (pos 0: 2,742; pos 9: 640). Position means at later positions come from self-selected thorough scanners who scrolled the full page. This inflates apparent dwell at later positions and may bias Butterworth LF/HF medians. Added to methodological-threats.md. This also connects to the F-pattern: Nielsen's aggregate heatmap conflates compiled criteria (real), survey-phase concentration at top (real), and survivor selection (artifact).

**3. Mean vs median LHIPA sensitivity.** The LHIPA "gradient" by click position appears in means (right-skewed distribution pulls the mean up at early positions) but disappears in medians (flat 0–8). The gradient in the mean is partly a confound: high-LHIPA (low-load) trials tend to be easy trials where the user clicked early. The median is the robust estimator and reveals the boundary-step pattern.

**Corrected notebooks:** NB05 (LHIPA: figure title, summary, key measures table), NB06 (orientation/evaluation: "Working Memory Accumulation" → "Evaluation Effort by Position," removed WM ramp narrative, corrected LHIPA claims, "dwell" → "gaze dwell ratio").

## v8 — 2026-04-04

### Per-position cognitive load: working memory hypothesis reversed

Duchowski (2026, PACM CGIT) recommended Butterworth IIR over wavelet LHIPA for short-window cognitive load. Minimum windows: FFT 10s, DWT 7.5s, Butterworth 1s. Implemented per-position LF/HF ratio for all 2,719 trials.

**The working memory hypothesis was wrong.** LF/HF *decreases* with position (ρ = −0.618, p = 0.04). Cognitive load peaks at position 0, drops steeply through 0–3, plateaus through 4–10. This contradicts the §3a interpretation that forward-only dwell increase (ρ = +0.82) reflects growing working memory load.

**Correction:** The prior interpretation in §3a ("cognitive load increases with foraging depth because the candidate set in working memory grows") has been revised. The dissociation between increasing dwell time and decreasing cognitive effort indicates evaluation becomes *routinized* through framework compilation, not overloaded through working memory accumulation. The Shi et al. (2025) lit note connection claiming per-result LHIPA showed increasing load was also corrected — wavelet LHIPA at ~2s granularity was below Duchowski's stated 7.5s minimum, making that trend unreliable.

**New files:** `scripts/compute_butterworth_lfhf.py`, `notebooks-v2/14_butterworth_cognitive_load.ipynb`, `docs/lit-notes/duchowski2026-realtime-pupil-lfhf.md`, `AdSERP/data/butterworth-lfhf-by-position.json`

**Updated:** `data_loader.py` (added `load_pupil_trial()`, `remove_blinks()`), `references.bib` (added `duchowski2026realtime`), `findings.md` (§3b-iv, §3a correction), `README.md` (notebook 14, key insight)

### Thumbnail screenshot fix

`build-gh-pages.js` PNG screenshot loop crashed without error handling, producing only 2 of 10 thumbnails. Added try/catch.

## v7 — 2026-04-03

(See git log for v7 changes — survey phase, ski-jump decomposition, forward/regression split, README rewrite, arxiv stub)

## v6 — 2026-04-02

### Semantic embeddings tested and null

Sentence-level cosine similarity (mxbai-embed-large) between each result's snippet embedding and the centroid of all prior result embeddings. Null within-position — same as bag-of-words. The priming hypothesis is now tested at three granularities (bag-of-words, semantic embeddings, within-position controls) and null at all of them.

### §9: Where relaxing the serial evaluation assumption helps

New findings section analyzing when non-serial SERP models add value. Acknowledges forced-choice inflation of regression rates, notes that at-scale regression prevalence (`click_rank < max_scroll_depth`) is unmeasured. Identifies three areas where complexity helps: position bias estimation, stop/regress/paginate decision, re-finding task metrics.

### Orientation time: 194ms median

Page orientation (time from page load to first fixation on any result) is 194ms median across all groups — consistent with a well-memorized SERP layout. Previously reported as ~1-3s from a regression intercept (a different metric).

### Lit review and references

11 new bibtex entries. Literature review on scroll regressions identifies 5 novelty claims. Key finding from the review: nobody has published the at-scale prevalence of `click_rank < max_scroll_depth` despite every search engine having this data.

## v5 — 2026-04-02

### Bug fix: FPOGY out-of-bounds clamp

The Gazepoint GP3 HD reports gaze Y coordinates that exceed screen boundaries. 24.5% of fixations have `FPOGY > screen_height` (1024px); the 95th percentile is 1830px. These out-of-bounds samples were added to scroll offset to compute page-space Y, attributing fixations to SERP positions below the visible viewport.

**Impact:** Position 9 dwell ratios were inflated by 3-50x per trial (mean 2.9×, 89% of trials >1.0). The aggregate dwell ratio for position 9 was 1.25 — now corrected to 0.79.

**Fix:** Clamp `FPOGY` to `[0, screen_height]` before computing `page_y = fy + scroll_offset` in `compute_fixation_per_result()`. Applied in `serp_priming.ipynb` (Cells 13, 16) and `fixation_coverage.ipynb` (Cell 3).

**Note for AdSERP users:** If you are working with the AdSERP fixation data and mapping gaze coordinates to page-space positions, always clamp or filter FPOGY to screen bounds first. The eye tracker does not constrain gaze reports to the application window.

**Other v5 changes:**
- Forward-only shape test ρ strengthened from +0.73 to +0.82 (positions 0-8)
- Dwell table in README and findings updated with corrected values

### New: Scroll kinematics analysis (`scroll_kinematics.ipynb`)

Tests the viewport mechanics confound hypothesis: does ballistic backward scrolling explain the apparent "priming during regressions" pattern?

**Results:**
- Backward scroll velocity > forward: median 915 vs 784 px/s, peak 1852 vs 1111 px/s
- Velocity profile is ballistic: ρ = 0.867 between distance-from-target and velocity
- 87.3% of regression targets are positions 0-4 (median: position 2)
- Regression velocity mediates the dwell delta: ρ = -0.762 (p = 0.017) across positions

Positions 6-8 are ballistic transit zones (high velocity, short viewport, suppressed fixations). The "priming during regressions" pattern is a viewport mechanics artifact.

### Prose cleanup: unsupported priming claims

Corrected language in README.md, TODO.md, findings.md, and adserp-key-claims.md that framed the regression-trial overlap correlation (r = -0.033) as evidence that "priming operates in re-evaluation." The signal is triply confounded:

1. **Position-overlap covariation** — within-position controls null (v3)
2. **Repetition/recognition** — revisiting already-read content produces shorter dwell (v4)
3. **Ballistic scroll kinematics** — high-velocity transit biases viewport time and fixation count (v5)

---

## v4 — 2026-04-01

### Bug fix: viewport time computation

The prior `compute_viewport_time` only counted time between scroll events. Pre-scroll periods (page load → first scroll) and post-scroll periods were dropped. Position 0 dwell ratios were >1.0 (up to 73×). Fixed by covering the full trial window. Position 0 dwell ratio corrected from 1.35 → 0.28.

### New: forward-only shape test

Isolating forward-scanning periods, gaze dwell ratio *increases* with position (ρ = +0.73), opposite the priming prediction. The aggregate priming correlation was entirely driven by regression artifacts.

### New: p(fixate | visible) analysis

Forward-only p(fixate) is ~99.8% at every position. Users fixate virtually everything during first-pass scanning. No skip decision for overlap to predict.

### Metric rename

"Eval rate" / "attention density" → "gaze dwell ratio" (fixation duration / visible duration).

---

## v3 — 2026-04-01

### Within-position controls

Testing high-overlap vs low-overlap at the same rank: null across all metrics (TFT, TFC, mean fixation duration, viewport time). The aggregate priming correlation (r = -0.054) was driven by the position-overlap confound.

---

## v2 — 2026-04-01

### Regression-stratified analysis

Aggregate effect concentrated in regression trials (r = -0.033), null in first-pass (r = -0.002). Initially reframed as "priming facilitates re-evaluation" — later shown to be confounded (v3-v5).

---

## v1 — 2026-04-01

### Initial analysis

- Lexical overlap builds rapidly down the SERP (62% by position 9)
- Aggregate priming correlation: partial r = -0.054 (p = 2.4×10⁻⁹)
- 69% scroll regression prevalence, mean 2.8 per trial
- Mouse-gaze convergence depends on click intent
- Viewport state predicts clicks better than distance (AUC 0.704 vs 0.548)
- Per-participant variance large (acquisition onset SD = 2.5s)
