"""F-scan farce chart, per-visit version (Def A — first-arrival contiguous block).

Honest decomposition: count drops fast (the F), per-visit duration drops
modestly, total drops fast because count drop dominates. Replaces the v1
chart that conflated per-fixation with per-visit.

Per-fixation duration is the metric that *rises* with rank (+0.63 raw ms /
+0.82 ratio). That's a different denominator. This chart sticks to per-visit
to keep the count × duration = total decomposition coherent.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "output" / "f_scan_farce" / "classifier_robustness_organic.json"
OUT = ROOT / "scripts" / "output" / "f_scan_farce"

with open(SRC) as f:
    data = json.load(f)

ranks = np.array(data["ranks"])
defA = data["definitions"]["A_first_arrival"]
counts = np.array(defA["n_visits_per_rank"])
mean_per_visit_ms = np.array(defA["mean_ms_per_visit_per_rank"])
total_dwell_s = counts * mean_per_visit_ms / 1000.0

rho_count, _ = spearmanr(ranks, counts)
rho_pv, _ = spearmanr(ranks, mean_per_visit_ms)
rho_total, _ = spearmanr(ranks, total_dwell_s)
print(f"count    rho={rho_count:+.3f}, range {counts.min():,}–{counts.max():,}")
print(f"per-visit rho={rho_pv:+.3f}, range {mean_per_visit_ms.min():.0f}–{mean_per_visit_ms.max():.0f} ms")
print(f"total    rho={rho_total:+.3f}, range {total_dwell_s.min():.1f}–{total_dwell_s.max():.1f} s")

plt.rcParams.update({
    "font.family": "Georgia",
    "font.size": 11,
    "axes.titlesize": 11.5,
    "axes.labelsize": 10.5,
})
ACCENT = "#5B3EB8"
ACCENT2 = "#B8722C"
GREY = "#4B4B4B"

fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0))

ax = axes[0]
ax.bar(ranks, counts, color=ACCENT, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(f"Forward-visit count per rank\n(ρ = {rho_count:+.2f})  —the F", color=ACCENT)
ax.set_xlabel("organic rank")
ax.set_ylabel("# trials with a forward visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[1]
ax.bar(ranks, mean_per_visit_ms, color=ACCENT2, alpha=0.85, edgecolor="white", linewidth=0.6)
ax.set_title(
    f"Dwell per forward visit (ms)\n(ρ = {rho_pv:+.2f}, p = {spearmanr(ranks, mean_per_visit_ms)[1]:.2f}, n.s.)  —rank-invariant",
    color=ACCENT2,
)
ax.set_xlabel("organic rank")
ax.set_ylabel("mean ms per first-pass visit")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

ax = axes[2]
ax.bar(ranks, total_dwell_s, color=GREY, alpha=0.7, edgecolor="white", linewidth=0.6)
ax.set_title(
    f"Total forward dwell pooled (s)\n(ρ = {rho_total:+.2f})  —what marginals show",
    color=GREY,
)
ax.set_xlabel("organic rank")
ax.set_ylabel("total seconds, all trials")
ax.set_xticks(ranks)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", linestyle=":", alpha=0.4)

count_pct_drop = (1 - counts[-1] / counts[0]) * 100
fig.suptitle(
    f"Bbox-organic: count drops {count_pct_drop:.0f}%, per-visit duration is flat (n.s.); "
    "the F is count-driven, per-visit effort is rank-invariant.",
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
