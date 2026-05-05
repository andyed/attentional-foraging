"""Ad-utility prior as predictor — per-participant analysis.

Builds two per-participant measures and tests whether the *prior*
(ad-attention rate during forward survey) predicts the *behavior*
(ad click rate, click position, sat/opt class) — the empirical
substrate for the rank-value-prior framing in the task-model paper
and a candidate premise for CIKM.

Per-participant prior measures (from existing per_participant_with_traits.csv):
  - p_ad_survey       : fraction of survey-phase fixations that landed on ads
  - ad_over_index     : ratio (p_ad_survey / area_share_ads) — calibrates against
                        the visible ad surface
  - n_ad_top_trials   : count of trials with at least one ad above the fold

Per-participant behavior measures (from cursor-approach-features-typed.json):
  - p_ad_click        : fraction of all clicks that landed on an ad surface
                        (dd_top + native_ad + dd_right combined)
  - p_dd_top_click    : fraction of all clicks landing on dd_top specifically
                        (the highest-CTR ad surface, population mean 17.1%)
  - mean_click_pos    : mean position-in-typed-rank of clicks
  - n_clicks          : per-ppt click count

Tests:
  - Spearman(p_ad_survey, p_ad_click)
  - Spearman(p_ad_survey, p_dd_top_click)
  - Spearman(p_ad_survey, mean_click_pos)
  - Spearman(p_ad_survey, regression_rate)        [sat-opt orthogonality]
  - Spearman(p_ad_survey, mean_lhipa)             [load × prior independence]

Outputs:
  scripts/output/ad_utility_prior/summary.json
  scripts/output/ad_utility_prior/per_participant.csv

Run:
  .venv/bin/python scripts/ad_utility_prior_analysis.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
TYPED_FEATURES = ROOT / 'AdSERP/data/cursor-approach-features-typed.json'
TRAITS_CSV = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
OUT_DIR = ROOT / 'scripts/output/ad_utility_prior'
OUT_DIR.mkdir(parents=True, exist_ok=True)

AD_TYPES = {'dd_top', 'native_ad', 'dd_right'}


def load_traits():
    rows = list(csv.DictReader(open(TRAITS_CSV)))
    return {r['participant']: r for r in rows}


def build_per_participant_behavior():
    """Aggregate cursor-approach-features-typed.json by participant.

    Returns dict {pid: {p_ad_click, p_dd_top_click, mean_click_pos,
                         n_clicks, n_ad_clicks}}.
    """
    feats = json.load(open(TYPED_FEATURES))
    by_pid = defaultdict(lambda: {
        'click_etypes': [],          # list of etypes among clicked rows
        'click_positions': [],       # list of clicked positions
    })
    for r in feats:
        pid = r['trial_id'].split('-')[0]
        if r.get('was_clicked'):
            by_pid[pid]['click_etypes'].append(r.get('etype', ''))
            cp = r.get('click_pos')
            if cp is not None:
                by_pid[pid]['click_positions'].append(cp)
    out = {}
    for pid, d in by_pid.items():
        n_clicks = len(d['click_etypes'])
        if n_clicks == 0:
            continue
        n_ad_clicks = sum(1 for et in d['click_etypes'] if et in AD_TYPES)
        n_dd_top_clicks = sum(1 for et in d['click_etypes'] if et == 'dd_top')
        n_native_ad_clicks = sum(1 for et in d['click_etypes']
                                  if et == 'native_ad')
        positions = d['click_positions']
        out[pid] = {
            'n_clicks': n_clicks,
            'n_ad_clicks': n_ad_clicks,
            'n_dd_top_clicks': n_dd_top_clicks,
            'n_native_ad_clicks': n_native_ad_clicks,
            'p_ad_click': n_ad_clicks / n_clicks,
            'p_dd_top_click': n_dd_top_clicks / n_clicks,
            'p_native_ad_click': n_native_ad_clicks / n_clicks,
            'mean_click_pos': float(np.mean(positions)) if positions else None,
        }
    return out


def safe_float(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def main():
    print("[ad-utility-prior] Loading traits + behavior...", file=sys.stderr)
    traits = load_traits()
    behavior = build_per_participant_behavior()

    common = sorted(set(traits) & set(behavior))
    print(f"  participants with traits: {len(traits)}", file=sys.stderr)
    print(f"  participants with click data: {len(behavior)}", file=sys.stderr)
    print(f"  common: {len(common)}", file=sys.stderr)

    # Per-ppt joined table
    rows = []
    for pid in common:
        t = traits[pid]
        b = behavior[pid]
        rows.append({
            'participant': pid,
            'p_ad_survey': safe_float(t.get('p_ad_survey')),
            'ad_over_index': safe_float(t.get('ad_over_index')),
            'n_ad_top_trials': safe_float(t.get('n_ad_top_trials')),
            'mean_ad_area_frac': safe_float(t.get('mean_ad_area_frac')),
            'regression_rate': safe_float(t.get('regression_rate')),
            'mean_lhipa': safe_float(t.get('mean_lhipa')),
            'mean_fixations': safe_float(t.get('mean_fixations')),
            'tercile': t.get('tercile'),
            'p_ad_click': b['p_ad_click'],
            'p_dd_top_click': b['p_dd_top_click'],
            'p_native_ad_click': b['p_native_ad_click'],
            'mean_click_pos': b['mean_click_pos'],
            'n_clicks': b['n_clicks'],
            'n_ad_clicks': b['n_ad_clicks'],
        })

    # Pull arrays for correlations
    def col(name):
        return np.array([r[name] for r in rows if r[name] is not None
                         and (rows[0].get(name) is None or
                              rows[rows.index(r)][name] is not None)])

    def aligned(*names):
        keep = []
        for r in rows:
            if all(r.get(n) is not None for n in names):
                keep.append(r)
        return {n: np.array([r[n] for r in keep]) for n in names}

    print("\n=== Per-participant correlations (n joined ≤ 47) ===\n",
          file=sys.stderr)

    tests = [
        ('p_ad_survey', 'p_ad_click',
         'ad-attention prior → ad-click rate'),
        ('p_ad_survey', 'p_dd_top_click',
         'ad-attention prior → dd_top-click rate'),
        ('p_ad_survey', 'p_native_ad_click',
         'ad-attention prior → native_ad-click rate'),
        ('ad_over_index', 'p_ad_click',
         'ad over-index (calibrated by area) → ad-click rate'),
        ('ad_over_index', 'p_dd_top_click',
         'ad over-index → dd_top-click rate'),
        ('p_ad_survey', 'mean_click_pos',
         'ad-attention prior → mean click position'),
        ('p_ad_survey', 'regression_rate',
         'ad-attention prior → regression rate (sat-opt)'),
        ('p_ad_survey', 'mean_lhipa',
         'ad-attention prior → trial-mean LHIPA (cognitive load)'),
        ('p_ad_click', 'regression_rate',
         'ad-click rate → regression rate'),
        ('p_dd_top_click', 'regression_rate',
         'dd_top-click rate → regression rate'),
    ]
    test_results = []
    for x_name, y_name, label in tests:
        d = aligned(x_name, y_name)
        x, y = d[x_name], d[y_name]
        if len(x) < 8:
            print(f"  {label:55s} : n={len(x)} insufficient", file=sys.stderr)
            continue
        rho, p = stats.spearmanr(x, y)
        r, _ = stats.pearsonr(x, y)
        print(f"  {label:55s} : n={len(x):2d}  ρ={rho:+.3f}  p={p:.4f}  r={r:+.3f}",
              file=sys.stderr)
        test_results.append({
            'x': x_name, 'y': y_name, 'label': label,
            'n': int(len(x)),
            'spearman_rho': float(rho), 'spearman_p': float(p),
            'pearson_r': float(r),
        })

    # Summary stats
    p_ad_click_arr = np.array([r['p_ad_click'] for r in rows])
    p_dd_top_arr = np.array([r['p_dd_top_click'] for r in rows])
    p_native_ad_arr = np.array([r['p_native_ad_click'] for r in rows])
    p_ad_survey_arr = np.array([r['p_ad_survey'] for r in rows
                                 if r['p_ad_survey'] is not None])

    n_zero_ad_clickers = int(np.sum(p_ad_click_arr == 0))
    n_high_ad_clickers = int(np.sum(p_ad_click_arr >= 0.20))

    print(f"\n=== Per-participant ad-click distribution ===", file=sys.stderr)
    print(f"  p_ad_click  median={np.median(p_ad_click_arr):.3f}  "
          f"mean={np.mean(p_ad_click_arr):.3f}  "
          f"IQR=[{np.percentile(p_ad_click_arr, 25):.3f}, "
          f"{np.percentile(p_ad_click_arr, 75):.3f}]  "
          f"min={p_ad_click_arr.min():.3f}  max={p_ad_click_arr.max():.3f}",
          file=sys.stderr)
    print(f"  p_dd_top    median={np.median(p_dd_top_arr):.3f}  "
          f"mean={np.mean(p_dd_top_arr):.3f}  "
          f"max={p_dd_top_arr.max():.3f}", file=sys.stderr)
    print(f"  zero-ad-clickers: {n_zero_ad_clickers}/{len(rows)}",
          file=sys.stderr)
    print(f"  high-ad-clickers (≥20%): {n_high_ad_clickers}/{len(rows)}",
          file=sys.stderr)

    print(f"\n=== Per-participant ad-attention prior distribution ===",
          file=sys.stderr)
    print(f"  p_ad_survey  median={np.median(p_ad_survey_arr):.3f}  "
          f"mean={np.mean(p_ad_survey_arr):.3f}  "
          f"IQR=[{np.percentile(p_ad_survey_arr, 25):.3f}, "
          f"{np.percentile(p_ad_survey_arr, 75):.3f}]  "
          f"min={p_ad_survey_arr.min():.3f}  max={p_ad_survey_arr.max():.3f}",
          file=sys.stderr)

    summary = {
        'date': '2026-05-04',
        'attribution': 'typed',
        'n_participants_joined': int(len(common)),
        'distributions': {
            'p_ad_click': {
                'median': float(np.median(p_ad_click_arr)),
                'mean': float(np.mean(p_ad_click_arr)),
                'p25': float(np.percentile(p_ad_click_arr, 25)),
                'p75': float(np.percentile(p_ad_click_arr, 75)),
                'min': float(p_ad_click_arr.min()),
                'max': float(p_ad_click_arr.max()),
                'n_zero': n_zero_ad_clickers,
                'n_high_20pct': n_high_ad_clickers,
            },
            'p_dd_top_click': {
                'median': float(np.median(p_dd_top_arr)),
                'mean': float(np.mean(p_dd_top_arr)),
                'max': float(p_dd_top_arr.max()),
            },
            'p_native_ad_click': {
                'median': float(np.median(p_native_ad_arr)),
                'mean': float(np.mean(p_native_ad_arr)),
                'max': float(p_native_ad_arr.max()),
            },
            'p_ad_survey': {
                'median': float(np.median(p_ad_survey_arr)),
                'mean': float(np.mean(p_ad_survey_arr)),
                'p25': float(np.percentile(p_ad_survey_arr, 25)),
                'p75': float(np.percentile(p_ad_survey_arr, 75)),
                'min': float(p_ad_survey_arr.min()),
                'max': float(p_ad_survey_arr.max()),
            },
        },
        'tests': test_results,
    }
    json.dump(summary, open(OUT_DIR / 'summary.json', 'w'), indent=2)

    # CSV per-ppt
    with (OUT_DIR / 'per_participant.csv').open('w') as f:
        if rows:
            cols = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print(f"\nWrote {OUT_DIR}/summary.json + per_participant.csv",
          file=sys.stderr)


if __name__ == '__main__':
    main()
