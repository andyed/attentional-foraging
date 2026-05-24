"""Per-participant dd_top cell-level engagement segmentation.

Question: does resolving dd_top engagement at the cell level (vs the
parent-bbox level p_dd_top_click currently uses) reveal user segments
that the binary "did they click an ad" signal collapses?

Hypothesis: two participants with the same p_dd_top_click can have very
different cell-engagement signatures — one samples multiple cells before
clicking (deliberative carousel-shopper); another clicks the first cell
without looking at the rest (first-cell-impulsive). The cell sub-bbox
data (~/scripts/output/cascade-baseline/aoi-snapshot-v1/) makes the
distinction observable.

Computes per participant, over trials with a dd_top carousel:
  - n_dd_top_trials          : denominator
  - mean_cells_per_carousel  : trial-mean of cell count in the carousel
  - any_cell_engagement_rate : fraction of trials with >= 1 cell touched
                               (cursor episode dwell >= 100ms inside cell)
  - cell_promiscuity_rate    : fraction with >= 2 cells touched
  - mean_n_touched_when_engaged : trial-mean of n_touched | n_touched >= 1
  - p_carousel_click         : fraction with >= 1 cell click
  - mean_touched_fraction    : trial-mean of (n_touched / n_cells)

Plus split-half reliability per metric and Spearman correlations
against ad-utility-prior axes (p_ad_survey, p_dd_top_click,
regression_rate, mean_lhipa).

Output:
  scripts/output/dd_top_cell_segmentation/summary.json
  scripts/output/dd_top_cell_segmentation/per_participant.csv

Run:
    .venv/bin/python scripts/dd_top_cell_segmentation.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_mouse_events, get_trial_ids  # noqa: E402
from probe_cellsplit_features import load_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/dd_top_cell_segmentation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRIOR_CSV = ROOT / "scripts/output/ad_utility_prior/per_participant.csv"

DWELL_THRESHOLD_MS = 100  # matches build_replay_trial.derive_aoi_labels heuristic


def cell_episodes_touched(events: list[tuple], cell: dict) -> tuple[int, bool]:
    """Walk cursor + click stream against one cell bbox. Returns
    (n_episodes_with_dwell_above_threshold, any_click_inside_cell).
    """
    x0, y0 = cell["x"], cell["y"]
    x1, y1 = x0 + cell["w"], y0 + cell["h"]
    n_episodes = 0
    any_click = False
    inside = False
    enter_t: int | None = None
    for t, evt, x, y in events:
        if evt not in ("mousemove", "click", "mouseover"):
            continue
        in_now = x0 <= x <= x1 and y0 <= y <= y1
        if evt == "click" and in_now:
            any_click = True
        if in_now and not inside:
            enter_t = t
            inside = True
        elif inside and not in_now:
            dwell = t - (enter_t if enter_t is not None else t)
            if dwell >= DWELL_THRESHOLD_MS:
                n_episodes += 1
            inside = False
            enter_t = None
    if inside and enter_t is not None:
        # close the trailing episode at the last event time
        last_t = events[-1][0]
        if (last_t - enter_t) >= DWELL_THRESHOLD_MS:
            n_episodes += 1
    return n_episodes, any_click


def analyze_trial(trial_id: str) -> dict | None:
    """Returns per-trial cell-engagement record, or None if trial has
    no dd_top cells or no usable cursor data."""
    try:
        aois = load_aois(trial_id, midpoint_split=True)
    except FileNotFoundError:
        return None
    cells = [a for a in aois if a["kind"] == "dd_top_cell"]
    if not cells:
        return None
    mouse_data = load_mouse_events(trial_id)
    if not mouse_data:
        return None
    all_events, _scrolls, _clicks = mouse_data
    if len(all_events) < 2:
        return None
    n_touched = 0
    n_clicked = 0
    for c in cells:
        eps, clicked = cell_episodes_touched(all_events, c)
        if eps >= 1:
            n_touched += 1
        if clicked:
            n_clicked += 1
    return {
        "trial_id": trial_id,
        "participant": trial_id.split("-", 1)[0],
        "n_cells": len(cells),
        "n_touched": n_touched,
        "n_clicked": n_clicked,
    }


def aggregate_participant(records: list[dict]) -> dict:
    """Per-participant metrics from a list of per-trial records.
    All trials in `records` have a dd_top carousel by construction."""
    n = len(records)
    n_cells = np.array([r["n_cells"] for r in records])
    n_touched = np.array([r["n_touched"] for r in records])
    n_clicked = np.array([r["n_clicked"] for r in records])
    engaged_mask = n_touched >= 1
    return {
        "n_dd_top_trials": int(n),
        "mean_cells_per_carousel": float(n_cells.mean()),
        "any_cell_engagement_rate": float(engaged_mask.mean()),
        "cell_promiscuity_rate": float((n_touched >= 2).mean()),
        "mean_n_touched_when_engaged": (
            float(n_touched[engaged_mask].mean()) if engaged_mask.any() else 0.0
        ),
        "p_carousel_click": float((n_clicked >= 1).mean()),
        "mean_touched_fraction": float((n_touched / n_cells).mean()),
    }


def split_half_reliability(by_participant: dict, metric: str,
                           records_by_pid: dict, seed: int = 0) -> dict:
    """Random-split each participant's trials in half, recompute the
    metric on each half, then correlate across participants."""
    rng = np.random.default_rng(seed)
    halves_a, halves_b, pids = [], [], []
    for pid, recs in records_by_pid.items():
        if len(recs) < 4:
            continue  # not enough trials to split meaningfully
        idx = np.arange(len(recs))
        rng.shuffle(idx)
        half = len(idx) // 2
        a_records = [recs[i] for i in idx[:half]]
        b_records = [recs[i] for i in idx[half:half * 2]]
        a_metrics = aggregate_participant(a_records)
        b_metrics = aggregate_participant(b_records)
        halves_a.append(a_metrics[metric])
        halves_b.append(b_metrics[metric])
        pids.append(pid)
    if len(halves_a) < 4:
        return {"r": None, "n": len(halves_a)}
    r, p = spearmanr(halves_a, halves_b)
    # Spearman-Brown correction to double-length
    sb = (2 * r) / (1 + r) if (1 + r) != 0 else None
    return {
        "r_split_half": round(float(r), 4),
        "r_spearman_brown": round(float(sb), 4) if sb is not None else None,
        "p": round(float(p), 4),
        "n_participants": len(halves_a),
    }


def load_prior_axes() -> dict[str, dict]:
    """Returns {pid: {p_ad_survey, p_dd_top_click, regression_rate, mean_lhipa, ...}}"""
    out = {}
    with PRIOR_CSV.open() as f:
        for row in csv.DictReader(f):
            out[row["participant"]] = {
                k: (float(v) if v else None)
                for k, v in row.items() if k != "participant" and k != "tercile"
            }
            out[row["participant"]]["tercile"] = row.get("tercile")
    return out


def main() -> int:
    print(f"[1/4] iterating trials...")
    trial_ids = get_trial_ids()
    print(f"  {len(trial_ids)} total trial IDs in AdSERP corpus")
    per_trial_records = []
    for i, tid in enumerate(trial_ids):
        rec = analyze_trial(tid)
        if rec is not None:
            per_trial_records.append(rec)
        if (i + 1) % 500 == 0:
            print(f"    processed {i+1}/{len(trial_ids)} "
                  f"({len(per_trial_records)} kept w/ dd_top cells + cursor)")
    print(f"  {len(per_trial_records)} trials retained "
          f"(have dd_top cells + usable cursor)")

    print(f"[2/4] aggregating per participant...")
    by_pid = defaultdict(list)
    for r in per_trial_records:
        by_pid[r["participant"]].append(r)
    per_part = {pid: aggregate_participant(recs) for pid, recs in by_pid.items()}
    print(f"  {len(per_part)} participants with >= 1 dd_top trial")

    # Coverage filter for downstream stats: need >= 8 dd_top trials for
    # meaningful split-half and per-participant rate estimation.
    eligible = {pid: m for pid, m in per_part.items()
                if m["n_dd_top_trials"] >= 8}
    print(f"  {len(eligible)} eligible (n_dd_top_trials >= 8) for stats")

    print(f"[3/4] split-half reliability per metric...")
    metrics_to_test = [
        "any_cell_engagement_rate",
        "cell_promiscuity_rate",
        "mean_n_touched_when_engaged",
        "p_carousel_click",
        "mean_touched_fraction",
    ]
    reliability = {}
    for m in metrics_to_test:
        eligible_records = {pid: by_pid[pid] for pid in eligible.keys()}
        reliability[m] = split_half_reliability(per_part, m, eligible_records)
        print(f"  {m}: r={reliability[m].get('r_split_half')}, "
              f"SB={reliability[m].get('r_spearman_brown')}, "
              f"n={reliability[m].get('n_participants')}")

    print(f"[4/4] correlation vs ad-utility-prior axes...")
    prior = load_prior_axes()
    overlap = sorted(set(eligible.keys()) & set(prior.keys()))
    print(f"  {len(overlap)} participants overlap with ad_utility_prior cohort")
    axes_to_compare = ["p_ad_survey", "p_dd_top_click", "p_ad_click",
                       "regression_rate", "mean_lhipa", "ad_over_index"]
    correlations = {}
    for m in metrics_to_test:
        correlations[m] = {}
        cell_vals = np.array([eligible[pid][m] for pid in overlap])
        for axis in axes_to_compare:
            prior_vals = np.array([prior[pid].get(axis) or np.nan for pid in overlap])
            mask = ~np.isnan(prior_vals)
            if mask.sum() < 4:
                continue
            r, p = spearmanr(cell_vals[mask], prior_vals[mask])
            correlations[m][axis] = {
                "spearman_r": round(float(r), 4),
                "p": round(float(p), 4),
                "n": int(mask.sum()),
            }
    for m in metrics_to_test:
        print(f"  {m}:")
        for axis, stat in correlations[m].items():
            sig = " *" if stat["p"] < 0.05 else ""
            print(f"    × {axis:20s} ρ={stat['spearman_r']:+.3f} p={stat['p']:.3f} n={stat['n']}{sig}")

    summary = {
        "n_trial_ids_total": len(trial_ids),
        "n_trials_with_dd_top_cells_and_cursor": len(per_trial_records),
        "n_participants_any_dd_top": len(per_part),
        "n_participants_eligible_for_stats": len(eligible),
        "n_overlap_with_prior_cohort": len(overlap),
        "dwell_threshold_ms": DWELL_THRESHOLD_MS,
        "metrics_definitions": {
            "any_cell_engagement_rate": "fraction of dd_top trials with >=1 cell touched (cursor episode dwell >= 100ms)",
            "cell_promiscuity_rate": "fraction with >=2 cells touched",
            "mean_n_touched_when_engaged": "mean n_touched conditional on n_touched >= 1",
            "p_carousel_click": "fraction with >=1 cell click",
            "mean_touched_fraction": "mean (n_touched / n_cells) across dd_top trials",
        },
        "reliability": reliability,
        "correlations": correlations,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # per_participant.csv
    with (OUT_DIR / "per_participant.csv").open("w") as f:
        keys = ["participant"] + list(next(iter(per_part.values())).keys())
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for pid in sorted(per_part.keys()):
            w.writerow({"participant": pid, **per_part[pid]})

    print(f"\nWrote {OUT_DIR}/summary.json and per_participant.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
