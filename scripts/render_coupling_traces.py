"""Per-episode cursor-gaze Euclidean distance traces, colored by outcome class.

The most compelling visualization of the motor-signature dissociation:
each trace is one approach episode, y = cursor-gaze distance (px),
x = time from episode entry (s). 3-4 exemplars per class (clicked /
deferred / evaluated-rejected) plus the class median as a thick line.

Variable duration — traces end at each exemplar's actual exit_t, so
the reader sees the duration contrast directly (eval-rejected short,
deferred long, clicked varies).

Output:
    scripts/output/figures/coupling_traces.png  (and .pdf)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_events,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TRACE_CACHE = OUT_DIR / "per_record_fixation_traces.json"  # NEW cache

N_PER_CLASS = 4

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
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
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


def compute_trace(raw, i):
    """Compute per-fixation cursor-gaze distance for one exemplar.

    Returns (t_rel_s, distance_px) arrays where t_rel is seconds from
    episode entry and distance is Euclidean cursor-gaze distance at
    each fixation's timestamp (cursor interpolated to fixation time).
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
    curs = [(t, x, y) for (t, ev, x, y) in events if ev in pos_evts]
    if len(curs) < 5:
        return None
    m_ts = np.array([c[0] for c in curs], dtype=np.int64)
    m_xs = np.array([c[1] for c in curs], dtype=float)
    m_ys = np.array([c[2] for c in curs], dtype=float)

    wfix = [f for f in fixes if entry <= f["t"] <= exit_]
    if len(wfix) < 3:
        return None
    wfix.sort(key=lambda f: f["t"])

    times_s = []
    dists = []
    for f in wfix:
        # Nearest-in-time cursor position
        pos = int(np.searchsorted(m_ts, f["t"]))
        if pos == 0:
            j = 0
        elif pos >= len(m_ts):
            j = len(m_ts) - 1
        else:
            j = pos if abs(m_ts[pos] - f["t"]) < abs(m_ts[pos - 1] - f["t"]) else pos - 1
        dx = f["x"] - m_xs[j]
        dy = f["y"] - m_ys[j]
        d = float(np.hypot(dx, dy))
        times_s.append((f["t"] - entry) / 1000.0)
        dists.append(d)
    return np.array(times_s), np.array(dists)


def compute_all_traces(raw):
    """Compute per-fixation cursor-gaze distance for EVERY record.

    Returns a dict: record_index -> list of (t_s, dist_px) tuples.
    Cached to TRACE_CACHE so subsequent renders skip the ~5 min loop.
    """
    if TRACE_CACHE.exists():
        print(f"loading cached traces from {TRACE_CACHE}")
        cached = json.load(open(TRACE_CACHE))
        # JSON round-trips int keys as strings — convert back
        return {int(k): v for k, v in cached.items()}

    print("computing per-record fixation traces (expensive, ~5 min)...")
    out = {}
    for n_done, i in enumerate(range(len(raw))):
        if n_done % 1000 == 0:
            print(f"  {n_done}/{len(raw)} records...")
        trace = compute_trace(raw, i)
        if trace is not None:
            t, d = trace
            out[i] = list(zip(t.tolist(), d.tolist()))

    TRACE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    json.dump({str(k): v for k, v in out.items()}, open(TRACE_CACHE, "w"))
    print(f"  cached to {TRACE_CACHE}")
    return out


