# Scroll Compensation in HCI Eye Tracking: Coordinate Mapping vs. Gaze Kinematics

**Status:** focused narrative review; source-checked 2026-09-01; not a systematic review.
**Question:** In studies of scrollable interfaces, is gaze correction documented well enough to
prevent movement of the page from being interpreted as movement of the eyes?

---

## Short answer

**Scroll compensation is documented, but scroll-safe saccade computation is not established here as
a routine reporting standard.** The literature clearly recognizes the need to synchronize gaze with
scrolling and to map screen coordinates to page content. It is much less consistent about reporting
the coordinate frame used for saccade metrics, the order of gaze-event inference and coordinate
remapping, or the treatment of fixation pairs that overlap a scroll.

The strongest direct prior art is Larigaldie, Dreneva, and Orquin's `eyeScrollR` paper (2024). It
provides a transparent screen-to-page mapping algorithm and explicitly warns that applying the
mapping before inferring fixations and saccades can turn stationary gaze during a scroll into an
apparent saccade. That warning is the same failure mode that motivates the AdSERP safeguard, but its
preferred remedy assumes access to raw gaze. AllSERP consumers may instead begin with page-mapped
fixations, making exclusion of scroll-overlapping fixation pairs the conservative downstream rule.

The defensible novelty is therefore **not** “scroll correction has not been documented.” It is that
AllSERP makes the coordinate/kinematics boundary explicit for dataset consumers, quantifies its
effect on a substantive result, and supplies an auditable correction when only page-space fixations
and scroll timestamps are available.

## Three processing layers that should not be collapsed

For ordinary scrolling content, let `s(t)` be the page's vertical scroll offset:

```text
y_page(t) = y_viewport(t) + s(t)
delta_y_page = delta_y_viewport + delta_s
```

The first equation is useful for assigning gaze to a document AOI. The second shows why the same
coordinate transform is unsafe for a saccade spanning a scroll: `delta_s` is stimulus motion, not eye
motion.

| Layer | Scientific question | Appropriate coordinate treatment |
|---|---|---|
| Gaze-to-content mapping | Which document element was viewed? | Map screen/viewport gaze into page or DOM coordinates. |
| Event inference | Which samples form fixations, saccades, or smooth pursuit? | Prefer raw screen-space gaze plus synchronized display/input state; do not let a page transform manufacture an event. |
| Saccade kinematics | How far and in which direction did the eye move? | Use viewport-space displacement, compensate stimulus motion, or conservatively exclude intervals containing scroll motion. |

Sticky elements, nested scroll containers, smooth/inertial scrolling, and display latency complicate
all three layers. A single “scroll corrected” label does not disclose which problem was solved.

## What the inspected literature documents

“Not reported” below means that no explicit rule was found in the inspected paper. It does **not**
prove that the authors' private code or vendor software lacked such a rule.

