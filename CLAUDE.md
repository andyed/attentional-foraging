# Attentional Foraging

SERP evaluation task model (OSEC) built on AdSERP eye+cursor dataset. 11 Tier-A analysis notebooks, 4 producer scripts, comprehensive Key Claims system.

## Feature extractor provenance — read this first

**Two parallel cursor-feature pipelines**, different questions. Neither supersedes the other; mistaking them for each other has bit us before. Full map in [`docs/methodology/feature-extractor-lineage.md`](docs/methodology/feature-extractor-lineage.md); `scripts/CANONICAL.md` is the table.

- **Paper §4.1 / §4.3 / §4.6 headline (cursor-only, deployable):** `approach-retreat` library (JS, `ResultFeatureTracker` v0.3.0) ↔ `scripts/m4_nb21_hybrid_rerun.py` (AdSERP Python), **parity-verified at 1e-6** via `scripts/test_feature_tracker_parity.{js,py}`. Produces M1 = 0.668 / M4 = 0.847 under `organic_hybrid`.
- **LAB analysis substrate (gaze-gated, active):** `scripts/compute_cursor_approach_features.py` → `cursor-approach-features-organic.json`. Feeds LFHF, four-class taxonomy (NB22), viewport bands (NB28), plot rendering. *Not* the source of the paper's §4.1 headline numbers.

**The one landmine:** `scripts/nb21_loso_retrain_organic.py` runs the §4.1 LOSO protocol on the LAB analysis substrate and produces M1 = 0.727 / M4 = 0.864 — *not* the paper's headline. Emits `DeprecationWarning` at import. The 2026-04-14 retrospective `docs/drafts/cikm-2026/process-trace-gaze-sync-missed.md` documents the failure pattern.

## CIKM 2026 paper

Edit in `~/Documents/dev/cikm-leakycursor/` — `source/paper.md` (markdown), `paper.tex` (LaTeX), `build.sh` (xelatex). Replicate pipeline: `~/Documents/dev/cikm-leakycursor-replicate/`. ACD validation: `~/Documents/dev/approach-retreat/analysis/attcur-validation/`. This repo (`attentional-foraging`) hosts the LAB analysis substrate feeding §4 — notebooks, gaze-gated extractors, taxonomy producer, figure renderers.

## LAB / WILD Convention (CIKM paper organizational axis)

Every quantitative claim in the CIKM paper, and every figure/table in `scripts/output/`, must be tagged with its regime. Two labels, no middle:

- **LAB** — AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025). Controlled lab: 47 participants, Gazepoint GP3 HD 150 Hz eye tracker, evtrack mouse telemetry, pupil diameter, full scroll signal, SERP HTML snapshots, ad bounding boxes. **Instrumentation stack:** pupil → gaze → cursor → scroll → click. Used for every claim that depends on eye movements, pupil dilation, or gaze-cursor coupling.
- **WILD** — ACD, the Attentive Cursor Dataset (Leiva & Arapakis, *Frontiers in Human Neuroscience* 2020). In-the-wild crowdsourced: ~2,909 sessions, cursor + click only, no eye tracker, no pupil. **Instrumentation stack:** cursor → click. Used for replicating any claim that the LAB observed via eye tracking but must survive without gaze to matter for deployment.

**Do not say "deployed" or "production."** ACD is crowdsourced Mechanical Turk, not real production search logs. `WILD` is honest; `deployed` is not.

**Rules:**
- Every number, figure caption, and Key Claim row gets a regime tag: `[LAB, NB22:K3]` or `[WILD, ACD-retreat]` or `[BOTH]` when the same statistic has been computed in both datasets.
- **The four-class taxonomy (clicked / deferred / evaluated-rejected / not-approached) is `[LAB]`-only by construction until further notice.** The deferred/eval-rejected split depends on `regression_labels`, which is computed in `notebooks-v2/22_four_class_taxonomy.ipynb` from the **gaze-fixation sequence** revisiting earlier result positions — `regressed_pos.add(p)` where `p` comes from `fix['y']`, not from scroll events. The variable name `regression_labels` is neutral but the detection mechanism is unambiguously gaze-based; prose should refer to it as **`gaze_regression_label`** (not `scroll_regressed_back` — that name is wrong and should not be used). A scroll-only detector is a named piece of future work that would earn `[BOTH]` for the taxonomy if validated against the gaze-based version. **There is already a scroll-regression detector in the project at `notebooks-v2/09_difficulty.ipynb` (`count_scroll_regressions`) and `notebooks-v2/17_scroll_retreat.ipynb` (start/end event detection).** These are separate from NB22's `regression_labels` and were built for a different purpose; the scroll-only proxy for the four-class taxonomy would validate the scroll-based detection against the gaze-based one on LAB data and then adopt it as the canonical class-grounding feature for WILD transfer.
- When a claim is LAB-only (pupil, LHIPA, LF/HF, direct gaze-cursor coupling medians, **the four-class taxonomy itself**), say so explicitly. Do not imply it transfers unless tested.
- `docs/notebook-key-claims.md` should carry the tag on every row. Prose in `findings.md`, `paper.md`, and README.md citations pass the tag through untouched.
- When writing §4/§5 of the CIKM paper, mirror the split: §4 LAB findings (pupil, gaze, motor signature) → §5 What survives to WILD (four-class taxonomy rebuilt from cursor alone, validated on ACD) → §6 deployment implication.

