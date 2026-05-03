"""Saccade participation by direction × source-position bin × element type.

External-validation chart: shows that the regress-scan-regress pattern
participates across both organic and ad surfaces (it's not an artifact of
organic-only attribution). Two-panel design:

  Top panel    — absolute saccade counts, stacked by source etype
  Bottom panel — same data normalized to 100% within each (bin, direction)

X-axis (6 categories): bin × direction = top-fwd / top-reg / mid-fwd /
mid-reg / deep-fwd / deep-reg.

Source etype: organic / dd_top / native_ad — pulled from the hybrid AOI
display order. Right-rail ads (dd_right) are excluded by construction
(consistent with the hybrid attribution policy).

Run:
  .venv/bin/python scripts/render_saccade_participation.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    DATA_DIR, get_trial_ids, load_fixations, get_trial_meta,
    organic_aoi_bands, assign_fixation_to_position,
)

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'

# Etype colors — purple-spectrum for organic, warm for ads (visible separation)
COLOR_ORGANIC = '#5B3EB8'   # purple
COLOR_DD_TOP = '#B8722C'    # orange — top-of-page ad
COLOR_NATIVE = '#D7A95C'    # warm gold — in-stream ad

# Direction colors for x-axis annotation
COLOR_FWD = '#3A2680'
COLOR_REG = '#7C2D12'

_AD_DIR = DATA_DIR / 'ad-boundary-data'
_RESULT_COL_X_MIN = 50
_RESULT_COL_X_MAX = 750


def _hybrid_aoi_with_etype(trial_id):
    """Return (tops, etypes) parallel lists in display order.
    Same logic as _hybrid_aoi_tops but preserves etype tags."""
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
                if not (rx < _RESULT_COL_X_MAX and (rx + rw) > _RESULT_COL_X_MIN):
                    continue
                items.append((ry, ry + rh, etype))
    if not items:
        return [], []
    items.sort(key=lambda r: r[0])
    return [r[0] for r in items], [r[2] for r in items]


def collect_participation():
    """Walk all trials under hybrid attribution; return saccade events with
    source etype + bin + direction tags."""
    events = []
    n_trials_walked = 0
    for tid in get_trial_ids():
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        tops, etypes = _hybrid_aoi_with_etype(tid)
        if not tops:
            continue
        n_res = len(tops)

        mapped = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is None or p < 0:
                continue
            mapped.append({'pos': int(p), 'etype': etypes[p]})
        if len(mapped) < 2:
            continue
        n_trials_walked += 1

        for i in range(len(mapped) - 1):
            src = mapped[i]; tgt = mapped[i + 1]
            if src['pos'] == tgt['pos']:
                continue
            jump = tgt['pos'] - src['pos']
            direction = 'forward' if jump > 0 else 'regressive'
            events.append({
                'tid': tid,
                'source_pos': src['pos'],
                'source_etype': src['etype'],
                'direction': direction,
            })
    return events, n_trials_walked


def bin_of(pos):
    if pos <= 3: return 'top (0-3)'
    if pos <= 7: return 'mid (4-7)'
    return 'deep (8+)'


def main():
    print('[walk] attribution=hybrid (with etype tags)', file=sys.stderr)
    events, n_trials = collect_participation()
    print(f'  trials walked: {n_trials:,}  saccades: {len(events):,}',
          file=sys.stderr)

    bins = ['top (0-3)', 'mid (4-7)', 'deep (8+)']
    directions = ['forward', 'regressive']
    etypes = ['organic', 'dd_top', 'native_ad']
    etype_colors = {
        'organic': COLOR_ORGANIC,
        'dd_top': COLOR_DD_TOP,
        'native_ad': COLOR_NATIVE,
    }
    etype_labels = {
        'organic': 'organic',
        'dd_top': 'dd_top (top-of-page ad)',
        'native_ad': 'native_ad (in-stream ad)',
    }

    # Tally counts by (bin, direction, etype)
    counts = defaultdict(int)
    for e in events:
        b = bin_of(e['source_pos'])
        counts[(b, e['direction'], e['source_etype'])] += 1

    # Stdout summary
    print()
    print(f'{"bin":>12s}  {"dir":>6s}  '
          + '  '.join(f'{et:>11s}' for et in etypes) + f'  {"total":>8s}')
    for b in bins:
        for d in directions:
            cells = []
            tot = 0
            for et in etypes:
                v = counts[(b, d, et)]
                cells.append(f'{v:>11,}')
                tot += v
            print(f'{b:>12s}  {d:>6s}  ' + '  '.join(cells) + f'  {tot:>8,}')

    # ── render ──
    fig, axes = plt.subplots(2, 1, figsize=(11, 8.5), facecolor=BG,
                             gridspec_kw={'hspace': 0.42, 'left': 0.10,
                                          'right': 0.97, 'top': 0.92,
                                          'bottom': 0.10,
                                          'height_ratios': [1.0, 1.0]})

    # X positions: 6 bars in 3 groups of 2 (bin × direction)
    bar_positions = []
    bar_labels = []
    bar_dirs = []
    bar_bins = []
    x = 0
    for b in bins:
        for d in directions:
            bar_positions.append(x)
            bar_labels.append(d[:3])  # 'for' / 'reg'
            bar_dirs.append(d)
            bar_bins.append(b)
            x += 1
        x += 0.7  # gap between bins

    bar_positions = np.array(bar_positions, dtype=float)

    # Panel 1: absolute counts, stacked by etype
    ax = axes[0]
    ax.set_facecolor(BG)
    bottom = np.zeros(len(bar_positions))
    for et in etypes:
        heights = np.array([counts[(bar_bins[i], bar_dirs[i], et)]
                            for i in range(len(bar_positions))])
        ax.bar(bar_positions, heights, bottom=bottom, width=0.75,
               color=etype_colors[et], edgecolor='white', linewidth=0.6,
               label=etype_labels[et], zorder=3)
        # Annotate within-stack count if material
        for i, h in enumerate(heights):
            if h >= 200:
                ax.text(bar_positions[i], bottom[i] + h / 2, f'{h:,}',
                        ha='center', va='center', fontsize=8.5,
                        color='white', family='Georgia', weight='bold')
        bottom += heights
    # Total annotation above each bar
    for i, tot in enumerate(bottom):
        ax.text(bar_positions[i], tot + 200, f'{int(tot):,}',
                ha='center', va='bottom', fontsize=9, color=INK,
                family='Georgia', weight='bold')

    ax.set_xticks(bar_positions)
    ax.set_xticklabels(bar_labels, fontsize=10, color=INK, family='Georgia')
    # Bin labels under groups
    bin_centers = []
    for b in bins:
        idxs = [i for i in range(len(bar_positions)) if bar_bins[i] == b]
        bin_centers.append(np.mean([bar_positions[i] for i in idxs]))
    for cx, b in zip(bin_centers, bins):
        ax.text(cx, -0.13, b, ha='center', va='top', fontsize=11,
                color=INK, family='Georgia', weight='bold',
                transform=ax.get_xaxis_transform())
    ax.set_ylabel('saccade count', fontsize=11, color=INK, family='Georgia')
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    ax.legend(loc='upper right', fontsize=9.5, frameon=True,
              facecolor=BG, edgecolor=RULE, labelcolor=INK)
    n_total = sum(counts.values())
    ax.set_title(
        f'A. Absolute saccade participation by source etype  —  '
        f'[organic_hybrid attribution]  ·  {n_total:,} saccades  '
        f'across {n_trials:,} trials',
        fontsize=12, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')

    # Panel 2: 100%-normalized composition
    ax = axes[1]
    ax.set_facecolor(BG)
    bottom = np.zeros(len(bar_positions))
    for et in etypes:
        shares = []
        for i in range(len(bar_positions)):
            tot = sum(counts[(bar_bins[i], bar_dirs[i], e)] for e in etypes)
            shares.append(100 * counts[(bar_bins[i], bar_dirs[i], et)] / max(tot, 1))
        shares = np.array(shares)
        ax.bar(bar_positions, shares, bottom=bottom, width=0.75,
               color=etype_colors[et], edgecolor='white', linewidth=0.6,
               zorder=3)
        for i, h in enumerate(shares):
            if h >= 8:
                ax.text(bar_positions[i], bottom[i] + h / 2, f'{h:.0f}%',
                        ha='center', va='center', fontsize=9,
                        color='white', family='Georgia', weight='bold')
        bottom += shares

    ax.set_xticks(bar_positions)
    ax.set_xticklabels(bar_labels, fontsize=10, color=INK, family='Georgia')
    for cx, b in zip(bin_centers, bins):
        ax.text(cx, -0.13, b, ha='center', va='top', fontsize=11,
                color=INK, family='Georgia', weight='bold',
                transform=ax.get_xaxis_transform())
    ax.set_ylabel('etype share within bar (%)', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_ylim(0, 100)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    ax.set_title(
        'B. Composition (etype share within each bin × direction cell)',
        fontsize=12, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')

    out_png = ROOT / 'scripts/output/figures/saccade_participation_hybrid.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'\n  wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
