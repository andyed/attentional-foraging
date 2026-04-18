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

    return {
        "organic_result": organics,
        "native_ad": ads.get("native_ad", []),
        "dd_top": ads.get("dd_top", []),
        "dd_right": ads.get("dd_right", []),
        "_meta": {
            "trial": trial_id,
            "card_count": len(cards),
            "organic_count": len(organics),
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
