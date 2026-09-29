"""Matched LTR feature ablation: raw cursor AOI dwell versus M4.

Holds the current nested cursor-grade experiment's ranker, training inclusion,
training labels, outer splits and click evaluation fixed. Binary supervision
is a parallel control without a learned labeler. No label-source substitution.
Run: .venv/bin/python scripts/ltr_raw_aoi_dwell_ablation.py
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from lightgbm import LGBMRanker

from ltr_cursor_only_nested_grades import nested_cursor_training_labels
from ltr_typed_four_distinct_grades import assign_four_distinct_grades, contiguous_group_sizes, per_trial_metrics
from m4_cursor_aoi_rerun import APPROACH_7, paired_comparison, sha256
from m4_return_scroll_ablation import holm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'scripts/output/ltr_raw_aoi_dwell_ablation'
SOURCE = ROOT/'scripts/output/ltr_cursor_only_nested_grades/summary_buf500.json'
DWELL_DIR = ROOT/'scripts/output/m4_raw_aoi_dwell'
CONFIG = dict(objective='lambdarank', metric='ndcg', eval_at=[10], n_estimators=200,
              learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, verbose=-1, n_jobs=1)
FEATURES = {'M4': APPROACH_7, 'AOI dwell': ['raw_aoi_dwell_ms'],
            'AOI dwell + position': ['raw_aoi_dwell_ms', 'position'],
            'M4 + position': APPROACH_7 + ['position'],
            'M4 + AOI dwell': APPROACH_7 + ['raw_aoi_dwell_ms']}


def summarize(scores, y, tids):
    ndcg, mrr, ordered = per_trial_metrics(scores, y, tids, k=10)
    groups = defaultdict(list)
    for i, tid in enumerate(ordered):
        groups[tid.split('-')[0]].append(i)
    folds = {metric: {p: float(values[idx].mean()) for p, idx in groups.items()}
             for metric, values in [('ndcg10', ndcg), ('mrr10', mrr)]}
    return {'ndcg10': float(ndcg.mean()), 'mrr10': float(mrr.mean()),
            'n_trials': len(ordered)}, folds, {'tids': ordered, 'ndcg10': ndcg.tolist(), 'mrr10': mrr.tolist()}


def metric_contrast(a, b):
    result = paired_comparison(a, b)
    result['mean_participant_metric_delta'] = result.pop('mean_participant_auc_delta')
    return result


def main():
    started = time.monotonic()
    source = json.loads(SOURCE.read_text())
    for field in ('feature_cache', 'regression_label_cache', 'regression_label_row_keys'):
        assert sha256(ROOT/source['inputs'][field]) == source['inputs'][field+'_sha256'], field
    dwell_summary = json.loads((DWELL_DIR/'summary.json').read_text())
    assert sha256(DWELL_DIR/'features.json') == dwell_summary['provenance']['derived_features_sha256']
    dwell_rows = json.loads((DWELL_DIR/'features.json').read_text())
    dwell = {(r['trial_id'], r['position']): r for r in dwell_rows}
    cache = json.loads((ROOT/source['inputs']['feature_cache']).read_text())
    assert (cache['anchor_event'], cache['sampling']) == ('mousedown', 'native')
    records = sorted(cache['conditions']['buf500'], key=lambda r: (r['trial_id'], r['position']))
    clicked = {r['trial_id']: r['position'] for r in records if r['was_clicked']}
    assert len(dwell) == len(records) == source['dataset']['records_total']
    for r in records:
        matched = dwell[(r['trial_id'], r['position'])]
        assert matched['was_clicked'] == r['was_clicked']
        assert all(matched[f] == r[f] for f in APPROACH_7)
        r['raw_aoi_dwell_ms'] = matched['raw_aoi_dwell_ms']
        r['click_pos'] = clicked[r['trial_id']]
    lab = json.loads((ROOT/source['inputs']['regression_label_row_keys']).read_text())
    reg = json.loads((ROOT/source['inputs']['regression_label_cache']).read_text())
    assert len(lab) == len(reg)
    label_map = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab, reg)}
    gaze = np.array([int(label_map.get((r['trial_id'], r['position']), False)) for r in records])
    _, include, _ = assign_four_distinct_grades(records, gaze)
    assert int(include.sum()) == source['dataset']['records_kept']
    tids = np.array([r['trial_id'] for r in records])
    pids = np.array([t.split('-')[0] for t in tids])
    parts = np.unique(pids)
    y = np.array([int(r['was_clicked']) for r in records])
    X = {name: np.array([[r[f] for f in features] for r in records], dtype=float) for name, features in FEATURES.items()}
    assert all(np.isfinite(matrix).all() for matrix in X.values())
    kept_tids, kept_pids = tids[include], pids[include]
    checks, metrics, fold_metrics, trial_metrics = [], {}, {}, {}

    def fit(label_source, features, nested=None):
        predictions = np.zeros(len(records))
        for p in parts:
            train, test = (pids != p) & include, pids == p
            labels = y[train] if nested is None else nested[p]
            assert len(labels) == int(train.sum())
            ranker = LGBMRanker(**CONFIG)
            ranker.fit(X[features][train], labels, group=contiguous_group_sizes(tids[train]))
            predictions[test] = ranker.predict(X[features][test])
        key = label_source+' | '+features
        metrics[key], fold_metrics[key], trial_metrics[key] = summarize(predictions, y, tids)
        print(f'{key}: NDCG@10={metrics[key]["ndcg10"]:.9f} MRR@10={metrics[key]["mrr10"]:.9f} ({time.monotonic()-started:.1f}s)', flush=True)
        return key

    def gate(key, source_key):
        for metric in ('ndcg10', 'mrr10'):
            expected, actual = source['metrics'][source_key][metric], metrics[key][metric]
            check = {'name': key+' '+metric, 'shipped': expected, 'reproduced': actual,
                     'delta': actual-expected, 'tolerance': 1e-8,
                     'source': '../ltr_cursor_only_nested_grades/summary_buf500.json',
                     'source_path': 'metrics.'+source_key+'.'+metric}
            if abs(check['delta']) > check['tolerance']:
                raise RuntimeError(f'Failed baseline gate: {check}')
            checks.append(check)
        print(f'Reproduction gate passed: {key}', flush=True)

    fit('binary', 'M4')
    gate('binary | M4', 'LambdaMART (binary click)')
    # Freeze inner-generated grades across every feature ablation. The labeler
    # always uses full M4; only downstream ranker feature columns change.
    pool = np.array([r['min_dist'] < 100 for r in records]) & (y == 0)
    nested, diagnostics = {}, []
    for i, p in enumerate(parts, 1):
        result = nested_cursor_training_labels(records, X['M4'], gaze, pids, pool, p)
        assert np.array_equal(result['include'], include[pids != p])
        nested[p] = result['3grade']
        diagnostics.append({'participant': str(p), **result['diagnostics']})
        assert result['diagnostics']['kept_three_grade_labels_sha256'] == source['nested_cursor_label_folds'][i-1]['kept_three_grade_labels_sha256']
        if i % 5 == 0 or i == len(parts):
            print(f'Nested labels {i}/{len(parts)}; grade hash matches saved fold ({time.monotonic()-started:.1f}s)', flush=True)
    fit('nested cursor 3-grade', 'M4', nested)
    gate('nested cursor 3-grade | M4', 'LambdaMART (3-grade collapse, 2/1/0/0; cursor labels)')
    # No new comparison is published until both baseline rankers reproduce.
    for label_source, labels in [('binary', None), ('nested cursor 3-grade', nested)]:
        for features in FEATURES:
            if features != 'M4':
                fit(label_source, features, labels)
    comparisons = {}
    for label_source in ('binary', 'nested cursor 3-grade'):
        for a, b in [('M4', 'AOI dwell'), ('M4', 'AOI dwell + position'),
                     ('AOI dwell + position', 'AOI dwell'), ('M4 + position', 'M4'),
                     ('M4 + AOI dwell', 'M4')]:
            key = label_source+' | '+a+' vs '+b
            comparisons[key] = {metric: metric_contrast(fold_metrics[label_source+' | '+a][metric], fold_metrics[label_source+' | '+b][metric]) for metric in ('ndcg10', 'mrr10')}
    primary = [k for k in comparisons if not k.endswith('M4 + AOI dwell vs M4')]
    adjusted = holm({k: comparisons[k]['ndcg10']['wilcoxon_two_sided_p'] for k in primary})
    for k, p in adjusted.items():
        comparisons[k]['ndcg10']['holm_p_primary_NDCG_family_8'] = p
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'per_trial_metrics.json').write_text(json.dumps(trial_metrics, allow_nan=False)+'\n')
    payload = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': 'full_corpus',
        'gate': {'status': 'ok', 'checks': checks}, 'ranker_config': CONFIG,
        'protocol': {'comparison': 'Input-feature ablation; training labels fixed within each supervision family',
                     'features': FEATURES, 'rows_scored': len(records), 'training_eligible_rows': int(include.sum()),
                     'excluded_training_rows': int((~include).sum()), 'trials': len(clicked), 'participants': len(parts),
                     'cutoff': '500 ms before final mousedown; same canonical native-cursor cache and matched strict XY AOI dwell',
                     'training_inclusion': 'Canonical NotApprBelow exclusion fixed across all models: non-approached results below final-clicked position excluded in training; score every AOI at test. Uses min_dist and final-click position to construct the offline training set, including for dwell-only arms.',
                     'supervision': {'binary': 'Observed click 0/1', 'nested cursor 3-grade': 'Clicked=2, approached cursor-predicted deferred=1, other kept rows=0; default gains 0/1/3. Labeler always uses M4 and gaze-regression training targets, inner LOSO strictly inside each outer training fold; fixed threshold .5.'},
                     'split': 'Participant outer LOSO; group by trial; identical training eligibility, labels, evaluation rows, ordering, metrics and hyperparameters across feature arms',
                     'evaluation': 'NDCG@10 and MRR@10 against held-out binary clicks, using canonical per_trial_metrics including original tie handling',
                     'uncertainty': 'Per-participant averages of per-trial metrics; paired 10000-resample bootstrap seed 20260904; Wilcoxon, Holm across eight primary NDCG contrasts. MRR and dwell-addition contrasts exploratory. Outer training folds overlap.',
                     'scope': 'Offline behavioral reranking after interaction, not a pre-impression production ranker. Nested-grade arm holds an M4-based labeler fixed and therefore is not a dwell-only end-to-end pipeline; binary arm has no labeler. No continuous soft-label/gain experiment here.'},
        'metrics': metrics, 'participant_metrics': fold_metrics, 'comparisons': comparisons,
        'nested_label_diagnostics': diagnostics,
        'provenance': {'source_summary_sha256': sha256(SOURCE), 'input_hashes': source['inputs'],
                       'dwell_features_sha256': sha256(DWELL_DIR/'features.json'),
                       'dwell_summary_sha256': sha256(DWELL_DIR/'summary.json'),
                       'producer_sha256': sha256(__file__), 'nested_labeler_sha256': sha256(ROOT/'scripts/ltr_cursor_only_nested_grades.py'),
                       'grading_metrics_sha256': sha256(ROOT/'scripts/ltr_typed_four_distinct_grades.py'),
                       'per_trial_metrics_sha256': sha256(OUT/'per_trial_metrics.json')},
    }
    (OUT/'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {OUT}/summary.json', flush=True)


if __name__ == '__main__':
    main()
