"""F-scan path farce v2 — total dwell decomposed into forward + regression per rank.

Adds a fourth panel: total pooled dwell at each rank, stacked into
forward-pass and regression-return contributions. Shows that the F-shape in
the marginal isn't only count-driven; regression mass concentrates at top
ranks too.
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
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
print(f'[attribution] {_args.attribution}', file=sys.stderr)

OUT = ROOT / "scripts" / "output" / "f_scan_farce"
OUT.mkdir(parents=True, exist_ok=True)

MAX_RANK = 8

forward_dur = {r: 0.0 for r in range(MAX_RANK + 1)}
regress_dur = {r: 0.0 for r in range(MAX_RANK + 1)}
forward_visits = {r: [] for r in range(MAX_RANK + 1)}  # list of first-arrival durations

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
    cur_pos = None
    cur_visit_dur = 0.0
    cur_visit_is_first_arrival = False

    def flush_visit(visited=visited):
        # nonlocal-ish via closure on the enclosing variables
        pass

    # Walk fixations grouping by consecutive position; bucket each visit's
    # total dwell into either first-arrival (forward) or non-first (regression+consolidation).
    for fix in fixations:
        pos = assign_fixation_to_position(fix["y"], tops, n_results)
        if pos is None or pos < 0 or pos > MAX_RANK:
            # close any open visit
            if cur_pos is not None and cur_visit_dur > 0 and 0 <= cur_pos <= MAX_RANK:
                if cur_visit_is_first_arrival:
                    forward_dur[cur_pos] += cur_visit_dur
                    forward_visits[cur_pos].append(cur_visit_dur)
                else:
                    regress_dur[cur_pos] += cur_visit_dur
            cur_pos = None
            cur_visit_dur = 0.0
            cur_visit_is_first_arrival = False
            continue

        if pos != cur_pos:
            # flush previous visit
            if cur_pos is not None and cur_visit_dur > 0 and 0 <= cur_pos <= MAX_RANK:
                if cur_visit_is_first_arrival:
                    forward_dur[cur_pos] += cur_visit_dur
                    forward_visits[cur_pos].append(cur_visit_dur)
                else:
                    regress_dur[cur_pos] += cur_visit_dur
            cur_pos = pos
            cur_visit_dur = 0.0
            cur_visit_is_first_arrival = pos not in visited
            visited.add(pos)

        cur_visit_dur += fix["d"]

    # flush trailing
    if cur_pos is not None and cur_visit_dur > 0 and 0 <= cur_pos <= MAX_RANK:
        if cur_visit_is_first_arrival:
            forward_dur[cur_pos] += cur_visit_dur
            forward_visits[cur_pos].append(cur_visit_dur)
        else:
            regress_dur[cur_pos] += cur_visit_dur
    n_used += 1

print(f"used {n_used} trials")

ranks = np.arange(MAX_RANK + 1)
fwd_tot_s = np.array([forward_dur[r] / 1000.0 for r in ranks])
reg_tot_s = np.array([regress_dur[r] / 1000.0 for r in ranks])
total_tot_s = fwd_tot_s + reg_tot_s
visit_counts = np.array([len(forward_visits[r]) for r in ranks])
mean_dwell_per_visit = np.array(
    [np.mean(forward_visits[r]) if forward_visits[r] else 0.0 for r in ranks]
)
reg_share = reg_tot_s / np.maximum(total_tot_s, 1e-9)

rho_count, _ = spearmanr(ranks, visit_counts)
rho_pv, _ = spearmanr(ranks, mean_dwell_per_visit)
rho_total, _ = spearmanr(ranks, total_tot_s)
rho_fwd, _ = spearmanr(ranks, fwd_tot_s)
rho_reg, _ = spearmanr(ranks, reg_tot_s)
rho_share, _ = spearmanr(ranks, reg_share)

print(f"forward count          rho={rho_count:+.2f}")
print(f"dwell per forward visit rho={rho_pv:+.2f}")
print(f"forward total          rho={rho_fwd:+.2f}")
print(f"regression total       rho={rho_reg:+.2f}")
print(f"total                  rho={rho_total:+.2f}")
print(f"regression share       rho={rho_share:+.2f}")
print("regression share by rank:", [f"{x:.2f}" for x in reg_share])
print("forward total seconds:", fwd_tot_s.tolist())
print("regression total seconds:", reg_tot_s.tolist())

plt.rcParams.update({
    "font.family": "Georgia",
    "font.size": 11,
    "axes.titlesize": 11,
    "axes.labelsize": 10.5,
})
ACCENT = "#5B3EB8"
ACCENT2 = "#B8722C"
GREY = "#6E6E6E"
RED = "#A8334F"

fig, axes = plt.subplots(1, 4, figsize=(17, 4.0))

ax = axes[0]
ax.bar(ranks, visit_counts, color=ACCENT, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Forward-visit count\n(ρ = {rho_count:+.2f})  —the F", color=ACCENT)
ax.set_xlabel("organic rank")
ax.set_ylabel("# trials with a forward visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[1]
ax.bar(ranks, mean_dwell_per_visit, color=ACCENT2, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Dwell per forward visit (ms)\n(ρ = {rho_pv:+.2f})  —the reversal", color=ACCENT2)
ax.set_xlabel("organic rank")
ax.set_ylabel("mean ms per first-pass visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[2]
ax.bar(ranks, fwd_tot_s, color=ACCENT, alpha=0.85, edgecolor="white", linewidth=0.6, label="forward")
ax.bar(ranks, reg_tot_s, bottom=fwd_tot_s, color=RED, alpha=0.85, edgecolor="white", linewidth=0.6, label="regression")
ax.set_title(f"Total dwell pooled (s)\nforward ρ = {rho_fwd:+.2f}; regression ρ = {rho_reg:+.2f}", color=GREY)
ax.set_xlabel("organic rank")
ax.set_ylabel("total seconds, all trials")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)
ax.legend(frameon=False, fontsize=9, loc="upper right")

ax = axes[3]
ax.bar(ranks, reg_share * 100, color=RED, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Regression share of total dwell\n(ρ = {rho_share:+.2f})  —top-rank concentration", color=RED)
ax.set_xlabel("organic rank")
ax.set_ylabel("% of total dwell that is regression")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

fig.suptitle(
    "Same data, four views — the F-shape pools forward and regression; per-visit duration goes the other way.",
    fontsize=11.5,
    color=GREY,
    y=1.04,
)
fig.tight_layout()

png = OUT / "f_scan_farce.png"
pdf = OUT / "f_scan_farce.pdf"
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
print(f"wrote {png}")

import json
summary = {
    "n_trials_used": n_used,
    "ranks": ranks.tolist(),
    "forward_total_s": fwd_tot_s.tolist(),
    "regression_total_s": reg_tot_s.tolist(),
    "total_s": total_tot_s.tolist(),
    "forward_visit_count": visit_counts.tolist(),
    "mean_dwell_per_forward_visit_ms": mean_dwell_per_visit.tolist(),
    "regression_share": reg_share.tolist(),
    "spearman": {
        "forward_count": float(rho_count),
        "dwell_per_forward_visit": float(rho_pv),
        "forward_total": float(rho_fwd),
        "regression_total": float(rho_reg),
        "total": float(rho_total),
        "regression_share": float(rho_share),
    },
}
with open(OUT / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)
