# Integration verification — 29 September 2026

## Import (morning)

- Both posters were imported from a working session with checksums in the [import manifest](import-manifest.json), and regenerated with repository-local renderers.
- Browser review confirmed the rendered README, both poster pages and the process explanation, including one-column layout at a 260 px CSS viewport and no page overflow on desktop.
- The cascade definition was checked against the original paper's Microsoft Research publication page.

## Consolidation and full rebuild (afternoon)

- The shared measurement rules moved into `scripts/attention_atlas/atlas_core.py`, replacing three copies in the producers. All three producers, the check script, both renderers and all page builders were rerun from the raw AdSERP recordings in an isolated copy (`AF_ATLAS_DIR`).
- Against the imported outputs, the rebuild reproduced the information-space summary, per-trial records and time budgets exactly, and the common-coverage records exactly. The resting-cursor and sequence summaries differ only in provenance: gate sources are repository paths rather than session paths.
- Additions:
  - the click target in each sequence record (previously always null);
  - two cursor-hold sensitivities in the resting-cursor summary;
  - the clock-origin sensitivity for matched visit pairs;
  - the example-rule prevalence in `checks.json`.
- Gates now exit with a message; they previously used `assert`, which `python -O` removes. The information-space baseline gate compares states in both directions.
- Per-trial records are gzip JSON with a zero timestamp. Outputs contain no run timings or absolute paths. The atlas directory went from 34 MB to 12 MB.
- `verify-atlas.py` verification:
  - links and anchors;
  - clock conservation;
  - aggregates and every gate in both directions;
  - a recomputation of common coverage;
  - 67 numbers in the pages, posters and entry-point prose checked against the JSON;
  - values pinned in [evidence-pin.json](evidence-pin.json).
- The verifier exits non-zero on a tampered value, including under `python -O`.
- `scripts/test_attention_atlas.py` (15 tests) covers the core rules on synthetic inputs, including matching against exhaustive search, and runs the verifier on a copy of the shipped atlas.

Raw gaze and cursor recordings were recomputed in the afternoon rebuild; the verifier itself reads only the saved records.

Machine-readable evidence: [integration-verification.json](integration-verification.json).
