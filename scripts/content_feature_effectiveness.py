"""Content-feature positive-control — do our 5 content features work on
*anything* on AdSERP, or are they ineffective regressors?

Motivated by the question: if the LF/HF content-crossover null (2026-04-19)
is really "features don't work at all," that null is uninformative. Test
the same five features on two outcomes where each feature has a clear
prior reason to predict:

  query_cosine       → was_clicked   (Google ranks by relevance → relevance
                                       predicts clicks)
  centroid_novelty   → was_clicked   (novel vs redundant — weak prior,
                                       but clicks should tilt toward
                                       distinctive results)
  token_count        → total_dwell_ms (more text to read → longer dwell)
  char_count         → total_dwell_ms (same mechanism)
  ttr                → total_dwell_ms (lexical diversity → processing cost)

If a feature hits on its prior-supported outcome but misses LF/HF, the
LF/HF null is a real finding (feature works, load doesn't move).
If a feature misses everywhere, our null is uninformative for that
feature.

Inputs:
  AdSERP/data/serp-embeddings.json
  AdSERP/data/query-embeddings.json
  AdSERP/data/cursor-approach-features.json  (was_clicked, total_dwell_ms)

Output:
  scripts/output/content_feature_effectiveness/summary.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
QUERY_EMBED = ROOT / 'AdSERP/data/query-embeddings.json'
CURSOR_FEATS = ROOT / 'AdSERP/data/cursor-approach-features.json'
OUT_DIR = ROOT / 'scripts/output/content_feature_effectiveness'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = ['token_count', 'char_count', 'ttr', 'query_cosine', 'centroid_novelty']


def compute_content_features() -> dict[tuple[str, int], dict[str, float]]:
    serp = json.load(open(SERP_EMBED))
    qemb = json.load(open(QUERY_EMBED))
    out: dict[tuple[str, int], dict[str, float]] = {}
    for tid, results in serp.items():
        embs = [np.asarray(r['embedding'], dtype=np.float32)
                for r in results if 'embedding' in r]
        if not embs:
            continue
        centroid = np.mean(embs, axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-9)
        qv = None
        q = qemb.get(tid)
        if isinstance(q, dict) and 'embedding' in q:
            qv = np.asarray(q['embedding'], dtype=np.float32)
            qv = qv / max(float(np.linalg.norm(qv)), 1e-9)

        for r in results:
            if 'embedding' not in r:
                continue
            pos = int(r.get('position', -1))
            if pos < 0 or pos >= 10:
                continue
            title = r.get('title') or ''
            snippet = r.get('snippet') or ''
            ts = (title + ' ' + snippet).strip()
            tokens = ts.split()
            tok_n = len(tokens)
            emb = np.asarray(r['embedding'], dtype=np.float32)
            emb_n = emb / max(float(np.linalg.norm(emb)), 1e-9)
            out[(tid, pos)] = {
                'token_count':      float(tok_n),
                'char_count':       float(len(ts)),
                'ttr':              float(len({t.lower() for t in tokens}) / tok_n) if tok_n else 0.0,
                'query_cosine':     float(emb_n @ qv) if qv is not None else 0.0,
                'centroid_novelty': float(1.0 - (emb_n @ centroid)),
            }
    return out


def main() -> None:
    print('[load] content features from embeddings')
    content = compute_content_features()
    print(f'       {len(content):,} (trial, pos) pairs')

    print('[load] cursor-approach features (was_clicked, total_dwell_ms)')
    cursor = json.load(open(CURSOR_FEATS))
    print(f'       {len(cursor):,} records')

    # Join
    rows = []
    for r in cursor:
        key = (r['trial_id'], r['position'])
        cf = content.get(key)
        if cf is None:
            continue
        rows.append({
            **cf,
            'was_clicked': int(r.get('was_clicked', 0)),
            'total_dwell_ms': float(r.get('total_dwell_ms', 0) or 0),
            'n_fixations': int(r.get('n_fixations', 0) or 0),
        })
    print(f'[join] {len(rows):,} records joined')

    arr = {k: np.array([r[k] for r in rows]) for k in
           FEATURES + ['was_clicked', 'total_dwell_ms', 'n_fixations']}

    summary: dict = {'n_records': len(rows), 'features': {}}

    print('\n── Feature × was_clicked (Spearman, Mann-Whitney) ──')
    for feat in FEATURES:
        rho, p = spearmanr(arr[feat], arr['was_clicked'])
        f_click = arr[feat][arr['was_clicked'] == 1]
        f_unclick = arr[feat][arr['was_clicked'] == 0]
        try:
            u, pmw = mannwhitneyu(f_click, f_unclick, alternative='two-sided')
        except ValueError:
            u, pmw = float('nan'), float('nan')
        mean_c = float(np.mean(f_click)) if len(f_click) else float('nan')
        mean_u = float(np.mean(f_unclick)) if len(f_unclick) else float('nan')
        # Cohen's d
        s = float(np.std(np.concatenate([f_click, f_unclick]), ddof=1))
        d = (mean_c - mean_u) / s if s > 0 else float('nan')
        summary['features'].setdefault(feat, {})['vs_was_clicked'] = {
            'spearman_rho': float(rho), 'spearman_p': float(p),
            'mean_clicked': mean_c, 'mean_unclicked': mean_u,
            'cohens_d': float(d), 'mann_whitney_p': float(pmw),
            'n_clicked': int(len(f_click)), 'n_unclicked': int(len(f_unclick)),
        }
        print(f'  {feat:>18s}: ρ={rho:+.4f} (p={p:.2g})  '
              f'd={d:+.3f}  mean clk={mean_c:.3f} vs unclk={mean_u:.3f}  MW-p={pmw:.2g}')

    print('\n── Feature × total_dwell_ms (Spearman) ──')
    mask_dwell = arr['total_dwell_ms'] > 0  # positions actually fixated
    for feat in FEATURES:
        rho, p = spearmanr(arr[feat][mask_dwell], arr['total_dwell_ms'][mask_dwell])
        summary['features'].setdefault(feat, {})['vs_total_dwell'] = {
            'spearman_rho': float(rho), 'spearman_p': float(p),
            'n': int(mask_dwell.sum()),
        }
        print(f'  {feat:>18s}: ρ={rho:+.4f} (p={p:.2g})  N={mask_dwell.sum()}')

    print('\n── Feature × n_fixations (Spearman) ──')
    for feat in FEATURES:
        rho, p = spearmanr(arr[feat], arr['n_fixations'])
        summary['features'].setdefault(feat, {})['vs_n_fixations'] = {
            'spearman_rho': float(rho), 'spearman_p': float(p),
        }
        print(f'  {feat:>18s}: ρ={rho:+.4f} (p={p:.2g})')

    # Verdict
    print('\n── Per-feature verdict ──')
    alpha = 0.001  # conservative
    verdict = {}
    for feat in FEATURES:
        f = summary['features'][feat]
        hits = []
        if f['vs_was_clicked']['spearman_p'] < alpha:
            hits.append(f'click (ρ={f["vs_was_clicked"]["spearman_rho"]:+.3f}, '
                        f'p={f["vs_was_clicked"]["spearman_p"]:.2g})')
        if f['vs_total_dwell']['spearman_p'] < alpha:
            hits.append(f'dwell (ρ={f["vs_total_dwell"]["spearman_rho"]:+.3f}, '
                        f'p={f["vs_total_dwell"]["spearman_p"]:.2g})')
        if f['vs_n_fixations']['spearman_p'] < alpha:
            hits.append(f'n_fix (ρ={f["vs_n_fixations"]["spearman_rho"]:+.3f}, '
                        f'p={f["vs_n_fixations"]["spearman_p"]:.2g})')
        status = 'EFFECTIVE' if hits else 'INERT'
        verdict[feat] = {'status': status, 'hits': hits}
        print(f'  {feat:>18s}: {status}  ' + (' / '.join(hits) if hits else 'no outcome reached α=0.001'))

    summary['verdict'] = verdict
    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
