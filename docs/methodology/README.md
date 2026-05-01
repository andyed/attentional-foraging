# Methodology

Audit-grade specs for every method this project uses. A methodologist (Duchowski-class peer reviewer, Gwizdka-class collaborator, future Andy) should be able to land on a single file, read the rule, find the exact code that implements it, and reproduce or challenge any number that depends on it.

This is not a glossary, not a findings file, not a threats-to-validity register. It is the contract between prose, code, and the auditor.

## What lives here

- **Procedural specs.** Segmentation rules, classifiers, coordinate handling, signal-processing pipelines, AOI definitions. Anything where a parameter choice or a rule edit would change downstream numbers.
- **Metric definitions** *(once split)*. `metrics-reference.md` is the legacy single-file index; per-metric docs (e.g. `lhipa-computation.md`, `ripa2-computation.md`, `lfhf-butterworth.md`) own the audit-relevant detail and `metrics-reference.md` becomes a one-line-per-metric pointer.

## What does NOT live here

- **`methodological-threats.md`** — documented confounds with no procedural workaround. Methodology can't change them, so they're not methodology choices.
- **`serp-structure-survey.md`, `audit-external-resources.md`** — empirical corpus surveys. A method that *uses* the corpus structure (e.g. rank assignment) gets its own methodology doc and cites the survey for the empirical denominator.
- **Findings, claims, plans, drafts, lit-notes, null-findings.** Stay at their current paths.

## Required sections (the template)

Every file in this folder must contain these ten sections, in this order. Stub files are allowed; a stub has the headers and `Status: stub — to be filled`.

1. **The rule, in one line** — the canonical statement of what this method does.
2. **Why this rule** — design rationale and alternatives considered. Cite prior art if any.
3. **Where this lives in code** — table mapping prose claims to the canonical implementation file/function. Prose disagreeing with code means the prose is wrong.
4. **Parameters** — every default value, allowed range, and what each parameter controls.
5. **Sensitivity tested** — robustness checks already run, with results and the notebook/script that produced them.
6. **Sensitivity NOT tested** — open robustness questions, ordered by likelihood of changing a downstream result.
7. **What's robust regardless of tweaking** — structural facts that survive any plausible parameter choice.
8. **Limitations to disclose in papers** — honest framing for manuscripts; the "we don't claim X" sentences.
9. **Where this rule appears in published / draft work** — back-references to papers, drafts, key claims.
10. **Status** — header at the top of the file. See conventions below.

## Status header convention

Every methodology doc opens with a status line:

```
**Status:** current as of YYYY-MM-DD; canonical implementation: <path>
```

Other allowed values:

- `**Status:** stub — to be filled`
- `**Status:** superseded by [<other-doc>.md](<other-doc>.md) on YYYY-MM-DD`
- `**Status:** stale; canonical implementation has changed since YYYY-MM-DD — needs review`

The plan-doc trap (a `Status: planned, not started` header surviving a year after the work shipped) is exactly what the contract is meant to prevent. If the canonical implementation file's last-modified date is newer than the methodology doc's status date, the doc is presumptively stale.

## Stable identifiers

Every methodology doc owns a stable ID of the form `M:<slug>`, declared in the front matter of the file. Examples: `M:forward-regressive-split`, `M:saccade-classification`, `M:lhipa-computation`. These IDs are the same shape as Key Claims (`NB18:K6`) and serve the same role: papers and notebooks cite IDs, and if prose disagrees with the methodology doc the prose is wrong.

Once assigned, IDs are never renamed. A retired methodology gets `Status: superseded by M:<other>` and the superseding doc gets a fresh ID.

## Cross-reference contract

Every methodology doc lists, in section 9, the papers and notebooks that depend on it. The inverse — papers that cite an undocumented methodology — is a science-agent lint target.

Every parameter value mentioned in a paper or notebook must match the value in the methodology doc's section 4. Cross-checking that match is also a science-agent lint target.

## science-agent contract

When science-agent runs against this folder it should enforce:

1. **Section completeness.** Every non-stub file has all ten required sections, in order, with non-empty content.
2. **Status freshness.** The status-line date is at least as recent as the last-modified date of every file referenced in section 3 (where this lives in code). If implementation changed without a methodology refresh, flag for review.
3. **Stable-ID uniqueness.** No two files declare the same `M:<slug>`.
4. **Parameter consistency.** Parameter values in section 4 match every paper and notebook that cites the methodology in section 9. Mismatches are flagged with both sources for the human to reconcile.
5. **Cross-reference graph.** Build the inverse graph (paper → methodology). Any paper that cites a methodology not present here, or that uses a method-shaped procedure (cutoff, threshold, classifier) without a methodology doc, is flagged.

The contract is loose where it should be loose: section content is the human's job, not the linter's. The linter only checks the contract is honored, not whether the science is correct.
