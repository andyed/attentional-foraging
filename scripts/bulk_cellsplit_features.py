"""Bulk-run the cell-aware feature extractor on all 2,776 AdSERP trials.

Emits a parallel features file to the canonical
`cursor-approach-features-organic-hybrid-buf500.json` (which has parent-only
records). The cellsplit output contains BOTH parent records (role='parent',
no X-gating, identical math to canonical) AND cell records (role='cell',
X-gated for the narrow horizontal carousel case).

Applies the canonical Δ=500ms click-buffer (m4_nb21_hybrid_rerun line
237-246 / compute_cursor_approach_features line 233-246): cursor samples
with t < click_t - 500ms.

Output:
  AdSERP/data/cursor-approach-features-organic-hybrid-cellsplit-buf500.json
  scripts/output/cellsplit-diff/summary.json     (parent vs cell deltas)

Run:
    .venv/bin/python scripts/bulk_cellsplit_features.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from collections import Counter

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import get_trial_ids, load_mouse_events  # noqa: E402
from probe_cellsplit_features import load_aois, compute_canonical_features  # noqa: E402

CLICK_BUFFER_MS = 500
OUT_JSON = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-cellsplit-buf500.json"
DIFF_DIR = ROOT / "scripts/output/cellsplit-diff"
DIFF_DIR.mkdir(parents=True, exist_ok=True)


def run_one(trial_id: str) -> dict | None:
    try:
        aois = load_aois(trial_id)
    except FileNotFoundError:
        return None
    if not aois:
        return None

    mouse_data = load_mouse_events(trial_id)
    if not mouse_data:
        return None

    all_events, _scrolls, clicks = mouse_data
    cursor_stream = [
        (e[0], e[2], e[3])
        for e in all_events
        if e[1] in ("mousemove", "click", "mouseover") and e[2] > 0
    ]
    if len(cursor_stream) < 2:
        return None

    ts = np.array([c[0] for c in cursor_stream])
    xs = np.array([c[1] for c in cursor_stream], dtype=float)
    ys = np.array([c[2] for c in cursor_stream], dtype=float)

    click_x = click_y = click_t = None
    if clicks:
        final = clicks[-1]
        if len(final) >= 3:
            click_t = float(final[0])
            click_x, click_y = float(final[1]), float(final[2])

    # Apply Δ=500ms click-buffer to cursor stream
    if click_t is not None:
        cutoff = click_t - CLICK_BUFFER_MS
        mask = ts < cutoff
        if mask.sum() < 2:
            return None
        ts, xs, ys = ts[mask], xs[mask], ys[mask]

    records = []
    for aoi in aois:
        feats = compute_canonical_features(xs, ys, ts, aoi, x_gate=(aoi["role"] == "cell"))
        was_clicked = False
        if click_x is not None and click_y is not None:
            if (aoi["x"] <= click_x <= aoi["x"] + aoi["w"] and
                aoi["y"] <= click_y <= aoi["y"] + aoi["h"]):
                was_clicked = True
        records.append({**aoi, **feats, "was_clicked": was_clicked, "trial_id": trial_id})

    return {"trial_id": trial_id, "click_xy": (click_x, click_y), "records": records}


def main():
    trial_ids = get_trial_ids()
    print(f"[bulk-cellsplit] {len(trial_ids)} trials, click-buffer={CLICK_BUFFER_MS}ms")

    t0 = time.time()
    all_records = []
    n_trials_with_cells = 0
    n_trials_skipped = 0
    n_total_parent_records = 0
    n_total_cell_records = 0
    cell_kind_counts = Counter()

    for i, tid in enumerate(trial_ids):
        if i % 500 == 0 and i > 0:
            elapsed = time.time() - t0
            print(f"  [{i}/{len(trial_ids)}] elapsed={elapsed:.1f}s  cells_so_far={n_total_cell_records}")
        r = run_one(tid)
        if r is None:
            n_trials_skipped += 1
            continue
        has_cell = any(rec["role"] == "cell" for rec in r["records"])
        if has_cell:
            n_trials_with_cells += 1
        for rec in r["records"]:
            if rec["role"] == "parent":
                n_total_parent_records += 1
            else:
                n_total_cell_records += 1
                cell_kind_counts[rec["kind"]] += 1
        all_records.extend(r["records"])

    elapsed = time.time() - t0
    print(f"\n[bulk-cellsplit] done in {elapsed:.1f}s")
    print(f"  trials processed:       {len(trial_ids) - n_trials_skipped}")
    print(f"  trials skipped:         {n_trials_skipped}")
    print(f"  trials with cells:      {n_trials_with_cells}")
    print(f"  total parent records:   {n_total_parent_records}")
    print(f"  total cell records:     {n_total_cell_records}")
    print(f"  cell kinds: {dict(cell_kind_counts)}")

    # Emit features JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump({
            "_meta": {
                "click_buffer_ms": CLICK_BUFFER_MS,
                "n_trials": len(trial_ids),
                "n_processed": len(trial_ids) - n_trials_skipped,
                "n_skipped": n_trials_skipped,
                "n_trials_with_cells": n_trials_with_cells,
                "n_parent_records": n_total_parent_records,
                "n_cell_records": n_total_cell_records,
                "cell_kinds": dict(cell_kind_counts),
            },
            "records": all_records,
        }, f)
    print(f"\n[bulk-cellsplit] wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"  file size: {OUT_JSON.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
