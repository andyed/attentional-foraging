"""Three-tercile small multiples of the regress-scan-regress staircase
by participant strategy (satisficer ↔ optimizer).

Tercile basis: per-participant overall regression rate
  = fraction of the participant's trials that contain ≥1 regressive fixation
  (a fixation at position p where p < HWM at that moment).

Lower regression rate = satisficer (short evaluation, commits early).
Higher regression rate = optimizer (revisits, multi-cycle scanning).

Each panel reuses the Panel-A treatment from
`render_scan_epoch_staircase.py`: trial traces (light), median HWM
staircase + IQR ribbon, median position fixated (the "dips" line).

Output:
  scripts/output/figures/staircase_by_strategy_organic.png (+ .pdf)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    DATA_DIR, get_trial_ids, load_fixations, get_trial_meta,
    organic_aoi_tops, organic_aoi_bands, assign_fixation_to_position,
)

# ── editorial cream palette ──
BG = '#FAFAF8'
INK = '#0B1220'
MUTED = '#4B4B4B'
RULE = '#D2CEC4'
ACCENT = '#5B3EB8'
ACCENT2 = '#B8722C'
HWM = '#3A2680'
TRACE = '#5B3EB8'

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


def collect_trials(attribution):
    trials = []
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
        pos_seq = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is not None and p >= 0:
                pos_seq.append(p)
        if len(pos_seq) < 2:
            continue
        hwm_seq = []
        hwm = -1
        in_epoch = True
        n_epochs = 0
        had_regress = False
        any_regression = False
        for p in pos_seq:
            if p > hwm:
                if not in_epoch and had_regress:
                    n_epochs += 1
                    in_epoch = True
                    had_regress = False
                elif n_epochs == 0:
                    n_epochs = 1
                    in_epoch = True
                hwm = p
            else:
                if p < hwm:
                    in_epoch = False
                    had_regress = True
                    any_regression = True
            hwm_seq.append(hwm)
        trials.append({
            'tid': tid,
            'pid': tid.split('-')[0],
            'pos_seq': np.asarray(pos_seq, dtype=int),
            'hwm_seq': np.asarray(hwm_seq, dtype=int),
            'n_epochs': n_epochs,
            'any_regression': any_regression,
            'n_fix': len(pos_seq),
        })
    return trials


def aggregate_ribbon(trials, n_bins=50):
    """Time-warp HWM and position trajectories to [0,1], return medians + IQR."""
    grid = np.linspace(0, 1, n_bins)
    hwm_mat = np.full((len(trials), n_bins), np.nan)
    pos_mat = np.full((len(trials), n_bins), np.nan)
    for i, t in enumerate(trials):
        if t['n_fix'] < 2:
            continue
        x = np.linspace(0, 1, t['n_fix'])
        idxs = np.searchsorted(x, grid, side='right') - 1
        idxs = np.clip(idxs, 0, t['n_fix'] - 1)
        hwm_mat[i] = t['hwm_seq'][idxs]
        pos_mat[i] = t['pos_seq'][idxs]
    return {
        'grid': grid,
        'hwm_med': np.nanmedian(hwm_mat, axis=0),
        'hwm_p25': np.nanpercentile(hwm_mat, 25, axis=0),
        'hwm_p75': np.nanpercentile(hwm_mat, 75, axis=0),
        'pos_med': np.nanmedian(pos_mat, axis=0),
    }


def render(trials, attribution, out_png):
    # Per-participant overall regression rate
    pid_trials = defaultdict(list)
    for t in trials:
        pid_trials[t['pid']].append(t)
    pid_rates = {}
    for pid, ts in pid_trials.items():
        n = len(ts)
        n_reg = sum(1 for x in ts if x['any_regression'])
        pid_rates[pid] = n_reg / max(n, 1)

    # Rank-based tercile assignment (robust to saturated distributions
    # under hybrid attribution where many pids share rate=1.0; percentile
    # cuts collapse the high tercile).
    pids_sorted = sorted(pid_rates.items(), key=lambda kv: kv[1])
    n_pids = len(pids_sorted)
    third = n_pids // 3
    low_set = {pid for pid, _ in pids_sorted[:third]}
    high_set = {pid for pid, _ in pids_sorted[-third:]}
    mid_set = {pid for pid, _ in pids_sorted[third:n_pids - third]}
    pid_tier = {}
    for pid in low_set:  pid_tier[pid] = 'low'
    for pid in mid_set:  pid_tier[pid] = 'mid'
    for pid in high_set: pid_tier[pid] = 'high'
    rates_low = [pid_rates[p] for p in low_set]
    rates_high = [pid_rates[p] for p in high_set]
    print(f'  rank-tercile cuts (rank-based): '
          f'low n={len(low_set)} (rate range {min(rates_low):.2f}–{max(rates_low):.2f}), '
          f'mid n={len(mid_set)}, '
          f'high n={len(high_set)} (rate range {min(rates_high):.2f}–{max(rates_high):.2f})',
          file=sys.stderr)

    by_tier = defaultdict(list)
    for t in trials:
        by_tier[pid_tier[t['pid']]].append(t)

    tier_labels = [
        ('low',  'Satisficer  (low regression rate)',  ACCENT2),
        ('mid',  'Mid',                                 ACCENT),
        ('high', 'Optimizer  (high regression rate)',  HWM),
    ]

    # Determine global y-axis max
    max_pos = max(t['pos_seq'].max() for t in trials)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 8.0), facecolor=BG,
                             gridspec_kw={'wspace': 0.18,
                                          'left': 0.05, 'right': 0.98,
                                          'top': 0.80, 'bottom': 0.22})
    rng = np.random.default_rng(20260503)
    attr_label = ('organic_hybrid' if attribution == 'hybrid'
                  else 'bbox-organic')

    panel_stats = []
    for ax, (tier_key, tier_title, tier_color) in zip(axes, tier_labels):
        ax.set_facecolor(BG)
        bin_trials = by_tier[tier_key]
        n_bin = len(bin_trials)
        n_pids = sum(1 for pid, t in pid_tier.items() if t == tier_key)

        # Trial trace texture
        sample_idx = rng.choice(len(bin_trials),
                                size=min(220, len(bin_trials)),
                                replace=False)
        for i in sample_idx:
            t = bin_trials[i]
            x = np.linspace(0, 1, t['n_fix'])
            ax.plot(x, t['pos_seq'], color=TRACE, alpha=0.05,
                    linewidth=0.7, zorder=1)

        # Aggregate ribbon
        agg = aggregate_ribbon(bin_trials)
        ax.fill_between(agg['grid'], agg['hwm_p25'], agg['hwm_p75'],
                        color=HWM, alpha=0.18, zorder=2)
        ax.plot(agg['grid'], agg['hwm_med'], color=HWM, linewidth=2.6,
                zorder=4, drawstyle='steps-mid')
        ax.plot(agg['grid'], agg['pos_med'], color=ACCENT2, linewidth=2.0,
                alpha=0.9, linestyle='--', zorder=3)

        # Style
        ax.set_xlim(0, 1)
        ax.set_ylim(max_pos + 0.5, -0.5)
        ax.set_xlabel('normalized trial time', color=INK, fontsize=10.5,
                      family='Georgia')
        if ax is axes[0]:
            ax.set_ylabel('organic position (0 = top)', color=INK, fontsize=11,
                          family='Georgia')
        else:
            ax.set_yticklabels([])
        ax.tick_params(colors=INK, labelsize=9.5)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)
        for spine in ('left', 'bottom'):
            ax.spines[spine].set_color(MUTED)
            ax.spines[spine].set_linewidth(0.8)
        ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)

        # Title — strategy label only
        ax.set_title(tier_title, fontsize=12, color=tier_color,
                     family='Georgia', loc='left', pad=10, weight='bold')

        # Compute stats for footer block
        n_multi = sum(1 for t in bin_trials if t['n_epochs'] >= 2)
        pct_multi = 100 * n_multi / max(n_bin, 1)
        median_n_epochs = float(np.median([t['n_epochs'] for t in bin_trials]))
        median_n_fix = float(np.median([t['n_fix'] for t in bin_trials]))
        rates_in = [pid_rates[pid] for pid, t in pid_tier.items() if t == tier_key]
        median_rate = float(np.median(rates_in))
        panel_stats.append({
            'ax': ax, 'tier_color': tier_color,
            'n_pids': n_pids, 'n_trials': n_bin,
            'median_rate': median_rate,
            'pct_multi': pct_multi,
            'median_n_epochs': median_n_epochs,
            'median_n_fix': median_n_fix,
        })

    # Panel-stat footers (one per panel, anchored beneath xlabel)
    for s in panel_stats:
        ax = s['ax']
        # Use figure-relative coordinates from axes bbox
        bbox = ax.get_position()
        x0 = bbox.x0
        x1 = bbox.x1
        y_anchor = bbox.y0 - 0.075  # below the xlabel
        line1 = (f"{s['n_pids']} participants  ·  {s['n_trials']:,} trials  ·  "
                 f"median regression rate  {s['median_rate']:.2f}")
        line2 = (f"{s['pct_multi']:.0f}% multi-cycle  ·  "
                 f"median n_epochs  {s['median_n_epochs']:.0f}  ·  "
                 f"median  {s['median_n_fix']:.0f}  fixations")
        fig.text((x0 + x1) / 2, y_anchor, line1, fontsize=10.5,
                 color=INK, family='Georgia', ha='center', va='top')
        fig.text((x0 + x1) / 2, y_anchor - 0.035, line2, fontsize=10,
                 color=s['tier_color'], family='Georgia', ha='center', va='top',
                 weight='bold')

    fig.suptitle(
        f'Regress-scan-regress structure by participant strategy  —  '
        f'[{attr_label}]  ·  three terciles of per-participant regression rate',
        fontsize=13.5, color=INK, family='Georgia', x=0.05, ha='left',
        y=0.97, weight='bold')

    # Definition strip beneath the suptitle
    fig.text(0.05, 0.91,
             'Definition: an "epoch" is a contiguous forward push of the high-water-mark (HWM = deepest rank reached).',
             fontsize=10.5, color=INK, family='Georgia', weight='bold')
    fig.text(0.05, 0.885,
             'A new epoch begins when the user, after regressing below HWM, advances HWM beyond its prior max — i.e., resumes scanning into territory not yet visited.',
             fontsize=10, color=INK, family='Georgia', style='italic')
    fig.text(0.05, 0.860,
             '   n_epochs = 1 → pure forward (any regressions did not later push the HWM further).   '
             'n_epochs = 2 → one regress-scan-regress cycle.   '
             'n_epochs ≥ 3 → multiple cycles.   "% multi-cycle" below = trials with n_epochs ≥ 2.',
             fontsize=9.5, color=MUTED, family='Georgia')

    # Single shared legend, parked in the bottom-margin gutter
    fig.legend(handles=[
        plt.Line2D([0], [0], color=HWM, linewidth=2.6,
                   label='median HWM (the staircase)'),
        plt.Line2D([0], [0], color=ACCENT2, linewidth=2.0, linestyle='--',
                   label='median position fixated (the dips)'),
        plt.Rectangle((0, 0), 1, 1, color=HWM, alpha=0.18,
                      label='HWM IQR (P25–P75)'),
    ], loc='lower center', fontsize=10, frameon=False,
        facecolor=BG, labelcolor=INK, ncol=3,
        bbox_to_anchor=(0.5, 0.005))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'  wrote {out_png.relative_to(ROOT)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'], default='organic')
    args = ap.parse_args()

    print(f'[walk] attribution={args.attribution}', file=sys.stderr)
    trials = collect_trials(args.attribution)
    print(f'  trials walked: {len(trials):,}', file=sys.stderr)
    suffix = f'_{args.attribution}'
    out_png = ROOT / 'scripts/output/figures' / f'staircase_by_strategy{suffix}.png'
    render(trials, args.attribution, out_png)


if __name__ == '__main__':
    main()
