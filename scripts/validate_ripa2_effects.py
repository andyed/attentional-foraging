"""Validate RIPA2 against the 5 effects from notebook 14's head-to-head table.

1. Survey → Evaluate phase transition
2. Click position (clicked vs non-clicked)
3. Satisficer vs Optimizer (shallow vs deep foraging)
4. Boundary clickers (click at last-visited position)
5. SERP difficulty

Outputs a summary table for comparison with LF/HF and LHIPA.

Usage:
    uv run python scripts/validate_ripa2_effects.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

sys.path.insert(0, str(Path(__file__).parent.parent / 'notebooks-v2'))
from data_loader import (
    get_trial_ids, load_fixations, load_difficulty_measures, load_lhipa,
)

DATA_DIR = Path(__file__).parent.parent / 'AdSERP' / 'data'


def load_ripa2():
    with open(DATA_DIR / 'ripa2-by-position.json') as f:
        return json.load(f)


def load_butterworth():
    with open(DATA_DIR / 'butterworth-lfhf-by-position.json') as f:
        return json.load(f)


def print_effect(name, group_a_name, group_a, group_b_name, group_b, alt='two-sided'):
    """Print Mann-Whitney comparison."""
    if not group_a or not group_b:
        print(f'  {name}: insufficient data (n={len(group_a)} vs {len(group_b)})')
        return None
    u, p = mannwhitneyu(group_a, group_b, alternative=alt)
    ma, mb = np.median(group_a), np.median(group_b)
    print(f'  {name}:')
    print(f'    {group_a_name}: median={ma:.4f}, n={len(group_a)}')
    print(f'    {group_b_name}: median={mb:.4f}, n={len(group_b)}')
    print(f'    U={u:.0f}, p={p:.2e}')
    return p


def main():
    ripa2_data = load_ripa2()
    bw_data = load_butterworth()

    print('=' * 70)
    print('RIPA2 VALIDATION: 5 effects from notebook 14')
    print('=' * 70)

    # ── Effect 1: Survey → Evaluate phase ──────────────────────────────
    # Survey = positions 0-1 (first ~3 fixations, gist sampling)
    # Evaluate = positions 2+ (committed reading)
    # LF/HF detects this at p = 10⁻⁴⁹

    print('\n1. SURVEY → EVALUATE PHASE TRANSITION')
    print('   (positions 0-1 vs positions 2-5)')

    survey_ripa2, eval_ripa2 = [], []
    survey_lfhf, eval_lfhf = [], []

    for tid in ripa2_data:
        for p in ripa2_data[tid]['positions']:
            if p['ripa2'] is None:
                continue
            if p['pos'] <= 1:
                survey_ripa2.append(p['ripa2'])
            elif 2 <= p['pos'] <= 5:
                eval_ripa2.append(p['ripa2'])

        if tid in bw_data:
            for p in bw_data[tid]['positions']:
                if p['lfhf'] is None:
                    continue
                if p['pos'] <= 1:
                    survey_lfhf.append(p['lfhf'])
                elif 2 <= p['pos'] <= 5:
                    eval_lfhf.append(p['lfhf'])

    print_effect('RIPA2', 'Survey (pos 0-1)', survey_ripa2,
                 'Evaluate (pos 2-5)', eval_ripa2)
    print_effect('LF/HF', 'Survey (pos 0-1)', survey_lfhf,
                 'Evaluate (pos 2-5)', eval_lfhf)

    # ── Effect 2: Click position ───────────────────────────────────────
    # Does the clicked result show different cognitive load?
    # LHIPA detects at p = 10⁻⁴; LF/HF is null

    print('\n2. CLICK POSITION (clicked vs non-clicked)')

    click_ripa2, noclick_ripa2 = [], []
    click_lfhf, noclick_lfhf = [], []

    for tid in ripa2_data:
        click_pos = ripa2_data[tid].get('click_pos')
        for p in ripa2_data[tid]['positions']:
            if p['ripa2'] is None or p['pos'] > 10:
                continue
            if p['pos'] == click_pos:
                click_ripa2.append(p['ripa2'])
            else:
                noclick_ripa2.append(p['ripa2'])

        if tid in bw_data:
            click_pos_b = bw_data[tid].get('click_pos')
            for p in bw_data[tid]['positions']:
                if p['lfhf'] is None or p['pos'] > 10:
                    continue
                if p['pos'] == click_pos_b:
                    click_lfhf.append(p['lfhf'])
                else:
                    noclick_lfhf.append(p['lfhf'])

    print_effect('RIPA2', 'Clicked', click_ripa2, 'Non-clicked', noclick_ripa2)
    print_effect('LF/HF', 'Clicked', click_lfhf, 'Non-clicked', noclick_lfhf)

    # ── Effect 3: Satisficer vs Optimizer ──────────────────────────────
    # Satisficers: click early (positions 0-2), visit few positions
    # Optimizers: click late (positions 5+), visit many positions
    # LHIPA detects at p = 10⁻⁵⁹; LF/HF is null

    print('\n3. SATISFICER vs OPTIMIZER (foraging depth)')

    satisficer_ripa2, optimizer_ripa2 = [], []
    satisficer_lfhf, optimizer_lfhf = [], []

    for tid in ripa2_data:
        trial = ripa2_data[tid]
        click_pos = trial.get('click_pos')
        n_visited = trial['n_positions_visited']

        # Classification: satisficers click in top 3 with < 5 positions visited
        # Optimizers visit 6+ positions
        valid_ripa2 = [p['ripa2'] for p in trial['positions']
                       if p['ripa2'] is not None]
        if not valid_ripa2:
            continue
        trial_mean_r = np.mean(valid_ripa2)

        if click_pos is not None and click_pos <= 2 and n_visited <= 5:
            satisficer_ripa2.append(trial_mean_r)
        elif n_visited >= 6:
            optimizer_ripa2.append(trial_mean_r)

        if tid in bw_data:
            valid_lfhf = [p['lfhf'] for p in bw_data[tid]['positions']
                          if p['lfhf'] is not None]
            if not valid_lfhf:
                continue
            trial_mean_l = np.mean(valid_lfhf)

            if click_pos is not None and click_pos <= 2 and n_visited <= 5:
                satisficer_lfhf.append(trial_mean_l)
            elif n_visited >= 6:
                optimizer_lfhf.append(trial_mean_l)

    print_effect('RIPA2', 'Satisficer', satisficer_ripa2,
                 'Optimizer', optimizer_ripa2)
    print_effect('LF/HF', 'Satisficer', satisficer_lfhf,
                 'Optimizer', optimizer_lfhf)

    # ── Effect 4: Boundary clickers ────────────────────────────────────
    # Click at the last-visited position (no further exploration)
    # vs click at an earlier position (selected from evaluated set)
    # LHIPA detects at p = 10⁻⁴; LF/HF is null

    print('\n4. BOUNDARY CLICKERS (click at last-visited vs earlier)')

    boundary_ripa2, interior_ripa2 = [], []
    boundary_lfhf, interior_lfhf = [], []

    for tid in ripa2_data:
        trial = ripa2_data[tid]
        click_pos = trial.get('click_pos')
        if click_pos is None:
            continue

        max_pos = max(p['pos'] for p in trial['positions'])
        valid_ripa2 = [p['ripa2'] for p in trial['positions']
                       if p['ripa2'] is not None]
        if not valid_ripa2:
            continue
        trial_mean_r = np.mean(valid_ripa2)

        if click_pos == max_pos:
            boundary_ripa2.append(trial_mean_r)
        else:
            interior_ripa2.append(trial_mean_r)

        if tid in bw_data:
            valid_lfhf = [p['lfhf'] for p in bw_data[tid]['positions']
                          if p['lfhf'] is not None]
            if not valid_lfhf:
                continue
            trial_mean_l = np.mean(valid_lfhf)

            if click_pos == max_pos:
                boundary_lfhf.append(trial_mean_l)
            else:
                interior_lfhf.append(trial_mean_l)

    print_effect('RIPA2', 'Boundary click', boundary_ripa2,
                 'Interior click', interior_ripa2)
    print_effect('LF/HF', 'Boundary click', boundary_lfhf,
                 'Interior click', interior_lfhf)

    # ── Effect 5: SERP difficulty ──────────────────────────────────────
    # Harder SERPs (low distinctiveness) → more cognitive load
    # LHIPA detects at p = 0.011; LF/HF is null

    print('\n5. SERP DIFFICULTY')

    try:
        diff_data = load_difficulty_measures()
    except FileNotFoundError:
        print('  serp-difficulty-measures.json not found — skipping')
        diff_data = None

    if diff_data:
        easy_ripa2, hard_ripa2 = [], []
        easy_lfhf, hard_lfhf = [], []

        # Use distinctive_density as difficulty proxy
        # Median split: above median = easy (distinctive), below = hard
        densities = {tid: d.get('distinctive_density', None)
                     for tid, d in diff_data.items()
                     if d.get('distinctive_density') is not None}
        if densities:
            med_density = np.median(list(densities.values()))

            for tid in ripa2_data:
                if tid not in densities:
                    continue
                valid_ripa2 = [p['ripa2'] for p in ripa2_data[tid]['positions']
                               if p['ripa2'] is not None]
                if not valid_ripa2:
                    continue
                trial_mean_r = np.mean(valid_ripa2)

                if densities[tid] >= med_density:
                    easy_ripa2.append(trial_mean_r)
                else:
                    hard_ripa2.append(trial_mean_r)

                if tid in bw_data:
                    valid_lfhf = [p['lfhf'] for p in bw_data[tid]['positions']
                                  if p['lfhf'] is not None]
                    if valid_lfhf:
                        trial_mean_l = np.mean(valid_lfhf)
                        if densities[tid] >= med_density:
                            easy_lfhf.append(trial_mean_l)
                        else:
                            hard_lfhf.append(trial_mean_l)

            print_effect('RIPA2', 'Easy (distinctive)', easy_ripa2,
                         'Hard (confusable)', hard_ripa2)
            print_effect('LF/HF', 'Easy (distinctive)', easy_lfhf,
                         'Hard (confusable)', hard_lfhf)

    # ── Summary table ──────────────────────────────────────────────────
    print('\n' + '=' * 70)
    print('SUMMARY TABLE')
    print('=' * 70)
    print('(Compare with notebook 14 Table: LF/HF, LHIPA, Raw PD)')
    print('RIPA2 column fills the fourth slot.')
    print()
    print('Effect                    | LF/HF (nb14) | LHIPA (nb05) | RIPA2 (this)')
    print('-' * 75)


if __name__ == '__main__':
    main()
