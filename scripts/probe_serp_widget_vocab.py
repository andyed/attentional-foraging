"""Probe SERP HTML across the corpus to enumerate widget signatures.

Stage 0 of the typed-AOI pipeline. Surveys all 2,776 HTML files for
distinctive structural patterns that identify widget types.

Output: scripts/output/aoi-typed/widget_vocab.{json, md}

Run:
  .venv/bin/python scripts/probe_serp_widget_vocab.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
SERPS = ROOT / 'AdSERP/data/serps'
OUT = ROOT / 'scripts/output/aoi-typed'
OUT.mkdir(parents=True, exist_ok=True)

# Pattern probes (kept as substrings or regex; we'll refine in Phase 1)
TEXT_MARKERS = [
    'People also ask', 'Related searches', 'Featured snippet',
    'Top stories', 'Local results', 'Image results',
    'Video results', 'Knowledge panel', 'Sponsored',
    'About this result',
]

CLASS_MARKERS = [
    'kp-wholepage', 'kp-blk', 'g-section-with-header',
    'related-question-pair', 'wWOJcd', 'ULSxyf',
    'related-search-pair',
]

DATA_ATTR_MARKERS = [
    'data-attrid', 'data-async-context', 'data-hveid', 'data-ved',
    'data-feature-id', 'data-q-source',
]


def main():
    files = sorted(SERPS.glob('*.html'))
    print(f'[probe] scanning {len(files):,} HTML files', file=sys.stderr)

    text_counter = Counter()
    class_counter = Counter()
    data_attr_kv_counter = Counter()
    data_attrid_values = Counter()

    # Card-detection: how many top-level result-like divs per page (rough)
    card_counts = []

    # Per-trial: which markers showed up
    marker_per_trial = defaultdict(list)

    n_processed = 0
    for fp in files:
        if (n_processed + 1) % 500 == 0:
            print(f'  {n_processed+1}/{len(files)}', file=sys.stderr)
        n_processed += 1

        html = fp.read_text(encoding='utf-8', errors='ignore')

        # Text markers
        for marker in TEXT_MARKERS:
            if marker in html:
                text_counter[marker] += 1
                marker_per_trial[fp.stem].append(f'TEXT:{marker}')

        # Class markers
        for marker in CLASS_MARKERS:
            if marker in html:
                class_counter[marker] += 1
                marker_per_trial[fp.stem].append(f'CLASS:{marker}')

        # data-attrid values (these are stable across Google A/B drift)
        for m in re.finditer(r'data-attrid="([^"]+)"', html):
            data_attrid_values[m.group(1)] += 1

        # Distinctive data-attr keys
        for marker in DATA_ATTR_MARKERS:
            if marker in html:
                data_attr_kv_counter[marker] += 1

        # Card count via rough heuristic — `<div class="g">` is the legacy
        # Google organic-result wrapper; modern uses `<div class="MjjYud">` or
        # similar. We'll iterate on this in Phase 1.
        soup = BeautifulSoup(html, 'html.parser')
        legacy_g = len(soup.find_all('div', class_='g'))
        # New-style card: `MjjYud` is one of the modern wrappers
        modern = len(soup.find_all('div', class_='MjjYud'))
        card_counts.append({
            'tid': fp.stem,
            'legacy_g_divs': legacy_g,
            'modern_MjjYud_divs': modern,
        })

    # Output
    summary = {
        'n_trials_scanned': n_processed,
        'text_markers': dict(text_counter.most_common()),
        'class_markers': dict(class_counter.most_common()),
        'data_attr_keys': dict(data_attr_kv_counter.most_common()),
        'top_data_attrid_values': dict(data_attrid_values.most_common(50)),
        'card_count_summary': {
            'legacy_g_div_counts': dict(Counter(c['legacy_g_divs'] for c in card_counts).most_common()),
            'modern_MjjYud_div_counts': dict(Counter(c['modern_MjjYud_divs'] for c in card_counts).most_common()),
        },
    }
    (OUT / 'widget_vocab.json').write_text(json.dumps(summary, indent=2))

    # Markdown
    lines = [
        '# SERP HTML widget vocabulary — corpus probe\n',
        '_Generated 2026-05-03 by `scripts/probe_serp_widget_vocab.py`._\n',
        f'**N trials scanned**: {n_processed:,}\n',
        '## Text markers (substring presence)\n',
        '| Marker | n trials | % of corpus |',
        '|---|---|---|',
    ]
    for marker, n in text_counter.most_common():
        pct = 100 * n / n_processed
        lines.append(f'| `{marker}` | {n:,} | {pct:.1f}% |')

    lines.extend([
        '\n## Class-name markers\n',
        '| Class | n trials | % of corpus |',
        '|---|---|---|',
    ])
    for marker, n in class_counter.most_common():
        pct = 100 * n / n_processed
        lines.append(f'| `{marker}` | {n:,} | {pct:.1f}% |')

    lines.extend([
        '\n## Top data-attrid values (these are usually stable across Google A/B drift)\n',
        '| data-attrid | n trials |',
        '|---|---|',
    ])
    for marker, n in data_attrid_values.most_common(30):
        lines.append(f'| `{marker}` | {n:,} |')

    lines.extend([
        '\n## Card-count distributions\n',
        '### Legacy `<div class="g">` count per page\n',
        '| count | n trials |',
        '|---|---|',
    ])
    for c, n in sorted(Counter(cc['legacy_g_divs'] for cc in card_counts).items()):
        lines.append(f'| {c} | {n:,} |')

    lines.extend([
        '\n### Modern `<div class="MjjYud">` count per page\n',
        '| count | n trials |',
        '|---|---|',
    ])
    for c, n in sorted(Counter(cc['modern_MjjYud_divs'] for cc in card_counts).items()):
        lines.append(f'| {c} | {n:,} |')

    (OUT / 'widget_vocab.md').write_text('\n'.join(lines))

    print(f'\nText markers (top 5):', file=sys.stderr)
    for m, n in text_counter.most_common(5):
        print(f'  {m}: {n:,}', file=sys.stderr)
    print(f'\nClass markers:', file=sys.stderr)
    for m, n in class_counter.most_common():
        print(f'  {m}: {n:,}', file=sys.stderr)
    print(f'\nTop 10 data-attrid values:', file=sys.stderr)
    for v, n in data_attrid_values.most_common(10):
        print(f'  {v}: {n:,}', file=sys.stderr)
    print(f'\nWrote {(OUT / "widget_vocab.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