The point of the convention is that a reader should never be uncertain which regime a number came from. The "three coupling scalars" confusion (306 vs 338 vs 381) was entirely within LAB; a WILD version of that statistic is either computable on ACD or isn't, and that binary is the axis the reader holds.

## Rank-type disclosure rule (project convention, post-2026-05-01 cascade)

**Every quantitative claim derived from AdSERP must carry a rank-type tag** identifying the AOI-attribution flavor under which it was computed. Three flavors are canonical, defined in [`docs/methodology/attribution-cascade-synthesis.md` §1](docs/methodology/attribution-cascade-synthesis.md) and tabulated in [`docs/methodology/aoi-coverage-contribution.md` §4](docs/methodology/aoi-coverage-contribution.md):

- **`absolute`** — legacy h3 + ads pooled, band-estimated AOIs (pre-2026-05-01).
- **`organic`** — CV-extracted bbox organics, ads excluded; the post-cascade primary.
- **`organic_hybrid`** — bbox organics + dd_top + native_ad in display order, etype-tagged; deployment-aware variant.

Every K-ID receives one rank-type tag, written next to the regime tag: e.g. `[LAB, AdSERP, organic, NB21:K-bbox-3]`.

**Three carve-outs** for tagging:

1. **Rank-type-independent claims** — pure cursor-only metrics computed on a single-AOI surface (e.g. `[WILD, attcur]`), library JS↔Python parity tests, time-series with no AOI-rank structure — are tagged `rank-type-N/A` with a one-line justification at first occurrence, never silently.
2. **Pre-cascade legacy values** retained for historical comparison are tagged `[absolute, legacy pre-2026-05-01]` with the cascade date explicit, so a reader sees the retirement date and can find the post-cascade replacement.
3. **Multi-flavor comparisons** are presented as a three-row table with `absolute / organic / organic_hybrid` as the row keys (the canonical example is `aoi-coverage-contribution.md` §4); narrative prose names the flavor that anchors the headline and treats the other two as robustness rows.

Cascade-affected K-IDs that have not yet been re-derived are tagged `[<flavor>, pending]` with a link to the gate (the multi-hour bootstrap, the producer migration, the figure regen) — never silently rolled forward.

**The methodology spec is the canonical definition site; downstream docs cite it, do not redefine it.** A K-ID without a rank-type tag (where one applies), or a numeric value quoted from before a cascade without explicit retirement notice, is a citation bug — treat it as confabulated until verified against the producer flag and the script output.

K-IDs are never renumbered; cascade-superseded rows get a new `K-bbox-#` row alongside the legacy K-#, and the legacy row keeps its number with a `(retired YYYY-MM-DD: replaced by K-bbox-#)` annotation.

## Two-pass citation workflow (pre-emptive discipline for research prose)

**When editing any file under `docs/drafts/cikm-*/`, `docs/drafts/task-model-paper*`, or `docs/arxiv/`, use the two-pass workflow below.** This is a pre-emptive rule against citation confabulation under reframe pressure, not a post-hoc check.

**Pass 1 — Prose generation.** Do NOT write in the prose:
- Author names in citation position (e.g. "Stone et al.", "Chen & Anderson")
- Venue+year citation tokens (e.g. "[TOCHI 2023]", "[CHIIR '18]")
- Paraphrases of what specific source papers "showed" / "demonstrated" / "found"

Instead use explicit placeholders:
- `[CITE: <topic>]` or `[CITE: <author-guess> on <topic>]` for citations
- `[ATTRIBUTE: <source-key>: <claim>]` for paraphrases of what a source shows
- `[CHECK: <claim>]` for any factual claim whose source I'm not sure of

