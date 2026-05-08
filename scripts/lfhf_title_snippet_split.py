"""Content analysis #2 — title-only vs snippet-only features × LF/HF.

The first crossover computed all content features on `title + ' ' + snippet`.
Those are structurally different streams: titles are skimmed (seconds),
snippets are read (longer). Conflating them could mask signal that lives
in one but not the other.

This script splits the text and tests non-embedding features on each
half (token_count, char_count, TTR, n_numerals, has_price). Embedding-
based features (query_cosine, centroid_novelty) are not split here —
re-embedding half-texts is a larger effort parked in the backlog if
this split shows anything.

Outputs:
  scripts/output/lfhf_title_snippet_split/summary.json
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
SERP_EMBED = ROOT / 'AdSERP/data/serp-embeddings.json'
LFHF_JSON = ROOT.parent / 'pupil-lfhf' / 'validation' / 'butterworth-lfhf-by-position.json'
CURSOR_FEATS = ROOT / 'AdSERP/data/cursor-approach-features.json'
OUT_DIR = ROOT / 'scripts/output/lfhf_title_snippet_split'
OUT_DIR.mkdir(parents=True, exist_ok=True)

NUM_RE = re.compile(r'\b\d+(?:[.,]\d+)?\b')
PRICE_RE = re.compile(r'\$\d+(?:[.,]\d+)?')

STREAMS = ('title', 'snippet')
BASE_FEATURES = ['token_count', 'char_count', 'ttr', 'n_numerals', 'has_price']


def text_features(text: str) -> dict[str, float]:
    text = text.strip()
    tokens = text.split()
    tok_n = len(tokens)
    return {
        'token_count': float(tok_n),
        'char_count':  float(len(text)),
        'ttr':         float(len({t.lower() for t in tokens}) / tok_n) if tok_n else 0.0,
        'n_numerals':  float(len(NUM_RE.findall(text))),
        'has_price':   float(len(PRICE_RE.findall(text)) > 0),
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


def build_split_content() -> dict[tuple[str, int], dict[str, float]]:
    serp = json.load(open(SERP_EMBED))
    out: dict[tuple[str, int], dict[str, float]] = {}
    for tid, results in serp.items():
        for r in results:
            pos = int(r.get('position', -1))
            if pos < 0 or pos >= 10:
                continue
            title = r.get('title') or ''
            snippet = r.get('snippet') or ''
            feats = {}
            for stream, text in (('title', title), ('snippet', snippet)):
                for k, v in text_features(text).items():
                    feats[f'{stream}__{k}'] = v
            # Add ratio features
            feats['title_char_share'] = (
                feats['title__char_count'] /
                max(feats['title__char_count'] + feats['snippet__char_count'], 1)
            )
            out[(tid, pos)] = feats
    return out


def load_behavior() -> dict[tuple[str, int], dict[str, float]]:
    cursor = json.load(open(CURSOR_FEATS))
    out: dict[tuple[str, int], dict[str, float]] = {}
    for r in cursor:
        out[(r['trial_id'], r['position'])] = {
            'was_clicked':    float(r.get('was_clicked', 0)),
            'total_dwell_ms': float(r.get('total_dwell_ms', 0) or 0),
            'n_fixations':    float(r.get('n_fixations', 0) or 0),
        }
    return out


def main() -> None:
    print('[load] LF/HF per (trial, pos)')
    lfhf = load_lfhf()
    print(f'       {len(lfhf):,} valid LF/HF')
    print('[load] split text → per-stream features')
    content = build_split_content()
    print(f'       {len(content):,} (trial, pos) pairs')
    print('[load] behavioral outcomes (positive control)')
    behavior = load_behavior()
    print(f'       {len(behavior):,} records')

    rows_lfhf = []
    for (tid, pos), v in lfhf.items():
        if pos >= 10:
            continue
        cf = content.get((tid, pos))
        if cf is None:
            continue
        rows_lfhf.append({'tid': tid, 'pos': pos, 'lfhf': v, **cf})
    print(f'[join] LF/HF × content: {len(rows_lfhf):,} records')

    rows_beh = []
    for key, cf in content.items():
        bh = behavior.get(key)
        if bh is None:
            continue
        rows_beh.append({**cf, **bh})
    print(f'[join] behavior × content: {len(rows_beh):,} records')

    # Descriptives
    print('\n── Distribution of split features ──')
    for feat in [f'{s}__{b}' for s in STREAMS for b in BASE_FEATURES] + ['title_char_share']:
        vals = np.array([r[feat] for r in rows_lfhf])
        print(f'  {feat:>28s}: mean={vals.mean():.3f}  median={np.median(vals):.3f}')

    lfhf_arr = np.array([r['lfhf'] for r in rows_lfhf])

    # Per-stream × LF/HF pooled Spearman
    print('\n── Pooled Spearman × LF/HF ──')
    pooled: dict[str, dict] = {}
    for feat in [f'{s}__{b}' for s in STREAMS for b in BASE_FEATURES] + ['title_char_share']:
        f_arr = np.array([r[feat] for r in rows_lfhf])
        rho, p = spearmanr(f_arr, lfhf_arr)
        pooled[feat] = {'rho': float(rho), 'p': float(p), 'n': len(rows_lfhf)}
        print(f'  {feat:>28s}: ρ={rho:+.4f}  p={p:.3g}')

    # Positive control: same split features × behavioral outcomes
    print('\n── Positive control: split features × behavior ──')
    pos_control: dict[str, dict] = {}
    beh_arr = {k: np.array([r[k] for r in rows_beh]) for k in
               [f'{s}__{b}' for s in STREAMS for b in BASE_FEATURES] + ['title_char_share'] +
               ['was_clicked', 'total_dwell_ms', 'n_fixations']}
    for feat in [f'{s}__{b}' for s in STREAMS for b in BASE_FEATURES] + ['title_char_share']:
        row = {}
        for out_name in ('was_clicked', 'total_dwell_ms', 'n_fixations'):
            if out_name == 'total_dwell_ms':
                mask = beh_arr['total_dwell_ms'] > 0
                rho, p = spearmanr(beh_arr[feat][mask], beh_arr[out_name][mask])
                n = int(mask.sum())
            else:
                rho, p = spearmanr(beh_arr[feat], beh_arr[out_name])
                n = len(rows_beh)
            row[out_name] = {'rho': float(rho), 'p': float(p), 'n': n}
        pos_control[feat] = row
        print(f'  {feat:>28s}: click ρ={row["was_clicked"]["rho"]:+.3f} '
              f'(p={row["was_clicked"]["p"]:.2g})  '
              f'dwell ρ={row["total_dwell_ms"]["rho"]:+.3f} '
              f'(p={row["total_dwell_ms"]["p"]:.2g})  '
              f'nfix ρ={row["n_fixations"]["rho"]:+.3f} '
              f'(p={row["n_fixations"]["p"]:.2g})')

    # Bonferroni across 11 features × 1 LF/HF test = 11; also 11 × 3 outcomes = 33
    alpha_lfhf = 0.05 / 11
    alpha_beh = 0.05 / 33
    print(f'\n── Bonferroni α = {alpha_lfhf:.4f} for LF/HF (11 tests) ──')
    survivors_lfhf = [(f, r['rho'], r['p']) for f, r in pooled.items() if r['p'] < alpha_lfhf]
    if survivors_lfhf:
        print('  Survivors (LF/HF):')
        for (f, rho, p) in survivors_lfhf:
            print(f'    {f}: ρ={rho:+.4f}  p={p:.3g}')
    else:
        print('  No LF/HF-side test survives Bonferroni. Null.')

    print(f'\n── Bonferroni α = {alpha_beh:.4f} for behavior (33 tests) ──')
    survivors_beh = []
    for feat, row in pos_control.items():
        for out_name, res in row.items():
            if res['p'] < alpha_beh:
                survivors_beh.append((feat, out_name, res['rho'], res['p']))
    if survivors_beh:
        print(f'  Survivors (behavior): {len(survivors_beh)}')
        for (f, o, rho, p) in sorted(survivors_beh, key=lambda t: t[3])[:15]:
            print(f'    {f} × {o}: ρ={rho:+.3f}  p={p:.2g}')
    else:
        print('  No behavioral-side test survives Bonferroni.')

    (OUT_DIR / 'summary.json').write_text(json.dumps({
        'n_records_lfhf': len(rows_lfhf),
        'n_records_behavior': len(rows_beh),
        'lfhf_pooled': pooled,
        'behavior_pooled': pos_control,
        'bonferroni_alpha_lfhf': alpha_lfhf,
        'bonferroni_alpha_behavior': alpha_beh,
        'bonferroni_survivors_lfhf': [
            {'feature': f, 'rho': rho, 'p': p} for (f, rho, p) in survivors_lfhf
        ],
        'bonferroni_survivors_behavior': [
            {'feature': f, 'outcome': o, 'rho': rho, 'p': p}
            for (f, o, rho, p) in survivors_beh
        ],
    }, indent=2))
    print(f'\n[out] {(OUT_DIR / "summary.json").relative_to(ROOT)}')


if __name__ == '__main__':
    main()
