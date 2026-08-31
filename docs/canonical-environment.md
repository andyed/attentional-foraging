# Canonical analysis environment

**Ruling (Andy, 2026-08-31):** the current `.venv` is the canonical environment
for every model-based number in this repo. Pinned in `requirements.lock`
(122 packages; `python -m pip freeze`). Python **3.13.11**. Key solvers:
scikit-learn **1.8.0**, LightGBM **4.6.0**, numpy **2.4.4**, scipy **1.17.1**.

## Why this exists

NB26's 2026-08-30 re-execution showed that model-based K rows do not survive
an environment change even on **byte-identical inputs**: deterministic
baselines reproduced to 4 decimals while every LR / Ridge / LambdaMART row
drifted, including a sign flip on the labeled-subset graded-vs-binary
contrast (K4, +0.0046 → −0.0049). The repo had no lockfile, so the April
environment is unrecoverable. Rule going forward:

- A model-based K row is citable only if produced in the pinned environment.
- Rebuilding `.venv` must start from `requirements.lock`
  (`uv pip install -r requirements.lock` or `python -m pip install -r`).
- Deliberate solver upgrades are a substrate event: re-pin the lock, re-run
  the affected producers, and annotate moved K rows — same protocol as an
  AOI-substrate re-derivation.

## Open decomposition experiment (unattributed drift)

The 2026-08-30/31 producer re-runs moved the LTR family a long way from the
published values: binary-click baselines rose ~+0.08–0.13 MRR@10 and the
graded-over-binary lift attenuated ~10× (e.g. 4-class vs binary LambdaMART
+0.0304 → +0.0094 at canonical buf500). Three factors changed at once:

1. classifier environment (this document),
2. the AOI substrate (y-DP realignment + card-collision fix, 12 exclusions),
3. the mouse-stream coordinate-space conversion in the feature producer
   (click-in-AOI containment 78.0 % → 96.2 %).

The likely driver is (3) — cleaner cursor features let binary clicks
near-saturate, absorbing the label-side gain — but this is **not yet
attributed**. The experiment that attributes it: re-run
`ltr_typed_four_class.py` in the canonical env on the **pre-conversion
feature file** (env new, features old ⇒ isolates the env term), then on
post-conversion features with the pre-collision-fix maps (isolates the
substrate term). Until then, treat "the graded lift shrank because the
features got better" as hypothesis, not finding.

### First result — the §4.1 headline (2026-08-31)

Run on `organic_hybrid` buf500 via the canonical harness
(`constant_ablation_common.m4_loso_eval_both`), pinned env:

| term | M4-7 AUC | M4-9 AUC | M1 (position) | n_clicks |
|---|---|---|---|---|
| published anchor | 0.847 | 0.8671 | 0.668 | 2,589 |
| stale features + pinned env (**env term**) | **0.8468** | **0.8671** | 0.6679 | 2,589 |
| converted features + pinned env (**coord term**) | **0.9040** | **0.9159** | 0.6642 | **2,751** |

- **Environment term ≈ 0** for the LR headline (anchors reproduce to
  ±0.0002). NB26's drift is a LightGBM/labeled-subset phenomenon, not
  universal.
- **Coordinate term = +0.057 AUC** on M4-7 — and it is not pure feature
  drift: the conversion re-attributes clicks (**2,589 → 2,751 clicked
  records, +6.3%**), so part of the gain is *label correction*. Every
  record's `min_dist`/`mean_dist` changed; `total_dwell_ms` (time-only)
  changed in none.
- **The §4.1 story strengthens**: M4 − M1 gap +0.179 → **+0.240**.
  Direction opposite to §4.6's graded-lift shrinkage, same mechanism —
  clean geometry helps cursor features and click labels, does nothing for
  the position baseline.
- The `CANONICAL_M4_AUC = 0.847` / `CANONICAL_M4_9_AUC = 0.8671` anchors in
  `constant_ablation_common.py` (and the sampling-rate ablation's anchor)
  now describe the **stale** substrate. Re-anchoring is a deliberate act:
  update them when the converted numbers are adopted as canonical, and
  re-run the constant sweeps + sampling ablation against the new anchor.
