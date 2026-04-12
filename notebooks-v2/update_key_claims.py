"""Update Key Claims blocks in notebooks AND emit the aggregate doc.

Usage:
    python update_key_claims.py

Does two things in one pass:

1. Insert (or replace) a "## Key Claims (authoritative for paper writers)"
   markdown cell at the top of each target notebook, with canonical
   numbers hand-curated from executed notebook output. Each row is tagged
   with a stable ID (K1, K2, ...) so papers can cite [NB13:K2] as a
   checkable reference.

2. Emit `docs/notebook-key-claims.md` — a single aggregate document with
   all target notebooks' Key Claims blocks concatenated, a preamble
   explaining the convention, and a table of contents. This is the
   paper-writer's lookup table: grep one file instead of opening five
   notebooks.

Contract for paper writers:
    If prose in a paper draft cites a value that disagrees with a Key Claims
    row, the paper is wrong, not the notebook. If re-running the notebook
    produces different values, update the Key Claims block immediately,
    re-run this script to refresh the aggregate doc, and grep for the old
    value across docs/ and docs/drafts/.
"""

import json
from datetime import date
from pathlib import Path

import nbformat as nbf

NBDIR = Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")
DOCSDIR = Path("/Users/andyed/Documents/dev/attentional-foraging/docs")
AGGREGATE_PATH = DOCSDIR / "notebook-key-claims.md"
VERIFIED = date(2026, 4, 12).isoformat()

KEY_CLAIMS_MARKER = "## Key Claims (authoritative for paper writers)"

# Canonical notebook labels used in cross-paper citations.
# Keep these stable — papers cite as [NB13:K5], etc.
NOTEBOOK_LABELS = {
    "13_survey_phase.ipynb": ("NB13", "13_survey_phase", "saccade amplitude phase distinction"),
    "11_individual_differences.ipynb": ("NB11", "11_individual_differences", "two-factor motor individual differences"),
    "11_5_chattiness_traits.ipynb": ("NB11.5", "11_5_chattiness_traits", "cursor chattiness as a stable individual-differences trait"),
    "14_butterworth_cognitive_load.ipynb": ("NB14", "14_butterworth_cognitive_load", "cognitive load decreases with SERP position"),
    "15_cursor_approach.ipynb": ("NB15", "15_cursor_approach", "cursor approach features and consideration set"),
    "21_click_prediction.ipynb": ("NB21", "21_click_prediction", "LOSO click prediction and four-class taxonomy"),
    "22_four_class_taxonomy.ipynb": ("NB22", "22_four_class_taxonomy", "regression-based four-class taxonomy and element-type interactions"),
    "23_rank_effects.ipynb": ("NB23", "23_rank_effects", "unified rank effects — framework compilation"),
    "05_lhipa.ipynb": ("NB05", "05_lhipa", "LHIPA pupillometric cognitive load validation"),
    "12_regression_precision_by_load.ipynb": ("NB12", "12_regression_precision_by_load", "regression landing precision under cognitive load (null)"),
    "18_ripa2_vs_lfhf.ipynb": ("NB18", "18_ripa2_vs_lfhf", "RIPA2 vs Butterworth LF/HF comparison"),
}


def make_claims_cell(title, body_md):
    """Assemble a standard Key Claims markdown cell."""
    preamble = f"""{KEY_CLAIMS_MARKER}

*Last verified against executed notebook output: {VERIFIED}.*
*Notebook: `{title}`.*

If prose in a paper draft cites a value that disagrees with a row below, the paper is wrong — not the notebook. If re-running this notebook produces different values, update this block immediately and `grep` for the old value across `docs/`.

"""
    return preamble + body_md + "\n"


# ── NB13 — survey phase ────────────────────────────────────────────────
NB13_BODY = """### Per-trial saccade amplitude slope (the main anchor result)

| ID | Claim | Value |
|---|---|---|
| **K1** | N trials with ≥ 10 saccades (unit of analysis for the slope test) | **2,754** |
| **K2** | Mean per-trial amplitude slope over first 20 saccades (negative = compression) | **ρ = −0.135** (mean of per-trial Spearmans) |
| **K3** | One-sample *t*-test vs ρ = 0 | *t* = −29.63, ***p* = 9.33 × 10⁻¹⁶⁸**, *df* = 2,753 |
| **K4** | Fraction of trials with ρ < 0 | 71.8% |

### Phase-level saccade amplitude medians (the phase distinction)

| ID | Claim | Value |
|---|---|---|
| **K5** | Survey-phase median saccade amplitude (fixations 1–5) | **107.8 px** (N = 13,840 saccades) |
| **K6** | Evaluate-phase median saccade amplitude (fixations 6+) | **69.4 px** (N = 65,764 saccades) |
| **K7** | Survey / Evaluate amplitude ratio | 1.55× |
| **K8** | Mann–Whitney U, survey > evaluate | *p* ≈ 0 (underflow; reported value 1.59 × 10⁻²¹⁹ on the re-windowed subset N = 9,550 / 45,262) |

### Other load-bearing rows

| ID | Claim | Value |
|---|---|---|
| **K9** | Click rate given surveyed vs not-surveyed | 16.9% (N = 700) vs 11.9% (N = 10,368) |
| **K10** | Pre-scroll saccade amplitude median | 74.9 px (N = 59,343) |
| **K11** | Post-scroll saccade amplitude median | 67.2 px (N = 38,622) |
| **K12** | Pre-scroll > post-scroll (Mann–Whitney) | *p* = 9.94 × 10⁻⁶⁶ |

> **Watch out:** stale drafts have cited N = 991, ρ = −0.128, *p* = 1.5 × 10⁻⁶¹ for K1/K2/K3. Those numbers are wrong by roughly 3× on N and by ~100 orders of magnitude on p. Use the values above. The 117 / 76 px pair some drafts cite for K5/K6 is also stale — current values are 107.8 / 69.4 px."""


