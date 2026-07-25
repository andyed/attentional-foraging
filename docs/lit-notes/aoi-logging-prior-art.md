# Prior Art: AOI-Keyed Interaction Logging

Compiled 2026-05-17 for the attentional-foraging research program. Covers the competitive landscape of systems that log user interaction relative to Areas of Interest (AOIs) or semantically-typed content blocks. Supports the paper related-work positioning, the AllSERP companion paper, and any future grant/positioning work on the typed-AOI representational claim.

---

## The question

Do any other systems log relative to AOIs?

Short answer: **AOI-keyed logging exists in pockets, but real-time, semantically-typed, episode-partitioned AOI logging on running pages is essentially unique to the `approach-retreat` line.** Every existing system gives up at least one of those four properties.

---

## The four-bucket landscape

| Bucket | What gets logged | AOI-aware? | Live in-page? | Semantic typing? | Per-AOI episode geometry? |
|---|---|---|---|---|---|
| Eye-tracking analysis software | Gaze fixations + AOI dwells/visits/transitions | Yes (manually defined on screenshots) | **No** — post-hoc on recorded data | No (geometric only) | No (descriptive stats) |
| Web analytics / session replay | Mousemove + click events keyed to DOM selectors | DOM-element ≠ AOI | Yes | **No** | **No** — heatmaps, not episodes |
| SERP click-model research | Per-result summary stats (dwell, hover, presence) | Per-rank, not per-AOI bbox | **No** — offline mouse data | No | No internal episode geometry |
| Cursor-modeling research | Raw cursor stream or 500-feature session bag | **No** — session-level, layout-blind | Capture is live; modeling is session-flat | No | No |
| **`approach-retreat` (Edmonds 2026)** | **19-field per-AOI episode records** | **Yes — runtime `getBoundingClientRect()`** | **Yes** | **Yes — organic / native ad / display ad / other** | **Yes — approach/retreat/dwell-in-proximity** |

The bottom row is the unoccupied four-property intersection.

---

## Bucket 1 — Eye-tracking analysis software

**Tobii Pro Lab, iMotions, SR Research Data Viewer, Pupil Labs, GazePoint Analysis.**

