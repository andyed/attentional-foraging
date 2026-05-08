"""Cursor saccade-orientation features — analog of compute_saccade_orientation
for cursor (mouse) movement instead of gaze fixations.

Cursor data is continuous (every mousemove event), so we don't have natural
fixation boundaries. We define cursor "saccades" as displacement vectors
between consecutive mousemove events with magnitude ≥ MIN_MAGNITUDE_PX,
matching the gaze pipeline's classification (horizontal/vertical/oblique).

The motivation: literature (Navalpakkam & Churchill CHI 2012, Huang/White/
Buscher CHI 2012) shows ~25-40% of users have tightly coupled gaze-cursor
trajectories on SERPs. For that subset, cursor saccade-orientation should
mimic gaze saccade-orientation — including the reading-shape signature at
clicked positions.

Outputs:
  AdSERP/data/cursor-saccade-orientation-by-position.json
  AdSERP/data/cursor-saccade-orientation-by-trial.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))

from adserp_loader import (  # type: ignore # noqa: E402
    get_trial_ids, load_mouse_events,
    get_trial_meta, result_band_tops, count_results_html,
    assign_fixation_to_position,
)

OUT_BY_POS = ROOT / 'AdSERP/data/cursor-saccade-orientation-by-position.json'
OUT_BY_TRIAL = ROOT / 'AdSERP/data/cursor-saccade-orientation-by-trial.json'

# Same thresholds as gaze pipeline for parallel comparison
HORIZ_DEG = 30.0
VERT_DEG = 60.0
MIN_MAGNITUDE_PX = 10.0
HORIZ_RAD = math.radians(HORIZ_DEG)
VERT_RAD = math.radians(VERT_DEG)


def classify(dx: float, dy: float) -> str | None:
    mag = math.hypot(dx, dy)
    if mag < MIN_MAGNITUDE_PX:
        return None
    theta = math.atan2(abs(dy), abs(dx))
    if theta <= HORIZ_RAD:
        return 'h'
    if theta >= VERT_RAD:
        return 'v'
    return 'o'


def max_run(seq: list[str], target: str) -> int:
    best = cur = 0
    for c in seq:
        if c == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def features_from_classes(classes: list[str]) -> dict:
    n = len(classes)
    n_h = classes.count('h')
    n_v = classes.count('v')
    n_o = classes.count('o')
    return {
        'n_saccades': n,
        'n_horizontal': n_h,
        'n_vertical': n_v,
        'n_oblique': n_o,
        'frac_horizontal': n_h / n if n else 0.0,
        'ratio_h_to_v': n_h / n_v if n_v else (float('inf') if n_h else 0.0),
        'max_horizontal_run': max_run(classes, 'h'),
    }


def main() -> None:
    trial_ids = get_trial_ids()
    print(f'[walk] {len(trial_ids):,} trials', file=sys.stderr)

    by_pos: dict[str, dict] = {}
    by_trial: dict[str, dict] = {}
    n_skipped_no_events = 0

    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        events, scrolls, clicks = load_mouse_events(tid)
        if not events or len(events) < 2:
            n_skipped_no_events += 1
            continue

        # Filter to mousemove events (the actual cursor-trail signal)
        moves = [(t, x, y) for (t, et, x, y) in events if et == 'mousemove']
        if len(moves) < 2:
            n_skipped_no_events += 1
            continue

        n_results = count_results_html(tid) or 11
        doc_h, _, _ = get_trial_meta(tid)
        if doc_h is None:
            tops = None
        else:
            tops = result_band_tops(n_results, doc_h)

        trial_classes: list[str] = []
        per_pos_classes: dict[int, list[str]] = defaultdict(list)
        for (t1, x1, y1), (t2, x2, y2) in zip(moves[:-1], moves[1:]):
            cls = classify(x2 - x1, y2 - y1)
            if cls is None:
                continue
            trial_classes.append(cls)
            if tops is not None:
                p = assign_fixation_to_position(y1, tops, n_results)
                if p is not None and 0 <= p < n_results:
                    per_pos_classes[int(p)].append(cls)

        by_trial[tid] = features_from_classes(trial_classes)
        by_trial[tid]['pid'] = tid.split('-')[0]
        positions = []
        for p, cls in per_pos_classes.items():
            entry = features_from_classes(cls)
            entry['pos'] = p
            positions.append(entry)
        positions.sort(key=lambda r: r['pos'])
        by_pos[tid] = {'positions': positions}

    print(f'  trials with cursor features: {len(by_trial):,}  '
          f'(skipped {n_skipped_no_events} no-events)', file=sys.stderr)

    OUT_BY_TRIAL.write_text(json.dumps(by_trial, indent=2))
    OUT_BY_POS.write_text(json.dumps(by_pos, indent=2))
    print(f'[out] {OUT_BY_TRIAL.relative_to(ROOT)}  '
          f'{OUT_BY_POS.relative_to(ROOT)}', file=sys.stderr)

    # Summary
    n_h = sum(t['n_horizontal'] for t in by_trial.values())
    n_v = sum(t['n_vertical'] for t in by_trial.values())
    n_o = sum(t['n_oblique'] for t in by_trial.values())
    n_sac = n_h + n_v + n_o
    print('\n=== Global cursor saccade-orientation distribution ===')
    print(f'  n trials = {len(by_trial):,};  n cursor saccades = {n_sac:,}')
    if n_sac:
        print(f'  horizontal = {n_h:,} ({100*n_h/n_sac:.1f}%)')
        print(f'  vertical   = {n_v:,} ({100*n_v/n_sac:.1f}%)')
        print(f'  oblique    = {n_o:,} ({100*n_o/n_sac:.1f}%)')


if __name__ == '__main__':
    main()