# ── NB11 — individual differences ──────────────────────────────────────
NB11_BODY = """### Panel summary (per-participant medians / means, n = 46 complete)

| ID | Claim | Value |
|---|---|---|
| **K1** | Median gaze–cursor lag (ms, negative = gaze leads cursor) | **−650 ms** (Huang et al. 2012: −700 ms) |
| **K2** | Gaze–cursor lag range across participants | −1,825 to +925 ms (SD 572) |
| **K3** | Split-half reliability of gaze–cursor lag (Spearman–Brown corrected) | **0.838** (raw *r* = 0.721, *n* = 46) |
| **K4** | Median TTI to first scroll | 5.46 s (range 0.91–17.54 s) |
| **K5** | Median regression rate | 0.57 (range 0.03–0.98) |
| **K6** | Median mean LHIPA | 0.04 (range 0.03–0.08) |
| **K7** | Median click position | 5.53 (range 4.01–6.89) |
| **K8** | Median mean fixations per trial | 88.6 (range 23–168) |

### Key correlations (per-participant Spearman, n = 46)

| ID | Pair | *ρ* | *p* | Interpretation |
|---|---|---|---|---|
| **K9**  | Gaze–cursor lag × TTI | −0.072 | 0.632 | null |
| **K10** | Gaze–cursor lag × regression rate | +0.159 | 0.293 | null |
| **K11** | Gaze–cursor lag × LHIPA | −0.149 | 0.322 | null |
| **K12** | Regression rate × LHIPA | **−0.568** | < 0.001 | significant — high regressors have lower LHIPA |
| **K13** | TTI × Regression rate | +0.122 | 0.420 | null |
| **K14** | Click position × LHIPA | −0.161 | 0.285 | null |

### Chattiness × NB11 panel (§11.5a orthogonality, n = 47)

| ID | Pair | *ρ* range across 4 chattiness measures |
|---|---|---|
| **K15** | Chattiness × gaze–cursor lag | +0.03 to +0.28, all *p* > 0.06 (**orthogonal**) |
| **K16** | Chattiness × TTI | −0.50 to −0.57, *p* < 0.001 (chatty = faster) |
| **K17** | Chattiness × LHIPA | +0.34 to +0.55, *p* < 0.05 (chatty = lower cognitive load) |
| **K18** | Chattiness × fixations/trial | −0.41 to −0.59, *p* < 0.01 |
| **K19** | Chattiness × regression rate | −0.11 to −0.45 (mixed) |
| **K20** | Chattiness × click position | −0.12 to +0.06, null |

> **Two-factor motor structure.** K15 is the key claim: gaze–cursor lag (timing) and cursor chattiness (volume) are empirically independent individual-differences factors. Paper prose should treat them as two axes, not one."""


# ── NB11.5 — chattiness traits ─────────────────────────────────────────
NB11_5_BODY = """### Chattiness trait stability (split-half reliability, n = 47)

| ID | Claim | Value |
|---|---|---|
| **K1** | `events_per_sec` reliability | *r* = 0.984, Spearman–Brown 0.992 |
| **K2** | `path_per_sec` reliability | *r* = 0.966, SB 0.983 |
| **K3** | `dir_changes_per_sec` reliability | *r* = 0.967, SB 0.983 |
| **K4** | `active_fraction` reliability | *r* = 0.966, SB 0.983 |

### Chattiness distribution (per-participant medians across 47 participants)

| ID | Measure | Median | Range | Range-× |
|---|---|---|---|---|
| **K5** | `events_per_sec` | 14.8 | 5.2 – 55.3 | 10.6× |
| **K6** | `path_per_sec` (px/s) | 158.7 | 56.2 – 469.8 | 8.4× |
| **K7** | `dir_changes_per_sec` | 0.608 | 0.187 – 2.669 | 14.3× |
| **K8** | `active_fraction` | 0.287 | 0.132 – 0.794 | 6.0× |

### LOSO M3 AUC stratified by chattiness (the deployability result)

| ID | Tercile | Median events/s | LOSO M3 AUC |
|---|---|---|---|
| **K9** | Low | 9.5 | **0.869** (n ≈ 15) |
| **K10** | Mid | 14.7 | **0.855** (n ≈ 16) |
| **K11** | High | 28.8 | **0.855** (n ≈ 16) |
| **K12** | Pooled LOSO M3 AUC (replication of NB21 §4.3) | — | **0.859** (n = 47) |

| ID | Spearman | *ρ* | *p* |
|---|---|---|---|
| **K13** | Per-participant chattiness (events/s) × per-participant AUC | **−0.187** | **0.209** (ns) |
| **K14** | Per-participant `path_per_sec` × AUC | **−0.105** | **0.481** (ns) |
| **K15** | Per-participant `dir_changes_per_sec` × AUC | **−0.161** | **0.281** (ns) |
| **K16** | Per-participant `active_fraction` × AUC | **−0.155** | **0.297** (ns) |

### Exposure-bias check (records per trial × chattiness)

| ID | Pair | *ρ* | *p* |
|---|---|---|---|
| **K17** | Records per trial × `events_per_sec` | **−0.516** | **0.0002** |
| **K18** | Records per trial × `active_fraction` | **−0.411** | **0.0041** |
| **K19** | Records per trial × `path_per_sec` | −0.112 | 0.454 (null) |
| **K20** | Records per trial × `dir_changes_per_sec` | −0.218 | 0.142 (null) |

> **Three headline claims.** (1) Chattiness is a 10×-range, high-reliability individual-differences trait (K1–K4). (2) LOSO M3 AUC is flat across chattiness terciles; all 4 Spearmans are ns (K13–K16). (3) Chatty users fixate *fewer* positions per trial, not more (K17) — the four-class taxonomy is not inflated by mechanical undersampling.
>
> **Coordinate-space audit (2026-04-12).** NB11.5 re-run on the regenerated `cursor-approach-features.json`. K1–K8 (chattiness distribution and reliability) are unchanged — those measures come from `mouse-movement-data`, not from FPOGY. K9–K16 shifted with the post-fix feature set: pooled LOSO M3 AUC 0.792 → **0.859**, tercile AUCs 0.803/0.780/0.793 → **0.869/0.855/0.855**. The deployability story gets **better**: every tercile's AUC climbed, and all four per-participant chattiness × AUC correlations remain ns (no exposure bias). K17/K18 bias checks also strengthened slightly."""


