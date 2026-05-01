# Jayawardena, Shi & Gwizdka (CHIIR 2026) — Key Claims Analysis

**Paper:** Gavindya Jayawardena, Li Shi, and Jacek Gwizdka. 2026. "Effects of Working Memory Capacity and Search Task Complexity on Cognitive Load." *CHIIR '26*, March 22–26, 2026, Seattle, WA, USA. Pages 89–99.
**DOI:** [10.1145/3786304.3787871](https://doi.org/10.1145/3786304.3787871)
**Local PDF:** `~/Downloads/3786304.3787871.pdf`

**Assessment.** Empirical paper. First-author Gavindya, senior Gwizdka. Uses **RIPA2** (their own modified RIPA, ref [39] = JEMR 2025) to track cognitive load (CL) across task phases (begin / mid / end) and task types (fact-checking vs decision-making) by working-memory-capacity (WM) group. Lab study, N=30, Tobii TX-300 at 300 Hz, DuckDuckGo with AI features off. Effect sizes are uniformly small (η² ≈ 0.03–0.05); the paper compensates with mechanism + multi-channel (CL + emotions) framing rather than effect magnitude.

**Relationship to our work.** This paper IS the standalone RIPA publication that the `project_gavindya_team_enablement_policy.md` strategy assumed was an open lane for Gavindya's team. **The lane is filled.** Reframe the Thursday offer.

---

## Method

- **N=30** (13M, 17F), ages 18–37, *M*=24.2, *SD*=4.74. UT Austin IRB.
- **Tobii TX-300 + iMotions**. Desktop, 24" 1920×1080 monitor.
- **Design:** within-subjects task type (FC vs DM) × phase (begin / mid / end). Between-subjects: WM capacity group (high vs low, median split on N-back composite z-score from n2 + n3 levels).
- **Tasks:** 4 fact-checking (FC, e.g., "find the 2019 NBA champion") + 3 decision-making (DM, e.g., choose weekend trip lodging within $500 budget). 7 trials per participant. DM order before FC.
- **WM measure:** Standard N-back paradigm (Duchowski et al. [22] / Appel et al. [2]), n0–n3 levels, 16 sessions, 4 per level. WM composite = mean *d_L* sensitivity score across n2 and n3, z-scored, then median split.
- **CL measure:** **RIPA2** (Jayawardena et al. [39] = JEMR 2025).
  - SG_VLF: *M*=486, *N*=2, window 973 points, target ≤0.29 Hz
  - SG_LF: *M*=60, *N*=4, window 121 points, target ≤4 Hz
  - Output: **LF² − VLF²** (squared *difference*, not ratio, for stability)
  - Clipped [0, 1.5]
  - Buffer requirement: **1200 samples = 4 s @ 300 Hz** before first valid output
  - 1-second moving average for visualization smoothing
- **Inclusion:** FC trials ≥ 15 s, DM trials ≥ 3 min (RIPA needs ≥ 4 s per phase). 20 trials excluded total (3 DM + 17 FC).
- **CL signal split** into three equal-length phases (begin / mid / end) per trial, mean RIPA2 per phase.
- **Emotions:** AFFDEX [11] facial-expression analysis on webcam → joy, valence, engagement, surprise, confusion. Threshold: total duration where likelihood > 50%.
- **Behavioral:** time-on-task + unique webpage visits (OCR'd from screen recordings, deduplicated).
- **Stats:** Mixed-design repeated-measures ANOVA on Box-Cox-transformed CL (raw was right-skewed, kurtosis 44). Holm correction. Kendall's τ for emotion-CL associations (non-normal).

---

## Core findings

### 1. CL is higher for DM than FC tasks (RQ1)

> *F*(1, 56) = 11.21, *p* = .002, η² = 0.034 (small effect)

DM tasks (decision-making, integrative, multi-criteria) impose more CL than FC tasks (fact-checking, retrieval-style). This is a main effect of task type pooled across WM groups.

| Group | DM mean CL | FC mean CL |
|---|---:|---:|
| Low WM | 0.138 (SD 0.073) | 0.118 (SD 0.109) |
| High WM | 0.109 (SD 0.044) | 0.120 (SD 0.145) |

The within-WM-group DM-vs-FC differences did not reach significance after Holm (low WM *p_holm* = .850; high WM *p_holm* = .996). The main effect comes from the pooled comparison.

### 2. WM capacity does not differ on time-on-task overall (4.2.1)

Mixed-design rmANOVA: task × WM group interaction *F*(1, 30) = 1.59, *p* = .226, η² = 0.006. Time-on-task is driven by task structure (DM ≈ 543 s, FC ≈ 50 s), not WM capacity. **Note:** the high-WM-spent-more-time-on-FC post hoc result (*M_diff* = 13.24 s, *p_holm* = .023) is a behavioral signature of more thorough fact-checking, not a CL effect.

### 3. High-WM users explore more pages on FC tasks (4.2.2) — *the satisficer/optimizer connection*

Their §4.2.2 framing: high-WM individuals adopt "more deliberate or exhaustive" strategies; low-WM "prioritize efficiency or early termination." That maps directly onto the **optimizer/satisficer** distinction.

**Pairs sharply with our `project_lfhf_orthogonality.md`:** on AdSERP, *load trajectory* (steep-phase per-participant LF/HF features) does NOT predict satisficer/optimizer classification (LOO-LR AUC = 0.523 vs 0.522 baseline; participant-slope × regression-rate ρ = −0.020, *p* = 0.90, N = 46).

**Combined picture, under the hypothesis that WM drives satisficer/optimizer:**

```
WM (trait) ──► strategy (behavior) ──► load trajectory
                       ⊥ shown
```

- Their paper: WM (trait, upstream) → exploration strategy (high WM visits more pages, takes longer on FC).
- Our paper: regression-rate-defined strategy ⊥ load trajectory (steep-phase per-participant LF/HF features do not predict satisficer/optimizer classification; LOO-LR AUC = 0.523 vs 0.522 baseline).

If WM drives strategy (Jayawardena 2026's documented direction), then the only causal path WM → load that runs through behavior is **mediated by strategy** — and we've shown that mediation is zero. The **WM-via-strategy path to load is therefore also zero** under the hypothesis.

**What remains untested:** a *direct* WM → load path that bypasses strategy. Two plausible channels:

1. **Emotional regulation.** CHIIR §4.6 shows WM modulates affect-CL coupling (high WM: CL ↑ correlates with valence/joy/engagement; low WM: CL ↑ correlates with confusion/surprise). Emotional state could affect pupil dynamics directly without going through search strategy.
2. **Capacity-on-pupil.** WM might modulate per-position effort allocation or arousal independently of behavioral exploration depth.

A clean test would need a corpus with both pupil signals AND a WM assessment. AdSERP has no N-back / complex-span measure.

**Useful for ETTAC discussion:** "Jayawardena 2026 documents WM-trait → exploration-strategy. We show strategy is orthogonal to load trajectory. Together, the WM-via-strategy path to load is zero; direct WM → load paths (emotional regulation, capacity-modulated arousal) remain to be tested."

**WM ≠ optimizer/satisficer (constructs differ even if the hypothesis links them).** WM is a cognitive *capacity* (items you can hold + manipulate, measured by N-back / complex span); optimizer/satisficer is a decision *strategy* (exhaustive vs. good-enough, measured by Schwartz MS-13 or behavioral proxies). The hypothesis Jayawardena 2026 supports is that high WM *enables* optimizer-shaped behavior because capacity is a precondition for exhaustive comparison. The two constructs are not identical (a high-WM person can choose to satisfice; a low-WM person can want to optimize but be capacity-constrained), but under the hypothesis they map onto each other behaviorally.



Mixed-design rmANOVA on unique page visits: main effect of task *F*(1, 30) = 153.48, *p* < .001, η² = 0.655.
Post hoc: during FC, high-WM visited *M_diff* = 0.718 more unique pages than low-WM (*p_holm* = .050).
DM showed the same trend but ns (*p_holm* = .081). Interpretation: high-WM users *can* afford to explore more even when the task is simple.

### 4. CL is highest at the beginning, decreases to mid, stable through end (RQ2) — *the load-bearing finding for our work*

> *F*(2, 56) = 12.235, *p* < .001, η² = 0.053 (small to medium effect)

| Phase | CL pattern |
|---|---|
| Begin | Highest |
| Mid | Significantly lower than begin (*p_holm* = .004) |
| End | Same as mid (*p_holm* = .890); also lower than begin (*p_holm* = .001) |

**Their interpretation (§5.2):** *"reflecting initial processing and/or problem understanding, before decreasing in the mid phase and stabilizing in the end phase ... participants adapted to the task over time, reducing the cognitive resources needed as they progressed."* The word they use is **cognitive adaptation**.

**Task × phase interaction is not significant** (*F*(2, 56) = 1.629, *p* = .205) — same temporal shape in both DM and FC tasks.

**Task × phase × WM interaction is not significant** (*F*(2, 56) = 2.30, *p* = .109, η² = 0.009) — same temporal shape across WM groups, though magnitude is higher for low WM during DM.

### 5. Sustained higher CL on DM during mid + end phases

DM remains slightly elevated after mid: mid *p_holm* = .062 (approaches significance), end *p_holm* = .021. Their reading: DM's ongoing integration / reconciliation prevents full adaptation, while FC users settle once they've found the verifying source.

### 6. CL × emotion correlations split sharply by WM group (RQ3)

| Group | Pattern |
|---|---|
| **High WM** | CL ↑ correlates with **positive** affect (valence, joy, engagement) on both task types. τ = .153–.261, *p* < .001 across all six pairs (3 emotions × 2 tasks). No association with confusion or surprise. |
| **Low WM** | CL ↑ correlates with **negative** affect (confusion, surprise) on DM tasks. τ_confusion = .163 (*p* = .018) and τ_surprise = .259 (*p* < .001). Weaker on FC. Negligible association with valence/joy/engagement on DM. |

**Their interpretation:** high-WM individuals frame cognitive demand as engagement; low-WM individuals frame it as overload. The asymmetry is in the *emotional regulation* of CL, not in the CL itself.

---

## Methodological caveats they flag

- **N = 30** — small sample, statistical power for higher-order interactions is limited.
- **Task order not counterbalanced** — DM always before FC, so FC may show carryover CL from preceding DM tasks. They acknowledge this directly.
- **Young adults only** (18–37). They explicitly call for older-adult and cognitive-impairment replications.
- **Lab environment** — DuckDuckGo with AI off, controlled monitor, no real consequences. Limits ecological validity for high-stakes search.
- **CL non-normality** — heavy right tail (skewness 4.92, kurtosis 44). Box-Cox transform addressed it but Shapiro-Wilk still significant after; sample-size-driven.

---

## What this means for our portfolio

### ETTAC paper (Andy + Duchowski) — repositioning required

Their RQ2 finding (CL highest at begin, decreases over time, "cognitive adaptation") is the **same temporal shape** as our NB14:K3 framework-compilation gradient (ρ = −0.927 for SERP-position-level CL on AdSERP).

**They have primacy on the temporal-decrease claim.** Differentiation must come from *unit*, *resolution*, *measurement pipeline*, and *mechanistic framing*:

| Dimension | Jayawardena 2026 (CHIIR) | Our §3.3 (ETTAC submission) |
|---|---|---|
| Unit | Task-phase (begin / mid / end of a 50–540 s trial) | SERP rank position (P0–P10) within a trial |
| Resolution | Coarse: 3 phases per trial | Fine: per-rank-segment (1 s window) |
| Estimator | RIPA2 (their pipeline) | Butterworth IIR LF/HF (Duchowski 2026, ref [9]) — independent pipeline |
| Convergent validity | None (RIPA2 alone) | LHIPA cross-index ρ = −0.125, *p* = 7.5 × 10⁻¹⁰ |
| Sample | N = 30, lab, 7 trials each | N = 47, public dataset, 2,719 trials |
| Effect size | η² = 0.053 | ρ = −0.927, *p* < 0.0001 |
| Mechanism named | "Cognitive adaptation" (Section 5.2, descriptive) | Framework compilation (Pirolli & Card scent + Sweller schema acquisition) — mechanistic |
| Click-outcome stratification | None | Clicked vs non-clicked LF/HF (currently omitted from §3.3 due to position confound) |

**Operational difference: RIPA2's 4 s buffer requirement.** They state this explicitly (§3.4.2). Our `pupil-lfhf/validation/compute_ripa2.py` uses MIN_SAMPLES=150 (1 s) for per-position aggregation. **Per-fixation RIPA2 is well below their reliability floor.** The R1 dissociation must be qualified accordingly:
- Per-(trial, position) findings (~1–3 s aggregate) are in similar ballpark to their smoothing window — defensible.
- Per-fixation findings (~200 ms) are below their stated floor — flag as "RIPA2-pipeline output" not "RIPA2 cognitive load" per the existing memory `reference_jayawardena_jemr_2025_ripa2.md`.

### RIPA2 standalone publication — already shipped

**The lane the strategy memo described as open is filled.** This paper IS the empirical-findings RIPA2 publication. Reframe the offer to Gavindya:
- Don't position AdSERP as her standalone-RIPA pub; she's already published the empirical RIPA2 paper.
- Position AdSERP as a **next corpus** her published method extends to: n=47 (vs her 30), 2,719 trials, naturalistic SERP with click-outcome ground truth and AOI structure — features her n=30 controlled study lacks. Useful for replication / external-validity claims.

### CIKM 2026 (Andy + Jacek)

Saccade-orientation lane is independent of pupillometry → no overlap with this paper. The CIKM submission's pupil components (if any) need positioning that doesn't compete with Jayawardena 2026's claim ground.

### CHI 2027 task-model paper

No direct overlap. Their task-phase decomposition (begin/mid/end of a single trial) is operationally different from our OSEC orient/survey/evaluate/commit task-model decomposition. Mention as related work.

---

## What we cannot replicate from AdSERP

- **N-back / WMC measure** — AdSERP has no working-memory assessment. We cannot test the high-vs-low WM split.
- **AFFDEX emotion correlations** — AdSERP did not record webcam, no facial expressions captured.
- **DM vs FC task type contrast** — AdSERP is transactional product search only; no decision-making integration tasks.

What we *can* do: their per-trial 3-phase decomposition (begin/mid/end of a 50–540 s trial) could be tested on AdSERP if we wanted a direct replication of the temporal-adaptation finding at task-phase resolution rather than per-position. Probably not worth the trouble — our per-position result is sharper, and replicating their unit-of-analysis on a different corpus doesn't add much.

---

## Citations they use that we should also cite (or are already citing)

- **[39] Jayawardena, Jayawardana & Gwizdka (JEMR 2025)** — RIPA2 method paper. Already in our bib (`Jayawardena2025RIPA2` in `references.bib`). Cite when discussing the RIPA2 spec.
- **[22] Duchowski et al. (CHI 2020) LHIPA** — already in our bib (`DKGB+20` in `andrewd.bib`). Cited in our §3.3.
- **[40] Jayawardena et al. (Procedia 2022)** — original RIPA paper (different parameters, less aligned with cognitive frequency bands per JEMR 2025's own correction). Don't cite without checking what we'd say about it.
- **[68] Peysakhovich et al. (2015)** — frequency-domain pupil power-spectral-density. Foundational for both LF/HF and RIPA. Likely already in our bib.

## Citations the paper makes that we should NOT bring forward

- The original RIPA (ref [40]) used different parameters that don't align with cognitive bands. Per JEMR 2025's own correction, prefer JEMR 2025 spec [39] over Procedia 2022 [40].
- AFFDEX [11] is closed-source proprietary; cite only if we adopt that specific pipeline.

---

## Quick reference table — claim → stat

| Claim | Stat | Effect size |
|---|---|---|
| DM > FC for CL | *F*(1, 56) = 11.21, *p* = .002 | η² = 0.034 |
| CL highest at begin, drops to mid | *F*(2, 56) = 12.24, *p* < .001 | η² = 0.053 |
| Begin > mid pairwise | *p_holm* = .004 | — |
| Begin > end pairwise | *p_holm* = .001 | — |
| Mid ≈ end | *p_holm* = .890 | — |
| Phase × task interaction | *F*(2, 56) = 1.63, *p* = .205 | ns |
| Phase × WM × task | *F*(2, 56) = 2.30, *p* = .109 | η² = 0.009, ns |
| High-WM CL × valence (DM) | τ = .252, *p* < .001 | small |
| Low-WM CL × surprise (DM) | τ = .259, *p* < .001 | small |
| Unique-page main effect of task | *F*(1, 30) = 153.48, *p* < .001 | η² = 0.655 (large) |
| FC pages, high vs low WM | *M_diff* = 0.718, *p_holm* = .050 | — |
| FC time, high vs low WM | *M_diff* = 13.24 s, *p_holm* = .023 | — |
