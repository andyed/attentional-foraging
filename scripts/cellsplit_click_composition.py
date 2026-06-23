"""Within-carousel click composition for the dd_top cell split.

The descriptive the cell split unlocks: of the clicks that land inside a
dd_top top-ads carousel, how do they distribute across the carousel's cells
(leftmost = index 0)? Block-level attribution cannot answer this — it sees
one dd_top AOI. This isolates within-surface position bias with NO organic-
rank confound (restricted to clicks on the carousel) and NO variable-length
confound (the headline panel fixes the modal 4-cell carousel).

Source of cells: the shipped cell-aware flavor
  scripts/output/adserp_aois_by_trial_id_typed_gapfill_cellsplit.csv
Source of clicks: data_loader.load_mouse_events (final click per trial).

Outputs (cite-able):
  scripts/output/cellsplit_click_composition/summary.json
  scripts/output/cellsplit_click_composition/by_cell_index.csv      (modal 4-cell)
  scripts/output/cellsplit_click_composition/by_norm_position.csv   (all carousels)

Regime tag: [LAB, AdSERP, typed_gapfill_cellsplit]
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import load_mouse_events  # noqa: E402

CSV = ROOT / "scripts/output/adserp_aois_by_trial_id_typed_gapfill_cellsplit.csv"
OUT = ROOT / "scripts/output/cellsplit_click_composition"
OUT.mkdir(parents=True, exist_ok=True)


def load_cells_by_trial() -> dict:
    """trial_id -> list of dd_top_cell rows (cell_index, n_cells, bbox)."""
    by_trial: dict = defaultdict(list)
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if r["etype"] != "dd_top_cell":
                continue
            by_trial[r["trial_id"]].append({
                "cell_index": int(r["cell_index"]),
                "n_cells": int(r["n_cells"]),
                "x0": float(r["left_x"]), "x1": float(r["right_x"]),
                "y0": float(r["top_y"]), "y1": float(r["bottom_y"]),
            })
    return by_trial


def final_click(trial_id: str):
    md = load_mouse_events(trial_id)
    if not md:
        return None
    _events, _scrolls, clicks = md
    if not clicks:
        return None
    c = clicks[-1]
    if len(c) < 3:
        return None
    return float(c[1]), float(c[2])


def main() -> None:
    cells_by_trial = load_cells_by_trial()
    n_carousels = len(cells_by_trial)

    n_with_click = 0
    n_click_on_carousel = 0
    idx_counts_modal4 = Counter()          # cell_index -> clicks (4-cell carousels)
    norm_bins = Counter()                  # 5 bins of normalized position
    n_modal4_clicks = 0

    for tid, cells in cells_by_trial.items():
        click = final_click(tid)
        if click is None:
            continue
        n_with_click += 1
        cx, cy = click
        hit = next((c for c in cells
                    if c["x0"] <= cx <= c["x1"] and c["y0"] <= cy <= c["y1"]), None)
        if hit is None:
            continue
        n_click_on_carousel += 1
        n = hit["n_cells"]
        i = hit["cell_index"]
        if n == 4:
            idx_counts_modal4[i] += 1
            n_modal4_clicks += 1
        # normalized position 0..1 -> 5 bins (works across variable n_cells)
        npos = i / (n - 1) if n > 1 else 0.0
        norm_bins[min(4, int(npos * 5))] += 1

    summary = {
        "flavor": "typed_gapfill_cellsplit",
        "n_carousels": n_carousels,
        "n_carousels_with_click": n_with_click,
        "n_clicks_on_carousel": n_click_on_carousel,
        "carousel_click_rate": round(n_click_on_carousel / max(n_with_click, 1), 4),
        "modal4": {
            "n_clicks": n_modal4_clicks,
            "by_cell_index_pct": {
                str(i): round(100 * idx_counts_modal4[i] / max(n_modal4_clicks, 1), 1)
                for i in range(4)
            },
            "by_cell_index_count": {str(i): idx_counts_modal4[i] for i in range(4)},
        },
        "leftmost_share_modal4": round(
            100 * idx_counts_modal4[0] / max(n_modal4_clicks, 1), 1),
        "note": ("clicks restricted to those landing inside a dd_top cell bbox; "
                 "modal panel fixes 4-cell carousels (61.9% of carousels) to "
                 "remove the variable-length confound"),
    }

    with open(OUT / "by_cell_index.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cell_index", "count", "pct"])
        for i in range(4):
            w.writerow([i, idx_counts_modal4[i],
                        round(100 * idx_counts_modal4[i] / max(n_modal4_clicks, 1), 2)])
    with open(OUT / "by_norm_position.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["norm_bin", "count", "pct"])
        tot = sum(norm_bins.values())
        for b in range(5):
            w.writerow([b, norm_bins[b], round(100 * norm_bins[b] / max(tot, 1), 2)])
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT}/summary.json")


if __name__ == "__main__":
    main()
