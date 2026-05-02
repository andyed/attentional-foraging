"""Canonical cursor-gaze small-multiples array contrasting the three
approach-retreat outcome classes.

Builds on scripts/plot_approach_retreat_hero.py (cursor-only two-panel
hero figure) but:

  (a) overlays fixation dots alongside cursor paths so the viewer can
      see gaze AND mouse movement in the same frame
  (b) color-codes the cursor path by time so the reader follows the
      temporal direction at a glance
  (c) uses a 3 x N array layout across all three classes
      (clicked / deferred / evaluated-rejected) instead of 2 hand-picked
      exemplars
  (d) picks exemplars per class automatically based on proximity to the
      class median on the key motor-signature metrics, filtered for
      data quality (≥ 5 fixations, ≥ 10 cursor samples, episode duration
      between 0.5 and 10 seconds)

Output:
    scripts/output/figures/cursor_gaze_array.png  (and .pdf)
"""

from __future__ import annotations

import argparse

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events, get_trial_meta, result_band_tops,
    absolute_rank_band_tops,
)


def resolve_inputs(attribution: str) -> tuple[Path, Path, str]:
    """Return (features_path, reg_cache_path, output_suffix) for the chosen attribution.

    organic (default, post-2026-05-01 cascade) reads bbox-attributed inputs and
    writes to canonical filenames so paper drafts keep working.

    absolute writes to ``*_absolute.{png,pdf,_summary.json}`` so the legacy
    comparison can sit next to canonical without overwriting.
    """
    if attribution == "organic":
        return (
            ROOT / "AdSERP/data/cursor-approach-features-organic.json",
            ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json",
            "",
        )
    if attribution == "absolute":
        return (
            ROOT / "AdSERP/data/cursor-approach-features.json",
            ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json",
            "_absolute",
        )
    raise ValueError(f"unknown attribution: {attribution!r}")
OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_PER_CLASS = 3  # columns in the small-multiples grid

# ── Light editorial palette (matches render channels/science.md) ───────────
INK = "#1a1a2e"     # text + axis
MUTED = "#5a5a6a"   # secondary text + band outlines

CLASS_COLORS = {
    "clicked": "#2ca25f",
    "deferred": "#e08214",
    "evaluated-rejected": "#b2182b",
}

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
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def classify_records(raw, regression_labels):
    n = len(raw)
    labels = np.full(n, "", dtype="U25")
    min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
    was_clicked = np.array([r["was_clicked"] for r in raw], dtype=bool)
    approached = min_dist < 100
    labels[was_clicked] = "clicked"
    labels[~was_clicked & approached & regression_labels] = "deferred"
    labels[~was_clicked & approached & ~regression_labels] = "evaluated-rejected"
    labels[~was_clicked & ~approached] = "not-approached"
    return labels


