"""Saccade-event metrics by direction × source-position bin.

For each consecutive fixation pair in each trial that crosses an organic
position boundary, classify the saccade as forward (target > source) or
regressive (target < source), and record:
  - jump_size       (ranks)
  - source_dwell_ms (ms; duration of source fixation)
  - saccade_speed   (ranks / second = jump_size / inter-fixation time)
  - source_visits   (distinct visits to source AOI up to and including
                     the source fixation — captures re-engagement)

Group by source-position bin: top (0-3) / mid (4-7) / deep (8+).
Render as a 4-row × 3-col violin grid (one row per metric, one col per
bin), with forward/regressive paired violins in each cell.

Run:
  .venv/bin/python scripts/render_saccade_metrics_by_bin.py --attribution organic
  .venv/bin/python scripts/render_saccade_metrics_by_bin.py --attribution hybrid
"""
from __future__ import annotations

import argparse
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
    organic_aoi_tops, organic_aoi_bands, assign_fixation_to_position,
)

# editorial cream palette
BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
FWD = '#5B3EB8'        # purple — forward
REG = '#B8722C'        # orange — regressive

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


def collect_saccades(attribution):
    """Walk fixation sequences. Return list of saccade-event dicts."""
    events = []
    n_trials_walked = 0
    for tid in get_trial_ids():
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        if attribution == 'hybrid':
            tops = _hybrid_aoi_tops(tid)
        else:
            tops = organic_aoi_tops(tid)
        if not tops:
            continue
        n_res = len(tops)

        # Map fixations to positions (filter unmappable)
        mapped = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is None or p < 0:
                continue
            mapped.append({
                'pos': int(p),
                't': int(f.get('t', 0)),
                'd': float(f.get('d', 200)),
            })
        if len(mapped) < 2:
            continue
        n_trials_walked += 1

        # Visit-count-so-far per AOI (a "visit" = maximal run of same-pos fixations)
        visits_per_pos = defaultdict(int)
        prev_pos = None
        visit_count_at_fix = []
        for m in mapped:
            if m['pos'] != prev_pos:
                visits_per_pos[m['pos']] += 1
            visit_count_at_fix.append(visits_per_pos[m['pos']])
            prev_pos = m['pos']

        # Generate saccade events between consecutive fixations of different position
        for i in range(len(mapped) - 1):
            src = mapped[i]
            tgt = mapped[i + 1]
            if src['pos'] == tgt['pos']:
                continue
            jump = tgt['pos'] - src['pos']
            direction = 'forward' if jump > 0 else 'regressive'
            interval_ms = max(tgt['t'] - src['t'], 1)  # avoid /0
            speed = abs(jump) / (interval_ms / 1000.0)  # ranks per second
            events.append({
                'tid': tid,
                'source_pos': src['pos'],
                'target_pos': tgt['pos'],
                'jump_size': abs(jump),
                'direction': direction,
                'source_dwell_ms': src['d'],
                'saccade_speed': speed,
                'source_visits': visit_count_at_fix[i],
            })
    return events, n_trials_walked


def bin_label(pos):
    if pos <= 3:
        return 'top (0-3)'
    if pos <= 7:
        return 'mid (4-7)'
    return 'deep (8+)'