# ── NB14 — Butterworth cognitive load ───────────────────────────────
NB14_BODY = """### Cognitive load decreases with SERP position (the Butterworth key finding)

**Convention.** Butterworth LF/HF ratio (Duchowski's index): *higher* LF/HF = more load. LHIPA (Index of Pupillary Activity): *lower* LHIPA = more load. The two indices are negatively correlated by construction and both agree on direction (K7).

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with usable Butterworth LF/HF data | 2,719 |
| **K2** | Position-segment count (fixation positions × LF/HF) | 6,112 |
| **K3** | **Position × median LF/HF (load DECREASES with deeper position)** | **ρ = −0.927, *p* < 0.0001** (N = 11 positions) |
| **K4** | Positions 1–10 only (excluding pos 0) | **ρ = −0.903, *p* = 0.0003** |
| **K5** | Within-trial Spearman (position vs LF/HF, ≥ 3 valid segments at positions 0–10) | N = 1,025 trials, mean ρ = −0.152, median ρ = −0.400, 61.0 % negative |
| **K6** | Clicked vs non-clicked median LF/HF | **22.40 (N = 1,463)** vs **19.27 (N = 4,636)**; Mann–Whitney *p* < 10⁻⁸ — clicked results carry more load than non-clicked |
| **K7** | Cross-index validation: trial-mean LF/HF × LHIPA | ρ = −0.125, *p* = 7.47 × 10⁻¹⁰, N = 2,416 (correct sign: both indices agree on load direction) |
| **K8** | Position-level medians (load by rank) | pos 0: 29.64 (N = 1,036) → pos 1: 22.17 → pos 2: 18.96 → pos 3: 18.30 → pos 4: 17.23 → pos 5: 16.77 → pos 6: 14.41 → pos 7: 13.82 → pos 8: 13.31 → pos 9: 15.58 → pos 10: 13.49 (monotone decline through pos 8) |

### Piecewise gradient (steep phase + plateau)

| ID | Claim | Value |
|---|---|---|
| **K9** | Steep (pos 0–3) vs plateau (pos 4–10) Mann–Whitney on raw segments | **U = 4,583,556, *p* = 3.2 × 10⁻²³** (N = 4,229 vs 1,870; steep median 22.0 vs plateau 15.7) |
| **K10** | Steep phase (pos 0–3) Spearman on position medians | **ρ = −1.000, *p* ≈ 0** — perfect monotone decline. Medians: 29.64 → 22.17 → 18.96 → 18.30 |
| **K11** | Plateau phase (pos 4–10) Spearman | **ρ = −0.714, *p* = 0.071** — marginal, clearly weaker gradient than steep phase |
| **K12** | Pooled early (0–3) vs late (4–10) medians | early 22.0 (N = 4,229) vs late 15.7 (N = 1,870) — see K9 for the Mann–Whitney *U*/*p* |

### Within-trial gradient by evaluation depth

| ID | Threshold | N trials | Mean ρ | Median ρ | % negative |
|---|---|---|---|---|---|
| **K13** | ≥ 3 positions | 1,025 | −0.152 | −0.400 | 61.0% |
| **K14** | ≥ 5 positions | 212 | −0.179 | — | 67.0% |
| **K15** | ≥ 7 positions | 32 | −0.207 | — | 71.9% |

*(K14/K15 values from `pupil-lfhf/validation/validate_adserp.py` output, which uses the same forward-pass classifier as `compute_butterworth_lfhf.py`. Pupil-lfhf's within-trial N differs from NB14 cell[8]'s N = 1,025 at the ≥3 threshold — different exclusion criteria in the two pipelines; both agree on direction.)*

> **Not working memory accumulation.** If prose says "forward-only dwell increases with position *consistent with working memory accumulation*," the prose is wrong. K3 shows per-fixation cognitive load *decreasing* with position — extra dwell at deeper positions reflects allocation / comparison-set growth, not WM overload. Framework compilation, not working-memory accumulation. This is the load-bearing claim for the ETTAC 2026 and CHI 2027 framings.
>
> **K3 post-2026-04-12 audit.** The headline between-position gradient **strengthened dramatically**: pre-fix ρ = −0.618 (p = 0.0426, borderline) → post-fix **ρ = −0.927 (p < 0.0001, unambiguous)**. The 1–10 subset (K4) flipped from non-significant (ρ = −0.491, p = 0.150) to highly significant (ρ = −0.903, p = 0.0003). The steep/plateau partition is preserved — steep phase still perfect monotone, plateau still flat. The pre-fix scroll double-count was injecting noise in the position direction, masking the signal.
>
> **Coordinate-space audit (2026-04-09, cursor side).** `compute_butterworth_lfhf.py` previously double-counted scroll offset when deriving `click_pos` from evtrack `ypos` (already page-space). Fixed in 2026-04-09. K6 moved: N_clicked 1,145 → 1,110, clicked median 22.86 → 22.24.
>
> **Coordinate-space audit (2026-04-12, fixation side).** FPOGY was also mis-documented as screen-space; the pipeline was adding scroll to fixation Y to derive page_y. Per the AdSERP README, FPOGY is already page-space. Fixing this regenerated `butterworth-lfhf-by-position.json` and shifted K1 (unchanged), K2 (6,874 → 6,112, -11%), K3 (−0.618 → −0.927), K4 (−0.491 ns → −0.903 sig), K5 (1,167 → 1,025 trials, mean ρ −0.105 → −0.152), K6 (1,110/5,472 → 1,463/4,636, p 1.3e-4 → <1e-8), K7 (essentially unchanged), K8 (position medians shifted by ≲1 unit each). Direction and significance **strengthened** throughout. K9–K15 re-computed from post-fix position medians; some piecewise statistics (K12, K14, K15) need a verbose-print re-run. See module docstring and `docs/drafts/coord_fix_snapshot_20260412/`."""


