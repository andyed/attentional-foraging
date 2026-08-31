"""PAI-vs-binary-exposure validation — does PAI add information over
traditional gaze-point-in-AOI metrics?

Direct answer to Duchowski's 2026-08-17 ask ("The key to doing so would be
to somehow show that the PAI provides additional info over traditional
gaze-point-in-AOIs metrics"). Built on the control-ladder harness
(viewport_exposure_ablation.py): same record populations, same LOSO
protocol, same paired per-fold stats, same excision condition.

Design:
  - The grid's `total_dwell_ms` IS the traditional metric: each fixation
    binary-assigned to exactly one AOI band by page-y bisection
    (assign_fixation_to_position), durations summed per (trial, AOI).
  - PAI features per (trial, AOI): each fixation contributes soft mass to
    EVERY AOI via Duchowski's exact alpha from glias2poly_1920x1080.py /
    the delivered demo (approach-retreat/site/pai/):
        alpha = clip(1 - sqrt(OGD / max(CGD, 1)) * w_A, 0, 1)
        w_A   = (A_max / max(A, 1)) ** phi^3     (phi^3 ~= 0.236)
    OGD = exact distance to the AOI rectangle boundary (0 inside; the
    boundary form, per the demo's documented deviation from vertex
    distance), CGD = distance to the AOI centroid, A_max = largest AOI
    area on the page.
        pai_dwell_ms  = sum_f  d_f * alpha(f, A)          (total soft mass)
        pai_periph_ms = sum_{f: OGD>0} d_f * alpha(f, A)  (strictly-outside
                        mass only — the component traditional point-in-AOI
                        assignment CANNOT see, by construction)
    Sensitivity variant: the NB35 abstract-only form
        alpha35 = clip(1 - OGD / max(CGD, 1), 0, 1)
    (no area weight, no sqrt) -> pai35_dwell_ms / pai35_periph_ms, to show
    conclusions don't hinge on the functional form.
  - AOI geometry: organic_hybrid bands (build_hybrid_aois) extruded to the
    result column x-extent [162, 702] (data_loader._RESULT_COL_X_MIN/MAX),
    so `position` indexes match the grid records exactly. Limitation: the
    column rect is wider than the true snippet bbox; peripheral alphas are
    conservative in x (right-rail fixations read as peripheral, never
    interior). Same geometry family for both channels keeps the
    comparison clean.
  - Fixation cutoffs identical to the extractor / viewport ablation:
      buf500   — fixations with t < t_click - 500 ms (no click: full span)
      excision — t < t_onset, loaded VERBATIM from
                 approach_truncation_trial_stats.json (not re-detected)
  - Populations: buf500 rows on the published grid record set
    (cursor-approach-features-organic-hybrid-buf500.json); excision rows
    on the truncation grid record set. Anchor: recomputed buf500 M2 must
    reproduce the published 0.7636 AUC to +/- 0.002 or abort.
  - LOSO: LeaveOneGroupOut by participant, StandardScaler,
    LogisticRegression(class_weight='balanced', C=1.0, max_iter=5000),
    n_jobs=4 (shared machine).

Model ladder (each fit in both conditions):
  D1      : total_dwell_ms alone            (traditional, single channel)
  P1      : pai_dwell_ms alone              (PAI, single channel)
  Pp1     : pai_periph_ms alone             (peripheral-only mass)
  M1      : position                        (pairing row)
  M2      : position + total_dwell_ms       (traditional model — ANCHOR)
  M2-PAI  : position + pai_dwell_ms         (head-to-head swap)
  M2+Pp   : M2 + pai_periph_ms              (THE incremental test)
  M2+Pp35 : M2 + pai35_periph_ms            (functional-form sensitivity)
  M3-7    : M2 + 7 cursor geometry          (full model)
  M3-7+Pp : M3-7 + pai_periph_ms            (increment over everything)
  M4-7    : 7 geometry alone                (reference)

Paired stats of record (47 LOSO folds; Wilcoxon, d_z, bootstrap CI):
  M2+Pp vs M2 (both conditions)  — "additional info over traditional",
                                    the sentence in his email
  M2-PAI vs M2                   — soft assignment replaces binary?
  P1 vs D1                       — single-channel head-to-head
  M3-7+Pp vs M3-7                — survives the full cursor model?
  Pp increment drop (buf500 -> excision) — leakage profile of the
                                    peripheral channel

Outputs (new files only; no existing script modified):
  scripts/output/ablations/pai_exposure_ablation.json
  scripts/output/ablations/pai_exposure_ablation.md

Rank-type: [LAB, AdSERP, organic_hybrid]. PAI alphas use the exact
delivered-demo formula; NB35 form is the labeled sensitivity variant.

Run (serial, LOSO fits use n_jobs=4 max):
    .venv/bin/python scripts/pai_exposure_ablation.py
"""
from __future__ import annotations

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, roc_auc_score,
)
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import load_fixations, load_mouse_events  # noqa: E402
from data_loader import _RESULT_COL_X_MIN, _RESULT_COL_X_MAX  # noqa: E402
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/ablations"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BUF500_FEATURES = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-buf500.json"
EXCISION_FEATURES = OUT_DIR / "cursor-approach-features-organic-hybrid-approach-truncated.json"
TRIAL_STATS = OUT_DIR / "approach_truncation_trial_stats.json"
PUBLISHED_GRID = ROOT / "scripts/output/paper-output/click_buffer_ablation.json"

