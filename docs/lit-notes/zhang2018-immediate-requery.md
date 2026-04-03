# Zhang, Abualsaud & Smucker (CHIIR 2018) — Immediate Requery Behavior

**Paper:** A Study of Immediate Requery Behavior in Search
**Authors:** Haotian Zhang, Mustafa Abualsaud, Mark D. Smucker
**Venue:** CHIIR '18, New Brunswick, NJ, March 11–15, 2018
**Pages:** 181–190
**DOI:** 10.1145/3176349.3176400

## Key claims

- As search result quality decreases, the probability of immediate requery (reformulating without clicking) increases
- Users form an **initial impression** of the SERP and often abandon without detailed snippet inspection — a rapid assessment of the top results that gates the stay-or-requery decision
- Two user types: one group reformulates frequently (and actually finds answers fastest); the other rarely reformulates unless nothing relevant is findable
- The requery decision is explained by the user's examination pattern not reaching a relevant result — users scan a limited window (top 2–3 results) and decide based on that sample
- Study manipulated placement of the only relevant document to systematically vary quality and measure requery rates

## Connection to our work

This is **prior work for the Survey phase** in the Orient–Survey–Evaluate–Commit model (observation dates to ~2011 per the authors). The survey serves a dual purpose in naturalistic search:

1. **Assessing result set composition** — what we measure in AdSERP via saccade amplitude (wide jumps across top 2–5 results during the first ~1s)
2. **Deciding whether to stay on the SERP at all** — what AdSERP's forced-choice task eliminates

Zhang et al. observed the survey in the context of the stay/reformulate decision. We observe it in the context of the difficulty impression that modulates evaluation depth. Same phase, different exit paths available.

The distinction matters: our finding that survey duration is fixed (~3.5 saccades, ~1s, no content modulation) may only hold in forced-choice contexts. In naturalistic search where requery is an option, the survey may terminate earlier on low-quality SERPs.

## What Zheng et al. (WSDM 2020) missed

Zheng et al. observed excess attention to the top 1–2 results (especially a first-result viewport time spike) but attributed it to position-dependent examination probability — a monotonically decreasing function. They did not posit a qualitatively different cognitive phase for top results. The behavioral signal Zhang et al. identified as "result inspection" was explained away as position bias in Zheng et al.'s mobile click models (MCM, VTCM).

This is the pattern Andy has noted from production search at scale: the no-scroll no-click reformulation rate (measurable from standard telemetry) captures the survey phase outcome but is not attributed to a cognitive evaluation step by the click modeling community.
