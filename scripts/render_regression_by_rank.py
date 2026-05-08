"""Paired-bar histogram of regression frequency by absolute organic rank.

Companion to render_regressive_arcs.py and render_regressive_relative.py.
Where the arc graph shows the full (source, target) pair structure and the
relative graph shows depth distribution, this view shows the marginals at
each absolute rank: how often each rank is a return target vs how often it
is a regression source (HWM).

Reads the JSON summary produced by render_regressive_arcs.py.
Output: scripts/output/figures/regression_by_rank_<flavor>.{png,pdf}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'scripts' / 'output' / 'figures'

ACCENT = '#5B3EB8'
ACCENT2 = '#26A69A'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
BG = '#FAFAF8'


def render(summary_json: Path, out_png: Path, max_rank: int = 10):
    with summary_json.open() as f:
        d = json.load(f)

    all_ranks = sorted({int(k) for k in (*d['returns_by_target'], *d['sources_by_hwm'])})
    ranks = [r for r in all_ranks if r <= max_rank]
    dropped = [r for r in all_ranks if r > max_rank]
    target_counts = [d['returns_by_target'].get(str(r), {'count': 0})['count'] for r in ranks]
    source_counts = [d['sources_by_hwm'].get(str(r), {'count': 0})['count'] for r in ranks]
    dropped_target = sum(d['returns_by_target'].get(str(r), {'count': 0})['count'] for r in dropped)
    dropped_source = sum(d['sources_by_hwm'].get(str(r), {'count': 0})['count'] for r in dropped)
    n_total = d['n_total_jumps']

    x = np.arange(len(ranks))
    w = 0.40

    fig, ax = plt.subplots(figsize=(11, 4.5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.bar(x - w/2, target_counts, w, label='returns to this rank (target)',
           color=ACCENT, edgecolor=INK, linewidth=0.5)
    ax.bar(x + w/2, source_counts, w, label='regressions originating from here (source HWM)',
           color=ACCENT2, edgecolor=INK, linewidth=0.5)

    for r, c in zip(ranks, target_counts):
        if c > n_total * 0.05:
            ax.text(ranks.index(r) - w/2, c + n_total*0.008, f'{100*c/n_total:.0f}%',
                    ha='center', va='bottom', fontsize=9, color=ACCENT, family='Georgia')
    for r, c in zip(ranks, source_counts):
        if c > n_total * 0.08:
            ax.text(ranks.index(r) + w/2, c + n_total*0.008, f'{100*c/n_total:.0f}%',
                    ha='center', va='bottom', fontsize=9, color=ACCENT2, family='Georgia')

    ax.set_xlabel('organic rank', fontsize=11, family='Georgia',
                  color=MUTED, style='italic')
    ax.set_ylabel(f'jumps (n; total = {n_total:,})', fontsize=11,
                  family='Georgia', color=MUTED)
    ax.set_title(f'Regression frequency by organic rank — {d["attribution"]} flavor, '
                 f'{n_total:,} jumps across {d["n_trials_with_jumps"]:,} trials',
                 fontsize=11.5, family='Georgia', color=INK, pad=12)
    ax.set_xticks(x); ax.set_xticklabels(ranks)
    if dropped:
        tail_t = 100 * dropped_target / n_total
        tail_s = 100 * dropped_source / n_total
        ax.text(0.99, 0.78,
                f'tail (rank > {max_rank}, {len(dropped)} ranks omitted):  '
                f'{dropped_target:,} returns ({tail_t:.1f}%)  ·  {dropped_source:,} sources ({tail_s:.1f}%)',
                ha='right', va='top', transform=ax.transAxes, fontsize=8.5,
                color=MUTED, family='Georgia', style='italic')
    ax.legend(loc='upper right', framealpha=0.95, prop={'family': 'Georgia', 'size': 9})
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(RULE); ax.spines['bottom'].set_color(RULE)
    ax.tick_params(colors=MUTED)
    ax.grid(axis='y', alpha=0.18, linewidth=0.6)

    plt.tight_layout()
    plt.savefig(out_png, dpi=160, bbox_inches='tight', facecolor=BG)
    plt.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'], default='organic')
    ap.add_argument('--max-rank', type=int, default=10,
                    help='cap the rank axis at this value; deeper ranks summarised in a tail note')
    args = ap.parse_args()
    summary = OUT_DIR / f'regressive_arcs_{args.attribution}_summary.json'
    out = OUT_DIR / f'regression_by_rank_{args.attribution}.png'
    render(summary, out, max_rank=args.max_rank)


if __name__ == '__main__':
    main()
