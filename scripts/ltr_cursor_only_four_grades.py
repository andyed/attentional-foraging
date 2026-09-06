"""§4.6 LTR utility check on the cursor-only typed feature cache.

Same protocol as ltr_typed_four_distinct_grades.py (LightGBM LambdaRank,
NDCG@10 objective, MRR@10 / NDCG@10 evaluated per trial against the binary
click, LOSO by participant, NotApprBelow excluded, no position feature), but:

  - features are the seven cursor-only M4 scalars produced by
    m4_cursor_aoi_rerun.py (no `total_dwell_ms`: that field was gaze dwell);
  - rows are the cursor-only rows (every main-axis typed AOI, strict X+Y
    final-click label), press-anchored buffer;
  - both label sources run in one pass so the binary rows are shared:
    gaze = NB22 gaze-regression label (LAB ceiling); cursor = §4.3 LOSO
    deployable classifier predictions on the same rows;
  - leave-one-feature-out on the ranker for three label flavors, and the
    ad-clicked vs organic-clicked split of the graded-label lift.

Run from attentional-foraging:
  .venv/bin/python scripts/ltr_cursor_only_four_grades.py
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
from lightgbm import LGBMRanker
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from ltr_typed_four_distinct_grades import (  # noqa: E402
    assign_four_distinct_grades, assign_three_grade_collapse, per_trial_metrics,
    baseline_serp_scores, contiguous_group_sizes, loso_deployable_classifier_predictions,
    APPROACH_THRESHOLD_PX,
)
from m4_cursor_aoi_rerun import APPROACH_7  # noqa: E402

REG_CACHE = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
LAB_TYPED = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--feature-cache', type=Path, default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--no-lofo', action='store_true')
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'scripts/output/ltr_cursor_only_four_grades')
    args = ap.parse_args()

    cache = json.loads(args.feature_cache.read_text())
    records = sorted(cache['conditions'][f'buf{args.buffer}'], key=lambda r: (r['trial_id'], r['position']))
    click_pos = {r['trial_id']: r['position'] for r in records if r['was_clicked']}
    for r in records:
        r['click_pos'] = click_pos[r['trial_id']]
    lab_rows = json.loads(LAB_TYPED.read_text())
    reg = json.loads(REG_CACHE.read_text())
    assert len(lab_rows) == len(reg)
    label_by_key = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}
    gaze_labels = [label_by_key.get((r['trial_id'], r['position']), False) for r in records]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r['was_clicked'])) for r in records])
    etype_all = np.array([r['etype'] for r in records])
    X_full = np.array([[float(r[f]) for f in APPROACH_7] for r in records])
    approached = np.array([r['min_dist'] < APPROACH_THRESHOLD_PX for r in records])
    gaze_arr = np.array([int(g) for g in gaze_labels])
    pool = approached & (y_click_all == 0)
    print(f'records {len(records):,} trials {len(np.unique(tid_all)):,} participants {len(np.unique(pid_all))}', file=sys.stderr)

    # §4.3 stand-in on the same rows -> cursor label source.
    defer_proba, defer_binary = loso_deployable_classifier_predictions(X_full, gaze_arr, pid_all, pool)
    agreement = float((defer_binary[pool] == gaze_arr[pool]).mean())
    cursor_labels = defer_binary.tolist()

    flavors = {}
    for source, labs in (('gaze', gaze_labels), ('cursor', cursor_labels)):
        l4, inc4, counts = assign_four_distinct_grades(records, labs)
        l3, inc3 = assign_three_grade_collapse(records, labs)
        assert (inc4 == inc3).all()
        flavors[source] = {'4grade': l4, '3grade': l3, 'include': inc4, 'class_counts': counts}
    include = flavors['gaze']['include']
    assert (include == flavors['cursor']['include']).all()
    X_kept, tid_kept, pid_kept = X_full[include], tid_all[include], pid_all[include]
    y_click_kept = y_click_all[include]
    parts = np.unique(pid_all)

    def loso_lambdamart(label_train, feats=None):
        cols = [APPROACH_7.index(f) for f in (feats or APPROACH_7)]
        pooled = np.zeros(len(records))
        for p in parts:
            tr, te = pid_kept != p, pid_all == p
            ranker = LGBMRanker(objective='lambdarank', metric='ndcg', eval_at=[10], n_estimators=200,
                                learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, verbose=-1, n_jobs=1)
            ranker.fit(X_kept[tr][:, cols], label_train[tr], group=contiguous_group_sizes(tid_kept[tr]))
            pooled[te] = ranker.predict(X_full[te][:, cols])
        return pooled

    def loso_lr(y_train):
        pooled = np.zeros(len(records))
        for p in parts:
            tr, te = pid_kept != p, pid_all == p
            m = Pipeline([('s', StandardScaler()), ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))])
            m.fit(X_kept[tr], y_train[tr])
            pooled[te] = m.predict_proba(X_full[te])[:, 1]
        return pooled

    def metrics(scores):
        ndcg, mrr, tids = per_trial_metrics(scores, y_click_all, tid_all, k=10)
        clicked_etype = {t: e for t, e, c in zip(tid_all, etype_all, y_click_all) if c}
        is_ad = np.array([clicked_etype[t] in ('dd_top', 'native_ad') for t in tids])
        return {'ndcg10': float(ndcg.mean()), 'mrr10': float(mrr.mean()), 'n_trials': int(len(ndcg)),
                'mrr10_ad_clicked': float(mrr[is_ad].mean()), 'n_ad_clicked': int(is_ad.sum()),
                'mrr10_organic_clicked': float(mrr[~is_ad].mean()), 'n_organic_clicked': int((~is_ad).sum()),
                'per_trial_mrr': mrr.tolist(), 'per_trial_tids': tids}

    rows = {}
    print('[fit] SERP position, LR binary, LambdaMART binary', file=sys.stderr)
    rows['Original SERP position (no ML)'] = metrics(baseline_serp_scores(records))
    rows['LR pointwise (binary click)'] = metrics(loso_lr(y_click_kept))
    rows['LambdaMART (binary click)'] = metrics(loso_lambdamart(y_click_kept))
    for source in ('gaze', 'cursor'):
        for grade in ('3grade', '4grade'):
            name = f'LambdaMART ({"3-grade collapse, 2/1/0/0" if grade == "3grade" else "4 distinct grades, 3/2/1/0"}; {source} labels)'
            print(f'[fit] {name}', file=sys.stderr)
            rows[name] = metrics(loso_lambdamart(flavors[source][grade][include]))

    b = rows['LambdaMART (binary click)']
    headlines = {}
    for source in ('gaze', 'cursor'):
        r3 = rows[f'LambdaMART (3-grade collapse, 2/1/0/0; {source} labels)']
        r4 = rows[f'LambdaMART (4 distinct grades, 3/2/1/0; {source} labels)']
        headlines[source] = {
            'delta_mrr10_3grade_minus_binary': r3['mrr10'] - b['mrr10'],
            'delta_mrr10_4grade_minus_binary': r4['mrr10'] - b['mrr10'],
            'delta_ndcg10_3grade_minus_binary': r3['ndcg10'] - b['ndcg10'],
            'delta_ndcg10_4grade_minus_binary': r4['ndcg10'] - b['ndcg10'],
            'delta_mrr10_4grade_minus_3grade': r4['mrr10'] - r3['mrr10'],
            'delta_mrr10_3grade_minus_binary_ad_clicked': r3['mrr10_ad_clicked'] - b['mrr10_ad_clicked'],
            'delta_mrr10_3grade_minus_binary_organic_clicked': r3['mrr10_organic_clicked'] - b['mrr10_organic_clicked'],
        }

    lofo = {}
    if not args.no_lofo:
        for flavor, labels in (('binary', y_click_kept),
                               ('3grade_cursor', flavors['cursor']['3grade'][include]),
                               ('4grade_gaze', flavors['gaze']['4grade'][include])):
            full = {'binary': b, '3grade_cursor': rows['LambdaMART (3-grade collapse, 2/1/0/0; cursor labels)'],
                    '4grade_gaze': rows['LambdaMART (4 distinct grades, 3/2/1/0; gaze labels)']}[flavor]
            lofo[flavor] = {}
            for f in APPROACH_7:
                print(f'[lofo] {flavor} drop {f}', file=sys.stderr)
                m = metrics(loso_lambdamart(labels, [x for x in APPROACH_7 if x != f]))
                lofo[flavor][f] = {'mrr10': m['mrr10'], 'ndcg10': m['ndcg10'],
                                   'delta_mrr10_vs_full': m['mrr10'] - full['mrr10']}

    for r in rows.values():  # aggregates only in the committed sidecar
        r.pop('per_trial_mrr'); r.pop('per_trial_tids')
    summary = {
        'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'experiment': 'LTR graded labels vs binary clicks on the cursor-only typed feature rows',
        'protocol': {'features': APPROACH_7, 'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event'],
                     'sampling': cache['sampling'], 'ranker': 'LGBMRanker lambdarank ndcg@10 n_estimators=200 lr=0.05 num_leaves=31 min_data_in_leaf=20',
                     'split': 'LOSO by participant; train on kept rows (NotApprBelow excluded), score all rows',
                     'evaluation': 'per-trial MRR@10 / NDCG@10 against the binary click; trials with >= 2 rows and a click',
                     'label_sources': {'gaze': 'NB22 gaze-regression label re-keyed by (trial, position)',
                                       'cursor': '§4.3 LOSO deployable classifier (M4-7 -> gaze label) binarised at 0.5 on approached non-click rows'},
                     'deployable_agreement_with_gaze_on_pool': agreement},
        'dataset': {'records_total': len(records), 'records_kept': int(include.sum()),
                    'records_dropped_NotApprBelow': int((~include).sum()), 'trials': int(len(np.unique(tid_all))),
                    'participants': int(len(parts)),
                    'class_distribution': {s: flavors[s]['class_counts'] for s in flavors}},
        'metrics': rows, 'headlines': headlines, 'ranker_leave_one_feature_out': lofo,
        'inputs': {'feature_cache': rel(args.feature_cache), 'feature_cache_sha256': sha256(args.feature_cache),
                   'regression_label_cache_sha256': sha256(REG_CACHE)},
        'provenance': {'producer_sha256': sha256(__file__), 'python': sys.version.split()[0]},
    }
    import lightgbm, sklearn
    summary['provenance'].update({'lightgbm': lightgbm.__version__, 'sklearn': sklearn.__version__})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f'summary_buf{args.buffer}.json'
    out.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(f'wrote {out}', file=sys.stderr)
    for k, v in rows.items():
        print(f'{k:60s} NDCG@10 {v["ndcg10"]:.4f} MRR@10 {v["mrr10"]:.4f}', file=sys.stderr)
    print(json.dumps(headlines, indent=1), file=sys.stderr)


if __name__ == '__main__':
    main()
