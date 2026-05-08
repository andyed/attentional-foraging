"""Pupil + cursor decision-moment locking — three events, one clicked trial.

Tests Andy's hypothesis: as soon as strong scent is discovered, that's when
mouse moves; pupil tracks the decision moment.

For each clicked trial:
  Event A — first fixation on the click target = gaze-landing (proposed
            scent-detection moment)
  Event B — last fixation on the click target = pre-click commitment
  Event C — click event = motor expression

Time-lock RIPA2 (per-fixation pupil amplitude) and cursor velocity around
each event. Peak timing across locks tells us:
  - Peak at A only: decision = scent detection, pupil tracks cognitive moment
  - Peak at C only: decision = motor commit, pupil tracks button press
  - Peak at A and continues through C: decision crystallizes over window
  - Peak at B: decision = pre-click confirmation read

Cursor velocity locking tests the "cursor moves when scent detected" prediction:
  - If cursor velocity ramps up at A: scent-detection triggers motor
  - If cursor velocity ramps up at C only: cursor is purely motor commit

Output:
  scripts/output/decision_moment_locking/summary.json
  scripts/output/decision_moment_locking/timeline_panel.png
"""
from __future__ import annotations

import json
import math
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
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/decision_moment_locking'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FS = 150
PRE_MS = 2000
POST_MS = 2000
BIN_MS = 20

