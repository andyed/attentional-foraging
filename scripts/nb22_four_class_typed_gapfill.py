"""NB22 four-class taxonomy under typed_gapfill — full population breakdown.

Uses cursor-approach-features-typed-gapfill.json + the typed_gapfill
regression-label cache (produced by compute_regression_labels.py
--attribution typed_gapfill).

Four classes (per-AOI):
  - clicked            : was_clicked == True
  - deferred           : approached non-click WITH gaze regression
  - eval-rejected      : approached non-click WITHOUT gaze regression
  - not-approached     : min_dist >= 100

Reports:
  - Class-size breakdown vs typed legacy
  - Per-etype class composition

Regime tag: [LAB, AdSERP, typed_gapfill, NB22-four-class]
See: docs/null-findings/2026-05-05-bbox-y-coverage.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))

FLAVORS = {
    "typed": (
        ROOT / "AdSERP/data/cursor-approach-features-typed.json",
        ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed.json",
    ),
    "typed_gapfill": (
        ROOT / "AdSERP/data/cursor-approach-features-typed-gapfill.json",
        ROOT / "scripts/output/approach_threshold_sensitivity/regression_labels_cache_typed_gapfill.json",
    ),
}


def four_class(records, regression_labels):
    """Return per-record (class, etype) tuples and aggregate counts."""
    assert len(records) == len(regression_labels)
    out = {"clicked": 0, "deferred": 0, "eval_rejected": 0, "not_approached": 0}
    by_class_etype = {k: Counter() for k in out}
    for r, regressed in zip(records, regression_labels):
        et = r.get("etype", "?")
        if r.get("was_clicked"):
            cls = "clicked"
        elif r.get("min_dist", 1e9) >= 100:
            cls = "not_approached"
        elif regressed:
            cls = "deferred"
        else:
            cls = "eval_rejected"
        out[cls] += 1
        by_class_etype[cls][et] += 1
    return out, by_class_etype


results = {}
for flavor, (feat_path, reg_path) in FLAVORS.items():
    print(f"\nLoading {flavor}: {feat_path.name}")
    records = json.load(open(feat_path))
    regression_labels = json.load(open(reg_path))
    if len(records) != len(regression_labels):
        print(
            f"  WARN: records {len(records):,} vs regression labels "
            f"{len(regression_labels):,} — using min length"
        )
        n = min(len(records), len(regression_labels))
        records = records[:n]
        regression_labels = regression_labels[:n]
    aggregate, by_class_etype = four_class(records, regression_labels)
    print(f"  total: {len(records):,}")
    for cls, n in aggregate.items():
        pct = 100 * n / len(records)
        print(f"    {cls:<18s}: {n:>6,d}  ({pct:5.1f}%)")
    results[flavor] = (aggregate, by_class_etype, len(records))

# ── Side-by-side comparison ──
print("\n" + "=" * 70)
print("Four-class population: typed → typed_gapfill")
print("=" * 70)
leg_agg, leg_etype, leg_n = results["typed"]
gap_agg, gap_etype, gap_n = results["typed_gapfill"]

print(f"  {'class':<18s} {'typed':>10s} {'gapfill':>10s} {'Δ':>10s}")
print("  " + "-" * 50)
for cls in ["clicked", "deferred", "eval_rejected", "not_approached"]:
    leg = leg_agg[cls]
    gap = gap_agg[cls]
    print(f"  {cls:<18s} {leg:>10,d} {gap:>10,d} {gap - leg:>+10,d}")
print("  " + "-" * 50)
print(f"  {'total':<18s} {leg_n:>10,d} {gap_n:>10,d} {gap_n - leg_n:>+10,d}")

# Per-etype × class table for typed_gapfill
print("\nPer-etype × class breakdown under typed_gapfill:")
all_etypes = set()
for c in gap_etype.values():
    all_etypes.update(c.keys())
classes = ["clicked", "deferred", "eval_rejected", "not_approached"]
print(f"  {'etype':<18s} " + " ".join(f"{c[:10]:>11s}" for c in classes))
print("  " + "-" * (18 + 4 * 12))
for et in sorted(all_etypes):
    row = [gap_etype[c].get(et, 0) for c in classes]
    print(f"  {et:<18s} " + " ".join(f"{n:>11,d}" for n in row))
