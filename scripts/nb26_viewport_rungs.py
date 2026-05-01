"""NB26 rung expansion — add viewport + trajectory features and run 2-grade ablation.

Context
-------
NB26 current rungs:
  Rung 0: LR / Ridge on 5 text features   [K7, K8]
  Rung 1: LGBM on 5 text features          [K9, K10]
  Rung 2a: LGBM on 5 text + 9 M4 cursor    [K11, K12]  (M4 leakage caveat)

This script adds:
  Rung 2b: LGBM on 5 text + 6 viewport/trajectory  (cursor-free, no leakage)
  Rung 3:  LGBM on 5 text + 9 M4 + 6 viewport/trajectory  (kitchen sink)

And also runs Peter Dixon-Moses's label-scheme ablation across all three M-bearing
rungs:
  3-grade (baseline NB26):
    2 = clicked
    1 = approached ∧ gaze-regression-deferred
    0 = eval-rejected OR not-approached-above-click
  2-grade (Peter's ablation):
    2 = clicked
    1 = approached ∧ gaze-regression-deferred
    0 = approached ∧ ¬deferred ∧ ¬clicked  (eval-rejected only)
    EXCLUDED: all not-approached (above AND below click)

Feature sources
---------------
Text (5 feats):       on-the-fly from query+title+snippet text and embeddings.
M4 (9 feats):         AdSERP/data/cursor-approach-features.json
Viewport (4):         AdSERP/data/viewport-trajectory-features.json — vt_any,
                      vt_center_ms, avg_viewport_y, max_overlap_frac
Trajectory (2):       AdSERP/data/viewport-trajectory-features.json —
                      min_abs_velocity, n_reversals
                      (NB30 forward-selection optimum; 5 other traj feats
                       were redundant per K18–K19)

Evaluation
----------
Full-SERP LOPO, 47 folds, seeds 0/1/2 averaged. Each held-out trial gets scores
for all 10 positions; MRR and NDCG@10 are computed.

Metrics: MRR, NDCG@10 (equivalent to full-SERP NDCG since trials are fixed 10).

Output: scripts/output/nb26_viewport_rungs/summary.json + per-rung breakdowns.
"""
from __future__ import annotations

import json
import math
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMRanker

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

LAB_RECORDS = ROOT / "AdSERP/data/cursor-approach-features.json"
VP_FEATURES = ROOT / "AdSERP/data/viewport-trajectory-features.json"
REGRESSION_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
SERP_EMB_COMBINED = ROOT / "AdSERP/data/serp-embeddings.json"
SERP_EMB_SPLIT = ROOT / "AdSERP/data/serp-embeddings-split.json"
QUERY_EMB = ROOT / "AdSERP/data/query-embeddings.json"
OUT_DIR = ROOT / "scripts/output/nb26_viewport_rungs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

STOPWORDS = set("a an and or but the is are was were be been being "
                "to of in on at for from by with as "
                "this that these those".split())

M4_FEATURES = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

VP_FEATURES_MINIMAL = [
    "vt_any", "vt_center_ms", "avg_viewport_y", "max_overlap_frac",
    "min_abs_velocity", "n_reversals",
]


