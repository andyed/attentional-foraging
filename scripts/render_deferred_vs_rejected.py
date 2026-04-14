"""Canonical figures contrasting deferred vs evaluated-rejected classes
for the CIKM paper §4.1.2, the approach-retreat README, and the Peter/
Leif email.

Figure 1 — Four-panel metric dissociation. Small-multiples violin plots
showing the four motor-signature metrics (cursor-gaze distance,
post-closest drift, total gaze dwell, dwell in proximity) for four
classes. Medians + IQR. p-value annotations for the deferred vs
evaluated-rejected Mann-Whitney U test.

Figure 2 — Median cursor-gaze distance trajectory over normalized
episode time. For each class, plot median cursor-gaze distance vs
episode progress (0 → 1) with 25–75 % IQR ribbons. Shows how coupling
evolves within each class.

Outputs:
  scripts/output/figures/deferred_vs_rejected_four_panel.png   (and .pdf)
  scripts/output/figures/deferred_vs_rejected_trajectory.png   (and .pdf)
  scripts/output/figures/per_record_coupling.json              (cache for reuse)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import load_fixations, load_mouse_events

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
COUPLING_CACHE = ROOT / "scripts/output/figures/per_record_coupling.json"
TRAJECTORY_CACHE = ROOT / "scripts/output/figures/per_record_trajectory.json"
OUT = ROOT / "scripts/output/figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Light editorial palette (render channels/science.md light variant) ─────
mpl.rcParams.update({
    "figure.figsize": (12, 8),
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.transparent": False,

    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 13,
    "axes.titlesize": 15,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "figure.titlesize": 17,
    "font.weight": "regular",

    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": "#1a1a2e",
    "axes.labelcolor": "#1a1a2e",
    "xtick.color": "#1a1a2e",
    "ytick.color": "#1a1a2e",
    "text.color": "#1a1a2e",
    "grid.color": "#dedede",
    "grid.linewidth": 0.6,
    "grid.alpha": 1.0,

    "axes.linewidth": 1.0,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,

    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 4,
    "ytick.major.size": 4,
    "xtick.major.width": 1.0,
    "ytick.major.width": 1.0,

    "lines.linewidth": 2.0,
    "lines.markersize": 7,
    "patch.linewidth": 0.8,
})

# Class colors — chosen for perceptual ordering and colorblind safety
# (tested on Dark2 + hand-tuned)
CLASS_COLORS = {
    "clicked": "#2ca25f",                    # green — terminal positive
    "deferred": "#fdae61",                   # warm orange — ambivalence
    "evaluated-rejected": "#b2182b",         # red — hard negative
    "not-approached": "#8a8aa0",             # neutral gray — no engagement
}

CLASS_ORDER = ["not-approached", "clicked", "deferred", "evaluated-rejected"]


def compute_per_record_coupling():
    """Compute per-episode median cursor-gaze Euclidean distance per record.

    Matches followup_peter_leif.py. Saves result to COUPLING_CACHE so
    downstream figures can skip the ~3 min loop.
    """
    if COUPLING_CACHE.exists():
        print(f"loading cached coupling distances from {COUPLING_CACHE}")
        cached = json.load(open(COUPLING_CACHE))
        return np.array(cached, dtype=float)

    print("computing per-record coupling (expensive, ~3 min)...")
    raw = json.load(open(FEATURES))
    n = len(raw)

    records_by_trial = defaultdict(list)
    for i, r in enumerate(raw):
        records_by_trial[r["trial_id"]].append(i)

    coupling = np.full(n, np.nan)
    for n_done, (tid, idxs) in enumerate(records_by_trial.items()):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(records_by_trial)} trials...")
        try:
            fixes = load_fixations(tid)
            events, _, _ = load_mouse_events(tid)
        except Exception:
            continue
        mouse_pos = [(e[0], e[2], e[3]) for e in events
                     if e[1] in ("mousemove", "mouseover", "click", "mousedown", "mouseup")]
        if not mouse_pos or not fixes:
            continue
        m_ts = np.array([m[0] for m in mouse_pos], dtype=np.int64)
        m_xs = np.array([m[1] for m in mouse_pos], dtype=float)
        m_ys = np.array([m[2] for m in mouse_pos], dtype=float)

        for idx in idxs:
            r = raw[idx]
            entry = r.get("entry_t")
            exit_ = r.get("exit_t")
            if entry is None or exit_ is None:
                continue
            window_fixes = [f for f in fixes if entry <= f["t"] <= exit_]
            if not window_fixes:
                continue
            dists = []
            for f in window_fixes:
                pos = int(np.searchsorted(m_ts, f["t"]))
                if pos == 0:
                    j = 0
                elif pos >= len(m_ts):
                    j = len(m_ts) - 1
                else:
                    j = pos if abs(m_ts[pos] - f["t"]) < abs(m_ts[pos - 1] - f["t"]) else pos - 1
                dx = f["x"] - m_xs[j]
                dy = f["y"] - m_ys[j]
                dists.append(float(np.hypot(dx, dy)))
            if dists:
                coupling[idx] = float(np.median(dists))

    COUPLING_CACHE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(coupling.tolist(), open(COUPLING_CACHE, "w"))
    return coupling


def compute_per_record_trajectory(n_bins=10, sample_cap=400):
    """Compute per-episode cursor-gaze distance as a function of normalized
    time, binned into `n_bins` uniform windows from 0 to 1.

    Returns shape (n_records, n_bins) with NaN where missing. Sampling
    cap limits the per-class records rendered in Figure 2 so the plot
    doesn't take an hour.
    """
    if TRAJECTORY_CACHE.exists():
        print(f"loading cached trajectories from {TRAJECTORY_CACHE}")
        cached = json.load(open(TRAJECTORY_CACHE))
        return np.array(cached, dtype=float)

    print(f"computing per-record trajectories binned into {n_bins} bins (expensive)...")
    raw = json.load(open(FEATURES))
    n = len(raw)

    records_by_trial = defaultdict(list)
    for i, r in enumerate(raw):
        records_by_trial[r["trial_id"]].append(i)

    traj = np.full((n, n_bins), np.nan)

    for n_done, (tid, idxs) in enumerate(records_by_trial.items()):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(records_by_trial)} trials...")
        try:
            fixes = load_fixations(tid)
            events, _, _ = load_mouse_events(tid)
        except Exception:
            continue
        mouse_pos = [(e[0], e[2], e[3]) for e in events
                     if e[1] in ("mousemove", "mouseover", "click", "mousedown", "mouseup")]
        if not mouse_pos or not fixes:
            continue
        m_ts = np.array([m[0] for m in mouse_pos], dtype=np.int64)
        m_xs = np.array([m[1] for m in mouse_pos], dtype=float)
        m_ys = np.array([m[2] for m in mouse_pos], dtype=float)

        for idx in idxs:
            r = raw[idx]
            entry = r.get("entry_t")
            exit_ = r.get("exit_t")
            if entry is None or exit_ is None or exit_ <= entry:
                continue
            duration = exit_ - entry
            window_fixes = [f for f in fixes if entry <= f["t"] <= exit_]
            if len(window_fixes) < 2:
                continue
            # For each bin, compute median cursor-gaze distance of
            # fixations whose timestamp falls in that bin
            bin_edges = np.linspace(entry, exit_, n_bins + 1)
            for b in range(n_bins):
                lo, hi = bin_edges[b], bin_edges[b + 1]
                bin_dists = []
                for f in window_fixes:
                    if lo <= f["t"] < hi or (b == n_bins - 1 and f["t"] == hi):
                        pos = int(np.searchsorted(m_ts, f["t"]))
                        if pos == 0:
                            j = 0
                        elif pos >= len(m_ts):
                            j = len(m_ts) - 1
                        else:
                            j = pos if abs(m_ts[pos] - f["t"]) < abs(m_ts[pos - 1] - f["t"]) else pos - 1
                        dx = f["x"] - m_xs[j]
                        dy = f["y"] - m_ys[j]
                        bin_dists.append(float(np.hypot(dx, dy)))
                if bin_dists:
                    traj[idx, b] = float(np.median(bin_dists))

    TRAJECTORY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(traj.tolist(), open(TRAJECTORY_CACHE, "w"))
    return traj


def classify_records(raw, regression_labels):
    """Return per-record class label using the NB22 regression-rule cut."""
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


def figure_one_four_panel(raw, labels, coupling_dist):
    """Four-panel violin plot of the motor-signature metrics by class."""
    n = len(raw)
    retreat = np.array([r["retreat_dist"] for r in raw], dtype=float)
    total_dwell = np.array([r["total_dwell_ms"] for r in raw], dtype=float)
    dwell_prox = np.array([r["dwell_in_proximity_ms"] for r in raw], dtype=float)

    metrics = [
        ("cursor_gaze", coupling_dist, "Cursor–gaze distance during episode (px)",
         "log"),
        ("retreat", retreat, "Post-closest cursor drift (px)",
         "log"),
        ("total_dwell", total_dwell / 1000.0, "Total gaze dwell (s)",
         "log"),
        ("prox_dwell", dwell_prox / 1000.0, "Dwell in proximity ≤ 100 px (s)",
         "log"),
    ]

    # Compute p-values for deferred vs eval-rejected for each metric
    p_vals = {}
    for key, arr, _, _ in metrics:
        def_mask = (labels == "deferred") & np.isfinite(arr) & (arr > 0)
        rej_mask = (labels == "evaluated-rejected") & np.isfinite(arr) & (arr > 0)
        if def_mask.sum() > 2 and rej_mask.sum() > 2:
            _, p = stats.mannwhitneyu(
                arr[def_mask], arr[rej_mask], alternative="two-sided"
            )
            p_vals[key] = p
        else:
            p_vals[key] = None

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle(
        "Motor-signature dissociation — deferred vs evaluated-rejected",
        fontsize=16, y=0.995, fontweight="bold",
    )
    axes = axes.flatten()

    for ax, (key, arr, ylabel, yscale) in zip(axes, metrics):
        # Violin data per class
        data = []
        positions = []
        colors = []
        labels_x = []
        counts = []
        medians = []
        for i, cls in enumerate(CLASS_ORDER):
            mask = (labels == cls) & np.isfinite(arr) & (arr > 0 if yscale == "log" else ~np.isnan(arr))
            vals = arr[mask]
            if len(vals) > 0:
                data.append(vals)
                positions.append(i + 1)
                colors.append(CLASS_COLORS[cls])
                labels_x.append(cls)
                counts.append(len(vals))
                medians.append(float(np.median(vals)))

        parts = ax.violinplot(
            data, positions=positions, showmeans=False, showmedians=False,
            showextrema=False, widths=0.75,
        )
        for j, pc in enumerate(parts["bodies"]):
            pc.set_facecolor(colors[j])
            pc.set_edgecolor("#1a1a2e")
            pc.set_linewidth(0.8)
            pc.set_alpha(0.72)

        # Median markers — diamond on top of each violin
        for pos, med, color in zip(positions, medians, colors):
            ax.scatter([pos], [med], marker="D", s=80, color="#1a1a2e",
                       edgecolors=color, linewidths=2.0, zorder=5)

        # IQR bar
        for pos, vals in zip(positions, data):
            q25, q75 = np.percentile(vals, [25, 75])
            ax.plot([pos, pos], [q25, q75], color="#1a1a2e", linewidth=3,
                    solid_capstyle="round", zorder=4)

        if yscale == "log":
            ax.set_yscale("log")

        ax.set_xticks(positions)
        ax.set_xticklabels(
            [f"{cls}\nn = {c:,}" for cls, c in zip(labels_x, counts)],
            fontsize=10,
        )
        ax.set_ylabel(ylabel, fontweight="semibold")

        # P-value annotation for deferred vs eval-rejected
        if p_vals[key] is not None:
            try:
                def_i = labels_x.index("deferred")
                rej_i = labels_x.index("evaluated-rejected")
                def_pos = positions[def_i]
                rej_pos = positions[rej_i]
                def_max = np.percentile(data[def_i], 97)
                rej_max = np.percentile(data[rej_i], 97)
                y_line = max(def_max, rej_max) * (2.2 if yscale == "log" else 1.15)
                ax.plot([def_pos, rej_pos], [y_line, y_line],
                        color="#1a1a2e", linewidth=1.2)
                p = p_vals[key]
                if p < 1e-30:
                    p_str = f"p < 10⁻³⁰"
                elif p < 1e-3:
                    exp = int(np.floor(np.log10(p)))
                    mant = p / (10 ** exp)
                    p_str = f"p = {mant:.1f} × 10^{{{exp}}}"
                else:
                    p_str = f"p = {p:.3f}"
                ax.text((def_pos + rej_pos) / 2, y_line * (1.3 if yscale == "log" else 1.02),
                        p_str, ha="center", va="bottom", fontsize=10,
                        color="#1a1a2e", fontweight="semibold")
            except (ValueError, IndexError):
                pass

        ax.grid(True, axis="y", color="#dedede", linewidth=0.6)
        ax.set_axisbelow(True)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out_png = OUT / "deferred_vs_rejected_four_panel.png"
    out_pdf = OUT / "deferred_vs_rejected_four_panel.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")
    return p_vals


def figure_two_trajectory(labels, trajectories, n_bins=10):
    """Median cursor-gaze distance trajectory over normalized episode time."""
    fig, ax = plt.subplots(figsize=(12, 7))

    x = np.linspace(0.05, 0.95, n_bins)

    for cls in ["clicked", "deferred", "evaluated-rejected"]:
        mask = labels == cls
        sub = trajectories[mask]
        if len(sub) == 0:
            continue
        # Per-bin median + IQR across records
        medians = np.nanmedian(sub, axis=0)
        q25 = np.nanpercentile(sub, 25, axis=0)
        q75 = np.nanpercentile(sub, 75, axis=0)

        color = CLASS_COLORS[cls]
        n_records = int(mask.sum())
        label = f"{cls} (n = {n_records:,})"
        ax.fill_between(x, q25, q75, color=color, alpha=0.22, linewidth=0)
        ax.plot(x, medians, color=color, linewidth=2.8, marker="o",
                markersize=8, label=label,
                markeredgecolor="#1a1a2e", markeredgewidth=0.8)

    ax.set_xlabel("Normalized episode time (0 = entry, 1 = exit)",
                  fontweight="semibold")
    ax.set_ylabel("Cursor–gaze Euclidean distance (px)", fontweight="semibold")
    ax.set_title(
        "Cursor–gaze coupling is set at episode entry, not during the episode\n"
        "Clicked: cursor converges on gaze. Deferred: holds steady at distance. Eval-rejected: co-located throughout.",
        fontsize=13, pad=12,
    )
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.set_xticklabels(["0", "0.2", "0.4", "0.6", "0.8", "1.0"])
    ax.set_xlim(0, 1)
    ax.legend(loc="upper left", frameon=True, framealpha=0.95,
              edgecolor="#cccccc", facecolor="white")
    ax.grid(True, axis="y", color="#dedede", linewidth=0.6)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out_png = OUT / "deferred_vs_rejected_trajectory.png"
    out_pdf = OUT / "deferred_vs_rejected_trajectory.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")


def main():
    print("loading features and regression labels...")
    raw = json.load(open(FEATURES))
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    assert len(regression_labels) == len(raw)

    labels = classify_records(raw, regression_labels)
    from collections import Counter
    print(f"class sizes: {dict(Counter(labels))}")

    coupling = compute_per_record_coupling()
    print(f"coupling computed / loaded: {int(np.isfinite(coupling).sum())} / {len(coupling)} records")

    print("\nrendering Figure 1 — four-panel metric dissociation")
    p_vals = figure_one_four_panel(raw, labels, coupling)
    for k, p in p_vals.items():
        print(f"  {k} deferred-vs-rej p = {p:.2e}")

    print("\nrendering Figure 2 — trajectory over normalized episode time")
    trajectories = compute_per_record_trajectory(n_bins=10)
    print(f"trajectories: {trajectories.shape}, valid rows: {int(np.isfinite(trajectories).any(axis=1).sum())}")
    figure_two_trajectory(labels, trajectories, n_bins=10)

    print("\nDone.")


if __name__ == "__main__":
    main()
