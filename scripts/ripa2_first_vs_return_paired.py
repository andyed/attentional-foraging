"""RIPA2 first-visit vs return-visit paired test (organic_hybrid only).

Mirror of lfhf_first_vs_return_paired.py with RIPA2 metric per Jayawardena,
Jayawardana & Gwizdka (JEMR 2025) Algorithm 1, post-2026-04-25 bug fix.

Computes Savitzky-Golay LF and VLF first-derivative outputs from raw pupil,
then RIPA2 = SG_LF² − SG_VLF², clipped to [0, 1.5]. Per-(trial, position)
RIPA2 = mean over fixation samples in that visit window (≥1s).

Tests whether the LF/HF return-vs-first effect generalizes across pupil
metrics or is LF/HF-specific.

Output: scripts/output/ripa2_first_vs_return_paired/{summary.json, report.md}

Run:
  .venv/bin/python scripts/ripa2_first_vs_return_paired.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.signal import savgol_filter

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/ripa2_first_vs_return_paired'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

# ── RIPA2 SG params at 150 Hz (Jayawardena 2025 Algorithm 1) ─────────
FS = 150
VLF_WINDOW = 243
VLF_POLYORDER = 2
LF_WINDOW = 31
LF_POLYORDER = 4
MIN_SAMPLES = 150  # 1 sec


def compute_ripa2_signal(pupil_signal):
    signal = np.asarray(pupil_signal, dtype=float)
    n = len(signal)
    if n < VLF_WINDOW:
        return np.zeros(n)
    sg_vlf = savgol_filter(signal, VLF_WINDOW, VLF_POLYORDER, deriv=1)
    sg_lf = savgol_filter(signal, LF_WINDOW, LF_POLYORDER, deriv=1)
    ripa2 = sg_lf ** 2 - sg_vlf ** 2
    return np.clip(ripa2, 0, 1.5)


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


def ripa2_for_windows(ripa2_signal, ts, windows):
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None, len(indices)
    return float(np.mean(ripa2_signal[np.array(indices)])), len(indices)


def process_trial(tid):
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return []
    ts = np.asarray(pupil['ts'])
    pd = np.asarray(pupil['clean_pd'])
    if len(pd) < MIN_SAMPLES * 2:
        return []
    ripa2_sig = compute_ripa2_signal(pd)

    fix = load_fixations(tid)
    if not fix:
        return []
    meta = get_trial_meta(tid)
    if meta is None or not meta[0]:
        return []

    tops = typed_aoi_tops(tid)
    if not tops:
        return []
    n_res = len(tops)

    first, ret = visit_segments(fix, tops, n_res)
    rows = []
    for pos, windows in first.items():
        rp_first, n_first = ripa2_for_windows(ripa2_sig, ts, windows)
        ret_windows = ret.get(pos)
        rp_return, n_return = (None, 0)
        if ret_windows:
            rp_return, n_return = ripa2_for_windows(ripa2_sig, ts, ret_windows)
        rows.append({
            'trial_id': tid, 'pid': tid.split('-')[0], 'pos': pos,
            'ripa2_first': rp_first, 'ripa2_return': rp_return,
            'n_samples_first': n_first, 'n_samples_return': n_return,
            'has_return_visit': rp_return is not None,
        })
    return rows


def main():
    print('[ripa2-paired] organic_hybrid', file=sys.stderr)
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,}', file=sys.stderr)

    rows = []
    n_trials_done = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}; pairs so far: '
                  f'{sum(1 for r in rows if r["has_return_visit"])}', file=sys.stderr)
        result = process_trial(tid)
        if result:
            rows.extend(result)
            n_trials_done += 1

    paired = [r for r in rows if r['ripa2_first'] is not None
              and r['ripa2_return'] is not None]
    print(f'\n  trials processed: {n_trials_done:,}  total records: {len(rows):,}  '
          f'paired: {len(paired):,}', file=sys.stderr)

    deltas = [{'pid': r['pid'], 'pos': r['pos'],
               'delta': float(r['ripa2_return'] - r['ripa2_first']),
               'first': r['ripa2_first'], 'return': r['ripa2_return']}
              for r in paired]
    delta_arr = np.array([d['delta'] for d in deltas])
    n = len(delta_arr)

    p_two = float(stats.wilcoxon(delta_arr, alternative='two-sided').pvalue)
    p_less = float(stats.wilcoxon(delta_arr, alternative='less').pvalue)
    p_greater = float(stats.wilcoxon(delta_arr, alternative='greater').pvalue)
    pct_neg = float(100 * (delta_arr < 0).mean())
    median_d = float(np.median(delta_arr))
    mean_d = float(delta_arr.mean())

    print(f'  median Δ: {median_d:+.6e}  mean Δ: {mean_d:+.6e}', file=sys.stderr)
    print(f'  % Δ < 0: {pct_neg:.1f}%', file=sys.stderr)
    print(f'  Wilcoxon p (two-sided): {p_two:.2e}', file=sys.stderr)
    print(f'  Wilcoxon p (less than 0): {p_less:.2e}', file=sys.stderr)
    print(f'  Wilcoxon p (greater than 0): {p_greater:.2e}', file=sys.stderr)

    # Per-rank
    by_rank = {}
    for d in deltas:
        by_rank.setdefault(d['pos'], []).append(d['delta'])
    per_rank = {}
    for rank, vals in sorted(by_rank.items()):
        if len(vals) >= 5:
            arr = np.array(vals)
            p_l = float(stats.wilcoxon(arr, alternative='less').pvalue)
            p_2 = float(stats.wilcoxon(arr, alternative='two-sided').pvalue)
            per_rank[str(rank)] = {
                'n': len(arr), 'median_delta': float(np.median(arr)),
                'mean_delta': float(arr.mean()),
                'pct_negative': float(100 * (arr < 0).mean()),
                'p_two_sided': p_2, 'p_less_than_zero': p_l,
            }

    # Participant-level
    by_pid = defaultdict(list)
    for d in deltas:
        by_pid[d['pid']].append(d['delta'])
    ppt_means = np.array([np.mean(v) for v in by_pid.values() if v])
    p_two_ppt = float(stats.wilcoxon(ppt_means, alternative='two-sided').pvalue)
    p_less_ppt = float(stats.wilcoxon(ppt_means, alternative='less').pvalue)

    out = {
        'attribution': 'typed',
        'n_records_total': len(rows),
        'n_paired': n,
        'obs_level': {
            'mean_delta': mean_d, 'median_delta': median_d,
            'pct_negative': pct_neg,
            'p_two_sided': p_two, 'p_less_than_zero': p_less,
            'p_greater_than_zero': p_greater,
        },
        'participant_level': {
            'n_participants': int(len(ppt_means)),
            'mean_of_means_delta': float(ppt_means.mean()),
            'median_of_means_delta': float(np.median(ppt_means)),
            'pct_negative': float(100 * (ppt_means < 0).mean()),
            'p_two_sided': p_two_ppt,
            'p_less_than_zero': p_less_ppt,
        },
        'per_rank': per_rank,
    }

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(out, indent=2))

    lines = [
        '# RIPA2 first-visit vs return-visit — paired (organic_hybrid)\n',
        '_Generated 2026-05-03 by `scripts/ripa2_first_vs_return_paired.py`._\n',
        'Triangulation against the LF/HF paired finding. Same pipeline, RIPA2 metric',
        '(Jayawardena et al. JEMR 2025 Algorithm 1, post-bug-fix).\n',
        '## Headline\n',
        f'**n paired = {n:,}** | median Δ = **{median_d:+.4g}** | mean Δ = {mean_d:+.4g}',
        '',
        f'- *p* (two-sided) = **{p_two:.2e}**',
        f'- *p* (less than 0, archetype-switch / recall hypothesis) = {p_less:.2e}',
        f'- *p* (greater than 0, re-evaluation hypothesis) = {p_greater:.2e}',
        f'- {pct_neg:.1f}% of paired records show Δ < 0',
        '',
        '## Participant-level',
        '',
        f'- {len(ppt_means)} participants',
        f'- mean-of-means Δ = {ppt_means.mean():+.4g}',
        f'- {100 * (ppt_means < 0).mean():.1f}% of participants show Δ < 0',
        f'- *p* (less than 0) = {p_less_ppt:.2e}',
        '',
        '## Per-rank Δ',
        '',
        '| Rank | n paired | median Δ | mean Δ | % Δ < 0 | p (two-sided) |',
        '|---|---|---|---|---|---|',
    ]
    for rank in sorted(per_rank.keys(), key=int):
        r = per_rank[rank]
        lines.append(f'| {rank} | {r["n"]} | {r["median_delta"]:+.4g} | '
                     f'{r["mean_delta"]:+.4g} | {r["pct_negative"]:.1f}% | '
                     f'{r["p_two_sided"]:.3e} |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)
    print(f'wrote {(OUT / "report.md").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
