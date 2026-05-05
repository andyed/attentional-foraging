"""[RETIRED 2026-05-05] Use scripts/ltr_typed_four_class.py instead.

This script is the original (Apr 15) graded-vs-click LTR experiment. It is
retired because its data + model assumptions are stale on three fronts:

  1. Reads cursor-approach-features.json (Apr 12), which is pre-typed-cascade
     and pre-prefix-bug-fix. Numbers from this script reflect mis-typed
     AOIs and a known etype-prefix bug (see methodology cascade synthesis).
  2. Uses sklearn GradientBoostingRegressor pointwise, not LightGBM
     LambdaRank — the spec from Peter Dixon-Moses (2026-05-04) calls for
     LambdaRank with NDCG@10 optimize / MRR@10 evaluate.
  3. Treats NotApprAbove and NotApprBelow identically (both 0). Peter's
     spec excludes NotApprBelow from training, since those AOIs were
     never reached by the user — they have no behavioral signal.

The replacement (scripts/ltr_typed_four_class.py) addresses all three.
Result: 4-class graded labels deliver +0.030 MRR@10 over binary-click
LambdaMART on the same NotApprBelow-excluded training set.

This file is preserved only as a historical record. Do not run it.

==== ORIGINAL DOCSTRING BELOW ====

LTR ranker training: graded 4-cell labels vs binary click labels.

Peter Dixon-Moses pointed out that the four-class examination taxonomy's
natural downstream use is as **graded relevance labels** for LTR ranker
training (LambdaMART-style), not as hard negatives for dense retrievers.
This script tests whether training an LTR ranker on the four-cell labels
produces better rank-recovery of the clicked item than training on
binary click labels alone, using AdSERP as a self-contained dataset.

Label schemes:
- **Graded (4-cell)**: Clicked → 2, Deferred (NB22 gaze-regression) → 1,
                       Eval-rejected and Not-approached → 0
- **Binary click**:    Clicked → 1, Else → 0

Features (query/result text + position only, deliberately minimal so the
comparison is about the label signal, not feature engineering):
- original_position       — 0..9 SERP rank
- title_overlap           — cosine-like overlap of query tokens with title tokens
- snippet_overlap         — same for snippet
- title_len               — number of title tokens
- snippet_len             — number of snippet tokens
- has_query_token_in_title — binary
- has_query_token_in_snippet — binary

Protocol: leave-one-participant-out (47 folds, matching M4/M5 LOSO).

Metric: MRR@10 on rank-of-the-clicked-item in the ranker's output, averaged
over all held-out trials. Also NDCG@10 with binary click gain. Baselines:
original SERP position (no reranking), click-trained ranker, position-only LR.

Outputs: scripts/output/ltr_graded_vs_click/summary.json
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import extract_serp_results, tokenize  # noqa: E402

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
META_DIR = ROOT / "AdSERP/data/trial-metadata"
OUT_DIR = ROOT / "scripts/output/ltr_graded_vs_click"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_NAMES = [
    "position",
    "title_overlap",
    "snippet_overlap",
    "title_len",
    "snippet_len",
    "query_in_title",
    "query_in_snippet",
]


def get_trial_query_tokens(trial_id):
    """Parse the query string from the trial metadata XML."""
    path = META_DIR / f"{trial_id}.xml"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<url>([^<]+)</url>", text)
    if not m:
        return None
    try:
        parsed = urlparse(m.group(1))
        params = parse_qs(parsed.query)
        q = params.get("q", [""])[0]
    except Exception:
        return None
    q = unquote(q).replace("-", " ")
    return tokenize(q)


def compute_features(query_tokens, serp_results, n_results=10):
    """Return (n_results, n_features) matrix for a single trial."""
    q_set = set(query_tokens)
    q_len = max(len(query_tokens), 1)
    X = np.zeros((n_results, len(FEATURE_NAMES)), dtype=float)
    for i in range(n_results):
        if i >= len(serp_results):
            X[i] = [i, 0.0, 0.0, 0, 0, 0, 0]
            continue
        r = serp_results[i]
        title_tokens = tokenize(r.get("title", ""))
        snip_tokens = tokenize(r.get("snippet", ""))
        title_set = set(title_tokens)
        snip_set = set(snip_tokens)
        title_len = max(len(title_tokens), 1)
        snip_len = max(len(snip_tokens), 1)
        # Cosine-like overlap on token sets: |intersection| / sqrt(|A|*|B|)
        title_overlap = len(q_set & title_set) / np.sqrt(q_len * title_len)
        snip_overlap = len(q_set & snip_set) / np.sqrt(q_len * snip_len)
        X[i] = [
            i,
            title_overlap,
            snip_overlap,
            len(title_tokens),
            len(snip_tokens),
            int(bool(q_set & title_set)),
            int(bool(q_set & snip_set)),
        ]
    return X


def build_dataset(lab_records, regression_labels):
    """Build per-trial feature matrices and label vectors.

    Returns:
        trial_order: list of trial_ids
        X_by_trial: dict trial_id → (10, n_features) matrix
        graded_by_trial: dict trial_id → (10,) graded labels
        click_by_trial: dict trial_id → (10,) binary click labels
        pid_by_trial: dict trial_id → participant id (for grouping)
    """
    # Group LAB records by trial_id
    by_trial = defaultdict(dict)
    for i, r in enumerate(lab_records):
        tid = r["trial_id"]
        pos = int(r["position"])
        by_trial[tid][pos] = {
            "was_clicked": bool(r["was_clicked"]),
            "gaze_regression": bool(regression_labels[i]),
            "min_dist": float(r.get("min_dist", 1e9)),
        }

    X_by_trial = {}
    graded_by_trial = {}
    click_by_trial = {}
    pid_by_trial = {}
    trial_order = []
    skipped = {"no_query": 0, "no_serp": 0, "no_click": 0}

    for tid, positions in sorted(by_trial.items()):
        q_tokens = get_trial_query_tokens(tid)
        if q_tokens is None or len(q_tokens) == 0:
            skipped["no_query"] += 1
            continue
        try:
            serp = extract_serp_results(tid)
        except Exception:
            skipped["no_serp"] += 1
            continue
        if not serp:
            skipped["no_serp"] += 1
            continue

        X = compute_features(q_tokens, serp, n_results=10)
        graded = np.zeros(10, dtype=int)
        click = np.zeros(10, dtype=int)
        for pos, info in positions.items():
            if pos >= 10:
                continue
            approached = info["min_dist"] < 100
            if info["was_clicked"]:
                graded[pos] = 2
                click[pos] = 1
            elif approached and info["gaze_regression"]:
                graded[pos] = 1  # deferred = Relevant
            else:
                graded[pos] = 0  # eval-rejected + not-approached

        if click.sum() == 0:
            skipped["no_click"] += 1
            continue

        X_by_trial[tid] = X
        graded_by_trial[tid] = graded
        click_by_trial[tid] = click
        pid_by_trial[tid] = tid.split("-")[0]
        trial_order.append(tid)

    return trial_order, X_by_trial, graded_by_trial, click_by_trial, pid_by_trial, skipped


def flatten(trial_ids, X_by_trial, label_by_trial, pid_by_trial):
    X_list, y_list, g_list, t_list = [], [], [], []
    for tid in trial_ids:
        X_list.append(X_by_trial[tid])
        y_list.append(label_by_trial[tid])
        g_list.append(np.full(10, pid_by_trial[tid], dtype=object))
        t_list.append(np.full(10, tid, dtype=object))
    return (
        np.vstack(X_list),
        np.concatenate(y_list),
        np.concatenate(g_list),
        np.concatenate(t_list),
    )


def compute_mrr_ndcg(trial_ids, click_by_trial, scores_per_sample, trial_ids_per_sample):
    """For each trial, rank the 10 results by predicted score, find the
    position of the clicked item in the reranked list (1-indexed), and
    compute MRR@10 + NDCG@10 (binary click gain)."""
    # Group sample scores back by trial
    scores_by_trial = defaultdict(list)
    for score, tid in zip(scores_per_sample, trial_ids_per_sample):
        scores_by_trial[tid].append(score)

    mrr = []
    ndcg = []
    for tid in trial_ids:
        scores = np.array(scores_by_trial[tid])
        if len(scores) < 10:
            continue
        click = click_by_trial[tid]
        # Rerank positions by descending score (break ties by original position)
        order = np.lexsort((np.arange(10), -scores))
        reranked_click = click[order]
        # 1-indexed rank of the click
        click_rank = np.argmax(reranked_click) + 1
        mrr.append(1.0 / click_rank)
        # NDCG@10 with binary click gain (only one relevant item)
        ndcg.append(1.0 / np.log2(click_rank + 1))
    return float(np.mean(mrr)), float(np.mean(ndcg)), len(mrr)


def baseline_position_scores(X_all):
    """Score = -position (rank 0 scores highest, matches original SERP)."""
    return -X_all[:, FEATURE_NAMES.index("position")]


def train_loso_scores(X_by_trial, label_by_trial, pid_by_trial, trial_ids, model_factory,
                       feature_mask=None):
    """Leave-one-participant-out training with per-fold prediction.

    If feature_mask is provided (boolean array over FEATURE_NAMES), only
    those columns are used as model input. Always returns predictions in
    the full-X order so downstream code doesn't have to know about masking.
    """
    X_all, y_all, groups_all, trial_all = flatten(
        trial_ids, X_by_trial, label_by_trial, pid_by_trial)

    X_model = X_all[:, feature_mask] if feature_mask is not None else X_all

    pred = np.zeros(len(X_all), dtype=float)
    gkf = GroupKFold(n_splits=len(set(groups_all)))
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X_model, y_all, groups=groups_all)):
        model = model_factory()
        model.fit(X_model[train_idx], y_all[train_idx])
        pred[test_idx] = model.predict(X_model[test_idx])
    return pred, trial_all


def gbr_factory():
    return GradientBoostingRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)


def lr_factory():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000)),
    ])


class PositionOnlyRegressor:
    def fit(self, X, y):
        self.coef_ = np.corrcoef(X[:, 0], y)[0, 1]
    def predict(self, X):
        return -X[:, 0]  # lower position → higher score


def position_factory():
    return PositionOnlyRegressor()


def main():
    print("=" * 70)
    print("LTR ranker: graded 4-cell vs binary click labels")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)
    print(f"  {len(lab_records):,} LAB records")

    print("\nparsing SERP HTML + trial metadata (~2-3 min for 2,776 trials)...")
    trial_ids, X_by_trial, graded_by_trial, click_by_trial, pid_by_trial, skipped = \
        build_dataset(lab_records, regression_labels)
    print(f"  trials in dataset: {len(trial_ids):,}")
    print(f"  skipped: {skipped}")
    n_participants = len(set(pid_by_trial.values()))
    print(f"  participants: {n_participants}")

    # Baseline: original SERP position
    print("\n── Baseline 1: original SERP position (no reranking) ──")
    X_all, _, _, trial_all = flatten(trial_ids, X_by_trial, click_by_trial, pid_by_trial)
    pos_scores = baseline_position_scores(X_all)
    mrr0, ndcg0, n0 = compute_mrr_ndcg(trial_ids, click_by_trial, pos_scores, trial_all)
    print(f"  MRR@10 = {mrr0:.4f}   NDCG@10 = {ndcg0:.4f}   (n={n0})")

    # ── Condition A: ALL features (position + 6 text features) ──
    print("\n── Condition A: all 7 features (position + text) ──")
    print("  LTR on binary click labels (GBR, LOPO)...")
    click_pred_A, _ = train_loso_scores(
        X_by_trial, click_by_trial, pid_by_trial, trial_ids, gbr_factory)
    mrr_click_A, ndcg_click_A, n_click_A = compute_mrr_ndcg(
        trial_ids, click_by_trial, click_pred_A, trial_all)
    print(f"    MRR@10 = {mrr_click_A:.4f}   NDCG@10 = {ndcg_click_A:.4f}")

    print("  LTR on graded 4-cell labels (GBR, LOPO)...")
    graded_pred_A, _ = train_loso_scores(
        X_by_trial, graded_by_trial, pid_by_trial, trial_ids, gbr_factory)
    mrr_graded_A, ndcg_graded_A, _ = compute_mrr_ndcg(
        trial_ids, click_by_trial, graded_pred_A, trial_all)
    print(f"    MRR@10 = {mrr_graded_A:.4f}   NDCG@10 = {ndcg_graded_A:.4f}")

    # ── Condition B: TEXT-ONLY (no position feature) ──
    # Force the ranker to use only query-text-content signals, so any
    # graded-vs-click advantage has room to manifest without being absorbed
    # by the dominant position feature.
    text_only_mask = np.array([name != "position" for name in FEATURE_NAMES], dtype=bool)
    print("\n── Condition B: 6 text-only features (position DROPPED) ──")
    print("  LTR on binary click labels (GBR, LOPO)...")
    click_pred_B, _ = train_loso_scores(
        X_by_trial, click_by_trial, pid_by_trial, trial_ids, gbr_factory,
        feature_mask=text_only_mask)
    mrr_click_B, ndcg_click_B, _ = compute_mrr_ndcg(
        trial_ids, click_by_trial, click_pred_B, trial_all)
    print(f"    MRR@10 = {mrr_click_B:.4f}   NDCG@10 = {ndcg_click_B:.4f}")

    print("  LTR on graded 4-cell labels (GBR, LOPO)...")
    graded_pred_B, _ = train_loso_scores(
        X_by_trial, graded_by_trial, pid_by_trial, trial_ids, gbr_factory,
        feature_mask=text_only_mask)
    mrr_graded_B, ndcg_graded_B, _ = compute_mrr_ndcg(
        trial_ids, click_by_trial, graded_pred_B, trial_all)
    print(f"    MRR@10 = {mrr_graded_B:.4f}   NDCG@10 = {ndcg_graded_B:.4f}")

    # Headline numbers
    mrr_click = mrr_click_A
    mrr_graded = mrr_graded_A
    ndcg_click = ndcg_click_A
    ndcg_graded = ndcg_graded_A
    n_click = n_click_A

    # Summary
    delta_click = mrr_click - mrr0
    delta_graded = mrr_graded - mrr0
    graded_over_click = mrr_graded - mrr_click

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Original SERP position (no ML)          MRR = {mrr0:.4f}   NDCG = {ndcg0:.4f}")
    print(f"  A) 7 features (incl. position):")
    print(f"      LTR binary click                    MRR = {mrr_click_A:.4f}   NDCG = {ndcg_click_A:.4f}   ΔMRR = {mrr_click_A - mrr0:+.4f}")
    print(f"      LTR graded 4-cell                   MRR = {mrr_graded_A:.4f}   NDCG = {ndcg_graded_A:.4f}   ΔMRR = {mrr_graded_A - mrr0:+.4f}")
    print(f"      Graded − click (ΔMRR)                            {mrr_graded_A - mrr_click_A:+.4f}")
    print(f"  B) 6 features (text only, no position):")
    print(f"      LTR binary click                    MRR = {mrr_click_B:.4f}   NDCG = {ndcg_click_B:.4f}   ΔMRR = {mrr_click_B - mrr0:+.4f}")
    print(f"      LTR graded 4-cell                   MRR = {mrr_graded_B:.4f}   NDCG = {ndcg_graded_B:.4f}   ΔMRR = {mrr_graded_B - mrr0:+.4f}")
    print(f"      Graded − click (ΔMRR)                            {mrr_graded_B - mrr_click_B:+.4f}")

    summary = {
        "experiment": "LTR ranker: graded 4-cell vs binary click labels",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "dataset": {
            "trials": len(trial_ids),
            "participants": n_participants,
            "skipped": skipped,
            "features": FEATURE_NAMES,
        },
        "baseline_serp_position": {"MRR@10": mrr0, "NDCG@10": ndcg0, "n": n0},
        "condition_A_with_position": {
            "features": FEATURE_NAMES,
            "ltr_binary_click": {
                "MRR@10": mrr_click_A, "NDCG@10": ndcg_click_A,
                "delta_vs_baseline": mrr_click_A - mrr0,
            },
            "ltr_graded_4cell": {
                "MRR@10": mrr_graded_A, "NDCG@10": ndcg_graded_A,
                "delta_vs_baseline": mrr_graded_A - mrr0,
            },
            "graded_minus_click_delta_MRR": mrr_graded_A - mrr_click_A,
        },
        "condition_B_text_only": {
            "features": [n for n in FEATURE_NAMES if n != "position"],
            "ltr_binary_click": {
                "MRR@10": mrr_click_B, "NDCG@10": ndcg_click_B,
                "delta_vs_baseline": mrr_click_B - mrr0,
            },
            "ltr_graded_4cell": {
                "MRR@10": mrr_graded_B, "NDCG@10": ndcg_graded_B,
                "delta_vs_baseline": mrr_graded_B - mrr0,
            },
            "graded_minus_click_delta_MRR": mrr_graded_B - mrr_click_B,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
