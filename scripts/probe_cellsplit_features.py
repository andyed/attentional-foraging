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


def load_aois(trial_id: str) -> list[dict]:
    """Return parent + cell AOIs from cascade-baseline snapshot.

    Each AOI dict: {kind, bbox_index, x, y, w, h, role}
    role = "parent" | "cell"  (parent records preserve backward compat;
                                cells carry per-card features.)
    """
    path = CASCADE_DIR / f"{trial_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"cascade-baseline snapshot missing: {path}")
    snap = json.load(open(path))
    out = []
    # Parents — emit alongside cells so analyses can pick either view
    for kind in ("dd_top", "dd_right"):
        for i, b in enumerate(snap.get(kind, [])):
            loc, sz = b["location"], b["size"]
            out.append({
                "kind": kind, "role": "parent", "bbox_index": i,
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
            })
    # Cells — narrower X-extent than parent in the horizontal case
    for cell_kind, parent_kind in (("dd_top_cell", "dd_top"),
                                    ("dd_right_cell", "dd_right"),
                                    ("organic_cell", "organic_result")):
        for i, c in enumerate(snap.get(cell_kind, [])):
            loc, sz = c["location"], c["size"]
            out.append({
                "kind": cell_kind, "role": "cell", "parent_kind": parent_kind,
                "bbox_index": i, "position": c.get("position"),
                "x": loc["x"], "y": loc["y"], "w": sz["width"], "h": sz["height"],
            })
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