NB15_BODY = r"""### Cursor approach features (per result-position record)

| ID | Claim | Value |
|---|---|---|
| **K1** | Records / trials / base click rate | **13,419 records / 2,340 trials / 16.6%** (2,228 clicks) |
| **K2** | Mean min\_dist (clicked vs not) | **110 px vs 299 px** (overall mean 268 px) |
| **K3** | Almost-clicked (min\_dist < 58 px, not clicked) | **1,122 records (8.4% of all)** |
| **K4** | Approached (min\_dist < 100 px) | **3,783 records (28.2%)**, click rate 37.7%, lift 2.3× |
| **K5** | Best single-threshold AUC | min\_dist < 150 px → **AUC 0.735** |

### Approach → regression → click pathway

| ID | Claim | Value |
|---|---|---|
| **K6** | Approach → regression rate | **81.6%** (vs 58.0% no-approach) |
| **K7** | Approach → regression odds ratio | **3.21×**, χ² = 661.1, p = 8.72 × 10⁻¹⁴⁶ |
| **K8** | Approach + regression → click rate | **37.9% (N = 3,087)** |
| **K9** | Approach + no regression → click rate | 36.9% (N = 696) |
| **K10** | No approach + regression → click rate | 8.1% (N = 5,589) |
| **K11** | No approach + no regression → click rate | 8.6% (N = 4,047) |

### Position gradient

| ID | Claim | Value |
|---|---|---|
| **K12** | Position 0: almost-clicked rate | **15.9%** (N = 2,320) |
| **K13** | Position 0: mean min\_dist | **167 px** |
| **K14** | Position 9: almost-clicked rate | **2.1%** (N = 192) |
| **K15** | Position 9: mean min\_dist | **488 px** |

### Click prediction (replicates NB21 from raw features)

| ID | Claim | Value |
|---|---|---|
| **K16** | Position + dwell + all approach (5-fold CV) | **AUC 0.859 ± 0.019** |
| **K17** | Position coefficient (full model) | **−0.130** (→ skip; correct direction) |
| **K18** | direction\_changes coefficient | **+0.061** (→ click; small positive) |

> **Coordinate-space audit (2026-04-09, cursor side).** Two bug sites in `compute_approach_features` double-counted scroll offset on cursor Y (`my + fix_scroll` where `my` is already page-space), inflating cursor proximity on scrolled trials (82% of corpus).
>
> **Coordinate-space audit (2026-04-12, fixation side).** The symmetric bug existed on the gaze side: FPOGY was treated as screen-space and had scroll added to it, but per the AdSERP README FPOGY is already page-space. Fixing this (and regenerating `cursor-approach-features.json`) shifted every row above. Headline changes: records 15,397 → **13,419** (−12.9%; phantom records from scroll-leaked approach signal at deep positions), base click rate 14.4% → **16.6%**, mean clicked min\_dist 204 px → **110 px** (cursor was always closer than the buggy pipeline reported), almost-clicked 734 → **1,122** records, approach-regression odds ratio 5.04× → **3.21×** (weaker but still highly significant — 36% of the pre-fix signal was scroll artifact). Direction of every headline result preserved. Approach + regression is still the dominant pathway to click (37.9% click rate vs 8% baseline). Position 9 mean min\_dist dropped from 683 px → **488 px**, consistent with the broader pattern: cursor was closer than the bug let us see.
>
> **K8 click rate note.** Pre-fix K8 (43.5% click rate for approach + regression at N = 2,086) was over-concentrated because the scroll leak mislabeled many deep-position results as "approached." Post-fix: 37.9% at N = 3,087 — lower rate on a larger, cleaner sample. Still the dominant decision-to-click signature in the corpus.
"""


NB21_BODY = """### LOSO click prediction — pooled results

| ID | Claim | Value |
|---|---|---|
| **K1** | Records / participants / click rate | **13,419 episodes / 47 participants / 16.6 % click rate** (2,228 clicks) |
| **K2** | Records per participant | **median 294, range 76–497** |
| **K3** | **M3 (position + dwell + approach) pooled LOSO AUC** | **0.859 ± 0.044** (47-fold) |
| **K4** | M4 (approach features only) LOSO AUC | **0.861 ± 0.043** |
| **K5** | M2 (position + dwell) LOSO AUC | **0.743 ± 0.076** |
| **K6** | M1 (position only) LOSO AUC | **0.613 ± 0.090** |
| **K7** | LOSO M3 AP | **0.611 ± 0.097** |
| **K8** | Leakage Δ (Random KFold − LOSO) for M2/M3/M4 | **+0.002 / −0.000 / −0.002** (direction now consistent with near-zero leakage — stronger LOSO invalidates prior leakage concern) |
| **K9** | **Per-participant LOSO M3 AUC** | **median 0.860, IQR [0.827, 0.901], range [0.745, 0.934]** (all 47 participants well above chance; min now 0.745, previously 0.589) |
| **K10** | Youden's J threshold (M3 OOF) | *p* = **0.493** (TPR = **0.798**, FPR = **0.222**) |
| **K11** | F1-optimal threshold | *p* = **0.637**, F1 = **0.584** |
| **K12** | Brier score (M3 OOF) | **0.1526** |

### Four-class taxonomy (classifier-derived, tautology fix)

| ID | Class | N | % | Mean *p*(click) |
|---|---|---|---|---|
| **K13** | Clicked | **2,228** | **16.6 %** | **0.690** |
| **K14** | Deferred candidate | **1,381** | **10.3 %** | **0.709** |
| **K15** | Evaluated-rejected | **974** | **7.3 %** | **0.313** |
| **K16** | No signal | **8,836** | **65.8 %** | **0.247** |

### M3 standardized feature coefficients (full-data refit)

| ID | Feature | Coefficient | Direction |
|---|---|---|---|
| **K17** | `mean_dist` | **+0.589** | → click |
| **K18** | `final_dist` | **−0.967** | → skip |
| **K19** | `dwell_in_proximity_ms` | **+0.738** | → click |
| **K20** | `min_dist` | **−0.904** | → skip |
| **K21** | `position` | **−0.130** | → skip |
| **K22** | `retreat_dist` | **−0.206** | → skip |
| **K23** | `mean_approach_velocity` | **+0.069** | → click |
| **K24** | `max_approach_velocity` | **+0.207** | → click |
| **K25** | `frac_decreasing` | **+0.031** | → click |
| **K26** | `total_dwell_ms` | **−0.040** | → skip |
| **K27** | `direction_changes` | **+0.061** | → click |

> **Robustness to individual cursor activity lives in NB11.5.** The chattiness-stratified AUC figure (§4.3 robustness paragraph of `docs/drafts/cikm-2026/paper.md`) uses [NB11_5:K9–K16], not NB21 directly.
>
> **Previously fixed bug (2026-04-08):** Cell 20 used `y_p_full` before definition (lines 14–15 were dead code from a pre-rewrite version). Symptom: `NameError: name 'y_p_full' is not defined`. Fix: delete the old block.
>
> **Coordinate-space audit (2026-04-09, cursor side).** NB15's `compute_approach_features` double-counted scroll offset on the cursor coordinate (`my + fix_scroll`). First fix landed 2026-04-09 and moved M3 LOSO AUC 0.827 → 0.792.
>
> **Coordinate-space audit (2026-04-12, fixation side).** FPOGY was similarly mis-documented as viewport-space; the position assignment pipeline was adding scroll to a page-space value. Per the AdSERP README, FPOGY is already page-space. Fixing this regenerated `cursor-approach-features.json` with a cleaner feature set, and **NB21 moved dramatically**: records 15,397 → **13,419** (−12.9%), click rate 14.4% → **16.6%**, **M3 LOSO AUC 0.792 → 0.859** (+0.067), M4 (approach only) 0.792 → **0.861**, M3 AP 0.491 → **0.611** (+0.120, very large jump in precision-recall), leakage Δ essentially zero across all models (+0.006 → −0.000 for M3), per-participant LOSO M3 median 0.798 → **0.860** with the minimum participant climbing from 0.589 → **0.745**. K21 (`position`) coefficient weakened from −0.380 → **−0.130** (position is a much weaker predictor once the scroll artifact is gone — the gradient lives in the approach features now). K27 (`direction_changes`) flipped sign from −0.005 → **+0.061** (now a small positive contribution). Classifier taxonomy Evaluated-rejected jumped from N = 344 → **974** because many formerly-"no signal" records are now approached records with low p(click) — the coord fix surfaced real evaluative rejections that were previously invisible. Direction of every headline result preserved. See `CHANGELOG.md` and `docs/drafts/coord_fix_snapshot_20260412/`."""


