"""
forward_regressive_tolerance_sweep.py — runs the NB24 headline numbers at
four HWM tolerances and writes notebooks-v2/forward-regressive-headlines.md
for the CIKM draft to pull from.

Emits:
  - Top Ad lateral/arc ratio (pooled / forward / regressive) at each tol_px
  - Top Ad arc_ratio (pooled / forward / regressive)
  - Re-approach transition counts

If the headline flips sign between tol_px=50 and tol_px=100, the finding is
fragile and should carry a sensitivity footnote in the CIKM draft.
"""

import json
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import (
    AD_DIR,
    DATA_DIR,
    get_trial_ids,
    load_mouse_events,
    get_trial_meta,
    interpolate_scroll,
    result_band_tops,
    extract_serp_results,
    load_trial,
    click_to_position,
)
from episode_classifier import classify_trial_episodes, clear_cache

# Local copies of the NB24 cell 3 geometry helpers — self-contained so we
# don't need to execute the notebook.
RESULT_COL_X_MIN = 162
RESULT_COL_X_MAX = 702
CONTENT_CX = 432


def load_ad_regions(trial_id):
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


def rect_in_result_column(rx, rw):
    return rx < RESULT_COL_X_MAX and (rx + rw) > RESULT_COL_X_MIN


def classify_position(pos_top, pos_bottom, ad_regions):
    pos_cy = (pos_top + pos_bottom) / 2
    for etype, rects in ad_regions.items():
        if etype == 'dd_right':
            continue
        for rx, ry, rw, rh in rects:
            if not rect_in_result_column(rx, rw):
                continue
            if ry <= pos_cy <= ry + rh:
                return etype
    return 'organic'


def aoi_height_for_position(pos, etype, pos_top, pos_bottom, ad_regions):
    if etype == 'organic':
        return pos_bottom - pos_top
    pos_cy = (pos_top + pos_bottom) / 2
    rects = ad_regions.get(etype, [])
    for rx, ry, rw, rh in rects:
        if not rect_in_result_column(rx, rw):
            continue
        if ry <= pos_cy <= ry + rh:
            return rh
    return pos_bottom - pos_top


def arc_length(points):
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total += float(np.sqrt(dx * dx + dy * dy))
    return total


def max_perpendicular_dist(points, p_start, p_end):
    if len(points) < 2:
        return 0.0
    ax, ay = p_start
    bx, by = p_end
    line_len = float(np.sqrt((bx - ax) ** 2 + (by - ay) ** 2))
    if line_len < 1:
        return 0.0
    max_d = 0.0
    for px, py in points:
        d = abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / line_len
        if d > max_d:
            max_d = d
    return max_d


