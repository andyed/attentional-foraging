# AllSERP enrichment v1.1.1

Typed area-of-interest (AOI) layer for the AdSERP corpus (Latifzadeh, Gwizdka & Leiva, SIGIR 2025): screenshot-anchored boxes and HTML-derived labels for every main-axis card, released as corpus CSVs and per-trial JSON. Paper: [arXiv:2605.04949](https://arxiv.org/abs/2605.04949) (v4 describes this release).

## What this release is

The collision-fixed typed maps of 2026-08-30, given their own release number. Substrate identity: 2,764 analysable trials, 12 alignment exclusions (`data/aoi-typed/alignment-exclusions.json`, rule embedded in every export summary), typed-map content hash `2cb789eb8febd234`. Every export summary stamps `allserp_release: 1.1.1`.

Relative to the `allserp-v1.1.0` tag (2026-08-28 build): card-collision fix (duplicated card boxes 454 to 0), exclusion list 14 to 12 with changed membership, and the cell-split export re-based onto the current parents so that filtering `role == parent` and `main_axis` recovers the gap-fill export exactly.

## Files

| file | rows | what |
|---|---:|---|
| `adserp_aois_by_trial_id_typed_gapfill.csv` | 36,407 | recommended default: eight main-axis element types, organic boxes extended to their shared midpoints |
| `adserp_aois_by_trial_id_typed.csv` | 36,378 | same labels, tight boxes |
| `adserp_aois_by_trial_id_organic_hybrid.csv` | 26,590 organic + ads | three labels, all-main-axis positions; independent of the HTML typing layer |
| `adserp_aois_by_trial_id_typed_gapfill_cellsplit.csv` | 43,958 | gap-fill parents plus 6,345 top-ads carousel cells (1,543 trials), 164 organic sub-cells (74 trials), 858 right-rail blocks and 184 right-rail cells |
| `alignment-exclusions.json` | 12 ids | quarantined trials and the rule that produced them |

Per-trial JSON maps live in the repository under `data/aoi-typed/` and `data/aoi-typed-gapfill/`. The AdSERP corpus itself (screenshots, HTML, telemetry) is not redistributed; get it from [Zenodo record 15236546](https://zenodo.org/records/15236546).

## Validation on this build

- Ad partition against the shipped ad rectangles: 38,250 comparisons, 0 disagreements (`scripts/validate_typed_ads_vs_shipped.py`).
- DOM fidelity harness, full corpus (`scripts/aoi_fidelity.py --all`, output `scripts/output/aoi_fidelity_full_2026-09-07.json`): recorded click inside its xpath element on 87.7 % of trials; released box matches its DOM element at IoU >= 0.5 on 90.8 %, median IoU 0.879; visible carousel card count agrees with the cell export on 29.5 % (the cell layer is the least mature tier; a DOM-derived replacement is validated but not yet adopted).
- Trial-level click filter in both coordinate spaces (`scripts/audit_trial_filter_space.py`): 91.5 % of final clicks attribute in document space, 95.7 % once evtrack clicks are converted to screenshot space.

## Licence

Code MIT. Derived data CC-BY-4.0. Cite the paper and the AdSERP corpus (`CITATION.cff`).
