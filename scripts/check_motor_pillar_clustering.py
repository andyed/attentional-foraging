"""Validate the §5.7 motor pillar under participant clustering.

The headline numbers (overall 316 vs 360 px, etc.) are computed by pooling
142,569 forward + 60,673 regressive fixations across 2,774 trials. We need
the per-participant version: for each participant, compute median(reg) and
median(fwd), then test the within-participant difference across the 47
participants. If most participants show regressive < forward, the headline
generalizes; if the row-level effect is participant-concentrated, the headline
is misleading (same audit-collapse pattern as the ski-jump click finding).
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict
from bisect import bisect_right

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # type: ignore  # noqa: E402
    get_trial_ids, load_fixations, load_mouse_and_scroll, load_mouse_events,
    get_trial_meta, classify_fixations,
)


def trial_participant(tid: str) -> str:
    return tid.split('-')[0]


def load_trial_for_classify(tid: str):
    fix = load_fixations(tid)
    _, scrolls = load_mouse_and_scroll(tid)
    doc_h, scr_h, _ = get_trial_meta(tid)
    if doc_h is None or scr_h is None or not fix:
        return None
    return {
        'fixations': fix,
        'screen_height': scr_h,
        'doc_height': doc_h,
        'scroll_ts': [s[0] for s in scrolls],
        'scroll_ys': [s[1] for s in scrolls],
    }


def cursor_at(t_ms, mouse):
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


def main():
    # participant -> mode -> list of distances
    by_pid_mode: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {'forward': [], 'regressive': []}
    )

    for tid in get_trial_ids():
        try:
            trial = load_trial_for_classify(tid)
        except FileNotFoundError:
            continue
        if trial is None:
            continue
        try:
            mouse, _ = load_mouse_and_scroll(tid)
            _, _, clicks = load_mouse_events(tid)
        except FileNotFoundError:
            continue
        if not clicks:
            continue
        click_t = clicks[-1][0]
        pid = trial_participant(tid)
        for fix in classify_fixations(trial):
            if fix['t'] > click_t:
                continue
            cur = cursor_at(fix['t'], mouse)
            if cur is None:
                continue
            d = float(np.hypot(cur[0] - fix['x'], cur[1] - fix['page_y']))
            mode = 'forward' if fix['is_forward'] else 'regressive'
            by_pid_mode[pid][mode].append(d)

    # Per-participant medians and within-participant gap
    rows = []
    for pid in sorted(by_pid_mode.keys()):
        f = by_pid_mode[pid]['forward']
        r = by_pid_mode[pid]['regressive']
        if not f or not r:
            continue
        rows.append({
            'pid': pid,
            'n_fwd': len(f),
            'n_reg': len(r),
            'med_fwd': float(np.median(f)),
            'med_reg': float(np.median(r)),
            'delta': float(np.median(f) - np.median(r)),  # +delta = regressive tighter
        })

    rows.sort(key=lambda x: -x['delta'])

    print(f'Participants with both forward and regressive fixations: {len(rows)} / 47')
    print()
    print(f'{"pid":>5s} {"n_fwd":>6s} {"n_reg":>6s} {"med_fwd":>8s} '
          f'{"med_reg":>8s} {"delta":>7s}')
    for r in rows:
        flag = ' ✓' if r['delta'] > 0 else (' —' if r['delta'] == 0 else ' ✗')
        print(f"{r['pid']:>5s} {r['n_fwd']:>6d} {r['n_reg']:>6d} "
              f"{r['med_fwd']:>8.1f} {r['med_reg']:>8.1f} {r['delta']:>+7.1f}{flag}")

    deltas = np.array([r['delta'] for r in rows])
    n_pos = int((deltas > 0).sum())
    n_neg = int((deltas < 0).sum())
    n_zero = int((deltas == 0).sum())

    print()
    print('=== Within-participant test of the motor-pillar claim ===')
    print('  positive (regressive tighter, predicted direction): '
          f'{n_pos} / {len(deltas)}')
    print(f'  zero:                                                {n_zero}')
    print(f'  negative (forward tighter, opposite direction):      {n_neg}')
    print(f'  median within-participant gap: {np.median(deltas):+.2f} px')
    print(f'  mean   within-participant gap: {np.mean(deltas):+.2f} px')

    try:
        w, pw = stats.wilcoxon(deltas)
        print(f'  Wilcoxon signed-rank vs zero: W = {w:.1f}, p = {pw:.4g} (two-sided)')
    except ValueError as e:
        print(f'  Wilcoxon failed: {e}')

    from scipy.stats import binomtest
    nz = n_pos + n_neg
    if nz:
        bt = binomtest(n_pos, nz, p=0.5, alternative='two-sided')
        print(f'  Sign test ({n_pos}/{nz} positive): p = {bt.pvalue:.4g}')

    # Robustness: drop top |delta| participants
    print()
    print('=== Robustness: drop participants with most extreme deltas ===')
    for k in (2, 4):
        # rank by absolute delta
        keep = sorted(rows, key=lambda x: abs(x['delta']))[:-k] if k < len(rows) else []
        if not keep:
            continue
        ds = np.array([r['delta'] for r in keep])
        print(f'  drop top {k} by |delta|: n = {len(ds)}, median = {np.median(ds):+.2f}, '
              f'positive = {int((ds > 0).sum())}/{len(ds)}')


if __name__ == '__main__':
    main()
