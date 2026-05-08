"""Ordinality τ-agreement test.

Question: do NB21 (cursor-classifier-threshold) and NB22 (gaze-regression)
binary deferred / eval-rejected labels reduce to two thresholds on a shared
latent ordinal of within-trial consideration?

Procedure:
  1. Restrict to approached non-click subset (the 2x2 population, n=2,070).
  2. For each trial with >=2 approached non-clicks, compute within-trial
     Kendall tau between candidate ordinal scores: total_dwell_ms,
     n_fixations, dwell_in_proximity_ms, -min_dist, p_click (LOSO M3 LR).
  3. AUC test: does binary NB21 / NB22 label predict from a single ordinal
     score on the non-click subset? If both rules score high on the same
     score, the "two thresholds on shared ordinal" reading holds.

Run:
  .venv/bin/python scripts/ordinality_tau_test.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
REG = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'
APPROACH_THR = 100.0

M4 = ['min_dist', 'mean_dist', 'final_dist', 'retreat_dist',
      'dwell_in_proximity_ms', 'mean_approach_velocity', 'max_approach_velocity',
      'direction_changes', 'frac_decreasing']


def main():
    print('[load] features + regression labels (organic)', file=sys.stderr)
    records = json.load(open(FEAT))
    will_regress = np.array(json.load(open(REG)), dtype=bool)
    assert len(records) == len(will_regress)

    pos = np.array([int(r['position']) for r in records])
    tid = np.array([r['trial_id'] for r in records])
    pid = np.array([t.split('-')[0] for t in tid])
    md = np.array([float(r.get('min_dist', 1e9) or 1e9) for r in records])
    wc = np.array([bool(r.get('was_clicked', False)) for r in records])
    approached = md < APPROACH_THR
    non_click = approached & ~wc

    total_dwell = np.array([float(r.get('total_dwell_ms', 0.0) or 0.0) for r in records])
    n_fix = np.array([int(r.get('n_fixations', 0) or 0) for r in records], dtype=float)
    dwell_prox = np.array([float(r.get('dwell_in_proximity_ms', 0.0) or 0.0) for r in records])

    # NB21 LOSO p_click on M3 (position + total_dwell + 9 approach features)
    print('[fit] LOSO LR for p_click (M3 features)', file=sys.stderr)
    X9 = np.array([[float(r.get(f, 0.0) or 0.0) for f in M4] for r in records])
    X3 = np.column_stack([pos.reshape(-1, 1), total_dwell.reshape(-1, 1), X9])
    pipe = Pipeline([
        ('s', StandardScaler()),
        ('lr', LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0)),
    ])
    p_click = cross_val_predict(pipe, X3, wc.astype(int),
                                groups=pid, cv=LeaveOneGroupOut(),
                                method='predict_proba', n_jobs=-1)[:, 1]
    fpr, tpr, thr = roc_curve(wc.astype(int), p_click)
    j_idx = int(np.argmax(tpr - fpr))
    j_thr = float(thr[j_idx])
    nb21_def = non_click & (p_click >= j_thr)
    nb22_def = non_click & will_regress

    # Candidate ordinal scores (higher = more considered)
    cands = {
        'total_dwell_ms': total_dwell,
        'n_fixations': n_fix,
        'dwell_in_proximity_ms': dwell_prox,
        'neg_min_dist': -md,
        'p_click_loso': p_click,
    }

    # Build per-trial index of non-click positions
    trial_to_idx = defaultdict(list)
    for i in np.where(non_click)[0]:
        trial_to_idx[tid[i]].append(i)
    multi = {t: np.array(idxs) for t, idxs in trial_to_idx.items() if len(idxs) >= 2}
    n_pos = sum(len(v) for v in multi.values())
    print(f'\ntrials with >=2 approached non-click: {len(multi):,}  '
          f'positions: {n_pos:,}  '
          f'(of {int(non_click.sum()):,} total)', file=sys.stderr)

    def within_trial_tau(s_a, s_b):
        taus, ws = [], []
        for idxs in multi.values():
            a = s_a[idxs]; b = s_b[idxs]
            if np.unique(a).size < 2 or np.unique(b).size < 2:
                continue
            t, _ = kendalltau(a, b)
            if np.isnan(t):
                continue
            taus.append(t); ws.append(len(idxs))
        return np.array(taus), np.array(ws)

    print('\n=== Pairwise within-trial Kendall tau (n-weighted mean across trials) ===\n')
    keys = list(cands.keys())
    width = 22
    header = ' ' * width + ''.join(f'{k:>{width}s}' for k in keys)
    print(header)
    tau_summary = {}
    for ka in keys:
        cells = [f'{ka:>{width}s}']
        for kb in keys:
            if ka == kb:
                cells.append(f'{1.000:>{width}.3f}')
                continue
            taus, ws = within_trial_tau(cands[ka], cands[kb])
            if len(taus) == 0:
                tau_w = float('nan')
            else:
                tau_w = float(np.average(taus, weights=ws))
            tau_summary[f'{ka}__{kb}'] = tau_w
            cells.append(f'{tau_w:>{width}.3f}')
        print(''.join(cells))

    # ── AUC of binary deferred label scored by ordinal s, on non-click subset ──
    print('\n=== AUC: binary "deferred" label scored by ordinal s (non-click subset) ===')
    print(f'  if both rules are thresholds on a shared ordinal s, both AUCs are high on the same s.\n')
    print(f'{"score":>22s}  {"NB21-AUC":>10s}  {"NB22-AUC":>10s}  {"note":<40s}')
    auc_summary = {}
    for k, s in cands.items():
        s_sub = s[non_click]
        nb21_sub = nb21_def[non_click].astype(int)
        nb22_sub = nb22_def[non_click].astype(int)
        try:
            a21 = float(roc_auc_score(nb21_sub, s_sub))
        except Exception:
            a21 = float('nan')
        try:
            a22 = float(roc_auc_score(nb22_sub, s_sub))
        except Exception:
            a22 = float('nan')
        note = ''
        if k == 'p_click_loso':
            note = '(circular for NB21 by construction)'
        print(f'{k:>22s}  {a21:>10.3f}  {a22:>10.3f}  {note:<40s}')
        auc_summary[k] = {'nb21': a21, 'nb22': a22}

    # ── Sanity: where does the click sit on each ordinal? ──
    # In trials that have both a click and >=1 approached non-click, what is the
    # within-trial rank of the click position by each candidate score?
    trial_click = {}
    trial_nc = defaultdict(list)
    for i in np.where(approached)[0]:
        if wc[i]:
            trial_click[tid[i]] = i
        else:
            trial_nc[tid[i]].append(i)
    co_trials = [t for t in trial_click if t in trial_nc]
    print(f'\n=== Sanity: click rank within trial (trials with click + >=1 approached non-click; '
          f'n={len(co_trials):,}) ===')
    print(f'  click should rank near top (= score 1.0 if always rank-1)')
    print(f'{"score":>22s}  {"click-rank-mean":>16s}  {"frac click=rank1":>18s}')
    click_rank_summary = {}
    for k, s in cands.items():
        ranks = []
        rank1 = 0
        for t in co_trials:
            ci = trial_click[t]
            ncs = trial_nc[t]
            scores = np.concatenate([[s[ci]], s[ncs]])
            # rank of click (1 = top) using ties->average
            order = np.argsort(-scores, kind='stable')
            rank_of_click = int(np.where(order == 0)[0][0]) + 1
            ranks.append(rank_of_click / len(scores))  # normalized
            if rank_of_click == 1:
                rank1 += 1
        ranks = np.array(ranks)
        print(f'{k:>22s}  {ranks.mean():>16.3f}  {rank1/len(co_trials):>18.3f}')
        click_rank_summary[k] = {'mean_norm_rank': float(ranks.mean()),
                                  'frac_rank1': rank1 / len(co_trials)}

    # ── Save ──
    out = {
        'attribution': 'organic',
        'population': {
            'approached_non_click': int(non_click.sum()),
            'trials_with_2plus_nc': len(multi),
            'positions_in_2plus': n_pos,
            'co_trials_for_click_rank': len(co_trials),
        },
        'youden_j_threshold': j_thr,
        'tau_pairs': tau_summary,
        'auc_per_score': auc_summary,
        'click_rank_per_score': click_rank_summary,
    }
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/ordinality_tau_test.json'
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
