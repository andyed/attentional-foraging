"""Compute per-fixation mean pupil diameter for AdSERP trials.

Maps raw 150Hz pupil samples to fixation windows and computes mean
pupil diameter per fixation (after blink removal). Outputs parallel
JSON arrays alongside fixation CSVs.

Usage:
    python compute_fixation_pupil.py                    # all trials
    python compute_fixation_pupil.py --trial p037-b2-t5 # single trial

Output: AdSERP/data/fixation-pupil/{trial_id}.json
"""

import os
import csv
import json
import argparse
import numpy as np
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'AdSERP' / 'data'
FIXATION_DIR = DATA_DIR / 'fixation-data'
PUPIL_DIR = DATA_DIR / 'pupil-data'
OUTPUT_DIR = DATA_DIR / 'fixation-pupil'

# Blink removal parameters (same as compute_lhipa.py)
BLINK_EXCLUSION_MS = 200
MIN_VALID_PCT = 0.50
MIN_VALID_SAMPLES = 3  # per fixation


def load_pupil_data(trial_id):
    """Load raw pupil CSV. Returns (timestamps, pupil_diameters, validity) arrays."""
    path = PUPIL_DIR / f'{trial_id}.csv'
    if not path.exists():
        return None, None, None

    timestamps = []
    diameters = []
    validity = []

    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                t = int(float(row['timestamp']))
                lpd = float(row['LPD'])
                rpd = float(row['RPD'])
                lpv = int(row['LPV'])
                rpv = int(row['RPV'])

                # Average both eyes if both valid, else use whichever is valid
                if lpv and rpv and lpd > 0 and rpd > 0:
                    pd = (lpd + rpd) / 2.0
                    valid = 1
                elif lpv and lpd > 0:
                    pd = lpd
                    valid = 1
                elif rpv and rpd > 0:
                    pd = rpd
                    valid = 1
                else:
                    pd = 0.0
                    valid = 0

                timestamps.append(t)
                diameters.append(pd)
                validity.append(valid)
            except (ValueError, KeyError):
                continue

    if len(timestamps) < 10:
        return None, None, None

    return np.array(timestamps), np.array(diameters), np.array(validity)


def clean_pupil(timestamps, diameters, validity):
    """Remove blinks with exclusion window. Returns (ts, clean_pd) or (None, None)."""
    invalid = (validity == 0) | (diameters <= 0)

    if invalid.any():
        invalid_times = timestamps[invalid]
        for it in invalid_times:
            mask = (timestamps >= it - BLINK_EXCLUSION_MS) & (timestamps <= it + BLINK_EXCLUSION_MS)
            invalid[mask] = True

    if invalid.sum() > len(invalid) * MIN_VALID_PCT:
        return None, None

    valid_mask = ~invalid
    if valid_mask.sum() < 10:
        return None, None

    # Interpolate over blink gaps
    clean_pd = diameters.copy()
    valid_indices = np.where(valid_mask)[0]
    invalid_indices = np.where(invalid)[0]

    if len(invalid_indices) > 0 and len(valid_indices) > 1:
        clean_pd[invalid_indices] = np.interp(
            timestamps[invalid_indices], timestamps[valid_indices], diameters[valid_indices]
        )

    return timestamps, clean_pd, valid_mask


def load_fixations(trial_id):
    """Load fixation timestamps and durations."""
    path = FIXATION_DIR / f'{trial_id}.csv'
    fixations = []
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                fixations.append({
                    't': int(float(row['timestamp'])),
                    'd': float(row['FPOGD']),
                })
            except (ValueError, KeyError):
                continue
    return fixations


def compute_fixation_pupil(trial_id):
    """Compute per-fixation mean pupil diameter for one trial.

    Returns list of dicts parallel to fixation CSV rows:
        [{mean_pd, pd_change, n_valid}, ...]
    """
    # Load data
    ts, pd, val = load_pupil_data(trial_id)
    if ts is None:
        return None

    # Clean blinks
    result = clean_pupil(ts, pd, val)
    if result[0] is None:
        return None
    clean_ts, clean_pd, valid_mask = result

    # Trial baseline
    trial_mean = np.mean(clean_pd[valid_mask])
    if trial_mean <= 0:
        return None

    # Load fixations
    fixations = load_fixations(trial_id)
    if not fixations:
        return None

    # Map pupil samples to fixation windows
    results = []
    for fix in fixations:
        t_start = fix['t']
        t_end = fix['t'] + fix['d']

        # Find pupil samples within this fixation window
        mask = (clean_ts >= t_start) & (clean_ts <= t_end) & valid_mask
        n_valid = mask.sum()

        if n_valid >= MIN_VALID_SAMPLES:
            fix_mean = float(np.mean(clean_pd[mask]))
            pd_change = float((fix_mean - trial_mean) / trial_mean)
            results.append({
                'mean_pd': round(fix_mean, 3),
                'pd_change': round(pd_change, 4),
                'n_valid': int(n_valid),
            })
        else:
            results.append({
                'mean_pd': None,
                'pd_change': None,
                'n_valid': int(n_valid),
            })

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trial', help='Single trial ID')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.trial:
        trial_ids = [args.trial]
    else:
        trial_ids = sorted(f.replace('.csv', '') for f in os.listdir(FIXATION_DIR) if f.endswith('.csv'))

    total = 0
    computed = 0
    null_count = 0

    for tid in trial_ids:
        result = compute_fixation_pupil(tid)
        if result is None:
            null_count += 1
            continue

        out_path = OUTPUT_DIR / f'{tid}.json'
        with open(out_path, 'w') as f:
            json.dump(result, f)

        computed += 1
        valid_fixes = sum(1 for r in result if r['mean_pd'] is not None)
        total += 1

        if args.trial or computed <= 3 or computed % 500 == 0:
            print(f'  {tid}: {valid_fixes}/{len(result)} fixations with pupil data')

    print(f'\nDone: {computed}/{computed + null_count} trials processed, {null_count} skipped (bad pupil data)')


if __name__ == '__main__':
    main()
