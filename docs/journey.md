# Attentional Foraging on SERPs — First Pass Journey

**Date:** 2026-04-01
**Dataset:** AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025)
**Duration:** Single session, ~2 hours from discovery to three notebooks

> **Frozen as of 2026-04-01 end of day.** This document records the first session as it happened, including wrong turns and naive assumptions. Updates go in [findings.md](findings.md). See "What We Got Wrong" at the end for corrections applied in v1+.

---

## Discovery

The session started with a paper drop — Andy spotted "A Versatile Dataset of Mouse and Eye Movements on Search Engine Results Pages" (SIGIR '25). Open access. 2,776 transactional queries on Google SERPs, 47 participants, simultaneous Gazepoint GP3 HD eye tracking (150 Hz) + evtrack mouse capture. The dataset includes SERP HTML snapshots, fixation data, mouse trajectories, scroll events, pupil dilation, and programmatic ad bounding boxes.

The immediate connection: this dataset sits at the intersection of Scrutinizer (gaze replay, foveated rendering) and ClickSense (click commitment dynamics). Gaze replay through Scrutinizer's pipeline on real SERP scanpaths would show what peripheral vision actually delivers at each fixation.

## The Hypothesis

Andy's first observation: academic work reporting mouse-gaze divergence (Huang, White & Buscher 2012; the AdSERP paper itself reports 372px mean distance) has never conditioned on **p(click)**. The higher the click probability, the closer the mouse should be to the eye — because the mouse must converge on the gaze target to execute the click. Averaging across entire browsing sessions (including scanning/idle periods) inflates the reported divergence.

This is a simple idea. Huang, White & Buscher (2012) showed gaze-cursor alignment tightens near clicks, but the continuous distance-as-a-function-of-time-to-click curve — and the scroll correction that changes its shape — hadn't been done.

## Notebook 1: Convergence Analysis

**Setup:** Cloned the AdSERP repo, downloaded behavioral data from Zenodo (~15MB for fixation + mouse + metadata). Built `convergence.py` — for each of 2,776 trials, compute mouse-gaze Euclidean distance at each fixation, tagged by time-remaining-to-click.

**First run (broken):** 12,556 pairs, 2,269 trials skipped. The fixation data had float values where we expected ints. Fixed parsing, reran.

**Second run:** 128,887 fixation-mouse pairs across 2,762 trials. The hypothesis holds:

| Time to click | Mean distance (px) |
|---|---|
| 20-60s | 330 |
| 10-20s | 334 |
| 5-10s | 314 |
| 3-5s | 282 |
| 2-3s | 240 |
| 1-2s | 172 |

Monotonic decrease. 48% reduction from scanning baseline to acquisition. The reported 372px aggregate sits *above* the scanning baseline because it includes all the zero-intent noise.

**Three phases emerged:**
1. **Scanning** (>5s): mouse parked, eye foraging. ~330px divergence.
2. **Evaluation** (2-5s): eye on candidate target, mouse drifting toward it.
3. **Acquisition** (0-2s): motor commitment, mouse converging. ~172px.

Andy identified the 1-2s window as the target acquisition phase (consistent with ClickSense trajectory data) and noted the 2-5s evaluation window preceding it as the interesting zone — the duration is variable and could be calibrated per session by result evaluation time.

**The 0.5-1s bump:** Distance spikes briefly at 0.5-1s before click before collapsing to click. Consistent with a verification saccade — the eye breaks from the target to check something peripherally before committing.

**Per-participant variation:** Acquisition onset ranges from 0.2s to 13.8s (mean=2.4s, SD=2.5s). Individual differences are large enough to warrant per-session calibration.

**X-Y decomposition:** X divergence dominates during scanning (mouse parked to the side, 245px vs 180px Y). The ratio inverts near click — Y briefly exceeds X at the verification window (ratio 1.12). SERPs are vertical layouts; the mouse approaches horizontally first, then the vertical component catches up for the final commit.

**Click prediction:** Logistic regression at 5s horizon gives AUC=0.638. Peak at 2s horizon (AUC=0.720). Raw distance is the dominant feature; convergence rate (slope) adds only +0.002 AUC. The distance signal is simple and powerful; the derivative doesn't help a linear model.

## Refining the Model: Scroll and Viewport State

Checking event types in the mouse data revealed **scroll events** — `window.scrollY` offsets captured at ~60Hz. They're the most frequent event type in many trials. This changed everything.

**Fixation coordinates are in page space** (gaze Y goes to 1647 on a 1024px screen). Mouse coordinates are in screen space. The scroll offset is the missing translation between coordinate systems — but more importantly, scroll state is a behavioral signal.

**The viewport chart** (Andy flagged this as critical): the click target is in the viewport only ~50% of the time before 10s — essentially chance. The target-in-viewport rate only rises meaningfully in the last 10 seconds, hitting ~66% at 5s and ~75% at 2s.

**Andy's reframe:** Before 10s, "distance to click target" is measuring distance to something often not on screen. It's an abstract distance-to-goal metric, not a spatial-motor signal. The convergence story only becomes spatially meaningful once the viewport locks onto the target region.

**Scroll features beat everything:** Adding viewport state to the logistic regression jumped AUC from 0.631 to 0.704 (+0.074). Scroll features alone (0.687) beat distance+all-prior-features (0.638). Target-in-viewport is the key predictor. The convergence signal is downstream of the scroll-stop event.

## Notebook 2: Scroll Regressions

Andy's reaction to seeing scroll regressions in the data: "we have regressions — that's huge, I'm unaware of much work in research quantifying those."

Eye movement regressions in reading are a massive literature. Page-level regressions — scrolling back up to re-examine previously viewed results — are barely studied.

**Prevalence:** 69.1% of trials contain at least one scroll regression. This is the norm, not the exception.

**Magnitude:** Mean 2.8 regressions per trial, mean regression distance 1,118px (~7 result slots). Users don't just glance back one slot — they traverse significant portions of the SERP.

**Timing:** Regressions cluster in the middle of the trial, not at the end. They're part of the evaluation process, not a last-minute correction.

**Decision cost:** Trials with regressions take 11.9 seconds longer (21.6s vs 9.7s). Regression count correlates with decision time at r=0.660.

**Per-participant:** Regression rate varies from 11% to 98% across participants (mean 66.8%, SD 20.6%).

**Sparkline visualization:** 20 highest-regression trials show a characteristic "mountain" pattern — scroll down, peak, scroll back up, settle, sometimes repeat. The scroll position trace is a decision narrative.

## Notebook 3: Lexical Priming

Andy's hypothesis: the well-documented finding that users evaluate results faster as they scroll down is attributed to decreasing effort or attention fatigue. The alternative: it's **cumulative lexical priming**. After reading results 1-3 for a query, the user has accumulated enough shared vocabulary that subsequent results can be evaluated faster — not because they care less, but because the context model is richer.

**Extracted text from 2,772 SERP HTML files** using BeautifulSoup. For each result, computed token set and cumulative overlap with all preceding results.

**The priming curve is strong:**
- Position 1: 38% of tokens already seen in position 0
- Position 5: 56% overlap
- Position 9: 62% overlap
- Novel tokens per result drop from 28 (position 0) to ~10 (position 9)

By the time a user reaches result 9, nearly two-thirds of its vocabulary is already primed. The information environment becomes increasingly redundant.

**SERP-level homogeneity doesn't predict regressions** (r=-0.015). This null result is informative: regressions aren't driven by how homogeneous the overall page is. They're likely triggered by **local novelty events** — a single result that breaks the pattern, introducing vocabulary that doesn't fit the accumulated context. That forces re-evaluation of prior results in light of new information. This per-result novelty → regression trigger analysis is the next step.

Andy also noted that the priming hypothesis connects to his eBay research: regressing time-to-first-click against image size showed bigger images add ~500ms evaluation time. Viewport slot economics — high-information elements cost more to evaluate but the cost is modulated by what context has already been established.

## Key Theoretical Contributions

### What our reanalysis adds

1. **p(click) conditioning** — mouse-gaze distance is a function of decision state, not a fixed property
2. **Two-regime distance metric** — before 10s it's abstract distance-to-goal; after 10s it's spatial distance-to-visible-target
3. **Scroll-stop as the real predictor** — viewport state (AUC=0.704) beats gaze-mouse distance (0.631) for click prediction
4. **Scroll regressions are the norm** — 69.1% of trials, barely studied in the literature
5. **Lexical priming curve** — cumulative overlap reaches 62% by position 9, explaining acceleration without invoking fatigue
6. **Individual calibration** — 2.5s SD in acquisition onset; 20.6% SD in regression rate

### Analyses the dataset enables

The authors' contribution is the dataset itself — a generous, well-structured public resource. These are directions we pursued, enabled by the richness of what they provided:

- Conditioning on click intent and decision stage
- Temporal dynamics (mouse lag/lead vs gaze)
- Scroll regression characterization
- SERP content analysis using the provided HTML snapshots
- Pre-attentive processing and peripheral vision questions
- Per-participant variability analysis

### Connections to other projects

- **Scrutinizer:** Gaze replay on SERP scanpaths. Mouse position replay added to TODO. Foveated rendering would show what peripheral vision delivers at each fixation — which elements are detectable pre-attentively.
- **ClickSense:** Scroll regressions as macro-scale hesitation; click hold duration as micro-scale. If they correlate, that's a multi-timescale confidence measure.
- **evtrack:** Same author (Leiva) behind both the capture library and the dataset. ClickSense is the next-generation capture — narrower but deeper.

## What's Next

- **Per-result novelty → regression trigger:** Does a specific high-novelty result (low cumulative overlap) predict a regression at that scroll position?
- **Pupil dilation × regressions:** The dataset includes pupil data. Pupil dilates on cognitive load/surprise — does it spike during regressions?
- **Fixation-to-result mapping:** Use ad bounding boxes + result positions to assign each fixation to a specific SERP result, enabling per-result evaluation time analysis.
- **Scrutinizer replay:** Render foveated view at each fixation on the actual SERP screenshots. What information is available peripherally at each moment?
- **Interactive visualizations:** The matplotlib plots are a first pass. The sparklines and convergence curves deserve D3/interactive treatment.
- **Coordinate correction:** Properly reconcile page-space fixations with screen-space mouse coordinates using scroll offset. Current analysis uses uncorrected screen-space distance — the scroll correction may sharpen the convergence signal in the 5-10s window.

## Files

```
attentional-foraging/
├── convergence_analysis.ipynb  — Notebook 1: convergence + prediction (12 plots)
├── scroll_regressions.ipynb    — Notebook 2: regression characterization (3 plot sets)
├── serp_priming.ipynb          — Notebook 3: lexical overlap + regression link (2 plot sets)
├── convergence.py              — Standalone aggregate analysis
├── phases.py                   — Per-trial phase detection (not yet integrated)
├── docs/
│   ├── journey.md              — This document
│   └── adserp-key-claims.md    — Theoretical gaps in the original paper
├── html/                       — Exported notebooks for sharing
│   ├── convergence_analysis.html
│   ├── scroll_regressions.html
│   └── serp_priming.html
└── AdSERP/                     — Cloned repo + Zenodo data
    └── data/
        ├── fixation-data/      — 2,776 CSVs (page-space coordinates)
        ├── mouse-movement-data/ — 2,776 CSVs (screen-space + scroll + click)
        ├── trial-metadata/     — 2,776 XMLs (viewport dimensions, query)
        ├── serps/              — 2,776 self-contained HTML files
        └── participants.csv    — 47 participants, demographics
```

---

## What We Got Wrong (v1 corrections)

**Coordinate mismatch (v0 → v1):** The v0 convergence plots used uncorrected screen-space coordinates for both gaze and mouse. Fixation Y is in page-space (increases past screen height as user scrolls); mouse Y is in screen-space. The scroll offset needed to reconcile them was available from the start but not applied until v1.

The corrected plot tells a different story: distance starts *low* (both gaze and mouse near top of page), *increases* as the user scrolls (gaze follows content down the page, mouse stays in screen space), then converges sharply in the last few seconds before click. The 372px aggregate sits in the middle of the curve rather than above the baseline.

The relative findings (two-regime model, convergence timing, viewport features beating distance) are robust — they depend on trends, not absolute pixel values. But the absolute numbers in the v0 table above are wrong.

**Click prediction AUC (v0 → v1):** Distance-only baseline dropped from 0.631 to 0.548 with corrected coordinates. Scroll features (0.687) and the full model (0.704) held. The distance signal was inflated by the coordinate mismatch — scroll features were doing most of the work all along.

---

*Frozen 2026-04-01. The dataset is rich enough for a full paper.*
