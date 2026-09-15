#!/usr/bin/env python3
"""PAI on the deferred class -- does peripheral gaze mass separate the results
the eyes come back to from the ones they reject?

Assessment probe (2026-09-14) for whether PAI has a place in the CHIIR 2027
divergence framing. Same rows, labels, anchor and scorer as
deferred_dwell_carve.py --labeled-only (the 9,269 label-complete approached
non-click rows on the cursor-only typed buf500 mousedown cache), so every
number here sits beside the carve's M4-7 0.680 / mean_dist 0.665 /
first-visit gaze dwell 0.514 without a pool change.

Kernel: spec_eq2 (the authors' Eq. 2 via pai_spec.rect_alpha_grid), bare
"PAI" per the 2026-08-31 kernel policy. Peripheral = strictly outside the
typed band rect (containment gate belongs to the harness, not the alpha).

Two windows per (trial, position), both on the typed map the label was built
on, fixations assigned by the label producer's own rule:

  pre   [first_visit_start - W, first_visit_start)   -- before the eyes ever land
  post  [first_visit_end, first_visit_end + W)        -- after they leave,
         truncated at the return (deferred rows) and at the trial's last
         fixation. The x500 variant also drops the 500 ms before the return,
         the same buffer logic the cursor features use at the press: without
         it the last fixations before a return are approach fixations and the
         alpha ramp is mechanical.

In the post window, point-in-AOI dwell is identically zero for every row
(the visit has ended and the return has not started), so the traditional
gaze metric's floor is 0.5 by construction; PAI is the only gaze channel
with content there. Features are rates (mass / available window) because
accumulation over unequal windows is the LF/HF record-length trap
(pai_exposure_validation.md, Probe A). `avail_post_ms` is scored alone as
the leak check: if window length predicts the label, the rate is
contaminated by trial structure, not by the periphery.

Gaze-distance control: mean |fixation_y - band centre| over the same window.
If a plain gaze distance scores the same as PAI, the finding is gaze
proximity, not PAI as such.

Output: scripts/output/pai_deferred_probe/summary.json
Run:    .venv/bin/python scripts/pai_deferred_probe.py [--perms 50] [--limit N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))

from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from m4_cursor_aoi_rerun import APPROACH_7, load_flavor_cards, main_cards  # noqa: E402
from m4_cursor_only_downstream import loso_proba, summarize, paired  # noqa: E402
from deferred_dwell_carve import visit_decomposition, perm_null  # noqa: E402
from peripheral_kernel import alpha_grid, add_kernel_args, kernel_label  # noqa: E402

OUT_DIR = ROOT / 'scripts/output/pai_deferred_probe'
APPROACH_PX = 100.0
WINDOW_MS = 2000.0   # overridable with --window
MIN_AVAIL_MS = 250.0
RETURN_BUFFER_MS = 500.0

PAI_FEATS = ('pai_pre', 'pai_post', 'pai_post_x500',
             'gaze_dist_pre', 'gaze_dist_post', 'avail_post_ms', 'avail_pre_ms',
             'n_fix_post', 'n_fix_pre')


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def walk_visits(dl, tid, tops):
    """Visits per position as (t_start, t_end) lists, by the label producer's
    rule (bisect on typed band tops; an unassigned fixation breaks the run).
    Mirrors deferred_dwell_carve.visit_decomposition, which is asserted
    against below on first_visit_end so the two walks cannot drift."""
    n_res = len(tops)
    visits = {}
    cur_pos, cur = None, None
    for f in dl.load_fixations(tid):
        p = dl.assign_fixation_to_position(f['y'], tops, n_res)
        if p is None or p < 0:
            if cur is not None:
                visits.setdefault(cur_pos, []).append(cur)
                cur_pos, cur = None, None
            continue
        if p != cur_pos:
            if cur is not None:
                visits.setdefault(cur_pos, []).append(cur)
            cur_pos, cur = p, [float(f['t']), float(f['t'])]
        cur[1] = float(f['t'])
    if cur is not None:
        visits.setdefault(cur_pos, []).append(cur)
    return visits


def window_stats(ft, fd, outside_col, alpha_col, dist_col, t0, t1):
    """Peripheral spec_eq2 mass rate and mean gaze distance over [t0, t1).
    Returns (pai_rate_per_s, mean_dist_px, avail_ms) or NaNs if the window
    is shorter than MIN_AVAIL_MS."""
    avail = t1 - t0
    if avail < MIN_AVAIL_MS:
        return np.nan, np.nan, np.nan, np.nan
    sel = (ft >= t0) & (ft < t1)
    if not sel.any():
        return 0.0, np.nan, avail, 0.0
    mass = float((fd[sel] * np.where(outside_col[sel], alpha_col[sel], 0.0)).sum())
    return mass / (avail / 1000.0), float(dist_col[sel].mean()), avail, float(sel.sum())


def main():
    global WINDOW_MS
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--carve', type=Path,
                    default=ROOT / 'scripts/output/deferred_dwell_carve/summary_labeled_only.json')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--perms', type=int, default=50)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    ap.add_argument('--window', type=float, default=WINDOW_MS)
    add_kernel_args(ap)
    ap.add_argument('--full-window-only', action='store_true',
                    help='score only rows whose post/pre window is untruncated '
                         '(avail == window), removing window length as a channel')
    args = ap.parse_args()
    WINDOW_MS = float(args.window)

    import data_loader as dl

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    want = sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}']
    got = hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest()
    if want != got:
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    records = sorted(stored, key=lambda r: (r['trial_id'], r['position']))

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    assert len(lab_rows) == len(reg)
    cache_label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({r['trial_id'] for r in records})
    if args.limit:
        tids = tids[:args.limit]
        records = [r for r in records if r['trial_id'] in set(tids)]
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)

    feats_by_key = {}
    n_fail = n_drift = 0
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  trials {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, 'typed'))
        except Exception:
            n_fail += 1
            continue
        if len(cards) < 2:
            n_fail += 1
            continue
        bands = dl.typed_aoi_bands(tid)
        tops = [b[0] for b in bands]
        bottoms = [b[1] for b in bands]
        per_pos, _, _ = visit_decomposition(dl, tid, cards)
        visits = walk_visits(dl, tid, tops)
        fixations = dl.load_fixations(tid)
        if not fixations:
            n_fail += 1
            continue
        ft = np.array([f['t'] for f in fixations], dtype=float)
        fx = np.array([f['x'] for f in fixations], dtype=float)
        fy = np.array([f['y'] for f in fixations], dtype=float)
        fd = np.array([f.get('d', 200) or 200 for f in fixations], dtype=float)
        a_top = np.asarray(tops, dtype=float)
        a_bot = np.asarray(bottoms, dtype=float)
        alpha = alpha_grid(fx, fy, x0, x1, a_top, a_bot, kernel=args.kernel, weight_placement=args.weight_placement,
                           e2_deg=args.e2_deg, px_per_deg=args.px_per_deg)
        inside = ((fx[:, None] >= x0) & (fx[:, None] <= x1)
                  & (fy[:, None] >= a_top[None, :]) & (fy[:, None] <= a_bot[None, :]))
        outside = ~inside
        centre = (a_top + a_bot) / 2.0
        dist = np.abs(fy[:, None] - centre[None, :])
        t_first, t_last = float(ft.min()), float(ft.max())

        for p, vs in visits.items():
            if p not in per_pos:
                continue
            fv_start, fv_end = vs[0]
            if abs(per_pos[p]['first_visit_end_ms'] - fv_end) > 1e-6:
                n_drift += 1
                continue
            ret_start = vs[1][0] if len(vs) > 1 else None
            # pre window
            pre_t0 = max(t_first, fv_start - WINDOW_MS)
            pai_pre, gd_pre, av_pre, nf_pre = window_stats(ft, fd, outside[:, p], alpha[:, p],
                                                   dist[:, p], pre_t0, fv_start)
            # post window (fixation START must precede the cap; the first
            # visit's last fixation starts at fv_end so exclude it: > fv_end)
            post_t0 = fv_end + 1e-3
            cap = min(fv_end + WINDOW_MS, t_last + 1.0)
            if ret_start is not None:
                cap = min(cap, ret_start)
            pai_post, gd_post, av_post, nf_post = window_stats(ft, fd, outside[:, p], alpha[:, p],
                                                      dist[:, p], post_t0, cap)
            cap_x = cap if ret_start is None else min(cap, ret_start - RETURN_BUFFER_MS)
            pai_post_x, _, _, _ = window_stats(ft, fd, outside[:, p], alpha[:, p],
                                            dist[:, p], post_t0, cap_x)
            feats_by_key[(tid, p)] = {
                'pai_pre': pai_pre, 'pai_post': pai_post, 'pai_post_x500': pai_post_x,
                'gaze_dist_pre': gd_pre, 'gaze_dist_post': gd_post,
                'avail_post_ms': av_post, 'avail_pre_ms': av_pre,
                'n_fix_post': nf_post, 'n_fix_pre': nf_pre,
                'return_gap_ms': (ret_start - fv_end) if ret_start is not None else np.nan,
            }

    for r in records:
        f = feats_by_key.get((r['trial_id'], r['position']))
        for k in PAI_FEATS + ('return_gap_ms',):
            r[k] = float(f[k]) if f is not None else np.nan

    pid = np.asarray([r['trial_id'].split('-')[0] for r in records])
    clicked = np.asarray([int(r['was_clicked']) for r in records])
    approached = np.asarray([r['min_dist'] < APPROACH_PX for r in records])
    labeled = np.asarray([(r['trial_id'], r['position']) in cache_label for r in records])
    y = np.asarray([int(cache_label.get((r['trial_id'], r['position']), False)) for r in records])
    pool = approached & (clicked == 0) & labeled
    has_feats = np.asarray([np.isfinite(r['pai_post']) for r in records])
    pool_post = pool & has_feats & np.asarray([np.isfinite(r['gaze_dist_post']) for r in records])
    pool_post_x = pool_post & np.asarray([np.isfinite(r['pai_post_x500']) for r in records])
    pool_pre = pool & np.asarray([np.isfinite(r['pai_pre']) and np.isfinite(r['gaze_dist_pre'])
                                  for r in records])
    if args.full_window_only:
        pool_post_x &= np.asarray([r['avail_post_ms'] >= WINDOW_MS - 1.0 for r in records])
        pool_pre &= np.asarray([r['avail_pre_ms'] >= WINDOW_MS - 1.0 for r in records])

    out = {'schema_version': 1,
           'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'kernel': kernel_label(args) + ', peripheral = outside typed band rect',
           'window_ms': WINDOW_MS, 'full_window_only': bool(args.full_window_only), 'min_avail_ms': MIN_AVAIL_MS, 'return_buffer_ms': RETURN_BUFFER_MS,
           'inputs': {'feature_cache': str(args.feature_cache.relative_to(ROOT)),
                      'feature_cache_sha256': sha256(args.feature_cache),
                      'label_cache_sha256': sha256(ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json'),
                      'carve_reference': str(args.carve.relative_to(ROOT)),
                      'buffer_ms': args.buffer, 'anchor_event': cache['anchor_event'], 'flavor': 'typed'},
           'population': {'records': len(records), 'trials': len(tids),
                          'trials_failed': n_fail, 'rows_visit_walk_drift': n_drift,
                          'label_complete_pool': int(pool.sum()),
                          'pool_post': int(pool_post.sum()), 'pool_post_x500': int(pool_post_x.sum()),
                          'pool_pre': int(pool_pre.sum()),
                          'deferred_in_pool': int(y[pool].sum())}}

    # --- GATE: reproduce the carve's M4-7 on the label-complete pool -------
    carve = json.loads(args.carve.read_text())
    target = carve['carve']['cache']['pool']['M4_7_cursor']['pooled_auc']
    pr, _ = loso_proba(records, APPROACH_7, y, pool)
    rep, _ = summarize(y, pr, pid, pool)
    delta = rep['pooled_auc'] - target
    out['gate'] = {'carve_M4_7_label_complete': target, 'reproduced': rep['pooled_auc'],
                   'delta': delta, 'n_records': rep['n_records']}
    print(f"GATE carve M4-7 = {target:.4f}  reproduced = {rep['pooled_auc']:.4f}  "
          f"delta = {delta:+.4f}  n={rep['n_records']:,}")
    if args.limit == 0 and abs(delta) > 5e-4:
        out['gate']['status'] = 'FAILED'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        json.dump(out, open(args.output.parent / 'summary.FAILED.json', 'w'), indent=1)
        raise SystemExit('Gate failed: cannot reproduce the carve number; nothing reported.')
    out['gate']['status'] = 'ok' if args.limit == 0 else 'skipped (--limit)'

    models = {
        'post': {
            'pai_post':                 ['pai_post'],
            'pai_post_x500':            ['pai_post_x500'],
            'gaze_dist_post':           ['gaze_dist_post'],
            'avail_post_ms':            ['avail_post_ms'],
            'n_fix_post':               ['n_fix_post'],
            'mean_dist':                ['mean_dist'],
            'M4_7_cursor':              APPROACH_7,
            'M4_7_plus_pai_post_x500':  APPROACH_7 + ['pai_post_x500'],
            'M4_7_plus_gaze_dist_post': APPROACH_7 + ['gaze_dist_post'],
            'M4_7_plus_n_fix_post':     APPROACH_7 + ['n_fix_post'],
            'M4_7_plus_pai_and_nfix':   APPROACH_7 + ['pai_post_x500', 'n_fix_post'],
            'M4_7_plus_pai_and_gazedist': APPROACH_7 + ['pai_post_x500', 'gaze_dist_post'],
            'mean_dist_plus_pai_post_x500': ['mean_dist', 'pai_post_x500'],
        },
        'pre': {
            'pai_pre':                  ['pai_pre'],
            'gaze_dist_pre':            ['gaze_dist_pre'],
            'avail_pre_ms':             ['avail_pre_ms'],
            'n_fix_pre':                ['n_fix_pre'],
            'M4_7_cursor':              APPROACH_7,
            'M4_7_plus_pai_pre':        APPROACH_7 + ['pai_pre'],
            'M4_7_plus_gaze_dist_pre':  APPROACH_7 + ['gaze_dist_pre'],
        },
    }
    masks = {'post': pool_post_x, 'pre': pool_pre}
    out['scores'] = {}
    folds_by = {}
    for block, mask in masks.items():
        blk = {}
        print(f"\n[{block}] n={int(mask.sum()):,}  deferred={int(y[mask].sum()):,}")
        for name, feats in models[block].items():
            p, _ = loso_proba(records, feats, y, mask)
            s, folds = summarize(y, p, pid, mask)
            folds_by[(block, name)] = folds
            blk[name] = s
            print(f"  {name:32s} pooled {s['pooled_auc']:.4f}  fold mean {s['fold_auc_mean']:.3f} ± {s['fold_auc_sd']:.3f}")
        blk['_null_M4_7'] = perm_null(records, APPROACH_7, y, mask, pid, n=args.perms)
        key_pai = 'pai_post_x500' if block == 'post' else 'pai_pre'
        blk[f'_null_{key_pai}'] = perm_null(records, [key_pai], y, mask, pid, n=args.perms)
        print(f"  null M4-7 mean {blk['_null_M4_7']['mean']:.3f} p95 {blk['_null_M4_7']['p95']:.3f}; "
              f"null {key_pai} mean {blk[f'_null_{key_pai}']['mean']:.3f} p95 {blk[f'_null_{key_pai}']['p95']:.3f}")
        out['scores'][block] = blk

    out['paired'] = {
        'post_M4_7_plus_pai_x500_vs_M4_7': paired(folds_by[('post', 'M4_7_plus_pai_post_x500')],
                                                 folds_by[('post', 'M4_7_cursor')]),
        'post_M4_7_plus_gazedist_vs_M4_7': paired(folds_by[('post', 'M4_7_plus_gaze_dist_post')],
                                                 folds_by[('post', 'M4_7_cursor')]),
        'post_M4_7_plus_both_vs_M4_7_plus_gazedist': paired(folds_by[('post', 'M4_7_plus_pai_and_gazedist')],
                                                           folds_by[('post', 'M4_7_plus_gaze_dist_post')]),
        'post_M4_7_plus_both_vs_M4_7_plus_nfix': paired(folds_by[('post', 'M4_7_plus_pai_and_nfix')],
                                                       folds_by[('post', 'M4_7_plus_n_fix_post')]),
        'post_pai_x500_vs_gaze_dist': paired(folds_by[('post', 'pai_post_x500')],
                                             folds_by[('post', 'gaze_dist_post')]),
        'pre_M4_7_plus_pai_vs_M4_7': paired(folds_by[('pre', 'M4_7_plus_pai_pre')],
                                            folds_by[('pre', 'M4_7_cursor')]),
    }
    for k, v in out['paired'].items():
        print(f"  paired {k}: {v['mean_delta']:+.4f} CI {v['bootstrap_ci95'][0]:+.4f}..{v['bootstrap_ci95'][1]:+.4f}")

    desc = {}
    for block, mask in masks.items():
        d, e = mask & (y == 1), mask & (y == 0)
        desc[block] = {}
        for f in PAI_FEATS + ('return_gap_ms',):
            v = np.asarray([r[f] for r in records], dtype=float)
            desc[block][f] = {'deferred_median': float(np.nanmedian(v[d])),
                              'rejected_median': float(np.nanmedian(v[e])),
                              'deferred_zero_frac': float(np.mean(v[d] == 0)) if f.startswith('pai') else None,
                              'rejected_zero_frac': float(np.mean(v[e] == 0)) if f.startswith('pai') else None}
    out['descriptives'] = desc
    print('\nmedians (deferred / rejected):')
    for f, m in desc['post'].items():
        print(f"  {f:16s} {m['deferred_median']:10.2f} / {m['rejected_median']:10.2f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)
    print(f'\nwrote {args.output}')


if __name__ == '__main__':
    main()
