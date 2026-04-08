# Literature Review: Scroll Regressions in SERP Evaluation

Compiled 2026-04-02 for the attentional-foraging project. Focus on empirical work with eye-tracking or scroll data.

---

## Papers you probably need

### 1. Maxwell & Azzopardi — Information Scent, Searching and Stopping (ECIR 2018)

Maxwell, D. & Azzopardi, L. (2018). Information Scent, Searching and Stopping: Modelling SERP Level Stopping Behaviour. In Advances in Information Retrieval, ECIR 2018, LNCS vol. 10772, pp. 210-222. Springer.

**Why it matters:** Models SERP-level stopping decisions using information foraging theory. Introduces a formal stopping model where the user evaluates the "scent" of remaining results against the cost of continued examination. Directly relevant to your patch-leaving framework — this is the IR community's closest analog to MVT applied at the SERP level. Azzopardi's broader program (SIGIR 2014, CHI 2019, CHIIR 2021) builds economic cost-benefit models of search interaction.

**Gap your work fills:** Azzopardi/Maxwell model the *leave* decision but not within-page *re-evaluation*. Your regression data (69% of trials, mean 2.8 regressions) shows that SERP browsing isn't a one-pass stopping problem — it's a revisitation loop. Their model would predict abandonment where you observe regression.

### 2. Liu et al. — A Two-Stage Examination Model (CIKM 2014)

Liu, Y. et al. (2014). From Skimming to Reading: A Two-stage Examination Model for Web Search. CIKM 2014.

**Why it matters:** Proposes that SERP examination has two stages: (1) skimming (fast scan, deciding *whether* to read) and (2) reading (slower evaluation of content). The two-stage model separates the decision to examine from the depth of examination — a distinction your data supports (flat 220ms per-fixation duration but declining fixation *count*).

**Gap:** Their model is single-pass. Your regression data shows a third stage: re-evaluation, where the user returns to previously skimmed content and examines it at reading depth.

### 3. RecGaze / Riding the Carousel — Eye Tracking in Carousel Recommenders (SIGIR 2025)

de León Martínez et al. (2025). RecGaze: The First Eye Tracking and User Interaction Dataset for Carousel Interfaces. SIGIR 2025.
Also: Riding the Carousel (2025) — extensive analysis of browsing behavior in horizontal scroll carousels.

**Why it matters:** The carousel interface is structurally analogous to a SERP — sequential items requiring scrolling (horizontal vs vertical). RecGaze captures 87 users × 3,477 interactions with gaze, cursor, clicks. They find F-pattern/golden-triangle browsing even in carousels. The "swiping back" behavior in carousels is the horizontal analog of your scroll regressions.

**Cross-reference opportunity:** Their dataset + yours = vertical and horizontal foraging comparison. Same MVT framework, different scroll axes.

### 4. Lorigo et al. — Eye Tracking & Behavior on Search Result Pages (JASIST 2008)

Lorigo, L., Haridasan, M., Brynjarsdóttir, H., Xia, L., Joachims, T., Gay, G., Granka, L., Pellacini, F., & Pan, B. (2008). Eye tracking and online search: Lessons learned and challenges ahead. JASIST, 59(7), 1041-1052.
Also relevant: Lorigo, L., Pan, B., Hembrooke, H., Joachims, T., Granka, L., & Gay, G. (2006). The influence of task and gender on search and evaluation behavior using Google. IP&M, 42(4), 1123-1131.

**Why it matters:** You already cite the ~66% nonlinear scanpath finding. This is still the primary empirical baseline for regression prevalence on SERPs. No one has substantially updated this number since — until your 69% (which aligns remarkably well despite a very different task and 17 years of SERP evolution).

### 5. Buscher, Dumais & Cutrell — Beyond Position Bias (SIGIR 2010)

Buscher, G., Dumais, S. T., & Cutrell, E. (2010). The good, the bad, and the random: an eye-tracking study of ad quality in web search. SIGIR 2010.

