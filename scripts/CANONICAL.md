# M4 feature streams and evidence boundaries

Checked 2026-09-04 against the producer code. Shared field names are not proof
that two models consume the same measurement.

| Role | Producer | Measurement and limits |
|---|---|---|
| Current cursor-only typed replay | [`m4_cursor_aoi_rerun.py`](m4_cursor_aoi_rerun.py) → [`m4_cursor_tracker.mjs`](m4_cursor_tracker.mjs) | Calls the actual sibling AR `ResultFeatureTracker`; native mousemove, document-space typed AOI centers, all main-axis AOIs, strict X+Y final-click labels, matched 0/500 ms windows. No gaze. Offline replay, without browser visibility gating or sample throttling. |
| LAB analysis stream | [`compute_cursor_approach_features.py`](compute_cursor_approach_features.py) | Fixations select rows and sampling times; distances are gaze–cursor distances; proximity dwell uses fixation duration. Active input to taxonomy, coupling, buffer grids and sensitivity analyses. |
| Historical cursor-only reconstruction | [`m4_nb21_hybrid_rerun.py`](m4_nb21_hybrid_rerun.py) | XPath observations plus linear fallback centers, positional mouse events, no buffered `organic_hybrid` option. Historical protocol, not the current AOI rerun. |
| Additional historical diagnostic | [`compute_lab_gaze_gated_features.py`](compute_lab_gaze_gated_features.py) | Gaze-dependent; its earlier diagnostic result must retain its own source and protocol. |

The new reader in `notebooks-v2/21_click_prediction.ipynb` reads
`scripts/output/m4_cursor_aoi/summary.json`, rejects smoke output and stale
source/substrate hashes, and separates pooled AUC from mean participant AUC.
The producer saves aggregates only and leaves existing LAB caches unchanged.

```sh
.venv/bin/python -m unittest discover -s scripts -p test_m4_cursor_aoi.py
.venv/bin/python scripts/m4_cursor_aoi_rerun.py
```

**A buffer must remove samples to test anything.** Read
`sampling_diagnostics` before interpreting equal buffered/unbuffered scores.
Removing `final_dist` and `retreat_dist` does not itself remove the terminal
approach from other features.

The previous table incorrectly described `m4_nb21_hybrid_rerun.py` as the
producer of the buffered-organic 0.847 headline and linked parity tests that
actually live in the sibling approach-retreat repository. Neither assertion
established the full protocol. See the [lineage audit](../docs/methodology/feature-extractor-lineage.md).

## Carousel cells: released snapshot and candidate

The released `typed_gapfill_cellsplit` export still reads the frozen May snapshot
through `probe_cellsplit_features.py`. The independent `aoi_fidelity.py` v2 check
now compares top/main counts per parent, retaining zeros and unresolved cases.
It does not certify card boundaries. `carousel_dom.py` is a candidate extractor
with original-screenshot fixtures and explicit rejection of layout mismatches;
it does not replace the export or alter M4 inputs. See the
[contract, evidence and adoption gate](../docs/methodology/carousel-dom-candidate.md).

`carousel_dom.py --register-screenshot` now adds conservative original-screenshot
border registration and emits a separate `candidate-cells.csv` audit adapter.
`carousel_match_report.py` compares it against a fixed audit cohort without dropping
missing/rejected trials. The registered sample matches 61/61 counts; six targeted
held-out spelling cases also pass. This is not yet the released export source.
See [registration rules and evidence](../docs/methodology/carousel-screenshot-registration.md).

`carousel_corpus.py` runs the frozen candidate against the complete metadata
inventory, keeping absent, rejected and alignment-excluded trials distinct.
`carousel_count_corpus.py` runs the separate numbered-link audit;
`summarize_carousel_corpus.py` joins their complete, hash-matched ledgers.
The full run admits 1,570/1,575 eligible top subdivisions with matching counts.
See [full-corpus evidence](../docs/methodology/carousel-full-corpus-validation.md)
and [the adoption contract](../docs/methodology/carousel-source-adoption.md).
The exporter now applies the canonical exclusion list before loading right-rail
rows; the frozen export itself remains unchanged.
