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
    "25_serp_composition.ipynb": ("NB25", "25_serp_composition", "corpus SERP structure — absolute vs organic rank, ad types, validation cohorts"),
    "09_difficulty.ipynb": ("NB09", "09_difficulty", "SERP difficulty (Jaccard token overlap) and its effect on page coverage"),
    "06_orientation_evaluation.ipynb": ("NB06", "06_orientation_evaluation", "OSEC phase boundaries — orient, survey, evaluate, commit"),
    "04_fixation_coverage.ipynb": ("NB04", "04_fixation_coverage", "fixation coverage and viewport-scan behavior"),
    "26_ltr_graded_relevance.ipynb": ("NB26", "26_ltr_graded_relevance", "LTR with graded relevance vs binary labels — null and 2026-04-19 extension"),
    "28_viewport_bands.ipynb": ("NB28", "28_viewport_bands", "viewport-band dwell calibration — bands-alone AUC 0.799, retreat+bands 0.837, rank-dependent vt_top, 97% per-participant consistency"),
    "29_content_residualized_bands.ipynb": ("NB29", "29_content_residualized_bands", "content-residualized bands — CLEAN NULL: residualization destroys signal (−0.024 at combined, −0.103 at bands-alone)"),
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
| **K3** | **Position × median LF/HF, forward-pass fixations only (load DECREASES with deeper position)** | **ρ = −0.927, *p* < 0.0001** (N = 11 positions) |
| **K4** | Positions 1–10 only (excluding pos 0), forward-pass | **ρ = −0.903, *p* = 0.0003** |
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

NB22 defines the four classes via cursor approach (min_dist < 100 px) + **gaze regression** to that position (the gaze-fixation sequence revisiting an earlier result band, detected from `fix['y']`, not scroll events), not via the classifier threshold used in NB21. **This makes the four-class taxonomy `[LAB]`-only by construction** — the variable is `regression_labels` in code for historical neutrality, but prose should call it `gaze_regression_label`. A scroll-only proxy is named future work. Class definitions are complementary to NB21, not competing.

| ID | Class | N | % |
|---|---|---|---|
| **K1** | Clicked | **2,228** | **16.6 %** |
| **K2** | Deferred (approached + regressed to) | **1,916** | **14.3 %** |
| **K3** | Evaluated-rejected (approached + no regression) | **439** | **3.3 %** |
| **K4** | Not approached | **8,836** | **65.8 %** |

### Motor signature separation (deferred vs evaluated-rejected)

| ID | Metric | Deferred | Eval-Rejected | *p* |
|---|---|---|---|---|
| **K5** | **Post-closest-approach drift** (px)¹ | **234.5** | **90.8** | **1.76 × 10⁻³⁸** |
| **K6** | Total gaze dwell (ms) | **4,137** | **1,612** | **9.76 × 10⁻⁷⁰** |
| **K7** | Dwell in proximity (ms) | **1,212.5** | **690.0** | **1.36 × 10⁻¹⁶** |

> ¹ **K5 is `distances[-1] − distances[min_dist_idx]`** in `notebooks-v2/15_cursor_approach.ipynb:325`. It measures **how far the cursor had drifted from its closest-approach point by the time the episode ended** — *not* max excursion, *not* arc length, *not* net Euclidean distance from the AOI. **Deferred has the larger K5 value (234 vs 91 px)** because deferred users park the cursor while fixating other candidates before regressing; eval-rejected users actively move the cursor to the next target, so post-closest drift stays small. This is the *opposite* direction from the "curved-close vs straight-far" intuition in earlier `approach-retreat/docs/theory.md` framings — the corrected interpretation is "deferred = cursor parked, eyes wandering; eval-rejected = cursor moving on with the eyes." The dissociation is real and strong; only the geometric metaphor needed updating.

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
> - K5 post-closest-approach drift gap: 191 vs 96 (p 1.9 × 10⁻¹¹) → **234 vs 91 (p 1.76 × 10⁻³⁸)** — *p*-value improved by 27 orders of magnitude (driven by cohort size doubling and cleaner class separation; effect size grew modestly from Δ = 95 px to Δ = 144 px)
> - K6 gaze-dwell gap: p 3.7 × 10⁻²⁶ → **9.76 × 10⁻⁷⁰** (*p*-value improved by 44 orders of magnitude; cohort doubling + cleaner separation, not effect-size explosion)
> - K7 proximity-dwell gap: p 5.0 × 10⁻⁹ → **1.36 × 10⁻¹⁶**
> - K11 M3 LOSO AUC: 0.792 → **0.859** (+0.067, a large effect in prediction space)
>
> Direction and significance of every headline result preserved; magnitudes all strengthened. The deferred vs rejected motor-signature dissociation — the CIKM 2026 paper's central empirical claim — is now on dramatically firmer statistical ground. See `docs/drafts/coord_fix_snapshot_20260412/`."""


