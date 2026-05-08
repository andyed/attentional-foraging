"""Sanity checks for the peri-click RIPA2 result (ripa2_around_click.py).

Three checks to disambiguate cognitive peri-decision response from saccade /
blink / motor-click artifacts:

  (1) Extended post-window — peri-decision dilation decays slowly over
      ~1500 ms; motor/saccade artifact drops within ~200 ms. Re-run with
      POST_MS = 3000.

  (2) Blink-stratified — exclude trials with any invalid pupil sample
      within ±500 ms of click. If the peak survives, blink-padding
      interpolation isn't the source.

  (3) Gaze-event locking — time-lock to onset of the LAST fixation before
      click instead of the click event itself. If peak still aligns with
      click time, the click event is the locker (likely motor/blink). If
      peak shifts to fixation onset, the gaze event is the locker (cleaner
      cognitive interpretation).

Output:
  scripts/output/ripa2_around_click/sanity_summary.json
  scripts/output/ripa2_around_click/sanity_4panel.png
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

FS = 150
PRE_MS = 3000
POST_MS_EXTENDED = 3000   # check #1
BIN_MS = 20
BLINK_WIN_MS = 500        # check #2: ±500 ms exclusion zone

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_RIPA2 = "#7c4dff"
COLOR_CONTROL = "#888888"
COLOR_GAZE = "#d4a574"


def make_axis(pre_ms: int, post_ms: int) -> tuple[np.ndarray, int]:
    n_bins = (pre_ms + post_ms) // BIN_MS
    axis = np.arange(-pre_ms, post_ms, BIN_MS) + BIN_MS / 2
    return axis, n_bins


def time_lock(ts_ms: np.ndarray, signal: np.ndarray, event_t_ms: float,
              pre_ms: int, post_ms: int) -> np.ndarray | None:
    rel = ts_ms - event_t_ms
    mask = (rel >= -pre_ms) & (rel < post_ms)
    if mask.sum() < ((pre_ms + post_ms) // BIN_MS) // 4:
        return None
    n_bins = (pre_ms + post_ms) // BIN_MS
    binned = np.full(n_bins, np.nan)
    for i in range(n_bins):
        bin_lo = -pre_ms + i * BIN_MS
        bin_hi = bin_lo + BIN_MS
        bin_mask = mask & (rel >= bin_lo) & (rel < bin_hi)
        if bin_mask.any():
            binned[i] = float(np.mean(signal[bin_mask]))
    return binned


def has_blink_near(ts_ms: np.ndarray, validity: np.ndarray,
                   event_t_ms: float, win_ms: int) -> bool:
    """Return True if any invalid sample exists within ±win_ms of event."""
    near = (ts_ms >= event_t_ms - win_ms) & (ts_ms <= event_t_ms + win_ms)
    return bool((validity[near] == 0).any())


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    # Buckets:
    # (1) extended-window click-locked
    # (2a) click-locked, with peri-click blink
    # (2b) click-locked, no peri-click blink
    # (3) last-fixation-before-click locked
    # control: random non-click fixation
    extended_axis, _ = make_axis(PRE_MS, POST_MS_EXTENDED)

    traces_click = []
    traces_blink = []        # has blink ±500ms of click
    traces_noblink = []      # no blink ±500ms of click
    traces_last_fix = []     # gaze-event locked
    traces_control = []
    delta_fix_to_click = []  # ms between last fixation onset and click

    rng = np.random.default_rng(42)
    n_pupil_failed = n_no_clicks = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            n_pupil_failed += 1
            continue
        ts = pupil['ts']
        signal = pupil['clean_pd']
        validity = pupil.get('validity')
        if validity is None:
            # Reconstruct from raw_pd if needed; for our purposes we'll skip if missing
            validity = np.ones(len(ts), dtype=int)
        if len(signal) < FS * 4:
            continue
        ripa2 = compute_ripa2_signal(signal)

        events, scrolls, clicks = load_mouse_events(tid)
        if not clicks:
            n_no_clicks += 1
            continue
        click_t = float(clicks[-1][0])

        # (1) extended-window click-locked
        ext = time_lock(ts, ripa2, click_t, PRE_MS, POST_MS_EXTENDED)
        if ext is not None:
            traces_click.append(ext)

            # (2) blink stratification
            if has_blink_near(ts, np.asarray(validity), click_t, BLINK_WIN_MS):
                traces_blink.append(ext)
            else:
                traces_noblink.append(ext)

        # (3) last-fixation-before-click locking
        fixations = load_fixations(tid)
        if fixations:
            fix_ts = np.array([f['t'] for f in fixations], dtype=float)
            mask = fix_ts < click_t
            if mask.any():
                last_fix_t = float(fix_ts[mask][-1])
                delta_fix_to_click.append(click_t - last_fix_t)
                lf = time_lock(ts, ripa2, last_fix_t, PRE_MS, POST_MS_EXTENDED)
                if lf is not None:
                    traces_last_fix.append(lf)

        # control: random fix far from click
        if fixations:
            fix_ts = np.array([f['t'] for f in fixations], dtype=float)
            mask = np.abs(fix_ts - click_t) > 2000
            if mask.any():
                ctrl_t = float(rng.choice(fix_ts[mask]))
                ctrl = time_lock(ts, ripa2, ctrl_t, PRE_MS, POST_MS_EXTENDED)
                if ctrl is not None:
                    traces_control.append(ctrl)

    print(f'\n  click-locked traces:        {len(traces_click):,}', file=sys.stderr)
    print(f'  with peri-click blink:      {len(traces_blink):,}', file=sys.stderr)
    print(f'  without peri-click blink:   {len(traces_noblink):,}', file=sys.stderr)
    print(f'  last-fix-before-click:      {len(traces_last_fix):,}', file=sys.stderr)
    print(f'  control (non-click fix):    {len(traces_control):,}', file=sys.stderr)
    if delta_fix_to_click:
        d = np.array(delta_fix_to_click)
        print(f'  delta (last_fix → click): med={np.median(d):.0f}ms  '
              f'mean={np.mean(d):.0f}ms  q25={np.percentile(d,25):.0f}  '
              f'q75={np.percentile(d,75):.0f}', file=sys.stderr)

    arr_click = np.array(traces_click)
    arr_blink = np.array(traces_blink) if traces_blink else None
    arr_noblink = np.array(traces_noblink) if traces_noblink else None
    arr_lastfix = np.array(traces_last_fix)
    arr_ctrl = np.array(traces_control)

    def trace_mean(arr):
        if arr is None or len(arr) == 0:
            return None
        return np.nanmean(arr, axis=0)

    def trace_ci(arr, n_boot=500):
        if arr is None or len(arr) == 0:
            return None, None
        n = len(arr)
        rng_loc = np.random.default_rng(7)
        idx = rng_loc.integers(0, n, size=(n_boot, n))
        boots = np.nanmean(arr[idx], axis=1)
        lo = np.nanpercentile(boots, 2.5, axis=0)
        hi = np.nanpercentile(boots, 97.5, axis=0)
        return lo, hi

    # ── 4-panel figure ─────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=False, sharex=False)
    fig.suptitle("Peri-click RIPA2 sanity checks",
                 y=0.995, fontsize=15)

    # Panel A — extended window: does the peak decay slowly (cognitive) or fast (artifact)?
    axA = axes[0, 0]
    if arr_ctrl is not None and len(arr_ctrl) > 0:
        ci_lo, ci_hi = trace_ci(arr_ctrl)
        axA.fill_between(extended_axis, ci_lo, ci_hi, color=COLOR_CONTROL, alpha=0.15)
        axA.plot(extended_axis, trace_mean(arr_ctrl), color=COLOR_CONTROL, lw=1.4,
                 label=f'Control non-click fix  (N = {len(arr_ctrl):,})')
    if arr_click is not None and len(arr_click) > 0:
        ci_lo, ci_hi = trace_ci(arr_click)
        axA.fill_between(extended_axis, ci_lo, ci_hi, color=COLOR_RIPA2, alpha=0.22)
        axA.plot(extended_axis, trace_mean(arr_click), color=COLOR_RIPA2, lw=2.0,
                 label=f'Click event  (N = {len(arr_click):,})')
    axA.axvline(0, color="#222222", lw=1.0, ls="--", alpha=0.6)
    axA.set_xlabel('time from click (ms)')
    axA.set_ylabel('RIPA2 (population-averaged)')
    axA.set_title("(A) Extended post-window  —  artifact decays fast, cognition decays slow")
    axA.legend(loc='upper left', frameon=True, framealpha=0.92, edgecolor="#cccccc")
    axA.grid(True, alpha=0.5)

    # Panel B — blink stratification
    axB = axes[0, 1]
    if arr_blink is not None and len(arr_blink) > 0:
        ci_lo, ci_hi = trace_ci(arr_blink)
        axB.fill_between(extended_axis, ci_lo, ci_hi, color="#cc6677", alpha=0.18)
        axB.plot(extended_axis, trace_mean(arr_blink), color="#cc6677", lw=1.6,
                 label=f'Blink ±500ms of click  (N = {len(arr_blink):,})')
    if arr_noblink is not None and len(arr_noblink) > 0:
        ci_lo, ci_hi = trace_ci(arr_noblink)
        axB.fill_between(extended_axis, ci_lo, ci_hi, color="#117733", alpha=0.18)
        axB.plot(extended_axis, trace_mean(arr_noblink), color="#117733", lw=1.6,
                 label=f'No blink ±500ms  (N = {len(arr_noblink):,})')
    axB.axvline(0, color="#222222", lw=1.0, ls="--", alpha=0.6)
    axB.set_xlabel('time from click (ms)')
    axB.set_ylabel('RIPA2')
    axB.set_title("(B) Blink stratification  —  if peak survives no-blink subset, blink-padding ruled out")
    axB.legend(loc='upper left', frameon=True, framealpha=0.92, edgecolor="#cccccc")
    axB.grid(True, alpha=0.5)

    # Panel C — last fixation onset locking
    axC = axes[1, 0]
    if arr_lastfix is not None and len(arr_lastfix) > 0:
        ci_lo, ci_hi = trace_ci(arr_lastfix)
        axC.fill_between(extended_axis, ci_lo, ci_hi, color=COLOR_GAZE, alpha=0.22)
        axC.plot(extended_axis, trace_mean(arr_lastfix), color=COLOR_GAZE, lw=2.0,
                 label=f'Last fixation onset  (N = {len(arr_lastfix):,})')
    if arr_click is not None and len(arr_click) > 0:
        # Overlay click-locked for comparison
        axC.plot(extended_axis, trace_mean(arr_click), color=COLOR_RIPA2, lw=1.4,
                 alpha=0.6, ls="--",
                 label='Click-locked (for compare)')
    axC.axvline(0, color="#222222", lw=1.0, ls="--", alpha=0.6)
    if delta_fix_to_click:
        med_d = np.median(delta_fix_to_click)
        axC.text(0.02, 0.98,
                 f'median(last_fix → click) = {med_d:.0f} ms\n'
                 f'(if peak shifts ≈this much, gaze locks; if not, motor)',
                 transform=axC.transAxes, ha='left', va='top',
                 fontsize=9, fontstyle='italic', color="#444444",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf8f2",
                           edgecolor="#cccccc", lw=0.5))
    axC.set_xlabel('time from event (ms)')
    axC.set_ylabel('RIPA2')
    axC.set_title("(C) Gaze-event locking  —  is the locker the click action or the final fixation?")
    axC.legend(loc='upper left', frameon=True, framealpha=0.92, edgecolor="#cccccc")
    axC.grid(True, alpha=0.5)

    # Panel D — verdict text
    axD = axes[1, 1]
    axD.axis('off')

    pre_peak_mask = (extended_axis >= -1500) & (extended_axis < 0)
    post_peak_mask = (extended_axis >= 0) & (extended_axis <= 1500)
    decay_mask = (extended_axis >= 500) & (extended_axis <= 1500)

    verdict_lines = ["**Sanity-check verdict:**", ""]

    # Check 1
    if arr_click is not None and len(arr_click) > 0:
        click_mean = trace_mean(arr_click)
        peak_idx = np.nanargmax(click_mean)
        peak_t = extended_axis[peak_idx]
        peak_v = click_mean[peak_idx]
        post_peak_decay_v = np.nanmean(click_mean[decay_mask])
        decay_ratio = post_peak_decay_v / peak_v if peak_v > 0 else float('nan')
        verdict_lines.append(f"(A) peak time = {peak_t:+.0f} ms;  "
                             f"500–1500 ms decay = {decay_ratio:.2f}× peak")
        if decay_ratio < 0.3:
            verdict_lines.append("    fast decay → artifact-flavored")
        elif decay_ratio > 0.5:
            verdict_lines.append("    slow decay → cognitive-flavored")
        else:
            verdict_lines.append("    intermediate decay → ambiguous")
    verdict_lines.append("")

    # Check 2
    if arr_blink is not None and arr_noblink is not None and len(arr_blink) > 0 and len(arr_noblink) > 0:
        blink_mean = trace_mean(arr_blink)
        noblink_mean = trace_mean(arr_noblink)
        blink_peak = np.nanmax(blink_mean[pre_peak_mask | post_peak_mask])
        noblink_peak = np.nanmax(noblink_mean[pre_peak_mask | post_peak_mask])
        ratio = noblink_peak / blink_peak if blink_peak > 0 else float('nan')
        verdict_lines.append(f"(B) blink subset peak = {blink_peak:.3f},  "
                             f"no-blink subset peak = {noblink_peak:.3f}")
        verdict_lines.append(f"    no-blink/blink ratio = {ratio:.2f}")
        if ratio > 0.85:
            verdict_lines.append("    peak survives no-blink subset → blink-padding ruled out")
        else:
            verdict_lines.append("    peak attenuates without blinks → blink-padding may contribute")
    verdict_lines.append("")

    # Check 3 — restrict peak detection to ±1500 ms around the locking event
    # (the full window has noisy +2-3s spikes that nanargmax catches otherwise)
    peak_search = (extended_axis >= -1500) & (extended_axis <= 1500)
    if arr_lastfix is not None and len(arr_lastfix) > 0 and arr_click is not None and len(arr_click) > 0:
        lf_mean = trace_mean(arr_lastfix)
        cl_mean = trace_mean(arr_click)
        lf_peak_t = extended_axis[peak_search][np.nanargmax(lf_mean[peak_search])]
        cl_peak_t = extended_axis[peak_search][np.nanargmax(cl_mean[peak_search])]
        med_d = float(np.median(delta_fix_to_click))
        verdict_lines.append(f"(C) click-locked peak = {cl_peak_t:+.0f} ms")
        verdict_lines.append(f"    last-fix-locked peak = {lf_peak_t:+.0f} ms")
        verdict_lines.append(f"    median (last_fix → click) = {med_d:.0f} ms")
        # If lf_peak_t shifted by approximately med_d toward 0, gaze is the locker
        shift = lf_peak_t - cl_peak_t
        if abs(shift - med_d) < 100:
            verdict_lines.append(f"    shift ≈ {shift:+.0f} ms ≈ {med_d:.0f} → gaze is the locker (cognitive flavor)")
        elif abs(shift) < 100:
            verdict_lines.append(f"    no shift → click event is the locker (motor flavor)")
        else:
            verdict_lines.append(f"    shift {shift:+.0f} ms — partial gaze coupling, ambiguous")

    axD.text(0.02, 0.98, "\n".join(verdict_lines),
             transform=axD.transAxes, ha='left', va='top',
             fontsize=10, family='serif',
             bbox=dict(boxstyle="round,pad=0.6", facecolor="#fdf8f2",
                       edgecolor="#dddddd", lw=0.6))

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    out_png = OUT_DIR / 'sanity_4panel.png'
    out_svg = OUT_DIR / 'sanity_4panel.svg'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(out_svg, bbox_inches='tight')
    print(f'\n[out] {out_png.relative_to(ROOT)}', file=sys.stderr)

    # ── Summary JSON ──────────────────────────────────────────────────
    summary = {
        'n_click_locked': int(len(arr_click)),
        'n_with_blink': int(len(arr_blink) if arr_blink is not None else 0),
        'n_no_blink':   int(len(arr_noblink) if arr_noblink is not None else 0),
        'n_last_fix':   int(len(arr_lastfix)),
        'n_control':    int(len(arr_ctrl)),
        'verdict_lines': verdict_lines,
    }
    if delta_fix_to_click:
        d = np.array(delta_fix_to_click)
        summary['last_fix_to_click_ms'] = {
            'median': float(np.median(d)),
            'mean':   float(np.mean(d)),
            'q25':    float(np.percentile(d, 25)),
            'q75':    float(np.percentile(d, 75)),
        }
    out = OUT_DIR / 'sanity_summary.json'
    out.write_text(json.dumps(summary, indent=2))
    print(f'[out] {out.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
