"""Scroll-aware ski jump: click rate by organic rank relative to the
deepest organic rank the user actually scrolled into view.

Hypothesis: the 'terminal spike' seen in industry SERP data is not the
last DOM slot, it is the last slot the user *evaluated*. Define
'viewed_max_rank' as the deepest organic rank whose band-top fell
within (max_scroll_y + screen_height) during the trial. Then bin each
click by d = viewed_max_rank - click_organic_rank.
- d = 0 means the user clicked the deepest rank they scrolled to (the
  classic 'least-bad final pick' spike).
- d > 0 means they clicked something above their deepest scroll.

Outputs:
  scripts/output/ski_jump_scroll_aware/ctr_by_d_to_max.csv
  scripts/output/ski_jump_scroll_aware/ctr_by_absolute_when_last.csv
  scripts/output/ski_jump_scroll_aware/ctr_by_organic_rank_plain.csv
  scripts/output/ski_jump_scroll_aware/summary.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import polars as pl

import sys
sys.path.insert(0, str(Path("/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2")))

from data_loader import (
    get_trial_ids,
    get_trial_meta,
    load_mouse_events,
    absolute_to_organic_rank,
    organic_rank_band_tops,
    count_organic_ranks,
)

OUT = Path("/Users/andyed/Documents/dev/attentional-foraging/scripts/output/ski_jump_scroll_aware")
OUT.mkdir(parents=True, exist_ok=True)


def deepest_organic_rank_viewed(trial_id, doc_h, scr_h, scrolls):
    """Return the deepest organic rank whose band-top came into view.

    A rank is 'in view' when max_scroll_y + scr_h >= band_top_of_that_rank.
    Uses max scroll high-water mark (not end-of-trial scroll) so backward
    scrolls still count the rank as seen.
    """
    band_tops = organic_rank_band_tops(trial_id, doc_height=doc_h)
    if not band_tops:
        return None
    max_scroll = 0
    if scrolls:
        max_scroll = max(y for _, y in scrolls)
    viewport_bottom = max_scroll + scr_h
    # pos 0 is always visible without scrolling
    deepest = -1
    for i, top in enumerate(band_tops):
        if top <= viewport_bottom:
            deepest = i
        else:
            break
    return deepest if deepest >= 0 else None


def click_organic_rank(trial_id, click_y, doc_h):
    """Return the organic rank a click at page-y click_y fell into,
    or None if the click hit an ad slot or outside the result column.

    We bin by organic-rank bands (skipping ad slots).
    """
    band_tops = organic_rank_band_tops(trial_id, doc_height=doc_h)
    if not band_tops:
        return None
    # Binary-free: linear is fine, ≤11 entries
    rank = -1
    for i, top in enumerate(band_tops):
        if click_y >= top:
            rank = i
        else:
            break
    return rank if rank >= 0 else None


def main():
    tids = get_trial_ids()
    rows = []
    absolute_rows = []

    for tid in tids:
        doc_h, scr_h, _ = get_trial_meta(tid)
        if not doc_h or not scr_h:
            continue
        _, scrolls, clicks = load_mouse_events(tid)
        n_organic = count_organic_ranks(tid, doc_height=doc_h)
        if n_organic == 0:
            continue

        viewed_max = deepest_organic_rank_viewed(tid, doc_h, scr_h, scrolls)
        if viewed_max is None:
            continue

        # First click only, matches ski-jump convention
        click = clicks[0] if clicks else None
        click_rank = None
        if click is not None:
            click_rank = click_organic_rank(tid, click[2], doc_h)

        rows.append({
            "tid": tid,
            "n_organic": n_organic,
            "viewed_max_rank": viewed_max,
            "click_rank": click_rank,
            "clicked": int(click_rank is not None),
        })

    df = pl.DataFrame(rows)

    # ── 1. CTR by d = viewed_max_rank - click_rank (scroll-aware) ──
    # "Impression" at rank r = # trials where viewed_max_rank >= r
    # "Click" at rank r = # trials where click_rank == r
    # But for scroll-aware ski jump we flip: bin by (viewed_max - r).
    # Simpler: compute CTR as fn(d) where we restrict to trials where
    # click_rank <= viewed_max (user clicked within their scrolled range)
    # and d = viewed_max - click_rank.
    clicked = df.filter(pl.col("clicked") == 1)
    clicked = clicked.filter(pl.col("click_rank") <= pl.col("viewed_max_rank"))
    clicked = clicked.with_columns(
        (pl.col("viewed_max_rank") - pl.col("click_rank")).alias("d_to_max")
    )
    print(f"trials with click within scrolled range: {clicked.height}")

    # Impressions at d: trial's viewed_max_rank defines how many d values
    # are 'available' (d=0..viewed_max_rank). A rank r is "impressed at
    # distance d" iff viewed_max_rank = r + d, i.e. every trial's max
    # rank gets counted once at d=0, and every rank below max gets
    # counted at positive d.
    # Simpler denominator: trials where viewed_max_rank >= d.
    d_counts = defaultdict(lambda: {"clicks": 0, "impressions": 0})
    for row in df.iter_rows(named=True):
        vmax = row["viewed_max_rank"]
        for d in range(vmax + 1):
            d_counts[d]["impressions"] += 1
    for row in clicked.iter_rows(named=True):
        d_counts[row["d_to_max"]]["clicks"] += 1

    d_rows = []
    for d in sorted(d_counts):
        c = d_counts[d]
        ctr = c["clicks"] / c["impressions"] if c["impressions"] > 0 else 0
        d_rows.append({
            "d_to_max": d,
            "clicks": c["clicks"],
            "impressions": c["impressions"],
            "ctr": round(ctr, 4),
        })
    d_df = pl.DataFrame(d_rows)
    d_df.write_csv(OUT / "ctr_by_d_to_max.csv")
    print("\nCTR by distance-from-deepest-viewed-rank:")
    print(d_df)

    # ── 2. CTR by absolute organic rank, restricted to trials where the
    # clicked rank IS the deepest viewed (the "terminal click" cohort) ──
    terminal = clicked.filter(pl.col("click_rank") == pl.col("viewed_max_rank"))
    print(f"\nterminal-click trials (clicked rank == deepest scrolled): {terminal.height}")
    term_counts = defaultdict(lambda: {"clicks": 0, "impressions": 0})
    for row in df.iter_rows(named=True):
        term_counts[row["viewed_max_rank"]]["impressions"] += 1
    for row in terminal.iter_rows(named=True):
        term_counts[row["viewed_max_rank"]]["clicks"] += 1
    term_rows = []
    for r in sorted(term_counts):
        c = term_counts[r]
        ctr = c["clicks"] / c["impressions"] if c["impressions"] > 0 else 0
        term_rows.append({
            "deepest_rank": r,
            "terminal_clicks": c["clicks"],
            "trials_scrolled_this_deep": c["impressions"],
            "terminal_rate": round(ctr, 4),
        })
    term_df = pl.DataFrame(term_rows)
    term_df.write_csv(OUT / "terminal_click_by_deepest_rank.csv")
    print("\nTerminal-click rate by deepest rank scrolled:")
    print(term_df)

    # ── 3. Classic CTR by organic rank, but stratified by how deep user scrolled ──
    strat_rows = []
    for max_scroll_bucket in ("all", "shallow_≤3", "deep_≥6"):
        if max_scroll_bucket == "all":
            sub = df
        elif max_scroll_bucket == "shallow_≤3":
            sub = df.filter(pl.col("viewed_max_rank") <= 3)
        else:
            sub = df.filter(pl.col("viewed_max_rank") >= 6)
        counts = defaultdict(lambda: {"clicks": 0, "impressions": 0})
        for row in sub.iter_rows(named=True):
            for r in range(row["viewed_max_rank"] + 1):
                counts[r]["impressions"] += 1
            if row["click_rank"] is not None and row["click_rank"] <= row["viewed_max_rank"]:
                counts[row["click_rank"]]["clicks"] += 1
        for r in sorted(counts):
            c = counts[r]
            ctr = c["clicks"] / c["impressions"] if c["impressions"] > 0 else 0
            strat_rows.append({
                "cohort": max_scroll_bucket,
                "organic_rank": r,
                "clicks": c["clicks"],
                "impressions": c["impressions"],
                "ctr": round(ctr, 4),
                "n_trials_in_cohort": sub.height,
            })
    strat_df = pl.DataFrame(strat_rows)
    strat_df.write_csv(OUT / "ctr_by_rank_by_scroll_depth.csv")
    print("\nCTR by organic rank × scroll-depth stratum:")
    print(strat_df)

    summary = {
        "n_trials": df.height,
        "n_trials_with_first_click": int(df["clicked"].sum()),
        "n_trials_click_within_scrolled_range": clicked.height,
        "n_terminal_clicks": terminal.height,
        "pct_terminal_of_clicks": round(
            terminal.height / clicked.height * 100, 1
        ) if clicked.height else None,
    }
    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nSummary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
