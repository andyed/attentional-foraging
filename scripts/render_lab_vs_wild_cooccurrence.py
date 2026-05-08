#!/usr/bin/env python3
"""Side-by-side LAB vs WILD-mode co-occurrence figures for the AdSERP four-class taxonomy.

Inputs (read-only):
  scripts/output/figures/class_distributions_summary.json           [LAB,  NB22 gaze-regression]
  scripts/output/figures/class_distributions_wild_mode_summary.json [WILD, M5 cursor-only LOSO]

Outputs (written to scripts/output/figures/):
  cooccurrence_matrix_lab_vs_wild.{png,pdf}
  cooccurrence_venn_lab_vs_wild.{png,pdf}

Idempotent: rerunning from the same JSONs reproduces byte-similar PNG/PDF output
modulo the matplotlib metadata timestamp.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib_venn import venn3, venn3_circles

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIG_DIR = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/figures")
LAB_JSON = FIG_DIR / "class_distributions_summary.json"
WILD_JSON = FIG_DIR / "class_distributions_wild_mode_summary.json"

INK = "#1a1a2e"
CREAM = "#e6e4d2"

CLASS_COLORS = {
    "clicked": "#2ca25f",         # green
    "deferred": "#e08214",        # orange
    "evaluated-rejected": "#b2182b",  # red
}

CLASSES = ["clicked", "deferred", "evaluated-rejected"]

# Bit position in the 3-bit pattern key:
#   bit 0 (leftmost char) -> has_clicked
#   bit 1                  -> has_deferred
#   bit 2 (rightmost)      -> has_eval_rejected
BIT_INDEX = {"clicked": 0, "deferred": 1, "evaluated-rejected": 2}


# ---------------------------------------------------------------------------
# WCAG contrast helpers (8:1 minimum for all text)
# ---------------------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    """rgb in 0-1 floats."""
    r, g, b = (_srgb_to_linear(v * 255.0) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_rgb: tuple[float, float, float], bg_rgb: tuple[float, float, float]) -> float:
    L1 = _relative_luminance(fg_rgb)
    L2 = _relative_luminance(bg_rgb)
    lighter, darker = max(L1, L2), min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


INK_RGB = hex_to_rgb(INK)
CREAM_RGB = hex_to_rgb(CREAM)
WHITE_RGB = (1.0, 1.0, 1.0)
BLACK_RGB = (0.0, 0.0, 0.0)


def pick_text_color_for_bg(bg_rgb: tuple[float, float, float]) -> str:
    """Return the hex color that yields >=8:1 contrast on the supplied background.

    Prefers INK on lighter backgrounds and CREAM on darker; falls back to pure
    black/white if INK/CREAM cannot reach 8:1 (rare on extreme cells)."""
    candidates = [
        ("#1a1a2e", INK_RGB),
        ("#e6e4d2", CREAM_RGB),
        ("#000000", BLACK_RGB),
        ("#ffffff", WHITE_RGB),
    ]
    best_hex, best_ratio = None, -1.0
    for hex_code, rgb in candidates:
        ratio = contrast_ratio(rgb, bg_rgb)
        if ratio >= 8.0:
            return hex_code
        if ratio > best_ratio:
            best_hex, best_ratio = hex_code, ratio
    # Fallback: nothing hit 8:1 — return whichever ink/cream has the higher ratio.
    return best_hex


# ---------------------------------------------------------------------------
# Data loading + WILD aggregation
# ---------------------------------------------------------------------------

def load_lab_panel_d(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)
    panel = data["panels"]["d_cooccurrence"]
    return {
        "n_trials": data["n_trials"],
        "inclusive_buckets": panel["inclusive_buckets"],
        "exclusive_patterns": panel["exclusive_patterns"],
    }


def load_wild_panel_d(path: Path) -> dict:
    """WILD JSON has `patterns` (not `exclusive_patterns`) and no `inclusive_buckets`.

    We aggregate inclusive marginals/pairs/triple from the 8-bucket pattern table.
    """
    with open(path) as f:
        data = json.load(f)
    panel = data["panels"]["d_cooccurrence"]
    n_trials = data["n_trials"]
    patterns = panel["patterns"]

    def sum_where(predicate) -> int:
        return sum(p["n_trials"] for key, p in patterns.items() if predicate(key))

    def has_bit(key: str, idx: int) -> bool:
        return key[idx] == "1"

    inclusive = {}
    # Singletons (marginals)
    for cls in CLASSES:
        idx = BIT_INDEX[cls]
        n = sum_where(lambda k, idx=idx: has_bit(k, idx))
        label = {"clicked": "click", "deferred": "defer", "evaluated-rejected": "eval-rej"}[cls]
        inclusive[label] = {"n_trials": n, "fraction": n / n_trials}

    # Pairs
    pair_specs = [
        (("clicked", "deferred"), "click \u2229 defer"),
        (("clicked", "evaluated-rejected"), "click \u2229 eval-rej"),
        (("deferred", "evaluated-rejected"), "defer \u2229 eval-rej"),
    ]
    for (a, b), label in pair_specs:
        ia, ib = BIT_INDEX[a], BIT_INDEX[b]
        n = sum_where(lambda k, ia=ia, ib=ib: has_bit(k, ia) and has_bit(k, ib))
        inclusive[label] = {"n_trials": n, "fraction": n / n_trials}

    # Triple
    n_triple = sum_where(lambda k: k == "111")
    inclusive["click \u2229 defer \u2229 eval-rej"] = {
        "n_trials": n_triple,
        "fraction": n_triple / n_trials,
    }

    return {
        "n_trials": n_trials,
        "inclusive_buckets": inclusive,
        "exclusive_patterns": patterns,
    }


# ---------------------------------------------------------------------------
# Figure A — pairwise co-occurrence matrices
# ---------------------------------------------------------------------------

def build_matrix(inclusive: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return (frac_matrix 3x3, count_matrix 3x3) in CLASSES order.

    Diagonal = marginals.  Off-diagonals = pairwise inclusive co-occurrence (symmetric).
    """
    label_for_class = {"clicked": "click", "deferred": "defer", "evaluated-rejected": "eval-rej"}
    pair_label = {
        frozenset({"clicked", "deferred"}): "click \u2229 defer",
        frozenset({"clicked", "evaluated-rejected"}): "click \u2229 eval-rej",
        frozenset({"deferred", "evaluated-rejected"}): "defer \u2229 eval-rej",
    }
    n = len(CLASSES)
    frac = np.zeros((n, n))
    cnt = np.zeros((n, n), dtype=int)
    for i, ci in enumerate(CLASSES):
        for j, cj in enumerate(CLASSES):
            if i == j:
                bucket = inclusive[label_for_class[ci]]
            else:
                bucket = inclusive[pair_label[frozenset({ci, cj})]]
            frac[i, j] = bucket["fraction"]
            cnt[i, j] = bucket["n_trials"]
    return frac, cnt


