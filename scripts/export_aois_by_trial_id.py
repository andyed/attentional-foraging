"""Export AdSERP AOI table keyed by canonical trial ID for cross-lab sharing.

Trial ID format: `p{PPP}-b{B}-t{T}` (e.g. p004-b1-t1) — the same handle
used throughout `notebooks-v2/data_loader.py` and the AdSERP per-trial
CSV filenames.

For every trial we emit one row per AOI slot with:
  - trial_id, uid, batch, trial
  - absolute_rank (0..n_abs-1) — every h3 slot, ads + organic pooled
  - organic_rank (0..n_org-1, or null for ad slots)
  - slot_type ('organic' | 'ad')
  - top_y, bottom_y, center_y (page-space px, doc-coords)
  - left_x, right_x (the result column x-range, constant across slots)
  - n_absolute, n_organic, doc_height (per-trial metadata)

Output: scripts/output/adserp_aois_by_trial_id.{csv,parquet,jsonl}
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "notebooks-v2"))

from data_loader import (  # noqa: E402
    get_trial_ids,
    get_trial_meta,
    count_absolute_ranks,
    absolute_rank_band_tops,
    absolute_to_organic_rank,
)

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


def rows_for_trial(trial_id: str) -> list[dict]:
    """Emit one row per absolute-rank AOI for this trial."""
    uid, batch, trial = parse_trial_id(trial_id)
    meta = get_trial_meta(trial_id)
    doc_h, scr_h, page_ts = meta
    if not doc_h:
        return []
    n_abs = count_absolute_ranks(trial_id)
    if n_abs == 0:
        return []
    tops = absolute_rank_band_tops(n_abs, doc_h)
    abs_to_org = absolute_to_organic_rank(trial_id, doc_height=doc_h)
    n_org = sum(1 for v in abs_to_org.values() if v is not None)

    rows = []
    for abs_rank in range(n_abs):
        top = tops[abs_rank]
        bottom = tops[abs_rank + 1] if abs_rank + 1 < n_abs else doc_h - 200
        org_rank = abs_to_org.get(abs_rank)
        rows.append({
            "trial_id": trial_id,
            "uid": uid,
            "batch": batch,
            "trial": trial,
            "absolute_rank": abs_rank,
            "organic_rank": org_rank,
            "slot_type": "ad" if org_rank is None else "organic",
            "top_y": round(top, 2),
            "bottom_y": round(bottom, 2),
            "center_y": round((top + bottom) / 2, 2),
            "left_x": RESULT_COL_X_MIN,
            "right_x": RESULT_COL_X_MAX,
            "n_absolute": n_abs,
            "n_organic": n_org,
            "doc_height": doc_h,
            "screen_height": scr_h,
        })
    return rows


def main() -> None:
    trial_ids = sorted(get_trial_ids())
    print(f"[export] {len(trial_ids):,} trials", file=sys.stderr)

    all_rows: list[dict] = []
    skipped = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f"  {i+1}/{len(trial_ids)}  (rows so far: {len(all_rows):,})",
                  file=sys.stderr)
        try:
            rows = rows_for_trial(tid)
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

    csv_path = OUT_DIR / "adserp_aois_by_trial_id.csv"
    fieldnames = list(all_rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)
    print(f"wrote {csv_path.relative_to(ROOT)}", file=sys.stderr)

    jsonl_path = OUT_DIR / "adserp_aois_by_trial_id.jsonl"
    with open(jsonl_path, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {jsonl_path.relative_to(ROOT)}", file=sys.stderr)

    # Optional parquet, only if pyarrow is available — keeps the script
    # standard-library-friendly for shipping to Jacek's lab.
    try:
        import pyarrow as pa  # noqa: F401
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(all_rows)
        pq.write_table(table, OUT_DIR / "adserp_aois_by_trial_id.parquet",
                       compression="snappy")
        print(f"wrote {(OUT_DIR / 'adserp_aois_by_trial_id.parquet').relative_to(ROOT)}",
              file=sys.stderr)
    except ImportError:
        print("(pyarrow not installed — skipping .parquet)", file=sys.stderr)

    # Per-trial-id quick index for sanity checks
    summary = {
        "n_trials": len({r["trial_id"] for r in all_rows}),
        "n_aoi_rows": len(all_rows),
        "n_organic_rows": sum(1 for r in all_rows if r["slot_type"] == "organic"),
        "n_ad_rows": sum(1 for r in all_rows if r["slot_type"] == "ad"),
        "trial_id_format": "p{PPP}-b{B}-t{T} (zero-padded uid, 1-indexed batch/trial)",
        "id_regex": ID_PATTERN.pattern,
        "coordinate_system": "page-space pixels (document coordinates, not viewport)",
        "result_column_x_range": [RESULT_COL_X_MIN, RESULT_COL_X_MAX],
        "header_offset_top_px": 200,
        "footer_offset_bottom_px": 200,
        "n_skipped_trials": skipped,
    }
    with open(OUT_DIR / "adserp_aois_by_trial_id_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {(OUT_DIR / 'adserp_aois_by_trial_id_summary.json').relative_to(ROOT)}",
          file=sys.stderr)

    print("\n[summary]", file=sys.stderr)
    for k, v in summary.items():
        print(f"  {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
