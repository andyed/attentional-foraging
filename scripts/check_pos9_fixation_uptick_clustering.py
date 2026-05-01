"""Check participant clustering on the position-9 fixation-count uptick
(forward-only, NB23 / §5.8 finding).

Specifically: how many participants contribute to the (pos 8, pos 9) row pool,
how concentrated is the effect, and does it survive a participant-clustered
test?
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

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


def load_trial_dict(tid: str):
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


def main() -> None:
    # (participant, trial, mode_filter) -> {pos: count}
    fwd_rows: list[tuple[str, str, int, int]] = []  # (pid, tid, pos, n_fixations)
    reg_rows: list[tuple[str, str, int, int]] = []

    for tid in get_trial_ids():
        try:
            trial = load_trial_dict(tid)
        except FileNotFoundError:
            continue
        if trial is None:
            continue
        classified = classify_fixations(trial)
        pid = trial_participant(tid)

        fwd_pos: dict[int, int] = defaultdict(int)
        reg_pos: dict[int, int] = defaultdict(int)
        for fix in classified:
            pos = fix['position']
            if pos < 0 or pos > 9:
                continue
            if fix['is_forward']:
                fwd_pos[pos] += 1
            else:
                reg_pos[pos] += 1

        for pos, n in fwd_pos.items():
            fwd_rows.append((pid, tid, pos, n))
        for pos, n in reg_pos.items():
            reg_rows.append((pid, tid, pos, n))

    # Replicate the row-level test as a sanity check
    fwd_pos8 = [n for (_, _, p, n) in fwd_rows if p == 8]
    fwd_pos9 = [n for (_, _, p, n) in fwd_rows if p == 9]
    reg_pos8 = [n for (_, _, p, n) in reg_rows if p == 8]
    reg_pos9 = [n for (_, _, p, n) in reg_rows if p == 9]

    print('=== Row-level Mann-Whitney (replicates the §5.8 claim) ===')
    print(f'Forward pos 8 vs 9: n = {len(fwd_pos8)} / {len(fwd_pos9)}, '
          f'medians {np.median(fwd_pos8):.0f} vs {np.median(fwd_pos9):.0f}')
    u, p = stats.mannwhitneyu(fwd_pos9, fwd_pos8, alternative='greater')
    print(f'  U = {u:.0f}, p = {p:.3g} (one-sided greater)')

    print(f'Regressive pos 8 vs 9: n = {len(reg_pos8)} / {len(reg_pos9)}, '
          f'medians {np.median(reg_pos8):.0f} vs {np.median(reg_pos9):.0f}')
    u, p = stats.mannwhitneyu(reg_pos9, reg_pos8, alternative='greater')
    print(f'  U = {u:.0f}, p = {p:.3g} (one-sided greater)')

    # Participant participation
    print('\n=== Participant contribution to forward pos 9 rows ===')
    pid_counts_fwd9: dict[str, int] = defaultdict(int)
    pid_n_fix_fwd9: dict[str, list[int]] = defaultdict(list)
    for pid, _, p, n in fwd_rows:
        if p == 9:
            pid_counts_fwd9[pid] += 1
            pid_n_fix_fwd9[pid].append(n)
    print(f'Participants contributing forward pos-9 rows: {len(pid_counts_fwd9)} / 47')
    sorted_pids = sorted(pid_counts_fwd9.items(), key=lambda kv: -kv[1])
    print('\nTop participants by row count:')
    cum = 0
    total_rows = sum(pid_counts_fwd9.values())
    for i, (pid, c) in enumerate(sorted_pids[:10]):
        cum += c
        print(f'  {pid}: {c:3d} rows ({c/total_rows*100:5.1f}% — cumulative {cum/total_rows*100:5.1f}%)'
              f'  median fixations on pos 9: {np.median(pid_n_fix_fwd9[pid]):.0f}')

    # Same for pos 8
    pid_counts_fwd8: dict[str, int] = defaultdict(int)
    for pid, _, p, n in fwd_rows:
        if p == 8:
            pid_counts_fwd8[pid] += 1
    print(f'\nParticipants contributing forward pos-8 rows: {len(pid_counts_fwd8)} / 47')

    # Per-participant median pos-9 minus median pos-8 (forward), then test across participants
    print('\n=== Per-participant test: median(pos 9) − median(pos 8), forward ===')
    fwd_pid_pos: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    for pid, _, p, n in fwd_rows:
        fwd_pid_pos[pid][p].append(n)

    deltas: list[float] = []
    pid_p9_minus_p8: list[tuple[str, float, int, int]] = []
    for pid, pos_map in fwd_pid_pos.items():
        if 8 in pos_map and 9 in pos_map:
            d = float(np.median(pos_map[9]) - np.median(pos_map[8]))
            deltas.append(d)
            pid_p9_minus_p8.append((pid, d, len(pos_map[8]), len(pos_map[9])))

    deltas_arr = np.asarray(deltas)
    print(f'Participants contributing both pos-8 and pos-9 forward rows: '
          f'{len(deltas_arr)} / 47')
    if len(deltas_arr):
        n_pos = int((deltas_arr > 0).sum())
        n_neg = int((deltas_arr < 0).sum())
        n_zero = int((deltas_arr == 0).sum())
        print(f'  positive (pos9 > pos8): {n_pos}')
        print(f'  zero (tied):            {n_zero}')
        print(f'  negative (pos9 < pos8): {n_neg}')
        print(f'  median delta:           {np.median(deltas_arr):+.2f}')
        print(f'  mean delta:             {np.mean(deltas_arr):+.2f}')

        # Wilcoxon signed-rank vs zero
        try:
            w, pw = stats.wilcoxon(deltas_arr)
            print(f'  Wilcoxon signed-rank vs zero: W = {w:.1f}, p = {pw:.4f} (two-sided)')
        except ValueError as e:
            print(f'  Wilcoxon failed: {e}')
        # Sign test
        from scipy.stats import binomtest
        nonzero = n_pos + n_neg
        if nonzero:
            bt = binomtest(n_pos, nonzero, p=0.5, alternative='two-sided')
            print(f'  Sign test ({n_pos}/{nonzero} positive): p = {bt.pvalue:.4f}')

    # Show top contributors and rerun row-level test dropping top 2
    print('\n=== Robustness: drop top contributors, redo row-level test ===')
    for k in (1, 2, 4):
        drop = {pid for pid, _ in sorted_pids[:k]}
        fwd_pos8_k = [n for (pid, _, p, n) in fwd_rows if p == 8 and pid not in drop]
        fwd_pos9_k = [n for (pid, _, p, n) in fwd_rows if p == 9 and pid not in drop]
        if fwd_pos8_k and fwd_pos9_k:
            u, p = stats.mannwhitneyu(fwd_pos9_k, fwd_pos8_k, alternative='greater')
            ratio_p9 = np.median(fwd_pos9_k) / max(np.median(fwd_pos8_k), 1e-9)
            print(f'  Drop top {k} (pids {sorted(drop)}): n8 = {len(fwd_pos8_k)}, '
                  f'n9 = {len(fwd_pos9_k)}, '
                  f'medians {np.median(fwd_pos8_k):.0f} vs {np.median(fwd_pos9_k):.0f}, '
                  f'p = {p:.3g}')


if __name__ == '__main__':
    main()
