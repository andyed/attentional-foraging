"""First-scroll-vs-gaze analysis (organic_hybrid).

Question: when the user issues their first significant downward scroll, how
much of the above-fold consideration set has been fixated? Is scroll
preemptive (before exhausting the visible set) or post-evaluation (after
fixating most/all of the visible set)?

Stratified by whether P0 (display-order top) is a top-of-page ad (`dd_top`)
or an organic — Andy's hypothesis: top-ads invite preemptive scrolls because
the user can identify them as ads from peripheral vision and skip past.

Output: scripts/output/first_scroll_vs_gaze/{summary.json, report.md}

Run:
  .venv/bin/python scripts/first_scroll_vs_gaze.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/first_scroll_vs_gaze'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_and_scroll, get_trial_meta,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

SCROLL_THRESHOLD_PX = 100   # first scroll = first event past this y value


def find_first_scroll_t(scrolls, threshold=SCROLL_THRESHOLD_PX):
    """Return timestamp of first scroll event past threshold, or None."""
    for t, y in scrolls:
        if y > threshold:
            return t
    return None


def main():
    print('[scroll-gaze] First scroll vs gaze coverage', file=sys.stderr)

    # Load hybrid features for etype lookup at P0
    feats = json.load(open(DATA / 'cursor-approach-features-typed.json'))
    etype_at_pos0 = {}
    for r in feats:
        if r['position'] == 0:
            etype_at_pos0[r['trial_id']] = r.get('etype')

    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,}', file=sys.stderr)

    rows = []
    n_no_scroll = 0
    n_no_geom = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        meta = get_trial_meta(tid)
        if meta is None or not meta[1]:
            n_no_geom += 1; continue
        doc_h, screen_h, _ = meta
        tops = typed_aoi_tops(tid)
        if not tops:
            n_no_geom += 1; continue
        fix = load_fixations(tid)
        if not fix:
            n_no_geom += 1; continue
        _, scrolls = load_mouse_and_scroll(tid)
        if not scrolls:
            n_no_scroll += 1
            # Treat as a "committed without scrolling" trial — different cohort.
            rows.append({
                'tid': tid, 'pid': tid.split('-')[0],
                'first_scroll_t': None,
                'visible_at_start': [p for p, t in enumerate(tops) if t < screen_h],
                'fixated_above_fold': [],
                'p0_etype': etype_at_pos0.get(tid),
                'no_scroll': True,
            })
            continue

        first_scroll_t = find_first_scroll_t(scrolls)
        if first_scroll_t is None:
            n_no_scroll += 1
            rows.append({
                'tid': tid, 'pid': tid.split('-')[0],
                'first_scroll_t': None,
                'visible_at_start': [p for p, t in enumerate(tops) if t < screen_h],
                'fixated_above_fold': [],
                'p0_etype': etype_at_pos0.get(tid),
                'no_scroll': True,
            })
            continue

        # Above-fold positions at trial start
        visible = [p for p, top in enumerate(tops) if top < screen_h]
        if not visible:
            continue

        # Fixations BEFORE first scroll
        fixated_above_fold = set()
        for f in fix:
            if f['t'] >= first_scroll_t:
                break
            pos = assign_fixation_to_position(f['y'], tops, len(tops))
            if pos is not None and pos in visible:
                fixated_above_fold.add(pos)

        # Deepest position fixated before scrolling
        deepest_fixated = max(fixated_above_fold) if fixated_above_fold else -1
        last_visible = max(visible)
        coverage = len(fixated_above_fold) / len(visible)

        rows.append({
            'tid': tid, 'pid': tid.split('-')[0],
            'first_scroll_t': float(first_scroll_t),
            'visible_at_start': visible,
            'fixated_above_fold': sorted(fixated_above_fold),
            'n_visible': len(visible),
            'n_fixated': len(fixated_above_fold),
            'coverage': coverage,
            'deepest_fixated': deepest_fixated,
            'last_visible': last_visible,
            'reached_last_visible': deepest_fixated >= last_visible,
            'p0_etype': etype_at_pos0.get(tid),
            'no_scroll': False,
        })

    print(f'\n  trials usable: {len(rows):,}', file=sys.stderr)
    print(f'  no scroll: {n_no_scroll:,}', file=sys.stderr)
    print(f'  no geometry: {n_no_geom:,}', file=sys.stderr)

    scrolling = [r for r in rows if not r['no_scroll']]
    no_scroll = [r for r in rows if r['no_scroll']]
    print(f'  trials with first scroll: {len(scrolling):,}', file=sys.stderr)
    print(f'  trials that committed without scrolling: {len(no_scroll):,}',
          file=sys.stderr)

    # ── Summary on scrolling-trials cohort ──
    coverages = np.array([r['coverage'] for r in scrolling])
    reached_last = np.mean([r['reached_last_visible'] for r in scrolling])
    deepest = [r['deepest_fixated'] for r in scrolling]
    last_vis = [r['last_visible'] for r in scrolling]

    print(f'\n  Coverage of visible set before first scroll:', file=sys.stderr)
    print(f'    mean coverage: {coverages.mean():.3f}', file=sys.stderr)
    print(f'    median coverage: {np.median(coverages):.3f}', file=sys.stderr)
    print(f'    p25/p50/p75: {np.percentile(coverages, 25):.2f} / '
          f'{np.percentile(coverages, 50):.2f} / '
          f'{np.percentile(coverages, 75):.2f}', file=sys.stderr)
    print(f'  fraction of trials that reached last visible: {reached_last:.3f}',
          file=sys.stderr)
    print(f'  deepest fixated p25/p50/p75: '
          f'{np.percentile(deepest, 25):.0f} / {np.percentile(deepest, 50):.0f} / '
          f'{np.percentile(deepest, 75):.0f}', file=sys.stderr)
    print(f'  last visible p25/p50/p75: '
          f'{np.percentile(last_vis, 25):.0f} / {np.percentile(last_vis, 50):.0f} / '
          f'{np.percentile(last_vis, 75):.0f}', file=sys.stderr)

    # ── Stratify by P0 etype ──
    print(f'\n  Stratified by P0 etype (top-of-display):', file=sys.stderr)
    by_etype = defaultdict(list)
    for r in scrolling:
        by_etype[r['p0_etype'] or 'unknown'].append(r)
    for et, rs in sorted(by_etype.items()):
        if not rs:
            continue
        c = np.array([r['coverage'] for r in rs])
        rl = np.mean([r['reached_last_visible'] for r in rs])
        d = np.array([r['deepest_fixated'] for r in rs])
        n0_fixated = np.mean([0 in r['fixated_above_fold'] for r in rs])
        print(f'    {et}: n={len(rs):,}  coverage median={np.median(c):.3f}  '
              f'reached_last={rl:.3f}  deepest median={np.median(d):.0f}  '
              f'P0-fixated={n0_fixated:.3f}', file=sys.stderr)

    # ── Distribution of deepest_fixated_before_first_scroll ──
    print(f'\n  Distribution of deepest position fixated before first scroll:',
          file=sys.stderr)
    deep_dist = Counter(deepest)
    for pos in sorted(deep_dist.keys()):
        if pos < 0:
            label = 'none'
        else:
            label = f'P{pos}'
        pct = 100 * deep_dist[pos] / len(scrolling)
        print(f'    {label}: {deep_dist[pos]:,} ({pct:.1f}%)', file=sys.stderr)

    # Per-position fraction of trials where this position was fixated before scroll
    print(f'\n  Per-visible-position: fraction of trials where it was '
          f'fixated before scroll', file=sys.stderr)
    for p in range(7):
        had_p_visible = [r for r in scrolling if p in r['visible_at_start']]
        if not had_p_visible:
            continue
        frac = np.mean([p in r['fixated_above_fold'] for r in had_p_visible])
        print(f'    P{p}: {frac:.3f} ({len(had_p_visible):,} trials had P{p} above fold)',
              file=sys.stderr)

    # ── Output ──
    summary = {
        'attribution': 'typed',
        'n_trials_total': len(rows),
        'n_scrolling': len(scrolling),
        'n_no_scroll': len(no_scroll),
        'scroll_threshold_px': SCROLL_THRESHOLD_PX,
        'coverage_before_first_scroll': {
            'mean': float(coverages.mean()),
            'median': float(np.median(coverages)),
            'p25': float(np.percentile(coverages, 25)),
            'p50': float(np.percentile(coverages, 50)),
            'p75': float(np.percentile(coverages, 75)),
        },
        'fraction_reached_last_visible': float(reached_last),
        'deepest_fixated_distribution': {str(k): int(v) for k, v in deep_dist.items()},
        'per_position_fixated_before_scroll': {
            str(p): {
                'n_trials_with_p_visible': int(sum(1 for r in scrolling if p in r['visible_at_start'])),
                'fraction_fixated': float(np.mean([
                    p in r['fixated_above_fold']
                    for r in scrolling if p in r['visible_at_start']
                ])) if any(p in r['visible_at_start'] for r in scrolling) else 0.0,
            }
            for p in range(7)
        },
        'by_p0_etype': {},
    }
    for et, rs in by_etype.items():
        c = np.array([r['coverage'] for r in rs])
        d = np.array([r['deepest_fixated'] for r in rs])
        summary['by_p0_etype'][et] = {
            'n_trials': len(rs),
            'coverage_median': float(np.median(c)),
            'coverage_mean': float(np.mean(c)),
            'fraction_reached_last_visible': float(np.mean([r['reached_last_visible'] for r in rs])),
            'deepest_median': float(np.median(d)),
            'p0_fixated_fraction': float(np.mean([0 in r['fixated_above_fold'] for r in rs])),
        }

    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Markdown report
    lines = [
        '# First scroll vs gaze coverage — organic_hybrid\n',
        '_Generated 2026-05-03 by `scripts/first_scroll_vs_gaze.py`._\n',
        '## Question\n',
        'When the user issues their first significant downward scroll, how much',
        'of the above-fold consideration set have they fixated? Pre-emptive vs',
        'post-evaluation scrolling.\n',
        '## Cohort\n',
        f'- {len(rows):,} trials with usable geometry',
        f'- **{len(scrolling):,} trials** had a first significant scroll '
        f'(scroll_y > {SCROLL_THRESHOLD_PX} px)',
        f'- **{len(no_scroll):,} trials** committed without scrolling',
        '',
        '## Coverage of above-fold set before first scroll\n',
        f'| stat | value |',
        f'|---|---|',
        f'| mean coverage | {coverages.mean():.3f} |',
        f'| median coverage | {np.median(coverages):.3f} |',
        f'| p25 / p50 / p75 | {np.percentile(coverages, 25):.2f} / '
        f'{np.percentile(coverages, 50):.2f} / {np.percentile(coverages, 75):.2f} |',
        f'| fraction reaching last-visible position | {reached_last:.3f} |',
        '',
        '## Per-position: fraction of trials where this above-fold position '
        'was fixated before first scroll\n',
        '| Pos | trials w/ P above fold | fraction fixated before scroll |',
        '|---|---|---|',
    ]
    for p in range(7):
        had = [r for r in scrolling if p in r['visible_at_start']]
        if not had:
            continue
        frac = np.mean([p in r['fixated_above_fold'] for r in had])
        lines.append(f'| P{p} | {len(had):,} | {frac:.3f} |')

    lines.extend([
        '\n## Stratified by P0 etype (top of display order)\n',
        "Hypothesis: a top-of-page ad (`dd_top`) at P0 invites pre-emptive scroll.",
        "",
        "| P0 etype | n trials | median coverage | reached last visible | deepest median | P0 fixated |",
        "|---|---|---|---|---|---|",
    ])
    for et, rs in sorted(by_etype.items()):
        if not rs:
            continue
        c = np.array([r['coverage'] for r in rs])
        rl = np.mean([r['reached_last_visible'] for r in rs])
        d = np.array([r['deepest_fixated'] for r in rs])
        n0 = np.mean([0 in r['fixated_above_fold'] for r in rs])
        lines.append(f'| {et} | {len(rs):,} | {np.median(c):.3f} | {rl:.3f} | '
                     f'{np.median(d):.0f} | {n0:.3f} |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)
    print(f'wrote {(OUT / "report.md").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