# ── NB23 — rank effects ──────────────────────────────────────────────
NB23_BODY = """### Unified rank effects (absolute rank, 10 equal bands, 0–10)

| ID | Measure | Spearman ρ | *p* | N positions |
|---|---|---|---|---|
| **K1** | Click **share** × **absolute rank** (ads + organic pooled, 10 equal bands) | **−0.973** | 5.1 × 10⁻⁷ | 11 |
| **K2** | Fixation count × absolute rank (all fixations pooled) | −0.442 | 0.200 (ns) | 10 |
| **K3** | Total dwell × absolute rank (all fixations pooled) | −0.515 | 0.128 (ns) | 10 |
| **K4** | Butterworth LF/HF × absolute rank (**all fixations pooled**, no forward-only filter) | **−0.618** | **0.0426** | 11 |
| **K5** | LHIPA × click position (absolute rank) | **−0.955** | < 10⁻⁵ | 11 |

### Corpus composition

| ID | Claim | Value |
|---|---|---|
| **K6** | Trials with clicks | 2,764 |
| **K7** | (trial, position) rows | 16,335 |
| **K8** | Forward fixations (% of classified) | 74 % (150,993) |
| **K9** | Regression fixations (% of classified) | 26 % (53,583) |

### Position-level summary (per-result medians/means, absolute rank)

| ID | Pos | Click% | Fix count | Dwell (s) | LF/HF | LHIPA |
|---|---|---|---|---|---|---|
| **K10** | 0 | 22.0 | 19.9 | 4.24 | 30.0 | 0.039 |
| **K11** | 1 | 26.9 | 14.2 | 3.18 | 21.2 | 0.039 |
| **K12** | 2 | 24.3 | 10.6 | 2.37 | 18.3 | 0.039 |
| **K13** | 3 | 11.9 | 10.0 | 2.21 | 16.0 | 0.039 |

### Unified rank effects (**organic rank**, ads excluded — recommended for paper figures)

K1–K4 above are indexed by absolute rank (every h3 slot, ads pooled with organic). That conflates dd_top / native_ad displacement with true rank effects: the non-monotone pos 0→1→2 in K1 (26.9% → 22.0% → 24.3%) is a dd_top artifact intercepting position-0 clicks, and the LF/HF bump at positions 5–7 in K4 is likely native_ad contamination. K18–K28 re-index the same measures by *organic rank* (ads excluded via `absolute_to_organic_rank()`) and are the canonical numbers for paper figures. Computed by `scripts/compute_nb23_organic_rank.py`.

**Cohorts.**
- *full* — all 2,776 trials.
- *clean_for_ctr* — `plain_top == 1 AND n_org ∈ {9,10,11}` = 555 trials (19.99% of corpus). Plain-top = absolute slot 0 is organic (no dd_top ad). This is the recommended figure cohort: no ad displacement, roughly textbook 10-organic SERPs.

| ID | Measure | Cohort | Spearman ρ | *p* | N ranks |
|---|---|---|---|---|---|
| **K18** | CTR by organic rank (trial-level click rate per impression) | full (N = 2,776) | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K19** | CTR by organic rank | clean_for_ctr (N = 555) | **−0.988** | 5.5 × 10⁻⁶ | 10 |
| **K20** | Click share by organic rank (click count / total clicks) | full | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K21** | Click share by organic rank | clean_for_ctr | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K22** | Fixation count × organic rank (mean per-(trial,rank)) | full | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K23** | Fixation count × organic rank | clean_for_ctr | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K24** | Total dwell × organic rank (mean s per-(trial,rank)) | full | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K25** | Total dwell × organic rank | clean_for_ctr | **−1.000** | 5.5 × 10⁻⁷ | 10 |
| **K26** | Butterworth LF/HF × organic rank (median over trials; ranks 0–9) | full | **−0.879** | **0.0016** | 10 |
| **K27** | Butterworth LF/HF × organic rank (ranks 0–10, parity with K4) | full | −0.409 | 0.214 (ns) | 11 |
| **K28** | Butterworth LF/HF × organic rank (ranks 0–9) | clean_for_ctr | −0.133 | 0.744 (ns) | 10 |

**CTR by organic rank (full corpus):**

| org_rank | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| CTR | 0.360 | 0.175 | 0.138 | 0.081 | 0.052 | 0.032 | 0.018 | 0.013 | 0.005 | 0.004 |
| Click share % | 41.25 | 20.22 | 15.72 | 9.24 | 5.79 | 3.73 | 1.99 | 1.38 | 0.41 | 0.24 |
| Fix count | 17.54 | 13.43 | 11.01 | 9.26 | 7.94 | 6.87 | 6.27 | 5.38 | 3.91 | 3.40 |
| Dwell (s) | 3.80 | 2.99 | 2.50 | 2.11 | 1.79 | 1.54 | 1.40 | 1.21 | 0.87 | 0.80 |
| LF/HF median | 22.5 | 19.6 | 18.0 | 18.0 | 16.2 | 13.7 | 14.5 | 16.1 | 14.9 | 12.9 |

> **K18/K19 vs K1.** K1 uses absolute rank, which pools ads with organic and introduces a non-monotone pos 0→1→2 dip from dd_top displacement. K18 (full corpus) and K19 (clean_for_ctr = 555 trials, plain-top ∩ 9–11 organic results) index by organic rank and restore the textbook monotonic CTR curve (0.36 → 0.17 → 0.14 → 0.08 → ...). K19 on the clean cohort is the recommended figure cohort for ETTAC/CIKM paper CTR-by-rank plots — no ad slots, roughly uniform SERP layout, direct comparison to textbook click models. K20/K21 are the click-share analogs (direct replacement for K1's semantic).
>
> **K22/K23 vs K2/K3.** Moving to organic rank strengthens the fixation-count and dwell curves from ρ ≈ −0.44/−0.52 (ns on N = 10 absolute positions) to ρ = −1.00 (p = 5.5 × 10⁻⁷). The original non-significance was a pooling artifact, not a real null: once ad slots are excluded, both time and effort decline monotonically with organic rank across the full 0–9 range. Papers citing the K2/K3 null should replace with K22/K24 (or K23/K25 on the clean cohort).
>
> **K26 vs K4 — framework-compilation finding strengthens.** K4 (absolute rank, 11 positions) gave ρ = −0.618, p = 0.0426. K26 (organic rank, ranks 0–9, full corpus) gives ρ = −0.879, p = 0.0016 — the correlation strengthens when ad slots are excluded. The LF/HF bump at positions 5–7 visible in the K10–K13-extended absolute-rank summary (LF/HF 18.7 → 18.2 → 17.1 → 16.0) is attenuated in the organic-rank curve (18.0 → 13.7 → 14.5 → 16.1 at org ranks 4–7); some bump survives at org rank 7 but is weaker. K27 (adding rank 10, one trial) inverts the sign and is noise — stick to ranks 0–9. K28 (clean cohort, ranks 0–9) is underpowered (N = 555 trials, Butterworth valid on only a subset, fewer than 90 samples past organic rank 7) and is reported for completeness, not interpretation.
>
> **Framework compilation, not declining interest.** K4 (LF/HF ρ = −0.618, all fixations pooled) and its forward-pass-only variant [NB14:K3] (ρ = −0.927) are the key results: cognitive load peaks at position 0 where the user is constructing evaluation criteria from scratch, drops steeply through positions 0–3 as criteria compile, then plateaus. K2 and K3 are non-significant at the position level (N = 10 points), but the direction is consistent: both time and effort decline. The dissociation between K2/K3 (declining time) and K4 (declining effort that drops *faster*) is the framework compilation signature.
>
> **K4 vs NB14:K3 aggregation difference.** NB23:K4 pools all fixations (forward + regression) and computes per-(trial, position) medians, yielding ρ = −0.618 (p = 0.0426, borderline). [NB14:K3] filters to forward-pass fixations only via `identify_forward_pass` and computes per-position medians over the pooled segments, yielding ρ = −0.927 (p < 0.0001). Both are valid measurements of "cognitive load vs SERP position" — they answer slightly different questions. NB14:K3 asks "during first-pass scanning, does load decline?" and the answer is an unambiguous yes. NB23:K4 asks "pooled across all fixations (including regressions), does load decline?" and the answer is yes but weaker because regressive fixations at late positions carry elevated LF/HF from re-evaluation effort. Papers citing the framework-compilation finding should prefer NB14:K3 as the cleaner first-pass claim and note NB23:K4 as the robustness check. The position-level median bump at positions 5–7 in the K10–K16 summary table below (LF/HF 18.7 → 18.2 → 17.1) is a regressive-contamination artifact and disappears in NB14:K8's forward-only medians (16.77 → 14.41 → 13.82).
>
> **K1 vs CTR-by-rank.** K1 is click *share* — the fraction of all clicks that landed at each absolute-rank band (sums to 100%). It is not the click-through-rate (CTR) by rank used in the click-modeling literature (click count / impressions at that position). CTR by organic rank is now canonical as **K18/K19** above; click share by organic rank as **K20/K21**. Papers citing CTR-by-rank should reference K18 (full corpus) or K19 (clean_for_ctr, recommended figure cohort).
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
> **Encoding insight (K14–K15).** Items that will later receive a **gaze regression** (see NB22 — this is the same `regression_labels` boolean derived from the gaze-fixation sequence, not from scroll events) show *lower* RIPA2 at first pass. This rejects the Pirolli scent-following prediction (higher arousal at scent-rich items) and supports encoding-completion: gaze regressions go to items that were *insufficiently* processed, not items that triggered high arousal. Reframing: gaze regressions are a completion mechanism, not a scent-following mechanism.
>
> **Coordinate-space audit (2026-04-12).** FPOGY page-space fix regenerated `butterworth-lfhf-by-position.json` and `ripa2-by-position.json`. Main shifts: K5 (LF/HF positional gradient) −0.618 → **−0.927** (matches NB14:K3), K6 (RIPA2 positional gradient) −0.827 → **−0.909**, K15 (RIPA2 will-regress one-sided *p*) 0.0022 → **0.0106** (weaker but still significant), K16 (first-pass dwell *p*) 4.1 × 10⁻²⁴ → **8.1 × 10⁻³²** (stronger). The main encoding-completion finding (K14, K15) is preserved and slightly weakened on RIPA2 while the dwell-time signature (K16) is strengthened. Both position gradients now strongly agree at ρ < −0.9."""


