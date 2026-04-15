"""Pooled gaze density around the parked cursor anchor — three classes.

Complement to render_coupling_traces.py. Instead of the time-series of
cursor-gaze distance, this figure shows the *spatial* density of gaze
relative to the cursor anchor, pooled across every episode in each class.

For every episode we compute the cursor's median position (x0, y0) —
the "parked" anchor — and subtract it from every fixation (fx-x0, fy-y0).
The offsets from all episodes in a class are pooled into a 2D histogram
and smoothed into a Tobii-style heatmap.

This reliably shows the population pattern that individual exemplars
can't: eval-rejected gaze clusters tightly on the anchor, deferred gaze
fans to one side (the "offset hold"), clicked gaze spreads widest before
converging at click.

Output:
    scripts/output/figures/gaze_density_class.png  (and .pdf)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OFFSET_CACHE = OUT_DIR / "per_record_gaze_offsets.json"

# View window in px (square, centered on cursor anchor at origin)
EXTENT = 600     # ±600 px around anchor
BIN_PX = 12      # histogram cell size → 100×100 grid
SIGMA = 3.0      # gaussian smoothing in bins (≈ 36 px)

INK = "#1a1a2e"
MUTED = "#5a5a6a"

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


def compute_record_offsets(raw, i):
    """Per-fixation (dx, dy, duration) offsets from cursor anchor for one record."""
    r = raw[i]
    tid = r["trial_id"]
    entry = r["entry_t"]
    exit_ = r["exit_t"]
    try:
        fixes = load_fixations(tid)
        events, _, _ = load_mouse_events(tid)
    except Exception:
        return None

    pos_evts = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    curs = [(x, y) for (t, ev, x, y) in events
            if ev in pos_evts and entry <= t <= exit_]
    if len(curs) < 5:
        return None
    cx = np.array([c[0] for c in curs], dtype=float)
    cy = np.array([c[1] for c in curs], dtype=float)
    cx_med = float(np.median(cx))
    cy_med = float(np.median(cy))

    wfix = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(wfix) < 3:
        return None

    out = []
    for f in wfix:
        dx = float(f["x"]) - cx_med
        dy = float(f["y"]) - cy_med
        dur = float(f.get("d", 200))
        out.append((dx, dy, dur))
    return out


def compute_all_offsets(raw):
    """Compute per-fixation offsets for every record. Cached."""
    if OFFSET_CACHE.exists():
        print(f"loading cached offsets from {OFFSET_CACHE}")
        cached = json.load(open(OFFSET_CACHE))
        return {int(k): v for k, v in cached.items()}

    print("computing per-record gaze offsets (expensive, ~5 min)...")
    out = {}
    n = len(raw)
    for i in range(n):
        if i % 1000 == 0:
            print(f"  {i}/{n} records...")
        offsets = compute_record_offsets(raw, i)
        if offsets is not None:
            out[i] = offsets

    OFFSET_CACHE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({str(k): v for k, v in out.items()}, open(OFFSET_CACHE, "w"))
    print(f"  cached to {OFFSET_CACHE}")
    return out


def build_density(all_offsets, labels, cls, weight_by_duration=True):
    """Aggregate 2D histogram + gaussian smoothing for one class."""
    mask = np.where(labels == cls)[0]
    xs, ys, ws = [], [], []
    n_records = 0
    for i in mask:
        if i not in all_offsets:
            continue
        offsets = all_offsets[i]
        if not offsets:
            continue
        n_records += 1
        for dx, dy, dur in offsets:
            # Clip to window so out-of-range fixations still count at border
            if abs(dx) > EXTENT or abs(dy) > EXTENT:
                continue
            xs.append(dx)
            ys.append(dy)
            ws.append(dur if weight_by_duration else 1.0)

    xs = np.array(xs)
    ys = np.array(ys)
    ws = np.array(ws)

    n_bins = int(2 * EXTENT / BIN_PX)
    edges = np.linspace(-EXTENT, EXTENT, n_bins + 1)
    H, _, _ = np.histogram2d(
        ys, xs, bins=[edges, edges], weights=ws,
    )
    # Smooth
    H_smooth = gaussian_filter(H, sigma=SIGMA)
    return H_smooth, n_records, len(xs)


def main():
    print("loading features + regression labels...")
    raw = json.load(open(FEATURES_JSON))
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    labels = classify_records(raw, regression_labels)

    all_offsets = compute_all_offsets(raw)
    print(f"  {len(all_offsets)} records have valid offsets")

    class_order = ["evaluated-rejected", "deferred", "clicked"]
    densities = {}
    pooled_counts = {}
    for cls in class_order:
        H, n_records, n_fix = build_density(all_offsets, labels, cls)
        densities[cls] = H
        pooled_counts[cls] = (n_records, n_fix)
        print(f"  {cls}: {n_records:,} records, {n_fix:,} fixations pooled")

    # Global normalization — scale each class's density to its own peak so
    # spatial pattern is readable even when absolute counts differ wildly
    # (clicked has 5× the episodes of eval-rejected).
    per_class_max = {cls: float(H.max()) for cls, H in densities.items()}

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5),
                              gridspec_kw={"wspace": 0.12})
    class_labels_human = {
        "clicked": "CLICKED",
        "deferred": "DEFERRED",
        "evaluated-rejected": "EVALUATED-REJECTED",
    }
    class_subtitles = {
        "clicked": "cursor held far from gaze\nthroughout approach",
        "deferred": "cursor parked at offset\nwhile gaze revisits",
        "evaluated-rejected": "cursor tracks gaze closely\n(tightest coupling)",
    }

    extent_arr = [-EXTENT, EXTENT, EXTENT, -EXTENT]  # note: imshow y flip
    class_n = {cls: int((labels == cls).sum()) for cls in class_order}

    for col, cls in enumerate(class_order):
        ax = axes[col]
        H = densities[cls]
        vmax = per_class_max[cls]
        # Mild log-like stretch via sqrt to spread the dynamic range
        H_show = np.sqrt(H / max(vmax, 1e-9))

        im = ax.imshow(
            H_show, extent=extent_arr, origin="upper",
            cmap="magma", vmin=0, vmax=1,
            interpolation="bilinear", aspect="equal",
        )

        # Crosshair at cursor anchor (origin)
        ax.axhline(0, color="#ffffff", linewidth=0.8, alpha=0.4, zorder=3)
        ax.axvline(0, color="#ffffff", linewidth=0.8, alpha=0.4, zorder=3)
        # Anchor marker
        ax.scatter([0], [0], s=180, marker="o", color="#1f4e8c",
                    edgecolors="white", linewidth=2.0, zorder=5)
        ax.text(0, -20, "cursor anchor", fontsize=9, color="white",
                ha="center", va="bottom", fontweight="semibold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#1f4e8c",
                          edgecolor="none", alpha=0.85))

        color = CLASS_COLORS[cls]
        n_rec, n_fix = pooled_counts[cls]
        ax.set_title(
            f"{class_labels_human[cls]}\n"
            f"{n_rec:,} of {class_n[cls]:,} episodes · {n_fix:,} fixations pooled",
            fontsize=12.5, fontweight="semibold", color=color, pad=8,
        )
        ax.text(
            0.02, 0.98, class_subtitles[cls],
            transform=ax.transAxes, fontsize=9, color="white",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#00000088",
                      edgecolor="none"),
        )

        # Scale bar: 200 px, bottom-right
        bar_x0 = EXTENT - 240
        bar_x1 = EXTENT - 40
        bar_y = EXTENT - 60
        ax.plot([bar_x0, bar_x1], [bar_y, bar_y], color="white",
                linewidth=3.0, zorder=4)
        ax.text((bar_x0 + bar_x1) / 2, bar_y - 18, "200 px",
                color="white", fontsize=9, ha="center", va="bottom",
                fontweight="semibold", zorder=5)

        ax.set_xlim(-EXTENT, EXTENT)
        ax.set_ylim(EXTENT, -EXTENT)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#d4d4d4")
            spine.set_linewidth(0.8)

        if col == 0:
            ax.set_ylabel(
                "Gaze offset from cursor anchor (px)",
                fontweight="semibold", color=INK,
            )

    fig.suptitle(
        "Pooled gaze density around the parked cursor — three coupling regimes\n"
        "Each panel: every fixation in the class, recentered on its episode's cursor median. "
        "Brighter = more gaze density. Each class normalized to its own peak.",
        fontsize=12, fontweight="semibold", y=1.02,
    )

    out_png = OUT_DIR / "gaze_density_class.png"
    out_pdf = OUT_DIR / "gaze_density_class.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")

    # ── Persist machine-readable stats alongside the figure ──
    out_json = OUT_DIR / "gaze_density_class_summary.json"
    summary = {
        "figure": "gaze_density_class.png",
        "script": "scripts/render_gaze_density.py",
        "generated": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "config": {
            "extent_px": EXTENT,
            "bin_px": BIN_PX,
            "smoothing_sigma_bins": SIGMA,
            "weighted_by_fixation_duration": True,
            "normalization": "per-class peak",
            "colormap": "magma",
        },
        "per_class": {},
    }
    for cls in class_order:
        n_rec, n_fix = pooled_counts[cls]
        # Radial magnitude distribution (how far from cursor anchor)
        mask = np.where(labels == cls)[0]
        radii = []
        for i in mask:
            if i in all_offsets:
                for dx, dy, _dur in all_offsets[i]:
                    if abs(dx) <= EXTENT and abs(dy) <= EXTENT:
                        radii.append(float(np.hypot(dx, dy)))
        radii_arr = np.array(radii) if radii else np.array([0.0])
        summary["per_class"][cls] = {
            "class_n_total": int(class_n[cls]),
            "class_n_pooled": int(n_rec),
            "n_fixations_pooled": int(n_fix),
            "radial_offset_px": {
                "median": float(np.median(radii_arr)),
                "p25": float(np.percentile(radii_arr, 25)),
                "p75": float(np.percentile(radii_arr, 75)),
                "p90": float(np.percentile(radii_arr, 90)),
                "mean": float(radii_arr.mean()),
            },
            "density_peak_value": float(densities[cls].max()),
        }
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
