"""Option Y — rebuilt two-panel task overview.

Same composition as the original, but with the muriel-critique fixes applied:
  - Visible cell tints (organics light, ads single warm tone)
  - No chartjunk inside cells (no decorative title/snippet stripes)
  - Curved forward path (natural drift, not rigid stick)
  - Two regressive arrows visually distinct (one solid thin, one thick dashed)
  - Single anchored "scanning order" annotation, no floating margin tags
  - Larger +Δ% hero number on panel (b)
  - Tighter bullet block (2 anchors, merged primary+secondary)

Run:
  .venv/bin/python scripts/render_task_overview_Y.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parent.parent

# editorial cream palette
BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
FWD = '#5B3EB8'
REG = '#B8722C'

# Cell fills — clearly visible against BG
ORGANIC = '#EAE6DA'              # warm pale grey, distinguishable from BG
AD = '#F0D5A8'                   # single ad tone (no dd_top/native_ad split — drop the noise)
CELL_BORDER = '#7E7868'

DEFAULT_STATS = {
    'fwd_speed_mid': 784.0,
    'reg_speed_mid': 972.0,
    'multi_cycle_pct': 62.4,
    'transition_hwm': 8,
}


def draw_serp(ax):
    ax.set_facecolor(BG)
    cells = [
        # (rank, etype, height_units)
        (0, 'ad',      1.10),
        (1, 'organic', 1.00),
        (2, 'ad',      0.90),
        (3, 'organic', 1.05),
        (4, 'organic', 1.00),
        (5, 'organic', 0.95),
        (6, 'organic', 1.00),
        (7, 'organic', 1.05),
    ]
    cell_w = 1.0
    x0 = 0.0
    cell_top = 0.0
    centers = []
    for rank, etype, h_units in cells:
        height = h_units * 0.78
        bottom = cell_top - height
        cy = (cell_top + bottom) / 2
        fill = AD if etype == 'ad' else ORGANIC
        ax.add_patch(Rectangle(
            (x0, bottom), cell_w, height,
            facecolor=fill, edgecolor=CELL_BORDER, linewidth=0.8,
            zorder=1,
        ))
        # Rank label, left of cell
        ax.text(x0 - 0.14, cy, str(rank), ha='right', va='center',
                fontsize=10, color=INK, family='Georgia', weight='bold')
        # Etype tag, right of cell (only for ads — minimal labeling)
        if etype == 'ad':
            ax.text(x0 + cell_w + 0.10, cy, 'ad', ha='left', va='center',
                    fontsize=9, color=MUTED, family='Georgia',
                    style='italic')
        centers.append((x0 + cell_w * 0.55, cy))
        cell_top = bottom - 0.06

    # ── Forward scanpath: curved descent with natural drift ──
    # Use a slight zigzag x-offset to suggest scanning, then anchor at cell centers
    rng = np.random.default_rng(20260503)
    drift = rng.uniform(-0.10, 0.10, size=len(centers))
    fwd_xs = np.array([c[0] + 0.0 + d for c, d in zip(centers, drift)])
    fwd_ys = np.array([c[1] for c in centers])
    # Smooth via Bezier-ish anchor — just plot with a smooth line connection
    ax.plot(fwd_xs, fwd_ys, color=FWD, linewidth=2.4, zorder=4,
            solid_capstyle='round')
    for x, y in zip(fwd_xs, fwd_ys):
        ax.scatter([x], [y], s=42, color=FWD, edgecolor='white',
                   linewidth=1.0, zorder=5)
    # Single anchored "1. forward sweep" annotation tied to first fixation
    ax.annotate(
        '1. forward sweep',
        xy=(fwd_xs[0], fwd_ys[0]),
        xytext=(fwd_xs[0] - 0.85, fwd_ys[0] + 0.18),
        fontsize=10, color=FWD, family='Georgia', weight='bold',
        arrowprops=dict(arrowstyle='-', color=FWD, linewidth=0.8,
                        alpha=0.7),
    )

    # ── Regressive episode A: short adjacent (rank 3 → rank 2). Thin solid. ──
    src1, tgt1 = centers[3], centers[2]
    arrow1 = FancyArrowPatch(
        (src1[0] + 0.42, src1[1]),
        (tgt1[0] + 0.42, tgt1[1]),
        arrowstyle='-|>', mutation_scale=12,
        color=REG, linewidth=1.4, linestyle='-',
        connectionstyle='arc3,rad=0.45', zorder=3, alpha=0.8,
    )
    ax.add_patch(arrow1)
    ax.annotate(
        '2a. short adjacent\nregression',
        xy=((src1[0] + tgt1[0]) / 2 + 0.55, (src1[1] + tgt1[1]) / 2),
        xytext=(src1[0] + 1.00, (src1[1] + tgt1[1]) / 2),
        fontsize=8.5, color=REG, family='Georgia', style='italic',
        ha='left', va='center',
        arrowprops=dict(arrowstyle='-', color=REG, linewidth=0.6, alpha=0.5),
    )

    # ── Regressive episode B: anchor return (rank 7 → rank 0). Thick dashed. ──
    src2, tgt2 = centers[7], centers[0]
    arrow2 = FancyArrowPatch(
        (src2[0] + 0.42, src2[1]),
        (tgt2[0] + 0.42, tgt2[1]),
        arrowstyle='-|>', mutation_scale=18,
        color=REG, linewidth=2.8, linestyle=(0, (5, 2.5)),
        connectionstyle='arc3,rad=0.55', zorder=4,
    )
    ax.add_patch(arrow2)
    ax.annotate(
        '2b. anchor return',
        xy=(src2[0] + 1.10, (src2[1] + tgt2[1]) / 2 + 0.3),
        xytext=(src2[0] + 1.10, (src2[1] + tgt2[1]) / 2 + 0.3),
        fontsize=10, color=REG, family='Georgia', weight='bold',
        ha='left', va='center',
    )
    ax.text(src2[0] + 1.10, (src2[1] + tgt2[1]) / 2 + 0.05,
            '50% of HWM≥8 episodes',
            fontsize=8.5, color=MUTED, family='Georgia',
            style='italic', ha='left', va='center')

    # Layout
    ax.set_xlim(-0.50, 2.60)
    ax.set_ylim(cell_top - 0.10, 0.40)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title('(a)  Forward sweep, then return',
                 fontsize=12, color=INK, family='Georgia', loc='left',
                 pad=10, weight='bold')


def draw_data_panel(ax, stats):
    ax.set_facecolor(BG)

    # Bigger hero +Δ%
    delta = 100 * (stats['reg_speed_mid'] - stats['fwd_speed_mid']) / stats['fwd_speed_mid']
    ax.text(0.50, 0.84, f'+{delta:.0f}%',
            ha='center', va='center', fontsize=44, color=REG,
            family='Georgia', weight='bold', transform=ax.transAxes)
    ax.text(0.50, 0.71,
            'regressive scroll vs forward, mid-page',
            ha='center', va='center', fontsize=10.5, color=MUTED,
            family='Georgia', style='italic',
            transform=ax.transAxes)

    # Two compact bars below the hero
    bar_h = 0.07
    bar_x_left = 0.10
    bar_x_max = 0.78
    max_speed = max(stats['fwd_speed_mid'], stats['reg_speed_mid'])

    def bar(y, val, color, label):
        w = (bar_x_max - bar_x_left) * (val / max_speed)
        ax.add_patch(patches.Rectangle(
            (bar_x_left, y), w, bar_h,
            facecolor=color, alpha=0.55, edgecolor=color, linewidth=1.2,
            transform=ax.transAxes,
        ))
        ax.text(bar_x_left - 0.005, y + bar_h / 2, label,
                ha='right', va='center', fontsize=10, color=INK,
                family='Georgia', weight='bold', transform=ax.transAxes)
        ax.text(bar_x_left + w + 0.012, y + bar_h / 2,
                f'{int(val):,} px/s',
                ha='left', va='center', fontsize=10.5, color=color,
                family='Georgia', weight='bold', transform=ax.transAxes)

    bar(0.50, stats['fwd_speed_mid'], FWD, 'forward')
    bar(0.40, stats['reg_speed_mid'], REG, 'regressive')

    # Two compact stat anchors (merged primary + secondary)
    ax.text(0.05, 0.22,
            f'•  {stats["multi_cycle_pct"]:.0f}% of trials have ≥ 1 regress-scan-regress cycle '
            '— multi-cycle is the modal pattern, not a special case',
            ha='left', va='top', fontsize=10, color=INK,
            family='Georgia', transform=ax.transAxes,
            wrap=True)
    ax.text(0.05, 0.10,
            f'•  Regression-episode tension grows past HWM = {stats["transition_hwm"]} '
            '(1–3 → 5–9 ranks median); local re-eval gives way to anchor return',
            ha='left', va='top', fontsize=10, color=INK,
            family='Georgia', transform=ax.transAxes,
            wrap=True)

    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title('(b)  Forward vs regressive — scroll-velocity asymmetry',
                 fontsize=12, color=INK, family='Georgia', loc='left',
                 pad=10, weight='bold')


def main():
    stats = dict(DEFAULT_STATS)
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.6), facecolor=BG,
                             gridspec_kw={'width_ratios': [0.42, 0.58],
                                          'wspace': 0.06,
                                          'left': 0.04, 'right': 0.985,
                                          'top': 0.91, 'bottom': 0.04})
    draw_serp(axes[0])
    draw_data_panel(axes[1], stats)

    fig.suptitle(
        'Examining behavior on AdSERP — forward sweep, then regressive return',
        fontsize=13, color=INK, family='Georgia', x=0.04, ha='left',
        y=0.985, weight='bold')

    out_png = ROOT / 'scripts/output/figures/task_overview_Y.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
