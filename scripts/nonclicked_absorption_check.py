"""Leakage-immune half of the story: non-clicked-AOI checks.

Concern: in a forced-choice setting, cursor proximity/dwell to a
result is close to a direct proxy for clicking it, and the same worry
applies to graded-label ranking as label leakage into the test set. Both
operate through the clicked AOI — the cursor must mechanically travel
there. This script re-derives the graded-label results restricted to the
population where mechanical travel-to-target CANNOT operate: non-clicked
AOIs.

Two parts:

(A) M5 deferred vs evaluated-rejected discrimination [LAB, organic].
    Population: approached (min_dist < 100 px) AND not clicked — the
    clicked AOI is excluded by construction, so travel-to-target leakage
    cannot supply the signal. Conditions: buf=0 ms, buf=500 ms (published
    terminal buffers), and the full approach-truncation stream from
    scripts/approach_truncation_ablation.py. Within each condition, three
    feature sets: position alone, M4-7 (7 canonical cursor features), and
    M4-7 + position. The (M4-7 + position) vs M4-7 paired contrast is the
    position-absorption statistic recomputed in the leakage-immune
    population.

(B) LambdaMART four-class graded LTR [LAB, typed].
    Reruns the §4.6 protocol (scripts/ltr_typed_four_distinct_grades.py,
    gaze label source) on the approach-truncated typed features and
    compares the graded-vs-binary MRR@10 delta against the published
    buf=0 and buf=500 runs. The May 2026 REVISION-PLAN hypothesis: the
    graded-label lift over the binary-click baseline WIDENS under
    leakage-corrected features because the binary baseline loses its
    mechanical lift while the graded model (which must separate deferred
    from not-approached, both with cursor ending elsewhere) never had it.

Protocols are mirrored, not modified, from m5_cursor_only_taxonomy.py
and ltr_typed_four_distinct_grades.py. New files only.

Run (serial; LGBM fits are the slow part, ~5-10 min):
    .venv/bin/python scripts/nonclicked_absorption_check.py
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np
from lightgbm import LGBMRanker
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

# Reuse the paired-stat convention of the truncation ablation (itself a
# mirror of scripts/paper_stat_tests.py).
from approach_truncation_ablation import paired_tests  # noqa: E402

# Protocol constants come from the canonical producer, not a copy. They were
# duplicated here because importing that module pulled in `muriel.provenance`
# through a skills path that stopped being importable on 2026-08-07; that is
# fixed (muriel is installed, and the path hack points at the package root), so
# the copy is retired. Copies of protocol constants do not announce their drift
# — they produce a different number in a paper.
from ltr_typed_four_distinct_grades import (  # noqa: E402
    APPROACH_THRESHOLD_PX, M3_NO_POS, M4_CANONICAL,
)


def contiguous_group_sizes(tid_arr):
    sizes, last = [], None
    for t in tid_arr:
        if t != last:
            sizes.append(1)
            last = t
        else:
            sizes[-1] += 1
    return sizes


def per_trial_metrics(scores, y_click, tid_arr, k=10):
    from collections import defaultdict
    from sklearn.metrics import ndcg_score
    by_trial = defaultdict(list)
    for i, t in enumerate(tid_arr):
        by_trial[t].append(i)
    ndcgs, mrrs, tids_kept = [], [], []
    for t in sorted(by_trial.keys()):
        idxs = by_trial[t]
        if len(idxs) < 2 or y_click[idxs].sum() == 0:
            continue
        s = scores[idxs]
        gold = y_click[idxs].astype(float)
        ndcgs.append(ndcg_score([gold], [s], k=min(k, len(idxs))))
        order = np.argsort(-s, kind='stable')
        ranked = gold[order]
        mrr = 0.0
        for r, v in enumerate(ranked, start=1):
            if r > k:
                break
            if v > 0:
                mrr = 1.0 / r
                break
        mrrs.append(mrr)
        tids_kept.append(str(t))
    return np.array(ndcgs), np.array(mrrs), tids_kept


def baseline_serp_scores(records):
    return np.array([-int(r['position']) for r in records], dtype=float)


def assign_four_distinct_grades(records, regression_labels):
    from collections import defaultdict
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is None:
            continue
        clicked_pos_by_trial[r['trial_id']] = int(cp)
    labels = np.zeros(len(records), dtype=int)
    include = np.ones(len(records), dtype=bool)
    cls_counts = defaultdict(int)
    for i, (r, regr) in enumerate(zip(records, regression_labels)):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        pos = int(r['position'])
        cp = clicked_pos_by_trial.get(r['trial_id'])
        if clicked:
            labels[i] = 3
            cls_counts['CLICKED'] += 1
        elif approached and bool(regr):
            labels[i] = 2
            cls_counts['DEFERRED'] += 1
        elif approached:
            labels[i] = 1
            cls_counts['EVAL_REJECTED'] += 1
        else:
            if cp is not None and pos > cp:
                include[i] = False
                cls_counts['NotApprBelow_EXCLUDED'] += 1
            else:
                labels[i] = 0
                cls_counts['NotApprAbove'] += 1
    return labels, include, dict(cls_counts)


def assign_three_grade_collapse(records, regression_labels):
    clicked_pos_by_trial = {}
    for r in records:
        cp = r.get('click_pos')
        if cp is None:
            continue
        clicked_pos_by_trial[r['trial_id']] = int(cp)
    labels = np.zeros(len(records), dtype=int)
    include = np.ones(len(records), dtype=bool)
    for i, (r, regr) in enumerate(zip(records, regression_labels)):
        clicked = bool(r.get('was_clicked', False))
        approached = float(r.get('min_dist', 1e9)) < APPROACH_THRESHOLD_PX
        pos = int(r['position'])
        cp = clicked_pos_by_trial.get(r['trial_id'])
        if clicked:
            labels[i] = 2
        elif approached and bool(regr):
            labels[i] = 1
        elif approached:
            labels[i] = 0
        else:
            if cp is not None and pos > cp:
                include[i] = False
            else:
                labels[i] = 0
    return labels, include

DATA = ROOT / "AdSERP/data"
ABL = ROOT / "scripts/output/ablations"
OUT_PATH = ABL / "nonclicked_absorption_check.json"

# ── Part A inputs (organic attribution, matching m5_cursor_only_taxonomy) ──
ORGANIC_CANONICAL = DATA / "cursor-approach-features-organic.json"
ORGANIC_CONDITIONS = {
    "buf0": ORGANIC_CANONICAL,
    "buf500": DATA / "cursor-approach-features-organic-buf500.json",
    "approach_truncated": ABL / "cursor-approach-features-organic-approach-truncated.json",
}
ORGANIC_REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json"

# ── Part B inputs (typed attribution, matching ltr_typed_four_distinct_grades)
TYPED_CANONICAL = DATA / "cursor-approach-features-typed.json"
TYPED_TRUNCATED = ABL / "cursor-approach-features-typed-approach-truncated.json"
TYPED_REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json"
PUBLISHED_LTR = {
    "buf0": ROOT / "scripts/output/ltr_typed_four_distinct_grades/summary.json",
    "buf500": ROOT / "scripts/output/ltr_typed_four_distinct_grades/summary_gaze_buf500.json",
}

M4_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
M4_9 = M4_7 + ["final_dist", "retreat_dist"]


def label_map_from_cache(canonical_path, cache_path):
    canonical = json.load(open(canonical_path))
    cache = json.load(open(cache_path))
    assert len(canonical) == len(cache), (
        f"cache misaligned: {len(canonical)} records vs {len(cache)} labels")
    return {(r["trial_id"], r["position"]): bool(cache[i])
            for i, r in enumerate(canonical)}


def loso_auc_per_part(X, y, groups):
    """GroupKFold LOSO (m5 protocol) -> (pooled_auc, per_part dict)."""
    from sklearn.metrics import roc_auc_score
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    gkf = GroupKFold(n_splits=len(set(groups)))
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=gkf,
                              method="predict_proba", n_jobs=4)[:, 1]
    pooled = float(roc_auc_score(y, proba))
    per_part = {}
    for g in sorted(set(groups)):
        m = groups == g
        if len(set(y[m])) == 2:
            per_part[str(g)] = float(roc_auc_score(y[m], proba[m]))
    return pooled, per_part


def part_a():
    print("=" * 72)
    print("Part A — M5 deferred vs eval-rejected on NON-CLICKED AOIs [organic]")
    print("=" * 72)
    label_by_key = label_map_from_cache(ORGANIC_CANONICAL, ORGANIC_REG_CACHE)

    results = {}
    per_part_store = {}
    for cond, path in ORGANIC_CONDITIONS.items():
        raw = json.load(open(path))
        labels = np.array([label_by_key.get((r["trial_id"], r["position"]), False)
                           for r in raw], dtype=bool)
        min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
        was_clicked = np.array([r["was_clicked"] for r in raw], dtype=bool)
        subset = (min_dist < 100) & ~was_clicked
        y = labels[subset].astype(int)
        groups = np.array([r["trial_id"].split("-")[0] for r in raw])[subset]
        n_def, n_rej = int(y.sum()), int((1 - y).sum())
        print(f"\n[{cond}] approached non-clicked n={int(subset.sum()):,} "
              f"(deferred {n_def:,} / eval-rej {n_rej:,}), "
              f"participants={len(set(groups))}")

        def X_of(features, with_pos):
            cols = [np.array([[float(r.get(f, 0.0) or 0.0) for f in features]
                              for r in raw])[subset]] if features else []
            if with_pos:
                pos = np.array([r["position"] for r in raw], dtype=float)[subset]
                cols.append(pos.reshape(-1, 1))
            return np.column_stack(cols)

        cond_res = {"n_subset": int(subset.sum()),
                    "n_deferred": n_def, "n_eval_rejected": n_rej,
                    "n_participants": len(set(groups))}
        model_specs = {
            "position_alone": ([], True),
            "M4-7": (M4_7, False),
            "M4-7_plus_position": (M4_7, True),
        }
        if cond == "buf0":
            model_specs["M4-9_legacy"] = (M4_9, False)
        for name, (feats, with_pos) in model_specs.items():
            auc, per_part = loso_auc_per_part(X_of(feats, with_pos), y, groups)
            vals = np.array(list(per_part.values()))
            cond_res[name] = {
                "loso_auc": auc,
                "per_part_median": float(np.median(vals)),
                "per_part_iqr": [float(np.percentile(vals, 25)),
                                 float(np.percentile(vals, 75))],
                "n_parts_scored": len(vals),
            }
            per_part_store[(cond, name)] = per_part
            print(f"  {name:22s} LOSO AUC = {auc:.4f} "
                  f"(per-part median {np.median(vals):.3f}, n={len(vals)})")
        results[cond] = cond_res

    # Paired contrasts within condition (align by participant)
    paired = {}
    for cond in ORGANIC_CONDITIONS:
        for a_name, b_name, key in [
            ("M4-7_plus_position", "M4-7", f"{cond}|absorption_pos_add"),
            ("M4-7", "position_alone", f"{cond}|M4-7_vs_position"),
        ]:
            pa, pb = per_part_store[(cond, a_name)], per_part_store[(cond, b_name)]
            common = sorted(set(pa) & set(pb))
            paired[key] = paired_tests(
                [pa[p] for p in common], [pb[p] for p in common],
                f"{a_name} ({cond})", f"{b_name} ({cond})")
            v = paired[key]
            print(f"  {key}: dAUC={v['mean_delta_auc']:+.4f} "
                  f"[{v['delta_ci_95_lo']:+.4f}, {v['delta_ci_95_hi']:+.4f}] "
                  f"d_z={v['cohens_d_z']:.2f} wilcoxon p={v['wilcoxon_p']:.2e}")
    return {"conditions": results, "paired_stats": paired}


# ── Part B — LambdaMART on truncated typed features ───────────────────────

def loso_lambdamart(X_full, X_kept, label_train, pid_all, pid_kept, tid_kept):
    pooled = np.zeros(len(X_full), dtype=float)
    parts = np.unique(pid_all)
    for i, p in enumerate(parts):
        train_mask = (pid_kept != p)
        test_mask = (pid_all == p)
        tid_tr = tid_kept[train_mask]
        sizes = contiguous_group_sizes(tid_tr)
        ranker = LGBMRanker(
            objective="lambdarank", metric="ndcg", eval_at=[10],
            n_estimators=200, learning_rate=0.05, num_leaves=31,
            min_data_in_leaf=20, verbose=-1,
        )
        ranker.fit(X_kept[train_mask], label_train[train_mask], group=sizes)
        pooled[test_mask] = ranker.predict(X_full[test_mask])
        if (i + 1) % 10 == 0:
            print(f"    fold {i + 1}/{len(parts)}", file=sys.stderr)
    return pooled


def loso_lr(X_full, X_kept, y_train, pid_all, pid_kept):
    pooled = np.zeros(len(X_full), dtype=float)
    for p in np.unique(pid_all):
        tr = (pid_kept != p)
        te = (pid_all == p)
        m = Pipeline([
            ("s", StandardScaler()),
            ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
        ])
        m.fit(X_kept[tr], y_train[tr])
        pooled[te] = m.predict_proba(X_full[te])[:, 1]
    return pooled


def part_b():
    print("\n" + "=" * 72)
    print("Part B — §4.6 LambdaMART graded LTR on approach-truncated features [typed]")
    print("=" * 72)
    label_by_key = label_map_from_cache(TYPED_CANONICAL, TYPED_REG_CACHE)

    records_raw = json.load(open(TYPED_TRUNCATED))
    regression_raw = [label_by_key.get((r["trial_id"], r["position"]), False)
                      for r in records_raw]
    order = np.argsort(np.array([r["trial_id"] for r in records_raw]), kind="stable")
    records = [records_raw[i] for i in order]
    regression_labels = [regression_raw[i] for i in order]

    tid_all = np.array([r["trial_id"] for r in records])
    pid_all = np.array([r["trial_id"].split("-")[0] for r in records])
    y_click_all = np.array([int(bool(r.get("was_clicked", False))) for r in records])
    print(f"  records: {len(records):,}  trials: {len(np.unique(tid_all)):,}  "
          f"participants: {len(np.unique(pid_all))}")

    labels_4g, include_4g, cls_counts = assign_four_distinct_grades(records, regression_labels)
    labels_3g, include_3g = assign_three_grade_collapse(records, regression_labels)
    assert (include_4g == include_3g).all()
    print(f"  class distribution: {cls_counts}")

    X_full = np.array([[float(r.get(f, 0.0) or 0.0) for f in M3_NO_POS] for r in records])
    X_kept = X_full[include_4g]
    tid_kept = tid_all[include_4g]
    pid_kept = pid_all[include_4g]

    fits = {
        "Original SERP position (no ML)": baseline_serp_scores(records),
        "LR pointwise (binary click)": loso_lr(
            X_full, X_kept, y_click_all[include_4g], pid_all, pid_kept),
        "LambdaMART (binary click)": loso_lambdamart(
            X_full, X_kept, y_click_all[include_4g], pid_all, pid_kept, tid_kept),
        "LambdaMART (3-grade collapse, 2/1/0/0)": loso_lambdamart(
            X_full, X_kept, labels_3g[include_4g], pid_all, pid_kept, tid_kept),
        "LambdaMART (4 distinct grades, 3/2/1/0)": loso_lambdamart(
            X_full, X_kept, labels_4g[include_4g], pid_all, pid_kept, tid_kept),
    }

    rows = {}
    per_trial = {}
    for name, s in fits.items():
        ndcg, mrr, tids_kept = per_trial_metrics(s, y_click_all, tid_all, k=10)
        rows[name] = {"ndcg10": float(ndcg.mean()), "mrr10": float(mrr.mean()),
                      "n_trials": int(len(ndcg))}
        per_trial[name] = dict(zip(tids_kept, mrr.tolist()))
        print(f"  {name:44s} NDCG@10={ndcg.mean():.4f}  MRR@10={mrr.mean():.4f}  "
              f"n_trials={len(ndcg):,}")

    def paired_mrr(name_a, name_b, key):
        common = sorted(set(per_trial[name_a]) & set(per_trial[name_b]))
        return key, paired_tests(
            [per_trial[name_a][t] for t in common],
            [per_trial[name_b][t] for t in common],
            f"{name_a} (truncated)", f"{name_b} (truncated)")

    paired = dict([
        paired_mrr("LambdaMART (3-grade collapse, 2/1/0/0)",
                   "LambdaMART (binary click)", "3grade_vs_binary"),
        paired_mrr("LambdaMART (4 distinct grades, 3/2/1/0)",
                   "LambdaMART (binary click)", "4grade_vs_binary"),
    ])
    for k, v in paired.items():
        print(f"  {k}: dMRR={v['mean_delta_auc']:+.4f} "
              f"[{v['delta_ci_95_lo']:+.4f}, {v['delta_ci_95_hi']:+.4f}] "
              f"d_z={v['cohens_d_z']:.2f} wilcoxon p={v['wilcoxon_p']:.2e}")

    published = {}
    for cond, path in PUBLISHED_LTR.items():
        d = json.load(open(path))
        published[cond] = {
            "headlines": d.get("headlines", {}),
            "mrr10": {k: v["mrr10"] for k, v in d.get("metrics", {}).items()},
        }

    delta_3g = rows["LambdaMART (3-grade collapse, 2/1/0/0)"]["mrr10"] - \
        rows["LambdaMART (binary click)"]["mrr10"]
    delta_4g = rows["LambdaMART (4 distinct grades, 3/2/1/0)"]["mrr10"] - \
        rows["LambdaMART (binary click)"]["mrr10"]
    print(f"\n  HEADLINE dMRR@10 (3-grade - binary) truncated: {delta_3g:+.4f} "
          f"(published buf0 {published['buf0']['headlines'].get('delta_mrr10_3grade_minus_binary', float('nan')):+.4f}, "
          f"buf500 {published['buf500']['headlines'].get('delta_mrr10_3grade_minus_binary', float('nan')):+.4f})")
    print(f"  HEADLINE dMRR@10 (4-grade - binary) truncated: {delta_4g:+.4f}")

    return {
        "dataset": {"records": len(records),
                    "trials": int(len(np.unique(tid_all))),
                    "participants": int(len(np.unique(pid_all))),
                    "class_distribution": cls_counts,
                    "approach_threshold_px": APPROACH_THRESHOLD_PX},
        "mrr_ndcg": rows,
        "deltas": {"mrr10_3grade_minus_binary": delta_3g,
                   "mrr10_4grade_minus_binary": delta_4g},
        "paired_stats_per_trial_mrr": paired,
        "published_comparison": published,
    }


def main():
    out = {
        "experiment": "non-clicked-AOI absorption / graded-label leakage-immunity check",
        "generated_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "LAB",
        "rank_type": {"part_a": "organic", "part_b": "typed"},
        "part_a_m5_nonclicked": part_a(),
        "part_b_lambdamart_truncated": part_b(),
        "inputs": {
            "organic_conditions": {k: str(v) for k, v in ORGANIC_CONDITIONS.items()},
            "typed_truncated": str(TYPED_TRUNCATED),
            "label_caches": {"organic": str(ORGANIC_REG_CACHE),
                             "typed": str(TYPED_REG_CACHE)},
        },
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
