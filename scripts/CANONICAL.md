# M4 feature streams and evidence boundaries

Updated 2026-09-07 against the producer code and retained aggregates. Shared field names are not proof
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
.venv/bin/python -m unittest discover -s scripts -p 'test_m4_cursor*.py'
.venv/bin/python scripts/m4_cursor_aoi_rerun.py                                   # click-anchored reference
.venv/bin/python scripts/m4_cursor_aoi_rerun.py --anchor mousedown --buffers 0 250 500 1000 \
    --output-dir scripts/output/m4_cursor_aoi_mousedown \
    --feature-cache AdSERP/data/cursor-only-typed-features-mousedown.json           # press-anchored headline + grid
.venv/bin/python scripts/m4_cursor_aoi_rerun.py --anchor mousedown --sampling gaze-gated --buffers 0 500 \
    --output-dir scripts/output/m4_cursor_aoi_mousedown_gazegated \
    --feature-cache AdSERP/data/cursor-only-typed-features-mousedown-gazegated.json # §4.3 matched-row ceiling
.venv/bin/python scripts/m4_cursor_only_downstream.py                              # §4.2 / §4.3 / terciles / per-etype
.venv/bin/python scripts/ltr_cursor_only_nested_grades.py --no-lofo                # §4.6 with nested cursor-label generation
# Historical non-nested diagnostic only:
# .venv/bin/python scripts/ltr_cursor_only_four_grades.py
```

**Anchor the buffer at the press.** evtrack's final `click` row is a navigation
stamp a median ~1.4 s after the `mousedown` of the same press (`mouseup` and
`click` share coordinates; `blur` follows within 1 ms). A click-anchored buffer
below ~0.7 s removes no cursor samples. `--anchor mousedown` is the headline
protocol; `--anchor click` is kept as the reference run. `--window pre5|post5`
(fifth-fixation boundary) and `--downsample-hz` (greedy thinning) are the
time-window and sampling-rate ablations on the same protocol; `--sampling
gaze-gated` samples the cursor at fixation onsets for the §4.3 ceiling; `--flavor
organic|typed_gapfill` swaps the AOI map (organic = bbox organics only, organic
rank). The sidecar records which of those read fixations (`gaze_used_for`).

**A buffer must remove samples to test anything.** Read
`sampling_diagnostics` before interpreting equal buffered/unbuffered scores.
Removing `final_dist` and `retreat_dist` does not itself remove the terminal
approach from other features.

The previous table incorrectly described `m4_nb21_hybrid_rerun.py` as the
producer of the buffered-organic 0.847 headline and linked parity tests that
actually live in the sibling approach-retreat repository. Neither assertion
established the full protocol. See the [lineage audit](../docs/methodology/feature-extractor-lineage.md).

## Nested supervision in the ranking check (September 7)

The original `ltr_cursor_only_four_grades.py` precomputed one global LOSO
cursor-label vector, then reused it in outer ranker folds. Training grades for
participant Q could depend on the gaze labels of outer test participant P.
Its cursor-label uplift and cursor-label ranker ablations are non-nested
historical diagnostics. `ltr_cursor_only_nested_grades.py` instead generates
grades within each outer training partition, with inner participant-held-out
labelers and a fixed 0.5 threshold. It writes a separate aggregate and preserves
the original result. See the [audit and comparison](../docs/methodology/ltr-nested-label-audit.md).

## Matched window and sampling comparisons (September 7)

[`m4_cursor_matched_sensitivity.py`](m4_cursor_matched_sensitivity.py) replays
the September 6 sensitivities with the canonical producer and requires exact
agreement with their retained feature hashes. The producer acquired a flavor
option between the sensitivity runs and headline rerun; both producer hashes
are recorded, and feature equality is checked rather than assumed. Native
features must match the press-grid sidecar. The script then intersects whole
trials separately for the window and rate families, rejects any shared trial
with a different AOI/label lattice, and refits each condition with the same
participant folds. M1 is refit once on each family's common rows.

```sh
.venv/bin/python scripts/m4_cursor_matched_sensitivity.py
```

The default keeps regenerated per-record caches in a temporary directory and
writes only aggregates/hashes to `output/m4_cursor_matched_sensitivity/`.
`--cache-dir /private/tmp/m4-matched-cache` allows a resumable local run; that
scratch directory is not a distributable artifact. The original sensitivity
and headline outputs are preserved. The native cohort retains the headline's
1,000 ms eligibility gate; sensitivities retain their 500 ms gate before the
intersection. Comparisons therefore estimate effects within common eligibility,
not the full corpus. Window eligibility/boundaries use fixation times, even
though the predictors are cursor-only. Different window durations and residual
terminal approach remain possible explanations; small rate differences are
not an equivalence test. See the
[matched report](../docs/methodology/m4-matched-sensitivity.md).

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
