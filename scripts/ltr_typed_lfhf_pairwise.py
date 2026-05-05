"""K29: LF/HF as a label-generator for pairwise preference LTR.

Two designs:

  K29a — Pure LF/HF rank-within-trial. For each trial with ≥3 non-null LF/HF
         positions, rank positions by lfhf descending and use those ranks as
         the graded label (mirrors Rung 4a / K22 — rank-within-trial of
         `withstood_pre_click`). Tests whether the pupil signal alone orders
         positions well enough to recover clicks. Trials with <3 non-null
         lfhf positions are dropped.

  K29b — Hybrid composite label: 4-class behavioral outer × LF/HF tiebreaker.
         For each kept position, compute composite key (4_class_label, lfhf,
         -position) and sort within trial. Assign grades 0..(N-1) by the
         resulting rank (top = N-1). Clicked always lands at top because
         4_class = 2 dominates; within Deferred / EvalRej buckets, LF/HF
         orders. Null LF/HF goes to bottom of bucket. NotApprBelow excluded.
         This is the answer to the "pairwise preferences" vision: 4-class
         supplies the outer hard label, LF/HF densifies the within-bucket
         pairwise gradient.

Comparison: K27.3 (4-class graded LambdaMART on M3-no-position, MRR@10 = 0.7713)
            is the headline baseline. K29a tests pupil-alone label; K29b tests
            pupil-as-tiebreaker label. Both use M3-no-position features, so
            the comparison isolates the label signal.

Run:
  .venv/bin/python scripts/ltr_typed_lfhf_pairwise.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from lightgbm import LGBMRanker
from sklearn.metrics import ndcg_score

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
REG_CACHE = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-typed.json'
OUT = ROOT / 'scripts/output/ltr_typed_lfhf_pairwise'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0
GRADES = 10
MIN_LFHF_PER_TRIAL_K29A = 3  # K29a requires ≥3 non-null lfhf positions

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


def per_trial_metrics(scores, y_click, tid_arr, k=10, restrict=None):
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        if restrict is None or restrict[i]:
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
    lfhf_arr = np.full(len(records), np.nan, dtype=float)
    for i, r in enumerate(records):
        td = lfhf_data.get(r['trial_id'])
        if td is None:
            continue
        for p in td['positions']:
            if p['pos'] == int(r['position']) and p.get('lfhf') is not None:
                lfhf_arr[i] = float(p['lfhf']); break
    return lfhf_arr


def label_pure_lfhf_rank(records, lfhf_arr, include):
    """K29a: 10-grade rank-within-trial of lfhf, drop trials w/ <K29A min."""
    by_trial = defaultdict(list)
    for i, r in enumerate(records):
        if include[i]:
            by_trial[r['trial_id']].append(i)
    labels = np.zeros(len(records), dtype=int)
    keep = np.zeros(len(records), dtype=bool)
    n_kept_trials = 0
    for tid, idxs in by_trial.items():
        non_null = [i for i in idxs if np.isfinite(lfhf_arr[i])]
        if len(non_null) < MIN_LFHF_PER_TRIAL_K29A:
            continue
        n_kept_trials += 1
        # Sort by lfhf descending → top gets highest grade
        non_null_sorted = sorted(non_null, key=lambda i: -lfhf_arr[i])
        N = len(non_null_sorted)
        for rank, i in enumerate(non_null_sorted):
            # rank 0 = top → grade GRADES-1 = 9; rank N-1 = bottom → 0
            grade = int(round((N - 1 - rank) / max(N - 1, 1) * (GRADES - 1)))
            labels[i] = grade; keep[i] = True
    return labels, keep, n_kept_trials


def label_hybrid_4class_lfhf(records, four_class, lfhf_arr, include):
    """K29b: composite (4_class, lfhf, -pos) within trial → grades 0..N-1
    rescaled to 0..GRADES-1. NotApprBelow already excluded via `include`.
    Null LF/HF goes to bottom of its 4-class bucket (-inf tiebreaker)."""
    by_trial = defaultdict(list)
    for i, r in enumerate(records):
        if include[i]:
            by_trial[r['trial_id']].append(i)
    labels = np.zeros(len(records), dtype=int)
    n_trials_labeled = 0
    for tid, idxs in by_trial.items():
        if len(idxs) < 2:
            continue
        n_trials_labeled += 1
        # Composite sort: outer 4-class DESC, lfhf DESC (null = -inf), pos ASC
        def key(i):
            lfhf_val = lfhf_arr[i] if np.isfinite(lfhf_arr[i]) else -np.inf
            return (-four_class[i], -lfhf_val, int(records[i]['position']))
        sorted_idxs = sorted(idxs, key=key)
        N = len(sorted_idxs)
        for rank, i in enumerate(sorted_idxs):
            # rank 0 = top → grade GRADES-1
            grade = int(round((N - 1 - rank) / max(N - 1, 1) * (GRADES - 1)))
            labels[i] = grade
    return labels, include.copy(), n_trials_labeled


def loso_lambdamart_full(X_full, label_train, train_mask_full, tid_full, pid_full):
    """Train on rows where train_mask_full[i] is True; predict on all rows.
    LOSO by participant via pid_full."""
    pooled = np.zeros(len(X_full), dtype=float)
    parts = np.unique(pid_full)
    label_train_arr = label_train[train_mask_full]
    X_kept = X_full[train_mask_full]
    pid_kept = pid_full[train_mask_full]
    tid_kept = tid_full[train_mask_full]
    for i, p in enumerate(parts):
        tr = (pid_kept != p); te = (pid_full == p)
        X_tr = X_kept[tr]; y_tr = label_train_arr[tr]; tid_tr = tid_kept[tr]
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


def main():
    print('[load] cursor-approach-features-typed.json + lfhf-typed', file=sys.stderr)
    records_raw = json.load(open(FEAT))
    regression_labels_raw = json.load(open(REG_CACHE))
    lfhf_data = json.load(open(LFHF))

    order = np.argsort(np.array([r['trial_id'] for r in records_raw]), kind='stable')
    records = [records_raw[i] for i in order]
    regression_labels = [regression_labels_raw[i] for i in order]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r.get('was_clicked', False))) for r in records])
    lfhf_arr = attach_lfhf(records, lfhf_data)

    four_class, include_4c, _ = assign_four_class(records, regression_labels)

    # Build features (M3-no-position, identical to K27/K28)
    X = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])

    n_total = len(records)
    print(f'  records: {n_total:,}  trials: {len(np.unique(tid_all)):,}  '
          f'participants: {len(np.unique(pid_all)):,}', file=sys.stderr)
    print(f'  lfhf non-null: {int(np.isfinite(lfhf_arr).sum()):,}', file=sys.stderr)

    # ── K29a: pure LF/HF rank label ──
    print('\n[label] K29a pure LF/HF rank-within-trial', file=sys.stderr)
    lab_29a, keep_29a, nt_29a = label_pure_lfhf_rank(records, lfhf_arr, include_4c)
    print(f'  K29a kept rows: {int(keep_29a.sum()):,}  trials: {nt_29a:,}',
          file=sys.stderr)
    print(f'  K29a label dist: {np.bincount(lab_29a[keep_29a]).tolist()}', file=sys.stderr)

    # ── K29b: hybrid 4-class × LF/HF composite label ──
    print('\n[label] K29b hybrid 4-class × LF/HF composite', file=sys.stderr)
    lab_29b, keep_29b, nt_29b = label_hybrid_4class_lfhf(records, four_class, lfhf_arr, include_4c)
    print(f'  K29b kept rows: {int(keep_29b.sum()):,}  trials: {nt_29b:,}',
          file=sys.stderr)
    print(f'  K29b label dist: {np.bincount(lab_29b[keep_29b]).tolist()}', file=sys.stderr)

    # ── Reference: K27.3 4-class graded label (rebuilt here for in-script comparison) ──
    print('\n[label] K27.3 4-class graded (reference)', file=sys.stderr)
    keep_27 = include_4c.copy()

    # ── Train + score each label ──
    rows = {}
    for name, label, keep in [
        ('K27.3 4-class graded (reference)', four_class, keep_27),
        ('K29a pure LF/HF rank',             lab_29a,    keep_29a),
        ('K29b hybrid 4-class × LF/HF',      lab_29b,    keep_29b),
    ]:
        print(f'\n[fit] LambdaMART — {name}', file=sys.stderr)
        scores = loso_lambdamart_full(X, label, keep, tid_all, pid_all)
        # Two evaluations:
        #  - full-pool (all 2,539 trials w/ ≥2 pos & ≥1 click), apples-to-K27
        #  - lfhf-trials-only (1,660 pairable trials), to isolate the LF/HF subset
        ndcg_full, mrr_full = per_trial_metrics(scores, y_click_all, tid_all, k=10)
        # restrict mask: trials with ≥1 non-null lfhf
        lfhf_trial = defaultdict(bool)
        for i, t in enumerate(tid_all):
            if np.isfinite(lfhf_arr[i]):
                lfhf_trial[t] = True
        restrict = np.array([lfhf_trial[t] for t in tid_all], dtype=bool)
        ndcg_sub, mrr_sub = per_trial_metrics(scores, y_click_all, tid_all, k=10, restrict=restrict)

        print(f'  full pool (n={len(ndcg_full)}): NDCG@10 {ndcg_full.mean():.4f}  '
              f'MRR@10 {mrr_full.mean():.4f}')
        print(f'  lfhf-trial subset (n={len(ndcg_sub)}): NDCG@10 {ndcg_sub.mean():.4f}  '
              f'MRR@10 {mrr_sub.mean():.4f}')
        rows[name] = {
            'full_pool': {'ndcg10': float(ndcg_full.mean()),
                          'mrr10':  float(mrr_full.mean()),
                          'n_trials': int(len(ndcg_full))},
            'lfhf_subset': {'ndcg10': float(ndcg_sub.mean()),
                            'mrr10':  float(mrr_sub.mean()),
                            'n_trials': int(len(ndcg_sub))},
            'kept_rows': int(keep.sum()),
        }

    # ── Headlines ──
    ref_full = rows['K27.3 4-class graded (reference)']['full_pool']
    a_full   = rows['K29a pure LF/HF rank']['full_pool']
    b_full   = rows['K29b hybrid 4-class × LF/HF']['full_pool']
    ref_sub = rows['K27.3 4-class graded (reference)']['lfhf_subset']
    a_sub   = rows['K29a pure LF/HF rank']['lfhf_subset']
    b_sub   = rows['K29b hybrid 4-class × LF/HF']['lfhf_subset']
    headlines = {
        'k29a_minus_k27_full_mrr10':   a_full['mrr10'] - ref_full['mrr10'],
        'k29b_minus_k27_full_mrr10':   b_full['mrr10'] - ref_full['mrr10'],
        'k29a_minus_k27_full_ndcg10':  a_full['ndcg10'] - ref_full['ndcg10'],
        'k29b_minus_k27_full_ndcg10':  b_full['ndcg10'] - ref_full['ndcg10'],
        'k29a_minus_k27_lfhf_mrr10':   a_sub['mrr10']  - ref_sub['mrr10'],
        'k29b_minus_k27_lfhf_mrr10':   b_sub['mrr10']  - ref_sub['mrr10'],
    }
    print('\n=== Headlines ===')
    print(f'K29a − K27.3 (full pool):  ΔMRR@10 {headlines["k29a_minus_k27_full_mrr10"]:+.4f}, '
          f'ΔNDCG@10 {headlines["k29a_minus_k27_full_ndcg10"]:+.4f}')
    print(f'K29b − K27.3 (full pool):  ΔMRR@10 {headlines["k29b_minus_k27_full_mrr10"]:+.4f}, '
          f'ΔNDCG@10 {headlines["k29b_minus_k27_full_ndcg10"]:+.4f}')
    print(f'K29a − K27.3 (lfhf trials only):  ΔMRR@10 {headlines["k29a_minus_k27_lfhf_mrr10"]:+.4f}')
    print(f'K29b − K27.3 (lfhf trials only):  ΔMRR@10 {headlines["k29b_minus_k27_lfhf_mrr10"]:+.4f}')

    summary = {
        'experiment': 'K29: LF/HF as label generator (pure rank, hybrid composite)',
        'design': {
            'K29a': 'pure LF/HF rank-within-trial (≥3 non-null per trial)',
            'K29b': 'hybrid 4-class × LF/HF composite (NotApprBelow excluded, null lfhf to bottom of bucket)',
        },
        'features': M3_NO_POS,
        'metrics': rows,
        'headlines': headlines,
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