def tokenize(text):
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def cos_sim(a, b):
    if a is None or b is None:
        return 0.0
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_all():
    print("[load] cursor-approach-features.json")
    lab_records = json.load(open(LAB_RECORDS))
    print(f"       {len(lab_records):,} records")

    print("[load] viewport-trajectory-features.json")
    vp_rows = json.load(open(VP_FEATURES))
    vp_by_key = {(r["trial_id"], int(r["position"])): r for r in vp_rows}
    print(f"       {len(vp_by_key):,} rows")

    print("[load] regression-labels cache (NB22 gaze_regression)")
    regression_labels = np.array(json.load(open(REGRESSION_CACHE)), dtype=bool)
    print(f"       {len(regression_labels):,} labels")
    assert len(regression_labels) == len(lab_records)

    print("[load] embeddings")
    serp_combined = json.load(open(SERP_EMB_COMBINED))
    serp_split = json.load(open(SERP_EMB_SPLIT))
    query_data = json.load(open(QUERY_EMB))

    combined_emb, title_emb, snippet_emb = {}, {}, {}
    title_text, snippet_text = {}, {}
    for tid, rs in serp_combined.items():
        for r in rs:
            if "embedding" in r:
                combined_emb[(tid, r["position"])] = np.array(r["embedding"], dtype=np.float32)
    for tid, rs in serp_split.items():
        for r in rs:
            k = (tid, r["position"])
            if "title_embedding" in r:
                title_emb[k] = np.array(r["title_embedding"], dtype=np.float32)
            if "snippet_embedding" in r:
                snippet_emb[k] = np.array(r["snippet_embedding"], dtype=np.float32)
            title_text[k] = r.get("title", "") or ""
            snippet_text[k] = r.get("snippet", "") or ""

    query_emb_lookup, query_text_lookup = {}, {}
    for tid, v in query_data.items():
        if isinstance(v, dict) and "embedding" in v:
            query_emb_lookup[tid] = np.array(v["embedding"], dtype=np.float32)
            query_text_lookup[tid] = v.get("query", "")

    return {
        "lab_records": lab_records,
        "vp_by_key": vp_by_key,
        "regression_labels": regression_labels,
        "combined_emb": combined_emb,
        "title_emb": title_emb,
        "snippet_emb": snippet_emb,
        "title_text": title_text,
        "snippet_text": snippet_text,
        "query_emb_lookup": query_emb_lookup,
        "query_text_lookup": query_text_lookup,
    }


def build_full_serp(data):
    lab_records = data["lab_records"]
    regression_labels = data["regression_labels"]
    vp_by_key = data["vp_by_key"]

    click_pos_by_trial = {}
    m4_by_key = {}
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        if r.get("was_clicked"):
            click_pos_by_trial[r["trial_id"]] = r["position"]
        m4_by_key[key] = {
            "m4": [float(r.get(f)) if r.get(f) is not None else np.nan
                   for f in M4_FEATURES],
            "regression": bool(regression_labels[i]),
        }

    full_serp = {}
    for tid, click_pos in click_pos_by_trial.items():
        q_emb = data["query_emb_lookup"].get(tid)
        q_text = data["query_text_lookup"].get(tid, "")
        if q_emb is None or not q_text:
            continue
        q_tokens = tokenize(q_text)

        records = []
        ok = True
        for pos in range(10):
            key = (tid, pos)
            t_emb = data["title_emb"].get(key)
            s_emb = data["snippet_emb"].get(key)
            c_emb = data["combined_emb"].get(key)
            if c_emb is None and t_emb is None and s_emb is None:
                ok = False
                break
            t_txt = data["title_text"].get(key, "")
            s_txt = data["snippet_text"].get(key, "")

            # Text features
            r_tokens = tokenize((t_txt or "") + " " + (s_txt or ""))
            if not q_tokens:
                lex, avg_tf_ = 0.0, 0.0
            else:
                counter = {}
                for tok in r_tokens:
                    counter[tok] = counter.get(tok, 0) + 1
                matches = [tok for tok in q_tokens if tok in counter]
                lex = len(matches) / len(q_tokens)
                avg_tf_ = float(np.mean([counter.get(tok, 0) for tok in q_tokens]))
            text_feats = [lex, avg_tf_,
                          cos_sim(q_emb, t_emb),
                          cos_sim(q_emb, s_emb),
                          cos_sim(q_emb, c_emb)]

            m4_row = m4_by_key.get(key)
            m4_feats = list(m4_row["m4"]) if m4_row else [np.nan] * 9
            approached = bool(m4_row) and not np.isnan(m4_feats[0]) and m4_feats[0] < 100
            clicked = (pos == click_pos)
            deferred = bool(m4_row) and m4_row["regression"]

            vp_row = vp_by_key.get(key)
            if vp_row is None:
                vp_feats = [np.nan] * len(VP_FEATURES_MINIMAL)
            else:
                vp_feats = [float(vp_row.get(f, 0.0)) for f in VP_FEATURES_MINIMAL]

            # Label schemes
            # 3-grade (NB26 current)
            if clicked:
                g3 = 2
                eligible_3g = True
            elif approached and deferred:
                g3 = 1
                eligible_3g = True
            else:
                # below-click not-approached → excluded
                if not approached and pos > click_pos:
                    g3 = None
                    eligible_3g = False
                else:
                    g3 = 0
                    eligible_3g = True
            # 2-grade (Peter's ablation: drop all not-approached)
            if clicked:
                g2 = 2
                eligible_2g = True
            elif approached and deferred:
                g2 = 1
                eligible_2g = True
            elif approached and not deferred:
                g2 = 0
                eligible_2g = True
            else:
                g2 = None
                eligible_2g = False

            records.append({
                "position": pos,
                "text_feats": text_feats,
                "m4_feats": m4_feats,
                "vp_feats": vp_feats,
                "approached_flag": int(approached),
                "clicked": clicked,
                "g3": g3,
                "g3_eligible": eligible_3g,
                "g2": g2,
                "g2_eligible": eligible_2g,
                "binary": 1 if clicked else 0,
                "participant": tid.split("-")[0],
            })
        if not ok or len(records) != 10:
            continue
        if not any(r["clicked"] for r in records):
            continue
        full_serp[tid] = records
    print(f"[build] full-SERP trials: {len(full_serp):,}")
    return full_serp