def render_matrix_subplot(
    ax: plt.Axes,
    frac: np.ndarray,
    cnt: np.ndarray,
    title: str,
    cmap: mpl.colors.Colormap,
    norm: Normalize,
) -> None:
    im = ax.imshow(frac, cmap=cmap, norm=norm, aspect="equal")

    ax.set_xticks(range(len(CLASSES)))
    ax.set_yticks(range(len(CLASSES)))
    ax.set_xticklabels(CLASSES, color=INK, fontsize=12)
    ax.set_yticklabels(CLASSES, color=INK, fontsize=12)
    ax.tick_params(axis="x", which="both", length=0, pad=4)
    ax.tick_params(axis="y", which="both", length=0, pad=4)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", rotation_mode="anchor")

    ax.set_title(title, color=INK, fontsize=13, pad=10)

    # Cell annotations: contrast-aware
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            cell_rgba = cmap(norm(frac[i, j]))
            cell_rgb = cell_rgba[:3]
            text_color = pick_text_color_for_bg(cell_rgb)
            ax.text(
                j,
                i - 0.13,
                f"n={cnt[i, j]:,}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=11,
                fontweight="bold",
            )
            ax.text(
                j,
                i + 0.18,
                f"{frac[i, j] * 100:.1f}%",
                ha="center",
                va="center",
                color=text_color,
                fontsize=11,
            )

    # Subtle grid between cells
    for spine in ax.spines.values():
        spine.set_edgecolor(INK)
        spine.set_linewidth(0.6)


def render_figure_a(lab: dict, wild: dict) -> None:
    lab_frac, lab_cnt = build_matrix(lab["inclusive_buckets"])
    wild_frac, wild_cnt = build_matrix(wild["inclusive_buckets"])

    vmax = float(max(lab_frac.max(), wild_frac.max()))
    norm = Normalize(vmin=0.0, vmax=vmax)
    cmap = plt.get_cmap("viridis")

    fig, (ax_lab, ax_wild) = plt.subplots(1, 2, figsize=(14, 6), facecolor="white")

    render_matrix_subplot(ax_lab, lab_frac, lab_cnt, "LAB (NB22 gaze-regression)", cmap, norm)
    render_matrix_subplot(
        ax_wild, wild_frac, wild_cnt, "WILD-mode (M5 cursor-only LOSO)", cmap, norm
    )

    # Shared colorbar on the right
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=[ax_lab, ax_wild], fraction=0.035, pad=0.03)
    cbar.set_label("P(class) or P(class i \u2229 class j)", color=INK, fontsize=11)
    cbar.ax.tick_params(colors=INK)
    cbar.outline.set_edgecolor(INK)

    fig.suptitle(
        "AdSERP four-class pairwise co-occurrence \u2014 LAB vs WILD-mode (n=2,287 trials)",
        color=INK,
        fontsize=15,
        y=0.99,
    )

    out_png = FIG_DIR / "cooccurrence_matrix_lab_vs_wild.png"
    out_pdf = FIG_DIR / "cooccurrence_matrix_lab_vs_wild.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


# ---------------------------------------------------------------------------
# Figure B — area-proportional three-circle Venn (matplotlib_venn.venn3)
# ---------------------------------------------------------------------------

