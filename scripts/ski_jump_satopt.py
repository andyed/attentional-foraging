"""Ski-jump click distribution stratified by satisficer/optimizer.

Re-tests the §0 findings.md claim ("optimizers are 1.56× more likely
to click at positions 9–10 than satisficers, 14.5% vs 9.3%") on
post-coord-fix data, and also runs the same split inside cohort A
(plain-top + ≥10 organic + reached rank 9, n=131) where the rank-9
uptick survives.

Outputs:
  scripts/output/ski_jump_satopt/full_corpus.csv  (click % by rank × tercile, full corpus)
  scripts/output/ski_jump_satopt/cohort_A.csv     (click % by rank × tercile, cohort A)
  scripts/output/ski_jump_satopt/summary.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    absolute_to_organic_rank,
    absolute_rank_band_tops,
    organic_rank_band_tops,
    count_organic_ranks,
)

OUT = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/ski_jump_satopt")
OUT.mkdir(parents=True, exist_ok=True)


def participant_regression_rate(trials_by_pid):
    """For each participant, return fraction of trials with at least one
    backward scroll (high-water-mark drop > 30px), per NB10 convention."""
    out = {}
    for pid, tids in trials_by_pid.items():
        n_with_reg = 0
        n_total = 0
        for tid in tids:
            try:
                _, scrolls, _ = load_mouse_events(tid)
            except Exception:
                continue
            n_total += 1
            if not scrolls:
                continue
            ys = [y for _, y in scrolls]
            hwm = ys[0]
            for y in ys:
                if hwm - y > 30:
                    n_with_reg += 1
                    break
                if y > hwm:
                    hwm = y
        if n_total > 0:
            out[pid] = n_with_reg / n_total
    return out


def click_organic_rank(click_y, org_tops):
    pos = -1
    for i, top in enumerate(org_tops):
        if click_y >= top:
            pos = i
        else:
            break
    return pos if 0 <= pos < len(org_tops) else None


def click_absolute_rank(click_y, abs_tops, n_abs):
    pos = -1
    for i, top in enumerate(abs_tops):
        if click_y >= top:
            pos = i
        else:
            break
    return pos if 0 <= pos < n_abs else None


def main():
    tids = sorted(get_trial_ids())
    print(f"trials: {len(tids)}")

    # 1) participant regression-rate terciles
    by_pid = defaultdict(list)
    for tid in tids:
        by_pid[tid.split("-")[0]].append(tid)
    reg_rate = participant_regression_rate(by_pid)
    rates = sorted(reg_rate.values())
    n = len(rates)
    t1 = rates[n // 3]
    t2 = rates[2 * n // 3]
    print(f"regression-rate tercile boundaries: t1 = {t1:.3f}, t2 = {t2:.3f}")
    pid_tier = {}
    for pid, r in reg_rate.items():
        if r <= t1:
            pid_tier[pid] = "satisficer"
        elif r <= t2:
            pid_tier[pid] = "mixed"
        else:
            pid_tier[pid] = "optimizer"
    counts = {t: sum(1 for v in pid_tier.values() if v == t) for t in ("satisficer", "mixed", "optimizer")}
    print(f"participant tier counts: {counts}")

    # 2) per-trial state
    rows = []
    for tid in tids:
        pid = tid.split("-")[0]
        tier = pid_tier.get(pid)
        if tier is None:
            continue
        doc_h, scr_h, _ = get_trial_meta(tid)
        if not doc_h or not scr_h:
            continue
        try:
            _, scrolls, clicks = load_mouse_events(tid)
        except Exception:
            continue
        if not clicks:
            continue
        mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
        if not mapping:
            continue
        n_abs = max(mapping.keys()) + 1
        abs_tops = absolute_rank_band_tops(n_abs, doc_h)
        org_tops = organic_rank_band_tops(tid, doc_height=doc_h)
        n_org = len(org_tops)

        click_y = clicks[0][2]
        click_abs = click_absolute_rank(click_y, abs_tops, n_abs)
        click_org = mapping.get(click_abs) if click_abs is not None else None

        # Cohort A flags
        first_abs_organic = (mapping.get(0) is not None)  # plain_top
        max_scroll = max((s[1] for s in scrolls), default=0)
        viewport_bottom = max_scroll + scr_h
        reached_rank9 = False
        if n_org >= 10:
            rank9_top = org_tops[9]
            reached_rank9 = viewport_bottom >= rank9_top

        rows.append({
            "tid": tid,
            "pid": pid,
            "tier": tier,
            "n_abs": n_abs,
            "n_org": n_org,
            "click_abs": click_abs,
            "click_org": click_org,
            "plain_top": first_abs_organic,
            "reached_rank9": reached_rank9,
        })

    df = pl.DataFrame(rows)
    print(f"trials with first click: {df.height}")

    # ── A. Full-corpus click-share by absolute rank, stratified ──
    # The original §0 finding was on absolute-rank positions 9-10.
    print("\n=== Full corpus: click share at positions 9-10 by tier ===")
    fullcorpus = []
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = df.filter(pl.col("tier") == tier)
        n = sub.height
        for r in range(12):
            n_at = sub.filter(pl.col("click_abs") == r).height
            fullcorpus.append({
                "scope": "full_corpus",
                "tier": tier,
                "rank_type": "absolute",
                "rank": r,
                "n_clicks": n_at,
                "n_trials_in_tier": n,
                "click_share": round(n_at / n, 4) if n else None,
            })
        # Pos 9-10 share
        n_910 = sub.filter(pl.col("click_abs").is_in([9, 10])).height
        share = n_910 / n if n else 0
        print(f"  {tier:>10s}  n={n}  pos 9-10 clicks={n_910}  share={share:.4f}")

    # Same by organic rank
    print("\n=== Full corpus: click share at organic ranks 8-9 by tier ===")
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = df.filter(pl.col("tier") == tier)
        n = sub.filter(pl.col("click_org").is_not_null()).height
        for r in range(11):
            n_at = sub.filter(pl.col("click_org") == r).height
            fullcorpus.append({
                "scope": "full_corpus",
                "tier": tier,
                "rank_type": "organic",
                "rank": r,
                "n_clicks": n_at,
                "n_trials_in_tier": n,
                "click_share": round(n_at / n, 4) if n else None,
            })
        n_89 = sub.filter(pl.col("click_org").is_in([8, 9])).height
        share = n_89 / n if n else 0
        print(f"  {tier:>10s}  n={n}  org 8-9 clicks={n_89}  share={share:.4f}")

    pl.DataFrame(fullcorpus).write_csv(OUT / "full_corpus.csv")

    # ── B. Cohort A: plain-top + ≥10 organic + reached rank 9 ──
    cohort_a = df.filter(
        pl.col("plain_top") & (pl.col("n_org") >= 10) & pl.col("reached_rank9")
    )
    print(f"\n=== Cohort A: n={cohort_a.height} ===")

    cohort_rows = []
    for tier in ("satisficer", "mixed", "optimizer"):
        sub = cohort_a.filter(pl.col("tier") == tier)
        n = sub.height
        n_with_org = sub.filter(pl.col("click_org").is_not_null()).height
        for r in range(10):
            n_at = sub.filter(pl.col("click_org") == r).height
            cohort_rows.append({
                "scope": "cohort_A",
                "tier": tier,
                "rank": r,
                "n_clicks": n_at,
                "n_trials_in_tier": n,
                "click_share": round(n_at / n, 4) if n else None,
            })
        # Show distribution
        click_counts = {r: sub.filter(pl.col("click_org") == r).height for r in range(10)}
        print(f"  {tier:>10s}  n={n}  org rank dist: " +
              "  ".join(f"{r}={click_counts[r]}" for r in range(10)))
        if n > 0:
            r9 = click_counts[9]
            r8 = click_counts[8]
            print(f"               rank 8 share: {r8/n:.3f}, rank 9 share: {r9/n:.3f}")
    pl.DataFrame(cohort_rows).write_csv(OUT / "cohort_A.csv")

    # Summary
    summary = {
        "tier_boundaries_regression_rate": {"t1": float(t1), "t2": float(t2)},
        "participant_counts": counts,
        "full_corpus_n": df.height,
        "cohort_A_n": cohort_a.height,
        "cohort_A_n_by_tier": {
            t: cohort_a.filter(pl.col("tier") == t).height
            for t in ("satisficer", "mixed", "optimizer")
        },
    }
    # Compute the headline ratio (full corpus, abs rank 9-10)
    n_sat = df.filter(pl.col("tier") == "satisficer").height
    n_opt = df.filter(pl.col("tier") == "optimizer").height
    sat_910 = df.filter((pl.col("tier") == "satisficer") & pl.col("click_abs").is_in([9, 10])).height
    opt_910 = df.filter((pl.col("tier") == "optimizer") & pl.col("click_abs").is_in([9, 10])).height
    sat_share = sat_910 / n_sat if n_sat else None
    opt_share = opt_910 / n_opt if n_opt else None
    summary["full_corpus_pos910_abs"] = {
        "satisficer_share": sat_share,
        "optimizer_share": opt_share,
        "ratio_opt_over_sat": (opt_share / sat_share) if (sat_share and opt_share) else None,
    }
    # Same for organic 8-9
    sat_org = df.filter(pl.col("tier") == "satisficer").filter(pl.col("click_org").is_not_null()).height
    opt_org = df.filter(pl.col("tier") == "optimizer").filter(pl.col("click_org").is_not_null()).height
    sat_89 = df.filter((pl.col("tier") == "satisficer") & pl.col("click_org").is_in([8, 9])).height
    opt_89 = df.filter((pl.col("tier") == "optimizer") & pl.col("click_org").is_in([8, 9])).height
    sat_org_share = sat_89 / sat_org if sat_org else None
    opt_org_share = opt_89 / opt_org if opt_org else None
    summary["full_corpus_org89"] = {
        "satisficer_share": sat_org_share,
        "optimizer_share": opt_org_share,
        "ratio_opt_over_sat": (opt_org_share / sat_org_share) if (sat_org_share and opt_org_share) else None,
    }

    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nSummary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
