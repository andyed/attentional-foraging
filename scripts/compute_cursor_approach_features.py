"""Compute per-result cursor approach features for every trial.

Extracts the `compute_approach_features` function from NB15 into a
standalone producer with `--attribution {absolute, organic, organic_hybrid}`.

- absolute: legacy band estimation on h3 count (pools ads + organics).
  Output: `AdSERP/data/cursor-approach-features.json`.
- organic: bbox-derived AOIs, organic results only (ads excluded).
  Output: `AdSERP/data/cursor-approach-features-organic.json`.
- organic_hybrid: bbox organics + shipped ad rectangles in the result
  column (dd_right excluded), sorted in display order. Adds an `etype`
  field per record (`organic` / `dd_top` / `native_ad`).
  Output: `AdSERP/data/cursor-approach-features-organic-hybrid.json`.

Output schema (per record):
  trial_id, position, etype (hybrid only), was_clicked, n_fixations,
  total_dwell_ms, click_pos, entry_t, exit_t,
  min_dist, mean_dist, final_dist, retreat_dist,
  dwell_in_proximity_ms, mean_approach_velocity, max_approach_velocity,
  direction_changes, frac_decreasing

Run:
    .venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic_hybrid
    .venv/bin/python scripts/compute_cursor_approach_features.py --attribution organic
    .venv/bin/python scripts/compute_cursor_approach_features.py --attribution absolute
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
    organic_aoi_bands,
)


# Mirrors compute_retreat_arcs.py — the result column is roughly x ∈ [50, 750].
AD_DIR = DATA_DIR / "ad-boundary-data"
RESULT_COL_X_MIN = 50
RESULT_COL_X_MAX = 750


def _load_ad_regions(trial_id):
    """Load shipped ad rectangles per trial. Same loader as compute_retreat_arcs.py."""
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


def _rect_in_result_column(rx, rw):
    return rx < RESULT_COL_X_MAX and (rx + rw) > RESULT_COL_X_MIN


def build_hybrid_aois(trial_id):
    """Return parallel (tops, bottoms, etypes) lists in display order.

    Combines bbox organics (etype='organic') with shipped ad rectangles in the
    result column (etype = 'dd_top' / 'native_ad'). dd_right (right-rail) is
    excluded. Returns empty lists if neither organics nor in-column ads exist.
    """
    bands = organic_aoi_bands(trial_id) or []
    items = [(t, b, "organic") for t, b in bands]
    ad_regions = _load_ad_regions(trial_id)
    for etype, rects in ad_regions.items():
        if etype == "dd_right":
            continue
        for rx, ry, rw, rh in rects:
            if not _rect_in_result_column(rx, rw):
                continue
            items.append((ry, ry + rh, etype))
    if not items:
        return [], [], []
    items.sort(key=lambda r: r[0])
    tops = [r[0] for r in items]
    bottoms = [r[1] for r in items]
    etypes = [r[2] for r in items]
    return tops, bottoms, etypes


def compute_approach_features(trial_id, attribution="absolute"):
    """Compute per-result cursor approach features for a trial.

    attribution: 'absolute' uses count_results_html + result_band_tops;
                 'organic'  uses load_aois -> organic_aoi_tops;
                 'organic_hybrid' combines bbox organics + ad rectangles
                                   (dd_top / native_ad) in display order.
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

    etypes = None  # set only under organic_hybrid / typed; tagged into output records.
    if attribution == "organic":
        tops = organic_aoi_tops(trial_id)
        n_results = len(tops)
        if n_results == 0:
            return None
    elif attribution == "organic_hybrid":
        tops_list, _bottoms, etypes_list = build_hybrid_aois(trial_id)
        n_results = len(tops_list)
        if n_results == 0:
            return None
        tops = tops_list
        etypes = etypes_list
    elif attribution == "typed":
        # HTML+vision typed AOI map (Phase 1+2 of feat/aoi-pipeline-v3-typed)
        from data_loader import typed_aoi_tops, typed_aoi_etypes
        tops_list = typed_aoi_tops(trial_id)
        if not tops_list:
            return None
        tops = tops_list
        n_results = len(tops_list)
        etypes = typed_aoi_etypes(trial_id)
    elif attribution == "typed_gapfill":
        # Midpoint-split typed AOI map. See
        # docs/null-findings/2026-05-05-bbox-y-coverage.md.
        from data_loader import (
            typed_gapfill_aoi_tops, typed_gapfill_aoi_etypes,
            is_main_axis_click,
        )
        # Trial-level filter: drop the 158 hard-error trials where the
        # final click is not on a main-axis AOI under typed_gapfill
        # (dd_right, right_chrome, off-target). Returning None here causes
        # the trial to be skipped from the output entirely.
        if not is_main_axis_click(trial_id):
            return None
        tops_list = typed_gapfill_aoi_tops(trial_id)
        if not tops_list:
            return None
        tops = tops_list
        n_results = len(tops_list)
        etypes = typed_gapfill_aoi_etypes(trial_id)
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

    if attribution == "typed_gapfill":
        # X+Y bbox-aware click attribution — the core fix for the 22.7%
        # contamination by Y-band-only attribution. Falls back to Y-band
        # via click_to_position only when the bbox-aware attribution
        # returns None (which shouldn't happen for is_main_axis_click==True
        # trials, but we keep the fallback to avoid silent skips).
        from data_loader import attribute_click_to_typed_gapfill
        if clicks:
            final = clicks[-1]
            if len(final) >= 3:
                cx, cy = float(final[1]), float(final[2])
                attrib = attribute_click_to_typed_gapfill(cx, cy, trial_id)
                click_pos = attrib[0] if attrib is not None else None
            else:
                click_pos = None
        else:
            click_pos = None
    else:
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

        rec = {
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
        }
        if etypes is not None:
            rec["etype"] = etypes[pos]
        records.append(rec)

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--attribution",
        choices=["absolute", "organic", "organic_hybrid", "typed", "typed_gapfill"],
        default="organic",
    )
    parser.add_argument("--output", "-o", help="Output JSON path (default depends on attribution)")
    parser.add_argument("--trial", help="Single trial only (for testing)")
    args = parser.parse_args()

    if args.output:
        out_path = Path(args.output)
    elif args.attribution == "typed_gapfill":
        out_path = DATA_DIR / "cursor-approach-features-typed-gapfill.json"
    elif args.attribution == "typed":
        out_path = DATA_DIR / "cursor-approach-features-typed.json"
    elif args.attribution == "organic_hybrid":
        out_path = DATA_DIR / "cursor-approach-features-organic-hybrid.json"
    elif args.attribution == "organic":
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
