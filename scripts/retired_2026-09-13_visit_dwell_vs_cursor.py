"""Does the AdSERP dwell baseline survive the first-vs-subsequent-visit carve?

Companion analysis to scripts/visit_decomposition.py. Three jobs:

 1. VALIDATE. My `deferred` label must reproduce the shipped
    regression_labels_cache_typed_gapfill.json exactly. If it does not, nothing
    below is trustworthy and the script says so and stops.

 2. DECOMPOSE. total_dwell_ms = first_visit_dwell_ms + subsequent_dwell_ms.
    The `deferred` label is defined by the existence of the subsequent visit,
    so any discriminative power the dwell baseline draws from the second term
    is the label reading itself back.

 3. RE-QUOTE. LOSO AUC for deferred vs evaluated-rejected under
    total dwell / first-visit dwell / cursor features, with cursor features
    recomputed on the SAME typed_gapfill substrate in screenshot space, so the
    dwell and cursor sides share one AOI definition and one coordinate space.
    (The paper's M4 numbers come from m4_nb21_hybrid_rerun.py, which builds
    bands with result_band_tops on document-space mouse coordinates -- a
    different substrate AND a different space. Not comparable line-for-line;
    this script reports its own internally-consistent pair.)

Output: scripts/output/visit_decomposition/dwell_carve.json + console table.
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
# Canonical replacement: scripts/deferred_dwell_carve.py
# Canonical numbers:     scripts/output/deferred_dwell_carve/
# Why:                   the replacement reproduces the shipped §4.3
#                        deployable M4-7 (0.6911) as a hard gate before it
#                        computes anything.
# ─────────────────────────────────────────────────────────────────────────────
raise SystemExit(
    __doc__.strip().splitlines()[0] + "\n\n"
    "RETIRED 2026-09-13 — this script is built on the retired feature lineage.\n"
    "Use scripts/deferred_dwell_carve.py instead; numbers in\n"
    "scripts/output/deferred_dwell_carve/ are the canonical ones.\n")


import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
OUT = ROOT / "scripts" / "output" / "visit_decomposition"

from data_loader import (  # noqa: E402
    load_mouse_events, typed_gapfill_aoi_bands,
)

PROX = 100.0
MAX_DWELL_GAP_MS = 2000.0
MIN_VEL_DT_MS = 8.0
MAX_VEL = 10000.0

M4 = ["min_dist", "mean_dist", "dwell_in_proximity_ms",
      "mean_approach_velocity", "max_approach_velocity",
      "direction_changes", "frac_decreasing"]


def validate_labels(records):
    """Reproduce the shipped regression-label cache from my visit records."""
    feats_p = ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json"
    cache_p = OUT.parent / "approach_threshold_sensitivity/regression_labels_cache_typed_gapfill.json"
    if not (feats_p.exists() and cache_p.exists()):
        return {"status": "cache missing — skipped"}
    feats = json.load(open(feats_p))
    cache = json.load(open(cache_p))
    n = min(len(feats), len(cache))
    mine = {(r["trial_id"], r["position"]): r["deferred"] for r in records}
    agree = compared = missing = 0
    for rec, lab in zip(feats[:n], cache[:n]):
        k = (rec["trial_id"], rec["position"])
        if k not in mine:
            missing += 1
            continue
        compared += 1
        agree += int(bool(lab) == mine[k])
    return {"status": "compared", "n_cache": len(cache), "n_compared": compared,
            "n_missing_from_mine": missing,
            "agreement": (agree / compared) if compared else None}


def cursor_features(trial_id, positions):
    """d(t) = |y_cursor - y_AOI_centre| per position, typed_gapfill bands,
    screenshot space. Cursor-only: no gaze enters."""
    try:
        bands = typed_gapfill_aoi_bands(trial_id)
        allev, _scr, _clk = load_mouse_events(trial_id, space="screenshot")
    except Exception:
        return {}
    pos_ev = [(t, y) for (t, e, x, y) in allev
              if e in ("mousemove", "mouseover", "mouseout",
                       "mousedown", "mouseup", "click") and x > 0 and y > 0]
    if len(pos_ev) < 2 or not bands:
        return {}
    pos_ev.sort()
    ts = np.array([p[0] for p in pos_ev], dtype=float)
    ys = np.array([p[1] for p in pos_ev], dtype=float)
    out = {}
    for pos in positions:
        if pos >= len(bands):
            continue
        top, bot = bands[pos][0], bands[pos][1]
        dist = np.abs(ys - (top + bot) / 2.0)
        dts = np.diff(ts)
        ok = dts > 0
        dd = np.diff(dist)
        in_prox = dist < PROX
        dwell = float(dts[ok & in_prox[1:] & (dts < MAX_DWELL_GAP_MS)].sum())
        if ok.any():
            v = np.clip(-dd[ok] / np.maximum(dts[ok], MIN_VEL_DT_MS) * 1000.0,
                        -MAX_VEL, MAX_VEL)
            mv, xv = float(v.mean()), float(v.max())
            dc = int(np.sum(np.diff(np.sign(v)) != 0)) if len(v) > 1 else 0
            fd = float(np.mean(dd[ok] < 0))
        else:
            mv = xv = 0.0; dc = 0; fd = 0.0
        out[pos] = {
            "min_dist": float(dist.min()), "mean_dist": float(dist.mean()),
            "dwell_in_proximity_ms": dwell, "mean_approach_velocity": mv,
            "max_approach_velocity": xv, "direction_changes": dc,
            "frac_decreasing": fd,
        }
    return out


def loso(recs, feats, label="deferred", permute=False, rng=None):
    X = np.array([[float(r[f]) for f in feats] for r in recs])
    y = np.array([bool(r[label]) for r in recs], dtype=int)
    g = np.array([r["participant"] for r in recs])
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
    records = json.load(open(OUT / "records.json"))
    print(f"loaded {len(records):,} visit records")

    v = validate_labels(records)
    print(f"\nLABEL VALIDATION vs shipped cache: {json.dumps(v)}")
    if v.get("agreement") is not None and v["agreement"] < 0.999:
        print("  !! labels do not reproduce the shipped cache — stopping.")
        return

    # --- Decomposition descriptives -------------------------------------
    pool = [r for r in records if not r["was_clicked"]]
    dfr = [r for r in pool if r["deferred"]]
    rej = [r for r in pool if not r["deferred"]]
    print(f"\nNON-CLICK POOL n={len(pool):,}  deferred={len(dfr):,} "
          f"({100*len(dfr)/len(pool):.1f}%)  evaluated-rejected={len(rej):,}")
    print(f"{'':28s}{'deferred':>12s}{'rejected':>12s}")
    for k in ["total_dwell_ms", "first_visit_dwell_ms", "subsequent_dwell_ms",
              "n_visits", "n_fix_total", "n_fix_first_visit"]:
        a = np.median([r[k] for r in dfr]); b = np.median([r[k] for r in rej])
        print(f"  median {k:21s}{a:12.1f}{b:12.1f}")
    share = np.median([r["subsequent_dwell_ms"] / max(r["total_dwell_ms"], 1)
                       for r in dfr])
    print(f"\n  subsequent-visit share of total dwell, deferred items: {share:.2f}")

    # deferred vs plain revisit are not the same set
    both = sum(1 for r in pool if r["deferred"] and r["plain_revisit"])
    rev_only = sum(1 for r in pool if r["plain_revisit"] and not r["deferred"])
    def_only = sum(1 for r in pool if r["deferred"] and not r["plain_revisit"])
    print(f"  deferred & revisited {both:,} | revisited but NOT deferred "
          f"{rev_only:,} | deferred but not revisited {def_only:,}")
    gaps = [r["return_gap_ms"] for r in pool if r.get("return_gap_ms")]
    if gaps:
        print(f"  return gap ms: p25 {np.percentile(gaps,25):.0f}  "
              f"median {np.median(gaps):.0f}  p75 {np.percentile(gaps,75):.0f}")

    # --- Join cursor features on the SAME substrate ----------------------
    by_trial = defaultdict(list)
    for r in pool:
        by_trial[r["trial_id"]].append(r)
    joined = []
    for i, (tid, rs) in enumerate(by_trial.items(), 1):
        if i % 400 == 0:
            print(f"    cursor features {i}/{len(by_trial)}", flush=True)
        cf = cursor_features(tid, [r["position"] for r in rs])
        for r in rs:
            f = cf.get(r["position"])
            if f is None:
                continue
            rec = dict(r); rec.update(f)
            joined.append(rec)
    print(f"\n  joined cursor features on {len(joined):,} records "
          f"({len({r['trial_id'] for r in joined}):,} trials)")

    approached = [r for r in joined if r["min_dist"] < PROX]
    print(f"  approached (min_dist < 100 px): {len(approached):,}")

    models = {
        "dwell (total)":        ["total_dwell_ms"],
        "dwell (first visit)":  ["first_visit_dwell_ms"],
        "n_fix (first visit)":  ["n_fix_first_visit"],
        "mean_dist":            ["mean_dist"],
        "M4 (seven, cursor)":   M4,
        "M4 + first-visit dwell": M4 + ["first_visit_dwell_ms"],
    }
    results = {}
    print(f"\n{'='*70}\nDEFERRED vs EVALUATED-REJECTED — LOSO AUC (AdSERP)\n{'='*70}")
    for name, feats in models.items():
        r = loso(approached, feats)
        if r is None:
            continue
        results[name] = r
        print(f"  {name:24s} AUC {r['auc']:.3f}   per-fold "
              f"{r['fold_mean']:.3f} +- {r['fold_sd']:.3f} ({r['n_folds']} folds)")
    rng = np.random.default_rng(1)
    nulls = [loso(approached, M4, permute=True, rng=rng) for _ in range(100)]
    nv = np.array([x["auc"] for x in nulls if x])
    print(f"  {'label-perm null (M4)':24s} mean {nv.mean():.3f}  "
          f"p95 {np.percentile(nv,95):.3f}  p99 {np.percentile(nv,99):.3f}  (100 perms)")
    results["_null_M4"] = {"mean": float(nv.mean()),
                           "p95": float(np.percentile(nv, 95)),
                           "p99": float(np.percentile(nv, 99))}
    results["_validation"] = v
    results["_pool"] = {"n_approached": len(approached),
                        "n_noclick": len(pool),
                        "deferred_rate": float(len(dfr) / len(pool))}
    json.dump(results, open(OUT / "dwell_carve.json", "w"), indent=1)
    print(f"\nwrote {OUT/'dwell_carve.json'}")


if __name__ == "__main__":
    main()