# venn3 subset tuple order: (Abc, aBc, ABc, abC, AbC, aBC, ABC)
# Our pattern bits are (clicked=0, deferred=1, evaluated-rejected=2), so
# A=clicked, B=deferred, C=evaluated-rejected maps pattern '100' -> Abc, etc.
_VENN_PATTERN_ORDER = ("100", "010", "110", "001", "101", "011", "111")
_VENN_REGION_IDS = ("100", "010", "110", "001", "101", "011", "111")  # venn3 region id == our key


def render_venn_subplot(ax: plt.Axes, exclusive_patterns: dict, title: str, n_trials: int) -> None:
    subsets = tuple(exclusive_patterns[k]["n_trials"] for k in _VENN_PATTERN_ORDER)

    v = venn3(
        subsets=subsets,
        set_labels=("", "", ""),  # we render the class legend once below
        set_colors=(
            CLASS_COLORS["clicked"],
            CLASS_COLORS["deferred"],
            CLASS_COLORS["evaluated-rejected"],
        ),
        alpha=0.55,
        ax=ax,
    )

    # Draw the outlines so empty/small regions still show a boundary
    circles = venn3_circles(subsets=subsets, linestyle="-", linewidth=1.2, color=INK, ax=ax)
    for c in circles:
        c.set_alpha(0.8)

    # Override region labels: show `n=... / xx.x%` with a white halo for legibility
    halo = [path_effects.withStroke(linewidth=2.8, foreground="white")]
    for rid in _VENN_REGION_IDS:
        label = v.get_label_by_id(rid)
        if label is None:
            continue  # region suppressed because subset == 0
        bucket = exclusive_patterns[rid]
        n = bucket["n_trials"]
        frac = bucket["fraction"]
        label.set_text(f"n={n:,}\n{frac * 100:.1f}%")
        label.set_color("#000000")
        label.set_fontsize(10)
        label.set_fontweight("bold")
        label.set_path_effects(halo)
        label.set_linespacing(1.15)

    ax.set_title(title, color=INK, fontsize=13, pad=10)


def render_figure_b(lab: dict, wild: dict) -> None:
    fig, (ax_lab, ax_wild) = plt.subplots(1, 2, figsize=(14, 7.5), facecolor="white")

    render_venn_subplot(
        ax_lab,
        lab["exclusive_patterns"],
        "LAB (NB22 gaze-regression)",
        lab["n_trials"],
    )
    render_venn_subplot(
        ax_wild,
        wild["exclusive_patterns"],
        "WILD-mode (M5 cursor-only LOSO)",
        wild["n_trials"],
    )

    # Shared legend below the panels — outside the circles.
    legend_handles = [
        mpatches.Patch(facecolor=CLASS_COLORS[cls], edgecolor=INK, alpha=0.55, label=cls)
        for cls in CLASSES
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=12,
        bbox_to_anchor=(0.5, 0.02),
        labelcolor=INK,
    )

    fig.suptitle(
        "AdSERP four-class trial-level co-occurrence — LAB vs WILD-mode "
        "(n=2,287 trials, area-proportional)",
        color=INK,
        fontsize=15,
        y=0.995,
    )

    fig.subplots_adjust(left=0.03, right=0.97, top=0.88, bottom=0.10, wspace=0.05)

    out_png = FIG_DIR / "cooccurrence_venn_lab_vs_wild.png"
    out_pdf = FIG_DIR / "cooccurrence_venn_lab_vs_wild.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


# ---------------------------------------------------------------------------
# Sanity prints (verify against prompt's expected counts)
# ---------------------------------------------------------------------------

def _verify_pattern_counts(label: str, patterns: dict) -> None:
    expected_keys = {"000", "100", "010", "001", "110", "101", "011", "111"}
    assert set(patterns.keys()) == expected_keys, f"{label}: pattern keys differ"
    total = sum(p["n_trials"] for p in patterns.values())
    print(f"  {label}: pattern-sum n={total} (should equal n_trials=2287)")


def main() -> None:
    assert LAB_JSON.exists(), f"missing {LAB_JSON}"
    assert WILD_JSON.exists(), f"missing {WILD_JSON}"

    lab = load_lab_panel_d(LAB_JSON)
    wild = load_wild_panel_d(WILD_JSON)

    print("Verifying inputs...")
    print(f"  LAB n_trials  = {lab['n_trials']}")
    print(f"  WILD n_trials = {wild['n_trials']}")
    _verify_pattern_counts("LAB ", lab["exclusive_patterns"])
    _verify_pattern_counts("WILD", wild["exclusive_patterns"])

    # Show inclusive aggregates so the WILD aggregation can be sanity-checked.
    print("\nWILD inclusive aggregates (computed from patterns):")
    for label, bucket in wild["inclusive_buckets"].items():
        print(f"  {label:32s} n={bucket['n_trials']:5d}  ({bucket['fraction'] * 100:.2f}%)")

    print("\nRendering Figure A (matrix)...")
    render_figure_a(lab, wild)

    print("\nRendering Figure B (Venn)...")
    render_figure_b(lab, wild)


if __name__ == "__main__":
    main()
