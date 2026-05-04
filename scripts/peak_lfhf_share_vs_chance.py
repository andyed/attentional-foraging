"""Peak-LF/HF click-share vs chance prior (1/N), stratified by set size.

For each trial where the clicked position has valid first-pass LF/HF and
N = number of valid-LF/HF positions >= 2:
  - is the click on the peak-LF/HF position? (binary)
  - chance baseline = 1/N (uniform random pick over the candidate set)

Aggregate by N: observed peak-share vs 1/N. The lift over chance is
the strength of the LF/HF signal corrected for ambiguity.

Run:
  .venv/bin/python scripts/peak_lfhf_share_vs_chance.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json'
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
REG = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'
OUT = ROOT / 'scripts/output/aoi-consumer-cascade/peak_lfhf_share_vs_chance.json'


def main():
    print('[load] LF/HF + features + regression (organic)', file=sys.stderr)
    lfhf = json.load(open(LFHF))
    feats = json.load(open(FEAT))
    will_regress = json.load(open(REG))
    assert len(feats) == len(will_regress)
    feat_by_tp = {}
    for r, wr in zip(feats, will_regress):
        feat_by_tp[(r['trial_id'], int(r['position']))] = (
            bool(r.get('was_clicked', False)), bool(wr)
        )

    # Per-trial: (peak_pos, N, click_pos, click_will_regress)
    trial_summary = {}
    for tid, payload in lfhf.items():
        pos_lfhf = [(p['pos'], p['lfhf']) for p in payload.get('positions', [])
                    if p.get('lfhf') is not None]
        if len(pos_lfhf) < 2:
            continue
        valid_positions = [pos for pos, _ in pos_lfhf]
        peak_pos = max(pos_lfhf, key=lambda x: x[1])[0]
        # Find the clicked position among valid-LFHF positions
        click_pos = None
        click_will_regress = None
        for pos, _ in pos_lfhf:
            tp = (tid, pos)
            if tp not in feat_by_tp:
                continue
            clicked, regressed = feat_by_tp[tp]
            if clicked:
                click_pos = pos
                click_will_regress = regressed
                break
        if click_pos is None:
            continue  # no click on a valid-LF/HF position; skip
        trial_summary[tid] = {
            'N': len(pos_lfhf),
            'peak_pos': peak_pos,
            'click_pos': click_pos,
            'click_at_peak': click_pos == peak_pos,
            'click_will_regress': click_will_regress,
            'pid': tid.split('-')[0],
        }
    print(f'  trials with click on valid-LFHF position and N>=2: '
          f'{len(trial_summary):,}', file=sys.stderr)

    rng = np.random.default_rng(20260503)
    n_boot = 2000

    def bootstrap_share(trials, observed_shares):
        """Cluster bootstrap by trial; observed_shares is a {trial_id: 1/0} dict."""
        if len(trials) == 0:
            return [float('nan'), float('nan')]
        ts = np.array(trials)
        means = np.empty(n_boot)
        for b in range(n_boot):
            sample = rng.choice(ts, size=len(ts), replace=True)
            vals = [observed_shares[t] for t in sample]
            means[b] = np.mean(vals)
        return [float(np.percentile(means, 2.5)),
                float(np.percentile(means, 97.5))]

    # ── Stratification by N ──
    print('\n=== Peak-LF/HF click-share vs chance (1/N) by set size ===\n')
    print(f"{'N':>3s}  {'trials':>6s}  {'click@peak':>11s}  "
          f"{'observed':>9s}  {'chance':>7s}  "
          f"{'lift (pp)':>10s}  {'fold (×)':>9s}  {'95% CI obs':>20s}")
    by_N = defaultdict(list)
    by_N_share = defaultdict(dict)
    for tid, td in trial_summary.items():
        n_bin = td['N'] if td['N'] <= 4 else 5  # bins: 2, 3, 4, 5+
        by_N[n_bin].append(tid)
        by_N_share[n_bin][tid] = 1 if td['click_at_peak'] else 0
    A = []
    for n_bin_label, n_bin_key in [('N=2', 2), ('N=3', 3), ('N=4', 4), ('N>=5', 5)]:
        trials = by_N[n_bin_key]
        if not trials:
            continue
        n_trials = len(trials)
        n_at_peak = sum(by_N_share[n_bin_key][t] for t in trials)
        obs_share = n_at_peak / n_trials
        # Compute chance prior: uniform 1/N. For N>=5 bin we use the per-trial
        # actual N to compute chance.
        if n_bin_key == 5:
            chance = float(np.mean([1.0 / trial_summary[t]['N'] for t in trials]))
        else:
            chance = 1.0 / n_bin_key
        ci = bootstrap_share(trials, by_N_share[n_bin_key])
        lift_pp = (obs_share - chance) * 100
        fold = obs_share / chance if chance > 0 else float('nan')
        A.append({
            'stratum': n_bin_label,
            'n_trials': n_trials,
            'n_click_at_peak': n_at_peak,
            'observed_share': float(obs_share),
            'chance_prior': float(chance),
            'lift_pp_over_chance': float(lift_pp),
            'fold_over_chance': float(fold),
            'observed_share_ci95': ci,
        })
        print(f"{n_bin_label:>3s}  {n_trials:>6,}  {n_at_peak:>11,}  "
              f"{obs_share:>8.3f}   {chance:>6.3f}   "
              f"{lift_pp:>+9.1f}   {fold:>8.2f}   "
              f"[{ci[0]:.3f}, {ci[1]:.3f}]")

    # ── Same stratification, regressive-click subset only ──
    print('\n=== Same, but regressive-click subset (click_will_regress=True) ===\n')
    print(f"{'N':>3s}  {'trials':>6s}  {'click@peak':>11s}  "
          f"{'observed':>9s}  {'chance':>7s}  "
          f"{'lift (pp)':>10s}  {'fold (×)':>9s}  {'95% CI obs':>20s}")
    B = []
    by_N_reg = defaultdict(list)
    by_N_share_reg = defaultdict(dict)
    for tid, td in trial_summary.items():
        if not td['click_will_regress']:
            continue
        n_bin = td['N'] if td['N'] <= 4 else 5
        by_N_reg[n_bin].append(tid)
        by_N_share_reg[n_bin][tid] = 1 if td['click_at_peak'] else 0
    for n_bin_label, n_bin_key in [('N=2', 2), ('N=3', 3), ('N=4', 4), ('N>=5', 5)]:
        trials = by_N_reg[n_bin_key]
        if not trials:
            continue
        n_trials = len(trials)
        n_at_peak = sum(by_N_share_reg[n_bin_key][t] for t in trials)
        obs_share = n_at_peak / n_trials
        if n_bin_key == 5:
            chance = float(np.mean([1.0 / trial_summary[t]['N'] for t in trials]))
        else:
            chance = 1.0 / n_bin_key
        ci = bootstrap_share(trials, by_N_share_reg[n_bin_key])
        lift_pp = (obs_share - chance) * 100
        fold = obs_share / chance if chance > 0 else float('nan')
        B.append({
            'stratum': n_bin_label + ' (regressive)',
            'n_trials': n_trials,
            'n_click_at_peak': n_at_peak,
            'observed_share': float(obs_share),
            'chance_prior': float(chance),
            'lift_pp_over_chance': float(lift_pp),
            'fold_over_chance': float(fold),
            'observed_share_ci95': ci,
        })
        print(f"{n_bin_label:>3s}  {n_trials:>6,}  {n_at_peak:>11,}  "
              f"{obs_share:>8.3f}   {chance:>6.3f}   "
              f"{lift_pp:>+9.1f}   {fold:>8.2f}   "
              f"[{ci[0]:.3f}, {ci[1]:.3f}]")

    # ── Forward-click subset (click_will_regress=False) ──
    print('\n=== Same, but forward-click subset (click_will_regress=False) ===\n')
    print(f"{'N':>3s}  {'trials':>6s}  {'click@peak':>11s}  "
          f"{'observed':>9s}  {'chance':>7s}  "
          f"{'lift (pp)':>10s}  {'fold (×)':>9s}  {'95% CI obs':>20s}")
    C = []
    by_N_fwd = defaultdict(list)
    by_N_share_fwd = defaultdict(dict)
    for tid, td in trial_summary.items():
        if td['click_will_regress']:
            continue
        n_bin = td['N'] if td['N'] <= 4 else 5
        by_N_fwd[n_bin].append(tid)
        by_N_share_fwd[n_bin][tid] = 1 if td['click_at_peak'] else 0
    for n_bin_label, n_bin_key in [('N=2', 2), ('N=3', 3), ('N=4', 4), ('N>=5', 5)]:
        trials = by_N_fwd[n_bin_key]
        if not trials:
            continue
        n_trials = len(trials)
        n_at_peak = sum(by_N_share_fwd[n_bin_key][t] for t in trials)
        obs_share = n_at_peak / n_trials
        if n_bin_key == 5:
            chance = float(np.mean([1.0 / trial_summary[t]['N'] for t in trials]))
        else:
            chance = 1.0 / n_bin_key
        ci = bootstrap_share(trials, by_N_share_fwd[n_bin_key])
        lift_pp = (obs_share - chance) * 100
        fold = obs_share / chance if chance > 0 else float('nan')
        C.append({
            'stratum': n_bin_label + ' (forward)',
            'n_trials': n_trials,
            'n_click_at_peak': n_at_peak,
            'observed_share': float(obs_share),
            'chance_prior': float(chance),
            'lift_pp_over_chance': float(lift_pp),
            'fold_over_chance': float(fold),
            'observed_share_ci95': ci,
        })
        print(f"{n_bin_label:>3s}  {n_trials:>6,}  {n_at_peak:>11,}  "
              f"{obs_share:>8.3f}   {chance:>6.3f}   "
              f"{lift_pp:>+9.1f}   {fold:>8.2f}   "
              f"[{ci[0]:.3f}, {ci[1]:.3f}]")

    out = {
        'attribution': 'organic',
        'description': (
            'Peak-LF/HF click-share by trial, vs chance prior 1/N. '
            'Trials retained: clicked position has valid first-pass LF/HF AND N >= 2.'
        ),
        'all_clicks_by_N': A,
        'regressive_clicks_by_N': B,
        'forward_clicks_by_N': C,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
