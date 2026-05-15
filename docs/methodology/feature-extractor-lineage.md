# Feature-extractor lineage (cursor approach features)

The CIKM "Leaky Cursor" paper's headline cursor-approach features are produced by
**one canonical pipeline**, with one diagnostic variant and one superseded
predecessor that share function names with the canonical one. This file exists
because anchoring on a non-canonical extractor is a documented failure mode — see
[`docs/drafts/cikm-2026/process-trace-gaze-sync-missed.md`](../drafts/cikm-2026/process-trace-gaze-sync-missed.md).

## Canonical — use for paper claims

**Production / WILD-deployable extractor (JS):**
[`approach-retreat/src/approach-retreat.js`](../../../approach-retreat/src/approach-retreat.js)
— `ResultFeatureTracker` class, released as the `approach-retreat` library
(currently **v0.3.0**). Pure cursor / mousemove-only: registers `mousemove`,
`click`, `scroll`, `resize` listeners and nothing else. **No gaze / fixation input.**
Computes the nine features per result from `(pageY, t)` mousemove samples, O(1)
memory per active episode.

**Canonical AdSERP extractor (Python, LAB-side):**
[`scripts/m4_nb21_hybrid_rerun.py`](../../scripts/m4_nb21_hybrid_rerun.py) — produces
the headline §4.1 numbers under organic-hybrid attribution.
**Parity-verified at 1e-6 tolerance** against the JS library via
[`scripts/test_feature_tracker_parity.js`](../../scripts/test_feature_tracker_parity.js)
+ `test_feature_tracker_parity.py` (synthetic trajectory; nine features; absolute
diff <1e-6).

**Headline §4.1 numbers** (M1 = 0.668, M4 = 0.847; organic_hybrid; Δ=500 ms
click-buffer): produced by this pipeline. Per-feature alone-AUCs in
[`scripts/output/cikm-2026/alone_auc_table.md`](../../scripts/output/cikm-2026/alone_auc_table.md).

## Diagnostic-only — deliberate gaze-gated variant

[`scripts/compute_lab_gaze_gated_features.py`](../../scripts/compute_lab_gaze_gated_features.py)
("STUB-D"). Explicitly fixation-timed cursor interpolation — replaces the
mousemove stream with cursor positions sampled at fixation times. **Requires an
eye tracker; not deployable.** The paper's §4.3 "diagnostic upper bound" (LOSO
AUC 0.781) is from this variant. It exists only as the ceiling the canonical
deployable cursor-only classifier (0.753) is compared against — capturing 96.4 %
of the gaze-gated ceiling on identical features and protocol.

## Superseded — do not use for paper claims

[`scripts/compute_cursor_approach_features.py`](../../scripts/compute_cursor_approach_features.py)
— early LAB producer extracted from NB15. **Gaze-gated by accident, not by
design**: iterates `fixations`, requires fixation data (returns None otherwise),
computes `gaze_cursor_distance(fix.x, fix.y, …)` at fixation timestamps. Its
output `AdSERP/data/cursor-approach-features-organic.json` is read by
`scripts/nb21_loso_retrain_organic.py` → produces **M1 = 0.727, M4 = 0.864** —
*different* from the paper's headline 0.668 / 0.847. Kept for historical
comparison and as the artifact the retrospective traces back to.

The header of `compute_cursor_approach_features.py` carries a SUPERSEDED banner
pointing here. Do not propagate its outputs into paper claims; do not "fix" it to
match the paper — that work landed elsewhere.

## Reading order for someone new to this question

1. **This file.**
2. `approach-retreat/src/approach-retreat.js` — the `ResultFeatureTracker` class
   (~150 lines) is the source of truth for what "the nine features" are.
3. `scripts/m4_nb21_hybrid_rerun.py` — the canonical AdSERP-side Python extractor.
4. `scripts/test_feature_tracker_parity.{js,py}` — the parity proof tying (2) and
   (3) together.

Do not anchor on `compute_cursor_approach_features.py` or
`nb21_loso_retrain_organic.py` / `cursor-approach-features-organic.json`. They are
superseded; their numbers do not match the paper.
