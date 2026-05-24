# Cursor-approach feature pipelines — read before adding new claims

Two pipelines, different questions. The trap is one specific LOSO re-run script.

| Role | Where | Notes |
|---|---|---|
| **Paper §4.1 headline — production library** | [`approach-retreat/src/approach-retreat.js`](../../approach-retreat/src/approach-retreat.js) — `ResultFeatureTracker` (v0.3.0) | Pure cursor / mousemove-only; no gaze. |
| **Paper §4.1 headline — AdSERP Python** | [`m4_nb21_hybrid_rerun.py`](m4_nb21_hybrid_rerun.py) | Parity-verified **1e-6** vs the JS library ([`test_feature_tracker_parity.js`](test_feature_tracker_parity.js) + `.py`). Produces M1 = 0.668 / M4 = 0.847 under `organic_hybrid`. |
| LAB analysis substrate (gaze-gated, active) | [`compute_cursor_approach_features.py`](compute_cursor_approach_features.py) → `AdSERP/data/cursor-approach-features-organic.json` | Feeds LFHF, four-class taxonomy (NB22), viewport bands (NB28), plot rendering. **Not deprecated** — just a different question than the paper's deployable cursor story. |
| Diagnostic-only — §4.3 upper bound | [`compute_lab_gaze_gated_features.py`](compute_lab_gaze_gated_features.py) (STUB-D) | Fixation-timed cursor interpolation; requires eye tracker. Produces the §4.3 0.781 ceiling. |
| **Landmine** — easy to confuse with the §4.1 headline | [`nb21_loso_retrain_organic.py`](nb21_loso_retrain_organic.py) | Runs the §4.1 LOSO protocol on the LAB analysis substrate. Produces M1 = 0.727 / M4 = 0.864 — **NOT** the paper's headline. Emits `DeprecationWarning` at import. |

Full lineage prose: [`docs/methodology/feature-extractor-lineage.md`](../docs/methodology/feature-extractor-lineage.md).
