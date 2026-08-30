"""Score the typed AOI substrate against DOM ground truth.

Three checks, each against something the pipeline did NOT produce, so a score
cannot be gamed by the thing being scored:

  click   every click event records the xpath of the element it hit. Render the
          saved SERP at the capture viewport and ask whether the recorded
          coordinate falls inside that element. Tests the coordinate model with
          no AOI involved.
  aoi     every typed AOI carries html_handle, and aoi-html-types carries the
          matching css_path. Resolve it, map the rendered box into screenshot
          space, and compare to the stored AOI box by IoU. Tests extraction.
  cell    carousel cards carry numbered DOM ids (vplaurlg<N>). Compare the
          visible ones against the cellsplit export. Tests the cell layer.

Every failure mode found on 2026-08-30 -- unconverted mouse coordinates,
two cards measured onto one DOM node, trailing cells dropped -- shows up in one
of these three. That is the point: the substrate had no measurement that could
fail, so nothing did.

Usage:
    python scripts/aoi_fidelity.py                 # 120-trial sample
    python scripts/aoi_fidelity.py --all
    python scripts/aoi_fidelity.py --trials p004-b1-t1 p039-b5-t3
    python scripts/aoi_fidelity.py --all --json scripts/output/aoi_fidelity.json
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(os.environ.get('AF_ROOT', '/Users/andyed/Documents/dev/attentional-foraging'))
SERPS_CACHED = ROOT / 'AdSERP/data/serps-cached'
SERPS = ROOT / 'AdSERP/data/serps'
SHOTS = ROOT / 'AdSERP/data/full-page-screenshots'
META = ROOT / 'AdSERP/data/trial-metadata'
MOUSE = ROOT / 'AdSERP/data/mouse-movement-data'
HTML_TYPES = ROOT / 'data/aoi-html-types'
TYPED = ROOT / 'data/aoi-typed'
CELLSPLIT = ROOT / 'scripts/output/adserp_aois_by_trial_id_typed_gapfill_cellsplit.csv'

CAPTURE_VIEWPORT = 1389   # reproduces the recorded document width of 1403
MAIN_MAX_X = 850          # capture space: main column ends ~832, right rail ~880

JS = """(args) => {
  const out = {paths: {}, cells: [], click: null};
  for (const [handle, sel] of Object.entries(args.paths)) {
    let el = null;
    try { el = document.querySelector(sel); } catch (e) {}
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1) continue;
    out.paths[handle] = {x: r.left+window.scrollX, y: r.top+window.scrollY,
                         w: r.width, h: r.height};
  }
  // Carousel cells are only "cells" if the user could see them. The strip is a
  // horizontal scroller: the container renders ~3,800px wide clipped to ~650px,
  // so most cards are in the DOM but off-screen. Find the clipping ancestor
  // (clientWidth < scrollWidth) and count only what fits inside it.
  const seen = new Map();
  let clip = null;
  const firstCell = document.querySelector('[id^="vplaurlg"]');
  if (firstCell) { let p = firstCell.parentElement;
    for (let i = 0; i < 10 && p; i++) {
      if (p.scrollWidth > p.clientWidth + 20 && p.clientWidth > 200) {
        clip = {x: p.getBoundingClientRect().left + window.scrollX, w: p.clientWidth};
        break;
      } p = p.parentElement; } }
  document.querySelectorAll('[id^="vplaurlg"]').forEach(el => {
    const m = el.id.match(/^vplaurlg(\\d+)$/); if (!m) return;
    const r = el.getBoundingClientRect();
    const x = r.left + window.scrollX;
    if (r.width < 5 || x > args.mainMaxX) return;
    if (clip && x + r.width > clip.x + clip.w + 2) return;   // scrolled off the strip
    seen.set(+m[1], {x: x, w: r.width});
  });
  out.cells = [...seen.keys()].sort((a,b)=>a-b);
  out.clip = clip;
  if (args.clickXpath) {
    let el = null;
    try { el = document.evaluate(args.clickXpath, document, null, 9, null).singleNodeValue; }
    catch (e) {}
    if (el) { const r = el.getBoundingClientRect();
      out.click = {x: r.left+window.scrollX, y: r.top+window.scrollY, w: r.width, h: r.height}; }
  }
  return out;
}"""


def ratios(tid):
    """Document -> screenshot scale, derived per trial from the shipped artifacts."""
    try:
        import xml.etree.ElementTree as ET
        t = ET.parse(META / f'{tid}.xml')
        dw, dh = (int(v) for v in t.find('.//document').text.split('x'))
    except Exception:
        return None
    shot = SHOTS / f'{tid}.png'
    if shot.exists():
        try:
            sw, sh = Image.open(shot).size
            return sw / dw, sh / dh
        except Exception:
            pass
    return 1280 / dw, 0.9000


def final_click(tid):
    f = MOUSE / f'{tid}.csv'
    if not f.exists():
        return None
    last = None
    with f.open() as fh:
        for r in csv.DictReader(fh):
            if 'click' not in (r.get('event') or '').lower():
                continue
            xp = (r.get('xpath') or '').strip()
            try:
                last = (float(r['xpos']), float(r['ypos']), xp)
            except (TypeError, ValueError):
                pass
    return last


def iou(a, b):
    ix = max(0, min(a[0]+a[2], b[0]+b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1]+a[3], b[1]+b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2]*a[3] + b[2]*b[3] - inter
    return inter / union if union > 0 else 0.0


def cellsplit_counts():
    counts = {}
    if not CELLSPLIT.exists():
        return counts
    with CELLSPLIT.open() as fh:
        for r in csv.DictReader(fh):
            if r.get('role') == 'cell' and r.get('cell_index'):
                counts[r['trial_id']] = counts.get(r['trial_id'], 0) + 1
    return counts


async def score(tids, verbose=False):
    cs = cellsplit_counts()
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={'width': CAPTURE_VIEWPORT, 'height': 1024})
        page = await ctx.new_page()
        for n, tid in enumerate(tids, 1):
            serp = SERPS_CACHED / f'{tid}.html'
            if not serp.exists():
                serp = SERPS / f'{tid}.html'
            if not serp.exists():
                continue
            try:
                cards = json.loads((HTML_TYPES / f'{tid}.json').read_text())
                aois = json.loads((TYPED / f'{tid}.json').read_text())
            except Exception:
                continue
            paths = {c['html_handle']: c['css_path'] for c in cards
                     if c.get('html_handle') and c.get('css_path')}
            click = final_click(tid)
            try:
                await page.goto(f'file://{serp}', wait_until='load', timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(90)
            try:
                res = await page.evaluate(JS, {'paths': paths, 'mainMaxX': MAIN_MAX_X,
                                               'clickXpath': click[2] if click else None})
            except Exception:
                continue
            rx, ry = ratios(tid) or (None, None)
            if rx is None:
                continue

            # click: does the recorded coordinate fall inside the element its xpath names?
            click_ok = None
            if click and res.get('click'):
                b = res['click']
                click_ok = (b['x'] <= click[0] <= b['x']+b['w']
                            and b['y'] <= click[1] <= b['y']+b['h'])

            # aoi: stored box vs the DOM element it claims, mapped into screenshot space
            ious = []
            for a in aois:
                h = a.get('html_handle')
                if not h or h not in res['paths'] or a.get('x') is None or not a.get('width'):
                    continue
                d = res['paths'][h]
                ious.append(iou((a['x'], a['y'], a['width'], a['height']),
                                (d['x']*rx, d['y']*ry, d['w']*rx, d['h']*ry)))

            # cell: DOM visible carousel cells vs the cellsplit export
            dom_cells = len(res['cells'])
            exp_cells = cs.get(tid)

            rows.append({'tid': tid,
                         'click_ok': click_ok,
                         'aoi_iou_median': statistics.median(ious) if ious else None,
                         'aoi_n': len(ious),
                         'dom_cells': dom_cells,
                         'export_cells': exp_cells,
                         'ratio_x': round(rx, 4), 'ratio_y': round(ry, 4)})
            if verbose:
                print(f"  {tid}: click={click_ok} iou={rows[-1]['aoi_iou_median']} "
                      f"cells dom={dom_cells} export={exp_cells}", flush=True)
            elif n % 40 == 0:
                print(f"  {n}/{len(tids)}", file=sys.stderr, flush=True)
        await browser.close()
    return rows


def report(rows):
    n = len(rows)
    print(f"\n{'='*66}\n  AOI FIDELITY  —  {n} trials\n{'='*66}")
    cl = [r['click_ok'] for r in rows if r['click_ok'] is not None]
    if cl:
        print(f"\n  click     recorded coordinate inside the element its xpath names")
        print(f"            {sum(cl)}/{len(cl)}  ({100*sum(cl)/len(cl):.1f}%)")
    io = [r['aoi_iou_median'] for r in rows if r['aoi_iou_median'] is not None]
    if io:
        io_s = sorted(io)
        good = sum(1 for v in io if v >= 0.5)
        print(f"\n  aoi       stored box vs the DOM element it claims (IoU)")
        print(f"            median {statistics.median(io):.3f}   "
              f"p10 {io_s[len(io_s)//10]:.3f}   p90 {io_s[9*len(io_s)//10]:.3f}")
        print(f"            IoU >= 0.5 on {good}/{len(io)} trials ({100*good/len(io):.1f}%)")
    cc = [(r['dom_cells'], r['export_cells']) for r in rows
          if r['dom_cells'] and r['export_cells'] is not None]
    if cc:
        agree = sum(1 for d, e in cc if d == e)
        print(f"\n  cell      visible DOM carousel cells vs the cellsplit export")
        print(f"            agree {agree}/{len(cc)} ({100*agree/len(cc):.1f}%)   "
              f"export short on {sum(1 for d,e in cc if e < d)}   over on {sum(1 for d,e in cc if e > d)}")
    print(f"\n{'='*66}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--trials', nargs='*')
    ap.add_argument('--limit', type=int, default=120)
    ap.add_argument('--json')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    every = sorted(p.stem for p in HTML_TYPES.glob('p*.json'))
    if a.trials:
        tids = a.trials
    elif a.all:
        tids = every
    else:
        step = max(1, len(every)//a.limit)
        tids = every[::step][:a.limit]
    print(f"scoring {len(tids)} trials at viewport {CAPTURE_VIEWPORT}…", file=sys.stderr)
    rows = asyncio.run(score(tids, a.verbose))
    report(rows)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rows, indent=1))
        print(f"  wrote {a.json}")


if __name__ == '__main__':
    main()
