# Zhang, Abualsaud & Smucker (CHIIR 2018) — Immediate Requery Behavior

**Paper:** A Study of Immediate Requery Behavior in Search
**Authors:** Haotian Zhang, Mustafa Abualsaud, Mark D. Smucker
**Venue:** CHIIR '18, New Brunswick, NJ, March 11–15, 2018
**DOI:** 10.1145/3176349.3176386

## Key claims

- Documents a **result inspection phase**: users evaluate top 2–3 results to decide whether the SERP is worth continued evaluation or immediate requery
- This observation dates to ~2011 per the authors
- The inspection phase is a rapid assessment — "is this SERP worth my time?" — before committing to deeper evaluation

## Connection to our work

This is prior work for what we call the **Survey phase** in the Orient–Survey–Evaluate–Commit model. The survey serves a dual purpose in naturalistic search:
1. Assessing result set composition (what we measure in AdSERP)
2. Deciding whether to stay on the SERP at all (what AdSERP's forced-choice task eliminates)

Zhang et al. observed the survey in the context of the stay/reformulate decision. We observe it in the context of the difficulty impression that modulates evaluation depth. Same phase, different exit paths available.

## What Zheng et al. (WSDM 2020) missed

_Per Andy's note:_ Zheng et al. observed additional attention to the top 2–3 results behaviorally but did not attribute it to a "is this SERP worth my time" evaluation phase. The behavioral signal was documented but the cognitive interpretation was missed.

_TODO: verify Zheng et al. 2020 citation details and specific claim._