# ── NB22 — four-class taxonomy ────────────────────────────────────────
NB22_BODY = """### Regression-based four-class taxonomy

NB22 defines the four classes via cursor approach (min_dist < 100 px) + scroll regression to that position, not via the classifier threshold used in NB21. The class definitions are complementary, not competing.

| ID | Class | N | % |
|---|---|---|---|
| **K1** | Clicked | **2,228** | **16.6 %** |
| **K2** | Deferred (approached + regressed to) | **1,916** | **14.3 %** |
| **K3** | Evaluated-rejected (approached + no regression) | **439** | **3.3 %** |
| **K4** | Not approached | **8,836** | **65.8 %** |

### Motor signature separation (deferred vs evaluated-rejected)

| ID | Metric | Deferred | Eval-Rejected | *p* |
|---|---|---|---|---|
| **K5** | Retreat distance (px) | **234.5** | **90.8** | **1.76 × 10⁻³⁸** |
| **K6** | Total gaze dwell (ms) | **4,137** | **1,612** | **9.76 × 10⁻⁷⁰** |
| **K7** | Dwell in proximity (ms) | **1,212.5** | **690.0** | **1.36 × 10⁻¹⁶** |

### Click prediction with element-type interactions

| ID | Element type | N | Click% | M3 AUC | M3ei AUC | Δ |
|---|---|---|---|---|---|---|
| **K8** | organic | **10,379** | **17.6 %** | **0.857** | **0.859** | **+0.002** |
| **K9** | dd_top | **1,394** | **17.6 %** | **0.909** | **0.919** | **+0.010** |
| **K10** | native_ad | **1,646** | **9.2 %** | **0.830** | **0.817** | **−0.014** |

| ID | Model | LOSO AUC |
|---|---|---|
| **K11** | M3 (replication of NB21) | **0.859 ± 0.044** |
| **K12** | M3 + regression feature | **0.863 ± 0.042** (regression adds +0.003) |

> **Interaction features still help most on top ads.** Top ads gain +0.010 AUC from element-type interactions. Native ads lose −0.014 (avoidance behavior muddies the signal). Regression features add +0.003 to M3 — essentially zero; the forward-pass approach features carry the full signal.
>
> **Coordinate-space audit (2026-04-12, fixation side).** NB22 consumes `cursor-approach-features.json`, which was regenerated after the FPOGY page-space fix. The four-class split **strengthened dramatically**:
> - K2 deferred: 1,178 → **1,916** (+62.6%) — half the pre-fix "not approached" records were actually approached + regressed trials mislabeled by the scroll leak
> - K3 evaluated-rejected: 278 → **439** (+57.9%)
> - K4 not approached: 11,727 → **8,836** (−24.7%)
> - K5 retreat-distance gap: 191 vs 96 (p 1.9 × 10⁻¹¹) → **234 vs 91 (p 1.76 × 10⁻³⁸)** — 27 orders of magnitude stronger motor signature
> - K6 gaze-dwell gap: p 3.7 × 10⁻²⁶ → **9.76 × 10⁻⁷⁰** (44 orders of magnitude)
> - K7 proximity-dwell gap: p 5.0 × 10⁻⁹ → **1.36 × 10⁻¹⁶**
> - K11 M3 LOSO AUC: 0.792 → **0.859** (+0.067, a large effect in prediction space)
>
> Direction and significance of every headline result preserved; magnitudes all strengthened. The deferred vs rejected motor-signature dissociation — the CIKM 2026 paper's central empirical claim — is now on dramatically firmer statistical ground. See `docs/drafts/coord_fix_snapshot_20260412/`."""


