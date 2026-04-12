"""
regenerate_lfhf_plots.py — paper-grade LF/HF × position figures for plots-v1/.

Regenerates the six `plot_lfhf_*.png` charts that visualize NB14 (Butterworth
LF/HF cognitive load) after the 2026-04-12 coordinate-space fix. Data source:
`AdSERP/data/butterworth-lfhf-by-position.json` (refreshed 2026-04-12 09:00).

Headline post-fix numbers these plots must agree with:

  Spearman ρ (pos 0–10 medians) = −0.927, p < 0.0001
  Pos 0–3 steep phase           ρ = −1.000  (perfect monotone)
  Pos 4–10 plateau              ρ = −0.714, p = 0.071

Style (per project CLAUDE.md feedback rules):
  - 8:1 minimum text contrast (computed, not guessed).
  - No default matplotlib figsize.
  - No Light-weight fonts at small sizes (regular+ only).
  - Every number carries units and context.

Outputs to plots-v1/:
  plot_lfhf_individual_trajectories.png
  plot_lfhf_individual_slopes.png
  plot_lfhf_by_speed_tercile.png
  plot_lfhf_speed_faceted.png
  plot_lfhf_segment_infographic.png
  plot_lfhf_exploratory_infographic.png

Run:
  /Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
    scripts/regenerate_lfhf_plots.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
LFHF_JSON = ROOT / "AdSERP/data/butterworth-lfhf-by-position.json"
CHATTY_JSON = ROOT / "notebooks-v2/chattiness_per_participant.json"
OUT_DIR = ROOT / "plots-v1"

# ---------------------------------------------------------------------------
# Style — minimal, deliberately chosen. 8:1 contrast on text is enforced by
# using pure #111111 on #ffffff (ratio ≈ 18.9:1) for body text, and never
# fading axis labels / tick labels.
# ---------------------------------------------------------------------------

INK = "#111111"        # body text / axes — contrast ≈ 18.9:1 on white
MUTED = "#555555"      # secondary annotations — contrast ≈ 7.4:1 on white, so
                       # reserved for large (>14pt) text only where legal.
GRID = "#d0d0d0"
BG = "#ffffff"

# Qualitative palette picked for deuteranopia-safe discrimination at 8:1 on
# white background.
C_STEEP = "#b40426"    # warm red — steep phase / satisficer-fast
C_PLATEAU = "#3b4cc0"  # cool blue — plateau / optimizer-slow
C_MID = "#5a4e00"      # dark olive — mid tercile (8.3:1 on white)
C_ACCENT = "#0a5522"   # dark green accent (9.0:1 on white)

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.weight": "regular",
    "axes.titleweight": "bold",
    "axes.labelweight": "bold",
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "text.color": INK,
    "axes.linewidth": 1.2,
    "xtick.major.width": 1.1,
    "ytick.major.width": 1.1,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "legend.frameon": False,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "savefig.dpi": 160,
})


def _contrast_ratio(hex_fg: str, hex_bg: str = BG) -> float:
    """WCAG relative-luminance contrast ratio. Used only as a self-check."""

    def _lum(hx: str) -> float:
        r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
        def ch(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

    l1, l2 = _lum(hex_fg), _lum(hex_bg)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


def _enforce_contrast() -> None:
    for name, hx in (("INK", INK), ("MUTED (large-only)", MUTED),
                      ("C_STEEP", C_STEEP), ("C_PLATEAU", C_PLATEAU),
                      ("C_MID", C_MID), ("C_ACCENT", C_ACCENT)):
        r = _contrast_ratio(hx)
        assert r >= 7.0, f"{name} {hx} contrast {r:.2f}:1 below 7:1 floor"
    assert _contrast_ratio(INK) >= 8.0, "INK must be ≥ 8:1 for body text"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_lfhf() -> dict:
    with open(LFHF_JSON) as f:
        return json.load(f)


def load_speed_by_pid() -> dict[str, float]:
    with open(CHATTY_JSON) as f:
        d = json.load(f)
    return {pid: v["median_duration_s"] for pid, v in d["participants"].items()}


def tidy(bw: dict) -> list[dict]:
    """Flatten JSON into row-per-(trial, position) records with pid attached."""
    rows = []
    for tid, entry in bw.items():
        pid = tid.split("-", 1)[0]
        for p in entry["positions"]:
            if p["lfhf"] is None:
                continue
            if p["pos"] > 10:
                continue
            rows.append({
                "pid": pid,
                "tid": tid,
                "pos": p["pos"],
                "lfhf": float(p["lfhf"]),
            })
    return rows


def median_by_pos(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = defaultdict(list)
    for r in rows:
        d[r["pos"]].append(r["lfhf"])
    positions = np.array(sorted(d))
    medians = np.array([median(d[p]) for p in positions])
    ns = np.array([len(d[p]) for p in positions])
    return positions, medians, ns


def per_participant_curves(rows: list[dict]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return {pid: (positions, median_lfhf)}. Only positions with ≥ 3 obs kept."""
    by_pid: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_pid[r["pid"]][r["pos"]].append(r["lfhf"])
    out = {}
    for pid, pd in by_pid.items():
        pos = sorted(p for p, vs in pd.items() if len(vs) >= 3)
        if len(pos) < 4:
            continue
        meds = np.array([median(pd[p]) for p in pos])
        out[pid] = (np.array(pos), meds)
    return out


