"""Zero-paging audit for the top-ads (dd_top) carousel, keyed on the clicked element.

Why this exists. The 2026-08-30 check (crforager docs/notes/carousel-paging-and-scent-2026-08-30.md)
assigned each click to a cell by its screen position and found 272/272 clicks inside the
visible strip. A click inside the visible strip is visible by construction, so that check
could not have detected paging. This audit uses the element evtrack says was clicked.

Every click event in the corpus is walked. Its xpath (anchored on an element id) is resolved
against the captured HTML, and the click is classified by what it hit:

  top_card        inside a product card of a `.commercial-unit-desktop-top` unit. The card's
                  load-time visible_fraction comes from the DOM candidate report, which lists
                  every card including the hidden tail. visible_fraction 0 = a paged-in card.
  top_other       inside the top unit but not in a card (whitespace, container).
  paging_control  a g-left-button / g-right-button (the carousel's Previous / Next arrows),
                  with the carousel it belongs to and whether that is the top ads unit.
  rhs_card        a right-rail shopping card (`.commercial-unit-desktop-rhs`); out of scope,
                  counted so the denominator is explicit.

Run:  .venv/bin/python scripts/audit_carousel_paging.py
Writes docs/evidence/carousel-paging-2026-09-26/audit.json. Exits non-zero if no top-card
click joins the DOM report (a blind audit must not report success).
"""
from __future__ import annotations
import argparse, collections, csv, gzip, json, re, sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/evidence/carousel-2026-09-04/corpus/candidate-report.json.gz'
MOUSE = ROOT / 'AdSERP/data/mouse-movement-data'
HTML = ROOT / 'AdSERP/data/serps-cached'
OUT = ROOT / 'docs/evidence/carousel-paging-2026-09-26/audit.json'
ANCHOR_RE = re.compile(r"^//\*\[@id='([^']+)'\](.*)$")
STEP_RE = re.compile(r'^([\w-]+)(?:\[(\d+)\])?$')


def resolve(soup, xpath):
    """Walk an evtrack xpath (id anchor + tag[n] steps). Returns the element or None."""
    m = ANCHOR_RE.match(xpath or '')
    if not m:
        return None
    el = soup.find(id=m.group(1))
    for step in (s for s in m.group(2).split('/') if s):
        if el is None:
            return None
        mm = STEP_RE.match(step)
        if not mm:
            return None
        kids = el.find_all(mm.group(1), recursive=False)
        i = int(mm.group(2) or 1) - 1
        el = kids[i] if 0 <= i < len(kids) else None
    return el


def card_id(el):
    unit = el.find_parent(class_='pla-unit') if el is not None else None
    if unit is None and el is not None and 'pla-unit' in (el.get('class') or []):
        unit = el
    if unit is None:
        return None
    g = unit.find(id=re.compile(r'^vplaurlg\d+$'))
    return g.get('id') if g else unit.get('id')


def classify(el, cards):
    """Classify a resolved click target. `cards` maps card_id -> DOM-report cell (all cards,
    hidden tail included). Returns a dict, or None when the click is outside every carousel."""
    top = el.find_parent(class_='commercial-unit-desktop-top')
    rhs = el.find_parent(class_='commercial-unit-desktop-rhs')
    btn = el if el.name in ('g-left-button', 'g-right-button') else el.find_parent(['g-left-button', 'g-right-button'])
    if btn is not None:
        car = btn.find_parent('g-scrolling-carousel')
        return {'kind': 'paging_control', 'direction': btn.name.split('-')[1],
                'in_top_ads_unit': top is not None,
                'product_cards_in_carousel': len(car.select('.pla-unit')) if car else None}
    if top is not None:
        cid = card_id(el)
        if cid is None:
            return {'kind': 'top_other'}
        c = cards.get(cid)
        if c is None:
            return {'kind': 'top_card', 'card_id': cid, 'visibility': 'card_not_in_report'}
        vf = c.get('visible_fraction') or 0
        return {'kind': 'top_card', 'card_id': cid, 'dom_order': c.get('dom_order'), 'visible_fraction': vf,
                'n_cards': len(cards), 'n_visible': sum(1 for k in cards.values() if (k.get('visible_fraction') or 0) > 0),
                'visibility': 'hidden_at_load' if vf == 0 else ('partial_at_load' if vf < 1 else 'visible_at_load')}
    if rhs is not None and card_id(el):
        return {'kind': 'rhs_card', 'card_id': card_id(el)}
    return None


