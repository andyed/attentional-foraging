"""Score the typed AOI substrate against DOM ground truth.

Three checks. Click/AOI checks use independently resolved DOM evidence; the cell
check is a count diagnostic only and cannot certify boundaries or identity:

  click   every click event records the xpath of the element it hit. Render the
          saved SERP at the capture viewport and ask whether the recorded
          coordinate falls inside that element. Tests the coordinate model with
          no AOI involved.
  aoi     every typed AOI carries html_handle, and aoi-html-types carries the
          matching css_path. Resolve it, map the rendered box into screenshot
          space, and compare to the stored AOI box by IoU. Tests extraction.
  cell    carousel cards carry numbered DOM ids (vplaurlg<N>). Compare the
          visible card counts per top parent against top/main cells only.
          Missing exports, observed zeroes and unresolved pages remain explicit.

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
import hashlib
import math
from collections import Counter
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

JS = r"""(args) => {
  const out = {paths: {}, cells: [], click: null};
  // Resolve a card by IDENTITY, not by css_path.
  //
  // css_path is unreliable: _css_path() builds nth-of-type indices from
  // BeautifulSoup's parse and the browser's parse disagrees, so the selector
  // lands on a neighbour on a sizeable minority of cards (5 of 12 on
  // p004-b1-t5). Trusting it made this harness report the substrate as broken
  // on exactly the trials where the SELECTOR drifted -- see
  // docs/aoi-failure-diagnosis-2026-08-30.md, second correction.
  //
  // Nor can we reuse the pipeline's own resolution (css_path + shift ladder +
  // matchKind), because then the harness agrees with the pipeline by
  // construction and can never detect a resolution error. So: search the whole
  // document for an element whose class AND heading match what the card
  // recorded, and score only when that is UNAMBIGUOUS. Ambiguous cards are
  // skipped rather than guessed -- fewer scored cards, no invented failures.
  const norm = s => (s || '').replace(/\s+/g, '');
  const clsOf = el => (el.getAttribute('class') || '').split(/\s+/).filter(Boolean).join(' ');
  const headOf = el => { const h = el.querySelector('h3') || el.querySelector('h2')
                                || el.querySelector('[role="heading"]'); return h ? h.textContent : ''; };
  const all = [...document.querySelectorAll('#rso *, #rso')];
  for (const [handle, card] of Object.entries(args.cards)) {
    if (!card.cls && !card.heading) continue;          // nothing to identify it by
    const hits = all.filter(el => {
      if (clsOf(el) !== (card.cls || '')) return false;
      if (card.heading) {
        return norm(headOf(el)).slice(0, 30) === norm(card.heading).slice(0, 30);
      }
      return true;
    });
    if (hits.length !== 1) { out.ambiguous = (out.ambiguous || 0) + 1; continue; }
    const r = hits[0].getBoundingClientRect();
    if (r.width < 1) continue;
    out.paths[handle] = {x: r.left+window.scrollX, y: r.top+window.scrollY,
                         w: r.width, h: r.height};
  }
  // Count independently from the candidate .pla-unit enumerator: start with
  // numbered product links, scope each to its own top parent, and deduplicate
  // aliases only within the same card node. Count positive visible CARD area;
  // a partially exposed card counts even when its image is clipped away.
  const topParents=[...document.querySelectorAll('.commercial-unit-desktop-top')];
  const groups=topParents.map(el=>({el,ids:new Map(),cards:new Set(),count:0,issues:[]}));
  const clipped = el => {
    const r=el.getBoundingClientRect(); let left=Math.max(r.left,0),right=Math.min(r.right,document.documentElement.clientWidth),top=r.top,bottom=r.bottom;
    for(let p=el;p;p=p.parentElement) {
      const cs=getComputedStyle(p);
      if(cs.display==='none'||['hidden','collapse'].includes(cs.visibility)||+cs.opacity===0) return false;
      if(cs.clipPath!=='none') return null;
      if(p===el) continue;
      const pr=p.getBoundingClientRect(),sx=p.offsetWidth ? pr.width/p.offsetWidth : 1,sy=p.offsetHeight ? pr.height/p.offsetHeight : 1;
      if(/^(hidden|clip|scroll|auto)$/.test(cs.overflowX)) {
        left=Math.max(left,pr.left+p.clientLeft*sx);right=Math.min(right,pr.left+(p.clientLeft+p.clientWidth)*sx);
      }
      if(/^(hidden|clip|scroll|auto)$/.test(cs.overflowY)) {
        top=Math.max(top,pr.top+p.clientTop*sy);bottom=Math.min(bottom,pr.top+(p.clientTop+p.clientHeight)*sy);
      }
    }
    return right>left && bottom>top;
  };
  let unscoped=0,offaxis=0;
  document.querySelectorAll('[id^="vplaurlg"]').forEach(link=>{
    if(!/^vplaurlg(\d+)$/.test(link.id)) return;
    const parent=link.closest('.commercial-unit-desktop-top'),group=groups.find(g=>g.el===parent);
    if(!group) {
      if(link.closest('.commercial-unit-desktop-rhs, #rhs')) offaxis++; else unscoped++;
      return;
    }
    const card=link.closest('.pla-unit');
    if(!card || card.closest('.commercial-unit-desktop-top')!==parent) {group.issues.push('unsupported_card_container');return;}
    if(group.ids.has(link.id) && group.ids.get(link.id)!==card) group.issues.push('duplicate_card_identity');
    group.ids.set(link.id,card);
    if(group.cards.has(card)) return;
    group.cards.add(card);
    const visible=clipped(card);
    if(visible===null) group.issues.push('unsupported_clip_path');
    if(visible) group.count++;
  });
  out.cell_parents=groups.map((g,i)=>{ const r=g.el.getBoundingClientRect();
    if(!g.cards.size) g.issues.push('no_supported_cards');
    return {dom_parent_index:i,count:g.count,issues:[...new Set(g.issues)],rect:{x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height}};
  });
  out.cell_unscoped_links=unscoped;
  out.cell_offaxis_links=offaxis;
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


def cellsplit_inventory(path=None):
    """Distinguish a present trial with zero top cells from a missing export.

    Scope is exactly role=cell, parent_etype=dd_top, main_axis=true.
    The parent rows supply explicit zero-cell observations and parent ranks.
    """
    path = Path(path) if path is not None else CELLSPLIT
    trials = {}
    if not path.exists():
        return trials
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tid = r['trial_id']
            trial = trials.setdefault(tid, {'count': 0, 'parents': {}, 'issues': []})
            if r.get('parent_etype') != 'dd_top' or r.get('main_axis', '').lower() != 'true':
                continue
            rank = r.get('parent_rank', '')
            if r.get('role') == 'cell':
                trial['count'] += 1
                parent = trial['parents'].setdefault(rank, {'count': 0, 'rect': None, 'cell_indices': set()})
                parent['count'] += 1
                idx=r.get('cell_index')
                try:
                    if str(int(idx)) != idx or int(idx)<0:
                        raise ValueError('noncanonical cell index')
                except (TypeError, ValueError):
                    trial['issues'].append('invalid_cell_index')
                if idx in parent['cell_indices']:
                    trial['issues'].append('duplicate_cell_index')
                parent['cell_indices'].add(idx)
                if r.get('cell_index') in (None, ''):
                    trial['issues'].append('missing_cell_index')
            elif r.get('role') == 'parent':
                parent = trial['parents'].setdefault(rank, {'count': 0, 'rect': None, 'cell_indices': set()})
                if parent['rect'] is not None:
                    trial['issues'].append('duplicate_export_parent')
                try:
                    x, y = float(r['left_x']), float(r['top_y'])
                    box={'x': x, 'y': y, 'w': float(r['right_x'])-x, 'h': float(r['bottom_y'])-y}
                    if not all(math.isfinite(v) for v in box.values()) or min(box['w'],box['h'])<=0:
                        raise ValueError('invalid rectangle')
                    parent['rect'] = box
                except (ValueError, KeyError):
                    trial['issues'].append('invalid_export_parent_rect')
    return trials


def cellsplit_counts(path=None):
    return {tid: row['count'] for tid, row in cellsplit_inventory(path).items()}


def compare_cells(res, exported, rx, ry, typed_top_count=0):
    parents = res.get('cell_parents', [])
    dom = sum(p['count'] for p in parents)
    exp = exported['count'] if exported is not None else 0
    issues = list(exported['issues']) if exported else []
    if res.get('cell_unscoped_links'):
        issues.append('unscoped_product_links')
    issues.extend(issue for p in parents for issue in p['issues'])
    comparisons, claimed = [], set()
    export_parents = exported['parents'] if exported else {}
    for p in parents:
        b=p['rect']; d={'x':b['x']*rx,'y':b['y']*ry,'w':b['w']*rx,'h':b['h']*ry}
        hits=[]
        for rank, entry in export_parents.items():
            e=entry['rect']
            if e is None:
                continue
            inter=max(0,min(d['x']+d['w'],e['x']+e['w'])-max(d['x'],e['x']))*max(0,min(d['y']+d['h'],e['y']+e['h'])-max(d['y'],e['y']))
            if inter/max(d['w']*d['h'],1)>=0.5:
                hits.append(rank)
        if len(hits)>1 or (hits and hits[0] in claimed):
            issues.append('ambiguous_export_parent')
            continue
        rank=hits[0] if hits else None
        if rank is not None:
            claimed.add(rank)
        comparisons.append({'dom_parent_index':p['dom_parent_index'],'export_parent_rank':rank,
                            'dom_cells':p['count'],'export_cells':export_parents[rank]['count'] if rank is not None else 0,
                            'status':'matched' if rank is not None else 'missing_export_parent'})
    for rank, entry in export_parents.items():
        if rank not in claimed:
            comparisons.append({'dom_parent_index':None,'export_parent_rank':rank,'dom_cells':0,
                                'export_cells':entry['count'],'status':'export_only_parent'})
            if entry['rect'] is None:
                issues.append('missing_export_parent_rect')
    # A typed parent with no recognized DOM template is unresolved, not a
    # certified zero-card page. Keep the evidence in the denominator ledger.
    if typed_top_count > len(parents):
        issues.append('unresolved_typed_parent')
    status = 'unresolved' if issues else ('scored' if parents or export_parents or typed_top_count else 'absent')
    return {'dom_cells':dom,'export_cells':exp,'cell_export_present':exported is not None,
            'cell_status':status,'cell_issues':sorted(set(issues)),'cell_parent_comparisons':comparisons,
            'cell_count_agree':all(p['dom_cells']==p['export_cells'] for p in comparisons) if status=='scored' else None}


async def score(tids, verbose=False):
    cs = cellsplit_inventory()
    rows = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={'width': CAPTURE_VIEWPORT, 'height': 1024})
        await ctx.route('http://**/*', lambda route: route.abort())
        await ctx.route('https://**/*', lambda route: route.abort())
        page = await ctx.new_page()
        for n, tid in enumerate(tids, 1):
            serp = SERPS_CACHED / f'{tid}.html'
            if not serp.exists():
                serp = SERPS / f'{tid}.html'
            failure = {'tid':tid,'click_ok':None,'aoi_iou_median':None,'aoi_n':0,
                       'dom_cells':None,'export_cells':cs.get(tid,{}).get('count'),
                       'cell_export_present':tid in cs,'cell_status':'unresolved'}
            if not serp.exists():
                rows.append(dict(failure,cell_issues=['missing_html']))
                continue
            try:
                cards = json.loads((HTML_TYPES / f'{tid}.json').read_text())
                aois = json.loads((TYPED / f'{tid}.json').read_text())
            except Exception as e:
                rows.append(dict(failure,cell_issues=['missing_or_invalid_aoi_input'],error=str(e)))
                continue
            paths = {c['html_handle']: {'cls': c.get('css_class', ''),
                                       'heading': c.get('heading_text', '')}
                     for c in cards if c.get('html_handle')}
            click = final_click(tid)
            try:
                await page.goto(f'file://{serp}', wait_until='load', timeout=20000)
            except Exception as e:
                rows.append(dict(failure,cell_issues=['navigation_failed'],error=str(e)))
                continue
            await page.wait_for_timeout(90)
            try:
                res = await page.evaluate(JS, {'cards': paths, 'mainMaxX': MAIN_MAX_X,
                                               'clickXpath': click[2] if click else None})
            except Exception as e:
                rows.append(dict(failure,cell_issues=['dom_evaluation_failed'],error=str(e)))
                continue
            rx, ry = ratios(tid) or (None, None)
            if rx is None:
                rows.append(dict(failure,cell_issues=['missing_coordinate_metadata']))
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
            cell_result = compare_cells(res, cs.get(tid), rx, ry,
                                        sum(a.get('type')=='dd_top' and a.get('position',-1)>=0 for a in aois))

            rows.append({'tid': tid,
                         'click_ok': click_ok,
                         'aoi_iou_median': statistics.median(ious) if ious else None,
                         'aoi_n': len(ious),
                         **cell_result,
                         'ratio_x': round(rx, 4), 'ratio_y': round(ry, 4)})
            if verbose:
                print(f"  {tid}: click={click_ok} iou={rows[-1]['aoi_iou_median']} "
                      f"cells {cell_result['cell_status']} dom={cell_result['dom_cells']} export={cell_result['export_cells']}", flush=True)
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
    summary = cell_summary(rows)
    print("\n  cell      top/main product cards, any positive visible card area")
    print("            count agreement only; not boundary or identity fidelity")
    print("            " + json.dumps(summary, sort_keys=True))
    print(f"\n{'='*66}")