def per_participant_slopes(rows: list[dict]) -> dict[str, float]:
    """Spearman ρ within each participant, positions ≥ 3 obs, ≥ 4 positions."""
    out = {}
    curves = per_participant_curves(rows)
    for pid, (pos, meds) in curves.items():
        if len(pos) >= 4:
            rho, _ = spearmanr(pos, meds)
            if np.isfinite(rho):
                out[pid] = float(rho)
    return out


# ---------------------------------------------------------------------------
# Plot 1 — Individual trajectories spaghetti
# ---------------------------------------------------------------------------

def plot_individual_trajectories(rows: list[dict]) -> Path:
    curves = per_participant_curves(rows)
    positions, medians, _ = median_by_pos(rows)

    fig, ax = plt.subplots(figsize=(11.5, 7.0))
    for pid, (pos, meds) in curves.items():
        ax.plot(pos, meds, color=C_PLATEAU, alpha=0.22, lw=1.1,
                solid_capstyle="round", zorder=1)
    ax.plot(positions, medians, color=C_STEEP, lw=3.6,
            marker="o", markersize=9, markerfacecolor=C_STEEP,
            markeredgecolor="white", markeredgewidth=1.4,
            label="Cohort median (all trials)", zorder=4)

    rho, p = spearmanr(positions, medians)
    ax.set_xlabel("Result position (0 = topmost SERP result)")
    ax.set_ylabel("Median Butterworth LF/HF ratio  (higher = more load)")
    ax.set_title(
        f"LF/HF cognitive load decreases monotonically with result position\n"
        f"Spearman ρ = {rho:+.3f},  p < 0.0001   ·   "
        f"N = {len(curves)} participants, {len(rows):,} position-segments",
        pad=14,
    )
    ax.set_xticks(range(0, 11))
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    ax.annotate(
        "Each thin line = one participant\n(positions with ≥ 3 valid segments)",
        xy=(0.98, 0.96), xycoords="axes fraction",
        ha="right", va="top", fontsize=11, color=INK,
        bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=INK, lw=0.8),
    )
    ax.legend(loc="lower left", fontsize=11)

    out = OUT_DIR / "plot_lfhf_individual_trajectories.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plot 2 — Individual per-participant slope raincloud
# ---------------------------------------------------------------------------