# ── NB25 — SERP composition / corpus structure ────────────────────────
NB25_BODY = """### Corpus size and preprocessing coverage

| ID | Claim | Value |
|---|---|---|
| **K1** | Total AdSERP trials | **2,776** |
| **K2** | Trials with ≥ 1 click inside a result band | **2,764** |
| **K3** | Trials with ad-boundary-data file present | 2,776 (100%) |
| **K4** | Trials with non-empty ad-boundary rects | 2,723 |
| **K5** | Unique queries | **2,776** (every trial has a unique query — forced-choice task) |
| **K6** | Unique brands | 1,320 |

### Absolute rank (all h3 slots, ads + organic pooled)

| ID | Claim | Value |
|---|---|---|
| **K7** | Modal absolute-rank count (h3 slots per trial) | **12** (31.7 %, 879 trials) |
| **K8** | Range of absolute-rank count | 1 – 17 |
| **K9** | Trials with ≥ 11 absolute slots (i.e., at least 1 ad interleaved) | **92 %** (2,553 / 2,776) |
| **K10** | Trials with exactly 10 absolute slots | 188 (6.8 %) |

### Organic rank (ads filtered via ad-boundary overlap)

| ID | Claim | Value |
|---|---|---|
| **K11** | Modal organic-rank count | **10** (26.3 %, 731 trials) |
| **K12** | Range of organic-rank count | 1 – 15 |
| **K13** | Trials with organic count ∈ {9, 10, 11} | **70.4 %** (1,938 / 2,776) |
| **K14** | Trials with exactly 10 organic results (any ads) | 731 (26.3 %) |

### Ad type distributions — `dd_top` is binary, `native_ad` is bimodal

| ID | Claim | Value |
|---|---|---|
| **K15** | Trials with 0 dd_top ads | **1,194** (43.01 %) |
| **K16** | Trials with 1 dd_top ad | **1,582** (57.0 %) |
| **K17** | Trials with ≥ 2 dd_top ads | 0 (dd_top is binary per trial) |
| **K18** | dd_top absolute-rank location (83.5 % at rank 0, 16.5 % at rank 1) | rank 0 when no native ads above; rank 1 when displaced |
| **K19** | Modal native_ad count per trial | **3** (49.6 %) |
| **K20** | Max native_ad count per trial | 7 |
| **K21** | Native ad absolute-rank distribution (bimodal) | **25.6 %** at abs ranks 0–2; **73 %** at abs ranks 6–11; modal abs rank 8 |
| **K22** | Mean total ads per trial (dd_top + native) | 3.89 |
| **K23** | Participant-level ad exposure mean range | **3.28 – 4.33** (±13 % flat across 47 pids) |
| **K24** | Block-level ad exposure | flat across blocks 1–6 (no block effect) |

### Click distribution — absolute rank is non-monotone, organic rank is textbook

| ID | Claim | Value |
|---|---|---|
| **K25** | Total clicks inside result bands | 2,875 |
| **K26** | Clicks in ad slots (dd_top + native, in-column) | **407** (14.2 %) |
| **K27** | Click distribution × **absolute** rank peaks at | **rank 2 (24.5 %)**, not rank 0 (19.0 %) — dd_top displacement |
| **K28** | Click distribution × **organic** rank peaks at | **rank 0 (41.3 %)** — textbook monotonic ski-jump |
| **K29** | Clicks unassignable to any rank (outside all bands) | 14 |

### Validation cohorts for position-based analyses

| ID | Cohort | N | % | Definition |
|---|---|---|---|---|
| **K30** | `textbook_10org` | **16** | 0.58 % | Exactly 10 organic, 0 ads of any type |
| **K31** | `canonical_10org_leq2ddtop` | 35 | 1.26 % | 10 organic + 0–2 dd_top + 0 native |
| **K32** | `no_any_ad` | 53 | 1.91 % | Zero ad rects in result column (includes irregular organic counts) |
| **K33** | **`plain_top`** | **776** | **27.95 %** | No dd_top ad at absolute rank 0 (any native_ad allowed) — **cohort used for ski-jump validation in NB23:K19** |
| **K34** | `no_ddtop` | 1,194 | 43.01 % | Zero dd_top ads (any native_ad allowed) |
| **K35** | **`clean_for_ctr`** | **555** | **19.99 %** | `plain_top` ∩ organic rank count ∈ {9, 10, 11} — **recommended cohort for ETTAC/CIKM CTR-by-rank figures** (NB23:K19) |

### Query/brand-level ad density (top automotive-parts brands)

| ID | Brand | N trials | dd_top / trial |
|---|---|---|---|
| **K36** | delphi | 40 | 0.93 |
| **K37** | gates | n/a | 0.89 |
| **K38** | monroe | n/a | 0.76 |
| **K39** | bosch | n/a | 0.64 |
| **K40** | denso | 113 | 0.58 (highest-volume brand) |

> **AdSERP is not a "10-result SERP dataset."** Only 0.58 % of trials match the textbook "10 organic + no ads" shape. The modal trial has 12 h3 slots; 37.5 % have 13 +. Any paper framing that calls AdSERP a 10-result corpus is wrong — use "47 participants, 2,776 commercial search trials, Gazepoint GP3 HD at 150 Hz" and add "modal 12 h3 slots per SERP with heavy ad interleaving" if rank structure matters.
>
> **Any position-based claim must specify absolute vs organic rank.** The non-monotone click-distribution dip at absolute rank 0 → 1 → 2 (19.0 % → 19.0 % → 24.5 %) is **dd_top displacement**, not a cognitive effect. [NB23:K1] reports this as-is (ρ = −0.973 on absolute rank); [NB23:K18–K19] report the clean organic-rank versions (ρ = −1.000 on full corpus, ρ = −0.988 on `clean_for_ctr`).
>
> **Ad exposure is query/brand-intrinsic.** Participant- and block-level ad exposure is flat (±13 %, no confound). Automotive-parts commerce drives ad density: delphi, gates, monroe, bosch, denso. Any confound story at the participant or block level is a dead end; brand/category stories have traction.
>
> **`clean_for_ctr` (555 trials, 19.99 %)** is the recommended figure cohort for the ETTAC and CIKM CTR-by-rank plots. All 47 participants, all 6 blocks represented. Excludes dd_top displacement; constrains organic rank count to the 9–11 band where per-rank denominators are stable.
>
> **Supporting analyses.** NB13 saccade-amplitude Survey-phase finding is robust to the ad-heterogeneity of this corpus; the Survey phase is gist formation + top-ad attention capture, not deliberate ad-mapping. See `docs/survey-phase-vs-ads.md`. For paper-facing narrative, see `docs/serp-structure-survey.md`."""


