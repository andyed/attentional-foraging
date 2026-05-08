"""Content analysis #1 — price / numeral saliency × LF/HF.

Commercial SERP queries load snippets with prices, product numbers,
percent-off, SKUs. Numerals are exogenously salient and price presence
is decision-ready content. Test whether numeral/price features move
LF/HF per position, controlling for raw text length.

Features (per-result, from title + snippet):
  has_price        — bool: any `$\\d+(?:\\.\\d+)?` match
  n_prices         — int:  count of `$\\d+` matches
  has_percent_off  — bool: any `\\d+%\\s*(off|discount|save)` match
  n_numerals       — int:  count of numeric tokens (4+ digits + decimals)
  first_numeral_pos— int:  character index of first numeral (-1 if none)
  numeral_density  — float: n_numerals / token_count

Outputs:
  scripts/output/lfhf_price_numeral_saliency/summary.json
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parent.parent
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
CURSOR_FEATS = ROOT / 'AdSERP/data/cursor-approach-features.json'
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
OUT_DIR = ROOT / 'scripts/output/lfhf_price_numeral_saliency'
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRICE_RE   = re.compile(r'\$\d+(?:[.,]\d+)?')
PERCENT_RE = re.compile(r'\b\d+\s*%\s*(?:off|discount|savings?|save)\b', re.IGNORECASE)
NUM_RE     = re.compile(r'\b\d+(?:[.,]\d+)?\b')

FEATURES = ['has_price', 'n_prices', 'has_percent_off', 'n_numerals',
            'first_numeral_pos', 'numeral_density']


def extract_features(text: str) -> dict[str, float]:
    prices = PRICE_RE.findall(text)
    percents = PERCENT_RE.findall(text)
    nums = list(NUM_RE.finditer(text))
    tokens = text.split()
    first_numeral_match = NUM_RE.search(text)
    first_pos = first_numeral_match.start() if first_numeral_match else -1
    return {
        'has_price':         float(len(prices) > 0),
        'n_prices':          float(len(prices)),
        'has_percent_off':   float(len(percents) > 0),
        'n_numerals':        float(len(nums)),
        'first_numeral_pos': float(first_pos),
        'numeral_density':   float(len(nums) / max(len(tokens), 1)),
    }


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


def build_content() -> dict[tuple[str, int], dict[str, float]]:
    serp = json.load(open(SERP_EMBED))
    out: dict[tuple[str, int], dict[str, float]] = {}
    for tid, results in serp.items():
        for r in results:
            pos = int(r.get('position', -1))
            if pos < 0 or pos >= 10:
                continue
            text = ((r.get('title') or '') + ' ' + (r.get('snippet') or '')).strip()
            out[(tid, pos)] = extract_features(text)
    return out


def build_behavioral() -> dict[tuple[str, int], dict[str, float]]:
    cursor = json.load(open(CURSOR_FEATS))
    out: dict[tuple[str, int], dict[str, float]] = {}
    for r in cursor:
        out[(r['trial_id'], r['position'])] = {
            'was_clicked':    float(r.get('was_clicked', 0)),
            'total_dwell_ms': float(r.get('total_dwell_ms', 0) or 0),
            'n_fixations':    float(r.get('n_fixations', 0) or 0),
        }
    return out


def spearman_report(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 20:
        return float('nan'), float('nan'), int(mask.sum())
    rho, p = spearmanr(x[mask], y[mask])
    return float(rho), float(p), int(mask.sum())


def mann_whitney_report(binary: np.ndarray, outcome: np.ndarray) -> dict:
    mask = np.isfinite(outcome)
    b = binary[mask].astype(bool)
    y = outcome[mask]
    on = y[b]; off = y[~b]
    if len(on) < 10 or len(off) < 10:
        return {'n_on': int(len(on)), 'n_off': int(len(off))}
    u, p = mannwhitneyu(on, off, alternative='two-sided')
    return {
        'median_on':  float(np.median(on)),
        'median_off': float(np.median(off)),
        'u': float(u), 'p': float(p),
        'n_on': int(len(on)), 'n_off': int(len(off)),
    }


def main() -> None:
    print('[load] LF/HF per (trial, pos)')
    lfhf = load_lfhf()
    print(f'       {len(lfhf):,} valid LF/HF observations')
    print('[load] content text → price/numeral features')
    content = build_content()
    print(f'       {len(content):,} (trial, pos) pairs')
    print('[load] behavioral outcomes for positive-control')
    behavior = build_behavioral()
    print(f'       {len(behavior):,} records')

    # Join for LF/HF
    rows_lfhf = []
    for (tid, pos), v in lfhf.items():
        if pos >= 10:
            continue
        cf = content.get((tid, pos))
        if cf is None:
            continue
        rows_lfhf.append({'tid': tid, 'pos': pos, 'lfhf': v, **cf})
    print(f'[join] LF/HF × content: {len(rows_lfhf):,} records')

    # Join for behavior (positive control)
    rows_beh = []
    for key, cf in content.items():
        bh = behavior.get(key)
        if bh is None:
            continue
        rows_beh.append({**cf, **bh})
    print(f'[join] Behavior × content: {len(rows_beh):,} records')

    # Corpus-level description of the features
    desc = {}
    for feat in FEATURES:
        vals = np.array([r[feat] for r in rows_lfhf])
        desc[feat] = {
            'mean':   float(np.mean(vals)),
            'median': float(np.median(vals)),
            'share_nonzero_or_true': float((vals > 0).mean()),
        }
    print('\n── Feature distribution (LF/HF-joined subset) ──')
    for feat, d in desc.items():
        print(f'  {feat:>20s}: mean={d["mean"]:.3f}  median={d["median"]:.3f}  '
              f'share>0={d["share_nonzero_or_true"]:.2%}')

    lfhf_arr = np.array([r['lfhf'] for r in rows_lfhf])
    pos_arr = np.array([r['pos'] for r in rows_lfhf])

    print('\n── Feature × LF/HF (Spearman, pooled) ──')
    pooled: dict[str, dict] = {}
    for feat in FEATURES:
        f_arr = np.array([r[feat] for r in rows_lfhf])
        rho, p, n = spearman_report(f_arr, lfhf_arr)
        pooled[feat] = {'rho': rho, 'p': p, 'n': n}
        print(f'  {feat:>20s}: ρ={rho:+.4f}  p={p:.3g}  N={n:,}')

    print('\n── Binary features × LF/HF (Mann-Whitney) ──')
    mw: dict[str, dict] = {}
    for feat in ('has_price', 'has_percent_off'):
        f_arr = np.array([r[feat] for r in rows_lfhf])
        res = mann_whitney_report(f_arr, lfhf_arr)
        mw[feat] = res
        if 'u' in res:
            print(f'  {feat:>20s}: LF/HF median on={res["median_on"]:.2f} vs off={res["median_off"]:.2f}  '
                  f'p={res["p"]:.3g}  (N_on={res["n_on"]}, N_off={res["n_off"]})')
        else:
            print(f'  {feat:>20s}: insufficient N_on or N_off')

    print('\n── Per-position LF/HF × n_numerals ──')
    per_pos_numerals = {}
    for p in range(10):
        mask = pos_arr == p
        if mask.sum() < 30:
            continue
        f = np.array([rows_lfhf[i]['n_numerals'] for i in range(len(rows_lfhf)) if pos_arr[i] == p])
        y = lfhf_arr[mask]
        rho, pv, _ = spearman_report(f, y)
        per_pos_numerals[p] = {'n': int(mask.sum()), 'rho': rho, 'p': pv}
        print(f'  P{p}: ρ(n_numerals, LF/HF) = {rho:+.3f}  p={pv:.3g}  N={mask.sum()}')

    print('\n── Positive control: features × behavioral outcomes ──')
    beh_arr = {k: np.array([r[k] for r in rows_beh]) for k in
               FEATURES + ['was_clicked', 'total_dwell_ms', 'n_fixations']}
    pos_control: dict[str, dict] = {}
    for feat in FEATURES:
        row = {}
        for out_name in ('was_clicked', 'total_dwell_ms', 'n_fixations'):
            if out_name == 'total_dwell_ms':
                mask = beh_arr['total_dwell_ms'] > 0
                rho, p, n = spearman_report(beh_arr[feat][mask], beh_arr[out_name][mask])
            else:
                rho, p, n = spearman_report(beh_arr[feat], beh_arr[out_name])
            row[out_name] = {'rho': rho, 'p': p, 'n': n}
        pos_control[feat] = row
        print(f'  {feat:>20s}: click ρ={row["was_clicked"]["rho"]:+.3f} (p={row["was_clicked"]["p"]:.2g}) · '
              f'dwell ρ={row["total_dwell_ms"]["rho"]:+.3f} (p={row["total_dwell_ms"]["p"]:.2g}) · '
              f'nfix ρ={row["n_fixations"]["rho"]:+.3f} (p={row["n_fixations"]["p"]:.2g})')

    # Bonferroni at α=0.05 / (6 features × 3 LF/HF-side tests + 2 MW tests) = 0.05/20
    alpha = 0.05 / 20
    print(f'\n── Bonferroni α = {alpha:.4f} (20 tests LF/HF side) ──')
    survivors = []
    for feat, r in pooled.items():
        if r['p'] < alpha:
            survivors.append(('pooled', feat, r['rho'], r['p']))
    for feat, r in mw.items():
        if 'p' in r and r['p'] < alpha:
            survivors.append(('mw', feat, r.get('median_on', 0) - r.get('median_off', 0), r['p']))
    for p, r in per_pos_numerals.items():
        if r['p'] < alpha:
            survivors.append(('per_pos', f'n_numerals@P{p}', r['rho'], r['p']))
    if survivors:
        print('  Survivors:')
        for (test, label, stat, p) in survivors:
            print(f'    {test}  {label}: stat={stat:+.4f}  p={p:.3g}')
    else:
        print('  No LF/HF-side test survives Bonferroni. Null.')

    (OUT_DIR / 'summary.json').write_text(json.dumps({
        'n_records_lfhf': len(rows_lfhf),
        'n_records_behavior': len(rows_beh),
        'feature_distribution': desc,
        'lfhf_pooled_spearman': pooled,
        'lfhf_mann_whitney': mw,
        'lfhf_per_position_numerals': {str(k): v for k, v in per_pos_numerals.items()},
        'positive_control_behavior': pos_control,
        'bonferroni_alpha': alpha,
        'bonferroni_survivors': [
            {'test': t, 'label': l, 'stat': s, 'p': p} for (t, l, s, p) in survivors
        ],
    }, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
