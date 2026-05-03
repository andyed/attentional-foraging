"""Arc-graph visualization of regressive jumps across organic positions.

Builds the (source HWM → target position) regression-jump histogram across
all trials, renders as semicircle arcs above an ordinal position line.

Arc width and opacity scale with frequency.
Node size at each position scales with total return-target volume.

Definitions (matches `compute_regression_labels.py` logic):
  - HWM = high-water-mark position reached so far in the fixation sequence.
  - A regressive jump occurs when fixation at position p revisits a
    previously-visited position AND p < HWM at the moment of the revisit.
  - Source = HWM at the moment of the regressive fixation.
  - Target = the position the user regressed to (p).

Run:
  .venv/bin/python scripts/render_regressive_arcs.py --attribution organic
  .venv/bin/python scripts/render_regressive_arcs.py --attribution hybrid
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

# Borrow the hybrid AOI builder from compute_regression_labels.py
_AD_DIR = DATA_DIR / 'ad-boundary-data'
_RESULT_COL_X_MIN = 50
_RESULT_COL_X_MAX = 750


def _hybrid_aoi_tops(trial_id):
    """Mirror compute_regression_labels._hybrid_aoi_tops — return
    sorted-display-order tops list (organic + dd_top + native_ad)."""
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

ACCENT = '#5B3EB8'
ACCENT2 = '#B8722C'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
BG = '#FAFAF8'


def collect_regressive_jumps(attribution='organic'):
    """Walk fixation sequences for all trials; tally (source, target) pairs."""
    jump_counts = Counter()
    target_counts = Counter()  # total returns per target position
    source_counts = Counter()  # total regression-source HWMs
    n_trials_with_jumps = 0
    n_trials_total = 0

    trial_ids = get_trial_ids()
    for tid in trial_ids:
        n_trials_total += 1
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        if attribution == 'hybrid':
            tops = _hybrid_aoi_tops(tid)
        else:
            tops = organic_aoi_tops(tid)
        n_res = len(tops)
        if not tops or n_res == 0:
            continue

        pos_seq = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is not None and p >= 0:
                pos_seq.append(p)

        visited = set()
        max_seen = -1
        had_jump = False
        for p in pos_seq:
            # Detect regression: revisit AND below current HWM
            if p in visited and p < max_seen:
                jump_counts[(max_seen, p)] += 1
                target_counts[p] += 1
                source_counts[max_seen] += 1
                had_jump = True
            visited.add(p)
            if p > max_seen:
                max_seen = p
        if had_jump:
            n_trials_with_jumps += 1
    return jump_counts, target_counts, source_counts, n_trials_total, n_trials_with_jumps


def render_arcs(jump_counts, target_counts, source_counts, n_trials, n_with_jumps,
                attribution='organic', out_png=None):
    if not jump_counts:
        print('  no regressive jumps found', file=sys.stderr)
        return
    max_pos = max(max(s, t) for (s, t) in jump_counts) + 1
    positions = list(range(max_pos))
    total_jumps = sum(jump_counts.values())

    # --- figure setup ---
    fig, ax = plt.subplots(figsize=(13.5, 5.6), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(-0.6, max_pos - 0.4)
    # We compute arc heights = gap/2; max gap is max_pos-1 → max height ~ (max_pos-1)/2
    max_gap_half = (max_pos - 1) / 2
    ax.set_ylim(-max_gap_half * 0.20, max_gap_half * 1.05)
    ax.set_aspect('equal')

    # Baseline + position ticks
    ax.axhline(0, color=RULE, linewidth=1.2, zorder=0)
    for p in positions:
        ax.text(p, -max_gap_half * 0.10, str(p), ha='center', va='top',
                fontsize=10, color=INK, fontweight='bold',
                family='Georgia')
    ax.text(max_pos / 2 - 0.5, -max_gap_half * 0.18, 'organic rank',
            ha='center', va='top', fontsize=11, color=MUTED,
            style='italic', family='Georgia')

    # Position nodes — size scaled by return-target volume
    target_vals = np.array([target_counts.get(p, 0) for p in positions])
    src_vals = np.array([source_counts.get(p, 0) for p in positions])
    max_tv = max(target_vals.max(), 1)
    for p in positions:
        tv = target_counts.get(p, 0)
        # Filled circle = return-target frequency
        if tv > 0:
            size = 80 + 600 * (tv / max_tv)
            ax.scatter([p], [0], s=size, color=ACCENT, alpha=0.85,
                       edgecolor='white', linewidth=1.4, zorder=3)
        else:
            ax.scatter([p], [0], s=80, color=RULE, edgecolor='white',
                       linewidth=1.0, zorder=3)

    # --- arcs ---
    # Sort by count so heavier arcs draw last (on top)
    sorted_jumps = sorted(jump_counts.items(), key=lambda x: x[1])
    max_count = max(jump_counts.values())
    cmin = 1
    n_arcs_drawn = 0
    for (src, tgt), cnt in sorted_jumps:
        if cnt < cmin:
            continue
        # Width: log scale, capped
        w = 0.6 + 4.5 * (np.log1p(cnt) / np.log1p(max_count))
        # Opacity: linear in share, floored
        alpha = 0.20 + 0.65 * (cnt / max_count)
        # Bezier-like: use a half-ellipse via matplotlib.patches.Arc
        cx = (src + tgt) / 2
        width = abs(src - tgt)  # horizontal diameter
        height = width  # circular
        arc = patches.Arc(
            (cx, 0), width=width, height=height,
            angle=0, theta1=0, theta2=180,
            color=ACCENT, lw=w, alpha=alpha, zorder=2,
        )
        ax.add_patch(arc)
        n_arcs_drawn += 1

    # --- annotations ---
    pct = 100 * n_with_jumps / max(n_trials, 1)
    attr_label = 'organic_hybrid (organic + dd_top + native_ad)' if attribution == 'hybrid' else 'bbox-organic'
    ax.set_title(
        f'Regressive jumps across positions [{attr_label}]  —  '
        f'{n_with_jumps:,} of {n_trials:,} trials ({pct:.0f}%) had >=1 regression  '
        f'·  {total_jumps:,} jumps total  ·  {n_arcs_drawn:,} (source, target) pairs',
        fontsize=11.5, color=INK, family='Georgia', loc='left', pad=14,
    )

    # Legend / hint inset
    ax.text(0.02, 0.96,
            f'arc: source HWM → target position\n'
            f'arc width / opacity: jump count (log scale)\n'
            f'node size: total returns to position\n'
            f'max source–target pair: ({max(jump_counts, key=jump_counts.get)})  '
            f'n = {max_count:,}',
            transform=ax.transAxes, va='top', ha='left',
            fontsize=9.5, color=MUTED, family='Georgia',
            bbox=dict(facecolor=BG, edgecolor=RULE, linewidth=0.8,
                      boxstyle='round,pad=0.5'))

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ('top', 'right', 'bottom', 'left'):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = out_png or (OUT_DIR / 'regressive_arcs.png')
    fig.savefig(target, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(target.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'  wrote {target.relative_to(ROOT)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'], default='organic')
    args = ap.parse_args()

    suffix = '_hybrid' if args.attribution == 'hybrid' else '_organic'
    out_png = OUT_DIR / f'regressive_arcs{suffix}.png'
    out_json = OUT_DIR / f'regressive_arcs{suffix}_summary.json'

    print(f'[walk] fixation sequences (attribution={args.attribution})', file=sys.stderr)
    jc, tc, sc, n_total, n_with = collect_regressive_jumps(args.attribution)
    print(f'  trials walked: {n_total:,}  with regressive jumps: {n_with:,} '
          f'({100 * n_with / max(n_total, 1):.1f}%)', file=sys.stderr)
    print(f'  unique (source, target) pairs: {len(jc):,}  '
          f'total jumps: {sum(jc.values()):,}', file=sys.stderr)

    # --- top-10 (source → target) pairs by count ---
    print('\n=== Top 10 (source HWM → target) regressive jumps ===')
    print(f"{'rank':>4s}  {'source':>6s}  {'target':>6s}  {'count':>7s}  {'pct':>6s}")
    total = sum(jc.values())
    for i, ((s, t), c) in enumerate(sorted(jc.items(), key=lambda x: -x[1])[:10]):
        print(f"{i+1:>4d}  {s:>6d}  {t:>6d}  {c:>7,}  {100*c/total:>5.1f}%")

    print('\n=== Returns per target position ===')
    print(f"{'pos':>4s}  {'returns':>8s}  {'pct':>6s}")
    for p in sorted(tc):
        print(f"{p:>4d}  {tc[p]:>8,}  {100*tc[p]/total:>5.1f}%")

    # Render
    render_arcs(jc, tc, sc, n_total, n_with, attribution=args.attribution, out_png=out_png)

    summary = {
        'attribution': args.attribution,
        'n_trials_total': n_total,
        'n_trials_with_jumps': n_with,
        'pct_trials_with_jumps': 100 * n_with / max(n_total, 1),
        'n_unique_pairs': len(jc),
        'n_total_jumps': total,
        'pairs_top20': [
            {'source': s, 'target': t, 'count': c, 'pct': 100 * c / total}
            for (s, t), c in sorted(jc.items(), key=lambda x: -x[1])[:20]
        ],
        'returns_by_target': {str(p): {'count': tc[p], 'pct': 100 * tc[p] / total}
                               for p in sorted(tc)},
        'sources_by_hwm': {str(p): {'count': sc[p], 'pct': 100 * sc[p] / total}
                            for p in sorted(sc)},
    }
    out_json.write_text(json.dumps(summary, indent=2))
    print(f'\nwrote {out_json.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
