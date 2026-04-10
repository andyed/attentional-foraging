"""Compute per-position RIPA2 cognitive load for AdSERP pupil data.

Implements Jayawardena, Jayawardana & Gwizdka (2025) RIPA2 — a near-real-time
pupillometric index that approximates LHIPA using Savitzky-Golay derivative
filters instead of wavelet decomposition.

RIPA2 targets two frequency bands via SG filter parameters:
  - VLF (~0.29 Hz): slow, luminance-driven pupil changes
  - LF  (~4 Hz): faster, cognitive-load-related oscillations

Metric: (SG_LF · P)² − (SG_VLF · P)² — squared difference, not ratio.
Output clipped to [0, 1.5].

Parallel structure to compute_butterworth_lfhf.py for direct comparison.

Usage:
    python compute_ripa2.py                          # all trials
    python compute_ripa2.py --output ripa2.json      # save to file
    python compute_ripa2.py --trial p004-b2-t6       # single trial
    python compute_ripa2.py --compare butter.json    # side-by-side comparison

Reference:
    Jayawardena, G., Jayawardana, Y., & Gwizdka, J. (2025). Measuring Mental
    Effort in Real Time Using Pupillometry. J. Eye Movement Research.
    PMC: 12733481
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter

# Add notebooks-v2 to path for data_loader
sys.path.insert(0, str(Path(__file__).parent.parent / 'notebooks-v2'))
from data_loader import (
    get_trial_ids, load_pupil_trial, load_fixations, load_mouse_events,
    get_trial_meta, interpolate_scroll, result_band_tops, count_results_html,
    assign_fixation_to_position, click_to_position,
)

# ── RIPA2 parameters (Jayawardena et al. 2025) ────────────────────────────
#
# Published for 300 Hz. AdSERP is 150 Hz — scale window lengths proportionally.
#
# At 300 Hz:
#   VLF: M=486, N=2  →  cutoff ≈ 0.29 Hz
#   LF:  M=60,  N=4  →  cutoff ≈ 4 Hz
#
# Cutoff ≈ (N+1) / (3.2 × M × (1/fs))  [Schafer 2011 approximation]
# To preserve cutoff at different fs, scale M linearly with fs.
#
# At 150 Hz:
#   VLF: M = round(486 * 150/300) = 243  (must be odd → 243)
#   LF:  M = round(60 * 150/300) = 30    (must be odd → 31)
#
# Verify cutoffs:
#   VLF: (2+1)/(3.2 × 243 × 1/150) ≈ 0.29 Hz ✓
#   LF:  (4+1)/(3.2 × 31 × 1/150) ≈ 7.6 Hz — higher than published 4 Hz
#
# More precise scaling: match the normalized cutoff (M/fs ratio)
#   VLF at 300Hz: 486/300 = 1.62 → at 150Hz: round(1.62 * 150) = 243 ✓
#   LF  at 300Hz: 60/300 = 0.20 → at 150Hz: round(0.20 * 150) = 30 → 31 (odd)
#
# The LF cutoff shifts up slightly at 150Hz. This is conservative —
# captures more of the cognitive band, may slightly inflate RIPA2 values.

FS = 150        # Gazepoint GP3 HD sampling rate

# SG filter parameters scaled for 150 Hz
VLF_WINDOW = 243   # odd, targets ~0.29 Hz
VLF_POLYORDER = 2
LF_WINDOW = 31     # odd, targets ~4 Hz (slightly higher at 150Hz)
LF_POLYORDER = 4

MIN_SAMPLES = 150  # 1 second minimum (matching Butterworth script)


def compute_ripa2_signal(pupil_signal):
    """Compute RIPA2 for entire pupil signal.

    Returns RIPA2 value per sample, clipped to [0, 1.5].

    RIPA2 = (SG_LF' · P)² − (SG_VLF' · P)²

    where SG_X' is the first derivative from the Savitzky-Golay filter
    and P is the pupil diameter signal.
    """
    signal = np.asarray(pupil_signal, dtype=float)
    n = len(signal)

    # Need enough samples for the VLF window
    if n < VLF_WINDOW:
        return np.zeros(n)

    # SG first derivatives
    # deriv=1 gives the first derivative estimate at each point
    sg_vlf = savgol_filter(signal, VLF_WINDOW, VLF_POLYORDER, deriv=1)
    sg_lf = savgol_filter(signal, LF_WINDOW, LF_POLYORDER, deriv=1)

    # RIPA2 metric: (LF_deriv · P)² − (VLF_deriv · P)²
    ripa2 = (sg_lf * signal) ** 2 - (sg_vlf * signal) ** 2

    # Clip to [0, 1.5] per published spec
    ripa2 = np.clip(ripa2, 0, 1.5)

    return ripa2


def compute_ripa2_segment(ripa2_signal, indices):
    """Compute mean RIPA2 for a segment of samples.

    Returns mean RIPA2 (float) or None if insufficient samples.
    """
    if len(indices) < MIN_SAMPLES:
        return None

    segment = ripa2_signal[indices]
    return float(np.mean(segment))


def identify_forward_pass(fixations, scroll_ts, scroll_ys, tops, n_results):
    """Identify forward-pass fixations per position.

    (Identical to compute_butterworth_lfhf.py — shared logic.)
    """
    forward_segments = {}
    high_water = -1
    visited = set()

    for fix in fixations:
        scroll_y = interpolate_scroll(fix['t'], scroll_ts, scroll_ys)
        pos = assign_fixation_to_position(fix['y'], scroll_y, tops, n_results)
        if pos is None or pos < 0:
            continue

        if pos >= high_water:
            high_water = pos
            if pos not in visited:
                visited.add(pos)
                forward_segments[pos] = []
            forward_segments[pos].append((fix['t'], fix['t'] + fix['d']))

    return forward_segments


def process_trial(trial_id):
    """Process a single trial: compute RIPA2, segment by position.

    Returns dict with per-position RIPA2 values, or None if trial unusable.
    """
    pupil = load_pupil_trial(trial_id)
    if pupil is None:
        return None

    ts = pupil['ts']
    clean_pd = pupil['clean_pd']

    if len(clean_pd) < MIN_SAMPLES * 2:
        return None

    # Compute RIPA2 for entire trial
    ripa2_signal = compute_ripa2_signal(clean_pd)

    # Also compute whole-trial summary
    trial_ripa2 = float(np.mean(ripa2_signal))

    # Load fixation and scroll data
    fixations = load_fixations(trial_id)
    if not fixations:
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

    # Find click position (coordinate-safe: clicks[-1][2] is page-space).
    click_pos = click_to_position(clicks, tops, n_results)

    # Identify forward-pass fixation segments per position
    forward_segs = identify_forward_pass(fixations, scroll_ts, scroll_ys, tops, n_results)

    if not forward_segs:
        return None

    # For each position, find pupil sample indices and compute RIPA2
    positions = []
    for pos in sorted(forward_segs.keys()):
        fix_windows = forward_segs[pos]

        indices = []
        for (start_ms, end_ms) in fix_windows:
            mask = (ts >= start_ms) & (ts <= end_ms)
            indices.extend(np.where(mask)[0].tolist())

        indices = np.array(sorted(set(indices)))
        if len(indices) == 0:
            continue

        ripa2_val = compute_ripa2_segment(ripa2_signal, indices)
        duration_s = len(indices) / FS

        positions.append({
            'pos': pos,
            'ripa2': round(ripa2_val, 6) if ripa2_val is not None else None,
            'n_samples': len(indices),
            'duration_s': round(duration_s, 3),
        })

    if not positions:
        return None

    return {
        'positions': positions,
        'click_pos': click_pos,
        'n_positions_visited': len(positions),
        'trial_samples': len(clean_pd),
        'trial_duration_s': round(len(clean_pd) / FS, 2),
        'trial_ripa2_mean': round(trial_ripa2, 6),
    }


def compare_metrics(ripa2_results, butterworth_path):
    """Compare RIPA2 to Butterworth LF/HF per position.

    Prints correlation, per-position means, and whether both detect
    the positional gradient (CL decreases with rank).
    """
    with open(butterworth_path) as f:
        butter_results = json.load(f)

    # Collect paired observations: (position, lfhf, ripa2) across all trials
    paired = []
    lfhf_by_pos = {}
    ripa2_by_pos = {}

    common_trials = set(ripa2_results.keys()) & set(butter_results.keys())
    print(f'\nCommon trials: {len(common_trials)}')

    for tid in common_trials:
        r_trial = ripa2_results[tid]
        b_trial = butter_results[tid]

        # Index by position
        r_by_pos = {p['pos']: p['ripa2'] for p in r_trial['positions'] if p['ripa2'] is not None}
        b_by_pos = {p['pos']: p['lfhf'] for p in b_trial['positions'] if p['lfhf'] is not None}

        for pos in set(r_by_pos.keys()) & set(b_by_pos.keys()):
            paired.append((pos, b_by_pos[pos], r_by_pos[pos]))

            lfhf_by_pos.setdefault(pos, []).append(b_by_pos[pos])
            ripa2_by_pos.setdefault(pos, []).append(r_by_pos[pos])

    if not paired:
        print('No paired observations found.')
        return

    positions, lfhf_vals, ripa2_vals = zip(*paired)
    positions = np.array(positions)
    lfhf_vals = np.array(lfhf_vals)
    ripa2_vals = np.array(ripa2_vals)

    # Correlation between metrics
    corr = np.corrcoef(lfhf_vals, ripa2_vals)[0, 1]
    print(f'Pearson r (LF/HF vs RIPA2): {corr:.3f}  (n={len(paired)} observations)')

    # Per-position means
    print(f'\n{"Pos":>4}  {"LF/HF":>10}  {"RIPA2":>10}  {"n":>5}')
    print('-' * 35)
    all_positions = sorted(set(list(lfhf_by_pos.keys()) + list(ripa2_by_pos.keys())))
    lfhf_means = []
    ripa2_means = []
    pos_list = []
    for pos in all_positions:
        lm = np.mean(lfhf_by_pos.get(pos, [np.nan]))
        rm = np.mean(ripa2_by_pos.get(pos, [np.nan]))
        n = min(len(lfhf_by_pos.get(pos, [])), len(ripa2_by_pos.get(pos, [])))
        print(f'{pos:>4}  {lm:>10.4f}  {rm:>10.6f}  {n:>5}')
        if not np.isnan(lm) and not np.isnan(rm):
            lfhf_means.append(lm)
            ripa2_means.append(rm)
            pos_list.append(pos)

    # Positional gradient (Spearman rank correlation with position)
    from scipy.stats import spearmanr
    if len(pos_list) >= 4:
        rho_lfhf, p_lfhf = spearmanr(pos_list, lfhf_means)
        rho_ripa2, p_ripa2 = spearmanr(pos_list, ripa2_means)
        print(f'\nPositional gradient (mean across trials):')
        print(f'  LF/HF  × position: ρ = {rho_lfhf:+.3f}, p = {p_lfhf:.4f}')
        print(f'  RIPA2  × position: ρ = {rho_ripa2:+.3f}, p = {p_ripa2:.4f}')

        if rho_lfhf < 0 and p_lfhf < 0.05:
            print('  → LF/HF confirms Butterworth finding (CL decreases with position)')
        else:
            print('  → LF/HF: no significant positional gradient')

        if rho_ripa2 < 0 and p_ripa2 < 0.05:
            print('  → RIPA2 also detects the positional gradient')
        else:
            print('  → RIPA2 does NOT detect the positional gradient')
            if rho_lfhf < 0 and p_lfhf < 0.05:
                print('    ⚠ Real-time approximation loses the positional signal')


def main():
    parser = argparse.ArgumentParser(description='Compute per-position RIPA2 cognitive load')
    parser.add_argument('--trial', help='Process single trial ID')
    parser.add_argument('--output', '-o', help='Output JSON path')
    parser.add_argument('--compare', help='Path to Butterworth LF/HF JSON for comparison')
    args = parser.parse_args()

    if args.trial:
        result = process_trial(args.trial)
        if result is None:
            print(f'{args.trial}: unusable', file=sys.stderr)
            sys.exit(1)
        out = {args.trial: result}
    else:
        trial_ids = get_trial_ids()
        out = {}
        n_ok, n_fail = 0, 0
        for i, tid in enumerate(trial_ids):
            if (i + 1) % 100 == 0:
                print(f'  {i+1}/{len(trial_ids)}...', file=sys.stderr)
            result = process_trial(tid)
            if result is not None:
                out[tid] = result
                n_ok += 1
            else:
                n_fail += 1

        print(f'\nDone: {n_ok} trials processed, {n_fail} skipped', file=sys.stderr)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(out, f, indent=2)
        print(f'Wrote {len(out)} trials to {output_path}', file=sys.stderr)
    else:
        if not args.compare:
            json.dump(out, sys.stdout, indent=2)

    # Compare if requested
    if args.compare:
        compare_metrics(out, args.compare)


if __name__ == '__main__':
    main()
