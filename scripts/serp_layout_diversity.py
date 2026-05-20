"""SERP layout diversity in the AdSERP corpus.

Counts, per trial, the AOI element types present in the typed-gapfill AOI
maps (data/aoi-typed-gapfill/) — characterizing how varied the AdSERP SERP
layouts are. Evidence for the layout-resilience claim: the M3 ~= M4
rank-position absorption holds across a corpus that is not a uniform
ten-blue-links list.

Run: .venv/bin/python scripts/serp_layout_diversity.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
AOI_DIR = ROOT / "data/aoi-typed-gapfill"
OUT = ROOT / "scripts/output/serp_layout_diversity/summary.json"


def main():
    files = sorted(AOI_DIR.glob("*.json"))
    n = len(files)
    if n == 0:
        print(f"no AOI files in {AOI_DIR}", file=sys.stderr)
        return 1

    type_trial_count = Counter()      # trials containing >=1 of each type
    organic_counts, distinct_types, total_aois = [], [], []
    n_with_nonorganic = 0

    for f in files:
        aois = json.load(open(f))
        types = [a.get("type") for a in aois if a.get("type")]
        tset = set(types)
        for t in tset:
            type_trial_count[t] += 1
        organic_counts.append(sum(1 for t in types if t == "organic"))
        distinct_types.append(len(tset))
        total_aois.append(len(types))
        if tset - {"organic"}:
            n_with_nonorganic += 1

    oc = np.array(organic_counts)
    dt = np.array(distinct_types)
    ta = np.array(total_aois)

    summary = {
        "trials": n,
        "trials_with_nonorganic_element": n_with_nonorganic,
        "frac_with_nonorganic_element": round(n_with_nonorganic / n, 4),
        "organic_per_serp": {"median": int(np.median(oc)), "mean": round(float(oc.mean()), 2),
                             "min": int(oc.min()), "max": int(oc.max())},
        "total_aois_per_serp": {"median": int(np.median(ta)), "mean": round(float(ta.mean()), 2)},
        "distinct_types_per_serp": {"median": int(np.median(dt)), "mean": round(float(dt.mean()), 2),
                                    "min": int(dt.min()), "max": int(dt.max())},
        "per_type_trial_presence": {t: {"trials": c, "frac": round(c / n, 4)}
                                    for t, c in type_trial_count.most_common()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(OUT, "w"), indent=2)

    print("=" * 60)
    print("AdSERP SERP layout diversity (typed-gapfill AOI maps)")
    print("=" * 60)
    print(f"trials: {n}")
    print(f"trials with >=1 non-organic element: {n_with_nonorganic} "
          f"({n_with_nonorganic / n * 100:.1f}%)")
    print(f"organic results / SERP: median {np.median(oc):.0f}, "
          f"mean {oc.mean():.1f}, range [{oc.min()}, {oc.max()}]")
    print(f"total AOIs / SERP: median {np.median(ta):.0f}, mean {ta.mean():.1f}")
    print(f"distinct AOI types / SERP: median {np.median(dt):.0f}, "
          f"mean {dt.mean():.1f}, range [{dt.min()}, {dt.max()}]")
    print("per-type trial presence:")
    for t, c in type_trial_count.most_common():
        print(f"  {t:22s} {c:5d}  {c / n * 100:5.1f}%")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
