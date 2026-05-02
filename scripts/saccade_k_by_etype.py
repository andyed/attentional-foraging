"""Test: do dd_top carousel positions show more horizontal saccades and more
ambient K-coefficient than organic positions?

Andy's hypothesis: the position-0 horizontal-saccade and ambient-K signals
that look unusual under absolute attribution may be the user tracking grid
contents in the top multi-panel carousel ad (dd_top), not reading the first
organic.

Method:
  1. Build hybrid AOI list per trial (organic + dd_top + native_ad in display
     order; same as compute_cursor_approach_features.py organic_hybrid mode)
  2. Walk fixations, classify each saccade (h / v / o), tag by etype of the
     ORIGIN fixation's hybrid position
  3. Compute per-fixation K = z(FD) - z(SA) using participant-level z-scores,
     tag by etype
  4. Aggregate by etype + by (etype, position)

Run:
  .venv/bin/python scripts/saccade_k_by_etype.py
"""
from __future__ import annotations

import json
import math
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
    organic_aoi_bands,
    assign_fixation_to_position,
)

AD_DIR = DATA_DIR / 'ad-boundary-data'
RESULT_COL_X_MIN = 50
RESULT_COL_X_MAX = 750

HORIZ_DEG = 30.0
VERT_DEG = 60.0
MIN_MAGNITUDE_PX = 10.0
HORIZ_RAD = math.radians(HORIZ_DEG)
VERT_RAD = math.radians(VERT_DEG)


def _load_ad_regions(trial_id):
    path = AD_DIR / f'{trial_id}.json'
    if not path.exists():
        return {}
    d = json.load(open(path))
    out = {}
    for etype, elements in d.items():
        rects = []
        for el in elements:
            loc = el.get('location', {})
            size = el.get('size', {})
            rects.append((loc.get('x', 0), loc.get('y', 0),
                          size.get('width', 0), size.get('height', 0)))
        if rects:
            out[etype] = rects
    return out


def build_hybrid_aois(trial_id):
    """Same logic as compute_cursor_approach_features.build_hybrid_aois."""
    bands = organic_aoi_bands(trial_id) or []
    items = [(t, b, 'organic') for t, b in bands]
    ad_regions = _load_ad_regions(trial_id)
    for etype, rects in ad_regions.items():
        if etype == 'dd_right':
            continue
        for rx, ry, rw, rh in rects:
            if not (rx < RESULT_COL_X_MAX and (rx + rw) > RESULT_COL_X_MIN):
                continue
            items.append((ry, ry + rh, etype))
    if not items:
        return [], [], []
    items.sort(key=lambda r: r[0])
    return ([r[0] for r in items],
            [r[1] for r in items],
            [r[2] for r in items])


def classify_saccade(dx, dy):
    mag = math.hypot(dx, dy)
    if mag < MIN_MAGNITUDE_PX:
        return None
    theta = math.atan2(abs(dy), abs(dx))
    if theta <= HORIZ_RAD:
        return 'h'
    if theta >= VERT_RAD:
        return 'v'
    return 'o'


