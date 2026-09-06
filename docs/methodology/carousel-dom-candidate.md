# Carousel repair: audit and screenshot fixtures

**Follow-up:** [screenshot-registered candidate v2](carousel-screenshot-registration.md)
now matches 61/61 counts on the fixed comparison cohort (frozen export: 19/61),
with screenshot-border support and three repaired layout shifts. Six targeted
held-out cases also pass. The released cells and model results remain unchanged.
The initial v1 evidence below is retained to show what the raw geometry missed.

Status: **candidate extraction, 2026-09-04**. Regime: **LAB, AdSERP**;
parent flavor: **typed**; comparison export: **typed_gapfill_cellsplit**, frozen
2026-05-24 cell snapshot. This increment does not replace that export or rederive
NB23/NB25, ranking models, or the M4 parent-AOI replay.

## Why the old score is retired

The original cell audit compared all exported cells (including organic and
right-rail cells) with numbered product links. It used one clipping ancestor,
merged equal numeric IDs across parents, omitted zero/missing comparisons, and
could count fully left-clipped or hidden elements. The historical full-corpus
451/1,551 (29.1%) and sample 18/58 (31.0%) are **not valid current top-carousel
fidelity estimates**. They remain historical records, not targets to optimize.

The repaired `scripts/aoi_fidelity.py` compares top/main cells per parent.
It retains explicit absent, missing-export, and unresolved states, distinguishes
known right-rail product links from unsupported layouts, and counts any positive
visible card area after ancestor clipping. An empty exported subdivision counts
as zero; it cannot disappear from a DOM-positive comparison. Ambiguous parents,
duplicate identities/indices, malformed boxes, and unreadable inputs are reported.
A matching count is **not** evidence of correct identity or boundaries.

On the exact retained 120-trial sample, the corrected audit reports **19/61
parent comparisons with matching counts (31.1%)**, with **37 short and 5 over**.
The remaining **59 trials have no top-carousel comparison**, with **0 unresolved**
and **0 missing trial exports**. A present parent with no cells is not a missing
trial export. Source: [sample metadata](../evidence/carousel-2026-09-04/audit-retained120.json.meta.json)
and [all sample rows](../evidence/carousel-2026-09-04/audit-retained120.json).
This is a sample diagnostic, not a new full-corpus rate or a per-card accuracy.

## Candidate contract

`scripts/carousel_dom.py` enumerates full `.pla-unit` cards under each
`.commercial-unit-desktop-top` parent. Numbered image links establish product
identity; they do not define the card rectangle. A recognized terminal
comparison-service directory is recorded separately from product cards.
Each card retains its DOM identity/order, visible index, raw rectangle, clipped
rectangle, and visible fraction. No midpoint expansion is applied, including
at the first/last card or across unknown space.

The captured horizontal viewport and all overflow-clipping ancestors bound the
visible rectangle. Below-fold cards remain eligible in the full-page snapshot.
This is rectangular clipping, not pixel-level occlusion (e.g. navigation arrows),
gaze exposure, or evidence of horizontal paging during the trial.

Existing `ad_only` typed top parents have null HTML handles. The candidate preserves
that fact, records a separate browser-derived DOM handle, and binds only a unique
parent with sufficient overlapping area. That association is a binding check,
not geometry validation; ambiguous, duplicate and missing matches are unresolved.
Input HTML, metadata, screenshots and typed maps are hashed. The output records
extractor/fixture hashes, browser versions, viewport and coordinate model.

## Independent screenshot checks

The fixture manifest (`scripts/fixtures/carousel_dom_cases.json`) contains manually
reviewed border rectangles from **original** AdSERP screenshots, not rectangles
copied from the producer. Six examples cover legacy short, over and matching
counts. The acceptance tolerance is **3 screenshot pixels per edge**.

| Trial | Original visible cards | Frozen export cells | Candidate outcome |
|---|---:|---:|---|
| p005-b2-t1 | 5 | 4 | accepted |
| p006-b2-t9 | 5 | 4 | accepted |
| p004-b5-t7 | 3 | 5 | accepted |
| p022-b2-t4 | 3 | 4 | accepted |
| p006-b5-t2 | 5 | 5 | rejected: screenshot layout mismatch |
| p011-b1-t1 | 4 | 4 | accepted |

Source: [candidate report](../evidence/carousel-2026-09-04/candidate.json).
Five accepted fixtures plus one expected rejection are six successful checks;
**they are not six validated extractions** or a representative accuracy estimate.
The rejected page renders a “Did you mean” block absent from the original
screenshot, shifting all cards down about 39 screenshot pixels. It is deliberately
retained as a negative control: count agreement cannot admit those boxes.

The overlays also exposed an X conversion issue. On these fixtures, screenshot
width / recorded **window** width matches the card borders; screenshot width /
recorded **document** width inflates X, reaching about 9 pixels at the fifth card.
The candidate uses the former for X, and screenshot height / document height for
Y. Both X ratios are recorded. This evidence is limited to these fixtures; shared
loaders, historical AOI-audit ratios, model inputs and prior results are unchanged.
A broader coordinate validation is required before adopting it corpus-wide.

## Reproduce

Run from the attentional-foraging checkout with local AdSERP files present:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s scripts -p 'test_*carousel_dom.py'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s scripts -p 'test_aoi_fidelity.py'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/carousel_dom.py --out /tmp/carousel-review
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/aoi_fidelity.py --json /tmp/aoi-fidelity.json
```

The candidate command writes a report and screenshot overlays. It exits nonzero
for an unexpected fixture outcome or unresolved extraction; the documented
negative control is expected to be rejected. The audit writes one row per requested
trial plus a provenance/denominator sidecar. Both browser paths block HTTP(S).
The published sample uses the exact trial list in the retained sample rows; the
default sample is derived from the current sorted HTML-map inventory.

## Gate before replacing the released cells

1. Extend the independent screenshot set to other layouts and partial cards;
   resolve captured-HTML/screenshot mismatches without fitting them to old boxes.
2. Validate the recorded-window X model beyond these fixtures and audit original
   click targets. Keep coordinate/model changes separately attributable.
3. Run the repaired audit over the corpus, report unsupported and excluded cases,
   then produce a versioned cell source through the existing build/export entry.
4. Preserve the corrected typed parent rows exactly; keep optional gap attribution
   separate from measured card geometry and never absorb unobserved tail space.
5. Recompute cell-dependent NB23/NB25 summaries, composition figures and ranking
   consumers, then update AllSERP's per-cell claims from the new outputs.
