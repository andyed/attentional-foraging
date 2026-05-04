"""Per-participant: knee depth vs click-position distribution shape.

Tests whether the rank-value-prior framing predicts the data:
  - Top-heavy click distribution (sharp drop with rank) → satisficer prior
    → predicted: DEEPER knee, more pre-scroll engagement on top
  - Flatter click distribution → optimizer prior
    → predicted: SHALLOWER knee, broader sampling

Per-participant features:
  - mean knee position (across their trials, hybrid attribution)
  - mean click position
  - top-heaviness of click distribution (fraction at P0; P0+P1)
  - entropy of click distribution
  - regression rate (existing trait)

Correlations across participants.

Output: scripts/output/knee_vs_click_distribution/{summary.json, report.md}

Run:
  .venv/bin/python scripts/knee_vs_click_distribution.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'
OUT = ROOT / 'scripts/output/knee_vs_click_distribution'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_and_scroll, get_trial_meta,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402
from data_loader import typed_aoi_tops  # noqa: E402  # noqa: E402

SCROLL_THRESHOLD_PX = 100


def first_scroll_t(scrolls):
    for t, y in scrolls:
        if y > SCROLL_THRESHOLD_PX:
            return t
    return None


def knee_for_trial(tid):
    meta = get_trial_meta(tid)
    if meta is None:
        return None
    tops = typed_aoi_tops(tid)
    if not tops:
        return None
    n = len(tops)
    fix = load_fixations(tid)
    if not fix:
        return None
    _, scrolls = load_mouse_and_scroll(tid)
    scroll_t = first_scroll_t(scrolls) if scrolls else None
    if scroll_t is None:
        return None

    deepest_pre = -1
    for f in fix:
        if f['t'] >= scroll_t:
            break
        pos = assign_fixation_to_position(f['y'], tops, n)
        if pos is not None and pos >= 0:
            if pos > deepest_pre:
                deepest_pre = pos
    return deepest_pre


def shannon_entropy_clicks(positions):
    """Entropy in bits."""
    if not positions:
        return 0.0
    c = Counter(positions)
    total = sum(c.values())
    p = np.array([v / total for v in c.values()])
    return float(-np.sum(p * np.log2(p)))


def main():
    print('[knee-click] per-participant knee vs click distribution', file=sys.stderr)

    # Load click positions per trial under hybrid attribution
    feats = json.load(open(DATA / 'cursor-approach-features-typed.json'))
    click_pos_by_trial = {}
    for r in feats:
        tid = r['trial_id']
        cp = r.get('click_pos')
        if cp is not None and cp >= 0 and tid not in click_pos_by_trial:
            click_pos_by_trial[tid] = int(cp)

    print(f'  trials with click_pos: {len(click_pos_by_trial):,}', file=sys.stderr)

    # Load existing traits for regression rate
    traits = {}
    traits_path = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
    if traits_path.exists():
        with open(traits_path) as f:
            for row in csv.DictReader(f):
                try:
                    traits[row['participant']] = {
                        'regression_rate': float(row['regression_rate']),
                        'tercile': row['tercile'],
                    }
                except (ValueError, KeyError):
                    pass

    # Compute knee per trial
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    knee_by_trial = {}
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            print(f'  {i+1}/{len(trial_ids)}', file=sys.stderr)
        k = knee_for_trial(tid)
        if k is not None:
            knee_by_trial[tid] = k

    print(f'  trials with knee: {len(knee_by_trial):,}', file=sys.stderr)

    # Aggregate per-participant
    by_pid = defaultdict(lambda: {'knees': [], 'clicks': []})
    for tid in set(knee_by_trial) | set(click_pos_by_trial):
        pid = tid.split('-')[0]
        if tid in knee_by_trial:
            by_pid[pid]['knees'].append(knee_by_trial[tid])
        if tid in click_pos_by_trial:
            by_pid[pid]['clicks'].append(click_pos_by_trial[tid])

    # Per-participant features
    rows = []
    for pid, d in by_pid.items():
        if len(d['knees']) < 5 or len(d['clicks']) < 5:
            continue
        clicks = d['clicks']
        knees = d['knees']
        rows.append({
            'pid': pid,
            'n_knee_trials': len(knees),
            'n_click_trials': len(clicks),
            'mean_knee': float(np.mean(knees)),
            'median_knee': float(np.median(knees)),
            'mean_click_pos': float(np.mean(clicks)),
            'median_click_pos': float(np.median(clicks)),
            'click_at_P0_frac': float(np.mean([c == 0 for c in clicks])),
            'click_at_P0_or_P1_frac': float(np.mean([c <= 1 for c in clicks])),
            'click_at_P3_or_deeper_frac': float(np.mean([c >= 3 for c in clicks])),
            'click_entropy_bits': shannon_entropy_clicks(clicks),
            'regression_rate': traits.get(pid, {}).get('regression_rate'),
            'tercile': traits.get(pid, {}).get('tercile'),
        })

    print(f'\n  participants: {len(rows):,}', file=sys.stderr)

    # Correlations
    def corr(field_a, field_b):
        xs = [r[field_a] for r in rows if r[field_a] is not None and r[field_b] is not None]
        ys = [r[field_b] for r in rows if r[field_a] is not None and r[field_b] is not None]
        if len(xs) < 5:
            return None
        rho = stats.spearmanr(xs, ys)
        pearson = stats.pearsonr(xs, ys)
        return {
            'n': len(xs),
            'spearman_rho': float(rho.statistic), 'spearman_p': float(rho.pvalue),
            'pearson_r': float(pearson.statistic), 'pearson_p': float(pearson.pvalue),
        }

    print(f'\n  Per-participant correlations:', file=sys.stderr)
    correlations = {}
    pairs = [
        ('mean_knee', 'mean_click_pos'),
        ('mean_knee', 'click_at_P0_frac'),
        ('mean_knee', 'click_at_P0_or_P1_frac'),
        ('mean_knee', 'click_at_P3_or_deeper_frac'),
        ('mean_knee', 'click_entropy_bits'),
        ('mean_knee', 'regression_rate'),
        ('regression_rate', 'click_entropy_bits'),
        ('regression_rate', 'click_at_P0_frac'),
        ('regression_rate', 'mean_click_pos'),
    ]
    for a, b in pairs:
        c = corr(a, b)
        if c is None:
            print(f'    {a} × {b}: insufficient data', file=sys.stderr)
            correlations[f'{a}__{b}'] = None
            continue
        print(f'    {a} × {b}: '
              f'Spearman ρ = {c["spearman_rho"]:+.3f} (p = {c["spearman_p"]:.3e}), '
              f'Pearson r = {c["pearson_r"]:+.3f} (p = {c["pearson_p"]:.3e}), '
              f'n = {c["n"]}', file=sys.stderr)
        correlations[f'{a}__{b}'] = c

    summary = {
        'attribution': 'typed',
        'n_participants': len(rows),
        'correlations': correlations,
        'per_participant': rows,
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2))

    # Markdown
    lines = [
        '# Per-participant knee vs click distribution\n',
        '_Generated 2026-05-03 by `scripts/knee_vs_click_distribution.py`._\n',
        '## Hypothesis\n',
        'Under the rank-value-prior framing:',
        '- Satisficer prior (top-heavy): high P(value | top) → invest in top → DEEPER knee, '
        'higher concentration of clicks on top positions.',
        '- Optimizer prior (flatter): wider sampling → SHALLOWER knee, '
        'flatter click distribution.',
        '',
        'Predictions:',
        '- mean_knee × mean_click_pos: positive (deeper knee → deeper clicks, since '
        'satisficer evaluates top carefully and may take what comes next)',
        '- mean_knee × click_at_P0_frac: weak/negative (deeper knee = satisficer; '
        "satisficers don't always click P0 since they take first acceptable)",
        '- mean_knee × click_entropy_bits: positive (deeper knee = satisficer = more '
        'concentrated commit decisions; lower entropy if clicks cluster)',
        '- regression_rate × mean_knee: negative (already known: high regr-rate = '
        'optimizer = shallow knee)',
        '',
        f'## Cohort: {len(rows):,} participants\n',
        '## Cross-participant correlations\n',
        '| Pair | n | Spearman ρ | p | Pearson r | p |',
        '|---|---|---|---|---|---|',
    ]
    for a, b in pairs:
        c = correlations.get(f'{a}__{b}')
        if c is None:
            lines.append(f'| {a} × {b} | — | — | — | — | — |')
            continue
        lines.append(
            f'| {a} × {b} | {c["n"]} | {c["spearman_rho"]:+.3f} | {c["spearman_p"]:.3e} | '
            f'{c["pearson_r"]:+.3f} | {c["pearson_p"]:.3e} |'
        )

    (OUT / 'report.md').write_text('\n'.join(lines))
    print(f'\nwrote {(OUT / "summary.json").relative_to(ROOT)}', file=sys.stderr)


if __name__ == '__main__':
    main()
