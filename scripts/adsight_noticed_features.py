"""Per-AOI 'noticed' features for the AdSight noticed-classifier replication
(NB31 / CIKM 2026 path-1 experiment).

Emits one row per (trial, AOI) for every AOI in the typed_gapfill inventory —
including non-fixated AOIs. The existing
`cursor-approach-features-typed-gapfill.json` only contains fixated AOIs, so
its 'noticed' target collapses to 100 % positive class. This producer fixes
that by computing cursor-only per-AOI features unconditionally and binarising
the AdSight-style 'noticed' target as TFT > 0.

Schema per record:
  trial_id, position, etype, aoi_x, aoi_y, aoi_width, aoi_height,
  noticed (0/1 — TFT > 0 from any in-bbox fixation),
  total_dwell_ms (sum of in-bbox fixation durations; reported, not used as feature),
  n_fixations,
  min_dist_aoi, mean_dist_aoi, final_dist_aoi  (cursor distance to AOI center),
  dwell_in_proximity_ms (cursor time within 100 px of AOI center),
  trial_cursor_path_px, trial_duration_ms, n_aois_on_trial.

Run:
  /Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
    scripts/adsight_noticed_features.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events, get_trial_ids,
    is_main_axis_click,
)

AOI_DIR = ROOT / 'data' / 'aoi-typed-gapfill'
OUT_PATH = ROOT / 'AdSERP/data/adsight-noticed-features-typed-gapfill.json'

PROX_THRESHOLD = 100  # px — same as compute_cursor_approach_features


def _load_aois(trial_id: str):
    p = AOI_DIR / f'{trial_id}.json'
    if not p.exists():
        return None
    return json.load(open(p))


def _cursor_arrays(events):
    """Return (ts, xs, ys) for movement-class events with non-zero coords."""
    timeline = [
        (e[0], e[2], e[3]) for e in events
        if e[1] in ('mousemove', 'click', 'mouseover') and e[2] > 0
    ]
    if len(timeline) < 2:
        return None
    ts = np.array([m[0] for m in timeline], dtype=float)
    xs = np.array([m[1] for m in timeline], dtype=float)
    ys = np.array([m[2] for m in timeline], dtype=float)
    return ts, xs, ys


def _trial_cursor_path_px(xs, ys):
    if len(xs) < 2:
        return 0.0
    dx = np.diff(xs); dy = np.diff(ys)
    return float(np.sqrt(dx * dx + dy * dy).sum())


def _valid_aois(aois):
    """Filter null-coord AOIs (related_searches, pagination, off-axis dd_right
    when its bbox is missing) and zero-size rectangles. Returns list of
    (aoi_dict, x0, y0, x1, y1, area) tuples preserving original order."""
    out = []
    for aoi in aois:
        if aoi.get('x') is None or aoi.get('y') is None:
            continue
        ax = float(aoi['x'])
        ay = float(aoi['y'])
        aw = float(aoi.get('width') or 0.0)
        ah = float(aoi.get('height') or 0.0)
        if aw <= 0 or ah <= 0:
            continue
        out.append((aoi, ax, ay, ax + aw, ay + ah, aw * ah))
    return out


def _assign_fixation_innermost(fx: float, fy: float, valid_aois):
    """Per the rigor audit (2026-05-05): when overlapping AOIs contain a
    fixation, assign it to the smallest-area AOI ('innermost'). This
    de-duplicates fixation counting across nested or boundary-shared AOIs
    (typed_gapfill midpoint-split organics share a Y line; image_pack /
    knowledge_panel / paa often nest above organic positions). Returns
    index into valid_aois or -1."""
    best = -1
    best_area = float('inf')
    for i, (_a, x0, y0, x1, y1, area) in enumerate(valid_aois):
        if x0 <= fx <= x1 and y0 <= fy <= y1:
            if area < best_area:
                best_area = area
                best = i
    return best


def compute_records(trial_id: str):
    """Per-AOI noticed-classifier records for one trial (or None)."""
    aois = _load_aois(trial_id)
    if not aois:
        return None
    fixations = load_fixations(trial_id)
    mouse_data = load_mouse_events(trial_id)
    if not fixations or mouse_data is None:
        return None
    all_events, _scrolls, _clicks = mouse_data
    cur = _cursor_arrays(all_events)
    if cur is None:
        return None
    cur_ts, cur_xs, cur_ys = cur
    trial_path = _trial_cursor_path_px(cur_xs, cur_ys)
    trial_duration = float(cur_ts[-1] - cur_ts[0])

    valid = _valid_aois(aois)
    n_aois = len(valid)

    # Innermost-AOI fixation assignment (post-audit fix). Each fixation lights
    # up at most one AOI (the smallest containing rect). per-AOI counters:
    per_aoi_n = [0] * len(valid)
    per_aoi_tft = [0.0] * len(valid)
    for f in fixations:
        idx = _assign_fixation_innermost(f['x'], f['y'], valid)
        if idx < 0:
            continue
        per_aoi_n[idx] += 1
        per_aoi_tft[idx] += f.get('d', 200.0)

    records = []
    for aoi_idx, (aoi, ax, ay, ax_r, ay_r, _area) in enumerate(valid):
        aw = ax_r - ax
        ah = ay_r - ay
        etype = aoi.get('type', 'unknown')
        position = int(aoi.get('position', -1))
        cx = ax + aw / 2.0
        cy = ay + ah / 2.0

        # Target uses innermost-AOI-assigned counters (de-duplicated above)
        # so each fixation contributes to at most one AOI per trial.
        n_fix = per_aoi_n[aoi_idx]
        tft = per_aoi_tft[aoi_idx]
        noticed = int(n_fix > 0)

        # Cursor-only features: distance from cursor path to AOI center.
        dxs = cur_xs - cx
        dys = cur_ys - cy
        dists = np.sqrt(dxs * dxs + dys * dys)
        # Time-weighted dwell-in-proximity using inter-sample dt.
        if len(cur_ts) > 1:
            dt = np.diff(cur_ts)
            close_mid = (dists[:-1] < PROX_THRESHOLD) & (dists[1:] < PROX_THRESHOLD)
            dwell_prox = float(dt[close_mid].sum())
        else:
            dwell_prox = 0.0

        records.append({
            'trial_id': trial_id,
            'position': position,
            'etype': etype,
            'aoi_x': ax, 'aoi_y': ay,
            'aoi_width': aw, 'aoi_height': ah,
            'noticed': noticed,
            'n_fixations': n_fix,
            'total_dwell_ms': tft,
            'min_dist_aoi': float(dists.min()),
            'mean_dist_aoi': float(dists.mean()),
            'final_dist_aoi': float(dists[-1]),
            'dwell_in_proximity_ms': dwell_prox,
            'trial_cursor_path_px': trial_path,
            'trial_duration_ms': trial_duration,
            'n_aois_on_trial': n_aois,
        })
    return records


def main():
    trial_ids = get_trial_ids()
    print(f'[load] {len(trial_ids):,} trial ids', file=sys.stderr)
    out = []
    skipped_main_axis = 0
    skipped_other = 0
    for i, tid in enumerate(trial_ids):
        # Mirror the typed_gapfill cascade rule: drop hard-error trials whose
        # final click is not on a main-axis AOI under typed_gapfill (158
        # trials by audit_cascade_contamination.py).
        try:
            if not is_main_axis_click(tid):
                skipped_main_axis += 1
                continue
        except Exception:
            skipped_main_axis += 1
            continue
        recs = compute_records(tid)
        if not recs:
            skipped_other += 1
            continue
        out.extend(recs)
        if (i + 1) % 200 == 0:
            print(f'  {i+1}/{len(trial_ids)}  rows={len(out):,}', file=sys.stderr)

    print(f'\n[summary] {len(out):,} rows from '
          f'{len({r["trial_id"] for r in out}):,} trials  '
          f'(skipped main_axis={skipped_main_axis}, other={skipped_other})',
          file=sys.stderr)

    from collections import Counter
    by_etype = Counter(r['etype'] for r in out)
    pos_by_etype = Counter(r['etype'] for r in out if r['noticed'])
    print('  per-etype noticed rates:', file=sys.stderr)
    for e, n in by_etype.most_common():
        p = pos_by_etype[e]
        print(f'    {e:>20s}  n={n:6d}  noticed={p:6d}  rate={100*p/n:.1f}%',
              file=sys.stderr)

    OUT_PATH.write_text(json.dumps(out, separators=(',', ':')))
    print(f'\n[out] {OUT_PATH.relative_to(ROOT)}  '
          f'({OUT_PATH.stat().st_size/1e6:.1f} MB)', file=sys.stderr)


if __name__ == '__main__':
    main()
