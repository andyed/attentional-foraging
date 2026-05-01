"""NB26 Rung 4 — continuous withstood_evaluation labels (Phase 3).

Context
-------
NB26 bg run (2026-04-19, `scripts/output/nb26_viewport_rungs/`) established the
3-grade / 2-grade rung picture. Rung 3 (text + M4 + VP, 3-grade graded) gave
MRR 0.68; viewport-on-top-of-M4 hurt (Δ = −0.099).

Phase 3 hypothesis (Andy): denser, continuous labels squeeze more pairwise
gradient out of the same features. With 10 graded ranks per trial, LambdaMART
sees ~45 informative pairs per group instead of ≤3 from the 3-grade scheme.

Labels
------
  w_pre  = withstood_pre_click (continuous, leakage-mitigated)
  w_full = withstood_full      (continuous, click-inclusive upper bound)

From these we build:
  g10_pre  — rank-within-trial of w_pre,  grade 0..9 (highest w = 9)
  g10_full — rank-within-trial of w_full, grade 0..9
  w_pre    — continuous target for pointwise Ridge (R4c)

Rank-within-trial gives each trial exactly one of each grade, which maximises
within-group ordering information for LambdaMART.

Configurations (all on text + M4 + VP features = Rung 3 feature set)
-------------------------------------------------------------------
  R3_3grade           NB26 g3,   LambdaMART graded 3-level (apples-to-apples re-run)
  R4a_10grade_pre     g10_pre,   LambdaMART 10-level (label_gain = [2^i])
  R4b_10grade_full    g10_full,  LambdaMART 10-level (leakage upper bound)
  R4c_continuous_pre  w_pre,     Ridge MSE pointwise

Headline contrast: R4a vs R3_3grade, paired Wilcoxon on MRR + NDCG@10.

Output: scripts/output/nb26_rung4_withstood/summary.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMRanker

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))

from nb26_viewport_rungs import (  # noqa: E402
    load_all, build_full_serp, features_for,
    mrr_from_scores, ndcg_from_scores,
    mrr_original_full, ndcg_original_full,
    paired_wilcoxon,
)

WITHSTOOD = ROOT / "AdSERP/data/withstood-evaluation-score.json"
OUT_DIR = ROOT / "scripts/output/nb26_rung4_withstood"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def attach_withstood(full_serp: dict) -> None:
    """Attach withstood_pre_click, withstood_full, and rank-within-trial
    10-grade labels to every record in full_serp."""
    w_rows = json.load(open(WITHSTOOD))
    w_by_key = {(r["trial_id"], int(r["position"])): r for r in w_rows}

    missing = 0
    for tid, recs in full_serp.items():
        for r in recs:
            key = (tid, r["position"])
            w = w_by_key.get(key)
            if w is None:
                r["w_pre"] = 0.0
                r["w_full"] = 0.0
                missing += 1
                continue
            r["w_pre"] = float(w["withstood_pre_click"])
            r["w_full"] = float(w["withstood_full"])

        # Rank-within-trial: highest withstood → grade 9.
        pre_vals = np.array([r["w_pre"] for r in recs])
        full_vals = np.array([r["w_full"] for r in recs])
        rank_pre = np.argsort(np.argsort(pre_vals, kind="stable"), kind="stable")
        rank_full = np.argsort(np.argsort(full_vals, kind="stable"), kind="stable")
        for i, r in enumerate(recs):
            r["g10_pre"] = int(rank_pre[i])
            r["g10_full"] = int(rank_full[i])
            r["g10_pre_eligible"] = True
            r["g10_full_eligible"] = True
            r["w_pre_eligible"] = True
            r["w_full_eligible"] = True
    if missing:
        print(f"[warn] {missing:,} (trial, pos) rows missing withstood; set to 0.0")


def run_lopo(full_serp, label_key, eligibility_key, feature_mode, ranker_kind, seed=0):
    trial_ids = sorted(full_serp.keys())
    pid_by_t = {t: full_serp[t][0]["participant"] for t in trial_ids}
    pid_to_t = defaultdict(list)
    for t, p in pid_by_t.items():
        pid_to_t[p].append(t)
    participants = sorted(pid_to_t.keys())

    mrr_by_trial, ndcg_by_trial = {}, {}
    for held in participants:
        held_set = set(pid_to_t[held])
        train_tids = [t for t in trial_ids if t not in held_set]

        X_list, y_list, groups = [], [], []
        for tid in train_tids:
            recs = full_serp[tid]
            elig = [r for r in recs if r[eligibility_key] and r[label_key] is not None]
            if len(elig) < 2:
                continue
            X_list.append(features_for(elig, feature_mode))
            y_list.append(np.array([r[label_key] for r in elig], dtype=float))
            groups.append(len(elig))
        X_train = np.vstack(X_list)
        y_train = np.concatenate(y_list)
        groups_arr = np.array(groups, dtype=int)

        if ranker_kind == "lgbm_3grade":
            model = LGBMRanker(objective="lambdarank", label_gain=[0, 1, 2],
                               n_estimators=200, num_leaves=31, learning_rate=0.05,
                               min_child_samples=10, random_state=seed, verbose=-1)
            model.fit(X_train, y_train.astype(int), group=groups_arr)
            sf = lambda X: model.predict(X)
        elif ranker_kind == "lgbm_10grade":
            label_gain = [float(2 ** i) for i in range(10)]
            model = LGBMRanker(objective="lambdarank", label_gain=label_gain,
                               n_estimators=200, num_leaves=31, learning_rate=0.05,
                               min_child_samples=10, random_state=seed, verbose=-1)
            model.fit(X_train, y_train.astype(int), group=groups_arr)
            sf = lambda X: model.predict(X)
        elif ranker_kind == "ridge_mse":
            pipe = Pipeline([
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=1.0, random_state=seed)),
            ])
            # Ridge with NaN features: replace NaN with column mean before fit
            X_train_clean = np.where(np.isnan(X_train), 0.0, X_train)
            pipe.fit(X_train_clean, y_train)
            sf = lambda X: pipe.predict(np.where(np.isnan(X), 0.0, X))
        else:
            raise ValueError(ranker_kind)

        for tid in held_set:
            recs = full_serp[tid]
            X_test = features_for(recs, feature_mode)
            scores = sf(X_test)
            assert len(scores) == 10
            mrr_by_trial[tid] = mrr_from_scores(recs, scores)
            ndcg_by_trial[tid] = ndcg_from_scores(recs, scores, k=10)

    per_p_mrr = defaultdict(list)
    per_p_ndcg = defaultdict(list)
    for tid, m in mrr_by_trial.items():
        pid = pid_by_t[tid]
        per_p_mrr[pid].append(m)
        per_p_ndcg[pid].append(ndcg_by_trial[tid])
    return {
        "mrr_per_trial": mrr_by_trial,
        "ndcg_per_trial": ndcg_by_trial,
        "mrr_per_p": {p: float(np.mean(v)) for p, v in per_p_mrr.items()},
        "ndcg_per_p": {p: float(np.mean(v)) for p, v in per_p_ndcg.items()},
        "concat_mrr": float(np.mean(list(mrr_by_trial.values()))),
        "concat_ndcg": float(np.mean(list(ndcg_by_trial.values()))),
    }


def seed_avg(full_serp, label_key, eligibility_key, feature_mode, ranker_kind, seeds=(0, 1, 2)):
    runs = [run_lopo(full_serp, label_key, eligibility_key, feature_mode, ranker_kind, seed=s)
            for s in seeds]
    tids = sorted(set().union(*[set(r["mrr_per_trial"].keys()) for r in runs]))
    mrr_pt = {t: float(np.mean([r["mrr_per_trial"][t] for r in runs])) for t in tids}
    ndcg_pt = {t: float(np.mean([r["ndcg_per_trial"][t] for r in runs])) for t in tids}
    pid_by_t = {t: full_serp[t][0]["participant"] for t in tids}
    per_p_mrr = defaultdict(list)
    per_p_ndcg = defaultdict(list)
    for t in tids:
        pid = pid_by_t[t]
        per_p_mrr[pid].append(mrr_pt[t])
        per_p_ndcg[pid].append(ndcg_pt[t])
    return {
        "mrr_per_trial": mrr_pt,
        "ndcg_per_trial": ndcg_pt,
        "mrr_per_p": {p: float(np.mean(v)) for p, v in per_p_mrr.items()},
        "ndcg_per_p": {p: float(np.mean(v)) for p, v in per_p_ndcg.items()},
        "concat_mrr": float(np.mean(list(mrr_pt.values()))),
        "concat_ndcg": float(np.mean(list(ndcg_pt.values()))),
    }


def main():
    data = load_all()
    full_serp = build_full_serp(data)
    attach_withstood(full_serp)

    # Label distribution sanity
    g10_pre_counts = defaultdict(int)
    g10_full_counts = defaultdict(int)
    click_bucket_pre = defaultdict(int)
    click_bucket_full = defaultdict(int)
    for recs in full_serp.values():
        for r in recs:
            g10_pre_counts[r["g10_pre"]] += 1
            g10_full_counts[r["g10_full"]] += 1
            if r["clicked"]:
                click_bucket_pre[r["g10_pre"]] += 1
                click_bucket_full[r["g10_full"]] += 1
    print(f"\n[labels] g10_pre  per-bucket counts: {dict(sorted(g10_pre_counts.items()))}")
    print(f"[labels] g10_full per-bucket counts: {dict(sorted(g10_full_counts.items()))}")
    print(f"[labels] clicked by g10_pre bucket : {dict(sorted(click_bucket_pre.items()))}")
    print(f"[labels] clicked by g10_full bucket: {dict(sorted(click_bucket_full.items()))}")

    fmode = "text_m4_vp"
    configs = [
        ("R3_3grade",          "g3",       "g3_eligible",        "lgbm_3grade"),
        ("R4a_10grade_pre",    "g10_pre",  "g10_pre_eligible",   "lgbm_10grade"),
        ("R4b_10grade_full",   "g10_full", "g10_full_eligible",  "lgbm_10grade"),
        ("R4c_continuous_pre", "w_pre",    "w_pre_eligible",     "ridge_mse"),
    ]

    results = {}
    for tag, label_key, elig_key, ranker in configs:
        print(f"\n[run] {tag}  label={label_key}  ranker={ranker}")
        results[tag] = seed_avg(full_serp, label_key, elig_key, fmode, ranker)
        print(f"       MRR = {results[tag]['concat_mrr']:.4f}   "
              f"NDCG@10 = {results[tag]['concat_ndcg']:.4f}")

    # Baseline MRR/NDCG from original Google ranking for reference
    orig_per_trial_mrr = {tid: mrr_original_full(recs) for tid, recs in full_serp.items()}
    orig_per_trial_ndcg = {tid: ndcg_original_full(recs) for tid, recs in full_serp.items()}
    pid_by_t = {t: full_serp[t][0]["participant"] for t in full_serp}
    per_p_mrr = defaultdict(list)
    per_p_ndcg = defaultdict(list)
    for t in full_serp:
        pid = pid_by_t[t]
        per_p_mrr[pid].append(orig_per_trial_mrr[t])
        per_p_ndcg[pid].append(orig_per_trial_ndcg[t])
    orig_res = {
        "mrr_per_p": {p: float(np.mean(v)) for p, v in per_p_mrr.items()},
        "ndcg_per_p": {p: float(np.mean(v)) for p, v in per_p_ndcg.items()},
        "concat_mrr": float(np.mean(list(orig_per_trial_mrr.values()))),
        "concat_ndcg": float(np.mean(list(orig_per_trial_ndcg.values()))),
    }
    print(f"\n[K6 — Google baseline] MRR = {orig_res['concat_mrr']:.4f}  "
          f"NDCG@10 = {orig_res['concat_ndcg']:.4f}")

    # Paired tests vs R3 3-grade baseline (the central contrast)
    print("\n-- Paired Wilcoxon vs R3 3-grade graded (greater) --")
    paired = {}
    baseline = results["R3_3grade"]
    for tag in ("R4a_10grade_pre", "R4b_10grade_full", "R4c_continuous_pre"):
        a = results[tag]
        r_mrr = paired_wilcoxon(a, baseline, "mrr")
        r_ndcg = paired_wilcoxon(a, baseline, "ndcg")
        paired[f"{tag}_vs_R3__mrr"] = r_mrr
        paired[f"{tag}_vs_R3__ndcg"] = r_ndcg
        print(f"  {tag:25s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")

    # Paired tests vs Google baseline (apples-to-apples with K6)
    print("\n-- Paired Wilcoxon vs Google baseline --")
    for tag in ("R3_3grade", "R4a_10grade_pre", "R4b_10grade_full", "R4c_continuous_pre"):
        a = results[tag]
        r_mrr = paired_wilcoxon(a, orig_res, "mrr")
        r_ndcg = paired_wilcoxon(a, orig_res, "ndcg")
        paired[f"{tag}_vs_google__mrr"] = r_mrr
        paired[f"{tag}_vs_google__ndcg"] = r_ndcg
        print(f"  {tag:25s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")

    # Save
    summary = {
        "feature_mode": fmode,
        "label_distributions": {
            "g10_pre":  dict(sorted(g10_pre_counts.items())),
            "g10_full": dict(sorted(g10_full_counts.items())),
        },
        "clicked_by_bucket": {
            "g10_pre":  dict(sorted(click_bucket_pre.items())),
            "g10_full": dict(sorted(click_bucket_full.items())),
        },
        "baseline_google": {"mrr": orig_res["concat_mrr"], "ndcg": orig_res["concat_ndcg"]},
        "rungs": {
            tag: {
                "mrr": v["concat_mrr"], "ndcg": v["concat_ndcg"],
                "mrr_per_p": v["mrr_per_p"], "ndcg_per_p": v["ndcg_per_p"],
            }
            for tag, v in results.items()
        },
        "paired_comparisons": paired,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
