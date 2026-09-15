# Foraging refresh plan — 2026-09-14

Decision (Andy, 2026-09-14): `attentional-foraging` is refocused on advancing
the state of the art in **foraging as a theory of search-page behaviour**, and
the repository is to be refreshed around that. Click prediction is a
diagnostic the theory happens to pass, not the object. This document is the
ordered plan: the thesis, the construct-to-observable map the repo now owns,
what the refresh keeps, retires and adds, and the phased worklist.

Companion docs this supersedes in *framing* (not in substrate facts):
`docs/notebook-refresh-plan-2026-08-30.md` (phase 04/05 worklist — still the
freshness ledger), `docs/drafts/publication-roadmap.md` (three-paper plan from
spring; venues have moved), `docs/notebook-strategy.md` (tier discipline —
unchanged and binding).

---

## 1 · Thesis

A searcher on a results page makes two nested decisions and leaves three
kinds of trace.

- **Within-patch:** harvest the result in front of me, or not. Witnessed by the
  cursor (the M4 vector, 0.935 AUC on commitment) and by gaze dwell.
- **Between-patch:** advance, return to a result already seen, or leave the
  page. Witnessed by the gaze return itself (NB22 label; 9,797 deferred slots
  on the typed map) and, as a candidate with no producer in this repo yet, by
  depletion state (how deep, how many sampled, how much page remains — the
  CHIIR note's Flavor B quotes 0.908 AUC from scratch runs; not quotable here
  until produced). Returns are what cascade models cannot represent.
- **Pre-patch:** what the periphery delivered before any fixation landed.
  Witnessed by PAI (Duchowski, Gehrer & Svaldi 2026), the graded-membership
  construct on the gaze side that mirrors the M4 construction on the cursor
  side. On this corpus its job is local next-fixation guidance and nothing
  the data can detect beyond proximity: no content evaluation, no format
  steering beyond reading order, no role in returns.

The phase model (Orient → Survey → Evaluate → Commit) is the temporal
structure inside which those decisions run; the survey is the between-patch
scan that costs ~1.3 s and does not pre-select the target.

Two claims that come out of today's producers and belong in the thesis
sentence once their notes are final:

1. **Returns are memory-guided, not periphery-guided.** Long returns land as
   precisely as first entries with half the peripheral intake on the target,
   and precision does not covary with that intake.
   (`scripts/return_is_memory.py` → `docs/ablations/return_is_memory.md`.)
2. **Engagement has five states, not four.** Never on screen / never sampled /
   peripherally sampled and skipped / fixated and rejected / deferred /
   clicked. The peripheral tier is a construct the ad-attention industry does
   not have (viewability is a viewport rectangle held for one second).
   (`scripts/engagement_state_census.py` → `docs/ablations/engagement_state_census.md`: a quarter of on-screen never-fixated results are sampled at read level within 200 px (≈ 5°), 44 % under a soft falloff, 73 % under the flat published kernel; the level is kernel-defined, the participant ordering is not.)

---

## 2 · Foraging constructs → observables this repo owns

The state of the art in information foraging (Pirolli & Card 1999; Charnov's
marginal value theorem; Azzopardi's economic and C/W/L models; Stephens &
Krebs) is stated at the level of patches, gain curves and stopping rules.
What this repo adds is a **saccade-level observable for each construct on a
public corpus**, with a producer that reproduces a shipped number before it
emits a new one.

| Foraging construct | Observable here | Producer | Status |
|---|---|---|---|
| Patch | one ranked result as its own observer of every stream | typed AOI maps (AllSERP v1.1.1) | shipped |
| Within-patch harvest decision | M4 cursor vector, 7 features, press-anchored 500 ms buffer | `m4_cursor_aoi_rerun.py` | shipped, 0.935 |
| Between-patch move / return | gaze return label (NB22); depletion-state model | `compute_regression_labels.py`; depletion model has **no producer here** (CHIIR note Flavor B, candidate) | label shipped; depletion **candidate** |
| Patch value gradient | motor engagement graded by outcome (187 vs 88 ms dwell) | `exploitation_vs_travel.py` | shipped (sidecar verified 2026-09-14) |
| Scent before entry | near-peripheral intake (published PAI gated at 8°, or a boundary-distance CM falloff) | `peripheral_kernel.py`, `pai_deferred_probe.py` | measured; nothing beyond the cursor on the return; published kernel flat on SERP bands |
| Return mechanism | landing precision and peripheral ramp, return vs entry | `return_is_memory.py` | **new today** |
| Engagement states | five-state census with opportunity baseline | `engagement_state_census.py` | **new today** |
| Survey / evaluate phases | saccade amplitude, pupil LF/HF | NB13, NB14 | shipped (task-model paper) |
| Give-up depth / knee | visible-patch depth model | Sara Allawati's track (CHI27), crforager | **not ours** — cite, do not rebuild |
| Gain curve / MVT threshold | not fitted anywhere | — | **gap** (Flavor B risk 2) |
| Generative gaze policy | bounded-optimal scan model | crforager | separate repo, private |

The gap row is the one piece of foraging theory the repo asserts without
fitting. Phase C below owns it.

---

## 3 · What the refresh keeps, retires, adds

**Keeps, unchanged.**
- The Key Claims contract, the Tier A/B/C discipline, the LAB/WILD and
  rank-type tags, the two-pass citation rule, pencil locks, null-findings.