def compute_class_trace_stats(all_traces, labels, cls, n_bins=24,
                               t_max_s=6.0, min_frac=0.40):
    """Per-class cursor-gaze distance stats at each time bin, using the
    pre-computed all_traces cache.

    min_frac: truncate the class median where fewer than this fraction
    of the class's records are still contributing to the bin. 0.40 means
    the class ends at the bin where less than 40% of records are still
    represented — forces visible duration truncation.
    """
    mask = np.where(labels == cls)[0]
    n_cls = len(mask)
    min_samples = max(30, int(n_cls * min_frac))
    bin_edges = np.linspace(0, t_max_s, n_bins + 1)
    per_bin = [[] for _ in range(n_bins)]
    for i in mask:
        if i not in all_traces:
            continue
        trace = all_traces[i]
        if not trace:
            continue
        t_arr = np.array([p[0] for p in trace], dtype=float)
        d_arr = np.array([p[1] for p in trace], dtype=float)
        for k in range(n_bins):
            lo, hi = bin_edges[k], bin_edges[k + 1]
            in_bin = d_arr[(t_arr >= lo) & (t_arr < hi)]
            if len(in_bin) > 0:
                per_bin[k].append(float(np.median(in_bin)))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    medians = np.full(n_bins, np.nan)
    q25 = np.full(n_bins, np.nan)
    q75 = np.full(n_bins, np.nan)
    n_per_bin = np.zeros(n_bins, dtype=int)
    for k, b in enumerate(per_bin):
        n_per_bin[k] = len(b)
        if len(b) >= min_samples:
            medians[k] = float(np.median(b))
            q25[k] = float(np.percentile(b, 25))
            q75[k] = float(np.percentile(b, 75))
    return bin_centers, medians, q25, q75, n_per_bin, min_samples


