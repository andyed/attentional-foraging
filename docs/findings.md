# Findings

Reanalysis of the AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). The [journey doc](journey.md) records how this started; this document records what we think we found.

**Status:** v2, 2026-04-01. Viewport-normalized attention density. Regression-stratified analysis. Honest correction of headline stat.

---

## Theoretical framework: The Attentional-Foraging Equilibrium

These findings are interpreted through the **Attentional-Foraging Equilibrium (AFE)** — a framework synthesizing Rational Inattention (Sims 2003) with Information Foraging Theory (Pirolli & Card 1999). The core equation: **ρ = V / (τ + T_s + σ²)**, where V = expected value, τ = handling time, T_s = travel time between patches, σ² = uncertainty. The user leaves a patch when ρ falls below threshold.

How each finding maps to AFE:

- **Lexical priming** (Finding 2) reduces τ — processing redundant vocabulary is cheaper. The speed-up is declining cost, not declining effort.
- **Scroll regressions** (Finding 4) are travel costs (T_s) paid for re-evaluation when a novel result disrupts the reward rate estimate.
- **Mouse-gaze convergence** (Finding 5) traces the transition from foraging (high T_s, moving between patches) to exploitation (low τ, evaluating within a patch).
- **Per-participant variance** (Finding 7) maps to bandwidth λ — individual cognitive capacity differences.
- The **forced-choice purchase task** creates a defined stopping criterion that makes the patch-leaving decision observable. Most SERP studies use open-ended tasks where the user can leave without clicking.

