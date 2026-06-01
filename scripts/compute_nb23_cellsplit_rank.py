"""Recompute NB23's rank-effects claims on CELLSPLIT rank.

Sibling to compute_nb23_organic_rank.py and compute_nb23_organic_rank's
parent in spirit — adds a fourth rank flavor to NB23 by treating the
dd_top carousel's K cells as their own per-cell rank coordinates.

Population: the 1,581 dd_top-topped trials (57.0% of the corpus) where
the highest-y non-organic non-chrome AOI is dd_top. Other trials are
excluded by definition — cellsplit only resolves dd_top rank.

Reuses the cellsplit AOI substrate from probe_cellsplit_features.load_aois
(midpoint-split X bboxes from the cascade-baseline snapshot) and the
canonical mouse-click + gaze-fixation loaders.

Metrics per cell position k ∈ {1..K} (typical K=4):
  - n_trials_with_cell_k         (denominator for CTR)
  - n_clicks_cell_k              (clicks landing in cell bbox)
  - ctr_cell_k                   = n_clicks / n_trials_with_cell_k
  - click_share_cell_k           = n_clicks_cell_k / total_clicks_in_dd_top
  - mean_fix_count_cell_k        (avg fixations on cell k per trial)
  - mean_dwell_ms_cell_k         (avg dwell on cell k per trial)

LF/HF is intentionally NOT recomputed in this v1 pass — the existing
butterworth-lfhf-by-position.json is keyed by absolute rank and would
need re-derivation for cellsplit. Deferred to a v2 pass.

Output:
  scripts/output/nb23_cellsplit_rank/summary.json
  scripts/output/nb23_cellsplit_rank/by_cell.csv
  scripts/output/nb23_cellsplit_rank/key_claims_summary.json

Run:
    .venv/bin/python scripts/compute_nb23_cellsplit_rank.py

Idempotent, ~30-60 seconds.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_fixations, load_mouse_events  # noqa: E402
from probe_cellsplit_features import load_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/nb23_cellsplit_rank"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# dd_top-topped trial list: reuse the markov substrate sequences.jsonl,
# which is restricted to the 1,581 trials where dd_top is the topmost
# non-organic non-chrome AOI (canonical dd_top stratum from
# dd_top_markov_extractor.py).
SEQ_PATH = ROOT / "scripts/output/dd_top_markov/sequences.jsonl"


# ── helpers ────────────────────────────────────────────────────────────────

def dd_top_cells(tid: str) -> list[dict]:
    """Return cells with kind=='dd_top_cell' for this trial, ordered by
    position. Midpoint-split applied so card-gap clicks attribute."""
    aois = load_aois(tid, midpoint_split=True)
    cells = [a for a in aois if a["kind"] == "dd_top_cell"]
    cells.sort(key=lambda c: c["position"] if c["position"] is not None else 999)
    return cells


def fixation_in_cell(x: float, y: float, cell: dict) -> bool:
    return (cell["x"] <= x <= cell["x"] + cell["w"]
            and cell["y"] <= y <= cell["y"] + cell["h"])


def first_click_xy(tid: str) -> tuple[float, float] | None:
    """First click coordinate for this trial (None if no clicks)."""
    _, _, clicks = load_mouse_events(tid)
    if not clicks:
        return None
    _, x, y = clicks[0]
    return (x, y)


def load_dd_top_tids() -> list[str]:
    out = []
    with SEQ_PATH.open() as f:
        for line in f:
            d = json.loads(line)
            out.append(d["trial_id"])
    return out


# ── main aggregation ──────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    tids = load_dd_top_tids()
    print(f"[nb23-cs] {len(tids)} dd_top-topped trials")

    # Per-cell accumulators (cell position k = 1..K).
    n_trials_with_cell: Counter[int] = Counter()
    n_clicks_in_cell: Counter[int] = Counter()
    # mean fix count / dwell are per-trial then averaged → collect per-trial vals
    fix_count_by_cell: defaultdict[int, list[int]] = defaultdict(list)
    dwell_ms_by_cell: defaultdict[int, list[float]] = defaultdict(list)

    # Bookkeeping
    n_trials_with_any_cell = 0
    n_trials_with_dd_top_click = 0
    n_trials_with_carousel_click = 0   # clicks landing in any dd_top cell
    n_trials_no_aoi_snapshot = 0
    cells_per_carousel_dist: Counter[int] = Counter()

    # Per-cell carousel-click denominator: trials where the carousel was
    # clicked at all (used for click-share within the carousel).
    n_carousel_click_trials_by_cell: Counter[int] = Counter()

    for idx, tid in enumerate(tids):
        if idx and idx % 200 == 0:
            print(f"[nb23-cs]   {idx}/{len(tids)}  ({time.time() - t0:.1f}s)")

        try:
            cells = dd_top_cells(tid)
        except FileNotFoundError:
            n_trials_no_aoi_snapshot += 1
            continue
        if not cells:
            continue
        n_trials_with_any_cell += 1
        cells_per_carousel_dist[len(cells)] += 1

        for c in cells:
            k = c["position"]
            if k is None:
                continue
            n_trials_with_cell[k] += 1

        # ── Click attribution ────────────────────────────────────────────
        click_xy = first_click_xy(tid)
        if click_xy is not None:
            cx, cy = click_xy
            for c in cells:
                if c["position"] is not None and fixation_in_cell(cx, cy, c):
                    n_clicks_in_cell[c["position"]] += 1
                    n_trials_with_carousel_click += 1
                    # mark which cells were present at the time of the
                    # carousel click — for click-share-within-carousel
                    for cc in cells:
                        if cc["position"] is not None:
                            n_carousel_click_trials_by_cell[cc["position"]] += 1
                    break

        # ── Fixation aggregation per cell ────────────────────────────────
        try:
            fixations = load_fixations(tid)
        except FileNotFoundError:
            continue
        per_cell_fix: Counter[int] = Counter()
        per_cell_dwell: defaultdict[int, float] = defaultdict(float)
        for f in fixations:
            for c in cells:
                if c["position"] is None:
                    continue
                if fixation_in_cell(f["x"], f["y"], c):
                    per_cell_fix[c["position"]] += 1
                    per_cell_dwell[c["position"]] += f["d"]
                    break
        for c in cells:
            k = c["position"]
            if k is None:
                continue
            fix_count_by_cell[k].append(per_cell_fix.get(k, 0))
            dwell_ms_by_cell[k].append(per_cell_dwell.get(k, 0.0))

    print(f"[nb23-cs] aggregation done in {time.time() - t0:.1f}s")
    print(f"[nb23-cs] trials with AOI snapshot + cells: {n_trials_with_any_cell}")
    print(f"[nb23-cs] trials with first click in any cell: {n_trials_with_carousel_click}")
    print(f"[nb23-cs] missing AOI snapshot: {n_trials_no_aoi_snapshot}")

    # ── Derive per-cell metrics ──────────────────────────────────────────
    max_k = max(n_trials_with_cell) if n_trials_with_cell else 0
    rows: list[dict] = []
    for k in range(1, max_k + 1):
        n_trials = n_trials_with_cell.get(k, 0)
        n_clicks = n_clicks_in_cell.get(k, 0)
        fix_counts = fix_count_by_cell.get(k, [])
        dwells = dwell_ms_by_cell.get(k, [])
        row = {
            "cell_position": k,
            "n_trials_with_cell": n_trials,
            "n_clicks_in_cell": n_clicks,
            "ctr": (n_clicks / n_trials) if n_trials else 0.0,
            "click_share_within_carousel": (
                n_clicks / n_trials_with_carousel_click
                if n_trials_with_carousel_click else 0.0
            ),
            "mean_fix_count": float(np.mean(fix_counts)) if fix_counts else 0.0,
            "median_fix_count": float(np.median(fix_counts)) if fix_counts else 0.0,
            "mean_dwell_ms": float(np.mean(dwells)) if dwells else 0.0,
            "median_dwell_ms": float(np.median(dwells)) if dwells else 0.0,
            "n_trials_with_fix_data": len(fix_counts),
        }
        rows.append(row)

    # ── Spearman rho: does each metric trend with cell position? ─────────
    cell_xs = [r["cell_position"] for r in rows]
    spearman = {}
    for metric in ("ctr", "mean_fix_count", "mean_dwell_ms"):
        ys = [r[metric] for r in rows]
        if len(ys) >= 3 and len(set(ys)) > 1:
            rho, p = spearmanr(cell_xs, ys)
            spearman[metric] = {"rho": float(rho), "p": float(p)}

    # ── Persist outputs ──────────────────────────────────────────────────
    csv_path = OUT_DIR / "by_cell.csv"
    with csv_path.open("w") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    summary = {
        "n_trials_in_substrate": len(tids),
        "n_trials_with_cells": n_trials_with_any_cell,
        "n_trials_no_aoi_snapshot": n_trials_no_aoi_snapshot,
        "n_trials_with_carousel_click": n_trials_with_carousel_click,
        "cells_per_carousel_distribution": dict(cells_per_carousel_dist),
        "modal_n_cells": cells_per_carousel_dist.most_common(1)[0][0]
            if cells_per_carousel_dist else None,
        "max_cell_position": max_k,
        "by_cell": rows,
        "spearman_vs_cell_position": spearman,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # ── Key Claims summary — dropdown-paste format for update_key_claims.py
    kc_rows = {}
    for r in rows:
        k = r["cell_position"]
        kc_rows[f"K-cellsplit-{k}-ctr"] = round(r["ctr"], 4)
        kc_rows[f"K-cellsplit-{k}-fix-mean"] = round(r["mean_fix_count"], 3)
        kc_rows[f"K-cellsplit-{k}-dwell-mean-ms"] = round(r["mean_dwell_ms"], 1)
    kc_rows["K-cellsplit-spearman-ctr"] = spearman.get("ctr", {})
    kc_rows["K-cellsplit-spearman-fix"] = spearman.get("mean_fix_count", {})
    kc_rows["K-cellsplit-spearman-dwell"] = spearman.get("mean_dwell_ms", {})
    kc_rows["K-cellsplit-population"] = {
        "n_trials": len(tids),
        "n_with_cells": n_trials_with_any_cell,
        "modal_n_cells": summary["modal_n_cells"],
    }
    (OUT_DIR / "key_claims_summary.json").write_text(
        json.dumps(kc_rows, indent=2))

    # ── Console digest ───────────────────────────────────────────────────
    print()
    print(f"{'cell':>5}  {'n_trials':>9}  {'n_clicks':>9}  {'CTR':>7}  "
          f"{'mean_fix':>9}  {'mean_dwell_ms':>14}")
    for r in rows:
        print(f"{r['cell_position']:>5}  {r['n_trials_with_cell']:>9d}  "
              f"{r['n_clicks_in_cell']:>9d}  {r['ctr']*100:>6.2f}%  "
              f"{r['mean_fix_count']:>9.3f}  {r['mean_dwell_ms']:>14.1f}")
    print()
    print("Spearman ρ vs cell position (1=leftmost):")
    for m, s in spearman.items():
        print(f"  {m:18}  ρ={s['rho']:+.3f}  p={s['p']:.3g}")
    print()
    print(f"[done] outputs at {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
