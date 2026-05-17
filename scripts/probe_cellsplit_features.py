"""Probe: compute M4 cursor approach features per dd_top/dd_right/organic
*cell* and compare to parent-only features.

This is the first concrete step on `cell-aware-features` branch. Reads
the cascade-baseline snapshot (which has dd_top_cell / dd_right_cell /
organic_cell from `extract_organic_bboxes.py` subdivision), computes
the 7 M4 features against each cell's Y-centerline, and emits a JSON
that pairs parent-features vs cell-features for sensitivity analysis.

Decisions per scope review (Andy, 2026-05-16):
- Emit both parent AND cell records; cells inherit parent etype and
  carry a `bbox_index` field.
- Click attribution to the cell containing the click's (x, y).

Why this is a probe, not yet a producer: refactoring
`compute_cursor_approach_features.py` to take a richer AOI source is
the next commit; this script proves the data flow on one trial first.

Run:
    .venv/bin/python scripts/probe_cellsplit_features.py p019-b4-t6
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    load_fixations,
    load_mouse_events,
    get_trial_meta,
    gaze_cursor_distance,
)

CASCADE_DIR = ROOT / "scripts/output/cascade-baseline/aoi-snapshot-v1"
PROX_THRESHOLD = 100  # px


def load_cell_bboxes(trial_id: str) -> dict:
    """Return cascade-baseline parent + cell bboxes for the trial.

    Schema returned:
      {
        "parent": [{"kind": "dd_top", "y": 158, "h": 296, "x": 162, "w": 587, "bbox_index": 0}, ...],
        "cells":  [{"kind": "dd_top_cell", "parent_index": 0, "y": 158, "h": 296,
                    "x": 170, "w": 101, "bbox_index": 0}, ...],
      }
    """
    path = CASCADE_DIR / f"{trial_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"cascade-baseline snapshot missing: {path}")
    snap = json.load(open(path))
    parents = []
    cells = []
    # parents = dd_top, dd_right (kinds with cells)
    for kind in ("dd_top", "dd_right"):
        for i, b in enumerate(snap.get(kind, [])):
            loc = b["location"]
            sz = b["size"]
            parents.append({
                "kind": kind, "bbox_index": i,
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
            })
    # cells
    for cell_kind, parent_kind in (("dd_top_cell", "dd_top"),
                                    ("dd_right_cell", "dd_right"),
                                    ("organic_cell", "organic_result")):
        for i, c in enumerate(snap.get(cell_kind, [])):
            loc = c["location"]
            sz = c["size"]
            cells.append({
                "kind": cell_kind, "parent_kind": parent_kind, "bbox_index": i,
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
                "position": c.get("position"),
            })
    return {"parent": parents, "cells": cells}


def compute_features_for_bbox(bbox: dict, fixations: list, mouse_ts: np.ndarray,
                               mouse_xs: np.ndarray, mouse_ys: np.ndarray,
                               click_x: float | None, click_y: float | None) -> dict:
    """Compute the 7 M4 features for one bbox over the fixation+cursor
    streams, using Y-distance to the bbox center (mirrors
    compute_cursor_approach_features.py lines 270-336)."""
    center_y = bbox["y"] + bbox["h"] / 2

    # Use ALL fixations (not band-filtered) — the parent-only producer
    # filters by position-band; for per-cell we approximate by using
    # fixations whose nearest-bbox is this one. For probe purposes,
    # just use all fixations in the trial — the Y-distance feature
    # naturally weighs near-bbox samples.
    distances = []
    cursor_velocities = []
    dwell_in_proximity = 0

    for fix in fixations:
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

        cursor_to_result = abs(my - center_y)
        if cursor_to_result < PROX_THRESHOLD:
            dwell_in_proximity += fix.get("d", 200)

        vel_window = 200
        mask_before = (mouse_ts >= t - vel_window) & (mouse_ts < t)
        mask_after = (mouse_ts > t) & (mouse_ts <= t + vel_window)
        if mask_before.any() and mask_after.any():
            y_before = float(np.mean(mouse_ys[mask_before]))
            y_after = float(np.mean(mouse_ys[mask_after]))
            dist_before = abs(y_before - center_y)
            dist_after = abs(y_after - center_y)
            velocity = (dist_before - dist_after) / (vel_window * 2 / 1000)
            cursor_velocities.append(velocity)

    distances = np.array(distances)
    feats = {
        "min_dist": float(np.min(distances)) if len(distances) else 0,
        "mean_dist": float(np.mean(distances)) if len(distances) else 0,
        "dwell_in_proximity_ms": float(dwell_in_proximity),
        "n_fixations": int(len(fixations)),
    }
    if cursor_velocities:
        feats["mean_approach_velocity"] = float(np.mean(cursor_velocities))
        feats["max_approach_velocity"] = float(np.max(cursor_velocities))
        signs = np.sign(cursor_velocities)
        feats["direction_changes"] = int(np.sum(np.abs(np.diff(signs)) > 0)) if len(cursor_velocities) > 1 else 0
    else:
        feats["mean_approach_velocity"] = 0.0
        feats["max_approach_velocity"] = 0.0
        feats["direction_changes"] = 0
    if len(distances) >= 3:
        diffs = np.diff(distances)
        feats["frac_decreasing"] = float(np.mean(diffs < 0))
    else:
        feats["frac_decreasing"] = 0.5

    # Click attribution at cell-level: click (cx, cy) lies inside this bbox?
    feats["was_clicked"] = False
    if click_x is not None and click_y is not None:
        if (bbox["x"] <= click_x <= bbox["x"] + bbox["w"] and
            bbox["y"] <= click_y <= bbox["y"] + bbox["h"]):
            feats["was_clicked"] = True
    return feats


def probe(trial_id: str) -> dict:
    bboxes = load_cell_bboxes(trial_id)
    fixations = load_fixations(trial_id)
    mouse_data = load_mouse_events(trial_id)
    if not fixations or not mouse_data:
        return {"trial_id": trial_id, "error": "missing fixations or mouse events"}

    all_events, _scrolls, clicks = mouse_data
    mouse_timeline = [
        (e[0], e[2], e[3])
        for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(mouse_timeline) < 2:
        return {"trial_id": trial_id, "error": "insufficient mouse events"}

    mouse_ts = np.array([m[0] for m in mouse_timeline])
    mouse_xs = np.array([m[1] for m in mouse_timeline], dtype=float)
    mouse_ys = np.array([m[2] for m in mouse_timeline], dtype=float)

    click_x = click_y = None
    if clicks:
        final = clicks[-1]
        if len(final) >= 3:
            click_x, click_y = float(final[1]), float(final[2])

    # Parent features
    parent_records = []
    for p in bboxes["parent"]:
        feats = compute_features_for_bbox(p, fixations, mouse_ts, mouse_xs, mouse_ys,
                                           click_x, click_y)
        parent_records.append({**p, **feats})

    # Cell features
    cell_records = []
    for c in bboxes["cells"]:
        feats = compute_features_for_bbox(c, fixations, mouse_ts, mouse_xs, mouse_ys,
                                           click_x, click_y)
        cell_records.append({**c, **feats})

    return {
        "trial_id": trial_id,
        "click_xy": (click_x, click_y) if click_x is not None else None,
        "parent_records": parent_records,
        "cell_records": cell_records,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: probe_cellsplit_features.py <trial_id>", file=sys.stderr)
        sys.exit(2)
    trial_id = sys.argv[1]
    result = probe(trial_id)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
