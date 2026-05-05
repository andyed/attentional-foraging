"""Population-size delta on NB22 four-class taxonomy: typed → typed_gapfill.

The full four-class split (clicked / deferred / eval-rejected / not-approached)
requires gaze-regression labels per (trial, position), which are cached at
scripts/output/approach_threshold_sensitivity/regression_labels_cache.json
under typed-legacy bbox geometry. Re-deriving regression labels under
typed_gapfill bbox geometry is a separate piece of work (the gap-fill
changes which fixations attribute to which position).

For the cascade headline, this script reports the **immediately-comparable**
populations under both flavors:
  - total records
  - clicked records (was_clicked=True)
  - approached records (min_dist < 100)
  - approached & clicked

These are the populations that gate the four-class split. The deferred /
eval-rejected breakdown moves with these but the directional shift is
captured by these counts.

Regime tag: [LAB, AdSERP, typed → typed_gapfill, NB22-population-delta]
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LEG = ROOT / "AdSERP" / "data" / "cursor-approach-features-typed.json"
GAP = ROOT / "AdSERP" / "data" / "cursor-approach-features-typed-gapfill.json"


def populations(records):
    n_total = len(records)
    n_clicked = sum(1 for r in records if r.get("was_clicked"))
    n_approached = sum(1 for r in records if r.get("min_dist", 1e9) < 100)
    n_apr_clk = sum(
        1 for r in records
        if r.get("was_clicked") and r.get("min_dist", 1e9) < 100
    )
    n_apr_nonclk = sum(
        1 for r in records
        if not r.get("was_clicked") and r.get("min_dist", 1e9) < 100
    )
    n_not_approached = n_total - n_approached
    by_etype = Counter(r.get("etype", "?") for r in records)
    by_etype_clk = Counter(
        r.get("etype", "?") for r in records if r.get("was_clicked")
    )
    return {
        "n_total": n_total,
        "n_clicked": n_clicked,
        "n_approached": n_approached,
        "n_approached_clicked": n_apr_clk,
        "n_approached_nonclick": n_apr_nonclk,
        "n_not_approached": n_not_approached,
        "click_rate_overall": n_clicked / n_total if n_total else 0,
        "click_rate_approached": n_apr_clk / n_approached if n_approached else 0,
        "by_etype": dict(by_etype),
        "by_etype_clicked": dict(by_etype_clk),
    }


leg = populations(json.load(open(LEG)))
gap = populations(json.load(open(GAP)))

print("NB22 four-class populations under typed → typed_gapfill\n")
print(f"  {'metric':<32s} {'typed':>10s} {'gapfill':>10s} {'Δ':>10s}")
print("  " + "-" * 64)
for k in [
    "n_total", "n_clicked", "n_approached", "n_approached_clicked",
    "n_approached_nonclick", "n_not_approached",
]:
    delta = gap[k] - leg[k]
    print(f"  {k:<32s} {leg[k]:>10,d} {gap[k]:>10,d} {delta:>+10,d}")

for k in ["click_rate_overall", "click_rate_approached"]:
    pct_leg = 100 * leg[k]
    pct_gap = 100 * gap[k]
    print(f"  {k:<32s} {pct_leg:>9.2f}% {pct_gap:>9.2f}% {pct_gap - pct_leg:>+10.2f}")

print(f"\n  Per-etype `was_clicked=True` records:")
print(f"  {'etype':<20s} {'typed':>8s} {'gapfill':>10s} {'Δ':>8s}")
print("  " + "-" * 50)
all_etypes = sorted(set(leg["by_etype_clicked"]) | set(gap["by_etype_clicked"]))
for et in all_etypes:
    a = leg["by_etype_clicked"].get(et, 0)
    b = gap["by_etype_clicked"].get(et, 0)
    print(f"  {et:<20s} {a:>8,d} {b:>10,d} {b - a:>+8d}")

print(f"\n  Per-etype TOTAL records:")
print(f"  {'etype':<20s} {'typed':>8s} {'gapfill':>10s} {'Δ':>8s}")
print("  " + "-" * 50)
all_etypes = sorted(set(leg["by_etype"]) | set(gap["by_etype"]))
for et in all_etypes:
    a = leg["by_etype"].get(et, 0)
    b = gap["by_etype"].get(et, 0)
    print(f"  {et:<20s} {a:>8,d} {b:>10,d} {b - a:>+8d}")