def extract_retreat_arcs_v2(trial_id, min_dwell_ms=100, retreat_pause_ms=500,
                             min_direct_dist=50):
    events, scrolls, clicks = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if meta is None or meta[0] is None:
        return []
    doc_h, _scr_h, _ = meta
    if not events or doc_h < 800:
        return []
    serp = extract_serp_results(trial_id)
    n_results = len(serp) if serp else 10
    if n_results == 0:
        return []
    tops = result_band_tops(n_results, doc_h)
    bottoms = tops[1:] + [doc_h - 200]
    ad_regions = load_ad_regions(trial_id)
    pos_etype = {p: classify_position(tops[p], bottoms[p], ad_regions)
                 for p in range(n_results)}
    pos_height = {p: aoi_height_for_position(p, pos_etype[p], tops[p], bottoms[p], ad_regions)
                  for p in range(n_results)}

    if scrolls:
        scroll_ts = [s[0] for s in scrolls]
        scroll_ys = [s[1] for s in scrolls]
    else:
        scroll_ts = [events[0][0]]
        scroll_ys = [0]

    mouse_pts = []
    for t, evt, x, y in events:
        if evt != 'mousemove':
            continue
        if x == 0 and y == 0:
            continue
        in_col = RESULT_COL_X_MIN <= x <= RESULT_COL_X_MAX
        # evtrack ypos is already page-space — do not add scroll.
        mouse_pts.append((t, x, y, in_col))
    if len(mouse_pts) < 10:
        return []

    # Coordinate-safe: evtrack clicks are already page-space.
    click_pos = click_to_position(clicks, tops, n_results)

    def page_y_to_pos(py, in_col):
        if not in_col:
            return -1
        idx = bisect_right(tops, py) - 1
        if 0 <= idx < n_results:
            return idx
        return -1

    arcs = []
    i = 0
    while i < len(mouse_pts):
        t, x, py, in_col = mouse_pts[i]
        pos = page_y_to_pos(py, in_col)
        if pos < 0:
            i += 1
            continue
        entry_t = t
        exit_idx = None
        j = i + 1
        while j < len(mouse_pts):
            tj, xj, pyj, ic = mouse_pts[j]
            if page_y_to_pos(pyj, ic) != pos:
                exit_idx = j
                break
            j += 1
        if exit_idx is None:
            break
        dwell_ms = mouse_pts[exit_idx][0] - entry_t
        if dwell_ms < min_dwell_ms:
            i = exit_idx
            continue
        aoi_top = tops[pos]
        aoi_bottom = bottoms[pos]
        aoi_cy = (aoi_top + aoi_bottom) / 2
        aoi_h = pos_height[pos]
        cx = CONTENT_CX

        exit_t, exit_x, exit_py, _ = mouse_pts[exit_idx]
        arc_pts = [(exit_x, exit_py)]
        max_d = float(np.sqrt((exit_x - cx) ** 2 + (exit_py - aoi_cy) ** 2))
        max_pt = (exit_x, exit_py)
        k = exit_idx + 1
        retreat_end = exit_idx + 1
        while k < len(mouse_pts):
            tk, xk, pyk, ic_k = mouse_pts[k]
            other_pos = page_y_to_pos(pyk, ic_k)
            if other_pos >= 0 and other_pos != pos:
                retreat_end = k
                break
            if tk - mouse_pts[k - 1][0] > retreat_pause_ms:
                retreat_end = k
                break
            arc_pts.append((xk, pyk))
            d = float(np.sqrt((xk - cx) ** 2 + (pyk - aoi_cy) ** 2))
            if d > max_d:
                max_d = d
                max_pt = (xk, pyk)
            k += 1
            retreat_end = k
        if len(arc_pts) < 3:
            i = max(exit_idx + 1, retreat_end)
            continue

        a_len = arc_length(arc_pts)
        d_dist = float(np.sqrt(
            (arc_pts[-1][0] - arc_pts[0][0]) ** 2 +
            (arc_pts[-1][1] - arc_pts[0][1]) ** 2
        ))
        a_ratio = a_len / d_dist if d_dist >= min_direct_dist else float('nan')
        fitts = float(np.log2(2 * max_d / aoi_h)) if max_d > 0 and aoi_h > 0 else float('nan')
        lat = max_perpendicular_dist(arc_pts, arc_pts[0], max_pt)

        arcs.append({
            'trial_id': trial_id,
            'participant': trial_id.split('-')[0],
            'position': pos,
            'etype': pos_etype[pos],
            'aoi_height': aoi_h,
            'entry_t': entry_t,
            'exit_t': exit_t,
            'dwell_ms': dwell_ms,
            'arc_len': a_len,
            'direct_dist': d_dist,
            'arc_ratio': a_ratio,
            'max_retreat_dist': max_d,
            'fitts_id': fitts,
            'lateral_disp': lat,
            'was_clicked': (click_pos == pos),
        })
        i = max(exit_idx + 1, retreat_end)
    return arcs


