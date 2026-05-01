"""Compute retreat arc geometry for every trial under both attribution methods.

Mirrors NB24's `extract_retreat_arcs_v2` but produces side-by-side outputs
under absolute-rank (band-tops, h3+ads pooled, etype tagged via ad-rect
overlap) and organic-hybrid (bbox organics + shipped ad rectangles
combined into one ordered position list, etype tagged at construction).

Output:
  AdSERP/data/retreat-arcs.json           — absolute (legacy)
  AdSERP/data/retreat-arcs-organic.json   — bbox organics + shipped ads

Each record contains the same fields as NB24's all_arcs:
  trial_id, participant, position, etype, aoi_height, entry_t, exit_t,
  dwell_ms, arc_len, direct_dist, arc_ratio, max_retreat_dist,
  fitts_id, lateral_disp, was_clicked, n_arc_points

Run:
    .venv/bin/python scripts/compute_retreat_arcs.py --attribution organic_hybrid
"""
from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    DATA_DIR,
    get_trial_ids,
    load_mouse_events,
    get_trial_meta,
    interpolate_scroll,
    result_band_tops,
    extract_serp_results,
    load_trial,
    load_aois,
    organic_aoi_bands,
)
from episode_classifier import classify_trial_episodes  # noqa: E402

AD_DIR = DATA_DIR / "ad-boundary-data"
CONTENT_CX = 432  # Content centerline (ads at x=162, width=540)
RESULT_COL_X_MIN = 162
RESULT_COL_X_MAX = 702


def load_ad_regions(trial_id):
    path = AD_DIR / f"{trial_id}.json"
    if not path.exists():
        return {}
    d = json.load(open(path))
    out = {}
    for etype, elements in d.items():
        rects = []
        for el in elements:
            loc = el.get("location", {})
            size = el.get("size", {})
            rects.append((loc.get("x", 0), loc.get("y", 0),
                          size.get("width", 0), size.get("height", 0)))
        if rects:
            out[etype] = rects
    return out


def rect_in_result_column(rx, rw):
    return rx < RESULT_COL_X_MAX and (rx + rw) > RESULT_COL_X_MIN


def classify_position(pos_top, pos_bottom, ad_regions):
    pos_cy = (pos_top + pos_bottom) / 2
    for etype, rects in ad_regions.items():
        if etype == "dd_right":
            continue
        for rx, ry, rw, rh in rects:
            if not rect_in_result_column(rx, rw):
                continue
            if ry <= pos_cy <= ry + rh:
                return etype
    return "organic"


def aoi_height_for_position(pos, etype, pos_top, pos_bottom, ad_regions):
    if etype == "organic":
        return pos_bottom - pos_top
    pos_cy = (pos_top + pos_bottom) / 2
    rects = ad_regions.get(etype, [])
    for rx, ry, rw, rh in rects:
        if not rect_in_result_column(rx, rw):
            continue
        if ry <= pos_cy <= ry + rh:
            return rh
    return pos_bottom - pos_top


def build_positions(trial_id, attribution, doc_h, ad_regions):
    """Returns (tops, bottoms, etypes, heights) lists."""
    if attribution == "organic_hybrid":
        # Combine bbox organics (etype='organic') + shipped ad rectangles
        # in the result column (etype = 'dd_top' / 'native_ad' as labeled
        # in the ad JSON). dd_right is excluded (right-rail).
        bands = organic_aoi_bands(trial_id)  # list of (top, bot)
        items = [(t, b, "organic", b - t) for t, b in bands]
        for etype, rects in ad_regions.items():
            if etype == "dd_right":
                continue
            for rx, ry, rw, rh in rects:
                if not rect_in_result_column(rx, rw):
                    continue
                items.append((ry, ry + rh, etype, rh))
        if not items:
            return [], [], [], []
        items.sort(key=lambda r: r[0])
        tops = [r[0] for r in items]
        bottoms = [r[1] for r in items]
        etypes = [r[2] for r in items]
        heights = [r[3] for r in items]
        return tops, bottoms, etypes, heights

    # absolute (legacy)
    serp = extract_serp_results(trial_id)
    n_results = len(serp) if serp else 10
    if n_results == 0:
        return [], [], [], []
    tops = list(result_band_tops(n_results, doc_h))
    bottoms = tops[1:] + [doc_h - 200]
    etypes = [classify_position(tops[p], bottoms[p], ad_regions) for p in range(n_results)]
    heights = [aoi_height_for_position(p, etypes[p], tops[p], bottoms[p], ad_regions)
               for p in range(n_results)]
    return tops, bottoms, etypes, heights


def arc_length(points):
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total += np.sqrt(dx * dx + dy * dy)
    return total


def max_perp_dist(points, p_start, p_end):
    if len(points) < 2:
        return 0.0
    ax, ay = p_start
    bx, by = p_end
    line_len = np.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
    if line_len < 1:
        return 0.0
    max_d = 0.0
    for px, py in points:
        d = abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / line_len
        max_d = max(max_d, d)
    return max_d


