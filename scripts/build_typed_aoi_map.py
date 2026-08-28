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
GEOMETRY = ROOT / 'data/aoi-html-geometry'
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


# ── Y-aware card<->bbox alignment ─────────────────────────────────────
# Replaces k-th<->k-th index matching, whose labels shift below any
# card/bbox count mismatch (docs/local-pack-aoi-shift.md §Residual).
# Cards carry rendered page-space geometry (data/aoi-html-geometry/,
# Chromium at the dataset's 1280px capture width); render y drifts
# progressively vs the dataset screenshots, so alignment runs twice:
# DP with a coarse scale guess, then a Theil-Sen linear refit
# (dataset_y ~ a + s * render_y) on the matched pairs, then DP again.

_GAP_BBOX = 100.0    # skip an unmatched bbox (splits, footer artifacts)
_GAP_CARD = 130.0    # skip an unmatched card (CV missed it)
_H_WEIGHT = 0.25


def _dp_align(bboxes, cards, fit, cap):
    """Monotonic Needleman-Wunsch over y-sorted bboxes and cards.

    fit = (a, s) mapping render y -> dataset y. Returns list of
    (bbox_idx, card_idx) matched pairs.
    """
    a, s = fit
    n, m = len(bboxes), len(cards)
    INF = float('inf')
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            base = dp[i][j]
            if i < n and base + _GAP_BBOX < dp[i + 1][j]:
                dp[i + 1][j] = base + _GAP_BBOX
                back[i + 1][j] = (i, j, 'skip_bbox')
            if j < m and base + _GAP_CARD < dp[i][j + 1]:
                dp[i][j + 1] = base + _GAP_CARD
                back[i][j + 1] = (i, j, 'skip_card')
            if i < n and j < m:
                b, c = bboxes[i], cards[j]
                cy = a + s * c['geo_y']
                cost = min(abs(b['y'] - cy), cap)
                cost += _H_WEIGHT * min(abs(b['height'] - s * c['geo_h']), 200)
                if base + cost < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = base + cost
                    back[i + 1][j + 1] = (i, j, 'match')
    pairs = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, op = back[i][j]
        if op == 'match':
            pairs.append((pi, pj))
        i, j = pi, pj
    pairs.reverse()
    return pairs, dp[n][m]