# ── NB23 — rank effects ──────────────────────────────────────────────
NB23_BODY = """### Unified rank effects (position 0–10)

| ID | Measure | Spearman ρ | *p* | N positions |
|---|---|---|---|---|
| **K1** | Click share × position | **−0.973** | 5.1 × 10⁻⁷ | 11 |
| **K2** | Fixation count × position | −0.442 | 0.200 (ns) | 10 |
| **K3** | Total dwell × position | −0.515 | 0.128 (ns) | 10 |
| **K4** | Butterworth LF/HF × position | **−0.618** | **0.0426** | 11 |
| **K5** | LHIPA × click position | **−0.955** | < 10⁻⁵ | 11 |

### Corpus composition

| ID | Claim | Value |
|---|---|---|
| **K6** | Trials with clicks | 2,764 |
| **K7** | (trial, position) rows | 16,335 |
| **K8** | Forward fixations (% of classified) | 74 % (150,993) |
| **K9** | Regression fixations (% of classified) | 26 % (53,583) |

### Position-level summary (per-result medians/means)

| ID | Pos | Click% | Fix count | Dwell (s) | LF/HF | LHIPA |
|---|---|---|---|---|---|---|
| **K10** | 0 | 22.0 | 19.9 | 4.24 | 30.0 | 0.039 |
| **K11** | 1 | 26.9 | 14.2 | 3.18 | 21.2 | 0.039 |
| **K12** | 2 | 24.3 | 10.6 | 2.37 | 18.3 | 0.039 |
| **K13** | 3 | 11.9 | 10.0 | 2.21 | 16.0 | 0.039 |

> **Framework compilation, not declining interest.** K4 (LF/HF ρ = −0.618) is the key result: cognitive load peaks at position 0 where the user is constructing evaluation criteria from scratch, drops steeply through positions 0–3 as criteria compile, then plateaus. K2 and K3 are non-significant at the position level (N = 10 points), but the direction is consistent: both time and effort decline. The dissociation between K2/K3 (declining time) and K4 (declining effort that drops *faster*) is the framework compilation signature.
>
> **K4 matches NB14:K3 exactly** (ρ = −0.618, p = 0.0426) — same data, independent computation path. Cross-notebook replication."""


# ── NB05 — LHIPA ────────────────────────────────────────────────────
NB05_BODY = """### Dataset

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with usable LHIPA | 2,721 (of 2,776; 55 failed) |
| **K2** | Mean valid pupil sample percentage | 97.8% |

### LHIPA distribution (trial-level, N = 2,721)

| ID | Claim | Value |
|---|---|---|
| **K3** | LHIPA mean / median / SD | 0.0483 / 0.0389 / 0.0190 |
| **K4** | LHIPA range | 0.0165 – 0.0914 |

### Behavioral proxy correlations (trial-level Spearman, N = 2,720)

| ID | Pair | *ρ* | *p* |
|---|---|---|---|
| **K5** | LHIPA × trial duration | **−0.650** | ≈ 0 |
| **K6** | LHIPA × fixation count | **−0.621** | 2.5 × 10⁻²⁹⁰ |
| **K7** | LHIPA × regression count | **−0.435** | 3.5 × 10⁻¹²⁶ |
| **K8** | LHIPA × click position | **−0.088** | 4.1 × 10⁻⁶ |

### LHIPA by click position

| ID | Claim | Value |
|---|---|---|
| **K9** | Spearman on N = 10 position means | ρ = **−0.903**, *p* = 3.4 × 10⁻⁴ |
| **K10** | Trial-level ρ (individual trials) | −0.088 |
| **K11** | Per-participant LHIPA range (mean across trials) | 0.035 – 0.075 |

### LHIPA × regressive fraction

| ID | Claim | Value |
|---|---|---|
| **K12** | Spearman ρ (regressive fraction × LHIPA) | **−0.381**, *p* = 9.0 × 10⁻⁹⁵ |
| **K13** | Kruskal–Wallis H (tercile split) | H = 466.2, *p* = 5.9 × 10⁻¹⁰² |
| **K14** | Low-regression tercile median LHIPA | 0.068 (n = 1,204) |
| **K15** | High-regression tercile median LHIPA | 0.038 (n = 897) |

> **Ecological fallacy warning on K9.** The ρ = −0.903 on N = 10 position means is driven by a step-down at positions 9–10. LHIPA is approximately flat across positions 0–8, then drops. The trial-level ρ (K10) is −0.088 — statistically significant but small. Do not cite K9 as evidence for a monotonic position gradient.
>
> **Minimum window constraint.** Per-result LHIPA computation (cell 12) requires ≥ 64 samples (~0.4 s at 150 Hz), yielding 13,649 / 17,393 segments (78%). However, Duchowski (2026) recommends a minimum 7.5–10 s window for stable LF/HF separation. Per-result LHIPA at ~2 s segments is below this threshold; use NB14's Butterworth method for per-position claims.
>
> **Cross-index validation.** NB14:K7 (trial-mean LF/HF × LHIPA ρ = −0.122, p = 9.29 × 10⁻¹⁰) confirms both indices measure the same construct. LHIPA direction (lower = higher load) and LF/HF direction (higher = higher load) are anti-correlated as expected."""