def main():
    print('[walk] passes 1+2: per-participant z-score params + per-fixation K')

    # Pass 1: collect FD/SA per participant
    pid_fd = defaultdict(list)
    pid_sa = defaultdict(list)
    trial_buf = []  # (tid, fixations, hybrid_aois)
    n_skipped = 0

    trial_ids = get_trial_ids()
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        fixations = load_fixations(tid)
        if not fixations or len(fixations) < 2:
            n_skipped += 1
            continue
        tops, bottoms, etypes = build_hybrid_aois(tid)
        if not tops:
            n_skipped += 1
            continue
        n_results = len(tops)

        pid = tid.split('-')[0]
        for idx, f in enumerate(fixations):
            fd = float(f['d'])
            if idx + 1 < len(fixations):
                nxt = fixations[idx + 1]
                sa = math.hypot(nxt['x'] - f['x'], nxt['y'] - f['y'])
                pid_sa[pid].append(sa)
            pid_fd[pid].append(fd)
        trial_buf.append((tid, fixations, (tops, etypes, n_results)))

    pid_params = {}
    for pid in pid_fd:
        if len(pid_fd[pid]) < 30 or len(pid_sa[pid]) < 30:
            continue
        pid_params[pid] = {
            'mu_fd': float(np.mean(pid_fd[pid])),
            'sd_fd': float(np.std(pid_fd[pid], ddof=1)),
            'mu_sa': float(np.mean(pid_sa[pid])),
            'sd_sa': float(np.std(pid_sa[pid], ddof=1)),
        }

    print(f'  trials kept: {len(trial_buf):,} ({n_skipped} skipped)')
    print(f'  participants with z-params: {len(pid_params)}')

    # Pass 2: tag each saccade + each fixation's K by hybrid etype
    sacc_by_etype = defaultdict(lambda: defaultdict(int))  # etype -> {h,v,o,total}
    k_by_etype = defaultdict(list)  # etype -> [K values]
    sacc_by_etype_pos = defaultdict(lambda: defaultdict(int))  # (etype, pos) -> ...
    k_by_etype_pos = defaultdict(list)  # (etype, pos) -> [K values]

    for tid, fixations, (tops, etypes, n_results) in trial_buf:
        pid = tid.split('-')[0]
        params = pid_params.get(pid)
        for idx, f in enumerate(fixations):
            pos = assign_fixation_to_position(f['y'], tops, n_results)
            if pos is None or pos < 0 or pos >= n_results:
                continue
            etype = etypes[pos]
            # Saccade originating from this fixation
            if idx + 1 < len(fixations):
                nxt = fixations[idx + 1]
                cls = classify_saccade(nxt['x'] - f['x'], nxt['y'] - f['y'])
                if cls is not None:
                    sacc_by_etype[etype][cls] += 1
                    sacc_by_etype[etype]['total'] += 1
                    sacc_by_etype_pos[(etype, int(pos))][cls] += 1
                    sacc_by_etype_pos[(etype, int(pos))]['total'] += 1
            # Per-fixation K
            if params is not None and idx + 1 < len(fixations):
                fd = float(f['d'])
                sa = math.hypot(fixations[idx + 1]['x'] - f['x'],
                                fixations[idx + 1]['y'] - f['y'])
                z_fd = (fd - params['mu_fd']) / max(params['sd_fd'], 1e-9)
                z_sa = (sa - params['mu_sa']) / max(params['sd_sa'], 1e-9)
                k = z_fd - z_sa
                k_by_etype[etype].append(k)
                k_by_etype_pos[(etype, int(pos))].append(k)

    # Aggregate
    print('\n=== Saccade orientation by etype ===')
    print(f'{"etype":12s} {"n_sacc":>8s} {"%horiz":>7s} {"%vert":>7s} {"%oblique":>9s} {"mean K":>8s} {"median K":>9s} {"K interp":>10s}')
    for etype in ['organic', 'dd_top', 'native_ad']:
        c = sacc_by_etype[etype]
        n = c['total']
        if n == 0:
            continue
        ks = k_by_etype[etype]
        mean_k = np.mean(ks) if ks else float('nan')
        med_k = np.median(ks) if ks else float('nan')
        interp = 'ambient' if med_k < 0 else 'focal'
        print(f'{etype:12s} {n:>8,} '
              f'{100 * c.get("h", 0) / n:>6.1f}% '
              f'{100 * c.get("v", 0) / n:>6.1f}% '
              f'{100 * c.get("o", 0) / n:>8.1f}% '
              f'{mean_k:>+8.3f} {med_k:>+9.3f} {interp:>10s}')

    # Per-(etype, position) — mostly interesting for low positions
    print('\n=== Saccade orientation by (etype, position) — low ranks ===')
    print(f'{"etype":12s} {"pos":>3s} {"n_sacc":>7s} {"%horiz":>7s} {"%vert":>7s} {"mean K":>8s} {"median K":>9s}')
    rows = []
    for (etype, pos), c in sacc_by_etype_pos.items():
        if c['total'] < 50:
            continue
        if pos > 5:
            continue
        ks = k_by_etype_pos.get((etype, pos), [])
        rows.append((etype, pos, c, ks))
    rows.sort(key=lambda r: (r[0], r[1]))
    for etype, pos, c, ks in rows:
        n = c['total']
        mean_k = np.mean(ks) if ks else float('nan')
        med_k = np.median(ks) if ks else float('nan')
        print(f'{etype:12s} {pos:>3d} {n:>7,} '
              f'{100 * c.get("h", 0) / n:>6.1f}% '
              f'{100 * c.get("v", 0) / n:>6.1f}% '
              f'{mean_k:>+8.3f} {med_k:>+9.3f}')

    # Save
    out_dir = ROOT / 'scripts/output/aoi-consumer-cascade'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'saccade_k_by_etype.json'
    out = {
        'by_etype': {
            etype: {
                'n_sacc': sacc_by_etype[etype].get('total', 0),
                'pct_horiz': 100 * sacc_by_etype[etype].get('h', 0) / max(sacc_by_etype[etype].get('total', 0), 1),
                'pct_vert': 100 * sacc_by_etype[etype].get('v', 0) / max(sacc_by_etype[etype].get('total', 0), 1),
                'pct_oblique': 100 * sacc_by_etype[etype].get('o', 0) / max(sacc_by_etype[etype].get('total', 0), 1),
                'mean_k': float(np.mean(k_by_etype[etype])) if k_by_etype[etype] else None,
                'median_k': float(np.median(k_by_etype[etype])) if k_by_etype[etype] else None,
                'n_fixations_with_k': len(k_by_etype[etype]),
            }
            for etype in sacc_by_etype
        },
        'by_etype_pos': {
            f'{etype}/{pos}': {
                'n_sacc': c.get('total', 0),
                'pct_horiz': 100 * c.get('h', 0) / max(c.get('total', 0), 1),
                'pct_vert': 100 * c.get('v', 0) / max(c.get('total', 0), 1),
                'mean_k': float(np.mean(ks)) if ks else None,
                'median_k': float(np.median(ks)) if ks else None,
            }
            for (etype, pos), c in sacc_by_etype_pos.items()
            if (ks := k_by_etype_pos.get((etype, pos), []))
        },
    }
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
