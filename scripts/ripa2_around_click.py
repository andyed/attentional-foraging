"""Time-locked RIPA2 trajectory around the click event — empirical centerpiece
for the RIPA2 unique story.

Gwizdka 2022 talk slide 8: "Largest pupil size before relevance decision."
This script tests whether AdSERP RIPA2 (per-trial continuous trajectory)
peaks pre-click — the SERP-side analog of the talk-slide peri-decision claim.

Methodological note (re Jayawardena 2026 §3.4.2 reliability floor):
  - The paper's ≥4 s/phase floor is for SINGLE-TRIAL CL phase means.
  - Here we compute RIPA2 on the full-trial pupil signal (well above the
    floor), then extract time-locked windows around clicks. Aggregating
    across N = 2,700+ click events smooths per-event noise; this is the
    standard event-related-potential approach.
  - We do NOT make per-event single-trial CL claims. We make a population-
    averaged peri-click trajectory claim.

Pipeline:
  1. For each trial: compute continuous RIPA2 signal via compute_ripa2_signal
  2. For each click event: extract signal in [t_click - 3000, t_click + 1000] ms
  3. Resample to a common time-from-click axis (10 ms bins → 401 points)
  4. Average across all click events
  5. Compare clicked-position trace to control: random non-click fixation
     timestamps in same trials (matched for trial-time)
  6. Plot + save trace + summary stats

Output:
  scripts/output/ripa2_around_click/summary.json
  scripts/output/ripa2_around_click/peri_click_trace.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_pupil_trial, load_mouse_events, load_fixations,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/ripa2_around_click'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FS = 150
PRE_MS = 3000
POST_MS = 1000
BIN_MS = 20
N_BINS = (PRE_MS + POST_MS) // BIN_MS  # = 200 bins
TIME_AXIS_MS = np.arange(-PRE_MS, POST_MS, BIN_MS) + BIN_MS / 2  # bin centers

# Editorial palette (matches viz_ripa2_lfhf style)
RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 12, "axes.titlesize": 14, "axes.labelsize": 12,
    "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_RIPA2 = "#7c4dff"
COLOR_CONTROL = "#888888"


def time_locked_window(ts_ms: np.ndarray, signal: np.ndarray,
                       event_t_ms: float) -> np.ndarray | None:
    """Bin signal into 20 ms windows centered on event."""
    rel = ts_ms - event_t_ms
    mask = (rel >= -PRE_MS) & (rel < POST_MS)
    if mask.sum() < N_BINS // 4:  # need at least a quarter of bins covered
        return None
    binned = np.full(N_BINS, np.nan)
    for i in range(N_BINS):
        bin_lo = -PRE_MS + i * BIN_MS
        bin_hi = bin_lo + BIN_MS
        bin_mask = mask & (rel >= bin_lo) & (rel < bin_hi)
        if bin_mask.any():
            binned[i] = float(np.mean(signal[bin_mask]))
    return binned


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    click_traces: list[np.ndarray] = []
    control_traces: list[np.ndarray] = []
    n_pupil_failed = 0
    n_no_clicks = 0

    rng = np.random.default_rng(42)

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}  (clicks: {len(click_traces):,})',
                  file=sys.stderr)

        pupil = load_pupil_trial(tid)
        if pupil is None:
            n_pupil_failed += 1
            continue
        ts = pupil['ts']
        signal = pupil['clean_pd']
        if len(signal) < FS * 4:
            continue
        ripa2 = compute_ripa2_signal(signal)

        events, scrolls, clicks = load_mouse_events(tid)
        if not clicks:
            n_no_clicks += 1
            continue

        # The "decision click" is the last click in the trial (matches
        # ripa2-by-position.json convention which uses clicks[-1])
        click_t_ms = float(clicks[-1][0])

        binned = time_locked_window(ts, ripa2, click_t_ms)
        if binned is not None:
            click_traces.append(binned)

        # Control: pick a random fixation timestamp in the same trial that's
        # NOT within ±2 s of the click (so we sample a non-decision moment in
        # the same task context). Matches trial-time without aligning to a
        # decision event.
        fixations = load_fixations(tid)
        if fixations:
            fix_ts = np.array([f['t'] for f in fixations], dtype=float)
            mask = np.abs(fix_ts - click_t_ms) > 2000
            if mask.any():
                eligible = fix_ts[mask]
                control_t = float(rng.choice(eligible))
                ctrl_binned = time_locked_window(ts, ripa2, control_t)
                if ctrl_binned is not None:
                    control_traces.append(ctrl_binned)

    print(f'\n  click event traces:   {len(click_traces):,}', file=sys.stderr)
    print(f'  control event traces: {len(control_traces):,}', file=sys.stderr)
    print(f'  skipped: pupil failed = {n_pupil_failed}, no clicks = {n_no_clicks}',
          file=sys.stderr)

    click_arr = np.array(click_traces)
    ctrl_arr = np.array(control_traces)

    # Mean and 95% bootstrap CI per bin
    def ci_bootstrap(arr: np.ndarray, n_boot: int = 1000, alpha: float = 0.05):
        n = len(arr)
        rng_loc = np.random.default_rng(7)
        idx = rng_loc.integers(0, n, size=(n_boot, n))
        # nanmean per bootstrap sample
        boots = np.nanmean(arr[idx], axis=1)
        lo = np.nanpercentile(boots, 100 * alpha / 2, axis=0)
        hi = np.nanpercentile(boots, 100 * (1 - alpha / 2), axis=0)
        return lo, hi

    click_mean = np.nanmean(click_arr, axis=0)
    ctrl_mean = np.nanmean(ctrl_arr, axis=0)
    click_lo, click_hi = ci_bootstrap(click_arr)
    ctrl_lo, ctrl_hi = ci_bootstrap(ctrl_arr)

    # ── Detect pre-click peak ────────────────────────────────────────
    # Pre-click region: t in [-1500, 0] ms
    pre_mask = (TIME_AXIS_MS >= -1500) & (TIME_AXIS_MS <= 0)
    pre_max_idx = np.nanargmax(click_mean[pre_mask])
    pre_max_t = TIME_AXIS_MS[pre_mask][pre_max_idx]
    pre_max_v = click_mean[pre_mask][pre_max_idx]

    # Compare pre-click peak (window [-1500, 0]) to early baseline ([-3000, -2000])
    early_mask = (TIME_AXIS_MS >= -3000) & (TIME_AXIS_MS <= -2000)
    pre_peak_window_mask = (TIME_AXIS_MS >= -1500) & (TIME_AXIS_MS <= -100)

    early_per_event = np.nanmean(click_arr[:, early_mask], axis=1)
    pre_peak_per_event = np.nanmean(click_arr[:, pre_peak_window_mask], axis=1)
    pre_max_per_event = np.nanmax(click_arr[:, pre_peak_window_mask], axis=1)
    pre_med_per_event = np.nanmedian(click_arr[:, pre_peak_window_mask], axis=1)
    valid = ~(np.isnan(early_per_event) | np.isnan(pre_peak_per_event) |
              np.isnan(pre_max_per_event) | np.isnan(pre_med_per_event))
    early_per_event = early_per_event[valid]
    pre_peak_per_event = pre_peak_per_event[valid]
    pre_max_per_event = pre_max_per_event[valid]
    pre_med_per_event = pre_med_per_event[valid]

    from scipy.stats import wilcoxon
    w_pre = wilcoxon(pre_peak_per_event, early_per_event, alternative='greater')
    w_max = wilcoxon(pre_max_per_event, early_per_event, alternative='greater')
    w_med = wilcoxon(pre_med_per_event, early_per_event, alternative='greater')

    # Click-vs-control at pre-peak window (paired by trial — but lengths may differ)
    # Use unpaired Mann-Whitney instead since traces are aligned to different events
    from scipy.stats import mannwhitneyu
    ctrl_pre_peak_per_event = np.nanmean(ctrl_arr[:, pre_peak_window_mask], axis=1)
    ctrl_pre_peak_per_event = ctrl_pre_peak_per_event[~np.isnan(ctrl_pre_peak_per_event)]
    u_clk_vs_ctrl = mannwhitneyu(pre_peak_per_event,
                                  ctrl_pre_peak_per_event,
                                  alternative='greater')

    summary = {
        'n_click_traces': int(len(click_traces)),
        'n_control_traces': int(len(control_traces)),
        'pre_peak': {
            'time_ms': float(pre_max_t),
            'value': float(pre_max_v),
        },
        'early_baseline_window_ms': [-3000, -2000],
        'pre_peak_window_ms': [-1500, -100],
        'wilcoxon_pre_peak_gt_early_baseline': {
            'statistic': float(w_pre.statistic),
            'p': float(w_pre.pvalue),
            'n': int(len(pre_peak_per_event)),
            'note': 'pre_peak_per_event is mean of RIPA2 over [-1500, -100] ms per event (despite the misleading variable name).',
        },
        'wilcoxon_per_event_max_gt_early_baseline': {
            'statistic': float(w_max.statistic),
            'p': float(w_max.pvalue),
            'n': int(len(pre_max_per_event)),
            'note': 'true peak per event: max of RIPA2 over [-1500, -100] ms vs early-baseline mean per event.',
        },
        'wilcoxon_per_event_median_gt_early_baseline': {
            'statistic': float(w_med.statistic),
            'p': float(w_med.pvalue),
            'n': int(len(pre_med_per_event)),
            'note': 'median of RIPA2 over [-1500, -100] ms vs early-baseline mean per event.',
        },
        'mw_clicked_pre_peak_gt_control': {
            'statistic': float(u_clk_vs_ctrl.statistic),
            'p': float(u_clk_vs_ctrl.pvalue),
            'n_clicked': int(len(pre_peak_per_event)),
            'n_control': int(len(ctrl_pre_peak_per_event)),
        },
        'note': (
            'RIPA2 computed on full-trial pupil signal (well above paper s '
            '4 s reliability floor); event-locked windows extracted from that '
            'precomputed trajectory. Population-averaged peri-click trace; not '
            'a per-event single-trial CL claim.'
        ),
    }

    print('\n=== Pre-click peak ===')
    print(f'  Time of peak in [-1500, 0] ms:  {pre_max_t:+.0f} ms')
    print(f'  RIPA2 at peak:                  {pre_max_v:.4f}')
    print(f'  Wilcoxon WINDOW-MEAN  > early baseline: p = {w_pre.pvalue:.3g}  '
          f'N = {len(pre_peak_per_event):,}')
    print(f'  Wilcoxon WINDOW-MAX   > early baseline: p = {w_max.pvalue:.3g}  '
          f'N = {len(pre_max_per_event):,}')
    print(f'  Wilcoxon WINDOW-MEDIAN > early baseline: p = {w_med.pvalue:.3g}  '
          f'N = {len(pre_med_per_event):,}')
    print(f'  MW clicked-pre-peak > control:    p = {u_clk_vs_ctrl.pvalue:.3g}  '
          f'(N = {len(pre_peak_per_event):,} vs {len(ctrl_pre_peak_per_event):,})')

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}', file=sys.stderr)

    # ── Plot ──────────────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(9, 5.2))

    # Control band
    ax.fill_between(TIME_AXIS_MS, ctrl_lo, ctrl_hi, color=COLOR_CONTROL,
                    alpha=0.18, label='_nolegend_')
    ax.plot(TIME_AXIS_MS, ctrl_mean, color=COLOR_CONTROL, lw=1.6,
            label=f'Control (random non-click fixation,  N = {len(ctrl_arr):,})')

    # Click band
    ax.fill_between(TIME_AXIS_MS, click_lo, click_hi, color=COLOR_RIPA2,
                    alpha=0.22, label='_nolegend_')
    ax.plot(TIME_AXIS_MS, click_mean, color=COLOR_RIPA2, lw=2.2,
            label=f'Click event,  N = {len(click_arr):,}')

    # Click moment
    ax.axvline(0, color="#222222", lw=1.2, ls="--", alpha=0.7)
    ax.text(0, ax.get_ylim()[1] * 0.97 if ax.get_ylim()[1] else 1, '  click',
            ha='left', va='top', fontsize=10, color="#222222")

    # Mark pre-peak
    ax.axvline(pre_max_t, color=COLOR_RIPA2, lw=1.0, ls=":", alpha=0.6)
    ax.text(pre_max_t, pre_max_v, f'  peak {pre_max_t:+.0f} ms',
            ha='left', va='bottom', fontsize=9, color=COLOR_RIPA2,
            fontstyle='italic')

    ax.set_xlabel('time from click (ms)')
    ax.set_ylabel('RIPA2 (population-averaged)')
    ax.set_title("Peri-click RIPA2 trajectory on AdSERP — "
                 "Gwizdka's pre-decision pupil claim, operationalized",
                 loc='left', pad=10)
    ax.grid(True, alpha=0.5)
    ax.legend(loc='upper left', frameon=True, framealpha=0.92, edgecolor='#cccccc')

    out_png = OUT_DIR / 'peri_click_trace.png'
    out_svg = OUT_DIR / 'peri_click_trace.svg'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(out_svg, bbox_inches='tight')
    print(f'[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
