# Notebook strategy

How notebooks, precomputed data, Key Claims, and papers stay consistent in this repo.

The pipeline that produces every number in our papers flows through one canonical path. When it drifts, papers cite stale values. The coordinate-space audit of 2026-04-09 is the cautionary tale: a single scroll double-counting bug in one helper invocation silently corrupted nine notebooks, two scripts, and three downstream precomputed JSONs for months. What saved us was (a) that only five notebooks ship key numbers, (b) the Key Claims contract locking those five to a machine-regeneratable canonical source, and (c) a regression test forcing the coordinate convention. This document describes the strategy so the next audit is shorter.

## The tiers

Every notebook belongs to exactly one of three tiers. Tier determines the discipline it must follow.

### Tier A — central

**Ships numbers directly to external papers or public writeups.**

Current Tier A notebooks:

| Notebook | Cites into |
|---|---|
| NB11 `individual_differences` | CIKM 2026, CHI 2027, ETTAC |
| NB11.5 `chattiness_traits` | CIKM 2026 §4.3 robustness |
| NB13 `survey_phase` | arXiv task-model paper §3, CHI 2027 |
| NB14 `butterworth_cognitive_load` | **ETTAC 2026 (headline)**, CHI 2027 |
| NB21 `click_prediction` | CIKM 2026 §4, CHI 2027 |

**Required of a Tier A notebook:**

1. A `## Key Claims` markdown cell at the top with a table of canonical values, each row tagged with a stable ID (`[NB14:K3]`, `[NB21:K12]`, …). The cell's content is the source of truth — if prose disagrees, the prose is wrong.
2. The block is maintained via `notebooks-v2/update_key_claims.py`, not by hand-editing the notebook. The script has per-notebook body constants (`NB14_BODY`, `NB21_BODY`, …) and rewrites the cell in place. Hand-editing gets clobbered on the next run.
3. Any number cited in `docs/findings.md`, `docs/arxiv/`, `docs/drafts/`, or a draft submitted to a venue must either (a) match a Key Claims row or (b) be recomputable from the notebook's published cells. Nothing else is citable.
4. After any re-run that changes a number, update the corresponding body constant, bump `VERIFIED` in `update_key_claims.py`, run the script, grep `docs/` for the old value, and add a CHANGELOG entry.

### Tier B — feeder

**Does not ship numbers to papers, but produces precomputed artifacts that Tier A notebooks consume.**

| Artifact | Producer | Consumed by |
|---|---|---|
| `AdSERP/data/butterworth-lfhf-by-position.json` | `scripts/compute_butterworth_lfhf.py` | NB14, NB18-ripa2, NB23 |
| `AdSERP/data/cursor-approach-features.json` | `15_cursor_approach.ipynb` | NB11.5, NB20, NB21, NB22 |
| `AdSERP/data/cursor-approach-features-typed.json` | `scripts/add_etype_to_features.py` | NB20 |
| `AdSERP/data/ripa2-by-position.json` | `scripts/compute_ripa2.py` | NB18-ripa2 |
| `AdSERP/data/butterworth-lhipa.json`, `lhipa-per-trial.json` | `scripts/compute_lhipa.py` | NB05, NB11, NB23, many |

**Required of Tier B:**

1. Every Tier B producer must `import` from `data_loader` rather than reimplement CSV parsing or scroll interpolation. This is the rule that, if followed, would have prevented the coordinate-space audit entirely.
2. When a Tier B artifact is regenerated, re-run every Tier A consumer and update affected Key Claims in the same commit. The CHANGELOG entry should list both the producer change and every affected Key Claim row.
3. Keep a `*.prefix-bug.json` backup whenever a Tier B artifact is regenerated after a bug fix, so the before/after diff is reproducible.

### Tier C — exploratory

