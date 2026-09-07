# Cursor-label ranking: nested supervision audit

**September 7, 2026 — [LAB, AdSERP, typed].**

## The discovered dependency

The September 6 ranking run used one global leave-one-participant-out vector
of predicted gaze-regression labels. It then reused that vector in every
outer participant-held-out LambdaMART fold. The two individually held-out
procedures were not nested.

For an outer test participant **P**, consider the ranker's training labels for
participant **Q**. Q's labeler was trained on every participant except Q,
including P. P's gaze labels could therefore influence Q's predicted grades,
which then trained the ranker evaluated on P. P's gaze need not enter the
ranker directly for this dependence to break the intended held-out protocol.

The source path is explicit:

- `ltr_cursor_only_four_grades.py` computes the global deferred predictions
  before entering `loso_lambdamart`.
- `ltr_typed_four_distinct_grades.py::loso_deployable_classifier_predictions`
  fits each labeler using `(pid != p) & approached_mask`.
- The outer ranker loop drops its test participant from ranker fitting, but
  does not reconstruct the already-computed training grades.

This establishes a validation defect, not its numerical effect. The original
cursor-label lift may be inflated, unchanged, or lower after nesting. Its
retained +0.0046 four-grade MRR@10 difference remains a **non-nested diagnostic**
and is superseded for the held-out comparison by the corrected run below. The direct gaze-label rankers and
binary-click baselines do not use this generated-label path. The standalone
deferred classifier's own LOSO evaluation is also a separate experiment.

## Corrected protocol

The separate [nested producer](../../scripts/ltr_cursor_only_nested_grades.py)
keeps the seven cursor features, press-anchored 500 ms cutoff, AOIs, click
labels, ranker settings, and 0.5 deferred-label threshold fixed. For each outer
test participant P, it generates ranker training grades using only the outer
training participants. Each inner labeler for Q excludes **both P and Q**;
scaling is fit on those same inner training rows. The ranker then trains on
those grades and scores P's AOIs against the observed click.

No outer-test gaze label is needed for either the inner labelers or ranker
training. Perturbing all of P's gaze labels must leave its outer training
grades unchanged. That invariance is a regression-test requirement, alongside
the existing grade and candidate-population rules.

The original producer and aggregate are retained so their provenance remains
reproducible. Its cursor-label feature-drop results also retain their original
non-nested protocol; they must not be presented as nested ablations.

## Results and retained evidence

The [corrected aggregate](../../scripts/output/ltr_cursor_only_nested_grades/summary_buf500.json)
retains **2,608 trials / 34,328 scored AOI rows / 47 participants**, with 46
inner training participants in each outer fold. The five noncursor result
rows (position, binary LR, binary LambdaMART, and both gaze-grade rankers)
reproduce the original metrics exactly, including their ad/organic slices.

| Supervision / model | Original MRR@10 | Nested-run MRR@10 | Difference from binary LambdaMART |
|---|---:|---:|---:|
| Binary-click LambdaMART | 0.774191 | 0.774191 | +0.000000 |
| Cursor, three grades | 0.775815 | 0.779716 | +0.005525 |
| Cursor, four grades | 0.778818 | 0.779158 | +0.004966 |
| Gaze, four grades | 0.785635 | 0.785635 | +0.011444 |
| Binary-click logistic regression | 0.783732 | 0.783732 | +0.009540 |

The cursor-label gain survives the corrected split, but the grade comparison
changes: three grades are numerically ahead of four by **0.000558 MRR@10**.
The fourth cursor grade therefore has no observed advantage in this run.
Binary logistic regression remains above both cursor-label rankers. These
are numerical differences without a new ranking-uncertainty test; they do
not establish superiority beyond this cohort.

Five regression tests pass, covering held-out gaze perturbations, held-out
feature/scaling perturbations, exclusion in every inner fit, exact 0.5
grade assignment, and explicit failure for one-class training pools.
Only core comparisons were rerun. Nested cursor-label ranker feature-drop
ablations were not run; the old ablations retain their historical protocol.

```sh
.venv/bin/python -m unittest discover -s scripts -p test_ltr_cursor_only_nested_grades.py
.venv/bin/python scripts/ltr_cursor_only_nested_grades.py --no-lofo
```

All source/cache hashes are retained in the aggregate. As with other cited
outputs under the ignored `scripts/output/` directory, a later deliberate
commit must promote only this aggregate with `git add -f`, not local caches.

Aggregate SHA-256: `811e1179bd7525f652b099b7a0ad619d22cd78dcb3efb2fe1690636dbc52b101`.
Producer SHA-256: `655028a0a78960362ec0f8cded66a95288930e989c4e12dcbe4ddc9612f96cbf`.

## Remaining interpretation limits

Nesting addresses generated-label dependence across the validation split.
The target remains an observed click in one LAB cohort; the research labels
remain gaze-derived. It does not establish independent relevance, a deployed
ranker improvement, browser lifecycle parity, or transfer of M5 weights.
The existing geometry-based training-row filter is preserved to isolate this
protocol change; it is not proof that all retained rows were examined.

## Grade interpretation and next diagnostics

The [fourth-grade exploration](../null-findings/2026-09-07-cursor-fourth-grade-nested.md)
records why the reversal is not a failed four-class taxonomy: four-grade
MRR improved slightly, while three grades improved more. It separates the
observed comparison from untested explanations and specifies participant-paired
uncertainty, training-label flip tracing, and controlled-gain comparisons.
Those follow-up diagnostics have not been run.
