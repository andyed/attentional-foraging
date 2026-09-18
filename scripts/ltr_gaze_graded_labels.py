#!/usr/bin/env python3
"""Is the graded-relevance signal there at gaze fidelity? -- LambdaMART on the
seven cursor-only features with training labels taken from gaze at the
resolution the five-state census and the return counts now give.

Same scaffold as ltr_cursor_only_nested_grades.py (cursor-only typed buf500
records, 47-fold participant LOSO, LGBMRanker lambdarank, NDCG@10 objective,
MRR@10 / NDCG@10 per trial on the binary click vector, the NotApprBelow
training exclusion held FIXED across every label scheme so only the label
changes). Gaze enters at training time only; inference is the seven cursor
features. This is the supervised ceiling question, not a deployment claim.

Label schemes (all from gaze + click; rows are the same for every scheme):
  binary            was_clicked                                   [gate]
  gaze4             4 distinct grades 3/2/1/0 (existing; 'approached' inside) [gate]
  gaze4_census      the same four grades from gaze alone: clicked 3 / deferred 2 /
                    rejected (fixated, no return) 1 / not fixated 0; no approach filter
  gaze3_census      clicked 2 / deferred 1 / everything else 0, from gaze alone
  states6           clicked 5 · deferred ≥3 visits 4 · deferred 3 · rejected 2 ·
                    peripheral 1 · unsampled / brief / never on screen 0
                    (census gate_200px states + n_visits; no cursor-approach
                    requirement: this is the gaze taxonomy as it stands)
  cost4             state → {0: never/unsampled/peripheral, 1: rejected,
                    2: deferred, 3: clicked}, label_gain = measured cost
                    tiers / 100 = [0, 5.41, 16.95, 40.52]
  dwell10           click pinned at 9; non-clicked ranked within trial by
                    total gaze dwell into grades 8..0 (zero dwell = 0);
                    LightGBM default exponential gain
  visits10          as dwell10 with n_visits (ties by dwell)
  dwell10_linear    dwell10 with linear gain [0..9]

Gate: 'LambdaMART (binary click)' and 'LambdaMART (4 distinct grades; gaze)'
reproduce scripts/output/ltr_cursor_only_nested_grades/summary_buf500.json
MRR@10 to 1e-6.

Output: scripts/output/ltr_gaze_graded_labels/summary_buf500.json
Run:    .venv/bin/python scripts/ltr_gaze_graded_labels.py
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
from lightgbm import LGBMRanker
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from ltr_typed_four_distinct_grades import (assign_four_distinct_grades,  # noqa: E402
                                            baseline_serp_scores, contiguous_group_sizes, per_trial_metrics)
from m4_cursor_aoi_rerun import APPROACH_7  # noqa: E402

CACHE = ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json'
LAB_TYPED = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
REG = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
STATES = ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv'
SHIPPED = ROOT / 'scripts/output/ltr_cursor_only_nested_grades/summary_buf500.json'
OUT = ROOT / 'scripts/output/ltr_gaze_graded_labels'
COST_MS = {'rejected': 541, 'deferred': 1695, 'clicked': 4052}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def paired_participant(mrr_a, mrr_b, tids, pids_of_trial):
    """per-participant mean of per-trial MRR, paired: a − b."""
    acc = defaultdict(lambda: [[], []])
    for t, a, b in zip(tids, mrr_a, mrr_b):
        acc[pids_of_trial[t]][0].append(a); acc[pids_of_trial[t]][1].append(b)
    d = np.array([np.mean(v[0]) - np.mean(v[1]) for v in acc.values()])
    rng = np.random.default_rng(20260917)
    boots = rng.choice(d, size=(10000, len(d)), replace=True).mean(axis=1)
    return {'n_participants': len(d), 'mean_delta': float(d.mean()),
            'bootstrap_ci95': np.quantile(boots, [.025, .975]).tolist(),
            'positive': int((d > 0).sum()),
            'wilcoxon_two_sided_p': float(wilcoxon(d).pvalue) if np.any(d) else 1.0}


def graded_ndcg(scores, gains, tid_arr, k=10, keep=None):
    """NDCG@k per trial against a graded relevance vector (gaze census grades),
    over every main-axis AOI; trials with fewer than two AOIs or all-zero gains skipped."""
    from sklearn.metrics import ndcg_score
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        if keep is None or keep[i]:
            by_trial[t].append(i)
    out, tids = [], []
    for t in sorted(by_trial):
        idx = by_trial[t]
        g = gains[idx].astype(float)
        if len(idx) < 2 or g.sum() == 0:
            continue
        out.append(ndcg_score([g], [scores[idx]], k=min(k, len(idx)))); tids.append(t)
    return np.array(out), tids


def main():
    cache = json.loads(CACHE.read_text())
    records = sorted(cache['conditions']['buf500'], key=lambda r: (r['trial_id'], r['position']))
    click_pos = {r['trial_id']: r['position'] for r in records if r['was_clicked']}
    for r in records:
        r['click_pos'] = click_pos[r['trial_id']]
    lab_rows = json.loads(LAB_TYPED.read_text()); reg = json.loads(REG.read_text())
    assert len(lab_rows) == len(reg)
    label_by_key = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}
    gaze_labels = [label_by_key.get((r['trial_id'], r['position']), False) for r in records]
    census = {(row['trial_id'], int(row['position'])): row for row in csv.DictReader(open(STATES))}

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([t.split('-')[0] for t in tid_all])
    y_click = np.array([int(bool(r['was_clicked'])) for r in records])
    X = np.array([[float(r[f]) for f in APPROACH_7] for r in records])
    pid_of_trial = {t: p for t, p in zip(tid_all, pid_all)}

    # ---- labels -------------------------------------------------------------
    l4, include, counts4 = assign_four_distinct_grades(records, gaze_labels)
    state = np.array([census.get((r['trial_id'], r['position']), {}).get('state', 'missing') for r in records])
    n_visits = np.array([int(census[(r['trial_id'], r['position'])]['n_visits']) if (r['trial_id'], r['position']) in census else 0 for r in records])
    dwell = np.array([float(census[(r['trial_id'], r['position'])]['total_dwell_ms']) if (r['trial_id'], r['position']) in census else 0.0 for r in records])
    n_missing = int((state == 'missing').sum())

    states6 = np.zeros(len(records), dtype=int)
    for i, (s, v, c) in enumerate(zip(state, n_visits, y_click)):
        if c:
            states6[i] = 5
        elif s == 'deferred':
            states6[i] = 4 if v >= 3 else 3
        elif s == 'rejected':
            states6[i] = 2
        elif s == 'peripheral':
            states6[i] = 1
        else:
            states6[i] = 0
    onscreen = np.isin(state, ['unsampled', 'peripheral', 'rejected', 'deferred', 'clicked'])
    # pure-gaze forms of the coarse label: no cursor-approach requirement anywhere
    gaze4_census = np.where(y_click == 1, 3, np.where(state == 'deferred', 2, np.where(state == 'rejected', 1, 0)))
    gaze3_census = np.where(y_click == 1, 2, np.where(state == 'deferred', 1, 0))
    cost4 = np.where(y_click == 1, 3, np.where(state == 'deferred', 2, np.where(state == 'rejected', 1, 0)))

    def click_pinned(score_primary, score_secondary):
        g = np.zeros(len(records), dtype=int)
        by_trial = defaultdict(list)
        for i, t in enumerate(tid_all):
            by_trial[t].append(i)
        for t, idxs in by_trial.items():
            non = [i for i in idxs if not y_click[i]]
            order = sorted(non, key=lambda i: (-score_primary[i], -score_secondary[i]))
            for rank, i in enumerate(order):
                g[i] = 0 if score_primary[i] <= 0 else max(0, 8 - rank)
            for i in idxs:
                if y_click[i]:
                    g[i] = 9
        return g
    dwell10 = click_pinned(dwell, n_visits)
    visits10 = click_pinned(n_visits.astype(float), dwell)
    # dense gaze grades CONFINED to cursor-approached rows (the cursor has data there);
    # everything the cursor never approached is 0, as in the paper's label
    approached = np.array([r['min_dist'] < 100 for r in records])
    approach6 = np.zeros(len(records), dtype=int)
    for i in range(len(records)):
        if y_click[i]:
            approach6[i] = 5
        elif approached[i]:
            if state[i] == 'deferred':
                approach6[i] = 4 if n_visits[i] >= 3 else 3
            elif state[i] == 'rejected':
                approach6[i] = 2
            else:
                approach6[i] = 1          # approached, never fixated
    approach_dwell10 = click_pinned(np.where(approached, dwell + 1.0, 0.0), n_visits)  # +1 so approached zero-dwell rows rank above unapproached

    schemes = {
        'LambdaMART (binary click)': (y_click, None),
        'LambdaMART (4 distinct grades, 3/2/1/0; gaze labels)': (l4, None),
        'LambdaMART (4 grades from gaze alone, no approach filter; census)': (gaze4_census, None),
        'LambdaMART (3-grade collapse from gaze alone, rejected folded to 0; census)': (gaze3_census, None),
        'LambdaMART (six grades within cursor reach: clicked 5 / deferred ≥3 visits 4 / deferred 3 / rejected 2 / approached-unfixated 1 / not approached 0)': (approach6, None),
        'LambdaMART (click-pinned dwell rank among approached rows; not approached 0)': (approach_dwell10, None),
        'LambdaMART (six states 5..0; gaze census)': (states6, None),
        'LambdaMART (four states, cost-tier gain; gaze census)': (cost4, [0.0, 5.41, 16.95, 40.52]),
        'LambdaMART (click-pinned gaze-dwell rank, 10 grades, exp gain)': (dwell10, None),
        'LambdaMART (click-pinned visit-count rank, 10 grades, exp gain)': (visits10, None),
        'LambdaMART (click-pinned gaze-dwell rank, 10 grades, linear gain)': (dwell10, list(range(10))),
    }

    X_kept, tid_kept, pid_kept = X[include], tid_all[include], pid_all[include]
    pos_col = np.array([[float(r['position'])] for r in records])
    X_pos = np.hstack([X, pos_col]); X_pos_kept = X_pos[include]
    parts = np.unique(pid_all)

    def loso_lambdamart(labels_all, label_gain, with_position=False):
        lab_kept = labels_all[include]
        Xa, Xk = (X_pos, X_pos_kept) if with_position else (X, X_kept)
        pooled = np.zeros(len(records))
        for p in parts:
            tr, te = pid_kept != p, pid_all == p
            kw = {} if label_gain is None else {'label_gain': label_gain}
            ranker = LGBMRanker(objective='lambdarank', metric='ndcg', eval_at=[10], n_estimators=200,
                                learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, verbose=-1, n_jobs=1, **kw)
            ranker.fit(Xk[tr], lab_kept[tr], group=contiguous_group_sizes(tid_kept[tr]))
            pooled[te] = ranker.predict(Xa[te])
        return pooled

    def loso_pointwise_regression(labels_all, with_position=False):
        from lightgbm import LGBMRegressor
        lab_kept = labels_all[include]
        Xa, Xk = (X_pos, X_pos_kept) if with_position else (X, X_kept)
        pooled = np.zeros(len(records))
        for p in parts:
            tr, te = pid_kept != p, pid_all == p
            m = LGBMRegressor(n_estimators=200, learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, verbose=-1, n_jobs=1)
            m.fit(Xk[tr], lab_kept[tr].astype(float))
            pooled[te] = m.predict(Xa[te])
        return pooled

    def metrics(scores):
        ndcg, mrr, tids = per_trial_metrics(scores, y_click, tid_all, k=10)
        g6, t6 = graded_ndcg(scores, states6, tid_all, keep=onscreen)
        g4, _ = graded_ndcg(scores, l4, tid_all, keep=onscreen)
        return {'ndcg10': float(ndcg.mean()), 'mrr10': float(mrr.mean()), 'n_trials': int(len(ndcg)),
                'graded_ndcg10_states6_onscreen': float(g6.mean()), 'graded_ndcg10_gaze4_onscreen': float(g4.mean()),
                'n_trials_graded': int(len(g6)),
                '_mrr': mrr, '_ndcg': ndcg, '_tids': tids, '_g6': g6, '_t6': t6}

    rows = {'Original SERP position (no ML)': metrics(baseline_serp_scores(records)),
            'Oracle: score = six-state gaze grade (upper bound on the graded metric)': metrics(states6.astype(float) + 1e-3 * dwell / (dwell.max() + 1))}
    for name, (lab, gain) in schemes.items():
        print(f'[fit] {name}', file=sys.stderr, flush=True)
        rows[name] = metrics(loso_lambdamart(lab, gain))
    for name, (lab, gain) in list(schemes.items())[:6]:
        pname = name.replace('LambdaMART (', 'LambdaMART (position + cursor; ')
        print(f'[fit] {pname}', file=sys.stderr, flush=True)
        rows[pname] = metrics(loso_lambdamart(lab, gain, with_position=True))
    for name, lab in [('pointwise regression on gaze4 grade', l4), ('pointwise regression on six-within-reach grade', approach6),
                      ('pointwise regression on six-state census grade', states6)]:
        print(f'[fit] {name}', file=sys.stderr, flush=True)
        rows[f'LGBM ({name})'] = metrics(loso_pointwise_regression(lab))

    # ---- gate -----------------------------------------------------------------
    shipped = json.loads(SHIPPED.read_text())['metrics']
    for name in ('LambdaMART (binary click)', 'LambdaMART (4 distinct grades, 3/2/1/0; gaze labels)'):
        g = abs(rows[name]['mrr10'] - shipped[name]['mrr10'])
        assert g < 1e-6, f'gate failed on {name}: {rows[name]["mrr10"]} vs shipped {shipped[name]["mrr10"]}'

    b = rows['LambdaMART (binary click)']; g4 = rows['LambdaMART (4 distinct grades, 3/2/1/0; gaze labels)']
    comparisons = {}
    for name, r in rows.items():
        if name.startswith('Original') or name.startswith('Oracle'):
            continue
        comparisons[name] = {
            'delta_mrr10_vs_binary': r['mrr10'] - b['mrr10'], 'delta_ndcg10_vs_binary': r['ndcg10'] - b['ndcg10'],
            'delta_mrr10_vs_gaze4': r['mrr10'] - g4['mrr10'],
            'paired_vs_binary': paired_participant(r['_mrr'], b['_mrr'], r['_tids'], pid_of_trial),
            'paired_vs_gaze4': paired_participant(r['_mrr'], g4['_mrr'], r['_tids'], pid_of_trial),
            'delta_graded_ndcg10_states6_vs_binary': r['graded_ndcg10_states6_onscreen'] - b['graded_ndcg10_states6_onscreen'],
            'paired_graded_states6_vs_binary': paired_participant(r['_g6'], b['_g6'], r['_t6'], pid_of_trial)}
    label_counts = {'states6': {str(k): int(v) for k, v in zip(*np.unique(states6[include], return_counts=True))},
                    'cost4': {str(k): int(v) for k, v in zip(*np.unique(cost4[include], return_counts=True))},
                    'dwell10': {str(k): int(v) for k, v in zip(*np.unique(dwell10[include], return_counts=True))},
                    'gaze4': counts4, 'rows_missing_census_state': n_missing}
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed, cursor-only features, gaze training labels]',
           'protocol': 'cursor-only typed buf500 (press-anchored); 47-fold participant LOSO; LGBMRanker lambdarank NDCG@10 '
                       '(200 trees, lr 0.05, 31 leaves, min 20); NotApprBelow rows excluded from training for EVERY scheme; '
                       'inference scores every main-axis AOI; MRR@10 / NDCG@10 per trial on the binary click vector',
           'inputs': {'cache': str(CACHE.relative_to(ROOT)), 'cache_sha256': sha(CACHE), 'label_cache_sha256': sha(REG),
                      'states_csv': str(STATES.relative_to(ROOT)), 'states_sha256': sha(STATES)},
           'gate': {name: {'this_run': rows[name]['mrr10'], 'shipped': shipped[name]['mrr10']}
                    for name in ('LambdaMART (binary click)', 'LambdaMART (4 distinct grades, 3/2/1/0; gaze labels)')},
           'training_rows': int(include.sum()), 'records': len(records), 'label_counts_on_training_rows': label_counts,
           'metrics': {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in rows.items()},
           'comparisons': comparisons}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / 'summary_buf500.json', 'w'), indent=1)

    print(f"gate OK: binary {b['mrr10']:.4f}, gaze4 {g4['mrr10']:.4f} reproduce shipped; training rows {int(include.sum()):,}; rows missing census state {n_missing}")
    print(f"\n{'ranker (training labels)':68s} click MRR@10  paired Δ vs binary [CI]      | graded NDCG@10 (6-state gaze, on-screen)  paired Δ vs binary [CI] | NDCG vs gaze4 grade")
    for name, r in rows.items():
        c = comparisons.get(name)
        if c:
            pb, pg = c['paired_vs_binary'], c['paired_graded_states6_vs_binary']
            print(f"  {name:66s} {r['mrr10']:.4f}  {pb['mean_delta']:+.4f} [{pb['bootstrap_ci95'][0]:+.4f},{pb['bootstrap_ci95'][1]:+.4f}] {pb['positive']:2d}/47 | "
                  f"{r['graded_ndcg10_states6_onscreen']:.4f}  {pg['mean_delta']:+.4f} [{pg['bootstrap_ci95'][0]:+.4f},{pg['bootstrap_ci95'][1]:+.4f}] {pg['positive']:2d}/47 | {r['graded_ndcg10_gaze4_onscreen']:.4f}")
        else:
            print(f"  {name:66s} {r['mrr10']:.4f}  {'':33s} | {r['graded_ndcg10_states6_onscreen']:.4f}")
    print('\nlabel counts on training rows:', json.dumps(label_counts))
    print(f'\nwrote {OUT / "summary_buf500.json"}')


if __name__ == '__main__':
    main()
