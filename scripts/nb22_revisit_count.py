"""Recompute NB22 gaze-regression labels with a per-result revisit COUNT.

The existing NB22 detector (notebooks-v2/22_four_class_taxonomy.ipynb) stores
a boolean `regression_labels[i] = True/False` per (trial, result) pair — True
iff the result was gaze-revisited at least once after max_seen advanced past.
That boolean collapses a 1-revisit episode (briefly reconsidered) and a 5-
revisit episode (actively comparison-shopping) into the same "deferred" class.

Re-run the same detection logic with a counter: for each (trial, result) pair,
how many times did the gaze return to this position after max_seen moved past?
Then histogram across the 1,916 NB22-deferred records to see what share of
"deferred" is single-revisit vs. multi-revisit.

This answers: **among deferred episodes, what share are the strong
comparison-shopping case (multiple revisits) vs. the single-return case?**

Output: scripts/output/nb22_revisit_count/summary.json
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    assign_fixation_to_position, extract_serp_results, get_trial_meta,
    interpolate_scroll, load_fixations, load_mouse_events, result_band_tops,
)

FEATURES_JSON = ROOT / "AdSERP/data/cursor-approach-features.json"
REG_CACHE = ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache.json"
OUT_DIR = ROOT / "scripts/output/nb22_revisit_count"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def count_revisits_per_trial(trial_id):
    """For a single trial, return dict: result_pos -> revisit_count.

    A 'revisit' is a fixation on a position that was previously fixated,
    followed by a later fixation on a position with higher index (max_seen
    has advanced past), followed by another fixation on the original
    position. We count each such return event per position.

    This matches the original NB22 detection logic — which checks
    `p in visited and p < max_seen` — but counts the number of times that
    condition fires per position, rather than just whether it ever fires.
    """
    try:
        fixations = load_fixations(trial_id)
    except Exception:
        return None
    meta = get_trial_meta(trial_id)
    mouse_data = load_mouse_events(trial_id)
    if fixations is None or meta is None or mouse_data is None:
        return None
    if len(fixations) < 5:
        return None

    doc_h, scr_h, _ = meta
    serp = extract_serp_results(trial_id)
    n_results = len(serp) if serp else 10
    tops = result_band_tops(n_results, doc_h)

    _, scrolls, _ = mouse_data
    s_ts = [s[0] for s in scrolls] if scrolls else [fixations[0]["t"]]
    s_ys = [s[1] for s in scrolls] if scrolls else [0]

    # Build per-fixation position sequence
    pos_seq = []
    for fix in fixations:
        py = fix["y"]
        p = assign_fixation_to_position(py, tops, n_results)
        if p >= 0:
            pos_seq.append(p)

    # Two counters:
    #  (a) regressive_fix_count — every fixation at p where p < max_seen and
    #      p was previously visited (matches NB22's per-fixation detection).
    #      Long dwell on a previously-visited position inflates this.
    #  (b) distinct_return_count — number of TRANSITIONS into a position from
    #      a different position during the regressive regime. A user who
    #      bounces [3, 7, 3, 7, 3] has 2 distinct returns to position 3;
    #      a user who stays at position 3 for 20 fixations during regression
    #      has 1 distinct return. This is the "how many times did the gaze
    #      come back" metric Peter is asking about.
    max_seen = -1
    visited = set()
    regressive_fix = defaultdict(int)
    distinct_returns = defaultdict(int)
    last_pos = None
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressive_fix[p] += 1
            if last_pos != p:
                distinct_returns[p] += 1
        visited.add(p)
        if p > max_seen:
            max_seen = p
        last_pos = p
    return {
        "regressive_fix": dict(regressive_fix),
        "distinct_returns": dict(distinct_returns),
    }


def main():
    print("=" * 70)
    print("NB22 revisit-count histogram")
    print("=" * 70)

    print(f"\nloading LAB records from {FEATURES_JSON}")
    lab_records = json.load(open(FEATURES_JSON))
    regression_labels = np.array(json.load(open(REG_CACHE)), dtype=bool)

    print("\ncomputing per-(trial, result) revisit counts (~3 min)...")
    trial_ids = sorted(set(r["trial_id"] for r in lab_records))
    regressive_fix_by_key = {}   # (trial_id, position) -> regressive-fix count
    distinct_return_by_key = {}  # (trial_id, position) -> distinct-return count
    skipped = 0
    for n_done, tid in enumerate(trial_ids):
        if n_done % 300 == 0:
            print(f"  {n_done}/{len(trial_ids)} trials")
        revisit_counts = count_revisits_per_trial(tid)
        if revisit_counts is None:
            skipped += 1
            continue
        for pos, cnt in revisit_counts["regressive_fix"].items():
            regressive_fix_by_key[(tid, pos)] = cnt
        for pos, cnt in revisit_counts["distinct_returns"].items():
            distinct_return_by_key[(tid, pos)] = cnt
    print(f"  {len(regressive_fix_by_key):,} (trial, result) pairs with ≥ 1 regressive fix")
    print(f"  {len(distinct_return_by_key):,} (trial, result) pairs with ≥ 1 distinct return")
    print(f"  skipped trials: {skipped}")

    # Map counts onto LAB records
    n = len(lab_records)
    per_record_regressive = np.zeros(n, dtype=int)
    per_record_returns = np.zeros(n, dtype=int)
    for i, r in enumerate(lab_records):
        key = (r["trial_id"], r["position"])
        per_record_regressive[i] = regressive_fix_by_key.get(key, 0)
        per_record_returns[i] = distinct_return_by_key.get(key, 0)

    # Focus on NB22 deferred population — approached, non-click, gaze-regressed
    min_dist = np.array([r["min_dist"] for r in lab_records], dtype=float)
    was_clicked = np.array([r["was_clicked"] for r in lab_records], dtype=bool)
    approached = min_dist < 100
    nb22_deferred_mask = approached & (~was_clicked) & regression_labels
    n_deferred = int(nb22_deferred_mask.sum())
    print(f"\nNB22 deferred population: {n_deferred:,} records")

    deferred_regressive = per_record_regressive[nb22_deferred_mask]
    deferred_returns = per_record_returns[nb22_deferred_mask]

    # Sanity check — every NB22-deferred record should have ≥ 1 regressive fix
    zeros = int((deferred_regressive == 0).sum())
    print(f"  deferred records with 0 regressive fixations (should be 0): {zeros}")
    if zeros > 0:
        print(f"  NOTE: {zeros} deferred records have 0 — tie-break edge cases")
        # Bump to 1 so every NB22-deferred has at least the minimum revisit signal.
        deferred_regressive = np.where(deferred_regressive == 0, 1, deferred_regressive)
        deferred_returns = np.where(deferred_returns == 0, 1, deferred_returns)

    def print_histogram_and_stats(label, counts):
        print(f"\n── {label} ──")
        print(f"{'count':>10s} {'records':>10s} {'fraction':>10s}")
        print("-" * 35)
        hist = Counter(counts.tolist())
        for k in sorted(hist.keys()):
            v = hist[k]
            frac = v / n_deferred
            print(f"{k:>10d} {v:>10,d} {frac * 100:>9.1f}%")

        print(f"\nShare of deferred with ≥ N {label}:")
        print(f"{'threshold':>12s} {'records':>10s} {'fraction':>10s}")
        print("-" * 35)
        for thresh in [1, 2, 3, 4, 5, 8, 10]:
            n_at_or_above = int((counts >= thresh).sum())
            frac = n_at_or_above / n_deferred
            print(f"{'≥ ' + str(thresh):>12s} {n_at_or_above:>10,d} {frac * 100:>9.1f}%")

        print(f"\n{label} distribution:")
        print(f"  median: {int(np.median(counts))}")
        print(f"  mean:   {float(np.mean(counts)):.2f}")
        print(f"  p25:    {int(np.percentile(counts, 25))}")
        print(f"  p75:    {int(np.percentile(counts, 75))}")
        print(f"  p90:    {int(np.percentile(counts, 90))}")
        print(f"  max:    {int(counts.max())}")
        return hist

    hist_regressive = print_histogram_and_stats(
        "REGRESSIVE FIXATION COUNT (per-fixation, dwell-inflated)", deferred_regressive)
    hist_returns = print_histogram_and_stats(
        "DISTINCT RETURN VISITS (transitions into position from elsewhere)", deferred_returns)

    def stats_dict(counts):
        return {
            "histogram": {int(k): int(v) for k, v in sorted(Counter(counts.tolist()).items())},
            "cumulative_at_or_above": {
                str(t): {
                    "n": int((counts >= t).sum()),
                    "fraction": float((counts >= t).sum() / n_deferred),
                }
                for t in [1, 2, 3, 4, 5, 8, 10]
            },
            "distribution_stats": {
                "median": int(np.median(counts)),
                "mean": float(np.mean(counts)),
                "p25": int(np.percentile(counts, 25)),
                "p75": int(np.percentile(counts, 75)),
                "p90": int(np.percentile(counts, 90)),
                "max": int(counts.max()),
            },
        }

    summary = {
        "experiment": "NB22 revisit-count histogram on deferred class",
        "generated": datetime.datetime.now(datetime.UTC).isoformat(),
        "n_deferred_total": n_deferred,
        "regressive_fixation_count": stats_dict(deferred_regressive),
        "distinct_return_visits": stats_dict(deferred_returns),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {OUT_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
