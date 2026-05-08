"""Option Z — "AdSERP at a glance" for an eye-tracking-researcher audience.

Plain language. Field-standard scanpath notation (numbered fixation circles).
No internal project jargon (no HWM, multi-cycle, anchor return, rank-type
tags, regress-scan-regress).

Two panels:
  (a) Google-style SERP with a sample scanpath — numbered fixation circles,
      cursor trail, one regression labeled in eye-tracking-field language.
  (b) Dataset specs (modalities + sample sizes + citation) and one
      plain-English behavioral takeaway.

Run:
  .venv/bin/python scripts/render_task_overview_Z.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle

ROOT = Path(__file__).resolve().parent.parent

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
GAZE = '#5B3EB8'                 # purple — gaze fixations + path
CURSOR = '#1A6F47'               # green — mouse trail
SCROLL = '#7A5CA0'               # muted purple — scroll annotation
REG = '#B8722C'                  # orange — regression highlight

ORGANIC = '#EAE6DA'              # cell fill — pale warm grey
AD = '#F0D5A8'                   # ad cell tint
CELL_BORDER = '#7E7868'


def draw_serp(ax):
    ax.set_facecolor(BG)
    cells = [
        # (label, etype, height_units)
        (0, 'ad',      1.10),
        (1, 'organic', 1.00),
        (2, 'organic', 1.00),
        (3, 'organic', 1.05),
        (4, 'organic', 0.95),
        (5, 'organic', 1.00),
        (6, 'organic', 1.00),
    ]
    cell_w = 1.6
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
            facecolor=fill, edgecolor=CELL_BORDER, linewidth=0.7,
            zorder=1,
        ))
        if etype == 'ad':
            ax.text(x0 + 0.10, cy + height * 0.30, 'Ad',
                    fontsize=8, color=MUTED, family='Georgia',
                    weight='bold', va='center')
        # Lightly suggest a "title line" inside the cell — single thin stroke,
        # restrained vs the original chartjunk version
        ax.plot([x0 + 0.18, x0 + cell_w - 0.20],
                [cell_top - 0.10, cell_top - 0.10],
                color=INK, linewidth=2.0, alpha=0.35, zorder=2)
        centers.append((x0 + cell_w * 0.40, cy))
        cell_top = bottom - 0.06

    # Right-edge scroll indicator
    scroll_x = x0 + cell_w + 0.15
    top_y = 0.05
    bot_y = cell_top + 0.06
    ax.plot([scroll_x, scroll_x], [top_y, bot_y], color=SCROLL,
            linewidth=2.0, alpha=0.8, solid_capstyle='round')
    ax.text(scroll_x + 0.06, (top_y + bot_y) / 2, 'scroll',
            fontsize=9, color=SCROLL, family='Georgia',
            style='italic', va='center', ha='left', rotation=90)

    # ── Sample scanpath: 6 numbered fixations, one regression ──
    # Fixations 1-4 descend through results, 5 regresses to position 2, 6 commits at position 2
    fixation_seq = [
        (1, centers[1], '1'),    # rank 1
        (2, centers[2], '2'),    # rank 2
        (3, centers[3], '3'),    # rank 3
        (4, centers[4], '4'),    # rank 4 (deepest reached)
        (5, centers[2], '5'),    # regression to rank 2
    ]
    # Cursor trail (mouse) — slightly offset to the right of gaze
    cursor_pts = [(c[0] + 0.55, c[1] + 0.05) for _, c, _ in fixation_seq]
    cx = [p[0] for p in cursor_pts]
    cy = [p[1] for p in cursor_pts]
    ax.plot(cx, cy, color=CURSOR, linewidth=1.0, linestyle=(0, (1.5, 1.8)),
            alpha=0.7, zorder=3)

    # Saccade lines (gaze path) — thin connecting segments
    pts = [c for _, c, _ in fixation_seq]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    # First 4 are forward saccades (rank 1→2→3→4)
    for i in range(3):
        ax.annotate('', xy=pts[i + 1], xytext=pts[i],
                    arrowprops=dict(arrowstyle='-', color=GAZE,
                                    linewidth=1.2, alpha=0.65),
                    zorder=3)
    # Saccade 4→5 is the regression — distinct color + thicker
    ax.annotate('', xy=pts[4], xytext=pts[3],
                arrowprops=dict(arrowstyle='-', color=REG,
                                linewidth=2.0,
                                connectionstyle='arc3,rad=-0.40'),
                zorder=4)

    # Numbered fixation circles
    for n, (x, y) in [(num, pt) for num, pt, _ in fixation_seq]:
        # The 5th fixation is on the same cell as fixation 2 — offset slightly
        is_regression_target = (n == 5)
        if is_regression_target:
            x_draw = x + 0.18; y_draw = y - 0.10
        else:
            x_draw, y_draw = x, y
        ax.add_patch(Circle((x_draw, y_draw), 0.16,
                            facecolor=GAZE if not is_regression_target else REG,
                            edgecolor='white', linewidth=1.5, zorder=5))
        ax.text(x_draw, y_draw, str(n), ha='center', va='center',
                fontsize=10, color='white', family='Georgia',
                weight='bold', zorder=6)

    # Annotations using field-standard terms
    ax.annotate(
        'forward scan',
        xy=(centers[2][0] - 0.30, centers[2][1]),
        xytext=(-0.85, centers[1][1] - 0.10),
        fontsize=10, color=GAZE, family='Georgia', weight='bold',
        arrowprops=dict(arrowstyle='-', color=GAZE, linewidth=0.8, alpha=0.6),
    )
    ax.annotate(
        'regression',
        xy=(pts[4][0] - 0.10, (pts[3][1] + pts[4][1]) / 2),
        xytext=(-0.95, (pts[3][1] + pts[4][1]) / 2),
        fontsize=10, color=REG, family='Georgia', weight='bold',
        arrowprops=dict(arrowstyle='-', color=REG, linewidth=0.8, alpha=0.6),
    )
    # Cursor trail label
    ax.text(cx[-1] + 0.20, cy[-1], 'cursor trail',
            fontsize=9, color=CURSOR, family='Georgia',
            style='italic', va='center')

    ax.set_xlim(-1.10, cell_w + 0.85)
    ax.set_ylim(cell_top - 0.10, 0.30)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title('(a)  A typical AdSERP trial — scanpath + cursor + scroll',
                 fontsize=12, color=INK, family='Georgia', loc='left',
                 pad=10, weight='bold')


def draw_specs_panel(ax):
    ax.set_facecolor(BG)

    # Title block
    ax.text(0.04, 0.94, 'AdSERP at a glance',
            fontsize=15, color=INK, family='Georgia', weight='bold',
            transform=ax.transAxes)
    ax.text(0.04, 0.885,
            'A re-analyzable eye-tracking dataset of real Web search behavior',
            fontsize=10.5, color=MUTED, family='Georgia', style='italic',
            transform=ax.transAxes)

    # Rule under title
    ax.plot([0.04, 0.96], [0.86, 0.86], color=RULE, linewidth=0.8,
            transform=ax.transAxes)

    # Specs block — two columns
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

    # Rule
    ax.plot([0.04, 0.96], [y + 0.02, y + 0.02], color=RULE, linewidth=0.8,
            transform=ax.transAxes)

    # Hero stat — one plain-English takeaway
    ax.text(0.50, y - 0.04, 'Behavioral takeaway',
            fontsize=11, color=MUTED, family='Georgia',
            style='italic', ha='center', va='top',
            transform=ax.transAxes)
    ax.text(0.50, y - 0.10,
            '62%',
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
                                          'left': 0.04, 'right': 0.985,
                                          'top': 0.93, 'bottom': 0.06})
    draw_serp(axes[0])
    draw_specs_panel(axes[1])

    out_png = ROOT / 'scripts/output/figures/task_overview_Z.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
