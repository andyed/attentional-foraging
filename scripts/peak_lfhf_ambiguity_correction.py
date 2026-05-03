"""Peak-LF/HF click lift, corrected for within-trial candidate-set structure.

Two stratifications:
  A. Available-set size: N = number of organic positions with valid first-pass
     LF/HF. Bins: 2, 3, 4+. (N=1 trials dropped — degenerate peak.)
  B. LF/HF dispersion: spread = (max - min) / median LF/HF within trial.
     Tercile split.

For each stratum, compute peak-vs-non-peak click rate + bootstrap CI,
trial-clustered.

Run:
  .venv/bin/python scripts/peak_lfhf_ambiguity_correction.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
LFHF = ROOT / 'AdSERP/data/butterworth-lfhf-by-position-organic.json'
FEAT = ROOT / 'AdSERP/data/cursor-approach-features-organic.json'
REG = ROOT / 'scripts/output/approach_threshold_sensitivity/regression_labels_cache_organic.json'
OUT = ROOT / 'scripts/output/aoi-consumer-cascade/peak_lfhf_ambiguity_correction.json'


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

    # Build per-trial state
    trial_data = {}  # tid -> {N, peak_pos, dispersion, positions: [(pos, lfhf, clicked, regressed)]}
    for tid, payload in lfhf.items():
        pos_lfhf = [(p['pos'], p['lfhf']) for p in payload.get('positions', [])
                    if p.get('lfhf') is not None]
        if len(pos_lfhf) < 2:
            continue
        peak_pos = max(pos_lfhf, key=lambda x: x[1])[0]
        vals = np.array([v for _, v in pos_lfhf], dtype=float)
        med = float(np.median(vals))
        spread_normed = (vals.max() - vals.min()) / med if med > 0 else float('nan')
        std = float(vals.std(ddof=1))

        positions = []
        for pos, lf in pos_lfhf:
            tp = (tid, pos)
            if tp not in feat_by_tp:
                continue
            clicked, regressed = feat_by_tp[tp]
            positions.append({
                'pos': pos, 'lfhf': lf,
                'is_peak': pos == peak_pos,
                'clicked': clicked,
                'will_regress': regressed,
            })
        if len(positions) < 2:
            continue
        trial_data[tid] = {
            'N': len(positions),
            'peak_pos': peak_pos,
            'spread_normed': spread_normed,
            'std': std,
            'positions': positions,
        }
    print(f'  trials with >=2 valid positions: {len(trial_data):,}', file=sys.stderr)

    # Flatten to record arrays
    rows = []
    for tid, td in trial_data.items():
        for p in td['positions']:
            rows.append({
                'trial_id': tid, 'pos': p['pos'],
                'is_peak': p['is_peak'], 'clicked': p['clicked'],
                'will_regress': p['will_regress'],
                'N': td['N'],
                'spread_normed': td['spread_normed'],
                'std': td['std'],
            })
    n_records = len(rows)
    is_peak = np.array([r['is_peak'] for r in rows])
    clicked = np.array([r['clicked'] for r in rows])
    N = np.array([r['N'] for r in rows])
    spread = np.array([r['spread_normed'] for r in rows])
    trial_ids = np.array([r['trial_id'] for r in rows])
    print(f'  records: {n_records:,}  peak: {is_peak.sum():,}  '
          f'click rate: {100*clicked.mean():.2f}%', file=sys.stderr)

    # Bootstrap CI helper (cluster by trial)
    rng = np.random.default_rng(20260503)
    n_boot = 2000
    unique_trials = np.unique(trial_ids)
    trial_to_indices = {t: np.where(trial_ids == t)[0] for t in unique_trials}

    def boot_lift(subset_mask):
        if subset_mask.sum() == 0:
            return [float('nan'), float('nan')]
        # Restrict to trials present in this subset
        trials_in = np.unique(trial_ids[subset_mask])
        lifts = np.empty(n_boot)
        for b in range(n_boot):
            sampled = rng.choice(trials_in, size=len(trials_in), replace=True)
            idx = np.concatenate([trial_to_indices[t] for t in sampled])
            sub = subset_mask[idx]
            ip = is_peak[idx][sub]
            ck = clicked[idx][sub]
            n_p = ip.sum(); n_np = (~ip).sum()
            if n_p == 0 or n_np == 0:
                lifts[b] = np.nan; continue
            lifts[b] = 100 * (ip & ck).sum() / n_p - 100 * ((~ip) & ck).sum() / n_np
        return [float(np.nanpercentile(lifts, 2.5)),
                float(np.nanpercentile(lifts, 97.5))]

    def stratum_stats(label, mask):
        n_rec = int(mask.sum())
        if n_rec == 0:
            return None
        peak_in = is_peak & mask
        nonpeak_in = (~is_peak) & mask
        n_trials = len(np.unique(trial_ids[mask]))
        n_peak = int(peak_in.sum()); n_nonpeak = int(nonpeak_in.sum())
        rate_peak = 100 * (peak_in & clicked).sum() / max(n_peak, 1)
        rate_nonpeak = 100 * (nonpeak_in & clicked).sum() / max(n_nonpeak, 1)
        lift = rate_peak - rate_nonpeak
        ci = boot_lift(mask)
        return {
            'stratum': label,
            'n_trials': n_trials,
            'n_records': n_rec,
            'n_peak_records': n_peak,
            'n_nonpeak_records': n_nonpeak,
            'peak_click_rate_pct': float(rate_peak),
            'nonpeak_click_rate_pct': float(rate_nonpeak),
            'lift_pp': float(lift),
            'lift_ci95_pp': ci,
        }

    # Stratification A: available-set size
    print('\n=== A. Stratify by available-set size (N positions per trial) ===\n')
    print(f"{'stratum':>14s}  {'trials':>7s}  {'n':>7s}  "
          f"{'peak rate':>10s}  {'non-peak':>10s}  {'lift':>8s}  {'95% CI':>20s}")
    A = []
    for lbl, mask in [
        ('N=2',  N == 2),
        ('N=3',  N == 3),
        ('N=4+', N >= 4),
    ]:
        s = stratum_stats(lbl, mask)
        if s is None:
            continue
        A.append(s)
        print(f"{lbl:>14s}  {s['n_trials']:>7,}  {s['n_records']:>7,}  "
              f"{s['peak_click_rate_pct']:>9.2f}%  {s['nonpeak_click_rate_pct']:>9.2f}%  "
              f"{s['lift_pp']:>+7.2f}  [{s['lift_ci95_pp'][0]:>+5.2f}, "
              f"{s['lift_ci95_pp'][1]:>+5.2f}]")

    # Stratification B: dispersion tercile
    # Tercile cuts on per-trial spread; then expand to records via trial_ids
    trial_spread = {tid: td['spread_normed'] for tid, td in trial_data.items()}
    spreads_sorted = np.array(sorted(trial_spread.values()))
    q33 = float(np.nanpercentile(spreads_sorted, 33.33))
    q67 = float(np.nanpercentile(spreads_sorted, 66.67))
    print(f'\n  spread tercile cuts: low ≤ {q33:.3f} ; mid ≤ {q67:.3f} ; high > {q67:.3f}',
          file=sys.stderr)
    spread_tercile = np.where(spread <= q33, 'low',
                              np.where(spread <= q67, 'mid', 'high'))

    print('\n=== B. Stratify by within-trial LF/HF dispersion ((max-min)/median) ===\n')
    print(f"{'stratum':>14s}  {'trials':>7s}  {'n':>7s}  "
          f"{'peak rate':>10s}  {'non-peak':>10s}  {'lift':>8s}  {'95% CI':>20s}")
    B = []
    for lbl in ['low', 'mid', 'high']:
        mask = spread_tercile == lbl
        s = stratum_stats(f'spread {lbl}', mask)
        if s is None:
            continue
        B.append(s)
        print(f"{'spread '+lbl:>14s}  {s['n_trials']:>7,}  {s['n_records']:>7,}  "
              f"{s['peak_click_rate_pct']:>9.2f}%  {s['nonpeak_click_rate_pct']:>9.2f}%  "
              f"{s['lift_pp']:>+7.2f}  [{s['lift_ci95_pp'][0]:>+5.2f}, "
              f"{s['lift_ci95_pp'][1]:>+5.2f}]")

    # Combined view: dispersion within set-size 4+
    print('\n=== Combined: dispersion stratification within N>=4+ trials ===\n')
    print(f"{'stratum':>22s}  {'trials':>7s}  {'n':>7s}  "
          f"{'peak rate':>10s}  {'non-peak':>10s}  {'lift':>8s}  {'95% CI':>20s}")
    AB = []
    for lbl in ['low', 'mid', 'high']:
        mask = (spread_tercile == lbl) & (N >= 4)
        s = stratum_stats(f'spread {lbl} | N>=4+', mask)
        if s is None:
            continue
        AB.append(s)
        print(f"{'spread '+lbl+' | N>=4':>22s}  {s['n_trials']:>7,}  {s['n_records']:>7,}  "
              f"{s['peak_click_rate_pct']:>9.2f}%  {s['nonpeak_click_rate_pct']:>9.2f}%  "
              f"{s['lift_pp']:>+7.2f}  [{s['lift_ci95_pp'][0]:>+5.2f}, "
              f"{s['lift_ci95_pp'][1]:>+5.2f}]")

    out = {
        'attribution': 'organic',
        'definitions': {
            'N': 'Number of organic positions per trial with valid first-pass LF/HF',
            'spread_normed': '(max LF/HF - min LF/HF) / median LF/HF within trial',
            'is_peak': 'position == argmax LF/HF within trial',
        },
        'tercile_cuts': {'q33_spread': q33, 'q67_spread': q67},
        'A_set_size': A,
        'B_dispersion_tercile': B,
        'AB_dispersion_within_N_geq_4': AB,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