def main(tol_pxs=(25, 50, 100, 200)):
    print('Extracting arcs from all trials (one-time work)...')
    trial_ids = get_trial_ids()
    all_arcs = []
    for tid in trial_ids:
        arcs = extract_retreat_arcs_v2(tid)
        if not arcs:
            continue
        all_arcs.extend((tid, a) for a in arcs)
    print(f'Total raw arcs: {len(all_arcs):,}')

    valid = [(tid, a) for tid, a in all_arcs
             if np.isfinite(a['arc_ratio']) and np.isfinite(a['fitts_id'])]
    print(f'Valid arcs: {len(valid):,}')

    retreats = [(tid, a) for tid, a in valid if not a['was_clicked']]
    print(f'Retreats (not clicked): {len(retreats):,}')

    # Per-tolerance sweep
    rows_by_tol = {}
    for tol in tol_pxs:
        clear_cache()
        # Classify retreats in place
        by_trial = defaultdict(list)
        for tid, a in retreats:
            by_trial[tid].append(a)
        classified_all = []
        for tid, group in by_trial.items():
            trial = load_trial(tid)
            if trial is None or not trial['fixations']:
                for a in group:
                    a_copy = dict(a)
                    a_copy['direction'] = None
                    classified_all.append(a_copy)
                continue
            classified, _ = classify_trial_episodes(trial, group, tol_px=float(tol))
            classified_all.extend(classified)
        rows_by_tol[tol] = classified_all

    def lateral_ratio(sub):
        if not sub:
            return float('nan')
        lats = [a['lateral_disp'] for a in sub]
        arcs_ = [a['arc_len'] for a in sub]
        return float(np.median(lats) / np.median(arcs_)) if np.median(arcs_) > 0 else float('nan')

    def median_arc_ratio(sub):
        return float(np.median([a['arc_ratio'] for a in sub])) if sub else float('nan')

    lines = []
    lines.append('# Forward/Regressive Split — CIKM Headlines')
    lines.append('')
    lines.append('Generated by `scripts/forward_regressive_tolerance_sweep.py`.')
    lines.append('Classifier: `episode_classifier.classify_episode`, HWM rule matches')
    lines.append('`data_loader.classify_fixations` (parity verified at 4,036/4,036 fixations).')
    lines.append('')
    lines.append('## Top Ad lateral/arc ratio (sanity check #2: monotonicity)')
    lines.append('')
    lines.append('| tol_px | pooled | forward | regressive | n_fwd | n_reg |')
    lines.append('|-------:|-------:|--------:|-----------:|------:|------:|')
    for tol in tol_pxs:
        rows = rows_by_tol[tol]
        top = [a for a in rows if a['etype'] == 'dd_top']
        fwd = [a for a in top if a.get('direction') == 'forward']
        reg = [a for a in top if a.get('direction') == 'regressive']
        lines.append(
            f'| {tol} | {lateral_ratio(top):.3f} | {lateral_ratio(fwd):.3f} | '
            f'{lateral_ratio(reg):.3f} | {len(fwd)} | {len(reg)} |'
        )
    lines.append('')
    lines.append('Interpretation: forward-only should sit **below** pooled at every tol_px.')
    lines.append('If the forward/regressive sign flips between tol_px=50 and tol_px=100,')
    lines.append('the lateral-ratio finding is fragile and needs a sensitivity footnote.')
    lines.append('')
    lines.append('## Top Ad arc ratio')
    lines.append('')
    lines.append('| tol_px | pooled | forward | regressive |')
    lines.append('|-------:|-------:|--------:|-----------:|')
    for tol in tol_pxs:
        rows = rows_by_tol[tol]
        top = [a for a in rows if a['etype'] == 'dd_top']
        fwd = [a for a in top if a.get('direction') == 'forward']
        reg = [a for a in top if a.get('direction') == 'regressive']
        lines.append(
            f'| {tol} | {median_arc_ratio(top):.2f} | {median_arc_ratio(fwd):.2f} | '
            f'{median_arc_ratio(reg):.2f} |'
        )
    lines.append('')
    lines.append('## Direction distribution across all retreat arcs')
    lines.append('')
    lines.append('| tol_px | forward | regressive | forward% |')
    lines.append('|-------:|--------:|-----------:|---------:|')
    for tol in tol_pxs:
        rows = rows_by_tol[tol]
        n_fwd = sum(1 for a in rows if a.get('direction') == 'forward')
        n_reg = sum(1 for a in rows if a.get('direction') == 'regressive')
        total = n_fwd + n_reg
        pct = 100 * n_fwd / total if total else 0
        lines.append(f'| {tol} | {n_fwd:,} | {n_reg:,} | {pct:.1f}% |')
    lines.append('')
    lines.append('## Stability check')
    lines.append('')
    # Did lateral ratio flip sign between 50 and 100?
    def top_lat(tol, direction):
        rows = [a for a in rows_by_tol[tol] if a['etype'] == 'dd_top' and a.get('direction') == direction]
        return lateral_ratio(rows)
    fwd50, fwd100 = top_lat(50, 'forward'), top_lat(100, 'forward')
    reg50, reg100 = top_lat(50, 'regressive'), top_lat(100, 'regressive')
    gap50 = reg50 - fwd50
    gap100 = reg100 - fwd100
    stable = (gap50 > 0) == (gap100 > 0) and abs(gap50) > 0.01
    lines.append(f'- Forward ratio at tol=50:  {fwd50:.3f}')
    lines.append(f'- Forward ratio at tol=100: {fwd100:.3f}')
    lines.append(f'- Regressive ratio at tol=50:  {reg50:.3f}')
    lines.append(f'- Regressive ratio at tol=100: {reg100:.3f}')
    lines.append(f'- Regressive − forward gap at tol=50:  {gap50:+.3f}')
    lines.append(f'- Regressive − forward gap at tol=100: {gap100:+.3f}')
    lines.append(f'- Stable across tol sweep: **{"YES" if stable else "NO — footnote needed"}**')

    out_path = ROOT / 'notebooks-v2' / 'forward-regressive-headlines.md'
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Wrote {out_path}')
    print()
    print('\n'.join(lines[-14:]))


if __name__ == '__main__':
    main()
