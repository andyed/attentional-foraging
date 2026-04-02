# Zhang, Jayawardena & Gwizdka (2026) — Attention! Rethinking What We Measure in CHIIR Studies

**Paper:** "Attention! Rethinking What We Measure in CHIIR Studies"
**Authors:** Dan Zhang, Gavindya Jayawardena, Jacek Gwizdka (U. Texas at Austin, IX Lab)
**Venue:** CHIIR '26, Seattle, WA
**DOI:** [10.1145/3786304.3787944](https://doi.org/10.1145/3786304.3787944)
**Citations:** 0 (published March 22, 2026)

## What This Paper Does

A systematic review of how "attention" has been defined, operationalized, and measured in CHIIR publications (2016-2025). They searched 296 papers, filtered to 45, manually reviewed to 19 papers that clearly study human attention. This is a perspective/meta-science paper, not an empirical study.

## Core Findings

### 1. Only 2 of 19 papers explicitly define attention

- Heck et al. (2021): "a scarce resource, noting that only a small portion of information in visually cluttered environments can be processed"
- Azzopardi et al. (2023): "the cognitive ability to focus on relevant items while ignoring non-relevant ones"

The other 17 papers use "attention" without defining it. The construct is inferred from the methodology, not stated up front.

**Relevance to us:** We should explicitly define what we mean by "attention" in each notebook. Our fixation coverage measures *overt visual attention*. Our TTI calibrator measures something closer to *processing speed* or *engagement onset*. Our priming analysis concerns *cognitive processing efficiency*, not attention per se.

### 2. Taxonomy of attention aspects studied in CHIIR

| Aspect | Papers | Description |
|--------|--------|-------------|
| **Visual Attention** | 13/19 | Overt gaze behavior — where eyes fixate |
| **Joint Visual Attention** | 1 | Coordinated gaze across multiple people |
| **Focused Attention** | 1 | Deep immersion / absorption in content |
| **Fragmented Attention** | 2 | Attention under distraction or multitasking |

Visual attention dominates (68%). No paper studies covert attention, sustained attention, or executive attention in search contexts — all major categories from the psychology literature.

**Relevance to us:** Our work spans multiple categories without labeling them:
- Fixation coverage = **visual attention** (where do eyes go)
- TTI = not attention at all — it's a **behavioral latency** that correlates with processing style
- Priming = **cognitive facilitation** — reduced processing cost, not attention allocation
- Satisfice/optimize = **strategic decision-making** — resource allocation policy, not an attention construct

### 3. How CHIIR measures attention (Table 2 — key reference table)

13 of 19 papers operationalize attention as "observable gaze behavior" measured via eye tracking. Common metrics:
- Total fixation duration (most common)
- Fixation count
- Mean/max fixation duration
- Saccade metrics (count, length, amplitude)
- Heatmap distributions
- Proportion of fixation on AOIs
- Scanpath analysis

Only 2 papers use non-eye-tracking measures:
- Mao et al. (2018): Binary self-report ("examined" vs "read")
- O'Brien et al. (2016): User Engagement Scale questionnaire

**Relevance to us:** We use total fixation duration per result as our primary measure — the most common operationalization. But we also introduce viewport time (behavioral, not gaze-based) and TTI (interaction latency), which are novel measurement approaches for attention-adjacent constructs.

### 4. Three key caveats the paper raises

**Caveat 1: Eye tracking captures overt attention only.**

> "Measures based solely on eye movements primarily capture overt visual attention and may overlook covert processes that are not directly observable, thereby compromising construct validity."

Covert attention — processing information without looking directly at it — is invisible to eye trackers. In SERP context, peripheral vision can process result snippets without fixation. Our work inherits this limitation.

**Relevance to us:** This connects directly to Scrutinizer. Foveated rendering would show what peripheral vision can deliver at each fixation. The "skip rate" we measure (20% at positions 4-9) might partly reflect covert processing — users may be evaluating results peripherally without fixating them.

**Caveat 2: "Attention" is used as both cause and effect.**

> "Attention can be understood as both a cause and an effect. In most CHIIR studies related to attention, it is primarily treated as an outcome variable."

Some studies treat attention as something *allocated* (a cause of behavior), others as something *observed* (an effect of interest). These are different theoretical commitments.

**Relevance to us:** We treat attention as an *effect* (fixation time as an outcome of evaluation) but our priming hypothesis proposes a *cause* (lexical overlap → reduced processing cost → shorter fixation). We should be clear about this causal direction.

**Caveat 3: Behavioral measures partially capture cognitive allocation.**

> "Researchers rely on external indicators, such as eye movements and navigational behaviors, to infer how attentional resources are distributed during certain activities. These behavioral measures only partially capture the underlying cognitive allocation, revealing a gap between empirical observations and theoretical assumptions."

### 5. Recommendations for the field

1. **Specify which aspect** of attention is being studied
2. **Define it explicitly** grounded in established theory
3. **Clarify its causal role** — cause, outcome, or mediator
4. **Align methodology** with the theoretical framing
5. **Use multi-method approaches** — combine eye tracking, physiology, behavioral, and self-report
6. **Articulate scope and limitations** of the theoretical perspective

### 6. The priming connection they highlight

From the background section (§2.1):

> "Meyer and Schvaneveldt [27] first demonstrated semantic priming effects, showing that related words facilitate recognition. Posner and Snyder [46] and Neely [31] further distinguished between automatic priming, which occurs independently of expectations, and strategic priming, which depends on the predictability of cues."

They explicitly discuss priming as a mechanism that influences attention allocation — where prior exposure changes subsequent processing. This is exactly what we're measuring with lexical overlap → fixation time.

## The Paper's Blind Spots

1. **No mention of scroll behavior as an attention signal.** Scrolling is mentioned nowhere despite being the primary navigation behavior on SERPs. Our scroll regression analysis fills this gap.

2. **No mention of temporal dynamics.** How attention changes *during* a search session is absent. Our position-dependent fixation curve and TTI calibration are temporal analyses.

3. **No mention of individual differences in attention strategy.** Our satisfice/optimize segmentation is a user-level attention allocation strategy — the kind of thing this review paper says the field should study but hasn't.

4. **No mention of content effects on attention.** Lexical overlap, novelty, semantic density — none of these appear. Our priming hypothesis is a content-driven modulation of attention that the CHIIR literature hasn't examined.

## How This Frames Our Contribution

This paper is essentially a call-to-arms that our work already answers. Their recommendations and our analyses map cleanly:

| Their recommendation | Our implementation |
|---|---|
| "Specify which aspect of attention" | We measure overt fixation, viewport exposure, interaction latency, and processing speed — four distinct constructs |
| "Define it explicitly" | Each notebook operationalizes its measures with formulas and caveats |
| "Clarify causal role" | Priming is a cause; fixation is an outcome; TTI is a calibration signal |
| "Multi-method approach" | Eye tracking + mouse events + scroll behavior + SERP content analysis |
| "Temporal perspective" | Position-dependent evaluation curves, TTI timeline, first-2-seconds analysis |

If we write this up, Zhang et al. 2026 is the framing paper to cite for why decomposing "attention" into specific measurable constructs matters.
