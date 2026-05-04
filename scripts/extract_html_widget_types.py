"""Phase 1 — extract HTML widget types per SERP card.

Parses every SERP HTML in AdSERP/data/serps/ and emits a typed
ordered list of cards per trial:

    data/aoi-html-types/<tid>.json
    [
      {"order": 0, "type": "organic", "html_signature": "div.g.tF2Cxc",
       "html_handle": "rso[3]", "heading_text": "Lee's Glass..."},
      {"order": 1, "type": "image_pack", ...},
      ...
    ]

Type taxonomy (per scope-doc 2026-05-03):
    organic | dd_top | native_ad | dd_right | top_places | knowledge_panel
    | paa | related_searches | image_pack | other_widget | chrome

dd_top / native_ad / dd_right are NOT detected here — they live in
AdSERP/data/ad-boundary-data/. The Phase-2 spatial join layers them on top.
This script labels everything else: organic results + non-ad widgets.

Run:
  .venv/bin/python scripts/extract_html_widget_types.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
SERPS = ROOT / 'AdSERP/data/serps'
OUT_DIR = ROOT / 'data/aoi-html-types'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Tags that cannot host a card (skip without typing)
SKIP_TAGS = {'script', 'style', 'noscript', 'span'}

# ── Type detection ────────────────────────────────────────────────────

def _heading_text(div):
    """Return the most prominent heading text in a card, or empty string."""
    h3 = div.find('h3')
    if h3:
        return h3.get_text(strip=True)
    h2 = div.find('h2')
    if h2:
        return h2.get_text(strip=True)
    role_h = div.find(attrs={'role': 'heading'})
    if role_h:
        return role_h.get_text(strip=True)
    return ''


def _classes(div):
    return ' '.join(div.get('class', []) or [])


def _detect_type(div):
    """Return (type_label, signature_str) for a top-level container child div.
    Signature is a short class+role marker for downstream debugging.

    Priority order: heading text > structural markers > class > generic-organic.
    Heading text wins because Google uses the same wrapper class (ULSxyf) for
    PAA, Related searches, image packs, etc. — only the heading distinguishes them.
    """
    classes = _classes(div)
    heading = _heading_text(div)
    heading_lc = heading.lower()
    data_attrid = div.get('data-attrid', '')

    # ── Tier 1: heading-text matches (highest priority) ──
    if heading_lc == 'people also ask':
        return 'paa', f'h="paa" div.{classes[:50]}'
    if heading_lc == 'related searches':
        return 'related_searches', f'h="rs" div.{classes[:50]}'
    if heading_lc == 'featured snippet':
        return 'other_widget', f'featured_snippet div.{classes[:50]}'
    if heading_lc == 'local results':
        return 'top_places', f'h="local" div.{classes[:50]}'
    if heading_lc == 'complementary results':
        return 'knowledge_panel', f'h="comp" div.{classes[:50]}'
    if heading_lc.startswith('top stories') or heading_lc == 'news':
        return 'other_widget', f'news_pack div.{classes[:50]}'
    if heading_lc.startswith('videos for ') or heading_lc.startswith('video '):
        return 'other_widget', f'video_pack div.{classes[:50]}'
    if heading_lc.startswith('images for '):
        return 'image_pack', f'h="imgs" div.{classes[:50]}'

    # ── Tier 2: structural markers ──
    if div.select_one('.related-question-pair') is not None:
        return 'paa', f'has_rqp div.{classes[:50]}'
    if div.select_one('g-map') is not None:
        return 'top_places', f'has_gmap div.{classes[:50]}'

    # ── Tier 3: data-attrid (knowledge-card namespace, stable across drift) ──
    if data_attrid.startswith('kc:/local'):
        return 'top_places', f'div[data-attrid={data_attrid[:30]}]'
    if data_attrid.startswith('kc:/'):
        return 'knowledge_panel', f'div[data-attrid={data_attrid[:30]}]'

    # ── Tier 4: class markers ──
    if 'TQc1id' in classes:
        return 'knowledge_panel', f'TQc1id div.{classes[:50]}'

    # ── Tier 5: image_pack via ULSxyf class without specific heading
    # ULSxyf is a generic widget wrapper — only treat as image_pack when no
    # other heading-driven match has fired.
    if 'ULSxyf' in classes:
        # Check for image-pack-specific descendants
        if div.select_one('img[data-src], img[src*="googleusercontent"]') is not None:
            return 'image_pack', f'ULSxyf+img div.{classes[:50]}'
        # Otherwise — generic widget container; examine inner h3
        return 'other_widget', f'ULSxyf div.{classes[:50]}'

    # ── Tier 6: g-section-with-header descendant (sectioned widget) ──
    if div.select_one('g-section-with-header') is not None:
        return 'other_widget', f'g-section div.{classes[:50]}'

    # ── Tier 7: organic result (class-based) ──
    organic_classes = {'g', 'tF2Cxc', 'hlcw0c'}
    cls_set = set((div.get('class') or []))
    if cls_set & organic_classes:
        return 'organic', f'div.{classes[:50]}'

    # ── Tier 8: organic result (structure-based) ──
    if heading and div.find('a', href=True):
        return 'organic', f'div.{classes[:50] if classes else "(no class)"}'

    # ── Unrecognised: keep for triage ──
    if heading or classes:
        return 'other_widget', f'div.{classes[:50] if classes else "(no class)"}'

    return None, None


def _is_substantive(div):
    """Filter out non-card elements: scripts, styles, empty spans, etc."""
    if div.name in SKIP_TAGS:
        return False
    text = div.get_text(strip=True)
    if not text:
        return False
    return True


ORGANIC_CARD_CLASSES = {'g', 'tF2Cxc', 'hlcw0c', 'MjjYud'}


def _is_main_results_wrapper(div):
    """Detect Google's 'Main results' ULSxyf wrapper that wraps the whole
    #rso block. These wrap multiple organic cards inside; we should descend.
    """
    if 'ULSxyf' not in _classes(div):
        return False
    # Heading text "Main results" is a definitive signal
    h = _heading_text(div).lower()
    if h.startswith('main result'):
        return True
    # Heuristic: count organic-card-class descendants. >2 means it wraps
    # multiple organic cards (a section wrapper, not a single widget).
    organic_descendants = 0
    for cls in ORGANIC_CARD_CLASSES:
        organic_descendants += len(div.find_all('div', class_=cls))
    return organic_descendants > 2


def _find_card_descendants(div):
    """Find card-class descendants (organic + widget). Dedupe nested.
    Returns list of (handle_suffix, descendant) in DOM order."""
    selectors = (
        'div.g',
        'div.tF2Cxc',
        'div.hlcw0c',
        'div.MjjYud',
        'div.ULSxyf',  # widgets inside (image_pack, paa, etc.)
        'div.TQc1id',  # complementary results
    )
    found = []
    seen = set()
    for sel in selectors:
        for d in div.select(sel):
            # Dedupe by element identity
            if id(d) in seen:
                continue
            # Skip if this element is nested inside another already-found
            # element (we want the outermost card, not its nested children)
            ancestor_already_found = False
            for f in found:
                if d in f.descendants:
                    ancestor_already_found = True
                    break
                if f in d.descendants:
                    # The newly-found element is an ancestor of an already-
                    # found element; replace
                    pass
            if not ancestor_already_found:
                found.append(d)
                seen.add(id(d))
    # Also dedupe nested-within-found for the case where a div.ULSxyf
    # contains a div.g — keep only the outer ULSxyf in that case
    dedup = []
    for d in found:
        is_nested = False
        for other in found:
            if other is d:
                continue
            if d in other.descendants:
                is_nested = True
                break
        if not is_nested:
            dedup.append(d)
    # Sort by document order: BeautifulSoup doesn't directly expose this; use
    # a positional approach via .sourceline if available, else just trust the
    # selector order (which roughly matches DOM order for our flat selectors).
    dedup.sort(key=lambda x: getattr(x, 'sourceline', 0) or 0)
    return dedup


def _walk_rso_cards(rso):
    """Yield (container_index, child_div) for substantive cards in #rso.

    If #rso has a 'Main results' wrapper containing many organic cards,
    descend INTO the wrapper and find card descendants there. Otherwise
    iterate direct children.
    """
    direct_children = [c for c in rso.find_all(recursive=False)
                       if _is_substantive(c)]

    wrappers = [c for c in direct_children
                if c.name == 'div' and _is_main_results_wrapper(c)]

    if wrappers:
        all_cards = []
        for w in wrappers:
            # Descend into THIS wrapper to find cards (not at rso level — that
            # would let the dedupe see the wrapper itself and remove its
            # contents)
            inner = _find_card_descendants(w)
            all_cards.extend(inner)
        # Include non-wrapper direct children too (rare)
        for c in direct_children:
            if c not in wrappers:
                all_cards.append(c)
        # Sort by source line for document order
        all_cards.sort(key=lambda x: getattr(x, 'sourceline', 0) or 0)
        for i, c in enumerate(all_cards):
            yield (str(i), c)
        return

    # Standard case: iterate direct children
    for i, child in enumerate(direct_children):
        yield (str(i), child)


def parse_serp(html: str):
    """Return ordered list of typed cards from a SERP HTML.

    Walks #rso (main results) then #botstuff (bottom widgets — Related
    searches lives here). Right-rail KP from #rhs is appended last with no
    scroll-axis position.
    """
    soup = BeautifulSoup(html, 'html.parser')
    cards = []

    # ── #rso: main result column ──
    rso = soup.select_one('#rso')
    if rso is not None:
        for handle_idx, child in _walk_rso_cards(rso):
            type_label, signature = _detect_type(child)
            if type_label is None:
                continue
            cards.append({
                'order': len(cards),
                'type': type_label,
                'html_handle': f'rso[{handle_idx}]',
                'html_signature': signature,
                'heading_text': _heading_text(child)[:120],
                'container': 'rso',
                'container_index': handle_idx,
            })

    # ── #botstuff: bottom-of-page widgets (Related searches lives here) ──
    botstuff = soup.select_one('#botstuff')
    if botstuff is not None:
        # Walk recursively to find every substantive container, but type each
        # only once at its outermost matching wrapper. Approach: find every
        # ULSxyf wrapper inside botstuff (which holds Related searches +
        # potentially other bottom widgets) and type each top-level one.
        for i, ulsxyf in enumerate(botstuff.select('div.ULSxyf')):
            # Skip ULSxyf wrappers that are nested inside another ULSxyf
            ancestor_uls = ulsxyf.find_parent('div', class_='ULSxyf')
            if ancestor_uls is not None:
                continue
            type_label, signature = _detect_type(ulsxyf)
            if type_label is None:
                continue
            cards.append({
                'order': len(cards),
                'type': type_label,
                'html_handle': f'botstuff.ULSxyf[{i}]',
                'html_signature': signature,
                'heading_text': _heading_text(ulsxyf)[:120],
                'container': 'botstuff',
                'container_index': i,
            })

    # ── #rhs: right-rail (knowledge panel column) ──
    rhs = soup.select_one('#rhs')
    if rhs is not None:
        kp = rhs.select_one('[data-attrid^="kc:/"], .kp-blk')
        if kp is not None:
            data_attrid = kp.get('data-attrid', '') if hasattr(kp, 'get') else ''
            kp_type = 'top_places' if data_attrid.startswith('kc:/local') else 'knowledge_panel'
            cards.append({
                'order': len(cards),
                'type': kp_type,
                'html_handle': '#rhs',
                'html_signature': f'rhs.kp[data-attrid={data_attrid[:30]}]',
                'heading_text': _heading_text(rhs)[:120],
                'container': 'rhs',
                'rhs_only': True,
            })

    return cards


# ── Main ──────────────────────────────────────────────────────────────

def main():
    files = sorted(SERPS.glob('*.html'))
    print(f'[extract] {len(files):,} HTML files', file=sys.stderr)

    type_counter = Counter()
    n_cards_per_trial = []
    n_unmatched = 0
    unmatched_signatures = Counter()

    for i, fp in enumerate(files):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(files)}', file=sys.stderr)
        tid = fp.stem
        html = fp.read_text(encoding='utf-8', errors='ignore')
        cards = parse_serp(html)

        # Stats
        n_cards_per_trial.append(len(cards))
        for c in cards:
            type_counter[c['type']] += 1
            if c['type'] == 'other_widget':
                unmatched_signatures[c['html_signature'][:80]] += 1

        # Write per-trial JSON
        out_path = OUT_DIR / f'{tid}.json'
        out_path.write_text(json.dumps(cards, indent=2))

    # Corpus summary
    summary = {
        'n_trials': len(files),
        'n_cards_total': sum(n_cards_per_trial),
        'cards_per_trial': {
            'mean': sum(n_cards_per_trial) / len(n_cards_per_trial),
            'min': min(n_cards_per_trial),
            'max': max(n_cards_per_trial),
        },
        'type_distribution': dict(type_counter.most_common()),
        'unmatched_other_widget_signatures': dict(unmatched_signatures.most_common(30)),
    }

    summary_path = ROOT / 'scripts/output/aoi-typed/extract_html_widget_types_summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f'\nType distribution across {len(files):,} trials:', file=sys.stderr)
    for t, n in type_counter.most_common():
        pct = 100 * n / sum(type_counter.values())
        print(f'  {t}: {n:,} ({pct:.1f}%)', file=sys.stderr)
    print(f'\nCards per trial: mean={summary["cards_per_trial"]["mean"]:.1f}, '
          f'min={summary["cards_per_trial"]["min"]}, '
          f'max={summary["cards_per_trial"]["max"]}', file=sys.stderr)
    print(f'\nTop unmatched other_widget signatures:', file=sys.stderr)
    for sig, n in unmatched_signatures.most_common(15):
        print(f'  ({n:,}) {sig}', file=sys.stderr)
    print(f'\nWrote {len(files):,} per-trial JSONs to data/aoi-html-types/',
          file=sys.stderr)
    print(f'Wrote {summary_path.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
