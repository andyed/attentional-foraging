"""Phase 2 — spatial join of HTML widget types onto bbox AOIs.

Combines:
  - data/aoi-html-types/<tid>.json (Phase 1 output: ordered typed cards)
  - AdSERP/data/organic-boundary-data{,-gapfill}/<tid>.json (CV-extracted
    bboxes: organic_result + widget slots)
  - AdSERP/data/ad-boundary-data/<tid>.json (dd_top, native_ad, dd_right)

Outputs per-trial:
  data/aoi-typed{,-gapfill}/<tid>.json
  [
    {"position": 0, "type": "organic", "x": 162, "y": 133, "width": 586,
     "height": 508, "html_handle": "rso[7]", "html_signature": "..."},
    {"position": 1, "type": "knowledge_panel", "x": 162, "y": 675,
     "width": 586, "height": 256, "html_handle": "rso[15]", ...},
    ...
    {"position": -1, "type": "related_searches", "html_handle":
     "botstuff.ULSxyf[0]", "x": null, ...}   # no scroll-axis position
  ]

Position is the display-order index in the main column (organic + widget +
top-column ads) sorted by y. dd_right and #botstuff / #rhs items get
position=-1.

Run:
  .venv/bin/python scripts/build_typed_aoi_map.py
  .venv/bin/python scripts/build_typed_aoi_map.py --source organic_gapfill

Source flavors:
  organic         (default) — tight CV-extracted bboxes (legacy)
  organic_gapfill           — midpoint-split bboxes; see
                              docs/null-findings/2026-05-05-bbox-y-coverage.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
HTML_TYPES = ROOT / 'data/aoi-html-types'
AD_BBOX = ROOT / 'AdSERP/data/ad-boundary-data'

ORGANIC_BBOX_BY_SOURCE = {
    'organic': ROOT / 'AdSERP/data/organic-boundary-data',
    'organic_gapfill': ROOT / 'AdSERP/data/organic-boundary-data-gapfill',
}
OUT_DIR_BY_SOURCE = {
    'organic': ROOT / 'data/aoi-typed',
    'organic_gapfill': ROOT / 'data/aoi-typed-gapfill',
}

# These globals are set by main() based on --source. Module-level functions
# read them via the configure() helper so existing imports keep working.
ORGANIC_BBOX = ORGANIC_BBOX_BY_SOURCE['organic']
OUT_DIR = OUT_DIR_BY_SOURCE['organic']
OUT_DIR.mkdir(parents=True, exist_ok=True)


def configure(source: str) -> None:
    """Switch the producer to read/write the given flavor."""
    global ORGANIC_BBOX, OUT_DIR
    ORGANIC_BBOX = ORGANIC_BBOX_BY_SOURCE[source]
    OUT_DIR = OUT_DIR_BY_SOURCE[source]
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _bbox_from(entry, kind):
    """Normalize a bbox record to dict {x, y, width, height, kind}."""
    loc = entry.get('location', {})
    sz = entry.get('size', {})
    return {
        'x': float(loc.get('x', 0)),
        'y': float(loc.get('y', 0)),
        'width': float(sz.get('width', 0)),
        'height': float(sz.get('height', 0)),
        'kind': kind,
    }


def _bbox_overlap_frac(a, b):
    """Return fraction of bbox a's area covered by bbox b."""
    ax2 = a['x'] + a['width']
    ay2 = a['y'] + a['height']
    bx2 = b['x'] + b['width']
    by2 = b['y'] + b['height']
    ix1 = max(a['x'], b['x'])
    iy1 = max(a['y'], b['y'])
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    a_area = a['width'] * a['height']
    return inter / a_area if a_area > 0 else 0.0


