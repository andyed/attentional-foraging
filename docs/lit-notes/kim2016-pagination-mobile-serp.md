# Kim, Thomas, Sankaranarayana, Gedeon & Yoon (CIKM 2016) — Pagination vs Scrolling in Mobile Web Search

**Paper:** Pagination versus Scrolling in Mobile Web Search
**Authors:** Jaewon Kim (ANU), Paul Thomas (Microsoft), Ramesh Sankaranarayana (ANU), Tom Gedeon (ANU), Hwan-Jin Yoon (ANU)
**Venue:** CIKM '16, Indianapolis, October 24–28 2016, pp. 751–760
**DOI:** 10.1145/2983323.2983720
**PDF:** https://users.cecs.anu.edu.au/~Tom.Gedeon/pdfs/Pagination%20versus%20scrolling%20in%20mobile%20web%20search.pdf

## Setup

Controlled lab study on touch-enabled mobile phone comparing two viewport-control modes:
- **Horizontal pagination** (swipe to flip whole-page sets, "ereader-style") — one swipe brings all results 5–10 onscreen
- **Vertical scrolling** (the standard SERP affordance on mobile)

Within-subject; 47 participants; eye-tracker (Eyeworks, 70-px-diameter fixation radius, >100 ms duration threshold, 1920×1080 screen). Ten-result SERPs with one "target" relevant result placed at rank 1, 3, 5, 6, 8, or 10. Each result becomes its own AOI (10 AOIs per SERP).

## Key claims

1. **Per-AOI fixation duration depends on viewport-control mode.** Pagination produced significantly longer fixation duration on back-of-page targets (over the fold) — about 2.6 s more per-AOI on AOI-back when the target was on the back page; significant control-type × target-position interaction (F(1,261) = 4.62, p<0.05). Front-page AOIs collected ~2.4 s more fixation time under scrolling (F(1,261) = 6.84, p<0.01).

2. **Pagination = more attention to over-the-fold results, better search accuracy on those results.** Search accuracy on back-page targets was 77.8% with pagination vs 58.3% with scrolling (Δ = 19.45 pp, GLM with binomial p<0.05 on the target-position × control-type interaction).

3. **Scrolling-induced time is overhead, not productive examination.** When scroll duration is subtracted, the control-type effect on "time on SERPs" loses significance (Table 4). Implication: pagination shifts time from gestural overhead into per-AOI examination.

4. **Participants were not faster, not more accurate, and not more satisfied with vertical scrolling**, despite scrolling being the only viewport-control mode currently provided by all mobile search engines.

## Connection to our work

This is the most direct precedent for the §7 mobile-extension hint. Two specific bridges:

- **Per-AOI fixation duration as a function of viewport-control regime.** Our cursor-side claim — "the per-AOI episode primitive transfers to touch surfaces where viewport residence plays the role of proximity-dwell" — is *empirically supported* in the Kim et al. setting: they show per-link fixation duration is the signal that moves when viewport control changes, in an eye-tracked controlled experiment. We don't have to assert that residence is the mobile analog; Kim et al. measured it.

- **Over-the-fold deferral.** Their target-back × pagination accuracy result (77.8 vs 58.3%) is a direct demonstration that fold-crossing changes per-result deliberation outcomes, which is the same mechanism our deferred-class taxonomy formalizes for desktop. They observed the effect in fixation duration; we recover the analogous deliberation episode from cursor geometry. The mobile-extension story is "swap the residence sensor; keep the episode primitive."

## Why this is the right cite (vs alternatives)

- Lagun et al. SIGIR 2014 measures viewport time as a non-click examination signal but does it as a session-level scalar, not per-AOI. Kim 2016 is the per-AOI eye-tracked mobile precedent.
- Lagun & Lalmas WSDM 2016 is a graded sub-document engagement taxonomy (Bounce/Shallow/Deep/Complete) for news, not ranked-result lists.
- Jaewon Kim's later CHIIR 2020 paper (Alanazi, Sanderson, Bao, Kim — "The Impact of Ad Quality and Position on Mobile SERPs", DOI 10.1145/3343413.3377990) is the next-paper-cite for the ad-asymmetry framing in §5.3.3 (deferred to v2 / camera-ready).

## BibTeX

```bibtex
@inproceedings{kim2016pagination,
  author    = {Kim, Jaewon and Thomas, Paul and Sankaranarayana, Ramesh and Gedeon, Tom and Yoon, Hwan-Jin},
  title     = {Pagination versus Scrolling in Mobile Web Search},
  booktitle = {Proceedings of the 25th ACM International on Conference on Information and Knowledge Management (CIKM '16)},
  year      = {2016},
  pages     = {751--760},
  publisher = {ACM},
  address   = {New York, NY, USA},
  doi       = {10.1145/2983323.2983720},
}
```
