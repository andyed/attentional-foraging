#!/usr/bin/env python3
"""Why the deferred-class classifier moved from the May figure to 0.691 --
a ladder that changes one thing per rung, holding the LOSO protocol and the
NB22 gaze-regression label fixed.

Question (Peter Dixon-Moses, 2026-09-16): "deferred classifier, cursor-only:
0.753 | 0.691 -- which change primarily accounts for this drop? Is there still
a constant standoff-distance threshold used in featurizing?"

Rungs (all: 47-fold LOSO balanced logistic regression on the seven M4
features, target = gaze-regression label deferred=1 / evaluated-rejected=0,
pooled out-of-fold AUC; the label is the typed NB22 cache keyed by
(trial, position) throughout):

  L   LAB stream, typed, click-anchored buf500 (removes ~no samples):
      rows selected by fixation, cursor sampled at fixation times, distances
      are gaze-to-cursor, proximity dwell is fixation-duration weighted.
      Pool = approached (LAB min_dist < 100 px) non-click rows. This is the
      lineage the May number came from (May used the organic flavour on the
      pre-fix substrate; the organic rung is added when its label cache exists).
  G0  cursor-only tracker features, cursor sampled at fixation onsets
      (gaze-gated cache), press-anchored buf0, on the SAME rows as L.
      L -> G0 isolates the feature definition (1-D cursor-to-centre distance
      and the tracker's accumulators vs gaze-cursor distance at fixations).
  N0  cursor-only, native mousemove sampling, buf0, same rows.
      G0 -> N0 isolates sampling.
  N5  cursor-only, native, press-anchored buf500, same rows.
      N0 -> N5 isolates the buffer (the LAB buffer removed nothing).
  C   cursor-only, native, buf500, the full approached (cursor min_dist < 100)
      non-click pool. N5 -> C isolates the row population.

Gate: rung C reproduces scripts/output/m4_cursor_only_downstream/summary.json
section_4_3.deployable_M4_7.pooled_auc to 1e-6.

Output: scripts/output/deferred_drop_decomposition/summary.json
Run:    .venv/bin/python scripts/deferred_drop_decomposition.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from m4_cursor_aoi_rerun import APPROACH_7  # noqa: E402
from m4_cursor_only_downstream import loso_proba, summarize, paired, fold_aucs  # noqa: E402

DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/deferred_drop_decomposition'
APPROACH_PX = 100


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def labels(flavor='typed'):
    rows = json.loads((DATA / f'cursor-approach-features-{flavor}.json').read_text())
    reg_p = ROOT / f'scripts/output/approach_threshold_sensitivity/regression_labels_cache_{flavor}.json'
    if not reg_p.exists():
        return None, None
    reg = json.loads(reg_p.read_text())
    assert len(rows) == len(reg)
    return {(r['trial_id'], r['position']): bool(v) for r, v in zip(rows, reg)}, reg_p


def score(records, label_by_key, pool_keys=None, name=''):
    """LOSO on `records` restricted to pool_keys (or to approached non-clicks if None)."""
    recs = sorted(records, key=lambda r: (r['trial_id'], r['position']))
    keys = [(r['trial_id'], r['position']) for r in recs]
    y = np.asarray([int(label_by_key.get(k, False)) for k in keys])
    clicked = np.asarray([int(r['was_clicked']) for r in recs])
    if pool_keys is None:
        mask = np.asarray([r['min_dist'] < APPROACH_PX for r in recs]) & (clicked == 0)
    else:
        mask = np.asarray([k in pool_keys for k in keys])
    proba, pid = loso_proba(recs, APPROACH_7, y, mask)
    s, folds = summarize(y, proba, pid, mask)
    s['rung'] = name
    s['n_deferred'] = int(y[mask].sum()); s['n_rejected'] = int((mask & (y == 0)).sum())
    return s, folds, set(k for k, m in zip(keys, mask) if m)


def main():
    lab_by_key, lab_reg_p = labels('typed')
    assert lab_by_key is not None
    # ---- rung L: LAB typed buf500 ------------------------------------------
    lab_p = DATA / 'cursor-approach-features-typed-buf500.json'
    lab = json.loads(lab_p.read_text())
    L, L_folds, L_pool = score(lab, lab_by_key, None, 'L: LAB typed (fixation rows, gaze-cursor distance, click-anchored buf500)')
    # ---- cursor-only caches -----------------------------------------------
    cur_p = DATA / 'cursor-only-typed-features-mousedown.json'
    gg_p = DATA / 'cursor-only-typed-features-mousedown-gazegated.json'
    cur = json.loads(cur_p.read_text())['conditions']
    gg = json.loads(gg_p.read_text())['conditions']
    cur_keys = {(r['trial_id'], r['position']) for r in cur['buf500']}
    gg_keys = {(r['trial_id'], r['position']) for r in gg['buf500']}
    shared_pool = {k for k in L_pool if k in cur_keys and k in gg_keys}
    G0, G0_folds, _ = score(gg['buf0'], lab_by_key, shared_pool, 'G0: cursor-only features, fixation-onset sampling, buf0, LAB rows')
    G5, G5_folds, _ = score(gg['buf500'], lab_by_key, shared_pool, 'G5: cursor-only, fixation-onset sampling, buf500, LAB rows')
    N0, N0_folds, _ = score(cur['buf0'], lab_by_key, shared_pool, 'N0: cursor-only, native sampling, buf0, LAB rows')
    N5, N5_folds, _ = score(cur['buf500'], lab_by_key, shared_pool, 'N5: cursor-only, native sampling, buf500, LAB rows')
    Ls, Ls_folds, _ = score(lab, lab_by_key, shared_pool, 'L on the shared rows (same rows as G0/N0/N5)')
    C, C_folds, C_pool = score(cur['buf500'], lab_by_key, None, 'C: cursor-only, native, buf500, full approached non-click pool')
    # ---- gate ------------------------------------------------------------
    shipped = json.loads((ROOT / 'scripts/output/m4_cursor_only_downstream/summary.json').read_text())['section_4_3']['deployable_M4_7']['pooled_auc']
    g = abs(C['pooled_auc'] - shipped)
    assert g < 1e-6, f'gate failed: rung C {C["pooled_auc"]} vs shipped {shipped}'
    # ---- optional: the organic LAB rung (the May flavour) --------------------
    organic = None
    org_by_key, org_reg_p = labels('organic')
    org_p = DATA / 'cursor-approach-features-organic-buf500.json'
    if org_by_key is not None and org_p.exists():
        O, _, O_pool = score(json.loads(org_p.read_text()), org_by_key, None, 'O: LAB organic buf500 (May flavour, post-coordinate-conversion cache)')
        organic = {'summary': O, 'label_cache': str(org_reg_p.relative_to(ROOT)), 'cache_sha256': sha(org_p)}
    # ---- the standoff threshold: pool size and AUC at 50 / 100 / 200 px on rung C ----
    thr = {}
    recs = sorted(cur['buf500'], key=lambda r: (r['trial_id'], r['position']))
    keys = [(r['trial_id'], r['position']) for r in recs]
    y = np.asarray([int(lab_by_key.get(k, False)) for k in keys]); clicked = np.asarray([int(r['was_clicked']) for r in recs])
    for px in (50, 100, 200):
        mask = np.asarray([r['min_dist'] < px for r in recs]) & (clicked == 0)
        proba, pid = loso_proba(recs, APPROACH_7, y, mask)
        s, _ = summarize(y, proba, pid, mask)
        thr[str(px)] = {'pool': int(mask.sum()), 'pooled_auc': s['pooled_auc']}
    steps = [('L → G0 (feature definition; LAB rows)', Ls_folds, G0_folds),
             ('G0 → N0 (sampling: fixation onsets → native)', G0_folds, N0_folds),
             ('N0 → N5 (press buffer 0 → 500 ms)', N0_folds, N5_folds),
             ('N5 → C (rows: LAB fixation-selected → full cursor pool)', N5_folds, C_folds)]
    ladder = [Ls, G0, N0, N5, C]
    out = {'schema_version': 1, 'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'regime': '[LAB, AdSERP, typed]',
           'inputs': {'lab_cache': str(lab_p.relative_to(ROOT)), 'lab_cache_sha256': sha(lab_p),
                      'cursor_cache': str(cur_p.relative_to(ROOT)), 'cursor_cache_sha256': sha(cur_p),
                      'gazegated_cache': str(gg_p.relative_to(ROOT)), 'gazegated_cache_sha256': sha(gg_p),
                      'label_cache': str(lab_reg_p.relative_to(ROOT)), 'label_cache_sha256': sha(lab_reg_p)},
           'gate': {'rung_C_pooled_auc': C['pooled_auc'], 'shipped_deployable_pooled_auc': shipped, 'abs_diff': g},
           'population': {'lab_pool': len(L_pool), 'shared_rows': len(shared_pool), 'full_cursor_pool': len(C_pool)},
           'rungs': {'L_full_lab_pool': L, 'L_shared_rows': Ls, 'G0': G0, 'G5': G5, 'N0': N0, 'N5': N5, 'C': C},
           'steps_paired_participant': {name: paired(b, a) for name, a, b in steps},
           'organic_rung': organic,
           'standoff_threshold_on_C': {'note': 'approached = cursor min_dist < px (1-D vertical distance to the AOI centre); the 100 px zone is still a constant', **thr}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / 'summary.json', 'w'), indent=1)
    print(f"gate: rung C {C['pooled_auc']:.4f} vs shipped {shipped:.4f} (diff {g:.1e})")
    print(f"pools: LAB {len(L_pool):,}  shared {len(shared_pool):,}  full cursor {len(C_pool):,}")
    print(f"\n{'rung':70s} pooled  fold mean±sd   n (deferred/rejected)")
    for s in [L] + ladder:
        print(f"  {s['rung']:68s} {s['pooled_auc']:.3f}  {s['fold_auc_mean']:.3f}±{s['fold_auc_sd']:.3f}  {s['n_records']:,} ({s['n_deferred']:,}/{s['n_rejected']:,})")
    print(f"  {G5['rung']:68s} {G5['pooled_auc']:.3f}  (the matched-row ceiling protocol on these rows)")
    print('\nsteps (paired participant Δ, 95% CI):')
    for name, a, b in steps:
        d = paired(b, a); print(f"  {name:60s} {d['mean_delta']:+.3f} [{d['bootstrap_ci95'][0]:+.3f}, {d['bootstrap_ci95'][1]:+.3f}]")
    if organic:
        print(f"\norganic LAB rung (May flavour, current cache): {organic['summary']['pooled_auc']:.3f} on {organic['summary']['n_records']:,} rows")
    print('\nstandoff threshold on rung C:', {k: (v['pool'], round(v['pooled_auc'], 3)) for k, v in thr.items()})
    print(f'\nwrote {OUT / "summary.json"}')


if __name__ == '__main__':
    main()
