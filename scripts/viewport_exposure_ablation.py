"""Viewport-exposure leakage ablation — final tier of the control ladder.

Deliberation-phase leakage control family. Question: is "time on
screen per result" (viewport residence — no cursor needed) robust to
deliberation-phase leakage, compared against hover/dwell and the full
cursor episode geometry?

Caveat being tested (stated up front, not assumed away): scroll-to-click
is travel-to-target one level up. The viewport must be scrolled to the
to-be-clicked result before the click, so exposure time is NOT
leakage-free by construction — that is exactly why we measure its
buf500 -> full-excision drop instead of asserting robustness.

Design:
  - Exposure features per (trial, AOI): cumulative ms the AOI intersected
    the scroll viewport, plus the top/mid/bot viewport-third split —
    identical piecewise-constant machinery as the viewport-bands
    calibration (tag edmonds-2026-vpbands-v1;
    scripts/viewport_time_calibration.py:viewport_ms_for_trial),
    re-implemented locally with a time cutoff. AOI geometry is the
    organic_hybrid bands (build_hybrid_aois: bbox organics + dd_top +
    native_ad in display order) so `position` indexes match the cursor
    feature records exactly.
  - Two conditions, matching scripts/approach_truncation_ablation.py:
      buf500   — exposure accumulated up to t_click - 500 ms (published
                 terminal-buffer convention; no-click trials: full span)
      excision — exposure accumulated up to the SAME per-trial
                 committed-approach onset t_onset used by the cursor
                 truncation grid, loaded verbatim from
                 scripts/output/ablations/approach_truncation_trial_stats.json
                 (t_cut = t_click - delta_ms). NOT re-detected.
  - Populations: the buf500 rows use the exact record set of the
    published grid (AdSERP/data/cursor-approach-features-organic-hybrid-
    buf500.json, 19,848 records / 2,589 clicks); the excision rows use
    the exact record set of the truncation grid (scripts/output/ablations/
    cursor-approach-features-organic-hybrid-approach-truncated.json,
    18,919 records). Cursor variants (M1/M2/M3-7/M4-7) are recomputed on
    those same records as anchor + pairing rows.
  - Anchor check: recomputed buf500 M2 must reproduce the published
    0.7636 AUC to within +/- 0.002 or the script aborts.
  - LOSO protocol: identical to click_buffer_ablation.py /
    approach_truncation_ablation.py — LeaveOneGroupOut by participant
    (47 folds), StandardScaler, LogisticRegression(class_weight=
    'balanced', C=1.0, max_iter=5000), n_jobs=4 (shared machine).
  - Coverage: any trial whose meta/mouse events cannot be loaded for the
    exposure computation is dropped from ALL ladder rows of that
    condition (cursor rows included) so every comparison stays paired;
    the count is reported prominently.

Model ladder (each fit in both conditions):
  E-any   : vt_any_ms alone (1 feature)
  E       : vt_any + vt_top + vt_mid + vt_bot (4 features)
  M1      : position (recomputed pairing row)
  M1+E    : position + 4 exposure
  M2      : position + total_dwell_ms (gaze fixation dwell; the grid's
            dwell model — anchor row)
  M2+E    : position + total_dwell_ms + 4 exposure ("M1+E+dwell")
  M3-7    : position + total_dwell_ms + 7 leakage-corrected geometry
  M3-7+E  : M3-7 + 4 exposure
  M4-7    : 7 geometry alone (reference)

Addendum rows (coordinator follow-up): the grid's M2 dwell is GAZE
fixation dwell, so cursor hover was never isolated. H isolates the
cursor-hover channel:
  H       : dwell_in_proximity_ms alone (cursor hover, 1 feature)
  M1+H    : position + cursor hover
  M1+H+E  : position + cursor hover + 4 exposure
Paired stat of record: M1+H vs M2 (gaze) under both conditions — how
much of gaze-dwell's robustness does the cursor analog retain?

Outputs (new files only; no existing script modified):
  scripts/output/ablations/viewport_exposure_ablation.json
  scripts/output/ablations/viewport_exposure_ablation.md

Rank-type: [LAB, AdSERP, organic_hybrid].

Run (serial, LOSO fits use n_jobs=4 max):
    .venv/bin/python scripts/viewport_exposure_ablation.py
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

from data_loader import get_trial_meta, load_mouse_events  # noqa: E402
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402

OUT_DIR = ROOT / "scripts/output/ablations"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BUF500_FEATURES = ROOT / "AdSERP/data/cursor-approach-features-organic-hybrid-buf500.json"
EXCISION_FEATURES = OUT_DIR / "cursor-approach-features-organic-hybrid-approach-truncated.json"
TRIAL_STATS = OUT_DIR / "approach_truncation_trial_stats.json"
PUBLISHED_GRID = ROOT / "scripts/output/paper-output/click_buffer_ablation.json"
TRUNCATION_GRID = OUT_DIR / "approach_truncation_ablation.json"

ANCHOR_M2_TOL = 0.002  # AUC tolerance on the buf500 M2 reproduction

APPROACH_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
EXPOSURE_4 = ["vt_any_ms", "vt_top_ms", "vt_mid_ms", "vt_bot_ms"]

VARIANTS = ["E-any", "E", "M1", "M1+E", "H", "M1+H", "M1+H+E",
            "M2", "M2+E", "M3-7", "M3-7+E", "M4-7"]

N_BOOT = 5000
RNG = np.random.default_rng(20260812)


# ── Viewport exposure with time cutoff ────────────────────────────────────

def viewport_exposure_for_trial(trial_id, t_cuts):
    """Cumulative per-AOI viewport-band exposure up to each cutoff time.

    Same piecewise-constant scroll-timeline machinery as
    viewport_time_calibration.viewport_ms_for_trial (edmonds-2026-vpbands-v1):
    scrollY assumed 0 at trial start, stepped at scroll events; an AOI
    accrues ms_any while any part of it intersects the [scrollY,
    scrollY + scr_h] viewport, and accrues in the top/mid/bot third
    according to its center's viewport-y. AOI geometry = organic_hybrid
    (top, bottom) bands from build_hybrid_aois, so index p here equals the
    `position` field of the cursor feature records.

    t_cuts: dict {condition_name: t_cut_or_None}. None = full trial span.
    Returns {condition_name: [[any, top, mid, bot] per AOI] } in ms,
    or None if meta/events/AOIs are unavailable (coverage accounting).
    """
    try:
        meta = get_trial_meta(trial_id)
    except Exception:
        return None
    if meta is None:
        return None
    _doc_h, scr_h, _ = meta
    try:
        events, scrolls, _clicks = load_mouse_events(trial_id)
    except Exception:
        return None
    if not events or not scr_h:
        return None
    tops, bottoms, _etypes = build_hybrid_aois(trial_id)
    if not tops:
        return None
    bands = list(zip(tops, bottoms))
    n_aoi = len(bands)
    third = scr_h / 3.0

    ts = [e[0] for e in events]
    t_start, t_end = min(ts), max(ts)
    if t_end <= t_start:
        return None

    out = {}
    for cond, t_cut in t_cuts.items():
        t_eff = t_end if t_cut is None else min(t_end, float(t_cut))
        acc = [[0.0, 0.0, 0.0, 0.0] for _ in range(n_aoi)]
        if t_eff > t_start:
            timeline = [(t_start, 0.0)]
            for (t, y) in sorted(scrolls):
                if t_start <= t <= t_eff:
                    timeline.append((float(t), float(y)))
            timeline.append((t_eff, timeline[-1][1]))
            for (t0, y0), (t1, _) in zip(timeline, timeline[1:]):
                dt = t1 - t0
                if dt <= 0:
                    continue
                vp_top, vp_bot = y0, y0 + scr_h
                for p, (a_top, a_bot) in enumerate(bands):
                    if min(a_bot, vp_bot) <= max(a_top, vp_top):
                        continue
                    acc[p][0] += dt
                    center_vp_y = (a_top + a_bot) / 2.0 - y0
                    if 0 <= center_vp_y < third:
                        acc[p][1] += dt
                    elif third <= center_vp_y < 2 * third:
                        acc[p][2] += dt
                    elif 2 * third <= center_vp_y <= scr_h:
                        acc[p][3] += dt
                    # center outside viewport: ms_any only
        out[cond] = acc
    return out


# ── LOSO protocol (mirrors approach_truncation_ablation.fit_eval) ─────────

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
    expo = np.array([[float(r[f]) for f in EXPOSURE_4] for r in records])
    vt_any = expo[:, :1]
    x7 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7]
                   for r in records])
    pos = positions.reshape(-1, 1)
    if variant == "E-any":
        return vt_any
    if variant == "E":
        return expo
    if variant == "M1":
        return pos
    if variant == "M1+E":
        return np.hstack([pos, expo])
    hover = np.array([[float(r.get("dwell_in_proximity_ms", 0.0) or 0.0)]
                      for r in records])
    if variant == "H":
        return hover
    if variant == "M1+H":
        return np.hstack([pos, hover])
    if variant == "M1+H+E":
        return np.hstack([pos, hover, expo])
    if variant == "M2":
        return np.column_stack([positions, total_dwell])
    if variant == "M2+E":
        return np.hstack([np.column_stack([positions, total_dwell]), expo])
    if variant == "M3-7":
        return np.column_stack([positions, total_dwell, x7])
    if variant == "M3-7+E":
        return np.hstack([np.column_stack([positions, total_dwell, x7]), expo])
    if variant == "M4-7":
        return x7
    raise ValueError(variant)


# ── Paired stats (mirrors approach_truncation_ablation) ───────────────────

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
    print("Viewport-exposure ablation — control-ladder final tier")
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
    print(f"  truncation trial stats: {len(trial_stats):,} trials")

    trials_buf = sorted({r["trial_id"] for r in recs_buf})
    trials_exc = sorted({r["trial_id"] for r in recs_exc})
    all_trials = sorted(set(trials_buf) | set(trials_exc))

    print(f"\n[2/5] computing viewport exposure for {len(all_trials):,} trials "
          "(both cutoffs in one pass)")
    exposure = {"buf500": {}, "excision": {}}
    n_fail = 0
    n_missing_stats = 0
    for i, tid in enumerate(all_trials):
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(all_trials)}", file=sys.stderr)
        # Cutoffs. buf500: t_click - 500 ms (extractor convention: no
        # truncation without a click). excision: t_click - delta_ms from
        # the truncation grid's per-trial stats, i.e. the identical
        # committed-approach onset; delta 0 / no_click -> full span.
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
            cut_exc = float(st["t_click"]) - float(st["delta_ms"])  # = t_onset
        res = viewport_exposure_for_trial(
            tid, {"buf500": cut_buf, "excision": cut_exc})
        if res is None:
            n_fail += 1
            continue
        exposure["buf500"][tid] = res["buf500"]
        exposure["excision"][tid] = res["excision"]

    cov = {
        "n_trials_union": len(all_trials),
        "n_trials_exposure_computed": len(exposure["buf500"]),
        "n_trials_exposure_failed": n_fail,
        "n_trials_missing_truncation_stats": n_missing_stats,
        "coverage_frac": (len(all_trials) - n_fail) / len(all_trials),
    }
    print(f"  exposure computed for {cov['n_trials_exposure_computed']:,}"
          f"/{len(all_trials):,} trials "
          f"({cov['coverage_frac'] * 100:.2f}% coverage; "
          f"{n_fail} failed, {n_missing_stats} missing truncation stats)")

    # ── Join exposure onto records; drop uncovered trials from BOTH
    #    conditions' ladders so every row stays paired ──
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
            a, t, m, b = per_aoi[p]
            r["vt_any_ms"], r["vt_top_ms"] = float(a), float(t)
            r["vt_mid_ms"], r["vt_bot_ms"] = float(m), float(b)
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

    # Exposure descriptives (units: ms)
    desc = {}
    for cond in ("buf500", "excision"):
        arr = np.array([[r[f] for f in EXPOSURE_4] for r in joined[cond]])
        desc[cond] = {
            f: {"median_ms": float(np.median(arr[:, i])),
                "p10_ms": float(np.percentile(arr[:, i], 10)),
                "p90_ms": float(np.percentile(arr[:, i], 90))}
            for i, f in enumerate(EXPOSURE_4)}
        print(f"  [{cond}] vt_any_ms median {desc[cond]['vt_any_ms']['median_ms']:.0f} ms "
              f"(p10 {desc[cond]['vt_any_ms']['p10_ms']:.0f}, "
              f"p90 {desc[cond]['vt_any_ms']['p90_ms']:.0f})")

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

    # ── Anchor check: buf500 M2 must reproduce the published grid ──
    pub = json.load(open(PUBLISHED_GRID))["grid"]
    pub_m2 = pub["organic_hybrid|buf500|M2"]["auc"]
    my_m2 = grid["buf500"]["M2"]["auc"]
    anchor = {
        "published_buf500_M2_auc": float(pub_m2),
        "recomputed_buf500_M2_auc": float(my_m2),
        "abs_diff": abs(my_m2 - pub_m2),
        "tolerance": ANCHOR_M2_TOL,
        "n_records_published": pub["organic_hybrid|buf500|M2"]["n_records"],
        "n_records_recomputed": grid["buf500"]["M2"]["n_records"],
        "pass": abs(my_m2 - pub_m2) <= ANCHOR_M2_TOL,
    }
    print(f"\n  ANCHOR: buf500 M2 recomputed {my_m2:.4f} vs published "
          f"{pub_m2:.4f} (|diff| {anchor['abs_diff']:.4f}, "
          f"tol {ANCHOR_M2_TOL}) -> {'PASS' if anchor['pass'] else 'FAIL'}")
    if not anchor["pass"]:
        print("  ANCHOR FAILED — protocol/population mismatch; aborting "
              "before any comparisons.", file=sys.stderr)
        out = OUT_DIR / "viewport_exposure_ablation.json"
        out.write_text(json.dumps({"anchor_check": anchor,
                                   "coverage": cov,
                                   "status": "ABORTED_ANCHOR_FAIL"}, indent=2))
        return 1

    print("\n[4/5] paired per-fold stats")
    stats_out = {}

    def add(key, res_a, res_b, la, lb):
        a, b, _ = paired_by_pid(res_a, res_b)
        stats_out[key] = paired_tests(a, b, la, lb)

    # The requested comparisons
    add("exc_E_vs_exc_M2", grid["excision"]["E"], grid["excision"]["M2"],
        "E (excision)", "M2 (excision)")
    add("exc_M1+E_vs_exc_M2", grid["excision"]["M1+E"], grid["excision"]["M2"],
        "M1+E (excision)", "M2 (excision)")
    add("exc_M3-7+E_vs_exc_M3-7", grid["excision"]["M3-7+E"],
        grid["excision"]["M3-7"], "M3-7+E (excision)", "M3-7 (excision)")
    add("buf500_M3-7+E_vs_buf500_M3-7", grid["buf500"]["M3-7+E"],
        grid["buf500"]["M3-7"], "M3-7+E (buf500)", "M3-7 (buf500)")
    add("exc_M2+E_vs_exc_M2", grid["excision"]["M2+E"], grid["excision"]["M2"],
        "M2+E (excision)", "M2 (excision)")
    # Addendum: cursor-hover analog vs gaze dwell (deployability question)
    add("buf500_M1+H_vs_buf500_M2", grid["buf500"]["M1+H"],
        grid["buf500"]["M2"], "M1+H (buf500)", "M2 gaze (buf500)")
    add("exc_M1+H_vs_exc_M2", grid["excision"]["M1+H"],
        grid["excision"]["M2"], "M1+H (excision)", "M2 gaze (excision)")
    # Per-model condition drop (buf500 -> excision), cross-condition pairing
    for v in VARIANTS:
        add(f"drop_{v}", grid["buf500"][v], grid["excision"][v],
            f"{v} (buf500)", f"{v} (excision)")

    for k, v in stats_out.items():
        print(f"  {k}: dAUC={v['mean_delta_auc']:+.4f} "
              f"[{v['delta_ci_95_lo']:+.4f}, {v['delta_ci_95_hi']:+.4f}], "
              f"d_z={v['cohens_d_z']:.2f}, wilcoxon p={v['wilcoxon_p']:.2e}")

    print("\n[5/5] combined control-ladder table + verdict")
    trunc_grid = json.load(open(TRUNCATION_GRID))[
        "loso_grid_truncated_organic_hybrid"]

    ladder = {}
    for v in VARIANTS:
        b, e = grid["buf500"][v]["auc"], grid["excision"][v]["auc"]
        ladder[v] = {"buf500_auc": b, "excision_auc": e,
                     "drop_auc": b - e,
                     "drop_frac_of_buf500_margin_over_M1": None}
    m1_b = grid["buf500"]["M1"]["auc"]
    m1_e = grid["excision"]["M1"]["auc"]
    for v in VARIANTS:
        b, e = ladder[v]["buf500_auc"], ladder[v]["excision_auc"]
        margin = b - m1_b
        if v != "M1" and margin > 0.005:
            ladder[v]["drop_frac_of_buf500_margin_over_M1"] = float(
                ((b - m1_b) - (e - m1_e)) / margin)

    # Reference rows from the two prior grids (full populations, pre-join)
    reference_rows = {
        "published_buf500": {v: pub[f"organic_hybrid|buf500|{v}"]["auc"]
                             for v in ["M1", "M2", "M3-7", "M4-7"]},
        "truncation_grid_excision": {v: trunc_grid[v]["auc"]
                                     for v in ["M1", "M2", "M3-7", "M4-7"]},
    }

    hdr = (f"  {'model':10s} {'buf500':>8s} {'excision':>9s} {'drop':>8s}")
    print(hdr)
    for v in VARIANTS:
        r = ladder[v]
        print(f"  {v:10s} {r['buf500_auc']:>8.4f} {r['excision_auc']:>9.4f} "
              f"{r['drop_auc']:>8.4f}")

    # Verdict heuristic — exposure vs hover vs geometry under excision:
    e_exc = grid["excision"]["E"]["auc"]
    m2_exc = grid["excision"]["M2"]["auc"]
    e_drop = ladder["E"]["drop_auc"]
    m2_drop = ladder["M2"]["drop_auc"]
    m37_drop = ladder["M3-7"]["drop_auc"]
    w = stats_out["exc_E_vs_exc_M2"]
    if e_drop <= m2_drop + 0.005 and e_exc >= m2_exc - 0.01:
        verdict_class = "supported"
    elif e_drop < m37_drop:
        verdict_class = "partially supported"
    else:
        verdict_class = "not supported"
    verdict = (
        f"{verdict_class}: E (exposure bands alone) holds "
        f"{e_exc:.3f} AUC under full excision vs M2 (position+dwell) "
        f"{m2_exc:.3f}, with a buf500->excision drop of {e_drop:+.4f} AUC "
        f"vs {m2_drop:+.4f} for M2 and {m37_drop:+.4f} for M3-7 "
        f"(E vs M2 under excision: dAUC={w['mean_delta_auc']:+.4f}, "
        f"Wilcoxon p={w['wilcoxon_p']:.2e}, d_z={w['cohens_d_z']:.2f}).")
    print(f"\n  VERDICT: {verdict}")

    summary = {
        "experiment": ("viewport-exposure leakage ablation "
                       "(control-ladder final tier, Leaky Cursor revision)"),
        "generated_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "LAB",
        "dataset": "AdSERP",
        "rank_type": "organic_hybrid",
        "caveat_under_test": (
            "scroll-to-click is travel-to-target one level up; viewport "
            "exposure is NOT leakage-free by construction — the "
            "buf500->excision drop measures how much of it is "
            "deliberation-phase leakage."),
        "exposure_machinery": (
            "per-AOI cumulative ms in viewport bands {any, top, mid, bot}, "
            "piecewise-constant over scroll events (scrollY=0 at trial "
            "start), organic_hybrid AOI (top,bottom) geometry from "
            "build_hybrid_aois; calibration tag edmonds-2026-vpbands-v1 "
            "(scripts/viewport_time_calibration.py)."),
        "conditions": {
            "buf500": "exposure accumulated up to t_click - 500 ms "
                      "(no-click trials: full span); records = published "
                      "buf500 organic_hybrid feature set",
            "excision": "exposure accumulated up to the per-trial "
                        "committed-approach onset t_onset reused verbatim "
                        "from approach_truncation_trial_stats.json; "
                        "records = truncation grid's feature set",
        },
        "loso_protocol": ("LeaveOneGroupOut by participant (47 folds), "
                          "StandardScaler + LogisticRegression("
                          "class_weight='balanced', C=1.0, max_iter=5000), "
                          "n_jobs=4"),
        "anchor_check": anchor,
        "coverage": cov,
        "exposure_descriptives_ms": desc,
        "ladder": ladder,
        "loso_grid": {cond: {v: grid[cond][v] for v in VARIANTS}
                      for cond in ("buf500", "excision")},
        "reference_rows_full_population": reference_rows,
        "paired_stats": stats_out,
        "verdict": verdict,
        "addendum_cursor_hover": {
            "note": ("H / M1+H / M1+H+E rows added at coordinator request "
                     "(2026-08-12): the grid's M2 dwell is gaze fixation "
                     "dwell, so the cursor-hover channel "
                     "(dwell_in_proximity_ms) was never isolated. Paired "
                     "stat of record: M1+H vs M2 (gaze) under both "
                     "conditions — how much of gaze-dwell's robustness the "
                     "cursor analog retains."),
            "variants": ["H", "M1+H", "M1+H+E"],
            "paired_stat_keys": ["buf500_M1+H_vs_buf500_M2",
                                 "exc_M1+H_vs_exc_M2"],
        },
        "inputs": {
            "buf500_features": str(BUF500_FEATURES.relative_to(ROOT)),
            "excision_features": str(EXCISION_FEATURES.relative_to(ROOT)),
            "trial_stats": str(TRIAL_STATS.relative_to(ROOT)),
            "published_grid": str(PUBLISHED_GRID.relative_to(ROOT)),
            "truncation_grid": str(TRUNCATION_GRID.relative_to(ROOT)),
        },
    }
    out = OUT_DIR / "viewport_exposure_ablation.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