ANCHOR_M2_TOL = 0.002

APPROACH_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]

PAI_FEATURES = ["pai_dwell_ms", "pai_periph_ms",
                "pai35_dwell_ms", "pai35_periph_ms"]

VARIANTS = ["D1", "P1", "Pp1", "M1", "M2", "M2-PAI", "M2+Pp", "M2+Pp35",
            "M3-7", "M3-7+Pp", "M4-7"]

# phi = golden-ratio conjugate; lambda = phi^3, his exponent choice
# (approach-retreat/site/pai/index.html:97-98, verified vs glias2poly).
PHI = (1 + np.sqrt(5)) / 2 - 1
P_LAMBDA = PHI ** 3

N_BOOT = 5000
RNG = np.random.default_rng(20260818)


# ── PAI accumulation with time cutoff ─────────────────────────────────────

def pai_exposure_for_trial(trial_id, t_cuts):
    """Per-AOI PAI-weighted fixation mass up to each cutoff time.

    Returns {condition: [[pai_dwell, pai_periph, pai35_dwell,
    pai35_periph] per AOI]} in ms, or None if fixations/AOIs are
    unavailable (coverage accounting mirrors viewport_exposure_for_trial).
    """
    try:
        fixations = load_fixations(trial_id)
    except Exception:
        return None
    if not fixations:
        return None
    tops, bottoms, _etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None

    n_aoi = len(tops)
    x0 = float(_RESULT_COL_X_MIN)
    x1 = float(_RESULT_COL_X_MAX)
    a_top = np.asarray(tops, dtype=float)
    a_bot = np.asarray(bottoms, dtype=float)
    heights = np.maximum(a_bot - a_top, 1.0)
    areas = (x1 - x0) * heights
    w_a = (areas.max() / np.maximum(areas, 1.0)) ** P_LAMBDA
    cx = (x0 + x1) / 2.0
    cy = (a_top + a_bot) / 2.0

    ft = np.array([f["t"] for f in fixations], dtype=float)
    fx = np.array([f["x"] for f in fixations], dtype=float)
    fy = np.array([f["y"] for f in fixations], dtype=float)
    fd = np.array([f.get("d", 200) or 200 for f in fixations], dtype=float)

    # (n_fix, n_aoi) geometry — exact rectangle-boundary distance (0
    # inside) and centroid distance, vectorized.
    dx = np.maximum.reduce([x0 - fx, np.zeros_like(fx), fx - x1])
    dxg = np.repeat(dx[:, None], n_aoi, axis=1)
    dyg = np.maximum.reduce([
        a_top[None, :] - fy[:, None],
        np.zeros((len(fy), n_aoi)),
        fy[:, None] - a_bot[None, :],
    ])
    ogd = np.hypot(dxg, dyg)
    cgd = np.hypot(fx[:, None] - cx, fy[:, None] - cy[None, :])

    # Exact demo formula (index.html:136-138): guard max(cgd, 1), clip.
    alpha = np.clip(1.0 - np.sqrt(ogd / np.maximum(cgd, 1.0)) * w_a[None, :],
                    0.0, 1.0)
    # NB35 abstract-only sensitivity form (boundary OGD, no sqrt/area).
    alpha35 = np.clip(1.0 - ogd / np.maximum(cgd, 1.0), 0.0, 1.0)
    outside = ogd > 0.0

    out = {}
    for cond, t_cut in t_cuts.items():
        mask = np.ones(len(ft), dtype=bool) if t_cut is None else (ft < float(t_cut))
        d = fd[mask][:, None]
        acc = np.zeros((n_aoi, 4))
        if mask.any():
            acc[:, 0] = (d * alpha[mask]).sum(axis=0)
            acc[:, 1] = (d * np.where(outside[mask], alpha[mask], 0.0)).sum(axis=0)
            acc[:, 2] = (d * alpha35[mask]).sum(axis=0)
            acc[:, 3] = (d * np.where(outside[mask], alpha35[mask], 0.0)).sum(axis=0)
        out[cond] = acc.tolist()
    return out


