"""F-scan path farce in real units.

Decomposes per-rank gaze behaviour into:
  (a) forward-visit count per rank — drops fast with rank (the F)
  (b) forward dwell *per visit* (ms) — rises with rank (the reversal)
  (c) total forward dwell pooled — falls with rank (count drop dominates)

A 'visit' is a contiguous run of forward-pass fixations at the same position
in the encoding-vs-retrieval first_pass sequence.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "AdSERP" / "data" / "encoding-vs-retrieval.json"
OUT = ROOT / "scripts" / "output" / "f_scan_farce"
OUT.mkdir(parents=True, exist_ok=True)

with open(SRC) as f:
    data = json.load(f)

MAX_RANK = 8  # match the +0.82 test (positions 0..8)

visits_by_rank = {r: [] for r in range(MAX_RANK + 1)}

for trial_id, trial in data.items():
    fps = trial.get("first_pass", [])
    if not fps:
        continue
    cur_pos, cur_dur, cur_fixn = None, 0.0, 0
    for fp in fps:
        pos = fp.get("pos")
        d = fp.get("duration_ms")
        if pos is None or d is None:
            continue
        if pos != cur_pos:
            if cur_pos is not None and 0 <= cur_pos <= MAX_RANK:
                visits_by_rank[cur_pos].append((cur_dur, cur_fixn))
            cur_pos, cur_dur, cur_fixn = pos, float(d), 1
        else:
            cur_dur += float(d)
            cur_fixn += 1
    if cur_pos is not None and 0 <= cur_pos <= MAX_RANK:
        visits_by_rank[cur_pos].append((cur_dur, cur_fixn))

ranks = np.arange(MAX_RANK + 1)
n_visits = np.array([len(visits_by_rank[r]) for r in ranks])
mean_dwell_per_visit = np.array(
    [np.mean([d for d, _ in visits_by_rank[r]]) if visits_by_rank[r] else 0 for r in ranks]
)
total_dwell = np.array(
    [sum(d for d, _ in visits_by_rank[r]) for r in ranks]
)
mean_fixn_per_visit = np.array(
    [np.mean([n for _, n in visits_by_rank[r]]) if visits_by_rank[r] else 0 for r in ranks]
)

rho_count, p_count = spearmanr(ranks, n_visits)
rho_per_visit, p_per_visit = spearmanr(ranks, mean_dwell_per_visit)
rho_total, p_total = spearmanr(ranks, total_dwell)
rho_fixn, p_fixn = spearmanr(ranks, mean_fixn_per_visit)

print(f"forward-visit count per rank:        rho={rho_count:+.3f} p={p_count:.2e}")
print(f"mean dwell per forward visit (ms):   rho={rho_per_visit:+.3f} p={p_per_visit:.2e}")
print(f"total forward dwell pooled (s):      rho={rho_total:+.3f} p={p_total:.2e}")
print(f"mean fixations per visit:            rho={rho_fixn:+.3f} p={p_fixn:.2e}")

# --- Figure ---
plt.rcParams.update({
    "font.family": "Georgia",
    "font.size": 11,
    "axes.titlesize": 11.5,
    "axes.labelsize": 10.5,
})
ACCENT = "#5B3EB8"
ACCENT2 = "#B8722C"
MUTED = "#4B4B4B"

fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0))

ax = axes[0]
ax.bar(ranks, n_visits, color=ACCENT, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Forward-visit count per rank\n(ρ = {rho_count:+.2f})  —the F", color=ACCENT)
ax.set_xlabel("organic rank")
ax.set_ylabel("# trials with a forward visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[1]
ax.bar(ranks, mean_dwell_per_visit, color=ACCENT2, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Dwell per forward visit (ms)\n(ρ = {rho_per_visit:+.2f})  —the reversal", color=ACCENT2)
ax.set_xlabel("organic rank")
ax.set_ylabel("mean ms per first-pass visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[2]
ax.bar(ranks, total_dwell / 1000.0, color=MUTED, alpha=0.7, edgecolor="white", linewidth=0.6)
ax.set_title(f"Total forward dwell pooled (s)\n(ρ = {rho_total:+.2f})  —what marginals show", color=MUTED)
ax.set_xlabel("organic rank")
ax.set_ylabel("total seconds, all trials")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

fig.suptitle(
    "Same data, three views — count × duration = total. Count drops faster than per-visit duration rises.",
    fontsize=11.5,
    color=MUTED,
    y=1.04,
)
fig.tight_layout()

png = OUT / "f_scan_farce.png"
pdf = OUT / "f_scan_farce.pdf"
fig.savefig(png, dpi=200, bbox_inches="tight")
fig.savefig(pdf, bbox_inches="tight")
print(f"wrote {png}")

summary = {
    "n_trials": len(data),
    "ranks": ranks.tolist(),
    "n_visits": n_visits.tolist(),
    "mean_dwell_per_visit_ms": mean_dwell_per_visit.tolist(),
    "total_dwell_ms": total_dwell.tolist(),
    "mean_fixn_per_visit": mean_fixn_per_visit.tolist(),
    "spearman": {
        "n_visits": {"rho": float(rho_count), "p": float(p_count)},
        "mean_dwell_per_visit": {"rho": float(rho_per_visit), "p": float(p_per_visit)},
        "total_dwell": {"rho": float(rho_total), "p": float(p_total)},
        "mean_fixn_per_visit": {"rho": float(rho_fixn), "p": float(p_fixn)},
    },
}
with open(OUT / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)
