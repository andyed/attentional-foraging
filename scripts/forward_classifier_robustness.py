"""Robustness check — per-visit dwell-by-rank under multiple forward definitions.

Three definitions tested:
  A  first-arrival      forward = first contiguous block of fixations at a pos
  B  HWM (pos≥hw)       forward = pos ≥ high-water-mark; consolidations included
  C  HWM-strict-visits  same as B but a "visit" closes whenever pos changes,
                        so re-arrivals at HWM after a regression are new visits
  D  EvR first_pass     pre-computed canonical first_pass list from
                        encoding-vs-retrieval.json (one entry per fixation)

Output: per-rank N visits, mean ms per visit, Spearman ρ vs rank for each
definition. Goal: show that the qualitative shape of per-visit dwell across
rank doesn't depend on the definition tweak.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_fixations,
    get_trial_meta,
    count_results_html,
    result_band_tops,
    assign_fixation_to_position,
    organic_aoi_tops,
)

import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument('--attribution', choices=['absolute', 'organic'], default='organic',
                 help='organic (default; bbox-attributed) or absolute (legacy)')
_args = _ap.parse_args()
_OUT_SUFFIX = '_organic' if _args.attribution == 'organic' else ''
print(f'[attribution] {_args.attribution}')

EVR_PATH = ROOT / "AdSERP" / "data" / "encoding-vs-retrieval.json"
OUT = ROOT / "scripts" / "output" / "f_scan_farce"
OUT.mkdir(parents=True, exist_ok=True)
MAX_RANK = 8

defs = ["A_first_arrival", "B_hwm_visit", "C_hwm_strict_visit", "D_evr_first_pass"]
visits = {d: {r: [] for r in range(MAX_RANK + 1)} for d in defs}

# ---------- Definitions A / B / C from raw fixations ----------
trial_ids = get_trial_ids()
n_used = 0
for tid in trial_ids:
    fixations = load_fixations(tid)
    if not fixations:
        continue
    doc_h, _scr_h, _ts = get_trial_meta(tid)
    if doc_h is None:
        continue
    if _args.attribution == 'organic':
        tops = organic_aoi_tops(tid)
        n_results = len(tops)
        if n_results == 0:
            continue
    else:
        n_results = count_results_html(tid) or 11
        tops = result_band_tops(n_results, doc_h)

    visited = set()
    high_water = -1

    # Tracker state per definition (cur_pos, cur_dur, accept flag)
    state_a = {"pos": None, "dur": 0.0, "fwd": False}
    state_b = {"pos": None, "dur": 0.0, "fwd": False}
    state_c = {"pos": None, "dur": 0.0, "fwd": False}

    def flush(state, defname):
        if state["pos"] is None or state["dur"] <= 0:
            return
        if 0 <= state["pos"] <= MAX_RANK and state["fwd"]:
            visits[defname][state["pos"]].append(state["dur"])
        state["pos"] = None
        state["dur"] = 0.0
        state["fwd"] = False

    for fix in fixations:
        pos = assign_fixation_to_position(fix["y"], tops, n_results)
        if pos is None or pos < 0 or pos > MAX_RANK:
            for st, dn in ((state_a, "A_first_arrival"),
                           (state_b, "B_hwm_visit"),
                           (state_c, "C_hwm_strict_visit")):
                flush(st, dn)
            continue

        is_first_arrival = pos not in visited
        is_hwm = pos >= high_water

        # Definition A: first-arrival
        if pos != state_a["pos"]:
            flush(state_a, "A_first_arrival")
            state_a["pos"] = pos
            state_a["fwd"] = is_first_arrival
        state_a["dur"] += fix["d"]

        # Definition B: HWM, visit boundary on pos change
        if pos != state_b["pos"]:
            flush(state_b, "B_hwm_visit")
            state_b["pos"] = pos
            state_b["fwd"] = is_hwm
        else:
            # consolidation while at hwm — keep cur fwd flag
            pass
        state_b["dur"] += fix["d"]

        # Definition C: HWM, but a new "visit" begins every time pos changes
        # (same boundary rule as B; the difference is conceptual — re-arrivals
        # at HWM after intervening regression count separately).
        if pos != state_c["pos"]:
            flush(state_c, "C_hwm_strict_visit")
            state_c["pos"] = pos
            state_c["fwd"] = is_hwm
        state_c["dur"] += fix["d"]

        if is_hwm:
            high_water = pos
        visited.add(pos)

    for st, dn in ((state_a, "A_first_arrival"),
                   (state_b, "B_hwm_visit"),
                   (state_c, "C_hwm_strict_visit")):
        flush(st, dn)
    n_used += 1

# ---------- Definition D: encoding-vs-retrieval first_pass ----------
with open(EVR_PATH) as f:
    evr = json.load(f)

for trial in evr.values():
    fps = trial.get("first_pass", [])
    cur_pos, cur_dur = None, 0.0
    for fp in fps:
        pos = fp.get("pos")
        d = fp.get("duration_ms")
        if pos is None or d is None:
            continue
        if pos != cur_pos:
            if cur_pos is not None and 0 <= cur_pos <= MAX_RANK and cur_dur > 0:
                visits["D_evr_first_pass"][cur_pos].append(cur_dur)
            cur_pos = pos
            cur_dur = 0.0
        cur_dur += float(d)
    if cur_pos is not None and 0 <= cur_pos <= MAX_RANK and cur_dur > 0:
        visits["D_evr_first_pass"][cur_pos].append(cur_dur)

# ---------- Report ----------
ranks = np.arange(MAX_RANK + 1)
print(f"trials processed (raw-fixation defs A/B/C): {n_used}")
print()
header = (
    f"{'rank':>4} | "
    + " | ".join(f"{d:>22}" for d in ["A_first_arrival", "B_hwm_visit", "C_hwm_strict", "D_evr_first_pass"])
)
print(header)
print("-" * len(header))
for r in ranks:
    row = [f"{r:>4} |"]
    for d in defs:
        v = visits[d][r]
        n = len(v)
        m = np.mean(v) if v else 0
        row.append(f" n={n:>5} mean={m:>6.1f}ms |")
    print(" ".join(row))

print()
print("Spearman ρ — mean per-visit dwell vs rank:")
for d in defs:
    means = np.array([np.mean(visits[d][r]) if visits[d][r] else 0.0 for r in ranks])
    rho, p = spearmanr(ranks, means)
    print(f"  {d:>22}: ρ = {rho:+.3f}  p = {p:.2e}  range = [{means.min():.0f}, {means.max():.0f}] ms")

print()
print("Spearman ρ — visit count vs rank:")
for d in defs:
    counts = np.array([len(visits[d][r]) for r in ranks])
    rho, p = spearmanr(ranks, counts)
    print(f"  {d:>22}: ρ = {rho:+.3f}  N(rank0)={counts[0]:,}  N(rank{MAX_RANK})={counts[-1]:,}")

# ---------- Save summary ----------
out = {
    "n_trials": n_used,
    "ranks": ranks.tolist(),
    "definitions": {
        d: {
            "n_visits_per_rank": [len(visits[d][r]) for r in ranks],
            "mean_ms_per_visit_per_rank": [
                float(np.mean(visits[d][r])) if visits[d][r] else 0.0 for r in ranks
            ],
        }
        for d in defs
    },
}
out_path = OUT / f"classifier_robustness{_OUT_SUFFIX}.json"
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
print(f"\nwrote {out_path}")
