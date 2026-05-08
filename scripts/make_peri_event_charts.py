"""Peri-event time-series for RIPA2 and LF/HF, click-locked, on a shared
real-time x-axis with both gaze and click event markers visible.

Replaces the comparison_4panel.png framing (which hid the 261 ms gaze→click
arc by locking each panel to its own t=0). This figure puts gaze and click
on the same timeline and lets the reader see RIPA2 fire at *both* events
while LF/HF drifts continuously across the whole arc.

Produces three variants of the same dataset for design comparison:
  variant_A_dual_axis.pdf      -- raw values, dual y-axis
  variant_B_fold_change.pdf    -- log2 fold-change vs baseline, shared y
  variant_C_zscore.pdf         -- z-score from baseline, shared y

Output:
  scripts/output/ripa2_meet_visuals/variant_A_dual_axis.{pdf,png}
  scripts/output/ripa2_meet_visuals/variant_B_fold_change.{pdf,png}
  scripts/output/ripa2_meet_visuals/variant_C_zscore.{pdf,png}
  scripts/output/ripa2_meet_visuals/peri_event_traces.json   (raw bin arrays)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_pupil_trial, load_mouse_events, load_fixations,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/ripa2_meet_visuals'
OUT_DIR.mkdir(parents=True, exist_ok=True)
TRACES_JSON = OUT_DIR / 'peri_event_traces.json'
GAZE_JSON = OUT_DIR / 'peri_event_traces_gaze_locked.json'

FS = 150
PRE_MS = 3000
POST_MS = 1000
BIN_MS = 20
BASELINE_MS = (-3000, -2500)  # far-past window for baseline reference

# RC tuned for paper-quality output. Cream bg matches Duchowski's other figs.
RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_RIPA2 = "#5b3eb8"   # deep purple — RIPA2
COLOR_LFHF  = "#b8722c"   # warm amber  — LF/HF
COLOR_GAZE  = "#666666"   # gaze marker
COLOR_CLICK = "#222222"   # click marker — slightly darker
COLOR_ARC   = "#e8d8b0"   # commitment-arc shade


def lfhf_signal(pupil: np.ndarray) -> np.ndarray:
    """Per-sample LF/HF power ratio (Task Force / Duchowski 2026 bands)."""
    nyq = FS / 2
    lf_b, lf_a = butter(2, [0.04 / nyq, 0.15 / nyq], btype='band')
    hf_b, hf_a = butter(2, [0.15 / nyq, 0.40 / nyq], btype='band')
    lf = filtfilt(lf_b, lf_a, pupil)
    hf = filtfilt(hf_b, hf_a, pupil)
    return (lf ** 2) / (hf ** 2 + 1e-9)


def make_axis() -> tuple[np.ndarray, int]:
    n = (PRE_MS + POST_MS) // BIN_MS
    return np.arange(-PRE_MS, POST_MS, BIN_MS) + BIN_MS / 2, n


def time_lock(ts_ms: np.ndarray, sig: np.ndarray, t0: float) -> np.ndarray | None:
    rel = ts_ms - t0
    mask = (rel >= -PRE_MS) & (rel < POST_MS)
    n_bins = (PRE_MS + POST_MS) // BIN_MS
    if mask.sum() < n_bins // 4:
        return None
    binned = np.full(n_bins, np.nan)
    for i in range(n_bins):
        lo = -PRE_MS + i * BIN_MS
        hi = lo + BIN_MS
        bm = mask & (rel >= lo) & (rel < hi)
        if bm.any():
            binned[i] = float(np.mean(sig[bm]))
    return binned


def walk_trials() -> dict:
    """Walk trials, time-lock both metrics to click, return aggregated arrays."""
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    axis, n_bins = make_axis()
    ripa2_traces: list[np.ndarray] = []
    lfhf_traces:  list[np.ndarray] = []
    last_fix_offsets: list[float] = []
    n_skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            n_skipped += 1
            continue
        ts = pupil['ts']
        sig = pupil['clean_pd']
        if len(sig) < FS * 4:
            continue

        ripa2 = compute_ripa2_signal(sig)
        lf = lfhf_signal(sig)
        # Tame LF/HF heavy tails per-trial (99th-percentile clip).
        lf_cap = float(np.nanpercentile(lf, 99))
        if np.isfinite(lf_cap) and lf_cap > 0:
            lf = np.clip(lf, 0, lf_cap)

        events, scrolls, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        click_t = float(clicks[-1][0])

        tr_r = time_lock(ts, ripa2, click_t)
        tr_l = time_lock(ts, lf, click_t)
        if tr_r is not None and tr_l is not None:
            ripa2_traces.append(tr_r)
            lfhf_traces.append(tr_l)

            fixations = load_fixations(tid)
            if fixations:
                fix_ts = np.array([f['t'] for f in fixations], dtype=float)
                pre = fix_ts[fix_ts < click_t]
                if pre.size:
                    last_fix_offsets.append(float(pre[-1] - click_t))

    R = np.stack(ripa2_traces, axis=0) if ripa2_traces else None
    L = np.stack(lfhf_traces, axis=0) if lfhf_traces else None
    n_per_bin = np.sum(~np.isnan(R), axis=0) if R is not None else None

    # Per-bin nanmean across trials → the headline trace
    with np.errstate(invalid='ignore'):
        ripa2_mean = np.nanmean(R, axis=0)
        lfhf_mean  = np.nanmean(L, axis=0)
        ripa2_se   = np.nanstd(R, axis=0) / np.sqrt(np.maximum(n_per_bin, 1))
        lfhf_se    = np.nanstd(L, axis=0) / np.sqrt(np.maximum(n_per_bin, 1))

    median_gaze_offset = float(np.median(last_fix_offsets)) if last_fix_offsets else -261.0

    print(f'\n  trials retained: {R.shape[0]:,}', file=sys.stderr)
    print(f'  median (last_fix → click): {median_gaze_offset:.0f} ms', file=sys.stderr)

    return {
        'axis_ms': axis.tolist(),
        'ripa2_mean': ripa2_mean.tolist(),
        'ripa2_se':   ripa2_se.tolist(),
        'lfhf_mean':  lfhf_mean.tolist(),
        'lfhf_se':    lfhf_se.tolist(),
        'n_per_bin':  n_per_bin.tolist(),
        'median_gaze_offset_ms': median_gaze_offset,
        'n_trials_total': int(R.shape[0]),
    }


def walk_trials_gaze_locked() -> dict:
    """Variant: time-lock each trial to its OWN last-fix-onset event,
    so the gaze pulse aggregates without smearing.
    Click event becomes the variable here — track offset distribution."""
    trial_ids = get_trial_ids()
    print(f'[walk gaze] {len(trial_ids):,} trials', file=sys.stderr)

    axis, n_bins = make_axis()
    ripa2_traces: list[np.ndarray] = []
    lfhf_traces:  list[np.ndarray] = []
    click_offsets: list[float] = []

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            continue
        ts = pupil['ts']
        sig = pupil['clean_pd']
        if len(sig) < FS * 4:
            continue

        ripa2 = compute_ripa2_signal(sig)
        lf = lfhf_signal(sig)
        lf_cap = float(np.nanpercentile(lf, 99))
        if np.isfinite(lf_cap) and lf_cap > 0:
            lf = np.clip(lf, 0, lf_cap)

        events, scrolls, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        click_t = float(clicks[-1][0])

        fixations = load_fixations(tid)
        if not fixations:
            continue
        fix_ts = np.array([f['t'] for f in fixations], dtype=float)
        pre = fix_ts[fix_ts < click_t]
        if pre.size == 0:
            continue
        last_fix_t = float(pre[-1])

        tr_r = time_lock(ts, ripa2, last_fix_t)
        tr_l = time_lock(ts, lf, last_fix_t)
        if tr_r is not None and tr_l is not None:
            ripa2_traces.append(tr_r)
            lfhf_traces.append(tr_l)
            click_offsets.append(click_t - last_fix_t)

    R = np.stack(ripa2_traces, axis=0)
    L = np.stack(lfhf_traces, axis=0)
    n_per_bin = np.sum(~np.isnan(R), axis=0)

    with np.errstate(invalid='ignore'):
        ripa2_mean = np.nanmean(R, axis=0)
        lfhf_mean  = np.nanmean(L, axis=0)
        ripa2_se   = np.nanstd(R, axis=0) / np.sqrt(np.maximum(n_per_bin, 1))
        lfhf_se    = np.nanstd(L, axis=0) / np.sqrt(np.maximum(n_per_bin, 1))

    co = np.array(click_offsets)
    print(f'\n  trials retained: {R.shape[0]:,}', file=sys.stderr)
    print(f'  click offsets (ms): p5={np.percentile(co,5):.0f} '
          f'p25={np.percentile(co,25):.0f} median={np.median(co):.0f} '
          f'p75={np.percentile(co,75):.0f} p95={np.percentile(co,95):.0f}',
          file=sys.stderr)

    return {
        'axis_ms': axis.tolist(),
        'ripa2_mean': ripa2_mean.tolist(),
        'ripa2_se':   ripa2_se.tolist(),
        'lfhf_mean':  lfhf_mean.tolist(),
        'lfhf_se':    lfhf_se.tolist(),
        'n_per_bin':  n_per_bin.tolist(),
        'click_offsets_ms': click_offsets,
        'n_trials_total': int(R.shape[0]),
    }


# ── Plot helpers ────────────────────────────────────────────────────────

def baseline_window(axis: np.ndarray, mean: np.ndarray) -> tuple[float, float]:
    """Mean and SD of a metric over the baseline window."""
    bm = (axis >= BASELINE_MS[0]) & (axis < BASELINE_MS[1])
    return float(np.nanmean(mean[bm])), float(np.nanstd(mean[bm]))


def add_event_markers(ax, gaze_offset_ms: float):
    ax.axvspan(gaze_offset_ms, 0, color=COLOR_ARC, alpha=0.45, lw=0)
    ax.axvline(gaze_offset_ms, color=COLOR_GAZE, lw=0.9, ls='--')
    ax.axvline(0, color=COLOR_CLICK, lw=1.0, ls='-')
    ymin, ymax = ax.get_ylim()
    yt = ymin + (ymax - ymin) * 0.97
    ax.text(gaze_offset_ms, yt, 'gaze settle',
            ha='right', va='top', fontsize=8, color=COLOR_GAZE,
            rotation=90)
    ax.text(0, yt, 'click',
            ha='right', va='top', fontsize=8, color=COLOR_CLICK,
            rotation=90)


def add_n_panel(fig, gs_n, axis, n_per_bin, gaze_offset_ms):
    axn = fig.add_subplot(gs_n)
    axn.fill_between(axis, 0, n_per_bin, color='#888888', alpha=0.4, lw=0)
    axn.set_xlim(-PRE_MS, POST_MS)
    axn.set_xlabel('time from click (ms)')
    axn.set_ylabel('$N_\\mathrm{trials}$\nper bin', fontsize=8)
    axn.tick_params(axis='both', length=3, pad=2)
    axn.grid(True, alpha=0.25, linewidth=0.6)
    axn.spines['top'].set_visible(False)
    axn.spines['right'].set_visible(False)
    axn.axvspan(gaze_offset_ms, 0, color=COLOR_ARC, alpha=0.45, lw=0)
    axn.axvline(gaze_offset_ms, color=COLOR_GAZE, lw=0.9, ls='--')
    axn.axvline(0, color=COLOR_CLICK, lw=1.0, ls='-')


def plot_variant_A_dual_axis(data):
    """Variant A — raw values, dual y-axis. The Tufte-fraught option."""
    axis = np.asarray(data['axis_ms'])
    r_mean = np.asarray(data['ripa2_mean'])
    r_se   = np.asarray(data['ripa2_se'])
    l_mean = np.asarray(data['lfhf_mean'])
    l_se   = np.asarray(data['lfhf_se'])
    n      = np.asarray(data['n_per_bin'])
    gaze   = data['median_gaze_offset_ms']

    fig = plt.figure(figsize=(8.5, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.0], hspace=0.10)
    ax = fig.add_subplot(gs[0])
    axR = ax.twinx()

    # Order: LF/HF on the left axis (broader trajectory),
    #        RIPA2 on the right (sharper pulse, higher absolute scale change).
    ax.fill_between(axis, l_mean - l_se, l_mean + l_se,
                    color=COLOR_LFHF, alpha=0.18, lw=0)
    ax.plot(axis, l_mean, color=COLOR_LFHF, lw=1.4, label='LF/HF (left)')
    axR.fill_between(axis, r_mean - r_se, r_mean + r_se,
                     color=COLOR_RIPA2, alpha=0.18, lw=0)
    axR.plot(axis, r_mean, color=COLOR_RIPA2, lw=1.4, label='RIPA2 (right)')

    ax.set_ylabel('LF/HF (per-sample power ratio)', color=COLOR_LFHF)
    axR.set_ylabel('RIPA2 ($\\mathrm{LF}^2 - \\mathrm{VLF}^2$)', color=COLOR_RIPA2)
    ax.tick_params(axis='y', labelcolor=COLOR_LFHF)
    axR.tick_params(axis='y', labelcolor=COLOR_RIPA2)

    ax.set_xlim(-PRE_MS, POST_MS)
    ax.set_xticklabels([])
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.spines['top'].set_visible(False)
    axR.spines['top'].set_visible(False)

    add_event_markers(ax, gaze)

    ax.set_title('Peri-click time series — RIPA2 and LF/HF on shared real-time axis '
                 '(N = {:,} trials)'.format(data['n_trials_total']),
                 loc='left', pad=8)

    add_n_panel(fig, gs[1], axis, n, gaze)

    out_pdf = OUT_DIR / 'variant_A_dual_axis.pdf'
    out_png = OUT_DIR / 'variant_A_dual_axis.png'
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close()
    print(f'wrote {out_pdf}', file=sys.stderr)


def plot_variant_B_fold_change(data):
    """Variant B — log2 fold-change vs baseline, shared y-axis."""
    axis = np.asarray(data['axis_ms'])
    r_mean = np.asarray(data['ripa2_mean'])
    l_mean = np.asarray(data['lfhf_mean'])
    n      = np.asarray(data['n_per_bin'])
    gaze   = data['median_gaze_offset_ms']

    r_base, _ = baseline_window(axis, r_mean)
    l_base, _ = baseline_window(axis, l_mean)
    eps = 1e-12
    r_fc = np.log2(np.maximum(r_mean, eps) / max(r_base, eps))
    l_fc = np.log2(np.maximum(l_mean, eps) / max(l_base, eps))

    fig = plt.figure(figsize=(8.5, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.0], hspace=0.10)
    ax = fig.add_subplot(gs[0])

    ax.axhline(0, color='#aaaaaa', lw=0.7, ls=':')
    ax.plot(axis, r_fc, color=COLOR_RIPA2, lw=1.6, label='RIPA2')
    ax.plot(axis, l_fc, color=COLOR_LFHF, lw=1.6, label='LF/HF')

    ax.set_xlim(-PRE_MS, POST_MS)
    ax.set_xticklabels([])
    ax.set_ylabel('$\\log_2$ fold-change vs baseline'
                  f' [{BASELINE_MS[0]}, {BASELINE_MS[1]}] ms')
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='upper left', frameon=False)

    add_event_markers(ax, gaze)

    ax.set_title('Peri-click fold-change — both metrics on shared $\\log_2$ axis '
                 '(N = {:,} trials)'.format(data['n_trials_total']),
                 loc='left', pad=8)

    add_n_panel(fig, gs[1], axis, n, gaze)

    out_pdf = OUT_DIR / 'variant_B_fold_change.pdf'
    out_png = OUT_DIR / 'variant_B_fold_change.png'
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close()
    print(f'wrote {out_pdf}', file=sys.stderr)


def plot_variant_C_zscore(data):
    """Variant C — z-score from baseline, shared linear y-axis."""
    axis = np.asarray(data['axis_ms'])
    r_mean = np.asarray(data['ripa2_mean'])
    l_mean = np.asarray(data['lfhf_mean'])
    n      = np.asarray(data['n_per_bin'])
    gaze   = data['median_gaze_offset_ms']

    r_base_mu, r_base_sd = baseline_window(axis, r_mean)
    l_base_mu, l_base_sd = baseline_window(axis, l_mean)
    eps = 1e-12
    r_z = (r_mean - r_base_mu) / max(r_base_sd, eps)
    l_z = (l_mean - l_base_mu) / max(l_base_sd, eps)

    fig = plt.figure(figsize=(8.5, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.0], hspace=0.10)
    ax = fig.add_subplot(gs[0])

    ax.axhline(0, color='#aaaaaa', lw=0.7, ls=':')
    ax.plot(axis, r_z, color=COLOR_RIPA2, lw=1.6, label='RIPA2')
    ax.plot(axis, l_z, color=COLOR_LFHF, lw=1.6, label='LF/HF')

    ax.set_xlim(-PRE_MS, POST_MS)
    ax.set_xticklabels([])
    ax.set_ylabel(f'$z$-score vs baseline\n[{BASELINE_MS[0]}, {BASELINE_MS[1]}] ms')
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='upper left', frameon=False)

    add_event_markers(ax, gaze)

    ax.set_title('Peri-click z-score — both metrics on shared $z$ axis '
                 '(N = {:,} trials)'.format(data['n_trials_total']),
                 loc='left', pad=8)

    add_n_panel(fig, gs[1], axis, n, gaze)

    out_pdf = OUT_DIR / 'variant_C_zscore.pdf'
    out_png = OUT_DIR / 'variant_C_zscore.png'
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close()
    print(f'wrote {out_pdf}', file=sys.stderr)


def plot_variant_D_gaze_locked(data):
    """Variant D — time-locked to last-fix-onset (gaze settle) rather than
    click. Eliminates the gaze-event smearing that plagued click-locked
    aggregates. Click event becomes the variable, shown as a histogram band."""
    axis = np.asarray(data['axis_ms'])
    r_mean = np.asarray(data['ripa2_mean'])
    r_se   = np.asarray(data['ripa2_se'])
    l_mean = np.asarray(data['lfhf_mean'])
    l_se   = np.asarray(data['lfhf_se'])
    n      = np.asarray(data['n_per_bin'])
    click_offsets = np.array(data['click_offsets_ms'])

    fig = plt.figure(figsize=(8.5, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.0], hspace=0.10)
    ax = fig.add_subplot(gs[0])
    axR = ax.twinx()

    # Click-offset distribution shaded as a kernel-density band along the bottom
    p25, p50, p75 = np.percentile(click_offsets, [25, 50, 75])
    ax.axvspan(p25, p75, color='#d8e0e8', alpha=0.45, lw=0,
               label=f'click 25-75%ile [{p25:.0f}, {p75:.0f}] ms')

    ax.fill_between(axis, l_mean - l_se, l_mean + l_se,
                    color=COLOR_LFHF, alpha=0.18, lw=0)
    ax.plot(axis, l_mean, color=COLOR_LFHF, lw=1.4)
    axR.fill_between(axis, r_mean - r_se, r_mean + r_se,
                     color=COLOR_RIPA2, alpha=0.18, lw=0)
    axR.plot(axis, r_mean, color=COLOR_RIPA2, lw=1.4)

    ax.set_ylabel('LF/HF (per-sample power ratio)', color=COLOR_LFHF)
    axR.set_ylabel('RIPA2 ($\\mathrm{LF}^2 - \\mathrm{VLF}^2$)', color=COLOR_RIPA2)
    ax.tick_params(axis='y', labelcolor=COLOR_LFHF)
    axR.tick_params(axis='y', labelcolor=COLOR_RIPA2)

    ax.set_xlim(-PRE_MS, POST_MS)
    ax.set_xticklabels([])
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.spines['top'].set_visible(False)
    axR.spines['top'].set_visible(False)

    # Gaze marker at t=0; click distribution markers
    ax.axvline(0, color=COLOR_GAZE, lw=1.0, ls='--')
    ax.axvline(p50, color=COLOR_CLICK, lw=1.0, ls='-', alpha=0.7)
    ymin, ymax = ax.get_ylim()
    yt = ymin + (ymax - ymin) * 0.97
    ax.text(0, yt, 'gaze settle (t=0)',
            ha='right', va='top', fontsize=8, color=COLOR_GAZE,
            rotation=90)
    ax.text(p50, yt, f'click median (+{p50:.0f} ms)',
            ha='right', va='top', fontsize=8, color=COLOR_CLICK,
            rotation=90)

    ax.set_title('Peri-gaze time series — locked to each trial\'s last-fix-onset '
                 '(N = {:,} trials)'.format(data['n_trials_total']),
                 loc='left', pad=8)

    # N per bin in lower panel
    axn = fig.add_subplot(gs[1])
    axn.fill_between(axis, 0, n, color='#888888', alpha=0.4, lw=0)
    axn.set_xlim(-PRE_MS, POST_MS)
    axn.set_xlabel('time from gaze settle (ms)')
    axn.set_ylabel('$N_\\mathrm{trials}$\nper bin', fontsize=8)
    axn.tick_params(axis='both', length=3, pad=2)
    axn.grid(True, alpha=0.25, linewidth=0.6)
    axn.spines['top'].set_visible(False)
    axn.spines['right'].set_visible(False)
    axn.axvspan(p25, p75, color='#d8e0e8', alpha=0.45, lw=0)
    axn.axvline(0, color=COLOR_GAZE, lw=0.9, ls='--')
    axn.axvline(p50, color=COLOR_CLICK, lw=1.0, ls='-', alpha=0.7)

    out_pdf = OUT_DIR / 'variant_D_gaze_locked.pdf'
    out_png = OUT_DIR / 'variant_D_gaze_locked.png'
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close()
    print(f'wrote {out_pdf}', file=sys.stderr)


def main():
    plt.rcParams.update(RC)

    if TRACES_JSON.exists():
        print(f'[reuse] loading cached traces from {TRACES_JSON}', file=sys.stderr)
        with open(TRACES_JSON) as f:
            data = json.load(f)
    else:
        data = walk_trials()
        with open(TRACES_JSON, 'w') as f:
            json.dump(data, f)
        print(f'wrote {TRACES_JSON}', file=sys.stderr)

    plot_variant_A_dual_axis(data)
    plot_variant_B_fold_change(data)
    plot_variant_C_zscore(data)

    if GAZE_JSON.exists():
        print(f'[reuse] loading cached gaze-locked traces from {GAZE_JSON}',
              file=sys.stderr)
        with open(GAZE_JSON) as f:
            gdata = json.load(f)
    else:
        gdata = walk_trials_gaze_locked()
        with open(GAZE_JSON, 'w') as f:
            json.dump(gdata, f)
        print(f'wrote {GAZE_JSON}', file=sys.stderr)

    plot_variant_D_gaze_locked(gdata)


if __name__ == '__main__':
    main()
