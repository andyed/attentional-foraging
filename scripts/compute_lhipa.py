"""Compute LHIPA (Low/High Index of Pupillary Activity) for AdSERP pupil data.

Implements Duchowski et al. (CHI 2020) for Gazepoint GP3 HD data at 150 Hz.
Outputs per-trial LHIPA values to stdout as JSON.

Usage:
    python compute_lhipa.py                          # all trials
    python compute_lhipa.py --output lhipa.json      # save to file
    python compute_lhipa.py --trial p004-b2-t6       # single trial

Requires: pywavelets (pip install pywavelets)

Reference:
    Duchowski, A. T., Krejtz, K., Zuber, S., & Krejtz, I. (2020).
    The Low/High Index of Pupillary Activity. CHI '20.
    https://doi.org/10.1145/3313831.3376394
"""

import os
import csv
import json
import sys
import argparse
import numpy as np
import pywt


def remove_blinks(timestamps, pupil_diameters, validity, exclusion_ms=200):
    """Remove blink samples and interpolate gaps.

    Blinks identified by validity=0 or pupil_diameter<=0.
    A 200ms exclusion window is applied around each invalid sample
    to remove pre- and post-blink artifacts.

    Returns (clean_timestamps, clean_pupil_diameters) as numpy arrays,
    or (None, None) if >50% of samples are invalid.
    """
    ts = np.array(timestamps, dtype=float)
    pd = np.array(pupil_diameters, dtype=float)
    val = np.array(validity, dtype=int)

    invalid = (val == 0) | (pd <= 0)

    if invalid.any():
        invalid_times = ts[invalid]
        for it in invalid_times:
            mask = (ts >= it - exclusion_ms) & (ts <= it + exclusion_ms)
            invalid[mask] = True

    if invalid.sum() > len(invalid) * 0.5:
        return None, None

    valid_mask = ~invalid
    if valid_mask.sum() < 50:
        return None, None

    clean_pd = pd.copy()
    valid_indices = np.where(valid_mask)[0]
    invalid_indices = np.where(invalid)[0]

    if len(invalid_indices) > 0 and len(valid_indices) > 1:
        clean_pd[invalid_indices] = np.interp(
            ts[invalid_indices], ts[valid_indices], pd[valid_indices]
        )

    return ts, clean_pd


