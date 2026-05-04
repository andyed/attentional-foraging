"""Decompose peak-LF/HF prediction by click type (forward vs regressive).

Question: ETTAC §Predicting return shows first-pass LF/HF predicts return.
The within-trial peak-LF/HF position is clicked at 35% vs 10% on other
positions (3.4x lift). We don't yet know whether that lift is concentrated
on forward clicks (commit at peak), regressive clicks (return-and-commit),
or both equally.

Definitions:
  - forward click  = click on (trial, position) where will_regress = False
  - regressive click = click on (trial, position) where will_regress = True
  - peak position  = within-trial argmax of median LF/HF on first-pass

Outputs:
  scripts/output/aoi-consumer-cascade/peak_lfhf_by_click_type.json
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
OUT = ROOT / 'scripts/output/aoi-consumer-cascade/peak_lfhf_by_click_type.json'


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

    peak_pos = {}
    trial_lfhf = {}
    for tid, payload in lfhf.items():
        pos_lfhf = [(p['pos'], p['lfhf']) for p in payload.get('positions', [])
                    if p.get('lfhf') is not None]
        if not pos_lfhf:
            continue
        trial_lfhf[tid] = pos_lfhf
        peak_pos[tid] = max(pos_lfhf, key=lambda x: x[1])[0]

    rows = []
    for tid, pos_lfhf in trial_lfhf.items():
        peak = peak_pos[tid]
        for pos, _ in pos_lfhf:
            tp = (tid, pos)
            if tp not in feat_by_tp:
                continue
            clicked, regressed = feat_by_tp[tp]
            rows.append({'trial_id': tid, 'position': pos,
                         'is_peak': pos == peak, 'clicked': clicked,
                         'will_regress': regressed})

    n = len(rows)
    is_peak = np.array([r['is_peak'] for r in rows])
    clicked = np.array([r['clicked'] for r in rows])
    will_regress_arr = np.array([r['will_regress'] for r in rows])
    print(f'\n  records: {n:,}  trials with valid LF/HF: {len(trial_lfhf):,}')
    print(f'  click rate overall: {100*clicked.mean():.2f}%')
    print(f'  peak-position records: {is_peak.sum():,}  '
          f'click rate at peak: {100*clicked[is_peak].mean():.2f}%')
    print(f'  non-peak records:    {(~is_peak).sum():,}  '
          f'click rate non-peak: {100*clicked[~is_peak].mean():.2f}%')

    print('\n=== Click rate by peak × click-type cells ===')
    print(f"{'cell':>30s}  {'n_records':>10s}  {'n_clicks':>9s}  {'click rate':>12s}")
    cells = {}
    for peak_label, peak_mask in [('peak', is_peak), ('non-peak', ~is_peak)]:
        for click_lbl, click_subset_mask in [
            ('forward (will_regress=F)', ~will_regress_arr),
            ('regressive (will_regress=T)', will_regress_arr),
        ]:
            mask = peak_mask & click_subset_mask
            n_records = int(mask.sum())
            n_clicks = int((mask & clicked).sum())
            rate = 100 * n_clicks / n_records if n_records else float('nan')
            cell_key = f'{peak_label} | {click_lbl}'
            cells[cell_key] = {'n_records': n_records, 'n_clicks': n_clicks,
                               'click_rate_pct': rate}
            print(f"{cell_key:>30s}  {n_records:>10,}  {n_clicks:>9,}  {rate:>11.2f}%")

    n_clicks_total = int(clicked.sum())
    print(f"\n=== Click composition (n = {n_clicks_total:,} clicks total) ===")
    composition = {}
    for peak_label, peak_mask in [('peak', is_peak), ('non-peak', ~is_peak)]:
        for click_lbl, click_subset_mask in [
            ('forward', ~will_regress_arr),
            ('regressive', will_regress_arr),
        ]:
            mask = peak_mask & click_subset_mask & clicked
            n_clicks = int(mask.sum())
            pct = 100 * n_clicks / n_clicks_total
            composition[f'{peak_label} | {click_lbl}'] = {
                'n_clicks': n_clicks, 'pct_of_clicks': pct
            }
            print(f"  {peak_label} | {click_lbl:>10s}  n = {n_clicks:>5,}  "
                  f"({pct:>5.1f}% of clicks)")

    print('\n=== Peak-LF/HF lift, stratified by click type ===\n')
    print(f"{'subset':>32s}  {'n':>6s}  {'peak rate':>12s}  {'non-peak rate':>15s}  {'lift (pp)':>10s}")
    stratified = {}
    rng = np.random.default_rng(20260503)
    n_boot = 2000
    trial_ids = np.array([r['trial_id'] for r in rows])
    unique_trials = np.unique(trial_ids)
    trial_to_indices = {t: np.where(trial_ids == t)[0] for t in unique_trials}

    def boot_lift(subset_mask):
        lifts = np.empty(n_boot)
        for b in range(n_boot):
            sampled_trials = rng.choice(unique_trials, size=len(unique_trials),
                                        replace=True)
            idx = np.concatenate([trial_to_indices[t] for t in sampled_trials])
            sub = subset_mask[idx]
            ip = is_peak[idx][sub]
            ck = clicked[idx][sub]
            n_p = ip.sum(); n_np = (~ip).sum()
            if n_p == 0 or n_np == 0:
                lifts[b] = np.nan; continue
            lifts[b] = 100 * (ip & ck).sum() / n_p - 100 * ((~ip) & ck).sum() / n_np
        return [float(np.nanpercentile(lifts, 2.5)), float(np.nanpercentile(lifts, 97.5))]

    for click_lbl, click_subset_mask in [
        ('all positions', np.ones_like(will_regress_arr, dtype=bool)),
        ('forward-eligible (~regress)', ~will_regress_arr),
        ('regressive-eligible (regress=T)', will_regress_arr),
    ]:
        n_sub = int(click_subset_mask.sum())
        peak_mask_in = is_peak & click_subset_mask
        nonpeak_mask_in = (~is_peak) & click_subset_mask
        rate_peak = 100 * (peak_mask_in & clicked).sum() / max(peak_mask_in.sum(), 1)
        rate_nonpeak = 100 * (nonpeak_mask_in & clicked).sum() / max(nonpeak_mask_in.sum(), 1)
        lift = rate_peak - rate_nonpeak
        ci = boot_lift(click_subset_mask)
        stratified[click_lbl] = {
            'n_records': n_sub,
            'n_peak_records': int(peak_mask_in.sum()),
            'n_nonpeak_records': int(nonpeak_mask_in.sum()),
            'peak_click_rate_pct': float(rate_peak),
            'nonpeak_click_rate_pct': float(rate_nonpeak),
            'lift_pp': float(lift),
            'lift_ci95_pp': ci,
        }
        print(f"{click_lbl:>32s}  {n_sub:>6,}  "
              f"{rate_peak:>11.2f}%  {rate_nonpeak:>14.2f}%  {lift:>+9.2f}  "
              f"95% CI [{ci[0]:>+6.2f}, {ci[1]:>+6.2f}]")

    out = {
        'attribution': 'organic',
        'definitions': {
            'forward_click': 'clicked AND will_regress == False',
            'regressive_click': 'clicked AND will_regress == True',
            'peak_position': 'within-trial argmax of median LF/HF on first-pass segments',
        },
        'cells_by_peak_x_click_type': cells,
        'click_composition': composition,
        'peak_lift_stratified': stratified,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == '__main__':
    main()
