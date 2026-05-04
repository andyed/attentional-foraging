"""Reproduce ETTAC §Predicting return from raw inputs.

NOTE 2026-05-03: first cut filtered LF/HF positions through
cursor-approach-features.json — that dropped positions with valid
LF/HF but no cursor-approach record (4,913 vs paper's 6,112). Fixed
to compute will_regress per LF/HF position directly from the trial's
fixation sequence (matching `compute_regression_labels.regressed_positions`
logic). This recovers the full 6,112 denominator.

Public ETTAC paper claim (`ettac-paper/sections/adserp.tex` lines 164-184):

  Per-(trial, organic-rank) median LF/HF differentiates first-pass
  evaluations of items the user later revisits from items they never revisit.
  - participant-level Wilcoxon signed-rank on per-participant
    Δ(returned − not-returned): p = 0.0055
  - 63% of participants showed the direction
  - participant-cluster bootstrap 95% CI on Δ_returned-not = [+0.94, +3.85]
  - N = 6,112 first-pass (trial, position) records, 46 participants

This script recomputes those numbers from the canonical inputs:
  - butterworth-lfhf-by-position.json   (per-(trial, pos) LF/HF, first-pass)
  - regression_labels_cache.json         (per-record will_regress flag,
                                          ordering matches cursor-approach-features.json)
  - cursor-approach-features.json        (per-(trial, pos) records, gives the
                                          ordering for the regression cache)

Methodology note: per-(trial, pos) record = a position with valid
first-pass LF/HF in this trial. The paper denominator is segments, not
trials. We compute under absolute attribution (matches the paper's
explicitly stated h3-counting methodology) and side-by-side under
bbox-organic for robustness.

Run:
  .venv/bin/python scripts/verify_ettac_predicting_return.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path('/Users/andyed/Documents/dev/attentional-foraging')
DATA = ROOT / 'AdSERP/data'

sys.path.insert(0, str(ROOT / 'notebooks-v2'))
sys.path.insert(0, str(ROOT / 'scripts'))
from data_loader import (  # noqa: E402
    load_fixations, get_trial_meta,
    organic_aoi_tops, organic_aoi_bands,
    extract_serp_results, result_band_tops,
    assign_fixation_to_position,
)
from compute_regression_labels import _hybrid_aoi_tops  # noqa: E402

INPUTS = {
    'absolute': {
        'lfhf': DATA / 'butterworth-lfhf-by-position.json',
    },
    'organic': {
        'lfhf': DATA / 'butterworth-lfhf-by-position-organic.json',
    },
}


def regressed_positions_for_trial(trial_id, attribution):
    """Return the set of organic positions the user later gaze-returned to,
    matching the algorithm in compute_regression_labels.regressed_positions.

    A position p is 'regressed' if the user fixated it, max_seen advanced
    past it, and the user later fixated it again."""
    fix = load_fixations(trial_id)
    meta = get_trial_meta(trial_id)
    if not fix or meta is None or not meta[0]:
        return None
    doc_h = meta[0]
    if attribution == 'organic':
        tops = organic_aoi_tops(trial_id)
        n_res = len(tops)
    elif attribution == 'organic_hybrid':
        tops = _hybrid_aoi_tops(trial_id)
        n_res = len(tops)
    else:
        serp = extract_serp_results(trial_id)
        n_res = len(serp) if serp else 10
        tops = result_band_tops(n_res, doc_h) if n_res else []
    if not tops:
        return None
    pos_seq = []
    for f in fix:
        p = assign_fixation_to_position(f['y'], tops, n_res)
        if p is not None and p >= 0:
            pos_seq.append(p)
    visited = set()
    regressed = set()
    max_seen = -1
    for p in pos_seq:
        if p in visited and p < max_seen:
            regressed.add(p)
        visited.add(p)
        if p > max_seen:
            max_seen = p
    return regressed


def participant_id(trial_id):
    return trial_id.split('-')[0]


def collect_records(attribution):
    """For each (trial, position) with valid first-pass LF/HF, compute
    will_regress per-trial directly from the fixation sequence — NOT via
    cursor-approach-features (which has a different population of records)."""
    paths = INPUTS[attribution]
    lfhf_by_trial = json.load(open(paths['lfhf']))

    records = []
    n_trials_total = 0
    n_trials_with_regression_data = 0
    for tid, payload in lfhf_by_trial.items():
        positions = [p for p in payload.get('positions', [])
                     if p.get('lfhf') is not None]
        if not positions:
            continue
        n_trials_total += 1
        regressed = regressed_positions_for_trial(tid, attribution)
        if regressed is None:
            continue
        n_trials_with_regression_data += 1
        for p in positions:
            pos = int(p['pos'])
            records.append({
                'trial_id': tid, 'pid': participant_id(tid),
                'pos': pos, 'lfhf': float(p['lfhf']),
                'returned': pos in regressed,
            })
    print(f'  trials with LF/HF: {n_trials_total:,}  '
          f'trials with regression labels computed: {n_trials_with_regression_data:,}',
          file=sys.stderr)
    return records


def participant_deltas(records):
    """Per participant, return Δ = mean(LF/HF | returned) − mean(LF/HF | not returned).
    Skip participants without both classes."""
    by_pid = defaultdict(lambda: {'returned': [], 'not_returned': []})
    for r in records:
        key = 'returned' if r['returned'] else 'not_returned'
        by_pid[r['pid']][key].append(r['lfhf'])

    deltas = {}
    for pid, vals in by_pid.items():
        if not vals['returned'] or not vals['not_returned']:
            continue
        m_ret = float(np.mean(vals['returned']))
        m_not = float(np.mean(vals['not_returned']))
        deltas[pid] = (m_ret, m_not, m_ret - m_not)
    return deltas


def cluster_bootstrap(deltas, n_boot=2000, rng=None):
    """Bootstrap participants (the cluster level)."""
    if rng is None:
        rng = np.random.default_rng(20260503)
    pids = list(deltas.keys())
    delta_vals = np.array([deltas[p][2] for p in pids])
    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        sample = rng.choice(len(pids), size=len(pids), replace=True)
        boot_means[b] = delta_vals[sample].mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    return float(lo), float(hi)


def report(attribution):
    print(f'\n=== {attribution.upper()} attribution ===', file=sys.stderr)
    records = collect_records(attribution)
    n_records = len(records)
    n_returned = sum(1 for r in records if r['returned'])
    n_not_returned = n_records - n_returned
    pids = sorted({r['pid'] for r in records})
    print(f'  records: {n_records:,}  '
          f'(returned {n_returned:,}, not-returned {n_not_returned:,})  '
          f'participants: {len(pids)}', file=sys.stderr)

    # Variant 1 — per-participant MEAN Δ (the natural reading of the paper's prose)
    deltas = participant_deltas(records)
    delta_mean = np.array([d[2] for d in deltas.values()])
    n_in_test = len(delta_mean)
    pct_pos_mean = 100 * float((delta_mean > 0).mean())
    p_two_mean = float(wilcoxon(delta_mean, alternative='two-sided').pvalue) if n_in_test else float('nan')
    p_one_mean = float(wilcoxon(delta_mean, alternative='greater').pvalue) if n_in_test else float('nan')
    ci_lo, ci_hi = cluster_bootstrap(deltas)

    # Variant 2 — per-participant MEDIAN-of-medians Δ
    by_pid = defaultdict(lambda: {'r': [], 'n': []})
    for r in records:
        by_pid[r['pid']]['r' if r['returned'] else 'n'].append(r['lfhf'])
    deltas_med = []
    for pid, vals in by_pid.items():
        if vals['r'] and vals['n']:
            deltas_med.append(float(np.median(vals['r']) - np.median(vals['n'])))
    deltas_med = np.array(deltas_med)
    pct_pos_med = 100 * float((deltas_med > 0).mean())
    p_two_med = float(wilcoxon(deltas_med, alternative='two-sided').pvalue)
    p_one_med = float(wilcoxon(deltas_med, alternative='greater').pvalue)

    print()
    print(f'{"records (per-(trial, pos)):":<48s}{n_records:>8,}')
    print(f'{"participants in test:":<48s}{n_in_test:>8d}')
    print(f'\n  Variant 1 — per-participant MEAN Δ:')
    print(f'  {"Δ mean across participants:":<46s}{delta_mean.mean():>+8.3f}')
    print(f'  {"% participants Δ > 0:":<46s}{pct_pos_mean:>7.1f}%')
    print(f'  {"Wilcoxon two-sided p:":<46s}{p_two_mean:>8.4f}')
    print(f'  {"Wilcoxon one-sided greater p:":<46s}{p_one_mean:>8.4f}')
    print(f'  {"95% cluster bootstrap CI:":<46s}[{ci_lo:+.3f}, {ci_hi:+.3f}]')

    print(f'\n  Variant 2 — per-participant MEDIAN-of-medians Δ:')
    print(f'  {"Δ median-of-medians:":<46s}{np.median(deltas_med):>+8.3f}')
    print(f'  {"% participants Δ > 0:":<46s}{pct_pos_med:>7.1f}%')
    print(f'  {"Wilcoxon two-sided p:":<46s}{p_two_med:>8.4f}')
    print(f'  {"Wilcoxon one-sided greater p:":<46s}{p_one_med:>8.4f}')

    return {
        'attribution': attribution,
        'n_records': n_records, 'n_returned': n_returned,
        'n_not_returned': n_not_returned,
        'n_participants_total': len(pids),
        'n_participants_in_test': n_in_test,
        'variant1_per_participant_mean_delta': {
            'mean_delta': float(delta_mean.mean()),
            'pct_positive': pct_pos_mean,
            'wilcoxon_p_two_sided': p_two_mean,
            'wilcoxon_p_one_sided_greater': p_one_mean,
            'cluster_bootstrap_ci95': [ci_lo, ci_hi],
        },
        'variant2_per_participant_median_of_medians_delta': {
            'median_of_medians_delta': float(np.median(deltas_med)),
            'pct_positive': pct_pos_med,
            'wilcoxon_p_two_sided': p_two_med,
            'wilcoxon_p_one_sided_greater': p_one_med,
        },
    }


def compare_to_published(abs_result):
    """Quote the absolute-attribution numbers against the published ETTAC values."""
    v1 = abs_result['variant1_per_participant_mean_delta']
    v2 = abs_result['variant2_per_participant_median_of_medians_delta']
    print('\n=== Comparison vs published ETTAC §Predicting return ===\n')
    print(f'  paper claims: p = 0.0055, 63% direction positive, CI [+0.94, +3.85], 6,112 records / 46 participants\n')
    print(f'  {"":>32s}  {"V1 mean-Δ":>12s}  {"V2 median-Δ":>12s}  {"paper":>10s}')
    print(f'  {"records":>32s}  {abs_result["n_records"]:>12,}  {abs_result["n_records"]:>12,}  {"6,112":>10s}')
    print(f'  {"participants":>32s}  {abs_result["n_participants_in_test"]:>12d}  {abs_result["n_participants_in_test"]:>12d}  {"46":>10s}')
    print(f'  {"% participants Δ > 0":>32s}  {v1["pct_positive"]:>11.1f}%  {v2["pct_positive"]:>11.1f}%  {"63%":>10s}')
    print(f'  {"Wilcoxon two-sided p":>32s}  {v1["wilcoxon_p_two_sided"]:>12.4f}  {v2["wilcoxon_p_two_sided"]:>12.4f}  {"0.0055":>10s}')
    print(f'  {"Wilcoxon one-sided greater p":>32s}  {v1["wilcoxon_p_one_sided_greater"]:>12.4f}  {v2["wilcoxon_p_one_sided_greater"]:>12.4f}  {"-":>10s}')
    print(f'  {"95% bootstrap CI on mean Δ":>32s}  '
          f'[{v1["cluster_bootstrap_ci95"][0]:+.3f}, {v1["cluster_bootstrap_ci95"][1]:+.3f}]  '
          f'{"-":>12s}  [+0.94, +3.85]')


def main():
    print('[verify] ETTAC §Predicting return reproduction', file=sys.stderr)
    abs_result = report('absolute')
    org_result = report('organic')
    compare_to_published(abs_result)

    out = {'absolute': abs_result, 'organic': org_result}
    out_path = ROOT / 'scripts/output/aoi-consumer-cascade/verify_ettac_predicting_return.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f'\nwrote {out_path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
