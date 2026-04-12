# Attentional Foraging

SERP evaluation task model (OSEC) built on AdSERP eye+cursor dataset. 11 Tier-A analysis notebooks, 4 producer scripts, comprehensive Key Claims system.

## Notebook Conventions

Every Tier-A notebook has a **Key Claims block** at the top with stable K-IDs (K1, K2, ...). These are the canonical source of truth for all quantitative findings.

**Rules for AI assistants:**
- When adding or modifying quantitative findings in a notebook, add/update a K-ID row in the Key Claims table. Values must come from executed cell output — never hand-type.
- When citing findings in prose (findings.md, papers, READMEs), use `[NB##:K##]` notation.
- K-IDs are never renumbered. Retired claims get marked `(retired YYYY-MM-DD: reason)`.
- After modifying a notebook's Key Claims, run `python notebooks-v2/update_key_claims.py` to refresh the aggregate.
- The contract: if prose disagrees with a Key Claims row, the prose is wrong.

Full convention spec: https://github.com/andyed/science-agent/blob/main/docs/notebook-conventions.md

## Key Files

- `docs/notebook-key-claims.md` — aggregate of all Key Claims (canonical reference for paper writers)
- `docs/findings.md` — narrative findings citing `[NB##:K##]`
- `notebooks-v2/update_key_claims.py` — generates aggregate from notebook Key Claims blocks
- `notebooks-v2/data_loader.py` — shared data loading (coordinate conventions documented in docstring)
- `tests/test_coordinate_invariants.py` — regression test for coordinate-space conventions

## Data

AdSERP dataset at `../AdSERP/data/`. Coordinate convention: mouse Y is **page-space** (document coordinates, not viewport). Do not add scroll offset to click_y or mouse_y — it's already included.

## Downstream Repos

- `../approach-retreat` — cursor episode library, validates against our NB21/NB22 Key Claims
- `../pupil-lfhf` — Butterworth IIR cognitive load, validates against our NB14/NB05/NB18 Key Claims

When Key Claims change here, downstream repos may need updates.
