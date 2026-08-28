"""Phase 1.5 — measure rendered page-space geometry for every HTML card.

Renders each SERP snapshot (AdSERP/data/serps-cached/, offline-cached
assets) in headless Chromium at the dataset's 1280 px capture width and
records, for every card in data/aoi-html-types/<tid>.json, the rendered
bounding box located via the card's `css_path`.

The rendered frame is NOT the dataset screenshot frame: fonts/asset
differences produce a progressive y drift (~+60 px near the top of the
flagged trials, ~+100 px by mid-page). Phase 2 therefore fits a per-trial
linear map render->dataset during alignment; this script just records raw
render geometry.

Outputs per-trial (order-aligned with the aoi-html-types card list):
  data/aoi-html-geometry/<tid>.json
  [
    {"order": 0, "found": true, "y": 584, "height": 367, "x": 160,
     "width": 652},
    {"order": 1, "found": false},   # css_path missed in the browser DOM
    ...
  ]

Idempotent: skips trials whose output already exists (delete the file or
pass --force to re-measure).

Run:
  .venv/bin/python scripts/measure_card_geometry.py
  .venv/bin/python scripts/measure_card_geometry.py p040-b4-t6 p040-b1-t7
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
HTML_TYPES = ROOT / 'data/aoi-html-types'
SERPS_CACHED = ROOT / 'AdSERP/data/serps-cached'
SERPS = ROOT / 'AdSERP/data/serps'
OUT_DIR = ROOT / 'data/aoi-html-geometry'

VIEWPORT = {'width': 1280, 'height': 1024}
N_WORKERS = 6

# Identity-verified measurement. html.parser (Phase 1) and Chromium can
# parse the same HTML into different trees — observed mechanism: a
# right-rail knowledge panel (TQc1id...rhstc4) that html.parser keeps as
# an #rso child but Chromium re-parents up to #rcnt, shifting every
# later sibling's nth-of-type index by one. A bare querySelector then
# silently measures the NEXT element. So each card carries identity
# fields (class tokens, heading, ws-stripped text length) and a match
# only counts when identity verifies; on failure the last nth-of-type
# index is shifted +-1..3 and re-verified (parser divergence moves
# siblings by a small offset). Chromium's parse is ground truth — it is
# what produced the dataset screenshots.
MEASURE_JS = """(cards) => {
    const norm = s => (s || '').replace(/\\s+/g, '');
    const clsTokens = el =>
        (el.getAttribute('class') || '').split(/\\s+/).filter(Boolean).join(' ');
    const headingOf = el => {
        const h = el.querySelector('h3') || el.querySelector('h2')
              || el.querySelector('[role="heading"]');
        return h ? h.textContent : '';
    };
    const verify = (el, c) => {
        if (!el) return false;
        if (clsTokens(el) !== (c.cls || '')) return false;
        // class matched; confirm content by heading OR text length —
        // heading_text is synthetic for some card types (pagination is
        // get_text(separator='|')), so either signal suffices.
        const okHeading = c.heading
            ? norm(headingOf(el)).slice(0, 30) === norm(c.heading).slice(0, 30)
            : false;
        let okLen = false;
        if (c.text_len != null) {
            const got = norm(el.textContent).length;
            const tol = Math.max(30, 0.15 * Math.max(c.text_len, got));
            okLen = Math.abs(got - c.text_len) <= tol;
        }
        return okHeading || okLen || (!c.heading && c.text_len == null);
    };
    const q = p => { try { return document.querySelector(p); } catch (e) { return null; } };
    const shifted = (p, d) => p.replace(/nth-of-type\\((\\d+)\\)(?!.*nth-of-type)/,
        (m, n) => `nth-of-type(${parseInt(n) + d})`);
    const rect = (el, extra) => {
        const r = el.getBoundingClientRect();
        return Object.assign({
            found: true,
            x: Math.round(r.left + window.scrollX),
            y: Math.round(r.top + window.scrollY),
            width: Math.round(r.width),
            height: Math.round(r.height),
        }, extra);
    };
    return cards.map(c => {
        if (!c.path) return {found: false};
        let el = q(c.path);
        if (verify(el, c)) return rect(el, {verified: true, shift: 0});
        for (const d of [-1, 1, -2, 2, -3, 3]) {
            const cand = q(shifted(c.path, d));
            if (verify(cand, c)) return rect(cand, {verified: true, shift: d});
        }
        // Unverifiable: report the raw path hit (if any) as unverified
        // rather than inventing geometry — Phase 2 treats it as missing.
        return {found: false, raw_path_hit: !!el};
    });
}"""


async def measure_trial(page, tid):
    cards = json.loads((HTML_TYPES / f'{tid}.json').read_text())
    serp = SERPS_CACHED / f'{tid}.html'
    if not serp.exists():
        serp = SERPS / f'{tid}.html'
    try:
        await page.goto(f'file://{serp}', wait_until='load', timeout=20000)
    except Exception:
        pass  # measure whatever rendered before the timeout
    await page.wait_for_timeout(250)
    rects = await page.evaluate(MEASURE_JS, [
        {'path': c.get('css_path'),
         'cls': c.get('css_class', ''),
         'heading': c.get('heading_text', ''),
         'text_len': c.get('text_len')}
        for c in cards])
    return [{'order': c['order'], **r} for c, r in zip(cards, rects)]


async def worker(name, queue, ctx, counters):
    page = await ctx.new_page()
    while True:
        tid = await queue.get()
        if tid is None:
            queue.task_done()
            break
        try:
            result = await measure_trial(page, tid)
            (OUT_DIR / f'{tid}.json').write_text(json.dumps(result))
            counters['done'] += 1
            counters['missed'] += sum(1 for r in result if not r['found'])
            counters['repaired'] += sum(1 for r in result if r.get('shift'))
            counters['cards'] += len(result)
        except Exception as e:
            counters['errors'] += 1
            print(f'  ERROR {tid}: {e}', file=sys.stderr)
        finally:
            queue.task_done()
        n = counters['done'] + counters['errors']
        if n % 200 == 0:
            print(f'  {n}/{counters["total"]} '
                  f'(css_path misses {counters["missed"]:,}/{counters["cards"]:,})',
                  file=sys.stderr)
    await page.close()


async def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('trials', nargs='*', help='trial ids (default: all)')
    ap.add_argument('--force', action='store_true',
                    help='re-measure even when output exists')
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tids = args.trials or sorted(fp.stem for fp in HTML_TYPES.glob('*.json'))
    if not args.force:
        tids = [t for t in tids if not (OUT_DIR / f'{t}.json').exists()]
    print(f'[geometry] {len(tids):,} trials to measure', file=sys.stderr)
    if not tids:
        return

    counters = {'done': 0, 'errors': 0, 'missed': 0, 'repaired': 0,
                'cards': 0, 'total': len(tids)}
    queue: asyncio.Queue = asyncio.Queue()
    for t in tids:
        queue.put_nowait(t)
    for _ in range(N_WORKERS):
        queue.put_nowait(None)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport=VIEWPORT)
        await asyncio.gather(*(worker(i, queue, ctx, counters)
                               for i in range(N_WORKERS)))
        await browser.close()

    print(f'[geometry] done: {counters["done"]:,} trials, '
          f'{counters["errors"]} errors, unverified '
          f'{counters["missed"]:,}/{counters["cards"]:,} cards, '
          f'shift-repaired {counters["repaired"]:,}',
          file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())
