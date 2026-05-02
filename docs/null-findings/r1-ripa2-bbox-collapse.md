# R1 RIPA2-leg dissociation collapses under bbox attribution

**Date observed:** 2026-05-02
**Stable ID:** `null:r1-ripa2-bbox-collapse`
**Cross-link:** [`docs/methodology/attribution-cascade-synthesis.md §2.4`](../methodology/attribution-cascade-synthesis.md)

---

## What was claimed under absolute attribution

The R1 dissociation: **same per-(trial, position) records, opposite
metric directions.** Items the user *later returned to* (will-regress,
n=3,075) showed:

- **Higher LF/HF** (sustained autonomic engagement) — d = +0.041, p = 0.011
  — interpreted as "lingered first time"
- **Lower RIPA2** (per-fixation arousal amplitude) — d = +0.006, p = 0.0058
  — interpreted as "processed shallowly"

The joint signature was the headline: *items the user returned to were
lingered-on but processed shallowly the first time*. This was a load-bearing
result for both the R1 paper (with Gwizdka) and the standalone RIPA2
publication track (with Gavindya/team).

Reference: legacy values per the JEMR-2025 RIPA2 implementation-bug fix
audit (commit window 2026-04-25, see `references_jayawardena_jemr_2025_ripa2.md`).

## What happens under bbox-organic attribution

| Metric | will-regress (n=3,075) | no-regress (n=1,059) | d | p | verdict |
|---|---|---|---|---|---|
| LF/HF (median) | 20.17 | 17.26 | +0.041 | **1.1 × 10⁻³** | preserved |
| RIPA2 (median) | 0.000414 | 0.000409 | +0.006 | **8.0 × 10⁻¹** | **collapsed** |

LF/HF leg passes a *stronger* significance test under bbox (p = 1.1e-03
vs absolute's p = 0.011) despite the smaller N. RIPA2 leg goes from
p = 0.0058 to p = 0.80 — a five-orders-of-magnitude shift in
significance with effect size ostensibly unchanged at d = +0.006.

Source: `scripts/output/ripa2_meet_visuals/r1_dissociation.png` and
`r1_2x2_dissociation.png` regenerated 2026-05-02 against
`AdSERP/data/butterworth-lfhf-by-position-organic.json` and
`ripa2-by-position-organic.json`.

## Interpretation

The most parsimonious reading is that **the legacy p = 0.0058 was a
rank-pooling artifact**. Under absolute attribution, the will-regress
and no-regress fixation pools were drawn from a mixed ad+organic set
where the rank label was pooling two different surfaces. Per-fixation
RIPA2 differences between the pools were inflated by the structural
heterogeneity, not by a true per-fixation arousal-amplitude
differential.

Under bbox attribution, fixations are cleanly attributed to a specific
organic AOI; the will-regress vs no-regress split happens within a
homogeneous pool; per-fixation RIPA2 values are essentially identical
between the groups (medians differ by 1.2%).

**Alternative reading** (worth examining): bbox attribution drops
~10% of trials and ~13% of segments. If the dropped trials carried
the bulk of the RIPA2 differential — e.g., trials where every visited
position was an ad, which happen on commercially-loaded SERPs that
also produce stronger arousal differentials — the collapse could be
selection rather than dilution. **Test:** rerun the R1 split on the
intersection-of-trials set (trials present in both attributions) under
both methods; if RIPA2 p stays ≈ 0.005 under absolute on the smaller
trial set but flat under bbox, dilution; if both flatten, selection.

## Implication for paper strands

- **R1 paper (Gwizdka collaboration):** the joint LF/HF × RIPA2
  signature claim does not survive. Either (a) publish the LF/HF leg
  alone with the RIPA2 leg as a sensitivity finding, or (b) hold
  absolute as primary attribution and document bbox as the boundary
  condition.
- **Standalone RIPA2 publication track (Gavindya/team):** the per-fixation
  amplitude differential between will-regress and no-regress items on
  AdSERP under bbox attribution is **n.s.**; that specific empirical
  claim should not appear in the standalone paper. Per-fixation RIPA2
  may still hold for other contrasts (e.g., peri-click TEPR; per-trial
  cognitive load gradient).
- **ETTAC paper:** unaffected — the LF/HF leg is the ETTAC story, and
  it survives.

## What this is NOT

- This is not a bug in the RIPA2 implementation. The 2026-04-25
  implementation fix (`SG_LF² − SG_VLF²`, not `(SG·P)² − ...`)
  reproduces across four sites; per-fixation values are stable.
- This is not a finding that RIPA2 is invalid. The peri-click TEPR
  finding (p = 3.3 × 10⁻²¹, N = 2,662) is unaffected; the per-(trial,
  position) load gradient finding (p = 0.0058) is unaffected. Only
  the *will-regress vs no-regress per-fixation amplitude differential*
  is null under bbox.

## Resolution path (recommended)

1. Run the intersection-of-trials sensitivity check described above
   to discriminate dilution from selection.
2. Discuss with Gwizdka before locking R1 paper framing.
3. Notify Gavindya/team before standalone RIPA2 publication land if
   their draft includes the AdSERP per-fixation claim.

This null lives in the file drawer with provenance until the paper
strands resolve — per the project's null-findings policy.
