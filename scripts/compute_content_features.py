"""Per-(trial, position) snippet content features for AdSERP.

Supports `--attribution {absolute, organic}`:
  absolute  — legacy h3-enumerated positions (0..N from SERP HTML),
              ads + organics pooled. Output:
              AdSERP/data/content-features-by-position.json
  organic   — bbox-derived organic-rank positions (post-2026-05-01
              cascade). Each record's `pos` is the organic-rank
              position; content is fetched from the matching h3 via
              data_loader.absolute_to_organic_rank inversion. Output:
              AdSERP/data/content-features-by-position-organic.json

Sources:
  serp-embeddings.json   — per-result title, snippet, text, embedding
                           (h3-keyed by absolute position 0..N)
  query-embeddings.json  — per-trial query string + embedding

Features per (trial, position):
  Lexical / syntactic:
    snippet_tokens         — token count
    snippet_chars          — character count
    snippet_ttr            — type-token ratio (lexical diversity)
    snippet_numerals       — numeral occurrences (regex)
    snippet_has_price      — bool
    title_tokens
    title_chars
    title_ttr

  Query overlap:
    q_overlap_count        — # query tokens (lowercased) in snippet
    q_overlap_jaccard      — |q ∩ s| / |q ∪ s|, lowercased token sets
    q_overlap_in_title     — # query tokens in title

  Semantic:
    q_snippet_cosine       — cosine(query_emb, snippet_emb)
    q_text_cosine          — cosine(query_emb, full text_emb)

Reuses text_features() pattern from lfhf_title_snippet_split.py for
consistency with existing TTR work.

Run:
  .venv/bin/python scripts/compute_content_features.py --attribution organic
  .venv/bin/python scripts/compute_content_features.py --attribution absolute
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))

from data_loader import absolute_to_organic_rank  # noqa: E402

SERP = ROOT / 'AdSERP/data/serp-embeddings.json'
QUERIES = ROOT / 'AdSERP/data/query-embeddings.json'
OUT_ABS = ROOT / 'AdSERP/data/content-features-by-position.json'
OUT_ORG = ROOT / 'AdSERP/data/content-features-by-position-organic.json'

NUM_RE = re.compile(r'\b\d+(?:[.,]\d+)?\b')
PRICE_RE = re.compile(r'\$\d+(?:[.,]\d+)?')
TOKEN_RE = re.compile(r"[a-z0-9]+")


def text_features(prefix: str, text: str) -> dict[str, float]:
    text = (text or '').strip()
    tokens = text.split()
    n = len(tokens)
    return {
        f'{prefix}_tokens':   float(n),
        f'{prefix}_chars':    float(len(text)),
        f'{prefix}_ttr':      float(len({t.lower() for t in tokens}) / n) if n else 0.0,
        f'{prefix}_numerals': float(len(NUM_RE.findall(text))),
        f'{prefix}_has_price': float(len(PRICE_RE.findall(text)) > 0),
    }


def query_overlap(q_tokens: set[str], text: str) -> tuple[int, float]:
    if not text:
        return 0, 0.0
    s_tokens = set(TOKEN_RE.findall(text.lower()))
    if not s_tokens:
        return 0, 0.0
    inter = q_tokens & s_tokens
    uni = q_tokens | s_tokens
    return len(inter), (len(inter) / len(uni) if uni else 0.0)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float((a / na) @ (b / nb))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--attribution', choices=['absolute', 'organic', 'organic_hybrid', 'typed'], default='organic',
                    help='absolute = h3-enumerated positions (legacy); organic = bbox-organic positions '
                         '(post-2026-05-01 cascade; maps via data_loader.absolute_to_organic_rank).')
    args = ap.parse_args()

    out_path = OUT_ORG if args.attribution == 'organic' else OUT_ABS
    print(f'[attribution] {args.attribution} → {out_path.name}', file=sys.stderr)

    print('[load] SERP embeddings', file=sys.stderr)
    serp = json.load(open(SERP))
    print(f'  {len(serp):,} trials', file=sys.stderr)
    print('[load] query embeddings', file=sys.stderr)
    queries = json.load(open(QUERIES))
    print(f'  {len(queries):,} trial-queries', file=sys.stderr)

    out: dict[str, dict] = {}
    n_skipped_q = 0
    n_skipped_no_mapping = 0
    n_results_total = 0

    for i, (tid, results) in enumerate(serp.items()):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(serp)}', file=sys.stderr)

        qrec = queries.get(tid)
        if qrec is None:
            n_skipped_q += 1
            continue
        q_text = qrec.get('query', '') or ''
        q_emb = qrec.get('embedding')
        q_emb_arr = np.asarray(q_emb, dtype=np.float32) if q_emb is not None else None
        q_tokens = set(TOKEN_RE.findall(q_text.lower()))

        # Build absolute → organic rank map for this trial when in organic mode.
        abs_to_org: dict[int, int | None] | None = None
        if args.attribution == 'organic':
            abs_to_org = absolute_to_organic_rank(tid)
            if not abs_to_org:
                n_skipped_no_mapping += 1
                continue

        positions: list[dict] = []
        for r in results:
            abs_pos = r.get('position')
            if abs_pos is None:
                continue

            # Translate position depending on attribution.
            if args.attribution == 'organic':
                org_pos = abs_to_org.get(int(abs_pos)) if abs_to_org else None
                if org_pos is None:
                    # ad-overlapping h3 — content not emitted under organic
                    continue
                emit_pos = int(org_pos)
            else:
                emit_pos = int(abs_pos)

            title = r.get('title', '') or ''
            snippet = r.get('snippet', '') or ''
            text = r.get('text', '') or ''
            r_emb = r.get('embedding')

            feats: dict[str, float | int] = {'pos': emit_pos}
            if args.attribution == 'organic':
                feats['source_h3_pos'] = int(abs_pos)
            feats.update(text_features('snippet', snippet))
            feats.update(text_features('title', title))

            if q_tokens:
                ov_s, jacc_s = query_overlap(q_tokens, snippet)
                ov_t, _ = query_overlap(q_tokens, title)
                feats['q_overlap_count'] = ov_s
                feats['q_overlap_jaccard'] = jacc_s
                feats['q_overlap_in_title'] = ov_t
            else:
                feats['q_overlap_count'] = 0
                feats['q_overlap_jaccard'] = 0.0
                feats['q_overlap_in_title'] = 0

            if q_emb_arr is not None and r_emb is not None:
                r_emb_arr = np.asarray(r_emb, dtype=np.float32)
                feats['q_text_cosine'] = cosine(q_emb_arr, r_emb_arr)
            else:
                feats['q_text_cosine'] = float('nan')

            # snippet-only embedding (text combines title+snippet); no separate
            # snippet-only embedding in serp-embeddings, so we approximate by
            # using r_emb (the 'text' field's embedding) for both.
            feats['q_snippet_cosine'] = feats['q_text_cosine']

            positions.append(feats)
            n_results_total += 1

        # Sort by emit position so consumers can index linearly.
        positions.sort(key=lambda p: p['pos'])
        out[tid] = {'positions': positions}

    print(f'\n  trials with content features: {len(out):,}  '
          f'(skipped {n_skipped_q} no-query, {n_skipped_no_mapping} no-mapping)', file=sys.stderr)
    print(f'  total positions: {n_results_total:,}', file=sys.stderr)

    out_path.write_text(json.dumps(out, indent=2))
    print(f'[out] {out_path.relative_to(ROOT)}', file=sys.stderr)

    # Quick distributional summary
    rows = [p for tr in out.values() for p in tr['positions']]
    keys = ['snippet_tokens', 'snippet_ttr', 'snippet_chars',
            'q_overlap_count', 'q_overlap_jaccard', 'q_text_cosine']
    print(f'\n=== Distributional summary (N = {len(rows):,} positions) ===')
    print(f'{"feature":>20s}  {"min":>8s} {"q25":>8s} {"median":>8s} {"q75":>8s} {"max":>8s}')
    for k in keys:
        v = np.array([r[k] for r in rows if r[k] == r[k]], dtype=float)  # filter NaN
        if len(v) > 0:
            qs = np.percentile(v, [0, 25, 50, 75, 100])
            print(f'{k:>20s}  {qs[0]:>8.3f} {qs[1]:>8.3f} {qs[2]:>8.3f} '
                  f'{qs[3]:>8.3f} {qs[4]:>8.3f}')


if __name__ == '__main__':
    main()
