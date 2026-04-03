"""Compute SERP difficulty measures beyond bag-of-words Jaccard.

Two measures:
1. Relevance spread: variance of query-result cosine similarities.
   Low spread = all results equidistant from query = hard to pick a winner.
2. Distinctive feature density: mean TF-IDF-weighted unique tokens per result.
   Low density = results share vocabulary = hard to discriminate.

Outputs JSON: {trial_id: {relevance_spread, distinctive_density, jaccard, ...}}

Requires: embedding server on localhost:8890, SERP HTML files.
"""

import os, re, json, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup
import numpy as np
import requests

DATA_DIR = 'AdSERP/data'
SERP_DIR = os.path.join(DATA_DIR, 'serps')
METADATA_DIR = os.path.join(DATA_DIR, 'trial-metadata')
EMBED_URL = 'http://localhost:8890/v1/embeddings'
OUTPUT_PATH = 'AdSERP/data/serp-difficulty-measures.json'

STOPWORDS = set('the a an and or but in on at to for of is it this that was were be been '
                'being have has had do does did will would shall should may might can could '
                'with from by as are not no its my your his her their our its '
                'between both during each few how more most other some such through until '
                'where which while who whom why into over under buy'.split())

def tokenize(text):
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

def extract_serp_results(html_path):
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    results = []
    rso = soup.find(id='rso') or soup
    for i, h3 in enumerate(rso.find_all('h3')):
        title = h3.get_text(strip=True)
        container = h3.parent
        for _ in range(5):
            if container and container.parent:
                container = container.parent
                if container.name == 'div' and container.get('class') and any('g' in c for c in container.get('class', [])):
                    break
        snippets = []
        if container:
            for el in container.find_all(['span', 'div'], recursive=True):
                t = el.get_text(strip=True)
                if t and t != title and len(t) > 20:
                    snippets.append(t)
        full_text = title + ' ' + ' '.join(snippets[:3])
        results.append({
            'position': i,
            'title': title,
            'text': full_text[:500],  # cap for embedding
            'tokens': tokenize(full_text),
            'token_set': set(tokenize(full_text)),
        })
    return results

def get_query(trial_id):
    path = os.path.join(METADATA_DIR, f'{trial_id}.xml')
    try:
        tree = ET.parse(path)
        return tree.find('.//query').text or ''
    except:
        # Fall back: extract from trial ID slug
        return ''