# ── NB09 — SERP difficulty (Jaccard token overlap) ────────────────────

NB09_BODY = """### Jaccard token overlap as a difficulty proxy

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with computed Jaccard difficulty | **2,772** (of 2,776) |
| **K2** | Jaccard difficulty distribution | **mean 0.151**, median 0.150, SD 0.033, range [0.029, 0.395] |
| **K3** | Difficulty × organic-result count | Spearman **ρ = −0.040**, *p* = 0.035 (trivial) |

### Tercile comparison — the one positive effect is on page coverage

| ID | Claim | Value |
|---|---|---|
| **K4** | Tercile boundaries (Jaccard) | 0.136 / 0.162 |
| **K5** | Tercile group sizes | Easy 915, Medium 914, Hard 942 |
| **K6** | Duration (s) by tercile | Easy 23.33, Medium 22.22, Hard 22.47 (KW *p* = 0.186) |
| **K7** | Fixation count by tercile | Easy 87.41, Medium 82.82, Hard 83.21 (KW *p* = 0.130) |
| **K8** | **Page coverage (%) by tercile** | **Easy 57.0, Medium 53.6, Hard 53.6** (KW *p* = 0.010) |
| **K9** | Regressions by tercile | Easy 0.86, Medium 0.81, Hard 0.83 (KW *p* = 0.697) |
| **K10** | Click Y by tercile | Easy 848, Medium 829, Hard 797 (KW *p* = 0.132) |

### Partial correlations (controlling for n_results)

| ID | Claim | Value |
|---|---|---|
| **K11** | Difficulty → coverage | *r* = **−0.056**, *p* = 0.003 |
| **K12** | Difficulty → click Y | *r* = **−0.049**, *p* = 0.010 |
| **K13** | Difficulty → duration | *r* = −0.034, *p* = 0.072 (ns) |
| **K14** | Difficulty → fixations | *r* = −0.035, *p* = 0.068 (ns) |
| **K15** | Difficulty → regressions | *r* = −0.008, *p* = 0.686 (ns) |

### Within-participant (N=47 except regressions N=46)

| ID | Claim | Value |
|---|---|---|
| **K16** | Difficulty → duration (within-participant) | mean ρ = **−0.043**, *p* = 0.014 |
| **K17** | Difficulty → fixations | mean ρ = −0.042, *p* = 0.021 |
| **K18** | Difficulty → coverage | mean ρ = **−0.056**, *p* = 0.014 |
| **K19** | Difficulty → regressions | mean ρ = −0.006, *p* = 0.770 (ns) |

> **Jaccard is a weak predictor** — all significant effects are small (|r| < 0.06). The one substantive signal is on page coverage: easier SERPs produce more coverage (5-pp absolute difference across terciles). Duration, fixations, and regressions are effectively null. See findings §3c for why token overlap is the wrong measure for transactional queries — `docs/findings.md` points to `compute_difficulty_measures.py` for the complementary "relevance spread" measure that has stronger effects.

### Step 7: Evaluation depth and cognitive effort by SERP diversity

*Operationalization.* Depth = click organic rank, max organic rank reached (via scroll), count and fraction of organic results fixated. Cognitive effort = total fixation time (TFT = Σ fixation durations). Stratified by Jaccard tercile, partial correlation (controlling for organic result count), and within-participant rank correlation.

| ID | Claim | Value |
|---|---|---|
| **K20** | Trials with evaluation-depth metrics | **2,771** |
| **K21** | Trials with assignable click organic rank | **2,419** |
| **K22** | Corpus-mean click organic rank | **1.57** |
| **K23** | Corpus-mean max organic rank reached | 5.32 |
| **K24** | Corpus-mean fraction of organic results fixated | 0.481 |
| **K25** | Corpus-mean TFT | **18.4 s** |

#### Tercile comparison (Easy → Hard = diverse → homogeneous)

| ID | Measure | Easy | Medium | Hard | KW *p* |
|---|---|---|---|---|---|
| **K26** | Click organic rank | **1.77** | 1.52 | **1.42** | **< 0.0001** *** |
| **K27** | Max rank reached | **5.67** | 5.19 | **5.11** | **< 0.0001** *** |
| **K28** | N org results fixated | 4.89 | 4.50 | 4.43 | 0.0001 *** |
| **K29** | Frac org results fixated | 0.498 | 0.470 | 0.475 | 0.035 * |
| **K30** | **TFT (s)** | 19.1 | 17.8 | **18.4** | **0.088** (ns) |

#### Continuous partial correlations (controlling for n_organic)

| ID | Measure | *r* | *p* |
|---|---|---|---|
| **K31** | Click organic rank × difficulty | **−0.093** | < 0.0001 *** |
| **K32** | Max rank reached × difficulty | −0.080 | < 0.0001 *** |
| **K33** | N org fixated × difficulty | −0.076 | 0.0001 *** |
| **K34** | Frac org fixated × difficulty | −0.073 | 0.0001 *** |
| **K35** | **TFT × difficulty** | **−0.039** | **0.041 *** |

#### Within-participant rank correlations (N = 47)

| ID | Measure | mean ρ | *t* | *p* |
|---|---|---|---|---|
| **K36** | Click organic rank | **−0.101** | −6.01 | < 0.0001 *** |
| **K37** | Max rank reached | −0.105 | −5.82 | < 0.0001 *** |
| **K38** | N org fixated | −0.093 | −5.06 | < 0.0001 *** |
| **K39** | Frac org fixated | −0.045 | −2.27 | 0.028 * |
| **K40** | **TFT** | **−0.036** | −2.12 | **0.039 *** |

> **Homogeneous SERPs produce shallower evaluation, not deeper.** All five depth measures point the same direction and all four primary ones are highly significant within-participant (*p* < 0.001). When results look alike (high Jaccard), users satisfice earlier — click organic rank drops from 1.77 on diverse SERPs to 1.42 on homogeneous ones, max scroll rank drops from 5.67 to 5.11. This is the "first-looks-good-enough" collapse: when there are no real distinctions to discover, picking the first option is cheap.
>
> **Cognitive effort (TFT) barely moves.** Tercile KW *p* = 0.088 (ns); continuous and within-participant are marginal (*p* ≈ 0.04). Homogeneity compresses the evaluation **window**, not the processing load per result. The Evaluate step gets shorter, not harder.
>
> **Relationship to the ski-jump rank-9 uptick (§0 findings.md).** The majority of users on homogeneous SERPs collapse forward (click earlier, shown here). A minority — the cohort A trials where the user scrolled all the way to rank 9 — collapse backward and pick the last result, producing the muted rank-9 uptick. Both patterns coexist within homogeneous SERPs and represent different exits from Evaluate.
>
> **Bottom line.** Yes, AdSERP is varied enough to detect SERP-diversity effects on evaluation depth. The range is [0.029, 0.395] Jaccard (11× spread), effect sizes are small but consistent across tercile / continuous / within-participant tests, and the direction is the opposite of the naive "homogeneous → deeper" hypothesis.

### Step 8: Butterworth LF/HF cognitive load by SERP diversity

*Cross-reference to the NB14 Butterworth LF/HF per-position cache (`AdSERP/data/butterworth-lfhf-by-position.json`). Per-trial LF/HF = mean of valid LF/HF values across positions visited in that trial.*

| ID | Claim | Value |
|---|---|---|
| **K41** | Trials with valid trial-mean LF/HF | **2,416** (from 2,719 NB14 cache entries; rest have no valid position) |
| **K42** | Depth-analysis rows matched to LF/HF | 2,411 |
| **K43** | Corpus-mean trial LF/HF (mean) | 39.1 |
| **K44** | Corpus-mean trial LF/HF (median) | 25.7 |

#### LF/HF by Jaccard tercile (log-transformed; distribution is right-skewed)

| ID | Tercile | n | raw mean | median | log₁₀ mean |
|---|---|---|---|---|---|
| **K45** | Easy (diverse) | 806 | 39.65 | 25.22 | 1.397 |
| **K46** | Medium | 776 | 39.74 | 25.88 | 1.398 |
| **K47** | Hard (homogeneous) | 829 | 37.90 | 26.15 | 1.403 |

#### Null tests — cognitive load does not change with SERP diversity

| ID | Test | Statistic | *p* |
|---|---|---|---|
| **K48** | Kruskal-Wallis across terciles (raw) | *H* = 0.229 | **0.8916** |
| **K49** | Kruskal-Wallis across terciles (log₁₀) | *H* = 0.229 | **0.8916** |
| **K50** | Continuous partial Spearman (log LF/HF × difficulty, controlling n_organic) | *r* = **−0.0017** | **0.9347** |
| **K51** | Within-participant rank correlation (log LF/HF × difficulty, N=46) | mean ρ = **+0.007**, *t* = +0.32 | **0.7500** |

> **The Evaluate step does not get harder on homogeneous SERPs — it gets shorter.** LF/HF cognitive load is clean null across Jaccard terciles (all four tests *p* > 0.75). TFT (K30/K35/K40) moves only marginally (*p* ≈ 0.04–0.09). The depth measures (K26–K38) move strongly and consistently in the "shallower on homogeneous" direction.
>
> **Synthesis.** When results look alike, the marginal value of evaluating one more candidate drops to zero faster. The user picks sooner. The process operating on each candidate is identical (LF/HF flat, TFT nearly flat); there are just fewer candidates processed. This is the same cost/reward collapse that produces the cohort A rank-9 uptick in §0 — the "first-looks-good-enough" and "last-looks-good-enough" endpoints of the same mechanism.
>
> **Caveat on effect magnitude.** Trial-mean LF/HF averages positions visited in that trial, which partially confounds difficulty with trial depth (hard SERPs visit fewer positions, so the mean is computed over fewer — but still stable — samples). The null survives the log transform, the nonparametric test, and the within-participant correlation, so the confound is not driving the zero signal."""