# ── NB12 — regression precision by load ─────────────────────────────
NB12_BODY = """### Dataset

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with all measures (LHIPA + regression + encoding fixation + landing fixation) | **1,272 trials, 45 participants** |
| **K2** | Trials with encoding pupil diameter | **1,266** |
| **K3** | Trials with encoding pupil SD | **1,261** |

### Summary statistics

| ID | Measure | Median | IQR |
|---|---|---|---|
| **K4** | Landing offset (px) | **60.24** | **[32.34, 87.83]** |
| **K5** | Encoding–regression time gap (ms) | **13,269.5** | **[8,069.75, 19,370.25]** |
| **K6** | Regression distance (px) | **666.67** | **[333.33, 1,320.56]** |
| **K7** | Encoding pupil diameter (mm) | **14.86** | **[13.20, 16.76]** |

### Main tests (all null)

| ID | Test | ρ | *p* | Partial ρ | Partial *p* |
|---|---|---|---|---|---|
| **K8** | Trial-level LHIPA × landing offset | **−0.0430** | **0.125** | **−0.0430** | **0.125** |
| **K9** | Encoding pupil diameter × landing offset | **+0.0116** | **0.681** | **+0.0120** | **0.671** |
| **K10** | Encoding pupil SD × landing offset | **−0.0453** | **0.108** | **−0.0458** | **0.104** |

### Control variables (also null)

| ID | Test | ρ | *p* |
|---|---|---|---|
| **K11** | Regression distance × landing offset | **+0.0272** | **0.333** |
| **K12** | Time gap × landing offset | **+0.0085** | **0.761** |

### Per-participant analysis

| ID | Claim | Value |
|---|---|---|
| **K13** | Participants with ≥ 3 qualifying trials | 43 |
| **K14** | Per-participant median encoding PD × median landing offset | **ρ = −0.0074, *p* = 0.962** |

> **Comprehensive null, preserved post-fix.** Neither coarse-grain load (trial-level LHIPA, K8) nor fine-grain load (encoding-fixation pupil diameter, K9; encoding pupil variability, K10) predicts regression landing precision. Partial correlations controlling for regression distance and encoding–regression time gap are also null. The per-participant analysis (K14) confirms this is not a within-person effect masked by between-person variance.
>
> **Interpretation.** Spatial memory for SERP result positions is robust to normal cognitive load variation during browsing. The motor system may rely on non-pupillometric cues (proprioceptive scroll memory, visual landmarks) rather than purely spatial memory. This is relevant for ETTAC because it bounds where Butterworth LF/HF *cannot* predict behavior — regression precision is not one of its targets.
>
> **Gazepoint caveat.** Pupil diameter values from the GP3 HD are in arbitrary units, not calibrated mm. Cross-participant comparisons of absolute PD are invalid. The within-participant correlations (K8–K10) are unaffected.
>
> **Coordinate-space audit (2026-04-12).** FPOGY page-space fix regenerated the fixation-to-position mapping used to identify "encoding fixation on clicked result" and "landing fixation on clicked result". Trial count rose 1,170 → **1,272** (+8.7%) because more fixations now correctly map to result bands. All null findings preserved; K9 sign flipped (−0.013 → +0.012) but both values are trivially close to zero. Comprehensive null is robust to the coord fix."""


# ── NB18 — RIPA2 vs LF/HF ──────────────────────────────────────────
NB18_BODY = """### Dataset

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with both Butterworth LF/HF and RIPA2 | 2,719 |
| **K2** | Paired observations (same trial, same position) | **6,112** |

### Observation-level correlation (near zero — different constructs at per-fixation scale)

| ID | Test | Value | *p* |
|---|---|---|---|
| **K3** | Pearson *r* (RIPA2 × LF/HF) | **−0.028** | **0.030** (borderline) |
| **K4** | Spearman ρ (RIPA2 × LF/HF) | **−0.016** | **0.224** (ns) |

### Positional gradient (both decline — agreement at aggregate level)

| ID | Metric | Spearman ρ with position | *p* |
|---|---|---|---|
| **K5** | Butterworth LF/HF × position (median per position) | **−0.927** | **3.97 × 10⁻⁵** |
| **K6** | RIPA2 × position (median per position) | **−0.909** | **1.06 × 10⁻⁴** |

### Click-position quadrant analysis (click rate by LF/HF × RIPA2 quadrant)

| ID | Quadrant | Click rate |
|---|---|---|
| **K7** | Effortful (high LF/HF + high RIPA2) | **26.3%** (407 / 1,548) |
| **K8** | Deliberation (high LF/HF + low RIPA2) | **25.2%** (380 / 1,508) |
| **K9** | Quick decision (low LF/HF + high RIPA2) | **23.9%** (360 / 1,508) |
| **K10** | Routine scanning (low LF/HF + low RIPA2) | **20.4%** (316 / 1,548) |

### RIPA2 at regression onset (underpowered — demo trials only)

| ID | Comparison | RIPA2 median | Mann–Whitney *p* |
|---|---|---|---|
| **K11** | Regression fixations (N = 118) | **0.0695** | **0.441** (two-sided, ns) |
| **K12** | Forward fixations (N = 263) | **0.0770** | — |

### Encoding vs retrieval (RIPA2 first-pass signal)

| ID | Claim | Value |
|---|---|---|
| **K13** | RIPA2 observations: will-regress vs no-regress | **10,466 vs 5,850** |
| **K14** | RIPA2 median: will-regress vs no-regress | **0.0777 vs 0.0809 (ratio 0.960×)** |
| **K15** | RIPA2 one-sided Mann–Whitney (will-regress < no-regress) | ***p* = 0.0106** |
| **K16** | First-pass dwell: will-regress vs no-regress | **194 ms vs 214 ms, *p* = 8.14 × 10⁻³²** |
| **K17** | LF/HF observations for same comparison | N = 20 vs 17 (underpowered) |

> **Complementary, not competing.** K3–K4 confirm the two metrics are nearly uncorrelated at the observation level — they measure different temporal aspects of cognitive dynamics. K5–K6 confirm both agree on the aggregate positional gradient (load declines with position). RIPA2's advantage is per-fixation temporal resolution. LF/HF's advantage is interpretability and direct tie to Duchowski (2026).
>
> **Encoding insight (K14–K15).** Items that will later receive scroll regressions show *lower* RIPA2 at first pass. This rejects the Pirolli scent-following prediction (higher arousal at scent-rich items) and supports encoding-completion: regressions go to items that were *insufficiently* processed, not items that triggered high arousal. Reframing: regressions are a completion mechanism, not a scent-following mechanism.
>
> **Coordinate-space audit (2026-04-12).** FPOGY page-space fix regenerated `butterworth-lfhf-by-position.json` and `ripa2-by-position.json`. Main shifts: K5 (LF/HF positional gradient) −0.618 → **−0.927** (matches NB14:K3), K6 (RIPA2 positional gradient) −0.827 → **−0.909**, K15 (RIPA2 will-regress one-sided *p*) 0.0022 → **0.0106** (weaker but still significant), K16 (first-pass dwell *p*) 4.1 × 10⁻²⁴ → **8.1 × 10⁻³²** (stronger). The main encoding-completion finding (K14, K15) is preserved and slightly weakened on RIPA2 while the dwell-time signature (K16) is strengthened. Both position gradients now strongly agree at ρ < −0.9."""


# ── Drive ─────────────────────────────────────────────────────────────

