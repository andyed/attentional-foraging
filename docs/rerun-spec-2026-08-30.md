# Re-run spec: the AF notebook re-runs that matter + AR propagation (2026-08-30)

Companion to `docs/notebook-refresh-plan-2026-08-30.md` (the exhaustive inventory).
This is the *executable subset* — what actually feeds a paper, a collaborator, or a
claims surface — in dependency order, with commands and acceptance gates. Everything
runs against the post-collision-fix substrate (`release/allserp-v1.1.0` ≥ `ab657a63`,
typed maps `2cb789eb8febd234`, 12 exclusions).

## 0 · The ratings question, answered (dd_top sub-ads)

Two different situations, do not conflate:

- **Plain typed graded-relevance surfaces: stale-but-sound.** The four-class
  taxonomy → graded-relevance chain is re-derivable and its substrate-nearest
  artifacts were re-derived today. Two laggards, both re-runs (Stage 1):
  `regression_labels_cache_typed.json` (Aug 28, pre-fix — gates NB22/NB28/NB30)
  and the May-05 `ltr_typed_*` summaries (gate NB26 K27–K29).
- **Cellsplit (dd_top sub-ad ranks): faulty at source, re-running is wrong.**
  `adserp_aois_by_trial_id_typed_gapfill_cellsplit.*` is Jun 23 (pre-realignment
  AND pre-collision-fix, unmarked), and its cells come from the frozen 2026-05-24
  snapshot with **no producer in the repo** and **31.0% DOM agreement** (fidelity
  harness; 902/1,551 carousels short, median shortfall exactly 1 cell). Any
  rating keyed to a cellsplit rank is keyed to a wrong lattice. **Hard gate:
  nothing cellsplit re-derives until Stage 4 rebuilds the cell producer.**
  Until then every `K-cellsplit-*` row and NB25's cellsplit cell keep their
  `[typed_gapfill-cellsplit, pending]` tags — that tag is currently the truth.

## 1 · Priority frame — who consumes what

| consumer | needs | urgency |
|---|---|---|
| CHI27 (Sara, go/no-go Fri 09-04) | NB22 four-class (crforager targets already re-derived from the script producer; the notebook + K-claims must match), knee artifacts (done) | this week |
| CHIIR resubmission (mid-Oct) | organic/organic_hybrid flavors — **unmoved by design**; only AR's M5 AUC reconciliation (§5.2) | September |
| Published claims surfaces (`notebook-key-claims.md`, `findings.md`) | every re-executed notebook's K rows + the phase-05 annotations | rolling, close per-stage |
| AR (approach-retreat) | replay surface (done today), master CSV regression labels (done today), docs corrections + M5 reconciliation (§5) | this week |

## 2 · Stage 1 — producers first (all inputs fresh as of 16:36–17:41 today)

Run from repo root, `.venv/bin/python`; stale-mark untracked outputs first
(`.stale-preCollisionFix-2026-08-30` suffix).

