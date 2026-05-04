"""Scroll velocity by direction — independent confirmation that regressive
scroll moves faster than forward scroll.

Reads mouse-events scroll stream (independent of the gaze stream that
drives the AOI-fixation analysis). For each consecutive pair of scroll
samples (t1, y1) → (t2, y2):
  - Δy = y2 - y1   (page-space)
  - direction = forward if Δy > 0 (scroll-down), regressive if Δy < 0
  - speed = |Δy| / Δt   (px/ms)

Bin by source scroll position (depth into the page) so we can see if
regressive scroll-back accelerates with depth.

Run:
  .venv/bin/python scripts/render_scroll_velocity.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
from data_loader import (  # noqa: E402
    get_trial_ids, load_mouse_events, get_trial_meta,
)

BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
FWD = '#5B3EB8'   # purple
REG = '#B8722C'   # orange


def collect_scroll_events():
    """Walk every trial; emit one record per consecutive scroll-pair."""
    events = []
    n_trials_walked = 0
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
        n_trials_walked += 1
        for (t1, y1), (t2, y2) in zip(scrolls[:-1], scrolls[1:]):
            dt = t2 - t1
            if dt <= 0:
                continue
            dy = y2 - y1
            if dy == 0:
                continue
            speed = abs(dy) / dt * 1000.0   # px/sec
            direction = 'forward' if dy > 0 else 'regressive'
            # Source scroll-y as fraction of doc height (0 = top, 1 = bottom)
            src_frac = y1 / max(doc_h, 1)
            events.append({
                'tid': tid, 'speed_px_per_ms': speed,
                'direction': direction, 'dy': dy, 'dt': dt,
                'src_y': y1, 'src_frac': src_frac,
            })
    return events, n_trials_walked


def depth_bin(frac):
    if frac < 0.20:
        return 'top (<20%)'
    if frac < 0.50:
        return 'mid (20-50%)'
    return 'deep (50%+)'


def main():
    print('[walk] scroll events across all trials', file=sys.stderr)
    events, n_trials = collect_scroll_events()
    print(f'  trials walked: {n_trials:,}  scroll-pair events: {len(events):,}',
          file=sys.stderr)

    # Stdout summary
    bins = ['top (<20%)', 'mid (20-50%)', 'deep (50%+)']
    print()
    print(f'{"depth bin":>14s}  {"dir":>6s}  {"n":>8s}  '
          f'{"med px/s":>10s}  {"mean px/s":>11s}  {"med |dy|":>9s}')
    for b in bins:
        for d in ('forward', 'regressive'):
            es = [e for e in events
                  if depth_bin(e['src_frac']) == b and e['direction'] == d]
            if not es:
                continue
            speeds = [e['speed_px_per_ms'] for e in es]   # variable kept as-is; values are now px/s
            dys = [abs(e['dy']) for e in es]
            print(f'{b:>14s}  {d:>6s}  {len(es):>8,}  '
                  f'{np.median(speeds):>9.0f}  '
                  f'{np.mean(speeds):>10.0f}  '
                  f'{np.median(dys):>8.0f}')

    # ── render ──
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.0), facecolor=BG,
                             gridspec_kw={'wspace': 0.25, 'left': 0.07,
                                          'right': 0.97, 'top': 0.86,
                                          'bottom': 0.20,
                                          'width_ratios': [1.5, 1.0]})

    # Panel A: violin pairs by depth bin
    ax = axes[0]
    ax.set_facecolor(BG)
    width = 0.36
    n_summary_per_cell = {}
    for ci, b in enumerate(bins):
        for di, d in enumerate(('forward', 'regressive')):
            xs = ci + (di * width - width / 2)
            es = [e for e in events
                  if depth_bin(e['src_frac']) == b and e['direction'] == d]
            if not es:
                continue
            speeds = np.asarray([e['speed_px_per_ms'] for e in es])
            n_summary_per_cell[(b, d)] = len(speeds)
            color = FWD if d == 'forward' else REG
            # Clip extreme tail for violin readability
            clip_hi = float(np.percentile(speeds, 98))
            speeds_clip = speeds[speeds <= clip_hi]
            vp = ax.violinplot([speeds_clip], positions=[xs], widths=width * 0.85,
                               showmeans=False, showmedians=False, showextrema=False)
            for body in vp['bodies']:
                body.set_facecolor(color); body.set_alpha(0.55)
                body.set_edgecolor(color); body.set_linewidth(0.7)
            med = float(np.median(speeds))
            q25 = float(np.percentile(speeds, 25))
            q75 = float(np.percentile(speeds, 75))
            ax.plot([xs - width * 0.30, xs + width * 0.30], [med, med],
                    color='white', linewidth=2.4, zorder=4)
            ax.plot([xs - width * 0.20, xs + width * 0.20], [med, med],
                    color=color, linewidth=2.4, zorder=5)
            ax.plot([xs, xs], [q25, q75], color=color, linewidth=1.0, alpha=0.8)
            ax.text(xs, med + 30, f'{med:.0f}', ha='center', va='bottom',
                    fontsize=9, color=color, family='Georgia', weight='bold')

    ax.set_xticks(range(len(bins)))
    ax.set_xticklabels(bins, fontsize=10.5, color=INK, family='Georgia')
    ax.set_xlabel('source scroll position (fraction of document height)',
                  fontsize=11, color=INK, family='Georgia')
    ax.set_ylabel('scroll speed (px / second)', fontsize=11,
                  color=INK, family='Georgia')
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    ax.set_title(
        f'A. Scroll speed by direction × source-position depth  —  '
        f'{len(events):,} scroll-pair events  ·  {n_trials:,} trials  ·  '
        f'[rank-type-N/A — mouse-events stream; depth bins are fractions of doc height]',
        fontsize=11.0, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')
    # legend — anchored above the plot, outside the data area
    import matplotlib.patches as mpatches
    ax.legend(handles=[
        mpatches.Patch(facecolor=FWD, alpha=0.55, edgecolor=FWD,
                       label='forward scroll (page-down)'),
        mpatches.Patch(facecolor=REG, alpha=0.55, edgecolor=REG,
                       label='regressive scroll (page-up)'),
    ], loc='upper center', bbox_to_anchor=(0.5, -0.18),
        fontsize=10, frameon=False, labelcolor=INK, ncol=2)

    # Panel B: pooled forward vs regressive speed distribution (CDF)
    ax = axes[1]
    ax.set_facecolor(BG)
    fwd_speeds = np.asarray([e['speed_px_per_ms'] for e in events if e['direction'] == 'forward'])
    reg_speeds = np.asarray([e['speed_px_per_ms'] for e in events if e['direction'] == 'regressive'])
    # CDF
    for vals, color, lbl in [
        (fwd_speeds, FWD, f'forward (n = {len(fwd_speeds):,})'),
        (reg_speeds, REG, f'regressive (n = {len(reg_speeds):,})'),
    ]:
        if len(vals) == 0:
            continue
        vals_s = np.sort(vals)
        cdf = np.arange(1, len(vals_s) + 1) / len(vals_s)
        ax.plot(vals_s, cdf, color=color, linewidth=2.4, label=lbl)
    ax.set_xlabel('scroll speed (px / second)', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_ylabel('cumulative fraction', fontsize=11, color=INK,
                  family='Georgia')
    ax.set_xlim(0, float(np.percentile(np.concatenate([fwd_speeds, reg_speeds]), 98)))
    ax.set_ylim(0, 1.0)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(MUTED)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(linestyle=':', color=RULE, alpha=0.5, zorder=0)
    ax.legend(loc='lower right', fontsize=9.5, frameon=True,
              facecolor=BG, edgecolor=RULE, labelcolor=INK)
    ax.set_title(
        'B. Pooled CDF — regressive scroll is faster overall',
        fontsize=11.5, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')

    out_png = ROOT / 'scripts/output/figures/scroll_velocity.png'
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'\n  wrote {out_png.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
