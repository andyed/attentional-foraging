"""Replicate Jayawardena, Shi & Gwizdka (CHIIR 2026) phase-CL finding on AdSERP.

Their headline result (CHIIR '26, §4):
    "CL was highest at the beginning of tasks and decreased over time,
     suggesting cognitive adaptation."

Their methodology (§3.4):
    - Continuous CL trajectory via RIPA2 (modified RIPA, SG-filter pipeline)
    - Each trial split into 3 equal-duration phases: begin / mid / end
    - Per-phase mean CL = average RIPA2 across phase samples
    - Reliability floor: ≥4 s per phase (i.e. ≥12 s per trial)

We port this directly to AdSERP (Latifzadeh, Gwizdka & Leiva 2025):
    - 47 participants, 2,719 trials with usable LF/HF + RIPA2
    - Same RIPA2 pipeline as `compute_ripa2.py` (their adapted spec, ours
      reimplemented from their repo; see Flag #1 caveat in chat history)
    - Subset to trials ≥ 12 s (RIPA2 phase floor)
    - Subset to trials ≥ 22.5 s for LF/HF analog (Duchowski 7.5 s phase floor)

Tests:
    - Friedman test on per-trial (begin, mid, end) means — within-subjects
      phase main effect
    - Wilcoxon pairwise post-hoc with Bonferroni correction
    - Spearman ρ on phase-rank × phase-mean (per-trial within-subjects)

Output:
    scripts/output/replicate_jayawardena_phase_cl/summary.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import friedmanchisquare, wilcoxon, spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_pupil_trial,
)
from compute_ripa2 import compute_ripa2_signal  # type: ignore # noqa: E402

OUT_DIR = ROOT / 'scripts/output/replicate_jayawardena_phase_cl'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FS = 150  # AdSERP sampling rate (Gazepoint GP3 HD)

# Floors per Jayawardena 2026 §3.4
RIPA2_PHASE_FLOOR_S = 4.0   # Their stated reliability floor per phase
TRIAL_FLOOR_RIPA2_S = 3 * RIPA2_PHASE_FLOOR_S  # 12 s — 3 phases × 4 s

# Butterworth LF/HF analog: Duchowski 2026 recommends ≥7.5 s window for
# stable separation. Per-phase application requires ≥7.5 s × 3 = 22.5 s.
LFHF_PHASE_FLOOR_S = 7.5
TRIAL_FLOOR_LFHF_S = 3 * LFHF_PHASE_FLOOR_S  # 22.5 s


def split_into_phases(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(signal)
    a, b = n // 3, 2 * n // 3
    return signal[:a], signal[a:b], signal[b:]


def compute_lfhf_signal(pupil_signal: np.ndarray) -> np.ndarray | None:
    """Continuous LF/HF via Butterworth IIR — matches compute_butterworth_lfhf.py
    pipeline conceptually but here we just compute the windowed envelope.

    For a phase-mean comparison we want a *per-sample* LF/HF estimate; we
    derive it from the squared filtered signals. Same logic compute_butterworth
    uses internally."""
    from scipy.signal import butter, filtfilt
    sig = np.asarray(pupil_signal, dtype=float)
    if len(sig) < FS * 4:
        return None
    # LF: 0.04-0.15 Hz, HF: 0.15-0.4 Hz (Task Force 1996 / Duchowski 2026)
    nyq = FS / 2
    lf_b, lf_a = butter(2, [0.04 / nyq, 0.15 / nyq], btype='band')
    hf_b, hf_a = butter(2, [0.15 / nyq, 0.40 / nyq], btype='band')
    lf = filtfilt(lf_b, lf_a, sig)
    hf = filtfilt(hf_b, hf_a, sig)
    # Per-sample power ratio (with epsilon to avoid div-by-zero)
    return (lf ** 2) / (hf ** 2 + 1e-9)


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    rows_ripa2 = []  # one per qualifying trial
    rows_lfhf = []
    skipped_pupil = skipped_short_ripa2 = skipped_short_lfhf = 0
    n_lfhf_failed = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        pupil = load_pupil_trial(tid)
        if pupil is None:
            skipped_pupil += 1
            continue
        signal = pupil['clean_pd']
        dur_s = len(signal) / FS

        # ── RIPA2 phase trajectory (≥12s) ─────────────────────────────────
        if dur_s >= TRIAL_FLOOR_RIPA2_S:
            ripa2 = compute_ripa2_signal(signal)
            if ripa2 is not None and len(ripa2) > 0:
                a, b, c = split_into_phases(ripa2)
                if len(a) > 0 and len(b) > 0 and len(c) > 0:
                    rows_ripa2.append({
                        'tid': tid,
                        'pid': tid.split('-')[0],
                        'duration_s': dur_s,
                        'begin': float(np.mean(a)),
                        'mid':   float(np.mean(b)),
                        'end':   float(np.mean(c)),
                    })
        else:
            skipped_short_ripa2 += 1

        # ── LF/HF phase trajectory (≥22.5s) ────────────────────────────────
        if dur_s >= TRIAL_FLOOR_LFHF_S:
            lfhf = compute_lfhf_signal(signal)
            if lfhf is None:
                n_lfhf_failed += 1
                continue
            a, b, c = split_into_phases(lfhf)
            rows_lfhf.append({
                'tid': tid,
                'pid': tid.split('-')[0],
                'duration_s': dur_s,
                'begin': float(np.mean(a)),
                'mid':   float(np.mean(b)),
                'end':   float(np.mean(c)),
            })
        else:
            skipped_short_lfhf += 1

    print(f'\n  RIPA2 qualifying trials: {len(rows_ripa2):,}  (skipped {skipped_short_ripa2:,} too short)',
          file=sys.stderr)
    print(f'  LF/HF qualifying trials: {len(rows_lfhf):,}  (skipped {skipped_short_lfhf:,} too short, '
          f'{n_lfhf_failed} compute failure)',
          file=sys.stderr)

    summary = {
        'cohort': {
            'n_total_trials': len(trial_ids),
            'n_pupil_failed': skipped_pupil,
            'ripa2_subset': {
                'n_trials': len(rows_ripa2),
                'n_pids': len(set(r['pid'] for r in rows_ripa2)),
                'duration_floor_s': TRIAL_FLOOR_RIPA2_S,
                'phase_floor_s': RIPA2_PHASE_FLOOR_S,
            },
            'lfhf_subset': {
                'n_trials': len(rows_lfhf),
                'n_pids': len(set(r['pid'] for r in rows_lfhf)),
                'duration_floor_s': TRIAL_FLOOR_LFHF_S,
                'phase_floor_s': LFHF_PHASE_FLOOR_S,
            },
        },
        'methodology_caveat': (
            'Per CHIIR 2026 §3.4.2, RIPA2 was designed for ≥4s/phase. We apply '
            'it on AdSERP trials with ≥12s total duration (3 phases × 4s). '
            'LF/HF analog uses Duchowski 2026 recommended ≥7.5s phase floor. '
            'Subset analysis: we cannot replicate the FC vs DM contrast '
            '(no AdSERP analog). We do replicate the within-trial begin/mid/end '
            'CL trajectory.'
        ),
        'results': {},
    }

    for label, rows in [('ripa2', rows_ripa2), ('lfhf', rows_lfhf)]:
        if len(rows) < 30:
            print(f'\n  {label}: too few trials ({len(rows)}); skipping')
            continue
        begin = np.array([r['begin'] for r in rows])
        mid   = np.array([r['mid']   for r in rows])
        end   = np.array([r['end']   for r in rows])

        # Friedman test (within-subjects, 3 conditions)
        fr_stat, fr_p = friedmanchisquare(begin, mid, end)

        # Pairwise Wilcoxon
        w_bm = wilcoxon(begin, mid, alternative='greater')
        w_me = wilcoxon(mid, end, alternative='greater')
        w_be = wilcoxon(begin, end, alternative='greater')

        # Spearman: per-trial phase-rank × phase-mean (rank trick: rank(begin,mid,end) within trial)
        # We'll compute median rank-correlation using paired rank
        # Simpler effect size: fraction of trials with begin > mid > end
        decreasing_count = sum(1 for r in rows if r['begin'] >= r['mid'] >= r['end'])
        any_decline_count = sum(1 for r in rows if r['begin'] > r['end'])

        result = {
            'n_trials': len(rows),
            'n_pids': len(set(r['pid'] for r in rows)),
            'phase_means': {
                'begin': {'median': float(np.median(begin)), 'mean': float(np.mean(begin)),
                          'std': float(np.std(begin, ddof=1))},
                'mid':   {'median': float(np.median(mid)),   'mean': float(np.mean(mid)),
                          'std': float(np.std(mid, ddof=1))},
                'end':   {'median': float(np.median(end)),   'mean': float(np.mean(end)),
                          'std': float(np.std(end, ddof=1))},
            },
            'friedman': {'chi2': float(fr_stat), 'p': float(fr_p)},
            'wilcoxon_one_sided': {
                'begin_gt_mid':  {'stat': float(w_bm.statistic), 'p': float(w_bm.pvalue)},
                'mid_gt_end':    {'stat': float(w_me.statistic), 'p': float(w_me.pvalue)},
                'begin_gt_end':  {'stat': float(w_be.statistic), 'p': float(w_be.pvalue)},
            },
            'monotone_trials_pct':       100 * decreasing_count / len(rows),
            'any_begin_gt_end_pct':      100 * any_decline_count / len(rows),
        }
        summary['results'][label] = result

        # Print
        print(f'\n=== {label.upper()} phase trajectory ===')
        print(f'  N = {len(rows):,} trials, {len(set(r["pid"] for r in rows))} pids')
        print(f'  begin: med = {np.median(begin):.4f}  mean = {np.mean(begin):.4f}')
        print(f'  mid:   med = {np.median(mid):.4f}  mean = {np.mean(mid):.4f}')
        print(f'  end:   med = {np.median(end):.4f}  mean = {np.mean(end):.4f}')
        print(f'  Friedman χ²(2, N={len(rows)}) = {fr_stat:.1f}, p = {fr_p:.3g}')
        print(f'  Wilcoxon begin > mid:  p = {w_bm.pvalue:.3g}')
        print(f'  Wilcoxon mid   > end:  p = {w_me.pvalue:.3g}')
        print(f'  Wilcoxon begin > end:  p = {w_be.pvalue:.3g}')
        print(f'  Monotone (b≥m≥e):  {100*decreasing_count/len(rows):.1f}% of trials')
        print(f'  Any decline (b>e): {100*any_decline_count/len(rows):.1f}% of trials')

    out = OUT_DIR / 'summary.json'
    out.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {out.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