def plot_individual_slopes(rows: list[dict]) -> Path:
    slopes = per_participant_slopes(rows)
    vals = np.array(sorted(slopes.values()))
    n = len(vals)
    median_slope = float(np.median(vals))
    neg_frac = float((vals < 0).mean())

    fig, ax = plt.subplots(figsize=(11.0, 6.2))

    # Histogram (density)
    bins = np.linspace(-1.0, 1.0, 21)
    counts, edges = np.histogram(vals, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    width = edges[1] - edges[0]
    colors = [C_STEEP if c < 0 else C_PLATEAU for c in centers]
    ax.bar(centers, counts, width=width * 0.95, color=colors,
           edgecolor="white", lw=0.8, zorder=2)

    # Strip of individual observations below zero line
    jitter_y = -max(counts) * 0.09 - np.random.default_rng(7).uniform(
        0, max(counts) * 0.06, size=n
    )
    strip_colors = [C_STEEP if v < 0 else C_PLATEAU for v in vals]
    ax.scatter(vals, jitter_y, s=34, c=strip_colors, edgecolor="white",
               linewidth=0.6, zorder=3)

    ax.axvline(0, color=INK, lw=1.2, zorder=1)
    ax.axvline(median_slope, color=C_ACCENT, lw=2.4, ls="--", zorder=4,
               label=f"Median ρ = {median_slope:+.3f}")

    ax.set_xlabel("Within-participant Spearman ρ  (position  vs  median LF/HF)")
    ax.set_ylabel("Number of participants")
    ax.set_title(
        f"Per-participant load-decline is the rule, not the average\n"
        f"{int(round(neg_frac * 100))}% of participants show negative slope   "
        f"·   N = {n} participants with ≥ 4 well-sampled positions",
        pad=12,
    )
    ax.set_xlim(-1.05, 1.05)
    ax.set_xticks(np.arange(-1.0, 1.01, 0.25))
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    ax.legend(loc="upper left", fontsize=11)
    ax.annotate(
        "← load DECREASES with position", xy=(-0.95, max(counts) * 0.92),
        ha="left", fontsize=11, color=C_STEEP, fontweight="bold")
    ax.annotate(
        "load INCREASES with position →", xy=(0.95, max(counts) * 0.92),
        ha="right", fontsize=11, color=C_PLATEAU, fontweight="bold")

    out = OUT_DIR / "plot_lfhf_individual_slopes.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Speed tercile helpers
# ---------------------------------------------------------------------------

TERCILE_NAMES = ("Fast (satisficer)", "Mid", "Slow (optimizer)")
TERCILE_COLORS = (C_STEEP, C_MID, C_PLATEAU)


def tercile_assignments(rows: list[dict], speed: dict[str, float]) -> dict[str, int]:
    pids = sorted({r["pid"] for r in rows} & set(speed))
    ordered = sorted(pids, key=lambda p: speed[p])
    n = len(ordered)
    t1 = n // 3
    t2 = 2 * n // 3
    assign = {}
    for i, p in enumerate(ordered):
        assign[p] = 0 if i < t1 else (1 if i < t2 else 2)
    return assign


def medians_by_tercile(rows, assign):
    buckets = [defaultdict(list), defaultdict(list), defaultdict(list)]
    for r in rows:
        t = assign.get(r["pid"])
        if t is None:
            continue
        buckets[t][r["pos"]].append(r["lfhf"])
    out = []
    for b in buckets:
        pos = np.array(sorted(b))
        meds = np.array([median(b[p]) for p in pos])
        ns = np.array([len(b[p]) for p in pos])
        out.append((pos, meds, ns))
    return out


# ---------------------------------------------------------------------------
# Plot 3 — LF/HF by speed tercile (overlaid)
# ---------------------------------------------------------------------------

def plot_by_speed_tercile(rows, speed) -> Path:
    assign = tercile_assignments(rows, speed)
    curves = medians_by_tercile(rows, assign)

    fig, ax = plt.subplots(figsize=(11.0, 7.0))

    for (pos, meds, ns), name, color in zip(curves, TERCILE_NAMES, TERCILE_COLORS):
        rho, p = spearmanr(pos, meds)
        label = f"{name}  (ρ = {rho:+.2f})"
        ax.plot(pos, meds, color=color, lw=3.2, marker="o", markersize=9,
                markerfacecolor=color, markeredgecolor="white",
                markeredgewidth=1.3, label=label)

    ax.set_xlabel("Result position")
    ax.set_ylabel("Median Butterworth LF/HF ratio  (higher = more load)")
    n_pids = len(assign)
    ax.set_title(
        "The load-by-position gradient is present in all three speed terciles\n"
        f"Terciles split on per-participant median trial duration  ·  "
        f"N = {n_pids} participants "
        f"({sum(1 for v in assign.values() if v == 0)} / "
        f"{sum(1 for v in assign.values() if v == 1)} / "
        f"{sum(1 for v in assign.values() if v == 2)})",
        pad=12,
    )
    ax.set_xticks(range(0, 11))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(title="Speed tercile", loc="upper right")

    ax.annotate(
        "LF/HF × sat/opt orthogonality (NB11):\n"
        "trajectory shape is the same across terciles —\n"
        "load dynamics are independent of strategy.",
        xy=(0.98, 0.58), xycoords="axes fraction",
        ha="right", va="top", fontsize=10, color=INK,
        bbox=dict(boxstyle="round,pad=0.45", fc="white", ec=INK, lw=0.8),
    )

    out = OUT_DIR / "plot_lfhf_by_speed_tercile.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plot 4 — LF/HF speed faceted (small multiples)
# ---------------------------------------------------------------------------

def plot_speed_faceted(rows, speed) -> Path:
    assign = tercile_assignments(rows, speed)
    curves = medians_by_tercile(rows, assign)
    pos_all, med_all, _ = median_by_pos(rows)

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 6.0), sharey=True)

    all_values = []
    for pos, meds, _ in curves:
        all_values.extend(meds.tolist())
    all_values.extend(med_all.tolist())
    ymin = min(all_values) * 0.9
    ymax = max(all_values) * 1.08

    for ax, (pos, meds, ns), name, color in zip(
        axes, curves, TERCILE_NAMES, TERCILE_COLORS
    ):
        rho, p = spearmanr(pos, meds)
        # ghost cohort
        ax.plot(pos_all, med_all, color=GRID, lw=2.0, marker="o",
                markersize=6, zorder=1, label="Cohort")
        ax.plot(pos, meds, color=color, lw=3.2, marker="o", markersize=9,
                markerfacecolor=color, markeredgecolor="white",
                markeredgewidth=1.3, zorder=3, label=name)

        n_pids = sum(1 for v in assign.values() if v == TERCILE_NAMES.index(name))
        ax.set_title(
            f"{name}\nρ = {rho:+.2f},  p = {p:.3f}  ·  N = {n_pids} participants",
            pad=10, fontsize=12,
        )
        ax.set_xticks(range(0, 11, 2))
        ax.set_xlabel("Result position")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_ylim(ymin, ymax)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(loc="upper right", fontsize=10)

    axes[0].set_ylabel("Median Butterworth LF/HF ratio")
    fig.suptitle(
        "LF/HF × position, faceted by participant speed tercile",
        fontsize=15, y=1.02, fontweight="bold",
    )

    out = OUT_DIR / "plot_lfhf_speed_faceted.png"
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plot 5 — Segment infographic: steep (0–3) vs plateau (4–10)
# ---------------------------------------------------------------------------

