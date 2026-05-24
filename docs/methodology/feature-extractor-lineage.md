# Feature-extractor lineage (cursor approach features)

Two parallel cursor-feature pipelines live here, serving different purposes.
Neither supersedes the other. The gotcha is the third entry — a §4.1 LOSO
retrain script whose numbers are mechanically real but easy to mistake for the
paper's headline.

## Pipeline A — paper §4.1 / §4.3 / §4.6 headline numbers (cursor-only)

**Production library:** [`approach-retreat/src/approach-retreat.js`](../../../approach-retreat/src/approach-retreat.js)
— `ResultFeatureTracker` class, released as `approach-retreat` (v0.3.0). Pure
mousemove-only: registers `mousemove` / `click` / `scroll` / `resize` listeners
and nothing else. **No gaze input.** Computes the nine features per result from
`(pageY, t)` mousemove samples.

**Canonical AdSERP extractor (LAB-side Python):**
[`scripts/m4_nb21_hybrid_rerun.py`](../../scripts/m4_nb21_hybrid_rerun.py).
**Parity-verified at 1e-6 tolerance** against the JS library via
[`scripts/test_feature_tracker_parity.js`](../../scripts/test_feature_tracker_parity.js)
+ `test_feature_tracker_parity.py` (synthetic trajectory; nine features;
absolute diff < 1e-6).

**Produces** the paper's headline §4.1 numbers — M1 = 0.668, M4 = 0.847 —
under `organic_hybrid` attribution at Δ = 500 ms click-buffer. Per-feature
alone-AUCs in
[`scripts/output/cikm-2026/alone_auc_table.md`](../../scripts/output/cikm-2026/alone_auc_table.md).

## Pipeline B — LAB analysis substrate (gaze-gated, not deployable)

**Producer:** [`scripts/compute_cursor_approach_features.py`](../../scripts/compute_cursor_approach_features.py)
— extracted from NB15. Gaze-gated: iterates fixations and samples cursor at
fixation timestamps; computes the same nine geometric features.

**Output:** `AdSERP/data/cursor-approach-features-organic.json` (and
`-absolute.json`, `-organic-hybrid.json` variants).

**Active and used widely** as the feature substrate for downstream LAB-side
analyses — LFHF studies, four-class taxonomy (NB22), viewport bands (NB28),
trial-level analyses, plot rendering. Not deprecated; just answers a different
question than Pipeline A.

**Why a separate pipeline exists:** Pipeline B uses fixation-timed cursor
samples to study what the cursor does *given a known gaze trajectory* — the
input to LAB-side coupling and load analyses. Pipeline A's job is what a
deployable extractor can recover from mouse telemetry alone. The two are not
swappable; they are not validations of each other.

## Diagnostic-only — deliberate gaze-gated extractor for the §4.3 upper bound

[`scripts/compute_lab_gaze_gated_features.py`](../../scripts/compute_lab_gaze_gated_features.py)
("STUB-D"). Explicit fixation-timed cursor interpolation; **requires an eye
tracker; not deployable**. Produces the paper's §4.3 "diagnostic upper bound"
(LOSO AUC 0.781). Exists only as the ceiling Pipeline A's deployable
cursor-only classifier (0.753) is compared against — 96.4 % capture on
identical features and protocol.

## The landmine — `nb21_loso_retrain_organic.py`

[`scripts/nb21_loso_retrain_organic.py`](../../scripts/nb21_loso_retrain_organic.py)
re-runs the §4.1 LOSO protocol on Pipeline B's
`cursor-approach-features-organic.json`. Its output —
**M1 = 0.727 / M4 = 0.864** — is mechanically real but is **NOT** the paper's
§4.1 headline (which is Pipeline A's M1 = 0.668 / M4 = 0.847 under
`organic_hybrid`). Easy to mistake for the headline; emits
`DeprecationWarning` at import for that reason.

## Historical context

The 2026-04-14 retrospective
[`docs/drafts/cikm-2026/process-trace-gaze-sync-missed.md`](../drafts/cikm-2026/process-trace-gaze-sync-missed.md)
documents how an earlier framing claimed Pipeline B's features were
"WILD-compatible" — a claim Pipeline A's existence + parity test corrected. The
producer in Pipeline B was never the problem; the *claim about its features
being deployable* was. That claim no longer appears in the paper.

## Reading order for someone new to this question

1. **This file.**
2. `approach-retreat/src/approach-retreat.js` — the `ResultFeatureTracker`
   class (~150 lines) is the source of truth for what "the nine features"
   actually are.
3. `scripts/m4_nb21_hybrid_rerun.py` — the canonical Python extractor
   (Pipeline A).
4. `scripts/test_feature_tracker_parity.{js,py}` — the proof tying (2) and
   (3) together at 1e-6.
5. `scripts/compute_cursor_approach_features.py` — Pipeline B, separately.
