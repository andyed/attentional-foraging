"""Difference plot: Δ(regressive − forward) per metric per bin, single panel.

Companion to render_saccade_metrics_by_bin.py: same data collection,
unified single-panel framing. Y-axis = % deviation of regressive median
from forward median (so all four metrics share an axis). X-axis = source-
position bin.

Run:
  .venv/bin/python scripts/render_saccade_diff_plot.py --attribution organic
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent

# Import collect_saccades + bin_label from the sibling script
spec = importlib.util.spec_from_file_location(
    'rsm', ROOT / 'scripts' / 'render_saccade_metrics_by_bin.py')
rsm = importlib.util.module_from_spec(spec)
sys.modules['rsm'] = rsm
spec.loader.exec_module(rsm)

# editorial cream palette
BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'

METRICS = [
    ('jump_size',       'Jump size (ranks)',       '#5B3EB8'),  # purple
    ('source_dwell_ms', 'Source dwell (ms)',       '#3A7D44'),  # green
    ('saccade_speed',   'Saccade speed (ranks/s)', '#B8722C'),  # orange
    ('source_visits',   'Source visit count',      '#6B5B95'),  # muted purple
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'],
                    default='organic')
    args = ap.parse_args()

    print(f'[walk] attribution={args.attribution}', file=sys.stderr)
    events, n_trials = rsm.collect_saccades(args.attribution)
    print(f'  trials walked: {n_trials:,}  saccades: {len(events):,}',
          file=sys.stderr)

    bins = ['top (0-3)', 'mid (4-7)', 'deep (8+)']
    bin_x = {bins[0]: 0, bins[1]: 1, bins[2]: 2}

    # Compute medians per (bin, direction, metric)
    medians = {}  # (bin, direction, metric) -> median
    counts = {}
    for b in bins:
        for d in ('forward', 'regressive'):
            es = [e for e in events
                  if rsm.bin_label(e['source_pos']) == b and e['direction'] == d]
            counts[(b, d)] = len(es)
            for mkey, _, _ in METRICS:
                medians[(b, d, mkey)] = (
                    float(np.median([e[mkey] for e in es])) if es else float('nan')
                )

    # Δ% per metric per bin: (reg − fwd) / fwd × 100
    deltas = {}
    for mkey, _, _ in METRICS:
        deltas[mkey] = []
        for b in bins:
            fwd = medians[(b, 'forward', mkey)]
            reg = medians[(b, 'regressive', mkey)]
            if fwd and not np.isnan(fwd) and fwd != 0:
                deltas[mkey].append(100 * (reg - fwd) / fwd)
            else:
                deltas[mkey].append(float('nan'))

    # ── render ──
    fig = plt.figure(figsize=(11, 6.5), facecolor=BG)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.5, 1.0],
                          wspace=0.10,
                          left=0.08, right=0.97,
                          top=0.86, bottom=0.12)

    ax = fig.add_subplot(gs[0, 0])
    ax.set_facecolor(BG)

    # Zero reference
    ax.axhline(0, color=MUTED, linewidth=1.2, linestyle='-', alpha=0.85,
               zorder=1)
    ax.text(2.05, 0, 'forward = baseline', fontsize=9, color=MUTED,
            family='Georgia', va='center', alpha=0.9)

    # Lines
    for mkey, mlabel, mcolor in METRICS:
        ys = deltas[mkey]
        xs = list(range(len(bins)))
        ax.plot(xs, ys, color=mcolor, linewidth=2.4, marker='o',
                markersize=9, markeredgecolor='white', markeredgewidth=1.2,
                zorder=4, label=mlabel)
        # Annotate each point
        for x, y in zip(xs, ys):
            if np.isnan(y):
                continue
            sign = '+' if y >= 0 else ''
            ax.text(x, y + 3 * (1 if y >= 0 else -1), f'{sign}{y:.0f}%',
                    ha='center', va='bottom' if y >= 0 else 'top',
                    fontsize=9.5, color=mcolor, family='Georgia',
                    weight='bold')

    ax.set_xticks(list(range(len(bins))))
    ax.set_xticklabels(bins, fontsize=11, color=INK, family='Georgia')
    ax.set_xlabel('source-position bin', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_ylabel('Δ regressive − forward median  (% of forward)',
                  fontsize=11, color=INK, family='Georgia')

    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)

    attr_label = 'organic_hybrid' if args.attribution == 'hybrid' else 'bbox-organic'
    n_total = len(events)
    n_fwd = sum(1 for e in events if e['direction'] == 'forward')
    n_reg = sum(1 for e in events if e['direction'] == 'regressive')
    ax.set_title(
        f'Saccade-metric divergence: regressive vs forward, by source-position bin  —  '
        f'[{attr_label}]\n{n_total:,} saccades  '
        f'({n_fwd:,} forward, {n_reg:,} regressive)',
        fontsize=11.5, color=INK, family='Georgia', loc='left', pad=12,
        weight='bold')

    ax.legend(loc='upper left', fontsize=10, frameon=True,
              facecolor=BG, edgecolor=RULE, labelcolor=INK)

    # ── companion table on the right ──
    ax_t = fig.add_subplot(gs[0, 1])
    ax_t.set_facecolor(BG)
    ax_t.axis('off')

    # Table cells: bin × metric, showing fwd / reg medians
    rows = []
    for b in bins:
        for mkey, mlabel, mcolor in METRICS:
            fwd = medians[(b, 'forward', mkey)]
            reg = medians[(b, 'regressive', mkey)]
            fmt = '.0f' if mkey != 'jump_size' else '.1f'
            if mkey == 'source_visits':
                fmt = '.0f'
            rows.append((b, mlabel.split(' (')[0], f'{fwd:{fmt}}', f'{reg:{fmt}}', mcolor))

    # Render a stacked text table
    y_step = 0.041
    y_top = 0.95
    ax_t.text(0, y_top + 0.025, 'Median values',
              fontsize=11.5, color=INK, family='Georgia', weight='bold',
              transform=ax_t.transAxes)
    ax_t.text(0.42, y_top - 0.005, 'fwd', fontsize=10, color=INK,
              family='Georgia', weight='bold', transform=ax_t.transAxes)
    ax_t.text(0.62, y_top - 0.005, 'reg', fontsize=10, color=INK,
              family='Georgia', weight='bold', transform=ax_t.transAxes)
    ax_t.axhline = None
    ax_t.plot([0, 0.85], [y_top - 0.025, y_top - 0.025], color=MUTED,
              linewidth=0.8, transform=ax_t.transAxes, zorder=1)

    last_bin = None
    y = y_top - 0.06
    for (b, ml, fwd_s, reg_s, mcolor) in rows:
        if b != last_bin:
            if last_bin is not None:
                y -= 0.012
            ax_t.text(0, y, b, fontsize=10, color=INK, family='Georgia',
                      weight='bold', transform=ax_t.transAxes)
            y -= y_step
            last_bin = b
        ax_t.text(0.04, y, ml, fontsize=9, color=mcolor, family='Georgia',
                  transform=ax_t.transAxes)
        ax_t.text(0.42, y, fwd_s, fontsize=9.5, color=INK, family='Georgia',
                  transform=ax_t.transAxes)
        ax_t.text(0.62, y, reg_s, fontsize=9.5, color=INK, family='Georgia',
                  transform=ax_t.transAxes)
        y -= y_step

    # Print the deltas to stdout as well
    print()
    print(f'{"":>22s}  ' + '  '.join(f'{b:>12s}' for b in bins))
    for mkey, mlabel, _ in METRICS:
        cells = [f'{deltas[mkey][i]:+11.1f}%' for i in range(len(bins))]
        print(f'{mlabel:>22s}  ' + '  '.join(cells))

    out_png = ROOT / 'scripts/output/figures' / f'saccade_diff_plot_{args.attribution}.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'\n  wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