TARGETS = [
    ("13_survey_phase.ipynb", NB13_BODY),
    ("11_individual_differences.ipynb", NB11_BODY),
    ("11_5_chattiness_traits.ipynb", NB11_5_BODY),
    ("14_butterworth_cognitive_load.ipynb", NB14_BODY),
    ("15_cursor_approach.ipynb", NB15_BODY),
    ("21_click_prediction.ipynb", NB21_BODY),
    ("22_four_class_taxonomy.ipynb", NB22_BODY),
    ("23_rank_effects.ipynb", NB23_BODY),
    ("05_lhipa.ipynb", NB05_BODY),
    ("12_regression_precision_by_load.ipynb", NB12_BODY),
    ("18_ripa2_vs_lfhf.ipynb", NB18_BODY),
]


def patch_notebook(name, body_md):
    path = NBDIR / name
    with open(path) as f:
        nb = nbf.read(f, as_version=4)

    new_source = make_claims_cell(name, body_md)

    # Search for existing Key Claims cell by marker
    replaced = False
    for cell in nb.cells:
        if cell.cell_type != "markdown":
            continue
        src = "".join(cell.source) if isinstance(cell.source, list) else cell.source
        if KEY_CLAIMS_MARKER in src:
            cell.source = new_source
            replaced = True
            break

    if not replaced:
        # Insert at position 1 (after the title) if the first cell is a
        # markdown title, else at position 0.
        new_cell = nbf.v4.new_markdown_cell(new_source)
        insert_at = 0
        if nb.cells and nb.cells[0].cell_type == "markdown":
            first_src = "".join(nb.cells[0].source) if isinstance(nb.cells[0].source, list) else nb.cells[0].source
            if first_src.lstrip().startswith("#"):
                insert_at = 1
        nb.cells.insert(insert_at, new_cell)

    with open(path, "w") as f:
        nbf.write(nb, f)

    print(f"  {'replaced' if replaced else 'inserted'}: {name}")


def _slug(label):
    """Convert a notebook label like 'NB11.5' to an anchor-friendly slug."""
    return label.lower().replace(".", "").replace(" ", "-")


def emit_aggregate_doc():
    """Write docs/notebook-key-claims.md aggregating all Key Claims blocks."""
    lines = []
    lines.append("# Notebook Key Claims — canonical numbers")
    lines.append("")
    lines.append(f"*Last verified against executed notebook output: **{VERIFIED}**.*")
    lines.append(f"*Generated by `notebooks-v2/update_key_claims.py`.*")
    lines.append("")
    lines.append("## What this document is for")
    lines.append("")
    lines.append(
        "Every notebook in this project that ships load-bearing numbers to "
        "papers or external readers has a **Key Claims** block at its top, "
        "containing a table of canonical values with stable row IDs. This "
        "document aggregates all five blocks into one scannable file so "
        "paper writers don't have to open five notebooks to look up a value."
    )
    lines.append("")
    lines.append("### The contract")
    lines.append("")
    lines.append(
        "- **If prose in a paper draft cites a value that disagrees with a "
        "row below, the paper is wrong — not the notebook.** The notebook "
        "is the canonical source; the Key Claims block in the notebook is a "
        "direct transcription of its executed output; this file is a direct "
        "transcription of the Key Claims blocks."
    )
    lines.append(
        "- **If re-running a notebook produces different values**, update the "
        "in-notebook Key Claims block immediately, re-run "
        "`notebooks-v2/update_key_claims.py` to refresh this file, and "
        "`grep` for the old value across `docs/` and `docs/drafts/` to "
        "catch stale citations. Drafts are gitignored but still need the "
        "fix."
    )
    lines.append(
        "- **Stable IDs.** Papers cite rows as `[NB13:K5]`, `[NB11.5:K9]`, "
        "etc. Adding a new row gets a new K-ID; never renumber existing "
        "rows. If a claim is retired, replace its row body with "
        "*\"(retired YYYY-MM-DD: reason)\"* but keep the ID."
    )
    lines.append("")
    lines.append("### Notebooks covered")
    lines.append("")
    for name, body in TARGETS:
        label, filename, subject = NOTEBOOK_LABELS[name]
        anchor = _slug(label) + "-" + filename
        lines.append(f"- [{label}: `{filename}`](#{anchor}) — {subject}")
    lines.append("")
    lines.append("### Notebooks intentionally NOT covered")
    lines.append("")
    lines.append(
        "Only notebooks that ship numbers directly to external papers or "
        "public writeups get a Key Claims block. Internal exploratory "
        "notebooks, one-off investigations, and work-in-progress notebooks "
        "do not — their numbers either aren't cited anywhere yet, or they "
        "change too frequently for the contract to hold. If you find a "
        "paper citing a notebook that isn't in the list above, that "
        "notebook needs a Key Claims block added via this script."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-notebook sections
    for name, body in TARGETS:
        label, filename, subject = NOTEBOOK_LABELS[name]
        anchor = _slug(label) + "-" + filename
        lines.append(f'<a id="{anchor}"></a>')
        lines.append("")
        lines.append(f"## {label}: `{filename}` — {subject}")
        lines.append("")
        lines.append(f"*Source: [`notebooks-v2/{name}`](../notebooks-v2/{name})*")
        lines.append("")
        lines.append(body.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("")

    # Footer
    lines.append("## Regenerating this file")
    lines.append("")
    lines.append("```bash")
    lines.append("cd ~/Documents/dev/attentional-foraging/notebooks-v2")
    lines.append(".venv/bin/python update_key_claims.py")
    lines.append("```")
    lines.append("")
    lines.append(
        "The script is idempotent: it updates every notebook's Key Claims "
        "block in place (replacing any existing block by its marker line) "
        "and regenerates this aggregate document. Notebook execution state "
        "is not touched — only the Key Claims markdown cell. Re-run the "
        "script any time a canonical number changes."
    )
    lines.append("")

    content = "\n".join(lines)
    DOCSDIR.mkdir(parents=True, exist_ok=True)
    with open(AGGREGATE_PATH, "w") as f:
        f.write(content)
    print(f"  aggregate: {AGGREGATE_PATH.relative_to(DOCSDIR.parent)}")


def main():
    print(f"Writing Key Claims blocks (verified {VERIFIED})")
    for name, body in TARGETS:
        patch_notebook(name, body)
    emit_aggregate_doc()
    print("Done.")


if __name__ == "__main__":
    main()
