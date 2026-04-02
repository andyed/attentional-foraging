# Shi, Jayawardena & Gwizdka (2025) — Pupillometric Analysis of Cognitive Load in Relation to Relevance and Confirmation Bias

**Citation:** Li Shi, Gavindya Jayawardena, and Jacek Gwizdka. 2025. Pupillometric Analysis of Cognitive Load in Relation to Relevance and Confirmation Bias. CHIIR '25, Melbourne, March 24–28. pp. 219–230.
**DOI:** https://doi.org/10.1145/3698204.3716458

## TL;DR

Pupil dilation (measured via LHIPA) reveals that cognitive load during relevance assessment is highest when there's a **mismatch** between a document's topical relevance and the user's perception of it. Users who are prone to confirmation bias invest *less* cognitive effort — they take shortcuts. Users who are curious or moderately familiar invest *more* — they engage deeply.

## Method

- **N=32** (15M, 17F), within-subject, lab-based, Tobii TX-300 eye tracker
- Health-related search tasks from 2021 CLEF eHealth IR dataset
- 18 trials per participant: 3 topical relevance levels × 6 documents
- Post-task: perceived relevance, familiarity, curiosity, NASA-TLX, confirmation bias (Berthet method)
- **Key measure: LHIPA** (Low/High Index of Pupillary Activity) — uses discrete wavelet transform to separate cognitive-load-related pupil diameter changes from luminance-related ones. Higher LHIPA = lower cognitive load.

## Core Findings

### 1. LHIPA validates against NASA-TLX (objective ↔ subjective alignment)

Significant difference across NASA-TLX workload groups (*H* = 55.65, *p* < 0.0001, adj. η² = 0.0972 — medium effect). Higher LHIPA (lower cognitive load) tracks lower self-reported workload. This validates LHIPA as a real-time, non-intrusive cognitive load measure for IIR.

### 2. Mismatch drives cognitive load (RQ1) — the big finding

Cognitive load depends on the **interaction** between topical and perceived relevance, not either alone:

| Document is... | User perceives as relevant | User perceives as irrelevant |
|---|---|---|
| **Topically irrelevant** | Higher cognitive load ↑ | Lower cognitive load ↓ |
| **Topically relevant** | Lower cognitive load ↓ | Higher cognitive load ↑ |

- **Irrelevant doc, perceived as relevant:** highest load (*W* = 3.824, *p* = 0.0001) — user is working hard to justify relevance of something that isn't relevant
- **Relevant doc, perceived as irrelevant:** also high load (*W* = 2.823, *p* = 0.0048) — user is effortfully dismissing something that IS relevant
- **When perception matches reality:** lower load in both directions

This is the cognitive signature of *misjudgment effort* — the brain works harder when the assessment conflicts with the content.

### 3. Familiarity and interest increase cognitive load (RQ2) — counter-intuitive

**H2 partially contradicted.** Higher familiarity and interest led to *higher* cognitive load, not lower:

- **Moderate familiarity > unfamiliar** (*z* = 2.659, *p* = 0.008) — users with some knowledge invest more mental resources. Complete novices don't engage as deeply.
- **Curiosity:** large effect (*U* = 39004.0, *p* < 0.0001, *r* = 0.6877). Curious users invest dramatically more cognitive effort.
- **Interaction:** Among highly interested users, those with greater topical knowledge showed *lower* cognitive load — expertise + interest = efficient processing.

### 4. Confirmation bias reduces cognitive load (RQ3)

Significant difference between high and low confirmation bias groups (*U* = 32802.0, *p* = 0.0025, *r* = 0.4260 — large effect). **Users prone to confirmation bias invest less mental effort.** They take cognitive shortcuts — System 1 processing — potentially leading to biased relevance judgments.

When confirmation-biased users perceive a document as relevant, their cognitive load is *higher* compared to when they perceive it as irrelevant (*W* = 3.48699, *p* = 0.0005). They invest effort only for confirming information.

### 5. No interaction between confirmation bias and relevance evaluations

Confirmation bias tendency did not significantly influence *what* users judged as relevant — just *how much effort* they invested. Prior beliefs about the specific topic may matter more than general confirmation bias disposition.

## Why LHIPA matters (vs. raw pupil dilation)

Previous pupillometry studies in IIR used absolute or relative pupil dilation, which is confounded by luminance changes (e.g., dark vs. light web pages). LHIPA uses wavelet decomposition to isolate high-frequency pupil diameter changes (cognitive) from low-frequency changes (luminance). This makes it viable for naturalistic web browsing where page luminance varies constantly.

## Implications for Scrutinizer / AdSERP

1. **AdSERP has pupil data** (`pupil-data/` directory) — BPOGX, BPOGY, LPD, LPV, RPD, RPV at 150Hz. Could compute LHIPA for each trial and overlay cognitive load heatmaps on the scanpath diagrams.

2. **Mismatch detection:** If we know the topical relevance of each SERP result (from ad-boundary-data and result ranking), we could predict where cognitive load spikes — when users evaluate results that don't match their assessment.

3. **The confirmation bias finding** is directly relevant to ad attention: ad-focused users may be taking cognitive shortcuts (low LHIPA), while ad-ignorers who scroll past ads invest more effort to evaluate alternatives.

4. **Curiosity as engagement signal:** The large effect size (*r* = 0.69) for curiosity suggests pupil dilation could differentiate genuine engagement from passive scanning — relevant for distinguishing our "scanner" vs "deep_explorer" behavioral prototypes.

5. **LHIPA as a Scrutinizer metric:** Could render cognitive load as a color overlay on the scanpath (cool=low effort, warm=high effort), showing not just *where* users looked but *how hard they were thinking*.

## Limitations noted by authors

- College student sample only
- Lab setting with predefined tasks (not naturalistic)
- Health domain only — may not generalize
- Didn't collect prior beliefs about specific topics (would explain confirmation bias non-interaction)

## Key references to follow

- Duchowski et al. (2020) — LHIPA algorithm: [ref 20]
- Gwizdka (2014) — Characterizing relevance with eye-tracking: [ref 30]
- Gwizdka (2015) — Differences in fixations on relevant/irrelevant pages: [ref 32]
- Wilson & Sperber — Theory of Relevance (mental effort ↔ relevance): [ref 78]
