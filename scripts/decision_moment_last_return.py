"""Decision-moment locking, refined again: LAST return-to-target before click.

Previous (decision_moment_return.py) defined "return event" as the FIRST
fixation on target after any other-position visit. Median return-to-click
was 11.6 s — still capturing multiple back-and-forth visits. The actual
decision-moment gaze event is the LAST gaze return — the start of the final
target-run that ends in the click.

This script identifies, for each clicked trial:

  LAST_RETURN — first fixation in the FINAL contiguous run of target
                fixations that ends with the click. (If the trial is
                DIRECT, last_return = first_fix.)

Then time-locks RIPA2 + cursor velocity around this event. Compares to
click-locked traces. Tests whether the cursor-leading-gaze pattern (panel G
of decision_moment_return — cursor velocity peaks ~430 ms before return)
holds at the cleaner LAST_RETURN event.

If cursor still leads gaze at LAST_RETURN, the cognition-leads-motor model
is confirmed at the precise decision moment. If cursor signal collapses,
the previous finding was an artifact of averaging over earlier returns.

Output:
  scripts/output/decision_moment_last_return/summary.json
  scripts/output/decision_moment_last_return/timeline_panel.png
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
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/decision_moment_last_return'
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
COLOR_LASTRET = "#117733"     # green — last return = decision moment
COLOR_CLICK = "#7c4dff"       # purple — motor commit
COLOR_RIPA2 = "#7c4dff"
COLOR_CURSOR_DARK = "#cc6677"


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


def cursor_velocity(events, t_start, t_end):
    moves = [(t, x, y) for (t, et, x, y) in events if et == 'mousemove']
    if len(moves) < 2:
        return np.array([]), np.array([])
    mt = np.array([m[0] for m in moves], dtype=float)
    mx = np.array([m[1] for m in moves], dtype=float)
    my = np.array([m[2] for m in moves], dtype=float)
    dt = np.diff(mt); dt[dt < 1] = 1
    speed = np.sqrt((np.diff(mx) / (dt / 1000)) ** 2 + (np.diff(my) / (dt / 1000)) ** 2)
    vt = (mt[:-1] + mt[1:]) / 2
    grid = np.arange(t_start, t_end, BIN_MS)
    if len(grid) == 0:
        return np.array([]), np.array([])
    return grid, np.interp(grid, vt, speed)


def find_last_return(fixations, click_t, target_pos, tops, n_results
                     ) -> float | None:
    """Find the first fixation in the FINAL contiguous run of target
    fixations that ends with the click.

    Walk fixations forward, building a run of target fixations. When a
    non-target fixation appears, reset the run. The last run that contains
    a fixation just before click_t is the decision-phase run; its first
    fixation is the LAST_RETURN event.
    """
    runs: list[list[float]] = []
    current: list[float] = []
    for f in fixations:
        if f['t'] >= click_t:
            break
        p = assign_fixation_to_position(f['y'], tops, n_results)
        if p == target_pos:
            current.append(float(f['t']))
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    if not runs:
        return None
    # The "last run" is whichever run touches click_t most recently — by
    # construction, that's the last run in the list (assumes no fixations
    # AFTER click_t are in the list). Take its first element.
    return runs[-1][0]


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    axis, _ = make_axis()
    traces = {
        'ripa2_lastret': [], 'ripa2_click': [],
        'cursor_lastret': [], 'cursor_click': [],
    }
    deltas_lastret_to_click = []
    n_used = n_skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}  '
                  f'(used={n_used:,})', file=sys.stderr)
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
        click_y = float(clicks[-1][2])

        n_results = count_results_html(tid) or 11
        doc_h, _, _ = get_trial_meta(tid)
        if doc_h is None:
            continue
        tops = result_band_tops(n_results, doc_h)
        target_pos = assign_fixation_to_position(click_y, tops, n_results)
        if target_pos is None:
            continue

        fixations = load_fixations(tid)
        if not fixations:
            continue

        last_ret_t = find_last_return(fixations, click_t, target_pos,
                                       tops, n_results)
        if last_ret_t is None:
            continue

        n_used += 1
        deltas_lastret_to_click.append(click_t - last_ret_t)

        # RIPA2 around both events
        for label, et in [('lastret', last_ret_t), ('click', click_t)]:
            tr = time_lock(ts, ripa2, et)
            if tr is not None:
                traces[f'ripa2_{label}'].append(tr)

        cgrid, cvel = cursor_velocity(events, last_ret_t - PRE_MS - 100,
                                       click_t + POST_MS + 100)
        if len(cgrid) >= 5:
            for label, et in [('lastret', last_ret_t), ('click', click_t)]:
                tr = time_lock(cgrid, cvel, et)
                if tr is not None:
                    traces[f'cursor_{label}'].append(tr)

    arrs = {k: np.array(v) if v else None for k, v in traces.items()}
    print(f'\n  trials used: {n_used:,}', file=sys.stderr)
    if deltas_lastret_to_click:
        d = np.array(deltas_lastret_to_click)
        print(f'  LAST_RETURN → click: median {np.median(d):.0f} ms,  '
              f'q25 {np.percentile(d, 25):.0f},  '
              f'q75 {np.percentile(d, 75):.0f},  '
              f'mean {np.mean(d):.0f}', file=sys.stderr)

    def trace_mean(arr):
        return None if arr is None or len(arr) == 0 else np.nanmean(arr, axis=0)

    def ci(arr, n_boot=400):
        if arr is None or len(arr) == 0:
            return None, None
        rng = np.random.default_rng(7)
        idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
        boots = np.nanmean(arr[idx], axis=1)
        return np.nanpercentile(boots, 2.5, axis=0), np.nanpercentile(boots, 97.5, axis=0)

    peak_window = (axis >= -1500) & (axis <= 1500)
    summary = {
        'n_trials': int(n_used),
        'median_lastret_to_click_ms': float(np.median(deltas_lastret_to_click))
                                      if deltas_lastret_to_click else None,
        'q25_lastret_to_click_ms': float(np.percentile(deltas_lastret_to_click, 25))
                                    if deltas_lastret_to_click else None,
        'q75_lastret_to_click_ms': float(np.percentile(deltas_lastret_to_click, 75))
                                    if deltas_lastret_to_click else None,
    }

    print('\n=== RIPA2 peak time + ratio ===')
    for ev in ('lastret', 'click'):
        arr = arrs[f'ripa2_{ev}']
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx]
        peak_v = m[peak_window][peak_idx]
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        ratio = peak_v / max(baseline, 1e-9)
        print(f'  {ev:>8s}-locked  N={len(arr):>4,}  peak t = {peak_t:+5.0f} ms,  '
              f'peak/baseline = {ratio:.2f}× ({peak_v:.4f} / {baseline:.4f})')
        summary[f'ripa2_{ev}'] = {
            'n': int(len(arr)),
            'peak_t_ms': float(peak_t),
            'peak_ratio': float(ratio),
            'peak_value': float(peak_v),
            'baseline': float(baseline),
        }

    print('\n=== Cursor velocity peak time + ratio ===')
    for ev in ('lastret', 'click'):
        arr = arrs[f'cursor_{ev}']
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx]
        peak_v = m[peak_window][peak_idx]
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        ratio = peak_v / max(baseline, 1e-9)
        print(f'  {ev:>8s}-locked  N={len(arr):>4,}  peak t = {peak_t:+5.0f} ms,  '
              f'peak/baseline = {ratio:.2f}× ({peak_v:.0f} / {baseline:.0f} px/s)')
        summary[f'cursor_{ev}'] = {
            'n': int(len(arr)),
            'peak_t_ms': float(peak_t),
            'peak_ratio': float(ratio),
            'peak_value': float(peak_v),
            'baseline': float(baseline),
        }

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))

    # ── Visualization: 2 rows × 2 cols (RIPA2 + cursor, lastret + click) ────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8), sharex=True)

    panels = [
        (0, 0, 'ripa2_lastret', COLOR_LASTRET,
         f'(A) RIPA2  —  LAST RETURN to target  (N={len(traces["ripa2_lastret"]):,})\n'
         f'final gaze episode that ends in click'),
        (0, 1, 'ripa2_click', COLOR_CLICK,
         f'(B) RIPA2  —  CLICK  (N={len(traces["ripa2_click"]):,})\n'
         f'motor commit'),
        (1, 0, 'cursor_lastret', COLOR_LASTRET,
         f'(C) Cursor velocity  —  LAST RETURN to target  (N={len(traces["cursor_lastret"]):,})\n'
         f'does cursor lead gaze return?'),
        (1, 1, 'cursor_click', COLOR_CLICK,
         f'(D) Cursor velocity  —  CLICK  (N={len(traces["cursor_click"]):,})'),
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

        # Mark peak time
        peak_idx = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx]
        peak_v = m[peak_window][peak_idx]
        ax.axvline(peak_t, color=color, lw=0.8, ls=':', alpha=0.6)
        ax.scatter([peak_t], [peak_v], s=60, color=color, edgecolor='#222222',
                   linewidth=0.8, zorder=5)
        ax.text(peak_t, peak_v * 1.04 if peak_v > 0 else peak_v * 0.96,
                f'  peak {peak_t:+.0f} ms', fontsize=9,
                color=color, fontstyle='italic',
                ha='left' if peak_t < 1000 else 'right',
                va='bottom' if peak_v > 0 else 'top')

        ax.set_title(title, fontsize=10.5)
        ax.grid(True, alpha=0.5)
        if col == 0:
            ax.set_ylabel('RIPA2' if row == 0 else 'cursor speed (px/s)')
        if row == 1:
            ax.set_xlabel('time from event (ms)')

    # Annotate the median LAST_RETURN → click delay on Panel A
    if deltas_lastret_to_click:
        med = float(np.median(deltas_lastret_to_click))
        ax = axes[0, 0]
        ax.axvline(med, color=COLOR_CLICK, lw=0.8, ls='--', alpha=0.5)
        ax.text(med, ax.get_ylim()[1] * 0.95, f'  click\n  +{med:.0f}ms',
                fontsize=8, color=COLOR_CLICK, fontstyle='italic',
                ha='left', va='top')

    fig.suptitle("LAST RETURN to target — the cleanest decision-moment gaze event\n"
                 "Tests cognition-leading-motor: does cursor lead gaze at the FINAL return episode?",
                 y=0.995, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.95))
    out_png = OUT_DIR / 'timeline_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'timeline_panel.svg', bbox_inches='tight')
    print(f'\n[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