def main():
    print("loading features + regression labels...")
    raw = json.load(open(FEATURES_JSON))
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    labels = classify_records(raw, regression_labels)

    # Compute all-record traces (cached after first run)
    all_traces = compute_all_traces(raw)
    print(f"  {len(all_traces)} records have valid traces")

    # Compute class trace stats. 40% min-frac threshold means each class
    # truncates where fewer than 40% of its records are still contributing
    # fixations — the class median line ends near its 60th-percentile
    # duration, which makes the duration contrast visible.
    print("computing class trace stats...")
    stats_by_cls = {}
    for cls in ("clicked", "deferred", "evaluated-rejected"):
        bc, med, q25, q75, n_per_bin, min_samples = compute_class_trace_stats(
            all_traces, labels, cls,
            n_bins=24, t_max_s=6.0, min_frac=0.40,
        )
        stats_by_cls[cls] = (bc, med, q25, q75, n_per_bin, min_samples)
        valid_bins = int(np.isfinite(med).sum())
        n_cls = int((labels == cls).sum())
        print(f"  {cls}: {valid_bins} valid bins (min_samples={min_samples}, class N={n_cls})")

    # Two-panel figure: main coupling plot + sample-count strip below
    fig, (ax, ax_strip) = plt.subplots(
        2, 1, figsize=(12, 7.8),
        gridspec_kw={"height_ratios": [4.2, 1.0], "hspace": 0.08},
        sharex=True,
    )

    class_order = ["evaluated-rejected", "deferred", "clicked"]
    class_labels_human = {
        "clicked": "CLICKED — cursor held far from gaze throughout approach",
        "deferred": "DEFERRED — cursor parked at offset while gaze revisits",
        "evaluated-rejected": "EVALUATED-REJECTED — cursor tracks gaze closely (tightest coupling)",
    }

    # IQR ribbons + median lines on the main axes
    for cls in class_order:
        color = CLASS_COLORS[cls]
        bc, med, q25, q75, n_per_bin, min_samples = stats_by_cls[cls]
        valid = np.isfinite(med)

        # Ribbon
        ax.fill_between(
            bc[valid], q25[valid], q75[valid],
            color=color, alpha=0.22, linewidth=0, zorder=2,
        )
        # Median line
        n_cls = int((labels == cls).sum())
        label = f"{class_labels_human[cls]}\n(n = {n_cls:,}, IQR ribbon)"
        ax.plot(
            bc[valid], med[valid], color=color, linewidth=3.4,
            marker="o", markersize=8, markeredgecolor="#1a1a2e",
            markeredgewidth=0.7, label=label, zorder=5,
        )

        # End-of-class marker (diamond at the rightmost valid bin)
        if valid.any():
            last_valid_idx = int(np.where(valid)[0].max())
            ax.scatter(
                bc[last_valid_idx], med[last_valid_idx], s=220, marker="D",
                color="white", edgecolors=color, linewidth=2.5, zorder=6,
            )

    ax.set_ylabel("Cursor–gaze distance (px)\n(lower = tighter coupling)",
                  fontweight="semibold")
    ax.set_title(
        "Cursor–gaze coupling is set at episode entry and held for the duration\n"
        "Eval-rejected runs tightest; deferred parks mid-distance; clicked stays farthest from gaze",
        fontsize=13.5, pad=12,
    )
    ax.set_xlim(-0.05, 6.0)
    ax.set_ylim(100, 550)
    ax.grid(True, axis="y", color="#ececec", linewidth=0.6)
    ax.grid(True, axis="x", color="#f4f4f4", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper right", frameon=True, framealpha=0.95,
        edgecolor="#cccccc", facecolor="white", fontsize=10,
        borderpad=0.8,
    )

    # ── Sample-count strip below — how many episodes contribute to each bin
    for cls in class_order:
        color = CLASS_COLORS[cls]
        bc, med, q25, q75, n_per_bin, min_samples = stats_by_cls[cls]
        n_cls = int((labels == cls).sum())
        # Normalize: each bar is fraction of class still contributing
        frac = n_per_bin / max(n_cls, 1)
        ax_strip.fill_between(
            bc, 0, frac, color=color, alpha=0.35, linewidth=0,
            zorder=2,
        )
        ax_strip.plot(
            bc, frac, color=color, linewidth=2.0, zorder=3,
        )
        # Mark threshold
        ax_strip.axhline(
            min_samples / max(n_cls, 1), color=color, linewidth=0.6,
            linestyle=":", alpha=0.5, zorder=1,
        )

    ax_strip.set_xlabel("Time from episode entry (seconds)", fontweight="semibold")
    ax_strip.set_ylabel("Fraction of\nclass present",
                        fontweight="semibold", fontsize=10)
    ax_strip.set_xlim(-0.05, 6.0)
    ax_strip.set_ylim(0, 1.05)
    ax_strip.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax_strip.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax_strip.grid(True, axis="y", color="#ececec", linewidth=0.4)
    ax_strip.set_axisbelow(True)

    plt.tight_layout()

    out_png = OUT_DIR / "coupling_traces.png"
    out_pdf = OUT_DIR / "coupling_traces.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")

    # ── Persist machine-readable stats alongside the figure ──
    out_json = OUT_DIR / "coupling_traces_summary.json"
    summary = {
        "figure": "coupling_traces.png",
        "script": "scripts/render_coupling_traces.py",
        "generated": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "config": {
            "n_bins": 24,
            "t_max_s": 6.0,
            "min_frac": 0.40,
            "trace_metric": "per-fixation cursor-gaze Euclidean distance (px)",
            "cursor_sampling": "nearest-in-time interpolation to fixation timestamp",
        },
        "cohort_counts": {
            cls: {
                "class_n_total": int((labels == cls).sum()),
                "class_n_pooled": int(sum(
                    1 for i in np.where(labels == cls)[0]
                    if i in all_traces and all_traces[i]
                )),
            }
            for cls in ("clicked", "deferred", "evaluated-rejected")
        },
        "per_class": {},
    }
    for cls in ("clicked", "deferred", "evaluated-rejected"):
        bc, med, q25, q75, n_per_bin, min_samples = stats_by_cls[cls]
        valid = np.isfinite(med)
        last_valid_idx = int(np.where(valid)[0].max()) if valid.any() else -1
        summary["per_class"][cls] = {
            "min_samples_threshold": int(min_samples),
            "n_valid_bins": int(valid.sum()),
            "last_valid_bin_center_s": float(bc[last_valid_idx]) if last_valid_idx >= 0 else None,
            "bin_centers_s": bc.tolist(),
            "median_px": [None if np.isnan(v) else float(v) for v in med],
            "q25_px": [None if np.isnan(v) else float(v) for v in q25],
            "q75_px": [None if np.isnan(v) else float(v) for v in q75],
            "n_per_bin": n_per_bin.tolist(),
        }
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
