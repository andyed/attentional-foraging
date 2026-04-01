"""
Per-trial phase detection: scanning → evaluation → acquisition → click

For each trial, compute the mouse-gaze distance trajectory over time-to-click,
find the inflection point where distance starts its steep decline (evaluation onset),
and characterize the evaluation phase duration.

The hypothesis: there's a per-trial "evaluation window" between scanning (mouse parked,
eye foraging) and acquisition (mouse converging on target). The duration of this window
varies by trial difficulty / SERP complexity and could be calibrated per session.
"""

import os
import csv
import xml.etree.ElementTree as ET
import math
import json
import statistics
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), 'AdSERP', 'data')
FIXATION_DIR = os.path.join(DATA_DIR, 'fixation-data')
MOUSE_DIR = os.path.join(DATA_DIR, 'mouse-movement-data')
METADATA_DIR = os.path.join(DATA_DIR, 'trial-metadata')


def load_metadata(trial_id):
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
    path = os.path.join(FIXATION_DIR, f'{trial_id}.csv')
    fixations = []
    with open(path) as f:
        for row in csv.DictReader(f):
            fixations.append({
                't': int(float(row['timestamp'])),
                'x': int(float(row['FPOGX'])),
                'y': int(float(row['FPOGY'])),
                'd': int(float(row['FPOGD'])),
            })
    return fixations


def load_mouse_events(trial_id, meta):
    path = os.path.join(MOUSE_DIR, f'{trial_id}.csv')
    events = []
    click_t = None
    rx = meta['screen_width'] / meta['window_width']
    ry = meta['screen_height'] / meta['window_height']
    with open(path) as f:
        for row in csv.DictReader(f):
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
    best = None
    best_dt = float('inf')
    for m in mouse_events:
        dt = abs(m['t'] - fixation_t)
        if dt < best_dt:
            best_dt = dt
            best = m
    if best_dt > 500:
        return None
    return best['x'], best['y'], best_dt


def compute_distance_trajectory(trial_id):
    """Returns list of (time_to_click_s, distance_px) for one trial."""
    meta = load_metadata(trial_id)
    fixations = load_fixations(trial_id)
    mouse_events, click_t = load_mouse_events(trial_id, meta)

    if click_t is None or len(fixations) < 5 or len(mouse_events) < 5:
        return None

    points = []
    for fix in fixations:
        ttc = click_t - fix['t']
        if ttc < 0:
            continue
        nearest = nearest_mouse_position(fix['t'], mouse_events)
        if nearest is None:
            continue
        mx, my, _ = nearest
        dist = math.sqrt((fix['x'] - mx) ** 2 + (fix['y'] - my) ** 2)
        points.append((ttc / 1000.0, dist))  # seconds

    return sorted(points, key=lambda p: -p[0])  # chronological: far-from-click first


def find_acquisition_onset(points, window=3):
    """Find when distance starts its sustained decline.

    Walk backward from click, find the first point where distance
    drops below 50% of the trial's baseline (mean of first half).
    Returns time-to-click in seconds at acquisition onset.
    """
    if len(points) < 6:
        return None

    # Baseline: mean distance in the first half of the trial
    half = len(points) // 2
    baseline_dists = [p[1] for p in points[:half]]
    if not baseline_dists:
        return None
    baseline = statistics.mean(baseline_dists)

    if baseline < 50:  # mouse was always near gaze — skip
        return None

    threshold = baseline * 0.5

    # Walk from click backward, find where distance first drops below threshold
    # Use a sliding window to avoid noise
    reversed_pts = list(reversed(points))
    for i in range(len(reversed_pts) - window):
        window_mean = statistics.mean(p[1] for p in reversed_pts[i:i+window])
        if window_mean > threshold:
            # The previous point was still below — that's the onset
            if i > 0:
                return reversed_pts[i-1][0]
            return reversed_pts[0][0]

    return None


def find_evaluation_onset(points, acquisition_onset_s):
    """Find when mouse starts drifting toward gaze (before full acquisition).

    Look for the point before acquisition where distance first drops below
    the scanning baseline — the mouse is leaking the decision.
    """
    if acquisition_onset_s is None or len(points) < 6:
        return None

    half = len(points) // 2
    baseline_dists = [p[1] for p in points[:half]]
    if not baseline_dists:
        return None
    baseline = statistics.mean(baseline_dists)
    baseline_std = statistics.stdev(baseline_dists) if len(baseline_dists) > 1 else 50

    # Walk forward from start, find first sustained drop below baseline - 1 SD
    drift_threshold = baseline - baseline_std

    for i in range(len(points) - 2):
        ttc = points[i][0]
        if ttc <= acquisition_onset_s:
            break
        # Check if next few points are below threshold
        window = points[i:i+3]
        if all(p[1] < drift_threshold for p in window):
            return ttc

    return None