def cell_summary(rows):
    cc=[r for r in rows if r.get('cell_status')=='scored']
    comparisons=[p for r in cc for p in r['cell_parent_comparisons']]
    return {'requested_trials':len(rows),'scored_trials':len(cc),
            'agree_trials':sum(r['cell_count_agree'] for r in cc),
            'unresolved_trials':sum(r.get('cell_status')=='unresolved' for r in rows),
            'absent_trials':sum(r.get('cell_status')=='absent' for r in rows),
            'missing_export_trials':sum(not r.get('cell_export_present',False) for r in rows),
            'compared_parents':len(comparisons),
            'agree_parents':sum(p['dom_cells']==p['export_cells'] for p in comparisons),
            'short_parents':sum(p['export_cells']<p['dom_cells'] for p in comparisons),
            'over_parents':sum(p['export_cells']>p['dom_cells'] for p in comparisons),
            'issue_counts':dict(Counter(issue for r in rows for issue in r.get('cell_issues',[])))}


def main():
    global CELLSPLIT
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--trials', nargs='*')
    ap.add_argument('--limit', type=int, default=120)
    ap.add_argument('--json')
    ap.add_argument('--cellsplit',type=Path,default=CELLSPLIT,help='Explicit cell export to audit; default is the released snapshot')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    CELLSPLIT = a.cellsplit
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
        meta={'schema':'allserp-aoi-fidelity-v2','cell_metric':'per-parent top/main visible card count agreement; not geometry fidelity',
              'visibility':'positive card area after ancestor clips; no vertical viewport or temporal exposure inference',
              'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cellsplit_sha256':hashlib.sha256(CELLSPLIT.read_bytes()).hexdigest() if CELLSPLIT.exists() else None,
              'viewport':CAPTURE_VIEWPORT,'network':'blocked','summary':cell_summary(rows)}
        Path(a.json+'.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
        print(f"  wrote {a.json} and metadata sidecar")


if __name__ == '__main__':
    main()
