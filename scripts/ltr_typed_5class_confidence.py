"""LTR ranker training: 5-class confidence-gated graded labels.

Generalizes Peter's 4-class spec by splitting `deferred` and
`evaluated_rejected` into hi/lo confidence sub-buckets gated on AR
signal strength — mirroring the missions-flow calibration logic where
"Not for me" only emits when `outcome == evaluated_rejected ∧
reapproach_count == 0 ∧ total_dwell_ms ≥ 500ms`.

5-class structure:

    Tier 4 (CLICKED)              clicked === True
    Tier 3 (DEFERRED-HI)          approached + gaze-regressed,
                                   total_dwell_ms ≥ median(deferred dwell)
    Tier 2 (DEFERRED-LO)          approached + gaze-regressed,
                                   total_dwell_ms <  median(deferred dwell)
    Tier 1 (EVAL-REJECTED-HI)     approached, no regression, no click,
                                   total_dwell_ms ≥ 500ms AND
                                   retreat_dist ≥ median(eval_rej retreat_dist)
                                   ── confident negative
    Tier 0 (UNMOTIVATED)          the rest of approached-no-regression-no-click
                                   plus NotApprAbove ── unmotivated middle.
                                   **Kept in training as the silent-negative
                                   floor** (label 0 in the ordinal). Without
                                   this, LambdaMART loses gradient grounding —
                                   the binary-click MRR collapses from 0.741
                                   (K27.2) to 0.318 (first run, dropped).

    NotApprBelow                  EXCLUDED outright (Peter's invariant —
                                   never seen, no behavioral signal)

Two flavors:

  Flavor A — flat 5-tier integer labels {0, 1, 2, 3, 4}. Tests whether
             confidence gating alone (no secondary order) lifts MRR
             over Peter's 4-class. ~10 informative pairs per trial
             (5 choose 2), vs ~3 for 4-class.

  Flavor B — hybrid: tier 0 stays at 0; tiers 1/2/3 each subdivide by
             within-tier median split on `withstood_pre_click`; tier 4
             (clicks) stays as a single bucket pinned at the top.
             Labels ∈ {0, 1, 2, 3, 4, 5, 6, 7}:

                   Tier 4 (CLICKED)             label 7
                   Tier 3 (DEFERRED-HI):  upper  label 6
                                          lower  label 5
                   Tier 2 (DEFERRED-LO):  upper  label 4
                                          lower  label 3
                   Tier 1 (EVAL-REJ-HI):  upper  label 2
                                          lower  label 1
                   Tier 0 (unmotivated)         label 0

             Mirrors R4f's hybrid-click-pinned trick (preserves ground
             truth at top, uses relevance proxy to refine within tier)
             at a coarser confidence-gated granularity. ~28 informative
             pairs per trial vs ~10 for flat 5-tier vs ~3 for 4-class.

Comparison rows:
  - Original SERP position (no ML)
  - LR pointwise (binary click)
  - LambdaMART (binary click)
  - LambdaMART (4-class graded, K27 reference)
  - LambdaMART (5-class flat, this script flavor A)
  - LambdaMART (5-class hybrid, this script flavor B)

All on M3-no-position cursor features (apples-to-apples with K27).
LOSO by participant, LightGBM LambdaRank.

Run:
  .venv/bin/python scripts/ltr_typed_5class_confidence.py
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
WITHSTOOD = ROOT / 'AdSERP/data/withstood-evaluation-score.json'
OUT = ROOT / 'scripts/output/ltr_typed_5class_confidence'
OUT.mkdir(parents=True, exist_ok=True)

APPROACH_THRESHOLD_PX = 100.0  # NB22 convention
EVAL_REJ_DWELL_MIN_MS = 500.0  # mirrors missions-flow confident-negative gate

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
    """MRR@k and NDCG@k on binary-click gold."""
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


def load_withstood_index():
    """Map (trial_id, position) → withstood_pre_click."""
    raw = json.load(open(WITHSTOOD))
    out = {}
    for r in raw:
        out[(r['trial_id'], int(r['position']))] = float(r.get('withstood_pre_click') or 0.0)
    return out


def assign_5class_confidence(records, regression_labels):
    """Assign confidence_tier per record + return diagnostics.

    Returns:
        tier  ─ int8 array, values in {0, 1, 2, 3, 4} or -1 for excluded
                (NotApprBelow).
        include_in_training ─ bool array, True iff tier >= 0 (everything
                except NotApprBelow). Tier 0 stays in training as the
                silent-negative floor — without it, LambdaMART loses
                gradient grounding (verified empirically: dropping tier 0
                collapsed binary-click MRR from K27.2's 0.741 to 0.318).
        include_in_eval ─ bool array, identical to include_in_training
                under this regime (NotApprBelow excluded; everything else
                scored at eval against binary-click gold).
        cls_counts ─ dict for diagnostics output.
    """
    n = len(records)
    tier = np.full(n, -1, dtype=np.int8)  # default to excluded
    cls_counts = defaultdict(int)

    # Pre-pass: clicked_pos per trial
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is None: continue
        clicked_pos_by_trial[r['trial_id']] = int(cp)

    # First pass: assign coarse class (CLICKED / DEFERRED / EVAL_REJECTED /
    # NotApprAbove / NotApprBelow). Then we'll set the hi/lo splits.
    coarse = np.full(n, -1, dtype=np.int8)
    # 0 = NotApprBelow (skip), 1 = NotApprAbove, 2 = EVAL_REJECTED,
    # 3 = DEFERRED, 4 = CLICKED
    for i, (r, regr) in enumerate(zip(records, regression_labels)):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        pos = int(r['position'])
        cp = clicked_pos_by_trial.get(r['trial_id'])

        if clicked:
            coarse[i] = 4
        elif approached and bool(regr):
            coarse[i] = 3
        elif approached:
            coarse[i] = 2
        else:
            if cp is not None and pos > cp:
                coarse[i] = 0  # NotApprBelow
            else:
                coarse[i] = 1  # NotApprAbove

    # Compute within-class medians for hi/lo gates
    deferred_dwell = np.array([float(records[i].get('total_dwell_ms', 0.0) or 0.0)
                               for i in range(n) if coarse[i] == 3])
    eval_rej_retreat = np.array([float(records[i].get('retreat_dist', 0.0) or 0.0)
                                 for i in range(n) if coarse[i] == 2])
    median_deferred_dwell = float(np.median(deferred_dwell)) if len(deferred_dwell) else 0.0
    median_eval_rej_retreat = float(np.median(eval_rej_retreat)) if len(eval_rej_retreat) else 0.0

    # Second pass: assign 5-tier label using gates
    for i in range(n):
        c = coarse[i]
        r = records[i]
        dwell = float(r.get('total_dwell_ms', 0.0) or 0.0)
        retreat = float(r.get('retreat_dist', 0.0) or 0.0)
        if c == 0:
            tier[i] = -1  # excluded outright
            cls_counts['NotApprBelow_EXCLUDED'] += 1
        elif c == 4:
            tier[i] = 4
            cls_counts['T4_CLICKED'] += 1
        elif c == 3:
            if dwell >= median_deferred_dwell:
                tier[i] = 3
                cls_counts['T3_DEFERRED_HI'] += 1
            else:
                tier[i] = 2
                cls_counts['T2_DEFERRED_LO'] += 1
        elif c == 2:
            confident_neg = (dwell >= EVAL_REJ_DWELL_MIN_MS
                             and retreat >= median_eval_rej_retreat)
            if confident_neg:
                tier[i] = 1
                cls_counts['T1_EVAL_REJ_HI'] += 1
            else:
                tier[i] = 0
                cls_counts['T0_EVAL_REJ_LO'] += 1
        else:  # NotApprAbove
            tier[i] = 0
            cls_counts['T0_NotApprAbove'] += 1

    include_in_training = tier >= 0  # exclude NotApprBelow only
    include_in_eval = tier >= 0       # same — NotApprBelow excluded outright

    # Stash thresholds in cls_counts for output
    cls_counts['_threshold_median_deferred_dwell_ms'] = median_deferred_dwell
    cls_counts['_threshold_median_eval_rej_retreat_dist'] = median_eval_rej_retreat
    cls_counts['_threshold_eval_rej_dwell_min_ms'] = EVAL_REJ_DWELL_MIN_MS

    return tier, include_in_training, include_in_eval, dict(cls_counts)


def expand_to_hybrid_labels(tier, records, withstood_index):
    """Flavor B: subdivide each tier by within-tier median split on
    withstood_pre_click. Tier 0 stays at 0 (silent-negative floor).

    Mapping:
      Tier 4 (clicked)         → 7 (single bucket; ground truth)
      Tier 3 (deferred-hi)     → upper 6, lower 5
      Tier 2 (deferred-lo)     → upper 4, lower 3
      Tier 1 (eval-rej-hi)     → upper 2, lower 1
      Tier 0 (unmotivated)     → 0 (single bucket — no within-tier signal)
      Tier -1 (NotApprBelow)   → -1 (excluded outright)
    """
    n = len(records)
    labels = tier.astype(np.int16).copy()  # widen for label range
    # Compute withstood per record (default 0 if missing)
    wstd = np.array([
        withstood_index.get((r['trial_id'], int(r['position'])), 0.0)
        for r in records
    ])
    # Tier 4 → 7
    labels[tier == 4] = 7
    # Tiers 3, 2, 1 — within-tier median split on withstood
    for t, hi_label, lo_label in [(3, 6, 5), (2, 4, 3), (1, 2, 1)]:
        mask = (tier == t)
        if not mask.any(): continue
        med = float(np.median(wstd[mask]))
        labels[mask & (wstd >= med)] = hi_label
        labels[mask & (wstd <  med)] = lo_label
    # Tier 0 stays at 0 (no change needed)
    return labels


def main():
    print('[load] cursor-approach-features-typed.json', file=sys.stderr)
    records_raw = json.load(open(FEAT))
    regression_labels_raw = json.load(open(REG_CACHE))
    assert len(records_raw) == len(regression_labels_raw)

    print('[load] withstood-evaluation-score.json', file=sys.stderr)
    withstood_index = load_withstood_index()

    # Sort by tid so groups are contiguous
    order = np.argsort(np.array([r['trial_id'] for r in records_raw]), kind='stable')
    records = [records_raw[i] for i in order]
    regression_labels = [regression_labels_raw[i] for i in order]

    tid_all = np.array([r['trial_id'] for r in records])
    pid_all = np.array([r['trial_id'].split('-')[0] for r in records])
    y_click_all = np.array([int(bool(r.get('was_clicked', False))) for r in records])

    # ── Confidence-tier assignment ──
    tier, include_train, include_eval, cls_counts = assign_5class_confidence(
        records, regression_labels)

    n_total = len(records)
    n_train = int(include_train.sum())
    n_eval = int(include_eval.sum())
    print(f'\n[5-class] tier distribution:', file=sys.stderr)
    for k in ['T4_CLICKED', 'T3_DEFERRED_HI', 'T2_DEFERRED_LO',
              'T1_EVAL_REJ_HI', 'T0_EVAL_REJ_LO', 'T0_NotApprAbove',
              'NotApprBelow_EXCLUDED']:
        c = cls_counts.get(k, 0)
        print(f'  {k:30s}  {c:>7,}  ({100*c/n_total:>5.1f}%)', file=sys.stderr)
    print(f'  ─────────────────────────────────────────────', file=sys.stderr)
    print(f'  records training (tier ≥ 1): {n_train:,} of {n_total:,}', file=sys.stderr)
    print(f'  records eval (tier ≠ -1):    {n_eval:,} of {n_total:,}', file=sys.stderr)
    print(f'  thresholds:', file=sys.stderr)
    print(f'    median deferred dwell:        '
          f'{cls_counts["_threshold_median_deferred_dwell_ms"]:>8.1f} ms', file=sys.stderr)
    print(f'    median eval-rej retreat dist: '
          f'{cls_counts["_threshold_median_eval_rej_retreat_dist"]:>8.1f} px', file=sys.stderr)
    print(f'    eval-rej dwell-hi gate:       '
          f'{EVAL_REJ_DWELL_MIN_MS:>8.1f} ms (missions-flow convention)',
          file=sys.stderr)

    # ── Build feature matrices ──
    X_full = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS]
                       for r in records])
    X_train = X_full[include_train]
    tid_train = tid_all[include_train]
    pid_train = pid_all[include_train]
    tier_train = tier[include_train]
    y_click_train = y_click_all[include_train]

    # Hybrid (flavor B) labels
    hybrid_labels = expand_to_hybrid_labels(tier, records, withstood_index)
    hybrid_train = hybrid_labels[include_train]

    # 4-class reference labels (Peter's K27 spec) — rebuilt on the same
    # training set as 5-class flavor A so this is a true apples-to-apples
    # comparison. Mapping:
    #   tier 4 (CLICKED)            → 2
    #   tier 3 (DEFERRED-HI)        → 1
    #   tier 2 (DEFERRED-LO)        → 1   (collapses to single deferred class)
    #   tier 1 (EVAL-REJ-HI)        → 0
    #   tier 0 (NotApprAbove + LO)  → 0
    #   tier -1 (NotApprBelow)      EXCLUDED above
    # Should reproduce K27.3 (MRR 0.7713) within fold-noise.
    fourclass_train = np.zeros(len(tier_train), dtype=int)
    fourclass_train[tier_train == 4] = 2
    fourclass_train[(tier_train == 3) | (tier_train == 2)] = 1

    print(f'\n[shape] X_full {X_full.shape}, X_train {X_train.shape}',
          file=sys.stderr)

    # Helper: train on training subset, predict over full dataset (for eval).
    def loso_lambdamart_full(label_train):
        pooled = np.zeros(n_total, dtype=float)
        parts = np.unique(pid_all)
        for i, p in enumerate(parts):
            train_mask = (pid_train != p)
            test_mask = (pid_all == p)
            X_tr = X_train[train_mask]
            y_tr = label_train[train_mask]
            tid_tr = tid_train[train_mask]
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
        pooled = np.zeros(n_total, dtype=float)
        for p in np.unique(pid_all):
            tr = (pid_train != p)
            te = (pid_all == p)
            m = Pipeline([
                ('s', StandardScaler()),
                ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
            ])
            m.fit(X_train[tr], y_train[tr])
            pooled[te] = m.predict_proba(X_full[te])[:, 1]
        return pooled

    def baseline_serp_scores():
        return -np.array([int(r['position']) for r in records], dtype=float)

    # ── Models ──
    print('\n[fit] LR pointwise (binary click)', file=sys.stderr)
    s_lr = loso_lr_full(y_click_train)

    print('[fit] LambdaMART (binary click)', file=sys.stderr)
    s_lm_bin = loso_lambdamart_full(y_click_train)

    print('[fit] LambdaMART (4-class graded, on confidence-gated train set)',
          file=sys.stderr)
    s_lm_4c = loso_lambdamart_full(fourclass_train)

    print('[fit] LambdaMART (5-class flat, flavor A)', file=sys.stderr)
    s_lm_5flat = loso_lambdamart_full(tier_train.astype(int))

    print('[fit] LambdaMART (5-class hybrid, flavor B — withstood within-tier)',
          file=sys.stderr)
    s_lm_5hybrid = loso_lambdamart_full(hybrid_train)

    s_pos = baseline_serp_scores()

    # ── Evaluation ──
    print('\n=== Evaluation: gold = binary click, k = 10 ===\n')
    print(f'{"model":>50s}  {"NDCG@10":>10s}  {"MRR@10":>10s}  {"n":>7s}')
    rows = {}
    for name, s in [
        ('Original SERP position (no ML)',                    s_pos),
        ('LR pointwise (binary click)',                       s_lr),
        ('LambdaMART (binary click)',                         s_lm_bin),
        ('LambdaMART (4-class graded, conf-gated train set)', s_lm_4c),
        ('LambdaMART (5-class flat, flavor A)',               s_lm_5flat),
        ('LambdaMART (5-class hybrid, flavor B)',             s_lm_5hybrid),
    ]:
        ndcg, mrr = per_trial_metrics(s, y_click_all, tid_all, k=10)
        print(f'{name:>50s}  {ndcg.mean():>10.4f}  {mrr.mean():>10.4f}  {len(ndcg):>7d}')
        rows[name] = {
            'ndcg10': float(ndcg.mean()),
            'mrr10':  float(mrr.mean()),
            'n_trials': int(len(ndcg)),
        }

    # ── Headline deltas ──
    mrr_5flat = rows['LambdaMART (5-class flat, flavor A)']['mrr10']
    mrr_5hyb  = rows['LambdaMART (5-class hybrid, flavor B)']['mrr10']
    mrr_4c    = rows['LambdaMART (4-class graded, conf-gated train set)']['mrr10']
    mrr_bin   = rows['LambdaMART (binary click)']['mrr10']
    mrr_pos   = rows['Original SERP position (no ML)']['mrr10']

    deltas = {
        'delta_mrr10_5flat_vs_4c':    mrr_5flat - mrr_4c,
        'delta_mrr10_5hybrid_vs_4c':  mrr_5hyb  - mrr_4c,
        'delta_mrr10_5hybrid_vs_5flat': mrr_5hyb - mrr_5flat,
        'delta_mrr10_5hybrid_vs_binary_lambdamart': mrr_5hyb - mrr_bin,
        'delta_mrr10_5hybrid_vs_serp_position': mrr_5hyb - mrr_pos,
    }
    print()
    for k, v in deltas.items():
        print(f'  {k}: {v:+.4f}')

    summary = {
        'experiment': "5-class confidence-gated LTR labels on typed cascade",
        'spec_source': "extends Peter's 4-class with hi/lo confidence sub-buckets per missions-flow logic",
        'date': '2026-05-05',
        'dataset': {
            'records_total': n_total,
            'records_training': n_train,
            'records_eval': n_eval,
            'trials': int(len(np.unique(tid_all))),
            'participants': int(len(np.unique(pid_all))),
            'tier_counts': {k: v for k, v in cls_counts.items() if not k.startswith('_')},
            'thresholds': {
                'median_deferred_dwell_ms': cls_counts['_threshold_median_deferred_dwell_ms'],
                'median_eval_rej_retreat_dist_px': cls_counts['_threshold_median_eval_rej_retreat_dist'],
                'eval_rej_dwell_min_ms': EVAL_REJ_DWELL_MIN_MS,
            },
        },
        'features': M3_NO_POS,
        'method': {
            'flavor_A_flat': 'tier ∈ {1,2,3,4}; tier 0 dropped from training',
            'flavor_B_hybrid': 'tier subdivides by within-tier median(withstood_pre_click); labels ∈ {2,3,4,5,6,7,8} + click at 8',
            'eval_protocol': 'LOSO by participant, train on motivated subset, predict on full dataset, MRR@10 / NDCG@10 against binary-click gold',
        },
        'metrics': rows,
        'headlines': deltas,
        'invariants': [
            'NotApprBelow excluded outright (Peter K27 rule)',
            'tier 0 (eval-rej-lo + NotApprAbove) excluded from training, scored at eval',
            'M3-no-position cursor features only (apples-to-apples with K27)',
        ],
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