**Pass 2 — Verification.** Walk every placeholder. For each:
1. Locate a candidate source: first check `references.bib` (existing entry), then local lit-notes / PDFs, then WebSearch / WebFetch with the claim as the query.
2. Read the abstract or the specific passage to verify the claim matches.
3. If verified: replace the placeholder with the real citation + accurate paraphrase. Add the bib entry if it's new.
4. If the candidate doesn't support the claim, or no candidate is found: either change the argument to use a source I do have, or drop the claim. **Do not resolve the placeholder by inventing.**

**Why this discipline exists.** On 2026-04-15 during a reframe of paper-v3, two citation confabulations survived into the prose across multiple sections: `Stone et al. TOCHI 2023` was entirely fabricated (real paper is Stone & Chapman PACMHCI ETRA 2023 with a different claim), and my paraphrase of Zhang/Abualsaud/Smucker CHIIR 2018 ("saccade-resolution survey-phase analysis") was fabricated (the paper is actually about immediate requery behavior with a result-inspection-phase hypothesis). Both were caught — Stone by Andy Googling; Zhang by the science-audit agent — but one had propagated through abstract, §1, and §2.4 of the paper before detection. The mechanism was prose generation and citation generation in the same forward pass: a reframed argument needed a citation-shaped token sequence that supported a specific claim, and I produced one that matched the argument without verification. The two-pass workflow physically separates these stages so confabulation cannot occur during generation.

**Rule of thumb.** If a citation token or a "X showed Y" paraphrase appears in the prose without first passing through the verification pass, it is presumptively confabulated. Treat it as a bug until verified.

## Pencil — sentence-level voice locking (paper drafts)

**When editing any file under `docs/drafts/cikm-*/`, `docs/drafts/task-model-paper*`, or `docs/arxiv/` that has a `<file>.pencil.json` sidecar, honor the locks.**

`pencil` is at `~/Documents/dev/pencil/pencil.py`. Run `python3 ~/Documents/dev/pencil/pencil.py <cmd> <file>`.

**Before any edit** to a paper file with a sidecar:

```bash
python3 ~/Documents/dev/pencil/pencil.py check docs/drafts/cikm-2026/paper-v4.md
```

If `check` exits 0, proceed. If it exits 1, the document already has drift from the previous pencil scan — surface that to Andy first; do not edit on top of it. Walking new drift into existing drift compounds the problem.

**Edits must not modify locked sentences.** A sentence is locked if its entry in the sidecar has `"status": "locked"`. The sentence text in the sidecar is canonical. Insertions adjacent to locked sentences are fine; rewording inside a locked sentence is not. If a locked sentence is wrong and needs to change, ask Andy first — the lock signals "Andy wrote this, leave it alone."

**After any edit:**

```bash
python3 ~/Documents/dev/pencil/pencil.py scan docs/drafts/cikm-2026/paper-v4.md
python3 ~/Documents/dev/pencil/pencil.py check docs/drafts/cikm-2026/paper-v4.md
```

`scan` re-walks the file and refreshes sidecar entries. New sentences land as `unmarked` (AI-drafted, eligible for further AI editing). `check` verifies no locked sentence drifted; if it fails, the edit broke a lock — revert and reconsider.

**Boundary cases.** If an edit splits one locked sentence into two, or merges two adjacent sentences, hashes invalidate and `check` will report drift. Treat this as a hard stop — split/merge of locked text is a content change. Either undo, or ask Andy to unlock first.

**Regex sweeps must use the pencil-aware sweeper.** When applying mechanical find-and-replace across paper drafts (e.g., AI-tell removal sweeps), use `pencil.sweep.sweep_files()` from `~/Documents/dev/pencil/sweep.py`. It loads the sidecar, skips substitutions that fall inside locked spans, and returns `protected_skip` counts so you can see what wasn't touched. A naive `re.sub` on the file text WILL clobber locked content if the pattern hits inside a lock — this happened on 2026-05-07 with sentence #42 of paper-v4.md and was only caught by the post-sweep `pencil check`.

## Null findings

**Principle (2026-04-15).** Null and near-null findings get written up in `docs/null-findings/` as markdown even when they don't make it into the published paper. See `docs/null-findings/README.md` for the principle statement, format conventions, and current index. This is a research-integrity commitment, not a bureaucratic one — the file-drawer cost of not documenting nulls on a single-lab project is re-walking the same paths months later.

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
