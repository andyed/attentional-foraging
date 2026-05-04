"""Knee position stratified by satisficer/optimizer (organic_hybrid only).

Hypothesis (Andy): optimizers compile criteria more than satisficers, so
their knee should be DEEPER (more pre-scroll fixations before the user
transitions to external-memory scanning).

Knee = deepest position fixated before first significant scroll, under
organic_hybrid attribution.

Stratification:
  - tercile field from per_participant_with_traits.csv ('low' / 'mid' / 'high'
    on regression rate)
  - also median split on regression_rate

Output: scripts/output/knee_by_satopt/{summary.json, report.md}

Run:
  .venv/bin/python scripts/knee_by_satopt.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
TRAITS = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
OUT = ROOT / 'scripts/output/knee_by_satopt'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_and_scroll, get_trial_meta,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

SCROLL_THRESHOLD_PX = 100


def first_scroll_t(scrolls):
    for t, y in scrolls:
        if y > SCROLL_THRESHOLD_PX:
            return t
    return None


def knee_for_trial(tid):
    meta = get_trial_meta(tid)
    if meta is None:
        return None
    tops = typed_aoi_tops(tid)
    if not tops:
        return None
    n = len(tops)
    fix = load_fixations(tid)
    if not fix:
        return None
    _, scrolls = load_mouse_and_scroll(tid)
    scroll_t = first_scroll_t(scrolls) if scrolls else None
    if scroll_t is None:
        return None  # no-scroll trials excluded from knee distribution

    deepest_pre = -1
    for f in fix:
        if f['t'] >= scroll_t:
            break
        pos = assign_fixation_to_position(f['y'], tops, n)
        if pos is not None and pos >= 0:
            if pos > deepest_pre:
                deepest_pre = pos
    return deepest_pre


def main():
    print('[knee-by-satopt] knee distribution by satopt classification',
          file=sys.stderr)

    # Load per-participant traits
    def _flt(v):
        try:
            return float(v) if v not in ('', None) else None
        except (TypeError, ValueError):
            return None

    traits = {}
    with open(TRAITS) as f:
        for row in csv.DictReader(f):
            traits[row['participant']] = {
                'regression_rate': _flt(row['regression_rate']),
                'tercile': row['tercile'],
                'mean_click_pos': _flt(row.get('mean_click_pos')),
                'median_tti_s': _flt(row.get('median_tti_s')),
            }
    # drop participants with missing regression_rate (the only required field)
    traits = {k: v for k, v in traits.items() if v['regression_rate'] is not None}
    print(f'  participants with traits: {len(traits):,}', file=sys.stderr)

    # Median split on regression rate
    rrs = [t['regression_rate'] for t in traits.values()]
    rr_median = float(np.median(rrs))
    for pid in traits:
        traits[pid]['median_split'] = (
            'optimizer' if traits[pid]['regression_rate'] >= rr_median else 'satisficer'
        )
    print(f'  regression rate median: {rr_median:.3f}', file=sys.stderr)

    # Compute knees
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    knee_rows = []
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pid = tid.split('-')[0]
        if pid not in traits:
            continue
        k = knee_for_trial(tid)
        if k is None:
            continue
        knee_rows.append({
            'tid': tid, 'pid': pid, 'knee': k,
            'tercile': traits[pid]['tercile'],
            'median_split': traits[pid]['median_split'],
            'regression_rate': traits[pid]['regression_rate'],
        })

    print(f'\n  trials with usable knee: {len(knee_rows):,}', file=sys.stderr)

    summary = {
        'attribution': 'typed',
        'n_trials': len(knee_rows),
        'regression_rate_median_split_at': rr_median,
    }

    # By median split
    print(f'\n  === By regression-rate median split ===', file=sys.stderr)
    by_split = defaultdict(list)
    for r in knee_rows:
        by_split[r['median_split']].append(r['knee'])

    summary['by_median_split'] = {}
    for split in ('satisficer', 'optimizer'):
        ks = by_split[split]
        if not ks:
            continue
        arr = np.array(ks)
        c = Counter(arr.tolist())
        d = {
            'n_trials': len(arr),
            'median': int(np.median(arr)),
            'mean': float(arr.mean()),
            'p25': int(np.percentile(arr, 25)),
            'p75': int(np.percentile(arr, 75)),
            'distribution_pct': {str(int(k)): float(100 * v / len(arr))
                                  for k, v in sorted(c.items())},
        }
        summary['by_median_split'][split] = d
        print(f'    {split}: N={len(arr):,}  median knee=P{int(np.median(arr))}  '
              f'p25/p75=P{int(np.percentile(arr, 25))}/P{int(np.percentile(arr, 75))}',
              file=sys.stderr)

    # MW between satisficer and optimizer
    if 'satisficer' in by_split and 'optimizer' in by_split:
        u, p = stats.mannwhitneyu(by_split['optimizer'], by_split['satisficer'],
                                   alternative='two-sided')
        u_g, p_g = stats.mannwhitneyu(by_split['optimizer'], by_split['satisficer'],
                                       alternative='greater')
        summary['median_split_test'] = {
            'mannwhitney_u': float(u),
            'p_two_sided': float(p),
            'p_one_sided_optimizer_greater': float(p_g),
        }
        print(f'  MW (optimizer vs satisficer): U={u:,.0f}, '
              f'two-sided p={p:.2e}, '
              f'one-sided (optimizer > satisficer) p={p_g:.2e}', file=sys.stderr)

    # By tercile
    print(f'\n  === By regression-rate tercile (low / mid / high) ===',
          file=sys.stderr)
    by_terc = defaultdict(list)
    for r in knee_rows:
        by_terc[r['tercile']].append(r['knee'])

    summary['by_tercile'] = {}
    for terc in ('low', 'mid', 'high'):
        ks = by_terc.get(terc, [])
        if not ks:
            continue
        arr = np.array(ks)
        c = Counter(arr.tolist())
        summary['by_tercile'][terc] = {
            'n_trials': len(arr),
            'median': int(np.median(arr)),
            'mean': float(arr.mean()),
            'p25': int(np.percentile(arr, 25)),
            'p75': int(np.percentile(arr, 75)),
            'distribution_pct': {str(int(k)): float(100 * v / len(arr))
                                  for k, v in sorted(c.items())},
        }
        print(f'    {terc}: N={len(arr):,}  median knee=P{int(np.median(arr))}  '
              f'p25/p75=P{int(np.percentile(arr, 25))}/P{int(np.percentile(arr, 75))}',
              file=sys.stderr)

    if all(t in by_terc for t in ('low', 'high')):
        u, p = stats.mannwhitneyu(by_terc['high'], by_terc['low'],
                                   alternative='two-sided')
        summary['tercile_test_high_vs_low'] = {
            'mannwhitney_u': float(u),
            'p_two_sided': float(p),
        }
        print(f'  MW (high vs low tercile): U={u:,.0f}, p={p:.2e}',
              file=sys.stderr)

    # Write outputs
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    lines = [
        '# Knee position by satopt — organic_hybrid\n',
        '_Generated 2026-05-03 by `scripts/knee_by_satopt.py`._\n',
        f'**N trials**: {len(knee_rows):,}  '
        f'(regression-rate median split at {rr_median:.3f})\n',
        '## By median split\n',
        '| Group | n | median knee | p25 / p50 / p75 | mean |',
        '|---|---|---|---|---|',
    ]
    for split in ('satisficer', 'optimizer'):
        s = summary['by_median_split'].get(split)
        if s:
            lines.append(f'| {split} | {s["n_trials"]:,} | P{s["median"]} | '
                         f'P{s["p25"]} / P{s["median"]} / P{s["p75"]} | {s["mean"]:.2f} |')

    if 'median_split_test' in summary:
        s = summary['median_split_test']
        lines.append(f'\n**Mann-Whitney (optimizer vs satisficer)**: '
                     f'two-sided *p* = {s["p_two_sided"]:.2e}, '
                     f'one-sided (optimizer > satisficer) *p* = '
                     f'{s["p_one_sided_optimizer_greater"]:.2e}')

    lines.append('\n## By tercile\n')
    lines.append('| Tercile | n | median knee | p25 / p75 | mean |')
    lines.append('|---|---|---|---|---|')
    for terc in ('low', 'mid', 'high'):
        s = summary['by_tercile'].get(terc)
        if s:
            lines.append(f'| {terc} | {s["n_trials"]:,} | P{s["median"]} | '
                         f'P{s["p25"]} / P{s["p75"]} | {s["mean"]:.2f} |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
