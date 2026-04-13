"""Rank-10 ski jump: on homogeneous 10-organic SERPs, conditional on
reaching the bottom, what fraction of users click result 10 vs regress/refine?

Cohort filters (most-restrictive → least):
  A) plain_top (no ad at top), exactly 10 organic results, user scrolled
     far enough that rank 9's band-top came into view.
  B) plain_top, 10+ organic, reached rank 9.
  C) any cohort, reached rank 9.

For each cohort, report:
  - n_trials
  - n_clicks (any organic click)
  - click rate by organic rank (classic ski jump)
  - 'regress' rate = n_trials_with_no_click_after_reaching_bottom / n_trials
  - terminal rate = p(click rank 9 | reached rank 9)
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict
import json

sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))
from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    absolute_to_organic_rank,
)

OUT = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/ski_jump_rank10")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    tids = get_trial_ids()
    print(f"trials: {len(tids)}")

    # Precompute per-trial state in a single pass to avoid repeated XML parsing
    trials = []
    for i, tid in enumerate(tids):
        if i % 500 == 0:
            print(f"  processed {i}/{len(tids)}")
        doc_h, scr_h, _ = get_trial_meta(tid)
        if not doc_h or not scr_h:
            continue

        mapping = absolute_to_organic_rank(tid, doc_height=doc_h)
        if not mapping:
            continue

        # Identify ad vs organic slots; derive n_organic and band tops per organic rank
        org_tops = []  # list of (organic_rank, band_top_y)
        first_abs_is_ad = None
        for abs_rank in sorted(mapping):
            org_rank = mapping[abs_rank]
            if first_abs_is_ad is None:
                first_abs_is_ad = org_rank is None
        # Build band tops using mapping structure (approximation — we use
        # vertical ordering). We'll rely on a proxy: the organic-rank
        # assignment already maps to positions; to get tops, we'd need
        # result_bands. For the rank-10 question, all we need is "did the
        # user scroll deep enough to see rank 9?"
        # Use the band-top of the absolute rank that corresponds to organic 9.
        n_organic = sum(1 for v in mapping.values() if v is not None)

        # If the trial has fewer than 10 organic results, skip (can't be
        # a rank-10 ski jump).
        if n_organic < 10:
            continue

        # Load scroll+clicks
        try:
            _, scrolls, clicks = load_mouse_events(tid)
        except Exception:
            continue

        # Max scroll reached
        max_scroll = 0
        if scrolls:
            max_scroll = max(y for _, y in scrolls)

        # Band-top for organic rank 9: we need the Y-position. Reuse
        # result_bands by importing it.
        from data_loader import absolute_rank_band_tops
        n_abs = max(mapping.keys()) + 1
        abs_tops = absolute_rank_band_tops(n_abs, doc_h)
        # Find absolute rank for organic rank 9
        inv = {v: k for k, v in mapping.items() if v is not None}
        rank9_abs = inv.get(9)
        if rank9_abs is None or rank9_abs >= len(abs_tops):
            continue
        rank9_top = abs_tops[rank9_abs]

        viewport_bottom = max_scroll + scr_h
        reached_rank9 = viewport_bottom >= rank9_top

        # Did user click any organic result? Which organic rank?
        click_rank = None
        first_click = clicks[0] if clicks else None
        if first_click is not None:
            _, _, cy = first_click
            # Find click absolute rank by band
            click_abs = -1
            for i_, top in enumerate(abs_tops):
                if cy >= top:
                    click_abs = i_
                else:
                    break
            if click_abs >= 0:
                click_rank = mapping.get(click_abs)  # may be None (ad)

        trials.append({
            "tid": tid,
            "n_organic": n_organic,
            "plain_top": not first_abs_is_ad,  # True if abs rank 0 is organic
            "reached_rank9": reached_rank9,
            "clicked_organic": click_rank is not None,
            "click_rank": click_rank,
        })

    print(f"\ntrials with ≥10 organic results: {len(trials)}")

    import polars as pl
    df = pl.DataFrame(trials)

    cohorts = {
        "A_plain_top_10plus_reached9": df.filter(
            pl.col("plain_top") & pl.col("reached_rank9")
        ),
        "B_plain_top_10plus_any_scroll": df.filter(pl.col("plain_top")),
        "C_any_10plus_reached9": df.filter(pl.col("reached_rank9")),
        "D_all_10plus": df,
    }

    rows = []
    for name, sub in cohorts.items():
        n = sub.height
        if n == 0:
            continue
        click_counts = defaultdict(int)
        ad_clicks = 0
        no_click = 0
        for row in sub.iter_rows(named=True):
            if row["click_rank"] is None:
                if row["clicked_organic"]:
                    ad_clicks += 1
                else:
                    no_click += 1
            else:
                click_counts[row["click_rank"]] += 1
        total_organic_clicks = sum(click_counts.values())
        for r in range(10):
            ctr = click_counts.get(r, 0) / n
            rows.append({
                "cohort": name,
                "n": n,
                "rank": r,
                "clicks": click_counts.get(r, 0),
                "ctr": round(ctr, 4),
            })
        print(
            f"\n{name}  n={n}  organic_clicks={total_organic_clicks}  "
            f"no_click={no_click}  ad_clicks={ad_clicks}"
        )
        print("  rank  clicks   ctr")
        for r in range(10):
            c = click_counts.get(r, 0)
            ctr = c / n
            bar = "█" * max(1, int(ctr * 200))
            print(f"  {r:>4}  {c:>6}  {ctr:.4f}  {bar}")

    pl.DataFrame(rows).write_csv(OUT / "ctr_by_rank_by_cohort.csv")

    summary = {
        name: {
            "n_trials": sub.height,
            "n_clicked_organic": int(sub.filter(pl.col("click_rank").is_not_null()).height),
            "p_click_rank9_among_reached": (
                (sub.filter(pl.col("click_rank") == 9).height / sub.height)
                if sub.height else None
            ),
            "p_any_click": (
                (sub["clicked_organic"].sum() / sub.height) if sub.height else None
            ),
        }
        for name, sub in cohorts.items()
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print(f"\nwrote {OUT}/ctr_by_rank_by_cohort.csv and summary.json")


if __name__ == "__main__":
    main()
