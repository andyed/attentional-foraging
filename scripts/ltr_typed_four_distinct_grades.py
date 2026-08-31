"""LTR ranker training: four-class taxonomy → FOUR distinct ordinal grades.

Tests whether promoting eval-rejected to a grade *above* not-approached
earns any ranking lift over the (2/1/0/0) collapse used in the paper's
headline. The clean experiment the 5-class confidence-gated variant
*doesn't* answer — that variant scrambles deferred and eval-rejected
splits, folds NotApprAbove into the silent floor anyway, and confounds
two design knobs at once.

Grade assignment:
    Clicked              → 3   (relevant)
    Deferred             → 2   (gaze-regression on approached AOI)
    Eval-rejected        → 1   (approached, no regression, no click)
    NotApprAbove         → 0   (not approached, position ≤ clicked_pos)
    NotApprBelow         EXCLUDE (never reached — no behavioral signal)

Compare against the (2/1/0/0) baseline from ltr_typed_four_class.py
to answer: does the 4th class earn its grade for ranking, or is the
two-negatives collapse loss-free?

Same protocol as ltr_typed_four_class.py:
  - LightGBM LambdaRank, NDCG@10 optimize, MRR@10 evaluate
  - LOSO by participant
  - No position feature (M3-no-position)
  - Typed-cascade input

Run:
  .venv/bin/python scripts/ltr_typed_four_distinct_grades.py
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

sys.path.insert(0, '/Users/andyed/Documents/dev/muriel')  # package root; the ~/.claude/skills/muriel symlink points at the plugin skill dir since 2026-08-07
from muriel.provenance import stamp_json  # noqa: E402

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
REG_CACHE = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'
OUT = ROOT / 'scripts/output/ltr_typed_four_distinct_grades'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0

M4_CANONICAL = ['min_dist', 'mean_dist',
                'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
                'direction_changes', 'frac_decreasing']
M3_NO_POS = ['total_dwell_ms'] + M4_CANONICAL


def contiguous_group_sizes(tid_arr):
    sizes, last = [], None
    for t in tid_arr:
        if t != last:
            sizes.append(1); last = t
        else:
            sizes[-1] += 1
    return sizes


def per_trial_metrics(scores, y_click, tid_arr, k=10):
    """Return (ndcgs, mrrs, tids_kept).

    tids_kept is the ordered list of trial IDs corresponding to each
    NDCG/MRR entry -- enables paired stat tests across rankers (each
    trial's score under ranker A is paired with its score under ranker
    B for the SAME trial). The filter (len(idxs)>=2 and at least one
    click) is identical across rankers, so the kept set is deterministic.
    """
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        by_trial[t].append(i)
    ndcgs, mrrs, tids_kept = [], [], []
    # Sort by trial id for stable cross-ranker pairing.
    for t in sorted(by_trial.keys()):
        idxs = by_trial[t]
        if len(idxs) < 2 or y_click[idxs].sum() == 0:
            continue
        s = scores[idxs]; gold = y_click[idxs].astype(float)
        ndcgs.append(ndcg_score([gold], [s], k=min(k, len(idxs))))
        order = np.argsort(-s, kind='stable')
        ranked = gold[order]
        # Reciprocal rank of first relevant within top-k (0 if outside top-k).
        # Single accumulator avoids the original for-else's length-mismatch
        # bug when a trial's relevant doc ranks beyond top-k.
        mrr = 0.0
        for r, v in enumerate(ranked, start=1):
            if r > k:
                break
            if v > 0:
                mrr = 1.0 / r
                break
        mrrs.append(mrr)
        tids_kept.append(str(t))
    return np.array(ndcgs), np.array(mrrs), tids_kept


def baseline_serp_scores(records):
    """SERP-position baseline: −position (top wins)."""
    return np.array([-int(r['position']) for r in records], dtype=float)


def assign_four_distinct_grades(records, regression_labels):
    """Four classes → four distinct ordinal grades."""
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
            labels[i] = 3; cls_counts['CLICKED'] += 1
        elif approached and bool(regr):
            labels[i] = 2; cls_counts['DEFERRED'] += 1
        elif approached:
            labels[i] = 1; cls_counts['EVAL_REJECTED'] += 1
        else:
            if cp is not None and pos > cp:
                include[i] = False; cls_counts['NotApprBelow_EXCLUDED'] += 1
            else:
                labels[i] = 0; cls_counts['NotApprAbove'] += 1
    return labels, include, dict(cls_counts)


def assign_three_grade_collapse(records, regression_labels):
    """Four classes → three grades (the paper's headline scheme, (2/1/0/0))."""
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is None:
            continue
        clicked_pos_by_trial[r['trial_id']] = int(cp)

    labels = np.zeros(len(records), dtype=int)
    include = np.ones(len(records), dtype=bool)

    for i, (r, regr) in enumerate(zip(records, regression_labels)):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        pos = int(r['position'])
        cp = clicked_pos_by_trial.get(r['trial_id'])

        if clicked:
            labels[i] = 2
        elif approached and bool(regr):
            labels[i] = 1
        elif approached:
            labels[i] = 0
        else:
            if cp is not None and pos > cp:
                include[i] = False
            else:
                labels[i] = 0
    return labels, include


def loso_deployable_classifier_predictions(X, y_gaze, pid, approached_mask):
    """Reproduce §4.3 deployable classifier predictions via 47-fold LOSO.

    Trains LR on (cursor features, gaze-regression label) over the
    approached-non-clicked subset, pools out-of-fold predictions for
    every participant. Returns a binary deferred-prediction array
    aligned with the full records list (False outside the approached
    subset since the classifier doesn't apply there).
    """
    pooled = np.zeros(len(X), dtype=float)
    for p in np.unique(pid):
        train = (pid != p) & approached_mask
        test = (pid == p) & approached_mask
        if train.sum() == 0 or test.sum() == 0:
            continue
        m = Pipeline([
            ('s', StandardScaler()),
            ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
        ])
        m.fit(X[train], y_gaze[train])
        pooled[test] = m.predict_proba(X[test])[:, 1]
    # Binarize at 0.5 (the deployable threshold; Youden-J in §4.3 is
    # roughly 0.449 but for a first-pass apples-to-apples vs gaze
    # labels, 0.5 keeps the labeler simple).
    return pooled, (pooled >= 0.5)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--click-buffer-ms', type=int, default=0)
    ap.add_argument('--label-source', choices=['gaze', 'cursor'], default='gaze',
                    help='gaze = use gaze-regression labels (LAB ceiling); '
                         'cursor = use §4.3 LOSO classifier predictions as '
                         'deferred/eval-rejected labels (deployment-actual)')
    args = ap.parse_args()

    feat_path = FEAT if args.click_buffer_ms == 0 else FEAT.with_name(
        f'{FEAT.stem}-buf{args.click_buffer_ms}.json')
    print(f'[load] {feat_path.name}', file=sys.stderr)
    records_raw = json.load(open(feat_path))
    canonical_raw = json.load(open(FEAT))
    regression_labels_canonical = json.load(open(REG_CACHE))
    assert len(canonical_raw) == len(regression_labels_canonical)

    # Re-key the regression label by (trial_id, position) so click-buffer
    # truncation that drops some records still finds the right label.
    label_by_key = {
        (r['trial_id'], r['position']): bool(regression_labels_canonical[i])
        for i, r in enumerate(canonical_raw)
    }
    regression_labels_raw = [
        label_by_key.get((r['trial_id'], r['position']), False)
        for r in records_raw
    ]
    assert len(records_raw) == len(regression_labels_raw)

    order = np.argsort(np.array([r['trial_id'] for r in records_raw]), kind='stable')
    records = [records_raw[i] for i in order]
    regression_labels = [regression_labels_raw[i] for i in order]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    print(f'  records: {len(records):,}  trials: {len(np.unique(tid_all)):,}  '
          f'participants: {len(np.unique(pid_all)):,}', file=sys.stderr)

    # Build feature matrix early so we can run the §4.3 stand-in classifier
    X_pre = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])
    approached_pre = np.array(
        [float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX for r in records], dtype=bool
    )
    clicked_pre = np.array([bool(r.get('was_clicked', False)) for r in records], dtype=bool)
    gaze_pre = np.array([bool(g) for g in regression_labels], dtype=int)

    # ── Decide which deferred-label source to use ──
    if args.label_source == 'cursor':
        print('\n[§4.3 stand-in] fitting LOSO LR on approached-non-clicked records '
              'to predict gaze-regression label from cursor features ...',
              file=sys.stderr)
        deferred_pool_subset = approached_pre & ~clicked_pre
        defer_proba, defer_binary = loso_deployable_classifier_predictions(
            X_pre, gaze_pre, pid_all, deferred_pool_subset,
        )
        # On approached-non-clicked records the classifier emits a binary
        # deferred label; elsewhere it's structurally False.
        labeling_regression_labels = defer_binary.tolist()
        # Quick QC: how often does §4.3 agree with gaze ground truth?
        ag = (defer_binary[deferred_pool_subset] == gaze_pre[deferred_pool_subset]).mean()
        print(f'  §4.3 LOSO agreement with gaze ground truth: {ag:.3f} '
              f'(n_approached_nonclicked = {deferred_pool_subset.sum():,})',
              file=sys.stderr)
    else:
        labeling_regression_labels = regression_labels

    # ── Both label flavors ──
    labels_4grade, include_4grade, cls_counts = assign_four_distinct_grades(records, labeling_regression_labels)
    labels_3grade, include_3grade = assign_three_grade_collapse(records, labeling_regression_labels)
    # The two flavors must share inclusion (only NotApprBelow excluded).
    assert (include_4grade == include_3grade).all(), 'include masks diverged — fix the assign fns'

    n_total = len(records)
    n_kept = int(include_4grade.sum())
    n_excluded = n_total - n_kept

    print(f'\n[four-distinct] class distribution:', file=sys.stderr)
    for k in ['CLICKED', 'DEFERRED', 'EVAL_REJECTED', 'NotApprAbove', 'NotApprBelow_EXCLUDED']:
        c = cls_counts.get(k, 0)
        print(f'  {k:30s}  {c:>7,}  ({100*c/n_total:>5.1f}%)', file=sys.stderr)
    print(f'  kept (training): {n_kept:,} of {n_total:,}', file=sys.stderr)

    X_full = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])
    X_kept = X_full[include_4grade]
    tid_kept = tid_all[include_4grade]
    pid_kept = pid_all[include_4grade]
    labels_4grade_kept = labels_4grade[include_4grade]
    labels_3grade_kept = labels_3grade[include_4grade]
    y_click_kept = y_click_all[include_4grade]

    print(f'\n[shape] X_full {X_full.shape}, X_kept {X_kept.shape}', file=sys.stderr)

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

    print('\n[fit] LR pointwise (binary click)', file=sys.stderr)
    s_lr = loso_lr_full(y_click_kept)

    print('[fit] LambdaMART (binary click)', file=sys.stderr)
    s_lm_bin = loso_lambdamart_full(y_click_kept)

    print('[fit] LambdaMART (3-grade collapse, 2/1/0/0) — paper headline', file=sys.stderr)
    s_lm_3g = loso_lambdamart_full(labels_3grade_kept)

    print('[fit] LambdaMART (4 distinct grades, 3/2/1/0) — this experiment', file=sys.stderr)
    s_lm_4g = loso_lambdamart_full(labels_4grade_kept)

    s_pos = baseline_serp_scores(records)

    print('\n=== Evaluation: gold = binary click, k = 10 ===\n', file=sys.stderr)
    print(f'{"model":>48s}  {"NDCG@10":>10s}  {"MRR@10":>10s}', file=sys.stderr)
    rows = {}
    for name, s in [
        ('Original SERP position (no ML)',           s_pos),
        ('LR pointwise (binary click)',              s_lr),
        ('LambdaMART (binary click)',                s_lm_bin),
        ('LambdaMART (3-grade collapse, 2/1/0/0)',   s_lm_3g),
        ('LambdaMART (4 distinct grades, 3/2/1/0)',  s_lm_4g),
    ]:
        ndcg, mrr, tids_kept = per_trial_metrics(s, y_click_all, tid_all, k=10)
        print(f'{name:>48s}  {ndcg.mean():>10.4f}  {mrr.mean():>10.4f}', file=sys.stderr)
        rows[name] = {
            'ndcg10': float(ndcg.mean()),
            'mrr10':  float(mrr.mean()),
            'n_trials': int(len(ndcg)),
            # Per-trial arrays + paired trial IDs -- enables paired stat
            # tests across rankers (same trial scored by different
            # rankers; pair on trial id).
            'per_trial_ndcg': ndcg.tolist(),
            'per_trial_mrr': mrr.tolist(),
            'per_trial_tids': tids_kept,
        }

    delta_4g_vs_3g_mrr = (rows['LambdaMART (4 distinct grades, 3/2/1/0)']['mrr10']
                          - rows['LambdaMART (3-grade collapse, 2/1/0/0)']['mrr10'])
    delta_4g_vs_3g_ndcg = (rows['LambdaMART (4 distinct grades, 3/2/1/0)']['ndcg10']
                           - rows['LambdaMART (3-grade collapse, 2/1/0/0)']['ndcg10'])
    delta_3g_vs_bin = (rows['LambdaMART (3-grade collapse, 2/1/0/0)']['mrr10']
                       - rows['LambdaMART (binary click)']['mrr10'])
    delta_4g_vs_bin = (rows['LambdaMART (4 distinct grades, 3/2/1/0)']['mrr10']
                       - rows['LambdaMART (binary click)']['mrr10'])

    print(f'\nHEADLINE: ΔMRR@10  (4-grade  − 3-grade):  {delta_4g_vs_3g_mrr:+.4f}', file=sys.stderr)
    print(f'          ΔNDCG@10 (4-grade  − 3-grade):  {delta_4g_vs_3g_ndcg:+.4f}', file=sys.stderr)
    print(f'          ΔMRR@10  (3-grade  − binary):   {delta_3g_vs_bin:+.4f}', file=sys.stderr)
    print(f'          ΔMRR@10  (4-grade  − binary):   {delta_4g_vs_bin:+.4f}', file=sys.stderr)

    summary = {
        'experiment': 'LTR four-class taxonomy: 4 distinct grades (3/2/1/0) vs 3-grade collapse (2/1/0/0)',
        'question': 'Does promoting eval-rejected to a grade above not-approached lift MRR?',
        'dataset': {
            'records_total': n_total,
            'records_kept': n_kept,
            'records_dropped_NotApprBelow': n_excluded,
            'trials': int(len(np.unique(tid_all))),
            'participants': int(len(np.unique(pid_all))),
            'class_distribution': cls_counts,
        },
        'features': M3_NO_POS,
        'note': 'no position feature; LOSO by participant; train on kept rows, predict on all.',
        'metrics': rows,
        'headlines': {
            'delta_mrr10_4grade_minus_3grade':  delta_4g_vs_3g_mrr,
            'delta_ndcg10_4grade_minus_3grade': delta_4g_vs_3g_ndcg,
            'delta_mrr10_3grade_minus_binary':  delta_3g_vs_bin,
            'delta_mrr10_4grade_minus_binary':  delta_4g_vs_bin,
        },
    }

    out_path = OUT / f'summary_{args.label_source}_buf{args.click_buffer_ms}.json'
    stamp_json(
        summary, out_path,
        script=__file__,
        dataset='AdSERP/data/cursor-approach-features-typed.json',
        h_ids=[],
        nb_k_ids=[],
        figure_version=f'four-grade-distinct-{args.label_source}-labels',
        notes=(f'4-grade vs 3-grade LTR comparison; label-source={args.label_source} '
               f'({"gaze regression ground truth (LAB)" if args.label_source == "gaze" else "§4.3 cursor-only LOSO predictions (deployment-actual)"})'),
    )
    print(f'\nwrote {out_path.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