These tools have used AOI-based dwell/visit/transition metrics for ~20 years on gaze data. The AOIs are typically drawn by the researcher onto screenshots or videos *after* recording. Output is descriptive statistics (time-to-first-fixation, total dwell, # visits) and transition matrices — no in-the-loop instrumentation, no semantic typing, no cursor coupling.

**Gap:** Post-hoc analysis only. The AOI exists in the analysis tool, not in the running page. Cannot generalize to deployment scenarios where the layout is generated server-side per request.

---

## Bucket 2 — Web analytics / session replay

**Hotjar, FullStory, Mouseflow, Microsoft Clarity, Crazy Egg, Heap, Amplitude (with autocapture).**

Log mousemove, scroll, and click events keyed to DOM selectors at runtime. Produce click maps, scroll maps, and session replay videos. Some autocapture frameworks (Heap, Amplitude) infer event taxonomies from DOM structure.

**Gap:** DOM element ≠ AOI. A `.serp-result` selector matches every result identically; the analytics layer has no notion of the *semantic type* of the region (organic vs ad vs widget) and no per-element *episode partitioning* of the cursor trajectory. The data model is event-stream-with-element-key, not AOI-keyed episode geometry. You can build heatmaps but cannot ask "what was the cursor doing relative to the third organic result between time t1 and t2."

---

## Bucket 3 — SERP click-model research

**Liu et al. 2014** "From Skimming to Reading" (CIKM '14) — closest per-result-AOI precedent. Per-result mouse summary statistics (dwell, hover, presence) feed a two-stage examination model.

**THUIR group** — Wang et al. 2015 (PSCM), Zhang et al. 2021 (CBCM). Per-rank click models with eye-tracking primitives. Per-rank, not per-AOI bbox.

**Lagun et al. 2014** "Towards Better Measurement of Attention and Satisfaction in Mobile Search" — viewport-band residence as attention proxy. Per-band, not per-AOI.

**Gap:** Per-rank summaries, no internal episode geometry. Operate offline on dataset traces, not as live instrumentation. The per-result-AOI commitment exists in Liu 2014 but is collapsed into scalar summaries (dwell/hover/presence), not preserved as a contiguous episode signal `d(t)` from which approach/retreat geometry can be computed.

---

## Bucket 4 — Cursor-modeling research

**Arapakis & Leiva SIGIR '20** — 1D-CNN autoencoder on raw trajectories. Session-level.

**Brückner, Arapakis, Leiva CIKM '20, SIGIR '21** — Deep CNN/RNN over raw cursor for query abandonment; later parsimonious examination of mouse-movement length. Session-level.

**Arapakis et al. (TOIS 2014 and earlier baselines)** — ~500-feature hand-crafted session bag (trajectory geometry, kinematics, event counts, temporal, spatial distribution).

**AdSight (Villaizán-Vallelado et al. SIGIR '25)** — Transformer predicting fixation from mouse trajectories on AdSERP. Uses AOI bboxes from the dataset but folds them into a sequence-model input, not per-AOI episode logging.

**Gap:** The whole lineage treats the cursor trace as a single stream (session-level features or raw sequence). Layout is implicit in the trace statistics, never factored out. Cannot compute gaze-cursor distance on AttentiveCursor (no gaze in that dataset); cannot reuse the per-AOI episode primitive across layouts.

---

## What `approach-retreat` does that none of the four buckets does

1. **Live in-page** instrumentation (like Bucket 2 / Hotjar, unlike Bucket 1 / Tobii).
2. **Semantically-typed AOIs** at runtime — organic / native ad / display ad / other — discovered by `getBoundingClientRect()` keyed to DOM structure (like Bucket 1 / Tobii's manual AOIs, unlike everyone's live logger).
3. **Per-AOI episode partitioning** of mousemoves into contiguous deliberation intervals (like Bucket 1 gaze AOIs, but for cursor, and at runtime).
4. **Configurable per page-layout** — the same library runs across different SERP layouts because the AOI layer is rebuilt at page-load.

That intersection is the structural argument. Reviewers and grant readers who see only one of the four properties (or two) will not see why the typed-AOI cascade is doing meaningful work; this table makes the empty cell visible.

---

## Lineage anchor — structured in-page instrumentation

The structured-in-page-instrumentation thesis predates the cursor-modeling literature by 13 years and traces directly to Edmonds:

- **Edmonds 2001** — Optimoz Firefox gesture extension. Cursor instrumentation in the browser.
- **Edmonds 2003** — Uzilla. Browser-side interaction capture.
- **Edmonds, White, Morris, Drucker 2007** — "Instrumenting the Dynamic Web." *Journal of Web Engineering*, 6, 243–260. Microsoft Research. In-page logging of interaction events; argues client-side scripting callbacks capture user experience that server-side logging cannot. **DOM Signatures lineage.**
- **approach-retreat 2026** — Current iteration. Adds semantic AOI typing + per-AOI episode geometry to the 2007 in-page-instrumentation thesis.

(The Edmonds 2007 paper is not currently in `references.bib`; add when ready to cite. The approach-retreat library bib entry already notes the Optimoz/Uzilla lineage.)

---

## Generalization implication — layout-drift resilience

Mono cursor models (Bucket 4) are vulnerable to SERP layout drift: as Google adds AI Overviews, shopping packs, video carousels, the trace statistics shift relative to the training distribution. The session-level feature bag and the raw-trace sequence model both implicitly encode the layout distribution.

The typed-AOI approach absorbs layout shift at the **typing layer**: when a new module type appears (say, an `ai_overview` etype), it gets bounding-box extraction and an etype label, then the per-AOI episode model runs unchanged. The 7-feature per-AOI primitive is portable across layouts because layout has been factored out of the model into the data representation.

This is the resilience argument that the four-bucket table makes concrete: every other live logger either gives up the semantic typing (Bucket 2) or gives up live-page operation (Bucket 1), so neither can serve as a drift-resilient deployment substrate. Only the unoccupied intersection can.

---

## Pointers

- Closest table-level prior art: **Liu et al. 2014** (Bucket 3) — per-result summary stats, offline.
- Closest live-page prior art: **Hotjar et al.** (Bucket 2) — DOM-keyed, no semantics, no episodes.
- Closest semantic-AOI prior art: **Tobii / iMotions** (Bucket 1) — manual AOIs, post-hoc.
- Closest cursor-instrumentation prior art (own lineage): **Edmonds 2007** — in-page logging, no AOI typing yet.

---

*Source: this document captures an observation that came up in methods paper drafting on 2026-05-17. Saved here because the observation is research-program-level (applies to AllSERP, future grants, OSEC task-model work) rather than methods-paper-specific.*