def batch_embed(texts, batch_size=100):
    """Embed texts in batches via local llama.cpp server."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = requests.post(EMBED_URL, json={"input": batch, "model": "mxbai-embed-large"})
        data = resp.json()
        for item in data['data']:
            all_embeddings.append(np.array(item['embedding']))
    return all_embeddings

def cosine_sim(a, b):
    dot = np.dot(a, b)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def compute_jaccard(results):
    pairwise = []
    for i in range(len(results)):
        for j in range(i+1, len(results)):
            union = results[i]['token_set'] | results[j]['token_set']
            if union:
                pairwise.append(len(results[i]['token_set'] & results[j]['token_set']) / len(union))
    return float(np.mean(pairwise)) if pairwise else 0.0

def compute_distinctive_density(results):
    """TF-IDF weighted unique-token density per result.

    For each result, compute sum of TF-IDF scores for tokens that appear
    in only that result (document frequency = 1 on this SERP).
    Normalize by total token count per result.
    """
    n_docs = len(results)
    if n_docs < 2:
        return 0.0

    # Document frequency: how many results contain each token
    doc_freq = Counter()
    for r in results:
        for t in r['token_set']:
            doc_freq[t] += 1

    densities = []
    for r in results:
        tokens = r['tokens']
        if not tokens:
            continue
        # TF: count within this result
        tf = Counter(tokens)
        # Sum TF-IDF for tokens unique to this result (df=1)
        unique_score = 0.0
        total_score = 0.0
        for token, count in tf.items():
            tfidf = (count / len(tokens)) * math.log(n_docs / doc_freq[token])
            total_score += tfidf
            if doc_freq[token] == 1:
                unique_score += tfidf

        # Density = fraction of TF-IDF mass that's distinctive
        if total_score > 0:
            densities.append(unique_score / total_score)

    return float(np.mean(densities)) if densities else 0.0


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Ensure cwd is project root
    if not os.path.exists('AdSERP') and os.path.exists('../AdSERP'):
        os.chdir('..')

    serp_files = sorted(Path(SERP_DIR).glob('*.html'))
    print(f'SERP files: {len(serp_files)}')

    # Phase 1: Extract all text
    print('Extracting SERP text...')
    serp_data = {}  # tid -> {query, results}
    for html_path in serp_files:
        tid = html_path.stem
        try:
            results = extract_serp_results(html_path)
            if len(results) >= 3:
                query = get_query(tid)
                serp_data[tid] = {'query': query, 'results': results}
        except:
            pass
    print(f'  Extracted: {len(serp_data)} SERPs')

    # Phase 2: Compute distinctive feature density (no embeddings needed)
    print('Computing distinctive feature density...')
    density_scores = {}
    for tid, data in serp_data.items():
        density_scores[tid] = compute_distinctive_density(data['results'])

    d_arr = np.array(list(density_scores.values()))
    print(f'  Density: mean={d_arr.mean():.3f}, median={np.median(d_arr):.3f}, std={d_arr.std():.3f}')

    # Phase 3: Batch embed queries + results for relevance spread
    print('Embedding queries and results...')

    # Build text list: query first, then all results per SERP
    embed_texts = []
    embed_index = []  # (tid, 'query'|position_idx)

    for tid, data in serp_data.items():
        # Query text
        q = data['query'] if data['query'] else data['results'][0]['title']
        embed_texts.append(q)
        embed_index.append((tid, 'query'))

        for r in data['results']:
            embed_texts.append(r['text'])
            embed_index.append((tid, r['position']))

    print(f'  Total texts to embed: {len(embed_texts)}')
    embeddings = batch_embed(embed_texts, batch_size=200)
    print(f'  Embedded: {len(embeddings)}')

    # Map back to per-trial structure
    trial_embeddings = {}  # tid -> {query_emb, result_embs: []}
    for (tid, idx), emb in zip(embed_index, embeddings):
        if tid not in trial_embeddings:
            trial_embeddings[tid] = {'query_emb': None, 'result_embs': []}
        if idx == 'query':
            trial_embeddings[tid]['query_emb'] = emb
        else:
            trial_embeddings[tid]['result_embs'].append(emb)

    # Phase 4: Compute relevance spread
    print('Computing relevance spread...')
    spread_scores = {}
    for tid, embs in trial_embeddings.items():
        if embs['query_emb'] is None or len(embs['result_embs']) < 3:
            continue
        sims = [cosine_sim(embs['query_emb'], r) for r in embs['result_embs']]
        spread_scores[tid] = float(np.std(sims))

    s_arr = np.array(list(spread_scores.values()))
    print(f'  Spread: mean={s_arr.mean():.4f}, median={np.median(s_arr):.4f}, std={s_arr.std():.4f}')

    # Phase 5: Assemble output
    print('Assembling output...')
    output = {}
    for tid in serp_data:
        jaccard = compute_jaccard(serp_data[tid]['results'])
        output[tid] = {
            'jaccard': jaccard,
            'distinctive_density': density_scores.get(tid, None),
            'relevance_spread': spread_scores.get(tid, None),
            'n_results': len(serp_data[tid]['results']),
            'query': serp_data[tid]['query'] or serp_data[tid]['results'][0]['title'],
        }

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=1)

    print(f'\nWrote {len(output)} trials to {OUTPUT_PATH}')

    # Correlations between measures
    tids = [t for t in output if output[t]['relevance_spread'] is not None]
    j = np.array([output[t]['jaccard'] for t in tids])
    d = np.array([output[t]['distinctive_density'] for t in tids])
    s = np.array([output[t]['relevance_spread'] for t in tids])

    from scipy import stats
    print(f'\nCorrelations between measures (N={len(tids)}):')
    r, p = stats.spearmanr(j, d)
    print(f'  Jaccard vs Density:  rho={r:.3f}, p={p:.2e}')
    r, p = stats.spearmanr(j, s)
    print(f'  Jaccard vs Spread:   rho={r:.3f}, p={p:.2e}')
    r, p = stats.spearmanr(d, s)
    print(f'  Density vs Spread:   rho={r:.3f}, p={p:.2e}')
