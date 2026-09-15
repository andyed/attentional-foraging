#!/usr/bin/env python3
"""Is the gaze return to a deferred result memory-guided or periphery-guided?

The 2026-09-14 deferred-class PAI probe found that results the eyes come
back to receive LESS peripheral mass after the eyes leave them, not more.
Under a foraging account that is expected: leaving a patch you will return
to is a wide move, and the return is executed from a remembered location,
not from ongoing peripheral monitoring. This producer tests that directly
on every deferred row of the typed map.

For each deferred (trial, position) with >= 2 gaze visits, two landing
events are compared within the row:

    entry   the first fixation of the first visit
    return  the first fixation of the second visit

and for each event:

    landing_offset_px    |fixation y - band centre|  (y only; x is reading
                         position, not target)
    saccade_amp_px       distance from the preceding fixation
    ranks_jumped         |position of preceding fixation - p| on the typed map
    pai_pre_rate         spec_eq2 peripheral mass rate on THIS band over the
                         1 s before the landing fixation (fixations strictly
                         before it; NaN if the trial starts inside the window)
    gaze_dist_pre_px     mean |fixation y - band centre| over the same window

Memory-guided returns predict: landing offset at return <= at entry, with a
pre-landing peripheral ramp no larger than at entry, and larger amplitude
(a ballistic long jump). Periphery-guided returns predict a larger ramp
before the return and precision that improves with the ramp.

Regime [LAB, AdSERP, typed]. Same substrate and fixation assignment as
deferred_dwell_carve.py; kernel spec_eq2; peripheral = outside the band.

Output: scripts/output/return_is_memory/summary.json
Run:    .venv/bin/python scripts/return_is_memory.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon, spearmanr

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))

from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from m4_cursor_aoi_rerun import load_flavor_cards, main_cards  # noqa: E402
from deferred_dwell_carve import visit_decomposition  # noqa: E402
from peripheral_kernel import alpha_grid, add_kernel_args, kernel_label  # noqa: E402

OUT_DIR = ROOT / 'scripts/output/return_is_memory'
WINDOW_MS = 1000.0
APPROACH_PX = 100.0


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def walk_visits_idx(dl, fixations, tops):
    """Visits per position as lists of fixation-index runs, by the label
    producer's rule (bisect on typed band tops; an unassigned fixation breaks
    the run). Also returns the per-fixation position array."""
    n_res = len(tops)
    pos = np.array([dl.assign_fixation_to_position(f['y'], tops, n_res) for f in fixations])
    visits = defaultdict(list)
    cur_pos, cur = None, None
    for i, p in enumerate(pos):
        if p < 0:
            if cur is not None:
                visits[cur_pos].append(cur)
                cur_pos, cur = None, None
            continue
        if p != cur_pos:
            if cur is not None:
                visits[cur_pos].append(cur)
            cur_pos, cur = int(p), [i, i]
        cur[1] = i
    if cur is not None:
        visits[cur_pos].append(cur)
    return visits, pos


def cluster_bootstrap_median(vals, pids, n=5000, seed=20260914):
    rng = np.random.default_rng(seed)
    vals, pids = np.asarray(vals, float), np.asarray(pids)
    ups = np.unique(pids)
    groups = [vals[pids == p] for p in ups]
    meds = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        meds.append(np.median(np.concatenate([groups[k] for k in pick])))
    return [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))]


def paired_block(name, a, b, pids):
    """return-minus-entry paired summary on rows where both are finite."""
    a, b, pids = np.asarray(a, float), np.asarray(b, float), np.asarray(pids)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b, pids = a[ok], b[ok], pids[ok]
    d = a - b
    per = defaultdict(list)
    for x, p in zip(d, pids):
        per[p].append(x)
    pmed = np.array([np.median(v) for v in per.values() if len(v) >= 5])
    try:
        w = wilcoxon(a, b)
        wp = float(w.pvalue)
    except ValueError:
        wp = None
    return {'n_rows': int(ok.sum()), 'n_participants': len(per),
            'return_median': float(np.median(a)), 'entry_median': float(np.median(b)),
            'diff_median': float(np.median(d)),
            'diff_median_ci95_cluster': cluster_bootstrap_median(d, pids),
            'wilcoxon_p': wp,
            'participants_with_median_diff_lt_0': int((pmed < 0).sum()),
            'participants_with_median_diff_gt_0': int((pmed > 0).sum()),
            'n_participants_ge5_rows': int(len(pmed))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feature-cache', type=Path,
                    default=ROOT / 'AdSERP/data/cursor-only-typed-features-mousedown.json')
    ap.add_argument('--summary-dir', default='m4_cursor_aoi_mousedown')
    ap.add_argument('--buffer', type=int, default=500)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--output', type=Path, default=OUT_DIR / 'summary.json')
    add_kernel_args(ap)
    args = ap.parse_args()

    import data_loader as dl

    cache = json.loads(args.feature_cache.read_text())
    stored = cache['conditions'][f'buf{args.buffer}']
    sidecar = json.loads((ROOT / 'scripts/output' / args.summary_dir / 'summary.json').read_text())
    if sidecar['provenance']['feature_records_sha256'][f'buf{args.buffer}'] != \
            hashlib.sha256(json.dumps(stored, sort_keys=True).encode()).hexdigest():
        raise ValueError('Feature cache does not match the aggregate sidecar it claims to accompany')
    rec = {(r['trial_id'], r['position']): r for r in stored}

    lab_rows = json.loads((ROOT / 'AdSERP/data/cursor-approach-features-typed.json').read_text())
    reg = json.loads((ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json').read_text())
    assert len(lab_rows) == len(reg)
    label = {(r['trial_id'], r['position']): bool(v) for r, v in zip(lab_rows, reg)}

    tids = sorted({k[0] for k in rec})
    if args.limit:
        tids = tids[:args.limit]
    x0, x1 = float(_RESULT_COL_X_MIN), float(_RESULT_COL_X_MAX)

    events = []
    n_def = n_def_lt2 = n_drift = 0
    for i, tid in enumerate(tids, 1):
        if i % 400 == 0:
            print(f'  trials {i}/{len(tids)}', flush=True)
        try:
            cards = main_cards(load_flavor_cards(dl, tid, 'typed'))
        except Exception:
            continue
        if len(cards) < 2:
            continue
        bands = dl.typed_aoi_bands(tid)
        tops_l = [b[0] for b in bands]
        tops = np.asarray(tops_l, float)
        bottoms = np.asarray([b[1] for b in bands], float)
        centre = (tops + bottoms) / 2.0
        fixations = dl.load_fixations(tid)
        if not fixations:
            continue
        per_pos, _, _ = visit_decomposition(dl, tid, cards)
        visits, pos = walk_visits_idx(dl, fixations, tops_l)
        ft = np.array([f['t'] for f in fixations], float)
        fx = np.array([f['x'] for f in fixations], float)
        fy = np.array([f['y'] for f in fixations], float)
        fd = np.array([f.get('d', 200) or 200 for f in fixations], float)
        alpha = alpha_grid(fx, fy, x0, x1, tops, bottoms, kernel=args.kernel, weight_placement=args.weight_placement,
                           e2_deg=args.e2_deg, px_per_deg=args.px_per_deg)
        inside = ((fx[:, None] >= x0) & (fx[:, None] <= x1)
                  & (fy[:, None] >= tops[None, :]) & (fy[:, None] <= bottoms[None, :]))
        outside = ~inside
        t_first = float(ft.min())

        for p, vs in visits.items():
            key = (tid, p)
            if key not in rec or not label.get(key, False) or rec[key]['was_clicked']:
                continue
            n_def += 1
            if len(vs) < 2:
                n_def_lt2 += 1
                continue
            if p in per_pos and abs(per_pos[p]['first_visit_end_ms'] - ft[vs[0][1]]) > 1e-6:
                n_drift += 1
                continue
            row = {'trial_id': tid, 'pid': tid.split('-')[0], 'position': p,
                   'etype': bands[p][2], 'approached': int(rec[key]['min_dist'] < APPROACH_PX),
                   'n_visits': len(vs),
                   'return_gap_ms': float(ft[vs[1][0]] - ft[vs[0][1]])}
            for tag, (i0, _i1) in (('entry', vs[0]), ('return', vs[1])):
                row[f'{tag}_landing_offset_px'] = float(abs(fy[i0] - centre[p]))
                if i0 > 0:
                    row[f'{tag}_saccade_amp_px'] = float(np.hypot(fx[i0] - fx[i0 - 1], fy[i0] - fy[i0 - 1]))
                    prev = int(pos[i0 - 1])
                    row[f'{tag}_ranks_jumped'] = (abs(prev - p) if prev >= 0 else np.nan)
                    row[f'{tag}_from_above'] = (int(prev < p) if prev >= 0 else np.nan)
                else:
                    row[f'{tag}_saccade_amp_px'] = np.nan
                    row[f'{tag}_ranks_jumped'] = np.nan
                    row[f'{tag}_from_above'] = np.nan
                t_land = ft[i0]
                w0 = t_land - WINDOW_MS
                if w0 < t_first:
                    row[f'{tag}_pai_pre_rate'] = np.nan
                    row[f'{tag}_gaze_dist_pre_px'] = np.nan
                    row[f'{tag}_n_fix_pre'] = np.nan
                else:
                    sel = (ft >= w0) & (ft < t_land)
                    m = float((fd[sel] * np.where(outside[sel, p], alpha[sel, p], 0.0)).sum())
                    row[f'{tag}_pai_pre_rate'] = m / (WINDOW_MS / 1000.0)
                    row[f'{tag}_gaze_dist_pre_px'] = (float(np.abs(fy[sel] - centre[p]).mean()) if sel.any() else np.nan)
                    row[f'{tag}_n_fix_pre'] = float(sel.sum())
            events.append(row)

    pids = [r['pid'] for r in events]
    measures = ('landing_offset_px', 'saccade_amp_px', 'ranks_jumped', 'pai_pre_rate',
                'gaze_dist_pre_px', 'n_fix_pre')
    paired = {m: paired_block(m, [r[f'return_{m}'] for r in events],
                              [r[f'entry_{m}'] for r in events], pids) for m in measures}

    # long returns only (>= 2 ranks jumped): the memory claim's strong case
    long_ = [r for r in events if np.isfinite(r['return_ranks_jumped']) and r['return_ranks_jumped'] >= 2]
    paired_long = {m: paired_block(m, [r[f'return_{m}'] for r in long_],
                                   [r[f'entry_{m}'] for r in long_], [r['pid'] for r in long_])
                   for m in ('landing_offset_px', 'saccade_amp_px', 'pai_pre_rate', 'gaze_dist_pre_px')}

    # does the pre-landing peripheral ramp buy precision? (within event type)
    def rho(tag):
        a = np.array([r[f'{tag}_pai_pre_rate'] for r in events], float)
        b = np.array([r[f'{tag}_landing_offset_px'] for r in events], float)
        ok = np.isfinite(a) & np.isfinite(b)
        s = spearmanr(a[ok], b[ok])
        return {'n': int(ok.sum()), 'spearman_rho': float(s.statistic), 'p': float(s.pvalue)}
    ramp_vs_precision = {'entry': rho('entry'), 'return': rho('return')}

    # return direction and distance descriptives
    rj = np.array([r['return_ranks_jumped'] for r in events], float)
    fa = np.array([r['return_from_above'] for r in events], float)
    ok = np.isfinite(rj)
    dist_hist = {int(k): int(v) for k, v in zip(*np.unique(rj[ok].astype(int), return_counts=True))}

    out = {
        'schema_version': 1,
        'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'regime': '[LAB, AdSERP, typed]', 'kernel': kernel_label(args) + ', peripheral = outside typed band rect',
        'window_ms': WINDOW_MS,
        'inputs': {'feature_cache': 'AdSERP/data/cursor-only-typed-features-mousedown.json',
                   'feature_cache_sha256': sha256(args.feature_cache),
                   'label_cache_sha256': sha256(ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json')},
        'population': {'deferred_rows_seen': n_def, 'deferred_with_lt2_visits': n_def_lt2,
                       'visit_walk_drift': n_drift, 'events': len(events),
                       'participants': len(set(pids)),
                       'approached_subset': int(sum(r['approached'] for r in events)),
                       'long_returns_ge2_ranks': len(long_)},
        'paired_return_minus_entry': paired,
        'paired_return_minus_entry_long_returns': paired_long,
        'ramp_vs_precision_spearman': ramp_vs_precision,
        'return_ranks_jumped_hist': dist_hist,
        'return_from_above_share': float(np.nanmean(fa)) if np.isfinite(fa).any() else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.output, 'w'), indent=1)

    print(f"\nevents {len(events):,} (deferred rows {n_def:,}; <2 visits {n_def_lt2:,}; drift {n_drift})")
    print('\nreturn vs entry (paired, return - entry):')
    for m, b in paired.items():
        print(f"  {m:18s} return {b['return_median']:8.1f}  entry {b['entry_median']:8.1f}  "
              f"diff {b['diff_median']:+8.1f} CI {b['diff_median_ci95_cluster'][0]:+.1f}..{b['diff_median_ci95_cluster'][1]:+.1f}  "
              f"p={b['wilcoxon_p']}  participants <0: {b['participants_with_median_diff_lt_0']}/{b['n_participants_ge5_rows']}")
    print('\nlong returns (>=2 ranks):')
    for m, b in paired_long.items():
        print(f"  {m:18s} return {b['return_median']:8.1f}  entry {b['entry_median']:8.1f}  diff {b['diff_median']:+8.1f} "
              f"CI {b['diff_median_ci95_cluster'][0]:+.1f}..{b['diff_median_ci95_cluster'][1]:+.1f}  p={b['wilcoxon_p']}")
    print(f"\nramp vs precision: {ramp_vs_precision}")
    print(f"ranks jumped hist: {dist_hist}   from above share: {out['return_from_above_share']}")
    print(f'\nwrote {args.output}')


if __name__ == '__main__':
    main()
