"""Embed SERP result titles + snippets using mxbai-embed-large (llama.cpp server).

Produces: AdSERP/data/serp-embeddings.json
  {trial_id: [{position, title, snippet, text, embedding: [1024 floats]}, ...]}

Requires: llama-server running on port 8890 with mxbai-embed-large.
  llama-server --model ~/.cache/llama-models/mxbai-embed-large-v1-f16.gguf \
    --port 8890 --embedding --ctx-size 512 -ngl 99
"""

import os
import json
import re
import time
import urllib.request
from pathlib import Path

SERP_DIR = os.path.join(os.path.dirname(__file__), '..', 'AdSERP', 'data', 'serps')
OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'AdSERP', 'data', 'serp-embeddings.json')
EMBED_URL = 'http://localhost:8890/v1/embeddings'

# ── SERP parsing (copied from serp_priming.ipynb) ─────────────────────────

def extract_serp_results(html_path):
    """Extract ordered list of results from a Google SERP HTML file."""
    from html.parser import HTMLParser

    class SimpleHTMLExtractor(HTMLParser):
        """Lightweight parser — avoids BeautifulSoup dependency for a script."""
        def __init__(self):
            super().__init__()
            self.in_h3 = False
            self.h3_text = ''
            self.results = []
            self.current_texts = []
            self.depth = 0

        def handle_starttag(self, tag, attrs):
            if tag == 'h3':
                self.in_h3 = True
                self.h3_text = ''

        def handle_endtag(self, tag):
            if tag == 'h3' and self.in_h3:
                self.in_h3 = False
                if self.h3_text.strip():
                    self.results.append({'title': self.h3_text.strip(), 'snippet': ''})

        def handle_data(self, data):
            if self.in_h3:
                self.h3_text += data

    # Use BeautifulSoup if available, else fall back to simple parser
    try:
        from bs4 import BeautifulSoup
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        results = []
        rso = soup.find(id='rso') or soup

        for i, h3 in enumerate(rso.find_all('h3')):
            title = h3.get_text(strip=True)
            # Walk up to find container, then extract snippet text
            container = h3.parent
            for _ in range(5):
                if container and container.parent:
                    container = container.parent
                    if container.get('class') and any('g' in c for c in container.get('class', [])):
                        break

            # Snippet: all text in the container minus the title
            all_text = container.get_text(' ', strip=True) if container else ''
            snippet = all_text.replace(title, '', 1).strip()
            # Truncate long snippets
            snippet = snippet[:500] if len(snippet) > 500 else snippet

            results.append({
                'position': i,
                'title': title,
                'snippet': snippet,
            })

        return results
    except ImportError:
        # Fallback: minimal HTML parser
        parser = SimpleHTMLExtractor()
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            parser.feed(f.read())
        for i, r in enumerate(parser.results):
            r['position'] = i
        return parser.results


# ── Embedding ──────────────────────────────────────────────────────────────

def embed_texts(texts, batch_size=32):
    """Embed a list of texts via the llama.cpp server. Returns list of 1024-dim vectors."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        payload = json.dumps({'input': batch, 'model': 'mxbai-embed-large'}).encode()
        req = urllib.request.Request(EMBED_URL, data=payload,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for item in data['data']:
            embeddings.append(item['embedding'])
    return embeddings


def main():
    serp_files = sorted(Path(SERP_DIR).glob('*.html'))
    print(f'SERP HTML files: {len(serp_files)}')

    all_data = {}
    texts_to_embed = []
    text_keys = []  # (trial_id, position) for each text

    # Phase 1: Parse all SERPs
    print('Parsing SERP HTML...')
    for fp in serp_files:
        trial_id = fp.stem
        results = extract_serp_results(str(fp))
        if not results:
            continue

        trial_results = []
        for r in results[:10]:  # Cap at 10 results
            text = f"{r['title']}. {r['snippet']}"
            trial_results.append({
                'position': r['position'],
                'title': r['title'],
                'snippet': r['snippet'][:200],
                'text': text[:400],  # Truncate for embedding context window
            })
            texts_to_embed.append(text[:400])
            text_keys.append((trial_id, r['position']))

        all_data[trial_id] = trial_results

    print(f'Parsed {len(all_data)} trials, {len(texts_to_embed)} result texts to embed')

    # Phase 2: Embed all texts
    print('Embedding...')
    t0 = time.time()
    embeddings = embed_texts(texts_to_embed)
    elapsed = time.time() - t0
    print(f'Embedded {len(embeddings)} texts in {elapsed:.1f}s ({len(embeddings)/elapsed:.0f} texts/s)')

    # Phase 3: Attach embeddings to results
    for emb, (trial_id, pos) in zip(embeddings, text_keys):
        for r in all_data[trial_id]:
            if r['position'] == pos:
                r['embedding'] = emb
                break

    # Phase 4: Save
    with open(OUTPUT, 'w') as f:
        json.dump(all_data, f)
    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f'Saved to {OUTPUT} ({size_mb:.1f} MB)')


if __name__ == '__main__':
    main()
