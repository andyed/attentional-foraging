"""Extract organic-result bounding boxes from AdSERP full-page screenshots.

Row-projection CV detection: finds card-shaped regions in the main column of
the SERP, subtracts the shipped ad-boundary rectangles, and emits the remainder
as numbered organic results.

Outputs JSON per trial matching the AdSERP ad-boundary schema, with an added
`organic_result` key:

    {
      "organic_result": [{"position": 1, "location": {...}, "size": {...}}, ...],
      "native_ad":  [...passthrough from input...],
      "dd_top":     [...],
      "dd_right":   [...],
      "_meta": {"flags": ["card_3_suspiciously_tall"], ...}
    }

Run:
    uv run python scripts/extract_organic_bboxes.py p007-b6-t8 p013-b2-t3 ...
    uv run python scripts/extract_organic_bboxes.py --all-cached
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG_DIR = ROOT / "AdSERP" / "data" / "full-page-screenshots"
AD_DIR = ROOT / "AdSERP" / "data" / "ad-boundary-data"
OUT_DIR = ROOT / "AdSERP" / "data" / "organic-boundary-data"

# Main column geometry — derived from observed ad bboxes across the dataset.
# native_ad width=540, dd_top width=586. Use 586 as the conservative card width.
COL_X = 162
COL_W = 586
COL_RIGHT = COL_X + COL_W

# Row-projection thresholds.
ROW_STD_THRESHOLD = 3       # row "has content" if pixel std >= this
GAP_MERGE = 24              # merge runs separated by < this many gap rows
MIN_CARD_H = 50             # drop merged runs shorter than this
SUSPICIOUS_H = 350          # flag tall cards for human review (likely 2+ cards merged)
AD_OVERLAP_THRESHOLD = 0.5  # card is "an ad" if >= this fraction of its area overlaps any ad


def detect_cards(png_path: Path) -> list[tuple[int, int]]:
    """Return list of (y_top, y_bottom) for content runs in the main column."""
    img = np.array(Image.open(png_path).convert("L"))
    main = img[:, COL_X:COL_RIGHT]
    content = main.std(axis=1) >= ROW_STD_THRESHOLD

    # Find raw runs.
    diff = np.diff(content.astype(int))
    starts = list(np.where(diff == 1)[0] + 1)
    ends = list(np.where(diff == -1)[0] + 1)
    if content[0]:
        starts.insert(0, 0)
    if content[-1]:
        ends.append(len(content))

    # Merge runs separated by < GAP_MERGE rows (within-card text-line gaps).
    merged: list[tuple[int, int]] = []
    for s, e in zip(starts, ends):
        if merged and s - merged[-1][1] <= GAP_MERGE:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    return [(s, e) for s, e in merged if e - s >= MIN_CARD_H]


def subdivide_horizontal(png_path: Path, bbox: dict, *, min_cell_w: int = 60, peak_height_frac: float = 0.4, peak_distance: int = 80) -> list[dict]:
    """Vertical-edge peak detection. Use for horizontally-stacked elements
    like dd_top product carousels where columnar whitespace gaps don't
    exist (cards touch or have only sub-pixel separators).

    Sums the per-column horizontal-derivative magnitude (|dx|) across all
    rows in the bbox; strong vertical edges = product card boundaries.
    `scipy.signal.find_peaks` with `distance=peak_distance` enforces a
    minimum card width.

    Returns list of cell bboxes. Returns [] if fewer than 2 cells found.
    """
    from scipy import signal as _sig

    img = np.array(Image.open(png_path).convert("L")).astype(float)
    x = bbox["location"]["x"]
    y = bbox["location"]["y"]
    w = bbox["size"]["width"]
    h = bbox["size"]["height"]
    crop = img[y:y + h, x:x + w]
    if crop.size == 0 or crop.shape[1] < 2:
        return []

    edge_strength = np.abs(np.diff(crop, axis=1)).sum(axis=0)
    if edge_strength.max() == 0:
        return []
    peaks, _ = _sig.find_peaks(edge_strength, height=edge_strength.max() * peak_height_frac, distance=peak_distance)
    if len(peaks) < 2:
        return []

    cells: list[dict] = []
    for i in range(len(peaks) - 1):
        cs, ce = int(peaks[i]), int(peaks[i + 1])
        if ce - cs >= min_cell_w:
            cells.append({
                "position": len(cells) + 1,
                "location": {"x": int(x + cs), "y": int(y)},
                "size": {"height": int(h), "width": int(ce - cs)},
            })
    return cells if len(cells) >= 2 else []


def subdivide_vertical(png_path: Path, bbox: dict, *, min_cell_h: int = 50, gap_merge: int = 12, std_threshold: int = 3) -> list[dict]:
    """Row-projection sub-segmentation. Use for vertically-stacked elements
    like dd_right product columns. Same algorithm as detect_cards but
    constrained to a parent bbox."""
    img = np.array(Image.open(png_path).convert("L"))
    x = bbox["location"]["x"]
    y = bbox["location"]["y"]
    w = bbox["size"]["width"]
    h = bbox["size"]["height"]
    crop = img[y:y + h, x:x + w]
    if crop.size == 0:
        return []
    content = crop.std(axis=1) >= std_threshold

    diff = np.diff(content.astype(int))
    starts = list(np.where(diff == 1)[0] + 1)
    ends = list(np.where(diff == -1)[0] + 1)
    if content[0]:
        starts.insert(0, 0)
    if content[-1]:
        ends.append(len(content))

    merged: list[tuple[int, int]] = []
    for rs, re in zip(starts, ends):
        if merged and rs - merged[-1][1] <= gap_merge:
            merged[-1] = (merged[-1][0], re)
        else:
            merged.append((rs, re))

    cells: list[dict] = []
    for i, (rs, re) in enumerate(c for c in merged if c[1] - c[0] >= min_cell_h):
        cells.append({
            "position": i + 1,
            "location": {"x": int(x), "y": int(y + rs)},
            "size": {"height": int(re - rs), "width": int(w)},
        })
    return cells if len(cells) >= 2 else []


def overlap_fraction(card: tuple[int, int], ad_y: int, ad_h: int) -> float:
    """Return fraction of card height that overlaps the ad y-range."""
    cs, ce = card
    overlap = max(0, min(ce, ad_y + ad_h) - max(cs, ad_y))
    return overlap / max(1, ce - cs)


def is_ad(card: tuple[int, int], ads: dict) -> bool:
    for kind in ("native_ad", "dd_top", "dd_right"):
        for a in ads.get(kind, []):
            if overlap_fraction(card, a["location"]["y"], a["size"]["height"]) >= AD_OVERLAP_THRESHOLD:
                return True
    return False


def extract_trial(trial_id: str) -> dict | None:
    png = PNG_DIR / f"{trial_id}.png"
    ad_json = AD_DIR / f"{trial_id}.json"
    if not png.exists():
        print(f"  SKIP {trial_id}: png not found at {png}", file=sys.stderr)
        return None
    if not ad_json.exists():
        print(f"  SKIP {trial_id}: ad-boundary not found at {ad_json}", file=sys.stderr)
        return None

    ads = json.loads(ad_json.read_text())
    cards = detect_cards(png)

    organics: list[dict] = []
    flags: list[str] = []
    position = 0
    for s, e in cards:
        if is_ad((s, e), ads):
            continue
        position += 1
        organics.append({
            "position": position,
            "location": {"x": COL_X, "y": int(s)},
            "size": {"height": int(e - s), "width": COL_W},
        })
        if e - s >= SUSPICIOUS_H:
            flags.append(f"organic_{position}_suspiciously_tall_h={e - s}")

    # Sub-segment ads into per-product cells where the layout permits.
    # dd_top is a horizontal carousel → column-projection. dd_right is a
    # vertical product stack → row-projection. native_ad stays as-is
    # (it's a single text ad block at the dataset's intended granularity).
    dd_top_cells: list[dict] = []
    for parent in ads.get("dd_top", []):
        dd_top_cells.extend(subdivide_horizontal(png, parent))
    dd_right_cells: list[dict] = []
    for parent in ads.get("dd_right", []):
        dd_right_cells.extend(subdivide_vertical(png, parent))

    return {
        "organic_result": organics,
        "native_ad": ads.get("native_ad", []),
        "dd_top": ads.get("dd_top", []),
        "dd_right": ads.get("dd_right", []),
        "dd_top_cell": dd_top_cells,
        "dd_right_cell": dd_right_cells,
        "_meta": {
            "trial": trial_id,
            "card_count": len(cards),
            "organic_count": len(organics),
            "dd_top_cell_count": len(dd_top_cells),
            "dd_right_cell_count": len(dd_right_cells),
            "flags": flags,
            "params": {
                "col_x": COL_X, "col_w": COL_W,
                "row_std_threshold": ROW_STD_THRESHOLD,
                "gap_merge": GAP_MERGE, "min_card_h": MIN_CARD_H,
                "ad_overlap_threshold": AD_OVERLAP_THRESHOLD,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trials", nargs="*", help="trial IDs e.g. p007-b6-t8")
    parser.add_argument("--all-cached", action="store_true",
                        help="process every trial with a local PNG")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    trial_ids: list[str] = list(args.trials)
    if args.all_cached:
        trial_ids = sorted(p.stem for p in PNG_DIR.glob("*.png"))

    if not trial_ids:
        parser.error("provide trial IDs or --all-cached")

    print(f"Processing {len(trial_ids)} trials...")
    n_ok = 0
    for tid in trial_ids:
        result = extract_trial(tid)
        if result is None:
            continue
        out = OUT_DIR / f"{tid}.json"
        out.write_text(json.dumps(result, indent=2))
        meta = result["_meta"]
        flag_str = f" FLAGS: {meta['flags']}" if meta["flags"] else ""
        print(f"  {tid}: {meta['organic_count']} organic, {meta['card_count']} total cards{flag_str}")
        n_ok += 1

    print(f"\nWrote {n_ok}/{len(trial_ids)} → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
