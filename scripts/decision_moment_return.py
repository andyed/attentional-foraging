"""Decision-moment locking, refined: separate Survey-phase incidentals from
return-to-target decision events.

The previous decision_moment_locking script averaged "first-fix-on-target"
across all clicked trials. Median first-fix → click was 14 seconds — way too
long for a clean decision moment. The first fixation is being polluted by
Survey-phase incidentals (user briefly glances at what later becomes the
target during scanning).

Refinement: classify each trial by gaze trajectory:

  TYPE A — DIRECT trials: user fixates target, never visits another position
           before clicking. First fixation IS the decision-phase contact.
  TYPE B — RETURN trials: user contacts target, leaves to visit another
           position (or several), then RETURNS to target and clicks.
           The "return event" (first fixation on target after at least one
           other-position fixation) is the clean decision-moment candidate.

Time-lock RIPA2 + cursor velocity around four event types:
  (1) DIRECT first-fix    — first contact on target, decision moment in DIRECT trials
  (2) RETURN first-glance — Survey-phase incidental in RETURN trials
  (3) RETURN return event — gaze-locks-back-on-target, the cleanest scent-
                             detection candidate
  (4) Click event         — motor commit (control comparison)

Predictions:
  - If pupil tracks scent detection: peak at (1) and (3), small at (2).
  - If decision crystallizes through evaluation: ramp from (1)/(3) to click.
  - If cursor leads decision: cursor velocity peaks at (3), not at click.

Output:
  scripts/output/decision_moment_return/summary.json
  scripts/output/decision_moment_return/timeline_panel.png
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

OUT_DIR = ROOT / 'scripts/output/decision_moment_return'
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
COLOR_DIRECT = "#332288"      # deep blue — direct decision
COLOR_GLANCE = "#888888"      # gray — Survey-incidental
COLOR_RETURN = "#117733"      # green — decision-phase return
COLOR_CLICK = "#7c4dff"       # purple — motor commit


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


def classify_trial(fixations, click_t, target_pos, tops, n_results):
    """Classify a trial as DIRECT or RETURN based on gaze trajectory.

    Returns (kind, first_fix_t, return_fix_t):
      DIRECT — only fixations on target before click; first_fix is the
               decision moment. return_fix_t = None.
      RETURN — at least one other-position fixation between first and
               last target fixation. return_fix_t is the first target
               fixation AFTER any other-position fixation.
      None    — no fixations on target at all (trial unusable).
    """
    target_fixs = []
    visited_other = False
    return_fix_t = None
    first_fix_t = None
    for f in fixations:
        if f['t'] >= click_t:
            break
        p = assign_fixation_to_position(f['y'], tops, n_results)
        if p is None:
            continue
        if p == target_pos:
            if first_fix_t is None:
                first_fix_t = float(f['t'])
            target_fixs.append(f)
            if visited_other and return_fix_t is None:
                return_fix_t = float(f['t'])
        else:
            if first_fix_t is not None:
                visited_other = True

    if first_fix_t is None:
        return None, None, None
    if return_fix_t is None:
        return 'DIRECT', first_fix_t, None
    return 'RETURN', first_fix_t, return_fix_t


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    axis, _ = make_axis()
    traces = {
        'ripa2_direct': [], 'ripa2_glance': [], 'ripa2_return': [], 'ripa2_click': [],
        'cursor_direct': [], 'cursor_glance': [], 'cursor_return': [], 'cursor_click': [],
    }
    deltas = {'direct_to_click': [], 'glance_to_return': [], 'return_to_click': []}
    n_direct = n_return = n_skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}  (direct={n_direct:,} return={n_return:,})',
                  file=sys.stderr)
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

        kind, first_fix_t, return_fix_t = classify_trial(
            fixations, click_t, target_pos, tops, n_results)
        if kind is None:
            continue

        # Cursor velocity grid for the whole trial (with margin)
        cgrid, cvel = cursor_velocity(events, first_fix_t - PRE_MS - 100,
                                       click_t + POST_MS + 100)

        # Click event traces (always present)
        for name, sig in [('ripa2_click', ripa2)]:
            tr = time_lock(ts, sig, click_t)
            if tr is not None:
                traces[name].append(tr)
        if len(cgrid) > 5:
            tr = time_lock(cgrid, cvel, click_t)
            if tr is not None:
                traces['cursor_click'].append(tr)

        if kind == 'DIRECT':
            n_direct += 1
            deltas['direct_to_click'].append(click_t - first_fix_t)
            tr = time_lock(ts, ripa2, first_fix_t)
            if tr is not None:
                traces['ripa2_direct'].append(tr)
            if len(cgrid) > 5:
                tr = time_lock(cgrid, cvel, first_fix_t)
                if tr is not None:
                    traces['cursor_direct'].append(tr)
        else:  # RETURN
            n_return += 1
            deltas['glance_to_return'].append(return_fix_t - first_fix_t)
            deltas['return_to_click'].append(click_t - return_fix_t)
            for name, et in [('glance', first_fix_t), ('return', return_fix_t)]:
                tr = time_lock(ts, ripa2, et)
                if tr is not None:
                    traces[f'ripa2_{name}'].append(tr)
                if len(cgrid) > 5:
                    tr = time_lock(cgrid, cvel, et)
                    if tr is not None:
                        traces[f'cursor_{name}'].append(tr)

    arrs = {k: np.array(v) if v else None for k, v in traces.items()}
    n_total = n_direct + n_return
    print(f'\n  total clicked-trial classifications: {n_total:,}', file=sys.stderr)
    print(f'    DIRECT (no other-pos fixation):  {n_direct:,} ({100*n_direct/max(n_total,1):.1f}%)',
          file=sys.stderr)
    print(f'    RETURN (visited elsewhere):       {n_return:,} ({100*n_return/max(n_total,1):.1f}%)',
          file=sys.stderr)
    if deltas['direct_to_click']:
        d = np.array(deltas['direct_to_click'])
        print(f'  DIRECT first-fix → click: median {np.median(d):.0f} ms,  '
              f'q25 {np.percentile(d, 25):.0f},  q75 {np.percentile(d, 75):.0f}',
              file=sys.stderr)
    if deltas['glance_to_return']:
        d_gr = np.array(deltas['glance_to_return'])
        d_rc = np.array(deltas['return_to_click'])
        print(f'  RETURN glance → return:   median {np.median(d_gr):.0f} ms',
              file=sys.stderr)
        print(f'  RETURN return → click:    median {np.median(d_rc):.0f} ms',
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

    # Peak ratios
    peak_window = (axis >= -1500) & (axis <= 1500)
    summary = {
        'n_direct': int(n_direct), 'n_return': int(n_return),
        'median_direct_to_click_ms': float(np.median(deltas['direct_to_click']))
                                       if deltas['direct_to_click'] else None,
        'median_glance_to_return_ms': float(np.median(deltas['glance_to_return']))
                                        if deltas['glance_to_return'] else None,
        'median_return_to_click_ms': float(np.median(deltas['return_to_click']))
                                        if deltas['return_to_click'] else None,
    }
    print('\n=== RIPA2 peak time + ratio by event ===')
    for ev in ('direct', 'glance', 'return', 'click'):
        arr = arrs[f'ripa2_{ev}']
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx]
        peak_v = m[peak_window][peak_idx]
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        ratio = peak_v / max(baseline, 1e-9)
        print(f'  {ev:>6s}-locked  N = {len(arr):>4,}  '
              f'peak t = {peak_t:+5.0f} ms  '
              f'peak/baseline = {ratio:.2f}×  ({peak_v:.4f} / {baseline:.4f})')
        summary[f'ripa2_{ev}'] = {
            'n': int(len(arr)), 'peak_t_ms': float(peak_t),
            'peak_value': float(peak_v), 'baseline': baseline,
            'peak_ratio': float(ratio),
        }

    print('\n=== Cursor velocity peak ratio by event ===')
    for ev in ('direct', 'glance', 'return', 'click'):
        arr = arrs[f'cursor_{ev}']
        m = trace_mean(arr)
        if m is None:
            continue
        peak_idx = np.nanargmax(m[peak_window])
        peak_t = axis[peak_window][peak_idx]
        peak_v = m[peak_window][peak_idx]
        baseline = float(np.nanmean(m[(axis >= -2000) & (axis <= -1000)]))
        ratio = peak_v / max(baseline, 1e-9)
        print(f'  {ev:>6s}-locked  N = {len(arr):>4,}  '
              f'peak t = {peak_t:+5.0f} ms  '
              f'peak/baseline = {ratio:.2f}×  ({peak_v:.0f} / {baseline:.0f} px/s)')
        summary[f'cursor_{ev}'] = {
            'n': int(len(arr)), 'peak_t_ms': float(peak_t),
            'peak_value': float(peak_v), 'baseline': baseline,
            'peak_ratio': float(ratio),
        }

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))

    # ── Visualization ─────────────────────────────────────────────────
    plt.rcParams.update(RC)
    fig, axes = plt.subplots(2, 4, figsize=(17, 8), sharex=True)

    panels = [
        (0, 0, 'ripa2_direct', COLOR_DIRECT,
         f'(A) RIPA2  —  DIRECT first-fix  (N={len(traces["ripa2_direct"]):,})\n'
         f'no Survey-phase visit elsewhere'),
        (0, 1, 'ripa2_glance', COLOR_GLANCE,
         f'(B) RIPA2  —  RETURN first-glance  (N={len(traces["ripa2_glance"]):,})\n'
         f'Survey-incidental on what becomes target'),
        (0, 2, 'ripa2_return', COLOR_RETURN,
         f'(C) RIPA2  —  RETURN-to-target  (N={len(traces["ripa2_return"]):,})\n'
         f'decision-phase scent re-detection'),
        (0, 3, 'ripa2_click', COLOR_CLICK,
         f'(D) RIPA2  —  CLICK  (N={len(traces["ripa2_click"]):,})\n'
         f'motor commit'),
        (1, 0, 'cursor_direct', COLOR_DIRECT, '(E) Cursor velocity  —  DIRECT first-fix'),
        (1, 1, 'cursor_glance', COLOR_GLANCE, '(F) Cursor velocity  —  RETURN first-glance'),
        (1, 2, 'cursor_return', COLOR_RETURN, '(G) Cursor velocity  —  RETURN-to-target'),
        (1, 3, 'cursor_click', COLOR_CLICK,    '(H) Cursor velocity  —  CLICK'),
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
        ax.set_title(title, fontsize=10)
        ax.grid(True, alpha=0.5)
        if col == 0:
            ax.set_ylabel('RIPA2' if row == 0 else 'cursor speed (px/s)')
        if row == 1:
            ax.set_xlabel('time from event (ms)')

    fig.suptitle("Decision-moment locking, refined: DIRECT vs RETURN trial trajectories\n"
                 "Tests scent-detection-triggers-decision hypothesis on the cleanest gaze events",
                 y=0.995, fontsize=13)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_png = OUT_DIR / 'timeline_panel.png'
    fig.savefig(out_png, dpi=300, bbox_inches='tight')
    fig.savefig(OUT_DIR / 'timeline_panel.svg', bbox_inches='tight')
    print(f'\n[out] {out_png.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