# ── NB06 — orientation + evaluation (OSEC phases) ─────────────────────

NB06_BODY = """### Orientation (page-load → first result fixation)

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with orientation data | **2,773** |
| **K2** | Orientation time (cohort-wide) | **median 194 ms**, mean 464 ms |
| **K3** | Orientation (first-viewport clickers) | median 194 ms (N=512) |
| **K4** | Orientation (scrollers) | median 194 ms (N=2,261) |
| **K5** | Pre-result fixations (header/chrome) | median 1, mean 1.7 |

### First fixated result position — most users land directly on result 0

| ID | Claim | Value |
|---|---|---|
| **K6** | Position 0 | **2,516 (90.7 %)** |
| **K7** | Position 1 | 180 (6.5 %) |
| **K8** | Positions 0–1 combined | **97.2 %** |
| **K9** | Position 2 | 46 (1.7 %) |
| **K10** | Position ≥ 3 | 31 (1.1 %) |

### Time-to-interaction (first mouse/scroll event)

| ID | Claim | Value |
|---|---|---|
| **K11** | TTI median | **835 ms** |
| **K12** | TTI mean | 2,435 ms |

### Per-result evaluation metrics (forward scanning only)

| ID | Claim | Value |
|---|---|---|
| **K13** | Evaluation observations | 16,326 |
| **K14** | Fixation count × position (Spearman on pos 0–9 means) | ρ = **−0.442** (directional, *p* = 0.20 at N = 10) |
| **K15** | Per-fixation duration × position | ρ = 0.358 (flat, *p* = 0.31) |
| **K16** | Scanning rate | **2.09 s per position** (intercept 2.16 s) |
| **K17** | Fixation count at position 0 / position 9 | 19.9 / 12.2 |

### Per-participant TTI ↔ cognitive load (N = 46 with valid LHIPA)

| ID | Claim | Value |
|---|---|---|
| **K18** | TTI × LHIPA correlation | **ρ = −0.557, *p* = 5.8 × 10⁻⁵** (longer TTI → higher load) |
| **K19** | Orientation × click depth | ρ = −0.078, *p* = 0.61 (ns) |
| **K20** | TTI × click depth | ρ = 0.203, *p* = 0.18 (ns) |

> **The orient phase is nearly a no-op.** 90.7 % of trials land the very first fixation directly on result 0, with a stereotyped 194 ms latency. The "looking for where the results are" story fails — users know. Orientation variance lives in TTI (pre-interaction reading), not in landing-position search. TTI × LHIPA is the strongest per-participant cognitive-load anchor in the notebook."""


