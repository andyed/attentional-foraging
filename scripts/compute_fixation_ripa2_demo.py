"""Compute per-fixation RIPA2 for demo trials (matching fixation-lfhf-demo.json format).

For each fixation, computes the mean RIPA2 value over the pupil samples
that fall within the fixation's time window. Requires at least 150 samples
(1 second) for a valid estimate — shorter fixations get null.

Output: fixation-ripa2-demo.json — same structure as fixation-lfhf-demo.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter

sys.path.insert(0, str(Path(__file__).parent.parent / 'notebooks-v2'))
from data_loader import load_pupil_trial, load_fixations

# RIPA2 parameters scaled for 150 Hz (see compute_ripa2.py for derivation)
FS = 150
VLF_WINDOW = 243
VLF_POLYORDER = 2
LF_WINDOW = 31
LF_POLYORDER = 4

# For per-fixation, use a shorter minimum since fixations are brief.
# RIPA2 is pointwise (no windowed variance like Butterworth), so we can
# compute it for shorter segments. But we need VLF_WINDOW samples for
# the SG filter to be valid — the per-fixation value comes from the
# pre-computed full-trial RIPA2 signal, so even short fixations get values.
MIN_FIXATION_SAMPLES = 5  # ~33ms — just need a few samples to average


def compute_ripa2_signal(pupil_signal):
    """Compute RIPA2 for entire pupil signal. Returns per-sample values."""
    signal = np.asarray(pupil_signal, dtype=float)
    n = len(signal)
    if n < VLF_WINDOW:
        return np.zeros(n)

    sg_vlf = savgol_filter(signal, VLF_WINDOW, VLF_POLYORDER, deriv=1)
    sg_lf = savgol_filter(signal, LF_WINDOW, LF_POLYORDER, deriv=1)

    # Bug fix 2026-04-25 per JEMR 2025 Algorithm 1: was `(sg * signal)² − ...`
    ripa2 = sg_lf ** 2 - sg_vlf ** 2
    return np.clip(ripa2, 0, 1.5)


def main():
    # Load demo trial IDs from existing LFHF file
    lfhf_path = Path(__file__).parent.parent / 'AdSERP' / 'data' / 'fixation-lfhf-demo.json'
    with open(lfhf_path) as f:
        lfhf_data = json.load(f)

    demo_trials = list(lfhf_data.keys())
    print(f'Computing per-fixation RIPA2 for {len(demo_trials)} demo trials')

    result = {}
    for tid in demo_trials:
        pupil = load_pupil_trial(tid)
        if pupil is None:
            result[tid] = [None] * len(lfhf_data[tid])
            print(f'  {tid}: no pupil data')
            continue

        ts = pupil['ts']
        clean_pd = pupil['clean_pd']

        # Compute RIPA2 for entire trial
        ripa2_signal = compute_ripa2_signal(clean_pd)

        # Load fixations
        fixations = load_fixations(tid)

        per_fix = []
        for fix in fixations:
            # Find pupil samples within this fixation
            mask = (ts >= fix['t']) & (ts <= fix['t'] + fix['d'])
            indices = np.where(mask)[0]

            if len(indices) < MIN_FIXATION_SAMPLES:
                per_fix.append(None)
            else:
                val = float(np.mean(ripa2_signal[indices]))
                per_fix.append(round(val, 3))

        result[tid] = per_fix
        n_valid = sum(1 for v in per_fix if v is not None)
        print(f'  {tid}: {len(per_fix)} fixations, {n_valid} with RIPA2')

    # Save
    out_path = Path(__file__).parent.parent / 'AdSERP' / 'data' / 'fixation-ripa2-demo.json'
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'\nWrote {out_path}')


if __name__ == '__main__':
    main()