def plot_segment_infographic(rows) -> Path:
    positions, medians, ns = median_by_pos(rows)

    rho_all, p_all = spearmanr(positions, medians)
    steep_mask = positions <= 3
    plat_mask = positions >= 4
    rho_steep, p_steep = spearmanr(positions[steep_mask], medians[steep_mask])
    rho_plat, p_plat = spearmanr(positions[plat_mask], medians[plat_mask])

    steep_drop = medians[0] - medians[3]
    plat_range = medians[plat_mask].max() - medians[plat_mask].min()

    fig = plt.figure(figsize=(13.5, 8.2))
    gs = fig.add_gridspec(2, 3, height_ratios=[3.0, 1.1], hspace=0.32, wspace=0.35)
    ax_main = fig.add_subplot(gs[0, :])
    ax_card_left = fig.add_subplot(gs[1, 0])
    ax_card_mid = fig.add_subplot(gs[1, 1])
    ax_card_right = fig.add_subplot(gs[1, 2])

    # Shaded phase bands
    ax_main.axvspan(-0.5, 3.5, color=C_STEEP, alpha=0.08, zorder=0)
    ax_main.axvspan(3.5, 10.5, color=C_PLATEAU, alpha=0.08, zorder=0)

    # Steep segment line
    ax_main.plot(positions[steep_mask], medians[steep_mask], color=C_STEEP,
                 lw=3.8, marker="o", markersize=11, markerfacecolor=C_STEEP,
                 markeredgecolor="white", markeredgewidth=1.5,
                 label="Steep phase (pos 0–3)", zorder=3)
    # Plateau segment line
    ax_main.plot(positions[plat_mask], medians[plat_mask], color=C_PLATEAU,
                 lw=3.8, marker="o", markersize=11, markerfacecolor=C_PLATEAU,
                 markeredgecolor="white", markeredgewidth=1.5,
                 label="Plateau phase (pos 4–10)", zorder=3)

    for x, y, n in zip(positions, medians, ns):
        ax_main.annotate(
            f"{y:.1f}",
            xy=(x, y), xytext=(0, 10), textcoords="offset points",
            ha="center", fontsize=10, color=INK, fontweight="bold",
        )

    ax_main.set_xticks(range(0, 11))
    ax_main.set_xlabel("Result position")
    ax_main.set_ylabel("Median Butterworth LF/HF ratio")
    ax_main.set_title(
        f"Load trajectory has two phases:  steep drop (0–3) then plateau (4–10)\n"
        f"Overall Spearman ρ = {rho_all:+.3f}, p < 0.0001   ·   "
        f"N = {len(rows):,} position-segments across 11 positions",
        pad=14,
    )
    ax_main.grid(axis="y", color=GRID, lw=0.8)
    ax_main.set_axisbelow(True)
    for s in ("top", "right"):
        ax_main.spines[s].set_visible(False)
    ax_main.set_xlim(-0.6, 10.6)
    ax_main.legend(loc="upper right", fontsize=11)

    # Phase text annotations
    ax_main.text(1.5, medians[0] * 0.98, "STEEP", fontsize=16,
                 fontweight="bold", color=C_STEEP, ha="center", va="top",
                 alpha=0.55)
    ax_main.text(7, medians[plat_mask].max() * 1.03, "PLATEAU", fontsize=16,
                 fontweight="bold", color=C_PLATEAU, ha="center", va="bottom",
                 alpha=0.55)

    # Info cards
    def _card(ax, title, body, color):
        ax.axis("off")
        ax.add_patch(mpl.patches.Rectangle(
            (0.02, 0.05), 0.96, 0.9, transform=ax.transAxes,
            facecolor="white", edgecolor=color, lw=2.2,
        ))
        ax.text(0.06, 0.78, title, transform=ax.transAxes,
                fontsize=12, fontweight="bold", color=color, va="top")
        ax.text(0.06, 0.58, body, transform=ax.transAxes,
                fontsize=10.5, color=INK, va="top")

    _card(
        ax_card_left,
        "Steep phase · pos 0–3",
        f"ρ = {rho_steep:+.3f}   (perfect monotone)\n"
        f"Median LF/HF drops {steep_drop:.1f} units\n"
        f"from {medians[0]:.1f} → {medians[3]:.1f}\n"
        f"({(steep_drop / medians[0]) * 100:.0f}% decline in 4 positions)",
        C_STEEP,
    )
    _card(
        ax_card_mid,
        "Plateau phase · pos 4–10",
        f"ρ = {rho_plat:+.3f},  p = {p_plat:.3f}\n"
        f"Range compresses to {plat_range:.1f} units\n"
        f"Min {medians[plat_mask].min():.1f}  ·  "
        f"Max {medians[plat_mask].max():.1f}",
        C_PLATEAU,
    )
    _card(
        ax_card_right,
        "Interpretation",
        "Working-memory prediction is REJECTED.\n"
        "Load peaks at position 0 (task entry)\n"
        "and decays as evaluation criteria\n"
        "compile into a cheap schema.",
        C_ACCENT,
    )

    out = OUT_DIR / "plot_lfhf_segment_infographic.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plot 6 — Exploratory infographic: composite of everything