# ── LOSO protocol (verbatim from viewport_exposure_ablation.py) ───────────

def per_trial_ranking_metrics(records, proba):
    by_trial = defaultdict(list)
    for r, p in zip(records, proba):
        by_trial[r["trial_id"]].append((r["was_clicked"], p))
    rrs, ndcg1s = [], []
    for _tid, rows in by_trial.items():
        if not any(c for c, _ in rows):
            continue
        rows.sort(key=lambda x: -x[1])
        for rank, (clicked, _) in enumerate(rows, 1):
            if clicked:
                rrs.append(1.0 / rank)
                ndcg1s.append(1.0 if rank == 1 else 0.0)
                break
    return float(np.mean(rrs)), float(np.mean(ndcg1s)), len(rrs)


def fit_eval(X, y, groups, records):
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=5000, class_weight="balanced", C=1.0)),
    ])
    proba = cross_val_predict(pipe, X, y, groups=groups, cv=LeaveOneGroupOut(),
                              method="predict_proba", n_jobs=4)[:, 1]
    auc = float(roc_auc_score(y, proba))
    ap = float(average_precision_score(y, proba))
    brier = float(brier_score_loss(y, proba))
    per_part, per_part_pids = [], []
    for pid in sorted(set(groups)):
        m = groups == pid
        if m.sum() < 10 or len(set(y[m])) < 2:
            continue
        per_part.append(float(roc_auc_score(y[m], proba[m])))
        per_part_pids.append(str(pid))
    mrr, ndcg1, n_trials = per_trial_ranking_metrics(records, proba)
    return {
        "auc": auc, "ap": ap, "brier": brier,
        "mrr_at_10": mrr, "ndcg_at_1": ndcg1, "n_ranked_trials": n_trials,
        "per_part_auc_median": float(np.median(per_part)),
        "per_part_auc_iqr": [float(np.percentile(per_part, 25)),
                             float(np.percentile(per_part, 75))],
        "per_part_aucs": per_part,
        "per_part_pids": per_part_pids,
        "n_records": int(len(records)),
    }