**Why it matters:** Examines how ad quality affects gaze patterns on SERPs. Shows that users develop *different* examination strategies for ads vs organic results. Relevant to your ad_focused/ad_ignorer prototype distinction — the behavioral split you observe is supported by their finding that ad evaluation is qualitatively different from organic result evaluation.

### 6. Huang, White & Buscher — User See, User Point (CHI 2012)

Huang, J., White, R. W., & Buscher, G. (2012). User see, user point: gaze and cursor alignment in web search. CHI 2012.

**Why it matters:** Characterizes gaze-cursor divergence during search. Their mean distance (~200px when reading, ~400px when scanning) is consistent with your 200-500px range. They found cursor position correlates with gaze but lags temporally — the cursor follows the eyes, not the reverse. Your mouse-gaze convergence curve extending their analysis with scroll correction.

### 7. eyeScrollR — Mapping Eye Tracking on Scrollable Pages (BRM 2024)

eyeScrollR: A software method for reproducible mapping of eye-tracking data from scrollable web pages. Behavior Research Methods (2024).

**Why it matters:** Addresses exactly the coordinate mapping problem you struggled with — remapping eye-tracking gaze coordinates to full-page coordinates using scroll data. Their deterministic algorithm is what the AdSERP importer does. Cite for methodological grounding of the scroll-correction approach.

### 8. Shi, Jayawardena & Gwizdka — LHIPA Pupillometry (CHIIR 2025)

Already in your docs as `shi2025-pupillometric-cognitive-load.md`. Directly validates your LHIPA findings.

### 9. Arapakis & Leiva — Predicting User Engagement with Direct Displays (SIGIR 2016)

Arapakis, I. & Leiva, L. A. (2016). Predicting User Engagement with Direct Displays Using Mouse Cursor Information. SIGIR '16, pp. 599-608.

**Why it matters:** The most directly relevant prior work on cursor trajectory features for SERP evaluation. Extracts 638 cursor features (movement patterns, pauses, direction changes, hover behavior) and achieves AUC 0.86 for predicting user attention to SERP components. This is the feature-engineering predecessor to AdSight's neural approach.

**Gap your work fills:** Their 638 features are aggregate statistics (mean velocity, total distance, direction change count). They don't decompose cursor trajectories into *episodes* with geometric properties (arc ratio, lateral displacement, Fitts' law ID). The approach-retreat decomposition — enter/dwell/exit per result — is a different representational choice that preserves temporal structure and spatial geometry.

### 10. Guo & Agichtein — Beyond Dwell Time (WWW 2012)

Guo, Q. & Agichtein, E. (2012). Beyond dwell time: estimating document relevance from cursor movements and other post-click searcher behavior. WWW '12, pp. 569-578.

**Why it matters:** Established cursor movement as a relevance signal, showing that post-click cursor features (movement speed, scroll patterns, cursor position relative to content) predict document relevance better than dwell time alone.

**Gap your work fills:** Their work is *post-click* — cursor behavior after the user has already committed. Approach-retreat analysis captures the *pre-click* evaluation phase where the user is deciding whether to commit. The complementary phases: Guo & Agichtein tell you what the user thought after clicking; approach-retreat tells you what the user thought before clicking.

### 11. Brückner, Arapakis & Leiva — Mouse Movement Length for Decision Making (SIGIR 2021)

Brückner, L., Arapakis, I., & Leiva, L. A. (2021). When Choice Happens: A Systematic Examination of Mouse Movement Length for Decision Making in Web Search. SIGIR '21, pp. 1510-1514.

**Why it matters:** Directly studies mouse movement during choice on SERPs, including ad notice, abandonment, and frustration scenarios. Shows that mouse movement length discriminates between decision states. The closest published work to "cursor trajectory encodes decision confidence."

