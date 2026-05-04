"""Recompute the LF/HF rank gradient under organic_hybrid attribution.

Outputs everything ETTAC §3.3 needs for the rank-gradient block:
  - per-position median LF/HF, N per position, IQR
  - 95% bootstrap CIs on per-position medians
  - cross-trial Spearman ρ on position medians (full range, P0–P3 steep,
    P4–P10 plateau)
  - cap-10 audit (per-participant ≤10 segments per rank, recompute plateau)
  - per-trial Spearman ρ between rank and LF/HF, with cohort cuts at
    ≥3 / ≥5 / ≥7 valid segments
  - pooled steep-vs-plateau Mann-Whitney U on raw rank-segments

Output: scripts/output/lfhf_rank_gradient_hybrid/{summary.json, report.md}

Run:
  .venv/bin/python scripts/lfhf_rank_gradient_hybrid.py
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
OUT = ROOT / 'scripts/output/lfhf_rank_gradient_hybrid'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta, load_pupil_trial,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

FS = 150
LF_SOS = butter(4, 1.6, btype='low', fs=FS, output='sos')
HF_SOS = butter(4, (1.6, 4.0), btype='band', fs=FS, output='sos')
MIN_SAMPLES = 150


def visit_segments_first_only(fix, tops, n_res):
    first = {}
    max_seen = -1
    for f in fix:
        pos = assign_fixation_to_position(f['y'], tops, n_res)
        if pos is None or pos < 0:
            continue
        if pos >= max_seen:
            first.setdefault(pos, []).append((f['t'], f['t'] + f['d']))
            if pos > max_seen:
                max_seen = pos
    return first


def lfhf_for_windows(lf_signal, hf_signal, ts, windows):
    indices = []
    for (start, end) in windows:
        lo = np.searchsorted(ts, start, side='left')
        hi = np.searchsorted(ts, end, side='right')
        if hi > lo:
            indices.extend(range(int(lo), int(hi)))
    if len(indices) < MIN_SAMPLES:
        return None
    idx = np.array(indices)
    lf_p = float(np.var(lf_signal[idx]))
    hf_p = float(np.var(hf_signal[idx]))
    return float(lf_p / hf_p) if hf_p >= 1e-20 else None


def process_trial(tid):
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
    tops = _hybrid_aoi_tops(tid)
    if not tops:
        return []
    n_res = len(tops)
    first = visit_segments_first_only(fix, tops, n_res)
    rows = []
    for pos, windows in first.items():
        lf = lfhf_for_windows(lf_sig, hf_sig, ts, windows)
        if lf is not None:
            rows.append({'tid': tid, 'pid': tid.split('-')[0],
                         'pos': pos, 'lfhf': lf})
    return rows


def bootstrap_ci_median(vals, n_boot=2000, rng=None):
    if rng is None:
        rng = np.random.default_rng(20260503)
    arr = np.asarray(vals)
    if len(arr) < 5:
        return float('nan'), float('nan')
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(len(arr), size=len(arr), replace=True)
        boots[b] = np.median(arr[idx])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def spearman_with_p(x, y):
    if len(x) < 3:
        return float('nan'), float('nan')
    res = stats.spearmanr(x, y)
    return float(res.statistic), float(res.pvalue)


def main():
    print('[hybrid-gradient] LF/HF rank gradient under organic_hybrid', file=sys.stderr)
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    print(f'  trial set: {len(trial_ids):,}', file=sys.stderr)

    all_rows = []
    n_trials_done = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)} trials', file=sys.stderr)
        result = process_trial(tid)
        if result:
            all_rows.extend(result)
            n_trials_done += 1

    print(f'\n  trials processed: {n_trials_done:,}', file=sys.stderr)
    print(f'  total (trial, pos) records: {len(all_rows):,}', file=sys.stderr)

    # ── Per-position summary ──
    by_pos = defaultdict(list)
    for r in all_rows:
        by_pos[r['pos']].append(r['lfhf'])

    per_position = {}
    pos_medians = []
    pos_keys = sorted(by_pos.keys())
    for pos in pos_keys:
        vals = by_pos[pos]
        med = float(np.median(vals))
        lo, hi = bootstrap_ci_median(vals)
        per_position[str(pos)] = {
            'n': len(vals),
            'median': med,
            'q25': float(np.percentile(vals, 25)),
            'q75': float(np.percentile(vals, 75)),
            'ci95_lo': lo, 'ci95_hi': hi,
        }
        pos_medians.append((pos, med))
        print(f'    pos {pos}: N={len(vals):,}  median={med:.2f}  CI=[{lo:.2f}, {hi:.2f}]',
              file=sys.stderr)

    # ── Cross-trial Spearman on position medians ──
    pos_arr = np.array([p for p, _ in pos_medians])
    med_arr = np.array([m for _, m in pos_medians])
    full_rho, full_p = spearman_with_p(pos_arr, med_arr)
    print(f'\n  Full-corpus Spearman on position medians: ρ={full_rho:+.3f}  p={full_p:.2e}  '
          f'(N={len(pos_arr)} positions)', file=sys.stderr)

    steep_mask = pos_arr <= 3
    plat_mask = (pos_arr >= 4) & (pos_arr <= 10)
    steep_rho, steep_p = spearman_with_p(pos_arr[steep_mask], med_arr[steep_mask])
    plat_rho, plat_p = spearman_with_p(pos_arr[plat_mask], med_arr[plat_mask])
    print(f'  Steep (P0–P3) ρ={steep_rho:+.3f}  p={steep_p:.2e}  '
          f'(N={int(steep_mask.sum())})', file=sys.stderr)
    print(f'  Plateau (P4–P10) ρ={plat_rho:+.3f}  p={plat_p:.2e}  '
          f'(N={int(plat_mask.sum())})', file=sys.stderr)

    # ── Pooled steep-vs-plateau Mann-Whitney on raw segments ──
    steep_pool = [r['lfhf'] for r in all_rows if r['pos'] <= 3]
    plat_pool = [r['lfhf'] for r in all_rows if 4 <= r['pos'] <= 10]
    u, mw_p = stats.mannwhitneyu(steep_pool, plat_pool, alternative='greater')
    pooled_summary = {
        'steep_n': len(steep_pool), 'plateau_n': len(plat_pool),
        'steep_median': float(np.median(steep_pool)),
        'plateau_median': float(np.median(plat_pool)),
        'mann_whitney_u': float(u),
        'mw_p_one_sided_greater': float(mw_p),
    }
    print(f'\n  Pooled steep vs plateau: U={u:,.0f}  p={mw_p:.2e}  '
          f'medians {pooled_summary["steep_median"]:.2f} vs {pooled_summary["plateau_median"]:.2f}  '
          f'(N={pooled_summary["steep_n"]:,} vs {pooled_summary["plateau_n"]:,})',
          file=sys.stderr)

    # ── Per-trial Spearman ρ between pos and lfhf ──
    by_trial = defaultdict(list)
    for r in all_rows:
        by_trial[r['tid']].append((r['pos'], r['lfhf']))

    per_trial_summary = {}
    for cutoff in (3, 5, 7):
        rhos = []
        for tid, pairs in by_trial.items():
            if len(pairs) >= cutoff:
                xs = [p[0] for p in pairs]
                ys = [p[1] for p in pairs]
                rho, _ = spearman_with_p(xs, ys)
                if not np.isnan(rho):
                    rhos.append(rho)
        rhos = np.array(rhos)
        per_trial_summary[f'min_segments_{cutoff}'] = {
            'n_trials': int(len(rhos)),
            'median_rho': float(np.median(rhos)) if len(rhos) else float('nan'),
            'pct_negative': float(100 * (rhos < 0).mean()) if len(rhos) else float('nan'),
        }
        print(f'  Per-trial ρ (≥{cutoff} segments): N={len(rhos):,}  '
              f'median ρ={np.median(rhos):+.3f}  '
              f'{100 * (rhos < 0).mean():.1f}% negative', file=sys.stderr)

    # ── Cap-10 audit (per-participant cap on contributions per rank) ──
    rng = np.random.default_rng(20260503)
    capped = defaultdict(list)
    by_pid_pos = defaultdict(list)
    for r in all_rows:
        by_pid_pos[(r['pid'], r['pos'])].append(r['lfhf'])
    for (pid, pos), vals in by_pid_pos.items():
        if len(vals) > 10:
            sample = rng.choice(vals, size=10, replace=False).tolist()
        else:
            sample = vals
        capped[pos].extend(sample)
    capped_medians = []
    for pos in sorted(capped.keys()):
        capped_medians.append((pos, float(np.median(capped[pos]))))
    cpos = np.array([p for p, _ in capped_medians])
    cmed = np.array([m for _, m in capped_medians])
    cap_full_rho, cap_full_p = spearman_with_p(cpos, cmed)
    cap_plat_mask = (cpos >= 4) & (cpos <= 10)
    cap_plat_rho, cap_plat_p = spearman_with_p(cpos[cap_plat_mask], cmed[cap_plat_mask])
    cap_steep_mask = cpos <= 3
    cap_steep_rho, cap_steep_p = spearman_with_p(cpos[cap_steep_mask], cmed[cap_steep_mask])
    print(f'\n  Cap-10 audit: full ρ={cap_full_rho:+.3f} p={cap_full_p:.2e}  '
          f'plateau ρ={cap_plat_rho:+.3f} p={cap_plat_p:.2e}  '
          f'steep ρ={cap_steep_rho:+.3f} p={cap_steep_p:.2e}', file=sys.stderr)

    out = {
        'attribution': 'organic_hybrid',
        'n_trials': n_trials_done,
        'n_records': len(all_rows),
        'per_position': per_position,
        'cross_trial_spearman': {
            'full': {'n': int(len(pos_arr)), 'rho': full_rho, 'p': full_p},
            'steep_P0_P3': {'n': int(steep_mask.sum()), 'rho': steep_rho, 'p': steep_p},
            'plateau_P4_P10': {'n': int(plat_mask.sum()), 'rho': plat_rho, 'p': plat_p},
        },
        'cap10_spearman': {
            'full': {'rho': cap_full_rho, 'p': cap_full_p},
            'steep_P0_P3': {'rho': cap_steep_rho, 'p': cap_steep_p},
            'plateau_P4_P10': {'rho': cap_plat_rho, 'p': cap_plat_p},
        },
        'pooled_steep_vs_plateau_mw': pooled_summary,
        'per_trial_spearman': per_trial_summary,
    }

    out_json = OUT / 'summary.json'
    out_json.write_text(json.dumps(out, indent=2))

    lines = [
        '# LF/HF rank gradient under organic_hybrid\n',
        '_Generated 2026-05-03 by `scripts/lfhf_rank_gradient_hybrid.py`._\n',
        f'**N trials**: {n_trials_done:,} | **N (trial, pos) records**: {len(all_rows):,}\n',
        '## Per-position medians\n',
        '| Pos | N | median | Q25 | Q75 | 95% CI on median |',
        '|---|---|---|---|---|---|',
    ]
    for pos in pos_keys:
        s = per_position[str(pos)]
        lines.append(f'| {pos} | {s["n"]:,} | {s["median"]:.2f} | '
                     f'{s["q25"]:.2f} | {s["q75"]:.2f} | '
                     f'[{s["ci95_lo"]:.2f}, {s["ci95_hi"]:.2f}] |')

    lines.append('\n## Cross-trial Spearman on position medians\n')
    lines.append(f'- **Full**: rho = {full_rho:+.3f}, p = {full_p:.2e}, '
                 f'N = {len(pos_arr)} position medians')
    lines.append(f'- **Steep (P0-P3)**: rho = {steep_rho:+.3f}, p = {steep_p:.2e}, '
                 f'N = {int(steep_mask.sum())}')
    lines.append(f'- **Plateau (P4-P10)**: rho = {plat_rho:+.3f}, p = {plat_p:.2e}, '
                 f'N = {int(plat_mask.sum())}')
    lines.append('')
    lines.append('## Pooled steep vs plateau (Mann-Whitney on raw segments)\n')
    lines.append(f'- U = {u:,.0f}, p = {mw_p:.2e} (one-sided, steep > plateau)')
    lines.append(f'- Steep median {pooled_summary["steep_median"]:.2f} '
                 f'(N = {pooled_summary["steep_n"]:,})')
    lines.append(f'- Plateau median {pooled_summary["plateau_median"]:.2f} '
                 f'(N = {pooled_summary["plateau_n"]:,})')
    lines.append('')
    lines.append('## Cap-10 audit (per-participant <=10 segments per rank)\n')
    lines.append(f'- Full: rho = {cap_full_rho:+.3f}, p = {cap_full_p:.2e}')
    lines.append(f'- Steep: rho = {cap_steep_rho:+.3f}, p = {cap_steep_p:.2e}')
    lines.append(f'- Plateau: rho = {cap_plat_rho:+.3f}, p = {cap_plat_p:.2e}')
    lines.append('')
    lines.append('## Per-trial Spearman rho (rank vs LF/HF within trial)\n')
    lines.append('| Min segments | N trials | median rho | % negative |')
    lines.append('|---|---|---|---|')
    for cutoff in (3, 5, 7):
        s = per_trial_summary[f'min_segments_{cutoff}']
        lines.append(f'| >={cutoff} | {s["n_trials"]:,} | {s["median_rho"]:+.3f} | '
                     f'{s["pct_negative"]:.1f}% |')

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
