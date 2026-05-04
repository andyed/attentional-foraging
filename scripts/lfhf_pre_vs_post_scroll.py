"""LF/HF on first visit, split by pre- vs post-first-scroll (organic_hybrid).

Tests Andy's intuition: the steep-phase LF/HF lives in the pre-first-scroll
fixations, when the user is engaged in active comparison among the initial
above-fold set. The plateau lives in post-first-scroll fixations, when the
mode shifts to sampling.

For each (trial, position) first visit:
  1. Compute LF/HF on the first-visit fixation samples (as before).
  2. Tag the segment as 'pre-scroll' if all first-visit fixations preceded
     the first significant scroll event; otherwise 'post-scroll'.
  3. Aggregate per-position medians, separately for pre vs post.

Output: scripts/output/lfhf_pre_vs_post_scroll/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_pre_vs_post_scroll.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.signal import butter, sosfiltfilt

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_pre_vs_post_scroll'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    load_mouse_and_scroll, assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

FS = 150
LF_SOS = butter(4, 1.6, btype='low', fs=FS, output='sos')
HF_SOS = butter(4, (1.6, 4.0), btype='band', fs=FS, output='sos')
MIN_SAMPLES = 150
SCROLL_THRESHOLD_PX = 100


def first_scroll_t(scrolls):
    for t, y in scrolls:
        if y > SCROLL_THRESHOLD_PX:
            return t
    return None


def visit_segments_first_only_with_split(fix, tops, n_res, scroll_t):
    """Return {pos: {'pre': [windows], 'post': [windows]}}."""
    segs = {}
    max_seen = -1
    for f in fix:
        pos = assign_fixation_to_position(f['y'], tops, n_res)
        if pos is None or pos < 0:
            continue
        if pos >= max_seen:
            phase = 'pre' if (scroll_t is None or f['t'] < scroll_t) else 'post'
            d = segs.setdefault(pos, {'pre': [], 'post': []})
            d[phase].append((f['t'], f['t'] + f['d']))
            if pos > max_seen:
                max_seen = pos
    return segs


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    if not windows:
        return None
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    return float(lf_p / hf_p) if hf_p >= 1e-20 else None


def process_trial(tid):
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return []
    ts = np.asarray(pupil['ts'])
    pd = np.asarray(pupil['clean_pd'])
    if len(pd) < MIN_SAMPLES * 2:
        return []
    lf_sig = sosfiltfilt(LF_SOS, pd)
    hf_sig = sosfiltfilt(HF_SOS, pd)
    fix = load_fixations(tid)
    if not fix:
        return []
    tops = typed_aoi_tops(tid)
    if not tops:
        return []
    n_res = len(tops)

    _, scrolls = load_mouse_and_scroll(tid)
    scroll_t = first_scroll_t(scrolls) if scrolls else None

    segs = visit_segments_first_only_with_split(fix, tops, n_res, scroll_t)
    rows = []
    for pos, phases in segs.items():
        lf_pre = lfhf_for_windows(lf_sig, hf_sig, ts, phases['pre'])
        lf_post = lfhf_for_windows(lf_sig, hf_sig, ts, phases['post'])
        # Whole-segment LF/HF (pre + post combined) for back-compat
        all_windows = phases['pre'] + phases['post']
        lf_all = lfhf_for_windows(lf_sig, hf_sig, ts, all_windows)
        rows.append({
            'tid': tid, 'pid': tid.split('-')[0], 'pos': pos,
            'lfhf_pre': lf_pre, 'lfhf_post': lf_post, 'lfhf_all': lf_all,
            'has_pre_only': lf_pre is not None and lf_post is None,
            'has_post_only': lf_post is not None and lf_pre is None,
            'has_both': lf_pre is not None and lf_post is not None,
        })
    return rows


def main():
    print('[pre-vs-post-scroll] LF/HF by visit timing relative to first scroll',
          file=sys.stderr)
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    all_rows = []
    n_trials_done = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        r = process_trial(tid)
        if r:
            all_rows.extend(r); n_trials_done += 1

    print(f'\n  trials processed: {n_trials_done:,}', file=sys.stderr)
    print(f'  total (trial, pos) records: {len(all_rows):,}', file=sys.stderr)

    # Counts
    n_pre_only = sum(1 for r in all_rows if r['has_pre_only'])
    n_post_only = sum(1 for r in all_rows if r['has_post_only'])
    n_both = sum(1 for r in all_rows if r['has_both'])
    print(f'  pre-only (first visit fully before scroll): {n_pre_only:,}',
          file=sys.stderr)
    print(f'  post-only (first visit fully after scroll): {n_post_only:,}',
          file=sys.stderr)
    print(f'  both (first visit straddled scroll): {n_both:,}', file=sys.stderr)

    # Per-position medians, split
    by_pos = defaultdict(lambda: {'pre': [], 'post': [], 'all': []})
    for r in all_rows:
        if r['lfhf_pre'] is not None:
            by_pos[r['pos']]['pre'].append(r['lfhf_pre'])
        if r['lfhf_post'] is not None:
            by_pos[r['pos']]['post'].append(r['lfhf_post'])
        if r['lfhf_all'] is not None:
            by_pos[r['pos']]['all'].append(r['lfhf_all'])

    print(f'\n  Per-position medians (organic_hybrid, P0–P10):', file=sys.stderr)
    print(f'    {"pos":>3} {"N_pre":>6} {"med_pre":>9} '
          f'{"N_post":>7} {"med_post":>10} '
          f'{"N_all":>6} {"med_all":>9} {"Δ(post−pre)":>13}',
          file=sys.stderr)

    summary_per_pos = {}
    for pos in range(11):
        if pos not in by_pos:
            continue
        d = by_pos[pos]
        n_pre, n_post, n_all = len(d['pre']), len(d['post']), len(d['all'])
        med_pre = float(np.median(d['pre'])) if n_pre >= 5 else None
        med_post = float(np.median(d['post'])) if n_post >= 5 else None
        med_all = float(np.median(d['all'])) if n_all >= 5 else None
        delta = (med_post - med_pre) if (med_pre is not None and med_post is not None) else None
        # MW pre vs post
        mw_p = None
        if n_pre >= 5 and n_post >= 5:
            try:
                _, mw_p = stats.mannwhitneyu(d['pre'], d['post'], alternative='two-sided')
                mw_p = float(mw_p)
            except ValueError:
                pass

        s_pre = f'{med_pre:.2f}' if med_pre is not None else '—'
        s_post = f'{med_post:.2f}' if med_post is not None else '—'
        s_all = f'{med_all:.2f}' if med_all is not None else '—'
        s_delta = f'{delta:+.2f}' if delta is not None else '—'
        s_mwp = f'{mw_p:.2e}' if mw_p is not None else '—'
        print(f'    {pos:>3} {n_pre:>6,} {s_pre:>9} {n_post:>7,} {s_post:>10} '
              f'{n_all:>6,} {s_all:>9} {s_delta:>13} mwp={s_mwp}', file=sys.stderr)

        summary_per_pos[str(pos)] = {
            'n_pre': n_pre, 'n_post': n_post, 'n_all': n_all,
            'median_pre': med_pre, 'median_post': med_post, 'median_all': med_all,
            'delta_post_minus_pre': delta,
            'mw_p_two_sided': mw_p,
        }

    # Cross-position Spearman, separately for pre and post
    pre_pos = []
    pre_med = []
    post_pos = []
    post_med = []
    for pos in range(11):
        if str(pos) in summary_per_pos:
            s = summary_per_pos[str(pos)]
            if s['median_pre'] is not None:
                pre_pos.append(pos); pre_med.append(s['median_pre'])
            if s['median_post'] is not None:
                post_pos.append(pos); post_med.append(s['median_post'])

    pre_rho, pre_p = (None, None)
    post_rho, post_p = (None, None)
    if len(pre_pos) >= 3:
        res = stats.spearmanr(pre_pos, pre_med)
        pre_rho, pre_p = float(res.statistic), float(res.pvalue)
    if len(post_pos) >= 3:
        res = stats.spearmanr(post_pos, post_med)
        post_rho, post_p = float(res.statistic), float(res.pvalue)

    s_pre_rho = f'{pre_rho:+.3f}' if pre_rho is not None else '—'
    s_pre_p = f'{pre_p:.2e}' if pre_p is not None else '—'
    s_post_rho = f'{post_rho:+.3f}' if post_rho is not None else '—'
    s_post_p = f'{post_p:.2e}' if post_p is not None else '—'
    print(f'\n  Cross-position Spearman on PRE-scroll medians: rho={s_pre_rho}, '
          f'p={s_pre_p}, N={len(pre_pos)} positions', file=sys.stderr)
    print(f'  Cross-position Spearman on POST-scroll medians: rho={s_post_rho}, '
          f'p={s_post_p}, N={len(post_pos)} positions', file=sys.stderr)

    out = {
        'attribution': 'typed',
        'scroll_threshold_px': SCROLL_THRESHOLD_PX,
        'n_trials': n_trials_done,
        'n_records_total': len(all_rows),
        'counts': {
            'pre_only': n_pre_only,
            'post_only': n_post_only,
            'both_pre_and_post': n_both,
        },
        'per_position': summary_per_pos,
        'cross_position_spearman': {
            'pre_scroll': {'rho': pre_rho, 'p': pre_p, 'n': len(pre_pos)},
            'post_scroll': {'rho': post_rho, 'p': post_p, 'n': len(post_pos)},
        },
    }
    (OUT / 'summary.json').write_text(json.dumps(out, indent=2))

    # Markdown report
    lines = [
        '# LF/HF first visit by pre- vs post-first-scroll — organic_hybrid\n',
        '_Generated 2026-05-03 by `scripts/lfhf_pre_vs_post_scroll.py`._\n',
        '## Counts\n',
        f'- Trials processed: {n_trials_done:,}',
        f'- Total (trial, pos) records: {len(all_rows):,}',
        f'- Pre-only (first-visit fixations entirely before first scroll): {n_pre_only:,}',
        f'- Post-only (first-visit fixations entirely after first scroll): {n_post_only:,}',
        f'- Both (first-visit straddled the scroll event): {n_both:,}',
        '',
        '## Per-position median LF/HF, split by visit timing\n',
        '| Pos | N pre | median pre | N post | median post | N all | median all | Δ (post − pre) | MW p (two-sided) |',
        '|---|---|---|---|---|---|---|---|---|',
    ]
    for pos in range(11):
        if str(pos) not in summary_per_pos:
            continue
        s = summary_per_pos[str(pos)]
        s_pre = f'{s["median_pre"]:.2f}' if s["median_pre"] is not None else '—'
        s_post = f'{s["median_post"]:.2f}' if s["median_post"] is not None else '—'
        s_all = f'{s["median_all"]:.2f}' if s["median_all"] is not None else '—'
        s_delta = f'{s["delta_post_minus_pre"]:+.2f}' if s["delta_post_minus_pre"] is not None else '—'
        s_mwp = f'{s["mw_p_two_sided"]:.2e}' if s["mw_p_two_sided"] is not None else '—'
        lines.append(
            f'| {pos} | {s["n_pre"]:,} | {s_pre} | {s["n_post"]:,} | {s_post} | '
            f'{s["n_all"]:,} | {s_all} | {s_delta} | {s_mwp} |'
        )

    if pre_rho is not None and post_rho is not None:
        lines.extend([
            '\n## Cross-position Spearman ρ on per-position medians',
            '',
            f'- **PRE-scroll medians**: ρ = {pre_rho:+.3f}, *p* = {pre_p:.2e}, '
            f'N = {len(pre_pos)} positions',
            f'- **POST-scroll medians**: ρ = {post_rho:+.3f}, *p* = {post_p:.2e}, '
            f'N = {len(post_pos)} positions',
        ])

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
