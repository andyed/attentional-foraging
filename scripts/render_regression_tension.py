"""Regression-episode 'rubber-band' distribution.

For each regression episode (contiguous backward AOI-fixation sequence
that ends when HWM advances or the trial ends), measure:
  - hwm_onset    = HWM at the moment regression began
  - dip_floor    = minimum AOI rank reached during the episode
  - tension      = hwm_onset − dip_floor
  - n_fixations  = number of fixations within the episode

Render: dip_floor vs hwm_onset as a violin / scatter with median + IQR.
The shape of dip_floor by hwm_onset is the 'rubber-band' distribution.

Run:
  .venv/bin/python scripts/render_regression_tension.py --attribution organic
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    DATA_DIR, get_trial_ids, load_fixations, get_trial_meta,
    organic_aoi_tops, organic_aoi_bands, assign_fixation_to_position,
)

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
ACCENT = '#5B3EB8'
ACCENT2 = '#B8722C'

_AD_DIR = DATA_DIR / 'ad-boundary-data'


def _hybrid_aoi_tops(trial_id):
    bands = organic_aoi_bands(trial_id) or []
    items = [(t, b, 'organic') for t, b in bands]
    ad_path = _AD_DIR / f'{trial_id}.json'
    if ad_path.exists():
        ad_data = json.load(open(ad_path))
        for etype, elements in ad_data.items():
            if etype == 'dd_right':
                continue
            for el in elements:
                loc = el.get('location', {}); size = el.get('size', {})
                rx = loc.get('x', 0); ry = loc.get('y', 0)
                rw = size.get('width', 0); rh = size.get('height', 0)
                if not (rx < 750 and (rx + rw) > 50):
                    continue
                items.append((ry, ry + rh, etype))
    if not items:
        return []
    items.sort(key=lambda r: r[0])
    return [r[0] for r in items]


def find_episodes(pos_seq):
    """Return list of regression episodes."""
    episodes = []
    hwm = -1
    in_reg = False
    ep_start = None
    ep_min = None
    ep_n = 0
    for i, p in enumerate(pos_seq):
        if p > hwm:
            if in_reg:
                episodes.append({
                    'hwm_onset': hwm, 'dip_floor': ep_min,
                    'n_fixations': ep_n, 'tension': hwm - ep_min,
                })
                in_reg = False
            hwm = p
        elif p < hwm:
            if not in_reg:
                in_reg = True; ep_start = i; ep_min = p; ep_n = 1
            else:
                ep_min = min(ep_min, p); ep_n += 1
        else:
            # at HWM — close episode if in regression
            if in_reg:
                episodes.append({
                    'hwm_onset': hwm, 'dip_floor': ep_min,
                    'n_fixations': ep_n, 'tension': hwm - ep_min,
                })
                in_reg = False
    if in_reg:
        episodes.append({
            'hwm_onset': hwm, 'dip_floor': ep_min,
            'n_fixations': ep_n, 'tension': hwm - ep_min,
        })
    return episodes


def collect_episodes(attribution):
    eps = []
    for tid in get_trial_ids():
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        if attribution == 'hybrid':
            tops = _hybrid_aoi_tops(tid)
        else:
            tops = organic_aoi_tops(tid)
        if not tops:
            continue
        n_res = len(tops)
        pos_seq = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is not None and p >= 0:
                pos_seq.append(p)
        if len(pos_seq) < 2:
            continue
        eps.extend(find_episodes(pos_seq))
    return eps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'],
                    default='organic')
    args = ap.parse_args()

    print(f'[walk] attribution={args.attribution}', file=sys.stderr)
    eps = collect_episodes(args.attribution)
    print(f'  regression episodes: {len(eps):,}', file=sys.stderr)
    if not eps:
        return

    # Aggregate by hwm_onset
    by_hwm = defaultdict(list)
    for e in eps:
        by_hwm[e['hwm_onset']].append(e)
    hwms = sorted([h for h in by_hwm if len(by_hwm[h]) >= 30])

    # Stdout summary
    print()
    print(f'{"HWM":>5s}  {"n_eps":>7s}  {"med_dip":>7s}  '
          f'{"med_tension":>11s}  {"med_n_fix":>9s}  '
          f'{"frac_to_pos0":>13s}')
    for h in hwms:
        sub = by_hwm[h]
        med_dip = float(np.median([e['dip_floor'] for e in sub]))
        med_t = float(np.median([e['tension'] for e in sub]))
        med_n = float(np.median([e['n_fixations'] for e in sub]))
        frac0 = sum(1 for e in sub if e['dip_floor'] == 0) / len(sub)
        print(f'{h:>5d}  {len(sub):>7,}  {med_dip:>7.1f}  '
              f'{med_t:>11.1f}  {med_n:>9.1f}  {100*frac0:>12.1f}%')

    # ── render ──
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.5), facecolor=BG,
                             gridspec_kw={'hspace': 0.40, 'left': 0.08,
                                          'right': 0.97, 'top': 0.92,
                                          'bottom': 0.08,
                                          'height_ratios': [1.0, 0.6]})

    # Panel A: dip-floor distribution by HWM-onset
    ax = axes[0]
    ax.set_facecolor(BG)
    positions = list(range(len(hwms)))
    data = [[e['dip_floor'] for e in by_hwm[h]] for h in hwms]
    vp = ax.violinplot(data, positions=positions, widths=0.78,
                       showmeans=False, showmedians=False, showextrema=False)
    for body in vp['bodies']:
        body.set_facecolor(ACCENT); body.set_alpha(0.55)
        body.set_edgecolor(ACCENT); body.set_linewidth(0.7)

    # Median + IQR markers + median connector line
    medians = []
    p25s = []; p75s = []
    for x, vals in zip(positions, data):
        med = float(np.median(vals))
        q25 = float(np.percentile(vals, 25)); q75 = float(np.percentile(vals, 75))
        medians.append(med); p25s.append(q25); p75s.append(q75)
        ax.plot([x - 0.18, x + 0.18], [med, med], color='white',
                linewidth=2.4, zorder=4)
        ax.plot([x - 0.10, x + 0.10], [med, med], color=ACCENT,
                linewidth=2.4, zorder=5)
        ax.plot([x, x], [q25, q75], color=ACCENT, linewidth=1.0, alpha=0.8)
    ax.plot(positions, medians, color=ACCENT, linewidth=1.8, alpha=0.8,
            linestyle='-', zorder=3)

    # "Tension" annotation: hwm - dip floor median
    for x, h, med in zip(positions, hwms, medians):
        tension = h - med
        ax.text(x, h + 0.3, f't={tension:.1f}', ha='center', va='bottom',
                fontsize=8.5, color=ACCENT2, family='Georgia',
                weight='bold')
        ax.scatter([x], [h], color=ACCENT2, marker='_', s=80, zorder=2,
                   alpha=0.8)
    # HWM-onset reference line at the top
    ax.plot(positions, hwms, color=ACCENT2, linewidth=1.0, linestyle=':',
            alpha=0.7, label='HWM at onset (reference)')

    # Origin reference
    ax.axhline(0, color=MUTED, linewidth=0.8, alpha=0.6, linestyle='-',
               zorder=0)

    ax.set_xticks(positions)
    ax.set_xticklabels([str(h) for h in hwms], fontsize=10, color=INK,
                       family='Georgia')
    ax.set_xlabel('HWM at episode onset', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_ylabel('dip floor (minimum rank reached)', fontsize=11,
                  color=INK, family='Georgia')
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED); ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    attr_label = 'organic_hybrid' if args.attribution == 'hybrid' else 'bbox-organic'
    ax.set_title(
        f'A. Regression-episode dip-floor by HWM-onset  —  [{attr_label}]  ·  '
        f'{len(eps):,} episodes  ·  '
        'orange dashes = HWM-onset reference; t = tension (HWM − median dip floor)',
        fontsize=11.5, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')
    ax.legend(loc='upper left', fontsize=9.5, frameon=True,
              facecolor=BG, edgecolor=RULE, labelcolor=INK)

    # Panel B: episode length (n_fixations) by HWM-onset
    ax = axes[1]
    ax.set_facecolor(BG)
    n_data = [[e['n_fixations'] for e in by_hwm[h]] for h in hwms]
    medians_n = [float(np.median(d)) for d in n_data]
    p25_n = [float(np.percentile(d, 25)) for d in n_data]
    p75_n = [float(np.percentile(d, 75)) for d in n_data]
    ax.fill_between(positions, p25_n, p75_n, color=ACCENT, alpha=0.20,
                    zorder=2, label='IQR')
    ax.plot(positions, medians_n, color=ACCENT, linewidth=2.2, marker='o',
            markersize=7, markeredgecolor='white', markeredgewidth=1.0,
            label='median')
    for x, m in zip(positions, medians_n):
        ax.text(x, m + 0.25, f'{m:.0f}', ha='center', va='bottom',
                fontsize=9, color=ACCENT, family='Georgia', weight='bold')
    ax.set_xticks(positions)
    ax.set_xticklabels([str(h) for h in hwms], fontsize=10, color=INK,
                       family='Georgia')
    ax.set_xlabel('HWM at episode onset', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_ylabel('episode length (fixations)', fontsize=11,
                  color=INK, family='Georgia')
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED); ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    ax.set_title(
        'B. Episode length (number of fixations within the regression run)',
        fontsize=11.5, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')
    ax.legend(loc='upper left', fontsize=9.5, frameon=True,
              facecolor=BG, edgecolor=RULE, labelcolor=INK)

    out_png = ROOT / 'scripts/output/figures' / f'regression_tension_{args.attribution}.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'\n  wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
