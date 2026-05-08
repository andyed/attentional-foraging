"""Test the 'occasionally lazy peeps at scale' hypothesis for the
cohort-A rank-9 uptick.

If the ski-jump terminal spike is just lazy / impatient clicking
aggregated across users (rather than a cost/reward cognitive
collapse), then within cohort A the 4 rank-9 click trials should look
like:
  - participant-concentrated (1-2 users, maybe with repeat behavior)
  - low engagement: short TFT, few fixations, fast time-to-click
  - no reading effort signature (no LHIPA dip, no extra fixations)

Compare cohort A rank-9 clickers to cohort A everybody-else clickers
on the same engagement metrics.

Outputs:
  scripts/output/ski_jump_lazy/cohort_a_rank9_profile.csv
  scripts/output/ski_jump_lazy/summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import Counter

import numpy as np

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    load_fixations,
    absolute_to_organic_rank,
    organic_rank_band_tops,
)

OUT = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/ski_jump_lazy")
OUT.mkdir(parents=True, exist_ok=True)

# Load LHIPA cache
LHIPA_PATH = Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2/lhipa_per_trial.json")
with open(LHIPA_PATH) as f:
    lhipa_cache = json.load(f)


def click_to_org_rank(click_y, org_tops):
    pos = -1
    for i, top in enumerate(org_tops):
        if click_y >= top:
            pos = i
        else:
            break
    return pos if 0 <= pos < len(org_tops) else None


def trial_metrics(tid):
    """Per-trial engagement profile."""
    doc_h, scr_h, _ = get_trial_meta(tid)
    if not doc_h:
        return None
    try:
        events, scrolls, clicks = load_mouse_events(tid)
    except Exception:
        return None
    if not clicks:
        return None
    mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
    if not mapping:
        return None
    org_tops = organic_rank_band_tops(tid, doc_height=doc_h)
    if len(org_tops) < 10:
        return None

    # plain_top filter
    plain_top = (mapping.get(0) is not None)
    if not plain_top:
        return None

    # reached rank 9 filter
    max_scroll = max((s[1] for s in scrolls), default=0)
    viewport_bottom = max_scroll + (scr_h or 0)
    if viewport_bottom < org_tops[9]:
        return None

    click_t, _, click_y = clicks[0]
    click_org = click_to_org_rank(click_y, org_tops)
    if click_org is None:
        return None  # ad slot click

    # Time-to-click: from first event to click event
    first_t = min(e[0] for e in events) if events else click_t
    ttc_s = (click_t - first_t) / 1000.0

    fixes = load_fixations(tid)
    n_fix = len(fixes)
    tft_ms = sum(f["d"] for f in fixes)
    mean_fix_dur = tft_ms / n_fix if n_fix else 0

    # Trial regression
    had_regression = False
    if scrolls:
        ys = [y for _, y in scrolls]
        hwm = ys[0]
        for y in ys:
            if hwm - y > 30:
                had_regression = True
                break
            if y > hwm:
                hwm = y

    lhipa = lhipa_cache.get(tid, {}).get("lhipa")

    return {
        "tid": tid,
        "pid": tid.split("-")[0],
        "click_org_rank": click_org,
        "ttc_s": ttc_s,
        "n_fixations": n_fix,
        "tft_s": tft_ms / 1000.0,
        "mean_fix_dur_ms": mean_fix_dur,
        "had_regression": had_regression,
        "max_scroll": max_scroll,
        "lhipa": lhipa,
    }


def main():
    tids = sorted(get_trial_ids())
    print(f"Scanning {len(tids)} trials for cohort A...")

    cohort = []
    for tid in tids:
        m = trial_metrics(tid)
        if m is not None:
            cohort.append(m)

    print(f"Cohort A: {len(cohort)} trials\n")

    # Split rank-9 clickers vs everybody-else
    rank9 = [t for t in cohort if t["click_org_rank"] == 9]
    other = [t for t in cohort if t["click_org_rank"] != 9]

    print(f"Rank-9 click trials: {len(rank9)}")
    print(f"  Trial IDs: {[t['tid'] for t in rank9]}")
    print(f"  Participants: {Counter(t['pid'] for t in rank9)}")
    print()

    # Engagement profile comparison
    metrics = [
        ("ttc_s", "Time-to-click (s)"),
        ("n_fixations", "Fixation count"),
        ("tft_s", "Total fixation time (s)"),
        ("mean_fix_dur_ms", "Mean fix duration (ms)"),
        ("max_scroll", "Max scroll Y (px)"),
        ("had_regression", "Has regression"),
        ("lhipa", "LHIPA"),
    ]

    print(f"{'Metric':>30s}  {'rank-9 (n=' + str(len(rank9)) + ')':>20s}  {'other cohort A':>20s}")
    print("-" * 80)
    for key, label in metrics:
        r9_vals = [t[key] for t in rank9 if t[key] is not None]
        ot_vals = [t[key] for t in other if t[key] is not None]
        if not r9_vals or not ot_vals:
            print(f"{label:>30s}  {'(no data)':>20s}  {'(no data)':>20s}")
            continue
        if isinstance(r9_vals[0], bool):
            r9_summary = f"{sum(r9_vals)}/{len(r9_vals)} ({np.mean(r9_vals)*100:.0f}%)"
            ot_summary = f"{sum(ot_vals)}/{len(ot_vals)} ({np.mean(ot_vals)*100:.0f}%)"
        else:
            r9_summary = f"med={np.median(r9_vals):.1f}"
            ot_summary = f"med={np.median(ot_vals):.1f}"
        print(f"{label:>30s}  {r9_summary:>20s}  {ot_summary:>20s}")

    # Per-trial detail for rank-9 clickers
    print("\n=== Per-trial detail for rank-9 cohort-A clickers ===")
    print(f"{'tid':>14s}  {'pid':>6s}  {'ttc_s':>7s}  {'n_fix':>6s}  {'tft':>6s}  {'reg':>4s}  {'lhipa':>8s}  {'max_scroll':>10s}")
    for t in rank9:
        lh = f"{t['lhipa']:.4f}" if t['lhipa'] is not None else "n/a"
        print(f"{t['tid']:>14s}  {t['pid']:>6s}  {t['ttc_s']:>7.1f}  {t['n_fixations']:>6d}  "
              f"{t['tft_s']:>6.1f}  {str(t['had_regression']):>4s}  {lh:>8s}  {t['max_scroll']:>10.0f}")

    # Median rank-0 (deepest "wrong"clickers in cohort A) for comparison
    rank0 = [t for t in cohort if t["click_org_rank"] == 0]
    print(f"\nFor reference — rank-0 clickers in cohort A: n={len(rank0)}")
    for key, label in metrics:
        r0_vals = [t[key] for t in rank0 if t[key] is not None]
        if not r0_vals:
            continue
        if isinstance(r0_vals[0], bool):
            print(f"  {label}: {sum(r0_vals)}/{len(r0_vals)} ({np.mean(r0_vals)*100:.0f}%)")
        else:
            print(f"  {label}: med={np.median(r0_vals):.1f}")

    # Save per-trial CSV
    import csv
    with open(OUT / "cohort_a_rank9_profile.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rank9[0].keys()) if rank9 else ['tid'])
        if rank9:
            w.writeheader()
            for row in rank9:
                w.writerow(row)

    # Summary
    summary = {
        "cohort_a_n": len(cohort),
        "rank9_clickers": {
            "n": len(rank9),
            "n_distinct_participants": len(set(t["pid"] for t in rank9)),
            "participant_breakdown": dict(Counter(t["pid"] for t in rank9)),
            "median_ttc_s": float(np.median([t["ttc_s"] for t in rank9])) if rank9 else None,
            "median_n_fix": float(np.median([t["n_fixations"] for t in rank9])) if rank9 else None,
            "median_tft_s": float(np.median([t["tft_s"] for t in rank9])) if rank9 else None,
            "had_regression_pct": float(np.mean([t["had_regression"] for t in rank9]) * 100) if rank9 else None,
        },
        "other_cohort_a": {
            "n": len(other),
            "median_ttc_s": float(np.median([t["ttc_s"] for t in other])) if other else None,
            "median_n_fix": float(np.median([t["n_fixations"] for t in other])) if other else None,
            "median_tft_s": float(np.median([t["tft_s"] for t in other])) if other else None,
            "had_regression_pct": float(np.mean([t["had_regression"] for t in other]) * 100) if other else None,
        },
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {OUT}/summary.json")


if __name__ == "__main__":
    main()