def mrr_from_scores(records, scores):
    order = np.argsort(-np.asarray(scores), kind="stable")
    for rank, idx in enumerate(order, 1):
        if records[idx]["clicked"]:
            return 1.0 / rank
    return 0.0


def ndcg_from_scores(records, scores, k=10):
    order = np.argsort(-np.asarray(scores), kind="stable")
    gains = np.array([2.0 if records[idx]["clicked"] else 0.0 for idx in order[:k]])
    discounts = 1.0 / np.log2(np.arange(len(gains)) + 2)
    dcg = float(np.sum(gains * discounts))
    # Ideal: click at rank 1 with gain 2
    idcg = 2.0 / np.log2(2)  # = 2.0
    return dcg / idcg if idcg > 0 else 0.0


def mrr_original_full(records):
    for rank, r in enumerate(records, 1):
        if r["clicked"]:
            return 1.0 / rank
    return 0.0


def ndcg_original_full(records, k=10):
    gains = np.array([2.0 if r["clicked"] else 0.0 for r in records[:k]])
    discounts = 1.0 / np.log2(np.arange(len(gains)) + 2)
    dcg = float(np.sum(gains * discounts))
    idcg = 2.0
    return dcg / idcg


def features_for(records, feature_mode):
    arr = []
    for r in records:
        base = list(r["text_feats"])
        if feature_mode == "text":
            arr.append(base)
        elif feature_mode == "text_m4":
            arr.append(base + [r["approached_flag"]] + list(r["m4_feats"]))
        elif feature_mode == "text_vp":
            arr.append(base + list(r["vp_feats"]))
        elif feature_mode == "text_m4_vp":
            arr.append(base + [r["approached_flag"]] + list(r["m4_feats"]) + list(r["vp_feats"]))
        else:
            raise ValueError(feature_mode)
    return np.asarray(arr, dtype=float)


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

        if ranker_kind == "lgbm_binary":
            # Binary ranker: collapse graded labels to {0, 1} where 1 = clicked.
            y_bin = (y_train >= 2).astype(int)
            model = LGBMRanker(objective="lambdarank", label_gain=[0, 1],
                               n_estimators=200, num_leaves=31, learning_rate=0.05,
                               min_child_samples=10, random_state=seed, verbose=-1)
            model.fit(X_train, y_bin, group=groups_arr)
            sf = lambda X: model.predict(X)
        elif ranker_kind == "lgbm_graded":
            model = LGBMRanker(objective="lambdarank", label_gain=[0, 1, 2],
                               n_estimators=200, num_leaves=31, learning_rate=0.05,
                               min_child_samples=10, random_state=seed, verbose=-1)
            model.fit(X_train, y_train.astype(int), group=groups_arr)
            sf = lambda X: model.predict(X)
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


