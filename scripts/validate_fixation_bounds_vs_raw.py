#!/usr/bin/env python3
"""
Validate that fixations fall within the bounds of the authors' raw full-page
screenshots from Zenodo (AdSERP/data/full-page-screenshots/).

Ground-truth assumption: raw screenshots define the page coordinate system.
Each fixation's page-space (x, y) must satisfy 0 <= x <= raw_w and
0 <= y <= raw_h. Per the 2026-04-12 coordinate audit, FPOGY is already
page-space — no scroll arithmetic needed.

Runs against the 31 canonical trials that have matching raw screenshots in
AdSERP/data/full-page-screenshots/ (populated from full-page-screenshots.zip).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from PIL import Image  # type: ignore

from data_loader import load_trial

RAW_DIR = ROOT / 'AdSERP' / 'data' / 'full-page-screenshots'
OUTPUT_JSON = ROOT / 'scripts' / 'output' / 'fixation_bounds_status.json'


def raw_trials():
    return sorted(p.stem for p in RAW_DIR.glob('*.png'))


def check_trial(trial_id):
    raw_path = RAW_DIR / f'{trial_id}.png'
    with Image.open(raw_path) as im:
        raw_w, raw_h = im.size

    trial = load_trial(trial_id)
    if trial is None:
        return {'trial_id': trial_id, 'error': 'load_trial returned None'}

    fixations = trial['fixations']

    n = len(fixations)
    out_x = 0
    out_y = 0
    max_x_over = 0.0
    max_y_over = 0.0
    worst_fix_y = None

    for f in fixations:
        page_x = f['x']
        page_y = f['y']  # FPOGY is page-space (2026-04-12 audit)
        if page_x < 0 or page_x > raw_w:
            out_x += 1
            over = max(0 - page_x, page_x - raw_w)
            if over > max_x_over:
                max_x_over = over
        if page_y < 0 or page_y > raw_h:
            out_y += 1
            over = max(0 - page_y, page_y - raw_h)
            if over > max_y_over:
                max_y_over = over
                worst_fix_y = (f['t'], page_x, page_y)

    return {
        'trial_id': trial_id,
        'raw_w': raw_w,
        'raw_h': raw_h,
        'n': n,
        'out_x': out_x,
        'out_y': out_y,
        'max_x_over': max_x_over,
        'max_y_over': max_y_over,
        'worst_fix_y': worst_fix_y,
    }


def main():
    trials = raw_trials()
    print(f'Checking {len(trials)} canonical trials against raw screenshots...\n')

    results = []
    for tid in trials:
        try:
            r = check_trial(tid)
            results.append(r)
        except Exception as e:
            results.append({'trial_id': tid, 'error': str(e)})

    ok = [r for r in results if 'error' not in r]
    err = [r for r in results if 'error' in r]

    # Per-trial table
    print(
        f'{"trial":<16}{"raw_wxh":<14}{"n":>5}  '
        f'{"x_out":>6}{"y_out":>6}  {"max_y_over":>11}'
    )
    print('-' * 66)
    total_n = 0
    total_x_out = 0
    total_y_out = 0
    for r in ok:
        total_n += r['n']
        total_x_out += r['out_x']
        total_y_out += r['out_y']
        dim = f'{r["raw_w"]}x{r["raw_h"]}'
        mark = '  !' if (r['out_x'] or r['out_y']) else ''
        print(
            f'{r["trial_id"]:<16}{dim:<14}{r["n"]:>5}  '
            f'{r["out_x"]:>6}{r["out_y"]:>6}  '
            f'{r["max_y_over"]:>11.1f}{mark}'
        )

    print('-' * 66)
    print(f'\nTotals: {len(ok)} trials, {total_n} fixations')
    print(f'  out-of-bounds X: {total_x_out} ({100*total_x_out/max(total_n,1):.2f}%)')
    print(f'  out-of-bounds Y: {total_y_out} ({100*total_y_out/max(total_n,1):.2f}%)')

    if err:
        print(f'\nErrors ({len(err)}):')
        for r in err:
            print(f'  {r["trial_id"]}: {r["error"]}')

    # Emit JSON summary for downstream consumers (e.g. build-gh-pages.js)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    status = {
        'generated_by': 'scripts/validate_fixation_bounds_vs_raw.py',
        'total_trials': len(ok),
        'total_fixations': total_n,
        'total_out_x': total_x_out,
        'total_out_y': total_y_out,
        'trials': {},
    }
    for r in ok:
        pct_bad = (r['out_x'] + r['out_y']) / max(r['n'], 1) * 100
        if r['out_x'] == 0 and r['out_y'] == 0:
            cls = 'aligned'
        elif pct_bad > 20:
            cls = 'anomaly'
        else:
            cls = 'noisy'
        status['trials'][r['trial_id']] = {
            'class': cls,
            'raw_w': r['raw_w'],
            'raw_h': r['raw_h'],
            'n': r['n'],
            'out_x': r['out_x'],
            'out_y': r['out_y'],
            'pct_bad': round(pct_bad, 2),
            'max_y_over': round(r['max_y_over'], 1),
            'max_x_over': round(r['max_x_over'], 1),
        }
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(status, f, indent=2)
    print(f'\nWrote {OUTPUT_JSON.relative_to(ROOT)}')

    # Worst offenders
    worst = sorted(ok, key=lambda r: r['max_y_over'], reverse=True)[:5]
    if worst and worst[0]['max_y_over'] > 0:
        print('\nWorst y-over offenders:')
        for r in worst:
            if r['max_y_over'] == 0:
                break
            wf = r['worst_fix_y']
            if wf is None:
                continue
            t, fx, fy = wf
            print(
                f'  {r["trial_id"]}: FPOGY={fy:.0f} '
                f'vs raw_h={r["raw_h"]} (over by {r["max_y_over"]:.0f})'
            )

    # Exit status: 0 if bounds hold, 1 if any violation
    return 0 if total_x_out == 0 and total_y_out == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