def join_one_trial(tid):
    """Produce typed AOI map for one trial. Returns (result_list, audit_dict).

    Strategy:
      1. Walk bbox `organic_result` + bbox `widget` lists in y-order — these
         are the visually-detected cards in the main column. The bbox
         extractor's ad_overlap_threshold doesn't always exclude ads, so for
         each bbox, check overlap with ad-boundary-data ads. Overlapping >= 30%
         = the bbox IS the ad.
      2. Non-ad bboxes get matched in y-order to HTML #rso cards in DOM
         order. The kth non-ad bbox <-> kth HTML card.
      3. dd_top / native_ad ad-bboxes that did NOT overlap any cv-bbox get
         appended as their own entries (rare; means CV missed the ad).
      4. dd_right ads, #botstuff cards, #rhs cards: position = -1 (no scroll
         axis position).
    """
    html_path = HTML_TYPES / f'{tid}.json'
    bbox_path = ORGANIC_BBOX / f'{tid}.json'
    ad_path = AD_BBOX / f'{tid}.json'

    if not html_path.exists() or not bbox_path.exists():
        return None, {'reason': 'missing-source-file', 'html': html_path.exists(),
                      'bbox': bbox_path.exists()}

    html_cards = json.loads(html_path.read_text())
    bbox = json.loads(bbox_path.read_text())
    ads = json.loads(ad_path.read_text()) if ad_path.exists() else {}

    # Bboxes in main column (cv-detected)
    main_bboxes = []
    for ob in bbox.get('organic_result', []):
        main_bboxes.append(_bbox_from(ob, 'cv_organic_slot'))
    for wb in bbox.get('widget', []):
        main_bboxes.append(_bbox_from(wb, 'cv_widget_slot'))
    main_bboxes.sort(key=lambda b: b['y'])

    # Ad bboxes (top-of-column ads only)
    ad_bboxes = []
    for ad in ads.get('dd_top', []):
        ad_bb = _bbox_from(ad, 'cv_ad')
        ad_bb['type'] = 'dd_top'
        ad_bboxes.append(ad_bb)
    for ad in ads.get('native_ad', []):
        ad_bb = _bbox_from(ad, 'cv_ad')
        ad_bb['type'] = 'native_ad'
        ad_bboxes.append(ad_bb)

    # Right-rail ads — position -1
    rhs_ads = [{**_bbox_from(ad, 'cv_ad'), 'type': 'dd_right'}
               for ad in ads.get('dd_right', [])]

    # HTML cards
    html_rso = [c for c in html_cards if c.get('container') == 'rso']
    html_botstuff = [c for c in html_cards if c.get('container') == 'botstuff']
    html_rhs = [c for c in html_cards if c.get('container') == 'rhs']

    # ── Step 1+2: classify each main bbox ──
    # For each main bbox, check overlap with any ad bbox. If overlap >= 30%,
    # it IS the ad. Otherwise it's a non-ad bbox awaiting HTML match.
    used_ad_indices = set()
    main_entries = []        # list of dicts in y-order (the main scroll axis)
    non_ad_bbox_indices = []

    for i, b in enumerate(main_bboxes):
        ad_match = None
        for j, ad_bb in enumerate(ad_bboxes):
            if j in used_ad_indices:
                continue
            if _bbox_overlap_frac(b, ad_bb) >= 0.30 or _bbox_overlap_frac(ad_bb, b) >= 0.30:
                ad_match = (j, ad_bb)
                break
        if ad_match is not None:
            j, ad_bb = ad_match
            used_ad_indices.add(j)
            main_entries.append({
                'type': ad_bb['type'],
                'x': b['x'], 'y': b['y'], 'width': b['width'], 'height': b['height'],
                'html_handle': None,
                'html_signature': '',
                'heading_text': '',
                'source': 'cv_bbox+ad_overlap',
            })
        else:
            non_ad_bbox_indices.append(i)

    # Match non-ad bboxes to HTML cards in DOM order
    matched_count = min(len(non_ad_bbox_indices), len(html_rso))
    for k in range(matched_count):
        b = main_bboxes[non_ad_bbox_indices[k]]
        h = html_rso[k]
        main_entries.append({
            'type': h['type'],
            'x': b['x'], 'y': b['y'], 'width': b['width'], 'height': b['height'],
            'html_handle': h['html_handle'],
            'html_signature': h.get('html_signature', ''),
            'heading_text': h.get('heading_text', ''),
            'source': 'html_rso+cv_bbox',
        })

    # Unmatched bboxes (cv saw, html had no card at this index)
    n_unmatched_bbox = 0
    for k in range(matched_count, len(non_ad_bbox_indices)):
        b = main_bboxes[non_ad_bbox_indices[k]]
        main_entries.append({
            'type': 'unknown_widget',
            'x': b['x'], 'y': b['y'], 'width': b['width'], 'height': b['height'],
            'html_handle': None,
            'html_signature': '',
            'heading_text': '',
            'source': 'cv_bbox_only',
        })
        n_unmatched_bbox += 1

    # Unmatched HTML cards (html had cards cv didn't bbox)
    unmatched_html = []
    for k in range(matched_count, len(html_rso)):
        h = html_rso[k]
        unmatched_html.append({
            'type': h['type'],
            'x': None, 'y': None, 'width': None, 'height': None,
            'html_handle': h['html_handle'],
            'html_signature': h.get('html_signature', ''),
            'heading_text': h.get('heading_text', ''),
            'source': 'html_only',
        })

    # Append ad bboxes that didn't overlap any cv bbox (cv missed them)
    n_ads_appended_separately = 0
    for j, ad_bb in enumerate(ad_bboxes):
        if j in used_ad_indices:
            continue
        main_entries.append({
            'type': ad_bb['type'],
            'x': ad_bb['x'], 'y': ad_bb['y'], 'width': ad_bb['width'],
            'height': ad_bb['height'],
            'html_handle': None,
            'html_signature': '',
            'heading_text': '',
            'source': 'ad_only',
        })
        n_ads_appended_separately += 1

    # Sort main entries by y (preliminary)
    main_entries.sort(key=lambda e: e.get('y') if e.get('y') is not None else 99999)

    # ── Chrome heuristic: sweep bottom-of-page unknown_widget cells ──
    # cv-detected cells at deep tentative position (>=10) with small height
    # (<200 px) are footer / pagination / promotional-band artifacts that
    # Google's HTML doesn't structure as named widgets. Relabel to `chrome`
    # and pull off the main scroll axis (position = -1).
    chrome_entries = []
    survivors = []
    for tentative_pos, e in enumerate(main_entries):
        if (e['type'] == 'unknown_widget'
                and e.get('height') is not None
                and e['height'] < 200
                and tentative_pos >= 10):
            chrome_entry = dict(e)
            chrome_entry['type'] = 'chrome'
            chrome_entry['source'] = (e.get('source', '') + '+chrome_heuristic').lstrip('+')
            chrome_entries.append(chrome_entry)
        else:
            survivors.append(e)
    main_entries = survivors

    # Assign positions
    result = []
    for i, e in enumerate(main_entries):
        result.append({**e, 'position': i})

    # Append unmatched HTML (no bbox) with position -1
    for e in unmatched_html:
        result.append({**e, 'position': -1})

    # Append #botstuff cards (Related searches) — position -1
    for c in html_botstuff:
        result.append({
            'type': c['type'],
            'x': None, 'y': None, 'width': None, 'height': None,
            'html_handle': c['html_handle'],
            'html_signature': c.get('html_signature', ''),
            'heading_text': c.get('heading_text', ''),
            'source': 'html_botstuff',
            'position': -1,
        })

    # Append #rhs cards (right-rail KP) — position -1
    for c in html_rhs:
        result.append({
            'type': c['type'],
            'x': None, 'y': None, 'width': None, 'height': None,
            'html_handle': c['html_handle'],
            'html_signature': c.get('html_signature', ''),
            'heading_text': c.get('heading_text', ''),
            'source': 'html_rhs',
            'position': -1,
        })

    # Append dd_right (right-rail ads) — position -1
    for ad in rhs_ads:
        result.append({
            'type': 'dd_right',
            'x': ad['x'], 'y': ad['y'],
            'width': ad['width'], 'height': ad['height'],
            'html_handle': None,
            'html_signature': '',
            'heading_text': '',
            'source': 'cv_ad_rhs',
            'position': -1,
        })

    # Append chrome entries swept from bottom of main column — position -1
    for ch in chrome_entries:
        result.append({**ch, 'position': -1})

    audit = {
        'n_html_rso': len(html_rso),
        'n_bbox_main': len(main_bboxes),
        'n_ad_bboxes': len(ad_bboxes),
        'n_ad_matched_to_cv_bbox': len(used_ad_indices),
        'n_ad_appended_separately': n_ads_appended_separately,
        'n_chrome_swept': len(chrome_entries),
        'n_non_ad_bbox': len(non_ad_bbox_indices),
        'n_matched': matched_count,
        'n_unmatched_bbox': n_unmatched_bbox,
        'n_unmatched_html': len(unmatched_html),
        'n_botstuff': len(html_botstuff),
        'n_rhs': len(html_rhs),
        'n_dd_top': len(ads.get('dd_top', [])),
        'n_native_ad': len(ads.get('native_ad', [])),
        'n_dd_right': len(ads.get('dd_right', [])),
        'flags': bbox.get('_meta', {}).get('flags', []),
    }

    return result, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument(
        '--source',
        choices=list(ORGANIC_BBOX_BY_SOURCE.keys()),
        default='organic',
        help='Source flavor for organic bboxes (organic = legacy tight; '
             'organic_gapfill = midpoint-split applied)',
    )
    args = parser.parse_args()
    configure(args.source)

    files = sorted(HTML_TYPES.glob('*.json'))
    print(f'[join] {len(files):,} HTML-typed files (source={args.source})',
          file=sys.stderr)

    type_counter = Counter()
    n_matched_total = 0
    n_unmatched_bbox_total = 0
    n_unmatched_html_total = 0
    audits = []
    errors = 0

    for i, fp in enumerate(files):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(files)}', file=sys.stderr)
        tid = fp.stem
        try:
            result, audit = join_one_trial(tid)
        except Exception as e:
            print(f'  ERROR on {tid}: {e}', file=sys.stderr)
            errors += 1
            continue
        if result is None:
            errors += 1
            continue

        for r in result:
            type_counter[r['type']] += 1

        n_matched_total += audit['n_matched']
        n_unmatched_bbox_total += audit['n_unmatched_bbox']
        n_unmatched_html_total += audit['n_unmatched_html']
        audits.append({'tid': tid, **audit})

        out_path = OUT_DIR / f'{tid}.json'
        out_path.write_text(json.dumps(result, indent=2))

    summary = {
        'source_flavor': args.source,
        'organic_bbox_dir': str(ORGANIC_BBOX),
        'out_dir': str(OUT_DIR),
        'n_trials': len(files),
        'n_errors': errors,
        'type_distribution_total': dict(type_counter.most_common()),
        'matching_summary': {
            'matched_total': n_matched_total,
            'unmatched_bbox_total': n_unmatched_bbox_total,
            'unmatched_html_total': n_unmatched_html_total,
        },
        'mismatch_distribution': {
            # how many trials with each Δ = n_html_rso − n_bbox_main
            **{str(k): v for k, v in
               Counter(a['n_html_rso'] - a['n_bbox_main'] for a in audits).most_common()},
        },
    }

    out_subdir = 'aoi-typed-gapfill' if args.source == 'organic_gapfill' else 'aoi-typed'
    summary_path = ROOT / f'scripts/output/{out_subdir}/build_typed_aoi_map_summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))

    # Per-trial audits (long; dump as JSONL)
    audits_path = ROOT / f'scripts/output/{out_subdir}/build_typed_aoi_map_audits.jsonl'
    with audits_path.open('w') as f:
        for a in audits:
            f.write(json.dumps(a) + '\n')

    print(f'\nType distribution across all entries:', file=sys.stderr)
    for t, n in type_counter.most_common():
        pct = 100 * n / sum(type_counter.values())
        print(f'  {t}: {n:,} ({pct:.1f}%)', file=sys.stderr)
    print(f'\nMatching summary:', file=sys.stderr)
    print(f'  matched HTML+bbox: {n_matched_total:,}', file=sys.stderr)
    print(f'  unmatched bbox (cv detected, html missed): {n_unmatched_bbox_total:,}',
          file=sys.stderr)
    print(f'  unmatched html (html had, cv missed): {n_unmatched_html_total:,}',
          file=sys.stderr)
    print(f'\nHTML rso count − bbox count distribution (Δ):', file=sys.stderr)
    deltas = Counter(a['n_html_rso'] - a['n_bbox_main'] for a in audits)
    for delta in sorted(deltas.keys()):
        print(f'  Δ={delta:+d}: {deltas[delta]:,} trials', file=sys.stderr)
    if errors:
        print(f'\nErrors: {errors:,}', file=sys.stderr)
    print(f'\nWrote {len(files) - errors:,} per-trial JSONs to data/aoi-typed/',
          file=sys.stderr)


if __name__ == '__main__':
    main()
