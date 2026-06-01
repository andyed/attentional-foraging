"""Cellsplit-aware re-derivation of NB25's composition + click claims.

Sibling to compute_nb23_cellsplit_rank.py — same cellsplit substrate,
different downstream consumer. NB25 documents corpus composition (slot
counts, ad placements, click distribution by rank). The cellsplit lens
refines NB25's §3 finding ("clicks by absolute rank peak at rank 2,
that's dd_top displacement") by expanding the dd_top widget into its
K constituent cells and re-assigning clicks accordingly.

Two parallel rank schemes computed per trial:

  abs_standard  — every AOI counts as 1 slot; dd_top = 1 slot
  abs_cellsplit — dd_top expands to K cells, shifting downstream
                  slots; trials without dd_top have abs_cellsplit ==
                  abs_standard

Click attribution: bbox y-band containment (more accurate than the
existing equal-band approximation that survey_serp_structure.py uses).

Output:
  scripts/output/nb25_cellsplit_composition/clicks_by_abs_cellsplit_rank.csv
  scripts/output/nb25_cellsplit_composition/clicks_by_abs_standard_rank.csv
  scripts/output/nb25_cellsplit_composition/cells_per_carousel.csv
  scripts/output/nb25_cellsplit_composition/summary.json
  scripts/output/nb25_cellsplit_composition/key_claims_summary.json

Run:
    .venv/bin/python scripts/compute_nb25_cellsplit_composition.py

Idempotent, ~30 seconds.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import get_trial_ids, load_mouse_events  # noqa: E402
from probe_cellsplit_features import load_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/nb25_cellsplit_composition"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── slot construction ─────────────────────────────────────────────────────

def trial_slots(tid: str, cellsplit: bool) -> list[dict]:
    """Return ordered (by y) list of slot dicts for the trial.

    Each slot: {kind, y_top, y_bot, x, w, position, source_role}
    cellsplit=False → dd_top is one slot at y of its parent bbox
    cellsplit=True  → dd_top expands to K cell slots
    """
    try:
        aois = load_aois(tid, midpoint_split=True)
    except FileNotFoundError:
        return []
    slots = []
    # Group by kind (and skip per-trial duplicates we don't want as slots).
    # Strategy: include parent for dd_top (when not cellsplit) and dd_right.
    # Include cells when cellsplit=True. Include organic_result and native_ad
    # as direct slots regardless. Skip 'cell' rows that aren't dd_top_cell
    # when not cellsplit; include them otherwise.
    for a in aois:
        if a["kind"] == "dd_top" and a["role"] == "parent":
            if not cellsplit:
                slots.append(_slot(a, source="dd_top"))
        elif a["kind"] == "dd_top_cell":
            if cellsplit:
                slots.append(_slot(a, source="dd_top_cell"))
        elif a["kind"] == "dd_right" and a["role"] == "parent":
            slots.append(_slot(a, source="dd_right"))
        elif a["kind"] in ("dd_right_cell", "organic_cell"):
            # ignore — these would double-count with their parents
            continue
    # AOIs from load_aois don't include organic_result + native_ad parents,
    # so layer them from the same cascade-baseline snapshot.
    for k in ("organic_result", "native_ad"):
        for r in _load_kind_from_snapshot(tid, k):
            slots.append(r)
    slots.sort(key=lambda s: s["y_top"])
    return slots


def _slot(a: dict, source: str) -> dict:
    return {
        "kind": a["kind"],
        "source": source,
        "position": a.get("position"),
        "y_top": float(a["y"]),
        "y_bot": float(a["y"] + a["h"]),
        "x": float(a["x"]),
        "x_end": float(a["x"] + a["w"]),
    }


def _load_kind_from_snapshot(tid: str, kind: str) -> list[dict]:
    """Pull `kind` rectangles directly from the cascade-baseline snapshot —
    load_aois currently only returns dd_top / dd_right parents + their cells."""
    snap_path = (ROOT / "scripts/output/cascade-baseline/aoi-snapshot-v1"
                 / f"{tid}.json")
    if not snap_path.exists():
        return []
    snap = json.loads(snap_path.read_text())
    out = []
    for i, b in enumerate(snap.get(kind, [])):
        loc, sz = b["location"], b["size"]
        out.append({
            "kind": kind,
            "source": kind,
            "position": b.get("position", i),
            "y_top": float(loc["y"]),
            "y_bot": float(loc["y"] + sz["height"]),
            "x": float(loc["x"]),
            "x_end": float(loc["x"] + sz["width"]),
        })
    return out


def click_to_rank(click_xy: tuple[float, float], slots: list[dict]
                  ) -> int | None:
    """Assign a click to a slot rank (0-indexed) by bbox containment.

    Containment rule:
      1. If click y is inside any slot's [y_top, y_bot] band AND click x is
         inside the slot's x-range (or the slot has no x-range, e.g.
         organic that spans the column): assign that slot.
      2. Else: tolerance-snap to nearest slot whose y-band is within 30 px
         vertically. (Matches the K-bbox 30-px snap convention.)
      3. Else: None.
    """
    cx, cy = click_xy
    for i, s in enumerate(slots):
        if s["y_top"] <= cy <= s["y_bot"]:
            # X check — only enforced for narrow horizontal slots (cells
            # where x_end - x < 540, the canonical column width).
            if (s["x_end"] - s["x"]) < 540:
                if not (s["x"] <= cx <= s["x_end"]):
                    continue
            return i
    # 30-px y-snap
    best_i, best_dist = None, 30.1
    for i, s in enumerate(slots):
        d_above = s["y_top"] - cy
        d_below = cy - s["y_bot"]
        d = max(0.0, max(d_above, d_below))
        if d < best_dist:
            best_dist = d
            best_i = i
    return best_i


# ── main aggregation ──────────────────────────────────────────────────────

def main() -> None:
    t0 = time.time()
    tids = get_trial_ids()
    print(f"[nb25-cs] {len(tids)} trials")

    clicks_by_cellsplit: Counter[int] = Counter()
    clicks_by_standard: Counter[int] = Counter()
    clicks_no_rank_cellsplit = 0
    clicks_no_rank_standard = 0
    n_trials_with_click = 0

    cells_per_carousel: Counter[int] = Counter()
    n_trials_with_dd_top = 0
    n_trials_no_snapshot = 0
    n_dd_top_clicks_cellsplit = 0
    n_dd_top_clicks_standard = 0

    for idx, tid in enumerate(tids):
        if idx and idx % 500 == 0:
            print(f"[nb25-cs]   {idx}/{len(tids)}  ({time.time() - t0:.1f}s)")

        slots_std = trial_slots(tid, cellsplit=False)
        slots_cs = trial_slots(tid, cellsplit=True)
        if not slots_std and not slots_cs:
            n_trials_no_snapshot += 1
            continue

        # Composition: count carousel cells
        n_cells = sum(1 for s in slots_cs if s["kind"] == "dd_top_cell")
        if n_cells > 0:
            cells_per_carousel[n_cells] += 1
            n_trials_with_dd_top += 1

        # Clicks
        try:
            _, _, clicks = load_mouse_events(tid)
        except Exception:
            clicks = []
        if not clicks:
            continue
        n_trials_with_click += 1
        # First click per trial (matches nb23 convention).
        _t, cx, cy = clicks[0]
        r_std = click_to_rank((cx, cy), slots_std)
        r_cs = click_to_rank((cx, cy), slots_cs)
        if r_std is None:
            clicks_no_rank_standard += 1
        else:
            clicks_by_standard[r_std] += 1
            if slots_std[r_std]["kind"] == "dd_top":
                n_dd_top_clicks_standard += 1
        if r_cs is None:
            clicks_no_rank_cellsplit += 1
        else:
            clicks_by_cellsplit[r_cs] += 1
            if slots_cs[r_cs]["kind"] == "dd_top_cell":
                n_dd_top_clicks_cellsplit += 1

    elapsed = time.time() - t0
    print(f"[nb25-cs] done in {elapsed:.1f}s")
    print(f"[nb25-cs] trials with dd_top cells: {n_trials_with_dd_top}")
    print(f"[nb25-cs] trials with click: {n_trials_with_click}")
    print(f"[nb25-cs] trials missing snapshot: {n_trials_no_snapshot}")

    # ── Persist ──────────────────────────────────────────────────────────
    def write_rank_csv(path: Path, ctr: Counter) -> None:
        total = sum(ctr.values()) or 1
        with path.open("w") as f:
            w = csv.writer(f)
            w.writerow(["rank", "count", "pct"])
            for r in sorted(ctr):
                w.writerow([r, ctr[r], round(ctr[r] / total * 100, 2)])

    write_rank_csv(OUT_DIR / "clicks_by_abs_cellsplit_rank.csv",
                   clicks_by_cellsplit)
    write_rank_csv(OUT_DIR / "clicks_by_abs_standard_rank.csv",
                   clicks_by_standard)

    with (OUT_DIR / "cells_per_carousel.csv").open("w") as f:
        w = csv.writer(f)
        w.writerow(["n_cells", "count", "pct"])
        denom = sum(cells_per_carousel.values()) or 1
        for n in sorted(cells_per_carousel):
            w.writerow([n, cells_per_carousel[n],
                        round(cells_per_carousel[n] / denom * 100, 2)])

    # Peak detection
    def top_rank(ctr: Counter) -> tuple[int, int]:
        if not ctr:
            return (-1, 0)
        return max(ctr.items(), key=lambda kv: kv[1])

    pk_std_rank, pk_std_n = top_rank(clicks_by_standard)
    pk_cs_rank, pk_cs_n = top_rank(clicks_by_cellsplit)
    total_std = sum(clicks_by_standard.values()) or 1
    total_cs = sum(clicks_by_cellsplit.values()) or 1

    summary = {
        "n_trials": len(tids),
        "n_trials_with_dd_top_carousel": n_trials_with_dd_top,
        "n_trials_with_click": n_trials_with_click,
        "n_trials_no_snapshot": n_trials_no_snapshot,
        "cells_per_carousel": dict(cells_per_carousel),
        "modal_n_cells": (cells_per_carousel.most_common(1)[0][0]
                          if cells_per_carousel else None),
        "n_dd_top_clicks_standard": n_dd_top_clicks_standard,
        "n_dd_top_clicks_cellsplit": n_dd_top_clicks_cellsplit,
        "abs_standard_peak": {"rank": pk_std_rank, "count": pk_std_n,
                              "pct": round(pk_std_n / total_std * 100, 2)},
        "abs_cellsplit_peak": {"rank": pk_cs_rank, "count": pk_cs_n,
                               "pct": round(pk_cs_n / total_cs * 100, 2)},
        "abs_standard_top10": [
            (r, clicks_by_standard[r],
             round(clicks_by_standard[r] / total_std * 100, 2))
            for r in sorted(clicks_by_standard)[:11]
        ],
        "abs_cellsplit_top10": [
            (r, clicks_by_cellsplit[r],
             round(clicks_by_cellsplit[r] / total_cs * 100, 2))
            for r in sorted(clicks_by_cellsplit)[:11]
        ],
        "clicks_no_rank_assigned": {
            "standard": clicks_no_rank_standard,
            "cellsplit": clicks_no_rank_cellsplit,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # Key Claims values for nb25 paste
    kc = {
        "K-cellsplit-comp-1-modal-n-cells": summary["modal_n_cells"],
        "K-cellsplit-comp-2-n-trials-with-carousel": n_trials_with_dd_top,
        "K-cellsplit-comp-3-cells-per-carousel-dist": dict(cells_per_carousel),
        "K-cellsplit-comp-4-n-clicks-on-carousel-cellsplit": n_dd_top_clicks_cellsplit,
        "K-cellsplit-comp-5-abs-standard-peak": summary["abs_standard_peak"],
        "K-cellsplit-comp-6-abs-cellsplit-peak": summary["abs_cellsplit_peak"],
    }
    (OUT_DIR / "key_claims_summary.json").write_text(json.dumps(kc, indent=2))

    # ── Console digest ───────────────────────────────────────────────────
    print()
    print("CELLS-PER-CAROUSEL distribution:")
    for n in sorted(cells_per_carousel):
        c = cells_per_carousel[n]
        print(f"  {n} cells:  {c:5d} trials  ({c/n_trials_with_dd_top*100:5.1f}%)")
    print(f"  modal: {summary['modal_n_cells']} cells")
    print()
    print(f"{'rank':>4}  {'abs_std':>10}  {'%':>6}  | "
          f"{'abs_cellsplit':>14}  {'%':>6}")
    all_ranks = sorted(set(clicks_by_standard) | set(clicks_by_cellsplit))
    for r in all_ranks[:14]:
        n_std = clicks_by_standard.get(r, 0)
        n_cs = clicks_by_cellsplit.get(r, 0)
        print(f"{r:>4}  {n_std:>10d}  {n_std/total_std*100:5.2f}%  | "
              f"{n_cs:>14d}  {n_cs/total_cs*100:5.2f}%")
    print()
    print(f"abs_standard peak: rank {pk_std_rank} = {pk_std_n} clicks "
          f"({pk_std_n/total_std*100:.2f}%)")
    print(f"abs_cellsplit peak: rank {pk_cs_rank} = {pk_cs_n} clicks "
          f"({pk_cs_n/total_cs*100:.2f}%)")
    print(f"[done] outputs at {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
