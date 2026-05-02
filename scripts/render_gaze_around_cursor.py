"""Gaze scanpath around the parked cursor — small multiples contrasting the
three approach-retreat outcome classes.

Companion to render_coupling_traces.py. Where the coupling-traces figure shows
the time-series of cursor-gaze distance, this figure shows the *spatial*
relationship: the cursor is reduced to a single anchored marker (its median
position during the episode) and the eye's scanpath is drawn around it.

Reveals the per-class pattern the aggregate statistics imply:
  - eval-rejected: gaze clusters tightly on top of the cursor (tight coupling)
  - deferred:      gaze fans outward from the parked cursor (offset pattern)
  - clicked:       gaze wanders the page while the cursor trails behind,
                   converging only at the final commit

Output:
    scripts/output/figures/gaze_around_cursor.png (and .pdf)
"""

from __future__ import annotations

import argparse

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events, get_trial_meta, result_band_tops,
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

N_PER_CLASS = 4  # columns per row

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


def pick_exemplars(raw, labels, n_per_class=N_PER_CLASS):
    """Pick N exemplars per class — quality-filtered, then ranked by
    closeness to the class median on (retreat_dist, total_dwell)."""
    picks = {}
    for cls in ("clicked", "deferred", "evaluated-rejected"):
        mask = np.where(labels == cls)[0]
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
            if duration < 800 or duration > 7000:
                continue
            if n_fix < 5:
                continue
            if min_d > 100:
                continue
            candidates.append(i)

        if len(candidates) < n_per_class:
            picks[cls] = candidates[:n_per_class]
            continue

        retreat = np.log1p(np.array([raw[i]["retreat_dist"] for i in candidates]))
        dwell = np.log1p(np.array([raw[i]["total_dwell_ms"] for i in candidates]))
        ret_z = (retreat - np.median(retreat)) / (np.std(retreat) + 1e-6)
        dwl_z = (dwell - np.median(dwell)) / (np.std(dwell) + 1e-6)
        typicality = np.sqrt(ret_z ** 2 + dwl_z ** 2)
        order = np.argsort(typicality)
        top = order[:max(n_per_class * 3, len(order) // 3)]
        if len(top) <= n_per_class:
            chosen = top
        else:
            step = max(1, len(top) // n_per_class)
            chosen = top[::step][:n_per_class]
        picks[cls] = [candidates[c] for c in chosen]
    return picks


def collect_episode_data(raw, i, pad_ms=200):
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

    pos_evts = {"mousemove", "mouseover", "mouseout", "mousedown", "mouseup", "click"}
    curs = [(t, x, y) for (t, ev, x, y) in events
            if ev in pos_evts and entry - pad_ms <= t <= exit_ + pad_ms]
    if len(curs) < 5:
        return None
    ct = np.array([c[0] for c in curs], dtype=np.int64)
    cx = np.array([c[1] for c in curs], dtype=float)
    cy = np.array([c[2] for c in curs], dtype=float)

    wfix = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(wfix) < 3:
        return None
    wfix.sort(key=lambda f: f["t"])
    fx = np.array([f["x"] for f in wfix], dtype=float)
    fy = np.array([f["y"] for f in wfix], dtype=float)
    fd = np.array([f["d"] for f in wfix], dtype=float)
    ft = np.array([f["t"] for f in wfix], dtype=np.int64)

    try:
        tops = result_band_tops(10, doc_h)
    except Exception:
        return None
    band_top = tops[r["position"]] if r["position"] < len(tops) else None
    if band_top is None:
        return None
    band_bot = tops[r["position"] + 1] if r["position"] + 1 < len(tops) else band_top + 160

    return {
        "record": r,
        "tid": tid,
        "entry": entry,
        "exit": exit_,
        "cursor_t": ct,
        "cursor_x": cx,
        "cursor_y": cy,
        "fix_t": ft,
        "fix_x": fx,
        "fix_y": fy,
        "fix_d": fd,
        "band_top": band_top,
        "band_bot": band_bot,
        "position": r["position"],
        "click_event": clicks[0] if clicks else None,
    }


def draw_panel(ax, data, cls):
    """Draw a gaze scanpath around the parked cursor."""
    color = CLASS_COLORS[cls]

    cx, cy = data["cursor_x"], data["cursor_y"]
    fx, fy, fd, ft = data["fix_x"], data["fix_y"], data["fix_d"], data["fix_t"]
    band_top, band_bot = data["band_top"], data["band_bot"]
    pos = data["position"]

    # Cursor "parked" position — median over the episode. This is the anchor.
    cx_med = float(np.median(cx))
    cy_med = float(np.median(cy))

    # Cursor movement radius — the IQR of cursor positions. Small for
    # parked cursors, large for wandering cursors.
    cx_iqr = float(np.percentile(cx, 75) - np.percentile(cx, 25))
    cy_iqr = float(np.percentile(cy, 75) - np.percentile(cy, 25))
    cursor_spread = float(np.hypot(cx_iqr, cy_iqr))

    # View window: center on the cursor anchor, include all fixations + padding
    all_x = np.concatenate([fx, [cx_med]])
    all_y = np.concatenate([fy, [cy_med, band_top, band_bot]])
    x_lo = float(all_x.min()) - 40
    x_hi = float(all_x.max()) + 40
    y_lo = float(all_y.min()) - 30
    y_hi = float(all_y.max()) + 30
    if x_hi - x_lo < 450:
        mid = (x_lo + x_hi) / 2
        x_lo, x_hi = mid - 225, mid + 225
    if y_hi - y_lo < 220:
        mid = (y_lo + y_hi) / 2
        y_lo, y_hi = mid - 110, mid + 110

    # Target band backdrop
    band_rect = mpatches.Rectangle(
        (x_lo + 2, band_top), x_hi - x_lo - 4, band_bot - band_top,
        linewidth=1.0, edgecolor="#d4d4d4", facecolor="#f7f7f7",
        alpha=0.8, zorder=1,
    )
    ax.add_patch(band_rect)
    ax.text(x_lo + 10, band_top + 10, f"result {pos}",
            fontsize=7, color=MUTED, va="top", zorder=2)

    # Cursor "spread" — a faint circle showing how much the cursor wandered
    # from its median. Tight circle = parked. Large circle = wandering.
    if cursor_spread > 0:
        cursor_halo = mpatches.Circle(
            (cx_med, cy_med), radius=max(cursor_spread / 2, 8),
            linewidth=1.2, edgecolor="#1f4e8c", facecolor="#e8eef5",
            linestyle="--", alpha=0.7, zorder=2,
        )
        ax.add_patch(cursor_halo)

    # Saccade lines connecting fixations in temporal order
    order = np.argsort(ft)
    fx_ord = fx[order]
    fy_ord = fy[order]
    fd_ord = fd[order]
    for k in range(len(fx_ord) - 1):
        ax.plot(
            [fx_ord[k], fx_ord[k + 1]],
            [fy_ord[k], fy_ord[k + 1]],
            color=color, linewidth=1.2, alpha=0.55, zorder=3,
            solid_capstyle="round",
        )

    # Fixation circles — sized by duration, numbered in order
    fix_sizes = np.clip(fd_ord * 0.35, 50, 320)
    ax.scatter(fx_ord, fy_ord, s=fix_sizes, facecolor="white",
               edgecolors=color, linewidth=2.0, zorder=4)
    for k, (x_, y_) in enumerate(zip(fx_ord, fy_ord)):
        ax.text(x_, y_, str(k + 1), fontsize=7.5, color=color,
                ha="center", va="center", fontweight="bold", zorder=5)

    # Cursor anchor marker — solid blue dot ON TOP so it reads as "parked here"
    ax.scatter([cx_med], [cy_med], s=180, color="#1f4e8c",
               edgecolors="white", linewidth=2.0, zorder=6, marker="o")
    ax.text(cx_med, cy_med - 14, "cursor", fontsize=7,
            color="#1f4e8c", ha="center", va="bottom",
            fontweight="semibold", zorder=7,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.85))

    # Click marker if applicable — yellow star at the click point
    if cls == "clicked" and data["click_event"]:
        _, click_x, click_y = data["click_event"]
        if x_lo <= click_x <= x_hi and y_lo <= click_y <= y_hi:
            ax.scatter(click_x, click_y, s=260, marker="*",
                       color="#fef08a", edgecolors="#166534", linewidth=1.5,
                       zorder=7)

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_hi, y_lo)
    ax.set_aspect("auto")
    ax.set_xticks([])
    ax.set_yticks([])

    # Stats callout — gaze-to-cursor distance aggregate, duration, n_fix
    r = data["record"]
    dur_s = (data["exit"] - data["entry"]) / 1000
    # Per-fixation cursor-gaze distance (to the parked anchor)
    dists = np.hypot(fx - cx_med, fy - cy_med)
    median_d = float(np.median(dists))
    txt = (
        f"{data['tid']} · p{pos} · {dur_s:.1f}s · {len(fx)} fix\n"
        f"gaze-to-anchor: median {median_d:.0f}px"
    )
    ax.text(0.02, 0.02, txt, transform=ax.transAxes, fontsize=7.5,
            color=MUTED, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="none", alpha=0.9))


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

    panels = {}
    for cls, ix_list in picks.items():
        panels[cls] = []
        for i in ix_list:
            data = collect_episode_data(raw, i)
            if data is not None:
                panels[cls].append(data)
        print(f"  {cls}: {len(panels[cls])} exemplars with valid data")

    n_rows = 3
    n_cols = N_PER_CLASS
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(n_cols * 4.2, n_rows * 3.6),
        gridspec_kw={"wspace": 0.1, "hspace": 0.18},
    )
    row_order = ["evaluated-rejected", "deferred", "clicked"]
    row_labels = {
        "clicked": "CLICKED\n(gaze roams page,\ncursor trails)",
        "deferred": "DEFERRED\n(gaze revisits,\ncursor parked offset)",
        "evaluated-rejected": "EVALUATED-REJECTED\n(gaze clusters\non parked cursor)",
    }

    for row, cls in enumerate(row_order):
        exemplars = panels.get(cls, [])
        for col in range(n_cols):
            ax = axes[row, col]
            if col < len(exemplars):
                draw_panel(ax, exemplars[col], cls)
            else:
                ax.axis("off")

        if exemplars:
            axes[row, 0].text(
                -0.12, 0.5, row_labels[cls],
                transform=axes[row, 0].transAxes,
                rotation=90, va="center", ha="center",
                color=CLASS_COLORS[cls], fontsize=10.5, fontweight="bold",
            )

    fig.suptitle(
        "Gaze scanpath around the parked cursor — three coupling regimes\n"
        "Blue dot = cursor median position (the anchor). Dashed halo = cursor IQR (spread). "
        "Numbered circles = fixations in order, sized by duration. Lines = saccades. Yellow star = click.",
        fontsize=12, fontweight="semibold", y=0.995,
    )
    plt.subplots_adjust(top=0.91, bottom=0.04, left=0.08, right=0.98)

    out_png = OUT_DIR / f"gaze_around_cursor{suffix}.png"
    out_pdf = OUT_DIR / f"gaze_around_cursor{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")


if __name__ == "__main__":
    main()
