# Lorigo et al. (JASIST 2008) — Eye Tracking and Online Search: Lessons Learned and Challenges Ahead

**Paper:** Eye tracking and online search: Lessons learned and challenges ahead
**Authors:** Lori Lorigo, Maya Haridasan, Hrönn Brynjarsdóttir, Ling Xia, Thorsten Joachims, Geri Gay, Laura Granka, Fabio Pellacini, Bing Pan
**Venue:** Journal of the American Society for Information Science and Technology (JASIST) **59(7): 1041–1052**, May 2008
**DOI:** 10.1002/asi.20794
**Paywall:** Wiley Online Library — https://onlinelibrary.wiley.com/doi/10.1002/asi.20794
**Open access alternatives tried:** ResearchGate (403), Cornell CS server (403/404), Semantic Scholar (no PDF). When reading, pull from institutional Wiley access or request from Joachims/Pan directly.

> **Status of this note:** Synthesis-level summary based on Andy's existing references in `lit-review-scroll-regressions.md` and `adserp-key-claims.md`, plus the published abstract and the well-attested Cornell-group result trail. **Specific within-paper numerics ([VERIFY] markers below) need confirmation against the PDF on reread.** Do not cite specific numbers from this note without checking the source.

## Why this paper matters for our portfolio

The **single most-cited empirical baseline** for non-linear scanpath prevalence on SERPs (≈ 65–66% non-linear; Andy uses this as the comparison anchor for AdSERP's 69% scroll-regression prevalence — see `adserp-key-claims.md` line 127 and `lit-review-scroll-regressions.md` §4). It is also one of the foundational papers in the F-pattern / golden-triangle citation chain — alongside Granka, Joachims & Gay SIGIR 2004 and Nielsen 2006.

For the F-pattern misinformation thesis, this paper is **load-bearing in two directions**:
1. It documents that scanpaths are *not* linear top-to-bottom for the majority of users — undermining the simple "users read down the F" mental model.
2. It is cited (often without rereading) as supporting the very F-pattern interpretation it complicates. The Lorigo group's actual claim is more nuanced than how the design world repeats it.

## What's actually in the paper (high-confidence from abstract + existing references)

- **Survey paper format:** consolidates three earlier eye-tracking experiments conducted by the Cornell IR group (Joachims/Granka/Pan/Gay) between 2004–2007 plus additional review of adjacent work. Not a single new experiment.
- **The three constituent experiments** are well-attested as:
  - Granka, Joachims & Gay (SIGIR 2004) — "Eye-tracking analysis of user behavior in WWW search"
  - Joachims, Granka, Pan, Hembrooke & Gay (SIGIR 2005) — "Accurately interpreting clickthrough data as implicit feedback"
  - Pan, Hembrooke, Joachims, Lorigo, Gay & Granka (IP&M 2007) — "In Google we trust: Users' decisions on rank, position, and relevance"
- **Key topics surveyed:** scanpath linearity, click-vs-view alignment by rank, effects of gender, search task type, and search engine on examination behavior. Eye-mouse coordination is touched on but not the primary contribution.
- **The "lessons learned" framing** is methodological — the paper is partly a stock-taking of what the Cornell group had learned from running multiple eye-tracking studies on SERPs, plus open challenges.

## Headline numerics (need verification on reread)

- **[VERIFY] ~65–66% non-linear scanpaths** on SERPs — this is the figure Andy cites and the figure most subsequent IR papers attribute to Lorigo et al. 2008. Confirm exact number, definition of "non-linear," and which constituent experiment it came from.
- **[VERIFY] Per-rank fixation density and click-through skew** — the "golden triangle" / F-shape pattern is documented but the exact numbers (mean fixations per rank, click-through ratios) should be re-checked.
- **[VERIFY] N per experiment, eye tracker model, sampling rate** — Cornell group historically used ASL 504 / 5000-series eye trackers in this era; confirm.
- **[VERIFY] Sex/task/engine effect sizes** — abstract mentions all three were investigated.

## Connection to the F-pattern misinformation thesis

The paper is a critical anchor because:

1. **The non-linear-scanpath finding undermines the strong-form F-pattern claim.** If ~65–66% of scanpaths are non-linear, then "users scan in an F" is at best an aggregate-heatmap description of a population mixture, not a description of individual behavior. This is the point Nielsen's 2017 update walked toward (see `nielsen2017-f-pattern-update.md`) but is rarely propagated in the SEO/UX literature.

2. **The paper is itself cited by Allawati et al. 2026** (as their [30] in the methodology lineage — confirm reference number on reread) for general eye-tracking methodology on SERPs. The Allawati paper does not engage with the non-linearity finding.

3. **The "golden triangle" framing** appears to originate in this Cornell group's work and predates Nielsen's 2006 F-pattern characterization. Worth tracing the priority claim — Lorigo et al. may have published the underlying phenomenon before Nielsen popularized the "F" label. Verify on reread.

## Relationship to AdSERP regression work

The 69% scroll-regression prevalence in AdSERP (`adserp-key-claims.md` line 127) is conceptually adjacent to Lorigo's ~66% non-linear scanpath statistic — same order of magnitude, both describing the failure of strict top-to-bottom sequential scanning. They are not the same construct:

- **Lorigo non-linear scanpaths** = at the gaze level, fixation sequences that don't monotonically descend in Y
- **AdSERP scroll regressions** = at the scroll level, scroll-up events after scroll-down, much coarser temporal scale

But both serve the same rhetorical purpose: empirical baselines establishing that "linear top-to-bottom scan" is not the dominant behavior. Cite together when grounding the "users do not scan linearly" thesis.

## Connection to the survey-phase / OSEC framing

The 2008 paper predates the explicit survey-phase operationalization in Zhang/Abualsaud/Smucker 2018 and Abualsaud/Smucker 2019. But:

- The Lorigo group's per-rank fixation-density analyses **describe** the survey + evaluation composite without ever decomposing it into phases. They report aggregate fixation counts per rank, which is exactly the layered count the survey-phase / evaluation / revisit decomposition unstacks.
- The "non-linear scanpath" finding is partly the signature of the survey-phase: rapid top-to-bottom scans with jump-backs to revisit promising results before committing to evaluation. Treating those scanpaths as "non-linear" rather than "phase-transitioning between survey and evaluation" is the framing gap the OSEC work fills.

## How to cite

For "non-linear scanpath prevalence on SERPs" — Lorigo et al. JASIST 2008 (with [VERIFY] on the specific percentage until confirmed on reread).

For "golden triangle / heatmap fixation distribution" — Lorigo et al. JASIST 2008 + Granka, Joachims & Gay SIGIR 2004 (the precursor).

For "F-pattern as aggregate description rather than individual behavior" — Lorigo et al. (non-linearity finding) + Nielsen 2017 update (conditional fallback framing).

**Do not paraphrase specific findings from this note alone.** Reread the PDF first. The synthesis here is correct in direction but the specific numerics carry [VERIFY] flags.

## Reread checklist (Andy)

When you reread, capture:
- [ ] Exact non-linear-scanpath percentage and its operational definition
- [ ] N, eye tracker model, sampling rate per constituent experiment
- [ ] Whether "golden triangle" appears in the paper text or is later attribution
- [ ] Per-rank fixation count + per-rank click-through ratio tables
- [ ] Gender / task / engine effect sizes
- [ ] What the "challenges ahead" section identifies as open problems — useful for positioning OSEC's contribution against the 2008 horizon

Update this note with the verified numbers after the reread; strip the [VERIFY] markers.
