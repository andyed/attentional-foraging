"""STUB-A: §4.2 NB22 trial-level recompute under bbox-organic attribution.

Closes the §4.2 prose gaps:
  - NB21 classifier-threshold deferred / eval-rejected split (was 1,418 / 937)
  - NB22 gaze-regression deferred / eval-rejected split (was 1,916 / 439)
  - Deferred:eval-rejected ratio (was 81/19; expected 75/25 under organic)
  - % of trials with ≥1 deferred episode (was 53%)
  - % of trials with any evaluated-rejected episode (was 17%)
  - Jaccard overlap of the two evaluated-rejected sets (was 0.125)
  - NB21-vs-NB22 label disagreement % (was 45.4%)

Population: approached non-click episodes under bbox-organic AOIs.
  approached = min_dist < APPROACH_THRESHOLD_PX (100 px, NB22 convention)
  non-click  = NOT was_clicked

NB21 rule: train LOSO LR on M3 features (position + 9 approach) with
was_clicked target; compute OOF p_click; pick Youden-J threshold from
the full-population ROC; classify approached non-click as
  NB21-deferred       = p_click ≥ J
  NB21-eval-rejected  = p_click < J

NB22 rule (gaze-regression): use the regression_labels_cache_organic.json
will_regress flag computed by compute_regression_labels.py
  NB22-deferred       = will_regress
  NB22-eval-rejected  = NOT will_regress

Outputs:
  scripts/output/aoi-consumer-cascade/nb22_trial_level_organic.json
  + stdout summary

Run:
  .venv/bin/python scripts/nb22_trial_level_organic.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
APPROACH_THRESHOLD_PX = 100.0

FEAT_PATH = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
REG_PATH = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'

M4_FEATURES = [
    'min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
    'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
    'direction_changes', 'frac_decreasing',
]


def youden_j(y_true, p_proba):
    """Return the threshold that maximizes Youden's J = TPR - FPR."""
    fpr, tpr, thr = roc_curve(y_true, p_proba)
    j = tpr - fpr
    idx = int(np.argmax(j))
    return float(thr[idx]), float(j[idx])


