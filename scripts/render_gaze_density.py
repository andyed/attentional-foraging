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

import argparse

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
    """Per-fixation (dx, dy, duration) offsets from the cursor position
    at the fixation's timestamp (nearest-in-time interpolation).

    This is the same reference frame used by render_coupling_traces.py,
    so the r50 density concentration radius is directly comparable to
    the followup_peter_leif cursor-gaze coupling median.
    """
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
    curs = [(t, x, y) for (t, ev, x, y) in events
            if ev in pos_evts and entry <= t <= exit_]
    if len(curs) < 5:
        return None
    m_ts = np.array([c[0] for c in curs], dtype=np.int64)
    m_xs = np.array([c[1] for c in curs], dtype=float)
    m_ys = np.array([c[2] for c in curs], dtype=float)

    wfix = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(wfix) < 3:
        return None

    out = []
    for f in wfix:
        ft = int(f["t"])
        pos = int(np.searchsorted(m_ts, ft))
        if pos == 0:
            j = 0
        elif pos >= len(m_ts):
            j = len(m_ts) - 1
        else:
            j = pos if abs(m_ts[pos] - ft) < abs(m_ts[pos - 1] - ft) else pos - 1
        dx = float(f["x"]) - float(m_xs[j])
        dy = float(f["y"]) - float(m_ys[j])
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

    out_png = OUT_DIR / f"gaze_density_class{suffix}.png"
    out_pdf = OUT_DIR / f"gaze_density_class{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")

    # ── Persist machine-readable stats alongside the figure ──
    out_json = OUT_DIR / f"gaze_density_class{suffix}_summary.json"
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
    # Precompute per-bin radius from origin once (grid is square, symmetric)
    n_bins = int(2 * EXTENT / BIN_PX)
    bin_edges = np.linspace(-EXTENT, EXTENT, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bx, by = np.meshgrid(bin_centers, bin_centers)
    bin_radius = np.hypot(bx, by)

    for cls in class_order:
        n_rec, n_fix = pooled_counts[cls]
        H = densities[cls]

        # Two aggregations, both from (dx, dy) offsets with cursor at
        # fixation timestamp — the same reference frame as followup.
        mask = np.where(labels == cls)[0]
        per_episode_medians = []  # median-of-medians — matches followup
        pooled_radii = []         # pooled — heatmap sees this distribution
        for i in mask:
            if i not in all_offsets:
                continue
            offs = all_offsets[i]
            if not offs:
                continue
            rs = [float(np.hypot(dx, dy)) for dx, dy, _dur in offs]
            per_episode_medians.append(float(np.median(rs)))
            pooled_radii.extend(rs)

        per_ep_arr = np.array(per_episode_medians)
        pooled_arr = np.array(pooled_radii)

        summary["per_class"][cls] = {
            "class_n_total": int(class_n[cls]),
            "class_n_pooled": int(n_rec),
            "n_fixations_pooled": int(n_fix),
            "cursor_gaze_distance_px": {
                "median_of_episode_medians": float(np.median(per_ep_arr)),
                "mean_of_episode_medians": float(per_ep_arr.mean()),
                "episode_median_p25": float(np.percentile(per_ep_arr, 25)),
                "episode_median_p75": float(np.percentile(per_ep_arr, 75)),
                "pooled_fixation_median": float(np.median(pooled_arr)),
                "pooled_fixation_p25": float(np.percentile(pooled_arr, 25)),
                "pooled_fixation_p75": float(np.percentile(pooled_arr, 75)),
            },
            "density_peak_value": float(densities[cls].max()),
            "note": (
                "median_of_episode_medians is the canonical coupling "
                "statistic — each episode contributes one value (median "
                "of its per-fixation cursor-gaze distances), then median "
                "across episodes. Matches scripts/output/followup_peter_leif "
                "and the §5 paper language. pooled_fixation_median pools "
                "all fixations into one bag, so long episodes dominate — "
                "this is the distribution the heatmap visualizes, not the "
                "coupling statistic. Cursor position is nearest-in-time "
                "to each fixation."
            ),
        }
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