Full presentation: [The Attentional-Foraging Equilibrium](https://gamma.app/docs/The-Attentional-Foraging-Equilibrium-A-Synthesis-of-Digital-Behav-aq0bw2ujjxwypbt)

---

## Dataset constraints

Two major caveats versus generalized SERP behavior. These pervade all findings.

**1. Forced choice with optimizing intent.** Participants were instructed to "click on the item they would typically choose" for product purchase queries, with up to 1 minute per trial and a confirmation step. Every trial ends with a click — no abandonment, no query reformulation. This is optimizing behavior ("what would I actually buy?"), not satisficing ("is this good enough?"). The 69% regression rate and thorough evaluation patterns reflect this constraint.

**2. Limited X-axis variation.** SERPs were served via localhost in a controlled lab environment. No competing browser chrome, no tabs, no bookmarks bar, no address bar. Mouse position variance is artificially constrained compared to real browsing where attention splits across the full browser window.

**Bottom line:** The findings describe underlying mechanisms (priming, convergence, regression patterns), not base rates. The mechanisms should transfer to real SERP behavior; the exact numbers are specific to this task design.

---

## 1. Lexical overlap builds rapidly down the SERP

By position 9, 62% of a result's vocabulary has already appeared in prior results. Novel tokens per result drop from 28 to 10. This is a content-structural fact, independent of behavior.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 2

## 2. Overlap predicts attention density — but only in re-evaluation

**This is the key finding, and it's more nuanced than our initial report.**

We measure attention density: fixation duration normalized by time-in-viewport (≥50% visible, IAB standard). This controls for exposure time — a result visible for 10s naturally accumulates more fixation than one visible for 2s.

| Analysis | Partial r | p | N |
|----------|-----------|---|---|
| All trials, positions 1-9 | -0.054 | 2.4×10⁻⁹ | 12,121 |
| All trials, positions 1-7 (no ski jump) | -0.021 | 0.028 | 10,902 |
| **No-regression trials, positions 1-9** | **-0.002** | **0.92** | **2,640** |
| **Regression trials, positions 1-7** | **-0.033** | **0.003** | **8,342** |

**What this means:** In trials where users scroll straight down and click without scrolling back (pure sequential evaluation), overlap does not predict attention density. The priming effect only appears in trials with regressions — when users scroll back to re-evaluate earlier results. High-overlap results are re-evaluated more efficiently on the second pass, not the first.

The initial headline stat (partial r = -0.054) was driven by two factors:
- Regression trials (69% of the dataset in this forced-choice paradigm)
- The position 8-9 "ski jump" (attention density spikes at the bottom of the SERP, where users face a pseudo forced-choice between the last results and the cost of loading page 2)

**Honest reframing:** Lexical priming facilitates **re-evaluation**, not first-pass scanning. On first contact, users evaluate each result on its own terms regardless of vocabulary overlap. But when they return to re-examine — after encountering a novel result that disrupts their context model — high-overlap results are processed faster because the vocabulary is already primed.

This distinction matters for theory: it's consistent with the reading literature where regressions serve integration/verification functions, not initial comprehension.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Step 4

## 3. SERP-level homogeneity does not predict trial duration or regressions

Neither trial duration (r = -0.027, p = 0.15) nor regression count (r = -0.015) varies with overall SERP homogeneity. The signal is local (per-result overlap), not global. SERP-level homogeneity is too blunt — the variance that matters is which specific results have high vs low overlap with their predecessors.

**Notebook:** [serp_priming.ipynb](../notebooks/serp_priming.ipynb), Steps 2.5 and 3

## 4. Scroll regressions are the dominant browsing pattern

69.1% of trials contain at least one scroll regression. Mean 2.8 regressions per trial, mean magnitude 1,118px (~7 result slots). Regression count correlates with decision time (r=0.660).

**Caveat:** The 69% rate is likely inflated by the forced-choice optimizing task. Participants who would normally abandon and reformulate are instead forced to re-evaluate. In real browsing, regression rates are probably lower.

**Notebook:** [scroll_regressions.ipynb](../notebooks/scroll_regressions.ipynb)

## 5. Mouse-gaze convergence depends on click intent

With scroll-corrected coordinates, distance starts low (~90px), rises as the user scrolls (gaze follows content, mouse stays in screen space), peaks near ~500px, then converges sharply in the last ~2s before click.

**Notebook:** [convergence_analysis.ipynb](../notebooks/convergence_analysis.ipynb)

## 6. Viewport state predicts clicks better than distance

At a 5s horizon, viewport features (target visible, time since scroll) outperform mouse-gaze distance (AUC 0.704 vs 0.548). The scroll-stop event is the stronger click signal.

**Notebook:** [convergence_analysis.ipynb](../notebooks/convergence_analysis.ipynb)

## 7. Individual differences are large

Per-participant acquisition onset ranges from 0.2s to 13.8s (SD=2.5s). Regression rates vary from 11% to 98% (SD=20.6%).

---

## Theoretical connections

The **Attentional-Foraging Equilibrium** provides the overarching frame. AFE models the SERP as a patch environment where the user's reward rate ρ = V / (τ + T_s + σ²) determines when to stop evaluating and commit to a click. The mechanisms below all operate on components of that equation.

The re-evaluation priming result connects to:

- **Surprisal theory** (Hale 2001, Levy 2008): High-overlap results have low surprisal on re-encounter → faster processing. In AFE terms, this reduces τ (handling time) for primed results.
- **E-Z Reader** (Reichle, Rayner, Pollatsek): Regressions serve integration/verification. Re-reading primed text is faster. Regressions are the T_s cost of re-entering a previously visited patch.
- **Given-new contract** (Clark & Haviland 1977): On re-evaluation, most vocabulary is "given" → fast processing. The given-new structure is what makes τ decline with position.
- **Rational Inattention** (Sims 2003): σ² (uncertainty) determines how much information the user acquires before deciding. Per-participant variance in regression rates and acquisition onset reflects differences in bandwidth λ — the cognitive channel capacity each user brings.

The first-pass null result is also informative: during initial sequential scanning, users may process results at a level above individual lexical items — evaluating domain, formatting, result type — where bag-of-words overlap is the wrong granularity. In AFE terms, first-pass scanning is dominated by T_s (travel between patches) rather than τ (within-patch evaluation), so the priming mechanism operates on the wrong component.

---

## What would test first-pass priming properly

The forced-choice lab paradigm can't isolate first-pass priming because:
1. 69% of trials have regressions (the non-regression subset is too small)
2. Participants optimize rather than satisfice

The right test: **at-scale production logs with first-click behavior only**. Millions of queries, no forced choice, natural satisficing. Measure time-to-first-click by position, conditioned on cumulative lexical overlap with results above the fold. This approach — large-scale behavioral logs with natural stopping criteria — is the path to a clean test (cf. Huang, White & Buscher 2012, who demonstrated the value of production-scale cursor data for understanding attention).

---

*v2, 2026-04-01. Corrected from v1: regression-stratified analysis reveals priming is a re-evaluation effect, not a first-pass effect.*
