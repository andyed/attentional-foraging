"""Export AdSERP AOI table keyed by canonical trial ID for cross-lab sharing.

Trial ID format: `p{PPP}-b{B}-t{T}` (e.g. p004-b1-t1) — the same handle
used throughout `notebooks-v2/data_loader.py` and the AdSERP per-trial
CSV filenames.

Three attribution flavors (mirror the producer-pattern from the
2026-05-01 cascade):

  --attribution absolute       (legacy h3-pooled bands; equal-interval estimate)
  --attribution organic        (bbox-extracted organic AOIs only; pixel-accurate)
  --attribution organic_hybrid (bbox organics + shipped ad rectangles in
                                display order, etype-tagged; pixel-accurate)

For every trial we emit one row per AOI slot:
  - trial_id, uid, batch, trial
  - rank (0..n-1, display order within the chosen attribution)
  - etype  (always 'organic' under --attribution organic;
            'organic'/'dd_top'/'native_ad' under organic_hybrid;
            'organic' or 'ad' under absolute, in the legacy slot_type column)
  - top_y, bottom_y, center_y  (page-space px, doc-coords)
  - left_x, right_x  (the result column x-range, constant across slots)
  - n_total, doc_height, screen_height  (per-trial metadata)

Output: scripts/output/adserp_aois_by_trial_id_{attribution}.{csv,jsonl,parquet}
        + adserp_aois_by_trial_id_{attribution}_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))
sys.path.insert(0, str(ROOT / "scripts"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    get_trial_meta,
    count_absolute_ranks,
    absolute_rank_band_tops,
    absolute_to_organic_rank,
    organic_aoi_bands,  # bbox organics
)
from compute_cursor_approach_features import build_hybrid_aois  # noqa: E402

# Result column x-range is shared across all trials (data_loader.py:370-371).
RESULT_COL_X_MIN = 162
RESULT_COL_X_MAX = 702

OUT_DIR = ROOT / "scripts" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ID_PATTERN = re.compile(r"^p(\d{3})-b(\d+)-t(\d+)$")


def parse_trial_id(tid: str) -> tuple[int, int, int]:
    m = ID_PATTERN.match(tid)
    if not m:
        raise ValueError(f"unexpected trial id: {tid!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def rows_absolute(trial_id, doc_h, scr_h, uid, batch, trial):
    """Legacy: equal-interval band estimate, pooling ads + organics."""
    n_abs = count_absolute_ranks(trial_id)
    if n_abs == 0:
        return []
    tops = absolute_rank_band_tops(n_abs, doc_h)
    abs_to_org = absolute_to_organic_rank(trial_id, doc_height=doc_h)
    n_org = sum(1 for v in abs_to_org.values() if v is not None)

    rows = []
    for r in range(n_abs):
        top = tops[r]
        bottom = tops[r + 1] if r + 1 < n_abs else doc_h - 200
        org_rank = abs_to_org.get(r)
        rows.append({
            "trial_id": trial_id,
            "uid": uid, "batch": batch, "trial": trial,
            "rank": r,
            "etype": "organic" if org_rank is not None else "ad",
            "organic_rank": org_rank,
            "top_y": round(top, 2),
            "bottom_y": round(bottom, 2),
            "center_y": round((top + bottom) / 2, 2),
            "left_x": RESULT_COL_X_MIN,
            "right_x": RESULT_COL_X_MAX,
            "n_total": n_abs,
            "n_organic": n_org,
            "doc_height": doc_h,
            "screen_height": scr_h,
        })
    return rows


def rows_organic(trial_id, doc_h, scr_h, uid, batch, trial):
    """Bbox-extracted organic AOIs only (ads excluded)."""
    bands = organic_aoi_bands(trial_id) or []
    if not bands:
        return []
    n = len(bands)
    rows = []
    for r, (top, bot) in enumerate(bands):
        rows.append({
            "trial_id": trial_id,
            "uid": uid, "batch": batch, "trial": trial,
            "rank": r,
            "etype": "organic",
            "organic_rank": r,
            "top_y": round(float(top), 2),
            "bottom_y": round(float(bot), 2),
            "center_y": round((float(top) + float(bot)) / 2, 2),
            "left_x": RESULT_COL_X_MIN,
            "right_x": RESULT_COL_X_MAX,
            "n_total": n,
            "n_organic": n,
            "doc_height": doc_h,
            "screen_height": scr_h,
        })
    return rows


def rows_organic_hybrid(trial_id, doc_h, scr_h, uid, batch, trial):
    """Bbox organics + shipped ad rectangles in display order, etype-tagged.
    Ads pulled from ad-boundary-data; result-column ads only (dd_right
    excluded). Mirrors build_hybrid_aois in compute_cursor_approach_features.
    """
    tops, bottoms, etypes = build_hybrid_aois(trial_id)
    if not tops:
        return []
    n = len(tops)
    n_org = sum(1 for e in etypes if e == "organic")
    rows = []
    org_idx = 0
    for r in range(n):
        et = etypes[r]
        org_rank = None
        if et == "organic":
            org_rank = org_idx
            org_idx += 1
        rows.append({
            "trial_id": trial_id,
            "uid": uid, "batch": batch, "trial": trial,
            "rank": r,
            "etype": et,
            "organic_rank": org_rank,
            "top_y": round(float(tops[r]), 2),
            "bottom_y": round(float(bottoms[r]), 2),
            "center_y": round((float(tops[r]) + float(bottoms[r])) / 2, 2),
            "left_x": RESULT_COL_X_MIN,
            "right_x": RESULT_COL_X_MAX,
            "n_total": n,
            "n_organic": n_org,
            "doc_height": doc_h,
            "screen_height": scr_h,
        })
    return rows


def rows_for_trial(trial_id: str, attribution: str) -> list[dict]:
    uid, batch, trial = parse_trial_id(trial_id)
    meta = get_trial_meta(trial_id)
    if not meta:
        return []
    doc_h, scr_h, _ = meta
    if not doc_h:
        return []
    if attribution == "absolute":
        return rows_absolute(trial_id, doc_h, scr_h, uid, batch, trial)
    if attribution == "organic":
        return rows_organic(trial_id, doc_h, scr_h, uid, batch, trial)
    if attribution == "organic_hybrid":
        return rows_organic_hybrid(trial_id, doc_h, scr_h, uid, batch, trial)
    raise ValueError(f"unknown attribution: {attribution!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution", choices=["absolute", "organic", "organic_hybrid"],
                        default="organic_hybrid",
                        help="AOI attribution flavor (default: organic_hybrid).")
    args = parser.parse_args()

    trial_ids = sorted(get_trial_ids())
    print(f"[export {args.attribution}] {len(trial_ids):,} trials", file=sys.stderr)

    all_rows: list[dict] = []
    skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f"  {i+1}/{len(trial_ids)}  (rows so far: {len(all_rows):,})",
                  file=sys.stderr)
        try:
            rows = rows_for_trial(tid, args.attribution)
        except Exception as exc:
            print(f"  skip {tid}: {exc}", file=sys.stderr)
            skipped += 1
            continue
        if not rows:
            skipped += 1
            continue
        all_rows.extend(rows)

    print(f"\n[export] {len(all_rows):,} AOI rows from "
          f"{len(trial_ids) - skipped:,} trials ({skipped} skipped)",
          file=sys.stderr)

    suffix = args.attribution
    csv_path = OUT_DIR / f"adserp_aois_by_trial_id_{suffix}.csv"
    fieldnames = list(all_rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    print(f"wrote {csv_path.relative_to(ROOT)}", file=sys.stderr)

    jsonl_path = OUT_DIR / f"adserp_aois_by_trial_id_{suffix}.jsonl"
    with open(jsonl_path, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {jsonl_path.relative_to(ROOT)}", file=sys.stderr)

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        table = pa.Table.from_pylist(all_rows)
        pq.write_table(table, OUT_DIR / f"adserp_aois_by_trial_id_{suffix}.parquet",
                       compression="snappy")
        print(f"wrote {(OUT_DIR / f'adserp_aois_by_trial_id_{suffix}.parquet').relative_to(ROOT)}",
              file=sys.stderr)
    except ImportError:
        print("(pyarrow not installed — skipping .parquet)", file=sys.stderr)

    summary = {
        "attribution": args.attribution,
        "n_trials": len({r["trial_id"] for r in all_rows}),
        "n_aoi_rows": len(all_rows),
        "n_by_etype": {
            e: sum(1 for r in all_rows if r["etype"] == e)
            for e in sorted(set(r["etype"] for r in all_rows))
        },
        "trial_id_format": "p{PPP}-b{B}-t{T} (zero-padded uid, 1-indexed batch/trial)",
        "id_regex": ID_PATTERN.pattern,
        "coordinate_system": "page-space pixels (document coordinates, not viewport)",
        "result_column_x_range": [RESULT_COL_X_MIN, RESULT_COL_X_MAX],
        "n_skipped_trials": skipped,
        "schema_note": (
            "rank is display-order within the chosen attribution; etype is "
            "the AOI kind (organic / dd_top / native_ad / ad); organic_rank "
            "is the within-organic position number (null for non-organics)."
        ),
    }
    with open(OUT_DIR / f"adserp_aois_by_trial_id_{suffix}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {(OUT_DIR / f'adserp_aois_by_trial_id_{suffix}_summary.json').relative_to(ROOT)}",
          file=sys.stderr)

    print("\n[summary]", file=sys.stderr)
    for k, v in summary.items():
        print(f"  {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