- Every canonical producer in `scripts/CANONICAL.md` and the gate pattern
  (reproduce a shipped number, then compute).
- The AllSERP substrate and its release ledger.

**Retires to `docs/history/` (moved, not deleted; links preserved).**
- The ski-jump and lexical-priming framings that open `README.md` and
  `docs/findings.md` §0–§2. Both are documented nulls; they stay citable as
  history and stop being the front door.
- `docs/drafts/publication-roadmap.md` (spring venues). Replaced by §5 below.
- Pre-fix PAI numbers (`pai_exposure_validation.md`, `pai_preentry_probe.json`)
  as quotable results; they stay as method history with the re-derivation
  debt stated at the top of each.

**Adds.**
- `README.md` rewritten around §1: puzzle → two decisions, three channels,
  five states → what is measured → notebooks → papers. Draft in Phase A.
- Two ablation notes (today's producers) and, once gated, two Tier B
  notebooks: NB37 engagement states, NB38 return mechanism.
- A `docs/foraging-constructs.md` that is §2 kept current: the single place a
  reader finds which observable stands for which construct and where it is
  produced.
- An MVT fit (Phase C).

---

## 4 · Boundaries with sibling tracks (hold these in every document)

| Track | Owner | Claims it keeps | This repo cites, does not restate |
|---|---|---|---|
| Leaky Cursor, CHIIR 2027 | Andy + Jacek | divergence-as-signal, cursor-only deferred split, M4 geometry | the cursor is the witness to the within-patch decision |
| AO-SERP / abandonment, CHI 2027 | Sara Allawati (RMIT); also a CHIIR coauthor for orientation | how deep, give-up depth, knee, AIO as outside option, where the survey lands on an AIO page | depth and the AIO effect; every AO number stays out of this tree; orientation mechanism shared |
| PAI method, ETRA 2027 short (due 2027-02-11) | Duchowski, Gehrer & Svaldi; Andy on the AdSERP application | the kernel, the CM-weighted extension | peripheral tier and return mechanism as applications |
| Task model, CHI 2027 | Andy (`~/Documents/dev/task-model-paper/`) | Orient/Survey/Evaluate/Commit at saccade grain | phases as the temporal container |
| RIPA2 / pupil | Gavindya + team | pupil trait axis | embargoed; LF/HF only here |
| crforager | Andy, private | generative bounded-optimal policy | the model the observables here calibrate |

The two corpora differ on seven axes (task, page top, geometry, practice,
tracker, screen, relevance structure); which results are sensitive to which is
in `docs/methodology/adserp-vs-ao-corpus-differences.md`. Timing and content
claims are AdSERP statements; structural claims have replicated.

The foraging spine and Flavor B of the CHIIR note collide with Sara's CHI27
framing at the theory level. The boundary is *how deep* (hers) versus *how you
move between patches and what each channel indexes* (here). It must be
settled with her before either abstract goes in (CHIIR 2026-10-08).

---

## 5 · Phased worklist

**Phase A — this week.** Land today's two producers with notes, gated
(engagement census is gated on the cache hash and the label producer's map;
return-is-memory is gated on the same plus zero visit-walk drift). Rewrite the
README front sections around §1. Move the retired framings to
`docs/history/`. Write `docs/foraging-constructs.md` from §2.

**Phase B — the CHIIR 2027 paper.** Decision 2026-09-14: one CHIIR
submission, the five-state / continuation paper (C/W/L and the IFT cost
model as the theory, PAI as the instrument; Leif and Duchowski as coauthors).
Leaky Cursor is not submitted. **Sara Allawati joins for orientation**
(decision later the same day): her survey-phase replication on the
AI-Overview corpus is the second corpus that makes orientation a mechanism.
CHIIR carries no AO number and says "replicates on a second corpus, in
preparation"; the AI-Overview effect (where the survey lands), depth,
give-up and scroll-or-not stay with the RMIT paper, which gets the
survey-map producer as its mechanism layer. Settle the CHI27 boundary with
Sara in the same note, and ask whether her PIs must be consulted. Decide whether the CHIIR paper adopts Flavor B; if it
does, the depletion-state predictor gets a gated producer in this repo first
(the 0.908 in the note is a scratch number) and the README points at it. Re-derive the PAI exposure ablation on the cursor-only
typed cache so the ETRA short paper has post-fix numbers.

**Phase C — the theory gap.** Fit a gain curve and a give-up threshold per
participant on the forced-choice trials (the outside option is the next
result, not reformulation, so the fit is within-page). Test whether the
depletion-state predictor is the MVT threshold in disguise. Until this lands,
the repo's language stays "depletion-state prediction", never "MVT".

**Phase D — notebook refresh.** NB37 / NB38 from the two producers; tier
re-assignment (`docs/notebook-strategy.md`); the freshness ledger in
`notebook-refresh-plan-2026-08-30.md` walked to zero stale rows; Key Claims
aggregate rebuilt.

**Phase E — archive.** `docs/history/` index; `findings.md` re-sectioned to
follow §1 (two decisions, three channels, five states) with the old numbering
preserved as anchors so external links survive.

---

## 6 · What this plan does not do

- It does not touch the CHIIR manuscript; that repo has its own framing note.
- It does not publish any PAI number before the exposure ablation is
  re-derived post-fix.
- It does not flip any private material public. The AO numbers, the RIPA2
  track and crforager's aggregates stay where they are.
