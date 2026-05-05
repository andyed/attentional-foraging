"""Cascade audit — quantify Y-band attribution contamination of typed cascade.

(1) Total contamination magnitude. Of the 690 strict-bbox-unattributed final
    clicks, how many does the existing `click_to_position` Y-band rule
    mis-attribute to some main-axis AOI? Break down by where the click
    actually was (dd_right, far-right chrome, below-doc, in-column-edge).

(3) Existing filter check. Do current "approached" populations
    (min_dist < 100) silently include these contaminated trials? Or does
    the cursor-approach gate happen to filter most out?

PLUS: cross-ref with the AR replay set so individual contaminated trials can
be visually inspected.

Regime tag: [LAB, AdSERP, typed, audit-2026-05-05]
Headline: 22.7% of 'approached & clicked' records (391/1,723) come from
contaminated trials. Bucket counts: dd_right 67, right_chrome 91,
in_column_edge 532. The 'approached' gate (min_dist<100) does NOT filter
these out.

See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#2.3)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import (  # noqa: E402
    get_trial_meta, load_mouse_events, click_to_position,
    typed_aoi_tops, typed_aoi_etypes,
)

TYPED_CSV = ROOT / "scripts/output/adserp_aois_by_trial_id_typed.csv"
AD_DIR = ROOT / "AdSERP/data/ad-boundary-data"
CURSOR_FEATURES = ROOT / "AdSERP/data/cursor-approach-features-typed.json"
REPLAY_DIR = Path("/Users/andyed/Documents/dev/approach-retreat/site/replay/trials")

REPLAY_TRIALS = {p.stem for p in REPLAY_DIR.glob("*.html")}
print(f"replay set size: {len(REPLAY_TRIALS)} trials")


def load_typed_aois():
    by_trial = defaultdict(list)
    with open(TYPED_CSV, newline="") as f:
        for row in csv.DictReader(f):
            by_trial[row["trial_id"]].append({
                "rank": int(row["rank"]),
                "etype": row["etype"],
                "top_y": float(row["top_y"]),
                "bottom_y": float(row["bottom_y"]),
                "left_x": float(row["left_x"]),
                "right_x": float(row["right_x"]),
                "screen_height": float(row["screen_height"]),
            })
    for tid in by_trial:
        by_trial[tid].sort(key=lambda a: a["rank"])
    return dict(by_trial)


def load_dd_right(tid):
    f = AD_DIR / f"{tid}.json"
    if not f.exists():
        return []
    d = json.load(open(f))
    out = []
    for r in d.get("dd_right", []):
        x0, y0 = r["location"]["x"], r["location"]["y"]
        w, h = r["size"]["width"], r["size"]["height"]
        out.append((x0, y0, x0 + w, y0 + h))
    return out


def click_in_aoi(cx, cy, aois):
    for a in aois:
        if a["left_x"] <= cx <= a["right_x"] and a["top_y"] <= cy <= a["bottom_y"]:
            return a
    return None


def click_in_dd_right(cx, cy, ddr):
    for x0, y0, x1, y1 in ddr:
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return (x0, y0, x1, y1)
    return None


def categorize(cx, cy, aois, ddr, doc_h, scr_h):
    """Return ('dd_right' | 'right_chrome' | 'left_chrome' | 'below_doc' |
                'above_top' | 'in_column_edge' | 'attributed', detail)."""
    if click_in_aoi(cx, cy, aois):
        return ("attributed_strict", None)
    if click_in_dd_right(cx, cy, ddr):
        return ("dd_right", None)
    if cy < 0:
        return ("above_top", None)
    if cy > doc_h:
        return ("below_doc", None)
    if cx < 162:
        return ("left_chrome", None)
    if cx > 702:
        return ("right_chrome", None)
    # In-column (X 162-702) but Y not in any bbox — bbox-edge near miss
    return ("in_column_edge", None)


# ==== Q1: contamination magnitude ====
print("\n=== Q1: contamination magnitude ===")
aois_by_trial = load_typed_aois()
typed_features = json.load(open(CURSOR_FEATURES))
features_by_trial = defaultdict(list)
for r in typed_features:
    features_by_trial[r["trial_id"]].append(r)

cat_counts = Counter()
mis_attribution_by_cat = Counter()
mis_attribution_etype_by_cat = defaultdict(Counter)
trials_unattributed = []  # (tid, click_xy, category, what_y_band_assigned_etype)

n_trials_examined = 0
for tid, aois in aois_by_trial.items():
    meta = get_trial_meta(tid)
    if meta[0] is None:
        continue
    doc_h, scr_h, _ = meta
    try:
        mouse = load_mouse_events(tid)
    except Exception:
        continue
    if mouse is None:
        continue
    _, _, clicks = mouse
    if not clicks:
        continue
    final = clicks[-1]
    if len(final) < 3:
        continue
    cx, cy = float(final[1]), float(final[2])
    n_trials_examined += 1

    ddr = load_dd_right(tid)
    cat, _ = categorize(cx, cy, aois, ddr, doc_h, scr_h)
    cat_counts[cat] += 1

    if cat != "attributed_strict":
        # What does Y-band rule assign?
        tops = typed_aoi_tops(tid)
        etypes = typed_aoi_etypes(tid)
        n_results = len(tops)
        yband_pos = click_to_position(clicks, tops, n_results)
        yband_etype = (
            etypes[yband_pos]
            if yband_pos is not None and 0 <= yband_pos < len(etypes)
            else None
        )
        if yband_etype:
            mis_attribution_by_cat[cat] += 1
            mis_attribution_etype_by_cat[cat][yband_etype] += 1
        trials_unattributed.append({
            "trial_id": tid,
            "click_xy": (cx, cy),
            "category": cat,
            "yband_assigned_pos": yband_pos,
            "yband_assigned_etype": yband_etype,
            "in_replay_set": tid in REPLAY_TRIALS,
        })

print(f"trials examined: {n_trials_examined:,}")
print(f"\ncategory of final-click landing site:")
for cat, n in cat_counts.most_common():
    yband_mis = mis_attribution_by_cat.get(cat, 0)
    print(f"  {cat:<22s} {n:>5,d}  "
          f"(of those, {yband_mis:>5,d} silently mis-attributed by Y-band rule)")

print(f"\nFor each contamination category, what etype Y-band assigned:")
for cat in mis_attribution_etype_by_cat:
    print(f"  {cat}:")
    for et, n in mis_attribution_etype_by_cat[cat].most_common():
        print(f"    -> {et}: {n}")

# ==== Q3: existing filter check ====
print("\n=== Q3: existing filter check (approached AOIs in cursor-approach-features-typed) ===")

# For the contaminated trials, find which (trial, position) records exist in
# cursor-approach-features-typed.json with was_clicked=True.
contaminated_tids = {t["trial_id"] for t in trials_unattributed}
print(f"contaminated trials: {len(contaminated_tids):,}")

# Of those, how many have a 'clicked' record in cursor-approach-features?
n_with_clicked_record = 0
n_with_approached_clicked = 0  # min_dist < 100 AND was_clicked AND in contaminated trial
clicked_records_in_contaminated = []
for tid in contaminated_tids:
    recs = features_by_trial.get(tid, [])
    clicked = [r for r in recs if r.get("was_clicked")]
    if clicked:
        n_with_clicked_record += 1
        for r in clicked:
            if r.get("min_dist", float("inf")) < 100:
                n_with_approached_clicked += 1
            clicked_records_in_contaminated.append({
                "tid": tid, "pos": r["position"], "etype": r["etype"],
                "min_dist": r["min_dist"], "was_clicked": r["was_clicked"],
            })

print(f"  contaminated trials with ≥1 was_clicked=True record: {n_with_clicked_record:,}")
print(f"  of which the 'clicked' record has min_dist<100 (approached): "
      f"{n_with_approached_clicked:,}")
print(f"  → these {n_with_approached_clicked:,} records are in the 'approached' "
      f"population BUT the click was actually off-axis")

# Compare to total "approached & clicked" pop size
total_approached_clicked = sum(
    1 for r in typed_features if r.get("was_clicked") and r.get("min_dist", float("inf")) < 100)
print(f"  total approached+clicked records in corpus: {total_approached_clicked:,}")
if total_approached_clicked:
    print(f"  contamination rate of 'approached & clicked' pop: "
          f"{100.0 * n_with_approached_clicked / total_approached_clicked:.2f}%")

# ==== Replay set examples ====
print("\n=== Replay-set examples (for visual inspection) ===")
by_cat = defaultdict(list)
for t in trials_unattributed:
    if t["in_replay_set"]:
        by_cat[t["category"]].append(t)

for cat in ["dd_right", "right_chrome", "in_column_edge", "left_chrome", "below_doc"]:
    examples = by_cat.get(cat, [])
    if not examples:
        continue
    print(f"\n  {cat} (n={len(examples)} in replay set):")
    for ex in examples[:5]:
        url = f"https://andyed.github.io/approach-retreat/replay/?trial={ex['trial_id']}"
        print(f"    {ex['trial_id']}: click@{ex['click_xy']}, "
              f"Y-band→ {ex['yband_assigned_etype']} pos {ex['yband_assigned_pos']}")
        print(f"      {url}")
