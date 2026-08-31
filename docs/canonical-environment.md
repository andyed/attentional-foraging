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