def build_features(records, variant):
    positions = np.array([r["position"] for r in records], dtype=float)
    total_dwell = np.array([r["total_dwell_ms"] for r in records], dtype=float)
    pai = np.array([[float(r[f]) for f in PAI_FEATURES] for r in records])
    pai_dwell = pai[:, :1]
    pai_periph = pai[:, 1:2]
    pai35_periph = pai[:, 3:4]
    x7 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7]
                   for r in records])
    pos = positions.reshape(-1, 1)
    dwell = total_dwell.reshape(-1, 1)
    if variant == "D1":
        return dwell
    if variant == "P1":
        return pai_dwell
    if variant == "Pp1":
        return pai_periph
    if variant == "M1":
        return pos
    if variant == "M2":
        return np.hstack([pos, dwell])
    if variant == "M2-PAI":
        return np.hstack([pos, pai_dwell])
    if variant == "M2+Pp":
        return np.hstack([pos, dwell, pai_periph])
    if variant == "M2+Pp35":
        return np.hstack([pos, dwell, pai35_periph])
    if variant == "M3-7":
        return np.hstack([pos, dwell, x7])
    if variant == "M3-7+Pp":
        return np.hstack([pos, dwell, x7, pai_periph])
    if variant == "M4-7":
        return x7
    raise ValueError(variant)


# ── Paired stats (verbatim from viewport_exposure_ablation.py) ────────────

