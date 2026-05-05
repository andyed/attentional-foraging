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

Flavors:
    --flavor organic         (default) — tight row-projection bboxes
    --flavor organic_gapfill — apply midpoint-split to fill inter-result Y
                               gaps. See `apply_midpoint_split` and
                               docs/null-findings/2026-05-05-bbox-y-coverage.md.
                               Output dir: organic-boundary-data-gapfill/

Run:
    uv run python scripts/extract_organic_bboxes.py p007-b6-t8 p013-b2-t3 ...
    uv run python scripts/extract_organic_bboxes.py --all-cached
    uv run python scripts/extract_organic_bboxes.py --all-cached --flavor organic_gapfill
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PNG_DIR = ROOT / "AdSERP" / "data" / "full-page-screenshots"
AD_DIR = ROOT / "AdSERP" / "data" / "ad-boundary-data"
OUT_DIR_BY_FLAVOR = {
    "organic": ROOT / "AdSERP" / "data" / "organic-boundary-data",
    "organic_gapfill": ROOT / "AdSERP" / "data" / "organic-boundary-data-gapfill",
}

# Widget heading patterns. Bottom-of-page refinement widgets ("Related
# searches", "People also search for") emerge from detect_cards as
# pipeline-organics because they sit in the main column and don't overlap
# any shipped ad rectangle. Audit (2026-04-30, n=111) showed 41% of trials
# over-count due to this. Filter by HTML h3-title regex + band-y floor.
WIDGET_HEADING_RE = re.compile(
    r"^(related searches|people also search for|búsquedas relacionadas|"
    r"otras personas también buscan)\b",
    re.IGNORECASE,
)

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

# Composite-widget sub-segmentation (local pack, PAA, top-stories, etc).
# An organic taller than COMPOSITE_TRIGGER_H is fed into subdivide_vertical;
# emitted cells are kept only if subdivision finds >= 2 of them, otherwise
# the parent stays as a single organic_result.
COMPOSITE_TRIGGER_H = 320      # below SUSPICIOUS_H so most flagged tall cards get split
COMPOSITE_GAP_MERGE = 12       # tighter than top-level GAP_MERGE — sub-listings sit closer
COMPOSITE_MIN_CELL_H = 60      # filter sub-listing chrome (rating bars, divider lines)
COMPOSITE_STD_THRESHOLD = 3    # same as top-level row-projection


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

    Known limitation: misses low-contrast inter-card dividers AND fires on
    intra-card vertical edges (product-image silhouettes). A 5-card carousel
    can come out as 4 cells when one boundary is below `peak_height_frac`.
    Tried column-whitespace as an alternative and it found 0 cells (cards
    touch with no inter-card whitespace columns), so this remains the
    least-bad option. See methodology §6.6.

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
    """A pipeline-detected main-column card is an ad iff it overlaps a
    shipped ad rectangle in BOTH y AND x.

    The earlier (y-only) version silently marked main-column results as
    ads whenever a tall right-rail (dd_right) ad's y-span happened to
    cover them, dropping real organics from the output. With the x-overlap
    requirement, dd_right rails (x ≥ 750) no longer touch main-column
    cards (x = 162..748).
    """
    for kind in ("native_ad", "dd_top", "dd_right"):
        for a in ads.get(kind, []):
            ax = a["location"]["x"]
            aw = a["size"]["width"]
            if ax + aw <= COL_X or ax >= COL_RIGHT:
                continue
            if overlap_fraction(card, a["location"]["y"], a["size"]["height"]) >= AD_OVERLAP_THRESHOLD:
                return True
    return False