**Gap your work fills:** They use total movement length as a scalar feature. The arc geometry decomposition (arc ratio, max retreat distance, Fitts' law ID) recovers the *shape* of the movement, not just its magnitude. NB24 (rebuilt 2026-04-08) shows these features discriminate deferred (re-approached) from rejected cursor episodes (Mann-Whitney p < 10⁻³, N = 731 retreats), while scalar movement length does not.

### 12. Leiva & Arapakis — The Attentive Cursor Dataset (Frontiers 2020)

Leiva, L. A. & Arapakis, I. (2020). The Attentive Cursor Dataset. Frontiers in Human Neuroscience, 14:565664.

**Why it matters:** Largest public cursor+attention dataset for SERPs — 2,737 users, cursor traces with attention labels and original SERP HTML. Provides the methodological precedent for capturing cursor behavior at scale on real search pages. Their attention labeling (attended vs not-attended) is the binary version of our four-class taxonomy (clicked / deferred / evaluated-rejected / not-approached).

**Gap your work fills:** Their binary attention label collapses the non-attended class. Our four-class taxonomy splits non-clicks into three behaviorally distinct categories recoverable from cursor trajectory geometry alone.

---

## Papers that may exist but I couldn't confirm

### Spatial memory for SERP positions

Your finding (η²=0.87 for regression target specificity, but region-level not result-level precision) appears genuinely novel. The closest analog is:

- **Spatial memory in visual search:** Aivar, P., Li, C.-L., Tong, M. H., Kit, D., & Hayhoe, M. M. (2024). "Knowing where to go: Spatial memory guides eye and body movements in a naturalistic visual search task." JOV 24(9). Shows spatial memory guides return fixations in real-world search — but in physical environments, not web pages. (Note: earlier work by Solman & Smilek, 2010, established spatial memory effects in simpler visual search tasks.)

- **Revisit behavior in web browsing** (Cockburn & McKenzie 2001, Obendorf et al. 2007) — characterizes page-level revisitation patterns but not within-page spatial memory for specific content positions.

I could not find any work specifically on spatial memory for SERP result positions during scroll regressions. This is likely a novel contribution.

### Satisficing/maximizing × regression behavior

- **Schwartz et al. (2002)** — Maximizing vs Satisficing scale. Applied extensively in consumer choice but I found no application to SERP scroll regression behavior.
- **Zhai et al. (2022)** — "An information retrieval benchmarking model of satisficing and impatient users' behavior in online search environments" (Expert Systems with Applications). Models satisficing in IR but uses click logs, not eye-tracking or scroll data.

Your satisficer/optimizer × LHIPA finding (ρ=-0.55) appears to be the first empirical connection between maximizing tendency, scroll regression rate, and objective cognitive load on SERPs.

---

## What the literature does NOT cover (your novelty)

1. **Within-page re-evaluation modeling.** MVT/IFT models patch-leaving but not the "go back and look again" behavior that dominates 69% of SERP sessions. Click models (Chuklin et al. 2015) assume monotonic top-to-bottom examination. Your regression data breaks that assumption.

2. **Spatial memory precision for SERP positions.** Nobody has characterized how accurately users can scroll back to a specific result. Your η²=0.87 (region-level but not result-level) is a new finding.

3. **Ballistic scroll kinematics as a methodological confound.** Your observation that backward scroll velocity is significantly higher (915 vs 784 px/s) with a ballistic velocity profile (ρ=0.87) means any analysis using dwell ratios during regressions is confounded by viewport mechanics. This hasn't been reported.

4. **LHIPA × boundary decision cost × satisficing.** The three-way connection between pupillometric cognitive load, boundary click behavior, and regression rate is new.

5. **Regression as the alternative to abandonment.** The forced-choice task makes this explicit — where naturalistic search allows abandonment, forced-choice reveals the full re-evaluation cycle that abandonment normally hides. This reframes Diriye et al.'s (2012) abandonment taxonomy.

---

## Recommended reading order for the blog post

For the Scrutinizer blog post, cite lightly:
1. Lorigo et al. 2008 (the ~66% baseline)
2. Azzopardi (SIGIR 2014 / CHI 2019) for the economic model framing
3. Liu et al. CIKM 2014 for the two-stage examination model
4. Shi et al. CHIIR 2025 for the LHIPA cognitive load connection

For the full attentional-foraging findings paper (if written):
- All of the above plus RecGaze, eyeScrollR, Buscher et al., and the spatial memory novelty claim

---

## Summary & Positioning

| Paper | Finding | Gap our work fills |
|---|---|---|
| **Lorigo et al. JASIST 2008** | ~66% nonlinear scanpaths on SERPs | Our 69% is comparable but under forced-choice (inflated base rate); we add scroll-level quantification (magnitude, timing, kinematics) |
| **Azzopardi & Maxwell (IFT stopping models)** | Model SERP-level stopping decisions | Single-pass assumption — don't model within-page re-evaluation. Our regressions break this. |
| **Liu et al. CIKM 2014** | Two-stage model: skim → read | Needs a third stage: **re-evaluate**. Our confirmation/rejection split on revisit characterizes it. |
| **RecGaze, SIGIR 2025** | Carousel analog — horizontal scroll regressions | Same behavioral pattern in a different UI paradigm. Cross-validates. |
| **eyeScrollR, BRM 2024** | Validates scroll-correction methodology for eye tracking | Confirms our approach to coordinate correction. |
| **Chuklin et al. (click models)** | Assume monotonic examination (top-to-bottom, single pass) | Our data breaks monotonic assumption — 69% of trials are non-monotonic. |
| **Arapakis & Leiva SIGIR 2016** | 638 cursor features, AUC 0.86 for attention prediction | Aggregate features; we decompose into episodes with geometric properties (arc ratio, Fitts' ID) |
| **Guo & Agichtein WWW 2012** | Post-click cursor features predict relevance | Post-click; we capture pre-click evaluation phase (approach-retreat) |
| **Brückner et al. SIGIR 2021** | Mouse movement length discriminates decision states | Scalar length; we recover trajectory *shape* (arc ratio, max retreat distance, Fitts' ID) which discriminates re-approached from committed-rejection retreats (NB24, p < 10⁻³) |
| **Leiva & Arapakis Frontiers 2020** | 2,737-user cursor+attention dataset, binary attention labels | Binary (attended/not); our four-class taxonomy splits non-clicks into three behavioral categories |

### What's novel (not in the literature)

1. **Within-page re-evaluation modeling** — MVT/IFT model patch-leaving but not patch-revisiting. We show regressions serve two distinct functions: confirmation (to the winner, +32% fixations) and rejection (of alternatives, -17% fixations). This is a new behavioral decomposition.
2. **Spatial memory precision for SERP positions** — η²=0.87 for position-specific scroll targeting, but landing precision ≈ random baseline. Region-level spatial memory with salience weighting (click target remembered ~1.8x better). No prior work on SERP spatial memory at this granularity.
3. **Ballistic scroll kinematics as methodological confound** — Backward velocity > forward (915 vs 784 px/s), ballistic profile (ρ=0.87). Nobody has reported the velocity asymmetry or its implications for dwell ratio analysis during regressions. This is a methods contribution.
4. **LHIPA × boundary cost × satisficing** — Three-way connection: trial-level LHIPA is flat across click positions 0–8 then steps down at boundary 9–10 (aggregate ρ=-0.90, driven by boundary step), regression rate correlates with LHIPA (ρ=-0.55), optimizers click higher not deeper. Each pair may exist in isolation in the literature; the triangle is new.
5. **Regression as alternative to abandonment** — Forced-choice reveals what naturalistic search hides: when users can't abandon, they regress. The 69% regression rate is the behavioral cost of forced commitment. (Note: this rate is likely inflated 3-5x by the forced-choice design; the mechanism transfers but the base rate does not.)

6. **Retreat arc geometry as deliberation/commitment signal.** No prior work examines the *shape* of cursor retreat trajectories after SERP result evaluation. Arapakis & Leiva (2016) use aggregate cursor features (distance, speed, direction changes); Brückner et al. (2021) use movement length. Neither decomposes the post-evaluation retreat into geometric properties. NB24 (rebuilt 2026-04-08, AdSERP 2,776 trials, N = 731 retreats) shows three retreat features predict whether the user re-approaches the result later in the same trial: arc ratio (path length / direct distance, p = 8.4 × 10⁻⁴), Fitts' law ID at max retreat point (p = 3.5 × 10⁻⁴), and max retreat distance (p = 0.022). The pattern is **curved + close + low ID = "I'll be back"; straight + far + high ID = "I'm done."** This provides a continuous deliberation/commitment signal recoverable from cursor telemetry alone, complementing the four-class taxonomy by giving a within-class continuous measure for the deferred-vs-rejected boundary. (Caveats: pooled-arcs statistics, mixed-effects model needed for reportable inference; the original "epistemic action / WM offloading" hypothesis we initially proposed was *not* supported and has been discarded — far retreats reflect commitment that has already happened cognitively, not commitment caused by raised motor cost.)

### Framing for the paper

The existing literature models SERP examination as a **single forward pass** with a **stopping decision**. Our contribution: examination is a **multi-pass process** with distinct cognitive phases (orientation → evaluation → working memory accumulation → regression/commitment), and the regression decision is where the interesting cognitive work happens — not at the stopping point, but at the *re-evaluation* point.

---

Sources:
- [Azzopardi SIGIR 2014 — Economic Models of Search](https://www.dcs.gla.ac.uk/~leif/papers/fp093-azzopardi.pdf)
- [Azzopardi CHI 2019 — Economic Models of HCI](https://strathprints.strath.ac.uk/66466/1/Azzopardi_Zuccon_CHI_2019_Building_economic_models_of_human_computer_interactionpdf.pdf)
- [Maxwell & Azzopardi — Information Scent, Searching and Stopping](https://www.semanticscholar.org/paper/Information-Scent,-Searching-and-Stopping-Modelling-Maxwell-Azzopardi/2fd6ab7aa2e3dfeebf69fc3792cd85c6a855b476)
- [Liu et al. CIKM 2014 — Two-Stage Examination](http://www.thuir.cn/group/~YQLiu/publications/cikm2014-liu.pdf)
- [RecGaze SIGIR 2025 — Carousel Eye Tracking](https://arxiv.org/abs/2504.20792)
- [Riding the Carousel 2025](https://arxiv.org/abs/2507.10135)
- [eyeScrollR 2024 — Scroll Coordinate Mapping](https://pmc.ncbi.nlm.nih.gov/articles/PMC11133154/)
- [Buscher et al. SIGIR 2010 — Ad Quality Eye Tracking](https://dl.acm.org/doi/10.1145/1835449.1835459)
- [Huang, White & Buscher CHI 2012 — Gaze-Cursor Alignment](https://dl.acm.org/doi/10.1145/2207676.2208591)
- [Chuklin et al. 2015 — Click Models](https://clickmodels.weebly.com/uploads/5/2/2/5/52257029/mc2015-clickmodels.pdf)
- [Diriye et al. CIKM 2012 — Search Abandonment](https://dl.acm.org/doi/10.1145/2396761.2398399)
- [Shi et al. CHIIR 2025 — LHIPA Pupillometry](https://doi.org/10.1145/3698204.3716458)
- [Zhai et al. 2022 — Satisficing IR Model](https://www.sciencedirect.com/science/article/abs/pii/S095741742101650X)
- [Aivar et al. JOV 2024 — Spatial Memory in Visual Search](https://jov.arvojournals.org/article.aspx?articleid=2800746)
- [Arapakis & Leiva SIGIR 2016 — Predicting User Engagement with Direct Displays](https://dl.acm.org/doi/10.1145/2911451.2911505)
- [Guo & Agichtein WWW 2012 — Beyond Dwell Time](https://dl.acm.org/doi/10.1145/2187836.2187914)
- [Brückner, Arapakis & Leiva SIGIR 2021 — Mouse Movement Length for Decision Making](https://dl.acm.org/doi/10.1145/3404835.3463088)
- [Leiva & Arapakis Frontiers 2020 — The Attentive Cursor Dataset](https://doi.org/10.3389/fnhum.2020.565664)
