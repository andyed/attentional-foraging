"""Viewport-fold check (organic_hybrid only).

Tests whether the LF/HF steep/plateau transition at P3->P4 corresponds to the
first-viewport fold on the desktop SERP layout. For each trial:
  1. Get hybrid AOI top-y per position.
  2. Compute viewport bottom at trial start = screen_height (scroll=0).
  3. Identify the largest position p whose top_y < viewport bottom (last
     above-fold position on first viewport).

Aggregates:
  - distribution of per-trial last-above-fold positions
  - per-position fraction of trials above the fold
  - alignment of fold with the cognitive knee (P3->P4)

Output: scripts/output/lfhf_viewport_fold_check/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_viewport_fold_check.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_viewport_fold_check'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import get_trial_meta  # noqa: E402
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402


def main():
    print('[fold] Viewport fold under organic_hybrid', file=sys.stderr)
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,}', file=sys.stderr)

    last_above_fold = []           # per-trial last position whose top < fold
    p4_top_minus_fold = []         # per-trial: P4_top_y - viewport_bottom
    per_pos_above_fold = {p: {'above': 0, 'below': 0} for p in range(15)}
    skipped = 0
    viewport_heights = []

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        meta = get_trial_meta(tid)
        if meta is None:
            skipped += 1; continue
        doc_h, screen_h, _ = meta
        if not screen_h:
            skipped += 1; continue
        tops = _hybrid_aoi_tops(tid)
        if not tops:
            skipped += 1; continue
        viewport_heights.append(int(screen_h))

        fold = float(screen_h)
        last_above = -1
        for p, top in enumerate(tops):
            if p < 15:
                if top < fold:
                    per_pos_above_fold[p]['above'] += 1
                    last_above = p
                else:
                    per_pos_above_fold[p]['below'] += 1
        if last_above >= 0:
            last_above_fold.append(last_above)

        if len(tops) > 4:
            p4_top_minus_fold.append(tops[4] - fold)

    last_arr = np.array(last_above_fold)
    p4_arr = np.array(p4_top_minus_fold) if p4_top_minus_fold else np.array([])

    print(f'\n  trials with usable geometry: {len(last_arr):,} '
          f'(skipped: {skipped:,})', file=sys.stderr)
    print(f'  viewport height (px): mean={np.mean(viewport_heights):.0f}, '
          f'p25={np.percentile(viewport_heights, 25):.0f}, '
          f'p50={np.percentile(viewport_heights, 50):.0f}, '
          f'p75={np.percentile(viewport_heights, 75):.0f}',
          file=sys.stderr)

    # Distribution of "last above fold"
    print(f'\n  Distribution of per-trial last-above-fold position:', file=sys.stderr)
    last_dist = Counter(last_arr.tolist())
    for pos in sorted(last_dist.keys()):
        pct = 100 * last_dist[pos] / len(last_arr)
        print(f'    P{pos}: {last_dist[pos]:,} ({pct:.1f}%)', file=sys.stderr)
    print(f'  median last-above-fold: P{int(np.median(last_arr))}', file=sys.stderr)
    print(f'  P25 / P50 / P75: P{int(np.percentile(last_arr, 25))} / '
          f'P{int(np.percentile(last_arr, 50))} / '
          f'P{int(np.percentile(last_arr, 75))}', file=sys.stderr)

    # Per-position above-fold fractions
    print(f'\n  Per-position fraction of trials above fold:', file=sys.stderr)
    for p in range(11):
        n_above = per_pos_above_fold[p]['above']
        n_below = per_pos_above_fold[p]['below']
        n_total = n_above + n_below
        if n_total > 0:
            pct = 100 * n_above / n_total
            print(f'    P{p}: {n_above:,}/{n_total:,} = {pct:.1f}%',
                  file=sys.stderr)

    if len(p4_arr):
        p4_below_count = int((p4_arr > 0).sum())
        p4_above_count = int((p4_arr <= 0).sum())
        print(f'\n  P4 specifically:', file=sys.stderr)
        print(f'    P4 top above viewport bottom (above fold): {p4_above_count:,}',
              file=sys.stderr)
        print(f'    P4 top below viewport bottom (below fold): {p4_below_count:,}',
              file=sys.stderr)
        print(f'    P4 top y - viewport bottom: median={np.median(p4_arr):+.0f} px, '
              f'mean={np.mean(p4_arr):+.0f}', file=sys.stderr)

    # Output
    summary = {
        'attribution': 'organic_hybrid',
        'n_trials_usable': int(len(last_arr)),
        'n_skipped': skipped,
        'viewport_height_px': {
            'mean': float(np.mean(viewport_heights)),
            'p25': float(np.percentile(viewport_heights, 25)),
            'p50': float(np.percentile(viewport_heights, 50)),
            'p75': float(np.percentile(viewport_heights, 75)),
        },
        'last_above_fold_distribution': {str(k): int(v) for k, v in last_dist.items()},
        'last_above_fold_percentiles': {
            'p25': int(np.percentile(last_arr, 25)),
            'p50': int(np.percentile(last_arr, 50)),
            'p75': int(np.percentile(last_arr, 75)),
        },
        'per_position_above_fold_pct': {
            str(p): {
                'n_above': per_pos_above_fold[p]['above'],
                'n_total': per_pos_above_fold[p]['above'] + per_pos_above_fold[p]['below'],
                'pct_above_fold': 100 * per_pos_above_fold[p]['above'] /
                    max(1, per_pos_above_fold[p]['above'] + per_pos_above_fold[p]['below']),
            }
            for p in range(11)
        },
        'p4_geometry': {
            'n_trials_with_p4': int(len(p4_arr)),
            'p4_top_minus_fold_median_px': float(np.median(p4_arr)) if len(p4_arr) else None,
            'p4_top_minus_fold_mean_px': float(np.mean(p4_arr)) if len(p4_arr) else None,
            'p4_above_fold_count': int((p4_arr <= 0).sum()) if len(p4_arr) else 0,
            'p4_below_fold_count': int((p4_arr > 0).sum()) if len(p4_arr) else 0,
        },
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Report
    lines = [
        '# Viewport-fold check — organic_hybrid\n',
        '_Generated 2026-05-03 by `scripts/lfhf_viewport_fold_check.py`._\n',
        '## Question\n',
        'Does the LF/HF steep/plateau transition at P3->P4 correspond to the',
        'first-viewport fold (above-fold = simultaneously visible at trial-start;',
        'below-fold = requires scroll)?\n',
        '## Headline\n',
        f'**Median per-trial last-above-fold position: P{int(np.percentile(last_arr, 50))}** '
        f'(P25 = P{int(np.percentile(last_arr, 25))}, P75 = P{int(np.percentile(last_arr, 75))})\n',
        f'Across {len(last_arr):,} trials with usable viewport geometry, '
        f'the typical first viewport contained P0 through '
        f'P{int(np.percentile(last_arr, 50))}.\n',
        '## Per-position fraction of trials above fold\n',
        '| Pos | n above-fold | n total | % above-fold |',
        '|---|---|---|---|',
    ]
    for p in range(11):
        n_above = per_pos_above_fold[p]['above']
        n_total = n_above + per_pos_above_fold[p]['below']
        if n_total > 0:
            pct = 100 * n_above / n_total
            lines.append(f'| P{p} | {n_above:,} | {n_total:,} | {pct:.1f}% |')

    if len(p4_arr):
        lines.extend([
            '\n## P4 specifically\n',
            f'- P4 top above viewport bottom (above fold): **{int((p4_arr <= 0).sum()):,}** trials',
            f'- P4 top below viewport bottom (below fold): **{int((p4_arr > 0).sum()):,}** trials',
            f'- median (P4_top_y − viewport_bottom) = **{np.median(p4_arr):+.0f} px**',
        ])

    lines.extend([
        '\n## Viewport heights\n',
        f'- mean: {np.mean(viewport_heights):.0f} px',
        f'- p25 / p50 / p75: {np.percentile(viewport_heights, 25):.0f} / '
        f'{np.percentile(viewport_heights, 50):.0f} / '
        f'{np.percentile(viewport_heights, 75):.0f} px',
    ])

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)
    print(f'wrote {(OUT / "report.md").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
