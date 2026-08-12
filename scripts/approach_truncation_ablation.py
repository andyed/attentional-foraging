"""Deliberation-phase leakage control: full-approach truncation ablation.

Motivating concern: the terminal click-buffer
(Δ ∈ {0, 200, 500, 1000} ms) removes only the lock-on window before the
click, not the entire deliberation-phase approach to the to-be-clicked
AOI. If the M4 cursor signal is partly mechanical (cursor must travel to
the click target), a control that excises the WHOLE committed approach
segment should collapse the AUC toward M1. If the signal is behavioral
(pre-decision hover/revisit geometry), it should survive.

Operational definition of "committed approach onset" (per trial):

    Let (x_c, y_c) be the trial's final click coordinate and t_click its
    timestamp. Over the pre-click positional cursor samples
    (mousemove / mouseover / click events, x > 0, t < t_click), define
    d(t) = Euclidean distance from the cursor to (x_c, y_c).

    Walking BACKWARD from the click, the committed-approach onset t_onset
    is the most recent sample t* such that:
      (a) d(t*) is a local maximum of d  (d[i] >= d[i-1] and d[i] >= d[i+1]),
      (b) prominence: d(t*) - min(d after t*) >= 50 px, and
      (c) d(t*) >= 100 px (outside the click target's proximity band —
          the same 100-px threshold used by dwell_in_proximity_ms).
    Fallback if no such local maximum exists (e.g. monotone descent all
    trial): the most recent sample with d(t) >= median(d) over the
    pre-click stream. If that also fails, the whole stream is excised
    (the trial drops out of the truncated feature set; counted).

    Everything at t >= t_onset is excluded from feature computation for
    ALL AOIs — the cursor stream and the fixation stream are truncated at
    t_onset, so the control is symmetric across AOIs, not a clicked-AOI-
    only surgery. Implementation: the canonical extractor
    `compute_cursor_approach_features.compute_approach_features` is
    called with a per-trial click_buffer_ms = t_click - t_onset, which
    truncates fixations + mouse samples at exactly t_onset. Click
    ATTRIBUTION still uses the raw click record — the label survives,
    only the feature inputs are truncated (same contract as the
    published terminal-buffer control).

Protocol (matches scripts/click_buffer_ablation.py, the producer of the
paper's Table 4/5 grid): LOSO (LeaveOneGroupOut by participant) logistic
regression, StandardScaler, class_weight='balanced', C=1.0. Variants
M1 / M2 / M3 / M3-7 / M4-9 / M4-7 under organic_hybrid attribution.
Comparison rows are loaded from the published grid at
scripts/output/paper-output/click_buffer_ablation.json (buf 0/200/500/1000),
NOT recomputed. Paired stats mirror scripts/paper_stat_tests.py
(Wilcoxon, paired t, Cohen's d_z, bootstrap 95% CI on per-fold ΔAUC).

Also emits truncated feature files for `organic` and `typed` attribution
(consumed by scripts/nonclicked_absorption_check.py) and per-trial
truncation cost stats (ms, px of path, fraction of trial removed).

New-file-only companion to the revision; does not modify any existing
script. Rank-type: [LAB, AdSERP, organic_hybrid] for the headline grid.

Run (serial, ~10-15 min; LOSO fits use n_jobs=4 max):
    .venv/bin/python scripts/approach_truncation_ablation.py
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

from data_loader import get_trial_ids, load_mouse_events  # noqa: E402
from compute_cursor_approach_features import compute_approach_features  # noqa: E402

OUT_DIR = ROOT / "scripts/output/ablations"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PUBLISHED_GRID = ROOT / "scripts/output/paper-output/click_buffer_ablation.json"

PROM_PX = 50.0        # required prominence of the onset local maximum
PROX_PX = 100.0       # onset must lie outside the proximity band
POSITIONAL = ("mousemove", "mouseover", "click")  # matches extractor timeline

# Attributions to emit truncated features for. organic_hybrid feeds the
# §4.1 grid here; organic feeds M5 and typed feeds the LambdaMART check
# in nonclicked_absorption_check.py.
ATTRIBUTIONS = ["organic_hybrid", "organic", "typed"]

APPROACH_9 = [
    "min_dist", "mean_dist", "final_dist", "retreat_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
APPROACH_7 = [
    "min_dist", "mean_dist",
    "dwell_in_proximity_ms", "mean_approach_velocity", "max_approach_velocity",
    "direction_changes", "frac_decreasing",
]
VARIANTS = ["M1", "M2", "M3", "M3-7", "M4-9", "M4-7"]

N_BOOT = 5000
RNG = np.random.default_rng(20260812)


# ── Committed-approach onset detection ────────────────────────────────────

def detect_approach_onset(trial_id):
    """Return per-trial truncation info dict, or None if trial unusable.

    Keys: trial_id, t_click, t_onset, delta_ms (click_buffer equivalent),
    onset_rule ('local_max' | 'median_fallback' | 'full_excision' |
    'no_click'), removed_path_px, trial_span_ms, frac_time_removed,
    n_samples_removed, n_samples_total.
    """
    mouse_data = load_mouse_events(trial_id)
    if mouse_data is None:
        return None
    all_events, _scrolls, clicks = mouse_data
    samples = [(t, x, y) for (t, evt, x, y) in all_events
               if evt in POSITIONAL and x > 0 and y > 0]
    if len(samples) < 3:
        return None
    ts = np.array([s[0] for s in samples], dtype=float)
    xs = np.array([s[1] for s in samples], dtype=float)
    ys = np.array([s[2] for s in samples], dtype=float)

    if not clicks:
        return {
            "trial_id": trial_id, "onset_rule": "no_click",
            "t_click": None, "t_onset": None, "delta_ms": 0.0,
            "removed_path_px": 0.0,
            "trial_span_ms": float(ts[-1] - ts[0]),
            "frac_time_removed": 0.0,
            "n_samples_removed": 0, "n_samples_total": int(len(ts)),
        }

    t_click = float(clicks[-1][0])
    cx, cy = float(clicks[-1][1]), float(clicks[-1][2])

    pre = ts < t_click
    if pre.sum() < 3:
        rule, t_onset = "full_excision", float(ts[0])
    else:
        d = np.sqrt((xs[pre] - cx) ** 2 + (ys[pre] - cy) ** 2)
        t_pre = ts[pre]
        n = len(d)
        # suffix minimum of d (min over d[i+1:]) for prominence check
        suffix_min = np.empty(n)
        suffix_min[-1] = d[-1]
        for i in range(n - 2, -1, -1):
            suffix_min[i] = min(d[i + 1], suffix_min[i + 1])
        t_onset, rule = None, None
        for i in range(n - 2, 0, -1):  # latest interior sample first
            if (d[i] >= d[i - 1] and d[i] >= d[i + 1]
                    and (d[i] - suffix_min[i]) >= PROM_PX
                    and d[i] >= PROX_PX):
                t_onset, rule = float(t_pre[i]), "local_max"
                break
        if t_onset is None:
            med = float(np.median(d))
            above = np.nonzero(d >= med)[0]
            if len(above):
                t_onset, rule = float(t_pre[above[-1]]), "median_fallback"
            else:
                t_onset, rule = float(t_pre[0]), "full_excision"

    delta_ms = max(t_click - t_onset, 0.0)

    # Cost accounting: path length + samples in the excised window
    removed = (ts >= t_onset) & (ts <= t_click)
    idx = np.nonzero(removed)[0]
    if len(idx) >= 2:
        seg = np.sqrt(np.diff(xs[idx]) ** 2 + np.diff(ys[idx]) ** 2)
        removed_path_px = float(seg.sum())
    else:
        removed_path_px = 0.0
    span = float(t_click - ts[0]) if t_click > ts[0] else float(ts[-1] - ts[0])
    frac = float(delta_ms / span) if span > 0 else 0.0

    return {
        "trial_id": trial_id, "onset_rule": rule,
        "t_click": t_click, "t_onset": t_onset, "delta_ms": float(delta_ms),
        "removed_path_px": removed_path_px,
        "trial_span_ms": span,
        "frac_time_removed": min(frac, 1.0),
        "n_samples_removed": int(removed.sum()),
        "n_samples_total": int(len(ts)),
    }


# ── LOSO protocol (mirrors click_buffer_ablation.fit_eval) ────────────────

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
    positions = np.array([r["position"] for r in records])
    total_dwell = np.array([r["total_dwell_ms"] for r in records])
    if variant == "M1":
        return positions.reshape(-1, 1)
    if variant == "M2":
        return np.column_stack([positions, total_dwell])
    if variant == "M3":
        X9 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
        return np.column_stack([positions, total_dwell, X9])
    if variant == "M3-7":
        X7 = np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
        return np.column_stack([positions, total_dwell, X7])
    if variant == "M4-9":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_9] for r in records])
    if variant == "M4-7":
        return np.array([[float(r.get(f, 0.0) or 0.0) for f in APPROACH_7] for r in records])
    raise ValueError(variant)


# ── Paired stats (mirrors paper_stat_tests.paired_tests) ──────────────────

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
    """Align two fit_eval results (or published grid cells) by participant."""
    map_a = dict(zip(res_a["per_part_pids"], res_a["per_part_aucs"]))
    map_b = dict(zip(res_b["per_part_pids"], res_b["per_part_aucs"]))
    common = sorted(set(map_a) & set(map_b))
    return ([map_a[p] for p in common], [map_b[p] for p in common], common)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Approach-truncation ablation — deliberation-phase leakage control")
    print("=" * 72)

    trial_ids = get_trial_ids()
    print(f"\n[1/4] detecting committed-approach onset for {len(trial_ids)} trials")
    trunc_info = {}
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(trial_ids)}", file=sys.stderr)
        info = detect_approach_onset(tid)
        if info is not None:
            trunc_info[tid] = info

    rules = defaultdict(int)
    for v in trunc_info.values():
        rules[v["onset_rule"]] += 1
    clicked = [v for v in trunc_info.values() if v["onset_rule"] not in ("no_click",)]
    deltas = np.array([v["delta_ms"] for v in clicked])
    paths = np.array([v["removed_path_px"] for v in clicked])
    fracs = np.array([v["frac_time_removed"] for v in clicked])
    trunc_stats = {
        "n_trials_with_onset": len(clicked),
        "onset_rule_counts": dict(rules),
        "delta_ms": {"median": float(np.median(deltas)),
                     "iqr": [float(np.percentile(deltas, 25)),
                             float(np.percentile(deltas, 75))],
                     "mean": float(deltas.mean())},
        "removed_path_px": {"median": float(np.median(paths)),
                            "iqr": [float(np.percentile(paths, 25)),
                                    float(np.percentile(paths, 75))],
                            "mean": float(paths.mean())},
        "frac_time_removed": {"median": float(np.median(fracs)),
                              "iqr": [float(np.percentile(fracs, 25)),
                                      float(np.percentile(fracs, 75))],
                              "mean": float(fracs.mean())},
    }
    print(f"  onset rules: {dict(rules)}")
    print(f"  median removed: {np.median(deltas):.0f} ms, "
          f"{np.median(paths):.0f} px path, "
          f"{np.median(fracs) * 100:.1f}% of trial time")

    print(f"\n[2/4] extracting truncated features ({', '.join(ATTRIBUTIONS)})")
    feature_paths = {}
    for attribution in ATTRIBUTIONS:
        out_path = OUT_DIR / f"cursor-approach-features-{attribution.replace('_', '-')}-approach-truncated.json"
        feature_paths[attribution] = out_path
        all_records, n_ok, n_dropped = [], 0, 0
        for i, tid in enumerate(trial_ids):
            if (i + 1) % 400 == 0:
                print(f"  [{attribution}] {i + 1}/{len(trial_ids)}", file=sys.stderr)
            info = trunc_info.get(tid)
            if info is None:
                n_dropped += 1
                continue
            delta = info["delta_ms"] if info["onset_rule"] != "no_click" else 0
            try:
                recs = compute_approach_features(
                    tid, attribution=attribution, click_buffer_ms=delta)
            except Exception:
                recs = None
            if recs:
                all_records.extend(recs)
                n_ok += 1
            else:
                n_dropped += 1
        out_path.write_text(json.dumps(all_records))
        print(f"  [{attribution}] {n_ok} trials kept, {n_dropped} dropped, "
              f"{len(all_records):,} records -> {out_path.name}")

    print("\n[3/4] LOSO grid on truncated organic_hybrid features")
    recs = json.load(open(feature_paths["organic_hybrid"]))
    y = np.array([r["was_clicked"] for r in recs], dtype=int)
    groups = np.array([r["trial_id"].split("-")[0] for r in recs])
    grid = {}
    for variant in VARIANTS:
        X = build_features(recs, variant)
        res = fit_eval(X, y, groups, recs)
        grid[variant] = res
        print(f"  {variant:6s}  AUC={res['auc']:.4f}  MRR={res['mrr_at_10']:.3f}  "
              f"NDCG@1={res['ndcg_at_1']:.3f}  n={res['n_records']:,}")

    print("\n[4/4] paired stats vs published terminal-buffer grid")
    pub = json.load(open(PUBLISHED_GRID))["grid"]

    def pub_cell(buf, variant):
        return pub[f"organic_hybrid|buf{buf}|{variant}"]

    stats_out = {}
    # The headline control: M4-7 vs M1 under full-approach truncation
    a, b, _ = paired_by_pid(grid["M4-7"], grid["M1"])
    stats_out["trunc_M4-7_vs_trunc_M1"] = paired_tests(
        a, b, "M4-7 (approach-truncated)", "M1 (approach-truncated)")
    # Cost of the control: truncated M4-7 vs published buf500 M4-7
    a, b, _ = paired_by_pid(pub_cell(500, "M4-7"), grid["M4-7"])
    stats_out["buf500_M4-7_vs_trunc_M4-7"] = paired_tests(
        a, b, "M4-7 @ buf500", "M4-7 (approach-truncated)")
    # And vs buf0 (the raw legacy headline)
    a, b, _ = paired_by_pid(pub_cell(0, "M4-9"), grid["M4-7"])
    stats_out["buf0_M4-9_vs_trunc_M4-7"] = paired_tests(
        a, b, "M4-9 @ buf0 (legacy)", "M4-7 (approach-truncated)")
    # Position-absorption check under truncation: M3-7 vs M4-7
    a, b, _ = paired_by_pid(grid["M3-7"], grid["M4-7"])
    stats_out["trunc_M3-7_vs_trunc_M4-7"] = paired_tests(
        a, b, "M3-7 (approach-truncated)", "M4-7 (approach-truncated)")

    for k, v in stats_out.items():
        print(f"  {k}: dAUC={v['mean_delta_auc']:+.4f} "
              f"[{v['delta_ci_95_lo']:+.4f}, {v['delta_ci_95_hi']:+.4f}], "
              f"d_z={v['cohens_d_z']:.2f}, wilcoxon p={v['wilcoxon_p']:.2e}")

    comparison_rows = {}
    for variant in VARIANTS:
        row = {}
        for buf in [0, 200, 500, 1000]:
            c = pub_cell(buf, variant)
            row[f"buf{buf}"] = {"auc": c["auc"], "mrr_at_10": c["mrr_at_10"],
                                "ndcg_at_1": c["ndcg_at_1"],
                                "n_records": c["n_records"]}
        row["approach_truncated"] = {
            "auc": grid[variant]["auc"], "mrr_at_10": grid[variant]["mrr_at_10"],
            "ndcg_at_1": grid[variant]["ndcg_at_1"],
            "n_records": grid[variant]["n_records"]}
        comparison_rows[variant] = row

    summary = {
        "experiment": "approach-truncation ablation (deliberation-phase leakage control)",
        "generated_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "regime": "LAB",
        "rank_type": "organic_hybrid (headline grid); organic + typed truncated feature files emitted for downstream checks",
        "operational_definition": (
            "t_onset = latest pre-click local maximum of Euclidean cursor "
            "distance to the final click coordinate, with prominence >= "
            f"{PROM_PX:.0f} px and distance >= {PROX_PX:.0f} px; fallback: "
            "latest sample with distance >= pre-click median. All fixations "
            "and cursor samples at t >= t_onset excluded from every AOI's "
            "features (per-trial click_buffer_ms = t_click - t_onset through "
            "the canonical extractor)."),
        "truncation_stats": trunc_stats,
        "loso_grid_truncated_organic_hybrid": {
            v: {k2: v2 for k2, v2 in grid[v].items()} for v in VARIANTS},
        "comparison_vs_published_buffers": comparison_rows,
        "paired_stats": stats_out,
        "published_grid_source": str(PUBLISHED_GRID.relative_to(ROOT)),
        "truncated_feature_files": {
            a: str(p.relative_to(ROOT)) for a, p in feature_paths.items()},
    }
    out = OUT_DIR / "approach_truncation_ablation.json"
    out.write_text(json.dumps(summary, indent=2))
    trunc_out = OUT_DIR / "approach_truncation_trial_stats.json"
    trunc_out.write_text(json.dumps(list(trunc_info.values())))
    print(f"\nwrote {out}")
    print(f"wrote {trunc_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
