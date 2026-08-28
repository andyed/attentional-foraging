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

# AllSERP enrichment release. Bump when the typed AOI maps change in a way
# that moves downstream values (see CHANGELOG.md). Stamped into every export
# summary so a consumer can identify which enrichment a CSV came from.
ALLSERP_RELEASE = "1.1.0"
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
from probe_cellsplit_features import load_aois as load_cell_aois  # noqa: E402

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


def rows_typed(trial_id, doc_h, scr_h, uid, batch, trial,
                gapfill: bool = False):
    """HTML+vision typed AOI map (Phase 1+2 of feat/aoi-pipeline-v3-typed).

    Emits one row per main-axis card (position >= 0). Off-axis cards
    (chrome, dd_right, #botstuff, #rhs) are NOT emitted — they have no
    scroll-axis position. Etype taxonomy: organic, dd_top, native_ad,
    top_places, knowledge_panel, paa, image_pack, related_searches,
    other_widget, unknown_widget.

    When gapfill=True, reads from data/aoi-typed-gapfill/ instead of
    data/aoi-typed/. The midpoint-split fills inter-result Y gaps so
    fixations and clicks landing between adjacent results are now
    attributable. See docs/null-findings/2026-05-05-bbox-y-coverage.md.
    """
    if gapfill:
        from data_loader import load_typed_gapfill_aois as load_typed_aois
    else:
        from data_loader import load_typed_aois
    cards = load_typed_aois(trial_id)
    if not cards:
        return []
    main = sorted([c for c in cards if c.get('position', -1) >= 0
                    and c.get('y') is not None and c.get('height') is not None],
                   key=lambda c: c['position'])
    n = len(main)
    n_org = sum(1 for c in main if c['type'] == 'organic')
    rows = []
    org_idx = 0
    for r, c in enumerate(main):
        et = c['type']
        org_rank = None
        if et == 'organic':
            org_rank = org_idx
            org_idx += 1
        top_y = float(c['y'])
        bot_y = top_y + float(c['height'])
        rows.append({
            'trial_id': trial_id,
            'uid': uid, 'batch': batch, 'trial': trial,
            'rank': r,
            'etype': et,
            'organic_rank': org_rank,
            'top_y': round(top_y, 2),
            'bottom_y': round(bot_y, 2),
            'center_y': round((top_y + bot_y) / 2, 2),
            'left_x': float(c.get('x', RESULT_COL_X_MIN)),
            'right_x': float(c.get('x', RESULT_COL_X_MIN) + c.get('width', RESULT_COL_X_MAX - RESULT_COL_X_MIN)),
            'n_total': n,
            'n_organic': n_org,
            'doc_height': doc_h,
            'screen_height': scr_h,
            'html_handle': c.get('html_handle'),
            'html_signature': c.get('html_signature', ''),
        })
    return rows


CELL_ETYPE = {"dd_top": "dd_top_cell", "organic_result": "organic_cell",
              "dd_right": "dd_right_cell"}


def _cellsplit_extra_keys(row: dict, role: str, cell_index, n_cells: int,
                           parent_rank: int, parent_etype: str, main_axis: bool):
    """Stamp the six cell-aware columns onto a base-schema row in place."""
    row.update(role=role, cell_index=cell_index, n_cells=n_cells,
               parent_rank=parent_rank, parent_etype=parent_etype,
               main_axis=main_axis)
    return row


def _cell_row(c, trial_id, uid, batch, trial, doc_h, scr_h,
               parent_row, cell_index, n_cells, main_axis, rank):
    """One role='cell' row from a cascade-snapshot cell dict (x,y,w,h)."""
    top_y = float(c["y"])
    bot_y = top_y + float(c["h"])
    return {
        "trial_id": trial_id, "uid": uid, "batch": batch, "trial": trial,
        "rank": rank,
        "etype": CELL_ETYPE[c["parent_kind"]],
        "organic_rank": None,
        "top_y": round(top_y, 2), "bottom_y": round(bot_y, 2),
        "center_y": round((top_y + bot_y) / 2, 2),
        "left_x": round(float(c["x"]), 2),
        "right_x": round(float(c["x"]) + float(c["w"]), 2),
        "n_total": parent_row["n_total"] if parent_row else None,
        "n_organic": parent_row["n_organic"] if parent_row else None,
        "doc_height": doc_h, "screen_height": scr_h,
        "html_handle": None, "html_signature": "",
        "role": "cell", "cell_index": cell_index, "n_cells": n_cells,
        "parent_rank": parent_row["rank"] if parent_row else -1,
        "parent_etype": parent_row["parent_etype"] if parent_row else CELL_ETYPE[c["parent_kind"]].rsplit("_cell", 1)[0],
        "main_axis": main_axis,
    }


