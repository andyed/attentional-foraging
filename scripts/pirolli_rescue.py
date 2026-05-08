"""Pirolli rescue — content-stratified dissociation test for NB18 K14.

NB18 K14 (pooled): items the gaze later regresses to had *lower* first-pass
RIPA2 (0.0777 vs 0.0809, p=0.0106 one-sided). Headline interpretation in
the canonical claims doc was "rejects Pirolli scent-following, supports
encoding-completion."

That rejection is unsafe under the snippet-content × position confound
(TTR ρ = −0.253 with rank, p = 10⁻⁸⁹). Pirolli's prediction is
*conditional on scent strength*: high-scent items should be revisited
**with elevated arousal** (scent draws attention back); low-scent items
that are revisited fit the encoding-completion story (under-processed
first time). Pooling collapses the two into a net direction.

This script tertile-splits first-pass fixations by *dynamic scent*
(cosine similarity of the current result's embedding to the centroid of
prior-visited results' embeddings — same definition as
lfhf_pirolli_scent.py) and runs the K14 will-regress vs no-regress
comparison **within each tertile** for both RIPA2 and LF/HF.

Predictions:
  - High-scent tertile, will-regress > no-regress on RIPA2 → Pirolli rescued
  - Low-scent tertile, will-regress < no-regress on RIPA2 → encoding-completion preserved
  - Both → dissociation (publishable as CIKM main figure)
  - Neither → confound-controlled rejection (NB18 conclusion strengthened)

Inputs:
  - AdSERP/data/encoding-vs-retrieval.json   (per-fixation: pos, ripa2, lfhf, will_regress, duration_ms)
  - AdSERP/data/serp-embeddings.json         (per-(trial, pos) embeddings)

Output:
  - scripts/output/pirolli_rescue/summary.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

ROOT = Path(__file__).resolve().parent.parent
ENC_RET = ROOT / 'AdSERP/data/encoding-vs-retrieval.json'
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
OUT_DIR = ROOT / 'scripts/output/pirolli_rescue'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_embeddings() -> dict[str, dict[int, np.ndarray]]:
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
            e = np.asarray(r['embedding'], dtype=np.float32)
            n = float(np.linalg.norm(e))
            if n < 1e-9:
                continue
            pos_emb[pos] = e / n
        if pos_emb:
            out[tid] = pos_emb
    return out


def compute_rows() -> list[dict]:
    """One row per first-pass fixation with scent_cos attached."""
    enc = json.load(open(ENC_RET))
    embeddings = load_embeddings()

    rows: list[dict] = []
    skipped_no_emb = 0
    skipped_first = 0
    for tid, trial in enc.items():
        pos_emb = embeddings.get(tid)
        if pos_emb is None:
            skipped_no_emb += 1
            continue
        first_pass = trial.get('first_pass') or []
        visited: list[int] = []
        for fix in first_pass:
            pos = int(fix['pos'])
            ordinal = len(visited)
            # Compute scent only if we have embeddings for current AND prior
            scent = float('nan')
            if ordinal >= 1 and pos in pos_emb:
                priors = [pos_emb[p] for p in visited if p in pos_emb]
                if priors:
                    centroid = np.mean(priors, axis=0)
                    cnorm = float(np.linalg.norm(centroid))
                    if cnorm >= 1e-9:
                        centroid = centroid / cnorm
                        scent = float(pos_emb[pos] @ centroid)
            if pos not in visited:
                visited.append(pos)

            if ordinal == 0:
                skipped_first += 1

            rows.append({
                'tid': tid,
                'pid': tid.split('-')[0],
                'pos': pos,
                'ordinal': ordinal,
                'ripa2': fix.get('ripa2'),
                'lfhf': fix.get('lfhf'),
                'will_regress': bool(fix.get('will_regress', False)),
                'duration_ms': float(fix.get('duration_ms') or 0.0),
                'scent_cos': scent,
            })
    print(f'  loaded {len(enc):,} trials, {skipped_no_emb:,} skipped (no embeddings)',
          file=sys.stderr)
    print(f'  {len(rows):,} first-pass fixations total ({skipped_first:,} ordinal=0 skipped from scent)',
          file=sys.stderr)
    return rows


def mw_compare(group_a: np.ndarray, group_b: np.ndarray, label_a: str, label_b: str
               ) -> dict:
    """Two-sided + one-sided Mann-Whitney."""
    if len(group_a) < 5 or len(group_b) < 5:
        return {'na': len(group_a), 'nb': len(group_b), 'note': 'insufficient n'}
    stat, p_two = mannwhitneyu(group_a, group_b, alternative='two-sided')
    _, p_a_lt_b = mannwhitneyu(group_a, group_b, alternative='less')
    _, p_a_gt_b = mannwhitneyu(group_a, group_b, alternative='greater')
    return {
        f'median_{label_a}': float(np.median(group_a)),
        f'median_{label_b}': float(np.median(group_b)),
        'na': int(len(group_a)),
        'nb': int(len(group_b)),
        'p_two_sided': float(p_two),
        f'p_{label_a}_lt_{label_b}': float(p_a_lt_b),
        f'p_{label_a}_gt_{label_b}': float(p_a_gt_b),
    }


def main() -> None:
    print('[load] encoding-vs-retrieval + embeddings', file=sys.stderr)
    rows = compute_rows()

    # Filter to rows with computable scent (ordinal >= 1 + finite scent) and finite RIPA2 or LF/HF
    have_scent = [r for r in rows if r['ordinal'] >= 1 and math.isfinite(r['scent_cos'])]
    print(f'  {len(have_scent):,} rows with computable scent', file=sys.stderr)

    # === Replicate NB18 K14 pooled comparison (no scent stratification) ===
    print('\n=== Pooled NB18 K14 replication (sanity) ===', file=sys.stderr)
    for metric in ('ripa2', 'lfhf'):
        finite = [r for r in rows if r[metric] is not None and math.isfinite(r[metric])]
        wr = np.array([r[metric] for r in finite if r['will_regress']])
        nr = np.array([r[metric] for r in finite if not r['will_regress']])
        if len(wr) < 5 or len(nr) < 5:
            print(f'  {metric}: insufficient n ({len(wr)} / {len(nr)})')
            continue
        res = mw_compare(wr, nr, 'wr', 'nr')
        direction = 'wr < nr' if res['median_wr'] < res['median_nr'] else 'wr > nr'
        print(f'  {metric:6s}: med_wr={res["median_wr"]:.4f}  med_nr={res["median_nr"]:.4f}  '
              f'N={res["na"]:,}/{res["nb"]:,}  p_two={res["p_two_sided"]:.3g}  '
              f'p_wr_lt_nr={res["p_wr_lt_nr"]:.3g}  ({direction})')

    # === Tertile split by scent ===
    scents = np.array([r['scent_cos'] for r in have_scent])
    t1, t2 = np.quantile(scents, [1/3, 2/3])
    print(f'\n=== Scent tertile cutpoints ===  low<{t1:.4f} mid<{t2:.4f} high≥{t2:.4f}',
          file=sys.stderr)

    def tertile(s: float) -> str:
        return 'low' if s < t1 else ('mid' if s < t2 else 'high')

    by_tertile: dict[str, list[dict]] = {'low': [], 'mid': [], 'high': []}
    for r in have_scent:
        by_tertile[tertile(r['scent_cos'])].append(r)

    summary: dict = {
        'cohort': {
            'n_trials': len(set(r['tid'] for r in rows)),
            'n_pids': len(set(r['pid'] for r in rows)),
            'n_first_pass_fixations': len(rows),
            'n_with_scent': len(have_scent),
        },
        'tertile_cutpoints': {'low_max': float(t1), 'mid_max': float(t2)},
        'tertiles': {},
        'pooled_replication': {},
    }

    # Pooled (with scent) replication for direct K14 cross-check
    for metric in ('ripa2', 'lfhf'):
        finite = [r for r in have_scent if r[metric] is not None and math.isfinite(r[metric])]
        wr = np.array([r[metric] for r in finite if r['will_regress']])
        nr = np.array([r[metric] for r in finite if not r['will_regress']])
        summary['pooled_replication'][metric] = mw_compare(wr, nr, 'wr', 'nr')

    print('\n=== Tertile-stratified will-regress vs no-regress ===')
    print(f'{"metric":>6s} {"tertile":>6s} {"med_wr":>10s} {"med_nr":>10s} {"N_wr":>6s} {"N_nr":>6s} {"p_two":>10s} {"direction":>14s}')
    for tname in ('low', 'mid', 'high'):
        bucket = by_tertile[tname]
        summary['tertiles'][tname] = {
            'n_total': len(bucket),
            'metrics': {},
        }
        for metric in ('ripa2', 'lfhf'):
            finite = [r for r in bucket if r[metric] is not None and math.isfinite(r[metric])]
            wr = np.array([r[metric] for r in finite if r['will_regress']])
            nr = np.array([r[metric] for r in finite if not r['will_regress']])
            res = mw_compare(wr, nr, 'wr', 'nr') if len(wr) >= 5 and len(nr) >= 5 else \
                  {'na': len(wr), 'nb': len(nr), 'note': 'insufficient n'}
            summary['tertiles'][tname]['metrics'][metric] = res
            if 'note' not in res:
                direction = 'wr < nr' if res['median_wr'] < res['median_nr'] else 'wr > nr'
                if res['median_wr'] > res['median_nr'] and metric == 'ripa2':
                    direction += '  ← Pirolli'
                if res['median_wr'] < res['median_nr'] and metric == 'ripa2':
                    direction += '  ← encoding'
                print(f'{metric:>6s} {tname:>6s} {res["median_wr"]:>10.4f} {res["median_nr"]:>10.4f} '
                      f'{res["na"]:>6d} {res["nb"]:>6d} {res["p_two_sided"]:>10.3g}  {direction}')
            else:
                print(f'{metric:>6s} {tname:>6s} insufficient n ({len(wr)}/{len(nr)})')

    # Bonferroni across 6 tests (3 tertiles × 2 metrics)
    n_tests = 6
    alpha = 0.05 / n_tests
    print(f'\n--- Bonferroni α = {alpha:.4f} (6 tests = 3 tertiles × 2 metrics) ---')
    survivors = []
    for tname in ('low', 'mid', 'high'):
        for metric in ('ripa2', 'lfhf'):
            res = summary['tertiles'][tname]['metrics'].get(metric, {})
            p = res.get('p_two_sided')
            if p is not None and p < alpha:
                survivors.append((metric, tname, res['median_wr'], res['median_nr'], p))
    if survivors:
        for s in survivors:
            print(f'  SURVIVES: {s[0]} @ {s[1]} — wr={s[2]:.4f} nr={s[3]:.4f} p={s[4]:.3g}')
    else:
        print('  No tertile×metric pair survives Bonferroni.')
    summary['bonferroni'] = {
        'alpha': alpha, 'n_tests': n_tests,
        'survivors': [
            {'metric': s[0], 'tertile': s[1], 'median_wr': s[2], 'median_nr': s[3], 'p': s[4]}
            for s in survivors
        ],
    }

    # Pirolli vs encoding direction summary
    print('\n--- Direction summary (RIPA2) ---')
    for tname in ('low', 'mid', 'high'):
        m = summary['tertiles'][tname]['metrics'].get('ripa2', {})
        if 'note' in m:
            continue
        sign = '+' if m['median_wr'] > m['median_nr'] else '−'
        diff = m['median_wr'] - m['median_nr']
        verdict = 'Pirolli (wr > nr)' if diff > 0 else 'encoding-completion (wr < nr)'
        print(f'  scent {tname:4s}: Δ_wr-nr = {diff:+.5f}  ({verdict})  p={m["p_two_sided"]:.3g}')

    out = OUT_DIR / 'summary.json'
    out.write_text(json.dumps(summary, indent=2))
    print(f'\n[out] {out.relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
