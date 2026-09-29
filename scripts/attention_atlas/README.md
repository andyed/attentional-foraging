# Attention atlas producers

The repository owns the two posters in `docs/visualizations/`. Scripts resolve
paths from this checkout. `AF_ATLAS_DIR` points every read and write at a copy
of the atlas for an isolated rebuild; provenance paths in the outputs still
name the canonical location, so a rebuilt copy produces the same summaries.
Use `.venv/bin/python` from the [canonical environment](../../docs/canonical-environment.md).

## Layout

| File | Role |
| --- | --- |
| `atlas_core.py` | Every shared measurement rule, once: trial reconstruction, cursor hold and interpolation, occupancy intervals, joint states, visits, matching, sequence counts, common coverage, bootstrap. Named constants; no side effects on import. |
| `compute-information-space.py` | Time budgets by AOI, fold, motion and click target. Gates: clock conservation, prior target-overlap baseline. |
| `compute-resting-cursor.py` | Cursor rest with gaze elsewhere, by threshold and denominator, plus two cursor-hold sensitivities. Gate: information-space totals. |
| `compute-gaze-cursor-echo.py` | Visits, first entries, matched pairs, pauses, the illustrated example. Gate: five resting-cursor totals. |
| `check-gaze-cursor-echo.py` | From saved records only: common-coverage rates, clock-boundary and clock-origin sensitivities, example-rule prevalence, pair integrity. |
| `page_values.py` | Every number displayed in the pages, posters and entry-point prose, formatted once from the JSON. |
| `render-*.py`, `build-*-page.py`, `build-index.py` | Posters (PDF, SVG, PNG, crops) and linked HTML; text comes from `page_values`. |
| `verify-atlas.py` | Verification from saved evidence (see below); `--pin` records the evidence values. |
| `provenance/compute-final-approach.py` | Byte-identical record of the script that produced the saved cohort and prior baseline in `evidence/final-approach/`; read, never run (see its README). |

Gates are explicit checks that exit non-zero with a message (not `assert`,
which `python -O` removes). Outputs contain no timings or absolute paths, and
per-trial records are gzip JSON with a zero timestamp, so an unchanged rebuild
produces unchanged files. PNG exports are byte-reproducible on a machine with
Arial; PDF and SVG exports carry no creation date and use fixed SVG ids.

## Full rebuild from raw recordings

Needs the AdSERP recordings and the full-page screenshots (the latter are a
symlink to an external volume on the development machine; producers stop with
an explicit message if the screenshot geometry is unavailable). About four
minutes:

```sh
cd scripts/attention_atlas
../../.venv/bin/python compute-information-space.py
../../.venv/bin/python compute-resting-cursor.py
../../.venv/bin/python compute-gaze-cursor-echo.py
../../.venv/bin/python check-gaze-cursor-echo.py
../../.venv/bin/python render-gaze-cursor-echo.py
../../.venv/bin/python build-gaze-cursor-echo-page.py
../../.venv/bin/python render-information-space.py
../../.venv/bin/python build-information-space-page.py
../../.venv/bin/python build-index.py
../../.venv/bin/python verify-atlas.py
```

Run in this order. The saved `evidence/final-approach/trial-summary.csv` fixes
cohort membership, press times and final-approach onsets; do not silently revise
cohort membership or the saved baselines to pass a gate. To rebuild in
isolation, copy `docs/visualizations` elsewhere and set `AF_ATLAS_DIR` to the copy.

## Verification and pinning

`verify-atlas.py` reads no raw data. It checks local HTML links and anchors
(and that no page links to a file the website copy leaves out), Markdown links
in the entry points, clock conservation for every trial, aggregate
reproduction, the prior baseline and every gate in both directions, a
recomputation of the common-coverage counts, that the numbers in the pages and
the README match the JSON, and that the shipped values match
`docs/visualizations/evidence-pin.json`.

The pin covers the numeric content of every summary and per-trial record,
excluding provenance hashes. An unchanged rebuild passes. A deliberate change
to a measurement rule changes shipped values and fails verification until it
is reviewed and re-pinned:

```sh
../../.venv/bin/python verify-atlas.py --pin
```

Re-pinning is a substrate event: rebuild pages and posters, update prose that
quotes the moved numbers, and record the change in the commit message.

Tests: `.venv/bin/python -m unittest discover -s scripts -p test_attention_atlas.py`
covers the core rules on synthetic inputs (including matching against
exhaustive search) and runs the verifier on a copy of the shipped atlas.

The `build-gh-pages.js` site builder copies the pages, figures and summaries;
per-trial records, Markdown and build manifests stay in the repository.
Rebuilding the site and publishing it are separate operations.