RC = {
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "serif",
    "font.serif": ["Georgia", "Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "xtick.labelsize": 10, "ytick.labelsize": 9, "legend.fontsize": 10,
    "figure.facecolor": "#fafaf8", "axes.facecolor": "#fafaf8",
    "savefig.facecolor": "#fafaf8", "axes.edgecolor": "#222222",
    "axes.labelcolor": "#222222", "xtick.color": "#222222",
    "ytick.color": "#222222", "text.color": "#222222",
    "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
}
COLOR_FIRST = "#117733"   # green — gaze-landing / scent
COLOR_LAST = "#d4a574"    # amber — pre-click
COLOR_CLICK = "#7c4dff"   # purple — motor commit


def make_axis():
    n = (PRE_MS + POST_MS) // BIN_MS
    return np.arange(-PRE_MS, POST_MS, BIN_MS) + BIN_MS / 2, n


def time_lock(ts: np.ndarray, signal: np.ndarray, event_t: float) -> np.ndarray | None:
    rel = ts - event_t
    mask = (rel >= -PRE_MS) & (rel < POST_MS)
    n_bins = (PRE_MS + POST_MS) // BIN_MS
    if mask.sum() < n_bins // 4:
        return None
    binned = np.full(n_bins, np.nan)
    for i in range(n_bins):
        bin_lo = -PRE_MS + i * BIN_MS
        bin_hi = bin_lo + BIN_MS
        bin_mask = mask & (rel >= bin_lo) & (rel < bin_hi)
        if bin_mask.any():
            binned[i] = float(np.mean(signal[bin_mask]))
    return binned


def cursor_velocity_signal(events, t_start: float, t_end: float
                            ) -> tuple[np.ndarray, np.ndarray]:
    """Return (timestamps, velocities) interpolated to common grid."""
    moves = [(t, x, y) for (t, et, x, y) in events if et == 'mousemove']
    if len(moves) < 2:
        return np.array([]), np.array([])
    mt = np.array([m[0] for m in moves], dtype=float)
    mx = np.array([m[1] for m in moves], dtype=float)
    my = np.array([m[2] for m in moves], dtype=float)
    # Velocity between consecutive points
    dt = np.diff(mt)
    dt[dt < 1] = 1  # avoid div by zero
    vx = np.diff(mx) / (dt / 1000)  # px/s
    vy = np.diff(my) / (dt / 1000)
    speed = np.sqrt(vx ** 2 + vy ** 2)
    # Timestamps for velocity = midpoint
    vt = (mt[:-1] + mt[1:]) / 2
    # Interpolate to a regular 20ms grid
    grid = np.arange(t_start, t_end, BIN_MS)
    if len(grid) == 0:
        return np.array([]), np.array([])
    speed_interp = np.interp(grid, vt, speed)
    return grid, speed_interp


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    axis, _ = make_axis()
    traces = {
        'ripa2_first': [], 'ripa2_last': [], 'ripa2_click': [],
        'cursor_first': [], 'cursor_last': [], 'cursor_click': [],
    }
    deltas_first_to_last = []
    deltas_first_to_click = []
    n_skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}  ('
                  f'{len(traces["ripa2_first"]):,} traces)', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            n_skipped += 1
            continue
        ts = pupil['ts']
        signal = pupil['clean_pd']
        if len(signal) < FS * 4:
            continue
        ripa2 = compute_ripa2_signal(signal)

        events, _, clicks = load_mouse_events(tid)
        if not clicks:
            continue
        click_t = float(clicks[-1][0])

        # Identify click position
        n_results = count_results_html(tid) or 11
        doc_h, _, _ = get_trial_meta(tid)
        if doc_h is None:
            continue
        tops = result_band_tops(n_results, doc_h)
        # Use last click's y as the target
        click_y = float(clicks[-1][2])
        target_pos = assign_fixation_to_position(click_y, tops, n_results)
        if target_pos is None:
            continue

        # Find first and last fixation on click target
        fixations = load_fixations(tid)
        if not fixations:
            continue
        target_fixs = []
        for f in fixations:
            p = assign_fixation_to_position(f['y'], tops, n_results)
            if p == target_pos and f['t'] < click_t:
                target_fixs.append(f)
        if len(target_fixs) < 1:
            continue
        first_fix_t = float(target_fixs[0]['t'])
        last_fix_t = float(target_fixs[-1]['t'])

        deltas_first_to_last.append(last_fix_t - first_fix_t)
        deltas_first_to_click.append(click_t - first_fix_t)

        # RIPA2 traces around all three events
        for label, et in [('first', first_fix_t), ('last', last_fix_t),
                          ('click', click_t)]:
            tr = time_lock(ts, ripa2, et)
            if tr is not None:
                traces[f'ripa2_{label}'].append(tr)

        # Cursor velocity traces around all three
        cgrid, cvel = cursor_velocity_signal(events,
                                              first_fix_t - PRE_MS - 100,
                                              click_t + POST_MS + 100)
        if len(cgrid) >= 5:
            for label, et in [('first', first_fix_t), ('last', last_fix_t),
                              ('click', click_t)]:
                tr = time_lock(cgrid, cvel, et)
                if tr is not None:
                    traces[f'cursor_{label}'].append(tr)

    arrs = {k: np.array(v) if v else None for k, v in traces.items()}
    n = len(traces['ripa2_first'])
    print(f'\n  pupil traces per event: {n:,}', file=sys.stderr)
    print(f'  cursor traces per event: {len(traces["cursor_first"]):,}', file=sys.stderr)
    if deltas_first_to_last:
        d_fl = np.array(deltas_first_to_last)
        d_fc = np.array(deltas_first_to_click)
        print(f'  median (first_fix → last_fix): {np.median(d_fl):.0f} ms',
              file=sys.stderr)
        print(f'  median (first_fix → click):    {np.median(d_fc):.0f} ms',
              file=sys.stderr)

    def trace_mean(arr):
        return None if arr is None or len(arr) == 0 else np.nanmean(arr, axis=0)

    def ci(arr, n_boot=400):
        if arr is None or len(arr) == 0:
            return None, None
        rng = np.random.default_rng(7)
        idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
        boots = np.nanmean(arr[idx], axis=1)
        return np.nanpercentile(boots, 2.5, axis=0), np.nanpercentile(boots, 97.5, axis=0)

    # ── Find peak time in each lock (within plausible window) ─────────────
    # For decision claim, restrict to ±1500 ms around event
    peak_window = (axis >= -1500) & (axis <= 1500)
    summary = {
        'n_traces': int(n),
        'median_first_to_last_ms': float(np.median(deltas_first_to_last))
                                    if deltas_first_to_last else None,
        'median_first_to_click_ms': float(np.median(deltas_first_to_click))
                                    if deltas_first_to_click else None,
    }
    print('\n=== RIPA2 peak time by event lock (peak within ±1500 ms) ===')
    for ev in ('first', 'last', 'click'):
        arr = arrs[f'ripa2_{ev}']
        if arr is None:
            continue
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx_in = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx_in]
        peak_v = m[peak_window][peak_idx_in]
        # Where is the value at t=0?
        zero_idx = np.argmin(np.abs(axis))
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        print(f'  {ev:>5s}-locked:  peak t = {peak_t:+5.0f} ms,  '
              f'peak RIPA2 = {peak_v:.4f},  baseline = {baseline:.4f}, '
              f'  ratio = {peak_v/max(baseline,1e-9):.2f}×')
        summary[f'ripa2_{ev}_peak'] = {
            'time_ms': float(peak_t), 'value': float(peak_v),
            'baseline': baseline,
            'peak_ratio': float(peak_v / max(baseline, 1e-9)),
        }

    print('\n=== Cursor velocity peak time by event lock ===')
    for ev in ('first', 'last', 'click'):
        arr = arrs[f'cursor_{ev}']
        if arr is None:
            continue
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx_in = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx_in]
        peak_v = m[peak_window][peak_idx_in]
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        print(f'  {ev:>5s}-locked:  peak t = {peak_t:+5.0f} ms,  '
              f'peak speed = {peak_v:.0f} px/s,  baseline = {baseline:.0f}, '
              f'  ratio = {peak_v/max(baseline,1e-9):.2f}×')
        summary[f'cursor_{ev}_peak'] = {
            'time_ms': float(peak_t), 'value': float(peak_v),
            'baseline': baseline,
            'peak_ratio': float(peak_v / max(baseline, 1e-9)),
        }

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))

    # ── Visualization: 2 rows (RIPA2, cursor velocity) × 3 cols (events) ────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True)

    panels = [
        # (row, col, signal_key, color, title)
        (0, 0, 'ripa2_first', COLOR_FIRST,  '(A) RIPA2  —  locked to first fixation on target  (gaze-landing)'),
        (0, 1, 'ripa2_last',  COLOR_LAST,   '(B) RIPA2  —  locked to last fixation on target  (pre-click)'),
        (0, 2, 'ripa2_click', COLOR_CLICK,  '(C) RIPA2  —  locked to click event  (motor commit)'),
        (1, 0, 'cursor_first', COLOR_FIRST, '(D) Cursor velocity  —  locked to first fixation'),
        (1, 1, 'cursor_last',  COLOR_LAST,  '(E) Cursor velocity  —  locked to last fixation'),
        (1, 2, 'cursor_click', COLOR_CLICK, '(F) Cursor velocity  —  locked to click'),
    ]

    for row, col, key, color, title in panels:
        ax = axes[row, col]
        arr = arrs[key]
        if arr is None or len(arr) == 0:
            ax.text(0.5, 0.5, 'no data', transform=ax.transAxes,
                    ha='center', va='center', color='#888888')
            continue
        lo, hi = ci(arr)
        m = trace_mean(arr)
        ax.fill_between(axis, lo, hi, color=color, alpha=0.20)
        ax.plot(axis, m, color=color, lw=1.8)
        ax.axvline(0, color='#222222', lw=1.0, ls='--', alpha=0.6)
        ax.set_title(title, fontsize=10.5)
        ax.grid(True, alpha=0.5)
        if col == 0:
            ax.set_ylabel('RIPA2' if row == 0 else 'cursor speed (px/s)')
        if row == 1:
            ax.set_xlabel('time from event (ms)')

    # Annotate the median delays on first-locked panels
    if deltas_first_to_last:
        med_fl = np.median(deltas_first_to_last)
        med_fc = np.median(deltas_first_to_click)
        for row in (0, 1):
            ax = axes[row, 0]
            yt = ax.get_ylim()[1]
            ax.axvline(med_fl, color=COLOR_LAST, lw=0.8, ls=':', alpha=0.7)
            ax.axvline(med_fc, color=COLOR_CLICK, lw=0.8, ls=':', alpha=0.7)
            ax.text(med_fl, yt * 0.95, f'last-fix\n+{med_fl:.0f}ms',
                    ha='center', va='top', fontsize=8, color=COLOR_LAST)
            ax.text(med_fc, yt * 0.85, f'click\n+{med_fc:.0f}ms',
                    ha='center', va='top', fontsize=8, color=COLOR_CLICK)

    fig.suptitle("Pupil + cursor time-locked to three decision-phase events on clicked trials\n"
                 "Tests: does pupil track scent-detection (first-fix), pre-click commit (last-fix), "
                 "or motor expression (click)?", y=0.99, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.95))
    out_png = OUT_DIR / 'timeline_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'timeline_panel.svg', bbox_inches='tight')
    print(f'\n[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