def paired_tests(a, b, label_a, label_b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    assert len(a) == len(b), f"length mismatch: {len(a)} vs {len(b)}"
    n = len(a)
    diffs = a - b
    mean_delta = float(np.mean(diffs))
    try:
        w_stat, w_p = stats.wilcoxon(a, b, zero_method="wilcox",
                                     alternative="two-sided")
        w_stat, w_p = float(w_stat), float(w_p)
    except ValueError:
        w_stat, w_p = float("nan"), 1.0
    t_stat, t_p = stats.ttest_rel(a, b, alternative="two-sided")
    sd = float(np.std(diffs, ddof=1)) if n >= 2 else float("nan")
    d_z = mean_delta / sd if sd and sd > 0 else float("nan")
    boot = np.array([np.mean(diffs[RNG.integers(0, n, size=n)])
                     for _ in range(N_BOOT)])
    return {
        "comparison": f"{label_a} vs {label_b}",
        "n_folds": int(n),
        "mean_auc_a": float(np.mean(a)),
        "mean_auc_b": float(np.mean(b)),
        "mean_delta_auc": mean_delta,
        "median_delta_auc": float(np.median(diffs)),
        "delta_ci_95_lo": float(np.percentile(boot, 2.5)),
        "delta_ci_95_hi": float(np.percentile(boot, 97.5)),
        "wilcoxon_stat": w_stat, "wilcoxon_p": w_p,
        "paired_t_stat": float(t_stat), "paired_t_p": float(t_p),
        "cohens_d_z": d_z,
    }


def paired_by_pid(res_a, res_b):
    map_a = dict(zip(res_a["per_part_pids"], res_a["per_part_aucs"]))
    map_b = dict(zip(res_b["per_part_pids"], res_b["per_part_aucs"]))
    common = sorted(set(map_a) & set(map_b))
    return ([map_a[p] for p in common], [map_b[p] for p in common], common)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("PAI-vs-binary-exposure ablation — additional info over point-in-AOI?")
    print("=" * 72)

    print("\n[1/5] loading record sets + per-trial truncation timestamps")
    recs_buf = json.load(open(BUF500_FEATURES))
    recs_exc = json.load(open(EXCISION_FEATURES))
    trial_stats = {d["trial_id"]: d for d in json.load(open(TRIAL_STATS))}
    print(f"  buf500 records:   {len(recs_buf):,} "
          f"({sum(r['was_clicked'] for r in recs_buf):,} clicks, "
          f"{len({r['trial_id'] for r in recs_buf}):,} trials)")
    print(f"  excision records: {len(recs_exc):,} "
          f"({sum(r['was_clicked'] for r in recs_exc):,} clicks, "
          f"{len({r['trial_id'] for r in recs_exc}):,} trials)")

    trials_buf = sorted({r["trial_id"] for r in recs_buf})
    trials_exc = sorted({r["trial_id"] for r in recs_exc})
    all_trials = sorted(set(trials_buf) | set(trials_exc))

    print(f"\n[2/5] computing PAI exposure for {len(all_trials):,} trials "
          "(both cutoffs in one pass)")
    exposure = {"buf500": {}, "excision": {}}
    n_fail = 0
    n_missing_stats = 0
    for i, tid in enumerate(all_trials):
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(all_trials)}", file=sys.stderr)
        try:
            _e, _s, clicks = load_mouse_events(tid)
        except Exception:
            clicks = []
        t_click = float(clicks[-1][0]) if clicks else None
        cut_buf = (t_click - 500.0) if t_click is not None else None
        st = trial_stats.get(tid)
        if st is None:
            n_missing_stats += 1
            cut_exc = None
        elif st["onset_rule"] == "no_click" or st["delta_ms"] <= 0:
            cut_exc = None
        else:
            cut_exc = float(st["t_click"]) - float(st["delta_ms"])
        res = pai_exposure_for_trial(
            tid, {"buf500": cut_buf, "excision": cut_exc})
        if res is None:
            n_fail += 1
            continue
        exposure["buf500"][tid] = res["buf500"]
        exposure["excision"][tid] = res["excision"]

    cov = {
        "n_trials_union": len(all_trials),
        "n_trials_pai_computed": len(exposure["buf500"]),
        "n_trials_pai_failed": n_fail,
        "n_trials_missing_truncation_stats": n_missing_stats,
        "coverage_frac": (len(all_trials) - n_fail) / len(all_trials),
    }
    print(f"  PAI computed for {cov['n_trials_pai_computed']:,}"
          f"/{len(all_trials):,} trials "
          f"({cov['coverage_frac'] * 100:.2f}% coverage; "
          f"{n_fail} failed, {n_missing_stats} missing truncation stats)")

    def join(records, cond):
        kept, dropped_trials, oob = [], set(), 0
        for r in records:
            tid = r["trial_id"]
            per_aoi = exposure[cond].get(tid)
            if per_aoi is None:
                dropped_trials.add(tid)
                continue
            p = r["position"]
            if p >= len(per_aoi):
                oob += 1
                continue
            r = dict(r)
            for k, v in zip(PAI_FEATURES, per_aoi[p]):
                r[k] = float(v)
            kept.append(r)
        return kept, dropped_trials, oob

    joined = {}
    for cond, records in (("buf500", recs_buf), ("excision", recs_exc)):
        kept, dropped, oob = join(records, cond)
        joined[cond] = kept
        cov[f"{cond}_records_in"] = len(records)
        cov[f"{cond}_records_kept"] = len(kept)
        cov[f"{cond}_trials_dropped"] = len(dropped)
        cov[f"{cond}_records_position_oob"] = oob
        print(f"  [{cond}] {len(kept):,}/{len(records):,} records kept "
              f"({len(dropped)} trials dropped, {oob} position-OOB records)")

    # Descriptives, incl. the zero-dwell recovery census: records the
    # traditional metric scores as UNSEEN (total_dwell_ms == 0) that carry
    # nonzero peripheral PAI mass — exposure only PAI can see.
    desc = {}
    for cond in ("buf500", "excision"):
        recs = joined[cond]
        arr = np.array([[r[f] for f in PAI_FEATURES] for r in recs])
        dwell = np.array([r["total_dwell_ms"] for r in recs])
        clicked = np.array([r["was_clicked"] for r in recs], dtype=bool)
        zero_dwell = dwell <= 0
        zd_with_pai = zero_dwell & (arr[:, 1] > 0)
        desc[cond] = {
            f: {"median_ms": float(np.median(arr[:, i])),
                "p10_ms": float(np.percentile(arr[:, i], 10)),
                "p90_ms": float(np.percentile(arr[:, i], 90))}
            for i, f in enumerate(PAI_FEATURES)}
        desc[cond]["zero_dwell_records"] = int(zero_dwell.sum())
        desc[cond]["zero_dwell_with_pai_periph"] = int(zd_with_pai.sum())
        desc[cond]["zero_dwell_recovered_frac"] = (
            float(zd_with_pai.sum() / zero_dwell.sum()) if zero_dwell.any()
            else float("nan"))
        desc[cond]["zero_dwell_clicked"] = int((zero_dwell & clicked).sum())
        desc[cond]["zero_dwell_clicked_with_pai_periph"] = int(
            (zd_with_pai & clicked).sum())
        desc[cond]["pai_periph_median_clicked_ms"] = float(
            np.median(arr[clicked, 1])) if clicked.any() else float("nan")
        desc[cond]["pai_periph_median_nonclicked_ms"] = float(
            np.median(arr[~clicked, 1])) if (~clicked).any() else float("nan")
        print(f"  [{cond}] pai_periph_ms median "
              f"{desc[cond]['pai_periph_ms']['median_ms']:.0f} ms; "
              f"zero-dwell records {desc[cond]['zero_dwell_records']:,}, "
              f"{desc[cond]['zero_dwell_recovered_frac'] * 100:.1f}% carry "
              "peripheral PAI mass")

    print("\n[3/5] LOSO ladder (both conditions)")
    grid = {"buf500": {}, "excision": {}}
    for cond in ("buf500", "excision"):
        records = joined[cond]
        y = np.array([r["was_clicked"] for r in records], dtype=int)
        groups = np.array([r["trial_id"].split("-")[0] for r in records])
        print(f"  ── {cond} ({len(records):,} records, "
              f"{int(y.sum()):,} clicks, {len(set(groups))} participants) ──")
        for variant in VARIANTS:
            X = build_features(records, variant)
            res = fit_eval(X, y, groups, records)
            grid[cond][variant] = res
            print(f"    {variant:8s} AUC={res['auc']:.4f}  "
                  f"MRR={res['mrr_at_10']:.3f}  NDCG@1={res['ndcg_at_1']:.3f}")

    print("\n[4/5] anchor check + paired per-fold stats")
    pub = json.load(open(PUBLISHED_GRID))["grid"]
    pub_m2 = pub["organic_hybrid|buf500|M2"]["auc"]
    my_m2 = grid["buf500"]["M2"]["auc"]
    anchor = {
        "published_buf500_M2_auc": float(pub_m2),
        "recomputed_buf500_M2_auc": float(my_m2),
        "abs_diff": abs(my_m2 - pub_m2),
        "tolerance": ANCHOR_M2_TOL,
    }
    print(f"  anchor: buf500 M2 recomputed {my_m2:.4f} vs published "
          f"{pub_m2:.4f} (|diff| {anchor['abs_diff']:.4f})")
    if anchor["abs_diff"] > ANCHOR_M2_TOL:
        raise SystemExit("ANCHOR FAILED — record population does not "
                         "reproduce the published grid; aborting.")
    print("  anchor OK.")

    paired = []
    comparisons = [
        ("M2+Pp", "M2", "buf500"),
        ("M2+Pp", "M2", "excision"),
        ("M2-PAI", "M2", "buf500"),
        ("M2-PAI", "M2", "excision"),
        ("P1", "D1", "buf500"),
        ("P1", "D1", "excision"),
        ("M2+Pp35", "M2", "buf500"),
        ("M2+Pp35", "M2", "excision"),
        ("M3-7+Pp", "M3-7", "buf500"),
        ("M3-7+Pp", "M3-7", "excision"),
    ]
    for va, vb, cond in comparisons:
        a, b, _ = paired_by_pid(grid[cond][va], grid[cond][vb])
        t = paired_tests(a, b, f"{va} ({cond})", f"{vb} ({cond})")
        paired.append(t)
        print(f"  {t['comparison']:36s} dAUC={t['mean_delta_auc']:+.4f} "
              f"CI[{t['delta_ci_95_lo']:+.4f},{t['delta_ci_95_hi']:+.4f}] "
              f"d_z={t['cohens_d_z']:+.2f} p={t['wilcoxon_p']:.1e}")

    # Leakage profile of the increment: (M2+Pp − M2) at buf500 vs the
    # same increment under excision, per fold.
    inc = {}
    for cond in ("buf500", "excision"):
        a, b, pids = paired_by_pid(grid[cond]["M2+Pp"], grid[cond]["M2"])
        inc[cond] = {p: x - y for p, x, y in zip(pids, a, b)}
    common = sorted(set(inc["buf500"]) & set(inc["excision"]))
    t = paired_tests([inc["buf500"][p] for p in common],
                     [inc["excision"][p] for p in common],
                     "Pp increment (buf500)", "Pp increment (excision)")
    paired.append(t)
    print(f"  {t['comparison']:36s} dAUC={t['mean_delta_auc']:+.4f} "
          f"p={t['wilcoxon_p']:.1e}")

    print("\n[5/5] writing outputs")
    out = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "tags": "[LAB, AdSERP, organic_hybrid]",
        "producer": "scripts/pai_exposure_ablation.py",
        "question": ("Does PAI-weighted soft AOI exposure add information "
                     "over traditional binary gaze-point-in-AOI dwell for "
                     "predicting clicks (LOSO) and ranking (MRR@10)?"),
        "pai_formula": {
            "alpha": "clip(1 - sqrt(OGD/max(CGD,1)) * w_A, 0, 1)",
            "w_A": "(A_max/max(A,1))^lambda",
            "lambda": float(P_LAMBDA),
            "ogd": "exact rectangle-boundary distance (0 inside)",
            "source": "approach-retreat/site/pai/index.html (delivered demo, "
                      "verified vs glias2poly_1920x1080.py)",
            "sensitivity_form": "alpha35 = clip(1 - OGD/max(CGD,1), 0, 1) "
                                "(NB35 abstract-only form)",
        },
        "coverage": cov,
        "descriptives": desc,
        "anchor": anchor,
        "grid": {
            cond: {v: {k: x for k, x in res.items()
                       if k not in ("per_part_aucs", "per_part_pids")}
                   for v, res in variants.items()}
            for cond, variants in grid.items()
        },
        "grid_per_fold": {
            cond: {v: {"pids": res["per_part_pids"],
                       "aucs": res["per_part_aucs"]}
                   for v, res in variants.items()}
            for cond, variants in grid.items()
        },
        "paired": paired,
    }
    json_path = OUT_DIR / "pai_exposure_ablation.json"
    json_path.write_text(json.dumps(out, indent=1))
    print(f"  wrote {json_path}")

    md_path = OUT_DIR / "pai_exposure_ablation.md"
    lines = [
        "# PAI vs binary exposure — machine summary",
        "",
        f"Generated {out['generated']} by `scripts/pai_exposure_ablation.py`.",
        "Tags: `[LAB, AdSERP, organic_hybrid]`. See "
        "`docs/ablations/pai_exposure_validation.md` for the write-up.",
        "",
        "| Model | buf500 AUC | buf500 MRR | excision AUC | excision MRR |",
        "|---|---|---|---|---|",
    ]
    for v in VARIANTS:
        b = grid["buf500"][v]
        e = grid["excision"][v]
        lines.append(f"| {v} | {b['auc']:.4f} | {b['mrr_at_10']:.3f} "
                     f"| {e['auc']:.4f} | {e['mrr_at_10']:.3f} |")
    lines += ["", "| Comparison | dAUC | 95% CI | d_z | Wilcoxon p |",
              "|---|---|---|---|---|"]
    for t in paired:
        lines.append(
            f"| {t['comparison']} | {t['mean_delta_auc']:+.4f} "
            f"| [{t['delta_ci_95_lo']:+.4f}, {t['delta_ci_95_hi']:+.4f}] "
            f"| {t['cohens_d_z']:+.2f} | {t['wilcoxon_p']:.1e} |")
    md_path.write_text("\n".join(lines) + "\n")
    print(f"  wrote {md_path}")


if __name__ == "__main__":
    main()
