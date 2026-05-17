"""Probe: compute X-gated cell-aware M4 cursor approach features for
dd_top / dd_right / organic_cell AOIs, mirroring the canonical
`m4_nb21_hybrid_rerun.py` extractor (full-cursor-stream, 1D-Y distance)
with an added X-containment gate for cells whose width is < the
single-column SERP width.

Why X-gating: the canonical 1D-Y design assumes "results span the full
column width" (m4_nb21_hybrid_rerun.py line 160-166), which is true
for organic results but breaks for horizontal dd_top carousel cells.
Without X-gating, all cells of a horizontal carousel produce identical
features (the cells share Y-center). With X-gating, each cell's
features count only cursor samples in its X-column.

For organic results (full column width), the X-gate is trivially TRUE
on every sample → features match canonical exactly.

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
    load_mouse_events,
    get_trial_meta,
)

CASCADE_DIR = ROOT / "scripts/output/cascade-baseline/aoi-snapshot-v1"
PROX_THRESHOLD = 100  # px — matches m4_nb21_hybrid_rerun.py


def _midpoint_split_cells(cells: list[dict], parent: dict | None) -> list[dict]:
    """Expand cell X-ranges to cover the gap between neighbors, and the
    edges to the parent's X-range. Same precedent as AllSERP §2.2's
    Y-midpoint split for adjacent organic pairs — applied here on X for
    horizontal carousels so a click in a card-gap region attributes to
    the nearest cell rather than being lost.

    For abutting cells (most dd_top carousels), the in-between boundary
    is already at the midpoint, so only the leftmost cell's left edge
    and rightmost cell's right edge need expanding to the parent edge.
    """
    if not cells:
        return cells
    if parent is None:
        # No parent to expand into — return cells unchanged
        return cells
    # Sort by x
    cells = sorted(cells, key=lambda c: c["x"])
    parent_x_left = parent["x"]
    parent_x_right = parent["x"] + parent["w"]
    new = []
    for i, c in enumerate(cells):
        x_left = c["x"]
        x_right = c["x"] + c["w"]
        # Left edge: midpoint with previous cell's right, or parent edge
        if i == 0:
            x_left = parent_x_left
        else:
            prev_right = cells[i - 1]["x"] + cells[i - 1]["w"]
            x_left = min(x_left, (prev_right + c["x"]) / 2)
        # Right edge: midpoint with next cell's left, or parent edge
        if i == len(cells) - 1:
            x_right = parent_x_right
        else:
            next_left = cells[i + 1]["x"]
            x_right = max(x_right, (x_right + next_left) / 2)
        new_c = dict(c)
        new_c["x"] = x_left
        new_c["w"] = x_right - x_left
        new_c["x_orig"] = c["x"]
        new_c["w_orig"] = c["w"]
        new.append(new_c)
    return new


def load_aois(trial_id: str, midpoint_split: bool = True) -> list[dict]:
    """Return parent + cell AOIs from cascade-baseline snapshot.

    Each AOI dict: {kind, bbox_index, x, y, w, h, role}
    role = "parent" | "cell"  (parent records preserve backward compat;
                                cells carry per-card features.)

    midpoint_split: when True (default), cell X-ranges are expanded to
    cover card-gap regions inside the parent, so clicks at card margins
    attribute to the nearest cell. Mirrors AllSERP §2.2's Y-midpoint
    split for organic pairs.
    """
    path = CASCADE_DIR / f"{trial_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"cascade-baseline snapshot missing: {path}")
    snap = json.load(open(path))
    out = []
    # Index parents by kind+bbox_index for cell-expansion lookup
    parents_by_kind = {}
    for kind in ("dd_top", "dd_right"):
        for i, b in enumerate(snap.get(kind, [])):
            loc, sz = b["location"], b["size"]
            parent_rec = {
                "kind": kind, "role": "parent", "bbox_index": i,
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
            }
            parents_by_kind[(kind, i)] = parent_rec
            out.append(parent_rec)
    # Cells — group by parent_kind so we can expand within each parent
    cells_by_parent_kind = {"dd_top_cell": [], "dd_right_cell": [], "organic_cell": []}
    for cell_kind in cells_by_parent_kind:
        for i, c in enumerate(snap.get(cell_kind, [])):
            loc, sz = c["location"], c["size"]
            cells_by_parent_kind[cell_kind].append({
                "kind": cell_kind, "role": "cell",
                "parent_kind": {"dd_top_cell": "dd_top",
                                 "dd_right_cell": "dd_right",
                                 "organic_cell": "organic_result"}[cell_kind],
                "bbox_index": i, "position": c.get("position"),
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
            })
    # Apply midpoint-split within each parent kind (using the first parent
    # of that kind — typical AdSERP trial has one dd_top, one or zero dd_right)
    if midpoint_split:
        if cells_by_parent_kind["dd_top_cell"]:
            p = parents_by_kind.get(("dd_top", 0))
            cells_by_parent_kind["dd_top_cell"] = _midpoint_split_cells(
                cells_by_parent_kind["dd_top_cell"], p)
        if cells_by_parent_kind["dd_right_cell"]:
            p = parents_by_kind.get(("dd_right", 0))
            cells_by_parent_kind["dd_right_cell"] = _midpoint_split_cells(
                cells_by_parent_kind["dd_right_cell"], p)
        # organic_cell expansion would need parent_organic_result bbox lookup —
        # rare (~7%), defer to future commit.
    for cell_list in cells_by_parent_kind.values():
        out.extend(cell_list)
    return out


def compute_canonical_features(xs: np.ndarray, ys: np.ndarray, ts: np.ndarray,
                                bbox: dict, x_gate: bool) -> dict:
    """Compute the 7 M4 features over a cursor stream against one bbox.

    Mirrors m4_nb21_hybrid_rerun.py:152-209 (the canonical extractor):
      dist = |ys - bbox.cy|   (1D-Y)
      dwell_in_proximity_ms accumulates dt where dist < PROX_THRESHOLD
      velocities from diff(-dist) / diff(ts)
      direction_changes from sign-flips of velocity
      frac_decreasing from diff(dist) < 0

    With x_gate=True: filter to samples where bbox.x <= xs <= bbox.x + bbox.w.
    This is the X-containment rule for cells whose width < column width.
    """
    cy = bbox["y"] + bbox["h"] / 2
    if x_gate:
        mask = (xs >= bbox["x"]) & (xs <= bbox["x"] + bbox["w"])
        xs_g, ys_g, ts_g = xs[mask], ys[mask], ts[mask]
    else:
        xs_g, ys_g, ts_g = xs, ys, ts

    n = len(xs_g)
    out = {"n_samples": int(n)}
    if n < 2:
        # Insufficient samples in the gated region — return null-ish features
        return {**out,
                "min_dist": None, "mean_dist": None, "final_dist": None,
                "retreat_dist": None, "dwell_in_proximity_ms": 0.0,
                "mean_approach_velocity": 0.0, "max_approach_velocity": 0.0,
                "direction_changes": 0, "frac_decreasing": 0.5}

    dist = np.abs(ys_g - cy)
    min_dist = float(dist.min())
    mean_dist = float(dist.mean())
    final_dist = float(dist[-1])
    min_idx = int(np.argmin(dist))
    retreat_dist = float(dist[-1] - dist[min_idx])

    in_prox = dist < PROX_THRESHOLD
    dwell_ms = 0.0
    for i in range(1, n):
        if in_prox[i]:
            dt = int(ts_g[i] - ts_g[i - 1])
            if 0 < dt < 2000:
                dwell_ms += dt

    dts = np.diff(ts_g).astype(float)
    dts[dts == 0] = 1.0
    vels = -np.diff(dist) / dts * 1000.0
    mean_vel = float(vels.mean())
    max_vel = float(vels.max())
    direction_changes = int(np.sum(np.diff(np.sign(vels)) != 0))
    frac_decreasing = float(np.mean(np.diff(dist) < 0))

    return {
        **out,
        "min_dist": min_dist, "mean_dist": mean_dist, "final_dist": final_dist,
        "retreat_dist": retreat_dist,
        "dwell_in_proximity_ms": dwell_ms,
        "mean_approach_velocity": mean_vel,
        "max_approach_velocity": max_vel,
        "direction_changes": direction_changes,
        "frac_decreasing": frac_decreasing,
    }


def probe(trial_id: str) -> dict:
    aois = load_aois(trial_id)
    mouse_data = load_mouse_events(trial_id)
    if not mouse_data:
        return {"trial_id": trial_id, "error": "no mouse events"}

    all_events, _scrolls, clicks = mouse_data
    cursor_stream = [
        (e[0], e[2], e[3])
        for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(cursor_stream) < 2:
        return {"trial_id": trial_id, "error": "insufficient cursor samples"}

    ts = np.array([c[0] for c in cursor_stream])
    xs = np.array([c[1] for c in cursor_stream], dtype=float)
    ys = np.array([c[2] for c in cursor_stream], dtype=float)

    click_x = click_y = None
    if clicks:
        final = clicks[-1]
        if len(final) >= 3:
            click_x, click_y = float(final[1]), float(final[2])

    records = []
    for aoi in aois:
        # X-gate only for cells (parents are full column width by design)
        feats = compute_canonical_features(xs, ys, ts, aoi, x_gate=(aoi["role"] == "cell"))
        was_clicked = False
        if click_x is not None and click_y is not None:
            if (aoi["x"] <= click_x <= aoi["x"] + aoi["w"] and
                aoi["y"] <= click_y <= aoi["y"] + aoi["h"]):
                was_clicked = True
        records.append({**aoi, **feats, "was_clicked": was_clicked})

    return {
        "trial_id": trial_id,
        "click_xy": (click_x, click_y) if click_x is not None else None,
        "total_cursor_samples": int(len(xs)),
        "records": records,
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
