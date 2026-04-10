"""Compute per-position Butterworth LF/HF cognitive load for AdSERP pupil data.

Implements Duchowski (2026) IIR Butterworth approach for real-time LF/HF
pupil power ratio. Filters the entire blink-cleaned trial stream, then
segments by result position during forward scanning.

Higher LF/HF ratio = higher cognitive load (low-frequency oscillations
dominate under task-related autonomic activity).

Usage:
    python compute_butterworth_lfhf.py                          # all trials
    python compute_butterworth_lfhf.py --output lfhf.json       # save to file
    python compute_butterworth_lfhf.py --trial p004-b2-t6       # single trial

Requires: scipy

Reference:
    Duchowski, A. T. (2026). Real-Time Cognitive Load Measurement of
    Pupillary Oscillation. Proc. ACM Comput. Graph. Interact. Tech. 9, 2.
    https://doi.org/10.1145/3803537
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

# Add notebooks-v2 to path for data_loader
sys.path.insert(0, str(Path(__file__).parent.parent / 'notebooks-v2'))
from data_loader import (
    get_trial_ids, load_pupil_trial, load_fixations, load_mouse_events,
    get_trial_meta, interpolate_scroll, result_band_tops, count_results_html,
    assign_fixation_to_position, click_to_position,
)

# ── Butterworth filter parameters (Duchowski 2026) ───────────────────────

FS = 150        # Gazepoint GP3 HD sampling rate
ORDER = 4       # Butterworth filter order
LF_CUTOFF = 1.6       # Hz — lowpass for LF band (0–1.6 Hz)
HF_BAND = (1.6, 4.0)  # Hz — bandpass for HF band
MIN_SAMPLES = 150      # 1 second at 150 Hz — Duchowski's stated minimum


def design_filters(fs=FS, order=ORDER):
    """Design LF lowpass and HF bandpass Butterworth filters."""
    lf_sos = butter(order, LF_CUTOFF, btype='low', fs=fs, output='sos')
    hf_sos = butter(order, HF_BAND, btype='band', fs=fs, output='sos')
    return lf_sos, hf_sos


def compute_lfhf_ratio(lf_signal, hf_signal, indices):
    """Compute LF/HF variance ratio for samples at given indices.

    Returns ratio (float) or None if insufficient samples or zero HF power.
    """
    if len(indices) < MIN_SAMPLES:
        return None

    lf_power = np.var(lf_signal[indices])
    hf_power = np.var(hf_signal[indices])

    if hf_power < 1e-20:
        return None

    return float(lf_power / hf_power)


def identify_forward_pass(fixations, scroll_ts, scroll_ys, tops, n_results):
    """Identify forward-pass fixations per position.

    Tracks the high-water mark of positions visited. A fixation counts as
    forward-pass if it's at or above the current high-water mark. Regressions
    are skipped but don't terminate tracking — the user may continue forward
    after a brief regression.

    Returns dict: {position: [(fix_start_ms, fix_end_ms), ...]} for
    forward-pass fixations only.
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
            # Only include first-visit fixations at each position
            if pos not in visited:
                visited.add(pos)
                forward_segments[pos] = []
            forward_segments[pos].append((fix['t'], fix['t'] + fix['d']))

    return forward_segments


def process_trial(trial_id, lf_sos, hf_sos):
    """Process a single trial: filter stream, segment by position, compute LF/HF.

    Returns dict with per-position LF/HF ratios, or None if trial unusable.
    """
    pupil = load_pupil_trial(trial_id)
    if pupil is None:
        return None

    ts = pupil['ts']
    clean_pd = pupil['clean_pd']

    if len(clean_pd) < MIN_SAMPLES * 2:
        return None

    # Filter the entire trial stream (zero-phase)
    lf_signal = sosfiltfilt(lf_sos, clean_pd)
    hf_signal = sosfiltfilt(hf_sos, clean_pd)

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

    # For each position, find pupil sample indices and compute LF/HF
    positions = []
    for pos in sorted(forward_segs.keys()):
        fix_windows = forward_segs[pos]

        # Find pupil sample indices within these fixation windows
        indices = []
        for (start_ms, end_ms) in fix_windows:
            mask = (ts >= start_ms) & (ts <= end_ms)
            indices.extend(np.where(mask)[0].tolist())

        indices = np.array(sorted(set(indices)))
        if len(indices) == 0:
            continue

        ratio = compute_lfhf_ratio(lf_signal, hf_signal, indices)
        duration_s = len(indices) / FS

        positions.append({
            'pos': pos,
            'lfhf': round(ratio, 6) if ratio is not None else None,
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
    }


def main():
    parser = argparse.ArgumentParser(description='Compute per-position Butterworth LF/HF ratio')
    parser.add_argument('--trial', help='Process single trial ID')
    parser.add_argument('--output', '-o', help='Output JSON path')
    args = parser.parse_args()

    lf_sos, hf_sos = design_filters()

    if args.trial:
        result = process_trial(args.trial, lf_sos, hf_sos)
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
            result = process_trial(tid, lf_sos, hf_sos)
            if result is not None:
                out[tid] = result
                n_ok += 1
            else:
                n_fail += 1

        print(f'\nDone: {n_ok} trials processed, {n_fail} skipped', file=sys.stderr)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(out, f, indent=2)
        print(f'Wrote {len(out)} trials to {output_path}', file=sys.stderr)
    else:
        json.dump(out, sys.stdout, indent=2)


if __name__ == '__main__':
    main()