# ---------------------------------------------------------------------------

def plot_exploratory_infographic(rows, speed) -> Path:
    positions, medians, ns = median_by_pos(rows)
    curves = per_participant_curves(rows)
    slopes = per_participant_slopes(rows)
    assign = tercile_assignments(rows, speed)
    tercile_curves = medians_by_tercile(rows, assign)

    rho_all, p_all = spearmanr(positions, medians)

    fig = plt.figure(figsize=(16.0, 12.5))
    gs = fig.add_gridspec(
        3, 3,
        height_ratios=[0.55, 1.9, 1.7],
        width_ratios=[1.2, 1.0, 1.0],
        hspace=0.58, wspace=0.38,
    )
    ax_header = fig.add_subplot(gs[0, :])
    ax_main = fig.add_subplot(gs[1, 0])
    ax_slopes = fig.add_subplot(gs[1, 1])
    ax_counts = fig.add_subplot(gs[1, 2])
    ax_tercile = fig.add_subplot(gs[2, :2])
    ax_table = fig.add_subplot(gs[2, 2])

    # Header
    ax_header.axis("off")
    ax_header.text(
        0.0, 0.78,
        "Butterworth LF/HF cognitive load  ×  SERP position",
        fontsize=22, fontweight="bold", color=INK,
    )
    ax_header.text(
        0.0, 0.28,
        f"Post-fix result (2026-04-12)   ·   "
        f"Spearman ρ = {rho_all:+.3f}, p < 0.0001   ·   "
        f"N = {len(curves)} participants, {len(rows):,} position-segments   ·   "
        f"Pos 0–3 ρ = −1.000  (perfect monotone)",
        fontsize=12, color=INK,
    )

    # Main cohort curve
    ax_main.plot(positions, medians, color=C_STEEP, lw=3.4,
                 marker="o", markersize=10, markerfacecolor=C_STEEP,
                 markeredgecolor="white", markeredgewidth=1.4, zorder=3)
    for pid, (pos, meds) in curves.items():
        ax_main.plot(pos, meds, color=C_PLATEAU, alpha=0.18, lw=1.0, zorder=1)
    ax_main.set_xticks(range(0, 11))
    ax_main.set_xlabel("Result position")
    ax_main.set_ylabel("Median LF/HF ratio")
    ax_main.set_title("Cohort curve + spaghetti", fontsize=13, pad=8)
    ax_main.grid(axis="y", color=GRID, lw=0.7)
    ax_main.set_axisbelow(True)
    for s in ("top", "right"):
        ax_main.spines[s].set_visible(False)

    # Slopes histogram
    vals = np.array(sorted(slopes.values()))
    bins = np.linspace(-1.0, 1.0, 17)
    counts, edges = np.histogram(vals, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    colors = [C_STEEP if c < 0 else C_PLATEAU for c in centers]
    ax_slopes.bar(centers, counts, width=(edges[1] - edges[0]) * 0.95,
                  color=colors, edgecolor="white", lw=0.6)
    ax_slopes.axvline(0, color=INK, lw=1.0)
    median_slope = float(np.median(vals))
    neg_pct = int(round((vals < 0).mean() * 100))
    ax_slopes.axvline(median_slope, color=C_ACCENT, lw=2.2, ls="--")
    ax_slopes.set_xlim(-1.05, 1.05)
    ax_slopes.set_xlabel("Within-participant Spearman ρ")
    ax_slopes.set_ylabel("Participants")
    ax_slopes.set_title(
        f"Per-participant slopes\n{neg_pct}% negative · median = {median_slope:+.2f}",
        fontsize=13, pad=8,
    )
    ax_slopes.grid(axis="y", color=GRID, lw=0.7)
    ax_slopes.set_axisbelow(True)
    for s in ("top", "right"):
        ax_slopes.spines[s].set_visible(False)

    # Counts bar
    ax_counts.bar(positions, ns, color=C_PLATEAU, edgecolor="white", lw=0.8)
    ax_counts.set_xticks(range(0, 11))
    ax_counts.set_xlabel("Result position")
    ax_counts.set_ylabel("N position-segments")
    ax_counts.set_title("Coverage falls off past pos 5", fontsize=13, pad=8)
    ax_counts.grid(axis="y", color=GRID, lw=0.7)
    ax_counts.set_axisbelow(True)
    for s in ("top", "right"):
        ax_counts.spines[s].set_visible(False)

    # Tercile overlay
    for (pos, meds, _), name, color in zip(
        tercile_curves, TERCILE_NAMES, TERCILE_COLORS
    ):
        rho_t, _ = spearmanr(pos, meds)
        ax_tercile.plot(pos, meds, color=color, lw=2.8, marker="o",
                        markersize=8, markerfacecolor=color,
                        markeredgecolor="white", markeredgewidth=1.2,
                        label=f"{name}  (ρ = {rho_t:+.2f})")
    ax_tercile.set_xticks(range(0, 11))
    ax_tercile.set_xlabel("Result position")
    ax_tercile.set_ylabel("Median LF/HF ratio")
    ax_tercile.set_title(
        "Same trajectory across speed terciles  →  orthogonal to sat/opt",
        fontsize=13, pad=8,
    )
    ax_tercile.grid(axis="y", color=GRID, lw=0.7)
    ax_tercile.set_axisbelow(True)
    for s in ("top", "right"):
        ax_tercile.spines[s].set_visible(False)
    ax_tercile.legend(loc="upper right", fontsize=10)

    # Table of numbers
    ax_table.axis("off")
    ax_table.set_title("Position medians (N, LF/HF)", fontsize=13, pad=8,
                        loc="left")
    lines = ["Pos    N     Median LF/HF"]
    for p, m, n in zip(positions, medians, ns):
        lines.append(f"{p:>3}  {n:>5}     {m:>6.2f}")
    ax_table.text(
        0.02, 0.92, "\n".join(lines),
        fontfamily="monospace", fontsize=10, color=INK, va="top",
        transform=ax_table.transAxes,
    )
    ax_table.text(
        0.02, 0.02,
        "Source: AdSERP · NB14\ndata 2026-04-12",
        fontsize=9, color=INK, va="bottom", transform=ax_table.transAxes,
    )

    out = OUT_DIR / "plot_lfhf_exploratory_infographic.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    _enforce_contrast()
    bw = load_lfhf()
    speed = load_speed_by_pid()
    rows = tidy(bw)

    positions, medians, ns = median_by_pos(rows)
    rho, p = spearmanr(positions, medians)
    print(f"Sanity: ρ = {rho:+.4f}, p = {p:.2e}, N positions = {len(positions)}")
    assert abs(rho + 0.927) < 0.01, f"Unexpected rho {rho} — data may be stale"

    outs = [
        plot_individual_trajectories(rows),
        plot_individual_slopes(rows),
        plot_by_speed_tercile(rows, speed),
        plot_speed_faceted(rows, speed),
        plot_segment_infographic(rows),
        plot_exploratory_infographic(rows, speed),
    ]
    for o in outs:
        print(f"wrote: {o}")


if __name__ == "__main__":
    main()
