#!/usr/bin/env python3
"""
Figure 1 for CIKM 2026 paper-v5: forward vs regressive cursor-swarm pair.

Renders two AdSERP exemplar trials side by side. Each panel shows:
- Stacked AOI rectangles (organic boundary bboxes, page-space)
- Cursor trajectory polyline with per-segment color by nearest AOI
- Click event marked with a star
- Trial duration printed bottom-right

Lands the methodological prior (per-result-AOI partitioning) AND the
deliberation-phase repeat-or-leave taxonomy in one image.
"""

from __future__ import annotations
import json
import csv
import math
from pathlib import Path
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

# ── Paths ─────────────────────────────────────────────────────────
REPO = Path("/Users/andyed/Documents/dev/attentional-foraging")
DATA = REPO / "AdSERP" / "data"
OUT = REPO / "scripts" / "output" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Exemplar trials chosen via cursor-approach-features-organic-hybrid.json
# - Forward: clicked AOI shows retreat_dist == 0, direction_changes == 0
# - Regressive: clicked AOI shows retreat_dist > 500, direction_changes >= 7
FORWARD = "p021-b1-t4"
REGRESSIVE = "p042-b1-t5"

# Wong-derived 10-color CVD-safe palette (saturation gradient on Okabe-Ito hues).
# Result positions 1..10 mapped to consistent hues across panels.
WONG10 = [
    "#000000",  # 1 black
    "#E69F00",  # 2 orange
    "#56B4E9",  # 3 sky-blue
    "#009E73",  # 4 bluish-green
    "#F0E442",  # 5 yellow
    "#0072B2",  # 6 blue
    "#D55E00",  # 7 vermillion
    "#CC79A7",  # 8 reddish-purple
    "#7E7E7E",  # 9 grey-50
    "#A52A2A",  # 10 brown
]


def load_aois(trial_id: str) -> list[dict]:
    """Return list of {position, x, y, w, h} dicts in page-space."""
    path = DATA / "organic-boundary-data" / f"{trial_id}.json"
    raw = json.load(open(path))
    out = []
    for item in raw.get("organic_result", []):
        out.append(
            {
                "position": item["position"],
                "x": item["location"]["x"],
                "y": item["location"]["y"],
                "w": item["size"]["width"],
                "h": item["size"]["height"],
            }
        )
    return out


def load_mouse(trial_id: str) -> tuple[np.ndarray, np.ndarray, tuple[int, int] | None]:
    """Return (xs, ys, click_xy_or_None). Coords in page-space."""
    path = DATA / "mouse-movement-data" / f"{trial_id}.csv"
    xs, ys = [], []
    click = None
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = row["event"]
            if event in ("mousemove", "mouseover"):
                try:
                    x = float(row["xpos"])
                    y = float(row["ypos"])
                except (ValueError, KeyError):
                    continue
                xs.append(x)
                ys.append(y)
            if event == "click":
                try:
                    click = (float(row["xpos"]), float(row["ypos"]))
                except (ValueError, KeyError):
                    pass
    return np.array(xs), np.array(ys), click


def nearest_aoi(x: float, y: float, aois: list[dict]) -> int:
    """Return position (1-indexed) of AOI with center nearest to (x, y)."""
    best_i, best_d = -1, float("inf")
    for a in aois:
        cx = a["x"] + a["w"] / 2
        cy = a["y"] + a["h"] / 2
        d = math.hypot(x - cx, y - cy)
        if d < best_d:
            best_d = d
            best_i = a["position"]
    return best_i


