"""Pirolli rescue v2 — scent = snippet-query similarity (Pirolli-faithful).

v1 (pirolli_rescue.py) used dynamic novelty-to-prior as scent (cosine to
centroid of previously-visited result embeddings). That's a valid
definition but not the most faithful to Pirolli & Card 1999, where scent
is the *per-item perceived query-relevance* read from content cues —
independent of viewing history.

v2 swaps scent → cos(snippet_embedding, query_embedding). Same
tertile-stratified will-regress vs no-regress test; same encoding-vs-
retrieval feature table.

Predictions (faithful Pirolli):
  - High-scent (high snippet-query similarity, "looks relevant"):
    will-regress > no-regress on RIPA2 → scent draws revisits with
    elevated arousal
  - Low-scent: will-regress < no-regress → encoding-completion preserved
  - Both → publication-defining dissociation
  - Neither → operationalization-robust rejection of the Pirolli
    arousal-at-revisit prediction (note: NOT a rejection of broader
    foraging theory)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
ENC_RET = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
QUERY_EMBED = ROOT / 'AdSERP/data/query-embeddings.json'
OUT_DIR = ROOT / 'scripts/output/pirolli_rescue_v2'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize(v: np.ndarray) -> np.ndarray | None:
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return None
    return v / n


def load_query_embeddings() -> dict[str, np.ndarray]:
    q = json.load(open(QUERY_EMBED))
    out: dict[str, np.ndarray] = {}
    for tid, rec in q.items():
        emb = rec.get('embedding')
        if emb is None:
            continue
        v = normalize(np.asarray(emb, dtype=np.float32))
        if v is not None:
            out[tid] = v
    return out


def load_snippet_embeddings() -> dict[str, dict[int, np.ndarray]]:
    serp = json.load(open(SERP_EMBED))
    out: dict[str, dict[int, np.ndarray]] = {}
    for tid, results in serp.items():
        pos_emb: dict[int, np.ndarray] = {}
        for r in results:
            if 'embedding' not in r:
                continue
            pos = int(r.get('position', -1))
            if pos < 0 or pos >= 11:
                continue
            v = normalize(np.asarray(r['embedding'], dtype=np.float32))
            if v is not None:
                pos_emb[pos] = v
        if pos_emb:
            out[tid] = pos_emb
    return out


def compute_rows() -> list[dict]:
    enc = json.load(open(ENC_RET))
    qemb = load_query_embeddings()
    semb = load_snippet_embeddings()
    print(f'  query embeddings: {len(qemb):,} trials', file=sys.stderr)
    print(f'  snippet embeddings: {len(semb):,} trials', file=sys.stderr)

    rows: list[dict] = []
    skipped_q = skipped_s = 0
    for tid, trial in enc.items():
        q = qemb.get(tid)
        if q is None:
            skipped_q += 1
            continue
        pos_emb = semb.get(tid)
        if pos_emb is None:
            skipped_s += 1
            continue
        for fix in trial.get('first_pass') or []:
            pos = int(fix['pos'])
            scent = float('nan')
            if pos in pos_emb:
                scent = float(pos_emb[pos] @ q)
            rows.append({
                'tid': tid,
                'pid': tid.split('-')[0],
                'pos': pos,
                'ripa2': fix.get('ripa2'),
                'lfhf': fix.get('lfhf'),
                'will_regress': bool(fix.get('will_regress', False)),
                'duration_ms': float(fix.get('duration_ms') or 0.0),
                'scent_cos': scent,
            })
    print(f'  {len(enc):,} trials seen; {skipped_q:,} no query, {skipped_s:,} no snippet emb',
          file=sys.stderr)
    print(f'  {len(rows):,} first-pass fixations', file=sys.stderr)
    return rows


def mw_compare(a: np.ndarray, b: np.ndarray, label_a: str, label_b: str) -> dict:
    if len(a) < 5 or len(b) < 5:
        return {'na': len(a), 'nb': len(b), 'note': 'insufficient n'}
    _, p_two = mannwhitneyu(a, b, alternative='two-sided')
    _, p_a_lt_b = mannwhitneyu(a, b, alternative='less')
    _, p_a_gt_b = mannwhitneyu(a, b, alternative='greater')
    return {
        f'median_{label_a}': float(np.median(a)),
        f'median_{label_b}': float(np.median(b)),
        'na': int(len(a)),
        'nb': int(len(b)),
        'p_two_sided': float(p_two),
        f'p_{label_a}_lt_{label_b}': float(p_a_lt_b),
        f'p_{label_a}_gt_{label_b}': float(p_a_gt_b),
    }


def main() -> None:
    rows = compute_rows()
    have_scent = [r for r in rows if math.isfinite(r['scent_cos'])]
    print(f'  {len(have_scent):,} rows with computable scent', file=sys.stderr)

    scents = np.array([r['scent_cos'] for r in have_scent])
    print(f'\n[describe] snippet-query cosine: mean={scents.mean():.3f} '
          f'med={np.median(scents):.3f} sd={scents.std():.3f} '
          f'p05={np.percentile(scents,5):.3f} p95={np.percentile(scents,95):.3f}')

    t1, t2 = np.quantile(scents, [1/3, 2/3])
    print(f'[tertile] cuts: low<{t1:.4f}  mid<{t2:.4f}  high≥{t2:.4f}')

    def tertile(s: float) -> str:
        return 'low' if s < t1 else ('mid' if s < t2 else 'high')

    by_tertile: dict[str, list[dict]] = {'low': [], 'mid': [], 'high': []}
    for r in have_scent:
        by_tertile[tertile(r['scent_cos'])].append(r)

    summary: dict = {
        'cohort': {
            'n_rows_total': len(rows),
            'n_with_scent': len(have_scent),
            'n_trials': len(set(r['tid'] for r in rows)),
            'n_pids': len(set(r['pid'] for r in rows)),
        },
        'tertile_cutpoints': {'low_max': float(t1), 'mid_max': float(t2)},
        'scent_stats': {
            'mean': float(scents.mean()),
            'median': float(np.median(scents)),
            'std': float(scents.std(ddof=1)),
            'p05': float(np.percentile(scents, 5)),
            'p95': float(np.percentile(scents, 95)),
        },
        'pooled': {},
        'tertiles': {},
    }

    # Pooled (with v2 scent) = K14 cross-check
    print('\n=== Pooled (no stratification) ===')
    for metric in ('ripa2', 'lfhf'):
        finite = [r for r in have_scent if r[metric] is not None and math.isfinite(r[metric])]
        wr = np.array([r[metric] for r in finite if r['will_regress']])
        nr = np.array([r[metric] for r in finite if not r['will_regress']])
        res = mw_compare(wr, nr, 'wr', 'nr')
        summary['pooled'][metric] = res
        if 'note' not in res:
            direction = 'wr<nr' if res['median_wr'] < res['median_nr'] else 'wr>nr'
            print(f'  {metric:6s}: med_wr={res["median_wr"]:.4f}  med_nr={res["median_nr"]:.4f}  '
                  f'N={res["na"]}/{res["nb"]}  p_two={res["p_two_sided"]:.3g}  ({direction})')

    print('\n=== Tertile-stratified (snippet-query similarity) ===')
    print(f'{"metric":>6s} {"tertile":>6s} {"med_wr":>10s} {"med_nr":>10s} {"N_wr":>6s} {"N_nr":>6s} {"p_two":>10s} {"verdict":>20s}')
    for tname in ('low', 'mid', 'high'):
        bucket = by_tertile[tname]
        summary['tertiles'][tname] = {'n_total': len(bucket), 'metrics': {}}
        for metric in ('ripa2', 'lfhf'):
            finite = [r for r in bucket if r[metric] is not None and math.isfinite(r[metric])]
            wr = np.array([r[metric] for r in finite if r['will_regress']])
            nr = np.array([r[metric] for r in finite if not r['will_regress']])
            res = mw_compare(wr, nr, 'wr', 'nr')
            summary['tertiles'][tname]['metrics'][metric] = res
            if 'note' in res:
                print(f'{metric:>6s} {tname:>6s} insufficient n ({len(wr)}/{len(nr)})')
                continue
            d = res['median_wr'] - res['median_nr']
            verdict = 'Pirolli (wr>nr)' if d > 0 else 'encoding (wr<nr)'
            print(f'{metric:>6s} {tname:>6s} {res["median_wr"]:>10.4f} {res["median_nr"]:>10.4f} '
                  f'{res["na"]:>6d} {res["nb"]:>6d} {res["p_two_sided"]:>10.3g}  {verdict:>20s}')

    # Bonferroni
    n_tests = 6
    alpha = 0.05 / n_tests
    print(f'\n--- Bonferroni α = {alpha:.4f} (6 tests) ---')
    survivors = []
    for tname in ('low', 'mid', 'high'):
        for metric in ('ripa2', 'lfhf'):
            res = summary['tertiles'][tname]['metrics'].get(metric, {})
            p = res.get('p_two_sided')
            if p is not None and p < alpha:
                survivors.append((metric, tname, res['median_wr'], res['median_nr'], p))
    if survivors:
        for s in survivors:
            print(f'  SURVIVES: {s[0]} @ {s[1]}: wr={s[2]:.4f} nr={s[3]:.4f}  p={s[4]:.3g}')
    else:
        print('  No tertile×metric pair survives Bonferroni.')
    summary['bonferroni'] = {
        'alpha': alpha, 'n_tests': n_tests,
        'survivors': [{'metric': s[0], 'tertile': s[1],
                       'median_wr': s[2], 'median_nr': s[3], 'p': s[4]}
                      for s in survivors],
    }

    print('\n--- v1 vs v2 cross-check (RIPA2 direction by tertile) ---')
    print(f'{"v":3s} {"low Δ":>10s} {"mid Δ":>10s} {"high Δ":>10s}')
    deltas_v2 = []
    for tname in ('low', 'mid', 'high'):
        m = summary['tertiles'][tname]['metrics'].get('ripa2', {})
        if 'note' in m:
            deltas_v2.append('—')
        else:
            deltas_v2.append(f'{m["median_wr"] - m["median_nr"]:+.5f}')
    print(f'v1  -0.00734  -0.00636  -0.00660  (dynamic novelty)')
    print(f'v2  {deltas_v2[0]:>10s}  {deltas_v2[1]:>10s}  {deltas_v2[2]:>10s}  (snippet-query)')

    out = OUT_DIR / 'summary.json'
    out.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {out.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
