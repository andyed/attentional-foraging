"""Recompute the regressive vs forward cursor-gaze coupling pillar
post 2026-04-12 fixation-y coordinate fix (NB13 audit).

Spec inherited from docs/drafts/task-model-paper.md §5.7 motor-pillar TODO:
  - per-fixation cursor-gaze Euclidean distance, page-space (no conversion)
  - partition by classify_fixations forward/regressive
  - bucket by time-to-click windows: acquisition (0-2s before click),
    evaluation (2-5s), scanning (5-15s), late (>15s)
  - report median + n per (mode, window) cell, plus the "clicked-cursor"
    median (cursor at click time vs gaze at click time) as the commit anchor.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict
from bisect import bisect_right

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # type: ignore  # noqa: E402
    get_trial_ids, load_fixations, load_mouse_and_scroll, load_mouse_events,
    get_trial_meta, classify_fixations,
)


def load_trial_for_classify(tid: str):
    """Build the dict shape classify_fixations() expects."""
    fix = load_fixations(tid)
    _, scrolls = load_mouse_and_scroll(tid)
    doc_h, scr_h, _ = get_trial_meta(tid)
    if doc_h is None or scr_h is None:
        return None
    return {
        'fixations': fix,
        'screen_height': scr_h,
        'doc_height': doc_h,
        'scroll_ts': [s[0] for s in scrolls],
        'scroll_ys': [s[1] for s in scrolls],
    }


def cursor_at(t_ms: int, mouse: list[tuple[int, float, float]]):
    """Return interpolated cursor (x, y) at time t_ms, or None if outside bounds."""
    if not mouse:
        return None
    ts = [m[0] for m in mouse]
    if t_ms < ts[0] or t_ms > ts[-1]:
        return None
    j = bisect_right(ts, t_ms)
    if j == 0:
        return mouse[0][1], mouse[0][2]
    if j >= len(mouse):
        return mouse[-1][1], mouse[-1][2]
    t0, x0, y0 = mouse[j - 1]
    t1, x1, y1 = mouse[j]
    if t1 == t0:
        return x0, y0
    a = (t_ms - t0) / (t1 - t0)
    return x0 + a * (x1 - x0), y0 + a * (y1 - y0)


WINDOWS = [
    ('acquisition', 0, 2000),
    ('evaluation', 2000, 5000),
    ('scanning', 5000, 15000),
    ('late', 15000, 10**9),
]


def window_for(ms_before_click: float) -> str:
    for name, lo, hi in WINDOWS:
        if lo <= ms_before_click < hi:
            return name
    return 'late'


def main() -> None:
    out_dir = ROOT / 'scripts/output/regressive_cursor_gaze_recompute'
    out_dir.mkdir(parents=True, exist_ok=True)

    samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    commit_dists: list[float] = []
    n_trials_processed = 0
    n_trials_skipped = 0

    for tid in get_trial_ids():
        try:
            trial = load_trial_for_classify(tid)
        except FileNotFoundError:
            n_trials_skipped += 1
            continue
        if trial is None or not trial['fixations']:
            n_trials_skipped += 1
            continue

        try:
            mouse, _ = load_mouse_and_scroll(tid)
            _, _, clicks = load_mouse_events(tid)
        except FileNotFoundError:
            n_trials_skipped += 1
            continue
        if not clicks:
            n_trials_skipped += 1
            continue

        click_t, click_x, click_y = clicks[-1]

        cur_at_click = cursor_at(click_t, mouse)
        if cur_at_click is not None:
            commit_dists.append(
                float(np.hypot(cur_at_click[0] - click_x,
                               cur_at_click[1] - click_y))
            )

        classified = classify_fixations(trial)
        n_trials_processed += 1

        for fix in classified:
            t = fix['t']
            ms_before = click_t - t
            if ms_before < 0:
                continue
            cur = cursor_at(t, mouse)
            if cur is None:
                continue
            d = float(np.hypot(cur[0] - fix['x'], cur[1] - fix['page_y']))
            mode = 'forward' if fix['is_forward'] else 'regressive'
            win = window_for(ms_before)
            samples[(mode, win)].append(d)

    summary: dict = {
        'n_trials_processed': n_trials_processed,
        'n_trials_skipped': n_trials_skipped,
        'commit_anchor': {
            'metric': 'cursor-vs-click-coords Euclidean px at click_t',
            'n': len(commit_dists),
            'median_px': float(np.median(commit_dists)) if commit_dists else None,
            'mean_px': float(np.mean(commit_dists)) if commit_dists else None,
            'p25_px': float(np.percentile(commit_dists, 25)) if commit_dists else None,
            'p75_px': float(np.percentile(commit_dists, 75)) if commit_dists else None,
        },
        'cells': {},
    }

    print(f"Trials processed: {n_trials_processed}")
    print(f"Trials skipped: {n_trials_skipped}")
    print(f"Commit anchor (cursor at click_t vs click coords): "
          f"median={summary['commit_anchor']['median_px']:.1f} px, "
          f"n={summary['commit_anchor']['n']}")
    print()
    print(f"{'mode':>11s} {'window':>12s} {'n':>9s} "
          f"{'median':>9s} {'p25':>9s} {'p75':>9s} {'mean':>9s}")

    for mode in ('forward', 'regressive'):
        for name, _, _ in WINDOWS:
            arr = np.asarray(samples.get((mode, name), []))
            n = len(arr)
            cell = {
                'n': int(n),
                'median_px': float(np.median(arr)) if n else None,
                'mean_px': float(np.mean(arr)) if n else None,
                'p25_px': float(np.percentile(arr, 25)) if n else None,
                'p75_px': float(np.percentile(arr, 75)) if n else None,
            }
            summary['cells'][f'{mode}_{name}'] = cell
            if n:
                print(f"{mode:>11s} {name:>12s} {n:>9d} "
                      f"{cell['median_px']:>9.1f} "
                      f"{cell['p25_px']:>9.1f} {cell['p75_px']:>9.1f} "
                      f"{cell['mean_px']:>9.1f}")
            else:
                print(f"{mode:>11s} {name:>12s} {n:>9d} "
                      f"{'—':>9s} {'—':>9s} {'—':>9s} {'—':>9s}")

    # Aggregate over all windows: the headline regressive vs forward gap.
    for mode in ('forward', 'regressive'):
        all_d = []
        for name, _, _ in WINDOWS:
            all_d.extend(samples.get((mode, name), []))
        a = np.asarray(all_d)
        summary[f'{mode}_overall'] = {
            'n': int(len(a)),
            'median_px': float(np.median(a)) if len(a) else None,
            'p25_px': float(np.percentile(a, 25)) if len(a) else None,
            'p75_px': float(np.percentile(a, 75)) if len(a) else None,
        }

    fwd = summary['forward_overall']
    reg = summary['regressive_overall']
    print()
    print(f"forward overall:    n={fwd['n']:>7d} median={fwd['median_px']:.1f} px")
    print(f"regressive overall: n={reg['n']:>7d} median={reg['median_px']:.1f} px")
    if fwd['median_px'] and reg['median_px']:
        print(f"gap (forward − regressive): "
              f"{fwd['median_px'] - reg['median_px']:+.1f} px")

    out_file = out_dir / 'summary.json'
    with open(out_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {out_file}")


if __name__ == '__main__':
    main()
