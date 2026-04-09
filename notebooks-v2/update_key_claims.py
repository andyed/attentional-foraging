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
VERIFIED = date(2026, 4, 8).isoformat()

KEY_CLAIMS_MARKER = "## Key Claims (authoritative for paper writers)"

# Canonical notebook labels used in cross-paper citations.
# Keep these stable — papers cite as [NB13:K5], etc.
NOTEBOOK_LABELS = {
    "13_survey_phase.ipynb": ("NB13", "13_survey_phase", "saccade amplitude phase distinction"),
    "11_individual_differences.ipynb": ("NB11", "11_individual_differences", "two-factor motor individual differences"),
    "11_5_chattiness_traits.ipynb": ("NB11.5", "11_5_chattiness_traits", "cursor chattiness as a stable individual-differences trait"),
    "14_butterworth_cognitive_load.ipynb": ("NB14", "14_butterworth_cognitive_load", "cognitive load decreases with SERP position"),
    "21_click_prediction.ipynb": ("NB21", "21_click_prediction", "LOSO click prediction and four-class taxonomy"),
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
| **K9** | Low | 9.4 | 0.826 ± 0.061 (n = 15) |
| **K10** | Mid | 14.7 | 0.817 ± 0.041 (n = 16) |
| **K11** | High | 32.2 | 0.838 ± 0.034 (n = 16) |
| **K12** | Pooled LOSO M3 AUC (replication of NB21 §4.3) | — | **0.827** (n = 47) |

| ID | Spearman | *ρ* | *p* |
|---|---|---|---|
| **K13** | Per-participant chattiness (events/s) × per-participant AUC | +0.11 | 0.48 |
| **K14** | Per-participant `path_per_sec` × AUC | +0.04 | 0.82 |
| **K15** | Per-participant `dir_changes_per_sec` × AUC | +0.14 | 0.37 |
| **K16** | Per-participant `active_fraction` × AUC | +0.12 | 0.41 |

### Exposure-bias check (records per trial × chattiness)

| ID | Pair | *ρ* | *p* |
|---|---|---|---|
| **K17** | Records per trial × `events_per_sec` | **−0.50** | **0.0004** |
| **K18** | Records per trial × `active_fraction` | −0.39 | 0.007 |
| **K19** | Records per trial × `path_per_sec` | −0.08 | 0.59 (null) |
| **K20** | Records per trial × `dir_changes_per_sec` | −0.18 | 0.23 (null) |

> **Three headline claims.** (1) Chattiness is a 10×-range, high-reliability individual-differences trait (K1–K4). (2) LOSO M3 AUC is flat across chattiness terciles; all 4 Spearmans are ns (K12–K16). (3) Chatty users fixate *fewer* positions per trial, not more (K17) — the four-class taxonomy is not inflated by parker mechanical undersampling."""


# ── NB14 — Butterworth cognitive load ───────────────────────────────
NB14_BODY = """### Cognitive load decreases with SERP position (the Butterworth key finding)

**Convention.** Butterworth LF/HF ratio (Duchowski's index): *higher* LF/HF = more load. LHIPA (Index of Pupillary Activity): *lower* LHIPA = more load. The two indices are negatively correlated by construction and both agree on direction (K7).

| ID | Claim | Value |
|---|---|---|
| **K1** | Trials with usable Butterworth LF/HF data | 2,719 |
| **K2** | Position-segment count (click position × LF/HF) | 6,874 |
| **K3** | **Position × median LF/HF (load DECREASES with deeper click)** | **ρ = −0.618, *p* = 0.0426** |
| **K4** | Positions 1–10 only (excluding pos 0) | ρ = −0.491, *p* = 0.150 (ns) |
| **K5** | Within-trial Spearman (position vs LF/HF) | N = 1,167 trials, mean ρ = −0.105, median ρ = −0.200, 56.6 % negative |
| **K6** | Clicked vs non-clicked median LF/HF | 22.86 (N = 1,145) vs 18.97 (N = 5,437); Mann–Whitney *p* ≈ 0 — clicked results carry more load than non-clicked |
| **K7** | Cross-index validation: trial-mean LF/HF × LHIPA | ρ = −0.122, *p* = 9.29 × 10⁻¹⁰, N = 2,492 (correct sign: both indices agree on load direction) |
| **K8** | Position-level medians (load by rank) | pos 0: 29.98 (N = 1,015) → pos 1: 21.20 → pos 2: 18.29 → pos 3: 16.00 → pos 4: 16.27 … (monotone decline) |

> **Not working memory accumulation.** If prose says "forward-only dwell increases with position *consistent with working memory accumulation*," the prose is wrong. K3 shows per-fixation cognitive load *decreasing* with position — extra dwell at deeper positions reflects allocation / comparison-set growth, not WM overload. Framework compilation, not working-memory accumulation. This is the load-bearing claim for the ETTAC 2026 and CHI 2027 framings.
>
> **Caveat on K3.** The *p* = 0.043 at the position level is borderline at α = 0.05; the 1–10 subset (K4) is non-significant. The robust claim is the direction: every measurement stream (between-position LF/HF, within-trial LF/HF, median-by-position table, cross-index LHIPA) points the same way — load declines with position."""


NB21_BODY = """### LOSO click prediction — pooled results

| ID | Claim | Value |
|---|---|---|
| **K1** | Records / participants / click rate | 15,397 episodes / 47 participants / 12.9 % click rate (1,981 clicks) |
| **K2** | Records per participant | median 320, range 76–562 |
| **K3** | **M3 (position + dwell + approach) pooled LOSO AUC** | **0.827 ± 0.047** (47-fold) |
| **K4** | M4 (approach features only) LOSO AUC | 0.821 ± 0.048 |
| **K5** | M2 (position + dwell) LOSO AUC | 0.746 ± 0.069 |
| **K6** | M1 (position only) LOSO AUC | 0.592 ± 0.083 |
| **K7** | LOSO M3 AP | 0.517 ± 0.111 |
| **K8** | Leakage Δ (Random KFold − LOSO) for M2/M3/M4 | −0.002 / −0.003 / −0.001 (negligible) |
| **K9** | **Per-participant LOSO M3 AUC** | **median 0.833, IQR [0.795, 0.857], range [0.698, 0.929]**, all 47 participants above chance |
| **K10** | Youden's J threshold (M3 OOF) | *p* = 0.466 (TPR = 0.751, FPR = 0.224) |
| **K11** | F1-optimal threshold | *p* = 0.614, F1 = 0.507 |
| **K12** | Brier score (M3 OOF) | 0.1615 |

### Four-class taxonomy (classifier-derived, tautology fix)

| ID | Class | N | % | Mean *p*(click) |
|---|---|---|---|---|
| **K13** | Clicked | 1,981 | 12.9 % | 0.656 |
| **K14** | Deferred candidate | 1,286 | 8.4 % | 0.704 |
| **K15** | Evaluated-rejected | 994 | 6.5 % | 0.307 |
| **K16** | No signal | 11,136 | 72.3 % | 0.305 |

### M3 standardized feature coefficients (full-data refit)

| ID | Feature | Coefficient | Direction |
|---|---|---|---|
| **K17** | `mean_dist` | +1.03 | → click |
| **K18** | `final_dist` | −0.80 | → skip |
| **K19** | `dwell_in_proximity` | +0.73 | → click |
| **K20** | `min_dist` | −0.73 | → skip |
| **K21** | `max_approach_velocity` | +0.30 | → click |
| **K22** | `position` | +0.21 | → click |
| **K23** | `direction_changes` | +0.20 | → click |
| **K24** | `retreat_dist` | −0.16 | → skip |
| **K25** | `total_dwell` | +0.15 | → click |
| **K26** | `mean_approach_velocity` | −0.11 | → skip |
| **K27** | `frac_decreasing` | +0.09 | → click |

> **Robustness to individual cursor activity lives in NB11.5.** The chattiness-stratified AUC figure (§4.3 robustness paragraph of `docs/drafts/cikm-2026/paper.md`) uses [NB11_5:K9–K16], not NB21 directly.
>
> **Previously fixed bug (2026-04-08):** Cell 20 used `y_p_full` before definition (lines 14–15 were dead code from a pre-rewrite version). Symptom: `NameError: name 'y_p_full' is not defined`. Fix: delete the old block."""


# ── Drive ─────────────────────────────────────────────────────────────

TARGETS = [
    ("13_survey_phase.ipynb", NB13_BODY),
    ("11_individual_differences.ipynb", NB11_BODY),
    ("11_5_chattiness_traits.ipynb", NB11_5_BODY),
    ("14_butterworth_cognitive_load.ipynb", NB14_BODY),
    ("21_click_prediction.ipynb", NB21_BODY),
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
