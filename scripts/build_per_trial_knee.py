"""Durable PER-TRIAL knee dataset — the foundation the rank-value-prior CR model needs.

The existing knee_vs_click_distribution.py computes the knee per trial but aggregates it away to
per-participant means and only persists those. The trial grain is exactly what the falsification-first
hinge needs ("does THIS trial's knee predict THIS trial's click beyond the participant's prior?"),
so this script persists it — reusing the IDENTICAL knee definition (deepest typed-AOI rank fixated
before the first scroll > 100px) so the per-participant correlations (mean_knee × mean_click_pos
ρ≈+0.47, × P0-frac ≈−0.41, × entropy ≈+0.47, × regression_rate ≈−0.02) reproduce as a self-check.

In the SAME pre-scroll pass it captures, for free, what the generative model will need later: the
per-rank pre-scroll fixation profile (the precision-allocation signal), consideration-set size, and
the page's relevance spread.

Output: scripts/output/knee_per_trial/{per_trial.json, gate_check.json}
Run:    .venv/bin/python scripts/build_per_trial_knee.py
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
OUT = ROOT / 'scripts/output/knee_per_trial'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, load_mouse_and_scroll, get_trial_meta,
    assign_fixation_to_position, typed_aoi_tops,
)

SCROLL_THRESHOLD_PX = 100  # identical to knee_vs_click_distribution.py


def first_scroll_t(scrolls):
    for t, y in scrolls:
        if y > SCROLL_THRESHOLD_PX:
            return t
    return None


def knee_and_profile(tid):
    """Return (knee, n_tops, pre_scroll_fix_by_rank) using the EXACT knee definition, or None.

    knee = deepest rank fixated before the first scroll > 100px (-1 if none landed on a ranked AOI).
    pre_scroll_fix_by_rank[r] = count of pre-scroll fixations assigned to rank r (the allocation profile).
    """
    if get_trial_meta(tid) is None:
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
    by_rank = [0] * n
    for f in fix:
        if f['t'] >= scroll_t:
            break
        pos = assign_fixation_to_position(f['y'], tops, n)
        if pos is not None and 0 <= pos < n:
            by_rank[pos] += 1
            if pos > deepest_pre:
                deepest_pre = pos
    return deepest_pre, n, by_rank


def shannon_entropy(positions):
    if not positions:
        return 0.0
    c = Counter(positions)
    tot = sum(c.values())
    p = np.array([v / tot for v in c.values()])
    return float(-np.sum(p * np.log2(p)))


def main():
    log = lambda *a: print(*a, file=sys.stderr)

    # click_pos per trial (typed attribution) — identical source to the original
    feats = json.load(open(DATA / 'cursor-approach-features-typed.json'))
    click_by_trial = {}
    for r in feats:
        tid, cp = r['trial_id'], r.get('click_pos')
        if cp is not None and cp >= 0 and tid not in click_by_trial:
            click_by_trial[tid] = int(cp)
    log(f'  trials with click_pos: {len(click_by_trial):,}')

    # participant regression-rate trait
    traits = {}
    tp = ROOT / 'scripts/output/survey_bimodality/per_participant_with_traits.csv'
    if tp.exists():
        for row in csv.DictReader(open(tp)):
            try:
                traits[row['participant']] = {
                    'regression_rate': float(row['regression_rate']),
                    'tercile': row['tercile'],
                }
            except (ValueError, KeyError):
                pass

    # page relevance spread (the content-derived depth signal; free dict lookup)
    spread = {}
    sp = DATA / 'serp-difficulty-measures.json'
    if sp.exists():
        for tid, d in json.load(open(sp)).items():
            rs = d.get('relevance_spread')
            if rs is not None:
                spread[tid] = float(rs)

    # iterate the SAME trial universe as the original (butterworth-lfhf-by-position keys)
    trial_ids = sorted(json.load(open(DATA / 'butterworth-lfhf-by-position.json')).keys())
    rows = []
    for i, tid in enumerate(trial_ids):
        if (i + 1) % 500 == 0:
            log(f'  {i+1}/{len(trial_ids)}')
        kp = knee_and_profile(tid)
        if kp is None:
            continue
        knee, n_tops, by_rank = kp
        pid = tid.split('-')[0]
        rows.append({
            'tid': tid, 'pid': pid,
            'knee': int(knee),
            'click_pos': click_by_trial.get(tid),
            'n_tops': int(n_tops),
            'relevance_spread': spread.get(tid),
            'pre_scroll_fix_by_rank': by_rank,
            'regression_rate': traits.get(pid, {}).get('regression_rate'),
            'tercile': traits.get(pid, {}).get('tercile'),
        })

    n_knee = len(rows)
    n_both = sum(1 for r in rows if r['click_pos'] is not None)
    log(f'  trials with knee: {n_knee:,} | with knee AND click: {n_both:,}')
    (OUT / 'per_trial.json').write_text(json.dumps(rows))

    # ---- GATE: reproduce the per-participant correlations from the trial table ----
    by_pid = defaultdict(lambda: {'knees': [], 'clicks': []})
    # match the original's set-union aggregation: a participant's knees and clicks are pooled
    # independently across their trials (knee from knee-trials, clicks from click-trials)
    seen_click = set()
    for r in rows:
        by_pid[r['pid']]['knees'].append(r['knee'])
    for tid, cp in click_by_trial.items():
        by_pid[tid.split('-')[0]]['clicks'].append(cp)

    pp = []
    for pid, d in by_pid.items():
        if len(d['knees']) < 5 or len(d['clicks']) < 5:
            continue
        cl = d['clicks']
        pp.append({
            'pid': pid,
            'mean_knee': float(np.mean(d['knees'])),
            'mean_click_pos': float(np.mean(cl)),
            'click_at_P0_frac': float(np.mean([c == 0 for c in cl])),
            'click_at_P3_or_deeper_frac': float(np.mean([c >= 3 for c in cl])),
            'click_entropy_bits': shannon_entropy(cl),
            'regression_rate': traits.get(pid, {}).get('regression_rate'),
        })

    def corr(a, b):
        xs = [r[a] for r in pp if r[a] is not None and r[b] is not None]
        ys = [r[b] for r in pp if r[a] is not None and r[b] is not None]
        rho = stats.spearmanr(xs, ys)
        return {'n': len(xs), 'rho': float(rho.statistic), 'p': float(rho.pvalue)}

    pairs = [('mean_knee', 'mean_click_pos'), ('mean_knee', 'click_at_P0_frac'),
             ('mean_knee', 'click_at_P3_or_deeper_frac'), ('mean_knee', 'click_entropy_bits'),
             ('mean_knee', 'regression_rate')]
    gate = {f'{a}__{b}': corr(a, b) for a, b in pairs}
    gate['_n_participants'] = len(pp)
    (OUT / 'gate_check.json').write_text(json.dumps(gate, indent=2))

    EXPECT = {'mean_knee__mean_click_pos': 0.471, 'mean_knee__click_at_P0_frac': -0.408,
              'mean_knee__click_at_P3_or_deeper_frac': 0.337, 'mean_knee__click_entropy_bits': 0.465,
              'mean_knee__regression_rate': -0.021}
    log(f'\n  GATE — per-participant reproduction (n={len(pp)}):')
    ok = True
    for k, exp in EXPECT.items():
        got = gate[k]['rho']
        match = abs(got - exp) < 0.03
        ok &= match
        flag = 'OK' if match else '*** DRIFT ***'
        log(f'    {k:42} rho={got:+.3f}  (expect {exp:+.3f})  {flag}')
    verdict = 'PASSED' if ok else 'FAILED'
    log(f'\n  GATE {verdict} - wrote per_trial.json ({n_knee:,} rows), gate_check.json')


if __name__ == '__main__':
    main()
