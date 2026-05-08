"""F-explainer visual — non-academic decomposition of the F-pattern.

For andyed.github.io/attentional-foraging/explainer/ and the LinkedIn post.
Story: the F-pattern's vertical fade is a headcount effect, not a reading
effect. Built from the AdSERP decomposition computed by make_f_scan_farce.py.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "output" / "f_scan_farce" / "summary.json"
OUT = ROOT / "scripts" / "output" / "f_explainer"
OUT.mkdir(parents=True, exist_ok=True)

with open(SRC) as f:
    data = json.load(f)

# Use the count × duration story; fall back to v1 numbers if v2 keys missing.
ranks = np.array(data["ranks"])
if "n_visits" in data:
    counts = np.array(data["n_visits"])
    per_visit_ms = np.array(data["mean_dwell_per_visit_ms"])
    total_s = np.array(data["total_dwell_ms"]) / 1000.0
else:
    counts = np.array(data["forward_visit_count"])
    per_visit_ms = np.array(data["mean_dwell_per_forward_visit_ms"])
    total_s = np.array(data["forward_total_s"])

CREAM = "#FAFAF8"
INK = "#1A1A1A"
MUTED = "#4B4B4B"
PURPLE = "#5B3EB8"
ORANGE = "#B8722C"
GRAY = "#A8A8A8"

plt.rcParams.update({
    "font.family": "Georgia",
    "font.size": 12,
    "axes.facecolor": CREAM,
    "figure.facecolor": CREAM,
    "savefig.facecolor": CREAM,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
})

fig = plt.figure(figsize=(15, 8.5), facecolor=CREAM)

# Title block
fig.text(
    0.5, 0.96,
    "The F-pattern is a headcount effect, not a reading effect.",
    ha="center", va="top", fontsize=22, fontweight="bold", color=INK,
)
fig.text(
    0.5, 0.915,
    "AdSERP eye-tracking, n = 2,775 search sessions. What the heatmap pools, decomposed.",
    ha="center", va="top", fontsize=12, color=MUTED, style="italic",
)

# Three panels in a row
gs = fig.add_gridspec(
    1, 3, left=0.06, right=0.97, top=0.78, bottom=0.22,
    wspace=0.42,
)

# Panel A — the F (total pooled time)
axA = fig.add_subplot(gs[0, 0])
axA.barh(ranks, total_s / total_s.max(), color=GRAY, alpha=0.85, edgecolor="white", linewidth=0.6)
axA.invert_yaxis()
axA.set_yticks(ranks)
axA.set_yticklabels([f"#{r+1}" for r in ranks])
axA.set_xticks([])
axA.set_title("What the heatmap shows\n(total time pooled across users)",
              fontsize=13, color=INK, pad=12)
axA.set_xlabel("shorter  ........  longer", fontsize=10, color=MUTED)
axA.spines[["top", "right", "bottom"]].set_visible(False)
axA.set_xlim(0, 1.05)
for r, v in zip(ranks, total_s):
    axA.text(v / total_s.max() + 0.02, r, "", va="center", fontsize=10, color=MUTED)

# Panel B — count of people
axB = fig.add_subplot(gs[0, 1])
axB.barh(ranks, counts, color=PURPLE, alpha=0.9, edgecolor="white", linewidth=0.6)
axB.invert_yaxis()
axB.set_yticks(ranks)
axB.set_yticklabels([f"#{r+1}" for r in ranks])
axB.set_title("How many people get there\n(forward visits per result)",
              fontsize=13, color=PURPLE, pad=12)
axB.set_xlabel("number of users", fontsize=10, color=MUTED)
axB.spines[["top", "right"]].set_visible(False)
axB.grid(axis="x", linestyle=":", alpha=0.35)
for r, v in zip(ranks, counts):
    axB.text(v + counts.max() * 0.02, r, f"{int(v):,}", va="center", fontsize=10, color=MUTED)
axB.set_xlim(0, counts.max() * 1.18)

# Panel C — time per look
axC = fig.add_subplot(gs[0, 2])
axC.barh(ranks, per_visit_ms, color=ORANGE, alpha=0.9, edgecolor="white", linewidth=0.6)
axC.invert_yaxis()
axC.set_yticks(ranks)
axC.set_yticklabels([f"#{r+1}" for r in ranks])
axC.set_title("How long each look lasts\n(milliseconds per first-pass visit)",
              fontsize=13, color=ORANGE, pad=12)
axC.set_xlabel("milliseconds per look", fontsize=10, color=MUTED)
axC.spines[["top", "right"]].set_visible(False)
axC.grid(axis="x", linestyle=":", alpha=0.35)
for r, v in zip(ranks, per_visit_ms):
    axC.text(v + per_visit_ms.max() * 0.02, r, f"{int(round(v))} ms",
             va="center", fontsize=10, color=MUTED)
axC.set_xlim(0, per_visit_ms.max() * 1.22)

# Bottom punchline
fig.text(
    0.5, 0.13,
    "Result #1 is read by 2,700 users for ~210 ms each.   Result #9 is read by ~700 users for ~245 ms each.",
    ha="center", va="top", fontsize=13, color=INK,
)
fig.text(
    0.5, 0.085,
    "The shorter \"vertical bar of the F\" isn't users skimming deeper results — it's fewer users reaching them.",
    ha="center", va="top", fontsize=13, color=INK, style="italic", fontweight="bold",
)
fig.text(
    0.5, 0.04,
    "Time per look at result #9 is actually slightly longer than at result #1 (+16%) — the people who scroll that far read more carefully, not less.",
    ha="center", va="top", fontsize=11, color=MUTED,
)

png = OUT / "f_explainer.png"
svg = OUT / "f_explainer.svg"
fig.savefig(png, dpi=200, bbox_inches="tight", facecolor=CREAM)
fig.savefig(svg, bbox_inches="tight", facecolor=CREAM)
print(f"wrote {png}")
print(f"wrote {svg}")
