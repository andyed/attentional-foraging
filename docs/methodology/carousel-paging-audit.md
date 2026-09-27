# Carousel paging audit, keyed on the clicked element (2026-09-26)

**Producer:** `scripts/audit_carousel_paging.py`. **Tests:** `scripts/test_audit_carousel_paging.py`
(a fixture page where a hidden-tail card is clicked; the audit must flag it).
**Output:** `docs/evidence/carousel-paging-2026-09-26/audit.json`.
**Inputs:** evtrack click rows (`AdSERP/data/mouse-movement-data`), captured HTML
(`AdSERP/data/serps-cached`), and the DOM candidate report
(`docs/evidence/carousel-2026-09-04/corpus/candidate-report.json.gz`), which lists every
card in each top-ads carousel, hidden tail included, with its load-time visible fraction.

## Why it was re-run

The 2026-08-30 zero-paging figure (272 of 272 cell clicks inside the visible strip;
crforager `docs/notes/carousel-paging-and-scent-2026-08-30.md`) assigned clicks to cells
by screen position. A click inside the visible strip is visible by construction, so that
check could not have detected paging. This was the open "selector scope" item in the
AllSERP v4 draft.

## Method

evtrack records an xpath for every click, anchored on an element id. Each of the 2,889
click events is resolved against the trial's captured HTML and classified by the element
it hit: a product card inside `.commercial-unit-desktop-top`, other top-unit content, a
carousel paging control (`g-left-button` / `g-right-button`), or a right-rail shopping
card (out of scope). A top-unit card is joined to the DOM report by its `vplaurlgN` id.

## Result

| | count |
|---|--:|
| click events scanned | 2,889 |
| clicks on a top-ads carousel card | 281 (275 trials) |
| of those, card visible at page load | **281** |
| of those, card hidden or partly clipped at load | **0** |
| clicks on top-unit whitespace (no card) | 5 |
| paging-control clicks, any carousel | 3 |
| paging-control clicks on the top-ads carousel | 1 (p006-b6-t10) |
| right-rail shopping-card clicks (excluded) | 96 |
| xpaths that do not resolve in the captured HTML | 67 |

Clicked cards by DOM order: 0: 75, 1: 78, 2: 61, 3: 39, 4: 28. No clicked card sits at or
beyond its carousel's visible-card count.

**Paging did occur, and converted nothing.** In p006-b6-t10 the participant pressed Next,
then about 21 s later clicked card 2, which was on screen at load; the click lands at
card 2's load-time position, so the strip was back at its starting offset. The other two
Next clicks are on non-ad carousels with no product cards.

**The 67 unresolved clicks cannot be carousel clicks.** All are anchored on `#rso`, the
organic container, and none of those trials places a top-ads unit inside `#rso`.

## What it settles

Visible-at-load is the right exposure definition for the DOM-derived cell layer: no click
in the corpus landed on a card that was not on screen when the page loaded. It does not
measure paging frequency. Horizontal wheel or trackpad paging leaves no click, and the
one recorded Next press shows paging happens without converting.
