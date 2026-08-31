# PAI research track — peripheral attention index

Status doc, started 2026-08-31. Decision (Andy): PAI is a first-class
research thread in this repo, not a support figure for the Leaky Cursor
CHIIR resubmission and not necessarily the CHI LBW poster. Seek insights
broader than click prediction.

## What is established (all on the converted substrate, pinned env)

Producers: `scripts/pai_exposure_ablation.py`, `scripts/pai_preentry_probe.py`,
`scripts/render_pai_preentry_figure.py`; validation writeup
`docs/ablations/pai_exposure_validation.md`. Outputs in
`scripts/output/ablations/pai_*`. All numbers 2026-08-31,
`[LAB, AdSERP, organic_hybrid, buf500/excision]`.

1. **Pre-foveation anticipation.** At the moment the clicked result is first
   fixated, its accumulated peripheral exposure mass already ranks it above
   **91.3 %** (exact-AOI) / **95.6 %** (nb35 skirt) of still-unfixated peers
   (d_z = 2.27 / 3.78). Click-specific: +4.5 / +2.8 pts over the
   next-foveated non-clicked control at its own entry (p ≈ 10⁻²⁰) — this is
   not merely "about to be looked at."
2. **Anticipation, not leakage.** PAI's click-prediction increment *grows*
   when the committed approach is excised: over position+dwell +0.006 →
   **+0.016** (p = 3.9×10⁻⁵); over the full 7-feature cursor model +0.004 →
   **+0.011** (p = 4.4×10⁻⁶); increment growth itself p = 1.3×10⁻⁴. Every
   commitment-loaded channel moves the other way.
3. **Load-bearing within gaze models.** Removing the peripheral skirt from
   position+dwell costs −0.043 AUC intact / −0.027 under excision
   (d_z ≈ −1.3).
4. **Kernel sensitivity is real and unexplained**: exact-AOI vs the ad-hoc
   nb35 skirt give materially different pre-entry numbers (91.3 vs 95.6;
   probe-A AUC 0.52 vs 0.42). The kernel is currently a convenience, not a
   theory. This is the biggest open methods question and the biggest
   opportunity (see Q1).

## Broader questions (beyond Leaky Cursor)

- **Q1 — A principled kernel from cortical magnification.** Replace the
  ad-hoc skirt with an eccentricity-weighted membership function derived
  from acuity falloff / cortical magnification (the Scrutinizer machinery
  is literally this). Prediction: a CM-weighted PAI beats both current
  kernels and turns "soft AOI membership" from a hack into a
  vision-science-grounded measurement. This is the methodological
  contribution with reach beyond SERPs (ETRA-shaped; also the natural
  Duchowski collaboration surface — settle authorship before it ships).
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
- **Venue for the construct itself**: ETRA-shaped (kernel methodology +
  validation) or a vision-science venue if Q1 lands. Not decided.
- **RIPA2/Gavindya track stays separate and embargoed** — any Q5 pupil
  crossover uses LF/HF only until that clears.

## Near-term worklist

1. Q1 prototype: CM-weighted kernel, same probe harness, three-way kernel
   comparison (exact / nb35 / CM) on the pre-entry probe and the excision
   increment.
2. Q3 per-etype PAI decomposition (cheap: the exposure producer already
   walks per-record etype).
3. Anticipation-horizon curve (Q2): pre-entry mass as a function of time
   before first entry, clicked vs control.
4. Write the kernel-sensitivity note (established fact 4) into
   `docs/ablations/pai_exposure_validation.md` so the current numbers can't
   be quoted kernel-free.
