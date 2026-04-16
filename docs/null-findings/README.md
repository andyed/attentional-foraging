# Null findings

**Principle (2026-04-15, Andy Edmonds).** This project documents null and near-null findings in the git repo even when they do not appear in papers. Published papers have page limits and rhetorical constraints that make it impractical to report every experiment that didn't work, but the analyses are still on disk and future work — including our own — benefits from a clean record of what was tried, what the numbers actually were, and why the result did not survive to publication. This directory is the canonical home for that record.

## What belongs here

- Experiments whose headline result was a null or near-null that we chose not to surface in a paper
- Experiments whose framing changed mid-analysis, where the original framing is worth preserving for honesty and reproducibility
- Ablations and diagnostic checks that returned the expected-but-unpublishable answer ("this confound is real but doesn't change the published finding")
- Any experiment where an *earlier* summary we made was later revised by a more honest metric; the earlier summary gets a writeup here showing *how* it was revised

## Format conventions

Each null finding gets its own markdown file in this directory, named `nb<##>-<short-slug>.md` or `<date>-<slug>.md` depending on whether it came from a Tier-A notebook or a one-off script. Each file includes:

1. **TL;DR header** — one paragraph. What was the hypothesis, what was the headline number, what did it not demonstrate.
2. **What was run** — link to the notebook or script, the exact CV protocol, sample sizes, feature set, label scheme.
3. **Numbers** — the full results table including the honest null alongside any near-positive results that tempted us to claim more.
4. **Why it's a null** — what changed (noise floor, denominator, sample composition) that killed the positive framing.
5. **What was learned anyway** — every null tells you something. Document the narrow claim that *does* survive.
6. **Pointers** — files touched, commits, upstream discussions (Slack, email), related notebooks.

## Relationship to other project docs

- `docs/findings.md` is where **published** findings live, tagged with `[NB##:K##]` Key Claim IDs.
- `docs/null-findings/` is where **unpublished** findings live. It's the shadow index to findings.md.
- `docs/methodological-threats.md` catalogues known confounds across all notebooks; some entries here will cross-reference it.

## Why this matters

The file-drawer problem in empirical research is the accumulated under-reporting of null results across many labs and papers. On a single-lab project like this one, the shadow cost of not documenting nulls is re-walking the same paths multiple times over the project's life and forgetting what was tried. Five minutes writing a null up cleanly today saves hours of re-derivation six months from now, and — more importantly — gives any reader of our published work a citable place to see the full empirical envelope of the project, not just the results that landed in print.

## Current entries

- [`priming-null-result.md`](priming-null-result.md) — 2026-04 — the original lexical-priming conjecture that drove early work on this project, invalidated at four granularities (forward-only gaze dwell ratio *reverses*, aggregate correlation was position confound + regression artifact, regression-trial signal is triply confounded, Y-offset bug invalidated earlier aggregate). Alternate explanation that emerged: framework compilation (cognitive load drops as evaluation criteria compile, not rises as working memory fills). **Positive reframe came out of this investigation** — the task-model framework-compilation finding is a direct descendant.
- [`2026-04-12-ski-jump-audit-collapse.md`](2026-04-12-ski-jump-audit-collapse.md) — 2026-04-12 — the "classic ski-jump" (terminal-click uptick at the last visible SERP result) that motivated the project at its start. The 2026-04-12 coordinate-space audit invalidated the full-corpus uptick (coord double-count), the satisficer / optimizer decomposition (collapsed to 1.06× ratio post-fix), and the mixed-tier apparent elevation (50 % from two participants, 53 % ad-contaminated). A narrow cohort-A small-n result (n = 131, +33 % relative uptick rank 8→9) survives in `findings.md §0`. The audit back story is documented here.
- [`2026-04-15-novelty-baseline-residual-redundancy.md`](2026-04-15-novelty-baseline-residual-redundancy.md) — 2026-04-15 — sentence-embedding lexical-novelty residuals applied to per-fixation dwell (NB25) and per-viewport dwell (NB27) are empirically indistinguishable from the raw dwell variables they're derived from. The novelty-baseline regression captures essentially none of the dwell variance, so the residual collapses to the raw variable. Methodological lesson: check baseline R² against the raw variable before building downstream pipelines on a "residual" feature.
- [`nb26-ltr-graded-vs-binary.md`](nb26-ltr-graded-vs-binary.md) — 2026-04-15 — LTR ranker comparison trained on graded vs binary click labels; on the full 10-result SERP, neither ranker beats Google's ordering, and the graded > binary contrast that was significant on the labeled subset (Wilcoxon p = 0.025) collapses to directional-only (p = 0.165) on the full SERP. Kept out of the CIKM paper.
