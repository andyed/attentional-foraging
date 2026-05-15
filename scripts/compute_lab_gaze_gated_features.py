"""STUB-D: LAB gaze-gated diagnostic-upper-bound feature extractor.

Replaces the canonical mousemove-stream cursor sampler with a fixation-
timed cursor interpolation: for each fixation in a trial, interpolate
the cursor's (x, y) at the fixation's timestamp. Use those as the
cursor stream that M4 features are computed against. The result is the
"LAB gaze-gated" variant referenced in paper-v3 Appendix A — a
diagnostic upper bound that requires an eye tracker at feature-
extraction time and is therefore not deployable in production.

Differences from compute_cursor_approach_features.py:
  - Cursor stream is fixation-timed interpolations, not raw mousemoves
  - Otherwise identical: organic AOIs (or absolute, by flag), nine M4
    features, same per-(trial, position) record schema

Run:
  .venv/bin/python scripts/compute_lab_gaze_gated_features.py --attribution organic
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    DATA_DIR,
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    get_trial_meta,
    assign_fixation_to_position,
    result_band_tops,
    extract_serp_results,
    organic_aoi_tops,
    click_to_position,
    gaze_cursor_distance,
)


PROX_THRESHOLD = 100  # px


def gaze_gated_cursor_stream(fixations, mouse_events):
    """Return (ts, xs, ys) arrays — cursor (x, y) interpolated at each
    fixation's start timestamp. Replaces the full mousemove stream with
    a sparser, fixation-timed sample."""
    if not fixations or not mouse_events:
        return None

    mouse_timeline = [
        (e[0], e[2], e[3])
        for e in mouse_events
        if e[1] in ('mousemove', 'click', 'mouseover') and e[2] > 0
    ]
    if len(mouse_timeline) < 2:
        return None

    m_ts = np.array([m[0] for m in mouse_timeline], dtype=np.int64)
    m_xs = np.array([m[1] for m in mouse_timeline], dtype=float)
    m_ys = np.array([m[2] for m in mouse_timeline], dtype=float)

    fix_ts = np.array([int(f['t']) for f in fixations], dtype=np.int64)
    interp_xs = np.empty(len(fix_ts), dtype=float)
    interp_ys = np.empty(len(fix_ts), dtype=float)
    for i, t in enumerate(fix_ts):
        idx = int(np.searchsorted(m_ts, t))
        if idx == 0:
            interp_xs[i] = m_xs[0]; interp_ys[i] = m_ys[0]
        elif idx >= len(m_ts):
            interp_xs[i] = m_xs[-1]; interp_ys[i] = m_ys[-1]
        else:
            t0, t1 = m_ts[idx - 1], m_ts[idx]
            frac = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            interp_xs[i] = m_xs[idx - 1] + frac * (m_xs[idx] - m_xs[idx - 1])
            interp_ys[i] = m_ys[idx - 1] + frac * (m_ys[idx] - m_ys[idx - 1])
    return fix_ts, interp_xs, interp_ys


def compute_features(trial_id, attribution='organic', click_buffer_ms=0):
    fixations = load_fixations(trial_id)
    mouse_data = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if fixations is None or mouse_data is None or meta is None:
        return None
    all_events, scrolls, clicks = mouse_data
    doc_h, scr_h, _ = meta
    if not fixations or not all_events or not doc_h:
        return None

    if attribution == 'organic':
        tops = organic_aoi_tops(trial_id)
        n_results = len(tops)
        if n_results == 0:
            return None
    else:
        serp = extract_serp_results(trial_id)
        n_results = len(serp) if serp else 10
        tops = result_band_tops(n_results, doc_h)

    click_pos = click_to_position(clicks, tops, n_results)

    # Click-buffer truncation: clip both fixations and the underlying
    # mousemove stream at click_t − Δ, mirroring the protocol in
    # compute_cursor_approach_features.py. Click attribution above
    # uses the raw click record; only the inputs to fixation-timed
    # cursor sampling are truncated.
    if click_buffer_ms > 0 and clicks:
        click_t = float(clicks[-1][0])
        cutoff = click_t - float(click_buffer_ms)
        fixations = [f for f in fixations if f['t'] < cutoff]
        all_events = [e for e in all_events if e[0] < cutoff]
        if not fixations or not all_events:
            return None

    sampled = gaze_gated_cursor_stream(fixations, all_events)
    if sampled is None:
        return None
    cur_ts, cur_xs, cur_ys = sampled

    # Group fixations by organic position
    fix_by_pos = defaultdict(list)
    for fi, fix in enumerate(fixations):
        page_y = fix['y']
        pos = assign_fixation_to_position(page_y, tops, n_results)
        if pos is None or pos < 0 or pos >= n_results:
            continue
        fix_by_pos[pos].append((fi, fix))

    # Per-position result center (band midpoint)
    centers = {}
    for p in range(n_results):
        if p < len(tops) - 1:
            cy = (tops[p] + tops[p + 1]) / 2
        elif len(tops) > 1:
            cy = tops[p] + (tops[1] - tops[0]) / 2
        else:
            cy = tops[p] + 100
        centers[p] = cy

    records = []
    for pos, items in fix_by_pos.items():
        if not items:
            continue
        was_clicked = (click_pos == pos)
        n_fix = len(items)
        total_dwell_ms = sum(f.get('d', 200) for _, f in items)
        result_cy = centers[pos]

        distances = []
        cursor_velocities = []
        dwell_in_proximity = 0

        for fi, fix in items:
            # gaze-gated cursor position at fixation index fi
            mx, my = float(cur_xs[fi]), float(cur_ys[fi])
            dist = gaze_cursor_distance(fix['x'], fix['y'], mx, my)
            distances.append(dist)
            cursor_to_result = abs(my - result_cy)
            if cursor_to_result < PROX_THRESHOLD:
                dwell_in_proximity += fix.get('d', 200)

            # velocity: change in (cursor distance to result center) per ms
            if fi > 0 and fi < len(cur_ts):
                t = cur_ts[fi]
                vel_window = 200
                # Local approximation: use neighboring fixations within window
                idx_before = max(0, fi - 1)
                idx_after = min(len(cur_ts) - 1, fi + 1)
                t0, t1 = int(cur_ts[idx_before]), int(cur_ts[idx_after])
                y0 = float(cur_ys[idx_before])
                y1 = float(cur_ys[idx_after])
                dist_before = abs(y0 - result_cy)
                dist_after = abs(y1 - result_cy)
                dt_s = max((t1 - t0) / 1000.0, 0.001)
                velocity = (dist_before - dist_after) / dt_s
                cursor_velocities.append(velocity)

        if not distances:
            continue
        distances = np.array(distances)
        min_dist = float(np.min(distances))
        mean_dist = float(np.mean(distances))
        final_dist = float(distances[-1])
        min_idx = int(np.argmin(distances))
        retreat_dist = float(distances[-1] - distances[min_idx]) if len(distances) > 1 else 0.0

        if cursor_velocities:
            mean_vel = float(np.mean(cursor_velocities))
            max_vel = float(np.max(cursor_velocities))
            if len(cursor_velocities) > 1:
                signs = np.sign(cursor_velocities)
                direction_changes = int(np.sum(np.abs(np.diff(signs)) > 0))
            else:
                direction_changes = 0
        else:
            mean_vel = 0.0
            max_vel = 0.0
            direction_changes = 0

        if len(distances) >= 3:
            diffs = np.diff(distances)
            frac_decreasing = float(np.mean(diffs < 0))
        else:
            frac_decreasing = 0.5

        records.append({
            'trial_id': trial_id,
            'position': int(pos),
            'was_clicked': bool(was_clicked),
            'n_fixations': int(n_fix),
            'total_dwell_ms': float(total_dwell_ms),
            'min_dist': min_dist, 'mean_dist': mean_dist, 'final_dist': final_dist,
            'retreat_dist': retreat_dist,
            'dwell_in_proximity_ms': float(dwell_in_proximity),
            'mean_approach_velocity': mean_vel,
            'max_approach_velocity': max_vel,
            'direction_changes': direction_changes,
            'frac_decreasing': frac_decreasing,
        })
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--attribution', choices=['absolute', 'organic'], default='organic')
    ap.add_argument('--click-buffer-ms', type=int, default=0,
                    help='Truncate fixations + mouse events at click_t − Δ ms before '
                         'gaze-gated sampling. Default 0 (no truncation).')
    ap.add_argument('--output', '-o',
                    help='Output JSON path (default depends on attribution)')
    args = ap.parse_args()

    if args.output:
        out_path = Path(args.output)
    else:
        attr_suffix = '-organic' if args.attribution == 'organic' else ''
        buf_suffix = f'-buf{args.click_buffer_ms}' if args.click_buffer_ms > 0 else ''
        out_path = DATA_DIR / f'cursor-approach-features-lab-gaze-gated{attr_suffix}{buf_suffix}.json'

    trial_ids = get_trial_ids()
    all_records = []
    n_ok = n_fail = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}...', file=sys.stderr)
        try:
            recs = compute_features(tid, attribution=args.attribution,
                                     click_buffer_ms=args.click_buffer_ms)
            if recs:
                all_records.extend(recs)
                n_ok += 1
            else:
                n_fail += 1
        except Exception as e:
            n_fail += 1

    print(f'\n{args.attribution} (LAB gaze-gated): {n_ok} trials, {n_fail} skipped',
          file=sys.stderr)
    print(f'Total records: {len(all_records):,}', file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(all_records, f)
    print(f'Wrote {out_path}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
