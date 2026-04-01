"""
Mouse-Gaze Convergence as a Function of Click Proximity

Hypothesis: Academic work on mouse-gaze distance has not factored in p(click).
The higher p(click), the closer the mouse should be to the eye — because the
mouse must converge on the gaze target to execute the click. Averaging across
entire sessions (including idle/scanning periods with low p(click)) inflates
the reported divergence.

Uses the AdSERP dataset (Latifzadeh, Gwizdka & Leiva, SIGIR 2025):
- 2,776 transactional queries on Google SERPs
- 47 participants
- Simultaneous eye tracking (Gazepoint GP3 HD, 150 Hz) + mouse tracking
- Each trial ends with a single purchase-decision click

Analysis: For each trial, compute mouse-gaze Euclidean distance at each fixation,
binned by time-remaining-to-click. If the hypothesis holds, distance should
monotonically decrease as click approaches.
"""

import os
import csv
import xml.etree.ElementTree as ET
import math
import json
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), 'AdSERP', 'data')
FIXATION_DIR = os.path.join(DATA_DIR, 'fixation-data')
MOUSE_DIR = os.path.join(DATA_DIR, 'mouse-movement-data')
METADATA_DIR = os.path.join(DATA_DIR, 'trial-metadata')


def get_trial_ids():
    """Get all trial IDs from fixation data directory."""
    ids = []
    for f in os.listdir(FIXATION_DIR):
        if f.endswith('.csv'):
            ids.append(f.replace('.csv', ''))
    return sorted(ids)


def load_metadata(trial_id):
    """Extract window dimensions for coordinate normalization."""
    path = os.path.join(METADATA_DIR, f'{trial_id}.xml')
    tree = ET.parse(path)
    root = tree.getroot()
    win = root.find('window').text.split('x')
    return {
        'window_width': int(win[0]),
        'window_height': int(win[1]),
        'screen_width': 1280,
        'screen_height': 1024,
    }


def load_fixations(trial_id):
    """Load fixation data: list of (timestamp_ms, x, y, duration_ms)."""
    path = os.path.join(FIXATION_DIR, f'{trial_id}.csv')
    fixations = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            fixations.append({
                't': int(float(row['timestamp'])),
                'x': int(float(row['FPOGX'])),
                'y': int(float(row['FPOGY'])),
                'd': int(float(row['FPOGD'])),
            })
    return fixations


def load_mouse_events(trial_id, meta):
    """Load mouse data, normalize coords to screen space (1280x1024)."""
    path = os.path.join(MOUSE_DIR, f'{trial_id}.csv')
    events = []
    click_t = None
    rx = meta['screen_width'] / meta['window_width']
    ry = meta['screen_height'] / meta['window_height']

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = int(float(row['timestamp']))
            x = int(float(row['xpos'])) * rx
            y = int(float(row['ypos'])) * ry
            evt = row['event']

            if evt == 'click':
                click_t = t

            if evt in ('mousemove', 'mouseover'):
                events.append({'t': t, 'x': x, 'y': y})

    return events, click_t


def nearest_mouse_position(fixation_t, mouse_events):
    """Find the mouse position closest in time to a fixation.
    Returns (x, y, time_delta) or None if no mouse data."""
    if not mouse_events:
        return None

    best = None
    best_dt = float('inf')

    # Binary search would be faster but N is small enough per trial
    for m in mouse_events:
        dt = abs(m['t'] - fixation_t)
        if dt < best_dt:
            best_dt = dt
            best = m

    # Only match if mouse event is within 500ms of fixation
    if best_dt > 500:
        return None

    return best['x'], best['y'], best_dt


def analyze_trial(trial_id):
    """For one trial, compute gaze-mouse distance at each fixation,
    tagged with time-to-click."""
    meta = load_metadata(trial_id)
    fixations = load_fixations(trial_id)
    mouse_events, click_t = load_mouse_events(trial_id, meta)

    if click_t is None or len(fixations) < 3 or len(mouse_events) < 3:
        return []

    results = []
    for fix in fixations:
        time_to_click = click_t - fix['t']  # ms until click

        # Only look at fixations before the click
        if time_to_click < 0:
            continue

        nearest = nearest_mouse_position(fix['t'], mouse_events)
        if nearest is None:
            continue

        mx, my, _ = nearest
        dist = math.sqrt((fix['x'] - mx) ** 2 + (fix['y'] - my) ** 2)

        results.append({
            'trial': trial_id,
            'time_to_click_ms': time_to_click,
            'distance_px': dist,
            'fix_x': fix['x'],
            'fix_y': fix['y'],
            'mouse_x': mx,
            'mouse_y': my,
        })

    return results


def bin_by_time_to_click(all_results):
    """Bin results by time-to-click intervals and compute mean distance."""
    bins = [
        (0, 500, '0-0.5s'),
        (500, 1000, '0.5-1s'),
        (1000, 2000, '1-2s'),
        (2000, 3000, '2-3s'),
        (3000, 5000, '3-5s'),
        (5000, 10000, '5-10s'),
        (10000, 20000, '10-20s'),
        (20000, 60000, '20-60s'),
    ]

    binned = {}
    for lo, hi, label in bins:
        dists = [r['distance_px'] for r in all_results
                 if lo <= r['time_to_click_ms'] < hi]
        if dists:
            binned[label] = {
                'mean': sum(dists) / len(dists),
                'median': sorted(dists)[len(dists) // 2],
                'n': len(dists),
                'std': (sum((d - sum(dists)/len(dists))**2 for d in dists) / len(dists)) ** 0.5,
            }
    return binned


def print_results(binned):
    """Print ASCII chart of convergence."""
    print("\n=== Mouse-Gaze Distance by Time-to-Click ===\n")
    print(f"{'Bin':<12} {'Mean (px)':>10} {'Median':>8} {'SD':>8} {'N':>8}")
    print("-" * 50)

    max_mean = max(b['mean'] for b in binned.values()) if binned else 1
    bar_width = 40

    for label, stats in binned.items():
        bar_len = int((stats['mean'] / max_mean) * bar_width)
        bar = '█' * bar_len
        print(f"{label:<12} {stats['mean']:>10.1f} {stats['median']:>8.1f} {stats['std']:>8.1f} {stats['n']:>8}")
        print(f"             {bar}")
    print()


def main():
    trial_ids = get_trial_ids()
    print(f"Processing {len(trial_ids)} trials...")

    all_results = []
    skipped = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(trial_ids)}...")
        try:
            results = analyze_trial(tid)
            if not results:
                skipped += 1
            else:
                all_results.extend(results)
        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"  Error on {tid}: {e}")

    print(f"\nTotal fixation-mouse pairs: {len(all_results)}")
    print(f"Trials skipped: {skipped}")

    binned = bin_by_time_to_click(all_results)
    print_results(binned)

    # Also dump raw binned data as JSON for further analysis
    out_path = os.path.join(os.path.dirname(__file__), 'convergence_results.json')
    # Convert for JSON serialization
    with open(out_path, 'w') as f:
        json.dump({
            'hypothesis': 'Mouse-gaze distance decreases as p(click) increases (time-to-click decreases)',
            'dataset': 'AdSERP (Latifzadeh, Gwizdka & Leiva, SIGIR 2025)',
            'total_pairs': len(all_results),
            'bins': binned,
        }, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == '__main__':
    main()
