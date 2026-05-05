"""LTR ranker training: four-class behavioral graded labels (Peter's spec).

Peter Dixon-Moses (2026-05-04) reframed the four-class taxonomy as a
behavioral graded-relevance label generator for LTR training:

    Clicked              → 2  (relevant)
    Deferred             → 1  (gaze-regression on approached AOI)
    Eval-rejected        → 0  (approached, no regression, no click)
    NotApprAbove         → 0  (not approached, position ≤ clicked_pos — saw it, skipped it)
    NotApprBelow         EXCLUDE   (not approached, position > clicked_pos — never reached)

The exclusion of NotApprBelow is load-bearing: those AOIs were never
seen because the user committed before reaching them, so labeling them
0 (irrelevant) is wrong — they have no behavioral signal.

Spec from 2026-05-04:
  - LightGBM LambdaRank (LGBMRanker, lambdarank objective)
  - NDCG@10 optimize, MRR@10 evaluate
  - No position feature (M3-no-position = total_dwell_ms + 9 M4 features)
  - LOSO by participant
  - Typed-cascade input (cursor-approach-features-typed.json, all etypes)

Comparison rows:
  - Original SERP position (no ML)
  - Pointwise LR on binary click
  - LambdaMART on binary click (flavor-1, the "withstood" baseline at MRR 0.799)
  - LambdaMART on four-class graded (this script's headline)

Run:
  .venv/bin/python scripts/ltr_typed_four_class.py
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
REG_CACHE = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
OUT = ROOT / 'scripts/output/ltr_typed_four_class'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0  # NB22 convention

M4 = ['min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
      'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
      'direction_changes', 'frac_decreasing']
M3_NO_POS = ['total_dwell_ms'] + M4


def contiguous_group_sizes(tid_arr):
    sizes, last = [], None
    for t in tid_arr:
        if t != last:
            sizes.append(1); last = t
        else:
            sizes[-1] += 1
    return sizes


def per_trial_metrics(scores, y_click, tid_arr, k=10):
    """MRR@k and NDCG@k on binary-click gold, regardless of training label."""
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        by_trial[t].append(i)
    ndcgs, mrrs = [], []
    for t, idxs in by_trial.items():
        if len(idxs) < 2 or y_click[idxs].sum() == 0:
            continue
        s = scores[idxs]; gold = y_click[idxs].astype(float)
        ndcgs.append(ndcg_score([gold], [s], k=min(k, len(idxs))))
        order = np.argsort(-s, kind='stable')
        ranked = gold[order]
        for r, v in enumerate(ranked, start=1):
            if r > k:
                break
            if v > 0:
                mrrs.append(1.0 / r); break
        else:
            mrrs.append(0.0)
    return np.array(ndcgs), np.array(mrrs)


def assign_four_class(records, regression_labels):
    """Return (label, include_in_training) per record.

    label  ∈ {0, 1, 2}
    include = False for NotApprBelow (drop from training set entirely).
    """
    # First, find clicked_pos per trial (records carry click_pos field).
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is None:
            continue
        clicked_pos_by_trial[r['trial_id']] = int(cp)

    labels = np.zeros(len(records), dtype=int)
    include = np.ones(len(records), dtype=bool)
    cls_counts = defaultdict(int)

    for i, (r, regr) in enumerate(zip(records, regression_labels)):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        pos = int(r['position'])
        cp = clicked_pos_by_trial.get(r['trial_id'])

        if clicked:
            labels[i] = 2; cls_counts['CLICKED'] += 1
        elif approached and bool(regr):
            labels[i] = 1; cls_counts['DEFERRED'] += 1
        elif approached:
            labels[i] = 0; cls_counts['EVAL_REJECTED'] += 1
        else:
            # Not approached — split above/below clicked position.
            if cp is not None and pos > cp:
                include[i] = False; cls_counts['NotApprBelow_EXCLUDED'] += 1
            else:
                labels[i] = 0; cls_counts['NotApprAbove'] += 1
    return labels, include, dict(cls_counts)


def loso_lambdamart(X, y, tid, pid, n_estimators=200, eval_at=10):
    pooled = np.zeros(len(y), dtype=float)
    parts = np.unique(pid)
    for i, p in enumerate(parts):
        train_mask = pid != p
        test_mask = pid == p
        X_tr = X[train_mask]; y_tr = y[train_mask]; tid_tr = tid[train_mask]
        sizes = contiguous_group_sizes(tid_tr)
        ranker = LGBMRanker(
            objective='lambdarank',
            metric='ndcg',
            eval_at=[eval_at],
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


def baseline_serp_scores(records):
    """Score = -position, so original rank order wins."""
    return -np.array([int(r['position']) for r in records], dtype=float)


def main():
    print('[load] cursor-approach-features-typed.json', file=sys.stderr)
    records_raw = json.load(open(FEAT))
    regression_labels_raw = json.load(open(REG_CACHE))
    assert len(records_raw) == len(regression_labels_raw), \
        f'len mismatch: {len(records_raw)} vs {len(regression_labels_raw)}'

    # Sort by tid so groups are contiguous.
    order = np.argsort(np.array([r['trial_id'] for r in records_raw]), kind='stable')
    records = [records_raw[i] for i in order]
    regression_labels = [regression_labels_raw[i] for i in order]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    print(f'  records: {len(records):,}  trials: {len(np.unique(tid_all)):,}  '
          f'participants: {len(np.unique(pid_all)):,}', file=sys.stderr)
    print(f'  click-positive: {int(y_click_all.sum()):,}', file=sys.stderr)

    # ── Four-class assignment ──
    labels_all, include_all, cls_counts = assign_four_class(records, regression_labels)
    n_total = len(records)
    n_kept = int(include_all.sum())
    n_excluded = n_total - n_kept
    print(f'\n[four-class] class distribution:', file=sys.stderr)
    for k in ['CLICKED', 'DEFERRED', 'EVAL_REJECTED', 'NotApprAbove', 'NotApprBelow_EXCLUDED']:
        c = cls_counts.get(k, 0)
        print(f'  {k:30s}  {c:>7,}  ({100*c/n_total:>5.1f}%)', file=sys.stderr)
    print(f'  ─────────────────────────────────────────────', file=sys.stderr)
    print(f'  records kept (training set): {n_kept:,} of {n_total:,}', file=sys.stderr)
    print(f'  records dropped (NotApprBelow): {n_excluded:,}', file=sys.stderr)

    # ── Build kept-records arrays for training (LambdaMART + LR) ──
    # NOTE: per-trial metrics get computed on the FULL dataset (kept and excluded
    # alike) using binary-click gold, so the model has to score every position
    # at evaluation time. We achieve this by training only on kept rows but
    # predicting on all rows.

    X_full = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])
    X_kept = X_full[include_all]
    tid_kept = tid_all[include_all]
    pid_kept = pid_all[include_all]
    labels_kept = labels_all[include_all]
    y_click_kept = y_click_all[include_all]

    print(f'\n[shape] X_full {X_full.shape}, X_kept {X_kept.shape}', file=sys.stderr)

    # Helper: train on kept subset, predict over full dataset, then evaluate per-trial.
    def loso_lambdamart_full(label_train):
        pooled = np.zeros(len(records), dtype=float)
        parts = np.unique(pid_all)
        for i, p in enumerate(parts):
            train_mask = (pid_kept != p)
            test_mask = (pid_all == p)
            X_tr = X_kept[train_mask]
            y_tr = label_train[train_mask]
            tid_tr = tid_kept[train_mask]
            sizes = contiguous_group_sizes(tid_tr)
            ranker = LGBMRanker(
                objective='lambdarank',
                metric='ndcg',
                eval_at=[10],
                n_estimators=200,
                learning_rate=0.05,
                num_leaves=31,
                min_data_in_leaf=20,
                verbose=-1,
            )
            ranker.fit(X_tr, y_tr, group=sizes)
            pooled[test_mask] = ranker.predict(X_full[test_mask])
            if (i + 1) % 10 == 0:
                print(f'    fold {i+1}/{len(parts)}', file=sys.stderr)
        return pooled

    def loso_lr_full(y_train):
        pooled = np.zeros(len(records), dtype=float)
        for p in np.unique(pid_all):
            tr = (pid_kept != p)
            te = (pid_all == p)
            m = Pipeline([
                ('s', StandardScaler()),
                ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
            ])
            m.fit(X_kept[tr], y_train[tr])
            pooled[te] = m.predict_proba(X_full[te])[:, 1]
        return pooled

    # ── Models ──
    print('\n[fit] LR (pointwise, binary click)', file=sys.stderr)
    s_lr = loso_lr_full(y_click_kept)

    print('[fit] LambdaMART (binary click)', file=sys.stderr)
    s_lm_bin = loso_lambdamart_full(y_click_kept)

    print('[fit] LambdaMART (four-class graded)', file=sys.stderr)
    s_lm_4c = loso_lambdamart_full(labels_kept)

    s_pos = baseline_serp_scores(records)

    # ── Evaluation: per-trial MRR@10 + NDCG@10 on binary-click gold ──
    print('\n=== Evaluation: gold = binary click, k = 10 ===\n')
    print(f'{"model":>40s}  {"NDCG@10":>10s}  {"MRR@10":>10s}  {"n_trials":>10s}')
    rows = {}
    for name, s in [
        ('Original SERP position (no ML)',       s_pos),
        ('LR pointwise (binary click)',          s_lr),
        ('LambdaMART (binary click, flavor-1)',  s_lm_bin),
        ("LambdaMART (4-class graded, Peter's)", s_lm_4c),
    ]:
        ndcg, mrr = per_trial_metrics(s, y_click_all, tid_all, k=10)
        print(f'{name:>40s}  {ndcg.mean():>10.4f}  {mrr.mean():>10.4f}  {len(ndcg):>10d}')
        rows[name] = {
            'ndcg10': float(ndcg.mean()),
            'mrr10':  float(mrr.mean()),
            'n_trials': int(len(ndcg)),
        }

    # ── Headline delta ──
    delta_4c_vs_bin = (rows["LambdaMART (4-class graded, Peter's)"]['mrr10']
                       - rows['LambdaMART (binary click, flavor-1)']['mrr10'])
    delta_4c_vs_pos = (rows["LambdaMART (4-class graded, Peter's)"]['mrr10']
                       - rows['Original SERP position (no ML)']['mrr10'])

    print(f'\nΔMRR@10 (4-class − binary-click LambdaMART): {delta_4c_vs_bin:+.4f}')
    print(f'ΔMRR@10 (4-class − SERP position baseline): {delta_4c_vs_pos:+.4f}')

    summary = {
        'experiment': "LTR four-class graded labels (Peter's spec) on typed cascade",
        'spec_source': 'Peter Dixon-Moses 2026-05-04',
        'dataset': {
            'records_total': n_total,
            'records_kept': n_kept,
            'records_dropped_NotApprBelow': n_excluded,
            'trials': int(len(np.unique(tid_all))),
            'participants': int(len(np.unique(pid_all))),
            'class_distribution': cls_counts,
        },
        'features': M3_NO_POS,
        'note': "no position feature; LOSO by participant; train on kept rows, predict on all.",
        'metrics': rows,
        'headlines': {
            'delta_mrr10_4class_vs_binary_lambdamart': delta_4c_vs_bin,
            'delta_mrr10_4class_vs_serp_position':     delta_4c_vs_pos,
        },
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
