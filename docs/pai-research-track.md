# PAI research track — peripheral attention index

Status doc, started 2026-08-31. Decision (Andy): PAI work is a first-class
research thread in this repo, not a support figure for the cursor methods
CHIIR resubmission and not necessarily the CHI LBW poster. Seek insights
broader than click prediction.

**Attribution — read first.** PAI is **Duchowski, Gehrer & Svaldi's
method** (*Peripheral Attention Index (PAI): Area-Weighted Distal Polygonal
Areas Of Interest*, to appear, ETTAC 2026 / ICPR Workshops, Lyon). This
repo's role is application and validation on AdSERP (the census notebooks
NB33–NB35, `docs/pai-census-note.md`, posted for the ETTAC session) plus a
**spec-exact implementation** from the authors' manuscript (received
2026-08-31): `scripts/pai_spec.py`, verified by `scripts/pai_spec_test.py`.
It supersedes NB35's abstract-derived variant; manuscript-equation vs
Listing-1.1 discrepancies are exposed as options and have been raised with
the authors. Extensions to the method are joint-work territory, not solo
contributions.

## What is established (all on the converted substrate, pinned env)

Producers: `scripts/pai_exposure_ablation.py`, `scripts/pai_preentry_probe.py`,
`scripts/render_pai_preentry_figure.py`; validation writeup
`docs/ablations/pai_exposure_validation.md`. Outputs in
`scripts/output/ablations/pai_*`. All numbers 2026-08-31,
`[LAB, AdSERP, organic_hybrid, buf500/excision]`.

1. **Anticipation, not leakage — restated under the spec 2026-08-31 and
   STRONGER.** The peripheral-mass click-prediction increment *grows* when
   the committed approach is excised, and the spec-eq2 kernel carries more
   of it than the demo kernel: over position+dwell, spec-eq2 +0.019 →
   **+0.032** (exact: +0.006 → +0.016); over the full 7-feature cursor
   model, spec-eq2 +0.0052 → **+0.0156** (exact: +0.0042 → +0.0107);
   increment-growth p ≈ 7×10⁻⁷ (spec) vs 1.3×10⁻⁴ (exact). The two spec
   options (Eq-2 vs Listing-1.1 weight placement) agree to ≲0.002 AUC —
   the manuscript's D2 ambiguity is immaterial at the model level.
2. **The pre-entry rank headline was kernel-direction-dependent and is
   RETIRED as a PAI claim.** Under the authors' Eq. 2 the clicked result
   beats only **43.2 %** (spec_eq2) / **37.1 %** (spec_listing) of
   still-unfixated peers — the demo kernel's 91.3/95.6 % reversed sign,
   and the click-specific delta flips to −12.5/−13.8 pts. Mechanism: the
   demo weight (A_max/A)^0.236 suppresses small AOIs; the published
   min(1, A/A_max) boosts them, and within-trial rank is dominated by
   that direction. The information is still there (model AUC increments
   above are *larger* under spec) — but the sign story belongs to the
   kernel, not the periphery. Full analysis:
   `docs/ablations/pai_exposure_validation.md` §Addendum 2026-08-31.
3. **Load-bearing within gaze models.** Removing the peripheral skirt from
   position+dwell costs −0.043 AUC intact / −0.027 under excision
   (d_z ≈ −1.3). [exact kernel; not re-derived — the spec analog is the
   M2+PpS − M2 increment above.]
4. **Kernel naming is hard policy.** Every quoted number names its kernel
   (`exact` / `nb35` / `spec_eq2` / `spec_listing`); bare "PAI" means
   `spec_eq2`. Rank-space statistics reverse sign between demo and
   published kernels; sign-free model increments do not. Pre-spec outputs
   preserved as `scripts/output/ablations/*-prespec-20260831.*`.

## Broader questions (beyond the cursor methods paper)

- **Q1 — Kernel comparison under the spec, then the CM proposal.** First,
  three-way comparison on the probe harness: spec-exact `pai_spec.py`
  (both manuscript and Listing-1.1 options) vs the exact/nb35 variants —
  does the authors' area-weighted distal-polygon design close or widen the
  91.3-vs-95.6 gap? Then, as a **proposed joint extension with the
  authors**: an eccentricity/cortical-magnification-weighted membership
  function (the Scrutinizer machinery is literally this) as a
  vision-science-grounded refinement of the distal weighting. Duchowski is
  the natural co-author, not a courtesy — it's his method.
