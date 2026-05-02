"""Scan candidate per-fixation/per-(trial,position) predictors of will-regress
to find replacements for the collapsed RIPA2 leg of R1.

Under bbox-organic attribution, the per-fixation RIPA2 amplitude differential
between will-regress and no-regress items goes from p=0.0058 to p=0.80
(rank-pooling artifact). The LF/HF leg survives at p=1.1e-03 but it's smaller
than the joint-signature claim.

This scan tests other per-fixation pupil-derived metrics for the same
will-regress vs no-regress contrast under bbox attribution. If anything
survives, the R1 paper has a per-fixation replacement story; if nothing
survives, the honest story is "lingered first time" via LF/HF only.

Predictors tested (per-(trial, organic position) aggregates):
  - mean_pd_mean      : average per-fixation mean pupil diameter
  - mean_pd_max       : peak per-fixation mean pupil diameter
  - pd_change_mean    : average per-fixation pupil change (dilation/constriction)
  - pd_change_max     : peak per-fixation pupil change (positive = max dilation)
  - pd_change_min     : trough per-fixation pupil change (most negative = max constriction)
  - n_fixations       : number of fixations on the position (forward-pass)
  - mean_fix_duration : mean per-fixation duration (ms)
  - max_fix_duration  : longest fixation
  - sum_fix_duration  : total dwell on the position
  - first_pd, last_pd : pupil at start vs end of position visit
  - pd_trajectory     : last_pd - first_pd (pupil drift across the visit)
  - lfhf_existing     : per-(trial, pos) LF/HF (sanity baseline; already survives)
  - ripa2_existing    : per-(trial, pos) RIPA2 (sanity baseline; collapses)

Run:
  .venv/bin/python scripts/will_return_predictor_scan.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    DATA_DIR,
    load_fixations,
    organic_aoi_tops,
    assign_fixation_to_position,
)

FIX_PUPIL_DIR = DATA_DIR / 'fixation-pupil'
EVR_PATH = DATA_DIR / 'encoding-vs-retrieval.json'
LFHF_PATH = DATA_DIR / 'butterworth-lfhf-by-position-organic.json'
RIPA2_PATH = DATA_DIR / 'ripa2-by-position-organic.json'


def cohens_d(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return float('nan')
    pooled = np.sqrt(((a.std(ddof=1) ** 2) + (b.std(ddof=1) ** 2)) / 2)
    return (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0


def mw_test(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 10 or len(b) < 10:
        return float('nan'), float('nan'), float('nan'), int(len(a)), int(len(b))
    u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    return float(np.median(a)), float(np.median(b)), float(p), int(len(a)), int(len(b))


def main():
    print('[load] EVR + LF/HF + RIPA2')
    evr = json.load(open(EVR_PATH))
    lfhf_data = json.load(open(LFHF_PATH))
    ripa2_data = json.load(open(RIPA2_PATH))

    print('[walk] aggregating per-fixation pupil to per-(trial, organic position)...')

    # Per-(tid, pos) record: dict of metric -> aggregate
    records = []
    n_trials_with_pupil = 0
    n_skipped = 0

    for tid, et in evr.items():
        # Need fixation list, fixation-pupil, organic AOIs, and EVR labels
        fix_pupil_path = FIX_PUPIL_DIR / f'{tid}.json'
        if not fix_pupil_path.exists():
            n_skipped += 1
            continue
        fix_pupil = json.load(open(fix_pupil_path))
        fixations = load_fixations(tid)
        if not fixations or len(fix_pupil) != len(fixations):
            n_skipped += 1
            continue

        tops = organic_aoi_tops(tid)
        n_results = len(tops)
        if n_results == 0:
            n_skipped += 1
            continue

        wr_by_pos = {fp['pos']: fp.get('will_regress', False)
                     for fp in et.get('first_pass', [])}
        if not wr_by_pos:
            continue

        # Group fixations by hybrid (organic) position; only forward-pass
        by_pos = defaultdict(list)  # pos -> [(fix, pupil) tuples]
        high_water = -1
        for f, p in zip(fixations, fix_pupil):
            pos = assign_fixation_to_position(f['y'], tops, n_results)
            if pos is None or pos < 0 or pos >= n_results:
                continue
            if pos >= high_water:
                high_water = pos
                by_pos[int(pos)].append((f, p))

        if not by_pos:
            continue

        # Aggregate per (trial, pos)
        n_trials_with_pupil += 1
        lfhf_t = {pp['pos']: pp['lfhf'] for pp in lfhf_data.get(tid, {}).get('positions', [])
                  if pp.get('lfhf') is not None}
        ripa2_t = {pp['pos']: pp['ripa2'] for pp in ripa2_data.get(tid, {}).get('positions', [])
                   if pp.get('ripa2') is not None}

        for pos, fp_list in by_pos.items():
            if pos not in wr_by_pos:
                continue
            mean_pds = [p['mean_pd'] for _, p in fp_list if p.get('mean_pd') is not None]
            pd_changes = [p['pd_change'] for _, p in fp_list if p.get('pd_change') is not None]
            durations = [f['d'] for f, _ in fp_list]
            n_fix = len(fp_list)
            if n_fix < 2 or len(mean_pds) < 2:
                continue
            rec = {
                'tid': tid, 'pos': pos,
                'wr': bool(wr_by_pos[pos]),
                'n_fix': n_fix,
                'mean_pd_mean': float(np.mean(mean_pds)),
                'mean_pd_max': float(np.max(mean_pds)),
                'pd_change_mean': float(np.mean(pd_changes)) if pd_changes else float('nan'),
                'pd_change_max': float(np.max(pd_changes)) if pd_changes else float('nan'),
                'pd_change_min': float(np.min(pd_changes)) if pd_changes else float('nan'),
                'mean_fix_duration': float(np.mean(durations)),
                'max_fix_duration': float(np.max(durations)),
                'sum_fix_duration': float(np.sum(durations)),
                'first_pd': float(mean_pds[0]),
                'last_pd': float(mean_pds[-1]),
                'pd_trajectory': float(mean_pds[-1] - mean_pds[0]),
                'lfhf_existing': lfhf_t.get(pos, float('nan')),
                'ripa2_existing': ripa2_t.get(pos, float('nan')),
            }
            records.append(rec)

    print(f'  trials with usable pupil: {n_trials_with_pupil:,}  (skipped: {n_skipped})')
    print(f'  per-(trial, position) records: {len(records):,}')

    wr_records = [r for r in records if r['wr']]
    nr_records = [r for r in records if not r['wr']]
    print(f'  will-regress: {len(wr_records):,}  no-regress: {len(nr_records):,}')

    metrics = [
        'mean_pd_mean', 'mean_pd_max',
        'pd_change_mean', 'pd_change_max', 'pd_change_min',
        'n_fix',
        'mean_fix_duration', 'max_fix_duration', 'sum_fix_duration',
        'first_pd', 'last_pd', 'pd_trajectory',
        'lfhf_existing', 'ripa2_existing',
    ]

    print(f'\n{"metric":22s} {"d":>7s} {"med wr":>10s} {"med nr":>10s} {"p":>10s}  {"n_wr":>5s}/{"n_nr":>5s}')
    print('-' * 80)

    summary = []
    for m in metrics:
        wr_vals = [r[m] for r in wr_records]
        nr_vals = [r[m] for r in nr_records]
        d = cohens_d(wr_vals, nr_vals)
        med_wr, med_nr, p, n_wr, n_nr = mw_test(wr_vals, nr_vals)
        marker = ' ***' if p < 0.001 else ('  **' if p < 0.01 else ('   *' if p < 0.05 else '    '))
        print(f'{m:22s} {d:+7.3f} {med_wr:>10.4g} {med_nr:>10.4g} {p:>10.3e}  '
              f'{n_wr:>5,}/{n_nr:>5,}{marker}')
        summary.append({
            'metric': m, 'd': float(d) if np.isfinite(d) else None,
            'median_wr': med_wr, 'median_nr': med_nr,
            'p': p, 'n_wr': n_wr, 'n_nr': n_nr,
        })

    out_dir = ROOT / 'scripts/output/aoi-consumer-cascade'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'will_return_predictor_scan.json'
    out_path.write_text(json.dumps({
        'n_records': len(records),
        'n_wr': len(wr_records),
        'n_nr': len(nr_records),
        'metrics': summary,
    }, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
