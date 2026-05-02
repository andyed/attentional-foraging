"""Aggregate Key Claims blocks from notebooks into ``docs/notebook-key-claims.md``.

The notebook is the source of truth. This script reads each target notebook's
``## Key Claims (authoritative for paper writers)`` cell and concatenates the
bodies into a single aggregate document for paper writers.

History: Until 2026-05-01 this script also held hardcoded ``body_md`` strings
for each notebook and *wrote* them into the notebooks' Key Claims cells. The
2026-05-01 AOI cascade migrated K-claims to bbox attribution, those edits
landed directly in the notebooks (commits 16830c62, 352084f7, 452554ca,
b5fb9f48, 433cfc82), and the hardcoded templates went stale. Rather than
re-sync two copies on every cascade, the script was inverted: notebooks are
canonical, this script reads from them. The pre-cascade templates live in git
history if you ever need to rebuild from scratch.

Usage:
    python notebooks-v2/update_key_claims.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

NBDIR = Path(__file__).resolve().parent
DOCSDIR = NBDIR.parent / "docs"
AGGREGATE_PATH = DOCSDIR / "notebook-key-claims.md"

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
    "30_scroll_trajectory.ipynb": ("NB30", "30_scroll_trajectory", "scroll trajectory adds AUC on top of continuous viewport analytics"),
}

TARGETS = list(NOTEBOOK_LABELS.keys())


def read_notebook_claims(name: str) -> tuple[str, str | None]:
    """Return (body_md, verified_line) extracted from a notebook's Key Claims cell.

    body_md is everything from the first ``### `` (or ``> `` / ``| ``) line
    onward, with leading and trailing whitespace stripped. verified_line is the
    raw ``*Last verified...*`` markdown line if found in the preamble, else None.

    Raises if no Key Claims cell exists.
    """
    path = NBDIR / name
    with open(path) as f:
        nb = nbf.read(f, as_version=4)

    for cell in nb.cells:
        if cell.cell_type != "markdown":
            continue
        src = "".join(cell.source) if isinstance(cell.source, list) else cell.source
        if KEY_CLAIMS_MARKER not in src:
            continue

        lines = src.split("\n")
        body_start = None
        for i, line in enumerate(lines):
            if i == 0:
                continue
            stripped = line.lstrip()
            if stripped.startswith("### ") or stripped.startswith("> ") or stripped.startswith("| "):
                body_start = i
                break
        if body_start is None:
            raise RuntimeError(
                f"{name}: Key Claims cell found but no body could be located "
                "(no '### ' / '| ' / '> ' line after the marker)."
            )

        verified_line = next(
            (l for l in lines[:body_start] if l.startswith("*Last verified")),
            None,
        )
        body = "\n".join(lines[body_start:]).strip()
        return body, verified_line

    raise RuntimeError(f"{name}: no Key Claims cell (missing marker {KEY_CLAIMS_MARKER!r}).")


def _slug(label: str) -> str:
    """Convert a notebook label like 'NB11.5' to an anchor-friendly slug."""
    return label.lower().replace(".", "").replace(" ", "-")


def emit_aggregate_doc() -> None:
    """Write docs/notebook-key-claims.md by reading each notebook's K-claims cell."""
    bodies: list[tuple[str, str, str | None]] = []
    for name in TARGETS:
        body, verified = read_notebook_claims(name)
        bodies.append((name, body, verified))

    lines: list[str] = []
    lines.append("# Notebook Key Claims — canonical numbers")
    lines.append("")
    lines.append("*Generated by `notebooks-v2/update_key_claims.py` from each notebook's "
                 "in-cell Key Claims block. Per-notebook verification dates appear inline.*")
    lines.append("")
    lines.append("## What this document is for")
    lines.append("")
    lines.append(
        "Every notebook in this project that ships load-bearing numbers to "
        "papers or external readers has a **Key Claims** block at its top, "
        "containing a table of canonical values with stable row IDs. This "
        "document aggregates all blocks into one scannable file so paper "
        "writers don't have to open each notebook to look up a value."
    )
    lines.append("")
    lines.append("### The contract")
    lines.append("")
    lines.append(
        "- **The notebook is canonical.** This document is generated from each "
        "notebook's in-cell Key Claims block. If prose in a paper draft cites a "
        "value that disagrees with a row below, the paper is wrong, not the "
        "notebook."
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
    for name in TARGETS:
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
        "notebook needs a Key Claims block added (insert a markdown cell "
        f"starting with `{KEY_CLAIMS_MARKER}` near the top of the notebook, "
        "then add the notebook to `NOTEBOOK_LABELS` in this script)."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    for name, body, verified in bodies:
        label, filename, subject = NOTEBOOK_LABELS[name]
        anchor = _slug(label) + "-" + filename
        lines.append(f'<a id="{anchor}"></a>')
        lines.append("")
        lines.append(f"## {label}: `{filename}` — {subject}")
        lines.append("")
        lines.append(f"*Source: [`notebooks-v2/{name}`](../notebooks-v2/{name})*")
        if verified:
            lines.append(verified)
        lines.append("")
        lines.append(body.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Regenerating this file")
    lines.append("")
    lines.append("```bash")
    lines.append("cd ~/Documents/dev/attentional-foraging")
    lines.append(".venv/bin/python notebooks-v2/update_key_claims.py")
    lines.append("```")
    lines.append("")
    lines.append(
        "The script reads each notebook's Key Claims cell directly and "
        "regenerates this aggregate. It does not mutate notebooks. If a "
        "notebook lacks a Key Claims cell, the script aborts with a clear "
        "error so the gap is fixed at source."
    )
    lines.append("")

    content = "\n".join(lines)
    DOCSDIR.mkdir(parents=True, exist_ok=True)
    with open(AGGREGATE_PATH, "w") as f:
        f.write(content)
    rel = AGGREGATE_PATH.relative_to(DOCSDIR.parent)
    print(f"Wrote {rel} ({len(bodies)} notebooks, {len(content):,} chars)")


def main() -> None:
    emit_aggregate_doc()


if __name__ == "__main__":
    main()
