"""NB26 Rung 4 variants — two follow-ups on the failed 10-grade baseline.

The first Rung 4 run (`scripts/output/nb26_rung4_withstood/summary.json`) found
rank-within-trial 10-grade UNDERperforms 3-grade on the text + M4 + VP feature
set (Δ MRR = −0.026, p = 0.98). Two hypotheses for why:

  (1) Label noise: 47 / 2,115 clicked items (2.2 %) land at grade 0 because
      their within-trial withstood rank is lowest. LambdaMART is trained to
      put these at the BOTTOM.
  (2) Gradient weighting: `label_gain = [2^i]` concentrates pairwise lambda
      on top-vs-rest pairs; the middle-grade pairs we paid for don't
      contribute much.

This script tests both remedies on text + M4 + VP:

  R4e_10grade_pre_linear   — same g10_pre label as R4a, linear gain [0..9]
  R4f_hybrid_exp           — g10_hybrid (click pinned at 9, rest ranked by
                              withstood_pre_click among the 9 non-clicks),
                              exp gain [2^i]   ← fixes noise, keeps gain shape
  R4g_hybrid_linear        — g10_hybrid label, linear gain [0..9]

Paired tests against two baselines (per-p metrics loaded from the earlier
summary.json, since identical seeds + trial ordering yield identical folds):

  vs R3_3grade         — does any variant beat the 3-grade LambdaMART?
  vs R4a_10grade_pre   — is the remedy actually doing anything vs. naive 10-grade?

Output: scripts/output/nb26_rung4_variants/summary.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from lightgbm import LGBMRanker

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "scripts"))

from nb26_viewport_rungs import (  # noqa: E402
    load_all, build_full_serp, features_for,
    mrr_from_scores, ndcg_from_scores,
    paired_wilcoxon,
)
from nb26_rung4_withstood import attach_withstood  # noqa: E402

PRIOR_SUMMARY = ROOT / "scripts/output/nb26_rung4_withstood/summary.json"
OUT_DIR = ROOT / "scripts/output/nb26_rung4_variants"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def attach_hybrid_label(full_serp: dict) -> None:
    """Grade 9 = clicked; remaining 9 positions ranked 0..8 by withstood_pre_click."""
    for tid, recs in full_serp.items():
        click_idx = None
        for i, r in enumerate(recs):
            if r["clicked"]:
                click_idx = i
                break
        if click_idx is None:
            # Shouldn't happen — build_full_serp filters to clicked trials
            for r in recs:
                r["g10_hybrid"] = 0
                r["g10_hybrid_eligible"] = False
            continue
        non_click_indices = [i for i in range(len(recs)) if i != click_idx]
        non_click_vals = np.array([recs[i]["w_pre"] for i in non_click_indices])
        ranks = np.argsort(np.argsort(non_click_vals, kind="stable"), kind="stable")
        for slot, i in enumerate(non_click_indices):
            recs[i]["g10_hybrid"] = int(ranks[slot])
            recs[i]["g10_hybrid_eligible"] = True
        recs[click_idx]["g10_hybrid"] = 9
        recs[click_idx]["g10_hybrid_eligible"] = True


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

        if ranker_kind == "lgbm_10grade_exp":
            label_gain = [float(2 ** i) for i in range(10)]
        elif ranker_kind == "lgbm_10grade_linear":
            label_gain = [float(i) for i in range(10)]
        else:
            raise ValueError(ranker_kind)
        model = LGBMRanker(objective="lambdarank", label_gain=label_gain,
                           n_estimators=200, num_leaves=31, learning_rate=0.05,
                           min_child_samples=10, random_state=seed, verbose=-1)
        model.fit(X_train, y_train.astype(int), group=groups_arr)
        sf = lambda X: model.predict(X)

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
    attach_withstood(full_serp)       # gives g10_pre, g10_full, w_pre, w_full
    attach_hybrid_label(full_serp)    # gives g10_hybrid (click@9, rest ranked)

    # Sanity check: hybrid label distribution
    hybrid_counts = defaultdict(int)
    click_bucket_hybrid = defaultdict(int)
    for recs in full_serp.values():
        for r in recs:
            hybrid_counts[r["g10_hybrid"]] += 1
            if r["clicked"]:
                click_bucket_hybrid[r["g10_hybrid"]] += 1
    print(f"\n[labels] g10_hybrid per-bucket counts: {dict(sorted(hybrid_counts.items()))}")
    print(f"[labels] clicked by g10_hybrid bucket: {dict(sorted(click_bucket_hybrid.items()))}")
    # Expected: each bucket has 2115 items, and bucket 9 has exactly 2115 clicks

    fmode = "text_m4_vp"
    configs = [
        ("R4e_10grade_pre_linear",  "g10_pre",    "g10_pre_eligible",    "lgbm_10grade_linear"),
        ("R4f_hybrid_exp",          "g10_hybrid", "g10_hybrid_eligible", "lgbm_10grade_exp"),
        ("R4g_hybrid_linear",       "g10_hybrid", "g10_hybrid_eligible", "lgbm_10grade_linear"),
    ]

    results = {}
    for tag, label_key, elig_key, ranker in configs:
        print(f"\n[run] {tag}  label={label_key}  ranker={ranker}")
        results[tag] = seed_avg(full_serp, label_key, elig_key, fmode, ranker)
        print(f"       MRR = {results[tag]['concat_mrr']:.4f}   "
              f"NDCG@10 = {results[tag]['concat_ndcg']:.4f}")

    # Load prior baselines for paired tests
    prior = json.load(open(PRIOR_SUMMARY))
    baselines = {
        "R3_3grade":       {"mrr_per_p": prior["rungs"]["R3_3grade"]["mrr_per_p"],
                            "ndcg_per_p": prior["rungs"]["R3_3grade"]["ndcg_per_p"]},
        "R4a_10grade_pre": {"mrr_per_p": prior["rungs"]["R4a_10grade_pre"]["mrr_per_p"],
                            "ndcg_per_p": prior["rungs"]["R4a_10grade_pre"]["ndcg_per_p"]},
    }

    print("\n-- Paired Wilcoxon vs R3_3grade (greater) --")
    paired = {}
    for tag in ("R4e_10grade_pre_linear", "R4f_hybrid_exp", "R4g_hybrid_linear"):
        a = results[tag]
        r_mrr = paired_wilcoxon(a, baselines["R3_3grade"], "mrr")
        r_ndcg = paired_wilcoxon(a, baselines["R3_3grade"], "ndcg")
        paired[f"{tag}_vs_R3__mrr"] = r_mrr
        paired[f"{tag}_vs_R3__ndcg"] = r_ndcg
        print(f"  {tag:25s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")

    print("\n-- Paired Wilcoxon vs R4a_10grade_pre (greater) — is the remedy working? --")
    for tag in ("R4e_10grade_pre_linear", "R4f_hybrid_exp", "R4g_hybrid_linear"):
        a = results[tag]
        r_mrr = paired_wilcoxon(a, baselines["R4a_10grade_pre"], "mrr")
        r_ndcg = paired_wilcoxon(a, baselines["R4a_10grade_pre"], "ndcg")
        paired[f"{tag}_vs_R4a__mrr"] = r_mrr
        paired[f"{tag}_vs_R4a__ndcg"] = r_ndcg
        print(f"  {tag:25s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")

    summary = {
        "feature_mode": fmode,
        "hybrid_bucket_counts": dict(sorted(hybrid_counts.items())),
        "clicked_by_hybrid_bucket": dict(sorted(click_bucket_hybrid.items())),
        "rungs": {
            tag: {
                "mrr": v["concat_mrr"], "ndcg": v["concat_ndcg"],
                "mrr_per_p": v["mrr_per_p"], "ndcg_per_p": v["ndcg_per_p"],
            }
            for tag, v in results.items()
        },
        "paired_comparisons": paired,
        "baselines_from": str(PRIOR_SUMMARY.relative_to(ROOT)),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
