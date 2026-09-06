# Carousel match improvement with screenshot registration

**Full-corpus follow-up:** see [the 2,776-trial validation](carousel-full-corpus-validation.md)
for current coverage, explicit rejected cases, and the source-adoption contract.

**2026-09-04, candidate v2 — LAB / AdSERP / typed parents.** On the fixed
61-trial top-carousel cohort from the retained 120-trial audit, the frozen
cellsplit matches **19/61 counts (31.1%)**. The new candidate matches **61/61**,
with **279 visible cards** and screenshot-border support for every card. No
candidate trial was omitted from the denominator. This is a development-sample
result, not a full-corpus accuracy estimate or semantic identity validation.

Sources: [before/after comparison](../evidence/carousel-2026-09-04/registration/comparison.json),
[separate candidate-CSV audit](../evidence/carousel-2026-09-04/registration/candidate-audit.json.meta.json),
and [complete candidate report](../evidence/carousel-2026-09-04/registration/cohort.json).
The released `typed_gapfill_cellsplit` CSV and downstream model results have not
been replaced. Its historical counts remain the baseline, not the new result.

## What improved

The DOM candidate recovers complete product cards missed or over-split by the
frozen snapshot. Screenshot checks then resolve a separate layout problem.
Three cohort pages (`p006-b5-t2`, `p040-b4-t3`, `p048-b3-t6`) contain a spelling
suggestion in both raw and cached HTML that the original screenshot lacks.
The module adds 43.265625 document CSS pixels before the carousel. A read-only
probe that removes it in the ephemeral DOM removes exactly that offset; changing
the viewport width does not. The original capture code responsible for the
absence remains unlocated, so the pipeline does not globally delete that module.

Instead, `carousel_screenshot.py` detects card-border strokes in the **original
screenshot**, without using DOM counts or typed boxes to generate those outlines.
Matching multiple outlines permits a single vertical translation for the
carousel. The three large accepted corrections are about **−38.4 screenshot
pixels**; the other cohort shifts are below one pixel. Raw geometry is retained
alongside `aligned_visible_rect_screenshot`, with the supporting outlines,
translation, and border scores recorded per parent.

The existing window-width X conversion is retained. Registration does not fit
an X scale, card width, card height, or independent per-card offsets to make boxes
agree. It does not use clicks, gaze, labels, model performance, or old cell counts.

## Acceptance rules

- Require at least two closed card outlines and at least 60% of visible cards
  as anchors. Their X/width/height must agree within three pixels; their vertical
  offsets must agree within two pixels and remain within an 80-pixel search bound.
- After the shared shift, **every visible card** must have top and bottom stroke
  support of at least 85%, plus at least one vertical edge supported at 70%.
  Rounded corners and subpixel rasterization have explicit allowances.
- Refuse ambiguous matching, inconsistent offsets, unsupported border styles,
  missing outlines, and previously unresolved DOM parent assignments.
- Check the full projected DOM parent/clip width for extra same-row outlines,
  including open/clipped leading and trailing cards. A missed last card cannot
  be hidden by limiting validation to the extracted cells' envelope.
- Clear prior aligned geometry before each attempt. Failed repeat calls cannot
  reuse formerly accepted boxes.

The stroke detector is deliberately specific to the captured Google card
outline style. Border support establishes geometry, not product-content identity,
pixel-level occlusion, browsing-time exposure, or generality to other templates.
Unknown cases remain rejected. The original-screenshot color/stroke search is
separate from the numbered-link count auditor, but both consume the same saved
page corpus; neither is a blind external benchmark.

## Checks beyond the development cohort

Eight original-screenshot fixtures now retain manually reviewed border rectangles
at a three-pixel tolerance. The three shifted cases still fail the **raw** check
and pass the registered check; those failures were repaired, not relabeled as
successful raw extractions.

An independent reviewer selected six additional spelling-mismatch pages outside
the development cohort and supplied original-screenshot visible counts before
seeing the registration results: **5, 5, 5, 4, 5, 5**. All six match those counts
and pass screenshot registration with the same thresholds. These are targeted
held-out cases, not a random sample or proof of corpus-wide reliability.
[Held-out validation](../evidence/carousel-2026-09-04/registration/heldout-validation.json)
records screenshot and candidate hashes.

The combined regression suite passes **94 tests** across DOM clipping/identity,
count-audit denominators, screenshot registration, and fixed-cohort comparisons.
Tests specifically reject inconsistent card shifts, missing borders, ambiguous
outlines, omitted clipped edge cards, stale accepted geometry, duplicate reference
IDs, and failures disappearing from the denominator.

## Reproduce and inspect

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts .venv/bin/python -m unittest \
  test_aoi_fidelity test_carousel_dom test_carousel_screenshot test_carousel_match_report

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/carousel_dom.py \
  --register-screenshot --trials-file scripts/fixtures/carousel_sample61.json \
  --out /tmp/carousel-registered

.venv/bin/python scripts/carousel_match_report.py \
  --reference docs/evidence/carousel-2026-09-04/audit-retained120.json \
  --candidate /tmp/carousel-registered/report.json \
  --out /tmp/carousel-registered/comparison.json
```

Omit `--trials-file` to run the eight screenshot fixtures. Omit
`--register-screenshot` to retain the raw extraction/rejection experiment.
`aoi_fidelity.py --cellsplit <path>` can independently audit a candidate export;
its default still selects the released snapshot. Use the same fixed trial list
when comparing exports.

`candidate-cells.csv` is an **audit adapter**, not the full released enrichment
schema. It contains only candidate top parents/cards and explicitly names its
geometry source. Parent bounds remain unchanged from the tight typed source.
Only admitted candidate cards are emitted; rejected subdivisions retain their
parent rows when resolved, while missing/ambiguous parents remain in the JSON
failure ledger and the audit's missing-export accounting. No legacy cells or
unobserved gaps are substituted.

## Remaining adoption gate

The [full-corpus candidate and independent audit](carousel-full-corpus-validation.md)
are complete, with unsupported single-card cases retained and an eight-page
content-order review. Click-target validation and the explicit
[versioned-source adoption](carousel-source-adoption.md) remain before rederiving
cell-dependent notebook figures and claims. The
M4 parent-AOI replay and shared coordinate loader remain separate experiments.