- **Q2 — Anticipation horizon and dynamics.** How long before first entry
  does the clicked item's peripheral mass separate from peers? Rise shape,
  decay after retreat, relation to saccade landing-site selection. Connects
  to the task-model paper's Survey/Evaluate phases: is PAI the observable of
  the survey "shadow" running ahead of foveation?
- **Q3 — Peripheral rejection of ads.** Per-etype PAI: do `native_ad` /
  `dd_top` / `dd_right` accumulate peripheral mass and then *not* get
  fixated (banner blindness as measured peripheral-intake-without-entry),
  or never accumulate at all (true invisibility)? dd_right's 103 captured
  clicks vs 861 present blocks gives the denominator. This is an ad-science
  insight independent of click prediction.
- **Q4 — Saliency vs task.** Does pre-entry mass track bottom-up saliency
  or task relevance? The four-class taxonomy + LTR machinery supply
  relevance labels; a saliency map over the SERP screenshots supplies the
  competitor. Separating them says what the periphery is *for* during SERP
  evaluation.
- **Q5 — Individual differences.** Only 64 % of participants show
  pre-entry AUC > 0.5 on the exact kernel; per-participant spread IQR
  0.268–0.324 in the calibration audit. Trait-like peripheral reliance?
  Cross with the satopt/speed terciles (mind the known redundancy,
  Cramér's V = 0.503) and, carefully, the LF/HF trait axis.
- **Q6 — The WILD analog.** PAI is gaze-only and stays `[LAB]`. Its
  deployable shadow is viewport exposure (E / E-any) — "peripheral" at the
  scroll level, which held 0.596 under full excision. Characterizing E as a
  degraded PAI (what fraction of the anticipation signal survives at
  viewport granularity?) is the bridge that would matter for deployment —
  a distinct claim from the cursor methods paper's geometry story.

## First results on Q2/Q3 (2026-08-31, spec_eq2, full trial)

Producer: `scripts/pai_etype_census.py` →
`scripts/output/ablations/pai_etype_census.json`. Never-fixated AOIs are
enumerated from `build_hybrid_aois()` (the feature file only carries
fixated slots). Regime `[LAB, AdSERP, organic_hybrid]`.

**Q3 — banner blindness is peripheral rejection, not invisibility.**

| etype | n AOIs | entry % | click % | med mass entered | med mass never-entered | never-entered above entered-median |
|---|---|---|---|---|---|---|
| organic | 26,571 | 55.2 | 8.6 | 7,495 | 4,872 | **30.6 %** |
| native_ad | 9,211 | 39.8 | 2.0 | 7,440 | 5,351 | **33.2 %** |
| dd_top | 1,582 | 99.9 | 17.3 | 2,256 | 981 | 0.0 |

A third of never-fixated ads (and organics) carry more peripheral PAI mass
than the *median fixated* AOI of their type — they are peripherally
sampled and then not visited. Caveats: cross-etype mass comparisons are
geometry-confounded (page position, area — dd_top's low masses are a
top-of-page artifact); the load-bearing contrast is entered vs
never-entered *within* etype. Next: normalize by an exposure-opportunity
baseline before claiming rejection rates.

**Q2 — the clicked item's peripheral intake is late-concentrated.**
Median cumulative share of pre-entry mass (500 ms bins, 8 s window before
each AOI's own first entry): clicked items reach half their pre-entry mass
only ≈ **2.25 s before entry** (28 % accumulated by −4 s), while
entered-non-clicked items accrue diffusely (t50 ≈ −3.75 s; 51 % by −4 s).
n = 2,355 clicked / 15,718 non-clicked records. The dissociation is in the
*shape* (curves are within-record normalized), not the amount: peripheral
intake on the future click target ramps as the decision approaches.
Caveat: window truncation at trial start can differ between the groups —
re-check with trial-time controls before this becomes a claim.

## Deferred-class probe (2026-09-14, post-fix substrate)

`scripts/pai_deferred_probe.py` → `docs/ablations/pai_deferred_probe.md`.
Scored on the CHIIR carve's own 9,269 label-complete rows (cursor-only typed
mousedown cache, label producer's map, gate reproduces M4-7 0.6802). On
untruncated 1 s post-exit windows, peripheral intake adds −0.000 paired AUC
over the seven-feature cursor vector under an eccentricity-aware kernel
(the published kernel's +0.010 was page-wide fixation duration: see the
kernel finding below). The truncated-window run (+0.022) is window-length
leakage and is not quotable. **CHIIR boundary confirmed on
evidence: PAI stays out.** The finding is a Q2/Q6 item for the ETRA 2027
short paper (due 2027-02-11) with the authors.

**Return mechanism (2026-09-14):** `scripts/return_is_memory.py` →
`docs/ablations/return_is_memory.md`. Long gaze returns (≥ 2 ranks, n = 1,774)
land at first-entry precision from 2.4× the distance with *half* the
peripheral intake on the target (78 vs 148 mass/s under the boundary
kernel, CI [−75, −50]), and precision does not covary with that intake
(ρ −0.001). Memory-guided. This is the Q2 answer for the deferred class.

**Kernel finding (2026-09-14, load-bearing):** the published Eq. 2 alpha is
nearly flat in eccentricity on SERP result bands (corpus Spearman with
boundary distance −0.08; `scripts/peripheral_kernel.py` docstring,
`docs/ablations/engagement_state_census.md`). Every PAI number on this
corpus is reported beside a gated or boundary-distance variant; the
boundary-distance cortical-magnification falloff is the Q1 proposal, now
with a concrete reason.

**Re-derivation debt:** everything in `pai_exposure_validation.md` and
`pai_preentry_probe.json` predates the 09-04 lineage audit and the 09-13
carve fix (organic_hybrid bands, gaze-selected feature caches). Re-run the
exposure ablation on the cursor-only typed cache before quoting any of it.

## Boundary decisions (2026-08-31)

- **CHIIR**: PAI stays out as a contribution; at most a two-sentence
  future-work/discussion note without numbers. The paper's spine remains
  gaze-trains/cursor-runs. *Re-confirmed 2026-09-14 on post-fix evidence
  (deferred-class probe above).*
- **CHI LBW poster**: optional, no longer load-bearing. If it ships, it is
  the descriptive/outreach vehicle and cites whatever the PAI track
  publishes, not the reverse.
- **Venue**: the construct belongs to the ETTAC 2026 paper (Duchowski et
  al.). AF's census/validation work and any CM extension are ETRA-shaped —
  scoped and authored with the method's authors. Not decided.
- **RIPA2/Gavindya track stays separate and embargoed** — any Q5 pupil
  crossover uses LF/HF only until that clears.

## Near-term worklist

0. ~~Spec-exact re-derivation~~ **DONE 2026-08-31.** Both producers carry
   all four kernels; §established rewritten from the spec runs. Outcome:
   model-level claims strengthened, pre-entry rank claim retired
   (sign flip — see §established 2 and the validation addendum).
1. Q1 comparison: ~~spec vs exact vs nb35 on the probe harness~~ done as
   part of item 0 (the four-kernel probe/ablation runs ARE the
   comparison). Remaining: draft the CM-weighted proposal for the
   authors — now with the sharpened framing that the area-weight
   *direction* dominates within-page rank, which is precisely the slot a
   cortical-magnification-grounded weight would fill on principled
   grounds instead of convention.
2. Q3 per-etype PAI decomposition (cheap: the exposure producer already
   walks per-record etype).
3. Anticipation-horizon curve (Q2): pre-entry mass as a function of time
   before first entry, clicked vs control.
4. Re-derive `pai_exposure_ablation.py` on the cursor-only typed mousedown
   cache with the carve gate (the 08-31 increments are over retired rows).
5. Write the kernel-sensitivity note (established fact 4) into
   `docs/ablations/pai_exposure_validation.md` so the current numbers can't
   be quoted kernel-free.
