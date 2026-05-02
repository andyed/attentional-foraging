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
selection rather than dilution.

### Sensitivity test result (2026-05-02): DILUTION confirmed

`scripts/r1_intersection_sensitivity.py`. Trial sets:
- absolute: 2,719 trials
- organic: 2,650 trials (fully contained in the absolute set)
- intersection: 2,650; absolute-only-dropped: 69

| Test | n records | RIPA2 d | RIPA2 p (two-sided) |
|---|---|---|---|
| Absolute (full universe) | 6,112 | −0.055 | **1.16 × 10⁻²** |
| Absolute (intersection only) | 6,042 | −0.055 | **1.29 × 10⁻²** |
| Organic (intersection = full) | 4,134 | +0.006 | **8.03 × 10⁻¹** |
| Absolute (dropped trials only, n=69) | 70 | −0.043 | 5.23 × 10⁻¹ |

**On the same 2,650 trials, absolute attribution still produces RIPA2
p = 1.29 × 10⁻²; organic attribution on those same trials produces
p = 0.80.** The dropped 69 trials show RIPA2 p = 0.52 — they are NOT
where the per-fixation signal lives.

The collapse is caused by the attribution change itself, not by
trial selection.

**Mechanism, now resolvable:** under absolute, "rank N" pools
organic-rank-N records (predominantly will-regress in this analysis)
with ad-rank-N records (predominantly no-regress, since users rarely
return to ads). Top-of-page ads have slightly higher RIPA2 (more
arousal-inducing surfaces); pooling them into the no-regress group
inflates that group's median RIPA2, which makes the will-regress
group appear lower-RIPA2 — the legacy "shallow processing" reading.
When bbox attribution restricts to organic-only, this ad-driven
inflation in the no-regress group disappears and the per-fixation
RIPA2 differential goes to zero.

This is a clean methodological finding: **the per-fixation RIPA2
will-regress differential on AdSERP under absolute attribution was a
rank-pooling artifact driven by ad-RIPA2 inflating the no-regress
comparator group**. It is not a per-fixation arousal-amplitude
differential between will-regress and no-regress organic items.

Note that **the per-(trial, position) RIPA2 × LF/HF click-rate
quadrant strengthens under bbox** (high-LF/HF × high-RIPA2 click rate
27.9% → 33.9%; low-LF/HF × low-RIPA2 click rate 21.5% → 19.7%; lift
+14.2 pp under bbox vs +5.9 pp under absolute) — RIPA2 still carries
information at the trial-position aggregate level, just not in the
per-fixation will-regress contrast.

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
   to discriminate dilution from selection. *(Done 2026-05-02 —
   confirmed dilution; see §"Sensitivity test result" above.)*
2. Discuss with Gwizdka before locking R1 paper framing.
3. Notify Gavindya/team before standalone RIPA2 publication land if
   their draft includes the AdSERP per-fixation claim.

## Replacement findings (2026-05-02)

A scan of candidate per-(trial, organic position) predictors of
will-regress under bbox identifies several bbox-clean replacements
for the dead RIPA2 leg, surfacing a cleaner cognitive-engagement
story. Audit:
[`scripts/will_return_predictor_scan.py`](../../scripts/will_return_predictor_scan.py).
Full table at
[`docs/methodology/attribution-cascade-synthesis.md` §4.3](../methodology/attribution-cascade-synthesis.md).

Headline: **mean-based** per-fixation pupil metrics (RIPA2,
`pd_change_mean`) all collapse under bbox; **peak-based** metrics
survive.

| metric | *p* (bbox) | reading |
|---|---|---|
| `n_fix` | 3.3 × 10⁻¹⁶ | will-regress = more fixations on first-pass visit |
| `pd_change_max` | 5.1 × 10⁻⁶ | larger peak dilation events |
| `pd_change_min` | 1.9 × 10⁻⁵ | larger peak constriction events |
| `first_pd` | 5.2 × 10⁻⁷ | lower baseline pupil at visit entry |
| `mean_fix_duration` | 2.6 × 10⁻⁷ | shorter individual fixations (more scanning) |
| LF/HF | 9.5 × 10⁻⁴ | the surviving R1 leg |
| RIPA2 | 0.88 | the collapsed R1 leg |
| `pd_change_mean` | 0.84 | mean-based pupil change — same fate as RIPA2 |

**Replacement R1 framing:** "lingered first time + more pupillary
excursion + lower baseline + more brief fixations" (multi-metric)
replaces "lingered first time + processed shallowly" (joint LF/HF ×
RIPA2 mean amplitude). Every component is bbox-clean. The
cognitive-engagement story is cleaner: will-regress positions are
revisited more, more briefly each time, entered with lower pupil
baseline, and accompanied by larger peak ± arousal events.

This null lives in the file drawer with provenance until the paper
strands resolve — per the project's null-findings policy. The
replacement findings can be moved into a positive results section
once the R1 paper framing is locked.