def find_widget_y_floor(trial_id: str) -> int | None:
    """Return the smallest estimated y-coordinate at which a refinement
    widget begins, or None if HTML is missing or no widget heading found.

    Widget heading text ("Related searches", "People also search for")
    lives in non-h3 elements (typically <span> or <div>), so we walk
    the DOM in document order, count h3 elements seen so far, and stop
    at the first descendant whose text matches the widget regex. The
    h3-count-before-widget is converted to a band-y estimate via
    absolute_rank_band_tops — not pixel-accurate, but sufficient as a
    floor: any pipeline-organic whose center sits at or below this y
    is widget territory.
    """
    sys.path.insert(0, str(ROOT / "notebooks-v2"))
    try:
        from bs4 import BeautifulSoup  # type: ignore
        from data_loader import get_trial_meta, absolute_rank_band_tops  # type: ignore
    except Exception:
        return None

    serp_path = ROOT / "AdSERP" / "data" / "serps" / f"{trial_id}.html"
    if not serp_path.exists():
        return None

    try:
        meta = get_trial_meta(trial_id)
    except Exception:
        return None
    doc_height = meta[0] if meta and meta[0] else None
    if not doc_height:
        return None

    soup = BeautifulSoup(serp_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    # Widget headings ("Related searches", "People also search for") sit in
    # the bottom-of-page container (often #bres / #w3bYAd), OUTSIDE #rso.
    # The HTML signal tells us widgets EXIST; the actual y-floor is found
    # via y-gap analysis on the pipeline organics (see _widget_floor_from_gap).
    all_h3s = soup.find_all("h3")
    if not all_h3s:
        return None

    has_widget_heading = any(
        WIDGET_HEADING_RE.match(h3.get_text(strip=True)) for h3 in all_h3s
    )
    if not has_widget_heading:
        return None

    # Conservative band-y estimate as a backstop. The y-gap analysis in
    # _widget_floor_from_gap is the primary signal; this is only used if
    # gap analysis is inconclusive.
    widget_h3_ord = next(
        (i for i, h3 in enumerate(all_h3s) if WIDGET_HEADING_RE.match(h3.get_text(strip=True))),
        None,
    )
    n_abs = len(all_h3s)
    band_tops = absolute_rank_band_tops(n_abs, doc_height)
    if widget_h3_ord is None or widget_h3_ord >= len(band_tops):
        return int(band_tops[-1])
    return int(band_tops[widget_h3_ord])


def _widget_floor_from_gap(organic_spans) -> int | None:
    """Return the y of the first card after the largest anomalous
    inter-card whitespace gap, or None if no anomaly is found.

    `organic_spans` is a list of (y_top, y_bottom) tuples.

    Real organic results are vertically packed; inter-card whitespace
    between adjacent organics is typically 5–60 px. When pipeline-organics
    include trailing refinement widgets, a much larger empty band
    separates the last real organic (bottom edge) from the first widget
    (top edge). Using (next_top - prev_bottom) instead of (next_top -
    prev_top) avoids false positives from a single tall organic creating
    a fake start-to-start gap.

    Floor is returned only when the largest whitespace gap is both:
      - > 3× the median gap (clearly anomalous vs. typical card spacing)
      - > 150 px (absolute floor; below this, gaps are routine layout noise)
    """
    if len(organic_spans) < 3:
        return None
    spans = sorted(organic_spans)  # sorts by y_top
    gaps = [
        (spans[i + 1][0] - spans[i][1], spans[i + 1][0])
        for i in range(len(spans) - 1)
    ]
    if not gaps:
        return None
    sorted_gap_sizes = sorted(g[0] for g in gaps)
    median_gap = max(sorted_gap_sizes[len(sorted_gap_sizes) // 2], 1)
    max_gap, floor_y = max(gaps, key=lambda x: x[0])
    if max_gap > max(150, 3.0 * median_gap):
        return int(floor_y)
    return None


def apply_midpoint_split(
    organics: list[dict],
    obstacles: list[tuple[int, int]] | None = None,
) -> list[dict]:
    """Extend each organic's Y extent to fill inter-result gaps via midpoint
    split. Pragmatic post-processing for the `organic_gapfill` flavor.

    For each adjacent pair of organics (sorted by Y), divide the inter-result
    gap at its center: the upper bbox's bottom extends down to (midpoint - 1)
    and the lower bbox's top extends up to (midpoint + 1). Every Y pixel
    between the first organic's top and the last organic's bottom belongs to
    exactly one bbox.

    Skip / clamp the split where an obstacle (widget, dd_top, native_ad,
    dd_right) sits in the gap — never extend an organic across an ad/widget
    rectangle.

    Don't extend the first organic's top (would expand into chrome/header) or
    the last organic's bottom (would expand into pagination / refinement).

    Returns a NEW list of dicts; does not mutate input.

    See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#4 midpoint-split
    decision)
    """
    if len(organics) < 2:
        return [
            {**o, "location": dict(o["location"]), "size": dict(o["size"])}
            for o in organics
        ]

    obstacles = obstacles or []

    # Deep-copy so we don't mutate caller's data
    sorted_organics = sorted(
        ({**o, "location": dict(o["location"]), "size": dict(o["size"])}
         for o in organics),
        key=lambda o: o["location"]["y"],
    )

    for i in range(len(sorted_organics) - 1):
        upper = sorted_organics[i]
        lower = sorted_organics[i + 1]
        u_top = upper["location"]["y"]
        u_bot = u_top + upper["size"]["height"]
        l_top = lower["location"]["y"]
        l_bot = l_top + lower["size"]["height"]

        gap = l_top - u_bot
        if gap <= 0:
            continue  # no gap or already touching

        midpoint = u_bot + gap // 2

        # If an obstacle sits in the gap, clamp the split to its boundaries
        # (the upper bbox stops at obstacle.top - 1; the lower bbox starts
        # at obstacle.bottom + 1).
        upper_cap = midpoint - 1
        lower_floor = midpoint + 1
        for o_top, o_bot in obstacles:
            if u_bot < o_bot and o_top < l_top:
                # Obstacle overlaps the gap.
                if o_top - 1 < upper_cap:
                    upper_cap = o_top - 1
                if o_bot + 1 > lower_floor:
                    lower_floor = o_bot + 1

        # Only extend (never shrink) — guard against pathological cases.
        if upper_cap > u_bot:
            upper["size"]["height"] = upper_cap - u_top
        if lower_floor < l_top:
            lower["location"]["y"] = lower_floor
            lower["size"]["height"] = l_bot - lower_floor

    # Restore original position ordering
    sorted_organics.sort(key=lambda o: o["position"])
    return sorted_organics


def assert_no_y_overlap(organics: list[dict]) -> None:
    """Sanity check: no two organics overlap in Y after midpoint-split."""
    if len(organics) < 2:
        return
    sorted_o = sorted(organics, key=lambda o: o["location"]["y"])
    for i in range(len(sorted_o) - 1):
        a_bot = sorted_o[i]["location"]["y"] + sorted_o[i]["size"]["height"]
        b_top = sorted_o[i + 1]["location"]["y"]
        if a_bot >= b_top:
            raise AssertionError(
                f"Y-overlap after gapfill: organic at y={sorted_o[i]['location']['y']} "
                f"extends to y={a_bot}, but next organic starts at y={b_top}"
            )


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
    widget_y_floor_html = find_widget_y_floor(trial_id)

    # Pre-compute the post-ad-subtraction card list so we can derive a
    # data-driven y-floor from the actual organic layout. This is more
    # accurate than the band-y estimate because real organic spacing is
    # not uniform — band estimation puts the floor too low on dense
    # SERPs and misses widget content sitting above the band-y line.
    candidate_organics: list[tuple[int, int]] = [
        (s, e) for s, e in cards if not is_ad((s, e), ads)
    ]
    widget_y_floor_gap: int | None = None
    if widget_y_floor_html is not None and len(candidate_organics) >= 3:
        widget_y_floor_gap = _widget_floor_from_gap(candidate_organics)
    # Prefer the gap-derived floor (sharper, layout-aware) WHEN it's
    # plausibly near the band-y position of the widget heading. The gap
    # heuristic can fire on featured-snippet-to-organics transitions
    # (album Knowledge Graph at top → real organics below), in which
    # case its floor is much earlier than the HTML widget heading
    # actually sits. Reject gap floors that are < 60% of the band-y
    # estimate; fall back to the band-y backstop.
    if (
        widget_y_floor_gap is not None
        and widget_y_floor_html is not None
        and widget_y_floor_gap < 0.6 * widget_y_floor_html
    ):
        widget_y_floor_gap = None
    widget_y_floor = (
        widget_y_floor_gap if widget_y_floor_gap is not None else widget_y_floor_html
    )

    organics: list[dict] = []
    widgets: list[dict] = []
    flags: list[str] = []
    position = 0
    for s, e in candidate_organics:
        # Reject anything whose top sits at or beyond the widget y-floor.
        # The floor is the y of the FIRST widget card (after the gap), so
        # use the top edge rather than center to keep widgets out cleanly.
        if widget_y_floor is not None and s >= widget_y_floor:
            widgets.append({
                "position": len(widgets) + 1,
                "location": {"x": COL_X, "y": int(s)},
                "size": {"height": int(e - s), "width": COL_W},
                "reason": "below_widget_y_floor",
            })
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

    # Composite-widget sub-segmentation: any organic taller than
    # COMPOSITE_TRIGGER_H is candidate-split via row-projection inside
    # the parent. Local-3-packs, PAA, top-stories, and inline image
    # carousels emerge from detect_cards as a single organic; this pass
    # recovers per-sub-listing AOIs. Each cell carries its parent's
    # organic position so downstream code can group cells back.
    organic_cells: list[dict] = []
    for parent in organics:
        if parent["size"]["height"] < COMPOSITE_TRIGGER_H:
            continue
        cells = subdivide_vertical(
            png, parent,
            min_cell_h=COMPOSITE_MIN_CELL_H,
            gap_merge=COMPOSITE_GAP_MERGE,
            std_threshold=COMPOSITE_STD_THRESHOLD,
        )
        for cell in cells:
            cell["parent_position"] = parent["position"]
            organic_cells.append(cell)

    return {
        "organic_result": organics,
        "widget": widgets,
        "native_ad": ads.get("native_ad", []),
        "dd_top": ads.get("dd_top", []),
        "dd_right": ads.get("dd_right", []),
        "dd_top_cell": dd_top_cells,
        "dd_right_cell": dd_right_cells,
        "organic_cell": organic_cells,
        "_meta": {
            "trial": trial_id,
            "card_count": len(cards),
            "organic_count": len(organics),
            "widget_count": len(widgets),
            "widget_y_floor": widget_y_floor,
            "dd_top_cell_count": len(dd_top_cells),
            "dd_right_cell_count": len(dd_right_cells),
            "organic_cell_count": len(organic_cells),
            "flags": flags,
            "params": {
                "col_x": COL_X, "col_w": COL_W,
                "row_std_threshold": ROW_STD_THRESHOLD,
                "gap_merge": GAP_MERGE, "min_card_h": MIN_CARD_H,
                "ad_overlap_threshold": AD_OVERLAP_THRESHOLD,
                "composite_trigger_h": COMPOSITE_TRIGGER_H,
                "composite_gap_merge": COMPOSITE_GAP_MERGE,
                "composite_min_cell_h": COMPOSITE_MIN_CELL_H,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trials", nargs="*", help="trial IDs e.g. p007-b6-t8")
    parser.add_argument("--all-cached", action="store_true",
                        help="process every trial with a local PNG")
    parser.add_argument(
        "--flavor", choices=list(OUT_DIR_BY_FLAVOR.keys()),
        default="organic",
        help="organic = tight bboxes (legacy); organic_gapfill = midpoint-split applied",
    )
    args = parser.parse_args()

    out_dir = OUT_DIR_BY_FLAVOR[args.flavor]
    out_dir.mkdir(parents=True, exist_ok=True)

    trial_ids: list[str] = list(args.trials)
    if args.all_cached:
        trial_ids = sorted(p.stem for p in PNG_DIR.glob("*.png"))

    if not trial_ids:
        parser.error("provide trial IDs or --all-cached")

    print(f"Processing {len(trial_ids)} trials, flavor={args.flavor}...")
    n_ok = 0
    n_gapfilled = 0
    for tid in trial_ids:
        result = extract_trial(tid)
        if result is None:
            continue

        if args.flavor == "organic_gapfill":
            # Build obstacle list from non-organic rectangles in the trial:
            # widgets, dd_top, native_ad, dd_right. Any of these sitting in
            # the inter-organic gap clamps the midpoint-split.
            obstacles: list[tuple[int, int]] = []
            for kind in ("widget", "dd_top", "native_ad", "dd_right"):
                for r in result.get(kind, []):
                    oy = r["location"]["y"]
                    oh = r["size"]["height"]
                    obstacles.append((oy, oy + oh))

            tight = result["organic_result"]
            gapfilled = apply_midpoint_split(tight, obstacles)
            assert_no_y_overlap(gapfilled)
            result["organic_result"] = gapfilled
            result["_meta"]["gapfill_applied"] = True
            n_gapfilled += 1
        else:
            result["_meta"]["gapfill_applied"] = False

        out = out_dir / f"{tid}.json"
        out.write_text(json.dumps(result, indent=2))
        meta = result["_meta"]
        flag_str = f" FLAGS: {meta['flags']}" if meta["flags"] else ""
        print(f"  {tid}: {meta['organic_count']} organic, {meta['card_count']} total cards{flag_str}")
        n_ok += 1

    print(f"\nWrote {n_ok}/{len(trial_ids)} → {out_dir}")
    if args.flavor == "organic_gapfill":
        print(f"  ({n_gapfilled} trials had midpoint-split applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
