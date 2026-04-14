"""Sensitivity sweep on the NB22 four-class taxonomy approach threshold.

Question: the canonical 100 px "approach" threshold in NB22 is a single
tuning point, not a sweep. How much does the deferred-vs-evaluated-rejected
motor-signature dissociation depend on that choice?

Method:
  1. Load cursor-approach-features.json (post 2026-04-12 fixation audit).
  2. Compute per-record regression_labels using NB22 cell 5's algorithm
     (visited → max_seen passed → visited again in fixation sequence).
     Cache to avoid the ~2 min recomputation cost on re-run.
  3. Sweep approach_threshold ∈ {50, 75, 100, 125, 150, 200} px.
  4. At each threshold: label records clicked / deferred / eval-rejected /
     not_approached. Run Mann-Whitney U on K5 (retreat_dist) and K6
     (total_dwell_ms) for deferred vs eval-rejected.
  5. Report cohort sizes, gaps, and p-values as a function of threshold.

Outputs:
  scripts/output/approach_threshold_sensitivity/sweep_results.csv
  scripts/output/approach_threshold_sensitivity/regression_labels_cache.json
  scripts/output/approach_threshold_sensitivity/summary.md

Note: K7 (dwell_in_proximity_ms) is not swept because proximity radius
is baked into the feature at compute time (NB15 uses 100 px). A full K7
sweep would require regenerating cursor-approach-features.json at each
proximity threshold — out of scope for this script.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    load_fixations,
    get_trial_meta,
    load_mouse_events,
    interpolate_scroll,
    extract_serp_results,
    result_band_tops,
    assign_fixation_to_position,
)

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
FEATURES = ROOT / "AdSERP/data/cursor-approach-features.json"
OUT = ROOT / "scripts/output/approach_threshold_sensitivity"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "regression_labels_cache.json"

THRESHOLDS = [50, 75, 100, 125, 150, 200]


def compute_regression_labels(raw):
    """Reproduce NB22 cell 5 — per-record boolean: was this (trial, position)
    regressed to? Visited → max_seen advanced past → visited again."""
    trial_records = defaultdict(list)
    for i, r in enumerate(raw):
        trial_records[r["trial_id"]].append((i, r["position"]))

    labels = np.zeros(len(raw), dtype=bool)
    skipped = 0
    for n_done, (tid, recs) in enumerate(trial_records.items()):
        if n_done % 500 == 0:
            print(f"  {n_done}/{len(trial_records)} trials...")
        try:
            fixations_t = load_fixations(tid)
            meta_t = get_trial_meta(tid)
            mouse_t = load_mouse_events(tid)
        except Exception:
            skipped += 1
            continue
        if fixations_t is None or meta_t is None or mouse_t is None or len(fixations_t) < 5:
            skipped += 1
            continue

        doc_h_t, scr_h_t, _ = meta_t
        serp_t = extract_serp_results(tid)
        n_res_t = len(serp_t) if serp_t else 10
        tops_t = result_band_tops(n_res_t, doc_h_t)

        _, scrolls_t, _ = mouse_t
        s_ts = [s[0] for s in scrolls_t] if scrolls_t else [fixations_t[0]["t"]]
        s_ys = [s[1] for s in scrolls_t] if scrolls_t else [0]

        # Fixation position sequence
        pos_seq = []
        for fix in fixations_t:
            py = fix["y"]  # FPOGY is page-space (2026-04-12 audit)
            p = assign_fixation_to_position(py, tops_t, n_res_t)
            if p >= 0:
                pos_seq.append(p)

        max_seen = -1
        visited = set()
        regressed = set()
        for p in pos_seq:
            if p in visited and p < max_seen:
                regressed.add(p)
            visited.add(p)
            max_seen = max(max_seen, p)

        for idx, pos in recs:
            if pos in regressed:
                labels[idx] = True
    print(f"  processed {len(trial_records)} trials, skipped {skipped}")
    return labels


def main():
    print(f"loading {FEATURES}")
    raw = json.load(open(FEATURES))
    n = len(raw)
    print(f"records: {n}")

    if CACHE.exists():
        print(f"loading cached regression labels from {CACHE}")
        cached = json.load(open(CACHE))
        regression_labels = np.array(cached, dtype=bool)
        if len(regression_labels) != n:
            print(f"  cache size mismatch ({len(regression_labels)} vs {n}); recomputing")
            regression_labels = compute_regression_labels(raw)
            json.dump(regression_labels.tolist(), open(CACHE, "w"))
    else:
        print("computing regression labels (expensive, ~2 min)...")
        regression_labels = compute_regression_labels(raw)
        json.dump(regression_labels.tolist(), open(CACHE, "w"))
        print(f"  cached to {CACHE}")

    clicked = np.array([r["was_clicked"] for r in raw])
    min_dist = np.array([r["min_dist"] for r in raw], dtype=float)
    retreat_dist = np.array([r["retreat_dist"] for r in raw], dtype=float)
    total_dwell = np.array([r["total_dwell_ms"] for r in raw], dtype=float)
    dwell_prox = np.array([r["dwell_in_proximity_ms"] for r in raw], dtype=float)

    print("\n=== Sensitivity sweep ===\n")
    header = (
        f"{'thr':>4s} {'N_def':>6s} {'N_rej':>6s} {'N_cli':>6s} {'N_na':>6s}  "
        f"{'K5 def':>7s} {'K5 rej':>7s} {'K5 p':>10s}  "
        f"{'K6 def':>8s} {'K6 rej':>8s} {'K6 p':>10s}  "
        f"{'K7 def':>8s} {'K7 rej':>8s} {'K7 p':>10s}"
    )
    print(header)
    print("-" * len(header))

    rows = []
    for thr in THRESHOLDS:
        approached = min_dist < thr
        labels = np.full(n, "", dtype="U25")
        labels[clicked] = "clicked"
        labels[~clicked & approached & regression_labels] = "deferred"
        labels[~clicked & approached & ~regression_labels] = "evaluated_rejected"
        labels[~clicked & ~approached] = "not_approached"
        counts = Counter(labels)

        def_mask = labels == "deferred"
        rej_mask = labels == "evaluated_rejected"

        k5_def = retreat_dist[def_mask]
        k5_rej = retreat_dist[rej_mask]
        k6_def = total_dwell[def_mask]
        k6_rej = total_dwell[rej_mask]
        k7_def = dwell_prox[def_mask]
        k7_rej = dwell_prox[rej_mask]

        def _mw(a, b):
            if len(a) < 2 or len(b) < 2:
                return float("nan"), float("nan"), float("nan")
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            return float(np.median(a)), float(np.median(b)), float(p)

        k5_mdef, k5_mrej, k5_p = _mw(k5_def, k5_rej)
        k6_mdef, k6_mrej, k6_p = _mw(k6_def, k6_rej)
        k7_mdef, k7_mrej, k7_p = _mw(k7_def, k7_rej)

        def _fp(p):
            return "nan" if not np.isfinite(p) else f"{p:.2e}"

        print(
            f"{thr:>4d} {counts['deferred']:>6d} {counts['evaluated_rejected']:>6d} "
            f"{counts['clicked']:>6d} {counts['not_approached']:>6d}  "
            f"{k5_mdef:>7.1f} {k5_mrej:>7.1f} {_fp(k5_p):>10s}  "
            f"{k6_mdef:>8.0f} {k6_mrej:>8.0f} {_fp(k6_p):>10s}  "
            f"{k7_mdef:>8.0f} {k7_mrej:>8.0f} {_fp(k7_p):>10s}"
        )
        rows.append({
            "threshold_px": thr,
            "n_deferred": int(counts["deferred"]),
            "n_evaluated_rejected": int(counts["evaluated_rejected"]),
            "n_clicked": int(counts["clicked"]),
            "n_not_approached": int(counts["not_approached"]),
            "K5_retreat_def_median": k5_mdef,
            "K5_retreat_rej_median": k5_mrej,
            "K5_p": k5_p,
            "K6_total_dwell_def_median": k6_mdef,
            "K6_total_dwell_rej_median": k6_mrej,
            "K6_p": k6_p,
            "K7_dwell_prox_def_median": k7_mdef,
            "K7_dwell_prox_rej_median": k7_mrej,
            "K7_p": k7_p,
        })

    import csv
    with open(OUT / "sweep_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT / 'sweep_results.csv'}")

    # Write a markdown summary for inclusion in methodological-threats.md §9 if desired
    with open(OUT / "summary.md", "w") as f:
        f.write("# Approach-threshold sensitivity sweep — NB22 four-class taxonomy\n\n")
        f.write("**Question.** The canonical NB22 `approached` flag is `min_dist < 100 px`.\n")
        f.write("How much does the deferred-vs-evaluated-rejected motor-signature dissociation\n")
        f.write("depend on that single tuning point?\n\n")
        f.write("**Method.** Sweep `approach_threshold` over {50, 75, 100, 125, 150, 200} px,\n")
        f.write("holding the per-record regression labels (NB22 cell 5 algorithm) and motor\n")
        f.write("features (K5 retreat_dist, K6 total_dwell_ms, K7 dwell_in_proximity_ms) fixed.\n\n")
        f.write("**Note.** K7 proximity dwell is computed against a 100 px proximity radius\n")
        f.write("baked into `cursor-approach-features.json` at NB15 compute time. The K7 sweep\n")
        f.write("therefore reflects only the re-labeling of records into deferred/rejected sets\n")
        f.write("at each approach threshold, not a re-computation of proximity at that threshold.\n")
        f.write("A full K7 sweep would require regenerating cursor-approach-features.json at\n")
        f.write("each proximity radius and is out of scope.\n\n")
        f.write("| Threshold (px) | N deferred | N eval-rej | N clicked | N not-approached | K5 def / rej (px) | K5 *p* | K6 def / rej (ms) | K6 *p* | K7 def / rej (ms) | K7 *p* |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            k5p = "nan" if not np.isfinite(r["K5_p"]) else f"{r['K5_p']:.2e}"
            k6p = "nan" if not np.isfinite(r["K6_p"]) else f"{r['K6_p']:.2e}"
            k7p = "nan" if not np.isfinite(r["K7_p"]) else f"{r['K7_p']:.2e}"
            f.write(
                f"| {r['threshold_px']} | {r['n_deferred']} | {r['n_evaluated_rejected']} | "
                f"{r['n_clicked']} | {r['n_not_approached']} | "
                f"{r['K5_retreat_def_median']:.1f} / {r['K5_retreat_rej_median']:.1f} | {k5p} | "
                f"{r['K6_total_dwell_def_median']:.0f} / {r['K6_total_dwell_rej_median']:.0f} | {k6p} | "
                f"{r['K7_dwell_prox_def_median']:.0f} / {r['K7_dwell_prox_rej_median']:.0f} | {k7p} |\n"
            )
        f.write("\n")
    print(f"wrote {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
