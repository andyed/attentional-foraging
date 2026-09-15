# Foraging constructs → observables

The single place a reader finds which saccade-level observable stands for
which foraging construct on the AdSERP corpus, and which producer emits it.
Kept current by hand; the plan that opened it is
`foraging-refresh-plan-2026-09-14.md` §2. Every producer named here follows
the gate rule: reproduce a shipped number before computing a new one.

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

## Reading the table

- **shipped** — the number is in a Key Claims block or a canonical sidecar
  under `scripts/output/` and the producer is listed in `scripts/CANONICAL.md`.
- **measured** — a producer and a note exist (`docs/ablations/`), not yet a
  Tier A/B notebook claim.
- **gap** — the construct is asserted in prose and fitted nowhere. Do not
  write it as a result.
- **not ours** — a sibling track owns it; cite, do not rebuild.
