"""Render the pre-foveation PAI probe figure (ETRA short paper / CHI poster).

One horizontal dot plot, three rows:
  1. Traditional point-in-AOI metric — pinned at 50% (= chance) BY
     CONSTRUCTION: every candidate has zero dwell in the shared window.
  2. Next-foveated, non-clicked control (probe C) — foveation anticipation.
  3. To-be-clicked result (probe B) — with the click-specific bracket
     against row 2.

Filled markers = exact delivered-demo alpha; open markers = NB35
abstract-only form. All values read from
scripts/output/ablations/pai_preentry_probe.json — never re-typed.

Output:
  scripts/output/ablations/pai_preentry_figure.{pdf,png}

Run:
  .venv/bin/python scripts/render_pai_preentry_figure.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
SRC = ROOT / "scripts/output/ablations/pai_preentry_probe.json"
OUT_DIR = ROOT / "scripts/output/ablations"

# muriel light palette — paper submission target. Text ink must hold
# 8:1 on white; INK does (~16:1). CYAN/GRAY are mark colors only.
INK = "#1a1a2e"
CYAN = "#2a7f93"    # darkened from #50b4c8 so the value labels beside
                    # marks stay ink-colored; the mark itself is fill only
GRAY = "#8a8aa0"    # decorative lines only, never text

plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 14, "axes.labelsize": 14, "xtick.labelsize": 12,
    "ytick.labelsize": 13,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False,
})


def main():
    d = json.loads(SRC.read_text())
    b = d["probe_b_shared_cutoff"]
    c = d["probe_c_specificity_control"]

    exact_click = b["exact"]["mean_score"] * 100
    exact_click_ci = [x * 100 for x in b["exact"]["ci_95"]]
    nb35_click = b["nb35"]["mean_score"] * 100
    exact_ctrl = c["exact"]["control_mean_score"] * 100
    nb35_ctrl = c["nb35"]["control_mean_score"] * 100
    delta = c["exact"]["mean_b_minus_c"] * 100
    delta_ci = [x * 100 for x in c["exact"]["ci_95"]]
    n_b = b["exact"]["n_trials"]
    med_peers = int(b["median_peers"])

    fig, ax = plt.subplots(figsize=(11, 4.6))

    rows = [
        ("Traditional point-in-AOI dwell\n(zero for every candidate)", 2),
        ("Next-foveated, non-clicked\n(anticipation control)", 1),
        ("To-be-clicked result", 0),
    ]
    y_trad, y_ctrl, y_clk = 2, 1, 0

    # Chance line = the traditional metric's structural floor.
    ax.axvline(50, color=GRAY, linestyle="--", linewidth=1.4, zorder=1)

    # Row 1: traditional metric — a mark ON the line, no CI (not an
    # estimate; an identity).
    ax.plot([50], [y_trad], marker="s", markersize=11, color="white",
            markeredgecolor=INK, markeredgewidth=2, zorder=5)
    ax.annotate("50.0%  exactly — chance, by construction", (50, y_trad),
                xytext=(52.2, y_trad), va="center", fontsize=13, color=INK)

    # Rows 2-3: stems from chance + filled (exact) and open (NB35) marks.
    for y, val_e, val_n in ((y_ctrl, exact_ctrl, nb35_ctrl),
                            (y_clk, exact_click, nb35_click)):
        ax.plot([50, val_e], [y, y], color=CYAN, linewidth=2.4, zorder=2)
        ax.plot([val_n], [y], marker="o", markersize=10, color="white",
                markeredgecolor=CYAN, markeredgewidth=2, zorder=4)
        ax.plot([val_e], [y], marker="o", markersize=11, color=CYAN,
                markeredgecolor=INK, markeredgewidth=1.2, zorder=5)

    # 95% CI whisker on the headline (clicked, exact) — bootstrap CI.
    ax.plot(exact_click_ci, [y_clk, y_clk], color=INK, linewidth=1.6,
            zorder=6)
    for xci in exact_click_ci:
        ax.plot([xci, xci], [y_clk - 0.07, y_clk + 0.07], color=INK,
                linewidth=1.6, zorder=6)

    ax.annotate(f"{exact_ctrl:.1f}%", (exact_ctrl, y_ctrl),
                xytext=(exact_ctrl - 0.4, y_ctrl + 0.32), ha="right",
                fontsize=14, fontweight="bold", color=INK)
    ax.annotate(f"{exact_click:.1f}%", (exact_click, y_clk),
                xytext=(exact_click - 0.6, y_clk - 0.42), ha="right",
                fontsize=14, fontweight="bold", color=INK)

    # Click-specific bracket between control and clicked rows.
    bx0, bx1 = exact_ctrl, exact_click
    by = 0.5
    ax.plot([bx0, bx0, bx1, bx1], [y_ctrl - 0.18, by, by, y_clk + 0.18],
            color=INK, linewidth=1.3, zorder=3)
    ax.annotate(
        f"click-specific  +{delta:.1f} pts\n"
        f"95% CI [+{delta_ci[0]:.1f}, +{delta_ci[1]:.1f}],  p < 10⁻³⁵",
        (bx0, by), xytext=(bx0 - 1.4, by), ha="right",
        va="center", fontsize=13, color=INK)

    ax.set_yticks([y for _, y in rows])
    ax.set_yticklabels([lbl for lbl, _ in rows])
    ax.set_ylim(-0.65, 2.55)
    ax.set_xlim(45, 100)
    ax.set_xlabel("% of still-unfixated peer results ranked below it "
                  "(peripheral PAI mass, at the instant before its first fixation)")
    ax.set_title("Before a result is ever foveated, peripheral PAI already ranks it",
                 fontsize=16, fontweight="bold", loc="left", pad=14)

    # Legend line (text, not a legend box): mark key + n.
    ax.annotate(
        f"filled marks: exact demo α      open marks: NB35 boundary form      "
        f"whisker: bootstrap 95% CI      n = {n_b:,} trials, "
        f"median {med_peers} peers",
        (0, 0), xycoords="axes fraction", xytext=(0.0, -0.30),
        textcoords="axes fraction", fontsize=12, color=INK)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        p = OUT_DIR / f"pai_preentry_figure.{ext}"
        fig.savefig(p)
        print(f"wrote {p}")

    # Contrast audit: ink on white.
    def lum(hex_c):
        r, g, b_ = (int(hex_c[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b_)
    ratio = (1.0 + 0.05) / (lum(INK) + 0.05)
    print(f"text contrast {INK} on white: {ratio:.1f}:1 (floor 8:1)")


if __name__ == "__main__":
    main()
