"""Two new paper-v3 figures: M1–M4 click-prediction AUC bars and the
NB21 vs M5 vs NB22 label-fidelity comparison.

Uses the light editorial palette from the rest of the figure pipeline.
All numbers are hard-coded from the paper-v3 results tables; they
trace back to:
- scripts/output/m5_cursor_only_taxonomy/summary.json (M5 numbers)
- scripts/output/hard_negative_overlap/overlap.json (NB21/NB22 label agreement)
- notebooks-v2/21_click_prediction.ipynb (M1–M4 LOSO AUC)

Outputs:
  scripts/output/figures/m1_m4_auc_bars.{png,pdf}
  scripts/output/figures/label_fidelity_comparison.{png,pdf}
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

OUT_DIR = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INK = "#1a1a2e"
MUTED = "#5a5a6a"
CANONICAL_GREEN = "#2ca25f"
DEFERRED_ORANGE = "#e08214"
REJECTED_RED = "#b2182b"
REFERENCE_GREY = "#b0b0b0"
BASELINE_BLUE = "#1f4e8c"

mpl.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.titlesize": 12.5,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def render_auc_bars():
    """M1-M4 LOSO AUC bar chart showing the M4 ≈ M3 equivalence on gaze-clean
    hybrid xpath + linear-fallback features (Option D 1-D)."""
    models = ["M1\nposition\nonly", "M2\n+ cursor dwell",
              "M4\napproach only\n(canonical)", "M3\n+position\n(reference)"]
    auc = [0.638, 0.714, 0.821, 0.820]
    err = [0.0, 0.0, 0.0, 0.0]  # SDs not reported on gaze-clean rerun
    colors = [REFERENCE_GREY, BASELINE_BLUE, CANONICAL_GREEN, REFERENCE_GREY]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(models))
    bars = ax.bar(
        x, auc, yerr=err, capsize=6, color=colors,
        edgecolor=INK, linewidth=0.8, alpha=0.95,
        error_kw={"elinewidth": 1.0, "ecolor": INK},
    )

    # Value labels above each bar
    for i, (b, v, e) in enumerate(zip(bars, auc, err)):
        ax.text(
            b.get_x() + b.get_width() / 2, v + 0.012,
            f"{v:.3f}",
            ha="center", va="bottom", fontsize=10.5, fontweight="semibold",
            color=INK,
        )

    # Bracket between M4 and M3 showing equivalence
    y_bracket = 0.92
    ax.plot([2, 3], [y_bracket, y_bracket], color=INK, linewidth=1.2)
    ax.plot([2, 2], [y_bracket - 0.01, y_bracket], color=INK, linewidth=1.2)
    ax.plot([3, 3], [y_bracket - 0.01, y_bracket], color=INK, linewidth=1.2)
    ax.text(
        2.5, y_bracket + 0.012,
        "M4 ≈ M3  (Δ = +0.001)",
        ha="center", va="bottom", fontsize=10, fontweight="semibold",
        color=CANONICAL_GREEN,
    )

    # Reference line at chance
    ax.axhline(0.5, color=MUTED, linewidth=0.6, linestyle="--", alpha=0.6, zorder=1)
    ax.text(
        -0.45, 0.52, "chance",
        fontsize=9, color=MUTED, va="bottom",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylabel("LOSO AUC (47-fold, participant held out)",
                  fontweight="semibold")
    ax.set_ylim(0.45, 1.03)
    ax.set_title(
        "Nine task-aware cursor features match the 10-feature baseline\n"
        "(gaze-clean hybrid xpath + linear-fallback extractor, 99.8% coverage)",
        fontweight="semibold", pad=14, fontsize=12,
    )
    ax.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax.set_axisbelow(True)

    # Narrow the plot footprint
    for spine_name in ("top", "right"):
        ax.spines[spine_name].set_visible(False)

    out_png = OUT_DIR / "m1_m4_auc_bars.png"
    out_pdf = OUT_DIR / "m1_m4_auc_bars.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


def render_label_fidelity():
    """NB21 vs M5 vs NB22 label-fidelity comparison bar chart on gaze-clean
    hybrid features (Option D 1-D). Two panels: (a) disagreement rate vs
    NB22 ground truth, (b) Jaccard."""
    methods = ["NB21\nclick-threshold\n(gaze-clean)", "M5\ncalibrated\n(gaze-clean)",
               "NB22\ngaze-regression\n(LAB ground truth)"]
    disagreement = [43.8, 29.4, 0.0]  # percent
    jaccard = [0.452, 0.652, 1.000]
    colors = [REFERENCE_GREY, CANONICAL_GREEN, REJECTED_RED]

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(11, 4.8),
        gridspec_kw={"wspace": 0.35},
    )

    # Panel (a) — Disagreement rate
    x = np.arange(len(methods))
    bars_a = ax_a.bar(
        x, disagreement, color=colors, edgecolor=INK, linewidth=0.8, alpha=0.95,
    )
    for b, v in zip(bars_a, disagreement):
        ax_a.text(
            b.get_x() + b.get_width() / 2, v + 1.0,
            f"{v:.1f}%",
            ha="center", va="bottom", fontsize=11, fontweight="semibold",
            color=INK,
        )

    # Arrow + annotation showing the 1.49× improvement
    y_arrow = 35
    ax_a.annotate(
        "",
        xy=(1, 31), xytext=(0, y_arrow),
        arrowprops=dict(
            arrowstyle="->", color=CANONICAL_GREEN,
            lw=2.2, connectionstyle="arc3,rad=-0.25",
        ),
    )
    ax_a.text(
        0.5, 47,
        "1.49× lower\nlabel disagreement",
        ha="center", va="bottom", fontsize=11, fontweight="semibold",
        color=CANONICAL_GREEN,
    )

    ax_a.set_xticks(x)
    ax_a.set_xticklabels(methods, fontsize=9.5)
    ax_a.set_ylabel("Label disagreement vs. NB22 ground truth (%)",
                    fontweight="semibold")
    ax_a.set_ylim(0, 60)
    ax_a.set_title(
        "(a)  Label fidelity against behavioral ground truth",
        fontweight="semibold", loc="left",
    )
    ax_a.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_a.set_axisbelow(True)

    # Panel (b) — Jaccard on deferred class
    bars_b = ax_b.bar(
        x, jaccard, color=colors, edgecolor=INK, linewidth=0.8, alpha=0.95,
    )
    for b, v in zip(bars_b, jaccard):
        ax_b.text(
            b.get_x() + b.get_width() / 2, v + 0.015,
            f"{v:.3f}",
            ha="center", va="bottom", fontsize=11, fontweight="semibold",
            color=INK,
        )

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(methods, fontsize=9.5)
    ax_b.set_ylabel("Jaccard on deferred class (vs. NB22)",
                    fontweight="semibold")
    ax_b.set_ylim(0, 1.15)
    ax_b.set_title(
        "(b)  Deferred-class agreement with ground truth",
        fontweight="semibold", loc="left",
    )
    ax_b.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_b.set_axisbelow(True)

    # Shared footnote at figure bottom
    fig.text(
        0.5, -0.03,
        "Both methods use the same 9 gaze-clean cursor approach features "
        "(hybrid xpath + linear-fallback extractor, 99.8% coverage). "
        "The only difference is the supervision signal: NB21 is trained on click labels "
        "and thresholded post-hoc; M5 is trained directly on NB22 gaze-regression labels. "
        "M5 is presented as a calibration methodology; AdSERP numbers are a reference point.",
        ha="center", fontsize=9.5, color=MUTED, style="italic",
    )

    plt.suptitle(
        "M5 calibration methodology — supervision signal on gaze-clean features",
        fontsize=13.5, fontweight="semibold", y=1.02,
    )

    out_png = OUT_DIR / "label_fidelity_comparison.png"
    out_pdf = OUT_DIR / "label_fidelity_comparison.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


def main():
    render_auc_bars()
    render_label_fidelity()


if __name__ == "__main__":
    main()
