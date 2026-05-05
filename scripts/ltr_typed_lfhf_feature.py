"""K28: LF/HF as a per-(trial, pos) feature on top of K27's typed-cascade
4-class graded LambdaMART.

Question: does pupillary LF/HF (windowed Butterworth IIR over the per-AOI
fixation window) add ranking signal on top of M3-no-position cursor
features when the label is the 4-class behavioral graded relevance?

LF/HF availability: 28.7 % of records have non-null LF/HF (Butterworth
needs enough pupil samples to settle). LightGBM splits natively on
missingness, so we pass NaN through.

Feature add over K27: `lfhf` and `lfhf_n_samples` (the latter as a
coverage/confidence signal — high n_samples → trustworthy lfhf, low
n_samples → noisier estimate, model can use this).

Comparison rows mirror K27.3:
  - LR pointwise on binary click (M3-no-pos + lfhf)
  - LambdaMART on binary click (M3-no-pos + lfhf, NotApprBelow excluded)
  - LambdaMART on 4-class graded (M3-no-pos + lfhf, NotApprBelow excluded)

Headline: ΔMRR@10 (4-class+lfhf − 4-class M3-only K27.3).

Run:
  .venv/bin/python scripts/ltr_typed_lfhf_feature.py
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
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-typed.json'
OUT = ROOT / 'scripts/output/ltr_typed_lfhf_feature'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0

M4 = ['min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
      'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
      'direction_changes', 'frac_decreasing']
M3_NO_POS = ['total_dwell_ms'] + M4
LFHF_FEATS = ['lfhf', 'lfhf_n_samples']
M3_PLUS_LFHF = M3_NO_POS + LFHF_FEATS


def contiguous_group_sizes(tid_arr):
    sizes, last = [], None
    for t in tid_arr:
        if t != last:
            sizes.append(1); last = t
        else:
            sizes[-1] += 1
    return sizes


def per_trial_metrics(scores, y_click, tid_arr, k=10):
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
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is not None:
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
            if cp is not None and pos > cp:
                include[i] = False; cls_counts['NotApprBelow_EXCLUDED'] += 1
            else:
                labels[i] = 0; cls_counts['NotApprAbove'] += 1
    return labels, include, dict(cls_counts)


def attach_lfhf(records, lfhf_data):
    """Returns parallel arrays of lfhf and lfhf_n_samples, NaN where missing."""
    lfhf_arr = np.full(len(records), np.nan, dtype=float)
    n_samp_arr = np.full(len(records), np.nan, dtype=float)
    for i, r in enumerate(records):
        tid = r['trial_id']
        pos = int(r['position'])
        td = lfhf_data.get(tid)
        if td is None:
            continue
        for p in td['positions']:
            if p['pos'] == pos:
                if p.get('lfhf') is not None:
                    lfhf_arr[i] = float(p['lfhf'])
                if p.get('n_samples') is not None:
                    n_samp_arr[i] = float(p['n_samples'])
                break
    return lfhf_arr, n_samp_arr


def main():
    print('[load] cursor-approach-features-typed.json', file=sys.stderr)
    records_raw = json.load(open(FEAT))
    regression_labels_raw = json.load(open(REG_CACHE))
    assert len(records_raw) == len(regression_labels_raw)

    print('[load] butterworth-lfhf-by-position-typed.json', file=sys.stderr)
    lfhf_data = json.load(open(LFHF))

    order = np.argsort(np.array([r['trial_id'] for r in records_raw]), kind='stable')
    records = [records_raw[i] for i in order]
    regression_labels = [regression_labels_raw[i] for i in order]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    lfhf_arr, n_samp_arr = attach_lfhf(records, lfhf_data)
    pct_nonnull = float(np.isfinite(lfhf_arr).mean())
    print(f'  records: {len(records):,}  trials: {len(np.unique(tid_all)):,}  '
          f'participants: {len(np.unique(pid_all)):,}', file=sys.stderr)
    print(f'  lfhf non-null: {int(np.isfinite(lfhf_arr).sum()):,} '
          f'({100*pct_nonnull:.1f}%)', file=sys.stderr)

    labels_all, include_all, cls_counts = assign_four_class(records, regression_labels)
    n_total = len(records); n_kept = int(include_all.sum())
    print(f'  kept: {n_kept:,}  excluded NotApprBelow: {n_total-n_kept:,}',
          file=sys.stderr)

    # Build feature matrices: M3-no-pos baseline (K27) + M3-no-pos + lfhf (K28)
    X_m3 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])
    X_lfhf = np.column_stack([X_m3, lfhf_arr, n_samp_arr])
    print(f'  X shapes: m3={X_m3.shape}  m3+lfhf={X_lfhf.shape}', file=sys.stderr)

    # ── LOSO drivers — train on kept, predict on full ──
    def loso_lambdamart_full(X_full, label_train_kept):
        pooled = np.zeros(len(records), dtype=float)
        parts = np.unique(pid_all)
        X_kept = X_full[include_all]
        tid_kept = tid_all[include_all]
        pid_kept = pid_all[include_all]
        for i, p in enumerate(parts):
            tr = (pid_kept != p); te = (pid_all == p)
            X_tr = X_kept[tr]; y_tr = label_train_kept[tr]; tid_tr = tid_kept[tr]
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
            pooled[te] = ranker.predict(X_full[te])
            if (i + 1) % 10 == 0:
                print(f'    fold {i+1}/{len(parts)}', file=sys.stderr)
        return pooled

    def loso_lr_full(X_full, y_train_kept):
        pooled = np.zeros(len(records), dtype=float)
        X_kept = X_full[include_all]
        pid_kept = pid_all[include_all]
        # Impute NaN with column-median for LR (LightGBM handles NaN natively, LR doesn't)
        med = np.nanmedian(X_kept, axis=0)
        Xk = np.where(np.isnan(X_kept), med, X_kept)
        Xf = np.where(np.isnan(X_full), med, X_full)
        for p in np.unique(pid_all):
            tr = (pid_kept != p); te = (pid_all == p)
            m = Pipeline([
                ('s', StandardScaler()),
                ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
            ])
            m.fit(Xk[tr], y_train_kept[tr])
            pooled[te] = m.predict_proba(Xf[te])[:, 1]
        return pooled

    labels_kept = labels_all[include_all]
    y_click_kept = y_click_all[include_all]

    rows = {}
    for cond_name, X in [('M3-no-position', X_m3), ('M3-no-position + lfhf', X_lfhf)]:
        print(f'\n──── condition: {cond_name} ────', file=sys.stderr)
        print(f'[fit] LR pointwise (binary click)', file=sys.stderr)
        s_lr  = loso_lr_full(X, y_click_kept)
        print(f'[fit] LambdaMART (binary click)', file=sys.stderr)
        s_lmb = loso_lambdamart_full(X, y_click_kept)
        print(f"[fit] LambdaMART (4-class graded)", file=sys.stderr)
        s_lm4 = loso_lambdamart_full(X, labels_kept)

        print(f'\n=== {cond_name}: gold = binary click, k = 10 ===')
        print(f'{"model":>40s}  {"NDCG@10":>10s}  {"MRR@10":>10s}  {"n_trials":>10s}')
        rows[cond_name] = {}
        for name, s in [
            ('LR (pointwise, binary click)', s_lr),
            ('LambdaMART (binary click)', s_lmb),
            ('LambdaMART (4-class graded)', s_lm4),
        ]:
            ndcg, mrr = per_trial_metrics(s, y_click_all, tid_all, k=10)
            print(f'{name:>40s}  {ndcg.mean():>10.4f}  {mrr.mean():>10.4f}  {len(ndcg):>10d}')
            rows[cond_name][name] = {
                'ndcg10': float(ndcg.mean()),
                'mrr10':  float(mrr.mean()),
                'n_trials': int(len(ndcg)),
            }

    # ── Headlines ──
    bb = rows['M3-no-position']
    bl = rows['M3-no-position + lfhf']
    headlines = {
        'delta_mrr10_lfhf_4class_minus_baseline_4class':
            bl['LambdaMART (4-class graded)']['mrr10']
            - bb['LambdaMART (4-class graded)']['mrr10'],
        'delta_ndcg10_lfhf_4class_minus_baseline_4class':
            bl['LambdaMART (4-class graded)']['ndcg10']
            - bb['LambdaMART (4-class graded)']['ndcg10'],
        'delta_mrr10_lfhf_binary_minus_baseline_binary':
            bl['LambdaMART (binary click)']['mrr10']
            - bb['LambdaMART (binary click)']['mrr10'],
    }
    print(f'\nΔMRR@10  (4-class +lfhf − 4-class M3-only): '
          f'{headlines["delta_mrr10_lfhf_4class_minus_baseline_4class"]:+.4f}')
    print(f'ΔNDCG@10 (4-class +lfhf − 4-class M3-only): '
          f'{headlines["delta_ndcg10_lfhf_4class_minus_baseline_4class"]:+.4f}')
    print(f'ΔMRR@10  (binary  +lfhf − binary  M3-only): '
          f'{headlines["delta_mrr10_lfhf_binary_minus_baseline_binary"]:+.4f}')

    summary = {
        'experiment': 'K28: LF/HF as feature on top of M3-no-position 4-class graded LambdaMART',
        'lfhf_coverage_pct_records': pct_nonnull,
        'class_distribution': cls_counts,
        'features': {
            'M3-no-position': M3_NO_POS,
            'M3-no-position + lfhf': M3_PLUS_LFHF,
        },
        'metrics': rows,
        'headlines': headlines,
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
