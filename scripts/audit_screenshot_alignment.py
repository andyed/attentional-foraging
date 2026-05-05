"""Use shipped AdSERP ad rectangles as a screenshot-alignment ground truth.

The shipped ad rects (`AdSERP/data/ad-boundary-data/{tid}.json`) were
extracted by the original authors against the same screenshots that the
gaze/cursor streams were recorded against. They provide a calibration
anchor: if click and fixation coordinates are screenshot-aligned, they
should fall either CLEARLY inside ad rects (negative signed distance to
nearest edge) or CLEARLY outside (positive). Accumulation just-outside
ad edges = misalignment by that offset.

Regime tag: [LAB, AdSERP, alignment-audit-2026-05-05]
Headline: 442 final clicks land inside shipped ad rects (median signed Y
to nearest edge = -84 px, deep inside); near-edge histogram shows ~4:1
ratio of inside vs outside (152 vs 39 in [-50, +50] px band). Fixation
distribution is consistent (~2:1 ratio inside vs outside near-edge).
Conclusion: data is screenshot-aligned. Refutes coordinate-space drift
hypothesis raised by replay-viewer alignment concern 2026-05-05.

See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#2.5 alignment
audit, post-publication addition)

Reports:
  (1) For all final clicks: histogram of signed Y distance to nearest ad
      rect edge (negative = inside ad).
  (2) For all final clicks within 50px of an ad rect (border zone): is the
      signed distribution symmetric (no bias) or skewed (alignment offset)?
  (3) Same metric for fixations.
  (4) Per-ad-type breakdown (dd_top, native_ad, dd_right).

Tag: [LAB, AdSERP, alignment-audit-2026-05-05]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import load_fixations, load_mouse_events  # noqa: E402

AD_DIR = ROOT / "AdSERP" / "data" / "ad-boundary-data"


def load_ad_rects(tid):
    """Return list of (kind, x_top, y_top, x_bot, y_bot) for all shipped ad rects."""
    f = AD_DIR / f"{tid}.json"
    if not f.exists():
        return []
    d = json.load(open(f))
    out = []
    for kind in ("dd_top", "native_ad", "dd_right"):
        for r in d.get(kind, []):
            x = r["location"]["x"]
            y = r["location"]["y"]
            w = r["size"]["width"]
            h = r["size"]["height"]
            out.append((kind, x, y, x + w, y + h))
    return out


def signed_distance_to_nearest_rect(px, py, rects):
    """Return (signed_y, signed_x, kind) for the nearest ad rect.

    Negative signed_y = inside the rect's Y span; signed_y > 0 = px is
    distance from nearest top/bottom edge along Y. Same for X.

    Returns (None, None, None) if no ad rects.
    """
    if not rects:
        return None, None, None
    best = None
    best_score = float("inf")
    for kind, x0, y0, x1, y1 in rects:
        # Distance to nearest edge of this rect (signed: negative inside)
        dx = max(x0 - px, px - x1, 0)
        dy = max(y0 - py, py - y1, 0)
        # Combined euclidean for tiebreak
        score = (dx * dx + dy * dy) if (dx > 0 or dy > 0) else \
                -min(px - x0, x1 - px, py - y0, y1 - py)
        if score < best_score:
            best_score = score
            # Compute signed Y and X to nearest edge
            sy = (
                py - y0 if abs(py - y0) < abs(py - y1) else py - y1
            ) if not (y0 <= py <= y1) else (
                # Inside Y span; use distance to nearer edge as signed (negative)
                -(min(py - y0, y1 - py))
            )
            sx = (
                px - x0 if abs(px - x0) < abs(px - x1) else px - x1
            ) if not (x0 <= px <= x1) else (
                -(min(px - x0, x1 - px))
            )
            best = (sy, sx, kind)
    return best


def in_rect(px, py, rects):
    for kind, x0, y0, x1, y1 in rects:
        if x0 <= px <= x1 and y0 <= py <= y1:
            return kind
    return None


def main():
    click_offsets = []  # list of (signed_y, signed_x, kind, in_rect_kind)
    fix_offsets = []

    n_trials = 0
    for f in sorted(AD_DIR.glob("*.json")):
        tid = f.stem
        rects = load_ad_rects(tid)
        if not rects:
            continue
        try:
            mouse = load_mouse_events(tid)
            fixations = load_fixations(tid)
        except Exception:
            continue
        if mouse is None or fixations is None:
            continue
        _, _, clicks = mouse
        n_trials += 1

        # Final click only
        if clicks:
            final = clicks[-1]
            if len(final) >= 3:
                cx, cy = float(final[1]), float(final[2])
                sy, sx, near_kind = signed_distance_to_nearest_rect(cx, cy, rects)
                inside = in_rect(cx, cy, rects)
                if sy is not None:
                    click_offsets.append((sy, sx, near_kind, inside))

        # Sample one fixation per trial to keep things bounded
        # — pick the fixation with longest dwell as representative
        if fixations:
            best_fix = max(fixations, key=lambda f: f.get("d", 0) if isinstance(f, dict) else f[3])
            if isinstance(best_fix, dict):
                fx, fy = float(best_fix["x"]), float(best_fix["y"])
            else:
                fx, fy = float(best_fix[1]), float(best_fix[2])
            sy, sx, near_kind = signed_distance_to_nearest_rect(fx, fy, rects)
            inside = in_rect(fx, fy, rects)
            if sy is not None:
                fix_offsets.append((sy, sx, near_kind, inside))

    print(f"trials examined: {n_trials:,}")

    def report(label, offsets):
        print(f"\n=== {label} ===")
        sy = np.array([o[0] for o in offsets])
        sx = np.array([o[1] for o in offsets])
        n_inside = sum(1 for o in offsets if o[3] is not None)
        n_outside = len(offsets) - n_inside
        print(f"  total: {len(offsets):,}  (inside ad rect: {n_inside:,}, outside: {n_outside:,})")

        # Border zone: |sy| <= 50 AND outside the rect
        border_mask = np.array([(0 < o[0] <= 50) for o in offsets])
        if border_mask.sum() > 0:
            border_sy = sy[border_mask]
            print(f"\n  Border zone (1-50 px outside ad rect Y): n={len(border_sy):,}")
            print(f"    signed Y to nearest ad edge:")
            print(f"      median: {np.median(border_sy):.1f}")
            print(f"      mean:   {np.mean(border_sy):.1f}")
            print(f"      p10/25/50/75/90: "
                  f"{np.percentile(border_sy, 10):.1f} / "
                  f"{np.percentile(border_sy, 25):.1f} / "
                  f"{np.percentile(border_sy, 50):.1f} / "
                  f"{np.percentile(border_sy, 75):.1f} / "
                  f"{np.percentile(border_sy, 90):.1f}")

        # Among all (inside + within-100-of-rect): position within bbox by Y
        # If alignment is correct, clicks ON ads should have signed_y < 0 (inside)
        # and the negative distribution should be symmetric within the rect.
        inside_mask = np.array([o[3] is not None for o in offsets])
        if inside_mask.sum() > 0:
            inside_sy = sy[inside_mask]
            print(f"\n  Inside ad rect: n={inside_sy.size:,}")
            print(f"    signed Y to nearest ad edge (negative = inside):")
            print(f"      median: {np.median(inside_sy):.1f}")
            print(f"      mean:   {np.mean(inside_sy):.1f}")
            print(f"      p10/50/90: "
                  f"{np.percentile(inside_sy, 10):.1f} / "
                  f"{np.percentile(inside_sy, 50):.1f} / "
                  f"{np.percentile(inside_sy, 90):.1f}")

        # Histogram of signed Y by ±5 px buckets near zero (the diagnostic zone)
        # If alignment is off by N px, clicks would accumulate at sy ≈ +N (just outside)
        print(f"\n  Histogram bucket counts near zero (signed Y to ad edge, all rects):")
        edges = list(range(-50, 51, 10))
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            cnt = int(((sy >= lo) & (sy < hi)).sum())
            print(f"    [{lo:>+4d}, {hi:>+4d}): {cnt:>5,d}")

        # Per-ad-type breakdown of clicks just-outside (1-30 px)
        just_outside_mask = (sy > 0) & (sy <= 30)
        if just_outside_mask.sum() > 0:
            print(f"\n  Just-outside ad rect (1-30 px below or above ad edge):")
            kinds = Counter(o[2] for o, m in zip(offsets, just_outside_mask) if m)
            for k, n in kinds.most_common():
                print(f"    near {k}: {n:,}")

    report("FINAL CLICKS vs shipped ad rects", click_offsets)
    report("LONGEST FIXATION per trial vs shipped ad rects", fix_offsets)


if __name__ == "__main__":
    main()
