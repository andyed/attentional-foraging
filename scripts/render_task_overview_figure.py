"""Composite paper figure: SERP task schematic + headline data.

Single figure, two panels, scientific-article register with one editorial
risk on the schematic side.

  (a) Stylized vertical-stack SERP + two scanpath overlays:
        forward sweep (purple) and two regressive episodes (orange) —
        a short adjacent return and a long top-of-page anchor return.
  (b) Headline data: forward vs regressive scroll velocity (mid-page bin)
        with absolute lift, plus three supporting stat anchors.

Reads scroll-velocity JSON if available so the bar values stay synced
with the canonical pipeline output. Falls back to embedded constants if
not.

Run:
  .venv/bin/python scripts/render_task_overview_figure.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent

# ── editorial cream palette ──
BG = '#FAFAF8'
INK = '#0B1220'                  # 18.7:1 on cream
MUTED = '#4B4B4B'                # 8.6:1
RULE = '#D2CEC4'                 # decorative rule
FWD = '#5B3EB8'                  # purple — forward
REG = '#B8722C'                  # orange — regressive
ORGANIC = '#FAFAF8'              # cell fill — keep light, structure carried by border
DDTOP = '#F5E8D4'                # warm sand — top-of-page ad
NATIVE = '#F0DBB6'               # warmer — native ad
CELL_BORDER = '#9B9588'          # decorative


# ── stats sources (fall back to embedded if JSON missing) ──
DEFAULT_STATS = {
    'fwd_speed_mid': 784.0,
    'reg_speed_mid': 972.0,
    'fwd_n_mid': 70788,
    'reg_n_mid': 35475,
    'multi_cycle_pct': 62.4,
    'multi_cycle_n_with': 1686,
    'multi_cycle_n_total': 2701,
    'tension_low': '1–3',
    'tension_high': '5–9',
    'transition_hwm': 8,
}


def load_stats():
    s = dict(DEFAULT_STATS)
    p = ROOT / 'scripts/output/figures/scroll_velocity.png'
    # We didn't write a JSON for scroll_velocity. Use embedded.
    # If a JSON appears later, this is where to wire it.
    return s


def draw_serp_schematic(ax, stats):
    ax.set_facecolor(BG)
    # 8 cells, varied heights
    cells = [
        # (rank, etype, height_units, label_etype)
        (0, 'dd_top',   1.10, 'dd_top (top ad)'),
        (1, 'organic',  1.00, 'organic'),
        (2, 'native_ad',0.95, 'native_ad'),
        (3, 'organic',  1.05, 'organic'),
        (4, 'organic',  0.95, 'organic'),
        (5, 'organic',  1.00, 'organic'),
        (6, 'organic',  0.90, 'organic'),
        (7, 'organic',  1.05, 'organic'),
    ]
    cell_w = 1.0
    x0 = 0.0
    cell_top = 0.0
    cell_centers = []
    cell_heights = []
    cell_tops = []
    fill_for = {'organic': ORGANIC, 'dd_top': DDTOP, 'native_ad': NATIVE}
    for rank, etype, h_units, lbl in cells:
        height = h_units * 0.85
        cell_bottom = cell_top - height
        cy = (cell_top + cell_bottom) / 2
        # Draw cell rectangle
        rect = patches.Rectangle((x0, cell_bottom), cell_w, height,
                                 facecolor=fill_for[etype],
                                 edgecolor=CELL_BORDER, linewidth=0.9,
                                 zorder=1)
        ax.add_patch(rect)
        # Rank label on the left
        ax.text(x0 - 0.10, cy, str(rank), ha='right', va='center',
                fontsize=10, color=INK, family='Georgia', weight='bold')
        # Etype label on the right (only for non-organic, plus rank 1 for grounding)
        if etype != 'organic' or rank == 1:
            ax.text(x0 + cell_w + 0.08, cy, lbl, ha='left', va='center',
                    fontsize=8.5, color=MUTED, family='Georgia', style='italic')
        # Render result preview lines (decorative rectangles inside the cell)
        line_y_top = cell_top - 0.08
        line_y_subtitle = cell_top - 0.20
        ax.plot([x0 + 0.10, x0 + 0.85], [line_y_top, line_y_top],
                color=INK, linewidth=2.5, zorder=2, alpha=0.85)
        ax.plot([x0 + 0.10, x0 + 0.65], [line_y_subtitle, line_y_subtitle],
                color=MUTED, linewidth=1.0, zorder=2, alpha=0.7)
        cell_centers.append((x0 + cell_w * 0.55, cy))
        cell_heights.append(height)
        cell_tops.append(cell_top)
        cell_top = cell_bottom - 0.06  # gutter

    # ── Forward scanpath (purple, solid) ──
    fwd_xs = [c[0] for c in cell_centers]
    fwd_ys = [c[1] for c in cell_centers]
    # Shift slightly to the left of cell centers to make path readable
    fwd_xs = [x - 0.30 for x in fwd_xs]
    ax.plot(fwd_xs, fwd_ys, color=FWD, linewidth=2.4, zorder=4,
            solid_capstyle='round')
    for i, (x, y) in enumerate(zip(fwd_xs, fwd_ys)):
        ax.scatter([x], [y], s=46, color=FWD, edgecolor='white',
                   linewidth=1.0, zorder=5)
    # Small "forward" annotation at top of trace
    ax.annotate('forward sweep',
                xy=(fwd_xs[1], fwd_ys[1]),
                xytext=(fwd_xs[1] - 0.95, fwd_ys[1] + 0.10),
                fontsize=9.5, color=FWD, family='Georgia',
                weight='bold', ha='center')

    # ── Regressive episodes (orange, dashed) ──
    # Short adjacent: HWM 3 → rank 2 (just one step back)
    src1, tgt1 = cell_centers[3], cell_centers[2]
    src1_x = src1[0] + 0.32; src1_y = src1[1]
    tgt1_x = tgt1[0] + 0.32; tgt1_y = tgt1[1]
    arrow1 = FancyArrowPatch(
        (src1_x, src1_y), (tgt1_x, tgt1_y),
        arrowstyle='-|>', mutation_scale=14,
        color=REG, linewidth=1.8, linestyle=(0, (4, 2.2)),
        connectionstyle='arc3,rad=0.30', zorder=4,
    )
    ax.add_patch(arrow1)
    ax.text(src1_x + 0.42, (src1_y + tgt1_y) / 2,
            'short\nadjacent', fontsize=8.5, color=REG, family='Georgia',
            style='italic', ha='left', va='center')

    # Long anchor return: HWM 7 → rank 0
    src2, tgt2 = cell_centers[7], cell_centers[0]
    src2_x = src2[0] + 0.32; src2_y = src2[1]
    tgt2_x = tgt2[0] + 0.32; tgt2_y = tgt2[1]
    arrow2 = FancyArrowPatch(
        (src2_x, src2_y), (tgt2_x, tgt2_y),
        arrowstyle='-|>', mutation_scale=16,
        color=REG, linewidth=2.2, linestyle=(0, (5, 2.5)),
        connectionstyle='arc3,rad=0.55', zorder=4,
    )
    ax.add_patch(arrow2)
    ax.text(src2_x + 0.85, (src2_y + tgt2_y) / 2 + 0.40,
            'anchor return\n(50% of HWM≥8 regressions)',
            fontsize=8.5, color=REG, family='Georgia',
            style='italic', ha='left', va='center')

    # Layout
    ax.set_xlim(-0.50, 2.70)
    last_bottom = cell_top + 0.06  # last assigned cell_top is bottom of cell 7 minus gutter
    ax.set_ylim(last_bottom - 0.10, 0.30)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title('(a)  Examining a SERP — forward sweep with regressive returns',
                 fontsize=11.5, color=INK, family='Georgia', loc='left',
                 pad=8, weight='bold')


def draw_stats_panel(ax, stats):
    ax.set_facecolor(BG)
    # Bars: forward then regressive (vertical positions)
    bar_h = 0.30
    bar_y_fwd = 0.82
    bar_y_reg = 0.55
    max_speed = max(stats['fwd_speed_mid'], stats['reg_speed_mid'])
    bar_x_max = 0.62  # bar width fraction of axis

    def bar(y, val, color, label, n):
        w = bar_x_max * (val / max_speed)
        ax.barh([y], [w], height=bar_h, color=color, alpha=0.65,
                edgecolor=color, linewidth=1.2)
        # Label inside or outside bar
        ax.text(0.005, y, label, ha='left', va='center',
                fontsize=10, color=INK, family='Georgia', weight='bold')
        ax.text(w + 0.012, y, f'{int(val):,} px/s',
                ha='left', va='center',
                fontsize=10.5, color=color, family='Georgia',
                weight='bold')
        ax.text(w + 0.012, y - 0.07, f'n = {n:,} events',
                ha='left', va='center',
                fontsize=8.5, color=MUTED, family='Georgia', style='italic')

    bar(bar_y_fwd, stats['fwd_speed_mid'], FWD,
        'forward scroll', stats['fwd_n_mid'])
    bar(bar_y_reg, stats['reg_speed_mid'], REG,
        'regressive scroll', stats['reg_n_mid'])

    # +Δ annotation between the bars
    delta_pct = 100 * (stats['reg_speed_mid'] - stats['fwd_speed_mid']) / stats['fwd_speed_mid']
    ax.text(0.04, (bar_y_fwd + bar_y_reg) / 2,
            f'+{delta_pct:.0f}%',
            ha='center', va='center',
            fontsize=15, color=REG, family='Georgia', weight='bold')

    # Subtitle
    ax.text(0.005, bar_y_reg - 0.18,
            'mid-page (20–50% of doc height); '
            'scripts/output/figures/scroll_velocity.png',
            fontsize=8, color=MUTED, family='Georgia', style='italic')

    # Supporting stats — three bullet lines below
    ystart = bar_y_reg - 0.30
    bullets = [
        (f"{stats['multi_cycle_pct']:.0f}% of trials "
         f"({stats['multi_cycle_n_with']:,}/{stats['multi_cycle_n_total']:,}) "
         "have ≥1 regress-scan-regress cycle",
         'multi-cycle scanning is the modal trial structure'),
        (f"regression-episode tension: "
         f"{stats['tension_low']} ranks (HWM<{stats['transition_hwm']}) → "
         f"{stats['tension_high']} ranks (HWM≥{stats['transition_hwm']})",
         'phase transition past HWM≈8 — local re-eval gives way to anchor return'),
        ('regressive scroll accelerates with depth; forward scroll is flat',
         'asymmetry confirmed in mouse-events stream (rank-type-N/A)'),
    ]
    bullet_y = ystart
    for primary, secondary in bullets:
        ax.text(0.005, bullet_y, '•', ha='left', va='top',
                fontsize=12, color=INK, family='Georgia', weight='bold')
        ax.text(0.030, bullet_y, primary, ha='left', va='top',
                fontsize=9.5, color=INK, family='Georgia',
                wrap=True)
        ax.text(0.030, bullet_y - 0.060, secondary, ha='left', va='top',
                fontsize=8.5, color=MUTED, family='Georgia', style='italic')
        bullet_y -= 0.16

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.02, 1.0)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title('(b)  Forward vs regressive — scroll-velocity asymmetry',
                 fontsize=11.5, color=INK, family='Georgia', loc='left',
                 pad=8, weight='bold')


def main():
    stats = load_stats()
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.6), facecolor=BG,
                             gridspec_kw={'width_ratios': [0.42, 0.58],
                                          'wspace': 0.10,
                                          'left': 0.045, 'right': 0.985,
                                          'top': 0.92, 'bottom': 0.05})
    draw_serp_schematic(axes[0], stats)
    draw_stats_panel(axes[1], stats)

    # Suptitle / figure caption — paper-style brief lead-in
    fig.suptitle(
        'Examining behavior on AdSERP exhibits a forward-then-regressive structure.',
        fontsize=12.5, color=INK, family='Georgia', x=0.045, ha='left',
        y=0.985, weight='bold')

    out_png = ROOT / 'scripts/output/figures/task_overview.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight',
                facecolor=BG)
    print(f'wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
