"""Count regress-scan-regress cycles per trial via subordinate HWMs.

Definition of a 'scanning epoch': a contiguous run of fixations that
advance the trial's high-water-mark. The first epoch is the initial
forward scan. After a regression, if the user later advances HWM beyond
the previous max, a new epoch begins.

Per trial, count n_epochs:
  - n_epochs = 1 → pure forward scan (any regressions did NOT later resume scanning beyond HWM)
  - n_epochs = 2 → one regress-scan-regress cycle (user backed off, then pushed past prior HWM, possibly with further regressions)
  - n_epochs >= 3 → multiple regress-scan-regress cycles

Output:
  scripts/output/figures/scan_epochs_summary.json (organic + hybrid side-by-side)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    DATA_DIR, get_trial_ids, load_fixations, get_trial_meta,
    organic_aoi_tops, organic_aoi_bands, assign_fixation_to_position,
)

_AD_DIR = DATA_DIR / 'ad-boundary-data'
_RESULT_COL_X_MIN = 50
_RESULT_COL_X_MAX = 750


def _hybrid_aoi_tops(trial_id):
    bands = organic_aoi_bands(trial_id) or []
    items = [(t, b, 'organic') for t, b in bands]
    ad_path = _AD_DIR / f'{trial_id}.json'
    if ad_path.exists():
        ad_data = json.load(open(ad_path))
        for etype, elements in ad_data.items():
            if etype == 'dd_right':
                continue
            for el in elements:
                loc = el.get('location', {}); size = el.get('size', {})
                rx = loc.get('x', 0); ry = loc.get('y', 0)
                rw = size.get('width', 0); rh = size.get('height', 0)
                if not (rx < _RESULT_COL_X_MAX and (rx + rw) > _RESULT_COL_X_MIN):
                    continue
                items.append((ry, ry + rh, etype))
    if not items:
        return []
    items.sort(key=lambda r: r[0])
    return [r[0] for r in items]


def count_epochs(pos_seq):
    """Walk the position sequence and return n_epochs.

    Epoch 1 = forward sweep until first regression.
    A new epoch begins when, after a regression, HWM advances beyond
    its prior max (i.e., user pushes past where they had been).
    """
    if not pos_seq:
        return 0
    hwm = -1
    in_epoch = True       # currently in a forward-scan epoch
    n_epochs = 0
    has_regressed_since_last_advance = False

    for p in pos_seq:
        if p > hwm:
            # HWM advance
            if not in_epoch and has_regressed_since_last_advance:
                # User has resumed forward scanning after a regression
                n_epochs += 1
                in_epoch = True
                has_regressed_since_last_advance = False
            elif n_epochs == 0:
                # First-ever advance starts epoch 1
                n_epochs = 1
                in_epoch = True
            hwm = p
        else:
            # Not a HWM advance — could be a re-fixation, a regression, or a stay
            if p < hwm:
                # Regression: leaving the forward-sweep epoch
                in_epoch = False
                has_regressed_since_last_advance = True
            # If p == hwm: stayed at the current HWM, no state change
    return n_epochs


def analyze(attribution):
    trial_ids = get_trial_ids()
    n_epochs_by_trial = {}
    n_epochs_by_pid = defaultdict(list)

    for tid in trial_ids:
        fix = load_fixations(tid)
        meta = get_trial_meta(tid)
        if not fix or meta is None or not meta[0]:
            continue
        if attribution == 'hybrid':
            tops = _hybrid_aoi_tops(tid)
        else:
            tops = organic_aoi_tops(tid)
        if not tops:
            continue
        n_res = len(tops)
        pos_seq = []
        for f in fix:
            p = assign_fixation_to_position(f['y'], tops, n_res)
            if p is not None and p >= 0:
                pos_seq.append(p)
        if not pos_seq:
            continue
        ne = count_epochs(pos_seq)
        n_epochs_by_trial[tid] = ne
        pid = tid.split('-')[0]
        n_epochs_by_pid[pid].append(ne)
    return n_epochs_by_trial, n_epochs_by_pid


def report(n_epochs_by_trial, n_epochs_by_pid, label):
    n_trials = len(n_epochs_by_trial)
    counts = Counter(n_epochs_by_trial.values())
    print(f'\n=== {label} ===')
    print(f'  trials analyzed: {n_trials:,}')
    print(f'  participants: {len(n_epochs_by_pid):,}')
    print(f'\n  Distribution of n_epochs per trial:')
    print(f"    {'n_epochs':>9s}  {'trials':>7s}  {'pct':>6s}")
    for n in sorted(counts):
        print(f"    {n:>9d}  {counts[n]:>7,}  {100*counts[n]/n_trials:>5.1f}%")

    # Cumulative summary
    n_with_1 = sum(c for k, c in counts.items() if k >= 1)
    n_with_2 = sum(c for k, c in counts.items() if k >= 2)
    n_with_3 = sum(c for k, c in counts.items() if k >= 3)
    n_with_4 = sum(c for k, c in counts.items() if k >= 4)
    print(f'\n  >=1 epoch: {n_with_1:,} ({100*n_with_1/n_trials:.1f}%)  '
          f'(everyone with any forward scan)')
    print(f'  >=2 epochs: {n_with_2:,} ({100*n_with_2/n_trials:.1f}%)  '
          f'(at least one regress-scan-regress cycle)')
    print(f'  >=3 epochs: {n_with_3:,} ({100*n_with_3/n_trials:.1f}%)  '
          f'(multiple regress-scan-regress cycles)')
    print(f'  >=4 epochs: {n_with_4:,} ({100*n_with_4/n_trials:.1f}%)')

    # Per-participant
    print(f'\n  Per-participant: trials with >=2 epochs (multi-cycle scanning)')
    pid_with_multi = []
    for pid, vals in n_epochs_by_pid.items():
        n_total = len(vals)
        n_multi = sum(1 for v in vals if v >= 2)
        pid_with_multi.append((pid, n_total, n_multi, n_multi / max(n_total, 1)))
    pid_with_multi.sort(key=lambda x: -x[3])
    n_pids_any = sum(1 for _, _, m, _ in pid_with_multi if m >= 1)
    n_pids_atleast5 = sum(1 for _, _, m, _ in pid_with_multi if m >= 5)
    print(f'    participants with >=1 multi-cycle trial: '
          f'{n_pids_any:,} of {len(pid_with_multi):,} '
          f'({100*n_pids_any/len(pid_with_multi):.1f}%)')
    print(f'    participants with >=5 multi-cycle trials: '
          f'{n_pids_atleast5:,} of {len(pid_with_multi):,} '
          f'({100*n_pids_atleast5/len(pid_with_multi):.1f}%)')

    fracs = [m / max(t, 1) for _, t, m, _ in pid_with_multi]
    import numpy as np
    print(f'    per-participant fraction of trials that are multi-cycle: '
          f'mean={np.mean(fracs):.2f}, median={np.median(fracs):.2f}, '
          f'p25={np.percentile(fracs, 25):.2f}, p75={np.percentile(fracs, 75):.2f}')

    return {
        'label': label,
        'n_trials': n_trials,
        'n_participants': len(n_epochs_by_pid),
        'distribution_n_epochs': {str(k): int(v) for k, v in sorted(counts.items())},
        'cumulative': {
            'ge_1': int(n_with_1), 'ge_2': int(n_with_2),
            'ge_3': int(n_with_3), 'ge_4': int(n_with_4),
        },
        'cumulative_pct': {
            'ge_1': 100 * n_with_1 / n_trials,
            'ge_2': 100 * n_with_2 / n_trials,
            'ge_3': 100 * n_with_3 / n_trials,
            'ge_4': 100 * n_with_4 / n_trials,
        },
        'per_participant_multi_cycle_frac': {
            'mean': float(np.mean(fracs)),
            'median': float(np.median(fracs)),
            'p25': float(np.percentile(fracs, 25)),
            'p75': float(np.percentile(fracs, 75)),
        },
        'n_pids_with_any_multi_cycle': int(n_pids_any),
        'n_pids_with_5plus_multi_cycle': int(n_pids_atleast5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', choices=['organic', 'hybrid', 'both'],
                    default='both')
    args = ap.parse_args()

    out = {}
    for attr in (['organic', 'hybrid'] if args.attribution == 'both' else [args.attribution]):
        print(f'\n[walk] attribution={attr}', file=sys.stderr)
        nt, npd = analyze(attr)
        out[attr] = report(nt, npd, attr)

    out_path = ROOT / 'scripts/output/figures/scan_epochs_summary.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