def render_panel(ax, trial_id: str, label: str, aois: list[dict],
                 xs: np.ndarray, ys: np.ndarray, click: tuple[int, int] | None,
                 y_range: tuple[float, float] | None = None) -> None:
    # Use shared y-range if provided (keeps both panels visually comparable),
    # otherwise compute per-panel.
    if y_range is not None:
        y_top, y_bot = y_range
    else:
        margin = 60
        if len(ys):
            y_top = max(0, ys.min() - margin)
            y_bot = ys.max() + margin
        else:
            y_top = 0
            y_bot = max(a["y"] + a["h"] for a in aois)
        if click is not None:
            y_top = min(y_top, click[1] - margin)
            y_bot = max(y_bot, click[1] + margin)

    # AOI x-extent: full SERP width
    median_x = np.median([a["x"] for a in aois])
    median_w = np.median([a["w"] for a in aois])
    x_left = max(0, median_x - 30)
    x_right = median_x + median_w + 30

    # Filter AOIs to those that overlap the visible y-range
    visible_aois = [a for a in aois if (a["y"] + a["h"]) > y_top and a["y"] < y_bot]

    # Draw AOI rectangles (faint, just the position structure)
    for a in visible_aois:
        color = WONG10[(a["position"] - 1) % 10]
        rect = plt.Rectangle(
            (a["x"], a["y"]),
            a["w"], a["h"],
            facecolor=color, alpha=0.12,
            edgecolor=color, linewidth=0.6,
        )
        ax.add_patch(rect)
        ax.text(a["x"] + 6, a["y"] + 14, str(a["position"]),
                fontsize=9, color=color, fontweight="bold",
                va="top", ha="left", alpha=0.95)

    # Color cursor segments by nearest AOI (against ALL AOIs, not just visible)
    if len(xs) > 1:
        pos_seq = np.array([nearest_aoi(x, y, aois) for x, y in zip(xs, ys)])
        seg_xy = np.array([xs, ys]).T.reshape(-1, 1, 2)
        segments = np.concatenate([seg_xy[:-1], seg_xy[1:]], axis=1)
        colors = [WONG10[(pos_seq[i] - 1) % 10] for i in range(len(segments))]
        lc = LineCollection(segments, colors=colors, linewidths=1.6, alpha=0.85)
        ax.add_collection(lc)

    # Click star
    if click is not None:
        cx, cy = click
        ax.plot(cx, cy, marker="*", markersize=20,
                markerfacecolor="#FFD700", markeredgecolor="black",
                markeredgewidth=1.2, zorder=5)

    # Frame + axis
    ax.set_xlim(x_left, x_right)
    ax.set_ylim(y_bot, y_top)  # invert y so top-of-page is up
    # Don't lock aspect — lets each panel use its full allocated space
    # (slight horizontal stretch in regressive, slight compression in forward)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#555555")
        spine.set_linewidth(0.5)

    ax.set_title(label, fontsize=11, fontweight="bold", loc="left", pad=8)
    ax.text(x_right - 8, y_bot - 8, f"trial {trial_id}",
            fontsize=7, color="#777777", ha="right", va="bottom",
            family="monospace")


def main() -> None:
    aois_f = load_aois(FORWARD)
    xs_f, ys_f, click_f = load_mouse(FORWARD)
    print(f"forward {FORWARD}: {len(aois_f)} AOIs, {len(xs_f)} mouse samples, click={click_f}")

    aois_r = load_aois(REGRESSIVE)
    xs_r, ys_r, click_r = load_mouse(REGRESSIVE)
    print(f"regressive {REGRESSIVE}: {len(aois_r)} AOIs, {len(xs_r)} mouse samples, click={click_r}")

    fig, axes = plt.subplots(1, 2, figsize=(8.0, 5.5))
    render_panel(axes[0], FORWARD, "(a) Forward evaluation", aois_f, xs_f, ys_f, click_f)
    render_panel(axes[1], REGRESSIVE, "(b) Regressive re-examination", aois_r, xs_r, ys_r, click_r)

    fig.suptitle(
        "The cursor is one stream; each AOI claims its nearest segment.",
        fontsize=11, y=0.98, color="#222222", fontweight="normal",
    )
    fig.subplots_adjust(left=0.03, right=0.97, top=0.90, bottom=0.04, wspace=0.10)

    out_png = OUT / "intro_forward_vs_regressive.png"
    out_pdf = OUT / "intro_forward_vs_regressive.pdf"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


if __name__ == "__main__":
    main()
