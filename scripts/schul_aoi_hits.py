"""Project gaze into page space and compute per-sample AOI membership.

Input: one staged trial's gaze.json + scroll.json + aois.json + meta.json.
Output: aoi_hits.json containing

  meta:     { parameters, total_valid_samples, total_in_aoi_ms, ... }
  samples:  [ {t_ms, page_x, page_y, aoi_id (or null), valid} ]  — one per gaze sample
  summary:
    per_aoi:     {id: {hits, first_entry_ms, dwell_ms, visits, rank}}
    transitions: [{t_ms, from, to}]  — AOI change points (null = gaze outside any AOI)
    visit_log:   [{aoi_id, t_enter_ms, t_exit_ms, duration_ms}]
  ar_signal:   [{t_ms, aoi_id, rank, direction}]  — approach/retreat markers

AOI rank: derived from AOI id by pattern — organic `o\\d+` → n, text ad `tt\\d+` → -n, etc.
A 'visit' is a contiguous run of samples inside the same AOI (≥ min_visit_ms).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict, OrderedDict


def aoi_rank(aoi_id: str) -> tuple[str, int]:
    """Return (category, rank) for an AOI id.

    Categories:
      'organic'  — o01, o02c, o07a  → rank = numeric part (1..10)
      'text_ad'  — tt01, tt02, tto2  → rank = -n (negative keeps ads above organic)
      'shopping' — s01..s03 → rank = -10 - n
      'tail'     — tb01, tb02 → rank = 100 + n
      'other'    → rank = 999
    Sub-element suffix letters (o02c) don't change rank; the rank of o02c is 2.
    """
    m = re.match(r"o(\d+)", aoi_id)
    if m:
        return ("organic", int(m.group(1)))
    m = re.match(r"tto?(\d+)", aoi_id)
    if m:
        return ("text_ad", -int(m.group(1)))
    m = re.match(r"s(\d+)", aoi_id)
    if m:
        return ("shopping", -10 - int(m.group(1)))
    m = re.match(r"tb(\d+)", aoi_id)
    if m:
        return ("tail", 100 + int(m.group(1)))
    return ("other", 999)


def find_containing_aoi(px: float, py: float, aois: list[dict]) -> str | None:
    """Return the smallest-area AOI rect containing (px,py), or None."""
    hit = None
    best_area = float("inf")
    for a in aois:
        if a["x1"] <= px <= a["x2"] and a["y1"] <= py <= a["y2"]:
            area = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
            if area < best_area:
                best_area = area
                hit = a["id"]
    return hit


def interp_scroll(t_ms: float, scroll_samples: list[dict]) -> float:
    """Linear interpolation of scroll_y at t_ms from a time-sorted sample list."""
    if not scroll_samples:
        return 0.0
    if t_ms <= scroll_samples[0]["t_ms"]:
        return float(scroll_samples[0]["y_offset_px"])
    if t_ms >= scroll_samples[-1]["t_ms"]:
        return float(scroll_samples[-1]["y_offset_px"])
    # binary search
    lo, hi = 0, len(scroll_samples) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if scroll_samples[mid]["t_ms"] <= t_ms:
            lo = mid
        else:
            hi = mid
    a, b = scroll_samples[lo], scroll_samples[hi]
    if b["t_ms"] == a["t_ms"]:
        return float(a["y_offset_px"])
    frac = (t_ms - a["t_ms"]) / (b["t_ms"] - a["t_ms"])
    return a["y_offset_px"] + frac * (b["y_offset_px"] - a["y_offset_px"])


def compute(meta: dict, gaze: list[list], scroll: list[dict], aois: list[dict],
            min_visit_ms: int = 100) -> dict:
    sr = meta["scroll_recovery"]
    cx0, cy0, cx1, cy1 = sr["phone_crop_bounds"]
    scale = sr["scale_crop_to_ref"]
    crop_w = cx1 - cx0
    crop_h = cy1 - cy0

    # Rank-annotate AOIs (no mutation of input)
    rank_info = {a["id"]: aoi_rank(a["id"]) for a in aois}

    samples = []
    transitions = []
    visits = []  # [{aoi_id, t_enter, t_exit}]
    current_aoi: str | None = None
    visit_start_t: float | None = None
    last_inside_t: float | None = None

    for t_ms, gx, gy in gaze:
        valid = (gx != -1 and gy != -1)
        aoi_id: str | None = None
        page_x = page_y = None
        if valid:
            in_crop_x = gx - cx0
            in_crop_y = gy - cy0
            if 0 <= in_crop_x <= crop_w and 0 <= in_crop_y <= crop_h:
                scroll_y = interp_scroll(t_ms, scroll)
                page_x = in_crop_x * scale
                page_y = scroll_y + in_crop_y * scale
                aoi_id = find_containing_aoi(page_x, page_y, aois)
            else:
                valid = False  # gaze outside phone screen → treat as invalid for AOI purposes
        samples.append({
            "t_ms": t_ms,
            "valid": valid,
            "page_x": round(page_x, 1) if page_x is not None else None,
            "page_y": round(page_y, 1) if page_y is not None else None,
            "aoi_id": aoi_id,
        })
        # Track visits (close on change or end)
        if aoi_id != current_aoi:
            if current_aoi is not None and visit_start_t is not None and last_inside_t is not None:
                visits.append({
                    "aoi_id": current_aoi,
                    "t_enter_ms": visit_start_t,
                    "t_exit_ms": last_inside_t,
                    "duration_ms": last_inside_t - visit_start_t,
                })
            transitions.append({"t_ms": t_ms, "from": current_aoi, "to": aoi_id})
            current_aoi = aoi_id
            visit_start_t = t_ms if aoi_id is not None else None
        if aoi_id is not None:
            last_inside_t = t_ms

    # Close final visit
    if current_aoi is not None and visit_start_t is not None and last_inside_t is not None:
        visits.append({
            "aoi_id": current_aoi,
            "t_enter_ms": visit_start_t,
            "t_exit_ms": last_inside_t,
            "duration_ms": last_inside_t - visit_start_t,
        })

    # Filter sub-min-visit-ms visits (sample noise)
    visits = [v for v in visits if v["duration_ms"] >= min_visit_ms]

    # Per-AOI summary
    per_aoi: dict[str, dict] = OrderedDict()
    for a in aois:
        cat, rank = rank_info[a["id"]]
        per_aoi[a["id"]] = {
            "category": cat,
            "rank": rank,
            "visits": 0,
            "first_entry_ms": None,
            "dwell_ms": 0,
            "revisits": 0,  # visits beyond the first
        }
    for v in visits:
        e = per_aoi[v["aoi_id"]]
        e["visits"] += 1
        e["dwell_ms"] += v["duration_ms"]
        if e["first_entry_ms"] is None or v["t_enter_ms"] < e["first_entry_ms"]:
            e["first_entry_ms"] = v["t_enter_ms"]
    for e in per_aoi.values():
        e["revisits"] = max(0, e["visits"] - 1)

    total_valid = sum(1 for s in samples if s["valid"])
    total_in_aoi_ms = sum(v["duration_ms"] for v in visits)

    return {
        "meta": {
            "crop_bounds": [cx0, cy0, cx1, cy1],
            "scale_crop_to_ref": scale,
            "n_samples": len(samples),
            "n_valid": total_valid,
            "total_in_aoi_ms": total_in_aoi_ms,
            "n_visits": len(visits),
            "min_visit_ms": min_visit_ms,
        },
        "samples": samples,
        "summary": {
            "per_aoi": per_aoi,
            "transitions": transitions,
            "visit_log": visits,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, help="replay data dir (with gaze.json, scroll.json, aois.json, meta.json)")
    ap.add_argument("--out", default=None, help="output path (default: <data-dir>/aoi_hits.json)")
    ap.add_argument("--min-visit-ms", type=int, default=100)
    args = ap.parse_args()

    d = args.data_dir
    gaze = json.load(open(os.path.join(d, "gaze.json")))
    scroll = json.load(open(os.path.join(d, "scroll.json")))["samples"]
    aois = json.load(open(os.path.join(d, "aois.json")))
    meta = json.load(open(os.path.join(d, "meta.json")))

    result = compute(meta, gaze, scroll, aois, min_visit_ms=args.min_visit_ms)

    out_path = args.out or os.path.join(d, "aoi_hits.json")
    with open(out_path, "w") as f:
        json.dump(result, f)
    print(f"wrote {out_path}")

    # Summary to stdout
    rm = result["meta"]
    print(f"  samples: {rm['n_samples']} ({rm['n_valid']} valid)")
    print(f"  time in AOIs: {rm['total_in_aoi_ms']}ms across {rm['n_visits']} visits")
    print(f"\n  per-AOI dwell:")
    by_dwell = sorted(
        ((aid, e) for aid, e in result["summary"]["per_aoi"].items() if e["visits"] > 0),
        key=lambda x: -x[1]["dwell_ms"],
    )
    for aid, e in by_dwell[:10]:
        print(f"    {aid:>6}  ({e['category']:>8}  rank {e['rank']:>3})  "
              f"first@{e['first_entry_ms']:>6}ms  dwell {e['dwell_ms']:>4}ms  "
              f"visits {e['visits']}  revisits {e['revisits']}")
    print(f"\n  transitions ({len(result['summary']['transitions'])}):")
    last_non_none = None
    for tr in result["summary"]["transitions"][:30]:
        print(f"    t={tr['t_ms']:>6.0f}ms  {tr['from'] or '—':>6} → {tr['to'] or '—':<6}")


if __name__ == "__main__":
    main()
