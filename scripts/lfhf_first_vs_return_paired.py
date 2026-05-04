"""Phase 2: paired within-item LF/HF, first-visit vs return-visit.

Tests the archetype-switch hypothesis (Duchowski 2026 §2.2):
  - First encounter of a SERP position = computation-dominated
    (criterion comparison) → higher LF/HF = more effort
  - Return visit to that same position = information-processing / recall
    (recognize previously-tagged candidate) → polarity flip, lower LF/HF
    = more effort

Paired test = rank-controlled by construction (same position, same user,
same trial), so this is immune to the rank-confounding that killed the
unpaired §Predicting return claim.

Output: scripts/output/lfhf_first_vs_return_paired/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_first_vs_return_paired.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.signal import butter, sosfiltfilt

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/lfhf_first_vs_return_paired'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    organic_aoi_tops, extract_serp_results,
    result_band_tops, assign_fixation_to_position,
    typed_aoi_tops,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

# ── Butterworth params (Duchowski 2026 / pupil-lfhf canonical) ────────
FS = 150
ORDER = 4
LF_CUTOFF = 1.6
HF_BAND = (1.6, 4.0)
MIN_SAMPLES = 150  # 1 sec at 150 Hz

LF_SOS = butter(ORDER, LF_CUTOFF, btype='low', fs=FS, output='sos')
HF_SOS = butter(ORDER, HF_BAND, btype='band', fs=FS, output='sos')


def get_aoi_tops(tid, attr):
    meta = get_trial_meta(tid)
    if meta is None or not meta[0]:
        return None, None
    doc_h = meta[0]
    if attr == 'organic':
        tops = organic_aoi_tops(tid)
        n_res = len(tops) if tops else 0
    elif attr == 'organic_hybrid':
        tops = _hybrid_aoi_tops(tid)
        n_res = len(tops) if tops else 0
    elif attr == 'typed':
        tops = typed_aoi_tops(tid)
        n_res = len(tops) if tops else 0
    else:
        serp = extract_serp_results(tid)
        n_res = len(serp) if serp else 10
        tops = result_band_tops(n_res, doc_h) if n_res else None
    if not tops or n_res == 0:
        return None, None
    return tops, n_res


def visit_segments(fix, tops, n_res):
    """Return (first_segs, return_segs) where each is dict pos -> list of
    (t_start_ms, t_end_ms) fixation windows."""
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


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    """Concatenate sample indices in given time windows; return LF/HF or None."""
    indices = []
    for (start, end) in windows:
        # ts may be ndarray; np.searchsorted is fast for sorted arrays
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None, len(indices)
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    if hf_p < 1e-20:
        return None, len(indices)
    return float(lf_p / hf_p), len(indices)


def process_trial(tid, attr):
    """Return list of dicts with paired first / return LF/HF per position."""
    pupil = load_pupil_trial(tid)
    if pupil is None:
        return []
    ts = np.asarray(pupil['ts'])
    pd = np.asarray(pupil['clean_pd'])
    if len(pd) < MIN_SAMPLES * 2:
        return []
    lf_sig = sosfiltfilt(LF_SOS, pd)
    hf_sig = sosfiltfilt(HF_SOS, pd)

    fix = load_fixations(tid)
    if not fix:
        return []
    tops, n_res = get_aoi_tops(tid, attr)
    if tops is None:
        return []

    first, ret = visit_segments(fix, tops, n_res)

    rows = []
    for pos, windows in first.items():
        lf_first, n_first = lfhf_for_windows(lf_sig, hf_sig, ts, windows)
        ret_windows = ret.get(pos)
        lf_return, n_return = (None, 0)
        if ret_windows:
            lf_return, n_return = lfhf_for_windows(lf_sig, hf_sig, ts, ret_windows)
        rows.append({
            'trial_id': tid,
            'pid': tid.split('-')[0],
            'pos': pos,
            'lfhf_first': lf_first,
            'lfhf_return': lf_return,
            'n_samples_first': n_first,
            'n_samples_return': n_return,
            'has_return_visit': lf_return is not None,
        })
    return rows


def participant_paired_wilcoxon(deltas):
    """Per-participant mean Δ across paired records, then Wilcoxon over
    participants."""
    by_pid = defaultdict(list)
    for d in deltas:
        by_pid[d['pid']].append(d['delta'])
    mean_deltas = []
    pids = []
    for pid, vals in by_pid.items():
        if vals:
            mean_deltas.append(float(np.mean(vals)))
            pids.append(pid)
    arr = np.array(mean_deltas)
    if len(arr) < 5:
        return None
    p_two = float(stats.wilcoxon(arr, alternative='two-sided').pvalue)
    p_less = float(stats.wilcoxon(arr, alternative='less').pvalue)
    p_greater = float(stats.wilcoxon(arr, alternative='greater').pvalue)
    return {
        'n_participants': len(arr),
        'mean_of_means_delta': float(arr.mean()),
        'median_of_means_delta': float(np.median(arr)),
        'pct_negative': float(100 * (arr < 0).mean()),
        'pct_positive': float(100 * (arr > 0).mean()),
        'p_two_sided': p_two,
        'p_less_than_zero': p_less,    # archetype-switch hypothesis: return < first
        'p_greater_than_zero': p_greater,
    }


def stress(attr, trial_ids):
    rows = []
    n_trials_done = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  [{attr}] {i+1}/{len(trial_ids)} trials processed; '
                  f'pairs so far: {sum(1 for r in rows if r["has_return_visit"])}',
                  file=sys.stderr)
        result = process_trial(tid, attr)
        if result:
            rows.extend(result)
            n_trials_done += 1

    # Filter to records where BOTH first and return have valid LF/HF (paired)
    paired = [r for r in rows if r['lfhf_first'] is not None
              and r['lfhf_return'] is not None]
    n_first_only = sum(1 for r in rows if r['lfhf_first'] is not None
                       and r['lfhf_return'] is None
                       and r['has_return_visit'])  # had return fixations but <1s
    n_no_return = sum(1 for r in rows if r['lfhf_first'] is not None
                      and not r['has_return_visit'])

    print(f'\n=== {attr.upper()} ===', file=sys.stderr)
    print(f'  trials processed: {n_trials_done:,}', file=sys.stderr)
    print(f'  total (trial,pos) records: {len(rows):,}', file=sys.stderr)
    print(f'  positions with first-pass LF/HF: '
          f'{sum(1 for r in rows if r["lfhf_first"] is not None):,}', file=sys.stderr)
    print(f'  positions with NO return visit: {n_no_return:,}', file=sys.stderr)
    print(f'  positions with return fixations but <1s window: {n_first_only:,}',
          file=sys.stderr)
    print(f'  PAIRED (both LF/HF defined): {len(paired):,}', file=sys.stderr)

    if not paired:
        print('  no paired records; cannot compute', file=sys.stderr)
        return {'attribution': attr, 'paired': 0}

    deltas = []
    for r in paired:
        d = float(r['lfhf_return'] - r['lfhf_first'])
        deltas.append({'pid': r['pid'], 'pos': r['pos'], 'delta': d,
                       'lfhf_first': r['lfhf_first'],
                       'lfhf_return': r['lfhf_return']})

    delta_arr = np.array([d['delta'] for d in deltas])
    n = len(delta_arr)

    # ── Obs-level paired tests ──
    p_two = float(stats.wilcoxon(delta_arr, alternative='two-sided').pvalue)
    p_less = float(stats.wilcoxon(delta_arr, alternative='less').pvalue)  # archetype hypothesis
    p_greater = float(stats.wilcoxon(delta_arr, alternative='greater').pvalue)
    pct_neg = float(100 * (delta_arr < 0).mean())
    median_d = float(np.median(delta_arr))
    mean_d = float(delta_arr.mean())

    # ── Rank-stratified ──
    by_rank = {}
    for d in deltas:
        by_rank.setdefault(d['pos'], []).append(d['delta'])
    per_rank = {}
    for rank, vals in sorted(by_rank.items()):
        if len(vals) >= 5:
            arr = np.array(vals)
            p2 = float(stats.wilcoxon(arr, alternative='two-sided').pvalue)
            p_l = float(stats.wilcoxon(arr, alternative='less').pvalue)
            per_rank[str(rank)] = {
                'n': len(arr),
                'median_delta': float(np.median(arr)),
                'mean_delta': float(arr.mean()),
                'pct_negative': float(100 * (arr < 0).mean()),
                'p_two_sided': p2,
                'p_less_than_zero': p_l,
            }

    # ── Participant-level ──
    ppt = participant_paired_wilcoxon(deltas)

    # ── Sample distribution (return-window quality check) ──
    n_return_samples = [r['n_samples_return'] for r in paired]
    n_first_samples = [r['n_samples_first'] for r in paired]

    return {
        'attribution': attr,
        'n_records_total': len(rows),
        'n_paired': n,
        'n_no_return_visit': n_no_return,
        'n_return_too_short': n_first_only,
        'n_return_samples_median': int(np.median(n_return_samples)),
        'n_return_samples_p25': int(np.percentile(n_return_samples, 25)),
        'n_return_samples_p75': int(np.percentile(n_return_samples, 75)),
        'n_first_samples_median': int(np.median(n_first_samples)),
        'obs_level': {
            'mean_delta': mean_d,
            'median_delta': median_d,
            'pct_negative': pct_neg,
            'p_two_sided': p_two,
            'p_less_than_zero': p_less,    # archetype hypothesis
            'p_greater_than_zero': p_greater,
        },
        'participant_level': ppt,
        'per_rank': per_rank,
    }


def write_report(results):
    lines = []
    lines.append('# LF/HF first-visit vs return-visit — paired within-item\n')
    lines.append('_Generated 2026-05-03 by `scripts/lfhf_first_vs_return_paired.py`._\n')
    lines.append('Tests Duchowski 2026 §2.2 archetype-switch hypothesis: '
                 'return-visit LF/HF < first-visit LF/HF '
                 '(if regressive pass = recall, polarity flips).\n')

    lines.append('## Counts\n')
    lines.append('| Attribution | total records | paired | no return visit | return < 1 s |')
    lines.append('|---|---|---|---|---|')
    for attr in ['absolute', 'organic', 'organic_hybrid', 'typed']:
        r = results.get(attr, {})
        lines.append(
            f'| {attr} | {r.get("n_records_total", "—"):,} | '
            f'**{r.get("n_paired", 0):,}** | '
            f'{r.get("n_no_return_visit", 0):,} | '
            f'{r.get("n_return_too_short", 0):,} |'
        )
    lines.append('')
    lines.append('Return-visit window samples (paired records): '
                 'p25 / median / p75 across all attributions.')

    lines.append('\n## Headline — paired observation level\n')
    lines.append('Δ = LF/HF (return) − LF/HF (first). Hypothesis: Δ < 0 (return is recall, '
                 'polarity flips per Duchowski 2026 §2.2).\n')
    lines.append('| Attribution | n paired | median Δ | mean Δ | % Δ < 0 | p (two-sided) | p (less than 0) |')
    lines.append('|---|---|---|---|---|---|---|')
    for attr in ['absolute', 'organic', 'organic_hybrid', 'typed']:
        r = results.get(attr, {})
        if r.get('n_paired', 0) == 0:
            lines.append(f'| {attr} | 0 | — | — | — | — | — |')
            continue
        ol = r['obs_level']
        lines.append(
            f'| {attr} | {r["n_paired"]:,} | {ol["median_delta"]:+.3f} | '
            f'{ol["mean_delta"]:+.3f} | {ol["pct_negative"]:.1f}% | '
            f'{ol["p_two_sided"]:.2e} | {ol["p_less_than_zero"]:.2e} |'
        )

    lines.append('\n## Participant-level paired Wilcoxon\n')
    lines.append('| Attribution | participants | mean-of-means Δ | median-of-means Δ | % participants Δ < 0 | p (two-sided) | p (less than 0) |')
    lines.append('|---|---|---|---|---|---|---|')
    for attr in ['absolute', 'organic', 'organic_hybrid', 'typed']:
        r = results.get(attr, {})
        ppt = r.get('participant_level')
        if ppt is None:
            lines.append(f'| {attr} | — | — | — | — | — | — |')
            continue
        lines.append(
            f'| {attr} | {ppt["n_participants"]} | {ppt["mean_of_means_delta"]:+.3f} | '
            f'{ppt["median_of_means_delta"]:+.3f} | {ppt["pct_negative"]:.1f}% | '
            f'{ppt["p_two_sided"]:.2e} | {ppt["p_less_than_zero"]:.2e} |'
        )

    lines.append('\n## Per-rank paired Δ (absolute attribution)\n')
    lines.append('| Rank | n paired | median Δ | mean Δ | % Δ < 0 | p (two-sided) | p (less than 0) |')
    lines.append('|---|---|---|---|---|---|---|')
    for rank in sorted(results.get('absolute', {}).get('per_rank', {}).keys(), key=int):
        r = results['absolute']['per_rank'][rank]
        lines.append(
            f'| {rank} | {r["n"]} | {r["median_delta"]:+.3f} | {r["mean_delta"]:+.3f} | '
            f'{r["pct_negative"]:.1f}% | {r["p_two_sided"]:.3e} | {r["p_less_than_zero"]:.3e} |'
        )

    return '\n'.join(lines)


def main():
    print('[paired] LF/HF first-visit vs return-visit', file=sys.stderr)
    # Get trial IDs from existing LF/HF data — same denominator as Phase 1
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,} trials with first-pass LF/HF data',
          file=sys.stderr)

    results = {}
    for attr in ['absolute', 'organic', 'organic_hybrid', 'typed']:
        results[attr] = stress(attr, trial_ids)

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(results, indent=2))
    out_md = OUT / 'report.md'
    out_md.write_text(write_report(results))
    print(f'\nwrote {out_json.relative_to(ROOT)}', file=sys.stderr)
    print(f'wrote {out_md.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
