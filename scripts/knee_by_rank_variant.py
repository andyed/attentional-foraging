"""How do ads affect the per-trial knee? Contrast rank variants.

Knee = deepest position fixated before first significant scroll.

Computes knee distribution under three attributions in parallel:
  - absolute    : legacy h3-based, ads pooled in display order with organics
  - organic     : bbox-organic only, ads excluded from rank counting
  - organic_hybrid : bbox organic + dd_top + native_ad in display order

Internal-only — for understanding ad effects on the knee mechanism, not for
ETTAC paper text.

Output: scripts/output/knee_by_rank_variant/{summary.json, report.md}

Run:
  .venv/bin/python scripts/knee_by_rank_variant.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/knee_by_rank_variant'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_and_scroll, get_trial_meta,
    organic_aoi_tops, extract_serp_results, result_band_tops,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

SCROLL_THRESHOLD_PX = 100


def first_scroll_t(scrolls):
    for t, y in scrolls:
        if y > SCROLL_THRESHOLD_PX:
            return t
    return None


def get_tops(tid, attr):
    meta = get_trial_meta(tid)
    if meta is None or not meta[0]:
        return None, None
    doc_h = meta[0]
    if attr == 'organic':
        tops = organic_aoi_tops(tid)
        n = len(tops) if tops else 0
    elif attr == 'organic_hybrid':
        tops = _hybrid_aoi_tops(tid)
        n = len(tops) if tops else 0
    elif attr == 'typed':
        from data_loader import typed_aoi_tops
        tops = typed_aoi_tops(tid)
        n = len(tops) if tops else 0
    else:  # absolute
        serp = extract_serp_results(tid)
        n = len(serp) if serp else 10
        tops = result_band_tops(n, doc_h) if n else None
    if not tops or n == 0:
        return None, None
    return tops, n


def knee_for_trial(tid, attr):
    """Return (deepest_pre_scroll, p0_etype_marker) or None."""
    meta = get_trial_meta(tid)
    if meta is None or not meta[1]:
        return None
    _, screen_h, _ = meta
    tops, n = get_tops(tid, attr)
    if tops is None:
        return None
    fix = load_fixations(tid)
    if not fix:
        return None
    _, scrolls = load_mouse_and_scroll(tid)
    scroll_t = first_scroll_t(scrolls) if scrolls else None
    if scroll_t is None:
        return None  # exclude no-scroll trials for the knee distribution

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
    print('[knee-by-rank-variant] knee distribution under 3 attributions',
          file=sys.stderr)
    feats = json.load(open(DATA / 'cursor-approach-features-organic-hybrid.json'))
    p0_etype_hybrid = {}
    for r in feats:
        if r['position'] == 0:
            p0_etype_hybrid[r['trial_id']] = r.get('etype')

    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,}', file=sys.stderr)

    knees = defaultdict(dict)
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        for attr in ('absolute', 'organic', 'organic_hybrid', 'typed'):
            k = knee_for_trial(tid, attr)
            if k is not None:
                knees[tid][attr] = k

    # Trials present under all three (apples-to-apples)
    common = [tid for tid in trial_ids
              if all(a in knees[tid] for a in ('absolute', 'organic', 'organic_hybrid', 'typed'))]
    print(f'\n  trials with knee defined under all 3 attributions: {len(common):,}',
          file=sys.stderr)

    summary = {'attributions': {}, 'n_common_trials': len(common)}

    for attr in ('absolute', 'organic', 'organic_hybrid', 'typed'):
        all_knees = [knees[tid][attr] for tid in common]
        arr = np.array(all_knees)
        c = Counter(arr.tolist())
        summary['attributions'][attr] = {
            'n_trials': len(arr),
            'median': int(np.median(arr)),
            'mean': float(arr.mean()),
            'p25': int(np.percentile(arr, 25)),
            'p75': int(np.percentile(arr, 75)),
            'distribution': {str(int(k)): int(v) for k, v in sorted(c.items())},
        }
        print(f'\n  === {attr} ===', file=sys.stderr)
        print(f'  N = {len(arr):,}  median = P{int(np.median(arr))}  '
              f'p25/p50/p75 = P{int(np.percentile(arr, 25))}/'
              f'P{int(np.percentile(arr, 50))}/P{int(np.percentile(arr, 75))}',
              file=sys.stderr)
        for k_pos in sorted(c.keys()):
            label = 'none' if k_pos < 0 else f'P{int(k_pos)}'
            pct = 100 * c[k_pos] / len(arr)
            print(f'    {label}: {c[k_pos]:,} ({pct:.1f}%)', file=sys.stderr)

    # Stratify by hybrid P0 etype
    print(f'\n  === Stratified by HYBRID P0 etype (across all 3 attributions) ===',
          file=sys.stderr)
    by_etype = defaultdict(lambda: {a: [] for a in ('absolute', 'organic', 'organic_hybrid', 'typed')})
    for tid in common:
        et = p0_etype_hybrid.get(tid, 'unknown')
        for a in ('absolute', 'organic', 'organic_hybrid', 'typed'):
            by_etype[et][a].append(knees[tid][a])

    summary['by_hybrid_p0_etype'] = {}
    for et in sorted(by_etype.keys()):
        summary['by_hybrid_p0_etype'][et] = {}
        print(f'\n    {et}:', file=sys.stderr)
        for a in ('absolute', 'organic', 'organic_hybrid', 'typed'):
            ks = by_etype[et][a]
            if not ks:
                continue
            arr = np.array(ks)
            summary['by_hybrid_p0_etype'][et][a] = {
                'n': len(arr),
                'median': int(np.median(arr)),
                'mean': float(arr.mean()),
                'p25': int(np.percentile(arr, 25)),
                'p75': int(np.percentile(arr, 75)),
            }
            print(f'      {a}: n={len(arr):,}  median=P{int(np.median(arr))}  '
                  f'p25/p75=P{int(np.percentile(arr, 25))}/P{int(np.percentile(arr, 75))}',
                  file=sys.stderr)

    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Markdown
    lines = [
        '# Knee position by rank variant — internal\n',
        '_Generated 2026-05-03 by `scripts/knee_by_rank_variant.py`._\n',
        f'Apples-to-apples cohort: {len(common):,} trials with knee defined under all 3 attributions.\n',
        '## Headline\n',
        '| Attribution | n | median knee | p25 / p50 / p75 |',
        '|---|---|---|---|',
    ]
    for a in ('absolute', 'organic', 'organic_hybrid', 'typed'):
        s = summary['attributions'][a]
        lines.append(f'| {a} | {s["n_trials"]:,} | P{s["median"]} | '
                     f'P{s["p25"]} / P{s["median"]} / P{s["p75"]} |')

    lines.append('\n## Knee distribution per attribution\n')
    lines.append('| knee pos | absolute | organic | organic_hybrid |')
    lines.append('|---|---|---|---|')
    all_keys = set()
    for a in ('absolute', 'organic', 'organic_hybrid', 'typed'):
        all_keys |= set(summary['attributions'][a]['distribution'].keys())
    for k in sorted(all_keys, key=lambda x: int(x)):
        a_n = summary['attributions']['absolute']['distribution'].get(k, 0)
        o_n = summary['attributions']['organic']['distribution'].get(k, 0)
        h_n = summary['attributions']['organic_hybrid']['distribution'].get(k, 0)
        a_pct = 100 * a_n / len(common)
        o_pct = 100 * o_n / len(common)
        h_pct = 100 * h_n / len(common)
        label = 'none (no pre-scroll fix)' if int(k) < 0 else f'P{k}'
        lines.append(f'| {label} | {a_n:,} ({a_pct:.1f}%) | {o_n:,} ({o_pct:.1f}%) | '
                     f'{h_n:,} ({h_pct:.1f}%) |')

    lines.append('\n## Stratified by hybrid P0 etype\n')
    lines.append('| P0 (hybrid) | attribution | n | median knee | p25 / p75 |')
    lines.append('|---|---|---|---|---|')
    for et in sorted(by_etype.keys()):
        for a in ('absolute', 'organic', 'organic_hybrid', 'typed'):
            s = summary['by_hybrid_p0_etype'].get(et, {}).get(a)
            if not s:
                continue
            lines.append(f'| {et} | {a} | {s["n"]:,} | P{s["median"]} | '
                         f'P{s["p25"]} / P{s["p75"]} |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