def main():
    trial_ids = sorted([f.replace('.csv', '') for f in os.listdir(FIXATION_DIR) if f.endswith('.csv')])
    print(f"Processing {len(trial_ids)} trials...")

    acquisition_onsets = []
    evaluation_onsets = []
    eval_durations = []
    trial_durations = []
    phase_data = []

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(trial_ids)}...")
        try:
            points = compute_distance_trajectory(tid)
            if points is None or len(points) < 6:
                continue

            trial_dur = points[0][0]  # total trial duration in seconds
            if trial_dur < 3:  # need enough time for phases to emerge
                continue

            acq_onset = find_acquisition_onset(points)
            if acq_onset is None:
                continue

            eval_onset = find_evaluation_onset(points, acq_onset)

            acquisition_onsets.append(acq_onset)
            trial_durations.append(trial_dur)

            if eval_onset is not None:
                evaluation_onsets.append(eval_onset)
                eval_dur = eval_onset - acq_onset
                if eval_dur > 0:
                    eval_durations.append(eval_dur)

            phase_data.append({
                'trial': tid,
                'trial_duration_s': round(trial_dur, 2),
                'acquisition_onset_s': round(acq_onset, 2),
                'evaluation_onset_s': round(eval_onset, 2) if eval_onset else None,
                'evaluation_duration_s': round(eval_onset - acq_onset, 2) if eval_onset and eval_onset > acq_onset else None,
            })

        except Exception as e:
            pass

    # Report
    print(f"\n=== Phase Detection Results ===\n")
    print(f"Trials analyzed: {len(phase_data)}")
    print(f"Trials with acquisition onset: {len(acquisition_onsets)}")
    print(f"Trials with evaluation onset: {len(evaluation_onsets)}")

    if acquisition_onsets:
        print(f"\n--- Acquisition Phase (mouse converging on target) ---")
        print(f"  Onset (time before click): "
              f"mean={statistics.mean(acquisition_onsets):.1f}s, "
              f"median={statistics.median(acquisition_onsets):.1f}s, "
              f"SD={statistics.stdev(acquisition_onsets):.1f}s")

        # Distribution
        bins = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 30)]
        print(f"\n  Acquisition onset distribution (seconds before click):")
        for lo, hi in bins:
            n = sum(1 for x in acquisition_onsets if lo <= x < hi)
            pct = n / len(acquisition_onsets) * 100
            bar = '█' * int(pct / 2)
            print(f"    {lo}-{hi}s: {n:>5} ({pct:>5.1f}%) {bar}")

    if eval_durations:
        print(f"\n--- Evaluation Phase (gaze on target, mouse drifting) ---")
        print(f"  Duration: "
              f"mean={statistics.mean(eval_durations):.1f}s, "
              f"median={statistics.median(eval_durations):.1f}s, "
              f"SD={statistics.stdev(eval_durations):.1f}s")

        print(f"\n  Evaluation duration distribution:")
        bins = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 30)]
        for lo, hi in bins:
            n = sum(1 for x in eval_durations if lo <= x < hi)
            pct = n / len(eval_durations) * 100
            bar = '█' * int(pct / 2)
            print(f"    {lo}-{hi}s: {n:>5} ({pct:>5.1f}%) {bar}")

    # Per-participant variation
    by_participant = defaultdict(list)
    for pd_item in phase_data:
        pid = pd_item['trial'].split('-')[0]
        if pd_item['acquisition_onset_s'] is not None:
            by_participant[pid].append(pd_item['acquisition_onset_s'])

    if by_participant:
        print(f"\n--- Per-Participant Acquisition Onset (mean seconds before click) ---")
        participant_means = []
        for pid in sorted(by_participant.keys()):
            vals = by_participant[pid]
            if len(vals) >= 5:
                m = statistics.mean(vals)
                participant_means.append((pid, m, len(vals)))

        participant_means.sort(key=lambda x: x[1])
        print(f"  {'PID':<8} {'Mean':>8} {'N':>5}")
        for pid, m, n in participant_means:
            bar = '█' * int(m * 3)
            print(f"  {pid:<8} {m:>7.1f}s {n:>5}  {bar}")

        if len(participant_means) >= 2:
            all_means = [x[1] for x in participant_means]
            print(f"\n  Cross-participant: range={min(all_means):.1f}s - {max(all_means):.1f}s, "
                  f"SD={statistics.stdev(all_means):.1f}s")

    # Save
    out_path = os.path.join(os.path.dirname(__file__), 'phase_results.json')
    with open(out_path, 'w') as f:
        json.dump({
            'summary': {
                'trials_analyzed': len(phase_data),
                'acquisition_onset_mean_s': round(statistics.mean(acquisition_onsets), 2) if acquisition_onsets else None,
                'acquisition_onset_median_s': round(statistics.median(acquisition_onsets), 2) if acquisition_onsets else None,
                'evaluation_duration_mean_s': round(statistics.mean(eval_durations), 2) if eval_durations else None,
                'evaluation_duration_median_s': round(statistics.median(eval_durations), 2) if eval_durations else None,
            },
            'trials': phase_data,
        }, f, indent=2)
    print(f"\nFull results saved to {out_path}")


if __name__ == '__main__':
    main()