def main():
    print(f'[load] features + regression labels under [organic]', file=sys.stderr)
    records = json.load(open(FEAT_PATH))
    will_regress_all = json.load(open(REG_PATH))
    assert len(records) == len(will_regress_all)
    print(f'  {len(records):,} records', file=sys.stderr)

    # Arrays
    was_clicked = np.array([bool(r.get('was_clicked', False)) for r in records])
    will_regress = np.array(will_regress_all, dtype=bool)
    min_dist = np.array([float(r.get('min_dist', 1e9) or 1e9) for r in records])
    approached = min_dist < APPROACH_THRESHOLD_PX
    pos = np.array([int(r['position']) for r in records])
    tid = np.array([r['trial_id'] for r in records])
    pid = np.array([r['trial_id'].split('-')[0] for r in records])

    # M3 feature matrix (position + total_dwell_ms + 9 approach features)
    total_dwell = np.array([float(r.get('total_dwell_ms', 0.0) or 0.0) for r in records])
    X9 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4_FEATURES] for r in records])
    X3 = np.column_stack([pos.reshape(-1, 1), total_dwell.reshape(-1, 1), X9])

    print(f'\n[NB21] Training LOSO LR (M3 features → was_clicked)...', file=sys.stderr)
    pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
    ])
    p_click = cross_val_predict(pipe, X3, was_clicked.astype(int),
                                 groups=pid, cv=LeaveOneGroupOut(),
                                 method='predict_proba', n_jobs=-1)[:, 1]

    j_thr, j_value = youden_j(was_clicked.astype(int), p_click)
    print(f'  Youden-J threshold: p = {j_thr:.4f} (J = {j_value:.4f})', file=sys.stderr)

    # ── Apply taxonomy rules to the approached non-click subset ──
    non_click = approached & ~was_clicked
    n_pop = int(non_click.sum())
    print(f'\n[population] approached non-click subset: n = {n_pop:,}', file=sys.stderr)

    # NB21 classifier-threshold split
    nb21_deferred = non_click & (p_click >= j_thr)
    nb21_evrej = non_click & (p_click < j_thr)
    n_nb21_def = int(nb21_deferred.sum())
    n_nb21_rej = int(nb21_evrej.sum())

    # NB22 gaze-regression split
    nb22_deferred = non_click & will_regress
    nb22_evrej = non_click & ~will_regress
    n_nb22_def = int(nb22_deferred.sum())
    n_nb22_rej = int(nb22_evrej.sum())

    print(f'\n=== NB21 classifier-threshold split (Youden-J p = {j_thr:.4f}) ===')
    print(f'  deferred           : {n_nb21_def:>5,}  ({100 * n_nb21_def / n_pop:.1f}%)')
    print(f'  evaluated-rejected : {n_nb21_rej:>5,}  ({100 * n_nb21_rej / n_pop:.1f}%)')

    print(f'\n=== NB22 gaze-regression split ===')
    print(f'  deferred           : {n_nb22_def:>5,}  ({100 * n_nb22_def / n_pop:.1f}%)')
    print(f'  evaluated-rejected : {n_nb22_rej:>5,}  ({100 * n_nb22_rej / n_pop:.1f}%)')

    # ── Per-trial coverage rates ──
    n_trials = len(set(tid))
    trials_with_nb22_def = len({tid[i] for i in range(len(tid)) if nb22_deferred[i]})
    trials_with_nb22_rej = len({tid[i] for i in range(len(tid)) if nb22_evrej[i]})
    trials_with_nb21_def = len({tid[i] for i in range(len(tid)) if nb21_deferred[i]})
    trials_with_nb21_rej = len({tid[i] for i in range(len(tid)) if nb21_evrej[i]})

    print(f'\n=== Per-trial coverage (n_trials = {n_trials:,}) ===')
    print(f'  trials with ≥1 NB22-deferred       : {trials_with_nb22_def:>5,}  '
          f'({100 * trials_with_nb22_def / n_trials:.1f}%)')
    print(f'  trials with ≥1 NB22-eval-rejected  : {trials_with_nb22_rej:>5,}  '
          f'({100 * trials_with_nb22_rej / n_trials:.1f}%)')
    print(f'  trials with ≥1 NB21-deferred       : {trials_with_nb21_def:>5,}  '
          f'({100 * trials_with_nb21_def / n_trials:.1f}%)')
    print(f'  trials with ≥1 NB21-eval-rejected  : {trials_with_nb21_rej:>5,}  '
          f'({100 * trials_with_nb21_rej / n_trials:.1f}%)')

    # ── Jaccard overlap of NB21 vs NB22 eval-rejected sets ──
    nb21_rej_set = {(tid[i], pos[i]) for i in range(len(tid)) if nb21_evrej[i]}
    nb22_rej_set = {(tid[i], pos[i]) for i in range(len(tid)) if nb22_evrej[i]}
    inter = nb21_rej_set & nb22_rej_set
    union = nb21_rej_set | nb22_rej_set
    jaccard_evrej = len(inter) / max(len(union), 1)
    print(f'\n=== Jaccard overlap of NB21 vs NB22 evaluated-rejected sets ===')
    print(f'  NB21 eval-rej  : {len(nb21_rej_set):>5,}')
    print(f'  NB22 eval-rej  : {len(nb22_rej_set):>5,}')
    print(f'  intersection   : {len(inter):>5,}')
    print(f'  union          : {len(union):>5,}')
    print(f'  Jaccard        : {jaccard_evrej:.3f}')

    # ── NB21 vs NB22 label disagreement % on approached non-click ──
    nb21_label = np.where(non_click, np.where(nb21_deferred, 'D', 'R'), 'X')  # X = not in pop
    nb22_label = np.where(non_click, np.where(nb22_deferred, 'D', 'R'), 'X')
    in_pop = non_click
    n_disagree = int(((nb21_label != nb22_label) & in_pop).sum())
    disagree_pct = 100 * n_disagree / max(in_pop.sum(), 1)
    print(f'\n=== NB21 vs NB22 label disagreement (approached non-click) ===')
    print(f'  disagreements: {n_disagree:,} / {int(in_pop.sum()):,} = {disagree_pct:.1f}%')

    # Confusion (NB21 rows × NB22 cols)
    n_DD = int(((nb21_label == 'D') & (nb22_label == 'D') & in_pop).sum())
    n_DR = int(((nb21_label == 'D') & (nb22_label == 'R') & in_pop).sum())
    n_RD = int(((nb21_label == 'R') & (nb22_label == 'D') & in_pop).sum())
    n_RR = int(((nb21_label == 'R') & (nb22_label == 'R') & in_pop).sum())
    print(f'\n  Confusion (NB21 rows × NB22 cols):')
    print(f'                 NB22-D    NB22-R')
    print(f'    NB21-D     {n_DD:>5,}   {n_DR:>5,}')
    print(f'    NB21-R     {n_RD:>5,}   {n_RR:>5,}')

    # ── Save ──
    out = {
        'attribution': 'organic',
        'population_n': n_pop,
        'n_trials': n_trials,
        'youden_j_threshold': float(j_thr),
        'nb21': {
            'deferred': n_nb21_def, 'deferred_pct': 100 * n_nb21_def / n_pop,
            'eval_rejected': n_nb21_rej, 'eval_rejected_pct': 100 * n_nb21_rej / n_pop,
            'trials_with_deferred': trials_with_nb21_def,
            'trials_with_deferred_pct': 100 * trials_with_nb21_def / n_trials,
            'trials_with_eval_rejected': trials_with_nb21_rej,
            'trials_with_eval_rejected_pct': 100 * trials_with_nb21_rej / n_trials,
        },
        'nb22': {
            'deferred': n_nb22_def, 'deferred_pct': 100 * n_nb22_def / n_pop,
            'eval_rejected': n_nb22_rej, 'eval_rejected_pct': 100 * n_nb22_rej / n_pop,
            'trials_with_deferred': trials_with_nb22_def,
            'trials_with_deferred_pct': 100 * trials_with_nb22_def / n_trials,
            'trials_with_eval_rejected': trials_with_nb22_rej,
            'trials_with_eval_rejected_pct': 100 * trials_with_nb22_rej / n_trials,
        },
        'eval_rejected_jaccard': {
            'nb21_n': len(nb21_rej_set),
            'nb22_n': len(nb22_rej_set),
            'intersection': len(inter),
            'union': len(union),
            'jaccard': float(jaccard_evrej),
        },
        'disagreement': {
            'n_disagree': n_disagree,
            'pct': float(disagree_pct),
            'confusion': {'D_D': n_DD, 'D_R': n_DR, 'R_D': n_RD, 'R_R': n_RR},
        },
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/nb22_trial_level_organic.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
