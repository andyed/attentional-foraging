"""Score all 2,776 AdSERP trials for the approach-retreat signal testbed.

Pass 1: cursor-only features (no AOI bboxes required). Fast — runs in
under a minute against the local cache.

Composite score targets trials that EXPOSE the four-class inference
problem: dense cursor, multiple distinct y-bands visited, re-visits to
the same band (proxy for DEFERRED), trial duration in the deliberation
sweet spot, terminating click present.

Output: AdSERP/data/trial-scores.csv, sorted by score desc. Pick top N
for organic-bbox extraction (Pass 2) and final testbed selection.
"""
from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "AdSERP" / "data"
MOUSE = DATA / "mouse-movement-data"
FIX = DATA / "fixation-data"
PUPIL = DATA / "pupil-data"
META = DATA / "trial-metadata"
OUT = DATA / "trial-scores.csv"

Y_BAND_PX = 100  # bin cursor y into bands this tall to detect "same region"


def score_trial(trial_id: str) -> dict | None:
    mouse_path = MOUSE / f"{trial_id}.csv"
    if not mouse_path.exists():
        return None

    n_mousemove = 0
    has_click = False
    click_y = None
    max_y = 0
    min_y = float("inf")
    band_visits: dict[int, int] = {}      # band -> visit count
    last_band: int | None = None
    band_revisits = 0
    visited_bands: set[int] = set()
    t_first = None
    t_last = None

    with mouse_path.open() as fh:
        for row in csv.DictReader(fh):
            event = row["event"]
            t = int(row["timestamp"])
            try:
                y = int(float(row["ypos"]))
            except (KeyError, ValueError):
                continue
            if t_first is None:
                t_first = t
            t_last = t
            if event == "click" or event == "mousedown":
                if not has_click:
                    has_click = True
                    click_y = y
            if event != "mousemove":
                continue
            n_mousemove += 1
            if y > max_y:
                max_y = y
            if y < min_y:
                min_y = y
            band = y // Y_BAND_PX
            if band != last_band:
                # Re-entry to a band already visited
                if band in visited_bands and last_band is not None:
                    band_revisits += 1
                visited_bands.add(band)
                band_visits[band] = band_visits.get(band, 0) + 1
                last_band = band

    duration_ms = (t_last - t_first) if (t_first and t_last) else 0
    distinct_bands = len(visited_bands)

    # Fixation count (cheap)
    n_fix = 0
    fix_path = FIX / f"{trial_id}.csv"
    if fix_path.exists():
        with fix_path.open() as fh:
            n_fix = sum(1 for _ in fh) - 1

    # Pupil dropout rate (LPV/RPV columns)
    n_pupil = 0
    n_pupil_valid = 0
    pupil_path = PUPIL / f"{trial_id}.csv"
    if pupil_path.exists():
        with pupil_path.open() as fh:
            r = csv.DictReader(fh)
            for row in r:
                n_pupil += 1
                if row.get("LPV") == "1" or row.get("RPV") == "1":
                    n_pupil_valid += 1
    dropout = 1.0 - (n_pupil_valid / n_pupil) if n_pupil else 1.0

    # Window width (for x-scaling reference)
    win_w = 1280
    meta_path = META / f"{trial_id}.xml"
    if meta_path.exists():
        try:
            root = ET.fromstring(meta_path.read_text())
            win = root.findtext("window") or "1280x1024"
            win_w = int(win.split("x")[0])
        except (ET.ParseError, ValueError):
            pass

    # Composite score in [0, 1]-ish
    def norm(v: float, lo: float, hi: float) -> float:
        return max(0.0, min(1.0, (v - lo) / (hi - lo)))

    score = (
        0.20 * norm(n_mousemove, 50, 400)
        + 0.25 * norm(distinct_bands, 2, 8)
        + 0.25 * norm(band_revisits, 0, 6)
        + 0.15 * norm(duration_ms, 5000, 25000)
        + 0.15 * (1.0 if has_click else 0.0)
    )
    # Penalty: bad pupil signal
    score *= (1.0 - 0.5 * dropout)

    return {
        "trial_id": trial_id,
        "score": round(score, 4),
        "n_mousemove": n_mousemove,
        "n_fixations": n_fix,
        "duration_ms": duration_ms,
        "distinct_y_bands": distinct_bands,
        "y_band_revisits": band_revisits,
        "has_click": int(has_click),
        "click_y": click_y if click_y is not None else "",
        "y_extent": max_y - (min_y if min_y != float("inf") else 0),
        "pupil_dropout": round(dropout, 3),
        "n_pupil_samples": n_pupil,
        "win_width": win_w,
    }


def main() -> int:
    trial_ids = sorted(p.stem for p in MOUSE.glob("p*.csv"))
    print(f"Scoring {len(trial_ids)} trials...")
    rows: list[dict] = []
    for i, tid in enumerate(trial_ids):
        r = score_trial(tid)
        if r is None:
            continue
        rows.append(r)
        if (i + 1) % 250 == 0:
            print(f"  {i + 1}/{len(trial_ids)}")
    rows.sort(key=lambda r: r["score"], reverse=True)
    fields = list(rows[0].keys())
    with OUT.open("w") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows → {OUT}")
    print("\nTop 20:")
    print(f"  {'trial':<14} {'score':>6} {'cur':>4} {'fix':>4} {'dur':>6} {'bands':>5} {'rev':>3} {'clk':>3}")
    for r in rows[:20]:
        print(f"  {r['trial_id']:<14} {r['score']:>6.3f} {r['n_mousemove']:>4} {r['n_fixations']:>4} {r['duration_ms']:>6} {r['distinct_y_bands']:>5} {r['y_band_revisits']:>3} {r['has_click']:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
