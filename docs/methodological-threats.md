# Methodological Threats

Threats to validity that pervade the analysis. Each entry names the threat, states what it affects, and records what (if anything) mitigates it.

---

## 1. Practice Effects Across 60 Trials

**Threat:** Participants completed ~60 trials (6 blocks of 10). Any metric averaged across trials confounds task-intrinsic variance with learning-over-time variance. If a participant is faster at trial 55 than trial 5, that difference is practice, not a property of the SERP they saw.

**What it affects:** Every analysis that pools trials within participants — which is nearly all of them. The strongest effects are on trial duration (-20%, p < 0.0001), fixation count (-18.5%, p = 0.0004), and cognitive load (LHIPA +14.7%, p < 0.0001). These three metrics change significantly between block 1 and block 6.

**What does NOT change with practice:** Orientation time, regression rate, click position, and survey amplitude are all stable across the 60 trials (all ns). The task *strategy* is invariant — participants scan the same extent, regress at the same rate, and click at similar positions throughout. What changes is *execution efficiency*: same operations, fewer fixations, less time, lower cognitive load.

**Shape of learning:** Block-level analysis shows most learning occurs in blocks 1–3, then plateaus. Power-law fit to trial duration gives b = -0.076 (R² = 0.38), consistent with shallow skill compilation rather than deep strategy change. 72% of participants (34/47) show the speedup individually.

**Mitigation:**
- All cross-position analyses use within-trial contrasts, which are immune to practice effects (every trial has positions 0–10)
- Practice does not interact with key findings: the forward-only dwell increase (ρ = +0.82), regression ballistics, and survey–evaluate transition are structural properties of each trial
- The learning curve is itself a finding: the asymptotic pattern (blocks 4–6) represents expert SERP scanning, what power users do in production; the early-trial pattern represents novice scanning
- If practice effects are a concern for a specific analysis, the notebook should test ordinal × metric interaction or restrict to blocks 4–6

**Evidence:** [18_learning_curve.ipynb](../notebooks-v2/18_learning_curve.ipynb)

---

## 2. Forced-Choice Task Constraint

**Threat:** Every trial ends with a click. No abandonment, no query reformulation, no next-page navigation. This eliminates the core foraging decision (stay vs. leave the patch) and inflates evaluation thoroughness.

**What it affects:** Regression rates (65% of trials — likely lower in free browsing where users can just leave), total fixation counts, trial duration, and any metric that depends on how far through the page users scan. The ski-jump boundary effect is amplified because users *must* pick from the available set.

**Mitigation:**
- Lorigo et al. (2008) found ~66% nonlinear scanpaths under free reformulation with informational queries, matching our 65% regression rate under forced choice. The within-page scanning behavior may be intrinsic, not an artifact
- The forced-choice constraint *isolates* the evaluate-and-commit loop, which is the component we're studying. It's a feature, not a bug, for decomposing within-page behavior
- Generalizing to the stay/refine/abandon decision requires production log data (noted in README and TODO)

---

## 3. Lab-Controlled Display Environment

**Threat:** SERPs served via localhost in a controlled lab. No competing browser chrome, tabs, bookmarks bar, or address bar. Mouse X-axis variation is artificially constrained versus real browsing.

**What it affects:** All mouse-based signals — approach-retreat analysis, mouse-gaze coupling, viewport-state prediction. In production, cursor wanders to tabs, back buttons, URL bar. The 66 px proximity threshold for consideration-set detection would need recalibration.

**Mitigation:**
- Eye-tracking measures (fixation patterns, saccade amplitude, pupil dilation) are less affected — foveal vision targets the SERP content regardless of surrounding chrome
- The cursor signals should be interpreted as upper bounds on effect sizes achievable in production

---

## 4. Transactional Product Queries Only

**Threat:** All queries are "buy [product]" — transactional, not informational or navigational. The evaluation strategy for comparing product listings may differ from evaluating informational results (Wikipedia, Stack Overflow) or navigational queries (finding a specific site).

**What it affects:** Generalizability of the task model. The survey–evaluate decomposition may not hold for informational queries where the user is looking for a single fact rather than comparing alternatives.

**Mitigation:**
- Product comparison is a well-defined, common search task. The foraging model (patch evaluation, giving-up time) maps directly
- Zhang et al. (CHIIR 2026) found similar attentional constructs across query types, suggesting the phase structure generalizes

---

## 5. Result Band Estimation

**Threat:** Result positions are estimated from document height and result count, not from ground-truth bounding boxes. Position assignment errors propagate into every per-position analysis.

**What it affects:** All position-level analyses — forward-only dwell curves, click position distributions, per-position cognitive load, approach-retreat by position.