def render(events, attribution, out_png):
    if not events:
        print('  no saccade events; aborting', file=sys.stderr)
        return

    bins = ['top (0-3)', 'mid (4-7)', 'deep (8+)']
    metrics = [
        ('jump_size',       'Jump size (ranks)',        None),
        ('source_dwell_ms', 'Source dwell (ms)',        None),
        ('saccade_speed',   'Saccade speed (ranks/s)',  None),
        ('source_visits',   'Source visit count',       None),
    ]

    # Bucketize
    by_cell = defaultdict(lambda: defaultdict(list))  # bin -> direction -> {metric: [...]}
    for ev in events:
        b = bin_label(ev['source_pos'])
        d = ev['direction']
        if d not in ('forward', 'regressive'):
            continue
        if d not in by_cell[b]:
            by_cell[b][d] = {m: [] for m, _, _ in metrics}
        for m, _, _ in metrics:
            by_cell[b][d][m].append(ev[m])

    fig, axes = plt.subplots(len(metrics), len(bins),
                             figsize=(13.5, 11.5),
                             facecolor=BG,
                             gridspec_kw={'wspace': 0.20, 'hspace': 0.45,
                                          'left': 0.10, 'right': 0.97,
                                          'top': 0.93, 'bottom': 0.06})

    # Compute per-row global y-range so violins are comparable across bins
    row_yrange = {}
    for m, _, _ in metrics:
        all_vals = []
        for b in bins:
            for d in ('forward', 'regressive'):
                if d in by_cell[b]:
                    all_vals += by_cell[b][d][m]
        if not all_vals:
            row_yrange[m] = (0, 1)
            continue
        a = np.asarray(all_vals)
        # Use 2nd–98th percentile to clip outliers; pad slightly
        lo, hi = np.percentile(a, [1, 98])
        if m == 'source_visits':
            lo = 0; hi = max(hi, 5)  # integer scale
        elif m == 'jump_size':
            lo = 0
        else:
            lo = max(0, lo)
        row_yrange[m] = (lo, hi)

    for r, (mkey, mlabel, _) in enumerate(metrics):
        for c, b in enumerate(bins):
            ax = axes[r, c]
            ax.set_facecolor(BG)
            cell = by_cell[b]

            data_fwd = cell.get('forward', {}).get(mkey, [])
            data_reg = cell.get('regressive', {}).get(mkey, [])
            n_fwd = len(data_fwd); n_reg = len(data_reg)

            positions = []
            data_lists = []
            colors = []
            if data_fwd:
                positions.append(1)
                data_lists.append(np.asarray(data_fwd))
                colors.append(FWD)
            if data_reg:
                positions.append(2)
                data_lists.append(np.asarray(data_reg))
                colors.append(REG)

            if data_lists:
                vp = ax.violinplot(data_lists, positions=positions,
                                   widths=0.78, showmeans=False,
                                   showmedians=False, showextrema=False)
                for body, col in zip(vp['bodies'], colors):
                    body.set_facecolor(col)
                    body.set_alpha(0.55)
                    body.set_edgecolor(col)
                    body.set_linewidth(0.8)
                # Median + IQR markers
                for x, vals, col in zip(positions, data_lists, colors):
                    med = float(np.median(vals))
                    q25 = float(np.percentile(vals, 25))
                    q75 = float(np.percentile(vals, 75))
                    ax.plot([x - 0.18, x + 0.18], [med, med],
                            color='white', linewidth=2.2, zorder=4)
                    ax.plot([x - 0.10, x + 0.10], [med, med],
                            color=col, linewidth=2.2, zorder=5)
                    ax.plot([x, x], [q25, q75], color=col,
                            linewidth=1.2, alpha=0.85, zorder=4)
                    # Annotate median
                    fmt = '.1f' if mkey != 'source_visits' else '.0f'
                    if mkey == 'source_dwell_ms' or mkey == 'saccade_speed':
                        fmt = '.0f'
                    ax.text(x + 0.30, med, f'{med:{fmt}}',
                            ha='left', va='center',
                            fontsize=8.5, color=col, family='Georgia')

            # Style
            ax.set_xlim(0.4, 2.6)
            lo, hi = row_yrange[mkey]
            ax.set_ylim(lo, hi)
            ax.set_xticks([1, 2])
            ax.set_xticklabels(
                [f'fwd\nn={n_fwd:,}', f'reg\nn={n_reg:,}']
                if r == len(metrics) - 1 else [f'fwd', f'reg'],
                fontsize=9, color=INK, family='Georgia')
            for spine in ('top', 'right'):
                ax.spines[spine].set_visible(False)
            for spine in ('left', 'bottom'):
                ax.spines[spine].set_color(MUTED)
                ax.spines[spine].set_linewidth(0.7)
            ax.tick_params(colors=INK, labelsize=9)
            ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)

            if r == 0:
                ax.set_title(b, fontsize=11, color=INK, family='Georgia',
                             weight='bold', pad=6)
            if c == 0:
                ax.set_ylabel(mlabel, fontsize=10, color=INK, family='Georgia')

    attr_label = 'organic_hybrid' if attribution == 'hybrid' else 'bbox-organic'
    n_total = len(events)
    n_fwd = sum(1 for e in events if e['direction'] == 'forward')
    n_reg = sum(1 for e in events if e['direction'] == 'regressive')
    fig.suptitle(
        f'Saccade-event metrics by direction × source-position bin  —  '
        f'[{attr_label}]  ·  {n_total:,} saccades  '
        f'({n_fwd:,} forward, {n_reg:,} regressive)',
        fontsize=12.5, color=INK, family='Georgia', x=0.10, ha='left',
        y=0.97, weight='bold')

    # Legend
    fig.legend(handles=[
        patches.Patch(facecolor=FWD, alpha=0.55, edgecolor=FWD,
                      label='forward saccade (target rank > source)'),
        patches.Patch(facecolor=REG, alpha=0.55, edgecolor=REG,
                      label='regressive saccade (target < source)'),
    ], loc='lower right', fontsize=10, frameon=False,
        labelcolor=INK, ncol=2, bbox_to_anchor=(0.97, 0.005))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'  wrote {out_png.relative_to(ROOT)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'],
                    default='organic')
    args = ap.parse_args()

    print(f'[walk] attribution={args.attribution}', file=sys.stderr)
    events, n_trials = collect_saccades(args.attribution)
    print(f'  trials walked: {n_trials:,}  saccades: {len(events):,}',
          file=sys.stderr)

    # Quick stdout summary
    print()
    bins = ['top (0-3)', 'mid (4-7)', 'deep (8+)']
    metrics = ['jump_size', 'source_dwell_ms', 'saccade_speed', 'source_visits']
    print(f'{"bin":>12s}  {"dir":>6s}  {"n":>7s}  '
          + '  '.join(f'{m:>14s}' for m in metrics))
    for b in bins:
        for d in ('forward', 'regressive'):
            es = [e for e in events
                  if bin_label(e['source_pos']) == b and e['direction'] == d]
            n = len(es)
            if n == 0:
                continue
            row = []
            for mkey in metrics:
                vals = [e[mkey] for e in es]
                row.append(f'{np.median(vals):>14.1f}')
            print(f'{b:>12s}  {d:>6s}  {n:>7,}  ' + '  '.join(row))

    suffix = '_hybrid' if args.attribution == 'hybrid' else '_organic'
    out_png = ROOT / 'scripts/output/figures' / f'saccade_metrics_by_bin{suffix}.png'
    render(events, args.attribution, out_png)


if __name__ == '__main__':
    main()
