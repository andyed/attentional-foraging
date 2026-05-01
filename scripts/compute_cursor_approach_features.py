"""Compute per-result cursor approach features for every trial.

Extracts the `compute_approach_features` function from NB15 into a
standalone producer with `--attribution {absolute, organic}`. The
absolute mode reproduces the file currently shipped at
`AdSERP/data/cursor-approach-features.json` (legacy band estimation
on h3 count). The organic mode writes a sibling file
`cursor-approach-features-organic.json` using bbox-derived AOIs.

Output schema (per record):
  trial_id, position, was_clicked, n_fixations, total_dwell_ms,
  click_pos, entry_t, exit_t,
  min_dist, mean_dist, final_dist, retreat_dist,
  dwell_in_proximity_ms, mean_approach_velocity, max_approach_velocity,
  direction_changes, frac_decreasing

Run:
    .venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic
    .venv/bin/python scripts/compute_cursor_approach_features.py --attribution absolute  # regenerate legacy
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    DATA_DIR,
    get_trial_ids,
    load_fixations,
    load_mouse_events,
    get_trial_meta,
    interpolate_scroll,
    assign_fixation_to_position,
    result_band_tops,
    extract_serp_results,
    click_to_position,
    gaze_cursor_distance,
    organic_aoi_tops,
)


def compute_approach_features(trial_id, attribution="absolute"):
    """Compute per-result cursor approach features for a trial.

    attribution: 'absolute' uses count_results_html + result_band_tops;
                 'organic'  uses load_aois -> organic_aoi_tops.
    """
    fixations = load_fixations(trial_id)
    mouse_data = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if fixations is None or mouse_data is None or meta is None:
        return None

    all_events, scrolls, clicks = mouse_data
    doc_h, scr_h, _ = meta
    if not fixations or not all_events or not doc_h:
        return None

    if attribution == "organic":
        tops = organic_aoi_tops(trial_id)
        n_results = len(tops)
        if n_results == 0:
            return None
    else:
        serp = extract_serp_results(trial_id)
        n_results = len(serp) if serp else 10
        tops = result_band_tops(n_results, doc_h)

    scroll_ts = [s[0] for s in scrolls] if scrolls else [fixations[0]["t"]]
    scroll_ys = [s[1] for s in scrolls] if scrolls else [0]

    mouse_timeline = [
        (e[0], e[2], e[3])
        for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(mouse_timeline) < 2:
        return None

    mouse_ts = np.array([m[0] for m in mouse_timeline])
    mouse_xs = np.array([m[1] for m in mouse_timeline], dtype=float)
    mouse_ys = np.array([m[2] for m in mouse_timeline], dtype=float)

    click_pos = click_to_position(clicks, tops, n_results)

    fix_by_pos = defaultdict(list)
    for fix in fixations:
        page_y = fix["y"]  # FPOGY is page-space (2026-04-12 audit)
        pos = assign_fixation_to_position(page_y, tops, n_results)
        if pos is None or pos < 0 or pos >= n_results:
            continue
        fix_by_pos[pos].append(fix)

    result_centers = {}
    for pos in range(n_results):
        if pos < len(tops) - 1:
            center_y = (tops[pos] + tops[pos + 1]) / 2
        elif len(tops) > 1:
            center_y = tops[pos] + (tops[1] - tops[0]) / 2
        else:
            center_y = tops[pos] + 100
        result_centers[pos] = center_y

    records = []
    PROX_THRESHOLD = 100  # px

    for pos, pos_fixations in fix_by_pos.items():
        if not pos_fixations:
            continue
        was_clicked = (click_pos == pos)
        n_fixations = len(pos_fixations)
        total_dwell_ms = sum(f.get("d", 200) for f in pos_fixations)

        result_center_y = result_centers[pos]
        distances = []
        cursor_velocities = []
        dwell_in_proximity = 0

        for fix in pos_fixations:
            t = fix["t"]
            idx = np.searchsorted(mouse_ts, t)
            if idx == 0:
                mx, my = mouse_xs[0], mouse_ys[0]
            elif idx >= len(mouse_ts):
                mx, my = mouse_xs[-1], mouse_ys[-1]
            else:
                t0, t1 = mouse_ts[idx - 1], mouse_ts[idx]
                frac = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                mx = mouse_xs[idx - 1] + frac * (mouse_xs[idx] - mouse_xs[idx - 1])
                my = mouse_ys[idx - 1] + frac * (mouse_ys[idx] - mouse_ys[idx - 1])

            dist = gaze_cursor_distance(fix["x"], fix["y"], mx, my)
            distances.append(dist)

            cursor_to_result = abs(my - result_center_y)
            if cursor_to_result < PROX_THRESHOLD:
                dwell_in_proximity += fix.get("d", 200)

            vel_window = 200
            mask_before = (mouse_ts >= t - vel_window) & (mouse_ts < t)
            mask_after = (mouse_ts > t) & (mouse_ts <= t + vel_window)
            if mask_before.any() and mask_after.any():
                y_before = np.mean(mouse_ys[mask_before])
                y_after = np.mean(mouse_ys[mask_after])
                dist_before = abs(y_before - result_center_y)
                dist_after = abs(y_after - result_center_y)
                velocity = (dist_before - dist_after) / (vel_window * 2 / 1000)
                cursor_velocities.append(velocity)

        distances = np.array(distances)
        min_dist = float(np.min(distances))
        mean_dist = float(np.mean(distances))
        final_dist = float(distances[-1]) if len(distances) > 0 else float("inf")
        min_dist_idx = int(np.argmin(distances))
        retreat_dist = float(distances[-1] - distances[min_dist_idx]) if len(distances) > 1 else 0

        if cursor_velocities:
            mean_velocity = float(np.mean(cursor_velocities))
            max_approach_velocity = float(np.max(cursor_velocities))
            if len(cursor_velocities) > 1:
                signs = np.sign(cursor_velocities)
                direction_changes = int(np.sum(np.abs(np.diff(signs)) > 0))
            else:
                direction_changes = 0
        else:
            mean_velocity = 0.0
            max_approach_velocity = 0.0
            direction_changes = 0

        if len(distances) >= 3:
            diffs = np.diff(distances)
            frac_decreasing = float(np.mean(diffs < 0))
        else:
            frac_decreasing = 0.5

        entry_t = int(pos_fixations[0]["t"])
        exit_t = int(pos_fixations[-1]["t"])

        records.append({
            "trial_id": trial_id,
            "position": pos,
            "was_clicked": bool(was_clicked),
            "n_fixations": int(n_fixations),
            "total_dwell_ms": float(total_dwell_ms),
            "click_pos": click_pos if click_pos is not None else -1,
            "entry_t": entry_t, "exit_t": exit_t,
            "min_dist": min_dist, "mean_dist": mean_dist, "final_dist": final_dist,
            "retreat_dist": retreat_dist,
            "dwell_in_proximity_ms": float(dwell_in_proximity),
            "mean_approach_velocity": mean_velocity,
            "max_approach_velocity": max_approach_velocity,
            "direction_changes": direction_changes,
            "frac_decreasing": frac_decreasing,
        })

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attribution", choices=["absolute", "organic"], default="organic")
    parser.add_argument("--output", "-o", help="Output JSON path (default depends on attribution)")
    parser.add_argument("--trial", help="Single trial only (for testing)")
    args = parser.parse_args()

    if args.output:
        out_path = Path(args.output)
    else:
        if args.attribution == "organic":
            out_path = DATA_DIR / "cursor-approach-features-organic.json"
        else:
            out_path = DATA_DIR / "cursor-approach-features.json"

    if args.trial:
        recs = compute_approach_features(args.trial, attribution=args.attribution)
        if recs is None:
            print(f"{args.trial}: unusable", file=sys.stderr)
            return 1
        json.dump(recs, sys.stdout, indent=2)
        return 0

    trial_ids = get_trial_ids()
    all_records = []
    n_ok = n_fail = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(trial_ids)}...", file=sys.stderr)
        try:
            recs = compute_approach_features(tid, attribution=args.attribution)
            if recs:
                all_records.extend(recs)
                n_ok += 1
            else:
                n_fail += 1
        except Exception as e:
            n_fail += 1
            print(f"  SKIP {tid}: {e}", file=sys.stderr)

    print(f"\n{args.attribution}: {n_ok} trials processed, {n_fail} skipped", file=sys.stderr)
    print(f"Total records: {len(all_records):,}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_records, f)
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
