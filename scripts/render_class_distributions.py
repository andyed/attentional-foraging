"""Per-session and per-position distributions of the four-class taxonomy.

Central figure for the CIKM paper: four panels answering four related
questions about how the classes (clicked / deferred / evaluated-rejected)
are distributed across the corpus.

  (a) Per-trial histogram — how many episodes of each class show up per
      trial. Answers "are deferreds rare one-offs or thick per session?"
  (b) Rank distribution — which result positions produce each class.
      Answers "is deferring top-of-page, mid-page, both?"
  (c) Within-trial timing — when in the trial each class's episodes
      happen. Answers "do deferreds come early (hold while looking) or
      late (come back after seeing everything)?"
  (d) Co-occurrence — do sessions cluster into pure classes or mix them?
      Heatmap of ≥1 clicked × ≥1 deferred × ≥1 eval-rejected per trial.

All classes are [LAB]-only by construction — the deferred/eval-rejected
split uses the gaze-fixation regression detector in NB22, not scroll
events. Figure caption must state this.

Output:
    scripts/output/figures/class_distributions.png  (and .pdf)
    scripts/output/figures/class_distributions_summary.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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

INK = "#1a1a2e"
MUTED = "#5a5a6a"
CLASS_COLORS = {
    "clicked": "#2ca25f",
    "deferred": "#e08214",
    "evaluated-rejected": "#b2182b",
}
CLASS_ORDER = ["evaluated-rejected", "deferred", "clicked"]
CLASS_HUMAN = {
    "clicked": "CLICKED",
    "deferred": "DEFERRED",
    "evaluated-rejected": "EVAL-REJECTED",
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
    "axes.titlesize": 12.5,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
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

    # Per-trial aggregation — episodes grouped by trial_id
    by_trial = defaultdict(lambda: {"clicked": 0, "deferred": 0, "evaluated-rejected": 0})
    trial_order = {}  # trial_id -> episode indices in trial order
    for i, r in enumerate(raw):
        cls = labels[i]
        if cls in CLASS_ORDER:
            by_trial[r["trial_id"]][cls] += 1
            trial_order.setdefault(r["trial_id"], []).append(i)

    trial_ids = sorted(by_trial.keys())
    n_trials = len(trial_ids)
    print(f"  {n_trials:,} trials with at least one episode in the 3 target classes")
    class_n = {cls: int((labels == cls).sum()) for cls in CLASS_ORDER}
    for cls in CLASS_ORDER:
        print(f"  {cls}: {class_n[cls]:,} episodes")

    # ──────────────────────────────────────────────────────────
    # Build the 4-panel figure
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(
        2, 2,
        width_ratios=[1.0, 1.0],
        height_ratios=[1.0, 1.0],
        hspace=0.36, wspace=0.26,
        left=0.07, right=0.97, top=0.90, bottom=0.07,
    )
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    # ── (a) Per-trial histogram: count distribution for each class ──
    max_count = 5  # collapse >5 into one bin
    bin_edges = np.arange(max_count + 2) - 0.5  # [-0.5, 0.5, 1.5, ... 5.5]
    for cls in CLASS_ORDER:
        counts = np.array([min(by_trial[t][cls], max_count) for t in trial_ids])
        hist, _ = np.histogram(counts, bins=bin_edges)
        frac = hist / n_trials
        color = CLASS_COLORS[cls]
        offset = {"evaluated-rejected": -0.25, "deferred": 0.0, "clicked": 0.25}[cls]
        xs = np.arange(max_count + 1) + offset
        ax_a.bar(
            xs, frac, width=0.24, color=color, alpha=0.92,
            edgecolor=INK, linewidth=0.4,
            label=f"{CLASS_HUMAN[cls]} (n = {class_n[cls]:,})",
        )

    ax_a.set_xticks(np.arange(max_count + 1))
    ax_a.set_xticklabels(["0", "1", "2", "3", "4", "5+"])
    ax_a.set_xlabel("Episodes of this class per trial", fontweight="semibold")
    ax_a.set_ylabel("Fraction of trials", fontweight="semibold")
    ax_a.set_title(
        "(a)  Per-trial episode counts — how thick is each class per session?",
        fontweight="semibold", loc="left",
    )
    ax_a.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_a.set_axisbelow(True)
    ax_a.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")

    # ── (b) Rank distribution: P(class | position) across the 10 ranks ──
    positions = np.arange(10)
    class_by_pos = {cls: np.zeros(10) for cls in CLASS_ORDER}
    total_by_pos = np.zeros(10)
    for i, r in enumerate(raw):
        p = r["position"]
        if 0 <= p < 10:
            total_by_pos[p] += 1
            if labels[i] in CLASS_ORDER:
                class_by_pos[labels[i]][p] += 1

    # Fraction conditional on position
    width = 0.27
    for ci, cls in enumerate(CLASS_ORDER):
        offset = (ci - 1) * width
        frac = class_by_pos[cls] / np.maximum(total_by_pos, 1)
        ax_b.bar(
            positions + offset, frac, width=width, color=CLASS_COLORS[cls],
            alpha=0.92, edgecolor=INK, linewidth=0.4,
            label=CLASS_HUMAN[cls],
        )
    ax_b.set_xticks(positions)
    ax_b.set_xticklabels([str(p + 1) for p in positions])
    ax_b.set_xlabel("Result position (1 = top of SERP)", fontweight="semibold")
    ax_b.set_ylabel("P(class | position)", fontweight="semibold")
    ax_b.set_title(
        "(b)  Class prevalence by rank — where does each class live on the page?",
        fontweight="semibold", loc="left",
    )
    ax_b.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_b.set_axisbelow(True)
    ax_b.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")

    # ── (c) Within-trial episode ORDER: 1st, 2nd, 3rd, ... episode of trial ──
    # For each episode, compute its rank in the trial's entry_t-sorted order.
    # Capped at 8+ to keep the axis readable.
    max_order = 8
    episode_order = {}  # (trial_id, record_idx) -> 1-based order
    for tid, idxs in trial_order.items():
        sorted_idxs = sorted(
            [i for i in idxs if raw[i].get("entry_t") is not None],
            key=lambda i: raw[i]["entry_t"],
        )
        for k, i in enumerate(sorted_idxs):
            episode_order[i] = k + 1

    hist_by_class = {cls: np.zeros(max_order) for cls in CLASS_ORDER}
    for i, r in enumerate(raw):
        cls = labels[i]
        if cls not in CLASS_ORDER:
            continue
        order = episode_order.get(i)
        if order is None:
            continue
        k = min(order - 1, max_order - 1)
        hist_by_class[cls][k] += 1

    order_xs = np.arange(1, max_order + 1)
    width_c = 0.27
    for ci, cls in enumerate(CLASS_ORDER):
        total = hist_by_class[cls].sum()
        if total > 0:
            frac = hist_by_class[cls] / total
            offset = (ci - 1) * width_c
            ax_c.bar(
                order_xs + offset, frac, width=width_c, color=CLASS_COLORS[cls],
                alpha=0.92, edgecolor=INK, linewidth=0.4, label=CLASS_HUMAN[cls],
            )

    ax_c.set_xticks(order_xs)
    ax_c.set_xticklabels(["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th+"])
    ax_c.set_xlabel("Episode order within trial (sorted by entry time)",
                    fontweight="semibold")
    ax_c.set_ylabel("Fraction of class episodes", fontweight="semibold")
    ax_c.set_title(
        "(c)  Episode position within trial — early, middle, or late in the sequence?",
        fontweight="semibold", loc="left",
    )
    ax_c.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_c.set_axisbelow(True)
    ax_c.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")

    # ── (d) Inclusive co-occurrence: 7 bars (3 marginals + 3 pairs + triple) ──
    # A trial counts toward "click + defer" iff it has ≥1 click AND ≥1 defer
    # (regardless of whether it also has ≥1 eval-rej). Bars overlap; the
    # complementary "exclusive 8-bucket" view is in the summary JSON.
    pattern_counts = defaultdict(int)
    for tid in trial_ids:
        c = by_trial[tid]
        key = (
            c["clicked"] > 0,
            c["deferred"] > 0,
            c["evaluated-rejected"] > 0,
        )
        pattern_counts[key] += 1

    # Inclusive (marginal / pairwise / triple) counts
    inclusive_buckets = [
        ("click",                  lambda p: p[0]),
        ("defer",                  lambda p: p[1]),
        ("eval-rej",               lambda p: p[2]),
        ("click ∩ defer",          lambda p: p[0] and p[1]),
        ("click ∩ eval-rej",       lambda p: p[0] and p[2]),
        ("defer ∩ eval-rej",       lambda p: p[1] and p[2]),
        ("click ∩ defer ∩ eval-rej", lambda p: p[0] and p[1] and p[2]),
    ]
    bucket_colors = [
        CLASS_COLORS["clicked"], CLASS_COLORS["deferred"], CLASS_COLORS["evaluated-rejected"],
    ]
    for pred_idxs in [(0, 1), (0, 2), (1, 2), (0, 1, 2)]:
        comps = [list(CLASS_COLORS.values())[i] for i in pred_idxs]
        rgbs = np.array([[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)] for c in comps])
        avg = rgbs.mean(axis=0).astype(int)
        bucket_colors.append(f"#{avg[0]:02x}{avg[1]:02x}{avg[2]:02x}")

    bucket_fracs = []
    for label, predicate in inclusive_buckets:
        n_match = sum(pattern_counts[p] for p in pattern_counts if predicate(p))
        bucket_fracs.append(n_match / n_trials)

    y_pos = np.arange(len(inclusive_buckets))[::-1]
    ax_d.barh(
        y_pos, bucket_fracs, color=bucket_colors,
        edgecolor=INK, linewidth=0.5,
    )
    ax_d.set_yticks(y_pos)
    ax_d.set_yticklabels([b[0] for b in inclusive_buckets])
    ax_d.set_xlabel("Fraction of trials (inclusive — bars overlap)", fontweight="semibold")
    ax_d.set_title(
        "(d)  Class co-occurrence within trial (inclusive)",
        fontweight="semibold", loc="left",
    )
    ax_d.grid(True, axis="x", color="#ececec", linewidth=0.5)
    ax_d.set_axisbelow(True)
    for i, frac in enumerate(bucket_fracs):
        n_pat = int(round(frac * n_trials))
        ax_d.text(
            frac + 0.005, y_pos[i], f"{n_pat:,} ({frac * 100:.1f}%)",
            va="center", fontsize=9, color=MUTED,
        )
    ax_d.set_xlim(0, max(bucket_fracs) * 1.28)

    # Suptitle + methodology note
    fig.suptitle(
        "Four-class episode distributions across AdSERP   [LAB]\n"
        "clicked · deferred · evaluated-rejected — per-trial, per-rank, within-trial, and co-occurrence",
        fontsize=14, fontweight="semibold", y=0.978,
    )
    fig.text(
        0.5, 0.006,
        "Classes via NB22 regression rule: approached AND NOT clicked AND gaze_regression_label (eye-tracked; scroll telemetry not used for labels).   "
        f"N = {n_trials:,} trials, {sum(class_n.values()):,} episodes.",
        ha="center", fontsize=9.5, color=MUTED, style="italic",
    )

    out_png = OUT_DIR / f"class_distributions{suffix}.png"
    out_pdf = OUT_DIR / f"class_distributions{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")

    # ── Summary JSON ──
    summary = {
        "figure": out_png.name,
        "script": "scripts/render_class_distributions.py",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "LAB",
        "attribution": args.attribution,
        "features_input": str(features_path.relative_to(ROOT)),
        "regression_labels_input": str(reg_cache_path.relative_to(ROOT)),
        "classification_rule": (
            "NB22 four-class taxonomy. clicked from click event; "
            "deferred = approached AND NOT clicked AND gaze_regression_label; "
            "evaluated-rejected = approached AND NOT clicked AND NOT gaze_regression_label; "
            "not-approached = NOT approached. gaze_regression_label is computed "
            "from the gaze-fixation sequence revisiting earlier result positions "
            "in notebooks-v2/22_four_class_taxonomy.ipynb — the regressed_pos "
            "set is built from fix['y'], not from scroll events. The variable "
            "name in code is regression_labels; prose should call it "
            "gaze_regression_label. This is a [LAB]-only feature — a "
            "scroll-only proxy is future work."
        ),
        "n_trials": int(n_trials),
        "class_counts": class_n,
        "panels": {
            "a_per_trial_histogram": {
                "description": "Fraction of trials with N episodes of each class (N ∈ 0..5+).",
                "bins": ["0", "1", "2", "3", "4", "5+"],
                "per_class": {
                    cls: [
                        float(
                            sum(1 for t in trial_ids if min(by_trial[t][cls], max_count) == k)
                            / n_trials
                        )
                        for k in range(max_count + 1)
                    ]
                    for cls in CLASS_ORDER
                },
            },
            "b_rank_distribution": {
                "description": "P(class | position) for positions 1..10.",
                "per_position_total": total_by_pos.tolist(),
                "per_class": {
                    cls: (class_by_pos[cls] / np.maximum(total_by_pos, 1)).tolist()
                    for cls in CLASS_ORDER
                },
            },
            "c_episode_order_within_trial": {
                "description": "Fraction of each class's episodes at each within-trial episode rank (1st, 2nd, ..., 8th+).",
                "order_bins": list(range(1, max_order + 1)),
                "per_class": {
                    cls: (
                        hist_by_class[cls] / max(hist_by_class[cls].sum(), 1)
                    ).tolist()
                    for cls in CLASS_ORDER
                },
            },
            "d_cooccurrence": {
                "description": "Per-trial co-occurrence: inclusive bucket fractions (panel d bars) plus exclusive 3-bit pattern counts for full provenance.",
                "inclusive_buckets": {
                    label: {
                        "n_trials": int(round(frac * n_trials)),
                        "fraction": float(frac),
                    }
                    for (label, _), frac in zip(inclusive_buckets, bucket_fracs)
                },
                "exclusive_patterns": {
                    f"{int(p[0])}{int(p[1])}{int(p[2])}": {
                        "has_clicked": bool(p[0]),
                        "has_deferred": bool(p[1]),
                        "has_eval_rejected": bool(p[2]),
                        "n_trials": int(pattern_counts.get(p, 0)),
                        "fraction": float(pattern_counts.get(p, 0) / n_trials),
                    }
                    for p in [
                        (False, False, False), (True, False, False),
                        (False, True, False), (False, False, True),
                        (True, True, False), (True, False, True),
                        (False, True, True), (True, True, True),
                    ]
                },
            },
        },
    }
    out_json = OUT_DIR / f"class_distributions{suffix}_summary.json"
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
