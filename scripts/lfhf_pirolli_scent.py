"""Content analysis #4 — Pirolli scent-sharpening × LF/HF.

Within a trial, for each newly-visited result position, compute cosine
similarity between that result's embedding and the centroid of
previously-visited results. This is the dynamic form of
information-scent: does the current result match or depart from the
scent model built from prior examples?

Predictions (Pirolli & Card 1999):
  A. similarity ↑ → LF/HF ↓ — redundant results are evaluated cheaply
                              (scent model already covers them)
  B. similarity ↓ → LF/HF ↑ — novel results trigger re-evaluation /
                              model update, carrying cognitive cost

Alternative: NULL at the content level if LF/HF is truly rank-bound
(framework compilation depends on ordinal position, not scent content).
Would reinforce the position-bound story from today's content-crossover
null.

Unit of analysis: (trial, first-visit position, visit-ordinal). Use
pupil-lfhf's forward-pass high-water-mark classifier — same rule as
NB14 K2 segment counting — so the matched LF/HF value at each
(trial, position) is exactly the one NB14 reports.

Outputs:
  scripts/output/lfhf_pirolli_scent/summary.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parent / 'pupil-lfhf' / 'validation'))
from adserp_loader import (  # type: ignore
    get_trial_ids, load_fixations, get_trial_meta, result_band_tops,
    count_results_html, assign_fixation_to_position,
)

SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
OUT_DIR = ROOT / 'scripts/output/lfhf_pirolli_scent'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_lfhf() -> dict[tuple[str, int], float]:
    data = json.load(open(LFHF_JSON))
    out: dict[tuple[str, int], float] = {}
    for tid, trial in data.items():
        for seg in trial['positions']:
            v = seg['lfhf']
            if v is None or not math.isfinite(v):
                continue
            out[(tid, int(seg['pos']))] = float(v)
    return out


def load_result_embeddings() -> dict[str, dict[int, np.ndarray]]:
    serp = json.load(open(SERP_EMBED))
    out: dict[str, dict[int, np.ndarray]] = {}
    for tid, results in serp.items():
        pos_emb: dict[int, np.ndarray] = {}
        for r in results:
            if 'embedding' not in r:
                continue
            pos = int(r.get('position', -1))
            if pos < 0 or pos >= 10:
                continue
            e = np.asarray(r['embedding'], dtype=np.float32)
            norm = float(np.linalg.norm(e))
            if norm < 1e-9:
                continue
            pos_emb[pos] = e / norm
        if pos_emb:
            out[tid] = pos_emb
    return out


def first_visit_order(fixations: list[dict], tid: str, n_results: int
                      ) -> list[int]:
    """Forward-pass first-visit ordering of positions (matches
    pupil-lfhf.identify_forward_pass rule)."""
    doc_h, _, _ = get_trial_meta(tid)
    if doc_h is None:
        return []
    tops = result_band_tops(n_results, doc_h)
    high_water = -1
    visited: list[int] = []
    seen: set[int] = set()
    for fix in fixations:
        pos = assign_fixation_to_position(fix['y'], tops, n_results)
        if pos is None or pos < 0 or pos >= n_results:
            continue
        if pos >= high_water:
            high_water = pos
            if pos not in seen:
                seen.add(pos)
                visited.append(pos)
    return visited


def compute_scent_rows(lfhf: dict[tuple[str, int], float],
                       embeddings: dict[str, dict[int, np.ndarray]],
                       ) -> list[dict]:
    rows: list[dict] = []
    trial_ids = get_trial_ids()
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 250 == 0:
            print(f'  {i+1}/{len(trial_ids)}...', file=sys.stderr)
        pos_emb = embeddings.get(tid)
        if pos_emb is None:
            continue
        n_results = count_results_html(tid)
        if n_results is None:
            n_results = 11
        fix = load_fixations(tid)
        if not fix:
            continue
        order = first_visit_order(fix, tid, n_results)
        if len(order) < 2:
            continue
        pid = tid.split('-')[0]
        for ordinal, pos in enumerate(order):
            if pos not in pos_emb:
                continue
            lfhf_val = lfhf.get((tid, pos))
            if lfhf_val is None:
                continue  # no LF/HF computed at this position
            if ordinal == 0:
                # No prior to compare against; skip similarity but record for coverage
                rows.append({
                    'tid': tid, 'pid': pid, 'pos': pos, 'ordinal': ordinal,
                    'lfhf': lfhf_val, 'scent_cos': float('nan'),
                    'n_prior': 0,
                })
                continue
            prior = [pos_emb[p] for p in order[:ordinal] if p in pos_emb]
            if not prior:
                continue
            centroid = np.mean(prior, axis=0)
            cnorm = float(np.linalg.norm(centroid))
            if cnorm < 1e-9:
                continue
            centroid = centroid / cnorm
            scent = float(pos_emb[pos] @ centroid)
            rows.append({
                'tid': tid, 'pid': pid, 'pos': pos, 'ordinal': ordinal,
                'lfhf': lfhf_val, 'scent_cos': scent,
                'n_prior': len(prior),
            })
    return rows


def main() -> None:
    print('[load] LF/HF per (trial, pos)')
    lfhf = load_lfhf()
    print(f'       {len(lfhf):,} valid LF/HF observations')
    print('[load] result embeddings')
    embeddings = load_result_embeddings()
    print(f'       {len(embeddings):,} trials with embeddings')

    print('[compute] forward-pass visit order + scent cosines')
    rows = compute_scent_rows(lfhf, embeddings)
    n_with_scent = sum(1 for r in rows if r['ordinal'] >= 1)
    print(f'[compute] {len(rows):,} matched (trial, pos, ordinal) rows '
          f'({n_with_scent:,} with scent cosine)')

    rows_s = [r for r in rows if r['ordinal'] >= 1 and math.isfinite(r['scent_cos'])]
    scent = np.array([r['scent_cos'] for r in rows_s])
    y = np.array([r['lfhf'] for r in rows_s])
    ordinals = np.array([r['ordinal'] for r in rows_s])
    positions = np.array([r['pos'] for r in rows_s])

    print(f'\n[describe] scent_cos distribution  (N = {len(rows_s):,})')
    print(f'  mean = {scent.mean():.3f}  median = {np.median(scent):.3f}  '
          f'std = {scent.std(ddof=1):.3f}  '
          f'p05 / p95 = {np.percentile(scent, 5):.3f} / {np.percentile(scent, 95):.3f}')

    # Pooled Spearman
    rho_pool, p_pool = spearmanr(scent, y)
    print(f'\n── Pooled Spearman(scent_cos, LF/HF) ──')
    print(f'  ρ = {rho_pool:+.4f}  p = {p_pool:.3g}  N = {len(rows_s):,}')

    # Per-ordinal Spearman
    print('\n── Per visit-ordinal Spearman ──')
    per_ord: dict[int, dict] = {}
    for o in sorted(set(ordinals)):
        mask = ordinals == o
        if mask.sum() < 30:
            continue
        rho, p = spearmanr(scent[mask], y[mask])
        per_ord[o] = {'n': int(mask.sum()), 'rho': float(rho), 'p': float(p)}
        print(f'  ordinal {o}: ρ = {rho:+.3f}  p = {p:.3g}  N = {mask.sum()}')

    # Per-position Spearman
    print('\n── Per-position Spearman ──')
    per_pos: dict[int, dict] = {}
    for p in sorted(set(positions)):
        mask = positions == p
        if mask.sum() < 30:
            continue
        rho, pv = spearmanr(scent[mask], y[mask])
        per_pos[int(p)] = {'n': int(mask.sum()), 'rho': float(rho), 'p': float(pv)}
        print(f'  P{p}: ρ = {rho:+.3f}  p = {pv:.3g}  N = {mask.sum()}')

    # Partial Spearman controlling for ordinal AND position (rank-residualized)
    def partial_rank_spearman(x, y, z_list):
        from scipy.stats import rankdata
        rx = rankdata(x).astype(float)
        ry = rankdata(y).astype(float)
        Z = np.column_stack([rankdata(z).astype(float) for z in z_list])
        Z = np.column_stack([np.ones(len(x)), Z])
        # Residualize rx and ry on Z via least-squares
        bx, *_ = np.linalg.lstsq(Z, rx, rcond=None)
        by, *_ = np.linalg.lstsq(Z, ry, rcond=None)
        rx_r = rx - Z @ bx
        ry_r = ry - Z @ by
        if rx_r.std() == 0 or ry_r.std() == 0:
            return float('nan'), float('nan')
        rho = float(np.corrcoef(rx_r, ry_r)[0, 1])
        n = len(x)
        if abs(rho) >= 1 or n < 5:
            return rho, 0.0
        t = rho * math.sqrt((n - 4) / max(1 - rho ** 2, 1e-12))
        from scipy.stats import t as tdist
        p = float(2 * (1 - tdist.cdf(abs(t), df=n - 4)))
        return rho, p

    rho_p_ord, p_p_ord = partial_rank_spearman(scent, y, [ordinals])
    rho_p_both, p_p_both = partial_rank_spearman(scent, y, [ordinals, positions])
    print('\n── Partial Spearman (rank-residualized) ──')
    print(f'  scent × LF/HF | ordinal:        ρ = {rho_p_ord:+.4f}  p = {p_p_ord:.3g}')
    print(f'  scent × LF/HF | ordinal, pos:   ρ = {rho_p_both:+.4f}  p = {p_p_both:.3g}')

    # Bonferroni across 3 main tests + per-ordinal + per-position
    n_tests = 3 + len(per_ord) + len(per_pos)
    alpha = 0.05 / n_tests
    print(f'\n── Bonferroni α = {alpha:.4f} ({n_tests} tests) ──')
    survivors = []
    if p_pool < alpha:
        survivors.append(('pooled', rho_pool, p_pool))
    if p_p_ord < alpha:
        survivors.append(('partial | ordinal', rho_p_ord, p_p_ord))
    if p_p_both < alpha:
        survivors.append(('partial | ordinal+pos', rho_p_both, p_p_both))
    for o, d in per_ord.items():
        if d['p'] < alpha:
            survivors.append((f'ordinal={o}', d['rho'], d['p']))
    for p, d in per_pos.items():
        if d['p'] < alpha:
            survivors.append((f'pos={p}', d['rho'], d['p']))
    if survivors:
        print('  SURVIVORS:')
        for (label, rho, p) in survivors:
            print(f'    {label}: ρ = {rho:+.4f}  p = {p:.3g}')
    else:
        print('  No test survives Bonferroni. Null.')

    (OUT_DIR / 'summary.json').write_text(json.dumps({
        'n_rows_total': len(rows),
        'n_rows_with_scent': len(rows_s),
        'scent_stats': {
            'mean': float(scent.mean()),
            'median': float(np.median(scent)),
            'std': float(scent.std(ddof=1)),
            'p05': float(np.percentile(scent, 5)),
            'p95': float(np.percentile(scent, 95)),
        },
        'pooled_spearman': {'rho': float(rho_pool), 'p': float(p_pool), 'n': len(rows_s)},
        'partial_given_ordinal': {'rho': float(rho_p_ord), 'p': float(p_p_ord)},
        'partial_given_ordinal_and_pos': {'rho': float(rho_p_both), 'p': float(p_p_both)},
        'per_ordinal': {str(o): d for o, d in per_ord.items()},
        'per_position': {str(p): d for p, d in per_pos.items()},
        'bonferroni_alpha': alpha,
        'bonferroni_survivors': [
            {'label': l, 'rho': r, 'p': p} for (l, r, p) in survivors
        ],
    }, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
