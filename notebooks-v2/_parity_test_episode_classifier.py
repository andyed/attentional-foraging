"""
Parity gate for episode_classifier.classify_episode vs data_loader.classify_fixations.

For every fixation in a 50-trial sample, call classify_episode at that
fixation's timestamp and require the returned direction to match the
is_forward field from classify_fixations. 100% required — any disagreement
means the episode-level wrapper has drifted from the canonical rule.

Run:
    /Users/andyed/Documents/dev/attentional-foraging/.venv/bin/python \
        notebooks-v2/_parity_test_episode_classifier.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import get_trial_ids, load_trial, classify_fixations
from episode_classifier import classify_episode, clear_cache


def main(n_trials=50, seed=0):
    random.seed(seed)
    all_ids = get_trial_ids()
    sample = random.sample(all_ids, min(n_trials, len(all_ids)))

    total_fixations = 0
    disagreements = []
    trials_with_fixations = 0

    for tid in sample:
        trial = load_trial(tid)
        if trial is None:
            continue
        fixations = trial['fixations']
        if not fixations:
            continue
        trials_with_fixations += 1

        classified = classify_fixations(trial, hwm_tolerance=50)

        for i, (fix, row) in enumerate(zip(fixations, classified)):
            total_fixations += 1
            info = classify_episode(fix['t'], trial, tol_px=50.0)
            ep_forward = info['direction'] == 'forward'
            if ep_forward != row['is_forward']:
                disagreements.append({
                    'trial_id': tid,
                    'fix_idx': i,
                    't': fix['t'],
                    'classify_fixations_is_forward': row['is_forward'],
                    'classify_episode_direction': info['direction'],
                    'entry_scroll': info['entry_scroll'],
                    'hwm_at_entry': info['hwm_at_entry'],
                    'hwm_deficit': info['hwm_deficit'],
                })

    clear_cache()

    print(f'Trials sampled:        {len(sample)}')
    print(f'Trials with fixations: {trials_with_fixations}')
    print(f'Total fixations:       {total_fixations}')
    print(f'Disagreements:         {len(disagreements)}')
    if disagreements:
        print('\nFirst 10 disagreements:')
        for d in disagreements[:10]:
            print(f'  {d}')
        sys.exit(1)
    print('\nPARITY OK — 100% agreement.')


if __name__ == '__main__':
    main()
