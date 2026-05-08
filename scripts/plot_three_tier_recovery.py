"""§4.3 figure — three-tier recovery of gaze-deliberation labels from cursor.

Two panels:

  (A) Coverage at each of three tiers (trial-level + participant-level bars).
        T1: cursor revisit (visit_count >= 2)        — visibly deliberated
        T2: cursor dynamics on cursor-blind subset    — recovered via 4-feature LR
        T3: union (T1 OR T2-positive)                — total LAB→WILD recovery

  (B) Per-fold LOPO AUC distribution for tier-2 cursor-dynamics inference,
      full nine-feature M4 vs the four-feature minimal kit. Boxplot + jitter.

Output: scripts/output/figures/three_tier_recovery.{pdf,png}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))
from cursor_arc_prevalence import visit_counts_for_trial  # noqa: E402
from nb22_revisit_count import count_revisits_per_trial  # noqa: E402

OUT_DIR = ROOT / "scripts/output/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M4_FULL = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity",
    "max_approach_velocity", "direction_changes", "frac_decreasing",
]
MINIMAL_4 = [
    "mean_dist", "dwell_in_proximity_ms", "min_dist", "direction_changes",
]


def build_data():
    feats_path = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    with open(feats_path) as f:
        feats = json.load(f)
    feat_idx = {(r["trial_id"], r["position"]): r for r in feats}
    trials = sorted({r["trial_id"] for r in feats})
    print(f"Trials: {len(trials):,}", flush=True)

    cursor_visits = {}
    print("Cursor visit counts...", flush=True)
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            v, _ = visit_counts_for_trial(tid)
        except Exception:
            continue
        if v is None:
            continue
        cursor_visits[tid] = v

    gaze_returns = {}
    print("Gaze distinct returns...", flush=True)
    for i, tid in enumerate(trials):
        if i % 400 == 0:
            print(f"  {i}/{len(trials)}", flush=True)
        try:
            r = count_revisits_per_trial(tid)
        except Exception:
            continue
        if r is None:
            continue
        gaze_returns[tid] = r["distinct_returns"]

    return feat_idx, trials, cursor_visits, gaze_returns


def tier_coverage(feat_idx, trials, cursor_visits, gaze_returns,
                  X_min, y, groups, predicted):
    """Compute per-tier trial and participant coverage.

    T1 = trials where the clicked AOI has cursor visit_count >= 2.
    T2 = trials in T1's complement where the cursor-dynamics 4-feature LR
         predicts gaze-regressed (true positive — model says regaze AND label
         agrees). Predicted positives that don't have a regaze ground-truth
         label are counted as model-flagged-deliberation, since gaze ground
         truth isn't available WILD-side.
    T3 = T1 ∪ T2.

    Reports trials_with_X, participants_with_X for each.
    """
    n_trials = len(trials)
    all_pids = {t.split("-")[0] for t in trials}

    tier1_trials = set()
    tier1_pids = set()
    for (tid, pos), row in feat_idx.items():
        if not row["was_clicked"]:
            continue
        v = cursor_visits.get(tid, {}).get(pos, 0)
        if v >= 2:
            tier1_trials.add(tid)
            tier1_pids.add(tid.split("-")[0])

    # T2 builds on the cursor-blind subset that the LR was trained against.
    # We need a record-aligned mapping from (X_min row index) to trial_id.
    # Reconstruct it.
    cursor_blind_records = []
    for (tid, pos), row in feat_idx.items():
        if not row["was_clicked"]:
            continue
        if row["min_dist"] >= 100:
            continue
        v = cursor_visits.get(tid, {}).get(pos, 0)
        if v != 1:
            continue
        gn = gaze_returns.get(tid, {}).get(pos, 0)
        target = 1 if gn >= 1 else 0
        feat_vec = [row[k] for k in MINIMAL_4]
        if any(v_ is None for v_ in feat_vec):
            continue
        cursor_blind_records.append((tid, pos, target))

    assert len(cursor_blind_records) == len(predicted), \
        f"{len(cursor_blind_records)} vs {len(predicted)}"

    tier2_trials = set()
    tier2_pids = set()
    for (tid, pos, target), pred_prob in zip(cursor_blind_records, predicted):
        # Tier 2 = predicted regaze on cursor-blind subset, threshold 0.5.
        if pred_prob >= 0.5:
            tier2_trials.add(tid)
            tier2_pids.add(tid.split("-")[0])

    tier3_trials = tier1_trials | tier2_trials
    tier3_pids = tier1_pids | tier2_pids

    return {
        "n_trials": n_trials,
        "n_participants": len(all_pids),
        "T1_trials": len(tier1_trials),
        "T1_pids": len(tier1_pids),
        "T2_trials": len(tier2_trials),
        "T2_pids": len(tier2_pids),
        "T3_trials": len(tier3_trials),
        "T3_pids": len(tier3_pids),
    }


def lopo_per_fold(X, y, groups):
    """Run LOPO LR; return dict of {pid: auc}, skipping degenerate folds."""
    logo = LeaveOneGroupOut()
    fold_auc = {}
    for tr, te in logo.split(X, y, groups):
        pid = groups[te][0]
        if len(set(y[tr])) < 2 or len(set(y[te])) < 2:
            continue
        scaler = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(
            scaler.transform(X[tr]), y[tr]
        )
        prob = clf.predict_proba(scaler.transform(X[te]))[:, 1]
        try:
            fold_auc[pid] = roc_auc_score(y[te], prob)
        except Exception:
            pass
    return fold_auc


def fit_predict_all(X, y, groups):
    """Run LOPO and return predicted probabilities aligned with input order."""
    logo = LeaveOneGroupOut()
    pred = np.zeros(len(y), dtype=float)
    pred[:] = np.nan
    for tr, te in logo.split(X, y, groups):
        if len(set(y[tr])) < 2:
            continue
        scaler = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(
            scaler.transform(X[tr]), y[tr]
        )
        pred[te] = clf.predict_proba(scaler.transform(X[te]))[:, 1]
    return pred


def main():
    feat_idx, trials, cursor_visits, gaze_returns = build_data()

    # Build the 845-record cursor-blind subset.
    X_full_rows = []
    X_min_rows = []
    y = []
    groups = []
    for (tid, pos), row in feat_idx.items():
        if not row["was_clicked"]:
            continue
        if row["min_dist"] >= 100:
            continue
        v = cursor_visits.get(tid, {}).get(pos, 0)
        if v != 1:
            continue
        gn = gaze_returns.get(tid, {}).get(pos, 0)
        target = 1 if gn >= 1 else 0
        full_vec = [row[k] for k in M4_FULL]
        min_vec = [row[k] for k in MINIMAL_4]
        if any(v_ is None for v_ in full_vec):
            continue
        X_full_rows.append(full_vec)
        X_min_rows.append(min_vec)
        y.append(target)
        groups.append(tid.split("-")[0])
    X_full = np.array(X_full_rows, dtype=float)
    X_min = np.array(X_min_rows, dtype=float)
    y = np.array(y, dtype=int)
    groups = np.array(groups)
    print(f"\nCursor-blind subset: {len(y)} records, {len(set(groups))} participants")

    # Per-fold AUCs.
    fold_auc_full = lopo_per_fold(X_full, y, groups)
    fold_auc_min = lopo_per_fold(X_min, y, groups)
    print(f"Folds with both classes (full / min): {len(fold_auc_full)} / {len(fold_auc_min)}")

    # Predicted probabilities on cursor-blind subset (for tier 2 coverage).
    pred_min = fit_predict_all(X_min, y, groups)
    # Records with NaN prediction (one-class fold) treated as 0.5 (neutral).
    pred_min = np.where(np.isnan(pred_min), 0.5, pred_min)

    coverage = tier_coverage(
        feat_idx, trials, cursor_visits, gaze_returns,
        X_min, y, groups, pred_min,
    )
    print(f"\nCoverage:")
    for k, v in coverage.items():
        print(f"  {k}: {v}")

    # ─── Plot ──────────────────────────────────────────────────────────────
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 4.4),
                                    gridspec_kw={"width_ratios": [1.05, 1]})

    # Panel A: tier coverage. Two bars per tier (trial-level / participant-level).
    tiers = ["T1\ncursor revisit\n(visit ≥ 2)",
             "T2\ncursor dynamics\non cursor-blind",
             "T3\nT1 ∪ T2"]
    trial_pct = [
        100 * coverage["T1_trials"] / coverage["n_trials"],
        100 * coverage["T2_trials"] / coverage["n_trials"],
        100 * coverage["T3_trials"] / coverage["n_trials"],
    ]
    pid_pct = [
        100 * coverage["T1_pids"] / coverage["n_participants"],
        100 * coverage["T2_pids"] / coverage["n_participants"],
        100 * coverage["T3_pids"] / coverage["n_participants"],
    ]

    x = np.arange(3)
    w = 0.36
    barsA = axA.bar(x - w/2, trial_pct, w, label="trials",
                    color="#4477aa", edgecolor="black", linewidth=0.6)
    barsB = axA.bar(x + w/2, pid_pct, w, label="participants",
                    color="#ee6677", edgecolor="black", linewidth=0.6)

    for bar, val in zip(barsA, trial_pct):
        axA.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                 f"{val:.1f}%", ha="center", fontsize=9)
    for bar, val in zip(barsB, pid_pct):
        axA.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                 f"{val:.1f}%", ha="center", fontsize=9)

    axA.set_xticks(x)
    axA.set_xticklabels(tiers, fontsize=9)
    axA.set_ylabel("coverage (%)", fontsize=10)
    axA.set_ylim(0, 110)
    axA.set_title(f"(a) Three-tier coverage  (n={coverage['n_trials']:,} trials, "
                  f"{coverage['n_participants']} participants)", fontsize=10)
    axA.legend(loc="upper left", fontsize=9, frameon=False)
    axA.spines["top"].set_visible(False)
    axA.spines["right"].set_visible(False)
    axA.axhline(100, color="grey", linewidth=0.5, linestyle=":")
    axA.grid(axis="y", linewidth=0.4, alpha=0.4)

    # Panel B: per-fold AUC for tier-2 inference.
    full_aucs = np.array(list(fold_auc_full.values()))
    min_aucs = np.array(list(fold_auc_min.values()))

    pos = [1, 2]
    bp = axB.boxplot(
        [full_aucs, min_aucs],
        positions=pos, widths=0.5,
        patch_artist=True, showfliers=False,
        medianprops=dict(color="black", linewidth=1.4),
    )
    box_colors = ["#bbddee", "#ffccbb"]
    for patch, c in zip(bp["boxes"], box_colors):
        patch.set_facecolor(c)
        patch.set_edgecolor("black")
        patch.set_linewidth(0.6)

    rng = np.random.default_rng(0)
    for p, aucs, c in zip(pos, [full_aucs, min_aucs], ["#225588", "#cc4422"]):
        jitter = rng.normal(0, 0.05, len(aucs))
        axB.scatter(np.full(len(aucs), p) + jitter, aucs,
                    s=14, alpha=0.6, color=c, edgecolor="white",
                    linewidth=0.4, zorder=3)

    axB.axhline(0.5, color="grey", linewidth=0.6, linestyle="--")
    axB.text(2.55, 0.50, "chance", fontsize=8, color="grey", va="center")

    axB.set_xticks(pos)
    axB.set_xticklabels(
        [f"M4 full\n(9 features)\n{full_aucs.mean():.3f} ± {full_aucs.std():.3f}",
         f"minimal-4\n{min_aucs.mean():.3f} ± {min_aucs.std():.3f}"],
        fontsize=9,
    )
    axB.set_ylabel("LOPO AUC per participant", fontsize=10)
    axB.set_ylim(0.2, 1.05)
    axB.set_title(f"(b) Tier-2 cursor-dynamics inference  (n={len(y)} cursor-blind records)",
                  fontsize=10)
    axB.spines["top"].set_visible(False)
    axB.spines["right"].set_visible(False)
    axB.grid(axis="y", linewidth=0.4, alpha=0.4)

    plt.tight_layout()
    out_pdf = OUT_DIR / "three_tier_recovery.pdf"
    out_png = OUT_DIR / "three_tier_recovery.png"
    plt.savefig(out_pdf, bbox_inches="tight")
    plt.savefig(out_png, dpi=180, bbox_inches="tight")
    print(f"\nWrote {out_pdf}")
    print(f"Wrote {out_png}")

    # Save coverage + fold-level data for paper citation.
    summary = {
        "coverage": coverage,
        "tier2_full_m4_aucs": {p: float(a) for p, a in fold_auc_full.items()},
        "tier2_minimal_4_aucs": {p: float(a) for p, a in fold_auc_min.items()},
        "tier2_full_m4_summary": {
            "mean": float(full_aucs.mean()),
            "median": float(np.median(full_aucs)),
            "std": float(full_aucs.std()),
            "n_folds": int(len(full_aucs)),
        },
        "tier2_minimal_4_summary": {
            "mean": float(min_aucs.mean()),
            "median": float(np.median(min_aucs)),
            "std": float(min_aucs.std()),
            "n_folds": int(len(min_aucs)),
        },
    }
    summary_path = ROOT / "scripts/output/regaze_no_rehover/three_tier_recovery.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
