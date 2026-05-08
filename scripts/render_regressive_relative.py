"""Sister graphic to render_regressive_arcs.py.

Same horizontal-bar-with-arcs visual vocabulary as `render_regressive_arcs.py`,
but plotted on a *relative* rank axis. Forward gaze advances rank exhaustively;
the X-axis here is regression depth (target rank − source HWM), always
non-positive. All arcs originate at 0 (the high-water mark, normalized) and
fan leftward to the depth they regressed to.

Output: scripts/output/figures/regressive_relative_<flavor>.{png,pdf,json}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    DATA_DIR, get_trial_ids, load_fixations, get_trial_meta,
    organic_aoi_tops, organic_aoi_bands, assign_fixation_to_position,
)

_AD_DIR = DATA_DIR / 'ad-boundary-data'
_RESULT_COL_X_MIN = 50
_RESULT_COL_X_MAX = 750


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
                if not (rx < _RESULT_COL_X_MAX and (rx + rw) > _RESULT_COL_X_MIN):
                    continue
                items.append((ry, ry + rh, etype))
    if not items:
        return []
    items.sort(key=lambda r: r[0])
    return [r[0] for r in items]


OUT_DIR = ROOT / 'scripts' / 'output' / 'figures'

# Match render_regressive_arcs.py palette
ACCENT = '#5B3EB8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
BG = '#FAFAF8'


def collect_relative_deltas(attribution='organic'):
    """Tally regression-depth deltas (target - source). Negative."""
    delta_counts = Counter()
    n_trials_total = 0
    n_trials_with_jumps = 0
    n_total_jumps = 0

    for tid in get_trial_ids():
        n_trials_total += 1
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        tops = _hybrid_aoi_tops(tid) if attribution == 'hybrid' else organic_aoi_tops(tid)
        n_res = len(tops)
        if not tops or n_res == 0:
            continue

        pos_seq = [assign_fixation_to_position(f['y'], tops, n_res) for f in fix]
        pos_seq = [p for p in pos_seq if p is not None and p >= 0]

        visited = set()
        max_seen = -1
        had_jump = False
        for p in pos_seq:
            if p in visited and p < max_seen:
                delta_counts[p - max_seen] += 1
                n_total_jumps += 1
                had_jump = True
            visited.add(p)
            if p > max_seen:
                max_seen = p
        if had_jump:
            n_trials_with_jumps += 1

    return delta_counts, n_trials_total, n_trials_with_jumps, n_total_jumps


def render_arcs_relative(delta_counts, n_trials, n_with_jumps, n_jumps,
                         attribution, out_png, min_pct=0.5):
    if not delta_counts:
        return
    deltas = sorted(delta_counts.keys())                  # most negative first
    counts_full = np.array([delta_counts[d] for d in deltas])
    pcts_full = 100 * counts_full / n_jumps

    # Trim < min_pct to a tail-note
    keep = pcts_full >= min_pct
    deltas = [d for d, k in zip(deltas, keep) if k]
    counts = counts_full[keep]
    pcts = pcts_full[keep]
    tail_pct = 100 - pcts.sum()
    tail_n = int(counts_full.sum() - counts.sum())

    # Domain: from min_delta..0
    min_d = min(deltas)
    positions = list(range(min_d, 1))  # min_d..0 inclusive

    fig, ax = plt.subplots(figsize=(13.5, 5.6), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(min_d - 0.6, 0.6)
    max_gap_half = abs(min_d) / 2
    ax.set_ylim(-max_gap_half * 0.22, max_gap_half * 1.10)
    ax.set_aspect('equal')

    # Baseline
    ax.axhline(0, color=RULE, linewidth=1.2, zorder=0)

    # Position ticks
    for p in positions:
        ax.text(p, -max_gap_half * 0.10, str(p), ha='center', va='top',
                fontsize=10, color=INK, fontweight='bold', family='Georgia')
    ax.text((min_d) / 2, -max_gap_half * 0.20,
            'regression depth (target − source HWM)  ·  0 = high-water mark',
            ha='center', va='top', fontsize=11, color=MUTED,
            style='italic', family='Georgia')

    # Nodes
    max_count = counts.max()
    # node at 0: anchor of all arcs
    ax.scatter([0], [0], s=380, color=INK, alpha=0.85,
               edgecolor='white', linewidth=1.4, zorder=4)
    ax.text(0, max_gap_half * 0.06, 'HWM',
            ha='center', va='bottom', fontsize=10, color=INK,
            fontweight='bold', family='Georgia')

    # nodes at each delta — size scaled by frequency
    for d, c in zip(deltas, counts):
        size = 80 + 700 * (c / max_count)
        ax.scatter([d], [0], s=size, color=ACCENT, alpha=0.85,
                   edgecolor='white', linewidth=1.4, zorder=3)

    # Arcs — all originate at 0, fan leftward to each delta
    sorted_pairs = sorted(zip(deltas, counts), key=lambda x: x[1])
    for d, c in sorted_pairs:
        w = 0.6 + 5.0 * (np.log1p(c) / np.log1p(max_count))
        alpha = 0.22 + 0.65 * (c / max_count)
        cx = d / 2
        width = abs(d)
        height = width
        arc = patches.Arc((cx, 0), width=width, height=height,
                          angle=0, theta1=0, theta2=180,
                          color=ACCENT, alpha=alpha, linewidth=w, zorder=2,
                          capstyle='round')
        ax.add_patch(arc)

    # Inline labels above each node — percentage of all jumps at this depth
    for d, p in zip(deltas, pcts):
        ax.text(d, -max_gap_half * 0.04, f'{p:.1f}%',
                ha='center', va='top', fontsize=9, color=MUTED,
                family='Georgia')

    # Title
    title = (f'Regression depth — {n_with_jumps:,} of {n_trials:,} trials '
             f'({100*n_with_jumps/n_trials:.0f}%) contain a regression  ·  '
             f'{n_jumps:,} jumps total  ·  arc width ∝ jump count (log)  ·  '
             f'node size ∝ returns at depth')
    ax.set_title(title, fontsize=11.5, family='Georgia', color=INK, pad=18)

    if tail_n > 0:
        ax.text(0.99, 0.97,
                f'tail (depth ≤ {min(delta_counts) if min(delta_counts) < min_d else min_d-1} … omitted, '
                f'< {min_pct:g} % each):  {tail_n:,} jumps  ({tail_pct:.1f}%)',
                ha='right', va='top', transform=ax.transAxes, fontsize=9,
                color=MUTED, family='Georgia', style='italic')

    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    plt.tight_layout()
    plt.savefig(out_png, dpi=160, bbox_inches='tight', facecolor=BG)
    plt.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'wrote {out_png}')

    summary = {
        'attribution': attribution,
        'n_trials_total': n_trials,
        'n_trials_with_jumps': n_with_jumps,
        'n_total_jumps': n_jumps,
        'delta_counts': {int(d): int(c) for d, c in sorted(delta_counts.items())},
        'delta_pcts': {int(d): float(100*c/n_jumps) for d, c in sorted(delta_counts.items())},
    }
    with out_png.with_suffix('.json').open('w') as f:
        json.dump(summary, f, indent=2)
    print(f'wrote {out_png.with_suffix(".json")}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'], default='organic')
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    delta_counts, n_total, n_with_jumps, n_jumps = collect_relative_deltas(args.attribution)
    out = OUT_DIR / f'regressive_relative_{args.attribution}.png'
    render_arcs_relative(delta_counts, n_total, n_with_jumps, n_jumps,
                         args.attribution, out)


if __name__ == '__main__':
    main()
