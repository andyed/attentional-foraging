#!/usr/bin/env python3
"""Does fixation duration buy parafoveal attribution? -- the skip test,
promoted from the 2026-09-14 inline analysis.

PAI accrues peripheral mass as fixation duration x a spatial weight, the
gradient-accrual assumption (SWIFT-like): the longer the eyes rest on result
k, the more parafoveal processing result k+1 receives, so the more likely it
is to be skipped as already processed. The serial-attention alternative
(E-Z Reader-like) says attention moves to k+1 only when foveal processing of
k completes, so a long visit on k means k was hard and k+1 got LESS preview,
and the next forward saccade is LESS likely to skip it.

Unit: every first visit to a typed position k (the run of consecutive
fixations the first entry starts, fixations assigned by the label
producer's rule: typed_aoi_tops + assign_fixation_to_position) whose next
fixated position q is forward (q > k) and not previously fixated (first
pass), on a page where k+1 and k+2 exist. Outcome: skip = q > k+1.
Controls: position k, height of band k+1, whether k+1 is a non-organic
element. Predictors: log visit duration on k, log last-fixation duration in
the visit, log fixation count in the visit. 47-fold LOSO balanced logistic
regression with per-fold scaler; quintiles of visit duration; per-participant
Spearman(visit duration, skip).

Gate: none shipped for this analysis before today; the inline numbers of
2026-09-14 (n 6,834 moves; base AUC 0.637; + duration 0.642, coef -0.156;
quintile skip rates 0.217 -> 0.131) are the reference and the run reports
its distance from them.

Regime [LAB, AdSERP, typed]. Output: scripts/output/duration_parafoveal_accrual/summary.json
Run: .venv/bin/python scripts/duration_parafoveal_accrual.py
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
import data_loader as dl  # noqa: E402

STATES = ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv'
OUT = ROOT / 'scripts/output/duration_parafoveal_accrual'
INLINE = {'n_moves': 6834, 'base_auc': 0.637, 'plus_duration_auc': 0.642, 'coef_log_visit_duration': -0.156,
          'coef_log_last_fixation': -0.093, 'coef_log_fix_count': -0.122, 'quintile_skip': [0.217, 0.201, 0.182, 0.171, 0.131],
          'participants_negative': 34, 'median_spearman': -0.046}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_visits(tid):
    """Yield (k, visit_fixations, next_q, previously_fixated_set) for each first visit."""
    bands = dl.typed_aoi_bands(tid)
    tops = [b[0] for b in bands]
    n = len(tops)
    if n < 3:
        return bands, []
    fixs = dl.load_fixations(tid)
    seq = [dl.assign_fixation_to_position(f['y'], tops, n) for f in fixs]
    seq = [(-1 if (q is None or q < 0) else q) for q in seq]
    out = []
    seen_before = set()       # positions fixated before the current visit started
    entered = set()
    i = 0
    while i < len(seq):
        q = seq[i]
        if q < 0:
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j] == q:
            j += 1
        # run i..j-1 on position q
        if q not in entered:
            entered.add(q)
            # next fixated position after the run
            nxt = None
            for t in range(j, len(seq)):
                if seq[t] >= 0:
                    nxt = seq[t]
                    break
            out.append((q, fixs[i:j], nxt, set(seen_before)))
        seen_before.add(q)
        i = j
    return bands, out


def main():
    rows = list(csv.DictReader(open(STATES)))
    tids = sorted({r['trial_id'] for r in rows})
    recs = []
    n_trials_used = set()
    for tid in tids:
        bands, visits = first_visits(tid)
        n = len(bands)
        for k, vf, q, seen in visits:
            if q is None or q <= k or q in seen:
                continue                      # not a first-pass forward move
            if k + 2 >= n:
                continue                      # k+1 and k+2 must exist
            top1, bot1, et1 = bands[k + 1]
            dur = sum(float(f['d']) for f in vf)
            recs.append({'tid': tid, 'pid': tid.split('-')[0], 'k': k, 'skip': int(q > k + 1),
                         'h_next': float(bot1 - top1), 'ad_next': int(et1 != 'organic'),
                         'log_dur': np.log1p(dur), 'log_last': np.log1p(float(vf[-1]['d'])),
                         'log_nfix': np.log1p(len(vf)), 'dur': dur})
            n_trials_used.add(tid)
    y = np.array([r['skip'] for r in recs]); pid = np.array([r['pid'] for r in recs])
    print(f'moves {len(recs):,}  trials {len(n_trials_used):,}  participants {len(set(pid))}  skip rate {y.mean():.3f}', file=sys.stderr)

    def loso(feats):
        X = np.array([[r[f] for f in feats] for r in recs], float)
        proba = np.full(len(recs), np.nan); coefs = []
        for p in np.unique(pid):
            tr, te = pid != p, pid == p
            m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
            m.fit(X[tr], y[tr]); proba[te] = m.predict_proba(X[te])[:, 1]
            coefs.append(m[-1].coef_[0])
        return float(roc_auc_score(y, proba)), np.mean(coefs, axis=0).tolist()

    base = ['k', 'h_next', 'ad_next']
    models = {}
    for name, feats in [('base', base), ('base+log_dur', base + ['log_dur']), ('base+log_last', base + ['log_last']),
                        ('base+log_nfix', base + ['log_nfix']), ('base+all_three', base + ['log_dur', 'log_last', 'log_nfix'])]:
        auc, coef = loso(feats)
        models[name] = {'features': feats, 'pooled_auc': auc, 'mean_fold_std_coef': dict(zip(feats, coef))}
    # quintiles of visit duration
    dur = np.array([r['dur'] for r in recs])
    edges = np.quantile(dur, [0.2, 0.4, 0.6, 0.8])
    qbin = np.searchsorted(edges, dur, side='right')
    quint = [{'quintile': i + 1, 'n': int((qbin == i).sum()), 'p_skip': float(y[qbin == i].mean()),
              'dur_ms_range': [float(dur[qbin == i].min()), float(dur[qbin == i].max())]} for i in range(5)]
    # per participant spearman
    sp = {}
    for p in np.unique(pid):
        m = pid == p
        if m.sum() >= 20 and len(set(y[m])) == 2:
            sp[p] = float(spearmanr(dur[m], y[m]).correlation)
    spv = np.array(list(sp.values()))
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]',
           'inputs': {'states_csv': str(STATES.relative_to(ROOT)), 'states_sha256': sha(STATES),
                      'fixation_rule': 'typed_aoi_tops + assign_fixation_to_position (label producer)'},
           'population': {'moves': len(recs), 'trials': len(n_trials_used), 'participants': int(len(set(pid))),
                          'skip_rate': float(y.mean())},
           'models': models,
           'quintiles_visit_duration': quint,
           'per_participant_spearman_dur_skip': {'n_participants': len(sp), 'negative': int((spv < 0).sum()),
                                                 'median': float(np.median(spv)), 'iqr': [float(np.percentile(spv, 25)), float(np.percentile(spv, 75))]},
           'inline_reference_2026_09_14': INLINE}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / 'summary.json', 'w'), indent=1)
    print(f"moves {len(recs):,} (inline {INLINE['n_moves']:,}); trials {len(n_trials_used):,}; skip rate {y.mean():.3f}")
    for name, m in models.items():
        extra = {k: round(v, 3) for k, v in m['mean_fold_std_coef'].items() if k.startswith('log_')}
        print(f"  {name:16s} AUC {m['pooled_auc']:.3f}  {extra}")
    print('  quintile P(skip):', [round(q['p_skip'], 3) for q in quint], '(inline', INLINE['quintile_skip'], ')')
    print(f"  per-participant Spearman: negative in {out['per_participant_spearman_dur_skip']['negative']}/{len(sp)}, median {np.median(spv):+.3f}")
    print(f'wrote {OUT / "summary.json"}')


if __name__ == '__main__':
    main()
