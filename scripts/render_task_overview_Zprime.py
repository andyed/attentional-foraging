"""Z'-scanpath — focused scanpath schematic + dataset specs.

What changed vs Z (per muriel critique):
  - Cell count reduced (5 instead of 7) — less for the eye to track
  - Fixation count reduced (4 instead of 5) — clearer sequence
  - Numbered fixation circles enlarged (~ 24 pt visual diameter)
  - Gaze path: bold solid for forward saccades, thick orange dashed for the regression
  - Regression label sits ON the arc, not in the margin
  - Cell rank labels visible (left margin) so the regression target is
    unambiguous
  - Cursor trail and scroll indicator removed from the visual; mentioned
    in the caption-style suptitle instead
  - Inner cell title-strokes removed (chartjunk)

Run:
  .venv/bin/python scripts/render_task_overview_Zprime.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

ROOT = Path(__file__).resolve().parent.parent

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
GAZE = '#5B3EB8'                 # purple — gaze fixations + forward path
REG = '#B8722C'                  # orange — regression

ORGANIC = '#EAE6DA'
AD = '#F0D5A8'
CELL_BORDER = '#7E7868'


def draw_serp(ax):
    ax.set_facecolor(BG)
    cells = [
        # (rank, etype, height_units)
        (0, 'ad',      1.10),
        (1, 'organic', 1.00),
        (2, 'organic', 1.00),
        (3, 'organic', 1.00),
        (4, 'organic', 1.00),
    ]
    cell_w = 1.8
    x0 = 0.0
    cell_top = 0.0
    centers = []
    for rank, etype, h_units in cells:
        height = h_units * 0.92
        bottom = cell_top - height
        cy = (cell_top + bottom) / 2
        fill = AD if etype == 'ad' else ORGANIC
        ax.add_patch(Rectangle(
            (x0, bottom), cell_w, height,
            facecolor=fill, edgecolor=CELL_BORDER, linewidth=0.7,
            zorder=1,
        ))
        # Rank label, prominent on the left margin
        ax.text(x0 - 0.18, cy, f'rank {rank}', ha='right', va='center',
                fontsize=10, color=MUTED, family='Georgia',
                weight='bold' if etype == 'ad' else 'normal')
        if etype == 'ad':
            ax.text(x0 + 0.10, cell_top - 0.10, 'Ad',
                    fontsize=9, color=MUTED, family='Georgia',
                    weight='bold', va='top')
        centers.append((x0 + cell_w * 0.55, cy))
        cell_top = bottom - 0.08

    # ── Sample scanpath: 1, 2, 3, 4 forward; 5 regresses to rank 2 ──
    fixations = [
        (1, centers[1]),    # rank 1
        (2, centers[2]),    # rank 2
        (3, centers[3]),    # rank 3
        (4, centers[4]),    # rank 4 (deepest)
        (5, centers[2]),    # regression → rank 2
    ]

    # Forward saccades (1→2→3→4): bold solid purple lines
    fwd_pts = [fixations[i][1] for i in range(4)]
    fwd_xs = [p[0] for p in fwd_pts]
    fwd_ys = [p[1] for p in fwd_pts]
    ax.plot(fwd_xs, fwd_ys, color=GAZE, linewidth=3.0, zorder=3,
            solid_capstyle='round', alpha=0.85)

    # Regression saccade (4 → 5): thick orange dashed arc with arrowhead,
    # sweeping outward to the right of the cells, label sits ON the arc
    src = fwd_pts[3]
    tgt = (fixations[4][1][0] + 0.50, fixations[4][1][1] - 0.08)
    # Use FancyArrowPatch for the arc
    from matplotlib.patches import FancyArrowPatch
    arc = FancyArrowPatch(
        (src[0] + 0.30, src[1]), tgt,
        arrowstyle='-|>', mutation_scale=22,
        color=REG, linewidth=3.0, linestyle=(0, (5, 2.5)),
        connectionstyle='arc3,rad=0.65', zorder=4,
    )
    ax.add_patch(arc)
    # Label ON the arc — find approximate midpoint
    mid_x = (src[0] + tgt[0]) / 2 + 1.00
    mid_y = (src[1] + tgt[1]) / 2
    ax.text(mid_x, mid_y, 'regression', fontsize=11, color=REG,
            family='Georgia', weight='bold', ha='left', va='center')

    # Numbered fixation circles — enlarged
    for n, (x, y) in fixations:
        is_regression = (n == 5)
        if is_regression:
            x_draw, y_draw = tgt
            face = REG
        else:
            x_draw, y_draw = x, y
            face = GAZE
        ax.add_patch(Circle((x_draw, y_draw), 0.22,
                            facecolor=face, edgecolor='white',
                            linewidth=2.0, zorder=5))
        ax.text(x_draw, y_draw, str(n), ha='center', va='center',
                fontsize=12.5, color='white', family='Georgia',
                weight='bold', zorder=6)

    # Layout
    ax.set_xlim(-0.85, cell_w + 2.20)
    ax.set_ylim(cell_top - 0.10, 0.30)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title('(a)  An example AdSERP scanpath',
                 fontsize=12, color=INK, family='Georgia', loc='left',
                 pad=10, weight='bold')


def draw_specs_panel(ax):
    ax.set_facecolor(BG)
    ax.text(0.04, 0.94, 'AdSERP at a glance',
            fontsize=15, color=INK, family='Georgia', weight='bold',
            transform=ax.transAxes)
    ax.text(0.04, 0.885,
            'A re-analyzable eye-tracking dataset of real Web search behavior',
            fontsize=10.5, color=MUTED, family='Georgia', style='italic',
            transform=ax.transAxes)
    ax.plot([0.04, 0.96], [0.86, 0.86], color=RULE, linewidth=0.8,
            transform=ax.transAxes)
    specs = [
        ('Trials', '2,776'),
        ('Participants', '47'),
        ('Queries', '60 transactional product searches'),
        ('Eye tracker', 'Gazepoint GP3 HD, 150 Hz'),
        ('Other channels', 'mouse cursor, scroll, full-page screenshots, ad bounding boxes'),
        ('Reference', 'Latifzadeh, Gwizdka & Leiva (SIGIR 2025)'),
    ]
    y = 0.78
    for label, value in specs:
        ax.text(0.04, y, label, fontsize=10, color=MUTED,
                family='Georgia', va='top', transform=ax.transAxes)
        ax.text(0.30, y, value, fontsize=10.5, color=INK,
                family='Georgia', va='top', weight='bold',
                transform=ax.transAxes)
        y -= 0.062
    ax.plot([0.04, 0.96], [y + 0.02, y + 0.02], color=RULE, linewidth=0.8,
            transform=ax.transAxes)
    ax.text(0.50, y - 0.04, 'Behavioral takeaway',
            fontsize=11, color=MUTED, family='Georgia',
            style='italic', ha='center', va='top',
            transform=ax.transAxes)
    ax.text(0.50, y - 0.10, '62%',
            fontsize=44, color=GAZE, family='Georgia', weight='bold',
            ha='center', va='top', transform=ax.transAxes)
    ax.text(0.50, y - 0.28,
            'of trials show participants returning\n'
            'to an earlier result before clicking.',
            fontsize=11, color=INK, family='Georgia',
            ha='center', va='top', transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), facecolor=BG,
                             gridspec_kw={'width_ratios': [0.55, 0.45],
                                          'wspace': 0.06,
                                          'left': 0.05, 'right': 0.985,
                                          'top': 0.91, 'bottom': 0.07})
    draw_serp(axes[0])
    draw_specs_panel(axes[1])

    # Caption-style suptitle — mentions modalities not visualized
    fig.suptitle(
        'Examining behavior on AdSERP — gaze + concurrent mouse cursor and scroll captured;  '
        'scanpath shown.',
        fontsize=12.5, color=INK, family='Georgia', x=0.05, ha='left',
        y=0.98, weight='bold')

    out_png = ROOT / 'scripts/output/figures/task_overview_Zprime.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