def compute_lhipa(pupil_signal, wavelet='sym16'):
    """Compute LHIPA for a pupil diameter time series.

    Algorithm (Duchowski et al., CHI 2020):
    1. Symlet-16 wavelet decomposition
    2. Extract detail coefficients at high-frequency (level 1) and
       low-frequency (level max_level//2)
    3. Normalize each band by 1/sqrt(2^j)
    4. Compute element-wise |cD_L| / mean(|cD_H|) ratio
    5. Find modulus maxima (local peaks of |ratio|)
    6. Apply hard threshold: sigma * sqrt(2 * log2(N))
    7. Count surviving maxima, divide by signal length

    Args:
        pupil_signal: 1D array of pupil diameter values (blink-cleaned).
        wavelet: Wavelet name (default: sym16).

    Returns:
        LHIPA value (float). Higher = lower cognitive load.
        None if signal is too short for decomposition.
    """
    signal = np.array(pupil_signal, dtype=float)
    n = len(signal)

    if n < 64:
        return None

    w = pywt.Wavelet(wavelet)
    max_level = pywt.dwt_max_level(n, w.dec_len)

    if max_level < 2:
        return None

    hif = 1
    lof = max(max_level // 2, 2)

    if lof <= hif:
        lof = hif + 1
    if lof > max_level:
        return None

    cD_H = pywt.downcoef('d', signal, wavelet, mode='per', level=hif)
    cD_L = pywt.downcoef('d', signal, wavelet, mode='per', level=lof)

    cD_H = cD_H / np.sqrt(2**hif)
    cD_L = cD_L / np.sqrt(2**lof)

    ratio_factor = max(len(cD_H) // len(cD_L), 1)
    ratio = np.zeros(len(cD_L))
    for i in range(len(cD_L)):
        start = i * ratio_factor
        end = min(start + ratio_factor, len(cD_H))
        h_mean = np.mean(np.abs(cD_H[start:end]))
        if h_mean > 1e-10:
            ratio[i] = np.abs(cD_L[i]) / h_mean

    if len(ratio) < 3:
        return None

    abs_ratio = np.abs(ratio)
    maxima = []
    for i in range(1, len(abs_ratio) - 1):
        if abs_ratio[i] > abs_ratio[i - 1] and abs_ratio[i] > abs_ratio[i + 1]:
            maxima.append(abs_ratio[i])

    if not maxima:
        return 0.0

    maxima = np.array(maxima)

    sigma = np.median(np.abs(cD_H)) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log2(max(n, 2)))

    n_surviving = int(np.sum(maxima > threshold))

    return n_surviving / n


def process_trial(pupil_csv_path):
    """Load a single AdSERP pupil CSV and compute LHIPA.

    AdSERP pupil files have columns:
        timestamp, BPOGX, BPOGY, LPD, LPV, RPD, RPV

    Returns dict with lhipa, mean_pd, n_samples, valid_pct, duration_s.
    Returns None if trial is unusable.
    """
    timestamps = []
    mean_pd = []
    combined_val = []

    with open(pupil_csv_path) as f:
        for row in csv.DictReader(f):
            try:
                t = int(float(row['timestamp']))
                lpd = float(row['LPD'])
                rpd = float(row['RPD'])
                lv = int(row['LPV'])
                rv = int(row['RPV'])
            except (ValueError, KeyError):
                continue

            timestamps.append(t)
            if lv and rv:
                mean_pd.append((lpd + rpd) / 2)
                combined_val.append(1)
            elif lv:
                mean_pd.append(lpd)
                combined_val.append(1)
            elif rv:
                mean_pd.append(rpd)
                combined_val.append(1)
            else:
                mean_pd.append(0)
                combined_val.append(0)

    if len(timestamps) < 100:
        return None

    clean_ts, clean_pd = remove_blinks(timestamps, mean_pd, combined_val)
    if clean_ts is None:
        return None

    lhipa = compute_lhipa(clean_pd)
    if lhipa is None:
        return None

    return {
        'lhipa': round(lhipa, 8),
        'mean_pd': round(float(np.mean(clean_pd)), 4),
        'n_samples': len(clean_pd),
        'valid_pct': round(np.mean(combined_val) * 100, 1),
        'duration_s': round((clean_ts[-1] - clean_ts[0]) / 1000, 2),
    }


def main():
    parser = argparse.ArgumentParser(description='Compute LHIPA for AdSERP pupil data')
    parser.add_argument('--pupil-dir', default=os.path.join('AdSERP', 'data', 'pupil-data'),
                        help='Path to pupil-data directory')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--trial', '-t', default=None,
                        help='Process a single trial ID')
    args = parser.parse_args()

    if args.trial:
        path = os.path.join(args.pupil_dir, f'{args.trial}.csv')
        result = process_trial(path)
        if result:
            print(json.dumps({args.trial: result}, indent=2))
        else:
            print(f'Failed to process {args.trial}', file=sys.stderr)
            sys.exit(1)
        return

    files = sorted(f for f in os.listdir(args.pupil_dir) if f.endswith('.csv'))
    print(f'Processing {len(files)} trials...', file=sys.stderr)

    results = {}
    failed = 0
    for f in files:
        tid = f.replace('.csv', '')
        result = process_trial(os.path.join(args.pupil_dir, f))
        if result:
            results[tid] = result
        else:
            failed += 1

    print(f'Computed: {len(results)}, failed: {failed}', file=sys.stderr)

    output = json.dumps(results, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f'Saved to {args.output}', file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
