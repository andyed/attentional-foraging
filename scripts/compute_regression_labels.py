"""Compute per-(trial, position) gaze-regression labels in the order
matching cursor-approach-features.json records.

NB22 / NB28 / NB21 all consume `regression_labels_cache.json` which
must be the same length and ordering as `cursor-approach-features.json`.
This producer regenerates it under either attribution.

Algorithm (from NB22): a position is 'regressed' iff the user fixated
it, max_seen advanced past it, and the user later fixated it again.

Run:
    .venv/bin/python scripts/compute_regression_labels.py --attribution organic
    # → scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    load_fixations,
    load_mouse_events,
    get_trial_meta,
    extract_serp_results,
    interpolate_scroll,
    result_band_tops,
    organic_aoi_tops,
    assign_fixation_to_position,
)


def regressed_positions(trial_id, attribution):
    fix = load_fixations(trial_id)
    meta = get_trial_meta(trial_id)
    if not fix or meta is None or not meta[0]:
        return None, 0
    doc_h = meta[0]
    if attribution == "organic":
        tops = organic_aoi_tops(trial_id)
        n_res = len(tops)
    else:
        serp = extract_serp_results(trial_id)
        n_res = len(serp) if serp else 10
        tops = result_band_tops(n_res, doc_h) if n_res else []
    if not tops:
        return None, 0

    pos_seq = []
    for f in fix:
        p = assign_fixation_to_position(f["y"], tops, n_res)
        if p is not None and p >= 0:
            pos_seq.append(p)

    visited = set()
    regressed = set()
    max_seen = -1
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressed.add(p)
        visited.add(p)
        max_seen = max(max_seen, p)

    return regressed, n_res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attribution", choices=["absolute", "organic"], default="organic")
    parser.add_argument("--features",
                        help="Path to cursor-approach-features JSON (default depends on attribution)")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    if args.features:
        feat_path = Path(args.features)
    elif args.attribution == "organic":
        feat_path = ROOT / "AdSERP/data/cursor-approach-features-organic.json"
    else:
        feat_path = ROOT / "AdSERP/data/cursor-approach-features.json"

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = ROOT / "scripts/output/approach_threshold_sensitivity"
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_organic" if args.attribution == "organic" else ""
        out_path = out_dir / f"regression_labels_cache{suffix}.json"

    print(f"Loading features from {feat_path}", file=sys.stderr)
    records = json.load(open(feat_path))
    print(f"Records: {len(records):,}", file=sys.stderr)

    cache_by_trial = {}
    labels = []
    n_pos = n_neg = 0
    for r in records:
        tid = r["trial_id"]
        pos = r["position"]
        if tid not in cache_by_trial:
            regressed, _n = regressed_positions(tid, args.attribution)
            cache_by_trial[tid] = regressed if regressed is not None else set()
        is_reg = pos in cache_by_trial[tid]
        labels.append(is_reg)
        if is_reg:
            n_pos += 1
        else:
            n_neg += 1

    print(f"\n{args.attribution}: regressed={n_pos:,} ({100*n_pos/len(labels):.1f}%), not_regressed={n_neg:,}", file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(labels, f)
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
