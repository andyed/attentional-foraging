# MRC Viewable Ad Impression Measurement Guidelines (Desktop)

**Document:** MRC Viewable Ad Impression Measurement Guidelines (Desktop)
**Version:** 2.0 (Final with 2015 additions), published August 18, 2015 (v1.0 originally June 30, 2014)
**Authority:** Media Rating Council, prepared in collaboration with IAB Emerging Innovations Task Force
**PDF:** https://www.mediaratingcouncil.org/sites/default/files/Standards/081815%20Viewable%20Ad%20Impression%20Guideline_v2.0_Final.pdf

## The core rule

A Viewable Display Ad Impression is counted when **both** criteria are met:

1. **Pixel Requirement** — ≥ 50% of the ad's pixels are on an in-focus browser tab within the viewable browser space.
2. **Time Requirement** — the pixel requirement is met for ≥ 1 continuous second, post ad render.

For digital video: ≥ 50% pixels for ≥ 2 continuous seconds.

Ordering is specified: pixel threshold must be met *first*, then the clock starts on the time threshold. Time accumulates only while pixel threshold is continuously satisfied — a continuous-window rule, not a cumulative one.

## What viewable does and doesn't mean

- "Viewable" = "opportunity to see," not confirmed attention. The doc is explicit: "It is recognized that an 'opportunity to see' the ad exists with a viewable ad impression."
- Mouseover is **not** a sufficient bypass for the viewability requirement (it doesn't substitute for the 50%/1s rule). A legitimate click does count as a "strong user interaction" that overrides the threshold; mouseover does not.
- Ads vs containers: measurement of the ad itself is preferred over measurement of the container (I-Frame); container-based measurement is acceptable only when shown not to introduce material counting differences.

## Connection to our work

This is the deployed industrial baseline for "per-AOI residence with a binary temporal threshold" on the ad-tech side. Three concrete bridges:

- **The per-AOI residence frame.** MRC's 50%-pixels / 1-continuous-second rule is, structurally, a per-AOI dwell-with-threshold metric: it commits one threshold, applied identically to every ad slot, with a binary in/out output. Our seven-feature M4 generalizes the same per-AOI residence frame to: (a) graded ordinal output (clicked / deferred / eval-rejected / not-approached), (b) cursor-derivative-ordered features over the AOI-relative distance function rather than pixel-overlap, and (c) a deliberation-window restriction rather than continuous-window accumulation.

- **The continuous-window rule motivates the deliberation phase.** MRC requires the pixel threshold to hold *continuously* for the time threshold to accumulate. Our §3 deliberation-phase windowing (the post-fifth-fixation window) is an analogous commitment: the signal-bearing time interval is bounded by a behavioral gate. The methods agree that residence has to be conditioned on something — they pick browser-side pixel-visibility; we pick fixation-phase + AOI proximity.

- **Mouseover-not-sufficient is the precise gap we fill.** MRC explicitly rules out mouseover as a viewability bypass. Our cursor episodes are *not* mouseover-as-viewability — they are a richer, per-result deliberation episode with derivative-ordered geometry. The MRC standard refuses the binary substitution; we offer the multi-feature alternative.

## Why this is camera-ready / v2 material

The MRC cite would anchor the §6/§7 mobile-extension paragraph against the deployed industrial standard, which strengthens the framing of the work as a graded extension of a binary baseline that everyone in ad-tech already runs. It is a *positioning* citation, not a method dependency — adding it carries one bib entry and one sentence of body prose. Defer to camera-ready or v2 to avoid last-night page-count surprises.

## BibTeX (stub — verify URL stability before camera-ready)

```bibtex
@techreport{mrc2015viewable,
  author      = {{Media Rating Council}},
  title       = {{MRC} Viewable Ad Impression Measurement Guidelines (Desktop), Version 2.0},
  institution = {Media Rating Council, in collaboration with {IAB} Emerging Innovations Task Force},
  year        = {2015},
  month       = {8},
  note        = {Originally published as v1.0, June 30, 2014. URL: \url{https://www.mediaratingcouncil.org/sites/default/files/Standards/081815\%20Viewable\%20Ad\%20Impression\%20Guideline_v2.0_Final.pdf}},
}
```
