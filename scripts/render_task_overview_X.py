"""Option X — single-panel data-first task overview.

Drops the SERP schematic. Single strong data panel: forward vs regressive
scroll velocity, violins by depth bin. Headline contrast carried by one
large annotation. Three compact stat anchors as a footer strip.

Run:
  .venv/bin/python scripts/render_task_overview_X.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    get_trial_ids, load_mouse_events, get_trial_meta,
)

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
FWD = '#5B3EB8'
REG = '#B8722C'


def collect():
    rows = []
    n_trials = 0
    for tid in get_trial_ids():
        try:
            _all, scrolls, _clicks = load_mouse_events(tid)
        except Exception:
            continue
        if not scrolls or len(scrolls) < 2:
            continue
        meta = get_trial_meta(tid)
        if meta is None or not meta[0]:
            continue
        doc_h = meta[0]
        n_trials += 1
        for (t1, y1), (t2, y2) in zip(scrolls[:-1], scrolls[1:]):
            dt = t2 - t1
            if dt <= 0: continue
            dy = y2 - y1
            if dy == 0: continue
            speed = abs(dy) / dt * 1000.0
            direction = 'forward' if dy > 0 else 'regressive'
            frac = y1 / max(doc_h, 1)
            rows.append({'speed': speed, 'direction': direction, 'frac': frac})
    return rows, n_trials


def depth(frac):
    if frac < 0.20: return 'top'
    if frac < 0.50: return 'mid'
    return 'deep'


def main():
    rows, n_trials = collect()
    print(f'  {n_trials:,} trials  ·  {len(rows):,} scroll events', file=sys.stderr)

    bins = ['top', 'mid', 'deep']
    bin_long = {'top': 'top of page', 'mid': 'mid page', 'deep': 'deep page'}

    # Pull medians
    med = {}
    for b in bins:
        for d in ('forward', 'regressive'):
            vals = [r['speed'] for r in rows if depth(r['frac']) == b and r['direction'] == d]
            med[(b, d)] = (float(np.median(vals)) if vals else float('nan'),
                           len(vals))

    # ── render ──
    fig, ax = plt.subplots(figsize=(11.5, 6.0), facecolor=BG,
                           gridspec_kw={'left': 0.07, 'right': 0.97,
                                        'top': 0.83, 'bottom': 0.18})
    ax.set_facecolor(BG)

    width = 0.36
    for ci, b in enumerate(bins):
        for di, d in enumerate(('forward', 'regressive')):
            xs = ci + (di * width - width / 2)
            vals = np.asarray([r['speed'] for r in rows
                               if depth(r['frac']) == b and r['direction'] == d])
            if len(vals) == 0: continue
            color = FWD if d == 'forward' else REG
            clip = float(np.percentile(vals, 98))
            vp = ax.violinplot([vals[vals <= clip]], positions=[xs], widths=width * 0.85,
                               showmeans=False, showmedians=False, showextrema=False)
            for body in vp['bodies']:
                body.set_facecolor(color); body.set_alpha(0.55)
                body.set_edgecolor(color); body.set_linewidth(0.7)
            m = float(np.median(vals)); n = len(vals)
            ax.plot([xs - width * 0.30, xs + width * 0.30], [m, m],
                    color='white', linewidth=2.4, zorder=4)
            ax.plot([xs - width * 0.20, xs + width * 0.20], [m, m],
                    color=color, linewidth=2.4, zorder=5)
            ax.text(xs, m + 60, f'{int(m):,}', ha='center', va='bottom',
                    fontsize=10, color=color, family='Georgia', weight='bold')
            ax.text(xs, -250, f'n = {n:,}', ha='center', va='top',
                    fontsize=8, color=MUTED, family='Georgia', style='italic')

    # Bin labels under groups
    for ci, b in enumerate(bins):
        ax.text(ci, -480, bin_long[b], ha='center', va='top',
                fontsize=11, color=INK, family='Georgia', weight='bold')

    # Headline: +Δ on the mid-page bin (the most populated bin)
    fwd_mid, _ = med[('mid', 'forward')]
    reg_mid, _ = med[('mid', 'regressive')]
    delta_pct = 100 * (reg_mid - fwd_mid) / fwd_mid
    # Annotation arc spanning mid-bin pair
    arc_y = max(fwd_mid, reg_mid) + 1500
    ax.annotate(
        '', xy=(1 + width / 2, arc_y), xytext=(1 - width / 2, arc_y),
        arrowprops=dict(arrowstyle='-', linewidth=1.4, color=INK,
                        connectionstyle='arc3,rad=-0.35'),
        zorder=2,
    )
    ax.text(1, arc_y + 1100, f'+{delta_pct:.0f}%',
            ha='center', va='bottom', fontsize=20, color=REG,
            family='Georgia', weight='bold')
    ax.text(1, arc_y + 700,
            'regressive faster than forward',
            ha='center', va='bottom', fontsize=9.5, color=MUTED,
            family='Georgia', style='italic')

    # Style
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(-650, 6500)
    ax.set_xticks([])
    ax.set_ylabel('scroll speed (px / second)', fontsize=11.5, color=INK,
                  family='Georgia')
    ax.tick_params(colors=INK, labelsize=10)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(MUTED); ax.spines[s].set_linewidth(0.8)
    ax.spines['bottom'].set_visible(False)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)

    # Legend (compact, top-right)
    ax.legend(handles=[
        patches.Patch(facecolor=FWD, alpha=0.55, edgecolor=FWD,
                      label='forward scroll (page-down)'),
        patches.Patch(facecolor=REG, alpha=0.55, edgecolor=REG,
                      label='regressive scroll (page-up)'),
    ], loc='upper right', fontsize=10, frameon=False,
        labelcolor=INK, ncol=1)

    # Suptitle (paper-style)
    fig.suptitle(
        'Regressive scroll moves faster than forward scroll across page depth.',
        fontsize=13, color=INK, family='Georgia', x=0.07, ha='left',
        y=0.96, weight='bold')

    # Footer strip — three compact stat anchors
    fig.text(0.07, 0.07,
             '62% of trials (1,686 / 2,701) have ≥ 1 regress-scan-regress cycle  '
             '·  regression-episode tension rises sharply past HWM = 8 (1–3 → 5–9 ranks)  '
             '·  signal lives in the mouse-events stream (rank-type-N/A)',
             fontsize=9, color=MUTED, family='Georgia', style='italic')

    out_png = ROOT / 'scripts/output/figures/task_overview_X.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
