"""Compare bbox AOI vs band-estimation for per-position fixation attribution.

Runs both attribution methods over the full corpus and reports:
  - per-trial: organic count from bbox vs from h3-count
  - per-fixation: which position bbox vs band-estimation assigns
  - aggregate: re-attribution rate (% of fixations that land at a different
    rank under bbox vs band) and per-rank count shifts

This is the consumer-side analog of the AOI-side audit. Migrating any
notebook from `result_band_tops` to `organic_aoi_tops` produces shifts
of the magnitude reported here.

Output:
  scripts/output/aoi-consumer-cascade/per-rank-shifts.json
  scripts/output/aoi-consumer-cascade/per-trial-summary.json
  stdout: tables ready for the CHANGELOG entry
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    load_fixations,
    get_trial_meta,
    count_results_html,  # legacy: absolute h3 count
    count_organic_ranks,
    result_band_tops,
    organic_aoi_tops,
    load_aois,
    assign_fixation_to_position,
)

OUT = ROOT / "scripts" / "output" / "aoi-consumer-cascade"
OUT.mkdir(parents=True, exist_ok=True)


def attribute_via_bands(fixations, doc_h, n_results):
    """Old method: even-band division, fixation→position via bisect."""
    if doc_h is None or n_results is None or n_results == 0:
        return None
    tops = result_band_tops(n_results, doc_h)
    counts = Counter()
    for fix in fixations:
        pos = assign_fixation_to_position(fix["y"], tops, n_results)
        if pos is not None:
            counts[pos] += 1
    return counts


def attribute_via_bbox(fixations, trial_id):
    """New method: pixel-accurate organic AOI bands from bbox JSON."""
    tops = organic_aoi_tops(trial_id)
    n = len(tops)
    if n == 0:
        return None
    counts = Counter()
    for fix in fixations:
        pos = assign_fixation_to_position(fix["y"], tops, n)
        if pos is not None:
            counts[pos] += 1
    return counts


def main():
    trial_ids = get_trial_ids()
    n_trials = len(trial_ids)
    print(f"Comparing AOI consumers across {n_trials} trials...\n")

    per_trial = []
    band_per_rank = Counter()
    bbox_per_rank = Counter()
    reattributed_fixations = 0
    total_fixations_attributed = 0
    rank_disagreements = defaultdict(Counter)  # band_rank → {bbox_rank: count}

    skipped = 0
    for tid in trial_ids:
        try:
            fixations = load_fixations(tid)
            if not fixations:
                skipped += 1
                continue
            meta = get_trial_meta(tid)
            doc_h = meta[0] if meta and meta[0] else None
            n_abs = count_results_html(tid)  # absolute h3 count, the legacy denominator

            band_counts = attribute_via_bands(fixations, doc_h, n_abs)
            bbox_counts = attribute_via_bbox(fixations, tid)

            if band_counts is None or bbox_counts is None:
                skipped += 1
                continue

            n_organic_bbox = len(organic_aoi_tops(tid))
            per_trial.append({
                "trial": tid,
                "n_abs_h3": n_abs,
                "n_organic_bbox": n_organic_bbox,
                "n_organic_h3": count_organic_ranks(tid, doc_h) or 0,
                "fixations": len(fixations),
                "band_attributed": sum(band_counts.values()),
                "bbox_attributed": sum(bbox_counts.values()),
            })

            for r, c in band_counts.items():
                band_per_rank[r] += c
            for r, c in bbox_counts.items():
                bbox_per_rank[r] += c

            # Per-fixation re-attribution: re-run attribution side by side.
            tops_band = result_band_tops(n_abs, doc_h) if doc_h else None
            tops_bbox = organic_aoi_tops(tid)
            for fix in fixations:
                p_band = assign_fixation_to_position(fix["y"], tops_band, n_abs) if tops_band else None
                p_bbox = assign_fixation_to_position(fix["y"], tops_bbox, len(tops_bbox)) if tops_bbox else None
                if p_band is None and p_bbox is None:
                    continue
                total_fixations_attributed += 1
                if p_band != p_bbox:
                    reattributed_fixations += 1
                rank_disagreements[p_band][p_bbox] += 1

        except Exception as e:
            print(f"  SKIP {tid}: {e}", file=sys.stderr)
            skipped += 1

    n_used = len(per_trial)
    print(f"Trials processed: {n_used}/{n_trials} (skipped: {skipped})\n")

    # Per-rank totals
    max_rank = max(max(band_per_rank.keys(), default=0), max(bbox_per_rank.keys(), default=0))
    print(f"{'rank':>5} | {'band-attr':>10} | {'bbox-attr':>10} | {'delta':>10} | {'shift %':>8}")
    print("-" * 60)
    for r in range(max_rank + 1):
        b = band_per_rank.get(r, 0)
        x = bbox_per_rank.get(r, 0)
        d = x - b
        pct = (100.0 * d / b) if b > 0 else float('nan')
        print(f"{r:>5} | {b:>10,} | {x:>10,} | {d:+10,} | {pct:>+7.1f}%")

    print()
    print(f"Fixations re-attributed: {reattributed_fixations:,} / {total_fixations_attributed:,} = {100.0*reattributed_fixations/max(total_fixations_attributed,1):.1f}%")

    # Concentration of re-attribution: where do band-rank fixations end up under bbox?
    print("\nRe-attribution flow (top 10 band-rank → bbox-rank shifts):")
    flows = []
    for b_rank, dest in rank_disagreements.items():
        for x_rank, c in dest.items():
            if b_rank != x_rank and c > 0:
                flows.append((c, b_rank, x_rank))
    flows.sort(reverse=True)
    for c, b, x in flows[:10]:
        print(f"  band rank {b} → bbox rank {x}: {c:,} fixations")

    # Save artifacts
    summary = {
        "n_trials_processed": n_used,
        "n_trials_skipped": skipped,
        "total_fixations_attributed": total_fixations_attributed,
        "reattributed_fixations": reattributed_fixations,
        "reattribution_rate_pct": 100.0 * reattributed_fixations / max(total_fixations_attributed, 1),
        "per_rank_band": {str(r): band_per_rank[r] for r in sorted(band_per_rank)},
        "per_rank_bbox": {str(r): bbox_per_rank[r] for r in sorted(bbox_per_rank)},
    }
    (OUT / "per-rank-shifts.json").write_text(json.dumps(summary, indent=2))
    (OUT / "per-trial-summary.json").write_text(json.dumps(per_trial, indent=2))
    print(f"\nWrote {OUT / 'per-rank-shifts.json'}")
    print(f"Wrote {OUT / 'per-trial-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
