# 2026-08-31 coordinate-conversion null revisit — triage

Sibling to [`2026-05-04-typed-cascade-null-revisit.md`](2026-05-04-typed-cascade-null-revisit.md),
same job for a different substrate event: the mouse-stream coordinate-space
conversion (document → screenshot space; click-in-AOI containment
78.0 % → 96.2 %) plus the re-attributed click labels it brings (+6.3 %
clicked records on `organic_hybrid` buf500). The conversion moved the §4.1
headline +0.057 AUC and attenuated the LTR graded lift ~10×, so every null
that leans on **cursor features or click labels** must be re-checked before
it is cited or silently trusted. Gaze-side and pupil-side nulls are
unaffected in their *features* (fixations were always screenshot space) but
not automatically in click-keyed *labels*.

## Exposure classes

- **A — cursor features or click labels load-bearing → re-run.**
- **B — click-keyed labels only (gaze/pupil features) → spot-check.**
- **C — fixation/pupil-side, position-keyed → holds by construction.**

## Triage

| null finding | class | verdict / action |
|---|---|---|
| `nb26-ltr-graded-vs-binary` | A | **Re-done 2026-08-31.** Canonical re-runs make the null stronger (graded lift +0.008–0.010); labeled-subset K4 retired. Cite new numbers only. |
| `2026-04-20-rung4-rank-within-trial` | A | **HIGH — re-run first.** The null (dense rank-within-trial labels lose) likely holds, but its *positive companion* — hybrid label with click pinned at 9, **+0.143 MRR** — is a headline-sized claim sitting on pre-conversion features AND pre-conversion labels, in the exact family that just attenuated 10×. Not citable until re-derived. |
| `2026-05-05-bbox-y-coverage` | A | **HIGH — AllSERP v4 critical path.** The 22.7 % contamination figure, the +155 recovered clicks, and the four cite-ready audits (`audit_unattributed_clicks.py` etc.) all quantify the *pre-conversion* click-attribution layer. The conversion attacks the same layer from the other side (+162 clicks on organic_hybrid). v4's data statement must not quote these audits until they're re-run on converted coords — and the interesting question is whether conversion shrinks the residual gapfill recovers. |
| `2026-04-12-ski-jump-audit-collapse` | A/B | **MEDIUM.** Itself a coordinate-audit null (stay dead, almost surely), but the surviving cohort-A ski-jump (n = 131, findings.md §0) is click-rank-keyed — re-check under converted attribution before it is cited again. NB23's Aug 30 typed re-run partially covers this. |
| `2026-04-26-pos9-fixation-uptick-collapse` | C | Holds — fixation-side, participant-clustering kill is protocol-level. |
| `2026-04-15-novelty-baseline-residual-redundancy` | C | Holds — content embeddings vs dwell, no cursor path. |
| `2026-04-16-satopt-lhipa-duration-confound` | C | Holds — pupil × duration. |
| `2026-04-19-lfhf-*` (crossover, satopt-orthogonality, viewport-strat) | C | Hold — pupil-side, position-keyed. Typed-cascade revisit already re-verified the load-bearing two. |
| `2026-04-19-nb14-plateau-concentration-audit` | C | Holds — pupil × position medians. |
| `2026-05-02-lfhf-leakage-check`, `2026-05-02-peri-click-ripa2-sg-leakage` | B | Time-domain click keying only (t_click unchanged by conversion) — hold. |
| `r1-ripa2-bbox-collapse` | B/C | Fixation-attribution based; AOI maps unchanged by conversion. Holds (embargoed track anyway). |
| `2026-05-24-long-regression-rate-not-trait` | C | Gaze-regression based — holds. |
| `2026-06-07-ad-capture-vs-engagement-lfhf` | B | LF/HF features safe; if any split keys on was_clicked, spot-check the n's. |
| `2026-07-25-survey-reentry-on-regression` | C | Saccade-amplitude based — holds. |
| `nb29-viewport-bands-content-residualization` | B | Bands re-derived in the Aug 30 typed re-runs (NB28/NB30); content null itself is content-side. Holds. |
| `lfhf-window-duration-confound` (2026-08-18) | C | Pupil windowing — holds. |
| `priming-null-result` | C | Historical, superseded by framework compilation. Holds. |

## Bottom line

Two re-runs are load-bearing and urgent: **rung-4's hybrid-label +0.143
companion** (cite-blocked until re-derived; feeds the CHIIR LTR story) and
**the bbox-y-coverage audit quartet** (cite-blocked for AllSERP v4's data
statement). Everything pupil/gaze-side holds by construction, consistent
with the typed-cascade revisit's conclusion that substrate hygiene moves
measurement quality, not the cognitive findings.

## PAI refresh (same pass, positive-side)

`pai_preentry_probe.py` re-run on converted substrate: the anticipation
pole **survives and strengthens** — clicked result beats 91.3 % (exact) /
95.6 % (nb35) of still-unfixated peers at shared cutoff (d_z = 2.27 / 3.78),
click-specific delta over the next-foveated control +4.5 / +2.8 pts
(p ≈ 10⁻²⁰). Poster text's "92.7 %" needs the updated pair. 
`pai_exposure_ablation.py` printed its grid (Pp increment over M3-7:
+0.008 intact → +0.015 under excision — grows, as the anticipation story
requires) but **aborted at its anchor check** (buf500 M2 0.8194 vs
published 0.7636) — the honesty guard tripping on the stale anchor, same as
`viewport_exposure_ablation.py`. Paired stats pend a deliberate re-anchor
of the published-grid constants.