Everything else. NB01, 03, 04, 05 (despite feeding LHIPA computation), 06, 07a/b/c, 08, 09, 10, 12, 15 (because it's the feeder for cursor-approach-features.json — note: NB15 is simultaneously Tier B for its JSON output and Tier C for its local figures), 16, 17, 18 variants, 19, 20, 22, 23, 24.

**Required of Tier C:**

1. `import` from `data_loader` rather than cargo-culting a mini-loader. This is aspirational today — ten Tier C notebooks still have their own `load_mouse_events`-equivalent functions. See "Phase 3 structural migration" below.
2. No prose in `docs/` may cite a Tier C notebook's numbers directly. If a Tier C notebook's finding is central enough to cite, promote it to Tier A by adding a Key Claims block.

## Coordinate conventions — non-negotiable

AdSERP combines two streams with different coordinate spaces. Mixing them silently produces scroll-proportional errors on 82% of trials.

- **Gaze** (Gazepoint FPOGX/FPOGY): screen-space (viewport pixels). `load_fixations` clamps to `scr_h` to drop noise. To compare against page-space bands, ADD `scroll_at_t`.
- Cursor (evtrack `xpos`/`ypos`): page-space (pageY, includes scroll). Verified empirically on `p004-b2-t3` (cursor Y up to 1,902 px, window is 1,137 px). To compare against screen-space gaze, SUBTRACT `scroll_at_t`.
- Clicks (from `load_mouse_events` `clicks[]`): same convention as cursor — already page-space. Never add scroll.
- Result band tops (`result_band_tops(n, doc_h)`): page-space measured from doc top.

**Never hand-write `+ scroll_y` on a mouse or click coordinate.** Use the canonical helpers in `data_loader`:

- `click_to_position(clicks, tops, n_results)` — page-space click → position index
- `get_click_page_xy(clicks)` — raw page-space click (x, y)
- `cursor_to_position(cursor_y_page, tops, n_results)` — cursor → position index
- `screen_y_to_page_y(screen_y, scroll_y_at_t)` — gaze conversion
- `page_y_to_screen_y(page_y, scroll_y_at_t)` — cursor → screen for display
- `gaze_cursor_distance(fix_x, fix_y, cur_x_page, cur_y_page, scroll_y_at_t)` — screen-space Euclidean
- `interpolate_cursor_at(t, mouse_ts, mouse_xs, mouse_ys)` — linear interp, page-space

The reference for all of this is the top of `notebooks-v2/data_loader.py`.

## The regression test

`notebooks-v2/test_coordinate_invariants.py` locks in the convention. It runs in a few seconds and has nine sections; the corpus-wide invariant 9 is the headline safety bar.

Run it:

```bash
/Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
    notebooks-v2/test_coordinate_invariants.py
```

**The test must pass before any change to `data_loader.py`, any Tier B script, or any Tier A notebook's data path.** It detects:

1. Coordinate-space contract violations (cursor Y out of page-space range)
2. `click_to_position` returning a band that does not contain the click
3. Disagreement with the old buggy formula on no-scroll trials (which means the fix broke the unaffected case)
4. Synthetic corner cases: band boundaries, off-SERP clicks, scr_h clamp leakage

## Phase 3 structural migration (planned)

Most Tier C notebooks reimplement CSV loading in cell 2 instead of importing `data_loader`. This is the root cause of the coordinate-space audit — each reimplementation has its own implicit convention, and half of them guessed wrong.

**Goal:** every notebook and script in this repo imports from `data_loader`. No cargo-culted mini-loaders.

**Ten notebooks to migrate:** NB01, 03, 05, 06, 07a, 07b, 07c, 08, 09, 10. Five scripts to verify (already migrated per grep): `compute_*.py`.

**Migration pattern:**

1. Read the mini-loader's CSV-parsing function.
2. Replace with `load_fixations`, `load_mouse_events`, `get_trial_meta`, `interpolate_scroll` from `data_loader`.
3. Delete the local helper.
4. Run the notebook end-to-end; confirm output is identical (modulo any known bug fixes). If Tier A, re-run `update_key_claims.py` afterward.

Do this as a separate, isolated PR from any behavioral fix. Mixing structural migration with behavior changes in the same diff makes review impossible.

## When a Tier A notebook's number changes

The canonical flow — this is the discipline the coordinate-space audit exposed and hardened:

1. **Verify the new number.** Either re-execute the notebook cell that produces it, or write a focused diff script that reads the relevant precomputed JSON and recomputes. Save the diff script as `_verify_nbXX_key_claims.py` (underscore prefix = not in notebook list, don't ship).
2. Update `notebooks-v2/update_key_claims.py` — edit the relevant per-notebook body constant. Do NOT edit the notebook directly; the script is canonical.
3. Bump `VERIFIED = date(Y, M, D).isoformat()` near the top of the script.
4. Run it: `/Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python update_key_claims.py`. This rewrites every Tier A notebook's Key Claims cell and regenerates `docs/notebook-key-claims.md`.
5. Grep `docs/` for the old value:
   ```bash
   cd /Users/andyed/Documents/dev/attentional-foraging
   grep -rn "0.827" docs/  # or whatever the old value was
   ```
   Skip `.claude/worktrees/` — ephemeral sandboxes.
6. Append to `CHANGELOG.md` — at minimum: what changed, before/after values for the affected rows, which consumers were re-run.
7. If a Tier B producer changed, list every Tier A consumer you re-ran in the same CHANGELOG entry. If you did not re-run a consumer, note the dependency so the next session picks it up.

## Why this exists (2026-04-09 retrospective)

Before the audit: five Tier A notebooks had Key Claims, but three of them cited numbers that were wrong (NB14:K6, NB21:K1–K27 except K2, NB11.5:K9–K16). The numbers were written by hand, back when they were computed correctly, and then the underlying data drifted silently as bugs accumulated in the feeders.

The fix structure (canonical script, Key Claims blocks, regression test, CHANGELOG discipline) is what lets us detect and repair this class of drift mechanically. Without it, each affected paper would have shipped with fragile or wrong numbers.

**The rule to remember:** if a number appears in a paper draft, it must match a row in `docs/notebook-key-claims.md`. If it does not, either (a) update the draft to match, (b) promote the source notebook to Tier A, or (c) remove the citation.
