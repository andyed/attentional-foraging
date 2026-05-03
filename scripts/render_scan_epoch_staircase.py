"""Visualize regress-scan-regress as the modal trial structure.

Two-panel figure:
  A. Aggregate HWM-staircase ribbon — every trial as a faint position
     trajectory (time-normalized), with median HWM staircase + IQR ribbon
     overlaid. Shows the climb-dip-resume gestalt at the population level.
  B. Small multiples — five panels by n_epochs (1, 2, 3, 4, 5+) with one
     representative trial per panel and percent-of-trials labels. Calibrates
     the prevalence claim (1-epoch trials are the *minority* under organic).

Run:
  .venv/bin/python scripts/render_scan_epoch_staircase.py --attribution organic
  .venv/bin/python scripts/render_scan_epoch_staircase.py --attribution hybrid
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

# ── editorial cream palette (matches v2 deck + arc viz) ──
BG = '#FAFAF8'
INK = '#0B1220'                 # 18.7:1 on cream
MUTED = '#4B4B4B'               # 8.6:1
RULE = '#D2CEC4'                # decorative grid only
ACCENT = '#5B3EB8'              # purple, primary
ACCENT2 = '#B8722C'             # warn / regression highlight
HWM = '#3A2680'                 # darker purple for HWM line
TRACE = '#5B3EB8'               # per-trial line color (low alpha)

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
    """Walk every trial. Return list of dicts with pos_seq, hwm_seq, n_epochs."""
    trials = []
    n_epoch_counts = Counter()
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
        # Compute HWM trajectory + epoch count
        hwm_seq = []
        hwm = -1
        in_epoch = True
        n_epochs = 0
        had_regress_since_advance = False
        for p in pos_seq:
            if p > hwm:
                if not in_epoch and had_regress_since_advance:
                    n_epochs += 1
                    in_epoch = True
                    had_regress_since_advance = False
                elif n_epochs == 0:
                    n_epochs = 1
                    in_epoch = True
                hwm = p
            else:
                if p < hwm:
                    in_epoch = False
                    had_regress_since_advance = True
            hwm_seq.append(hwm)
        trials.append({
            'tid': tid,
            'pos_seq': np.asarray(pos_seq, dtype=int),
            'hwm_seq': np.asarray(hwm_seq, dtype=int),
            'n_epochs': n_epochs,
            'n_fix': len(pos_seq),
            'final_pos': pos_seq[-1],
        })
        n_epoch_counts[n_epochs] += 1
    return trials, n_epoch_counts


def aggregate_hwm_ribbon(trials, n_bins=50):
    """Time-normalize each trial's HWM trajectory to [0,1] and aggregate."""
    grid = np.linspace(0, 1, n_bins)
    matrix = np.full((len(trials), n_bins), np.nan)
    for i, t in enumerate(trials):
        if t['n_fix'] < 2:
            continue
        x = np.linspace(0, 1, t['n_fix'])
        # Interpolate (step) to grid
        idxs = np.searchsorted(x, grid, side='right') - 1
        idxs = np.clip(idxs, 0, t['n_fix'] - 1)
        matrix[i] = t['hwm_seq'][idxs]
    median = np.nanmedian(matrix, axis=0)
    p25 = np.nanpercentile(matrix, 25, axis=0)
    p75 = np.nanpercentile(matrix, 75, axis=0)
    return grid, median, p25, p75


def aggregate_position_ribbon(trials, n_bins=50):
    """Same time-warping but on the actual position (not HWM) — captures dips."""
    grid = np.linspace(0, 1, n_bins)
    matrix = np.full((len(trials), n_bins), np.nan)
    for i, t in enumerate(trials):
        if t['n_fix'] < 2:
            continue
        x = np.linspace(0, 1, t['n_fix'])
        idxs = np.searchsorted(x, grid, side='right') - 1
        idxs = np.clip(idxs, 0, t['n_fix'] - 1)
        matrix[i] = t['pos_seq'][idxs]
    median = np.nanmedian(matrix, axis=0)
    return grid, median