| Source | What is documented | Boundary relevant to AllSERP |
|---|---|---|
| [Beymer and Russell (2005)](https://doi.org/10.1145/1056808.1057055) | `WebGazeAnalyzer` records gaze, screen changes, the browser DOM, scroll events, and clicks, then aligns detected fixations with page text. This establishes an early instrumented-browser lineage in which scrolling is part of the synchronized record. | The paper does not state a reproducible rule for saccade vectors whose endpoints straddle scroll motion. Its main target is reading analysis and gaze-to-DOM alignment. |
| [Turner, Iqbal, and Dumais (2015)](https://doi.org/10.1145/2800835.2804331) | Gaze and browser scroll events are timestamped against the same clock. The analysis distinguishes gaze location in the viewport from location in document structure and studies the fixation immediately before a scroll. | Because the dependent gaze measure is pre-scroll location rather than a cross-scroll saccade vector, the coordinate-contamination problem is avoided rather than operationalized. |
| [Menges, Tamimi, Kumar, Walber, Schaefer, and Staab (2018)](https://doi.org/10.1145/3204493.3204535) | The paper calls gaze synchronization on interactive web pages non-trivial, shows why naive screen-to-page mapping fails for fixed elements, and proposes a DOM-aware page representation assembled from viewport captures. | The contribution targets accurate gaze visualization and AOI metrics. It documents page-representation hazards but not a general scroll-overlap rule for saccade amplitude or direction. |
| [Larigaldie, Dreneva, and Orquin (2024)](https://doi.org/10.3758/s13428-024-02343-1) | `eyeScrollR` deterministically maps screen-space gaze/fixations to full-page coordinates using synchronized scroll input, including explicit handling of fixed regions and scroll/display lag. The authors describe their method as the only then-known approach that was both reproducible and transparent. | This is the direct warning: infer fixations and saccades from raw gaze before page mapping, because mapping first can interpret stationary gaze during a scroll as a saccade. The authors also note irreducible uncertainty when scrolling occurs during a fixation. |
| [Heo, Manduchi, and Chung (2024)](https://doi.org/10.1145/3649902.3656493) | In the distinct case of reading with screen magnification, the paper uses mouse-controlled content position to undo display motion. The compensation converts gaze tracking moving text into a document-relative representation suitable for fixation/saccade analysis. | This is strong evidence for the general stimulus-motion principle, but it is not a standard web-page scroll pipeline and should be cited as an adjacent conceptual analogue. |

## Synthesis

### What is well documented

- Scrolling makes the viewed stimulus dynamic and requires synchronized interaction state.
- AOI analysis often needs screen/viewport gaze mapped into document or DOM coordinates.
- Fixed or sticky elements cannot be handled by adding one global scroll offset.
- Timing near scroll onset is a real error source because input, display refresh, video, and gaze
  timestamps can disagree.

### What is not yet shown to be standard practice

- Reporting whether exported gaze/fixations are screen-space, viewport-space, page-space, or
  element-relative.
- Reporting whether fixation and saccade inference occurred before or after page remapping.
- Reporting how smooth or inertial scrolling and nested scroll containers were handled.
- Reporting an exclusion, compensation, or classification rule for eye-movement events that overlap
  stimulus motion.
- Publishing enough code or parameters to reproduce the correction.

The literature therefore supports a **reporting and reproducibility gap**, not a claim that the
underlying geometry is unknown. `eyeScrollR` is particularly important because it both states the
failure mode and argues that earlier manual and commercial mapping methods were not transparent or
reproducible enough to audit.

## Relation to the AllSERP / AdSERP rule

The canonical project rule is documented in
[`../methodology/scroll-aware-saccades.md`](../methodology/scroll-aware-saccades.md): when computing
a vector between consecutive page-space fixations, exclude the vector if its time interval contains a
scroll event. For retained pairs, the page offset is constant and cancels under differencing.

This is a conservative dataset-consumer adaptation of the same principle documented by `eyeScrollR`:

- If raw gaze and synchronized display state are available, infer eye-movement events without letting
  the page-coordinate transform create false motion.
- If only page-space fixations and scroll timestamps are available, do not treat a cross-scroll
  fixation pair as an eye-only displacement.
- Subtracting the per-fixation scroll offset reconstructs viewport displacement, but exclusion remains
  safer when a fixation itself overlaps scrolling or when scroll/display latency is uncertain.

In AdSERP, this audit changed the sign of a survey-versus-evaluate orientation contrast and caused the
earlier F-pattern verticality interpretation to be retracted; the amplitude-compression result
survived. `[LAB, AdSERP, rank-type-N/A; NB13:K1–K8, K13–K22]`

## Claim boundary for papers and data documentation

Safe wording now:

> Prior work documents screen-to-page gaze remapping for scrollable interfaces, and recent methods
> work explicitly warns that page motion can be misclassified as eye motion. However, this focused
> review found no uniform reporting convention for coordinate frame, processing order, or the
> treatment of saccade intervals that overlap scrolling. We therefore document and validate a
> conservative rule for consumers of page-mapped fixation data.

Do not currently claim that:

- AllSERP invented scroll compensation.
- No prior HCI work recognized false saccades caused by scrolling.
- Most HCI studies compute saccades incorrectly.
- The prevalence of adequate reporting is known.

The last two statements require a systematic sample rather than a narrative review.

## Protocol for a prevalence audit

To turn “not routinely reported” into a measured claim, sample empirical papers from ETRA, CHI,
CHIIR/SIGIR, and web-usability venues that satisfy both criteria: participants interacted with
scrollable content, and the paper reports scanpaths or saccade-level metrics rather than AOI dwell
alone. Code each paper for:

1. gaze coordinate frame;
2. scroll source and timestamp synchronization;
3. smooth/inertial scrolling and fixed/nested-region handling;
4. fixation/saccade inference order;
5. treatment of events overlapping scroll motion;
6. availability of executable code or complete parameters.

Report `documented / inferable / not reported / not applicable` for each field. Do not code silence as
“incorrect,” and separate AOI-only studies from papers whose conclusions depend on gaze kinematics.

## Verified references

- Beymer, David, and Daniel M. Russell. 2005. “WebGazeAnalyzer: A System for Capturing and Analyzing
  Web Reading Behavior Using Eye Gaze.” *CHI '05 Extended Abstracts*, 1913–1916.
  <https://doi.org/10.1145/1056808.1057055>
- Turner, Jayson, Shamsi T. Iqbal, and Susan T. Dumais. 2015. “Understanding Gaze and Scrolling
  Strategies in Text Consumption Tasks.” *UbiComp/ISWC '15 Adjunct*, 829–838.
  <https://doi.org/10.1145/2800835.2804331>
- Menges, Raphael, Hanadi Tamimi, Chandan Kumar, Tina Walber, Christoph Schaefer, and Steffen Staab.
  2018. “Enhanced Representation of Web Pages for Usability Analysis with Eye Tracking.” *ETRA '18*.
  <https://doi.org/10.1145/3204493.3204535>
- Larigaldie, Nathanael, Anna Dreneva, and Jacob L. Orquin. 2024. “eyeScrollR: A Software Method for
  Reproducible Mapping of Eye-Tracking Data from Scrollable Web Pages.” *Behavior Research Methods*
  56(4): 3380–3395. <https://doi.org/10.3758/s13428-024-02343-1>
- Heo, Seongsil, Roberto Manduchi, and Susana Chung. 2024. “Reading with Screen Magnification: Eye
  Movement Analysis Using Compensated Gaze Tracks.” *ETRA '24*.
  <https://doi.org/10.1145/3649902.3656493>

## Verification notes

- Titles, author lists, venues, pagination where stated, and DOIs were checked against publisher or
  author-hosted versions of the papers on 2026-09-01.
- The existing `references.bib` entry for `eyescrollr2024` had unrelated authors and DOI
  `10.3758/s13428-024-02385-5`, which resolves to *A natural language model to automate scoring of
  autobiographical memories*. The entry was corrected while adding this review.
- This review inspected five methodologically relevant papers. It is sufficient to bound the current
  claim, not to estimate field-wide reporting prevalence.
