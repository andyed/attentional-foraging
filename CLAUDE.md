# Attentional Foraging

SERP evaluation task model (OSEC) built on AdSERP eye+cursor dataset. 11 Tier-A analysis notebooks, 4 producer scripts, comprehensive Key Claims system.

## LAB / WILD Convention (CIKM paper organizational axis)

Every quantitative claim in the CIKM paper, and every figure/table in `scripts/output/`, must be tagged with its regime. Two labels, no middle:

- **LAB** — AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). Controlled lab: 47 participants, Gazepoint GP3 HD 150 Hz eye tracker, evtrack mouse telemetry, pupil diameter, full scroll signal, SERP HTML snapshots, ad bounding boxes. **Instrumentation stack:** pupil → gaze → cursor → scroll → click. Used for every claim that depends on eye movements, pupil dilation, or gaze-cursor coupling.
- **WILD** — ACD, the Attentive Cursor Dataset (Leiva & Arapakis, *Frontiers in Human Neuroscience* 2020). In-the-wild crowdsourced: ~2,909 sessions, cursor + click only, no eye tracker, no pupil. **Instrumentation stack:** cursor → click. Used for replicating any claim that the LAB observed via eye tracking but must survive without gaze to matter for deployment.

**Do not say "deployed" or "production."** ACD is crowdsourced Mechanical Turk, not real production search logs. `WILD` is honest; `deployed` is not.

**Rules:**
- Every number, figure caption, and Key Claim row gets a regime tag: `[LAB, NB22:K3]` or `[WILD, ACD-retreat]` or `[BOTH]` when the same statistic has been computed in both datasets.
- **The four-class taxonomy (clicked / deferred / evaluated-rejected / not-approached) is `[LAB]`-only by construction until further notice.** The deferred/eval-rejected split depends on `regression_labels`, which is computed in `notebooks-v2/22_four_class_taxonomy.ipynb` from the **gaze-fixation sequence** revisiting earlier result positions — not from the scroll stream. The feature name conventionally used in prose, `scroll_regressed_back`, is misleading: the detection is gaze-regression, not scroll-regression. A scroll-only detector is a named piece of future work that would earn `[BOTH]` for the taxonomy if validated against the gaze-based version.
- When a claim is LAB-only (pupil, LHIPA, LF/HF, direct gaze-cursor coupling medians, **the four-class taxonomy itself**), say so explicitly. Do not imply it transfers unless tested.
- `docs/notebook-key-claims.md` should carry the tag on every row. Prose in `findings.md`, `paper.md`, and README.md citations pass the tag through untouched.
- When writing §4/§5 of the CIKM paper, mirror the split: §4 LAB findings (pupil, gaze, motor signature) → §5 What survives to WILD (four-class taxonomy rebuilt from cursor alone, validated on ACD) → §6 deployment implication.

The point of the convention is that a reader should never be uncertain which regime a number came from. The "three coupling scalars" confusion (306 vs 338 vs 381) was entirely within LAB; a WILD version of that statistic is either computable on ACD or isn't, and that binary is the axis the reader holds.

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