def load_report():
    with gzip.open(REPORT, 'rt') as f:
        d = json.load(f)
    out = {}
    for t in d['trials']:
        cards = {c['card_id']: c for p in (t.get('parents') or []) for c in (p.get('cells') or [])}
        out[t['trial_id']] = {'cards': cards, 'outcome': t.get('corpus_outcome'),
                              'eligible': t.get('analysis_eligible')}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args()
    report = load_report()
    rows, n_clicks, n_trials = [], 0, 0
    unresolved = []
    for path in sorted(MOUSE.glob('*.csv')):
        tid = path.stem
        with open(path) as f:
            clicks = [r for r in csv.DictReader(f) if r['event'] == 'click']
        n_trials += 1
        n_clicks += len(clicks)
        cand = list(enumerate(clicks))  # no prefilter: every click is resolved, so nothing is skipped by id shape
        if not cand:
            continue
        soup = BeautifulSoup((HTML / f'{tid}.html').read_text(errors='replace'), 'html.parser')
        for i, r in cand:
            el = resolve(soup, r['xpath'])
            if el is None:
                unresolved.append({'trial_id': tid, 'click_seq': i, 'xpath': r['xpath'],
                                   'xpos': r['xpos'], 'ypos': r['ypos']})
                continue
            rec = {'trial_id': tid, 'click_seq': i, 'n_clicks_in_trial': len(clicks),
                   't_ms': int(float(r['timestamp'])), 'xpath': r['xpath']}
            cls = classify(el, report.get(tid, {}).get('cards', {}))
            if cls is None:
                continue
            rec.update(cls)
            rows.append(rec)

    # Per-trial ordering: which top-card clicks came after a paging-control click.
    paged_at = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == 'paging_control' and r['in_top_ads_unit']:
            paged_at[r['trial_id']].append(r['t_ms'])
    for r in rows:
        if r['kind'] == 'top_card':
            r['after_top_paging_click'] = any(t < r['t_ms'] for t in paged_at.get(r['trial_id'], []))

    top = [r for r in rows if r['kind'] == 'top_card']
    ctl = [r for r in rows if r['kind'] == 'paging_control']
    summary = {
        'trials_scanned': n_trials,
        'click_events_total': n_clicks,
        'top_card_clicks': len(top),
        'top_card_click_trials': len({r['trial_id'] for r in top}),
        'top_card_visibility_at_load': dict(collections.Counter(r['visibility'] for r in top)),
        'top_card_clicks_by_dom_order': dict(sorted(collections.Counter(r.get('dom_order') for r in top if r.get('dom_order') is not None).items())),
        'top_card_clicks_after_a_top_paging_click': sum(1 for r in top if r['after_top_paging_click']),
        'top_other_clicks': sum(1 for r in rows if r['kind'] == 'top_other'),
        'paging_control_clicks': len(ctl),
        'paging_control_clicks_on_top_ads_carousel': sum(1 for r in ctl if r['in_top_ads_unit']),
        'paging_control_trials_on_top_ads_carousel': sorted({r['trial_id'] for r in ctl if r['in_top_ads_unit']}),
        'unresolved_xpaths': len(unresolved),
        'unresolved_xpath_anchors': dict(collections.Counter((ANCHOR_RE.match(u['xpath'] or '') or [None, 'no_anchor'])[1] for u in unresolved).most_common(10)),
        'rhs_card_clicks_out_of_scope': sum(1 for r in rows if r['kind'] == 'rhs_card'),
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'summary': summary, 'rows': rows, 'unresolved': unresolved,
                               'inputs': {'dom_report': str(REPORT.relative_to(ROOT)),
                                          'mouse': str(MOUSE.relative_to(ROOT)),
                                          'html': str(HTML.relative_to(ROOT))}}, indent=1))
    print(json.dumps(summary, indent=1))
    joined = sum(1 for r in top if r['visibility'] != 'card_not_in_report')
    if joined == 0:
        print('FAIL: no top-card click joined the DOM report; the audit is blind', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
