# M4 same-target learned controls

**Stable ID:** M:m4-same-target-learned-baselines
**Status:** current as of 2026-09-12; canonical implementation: `scripts/m4_same_target_learned_baselines.py`

Full-corpus result. Regime and rank type:
`[LAB, AdSERP, typed]`.

## Question

Does the canonical seven-scalar, per-result M4 representation outperform
learned alternatives when the candidate rows, click target, cursor cutoff, and
participant-held-out evaluation are held fixed?

This is an architecture-inspired control, not a reproduction of the published
session, abandonment, or AdSight models.  Those models use different targets
and candidate populations.

## Fixed protocol

- 2,608 included trials, 34,328 per-AOI rows, one final-click label per trial,
  and 47 participants from the canonical typed M4 result.
- Native `mousemove` samples with `t < mousedown - 500 ms`.
- The canonical producer, AOI substrate, click attribution, exclusions, record
  keys, and labels are hash-checked before the learned controls run.
- Cursor traces are interpolated on clock time to 64 steps.  Global inputs are
  normalized vertical cursor position and velocity.  Candidate-relative inputs
  are absolute cursor-to-AOI-center distance and signed approach velocity.
- Every reported model uses the same 47-fold leave-one-participant-out split.
  Metrics are pooled out-of-fold ROC-AUC and average precision plus per-trial
  MRR@10 and NDCG@1 (top-1 click rate).

## Controls

1. **M4 LR** is the canonical linear classifier on the seven screened M4
   scalars.
2. **M4 LightGBM** changes model capacity while keeping the seven scalars.
3. **Relative ordered trace** applies the same fixed LightGBM configuration to
   the flattened 64-step candidate-relative distance/velocity sequence.
4. **Global ordered trace** applies that configuration to the flattened global
   cursor sequence plus the candidate AOI center.  Rows from the same trial
   share the trajectory; only the center changes by candidate.

The ordered-trace controls intentionally retain the last sample before the
500-ms cutoff.  This is the literal same-stream comparison, but it is not the
same *leakage screen* as M4: a learner can reconstruct the excluded
`final_dist` cue from the terminal sequence element.

All LightGBM controls use 200 trees, learning rate 0.05, 15 leaves, minimum 100
child samples, L2 regularization 1.0, balanced class weights, deterministic
column-wise fitting, and one thread.  These settings are fixed across the two
ordered-trace representations.

## Full-corpus result

| Model | ROC-AUC | Average precision | MRR@10 | NDCG@1 |
|---|---:|---:|---:|---:|
| Position LR | 0.7918 | 0.1825 | 0.4471 | 0.1975 |
| M4 LR, seven screened scalars | 0.9348 | 0.5056 | 0.7773 | 0.6338 |
| M4 LightGBM, same seven scalars | 0.9435 | 0.6040 | 0.7895 | 0.6499 |
| Global ordered trace + AOI center | 0.9886 | 0.8691 | 0.9380 | 0.8842 |
| Candidate-relative ordered trace | 0.9916 | 0.9119 | 0.9515 | 0.9087 |

Paired participant-AUC comparisons (10,000-resample participant bootstrap;
two-sided Wilcoxon signed-rank):

| Contrast | Mean delta AUC | 95% bootstrap CI | Wilcoxon p |
|---|---:|---:|---:|
| M4 LightGBM - M4 LR | +0.0079 | [+0.0056, +0.0101] | 1.2e-7 |
| Relative ordered trace - M4 LR | +0.0552 | [+0.0492, +0.0614] | 1.4e-14 |
| Global ordered trace - M4 LR | +0.0522 | [+0.0461, +0.0587] | 1.4e-14 |
| Relative ordered trace - global ordered trace | +0.0030 | [+0.0019, +0.0042] | 7.6e-8 |

## What the result establishes

- **Model capacity matters modestly on the screened M4 vector.** Replacing LR
  with LightGBM adds 0.008 mean participant AUC and 0.098 average precision.
- **M4 is not the best predictor under the literal same-stream comparison.**
  Both ordered-trace learners exceed 0.988 pooled AUC.
- **Candidate-relative conditioning helps, but only slightly once endpoint
  access is shared.** Its paired advantage over the global decoder is 0.003
  AUC, with +0.0135 MRR@10 and +0.0245 top-1 click rate descriptively.
- **The endpoint cue dominates this comparison.** The canonical full-corpus
  M4-9 leakage diagnostic, which merely restores `final_dist` and
  `retreat_dist`, already reaches 0.9903 AUC and 0.9064 NDCG@1 at the same
  500-ms cutoff.  The ordered learners' 0.989-0.992 range is therefore not
  evidence that sequence grain recovers deliberation better; it is consistent
  with learning terminal motor targeting.

## Claim boundary

The control is useful precisely because it prevents two overclaims.  We cannot
say that compact M4 is predictively superior to a learned trajectory model on
the same raw stream, and the 0.003 relative-vs-global gap does not establish
universal superiority of the per-result grain.  The paper should keep RQ1
narrow: M4 beats the stated matched simple baselines and a nonlinear estimator
on the screened vector improves it modestly.  A decisive grain comparison
would require the same target, candidate population, split, and a shared
pre-decision or endpoint-leakage control for both representations.

## Withdrawn optimization pilot

An optional terminal-index-blind circular TCN was explored to equalize the
endpoint screen.  Its initial 20-epoch full-corpus run is not a result: 23 of
47 relative folds and 37 of 47 global folds hit the epoch ceiling.  Extending a
capped relative fold raised inner-validation AUC from 0.842 at epoch 20 to
0.929 at epoch 60 and 0.980 at epoch 93 under a faster optimizer.  The pilot was
therefore undertrained, and its outer-fold metrics must not be quoted.  The
code and ignored checkpoints are retained only to document the failed route.

## Reproduction

```bash
uv run --extra learned-baselines python scripts/m4_same_target_learned_baselines.py
.venv/bin/python -m unittest discover -s scripts -p 'test_m4_same_target_learned_baselines.py'
```

Aggregate output and derived caches are ignored by repository policy and live
under `scripts/output/m4_same_target_learned/`.  The full summary records the
canonical sidecar hash, six source/substrate hashes, the prepared-cache hash,
the record-key/label hash, package versions, and the producer hash.