def pick_representative_trial(trials_with_n, target_n_fix=None):
    """Pick a trial close to the median fixation count and ending in a click region."""
    if not trials_with_n:
        return None
    fix_counts = np.array([t['n_fix'] for t in trials_with_n])
    if target_n_fix is None:
        target = float(np.median(fix_counts))
    else:
        target = target_n_fix
    # Pick trial closest to target n_fix, prefer trials with regression to the top
    distances = np.abs(fix_counts - target)
    sorted_idx = np.argsort(distances)
    return trials_with_n[int(sorted_idx[0])]


def render(trials, attribution, n_epoch_counts, out_png):
    n_total = len(trials)
    n_pure = n_epoch_counts.get(1, 0)
    n_multi = n_total - n_pure
    pct_multi = 100 * n_multi / max(n_total, 1)

    # Figure dimensions: A on top, definition strip, B below
    fig = plt.figure(figsize=(13.0, 10.5), facecolor=BG)
    gs = fig.add_gridspec(2, 5, height_ratios=[1.4, 1.0],
                          hspace=0.78, wspace=0.30,
                          left=0.06, right=0.97, top=0.93, bottom=0.06)

    # ── Panel A: aggregate HWM-staircase ribbon ──
    axA = fig.add_subplot(gs[0, :])
    axA.set_facecolor(BG)

    # 250 random trials in light trace
    rng = np.random.default_rng(20260503)
    sample_idx = rng.choice(len(trials), size=min(250, len(trials)), replace=False)
    for i in sample_idx:
        t = trials[i]
        if t['n_fix'] < 2:
            continue
        x = np.linspace(0, 1, t['n_fix'])
        axA.plot(x, t['pos_seq'], color=TRACE, alpha=0.04, linewidth=0.7,
                 zorder=1)

    # HWM ribbon (median + IQR)
    grid, hwm_med, hwm_25, hwm_75 = aggregate_hwm_ribbon(trials)
    axA.fill_between(grid, hwm_25, hwm_75, color=HWM, alpha=0.18, zorder=2,
                     label='HWM IQR (P25–P75)')
    axA.plot(grid, hwm_med, color=HWM, linewidth=2.6, zorder=4,
             label='median HWM (the staircase)', drawstyle='steps-mid')

    # Median actual position (shows the dips)
    grid_p, pos_med = aggregate_position_ribbon(trials)
    axA.plot(grid_p, pos_med, color=ACCENT2, linewidth=2.0, zorder=3,
             alpha=0.85, label='median position fixated (the dips)',
             linestyle='--')

    # Style
    max_pos = max(t['pos_seq'].max() for t in trials)
    axA.set_xlim(0, 1)
    axA.set_ylim(max_pos + 0.5, -0.5)  # invert y so deeper ranks go down
    axA.set_xlabel('normalized trial time (fixation 0 → click)', color=INK,
                   fontsize=11, family='Georgia')
    axA.set_ylabel('organic position (0 = top)', color=INK, fontsize=11,
                   family='Georgia')
    axA.tick_params(colors=INK, labelsize=9.5)
    for spine in ('top', 'right'):
        axA.spines[spine].set_visible(False)
    for spine in ('left', 'bottom'):
        axA.spines[spine].set_color(MUTED)
        axA.spines[spine].set_linewidth(0.8)
    axA.grid(axis='y', linestyle=':', color=RULE, alpha=0.5, zorder=0)
    axA.legend(loc='lower right', fontsize=9.5, frameon=True,
               facecolor=BG, edgecolor=RULE, labelcolor=INK)

    attr_label = ('organic_hybrid (organic + dd_top + native_ad)'
                  if attribution == 'hybrid' else 'bbox-organic')
    axA.set_title(
        f'A. The staircase pattern is the population-level scan shape  —  '
        f'[{attr_label}]  ·  {n_total:,} trials  ·  '
        f'{pct_multi:.0f}% of trials had ≥ 1 regress-scan-regress cycle',
        fontsize=13, color=INK, family='Georgia', loc='left', pad=10,
        weight='bold')

    # ── Panel B: small multiples by n_epochs ──
    n_bins = [1, 2, 3, 4, '5+']
    by_epoch = defaultdict(list)
    for t in trials:
        if t['n_epochs'] == 0:
            continue
        if t['n_epochs'] >= 5:
            by_epoch['5+'].append(t)
        else:
            by_epoch[t['n_epochs']].append(t)

    for col_idx, n_lbl in enumerate(n_bins):
        ax = fig.add_subplot(gs[1, col_idx])
        ax.set_facecolor(BG)
        bin_trials = by_epoch[n_lbl]
        n_bin = len(bin_trials)
        pct_bin = 100 * n_bin / max(n_total, 1)

        rep = pick_representative_trial(bin_trials)
        if rep is None:
            ax.text(0.5, 0.5, '—', ha='center', va='center', transform=ax.transAxes,
                    color=MUTED, fontsize=14)
        else:
            x = np.arange(rep['n_fix'])
            ax.plot(x, rep['pos_seq'], color=ACCENT, linewidth=1.6, zorder=3,
                    drawstyle='steps-mid')
            # Mark regression dips: highlight fixations where pos < HWM at that point
            dip_mask = rep['pos_seq'] < rep['hwm_seq']
            if dip_mask.any():
                ax.scatter(x[dip_mask], rep['pos_seq'][dip_mask],
                           color=ACCENT2, s=22, zorder=4,
                           edgecolor='white', linewidth=0.6,
                           label=f'{int(dip_mask.sum())} regression fixations')
            # HWM dotted
            ax.plot(x, rep['hwm_seq'], color=HWM, linewidth=1.0, alpha=0.7,
                    linestyle=':', zorder=2)

        ax.set_xlim(-0.5, max(rep['n_fix'] - 0.5, 5) if rep else 10)
        ax.set_ylim(max_pos + 0.5, -0.5)
        ax.set_xticks([])
        if col_idx == 0:
            ax.set_ylabel('position', color=INK, fontsize=10, family='Georgia')
            ax.tick_params(colors=INK, labelsize=8.5)
        else:
            ax.set_yticklabels([])
            ax.tick_params(colors=INK, labelsize=8.5)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)
        for spine in ('left', 'bottom'):
            ax.spines[spine].set_color(MUTED)
            ax.spines[spine].set_linewidth(0.6)
        ax.grid(axis='y', linestyle=':', color=RULE, alpha=0.4, zorder=0)
        title_text = (f'n_epochs = {n_lbl}\n'
                      f'{n_bin:,} trials ({pct_bin:.1f}%)')
        bold_color = ACCENT if pct_bin >= 15 else INK
        ax.set_title(title_text, fontsize=10.5, color=bold_color,
                     family='Georgia', loc='left', pad=6,
                     weight='bold' if pct_bin >= 15 else 'normal')

    # Definition strip between Panel A and Panel B
    fig.text(0.06, 0.43,
             'Definition: an "epoch" is a contiguous forward push of the high-water-mark (HWM = deepest rank reached).',
             fontsize=10.5, color=INK, family='Georgia', weight='bold')
    fig.text(0.06, 0.412,
             'A new epoch begins when the user, after regressing below HWM, advances HWM beyond its prior max — i.e., resumes scanning into territory not yet visited.',
             fontsize=10, color=INK, family='Georgia', style='italic')
    fig.text(0.06, 0.394,
             '   n_epochs = 1 → pure forward (any regressions did not later push the HWM further).   '
             'n_epochs = 2 → one regress-scan-regress cycle.   '
             'n_epochs ≥ 3 → multiple cycles.',
             fontsize=9.5, color=MUTED, family='Georgia')

    # Bottom-row figure title
    fig.text(0.06, 0.36,
             'B. Small multiples by epoch count  —  '
             'one representative trial per stratum, regression fixations highlighted in orange  ·  '
             'dotted line = HWM',
             fontsize=11.5, color=INK, family='Georgia', weight='bold')

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches='tight', facecolor=BG)
    fig.savefig(out_png.with_suffix('.pdf'), bbox_inches='tight', facecolor=BG)
    print(f'  wrote {out_png.relative_to(ROOT)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid'], default='organic')
    args = ap.parse_args()

    print(f'[walk] attribution={args.attribution}', file=sys.stderr)
    trials, ne_counts = collect_trials(args.attribution)
    print(f'  trials walked: {len(trials):,}', file=sys.stderr)
    print(f'  n_epoch distribution: '
          f'{[(k, ne_counts[k]) for k in sorted(ne_counts)]}', file=sys.stderr)

    suffix = f'_{args.attribution}'
    out_png = ROOT / 'scripts/output/figures' / f'scan_epoch_staircase{suffix}.png'
    render(trials, args.attribution, ne_counts, out_png)


if __name__ == '__main__':
    main()
