#!/usr/bin/env python3
"""Validating peripheral membership kernels against later fixation -- what
the corpus can say back to PAI.

A peripheral kernel is a claim about what a fixation delivers to a result
it does not land on. The corpus can test the claim without any content
model: intake during the survey phase (first five fixations, NB13) on
results NOT fixated during those five should predict which of them the
searcher fixates later in the trial. A kernel that does this better than
plain gaze distance is carrying something about the periphery; one that
does not is geometry with a weight on it.

For each kernel configuration, on the same candidate set:
  intake rank alone                 LOSO AUC for later fixation
  position + intake rank            vs position alone (paired)
  position + distance + intake      vs position + distance (paired)
Distance = mean rect-boundary distance from the five survey fixations.

Kernels: published Eq. 2 ungated and gated at 100 / 200 / 400 px;
boundary-distance 1/(1+E/E2) at E2 = 1, 2, 4 deg (24 px/deg) ungated and
gated at 200 px; a hard-gate-only kernel (alpha = 1 inside the gate, i.e.
duration within reach). Regime [LAB, AdSERP, typed].
Output: scripts/output/pai_kernel_validation/summary.json
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from pai_spec import rect_alpha_grid  # noqa: E402
from peripheral_kernel import boundary_ogd  # noqa: E402

STATES = ROOT / 'scripts/output/engagement_state_census/gate_200px/states.csv'
OUT = ROOT / 'scripts/output/pai_kernel_validation'
SURVEY_FIX = 5
PX_PER_DEG = 24.0

KERNELS = [
    ('published eq2, ungated', 'spec', None, None),
    ('published eq2, gate 400 px', 'spec', None, 400.0),
    ('published eq2, gate 200 px', 'spec', None, 200.0),
    ('published eq2, gate 100 px', 'spec', None, 100.0),
    ('boundary 1/(1+E/1deg), ungated', 'cm', 1.0, None),
    ('boundary 1/(1+E/2deg), ungated', 'cm', 2.0, None),
    ('boundary 1/(1+E/4deg), ungated', 'cm', 4.0, None),
    ('boundary 1/(1+E/2deg), gate 200 px', 'cm', 2.0, 200.0),
    ('hard gate only, 200 px (duration within reach)', 'gate', None, 200.0),
    ('hard gate only, 100 px', 'gate', None, 100.0),
]


def loso_auc(X, y, pid):
    X = np.asarray(X, float)
    proba = np.full(len(y), np.nan)
    for p in np.unique(pid):
        tr, te = pid != p, pid == p
        if len(set(y[tr])) < 2 or not te.any():
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, class_weight='balanced', C=1.0))
        m.fit(X[tr], y[tr])
        proba[te] = m.predict_proba(X[te])[:, 1]
    ok = np.isfinite(proba)
    folds = {}
    for p in np.unique(pid):
        s = ok & (pid == p)
        if len(set(y[s])) == 2:
            folds[p] = roc_auc_score(y[s], proba[s])
    return float(roc_auc_score(y[ok], proba[ok])), folds


def paired(a, b):
    ps = sorted(set(a) & set(b))
    d = np.array([a[p] - b[p] for p in ps])
    rng = np.random.default_rng(20260914)
    m = rng.choice(d, size=(10000, len(d)), replace=True).mean(axis=1)
    return {'mean_delta': float(d.mean()), 'ci95': np.quantile(m, [.025, .975]).tolist()}


def main():
    import data_loader as dl
    rows = list(csv.DictReader(open(STATES)))
    by = defaultdict(dict)
    for r in rows:
        by[r['trial_id']][int(r['position'])] = r
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)

    # one pass over trials: store per-candidate geometry so every kernel scores the same rows
    cands = []   # (pid, tid, p, later_fixated, ogd[5], alpha_spec[5], fd[5])
    for tid, d in by.items():
        fx_ = dl.load_fixations(tid)
        try:
            bands = dl.typed_aoi_bands(tid)
        except Exception:
            continue
        if not fx_ or len(fx_) <= SURVEY_FIX or not bands:
            continue
        tops = np.asarray([b[0] for b in bands], float)
        bots = np.asarray([b[1] for b in bands], float)
        fx = np.array([f['x'] for f in fx_], float)[:SURVEY_FIX]
        fy = np.array([f['y'] for f in fx_], float)[:SURVEY_FIX]
        fd = np.array([f.get('d', 200) or 200 for f in fx_], float)[:SURVEY_FIX]
        ogd = boundary_ogd(fx, fy, x0, x1, tops, bots)
        a_spec = rect_alpha_grid(fx, fy, x0, x1, tops, bots, weight_placement='eq2')
        inside = ogd == 0
        surveyed = inside.any(axis=0)
        trial_c = []
        for p, r in d.items():
            if p >= len(bands) or surveyed[p] or r['state'] in ('never_onscreen', 'unknown_opportunity') or r['was_clicked'] == '1':
                continue
            trial_c.append((r['pid'], tid, p, int(r['fixated'] == '1'), ogd[:, p], a_spec[:, p], fd))
        if len(trial_c) >= 2:
            cands.extend(trial_c)
    y = np.array([c[3] for c in cands])
    pid = np.array([c[0] for c in cands])
    tid_arr = np.array([c[1] for c in cands])
    pos = np.array([c[2] for c in cands], float)
    dist = np.array([c[4].mean() for c in cands])
    print(f'candidates {len(cands):,} later fixated {int(y.sum()):,} trials {len(set(tid_arr)):,}')

    def within_trial_rank(v, ascending=False):
        out = np.zeros(len(v))
        for t in np.unique(tid_arr):
            m = tid_arr == t
            vv = v[m] if ascending else -v[m]
            out[m] = (np.argsort(np.argsort(vv)) + 1) / m.sum()
        return out

    rdist = within_trial_rank(dist, ascending=True)
    a_pos, f_pos = loso_auc(pos[:, None], y, pid)
    a_pd, f_pd = loso_auc(np.c_[pos, rdist], y, pid)
    a_d, _ = loso_auc(rdist[:, None], y, pid)
    res = {'baselines': {'position only': a_pos, 'distance rank only': a_d, 'position + distance rank': a_pd}, 'kernels': []}
    print(f"baselines: position {a_pos:.3f}  distance rank {a_d:.3f}  position+distance {a_pd:.3f}")
    for name, kind, e2, gate in KERNELS:
        intake = np.zeros(len(cands))
        for i, c in enumerate(cands):
            o, a_s, fdur = c[4], c[5], c[6]
            if kind == 'spec':
                a = a_s
            elif kind == 'cm':
                a = 1.0 / (1.0 + (o / PX_PER_DEG) / e2)
            else:
                a = np.ones_like(o)
            contrib = o > 0
            if gate is not None:
                contrib = contrib & (o <= gate)
            intake[i] = float((fdur * np.where(contrib, a, 0.0)).sum())
        rint = within_trial_rank(intake)
        a_i, _ = loso_auc(rint[:, None], y, pid)
        a_pi, f_pi = loso_auc(np.c_[pos, rint], y, pid)
        a_pdi, f_pdi = loso_auc(np.c_[pos, rdist, rint], y, pid)
        zero = float(np.mean(intake == 0))
        row = {'kernel': name, 'zero_intake_share': zero, 'intake rank alone': a_i,
               'position + intake': a_pi, 'position + distance + intake': a_pdi,
               'gain over position': paired(f_pi, f_pos), 'gain over position + distance': paired(f_pdi, f_pd)}
        res['kernels'].append(row)
        print(f"  {name:48s} zero {zero:.2f}  alone {a_i:.3f}  +pos {a_pi:.3f} ({row['gain over position']['mean_delta']:+.3f})  "
              f"+pos+dist {a_pdi:.3f} ({row['gain over position + distance']['mean_delta']:+.3f} "
              f"[{row['gain over position + distance']['ci95'][0]:+.3f},{row['gain over position + distance']['ci95'][1]:+.3f}])")
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]', 'candidates': len(cands), 'later_fixated': int(y.sum()),
           'px_per_deg': PX_PER_DEG, 'survey_fixations': SURVEY_FIX, **res}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / 'summary.json', 'w'), indent=1)
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
