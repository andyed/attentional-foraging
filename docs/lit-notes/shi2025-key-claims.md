# Shi et al. (2025) — Key Claims Analysis

**Paper:** Li Shi, Gavindya Jayawardena, and Jacek Gwizdka. 2025. "Pupillometric Analysis of Cognitive Load in Relation to Relevance and Confirmation Bias." CHIIR '25, Melbourne, March 24–28. pp. 219–230.
**DOI:** [10.1145/3698204.3716458](https://doi.org/10.1145/3698204.3716458)

**Assessment:** This is a methods + findings paper that validates LHIPA as a cognitive load measure for information retrieval and discovers the relevance-perception mismatch effect. Strong methodology, clean design, but lab-only with a narrow domain (health search). The data is not publicly available.

**Relationship to our work:** Same senior author (Gwizdka) as AdSERP. We apply the same LHIPA algorithm to a public dataset (AdSERP) with different task characteristics (product search, forced click, naturalistic SERP). Their mismatch finding cannot be directly replicated in our data (no relevance labels, no perceived relevance ratings), but our LHIPA validation and process model findings are complementary.

---

## What they claim

### 1. LHIPA validates against NASA-TLX

> LHIPA tracks self-reported workload (H = 55.65, p < 0.0001, adj. η² = 0.097 — medium effect).

Higher LHIPA (lower cognitive load) corresponds to lower NASA-TLX scores. This establishes LHIPA as a real-time, non-intrusive cognitive load proxy for IIR tasks.

**Our replication:** LHIPA validates against four behavioral proxies on AdSERP: trial duration (ρ = -0.65), fixation count (ρ = -0.62), regression count (ρ = -0.44), click position (ρ = -0.09). All significant, all in the expected direction. We don't have NASA-TLX but the behavioral validation is consistent.

### 2. Mismatch between topical and perceived relevance drives cognitive load (the big finding)

> Cognitive load peaks when perception mismatches reality: irrelevant docs perceived as relevant (W = 3.82, p = 0.0001), and relevant docs perceived as irrelevant (W = 2.82, p = 0.005).

This is a 2×2 interaction (topical relevance × perceived relevance), not a main effect of either. The user works harder when their assessment conflicts with the content.

**Our test:** Cannot directly replicate — AdSERP lacks relevance labels and perceived relevance ratings. We tested an analogy: semantic embedding similarity to the clicked result (proxy for "expected relevance") × click/no-click (proxy for "actual relevance"). The mismatch test was null at every position, both with raw pupil and with LHIPA. Probable reasons: (a) product SERPs are too semantically homogeneous for embedding similarity to create perceptual "expectation" (cosine range ~0.77-0.83), (b) click-similarity is not the same construct as perceived relevance, (c) their relevance gradient (health information, 3 levels) has far more contrast than our SERPs.

**What this means:** The mismatch finding is likely real (clean design, significant effects) but domain-specific. It requires genuine relevance variation and a way to assess perceived relevance, neither of which AdSERP provides.

### 3. Familiarity and interest increase cognitive load (counter-intuitive)

> Moderate familiarity > unfamiliar (z = 2.66, p = 0.008). Curiosity has a large effect (U = 39004, p < 0.0001, r = 0.69).

Curious users and moderately familiar users invest *more* cognitive effort. This contradicts the naive prediction that familiarity reduces load. The resolution: familiarity gives you the tools to engage deeply, curiosity gives you the motivation. Complete novices don't engage because they can't.

**Connection to our data:** Per-result wavelet LHIPA appeared to decline during forward scanning, but Duchowski (2026) established that wavelet decomposition requires 7.5–10s minimum — our per-result segments (~2s) were below this threshold, making per-result LHIPA unreliable. Using Duchowski's recommended Butterworth IIR method (1s minimum window), we find cognitive load *decreases* with position (LF/HF ρ = −0.927, §3b-iv of findings.md). This is the opposite of the working memory accumulation prediction. The resolution: within-session "familiarity" compiles evaluation criteria rather than building load — the user gets more efficient, not more burdened. This contrasts with Shi et al.'s between-task familiarity finding (deeper engagement), because within-SERP familiarity serves discrimination, not comprehension.

### 4. Confirmation bias reduces cognitive load

> High confirmation bias → lower cognitive load (U = 32802, p = 0.0025, r = 0.43 — large effect).

Biased users take shortcuts — System 1 processing. They invest effort only when confirming information.

**Connection to our data:** Our satisfice/optimize segmentation (from `user_strategies.ipynb`) captures a related dimension. Low-regression users (satisficers) may be taking similar shortcuts — accepting early results without deep comparison. High-regression users (optimizers) invest more effort. We could test: do satisficers have higher trial-level LHIPA (less load) than optimizers?

### 5. No interaction between confirmation bias and relevance evaluations

Bias doesn't change *what* users judge as relevant, only *how much effort* they invest. Prior beliefs about specific topics may matter more than dispositional bias.

---

## What they didn't test (gaps our work addresses)

| Gap | Our contribution |
|-----|-----------------|
| No temporal process model | We decompose search into orientation → survey → evaluation → regression → commitment phases, each with distinct behavioral and pupillometric signatures |
| Trial-level LHIPA only | We extend LHIPA to per-result segments during naturalistic SERP browsing (78% computable at ≥64 samples) |
| 300 Hz Tobii only | We demonstrate LHIPA at 150 Hz on Gazepoint GP3 HD — lower cost, broader accessibility |
| Lab documents, not SERPs | We apply LHIPA to SERP browsing with scroll, regression, and click behavior |
| Data not public | Our implementation and analysis are on a public dataset (AdSERP on Zenodo) |
| No regression/scroll analysis | LHIPA × scroll regressions, foraging depth, and the click commitment cost |

## What we can't do that they did

| Their advantage | Why we can't replicate |
|---|---|
| Topical relevance labels (CLEF assessors) | AdSERP has no external relevance judgments |
| Perceived relevance self-reports | No post-task questionnaires in AdSERP |
| NASA-TLX validation | No subjective workload measure |
| Familiarity, curiosity, confirmation bias scales | No individual difference measures beyond behavioral |
| Controlled relevance manipulation (3 levels × 6 docs) | Naturalistic SERPs with no experimental control over content |

---

## Design differences that matter

| Dimension | Shi et al. | Our analysis |
|---|---|---|
| Eye tracker | Tobii TX-300 (300 Hz) | Gazepoint GP3 HD (150 Hz) |
| N | 32 | 47 (AdSERP participants) |
| Task | Health document relevance assessment | Product purchase search (forced click) |
| Stimuli | Pre-selected documents, controlled relevance | Google SERPs, uncontrolled content |
| LHIPA granularity | Per-trial (offline) | Per-trial + per-result segment |
| Relevance ground truth | CLEF assessor labels | None (click position only) |
| Data availability | Not public | Public (Zenodo) |

---

## Key references to follow from their bibliography

- **Duchowski et al. (2020)** — LHIPA algorithm. CHI '20. [doi:10.1145/3313831.3376394](https://doi.org/10.1145/3313831.3376394)
- **Jayawardena et al. (2022)** — RIPA: Real-time IPA. Addresses windowed/real-time LHIPA computation. [doi:10.1016/j.procs.2022.09.115](https://doi.org/10.1016/j.procs.2022.09.115)
- **Gwizdka (2014)** — Characterizing relevance with eye-tracking measures. Earlier work connecting eye behavior to relevance assessment.
- **Gwizdka (2010)** — "Distribution of Cognitive Load in Web Search" (JASIST). Found load peaks during query formulation and document evaluation, not during SERP scanning.

---

*Created 2026-04-02. Based on published paper + our LHIPA replication attempt on AdSERP.*
