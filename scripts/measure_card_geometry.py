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
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# Absolute by default so the script runs from anywhere; AF_ROOT lets a git
# worktree measure into its own tree instead of writing back into the main
# checkout's data/aoi-html-geometry.
ROOT = Path(os.environ.get('AF_ROOT',
                           '/Users/andyed/Documents/dev/attentional-foraging'))
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
    // Returns WHICH signal identified the element, not just whether one did.
    // 'heading' is strong identity; 'len' is a +/-15% text-length window that two
    // adjacent organics can both satisfy; 'weak' is the no-signal-available case.
    // Ranked so a contested node can be awarded on evidence instead of loop order.
    const RANK = {heading: 3, len: 2, weak: 1};
    const matchKind = (el, c) => {
        if (!el) return null;
        if (clsTokens(el) !== (c.cls || '')) return null;
        // class matched; confirm content by heading OR text length —
        // heading_text is synthetic for some card types (pagination is
        // get_text(separator='|')), so either signal suffices.
        const okHeading = c.heading
            ? norm(headingOf(el)).slice(0, 30) === norm(c.heading).slice(0, 30)
            : false;
        if (okHeading) return 'heading';
        if (c.text_len != null) {
            const got = norm(el.textContent).length;
            const tol = Math.max(30, 0.15 * Math.max(c.text_len, got));
            if (Math.abs(got - c.text_len) <= tol) return 'len';
        }
        if (!c.heading && c.text_len == null) return 'weak';
        return null;
    };
    const verify = (el, c) => matchKind(el, c) !== null;
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
    // Two passes, so a card's own css_path always outranks another card's
    // shift-repair, and no DOM node is measured for two cards.
    //
    // Single-pass, a failed css_path fell straight to d=-1 -- the PREVIOUS
    // card's node, since -1 leads the ladder -- and verify()'s length
    // tolerance (max(30, 0.15*len)) is loose enough that two adjacent
    // "g tF2Cxc" organics pass each other's check. The duplicate then
    // reported verified:true, indistinguishable from a real match. All 508
    // colliding pairs measured on v1.1.0 carried exactly that signature:
    // shift -1, adjacent order, verified true.
    // Three phases, so a contested node is awarded on EVIDENCE, not on the
    // order the loop happens to reach the cards in.
    //
    // Phase 1  a card's own css_path wins outright — positional authority.
    // Phase 2  every still-unresolved card bids its best unclaimed candidate
    //          from the shift ladder, carrying the signal that identified it.
    // Phase 3  each node goes to its strictly-strongest bidder; a tie goes to
    //          NOBODY and both stay honestly unresolved. Losers re-bid on their
    //          next-best node in the following round.
    //
    // Ranking matters because verify() collapsed three different grades of
    // evidence into one boolean. Measured on v1.1.0, 34 of 36 contested nodes
    // had a `len` bidder beating a `heading` bidder purely on loop order — a
    // +/-15% text-length window outranking a matched heading. `len` is the same
    // weak signal that let two adjacent "g tF2Cxc" organics impersonate each
    // other and produced all 508 original collisions.
    const claimed = new Map();          // element -> winning card index
    const out = new Array(cards.length).fill(null);

    cards.forEach((c, i) => {
        if (!c.path) { out[i] = {found: false}; return; }
        const el = q(c.path);
        const k = matchKind(el, c);
        if (k && !claimed.has(el)) {
            claimed.set(el, i);
            out[i] = rect(el, {verified: true, shift: 0});
        }
    });

    // Candidate ladder per unresolved card, best evidence first, then the
    // original ladder order as the within-grade tiebreak.
    const ladder = [-1, 1, -2, 2, -3, 3];
    const cands = cards.map((c, i) => {
        if (out[i] !== null) return [];
        const list = [];
        ladder.forEach((d, rank) => {
            const el = q(shifted(c.path, d));
            if (!el) return;
            const k = matchKind(el, c);
            if (k) list.push({el, d, k, rank});
        });
        return list.sort((a, b) => RANK[b.k] - RANK[a.k] || a.rank - b.rank);
    });

    for (let round = 0; round < ladder.length + 1; round++) {
        const bids = new Map();
        cards.forEach((c, i) => {
            if (out[i] !== null) return;
            const best = cands[i].find(x => !claimed.has(x.el));
            if (!best) return;
            if (!bids.has(best.el)) bids.set(best.el, []);
            bids.get(best.el).push({i, ...best});
        });
        let awarded = 0;
        bids.forEach((bs, el) => {
            if (claimed.has(el)) return;
            const top = Math.max(...bs.map(b => RANK[b.k]));
            const winners = bs.filter(b => RANK[b.k] === top);
            if (winners.length !== 1) return;   // tie -> nobody
            const b = winners[0];
            claimed.set(el, b.i);
            out[b.i] = rect(el, {verified: true, shift: b.d});
            awarded++;
        });
        if (!awarded) break;
    }

    cards.forEach((c, i) => {
        if (out[i] !== null) return;
        // Unresolvable: report the raw path hit (if any) as unverified rather
        // than inventing geometry -- Phase 2 of the map builder treats it as
        // missing.
        //
        // The loss is recorded in full so a downstream count can tell the two
        // very different causes apart:
        //   lost_to = <order>  the node belongs to another card. If that card
        //                      holds it at shift 0 it has own-css_path
        //                      authority, so this card's true node is simply
        //                      not reachable within +/-3 nth-of-type.
        //   lost_to = null     nobody holds it: this card tied with an equally
        //                      strong bidder and the tie went to neither.
        const el = c.path ? q(c.path) : null;
        const best = cands[i].length ? cands[i][0] : null;
        const holder = best ? claimed.get(best.el) : undefined;
        out[i] = {found: false, raw_path_hit: !!el, collided: !!best,
                  lost_with: best ? best.k : null,
                  lost_to: holder === undefined ? null : holder,
                  lost_to_shift: holder === undefined ? null
                                 : (out[holder] || {}).shift,
                  tied: !!best && holder === undefined};
    });
    return out;
}"""


def _structurally_same(path, result) -> bool:
    """True when a re-measure found the same cards at the same nodes.

    Re-rendering a saved SERP is not byte-deterministic: getBoundingClientRect
    lands a pixel either way of a rounding boundary, so a plain --force rewrites
    nearly every trial. Measured on the v1.1.0 corpus, 1,258 of 1,690 rewritten
    files differed by <=1px with an identical found-set and identical shifts --
    74% of the diff was noise, which buries the trials that actually moved and
    makes a substrate bump unreviewable.

    Structure is the found-set and the node each card resolved to -- (found,
    shift) identifies the node, since shift is the offset from the card's own
    css_path. Geometry within 1px of the stored value is the same measurement,
    so the file is left alone. Diagnostic fields are deliberately NOT compared:
    they live only on unresolved cards, so introducing one cannot rewrite the
    30k resolved cards that did not move.
    """
    if not path.exists():
        return False
    try:
        old = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if len(old) != len(result):
        return False
    for a, b in zip(old, result):
        if a.get('order') != b.get('order'):
            return False
        if bool(a.get('found')) != bool(b.get('found')):
            return False
        if a.get('shift') != b.get('shift'):
            return False
        if a.get('found') and any(abs(a.get(k, 0) - b.get(k, 0)) > 1
                                  for k in ('x', 'y', 'width', 'height')):
            return False
    return True


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
            out_path = OUT_DIR / f'{tid}.json'
            if not _structurally_same(out_path, result):
                out_path.write_text(json.dumps(result))
            else:
                counters['unchanged'] += 1
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
                'cards': 0, 'unchanged': 0, 'total': len(tids)}
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
          f'unchanged {counters["unchanged"]:,}',
          file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())
