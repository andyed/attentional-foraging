"""Peter's sampling-rate curve: deferred task vs click task, plus the
scroll+click-only floor.

Reads rate_curve_records.json. For every condition, runs the identical LOSO
protocol on the identical rows and reports both tasks side by side, because the
question is not "does the cursor survive thinning" but "does the DEFERRED task
survive thinning the way the CLICK task does" -- which is what §6 assumes when
it carries the click-task rate result over to deferred-class deployment.

Rows are fixed across conditions: only AOIs that produce features in EVERY
condition are used, so the curve is a within-row comparison and cannot move
because a sparse condition dropped different rows.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# RETIRED 2026-09-13. DO NOT RUN. DO NOT CITE ITS NUMBERS.
#
# Built on the lineage retired from the paper on 2026-09-06: features from
# compute_cursor_approach_features.py / m4_nb21_hybrid_rerun.py (whose
# identically-named fields are gaze-cursor distances over fixation-selected
# rows) and labels from compute_regression_labels.py. Its outputs look
# canonical and are not.
#
# Canonical replacement: scripts/rate_curve_canonical.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/rate_curve_canonical.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")


import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "output" / "visit_decomposition"
PROX = 100.0


def loso(X, y, g, permute=False, rng=None):
    if permute:
        y = y.copy()
        for p in np.unique(g):
            m = g == p
            y[m] = rng.permutation(y[m])
    if len(np.unique(y)) < 2:
        return None
    oof = np.full(len(y), np.nan)
    folds = []
    for p in np.unique(g):
        te = g == p; tr = ~te
        if len(np.unique(y[tr])) < 2 or te.sum() == 0:
            continue
        sc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=2000, class_weight="balanced")
        clf.fit(sc.transform(X[tr]), y[tr])
        pr = clf.predict_proba(sc.transform(X[te]))[:, 1]
        oof[te] = pr
        if len(np.unique(y[te])) == 2:
            folds.append(roc_auc_score(y[te], pr))
    ok = ~np.isnan(oof)
    if ok.sum() == 0 or len(np.unique(y[ok])) < 2:
        return None
    return {"auc": float(roc_auc_score(y[ok], oof[ok])),
            "fold_mean": float(np.mean(folds)), "fold_sd": float(np.std(folds)),
            "n_folds": len(folds), "n": int(ok.sum())}


def main():
    recs = json.load(open(OUT / "rate_curve_records.json"))
    prov = json.load(open(OUT / "rate_curve_provenance.json"))
    conds = prov["conditions"]
    print(f"loaded {len(recs):,} records over {prov['n_trials']:,} trials")
    print("\npositional event mix (what the paper's thinner does NOT touch):")
    for k, v in sorted(prov["positional_event_share"].items(), key=lambda kv: -kv[1]):
        flag = "" if k == "mousemove" else "   <- passes through untouched"
        print(f"   {k:11s} {v*100:5.1f}%{flag}")

    # Rows present in every condition AND with scroll features.
    complete = [r for r in recs
                if all(c in r["cond"] for c in conds) and r.get("scroll")]
    print(f"\nrows complete across all {len(conds)} conditions: {len(complete):,}")

    # The approach gate uses the NATIVE stream so the pool is fixed; a thinned
    # stream must not be allowed to redefine which results count as approached.
    native = "mousemove_only@native"
    pool = [r for r in complete if r["cond"][native][0] < PROX]
    print(f"approached at native rate (min_dist < 100 px): {len(pool):,}")

    g = np.array([r["participant"] for r in pool])
    y_def = np.array([bool(r["deferred"]) for r in pool], dtype=int)
    y_clk = np.array([bool(r["was_clicked"]) for r in pool], dtype=int)
    print(f"deferred base rate {y_def.mean():.3f} | click base rate {y_clk.mean():.3f}")

    results = {"conditions": {}, "event_mix": prov["positional_event_share"]}
    rng = np.random.default_rng(1)
    Xn = np.array([r["cond"][native] for r in pool])
    nulls = [loso(Xn, y_def, g, permute=True, rng=rng) for _ in range(100)]
    nv = np.array([x["auc"] for x in nulls if x])
    null = {"mean": float(nv.mean()), "p95": float(np.percentile(nv, 95)),
            "p99": float(np.percentile(nv, 99))}
    results["null_deferred"] = null

    hdr = f"{'condition':>28s} {'samples/trial':>14s} {'DEFERRED':>10s} {'CLICK':>10s}"
    print(f"\n{'='*66}\n{hdr}\n{'='*66}")
    for c in conds:
        X = np.array([r["cond"][c] for r in pool])
        ns = np.median([r["n_samples"][c] for r in pool])
        rd = loso(X, y_def, g)
        rc = loso(X, y_clk, g)
        results["conditions"][c] = {"deferred": rd, "click": rc,
                                    "median_samples_per_trial": float(ns)}
        mark = " *" if rd and rd["auc"] <= null["p99"] else ""
        da = f"{rd['auc']:10.3f}" if rd else f"{'--':>10s}"
        ca = f"{rc['auc']:10.3f}" if rc else f"{'--':>10s}"
        print(f"{c:>28s} {ns:14.0f} {da} {ca}{mark}")

    Xs = np.array([r["scroll"] for r in pool])
    rds = loso(Xs, y_def, g)
    rcs = loso(Xs, y_clk, g)
    results["scroll_only"] = {"deferred": rds, "click": rcs}
    mark = " *" if rds and rds["auc"] <= null["p99"] else ""
    da = f"{rds['auc']:10.3f}" if rds else f"{'--':>10s}"
    ca = f"{rcs['auc']:10.3f}" if rcs else f"{'--':>10s}"
    print(f"{'scroll+click only':>28s} {'—':>14s} {da} {ca}{mark}")
    print(f"{'':>28s} {'':>14s} {'':>10s}")
    print(f"  permutation null (deferred): mean {null['mean']:.3f}  "
          f"p95 {null['p95']:.3f}  p99 {null['p99']:.3f}   (* = at or inside null)")

    # Which scroll feature carries it
    names = prov["scroll_feature_order"]
    print("\n  scroll-only, single features (deferred):")
    for j, nm in enumerate(names):
        r = loso(Xs[:, [j]], y_def, g)
        if r:
            print(f"     {nm:22s} {r['auc']:.3f}")
            results.setdefault("scroll_single", {})[nm] = r["auc"]

    json.dump(results, open(OUT / "rate_curve_results.json", "w"), indent=1)
    print(f"\nwrote {OUT/'rate_curve_results.json'}")


if __name__ == "__main__":
    main()