def extract_retreat_arcs(trial_id, attribution,
                          min_dwell_ms=100, retreat_pause_ms=500, min_direct_dist=50):
    events, scrolls, clicks = load_mouse_events(trial_id)
    meta = get_trial_meta(trial_id)
    if meta is None or meta[0] is None:
        return []
    doc_h, _scr_h, _ = meta
    if not events or doc_h < 800:
        return []

    ad_regions = load_ad_regions(trial_id)
    tops, bottoms, etypes, heights = build_positions(trial_id, attribution, doc_h, ad_regions)
    if not tops:
        return []
    n_results = len(tops)

    if scrolls:
        scroll_ts = [s[0] for s in scrolls]
        scroll_ys = [s[1] for s in scrolls]
    else:
        scroll_ts = [events[0][0]]
        scroll_ys = [0]

    mouse_pts = []
    for t, evt, x, y in events:
        if evt != "mousemove":
            continue
        if x == 0 and y == 0:
            continue
        sy = interpolate_scroll(t, scroll_ts, scroll_ys)
        in_col = RESULT_COL_X_MIN <= x <= RESULT_COL_X_MAX
        mouse_pts.append((t, x, y + sy, in_col))
    if len(mouse_pts) < 10:
        return []

    click_pos = None
    if clicks:
        ct, _cx, cy_click = clicks[0]
        # cy_click is page-space already (no scroll add)
        idx = bisect_right(tops, cy_click) - 1
        if 0 <= idx < n_results:
            click_pos = idx

    def page_y_to_pos(py, in_col):
        if not in_col:
            return -1
        idx = bisect_right(tops, py) - 1
        if 0 <= idx < n_results and py <= bottoms[idx]:
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
        aoi_h = heights[pos]
        cx = CONTENT_CX

        exit_t, exit_x, exit_py, _ = mouse_pts[exit_idx]
        arc_pts = [(exit_x, exit_py)]
        max_d = np.sqrt((exit_x - cx) ** 2 + (exit_py - aoi_cy) ** 2)
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
            d = np.sqrt((xk - cx) ** 2 + (pyk - aoi_cy) ** 2)
            if d > max_d:
                max_d = d
                max_pt = (xk, pyk)
            k += 1
            retreat_end = k

        if len(arc_pts) < 3:
            i = max(exit_idx + 1, retreat_end)
            continue

        a_len = arc_length(arc_pts)
        d_dist = np.sqrt((arc_pts[-1][0] - arc_pts[0][0]) ** 2 +
                         (arc_pts[-1][1] - arc_pts[0][1]) ** 2)
        a_ratio = a_len / d_dist if d_dist >= min_direct_dist else float("nan")
        fitts = float(np.log2(2 * max_d / aoi_h)) if max_d > 0 and aoi_h > 0 else float("nan")
        lat = max_perp_dist(arc_pts, arc_pts[0], max_pt)

        arcs.append({
            "trial_id": trial_id,
            "participant": trial_id.split("-")[0],
            "position": pos,
            "etype": etypes[pos],
            "aoi_height": float(aoi_h),
            "entry_t": int(entry_t),
            "exit_t": int(exit_t),
            "dwell_ms": float(dwell_ms),
            "arc_len": float(a_len),
            "direct_dist": float(d_dist),
            "arc_ratio": a_ratio,
            "max_retreat_dist": float(max_d),
            "fitts_id": fitts,
            "lateral_disp": float(lat),
            "was_clicked": bool(click_pos == pos),
            "n_arc_points": int(len(arc_pts)),
        })
        i = max(exit_idx + 1, retreat_end)

    return arcs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attribution", choices=["absolute", "organic_hybrid"], default="organic_hybrid")
    parser.add_argument("--output", "-o", help="Output path")
    args = parser.parse_args()

    if args.output:
        out_path = Path(args.output)
    elif args.attribution == "organic_hybrid":
        out_path = DATA_DIR / "retreat-arcs-organic.json"
    else:
        out_path = DATA_DIR / "retreat-arcs.json"

    tids = get_trial_ids()
    all_arcs = []
    n_ok = n_skip = 0
    for i, tid in enumerate(tids):
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(tids)}...", file=sys.stderr)
        try:
            arcs = extract_retreat_arcs(tid, args.attribution)
            if arcs:
                trial = load_trial(tid)
                if trial is not None and trial.get("fixations"):
                    arcs, _ = classify_trial_episodes(trial, arcs, tol_px=50.0)
                else:
                    for a in arcs:
                        a["direction"] = None
                all_arcs.extend(arcs)
                n_ok += 1
            else:
                n_skip += 1
        except Exception as e:
            n_skip += 1
            print(f"  SKIP {tid}: {e}", file=sys.stderr)

    print(f"\n{args.attribution}: {n_ok} processed, {n_skip} skipped, {len(all_arcs):,} arcs", file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_arcs, f)
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