def rows_typed_cellsplit(trial_id, doc_h, scr_h, uid, batch, trial):
    """Cell-aware superset of typed_gapfill.

    Every typed_gapfill main-axis card is emitted unchanged as a role='parent'
    row (filter ``role == 'parent' and main_axis`` to recover typed_gapfill
    exactly). Cards the cascade snapshot resolves into sub-cells gain extra
    role='cell' rows, in three honest tiers:

      dd_top_cell   horizontal top-ads carousel cards. The headline split:
                    midpoint-split X-ranges, ~4 cells/carousel, ~56% of trials.
      organic_cell  organic sub-elements (sitelinks etc.). Sparse (~6%); the
                    X midpoint-split is deferred, so cell X is as-detected.
      dd_right_cell right-rail cards. OFF-AXIS (main_axis=False). Right-rail
                    blocks are also emitted at parent grain for every trial
                    that has one, so consumers can condition on right-rail
                    exposure to reduce variance in main-axis models. dd_right
                    is a control covariate, not a modeling target.

    Adds six columns to the typed schema: role ('parent'|'cell'), cell_index,
    n_cells (cells in this parent; 0 = not subdivided), parent_rank,
    parent_etype, main_axis (bool).
    """
    base = rows_typed(trial_id, doc_h, scr_h, uid, batch, trial, gapfill=True)
    for r in base:
        _cellsplit_extra_keys(r, "parent", None, 0, r["rank"], r["etype"], True)

    try:
        aois = load_cell_aois(trial_id, midpoint_split=True)
    except FileNotFoundError:
        return base
    cells = [a for a in aois if a["role"] == "cell"]
    dd_right_parents = [a for a in aois
                        if a["role"] == "parent" and a["kind"] == "dd_right"]

    extra: list[dict] = []

    # Main-axis subdivisions (dd_top, organic): attach each cell to the
    # backbone parent whose Y-range contains the cell center.
    for parent_kind, target_etype in (("dd_top", "dd_top"),
                                       ("organic_result", "organic")):
        kin = [c for c in cells if c["parent_kind"] == parent_kind]
        if not kin:
            continue
        parents = [r for r in base
                   if r["etype"] == target_etype and r["main_axis"]]
        buckets: dict = {}
        for c in kin:
            cy = float(c["y"]) + float(c["h"]) / 2
            match = next((r for r in parents
                          if r["top_y"] <= cy <= r["bottom_y"]), None)
            key = match["rank"] if match else None
            buckets.setdefault(key, (match, []))[1].append(c)
        for key, (parent_row, clist) in buckets.items():
            if parent_row is None:
                continue  # cell with no main-axis parent (rare) — drop
            clist = sorted(clist, key=lambda c: (c["x"], c["y"]))
            parent_row["n_cells"] = len(clist)
            for i, c in enumerate(clist):
                extra.append(_cell_row(c, trial_id, uid, batch, trial, doc_h,
                                       scr_h, parent_row, i, len(clist),
                                       True, parent_row["rank"]))

    # Off-axis dd_right covariate: a parent row for every right-rail block
    # plus its cells, all main_axis=False (filtered from main-axis analyses).
    dr_cells = sorted([c for c in cells if c["parent_kind"] == "dd_right"],
                      key=lambda c: (c["y"], c["x"]))
    for j, p in enumerate(dd_right_parents):
        top_y = float(p["y"])
        bot_y = top_y + float(p["h"])
        mine = dr_cells if j == 0 else []  # cells attach to first block (1 typical)
        pr = {
            "trial_id": trial_id, "uid": uid, "batch": batch, "trial": trial,
            "rank": -1, "etype": "dd_right", "organic_rank": None,
            "top_y": round(top_y, 2), "bottom_y": round(bot_y, 2),
            "center_y": round((top_y + bot_y) / 2, 2),
            "left_x": round(float(p["x"]), 2),
            "right_x": round(float(p["x"]) + float(p["w"]), 2),
            "n_total": None, "n_organic": None,
            "doc_height": doc_h, "screen_height": scr_h,
            "html_handle": None, "html_signature": "",
            "role": "parent", "cell_index": None, "n_cells": len(mine),
            "parent_rank": -1, "parent_etype": "dd_right", "main_axis": False,
        }
        extra.append(pr)
        for i, c in enumerate(mine):
            extra.append(_cell_row(c, trial_id, uid, batch, trial, doc_h,
                                   scr_h, pr, i, len(mine), False, -1))

    return base + extra


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
    if attribution == "typed":
        return rows_typed(trial_id, doc_h, scr_h, uid, batch, trial)
    if attribution == "typed_gapfill":
        return rows_typed(trial_id, doc_h, scr_h, uid, batch, trial,
                           gapfill=True)
    if attribution == "typed_gapfill_cellsplit":
        return rows_typed_cellsplit(trial_id, doc_h, scr_h, uid, batch, trial)
    raise ValueError(f"unknown attribution: {attribution!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution",
                        choices=["absolute", "organic", "organic_hybrid", "typed",
                                 "typed_gapfill", "typed_gapfill_cellsplit"],
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

    # Release provenance so a consumer can tell WHICH enrichment they hold.
    # The typed maps are rebuilt in place (docs/local-pack-aoi-shift.md), so a
    # bare CSV is otherwise indistinguishable from an older one.
    excl_path = ROOT / "data" / "aoi-typed" / "alignment-exclusions.json"
    excl = json.loads(excl_path.read_text()) if excl_path.exists() else {}
    summary = {
        "allserp_release": ALLSERP_RELEASE,
        "alignment_exclusions": {
            "n": len(excl.get("tids", [])),
            "date": excl.get("date"),
            "rule": excl.get("rule"),
            "tids": excl.get("tids", []),
        },
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