| # | command | unblocks | gate |
|---|---|---|---|
| 1.1 | `scripts/compute_regression_labels.py --attribution typed` (verify flag name in-file) | NB22, NB28, NB30 | cache trial count = 2,764; excluded tids absent |
| 1.2 | `scripts/ltr_typed_four_class.py`, `ltr_typed_lfhf_feature.py`, `ltr_typed_lfhf_pairwise.py`, `ltr_typed_5class_confidence.py`, `ltr_typed_four_distinct_grades.py` — plain AND buf500 variants (buf500 inputs landed 16:41/17:41 today; the plan doc's "wait" note is obsolete) | NB26 K27–K29 | summaries carry today's date + fresh input mtimes |
| 1.3 | `scripts/adsight_noticed_classifier.py` (features regenerated 16:39) | NB31 | — |
| 1.4 | `scripts/k_coefficient_phase_trajectory.py` | NB32 | — |
| SKIP | `ltr_typed_four_class_cellsplit.py` and every `*_cellsplit` producer | — | **blocked by §0 hard gate** |

## 3 · Stage 2 — the notebook re-runs that matter (after their Stage-1 row)

Re-execute via `.venv/bin/jupyter nbconvert --to notebook --execute --inplace`;
rebuild Key Claims from executed output (no stdout scraping — that defect shipped
at least 12 times, see plan doc §7); `notebooks-v2/update_key_claims.py` after each.

| NB | why it matters | waits on |
|---|---|---|
| **NB22** four-class taxonomy | THE validation object: crforager HUMAN_FOUR, AR regression labels, LTR grades all trace here; its K rows must match the already-re-derived script-producer numbers or something is wrong | 1.1 |
| NB20 | inputs fresh now; feeds claims surface | none |
| NB28, NB30 | viewport bands / consumers of the label cache | 1.1 |
| NB26 | K27–K29 cite May-05 summaries — currently the most-stale *cited* rows | 1.2 |
| NB31 | adsight replication | 1.3 |
| NB32 | phase trajectory | 1.4 |
| SKIP NB25 cellsplit cell, NB23 K-cellsplit rows | §0 hard gate | Stage 4 |

Per-notebook acceptance: corpus = 2,764 (12 excluded), typed inputs mtime ≥ today
16:00, K-ID deltas recorded with `(re-derived 2026-08-30: collision-fixed maps)`
annotations, aggregate regenerated. A K row that *reverses* goes to Andy before
commit — today's precedent: NB23's boundary-excluded LHIPA × click-position lost
significance (−0.617, p=.077).

## 4 · Stage 3 — claims-surface close-out (phase 05, do once Stage 2 lands)

- `docs/notebook-key-claims.md` + `docs/findings.md`: add the mandated
  re-derivation annotations (both 2026-08-28 y-DP and 2026-08-30 collision-fix
  passes); currently neither surface mentions either.
- `docs/local-pack-aoi-shift.md` §Resolution: figures are now TWO generations
  stale — current truth: matched 25,054 / unknown_widget 650 / residual 1.95 px
  / **12** suspects (membership changed: +p018-b3-t1).
- Stdout-scrape sweep (NB24 ×2, NB28 ×2, NB30 ×2, NB32 ×2, NB04 ×1 — NB15's two
  placeholders were fixed today): mechanical, one commit.

## 5 · AR propagation (approach-retreat)

Already done today (commits `92c54dc`, `ad789c6`): 147 replay bundles + pages on
post-fix maps, html_handle joins, exclusion badging, master CSV regression labels
re-derived in typed rank space, `.ias` exports. Remaining:

1. **Docs corrections** — `findings.md:144`: 2,776 → 2,764 trials, median
   distinct types 6 → **7**, range 2–11. Key-claims V1/V2/V3 are WILD/`organic`
   — unmoved, say so explicitly rather than silently.
2. **M5 AUC reconciliation** — three values pinned across AR (0.794 curation
   docs / 0.769 key-claims / 0.709 legacy), none rank-type-labelled at the 0.794
   site. Resolve to one provenance-clean number per rank-type. **This is the
   CHIIR-critical item** (head-to-head baseline table needs it); it is a
   provenance audit, not a re-run — the `organic` flavor never moved.
3. **After AF's NB22 re-executes**: confirm AR's four-class validation targets
   (`analysis/` vs NB22 K rows) still agree; AR validates against NB21/NB22 per
   its charter.
4. **PAI proof images** — p006-b4-t7, p019-b1-t8 stale (their `.ias` changed);
   needs Duchowski's glias2poly. p047-b6-t1 current. External dependency, track
   in AR TODO.
5. **Deploy decision (Andy)** — the published replay site still serves pre-fix
   pages; the two alignment-suspect pages are badged in the repo but live
   unbadged until deploy.
6. **Provenance stamps (phase 08)** — AF publishes `data/aoi-typed/substrate.json`
   (tag + content hash) beside the exclusion list; AR bundles already stamp
   `alignment_suspect` since today — extend `_meta` with AF commit + flavor.

## 6 · Stage 4 — the cellsplit rebuild (the real dd_top fix; separate work item)

Not a re-run: a producer. The carousel cells need an in-repo producer deriving
cell membership from the DOM (the `vplaurlg<N>` ids the fidelity harness already
reads via the rendered saved SERPs) instead of the frozen 2026-05-24 snapshot.
Definition of done: fidelity `cell` check ≥ ~90% (from 31.0%), producer + stamp
committed, then and only then: regenerate the cellsplit export
(`build_aois.py --flavor typed_gapfill_cellsplit` path — verify), re-run
`compute_nb23_cellsplit_rank.py` + `compute_nb25_cellsplit_composition.py` +
`ltr_typed_four_class_cellsplit.py`, drop the `pending` tags. Candidate shared
work item with Sara (her §2/§3e finding; flagged in the f2f prep).

## Ordering note

Stages 1–2 are an afternoon of compute and can run unattended; Stage 3 is an
hour of editing; §5.1–5.2 are independent of all of it and CHIIR-critical.
Stage 4 is the only real build and should be scoped with Sara before anyone
starts it.
