"""Quantify the dd_right (right-rail ad) blind spot in typed extraction.

For each trial:
- Load shipped dd_right rectangles from AdSERP/data/ad-boundary-data/{tid}.json
- Load the final click
- Check if final click falls inside any dd_right rectangle
- Count: how many clicks land on dd_right that typed attribution misses?

Regime tag: [LAB, AdSERP, typed, audit-2026-05-05]
Headline: 861 dd_right rectangles in corpus (one per 31% of trials); 67 final
clicks (2.41%) land on dd_right; typed extraction filters dd_right by design
(result column X 162-702; dd_right at X 910-1128). The Y-band-only legacy
attribution silently rolls these into organic.

See: docs/null-findings/2026-05-05-bbox-y-coverage.md (#2.2)
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/andyed/Documents/dev/attentional-foraging")
sys.path.insert(0, str(ROOT / "notebooks-v2"))
from data_loader import load_mouse_events  # noqa: E402

AD_DIR = ROOT / "AdSERP/data/ad-boundary-data"

n_trials = 0
n_with_ddright = 0
n_clicks_on_ddright = 0
n_clicks_total = 0
ddright_count_per_trial = Counter()

# Also: what fraction of trials have a dd_right ad at all?
trials_with_any_ddright = 0
total_ddright_rects = 0

# Click X distribution for clicks on dd_right
ddright_click_x = []
ddright_click_y = []

for f in sorted(AD_DIR.glob("*.json")):
    tid = f.stem
    d = json.load(open(f))
    ddright = d.get("dd_right", [])
    if ddright:
        trials_with_any_ddright += 1
        total_ddright_rects += len(ddright)
        ddright_count_per_trial[len(ddright)] += 1

    try:
        mouse = load_mouse_events(tid)
    except Exception:
        continue
    if mouse is None:
        continue
    _, _, clicks = mouse
    if not clicks:
        continue
    n_trials += 1
    if ddright:
        n_with_ddright += 1
    final = clicks[-1]
    if len(final) < 3:
        continue
    cx, cy = float(final[1]), float(final[2])
    n_clicks_total += 1
    for r in ddright:
        x0 = r["location"]["x"]
        y0 = r["location"]["y"]
        w = r["size"]["width"]
        h = r["size"]["height"]
        if x0 <= cx <= x0 + w and y0 <= cy <= y0 + h:
            n_clicks_on_ddright += 1
            ddright_click_x.append(cx)
            ddright_click_y.append(cy)
            break

print(f"trials: {n_trials:,}")
print(f"trials with at least one dd_right rect: {trials_with_any_ddright:,}")
print(f"total dd_right rectangles in corpus: {total_ddright_rects:,}")
print(f"dd_right per trial distribution: {dict(ddright_count_per_trial)}")
print()
print(f"final clicks landing inside a dd_right rect: {n_clicks_on_ddright:,}")
print(f"  as fraction of total final clicks: {100.0 * n_clicks_on_ddright / n_clicks_total:.2f}%")
print(f"  as fraction of trials with dd_right present: "
      f"{100.0 * n_clicks_on_ddright / n_with_ddright if n_with_ddright else 0:.2f}%")
print()
if ddright_click_x:
    import statistics
    print(f"dd_right click X: min={min(ddright_click_x):.0f}, "
          f"median={statistics.median(ddright_click_x):.0f}, "
          f"max={max(ddright_click_x):.0f}")
    print(f"dd_right click Y: min={min(ddright_click_y):.0f}, "
          f"median={statistics.median(ddright_click_y):.0f}, "
          f"max={max(ddright_click_y):.0f}")
