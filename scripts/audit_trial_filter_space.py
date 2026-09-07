"""Trial-level final-click attribution under typed_gapfill, document vs screenshot space.

Mirrors data_loader.is_main_axis_click but runs the containment test in both
coordinate spaces and buckets every non-attributed trial:
  main_axis            final click lands in a main-axis typed_gapfill AOI
  dd_right             final click lands in a shipped right-rail ad rectangle
  chrome_or_offtarget  neither (page chrome, search tools, far-off-target)
  no_click             no usable click event
Prints both rates, the recovered/lost counts between spaces, and the
transition table. Source for the click-filter paragraph of the AllSERP paper.

Run:  .venv/bin/python scripts/audit_trial_filter_space.py [--json out.json]
Tag:  [LAB, AdSERP, typed_gapfill]
"""
import sys, json, glob, collections, argparse
sys.path.insert(0, '/Users/andyed/Documents/dev/attentional-foraging/notebooks-v2')
from data_loader import load_mouse_events, attribute_click_to_typed_gapfill, get_trial_geometry
AD = '/Users/andyed/Documents/dev/attentional-foraging/AdSERP/data'
tids = sorted(p.split('/')[-1][:-4] for p in glob.glob(f'{AD}/mouse-movement-data/*.csv'))
def dd_right_rects(tid):
    """Shipped ad-boundary JSON: {"dd_right": [{"location": {"x","y"}, "size": {"width","height"}}]}, screenshot space."""
    try: d = json.load(open(f'{AD}/ad-boundary-data/{tid}.json'))
    except Exception: return []
    return [(float(a['location']['x']), float(a['location']['y']), float(a['size']['width']), float(a['size']['height'])) for a in d.get('dd_right', [])]
def in_rect(x, y, r):
    rx, ry, rw, rh = r
    return rx <= x <= rx + rw and ry <= y <= ry + rh
res = {}
for tid in tids:
    row = {}
    for space in ('document', 'screenshot'):
        try:
            _, _, clicks = load_mouse_events(tid, space=space)
        except Exception as e:
            row[space] = 'unreadable'; continue
        if not clicks or len(clicks[-1]) < 3:
            row[space] = 'no_click'; continue
        cx, cy = float(clicks[-1][1]), float(clicks[-1][2])
        hit = attribute_click_to_typed_gapfill(cx, cy, tid)
        if hit is not None:
            row[space] = 'main_axis'; continue
        # bucket the miss: screenshot-space rects vs (for document) the same rects compared to unconverted coords, as the released filter would
        rects = dd_right_rects(tid)
        row[space] = 'dd_right' if any(in_rect(cx, cy, r) for r in rects) else 'chrome_or_offtarget'
    res[tid] = row
N = len(res)
for space in ('document', 'screenshot'):
    c = collections.Counter(r[space] for r in res.values())
    print(f'{space:11s} n={N} ' + ' '.join(f'{k}={v}' for k, v in sorted(c.items())) + f'  rate={c["main_axis"]/N:.4f}')
rec = sum(1 for r in res.values() if r['document'] != 'main_axis' and r['screenshot'] == 'main_axis')
lost = sum(1 for r in res.values() if r['document'] == 'main_axis' and r['screenshot'] != 'main_axis')
print(f'recovered={rec} lost={lost}')
trans = collections.Counter((r['document'], r['screenshot']) for r in res.values())
print('transitions:', sorted(trans.items(), key=lambda kv: -kv[1]))
ap = argparse.ArgumentParser(); ap.add_argument('--json'); args = ap.parse_args()
if args.json:
    json.dump({'per_trial': res, 'n': N}, open(args.json, 'w'), indent=1)
    print('wrote', args.json)