# ── NB26 — LTR graded vs binary (null + 2026-04-19 extension) ─────────
NB26_BODY = """### Original null-findings protocol (2026-04-15) — labeled-subset MRR, LR/Ridge, 5 text features

**Regime:** `[LAB]` four-cell labels (requires NB22 gaze-regression). 47-fold LOPO. Training-side exclusion: not-approached-below-click records dropped.

| ID | Claim | Value |
|---|---|---|
| **K1** | MRR@labeled-subset on original SERP ordering (Google baseline) | **0.4114** |
| **K2** | MRR@labeled-subset on LR binary ranker | **0.6108** |
| **K3** | MRR@labeled-subset on Ridge graded ranker | **0.6152** |
| **K4** | Paired Δ(graded − binary) on labeled subset, 47-participant Wilcoxon one-sided | Δ = **+0.0046 ± 0.0209**, 31/47, *W* = 720.5, ***p* = 0.0246** |
| **K5** | Paired Δ(graded − original) on labeled subset, 47-participant Wilcoxon one-sided | Δ = **+0.2065**, *W* = 1128, ***p* ≈ 1 × 10⁻⁹** |

The labeled-subset framing is known to compress the MRR competition — the training-side exclusion drops rarely-clicked positions 4–9 where Google trivially wins, artificially narrowing the ranker-vs-Google gap. See `docs/null-findings/nb26-ltr-graded-vs-binary.md` for the full-SERP reanalysis that revealed the original headline was labeled-subset-artefact-inflated.

### 2026-04-19 extension — full-SERP MRR, LambdaMART, M4 cursor features

**Regime:** `[LAB]`. 47-fold LOPO. Training uses the not-approached-below-click exclusion; held-out **inference scores all 10 positions per trial** (stricter than the null-doc "scorable-subset" protocol). LGBM rungs are averaged across seeds 0/1/2 for stability. 1,826 held-out trials (trials with missing embeddings at any position are dropped — stricter than the null-doc protocol).

| ID | Claim | Value |
|---|---|---|
| **K6** | Full-SERP MRR on original SERP ordering (Google baseline) | **0.4125** |
| **K7** | Full-SERP MRR, Rung 0: LR binary on 5 text features | **0.2878** |
| **K8** | Full-SERP MRR, Rung 0: Ridge graded on 5 text features | **0.2922** |
| **K9** | Full-SERP MRR, Rung 1: LambdaMART binary on 5 text features | **0.2893** |
| **K10** | Full-SERP MRR, Rung 1: LambdaMART graded on 5 text features | **0.2821** |
| **K11** | Full-SERP MRR, Rung 2: LambdaMART binary on 5 text + 9 M4 features (leakage) | **0.3723** |
| **K12** | Full-SERP MRR, Rung 2: LambdaMART graded on 5 text + 9 M4 features (leakage) | **0.4326** |

Paired per-participant Wilcoxon signed-rank (one-sided, 47 participants):

| ID | Claim | Value |
|---|---|---|
| **K13** | Rung 1: graded − binary paired Δ (LambdaMART on text) | Δ = **−0.0042 ± 0.0450**, 22/47, *p* = **0.7891** (ns) |
| **K14** | Rung 2: graded − binary paired Δ (LambdaMART on text + M4) | Δ = **+0.0591 ± 0.0826**, **39/47**, ***p* < 0.0001** |
| **K15** | Ranker-family isolated: Rung 1 graded − Rung 0 Ridge graded | Δ = **−0.0041 ± 0.0537**, 23/47, *p* = **0.6645** (ns) |
| **K16** | Feature-add isolated: Rung 2 graded − Rung 1 graded | Δ = **+0.1343 ± 0.1458**, 39/47, ***p* < 0.0001** |

**Notable negatives** (defensibly bound the story):

- R2 LGBM graded − Original (Google): Δ = +0.0079 ± 0.1354, 21/47, *p* = 0.4687 (ns). Even with M4 leakage, Rung 2 graded does not significantly beat Google on paired per-participant MRR. The leakage is not enough to produce a deployable-ranker claim.
- R2 LGBM binary − Original: Δ = −0.0512, 17/47, *p* = 0.9962 (ns). Rung 2 binary loses to Google.
- R0 Ridge graded − R0 LR binary: Δ = +0.0039, 29/47, *p* = 0.0719 (full-SERP analogue of K4; marginal under stricter eval).

**M4 leakage caveat — reportable caveat on K11, K12, K14, K16.** The 9 M4 cursor features are aggregates over the full cursor trajectory on each result. For clicked results the trajectory includes the movement *to* the click target, so clicked records carry click-indicative feature values: `min_dist` ≈ 73 px median vs 235 px for not-clicked; `dwell_in_proximity_ms` ≈ 1760 ms vs 194 ms. This means the Rung-2 comparisons probe a regime where the features partially encode the click.

The K14 graded-vs-binary Δ holds *feature distribution and LOPO splits constant* across the contrast; what it does **not** hold constant is loss geometry — LambdaMART with `label_gain=[0,1]` optimizes a different pairwise ranking loss than with `label_gain=[0,1,2]`, and the graded loss can exploit the leaky features more aggressively to separate clicked (gain 2) from deferred (gain 1). The defensible reading of K14 is therefore: **isolates label encoding plus any loss-structure interaction with the leaky features**, not label encoding alone. A pre-click-truncated M4 variant (not yet built) is what would attribute the +0.0591 cleanly to the graded labels. The K11/K12 absolute MRRs are not deployable-ranker values and should not be cited as such.

**What the extension shows about the null:**

- **Ranker family alone does not break the null (K15).** LambdaMART with 5 text features does not meaningfully outperform Ridge on the same features (paired Δ = −0.0041, ns). Minor caveat: K15 compares seed-averaged LGBM to deterministic Ridge, which biases the comparison *toward* finding no effect — the null is conservatively established.
- **Feature addition yields a paired graded-vs-binary lift at Rung 2 (K14, K16) — with the loss-geometry + leakage caveat above.** +0.0591 (p < 0.0001, 39/47) for graded-vs-binary at Rung 2; +0.1343 (p < 0.0001, 39/47) for feature-add isolated.
- **No leakage-driven "beat Google" headline.** R2 graded − Original is not significant (+0.0079, p = 0.47). Note this bounds *deployability*, not the contribution of leakage to the K14 contrast — those are separate claims.

**WILD gate — deferred.** ACD has one AOI per session and no SERP HTML, so a graded-label LTR replication is blocked. A binary ad-click LTR on ACD would only probe ranker-family effects, but K15 already indicates no lift on LAB text features — no pending WILD signal today. Revisit once a validated cursor-only deferred proxy exists (blocked per `attentional-foraging/CLAUDE.md`)."""


