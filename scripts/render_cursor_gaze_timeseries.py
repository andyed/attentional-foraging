"""Canonical cursor-vs-gaze time-series small-multiples array for the
three approach-retreat outcome classes.

Complements render_cursor_gaze_array.py (which shows spatial
trajectories). This figure puts time on the x-axis and shows how
cursor-y and gaze-y move relative to the target result band across
the episode window.

The time-series view makes the motor-signature dissociation visible
in a way the spatial view cannot: evaluated-rejected episodes have
short focused visits where gaze and cursor travel nearly in lockstep;
deferred episodes have long multi-visit gaze patterns where the
cursor holds steady at an offset position; clicked episodes show the
cursor converging on the gaze at the click event.

Output:
    scripts/output/figures/cursor_gaze_timeseries.png  (and .pdf)
"""

from __future__ import annotations

import argparse

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
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

N_PER_CLASS = 3
INK = "#1a1a2e"
MUTED = "#5a5a6a"
CURSOR_COLOR = "#1f4e8c"
GAZE_COLOR = "#d7301f"
BAND_FILL = "#f3f3f7"

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
            # For timeseries clarity, prefer episodes 1-6 seconds
            if duration < 1000 or duration > 6000:
                continue
            if n_fix < 6:
                continue
            if min_d > 100:
                continue
            candidates.append(i)

        if len(candidates) < n_per_class:
            picks[cls] = candidates[:n_per_class]
            continue

        # Rank by typicality
        retreat = np.log1p(np.array([raw[i]["retreat_dist"] for i in candidates]))
        dwell = np.log1p(np.array([raw[i]["total_dwell_ms"] for i in candidates]))
        ret_z = (retreat - np.median(retreat)) / (np.std(retreat) + 1e-6)
        dwl_z = (dwell - np.median(dwell)) / (np.std(dwell) + 1e-6)
        typicality = np.sqrt(ret_z ** 2 + dwl_z ** 2)
        order = np.argsort(typicality)
        top_half = order[:max(n_per_class * 3, len(order) // 2)]
        if len(top_half) <= n_per_class:
            chosen = top_half
        else:
            step = len(top_half) // n_per_class
            chosen = top_half[::step][:n_per_class]
        picks[cls] = [candidates[c] for c in chosen]
    return picks


def collect_episode(raw, i):
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
            if ev in pos_evts and entry <= t <= exit_]
    if len(curs) < 5:
        return None
    ct = np.array([c[0] - entry for c in curs], dtype=float)
    cx = np.array([c[1] for c in curs], dtype=float)
    cy = np.array([c[2] for c in curs], dtype=float)

    wfix = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(wfix) < 3:
        return None
    ft = np.array([f["t"] - entry for f in wfix], dtype=float)
    fx = np.array([f["x"] for f in wfix], dtype=float)
    fy = np.array([f["y"] for f in wfix], dtype=float)
    fd = np.array([f["d"] for f in wfix], dtype=float)

    try:
        tops = result_band_tops(10, doc_h)
    except Exception:
        return None
    if r["position"] >= len(tops):
        return None
    band_top = tops[r["position"]]
    band_bot = tops[r["position"] + 1] if r["position"] + 1 < len(tops) else band_top + 160

    click_t_rel = None
    if clicks:
        ct_click, _, _ = clicks[0]
        if entry <= ct_click <= exit_:
            click_t_rel = ct_click - entry

    return {
        "record": r,
        "tid": tid,
        "duration_ms": exit_ - entry,
        "cursor_t": ct, "cursor_x": cx, "cursor_y": cy,
        "fix_t": ft, "fix_x": fx, "fix_y": fy, "fix_d": fd,
        "band_top": band_top, "band_bot": band_bot,
        "position": r["position"],
        "click_t_rel": click_t_rel,
    }


def draw_panel(ax, data, cls):
    cls_color = CLASS_COLORS[cls]
    band_top = data["band_top"]
    band_bot = data["band_bot"]
    dur_s = data["duration_ms"] / 1000

    # Target band as a horizontal shaded zone
    ax.axhspan(band_top, band_bot, color=BAND_FILL, zorder=1)
    ax.axhline(band_top, color=INK, linewidth=0.6, alpha=0.4, zorder=1)
    ax.axhline(band_bot, color=INK, linewidth=0.6, alpha=0.4, zorder=1)

    # Cursor y-position over time
    ax.plot(
        data["cursor_t"] / 1000, data["cursor_y"],
        color=CURSOR_COLOR, linewidth=2.2, alpha=0.9, zorder=3,
        label="cursor y",
    )

    # Fixations as dots — stems drop to gaze y, sized by duration
    for t, y, d in zip(data["fix_t"], data["fix_y"], data["fix_d"]):
        ax.plot([t / 1000, t / 1000], [y, y - d * 0.0001], color=GAZE_COLOR,
                linewidth=0.6, alpha=0.5, zorder=2)
    ax.scatter(
        data["fix_t"] / 1000, data["fix_y"],
        s=np.clip(data["fix_d"] * 0.35, 30, 280),
        facecolor="none", edgecolors=GAZE_COLOR, linewidth=2.0, zorder=4,
    )
    ax.scatter(
        data["fix_t"] / 1000, data["fix_y"],
        s=8, color=GAZE_COLOR, zorder=5,
    )

    # Click marker
    if cls == "clicked" and data["click_t_rel"] is not None:
        ax.axvline(data["click_t_rel"] / 1000, color="#2ca25f",
                   linewidth=1.8, alpha=0.85, linestyle="--", zorder=2)
        ax.text(
            data["click_t_rel"] / 1000, band_top - 30,
            "click", fontsize=8, color="#2ca25f", ha="center", va="bottom",
            fontweight="bold",
        )

    # Axis limits
    all_y = np.concatenate([data["cursor_y"], data["fix_y"],
                            [band_top, band_bot]])
    y_pad = (all_y.max() - all_y.min()) * 0.1
    y_lo = float(all_y.min()) - max(y_pad, 40)
    y_hi = float(all_y.max()) + max(y_pad, 40)
    ax.set_xlim(-0.05, dur_s * 1.02)
    ax.set_ylim(y_hi, y_lo)  # invert: top of page at top

    # Episode stats callout
    r = data["record"]
    txt = (
        f"{data['tid']} p{data['position']}  "
        f"{dur_s:.1f}s  {len(data['fix_t'])} fix"
    )
    ax.text(
        0.02, 0.98, txt, transform=ax.transAxes, fontsize=8,
        color=MUTED, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                  edgecolor="none", alpha=0.85),
    )

    ax.set_xlabel("time (s)", fontsize=9, color=MUTED)
    ax.set_ylabel("page y (px)", fontsize=9, color=MUTED)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, axis="x", color="#ececec", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


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

    panels = {}
    for cls, ix_list in picks.items():
        panels[cls] = []
        for i in ix_list:
            data = collect_episode(raw, i)
            if data is not None:
                panels[cls].append(data)
        print(f"  {cls}: {len(panels[cls])} exemplars with valid data")

    n_rows = 3
    n_cols = N_PER_CLASS
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(n_cols * 4.8, n_rows * 3.6),
        gridspec_kw={"wspace": 0.22, "hspace": 0.4},
    )

    row_order = ["clicked", "deferred", "evaluated-rejected"]
    row_labels = {
        "clicked": "CLICKED",
        "deferred": "DEFERRED",
        "evaluated-rejected": "EVALUATED-REJECTED",
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
                -0.25, 0.5, row_labels[cls],
                transform=axes[row, 0].transAxes,
                rotation=90, va="center", ha="center",
                color=CLASS_COLORS[cls], fontsize=12, fontweight="bold",
            )

    fig.suptitle(
        "Cursor y-position and gaze fixations over episode time, by outcome class\n"
        "Blue line: cursor y. Red circles: fixations (size = duration). "
        "Gray band: target result position. Green dashed line: click event.",
        fontsize=12, fontweight="semibold", y=0.995,
    )

    plt.subplots_adjust(top=0.92, bottom=0.06, left=0.09, right=0.98)

    out_png = OUT_DIR / f"cursor_gaze_timeseries{suffix}.png"
    out_pdf = OUT_DIR / f"cursor_gaze_timeseries{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")


if __name__ == "__main__":
    main()