def pick_exemplars(raw, labels, n_per_class=N_PER_CLASS):
    """Pick N exemplars per class at quality-filtered positions along the
    class-median vector of (min_dist, retreat_dist, total_dwell)."""
    picks = {}
    for cls in ("clicked", "deferred", "evaluated-rejected"):
        mask = np.where(labels == cls)[0]
        if len(mask) == 0:
            picks[cls] = []
            continue

        # Quality filter: reasonable duration, approached, has features
        candidates = []
        for i in mask:
            r = raw[i]
            entry = r.get("entry_t")
            exit_ = r.get("exit_t")
            n_fix = r.get("n_fixations", 0) or 0
            min_d = r.get("min_dist", 9999)
            if entry is None or exit_ is None:
                continue
            duration = exit_ - entry
            if duration < 500 or duration > 10_000:
                continue
            if n_fix < 5:
                continue
            if min_d > 120:   # episode where cursor barely approached — boring
                continue
            candidates.append(i)

        if len(candidates) < n_per_class:
            picks[cls] = candidates[:n_per_class]
            continue

        # Rank candidates by "typical-ness" — closeness to class median on
        # retreat_dist and total_dwell (after log-scaling and z-scoring)
        retreat = np.log1p(np.array([raw[i]["retreat_dist"] for i in candidates]))
        dwell = np.log1p(np.array([raw[i]["total_dwell_ms"] for i in candidates]))
        ret_z = (retreat - np.median(retreat)) / (np.std(retreat) + 1e-6)
        dwl_z = (dwell - np.median(dwell)) / (np.std(dwell) + 1e-6)
        typicality = np.sqrt(ret_z ** 2 + dwl_z ** 2)

        # Sort by typicality and take N spread across the distribution
        order = np.argsort(typicality)
        # Pick N evenly spaced within the most typical 50% to get variety
        top_half = order[:max(n_per_class * 3, len(order) // 2)]
        if len(top_half) <= n_per_class:
            chosen = top_half
        else:
            step = len(top_half) // n_per_class
            chosen = top_half[::step][:n_per_class]
        picks[cls] = [candidates[c] for c in chosen]
    return picks


def collect_episode_data(raw, i, pad_ms=250):
    """Load fixations + cursor path for one record's episode."""
    r = raw[i]
    tid = r["trial_id"]
    entry = r["entry_t"]
    exit_ = r["exit_t"]
    try:
        fixes = load_fixations(tid)
        events, _, clicks = load_mouse_events(tid)
        doc_h, _, _ = get_trial_meta(tid)
    except Exception:
        return None
    if doc_h is None:
        return None

    # Cursor positions in the window (+padding for context)
    pos_evts = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    curs = [(t, x, y) for (t, ev, x, y) in events
            if ev in pos_evts and entry - pad_ms <= t <= exit_ + pad_ms]
    if len(curs) < 5:
        return None
    ct = np.array([c[0] for c in curs], dtype=np.int64)
    cx = np.array([c[1] for c in curs], dtype=float)
    cy = np.array([c[2] for c in curs], dtype=float)

    # Fixations in the window
    window_fixes = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(window_fixes) < 2:
        return None
    fx = np.array([f["x"] for f in window_fixes], dtype=float)
    fy = np.array([f["y"] for f in window_fixes], dtype=float)
    fd = np.array([f["d"] for f in window_fixes], dtype=float)  # duration ms
    ft = np.array([f["t"] for f in window_fixes], dtype=np.int64)

    # Result band tops
    try:
        tops = result_band_tops(10, doc_h)
    except Exception:
        return None
    band_top = tops[r["position"]] if r["position"] < len(tops) else None
    if band_top is None:
        return None
    if r["position"] + 1 < len(tops):
        band_bot = tops[r["position"] + 1]
    else:
        band_bot = band_top + 160  # fallback height

    return {
        "record": r,
        "tid": tid,
        "entry": entry,
        "exit": exit_,
        "cursor": (ct, cx, cy),
        "fixations": (ft, fx, fy, fd),
        "band_top": band_top,
        "band_bot": band_bot,
        "position": r["position"],
        "click_event": clicks[0] if clicks else None,
    }


def draw_panel(ax, data, cls, is_first_in_row=False):
    """Draw one cursor+gaze panel."""
    color = CLASS_COLORS[cls]

    ct, cx, cy = data["cursor"]
    ft, fx, fy, fd = data["fixations"]
    band_top = data["band_top"]
    band_bot = data["band_bot"]
    entry, exit_ = data["entry"], data["exit"]
    pos = data["position"]

    # Zoom: center on cursor + gaze action
    all_x = np.concatenate([cx, fx])
    all_y = np.concatenate([cy, fy, [band_top, band_bot]])
    x_lo = float(all_x.min()) - 40
    x_hi = float(all_x.max()) + 40
    y_lo = float(all_y.min()) - 30
    y_hi = float(all_y.max()) + 30

    # Width at least 500 px for readability
    if x_hi - x_lo < 500:
        mid = (x_lo + x_hi) / 2
        x_lo = mid - 250
        x_hi = mid + 250

    # Target result band rectangle
    band_rect = mpatches.Rectangle(
        (x_lo + 2, band_top), x_hi - x_lo - 4, band_bot - band_top,
        linewidth=1.4, edgecolor=INK, facecolor="#f4f4f4",
        alpha=0.85, zorder=1,
    )
    ax.add_patch(band_rect)
    ax.text(
        x_lo + 12, band_top + 12, f"result {pos}",
        fontsize=8, color=MUTED, va="top", zorder=2,
    )

    # Cursor path — thin blue line with arrows for direction
    ax.plot(cx, cy, color="#1f4e8c", linewidth=1.8, alpha=0.85,
            zorder=3, solid_capstyle="round")

    # Arrows along the cursor path (sparse — every Nth segment)
    n_arrows = min(5, max(2, len(cx) // 8))
    idxs = np.linspace(0, len(cx) - 2, n_arrows, dtype=int)
    for k in idxs:
        if k + 1 >= len(cx):
            continue
        dx = cx[k + 1] - cx[k]
        dy = cy[k + 1] - cy[k]
        if dx == 0 and dy == 0:
            continue
        ax.annotate(
            "", xy=(cx[k + 1], cy[k + 1]), xytext=(cx[k], cy[k]),
            arrowprops=dict(arrowstyle="->", color="#1f4e8c",
                            lw=1.4, alpha=0.85),
            zorder=3,
        )

    # Cursor start + end markers
    ax.scatter(cx[0], cy[0], s=70, color="#1f4e8c", edgecolors=INK,
               linewidth=1.0, zorder=5, marker="s", label="cursor start")
    ax.scatter(cx[-1], cy[-1], s=70, color="#1f4e8c", edgecolors=INK,
               linewidth=1.0, zorder=5, marker="D", label="cursor end")

    # Fixations — sorted by time, numbered in order
    order = np.argsort(ft)
    fx_ord = fx[order]
    fy_ord = fy[order]
    fd_ord = fd[order]
    fix_sizes = np.clip(fd_ord * 0.25, 30, 220)
    ax.scatter(fx_ord, fy_ord, s=fix_sizes, facecolor="white",
               edgecolors=color, linewidth=2.0, zorder=4)
    for k, (x_, y_) in enumerate(zip(fx_ord, fy_ord)):
        ax.text(x_, y_, str(k + 1), fontsize=8, color=color,
                ha="center", va="center", fontweight="bold", zorder=5)

    # Click marker if applicable
    if cls == "clicked" and data["click_event"]:
        _, click_x, click_y = data["click_event"]
        if x_lo <= click_x <= x_hi and y_lo <= click_y <= y_hi:
            ax.scatter(click_x, click_y, s=240, marker="*",
                       color="#fef08a", edgecolors="#166534", linewidth=1.5,
                       zorder=6)

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_hi, y_lo)   # invert y — page coords
    ax.set_aspect("auto")
    ax.set_xticks([])
    ax.set_yticks([])

    # Episode stats callout
    r = data["record"]
    dur_s = (exit_ - entry) / 1000
    txt = (
        f"{data['tid']} · p{pos}\n"
        f"min {r['min_dist']:.0f} · retreat {r['retreat_dist']:.0f} · "
        f"{dur_s:.1f}s · {len(fx)} fix"
    )
    ax.text(0.02, 0.02, txt, transform=ax.transAxes, fontsize=8,
            color=MUTED, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="none", alpha=0.85))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribution", choices=["organic", "absolute"], default="organic",
                    help="organic (default; bbox-attributed) or absolute (legacy h3+ads pooled)")
    args = ap.parse_args()
    features_path, reg_cache_path, suffix = resolve_inputs(args.attribution)
    print(f"attribution: {args.attribution}")
    print(f"  features: {features_path.name}")
    print(f"  reg cache: {reg_cache_path.name}")
    print("loading features + regression labels...")
    raw = json.load(open(features_path))
    regression_labels = np.array(json.load(open(reg_cache_path)), dtype=bool)
    assert len(regression_labels) == len(raw)

    labels = classify_records(raw, regression_labels)
    picks = pick_exemplars(raw, labels, n_per_class=N_PER_CLASS)
    for cls, ix in picks.items():
        print(f"  {cls}: {len(ix)} exemplars picked")

    # Collect episode data for each pick
    panels = {}
    for cls, ix_list in picks.items():
        panels[cls] = []
        for i in ix_list:
            data = collect_episode_data(raw, i)
            if data is not None:
                panels[cls].append(data)
        print(f"  {cls}: {len(panels[cls])} exemplars with valid data")

    # Build the figure
    n_rows = 3
    n_cols = N_PER_CLASS
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(n_cols * 4.8, n_rows * 4.0),
        gridspec_kw={"wspace": 0.12, "hspace": 0.22},
    )
    row_order = ["clicked", "deferred", "evaluated-rejected"]
    row_labels = {
        "clicked": "CLICKED\n(terminal commit)",
        "deferred": "DEFERRED\n(approached, later scroll-regressed back)",
        "evaluated-rejected": "EVALUATED-REJECTED\n(approached, never returned)",
    }

    for row, cls in enumerate(row_order):
        exemplars = panels.get(cls, [])
        for col in range(n_cols):
            ax = axes[row, col]
            if col < len(exemplars):
                draw_panel(ax, exemplars[col], cls, is_first_in_row=(col == 0))
            else:
                ax.axis("off")

        # Row label on the left of first panel
        if exemplars:
            axes[row, 0].text(
                -0.11, 0.5, row_labels[cls],
                transform=axes[row, 0].transAxes,
                rotation=90, va="center", ha="center",
                color=CLASS_COLORS[cls], fontsize=11, fontweight="bold",
            )

    fig.suptitle(
        "Cursor trajectories + numbered fixations by outcome class\n"
        "Blue line = cursor path (square = start, diamond = end). "
        "Numbered circles = fixations in temporal order, sized by duration. "
        "Yellow star = click.",
        fontsize=12, fontweight="semibold", y=0.995,
    )

    plt.subplots_adjust(top=0.91, bottom=0.04, left=0.08, right=0.98)

    out_png = OUT_DIR / f"cursor_gaze_array{suffix}.png"
    out_pdf = OUT_DIR / f"cursor_gaze_array{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")


if __name__ == "__main__":
    main()