def _theil_sen(pairs_xy):
    """Robust linear fit y ~ a + s*x from >= 2 (x, y) pairs."""
    slopes = []
    for k in range(len(pairs_xy)):
        for l in range(k + 1, len(pairs_xy)):
            (x1, y1), (x2, y2) = pairs_xy[k], pairs_xy[l]
            if x2 != x1:
                slopes.append((y2 - y1) / (x2 - x1))
    if not slopes:
        return None
    slopes.sort()
    s = slopes[len(slopes) // 2]
    if not (0.7 <= s <= 1.3):    # degenerate fit — reject
        return None
    intercepts = sorted(y - s * x for x, y in pairs_xy)
    a = intercepts[len(intercepts) // 2]
    return (a, s)


def align_cards_to_bboxes(bboxes, cards):
    """Two-pass y-aware alignment. Returns (pairs, fit, mean_residual).

    Pass 1 tries several candidate linear maps and keeps the lowest-cost
    DP alignment. Candidates are head-anchored at a few plausible scales
    (Chromium re-render inflates layout ~5-15% vs the dataset capture, so
    the true slope sits near 0.9); a span-matched candidate covers trials
    where the head anchor itself is a mismatch. Span-matching alone is a
    trap: tail bboxes with no cards (footer artifacts) stretch the span
    and lock the fit into a shifted local minimum.
    Pass 2 refits render->dataset with Theil-Sen on the matched pairs and
    re-aligns; the refit is kept only if it doesn't worsen DP cost.
    """
    ys_b = [b['y'] for b in bboxes]
    ys_c = [c['geo_y'] for c in cards]

    # Head-, tail-, and median-anchored candidates at each scale. Head
    # alone is not enough: top-of-page widgets are the region that
    # renders most pathologically (a maps block collapsing 367->140px, a
    # local pack expanding 93->553px — p047-b5-t2), and an anchor inside
    # the corruption locks the DP into a one-slot-shifted compromise fit.
    # Tail/median anchors sit in the stable organic run.
    med_b = ys_b[len(ys_b) // 2]
    med_c = ys_c[len(ys_c) // 2]
    candidates = []
    for s0 in (0.85, 0.9, 0.95, 1.0):
        candidates.append((ys_b[0] - s0 * ys_c[0], s0))
        candidates.append((ys_b[-1] - s0 * ys_c[-1], s0))
        candidates.append((med_b - s0 * med_c, s0))
    if len(bboxes) >= 2 and len(cards) >= 2 and max(ys_c) > min(ys_c):
        s_span = (max(ys_b) - min(ys_b)) / (max(ys_c) - min(ys_c))
        s_span = min(max(s_span, 0.7), 1.3)
        candidates.append((min(ys_b) - s_span * min(ys_c), s_span))

    best = None
    for fit0 in candidates:
        pairs0, cost0 = _dp_align(bboxes, cards, fit0, cap=400.0)
        if best is None or cost0 < best[2]:
            best = (pairs0, fit0, cost0)
    pairs, fit, cost = best

    if len(pairs) >= 2:
        refit = _theil_sen([(cards[j]['geo_y'], bboxes[i]['y'])
                            for i, j in pairs])
        if refit is not None:
            pairs2, cost2 = _dp_align(bboxes, cards, refit, cap=200.0)
            # cap differs between passes; compare on the tighter cap
            _, cost1 = _dp_align(bboxes, cards, fit, cap=200.0)
            if cost2 <= cost1:
                fit, pairs = refit, pairs2
    a, s = fit
    residuals = [abs(bboxes[i]['y'] - (a + s * cards[j]['geo_y']))
                 for i, j in pairs]

    # Outlier-pair filter. The DP's cost cap makes one terrible match
    # (capped ~200-250) cheaper than skipping both sides (230), so a
    # trial with otherwise sub-pixel alignment can carry a single forced
    # wrong pair with a 100-700px residual — a mislabel. Drop pairs whose
    # residual is extreme relative to the trial's own median: uniform
    # drift (nonlinear reflow, order-preserved, labels right) passes, a
    # lone spike doesn't. Freed bboxes/cards fall through to segment
    # absorption / span rescue / honest unmatched.
    n_dropped = 0
    if residuals:
        med = sorted(residuals)[len(residuals) // 2]
        cutoff = max(100.0, 3 * med + 40)
        kept = [(p, r) for p, r in zip(pairs, residuals) if r <= cutoff]
        n_dropped = len(pairs) - len(kept)
        if n_dropped:
            pairs = [p for p, _ in kept]
            residuals = [r for _, r in kept]

    mean_res = sum(residuals) / len(residuals) if residuals else None
    # Height mismatch catches the failure y-residuals cannot: an evenly
    # spaced organic run is shift-periodic, so a one-slot-shifted lattice
    # has self-consistent (low) y-residuals — but it pairs cards with the
    # wrong heights (p047-b5-t2: a 497px local pack on an 82px bbox).
    h_mis = [abs(bboxes[i]['height'] - s * cards[j]['geo_h'])
             for i, j in pairs]
    mean_h_mis = sum(h_mis) / len(h_mis) if h_mis else None
    return pairs, fit, mean_res, n_dropped, mean_h_mis


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

    # ── Match non-ad bboxes to HTML cards ──
    # Preferred: y-aware DP alignment against rendered card geometry.
    # Fallback (no geometry file / degenerate): legacy DOM-order index match.
    non_ad_bboxes = [main_bboxes[i] for i in non_ad_bbox_indices]

    geo_path = GEOMETRY / f'{tid}.json'
    geo_by_order = {}
    if geo_path.exists():
        for g in json.loads(geo_path.read_text()):
            if g.get('found'):
                geo_by_order[g['order']] = g
    cards_geo = []
    cards_nogeo = []
    cards_offcolumn = []
    for h in html_rso:
        g = geo_by_order.get(h.get('order'))
        if g is not None:
            cards_geo.append({**h, 'geo_y': g['y'], 'geo_h': g['height'],
                              'geo_x': g.get('x', 0)})
        else:
            cards_nogeo.append(h)

    # A card whose rendered x is far from the pack of main-column cards
    # rendered in the RIGHT RAIL in the real browser (html.parser kept it
    # as an #rso child, Chromium re-parents it — e.g. TQc1id...rhstc4
    # knowledge panels). It has no main-column bbox; keep it out of the DP.
    if len(cards_geo) >= 3:
        xs = sorted(c['geo_x'] for c in cards_geo)
        x_med = xs[len(xs) // 2]
        in_col = [c for c in cards_geo if abs(c['geo_x'] - x_med) <= 200]
        cards_offcolumn = [c for c in cards_geo
                           if abs(c['geo_x'] - x_med) > 200]
        cards_geo = in_col

    # Verified geometry is the true visual order; bs4 list order can
    # diverge from it (parser re-parenting), and the DP assumes both
    # sequences are y-monotonic.
    cards_geo.sort(key=lambda c: c['geo_y'])

    alignment_mode = 'index_fallback'
    fit = None
    mean_residual = None
    mean_h_mismatch = None
    n_segments_merged = 0
    n_span_rescued = 0
    n_pairs_dropped = 0
    matched_bbox_idx = {}     # index into non_ad_bboxes -> entry dict
    unmatched_html = []

    if len(cards_geo) >= 2 and non_ad_bboxes:
        # Cards without geometry can't join the DP; parking them as
        # unmatched beats degrading the whole trial to index matching
        # (their bbox, if any, surfaces as unknown_widget).
        for h in cards_nogeo:
            unmatched_html.append({
                'type': h['type'],
                'x': None, 'y': None, 'width': None, 'height': None,
                'html_handle': h['html_handle'],
                'html_signature': h.get('html_signature', ''),
                'heading_text': h.get('heading_text', ''),
                'source': 'html_only+no_geometry',
            })
        for h in cards_offcolumn:
            unmatched_html.append({
                'type': h['type'],
                'x': None, 'y': None, 'width': None, 'height': None,
                'html_handle': h['html_handle'],
                'html_signature': h.get('html_signature', ''),
                'heading_text': h.get('heading_text', ''),
                'source': 'html_rendered_offcolumn',
            })
        alignment_mode = 'y_dp'
        (pairs, fit, mean_residual, n_pairs_dropped,
         mean_h_mismatch) = align_cards_to_bboxes(non_ad_bboxes, cards_geo)
        matched_card_js = {j for _, j in pairs}
        for i, j in pairs:
            b, h = non_ad_bboxes[i], cards_geo[j]
            entry = {
                'type': h['type'],
                'x': b['x'], 'y': b['y'], 'width': b['width'],
                'height': b['height'],
                'html_handle': h['html_handle'],
                'html_signature': h.get('html_signature', ''),
                'heading_text': h.get('heading_text', ''),
                'source': 'html_rso+cv_bbox+y_dp',
                '_card_j': j,
            }
            matched_bbox_idx[i] = entry
            main_entries.append(entry)

        # Absorb unmatched bboxes that fall inside a matched card's rendered
        # span — CV over-segmentation (e.g. a PAA block split into per-row
        # bboxes) becomes one entry spanning the union.
        a_fit, s_fit = fit
        entry_by_j = {e['_card_j']: e for e in main_entries if '_card_j' in e}
        for i, b in enumerate(non_ad_bboxes):
            if i in matched_bbox_idx:
                continue
            b_center = b['y'] + b['height'] / 2
            for j, e in entry_by_j.items():
                c = cards_geo[j]
                top = a_fit + s_fit * c['geo_y'] - 30
                bot = a_fit + s_fit * (c['geo_y'] + c['geo_h']) + 40
                if top <= b_center <= bot:
                    y2 = max(e['y'] + e['height'], b['y'] + b['height'])
                    y1 = min(e['y'], b['y'])
                    # A card cannot own more area than it renders: reject
                    # a merge that would grow the entry past its rendered
                    # height (under drift, span tests over-claim the
                    # neighbor's bbox and shift every label below).
                    if y2 - y1 > 1.4 * s_fit * c['geo_h'] + 40:
                        continue
                    e['y'] = y1
                    e['height'] = y2 - y1
                    if '+merged_segment' not in e['source']:
                        e['source'] += '+merged_segment'
                    matched_bbox_idx[i] = e
                    n_segments_merged += 1
                    break

        # Span rescue: a tall card CV split into several small bboxes (e.g.
        # a 700px+ in-rso local pack chopped into per-business segments)
        # matches none of them 1-1 — DP leaves the card AND the segments
        # unmatched. Let each unmatched card claim the unmatched bboxes
        # whose centers fall in its corrected span, as one union entry.
        for j, c in enumerate(cards_geo):
            if j in matched_card_js:
                continue
            top = a_fit + s_fit * c['geo_y'] - 30
            bot = a_fit + s_fit * (c['geo_y'] + c['geo_h']) + 40
            candidates = [i for i, b in enumerate(non_ad_bboxes)
                          if i not in matched_bbox_idx
                          and top <= b['y'] + b['height'] / 2 <= bot]
            if not candidates:
                continue
            # Same owns-no-more-than-it-renders guard as absorption:
            # claim nearest-to-card-center first, stop before the union
            # outgrows the card's rendered height.
            c_center = a_fit + s_fit * (c['geo_y'] + c['geo_h'] / 2)
            candidates.sort(key=lambda i: abs(
                non_ad_bboxes[i]['y'] + non_ad_bboxes[i]['height'] / 2
                - c_center))
            claimed = []
            h_limit = 1.4 * s_fit * c['geo_h'] + 40
            for i in candidates:
                trial_set = claimed + [i]
                t1 = min(non_ad_bboxes[k]['y'] for k in trial_set)
                t2 = max(non_ad_bboxes[k]['y'] + non_ad_bboxes[k]['height']
                         for k in trial_set)
                if t2 - t1 <= h_limit:
                    claimed = trial_set
            if not claimed:
                continue
            y1 = min(non_ad_bboxes[i]['y'] for i in claimed)
            y2 = max(non_ad_bboxes[i]['y'] + non_ad_bboxes[i]['height']
                     for i in claimed)
            entry = {
                'type': c['type'],
                'x': non_ad_bboxes[claimed[0]]['x'], 'y': y1,
                'width': non_ad_bboxes[claimed[0]]['width'],
                'height': y2 - y1,
                'html_handle': c['html_handle'],
                'html_signature': c.get('html_signature', ''),
                'heading_text': c.get('heading_text', ''),
                'source': 'html_rso+cv_bbox+y_dp+span_rescue',
            }
            main_entries.append(entry)
            for i in claimed:
                matched_bbox_idx[i] = entry
            matched_card_js.add(j)
            n_span_rescued += 1
            n_segments_merged += len(claimed) - 1

        # Remaining unmatched bboxes — no card claims them
        n_unmatched_bbox = 0
        for i, b in enumerate(non_ad_bboxes):
            if i in matched_bbox_idx:
                continue
            main_entries.append({
                'type': 'unknown_widget',
                'x': b['x'], 'y': b['y'], 'width': b['width'],
                'height': b['height'],
                'html_handle': None,
                'html_signature': '',
                'heading_text': '',
                'source': 'cv_bbox_only',
            })
            n_unmatched_bbox += 1

        # Cards the DP left unmatched (CV never bboxed them)
        for j, h in enumerate(cards_geo):
            if j in matched_card_js:
                continue
            unmatched_html.append({
                'type': h['type'],
                'x': None, 'y': None, 'width': None, 'height': None,
                'html_handle': h['html_handle'],
                'html_signature': h.get('html_signature', ''),
                'heading_text': h.get('heading_text', ''),
                'source': 'html_only',
                'y_render': h['geo_y'],
            })
        for e in main_entries:
            e.pop('_card_j', None)
        matched_count = len(pairs)
    else:
        # Legacy DOM-order index matching
        matched_count = min(len(non_ad_bboxes), len(html_rso))
        for k in range(matched_count):
            b = non_ad_bboxes[k]
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
        for k in range(matched_count, len(non_ad_bboxes)):
            b = non_ad_bboxes[k]
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
        'alignment_mode': alignment_mode,
        # Two independent shift signatures: raw y misfit, or high height
        # mismatch WITH nonzero y misfit (a shift-periodic wrong lattice,
        # p047-b5-t2). Height mismatch alone at ~1px y-residual is a
        # correct lattice whose widgets render at divergent heights
        # (verified on p036-b2-t6) — not flagged.
        'alignment_suspect': bool(
            (mean_residual is not None and mean_residual > 30)
            or (mean_h_mismatch is not None and mean_h_mismatch > 60
                and mean_residual is not None and mean_residual > 8)),
        'mean_h_mismatch': (round(mean_h_mismatch, 1)
                            if mean_h_mismatch is not None else None),
        'fit_intercept': round(fit[0], 1) if fit else None,
        'fit_slope': round(fit[1], 4) if fit else None,
        'mean_residual': round(mean_residual, 1) if mean_residual is not None else None,
        'n_segments_merged': n_segments_merged,
        'n_span_rescued': n_span_rescued,
        'n_pairs_dropped': n_pairs_dropped,
        'n_cards_no_geometry': len(cards_nogeo),
        'n_cards_offcolumn': len(cards_offcolumn),
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

    residuals = [a['mean_residual'] for a in audits
                 if a.get('mean_residual') is not None]
    summary = {
        'source_flavor': args.source,
        'organic_bbox_dir': str(ORGANIC_BBOX),
        'out_dir': str(OUT_DIR),
        'n_trials': len(files),
        'n_errors': errors,
        'alignment': {
            'mode_distribution': dict(Counter(
                a['alignment_mode'] for a in audits).most_common()),
            'segments_merged_total': sum(a['n_segments_merged'] for a in audits),
            'cards_no_geometry_total': sum(a['n_cards_no_geometry'] for a in audits),
            'n_alignment_suspect': sum(1 for a in audits
                                       if a.get('alignment_suspect')),
            'mean_residual_px': (sum(residuals) / len(residuals)) if residuals else None,
            'p90_residual_px': (sorted(residuals)[int(0.9 * len(residuals))]
                                if residuals else None),
        },
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
