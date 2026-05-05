"""LambdaMART with continuous p_click gain — flavor (2) of the
"click probability as label" proposal.

Question: does continuous p_click (from a held-out teacher LR) used as
the LTR gain beat the binary-click LambdaMART baseline?

Setup:
  - Teacher: LOSO LR (M3 features) → out-of-fold p_click for every record.
    Each record's p_click is from an LR trained on participants other
    than its own — so when LambdaMART trains on a non-test participant
    set, the labels are mostly from LRs that did not see those records
    (mild residual leakage at the participant boundary; negligible).
  - Discretization: round(p_click * 31) → integer label in [0, 31];
    LightGBM's lambdarank objective expects integer relevance grades.
    32 grades is ~3x denser than NB26's 10-grade hybrid label.
  - Student: LambdaMART (LightGBM LGBMRanker) trained per LOSO fold on
    the same M3 features. Reports NDCG@5 / NDCG@all / MRR per trial.

Comparison: flavor-1 LambdaMART (binary click gain) result was:
  NDCG@5 = 0.8376, NDCG@all = 0.8516, MRR = 0.8029.
Pointwise LR M3 baseline:
  NDCG@5 = 0.8221, NDCG@all = 0.8395, MRR = 0.7872.

If flavor-2 lands meaningfully above 0.8029 MRR, the continuous-gain
story is real and supersedes the discrete-grade label decision.

Run:
  .venv/bin/python scripts/lambdamart_continuous_gain_organic.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from lightgbm import LGBMRanker
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ndcg_score
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'

M4 = ['min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
      'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
      'direction_changes', 'frac_decreasing']
# Migrated 2026-05-05: typed cascade + Peter's no-position spec.
M3 = ['total_dwell_ms'] + M4

GRADE_K = 31  # discretization: label = round(p_click * GRADE_K), 32 grades


def contiguous_group_sizes(tid_arr):
    sizes, last = [], None
    for t in tid_arr:
        if t != last:
            sizes.append(1); last = t
        else:
            sizes[-1] += 1
    return sizes


def per_trial_metrics(scores, y, tid_arr, k=5):
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        by_trial[t].append(i)
    ndcgs, mrrs = [], []
    for t, idxs in by_trial.items():
        if len(idxs) < 2 or y[idxs].sum() == 0:
            continue
        s = scores[idxs]; gold = y[idxs].astype(float)
        ndcgs.append(ndcg_score([gold], [s], k=min(k, len(idxs))))
        order = np.argsort(-s, kind='stable')
        ranked = gold[order]
        for r, v in enumerate(ranked, start=1):
            if v > 0:
                mrrs.append(1.0 / r); break
    return np.array(ndcgs), np.array(mrrs)


def loso_lambdamart(X, labels_int, tid, pid, n_estimators=200,
                    label_gain=None, max_label=None):
    pooled = np.zeros(len(labels_int), dtype=float)
    parts = np.unique(pid)
    for i, p in enumerate(parts):
        train_mask = pid != p
        test_mask = pid == p
        X_tr = X[train_mask]; y_tr = labels_int[train_mask]; tid_tr = tid[train_mask]
        sizes = contiguous_group_sizes(tid_tr)
        kwargs = dict(
            objective='lambdarank',
            metric='ndcg',
            n_estimators=n_estimators,
            learning_rate=0.05,
            num_leaves=31,
            min_data_in_leaf=20,
            verbose=-1,
        )
        if label_gain is not None:
            kwargs['label_gain'] = label_gain
        if max_label is not None:
            kwargs['max_position'] = 10  # NDCG@10 internal
        ranker = LGBMRanker(**kwargs)
        ranker.fit(X_tr, y_tr, group=sizes)
        pooled[test_mask] = ranker.predict(X[test_mask])
        if (i + 1) % 10 == 0:
            print(f'  fold {i+1}/{len(parts)}', file=sys.stderr)
    return pooled


def main():
    print('[load] cursor-approach-features-typed.json (no-position M3)', file=sys.stderr)
    records = json.load(open(FEAT))
    tid_raw = np.array([r['trial_id'] for r in records])
    order = np.argsort(tid_raw, kind='stable')
    records = [records[i] for i in order]
    tid = np.array([r['trial_id'] for r in records])
    pid = np.array([r['trial_id'].split('-')[0] for r in records])
    X = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3] for r in records])
    y_bin = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    print(f'  records: {len(records):,}  trials: {len(np.unique(tid)):,}  '
          f'participants: {len(np.unique(pid)):,}', file=sys.stderr)
    print(f'  click-positive: {int(y_bin.sum()):,}', file=sys.stderr)

    # ── Teacher: LOSO LR p_click ──
    print('\n[teacher] LOSO LR (M3) -> OOF p_click', file=sys.stderr)
    pipe = Pipeline([
        ('s', StandardScaler()),
        ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
    ])
    p_click = cross_val_predict(pipe, X, y_bin,
                                groups=pid, cv=LeaveOneGroupOut(),
                                method='predict_proba', n_jobs=-1)[:, 1]
    print(f'  p_click distribution: min={p_click.min():.3f}  '
          f'median={np.median(p_click):.3f}  max={p_click.max():.3f}', file=sys.stderr)

    # Discretize: round(p_click * GRADE_K)
    labels_int = np.rint(p_click * GRADE_K).astype(int)
    labels_int = np.clip(labels_int, 0, GRADE_K)
    grade_dist = np.bincount(labels_int, minlength=GRADE_K + 1)
    print(f'  grade distribution (n per grade, first 5 + last 5):', file=sys.stderr)
    print(f'    grades 0-4:  {grade_dist[:5].tolist()}', file=sys.stderr)
    print(f'    grades 27-31: {grade_dist[-5:].tolist()}', file=sys.stderr)
    print(f'    grade of clicks: median={int(np.median(labels_int[y_bin==1]))}, '
          f'mean={labels_int[y_bin==1].mean():.1f}', file=sys.stderr)

    # Custom label_gain: 2^k - 1 for k in [0, GRADE_K]; capped
    label_gain = [(2.0 ** k - 1.0) if k <= 31 else (2.0 ** 31 - 1.0)
                  for k in range(GRADE_K + 1)]

    # ── Student: LambdaMART with continuous-derived integer grades ──
    print('\n[student] LOSO LambdaMART with 32-grade p_click-derived labels', file=sys.stderr)
    s_lm_cont = loso_lambdamart(X, labels_int, tid, pid,
                                n_estimators=200, label_gain=label_gain)

    # ── Reproduce flavor-1 (binary gain) for fair comparison ──
    print('\n[ref] LOSO LambdaMART with binary click gain (flavor-1 reproduce)', file=sys.stderr)
    s_lm_bin = loso_lambdamart(X, y_bin, tid, pid, n_estimators=200)

    # Pointwise LR scores already computed (p_click) — reuse
    s_lr = p_click

    print('\n=== Within-trial ranking metrics (gold = binary click; n=2,020 trials) ===\n')
    print(f'{"model":>34s}  {"NDCG@5":>10s}  {"NDCG@all":>10s}  {"MRR":>10s}')
    rows = {}
    for name, s in [
        ('LR (pointwise, M3)', s_lr),
        ('LambdaMART (binary gain, flavor-1)', s_lm_bin),
        ('LambdaMART (32-grade p_click, flavor-2)', s_lm_cont),
    ]:
        n5, mrr = per_trial_metrics(s, y_bin, tid, k=5)
        nA, _ = per_trial_metrics(s, y_bin, tid, k=10**6)
        print(f'{name:>34s}  {n5.mean():>10.4f}  {nA.mean():>10.4f}  {mrr.mean():>10.4f}')
        rows[name] = {'ndcg5': float(n5.mean()), 'ndcg_all': float(nA.mean()),
                      'mrr': float(mrr.mean()), 'n_trials': int(len(n5))}

    out = {
        'attribution': 'typed',
        'feature_set': 'M3-no-position',
        'flavor_2_setup': {
            'teacher': 'LOSO LR (M3) -> OOF p_click',
            'discretization': f'round(p_click * {GRADE_K}) -> 32 grades',
            'label_gain': '2^k - 1 capped at 2^31-1',
            'student': 'LightGBM LGBMRanker, lambdarank objective',
        },
        'metrics': rows,
        'p_click_summary': {
            'min': float(p_click.min()),
            'median': float(np.median(p_click)),
            'max': float(p_click.max()),
            'click_grade_median': int(np.median(labels_int[y_bin == 1])),
            'click_grade_mean': float(labels_int[y_bin == 1].mean()),
        },
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/lambdamart_continuous_gain_typed.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
