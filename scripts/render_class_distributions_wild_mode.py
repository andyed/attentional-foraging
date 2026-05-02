"""WILD-mode counterpart to scripts/render_class_distributions.py.

Same four-panel chart, same trials, but the deferred / evaluated-rejected
split uses **M5's cursor-only LOSO predictions** instead of NB22's
gaze-regression labels. This shows the four-class distribution that a
production deployment would see (cursor telemetry, no eye tracker) and
makes the LAB-vs-WILD-mode alignment visually inspectable.

Wired:
- M5 features: nine cursor approach features (Option D hybrid xpath +
  linear fallback), loaded from `scripts/output/m4_nb21_hybrid_rerun/hybrid_features.json`.
- M5 supervision: NB22 regression_labels at training time only.
- M5 protocol: 47-fold GroupKFold by participant, class-weight balanced
  LR. Predicted-deferred = predicted probability ≥ Youden-J threshold.
- WILD-mode label per (trial, position):
  - clicked: from click event (same as LAB)
  - deferred (WILD-mode): approached AND non-clicked AND M5 predicted ≥ J*
  - eval-rejected (WILD-mode): approached AND non-clicked AND M5 predicted < J*
  - not-approached: min_dist ≥ 100 (same as LAB)

Outputs:
    scripts/output/figures/class_distributions_wild_mode.png  (and .pdf)
    scripts/output/figures/class_distributions_wild_mode_summary.json
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")


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
HYBRID_FEATURES = ROOT / "scripts/output/m4_nb21_hybrid_rerun/hybrid_features.json"
OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms",
    "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

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


def compute_m5_wild_mode_labels(raw, regression_labels):
    """Train M5 LOSO and return a boolean array (per LAB record) where
    True means M5 predicts the record is deferred (cursor-only, no gaze).

    Records outside the training subset (not approached, or clicked) get
    False — they are not candidates for deferred classification.
    """
    print("loading hybrid features for M5...")
    hy_records = json.load(open(HYBRID_FEATURES))
    hy_index = {(r["trial_id"], r["position"]): r for r in hy_records}

    n = len(raw)
    X_full = np.zeros((n, len(M4_FEATURES)), dtype=float)
    valid = np.zeros(n, dtype=bool)
    for i, r in enumerate(raw):
        hy = hy_index.get((r["trial_id"], r["position"]))
        if hy is None:
            continue
        for j, f in enumerate(M4_FEATURES):
            X_full[i, j] = float(hy.get(f) or 0)
        valid[i] = True

    min_dist_lab = np.array([r["min_dist"] for r in raw], dtype=float)
    was_clicked = np.array([r["was_clicked"] for r in raw], dtype=bool)
    approached_lab = min_dist_lab < 100
    subset_m5 = approached_lab & (~was_clicked) & valid

    X_m5 = X_full[subset_m5]
    y_m5 = regression_labels[subset_m5].astype(int)
    groups_m5 = np.array([r["trial_id"].split("-")[0] for r in raw])[subset_m5]

    print(f"  M5 training subset: {len(y_m5):,} records "
          f"({int(y_m5.sum())} deferred / {int((1 - y_m5).sum())} eval-rej)")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(set(groups_m5)))
    print("  running M5 LOSO LR...")
    yp_m5 = cross_val_predict(pipe, X_m5, y_m5, groups=groups_m5,
                              cv=gkf, method="predict_proba", n_jobs=1)[:, 1]

    fpr5, tpr5, thr5 = roc_curve(y_m5, yp_m5)
    j_idx = int(np.argmax(tpr5 - fpr5))
    threshold = float(thr5[j_idx])
    print(f"  Youden-J threshold: p* = {threshold:.4f}")

    # Map M5 binary predictions back to the full LAB record array
    m5_predicted_deferred = np.zeros(n, dtype=bool)
    subset_indices = np.where(subset_m5)[0]
    m5_predicted_deferred[subset_indices] = yp_m5 >= threshold

    return m5_predicted_deferred, threshold


def classify_records(raw, deferred_mask):
    """Construct four-class labels using `deferred_mask` (boolean per record)
    in place of NB22's regression_labels. Same logic as the LAB version,
    with the deferred mask being the configurable input."""
    n = len(raw)
    labels = np.full(n, "", dtype="U25")
    min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
    was_clicked = np.array([r["was_clicked"] for r in raw], dtype=bool)
    approached = min_dist < 100
    labels[was_clicked] = "clicked"
    labels[~was_clicked & approached & deferred_mask] = "deferred"
    labels[~was_clicked & approached & ~deferred_mask] = "evaluated-rejected"
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
    print("loading features + NB22 regression labels...")
    raw = json.load(open(features_path))
    regression_labels = np.array(json.load(open(reg_cache_path)), dtype=bool)

    print("\n── Computing WILD-mode (M5 cursor-only) deferred labels ──")
    deferred_mask, threshold = compute_m5_wild_mode_labels(raw, regression_labels)

    print(f"\n  WILD-mode deferred predictions: {int(deferred_mask.sum()):,}")
    print(f"  LAB ground truth deferreds:     {int(regression_labels.sum()):,}")
    print(f"  LAB-vs-WILD agreement on deferred subset:")
    lab_def = regression_labels.astype(bool)
    wild_def = deferred_mask.astype(bool)
    union = lab_def | wild_def
    intersect = lab_def & wild_def
    jaccard = float(intersect.sum() / max(union.sum(), 1))
    print(f"    intersection: {int(intersect.sum()):,}")
    print(f"    union:        {int(union.sum()):,}")
    print(f"    Jaccard:      {jaccard:.3f}")

    labels = classify_records(raw, deferred_mask)

    # Per-trial aggregation
    by_trial = defaultdict(lambda: {"clicked": 0, "deferred": 0, "evaluated-rejected": 0})
    trial_order = {}
    for i, r in enumerate(raw):
        cls = labels[i]
        if cls in CLASS_ORDER:
            by_trial[r["trial_id"]][cls] += 1
        if r["trial_id"] not in trial_order:
            trial_order[r["trial_id"]] = []
        trial_order[r["trial_id"]].append(i)

    trial_ids = sorted(by_trial.keys())
    n_trials = len(trial_ids)
    class_n = {cls: int((labels == cls).sum()) for cls in CLASS_ORDER}
    print(f"\n  trials: {n_trials:,}")
    print(f"  WILD-mode class counts: {class_n}")

    # Per-position aggregation (panel b)
    max_pos = 10
    class_by_pos = {cls: np.zeros(max_pos, dtype=float) for cls in CLASS_ORDER}
    total_by_pos = np.zeros(max_pos, dtype=float)
    seen_at_pos = defaultdict(set)  # (cls, pos) -> set of trial_ids
    for i, r in enumerate(raw):
        pos = int(r["position"])
        if pos >= max_pos:
            continue
        cls = labels[i]
        if cls in CLASS_ORDER:
            seen_at_pos[(cls, pos)].add(r["trial_id"])
    # Total trials with any episode at each position (denominator)
    trials_at_pos = defaultdict(set)
    for r in raw:
        pos = int(r["position"])
        if pos < max_pos:
            trials_at_pos[pos].add(r["trial_id"])
    for pos in range(max_pos):
        total_by_pos[pos] = len(trials_at_pos[pos])
        for cls in CLASS_ORDER:
            class_by_pos[cls][pos] = len(seen_at_pos.get((cls, pos), set()))

    # Episode order within trial (panel c)
    max_order = 8
    hist_by_class = {cls: np.zeros(max_order, dtype=float) for cls in CLASS_ORDER}
    for tid in trial_ids:
        episode_indices = trial_order[tid]
        episode_indices_sorted = sorted(
            episode_indices, key=lambda i: raw[i].get("entry_t") or 0)
        cls_episodes = [
            (k + 1, labels[i]) for k, i in enumerate(episode_indices_sorted)
            if labels[i] in CLASS_ORDER
        ]
        for order, cls in cls_episodes:
            bin_idx = min(order - 1, max_order - 1)
            hist_by_class[cls][bin_idx] += 1

    # Co-occurrence (panel d)
    pattern_counts = defaultdict(int)
    for tid in trial_ids:
        c = by_trial[tid]
        key = (
            c["clicked"] > 0,
            c["deferred"] > 0,
            c["evaluated-rejected"] > 0,
        )
        pattern_counts[key] += 1
    patterns = [
        (False, False, False), (True, False, False), (False, True, False),
        (False, False, True), (True, True, False), (True, False, True),
        (False, True, True), (True, True, True),
    ]

    # ── Render the figure ──
    fig, ((ax_a, ax_b), (ax_c, ax_d)) = plt.subplots(
        2, 2, figsize=(12.5, 9), gridspec_kw={"hspace": 0.42, "wspace": 0.28})

    # Panel (a): Per-trial histogram
    max_count = 5
    bins = list(range(max_count + 1))
    bar_w = 0.27
    for k, cls in enumerate(CLASS_ORDER):
        per_class_fracs = [
            sum(1 for t in trial_ids if min(by_trial[t][cls], max_count) == b) / n_trials
            for b in bins
        ]
        x = np.arange(len(bins)) + (k - 1) * bar_w
        ax_a.bar(x, per_class_fracs, width=bar_w, color=CLASS_COLORS[cls],
                 edgecolor=INK, linewidth=0.5, label=CLASS_HUMAN[cls])
    ax_a.set_xticks(np.arange(len(bins)))
    ax_a.set_xticklabels([str(b) if b < max_count else f"{max_count}+" for b in bins])
    ax_a.set_xlabel("Episodes per trial", fontweight="semibold")
    ax_a.set_ylabel("Fraction of trials", fontweight="semibold")
    ax_a.set_title("(a)  Per-trial episode counts (WILD-mode = M5 prediction)",
                   fontweight="semibold", loc="left")
    ax_a.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")
    ax_a.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_a.set_axisbelow(True)

    # Panel (b): P(class | position) by rank
    positions = list(range(1, max_pos + 1))
    for cls in CLASS_ORDER:
        fracs = class_by_pos[cls] / np.maximum(total_by_pos, 1)
        ax_b.plot(positions, fracs, marker="o", color=CLASS_COLORS[cls],
                  linewidth=2, markersize=5, label=CLASS_HUMAN[cls])
    ax_b.set_xlabel("Result rank (1 = top)", fontweight="semibold")
    ax_b.set_ylabel("P(class | position)", fontweight="semibold")
    ax_b.set_title("(b)  Class prevalence by rank", fontweight="semibold", loc="left")
    ax_b.set_xticks(positions)
    ax_b.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")
    ax_b.grid(True, color="#ececec", linewidth=0.5)
    ax_b.set_axisbelow(True)

    # Panel (c): Episode order within trial
    order_x = np.arange(1, max_order + 1)
    for k, cls in enumerate(CLASS_ORDER):
        norm = max(hist_by_class[cls].sum(), 1)
        ax_c.plot(order_x, hist_by_class[cls] / norm, marker="o",
                  color=CLASS_COLORS[cls], linewidth=2, markersize=5,
                  label=CLASS_HUMAN[cls])
    ax_c.set_xticks(order_x)
    ax_c.set_xticklabels([str(o) if o < max_order else f"{max_order}+" for o in order_x])
    ax_c.set_xlabel("Episode order within trial", fontweight="semibold")
    ax_c.set_ylabel("Fraction of class's episodes", fontweight="semibold")
    ax_c.set_title("(c)  Episode order within trial", fontweight="semibold", loc="left")
    ax_c.grid(True, axis="y", color="#ececec", linewidth=0.5)
    ax_c.set_axisbelow(True)
    ax_c.legend(loc="upper right", frameon=True, framealpha=0.95,
                edgecolor="#cccccc", facecolor="white")

    # Panel (d): Inclusive co-occurrence (matches LAB script)
    inclusive_buckets = [
        ("click",                      lambda p: p[0]),
        ("defer",                      lambda p: p[1]),
        ("eval-rej",                   lambda p: p[2]),
        ("click ∩ defer",              lambda p: p[0] and p[1]),
        ("click ∩ eval-rej",           lambda p: p[0] and p[2]),
        ("defer ∩ eval-rej",           lambda p: p[1] and p[2]),
        ("click ∩ defer ∩ eval-rej",   lambda p: p[0] and p[1] and p[2]),
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
    ax_d.barh(y_pos, bucket_fracs, color=bucket_colors, edgecolor=INK, linewidth=0.5)
    ax_d.set_yticks(y_pos)
    ax_d.set_yticklabels([b[0] for b in inclusive_buckets])
    ax_d.set_xlabel("Fraction of trials (inclusive — bars overlap)", fontweight="semibold")
    ax_d.set_title("(d)  Class co-occurrence within trial (inclusive)",
                   fontweight="semibold", loc="left")
    for i, frac in enumerate(bucket_fracs):
        n_pat = int(round(frac * n_trials))
        ax_d.text(frac + 0.005, y_pos[i], f"{n_pat:,} ({frac * 100:.1f}%)",
                  va="center", fontsize=9, color=MUTED)
    ax_d.set_xlim(0, max(bucket_fracs) * 1.28)
    ax_d.grid(True, axis="x", color="#ececec", linewidth=0.5)
    ax_d.set_axisbelow(True)

    fig.suptitle(
        "WILD-mode four-class taxonomy on AdSERP (M5 cursor-only deferred classifier)\n"
        "clicked · deferred · evaluated-rejected — what a production cursor-only deployment would see",
        fontsize=14, fontweight="semibold", y=0.985,
    )
    fig.text(
        0.5, 0.006,
        f"M5 LOSO predicted-deferred at Youden-J threshold p* = {threshold:.4f}. "
        f"deferred (WILD-mode) = approached AND NOT clicked AND M5 ≥ p*. "
        f"Compare with class_distributions.png (LAB ground truth via NB22). "
        f"N = {n_trials:,} trials, {sum(class_n.values()):,} episodes.",
        ha="center", fontsize=9.5, color=MUTED, style="italic",
    )

    out_png = OUT_DIR / f"class_distributions_wild_mode{suffix}.png"
    out_pdf = OUT_DIR / f"class_distributions_wild_mode{suffix}.pdf"
    fig.savefig(out_png, dpi=200, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out_png}")
    print(f"wrote {out_pdf}")

    summary = {
        "figure": "class_distributions_wild_mode.png",
        "script": "scripts/render_class_distributions_wild_mode.py",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "WILD-mode (M5 predicted-deferred, cursor-only)",
        "m5_youden_j_threshold": threshold,
        "m5_lab_jaccard": jaccard,
        "classification_rule": (
            "Same as scripts/render_class_distributions.py except deferred / "
            "eval-rejected split uses M5 LOSO predicted-deferred (cursor-only) "
            "in place of NB22 gaze_regression_label. Threshold = Youden-J on "
            "the M5 ROC curve."
        ),
        "n_trials": int(n_trials),
        "class_counts_wild_mode": class_n,
        "panels": {
            "a_per_trial_histogram": {
                "description": "Fraction of trials with N WILD-mode episodes of each class.",
                "bins": ["0", "1", "2", "3", "4", "5+"],
                "per_class": {
                    cls: [
                        float(sum(1 for t in trial_ids
                                  if min(by_trial[t][cls], max_count) == k) / n_trials)
                        for k in range(max_count + 1)
                    ]
                    for cls in CLASS_ORDER
                },
            },
            "b_rank_distribution": {
                "description": "P(class | position) for positions 1..10, WILD-mode.",
                "per_position_total": total_by_pos.tolist(),
                "per_class": {
                    cls: (class_by_pos[cls] / np.maximum(total_by_pos, 1)).tolist()
                    for cls in CLASS_ORDER
                },
            },
            "d_cooccurrence": {
                "description": "Per-trial WILD-mode presence patterns.",
                "patterns": {
                    f"{int(p[0])}{int(p[1])}{int(p[2])}": {
                        "has_clicked": bool(p[0]),
                        "has_deferred": bool(p[1]),
                        "has_eval_rejected": bool(p[2]),
                        "n_trials": int(pattern_counts.get(p, 0)),
                        "fraction": float(pattern_counts.get(p, 0) / n_trials),
                    }
                    for p in patterns
                },
            },
        },
    }
    out_json = OUT_DIR / f"class_distributions_wild_mode{suffix}_summary.json"
    json.dump(summary, open(out_json, "w"), indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
