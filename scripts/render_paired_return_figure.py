"""Render the ETTAC §3.3 within-item paired return-vs-first LF/HF figure.

Two-panel layout:
  (a) per-(trial, position) paired Δ scatter (first-visit on x, return-visit
      on y; identity diagonal; off-diagonal = direction of effect).
  (b) per-rank Δ forest plot — median Δ per display rank with bootstrap
      95 % CIs, reading left-to-right.

Output:
  ~/Documents/dev/ettac-paper/figs/adserp/paired-return.{pdf,png}

Run:
  .venv/bin/python scripts/render_paired_return_figure.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from scipy.signal import butter, sosfiltfilt

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))

from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    typed_aoi_tops, assign_fixation_to_position,
)

OUT = Path.home() / 'Documents/dev/ettac-paper/figs/adserp'
OUT.mkdir(parents=True, exist_ok=True)
OUT_PDF = OUT / 'paired-return.pdf'

FS = 150
LF_SOS = butter(4, 1.6, btype='low', fs=FS, output='sos')
HF_SOS = butter(4, (1.6, 4.0), btype='band', fs=FS, output='sos')
MIN_SAMPLES = 150


def visit_segments(fix, tops, n_res):
    first, ret = {}, {}
    max_seen = -1
    for f in fix:
        pos = assign_fixation_to_position(f['y'], tops, n_res)
        if pos is None or pos < 0:
            continue
        win = (f['t'], f['t'] + f['d'])
        if pos < max_seen:
            ret.setdefault(pos, []).append(win)
        else:
            first.setdefault(pos, []).append(win)
            if pos > max_seen:
                max_seen = pos
    return first, ret


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    return float(lf_p / hf_p) if hf_p >= 1e-20 else None


def build_paired_records():
    """Reproduce the typed row of lfhf_first_vs_return_paired."""
    import json as _json
    trial_ids = sorted(_json.load(open(
        ROOT / 'AdSERP/data/butterworth-lfhf-by-position.json')).keys())
    rows = []
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            continue
        ts = np.asarray(pupil['ts'])
        pd = np.asarray(pupil['clean_pd'])
        if len(pd) < MIN_SAMPLES * 2:
            continue
        lf = sosfiltfilt(LF_SOS, pd)
        hf = sosfiltfilt(HF_SOS, pd)
        fix = load_fixations(tid)
        if not fix:
            continue
        tops = typed_aoi_tops(tid)
        if not tops:
            continue
        first, ret = visit_segments(fix, tops, len(tops))
        for pos in first:
            if pos not in ret:
                continue
            f1 = lfhf_for_windows(lf, hf, ts, first[pos])
            r1 = lfhf_for_windows(lf, hf, ts, ret[pos])
            if f1 is None or r1 is None:
                continue
            rows.append({'tid': tid, 'pos': pos,
                         'first': f1, 'return': r1, 'delta': r1 - f1})
    return rows


def main():
    print('[paired-return-fig] Building paired records under typed...', file=sys.stderr)
    records = build_paired_records()
    print(f'  N paired = {len(records):,}', file=sys.stderr)

    deltas = np.array([r['delta'] for r in records])
    firsts = np.array([r['first'] for r in records])
    returns = np.array([r['return'] for r in records])
    poss = np.array([r['pos'] for r in records])

    median_d = np.median(deltas)
    p_two = stats.wilcoxon(deltas, alternative='two-sided').pvalue
    pct_pos = 100 * (deltas > 0).mean()

    plt.rcParams.update({
        'font.size': 9, 'font.family': 'serif',
        'pdf.fonttype': 42, 'ps.fonttype': 42,
    })

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.0, 3.0),
                                    gridspec_kw={'width_ratios': [1.0, 1.0],
                                                 'wspace': 0.30})

    # ── Panel A: paired scatter ──
    # Log-log scatter (LF/HF spans 1-2 orders of magnitude)
    cap = 200
    fc = np.clip(firsts, 0.5, cap)
    rc = np.clip(returns, 0.5, cap)
    axL.scatter(fc, rc, s=4, alpha=0.18, color='#1f4e8c', edgecolor='none', zorder=2)
    # Identity diagonal
    diag_max = max(fc.max(), rc.max())
    axL.plot([0.5, diag_max], [0.5, diag_max], color='#999999',
             linestyle=(0, (3, 3)), linewidth=0.8, zorder=1)
    axL.set_xscale('log')
    axL.set_yscale('log')
    axL.set_xlabel('First-visit LF/HF')
    axL.set_ylabel('Return-visit LF/HF')
    axL.set_xlim(0.5, cap)
    axL.set_ylim(0.5, cap)
    axL.set_title(f'(a) Paired within-item ($N$ = {len(records):,})',
                  loc='left', fontsize=9, pad=4)
    axL.tick_params(axis='both', length=3, pad=2)
    axL.spines['top'].set_visible(False)
    axL.spines['right'].set_visible(False)
    axL.text(0.05, 0.93,
             f'median $\\Delta$ = {median_d:+.2f}\n{pct_pos:.0f}% above identity\n$p$ < 10$^{{-22}}$',
             transform=axL.transAxes, fontsize=8, va='top',
             color='#222222',
             bbox=dict(facecolor='#fafaf8', edgecolor='#cccccc', alpha=0.9, pad=4))

    # ── Panel B: per-rank Δ forest plot ──
    # Compute per-rank median + 95 % bootstrap CI
    rank_ids = sorted(set(poss.tolist()))
    rank_ids = [r for r in rank_ids if r <= 6]  # P0-6 has enough samples
    rng = np.random.default_rng(42)
    medians = []
    los = []
    his = []
    n_per_rank = []
    for r in rank_ids:
        d = deltas[poss == r]
        if len(d) < 5:
            continue
        boot = np.array([
            np.median(rng.choice(d, size=len(d), replace=True))
            for _ in range(2000)
        ])
        medians.append(float(np.median(d)))
        los.append(float(np.percentile(boot, 2.5)))
        his.append(float(np.percentile(boot, 97.5)))
        n_per_rank.append(len(d))

    rank_arr = np.array(rank_ids[:len(medians)])
    medians_arr = np.array(medians)
    err_lo = medians_arr - np.array(los)
    err_hi = np.array(his) - medians_arr
    axR.axhline(0, color='#999999', linewidth=0.8, linestyle=(0, (3, 3)))
    axR.errorbar(rank_arr, medians_arr,
                 yerr=np.vstack([err_lo, err_hi]),
                 fmt='o', color='#1f4e8c', markersize=5,
                 elinewidth=1.0, capsize=3, capthick=0.8)
    for r, m, n in zip(rank_arr, medians_arr, n_per_rank):
        axR.text(r, m + 1.5, f'{n:,}', ha='center', fontsize=7, color='#555555')
    axR.set_xticks(rank_arr)
    axR.set_xlabel('Display rank')
    axR.set_ylabel('Median $\\Delta$ (return − first)')
    axR.set_title('(b) Per-rank paired $\\Delta$',
                  loc='left', fontsize=9, pad=4)
    axR.tick_params(axis='both', length=3, pad=2)
    axR.spines['top'].set_visible(False)
    axR.spines['right'].set_visible(False)
    axR.grid(True, alpha=0.25, linewidth=0.6, axis='y')

    plt.tight_layout(pad=0.4)
    plt.savefig(OUT_PDF)
    plt.savefig(OUT_PDF.with_suffix('.png'), dpi=200)
    print(f'wrote {OUT_PDF}', file=sys.stderr)


if __name__ == '__main__':
    main()
