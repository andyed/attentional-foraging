"""LF/HF × content-feature crossover — does semantic novelty modulate cognitive load?

Gap audit (2026-04-19): NB25 / NB27 / NB29 content residualization targeted
click prediction and viewport dwell. NB14 Butterworth LF/HF (cognitive load)
was never crossed against per-result content features. This script fills
that gap.

Hypotheses:
  H1 (semantic load)     — LF/HF correlates with per-result content features
                           beyond the position-bound K10/K3 gradient. A
                           positive extends cognitive-load measurement from
                           structural position to item-level semantics.
  H0 (position-bound)    — LF/HF is position-bound (framework compilation
                           sharpens by rank), and per-result content adds
                           nothing. Consistent with NB29 viewport-bands null.

Design:
  - Inner-join per (trial, position) on LF/HF and content features
  - Pooled Spearman(LF/HF, feature)
  - Per-position Spearman(LF/HF, feature) at each of P0..P9
  - Partial correlation controlling for position (rank-based residuals)
  - Mixed-effects-lite: fixed-effect participant dummies + position + feature
    via numpy (no statsmodels dependency), report standardized beta on feature
  - Multiple-testing note: 5 features × 3 tests → Bonferroni α = 0.05/15 ≈ 0.0033

Inputs:
  AdSERP/data/serp-embeddings.json
  AdSERP/data/query-embeddings.json
  ../pupil-lfhf/validation/butterworth-lfhf-by-position.json

Outputs:
  scripts/output/lfhf_content_crossover/summary.json
  scripts/output/lfhf_content_crossover/per_position.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
QUERY_EMBED = ROOT / 'AdSERP/data/query-embeddings.json'
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
OUT_DIR = ROOT / 'scripts/output/lfhf_content_crossover'
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = ['token_count', 'char_count', 'ttr', 'query_cosine', 'centroid_novelty']
POS_RANGE = list(range(0, 10))  # content features stop at position 9 (see NB29)


# ── Data loading ──────────────────────────────────────────────────────────

def load_lfhf() -> dict[tuple[str, int], float]:
    """Return {(trial_id, pos): lfhf}. Filters null / non-finite."""
    data = json.load(open(LFHF_JSON))
    out: dict[tuple[str, int], float] = {}
    for tid, trial in data.items():
        for seg in trial['positions']:
            v = seg['lfhf']
            if v is None or not math.isfinite(v):
                continue
            out[(tid, int(seg['pos']))] = float(v)
    return out


def compute_content_features() -> dict[tuple[str, int], dict[str, float]]:
    """Recompute per-(trial, pos) content features from embeddings — mirrors
    NB29 _build_nb29_content_residualization.py logic exactly."""
    print('[content] loading SERP + query embeddings…')
    serp = json.load(open(SERP_EMBED))
    qemb = json.load(open(QUERY_EMBED))
    print(f'         SERP: {len(serp):,} trials  ·  Query: {len(qemb):,} trials')

    def qvec(entry) -> np.ndarray | None:
        if isinstance(entry, list):
            return np.asarray(entry, dtype=np.float32)
        if isinstance(entry, dict) and 'embedding' in entry:
            return np.asarray(entry['embedding'], dtype=np.float32)
        return None

    out: dict[tuple[str, int], dict[str, float]] = {}
    for tid, results in serp.items():
        embs = [np.asarray(r['embedding'], dtype=np.float32)
                for r in results if 'embedding' in r]
        if not embs:
            continue
        centroid = np.mean(embs, axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-9)

        qv = qvec(qemb.get(tid))
        if qv is not None:
            qv = qv / max(float(np.linalg.norm(qv)), 1e-9)

        for r in results:
            if 'embedding' not in r:
                continue
            pos = int(r.get('position', -1))
            if pos not in POS_RANGE:
                continue
            title = r.get('title') or ''
            snippet = r.get('snippet') or ''
            text_s = (title + ' ' + snippet).strip()
            tokens = text_s.split()
            tok_n = len(tokens)
            out[(tid, pos)] = {
                'token_count':     float(tok_n),
                'char_count':      float(len(text_s)),
                'ttr':             float(len({t.lower() for t in tokens}) / tok_n) if tok_n else 0.0,
                'query_cosine':    float(np.asarray(r['embedding'], dtype=np.float32) @ qv
                                         / max(float(np.linalg.norm(r['embedding'])), 1e-9))
                                    if qv is not None else 0.0,
                'centroid_novelty':float(1.0 - (
                    np.asarray(r['embedding'], dtype=np.float32) @ centroid
                    / max(float(np.linalg.norm(r['embedding'])), 1e-9))),
            }
    print(f'[content] features for {len(out):,} (trial, pos) pairs')
    return out


# ── Stats helpers ─────────────────────────────────────────────────────────

def partial_spearman(x: np.ndarray, y: np.ndarray, z: np.ndarray
                     ) -> tuple[float, float]:
    """Partial Spearman ρ(x, y | z) via ranks-residualized correlation."""
    from scipy.stats import rankdata
    rx = rankdata(x); ry = rankdata(y); rz = rankdata(z)
    # Residualize rx, ry on rz (simple OLS on ranks)
    def resid(r: np.ndarray, zr: np.ndarray) -> np.ndarray:
        zc = zr - zr.mean()
        denom = float((zc * zc).sum())
        if denom == 0:
            return r - r.mean()
        beta = float(((r - r.mean()) * zc).sum() / denom)
        return r - (zr.mean() + beta * (zr - zr.mean()))
    rxr = resid(rx, rz)
    ryr = resid(ry, rz)
    # Pearson on residualized ranks — equivalent to the standard partial
    if rxr.std() == 0 or ryr.std() == 0:
        return float('nan'), float('nan')
    rho = float(np.corrcoef(rxr, ryr)[0, 1])
    # Approximate p-value for the partial correlation
    n = len(x)
    if abs(rho) >= 1.0 or n < 4:
        return rho, 0.0
    t = rho * math.sqrt((n - 3) / max(1.0 - rho * rho, 1e-12))
    from scipy.stats import t as tdist
    p = float(2 * (1 - tdist.cdf(abs(t), df=n - 3)))
    return rho, p


def fe_regression(lfhf: np.ndarray, feat: np.ndarray, pos: np.ndarray,
                  pid_idx: np.ndarray) -> dict:
    """Fixed-effects OLS: standardize y + feat; regressors = feat + pos-dummies + participant-dummies.

    Returns {beta_feat, se_feat, t_feat, p_feat, r2}.
    """
    from scipy.stats import t as tdist
    n = len(lfhf)
    # Standardize y and feat for a comparable beta
    y = (lfhf - lfhf.mean()) / max(lfhf.std(ddof=1), 1e-9)
    x = (feat - feat.mean()) / max(feat.std(ddof=1), 1e-9)

    # Build design: [1, x, pos-dummies (pos ≥ 1), participant-dummies (pid ≥ 1)]
    pos_vals = np.unique(pos)
    part_vals = np.unique(pid_idx)
    X_cols = [np.ones(n), x]
    for pv in pos_vals[1:]:  # drop first as baseline
        X_cols.append((pos == pv).astype(float))
    for pv in part_vals[1:]:
        X_cols.append((pid_idx == pv).astype(float))
    X = np.column_stack(X_cols)

    # Ridge-regularized pinv for stability at high dummy count
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coef
    resid = y - y_hat
    dof = n - X.shape[1]
    if dof <= 0:
        return {'beta_feat': float('nan'), 'se_feat': float('nan'),
                't_feat': float('nan'), 'p_feat': float('nan'), 'r2': float('nan')}
    mse = float((resid @ resid) / dof)
    try:
        cov = mse * np.linalg.pinv(X.T @ X)
    except np.linalg.LinAlgError:
        cov = mse * np.linalg.pinv(X.T @ X, rcond=1e-6)
    beta = float(coef[1])
    se = float(math.sqrt(max(cov[1, 1], 1e-20)))
    t_val = beta / se if se > 0 else float('nan')
    p_val = float(2 * (1 - tdist.cdf(abs(t_val), df=dof))) if math.isfinite(t_val) else float('nan')
    ss_tot = float(((y - y.mean()) ** 2).sum())
    ss_res = float((resid @ resid))
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    return {'beta_feat': beta, 'se_feat': se, 't_feat': t_val,
            'p_feat': p_val, 'r2': r2, 'dof': dof, 'n': n}


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    print('[load] LF/HF per (trial, pos)')
    lfhf = load_lfhf()
    print(f'       {len(lfhf):,} valid LF/HF observations')

    content = compute_content_features()

    # Inner join
    rows: list[dict] = []
    for (tid, pos), v in lfhf.items():
        if pos not in POS_RANGE:
            continue
        cf = content.get((tid, pos))
        if cf is None:
            continue
        rows.append({
            'tid': tid, 'pid': tid.split('-')[0], 'pos': pos, 'lfhf': v, **cf,
        })
    print(f'[join] {len(rows):,} inner-joined records  '
          f'({len({r["tid"] for r in rows})} trials, '
          f'{len({r["pid"] for r in rows})} participants)')

    lfhf_arr = np.array([r['lfhf'] for r in rows])
    pos_arr = np.array([r['pos'] for r in rows])
    pids = sorted({r['pid'] for r in rows})
    pid_idx = np.array([pids.index(r['pid']) for r in rows])

    summary: dict = {
        'n_records': len(rows),
        'n_trials':  len({r['tid'] for r in rows}),
        'n_participants': len(pids),
        'alpha_bonferroni': 0.05 / (len(FEATURES) * 3),
        'features': {},
    }
    per_position: dict[str, dict] = {}

    for feat in FEATURES:
        f_arr = np.array([r[feat] for r in rows])
        # Pooled Spearman
        rho_pool, p_pool = spearmanr(f_arr, lfhf_arr)
        # Partial Spearman controlling for position
        rho_part, p_part = partial_spearman(f_arr, lfhf_arr, pos_arr.astype(float))
        # Mixed-effects-lite
        fe = fe_regression(lfhf_arr, f_arr, pos_arr, pid_idx)

        # Per-position breakdown
        pp: dict[int, dict] = {}
        for p in POS_RANGE:
            mask = pos_arr == p
            if mask.sum() < 30:
                continue
            rho_p, pval_p = spearmanr(f_arr[mask], lfhf_arr[mask])
            pp[p] = {'n': int(mask.sum()), 'rho': float(rho_p), 'p': float(pval_p)}

        summary['features'][feat] = {
            'pooled_spearman':          {'rho': float(rho_pool), 'p': float(p_pool)},
            'partial_spearman_pos':     {'rho': float(rho_part), 'p': float(p_part)},
            'fe_regression_pid_pos':    fe,
        }
        per_position[feat] = pp

        print(f'\n── {feat} ──')
        print(f'  pooled Spearman  ρ = {rho_pool:+.4f}  p = {p_pool:.3g}')
        print(f'  partial ρ | pos  ρ = {rho_part:+.4f}  p = {p_part:.3g}')
        print(f'  FE β (z-units)   β = {fe["beta_feat"]:+.4f}  t = {fe["t_feat"]:+.3f}  '
              f'p = {fe["p_feat"]:.3g}  R² = {fe["r2"]:.3f}')
        per_pos_summary = ' '.join(f'P{p}={pp[p]["rho"]:+.3f}' for p in sorted(pp))
        print(f'  per-pos ρ: {per_pos_summary}')

    # Bonferroni survivors
    alpha = summary['alpha_bonferroni']
    survivors = []
    for feat, res in summary['features'].items():
        hits = []
        if res['pooled_spearman']['p'] < alpha:
            hits.append(f'pooled (p={res["pooled_spearman"]["p"]:.2g})')
        if res['partial_spearman_pos']['p'] < alpha:
            hits.append(f'partial (p={res["partial_spearman_pos"]["p"]:.2g})')
        if res['fe_regression_pid_pos']['p_feat'] < alpha:
            hits.append(f'FE (p={res["fe_regression_pid_pos"]["p_feat"]:.2g})')
        if hits:
            survivors.append((feat, hits))

    print(f'\n── Bonferroni α = {alpha:.4f} (5 features × 3 tests) ──')
    if survivors:
        print('  SURVIVORS (positive signal):')
        for feat, hits in survivors:
            print(f'    {feat}: ' + ' / '.join(hits))
    else:
        print('  No feature × test survives Bonferroni. Clean null.')

    summary['bonferroni_survivors'] = [
        {'feature': f, 'tests': h} for f, h in survivors
    ]

    (OUT_DIR / 'summary.json').write_text(json.dumps(summary, indent=2))
    (OUT_DIR / 'per_position.json').write_text(json.dumps({
        k: {str(p): v for p, v in d.items()} for k, d in per_position.items()
    }, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}')
    print(f'[out] {(OUT_DIR / "per_position.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