def paired_wilcoxon(res_a, res_b, metric="mrr", alternative="greater"):
    a_per = res_a[f"{metric}_per_p"]
    b_per = res_b[f"{metric}_per_p"]
    pids = sorted(set(a_per.keys()) & set(b_per.keys()))
    a = np.array([a_per[p] for p in pids])
    b = np.array([b_per[p] for p in pids])
    delta = a - b
    try:
        w = wilcoxon(a, b, alternative=alternative)
        W, p = float(w.statistic), float(w.pvalue)
    except Exception:
        W, p = float("nan"), float("nan")
    return {
        "delta_mean": float(delta.mean()),
        "delta_sd": float(delta.std(ddof=1)) if len(delta) > 1 else 0.0,
        "a_ge_b": int((a >= b).sum()),
        "n": len(pids),
        "W": W,
        "p": p,
    }


def main():
    data = load_all()
    full_serp = build_full_serp(data)

    # Label-eligibility audit
    def count(eligibility_key, label_key):
        g2_counts = defaultdict(int)
        for recs in full_serp.values():
            for r in recs:
                if r[eligibility_key] and r[label_key] is not None:
                    g2_counts[r[label_key]] += 1
        return dict(sorted(g2_counts.items()))

    print("\n-- Label distributions --")
    print(f"3-grade eligible counts: {count('g3_eligible', 'g3')}")
    print(f"2-grade eligible counts: {count('g2_eligible', 'g2')}")

    # Baseline
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
    print(f"\n[K6  — Google baseline] MRR = {orig_res['concat_mrr']:.4f}  NDCG@10 = {orig_res['concat_ndcg']:.4f}")

    # Run matrix
    rungs = [
        ("R1_text",        "text"),
        ("R2a_text_M4",    "text_m4"),
        ("R2b_text_VP",    "text_vp"),
        ("R3_text_M4_VP",  "text_m4_vp"),
    ]
    label_modes = [
        ("3grade", "g3", "g3_eligible"),
        ("2grade", "g2", "g2_eligible"),
    ]

    all_results = {}
    for rung_tag, fmode in rungs:
        for label_tag, label_key, elig_key in label_modes:
            for ranker in ("lgbm_binary", "lgbm_graded"):
                key = f"{rung_tag}__{label_tag}__{ranker}"
                print(f"\n[run] {key}")
                all_results[key] = seed_avg(full_serp, label_key, elig_key, fmode, ranker)
                print(f"       MRR = {all_results[key]['concat_mrr']:.4f}   "
                      f"NDCG@10 = {all_results[key]['concat_ndcg']:.4f}")

    # Report
    print("\n" + "=" * 76)
    print("Summary table — MRR (NDCG@10 in parens)")
    print("=" * 76)
    print(f"{'rung':20s} | {'3g_bin':>16s} | {'3g_grad':>16s} | {'2g_bin':>16s} | {'2g_grad':>16s}")
    print("-" * 100)
    for rung_tag, _ in rungs:
        row = [f"{rung_tag:20s}"]
        for label_tag, _, _ in label_modes:
            for ranker in ("lgbm_binary", "lgbm_graded"):
                key = f"{rung_tag}__{label_tag}__{ranker}"
                r = all_results[key]
                row.append(f"{r['concat_mrr']:.4f} ({r['concat_ndcg']:.4f})")
        print(" | ".join(row))

    # Paired graded-vs-binary at each rung × label
    print("\n-- Paired graded − binary (Wilcoxon, one-sided) --")
    paired = {}
    for rung_tag, _ in rungs:
        for label_tag, _, _ in label_modes:
            a = all_results[f"{rung_tag}__{label_tag}__lgbm_graded"]
            b = all_results[f"{rung_tag}__{label_tag}__lgbm_binary"]
            r_mrr = paired_wilcoxon(a, b, "mrr")
            r_ndcg = paired_wilcoxon(a, b, "ndcg")
            tag = f"{rung_tag}__{label_tag}"
            paired[f"{tag}__graded_minus_binary__mrr"] = r_mrr
            paired[f"{tag}__graded_minus_binary__ndcg"] = r_ndcg
            print(f"  {tag:30s}  MRR Δ = {r_mrr['delta_mean']:+.4f} "
                  f"(p = {r_mrr['p']:.4f}, {r_mrr['a_ge_b']}/{r_mrr['n']})   "
                  f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")

    # Rung 2b and Rung 3 vs Google (graded only, 3-grade)
    print("\n-- Rung 2b, Rung 3 vs Google baseline (3-grade graded) --")
    def vs_baseline(a, tag):
        r_mrr = paired_wilcoxon(a, orig_res, "mrr")
        r_ndcg = paired_wilcoxon(a, orig_res, "ndcg")
        paired[f"{tag}_vs_google__mrr"] = r_mrr
        paired[f"{tag}_vs_google__ndcg"] = r_ndcg
        print(f"  {tag:30s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")
    vs_baseline(all_results["R2b_text_VP__3grade__lgbm_graded"], "R2b_3g_graded")
    vs_baseline(all_results["R3_text_M4_VP__3grade__lgbm_graded"], "R3_3g_graded")
    # 2-grade vs Google
    vs_baseline(all_results["R2a_text_M4__2grade__lgbm_graded"], "R2a_2g_graded")
    vs_baseline(all_results["R2b_text_VP__2grade__lgbm_graded"], "R2b_2g_graded")
    vs_baseline(all_results["R3_text_M4_VP__2grade__lgbm_graded"], "R3_2g_graded")

    # Rung additions (feature-add isolated, graded, 3-grade)
    print("\n-- Feature-add isolated (3-grade graded): ΔΔ vs Rung 1 or Rung 2a --")
    def feat_add(a_key, b_key, tag):
        r_mrr = paired_wilcoxon(all_results[a_key], all_results[b_key], "mrr")
        r_ndcg = paired_wilcoxon(all_results[a_key], all_results[b_key], "ndcg")
        paired[f"{tag}__mrr"] = r_mrr
        paired[f"{tag}__ndcg"] = r_ndcg
        print(f"  {tag:35s}  MRR Δ = {r_mrr['delta_mean']:+.4f} (p = {r_mrr['p']:.4f})   "
              f"NDCG Δ = {r_ndcg['delta_mean']:+.4f} (p = {r_ndcg['p']:.4f})")
    feat_add("R2b_text_VP__3grade__lgbm_graded", "R1_text__3grade__lgbm_graded",
             "R2b_vs_R1__vp_add")
    feat_add("R3_text_M4_VP__3grade__lgbm_graded", "R2a_text_M4__3grade__lgbm_graded",
             "R3_vs_R2a__vp_on_top_of_m4")
    feat_add("R3_text_M4_VP__3grade__lgbm_graded", "R2b_text_VP__3grade__lgbm_graded",
             "R3_vs_R2b__m4_on_top_of_vp")

    # Save
    summary = {
        "label_counts": {
            "3grade": count("g3_eligible", "g3"),
            "2grade": count("g2_eligible", "g2"),
        },
        "baseline_google": {
            "mrr": orig_res["concat_mrr"],
            "ndcg": orig_res["concat_ndcg"],
        },
        "rungs": {
            key: {
                "mrr": v["concat_mrr"],
                "ndcg": v["concat_ndcg"],
                "mrr_per_p": v["mrr_per_p"],
                "ndcg_per_p": v["ndcg_per_p"],
            }
            for key, v in all_results.items()
        },
        "paired_comparisons": paired,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[out] {(OUT_DIR / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
