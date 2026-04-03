# Azzopardi, Thomas & Craswell (SIGIR 2018) — Measuring SERP Utility

**Paper:** Measuring the Utility of Search Engine Result Pages: An Information Foraging Based Measure
**Authors:** Leif Azzopardi, Paul Thomas, Nick Craswell
**Venue:** SIGIR '18
**Pages:** 605–614
**DOI:** 10.1145/3209978.3210027

## Key claims

- Proposes an IFT-based evaluation measure within the C/W/L framework that models heterogeneous SERP elements (web results, ads, answer boxes) with different costs per element type
- Stopping model derived from **information foraging theory's marginal value theorem**: users continue examining results as long as the rate of gain exceeds the expected rate from reformulating (switching patches)
- Users stop when the marginal rate of gain drops below the between-patch rate — directly connecting Pirolli & Card (1999) to operational SERP evaluation
- Naturally accommodates different element costs (ad snippet costs less than a full web result) and different gain values — suitable for modern mixed SERPs
- Formal bridge between user behavior models (how people search) and evaluation metrics (how we measure search quality)

## Connection to our work

This paper formalizes the **cost structure** that produces the ski-jump. The marginal value theorem predicts exactly the behavior we observe: evaluation continues as long as the rate of gain exceeds the cost of switching patches (reformulating). At the boundary, switching cost is maximized (next page) while evaluation cost approaches zero (sharp criteria, low uncertainty) — explaining the uptick.

The C/W/L framework's per-element cost model is the formal version of our observation that different task phases have different cost profiles (survey is cheap/fast, evaluate is expensive/variable, commit has a threshold).

Not directly applicable to AdSERP (forced choice eliminates the patch-switching decision), but provides the theoretical grounding for the general task model where stay/refine/abandon is the core foraging choice.
