"""Encoding vs retrieval: is cognitive load front-loaded to first-pass?

Pirolli/IFT prediction: regressions are scent-following, not decisions.
The cognitive work happened during the FIRST-PASS encoding of the item,
not at the regression (retrieval). Test: compare RIPA2 and LF/HF at
first-pass fixations on items that later receive a regression vs items
that don't.

Outputs JSON with per-trial regression analysis for notebook consumption.

Usage:
    uv run python scripts/compute_encoding_vs_retrieval.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter, butter, sosfiltfilt

sys.path.insert(0, str(Path(__file__).parent.parent / 'notebooks-v2'))
from data_loader import (
    get_trial_ids, load_pupil_trial, load_fixations, load_mouse_events,
    get_trial_meta, interpolate_scroll, result_band_tops, count_results_html,
    assign_fixation_to_position,
)

# RIPA2 parameters (150 Hz)
VLF_WINDOW = 243
VLF_POLYORDER = 2
LF_WINDOW = 31
LF_POLYORDER = 4
FS = 150

# Butterworth parameters
ORDER = 4
LF_CUTOFF = 1.6
HF_BAND = (1.6, 4.0)
MIN_SAMPLES = 150


def compute_ripa2_signal(pupil_signal):
    signal = np.asarray(pupil_signal, dtype=float)
    if len(signal) < VLF_WINDOW:
        return np.zeros(len(signal))
    sg_vlf = savgol_filter(signal, VLF_WINDOW, VLF_POLYORDER, deriv=1)
    sg_lf = savgol_filter(signal, LF_WINDOW, LF_POLYORDER, deriv=1)
    # Bug fix 2026-04-25 per JEMR 2025 Algorithm 1: was `(sg * signal)² − ...`
    # which introduced a spurious P² weighting; correct formula is `LF² − VLF²`.
    ripa2 = sg_lf ** 2 - sg_vlf ** 2
    return np.clip(ripa2, 0, 1.5)


def compute_lfhf_signals(pupil_signal):
    signal = np.asarray(pupil_signal, dtype=float)
    if len(signal) < MIN_SAMPLES * 2:
        return None, None
    lf_sos = butter(ORDER, LF_CUTOFF, btype='low', fs=FS, output='sos')
    hf_sos = butter(ORDER, HF_BAND, btype='band', fs=FS, output='sos')
    padlen = min(3 * max(len(lf_sos), len(hf_sos)), len(signal) - 1)
    if padlen < 1:
        return None, None
    lf = sosfiltfilt(lf_sos, signal, padlen=padlen)
    hf = sosfiltfilt(hf_sos, signal, padlen=padlen)
    return lf, hf


def get_fixation_metric(ts, signal, fix_t, fix_d, min_samples=5):
    """Mean of signal during a fixation window."""
    mask = (ts >= fix_t) & (ts <= fix_t + fix_d)
    indices = np.where(mask)[0]
    if len(indices) < min_samples:
        return None
    return float(np.mean(signal[indices]))


def get_fixation_lfhf(ts, lf_sig, hf_sig, fix_t, fix_d):
    """LF/HF ratio during a fixation window."""
    mask = (ts >= fix_t) & (ts <= fix_t + fix_d)
    indices = np.where(mask)[0]
    if len(indices) < MIN_SAMPLES:
        return None
    lf_power = np.var(lf_sig[indices])
    hf_power = np.var(hf_sig[indices])
    if hf_power < 1e-20:
        return None
    return float(lf_power / hf_power)


def process_trial(trial_id):
    """For each trial, identify first-pass fixations and regression targets."""
    pupil = load_pupil_trial(trial_id)
    if pupil is None:
        return None

    ts = pupil['ts']
    clean_pd = pupil['clean_pd']
    if len(clean_pd) < MIN_SAMPLES * 2:
        return None

    fixations = load_fixations(trial_id)
    if not fixations or len(fixations) < 5:
        return None

    events, scrolls, clicks = load_mouse_events(trial_id)
    doc_h, scr_h, page_ts = get_trial_meta(trial_id)
    if doc_h is None:
        return None

    scroll_ts = [s[0] for s in scrolls]
    scroll_ys = [s[1] for s in scrolls]

    n_results = count_results_html(trial_id)
    if n_results is None:
        n_results = 11
    tops = result_band_tops(n_results, doc_h)

    # Assign each fixation to a result position
    fix_positions = []
    for fix in fixations:
        # FPOGY is page-space (2026-04-12 audit) — bisect directly, no scroll.
        pos = assign_fixation_to_position(fix['y'], tops, n_results)
        fix_positions.append(pos)

    # Identify first-pass vs regression fixations per position
    # First-pass: first time a position is visited
    # Regression: any subsequent visit to a previously-visited position
    first_visit_idx = {}  # pos -> index of first fixation at that position
    regression_targets = set()  # positions that receive a regression
    high_water = -1

    for i, pos in enumerate(fix_positions):
        if pos is None or pos < 0:
            continue
        if pos not in first_visit_idx:
            first_visit_idx[pos] = i
            if pos >= high_water:
                high_water = pos
        else:
            # This is a revisit — is it a regression (going back)?
            if pos < high_water:
                regression_targets.add(pos)

    if not first_visit_idx:
        return None

    # Compute pupil metrics
    ripa2_signal = compute_ripa2_signal(clean_pd)
    lf_sig, hf_sig = compute_lfhf_signals(clean_pd)

    # For each first-visit fixation, compute RIPA2 and LF/HF
    results = []
    for pos, fix_idx in first_visit_idx.items():
        fix = fixations[fix_idx]
        ripa2_val = get_fixation_metric(ts, ripa2_signal, fix['t'], fix['d'])

        lfhf_val = None
        if lf_sig is not None:
            lfhf_val = get_fixation_lfhf(ts, lf_sig, hf_sig, fix['t'], fix['d'])

        will_regress = pos in regression_targets

        results.append({
            'pos': pos,
            'fix_idx': fix_idx,
            'ripa2': round(ripa2_val, 6) if ripa2_val is not None else None,
            'lfhf': round(lfhf_val, 4) if lfhf_val is not None else None,
            'will_regress': will_regress,
            'duration_ms': fix['d'],
        })

    return {
        'first_pass': results,
        'n_regression_targets': len(regression_targets),
        'n_positions_visited': len(first_visit_idx),
        'n_fixations': len(fixations),
    }


def main():
    trial_ids = get_trial_ids()
    all_results = {}
    n_ok, n_fail = 0, 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}...', file=sys.stderr)
        result = process_trial(tid)
        if result is not None:
            all_results[tid] = result
            n_ok += 1
        else:
            n_fail += 1

    print(f'\n{n_ok} trials processed, {n_fail} skipped', file=sys.stderr)

    # Aggregate: first-pass RIPA2/LF/HF at regression targets vs non-targets
    reg_ripa2 = []
    noreg_ripa2 = []
    reg_lfhf = []
    noreg_lfhf = []
    reg_dur = []
    noreg_dur = []

    for tid, trial in all_results.items():
        for fp in trial['first_pass']:
            if fp['will_regress']:
                if fp['ripa2'] is not None:
                    reg_ripa2.append(fp['ripa2'])
                if fp['lfhf'] is not None:
                    reg_lfhf.append(fp['lfhf'])
                reg_dur.append(fp['duration_ms'])
            else:
                if fp['ripa2'] is not None:
                    noreg_ripa2.append(fp['ripa2'])
                if fp['lfhf'] is not None:
                    noreg_lfhf.append(fp['lfhf'])
                noreg_dur.append(fp['duration_ms'])

    print(f'\n=== ENCODING VS RETRIEVAL (Pirolli prediction) ===')
    print(f'First-pass fixations at positions that WILL receive a regression:')
    print(f'  N = {len(reg_ripa2)} (RIPA2), {len(reg_lfhf)} (LF/HF)')
    print(f'First-pass fixations at positions that will NOT be regressed to:')
    print(f'  N = {len(noreg_ripa2)} (RIPA2), {len(noreg_lfhf)} (LF/HF)')

    from scipy.stats import mannwhitneyu

    if reg_ripa2 and noreg_ripa2:
        u, p = mannwhitneyu(reg_ripa2, noreg_ripa2, alternative='greater')
        print(f'\nRIPA2 at first-pass encoding:')
        print(f'  Will-regress median:  {np.median(reg_ripa2):.6f}')
        print(f'  No-regress median:    {np.median(noreg_ripa2):.6f}')
        print(f'  Ratio: {np.median(reg_ripa2) / np.median(noreg_ripa2):.3f}x')
        print(f'  U = {u:.0f}, p = {p:.6f} (one-sided: will-regress > no-regress)')

    if reg_lfhf and noreg_lfhf:
        u, p = mannwhitneyu(reg_lfhf, noreg_lfhf, alternative='greater')
        print(f'\nLF/HF at first-pass encoding:')
        print(f'  Will-regress median:  {np.median(reg_lfhf):.4f}')
        print(f'  No-regress median:    {np.median(noreg_lfhf):.4f}')
        print(f'  Ratio: {np.median(reg_lfhf) / np.median(noreg_lfhf):.3f}x')
        print(f'  U = {u:.0f}, p = {p:.6f} (one-sided: will-regress > no-regress)')

    if reg_dur and noreg_dur:
        u, p = mannwhitneyu(reg_dur, noreg_dur, alternative='greater')
        print(f'\nFirst-pass dwell time:')
        print(f'  Will-regress median:  {np.median(reg_dur):.0f} ms')
        print(f'  No-regress median:    {np.median(noreg_dur):.0f} ms')
        print(f'  U = {u:.0f}, p = {p:.6f}')

    # Save for notebook
    out_path = Path(__file__).parent.parent / 'AdSERP' / 'data' / 'encoding-vs-retrieval.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f)
    print(f'\nWrote {len(all_results)} trials to {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
