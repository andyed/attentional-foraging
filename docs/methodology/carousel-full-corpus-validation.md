# Full-corpus carousel validation

**2026-09-04 — LAB / AdSERP / typed parents with candidate top cells.**
The frozen screenshot-registration candidate was run on all **2,776 trials**.
On the same **1,575 eligible top-parent comparisons**, the released snapshot
matches **465/1,575 counts (29.5%)**; the registered candidate admits
**1,570/1,575 matching subdivisions (99.68%)**, containing **7,265 cards**.
The **5 rejected trials remain in that denominator**. Count agreement and
screenshot-border support are separate checks; neither establishes product correctness.

[Comparison and per-trial ledger](../evidence/carousel-2026-09-04/corpus/comparison.json)
· [compressed candidate report](../evidence/carousel-2026-09-04/corpus/candidate-report.json.gz)
· [independent count measurements](../evidence/carousel-2026-09-04/corpus/count-audit.json.gz).

## Population and outcomes

| Population | Trials |
|---|---:|
| Requested metadata inventory | 2,776 |
| Existing alignment exclusions, measured but never admitted | 12 |
| Eligible trials | 2,764 |
| Eligible, confirmed no top carousel | 1,189 |
| Eligible top-parent comparisons | 1,575 |
| Accepted, count-matching candidate subdivisions | 1,570 |
| Rejected subdivisions, retained as zero admitted cells | 5 |
| Eligible unresolved top presence | 0 |

Raw typed maps contain 1,582 top parents; seven belong to the existing exclusion
list. The eligible top count is therefore 1,575, not the historical 1,581 or the
current 1,572-row NB23 sequence file. Each measured page has exactly one top
parent when present. Excluded trials do not appear in the candidate CSV.

The independent numbered-link audit finds **7,274 visible cards** in eligible
top parents. The old source is short on **956 parents** and over on
**154**, with 465 count matches. Every admitted candidate card has
original-screenshot border support. **79 eligible accepted pages** require a
vertical correction larger than three pixels; the registration thresholds and
producer bytes were unchanged from the earlier 61-trial evaluation.
The comparison includes results by participant and visible-card count.

## Explicit unsupported cases

| Trial | Visible cards | Rejection reason |
|---|---:|---|
| `p017-b5-t8` | 1 | unresolved_parent_or_too_few_cards |
| `p033-b3-t2` | 1 | unresolved_parent_or_too_few_cards |
| `p035-b3-t10` | 1 | unresolved_parent_or_too_few_cards |
| `p042-b2-t8` | 5 | visible_card_border_mismatch |
| `p044-b4-t6` | 1 | unresolved_parent_or_too_few_cards |

The first two inspected examples contain one genuine full-width product card:
Heinz Oxtail Soup and a Rule automatic float switch. Their raw DOM rectangles
visually follow the original screenshot cards. The current validator requires
at least two card outlines to establish a shared translation, so these remain
unadmitted. A third single-card example is a Schmidt puzzle mat.
Manual inspection is not an override, and the candidate export does not
substitute an old cell or the whole parent box.

`p042-b2-t8` is a different rejection: all five lower card borders fail after
registration. The recorded document height is 3,141 CSS pixels but the full-page
PNG is 2,846 pixels high, giving a Y factor of 0.90608 rather than approximately
0.900. This predicts 291.758-pixel card height; independent screenshot outlines
measure 290 pixels. Applying the width/window factor diagnostically gives
289.845 pixels. A shared vertical shift cannot correct this scale discrepancy.
A separate [diagnostic projection](../evidence/carousel-2026-09-04/corpus/height-scale-diagnostic.json)
using that independently derived width/window factor passes all five cards with
the same registration thresholds. This supports repairing the coordinate-frame
derivation, not widening the border tolerance. No Y-scale rule or threshold
was changed in the frozen corpus run; its rejection remains in the denominator.

The corpus contains no eligible positive-area partially clipped cards under this
candidate's DOM clipping rule. Clipped-edge handling remains covered by synthetic
regressions, not by an observed partial-card stratum in this run. Arrow occlusion
and a genuinely clipped card are different conditions.

## Independent checks and limits

A separate reviewer preselected eight new pages across participants, card heights,
spelling conditions and parent positions before looking at candidate outcomes.
All **34 visible cards** match the captured text and card order, and all eight
complete corpus records exactly match the independent frozen invocation.
[Review and limits](../evidence/carousel-2026-09-04/corpus/semantic-review.md)
retain truncated product labels, source image/title inconsistencies and an explicit
correction to one album-cover reading. Merchant destinations and SKU identity
were not validated. This eight-page review is not a corpus-wide identity estimate.

All existing eight screenshot fixtures and the six targeted spelling holdouts
also pass against the full-run records. **109 focused tests pass**: 94 existing
carousel checks, three exporter-exclusion regressions, and 12 corpus-comparison
regressions. The comparison refuses incomplete/duplicate cohorts, missing or
changed input provenance, altered parent grain, rejected-cell leakage and
inconsistent accepted geometry. Unknown parent presence cannot become absence.
[Validation manifest](../evidence/carousel-2026-09-04/corpus/validation.json).

## What changed and what comes next

Added resumable corpus measurement, an independent count pass, a fixed-inventory
comparison and reproducible evidence. Also repaired the existing exporter so
all 12 canonical alignment exclusions apply before either main or right-rail
rows can be loaded. Eligible right-only trials still export; parent fields are
preserved. **No released CSV, notebook result, model output or public release was
regenerated by this work.**

First resolve the singleton-validation policy and the recorded-height Y-scale
discrepancy, with the current rejections retained as regression fixtures. Then
implement an explicitly versioned top-cell source, pinned to
the current typed/gapfill parent baseline. It must expose unsupported cases,
carry identity and raw/registered geometry, and avoid fallback to frozen cells.
The old cellsplit CSV's parent rows already differ from the current gapfill
export, so filtering its parents does not recover today's baseline.

NB23 and NB25 call the snapshot loader directly. They need coordinated source
selection, one-based analysis positions, explicit screenshot-space clicks,
matched populations and source-pinned outputs. NB25 also loads legacy parent
boxes and has an X-ignoring fallback. Simply replacing a CSV would leave the
behavioral claims stale. The [adoption contract](carousel-source-adoption.md)
records these requirements; M4's parent-AOI replay remains a separate protocol.

## Reproduce

Run from the attentional-foraging checkout with its pinned Python environment:

```sh
AF_ROOT="$PWD" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/carousel_corpus.py \
  --root "$PWD" --out /tmp/carousel-corpus --workers 4
AF_ROOT="$PWD" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/carousel_count_corpus.py \
  --out /tmp/carousel-count-audit --workers 4
.venv/bin/python scripts/summarize_carousel_corpus.py \
  --candidate /tmp/carousel-corpus/report.json \
  --reference /tmp/carousel-count-audit/report.json \
  --candidate-csv /tmp/carousel-corpus/candidate-cells.csv \
  --out /tmp/carousel-comparison.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts .venv/bin/python -m unittest \
  test_aoi_fidelity test_carousel_dom test_carousel_screenshot \
  test_carousel_match_report test_export_aois_by_trial_id test_carousel_corpus_summary
```

Both passes retain per-trial checkpoints and verify source/runtime/cohort hashes
before resuming; existing input bytes must still match. Browser requests to
HTTP(S) are blocked. Raw HTML fallback, screenshot, metadata and typed-map hashes
are recorded per trial. The registered CSV is an audit adapter with only top
parents/cells; it is not the released enrichment schema. Compressed evidence
preserves the original report/CSV bytes, whose uncompressed hashes are in the
comparison and candidate report.
