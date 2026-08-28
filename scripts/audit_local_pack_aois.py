"""Audit — local-pack (maps) blocks vs the typed AOI map.

Sara Allawati (2026-08-28, "CHI27 Progress Update") spotted AdSERPs with
Google Maps / local-results blocks sitting in the main column between the
top ads and the organics — e.g. p040-b4-t6 ("Camera Stores"), p040-b1-t7
("Grocery Stores"). Ground truth (full-page screenshots): the block is a
real main-column card that the CV extractor bboxes, but Phase 1
(extract_html_widget_types.py) walks only #rso / #botstuff / #rhs — and in
these SERPs the pack lives OUTSIDE #rso, under div#Odp5De in the .M8OgIe
subtree of #rcnt. No HTML card is emitted, so Phase 2's index-based
bbox<->card matching assigns the pack's bbox to the first real card and
shifts every main-column label below it by one slot (same failure class as
the dd_top cellsplit rank shift).

This script quantifies exposure across the corpus:
  - which trials contain local-results content (.uMdZh / rllt__ markers)
  - where the pack lives (inside #rso / out-of-rso main column / #rhs)
  - whether the trial's typed map has a main-column top_places entry
  - how many main-column AOIs sit below the pack (rank-shift extent,
    computable once the typed map types the pack)

Run BEFORE and AFTER the Phase-1 fix; the summary records which state it
audited (a trial is "mis-shifted" if it has an out-of-rso main-column pack
but no main-column top_places entry in the typed map).

Outputs:
  scripts/output/aoi-typed/audit_local_pack_summary.json
  scripts/output/aoi-typed/audit_local_pack_trials.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
SERPS = ROOT / 'AdSERP/data/serps'
TYPED = ROOT / 'data/aoi-typed'
OUT = ROOT / 'scripts/output/aoi-typed'


def classify_pack_location(soup):
    """Return set of location labels for local-pack entries in this SERP.

    Labels: in_rso | out_of_rso_main | rhs | botstuff
    A .uMdZh div is one local-business entry (the rllt__ card wrapper).
    """
    locations = set()
    for el in soup.select('div.uMdZh'):
        parent_ids = set()
        cur = el
        while cur is not None and getattr(cur, 'name', None):
            pid = cur.get('id', '') if hasattr(cur, 'get') else ''
            if pid:
                parent_ids.add(pid)
            cur = cur.parent
        if 'rso' in parent_ids:
            locations.add('in_rso')
        elif 'rhs' in parent_ids:
            locations.add('rhs')
        elif 'botstuff' in parent_ids:
            locations.add('botstuff')
        else:
            locations.add('out_of_rso_main')
    return locations


def main():
    files = sorted(SERPS.glob('*.html'))
    print(f'[audit] {len(files):,} SERP HTML files', file=sys.stderr)

    rows = []
    for i, fp in enumerate(files):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(files)}', file=sys.stderr)
        tid = fp.stem
        html = fp.read_text(encoding='utf-8', errors='ignore')
        # Cheap pre-filter: skip the ~87% of trials with no local content
        if 'uMdZh' not in html and 'rllt__' not in html:
            continue
        soup = BeautifulSoup(html, 'html.parser')
        locations = classify_pack_location(soup)
        if not locations:
            # rllt__ string present but no .uMdZh entries (e.g. stylesheet
            # remnant); record for completeness
            locations = {'markers_only'}

        typed_path = TYPED / f'{tid}.json'
        typed = json.loads(typed_path.read_text()) if typed_path.exists() else []
        main_entries = [e for e in typed if e.get('position', -1) >= 0]
        tp_main = [e for e in main_entries if e['type'] == 'top_places']
        tp_any = [e for e in typed if e['type'] == 'top_places']

        # Rank-shift extent: main-column AOIs strictly below the pack.
        # Only computable when the typed map types the pack (post-fix).
        n_below_pack = None
        if tp_main:
            first_tp_pos = min(e['position'] for e in tp_main)
            n_below_pack = sum(1 for e in main_entries
                               if e['position'] > first_tp_pos)

        mis_shifted = ('out_of_rso_main' in locations) and not tp_main

        rows.append({
            'tid': tid,
            'locations': sorted(locations),
            'n_umdzh_entries': len(soup.select('div.uMdZh')),
            'n_main_entries': len(main_entries),
            'n_organic_main': sum(1 for e in main_entries
                                  if e['type'] == 'organic'),
            'has_top_places_main': bool(tp_main),
            'has_top_places_any': bool(tp_any),
            'n_below_pack': n_below_pack,
            'mis_shifted': mis_shifted,
        })

    loc_counter = Counter()
    for r in rows:
        for loc in r['locations']:
            loc_counter[loc] += 1

    mis = [r for r in rows if r['mis_shifted']]
    below = [r['n_below_pack'] for r in rows if r['n_below_pack'] is not None]

    summary = {
        'n_trials_scanned': len(files),
        'n_trials_with_local_content': len(rows),
        'pack_location_distribution': dict(loc_counter.most_common()),
        'n_mis_shifted': len(mis),
        'mis_shifted_tids': sorted(r['tid'] for r in mis),
        'n_typed_top_places_main': sum(1 for r in rows
                                       if r['has_top_places_main']),
        'rank_shift_extent': {
            'n_trials_with_typed_pack': len(below),
            'aois_below_pack_total': sum(below),
            'aois_below_pack_mean': (sum(below) / len(below)) if below else None,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'audit_local_pack_summary.json').write_text(
        json.dumps(summary, indent=2))
    with (OUT / 'audit_local_pack_trials.jsonl').open('w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')

    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
