"""LambdaMART (LightGBM LGBMRanker) baseline for AdSERP ranking — typed cascade.

Question: does listwise LambdaRank with binary click as gain beat the
current pointwise LR (M3 features) on within-trial ranking metrics
(NDCG@k, MRR)?

This is flavor (1) of the "click probability as label" proposal:
binary click gain + listwise NDCG. Establishes whether listwise loss
alone moves the needle before flavor (2) — continuous p_click as gain —
is worth building.

Migrated 2026-05-05 to the typed-cascade dataset (cursor-approach-features-typed.json,
all 9 etypes). Now runs two conditions side-by-side:
  A) with position (deployment-flavored baseline)
  B) without position (Peter's no-position spec — content+motor signal alone)

LOSO by participant. Trial-grouped within each fold. M3 features:
position + total_dwell_ms + 9 M4 approach features.

Run:
  .venv/bin/python scripts/lambdamart_baseline_organic.py
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'

M4 = ['min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
      'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
      'direction_changes', 'frac_decreasing']
M3_WITH_POS = ['position', 'total_dwell_ms'] + M4
M3_NO_POS = ['total_dwell_ms'] + M4


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


def loso_lambdamart(X, y, tid, pid, n_estimators=200):
    pooled = np.zeros(len(y), dtype=float)
    parts = np.unique(pid)
    for i, p in enumerate(parts):
        train_mask = pid != p
        test_mask = pid == p
        # tid is already globally sorted, train subset preserves order
        X_tr = X[train_mask]; y_tr = y[train_mask]; tid_tr = tid[train_mask]
        sizes = contiguous_group_sizes(tid_tr)
        ranker = LGBMRanker(
            objective='lambdarank',
            metric='ndcg',
            n_estimators=n_estimators,
            learning_rate=0.05,
            num_leaves=31,
            min_data_in_leaf=20,
            verbose=-1,
        )
        ranker.fit(X_tr, y_tr, group=sizes)
        pooled[test_mask] = ranker.predict(X[test_mask])
        if (i + 1) % 10 == 0:
            print(f'  fold {i+1}/{len(parts)}', file=sys.stderr)
    return pooled


def loso_lr(X, y, pid):
    pooled = np.zeros(len(y), dtype=float)
    for p in np.unique(pid):
        tr = pid != p; te = pid == p
        m = Pipeline([
            ('s', StandardScaler()),
            ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
        ])
        m.fit(X[tr], y[tr])
        pooled[te] = m.predict_proba(X[te])[:, 1]
    return pooled


def main():
    print('[load] cursor-approach-features-typed.json', file=sys.stderr)
    records = json.load(open(FEAT))
    tid_raw = np.array([r['trial_id'] for r in records])
    # Sort globally by tid so groups are contiguous; tid prefix is participant
    # so this also keeps participants together.
    order = np.argsort(tid_raw, kind='stable')
    records = [records[i] for i in order]
    tid = np.array([r['trial_id'] for r in records])
    pid = np.array([r['trial_id'].split('-')[0] for r in records])
    y = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    n_trials = len(np.unique(tid))
    n_clicked_trials = len({tid[i] for i in range(len(y)) if y[i]})
    print(f'  records: {len(records):,}  trials: {n_trials:,}  '
          f'participants: {len(np.unique(pid)):,}', file=sys.stderr)
    print(f'  click-positive records: {int(y.sum()):,}  '
          f'trials with >=1 click: {n_clicked_trials:,}', file=sys.stderr)

    rows = {}
    for cond_name, feat_set in [('with_position', M3_WITH_POS),
                                 ('no_position',   M3_NO_POS)]:
        X = np.array([[float(r.get(f, 0.0) or 0.0) for f in feat_set] for r in records])
        print(f'\n────────  Condition: {cond_name}  (features: {feat_set})  ────────',
              file=sys.stderr)
        print(f'[fit] LOSO pointwise LR ({cond_name})', file=sys.stderr)
        s_lr = loso_lr(X, y, pid)
        print(f'[fit] LOSO LambdaMART ({cond_name})', file=sys.stderr)
        s_lm = loso_lambdamart(X, y, tid, pid)

        print(f'\n=== {cond_name}: within-trial metrics ===')
        print(f'{"model":>22s}  {"NDCG@5":>10s}  {"NDCG@10":>10s}  {"NDCG@all":>10s}  {"MRR":>10s}  {"n_trials":>10s}')
        rows[cond_name] = {}
        for name, s in [('LR (pointwise)', s_lr), ('LambdaMART (listwise)', s_lm)]:
            n5,  mrr  = per_trial_metrics(s, y, tid, k=5)
            n10, _    = per_trial_metrics(s, y, tid, k=10)
            nA,  _    = per_trial_metrics(s, y, tid, k=10**6)
            print(f'{name:>22s}  {n5.mean():>10.4f}  {n10.mean():>10.4f}  '
                  f'{nA.mean():>10.4f}  {mrr.mean():>10.4f}  {len(n5):>10d}')
            rows[cond_name][name] = {
                'ndcg5':   float(n5.mean()),
                'ndcg10':  float(n10.mean()),
                'ndcg_all':float(nA.mean()),
                'mrr':     float(mrr.mean()),
                'n_trials':int(len(n5)),
            }

    out = {
        'attribution': 'typed',
        'feature_sets': {'with_position': M3_WITH_POS, 'no_position': M3_NO_POS},
        'note': 'flavor-1 binary-click gain, listwise NDCG; typed cascade migration 2026-05-05.',
        'metrics': rows,
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/lambdamart_baseline_typed.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
