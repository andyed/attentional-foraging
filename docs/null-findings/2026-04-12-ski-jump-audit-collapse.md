# The ski-jump hypothesis: audit collapse (2026-04-12)

**Date:** 2026-04-12 coordinate-space audit
**Status:** Back story. The cohort-A narrow finding survives in `docs/findings.md §0`; the *full-corpus* uptick and the *satisfice / optimize decomposition* did not survive audit and are documented here.
**Scripts:** `scripts/ski_jump_satopt.py`, `scripts/ski_jump_mixed_tier.py`, `scripts/output/ski_jump_canonical.csv`, `scripts/output/ski_jump_rank10/ctr_by_rank_by_cohort.csv`
**Notebook:** [`00_skijump.ipynb`](../../notebooks-v2/00_skijump.ipynb)

## TL;DR

The "ski-jump" — the terminal-click uptick at the last visible search result — is the classic click-log artifact that industry search engines have reported for two decades. Andy came into this project expecting AdSERP to reproduce it at large scale and to decompose it along a satisficer / optimizer axis using the Butterworth LF/HF cognitive-load signal. The pre-audit headline claim was that boundary clickers were "1.56× more likely to be optimizers" and that the uptick was an optimizer-dominated phenomenon.

**The 2026-04-12 coordinate-space audit invalidated the full-corpus uptick and the satisficer / optimizer decomposition.** Root causes, in order of magnitude:

1. **Coordinate-handling bug in the cursor pipeline.** A scroll double-count on cursor Y contaminated the click-position labeling, inflating boundary clicks across the full corpus.
2. **Participant-level concentration.** On the cleaned data, the "mixed tier" apparent elevation is 50 % driven by two participants (p044 + p020).
3. **Ad contamination.** 53 % of the mixed-tier boundary clicks land on AD slots at absolute ranks 9–10, not on organic results. Stripping ads kills the apparent mixed-tier elevation.
4. **Small-n at the boundary.** Boundary clicks are 42 / 2,775 trials (1.5 %) on the full corpus, and the cohort where the real industry ski-jump lives (plain-top SERPs with ≥ 10 organic, user scrolled rank 9 into view) is n = 131. A tier-level decomposition on n = 131 with 50 % from two users is not robust to participant resampling.

## What the audit-surviving finding actually is

The cohort-A narrow result (preserved in `findings.md §0`):

- **Plain-top SERPs, ≥ 10 organic results, user scrolled rank 9 into view (n = 131):** rank 7 = 6.1 % → rank 8 = 2.3 % → **rank 9 = 3.1 %**, a **+33 % relative uptick** from rank 8 to rank 9.
- **Satisfice/optimize modulation on cohort A: null.** Post-fix opt/sat ratio = 1.06× on the full corpus, *inverted* within cohort A. The small-n boundary cluster is participant-concentrated and ad-contaminated rather than tier-driven. The pre-audit "1.56× optimizers" claim did not survive.
- **Cohort-A LHIPA at the boundary** (0.041 vs 0.049 mid-page, *p* < 0.0001): real but caveated. Boundary clickers show higher cognitive load, consistent with "finishing the job" rather than giving up. The LHIPA finding uses a pre-audit boundary-click definition and should be re-verified on cohort A directly before being used as a load-bearing claim.

In short: **a real but narrow boundary-uptick finding survives on n = 131; the full-corpus ski-jump and its satisficer / optimizer story do not.** The task-model story that grew out of the same dataset (OSEC, the F-pattern decomposition, cursor approach-retreat, the four-class taxonomy) survived the audit cleanly and is the primary contribution of the project.

## Why it's a null (what changed)

The pre-audit pipeline labeled click positions using a coordinate-space that double-counted scroll offset on the cursor Y channel. Specifically:

- `click_y_page` was computed as `cursor_y + scroll_y` in some paths and `cursor_y` (already page-space) in others, producing a spurious page-Y shift on trials where the user scrolled significantly.
- This shifted click labels downward on scrolled trials, inflating the apparent density of clicks at absolute ranks 9–10.
- When the shift was removed on 2026-04-12, the full-corpus uptick collapsed.

The M4 cursor approach features survived the audit with headline direction preserved but magnitudes *strengthened* (retreat-distance dissociation *p* went from 10⁻¹¹ → 10⁻³⁸; see `docs/findings-approach-retreat.md` header). This is the correct audit outcome for a legitimate finding: the coordinate fix tightened the real signal and killed the spurious one.

## What was learned anyway

1. **The "classic ski-jump" — terminal-click uptick at scale — is not present in AdSERP as a full-corpus effect.** The dataset is too small and too forced-choice-constrained to produce the industry-scale pattern. Any ski-jump claim on AdSERP needs the cohort-A filter and the participant-concentration caveat.
2. **Satisficer / optimizer is a continuous user trait (§5 in findings.md) but it does not decompose the ski-jump.** The positive sat/opt finding at the individual-differences level survives independently (§11 in findings.md); its attempted application to the boundary-click population was what collapsed.
3. **Coordinate-space audits change magnitudes, not directions, when the underlying finding is real.** The M4 approach-retreat audit strengthened every finding it touched (§1 of this doc's linked `findings-approach-retreat.md`). The ski-jump audit collapsed the full-corpus finding and shrank the decomposition to the cohort-A small-n. The pattern distinguishes real signal from bookkeeping artifact.
4. **The framework-compilation reframe — cognitive load drops as evaluation criteria compile, not rises as working memory fills — came out of the adjacent priming-null investigation, not this one.** See `docs/null-findings/priming-null-result.md` for that back story. Both nulls (ski-jump and priming) surfaced positive alternatives during the same audit window.

## Pointers

- Surviving finding: `docs/findings.md §0` (cohort-A narrow result, caveated LHIPA, caveated investment)
- Audit log entry: `docs/drafts/task-model-paper-resteer-log.md` entries dated 2026-04-12
- Sibling coordinate-audit: `docs/findings-approach-retreat.md` header (M4 cursor-side 2026-04-09 and fixation-side 2026-04-12 audits; those survived and strengthened)
- Pre-audit snapshot: `docs/drafts/coord_fix_snapshot_20260412/` (git state + before/after numbers)
- Related null: [`priming-null-result.md`](priming-null-result.md) — adjacent null investigation from the same audit window that surfaced the framework-compilation positive alternative
- LinkedIn write-up (pre-audit): `docs/drafts/linkedin-skijump.md` — not yet updated post-audit; author's personal narrative of the pre-audit expectation

## Status

**Removed from README as the project's orienting story (2026-04-15).** The ski-jump audit back story was prominent in the repo's README intro because it was the initial motivation. The forward story — task model, cursor approach-retreat, graded-relevance reframe, mobile-portability bounds — has now accumulated enough material that leading with the audit back story under-represents what the project is actually about. The narrow cohort-A finding stays in `findings.md §0` as a real-but-small result; the audit history lives here as the honest record of what did not survive.
