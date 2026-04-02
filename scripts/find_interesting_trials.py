#!/usr/bin/env python3
"""
Analyze AdSERP eye-tracking dataset and produce a catalog of interesting trials.
Iterates all 2,776 trials, computes behavioral metrics, assigns tags, and writes
a filtered JSON output containing only tagged trials plus prototypical examples.

Stdlib only — no pandas/numpy.
"""

import csv
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "AdSERP", "data")
FIX_DIR = os.path.join(DATA_DIR, "fixation-data")
MOUSE_DIR = os.path.join(DATA_DIR, "mouse-movement-data")
META_DIR = os.path.join(DATA_DIR, "trial-metadata")
AD_DIR = os.path.join(DATA_DIR, "ad-boundary-data")
OUT_PATH = os.path.join(DATA_DIR, "interesting-trials.json")


def parse_trial_id(filename):
    """Extract participant, batch, trial from filename like p004-b1-t1."""
    m = re.match(r"(p\d+)-b(\d+)-t(\d+)", filename)
    if not m:
        return None, None, None
    return m.group(1), int(m.group(2)), int(m.group(3))


def load_fixations(trial_id):
    """Return list of (timestamp, x, y, duration) tuples."""
    path = os.path.join(FIX_DIR, f"{trial_id}.csv")
    fixations = []
    try:
        with open(path, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return fixations
            for row in reader:
                if len(row) < 4:
                    continue
                try:
                    ts = float(row[0])
                    x = float(row[1])
                    y = float(row[2])
                    d = float(row[3])
                    fixations.append((ts, x, y, d))
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        pass
    return fixations


def load_mouse_events(trial_id):
    """Return list of (timestamp, xpos, ypos, event, xpath) tuples."""
    path = os.path.join(MOUSE_DIR, f"{trial_id}.csv")
    events = []
    try:
        with open(path, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return events
            for row in reader:
                if len(row) < 4:
                    continue
                try:
                    ts = float(row[0])
                    xpos = float(row[1])
                    ypos = float(row[2])
                    event = row[3] if len(row) > 3 else ""
                    xpath = row[4] if len(row) > 4 else ""
                    events.append((ts, xpos, ypos, event, xpath))
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        pass
    return events


def load_metadata(trial_id):
    """Return dict with url, screen, window, document dims, task."""
    path = os.path.join(META_DIR, f"{trial_id}.xml")
    result = {
        "url": "",
        "query": "",
        "page_width": 0,
        "page_height": 0,
        "screen_width": 0,
        "screen_height": 0,
        "window_width": 0,
        "window_height": 0,
    }
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        url_el = root.find("url")
        if url_el is not None and url_el.text:
            result["url"] = url_el.text
            parsed = urlparse(url_el.text)
            qs = parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            result["query"] = q.replace("-", " ")

        doc_el = root.find("document")
        if doc_el is not None and doc_el.text:
            parts = doc_el.text.split("x")
            if len(parts) == 2:
                try:
                    result["page_width"] = int(parts[0])
                    result["page_height"] = int(parts[1])
                except ValueError:
                    pass

        screen_el = root.find("screen")
        if screen_el is not None and screen_el.text:
            parts = screen_el.text.split("x")
            if len(parts) == 2:
                try:
                    result["screen_width"] = int(parts[0])
                    result["screen_height"] = int(parts[1])
                except ValueError:
                    pass

        window_el = root.find("window")
        if window_el is not None and window_el.text:
            parts = window_el.text.split("x")
            if len(parts) == 2:
                try:
                    result["window_width"] = int(parts[0])
                    result["window_height"] = int(parts[1])
                except ValueError:
                    pass

    except (FileNotFoundError, ET.ParseError):
        pass
    return result


def load_ad_boundaries(trial_id):
    """Return dict with keys native_ad, dd_top, dd_right, each a list of rects."""
    path = os.path.join(AD_DIR, f"{trial_id}.json")
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ad_rects_from_data(ad_data):
    """Convert ad boundary data to list of (x, y, w, h) rects."""
    rects = []
    for key in ("native_ad", "dd_top", "dd_right"):
        for ad in ad_data.get(key, []):
            loc = ad.get("location", {})
            size = ad.get("size", {})
            x = loc.get("x", 0)
            y = loc.get("y", 0)
            w = size.get("width", 0)
            h = size.get("height", 0)
            if w > 0 and h > 0:
                rects.append((x, y, w, h))
    return rects


def ad_layout_label(ad_data):
    """Describe which ad types are present."""
    present = []
    for key in ("dd_top", "dd_right", "native_ad"):
        if ad_data.get(key):
            present.append(key)
    if not present:
        return "none"
    return "+".join(present)


def point_in_rect(px, py, rx, ry, rw, rh):
    return rx <= px <= rx + rw and ry <= py <= ry + rh


def build_scroll_timeline(mouse_events):
    """Build sorted list of (timestamp, scroll_y) from scroll events."""
    scrolls = []
    for ts, xpos, ypos, event, xpath in mouse_events:
        if event == "scroll":
            scrolls.append((ts, ypos))
    scrolls.sort(key=lambda x: x[0])
    return scrolls


def interpolate_scroll(scroll_timeline, ts):
    """Get interpolated scroll offset at a given timestamp."""
    if not scroll_timeline:
        return 0.0
    if ts <= scroll_timeline[0][0]:
        return scroll_timeline[0][1]
    if ts >= scroll_timeline[-1][0]:
        return scroll_timeline[-1][1]
    # Binary search
    lo, hi = 0, len(scroll_timeline) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if scroll_timeline[mid][0] <= ts:
            lo = mid
        else:
            hi = mid
    t0, s0 = scroll_timeline[lo]
    t1, s1 = scroll_timeline[hi]
    if t1 == t0:
        return s0
    frac = (ts - t0) / (t1 - t0)
    return s0 + frac * (s1 - s0)


def compute_mouse_gaze_divergence(fixations, mouse_events, scroll_timeline):
    """For each fixation, find nearest-in-time mouse position, compute distance.
    Gaze is page-space; mouse is screen-space. Convert gaze to screen-space
    by subtracting interpolated scroll offset from gaze Y."""
    if not fixations or not mouse_events:
        return None

    # Filter to positional mouse events (not scroll, load, pageshow, etc.)
    pos_events = [
        (ts, xpos, ypos)
        for ts, xpos, ypos, event, xpath in mouse_events
        if event in ("mousemove", "mouseover", "mouseout", "mouseenter", "mouseleave",
                      "click", "mousedown", "mouseup")
    ]
    if not pos_events:
        return None

    pos_events.sort(key=lambda x: x[0])
    mouse_ts = [e[0] for e in pos_events]

    total_dist = 0.0
    count = 0
    for fix_ts, fix_x, fix_y, fix_d in fixations:
        # Convert gaze page-space Y to screen-space Y
        scroll_offset = interpolate_scroll(scroll_timeline, fix_ts)
        screen_gaze_y = fix_y - scroll_offset
        screen_gaze_x = fix_x  # X is unaffected by vertical scroll

        # Binary search for nearest mouse event
        lo, hi = 0, len(mouse_ts) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if mouse_ts[mid] < fix_ts:
                lo = mid + 1
            else:
                hi = mid
        # Check lo and lo-1 for nearest
        best_idx = lo
        if lo > 0:
            if abs(mouse_ts[lo - 1] - fix_ts) < abs(mouse_ts[lo] - fix_ts):
                best_idx = lo - 1

        mx, my = pos_events[best_idx][1], pos_events[best_idx][2]
        dist = math.sqrt((screen_gaze_x - mx) ** 2 + (screen_gaze_y - my) ** 2)
        total_dist += dist
        count += 1

    return total_dist / count if count > 0 else None


def process_trial(trial_id):
    """Compute all metrics for a single trial. Returns dict or None on failure."""
    participant, batch, trial_num = parse_trial_id(trial_id)
    if participant is None:
        return None

    fixations = load_fixations(trial_id)
    mouse_events = load_mouse_events(trial_id)
    metadata = load_metadata(trial_id)
    ad_data = load_ad_boundaries(trial_id)

    fixation_count = len(fixations)

    # Duration
    if fixation_count >= 2:
        first_ts = fixations[0][0]
        last_fix = fixations[-1]
        last_ts_end = last_fix[0] + last_fix[3]  # timestamp + duration
        duration_s = round((last_ts_end - first_ts) / 1000.0, 2)
    elif fixation_count == 1:
        duration_s = round(fixations[0][3] / 1000.0, 2)
    else:
        duration_s = 0.0

    # Scroll events
    scroll_events = [e for e in mouse_events if e[3] == "scroll"]
    scroll_event_count = len(scroll_events)
    max_scroll_y = max((e[2] for e in scroll_events), default=0)
    max_scroll_y = round(max_scroll_y, 1)

    # Click events
    click_events = [e for e in mouse_events if e[3] == "click"]
    click_count = len(click_events)

    # Non-scroll mouse events (exclude meta events like load, pageshow)
    non_scroll = [e for e in mouse_events if e[3] != "scroll"]
    mouse_event_count = len(non_scroll)

    # Page dims
    page_height = metadata["page_height"]
    page_width = metadata["page_width"]
    query = metadata["query"]

    # Ad layout
    layout = ad_layout_label(ad_data)

    # Ad fixation count
    ad_rects = ad_rects_from_data(ad_data)
    ad_fixation_count = 0
    for _, fx, fy, _ in fixations:
        for rx, ry, rw, rh in ad_rects:
            if point_in_rect(fx, fy, rx, ry, rw, rh):
                ad_fixation_count += 1
                break

    ad_fixation_pct = round(ad_fixation_count / fixation_count, 3) if fixation_count > 0 else 0.0

    # Scroll timeline for gaze-mouse divergence
    scroll_timeline = build_scroll_timeline(mouse_events)

    # Mean mouse-gaze divergence
    divergence = compute_mouse_gaze_divergence(fixations, mouse_events, scroll_timeline)
    mean_divergence = round(divergence, 1) if divergence is not None else None

    # Max fixation Y
    max_fixation_y = max((fy for _, _, fy, _ in fixations), default=0)
    max_fixation_y = round(max_fixation_y, 1)

    # Page coverage
    page_coverage_pct = round(max_fixation_y / page_height * 100, 1) if page_height > 0 else 0.0

    # Scroll regression
    has_scroll_regression = False
    if len(scroll_timeline) >= 2:
        for i in range(1, len(scroll_timeline)):
            if scroll_timeline[i][1] < scroll_timeline[i - 1][1]:
                has_scroll_regression = True
                break

    # Tags
    tags = []
    if fixation_count > 200:
        tags.append("scanner")
    if fixation_count <= 10 and duration_s <= 5:
        tags.append("satisficer")
    if scroll_event_count > 200:
        tags.append("heavy_scroller")
    if scroll_event_count > 100 and fixation_count < 50:
        tags.append("scroll_without_reading")
    if mean_divergence is not None and mean_divergence < 100:
        tags.append("mouse_follower")
    if mean_divergence is not None and mean_divergence > 500:
        tags.append("mouse_independent")
    if ad_fixation_pct > 0.5:
        tags.append("ad_focused")
    if ad_fixation_pct == 0 and layout != "none":
        tags.append("ad_ignorer")
    if page_coverage_pct > 80:
        tags.append("deep_explorer")
    if max_fixation_y < 400:
        tags.append("top_only")
    if has_scroll_regression and scroll_event_count > 50:
        tags.append("regressive_scroller")
    if duration_s > 40:
        tags.append("long_trial")
    if duration_s < 2:
        tags.append("instant_decision")

    return {
        "trial_id": trial_id,
        "participant": participant,
        "batch": batch,
        "trial": trial_num,
        "query": query,
        "fixation_count": fixation_count,
        "duration_s": duration_s,
        "scroll_event_count": scroll_event_count,
        "max_scroll_y": max_scroll_y,
        "click_count": click_count,
        "mouse_event_count": mouse_event_count,
        "page_height": page_height,
        "page_width": page_width,
        "ad_layout": layout,
        "ad_fixation_count": ad_fixation_count,
        "ad_fixation_pct": ad_fixation_pct,
        "mean_mouse_gaze_divergence_px": mean_divergence,
        "max_fixation_y": max_fixation_y,
        "page_coverage_pct": page_coverage_pct,
        "has_scroll_regression": has_scroll_regression,
        "tags": tags,
    }


def find_prototypical(tagged_trials):
    """For each tag, find the most extreme example by its defining metric."""
    # Map tag -> (metric_key, comparison_fn)
    tag_metric = {
        "scanner": ("fixation_count", max),
        "satisficer": ("fixation_count", min),
        "heavy_scroller": ("scroll_event_count", max),
        "scroll_without_reading": ("scroll_event_count", max),
        "mouse_follower": ("mean_mouse_gaze_divergence_px", min),
        "mouse_independent": ("mean_mouse_gaze_divergence_px", max),
        "ad_focused": ("ad_fixation_pct", max),
        "ad_ignorer": ("fixation_count", max),  # most fixations while ignoring ads
        "deep_explorer": ("page_coverage_pct", max),
        "top_only": ("max_fixation_y", min),
        "regressive_scroller": ("scroll_event_count", max),
        "long_trial": ("duration_s", max),
        "instant_decision": ("duration_s", min),
    }

    prototypical = {}
    for tag, (metric, fn) in tag_metric.items():
        candidates = [t for t in tagged_trials if tag in t["tags"]]
        if not candidates:
            continue
        # Filter out None values for the metric
        valid = [t for t in candidates if t.get(metric) is not None]
        if not valid:
            continue
        if fn == max:
            best = max(valid, key=lambda t: t[metric])
        else:
            best = min(valid, key=lambda t: t[metric])
        prototypical[tag] = {
            "trial_id": best["trial_id"],
            "metric": metric,
            "value": best[metric],
            "query": best["query"],
        }

    return prototypical


def main():
    # Discover all trial IDs from fixation data directory
    trial_files = sorted(os.listdir(FIX_DIR))
    trial_ids = [f.replace(".csv", "") for f in trial_files if f.endswith(".csv")]

    print(f"Found {len(trial_ids)} trials to process")

    all_trials = []
    errors = 0
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(trial_ids)}...")
        try:
            result = process_trial(tid)
            if result is not None:
                all_trials.append(result)
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  Error on {tid}: {e}", file=sys.stderr)

    print(f"Processed {len(all_trials)} trials successfully ({errors} errors)")

    # Filter to tagged trials only
    tagged_trials = [t for t in all_trials if t["tags"]]
    print(f"Tagged trials: {len(tagged_trials)} / {len(all_trials)}")

    # Tag counts
    tag_counts = {}
    for t in tagged_trials:
        for tag in t["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort tag counts descending
    tag_counts_sorted = dict(sorted(tag_counts.items(), key=lambda x: -x[1]))

    # Prototypical examples
    prototypical = find_prototypical(tagged_trials)

    # Build output
    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_trials": len(all_trials),
        "tagged_trials": len(tagged_trials),
        "tag_counts": tag_counts_sorted,
        "prototypical": prototypical,
        "trials": sorted(tagged_trials, key=lambda t: t["trial_id"]),
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nOutput written to {OUT_PATH}")
    print(f"\n--- Tag Distribution ---")
    for tag, count in tag_counts_sorted.items():
        print(f"  {tag}: {count}")

    print(f"\n--- Prototypical Examples ---")
    for tag, info in prototypical.items():
        print(f"  {tag}: {info['trial_id']} ({info['metric']}={info['value']}, q=\"{info['query']}\")")


if __name__ == "__main__":
    main()
