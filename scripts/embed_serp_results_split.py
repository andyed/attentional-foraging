"""Embed SERP result titles and summaries SEPARATELY using mxbai-embed-large.

Companion to embed_serp_results.py which embeds title + summary combined.
This one produces title-only and summary-only embeddings needed for NB26's
LTR comparison (Peter Dixon-Moses's exact 5-feature spec includes
cos_sim(query, title) and cos_sim(query, summary) as separate features).

Produces: AdSERP/data/serp-embeddings-split.json
  {trial_id: [{position, title, snippet, title_embedding, snippet_embedding}, ...]}

Requires: llama-server running on port 8890 with mxbai-embed-large.
  llama-server --model ~/.cache/llama-models/mxbai-embed-large-v1-f16.gguf \
    --port 8890 --embedding --ctx-size 512 -ngl 99
"""

import os
import json
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

SERP_DIR = Path(__file__).parent.parent / "AdSERP" / "data" / "serps"
OUTPUT = Path(__file__).parent.parent / "AdSERP" / "data" / "serp-embeddings-split.json"
EMBED_URL = "http://localhost:8890/v1/embeddings"


def extract_serp_results(html_path):
    """Extract per-result (title, snippet) from a Google SERP HTML file."""
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    rso = soup.find(id="rso") or soup
    results = []
    for i, h3 in enumerate(rso.find_all("h3")):
        title = h3.get_text(strip=True)
        container = h3.parent
        for _ in range(5):
            if container and container.parent:
                container = container.parent
                if container.get("class") and any("g" in c for c in container.get("class", [])):
                    break
        all_text = container.get_text(" ", strip=True) if container else ""
        snippet = all_text.replace(title, "", 1).strip()
        snippet = snippet[:500]
        results.append({"position": i, "title": title, "snippet": snippet})
    return results


def embed_texts(texts, batch_size=200):
    """Embed a list of texts via the llama.cpp server. Returns list of 1024-dim vectors."""
    out = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = json.dumps({"input": batch, "model": "mxbai-embed-large"}).encode()
        req = urllib.request.Request(
            EMBED_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        for item in data["data"]:
            out.append(item["embedding"])
    return out


def main():
    serp_files = sorted(SERP_DIR.glob("*.html"))
    print(f"SERP HTML files: {len(serp_files)}")

    all_data = {}
    title_texts = []
    snippet_texts = []
    keys = []  # (trial_id, position) — preserved order for re-join

    print("Parsing SERP HTML...")
    for fp in serp_files:
        tid = fp.stem
        results = extract_serp_results(str(fp))
        if not results:
            continue
        all_data[tid] = []
        for r in results[:10]:
            all_data[tid].append(
                {"position": r["position"], "title": r["title"], "snippet": r["snippet"]}
            )
            # cap text length for embedding context window
            title_texts.append((r["title"] or "")[:400] or "(empty title)")
            snippet_texts.append((r["snippet"] or "")[:400] or "(empty snippet)")
            keys.append((tid, r["position"]))

    print(f"parsed {len(all_data)} trials, {len(keys)} (title, snippet) pairs to embed")

    print("\nembedding titles...")
    t0 = time.time()
    title_embs = embed_texts(title_texts)
    print(f"  {len(title_embs)} title embeddings in {time.time() - t0:.1f}s")

    print("\nembedding snippets...")
    t0 = time.time()
    snippet_embs = embed_texts(snippet_texts)
    print(f"  {len(snippet_embs)} snippet embeddings in {time.time() - t0:.1f}s")

    # Re-attach
    for (tid, pos), te, se in zip(keys, title_embs, snippet_embs):
        for r in all_data[tid]:
            if r["position"] == pos:
                r["title_embedding"] = te
                r["snippet_embedding"] = se
                break

    print(f"\nwriting {OUTPUT}...")
    OUTPUT.write_text(json.dumps(all_data))
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"  {size_mb:.1f} MB")
    print(f"\ndone: {len(all_data)} trials × 2 embeddings (title, snippet) cached")


if __name__ == "__main__":
    main()
