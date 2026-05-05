"""Apply midpoint-split gapfill to already-extracted organic bboxes.

Reads AdSERP/data/organic-boundary-data/{tid}.json (legacy tight bboxes) and
writes AdSERP/data/organic-boundary-data-gapfill/{tid}.json with the
midpoint-split applied to organic_result. All other keys (widget, native_ad,
dd_top, dd_right, dd_top_cell, dd_right_cell, organic_cell, _meta) are passed
through unchanged.

This is the no-screenshot path — useful when /Volumes/andyed (where
full-page-screenshots/ symlinks to) is not mounted. The CV extraction is
deterministic and already cached on disk; the gapfill is a pure post-process
on bboxes that doesn't need the PNG.

If you have the screenshots and want the canonical pipeline, use:
    extract_organic_bboxes.py --all-cached --flavor organic_gapfill

Regime tag: [LAB, AdSERP, organic_gapfill]
See: docs/null-findings/2026-05-05-bbox-y-coverage.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from extract_organic_bboxes import (  # noqa: E402
    apply_midpoint_split, assert_no_y_overlap,
)

SRC = ROOT / "AdSERP" / "data" / "organic-boundary-data"
DST = ROOT / "AdSERP" / "data" / "organic-boundary-data-gapfill"


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    src_files = sorted(SRC.glob("*.json"))
    print(f"applying midpoint-split to {len(src_files)} trials...")

    n_ok = 0
    n_nochange = 0
    n_widened = 0
    height_deltas = []  # bottom_y delta per organic
    for f in src_files:
        result = json.loads(f.read_text())
        tight = result.get("organic_result", [])
        if not tight:
            # No organics; pass through unchanged
            (DST / f.name).write_text(json.dumps(result, indent=2))
            n_ok += 1
            n_nochange += 1
            continue

        # Build obstacle list
        obstacles: list[tuple[int, int]] = []
        for kind in ("widget", "dd_top", "native_ad", "dd_right"):
            for r in result.get(kind, []):
                oy = r["location"]["y"]
                oh = r["size"]["height"]
                obstacles.append((oy, oy + oh))

        gapfilled = apply_midpoint_split(tight, obstacles)
        try:
            assert_no_y_overlap(gapfilled)
        except AssertionError as e:
            print(f"  ASSERT FAIL on {f.stem}: {e}")
            continue

        # Track delta for verification
        for tight_o, fill_o in zip(tight, gapfilled):
            tight_bot = tight_o["location"]["y"] + tight_o["size"]["height"]
            fill_bot = fill_o["location"]["y"] + fill_o["size"]["height"]
            tight_top = tight_o["location"]["y"]
            fill_top = fill_o["location"]["y"]
            d_bot = fill_bot - tight_bot
            d_top = fill_top - tight_top
            if d_bot != 0 or d_top != 0:
                height_deltas.append(d_bot - d_top)
                n_widened += 1

        result["organic_result"] = gapfilled
        result.setdefault("_meta", {})["gapfill_applied"] = True

        (DST / f.name).write_text(json.dumps(result, indent=2))
        n_ok += 1

    print(f"\nwrote {n_ok}/{len(src_files)} → {DST}")
    print(f"  organics widened (bottom or top moved): {n_widened:,}")
    if height_deltas:
        import statistics
        print(f"  height delta median: "
              f"{statistics.median(height_deltas):.1f} px")
        print(f"  height delta mean: "
              f"{statistics.mean(height_deltas):.1f} px")
        print(f"  height delta max: {max(height_deltas)} px")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
