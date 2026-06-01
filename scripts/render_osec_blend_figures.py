"""Two hero figures for the OSEC × Markov × per-AOI sessionization blend.

Figure 1 (osec_blend_saccade_rose):
    Polar histograms of saccade direction by OSEC phase, 2-panel small
    multiples Survey vs Evaluate. Reference shading marks horizontal and
    vertical zones (H-ratio thresholds 0.30 / 0.70). Makes the headline
    finding legible: Survey is wide AND diagonal-leaning; Evaluate is
    more axis-polarized.

Figure 2 (osec_blend_regression_destinations):
    Destination-rank histograms by regression subtype (local 1-2 / mid 3 /
    long >=4), 3-panel small multiples. Makes the local->long top-pull
    gradient visible and shows the 96.4% truncation of longs onto
    organic_1-5.

Inputs:
    scripts/output/osec_markov_blend/saccades.jsonl
    scripts/output/osec_markov_blend/regression_subtypes.json

Outputs (under scripts/output/figures/):
    osec_blend_saccade_rose.{png,pdf}
    osec_blend_regression_destinations.{png,pdf}

Run:
    .venv/bin/python scripts/render_osec_blend_figures.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, "/Users/andyed/Documents/dev/muriel")

from muriel.matplotlibrc_light import PARAMS, apply  # noqa: E402
try:
    from muriel.provenance import stamp_savefig  # noqa: E402
    HAS_PROVENANCE = True
except ImportError:
    HAS_PROVENANCE = False

OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SACC_PATH = ROOT / "scripts/output/osec_markov_blend/saccades.jsonl"
REG_PATH = ROOT / "scripts/output/osec_markov_blend/regression_subtypes.json"

# Wong colorblind-safe palette (Nature Methods 2011).
SURVEY_COLOR = "#E69F00"     # orange — gist sampling
EVALUATE_COLOR = "#0072B2"   # blue — committed reading
LOCAL_COLOR = "#56B4E9"      # sky blue — common, shallow
MID_COLOR = "#E69F00"        # orange — intermediate
LONG_COLOR = "#D55E00"       # vermilion — rare, target-locked

REF_SHADE = "#dddddd"  # axis-zone shading
INK = "#222222"        # body text — 15.2:1 vs #fafaf8 (muriel 8:1 floor)
MUTED = "#444444"      # secondary text — 12.6:1 vs #fafaf8 (passes 8:1)

# Saccade-direction thresholds: must match scripts/osec_markov_blend.py
MICRO_AMP_PX = 30.0
H_RATIO_HV_BOUNDARY = 0.70
H_RATIO_VH_BOUNDARY = 0.30


# ── data loading ────────────────────────────────────────────────────────────

def load_saccades() -> list[dict]:
    recs = []
    with SACC_PATH.open() as f:
        for line in f:
            recs.append(json.loads(line))
    return recs


def saccade_theta(s: dict) -> float:
    """Return saccade angle in radians.

    atan2(-dy, dx): on-page +y is downward, so we negate dy to put
    upward saccades at the top of the polar plot (theta=+pi/2) and
    downward at the bottom (theta=-pi/2). Rightward saccades sit at
    theta=0; leftward at theta=pi.
    """
    return math.atan2(-s["dy"], s["dx"])


def angle_zone(theta_rad: float) -> str:
    """Classify a saccade angle into the same H/V scheme used by
    osec_markov_blend.py — derived purely from theta so the reference
    bands on the polar plot correspond exactly to the dir_class labels."""
    # H ratio = |cos(theta)| / (|cos(theta)| + |sin(theta)|)
    c = abs(math.cos(theta_rad))
    s = abs(math.sin(theta_rad))
    if (c + s) == 0:
        return "diagonal"
    h_ratio = c / (c + s)
    if h_ratio > H_RATIO_HV_BOUNDARY:
        return "horizontal"
    if h_ratio < H_RATIO_VH_BOUNDARY:
        return "vertical"
    return "diagonal"


# ── figure 1: saccade rose ──────────────────────────────────────────────────

def render_saccade_rose(saccades: list[dict]) -> None:
    """Polar histogram of saccade direction, Survey vs Evaluate."""
    n_bins = 24
    edges = np.linspace(-math.pi, math.pi, n_bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    width = 2 * math.pi / n_bins

    # Filter to non-micro saccades — micros have undefined direction.
    survey_thetas = [saccade_theta(s) for s in saccades
                     if s["phase"] == "Survey" and s["amp"] >= MICRO_AMP_PX]
    evaluate_thetas = [saccade_theta(s) for s in saccades
                       if s["phase"] == "Evaluate" and s["amp"] >= MICRO_AMP_PX]

    s_hist, _ = np.histogram(survey_thetas, bins=edges)
    e_hist, _ = np.histogram(evaluate_thetas, bins=edges)
    s_pct = s_hist / s_hist.sum() if s_hist.sum() else s_hist
    e_pct = e_hist / e_hist.sum() if e_hist.sum() else e_hist

    # Direction-class proportions (same dir_class function as the extractor).
    def dir_breakdown(thetas):
        c = Counter(angle_zone(t) for t in thetas)
        total = sum(c.values())
        return {k: c[k] / total if total else 0.0
                for k in ("horizontal", "vertical", "diagonal")}

    s_break = dir_breakdown(survey_thetas)
    e_break = dir_breakdown(evaluate_thetas)

    with plt.rc_context(PARAMS):
        fig, axes = plt.subplots(
            1, 2, figsize=(13, 7.5),
            subplot_kw={"projection": "polar"},
            constrained_layout=True,
        )

        # H-ratio thresholds → angular half-widths of the reference fans.
        theta_h_bound = math.atan2(1 - H_RATIO_HV_BOUNDARY,
                                   H_RATIO_HV_BOUNDARY)
        theta_v_bound = math.atan2(H_RATIO_VH_BOUNDARY,
                                   1 - H_RATIO_VH_BOUNDARY)

        for ax, (phase, pct, n, break_d, color) in zip(axes, [
            ("Survey", s_pct, len(survey_thetas), s_break, SURVEY_COLOR),
            ("Evaluate", e_pct, len(evaluate_thetas), e_break, EVALUATE_COLOR),
        ]):
            ax.set_theta_zero_location("E")
            ax.set_theta_direction(1)  # ccw, so theta=+pi/2 is at top

            r_max = float(pct.max()) * 1.15 if pct.size else 1.0
            # Horizontal reference fans (around theta=0 and pi).
            for theta_c in (0.0, math.pi):
                ax.bar(theta_c, r_max, width=2 * theta_h_bound,
                       bottom=0, color=REF_SHADE, alpha=0.55,
                       zorder=0, edgecolor="none")
            # Vertical reference fans (around +/- pi/2).
            for theta_c in (math.pi / 2, -math.pi / 2):
                ax.bar(theta_c, r_max, width=2 * theta_v_bound,
                       bottom=0, color=REF_SHADE, alpha=0.55,
                       zorder=0, edgecolor="none")

            # Saccade histogram on top.
            ax.bar(centers, pct, width=width * 0.92, bottom=0,
                   color=color, alpha=0.88, edgecolor=INK, linewidth=0.9,
                   zorder=3)

            ax.set_ylim(0, r_max)
            yticks = np.linspace(0, r_max, 5)[1:]
            ax.set_yticks(yticks)
            ax.set_yticklabels([f"{y*100:.0f}%" for y in yticks],
                               fontsize=9, color=MUTED)
            ax.tick_params(axis="y", pad=2)
            ax.set_rlabel_position(112.5)  # tucked between cardinals
            # NOTE: use 3*pi/2 (not -pi/2). Negative theta in set_xticks
            # triggers an implicit thetalim clip that hides ~half the disc.
            ax.set_xticks([0, math.pi / 2, math.pi, 3 * math.pi / 2])
            ax.set_xticklabels(["right", "up", "left", "down"],
                               fontsize=11.5, color=INK)
            ax.tick_params(axis="x", pad=8)
            ax.grid(True, color="#cccccc", linewidth=0.4, alpha=0.5)
            ax.set_axisbelow(False)

            # Single-line title with the dir-class breakdown inline.
            subtitle = (
                f"{phase}    n = {n:,} saccades\n"
                f"H {break_d['horizontal']*100:.1f}%   "
                f"V {break_d['vertical']*100:.1f}%   "
                f"diag {break_d['diagonal']*100:.1f}%"
            )
            ax.set_title(subtitle, fontsize=13, color=INK, pad=18,
                         weight="bold")

        # Single suptitle — constrained_layout reserves space for it.
        # Caption / methodological detail lives in the figure caption when
        # this gets referenced from a draft, not in a competing figtext.
        fig.suptitle(
            "Survey saccades are wide AND diagonal — not horizontal-dominant",
            fontsize=16, weight="bold", color=INK,
        )

        out_png = OUT_DIR / "osec_blend_saccade_rose.png"
        out_pdf = OUT_DIR / "osec_blend_saccade_rose.pdf"
        # Use savefig without bbox_inches='tight' — constrained_layout
        # already manages the figure bounds, and tight-bbox can re-crop
        # polar axes inconsistently.
        if HAS_PROVENANCE:
            stamp_savefig(fig, out_png, script=__file__, bbox_inches=None)
            stamp_savefig(fig, out_pdf, script=__file__, bbox_inches=None)
        else:
            fig.savefig(out_png)
            fig.savefig(out_pdf)
        plt.close(fig)
        print(f"[ok] {out_png.relative_to(ROOT)}")
        print(f"[ok] {out_pdf.relative_to(ROOT)}")


# ── figure 2: regression destinations ──────────────────────────────────────

def render_regression_destinations(reg: dict) -> None:
    """Three small multiples — destination-rank histogram by subtype."""
    subtypes = [
        ("local", "Local (|Δrank| = 1–2)", LOCAL_COLOR, 5159),
        ("mid", "Mid (|Δrank| = 3)", MID_COLOR, 274),
        ("long", "Long (|Δrank| ≥ 4)", LONG_COLOR, 305),
    ]
    # Collect destination distributions across all subtypes.
    max_rank = 10  # show through organic_10, lump beyond into "11+"
    ranks = list(range(1, max_rank + 1)) + ["11+"]
    rank_labels = [str(r) if isinstance(r, int) else r for r in ranks]

    def dest_pct(subtype_key):
        dest = reg.get(f"{subtype_key}_destination_top10", {})
        total = sum(dest.values())
        bin_counts = {r: 0 for r in ranks}
        for k, v in dest.items():
            # k looks like "organic_3"
            if not k.startswith("organic_"):
                continue
            try:
                n = int(k.split("_")[1])
            except ValueError:
                continue
            if n >= 11:
                bin_counts["11+"] += v
            else:
                bin_counts[n] = bin_counts.get(n, 0) + v
        if total == 0:
            return [0.0] * len(ranks)
        return [bin_counts[r] / total * 100 for r in ranks]

    # Y-axis max for shared scaling.
    all_pcts = [dest_pct(st[0]) for st in subtypes]
    y_max = max(max(p) for p in all_pcts) * 1.15

    # Top-pull (rank 1+2) per subtype.
    top_pull = {
        st[0]: sum(p for r, p in zip(ranks, dest_pct(st[0]))
                   if isinstance(r, int) and r <= 2)
        for st in subtypes
    }

    with plt.rc_context(PARAMS):
        fig, axes = plt.subplots(1, 3, figsize=(13, 5.8), sharey=True,
                                 gridspec_kw={"wspace": 0.12},
                                 constrained_layout=True)

        for ax, (key, label, color, n_total), pcts in zip(
                axes, subtypes, all_pcts):
            x_pos = np.arange(len(ranks))
            ax.bar(x_pos, pcts, color=color, alpha=0.9,
                   edgecolor=INK, linewidth=0.9, width=0.78)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(rank_labels, fontsize=10)
            ax.set_xlabel("destination rank", fontsize=12)
            ax.set_ylim(0, y_max)
            ax.grid(axis="y", color="#cccccc", linewidth=0.4, alpha=0.6)
            ax.set_axisbelow(True)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.set_title(f"{label}\nn = {n_total:,}",
                         fontsize=13, color=INK, weight="bold", pad=12)

            # Inline annotation: top-2 cumulative.
            tp = top_pull[key]
            ax.text(0.98, 0.96,
                    f"top-2: {tp:.1f}%",
                    transform=ax.transAxes, ha="right", va="top",
                    fontsize=11.5, color=INK, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.4",
                              facecolor="#fdf8f2",
                              edgecolor=color, linewidth=1.2))

        axes[0].set_ylabel("% of subtype's regressions", fontsize=12)
        fig.suptitle(
            "Long regressions snap to the top — local re-checks spread further down",
            fontsize=16, weight="bold", color=INK,
        )

        out_png = OUT_DIR / "osec_blend_regression_destinations.png"
        out_pdf = OUT_DIR / "osec_blend_regression_destinations.pdf"
        if HAS_PROVENANCE:
            stamp_savefig(fig, out_png, script=__file__, bbox_inches=None)
            stamp_savefig(fig, out_pdf, script=__file__, bbox_inches=None)
        else:
            fig.savefig(out_png)
            fig.savefig(out_pdf)
        plt.close(fig)
        print(f"[ok] {out_png.relative_to(ROOT)}")
        print(f"[ok] {out_pdf.relative_to(ROOT)}")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    apply()  # matplotlibrc_light
    print("[info] loading saccades.jsonl ...")
    saccades = load_saccades()
    print(f"[info] {len(saccades):,} saccades loaded")
    print(f"[info] loading regression_subtypes.json ...")
    reg = json.loads(REG_PATH.read_text())

    print("[info] rendering figure 1 — saccade rose ...")
    render_saccade_rose(saccades)
    print("[info] rendering figure 2 — regression destinations ...")
    render_regression_destinations(reg)
    print("[done]")


if __name__ == "__main__":
    main()
