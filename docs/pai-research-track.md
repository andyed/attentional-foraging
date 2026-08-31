# PAI research track — peripheral attention index

Status doc, started 2026-08-31. Decision (Andy): PAI work is a first-class
research thread in this repo, not a support figure for the Leaky Cursor
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

## Broader questions (beyond Leaky Cursor)

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
  a distinct claim from Leaky Cursor's cursor-geometry story.

## Boundary decisions (2026-08-31)

- **CHIIR**: PAI stays out as a contribution; at most a two-sentence
  future-work/discussion note without numbers. The paper's spine remains
  gaze-trains/cursor-runs.
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
4. Write the kernel-sensitivity note (established fact 4) into
   `docs/ablations/pai_exposure_validation.md` so the current numbers can't
   be quoted kernel-free.
