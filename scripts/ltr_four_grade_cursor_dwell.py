"""Four-grade cursor-time control for the current approach-retreat LTR.

The primary contrast changes training grades with M4 ranker features fixed.
A crossed feature comparison (M4 vs raw AOI dwell), with/without position,
separates grade-source effects from feature effects. Same LambdaMART config,
participant splits, training inclusion and binary-click evaluation throughout.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from datetime import datetime, timezone
import hashlib
import json
import time
import numpy as np
from lightgbm import LGBMRanker
import lightgbm
import sklearn

from ltr_raw_aoi_dwell_ablation import ROOT, SOURCE, DWELL_DIR, CONFIG, summarize, metric_contrast
from ltr_cursor_only_nested_grades import nested_cursor_training_labels
from ltr_typed_four_distinct_grades import assign_four_distinct_grades, contiguous_group_sizes
from m4_cursor_aoi_rerun import APPROACH_7, sha256
from m4_return_scroll_ablation import holm

OUT = ROOT/'scripts/output/ltr_four_grade_cursor_dwell'
FEATURES = {'M4': APPROACH_7, 'AOI dwell': ['raw_aoi_dwell_ms'],
            'M4 + position': APPROACH_7 + ['position'],
            'AOI dwell + position': ['raw_aoi_dwell_ms', 'position']}


def dwell_four_grades(dwell, clicked, training_mask):
    """Return only training grades; learn the positive-time median there only.

    Click=3, nonclick above positive median=2, other positive=1, zero=0.
    The provided mask already excludes the held-out participant and the fixed
    NotApprBelow training exclusion. No held-out value enters any operation.
    """
    d = np.asarray(dwell)[training_mask]
    c = np.asarray(clicked, dtype=bool)[training_mask]
    if not np.isfinite(d).all() or np.any(d < 0):
        raise ValueError('Training dwell must be finite and nonnegative')
    positive = d[(d > 0) & ~c]
    threshold = float(np.median(positive)) if len(positive) else None
    labels = (d > 0).astype(int)
    if threshold is not None:
        labels[(d > threshold) & ~c] = 2
    labels[c] = 3
    return labels, {'positive_nonclick_median_ms': threshold,
                    'training_grade_counts': {str(k): int((labels == k).sum()) for k in range(4)},
                    'label_sha256': hashlib.sha256(labels.astype('<i8').tobytes()).hexdigest()}


def main():
    started = time.monotonic()
    source = json.loads(SOURCE.read_text())
    for field in ('feature_cache', 'regression_label_cache', 'regression_label_row_keys'):
        assert sha256(ROOT/source['inputs'][field]) == source['inputs'][field+'_sha256']
    dwell_summary = json.loads((DWELL_DIR/'summary.json').read_text())
    assert sha256(DWELL_DIR/'features.json') == dwell_summary['provenance']['derived_features_sha256']
    dwell_rows = json.loads((DWELL_DIR/'features.json').read_text())
    dwell_lookup = {(r['trial_id'], r['position']): r for r in dwell_rows}
    cache = json.loads((ROOT/source['inputs']['feature_cache']).read_text())
    assert (cache['anchor_event'], cache['sampling']) == ('mousedown', 'native')
    records = sorted(cache['conditions']['buf500'], key=lambda r: (r['trial_id'], r['position']))
    clicked_pos = {r['trial_id']: r['position'] for r in records if r['was_clicked']}
    assert len(dwell_lookup) == len(records) == source['dataset']['records_total']
    for r in records:
        other = dwell_lookup[(r['trial_id'], r['position'])]
        assert r['was_clicked'] == other['was_clicked'] and all(r[f] == other[f] for f in APPROACH_7)
        r['raw_aoi_dwell_ms'] = other['raw_aoi_dwell_ms']
        r['click_pos'] = clicked_pos[r['trial_id']]
    lab = json.loads((ROOT/source['inputs']['regression_label_row_keys']).read_text())
    reg = json.loads((ROOT/source['inputs']['regression_label_cache']).read_text())
    assert len(lab) == len(reg)
    label_map = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab, reg)}
    gaze = np.array([int(label_map.get((r['trial_id'], r['position']), False)) for r in records])
    _, include, _ = assign_four_distinct_grades(records, gaze)
    assert int(include.sum()) == source['dataset']['records_kept']
    tids = np.array([r['trial_id'] for r in records])
    pids = np.array([t.split('-')[0] for t in tids])
    participants = np.unique(pids)
    click = np.array([int(r['was_clicked']) for r in records])
    dwell = np.array([r['raw_aoi_dwell_ms'] for r in records])
    X = {key: np.array([[r[f] for f in features] for r in records]) for key, features in FEATURES.items()}
    assert all(np.isfinite(v).all() for v in X.values())
    grades = {'binary': {p: click[(pids != p) & include] for p in participants},
              'approach-retreat 4': {}, 'dwell 4': {}}
    metrics, folds, trial_metrics, checks, diagnostics = {}, {}, {}, [], []

    def fit(label_source, features):
        scores = np.zeros(len(records))
        for p in participants:
            tr, te = (pids != p) & include, pids == p
            y = grades[label_source][p]
            assert len(y) == tr.sum()
            ranker = LGBMRanker(**CONFIG)
            ranker.fit(X[features][tr], y, group=contiguous_group_sizes(tids[tr]))
            scores[te] = ranker.predict(X[features][te])
        key = label_source+' | '+features
        metrics[key], folds[key], trial_metrics[key] = summarize(scores, click, tids)
        print(f'{key}: NDCG@10={metrics[key]["ndcg10"]:.9f}, MRR@10={metrics[key]["mrr10"]:.9f} ({time.monotonic()-started:.1f}s)', flush=True)
        return key

    def gate(key, source_key):
        for metric in ('ndcg10', 'mrr10'):
            shipped, actual = source['metrics'][source_key][metric], metrics[key][metric]
            check = {'name': key+' '+metric, 'shipped': shipped, 'reproduced': actual,
                     'delta': actual-shipped, 'tolerance': 1e-8,
                     'source': '../ltr_cursor_only_nested_grades/summary_buf500.json',
                     'source_path': 'metrics.'+source_key+'.'+metric}
            if abs(check['delta']) > check['tolerance']:
                raise RuntimeError(check)
            checks.append(check)
        print('Reproduction gate passed: '+key, flush=True)

    gate(fit('binary', 'M4'), 'LambdaMART (binary click)')
    pool = np.array([r['min_dist'] < 100 for r in records]) & (click == 0)
    for i, p in enumerate(participants):
        nested = nested_cursor_training_labels(records, X['M4'], gaze, pids, pool, p)
        assert np.array_equal(nested['include'], include[pids != p])
        grades['approach-retreat 4'][p] = nested['4grade']
        digest = nested['diagnostics']['kept_four_grade_labels_sha256']
        assert digest == source['nested_cursor_label_folds'][i]['kept_four_grade_labels_sha256']
        grades['dwell 4'][p], dwell_diag = dwell_four_grades(dwell, click, (pids != p) & include)
        diagnostics.append({'participant': str(p), 'dwell': dwell_diag,
                            'approach_retreat_grade_counts': {str(k): int((nested['4grade'] == k).sum()) for k in range(4)},
                            'approach_retreat_grade_sha256': digest})
        if (i+1) % 10 == 0 or i+1 == len(participants):
            print(f'Four-grade labels {i+1}/{len(participants)}; saved A-R label hash matched', flush=True)
    gate(fit('approach-retreat 4', 'M4'), 'LambdaMART (4 distinct grades, 3/2/1/0; cursor labels)')
    for label in ('approach-retreat 4', 'dwell 4'):
        for feature in FEATURES:
            if (label, feature) != ('approach-retreat 4', 'M4'):
                fit(label, feature)
    pairs = [
        ('approach-retreat 4 | M4', 'dwell 4 | M4'),
        ('approach-retreat 4 | AOI dwell', 'dwell 4 | AOI dwell'),
        ('approach-retreat 4 | M4', 'approach-retreat 4 | AOI dwell'),
        ('dwell 4 | M4', 'dwell 4 | AOI dwell'),
        ('approach-retreat 4 | M4 + position', 'approach-retreat 4 | M4'),
        ('dwell 4 | M4 + position', 'dwell 4 | M4'),
        ('approach-retreat 4 | AOI dwell + position', 'approach-retreat 4 | AOI dwell'),
        ('dwell 4 | AOI dwell + position', 'dwell 4 | AOI dwell'),
        ('approach-retreat 4 | M4', 'binary | M4'),
        ('dwell 4 | M4', 'binary | M4'),
    ]
    comparisons = {a+' minus '+b: {metric: metric_contrast(folds[a][metric], folds[b][metric])
                                   for metric in ('ndcg10', 'mrr10')} for a, b in pairs}
    primary = pairs[0][0]+' minus '+pairs[0][1]
    for metric in ('ndcg10', 'mrr10'):
        adjusted = holm({key: comparisons[key][metric]['wilcoxon_two_sided_p'] for key in comparisons})
        for key, value in adjusted.items():
            comparisons[key][metric]['holm_p_all_10_contrasts_this_metric'] = value
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'per_trial_metrics.json').write_text(json.dumps(trial_metrics, allow_nan=False)+'\n')
    thresholds = [d['dwell']['positive_nonclick_median_ms'] for d in diagnostics]
    payload = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': 'full_corpus',
        'gate': {'status': 'ok', 'checks': checks}, 'ranker_config': CONFIG,
        'protocol': {'primary_question': 'With the existing M4 ranker features fixed, compare current four-grade approach-retreat training labels with four grades based on cursor AOI dwell.',
                     'primary_contrast': primary, 'primary_metric': 'ndcg10', 'secondary_metric': 'mrr10',
                     'feature_control': FEATURES,
                     'grades': {'approach-retreat 4': '3 clicked; 2 approached and nested cursor-predicted deferred; 1 approached and predicted nondeferred; 0 other kept rows. Original four-grade source, not the three-grade collapse.',
                                'dwell 4': '3 clicked regardless of dwell; 2 nonclicked dwell above the outer-training positive-nonclick median; 1 other positive nonclicked dwell, including median ties; 0 zero nonclicked dwell. No held-out rows or excluded training rows set thresholds.'},
                     'label_gain': [0, 1, 3, 7], 'gain_note': 'Unchanged LightGBM default exponential gain for labels 0/1/2/3; grade number is not gain value.',
                     'raw_dwell': dwell_summary['protocol']['raw_AOI_dwell'],
                     'cutoff': 'Strictly before final mousedown minus 500 ms for all cursor observations',
                     'rows_scored': len(records), 'training_eligible_rows': int(include.sum()),
                     'training_excluded_NotApprBelow': int((~include).sum()), 'trials': len(clicked_pos), 'participants': len(participants),
                     'inclusion': 'Canonical fixed NotApprBelow mask for every arm. Uses approach min_dist and clicked position to select training rows; all candidates scored at test, including in dwell-feature arms.',
                     'split': 'Outer participant LOSO. A-R training labels generated by inner participant LOSO strictly inside outer training fold, using fixed full M4 labeler. Dwell thresholds use outer training data only.',
                     'evaluation': 'Canonical per-trial NDCG@10 and MRR@10 against binary held-out clicks, with original tie handling. Neither method evaluated against its own training grades.',
                     'uncertainty': 'Pair participant means of per-trial scores; bootstrap 10000 resamples seed 20260904. Wilcoxon plus Holm across 10 contrasts per metric; NDCG primary, MRR secondary. Outer training folds overlap.',
                     'limits': 'Offline post-interaction behavioral ranking; no new independent relevance judgments. The dwell median split is a prespecified control, not an optimized dwell model. A-R grade source remains supervised by gaze-regression training labels. Grade frequencies need not match even though four levels and gain schedule do.'},
        'dwell_threshold_ms_range': [float(min(thresholds)), float(max(thresholds))],
        'fold_grade_diagnostics': diagnostics, 'metrics': metrics, 'participant_metrics': folds, 'comparisons': comparisons,
        'provenance': {'source_summary_sha256': sha256(SOURCE), 'input_hashes': source['inputs'],
                       'dwell_features_sha256': sha256(DWELL_DIR/'features.json'), 'dwell_summary_sha256': sha256(DWELL_DIR/'summary.json'),
                       'producer_sha256': sha256(__file__), 'ranker_scaffold_sha256': sha256(ROOT/'scripts/ltr_raw_aoi_dwell_ablation.py'),
                       'nested_labeler_sha256': sha256(ROOT/'scripts/ltr_cursor_only_nested_grades.py'),
                       'per_trial_metrics_sha256': sha256(OUT/'per_trial_metrics.json'),
                       'numpy': np.__version__, 'lightgbm': lightgbm.__version__, 'sklearn': sklearn.__version__},
    }
    (OUT/'summary.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {OUT}/summary.json', flush=True)


if __name__ == '__main__':
    main()
