# Preselected card-content correspondence check

**Full-run follow-up:** all eight completed corpus records exactly match the
independent invocation; see `semantic-corpus-comparison.json`. The original
review timing and blind annotations below are retained.

Eight trials were selected by a fixed SHA256 seed within typed-map height,
spelling-block and parent-position strata, with eight different participants.
Prior 61-trial and six-trial visual sets and alignment exclusions were removed.
Selection and blind annotations were frozen before candidate outcomes were read.
No source or threshold was changed during this check.

| Trial | Blind visible count | Frozen candidate count | Registered Y shift (px) |
|---|---:|---:|---:|
| p016-b3-t1 | 5 | 5 | -0.4175 |
| p046-b1-t1 | 5 | 5 | -38.4666 |
| p030-b6-t4 | 3 | 3 | -38.4143 |
| p048-b4-t8 | 5 | 5 | +0.4659 |
| p040-b5-t10 | 5 | 5 | +0.4647 |
| p009-b6-t4 | 5 | 5 | +0.4748 |
| p032-b2-t5 | 3 | 3 | +0.5252 |
| p014-b3-t4 | 3 | 3 | +0.5140 |

All eight frozen extractions were accepted. The 34 visible card IDs occur in
the order identified from original screenshots; raw and cached HTML text/order
agree. Captured titles, prices, merchants and product-image order correspond
to the DOM cards. The two spelling pages alone need a large translation.
Original source-image thumbnails were decoded with their alpha channel and
composited on white for the contact-sheet comparison.

This is **captured-card correspondence**, not validation of product correctness,
SKU identity, query relevance, merchant landing pages or the entire corpus.
Two explicit limitations remain:

- In p009-b6-t4, the first two lamp subtype titles are truncated in the original
  screenshot and have the same price; their rendered images and DOM labels
  preserve the source order, but the exact subtype cannot be independently read
  from the screenshot title alone.
- In p014-b3-t4, the first cover reads **Liszt** and the second **Journey**,
  whereas the query and first title refer to Daniel O'Donnell. The same images
  occur in the original screenshot and replayed HTML. This is a source content
  inconsistency, not extractor reordering. An initial quick reading called the
  second cover Chopin; `blind-annotation-erratum.json` corrects that explicitly
  while preserving the original blind-annotation hash.

At this check, corpus records were available for p009-b6-t4, p014-b3-t4 and
p016-b3-t1. Their status, input hashes, cell IDs, raw/registered rectangles and
registration diagnostics exactly match the independent frozen invocation.
The other five were validated with the same frozen source in a separate local
run; their corpus records were not yet available. Do not call this eight
completed corpus comparisons until those records are checked.

Evidence: `semantic-preselection.json`, `blind-source-evidence.json`,
`blind-semantic-annotations.json`, `blind-annotation-erratum.json`,
`semantic-extraction.json`, `semantic-review-results.json`, the eight
`*-original-carousel.png` crops and `rendered-source-images-contact.png`.
The extractor and registration hashes match the full-corpus manifest:
`9596f492a167d388479d508e6c1522f960106744a54ef48a69f44c467c22cab2` and
`85a9df2c866e80ff70da55f048dd4bd7630eedf9cc30425ec40813f67c71da30`.

## Separately inspected unsupported single-card template

p017-b5-t8 was reported by the corpus run, not part of the preselected eight.
The original screenshot visibly contains one full-width Heinz Oxtail Soup 400g
card, with EUR 2.81 / GBP 2.39 and British Essentials text matching saved HTML.
The raw candidate rectangle visually follows this card's borders. Its rejection
as `unresolved_parent_or_too_few_cards` is consistent with the frozen minimum
of two anchors. This manual observation is **not an admission override**;
keep it in unsupported single-card coverage for this run.

Original screenshot SHA256:
`c3f7b3af96d725105b69cc569b1bcc4c4a6ee30d11ee8184f1a14b02be9d8e14`.
Cached HTML SHA256:
`81ac8d568769f7e3de5831a5654a81e13f664dd3d61ba310d283b02ddaf7f2c8`.