**Mitigation:**
- The estimation uses a uniform-height model with a 200 px header offset, consistent with Google's layout at the time of data collection
- Ad bounding boxes are available from the dataset and are used for ad/organic classification
- Errors are systematic (same offset across all trials), not random, so they bias absolute position assignments but preserve relative ordering
- Cross-checking with fixation Y distributions shows clear clustering at expected band boundaries

---

## 6. Eye Tracker Noise (Gazepoint GP3 HD)

**Threat:** The GP3 HD is a consumer-grade eye tracker (~0.5–1° accuracy). 24.5% of fixation Y-coordinates exceed the screen height (1024 px), indicating substantial noise. These are clamped to screen bounds in data_loader.py but represent a real precision limit.

**What it affects:** Fine-grained spatial analyses — parafoveal preview detection (notebook 19, null result), reading span estimation, exact fixation-to-word mapping.

**Mitigation:**
- FPOGY clamping corrects the most extreme errors (position 9 dwell ratio corrected from 1.25 to 0.79)
- Analyses that depend on spatial precision (parafoveal preview) report their null results with the caveat that tracker noise may mask true effects
- Aggregate patterns (position-level means, saccade amplitude distributions) are robust to individual-fixation noise

---

## 7. LHIPA Window Size

**Threat:** LHIPA (Low/High Index of Pupillary Activity) requires a minimum analysis window for reliable wavelet decomposition. Per-position windows may be too short for some positions, especially at the extremes.

**What it affects:** Per-position LHIPA values, especially at early positions (short dwell) and late positions (few data points).

**Mitigation:**
- Trial-level LHIPA uses the full trial duration, which is typically sufficient (mean ~22 s)
- Per-position cognitive load is measured via Butterworth LF/HF (§3b-iv), not per-position LHIPA. Trial-level LHIPA is flat across click positions 0–8 with a step down at boundary positions 9–10 (see CHANGELOG v9). The wavelet method requires minimum ~7.5s windows; per-result segments (~2s) are below this threshold.

---

## 8. Survivor Bias in Per-Position Aggregates

**Threat:** Position-level summary statistics (means or medians at each of N ≈ 10 positions) condition on the user having reached that position. Deep positions (6–9) are populated by a self-selected subset — users who chose to scroll past earlier results. Position-level correlations (ρ on *N* = 10 points) are therefore *not* estimates of a within-trial gradient across all users; they are estimates of an aggregate pattern among successively shrinking subsets.

**What it affects:**
- All "ρ × position" correlations on tiny *N* (position-mean or position-median rhos): LHIPA × click position (ρ = −0.903, *N* = 10), Butterworth LF/HF × position (ρ = −0.927, *N* = 11), forward-only gaze dwell × position (ρ = +0.82, *N* = 9).
- The headline "position effect" framing in papers that cite these as monotonic gradients.
- Boundary-step findings (positions 9–10) are especially vulnerable — the cohort at position 9 may be fundamentally different from the cohort at position 0 (thorough-evaluator optimizers vs decisive first-clickers).

**Why it matters:** A ρ = −0.927 on 11 points looks like strong evidence for a monotonic gradient but has *df* = 9. The confidence interval is wide, the *p*-value is fragile, and the interpretation hinges on assuming the population is stable across positions — which it is not (survivorship).

**Mitigation:**
- **Lead with trial-level statistics when available.** NB05 reports LHIPA × click position at ρ = −0.088 on *N* = 2,721 trials (*p* = 4.1 × 10⁻⁶) [NB05:K8] — significant but small. The ρ = −0.903 on 10 points is demoted to a secondary "position-mean" companion with an explicit ecological-fallacy warning [NB05:K9].
- **Every citation of a position-aggregate rho must state the N.** We have retrofitted this into findings.md §0, §3b-iv, §3d-ii and README lines 100–101, 106, 117.
- **Report within-participant alongside between-trial.** NB09 Key Claims K16–K19 (SERP difficulty) and K36–K40 (evaluation depth) show that within-participant rank correlations — which avoid the survivorship issue by holding participant fixed — are the cleaner test.
- **For boundary-step findings, distinguish a step from a gradient.** LHIPA at positions 9–10 shows a step (flat across 0–8, drops at 9–10). Calling this a "ρ = −0.903 gradient" misreads the shape. The correct framing is "boundary effect," visible as a discrete drop, and the ρ is a summary statistic of a piecewise shape, not a linear trend.
- **For Butterworth LF/HF × position, the post-audit ρ = −0.927 is a position-median correlation.** Paper drafts that cite it must write "on *N* = 11 position medians aggregated from 2,719 trials" — not "on 2,719 trials."