# ── NB04 — fixation coverage and viewport scanning ────────────────────

NB04_BODY = """### Coverage of the clicked region

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials processed | **2,761 / 2,776** |
| **K2** | First-viewport clickers | **502 (18.2 %)** — click without scrolling |
| **K3** | Scrollers | 2,259 (81.8 %) |
| **K4** | Mean share of results-above-click fixated | **94.7 %** (median 100 %) |
| **K5** | Trials with 100 % above-click fixation | **82.0 %** (2,263) |
| **K6** | Mean share of max-scroll-depth results fixated | 82.8 % (median 85.7 %) |

### First-viewport scanning completeness

| ID | Claim | Value |
|---|---|---|
| **K7** | FV clickers — share of first-screen results fixated | **68.3 %** |
| **K8** | Scrollers — share of first-screen results fixated | **91.7 %** |
| **K9** | Time-to-click — FV clickers | **11.4 s** (median) |
| **K10** | Time-to-click — scrollers | **23.8 s** — 2.1× slower |
| **K11** | First-move TTI — both cohorts | 1.7 s |
| **K12** | First-scroll TTI — scrollers only | 5.9 s |

### Fixation budget by position (share of total fixation time)

| ID | Claim | Value |
|---|---|---|
| **K13** | FV clickers — position 0 budget | **42 %** |
| **K14** | FV clickers — position 1 budget | 32 % |
| **K15** | Scrollers — position 0 budget | **21 %** |
| **K16** | Scrollers — position 1 budget | 15 % |

### User-level calibration: TTI predicts per-trial investment

| ID | Claim | Value |
|---|---|---|
| **K17** | TTI(move) → fix/result (N=47) | *r* = **0.460**, *p* = 0.001 |
| **K18** | TTI(move) → viewport time per result | *r* = 0.358, *p* = 0.014 |
| **K19** | TTI(move) → time-to-click | *r* = 0.417, *p* = 0.004 |
| **K20** | TTI(scroll) → fix/result (N=46) | *r* = **0.771**, *p* < 0.0001 |
| **K21** | TTI(scroll) → viewport time | *r* = 0.735, *p* < 0.0001 |
| **K22** | Calibration — first-5 TTI → remaining trials fix/result | *r* = 0.422, *p* = 0.003 |

### Per-position TTI predictiveness

| ID | Claim | Value |
|---|---|---|
| **K23** | TTI predicts fixation time significantly for positions | **0–7** (fades at 8–9 due to ski-jump variance) |

### Corpus-wide fixation duration (single-fixation FPOGD distribution)

*Computed across all single fixations from `get_trial_ids()` × `load_fixations()` post 2026-04-12 coordinate-space audit. The ".tex Mean fixation duration 219 ms, median 193 ms" stat in `task-model-paper.tex` is sourced here.*

| ID | Claim | Value |
|---|---|---|
| **K24** | Total single-fixation events | **234,339** |
| **K25** | Mean single-fixation duration | **218.1 ms** (post-audit; pre-audit value was 219 ms — within rounding) |
| **K26** | Median single-fixation duration | **187.0 ms** (post-audit; pre-audit value was 193 ms — drifted ~3% downward after coord fix) |
| **K27** | Single-fixation duration SD / IQR | SD = 130.6 ms; IQR = [133, 268] ms |

> **First-viewport clickers are not satisficers — they're faster deciders.** They fixate 68 % of the first screen (vs scrollers' 92 %) but reach a click in 11 s vs 23 s. Fixation budget on result 0 doubles (42 % vs 21 %). TTI is a stable per-user trait: a participant's first-5-trial TTI predicts the fix/result investment on their remaining trials (r = 0.42). The TTI(scroll) → investment correlation (r = 0.77) is among the strongest user-level signals in the corpus.
>
> **K24–K27 are the canonical fixation-duration source for paper drafts.** Cite as `[NB04:K25]` for mean, `[NB04:K26]` for median. The `task-model-paper.tex` line 150 figures should be updated to the post-audit values on the next .tex regeneration."""


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
    ("25_serp_composition.ipynb", NB25_BODY),
    ("09_difficulty.ipynb", NB09_BODY),
    ("06_orientation_evaluation.ipynb", NB06_BODY),
    ("04_fixation_coverage.ipynb", NB04_BODY),
    ("26_ltr_graded_relevance.ipynb", NB26_BODY),
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
